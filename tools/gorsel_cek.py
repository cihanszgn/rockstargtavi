#!/usr/bin/env python3
"""Haber görselleri: her haberin ilk resmî kaynağından og:image adresini bulur.

data/icerik.json'daki her haber için ilk kaynağın sayfasını okur, og:image (yoksa
twitter:image) adresini alır, görselin başını indirip boyutunu ölçer ve
data/gorseller.json'a yazar:

  {"<haber-id>": {"url": "https://...", "kaynak": "Xbox Wire", "en": 1200, "boy": 630}}

Görsel depoya KAYDEDİLMEZ; site onu doğrudan kaynağın sunucusundan gösterir
(yüklenemezse sayfa üretilmiş kapağa düşer).

Kurallar: yalnız https; görsel ya kaynak sayfayla aynı alan adından ya da o
kaynağın bilinen CDN'inden gelmeli (CDN listesi aşağıda); eni 600 px'ten küçük
ya da ulaşılamayan görsel atlanır; jenerik site görseli (favicon, ogimage, social-share,
svg, kare logo, page_bg) reddedilir. Kaydı olan haber yeniden çekilmez.

Elle düzeltme: kayda "kilit": true eklenirse --yenile ile de ezilmez. Kaynak görseli
yanlış olan habere {"kilit": true, "neden": "..."} (url'siz) yazılır; site o haberde
oyunun doğrulanmış resmî görselini (data/oyun_gorselleri.json) gösterir.

Kullanım:
  py tools/gorsel_cek.py              yalnız kaydı olmayan haberler
  py tools/gorsel_cek.py --yenile     hepsini yeniden çek
  py tools/gorsel_cek.py --id <id>    tek haber (--yenile ile birlikte zorlar)
  py tools/gorsel_cek.py --kuru       yazmadan ne bulacağını göster

data/icerik.json'a yazmaz (o dosya değişince sosyal paylaşım tetiklenir).
Boyut Pillow ile ölçülür; Pillow yoksa PNG/JPEG/GIF/WebP başlığı elle okunur.
"""
from __future__ import annotations

import argparse
import io
import json
import pathlib
import re
import struct
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

KOK = pathlib.Path(__file__).resolve().parent.parent
ICERIK = KOK / "data" / "icerik.json"
CIKTI = KOK / "data" / "gorseller.json"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
EN_AZ = 600                 # px; daha dar görsel kart için bulanık kalır
SAYFA_SINIR = 3_000_000     # bayt; kaynak sayfanın en fazla bu kadarı okunur
GORSEL_SINIR = 4_000_000    # bayt; boyut bulunamazsa bu kadardan sonra vazgeçilir

# Kaynak alan adı (kayıtlı ad) -> görsellerini sunduğu CDN alan adları.
# Yalnız o yayıncının kendi CDN'leri; genel görsel barındırma servisleri yok.
CDN = {
    "blizzard.com": ("blz-contentstack-images.akamaized.net", "bnetcmsus-a.akamaihd.net",
                     "bnetcmsus-a.akamaized.net", "blz-contentstack.com", "blizzard.cn"),
    "epicgames.com": ("unrealengine.com", "epicgames.net", "fortnite.com"),
    "playvalorant.com": ("rgpub.io", "contentstack.io", "riotgames.com"),
    "leagueoflegends.com": ("rgpub.io", "contentstack.io", "riotgames.com"),
    "pathofexile.com": ("poecdn.com",),
    "pubg.com": ("krafton.com", "pubg.com"),
    "minecraft.net": ("minecraft.net", "minecraftservices.com"),
    "playstation.com": ("playstation.net", "playstation.com"),
    # Xbox Wire görselleri Microsoft'un haber odası barındırmasında, kendi alt alan adında durur
    "xbox.com": ("xbox.com", "xboxlive.com", "microsoft.com", "s-microsoft.com",
                 "xboxwire.thesourcemediaassets.com"),
    "nintendo.com": ("nintendo.com", "nintendo.net", "nintendo-europe.com"),
    # Google blog ailesi (blog.youtube dahil) görselleri Google'ın blog deposundan sunar; yalnız o klasör
    "blog.youtube": ("youtube.com", "ytimg.com", "storage.googleapis.com/gweb-uniblog-publish-prod/"),
    "nttgame.com": ("nttgame.com",),
}
IKILI_SON = {"co.uk", "com.tr", "co.jp", "com.au", "com.br"}


def kayitli_ad(host: str) -> str:
    """news.xbox.com -> xbox.com, blog.youtube -> blog.youtube (kısa alan adı olduğu gibi)."""
    host = (host or "").lower().rstrip(".")
    p = host.split(".")
    if len(p) <= 2:
        return host
    if ".".join(p[-2:]) in IKILI_SON:
        return ".".join(p[-3:])
    if p[-1] == "youtube":            # blog.youtube gibi marka üst alan adları
        return ".".join(p[-2:])
    return ".".join(p[-2:])


def izinli(sayfa: str, gorsel: str) -> bool:
    s, g = urllib.parse.urlsplit(sayfa), urllib.parse.urlsplit(gorsel)
    if g.scheme != "https" or not g.hostname:
        return False
    ka, kg = kayitli_ad(s.hostname or ""), (g.hostname or "").lower()
    if kg == ka or kg.endswith("." + ka):
        return True
    for c in CDN.get(ka, ()):
        if "/" in c:   # paylaşımlı barındırma: yalnız yayıncının klasörü
            ana, _, yol = c.partition("/")
            if kg == ana and g.path.startswith("/" + yol):
                return True
        elif kg == c or kg.endswith("." + c):
            return True
    return False


class MetaOku(HTMLParser):
    ADLAR = ("og:image:secure_url", "og:image", "og:image:url", "twitter:image", "twitter:image:src")

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.bulunan: dict[str, str] = {}

    def handle_starttag(self, tag, attrs):
        if tag != "meta":
            return
        a = {k.lower(): (v or "") for k, v in attrs}
        ad = (a.get("property") or a.get("name") or "").strip().lower()
        if ad in self.ADLAR and a.get("content") and ad not in self.bulunan:
            self.bulunan[ad] = a["content"].strip()


# Çerezli açıcı: bazı topluluk sayfaları (ör. Epic forumu) çerez koymadan yönlendirme döngüsüne girer
_ACICI = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())


def ac(url: str, kabul: str, zaman: int = 25):
    istek = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": kabul,
                                                 "Accept-Language": "en-US,en;q=0.8"})
    return _ACICI.open(istek, timeout=zaman)


def sayfa_oku(url: str) -> tuple[str, str]:
    with ac(url, "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5") as y:
        son = y.geturl()
        ham = y.read(SAYFA_SINIR)
        kod = y.headers.get_content_charset() or "utf-8"
    return son, ham.decode(kod, errors="replace")


def adaylar(son_url: str, html: str) -> list[str]:
    m = MetaOku()
    try:
        m.feed(html)
    except Exception:  # bozuk HTML: o ana kadar bulunanla devam
        pass
    sira = []
    for ad in MetaOku.ADLAR:
        v = m.bulunan.get(ad)
        if v:
            u = urllib.parse.urljoin(son_url, v)
            if u.startswith("//"):
                u = "https:" + u
            if u not in sira:
                sira.append(u)
    return sira


def _el_ile(b: bytes):
    """Pillow yoksa: PNG, GIF, JPEG, WebP başlığından (en, boy)."""
    if b[:8] == b"\x89PNG\r\n\x1a\n" and len(b) >= 24:
        return struct.unpack(">II", b[16:24])
    if b[:6] in (b"GIF87a", b"GIF89a") and len(b) >= 10:
        return struct.unpack("<HH", b[6:10])
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP" and len(b) >= 30:
        t = b[12:16]
        if t == b"VP8X":
            return 1 + int.from_bytes(b[24:27], "little"), 1 + int.from_bytes(b[27:30], "little")
        if t == b"VP8 ":
            w, h = struct.unpack("<HH", b[26:30])
            return w & 0x3FFF, h & 0x3FFF
        if t == b"VP8L":
            v = int.from_bytes(b[21:25], "little")
            return (v & 0x3FFF) + 1, ((v >> 14) & 0x3FFF) + 1
    if b[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(b):
            if b[i] != 0xFF:
                i += 1
                continue
            m = b[i + 1]
            if m in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h, w = struct.unpack(">HH", b[i + 5:i + 9])
                return w, h
            if m in (0xD8, 0x01) or 0xD0 <= m <= 0xD7:
                i += 2
                continue
            i += 2 + struct.unpack(">H", b[i + 2:i + 4])[0]
    return None


def boyut_bul(b: bytes):
    try:
        from PIL import Image  # isteğe bağlı
        with Image.open(io.BytesIO(b)) as im:
            return im.size
    except ImportError:
        return _el_ile(b)
    except Exception:  # başlık henüz tam inmedi
        return None


def gorsel_olc(url: str) -> tuple[int, int]:
    with ac(url, "image/avif,image/webp,image/png,image/jpeg,image/*;q=0.8") as y:
        tur = (y.headers.get_content_type() or "").lower()
        if not tur.startswith("image/"):
            raise ValueError(f"görsel değil ({tur})")
        if tur == "image/svg+xml":
            raise ValueError("svg (boyutsuz) atlandı")
        veri = b""
        while len(veri) < GORSEL_SINIR:
            parca = y.read(65536)
            if not parca:
                break
            veri += parca
            olcu = boyut_bul(veri)
            if olcu:
                return int(olcu[0]), int(olcu[1])
        olcu = boyut_bul(veri)
        if olcu:
            return int(olcu[0]), int(olcu[1])
    raise ValueError("boyut okunamadı")


# Site geneli/jenerik paylaşım görselleri haberin görseli değildir (logo, favicon, arka plan dokusu, eski tarihli afiş).
JENERIK = re.compile(r"favicon|ogimage|og-image|og_image|social-share|share-default|default-og|page_bg|sprite|apple-touch|/logo", re.I)


def jenerik_mi(u: str, en: int, boy: int) -> str:
    """Jenerik/uygunsuz görselse nedeni, değilse boş döner."""
    yol = urllib.parse.urlsplit(u).path
    if yol.lower().endswith((".svg", ".ico")):
        return "vektör/simge"
    if JENERIK.search(yol):
        return "jenerik site görseli"
    if boy and en / boy < 1.2:
        return f"kare/dikey logo ({en}x{boy})"
    return ""


def bul(haber: dict) -> tuple[dict | None, str]:
    k = (haber.get("kaynaklar") or [{}])[0]
    url = k.get("url", "")
    if not url.startswith("https://"):
        return None, "kaynak https değil"
    try:
        son, html = sayfa_oku(url)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as h:
        return None, f"sayfa açılamadı: {h}"
    sec = adaylar(son, html)
    if not sec:
        return None, "og:image/twitter:image yok"
    neden = []
    for u in sec:
        if not izinli(url, u) and not izinli(son, u):
            neden.append(f"izinsiz alan adı: {urllib.parse.urlsplit(u).hostname}")
            continue
        try:
            en, boy = gorsel_olc(u)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as h:
            neden.append(f"görsel açılamadı: {h}")
            continue
        if en < EN_AZ:
            neden.append(f"çok küçük ({en}x{boy})")
            continue
        jn = jenerik_mi(u, en, boy)
        if jn:
            neden.append(f"{jn}: {urllib.parse.urlsplit(u).path.rsplit('/', 1)[-1]}")
            continue
        return {"url": u, "kaynak": k.get("ad") or urllib.parse.urlsplit(url).hostname, "en": en, "boy": boy}, "tamam"
    return None, "; ".join(neden)


def oyunlarda_var(ad: str) -> bool:
    """Oyun adı data/oyunlar.json kayıtlarından biriyle eşleşiyor mu (o zaman site oyun görseline düşer)."""
    try:
        for o in json.loads((KOK / "data" / "oyunlar.json").read_text(encoding="utf-8")):
            adlar = [o.get("ad"), o.get("kisa"), *(o.get("eslesme") or [])]
            if ad.strip().casefold() in {a.strip().casefold() for a in adlar if isinstance(a, str)}:
                return True
    except (OSError, ValueError):
        pass
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--yenile", action="store_true", help="kaydı olanları da yeniden çek")
    ap.add_argument("--id", action="append", default=[], help="yalnız bu haber(ler)")
    ap.add_argument("--kuru", action="store_true", help="dosyaya yazma")
    a = ap.parse_args()

    haberler = json.loads(ICERIK.read_text(encoding="utf-8"))
    eski = {}
    if CIKTI.exists():
        try:
            eski = json.loads(CIKTI.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print("UYARI: gorseller.json bozuk, baştan yazılacak", file=sys.stderr)
    idler = {h["id"] for h in haberler}
    yeni = {k: v for k, v in eski.items() if k in idler}
    atilan = sorted(set(eski) - idler)
    bulunan = atlanan = denenen = 0
    for h in haberler:
        hid = h["id"]
        if a.id and hid not in a.id:
            continue
        if hid in yeni and (not a.yenile or (isinstance(yeni[hid], dict) and yeni[hid].get("kilit"))):
            continue  # kayıtlı iyi kayıt; "kilit" (elle doğrulanmış) kayıt --yenile ile de ezilmez
        denenen += 1
        kayit, neden = bul(h)
        if not kayit and hid not in yeni and h.get("oyun") and not oyunlarda_var(h["oyun"]):
            try:   # kaynak sayfada kullanılır görsel yok ve oyun kaydı da yok: Steam'de tam ad eşleşen oyunun kartı
                import oyun_gorsel_cek as og
                kayit, neden = og.steam_oyun_gorseli(h["oyun"])
            except Exception as hata:
                neden = f"{neden}; Steam yedeği hata: {hata}"
        if kayit:
            yeni[hid] = kayit
            bulunan += 1
            print(f"+ {hid}: {kayit['en']}x{kayit['boy']} {urllib.parse.urlsplit(kayit['url']).hostname}")
        else:
            atlanan += 1   # geçici ağ hatası iyi bir eski kaydı silmesin; eski kayıt (varsa) kalır
            print(f"- {hid}: {neden}" + (" (eski kayıt korundu)" if hid in yeni else ""))
        time.sleep(0.4)  # kaynak sunuculara nazik ol
    sirali = {k: yeni[k] for k in sorted(yeni)}
    print(f"denenen {denenen}, bulunan {bulunan}, atlanan {atlanan}; kayıtlı toplam {len(sirali)}/{len(idler)} haber"
          + (f"; artık olmayan {len(atilan)} kayıt silindi" if atilan else ""))
    if not a.kuru and (sirali != eski or not CIKTI.exists()):
        CIKTI.write_text(json.dumps(sirali, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
        print(f"yazıldı: {CIKTI.relative_to(KOK)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
