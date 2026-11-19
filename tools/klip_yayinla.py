"""Panelde "Onaylananları yayınla": onaylı ve yüklenmemiş klipleri sunucuya yükler, `klipler.json` değişikliğini commit eder,
önce `git pull --rebase` yapıp push eder. YALNIZ Cio'nun düğmeye tıklamasıyla çalışır (panel uçları belirteç + Origin ister).

Yükleme, `klip_yayin.py yukle` komutunun kendisidir (alt süreç): onay özeti, boyut denetimi ve klip hesabı kuralları orada.
Git adımları liste argümanıyla (kabuk yok) çalışır. Çakışmada rebase iptal edilir, hata sayfada gösterilir, commit yerelde kalır.
Testte `_kos` ve `YUKLE_KOMUTU` sahtelenir: gerçek yükleme ve gerçek push yapılmaz."""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import threading
import time
from typing import Callable

KOK = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK / "tools"))
import klip_sosyal as ks  # noqa: E402


class Hata(Exception):
    pass


YUKLE_KOMUTU: list[str] | None = None     # yalnız test
YUKLE_ZAMAN_ASIMI = 4 * 3600
GIT_ZAMAN_ASIMI = 300
SON_SATIR_SAYISI = 8
BITTI_SURESI = 900


def _gizle(metin: str) -> str:
    """Çıktıdaki olası kimlik bilgilerini (https://kullanici:belirtec@...) sayfaya/loga taşıma."""
    return re.sub(r"(https?://)[^/@\s]+@", r"\1***@", metin or "")


def _kos(argv: list[str], zaman_asimi: float, cwd: pathlib.Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(argv, cwd=str(cwd) if cwd else None, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=zaman_asimi, stdin=subprocess.DEVNULL,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def _son_satirlar(cp: subprocess.CompletedProcess, n: int = 4) -> str:
    satirlar = [" ".join(x.split()) for x in ((cp.stdout or "") + "\n" + (cp.stderr or "")).splitlines() if x.strip()]
    return _gizle(" | ".join(satirlar[-n:]))


def bekleyen_say(manifest_yolu: pathlib.Path) -> int:
    """Onaylı (geçerli) ve henüz yüklenmemiş öğe sayısı."""
    m = ks.yukle(manifest_yolu)
    return sum(1 for o in m["ogeler"].values() if ks.onay_gecerli(o) and not ks.yayinda_gecerli(o))


class Yayinla:
    """Tek seferde TEK yayınlama işi. `manifest_yolu()` güncel klipler.json yolunu verir."""

    def __init__(self, manifest_yolu: Callable[[], pathlib.Path], depo: pathlib.Path | None = None):
        self.manifest_yolu = manifest_yolu
        self.depo = pathlib.Path(depo) if depo else KOK
        self.kilit = threading.Lock()
        self.durum: dict | None = None

    def mesgul(self) -> bool:
        with self.kilit:
            return bool(self.durum and self.durum["durum"] == "calisiyor")

    def baslat(self) -> dict:
        try:
            n = bekleyen_say(self.manifest_yolu())
        except (OSError, ValueError, KeyError) as e:
            raise Hata(f"Klip listesi okunamadı: {e}") from e
        with self.kilit:
            if self.durum and self.durum["durum"] == "calisiyor":
                raise Hata("Yayınlama zaten sürüyor; bitmesini bekle.")
            if n == 0:
                raise Hata("Yüklenecek onaylı klip yok. Önce Klipler sekmesinde beğendiklerini onayla.")
            self.durum = {"durum": "calisiyor", "adim": "Başlıyor", "mesaj": "", "satirlar": [], "baslangic": time.monotonic(),
                          "bitis": None, "klip": n}
        threading.Thread(target=self._calis, name="klip-yayinla", daemon=True).start()
        return {"ok": True, "mesaj": f"{n} onaylı klip yayınlanıyor (yükleme, kayıt, GitHub'a gönderme)."}

    # ---- iç
    def _adim(self, adim: str, satir: str | None = None) -> None:
        with self.kilit:
            self.durum["adim"] = adim
            if satir:
                self.durum["satirlar"] = (self.durum["satirlar"] + [satir])[-SON_SATIR_SAYISI:]

    def _bitir(self, durum: str, mesaj: str) -> None:
        with self.kilit:
            self.durum.update(durum=durum, mesaj=mesaj, bitis=time.monotonic(),
                              adim={"bitti": "Bitti", "hata": "Durdu"}[durum])

    def _git(self, *arg: str, zaman_asimi: float = GIT_ZAMAN_ASIMI) -> subprocess.CompletedProcess:
        return _kos(["git", *arg], zaman_asimi, self.depo)

    def _calis(self) -> None:
        try:
            self._calis_ic()
        except Hata as e:
            self._bitir("hata", str(e))
        except subprocess.TimeoutExpired as e:
            self._bitir("hata", f"Zaman aşımı: {' '.join(map(str, e.cmd[:3]))} çok uzun sürdü, durduruldu.")
        except Exception as e:  # noqa: BLE001 — iş parçacığı sessiz ölmesin
            self._bitir("hata", f"Beklenmeyen hata: {type(e).__name__}: {_gizle(str(e))[:200]}")

    def _calis_ic(self) -> None:
        yol = pathlib.Path(self.manifest_yolu())
        # 1) yükleme
        self._adim("Klipler sunucuya yükleniyor")
        komut = list(YUKLE_KOMUTU) if YUKLE_KOMUTU else [sys.executable, str(KOK / "tools" / "klip_yayin.py")]
        cp = _kos([*komut, "--manifest", str(yol), "yukle"], YUKLE_ZAMAN_ASIMI, self.depo)
        cikti = [" ".join(x.split()) for x in (cp.stdout or "").splitlines() if x.strip()]
        for s in cikti[-SON_SATIR_SAYISI:]:
            self._adim("Klipler sunucuya yükleniyor", _gizle(s))
        yuklenen = sum(1 for s in cikti if "yüklendi, yayında" in s)
        if cp.returncode != 0:
            sorun = [s for s in cikti if s.startswith(("HATA", "ATLANDI", "ONAY DÜŞTÜ"))] or cikti[-2:] or [(cp.stderr or "").strip()[:200]]
            raise Hata(f"Yükleme tamamlanamadı ({yuklenen} klip yüklendi): {_gizle(' | '.join(sorun)[:400])} "
                       "Commit ve push yapılmadı; sorunu giderip düğmeye yeniden bas (yüklenenler tekrar yüklenmez).")
        # 2) commit
        self._adim("Değişiklik kaydediliyor (commit)")
        r = self._git("add", "--", str(yol))
        if r.returncode != 0:
            raise Hata(f"git add başarısız: {_son_satirlar(r)}")
        degisti = self._git("diff", "--cached", "--quiet", "--", str(yol)).returncode != 0
        if degisti:
            r = self._git("commit", "-m", f"klipler: {max(yuklenen, 1)} klip yayında", "--", str(yol))
            if r.returncode != 0:
                raise Hata(f"git commit başarısız: {_son_satirlar(r)}")
            self._adim("Değişiklik kaydedildi (commit)", "commit atıldı")
        else:
            self._adim("Değişiklik yok", "klipler.json'da yeni değişiklik yok; yalnız gönderilmemiş commit varsa gönderilir")
        # 3) pull --rebase (çalışma klasöründeki ilgisiz değişiklikler için autostash)
        self._adim("Sunucudaki değişiklikler çekiliyor (pull --rebase)")
        r = self._git("pull", "--rebase", "--autostash")
        if r.returncode != 0:
            ayrinti = _son_satirlar(r)
            self._git("rebase", "--abort")          # yarım rebase bırakma; commit yerelde kalır
            raise Hata(f"git pull --rebase başarısız (çakışma olabilir), rebase iptal edildi, commit yerelde duruyor: {ayrinti}")
        # 4) push
        self._adim("GitHub'a gönderiliyor (push)")
        r = self._git("push")
        if r.returncode != 0:
            raise Hata(f"git push başarısız: {_son_satirlar(r)}")
        self._bitir("bitti", f"Bitti: {yuklenen} klip yüklendi, kayıt commit edildi ve GitHub'a gönderildi."
                    if degisti else "Bitti: yeni yüklenecek klip kalmadı; bekleyen commit gönderildi.")

    def goster(self) -> dict:
        try:
            bekleyen = bekleyen_say(self.manifest_yolu())
        except (OSError, ValueError, KeyError):
            bekleyen = None
        with self.kilit:
            d = self.durum
            if d is not None and d["bitis"] is not None and time.monotonic() - d["bitis"] > BITTI_SURESI:
                self.durum = d = None
            if d is None:
                return {"durum": "yok", "bekleyen": bekleyen}
            gecen = int((d["bitis"] or time.monotonic()) - d["baslangic"])
            return {"durum": d["durum"], "adim": d["adim"], "mesaj": d["mesaj"], "satirlar": list(d["satirlar"]),
                    "gecen_sn": gecen, "bekleyen": bekleyen}
