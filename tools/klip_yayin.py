#!/usr/bin/env python3
"""Klip hattı -> paylaşım hattı köprüsü (onay kapılı). Bilgisayarda çalışır; GitHub Actions yalnız data/klipler.json okur.

  py tools/klip_yayin.py liste                  aday klip/derlemeleri tarar, TEK yerel HTML üretir (onay/index.html)
  py tools/klip_yayin.py onayla 3 7 ...         listedeki numaraları (ya da paket yollarını) onaylar
  py tools/klip_yayin.py onayla 12 --kucuk-resim 2   derleme için küçük resim seçer
  py tools/klip_yayin.py geri-cek 3             onayı geri alır (sunucudaki dosya silinmez)
  py tools/klip_yayin.py yukle [--kuru]         onaylı klipleri medya sunucusuna yükler (--kuru: yalnız yazdırır)
  py tools/klip_yayin.py durum                  manifestin özeti

Onaysız hiçbir klip paylaşılmaz: sosyal_yayinla.py yalnız `onay` + `yayinda` kaydı geçerli olan öğeleri görür.
Onay, onay anındaki paket+mp4 özetine bağlıdır; dosya sonradan değişirse `yukle` onayı düşürür.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

KOK = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK / "tools"))
import klip_sosyal as ks  # noqa: E402
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


def tara(d: pathlib.Path | None = None, ayar: dict | None = None) -> list[dict]:
    """Bütün klip/derleme paketlerini öğe sözlüğü olarak döndürür (varyant tekilleştirmesi `tekillestir`te)."""
    d = d or yk.calisma_dizini()
    ayar = ayar if ayar is not None else ayar_oku()
    ek_yasak = tuple((ayar.get("ayar") or {}).get("aciklama_yasak_kelimeler") or ())
    ogeler = []
    for tur, json_yol, mp4 in paket_dosyalari(d):
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
            oge["metin"] = ks.klip_metni(paket, kisa, ek_yasak)
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
            oge["kucuk_resimler"] = []
        else:
            oge["id"] = ks.derleme_id(json_yol.parent)
            oge["oncelik"] = 0
            oge["metin"] = ks.derleme_metni(paket, ek_yasak)
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
    return sorted(ogeler, key=lambda o: (o["tur"] != "klip", o["goreli"]))


def ozet_taban(o: dict) -> str:
    return ks.sha_dosyalar(o["json"], o["mp4"])


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
    return ks.sha_dosyalar(*yollar)


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


def html_uret(ogeler: list[dict], manifest: dict, zaman: str) -> str:
    def esc(x) -> str:
        return html.escape(str(x if x is not None else ""))

    def kart(o: dict) -> str:
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
        if o["tur"] == "derleme" and o["kucuk_resimler"]:
            kr = "<p><b>Küçük resim seçenekleri</b> (onay için numara seç: <code>--kucuk-resim N</code>)</p><div class=kr>" + "".join(
                f'<figure><img loading=lazy src="{esc(k.as_uri())}" alt="küçük resim {i}"><figcaption>{i}</figcaption></figure>'
                for i, k in enumerate(o["kucuk_resimler"], 1)) + "</div>"
        komut = (f"py tools/klip_yayin.py onayla {o['no']}" + (" --kucuk-resim 1" if o["tur"] == "derleme" else ""))
        return f"""<article class="kart {sinif}{' kufur' if kufur else ''}" id="k{esc(o['no'])}">
<h3><span class=no>{esc(o['no'])}</span> {esc(kisa)}</h3>
<p class="durum {sinif}">{esc(etiket)}</p>
<div class="govde{' dikey' if dikey else ''}">
<video controls preload="metadata" {'height=480' if dikey else 'width=560'} src="{esc(o['mp4'].as_uri())}"></video>
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
<p class=ipucu>Onay için asistana yaz: <code>{esc(komut)}</code></p>
</article>"""

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
    return f"""<!doctype html>
<html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Klip onay listesi</title>
<style>
:root{{--bg:#f6f6f4;--fg:#1c1c1a;--kart:#fff;--cizgi:#d9d9d4;--vurgu:#0a6cff;--kirmizi:#b3261e;--yesil:#1b7a3a;--sari:#8a6100}}
@media (prefers-color-scheme:dark){{:root{{--bg:#141413;--fg:#ecebe6;--kart:#1f1f1d;--cizgi:#3a3a36;--vurgu:#6aa4ff;--kirmizi:#ff8b82;--yesil:#6fd08a;--sari:#e0b64a}}}}
body{{margin:0;padding:16px;background:var(--bg);color:var(--fg);font:16px/1.45 system-ui,Segoe UI,sans-serif}}
main{{max-width:1100px;margin:0 auto}}
h1{{font-size:1.4rem}} h2{{margin-top:2rem;border-bottom:1px solid var(--cizgi);padding-bottom:.3rem;font-size:1.15rem}}
.kart{{background:var(--kart);border:1px solid var(--cizgi);border-radius:10px;padding:14px;margin:14px 0}}
.kart.kufur{{border-color:var(--kirmizi);border-width:2px}}
.kart h3{{margin:0 0 6px;font-size:1.05rem}} .no{{display:inline-block;min-width:1.8em;text-align:center;background:var(--vurgu);color:#fff;border-radius:6px;padding:0 6px;margin-right:6px}}
.govde{{display:flex;gap:16px;flex-wrap:wrap}} .govde video{{background:#000;max-width:100%;border-radius:6px}}
.yan{{flex:1;min-width:260px}} table{{border-collapse:collapse}} th{{text-align:left;padding:1px 10px 1px 0;color:var(--sari);font-weight:600}}
pre{{white-space:pre-wrap;word-break:break-word;background:var(--bg);padding:8px;border-radius:6px;margin:4px 0}}
.uyari{{color:var(--kirmizi);padding-left:1.2em;margin:.4em 0}} .durum{{margin:2px 0 8px;font-weight:600}}
.durum.yayinda,.durum.paylasildi{{color:var(--yesil)}} .durum.dustu,.durum.bekle{{color:var(--kirmizi)}}
.kr{{display:flex;gap:10px;flex-wrap:wrap}} .kr img{{width:280px;max-width:100%;border-radius:4px}} figure{{margin:0}}
a{{color:var(--vurgu)}} .ipucu{{color:var(--sari);font-size:.92rem}} code{{background:var(--bg);padding:1px 5px;border-radius:4px}}
</style></head><body><main>
<h1>Klip onay listesi</h1>
<p>Hazırlanma: {esc(zaman)} · {len(klipler)} klip, {len(derlemeler)} derleme · küfür uyarılı: {kufurlu}.</p>
<p><b>Onaylamak istediğin kliplerin numarasını asistana yaz.</b> Onaylamadığın hiçbir klip paylaşılmaz.
Kırmızı çerçeveli kartlarda küfür uyarısı var: önce dinle.</p>
{''.join(govde)}
</main></body></html>
"""


def komut_liste(args) -> int:
    d = yk.calisma_dizini()
    ayar = ayar_oku()
    ogeler = tara(d, ayar)
    manifest = ks.yukle(manifest_yolu(args.manifest))
    kayit = liste_kaydi_oku()
    numaralari_ata(kayit, ogeler)
    onay_dizini().mkdir(parents=True, exist_ok=True)
    liste_yolu().write_text(json.dumps(kayit, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
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
def onayla_bir(o: dict, ogeler: list[dict], manifest: dict, kucuk_no: int | None, ayar: dict) -> str:
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
    if ks.onay_gecerli(eski) and eski["onay"]["ozet"] == ozet and eski.get("metin") == metin:
        return f"{o['id']}: zaten onaylı"
    yeni = {k: v for k, v in eski.items() if k in ("instagram", "youtube")}  # eski bağlantılar kalır (çift paylaşımı önler)
    yeni.update({
        "tur": o["tur"], "paket": o["goreli"], "yayinci": o["yayinci"], "oyun": o["oyun"], "kanal_url": o["kanal_url"],
        "sure": o.get("sure"), "yayin_tarihi": o["yayin_tarihi"], "metin": metin,
        "onay": {"zaman": ks.simdi_iso(), "ozet": ozet, "metin_ozeti": ks.metin_ozeti(metin)},
    })
    if kucuk is not None:
        yeni["onay"]["kucuk_resim"] = kucuk.name
    manifest["ogeler"][o["id"]] = yeni
    return f"{o['id']}: onaylandı"


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
        kayit_oge = manifest["ogeler"].get(oge_id)
        if not kayit_oge or not kayit_oge.get("onay"):
            print(f"{oge_id}: zaten onaylı değil")
            continue
        kayit_oge.pop("onay")
        print(f"{oge_id}: onay geri çekildi (sunucudaki dosyalar silinmedi; paylaşılmış gönderi varsa elle kaldırılır)")
    ks.kaydet(manifest, yol)
    return hata


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
            print(f"[kuru] {oge_id} ({o['tur']})")
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
        kayit["yayinda"] = {"zaman": ks.simdi_iso(), "yuklenen_ozet": kayit["onay"]["ozet"], "sure": round(sure, 2),
                            **{a: adlar[a] for a in adlar}}
        print(f"{oge_id}: yüklendi, yayında")
        ks.kaydet(manifest, yol)  # her klipten sonra yaz: sonraki hata bunu kaybettirmesin
    if not args.kuru:
        ks.kaydet(manifest, yol)
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
    a = ap.parse_args(argv)
    try:
        return {"liste": komut_liste, "onayla": komut_onayla, "geri-cek": komut_geri_cek, "yukle": komut_yukle,
                "durum": komut_durum}[a.komut](a)
    except Hata as e:
        print(f"HATA: {e}")
        return 1
    except (RuntimeError, yk.KlipHatasi) as e:
        print(f"HATA: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(ana())
