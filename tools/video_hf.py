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
GUVENLI_BETIK = HF / "araclar" / "guvenli_alan.mjs"
HF_SURUMU = "0.9.56"
PAKETLER = ("esports", "gazete", "neon", "kolaj")
TURLER = ("haber", "guncelleme", "indirim", "ucretsiz", "cikis")
BOYUT_SINIRI = 24_000_000  # 1080p mp4 en çok bu kadar bayt (hedef: 25 MB altı)

# Güvenli alan (px): okunur yazı üstten 220, alttan 420 (y ≤ 1500); alt yarıda sağdan 150 boş (x ≤ 930).
GUVENLI = {"ust": 220, "alt": 1500, "sol": 40, "sag": 1040, "sag_alt": 930, "alt_yari": 960}

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
            "ozel_oge": ozel.get("oge") or None, "gorsel": gorsel_adresi(haber.get("id", ""))}


def anahtar_eki(girdi: dict) -> dict:
    """video_uret.anahtar() içine eklenen tema bölümü (üretimde bu girdilerden bir şey değişirse video yenilenir)."""
    return {k: girdi[k] for k in ("motor", "paket", "oyun", "ozel_palet", "ozel_oge", "gorsel")}


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

def gorsel_adresi(haber_id: str, yol: Path | None = None) -> str | None:
    yol = Path(yol or GORSELLER)
    try:
        k = (json.loads(yol.read_text(encoding="utf-8")) or {}).get(haber_id) or {}
    except (OSError, ValueError):
        return None
    url = k.get("url")
    return url if isinstance(url, str) and url.startswith("https://") else None


def foto_hazirla(haber_id: str, onbellek: Path, hedef: Path, cikti=print, yol: Path | None = None) -> Path | None:
    """Haberin resmî görselini indirir (önbellekli), 1600 px genişliğe indirip hedefe JPEG yazar. Alınamazsa None:
    başlık sahnesi görselsiz (oyun adı büyük yazı) çalışır."""
    url = gorsel_adresi(haber_id, yol)
    if not url:
        return None
    try:
        from PIL import Image
    except ImportError:
        cikti("uyarı: Pillow yok, görsel kullanılmadı")
        return None
    onbellek.mkdir(parents=True, exist_ok=True)
    onb = onbellek / (hashlib.sha256(url.encode("utf-8")).hexdigest()[:12] + ".jpg")
    if not onb.exists():
        try:
            istek = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; video-uretici)"})
            with urllib.request.urlopen(istek, timeout=30) as r:
                ham = r.read(20_000_000)
            gecici = onb.with_suffix(".indir")
            gecici.write_bytes(ham)
            im = Image.open(gecici).convert("RGB")
            if im.width > 1600:
                im = im.resize((1600, round(im.height * 1600 / im.width)), Image.LANCZOS)
            im.save(onb, quality=88)
            gecici.unlink(missing_ok=True)
        except Exception as e:  # ağ/format hatası videoyu durdurmaz
            cikti(f"uyarı: görsel alınamadı ({type(e).__name__}); başlık görselsiz çizilecek")
            return None
    hedef.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(onb, hedef)
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


def guvenli_denetle(klasor: Path, props: dict, rapor: Path, cikti=print, kos=subprocess.run) -> dict:
    """Her sahnenin her yerleşmiş metni güvenli alanın içinde mi: üstten 220, alttan 420 (y ≤ 1500), alt yarıda
    sağdan 150 boş; ayrıca sığdırma taşması. Bir ihlal üretimi durdurur (video çizilmez)."""
    node = shutil.which("node")
    if not node:
        raise TemaHatasi("node bulunamadı")
    komut = [node, str(GUVENLI_BETIK), "--klasor", str(klasor), "--rapor", str(rapor), "--chrome", tarayici_yolu(kos),
             "--hf", hf_koku(kos), "--sahneler", json.dumps([[s["bas"], s["bit"]] for s in props["sahneler"]]),
             "--sure", str(props["sure"]), "--sinir", json.dumps(GUVENLI)]
    r = _kos(komut, kos, timeout=600)
    if r.returncode not in (0, 3) or not Path(rapor).exists():
        raise TemaHatasi(f"güvenli alan denetimi çalışmadı: {(r.stderr or r.stdout or '').strip()[-800:]}")
    sonuc = json.loads(Path(rapor).read_text(encoding="utf-8"))
    if sonuc["ihlal_sayisi"]:
        ilk = "; ".join(f"{i['metin']!r} {i['yon']} {i['an']} sn, {i['deger']} px" for i in sonuc["ihlaller"][:5])
        raise TemaHatasi(f"güvenli alan denetimi: {sonuc['ihlal_sayisi']} ihlal ({ilk}); rapor: {rapor}")
    cikti(f"güvenli alan denetimi: {sonuc['olcum_sayisi']} ölçüm, {sonuc['metin_sayisi']} metin, ihlal yok")
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
