#!/usr/bin/env python3
"""Klip/derleme paylaşım köprüsü: onay manifesti (data/klipler.json), onay özeti, paylaşım metni, küfür denetimi, aday üretimi.

Yalnız Python standart kütüphanesi; GitHub Actions'ta (mp4 dosyaları yok) import edilebilir. Bilgisayar tarafındaki
komutlar (liste, onayla, yukle) tools/klip_yayin.py içindedir; sosyal_yayinla.py yalnız `adaylar`, `bul` ve
`baglanti_yaz` kullanır.

Onay kapısı: bir klip/derleme ancak
  1) `onay` kaydı varsa (Cio `klip_yayin.py onayla` ile verir; onay anında paketin ve mp4'ün özeti saklanır),
  2) saklı paylaşım metninin özeti (`onay.metin_ozeti`) metinle uyuşuyorsa,
  3) medya sunucusuna yüklenmişse (`yayinda`) ve yüklenen dosyaların özeti onaydaki özetle aynıysa,
  4) `beklet` yoksa
paylaşım adayı olur. Paket ya da mp4 onaydan sonra değişirse `yukle` onayı düşürür (yerel özet eşleşmez).
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import sys
from datetime import datetime, timezone

KOK = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK / "tools"))
from video_site import DOSYA_AD  # noqa: E402

MANIFEST_YOLU = KOK / "data" / "klipler.json"
TABAN_VARSAYILAN = "https://medya.ctrl-agame.com/v/"
SURUM = 1
TURLER = ("klip", "derleme")
# Yayıncı klipleri CTRL+A GAME hesaplarına değil AYRI klip hesabına gider (sır önekleri YT_KLIP_* / IG_KLIP_*).
# sosyal_yayinla.KLIP_HESABI ile aynı değer (test denetler). `yukle` manifestte hedefi bu alana açıkça yazar.
KLIP_HESABI = "klip"
HESAP_ALANI = "hesap"
BASLIK_AZAMI = 90
OZET_BLOK = 1024 * 1024

# Eşleşmeyen sosyal_tur değerleri sosyal_yayinla tarafında klip sayılmaz.
KLIP_TURLERI = TURLER


def e_json(veri) -> str:
    return json.dumps(veri, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


# ---------------------------------------------------------------- manifest
def bos_manifest() -> dict:
    return {"surum": SURUM, "taban": TABAN_VARSAYILAN, "ogeler": {}}


def yukle(yol: pathlib.Path | None = None) -> dict:
    """Manifesti okur. Yok, bozuk ya da şeması yanlışsa boş manifest döner (paylaşım klipsiz sürer)."""
    yol = yol or MANIFEST_YOLU
    try:
        ham = json.loads(pathlib.Path(yol).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return bos_manifest()
    taban = ham.get("taban") if isinstance(ham, dict) else None
    ogeler = ham.get("ogeler") if isinstance(ham, dict) else None
    if not (isinstance(taban, str) and taban.startswith("https://") and isinstance(ogeler, dict)):
        return bos_manifest()
    return ham


def kaydet(manifest: dict, yol: pathlib.Path | None = None) -> None:
    yol = pathlib.Path(yol or MANIFEST_YOLU)
    yol.parent.mkdir(parents=True, exist_ok=True)
    gecici = yol.with_name(yol.name + ".tmp")
    gecici.write_text(e_json(manifest), encoding="utf-8")
    gecici.replace(yol)


def simdi_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------- özet
def sha_dosyalar(*yollar) -> str:
    """Dosyaların sırayla bayt özeti (sha256). Dosya yoksa FileNotFoundError."""
    h = hashlib.sha256()
    for yol in yollar:
        with open(yol, "rb") as f:
            while True:
                blok = f.read(OZET_BLOK)
                if not blok:
                    break
                h.update(blok)
        h.update(b"\0")
    return h.hexdigest()


def metin_ozeti(metin: dict) -> str:
    kanon = {"baslik": metin.get("baslik", ""), "aciklama": metin.get("aciklama", ""),
             "etiketler": list(metin.get("etiketler") or [])}
    return hashlib.sha256(json.dumps(kanon, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- kimlik, dosya adları
def guvenli(ad: str) -> str:
    ad = re.sub(r"[^A-Za-z0-9._-]+", "-", ad).strip("-.")
    return ad or "x"


def klip_id(json_yol: pathlib.Path) -> str:
    """cikti/<klasör>/<paket>.json -> '<klasör>-<paket>' (dosya adında ve kayıt anahtarında güvenli)."""
    yol = pathlib.Path(json_yol)
    return guvenli(f"{yol.parent.name}-{yol.stem}")


def derleme_id(klasor: pathlib.Path) -> str:
    return guvenli(f"derleme-{pathlib.Path(klasor).name}")


def dosya_adlari(oge_id: str, tur: str) -> dict:
    if tur == "derleme":
        return {"mp4_1080": f"{oge_id}.mp4", "kapak": f"{oge_id}-kapak.jpg"}
    return {"mp4_1080": f"klip-{oge_id}-1080.mp4", "mp4_720": f"klip-{oge_id}-720.mp4",
            "mp4_540": f"klip-{oge_id}-540.mp4", "kapak": f"klip-{oge_id}-kapak.jpg"}


# ---------------------------------------------------------------- küfür
# klip_konusma'nın listesine ek: eski Türkçe hakaretler (Osmanlıca küfür klibi gibi içerikler metne taşımasın).
EK_YASAK = ("veledi*", "veled", "kelp*")


def kufur_var(metin: str, ek=(), *, zorunlu: bool = True) -> bool:
    """klip_konusma'nın yasak kök listesiyle (kelime bazlı) denetler. Yüklenemezse zorunlu denetimde hata verir;
    zorunlu olmayan (Actions'taki ikinci kontrol) denetim atlanır, asıl kapı onay anındadır."""
    try:
        import klip_konusma
    except Exception as h:  # noqa: BLE001
        if zorunlu:
            raise RuntimeError(f"küfür denetimi yüklenemedi: {h}") from h
        return False
    yasak = tuple(klip_konusma.ACIKLAMA_YASAK_VARSAYILAN) + EK_YASAK + tuple(ek or ())
    return bool(klip_konusma.yasak_kelime_var(str(metin or ""), yasak))


# ---------------------------------------------------------------- metin üretimi
def sade(metin) -> str:
    return re.sub(r"\s+", " ", str(metin or "")).strip()


def tr_kucuk(s: str) -> str:
    return s.replace("İ", "i").replace("I", "ı").lower()


def baslik_kisalt(metin: str, azami: int = BASLIK_AZAMI) -> str:
    metin = sade(metin)
    if len(metin) <= azami:
        return metin
    kes = metin[:azami - 1].rsplit(" ", 1)[0].rstrip(" ,;:-")
    return (kes or metin[:azami - 1]) + "…"


def cumle(metin: str) -> str:
    metin = sade(metin).rstrip("…").rstrip()
    if metin and metin[-1] not in ".!?":
        metin += "."
    return metin


def etiket_kelime(s: str) -> str:
    k = re.sub(r"[^\w]", "", str(s or ""))
    return ("#" + k) if k else ""


def marka_paylasim(paket: dict | None = None, ayar: dict | None = None) -> tuple[str, list[str]]:
    """Paylaşım metnine giren marka: (imza satırı, ek etiketler). Kaynak: klip-yayincilar.json `ayar`
    (klip_paylasim_imza, klip_ek_etiketler; boş = yok). Ayar yoksa eski davranış: imza yok, ek etiket #CTRLA_GAME.
    Paket `duzenleme.marka_yazi` taşıyorsa (yeniden-uret --marka / --markasiz) o geçerlidir; ek etiket markadan türer."""
    dz = (paket or {}).get("duzenleme")
    if isinstance(dz, dict) and "marka_yazi" in dz:
        marka = sade(dz.get("marka_yazi"))
        kelime = etiket_kelime(marka)
        return marka, ([kelime] if kelime else [])
    a = ayar or {}
    imza = a.get("klip_paylasim_imza")
    ek = a.get("klip_ek_etiketler")
    return (sade(imza) if imza is not None else ""), (["#CTRLA_GAME"] if ek is None else [str(e) for e in ek if str(e).strip()])


def etiketler_uret(paket: dict, kisa_ad: str = "", ayar: dict | None = None) -> list[str]:
    sonuc = []
    for ham in (kisa_ad or paket.get("yayinci"), str(paket.get("platform") or "").capitalize(), paket.get("oyun"),
                *marka_paylasim(paket, ayar)[1]):
        t = etiket_kelime(ham)
        if t and t.casefold() not in {x.casefold() for x in sonuc}:
            sonuc.append(t)
    return sonuc[:5]


def klip_metni(paket: dict, kisa_ad: str = "", ek_yasak=(), ayar: dict | None = None) -> dict:
    """Paketten paylaşım başlığı + açıklaması + etiketleri. Küfür içeren parça yedek parçayla değişir.
    -> {baslik, aciklama, etiketler, uyarilar}. Açıklamada #Shorts yok (YouTube gönderimi sonuna kendisi ekler)."""
    yayinci = sade(paket.get("yayinci")) or "Yayıncı"
    kisa = kisa_ad or yayinci
    uyarilar = []

    def temiz(adaylar_, yedek):
        for a in adaylar_:
            a = sade(a)
            if not a:
                continue
            if kufur_var(a, ek_yasak):
                uyarilar.append("metinde küfür vardı, değiştirildi")
                continue
            return a
        return yedek

    yedek = f"{yayinci} yayınından kesit"
    ham_baslik = temiz([paket.get("kisa_aciklama"), paket.get("baslik")], yedek)
    baslik = baslik_kisalt(ham_baslik)
    gecen = [tr_kucuk(x) for x in {kisa, yayinci, yayinci.split(" ")[0]} if x]
    if not any(g in tr_kucuk(baslik) for g in gecen):
        baslik = baslik_kisalt(f"{baslik} | {kisa}")
    uzun = sade(paket.get("baslik"))
    cumle_adaylari = [uzun] if uzun and not uzun.endswith("…") else []
    cumle_adaylari += [paket.get("kisa_aciklama"), uzun]
    cumle_ham = temiz(cumle_adaylari, "")
    govde = cumle(cumle_ham) if cumle_ham else ""
    if govde and tr_kucuk(govde.rstrip(".")) == tr_kucuk(baslik.rstrip(".")):
        govde = ""  # başlıkla aynı cümleyi tekrarlama
    satirlar = []
    if govde:
        satirlar.append(govde)
    kanal = str(paket.get("kanal_url") or "")
    if kanal.startswith("https://"):
        satirlar.append(f"Kaynak: {kanal}")
    vod = str(paket.get("vod_zaman_damgali_url") or "")
    if paket.get("vod_zaman_damgali_url_dogrulandi") is True and vod.startswith("https://"):
        satirlar.append(f"Yayının bu anı: {vod}")
    etiketler = etiketler_uret(paket, kisa, ayar)
    imza = marka_paylasim(paket, ayar)[0]
    if imza:
        satirlar.append(imza)
    aciklama = "\n".join(satirlar)
    return {"baslik": baslik, "aciklama": aciklama, "etiketler": etiketler, "uyarilar": list(dict.fromkeys(uyarilar))}


def derleme_metni(derleme: dict, ek_yasak=(), ayar: dict | None = None) -> dict:
    """Derleme.json'dan YouTube başlığı/açıklaması. Bölüm zaman damgaları derleme.json'daki açıklamadadır."""
    baslik = baslik_kisalt(derleme.get("baslik") or "Yayın Kolajı", 100)
    aciklama = str(derleme.get("aciklama") or "").strip()
    uyarilar = []
    if kufur_var(baslik + "\n" + aciklama, ek_yasak):
        uyarilar.append("metinde küfür var")
    ek = marka_paylasim(None, ayar)[1]
    return {"baslik": baslik, "aciklama": aciklama, "etiketler": [*ek, "#Kick"], "uyarilar": uyarilar}


# ---------------------------------------------------------------- örtüşen varyantlar
def aralik(paket: dict) -> tuple[str, float, float] | None:
    vod = str(paket.get("vod_url") or "")
    bas, bit = paket.get("klip_baslangic_sn"), paket.get("klip_bitis_sn")
    if not vod or not isinstance(bas, (int, float)) or not isinstance(bit, (int, float)) or bit <= bas:
        return None
    return vod, float(bas), float(bit)


def ortusuyor(a: dict, b: dict, oran: float = 0.5) -> bool:
    """Aynı yayının aynı anını gösteren iki varyant (klip / konuşma / hizalı / canlı) mı?"""
    x, y = aralik(a), aralik(b)
    if not x or not y or x[0] != y[0]:
        return False
    kesisim = min(x[2], y[2]) - max(x[1], y[1])
    return kesisim > 0 and kesisim / min(x[2] - x[1], y[2] - y[1]) > oran


# ---------------------------------------------------------------- onay ve yayın durumu
def onay_gecerli(oge: dict) -> bool:
    on = oge.get("onay")
    metin = oge.get("metin")
    if not (isinstance(on, dict) and isinstance(on.get("ozet"), str) and on["ozet"]
            and isinstance(on.get("zaman"), str) and isinstance(metin, dict)):
        return False
    if on.get("metin_ozeti") != metin_ozeti(metin):
        return False
    return bool(metin.get("baslik")) and not oge.get("beklet")


def yayinda_gecerli(oge: dict) -> bool:
    y = oge.get("yayinda")
    if not isinstance(y, dict):
        return False
    tur = oge.get("tur")
    gerekli = ("mp4_1080", "kapak") if tur == "derleme" else ("mp4_1080", "mp4_720", "mp4_540", "kapak")
    for a in gerekli:
        ad = y.get(a)
        if not (isinstance(ad, str) and DOSYA_AD.fullmatch(ad) and ".." not in ad):
            return False
    sure = y.get("sure")
    if isinstance(sure, bool) or not isinstance(sure, (int, float)) or sure <= 0:
        return False
    return y.get("yuklenen_ozet") == (oge.get("onay") or {}).get("ozet")


def bul(manifest: dict, oge_id: str) -> dict | None:
    """Onaylı + yüklenmiş + özeti tutarlı klip/derleme için tam adresli medya bilgisi, yoksa None.
    sosyal_yayinla'daki `video` sözlüğüyle aynı alanlar: mp4_1080, mp4_720, mp4_540, kapak, sure, instagram, youtube."""
    oge = (manifest.get("ogeler") or {}).get(oge_id)
    if not isinstance(oge, dict) or oge.get("tur") not in TURLER:
        return None
    if not onay_gecerli(oge) or not yayinda_gecerli(oge):
        return None
    taban = manifest["taban"] if manifest["taban"].endswith("/") else manifest["taban"] + "/"
    y = oge["yayinda"]
    cikti = {a: taban + y[a] for a in ("mp4_1080", "mp4_720", "mp4_540", "kapak") if y.get(a)}
    cikti["sure"] = float(y["sure"])
    cikti[HESAP_ALANI] = str(y.get(HESAP_ALANI) or "")   # `yukle` yazar; boş = eski kayıt (klip hesabı sayılır)
    for p in ("youtube", "instagram"):
        cikti[p] = oge[p] if isinstance(oge.get(p), str) and oge[p].startswith("https://") else ""
    return cikti


def aday_metni(oge: dict) -> dict:
    m = oge["metin"]
    return {"baslik": m["baslik"], "aciklama": m.get("aciklama", ""), "etiketler": list(m.get("etiketler") or [])}


def aday_uret(oge_id: str, oge: dict) -> dict:
    """sosyal_yayinla kuyruğuna girecek aday (haber adayı şemasına uyumlu; yalnız Türkçe)."""
    m = aday_metni(oge)
    tur = oge["tur"]
    etiketler = [t for t in m["etiketler"] if re.fullmatch(r"#[\w]+", t)]
    zaman = oge["onay"]["zaman"]
    ig = "\n\n".join(p for p in (m["baslik"], m["aciklama"], " ".join(etiketler)) if p)
    yt = "\n\n".join(p for p in (m["aciklama"], " ".join(etiketler)) if p)
    p = oge.get("platformlar") if isinstance(oge.get("platformlar"), dict) else {}
    # Onay panelinde seçilen platformlar; yoksa ya da bozuksa eski davranış (hepsi açık). Derleme zaten yalnız YouTube'a gider.
    platformlar = {k: p.get(k) is not False for k in ("instagram", "youtube")}
    return {
        "platformlar": platformlar,
        # Cio onaylamadan önce makine onayı (`onay.otomatik`): yalnız klip, YouTube'a GİZLİ gider; Cio Studio'dan açar.
        "otomatik_gizli": tur == "klip" and (oge.get("onay") or {}).get("otomatik") is True,
        "id": oge_id, "sosyal_tur": tur, "sosyal_anahtar": oge_id, "oyun": oge.get("oyun") or "",
        "tarih": zaman[:10], "tur": "haber", "kaynaklar": [{"ad": oge.get("yayinci") or "CTRL+A GAME", "url": oge.get("kanal_url") or ""}],
        "sayfalar": {}, "gorsel": None,
        "diller": {"tr": {"baslik": m["baslik"], "ozet": m["aciklama"], "metin": m["aciklama"], "etiketler": etiketler,
                          "ig_aciklama": ig, "yt_aciklama": yt}},
    }


def studio_adresi(video_kimlik: str) -> str:
    return f"https://studio.youtube.com/video/{video_kimlik}/edit"


def bildirim_metni(gizli: list[dict]) -> str:
    """Otomatik gizli yüklenen Shorts için Telegram mesajı. `gizli`: [{baslik, kimlik}]. Kimliği olmayan satıra Studio adresi konmaz."""
    n = len(gizli)
    satirlar = [f"Komixsi: {n} Shorts gizli olarak yüklendi, onayını bekliyor."]
    for g in gizli:
        satirlar.append("")
        satirlar.append(f"• {g.get('baslik') or g.get('id') or '(başlıksız)'}")
        if g.get("kimlik"):
            satirlar.append(studio_adresi(g["kimlik"]))
    return _telegram_kacis("\n".join(satirlar))


def _telegram_kacis(metin: str) -> str:
    """n8n Telegram düğümü metni eski Markdown olarak yollar: video kimliğindeki/başlıktaki `_ * ` [` kapanmamış biçim sayılır,
    Telegram 400 döner ve mesaj HİÇ gitmez (2026-11-22, kimlik `Alot59_uoT8`). Ters bölüyle kaçırılır; adres yine tıklanır."""
    return re.sub(r"([_*`\[])", r"\\\1", metin)


def adaylar(manifest: dict, ayar: dict | None = None) -> list[dict]:
    """Paylaşıma hazır klip/derleme adayları (eski onaydan yeniye). `ayar.turler.klip/derleme` false ise o tür dışarıda."""
    turler = (ayar or {}).get("turler") or {}
    sonuc = []
    for oge_id, oge in sorted((manifest.get("ogeler") or {}).items(),
                              key=lambda kv: ((kv[1].get("onay") or {}).get("zaman", ""), kv[0])):
        if not isinstance(oge, dict) or oge.get("tur") not in TURLER or not turler.get(oge["tur"], True):
            continue
        if bul(manifest, oge_id) is None:
            continue
        m = aday_metni(oge)
        if kufur_var(m["baslik"] + "\n" + m["aciklama"], zorunlu=False):
            continue
        sonuc.append(aday_uret(oge_id, oge))
    return sonuc


def baglanti_yaz(yol: pathlib.Path, oge_id: str, alan: str, url: str) -> bool:
    """Yayın sonrası youtube/instagram bağlantısını manifeste yazar; başka alana dokunmaz. Kayıt yoksa False."""
    if alan not in ("youtube", "instagram") or not str(url).startswith("https://"):
        return False
    try:
        ham = json.loads(pathlib.Path(yol).read_text(encoding="utf-8"))
        oge = ham["ogeler"][oge_id]
    except (OSError, ValueError, KeyError, TypeError):
        return False
    if oge.get(alan) == url:
        return True
    oge[alan] = url
    pathlib.Path(yol).write_text(e_json(ham), encoding="utf-8")
    return True
