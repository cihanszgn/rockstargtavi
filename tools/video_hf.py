"""Hyperframes video motoru: haber başına tema, ses seçimi, veri dosyası, çizim ve güvenli alan denetimi.

Tek yönlü bağımlılık: video_uret bu modülü içe alır (tersi yok). Bu yüzden burada senaryo/zamanlama kodu yok;
video_uret `props` (zamanli.json ile aynı yapı) verir, burada Hyperframes proje klasörü kurulur ve çizilir.

Tema üç katmandır (video-hf/oyun_temalari.json ve temalar.css):
  1. palet: oyun görselinin baskın rengi + haber türünün vurgu rengi, kontrast denetimli;
  2. paket: esports / gazete / neon / kolaj (yazı tipi çifti, doku, geçiş, süs); haber türü + oyun türü ipucu +
     kimlikten türeyen sabit sayı ile seçilir, art arda iki haber aynı paketi almaz;
  3. oyuna özel dokunuş: tablodaki oyunlar için palet + tek süs (telifli logo/karakter yok).
"""
from __future__ import annotations

import colorsys
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HF = ROOT / "video-hf"
OYUN_TEMALARI = HF / "oyun_temalari.json"
GORSELLER = ROOT / "data" / "gorseller.json"
OYUN_GORSELLERI = ROOT / "data" / "oyun_gorselleri.json"
OYUNLAR = ROOT / "data" / "oyunlar.json"
GUVENLI_BETIK = HF / "araclar" / "guvenli_alan.mjs"
KAPAK_FONT_BASLIK = ROOT / "otomasyon" / "fontlar" / "Anton-Regular.ttf"
KAPAK_FONT_ETIKET = ROOT / "tools" / "yazi" / "Archivo-ExpandedExtraBold.ttf"
KAPAK_FONT_CJK = ROOT / "tools" / "yazi" / "NotoSansSC-Bold.otf"
HF_SURUMU = "0.9.56"
PAKETLER = ("esports", "gazete", "neon", "kolaj")
TURLER = ("haber", "guncelleme", "indirim", "ucretsiz", "cikis")
BOYUT_SINIRI = 24_000_000  # 1080p mp4 en çok bu kadar bayt (hedef: 25 MB altı)

# Güvenli alan (px): okunur yazı üstten 220, alttan 420 (y ≤ 1500); alt yarıda sağdan 150 boş (x ≤ 930).
GUVENLI = {"ust": 220, "alt": 1500, "sol": 40, "sag": 1040, "sag_alt": 930, "alt_yari": 960, "doluluk_min": 0.7, "baslik_min": 96}

# Haber türünün vurgu rengi: ücretsiz/indirim fiyat etiketi yeşil-sarı, çıkış kutlama altını, güncelleme teknik camgöbeği,
# haber gazete kırmızısı. Hue, görselden renk alınamazsa da türe göre sabit bir taban verir.
TUR_VURGU = {"ucretsiz": "#c6f432", "indirim": "#ffe14a", "cikis": "#ffc233", "guncelleme": "#19e3ff",
             "haber": "#e63946"}
TUR_TABAN_HUE = {"ucretsiz": 150, "indirim": 30, "cikis": 330, "guncelleme": 215, "haber": 355}


class TemaHatasi(RuntimeError):
    pass


# ---------------------------------------------------------------- renk yardımcıları

def _rgb(hexs: str) -> tuple[float, float, float]:
    h = hexs.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def _hex(r: float, g: float, b: float) -> str:
    return "#{:02x}{:02x}{:02x}".format(*(max(0, min(255, round(v * 255))) for v in (r, g, b)))


def hsl_hex(h: float, s: float, l: float) -> str:
    r, g, b = colorsys.hls_to_rgb((h % 360) / 360, max(0.0, min(1.0, l)), max(0.0, min(1.0, s)))
    return _hex(r, g, b)


def hex_hsl(hexs: str) -> tuple[float, float, float]:
    r, g, b = _rgb(hexs)
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return h * 360, s, l


def parlaklik(hexs: str) -> float:
    def kanal(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (kanal(c) for c in _rgb(hexs))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def kontrast_orani(a: str, b: str) -> float:
    la, lb = parlaklik(a), parlaklik(b)
    ust, alt = max(la, lb), min(la, lb)
    return (ust + 0.05) / (alt + 0.05)


def okunur_yazi(zemin: str) -> str:
    """Zeminin üstüne konacak yazı rengi: beyaz ya da koyu, hangisi daha çok kontrast veriyorsa (her zeminde ≥ 4,5)."""
    return "#ffffff" if kontrast_orani("#ffffff", zemin) >= kontrast_orani("#0d0d0d", zemin) else "#0d0d0d"


def _ayarla(hexs: str, karsi: str, hedef: float, yon: str) -> str:
    """Rengin açıklığını `yon` (acik | koyu) tarafına, `karsi` renkle oran `hedef`e ulaşana dek kaydırır."""
    h, s, l = hex_hsl(hexs)
    adim = 0.02 if yon == "acik" else -0.02
    for _ in range(50):
        if kontrast_orani(hsl_hex(h, s, l), karsi) >= hedef:
            break
        l += adim
        if not 0.0 < l < 1.0:
            break
    return hsl_hex(h, s, max(0.0, min(1.0, l)))


# ---------------------------------------------------------------- görsel paleti

def gorsel_paleti(yol: Path) -> dict | None:
    """Oyun görselinin baskın rengi (doygun ve ne çok koyu ne çok açık, en çok yer kaplayan) ve ikinci rengi.
    Renksiz (gri) görselde None döner; tema o zaman türün taban rengine düşer."""
    try:
        from PIL import Image
    except ImportError:  # Pillow yoksa tema türden gelir
        return None
    try:
        im = Image.open(yol).convert("RGB")
        im.thumbnail((96, 96))
        q = im.quantize(colors=8, method=Image.Quantize.MEDIANCUT)
        pal = q.getpalette() or []
        sayilar = sorted(q.getcolors() or [], reverse=True)
        toplam = sum(n for n, _ in sayilar) or 1
        adaylar = []
        for n, i in sayilar:
            r, g, b = pal[i * 3:i * 3 + 3]
            h, s, l = hex_hsl(_hex(r / 255, g / 255, b / 255))
            if s < 0.28 or not 0.14 < l < 0.86:
                continue
            adaylar.append((n / toplam * (s ** 1.3) * (1 - abs(l - 0.5) * 1.1), h, s))
        adaylar.sort(reverse=True)
        if not adaylar:
            return None
        _, h1, s1 = adaylar[0]
        h2 = next((h for _, h, _ in adaylar[1:] if min(abs(h - h1), 360 - abs(h - h1)) >= 35), None)
        return {"h": round(h1, 1), "s": round(s1, 3), "h2": None if h2 is None else round(h2, 1)}
    except Exception:  # bozuk/okunamayan görsel temayı durdurmaz
        return None


# ---------------------------------------------------------------- tema

def tablo_oku(yol: Path | None = None) -> dict:
    return json.loads(Path(yol or OYUN_TEMALARI).read_text(encoding="utf-8"))


def _sayi(*parcalar: str) -> int:
    return int.from_bytes(hashlib.sha256("|".join(parcalar).encode("utf-8")).digest()[:8], "big")


def _tur(haber: dict) -> str:
    return haber.get("tur") if haber.get("tur") in TURLER else "haber"


def paket_puanlari(haber: dict, tablo: dict) -> dict:
    """Paket başına puan: haber türü + oyun türü ipucu + kimlikten türeyen küçük sabit sayı (aynı haber her dilde
    aynı puanı alır; farklı haberler aynı türde bile değişir)."""
    p = {k: 0.0 for k in PAKETLER}
    pt = tablo["paket_puani"]
    for k, v in (pt["tur"].get(_tur(haber)) or {}).items():
        if k in p:
            p[k] += v
    metin = f"{haber.get('oyun', '')} {haber.get('id', '')}".lower()
    for ip in tablo.get("tur_ipuclari", []):
        if any(a in metin for a in ip["anahtar"]):
            for k, v in (pt["ipucu"].get(ip["tur"]) or {}).items():
                if k in p:
                    p[k] += v
            break
    for k in PAKETLER:
        p[k] += 3.4 * (_sayi(str(haber.get("id", "")), k) % 1000) / 1000
    return p


def paket_sec(haber: dict, onceki: str | None = None, tablo: dict | None = None) -> str:
    tablo = tablo or tablo_oku()
    sirali = sorted(PAKETLER, key=lambda k: (-paket_puanlari(haber, tablo)[k], k))
    return sirali[1] if sirali[0] == onceki else sirali[0]


def paket_zinciri(icerik: list[dict], tablo: dict | None = None) -> dict:
    """Haberleri (tarih, kimlik) sırasıyla dolaşıp her habere paket verir; bir önceki haberin paketi aynı gelirse
    ikinci en iyi paket alınır: art arda iki haber hiçbir zaman aynı görünmez. Yeni haber listenin sonuna eklendiği
    için eski haberlerin paketi değişmez."""
    tablo = tablo or tablo_oku()
    sonuc, onceki = {}, None
    for h in sorted(icerik, key=lambda x: (x.get("tarih", ""), x.get("id", ""))):
        onceki = sonuc[h["id"]] = paket_sec(h, onceki, tablo)
    return sonuc


def oyun_dokunusu(haber: dict, tablo: dict) -> tuple[str | None, dict | None]:
    metin = f"{haber.get('oyun', '')} {haber.get('id', '')}".lower()
    for o in tablo.get("oyunlar", []):
        eslesen = next((a for a in o["anahtar"] if a in metin), None)
        if eslesen:
            return eslesen, o
    return None, None


def palet_kur(paket: str, tur: str, h: float, s: float, h2: float | None, oyun_palet: dict | None = None) -> dict:
    """Paletin bütün değerleri (tema CSS değişkenleri). h/s: ana renk tonu/doygunluğu; h2: ikinci ton."""
    s = max(0.6, min(0.92, s))
    h2 = (h + 150) % 360 if h2 is None else h2
    vurgu = TUR_VURGU.get(tur, TUR_VURGU["haber"])
    ana_l = {"esports": 0.5, "neon": 0.58, "kolaj": 0.52, "gazete": 0.45}[paket]
    bg_l, bg2_l = {"esports": (0.075, 0.16), "neon": (0.05, 0.13), "kolaj": (0.1, 0.2), "gazete": (0.08, 0.16)}[paket]
    p = {"bg": hsl_hex(h, 0.55, bg_l), "bg2": hsl_hex(h, 0.6, bg2_l), "ana": hsl_hex(h, s, ana_l),
         "ana2": hsl_hex(h2, 0.75, 0.52), "ana-acik": hsl_hex(h, 0.95, 0.72), "ana-koyu": hsl_hex(h, 0.6, 0.3 if paket == "kolaj" else 0.16),
         "vurgu": vurgu, "yazi": "#ffffff", "kagit": "#f1ebdd", "murekkep": "#14110e", "vurgu-kagit": ""}
    if oyun_palet:
        for k in ("ana", "ana2", "vurgu", "bg"):
            if oyun_palet.get(k):
                p[k] = oyun_palet[k]
        if oyun_palet.get("bg"):
            bh, bs, bl = hex_hsl(oyun_palet["bg"])
            p["bg2"] = hsl_hex(bh, bs, min(0.3, bl + 0.08))
        ah, as_, al = hex_hsl(p["ana"])
        p["ana-acik"] = hsl_hex(ah, 0.95, 0.72)
        p["ana-koyu"] = hsl_hex(ah, min(0.7, as_), 0.3 if paket == "kolaj" else 0.16)
    vh, vs, vl = hex_hsl(p["vurgu"])
    p["vurgu-kagit"] = hsl_hex(vh, min(0.85, max(0.6, vs)), 0.36)
    return kontrast_duzelt(p)


def kontrast_duzelt(p: dict) -> dict:
    """Okunurluk için renkleri kaydırır: koyu zeminler beyaz yazıyla ≥ 7, açık tonlar zeminle ≥ 4,5, kâğıt/mürekkep
    ve kâğıt/vurgu çiftleri okunur; `*-yazi` renkleri zemine göre beyaz ya da koyu seçilir."""
    q = dict(p)
    for k in ("bg", "bg2", "ana-koyu"):
        q[k] = _ayarla(q[k], q["yazi"], 7.0, "koyu")
    q["ana-acik"] = _ayarla(q["ana-acik"], q["bg"], 4.5, "acik")
    q["vurgu"] = _ayarla(q["vurgu"], q["bg"], 3.0, "acik")
    q["ana"] = _ayarla(q["ana"], q["bg"], 2.5, "acik")
    q["vurgu-kagit"] = _ayarla(q["vurgu-kagit"], q["kagit"], 4.5, "koyu")
    for zemin, yazi in (("ana", "ana-yazi"), ("ana2", "ana2-yazi"), ("vurgu", "vurgu-yazi")):
        q[yazi] = okunur_yazi(q[zemin])
        if kontrast_orani(q[yazi], q[zemin]) < 4.5:  # orta tonda ne beyaz ne koyu yazı yetiyor: zemini koyulaştır
            q[zemin] = _ayarla(q[zemin], "#ffffff", 4.5, "koyu")
            q[yazi] = okunur_yazi(q[zemin])
    return q


def tema_hatalari(p: dict) -> list[str]:
    """Okunurluk denetimi: (yazı, zemin, en az oran). Boş liste = tema okunur."""
    cift = [("yazi", "bg", 7.0), ("yazi", "bg2", 7.0), ("yazi", "ana-koyu", 7.0), ("ana-acik", "bg", 4.5),
            ("vurgu", "bg", 3.0), ("ana-yazi", "ana", 4.5), ("ana2-yazi", "ana2", 4.5),
            ("vurgu-yazi", "vurgu", 4.5), ("murekkep", "kagit", 10.0), ("kagit", "vurgu-kagit", 4.5)]
    hatalar = []
    for yazi, zemin, en_az in cift:
        if yazi not in p or zemin not in p:
            hatalar.append(f"{yazi}/{zemin}: palette yok")
            continue
        oran = kontrast_orani(p[yazi], p[zemin])
        if oran < en_az:
            hatalar.append(f"{yazi} {p[yazi]} / {zemin} {p[zemin]}: kontrast {oran:.2f} < {en_az}")
    return hatalar


def tema_girdisi(haber: dict, senaryo: dict | None = None, icerik: list[dict] | None = None,
                 zorla_paket: str | None = None, tablo: dict | None = None) -> dict:
    """Anahtara girecek tema girdileri: ağ ve görsel indirme gerektirmez, bu yüzden bekleyenler hesabında da kullanılır.
    Görselin kendisi değil adresi anahtardadır (görsel değişirse video yenilenir)."""
    tablo = tablo or tablo_oku()
    ozel = (senaryo or {}).get("tema") or {}
    if zorla_paket and zorla_paket not in PAKETLER:
        raise TemaHatasi(f"bilinmeyen tema paketi: {zorla_paket!r} ({', '.join(PAKETLER)})")
    if ozel.get("paket") and ozel["paket"] not in PAKETLER:
        raise TemaHatasi(f"senaryo.tema.paket şunlardan biri olmalı: {', '.join(PAKETLER)}")
    zincir = paket_zinciri(icerik, tablo) if icerik else {}
    paket = zorla_paket or ozel.get("paket") or zincir.get(haber.get("id")) or paket_sec(haber, None, tablo)
    anahtar, oyun = oyun_dokunusu(haber, tablo)
    return {"motor": "hyperframes", "paket": paket, "oyun": anahtar, "oyun_ogesi": (oyun or {}).get("oge"),
            "oyun_palet": (oyun or {}).get("palet"), "ozel_palet": ozel.get("palet") or None,
            "ozel_oge": ozel.get("oge") or None, "gorsel": gorsel_adresi(haber.get("id", ""), haber=haber)}


def anahtar_eki(girdi: dict) -> dict:
    """video_uret.anahtar() içine eklenen tema bölümü (üretimde bu girdilerden bir şey değişirse video yenilenir)."""
    ek = {k: girdi[k] for k in ("motor", "paket", "oyun", "ozel_palet", "ozel_oge", "gorsel")}
    if not girdi.get("gorsel"):
        # Görselsiz açılışın çizimi değişince artır: yalnız görselsiz videolar yeniden üretilir.
        # 2 (2026-11-18): dev oyun adı soluk arka plan oldu; eskiden başlıkla üst üste biniyordu.
        ek["gorselsiz_surum"] = 2
    return ek


def tema_sec(haber: dict, girdi: dict, foto: Path | None = None) -> dict:
    """Son tema: girdilerden + görselin rengi. {paket, palet, oge, oyun, renk}."""
    tur = _tur(haber)
    gp = gorsel_paleti(foto) if foto else None
    if gp:
        h, s, h2, renk = gp["h"], gp["s"], gp["h2"], "gorsel"
    else:
        h, s, h2, renk = TUR_TABAN_HUE[tur] + (_sayi(str(haber.get("id", ""))) % 40) - 20, 0.8, None, "tur"
    oyun_palet = girdi.get("oyun_palet")
    if oyun_palet:
        renk = "oyun"
        if oyun_palet.get("ana"):
            h = hex_hsl(oyun_palet["ana"])[0]
    palet = palet_kur(girdi["paket"], tur, h, s, h2, oyun_palet)
    if girdi.get("ozel_palet"):
        palet = kontrast_duzelt({**palet, **{k: v for k, v in girdi["ozel_palet"].items() if k in palet}})
    hatalar = tema_hatalari(palet)
    if hatalar:
        raise TemaHatasi("tema kontrast denetimi: " + "; ".join(hatalar))
    oge = girdi.get("ozel_oge") or ([girdi["oyun_ogesi"]] if girdi.get("oyun_ogesi") else [])
    return {"paket": girdi["paket"], "palet": palet, "oge": list(oge), "oyun": girdi.get("oyun"), "renk": renk}


# ---------------------------------------------------------------- ses

def ses_sec(liste: list[str], haber_id: str, edge: bool = False) -> str:
    """Dilin üç sesinden biri, haber kimliğinden türeyen sabit sayıyla (aynı haber aynı sesi her çalışmada alır;
    listeler [erkek, KADIN, erkek] sıralıdır, bu yüzden aynı haber her dilde aynı sırayı alır).
    edge=True: Edge'de olmayan MAI sesi ("Ad:MAI-...") atlanır (yerel önizleme için)."""
    adaylar = [v for v in liste if not (edge and ":" in v)] or list(liste)
    if not adaylar:
        return ""
    return adaylar[_sayi(haber_id, "ses") % len(adaylar)]


# ---------------------------------------------------------------- görsel

_OYUN_TAKMA = {
    "gta-vi": "gta-6", "gta6": "gta-6", "gta-v": "grand-theft-auto-v", "gta5": "grand-theft-auto-v",
    "cs2": "counter-strike-2", "ffxiv": "final-fantasy-xiv", "ff14": "final-fantasy-xiv",
    "r6": "tom-clancys-rainbow-six-siege", "r6-siege": "tom-clancys-rainbow-six-siege",
    "rainbow-six-siege": "tom-clancys-rainbow-six-siege", "bf6": "battlefield-6",
}
_STEAM_APP_RE = re.compile(r"https://(?:shared\.[a-z0-9.-]*steamstatic\.com/store_item_assets|cdn\.[a-z0-9.-]*steamstatic\.com|steamcdn-a\.akamaihd\.net)/steam/apps/(\d+)/")


def _oyun_slug(ad: str) -> str:
    s = str(ad or "").lower().translate(str.maketrans("çğıöşü", "cgiosu"))
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    if s.startswith("grand-theft-auto-"):
        s = "gta-" + s[len("grand-theft-auto-"):]
    return s


def _oyun_eslesme(oyunlar_yol: Path | None = None) -> dict[str, str]:
    esles = dict(_OYUN_TAKMA)
    yol = Path(oyunlar_yol or OYUNLAR)
    try:
        liste = json.loads(yol.read_text(encoding="utf-8")) or []
    except (OSError, ValueError):
        return esles
    for o in liste:
        if not isinstance(o, dict) or not o.get("id"):
            continue
        oid = str(o["id"])
        for a in (oid, o.get("ad"), o.get("kisa"), *(o.get("eslesme") or [])):
            k = _oyun_slug(str(a or ""))
            if k:
                esles[k] = oid
    return esles


def _oyun_gorsel_adresi(haber: dict | None, oyun_yol: Path | None = None,
                        oyunlar_yol: Path | None = None) -> str | None:
    if not isinstance(haber, dict):
        return None
    ad = str(haber.get("oyun") or "").strip()
    if not ad:
        return None
    yol = Path(oyun_yol or OYUN_GORSELLERI)
    try:
        veri = json.loads(yol.read_text(encoding="utf-8")) or {}
    except (OSError, ValueError):
        return None
    s = _oyun_slug(ad)
    esles = _oyun_eslesme(oyunlar_yol)
    adaylar = []
    for k in (s, esles.get(s, "")):
        if k and k not in adaylar:
            adaylar.append(k)
    for k in adaylar:
        for bolum in ("oyun", "takvim"):
            kayit = (veri.get(bolum) or {}).get(k) or {}
            url = kayit.get("url")
            if isinstance(url, str) and url.startswith("https://"):
                return url
    return None


def gorsel_adresi(haber_id: str, yol: Path | None = None, haber: dict | None = None,
                  oyun_yol: Path | None = None) -> str | None:
    """Önce habere özel görseli (data/gorseller.json), yoksa ilgili oyunun resmî kapak/tanıtım görselini
    (data/oyun_gorselleri.json) döndürür."""
    yol = Path(yol or GORSELLER)
    try:
        k = (json.loads(yol.read_text(encoding="utf-8")) or {}).get(haber_id) or {}
    except (OSError, ValueError):
        k = {}
    url = k.get("url")
    if isinstance(url, str) and url.startswith("https://"):
        return url
    return _oyun_gorsel_adresi(haber, oyun_yol)


def _gorsel_indir(url: str, onbellek: Path, *, en_az_boyut: tuple[int, int] | None = None,
                  dikey_sart: bool = False) -> Path | None:
    from PIL import Image, ImageStat
    onbellek.mkdir(parents=True, exist_ok=True)
    anahtar = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
    onb = onbellek / f"{anahtar}.jpg"
    yok = onbellek / f"{anahtar}.yok"
    if onb.exists():
        if dikey_sart or en_az_boyut:
            try:
                with Image.open(onb) as cim:
                    if max(ImageStat.Stat(cim.convert("RGB")).stddev) < 12.0:
                        onb.unlink(missing_ok=True)
                        yok.write_text("blank", encoding="utf-8")
                        return None
            except Exception:
                pass
        return onb
    if yok.exists():
        return None
    gecici = onb.with_suffix(".indir")
    try:
        istek = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; video-uretici)"})
        with urllib.request.urlopen(istek, timeout=30) as r:
            ham = r.read(20_000_000)
        gecici.write_bytes(ham)
        im = Image.open(gecici).convert("RGB")
        if dikey_sart and im.height <= im.width:
            yok.write_text("not-portrait", encoding="utf-8")
            return None
        if en_az_boyut and (im.width < en_az_boyut[0] or im.height < en_az_boyut[1]):
            yok.write_text("too-small", encoding="utf-8")
            return None
        if (dikey_sart or en_az_boyut) and max(ImageStat.Stat(im).stddev) < 12.0:
            yok.write_text("blank", encoding="utf-8")
            return None
        if im.width > 1600:
            im = im.resize((1600, round(im.height * 1600 / im.width)), Image.LANCZOS)
        im.save(onb, quality=90)
        return onb
    except Exception:
        if dikey_sart or en_az_boyut:
            try:
                yok.write_text("err", encoding="utf-8")
            except OSError:
                pass
        return None
    finally:
        gecici.unlink(missing_ok=True)


def foto_hazirla(haber_id: str, onbellek: Path, hedef: Path, cikti=print, yol: Path | None = None,
                 haber: dict | None = None, oyun_yol: Path | None = None,
                 dikey_tercih: bool = False) -> Path | None:
    """Haberin ya da ilgili oyunun resmî görselini indirir (önbellekli), JPEG olarak hedefe yazar.
    dikey_tercih=True (kapak için): Steam oyun görselinde önce yüksek çözünürlüklü 600×900 dikey kutu kapağını,
    yoksa geniş hero görselini dener; olmazsa özgün URL'ye düşer."""
    url = gorsel_adresi(haber_id, yol, haber=haber, oyun_yol=oyun_yol)
    if not url:
        return None
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        cikti("uyarı: Pillow yok, görsel kullanılmadı")
        return None
    onb = None
    if dikey_tercih:
        m = _STEAM_APP_RE.match(url)
        if m:
            appid = m.group(1)
            onb = _gorsel_indir(
                f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{appid}/library_600x900_2x.jpg",
                onbellek, en_az_boyut=(400, 600), dikey_sart=True)
            if onb is None and "/header.jpg" in url:
                onb = _gorsel_indir(
                    f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{appid}/library_hero.jpg",
                    onbellek, en_az_boyut=(1000, 400))
    if onb is None:
        onb = _gorsel_indir(url, onbellek)
    if onb is None:
        cikti("uyarı: görsel alınamadı; başlık görselsiz çizilecek")
        return None
    hedef.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(onb, hedef)
    return hedef


# ---------------------------------------------------------------- Reels / Shorts kapak afişi

def _kapak_buyuk(metin: str, dil: str) -> str:
    s = str(metin or "").strip()
    if dil == "zh":
        return s
    if dil == "tr":
        return s.replace("i", "İ").replace("ı", "I").upper()
    return s.upper()


def _kapak_norm(kelime: str, dil: str) -> str:
    s = _kapak_buyuk(kelime, dil)
    return re.sub(r"[^\w\u00c0-\u024f\u4e00-\u9fff]+", "", s)


def _kapak_font(yollar: tuple[Path, ...], boyut: int):
    from PIL import ImageFont
    for y in yollar:
        if y.exists():
            return ImageFont.truetype(str(y), boyut)
    return ImageFont.load_default()


def _hex_rgba(hexs: str, alfa: int = 255) -> tuple[int, int, int, int]:
    r, g, b = (round(c * 255) for c in _rgb(hexs))
    return (r, g, b, max(0, min(255, alfa)))


def _dikey_gradyan(w: int, h: int, duraklar: list[tuple[float, tuple[int, int, int, int]]]):
    """Hızlı dikey RGBA gradyanı: 1×h şeritten w×h'ye ölçekler."""
    from PIL import Image
    serit = Image.new("RGBA", (1, h))
    px = serit.load()
    for y in range(h):
        t = y / max(1, h - 1)
        a, b = duraklar[0], duraklar[-1]
        for i in range(len(duraklar) - 1):
            if duraklar[i][0] <= t <= duraklar[i + 1][0]:
                a, b = duraklar[i], duraklar[i + 1]
                break
        f = 0.0 if b[0] == a[0] else (t - a[0]) / (b[0] - a[0])
        px[0, y] = tuple(round(a[1][c] + (b[1][c] - a[1][c]) * f) for c in range(4))
    return serit.resize((w, h), Image.BILINEAR)


def _kapak_satirla(metin: str, font, azami_w: int, dil: str) -> list[list[str]]:
    """Metni azami_w genişliğe sığacak satırlara böler (CJK karakter, diğer diller kelime tabanlı)."""
    cjk = dil == "zh" or bool(re.search(r"[\u4e00-\u9fff]", metin))
    parcalar = list(metin) if cjk else metin.split()
    if not parcalar:
        return []
    ayrac = "" if cjk else " "
    satirlar: list[list[str]] = []
    cur: list[str] = []
    for p in parcalar:
        deneme = ayrac.join([*cur, p])
        if cur and font.getlength(deneme) > azami_w:
            satirlar.append(cur)
            cur = [p]
        else:
            cur.append(p)
    if cur:
        satirlar.append(cur)
    return satirlar


def _kapak_cover_kirp(im, w: int, h: int, ust_pay: float = 0.35):
    from PIL import Image
    oran = max(w / im.width, h / im.height)
    nw, nh = max(w, round(im.width * oran)), max(h, round(im.height * oran))
    im = im.resize((nw, nh), Image.LANCZOS)
    x0 = (nw - w) // 2
    y0 = round((nh - h) * ust_pay)
    return im.crop((x0, y0, x0 + w, y0 + h))


def _kapak_kenar_yumusat(im, ust_px: int, alt_px: int):
    """Yatay hero görselinin üst ve alt kenarlarını yumuşak alpha maskesiyle arka plana eritir."""
    from PIL import Image
    w, h = im.size
    serit = Image.new("L", (1, h), 255)
    px = serit.load()
    for y in range(min(ust_px, h)):
        px[0, y] = round(255 * ((y / max(1, ust_px)) ** 1.35))
    for y in range(max(0, h - alt_px), h):
        kalan = h - 1 - y
        px[0, y] = round(255 * ((kalan / max(1, alt_px)) ** 1.45))
    maske = serit.resize((w, h), Image.BILINEAR)
    out = im.convert("RGBA")
    out.putalpha(maske)
    return out


def kapak_ciz(hedef: Path, *, foto: Path | None, baslik: str, vurgu: list[str] | None = None,
              tur_etiket: str = "", oyun: str = "", palet: dict | None = None, dil: str = "tr") -> Path:
    """Reels & Shorts için 1080×1920 oyun odaklı dikkat çekici kapak afişi üretir.
    Oyun görseli üst bölgede temiz ve engelsiz durur; kategori rozeti, oyun adı ve kısa vurucu başlık
    platform güvenli alanında (y ≈ 1000–1520) yüksek kontrastla yer alır. Altyazı / tuş / tarih kalabalığı yok."""
    from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

    W, H = 1080, 1920
    p = palet or {"bg": "#0b0914", "bg2": "#1c1330", "ana": "#ff2a85", "ana2": "#19e3ff", "vurgu": "#ffc233"}
    bg_hex = _ayarla(p.get("bg") or "#0b0914", "#ffffff", 11.0, "koyu")
    bg2_hex = _ayarla(p.get("bg2") or p.get("ana") or "#1c1330", "#ffffff", 5.5, "koyu")
    ana_hex = p.get("ana") or "#ff2a85"
    vurgu_hex = _ayarla(p.get("vurgu") or "#ffc233", bg_hex, 6.2, "acik")
    rozet_yazi = okunur_yazi(vurgu_hex)
    bg_rgb = _hex_rgba(bg_hex)[:3]

    tuval = Image.new("RGBA", (W, H), (*bg_rgb, 255))
    im = None
    if foto and Path(foto).exists():
        try:
            im = Image.open(foto).convert("RGB")
        except Exception:
            im = None

    if im is not None:
        if im.height > im.width:
            # Dikey resmi oyun kapağı (örn. Steam 600×900): üst yarı tamamen temiz, alt yarıda yumuşak karartma.
            hero = _kapak_cover_kirp(im, W, H, ust_pay=0.22)
            hero = ImageEnhance.Color(hero).enhance(1.12)
            hero = ImageEnhance.Contrast(hero).enhance(1.06)
            hero = ImageEnhance.Sharpness(hero).enhance(1.08)
            tuval.paste(hero.convert("RGBA"), (0, 0))
            perde = _dikey_gradyan(W, H, [
                (0.00, (*bg_rgb, 40)),
                (0.14, (*bg_rgb, 0)),
                (0.46, (*bg_rgb, 0)),
                (0.58, (*bg_rgb, 155)),
                (0.70, (*bg_rgb, 232)),
                (0.84, (*bg_rgb, 248)),
                (1.00, (*bg_rgb, 255)),
            ])
            tuval.alpha_composite(perde)
        else:
            # Yatay / kare resmi oyun görseli (örn. GTA VI 1200×630, R6 1920×1080):
            # Tam ekran renk atmosferli bulanık arka plan + üst-ortada keskin, yumuşak kenarlı hero vitrin.
            arka = _kapak_cover_kirp(im, W, H, ust_pay=0.45)
            arka = ImageEnhance.Color(arka).enhance(1.30)
            arka = arka.filter(ImageFilter.GaussianBlur(radius=42))
            arka = ImageEnhance.Brightness(arka).enhance(0.42)
            tuval.paste(arka.convert("RGBA"), (0, 0))

            oran = im.width / max(1, im.height)
            # Geniş görsellerde karakter/logo kesilmesin diye dengeli kırpma (~780–940 px yükseklik)
            vitrin_h = 840 if oran >= 1.55 else 940
            vitrin_y = 120 if oran >= 1.55 else 80
            hero = _kapak_cover_kirp(im, W, vitrin_h, ust_pay=0.38)
            hero = ImageEnhance.Color(hero).enhance(1.13)
            hero = ImageEnhance.Contrast(hero).enhance(1.07)
            hero = ImageEnhance.Sharpness(hero).enhance(1.10)
            hero_rgba = _kapak_kenar_yumusat(hero, ust_px=95, alt_px=155)
            tuval.alpha_composite(hero_rgba, (0, vitrin_y))

            perde = _dikey_gradyan(W, H, [
                (0.00, (*bg_rgb, 120)),
                (0.10, (*bg_rgb, 0)),
                (0.44, (*bg_rgb, 0)),
                (0.54, (*bg_rgb, 170)),
                (0.66, (*bg_rgb, 235)),
                (0.84, (*bg_rgb, 248)),
                (1.00, (*bg_rgb, 255)),
            ])
            tuval.alpha_composite(perde)
    else:
        # Görselsiz oyunlar için koyu atmosfer + renkli radyal parlama + büyük soluk oyun adı dokusu
        zemin = _dikey_gradyan(W, H, [
            (0.00, _hex_rgba(bg2_hex, 255)),
            (0.45, (*bg_rgb, 255)),
            (1.00, (*bg_rgb, 255)),
        ])
        tuval.alpha_composite(zemin)
        parla = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        pd = ImageDraw.Draw(parla)
        pd.ellipse((-120, -60, 920, 980), fill=_hex_rgba(ana_hex, 125))
        pd.ellipse((320, 260, 1260, 1200), fill=_hex_rgba(p.get("ana2") or vurgu_hex, 85))
        tuval.alpha_composite(parla.filter(ImageFilter.GaussianBlur(radius=140)))
        if oyun:
            f_arka = _kapak_font((KAPAK_FONT_BASLIK, KAPAK_FONT_ETIKET), 170)
            katman = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            kd = ImageDraw.Draw(katman)
            oyun_u = _kapak_buyuk(oyun, dil)
            sat = _kapak_satirla(oyun_u, f_arka, W - 96, dil)[:2]
            yy = 280
            for s in sat:
                kd.text((64, yy), " ".join(s), font=f_arka, fill=(255, 255, 255, 26))
                yy += 168
            tuval.alpha_composite(katman)

    # Başlık metni hazırlığı (kısa, vurucu, 2-3 satır, güvenli alan içinde)
    cjk = dil == "zh" or bool(re.search(r"[\u4e00-\u9fff]", baslik or ""))
    baslik_fontlar = (KAPAK_FONT_CJK,) if cjk else (KAPAK_FONT_BASLIK, KAPAK_FONT_ETIKET)
    etiket_fontlar = (KAPAK_FONT_CJK,) if cjk else (KAPAK_FONT_ETIKET, KAPAK_FONT_BASLIK)
    baslik_u = _kapak_buyuk(baslik or oyun or "CTRL+A GAME", dil)
    sol, sag = 64, 64
    azami_w = W - sol - sag

    vurgu_parcalar = []
    for v_oge in (vurgu or []):
        if isinstance(v_oge, dict):
            m = v_oge.get("metin") or v_oge.get("yazi") or ""
        else:
            m = str(v_oge or "")
        if m:
            vurgu_parcalar.append(str(m))
    vurgu_set = set()
    for m in vurgu_parcalar:
        for k in m.split():
            nk = _kapak_norm(k, dil)
            if nk:
                vurgu_set.add(nk)

    sec_font, sec_satir, sec_boyut = None, [], 92
    for boyut in (122, 114, 106, 98, 90, 82, 74):
        f = _kapak_font(baslik_fontlar, boyut)
        sat = _kapak_satirla(baslik_u, f, azami_w, dil)
        if len(sat) <= 3:
            sec_font, sec_satir, sec_boyut = f, sat, boyut
            break
    if sec_font is None:
        sec_boyut = 70
        sec_font = _kapak_font(baslik_fontlar, sec_boyut)
        sec_satir = _kapak_satirla(baslik_u, sec_font, azami_w, dil)[:3]

    satir_h = round(sec_boyut * (1.22 if cjk else 1.24))
    baslik_h = len(sec_satir) * satir_h
    # Başlığı Instagram 3:4 grid (y=240..1680) ve Reels/Shorts güvenli alan (y<=1500) içine oturt
    baslik_y = max(1040, min(1140, 1465 - baslik_h))

    # Üst meta satırı: [KATEGORİ ROZETİ] + OYUN ADI (üst görseli hiç kapatmaz!)
    meta_y = baslik_y - 78
    ciz = ImageDraw.Draw(tuval)
    cur_x = sol
    if tur_etiket:
        f_rozet = _kapak_font(etiket_fontlar, 27)
        et_u = _kapak_buyuk(tur_etiket, dil)
        bb = f_rozet.getbbox(et_u)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        pw, ph = tw + 36, 48
        ciz.rounded_rectangle((cur_x, meta_y, cur_x + pw, meta_y + ph), radius=12, fill=_hex_rgba(vurgu_hex, 255))
        ciz.text((cur_x + 18 - bb[0], meta_y + (ph - th) // 2 - bb[1] - 1), et_u,
                 font=f_rozet, fill=_hex_rgba(rozet_yazi, 255))
        cur_x += pw + 20
    else:
        ciz.rounded_rectangle((cur_x, meta_y + 20, cur_x + 56, meta_y + 28), radius=4, fill=_hex_rgba(vurgu_hex, 255))
        cur_x += 72

    if oyun:
        f_oyun = _kapak_font(etiket_fontlar, 26)
        # Oyun adları çoğunlukla İngilizce özel addır (COUNTER-STRIKE 2, RAINBOW SIX SIEGE);
        # yalnızca Türkçe harf içeriyorsa Türkçe büyük harf uygulanır.
        oyun_dil = dil if any(c in oyun.lower() for c in "çğıöşü") else "en"
        oyun_u = _kapak_buyuk(oyun, oyun_dil)
        kalan_w = W - sag - cur_x
        while oyun_u and f_oyun.getlength(oyun_u) > kalan_w and len(oyun_u) > 6:
            oyun_u = oyun_u[:-2].rstrip() + "…"
        if oyun_u and kalan_w > 120:
            bb = f_oyun.getbbox(oyun_u)
            th = bb[3] - bb[1]
            oy_y = meta_y + (48 - th) // 2 - bb[1]
            ciz.text((cur_x + 2, oy_y + 2), oyun_u, font=f_oyun, fill=(0, 0, 0, 190))
            ciz.text((cur_x, oy_y), oyun_u, font=f_oyun, fill=(245, 245, 250, 235))

    # Gölge katmanı + net ana başlık (vurgulu kelimeler canlı vurgu renginde)
    golge = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(golge)
    ayrac = "" if cjk else " "
    ayrac_w = 0.0 if cjk else sec_font.getlength(" ")
    vurgu_str = _kapak_buyuk(" ".join(vurgu_parcalar), dil)

    yy = baslik_y
    for satir in sec_satir:
        satir_metin = ayrac.join(satir)
        gd.text((sol, yy + 8), satir_metin, font=sec_font, fill=(0, 0, 0, 225), stroke_width=8, stroke_fill=(0, 0, 0, 225))
        yy += satir_h
    tuval.alpha_composite(golge.filter(ImageFilter.GaussianBlur(radius=10)))

    ciz = ImageDraw.Draw(tuval)
    yy = baslik_y
    for satir in sec_satir:
        xx = float(sol)
        for parca in satir:
            vurgulu = (parca in vurgu_str) if cjk else (_kapak_norm(parca, dil) in vurgu_set)
            renk = _hex_rgba(vurgu_hex, 255) if vurgulu else (255, 255, 255, 255)
            ciz.text((round(xx), yy), parca, font=sec_font, fill=renk, stroke_width=4, stroke_fill=(8, 8, 12, 235))
            xx += sec_font.getlength(parca) + ayrac_w
        yy += satir_h

    # Alt marka imzası (sade, başlık alt uzantılarının altında temiz boşlukla)
    imza_y = yy + 44
    if imza_y <= 1590:
        f_marka = _kapak_font((KAPAK_FONT_ETIKET, KAPAK_FONT_BASLIK), 22)
        ciz.ellipse((sol, imza_y + 7, sol + 12, imza_y + 19), fill=_hex_rgba(vurgu_hex, 245))
        ciz.text((sol + 22, imza_y), "CTRL+A GAME", font=f_marka, fill=(235, 235, 242, 185))

    hedef = Path(hedef)
    hedef.parent.mkdir(parents=True, exist_ok=True)
    tuval.convert("RGB").save(hedef, format="JPEG", quality=92, optimize=True, progressive=True)
    return hedef


# ---------------------------------------------------------------- proje klasörü

STATIK = ("fontlar.css", "taban.css", "temalar.css", "motor.js", "hyperframes.json", "meta.json")


def palet_css(palet: dict) -> str:
    return ";".join(f"--{k}:{v}" for k, v in palet.items())


def sahne_html(sahneler: list[dict]) -> str:
    return "\n".join(f'<section class="clip sc" id="s{i}" data-start="{s["bas"]}" '
                     f'data-duration="{round(s["bit"] - s["bas"], 3)}" data-track-index="1"></section>'
                     for i, s in enumerate(sahneler))


def veri_olustur(props: dict, tema: dict, foto: str | None) -> dict:
    """window.VIDEO: motor.js'in okuduğu her şey (metin, sayı, süre, görsel yolu, tema) senaryo verisinden gelir."""
    return {"sure": props["sure"], "dil": props["dil"], "tema": {"paket": tema["paket"], "oge": tema["oge"]},
            "haber": props["haber"], "foto": foto,
            "sahneler": [{"sablon": s["sablon"], "bas": s["bas"], "bit": s["bit"], "veri": s["veri"]}
                         for s in props["sahneler"]],
            "kelimeler": props["kelimeler"], "parcalar": props["parcalar"]}


def klasor_kur(klasor: Path, props: dict, tema: dict, ses: Path, foto: Path | None) -> Path:
    """Çizilecek Hyperframes projesi: şablon + sabit dosyalar + yazı tipleri + üretilen veri, ses ve görsel."""
    if klasor.exists():
        shutil.rmtree(klasor)
    (klasor / "assets" / "ses").mkdir(parents=True)
    for ad in STATIK:
        shutil.copyfile(HF / ad, klasor / ad)
    shutil.copytree(HF / "assets" / "fonts", klasor / "assets" / "fonts")
    shutil.copytree(HF / "vendor", klasor / "vendor")
    shutil.copyfile(ses, klasor / "assets" / "ses" / "ses.mp3")
    foto_yolu = None
    if foto:
        (klasor / "assets" / "img").mkdir()
        shutil.copyfile(foto, klasor / "assets" / "img" / "foto.jpg")
        foto_yolu = "assets/img/foto.jpg"
    veri = veri_olustur(props, tema, foto_yolu)
    (klasor / "assets" / "data.js").write_text("window.VIDEO = " + json.dumps(veri, ensure_ascii=False) + ";\n",
                                               encoding="utf-8")
    sablon = (HF / "index.html").read_text(encoding="utf-8")
    html = (sablon.replace("__DIL__", props["dil"]).replace("__PALET__", palet_css(tema["palet"]))
            .replace("__PAKET__", tema["paket"]).replace("__SURE__", str(props["sure"]))
            .replace("__SAHNELER__", sahne_html(props["sahneler"])))
    if "__" in re.sub(r"__[a-z_]+__", "", html) and re.search(r"__[A-Z]+__", html):
        raise TemaHatasi("şablonda doldurulmamış yer tutucu kaldı")
    (klasor / "index.html").write_text(html, encoding="utf-8")
    return klasor


# ---------------------------------------------------------------- araç yolları, çizim

def ffmpeg_dizini() -> str | None:
    """ffmpeg'in bulunduğu klasör (PATH'te ya da WinGet kurulumunda)."""
    y = shutil.which("ffmpeg")
    if y:
        return str(Path(y).parent)
    yerel = os.environ.get("LOCALAPPDATA")
    if yerel:
        for p in sorted((Path(yerel) / "Microsoft" / "WinGet" / "Packages").glob("Gyan.FFmpeg*/*/bin"), reverse=True):
            if (p / "ffmpeg.exe").exists():
                return str(p)
    return None


def hf_ortami() -> dict:
    env = dict(os.environ)
    env["HYPERFRAMES_NO_TELEMETRY"] = "1"
    env["DO_NOT_TRACK"] = "1"
    d = ffmpeg_dizini()
    if d:
        env["PATH"] = d + os.pathsep + env.get("PATH", "")
    return env


def hf_komutu() -> list[str]:
    y = shutil.which("hyperframes")
    if y:
        return [y]
    raise TemaHatasi(f"hyperframes bulunamadı: npm i -g hyperframes@{HF_SURUMU}")


def _kos(komut: list[str], kos, **kw) -> subprocess.CompletedProcess:
    r = kos(komut, capture_output=True, text=True, encoding="utf-8", errors="replace", env=hf_ortami(), **kw)
    return r


def tarayici_yolu(kos=subprocess.run) -> str:
    r = _kos(hf_komutu() + ["browser", "path"], kos, timeout=120)
    yol = (r.stdout or "").strip().splitlines()[-1:] or [""]
    if r.returncode != 0 or not yol[0] or not Path(yol[0]).exists():
        raise TemaHatasi(f"Chrome bulunamadı (hyperframes browser ensure): {(r.stderr or r.stdout or '').strip()[-300:]}")
    return yol[0]


def hf_koku(kos=subprocess.run) -> str:
    """Global hyperframes paketinin klasörü (içindeki puppeteer-core güvenli alan denetiminde kullanılır)."""
    npm = shutil.which("npm")
    if not npm:
        raise TemaHatasi("npm bulunamadı")
    r = _kos([npm, "root", "-g"], kos, timeout=60)
    kok = Path((r.stdout or "").strip()) / "hyperframes"
    if r.returncode != 0 or not (kok / "package.json").exists():
        raise TemaHatasi("global hyperframes paketi bulunamadı")
    return str(kok)


def _doluluk_ozeti(sonuc: dict) -> dict:
    """Sahne türü başına ölçülen en düşük doluluk oranı."""
    ozet: dict = {}
    for d in sonuc.get("doluluk", []):
        ozet[d["sablon"]] = min(d["oran"], ozet.get(d["sablon"], 9.0))
    return ozet


def guvenli_denetle(klasor: Path, props: dict, rapor: Path, cikti=print, kos=subprocess.run) -> dict:
    """Her sahnenin her yerleşmiş metni güvenli alanın içinde mi: üstten 220, alttan 420 (y ≤ 1500), alt yarıda
    sağdan 150 boş; ayrıca sığdırma taşması, doluluk (ön plan öğelerinin birleşik kutusu güvenli alan yüksekliğinin
    en az %70'i) ve açılış başlığı yazı boyutu alt sınırı (96 px). Bir ihlal üretimi durdurur (video çizilmez)."""
    node = shutil.which("node")
    if not node:
        raise TemaHatasi("node bulunamadı")
    komut = [node, str(GUVENLI_BETIK), "--klasor", str(klasor), "--rapor", str(rapor), "--chrome", tarayici_yolu(kos),
             "--hf", hf_koku(kos), "--sahneler", json.dumps([[s["bas"], s["bit"], s["sablon"]] for s in props["sahneler"]]),
             "--sure", str(props["sure"]), "--sinir", json.dumps(GUVENLI)]
    r = _kos(komut, kos, timeout=600)
    if r.returncode not in (0, 3) or not Path(rapor).exists():
        raise TemaHatasi(f"güvenli alan denetimi çalışmadı: {(r.stderr or r.stdout or '').strip()[-800:]}")
    sonuc = json.loads(Path(rapor).read_text(encoding="utf-8"))
    if sonuc["ihlal_sayisi"]:
        ilk = "; ".join(f"{i['metin']!r} {i['yon']} {i['an']} sn, {i['deger']} px" for i in sonuc["ihlaller"][:5])
        raise TemaHatasi(f"güvenli alan denetimi: {sonuc['ihlal_sayisi']} ihlal ({ilk}); rapor: {rapor}")
    cikti(f"güvenli alan denetimi: {sonuc['olcum_sayisi']} ölçüm, {sonuc['metin_sayisi']} metin, ihlal yok")
    for sablon, oran in sorted(_doluluk_ozeti(sonuc).items()):
        cikti(f"  doluluk {sablon}: en düşük %{round(oran * 100)}")
    return sonuc


def render(klasor: Path, cikti_mp4: Path, kos=subprocess.run, fps: int = 30) -> None:
    """Hyperframes ile çizim (yalnız yerel `render` komutu; publish/share/cloud/auth kullanılmaz)."""
    komut = hf_komutu() + ["render", str(klasor), "-o", str(cikti_mp4), "-f", str(fps), "--quiet", "--no-wait"]
    r = _kos(komut, kos, timeout=3600)
    if r.returncode != 0 or not Path(cikti_mp4).exists():
        raise TemaHatasi(f"hyperframes render başarısız: {(r.stderr or r.stdout or '').strip()[-1500:]}")


def ffmpeg_calistir(*arg: str, kos=subprocess.run) -> None:
    d = ffmpeg_dizini()
    ff = str(Path(d) / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")) if d else "ffmpeg"
    r = kos([ff, "-hide_banner", "-loglevel", "error", "-y", *arg], capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=1800)
    if r.returncode != 0:
        raise TemaHatasi(f"ffmpeg başarısız: {(r.stderr or r.stdout or '').strip()[-800:]}")


def sikistir(ham: Path, hedef: Path, sinir: int = BOYUT_SINIRI, kos=subprocess.run) -> int:
    """Ham çizimden 1080p mp4: libx264 slow, CRF yükselerek dosya `sinir` baytın altına inene dek. Dönen: son CRF."""
    for crf in (21, 24, 27, 30, 33):
        ffmpeg_calistir("-i", str(ham), "-c:v", "libx264", "-preset", "slow", "-crf", str(crf), "-maxrate", "3600k",
                        "-bufsize", "7200k", "-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709",
                        "-color_trc", "bt709", "-color_range", "tv", "-c:a", "aac", "-b:a", "96k",
                        "-movflags", "+faststart", str(hedef), kos=kos)
        if Path(hedef).stat().st_size <= sinir:
            return crf
    raise TemaHatasi(f"1080p video {sinir} bayta sığdırılamadı")


def kapak_cikar(video: Path, an: float, hedef: Path, kos=subprocess.run) -> None:
    ffmpeg_calistir("-ss", f"{an:.3f}", "-i", str(video), "-frames:v", "1", "-q:v", "2", str(hedef), kos=kos)


def baslat_zamani() -> float:
    return time.monotonic()


if __name__ == "__main__":  # küçük elle denetim: py tools/video_hf.py <haber id>
    if len(sys.argv) > 1:
        ic = json.loads((ROOT / "data" / "icerik.json").read_text(encoding="utf-8"))
        h = next(x for x in ic if x["id"] == sys.argv[1])
        g = tema_girdisi(h, None, ic)
        print(json.dumps(g, ensure_ascii=False, indent=1))
