"""Üretilen HTML, yapılandırılmış veri ve Google Haberler site haritasını yerelde ölç."""
import argparse
import json
import os
import re
from html import unescape
from pathlib import Path
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree as ET

from haber_oto import Sayfa
from site_metin import ETIKET_KLASOR

KOK = Path(__file__).resolve().parents[1]
SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
LD = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)


def html_sayfalari():
    # Bu depoda Jekyll dışlama listesi tek seviyeli klasör/dosya adlarından oluşur.
    dislanan = {"video"} | set(re.findall(r"^  - ([\w.-]+)\s*$", (KOK / "_config.yml").read_text(encoding="utf-8"), re.M))
    for klasor, alt, dosyalar in os.walk(KOK):
        alt[:] = [ad for ad in alt if not ad.startswith(".") and ad not in dislanan]
        for ad in dosyalar:
            if ad.endswith(".html") and ad not in dislanan:
                yield Path(klasor) / ad


def sayfalari_olc():
    toplam = uzun = eksik_ld = kisa = 0
    for dosya in html_sayfalari():
        bas = dosya.read_text(encoding="utf-8").split("</head>", 1)[0]
        if re.search(r'<meta name="robots" content="[^"]*\bnoindex\b', bas, re.I):
            continue
        baslik = re.search(r"<title>(.*?)</title>", bas, re.S)
        aciklama = re.search(r'<meta name="description" content="([^"]*)"', bas)
        toplam += 1
        uzun += bool(baslik and len(unescape(baslik[1])) > 65)
        eksik_ld += not LD.search(bas)
        kisa += len(unescape(aciklama[1] if aciklama else "")) < 70
    return {"sayfa": toplam, "title_gt_65": uzun, "json_ld_yok": eksik_ld, "description_lt_70": kisa}


def ornegi_olc(yol: str, baglanti: bool = False):
    dosya = KOK / yol
    html = dosya.read_text(encoding="utf-8")
    ld = [json.loads(raw) for raw in LD.findall(html)]
    if not ld:
        raise ValueError(f"{yol}: JSON-LD bulunamadı")
    print(f"{yol}: json.loads={len(ld)}")
    if not baglanti:
        return
    kirik = []
    ic = 0
    for adres in Sayfa(html).links:
        url = urlsplit(adres)
        if url.scheme not in ("", "http", "https") or (url.netloc and url.hostname not in ("ctrl-agame.com", "www.ctrl-agame.com")):
            continue
        yol = unquote(url.path)
        hedef = dosya if not yol else KOK / yol.lstrip("/") if yol.startswith("/") else dosya.parent / yol
        if hedef.is_dir():
            hedef /= "index.html"
        ic += 1
        if not hedef.is_file():
            kirik.append(adres)
    print(f"ic_baglanti={ic} kirik={len(kirik)}")
    if kirik:
        raise ValueError(", ".join(kirik))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--haber", help="JSON-LD ölçümü için örnek haber dosyası")
    parser.add_argument("--etiket", help="JSON-LD ve iç bağlantı ölçümü için örnek etiket dosyası")
    args = parser.parse_args()
    print(sayfalari_olc())
    print("etiket:", {d: len(list((KOK / klasor).glob("*.html"))) for d, klasor in ETIKET_KLASOR.items()})
    xml = ET.parse(KOK / "news-sitemap.xml")
    print(f"news-sitemap.xml: xml.etree=OK adres={len(xml.findall(SITEMAP_NS + 'url'))}")
    if args.haber:
        ornegi_olc(args.haber)
    if args.etiket:
        ornegi_olc(args.etiket, baglanti=True)


if __name__ == "__main__":
    main()
