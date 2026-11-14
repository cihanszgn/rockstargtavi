#!/usr/bin/env python3
"""İndirim ve ücretsiz oyun anlık görüntüsü.

CheapShark (ücretsiz, anahtarsız) ve Epic Games Store'un haftalık ücretsiz oyun
listesinden veriyi çeker, sitenin canlı veri alamadığında kullandığı iki dosyayı yazar:

  data/indirimler.json   güncel fırsatlar + izinli mağaza listesi
  data/ucretsiz.json     Epic'in bu haftaki ve gelecek haftaki ücretsiz oyunları + CheapShark'ta 0 $ olanlar

Kullanım:  python tools/indirim_cek.py
Yalnız Python standart kütüphanesi kullanılır (GitHub Actions'ta da çalışır: .github/workflows/indirim.yml).
Bir kaynak hata verirse o dosyanın eski hâli korunur, çıkış kodu 1 olur.
"""
from __future__ import annotations

import json
import pathlib
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

KOK = pathlib.Path(__file__).resolve().parent.parent
VERI = KOK / "data"
UA = "ctrl-agame-indirim/1.0"
CS = "https://www.cheapshark.com"
CS_API = CS + "/api/1.0"
EPIC = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions?locale=en-US&country=TR&allowCountries=TR"

# Yalnız resmî / yetkili dijital mağazalar. CheapShark'ın mağaza adlarıyla eşleşir (küçük harf).
# Gri pazar anahtar satıcıları bu listeye eklenmez.
IZINLI = {
    "steam", "gamersgate", "greenmangaming", "gog", "humble store", "fanatical", "wingamestore",
    "gamebillet", "voidu", "epic games store", "gamesplanet", "gamesload", "2game", "indiegala",
    "blizzard shop", "dlgamer", "noctre", "dreamgame", "allyouplay", "uplay", "ubisoft store",
    "origin", "ea app", "gamestop", "amazon", "razer game store", "battle.net",
}

ALANLAR = ("dealID", "gameID", "title", "storeID", "salePrice", "normalPrice", "savings",
           "metacriticScore", "steamRatingText", "steamRatingPercent", "steamAppID", "releaseDate",
           "dealRating", "thumb")


def getir(url: str, deneme: int = 3):
    hata = None
    for i in range(deneme):
        try:
            istek = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(istek, timeout=30) as yanit:
                return json.loads(yanit.read().decode("utf-8"))
        except Exception as h:  # ağ hatası, 429, bozuk JSON
            hata = h
            time.sleep(2 + 3 * i)
    raise RuntimeError(f"{url}: {hata}")


def yaz(yol: pathlib.Path, veri: dict) -> None:
    yol.parent.mkdir(parents=True, exist_ok=True)
    metin = json.dumps(veri, ensure_ascii=False, indent=1) + "\n"
    yol.write_text(metin, encoding="utf-8", newline="\n")


def sade(f: dict) -> dict:
    x = {k: f.get(k) for k in ALANLAR}
    for k in ("salePrice", "normalPrice", "savings", "dealRating"):
        try:
            x[k] = round(float(x[k] or 0), 2)
        except ValueError:
            x[k] = 0.0
    for k in ("metacriticScore", "steamRatingPercent", "releaseDate"):
        try:
            x[k] = int(x[k] or 0)
        except ValueError:
            x[k] = 0
    return x


def magazalar() -> list[dict]:
    liste = []
    for m in getir(CS_API + "/stores"):
        ad = str(m.get("storeName", "")).strip()
        if str(m.get("isActive")) != "1" or ad.lower() not in IZINLI:
            continue
        ikon = (m.get("images") or {}).get("icon", "")
        liste.append({"id": str(m["storeID"]), "ad": ad, "ikon": (CS + ikon) if ikon.startswith("/") else ikon})
    if not liste:
        raise RuntimeError("izinli aktif mağaza bulunamadı")
    return liste


def en_dusukler(oyunlar: list[str]) -> dict[str, float]:
    sonuc = {}
    for i in range(0, len(oyunlar), 25):
        parca = oyunlar[i:i + 25]
        veri = getir(CS_API + "/games?ids=" + ",".join(parca))
        for gid, bilgi in (veri or {}).items():
            try:
                sonuc[gid] = round(float(bilgi["cheapestPriceEver"]["price"]), 2)
            except (KeyError, TypeError, ValueError):
                pass
        time.sleep(1)
    return sonuc


def firsatlar(izinli: list[str], **ek) -> list[dict]:
    q = {"storeID": ",".join(izinli), "pageSize": "60", **ek}
    ham = getir(CS_API + "/deals?" + urllib.parse.urlencode(q))
    gorulen, liste = set(), []
    for f in ham:
        if str(f.get("storeID")) not in izinli or f.get("gameID") in gorulen:
            continue
        gorulen.add(f.get("gameID"))
        liste.append(sade(f))
    return liste


def epic_ucretsiz() -> list[dict]:
    veri = getir(EPIC)
    ogeler = (((veri.get("data") or {}).get("Catalog") or {}).get("searchStore") or {}).get("elements") or []
    simdi = datetime.now(timezone.utc)
    sonuc = []
    for o in ogeler:
        promo = o.get("promotions") or {}
        for durum, anahtar in (("simdi", "promotionalOffers"), ("yakinda", "upcomingPromotionalOffers")):
            for grup in promo.get(anahtar) or []:
                for teklif in grup.get("promotionalOffers") or []:
                    if (teklif.get("discountSetting") or {}).get("discountPercentage") != 0:
                        continue
                    bas, bit = teklif.get("startDate"), teklif.get("endDate")
                    if not bas or not bit:
                        continue
                    if durum == "simdi" and not (datetime.fromisoformat(bas.replace("Z", "+00:00")) <= simdi < datetime.fromisoformat(bit.replace("Z", "+00:00"))):
                        continue
                    slug = o.get("productSlug") or ""
                    for kume in (o.get("catalogNs") or {}).get("mappings") or [], o.get("offerMappings") or []:
                        for e in kume:
                            if e.get("pageSlug") and (not slug or slug == "[]"):
                                slug = e["pageSlug"]
                    if slug in ("", "[]"):
                        slug = ""
                    resimler = {r.get("type"): r.get("url") for r in o.get("keyImages") or []}
                    resim = next((resimler[t] for t in ("OfferImageWide", "DieselStoreFrontWide", "Thumbnail", "OfferImageTall") if resimler.get(t)), "")
                    fiyat = (o.get("price") or {}).get("totalPrice") or {}
                    sonuc.append({
                        "baslik": o.get("title", "").strip(),
                        "slug": slug.split("/")[0],
                        "resim": resim,
                        "baslangic": bas,
                        "bitis": bit,
                        "durum": durum,
                        "normal": round((fiyat.get("originalPrice") or 0) / 100, 2),
                        "para": fiyat.get("currencyCode", ""),
                    })
    sonuc.sort(key=lambda x: (x["durum"] != "simdi", x["baslangic"], x["baslik"]))
    return sonuc


def main() -> int:
    zaman = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    hata = 0
    try:
        mag = magazalar()
        izinli = [m["id"] for m in mag]
        liste = firsatlar(izinli, sortBy="Deal Rating", onSale="1")
        dusuk = en_dusukler([f["gameID"] for f in liste])
        for f in liste:
            if f["gameID"] in dusuk:
                f["enDusuk"] = dusuk[f["gameID"]]
        bedava = firsatlar(izinli, upperPrice="0")
        yaz(VERI / "indirimler.json", {"guncel": zaman, "kaynak": CS, "magazalar": mag, "firsatlar": liste})
        print(f"indirimler.json: {len(liste)} fırsat, {len(mag)} mağaza")
    except Exception as h:
        print("CheapShark alınamadı:", h)
        bedava, hata = None, 1
    try:
        epic = epic_ucretsiz()
    except Exception as h:
        print("Epic alınamadı:", h)
        epic, hata = None, 1
    eski = {}
    yol = VERI / "ucretsiz.json"
    if yol.exists():
        eski = json.loads(yol.read_text(encoding="utf-8"))
    if epic is not None or bedava is not None:
        yaz(yol, {
            "guncel": zaman,
            "epic": epic if epic is not None else eski.get("epic", []),
            "cheapshark": bedava if bedava is not None else eski.get("cheapshark", []),
        })
        print(f"ucretsiz.json: Epic {len(epic or eski.get('epic', []))}, CheapShark {len(bedava or eski.get('cheapshark', []))}")
    return hata


if __name__ == "__main__":
    sys.exit(main())
