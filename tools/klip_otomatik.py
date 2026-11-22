"""Günlük otomatik klip çıkarma (zamanlanmış görev `Komixsi Klip Cikar`, her gün 10:00).

Etkin her yayıncı için `yayin_klip.py otomatik --yayinci <ad> --en-cok 2 --konusma` çalıştırır; işlenmiş yayınları o komut
zaten atlar. Klip üretimi onaylamaz, yüklemez, paylaşmaz, push yapmaz. Üretimden SONRA (kilit bırakıldığında) tek istisna:
`sosyal/ayarlar.json` klip.otomatik_gizli açıksa `klip_yayin.py otomatik-gizli` çalışır (2026-11-22, Cio): yeni klipleri onay.otomatik ile
onaylar, sunucuya yükler, klipler.json'ı push eder, sosyal.yml turunu başlatır; YouTube'a YALNIZ GİZLİ (private) gider, Telegram'a tek mesaj atılır.
Herkese açmak Cio'nun işidir (YouTube Studio). Bu adımın hatası klip üretimini ve çıkış kodunu bozmaz (loga yazılır).
Panelden başlatılan klip işiyle aynı anda çalışmaz (çalışma dizinindeki `klip-cikar.kilit`): kilit doluysa en çok
BEKLEME_SN bekler, olmazsa o gün atlanır ("0 yeni klip onay bekliyor"; ertesi gün tekrar denenir).
Log: C:\\Cihan.Ai\\.scratch\\yayin-klip\\gunluk\\klip-YYYY-MM-DD.log, son satır "N yeni klip onay bekliyor"."""
from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import sys
import time

KOK = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK / "tools"))
import klip_kilit as kk  # noqa: E402

GUNLUK = pathlib.Path(r"C:\Cihan.Ai\.scratch\yayin-klip\gunluk")
CALISMA = pathlib.Path(r"C:\Cihan.Ai\.scratch\yayin-klip")
AYAR = KOK / "otomasyon" / "klip-yayincilar.json"
BEKLEME_SN = 60 * 60
BEKLEME_ARALIK = 30
YAYINCI_ZAMAN_ASIMI = 3 * 3600     # bir yayıncı için üst sınır; aşarsa o yayıncı atlanır, diğerleri sürer
EN_COK_YAYIN = "2"
OTOMATIK_GIZLI_ZAMAN_ASIMI = 2 * 3600   # onay + yükleme + GitHub turu beklemesi için üst sınır

_SIR = re.compile(r"(https?://)[^/@\s]+@|(?i:(token|belirte[cç]|key|secret|password)\s*[=:]\s*)\S+")


def temizle(metin: str) -> str:
    return _SIR.sub(lambda m: (m.group(1) + "***@") if m.group(1) else m.group(2) + "=***", metin)


class Gunluk:
    def __init__(self, yol: pathlib.Path):
        yol.parent.mkdir(parents=True, exist_ok=True)
        self.f = open(yol, "a", encoding="utf-8", buffering=1)

    def yaz(self, satir: str) -> None:
        self.f.write(f"{time.strftime('%H:%M:%S')} {temizle(satir)}\n")
        self.f.flush()

    def kapat(self) -> None:
        self.f.close()


def yayincilar() -> list[str]:
    veri = json.loads(AYAR.read_text(encoding="utf-8"))
    return [str(y["ad"]) for y in veri.get("yayincilar", []) if isinstance(y, dict) and y.get("etkin", True) and y.get("ad")]


def yayinci_calistir(ad: str, log: Gunluk) -> int:
    """Alt süreci satır satır loga yazar; üretilen mp4 sayısını döndürür."""
    komut = [sys.executable, str(KOK / "tools" / "yayin_klip.py"), "--ayar", str(AYAR), "--dizin", str(CALISMA),
             "otomatik", "--yayinci", ad, "--en-cok", EN_COK_YAYIN, "--konusma"]
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONUNBUFFERED": "1", "KLIP_YAYINCILAR": str(AYAR), "YAYIN_KLIP_DIZIN": str(CALISMA)}
    p = subprocess.Popen(komut, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, text=True,
                         encoding="utf-8", errors="replace", env=env, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    bitis = time.monotonic() + YAYINCI_ZAMAN_ASIMI
    n = 0
    import threading
    zaman = threading.Timer(YAYINCI_ZAMAN_ASIMI, lambda: p.kill())
    zaman.daemon = True
    zaman.start()
    try:
        for ham in p.stdout:
            s = " ".join(ham.split())[:400]
            if not s:
                continue
            log.yaz(f"  {ad}: {s}")
            if s.lower().endswith(".mp4"):
                n += 1
            if time.monotonic() > bitis:
                break
    finally:
        zaman.cancel()
    rc = p.wait()
    if time.monotonic() > bitis:
        log.yaz(f"  {ad}: zaman aşımı ({YAYINCI_ZAMAN_ASIMI // 3600} sa), durduruldu")
    log.yaz(f"{ad}: bitti (çıkış kodu {rc}, {n} yeni klip)")
    return n if rc == 0 else -n - 1000      # hata işareti: negatif


def otomatik_gizli_calistir(log: Gunluk) -> int:
    """`klip_yayin.py otomatik-gizli` (ana anahtar kapalıysa komut kendiliğinden bir şey yapmaz). Çıktıyı loga yazar. -> çıkış kodu"""
    komut = [sys.executable, str(KOK / "tools" / "klip_yayin.py"), "otomatik-gizli"]
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONUNBUFFERED": "1", "YAYIN_KLIP_DIZIN": str(CALISMA)}
    kos = subprocess.run(komut, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=str(KOK),
                         stdin=subprocess.DEVNULL, timeout=OTOMATIK_GIZLI_ZAMAN_ASIMI,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    for ham in ((kos.stdout or "") + "\n" + (kos.stderr or "")).splitlines():
        s = " ".join(ham.split())[:400]
        if s:
            log.yaz(f"  otomatik gizli: {s}")
    return kos.returncode


def main() -> int:
    log = Gunluk(GUNLUK / f"klip-{time.strftime('%Y-%m-%d')}.log")
    toplam, hatali = 0, 0
    try:
        log.yaz("Günlük klip çıkarma başladı")
        try:
            adlar = yayincilar()
        except (OSError, ValueError, KeyError) as e:
            log.yaz(f"HATA: yayıncı listesi okunamadı: {e}")
            adlar = []
            hatali += 1
        log.yaz(f"Etkin yayıncı: {', '.join(adlar) or '(yok)'}")
        kilit = kk.Kilit(CALISMA, "günlük otomatik")
        bitis = time.monotonic() + BEKLEME_SN
        while True:
            try:
                kilit.al()
                break
            except kk.KilitDolu as e:
                if time.monotonic() > bitis:
                    log.yaz(f"Başka iş çalışıyor ({e.sahip}); {BEKLEME_SN // 60} dk beklendi, bugün atlandı")
                    adlar = []
                    break
                log.yaz(f"Başka iş çalışıyor ({e.sahip}); bekleniyor")
                time.sleep(BEKLEME_ARALIK)
        try:
            for ad in adlar:
                log.yaz(f"{ad}: yeni yayınlar taranıyor")
                try:
                    n = yayinci_calistir(ad, log)
                except Exception as e:  # noqa: BLE001 — bir yayıncı patlarsa diğerleri sürsün
                    log.yaz(f"HATA: {ad}: {type(e).__name__}: {e}")
                    hatali += 1
                    continue
                if n < 0:
                    hatali += 1
                    n = -n - 1000
                toplam += n
                kilit.tazele()
        finally:
            kilit.birak()
        try:
            rc = otomatik_gizli_calistir(log)
            log.yaz(f"otomatik gizli adımı bitti (çıkış kodu {rc})")
        except Exception as e:  # noqa: BLE001 — onay/yükleme sorunu klip üretimini ve çıkış kodunu bozmaz; ayrıntı yukarıda
            log.yaz(f"UYARI: otomatik gizli adımı tamamlanamadı: {type(e).__name__}: {e}")
        if hatali:
            log.yaz(f"Uyarı: {hatali} yayıncıda hata oldu (ayrıntı yukarıda)")
        log.yaz(f"{toplam} yeni klip onay bekliyor")
        return 1 if hatali else 0
    finally:
        log.kapat()


if __name__ == "__main__":
    sys.exit(main())
