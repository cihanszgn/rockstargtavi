#!/usr/bin/env python3
"""Oyun görselleri: takvim ve oyunlar kayıtları için kart/afiş adresi bulur.

Her kayıt için kaynak sırası:
  1. Steam mağazası: ad (normalize edilmiş) tam eşleşirse appdetails'teki
     header_image klasöründen capsule_616x353.jpg (kart) ve library_hero.jpg
     (geniş afiş) denenir; gerçekten açılanların en büyüğü seçilir.
  2. Steam'de yoksa resmî sayfanın og:image adresi (gorsel_cek.bul kuralı:
     aynı alan adı/CDN, en az 600 px). Haber siteleri kaynak olamaz.
  3. İkisi de olmazsa kayıt yazılmaz (site üretilmiş kapağı gösterir).

Görsel depoya KAYDEDİLMEZ; adres yazılır, site doğrudan kaynaktan gösterir.

Çıktı: data/oyun_gorselleri.json
  {"takvim": {"<id>": {"url", "genis"?, "kaynak", "en", "boy"}}, "oyun": {...}}

Kullanım:
  py tools/oyun_gorsel_cek.py              yalnız kaydı olmayanlar
  py tools/oyun_gorsel_cek.py --yenile     hepsini yeniden çek
  py tools/oyun_gorsel_cek.py --id <id>    tek kayıt (takvim veya oyun id'si)
  py tools/oyun_gorsel_cek.py --kuru       yazmadan ne bulacağını göster

Hata bir kaydı atlar, aracı düşürmez; var olan iyi kayıt geçici hatada silinmez.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.parse

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import gorsel_cek as gc  # yardımcılar (ac, gorsel_olc, bul) yeniden kullanılır

KOK = pathlib.Path(__file__).resolve().parent.parent
TAKVIM = KOK / "data" / "takvim.json"
OYUNLAR = KOK / "data" / "oyunlar.json"
CIKTI = KOK / "data" / "oyun_gorselleri.json"

STEAM_ARA = "https://store.steampowered.com/api/storesearch/?term={}&cc=us&l=en"
STEAM_DETAY = "https://store.steampowered.com/api/appdetails?appids={}"
KART_DOSYA = "capsule_616x353.jpg"   # 616x353, ~16:9
ILAVE_KART = "header.jpg"            # 460x215, yedek
GENIS_DOSYA = "library_hero.jpg"     # geniş afiş
KART_EN_AZ = 460                     # px
GENIS_EN_AZ = 1200                   # px
BEKLE = 1.0                          # sn; istekler arası
ALAN = ("url", "genis", "kaynak", "en", "boy")

# Haber/inceleme siteleri kaynak olamaz (fan sitesi, wiki, haber sitesi kuralı).
HABER_SITELERI = ("ign.com", "rpgfan.com", "hypebeast.com", "invenglobal.com",
                  "gameinformer.com", "nintendolife.com")


def norm(s: str | None) -> str:
    """Küçük harf, ™®© ve noktalama atılmış, boşluklar teke indirilmiş ad."""
    s = (s or "").lower().replace("™", "").replace("®", "").replace("©", "")
    return " ".join(re.sub(r"[\W_]+", " ", s).split())


def json_al(url: str):
    """Steam JSON'u; 429 (hız sınırı) yanıtında bekleyip en fazla 3 kez dener."""
    for bekle in (0, 30, 60):
        if bekle:
            time.sleep(bekle)
        try:
            with gc.ac(url, "application/json,*/*;q=0.5") as y:
                return json.loads(y.read(3_000_000).decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as h:
            if h.code != 429:
                raise
    raise OSError("Steam hız sınırı (429)")


def steam_bul(adlar: list[str]) -> tuple[int, str] | None:
    """Adlardan biri Steam'de normalize tam eşleşirse (appid, steam_adı) döner."""
    for ad in adlar:
        hedef = norm(ad)
        if not hedef:
            continue
        veri = json_al(STEAM_ARA.format(urllib.parse.quote(ad)))
        time.sleep(BEKLE)
        for it in veri.get("items") or []:
            if it.get("type", "app") == "app" and norm(it.get("name")) == hedef:
                return int(it["id"]), str(it["name"])
    return None


def steam_gorselleri(appid: int) -> dict | None:
    """appdetails'teki header_image klasöründen kart ve (varsa) geniş afiş."""
    veri = json_al(STEAM_DETAY.format(appid))
    time.sleep(BEKLE)
    d = veri.get(str(appid)) or {}
    if not d.get("success"):
        return None
    baslik = (d.get("data") or {}).get("header_image") or ""
    if not baslik.startswith("https://"):
        return None
    klasor = baslik.split("?")[0].rsplit("/", 1)[0] + "/"
    en_iyi = None
    for aday in (klasor + KART_DOSYA, klasor + ILAVE_KART, baslik):
        try:
            en, boy = gc.gorsel_olc(aday)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            continue
        finally:
            time.sleep(BEKLE)
        if en >= KART_EN_AZ and (en_iyi is None or en > en_iyi["en"]):
            en_iyi = {"url": aday, "en": en, "boy": boy}
    if not en_iyi:
        return None
    kayit = {"url": en_iyi["url"], "kaynak": "Steam", "en": en_iyi["en"], "boy": en_iyi["boy"]}
    try:
        genis_en, _ = gc.gorsel_olc(klasor + GENIS_DOSYA)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        genis_en = 0
    finally:
        time.sleep(BEKLE)
    if genis_en >= GENIS_EN_AZ:
        kayit["genis"] = klasor + GENIS_DOSYA
    return kayit


def resmi_bul(url: str | None, ad: str) -> tuple[dict | None, str]:
    """Resmî sayfanın og:image adresi; gorsel_cek.bul kuralıyla (alan adı, 600 px)."""
    if not url or not url.startswith("https://"):
        return None, "resmî adres yok"
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    if any(host == h or host.endswith("." + h) for h in HABER_SITELERI):
        return None, f"haber sitesi, kaynak olamaz ({host})"
    kayit, neden = gc.bul({"kaynaklar": [{"url": url, "ad": ad}]})
    if not kayit:
        return None, neden
    # Kare logo/simge kart görseli olamaz (16:9 alanda kırpılınca tanınmaz).
    if kayit["boy"] and kayit["en"] / kayit["boy"] < 1.3:
        return None, f"yatay değil ({kayit['en']}x{kayit['boy']})"
    return {"url": kayit["url"], "kaynak": ad, "en": kayit["en"], "boy": kayit["boy"]}, "resmî sayfa"


def bul_kayit(adlar: list[str], resmi_url: str | None, resmi_ad: str) -> tuple[dict | None, str]:
    """Bir kayıt için: Steam, yoksa resmî sayfa. Dönüş: (kayıt veya None, açıklama)."""
    notlar = []
    s = steam_bul(adlar)
    if s:
        appid, steam_ad = s
        kayit = steam_gorselleri(appid)
        if kayit:
            return kayit, f"Steam: {steam_ad} (appid {appid})"
        notlar.append(f"Steam'de görsel yok (appid {appid})")
    else:
        notlar.append("Steam'de tam eşleşme yok")
    kayit, neden = resmi_bul(resmi_url, resmi_ad)
    if kayit:
        return kayit, neden
    return None, "; ".join(notlar + [neden])


def alanlari_sirala(kayit: dict) -> dict:
    return {k: kayit[k] for k in ALAN if k in kayit}


def topla(bolumler: dict, eski: dict, yenile: bool, idler: list[str], bul) -> tuple[dict, dict]:
    """bolumler: {"takvim": [(id, adlar, resmi_url, resmi_ad), ...], "oyun": [...]}.
    Dönüş: (yeni sonuç, sayaçlar). `bul` (adlar, url, ad) -> (kayıt|None, açıklama)."""
    yeni = {"takvim": {}, "oyun": {}}
    sayac = {"denenen": 0, "bulunan": 0, "atlanan": 0}
    for bolum, kayitlar in bolumler.items():
        onceki_bolum = eski.get(bolum) or {}
        for kid, adlar, url, ad in kayitlar:
            onceki = onceki_bolum.get(kid)
            if (idler and kid not in idler) or (onceki and not yenile):
                if onceki:
                    yeni[bolum][kid] = onceki
                continue
            sayac["denenen"] += 1
            try:
                kayit, aciklama = bul(adlar, url, ad)
            except Exception as h:  # ağ/ayrıştırma hatası: kayıt atlanır, araç devam eder
                kayit, aciklama = None, f"hata: {h}"
            if kayit:
                yeni[bolum][kid] = alanlari_sirala(kayit)
                sayac["bulunan"] += 1
                print(f"+ {bolum}:{kid}: {aciklama} -> {kayit['kaynak']} {kayit['en']}x{kayit['boy']}")
            else:
                sayac["atlanan"] += 1
                if onceki:
                    yeni[bolum][kid] = onceki
                print(f"- {bolum}:{kid}: {aciklama}" + (" (eski kayıt korundu)" if onceki else ""))
            time.sleep(BEKLE)
    return yeni, sayac


def sirali(yeni: dict) -> dict:
    return {b: {k: yeni[b][k] for k in sorted(yeni[b])} for b in ("takvim", "oyun")}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--yenile", action="store_true", help="kaydı olanları da yeniden çek")
    ap.add_argument("--id", action="append", default=[], help="yalnız bu kayıt(lar)")
    ap.add_argument("--kuru", action="store_true", help="dosyaya yazma")
    a = ap.parse_args()

    takvim = json.loads(TAKVIM.read_text(encoding="utf-8"))
    oyunlar = json.loads(OYUNLAR.read_text(encoding="utf-8"))
    eski: dict = {}
    if CIKTI.exists():
        try:
            eski = json.loads(CIKTI.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print("UYARI: oyun_gorselleri.json bozuk, baştan yazılacak", file=sys.stderr)

    bolumler = {
        "takvim": [(r["id"], [r["oyun"]], r["kaynak"]["url"], r["kaynak"]["ad"]) for r in takvim],
        "oyun": [(r["id"], list(dict.fromkeys([r["ad"], *r.get("eslesme", [])])),
                  r["resmi"]["url"], r["gelistirici"]) for r in oyunlar],
    }
    sonuc_cache: dict = {}

    def bul(adlar, url, ad):
        anahtar = tuple(adlar)
        if anahtar not in sonuc_cache:  # aynı oyun iki listede: bir kez sorgula
            sonuc_cache[anahtar] = bul_kayit(adlar, url, ad)
        return sonuc_cache[anahtar]

    yeni, sayac = topla(bolumler, eski, a.yenile, a.id, bul)
    son = sirali(yeni)
    print(f"denenen {sayac['denenen']}, bulunan {sayac['bulunan']}, atlanan {sayac['atlanan']}; "
          f"takvim {len(son['takvim'])}/{len(takvim)}, oyun {len(son['oyun'])}/{len(oyunlar)}")
    if not a.kuru and (son != eski or not CIKTI.exists()):
        CIKTI.write_text(json.dumps(son, ensure_ascii=False, indent=1) + "\n",
                         encoding="utf-8", newline="\n")
        print(f"yazıldı: {CIKTI.relative_to(KOK)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
