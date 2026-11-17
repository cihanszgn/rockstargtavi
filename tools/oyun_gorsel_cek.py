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
  py tools/oyun_gorsel_cek.py --appid <id>=<steam appid>   elle Steam eşleşmesi (ad doğrulanır, kayıt kilitlenir)
  py tools/oyun_gorsel_cek.py --elle <id>=<https görsel adresi>   elle resmî görsel (ölçülür, kayıt kilitlenir)

Kilit: kayda "kilit": true yazılırsa (--appid/--elle bunu yapar) --yenile bile o kaydı ezmez.
Steam araması: ad listesindeki 5 karakterden kısa takma adlar (ör. "BDO") yalnız tam adın
yanında aranmaz; kısaltma başka bir oyunla eşleşip yanlış görsel getirmesin diye atlanır.

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
ALAN = ("url", "genis", "kaynak", "en", "boy", "appid", "kilit")
TAKMA_AD_EN_AZ = 5                  # karakter; ilk ad hariç takma adlar için

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
    for i, ad in enumerate(adlar):
        hedef = norm(ad)
        if not hedef or (i > 0 and len(hedef) < TAKMA_AD_EN_AZ):
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
        tamam, bilgi = steam_dogrula(appid, adlar[0])   # DLC/demo/oyun dışı uygulama olmasın
        kayit = steam_gorselleri(appid) if tamam else None
        if not tamam:
            notlar.append(f"Steam eşleşmesi elendi: {bilgi}")
        if kayit:
            return kayit, f"Steam: {steam_ad} (appid {appid})"
        if tamam:
            notlar.append(f"Steam'de görsel yok (appid {appid})")
    else:
        notlar.append("Steam'de tam eşleşme yok")
    kayit, neden = resmi_bul(resmi_url, resmi_ad)
    if kayit:
        return kayit, neden
    return None, "; ".join(notlar + [neden])


def steam_oyun_gorseli(ad: str) -> tuple[dict | None, str]:
    """Haber için yedek: oyun adı Steam'de tam eşleşir ve tür game ise Steam kart görseli (gorsel_cek çağırır)."""
    s = steam_bul([ad])
    if not s:
        return None, "Steam'de tam eşleşme yok"
    appid, steam_ad = s
    tamam, bilgi = steam_dogrula(appid, ad)
    if not tamam:
        return None, f"Steam eşleşmesi elendi: {bilgi}"
    kayit = steam_gorselleri(appid)
    return (kayit, f"Steam: {steam_ad} (appid {appid})") if kayit else (None, f"Steam'de görsel yok (appid {appid})")


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
            if (idler and kid not in idler) or (onceki and (not yenile or onceki.get("kilit"))):
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


def steam_dogrula(appid: int, ad: str) -> tuple[bool, str]:
    """appid gerçekten bu oyun mu: type=game ve Steam adı ile kayıt adı birbirini içermeli."""
    veri = json_al(STEAM_DETAY.format(appid))
    time.sleep(BEKLE)
    d = veri.get(str(appid)) or {}
    if not d.get("success"):
        return False, "appdetails başarısız"
    dd = d.get("data") or {}
    steam_ad = str(dd.get("name") or "")
    if dd.get("type") != "game":
        return False, f"tür game değil ({dd.get('type')}): {steam_ad}"
    a, b = norm(ad), norm(steam_ad)
    if not a or not (a in b or b in a):
        return False, f"ad uyuşmuyor: kayıt '{ad}' / Steam '{steam_ad}'"
    return True, steam_ad


def elle_ekle(eski: dict, bolumler: dict, istekler: list[str], mod: str) -> int:
    """--appid / --elle: kaydı doğrulayıp 'kilit' ile yazar. Dönüş: hata sayısı."""
    hata = 0
    for ist in istekler:
        kid, _, deger = ist.partition("=")
        bolum = next((b for b, ks in bolumler.items() if any(k[0] == kid for k in ks)), None)
        if not bolum or not deger:
            print(f"! {ist}: kayıt bulunamadı ya da değer yok")
            hata += 1
            continue
        satir = next(k for k in bolumler[bolum] if k[0] == kid)
        try:
            if mod == "appid":
                ok, bilgi = steam_dogrula(int(deger), satir[1][0])
                if not ok:
                    print(f"! {bolum}:{kid}: {bilgi}")
                    hata += 1
                    continue
                kayit = steam_gorselleri(int(deger))
                if not kayit:
                    print(f"! {bolum}:{kid}: Steam görseli açılmadı (appid {deger})")
                    hata += 1
                    continue
                kayit["appid"] = int(deger)
                aciklama = f"Steam: {bilgi} (appid {deger})"
            else:
                if not deger.startswith("https://"):
                    raise ValueError("https değil")
                en, boy = gc.gorsel_olc(deger)
                if en < gc.EN_AZ:
                    raise ValueError(f"çok küçük ({en}x{boy})")
                kayit = {"url": deger, "kaynak": satir[3], "en": en, "boy": boy}
                aciklama = "elle resmî görsel"
        except Exception as h:
            print(f"! {bolum}:{kid}: {h}")
            hata += 1
            continue
        kayit["kilit"] = True
        eski.setdefault(bolum, {})[kid] = alanlari_sirala(kayit)
        print(f"+ {bolum}:{kid}: {aciklama} -> {kayit['en']}x{kayit['boy']} (kilitli)")
    return hata


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--yenile", action="store_true", help="kaydı olanları da yeniden çek")
    ap.add_argument("--id", action="append", default=[], help="yalnız bu kayıt(lar)")
    ap.add_argument("--kuru", action="store_true", help="dosyaya yazma")
    ap.add_argument("--appid", action="append", default=[], metavar="ID=APPID", help="elle Steam appid (doğrulanır, kilitlenir)")
    ap.add_argument("--elle", action="append", default=[], metavar="ID=URL", help="elle resmî görsel adresi (kilitlenir)")
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

    if a.appid or a.elle:
        eski.setdefault("takvim", {})
        eski.setdefault("oyun", {})
        hata = elle_ekle(eski, bolumler, a.appid, "appid") + elle_ekle(eski, bolumler, a.elle, "elle")
        son = sirali(eski)
        if not a.kuru:
            CIKTI.write_text(json.dumps(son, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
            print(f"yazıldı: {CIKTI.relative_to(KOK)}")
        return 1 if hata else 0
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
