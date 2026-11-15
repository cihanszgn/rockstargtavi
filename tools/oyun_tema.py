"""Oyun temaları: her oyunun merkez ve rehber sayfasını giydiren el yapımı tema kaydı.

Kabuk (üst çubuk, alt bilgi, arama) her sayfada aynıdır; tema yalnız <main> gövdesini giydirir.
Her tema şunları seçer:
  duzen  : kahraman (hero) yerleşimi; amblem SVG'si, arka plan motifi ve bölüm ayracı da buna bağlıdır
  yazi   : başlık yazı tipi (fonts/oyun/*.woff2, hepsi OFL; lisanslar fonts/oyun/lisans/)
  koyu / acik : renkler (zemin, yuzey, cizgi, yazi, soluk, vurgu, vurgu2, vurgu_yazi); AA karşıtlık derlemede denetlenir
  kutu, adim, tablo, hareket : ipucu/uyarı kutusu, adım numarası, tablo ve kaydırma girişi karakteri
  isaret : h2 başlıklarının önündeki süs; ek : yalnız bu temaya özel CSS ("&" tema kökü yerine geçer)
Telif sınırı: logo, ekran görüntüsü, karakter çizimi ve resmî yazı tipi yok; yalnız özgün soyut geometri.
Yeni tema eklemek: TEMALAR'a oyun kimliğiyle (data/oyunlar.json "id") bir kayıt ekle; temasız oyun
otomatik varsayılan tema alır (renk kimlikten, düzen türden türetilir). Ayrıntı: README "Oyun temaları".
"""
from __future__ import annotations

import hashlib
import math
import pathlib
import urllib.parse

KOK = pathlib.Path(__file__).resolve().parent.parent
TEMEL_CSS = pathlib.Path(__file__).resolve().parent / "oyun_tema_temel.css"

# yazı tipi anahtarı -> (aile adı, dosya, ağırlık)
YAZILAR = {
    "cinzel": ("Cinzel O", "cinzel", 700), "pirata-one": ("Pirata One O", "pirata-one", 400),
    "marcellus-sc": ("Marcellus SC O", "marcellus-sc", 400), "uncial": ("Uncial Antiqua O", "uncial", 400),
    "grenze-gotisch": ("Grenze Gotisch O", "grenze-gotisch", 700), "philosopher": ("Philosopher O", "philosopher", 700),
    "chakra-petch": ("Chakra Petch O", "chakra-petch", 700), "russo-one": ("Russo One O", "russo-one", 400),
    "saira-stencil": ("Saira Stencil O", "saira-stencil", 400), "oswald": ("Oswald O", "oswald", 600),
    "baloo": ("Baloo O", "baloo", 800), "bungee": ("Bungee O", "bungee", 400), "pixelify": ("Pixelify O", "pixelify", 600),
    "teko": ("Teko O", "teko", 600), "barlow-condensed": ("Barlow Condensed O", "barlow-condensed", 700),
    "monoton": ("Monoton O", "monoton", 400), "archivo": ("Archivo", "", 800),
}


def P(zemin, yuzey, cizgi, yazi, soluk, vurgu, vurgu2, vurgu_yazi):
    return {"zemin": zemin, "yuzey": yuzey, "cizgi": cizgi, "yazi": yazi, "soluk": soluk,
            "vurgu": vurgu, "vurgu2": vurgu2, "vurgu_yazi": vurgu_yazi}


# ---------------------------------------------------------------- el yapımı temalar
TEMALAR: dict[str, dict] = {
    "world-of-warcraft": dict(
        not_="Fantastik: altın ve gece mavisi, rün çemberli arma, parşömen dokusu, Roma rakamlı adımlar.",
        yazi="cinzel", buyuk=False, aralik=".03em", duzen="orta", kutu="parsomen", adim="roma", tablo="sus",
        hareket="yavas", isaret='"\\2756"',
        koyu=P("#0B1222", "#121C33", "#2B3A5C", "#F1E9D6", "#B9B09C", "#E2B65C", "#7F9BE0", "#1A1206"),
        acik=P("#F3EAD6", "#FBF5E8", "#D7C6A0", "#2A1F0E", "#5E4F33", "#82550C", "#24427E", "#FFF8E8"),
        ek="& .o-h1{text-shadow:0 2px 0 rgba(0,0,0,.25)}& .o-bolum h2{border-bottom:1px solid var(--o-cizgi);padding-bottom:.35em}",
    ),
    "knight-online": dict(
        not_="Orta çağ: çelik ve kızıl, armalı kalkan, sancak şeritleri, perçinli çelik levha kutular.",
        yazi="pirata-one", buyuk=False, aralik=".02em", duzen="kalkan", kutu="percin", adim="kalkan", tablo="celik",
        hareket="hucum", isaret='"\\25C6"',
        koyu=P("#0E1013", "#171B20", "#343B45", "#ECEEF1", "#A9B0BA", "#F0505A", "#A9B6C8", "#17060A"),
        acik=P("#ECEEF1", "#FFFFFF", "#C5CBD3", "#15181C", "#4A525C", "#A3121D", "#3D4A5C", "#FFFFFF"),
        ek="& .o-h1{font-size:clamp(2.4rem,1.6rem + 3vw,4rem)}",
    ),
    "rise-online": dict(
        not_="Şafak: bronz ve deniz yeşili, ufuktan doğan güneş ışınları, yaldızlı ince çizgiler.",
        yazi="cinzel", buyuk=True, aralik=".08em", duzen="safak", kutu="yaldiz", adim="halka", tablo="sus",
        hareket="yavas", isaret='"\\2600"',
        koyu=P("#0C1416", "#132024", "#2B4247", "#EEF3F1", "#A6B9B6", "#F0A04B", "#3FC1B0", "#1A0F04"),
        acik=P("#F5EFE6", "#FFFBF5", "#E0D3BF", "#1B2426", "#4F5D5F", "#924A08", "#0E6E63", "#FFFFFF"),
        ek="",
    ),
    "metin2": dict(
        not_="Doğu fantezisi: yeşim ve kızıl, dikili taş, dalga pulları, kırmızı mühür kutular.",
        yazi="marcellus-sc", buyuk=False, aralik=".04em", duzen="yazit", kutu="muhur", adim="muhur", tablo="murekkep",
        hareket="murekkep", isaret='"\\25A3"',
        koyu=P("#0D1110", "#161D1B", "#2E3B37", "#ECEFE8", "#A8B3AB", "#4FC08D", "#EF6A63", "#06140E"),
        acik=P("#F2EEE3", "#FBF8F0", "#D8D0BC", "#1A1D1B", "#50574F", "#1D6B4A", "#A8231D", "#FFFFFF"),
        ek="",
    ),
    "league-of-legends": dict(
        not_="Üç koridorlu harita: altın ve turkuaz, altıgen mücevher, köşegen koridor çizgileri.",
        yazi="marcellus-sc", buyuk=True, aralik=".06em", duzen="serit", kutu="cerceve", adim="altigen", tablo="altin",
        hareket="kayma", isaret='"\\2B21"',
        koyu=P("#07121A", "#0D1D28", "#1F3A48", "#E9F1F2", "#9FB5BC", "#C8AA6E", "#2FC6D6", "#140F05"),
        acik=P("#EEF3F3", "#FFFFFF", "#C7D6D8", "#0D1B22", "#44585F", "#7A5A1C", "#0B6670", "#FFFFFF"),
        ek="",
    ),
    "path-of-exile-2": dict(
        not_="Kül ve kehribar: yetenek ağacını andıran takımyıldız düğümleri, aşınmış taş kutular.",
        yazi="uncial", buyuk=False, aralik=".01em", duzen="yildiz", kutu="tas", adim="dugum", tablo="kul",
        hareket="murekkep", isaret='"\\2726"',
        koyu=P("#0E0C0A", "#181512", "#3A322A", "#EDE6DA", "#B0A595", "#E29545", "#9DB0C4", "#170B02"),
        acik=P("#EFE9DF", "#FAF6EF", "#D3C7B4", "#1F1A14", "#564B3D", "#8A470B", "#3E5468", "#FFFFFF"),
        ek="",
    ),
    "diablo-4": dict(
        not_="Gotik: kan kırmızısı ve kemik, sivri kemerli pencere, diken dokusu, karanlıkta açılan bölümler.",
        yazi="grenze-gotisch", buyuk=False, aralik=".01em", duzen="gotik", kutu="gotik", adim="roma-halka", tablo="kan",
        hareket="karanlik", isaret='"\\2720"',
        koyu=P("#0B0607", "#160C0E", "#3A1D21", "#F0E6E2", "#BAA6A2", "#F0505C", "#CFAE7A", "#14040A"),
        acik=P("#F1E9E4", "#FBF6F2", "#DCC9C1", "#1C0F10", "#5A4446", "#8E0F21", "#6B4F23", "#FFFFFF"),
        ek="& .o-h1{font-size:clamp(2.6rem,1.6rem + 3.6vw,4.6rem);line-height:1.02}",
    ),
    "genshin-impact": dict(
        not_="Gökyüzü: altın ve gök mavisi, dört köşeli pusula yıldızı, yörünge halkaları, hafif süzülen girişler.",
        yazi="philosopher", buyuk=False, aralik=".02em", duzen="gok", kutu="bulut", adim="yildiz", tablo="hafif",
        hareket="suzulme", isaret='"\\2727"',
        koyu=P("#0C1426", "#142039", "#2C3D63", "#F2F4FA", "#AEB8CF", "#F3CF7A", "#7FD3F7", "#1C1404"),
        acik=P("#EEF5FB", "#FFFFFF", "#CADCEB", "#14213A", "#47566F", "#7E590B", "#0F5F8C", "#FFFFFF"),
        ek="",
    ),
    "valorant": dict(
        not_="Taktik: kırmızı ve kömür, keskin açılı kesikler, taktik ızgara, paralelkenar adım numaraları.",
        yazi="chakra-petch", buyuk=True, aralik=".04em", duzen="acili", kutu="kesik", adim="kesik", tablo="izgara",
        hareket="kesik", isaret='"//"',
        koyu=P("#0F1115", "#181B21", "#323741", "#ECE8E1", "#A9ABB0", "#FF5A63", "#ECE8E1", "#1A0507"),
        acik=P("#F1EEE9", "#FFFFFF", "#D3CEC6", "#111317", "#4B4F57", "#C1121F", "#111317", "#FFFFFF"),
        ek="& .o-h1{font-style:italic;letter-spacing:.02em}",
    ),
    "overwatch": dict(
        not_="İyimser gelecek: turuncu, beyaz ve gök mavisi, bal peteği altıgenler, yuvarlak köşeli paneller.",
        yazi="russo-one", buyuk=True, aralik=".03em", duzen="panel", kutu="panel", adim="altigen", tablo="hafif",
        hareket="pop", isaret='"\\2B22"',
        koyu=P("#101722", "#172231", "#2E4058", "#F4F6F9", "#ADB9C8", "#FF9A3C", "#5FB8FF", "#1D0F02"),
        acik=P("#F3F6FA", "#FFFFFF", "#D0DAE6", "#142034", "#475569", "#A84A00", "#1F5FA8", "#FFFFFF"),
        ek="",
    ),
    "halo-campaign-evolved": dict(
        not_="Bilimkurgu: zeytin yeşili zırh ve vizör camgöbeği, halka dünya yayı, HUD köşe çerçeveleri, tarama çizgileri.",
        yazi="chakra-petch", buyuk=True, aralik=".12em", duzen="hud", kutu="hud", adim="hud", tablo="izgara",
        hareket="tarama", isaret='"\\25B8"',
        koyu=P("#0B110F", "#121B18", "#2A3A34", "#E7EFEA", "#A3B4AB", "#9AD65C", "#4FD8E8", "#0B1404"),
        acik=P("#EDF1EC", "#FFFFFF", "#CBD5CC", "#121A16", "#48554E", "#3D6B12", "#0B6874", "#FFFFFF"),
        ek="& .o-h1{font-weight:700}",
    ),
    "marathon": dict(
        not_="Grafik afiş: asit yeşili ve siyah, İsviçre ızgarası, kayıt işaretleri, barkod şeritleri, dev başlık.",
        yazi="archivo", buyuk=True, aralik="-.02em", duzen="afis", kutu="afis", adim="afis", tablo="afis",
        hareket="kesik", isaret='"\\25A0"',
        koyu=P("#0A0A0A", "#141414", "#2E2E2E", "#F2F2EE", "#ABABA4", "#C8FF1A", "#FF6FE0", "#0A0A0A"),
        acik=P("#F2F2EC", "#FFFFFF", "#CFCFC6", "#0A0A0A", "#4D4D47", "#3A6300", "#A3127F", "#FFFFFF"),
        ek="& .o-h1{font-stretch:125%;font-weight:800;font-size:clamp(2.6rem,1.4rem + 5vw,5.6rem);line-height:.92}",
    ),
    "counter-strike-2": dict(
        not_="Askerî şablon: turuncu ve gri, nişangâh geometrisi, tehlike şeritli etiket kutuları, damga adımlar.",
        yazi="saira-stencil", buyuk=True, aralik=".05em", duzen="sablon", kutu="etiket", adim="damga", tablo="izgara",
        hareket="ani", isaret='"\\271A"',
        koyu=P("#121416", "#1B1E21", "#383D42", "#ECEDEE", "#A8ADB2", "#F5A524", "#9AAAB8", "#171002"),
        acik=P("#ECEDEE", "#FFFFFF", "#C9CDD1", "#16191C", "#4A5056", "#8F5300", "#3E4C58", "#FFFFFF"),
        ek="",
    ),
    "call-of-duty": dict(
        not_="Gizli brifing: zeytin, manila dosya ve sinyal turuncusu, eş yükselti çizgileri, karartılmış satır süsleri.",
        yazi="oswald", buyuk=True, aralik=".06em", duzen="brifing", kutu="dosya", adim="kod", tablo="dosya",
        hareket="ani", isaret='"\\25B6"',
        koyu=P("#0C0D0A", "#151711", "#33362A", "#E9EADF", "#A9AB9A", "#C4CE62", "#FF7A4D", "#0F1103"),
        acik=P("#ECEBE0", "#F8F7EE", "#CFCCB6", "#15160F", "#4D4E40", "#4F5714", "#A8380C", "#FFFFFF"),
        ek="",
    ),
    "pubg": dict(
        not_="İniş bölgesi: haki ve sinyal sarısı, daralan güvenli alan halkaları, harita koordinat ızgarası, kesik uçuş hattı.",
        yazi="oswald", buyuk=True, aralik=".03em", duzen="bolge", kutu="sandik", adim="koordinat", tablo="harita",
        hareket="dusus", isaret='"\\25CE"',
        koyu=P("#12110D", "#1C1A14", "#3A362A", "#EFEBDF", "#B1AA97", "#F2C230", "#6DB3EE", "#1A1402"),
        acik=P("#EFEADB", "#FBF8EF", "#D6CDB3", "#1B1912", "#504A3A", "#765700", "#1E5F96", "#FFFFFF"),
        ek="",
    ),
    "fortnite": dict(
        not_="Canlı ve eğik: mor, mavi ve sarı, üst üste eğik bloklar, yapıştırma etiket kutular, zıplayan girişler.",
        yazi="baloo", buyuk=False, aralik="0", duzen="egik", kutu="etiket-renk", adim="rozet", tablo="renkli",
        hareket="pop", isaret='"\\26A1"',
        koyu=P("#140E2E", "#1E1641", "#3D2F78", "#F7F4FF", "#BDB3E2", "#FFE14D", "#5FC8FF", "#1D1600"),
        acik=P("#F1EEFF", "#FFFFFF", "#D5CCF5", "#1A1236", "#4C4377", "#6A2BD9", "#0B62B3", "#FFFFFF"),
        ek="& .o-h1{font-size:clamp(2.5rem,1.6rem + 3.6vw,4.6rem);line-height:1}",
    ),
    "roblox": dict(
        not_="Yapı taşları: parlak kırmızı ve mavi, eğik karo ve düğmeli tuğla dokusu, kalın tabela başlık.",
        yazi="bungee", buyuk=True, aralik=".01em", duzen="tugla", kutu="tugla", adim="tugla", tablo="renkli",
        hareket="pop", isaret='"\\25A0"',
        koyu=P("#101318", "#181D25", "#313A48", "#F4F6F8", "#AEB6C2", "#FF6464", "#5AAEFF", "#1A0505"),
        acik=P("#F4F6F8", "#FFFFFF", "#D3D9E1", "#12161C", "#4A5260", "#C4161C", "#0B5CB8", "#FFFFFF"),
        ek="",
    ),
    "minecraft": dict(
        not_="Blok ve piksel: toprak ve çimen yeşili, piksel ızgara, basamaklı kenarlar, adım adım (steps) açılan girişler.",
        yazi="pixelify", buyuk=False, aralik=".01em", duzen="blok", kutu="piksel", adim="piksel", tablo="piksel",
        hareket="adim", isaret='"\\25A0"',
        koyu=P("#14130E", "#1E1C15", "#3D3929", "#EEF0E6", "#B0B3A1", "#7BC144", "#D19C63", "#0C1405"),
        acik=P("#ECF1E2", "#FFFFFF", "#C9D3B6", "#1A1C12", "#4C5140", "#3B6E14", "#7A4B21", "#FFFFFF"),
        ek="",
    ),
    "mobile-legends": dict(
        not_="Arena: lacivert ve altın, merkezden yayılan ışınlar, elmas amblem, enerji çizgili kutular.",
        yazi="russo-one", buyuk=True, aralik=".04em", duzen="arena", kutu="enerji", adim="elmas", tablo="altin",
        hareket="pop", isaret='"\\25C8"',
        koyu=P("#0A1030", "#121A45", "#2B3878", "#F3F5FF", "#B3BBE0", "#FFC845", "#56E0FF", "#1D1400"),
        acik=P("#EEF1FF", "#FFFFFF", "#CDD4F5", "#111A44", "#454F80", "#845900", "#0B5E8C", "#FFFFFF"),
        ek="",
    ),
    "ea-sports-fc": dict(
        not_="Canlı yayın: elektrik yeşili ve gece laciverti, stadyum ışık huzmeleri, biçilmiş çim şeritleri, skor bandı.",
        yazi="teko", buyuk=True, aralik=".02em", duzen="yayin", kutu="skor", adim="skor", tablo="skor",
        hareket="kayma", isaret='"\\25B0"',
        koyu=P("#071318", "#0D1F26", "#1E3B45", "#EAF6F5", "#A0BAB8", "#2BF5A1", "#FFFFFF", "#03140D"),
        acik=P("#EAF4F1", "#FFFFFF", "#C4DDD6", "#0A1A1E", "#3F5856", "#00704A", "#0A3D57", "#FFFFFF"),
        ek="& .o-h1{font-size:clamp(2.8rem,1.8rem + 4vw,5.2rem);line-height:.95}",
    ),
    "football-manager-27": dict(
        not_="Taktik tahtası: saha yeşili, tebeşir beyazı ve işaretleyici sarısı, saha çizgileri, diziliş noktaları.",
        yazi="barlow-condensed", buyuk=True, aralik=".04em", duzen="saha", kutu="pano", adim="forma", tablo="pano",
        hareket="kayma", isaret='"\\25CF"',
        koyu=P("#0E1A14", "#15251D", "#2E4A3B", "#F1F5EE", "#A9BBAE", "#E9D86A", "#8FD3A8", "#1A1604"),
        acik=P("#EEF2EA", "#FFFFFF", "#CBD8C8", "#13201A", "#46574C", "#1F6B3A", "#6E5A00", "#FFFFFF"),
        ek="",
    ),
    "gta-6": dict(
        not_="Neon gün batımı: pembe, turuncu ve mor, şeritli güneş, perspektif ızgara, neon çerçeveli kutular.",
        yazi="monoton", buyuk=True, aralik=".04em", duzen="neon", kutu="neon", adim="neon", tablo="neon",
        hareket="parilti", isaret='"\\25C6"',
        koyu=P("#0E0A1C", "#18112B", "#3A2A5C", "#FBF1F7", "#C7B4CF", "#FF5FA2", "#FFB347", "#1E0612"),
        acik=P("#FFF3EC", "#FFFFFF", "#F2D2D9", "#24102A", "#5D4364", "#B0145A", "#A84700", "#FFFFFF"),
        ek=("& .o-h1{font-family:Archivo,sans-serif;font-style:italic;font-stretch:125%;font-weight:800}"
            "& .o-h1 .o-h1-vurgu{font-family:var(--o-font);font-style:normal;font-weight:400}"),
    ),
}

TAKMA = {"diablo": "diablo-4", "diablo-iv": "diablo-4", "gta-vi": "gta-6", "cs2": "counter-strike-2",
         "wow": "world-of-warcraft", "lol": "league-of-legends", "poe-2": "path-of-exile-2", "fc": "ea-sports-fc",
         "mlbb": "mobile-legends", "cod": "call-of-duty", "fm27": "football-manager-27", "halo": "halo-campaign-evolved"}

# Tema olmayan oyun: türüne göre düzen (sıralı anahtar sözcükler), renk kimlikten.
VARSAYILAN_DUZEN = [("mmo", "orta"), ("moba", "serit"), ("battle", "bolge"), ("fps", "acili"), ("nisanci", "acili"),
                    ("shooter", "acili"), ("ryo", "yildiz"), ("rpg", "yildiz"), ("futbol", "saha"), ("spor", "saha"),
                    ("sandbox", "blok"), ("yaris", "yayin"), ("racing", "yayin")]


# ---------------------------------------------------------------- renk yardımcıları
def _rgb(h: str) -> tuple[float, float, float]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _parlaklik(h: str) -> float:
    def kanal(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (kanal(c) for c in _rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def karsitlik(a: str, b: str) -> float:
    x, y = sorted((_parlaklik(a), _parlaklik(b)), reverse=True)
    return (x + 0.05) / (y + 0.05)


def _hsl(h: float, s: float, l: float) -> str:
    c = (1 - abs(2 * l - 1)) * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = l - c / 2
    r, g, b = [(c, x, 0), (x, c, 0), (0, c, x), (0, x, c), (x, 0, c), (c, 0, x)][int(h // 60) % 6]
    return "#" + "".join(f"{round((v + m) * 255):02X}" for v in (r, g, b))


def _uygun(renk_h: float, s: float, l: float, zemin: str, hedef: float, yon: int) -> str:
    """Zemine karşı hedef karşıtlığa ulaşana kadar açıklığı kaydırır (yon +1 açar, -1 koyulaştırır)."""
    for _ in range(60):
        r = _hsl(renk_h, s, l)
        if karsitlik(r, zemin) >= hedef:
            return r
        l = min(0.97, max(0.03, l + 0.01 * yon))
    return _hsl(renk_h, s, l)


def _sade(tur: str) -> str:
    return tur.lower().replace("ı", "i").replace("ş", "s").replace("ç", "c").replace("ğ", "g").replace("ö", "o").replace("ü", "u")


def _varsayilan_palet(hue: float) -> tuple[dict, dict]:
    """Tek renk tonundan koyu ve açık palet (AA karşıtlığı _uygun ile tutturulur)."""
    z_k, y_k, c_k = _hsl(hue, .35, .07), _hsl(hue, .3, .11), _hsl(hue, .25, .24)
    z_a, y_a, c_a = _hsl(hue, .35, .95), "#FFFFFF", _hsl(hue, .25, .82)
    koyu = P(z_k, y_k, c_k, _hsl(hue, .2, .94), _uygun(hue, .15, .66, y_k, 4.6, 1), _uygun(hue, .75, .62, y_k, 4.6, 1),
             _uygun((hue + 150) % 360, .6, .66, y_k, 3.2, 1), _hsl(hue, .5, .08))
    acik = P(z_a, y_a, c_a, _hsl(hue, .3, .1), _uygun(hue, .15, .38, z_a, 4.8, -1), _uygun(hue, .75, .36, z_a, 4.8, -1),
             _uygun((hue + 150) % 360, .6, .34, z_a, 3.2, -1), "#FFFFFF")
    return koyu, acik


def varsayilan_tema(oyun_id: str, tur: str = "") -> dict:
    hue = int(hashlib.sha1(oyun_id.encode()).hexdigest()[:6], 16) % 360
    duzen = next((d for k, d in VARSAYILAN_DUZEN if k in _sade(tur)), "kart")
    koyu, acik = _varsayilan_palet(hue)
    return dict(not_="Varsayılan tema (renk kimlikten türetildi).", yazi="archivo", buyuk=False, aralik="-.01em",
                duzen=duzen, kutu="cerceve", adim="halka", tablo="sus", hareket="yavas", isaret='"\\25C6"',
                koyu=koyu, acik=acik, ek="", varsayilan=True)


# Merkezi olmayan oyunlar (takvim, söylenti, mağaza haberi) için kapak: renk 18 kovadan, düzen kimlikten.
GENEL_KOVA = 18
GENEL_DUZEN = ("orta", "serit", "bolge", "acili", "yildiz", "saha", "blok", "yayin", "kart")


def genel_tema(kimlik: str, tur: str = "") -> dict:
    """Sınıfları genel_css()'te hazır olan hafif tema: {'id', 'duzen', 'kova'} (amblem() için yeterli)."""
    h = int(hashlib.sha1(kimlik.encode()).hexdigest()[:6], 16)
    duzen = next((d for k, d in VARSAYILAN_DUZEN if k in _sade(tur)), "") if tur else ""
    return {"id": kimlik, "duzen": duzen or GENEL_DUZEN[h % len(GENEL_DUZEN)], "kova": (h % 360) * GENEL_KOVA // 360}


def genel_css() -> tuple[str, list[str]]:
    """.tv-<kova> paletleri ve .tm-<düzen> motifleri; denetle() ile AA sınaması."""
    parca, uyari = [], []
    for k in range(GENEL_KOVA):
        koyu, acik = _varsayilan_palet(k * 360 / GENEL_KOVA)
        t = {"id": f"tv-{k}", "koyu": koyu, "acik": acik}
        uyari += denetle(t)
        kb, ab = _paletler(t)
        s = f".tv-{k}"
        parca.append(f"{s}{{{kb}--o-font:Archivo,sans-serif;--o-font-agirlik:800;--o-buyuk:uppercase;--o-aralik:0;color-scheme:dark}}"
                     f'[data-tema="acik"] {s}{{{ab}color-scheme:light}}'
                     f"@media (prefers-color-scheme:light){{:root:not([data-tema]) {s}{{{ab}color-scheme:light}}}}")
    for d in GENEL_DUZEN:
        url, w, h = motif_url(d)
        parca.append(f".tm-{d}{{--o-motif:{url};--o-motif-boy:{w}px {h}px}}")
    return "\n".join(parca), uyari


def tema_al(oyun_id: str, tur: str = "") -> dict:
    kimlik = TAKMA.get(oyun_id, oyun_id)
    t = TEMALAR.get(kimlik) or varsayilan_tema(oyun_id, tur)
    return dict(t, id=oyun_id)


def siniflar(t: dict) -> str:
    return f"o-sayfa t-{t['id']} d-{t['duzen']} k-{t['kutu']} a-{t['adim']} b-{t['tablo']} h-{t['hareket']}"


# ---------------------------------------------------------------- SVG parçaları
def _n(x: float) -> str:
    return f"{x:.1f}".rstrip("0").rstrip(".")


def _halka_cizgi(cx, cy, r1, r2, n, kayma=0.0, sinif="s1", kalin=1.5) -> str:
    out = []
    for i in range(n):
        a = 2 * math.pi * i / n + kayma
        out.append(f'<line x1="{_n(cx + r1 * math.cos(a))}" y1="{_n(cy + r1 * math.sin(a))}" '
                   f'x2="{_n(cx + r2 * math.cos(a))}" y2="{_n(cy + r2 * math.sin(a))}" class="{sinif}" stroke-width="{kalin}"/>')
    return "".join(out)


def _yari_isin(cx, cy, r1, r2, n, sinif="s1", kalin=1.5) -> str:
    """Yalnız ufkun üstüne (yukarı yarım daire) eşit aralıklı n ışın; ufuk çizgisinin altına taşmaz."""
    out = []
    for i in range(n):
        a = math.pi + math.pi * (i + 1) / (n + 1)
        out.append(f'<line x1="{_n(cx + r1 * math.cos(a))}" y1="{_n(cy + r1 * math.sin(a))}" '
                   f'x2="{_n(cx + r2 * math.cos(a))}" y2="{_n(cy + r2 * math.sin(a))}" class="{sinif}" stroke-width="{kalin}"/>')
    return "".join(out)


def _cokgen(cx, cy, r, n, donus=0.0) -> str:
    return " ".join(f"{_n(cx + r * math.cos(2 * math.pi * i / n + donus))},{_n(cy + r * math.sin(2 * math.pi * i / n + donus))}"
                    for i in range(n))


def _yildiz(cx, cy, r1, r2, n, donus=-math.pi / 2) -> str:
    pts = []
    for i in range(2 * n):
        r = r1 if i % 2 == 0 else r2
        a = math.pi * i / n + donus
        pts.append(f"{_n(cx + r * math.cos(a))},{_n(cy + r * math.sin(a))}")
    return " ".join(pts)


def _tohum(ad: str):
    s = int(hashlib.md5(ad.encode()).hexdigest()[:8], 16)

    def rnd():
        nonlocal s
        s = (1103515245 * s + 12345) & 0x7FFFFFFF
        return s / 0x7FFFFFFF
    return rnd


def amblem(t: dict, ek: str = "") -> str:
    """Kahraman alanındaki büyük soyut amblem (satır içi SVG; renkler CSS sınıflarından).
    ek: aynı sayfada birden çok amblem olursa SVG kimliklerini (clipPath, gradient) tekilleştiren sonek."""
    d = t["duzen"]
    g = AMBLEM.get(d, AMBLEM["kart"])(t)
    if ek:
        for kimlik in ("o-kk", "o-gun", "o-gk"):
            g = g.replace(f'id="{kimlik}"', f'id="{kimlik}-{ek}"').replace(f"url(#{kimlik})", f"url(#{kimlik}-{ek})")
    vb = "0 0 200 240" if d in ("yazit", "gotik") else "0 0 200 200"
    return (f'<svg class="o-amblem-svg" viewBox="{vb}" aria-hidden="true" focusable="false" '
            f'fill="none" stroke-linecap="round" stroke-linejoin="round">{g}</svg>')


def _a_orta(t):
    yild = _yildiz(100, 100, 70, 52, 8, -math.pi / 2)
    return ('<circle cx="100" cy="100" r="94" class="s1" stroke-width="2"/>'
            '<circle cx="100" cy="100" r="86" class="s1" stroke-width="1" stroke-dasharray="1 7"/>'
            + _halka_cizgi(100, 100, 86, 94, 32, 0, "s1", 1)
            + f'<polygon points="{yild}" class="f2" opacity=".18"/><polygon points="{yild}" class="s1" stroke-width="2"/>'
            + f'<polygon points="{_cokgen(100, 100, 40, 4, 0)}" class="s1" stroke-width="1.5"/>'
            + f'<polygon points="{_cokgen(100, 100, 40, 4, math.pi / 4)}" class="s1" stroke-width="1.5"/>'
            '<polygon points="100,74 114,100 100,126 86,100" class="f1"/>'
            '<circle cx="100" cy="100" r="5" class="f0"/>')


def _a_kalkan(t):
    yol = "M100 10 L178 32 V94 C178 146 144 176 100 192 C56 176 22 146 22 94 V32 Z"
    return (f'<defs><clipPath id="o-kk"><path d="{yol}"/></clipPath></defs>'
            f'<path d="{yol}" class="f0"/>'
            '<g clip-path="url(#o-kk)"><path d="M-10 60 L60 -10 L120 -10 L-10 120 Z" class="f1" opacity=".9"/>'
            '<path d="M80 200 L210 70 L210 130 L140 200 Z" class="f2" opacity=".35"/>'
            '<path d="M22 118 L100 72 L178 118 L178 140 L100 94 L22 140 Z" class="f2" opacity=".55"/></g>'
            f'<path d="{yol}" class="s1" stroke-width="4"/>'
            '<path d="M100 22 L166 41 V94 C166 139 137 165 100 179 C63 165 34 139 34 94 V41 Z" class="s2" stroke-width="1.2" opacity=".7"/>'
            '<circle cx="100" cy="112" r="9" class="f1"/>')


def _a_safak(t):
    isin = _yari_isin(100, 150, 70, 96, 9, "s1", 2)
    return ('<path d="M20 150 A80 80 0 0 1 180 150 Z" class="f1" opacity=".22"/>'
            '<path d="M44 150 A56 56 0 0 1 156 150" class="s1" stroke-width="3"/>'
            '<path d="M64 150 A36 36 0 0 1 136 150 Z" class="f1"/>' + isin
            + '<line x1="6" y1="150" x2="194" y2="150" class="s2" stroke-width="2"/>'
              '<line x1="30" y1="162" x2="170" y2="162" class="s2" stroke-width="1" opacity=".6"/>'
              '<line x1="56" y1="172" x2="144" y2="172" class="s2" stroke-width="1" opacity=".4"/>'
              '<polygon points="100,22 106,32 100,42 94,32" class="f2"/>')


def _a_yazit(t):
    tas = "M66 18 L134 18 L156 62 L156 226 L44 226 L44 62 Z"
    cizgi = "".join(f'<line x1="62" y1="{y}" x2="{138 - (y % 3) * 6}" y2="{y}" class="s1" stroke-width="2" opacity=".55"/>'
                    for y in range(84, 200, 14))
    return (f'<path d="{tas}" class="f0"/><path d="{tas}" class="s1" stroke-width="3"/>'
            '<path d="M74 30 L126 30 L142 64" class="s1" stroke-width="1" opacity=".6"/>' + cizgi
            + '<rect x="112" y="186" width="34" height="34" class="f2"/><rect x="118" y="192" width="22" height="22" class="s0" stroke-width="2"/>'
              '<line x1="122" y1="203" x2="136" y2="203" class="s0" stroke-width="2"/><line x1="129" y1="196" x2="129" y2="210" class="s0" stroke-width="2"/>')


def _a_serit(t):
    return (f'<polygon points="{_cokgen(100, 100, 78, 6, math.pi / 6)}" class="f0"/>'
            f'<polygon points="{_cokgen(100, 100, 78, 6, math.pi / 6)}" class="s1" stroke-width="3"/>'
            f'<polygon points="{_cokgen(100, 100, 50, 6, math.pi / 6)}" class="f2" opacity=".25"/>'
            f'<polygon points="{_cokgen(100, 100, 50, 6, math.pi / 6)}" class="s2" stroke-width="2"/>'
            + _halka_cizgi(100, 100, 50, 78, 6, math.pi / 6, "s1", 1.2)
            + f'<polygon points="{_cokgen(100, 100, 20, 6, math.pi / 6)}" class="f1"/>'
              '<line x1="10" y1="190" x2="190" y2="10" class="s2" stroke-width="1" stroke-dasharray="4 6" opacity=".7"/>')


def _a_yildiz(t):
    rnd = _tohum("yildiz" + t["id"])
    nok = [(100, 100)] + [(100 + (30 + 55 * rnd()) * math.cos(a), 100 + (30 + 55 * rnd()) * math.sin(a))
                          for a in [2 * math.pi * i / 9 + rnd() * .4 for i in range(9)]]
    bag = "".join(f'<line x1="{_n(nok[0][0])}" y1="{_n(nok[0][1])}" x2="{_n(x)}" y2="{_n(y)}" class="s1" stroke-width="1.2" opacity=".5"/>'
                  for x, y in nok[1::2])
    bag += "".join(f'<line x1="{_n(nok[i][0])}" y1="{_n(nok[i][1])}" x2="{_n(nok[i + 1][0])}" y2="{_n(nok[i + 1][1])}" class="s1" stroke-width="1.6"/>'
                   for i in range(1, len(nok) - 1))
    dug = "".join(f'<circle cx="{_n(x)}" cy="{_n(y)}" r="{4 + (i % 3) * 2}" class="{"f1" if i % 3 else "f0 s1"}" stroke-width="1.5"/>'
                  for i, (x, y) in enumerate(nok[1:]))
    return ('<circle cx="100" cy="100" r="94" class="s2" stroke-width="1" opacity=".6"/>'
            '<circle cx="100" cy="100" r="62" class="s2" stroke-width="1" stroke-dasharray="2 5" opacity=".6"/>'
            + bag + dug + '<circle cx="100" cy="100" r="12" class="f0 s1" stroke-width="3"/><circle cx="100" cy="100" r="5" class="f1"/>')


def _a_gotik(t):
    dis = "M30 232 V104 Q30 40 100 12 Q170 40 170 104 V232"
    ic = "M50 232 V110 Q50 58 100 34 Q150 58 150 110 V232"
    yap = "".join(f'<circle cx="{_n(100 + 15 * math.cos(a))}" cy="{_n(96 + 15 * math.sin(a))}" r="11" class="s1" stroke-width="1.5"/>'
                  for a in [2 * math.pi * i / 6 for i in range(6)])
    diken = "".join(f'<path d="M{x} 232 L{x + 6} 214 L{x + 12} 232" class="f1" opacity=".8"/>' for x in range(36, 160, 18))
    return (f'<path d="{dis} Z" class="f0"/><path d="{dis}" class="s1" stroke-width="4"/><path d="{ic}" class="s1" stroke-width="1.5" opacity=".7"/>'
            '<circle cx="100" cy="96" r="30" class="s1" stroke-width="2"/>' + yap
            + '<line x1="100" y1="130" x2="100" y2="232" class="s1" stroke-width="2"/><line x1="50" y1="160" x2="150" y2="160" class="s1" stroke-width="1" opacity=".6"/>'
            + diken + '<circle cx="100" cy="96" r="6" class="f2"/>')


def _a_gok(t):
    yild = ("M100 18 C106 72 128 94 182 100 C128 106 106 128 100 182 C94 128 72 106 18 100 C72 94 94 72 100 18 Z")
    return ('<ellipse cx="100" cy="100" rx="92" ry="34" class="s2" stroke-width="1.2" opacity=".7" transform="rotate(-18 100 100)"/>'
            '<ellipse cx="100" cy="100" rx="92" ry="34" class="s2" stroke-width="1.2" opacity=".5" transform="rotate(30 100 100)"/>'
            f'<path d="{yild}" class="f1" opacity=".2"/><path d="{yild}" class="s1" stroke-width="2"/>'
            '<circle cx="100" cy="100" r="26" class="s1" stroke-width="1.5"/><circle cx="100" cy="100" r="8" class="f1"/>'
            '<circle cx="168" cy="58" r="4" class="f2"/><circle cx="34" cy="146" r="3" class="f2"/><circle cx="150" cy="160" r="2.5" class="f1"/>')


def _a_acili(t):
    return ('<polygon points="20,170 92,20 118,20 50,170" class="f1"/>'
            '<polygon points="70,170 130,46 156,46 100,170" class="f2" opacity=".25"/>'
            '<polygon points="70,170 130,46 156,46 100,170" class="s2" stroke-width="2"/>'
            '<polyline points="126,120 156,146 126,172" class="s1" stroke-width="6" stroke-linecap="square" stroke-linejoin="miter"/>'
            '<polyline points="150,120 180,146 150,172" class="s1" stroke-width="6" stroke-linecap="square" stroke-linejoin="miter" opacity=".5"/>'
            '<line x1="10" y1="186" x2="190" y2="186" class="s2" stroke-width="2"/><rect x="150" y="18" width="30" height="8" class="f1"/>')


def _a_panel(t):
    r = 26
    merk = [(100, 100)] + [(100 + r * 1.75 * math.cos(math.pi / 3 * i + math.pi / 6), 100 + r * 1.75 * math.sin(math.pi / 3 * i + math.pi / 6))
                           for i in range(6)]
    pet = "".join(f'<polygon points="{_cokgen(x, y, r, 6, 0)}" class="{"f1" if i == 0 else ("f2" if i == 2 else "f0")}" opacity="{1 if i in (0, 2) else .9}"/>'
                  f'<polygon points="{_cokgen(x, y, r, 6, 0)}" class="s1" stroke-width="2.5"/>' for i, (x, y) in enumerate(merk))
    return '<circle cx="100" cy="100" r="96" class="s2" stroke-width="2" opacity=".5"/>' + pet


def _a_hud(t):
    return ('<path d="M8 128 A92 34 0 0 1 192 128" class="s1" stroke-width="6" opacity=".9"/>'
            '<path d="M8 128 A92 34 0 0 0 192 128" class="s1" stroke-width="2" opacity=".35"/>'
            '<circle cx="100" cy="92" r="40" class="s2" stroke-width="2"/>'
            '<circle cx="100" cy="92" r="28" class="s2" stroke-width="1" stroke-dasharray="3 5"/>'
            '<line x1="100" y1="40" x2="100" y2="60" class="s2" stroke-width="2"/><line x1="100" y1="124" x2="100" y2="144" class="s2" stroke-width="2"/>'
            '<line x1="48" y1="92" x2="68" y2="92" class="s2" stroke-width="2"/><line x1="132" y1="92" x2="152" y2="92" class="s2" stroke-width="2"/>'
            '<path d="M14 14 H44 M14 14 V44 M186 14 H156 M186 14 V44 M14 186 H44 M14 186 V156 M186 186 H156 M186 186 V156" class="s1" stroke-width="3"/>'
            '<circle cx="100" cy="92" r="4" class="f1"/>')


def _a_afis(t):
    bar = "".join(f'<rect x="{x}" y="150" width="{w}" height="38" class="f2"/>' for x, w in
                  [(112, 3), (118, 6), (127, 2), (132, 4), (139, 8), (150, 2), (155, 5), (163, 3), (169, 7), (179, 2), (184, 4)])
    return ('<path d="M12 12 H108 V108 A96 96 0 0 1 12 12 Z" class="f1"/>'
            '<circle cx="150" cy="56" r="34" class="s1" stroke-width="3"/>'
            '<line x1="106" y1="56" x2="194" y2="56" class="s1" stroke-width="2"/><line x1="150" y1="12" x2="150" y2="100" class="s1" stroke-width="2"/>'
            '<circle cx="150" cy="56" r="10" class="f1"/><rect x="12" y="130" width="78" height="58" class="s2" stroke-width="3"/>'
            '<line x1="12" y1="130" x2="90" y2="188" class="s2" stroke-width="3"/>' + bar)


def _a_sablon(t):
    return ('<circle cx="100" cy="100" r="70" class="s1" stroke-width="5"/>'
            '<circle cx="100" cy="100" r="40" class="s2" stroke-width="2" stroke-dasharray="6 6"/>'
            + _halka_cizgi(100, 100, 76, 90, 36, 0, "s2", 1.2)
            + '<line x1="100" y1="6" x2="100" y2="74" class="s1" stroke-width="5"/><line x1="100" y1="126" x2="100" y2="194" class="s1" stroke-width="5"/>'
              '<line x1="6" y1="100" x2="74" y2="100" class="s1" stroke-width="5"/><line x1="126" y1="100" x2="194" y2="100" class="s1" stroke-width="5"/>'
              '<circle cx="100" cy="100" r="5" class="f1"/>')


def _a_brifing(t):
    kon = "".join(
        f'<path d="M{_n(100 - k * 15)} 104 C{_n(100 - k * 15)} {_n(70 - k * 13)} {_n(140 + k * 8)} {_n(60 - k * 14)} {_n(150 + k * 12)} {_n(96 - k * 4)} '
        f'C{_n(160 + k * 10)} {_n(132 + k * 12)} {_n(110 - k * 6)} {_n(150 + k * 13)} {_n(100 - k * 15)} 104 Z" class="s1" stroke-width="{2 if k == 0 else 1.2}" opacity="{1 - k * .14}"/>'
        for k in range(6))
    return (kon + '<path d="M120 80 h-12 m12 0 v12 M156 80 h12 m-12 0 v12 M120 124 h-12 m12 0 v-12 M156 124 h12 m-12 0 v-12" class="s2" stroke-width="3" transform="translate(-16 -4)"/>'
            '<rect x="14" y="168" width="70" height="10" class="f2"/><rect x="92" y="168" width="40" height="10" class="f2" opacity=".6"/>'
            '<rect x="14" y="184" width="110" height="10" class="f2" opacity=".8"/><circle cx="124" cy="98" r="4" class="f2"/>')


def _a_bolge(t):
    izg = "".join(f'<line x1="{v}" y1="0" x2="{v}" y2="200" class="s2" stroke-width=".8" opacity=".4"/>'
                  f'<line x1="0" y1="{v}" x2="200" y2="{v}" class="s2" stroke-width=".8" opacity=".4"/>' for v in range(25, 200, 25))
    return (izg + '<circle cx="104" cy="96" r="88" class="s2" stroke-width="2.5"/>'
            '<circle cx="118" cy="110" r="52" class="s1" stroke-width="3"/>'
            '<circle cx="126" cy="120" r="22" class="f1" opacity=".25"/><circle cx="126" cy="120" r="22" class="s1" stroke-width="2"/>'
            '<line x1="8" y1="36" x2="192" y2="168" class="s1" stroke-width="2.5" stroke-dasharray="10 8"/>'
            '<polygon points="40,52 56,50 48,64" class="f1"/>')


def _a_egik(t):
    return ('<polygon points="40,40 190,40 160,90 10,90" class="f1"/>'
            '<polygon points="56,100 196,100 172,140 32,140" class="f2"/>'
            '<polygon points="20,150 150,150 130,184 0,184" class="s1" stroke-width="4"/>'
            '<polygon points="112,6 84,72 108,72 92,126 140,52 114,52 132,6" class="f0 s1" stroke-width="3"/>')


def _a_tugla(t):
    def karo(x, y, s, sinif, don):
        dugme = "".join(f'<circle cx="{x + a}" cy="{y + b}" r="{s * .13}" class="f0"/><circle cx="{x + a}" cy="{y + b}" r="{s * .13}" class="s0" stroke-width="2"/>'
                        for a in (s * .3, s * .7) for b in (s * .3, s * .7))
        return f'<g transform="rotate({don} {x + s / 2} {y + s / 2})"><rect x="{x}" y="{y}" width="{s}" height="{s}" rx="8" class="{sinif}"/>{dugme}</g>'
    return karo(30, 34, 96, "f1", -14) + karo(96, 92, 80, "f2", 12)


def _a_blok(t):
    # soyut yapı taşları: tek renk tonlamalı izometrik küp yığını (oyundaki çimen bloğu dokusu taklit edilmez)
    a, b, h = 36, 21, 42

    def kup(cx, cy, sinif, ton=1.0):
        ust = f"{cx},{cy - b} {cx + a},{cy} {cx},{cy + b} {cx - a},{cy}"
        sol = f"{cx - a},{cy} {cx},{cy + b} {cx},{cy + b + h} {cx - a},{cy + h}"
        sag = f"{cx},{cy + b} {cx + a},{cy} {cx + a},{cy + h} {cx},{cy + b + h}"
        return "".join(f'<polygon points="{p}" class="{sinif}" opacity="{o * ton:.2f}"/><polygon points="{p}" class="s0" stroke-width="2"/>'
                       for p, o in ((ust, 1), (sol, .62), (sag, .38)))
    return (kup(100, 84, "f1", .9) + kup(100, 42, "f1") + kup(64, 105, "f1", .8) + kup(136, 105, "f1", .8)
            + kup(100, 126, "f2"))


def _a_arena(t):
    isin = _halka_cizgi(100, 100, 60, 98, 24, 0, "s2", 2)
    return (isin + f'<polygon points="{_cokgen(100, 100, 62, 4, 0)}" class="f0"/>'
            f'<polygon points="{_cokgen(100, 100, 62, 4, 0)}" class="s1" stroke-width="4"/>'
            f'<polygon points="{_cokgen(100, 100, 40, 4, 0)}" class="f1" opacity=".3"/>'
            f'<polygon points="{_cokgen(100, 100, 40, 4, 0)}" class="s1" stroke-width="2"/>'
            f'<polygon points="{_cokgen(100, 100, 16, 4, 0)}" class="f1"/>')


def _a_yayin(t):
    isik = "".join(f'<circle cx="{x}" cy="{y}" r="3.2" class="f2"/>' for bx in (18, 150) for x in range(bx, bx + 34, 10) for y in (14, 24))
    return (isik + '<polygon points="20,32 50,32 110,200 -30,200" class="f1" opacity=".16"/>'
            '<polygon points="150,32 180,32 230,200 90,200" class="f1" opacity=".16"/>'
            + "".join(f'<rect x="{x}" y="120" width="20" height="80" class="f1" opacity="{.18 if (x // 20) % 2 else .08}"/>' for x in range(0, 200, 20))
            + '<rect x="24" y="92" width="152" height="34" rx="3" class="f0 s1" stroke-width="2"/>'
              '<rect x="24" y="92" width="44" height="34" rx="3" class="f1"/><rect x="132" y="92" width="44" height="34" rx="3" class="f2" opacity=".85"/>'
              '<line x1="88" y1="109" x2="112" y2="109" class="s1" stroke-width="3"/>')


def _a_saha(t):
    dizi = [(100, 176), (40, 140), (80, 146), (120, 146), (160, 140), (60, 104), (100, 112), (140, 104), (46, 64), (100, 56), (154, 64)]
    nok = "".join(f'<circle cx="{x}" cy="{y}" r="7" class="f1"/>' for x, y in dizi)
    return ('<rect x="8" y="8" width="184" height="184" class="s2" stroke-width="2"/>'
            '<line x1="8" y1="100" x2="192" y2="100" class="s2" stroke-width="1.5"/>'
            '<circle cx="100" cy="100" r="26" class="s2" stroke-width="1.5"/>'
            '<rect x="52" y="8" width="96" height="34" class="s2" stroke-width="1.5"/><rect x="52" y="158" width="96" height="34" class="s2" stroke-width="1.5"/>'
            + nok + '<path d="M100 112 Q130 86 146 70" class="s1" stroke-width="2.5" stroke-dasharray="5 5"/><polygon points="150,62 152,76 140,72" class="f1"/>')


def _a_neon(t):
    serit = "".join(f'<rect x="20" y="{y}" width="160" height="{h}" class="f-zemin"/>' for y, h in [(78, 4), (90, 6), (102, 8), (114, 9)])
    izg = "".join(f'<line x1="100" y1="124" x2="{x}" y2="200" class="s2" stroke-width="1.2" opacity=".8"/>' for x in range(-80, 290, 30))
    izg += "".join(f'<line x1="0" y1="{y}" x2="200" y2="{y}" class="s2" stroke-width="1.2" opacity=".8"/>' for y in (132, 144, 160, 182))
    return ('<defs><linearGradient id="o-gun" x1="0" y1="0" x2="0" y2="1"><stop offset="0" class="dur2"/><stop offset="1" class="dur1"/></linearGradient>'
            '<clipPath id="o-gk"><rect x="0" y="0" width="200" height="124"/></clipPath></defs>'
            '<circle cx="100" cy="92" r="66" fill="url(#o-gun)" clip-path="url(#o-gk)"/>' + serit
            + '<line x1="0" y1="124" x2="200" y2="124" class="s1" stroke-width="2.5"/>' + izg)


def _a_kart(t):
    n = 3 + int(hashlib.md5(t["id"].encode()).hexdigest()[:2], 16) % 5
    return (f'<polygon points="{_cokgen(100, 100, 90, n, -math.pi / 2)}" class="s1" stroke-width="3"/>'
            f'<polygon points="{_cokgen(100, 100, 62, n, -math.pi / 2 + math.pi / n)}" class="f2" opacity=".25"/>'
            f'<polygon points="{_cokgen(100, 100, 62, n, -math.pi / 2 + math.pi / n)}" class="s2" stroke-width="2"/>'
            f'<polygon points="{_cokgen(100, 100, 26, n, -math.pi / 2)}" class="f1"/>')


AMBLEM = {"orta": _a_orta, "kalkan": _a_kalkan, "safak": _a_safak, "yazit": _a_yazit, "serit": _a_serit, "yildiz": _a_yildiz,
          "gotik": _a_gotik, "gok": _a_gok, "acili": _a_acili, "panel": _a_panel, "hud": _a_hud, "afis": _a_afis,
          "sablon": _a_sablon, "brifing": _a_brifing, "bolge": _a_bolge, "egik": _a_egik, "tugla": _a_tugla, "blok": _a_blok,
          "arena": _a_arena, "yayin": _a_yayin, "saha": _a_saha, "neon": _a_neon, "kart": _a_kart}


# Arka plan motifi: tek renkli döşeme, CSS'te maske olarak kullanılır (rengi temadan gelir).
def _m(w, h, govde):
    return w, h, f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">{govde}</svg>'


MOTIF = {
    "orta": lambda: _m(48, 48, '<path d="M24 2 L46 24 L24 46 L2 24 Z" fill="none" stroke="#000" stroke-width="1"/><circle cx="24" cy="24" r="2.4"/>'),
    "kalkan": lambda: _m(36, 36, '<path d="M-9 9 L9 -9 M0 36 L36 0 M27 45 L45 27" stroke="#000" stroke-width="7"/>'),
    "safak": lambda: _m(64, 16, '<rect x="0" y="7" width="40" height="1.5"/><rect x="48" y="7" width="8" height="1.5"/>'),
    "yazit": lambda: _m(40, 20, '<g fill="none" stroke="#000" stroke-width="1.2">' + "".join(
        f'<circle cx="{cx}" cy="{cy}" r="{r}"/>' for cx, cy in ((0, 20), (40, 20), (20, 10)) for r in (6, 12, 18)) + '</g>'),
    "serit": lambda: _m(34, 58, f'<polygon points="{_cokgen(17, 15, 5, 6, math.pi / 6)}"/><polygon points="{_cokgen(0, 44, 5, 6, math.pi / 6)}"/>'
                                f'<polygon points="{_cokgen(34, 44, 5, 6, math.pi / 6)}"/>'),
    "yildiz": lambda: _m(90, 90, '<circle cx="12" cy="18" r="1.6"/><circle cx="60" cy="8" r="1"/><circle cx="44" cy="52" r="2"/>'
                                 '<circle cx="80" cy="70" r="1.3"/><circle cx="20" cy="76" r="1"/><path d="M12 18 L44 52 L80 70" stroke="#000" stroke-width=".6" fill="none"/>'),
    "gotik": lambda: _m(40, 40, '<path d="M20 4 L23 17 L36 20 L23 23 L20 36 L17 23 L4 20 L17 17 Z"/>'),
    "gok": lambda: _m(70, 70, '<circle cx="10" cy="12" r="1.6"/><circle cx="46" cy="30" r="1"/><circle cx="28" cy="58" r="2.2"/>'
                              '<path d="M50 56 q6 -6 12 0" fill="none" stroke="#000" stroke-width="1"/>'),
    "acili": lambda: _m(48, 48, '<path d="M0 .5 H48 M.5 0 V48" stroke="#000" stroke-width="1"/><path d="M20 24 H28 M24 20 V28" stroke="#000" stroke-width="1.5"/>'),
    "panel": lambda: _m(42, 72, '<g fill="none" stroke="#000" stroke-width="1.2">' + "".join(
        f'<polygon points="{_cokgen(x, y, 14, 6, 0)}"/>' for x, y in ((0, 0), (42, 0), (21, 36), (0, 72), (42, 72))) + '</g>'),
    "hud": lambda: _m(8, 8, '<rect x="0" y="0" width="8" height="1"/>'),
    "afis": lambda: _m(14, 14, '<circle cx="3.5" cy="3.5" r="2.2"/><circle cx="10.5" cy="10.5" r="1.2"/>'),
    "sablon": lambda: _m(56, 56, '<rect x="0" y="0" width="28" height="56" transform="skewX(-30)" opacity=".9"/>'),
    "brifing": lambda: _m(120, 60, '<g fill="none" stroke="#000" stroke-width="1">'
                                   '<path d="M0 30 C30 10 60 50 120 30"/><path d="M0 44 C30 24 60 64 120 44"/><path d="M0 16 C30 -4 60 36 120 16"/></g>'),
    "bolge": lambda: _m(64, 64, '<path d="M0 .5 H64 M.5 0 V64" stroke="#000" stroke-width="1.6"/><path d="M0 16.5 H64 M0 32.5 H64 M0 48.5 H64 '
                                'M16.5 0 V64 M32.5 0 V64 M48.5 0 V64" stroke="#000" stroke-width=".5"/>'),
    "egik": lambda: _m(60, 30, '<polygon points="8,2 40,2 32,13 0,13"/><polygon points="38,17 70,17 62,28 30,28"/><polygon points="-22,17 10,17 2,28 -30,28"/>'),
    "tugla": lambda: _m(32, 32, '<circle cx="16" cy="16" r="6" fill="none" stroke="#000" stroke-width="2"/><circle cx="16" cy="16" r="2"/>'),
    "blok": lambda: _m(64, 64, "".join(f'<rect x="{x * 8}" y="{y * 8}" width="8" height="8" opacity="{o:.2f}"/>'
                                       for x in range(8) for y in range(8) for o in [(((x * 7 + y * 13) % 9) / 9) ** 2] if o > .15)),
    "arena": lambda: _m(40, 24, '<path d="M4 20 L20 6 L36 20" fill="none" stroke="#000" stroke-width="2"/>'),
    "yayin": lambda: _m(80, 10, '<rect x="0" y="0" width="40" height="10"/>'),
    "saha": lambda: _m(28, 28, '<circle cx="14" cy="14" r="1.4"/>'),
    "neon": lambda: _m(10, 10, '<rect x="0" y="0" width="10" height="2"/>'),
    "kart": lambda: _m(24, 24, '<circle cx="12" cy="12" r="1.5"/>'),
}


def motif_url(duzen: str) -> tuple[str, int, int]:
    w, h, svg = MOTIF.get(duzen, MOTIF["kart"])()
    return "url(\"data:image/svg+xml," + urllib.parse.quote(svg, safe=" =:/,.#-") + "\")", w, h


def ayrac(t: dict) -> str:
    """Bölümler arası süs ayracı (satır içi SVG, 240x24)."""
    d = t["duzen"]
    orta = {
        "orta": '<polygon points="120,4 128,12 120,20 112,12" class="f1"/><polygon points="100,9 104,12 100,15 96,12" class="f1"/><polygon points="140,9 144,12 140,15 136,12" class="f1"/>',
        "kalkan": '<path d="M106 4 L134 20 M134 4 L106 20" class="s1" stroke-width="3"/><circle cx="120" cy="12" r="4" class="f2"/>',
        "safak": '<path d="M104 18 A16 16 0 0 1 136 18 Z" class="f1"/>' + _yari_isin(120, 18, 18, 24, 5, "s1", 1.5),
        "yazit": '<rect x="112" y="4" width="16" height="16" class="f2"/><rect x="116" y="8" width="8" height="8" class="s0" stroke-width="1.5"/>',
        "serit": f'<polygon points="{_cokgen(120, 12, 9, 6, math.pi / 6)}" class="s1" stroke-width="2"/><polygon points="{_cokgen(120, 12, 4, 6, math.pi / 6)}" class="f2"/>',
        "yildiz": '<circle cx="96" cy="12" r="3" class="f1"/><circle cx="120" cy="12" r="5" class="f0 s1" stroke-width="2"/><circle cx="144" cy="12" r="3" class="f1"/>',
        "gotik": '<path d="M108 20 Q108 8 120 2 Q132 8 132 20" class="s1" stroke-width="2"/><circle cx="120" cy="13" r="3" class="f1"/>',
        "gok": '<path d="M120 2 C121 10 122 11 130 12 C122 13 121 14 120 22 C119 14 118 13 110 12 C118 11 119 10 120 2 Z" class="f1"/>',
        "acili": '<polygon points="98,20 108,4 142,4 132,20" class="f1"/>',
        "panel": f'<polygon points="{_cokgen(108, 12, 8, 6, 0)}" class="f1"/><polygon points="{_cokgen(132, 12, 8, 6, 0)}" class="s1" stroke-width="2"/>',
        "hud": '<path d="M100 6 H112 L118 12 H122 L128 6 H140" class="s2" stroke-width="2"/>',
        "afis": '<rect x="104" y="4" width="16" height="16" class="f1"/><circle cx="132" cy="12" r="8" class="s1" stroke-width="2.5"/>',
        "sablon": '<circle cx="120" cy="12" r="8" class="s1" stroke-width="2.5"/><path d="M120 0 V8 M120 16 V24 M108 12 H116 M124 12 H132" class="s1" stroke-width="2"/>',
        "brifing": '<rect x="96" y="7" width="48" height="10" class="f2"/>',
        "bolge": '<circle cx="120" cy="12" r="9" class="s1" stroke-width="2"/><circle cx="123" cy="13" r="4" class="f1"/>',
        "egik": '<polygon points="104,4 122,4 116,20 98,20" class="f1"/><polygon points="124,4 142,4 136,20 118,20" class="f2"/>',
        "tugla": '<rect x="106" y="2" width="28" height="20" rx="4" class="f1"/><circle cx="114" cy="12" r="3" class="f0"/><circle cx="126" cy="12" r="3" class="f0"/>',
        "blok": '<rect x="104" y="8" width="8" height="8" class="f2"/><rect x="112" y="0" width="8" height="8" class="f1"/><rect x="120" y="8" width="8" height="8" class="f1"/><rect x="128" y="16" width="8" height="8" class="f2"/>',
        "arena": f'<polygon points="{_cokgen(120, 12, 10, 4, 0)}" class="f1"/>' + _halka_cizgi(120, 12, 12, 16, 8, math.pi / 8, "s2", 1.2),
        "yayin": '<rect x="96" y="6" width="22" height="12" class="f1"/><rect x="122" y="6" width="22" height="12" class="f2"/>',
        "saha": '<circle cx="120" cy="12" r="8" class="s1" stroke-width="1.5"/><circle cx="120" cy="12" r="2.5" class="f1"/>',
        "neon": '<path d="M104 12 L120 4 L136 12 L120 20 Z" class="s1" stroke-width="2"/>',
    }.get(d, '<polygon points="120,5 127,12 120,19 113,12" class="f1"/>')
    kesik = ' stroke-dasharray="6 6"' if d in ("bolge", "brifing", "saha") else ""
    return (f'<div class="o-ayrac" aria-hidden="true"><svg viewBox="0 0 240 24" fill="none">'
            f'<line x1="6" y1="12" x2="90" y2="12" class="s1" stroke-width="1.5"{kesik}/>'
            f'<line x1="150" y1="12" x2="234" y2="12" class="s1" stroke-width="1.5"{kesik}/>{orta}</svg></div>')


# ---------------------------------------------------------------- CSS üretimi
def _paletler(t: dict) -> tuple[str, str]:
    def blok(p):
        return (f"--o-zemin:{p['zemin']};--o-yuzey:{p['yuzey']};--o-cizgi:{p['cizgi']};--o-yazi:{p['yazi']};--o-soluk:{p['soluk']};"
                f"--o-vurgu:{p['vurgu']};--o-vurgu2:{p['vurgu2']};--o-vurgu-yazi:{p['vurgu_yazi']};")
    return blok(t["koyu"]), blok(t["acik"])


def denetle(t: dict) -> list[str]:
    """AA karşıtlık denetimi: metin 4.5, büyük başlık süsü ve çizim 3."""
    sorun = []
    for tema in ("koyu", "acik"):
        p = t[tema]
        for on, arka, en_az, ne in [("yazi", "zemin", 7, "metin"), ("yazi", "yuzey", 7, "metin/yüzey"),
                                    ("soluk", "zemin", 4.5, "soluk"), ("soluk", "yuzey", 4.5, "soluk/yüzey"),
                                    ("vurgu", "zemin", 4.5, "vurgu metni"), ("vurgu", "yuzey", 4.5, "vurgu/yüzey"),
                                    ("vurgu_yazi", "vurgu", 4.5, "düğme yazısı"), ("vurgu2", "zemin", 3, "vurgu2 çizimi")]:
            k = karsitlik(p[on], p[arka])
            if k < en_az:
                sorun.append(f"{t['id']} {tema}: {ne} {k:.2f} < {en_az}")
    return sorun


def css_uret(oyunlar: list[dict]) -> tuple[str, list[str]]:
    """oyun-tema.css içeriği ve karşıtlık uyarıları."""
    parca = [TEMEL_CSS.read_text(encoding="utf-8")]
    for anahtar, (aile, dosya, agirlik) in YAZILAR.items():
        if dosya:
            parca.append(f'@font-face{{font-family:"{aile}";src:url(/fonts/oyun/{dosya}.woff2) format("woff2");'
                         f"font-weight:{agirlik};font-display:swap}}")
    uyari = []
    goruldu = set()
    for o in oyunlar:
        t = tema_al(o["id"], (o.get("tur") or {}).get("en", ""))
        if t["id"] in goruldu:
            continue
        goruldu.add(t["id"])
        uyari += denetle(t)
        k, a = _paletler(t)
        aile = YAZILAR.get(t["yazi"], YAZILAR["archivo"])[0]
        ag = YAZILAR.get(t["yazi"], YAZILAR["archivo"])[2]
        url, w, h = motif_url(t["duzen"])
        s = f".t-{t['id']}"
        parca.append(
            f'{s}{{{k}--o-font:"{aile}",Archivo,sans-serif;--o-font-agirlik:{ag};--o-buyuk:{"uppercase" if t["buyuk"] else "none"};'
            f"--o-aralik:{t['aralik']};--o-isaret:{t['isaret']};--o-motif:{url};--o-motif-boy:{w}px {h}px;color-scheme:dark}}"
            f'[data-tema="acik"] {s}{{{a}color-scheme:light}}'
            f"@media (prefers-color-scheme:light){{:root:not([data-tema]) {s}{{{a}color-scheme:light}}}}")
        if t.get("ek"):
            parca.append(t["ek"].replace("&", s))
    genel, g_uyari = genel_css()
    parca.append(genel)
    return "\n".join(parca) + "\n", uyari + g_uyari


def kapak(t: dict, kisa: str, buyuk: bool = False, ek: str = "") -> str:
    """Dizin kartı ve merkez sayfası için üretilmiş kapak (telifli görsel yok). kisa kaçışlanmış gelmeli."""
    return (f'<div class="o-kapak{" o-kapak-buyuk" if buyuk else ""}" aria-hidden="true">'
            f'<span class="o-kapak-motif"></span><span class="o-kapak-amblem">{amblem(t, ek)}</span>'
            f'<span class="o-kapak-ad">{kisa}</span></div>')
