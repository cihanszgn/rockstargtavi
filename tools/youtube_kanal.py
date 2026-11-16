#!/usr/bin/env python3
"""YouTube kanal ayarları (Windows, Cio'nun bilgisayarı).

  py tools\\youtube_kanal.py goster [--dil tr]            kanalın adını, açıklamasını, izinleri gösterir
  py tools\\youtube_kanal.py aciklama <dosya> [--dil tr]  kanal açıklamasını dosyadaki metinle değiştirir

Anahtarlar bu bilgisayarda şifreli durur (sosyal\\kurulum.bat → "YouTube kanalı bağla" yazar); ekrana basılmaz.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from sosyal_kurulum import YT_YONETIM, yt_oku  # noqa: E402
from sosyal_yayinla import PaylasimHatasi, istek  # noqa: E402

API = "https://www.googleapis.com/youtube/v3/channels"
EN_UZUN = 1000  # YouTube kanal açıklaması sınırı (karakter)
YENIDEN_BAGLA = 'Önce sosyal\\kurulum.bat, menüden "YouTube kanalı bağla (Shorts)" adımını yeniden yap.'


def erisim(dil: str) -> tuple[str, bool]:
    """(erişim anahtarı, kanalı yönetme izni var mı)"""
    s = yt_oku(dil)
    if not s:
        raise PaylasimHatasi(f"Bu bilgisayarda {dil.upper()} YouTube anahtarı yok. {YENIDEN_BAGLA}", kesin=True)
    _, t = istek("POST", "https://oauth2.googleapis.com/token", veri={
        "client_id": s["CLIENT_ID"], "client_secret": s["CLIENT_SECRET"], "refresh_token": s["REFRESH_TOKEN"],
        "grant_type": "refresh_token"})
    return t["access_token"], YT_YONETIM in t.get("scope", "").split()


def kanal_oku(anahtar: str) -> dict:
    _, k = istek("GET", API + "?part=snippet,brandingSettings&mine=true", basliklar={"Authorization": "Bearer " + anahtar})
    ogeler = k.get("items") or []
    if not ogeler:
        raise PaylasimHatasi("Bu Google hesabında YouTube kanalı görünmüyor.", kesin=True)
    return ogeler[0]


def aciklama_govdesi(kanal: dict, metin: str) -> dict:
    """Yalnız açıklamayı değiştirir. Kanalın öteki ayarları (anahtar kelime, ülke...) aynen geri yollanır,
    çünkü YouTube gövdede olmayan ayarı siler."""
    ayar = dict((kanal.get("brandingSettings") or {}).get("channel") or {})
    ayar["description"] = metin
    return {"id": kanal["id"], "brandingSettings": {"channel": ayar}}


def main() -> int:
    ap = argparse.ArgumentParser(description="YouTube kanal ayarları")
    ap.add_argument("is_", choices=["goster", "aciklama"], metavar="goster|aciklama")
    ap.add_argument("dosya", nargs="?", help="açıklama metni (UTF-8 dosya)")
    ap.add_argument("--dil", default="tr")
    a = ap.parse_args()
    sys.stdout.reconfigure(errors="replace")  # boruya yazarken Windows kod sayfası hatası vermesin
    try:
        anahtar, yonetim = erisim(a.dil)
        kanal = kanal_oku(anahtar)
        if a.is_ == "goster":
            print(f'Kanal: {kanal["snippet"]["title"]}')
            print(f'Yönetme izni: {"var" if yonetim else "YOK. " + YENIDEN_BAGLA}')
            print("Açıklama:\n" + (kanal["snippet"].get("description") or "(boş)"))
            return 0
        if not a.dosya:
            ap.error("aciklama için dosya gerekir")
        metin = pathlib.Path(a.dosya).read_text(encoding="utf-8").strip()
        if not metin or len(metin) > EN_UZUN:
            raise PaylasimHatasi(f"Açıklama 1-{EN_UZUN} karakter olmalı (şimdi {len(metin)}).", kesin=True)
        if not yonetim:
            raise PaylasimHatasi(f"Kanalı yönetme izni yok. {YENIDEN_BAGLA}", kesin=True)
        istek("PUT", API + "?part=brandingSettings", json_govde=aciklama_govdesi(kanal, metin),
              basliklar={"Authorization": "Bearer " + anahtar})
        yeni = kanal_oku(anahtar)["snippet"].get("description", "")
        if yeni.strip() != metin:
            raise PaylasimHatasi("YouTube isteği kabul etti ama açıklama değişmemiş görünüyor.")
        print(f'TAMAM: "{kanal["snippet"]["title"]}" kanalının açıklaması güncellendi ({len(metin)} karakter).')
        return 0
    except (PaylasimHatasi, KeyError) as h:
        print(f"OLMADI: {h}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
