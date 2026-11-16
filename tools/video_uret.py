#!/usr/bin/env python3
"""Haber videosu: senaryo doğrulama, seslendirme, kelime zamanlama, Remotion render ve manifest.

Komutlar:
  py tools/video_uret.py dogrula --id ID --dil tr
  py tools/video_uret.py uret --id ID --dil tr [--ses azure|edge] [--yukle] [--zorla]
  py tools/video_uret.py bekleyenler [--dil tr] [--gunluk]

Senaryo `video/senaryo/<haber id>-<dil>.json`, çıktı `video/cikti/` (git dışı), manifest `data/videolar.json`.
Senaryo metni yalnız veridir: kod olarak değerlendirilmez, kabuğa verilmez; alt süreçlere liste argümanı ve
dosya olarak gider. Seslendirme servisine yalnız haberin herkese açık anlatım metni gider. Kelime sınırı göndermeyen
seslerde (MAI) zamanlar üretilen sesin kendisinden Azure konuşma tanımayla ölçülür; tanımaya yalnız o ses gider.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
ICERIK = ROOT / "data" / "icerik.json"
MANIFEST = ROOT / "data" / "videolar.json"
AYARLAR = ROOT / "sosyal" / "ayarlar.json"
VIDEO = ROOT / "video"
SENARYO = VIDEO / "senaryo"
CIKTI = VIDEO / "cikti"
GECICI = VIDEO / "tmp"
DUZEN_YOLU = VIDEO / "src" / "olcu" / "duzen.json"
GENISLIK_YOLU = VIDEO / "src" / "olcu" / "genislik.json"
YARDIMCI = Path(__file__).with_name("video_ses_yardimci.py")
REMOTION_CLI = VIDEO / "node_modules" / "@remotion" / "cli" / "remotion-cli.js"

SABLON_SURUMU = 3
# 2. sürümde şablonların görünüşü, 3. sürümde kapak resmi değişti; senaryo verisi aynı kaldı: eski sürümle yazılmış
# senaryolar da okunur.
OKUNAN_SURUMLER = (1, 2, 3)
TABAN = "https://medya.ctrl-agame.com/v/"
TZ = timezone(timedelta(hours=3))
EN_KISA, EN_UZUN = 20.0, 80.0
KELIME_ALT, KELIME_UST = 60, 110
ONDEN = 0.25      # sahne görüntüsü sesten biraz önce gelir
KUYRUK = 1.4      # son sözden sonra kapanış için kalan süre
# Kapak resmi (site oynatıcısının posteri, Reels kapağı, YouTube küçük resmi) başlık sahnesinin bir karesidir. Süreler
# video/src ile aynı: sabit girişler (pencere, marka şeridi, çipler, tuşlar, kehribar şerit, alt kart) en geç 1 sn'de
# biter; başlık kelimesi söylendikten 0.25 sn sonra yerine oturur, eşleşmeyen son kelimeler son sözden en çok 0.3 sn
# sonraya yayılır; vurgu kutusu kelime başına 0.07 sn gecikmeyle 0.16 sn'de dolar; kamera sahne sonundan önceki
# 0.6 sn'de bütün başlığı gösterir; pencere sahne sonunda kaymaya başlar, kapak ondan en az 0.1 sn önce alınır.
KAPAK_GIRIS, KAPAK_SOZ, KAPAK_IZ = 1.0, 0.25, 0.3
KAPAK_VURGU, KAPAK_VURGU_ARA = 0.16, 0.07
KAPAK_KAMERA, KAPAK_PAY = 0.6, 0.1
HIZ = "+0%"
DURAK_DB, DURAK_SN = -40, 0.15  # konuşma arası sayılan sessizlik: bu düzeyin altında, en az bu kadar süren
SES_PAKETLERI = {"edge": "edge-tts==7.3.1", "azure": "azure-cognitiveservices-speech==1.53.1"}
VARSAYILAN_KONUSMACI = {"tr": "tr-TR-AhmetNeural", "en": "en-US-AndrewNeural",
                        "fr": "fr-FR-HenriNeural", "es": "es-ES-AlvaroNeural"}
SABLONLAR = ("baslik", "kaynak", "maddeler", "yama_fark", "tarih", "fiyat", "platform", "kapanis")
SIMGELER = ("haber", "guncelleme", "indirim", "ucretsiz", "cikis", "kaynak", "liste", "yama", "takvim",
            "fiyat", "platform", "site")
HAREKETLER = ("zipla", "bas", "tara", "bekle")
TURLER = ("haber", "guncelleme", "indirim", "ucretsiz", "cikis")
TUR_ETIKET = {
    "tr": {"haber": "HABER", "guncelleme": "GÜNCELLEME", "indirim": "İNDİRİM", "ucretsiz": "ÜCRETSİZ", "cikis": "ÇIKIŞ"},
    "en": {"haber": "NEWS", "guncelleme": "UPDATE", "indirim": "DEAL", "ucretsiz": "FREE", "cikis": "RELEASE"},
    "fr": {"haber": "ACTU", "guncelleme": "MISE À JOUR", "indirim": "PROMO", "ucretsiz": "GRATUIT", "cikis": "SORTIE"},
    "es": {"haber": "NOTICIA", "guncelleme": "ACTUALIZACIÓN", "indirim": "OFERTA", "ucretsiz": "GRATIS",
           "cikis": "LANZAMIENTO"},
}
AYLAR = {
    "tr": ["ocak", "şubat", "mart", "nisan", "mayıs", "haziran", "temmuz", "ağustos", "eylül", "ekim", "kasım", "aralık"],
    "en": ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
           "november", "december"],
    "fr": ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
           "novembre", "décembre"],
    "es": ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
           "noviembre", "diciembre"],
}
HAFTA = {"tr": "PSÇPCCP", "en": "MTWTFSS", "fr": "LMMJVSD", "es": "LMXJVSD"}
KAYNAK_ETIKET = {"tr": "RESMÎ KAYNAK", "en": "OFFICIAL SOURCE", "fr": "SOURCE OFFICIELLE", "es": "FUENTE OFICIAL"}
SAYI = re.compile(r"\d+(?:[.,]\d+)*")
NOKTALAMA = "\"'“”‘’()[]{}.,;:!?…«»"
KESMELER = ("'", "’")
CUMLE_SONU = ".!?…:;"
# Altyazı parçası bu kelimelerle bitmez (sonraki kelimeye bağlılar) ve bu eklerle başlamaz (öncekine bağlılar).
BAGLI_SON = frozenset("ve veya ile ya ama fakat ancak hem en bu şu o bir her çok daha "
                      "the a an and or of to in on for with at by "
                      "le la les un une des et ou du au el los las y del con".split())
BAGLI_BAS = frozenset("de da ki mi mı mu mü".split())
KIRILMAZ = 100.0
KIMLIK = re.compile(r"^[a-z0-9][a-z0-9-]{2,150}$")
DIL = re.compile(r"^[a-z]{2}$")
# Neural sesler "tr-TR-AhmetNeural", MAI sesleri "tr-TR-Aydin:MAI-Voice-2.1" biçiminde.
KONUSMACI = re.compile(r"^[a-z]{2,3}-[A-Z]{2}-[A-Za-z]+(?:Neural|:[A-Za-z][A-Za-z0-9.-]{0,40}[A-Za-z0-9])$")
HEDEF = re.compile(r"^(?:[A-Za-z0-9._-]+@)?[A-Za-z0-9._-]+:[A-Za-z0-9._/~-]*$")
# Ses adresi harf harf ya da "nokta kom" diye okur; sahibi bunu duymak istemiyor (2026-11-16). Anlatım sitenin adını söyler.
WEB_ADRESI = re.compile(r"\b[\w-]+\.(?:com|net|org|io|gg|tv|co)(?:\.[a-z]{2})?\b|\bwww\.|\bhttps?://"
                        r"|\b(?:nokta|dot|point|punto)\s+(?:com|kom|net|org)\b", re.I)

_calistir = subprocess.run  # testler sahte koşucu verir


class SenaryoHatasi(ValueError):
    """Senaryo geçersiz; mesaj tüm hataları satır satır içerir."""

    def __init__(self, hatalar: list[str]):
        super().__init__("\n".join(hatalar))
        self.hatalar = hatalar


class UretimHatasi(RuntimeError):
    pass


# ---------------------------------------------------------------- yardımcılar

def json_oku(yol: Path):
    return json.loads(Path(yol).read_text(encoding="utf-8"))


def json_yaz(yol: Path, deger, sirali: bool = False) -> None:
    """Atomik yazım: yarım dosya bırakmaz."""
    yol = Path(yol)
    yol.parent.mkdir(parents=True, exist_ok=True)
    metin = json.dumps(deger, ensure_ascii=False, indent=1, sort_keys=sirali) + "\n"
    fd, gecici = tempfile.mkstemp(dir=yol.parent, prefix=yol.name, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        f.write(metin)
    os.replace(gecici, yol)


def tr_upper(metin: str, dil: str = "tr") -> str:
    """Türkçe büyük harf: i→İ, ı→I (str.upper() i'yi I yapar). Zaten büyük yazılmış yabancı adlar korunur."""
    if dil in ("tr", "az"):
        metin = metin.replace("i", "İ").replace("ı", "I")
    return metin.upper()


def _bosluk(metin: str) -> str:
    return " ".join(metin.split())


_DUZEN = None
_GENISLIK = None


def duzen() -> dict:
    global _DUZEN
    if _DUZEN is None:
        _DUZEN = json_oku(DUZEN_YOLU)
    return _DUZEN


def yazi_genisligi(metin: str, punto: float, agirlik: int = 800, aralik: float = 0.0) -> float:
    """Archivo genişlik tablosuyla piksel genişlik (kerning yok sayılır, pay ile örtülür)."""
    global _GENISLIK
    if _GENISLIK is None:
        _GENISLIK = json_oku(GENISLIK_YOLU)
    harf = _GENISLIK["agirlik"][str(agirlik)]
    yok = _GENISLIK["varsayilan"]
    return punto * sum(harf.get(h, yok) + aralik for h in metin)


def satirlara_bol(metin: str, punto: float, agirlik: int, genislik: float, aralik: float = 0.0) -> list[str]:
    pay = duzen()["altyazi"]["pay"]
    satirlar, simdiki = [], ""
    for kelime in metin.split():
        aday = f"{simdiki} {kelime}" if simdiki else kelime
        if not simdiki or yazi_genisligi(aday, punto, agirlik, aralik) * pay <= genislik:
            simdiki = aday
        else:
            satirlar.append(simdiki)
            simdiki = kelime
    if simdiki:
        satirlar.append(simdiki)
    return satirlar


def _parcala(kelime: str) -> tuple[str, str, str]:
    """Kelimeyi (öndeki noktalama, gövde, arkadaki noktalama) olarak böler."""
    i, j = 0, len(kelime)
    while i < j and kelime[i] in NOKTALAMA:
        i += 1
    while j > i and kelime[j - 1] in NOKTALAMA:
        j -= 1
    return kelime[:i], kelime[i:j], kelime[j:]


def _norm(metin: str) -> str:
    return "".join(c for c in metin.casefold() if c.isalnum())


def _cumle_sonu(kelime: str, sonraki: str | None) -> bool:
    arka = _parcala(kelime)[2]
    if not any(c in CUMLE_SONU for c in arka):
        return False
    if any(c in ":;!?…" for c in arka) or sonraki is None:
        return True
    # "11. yıl" gibi sıra sayıları cümle bitirmez
    govde = _parcala(sonraki)[1]
    return not (govde[:1].islower() and _parcala(kelime)[1].isdigit())


# ---------------------------------------------------------------- doğrulama

class Denetci:
    def __init__(self, haber: dict, dil: str):
        self.hatalar: list[str] = []
        self.uyarilar: list[str] = []
        self.haber = haber
        self.dil = dil
        d = haber["diller"][dil]
        self.kaynak_metin = " ".join([d.get("baslik", ""), d.get("ozet", ""), d.get("metin", "")])
        izin = " ".join([self.kaynak_metin, haber.get("oyun", ""), haber.get("tarih", "").replace("-", " ")])
        sayilar = {m.group() for m in SAYI.finditer(izin)}
        sayilar |= {s.lstrip("0") or "0" for s in sayilar}
        sayilar |= {s.replace(",", ".") for s in sayilar} | {s.replace(".", ",") for s in sayilar}
        self.izinli_sayilar = sayilar

    def hata(self, yol: str, mesaj: str) -> None:
        self.hatalar.append(f"{yol}: {mesaj}")

    def anahtarlar(self, d, izinli: set, yol: str) -> bool:
        if not isinstance(d, dict):
            self.hata(yol, "nesne olmalı")
            return False
        for k in sorted(set(d) - izinli):
            self.hata(f"{yol}.{k}", "bilinmeyen alan")
        return True

    def metin(self, d: dict, anahtar: str, yol: str, en_fazla: int, zorunlu: bool = True,
              alan: str | None = None, buyuk: bool = False) -> str | None:
        v = d.get(anahtar)
        y = f"{yol}.{anahtar}"
        if v is None:
            if zorunlu:
                self.hata(y, "zorunlu")
            return None
        if not isinstance(v, str) or not v.strip():
            self.hata(y, "boş olmayan metin olmalı")
            return None
        if any(ord(c) < 32 for c in v.replace("\n", " ")):
            self.hata(y, "denetim karakteri içeriyor")
            return None
        v = _bosluk(v)
        if buyuk:
            v = tr_upper(v, self.dil)
        if len(v) > en_fazla:
            self.hata(y, f"en çok {en_fazla} karakter ({len(v)})")
        self.sayi(y, v)
        if alan:
            self.sigdir(y, v, alan)
        return v

    def sayi(self, yol: str, metin: str) -> None:
        """Ekranda görünen ya da söylenen her sayı haberin kendi metninde (veya tarihinde) geçmeli."""
        for m in SAYI.finditer(metin):
            if m.group() not in self.izinli_sayilar:
                self.hata(yol, f'"{m.group()}" sayısı haber metninde yok')

    def sigdir(self, yol: str, metin: str, alan: str) -> None:
        o = duzen()["alanlar"][alan]
        aralik = o.get("aralik", 0.0)
        pay = duzen()["altyazi"]["pay"]
        for kelime in metin.split():
            if yazi_genisligi(kelime, o["punto"], o["agirlik"], aralik) * pay > o["genislik"]:
                self.hata(yol, f'"{kelime}" kelimesi alana sığmıyor')
                return
        satir = len(satirlara_bol(metin, o["punto"], o["agirlik"], o["genislik"], aralik))
        if satir > o["satir"]:
            self.hata(yol, f"{satir} satıra taşıyor (en çok {o['satir']})")

    def liste(self, d: dict, anahtar: str, yol: str, en_az: int, en_cok: int, zorunlu: bool = True) -> list:
        v = d.get(anahtar)
        if v is None:
            if zorunlu:
                self.hata(f"{yol}.{anahtar}", "zorunlu")
            return []
        if not isinstance(v, list) or not en_az <= len(v) <= en_cok:
            self.hata(f"{yol}.{anahtar}", f"{en_az}–{en_cok} ögeli liste olmalı")
            return v if isinstance(v, list) else []
        return v


def _tetik(D: Denetci, oge: dict, yol: str, kelimeler: list[str]) -> str | None:
    t = oge.get("tetik")
    if t is None:
        return None
    if not isinstance(t, str) or not t.strip():
        D.hata(f"{yol}.tetik", "metin olmalı")
        return None
    if tetik_bul(t, kelimeler) is None:
        D.hata(f"{yol}.tetik", f'"{t}" bu sahnenin anlatımında geçmiyor')
    return _bosluk(t)


def tetik_bul(tetik: str, kelimeler: list[str]) -> int | None:
    """Tetik ifadesinin anlatımda başladığı kelime sırası (büyük/küçük harf ve ek duyarsız)."""
    parca = [_norm(p) for p in tetik.split()]
    govde = [_norm(_parcala(k)[1]) for k in kelimeler]
    for i in range(len(govde) - len(parca) + 1):
        if all(govde[i + m] == parca[m] if m < len(parca) - 1 else govde[i + m].startswith(parca[m])
               for m in range(len(parca))):
            return i
    return None


def _ogeler(D: Denetci, ham: list, yol: str, kelimeler: list[str], alan: str, en_fazla: int) -> list[dict]:
    cikti = []
    for i, oge in enumerate(ham):
        y = f"{yol}[{i}]"
        if isinstance(oge, str):
            oge = {"metin": oge}
        if not D.anahtarlar(oge, {"metin", "tetik"}, y):
            continue
        cikti.append({"metin": D.metin(oge, "metin", y, en_fazla, alan=alan) or "",
                      "tetik": _tetik(D, oge, y, kelimeler)})
    return cikti


def _ay_bul(ad: str, dil: str) -> int | None:
    ad = ad.casefold()
    for d in (dil, "tr", "en", "fr", "es"):
        if ad in AYLAR[d]:
            return AYLAR[d].index(ad) + 1
    return None


def tarih_coz(metin: str, haber_tarihi: str, dil: str) -> dict | None:
    """"1 Aralık", "13–16 Kasım", "1 de diciembre 2026" → gün aralığı, ay, yıl (yıl yoksa haber tarihinden)."""
    m = re.fullmatch(r"(\d{1,2})(?:\s*[–-]\s*(\d{1,2}))?\s+(?:de\s+)?([^\W\d_]+)(?:\s+(?:de\s+)?(\d{4}))?",
                     metin.strip(), re.IGNORECASE)
    if not m:
        return None
    ay = _ay_bul(m.group(3), dil)
    if not ay:
        return None
    gun_bas = int(m.group(1))
    gun_bit = int(m.group(2) or m.group(1))
    h = date.fromisoformat(haber_tarihi)
    yil = int(m.group(4)) if m.group(4) else (h.year + 1 if ay < h.month else h.year)
    try:
        ilk = date(yil, ay, 1)
        date(yil, ay, gun_bit)
    except ValueError:
        return None
    if gun_bit < gun_bas:
        return None
    gun_sayisi = ((date(yil + (ay == 12), ay % 12 + 1, 1)) - ilk).days
    return {"gun_bas": gun_bas, "gun_bit": gun_bit, "ay": ay, "yil": yil, "ilk_haftagunu": ilk.weekday(),
            "gun_sayisi": gun_sayisi}


def tarih_metni(iso: str, dil: str) -> str:
    g = date.fromisoformat(iso)
    ay = AYLAR[dil][g.month - 1]
    if dil == "en":
        return tr_upper(f"{ay} {g.day}, {g.year}", dil)
    if dil == "es":
        return tr_upper(f"{g.day} de {ay} de {g.year}", dil)
    return tr_upper(f"{g.day} {ay} {g.year}", dil)


def platform_anahtari(ad: str) -> str:
    a = ad.casefold()
    if "playstation" in a or a.startswith("ps"):
        return "ps"
    if "xbox" in a:
        return "xbox"
    if "switch" in a or "nintendo" in a:
        return "switch"
    if a in ("mobil", "mobile", "ios", "android"):
        return "mobil"
    return "pc" if a in ("pc", "windows", "steam", "mac", "linux") else "diger"


def _alan_adi(url: str) -> tuple[str, str]:
    p = urlsplit(url)
    alan = (p.hostname or "").removeprefix("www.")
    yol = p.path.rstrip("/")
    if len(yol) > 30:
        yol = yol[:29] + "…"
    return alan, yol


def _sayi_degeri(metin: str) -> float | None:
    m = SAYI.search(metin)
    if not m:
        return None
    try:
        return float(m.group().replace(".", "").replace(",", ".")) if "," in m.group() else float(m.group())
    except ValueError:
        return None


def _veri_baslik(D, v, y, kel):
    D.anahtarlar(v, {"ust_etiket", "baslik", "vurgu", "tuslar"}, y)
    baslik = D.metin(v, "baslik", y, 90, alan="baslik.baslik") or ""
    vurgu = []
    for i, s in enumerate(D.liste(v, "vurgu", y, 0, 3, zorunlu=False)):
        if not isinstance(s, str) or not s.strip() or s not in baslik:
            D.hata(f"{y}.vurgu[{i}]", "başlıkta aynen geçen bir parça olmalı")
            continue
        vurgu.append({"metin": s, "tetik": s.split()[0] if tetik_bul(s.split()[0], kel) is not None else None})
    tuslar = v.get("tuslar")
    if tuslar is None:
        tuslar = [w[0] for w in D.haber.get("oyun", "").split() if w[:1].isalnum()][:4]
    if not isinstance(tuslar, list) or not 1 <= len(tuslar) <= 4 or not all(isinstance(t, str) and 0 < len(t) <= 3 for t in tuslar):
        D.hata(f"{y}.tuslar", "1–4 ögeli, en çok 3 karakterlik tuş listesi olmalı")
        tuslar = []
    tuslar = [tr_upper(t, D.dil) for t in tuslar]
    for i, t in enumerate(tuslar):
        D.sayi(f"{y}.tuslar[{i}]", t)
        D.sigdir(f"{y}.tuslar[{i}]", t, "baslik.tus")
    return {"ust_etiket": D.metin(v, "ust_etiket", y, 32, alan="baslik.ust_etiket", buyuk=True) or "",
            "baslik": baslik, "vurgu": vurgu, "tuslar": tuslar}


def _veri_kaynak(D, v, y, kel):
    D.anahtarlar(v, {"kaynak", "ad", "alinti", "etiket"}, y)
    kaynaklar = D.haber.get("kaynaklar") or []
    i = v.get("kaynak", 0)
    if not isinstance(i, int) or isinstance(i, bool) or not 0 <= i < len(kaynaklar):
        D.hata(f"{y}.kaynak", f"haberin kaynak listesinde sıra olmalı (0–{len(kaynaklar) - 1})")
        i = 0
    k = kaynaklar[i] if kaynaklar else {"url": "", "ad": ""}
    alan, yol = _alan_adi(k.get("url", ""))
    if not alan:
        D.hata(f"{y}.kaynak", "kaynağın adresi yok")
    ad = D.metin(v, "ad", y, 60, zorunlu=False, alan="kaynak.ad") or _bosluk(k.get("ad", ""))[:60]
    etiket = D.metin(v, "etiket", y, 24, zorunlu=False, alan="kaynak.etiket", buyuk=True) or KAYNAK_ETIKET.get(D.dil, "")
    return {"alan": alan, "yol": yol, "ad": ad, "etiket": etiket,
            "alinti": D.metin(v, "alinti", y, 150, alan="kaynak.alinti") or "",
            "tarih": tarih_metni(k.get("tarih") or D.haber["tarih"], D.dil)}


def _veri_maddeler(D, v, y, kel):
    D.anahtarlar(v, {"baslik", "maddeler"}, y)
    return {"baslik": D.metin(v, "baslik", y, 30, alan="pencere_basligi", buyuk=True) or "",
            "maddeler": _ogeler(D, D.liste(v, "maddeler", y, 2, 4), f"{y}.maddeler", kel, "maddeler.metin", 70)}


def _veri_yama_fark(D, v, y, kel):
    D.anahtarlar(v, {"baslik", "satirlar"}, y)
    satirlar = []
    for i, s in enumerate(D.liste(v, "satirlar", y, 1, 3)):
        ys = f"{y}.satirlar[{i}]"
        if not D.anahtarlar(s, {"ad", "eski", "yeni", "birim", "tetik"}, ys):
            continue
        eski = D.metin(s, "eski", ys, 12, alan="yama_fark.deger") or ""
        yeni = D.metin(s, "yeni", ys, 12, alan="yama_fark.deger") or ""
        a, b = _sayi_degeri(eski), _sayi_degeri(yeni)
        yon = "ayni" if a is None or b is None or a == b else ("azalis" if b < a else "artis")
        tepe = max(a or 0, b or 0) or 1
        satirlar.append({"ad": D.metin(s, "ad", ys, 30, alan="yama_fark.ad", buyuk=True) or "", "eski": eski,
                         "yeni": yeni, "birim": D.metin(s, "birim", ys, 12, zorunlu=False, buyuk=True) or "",
                         "yon": yon, "eski_oran": round((a or 0) / tepe, 4), "yeni_oran": round((b or 0) / tepe, 4),
                         "tetik": _tetik(D, s, ys, kel)})
    return {"baslik": D.metin(v, "baslik", y, 30, alan="pencere_basligi", buyuk=True) or "", "satirlar": satirlar}


def _veri_tarih(D, v, y, kel):
    D.anahtarlar(v, {"etiket", "tarih", "not"}, y)
    metin = D.metin(v, "tarih", y, 24) or ""
    cozum = tarih_coz(metin, D.haber["tarih"], D.dil) if metin else None
    if metin and not cozum:
        D.hata(f"{y}.tarih", 'gün ve ay adı olmalı ("1 Aralık", "13–16 Kasım")')
    if metin and _norm(metin.replace("–", "-")) not in _norm(D.kaynak_metin.replace("–", "-")):
        D.hata(f"{y}.tarih", f'"{metin}" haber metninde aynen geçmiyor')
    cikti = {"etiket": D.metin(v, "etiket", y, 30, alan="pencere_basligi", buyuk=True) or "",
             "not": D.metin(v, "not", y, 70, zorunlu=False, alan="tarih.not") or "",
             "hafta": list(HAFTA.get(D.dil, HAFTA["en"]))}
    if cozum:
        cikti.update(cozum)
        cikti["ay_adi"] = tr_upper(AYLAR[D.dil][cozum["ay"] - 1], D.dil)
        # yıl yalnız haberde geçiyorsa yazılır (ekrandaki her sayı kaynaktan gelir)
        cikti["yil_metin"] = str(cozum["yil"]) if str(cozum["yil"]) in D.izinli_sayilar else ""
        h = date.fromisoformat(D.haber["tarih"])
        cikti["haber_gunu"] = h.day if (h.year, h.month) == (cozum["yil"], cozum["ay"]) else 0
    return cikti


def _veri_fiyat(D, v, y, kel):
    D.anahtarlar(v, {"durum", "etiket", "bitis", "eski_fiyat", "yeni_fiyat", "indirim", "magazalar"}, y)
    durum = v.get("durum")
    if durum not in ("ucretsiz", "indirim"):
        D.hata(f"{y}.durum", '"ucretsiz" veya "indirim" olmalı')
    magazalar = []
    for i, m in enumerate(D.liste(v, "magazalar", y, 0, 6, zorunlu=False)):
        if not isinstance(m, str):
            D.hata(f"{y}.magazalar[{i}]", "metin olmalı")
            continue
        magazalar.append(D.metin({"m": m}, "m", f"{y}.magazalar[{i}]", 24, alan="fiyat.magaza") or "")
    return {"durum": durum or "ucretsiz",
            "etiket": D.metin(v, "etiket", y, 22, alan="fiyat.etiket", buyuk=True) or "",
            "bitis": D.metin(v, "bitis", y, 30, zorunlu=False, alan="fiyat.bitis", buyuk=True) or "",
            "eski_fiyat": D.metin(v, "eski_fiyat", y, 14, zorunlu=False, alan="fiyat.fiyat") or "",
            "yeni_fiyat": D.metin(v, "yeni_fiyat", y, 14, zorunlu=False, alan="fiyat.fiyat") or "",
            "indirim": D.metin(v, "indirim", y, 8, zorunlu=False) or "", "magazalar": magazalar}


def _veri_platform(D, v, y, kel):
    D.anahtarlar(v, {"baslik", "platformlar", "not", "sayilar"}, y)
    haber_pl = D.haber.get("platform") or []
    pl = v.get("platformlar", haber_pl)
    if not isinstance(pl, list) or len(pl) > 4 or any(p not in haber_pl for p in pl):
        D.hata(f"{y}.platformlar", f"haberin platform listesinden en çok 4 öge olmalı ({', '.join(haber_pl) or 'haberde yok'})")
        pl = [p for p in pl if p in haber_pl] if isinstance(pl, list) else []
    platformlar = []
    for p in pl:
        ad = p.upper()  # marka adı: Türkçe i→İ kuralı uygulanmaz (PLAYSTATION)
        D.sigdir(f"{y}.platformlar", ad, "platform.ad")
        platformlar.append({"ad": ad, "renk": platform_anahtari(p),
                            "tetik": p if tetik_bul(p, kel) is not None else None})
    sayilar = []
    for i, s in enumerate(D.liste(v, "sayilar", y, 0, 3, zorunlu=False)):
        ys = f"{y}.sayilar[{i}]"
        if not D.anahtarlar(s, {"deger", "etiket", "tetik"}, ys):
            continue
        sayilar.append({"deger": D.metin(s, "deger", ys, 8, alan="platform.deger") or "",
                        "etiket": D.metin(s, "etiket", ys, 26, alan="platform.etiket", buyuk=True) or "",
                        "tetik": _tetik(D, s, ys, kel)})
    if not platformlar and not sayilar:
        D.hata(y, "platform rozeti ya da sayı kutusu olmalı (ikisi birden boş)")
    baslik = D.metin(v, "baslik", y, 30, alan="pencere_basligi", buyuk=True) or ""
    if baslik:
        D.sigdir(f"{y}.baslik", baslik, "platform.baslik")
    return {"baslik": baslik,
            "platformlar": platformlar, "not": D.metin(v, "not", y, 110, zorunlu=False, alan="platform.not") or "",
            "sayilar": sayilar}


def _veri_kapanis(D, v, y, kel):
    D.anahtarlar(v, {"cagri", "alt"}, y)
    return {"cagri": D.metin(v, "cagri", y, 60, alan="kapanis.cagri") or "",
            "alt": D.metin(v, "alt", y, 70, zorunlu=False, alan="kapanis.alt") or "", "adres": "ctrl-agame.com"}


VERI = {"baslik": _veri_baslik, "kaynak": _veri_kaynak, "maddeler": _veri_maddeler, "yama_fark": _veri_yama_fark,
        "tarih": _veri_tarih, "fiyat": _veri_fiyat, "platform": _veri_platform, "kapanis": _veri_kapanis}


def _kisalt(metin: str, alan: str) -> str:
    """Hesaplanan başlık (oyun adı, alan adı) alana sığmazsa sondan kısaltıp … ekler."""
    o = duzen()["alanlar"][alan]
    pay = duzen()["altyazi"]["pay"]

    def sigar(m: str) -> bool:
        return yazi_genisligi(m, o["punto"], o["agirlik"], o.get("aralik", 0.0)) * pay <= o["genislik"]

    if sigar(metin):
        return metin
    kel = metin.split()
    while len(kel) > 1 and not sigar(" ".join(kel) + "…"):
        kel.pop()
    m = " ".join(kel)
    while len(m) > 1 and not sigar(m + "…"):
        m = m[:-1]
    return m.rstrip() + "…"


def _pencere(D: Denetci, sablon: str, veri: dict) -> str:
    """Uygulama penceresinin başlık çubuğundaki yazı."""
    # Platform sahnesi başlığını içerikte büyük yazar; pencerede tekrarlamamak için oyun adı.
    if sablon in ("baslik", "fiyat", "platform"):
        m = (D.haber.get("oyun") or "").upper()  # oyun adı marka: Türkçe büyütme uygulanmaz
    elif sablon == "kaynak":
        m = veri.get("alan", "")
    elif sablon == "tarih":
        m = veri.get("etiket", "")
    elif sablon == "kapanis":
        m = veri.get("adres", "")
    else:
        m = veri.get("baslik", "")
    return _kisalt(m, "pencere_basligi") if m else ""


def _alt_kart(D: Denetci, a, y: str) -> dict:
    if not D.anahtarlar(a, {"simge", "baslik", "alt"}, y):
        return {"simge": "haber", "baslik": "", "alt": "", "baslik_olcek": 1, "alt_olcek": 1}
    simge = a.get("simge")
    if simge not in SIMGELER:
        D.hata(f"{y}.simge", f"şunlardan biri olmalı: {', '.join(SIMGELER)}")
    k = duzen()["kart"]
    genislik = k["genislik"] - k["yazi_sol"] - k["yazi_sag"]
    cikti = {"simge": simge if simge in SIMGELER else "haber"}
    for ad, punto, agirlik, en_fazla in (("baslik", k["baslik_punto"], 800, 26), ("alt", k["alt_punto"], 700, 40)):
        metin = D.metin(a, ad, y, en_fazla, buyuk=True) or ""
        olcek = min(1.0, genislik / max(1.0, yazi_genisligi(metin, punto, agirlik) * duzen()["altyazi"]["pay"]))
        if olcek < k["en_kucuk_olcek"]:
            D.hata(f"{y}.{ad}", "bilgi kartına sığmıyor, kısaltın")
        cikti[ad] = metin
        cikti[f"{ad}_olcek"] = round(olcek, 3)
    return cikti


def okunus_uygula(kelimeler: list[str], okunus: dict, kullanilan: set | None = None) -> list[tuple[list[int], str]]:
    """Gösterilen kelimeleri sözlü birimlere çevirir: [(kelime sıraları, söylenecek metin)].
    Anahtar tam kelime(ler)le, büyük/küçük harf duyarlı eşleşir; kesmeden sonraki ek korunur (Siege'in → Siyc'in)."""
    anahtarlar = sorted(((k.split(), k, v) for k, v in okunus.items()), key=lambda x: -len(x[0]))
    birimler, i = [], 0
    while i < len(kelimeler):
        for parca, ham, deger in anahtarlar:
            n = len(parca)
            if not parca or i + n > len(kelimeler):
                continue
            govde = [_parcala(kelimeler[i + m])[1] for m in range(n)]
            if govde[:-1] != parca[:-1]:
                continue
            ek = "" if govde[-1] == parca[-1] else next(
                (govde[-1][len(parca[-1]):] for ks in KESMELER if govde[-1].startswith(parca[-1] + ks)), None)
            if ek is None:
                continue
            birimler.append((list(range(i, i + n)),
                             _parcala(kelimeler[i])[0] + deger + ek + _parcala(kelimeler[i + n - 1])[2]))
            if kullanilan is not None:
                kullanilan.add(ham)
            i += n
            break
        else:
            birimler.append(([i], kelimeler[i]))
            i += 1
    return birimler


def tahmini_sure(sozlu: str) -> float:
    """Kaba süre tahmini (doğrulama için; gerçek süreyi uret ölçer). Türkçe neural ses ~13 harf/sn, rakamlar uzun okunur."""
    harf = sum(1 for c in sozlu if c.isalpha())
    rakam = sum(1 for c in sozlu if c.isdigit())
    cumle = sum(1 for c in sozlu if c in ".!?:;")
    return harf / 13.0 + rakam * 0.32 + cumle * 0.3 + KUYRUK


def senaryo_hazirla(senaryo, haber: dict, dil: str) -> dict:
    """Senaryoyu doğrular ve şablon verisini Remotion'a hazır biçime getirir. Hata varsa SenaryoHatasi."""
    if dil not in (haber.get("diller") or {}):
        raise SenaryoHatasi([f"dil: haberde {dil} metni yok"])
    D = Denetci(haber, dil)
    if not D.anahtarlar(senaryo, {"id", "dil", "fps", "boyut", "sablon_surumu", "okunus", "sahneler", "ses"}, "senaryo"):
        raise SenaryoHatasi(D.hatalar)
    if senaryo.get("id") != haber["id"]:
        D.hata("id", f"haber kimliğiyle aynı olmalı ({haber['id']})")
    if senaryo.get("dil") != dil:
        D.hata("dil", f'"{dil}" olmalı')
    if senaryo.get("fps", 30) != 30:
        D.hata("fps", "30 olmalı")
    if senaryo.get("boyut", [1080, 1920]) != [1080, 1920]:
        D.hata("boyut", "[1080, 1920] olmalı")
    if senaryo.get("sablon_surumu", SABLON_SURUMU) not in OKUNAN_SURUMLER:
        D.hata("sablon_surumu", f"şunlardan biri olmalı: {', '.join(map(str, OKUNAN_SURUMLER))}")
    okunus = senaryo.get("okunus", {})
    if not isinstance(okunus, dict) or not all(
            isinstance(k, str) and isinstance(v, str) and k.strip() and v.strip() and len(k) <= 60 and len(v) <= 80
            for k, v in okunus.items()):
        D.hata("okunus", "metin → metin eşlemesi olmalı (anahtar ≤60, değer ≤80 karakter)")
        okunus = {}
    for k, v in okunus.items():
        D.sayi(f"okunus.{k}", v)
    sahneler = senaryo.get("sahneler")
    if not isinstance(sahneler, list) or not 3 <= len(sahneler) <= 9:
        D.hata("sahneler", "3–9 sahnelik liste olmalı")
        raise SenaryoHatasi(D.hatalar)
    hazir, kullanilan, sozlu = [], set(), []
    for i, s in enumerate(sahneler):
        y = f"sahneler[{i}]"
        if not D.anahtarlar(s, {"sablon", "anlatim", "veri", "alt_kart", "maskot", "bas", "bit", "altyazi"}, y):
            continue
        for k in ("bas", "bit", "altyazi"):
            if k in s:
                D.uyarilar.append(f"{y}.{k}: zamanlamadan hesaplanır, yazılan değer yok sayıldı")
        sablon = s.get("sablon")
        if sablon not in SABLONLAR:
            D.hata(f"{y}.sablon", f"şunlardan biri olmalı: {', '.join(SABLONLAR)}")
            continue
        anlatim = D.metin(s, "anlatim", y, 600) or ""
        kel = anlatim.split()
        veri = VERI[sablon](D, s.get("veri") if isinstance(s.get("veri"), dict) else {}, f"{y}.veri", kel)
        if not isinstance(s.get("veri"), dict):
            D.hata(f"{y}.veri", "nesne olmalı")
        veri["pencere"] = _pencere(D, sablon, veri)
        maskot = s.get("maskot") or {}
        hareket = None
        if D.anahtarlar(maskot, {"hareket", "konum"}, f"{y}.maskot"):
            hareket = maskot.get("hareket")
            if hareket is not None and hareket not in HAREKETLER:
                D.hata(f"{y}.maskot.hareket", f"şunlardan biri olmalı: {', '.join(HAREKETLER)}")
            if "konum" in maskot:
                D.uyarilar.append(f"{y}.maskot.konum: maskotun yeri şablondan gelir, yok sayıldı")
        birimler = okunus_uygula(kel, okunus, kullanilan)
        sozlu.append(" ".join(b[1] for b in birimler))
        if WEB_ADRESI.search(anlatim) or WEB_ADRESI.search(sozlu[-1]):
            D.hata(f"{y}.anlatim", "web adresi seslendirilmez; sitenin adını yazın "
                                   "(ör. \"tamamı sitemizde, Control A Game'de\")")
        hazir.append({"sablon": sablon, "anlatim": anlatim, "kelimeler": kel, "birimler": birimler, "veri": veri,
                      "alt_kart": _alt_kart(D, s.get("alt_kart"), f"{y}.alt_kart"),
                      "maskot": {"hareket": hareket or ""}})
    if hazir and (hazir[0]["sablon"] != "baslik" or hazir[-1]["sablon"] != "kapanis"):
        D.hata("sahneler", "ilk sahne baslik, son sahne kapanis olmalı")
    for k in sorted(set(okunus) - kullanilan):
        D.uyarilar.append(f'okunus.{k}: anlatımda geçmiyor')
    kelime_sayisi = sum(len(h["kelimeler"]) for h in hazir)
    if not KELIME_ALT <= kelime_sayisi <= KELIME_UST:
        D.uyarilar.append(f"anlatım {kelime_sayisi} kelime; önerilen {KELIME_ALT}–{KELIME_UST}")
    tts = "\n".join(_cumle_bitir(x) for x in sozlu)
    tahmin = tahmini_sure(tts)
    if not EN_KISA <= tahmin <= EN_UZUN:
        D.hata("sahneler", f"tahmini süre {tahmin:.1f} sn; {EN_KISA:.0f}–{EN_UZUN:.0f} sn olmalı")
    if D.hatalar:
        raise SenaryoHatasi(D.hatalar)
    return {"dil": dil, "sahneler": hazir, "tts": tts, "kelime_sayisi": kelime_sayisi,
            "tahmini_sure": round(tahmin, 1), "uyarilar": D.uyarilar}


def _cumle_bitir(metin: str) -> str:
    metin = metin.strip()
    return metin if not metin or metin[-1] in ".!?…" else metin + "."


def senaryo_oku(haber_id: str, dil: str, klasor: Path | None = None):
    if not KIMLIK.match(haber_id) or not DIL.match(dil):
        raise SenaryoHatasi([f"geçersiz kimlik/dil: {haber_id!r} {dil!r}"])
    yol = (klasor or SENARYO) / f"{haber_id}-{dil}.json"
    if not yol.exists():
        raise SenaryoHatasi([f"senaryo yok: {yol.relative_to(ROOT) if yol.is_relative_to(ROOT) else yol}"])
    try:
        return json_oku(yol)
    except json.JSONDecodeError as e:
        raise SenaryoHatasi([f"{yol.name}: JSON okunamadı ({e})"]) from e


def senaryo_dosyasi_denetle(yol: Path, haber: dict, dil: str) -> list[str]:
    """haber_oto için: senaryo dosyası geçerliyse boş liste, değilse hata satırları."""
    try:
        senaryo_hazirla(json_oku(yol), haber, dil)
    except json.JSONDecodeError as e:
        return [f"{Path(yol).name}: JSON okunamadı ({e})"]
    except SenaryoHatasi as e:
        return e.hatalar
    return []


# ---------------------------------------------------------------- zamanlama

_BIRLER = ("", "bir", "iki", "üç", "dört", "beş", "altı", "yedi", "sekiz", "dokuz")
_ONLAR = ("", "on", "yirmi", "otuz", "kırk", "elli", "altmış", "yetmiş", "seksen", "doksan")
_BUYUKLER = ((10 ** 12, "trilyon"), (10 ** 9, "milyar"), (10 ** 6, "milyon"), (1000, "bin"))


def sayi_oku_tr(n: int) -> str:
    """Tam sayının Türkçe okunuşu: 750 → "yedi yüz elli", 1000 → "bin", 2026 → "iki bin yirmi altı"."""
    if n == 0:
        return "sıfır"
    parca = []
    for deger, ad in _BUYUKLER:
        if n >= deger:
            kat, n = divmod(n, deger)
            if not (deger == 1000 and kat == 1):
                parca.append(sayi_oku_tr(kat))
            parca.append(ad)
    yuz, n = divmod(n, 100)
    if yuz:
        parca.extend(([_BIRLER[yuz]] if yuz > 1 else []) + ["yüz"])
    on, bir = divmod(n, 10)
    parca.extend(x for x in (_ONLAR[on], _BIRLER[bir]) if x)
    return " ".join(parca)


def _soz_norm(metin: str, dil: str | None) -> str:
    """Eşleme için sözlü biçim: Türkçede rakamlar okunduğu gibi yazılır (konuşma tanıma "750"yi "yedi yüz elli" verir).
    Seslendirici sınırları rakamı rakam olarak verse de iki taraf aynı çevrildiği için eşleşme bozulmaz."""
    if dil == "tr":
        metin = re.sub(r"\d{1,3}(?:\.\d{3})+(?!\d)|\d+",
                       lambda m: f" {sayi_oku_tr(int(m.group().replace('.', '')))} ", metin)
    return _norm(metin)


def hizala(sozlu_birimler: list[str], sinirlar: list[dict], dil: str | None = None) -> list[tuple[float, float] | None]:
    """Sözlü birimleri seslendirme kelime sınırlarına harf düzeyinde eşler.
    Bir sınır birden çok birimi kapsıyorsa (ör. "1 Aralık'ta") süresi harf payına göre bölünür. Sınırlar seslendiricinin
    kendi olayları da olabilir, sesten konuşma tanımayla çıkmış kelimeler de: ikincisinde yanlış duyulan adlar
    eşleşmeyen harf olarak kalır, o birimler komşularının arasına _doldur ile yerleşir."""
    a, a_sahip, b, b_sahip = [], [], [], []
    for u, s in enumerate(sozlu_birimler):
        for c in _soz_norm(s, dil):
            a.append(c)
            a_sahip.append(u)
    for j, s in enumerate(sinirlar):
        for c in _soz_norm(s["k"], dil):
            b.append(c)
            b_sahip.append(j)
    eslesme: dict[int, dict[int, int]] = {}
    for blok in difflib.SequenceMatcher(None, "".join(a), "".join(b), autojunk=False).get_matching_blocks():
        for d in range(blok.size):
            sayim = eslesme.setdefault(b_sahip[blok.b + d], {})
            u = a_sahip[blok.a + d]
            sayim[u] = sayim.get(u, 0) + 1
    araliklar: list = [None] * len(sozlu_birimler)
    for j in sorted(eslesme):
        sayim, s = eslesme[j], sinirlar[j]
        ilk, son_birim = min(sayim), max(sayim)
        # Tanıma birkaç sözü tek kelimede birleştirebiliyor ("EA app, Steam, Epic" → "epic"). Eşleşme sıralı olduğundan
        # iki uç arasındaki birimler başka kelimeye düşemez; o sürede söylenmişlerdir ve tam harf payı alırlar.
        pay = {u: sayim[u] if u in (ilk, son_birim) else len(_soz_norm(sozlu_birimler[u], dil)) or 1
               for u in range(ilk, son_birim + 1)}
        toplam, bas, sure = sum(pay.values()), s["b"], s["s"] - s["b"]
        for u in range(ilk, son_birim + 1):
            son = bas + sure * pay[u] / toplam
            eski = araliklar[u]
            araliklar[u] = (bas, son) if eski is None else (min(eski[0], bas), max(eski[1], son))
            bas = son
    return araliklar


def _doldur(araliklar: list, agirlik: list[float], son: float) -> list[tuple[float, float]]:
    """Eşleşmeyen birimlere komşular arasındaki boşluğu harf payına göre dağıtır; sırayı tekdüze yapar."""
    n, sonuc, i = len(araliklar), list(araliklar), 0
    while i < n:
        if sonuc[i] is not None:
            i += 1
            continue
        j = i
        while j < n and sonuc[j] is None:
            j += 1
        sol = sonuc[i - 1][1] if i else 0.0
        sag = sonuc[j][0] if j < n else max(son, sol + 0.35 * (j - i))
        sag = max(sag, sol)
        toplam = sum(agirlik[i:j]) or (j - i)
        t = sol
        for k in range(i, j):
            d = (sag - sol) * (agirlik[k] or 1) / toplam
            sonuc[k] = (t, t + d)
            t += d
        i = j
    for k in range(n):
        b, s = sonuc[k]
        if k:
            b = max(b, sonuc[k - 1][0] + 0.01)
        sonuc[k] = (b, max(s, b + 0.05))
    return sonuc


def _duraklara_yerlestir(araliklar: list[tuple[float, float]], duraklar) -> list[tuple[float, float]]:
    """Sesteki durak söz değildir: durağın içinde başlayıp sonra süren birim durak bitince başlar, durağa taşan birim
    durak başında biter. Harf payıyla bölünmüş birleşik tanıma kelimesinin sözleri böylece aralarındaki duraklara
    oturur. Durağı baştan sona kapsayan birime dokunulmaz (kod içi durak: "MBZ-19"). Duraktan sonraki ilk söz
    durak bitiminden en çok 0,25 sn geç başlıyorsa durak bitimine, duraktan önceki son söz durak başından en çok
    0,25 sn önce bitiyorsa durak başına uzatılır: ses orada başlamış ya da sürüyordur (tanıma, MAI sesinde bazı
    kelimeleri ~0,1–0,2 sn geç başlatıp erken bitiriyor, ölçüm 2026-11-16)."""
    sonuc = list(araliklar)
    for d0, d1 in duraklar:
        for k, (b, s) in enumerate(sonuc):
            sonraki = sonuc[k + 1][0] if k + 1 < len(sonuc) else None
            if d0 - 0.03 <= b < d1 < s:
                sonuc[k] = (d1, s)
            elif b < d0 < s <= d1 + 0.03:
                sonuc[k] = (b, d0)
            elif d1 < b <= d1 + 0.25 and (k == 0 or sonuc[k - 1][1] <= d1 + 0.02):
                sonuc[k] = (d1, s)
            elif b < s < d0 and d0 - s <= 0.25 and (sonraki is None or sonraki >= d1 - 0.02):
                sonuc[k] = (b, d0)
    return sonuc


def _tetik_zamani(tetik, kelimeler, zamanlar):
    if not tetik:
        return None
    i = tetik_bul(tetik, kelimeler)
    return None if i is None else zamanlar[i]["b"]


def _gosterim_zamanlari(ogeler: list[dict], kelimeler, zamanlar, bas: float, bit: float) -> None:
    """Ögelerin görünme anı: tetik kelimesi söylendiğinde, yoksa sahnenin konuşma aralığına eşit dağıtılmış."""
    if not ogeler:
        return
    ilk = zamanlar[0]["b"] if zamanlar else bas + 0.3
    son = zamanlar[-1]["s"] if zamanlar else bit - 0.5
    adim = max(0.35, (son - ilk) / len(ogeler))
    onceki = bas + 0.2
    for j, o in enumerate(ogeler):
        t = _tetik_zamani(o.pop("tetik", None), kelimeler, zamanlar)
        if t is None:
            t = ilk + 0.15 + j * adim
        t = min(max(t, onceki + (0.3 if j else 0)), bit - 0.4)
        o["goster"] = round(t, 3)
        onceki = t


def satir_dagit(kelimeler: list[str]) -> tuple[list[list[int]], float] | None:
    """Altyazı parçasını en çok iki satıra böler: tek satıra sığıyorsa tek, değilse en dengeli iki satır.
    Sığmıyorsa None; tek kelime sığmıyorsa küçültme ölçeğiyle döner."""
    A = duzen()["altyazi"]
    en = A["en_genis_kutu"] - 2 * (A["dolgu_x"] + A["cerceve"])
    w = [yazi_genisligi(k, A["punto"], A["agirlik"]) * A["pay"] for k in kelimeler]
    bosluk = yazi_genisligi(" ", A["punto"], A["agirlik"])
    toplam = sum(w) + bosluk * (len(w) - 1)
    if toplam <= en:
        return [list(range(len(w)))], 1.0
    if len(w) == 1:
        return [[0]], round(en / toplam, 3)
    en_iyi = None
    for k in range(1, len(w)):
        uzun = max(sum(w[:k]) + bosluk * (k - 1), sum(w[k:]) + bosluk * (len(w) - k - 1))
        if uzun <= en and (en_iyi is None or uzun < en_iyi[0]):
            en_iyi = (uzun, k)
    if en_iyi is None:
        return None
    k = en_iyi[1]
    return [list(range(k)), list(range(k, len(w)))], 1.0


def kirma_cezasi(onceki: str, sonraki: str) -> float:
    """İki kelime arasında altyazıyı kırmanın bedeli. Sayı, ardındaki birimden ya da sıra sayısının
    ait olduğu kelimeden ayrılmaz ("11. / yılın", "750 / mermi"); bağlaçta bitmek, ekle başlamak pahalı."""
    _, govde, arka = _parcala(onceki)
    sg = _parcala(sonraki)[1].casefold()
    if govde.isdigit() and arka in ("", "."):
        return KIRILMAZ
    ceza = 0.0 if arka else 0.8  # noktalamada kırmak daha doğal
    if govde.isdigit():
        ceza += 4  # "2, 3 veya 5 kişilik" gibi sayı dizileri
    if not arka and govde.casefold() in BAGLI_SON:
        ceza += 4
    if sg in BAGLI_BAS:
        ceza += 4
    if govde[:1].isdigit() and sg[:1].isdigit():
        ceza += 3  # "50'den 30'a" aralığı
    return ceza


def parcalara_bol(kelimeler: list[dict]) -> list[dict]:
    """Altyazı parçaları: sahne ve cümle sonları kesin kırılır; parça 3–5 kelime (çoğu 4), en çok iki satır,
    tek satır yeğlenir. Ölçüler örnek videodan: parça başına ortalama 3,6 kelime, parçaların ~%28'i iki satır."""
    A = duzen()["altyazi"]
    bolumler, simdiki = [], []
    for i, w in enumerate(kelimeler):
        if simdiki and kelimeler[simdiki[-1]]["sahne"] != w["sahne"]:
            bolumler.append(simdiki)
            simdiki = []
        simdiki.append(i)
        sonraki = kelimeler[i + 1]["k"] if i + 1 < len(kelimeler) and kelimeler[i + 1]["sahne"] == w["sahne"] else None
        if _cumle_sonu(w["k"], sonraki):
            bolumler.append(simdiki)
            simdiki = []
    if simdiki:
        bolumler.append(simdiki)
    parcalar = []
    for bolum in bolumler:
        n = len(bolum)
        en_iyi = [math.inf] * (n + 1)
        geri: list = [None] * (n + 1)
        en_iyi[0] = 0.0
        for j in range(1, n + 1):
            for i in range(max(0, j - A["en_cok_kelime"]), j):
                if en_iyi[i] == math.inf:
                    continue
                dagilim = satir_dagit([kelimeler[x]["k"] for x in bolum[i:j]])
                if dagilim is None:
                    continue
                boy = j - i
                ceza = 1.0 + abs(boy - A["hedef_kelime"]) * A["boy_ceza"]
                if boy < A["en_az_kelime"] and n >= A["en_az_kelime"]:
                    ceza += (A["en_az_kelime"] - boy) * 3
                if len(dagilim[0]) > 1:
                    ceza += A["iki_satir_ceza"]
                if j < n:
                    ceza += kirma_cezasi(kelimeler[bolum[j - 1]]["k"], kelimeler[bolum[j]]["k"])
                sure = kelimeler[bolum[j - 1]]["s"] - kelimeler[bolum[i]]["b"]
                ceza += max(0.0, sure - 3.0) * 4
                if dagilim[1] < 1:
                    ceza += 10
                if en_iyi[i] + ceza < en_iyi[j]:
                    en_iyi[j] = en_iyi[i] + ceza
                    geri[j] = (i, dagilim)
        kesim, j = [], n
        while j > 0:
            i, dagilim = geri[j]
            kesim.append((i, j, dagilim))
            j = i
        for i, j, (satirlar, olcek) in reversed(kesim):
            idx = bolum[i:j]
            parcalar.append({"b": kelimeler[idx[0]]["b"], "s": kelimeler[idx[-1]]["s"],
                             "satirlar": [[idx[x] for x in satir] for satir in satirlar], "olcek": olcek})
    for p, sonraki in zip(parcalar, parcalar[1:] + [None]):
        bitis = p["s"] + A["bekleme"]
        p["bitis"] = round(min(bitis, sonraki["b"]) if sonraki else bitis, 3)
    return parcalar


def zamanla(hazir: dict, sinirlar: list[dict], ses_suresi: float, duraklar=()) -> dict:
    """Kelime zamanlarını sahnelere bağlar: sahne ilk sözünden biraz önce başlar, sonrakine kadar sürer.
    duraklar verilirse birim zamanları sesteki duraklara yerleştirilir (_duraklara_yerlestir)."""
    birim_sozlu, birim_kelime, kelimeler = [], [], []
    for si, s in enumerate(hazir["sahneler"]):
        taban = len(kelimeler)
        kelimeler.extend({"k": k, "sahne": si} for k in s["kelimeler"])
        for idx, soz in s["birimler"]:
            birim_sozlu.append(soz)
            birim_kelime.append([taban + x for x in idx])
    dil = hazir.get("dil")
    agirlik = [float(len(_soz_norm(s, dil)) or 1) for s in birim_sozlu]
    son_sinir = max((s["s"] for s in sinirlar), default=0.0)
    birim_zaman = _duraklara_yerlestir(_doldur(hizala(birim_sozlu, sinirlar, dil), agirlik, son_sinir), duraklar)
    for (b, s), idx in zip(birim_zaman, birim_kelime):
        uzunluk = [len(_norm(kelimeler[x]["k"])) or 1 for x in idx]
        t = b
        for x, u in zip(idx, uzunluk):
            d = (s - b) * u / sum(uzunluk)
            kelimeler[x]["b"], kelimeler[x]["s"] = round(t, 3), round(t + d, 3)
            t += d
    sahneler, toplam = [], max(ses_suresi, max((w["s"] for w in kelimeler), default=0) + 0.3) + KUYRUK
    baslar = []
    for si in range(len(hazir["sahneler"])):
        ilk = next((w["b"] for w in kelimeler if w["sahne"] == si), None)
        if si == 0 or ilk is None:
            bas = 0.0 if si == 0 else baslar[-1] + 1.0
        else:
            bas = max(baslar[-1] + 0.8, ilk - ONDEN)
        baslar.append(round(bas, 3))
    for si, s in enumerate(hazir["sahneler"]):
        bas = baslar[si]
        bit = baslar[si + 1] if si + 1 < len(baslar) else round(toplam, 3)
        ws = [w for w in kelimeler if w["sahne"] == si]
        zaman = [{"k": w["k"], "b": w["b"], "s": w["s"]} for w in ws]
        veri = json.loads(json.dumps(s["veri"]))
        for alan in ("maddeler", "satirlar", "sayilar", "vurgu", "platformlar"):
            if isinstance(veri.get(alan), list):
                _gosterim_zamanlari(veri[alan], s["kelimeler"], zaman, bas, bit)
        if s["sablon"] in ("tarih", "fiyat", "kaynak", "kapanis"):
            veri["goster"] = round(min(bas + 0.45, bit - 0.5), 3)
        if s["sablon"] == "fiyat":
            ogeler = [{"ad": m, "tetik": m.split()[0] if tetik_bul(m.split()[0], s["kelimeler"]) is not None else None}
                      for m in veri["magazalar"]]
            _gosterim_zamanlari(ogeler, s["kelimeler"], zaman, bas + 0.9, bit)
            veri["magazalar"] = ogeler
        sahneler.append({"sablon": s["sablon"], "bas": bas, "bit": bit, "veri": veri, "alt_kart": s["alt_kart"],
                         "maskot": s["maskot"], "altyazi": zaman})
    sade = [{"k": w["k"], "b": w["b"], "s": w["s"], "sahne": w["sahne"]} for w in kelimeler]
    parcalar = parcalara_bol(sade)
    return {"sahneler": sahneler, "kelimeler": [{"k": w["k"], "b": w["b"], "s": w["s"]} for w in sade],
            "parcalar": parcalar, "sure": round(toplam, 3)}


def kapak_karesi(sahne: dict, fps: int) -> int:
    """Kapak karesi: başlık sahnesinin bütün girişleri bitmiş, kamera bütün başlıkta, pencere henüz kaymıyor."""
    bas, bit = sahne["bas"], sahne["bit"]
    son_soz = max((w["s"] for w in sahne.get("altyazi") or []), default=bas)
    vurgular = [x["goster"] + KAPAK_VURGU_ARA * (len(str(x.get("metin", "")).split()) - 1) + KAPAK_VURGU
                for x in sahne["veri"].get("vurgu") or []
                if isinstance(x, dict) and isinstance(x.get("goster"), (int, float))]
    an = max(bas + KAPAK_GIRIS, max(bas + 0.4, son_soz) + KAPAK_IZ + KAPAK_SOZ, bit - KAPAK_KAMERA, *vurgular)
    # Anlatım sahne sonuna dayanırsa kare pencere kaymadan önceye çekilir; şablon kapakta başlığı yine tam çizer.
    return max(0, min(math.ceil(an * fps - 1e-6), math.floor((bit - KAPAK_PAY) * fps)))


def vtt_yaz(kelimeler: list[dict], parcalar: list[dict]) -> str:
    def zd(t: float) -> str:
        ms = int(round(t * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d}.{ms % 1000:03d}"

    def kac(s: str) -> str:
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    satirlar = ["WEBVTT", ""]
    for p in parcalar:
        satirlar.append(f"{zd(p['b'])} --> {zd(max(p['bitis'], p['b'] + 0.2))}")
        satirlar.extend(kac(" ".join(kelimeler[i]["k"] for i in satir)) for satir in p["satirlar"])
        satirlar.append("")
    return "\n".join(satirlar)


# ---------------------------------------------------------------- anahtar, manifest, ayar

def anahtar(haber: dict, dil: str, senaryo, ses_ayari: dict) -> str:
    """sha12: haber metni + senaryo + ses ayarı + şablon sürümü. Biri değişince video yeniden üretilir."""
    d = haber["diller"][dil]
    govde = {"haber": {"id": haber["id"], "tarih": haber.get("tarih"), "oyun": haber.get("oyun"),
                       "tur": haber.get("tur"), "platform": haber.get("platform"),
                       "kaynaklar": [k.get("url") for k in haber.get("kaynaklar") or []],
                       "baslik": d.get("baslik"), "ozet": d.get("ozet"), "metin": d.get("metin")},
             "senaryo": senaryo, "ses": ses_ayari, "sablon_surumu": SABLON_SURUMU}
    ham = json.dumps(govde, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(ham.encode("utf-8")).hexdigest()[:12]


def manifest_oku(yol: Path | None = None) -> dict:
    yol = yol or MANIFEST
    m = json_oku(yol) if Path(yol).exists() else {}
    if not isinstance(m, dict):
        raise UretimHatasi(f"{yol}: nesne değil")
    m.setdefault("surum", 1)
    m.setdefault("taban", TABAN)
    if not isinstance(m.setdefault("videolar", {}), dict):
        raise UretimHatasi(f"{yol}: videolar nesne değil")
    return m


def manifest_guncelle(m: dict, haber_id: str, dil: str, kayit: dict) -> dict:
    """Yalnız bu aracın alanlarını yazar; youtube/instagram ve bilinmeyen alanlar korunur.
    Onay izlenmiş içeriğe verilir: anahtar değişince video yeniden onaysız döner."""
    girdi = m["videolar"].setdefault(haber_id, {}).setdefault(dil, {})
    if girdi.get("anahtar") != kayit.get("anahtar"):
        girdi.pop("onay", None)
    girdi.update(kayit)
    girdi.setdefault("youtube", "")
    girdi.setdefault("instagram", "")
    return m


def manifest_yaz(m: dict, yol: Path | None = None) -> None:
    json_yaz(yol or MANIFEST, m, sirali=True)  # tools/video_site.py ile aynı biçim


def video_ayari(yol: Path | None = None) -> dict:
    yol = yol or AYARLAR
    ayar = (json_oku(yol) if Path(yol).exists() else {}).get("video") or {}
    return {"ses": ayar.get("ses") or "azure", "konusmaci": ayar.get("konusmaci") or "",
            "yukleme_hedefi": ayar.get("yukleme_hedefi") or "", "gunluk_en_fazla": int(ayar.get("gunluk_en_fazla", 2))}


# ---------------------------------------------------------------- seslendirme

class Seslendirici:
    """Ortak arayüz: seslendir(metin, klasor) → (mp3 yolu, [{k, b, s}] saniye)."""
    ad = ""

    def __init__(self, konusmaci: str, dil: str):
        if not KONUSMACI.match(konusmaci):
            raise UretimHatasi(f"geçersiz konuşmacı adı: {konusmaci!r}")
        self.konusmaci, self.dil, self.paket = konusmaci, dil, SES_PAKETLERI[self.ad]

    def ayar(self) -> dict:
        return {"saglayici": self.ad, "konusmaci": self.konusmaci, "hiz": HIZ, "paket": self.paket}

    def on_kosul(self) -> None:
        pass

    def seslendir(self, metin: str, klasor: Path) -> tuple[Path, list[dict]]:
        self.on_kosul()
        klasor.mkdir(parents=True, exist_ok=True)
        girdi, ses, olay = klasor / "tts-girdi.json", klasor / "ses.mp3", klasor / "tts-olaylar.json"
        json_yaz(girdi, {"metin": metin, "konusmaci": self.konusmaci, "hiz": HIZ,
                         "dil": self.konusmaci[:5]})
        self._yardimci(self.ad, girdi, ses, olay, "seslendirme", ses)
        return ses, olaylari_kelimeye(json_oku(olay))

    def _yardimci(self, mod: str, girdi: Path, ses: Path, olay: Path, is_adi: str, beklenen: Path) -> None:
        uv = shutil.which("uv")
        if not uv:
            raise UretimHatasi("uv bulunamadı (seslendirme yardımcısı uv ile çalışır)")
        komut = [uv, "run", "--quiet", "--no-project", "--with", self.paket, "python", "-I", str(YARDIMCI),
                 mod, str(girdi), str(ses), str(olay)]
        r = _calistir(komut, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
        if r.returncode != 0 or not beklenen.exists() or not olay.exists():
            raise UretimHatasi(f"{self.ad} {is_adi} başarısız: {(r.stderr or r.stdout or '').strip()[-800:]}")


class EdgeSes(Seslendirici):
    ad = "edge"


class AzureSes(Seslendirici):
    ad = "azure"

    def on_kosul(self) -> None:
        eksik = [k for k in ("AZURE_SPEECH_KEY", "AZURE_SPEECH_REGION") if not os.environ.get(k)]
        if eksik:
            raise UretimHatasi(f"Azure için ortam değişkeni yok: {', '.join(eksik)} (önizleme için --ses edge)")

    def seslendir(self, metin: str, klasor: Path) -> tuple[Path, list[dict]]:
        ses, sinirlar = super().seslendir(metin, klasor)
        if sinirlar:
            return ses, sinirlar
        # MAI-Voice kelime sınırı göndermiyor: zamanlar videoya giren mp3'ün kendisinden, Azure konuşma tanımayla
        # ölçülür. mp3, Remotion'ın da kullandığı ffmpeg ile açılır; böylece iki taraf aynı zaman çizgisini görür.
        wav, girdi, olay = klasor / "tani.wav", klasor / "tani-girdi.json", klasor / "tani-olaylar.json"
        ffmpeg("-i", str(ses), "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(wav))
        json_yaz(girdi, {"dil": self.konusmaci[:5]})
        self._yardimci("tani", girdi, wav, olay, "konuşma tanıma", wav)
        return ses, tanima_sonlarini_kirp(olaylari_kelimeye(json_oku(olay)), sessizlikler(ses))


def tanima_sonlarini_kirp(kelimeler: list[dict], duraklar: list[tuple[float, float]]) -> list[dict]:
    """Konuşma tanıma kelime başlarını sesle ölçer (durak sonrası başlar konuşmanın başlangıcına ~16 ms yakın), ama
    durak önündeki kelimenin süresini durağın ~150 ms içine uzatır (ölçüm 2026-11-16). O bitiş durak başına çekilir.
    Yalnız kelimenin bittiği durak sayılır: birleşik tanıma kelimesi ("EA app, Steam, Epic" → "epic") araya giren
    duraklarda kesilmez. Durak kelimenin ortasındaysa (sonraki kelime durak bitmeden başlıyorsa) dokunulmaz."""
    yeni = [dict(w) for w in kelimeler]
    for d0, d1 in duraklar:
        for i, w in enumerate(yeni):
            sonraki = yeni[i + 1]["b"] if i + 1 < len(yeni) else None
            if w["b"] < d0 < w["s"] <= d1 + 0.1 and (sonraki is None or sonraki >= d1 - 0.05):
                w["s"] = round(max(d0, w["b"] + 0.05), 3)
    return yeni


SESLENDIRICILER = {"edge": EdgeSes, "azure": AzureSes}


def seslendirici(ad: str, konusmaci: str, dil: str) -> Seslendirici:
    if ad not in SESLENDIRICILER:
        raise UretimHatasi(f"bilinmeyen ses sağlayıcı: {ad!r} (edge veya azure)")
    # Ayardaki konuşmacı yalnız kendi dilinde kullanılır: tr-TR sesi İngilizce metni okumasın.
    if not konusmaci or konusmaci.split("-")[0].lower() != dil:
        konusmaci = VARSAYILAN_KONUSMACI.get(dil, "")
    return SESLENDIRICILER[ad](konusmaci, dil)


def olaylari_kelimeye(ham: dict) -> list[dict]:
    """Yardımcının ham olayları (100 ns birim) → [{k, b, s}] saniye."""
    cikti = []
    for o in ham.get("olaylar", []):
        if not isinstance(o.get("metin"), str) or not o["metin"].strip():
            continue
        b = int(o["bas"]) / 1e7
        cikti.append({"k": o["metin"], "b": round(b, 3), "s": round(b + int(o["sure"]) / 1e7, 3)})
    cikti.sort(key=lambda w: w["b"])
    return cikti


def sessizlikler(yol: Path) -> list[tuple[float, float]]:
    """Sesteki duraklar (ffmpeg silencedetect): [(baş, bitiş)] saniye."""
    r = _kos([_node(), str(REMOTION_CLI), "ffmpeg", "-hide_banner", "-nostats", "-i", str(yol), "-af",
              f"silencedetect=noise={DURAK_DB}dB:d={DURAK_SN}", "-f", "null", "-"], cwd=VIDEO, timeout=300)
    bas = [float(x) for x in re.findall(r"silence_start: (-?[0-9.]+)", r.stderr)]
    bit = [float(x) for x in re.findall(r"silence_end: ([0-9.]+)", r.stderr)]
    duraklar = []
    for b, e in zip(bas, bit):
        # silencedetect uzun bir durağı bazen 10 ms arayla ikiye böler (MAI sesinde ölçüldü); tek durak sayılır.
        if duraklar and b - duraklar[-1][1] < 0.03:
            duraklar[-1] = (duraklar[-1][0], e)
        else:
            duraklar.append((max(0.0, b), e))
    return duraklar


def sesle_hizala(kelimeler: list[dict], duraklar: list[tuple[float, float]]) -> list[dict]:
    """Seslendiricinin kelime zamanlarını gerçek sese oturtur.

    Ölçüm (edge, 2026-11-16): kelime sınırları sesten ~95 ms önde; paragraf başındaki kelime duraklamanın bir
    kısmını kendine sayıp ~330 ms önde başlıyordu, altyazı sözden önce yanıyordu. Azure'un kendi kelime sınırları da
    aynı (Ahmet: bitişler ~94 ms, durak sonrası başlar ~313 ms önde). Önce duraklardan önceki kelime bitişleriyle sabit
    kayma bulunur, sonra her durağın bittiği andaki kelimenin başı konuşmanın başladığı ana çekilir.
    Konuşma tanımadan gelen zamanlar sesin kendisinden ölçüldüğü için kaymaz: durak önündeki kelimenin bitişi durağın
    ~150 ms içine taşar, o fark aralık dışında kalır ve kayma sıfır çıkar.
    """
    if not kelimeler or not duraklar:
        return kelimeler
    farklar = []
    for d0, _ in duraklar:
        # Duraktan önce başlamış kelimelerden bitişi durak başına en yakın olan: duraktan hemen önceki söz.
        once = [d0 - w["s"] for w in kelimeler if w["b"] < d0]
        if d0 > 0.05 and once and -0.05 <= min(once, key=abs) <= 0.3:
            farklar.append(min(once, key=abs))
    kayma = min(0.25, max(0.0, sorted(farklar)[len(farklar) // 2])) if farklar else 0.0
    yeni = [{**w, "b": w["b"] + kayma, "s": w["s"] + kayma} for w in kelimeler]
    for d0, d1 in duraklar:
        i = next((j for j, w in enumerate(yeni) if w["s"] > d1), None)
        if i is None:
            continue
        w = yeni[i]
        # Durağı çok önceden başlayıp içine alan kelime (birleşik tanıma kelimesi) durak sonrasına taşınmaz.
        if (d0 - 0.15 <= w["b"] < d1 - 0.04 < w["s"] - 0.09
                and (i == 0 or yeni[i - 1]["s"] <= d1 + 0.02)):
            w["b"] = d1
    return [{**w, "b": round(w["b"], 3), "s": round(w["s"], 3)} for w in yeni]


# ---------------------------------------------------------------- render

def _node() -> str:
    node = shutil.which("node")
    if not node:
        raise UretimHatasi("node bulunamadı")
    if not REMOTION_CLI.exists():
        raise UretimHatasi("video/node_modules yok: önce `npm ci` (video klasöründe)")
    return node


def _kos(komut: list[str], **kw) -> subprocess.CompletedProcess:
    r = _calistir(komut, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)
    if r.returncode != 0:
        raise UretimHatasi(f"{Path(komut[1]).name if len(komut) > 1 else komut[0]} başarısız: "
                           f"{(r.stderr or r.stdout or '').strip()[-1500:]}")
    return r


def ffmpeg(*arg: str) -> None:
    _kos([_node(), str(REMOTION_CLI), "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *arg], cwd=VIDEO,
         timeout=900)


def medya_bilgisi(yol: Path) -> dict:
    r = _kos([_node(), str(REMOTION_CLI), "ffprobe", "-v", "error", "-show_entries",
              "format=duration:stream=codec_type,width,height", "-of", "json", str(yol)], cwd=VIDEO, timeout=120)
    ham = json.loads(r.stdout)
    video = next((s for s in ham.get("streams", []) if s.get("codec_type") == "video"), {})
    return {"sure": float(ham["format"]["duration"]), "genislik": video.get("width"), "yukseklik": video.get("height"),
            "ses_var": any(s.get("codec_type") == "audio" for s in ham.get("streams", []))}


def props_kur(haber: dict, dil: str, hazir: dict, zaman: dict) -> dict:
    fps = 30
    return {"surum": 1, "id": haber["id"], "dil": dil, "fps": fps, "boyut": [1080, 1920], "ses": "ses.mp3",
            "sure": zaman["sure"], "kapak_kare": kapak_karesi(zaman["sahneler"][0], fps),
            "haber": {"oyun": haber.get("oyun", ""), "tur": haber.get("tur") if haber.get("tur") in TURLER else "haber",
                      "tur_etiket": TUR_ETIKET.get(dil, TUR_ETIKET["en"]).get(haber.get("tur"), ""),
                      "platformlar": [{"ad": p.upper(), "renk": platform_anahtari(p)}
                                      for p in (haber.get("platform") or [])[:4]],
                      "tarih": haber.get("tarih", ""), "tarih_metin": tarih_metni(haber["tarih"], dil)},
            "sahneler": zaman["sahneler"], "kelimeler": zaman["kelimeler"], "parcalar": zaman["parcalar"]}


def uret(haber_id: str, dil: str, ses: str | None = None, yukle: bool = False, zorla: bool = False,
         cikti=print) -> dict:
    ayar = video_ayari()
    haber = haber_bul(haber_id)
    senaryo = senaryo_oku(haber_id, dil)
    hazir = senaryo_hazirla(senaryo, haber, dil)
    for u in hazir["uyarilar"]:
        cikti(f"uyarı: {u}")
    sesci = seslendirici(ses or ayar["ses"], ayar["konusmaci"], dil)
    k = anahtar(haber, dil, senaryo, sesci.ayar())
    m = manifest_oku()
    mevcut = m["videolar"].get(haber_id, {}).get(dil)
    taban = f"{haber_id}-{dil}-{k}"
    if mevcut and mevcut.get("anahtar") == k and not zorla:
        cikti(f"atlandı: {haber_id} {dil} zaten hazır (anahtar {k})")
        if yukle:
            yukle_dosyalar([CIKTI / mevcut[a] for a in ("mp4_1080", "mp4_720", "mp4_540", "kapak", "vtt")
                            if mevcut.get(a)], ayar["yukleme_hedefi"], cikti)
        return mevcut
    bas_zaman = time.monotonic()
    ses_anahtari = hashlib.sha256(json.dumps([hazir["tts"], sesci.ayar()], ensure_ascii=False).encode()).hexdigest()[:12]
    ses_klasoru = GECICI / "ses" / ses_anahtari
    if (ses_klasoru / "ses.mp3").exists() and (ses_klasoru / "kelimeler.json").exists():
        ses_yolu, sinirlar = ses_klasoru / "ses.mp3", json_oku(ses_klasoru / "kelimeler.json")
        cikti(f"ses önbellekten: {ses_klasoru.relative_to(ROOT)}")
    else:
        ses_yolu, sinirlar = sesci.seslendir(hazir["tts"], ses_klasoru)
        json_yaz(ses_klasoru / "kelimeler.json", sinirlar)
    if not sinirlar:
        raise UretimHatasi("seslendirme kelime zamanı vermedi")
    # Önbellekte seslendiricinin ham zamanları durur; sese oturtma her üretimde aynı sesten yeniden hesaplanır.
    duraklar = sessizlikler(ses_yolu)
    sinirlar = sesle_hizala(sinirlar, duraklar)
    ses_suresi = medya_bilgisi(ses_yolu)["sure"]
    zaman = zamanla(hazir, sinirlar, ses_suresi, duraklar)
    if not EN_KISA <= zaman["sure"] <= EN_UZUN:
        raise UretimHatasi(f"video süresi {zaman['sure']:.1f} sn; {EN_KISA:.0f}–{EN_UZUN:.0f} sn olmalı, anlatımı ayarlayın")
    is_klasoru = GECICI / taban
    is_klasoru.mkdir(parents=True, exist_ok=True)
    props = props_kur(haber, dil, hazir, zaman)
    json_yaz(is_klasoru / "zamanli.json", props)
    dosya = {"mp4_1080": f"{taban}-1080.mp4", "mp4_720": f"{taban}-720.mp4", "mp4_540": f"{taban}-540.mp4",
             "kapak": f"{taban}-kapak.jpg", "vtt": f"{taban}.vtt"}
    ham_video = is_klasoru / "ham-1080.mp4"
    render_bas = time.monotonic()
    _kos([_node(), str(VIDEO / "render.mjs"), "--girdi", str(is_klasoru / "zamanli.json"), "--ses", str(ses_yolu),
          "--video", str(ham_video), "--kapak", str(is_klasoru / dosya["kapak"])], cwd=VIDEO, timeout=3600)
    render_sure = time.monotonic() - render_bas
    ffmpeg("-i", str(ham_video), "-c", "copy", "-movflags", "+faststart", str(is_klasoru / dosya["mp4_1080"]))
    for ad, boy, crf, ses_bit in (("mp4_720", "720:1280", "24", "96k"), ("mp4_540", "540:960", "26", "80k")):
        ffmpeg("-i", str(ham_video), "-vf", f"scale={boy}:flags=lanczos", "-c:v", "libx264", "-preset", "slow",
               "-crf", crf, "-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709",
               "-color_trc", "bt709", "-color_range", "tv", "-c:a", "aac", "-b:a", ses_bit, "-movflags", "+faststart",
               str(is_klasoru / dosya[ad]))
    (is_klasoru / dosya["vtt"]).write_text(vtt_yaz(props["kelimeler"], props["parcalar"]), encoding="utf-8",
                                           newline="\n")
    olcum = {}
    for ad, boy in (("mp4_1080", (1080, 1920)), ("mp4_720", (720, 1280)), ("mp4_540", (540, 960))):
        b = medya_bilgisi(is_klasoru / dosya[ad])
        if (b["genislik"], b["yukseklik"]) != boy or not b["ses_var"] or not EN_KISA <= b["sure"] <= EN_UZUN:
            raise UretimHatasi(f"{dosya[ad]}: beklenmeyen çıktı {b}")
        olcum[ad] = {**b, "bayt": (is_klasoru / dosya[ad]).stat().st_size}
    CIKTI.mkdir(parents=True, exist_ok=True)
    for ad in dosya.values():
        os.replace(is_klasoru / ad, CIKTI / ad)
    kayit = {"anahtar": k, "sure": round(olcum["mp4_1080"]["sure"], 1), **dosya,
             "uretildi": datetime.now(TZ).isoformat(timespec="seconds")}
    m = manifest_oku()  # render uzun sürer; arada başka yazım olduysa onu koru
    manifest_yaz(manifest_guncelle(m, haber_id, dil, kayit))
    toplam = time.monotonic() - bas_zaman
    cikti(json.dumps({"hazir": haber_id, "dil": dil, "anahtar": k, "sure": kayit["sure"],
                      "render_sn": round(render_sure, 1), "toplam_sn": round(toplam, 1),
                      "dosyalar": {a: {"ad": dosya[a], "bayt": o["bayt"]} for a, o in olcum.items()}},
                     ensure_ascii=False))
    if yukle:
        yukle_dosyalar([CIKTI / ad for ad in dosya.values()], ayar["yukleme_hedefi"], cikti)
    return kayit


def yukle_dosyalar(dosyalar: list[Path], hedef: str, cikti=print) -> bool:
    if not hedef:
        cikti("yükleme atlandı: sosyal/ayarlar.json içinde video.yukleme_hedefi boş")
        return False
    if not HEDEF.match(hedef) or hedef.startswith("-"):
        raise UretimHatasi("video.yukleme_hedefi kullanici@sunucu:/yol biçiminde olmalı")
    eksik = [d.name for d in dosyalar if not d.exists()]
    if eksik:
        raise UretimHatasi(f"yüklenecek dosya yok: {', '.join(eksik)}")
    scp = shutil.which("scp")
    if not scp:
        raise UretimHatasi("scp bulunamadı")
    _kos([scp, "-q", "-B", "--", *map(str, dosyalar), hedef], timeout=1800)
    cikti(f"yüklendi: {len(dosyalar)} dosya")
    return True


# ---------------------------------------------------------------- komutlar

def haberler() -> list[dict]:
    return json_oku(ICERIK)


def haber_bul(haber_id: str, icerik: list[dict] | None = None) -> dict:
    for x in icerik if icerik is not None else haberler():
        if x.get("id") == haber_id:
            return x
    raise SenaryoHatasi([f"haber yok: {haber_id}"])


def dogrula(haber_id: str, dil: str, cikti=print) -> int:
    try:
        hazir = senaryo_hazirla(senaryo_oku(haber_id, dil), haber_bul(haber_id), dil)
    except SenaryoHatasi as e:
        for h in e.hatalar:
            cikti(f"hata: {h}")
        return 1
    for u in hazir["uyarilar"]:
        cikti(f"uyarı: {u}")
    cikti(f"geçerli: {haber_id}-{dil} ({len(hazir['sahneler'])} sahne, {hazir['kelime_sayisi']} kelime, "
          f"tahmini {hazir['tahmini_sure']} sn)")
    return 0


def bekleyenler(dil: str = "tr", gunluk: bool = False, bugun: date | None = None, cikti=print) -> list[str]:
    """Son günlerin (sosyal/ayarlar.json en_eski_gun, varsayılan 3) geçerli senaryolu ama hazır videosu olmayan haberleri."""
    ayarlar = json_oku(AYARLAR) if AYARLAR.exists() else {}
    ayar = video_ayari()
    bugun = bugun or datetime.now(TZ).date()
    m = manifest_oku()
    kalan = math.inf
    if gunluk:
        bugunku = sum(1 for v in m["videolar"].values() for g in v.values()
                      if str(g.get("uretildi", ""))[:10] == bugun.isoformat())
        kalan = max(0, ayar["gunluk_en_fazla"] - bugunku)
    sonuc = []
    for h in sorted(haberler(), key=lambda x: (x.get("tarih", ""), x.get("id", "")), reverse=True):
        if len(sonuc) >= kalan:
            break
        try:
            gun = (bugun - date.fromisoformat(h.get("tarih", ""))).days
        except ValueError:
            continue
        if not 0 <= gun <= ayarlar.get("en_eski_gun", 3) or not (SENARYO / f"{h['id']}-{dil}.json").exists():
            continue
        try:
            senaryo = senaryo_oku(h["id"], dil)
            senaryo_hazirla(senaryo, h, dil)
        except SenaryoHatasi as e:
            print(f"geçersiz senaryo atlandı: {h['id']}-{dil}: {e.hatalar[0]}", file=sys.stderr)
            continue
        k = anahtar(h, dil, senaryo, seslendirici(ayar["ses"], ayar["konusmaci"], dil).ayar())
        if m["videolar"].get(h["id"], {}).get(dil, {}).get("anahtar") != k:
            sonuc.append(h["id"])
            cikti(h["id"])
    return sonuc


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="CTRL+A GAME haber videosu")
    alt = p.add_subparsers(dest="komut", required=True)
    for ad in ("dogrula", "uret"):
        a = alt.add_parser(ad)
        a.add_argument("--id", required=True)
        a.add_argument("--dil", default="tr")
        if ad == "uret":
            a.add_argument("--ses", choices=sorted(SESLENDIRICILER))
            a.add_argument("--yukle", action="store_true")
            a.add_argument("--zorla", action="store_true", help="aynı anahtarlı hazır video olsa da yeniden üret")
    b = alt.add_parser("bekleyenler")
    b.add_argument("--dil", default="tr")
    b.add_argument("--gunluk", action="store_true", help="video.gunluk_en_fazla sınırını uygula")
    a = p.parse_args(argv)
    try:
        if a.komut == "dogrula":
            return dogrula(a.id, a.dil)
        if a.komut == "bekleyenler":
            bekleyenler(a.dil, a.gunluk)
            return 0
        uret(a.id, a.dil, a.ses, a.yukle, a.zorla)
        return 0
    except SenaryoHatasi as e:
        for h in e.hatalar:
            print(f"hata: {h}", file=sys.stderr)
        return 1
    except UretimHatasi as e:
        print(f"hata: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
