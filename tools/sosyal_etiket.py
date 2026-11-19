"""Keşfe uygun sosyal etiket üretimi (Instagram hashtag'leri, YouTube anahtar kelimeleri).

Saf fonksiyonlar: ağ yok, model yok. Kaynak: haber öğesi (oyun adı, platform, tür, isteğe bağlı
yazar etiketleri) ve data/oyunlar.json. Dosya yoksa ya da bozuksa boş listeyle çalışır; paylaşım
bu yüzden asla kırılmaz.

Özel yazım gereken oyunlar (Roma rakamlı adlar vb.) aşağıdaki OZEL tablosuna eklenir: anahtar oyun adının
küçük harfli hâli, değer en çok iki etiketlik liste (rakamlı biçim önce).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import sosyal_kuyruk as sk

OYUNLAR_YOLU = Path(__file__).resolve().parent.parent / "data" / "oyunlar.json"

OZEL = {
    "gta vi": ["#GTA6", "#GTAVI"],
    "grand theft auto vi": ["#GTA6", "#GTAVI"],
    "crusader kings iii": ["#CK3", "#CrusaderKingsIII"],
    "final fantasy xiv": ["#FFXIV", "#FinalFantasyXIV"],
    "the legend of zelda: ocarina of time": ["#Zelda", "#OcarinaOfTime"],
}

UZUN_AD_SINIRI = 24

KONU = {
    "ucretsiz": {"tr": "#BedavaOyun", "en": "#FreeGames", "de": "#GratisSpiele", "fr": "#JeuxGratuits",
                 "es": "#JuegosGratis", "nl": "#GratisGames", "zh": "#免费游戏"},
    "indirim": {"tr": "#OyunFırsatları", "en": "#GameDeals", "de": "#GamingDeals", "fr": "#BonsPlansJeux",
                "es": "#OfertasJuegos", "nl": "#GameDeals", "zh": "#游戏折扣"},
    "haber": {"tr": "#OyunHaberleri", "en": "#GamingNews", "de": "#GamingNews", "fr": "#ActuJeuxVideo",
              "es": "#NoticiasGaming", "nl": "#GameNieuws", "zh": "#游戏新闻"},
}
GENEL = {"tr": "#Oyun", "en": "#Gaming", "de": "#Gaming", "nl": "#Gaming", "fr": "#JeuxVideo",
         "es": "#Videojuegos", "zh": "#游戏"}

# YouTube anahtar kelimeleri: "<oyun> haber" son eki ve iki genel ifade
HABER_SOZU = {"tr": "haber", "en": "news", "de": "News", "fr": "actualités", "es": "noticias",
              "nl": "nieuws", "zh": "新闻"}
GENEL_IFADE = {"tr": ["oyun haberleri", "oyun gündemi"], "en": ["gaming news", "video game news"],
               "de": ["Gaming News", "Videospiel News"], "fr": ["actualité jeux vidéo", "jeux vidéo"],
               "es": ["noticias de videojuegos", "noticias gaming"], "nl": ["game nieuws", "gaming nieuws"],
               "zh": ["游戏新闻", "游戏资讯"]}
MARKA = "CTRL+A GAME"

_YAZAR_DESEN = re.compile(r"#[\w]+")
_onbellek: dict = {}


def onbellek_temizle() -> None:
    _onbellek.clear()


def oyunlar() -> list:
    """data/oyunlar.json kayıtları; bir kez okunur. Dosya yok/bozuksa boş liste."""
    yol = OYUNLAR_YOLU
    if yol not in _onbellek:
        try:
            veri = json.loads(Path(yol).read_text(encoding="utf-8"))
            _onbellek[yol] = [o for o in veri if isinstance(o, dict)] if isinstance(veri, list) else []
        except (OSError, ValueError):
            _onbellek[yol] = []
    return _onbellek[yol]


def kayit_bul(ad: str) -> dict | None:
    ad = str(ad or "").casefold().strip()
    if not ad:
        return None
    for o in oyunlar():
        adlar = [o.get("ad", ""), *(o.get("eslesme") or [])]
        if ad in {str(a).casefold().strip() for a in adlar}:
            return o
    return None


def _birlestir(metin: str) -> str:
    return "".join(c for c in str(metin) if c.isalnum())


def _etiket(metin: str) -> str | None:
    govde = _birlestir(metin)
    return "#" + govde if govde and not govde.isdigit() else None


def oyun_etiketleri(x: dict) -> list[str]:
    """Oyun adından etiketler (en çok iki): ana etiket, varsa özel/rakamlı ya da kısa ad biçimi."""
    ad = str(x.get("oyun") or "").strip()
    if not ad:
        return []
    sonuc: list[str] = []

    def ekle(t):
        if t and t.casefold() not in {s.casefold() for s in sonuc}:
            sonuc.append(t)

    ozel = OZEL.get(ad.casefold())
    if ozel:
        for t in ozel:
            ekle(t)
    else:
        govde = ad
        if ":" in ad and len(_birlestir(ad)) > UZUN_AD_SINIRI:
            govde = ad.split(":")[0]
        ekle(_etiket(govde))
    kayit = kayit_bul(ad)
    if kayit:
        kisa = str(kayit.get("kisa") or "").strip()
        if kisa and _birlestir(kisa).casefold() != _birlestir(ad).casefold():
            ekle(_etiket(kisa))
    return sonuc[:2]


def yazar_etiketleri(dil: str, x: dict) -> list[str]:
    genel = {t.casefold() for t in sk.SABLON.get(dil, {}).get("etiket", "").split()}
    sonuc, gorulen = [], set()
    for t in ((x.get("diller") or {}).get(dil) or {}).get("etiketler", []) or []:
        if isinstance(t, str) and _YAZAR_DESEN.fullmatch(t) and t.casefold() not in genel and t.casefold() not in gorulen:
            sonuc.append(t)
            gorulen.add(t.casefold())
    return sonuc


def _platform_adi(p: str) -> tuple[str, str] | None:
    """Platform listesi öğesi için (etiket, ad) ya da None."""
    s = str(p).casefold().strip()
    if "ps5" in s or (s.startswith("playstation") and "4" not in s):
        return "#PS5", "PS5"
    if s.startswith("xbox"):
        return "#Xbox", "Xbox"
    if "switch 2" in s:
        return "#NintendoSwitch2", "Nintendo Switch 2"
    if "switch" in s:
        return "#NintendoSwitch", "Nintendo Switch"
    if s == "pc":
        return "#PCGaming", "PC"
    if s in ("mobil", "mobile", "android", "ios"):
        return "#MobileGaming", "Mobile"
    return None


def platform_etiketi(x: dict) -> str | None:
    for p in x.get("platform") or []:
        r = _platform_adi(p)
        if r:
            return r[0]
    return None


def konu_etiketi(dil: str, x: dict) -> str:
    tur = x.get("tur")
    if x.get("sosyal_tur") == "ucretsiz":
        tur = "ucretsiz"
    elif x.get("sosyal_tur") == "firsat":
        tur = "indirim"
    return KONU.get(tur, KONU["haber"]).get(dil) or KONU["haber"]["en"]


def hashtagler(dil: str, x: dict, sinir: int) -> list[str]:
    """En çok `sinir` etiket. Kırpma önceliği: oyun (en çok 2), 1 yazar etiketi, platform, konu, genel,
    kalan yazar etiketleri. Çıktı sırası: oyun, yazar, platform, konu, genel (büyük-küçük harf duyarsız tekil).
    Instagram için sinir=5, YouTube açıklaması için 3."""
    oyun = oyun_etiketleri(x)
    yazar = yazar_etiketleri(dil, x)
    plat = platform_etiketi(x)
    konu = konu_etiketi(dil, x)
    genel = GENEL.get(dil, GENEL["en"])
    # (kategori sırası, etiket) çiftleri öncelik sırasında
    oncelik = [(0, t) for t in oyun] + [(1, t) for t in yazar[:1]] + [(2, plat)] + [(3, konu)] + [(4, genel)] \
        + [(1, t) for t in yazar[1:]]
    secilen, gorulen = [], set()
    for kat, t in oncelik:
        if not t or len(secilen) >= sinir or t.casefold() in gorulen:
            continue
        secilen.append((kat, t))
        gorulen.add(t.casefold())
    secilen.sort(key=lambda p: p[0])  # kararlı sıralama: kategori içinde öncelik sırası korunur
    return [t for _, t in secilen]


def yt_anahtar_kelimeler(dil: str, x: dict) -> list[str]:
    """YouTube snippet.tags için düz kelimeler (# yok, <>, yok); eleman başına +1 ile toplam ≤ 400."""
    ad = str(x.get("oyun") or "").strip()
    kayit = kayit_bul(ad)
    ham: list[str] = []
    if ad:
        ham.append(ad)
        if kayit:
            kisa = str(kayit.get("kisa") or "").strip()
            if kisa:
                ham.append(kisa)
            diger = [str(a).strip() for a in (kayit.get("eslesme") or [])
                     if str(a).strip() and str(a).strip().casefold() not in (ad.casefold(), kisa.casefold())]
            ham += diger[:4]
        ham.append(f"{ad} {HABER_SOZU.get(dil, HABER_SOZU['en'])}")
    ham += [r[1] for r in (_platform_adi(p) for p in (x.get("platform") or [])) if r]
    ham += GENEL_IFADE.get(dil, GENEL_IFADE["en"])
    ham += [t.lstrip("#") for t in yazar_etiketleri(dil, x)]
    ham.append(MARKA)
    sonuc, gorulen, toplam = [], set(), 0
    for e in ham:
        e = re.sub(r"[<>,#]", "", e).strip()
        if not e or e.casefold() in gorulen or toplam + len(e) + 1 > 400:
            continue
        sonuc.append(e)
        gorulen.add(e.casefold())
        toplam += len(e) + 1
    return sonuc
