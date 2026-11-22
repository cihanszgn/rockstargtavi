#!/usr/bin/env python3
"""Klip hattı -> paylaşım hattı köprüsü (onay kapılı). Bilgisayarda çalışır; GitHub Actions yalnız data/klipler.json okur.

  py tools/klip_yayin.py liste                  aday klip/derlemeleri tarar, TEK yerel HTML üretir (onay/index.html)
  py tools/klip_yayin.py onayla 3 7 ...         listedeki numaraları (ya da paket yollarını) onaylar
  py tools/klip_yayin.py onayla 12 --kucuk-resim 2   derleme için küçük resim seçer
  py tools/klip_yayin.py geri-cek 3             onayı geri alır (sunucudaki dosya silinmez)
  py tools/klip_yayin.py yukle [--kuru]         onaylı klipleri medya sunucusuna yükler (--kuru: yalnız yazdırır)
  py tools/klip_yayin.py durum                  manifestin özeti
  py tools/klip_yayin.py otomatik-gizli [--kuru] [--en-cok N]   (sosyal/ayarlar.json klip.otomatik_gizli açıkken) Cio onayını beklemeden
                                                yeni klipleri onay.otomatik=true ile onaylar, sunucuya yükler, klipler.json'ı push eder, sosyal.yml
                                                turunu başlatır (YouTube'a HER ZAMAN gizli) ve en az 1 gizli Shorts yüklendiyse Telegram'a tek mesaj yollar.
                                                Gizliyi herkese açmak Cio'nun işidir (YouTube Studio). Günlük otomatik klip işinin sonunda kendiliğinden çalışır.
  py tools/klip_yayin.py sayfa [--kapi 8765] [--acma]   yerel onay sayfası: Onayla / Onayı geri al düğmeleri
                                                (yalnız 127.0.0.1; yükleme ya da paylaşım yapmaz; --acma tarayıcıyı AÇMAZ)

Onaysız hiçbir klip paylaşılmaz: sosyal_yayinla.py yalnız `onay` + `yayinda` kaydı geçerli olan öğeleri görür.
(`onay.otomatik: true` onayı yalnız gizli yüklemeye gider; elle onay her zaman eskisi gibi herkese açık akıştır.)
Onay, onay anındaki paket+mp4 özetine bağlıdır; dosya sonradan değişirse `yukle` onayı düşürür.
"""
from __future__ import annotations

import argparse
import copy
import datetime
import hmac
import html
import http.server
import json
import os
import pathlib
import queue
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser

KOK = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK / "tools"))
import klip_duzenle as kd  # noqa: E402
import klip_kilit as kk  # noqa: E402
import klip_panel_ui as ui  # noqa: E402
import klip_sosyal as ks  # noqa: E402
import klip_yayincilar as ky_y  # noqa: E402
import klip_yayinla as ky_l  # noqa: E402
import sosyal_yayinla as sy  # noqa: E402
import klip_yayinci_ui as yui  # noqa: E402
import yayin_klip as yk  # noqa: E402

YUKLEME_HEDEFI_VARSAYILAN = "oracle:/var/www/medya/v/"
HEDEF_DESEN = re.compile(r"^(?:[A-Za-z0-9._-]+@)?[A-Za-z0-9._-]+:[A-Za-z0-9._/~-]*$")
# Aynı yayın anının varyantları: küçük sayı = tercih edilen (listede görünür), büyük = "listede yok" notuyla gösterilir.
ONCELIK = (("konusma-hizali", 0), ("konusma-ek", 2), ("konusma", 1), ("canli", 3), ("klip", 4))
KAPAK_AZAMI_BAYT = 2 * 1024 * 1024
KUCUK_RESIM_DESEN = "kucuk-resim-*.png"


class Hata(Exception):
    pass


# ---------------------------------------------------------------- yollar ve ayar
def manifest_yolu(arg: str | None = None) -> pathlib.Path:
    return pathlib.Path(arg or os.environ.get("KLIP_MANIFEST") or ks.MANIFEST_YOLU)


def onay_dizini() -> pathlib.Path:
    return yk.calisma_dizini() / "onay"


def liste_yolu() -> pathlib.Path:
    return onay_dizini() / "liste.json"


def sosyal_ayar_oku() -> dict:
    try:
        ham = json.loads((KOK / "sosyal" / "ayarlar.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return ham if isinstance(ham, dict) else {}


def sosyal_saklama_dizini() -> pathlib.Path:
    """sosyal_kurulum.py'nin Windows şifreli (DPAPI) saklama klasörü; KLIP_SOSYAL_SAKLA ile değişir (test)."""
    return pathlib.Path(os.environ.get("KLIP_SOSYAL_SAKLA")
                        or (pathlib.Path(os.environ.get("LOCALAPPDATA", str(pathlib.Path.home()))) / "rockstargtavi-sosyal"))


def klip_hesabi_durumu(ayar: dict | None = None, sosyal: dict | None = None, sakla: pathlib.Path | None = None) -> dict:
    """Klip hesabı (ayrı kanal) bu bilgisayardan görünen durumu. GitHub sırlarını ölçmez (ağ yok): kurulum aracı bağlayınca
    yerelde `yt_klip.bin` / `ig_klip.bin` yazar ve ayarlar.json klip.youtube / klip.instagram açılır; ikisi birlikte 'bağlı' sayılır.
    ad: videodaki marka yazısı (ayar.marka_yazi) ya da yoksa 'klip kanalı'."""
    ayar = ayar if ayar is not None else ayar_oku()
    sosyal = sosyal if sosyal is not None else sosyal_ayar_oku()
    sakla = sakla or sosyal_saklama_dizini()
    klip = sosyal.get("klip") if isinstance(sosyal.get("klip"), dict) else {}
    ad = yk.marka_yazisi(ayar.get("ayar")) or "klip kanalı"
    yt = bool(klip.get("youtube", True)) and (sakla / f"yt_{ks.KLIP_HESABI}.bin").exists()
    ig = bool(klip.get("instagram", False)) and (sakla / f"ig_{ks.KLIP_HESABI}.bin").exists()
    return {"ad": ad, "youtube": yt, "instagram": ig}


def klip_hesabi_kutusu(h: dict) -> str:
    """Panelin üstündeki kanal satırı; bağlı değilse uyarı (klipler HİÇBİR hesaba gitmez)."""
    durum = "bağlı" if h["youtube"] else "bağlı değil"
    s = (f'<p class=klip-hesap data-bagli="{"evet" if h["youtube"] else "hayir"}">Klipler şu kanalda paylaşılır: '
         f'<b>{esc(h["ad"])}</b> ({durum})</p>')
    if not h["youtube"]:
        s += ('<p class=uyari role=alert>Klip kanalı bağlı değil: onaylanan klipler şu an HİÇBİR hesaba gitmez '
              '(CTRL+A GAME kanalına da gitmez). Bağlamak için <code>sosyal\\kurulum.bat</code> &rarr; "YouTube kanalı bağla (Shorts; klip kanalı için KLİP seç)" '
              '&rarr; KLİP.</p>')
    return s


def ayar_oku() -> dict:
    try:
        return yk.ayar_yukle()
    except Exception:  # noqa: BLE001 — ayar bozuksa kısa ad/yasak kelime olmadan sürer
        return {"ayar": {}, "yayincilar": []}


def json_oku(yol: pathlib.Path) -> dict | None:
    try:
        ham = json.loads(pathlib.Path(yol).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return ham if isinstance(ham, dict) else None


# ---------------------------------------------------------------- tarama
def oncelik(json_yol: pathlib.Path) -> int:
    ad = json_yol.stem
    for onek, n in ONCELIK:
        if ad.startswith(onek):
            return n
    return 5


def paket_dosyalari(d: pathlib.Path) -> list[tuple[str, pathlib.Path, pathlib.Path]]:
    """(tur, json, mp4). ESKI-* klasörleri, deneme-* derlemeleri ve `_` ile başlayanlar atlanır."""
    sonuc = []
    for y in yk.paket_yollari(d):
        if any(p.lower().startswith("eski-") for p in y.relative_to(d).parts):
            continue
        sonuc.append(("klip", y, y.with_suffix(".mp4")))
    kok = d / "derleme"
    if kok.is_dir():
        for y in sorted(kok.glob("*/derleme.json")):
            ad = y.parent.name
            if ad.startswith(("deneme-", "_")) or ad.lower().startswith("eski-"):
                continue
            mp4 = y.with_name("derleme.mp4")
            if mp4.exists():
                sonuc.append(("derleme", y, mp4))
    return sonuc


def duzenleme_uygula(oge: dict) -> None:
    """Paketin yanındaki `.duzenleme.json` varsa metni/platformu ona çevirir (kalıcı elle düzenleme). Otomatik metin saklanır."""
    dz = kd.oku(oge["json"])
    oge["duzenleme"] = dz
    oge["otomatik_metin"] = {k: (list(v) if isinstance(v, list) else v) for k, v in oge["metin"].items()}
    varsayilan = kd.varsayilan_platformlar(oge["tur"])
    oge["platformlar"] = dict(dz.get("platformlar") or varsayilan)
    if oge["tur"] == "derleme":
        oge["platformlar"]["instagram"] = False  # derleme yalnız YouTube'a gider
    oge["elle"] = []
    if dz.get("metin"):
        oge["metin"] = {**dz["metin"], "uyarilar": []}
        oge["elle"].append("metin")
    if dz.get("platformlar") and oge["platformlar"] != varsayilan:
        oge["elle"].append("platform")
    if dz.get("video"):
        oge["elle"].append("video")


def tara(d: pathlib.Path | None = None, ayar: dict | None = None) -> list[dict]:
    """Bütün klip/derleme paketlerini öğe sözlüğü olarak döndürür (varyant tekilleştirmesi `tekillestir`te)."""
    d = d or yk.calisma_dizini()
    ayar = ayar if ayar is not None else ayar_oku()
    ek_yasak = tuple((ayar.get("ayar") or {}).get("aciklama_yasak_kelimeler") or ())
    ogeler = []
    for tur, json_yol, mp4 in paket_dosyalari(d):
        if kd.oku(json_yol).get("gizli"):
            continue
        paket = json_oku(json_yol)
        if not paket:
            continue
        if tur == "klip" and not paket.get("yayinci"):
            continue
        oge = {"tur": tur, "json": json_yol, "mp4": mp4, "paket": paket, "goreli": json_yol.relative_to(d).as_posix(),
               "uyarilar": [], "yok_notu": "", "kufur": False}
        if tur == "klip":
            oge["id"] = ks.klip_id(json_yol)
            oge["oncelik"] = oncelik(json_yol)
            kisa = yk.yayinci_kisa_ad(ayar, paket)
            oge["metin"] = ks.klip_metni(paket, kisa, ek_yasak, ayar.get("ayar"))
            oge["kisa_ad"] = kisa
            duzenleme_uygula(oge)
            oge["yayinci"] = paket.get("yayinci") or ""
            oge["oyun"] = paket.get("oyun") or ""
            oge["kanal_url"] = paket.get("kanal_url") or ""
            oge["sure"] = (paket.get("video") or {}).get("sure_sn")
            oge["yayin_tarihi"] = paket.get("yayin_tarihi") or ""
            v = paket.get("video") or {}
            if (v.get("genislik") or 0) < 1080 or (v.get("yukseklik") or 0) < 1920:
                oge["uyarilar"].append(f"kaynak 1080p değil ({v.get('genislik')}x{v.get('yukseklik')})")
            if ks.kufur_var(str(paket.get("dokum_metni") or ""), ek_yasak):
                oge["uyarilar"].append("konuşmada küfür geçiyor (dökümde)")
                oge["kufur"] = True
            elif not paket.get("dokum_metni"):
                oge["uyarilar"].append("döküm yok: konuşmadaki küfür denetlenemedi, klibi dinle")
            oge["uyarilar"] += oge["metin"].get("uyarilar") or []
            oge["kufur"] = oge["kufur"] or bool(oge["metin"].get("uyarilar"))
            if "metin" in oge["elle"] and ks.kufur_var(oge["metin"]["baslik"] + " " + oge["metin"]["aciklama"], ek_yasak):
                oge["uyarilar"].append("elle yazılan başlıkta/açıklamada küfür var")
                oge["kufur"] = True
            oge["kucuk_resimler"] = []
        else:
            oge["id"] = ks.derleme_id(json_yol.parent)
            oge["oncelik"] = 0
            oge["metin"] = ks.derleme_metni(paket, ek_yasak, ayar.get("ayar"))
            duzenleme_uygula(oge)
            oge["yayinci"] = "Yayın kolajı"
            oge["oyun"] = ""
            oge["kanal_url"] = ""
            oge["sure"] = paket.get("sure_sn")
            oge["yayin_tarihi"] = str(paket.get("yayinlandi") or "")[:10]
            if str(paket.get("cozunurluk") or "") != "1920x1080":
                oge["uyarilar"].append(f"çözünürlük 1920x1080 değil ({paket.get('cozunurluk')})")
            if ks.kufur_var(oge["metin"]["baslik"] + "\n" + oge["metin"]["aciklama"], ek_yasak):
                oge["uyarilar"].append("başlıkta/açıklamada küfür var")
                oge["kufur"] = True
            oge["kucuk_resimler"] = sorted(json_yol.parent.glob(KUCUK_RESIM_DESEN))
            if not oge["kucuk_resimler"]:
                oge["uyarilar"].append("küçük resim yok")
            for u in paket.get("uyarilar") or []:
                oge["uyarilar"].append(f"derleme uyarısı: {ks.sade(u)}")
        ogeler.append(oge)
    return tekillestir(ogeler)


def _sira_anahtari(o: dict) -> tuple:
    """Klipler önce, derlemeler sonra; her biri yayın tarihine göre en yeniden en eskiye, aynı günde dosya sırasıyla."""
    t = re.sub(r"\D", "", str(o.get("yayin_tarihi") or ""))[:8]
    return (o["tur"] != "klip", -int(t) if len(t) == 8 else 0, o["goreli"])


def tekillestir(ogeler: list[dict]) -> list[dict]:
    """Aynı yayın anını gösteren klip varyantlarından yalnız en iyisi öne çıkar; öbürleri `yok_notu` alır."""
    sirali = sorted(ogeler, key=lambda o: (o["tur"] != "klip", o["oncelik"], o["goreli"]))
    secilen: list[dict] = []
    for o in sirali:
        if o["tur"] == "klip":
            es = next((s for s in secilen if s["tur"] == "klip" and ks.ortusuyor(s["paket"], o["paket"])), None)
            if es is not None:
                o["yok_notu"] = f"aynı anın başka sürümü listede: {es['goreli']}"
        secilen.append(o)
    return sorted(ogeler, key=_sira_anahtari)


_ONBELLEK: dict | None = None  # yalnız `sayfa` sunucusu açar: (yollar, boyut, değişim zamanı) -> özet


def _sha(*yollar) -> str:
    if _ONBELLEK is None:
        return ks.sha_dosyalar(*yollar)
    anahtar = []
    for y in yollar:
        st = os.stat(y)
        anahtar.append((str(y), st.st_size, st.st_mtime_ns))
    anahtar = tuple(anahtar)
    if anahtar not in _ONBELLEK:
        _ONBELLEK[anahtar] = ks.sha_dosyalar(*yollar)
    return _ONBELLEK[anahtar]


def ozet_taban(o: dict) -> str:
    return _sha(o["json"], o["mp4"])


def kucuk_resim_sec(o: dict, secim: int | None) -> pathlib.Path | None:
    if o["tur"] != "derleme":
        return None
    kr = o["kucuk_resimler"]
    if not kr:
        raise Hata("derlemede küçük resim yok (kucuk-resim-*.png)")
    n = secim or 1
    if not 1 <= n <= len(kr):
        raise Hata(f"küçük resim numarası 1-{len(kr)} olmalı")
    return kr[n - 1]


def ozet_onay(o: dict, kucuk: pathlib.Path | None = None) -> str:
    yollar = [o["json"], o["mp4"]] + ([kucuk] if kucuk else [])
    return _sha(*yollar)


# ---------------------------------------------------------------- durum
def durum_metni(o: dict, manifest: dict) -> tuple[str, str]:
    """(kısa etiket, sınıf)."""
    kayit = (manifest.get("ogeler") or {}).get(o["id"])
    if not kayit or not kayit.get("onay"):
        return "Henüz onaylanmadı", "yok"
    kucuk = None
    ad = kayit["onay"].get("kucuk_resim")
    if ad:
        kucuk = o["json"].parent / ad
    try:
        guncel = ozet_onay(o, kucuk)
    except OSError:
        return "Onay düştü: dosya okunamadı", "dustu"
    if guncel != kayit["onay"].get("ozet"):
        return "Onay düştü: paket ya da video değişmiş", "dustu"
    if kayit.get("beklet"):
        return "Bekletiliyor", "bekle"
    if ks.yayinda_gecerli(kayit):
        paylasim = [p for p in ("instagram", "youtube") if kayit.get(p)]
        if paylasim:
            return "Paylaşıldı: " + ", ".join(paylasim), "paylasildi"
        return "Onaylı, medya sunucusunda; paylaşım sırası bekleniyor", "yayinda"
    return "Onaylı, medya sunucusuna yüklenmeyi bekliyor (yukle)", "onayli"


# ---------------------------------------------------------------- liste
def liste_kaydi_oku() -> dict:
    ham = json_oku(liste_yolu()) or {}
    ham.setdefault("sonraki", 1)
    ham.setdefault("ogeler", {})
    return ham


def numaralari_ata(kayit: dict, ogeler: list[dict]) -> None:
    """Numaralar kalıcıdır: bir paket yolu hep aynı numarayı alır; numara yeniden kullanılmaz."""
    yol_no = {v["paket"]: no for no, v in kayit["ogeler"].items()}
    for o in ogeler:
        if o["yok_notu"]:
            o["no"] = None
            continue
        no = yol_no.get(o["goreli"])
        if no is None:
            no = str(kayit["sonraki"])
            kayit["sonraki"] += 1
        o["no"] = no
        kayit["ogeler"][no] = {"paket": o["goreli"], "id": o["id"], "ozet": ozet_taban(o)}


ONAYLI_SINIFLAR = ("onayli", "yayinda", "paylasildi", "bekle")
BASLATICI_AD = "Onay Sayfası.bat"


def dosya_url(yol: pathlib.Path) -> str:
    """Sayfa sunucusunda dosya adresi: çalışma dizinine göreli, yüzde-kodlu."""
    return "/dosya/" + urllib.parse.quote(yol.relative_to(yk.calisma_dizini()).as_posix(), safe="/")


def ozet_sayilari(ogeler: list[dict], manifest: dict) -> dict:
    listede = [o for o in ogeler if not o["yok_notu"]]
    siniflar = [durum_metni(o, manifest)[1] for o in listede]
    return {"toplam": len(listede), "onayli": sum(1 for x in siniflar if x in ONAYLI_SINIFLAR),
            "bekleyen": sum(1 for x in siniflar if x == "onayli"), "dusen": sum(1 for x in siniflar if x == "dustu"),
            "kufur": sum(1 for o in listede if o["kufur"]), "elle": sum(1 for o in listede if o.get("elle"))}


def esc(x) -> str:
    return html.escape(str(x if x is not None else ""))


ELLE_ADLARI = {"metin": "metin", "platform": "platform seçimi", "video": "video"}


def _yazi_metni(v) -> str:
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        return str(v.get("metin") or v.get("yazi") or "")
    return ""


def video_ilk_degerler(o: dict, ayar_duzen: str) -> dict:
    """Video-üstü formunun başlangıç değerleri: son istenen (sidecar) ya da paketten/ayardan."""
    v = (o.get("duzenleme") or {}).get("video") or {}
    paket = o["paket"]
    kutu = v.get("kamera_kutu")
    return {
        "aciklama_metni": v["aciklama_metni"] if "aciklama_metni" in v else (_yazi_metni(paket.get("aciklama_yazisi")) or str(paket.get("kisa_aciklama") or "")),
        "oyun": v["oyun"] if "oyun" in v else str(paket.get("oyun") or ""),
        "yayinci_adi": v["yayinci_adi"] if "yayinci_adi" in v else str(o.get("kisa_ad") or o.get("yayinci") or ""),
        "duzen": v["duzen"] if v.get("duzen") in kd.DUZENLER else (ayar_duzen if ayar_duzen in kd.DUZENLER else "kamera"),
        "kamera_kutu": [str(x) for x in kutu] if isinstance(kutu, list) and len(kutu) == 4 else ["", "", "", ""],
    }


def kesim_kutusu(durum: dict | None) -> str:
    if not durum:
        return ""
    return f'<p class=kesim data-durum="{esc(durum["durum"])}" role=status>{esc(durum["mesaj"])}</p>'


def duzen_paneli(o: dict, kesim: dict | None, acik: bool, ayar_duzen: str, hesap: dict | None = None) -> str:
    no = esc(o["no"])
    hesap = hesap or klip_hesabi_durumu()
    klip = o["tur"] == "klip"
    m, pl = o["metin"], o["platformlar"]
    S = kd.SINIRLAR
    aktif = bool(kesim and kesim["durum"] in ("kuyrukta", "kesiliyor"))
    if klip:
        # Klip Instagram hesabı (IG_KLIP_*) yoksa seçenek kapalı: işaret durumu DEĞİŞMEZ (kaydetme platform seçimini bozup onayı düşürmesin)
        ig_kapali = not hesap["instagram"]
        ig_not = (' <span class=kucuk>(klip Instagram hesabı bağlı değil, Instagram\'a gitmez; bağlayınca açılır)</span>' if ig_kapali else "")
        plat = (f'<label class=anahtar><input type=checkbox name=p_instagram{" checked" if pl["instagram"] else ""}{" disabled" if ig_kapali else ""}> Instagram Reel{ig_not}</label>'
                f'<label class=anahtar><input type=checkbox name=p_youtube{" checked" if pl["youtube"] else ""}> YouTube Short ({esc(hesap["ad"])})</label>')
        sayac_ig = f'<span class=s-ig>Instagram açıklaması <b>0</b>/{S["ig_aciklama"]}</span>'
    else:
        plat = '<label class=anahtar><input type=checkbox name=p_youtube checked disabled> YouTube (derleme yalnız YouTube\'a gider)</label>'
        sayac_ig = ""
    metin = f"""<fieldset class=metin data-ig-acik="{S['ig_aciklama']}" data-yt-baslik="{S['yt_baslik']}" data-yt-acik="{S['yt_aciklama_karakter']}">
<legend>Paylaşım metni <span class=kucuk>(video yeniden kesilmez)</span></legend>
<label for="b{no}">Başlık <span class="say say-baslik"></span></label>
<input type=text id="b{no}" name=baslik value="{esc(m['baslik'])}" autocomplete=off>
<label for="a{no}">Açıklama</label>
<textarea id="a{no}" name=aciklama rows=6>{esc(m['aciklama'])}</textarea>
<label for="e{no}">Etiketler <span class=kucuk>(boşlukla ayır; # kendiliğinden eklenir)</span></label>
<input type=text id="e{no}" name=etiketler value="{esc(' '.join(m['etiketler']))}" autocomplete=off>
<p><b>Nereye paylaşılsın?</b></p>
{plat}
<div class=sayaclar>{sayac_ig}<span class=s-ytb>YouTube başlığı <b>0</b>/{S['yt_baslik']}</span><span class=s-yta>YouTube açıklaması <b>0</b>/{S['yt_aciklama_karakter']}</span></div>
<div class=islem><button type=button class="birincil metin-kaydet">Metni kaydet</button>
<button type=button class="tehlike metin-sifirla"{'' if 'metin' in o.get('elle', []) else ' disabled'}>Otomatik metne dön</button></div>
<p class=hata role=alert hidden></p><p class=tamam role=status hidden></p>
</fieldset>"""
    video = ""
    if klip:
        ilk = video_ilk_degerler(o, ayar_duzen)
        b0, b1 = o["paket"].get("klip_baslangic_sn"), o["paket"].get("klip_bitis_sn")
        secenek = [("kamera", "Kamera + oyun (iki panel)"), ("kadraj", "Tek panel")]
        if ilk["duzen"] == "serit":
            secenek.append(("serit", "Şerit"))
        opt = "".join(f'<option value="{k}"{" selected" if k == ilk["duzen"] else ""}>{esc(a)}</option>' for k, a in secenek)

        def adim(alan: str) -> str:
            return (f'<div class=kaydir><button type=button class=adim data-adim="-2">−2</button><button type=button class=adim data-adim="-0.5">−0,5</button>'
                    f'<input type=number step=0.1 inputmode=decimal name={alan} value=0 aria-label="saniye">'
                    f'<button type=button class=adim data-adim="0.5">+0,5</button><button type=button class=adim data-adim="2">+2</button></div>')
        kutu = "".join(f'<input type=number step=any min=0 max=1 inputmode=decimal name={n} value="{esc(v)}" placeholder="{p}" aria-label="{p}">'
                       for n, v, p in zip(("kx", "ky", "kw", "kh"), ilk["kamera_kutu"], ("x", "y", "genişlik", "yükseklik")))
        video = f"""<fieldset class=video data-yazi-sinir="{S['aciklama_yazisi']}" data-bas="{esc(b0 if isinstance(b0, (int, float)) else '')}" data-son="{esc(b1 if isinstance(b1, (int, float)) else '')}">
<legend>Video üstündekiler <span class=kucuk>(yeniden kesim gerekir; 20-60 sn sürer)</span></legend>
<label for="va{no}">Video üstü kısa açıklama <span class="say say-yazi"></span></label>
<input type=text id="va{no}" name=aciklama_metni value="{esc(ilk['aciklama_metni'])}" data-ilk="{esc(ilk['aciklama_metni'])}" autocomplete=off>
<p class=kucuk>Boş bırakırsan videoda yazı olmaz.</p>
<label for="vo{no}">Oyun adı</label>
<input type=text id="vo{no}" name=oyun value="{esc(ilk['oyun'])}" data-ilk="{esc(ilk['oyun'])}" autocomplete=off>
<p class=kucuk>Boş bırakırsan oyun adı yazılmaz.</p>
<label for="vy{no}">Yayıncı adı</label>
<input type=text id="vy{no}" name=yayinci_adi value="{esc(ilk['yayinci_adi'])}" data-ilk="{esc(ilk['yayinci_adi'])}" autocomplete=off>
<label>Başlangıcı kaydır (saniye; + ileri, − geri)</label>{adim('bas_kaydir')}
<label>Bitişi kaydır (saniye; + uzatır, − kısaltır)</label>{adim('son_kaydir')}
<p class="kucuk sure-yeni"></p>
<label for="vd{no}">Düzen</label>
<select id="vd{no}" name=duzen data-ilk="{esc(ilk['duzen'])}">{opt}</select>
<details><summary>Gelişmiş: kamera kutusu</summary>
<p class=kucuk>Kameranın yerini elle göster: x, y, genişlik, yükseklik (görüntünün 0 ile 1 arası oranları). Boş bırakırsan kendiliğinden bulunur.</p>
<div class=kutu4 data-ilk="{esc(','.join(ilk['kamera_kutu']) if any(ilk['kamera_kutu']) else '')}">{kutu}</div></details>
<div class=islem><button type=button class="birincil kesim-baslat"{' disabled' if aktif else ''}>Kaydet ve yeniden kes</button></div>
<p class=hata role=alert hidden></p><p class=tamam role=status hidden></p>
</fieldset>"""
    return f'<div class=duzenle{"" if acik else " hidden"}>{metin}{video}</div>'


def kart_uret(o: dict, manifest: dict, etk: dict | None = None, hesap: dict | None = None) -> str:
    """Tek kartın HTML'i. `etk` verilirse (sayfa sunucusu) düğmeli + düzenlemeli; yoksa durağan (file://) kart."""
    etiket, sinif = durum_metni(o, manifest)
    m = o["metin"]
    v = o["paket"]
    dikey = o["tur"] == "klip"
    uyari = "".join(f"<li>{esc(u)}</li>" for u in o["uyarilar"])
    kufur = o["kufur"]
    sure = o.get("sure")
    sure_s = f"{float(sure):.0f} sn" if isinstance(sure, (int, float)) else ""
    bilgi = [("Yayıncı", o["yayinci"]), ("Oyun", o["oyun"]), ("Yayın tarihi", o["yayin_tarihi"]), ("Süre", sure_s)]
    if o["tur"] == "klip":
        bilgi.append(("Konuşma puanı", v.get("konusma_puani") if v.get("konusma_puani") is not None else "—"))
    satir = "".join(f"<tr><th>{esc(a)}</th><td>{esc(b)}</td></tr>" for a, b in bilgi if b not in ("", None))
    kaynak = o["kanal_url"]
    kaynak_html = f'<a href="{esc(kaynak)}">{esc(kaynak)}</a>' if kaynak.startswith("https://") else ""
    kisa = v.get("kisa_aciklama") or v.get("baslik") or m["baslik"]
    dokum = str(v.get("dokum_metni") or "").strip()
    kr = ""
    if etk and o["tur"] == "derleme" and o["kucuk_resimler"]:
        kayit_o = (manifest.get("ogeler") or {}).get(o["id"]) or {}
        secili = (kayit_o.get("onay") or {}).get("kucuk_resim") or (o.get("duzenleme") or {}).get("kucuk_resim")
        kr = "<p><b>Küçük resim seç</b> (seçmeden onaylanamaz; değiştirirsen onay düşer)</p><div class=kr>" + "".join(
            f'<label class=krsec><input type=radio name="kr{esc(o["no"])}" value="{i}"{" checked" if k.name == secili else ""}>'
            f'<img loading=lazy src="{esc(dosya_url(k))}" alt="küçük resim {i}"><span>{i}</span></label>'
            for i, k in enumerate(o["kucuk_resimler"], 1)) + "</div>"
    elif o["tur"] == "derleme" and o["kucuk_resimler"]:
        kr = "<p><b>Küçük resim seçenekleri</b> (onay için numara seç: <code>--kucuk-resim N</code>)</p><div class=kr>" + "".join(
            f'<figure><img loading=lazy src="{esc(k.as_uri())}" alt="küçük resim {i}"><figcaption>{i}</figcaption></figure>'
            for i, k in enumerate(o["kucuk_resimler"], 1)) + "</div>"
    komut = (f"py tools/klip_yayin.py onayla {o['no']}" + (" --kucuk-resim 1" if o["tur"] == "derleme" else ""))
    rozetler = ""
    if kufur:
        rozetler += ' <span class=kufurrozet>KÜFÜR UYARISI</span>'
    if o.get("elle"):
        ad = ", ".join(ELLE_ADLARI.get(x, x) for x in o["elle"])
        rozetler += f' <span class=ellerozet title="Elle düzenlenen: {esc(ad)}">ELLE DÜZENLENDİ</span>'
    pl = o.get("platformlar") or {}
    if dikey and pl.get("instagram") != pl.get("youtube"):
        rozetler += f' <span class=platrozet>yalnız {"Instagram" if pl.get("instagram") else "YouTube"}</span>'
    kesim = ((etk or {}).get("kesimler") or {}).get(o["id"])
    aktif = bool(kesim and kesim["durum"] in ("kuyrukta", "kesiliyor"))
    duzen_dugme = ""
    panel = ""
    if etk:
        video_url = dosya_url(o["mp4"])
        try:
            video_url += f"?s={o['mp4'].stat().st_mtime_ns}"  # yeniden kesilince tarayıcı eski videoyu göstermesin
        except OSError:
            pass
        onayli = sinif in ONAYLI_SINIFLAR
        acik = o["id"] in ((etk or {}).get("acik") or ())
        panel = duzen_paneli(o, kesim, acik, str(((etk.get("ayar") or {}).get("ayar") or {}).get("duzen") or ""), hesap)
        alt = (f'<div class=islem><button type=button class=onayla{" disabled" if aktif else ""}>Onayla</button>'
               '<button type=button class=geri>Onayı geri al</button>'
               f'<button type=button class=duzen-ac aria-expanded="{"true" if acik else "false"}">{"Düzenlemeyi kapat" if acik else "Düzenle"}</button>'
               f'<button type=button class="tehlike kaldir"{" disabled" if aktif else ""}>Kaldır</button></div>'
               '<p class=hata role=alert hidden></p><p class=tamam role=status hidden></p>')
    else:
        video_url = o["mp4"].as_uri()
        onayli = False
        alt = f"<p class=ipucu>Onay için asistana yaz: <code>{esc(komut)}</code> (butonlar için: {esc(BASLATICI_AD)})</p>"
    return f"""<article class="kart {sinif}{' kufur' if kufur else ''}" id="k{esc(o['no'])}" data-no="{esc(o['no'])}" data-tur="{esc(o['tur'])}" data-kufur="{'1' if kufur else '0'}" data-onayli="{'evet' if onayli else 'hayir'}" data-sinif="{sinif}" data-yayinci="{esc(o['yayinci'])}" data-elle="{'1' if o.get('elle') else '0'}">
<h3><span class=no>{esc(o['no'])}</span> {esc(kisa)}{rozetler}</h3>
<p class="durum {sinif}"><span class=etiket>{esc(etiket)}</span></p>
{kesim_kutusu(kesim)}
<div class="govde{' dikey' if dikey else ''}">
<video controls preload="metadata" {'height=480' if dikey else 'width=560'} src="{esc(video_url)}"></video>
<div class=yan>
<table>{satir}</table>
{('<ul class=uyari>' + uyari + '</ul>') if uyari else ''}
<p><b>Paylaşılacak başlık</b><br>{esc(m['baslik'])}</p>
<p><b>Paylaşılacak açıklama</b></p><pre>{esc(m['aciklama'])}</pre>
<p><b>Etiketler</b> {esc(' '.join(m['etiketler']))}</p>
<p><b>Kaynak</b> {kaynak_html}</p>
</div></div>
{kr}
{('<details><summary>Konuşma dökümü</summary><pre>' + esc(dokum) + '</pre></details>') if dokum else ''}
{alt}
{panel}
</article>"""


def html_uret(ogeler: list[dict], manifest: dict, zaman: str, etk: dict | None = None, hesap: dict | None = None) -> str:
    """`etk` verilirse (sayfa sunucusu) düğmeli canlı sayfa; yoksa durağan liste (file:// adresleri).
    `hesap`: klip hesabı durumu (klip_hesabi_durumu); verilmezse yerelden ölçülür."""
    hesap = hesap or klip_hesabi_durumu((etk or {}).get("ayar"))
    kart = lambda o: kart_uret(o, manifest, etk, hesap)  # noqa: E731
    klipler = [o for o in ogeler if o["tur"] == "klip" and not o["yok_notu"]]
    derlemeler = [o for o in ogeler if o["tur"] == "derleme"]
    gizli = [o for o in ogeler if o["yok_notu"]]
    kufurlu = sum(1 for o in klipler + derlemeler if o["kufur"])
    govde = [f"<h2>Klipler (dikey, Reels + Shorts) — {len(klipler)} adet</h2>"]
    govde += [kart(o) for o in klipler] or ["<p>Klip yok.</p>"]
    govde += [f"<h2>Derlemeler (yatay, yalnız YouTube) — {len(derlemeler)} adet</h2>"]
    govde += [kart(o) for o in derlemeler] or ["<p>Derleme yok.</p>"]
    if gizli:
        govde.append(f"<h2>Listede yok ({len(gizli)}): aynı anın başka sürümü zaten listede</h2><ul>" + "".join(
            f"<li>{esc(o['goreli'])} — {esc(o['yok_notu'])}</li>" for o in gizli) + "</ul>")
    if etk:
        sy = ozet_sayilari(ogeler, manifest)
        yayincilar = sorted({o["yayinci"] for o in klipler + derlemeler if o["yayinci"]}, key=str.casefold)
        secenek = '<option value="">Tüm yayıncılar</option>' + "".join(f'<option value="{esc(y)}">{esc(y)}</option>' for y in yayincilar)
        ust = (f'<div id=ozet class=ozet><span><b id=s-onayli>{sy["onayli"]}</b> onaylı</span> · '
               f'<span><b id=s-bekleyen>{sy["bekleyen"]}</b> yüklenmeyi bekliyor</span> · '
               f'<span><b id=s-kufur>{sy["kufur"]}</b> küfür uyarılı</span> · '
               f'<span><b id=s-elle>{sy["elle"]}</b> elle düzenlenmiş</span> · '
               f'<span><b id=s-toplam>{sy["toplam"]}</b> öğe</span></div>'
               '<div class=suzgec role=group aria-label="Süzgeç">'
               '<button type=button data-suz=hepsi aria-pressed=true>Hepsi</button>'
               '<button type=button data-suz=onayli aria-pressed=false>Onaylı</button>'
               '<button type=button data-suz=kufur aria-pressed=false>Küfür uyarılı</button>'
               f'<select id=suz-yayinci aria-label="Yayıncıya göre">{secenek}</select>'
               '<span id=suz-sayi class=kucuk></span></div>'
               '<p class=not><b>Onay yalnız işaretler; paylaşım için yükleme ve gönderim ayrı adımdır.</b> '
               'Kırmızı çerçeveli kartlarda küfür uyarısı var: önce dinle. '
               'Bir kartta <b>Düzenle</b>ye basarak metni, platformu ve video üstündekileri değiştirebilirsin; onaylı bir kartı düzenlersen onayı düşer.</p>')
        betik = ui.BETIK
        belirtec = f'<meta name="belirtec" content="{esc(etk["belirtec"])}">'
    else:
        ust = (f'<p>Hazırlanma: {esc(zaman)} · {len(klipler)} klip, {len(derlemeler)} derleme · küfür uyarılı: {kufurlu}.</p>\n'
               '<p><b>Butonlar için: Onay Sayfası.bat</b> dosyasına çift tıkla (bu klasörde). Ya da onaylamak istediklerinin numarasını asistana yaz. '
               'Onaylamadığın hiçbir klip paylaşılmaz. '
               'Kırmızı çerçeveli kartlarda küfür uyarısı var: önce dinle.</p>')
        betik = ""
        belirtec = ""
    if etk:  # canlı sayfa: Klipler / Yayıncılar sekmeleri
        icerik = "\n".join([yui.SEKMELER, "<div id=sekme-klipler>", ust, "".join(govde), "</div>", yui.BOLUM])
        css, betik = ui.CSS + yui.CSS, betik + yui.BETIK
    else:
        icerik = "\n".join([ust, "".join(govde)])
        css = ui.CSS
    return f"""<!doctype html>
<html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
{belirtec}
<title>Klip onay listesi</title>
<style>{css}</style>{betik}</head><body><main>
<h1>Klip onay listesi</h1>
{klip_hesabi_kutusu(hesap)}
{icerik}
</main></body></html>
"""


def komut_liste(args) -> int:
    ogeler, manifest, _kayit, _ayar = liste_hazirla(args.manifest)
    baslatici_yaz()
    zaman = ks.simdi_iso().replace("T", " ").replace("Z", " UTC")
    cikti = onay_dizini() / "index.html"
    cikti.write_text(html_uret(ogeler, manifest, zaman), encoding="utf-8")
    listede = [o for o in ogeler if not o["yok_notu"]]
    klip = sum(1 for o in listede if o["tur"] == "klip")
    der = sum(1 for o in listede if o["tur"] == "derleme")
    kufur = sum(1 for o in listede if o["kufur"])
    dokumsuz = sum(1 for o in listede if any(u.startswith("döküm yok") for u in o["uyarilar"]))
    print(f"listelendi: {klip} klip, {der} derleme; gizlenen varyant: {len(ogeler) - len(listede)}; küfür uyarılı: {kufur}; dökümü olmadığı için denetlenemeyen: {dokumsuz}")
    print(f"sayfa: {cikti}")
    return 0


# ---------------------------------------------------------------- hedef çözme
def hedef_coz(token: str, ogeler: list[dict], kayit: dict) -> dict:
    token = token.strip()
    if token.isdigit():
        k = kayit["ogeler"].get(token)
        if not k:
            raise Hata(f"{token} numarası listede yok; önce `liste` çalıştır")
        o = next((x for x in ogeler if x["goreli"] == k["paket"]), None)
        if o is None:
            raise Hata(f"{token} numaralı paket artık bulunamıyor ({k['paket']}); `liste`yi yeniden çalıştır")
        if ozet_taban(o) != k["ozet"]:
            raise Hata(f"{token} numaralı klip listeden sonra değişmiş; `liste`yi yeniden çalıştırıp yeniden izle")
        return o
    d = yk.calisma_dizini()
    yol = pathlib.Path(token)
    for aday in ((yol if yol.is_absolute() else pathlib.Path.cwd() / yol), d / token):
        try:
            gor = aday.resolve().relative_to(d.resolve()).as_posix()
        except (OSError, ValueError):
            continue
        o = next((x for x in ogeler if x["goreli"] == gor), None)
        if o is not None:
            return o
    o = next((x for x in ogeler if x["id"] == token or x["goreli"] == token.replace("\\", "/")), None)
    if o is None:
        raise Hata(f"bulunamadı: {token}")
    return o


# ---------------------------------------------------------------- onayla / geri-çek
def onayla_bir(o: dict, ogeler: list[dict], manifest: dict, kucuk_no: int | None, ayar: dict, otomatik: bool = False) -> str:
    """otomatik=True: Cio'nun elle onayı yerine `onay.otomatik` işaretli onay (YouTube'a yalnız GİZLİ yüklenir; bkz. otomatik_gizli)."""
    if o["tur"] == "derleme":
        kucuk = kucuk_resim_sec(o, kucuk_no)
    else:
        kucuk = None
        if kucuk_no:
            raise Hata("--kucuk-resim yalnız derleme içindir")
    metin = {"baslik": o["metin"]["baslik"], "aciklama": o["metin"]["aciklama"], "etiketler": list(o["metin"]["etiketler"])}
    ek_yasak = tuple((ayar.get("ayar") or {}).get("aciklama_yasak_kelimeler") or ())
    if ks.kufur_var(metin["baslik"] + "\n" + metin["aciklama"], ek_yasak):
        raise Hata(f"{o['id']}: paylaşım metninde küfür var, onaylanmadı")
    for diger_id, kayit in (manifest.get("ogeler") or {}).items():
        if diger_id == o["id"] or o["tur"] != "klip" or kayit.get("tur") != "klip" or not ks.onay_gecerli(kayit):
            continue
        diger = next((x for x in ogeler if x["id"] == diger_id), None)
        if diger is not None and ks.ortusuyor(diger["paket"], o["paket"]):
            raise Hata(f"{o['id']}: aynı anın başka sürümü ({diger_id}) zaten onaylı; önce onu geri çek")
    ozet = ozet_onay(o, kucuk)
    eski = (manifest["ogeler"].get(o["id"]) or {})
    # platform seçimi yalnız varsayılandan farklıysa manifeste yazılır (yoksa her platform açık sayılır)
    pl = o.get("platformlar")
    pl_yaz = dict(pl) if pl and pl != kd.varsayilan_platformlar(o["tur"]) else None
    if (ks.onay_gecerli(eski) and eski["onay"]["ozet"] == ozet and eski.get("metin") == metin and eski.get("platformlar") == pl_yaz
            and bool(eski["onay"].get("otomatik")) == otomatik):  # elle onay, otomatik gizli onayı AÇIĞA çevirir (ve tersi yapılmaz)
        return f"{o['id']}: zaten onaylı"
    yeni = {k: v for k, v in eski.items() if k in ("instagram", "youtube")}  # eski bağlantılar kalır (çift paylaşımı önler)
    yeni.update({
        "tur": o["tur"], "paket": o["goreli"], "yayinci": o["yayinci"], "oyun": o["oyun"], "kanal_url": o["kanal_url"],
        "sure": o.get("sure"), "yayin_tarihi": o["yayin_tarihi"], "metin": metin,
        "onay": {"zaman": ks.simdi_iso(), "ozet": ozet, "metin_ozeti": ks.metin_ozeti(metin)},
    })
    if otomatik:
        yeni["onay"]["otomatik"] = True
        yeni["otomatik"] = True  # kayıt otomatik akışın: onayı düşse bile yalnız bu işaretle yeniden otomatik onaylanır
    if kucuk is not None:
        yeni["onay"]["kucuk_resim"] = kucuk.name
    if pl_yaz is not None:
        yeni["platformlar"] = pl_yaz
    yeni.pop("otomatik_red", None)
    manifest["ogeler"][o["id"]] = yeni
    return f"{o['id']}: " + ("otomatik onaylandı (gizli)" if otomatik else "onaylandı")


def komut_onayla(args) -> int:
    d = yk.calisma_dizini()
    ayar = ayar_oku()
    ogeler = tara(d, ayar)
    kayit = liste_kaydi_oku()
    yol = manifest_yolu(args.manifest)
    manifest = ks.yukle(yol)
    secilen = [hedef_coz(t, ogeler, kayit) for t in args.hedefler]
    hata = 0
    for o in secilen:
        try:
            print(onayla_bir(o, ogeler, manifest, args.kucuk_resim, ayar))
        except (Hata, RuntimeError, OSError) as e:
            print(f"HATA {o['id']}: {e}")
            hata = 1
    ks.kaydet(manifest, yol)
    return hata


def geri_cek_oge(oge_id: str, manifest: dict) -> str:
    kayit_oge = manifest["ogeler"].get(oge_id)
    if not kayit_oge or not kayit_oge.get("onay"):
        return f"{oge_id}: zaten onaylı değil"
    kayit_oge.pop("onay")
    kayit_oge["otomatik_red"] = True  # Cio geri çekti: otomatik gizli akışı bu klibi bir daha onaylamaz (elle onay bunu temizler)
    return f"{oge_id}: onay geri çekildi (sunucudaki dosyalar silinmedi; paylaşılmış gönderi varsa elle kaldırılır)"


def komut_geri_cek(args) -> int:
    d = yk.calisma_dizini()
    ogeler = tara(d)
    kayit = liste_kaydi_oku()
    yol = manifest_yolu(args.manifest)
    manifest = ks.yukle(yol)
    hata = 0
    for t in args.hedefler:
        try:
            if t in manifest["ogeler"]:
                oge_id = t
            else:
                oge_id = hedef_coz(t, ogeler, kayit)["id"]
        except Hata as e:
            if t.isdigit():
                k = kayit["ogeler"].get(t)
                oge_id = k["id"] if k else None
            else:
                oge_id = None
            if not oge_id or oge_id not in manifest["ogeler"]:
                print(f"HATA {t}: {e}")
                hata = 1
                continue
        print(geri_cek_oge(oge_id, manifest))
    ks.kaydet(manifest, yol)
    return hata


# ---------------------------------------------------------------- yerel onay sayfası (düğmeli)
SAYFA_BETIGI = ui.BETIK  # geri uyum: betik klip_panel_ui.py'de

DOSYA_TURLERI = {".mp4": "video/mp4", ".webm": "video/webm", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
KAPI_VARSAYILAN = 8765
KAPI_DENEME = 20
ISTEK_AZAMI_BAYT = 4096
BLOK_BAYT = 64 * 1024
YAYINCI_GET = ("/api/yayinci/liste", "/api/yayinci/is", "/api/yayinci/yayinla-durum")
YAYINCI_POST = tuple(f"/api/yayinci/{a}" for a in ("onizle", "ekle", "ekle-cikar", "duzenle", "kaldir", "geri-getir", "klip-cikar", "iptal", "yayinla"))
YAYINCI_AZAMI = 8192
DUZENLE_YOLLARI = {"/api/metin-kaydet": ("metin-kaydet", 131072), "/api/metin-sifirla": ("metin-sifirla", 4096),
                   "/api/kesim": ("kesim", 16384), "/api/kucuk-resim": ("kucuk-resim", 4096),
                   "/api/kaldir": ("kaldir", 4096)}
SAYFA_CSP = ("default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src 'self'; "
             "media-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")


def aralik_coz(baslik: str | None, boyut: int):
    """Range başlığı -> None (tam dosya) | (başlangıç, son) | 'yok' (karşılanamaz, 416). Çoklu/bozuk aralık yok sayılır."""
    if not baslik:
        return None
    m = re.fullmatch(r"bytes=(\d*)-(\d*)", baslik.strip())
    if not m or (not m.group(1) and not m.group(2)):
        return None
    bas_s, son_s = m.groups()
    if boyut <= 0:
        return "yok"
    if not bas_s:  # son N bayt
        n = int(son_s)
        if n == 0:
            return "yok"
        return (max(0, boyut - n), boyut - 1)
    bas = int(bas_s)
    son = int(son_s) if son_s else boyut - 1
    if bas >= boyut or son < bas:
        return "yok"
    return (bas, min(son, boyut - 1))


class OnaySunucusu(http.server.ThreadingHTTPServer):
    allow_reuse_address = False  # Windows'ta SO_REUSEADDR dolu kapıya ikinci bağlanmaya izin verir
    daemon_threads = True

    def __init__(self, kapi: int, manifest_arg: str | None):
        super().__init__(("127.0.0.1", kapi), OnayIstegi)
        global _ONBELLEK
        _ONBELLEK = {}
        self.port = self.server_address[1]
        self.belirtec = secrets.token_urlsafe(24)
        self.manifest_arg = manifest_arg
        self.kilit = threading.Lock()
        self.kesim = KesimIsleri(self.kilit, manifest_arg)
        self.yayinci = ky_y.YayinciIsleri()
        self.yayinla = ky_l.Yayinla(lambda: manifest_yolu(manifest_arg))
        self.kesim.dis_mesgul = self.yayinci.calisiyor  # yayından klip çıkarırken yeniden kesim sıraya girmez
        self.izinli_host = {f"127.0.0.1:{self.port}", f"localhost:{self.port}"}
        self.izinli_origin = {f"http://127.0.0.1:{self.port}", f"http://localhost:{self.port}"}

    def server_bind(self):
        if os.name == "nt":  # kapıyı tek başına tut: başka süreç aynı kapıya bağlanamasın
            import socket
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()

    def server_close(self):
        global _ONBELLEK
        _ONBELLEK = None
        try:
            yi = getattr(self, "yayinci", None)  # kapı doluysa yapıcı yarıda kalır
            if yi is not None:
                yi.kapat()  # çalışan klip çıkarma işi de durur
        finally:
            super().server_close()

    def adres(self) -> str:
        return f"http://127.0.0.1:{self.port}/"


class OnayIstegi(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "KlipOnay"
    sys_version = ""

    def log_message(self, *a):  # sessiz
        pass

    # ---- ortak
    def _yanit(self, kod: int, govde: bytes, tur: str = "text/plain; charset=utf-8", ek: dict | None = None, gonder: bool = True):
        self.send_response(kod)
        self.send_header("Content-Type", tur)
        self.send_header("Content-Length", str(len(govde)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        for k, v in (ek or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if gonder:
            self.wfile.write(govde)

    def _json(self, kod: int, veri: dict):
        self._yanit(kod, json.dumps(veri, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _host_tamam(self) -> bool:
        return (self.headers.get("Host") or "").lower() in self.server.izinli_host

    # ---- GET / HEAD
    def do_GET(self):
        self._oku(True)

    def do_HEAD(self):
        self._oku(False)

    def _oku(self, gonder: bool):
        try:
            if not self._host_tamam():
                return self._yanit(403, "Geçersiz Host başlığı.".encode("utf-8"), gonder=gonder)
            yol = self.path.split("?", 1)[0].split("#", 1)[0]
            if yol in ("/", "/index.html"):
                return self._sayfa(gonder)
            if yol.startswith("/dosya/"):
                return self._dosya(yol[len("/dosya/"):], gonder)
            if yol in YAYINCI_GET or yol == "/api/durum" or yol.startswith("/kart/"):
                return self._canli(yol, gonder)
            return self._yanit(404, "Bulunamadı.".encode("utf-8"), gonder=gonder)
        except (ConnectionError, TimeoutError):
            self.close_connection = True

    def _canli(self, yol: str, gonder: bool):
        """Belirteçli okuma uçları: kesim durumu ve tek kart parçası (sayfa betiği çağırır)."""
        if not hmac.compare_digest((self.headers.get("X-Belirtec") or "").encode("utf-8"), self.server.belirtec.encode("utf-8")):
            return self._yanit(403, "Oturum belirteci geçersiz: sayfayı yenile (F5).".encode("utf-8"), gonder=gonder)
        if yol in YAYINCI_GET:
            try:
                if yol == "/api/yayinci/is":
                    veri = {"ok": True, **self.server.yayinci.cikar.goster()}
                elif yol == "/api/yayinci/yayinla-durum":
                    veri = {"ok": True, **self.server.yayinla.goster()}
                else:
                    veri = yayinci_listesi(self.server.manifest_arg)
            except (ky_y.Hata, ky_l.Hata, OSError, ValueError) as e:
                veri = {"ok": False, "mesaj": f"Yayıncı listesi okunamadı: {e}"}
            return self._yanit(200, json.dumps(veri, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8", gonder=gonder)
        if yol == "/api/durum":
            with self.server.kilit:
                kayit = liste_kaydi_oku()
            id_no = {v["id"]: no for no, v in kayit["ogeler"].items()}
            kesimler = {id_no[k]: d for k, d in self.server.kesim.durumlar().items() if k in id_no}
            veri = json.dumps({"ok": True, "kesimler": kesimler}, ensure_ascii=False).encode("utf-8")
            return self._yanit(200, veri, "application/json; charset=utf-8", gonder=gonder)
        no = yol[len("/kart/"):]
        if not no.isdigit():
            return self._yanit(404, "Bulunamadı.".encode("utf-8"), gonder=gonder)
        acik = urllib.parse.parse_qs(self.path.split("?", 1)[1] if "?" in self.path else "").get("ac") == ["1"]
        with self.server.kilit:
            ogeler, manifest, _kayit, ayar = ogeleri_oku(self.server.manifest_arg)
            o = next((x for x in ogeler if x["no"] == no), None)
            if o is None:
                return self._yanit(404, "Bu numarada klip yok; sayfayı yenile.".encode("utf-8"), gonder=gonder)
            govde = kart_html(o, manifest, ayar, self.server.kesim, acik)
        self._yanit(200, govde.encode("utf-8"), "text/html; charset=utf-8", {"Content-Security-Policy": SAYFA_CSP}, gonder)

    def _sayfa(self, gonder: bool):
        with self.server.kilit:
            ogeler, manifest, _kayit, ayar = liste_hazirla(self.server.manifest_arg)
            zaman = ks.simdi_iso().replace("T", " ").replace("Z", " UTC")
            sayfa = html_uret(ogeler, manifest, zaman, {"belirtec": self.server.belirtec, "kesimler": self.server.kesim.durumlar(),
                                                        "acik": set(), "ayar": ayar})
        self._yanit(200, sayfa.encode("utf-8"), "text/html; charset=utf-8", {"Content-Security-Policy": SAYFA_CSP}, gonder)

    def _dosya(self, ham: str, gonder: bool):
        goreli = urllib.parse.unquote(ham)
        parcalar = goreli.split("/")
        if (not goreli or "\\" in goreli or "\0" in goreli or ":" in goreli
                or any(p in ("", ".", "..") for p in parcalar)):
            return self._yanit(400, "Geçersiz dosya yolu.".encode("utf-8"), gonder=gonder)
        d = yk.calisma_dizini().resolve()
        try:
            hedef = (d / goreli).resolve()
            hedef.relative_to(d)
        except (OSError, ValueError):
            return self._yanit(404, "Bulunamadı.".encode("utf-8"), gonder=gonder)
        tur = DOSYA_TURLERI.get(hedef.suffix.lower())
        if tur is None or not hedef.is_file():
            return self._yanit(404, "Bulunamadı.".encode("utf-8"), gonder=gonder)
        boyut = hedef.stat().st_size
        ar = aralik_coz(self.headers.get("Range"), boyut)
        if ar == "yok":
            return self._yanit(416, b"", ek={"Content-Range": f"bytes */{boyut}"}, gonder=False)
        ek = {"Accept-Ranges": "bytes"}
        if ar is None:
            bas, son, kod = 0, boyut - 1, 200
        else:
            bas, son = ar
            kod = 206
            ek["Content-Range"] = f"bytes {bas}-{son}/{boyut}"
        uzun = max(0, son - bas + 1)
        self.send_response(kod)
        self.send_header("Content-Type", tur)
        self.send_header("Content-Length", str(uzun))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in ek.items():
            self.send_header(k, v)
        self.end_headers()
        if not gonder or uzun == 0:
            return
        try:
            with open(hedef, "rb") as f:
                f.seek(bas)
                kalan = uzun
                while kalan > 0:
                    blok = f.read(min(BLOK_BAYT, kalan))
                    if not blok:
                        break
                    self.wfile.write(blok)
                    kalan -= len(blok)
        except (ConnectionError, TimeoutError, OSError):
            self.close_connection = True  # tarayıcı videoyu yarıda bıraktı (ileri sarma): normal

    # ---- POST
    def do_POST(self):
        try:
            self._yaz()
        except (ConnectionError, TimeoutError):
            self.close_connection = True

    def _yaz(self):
        if not self._host_tamam():
            return self._json(403, {"ok": False, "mesaj": "Geçersiz Host başlığı."})
        if (self.headers.get("Origin") or "") not in self.server.izinli_origin:
            return self._json(403, {"ok": False, "mesaj": "İstek bu sayfadan gelmedi (Origin reddedildi)."})
        if not hmac.compare_digest((self.headers.get("X-Belirtec") or "").encode("utf-8"), self.server.belirtec.encode("utf-8")):
            return self._json(403, {"ok": False, "mesaj": "Oturum belirteci geçersiz: sayfayı yenile (F5)."})
        yol = self.path.split("?", 1)[0]
        if yol not in ("/api/onayla", "/api/geri-al") and yol not in DUZENLE_YOLLARI and yol not in YAYINCI_POST:
            return self._json(404, {"ok": False, "mesaj": "Bilinmeyen işlem."})
        azami = DUZENLE_YOLLARI[yol][1] if yol in DUZENLE_YOLLARI else (YAYINCI_AZAMI if yol in YAYINCI_POST else ISTEK_AZAMI_BAYT)
        if not (self.headers.get("Content-Type") or "").lower().startswith("application/json"):
            return self._json(415, {"ok": False, "mesaj": "İçerik türü application/json olmalı."})
        try:
            n = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            n = -1
        if not 0 < n <= azami:
            self.close_connection = True
            return self._json(400, {"ok": False, "mesaj": "İstek gövdesi geçersiz."})
        try:
            veri = json.loads(self.rfile.read(n).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return self._json(400, {"ok": False, "mesaj": "İstek gövdesi JSON değil."})
        if not isinstance(veri, dict):
            return self._json(400, {"ok": False, "mesaj": "İstek gövdesi geçersiz."})
        if yol in YAYINCI_POST:
            try:
                return self._json(200, yayinci_islemi(yol, veri, self.server))
            except (ky_y.Hata, ky_l.Hata) as e:
                return self._json(422, {"ok": False, "mesaj": str(e)})
            except (Hata, RuntimeError, OSError) as e:
                return self._json(409, {"ok": False, "mesaj": f"İşlem yapılamadı: {e}"})
        try:
            with self.server.kilit:
                if yol in DUZENLE_YOLLARI:
                    sonuc = duzenle_islemi(DUZENLE_YOLLARI[yol][0], veri, self.server.manifest_arg, self.server.kesim)
                else:
                    sonuc = onay_islemi(yol == "/api/onayla", veri, self.server.manifest_arg, self.server.kesim)
        except kd.Hata as e:
            return self._json(422, {"ok": False, "mesaj": str(e)})
        except (Hata, RuntimeError, OSError) as e:
            m = str(e)
            if "`liste`" in m:
                m = f"{m.split(';')[0]}; sayfayı yenile (F5)."
            return self._json(409, {"ok": False, "mesaj": m})
        return self._json(200, sonuc)


def yayinci_listesi(manifest_arg: str | None) -> dict:
    """Yayıncılar sekmesi: dosyadaki liste + yayıncı başına kayıtlı klip sayısı (paketlerden)."""
    sayilar: dict[str, int] = {}
    for o in tara(yk.calisma_dizini(), ayar_oku()):  # yalnız okur: sunucu kilidi gerekmez
        if o["tur"] == "klip" and not o["yok_notu"] and o["yayinci"]:
            sayilar[o["yayinci"]] = sayilar.get(o["yayinci"], 0) + 1
    return ky_y.liste(sayilar)


def yayinci_islemi(yol: str, veri: dict, sunucu) -> dict:
    """Yayıncı yönetimi POST'ları. Dış istekler (Kick/YouTube) sunucu kilidi DIŞINDA yapılır; klip çıkarma kilit İÇİNDE başlar
    (aynı anda yeniden kesimle yarışmasın)."""
    ad = yol[len("/api/yayinci/"):]
    yi = sunucu.yayinci
    if ad == "onizle":
        return ky_y.onizle(veri, yi.onizlemeler)
    if ad == "ekle":
        return ky_y.ekle(veri, yi.onizlemeler)
    if ad == "ekle-cikar":
        def baslat(yayinci_adi: str) -> str:
            with sunucu.kilit:   # yeniden kesimle yarışmasın; dış doğrulama (Kick/YouTube) bu kilidin DIŞINDA yapıldı
                if sunucu.kesim.mesgul():
                    raise ky_y.Hata("Şu an bir klip yeniden kesiliyor; bitince listeden \"Son yayından klip çıkar\"a bas.")
                return yi.cikar.baslat(yayinci_adi, sirala=True)
        return ky_y.ekle_ve_cikar(veri, yi, baslat)
    if ad == "yayinla":
        return sunucu.yayinla.baslat()
    if ad == "duzenle":
        return ky_y.duzenle(veri)
    if ad == "kaldir":
        return ky_y.kaldir(veri)
    if ad == "geri-getir":
        return ky_y.geri_getir(veri)
    if ad == "iptal":
        yi.cikar.iptal()
        return {"ok": True, "mesaj": "İptal ediliyor…"}
    with sunucu.kilit:  # klip-cikar
        return yi.klip_cikar(veri, sunucu.kesim.mesgul())


def liste_hazirla(manifest_arg: str | None):
    """Tarar, kalıcı numaraları atar, liste.json'ı yazar (komut_liste ve sayfa ortak)."""
    d = yk.calisma_dizini()
    ayar = ayar_oku()
    ogeler = tara(d, ayar)
    manifest = ks.yukle(manifest_yolu(manifest_arg))
    kayit = liste_kaydi_oku()
    numaralari_ata(kayit, ogeler)
    onay_dizini().mkdir(parents=True, exist_ok=True)
    liste_yolu().write_text(json.dumps(kayit, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    return ogeler, manifest, kayit, ayar


def onay_islemi(onayla: bool, veri: dict, manifest_arg: str | None, kesim=None) -> dict:
    """Tek öğe: onayla ya da geri al. Mevcut `onayla_bir`/`geri_cek_oge` mantığı; numaralar son sayfa yüklemesindeki liste.json'dandır."""
    no = veri.get("no")
    if not isinstance(no, str) or not no.isdigit():
        raise Hata("Geçersiz klip numarası.")
    kr = veri.get("kucuk_resim")
    if kr is not None and (isinstance(kr, bool) or not isinstance(kr, int)):
        raise Hata("Küçük resim numarası geçersiz.")
    d = yk.calisma_dizini()
    ayar = ayar_oku()
    ogeler = tara(d, ayar)
    yol = manifest_yolu(manifest_arg)
    manifest = ks.yukle(yol)
    kayit = liste_kaydi_oku()  # güncellenmez: onay, kullanıcının izlediği listedeki özete bağlı kalır
    if onayla:
        o = hedef_coz(no, ogeler, kayit)
        if kesim is not None and kesim.aktif(o["id"]):
            raise Hata("Bu klip şu an yeniden kesiliyor; kesim bitince onayla.")
        if o["tur"] == "derleme" and kr is None:
            raise Hata("Küçük resim seçmeden onaylanamaz: önce bir küçük resme tıkla.")
        mesaj = onayla_bir(o, ogeler, manifest, kr, ayar)
    else:
        k = kayit["ogeler"].get(no)
        if not k:
            raise Hata(f"{no} numarası listede yok; sayfayı yenile")
        o = next((x for x in ogeler if x["id"] == k["id"]), None)
        if o is None:
            raise Hata(f"{no} numaralı paket artık bulunamıyor")
        mesaj = geri_cek_oge(k["id"], manifest)
    ks.kaydet(manifest, yol)
    etiket, sinif = durum_metni(o, manifest)
    return {"ok": True, "mesaj": mesaj, "durum": {"etiket": etiket, "sinif": sinif, "onayli": sinif in ONAYLI_SINIFLAR},
            "ozet": ozet_sayilari(ogeler, manifest)}


# ---------------------------------------------------------------- düzenleme + yeniden kesim
KESIM_KOMUTU: list[str] | None = None  # yalnız test: gerçek `yayin_klip.py` yerine sahte komut (liste, kabuk yok)
KESIM_ZAMAN_ASIMI = 1800
BITTI_SURESI = 60
HATA_SURESI = 600


def ogeleri_oku(manifest_arg: str | None):
    """Yalnız okur (liste.json'a dokunmaz): öğeler, manifest, kayıt, ayar. Öğelere kayıttaki kalıcı numara verilir."""
    ayar = ayar_oku()
    ogeler = tara(yk.calisma_dizini(), ayar)
    manifest = ks.yukle(manifest_yolu(manifest_arg))
    kayit = liste_kaydi_oku()
    yol_no = {v["paket"]: no for no, v in kayit["ogeler"].items()}
    for o in ogeler:
        o["no"] = None if o["yok_notu"] else yol_no.get(o["goreli"])
    return ogeler, manifest, kayit, ayar


def onayi_dusur(manifest: dict, oge_id: str) -> bool:
    k = (manifest.get("ogeler") or {}).get(oge_id)
    if k and k.get("onay"):
        k.pop("onay")
        return True
    return False


def liste_oge_yenile(no: str, o: dict) -> None:
    """Düzenlenen/yeniden kesilen tek öğenin özetini liste.json'da günceller (öbür öğelere dokunmaz): kullanıcı yeni hâlini görüyor."""
    kayit = liste_kaydi_oku()
    if no in kayit["ogeler"]:
        kayit["ogeler"][no]["ozet"] = ozet_taban(o)
        liste_yolu().write_text(json.dumps(kayit, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")


def kart_html(o: dict, manifest: dict, ayar: dict, kesim, acik: bool = True) -> str:
    etk = {"kesimler": kesim.durumlar() if kesim is not None else {}, "acik": {o["id"]} if acik else set(), "ayar": ayar}
    return kart_uret(o, manifest, etk)


def kesim_calistir(paket_yolu: str, arg: list[str]) -> tuple[bool, str]:
    """`yayin_klip.py yeniden-uret <paket> <seçenekler>` alt süreci. Liste argümanı (kabuk yok). (başarılı, ileti)."""
    komut = list(KESIM_KOMUTU) if KESIM_KOMUTU else [sys.executable, str(KOK / "tools" / "yayin_klip.py")]
    komut += ["yeniden-uret", str(paket_yolu), *arg]
    env = {**os.environ, "YAYIN_KLIP_DIZIN": str(yk.calisma_dizini()), "PYTHONUTF8": "1"}
    bayrak = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    try:
        kos = subprocess.run(komut, capture_output=True, text=True, encoding="utf-8", errors="replace",
                             timeout=KESIM_ZAMAN_ASIMI, env=env, creationflags=bayrak, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return False, f"Kesim {KESIM_ZAMAN_ASIMI // 60} dakikada bitmedi, durduruldu."
    except OSError as e:
        return False, f"Kesim başlatılamadı: {e}"
    cikti = [s.strip() for s in (kos.stdout or "").splitlines() if s.strip()]
    hatalar = [s.strip() for s in (kos.stderr or "").splitlines() if s.strip()]
    if kos.returncode != 0:
        if "unrecognized arguments" in (kos.stderr or ""):
            return False, "Kesim aracı bu seçeneği tanımıyor (yayin_klip.py eski sürüm olabilir): " + (hatalar[-1] if hatalar else "")[:200]
        return False, (hatalar[-1] if hatalar else (cikti[-1] if cikti else f"Kesim {kos.returncode} koduyla bitti."))[:400]
    return True, cikti[-1] if cikti else ""


class KesimIsleri:
    """Yeniden kesim kuyruğu: aynı anda tek kesim (tek işçi iş parçacığı), öbürleri sırada bekler."""

    def __init__(self, sunucu_kilidi: threading.Lock, manifest_arg: str | None):
        self.kilit = threading.Lock()
        self.sunucu_kilidi = sunucu_kilidi
        self.manifest_arg = manifest_arg
        self.kuyruk: queue.Queue = queue.Queue()
        self.durum: dict[str, dict] = {}
        self.isci: threading.Thread | None = None
        self.dis_mesgul = None  # çağrılabilir: başka bir uzun iş (yayından klip çıkarma) sürüyorsa True

    def mesgul(self) -> bool:
        with self.kilit:
            return any(d.get("durum") in ("kuyrukta", "kesiliyor") for d in self.durum.values())

    def aktif(self, oge_id: str) -> bool:
        with self.kilit:
            return (self.durum.get(oge_id) or {}).get("durum") in ("kuyrukta", "kesiliyor")

    def ekle(self, o: dict, arg: list[str], video: dict) -> None:
        if self.dis_mesgul and self.dis_mesgul():
            raise Hata("Yayından klip çıkarma işi sürüyor; bitince yeniden kes (Yayıncılar sekmesinden görebilir ya da iptal edebilirsin).")
        with self.kilit:
            if (self.durum.get(o["id"]) or {}).get("durum") in ("kuyrukta", "kesiliyor"):
                raise Hata("Bu klip zaten kesiliyor ya da sırada; bitmesini bekle.")
            self.durum[o["id"]] = {"durum": "kuyrukta", "mesaj": "", "zaman": time.monotonic()}
            self.kuyruk.put({"id": o["id"], "no": o["no"], "json": str(o["json"]), "arg": list(arg), "video": dict(video)})
            if self.isci is None or not self.isci.is_alive():
                self.isci = threading.Thread(target=self._isle, name="klip-kesim", daemon=True)
                self.isci.start()

    def _yaz(self, oge_id: str, durum: str, mesaj: str) -> None:
        with self.kilit:
            self.durum[oge_id] = {"durum": durum, "mesaj": mesaj, "zaman": time.monotonic()}

    def _isle(self) -> None:
        while True:
            job = self.kuyruk.get()
            try:
                self._yaz(job["id"], "kesiliyor", "Kesiliyor… (20-60 sn sürer; bu sayfayı açık tutman şart değil)")
                ok, mesaj = kesim_calistir(job["json"], job["arg"])
                if ok:
                    self._bitir(job)
                    self._yaz(job["id"], "bitti", "Yeniden kesildi. Videoyu izle; beğenirsen yeniden onayla.")
                else:
                    self._yaz(job["id"], "hata", f"Kesim başarısız, video değişmedi: {mesaj}")
            except Exception as e:  # noqa: BLE001 — işçi ölmesin; hata kartta görünsün
                self._yaz(job["id"], "hata", f"Kesim sonrası işlem başarısız: {e}")
            finally:
                self.kuyruk.task_done()

    def _bitir(self, job: dict) -> None:
        """Başarılı kesim: istenen video-üstü seçenekleri düzenleme dosyasına işler, listedeki özeti tazeler."""
        with self.sunucu_kilidi:
            ogeler = tara(yk.calisma_dizini(), ayar_oku())
            o = next((x for x in ogeler if x["id"] == job["id"]), None)
            if o is None:
                raise Hata("paket kesimden sonra bulunamadı")
            dz = kd.oku(o["json"])
            dz["video"] = {**(dz.get("video") or {}), **job["video"]}
            kd.yaz(o["json"], dz)
            liste_oge_yenile(job["no"], o)

    def bekle(self, saniye: float = 30.0) -> bool:
        """Kuyruk boşalana kadar bekler (test)."""
        bitis = time.monotonic() + saniye
        while time.monotonic() < bitis:
            if self.kuyruk.unfinished_tasks == 0:
                return True
            time.sleep(0.02)
        return False

    def durumlar(self) -> dict:
        with self.kilit:
            simdi = time.monotonic()
            for k in list(self.durum):
                d = self.durum[k]
                if d["durum"] in ("bitti", "hata") and simdi - d["zaman"] > (BITTI_SURESI if d["durum"] == "bitti" else HATA_SURESI):
                    del self.durum[k]
            sirada = [j["id"] for j in list(self.kuyruk.queue)]
            onde = 1 if any(d["durum"] == "kesiliyor" for d in self.durum.values()) else 0
            cikti = {}
            for k, d in self.durum.items():
                mesaj = d["mesaj"]
                if d["durum"] == "kuyrukta":
                    n = (sirada.index(k) if k in sirada else 0) + onde
                    mesaj = f"Sırada bekliyor (önünde {n} kesim var)…"
                cikti[k] = {"durum": d["durum"], "mesaj": mesaj}
            return cikti


def duzenle_islemi(islem: str, veri: dict, manifest_arg: str | None, kesim: KesimIsleri | None) -> dict:
    """Panelden gelen düzenleme. Metin/platform/küçük resim ya da yeniden kesim; onaylı öğe düzenlenirse ONAY DÜŞER."""
    no = veri.get("no")
    if not isinstance(no, str) or not no.isdigit():
        raise Hata("Geçersiz klip numarası.")
    ogeler, manifest, kayit, ayar = ogeleri_oku(manifest_arg)
    o = hedef_coz(no, ogeler, kayit)
    yol = manifest_yolu(manifest_arg)
    ek: dict = {}
    dustu = False
    if islem == "metin-kaydet":
        ek_yasak = tuple((ayar.get("ayar") or {}).get("aciklama_yasak_kelimeler") or ())
        metin, pl, uyarilar = kd.metin_dogrula({"baslik": veri.get("baslik"), "aciklama": veri.get("aciklama"),
                                                "etiketler": veri.get("etiketler", ""), "platformlar": veri.get("platformlar")},
                                               o["tur"], ek_yasak)
        dz = kd.oku(o["json"])
        once = json.dumps(dz, sort_keys=True)
        oto = o["otomatik_metin"]
        if metin == {"baslik": oto["baslik"], "aciklama": oto["aciklama"], "etiketler": list(oto["etiketler"])}:
            dz.pop("metin", None)
        else:
            dz["metin"] = metin
        if pl == kd.varsayilan_platformlar(o["tur"]):
            dz.pop("platformlar", None)
        else:
            dz["platformlar"] = pl
        if json.dumps(dz, sort_keys=True) == once:
            mesaj = "Değişiklik yok; kaydedilecek bir şey yoktu."
        else:
            kd.yaz(o["json"], dz)
            dustu = onayi_dusur(manifest, o["id"])
            mesaj = "Kaydedildi." + (" Onay düştü: yeniden onaylaman gerekir." if dustu else "")
        ek["uyarilar"] = uyarilar
    elif islem == "metin-sifirla":
        dz = kd.oku(o["json"])
        if "metin" not in dz and "platformlar" not in dz:
            mesaj = "Zaten otomatik metin kullanılıyor."
        else:
            dz.pop("metin", None)
            dz.pop("platformlar", None)
            kd.yaz(o["json"], dz)
            dustu = onayi_dusur(manifest, o["id"])
            mesaj = "Otomatik metne dönüldü." + (" Onay düştü: yeniden onaylaman gerekir." if dustu else "")
    elif islem == "kucuk-resim":
        if o["tur"] != "derleme":
            raise Hata("Küçük resim yalnız derlemede seçilir.")
        n = veri.get("kucuk_resim")
        if isinstance(n, bool) or not isinstance(n, int):
            raise Hata("Küçük resim numarası geçersiz.")
        secilen = kucuk_resim_sec(o, n)
        dz = kd.oku(o["json"])
        onayli_ad = ((manifest["ogeler"].get(o["id"]) or {}).get("onay") or {}).get("kucuk_resim")
        if dz.get("kucuk_resim") != secilen.name:
            dz["kucuk_resim"] = secilen.name
            kd.yaz(o["json"], dz)
        if onayli_ad is not None and onayli_ad != secilen.name:
            dustu = onayi_dusur(manifest, o["id"])
        mesaj = "Küçük resim seçildi." + (" Onay düştü: yeniden onaylaman gerekir." if dustu else "")
    elif islem == "kesim":
        if o["tur"] != "klip":
            raise Hata("Derlemenin videosu bu panelde yeniden kesilmez.")
        if kesim is None:
            raise Hata("Yeniden kesim bu sunucuda kapalı.")
        arg, video = kd.kesim_argumanlari(veri, o["paket"])
        kesim.ekle(o, arg, video)
        dustu = onayi_dusur(manifest, o["id"])
        mesaj = "Kesim başlatıldı; 20-60 sn sürer." + (" Onay düştü: kesim bitince yeniden onaylaman gerekir." if dustu else "")
    elif islem == "kaldir":
        if kesim is not None and kesim.aktif(o["id"]):
            raise Hata("Bu klip şu an yeniden kesiliyor; bitince kaldır.")
        _, sinif = durum_metni(o, manifest)
        if sinif == "onayli":
            raise Hata("Bu öğe onaylı ve yüklenmeyi bekliyor. Kaldırmak için önce 'Onayı geri al'a bas.")
        hedefler = [o["json"]]
        if o["tur"] == "klip":
            hedefler += [x["json"] for x in ogeler if x["tur"] == "klip" and x["json"] != o["json"] and ks.ortusuyor(o["paket"], x["paket"])]
        for yol_j in hedefler:
            dz = kd.oku(yol_j)
            dz["gizli"] = True
            kd.yaz(yol_j, dz)
        mesaj = "Listeden kaldırıldı (dosya silinmedi)."
        ek["kaldirildi"] = True
    else:
        raise Hata("Bilinmeyen işlem.")
    if dustu:
        ks.kaydet(manifest, yol)
    # taze hâl: kartı yeniden üret; listedeki özet yalnız bu öğe için tazelenir
    ogeler, manifest, kayit, ayar = ogeleri_oku(manifest_arg)
    o2 = next((x for x in ogeler if x["id"] == o["id"]), None)
    sonuc = {"ok": True, "mesaj": mesaj, "onay_dustu": dustu, "ozet": ozet_sayilari(ogeler, manifest), **ek}
    if o2 is not None:
        if islem != "kesim":
            liste_oge_yenile(no, o2)
        sonuc["kart"] = kart_html(o2, manifest, ayar, kesim)
    return sonuc


def baslatici_yaz() -> pathlib.Path:
    """Çift tıklanan başlatıcı (yoksa yazar). UTF-8 (BOM'suz) + chcp 65001: Türkçe karakterli ileti doğru görünür."""
    yol = onay_dizini() / BASLATICI_AD
    if not yol.exists():
        satirlar = ["@echo off", "chcp 65001 >nul", f'cd /d "{KOK}"',
                    "echo Klip onay sayfası açılıyor. Kapatmak için bu pencereyi kapat.",
                    r"py tools\klip_yayin.py sayfa", "pause"]
        onay_dizini().mkdir(parents=True, exist_ok=True)
        yol.write_bytes(("\r\n".join(satirlar) + "\r\n").encode("utf-8"))
    return yol


def sunucu_baslat(kapi: int, manifest_arg: str | None) -> OnaySunucusu:
    """Boş kapıyı bulur (kapi=0: sistem seçer). 127.0.0.1 dışına asla bağlanmaz."""
    if not 0 <= kapi <= 65535:
        raise Hata("kapı numarası 0-65535 olmalı")
    adaylar = [0] if kapi == 0 else range(kapi, min(kapi + KAPI_DENEME, 65536))
    for k in adaylar:
        try:
            return OnaySunucusu(k, manifest_arg)
        except OSError:
            continue
    raise Hata(f"{kapi}-{max(adaylar)} arası kapılar dolu (başka bir Onay Sayfası açık olabilir); --kapi ile başka bir kapı ver")


def komut_sayfa(args) -> int:
    if getattr(args, "ayar", None):  # yayıncı ayar dosyası (deneme: geçici kopya)
        os.environ["KLIP_YAYINCILAR"] = str(pathlib.Path(args.ayar).resolve())
    liste_hazirla(args.manifest)  # numaralar hazır olsun; hata varsa sunucu açılmadan görünsün
    baslatici_yaz()
    sunucu = sunucu_baslat(args.kapi, args.manifest)
    if args.kapi and sunucu.port != args.kapi:
        print(f"{args.kapi} numaralı kapı doluydu; {sunucu.port} kullanılıyor")
    adres = sunucu.adres()
    print(f"Onay sayfası: {adres}")
    print("Onay yalnız işaretler; yükleme ve paylaşım ayrı adımdır. Kapatmak için Ctrl+C (ya da pencereyi kapat).")
    if not args.acma:
        try:
            threading.Timer(0.3, webbrowser.open, args=(adres,)).start()
        except Exception:  # noqa: BLE001 — tarayıcı açılamazsa adres yazıldı, elle açılır
            pass
    try:
        sunucu.serve_forever()
    except KeyboardInterrupt:
        print("\nkapatıldı")
    finally:
        sunucu.server_close()
    return 0


# ---------------------------------------------------------------- yükleme
def sure_olc(ff: str, yol: pathlib.Path) -> float:
    kos = subprocess.run([ff, "-hide_banner", "-i", str(yol)], capture_output=True, text=True, encoding="utf-8",
                         errors="replace", timeout=120)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", kos.stderr or "")
    if not m:
        raise Hata(f"süre ölçülemedi: {yol.name}")
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])


def ffmpeg_kos(ff: str, *arg: str) -> None:
    kos = subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y", *arg], capture_output=True, text=True,
                         encoding="utf-8", errors="replace", timeout=3600)
    if kos.returncode != 0:
        raise Hata(f"ffmpeg hatası: {(kos.stderr or '').strip()[:300]}")


def klip_dosyalari(o: dict, kayit: dict, ff: str, hazir: pathlib.Path) -> dict:
    """Yüklenecek {ad: yerel yol}: 1080 aynen, 720/540 küçültülmüş, kapak karesi. Üretilenler `hazir` klasörüne."""
    adlar = ks.dosya_adlari(o["id"], "klip")
    boyut = {"mp4_720": ("720:1280", "24", "96k"), "mp4_540": ("540:960", "26", "80k")}
    dosyalar = {adlar["mp4_1080"]: o["mp4"]}
    for anahtar, (olcu, crf, ses) in boyut.items():
        hedef = hazir / adlar[anahtar]
        ffmpeg_kos(ff, "-i", str(o["mp4"]), "-vf", f"scale={olcu}:flags=lanczos", "-c:v", "libx264", "-preset", "slow",
                   "-crf", crf, "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", ses, "-movflags", "+faststart", str(hedef))
        dosyalar[adlar[anahtar]] = hedef
    sure = sure_olc(ff, o["mp4"])
    kapak = hazir / adlar["kapak"]
    ffmpeg_kos(ff, "-ss", f"{min(1.2, sure / 3):.2f}", "-i", str(o["mp4"]), "-frames:v", "1", "-q:v", "2", str(kapak))
    dosyalar[adlar["kapak"]] = kapak
    return dosyalar


def derleme_dosyalari(o: dict, kayit: dict, ff: str, hazir: pathlib.Path) -> dict:
    adlar = ks.dosya_adlari(o["id"], "derleme")
    ad = (kayit.get("onay") or {}).get("kucuk_resim")
    kaynak = o["json"].parent / ad if ad else None
    if not kaynak or not kaynak.exists():
        raise Hata("onaylanan küçük resim bulunamadı")
    kapak = hazir / adlar["kapak"]
    for q in (2, 4, 6, 9, 13, 18, 24):  # YouTube küçük resim sınırı 2 MB: JPEG kalitesini düşürerek sığdır
        ffmpeg_kos(ff, "-i", str(kaynak), "-vf", "scale=1280:720:force_original_aspect_ratio=decrease", "-frames:v", "1",
                   "-q:v", str(q), str(kapak))
        if kapak.stat().st_size <= KAPAK_AZAMI_BAYT:
            break
    else:
        raise Hata("küçük resim 2 MB altına inmedi")
    return {adlar["mp4_1080"]: o["mp4"], adlar["kapak"]: kapak}


def hedef_dogrula(hedef: str) -> str:
    if not HEDEF_DESEN.match(hedef) or hedef.startswith("-"):
        raise Hata("yükleme hedefi kullanici@sunucu:/yol/ ya da takma_ad:/yol/ biçiminde olmalı")
    return hedef if hedef.endswith("/") else hedef + "/"


def uzak_boyut(hedef: str, ad: str) -> int | None:
    sunucu, _, yol = hedef.partition(":")
    ssh = shutil.which("ssh")
    if not ssh:
        return None
    kos = subprocess.run([ssh, "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", sunucu, f"stat -c %s {yol}{ad}"],
                         capture_output=True, text=True, timeout=60)
    try:
        return int((kos.stdout or "").strip())
    except ValueError:
        return None


def scp_yukle(yerel: pathlib.Path, hedef: str, ad: str) -> None:
    scp = shutil.which("scp")
    if not scp:
        raise Hata("scp bulunamadı")
    kos = subprocess.run([scp, "-q", "-B", "--", str(yerel), hedef + ad], capture_output=True, text=True, timeout=3600)
    if kos.returncode != 0:
        raise Hata(f"scp hatası ({ad}): {(kos.stderr or '').strip()[:200]}")
    boyut = uzak_boyut(hedef, ad)
    if boyut is not None and boyut != yerel.stat().st_size:
        raise Hata(f"{ad}: sunucudaki boyut ({boyut}) yerelle ({yerel.stat().st_size}) aynı değil")


def komut_yukle(args) -> int:
    d = yk.calisma_dizini()
    ogeler = tara(d)
    yol = manifest_yolu(args.manifest)
    manifest = ks.yukle(yol)
    hedef = hedef_dogrula(args.hedef or os.environ.get("KLIP_YUKLEME_HEDEFI") or YUKLEME_HEDEFI_VARSAYILAN)
    sec = set(args.idler or [])
    ff = None
    hata = 0
    for oge_id, kayit in sorted(manifest["ogeler"].items()):
        if sec and oge_id not in sec:
            continue
        if not ks.onay_gecerli(kayit) or ks.yayinda_gecerli(kayit):
            continue
        o = next((x for x in ogeler if x["id"] == oge_id), None)
        if o is None:
            print(f"ATLANDI {oge_id}: paket yerelde bulunamadı ({kayit.get('paket')})")
            hata = 1
            continue
        ad = kayit["onay"].get("kucuk_resim")
        guncel = ozet_onay(o, o["json"].parent / ad if ad else None)
        if guncel != kayit["onay"]["ozet"]:
            print(f"ONAY DÜŞTÜ {oge_id}: paket ya da video onaydan sonra değişmiş; yeniden listele ve onayla")
            if not args.kuru:
                kayit.pop("onay", None)
            hata = 1
            continue
        adlar = ks.dosya_adlari(oge_id, o["tur"])
        if args.kuru:
            print(f"[kuru] {oge_id} ({o['tur']})  hedef hesap: {ks.KLIP_HESABI}")
            print(f"  {adlar['mp4_1080']}  <- {o['mp4']}")
            for a in ("mp4_720", "mp4_540"):
                if a in adlar:
                    print(f"  {adlar[a]}  <- ffmpeg ile üretilecek")
            print(f"  {adlar['kapak']}  <- {'seçilen küçük resim (JPEG, ≤2 MB)' if o['tur'] == 'derleme' else 'ffmpeg kare'}")
            print(f"  hedef: {hedef}")
            continue
        try:
            ff = ff or yk.ffmpeg_bul()
            hazir = onay_dizini() / "yuklenecek" / oge_id
            hazir.mkdir(parents=True, exist_ok=True)
            dosyalar = (derleme_dosyalari if o["tur"] == "derleme" else klip_dosyalari)(o, kayit, ff, hazir)
            for dosya_adi, yerel in dosyalar.items():
                print(f"yükleniyor: {dosya_adi}")
                scp_yukle(yerel, hedef, dosya_adi)
            sure = sure_olc(ff, o["mp4"])
        except (Hata, yk.KlipHatasi, OSError, subprocess.SubprocessError) as e:
            print(f"HATA {oge_id}: {e}")
            hata = 1
            continue
        kayit[ks.HESAP_ALANI] = ks.KLIP_HESABI   # paylaşım hedefi AÇIKÇA yazılır: CTRL+A GAME hesaplarına değil, klip hesabına
        kayit["yayinda"] = {"zaman": ks.simdi_iso(), "yuklenen_ozet": kayit["onay"]["ozet"], "sure": round(sure, 2),
                            **{a: adlar[a] for a in adlar}}
        print(f"{oge_id}: yüklendi, yayında")
        ks.kaydet(manifest, yol)  # her klipten sonra yaz: sonraki hata bunu kaybettirmesin
    if not args.kuru:
        ks.kaydet(manifest, yol)
    return hata


# ---------------------------------------------------------------- otomatik gizli (Cio onayı beklenmez; YouTube'a yalnız GİZLİ)
BILDIRIM_SUNUCU = "oracle"                           # ssh takma adı (medya sunucusuyla aynı)
BILDIRIM_ADRES_DOSYASI = "/home/haberci/.bildirim-adresi"   # n8n webhook adresi YALNIZ sunucuda durur; buraya/loga/rapora yazılmaz
BILDIRIM_SON_GUN = 3                                 # gönderilenler kaydında yalnız son N günün gizli yüklemeleri bildirilir
CALISMA_BEKLE_DK = 20                                # `sosyal.yml` turunu en çok bu kadar bekler (0: bekleme)
GITHUB_ISLEM_ZAMAN_ASIMI = 120


def _git(*arg: str, zaman_asimi: float = 300) -> subprocess.CompletedProcess:
    return ky_l._kos(["git", *arg], zaman_asimi, KOK)


def _gh(*arg: str, zaman_asimi: float = GITHUB_ISLEM_ZAMAN_ASIMI) -> subprocess.CompletedProcess:
    gh = shutil.which("gh")
    if not gh:
        raise Hata("gh (GitHub CLI) bulunamadı")
    return ky_l._kos([gh, *arg], zaman_asimi, KOK)


def _uyu(saniye: float) -> None:
    time.sleep(saniye)


def bildirilen_yolu() -> pathlib.Path:
    return onay_dizini() / "bildirilen.json"


def bildirilenleri_oku() -> set[str]:
    ham = json_oku(bildirilen_yolu()) or {}
    return {str(x) for x in (ham.get("anahtarlar") or [])}


def bildirilenleri_yaz(kume: set[str]) -> None:
    yol = bildirilen_yolu()
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(json.dumps({"anahtarlar": sorted(kume)[-500:]}, ensure_ascii=False, indent=1), encoding="utf-8")


def gonderilenler_oku() -> dict:
    """Paylaşım kaydı (Actions yazar): önce origin/main'deki güncel hâli, olmazsa yerel dosya."""
    try:
        _git("fetch", "--quiet", "origin", "main")
        r = _git("show", "origin/main:sosyal/gonderilenler.json")
        if r.returncode == 0:
            ham = json.loads(r.stdout)
            if isinstance(ham, dict):
                return ham
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return json_oku(sy.KAYIT) or {}


def otomatik_bekleyenler(manifest: dict) -> list[str]:
    """Otomatik onaylı (geçerli) ve YouTube'a henüz paylaşılmamış öğeler: yüklenmiş ya da yüklenecek, günlük gizli hakkını kullanacaklar."""
    return sorted(i for i, e in (manifest.get("ogeler") or {}).items()
                  if (e.get("onay") or {}).get("otomatik") is True and ks.onay_gecerli(e) and not e.get("youtube"))


def otomatik_sec(ogeler: list[dict], manifest: dict, sosyal: dict, kayit: dict, gun: str, ayar: dict,
                 en_cok: int | None = None) -> tuple[list[dict], list[str]]:
    """Otomatik onaylanacak klipleri seçer ve MANIFESTE işler (kuru çalışmada kopya verilir). En yeni yayın önce.
    Hak = gizli günlük sınır − bugün yüklenen gizli − onaylı ama henüz paylaşılmamış otomatik; `en_cok` ile de kısılır.
    Cio'nun kararı korunur: manifestte kaydı olan klip yalnız KENDİ otomatik kaydıysa (ve geri çekilmediyse) yeniden onaylanır.
    -> (onaylananlar, atlama notları)"""
    k = sy.klip_ayari(sosyal)
    kullanilan = sy.bugunku_tur_sayisi(kayit, "youtube", ks.KLIP_HESABI, gun, ("klip",), gizli=True)
    hak = k["gizli_gunluk_en_fazla"] - kullanilan - len(otomatik_bekleyenler(manifest))
    if en_cok is not None:
        hak = min(hak, en_cok)
    secilen: list[dict] = []
    notlar: list[str] = []
    for o in ogeler:
        if hak <= 0:
            break
        if o["tur"] != "klip" or o["yok_notu"]:
            continue
        e = (manifest.get("ogeler") or {}).get(o["id"])
        if e is not None and (e.get("otomatik") is not True or e.get("otomatik_red")):
            continue  # Cio'nun onayladığı/geri çektiği/düzenleyip düşürdüğü kayıt: otomatik akış dokunmaz
        e = e or {}
        if ks.onay_gecerli(e) or e.get("beklet") or e.get("youtube"):
            continue
        if (o.get("platformlar") or {}).get("youtube") is False:
            continue
        if o["kufur"]:
            notlar.append(f"{o['id']}: küfür uyarısı var, otomatik onaylanmadı")
            continue
        try:
            onayla_bir(o, ogeler, manifest, None, ayar, otomatik=True)
        except (Hata, RuntimeError, OSError) as h:
            notlar.append(str(h))
            continue
        secilen.append(o)
        hak -= 1
    return secilen, notlar


def manifesti_gonder(yol: pathlib.Path, mesaj: str) -> bool:
    """`klipler.json` commit + `pull --rebase` + push (panel düğmesiyle aynı adımlar). -> commit atıldı mı"""
    r = _git("add", "--", str(yol))
    if r.returncode != 0:
        raise Hata(f"git add başarısız: {ky_l._son_satirlar(r)}")
    degisti = _git("diff", "--cached", "--quiet", "--", str(yol)).returncode != 0
    if degisti:
        r = _git("commit", "-m", mesaj, "--", str(yol))
        if r.returncode != 0:
            raise Hata(f"git commit başarısız: {ky_l._son_satirlar(r)}")
    r = _git("pull", "--rebase", "--autostash")
    if r.returncode != 0:
        ayrinti = ky_l._son_satirlar(r)
        _git("rebase", "--abort")
        raise Hata(f"git pull --rebase başarısız, rebase iptal edildi, commit yerelde duruyor: {ayrinti}")
    r = _git("push")
    if r.returncode != 0:
        raise Hata(f"git push başarısız: {ky_l._son_satirlar(r)}")
    return degisti


def paylasim_turu_baslat() -> int | None:
    """`gh workflow run sosyal.yml` (klipler.json push'u turu kendiliğinden tetiklemez). -> yeni turun kimliği (bulunamazsa None)."""
    t0 = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=30)
    r = _gh("workflow", "run", "sosyal.yml", "--ref", "main")
    if r.returncode != 0:
        raise Hata(f"gh workflow run başarısız: {ky_l._son_satirlar(r)}")
    for _ in range(12):
        _uyu(5)
        r = _gh("run", "list", "--workflow", "sosyal.yml", "--event", "workflow_dispatch", "--limit", "5",
                "--json", "databaseId,createdAt")
        try:
            tur = json.loads(r.stdout or "[]")
        except ValueError:
            continue
        for x in tur:
            try:
                zaman = datetime.datetime.fromisoformat(str(x["createdAt"]).replace("Z", "+00:00"))
            except (KeyError, ValueError):
                continue
            if zaman >= t0:
                return int(x["databaseId"])
    return None


def paylasim_turu_bekle(tur_id: int, dakika: int) -> str | None:
    """Tur bitene dek bekler. -> sonuç ('success', 'failure', …) ya da zaman aşımında None"""
    bitis = time.monotonic() + dakika * 60
    while True:
        r = _gh("run", "view", str(tur_id), "--json", "status,conclusion")
        try:
            d = json.loads(r.stdout or "{}")
        except ValueError:
            d = {}
        if d.get("status") == "completed":
            return str(d.get("conclusion") or "")
        if time.monotonic() > bitis:
            return None
        _uyu(20)


def paylasim_turu_satirlari(tur_id: int) -> list[str]:
    """Turun logundan yalnız ilgili satırlar (gizli paylaşım, uyarı, bildirim işareti). Adres/sır zaten loga yazılmaz."""
    r = _gh("run", "view", str(tur_id), "--log", zaman_asimi=300)
    cikti = []
    for s in (r.stdout or "").splitlines():
        s = s.split("\t")[-1].strip()
        if "[gizli]" in s or "KLIP_BILDIRIM" in s or s.startswith("UYARI") or "Telegram" in s:
            cikti.append(s[:300])
    return cikti


def telegram_gonder(metin: str) -> bool:
    """Mesajı sunucu üzerinden n8n webhook'una yollar: adres yalnız sunucuda okunur (buraya hiç gelmez); stderr yazdırılmaz."""
    ssh = shutil.which("ssh")
    if not ssh:
        return False
    govde = json.dumps({"metin": metin[:3500]}, ensure_ascii=False).encode("utf-8")
    komut = ('curl -sS -m 20 -o /dev/null -w "%{http_code}" -X POST -H "Content-Type: application/json; charset=utf-8" '
             f'--data-binary @- "$(sudo -n cat {BILDIRIM_ADRES_DOSYASI})"')
    try:
        kos = subprocess.run([ssh, "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", BILDIRIM_SUNUCU, komut],
                             input=govde, capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return False
    kod = (kos.stdout or b"").decode("utf-8", "replace").strip()
    return kos.returncode == 0 and kod.startswith("2")


def gizli_bildirimleri(kayit: dict, manifest: dict, bildirilen: set[str], bugun: datetime.date) -> list[dict]:
    """Gizli yüklenmiş (paylaşıldı kaydı tamam, Studio kimliği var) ve henüz bildirilmemiş Shorts'lar. Son BILDIRIM_SON_GUN gün."""
    sinir = (bugun - datetime.timedelta(days=BILDIRIM_SON_GUN)).isoformat()
    cikti = []
    for k, v in sorted(kayit.items()):
        if (len(k.split("|")) != 4 or not v.get("gizli") or v.get("sosyal_tur") != "klip" or v.get("platform") != "youtube"
                or v.get("durum") != "tamam" or not v.get("kimlik") or k in bildirilen):
            continue
        zaman = str(v.get("zaman") or v.get("niyet_zamani") or "")
        if zaman[:10] < sinir:
            continue
        baslik = ((manifest.get("ogeler") or {}).get(v.get("id")) or {}).get("metin", {}).get("baslik") or v.get("id")
        cikti.append({"anahtar": k, "id": v.get("id"), "baslik": baslik, "kimlik": v["kimlik"], "zaman": zaman})
    return cikti


def gizli_bildir(manifest: dict, tur_basi: str | None, tur_satirlari: list[str], cikti=print) -> int:
    """Bildirilmemiş gizli Shorts için TEK Telegram mesajı. Actions turu zaten gönderdiyse (log işareti) onlar tekrar yollanmaz.
    Hata turu/komutu düşürmez. -> mesajda bildirilen Shorts sayısı"""
    bildirilen = bildirilenleri_oku()
    bekleyen = gizli_bildirimleri(gonderilenler_oku(), manifest, bildirilen, datetime.datetime.now(datetime.timezone.utc).date())
    if tur_basi and any("KLIP_BILDIRIM: gönderildi" in s for s in tur_satirlari):
        bu_tur = [b for b in bekleyen if b["zaman"] >= tur_basi]
        bildirilen |= {b["anahtar"] for b in bu_tur}
        bekleyen = [b for b in bekleyen if b not in bu_tur]
        bildirilenleri_yaz(bildirilen)
        cikti(f"Telegram: {len(bu_tur)} Shorts için bildirimi GitHub turu zaten gönderdi")
    if not bekleyen:
        cikti("Telegram: bildirilecek yeni gizli Shorts yok, mesaj gitmedi")
        return 0
    if not telegram_gonder(ks.bildirim_metni(bekleyen)):
        cikti(f"UYARI: Telegram bildirimi gönderilemedi ({len(bekleyen)} gizli Shorts yüklendi); sonraki çalışmada yeniden denenir")
        return 0
    bildirilenleri_yaz(bildirilen | {b["anahtar"] for b in bekleyen})
    cikti(f"TELEGRAM: gönderildi ({len(bekleyen)} gizli Shorts)")
    return len(bekleyen)


def komut_otomatik_gizli(args) -> int:
    """Cio onayını beklemeden: yeni klipleri otomatik onayla -> medya sunucusuna yükle -> klipler.json commit+push -> sosyal.yml turu
    (YouTube'a HER ZAMAN gizli) -> tur sonunda tek Telegram mesajı. Yalnız `sosyal/ayarlar.json` klip.otomatik_gizli açıkken."""
    sosyal = sosyal_ayar_oku()
    if not sy.klip_ayari(sosyal)["otomatik_gizli"]:
        print("otomatik gizli kapalı (sosyal/ayarlar.json → klip.otomatik_gizli); bir şey yapılmadı")
        return 0
    if args.en_cok is not None and args.en_cok < 1:
        raise Hata("--en-cok en az 1 olmalı")
    d = yk.calisma_dizini()
    yol = manifest_yolu(args.manifest)
    kilit = None
    if not args.kuru:
        kilit = kk.Kilit(d, "otomatik gizli onay+yükleme")
        try:
            kilit.al()
        except kk.KilitDolu as e:
            print(f"ATLANDI: başka klip işi çalışıyor ({e.sahip}); sonraki çalışmada denenir")
            return 0
    hata = 0
    try:
        ayar = ayar_oku()
        ogeler = tara(d, ayar)
        manifest = ks.yukle(yol)
        kayit = gonderilenler_oku()
        gun = ks.simdi_iso()[:10]
        calisma = copy.deepcopy(manifest) if args.kuru else manifest
        secilen, notlar = otomatik_sec(ogeler, calisma, sosyal, kayit, gun, ayar, args.en_cok)
        for n in notlar:
            print(f"ATLANDI {n}")
        etiket = "[kuru] " if args.kuru else ""
        for o in secilen:
            print(f"{etiket}otomatik onay: {o['id']}  {o['yayinci']} / {o['oyun']}  \"{o['metin']['baslik']}\"")
        bekleyen = otomatik_bekleyenler(calisma)
        yuklenecek = [i for i in bekleyen if not ks.yayinda_gecerli(calisma["ogeler"][i])]
        k = sy.klip_ayari(sosyal)
        print(f"{etiket}bugün gizli yüklenen: {sy.bugunku_tur_sayisi(kayit, 'youtube', ks.KLIP_HESABI, gun, ('klip',), gizli=True)}"
              f"/{k['gizli_gunluk_en_fazla']}; yeni onaylanan: {len(secilen)}; paylaşılmayı bekleyen: {len(bekleyen)}; "
              f"sunucuya yüklenecek: {len(yuklenecek)}")
        if args.kuru:
            print("[kuru] yükleme, commit, push, GitHub turu ve Telegram yapılmadı")
            return 0
        if secilen:
            ks.kaydet(manifest, yol)
        if yuklenecek:
            hata = komut_yukle(argparse.Namespace(manifest=args.manifest, hedef=args.hedef, kuru=False, idler=yuklenecek))
    finally:
        if kilit is not None:
            kilit.birak()
    manifest = ks.yukle(yol)
    hazir = [i for i in otomatik_bekleyenler(manifest) if ks.yayinda_gecerli(manifest["ogeler"][i])]
    tur_basi = None
    tur_satirlari: list[str] = []
    try:
        if manifesti_gonder(yol, f"klipler: {len(hazir) or len(secilen)} klip otomatik onaylandı (gizli yükleme)"):
            print("klipler.json commit edildi ve GitHub'a gönderildi")
        if hazir:
            tur_basi = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
            tur_id = paylasim_turu_baslat()
            if tur_id is None:
                print("UYARI: başlatılan GitHub turu bulunamadı; saatlik tur paylaşımı yapar")
            else:
                print(f"GitHub turu başladı: {tur_id}")
                if args.calisma_bekle > 0:
                    sonuc = paylasim_turu_bekle(tur_id, args.calisma_bekle)
                    print(f"GitHub turu sonucu: {sonuc or 'beklenirken zaman aşımı'}")
                    tur_satirlari = paylasim_turu_satirlari(tur_id) if sonuc else []
                    for s in tur_satirlari:
                        print(f"  tur: {s}")
    except (Hata, subprocess.SubprocessError, OSError) as e:
        print(f"HATA: {e}")
        hata = 1
    try:
        gizli_bildir(ks.yukle(yol), tur_basi, tur_satirlari)
    except (Hata, OSError, ValueError, subprocess.SubprocessError) as e:  # bildirim hatası komutu düşürmez
        print(f"UYARI: Telegram adımı tamamlanamadı: {type(e).__name__}")
    return hata


def komut_durum(args) -> int:
    manifest = ks.yukle(manifest_yolu(args.manifest))
    sayac = {"onayli": 0, "yayinda": 0, "paylasilan": 0, "dusen": 0}
    for oge in manifest["ogeler"].values():
        if not oge.get("onay"):
            sayac["dusen"] += 1
        elif ks.yayinda_gecerli(oge) and ks.onay_gecerli(oge):
            sayac["yayinda"] += 1
        elif ks.onay_gecerli(oge):
            sayac["onayli"] += 1
        if oge.get("instagram") or oge.get("youtube"):
            sayac["paylasilan"] += 1
    print(f"öğe: {len(manifest['ogeler'])}; onaylı (yüklenmemiş): {sayac['onayli']}; yayında: {sayac['yayinda']}; "
          f"paylaşılmış: {sayac['paylasilan']}; onayı olmayan: {sayac['dusen']}")
    return 0


def ana(argv=None) -> int:
    for akis in (sys.stdout, sys.stderr):
        try:
            akis.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", help="klipler.json yolu (varsayılan data/klipler.json; KLIP_MANIFEST ile de değişir)")
    alt = ap.add_subparsers(dest="komut", required=True)
    alt.add_parser("liste", help="onay sayfasını üretir")
    p = alt.add_parser("onayla", help="klip/derleme onaylar")
    p.add_argument("hedefler", nargs="+")
    p.add_argument("--kucuk-resim", type=int, default=None, help="derleme için küçük resim numarası (varsayılan 1)")
    p = alt.add_parser("geri-cek", help="onayı geri alır")
    p.add_argument("hedefler", nargs="+")
    p = alt.add_parser("yukle", help="onaylı klipleri medya sunucusuna yükler")
    p.add_argument("--kuru", action="store_true", help="hiçbir şey yüklemez, yalnız yazdırır")
    p.add_argument("--hedef", help="kullanici@sunucu:/yol/ (varsayılan oracle:/var/www/medya/v/; KLIP_YUKLEME_HEDEFI)")
    p.add_argument("idler", nargs="*", help="yalnız bu öğe kimlikleri")
    alt.add_parser("durum", help="manifest özeti")
    p = alt.add_parser("otomatik-gizli", help="Cio onayını beklemeden: otomatik onayla, yükle, push, GitHub turu, Telegram (YouTube'a yalnız gizli)")
    p.add_argument("--kuru", action="store_true", help="hiçbir şey yazmaz/yüklemez/göndermez; yalnız neyin onaylanacağını yazdırır")
    p.add_argument("--en-cok", type=int, default=None, help="bu çalışmada en çok kaç YENİ klip onaylansın (günlük gizli sınır yine geçerli)")
    p.add_argument("--hedef", help="kullanici@sunucu:/yol/ (varsayılan oracle:/var/www/medya/v/)")
    p.add_argument("--calisma-bekle", type=int, default=CALISMA_BEKLE_DK, help=f"GitHub turunu en çok kaç dakika beklesin (varsayılan {CALISMA_BEKLE_DK}; 0: bekleme)")
    p = alt.add_parser("sayfa", help="yerel onay sayfası (Onayla / Onayı geri al düğmeleri); yalnız 127.0.0.1")
    p.add_argument("--kapi", type=int, default=KAPI_VARSAYILAN, help=f"kapı numarası (varsayılan {KAPI_VARSAYILAN}; doluysa sıradaki boş kapı)")
    p.add_argument("--acma", action="store_true", help="tarayıcıyı otomatik AÇMA (varsayılan: açar)")
    p.add_argument("--ayar", help="yayıncı ayar dosyası (varsayılan otomasyon/klip-yayincilar.json; deneme için kopya)")
    a = ap.parse_args(argv)
    try:
        return {"liste": komut_liste, "onayla": komut_onayla, "geri-cek": komut_geri_cek, "yukle": komut_yukle,
                "durum": komut_durum, "sayfa": komut_sayfa, "otomatik-gizli": komut_otomatik_gizli}[a.komut](a)
    except Hata as e:
        print(f"HATA: {e}")
        return 1
    except (RuntimeError, yk.KlipHatasi) as e:
        print(f"HATA: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(ana())
