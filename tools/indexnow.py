#!/usr/bin/env python3
"""Yeni ve değişen sayfaları IndexNow ile arama motorlarına (Bing, Yandex, Naver, Seznam, Yep) bildirir.

  python tools/indexnow.py --aralik <önceki commit> <yeni commit>   iki commit arasında eklenen sayfalar + liste sayfaları
  python tools/indexnow.py --tum                                    site haritasındaki bütün adresler (ilk kurulum / elle)
  ... --deneme                                                      yalnız listeyi yaz, gönderme

Yalnız sitemap.xml'de olan adres gönderilir (noindex sayfa haritada yoktur, o yüzden gitmez).
Anahtar kökteki 32 haneli .txt dosyasıdır; gizli değildir (sitede herkese açık durur).
Google IndexNow kullanmaz; onun için site haritası yeter.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

KOK = pathlib.Path(__file__).resolve().parent.parent
UC = "https://api.indexnow.org/indexnow"
EN_FAZLA = 10000  # IndexNow tek istekte en çok 10.000 adres alır


def site() -> str:
    return "https://" + (KOK / "CNAME").read_text(encoding="utf-8").strip()


def anahtar() -> str:
    for k in sorted(KOK.glob("*.txt")):
        if re.fullmatch(r"[0-9a-f]{32}", k.stem) and k.read_text(encoding="utf-8").strip() == k.stem:
            return k.stem
    raise SystemExit("IndexNow anahtar dosyası (32 haneli .txt) kökte yok")


def harita_adresleri() -> list[str]:
    return re.findall(r"<loc>([^<]+)</loc>", (KOK / "sitemap.xml").read_text(encoding="utf-8"))


def adres(yol: str, kok: str) -> str:
    """Depo yolu → site adresi. index.html klasör adresine döner (site haritasındaki biçim)."""
    yol = yol.replace("\\", "/")
    if yol == "index.html":
        return kok + "/"
    if yol.endswith("/index.html"):
        return f"{kok}/{yol[:-len('index.html')]}"
    return f"{kok}/{yol}"


def secilenler(degisen: list[tuple[str, str]], harita: list[str], kok: str) -> list[str]:
    """degisen: (durum harfi, yol). Eklenen her sayfa + değişen dil ana sayfaları.
    Öteki değişen sayfa gönderilmez: site yeniden üretilince yüzlerce sayfa biçimce değişir, içerik aynıdır."""
    harita_k = set(harita)
    eklenen, liste = [], []
    for durum, yol in degisen:
        if not yol.endswith(".html"):
            continue
        a = adres(yol, kok)
        if a not in harita_k:
            continue
        if durum.startswith("A"):
            eklenen.append(a)
        elif durum.startswith("M") and re.fullmatch(r"([a-z]{2}/)?index\.html", yol.replace("\\", "/")):
            liste.append(a)
    if not eklenen:
        return []  # yeni sayfa yoksa liste sayfalarını tek başına gönderme
    return list(dict.fromkeys(eklenen + liste))[:EN_FAZLA]


def git_degisen(once: str, sonra: str) -> list[tuple[str, str]]:
    c = subprocess.run(["git", "diff", "--name-status", "--no-renames", once, sonra, "--", "*.html"],
                       cwd=KOK, capture_output=True, text=True, encoding="utf-8", check=True)
    return [tuple(s.split("\t", 1)) for s in c.stdout.splitlines() if "\t" in s]


def yayinda_bekle(url: str, sure: int = 420) -> bool:
    """GitHub Pages yeni sayfayı yayına alana kadar bekler (yayında olmayan adres bildirilmez)."""
    son = time.time() + sure
    while True:
        try:
            req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "ctrl-agame-indexnow"})
            with urllib.request.urlopen(req, timeout=15) as r:
                if r.status == 200:
                    return True
        except (urllib.error.URLError, TimeoutError):
            pass
        if time.time() >= son:
            return False
        time.sleep(20)


def gonder(adresler: list[str], kok: str, key: str) -> int:
    govde = json.dumps({"host": kok.split("://", 1)[1], "key": key, "keyLocation": f"{kok}/{key}.txt",
                        "urlList": adresler}).encode()
    req = urllib.request.Request(UC, data=govde, method="POST",
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status
    except urllib.error.HTTPError as h:
        print("IndexNow yanıtı:", h.code, h.read().decode("utf-8", "replace")[:300])
        return h.code


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aralik", nargs=2, metavar=("ONCE", "SONRA"))
    ap.add_argument("--tum", action="store_true")
    ap.add_argument("--deneme", action="store_true")
    a = ap.parse_args()
    kok, key, harita = site(), anahtar(), harita_adresleri()
    if a.tum:
        adresler = harita[:EN_FAZLA]
    elif a.aralik:
        adresler = secilenler(git_degisen(*a.aralik), harita, kok)
    else:
        ap.error("--aralik ya da --tum gerekli")
    print(f"{len(adresler)} adres")
    for u in adresler[:15]:
        print(" ", u)
    if not adresler or a.deneme:
        return 0
    if not a.tum and not yayinda_bekle(adresler[0]):
        print(f"::warning::{adresler[0]} yayına girmedi; bildirim atlandı")
        return 0
    kod = gonder(adresler, kok, key)
    print("IndexNow durum kodu:", kod)
    if kod not in (200, 202):
        print(f"::warning::IndexNow {kod} döndü")
    return 0


if __name__ == "__main__":
    sys.exit(main())
