#!/usr/bin/env python3
"""Çok oyunlu haber derleyici.

data/icerik.json  →  4 dilde haber sayfaları, paylaşım kartları (JPEG), RSS,
site haritası, ana sayfa kutusu ve menü bağlantısı.

Kullanım:  python tools/sosyal_derle.py
Aynı girdiyle tekrar çalıştırmak aynı çıktıyı üretir (değişiklik yoksa git temiz kalır).
"""
from __future__ import annotations

import hashlib
import html
import json
import pathlib
import re
import sys
from email.utils import format_datetime
from datetime import datetime, timezone

KOK = pathlib.Path(__file__).resolve().parent.parent
SITE = "https://ctrl-agame.com"
GORUNEN = "ctrl-agame.com"
DILLER = ("tr", "en", "fr", "es")
ONEK = {"tr": "/", "en": "/en/", "fr": "/fr/", "es": "/es/"}
HUB = {"tr": "oyun-haberleri.html", "en": "en/game-news.html", "fr": "fr/actus-jeux.html", "es": "es/noticias-juegos.html"}
KLASOR = {"tr": "oyun-haberleri", "en": "en/game-news", "fr": "fr/actus-jeux", "es": "es/noticias-juegos"}
FEED = {"tr": "oyun-haberleri.xml", "en": "en/game-news.xml", "fr": "fr/actus-jeux.xml", "es": "es/noticias-juegos.xml"}
GTA_HABER = {"tr": "haberler.html", "en": "en/news.html", "fr": "fr/news.html", "es": "es/news.html"}
KART_KLASOR = "kart"
TUR = ("haber", "ucretsiz", "cikis", "indirim", "guncelleme")

AY = {
    "tr": ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"],
    "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
    "fr": ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"],
    "es": ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"],
}

M = {
    "tr": {
        "menu": "Oyun haberleri", "hub_baslik": "Oyun haberleri: PlayStation, Xbox, Nintendo ve PC",
        "hub_h1": "Oyun haberleri",
        "hub_aciklama": "Tüm platformlardan teyitli oyun haberleri: çıkışlar, ücretsiz oyunlar, indirimler ve güncellemeler. Her haberin resmî kaynağı belirtilir.",
        "hub_not": "Yalnız resmî duyurulara (PlayStation Blog, Xbox Wire, Nintendo, Epic Games Store, yayıncı siteleri) dayanır; söylenti ve sızıntı yazılmaz.",
        "guncel": "Son güncelleme", "kaynak": "Kaynak", "devam": "Haberin tamamı →", "tum": "Tüm oyun haberleri →",
        "geri": "← Tüm oyun haberleri", "kutu": "Diğer oyunlardan haberler", "gta": "GTA VI haberleri →",
        "tur": {"haber": "Haber", "ucretsiz": "Ücretsiz", "cikis": "Çıkış", "indirim": "İndirim", "guncelleme": "Güncelleme"},
        "locale": "tr_TR", "feed": "Oyun haberleri (ctrl-agame.com)",
        "oneri": "Bu haber Türkçe de var:", "oneri_link": "Türkçe oku",
    },
    "en": {
        "menu": "Game news", "hub_baslik": "Game news: PlayStation, Xbox, Nintendo and PC",
        "hub_h1": "Game news",
        "hub_aciklama": "Verified gaming news from every platform: launches, free games, deals and updates. Every story links to its official source.",
        "hub_not": "Based only on official announcements (PlayStation Blog, Xbox Wire, Nintendo, Epic Games Store, publisher sites). No rumors or leaks.",
        "guncel": "Last updated", "kaynak": "Source", "devam": "Read the full story →", "tum": "All game news →",
        "geri": "← All game news", "kutu": "News from other games", "gta": "GTA VI news →",
        "tur": {"haber": "News", "ucretsiz": "Free", "cikis": "Launch", "indirim": "Deal", "guncelleme": "Update"},
        "locale": "en_US", "feed": "Game news (ctrl-agame.com)",
        "oneri": "This story is also available in English:", "oneri_link": "Read in English",
    },
    "fr": {
        "menu": "Actus jeux", "hub_baslik": "Actus jeux vidéo : PlayStation, Xbox, Nintendo et PC",
        "hub_h1": "Actus jeux vidéo",
        "hub_aciklama": "Des actus jeux vidéo vérifiées sur toutes les plateformes : sorties, jeux gratuits, promos et mises à jour. Chaque info cite sa source officielle.",
        "hub_not": "Uniquement des annonces officielles (PlayStation Blog, Xbox Wire, Nintendo, Epic Games Store, sites des éditeurs). Ni rumeurs ni fuites.",
        "guncel": "Dernière mise à jour", "kaynak": "Source", "devam": "Lire l'article →", "tum": "Toutes les actus jeux →",
        "geri": "← Toutes les actus jeux", "kutu": "Actus des autres jeux", "gta": "Actus GTA VI →",
        "tur": {"haber": "Actu", "ucretsiz": "Gratuit", "cikis": "Sortie", "indirim": "Promo", "guncelleme": "Mise à jour"},
        "locale": "fr_FR", "feed": "Actus jeux (ctrl-agame.com)",
        "oneri": "Cet article existe aussi en français :", "oneri_link": "Lire en français",
    },
    "es": {
        "menu": "Noticias de juegos", "hub_baslik": "Noticias de videojuegos: PlayStation, Xbox, Nintendo y PC",
        "hub_h1": "Noticias de videojuegos",
        "hub_aciklama": "Noticias de videojuegos verificadas de todas las plataformas: lanzamientos, juegos gratis, ofertas y actualizaciones. Cada noticia cita su fuente oficial.",
        "hub_not": "Solo anuncios oficiales (PlayStation Blog, Xbox Wire, Nintendo, Epic Games Store, webs de las editoras). Sin rumores ni filtraciones.",
        "guncel": "Última actualización", "kaynak": "Fuente", "devam": "Leer la noticia →", "tum": "Todas las noticias de juegos →",
        "geri": "← Todas las noticias de juegos", "kutu": "Noticias de otros juegos", "gta": "Noticias de GTA VI →",
        "tur": {"haber": "Noticia", "ucretsiz": "Gratis", "cikis": "Lanzamiento", "indirim": "Oferta", "guncelleme": "Actualización"},
        "locale": "es_ES", "feed": "Noticias de juegos (ctrl-agame.com)",
        "oneri": "Esta noticia también está en español:", "oneri_link": "Leer en español",
    },
}

e = lambda s: html.escape(str(s), quote=True)  # noqa: E731


def tarih_yaz(dil: str, iso: str) -> str:
    y, a, g = (int(x) for x in iso.split("-"))
    if dil == "en":
        return f"{AY['en'][a - 1]} {g}, {y}"
    if dil == "es":
        return f"{g} de {AY['es'][a - 1]} de {y}"
    return f"{g} {AY[dil][a - 1]} {y}"


# ---------------------------------------------------------------- doğrulama
def yukle() -> list[dict]:
    yol = KOK / "data" / "icerik.json"
    veri = json.loads(yol.read_text(encoding="utf-8"))
    hatalar, gorulen = [], set()
    for i, x in enumerate(veri):
        k = x.get("id", f"#{i}")
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", str(x.get("id", ""))):
            hatalar.append(f"{k}: id küçük harf/rakam/tire olmalı")
        if k in gorulen:
            hatalar.append(f"{k}: id tekrar ediyor")
        gorulen.add(k)
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(x.get("tarih", ""))):
            hatalar.append(f"{k}: tarih YYYY-AA-GG olmalı")
        if x.get("tur") not in TUR:
            hatalar.append(f"{k}: tur {TUR} içinden olmalı")
        ks = x.get("kaynaklar") or []
        if not ks or not all(str(s.get("url", "")).startswith("https://") and s.get("ad") for s in ks):
            hatalar.append(f"{k}: en az bir https kaynak (url + ad) gerekli")
        for d in DILLER:
            t = (x.get("diller") or {}).get(d)
            if not t:
                hatalar.append(f"{k}: {d} dili eksik")
                continue
            for alan in ("baslik", "ozet", "metin"):
                if not str(t.get(alan, "")).strip():
                    hatalar.append(f"{k}/{d}: {alan} boş")
            if len(t.get("baslik", "")) > 100:
                hatalar.append(f"{k}/{d}: başlık 100 karakteri aşıyor")
            for et in t.get("etiketler", []):
                if not re.fullmatch(r"#[A-Za-z0-9]+", et):
                    hatalar.append(f"{k}/{d}: etiket '{et}' geçersiz")
    if hatalar:
        print("İÇERİK HATASI:\n  " + "\n  ".join(hatalar))
        sys.exit(1)
    veri.sort(key=lambda x: (x["tarih"], x["id"]), reverse=True)
    return veri


# ---------------------------------------------------------------- yardımcılar
def yaz(yol: pathlib.Path, metin: str) -> bool:
    yol.parent.mkdir(parents=True, exist_ok=True)
    eski = yol.read_text(encoding="utf-8") if yol.exists() else None
    if eski == metin:
        return False
    yol.write_text(metin, encoding="utf-8", newline="\n")
    return True


def sayfa_url(dil: str, oid: str) -> str:
    return f"{SITE}/{KLASOR[dil]}/{oid}.html"


def kart_ad(oid: str, dil: str, tip: str) -> str:
    return f"{KART_KLASOR}/{oid}-{dil}-{tip}." + ("png" if tip == "og" else "jpg")


IG_GUN = 3       # Instagram kartı yalnız son 3 günün haberleri için üretilir (paylaşım penceresi)
IG_SAKLA = 14    # Instagram paylaşınca görseli kendine kopyalar; 14 günden eski kartlar silinir


def ayarlar() -> dict:
    return json.loads((KOK / "sosyal" / "ayarlar.json").read_text(encoding="utf-8"))


def kabuk(dil: str) -> tuple[str, str]:
    """Var olan GTA haber sayfasından afiş+header ve footer'ı alır, bağlantıları köke göre mutlak yapar."""
    kaynak = (KOK / GTA_HABER[dil]).read_text(encoding="utf-8")
    bas = re.search(r'<div class="unofficial".*?</header>', kaynak, re.S).group(0)
    son = re.search(r"<footer>.*?</footer>", kaynak, re.S).group(0)

    def mutlak(m: re.Match) -> str:
        h = m.group(1)
        if re.match(r"(https?:|/|#|mailto:)", h):
            return m.group(0)
        if h in ("./", ""):
            return f'href="{ONEK[dil]}"'
        return f'href="{ONEK[dil]}{h}"'

    bas = re.sub(r'href="([^"]*)"', mutlak, bas)
    son = re.sub(r'href="([^"]*)"', mutlak, son)
    bas = bas.replace(' aria-current="page"', "")
    bas = re.sub(r'<div class="lang".*?</div>', "{{DIL_SECICI}}", bas, flags=re.S)
    bas = bas.replace(f'href="/{HUB[dil]}"', f'href="/{HUB[dil]}" aria-current="page"')
    return bas, son


def dil_secici(dil: str, yollar: dict[str, str]) -> str:
    etiket = "Dil / Language" if dil == "tr" else "Language" if dil == "en" else "Langue" if dil == "fr" else "Idioma"
    parcalar = []
    for d in DILLER:
        cur = ' aria-current="true"' if d == dil else ""
        parcalar.append(f'<a href="/{yollar[d]}" hreflang="{d}" lang="{d}"{cur}>{d.upper()}</a>')
    return f'<div class="lang" aria-label="{etiket}">' + "".join(parcalar) + "</div>"


def bas_kismi(dil, baslik, aciklama, yol, yollar, gorsel, tip="website", ek=""):
    alt = "".join(f'<link rel="alternate" hreflang="{d}" href="{SITE}/{yollar[d]}">\n' for d in DILLER)
    alt += f'<link rel="alternate" hreflang="x-default" href="{SITE}/{yollar["en"]}">\n'
    return f"""<!doctype html>
<html lang="{dil}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(baslik)}</title>
<meta name="description" content="{e(aciklama)}">
<link rel="canonical" href="{SITE}/{yol}">
{alt}<meta property="og:title" content="{e(baslik)}">
<meta property="og:description" content="{e(aciklama)}">
<meta property="og:type" content="{tip}">
<meta property="og:url" content="{SITE}/{yol}">
<meta property="og:image" content="{SITE}/{gorsel}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:locale" content="{M[dil]['locale']}">
<meta property="og:site_name" content="{GORUNEN}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(baslik)}">
<meta name="twitter:description" content="{e(aciklama)}">
<meta name="twitter:image" content="{SITE}/{gorsel}">
<link rel="alternate" type="application/rss+xml" title="{e(M[dil]['feed'])}" href="{SITE}/{FEED[dil]}">
<meta name="theme-color" content="#0f0b1a">
<meta name="color-scheme" content="dark">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="/style.css">
<script async src="https://www.googletagmanager.com/gtag/js?id=G-67FMKX5E05"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());gtag('config','G-67FMKX5E05');</script>
<script src="/anma.js" defer></script>
{ek}</head>
<body>
<a class="skip" href="#main">{ {'tr': 'İçeriğe geç', 'en': 'Skip to content', 'fr': 'Aller au contenu', 'es': 'Ir al contenido'}[dil] }</a>
"""


# Sosyal ağdan gelen ziyaretçiyi tarayıcı diline yönlendirir (yalnız utm_source varsa, bir kez).
YONLENDIR = """<script>(function(){try{var q=new URLSearchParams(location.search);if(!q.has('utm_source')||q.has('r'))return;
var s=%s,h=document.documentElement.lang,l=(navigator.languages&&navigator.languages.length?navigator.languages:[navigator.language||'']);
for(var i=0;i<l.length;i++){var d=String(l[i]).slice(0,2).toLowerCase();if(s[d]){if(d!==h){q.set('r','1');location.replace(s[d]+'?'+q.toString()+location.hash);}return;}}}catch(e){}})();</script>
"""


def oge_html(dil: str, x: dict, baglanti: bool) -> str:
    t = x["diller"][dil]
    kay = x["kaynaklar"][0]
    tur = M[dil]["tur"][x["tur"]]
    baslik = f'<a href="/{KLASOR[dil]}/{x["id"]}.html">{e(t["baslik"])}</a>' if baglanti else e(t["baslik"])
    return (
        f'    <li id="{x["id"]}"><time datetime="{x["tarih"]}">{tarih_yaz(dil, x["tarih"])}</time>'
        f'<span class="oh-tur"><span lang="en">{e(x["oyun"])}</span> · {e(tur)}</span><strong>{baslik}</strong>\n'
        f'      <p>{e(t["ozet"])}</p>\n'
        f'      <p class="src">{M[dil]["kaynak"]}: <a href="{e(kay["url"])}" rel="noopener">{e(kay["ad"])}, {tarih_yaz(dil, kay.get("tarih", x["tarih"]))}</a></p></li>\n'
    )


# ---------------------------------------------------------------- sayfalar
def hub_sayfasi(dil: str, veri: list[dict], kabuklar) -> str:
    m = M[dil]
    bas, son = kabuklar[dil]
    bas = bas.replace("{{DIL_SECICI}}", dil_secici(dil, HUB))
    gorsel = kart_ad(veri[0]["id"], dil, "og") if veri else "og.png"
    son_tarih = veri[0]["tarih"] if veri else "2026-11-14"
    liste = "".join(oge_html(dil, x, True) for x in veri)
    return (
        bas_kismi(dil, m["hub_baslik"], m["hub_aciklama"], HUB[dil], HUB, gorsel)
        + bas
        + f"""

<main id="main"><section><div class="wrap">
  <h1>{e(m['hub_h1'])}</h1>
  <p class="updated">{m['guncel']}: {tarih_yaz(dil, son_tarih)}. {e(m['hub_not'])}</p>
  <ul class="tl oh-liste">
{liste}  </ul>
  <p><a href="/{GTA_HABER[dil]}">{m['gta']}</a></p>
</div></section></main>

"""
        + son
        + "\n</body>\n</html>\n"
    )


def haber_sayfasi(dil: str, x: dict, kabuklar) -> str:
    m = M[dil]
    t = x["diller"][dil]
    yollar = {d: f"{KLASOR[d]}/{x['id']}.html" for d in DILLER}
    bas, son = kabuklar[dil]
    bas = bas.replace("{{DIL_SECICI}}", dil_secici(dil, yollar))
    og = kart_ad(x["id"], dil, "og")
    ld = {
        "@context": "https://schema.org", "@type": "NewsArticle", "headline": t["baslik"],
        "description": t["ozet"], "datePublished": x["tarih"], "inLanguage": dil,
        "image": [f"{SITE}/{og}"], "mainEntityOfPage": f"{SITE}/{yollar[dil]}",
        "publisher": {"@type": "Organization", "name": GORUNEN, "url": f"{SITE}/"},
        "isBasedOn": [s["url"] for s in x["kaynaklar"]],
    }
    yon = YONLENDIR % json.dumps({d: "/" + yollar[d] for d in DILLER})
    ek = f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>\n' + yon
    paragraflar = "".join(f"  <p>{e(p.strip())}</p>\n" for p in re.split(r"\n\s*\n", t["metin"]) if p.strip())
    kaynaklar = " · ".join(
        f'<a href="{e(s["url"])}" rel="noopener">{e(s["ad"])}, {tarih_yaz(dil, s.get("tarih", x["tarih"]))}</a>' for s in x["kaynaklar"]
    )
    etiket = " ".join(e(s) for s in t.get("etiketler", []))
    return (
        bas_kismi(dil, f"{t['baslik']} | {m['menu']}", t["ozet"], yollar[dil], yollar, og, "article", ek)
        + bas
        + f"""

<main id="main"><section><div class="wrap oh-haber">
  <p class="oh-yol"><a href="/{HUB[dil]}">{e(m['menu'])}</a> · {e(x['oyun'])} · {e(m['tur'][x['tur']])}</p>
  <h1>{e(t['baslik'])}</h1>
  <p class="updated"><time datetime="{x['tarih']}">{tarih_yaz(dil, x['tarih'])}</time></p>
  <img class="oh-kart" src="/{og}" width="1200" height="630" alt="{e(t['baslik'])}">
  <p class="oh-giris">{e(t['ozet'])}</p>
{paragraflar}  <p class="src">{m['kaynak']}: {kaynaklar}</p>
  <p class="oh-etiket">{etiket}</p>
  <p><a href="/{HUB[dil]}">{m['geri']}</a></p>
</div></section></main>

"""
        + son
        + "\n</body>\n</html>\n"
    )


def rss(dil: str, veri: list[dict]) -> str:
    m = M[dil]
    son = veri[0]["tarih"] if veri else "2026-11-14"
    tarih = lambda iso: format_datetime(datetime.fromisoformat(iso).replace(hour=12, tzinfo=timezone.utc), usegmt=True)  # noqa: E731
    ogeler = []
    for x in veri[:30]:
        t = x["diller"][dil]
        u = sayfa_url(dil, x["id"])
        ogeler.append(
            f"  <item><title>{e(t['baslik'])}</title><link>{u}</link><guid isPermaLink=\"true\">{u}</guid>"
            f"<pubDate>{tarih(x['tarih'])}</pubDate><description>{e(t['ozet'])}</description></item>\n"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n<channel>\n'
        f"  <title>{e(m['feed'])}</title>\n  <link>{SITE}/{HUB[dil]}</link>\n  <description>{e(m['hub_aciklama'])}</description>\n"
        f"  <language>{dil}</language>\n  <lastBuildDate>{tarih(son)}</lastBuildDate>\n"
        f'  <atom:link href="{SITE}/{FEED[dil]}" rel="self" type="application/rss+xml"/>\n'
        + "".join(ogeler)
        + "</channel>\n</rss>\n"
    )


# ---------------------------------------------------------------- yerinde güncellemeler
BAS_IM, SON_IM = "<!-- oyun-haberleri:basla -->", "<!-- oyun-haberleri:bitir -->"


def isaretli_degistir(metin: str, yeni: str, once: str) -> str:
    blok = f"{BAS_IM}\n{yeni}{SON_IM}\n"
    if BAS_IM in metin:
        return re.sub(re.escape(BAS_IM) + r".*?" + re.escape(SON_IM) + r"\n?", lambda _: blok, metin, flags=re.S)
    i = metin.rindex(once)
    return metin[:i] + blok + metin[i:]


def ana_sayfa_kutusu(dil: str, veri: list[dict]) -> None:
    yol = KOK / ("index.html" if dil == "tr" else f"{dil}/index.html")
    m = M[dil]
    ogeler = []
    for x in veri[:4]:
        t = x["diller"][dil]
        ogeler.append(
            f'    <li><time datetime="{x["tarih"]}">{tarih_yaz(dil, x["tarih"])}</time><span class="oh-tur" lang="en">{e(x["oyun"])}</span>'
            f'<strong>{e(t["baslik"])}</strong><p>{e(t["ozet"])} <a href="/{KLASOR[dil]}/{x["id"]}.html">{m["devam"]}</a></p></li>\n'
        )
    kutu = (
        f'<section><div class="wrap">\n  <h2>{e(m["kutu"])}</h2>\n  <ul class="tl oh-liste">\n'
        + "".join(ogeler)
        + f'  </ul>\n  <p><a href="/{HUB[dil]}">{m["tum"]}</a></p>\n</div></section>\n'
    )
    yaz(yol, isaretli_degistir(yol.read_text(encoding="utf-8"), kutu, "</main>"))


def menuye_ekle() -> int:
    """Tüm sayfaların menüsüne (Haberler/News bağlantısından sonra) oyun haberleri bağlantısını ekler."""
    sayi = 0
    for yol in sorted(KOK.rglob("*.html")):
        g = yol.relative_to(KOK).as_posix()
        if g.startswith(("_", ".", KART_KLASOR + "/")):
            continue
        dil = g.split("/")[0] if g.split("/")[0] in ("en", "fr", "es") else "tr"
        metin = yol.read_text(encoding="utf-8")
        if "<header>" not in metin or f'href="/{HUB[dil]}"' in metin.split("</header>")[0]:
            continue
        haber = "haberler.html" if dil == "tr" else "news.html"
        m = re.search(r'(\n(\s*)<li><a class="l" href="[^"]*' + re.escape(haber) + r'"[^>]*>[^<]*</a></li>)', metin)
        if not m:
            continue
        li = f'\n{m.group(2)}<li><a class="l" href="/{HUB[dil]}">{e(M[dil]["menu"])}</a></li>'
        metin = metin[: m.end()] + li + metin[m.end():]
        yaz(yol, metin)
        sayi += 1
    return sayi


def site_haritasi(veri: list[dict]) -> None:
    yol = KOK / "sitemap.xml"
    satirlar = []

    def grup(yollar: dict[str, str], tarih: str):
        alt = "".join(f'<xhtml:link rel="alternate" hreflang="{d}" href="{SITE}/{yollar[d]}"/>' for d in DILLER)
        for d in DILLER:
            satirlar.append(f"  <url><loc>{SITE}/{yollar[d]}</loc><lastmod>{tarih}</lastmod>{alt}</url>\n")

    if veri:
        grup(HUB, veri[0]["tarih"])
    for x in veri:
        grup({d: f"{KLASOR[d]}/{x['id']}.html" for d in DILLER}, x["tarih"])
    yaz(yol, isaretli_degistir(yol.read_text(encoding="utf-8"), "".join(satirlar), "</urlset>"))


# ---------------------------------------------------------------- kartlar
def kartlar(veri: list[dict]) -> int:
    from PIL import Image, ImageDraw, ImageFont

    def font(kalin: bool, boy: int):
        adaylar = (
            ["C:/Windows/Fonts/segoeuib.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
            if kalin else ["C:/Windows/Fonts/segoeui.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
        )
        for a in adaylar:
            if pathlib.Path(a).exists():
                return ImageFont.truetype(a, boy)
        raise SystemExit("Yazı tipi bulunamadı (Segoe UI veya DejaVu Sans gerekli).")

    def sar(ciz, metin, f, gen):
        satir, satirlar = "", []
        for k in metin.split():
            dene = (satir + " " + k).strip()
            if ciz.textlength(dene, font=f) <= gen:
                satir = dene
            else:
                if satir:
                    satirlar.append(satir)
                satir = k
        if satir:
            satirlar.append(satir)
        return satirlar

    def sigdir(ciz, metin, kalin, buyuk, kucuk, gen, en_cok):
        for boy in range(buyuk, kucuk - 1, -2):
            f = font(kalin, boy)
            s = sar(ciz, metin, f, gen)
            if len(s) <= en_cok:
                return f, s, boy
        f = font(kalin, kucuk)
        s = sar(ciz, metin, f, gen)[:en_cok]
        s[-1] = s[-1].rstrip(".,;:") + "…"
        return f, s, kucuk

    def zemin(W, H):
        img = Image.new("RGB", (W, H), (13, 10, 24))
        px = ImageDraw.Draw(img)
        for y in range(H):  # üstten alta koyu mor geçiş
            r = y / H
            px.line([(0, y), (W, y)], fill=(int(33 - 20 * r), int(26 - 16 * r), int(59 - 35 * r)))
        for x in range(W):  # üst şerit: pembe → turuncu → sarı
            r = x / W
            if r < .55:
                c = tuple(int(a + (b - a) * r / .55) for a, b in zip((255, 79, 163), (255, 162, 76)))
            else:
                c = tuple(int(a + (b - a) * (r - .55) / .45) for a, b in zip((255, 162, 76), (255, 211, 110)))
            px.line([(x, 0), (x, 11)], fill=c)
        return img

    def ciz_kart(x, dil, W, H, ozetli):
        t = x["diller"][dil]
        img = zemin(W, H)
        c = ImageDraw.Draw(img)
        P = 72 if W >= 1200 else 80
        gen = W - 2 * P
        etiket = f"{x['oyun']}  ·  {M[dil]['tur'][x['tur']]}".upper()
        fe = font(True, 30 if not ozetli else 34)
        while c.textlength(etiket, font=fe) > gen and fe.size > 20:
            fe = font(True, fe.size - 2)
        if ozetli:
            fb, sb, bb = sigdir(c, t["baslik"], True, 88, 54, gen, 6)
            fo, so, bo = sigdir(c, t["ozet"], False, 42, 32, gen, 5)
        else:
            fb, sb, bb = sigdir(c, t["baslik"], True, 72, 44, gen, 4)
            fo, so, bo = None, [], 0
        # içerik bloğunu üst şerit ile alt bilgi arasında dikey ortala
        blok = fe.size + 34 + len(sb) * int(bb * 1.18) + ((26 + len(so) * int(bo * 1.3)) if so else 0)
        ust, alt = 12 + P // 2, H - P - 44 - 26 - P // 2
        y = max(P, ust + (alt - ust - blok) // 2) if ozetli else P + 8
        c.text((P, y), etiket, font=fe, fill=(255, 162, 76))
        y += fe.size + 34
        for s in sb:
            c.text((P, y), s, font=fb, fill=(246, 242, 255))
            y += int(bb * 1.18)
        if so:
            y += 26
            for s in so:
                c.text((P, y), s, font=fo, fill=(185, 174, 214))
                y += int(bo * 1.3)
        yb = H - P - 44
        c.line([(P, yb - 26), (W - P, yb - 26)], fill=(58, 47, 102), width=2)
        fs = font(True, 34)
        c.text((P, yb), GORUNEN, font=fs, fill=(46, 230, 200))
        sag = f"{tarih_yaz(dil, x['tarih'])}  ·  {M[dil]['kaynak']}: {x['kaynaklar'][0]['ad']}"
        fk = font(False, 28)
        while c.textlength(sag, font=fk) > gen - c.textlength(GORUNEN, font=fs) - 40 and fk.size > 18:
            fk = font(False, fk.size - 2)
        c.text((W - P - c.textlength(sag, font=fk), yb + 6), sag, font=fk, fill=(185, 174, 214))
        return img

    def kaydet(img, yol, tip):
        tmp = yol.with_name(yol.stem + ".tmp" + yol.suffix)
        if tip == "og":  # 128 renkli PNG: metin kartı için ~15 KB, depo şişmez
            img.quantize(128, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE).save(tmp, "PNG", optimize=True)
        else:            # Instagram yalnız JPEG kabul eder
            img.save(tmp, "JPEG", quality=85, optimize=True, subsampling=2)
        if yol.exists() and yol.read_bytes() == tmp.read_bytes():
            tmp.unlink()
            return 0
        tmp.replace(yol)
        return 1

    from datetime import date, timedelta
    bugun = date.today()
    ig_diller = [d for d in DILLER if ayarlar()["hesaplar"].get(d, {}).get("instagram")]
    (KOK / KART_KLASOR).mkdir(exist_ok=True)
    gerekli, yeni = set(), 0
    for x in veri:
        yas = (bugun - date.fromisoformat(x["tarih"])).days
        for dil in DILLER:
            yol = KOK / kart_ad(x["id"], dil, "og")
            gerekli.add(yol.name)
            yeni += kaydet(ciz_kart(x, dil, 1200, 630, False), yol, "og")
            if dil in ig_diller and yas <= IG_SAKLA:
                yol = KOK / kart_ad(x["id"], dil, "ig")
                gerekli.add(yol.name)
                if yas <= IG_GUN or yol.exists():
                    yeni += kaydet(ciz_kart(x, dil, 1080, 1350, True), yol, "ig")
    silinen = 0
    for f in (KOK / KART_KLASOR).iterdir():
        if f.name not in gerekli:
            f.unlink()
            silinen += 1
    return yeni, silinen


# ---------------------------------------------------------------- ana akış
def main() -> None:
    veri = yukle()
    eklenen_menu = menuye_ekle()
    kabuklar = {d: kabuk(d) for d in DILLER}
    degisen = 0
    for d in DILLER:
        degisen += yaz(KOK / HUB[d], hub_sayfasi(d, veri, kabuklar))
        degisen += yaz(KOK / FEED[d], rss(d, veri))
        for x in veri:
            degisen += yaz(KOK / KLASOR[d] / f"{x['id']}.html", haber_sayfasi(d, x, kabuklar))
        ana_sayfa_kutusu(d, veri)
    site_haritasi(veri)
    yeni_kart, silinen = kartlar(veri)
    print(f"Tamam: {len(veri)} haber, {degisen} sayfa/RSS değişti, {yeni_kart} kart yazıldı, {silinen} eski kart silindi, menüye {eklenen_menu} sayfada bağlantı eklendi.")


if __name__ == "__main__":
    main()
