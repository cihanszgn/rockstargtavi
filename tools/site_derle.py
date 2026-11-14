#!/usr/bin/env python3
"""CTRL+A GAME site derleyici (4 dil, düz statik HTML).

Üretir:  ana sayfa, oyun haberleri (liste + haber sayfaları + RSS), indirimler, ücretsiz oyunlar,
         söylentiler, çıkış takvimi, GTA VI dosyası, 404, arama dizini (ara-<dil>.json), sitemap.xml.
Elle yazılmış sayfaların (GTA rehberleri, hakkında, gizlilik) <main> içeriği korunur; yalnız ortak
kabuk (üst menü, alt bilgi, head etiketleri) yeniden basılır.

Kullanım:   python tools/sosyal_derle.py     (sitenin tamamı + paylaşım kartları; Pillow gerekir)
            python tools/site_derle.py       (yalnız HTML/JSON; Pillow gerekmez, GitHub Actions bunu çalıştırır)
Ortam:      SITE_BUGUN=2026-11-20          derleme gününü değiştirir (test için)
            SITE_DENEME_VERI=<klasör>       söylenti/takvim yalnız bu klasörden, indirim/ücretsiz varsa buradan okunur
Aynı gün aynı veriyle ikinci çalıştırma hiçbir dosyayı değiştirmez.
"""
from __future__ import annotations

import hashlib
import html
import json
import math
import os
import pathlib
import re
import sys
import unicodedata
from datetime import date, datetime, time, timedelta, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import site_oyun as so  # noqa: E402
import sosyal_derle as sd  # noqa: E402
from site_metin import (AY_KISA, DIL_AD, ESLER, GTA_ALT_SAYI, GTA_HEDEF, GTA_SAYFALAR, GTA_SERI,  # noqa: E402
                        GTA_TARIH, GTA_UST, MARKA, PLATFORMLAR, SAYFA, T, TEK_TR, say)

KOK, SITE, DILLER, M, e = sd.KOK, sd.SITE, sd.DILLER, sd.M, sd.e
TRT = timezone(timedelta(hours=3))
NBSP = " "
BOLUM_NO = {"ana": 0, "haber": 1, "oyunlar": 2, "indirim": 3, "ucretsiz": 4, "soylenti": 5, "takvim": 6, "rehberler": 7, "gta": 8}
NAV = ("haber", "oyunlar", "indirim", "ucretsiz", "soylenti", "takvim", "rehberler", "gta")
NAV_GRUP = ("indirim", "ucretsiz")  # üst menüde "Fırsatlar" altında
TEKIL = {"tr": ("gün", "saat", "dakika", "saniye"), "en": ("day", "hour", "minute", "second"),
         "fr": ("jour", "heure", "minute", "seconde"), "es": ("día", "hora", "minuto", "segundo")}
SEMBOL = {"USD": "$", "TRY": "₺", "EUR": "€", "GBP": "£"}
GUVEN = ("dusuk", "orta", "yuksek")
DURUM = ("dogrulanmadi", "dogrulandi", "yalanlandi")
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")

GA = ("<script async src=\"https://www.googletagmanager.com/gtag/js?id=G-67FMKX5E05\"></script>\n"
      "<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}"
      "gtag('js',new Date());gtag('config','G-67FMKX5E05');</script>\n")
TEMA_JS = ("<script>(function(d){d.className='js';try{var t=localStorage.getItem('cag-tema')}catch(e){}"
           "if(t!=='acik'&&t!=='koyu')t=matchMedia('(prefers-color-scheme: light)').matches?'acik':'koyu';"
           "d.setAttribute('data-tema',t)})(document.documentElement)</script>\n")

SVG = '<svg class="ikon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
IK_ARA = SVG + '<circle cx="10.5" cy="10.5" r="6.5" fill="none" stroke="currentColor" stroke-width="2"/><path d="m15.5 15.5 5 5" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>'
IK_TEMA = SVG + '<circle cx="12" cy="12" r="8" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 4a8 8 0 0 1 0 16z" fill="currentColor"/></svg>'
IK_DIL = SVG + '<circle cx="12" cy="12" r="8.5" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M3.5 12h17M12 3.5c2.6 2.4 3.6 5.3 3.6 8.5s-1 6.1-3.6 8.5c-2.6-2.4-3.6-5.3-3.6-8.5s1-6.1 3.6-8.5z" fill="none" stroke="currentColor" stroke-width="1.8"/></svg>'
IK = {
    "ana": SVG + '<path d="M4 11.5 12 5l8 6.5V20h-5.5v-5h-5v5H4z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg>',
    "haber": SVG + '<rect x="4" y="5" width="16" height="14" rx="2" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M8 9.5h8M8 13h8M8 16.5h5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
    "indirim": SVG + '<path d="M4 12.5V5h7.5l8.5 8.5-7.5 7.5z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/><circle cx="8.5" cy="9.5" r="1.6" fill="currentColor"/></svg>',
    "takvim": SVG + '<rect x="4" y="6" width="16" height="14" rx="2" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M4 10.5h16M9 3.5v4M15 3.5v4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
    "menu": SVG + '<path d="M4.5 7h15M4.5 12h15M4.5 17h15" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
    "oyunlar": SVG + '<path d="M7.5 8h9a4 4 0 0 1 3.9 4.9l-.9 3.6a2.2 2.2 0 0 1-3.8.9L14 15.5h-4l-1.7 1.9a2.2 2.2 0 0 1-3.8-.9l-.9-3.6A4 4 0 0 1 7.5 8z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/><path d="M8.5 10.5v3M7 12h3" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><circle cx="15.8" cy="11.2" r="1.1" fill="currentColor"/></svg>',
    "rehberler": SVG + '<path d="M12 6.5C10 5 7.5 4.5 4.5 5v13c3-.5 5.5 0 7.5 1.5 2-1.5 4.5-2 7.5-1.5V5c-3-.5-5.5 0-7.5 1.5zM12 6.5v13" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg>',
}

UYARILAR: list[str] = []
BUGUN = date.today()
SIMDI = datetime.now(TRT)
URETILEN: dict[str, dict] = {}
MANIFEST: dict[str, list] = {}
ESKI_HARITA: dict[str, str] = {}
SURUM: dict[str, str] = {}


def uyar(metin: str) -> None:
    UYARILAR.append(metin)


# ---------------------------------------------------------------- küçük yardımcılar
def u(yol: str) -> str:
    """Site içi bağlantı: index.html → klasör adresi."""
    if yol == "index.html":
        return "/"
    if yol.endswith("/index.html"):
        return "/" + yol[: -len("index.html")]
    return "/" + yol


def tam(yol: str) -> str:
    return SITE + u(yol)


def norm(s: str) -> str:
    s = str(s).lower().replace("ı", "i")
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def slug(s: str) -> str:
    return norm(s).replace(" ", "-")


def ham_anahtar(ad: str) -> str:
    s = slug(re.sub(r"\([^)]*\)", " ", str(ad)))
    if s.startswith("grand-theft-auto-"):
        s = "gta-" + s[len("grand-theft-auto-"):]
    return s


def oyun_anahtar(ad: str) -> str:
    """Takip ve süzgeç anahtarı: oyunlar.json'daki bir oyunun bütün adları tek anahtara iner."""
    return so.takip_anahtar(ad)


def gom(veri) -> str:
    """Sayfaya gömülecek JSON (</script> kaçışlı)."""
    return json.dumps(veri, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def zaman_al(s) -> datetime | None:
    try:
        z = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return z if z.tzinfo else z.replace(tzinfo=timezone.utc)


def iso_gun(s) -> bool:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(s or "")):
        return False
    try:
        date.fromisoformat(s)
    except ValueError:
        return False
    return True


def https(s) -> bool:
    return isinstance(s, str) and s.startswith("https://")


def tarih(dil: str, iso: str) -> str:
    return sd.tarih_yaz(dil, iso)


def zaman_etiketi(dil: str, iso: str) -> str:
    return f'<time datetime="{iso}">{tarih(dil, iso)}</time>'


def ay_baslik(dil: str, iso: str) -> str:
    y, a = int(iso[:4]), int(iso[5:7])
    ad = sd.AY[dil][a - 1]
    return f"{ad[:1].upper()}{ad[1:]} {y}"


def fiyat(dil: str, n: float, para: str = "USD") -> str:
    s = SEMBOL.get(para, para)
    tam_, kes = f"{float(n):.2f}".split(".")
    t = int(tam_)
    if dil == "en":
        return f"{s}{t:,}.{kes}"
    if dil == "tr":
        g = f"{t:,}".replace(",", ".")
    elif dil == "fr":
        g = f"{t:,}".replace(",", " ")
    else:
        g = f"{t:,}".replace(",", ".") if t >= 10000 else str(t)
    return f"{g},{kes}{NBSP}{s}"


def yuzde(dil: str, n: float) -> str:
    n = int(math.floor(float(n) + 0.5))
    if dil == "tr":
        return f"−%{n}"
    if dil == "en":
        return f"−{n}%"
    return f"−{n}{NBSP}%"


def birim(dil: str, n: int, i: int) -> str:
    return f"{n} {TEKIL[dil][i] if n == 1 else T[dil]['birim'][i]}"


def kalan_gun(dil: str, hedef: date) -> str:
    g = (hedef - BUGUN).days
    if g < 0:
        return T[dil]["cikti"]
    if g == 0:
        return T[dil]["bugun"]
    return birim(dil, g, 0)


def kalan_zaman(dil: str, hedef: datetime) -> str:
    sn = int((hedef - SIMDI).total_seconds())
    if sn <= 0:
        return T[dil]["gecti"]
    g, s = sn // 86400, (sn % 86400) // 3600
    if g >= 2:
        return birim(dil, g, 0)
    if g == 1:
        return f"{birim(dil, 1, 0)} {birim(dil, s, 1)}"
    return birim(dil, max(s, 1), 1)


def utc_yaz(dil: str, z: datetime) -> str:
    z = z.astimezone(timezone.utc)
    return f"{tarih(dil, z.date().isoformat())}, {z:%H:%M} UTC"


# ---------------------------------------------------------------- veri
def _json(ad: str, yalniz_deneme: bool):
    deneme = os.environ.get("SITE_DENEME_VERI")
    adaylar = [pathlib.Path(deneme) / ad] if deneme else []
    if not deneme or not yalniz_deneme:
        adaylar.append(KOK / "data" / ad)
    for y in adaylar:
        if y.exists():
            try:
                metin = y.read_text(encoding="utf-8").strip()
                return json.loads(metin) if metin else None
            except (OSError, ValueError) as h:
                uyar(f"{y.name} okunamadı ({h}); boş sayıldı.")
                return None
    return None


def _liste(v, *anahtarlar) -> list:
    if isinstance(v, list):
        return v
    if isinstance(v, dict):
        for k in anahtarlar:
            if isinstance(v.get(k), list):
                return v[k]
    return []


def soylentiler_yukle() -> list[dict]:
    sonuc, gorulen = [], set()
    for i, x in enumerate(_liste(_json("soylentiler.json", True), "soylentiler", "ogeler")):
        if not isinstance(x, dict):
            uyar(f"soylentiler.json #{i}: nesne değil; atlandı.")
            continue
        k, sorun = x.get("id"), []
        if not (isinstance(k, str) and SLUG.fullmatch(k)) or k in gorulen:
            sorun.append("id")
        if not iso_gun(x.get("tarih")):
            sorun.append("tarih")
        if not str(x.get("oyun") or "").strip():
            sorun.append("oyun")
        if x.get("guven") not in GUVEN:
            sorun.append("guven")
        if x.get("durum") not in DURUM:
            sorun.append("durum")
        ks = [s for s in x.get("kaynaklar") or [] if isinstance(s, dict) and https(s.get("url")) and s.get("ad")]
        if not ks:
            sorun.append("kaynaklar")
        dl = {d: t for d, t in (x.get("diller") or {}).items()
              if d in DILLER and isinstance(t, dict) and str(t.get("baslik") or "").strip() and str(t.get("ozet") or "").strip()}
        if not dl:
            sorun.append("diller")
        if sorun:
            uyar(f"soylentiler.json #{i} ({k}): {', '.join(sorun)} geçersiz; atlandı.")
            continue
        gorulen.add(k)
        pl = [str(p) for p in x.get("platform") or [] if str(p).strip()]
        sonuc.append({**x, "kaynaklar": ks, "diller": dl, "platform": pl})
    sonuc.sort(key=lambda x: (x["tarih"], x["id"]), reverse=True)
    return sonuc


def takvim_yukle() -> list[dict]:
    sonuc, gorulen = [], set()
    for i, x in enumerate(_liste(_json("takvim.json", True), "takvim", "oyunlar", "ogeler")):
        if not isinstance(x, dict):
            uyar(f"takvim.json #{i}: nesne değil; atlandı.")
            continue
        k, sorun = x.get("id"), []
        if not (isinstance(k, str) and SLUG.fullmatch(k)) or k in gorulen:
            sorun.append("id")
        if not str(x.get("oyun") or "").strip():
            sorun.append("oyun")
        if x.get("tarih") is not None and not iso_gun(x.get("tarih")):
            sorun.append("tarih")
        kay = x.get("kaynak")
        if not (isinstance(kay, dict) and https(kay.get("url")) and kay.get("ad")):
            sorun.append("kaynak")
        if sorun:
            uyar(f"takvim.json #{i} ({k}): {', '.join(sorun)} geçersiz; atlandı.")
            continue
        gorulen.add(k)
        pl = [str(p) for p in x.get("platform") or [] if str(p).strip()]
        sonuc.append({**x, "tarih": x.get("tarih") or None, "platform": pl,
                      "tur": x.get("tur") if isinstance(x.get("tur"), dict) else {},
                      "pencere": x.get("pencere") if isinstance(x.get("pencere"), dict) else {}})
    sonuc.sort(key=lambda x: (x["tarih"] is None, x["tarih"] or "", x["oyun"].lower()))
    return sonuc


def indirim_yukle() -> dict:
    v = _json("indirimler.json", False)
    v = v if isinstance(v, dict) else {}
    mag = [{"id": str(m["id"]), "ad": str(m["ad"]), "ikon": str(m.get("ikon") or "")}
           for m in v.get("magazalar") or [] if isinstance(m, dict) and m.get("id") and m.get("ad")]
    izin = {m["id"] for m in mag}
    fl = []
    for f in v.get("firsatlar") or []:
        try:
            if str(f["storeID"]) not in izin or not f.get("dealID") or not str(f.get("title") or "").strip():
                continue
            x = {"dealID": str(f["dealID"]), "gameID": str(f.get("gameID") or ""), "title": str(f["title"]).strip(),
                 "storeID": str(f["storeID"]), "salePrice": float(f["salePrice"]), "normalPrice": float(f["normalPrice"]),
                 "savings": float(f.get("savings") or 0), "thumb": str(f.get("thumb") or "")}
            if f.get("enDusuk") is not None:
                x["enDusuk"] = float(f["enDusuk"])
            fl.append(x)
        except (KeyError, TypeError, ValueError):
            continue
    return {"guncel": str(v.get("guncel") or ""), "magazalar": mag, "firsatlar": fl}


def ucretsiz_yukle() -> dict:
    v = _json("ucretsiz.json", False)
    v = v if isinstance(v, dict) else {}
    epic = []
    for x in v.get("epic") or []:
        if not isinstance(x, dict) or not str(x.get("baslik") or "").strip():
            continue
        bas, bit = zaman_al(x.get("baslangic")), zaman_al(x.get("bitis"))
        if not bas or not bit or bit <= SIMDI:
            continue
        durum = "simdi" if bas <= SIMDI else "yakinda"
        try:
            normal = float(x.get("normal") or 0)
        except (TypeError, ValueError):
            normal = 0.0
        epic.append({"baslik": str(x["baslik"]).strip(), "slug": str(x.get("slug") or ""), "resim": str(x.get("resim") or ""),
                     "baslangic": bas.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                     "bitis": bit.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                     "durum": durum, "normal": normal, "para": str(x.get("para") or "")})
    epic.sort(key=lambda x: (x["durum"] != "simdi", x["baslangic"], x["baslik"]))
    basliklar = {norm(x["baslik"]) for x in epic}
    cs = []
    for f in v.get("cheapshark") or []:
        try:
            if not f.get("dealID") or norm(f.get("title", "")) in basliklar:
                continue
            cs.append({"dealID": str(f["dealID"]), "gameID": str(f.get("gameID") or ""), "title": str(f["title"]).strip(),
                       "storeID": str(f["storeID"]), "salePrice": float(f["salePrice"]), "normalPrice": float(f["normalPrice"]),
                       "savings": float(f.get("savings") or 0), "thumb": str(f.get("thumb") or "")})
        except (KeyError, TypeError, ValueError):
            continue
    return {"guncel": str(v.get("guncel") or ""), "epic": epic, "cheapshark": cs}


# ---------------------------------------------------------------- eski (elle yazılmış) sayfalar
SONEK = re.compile(r"\s*\|\s*(?:GTA VI (?:Türkçe )?Rehber|GTA VI Guide|Guía de GTA VI|Guide GTA VI|CTRL\+A GAME)\s*$")


def eski_oku(yol: str) -> dict | None:
    p = KOK / yol
    if not p.exists():
        uyar(f"{yol} bulunamadı; atlandı.")
        return None
    t = p.read_text(encoding="utf-8")
    bas = t.split("</head>", 1)[0]
    m = re.search(r'<main id="main"[^>]*>(.*)</main>', t, re.S)
    b = re.search(r"<title>(.*?)</title>", bas, re.S)
    if not m or not b:
        uyar(f"{yol}: <title> veya <main id=\"main\"> yok; atlandı.")
        return None
    baslik = html.unescape(b.group(1).strip())
    while True:
        y = SONEK.sub("", baslik)
        if y == baslik:
            break
        baslik = y
    a = re.search(r'<meta name="description" content="([^"]*)"', bas)
    tip = re.search(r'<meta property="og:type" content="([^"]*)"', bas)
    return {"yol": yol, "baslik": baslik, "aciklama": html.unescape(a.group(1)) if a else "",
            "tip": tip.group(1) if tip else "website",
            "ld": "".join(s + "\n" for s in re.findall(r'<script type="application/ld\+json">.*?</script>', bas, re.S)),
            "main": m.group(1)}


def isaret(metin: str, ad: str, yeni: str) -> str:
    bas, son = f"<!-- {ad}:basla -->", f"<!-- {ad}:bitir -->"
    if bas not in metin:
        return metin
    return re.sub(re.escape(bas) + r".*?" + re.escape(son), lambda _: f"{bas}\n{yeni}{son}", metin, count=1, flags=re.S)


def gta_cikti() -> bool:
    return BUGUN >= date.fromisoformat(GTA_TARIH)


def geri_sayim(dil: str, kucuk: bool = False) -> str:
    t, g = T[dil], GTA_UST[dil]
    gun = max((date.fromisoformat(GTA_TARIH) - BUGUN).days, 0)
    b = t["birim"]
    ogeler = [("g", str(gun), b[0], ""), ("s", "00", b[1], " js-only"), ("d", "00", b[2], " js-only"), ("sn", "00", b[3], " js-only")]
    ic = "".join(f'<span class="gs-birim{c}"><b class="tus" data-b="{k}">{v}</b><span>{ad}</span></span>' for k, v, ad, c in ogeler)
    return (f'<div class="geri-sayim{" gs-kucuk" if kucuk else ""}" data-geri-sayim data-hedef="{GTA_HEDEF[dil]}" role="timer" '
            f'aria-label="{e(t["sayac_aria"])}" data-bitti="{e(g["cikti"] + " " + g["cikti_alt"])}">{ic}</div>')


def gta_ust(dil: str) -> str:
    g = GTA_UST[dil]
    if gta_cikti():
        return (f'<section class="gta-ust cikti-durum"><div class="wrap">\n<h1>{e(g["h1_cikti"])}</h1>\n'
                f'<p class="gta-giris">{g["p_cikti"]}</p>\n'
                f'<p class="cikti-blok"><span class="tus tus-genis">{e(g["cikti"])}</span> {e(g["cikti_alt"])}</p>\n</div></section>\n')
    return (f'<section class="gta-ust"><div class="wrap">\n'
            f'<h1 data-cikti-h1="{e(g["h1_cikti"])}">{e(g["h1"])}</h1>\n'
            f'<p class="gta-giris" data-cikti-p="{e(g["p_cikti"])}">{g["p"]}</p>\n'
            f'{geri_sayim(dil)}\n<p class="not gs-not">{e(g["not"])}</p>\n</div></section>\n')


def gta_haberleri(dil: str, adet: int = 5) -> str:
    yol = sd.GTA_HABER[dil]
    p = KOK / yol
    if not p.exists():
        return ""
    t = p.read_text(encoding="utf-8")
    m = re.search(r'<main id="main"[^>]*>(.*)</main>', t, re.S)
    ogeler = re.findall(r'<li id="([^"]+)"><time>(.*?)</time><strong>(.*?)</strong>(.*?)</li>', m.group(1) if m else "", re.S)
    satir = []
    for oid, zmn, baslik, govde in ogeler[:adet]:
        kay = re.search(r'<p class="src">.*?</p>', govde, re.S)
        # elle yazılmış listede "Kaynak <a" ve "Kaynak: <a" karışık; tek biçime getir
        kay_html = re.sub(r'^(<p class="src">)([^<:]+?)\s*(<a)', r'\1\2: \3', kay.group(0)) if kay else ""
        satir.append(f'<li class="satir"><p class="meta"><time>{zmn}</time></p><h3 class="satir-baslik"><a href="{u(yol)}#{oid}">{baslik}</a></h3>'
                     + kay_html + "</li>\n")
    if not satir:
        return ""
    t_ = T[dil]
    return (f'<section class="gta-haber"><div class="wrap">\n<h2>{e(t_["gta_son"])}</h2>\n<ul class="satirlar panel">\n'
            + "".join(satir) + f'</ul>\n<p class="devam"><a class="dugme" href="{u(yol)}">{e(t_["gta_tum"])}</a></p>\n</div></section>\n')


def gta_dizin(dil: str, yol: str) -> str:
    ogeler = "".join(f'<li><a href="{u(p)}"><b>{e(ad)}</b><span>{e(ac)}</span></a></li>\n'
                     for p, ad, ac in GTA_SAYFALAR[dil] if p != yol)
    return (f'<section class="gta-dizin"><div class="wrap">\n<h2>{e(T[dil]["gta_dizin"])}</h2>\n'
            f'<ul class="dizin">\n{ogeler}</ul>\n</div></section>\n')


# ---------------------------------------------------------------- kabuk
def js_metin(dil: str) -> dict:
    t = T[dil]
    anahtarlar = ("takip_et", "takipte", "takip_birak", "kopyalandi", "kapat", "kisayollar", "k_ara", "k_yardim", "k_bolum",
                  "k_tema", "k_kapat", "palet_yer", "palet_bos", "palet_hizli", "palet_ipucu", "tur_ara", "ara_aria", "birim",
                  "gecti", "bugun", "cikti", "canli", "hata_canli", "yukleniyor", "daha", "rozet_dusuk", "bos_filtre",
                  "bilgi_yok", "ics_bos", "son_haber", "cikis_tarihi", "simdi", "yakinda", "bitise", "baslangica", "bitis",
                  "baslangic", "menu", "nav_aria", "takip_baslik", "tema_aria", "radar")
    d = {k: t[k] for k in anahtarlar}
    d["tekil"] = TEKIL[dil]
    d["kaynak"] = M[dil]["kaynak"]
    d["ucretsiz"] = M[dil]["tur"]["ucretsiz"]
    d["bolumler"] = [[BOLUM_NO[b], t["nav"][b], u(SAYFA[b][dil])] for b in ("ana",) + NAV]
    return d


def dil_menusu(dil: str, hedefler: dict[str, str]) -> str:
    ogeler = "".join(
        f'<li><a href="{u(hedefler[d])}" hreflang="{d}" lang="{d}"{" aria-current=\"true\"" if d == dil else ""}>'
        f'<span class="dil-kod" aria-hidden="true">{d.upper()}</span>{DIL_AD[d]}</a></li>'
        for d in DILLER)
    return (f'<details class="dil"><summary>{IK_DIL}<span class="gizli">{e(T[dil]["dil_aria"])}: {DIL_AD[dil]}</span>'
            f'<span aria-hidden="true">{dil.upper()}</span></summary><ul class="dil-liste">{ogeler}</ul></details>')


def logo(dil: str) -> str:
    return (f'<a class="logo" href="{u(SAYFA["ana"][dil])}" aria-label="{MARKA}, {e(T[dil]["nav"]["ana"])}">'
            '<kbd class="tus">Ctrl</kbd><span class="logo-arti" aria-hidden="true">+</span><kbd class="tus">A</kbd>'
            '<span class="logo-ad">GAME</span></a>')


def kabuk(dil: str, yol: str, baslik: str, aciklama: str, govde: str, *, esler: dict | None = None, bolum: str | None = None,
          tip: str = "website", gorsel: str = "og.png", ek_bas: str = "", tam_baslik: bool = False, gta: bool = False,
          sayfa_turu: str = "", hedefler: dict | None = None, dizinle: bool = True, ana_sinif: str = "") -> str:
    t = T[dil]
    title = baslik if tam_baslik else f"{baslik} | {MARKA}"
    bas = [f'<!doctype html>\n<html lang="{dil}" class="no-js">\n<head>\n<meta charset="utf-8">\n'
           '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
           f"<title>{e(title)}</title>\n<meta name=\"description\" content=\"{e(aciklama)}\">\n"]
    if dizinle:
        bas.append(f'<link rel="canonical" href="{tam(yol)}">\n')
        if esler and len(esler) > 1:
            bas += [f'<link rel="alternate" hreflang="{d}" href="{tam(esler[d])}">\n' for d in DILLER if d in esler]
            bas.append(f'<link rel="alternate" hreflang="x-default" href="{tam(esler.get("en") or esler.get("tr") or esler[dil])}">\n')
    else:
        bas.append('<meta name="robots" content="noindex">\n')
    bas.append(
        f'<meta property="og:title" content="{e(baslik if tam_baslik else title)}">\n'
        f'<meta property="og:description" content="{e(aciklama)}">\n<meta property="og:type" content="{tip}">\n'
        f'<meta property="og:url" content="{tam(yol)}">\n<meta property="og:image" content="{SITE}/{gorsel}">\n'
        '<meta property="og:image:width" content="1200">\n<meta property="og:image:height" content="630">\n'
        f'<meta property="og:locale" content="{M[dil]["locale"]}">\n<meta property="og:site_name" content="{MARKA}">\n'
        f'<meta name="twitter:card" content="summary_large_image">\n<meta name="twitter:title" content="{e(title)}">\n'
        f'<meta name="twitter:description" content="{e(aciklama)}">\n<meta name="twitter:image" content="{SITE}/{gorsel}">\n'
        f'<link rel="alternate" type="application/rss+xml" title="{e(M[dil]["feed"])}" href="{SITE}/{sd.FEED[dil]}">\n')
    if gta:
        bas.append(f'<link rel="alternate" type="application/rss+xml" title="{e(t["rss_gta"])} | {MARKA}" href="{SITE}{gta_feed(dil)}">\n')
    bas.append(
        '<meta name="theme-color" content="#0B1322" media="(prefers-color-scheme: dark)">\n'
        '<meta name="theme-color" content="#EDF1F7" media="(prefers-color-scheme: light)">\n'
        '<meta name="color-scheme" content="dark light">\n'
        '<link rel="icon" href="/favicon.svg" type="image/svg+xml">\n'
        '<link rel="preload" href="/fonts/archivo.woff2" as="font" type="font/woff2" crossorigin>\n'
        f'<link rel="stylesheet" href="/style.css?v={SURUM["css"]}">\n' + TEMA_JS + GA + ek_bas +
        '<script src="/anma.js" defer></script>\n'
        f'<script src="/site.js?v={SURUM["js"]}" defer></script>\n</head>\n')

    if hedefler is None:
        hedefler = esler or {d: (yol if d == dil else (SAYFA["gta"][d] if gta else SAYFA["ana"][d])) for d in DILLER}
    hedefler = {d: hedefler.get(d) or SAYFA["ana"][d] for d in DILLER}
    nav, grup = [], []
    for b in NAV:
        hedef = SAYFA[b][dil]
        cur = ' aria-current="page"' if hedef == yol else (' aria-current="true"' if b == bolum else "")
        oge = f'<li><a href="{u(hedef)}"{cur}>{e(t["nav"][b])}</a></li>'
        if b in NAV_GRUP:
            grup.append(oge)
            if len(grup) == len(NAV_GRUP):
                acik = ' aria-current="true"' if bolum in NAV_GRUP else ""
                nav.append(f'<li class="nav-grup-li"><details class="nav-grup"><summary{acik}>{e(t["nav_firsat"])}</summary>'
                           f'<ul>{"".join(grup)}</ul></details></li>')
        else:
            nav.append(oge)
    ust = (f'<body data-dil="{dil}" data-sayfa="{sayfa_turu or bolum or "sayfa"}" data-ara="/ara-{dil}.json?v={SURUM["ara-" + dil]}">\n'
           f'<a class="atla" href="#main">{e(t["atla"])}</a>\n'
           f'<header class="ust"><div class="ust-ic">\n{logo(dil)}\n'
           f'<nav class="ana-nav" aria-label="{e(t["nav_aria"])}"><ul>{"".join(nav)}</ul></nav>\n'
           '<div class="ust-arac">'
           f'<button type="button" class="arac-dugme ara-dugme js-only" data-ara-ac aria-keyshortcuts="Control+K /">{IK_ARA}'
           f'<span class="ara-yazi">{e(t["ara"])}</span><span class="kisa" aria-hidden="true"><kbd class="tus" data-mod>Ctrl</kbd><kbd class="tus">K</kbd></span>'
           f'<span class="gizli">{e(t["ara_aria"])}</span></button>'
           f'<button type="button" class="arac-dugme js-only" data-tema-dugme title="{e(t["tema_aria"])}">{IK_TEMA}'
           f'<span class="gizli">{e(t["tema_aria"])}</span></button>'
           f'{dil_menusu(dil, hedefler)}</div>\n</div></header>\n')
    if gta:
        alt_sayfalar = GTA_SAYFALAR[dil][:GTA_ALT_SAYI]
        isaretli = "oyunlar.html" if yol in GTA_SERI else yol
        sekme = "".join(f'<li><a href="{u(p)}"{" aria-current=\"page\"" if p == isaretli else ""}>{e(ad)}</a></li>'
                        for p, ad, _ in alt_sayfalar)
        ust += f'<nav class="dosya-nav" aria-label="{e(t["dosya_aria"])}"><div class="wrap"><ul>{sekme}</ul></div></nav>\n'

    sinif = " ".join(s for s in ("metin-sayfa" if sayfa_turu == "eski" else "", ana_sinif) if s)
    sinif = f' class="{sinif}"' if sinif else ""
    ana = f'<main id="main" tabindex="-1"{sinif}>\n{govde}</main>\n'

    bolumler = "".join(f'<li><a href="{u(SAYFA[b][dil])}">{e(t["nav"][b])}</a></li>' for b in ("ana",) + NAV)
    gta_l = "".join(f'<li><a href="{u(p)}">{e(ad)}</a></li>' for p, ad, _ in GTA_SAYFALAR[dil])
    site_l = (f'<li><a href="{u(SAYFA["hakkinda"][dil])}">{e(t["hakkinda"])}</a></li>'
              f'<li><a href="{u(SAYFA["gizlilik"][dil])}">{e(t["gizlilik"])}</a></li>'
              + "".join(f'<li><a href="{u(SAYFA["ana"][d])}" hreflang="{d}" lang="{d}">{DIL_AD[d]}</a></li>' for d in DILLER if d != dil))
    rss_l = (f'<li><a href="/{sd.FEED[dil]}">{e(t["rss_haber"])}</a></li>'
             f'<li><a href="{gta_feed(dil)}">{e(t["rss_gta"])}</a></li>')
    alt = (f'<footer class="alt" id="site-haritasi"><div class="wrap">\n<div class="alt-ic">\n'
           f'<div class="alt-marka">{logo(dil)}<p>{e(t["hero_p"])}</p></div>\n'
           f'<nav class="alt-kol" aria-label="{e(t["alt_bolumler"])}"><h2>{e(t["alt_bolumler"])}</h2><ul>{bolumler}</ul></nav>\n'
           f'<nav class="alt-kol" aria-label="{e(t["alt_gta"])}"><h2>{e(t["alt_gta"])}</h2><ul>{gta_l}</ul></nav>\n'
           f'<nav class="alt-kol" aria-label="{e(t["alt_site"])}"><h2>{e(t["alt_site"])}</h2><ul>{site_l}</ul></nav>\n'
           f'<div class="alt-kol"><h2>{e(t["alt_rss"])}</h2><ul>{rss_l}</ul></div>\n</div>\n'
           f'<p class="kisayol-notu js-only">{t["kisayol_notu"]}</p>\n'
           f'<p class="marka-notu">{MARKA}. {e(t["marka_notu"])}</p>\n</div></footer>\n')
    alt_nav = []
    for b in ("ana", "haber", "oyunlar", "indirim"):
        hedef = SAYFA[b][dil]
        cur = ' aria-current="page"' if hedef == yol else (' aria-current="true"' if b == bolum and b != "ana" else "")
        alt_nav.append(f'<li><a href="{u(hedef)}"{cur}>{IK[b]}<span>{e(t["nav"][b])}</span></a></li>')
    alt_nav.append(f'<li><a href="#site-haritasi" data-cekmece>{IK["menu"]}<span>{e(t["menu"])}</span></a></li>')
    alt += f'<nav class="alt-nav" aria-label="{e(t["alt_nav_aria"])}"><ul>{"".join(alt_nav)}</ul></nav>\n'
    alt += f'<script type="application/json" id="cag-metin">{gom(js_metin(dil))}</script>\n</body>\n</html>\n'
    return "".join(bas) + ust + ana + alt


def gta_feed(dil: str) -> str:
    return "/feed.xml" if dil == "tr" else f"/{dil}/feed.xml"


# ---------------------------------------------------------------- ortak parçalar
def cip_oyun(ad: str, dil: str = "") -> str:
    """Oyun çipi; dil verilir ve oyun oyunlar.json'da varsa oyun sayfasına bağlanır."""
    return so.cip(dil, ad)


def cip_tur(dil: str, tur: str) -> str:
    return f'<span class="cip cip-tur cip-{tur}">{e(M[dil]["tur"].get(tur, tur))}</span>'


def pl_metin(pl: list) -> str:
    return f'<span class="pl">{e(", ".join(pl))}</span>' if pl else ""


def pl_attr(pl: list) -> str:
    return " ".join(slug(p) for p in pl)


def takip_dugme(dil: str, ad: str) -> str:
    return (f'<button type="button" class="takip js-only" data-takip="{oyun_anahtar(ad)}" data-ad="{e(ad)}" aria-pressed="false">'
            f'<span class="takip-isaret" aria-hidden="true"></span><span data-takip-yazi>{e(T[dil]["takip_et"])}</span></button>')


def sayfa_bas(dil: str, bolum: str, h1: str, giris: str = "", ek: str = "") -> str:
    n = BOLUM_NO[bolum]
    return (f'<header class="sayfa-bas"><div class="wrap">\n'
            f'<div class="sb-satir"><kbd class="tus tus-bolum" aria-hidden="true">{n}</kbd><h1>{e(h1)}</h1></div>\n'
            + (f'<p class="giris">{giris}</p>\n' if giris else "") + ek + '</div></header>\n')


def sz_ac(dil: str) -> str:
    """Dar ekranda süzgeç formunu açıp kapatan düğme (yalnız JS açıkken; form JS'siz zaten gizli)."""
    return (f'<button type="button" class="sz-ac js-only" aria-expanded="false" aria-controls="suzgec-form">'
            '<svg class="ikon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h16M7 12h10M10 18h4" stroke="currentColor" '
            f'stroke-width="2" stroke-linecap="round" fill="none"/></svg><span>{e(T[dil]["f_ac"])}</span>'
            '<b class="sz-say" data-sz-say hidden></b></button>')


def suzgec(dil: str, gruplar: list, ad: str, *, arama: bool = True, takipli: bool = True, ek: str = "") -> str:
    t = T[dil]
    h = [sz_ac(dil), f'<form class="suzgec js-only" id="suzgec-form" data-suzgec aria-label="{e(t["f_ara"])}">']
    if arama:
        h.append(f'<label class="sz-ara"><span>{e(t["f_ara"])}</span><input type="search" data-arama '
                 f'placeholder="{e(t["f_ara_yer"])}" autocomplete="off" spellcheck="false"></label>')
    for alan, baslik, secenek in gruplar:
        if not secenek:
            continue
        h.append(f'<fieldset class="sz-grup"><legend>{e(baslik)}</legend><div class="sz-dugmeler">'
                 f'<button type="button" data-alan="{alan}" data-deger="" aria-pressed="true">{e(t["f_tumu"])}</button>')
        h += [f'<button type="button" data-alan="{alan}" data-deger="{d}" aria-pressed="false">{e(et)}</button>' for d, et in secenek]
        h.append("</div></fieldset>")
    if takipli:
        h.append(f'<label class="sz-onay"><input type="checkbox" data-takipli><span>{e(t["f_takip"])}</span></label>')
    h.append(ek)
    h.append(f'<button type="button" class="metin-dugme" data-temizle hidden>{e(t["f_temizle"])}</button></form>')
    bir, cok = say(dil, 1, ad), say(dil, 2, ad).replace("2", "{n}", 1)
    h.append(f'<p class="sonuc js-only" data-sonuc aria-live="polite" data-bir="{e(bir)}" data-cok="{e(cok)}"></p>')
    return "".join(h)


def bos_kutu(metin: str, filtre: str = "", yon: tuple[str, str] | None = None) -> str:
    """Boş liste kutusu; yon=(adres, yazı) verilirse okuru gidebileceği yere yönlendirir."""
    if filtre:
        return f'<p class="bos" data-bos hidden>{e(filtre)}</p>'
    ek = f' <a href="{u(yon[0])}">{e(yon[1])}</a>' if yon else ""
    return f'<p class="bos">{e(metin)}{ek}</p>'


def platform_secenek(ogeler: list, dil: str = "tr") -> list:
    var = {slug(p) for x in ogeler for p in x.get("platform") or []}
    return [(slug(p), so.pl_ad(dil, p)) for p in so.PL_SIRA if slug(p) in var]


# ---------------------------------------------------------------- haber parçaları
def haber_url(dil: str, x: dict) -> str:
    return f"/{sd.KLASOR[dil]}/{x['id']}.html"


def haber_satir(dil: str, x: dict, *, h: str = "h3", ozet: bool = True, oge: bool = False, sinif: str = "") -> str:
    t, pl = x["diller"][dil], x.get("platform") or []
    attr = ""
    if oge:
        attr = (f' id="{x["id"]}" data-oge data-tur="{x["tur"]}" data-platform="{pl_attr(pl)}" data-oyun="{oyun_anahtar(x["oyun"])}"'
                f' data-ara="{e(norm(" ".join([t["baslik"], t["ozet"], x["oyun"], " ".join(pl)])))}"')
    return (f'<li class="satir haber-satir{sinif}"{attr}>'
            f'<p class="meta">{zaman_etiketi(dil, x["tarih"])}{cip_oyun(x["oyun"], dil)}{cip_tur(dil, x["tur"])}{pl_metin(pl)}</p>'
            f'<{h} class="satir-baslik"><a href="{haber_url(dil, x)}">{e(t["baslik"])}</a></{h}>'
            + (f'<p class="ozet">{e(t["ozet"])}</p>' if ozet else "")
            + f'<p class="kaynak-satir">{e(M[dil]["kaynak"])}: {e(x["kaynaklar"][0]["ad"])}</p></li>\n')


# ---------------------------------------------------------------- indirim parçaları
def magaza_haritasi(ind: dict) -> dict:
    return {m["id"]: m for m in ind["magazalar"]}


def firsat_satir(dil: str, f: dict, mag: dict) -> str:
    m = mag.get(f["storeID"], {"ad": "", "ikon": ""})
    dusuk = "enDusuk" in f and f["salePrice"] <= f["enDusuk"] + 0.005
    resim = (f'<img class="f-resim" src="{e(f["thumb"])}" width="120" height="45" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer">'
             if f.get("thumb") else '<span class="f-resim" aria-hidden="true"></span>')
    ikon = (f'<img class="f-ikon" src="{e(m["ikon"])}" width="16" height="16" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer">'
            if m.get("ikon") else "")
    bedava = f["salePrice"] <= 0.001
    fiyat_ic = (f'<strong>{e(M[dil]["tur"]["ucretsiz"])}</strong>' if bedava else f'<strong>{fiyat(dil, f["salePrice"])}</strong>')
    return (f'<li class="firsat">{resim}<div class="f-bilgi">'
            f'<a class="f-ad" href="https://www.cheapshark.com/redirect?dealID={e(f["dealID"])}" rel="noopener nofollow">{e(f["title"])}</a>'
            f'<span class="f-alt"><span class="f-magaza">{ikon}{e(m["ad"])}</span>'
            + (f'<span class="rozet">{e(T[dil]["rozet_dusuk"])}</span>' if dusuk else "")
            + f'</span></div><div class="f-fiyat">'
            + (f'<span class="f-yuzde">{yuzde(dil, f["savings"])}</span>' if f["savings"] >= 1 else "")
            + (f'<del>{fiyat(dil, f["normalPrice"])}</del>' if f["normalPrice"] > f["salePrice"] else "")
            + fiyat_ic + "</div></li>\n")


def epic_resim(r: str) -> str:
    return r + ("&" if "?" in r else "?") + "h=270&w=480&resize=1" if r else ""


def epic_oge(dil: str, x: dict, h: str = "h3") -> str:
    t = T[dil]
    href = f"https://store.epicgames.com/p/{x['slug']}" if x.get("slug") else "https://store.epicgames.com/free-games"
    simdi = x["durum"] == "simdi"
    hedef = x["bitis"] if simdi else x["baslangic"]
    hz = zaman_al(hedef)
    img = (f'<img class="u-resim" src="{e(epic_resim(x["resim"]))}" width="480" height="270" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer">'
           if x.get("resim") else '<span class="u-resim" aria-hidden="true"></span>')
    # Epic fiyatı mağazanın bölgesine göre gelir (şu an TRY). ₺ yalnız Türkçe sayfada, açıklamalı gösterilir;
    # USD her dilde gösterilebilir; başka para birimi gösterilmez (₺ ile USD asla karışmaz).
    para = str(x.get("para") or "").upper()
    normal = ""
    if x.get("normal") and (para == "USD" or (para == "TRY" and dil == "tr")):
        et = t["epic_tr_normal"] if para == "TRY" else t["normal_fiyat"]
        normal = f'<p class="u-normal">{e(et)} <del>{fiyat(dil, x["normal"], para)}</del></p>'
    return (f'<li class="ucretsiz" data-epic data-bas="{x["baslangic"]}" data-bit="{x["bitis"]}" data-durum="{x["durum"]}">{img}'
            f'<div class="u-bilgi"><p class="meta"><span class="cip {"cip-ucretsiz" if simdi else "cip-yakinda"}" data-durum-yazi>'
            f'{e(t["simdi"] if simdi else t["yakinda"])}</span><span class="cip cip-oyun">Epic Games Store</span></p>'
            f'<{h} class="u-ad">{e(x["baslik"])}</{h}>'
            f'<p class="u-kalan"><span data-kalan-etiket>{e(t["bitise"] if simdi else t["baslangica"])}</span> '
            f'<span class="kalan" data-kalan data-hedef="{hedef}" data-gecti="{e(t["gecti"])}">{e(kalan_zaman(dil, hz))}</span></p>'
            f'<p class="u-saat"><span data-saat-etiket>{e(t["bitis"] if simdi else t["baslangic"])}</span>: '
            f'<time datetime="{hedef}" data-yerel>{utc_yaz(dil, hz)}</time></p>{normal}'
            f'<p><a class="dugme" href="{e(href)}" rel="noopener">{e(t["epic_ac"])}</a></p></div></li>\n')


# ---------------------------------------------------------------- söylenti / takvim parçaları
def guven_olcer(dil: str, g: str) -> str:
    return (f'<span class="guven guven-{g}"><span class="g-cubuk" aria-hidden="true"><i></i><i></i><i></i></span>'
            f'{e(T[dil]["guven"][g])}</span>')


def durum_cip(dil: str, d: str) -> str:
    return f'<span class="durum-cip durum-{d}">{e(T[dil]["durum"][d])}</span>'


def soylenti_url(dil: str, s: dict) -> str:
    return f'{u(SAYFA["soylenti"][dil])}#{s["id"]}'


def soylenti_kisa(dil: str, s: dict) -> str:
    dl = s["diller"][dil]
    return (f'<li class="soylenti-kisa"><p class="meta">{cip_oyun(s["oyun"], dil)}{durum_cip(dil, s["durum"])}</p>'
            f'<h3 class="satir-baslik"><a href="{soylenti_url(dil, s)}">{e(dl["baslik"])}</a></h3>'
            f'<p class="ozet">{e(dl["ozet"])}</p>{guven_olcer(dil, s["guven"])}</li>\n')


def soylenti_tam(dil: str, s: dict) -> str:
    t, dl, pl = T[dil], s["diller"][dil], s.get("platform") or []
    ara = norm(" ".join([dl["baslik"], dl["ozet"], s["oyun"], " ".join(pl)]))
    metin = "".join(f"<p>{e(p.strip())}</p>" for p in re.split(r"\n\s*\n", str(dl.get("metin") or "")) if p.strip())
    neden = (f'<details class="neden"><summary>{e(t["neden"])}</summary><p>{e(dl["guven_nedeni"])}</p></details>'
             if str(dl.get("guven_nedeni") or "").strip() else "")
    kay = "".join(f'<li><a href="{e(k["url"])}" rel="noopener nofollow">{e(k["ad"])}</a>'
                  + (f' {zaman_etiketi(dil, k["tarih"])}' if iso_gun(k.get("tarih")) else "") + "</li>" for k in s["kaynaklar"])
    return (f'<article class="soylenti" id="{s["id"]}" data-oge data-guven="{s["guven"]}" data-durum="{s["durum"]}" '
            f'data-platform="{pl_attr(pl)}" data-oyun="{oyun_anahtar(s["oyun"])}" data-ara="{e(ara)}">\n'
            f'<p class="meta">{zaman_etiketi(dil, s["tarih"])}{cip_oyun(s["oyun"], dil)}{durum_cip(dil, s["durum"])}{pl_metin(pl)}</p>\n'
            f'<h2>{e(dl["baslik"])}</h2>\n{guven_olcer(dil, s["guven"])}\n<p class="ozet">{e(dl["ozet"])}</p>\n{metin}\n{neden}\n'
            f'<div class="s-alt"><div class="s-kaynak"><h3>{e(t["iddia_kaynak"])}</h3><ul>{kay}</ul></div>{takip_dugme(dil, s["oyun"])}</div>\n'
            '</article>\n')


def takvim_url(dil: str, c: dict) -> str:
    return f'{u(SAYFA["takvim"][dil])}#{c["id"]}'


def cikis_satir(dil: str, c: dict, *, oge: bool = True, h: str = "h3", arac: bool = True) -> str:
    t, pl = T[dil], c.get("platform") or []
    tur = str((c.get("tur") or {}).get(dil) or "")
    if c.get("tarih"):
        d = date.fromisoformat(c["tarih"])
        tus = f'<time class="tarih-tus" datetime="{c["tarih"]}"><b>{d.day}</b><span>{AY_KISA[dil][d.month - 1]}</span></time>'
        kalan = f'<span class="kalan" data-kalan data-hedef="{c["tarih"]}" data-gecti="{e(t["cikti"])}">{e(kalan_gun(dil, d))}</span>'
    else:
        tus = '<span class="tarih-tus belirsiz" aria-hidden="true"><b>?</b></span>'
        pencere = str((c.get("pencere") or {}).get(dil) or "")
        kalan = f'<span class="kalan belirsiz">{e(pencere)}</span>' if pencere else ""
    attr = ""
    if oge:
        ara = norm(" ".join([c["oyun"], tur, " ".join(pl), str(c.get("gelistirici") or ""), str(c.get("yayinci") or "")]))
        attr = f' id="{c["id"]}" data-oge data-platform="{pl_attr(pl)}" data-oyun="{oyun_anahtar(c["oyun"])}" data-ara="{e(ara)}"'
    kim = []
    if c.get("gelistirici"):
        kim.append(f'<span>{e(t["gelistirici"])}: {e(c["gelistirici"])}</span>')
    if c.get("yayinci") and c.get("yayinci") != c.get("gelistirici"):
        kim.append(f'<span>{e(t["yayinci"])}: {e(c["yayinci"])}</span>')
    kim.append(f'<span>{e(M[dil]["kaynak"])}: <a href="{e(c["kaynak"]["url"])}" rel="noopener">{e(c["kaynak"]["ad"])}</a></span>')
    cipler = (f'<span class="cip">{e(tur)}</span>' if tur else "") + "".join(f'<span class="cip cip-pl">{e(p)}</span>' for p in pl)
    araclar = ""
    if arac:
        ics = (f'<button type="button" class="metin-dugme js-only" data-ics data-id="{c["id"]}" data-ad="{e(c["oyun"])}" '
               f'data-tarih="{c["tarih"]}" data-url="{tam(SAYFA["takvim"][dil])}#{c["id"]}">{e(t["ics"])}</button>' if c.get("tarih") else "")
        araclar = f'<div class="c-arac">{takip_dugme(dil, c["oyun"])}{ics}</div>'
    return (f'<li class="cikis"{attr}>{tus}<div class="c-govde">'
            f'<{h} class="c-ad">{so.oyun_adi_html(dil, c["oyun"])}</{h}><p class="c-cip">{cipler}</p>'
            f'<p class="c-kim">{"".join(kim)}</p></div><div class="c-sag">{kalan}{araclar}</div></li>\n')


# ---------------------------------------------------------------- sayfalar
def ana_sayfa(dil: str, veri: list, ind: dict, ucr: dict, soy: list, tak: list) -> str:
    t = T[dil]
    soy_d = [s for s in soy if dil in s["diller"]]
    yakin = [c for c in tak if c.get("tarih") and date.fromisoformat(c["tarih"]) >= BUGUN]
    simdi_epic = [x for x in ucr["epic"] if x["durum"] == "simdi"]
    ucretsiz_say = len(simdi_epic) + len(ucr["cheapshark"])
    hafta_haber = sum(1 for x in veri if (BUGUN - date.fromisoformat(x["tarih"])).days <= 6)
    hafta_cikis = sum(1 for c in yakin if (date.fromisoformat(c["tarih"]) - BUGUN).days <= 7)
    gta_gun = (date.fromisoformat(GTA_TARIH) - BUGUN).days

    def tus(b: str, say_: str) -> str:
        return (f'<li><a href="{u(SAYFA[b][dil])}"><kbd class="tus">{BOLUM_NO[b]}</kbd>'
                f'<span class="tb-ad">{e(t["nav"][b])}</span><span class="tb-say">{say_}</span></a></li>')

    gta_say = e(t["cikti"]) if gta_gun < 0 else (e(t["bugun"]) if gta_gun == 0 else e(birim(dil, gta_gun, 0)))
    tus_ham = [("haber", e(say(dil, len(veri), "haber"))), ("indirim", e(say(dil, len(ind["firsatlar"]), "firsat"))),
               ("ucretsiz", e(say(dil, ucretsiz_say, "oyun"))), ("soylenti", e(say(dil, len(soy_d), "soylenti"))),
               ("takvim", e(say(dil, len(yakin), "cikis"))), ("gta", gta_say)]
    if so.OYUNLAR:
        tus_ham.append(("oyunlar", e(say(dil, len(so.OYUNLAR), "oyun"))))
    if so._rehber_sirasi(dil):
        tus_ham.append(("rehberler", e(say(dil, len(so._rehber_sirasi(dil)), "rehber"))))
    # tuşlar kısayol numarası sırasıyla dizilir (1 Haberler, 2 Oyunlar, 3 İndirimler ...)
    tuslar = "".join(tus(b, s) for b, s in sorted(tus_ham, key=lambda x: int(BOLUM_NO[x[0]])))
    hero = (f'<section class="hero"><canvas class="hero-tuval js-only" aria-hidden="true"></canvas>'
            f'<div class="hero-isik js-only" aria-hidden="true"></div><div class="wrap">\n'
            f'<h1 data-yaz><span class="secim">{e(t["hero_h1"])}</span></h1>\n'
            f'<p class="hero-p">{e(t["hero_p"])}</p>\n'
            f'<ul class="tuslar" aria-label="{e(t["hero_tus_aria"])}">{tuslar}</ul>\n'
            f'<div class="durum-cubugu" role="group" aria-label="{e(t["hafta"])}"><span class="dc-bas">{e(t["hafta"])}</span>'
            f'<a href="{u(SAYFA["haber"][dil])}"><b>{hafta_haber}</b><span>{e(t["hafta_haber"])}</span></a>'
            f'<a href="{u(SAYFA["takvim"][dil])}"><b>{hafta_cikis}</b><span>{e(t["hafta_cikis"])}</span></a>'
            f'<a href="{u(SAYFA["ucretsiz"][dil])}"><b>{ucretsiz_say}</b><span>{e(t["hafta_ucretsiz"])}</span></a></div>\n'
            '</div></section>\n')

    takip = (f'<section class="blok takip-blok" id="takip" hidden><div class="wrap">\n<h2>{e(t["takip_baslik"])}</h2>\n'
             '<ul class="takip-liste" data-takip-liste></ul>\n</div></section>\n')

    if veri:
        haber_ic = (f'<ul class="satirlar">\n' + haber_satir(dil, veri[0], sinif=" one-cikan")
                    + "".join(haber_satir(dil, x, ozet=False) for x in veri[1:6]) + "</ul>\n")
    else:
        haber_ic = bos_kutu(t["bos_haber"])
    haberler = (f'<section class="panel blok-panel" id="haberler" aria-labelledby="b-haber">\n'
                f'<div class="panel-bas"><h2 id="b-haber">{e(t["son_haberler"])}</h2>'
                f'<a class="panel-link" href="{u(SAYFA["haber"][dil])}">{e(t["tum_haberler"])}</a></div>\n{haber_ic}</section>\n')

    mag = magaza_haritasi(ind)
    if ind["firsatlar"]:
        f_ic = (f'<ul class="firsatlar kompakt" data-firsat-liste>\n' + "".join(firsat_satir(dil, f, mag) for f in ind["firsatlar"][:6]) + "</ul>\n")
    else:
        f_ic = '<ul class="firsatlar kompakt" data-firsat-liste></ul>\n'
    f_bos = f'<p class="bos" data-firsat-bos{"" if not ind["firsatlar"] else " hidden"}>{e(t["bos_firsat"])}</p>\n'
    f_durum = (f'<p class="durum-satir" data-firsat-durum aria-live="polite">'
               f'{e(t["durum_statik"].format(tarih=tarih(dil, ind["guncel"][:10]))) if iso_gun(ind["guncel"][:10]) else ""}</p>\n')
    mini = {"guncel": ind["guncel"], "magazalar": ind["magazalar"], "firsatlar": ind["firsatlar"][:12]}
    firsatlar = (f'<section class="panel blok-panel" id="firsatlar" aria-labelledby="b-firsat" data-firsat="mini" data-boyut="6">\n'
                 f'<div class="panel-bas"><h2 id="b-firsat">{e(t["firsat_baslik"])}</h2>'
                 f'<a class="panel-link" href="{u(SAYFA["indirim"][dil])}">{e(t["tum_firsatlar"])}</a></div>\n'
                 f'{f_ic}{f_bos}{f_durum}<script type="application/json" id="indirim-veri">{gom(mini)}</script>\n</section>\n')

    if simdi_epic or ucr["epic"]:
        u_ic = '<ul class="ucretsiz-liste kompakt">\n' + "".join(epic_oge(dil, x) for x in (simdi_epic or ucr["epic"])[:2]) + "</ul>\n"
    else:
        u_ic = bos_kutu(t["bos_ucretsiz"])
    ucretsiz = (f'<section class="panel blok-panel" id="ucretsiz" aria-labelledby="b-ucretsiz">\n'
                f'<div class="panel-bas"><h2 id="b-ucretsiz">{e(t["ucretsiz_baslik"])}</h2>'
                f'<a class="panel-link" href="{u(SAYFA["ucretsiz"][dil])}">{e(t["tum_ucretsiz"])}</a></div>\n{u_ic}</section>\n')

    if soy_d:
        r_ic = '<ul class="radar-liste">\n' + "".join(soylenti_kisa(dil, s) for s in soy_d[:3]) + "</ul>\n"
    else:
        r_ic = bos_kutu(t["bos_soylenti"])
    radar = (f'<section class="blok radar" id="radar" aria-labelledby="b-radar"><div class="wrap">\n'
             f'<div class="blok-bas"><h2 id="b-radar">{e(t["radar"])}</h2><p>{e(t["radar_not"])}</p>'
             f'<a class="panel-link" href="{u(SAYFA["soylenti"][dil])}">{e(t["tum_soylenti"])}</a></div>\n{r_ic}</div></section>\n')

    if yakin:
        y_ic = '<ul class="takvim-liste ikili">\n' + "".join(cikis_satir(dil, c, oge=False) for c in yakin[:6]) + "</ul>\n"
    else:
        y_ic = bos_kutu(t["bos_takvim"])
    yaklasan = (f'<section class="blok" id="yaklasan" aria-labelledby="b-yaklasan"><div class="wrap">\n'
                f'<div class="blok-bas"><h2 id="b-yaklasan">{e(t["yaklasan"])}</h2>'
                f'<a class="panel-link" href="{u(SAYFA["takvim"][dil])}">{e(t["tum_takvim"])}</a></div>\n{y_ic}'
                f'<p class="takip-ipucu js-only" data-takip-ipucu hidden><span class="takip-isaret" aria-hidden="true"></span>'
                f'<span>{t["takip_bos"]}</span></p>\n</div></section>\n')

    cikti = gta_gun < 0
    bant = (f'<section class="blok gta-bant" id="gta" aria-labelledby="b-gta"><div class="wrap"><div class="bant-ic">\n'
            f'<div class="bant-metin"><h2 id="b-gta">{e(t["gta_bant_h_cikti"] if cikti else t["gta_bant_h"])}</h2>'
            f'<p>{e(t["gta_bant_p"])}</p><p><a class="dugme dugme-dolu" href="{u(SAYFA["gta"][dil])}">{e(t["gta_bant_link"])}</a></p></div>\n'
            + ("" if cikti else geri_sayim(dil, kucuk=True)) + '\n</div></div></section>\n')

    gundem = ""
    if veri:
        og = "".join(f'<li><span class="gd-tarih">{zaman_etiketi(dil, x["tarih"])}</span>'
                     f'<a href="{haber_url(dil, x)}">{e(x["diller"][dil]["baslik"])}</a></li>' for x in veri[:8])
        og2 = re.sub(r'<a href="', '<a tabindex="-1" href="', og)
        gundem = (f'<section class="gundem" aria-labelledby="b-gundem"><div class="wrap gundem-ic">\n'
                  f'<h2 class="gundem-bas" id="b-gundem">{e(t["gundem"])}</h2>'
                  f'<div class="gundem-pencere"><div class="gundem-serit"><ul class="gundem-liste">{og}</ul>'
                  f'<ul class="gundem-liste gundem-kopya js-only" aria-hidden="true">{og2}</ul></div></div>'
                  f'<button type="button" class="gundem-dugme js-only" data-dur="{e(t["gundem_dur"])}" '
                  f'data-bas="{e(t["gundem_bas"])}" aria-label="{e(t["gundem_dur"])}">'
                  '<svg class="ikon" viewBox="0 0 24 24" aria-hidden="true"><path class="gd-dur" d="M8 5v14M16 5v14" stroke="currentColor" '
                  'stroke-width="3" stroke-linecap="round"/><path class="gd-bas" d="M8 5l11 7-11 7z" fill="currentColor"/></svg></button>'
                  '\n</div></section>\n')
    takip_veri = takip_verisi(dil, veri, soy_d, tak)
    govde = (hero + gundem + takip + '<div class="wrap ana-izgara">\n' + haberler + '<div class="yan-kol">\n' + firsatlar + ucretsiz
             + '</div>\n</div>\n' + so.populer_serit(dil, veri, soy, tak) + radar + yaklasan + bant
             + f'<script type="application/json" id="takip-veri">{gom(takip_veri)}</script>\n')
    ld = {"@context": "https://schema.org", "@type": "WebSite", "name": MARKA, "url": f"{SITE}/", "inLanguage": dil}
    return kabuk(dil, SAYFA["ana"][dil], t["ana_title"], t["ana_desc"], govde, esler=SAYFA["ana"], bolum="ana",
                 tam_baslik=True, sayfa_turu="ana",
                 ek_bas=f'<script type="application/ld+json">{gom(ld)}</script>\n' + so.bas_ek())


def takip_verisi(dil: str, veri: list, soy: list, tak: list) -> dict:
    d: dict[str, dict] = {}
    for c in tak:
        o = d.setdefault(oyun_anahtar(c["oyun"]), {"a": c["oyun"]})
        if c.get("tarih"):
            o["t"] = c["tarih"]
        o["u"] = takvim_url(dil, c)
    for x in veri:
        o = d.setdefault(oyun_anahtar(x["oyun"]), {"a": x["oyun"]})
        h = o.setdefault("h", [])
        if len(h) < 2:
            h.append([x["diller"][dil]["baslik"], haber_url(dil, x), x["tarih"]])
    for s in soy:
        o = d.setdefault(oyun_anahtar(s["oyun"]), {"a": s["oyun"]})
        o.setdefault("s", [s["diller"][dil]["baslik"], soylenti_url(dil, s)])
    return d


def hub_sayfasi(dil: str, veri: list) -> str:
    t, m = T[dil], M[dil]
    son = veri[0]["tarih"] if veri else BUGUN.isoformat()
    turler = [(k, m["tur"][k]) for k in sd.TUR if any(x["tur"] == k for x in veri)]
    gruplar, sira = {}, []
    for x in veri:
        a = x["tarih"][:7]
        if a not in gruplar:
            gruplar[a] = []
            sira.append(a)
        gruplar[a].append(x)
    liste = "".join(f'<section class="ay-grup" data-grup><h2>{ay_baslik(dil, a + "-01")}</h2>\n<ul class="satirlar panel">\n'
                    + "".join(haber_satir(dil, x, oge=True) for x in gruplar[a]) + "</ul></section>\n" for a in sira)
    ek = (f'<p class="not">{e(m["hub_not"])}</p>\n<p class="sb-meta">{e(m["guncel"])}: {zaman_etiketi(dil, son)}'
          f'<a href="/{sd.FEED[dil]}">{e(t["rss_abone"])}</a></p>\n')
    govde = (sayfa_bas(dil, "haber", m["hub_h1"], e(m["hub_aciklama"]), ek)
             + '<div class="wrap liste-duzen" data-suzgec-kok>\n<aside class="liste-yan">'
             + suzgec(dil, [("tur", t["f_tur"], turler), ("platform", t["f_platform"], platform_secenek(veri, dil))], "haber")
             + '</aside>\n<div class="liste-ana">\n' + (liste or bos_kutu(t["bos_haber"]))
             + bos_kutu("", t["bos_filtre"]) + '</div>\n</div>\n')
    return kabuk(dil, SAYFA["haber"][dil], m["hub_baslik"], m["hub_aciklama"], govde, esler=SAYFA["haber"], bolum="haber",
                 sayfa_turu="haber")


def haber_sayfasi(dil: str, x: dict, veri: list) -> str:
    t, m, dl = T[dil], M[dil], x["diller"][dil]
    yollar = {d: f"{sd.KLASOR[d]}/{x['id']}.html" for d in DILLER}
    og = sd.kart_ad(x["id"], dil, "og")
    ld = {"@context": "https://schema.org", "@type": "NewsArticle", "headline": dl["baslik"], "description": dl["ozet"],
          "datePublished": x["tarih"], "inLanguage": dil, "image": [f"{SITE}/{og}"], "mainEntityOfPage": tam(yollar[dil]),
          "publisher": {"@type": "Organization", "name": MARKA, "url": f"{SITE}/"},
          "isBasedOn": [s["url"] for s in x["kaynaklar"]]}
    yon = sd.YONLENDIR % json.dumps({d: "/" + yollar[d] for d in DILLER})
    paragraflar = "".join(f"<p>{e(p.strip())}</p>\n" for p in re.split(r"\n\s*\n", dl["metin"]) if p.strip())
    kaynaklar = "".join(f'<li><a href="{e(s["url"])}" rel="noopener">{e(s["ad"])}</a> {zaman_etiketi(dil, s.get("tarih") or x["tarih"])}</li>'
                        for s in x["kaynaklar"])
    etiket = " ".join(f'<span class="cip cip-etiket">{e(s)}</span>' for s in dl.get("etiketler", []))
    url = tam(yollar[dil])
    paylas_metin = dl["baslik"]
    from urllib.parse import quote
    x_link = f"https://x.com/intent/post?text={quote(paylas_metin)}&url={quote(url, safe='')}"
    wa_link = f"https://wa.me/?text={quote(paylas_metin + ' ' + url)}"
    k = oyun_anahtar(x["oyun"])
    ilgili = [y for y in veri if y["id"] != x["id"] and oyun_anahtar(y["oyun"]) == k]
    ilgili += [y for y in veri if y["id"] != x["id"] and y not in ilgili and y["tur"] == x["tur"]]
    ilgili_html = ""
    if ilgili:
        ilgili_html = (f'<section class="ilgili" aria-labelledby="b-ilgili"><h2 id="b-ilgili">{e(t["ilgili"])}</h2>\n'
                       '<ul class="satirlar panel">\n' + "".join(haber_satir(dil, y, ozet=False) for y in ilgili[:3]) + "</ul></section>\n")
    pl = x.get("platform") or []
    govde = (f'<article class="wrap haber-detay">\n<p class="geri"><a href="{u(SAYFA["haber"][dil])}">{e(m["geri"])}</a></p>\n'
             f'<div class="hd-govde">\n'
             f'<header class="hd-bas"><p class="meta">{zaman_etiketi(dil, x["tarih"])}{cip_oyun(x["oyun"], dil)}{cip_tur(dil, x["tur"])}{pl_metin(pl)}</p>\n'
             f'<h1>{e(dl["baslik"])}</h1>\n<p class="giris">{e(dl["ozet"])}</p></header>\n'
             f'<div class="metin">\n{paragraflar}</div>\n<aside class="hd-yan">\n'
             f'<section class="kutu kaynak-kutu"><h2>{e(t["kaynaklar_baslik"])}</h2><ul>{kaynaklar}</ul></section>\n'
             f'<section class="kutu"><h2>{e(t["paylas"])}</h2><div class="paylas">'
             f'<button type="button" class="dugme js-only" data-kopyala="{url}">{e(t["kopyala"])}</button>'
             f'<button type="button" class="dugme" data-paylas-web hidden>{e(t["paylas"])}</button>'
             f'<a class="dugme" href="{e(x_link)}" rel="noopener">{e(t["x_paylas"])}</a>'
             f'<a class="dugme" href="{e(wa_link)}" rel="noopener">{e(t["wa_paylas"])}</a></div>'
             f'<p class="paylas-durum" data-paylas-durum aria-live="polite"></p></section>\n'
             f'<section class="kutu js-only"><h2>{e(x["oyun"])}</h2>{takip_dugme(dil, x["oyun"])}</section>\n'
             + (f'<section class="kutu"><h2>{e(t["etiketler"])}</h2><p class="etiketler">{etiket}</p></section>\n' if etiket else "")
             + '</aside>\n' + ilgili_html + '</div>\n</article>\n')
    return kabuk(dil, yollar[dil], f"{dl['baslik']} | {m['menu']}", dl["ozet"], govde, esler=yollar, bolum="haber", tip="article",
                 gorsel=og, sayfa_turu="haber-detay",
                 ek_bas=f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>\n' + yon)


def indirim_sayfasi(dil: str, ind: dict) -> str:
    t = T[dil]
    mag = magaza_haritasi(ind)
    ops = lambda ls: "".join(f'<option value="{v}">{e(a)}</option>' for v, a in ls)  # noqa: E731
    form = (sz_ac(dil) + f'<form class="suzgec firsat-form js-only" id="suzgec-form" data-firsat-form aria-label="{e(t["indirim_h1"])}">'
            f'<label class="sz-ara"><span>{e(t["f_oyun"])}</span><input type="search" name="q" placeholder="{e(t["f_ara_yer"])}" autocomplete="off" spellcheck="false"></label>'
            f'<label class="sz-sec"><span>{e(t["f_magaza"])}</span><select name="magaza">{ops([("", t["f_tum_magaza"])] + [(m["id"], m["ad"]) for m in ind["magazalar"]])}</select></label>'
            f'<label class="sz-sec"><span>{e(t["f_fiyat"])}</span><select name="fiyat">{ops([("", t["f_herhangi"])] + [(str(n), fiyat(dil, n).replace(",00", "")) for n in (5, 10, 15, 20, 30, 50)])}</select></label>'
            f'<label class="sz-sec"><span>{e(t["f_indirim"])}</span><select name="indirim">{ops([("", t["f_herhangi"])] + [(str(n), t["en_az"].format(n=n)) for n in (25, 50, 75, 90)])}</select></label>'
            f'<label class="sz-sec"><span>{e(t["f_sirala"])}</span><select name="sira">{ops(list(t["sira"].items()))}</select></label>'
            f'<label class="sz-onay"><input type="checkbox" name="dusuk"><span>{e(t["f_dusuk"])}</span></label></form>')
    durum = (e(t["durum_statik"].format(tarih=tarih(dil, ind["guncel"][:10]))) if iso_gun(ind["guncel"][:10]) else "")
    liste = "".join(firsat_satir(dil, f, mag) for f in ind["firsatlar"])
    govde = (sayfa_bas(dil, "indirim", t["indirim_h1"], e(t["indirim_giris"]))
             + '<div class="wrap liste-duzen" data-firsat="tam" data-boyut="60">\n'
             + f'<aside class="liste-yan">{form}</aside>\n<div class="liste-ana">\n'
             + f'<p class="durum-satir" data-firsat-durum aria-live="polite">{durum}</p>\n'
             + f'<ul class="firsatlar panel" data-firsat-liste>\n{liste}</ul>\n'
             + f'<p class="bos" data-firsat-bos{" hidden" if liste else ""}>{e(t["bos_firsat"] if not liste else t["bos_filtre"])}</p>\n'
             + f'<p class="devam js-only"><button type="button" class="dugme" data-firsat-daha hidden>{e(t["daha"])}</button></p>\n'
             + f'<p class="not">{e(t["firsat_not"])} {e(t["usd_not"])}</p>\n</div>\n'
             + f'<script type="application/json" id="indirim-veri">{gom(ind)}</script>\n</div>\n')
    return kabuk(dil, SAYFA["indirim"][dil], t["indirim_title"], t["indirim_desc"], govde, esler=SAYFA["indirim"], bolum="indirim",
                 sayfa_turu="indirim")


def ucretsiz_sayfasi(dil: str, ucr: dict, ind: dict) -> str:
    t = T[dil]
    mag = magaza_haritasi(ind)
    epic = ('<ul class="ucretsiz-liste">\n' + "".join(epic_oge(dil, x) for x in ucr["epic"]) + "</ul>\n") if ucr["epic"] else bos_kutu(t["bos_epic"])
    cs = "".join(firsat_satir(dil, f, mag) for f in ucr["cheapshark"])
    gomu = {"epic": [norm(x["baslik"]) for x in ucr["epic"]], "magazalar": ind["magazalar"], "firsatlar": ucr["cheapshark"],
            "guncel": ucr["guncel"]}
    govde = (sayfa_bas(dil, "ucretsiz", t["ucretsiz_h1"], e(t["ucretsiz_giris"]))
             + f'<div class="wrap">\n<section class="blok-ic" aria-labelledby="b-epic"><h2 id="b-epic">{e(t["epic_baslik"])}</h2>\n{epic}</section>\n'
             + f'<section class="blok-ic" aria-labelledby="b-cs" data-firsat="ucretsiz" data-boyut="60"><h2 id="b-cs">{e(t["cs_baslik"])}</h2>\n'
             + f'<ul class="firsatlar panel" data-firsat-liste>\n{cs}</ul>\n'
             + f'<p class="bos" data-firsat-bos{" hidden" if cs else ""}>{e(t["bos_cs"])}</p>\n'
             + '<p class="durum-satir" data-firsat-durum aria-live="polite"></p>\n'
             + f'<script type="application/json" id="indirim-veri">{gom(gomu)}</script>\n</section>\n'
             + f'<p class="not">{e(t["firsat_not"])} {e(t["usd_not"])}</p>\n</div>\n')
    return kabuk(dil, SAYFA["ucretsiz"][dil], t["ucretsiz_title"], t["ucretsiz_desc"], govde, esler=SAYFA["ucretsiz"],
                 bolum="ucretsiz", sayfa_turu="ucretsiz")


def soylenti_sayfasi(dil: str, soy: list) -> str:
    t = T[dil]
    ogeler = [s for s in soy if dil in s["diller"]]
    uyari = (f'<div class="uyari" role="note"><p><strong>{e(t["uyari_baslik"])}</strong> {e(t["uyari_metin"])}</p></div>\n'
             f'<p class="lejant">{guven_olcer(dil, "dusuk")}{guven_olcer(dil, "orta")}{guven_olcer(dil, "yuksek")}'
             f'<span>{e(t["lejant"])}</span></p>\n')
    guven = [(g, t["guven_k"][g]) for g in GUVEN if any(s["guven"] == g for s in ogeler)]
    durum = [(d, t["durum"][d]) for d in DURUM if any(s["durum"] == d for s in ogeler)]
    liste = ('<div class="soylenti-liste" data-grup>\n' + "".join(soylenti_tam(dil, s) for s in ogeler) + "</div>\n") if ogeler else bos_kutu(t["bos_soylenti"], yon=(SAYFA["haber"][dil], t["bos_yon"]))
    govde = (sayfa_bas(dil, "soylenti", t["soylenti_h1"], "", uyari)
             + '<div class="wrap liste-duzen" data-suzgec-kok>\n<aside class="liste-yan">'
             + (suzgec(dil, [("guven", t["f_guven"], guven), ("durum", t["f_durum"], durum),
                             ("platform", t["f_platform"], platform_secenek(ogeler, dil))], "soylenti") if ogeler else "")
             + '</aside>\n<div class="liste-ana">\n' + liste + bos_kutu("", t["bos_filtre"]) + '</div>\n</div>\n')
    return kabuk(dil, SAYFA["soylenti"][dil], t["soylenti_title"], t["soylenti_desc"], govde, esler=SAYFA["soylenti"],
                 bolum="soylenti", sayfa_turu="soylenti")


def takvim_sayfasi(dil: str, tak: list) -> str:
    t = T[dil]
    sinir = BUGUN - timedelta(days=31)
    tarihli = [c for c in tak if c.get("tarih") and date.fromisoformat(c["tarih"]) >= sinir]
    gecmis = [c for c in tak if c.get("tarih") and date.fromisoformat(c["tarih"]) < sinir]
    belirsiz = [c for c in tak if not c.get("tarih")]
    gruplar, sira = {}, []
    for c in tarihli:
        a = c["tarih"][:7]
        if a not in gruplar:
            gruplar[a] = []
            sira.append(a)
        gruplar[a].append(c)
    bolumler = [f'<section class="ay-grup" data-grup><h2>{ay_baslik(dil, a + "-01")}</h2>\n<ul class="takvim-liste panel">\n'
                + "".join(cikis_satir(dil, c) for c in gruplar[a]) + "</ul></section>\n" for a in sira]
    if belirsiz:
        bolumler.append(f'<section class="ay-grup" data-grup><h2>{e(t["kesin_degil"])}</h2>\n<ul class="takvim-liste panel">\n'
                        + "".join(cikis_satir(dil, c) for c in belirsiz) + "</ul></section>\n")
    if gecmis:
        bolumler.append(f'<details class="ay-grup gecmis" data-grup><summary>{e(t["gecmis"])}</summary>\n<ul class="takvim-liste panel">\n'
                        + "".join(cikis_satir(dil, c) for c in reversed(gecmis)) + "</ul></details>\n")
    ics = f'<button type="button" class="dugme" data-ics-takip>{e(t["ics_takip"])}</button><p class="sz-not" data-ics-durum aria-live="polite"></p>'
    govde = (sayfa_bas(dil, "takvim", t["takvim_h1"], e(t["takvim_giris"]))
             + '<div class="wrap liste-duzen" data-suzgec-kok>\n<aside class="liste-yan">'
             + (suzgec(dil, [("platform", t["f_platform"], platform_secenek(tak, dil))], "cikis", ek=ics) if tak else "")
             + '</aside>\n<div class="liste-ana">\n' + ("".join(bolumler) or bos_kutu(t["bos_takvim"], yon=(SAYFA["haber"][dil], t["bos_yon"])))
             + bos_kutu("", t["bos_filtre"]) + '</div>\n</div>\n')
    return kabuk(dil, SAYFA["takvim"][dil], t["takvim_title"], t["takvim_desc"], govde, esler=SAYFA["takvim"], bolum="takvim",
                 sayfa_turu="takvim")


def yok_sayfasi(veri: list | None = None) -> str:
    t = T["tr"]
    diger = "".join(f'<p lang="{d}">{e(T[d]["yok_h1"])} <a href="{u(SAYFA["ana"][d])}">{e(T[d]["yok_ana"])}</a></p>\n'
                    for d in DILLER if d != "tr")
    bolumler = "".join(f'<li><a href="{u(SAYFA[b]["tr"])}"><kbd class="tus">{BOLUM_NO[b]}</kbd>{e(t["nav"][b])}</a></li>' for b in NAV)
    # kaybolan ziyaretçiye son haberler: sayfanın altı boş kalmaz
    son = [x for x in (veri or []) if "tr" in x.get("diller", {})][:4]
    son_ic = ""
    if son:
        son_ic = (f'<section class="panel yok-son" aria-labelledby="b-yok-son"><div class="panel-bas">'
                  f'<h2 id="b-yok-son">{e(t["son_haberler"])}</h2>'
                  f'<a class="panel-link" href="{u(SAYFA["haber"]["tr"])}">{e(t["tum_haberler"])}</a></div>\n'
                  f'<ul class="satirlar">\n' + "".join(haber_satir("tr", x, ozet=False) for x in son) + '</ul></section>\n')
    govde = (f'<section class="yok"><div class="wrap">\n<div class="yok-ana">\n<h1><span class="secim">{e(t["yok_h1"])}</span></h1>\n'
             f'<p class="giris">{e(t["yok_p"])}</p>\n'
             f'<p class="yok-arac"><a class="dugme dugme-dolu" href="/">{e(t["yok_ana"])}</a>'
             f'<button type="button" class="dugme js-only" data-ara-ac>{IK_ARA}{e(t["ara"])}</button></p>\n'
             f'<ul class="yok-bolum">{bolumler}</ul>\n<div class="yok-diller">\n{diger}</div>\n</div>\n{son_ic}</div></section>\n')
    return kabuk("tr", "404.html", t["yok_title"], t["yok_p"], govde, bolum=None, sayfa_turu="yok", dizinle=False,
                 hedefler=dict(SAYFA["ana"]))


def eski_sayfa(dil: str, bilgi: dict, esler: dict | None, gta: bool) -> str:
    govde = bilgi["main"]
    yol = bilgi["yol"]
    if yol == SAYFA["gta"][dil]:
        govde = isaret(govde, "gta-ust", gta_ust(dil))
        govde = isaret(govde, "gta-haber", gta_haberleri(dil))
        govde = isaret(govde, "gta-dizin", gta_dizin(dil, yol))
    if not govde.startswith("\n"):
        govde = "\n" + govde
    govde = govde[1:] if govde.startswith("\n") else govde
    bolum = "gta" if gta else None
    return kabuk(dil, yol, bilgi["baslik"], bilgi["aciklama"], govde, esler=esler, bolum=bolum, tip=bilgi["tip"],
                 ek_bas=bilgi["ld"], gta=gta, sayfa_turu="eski")


# ---------------------------------------------------------------- arama dizini
def ara_dizini(dil: str, veri: list, soy: list, tak: list, eskiler: list) -> list:
    t = T[dil]
    d = []

    def ekle(baslik, url, tur, oyun="", gun="", ek=""):
        d.append({"t": baslik, "u": url, "k": tur, "o": oyun, "d": gun, "x": norm(" ".join([baslik, oyun, ek]))})

    for b in ("ana",) + NAV:
        ekle(t["nav"][b], u(SAYFA[b][dil]), "sayfa")
    ekle(t["hakkinda"], u(SAYFA["hakkinda"][dil]), "sayfa")
    ekle(t["gizlilik"], u(SAYFA["gizlilik"][dil]), "sayfa")
    for x in veri:
        dl = x["diller"][dil]
        ekle(dl["baslik"], haber_url(dil, x), "haber", x["oyun"], x["tarih"], dl["ozet"] + " " + " ".join(x.get("platform") or []))
    for c in tak:
        ekle(c["oyun"], takvim_url(dil, c), "takvim", "", c.get("tarih") or "",
             " ".join([str((c.get("tur") or {}).get(dil) or ""), " ".join(c.get("platform") or []), str(c.get("gelistirici") or "")]))
    for s in soy:
        if dil in s["diller"]:
            ekle(s["diller"][dil]["baslik"], soylenti_url(dil, s), "soylenti", s["oyun"], s["tarih"], s["diller"][dil]["ozet"])
    gta_yollar = {p for p, _, _ in GTA_SAYFALAR[dil]} | ({p for p in TEK_TR} if dil == "tr" else set())
    for b in eskiler:
        if b["yol"] in gta_yollar and b["yol"] != SAYFA["gta"][dil]:
            ekle(b["baslik"], u(b["yol"]), "gta", "", "", b["aciklama"])
    for x in so.ara_ekleri(dil):
        ekle(*x)
    return d


# ---------------------------------------------------------------- yazma, manifest, site haritası
def sayfa_yaz(yol: str, metin: str, *, esler: dict | None = None, lastmod: str | None = None, harita: bool = True) -> int:
    if harita:
        if lastmod is None:
            m = re.search(r'<main id="main"[^>]*>(.*)</main>', metin, re.S)
            h = hashlib.sha1((m.group(1) if m else metin).encode("utf-8")).hexdigest()[:12]
            eski = MANIFEST.get(yol)
            if eski and eski[0] == h:
                lastmod = eski[1]
            else:
                lastmod = ESKI_HARITA.get(tam(yol), BUGUN.isoformat()) if (eski is None and ESKI_HARITA.get(tam(yol))) else BUGUN.isoformat()
                MANIFEST[yol] = [h, lastmod]
            MANIFEST[yol] = [h, lastmod]
        URETILEN[yol] = {"esler": esler, "lastmod": lastmod}
    return int(sd.yaz(KOK / yol, metin))


def eski_haritayi_oku() -> None:
    p = KOK / "sitemap.xml"
    if p.exists():
        for loc, lm in re.findall(r"<loc>([^<]+)</loc><lastmod>([^<]+)</lastmod>", p.read_text(encoding="utf-8")):
            ESKI_HARITA[loc] = lm


def site_haritasi() -> int:
    sira = sorted(URETILEN, key=lambda y: (y not in SAYFA["ana"].values(), y.count("/"), y))
    satir = []
    for yol in sira:
        b = URETILEN[yol]
        alt = ""
        es = {d: b["esler"][d] for d in DILLER if (b["esler"] or {}).get(d)}
        if len(es) > 1:
            alt = "".join(f'<xhtml:link rel="alternate" hreflang="{d}" href="{tam(p)}"/>' for d, p in es.items())
            alt += f'<xhtml:link rel="alternate" hreflang="x-default" href="{tam(es.get("en") or es.get("tr") or next(iter(es.values())))}"/>'
        satir.append(f"  <url><loc>{tam(yol)}</loc><lastmod>{b['lastmod']}</lastmod>{alt}</url>\n")
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
           + "".join(satir) + "</urlset>\n")
    return int(sd.yaz(KOK / "sitemap.xml", xml))


def surum_al(yol: str) -> str:
    p = KOK / yol
    return hashlib.sha1(p.read_bytes()).hexdigest()[:8] if p.exists() else "0"


# ---------------------------------------------------------------- ana akış
def derle(veri: list) -> dict:
    global BUGUN, SIMDI
    s = os.environ.get("SITE_BUGUN")
    BUGUN = date.fromisoformat(s) if s else datetime.now(TRT).date()
    SIMDI = datetime.combine(BUGUN, time(0), TRT)
    UYARILAR.clear()
    URETILEN.clear()
    MANIFEST.clear()
    mp = KOK / "data" / "sayfalar.json"
    if mp.exists():
        try:
            MANIFEST.update(json.loads(mp.read_text(encoding="utf-8")))
        except ValueError:
            uyar("data/sayfalar.json bozuk; yeniden oluşturuldu.")
    eski_haritayi_oku()

    soy, tak, ind, ucr = soylentiler_yukle(), takvim_yukle(), indirim_yukle(), ucretsiz_yukle()
    SURUM["css"], SURUM["js"] = surum_al("style.css"), surum_al("site.js")

    # elle yazılmış sayfalar
    eski_gruplar = []
    for i, grup in enumerate(ESLER):
        gta = i < 5
        bilgiler = {d: eski_oku(grup[d]) for d in DILLER}
        tamam = all(bilgiler.values())
        for d in DILLER:
            if bilgiler[d]:
                eski_gruplar.append((d, bilgiler[d], dict(grup) if tamam else None, gta))
    for yol in TEK_TR:
        b = eski_oku(yol)
        if b:
            eski_gruplar.append(("tr", b, None, True))

    so.bagla(sys.modules[__name__])
    so.yukle()
    degisen = so.tema_yaz()
    for d in DILLER:
        dizin = ara_dizini(d, veri, soy, tak, [b for dd, b, _, _ in eski_gruplar if dd == d])
        metin = json.dumps(dizin, ensure_ascii=False, separators=(",", ":")) + "\n"
        degisen += int(sd.yaz(KOK / f"ara-{d}.json", metin))
        SURUM["ara-" + d] = hashlib.sha1(metin.encode("utf-8")).hexdigest()[:8]

    for d in DILLER:
        degisen += sayfa_yaz(SAYFA["ana"][d], ana_sayfa(d, veri, ind, ucr, soy, tak), esler=SAYFA["ana"])
        degisen += sayfa_yaz(SAYFA["haber"][d], hub_sayfasi(d, veri), esler=SAYFA["haber"])
        for x in veri:
            yollar = {dd: f"{sd.KLASOR[dd]}/{x['id']}.html" for dd in DILLER}
            degisen += sayfa_yaz(yollar[d], haber_sayfasi(d, x, veri), esler=yollar, lastmod=x["tarih"])
        degisen += sayfa_yaz(SAYFA["indirim"][d], indirim_sayfasi(d, ind), esler=SAYFA["indirim"])
        degisen += sayfa_yaz(SAYFA["ucretsiz"][d], ucretsiz_sayfasi(d, ucr, ind), esler=SAYFA["ucretsiz"])
        degisen += sayfa_yaz(SAYFA["soylenti"][d], soylenti_sayfasi(d, soy), esler=SAYFA["soylenti"])
        degisen += sayfa_yaz(SAYFA["takvim"][d], takvim_sayfasi(d, tak), esler=SAYFA["takvim"])
        degisen += int(sd.yaz(KOK / sd.FEED[d], sd.rss(d, veri)))
        degisen += so.sayfalari_yaz(d, veri, soy, tak)
    for d, b, esler, gta in eski_gruplar:
        degisen += sayfa_yaz(b["yol"], eski_sayfa(d, b, esler, gta), esler=esler)
    degisen += sayfa_yaz("404.html", yok_sayfasi(veri), harita=False)
    degisen += so.artiklari_temizle(URETILEN)

    for k in [k for k in MANIFEST if k not in URETILEN]:
        del MANIFEST[k]
    degisen += int(sd.yaz(mp, json.dumps(dict(sorted(MANIFEST.items())), ensure_ascii=False, indent=0) + "\n"))
    degisen += site_haritasi()
    for w in UYARILAR:
        print("UYARI:", w)
    return {"sayfa": len(URETILEN) + 1, "degisen": degisen, "soylenti": len(soy), "takvim": len(tak),
            "firsat": len(ind["firsatlar"]), "epic": len(ucr["epic"]), "uyari": len(UYARILAR),
            "oyun": len(so.OYUNLAR), "rehber": len(so.REHBER)}


def main() -> None:
    sonuc = derle(sd.yukle())
    print(f"Site: {sonuc['sayfa']} sayfa, {sonuc['degisen']} dosya değişti; {sonuc['soylenti']} söylenti, "
          f"{sonuc['takvim']} çıkış, {sonuc['firsat']} fırsat, {sonuc['epic']} Epic oyunu, {sonuc['oyun']} oyun, "
          f"{sonuc['rehber']} rehber, {sonuc['uyari']} uyarı.")


if __name__ == "__main__":
    main()
