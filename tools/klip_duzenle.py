#!/usr/bin/env python3
"""Klip/derleme onay panelinde yapılan düzenlemeler: kalıcı kayıt + doğrulama. Ağ yok, kabuk yok.

Düzenlemeler paketin YANINDAKİ `<paket>.duzenleme.json` dosyasında durur (klip-01.json -> klip-01.duzenleme.json,
derleme.json -> derleme.duzenleme.json). Paketin kendisine yazılmaz: `yayin_klip.py yeniden-uret` paketi yeniden yazsa da
`liste`/`sayfa` yeniden çalışsa da düzenleme kaybolmaz. Dosyanın `.mp4`si olmadığı için paket taramasına paket diye girmez.

  metin        {baslik, aciklama, etiketler}  -> varsa "elle düzenlendi"; paylaşım bunu kullanır (yoksa otomatik metin)
  platformlar  {instagram: bool, youtube: bool}  -> hangi platforma paylaşılacak (derlemede yalnız youtube)
  video        {oyun, aciklama_metni, yayinci_adi, duzen, kamera_kutu}  -> son istenen video-üstü seçenekler (forma geri doldurulur)
  kucuk_resim  "kucuk-resim-2.png"  -> derlemede panelde seçilen küçük resim (onayda kullanılır)
"""
from __future__ import annotations

import json
import math
import pathlib
import re

import klip_sosyal as ks


class Hata(Exception):
    pass


SURUM = 1
SINIRLAR = {"ig_aciklama": 2200, "yt_baslik": 100, "yt_aciklama_bayt": 5000, "yt_aciklama_karakter": 4900,
            "ig_etiket": 30, "aciklama_yazisi": 45, "baslik_oneri": ks.BASLIK_AZAMI, "ad": 60}
DUZENLER = ("kamera", "kadraj", "serit")
# sosyal_yayinla.emojisiz ile aynı karakter sınıfı (paylaşımda bu karakterler silinir)
EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️‍⃣]")
KONTROL = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
PLATFORMLAR = ("instagram", "youtube")


def duzenleme_yolu(json_yol: pathlib.Path) -> pathlib.Path:
    return pathlib.Path(json_yol).with_suffix(".duzenleme.json")


def oku(json_yol: pathlib.Path) -> dict:
    """Bozuk ya da yoksa {} (düzenleme yok sayılır; otomatik metin sürer)."""
    try:
        ham = json.loads(duzenleme_yolu(json_yol).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(ham, dict):
        return {}
    sonuc: dict = {}
    m = ham.get("metin")
    if (isinstance(m, dict) and isinstance(m.get("baslik"), str) and m["baslik"].strip()
            and isinstance(m.get("aciklama"), str) and isinstance(m.get("etiketler"), list)
            and all(isinstance(t, str) for t in m["etiketler"])):
        sonuc["metin"] = {"baslik": m["baslik"], "aciklama": m["aciklama"], "etiketler": list(m["etiketler"])}
    p = ham.get("platformlar")
    if isinstance(p, dict) and all(isinstance(p.get(k), bool) for k in PLATFORMLAR):
        sonuc["platformlar"] = {k: p[k] for k in PLATFORMLAR}
    k = ham.get("kucuk_resim")
    if isinstance(k, str) and re.fullmatch(r"[\w.-]+\.png", k):
        sonuc["kucuk_resim"] = k
    v = ham.get("video")
    if isinstance(v, dict):
        sonuc["video"] = {k: x for k, x in v.items() if k in ("oyun", "aciklama_metni", "yayinci_adi", "duzen", "kamera_kutu")}
    return sonuc


def yaz(json_yol: pathlib.Path, veri: dict) -> None:
    """Anlamlı alan kalmadıysa dosyayı siler; yoksa atomik yazar."""
    yol = duzenleme_yolu(json_yol)
    veri = {k: v for k, v in veri.items() if v}
    if not veri:
        try:
            yol.unlink()
        except FileNotFoundError:
            pass
        return
    veri["surum"] = SURUM
    veri["zaman"] = ks.simdi_iso()
    gecici = yol.with_name(yol.name + ".tmp")
    gecici.write_text(json.dumps(veri, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    gecici.replace(yol)


def varsayilan_platformlar(tur: str) -> dict:
    return {"instagram": tur == "klip", "youtube": True}


# ---------------------------------------------------------------- metin
def etiketleri_ayikla(ham) -> list[str]:
    """'#Eray, Kick  #Eray' -> ['#Eray', '#Kick'] (paylaşımın kabul ettiği biçim: # + harf/rakam/_; yinelenen atılır)."""
    parcalar = ham if isinstance(ham, list) else re.split(r"[\s,;]+", str(ham or ""))
    sonuc, gorulen = [], set()
    for p in parcalar:
        t = ks.etiket_kelime(str(p).lstrip("#"))
        if t and t.casefold() not in gorulen:
            sonuc.append(t)
            gorulen.add(t.casefold())
    return sonuc


def _temiz(s, *, tek_satir: bool) -> str:
    s = KONTROL.sub("", str(s if s is not None else "")).replace("\r\n", "\n").replace("\r", "\n")
    if tek_satir:
        s = re.sub(r"\s*\n\s*", " ", s)
    return s.strip()


def sayilar(metin: dict, tur: str) -> dict:
    """Paylaşımda kullanılacak ham uzunluklar (kesmeden önce): ks.aday_uret + sosyal_yayinla ile aynı birleştirme."""
    etiketler = [t for t in metin.get("etiketler") or [] if re.fullmatch(r"#[\w]+", t)]
    emojisiz = lambda x: EMOJI.sub("", x)  # noqa: E731
    ig = emojisiz("\n\n".join(p for p in (metin["baslik"], metin.get("aciklama", ""), " ".join(etiketler)) if p))
    yt_ac = "\n\n".join(p for p in (metin.get("aciklama", ""), " ".join(etiketler)) if p)
    if tur == "klip":
        yt_ac = (yt_ac + " #Shorts").strip()
    yt_ac = emojisiz(re.sub(r"[<>]", "", yt_ac))
    yt_b = emojisiz(re.sub(r"[<>]", "", metin["baslik"])).strip()
    return {"ig_aciklama": len(ig), "yt_baslik": len(yt_b), "yt_aciklama": len(yt_ac), "yt_aciklama_bayt": len(yt_ac.encode("utf-8")),
            "ig_etiket": len(etiketler)}


def metin_dogrula(girdi: dict, tur: str, ek_yasak=()) -> tuple[dict, dict, list[str]]:
    """Panelden gelen metin+platform -> (metin, platformlar, uyarılar). Kurala aykırıysa Türkçe `Hata`."""
    if not isinstance(girdi, dict):
        raise Hata("Metin bilgisi geçersiz.")
    for a in ("baslik", "aciklama"):
        if not isinstance(girdi.get(a), str):
            raise Hata("Başlık ve açıklama metin olmalı.")
    if not isinstance(girdi.get("etiketler", ""), (str, list)):
        raise Hata("Etiketler geçersiz.")
    if len(girdi["baslik"]) > 1000 or len(girdi["aciklama"]) > 20000:
        raise Hata("Metin çok uzun.")
    baslik = _temiz(girdi["baslik"], tek_satir=True)
    aciklama = _temiz(girdi["aciklama"], tek_satir=False)
    etiket_ham = girdi.get("etiketler", "")
    etiketler = etiketleri_ayikla(etiket_ham)
    uyarilar: list[str] = []
    if not baslik:
        raise Hata("Başlık boş olamaz.")
    # platformlar
    p = girdi.get("platformlar")
    if p is None:
        p = varsayilan_platformlar(tur)
    if not isinstance(p, dict) or not all(isinstance(p.get(k), bool) for k in PLATFORMLAR):
        raise Hata("Platform seçimi geçersiz.")
    p = {k: p[k] for k in PLATFORMLAR}
    if tur == "derleme" and p["instagram"]:
        raise Hata("Derleme yalnız YouTube'a gider; Instagram açılamaz.")
    if not (p["instagram"] or p["youtube"]):
        raise Hata("En az bir platform açık olmalı (Instagram Reel ya da YouTube Short).")
    # küfür (mevcut sözlük; kaydetme anında)
    for ad, deger in (("Başlıkta", baslik), ("Açıklamada", aciklama), ("Etiketlerde", " ".join(etiketler))):
        if deger and ks.kufur_var(deger, ek_yasak):
            raise Hata(f"{ad} küfür var, kaydedilmedi. Metni değiştir.")
    metin = {"baslik": baslik, "aciklama": aciklama, "etiketler": etiketler}
    n = sayilar(metin, tur)
    s = SINIRLAR
    if p["youtube"]:
        if n["yt_baslik"] > s["yt_baslik"]:
            raise Hata(f"YouTube başlığı en çok {s['yt_baslik']} karakter olabilir (şu an {n['yt_baslik']}).")
        if n["yt_aciklama_bayt"] > s["yt_aciklama_bayt"] or n["yt_aciklama"] > s["yt_aciklama_karakter"]:
            raise Hata(f"YouTube açıklaması çok uzun (şu an {n['yt_aciklama']} karakter, {n['yt_aciklama_bayt']} bayt; "
                       f"sınır {s['yt_aciklama_karakter']} karakter / {s['yt_aciklama_bayt']} bayt).")
    if p["instagram"]:
        if n["ig_aciklama"] > s["ig_aciklama"]:
            raise Hata(f"Instagram açıklaması en çok {s['ig_aciklama']} karakter olabilir (şu an {n['ig_aciklama']}).")
        if n["ig_etiket"] > s["ig_etiket"]:
            raise Hata(f"Instagram en çok {s['ig_etiket']} etiket kabul eder (şu an {n['ig_etiket']}).")
    # engellemeyen uyarılar
    if any(EMOJI.search(x) for x in (baslik, aciklama)):
        uyarilar.append("Emoji paylaşımda silinir.")
    if re.search(r"[<>]", baslik + aciklama):
        uyarilar.append("< ve > işaretleri YouTube'da silinir.")
    if isinstance(etiket_ham, str):
        ham_sayi = len([x for x in re.split(r"[\s,;]+", etiket_ham) if x.strip("#")])
        if ham_sayi != len(etiketler):
            uyarilar.append("Yinelenen ya da geçersiz etiketler çıkarıldı.")
    if tur == "klip" and p["youtube"] and not p["instagram"]:
        pass
    return metin, p, uyarilar


# ---------------------------------------------------------------- video üstü (yeniden kesim)
def _sayi(v, ad: str, *, azami: float) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float, str)):
        raise Hata(f"{ad} sayı olmalı.")
    try:
        x = float(str(v).replace(",", ".")) if isinstance(v, str) else float(v)
    except ValueError:
        raise Hata(f"{ad} sayı olmalı.") from None
    if not math.isfinite(x) or abs(x) > azami:
        raise Hata(f"{ad} geçersiz (en çok ±{azami:g}).")
    return x


def _ad(v, ad: str, *, bos_olur: bool) -> str:
    if not isinstance(v, str):
        raise Hata(f"{ad} metin olmalı.")
    s = _temiz(v, tek_satir=True)
    if not s and not bos_olur:
        raise Hata(f"{ad} boş olamaz.")
    if len(s) > SINIRLAR["ad"]:
        raise Hata(f"{ad} en çok {SINIRLAR['ad']} karakter olabilir.")
    return s


def kesim_argumanlari(veri: dict, paket: dict) -> tuple[list[str], dict]:
    """Panelden gelen değişen video-üstü alanlar -> (`yeniden-uret` seçenek listesi, sidecar'a yazılacak `video` kaydı).
    Yalnız gelen alanlar işlenir. Hiçbiri yoksa Hata. Değerler liste elemanıdır (kabuk yok); metinler `--ad=değer` biçiminde
    geçer, böylece '-' ile başlayan bir ad seçenek sanılmaz."""
    if not isinstance(veri, dict):
        raise Hata("İstek geçersiz.")
    arg: list[str] = []
    kayit: dict = {}
    if "aciklama_metni" in veri:
        if not isinstance(veri["aciklama_metni"], str):
            raise Hata("Video üstü açıklama metin olmalı.")
        t = _temiz(veri["aciklama_metni"], tek_satir=True)
        if len(t) > SINIRLAR["aciklama_yazisi"]:
            raise Hata(f"Video üstü açıklama en çok {SINIRLAR['aciklama_yazisi']} karakter olabilir (şu an {len(t)}).")
        arg += [f"--aciklama-metni={t}"] if t else ["--aciklamasiz"]
        kayit["aciklama_metni"] = t
    if "oyun" in veri:
        t = _ad(veri["oyun"], "Oyun adı", bos_olur=True)
        arg += [f"--oyun={t}"] if t else ["--oyunsuz"]
        kayit["oyun"] = t
    if "yayinci_adi" in veri:
        t = _ad(veri["yayinci_adi"], "Yayıncı adı", bos_olur=False)
        arg += [f"--yayinci-adi={t}"]
        kayit["yayinci_adi"] = t
    bas = _sayi(veri["bas_kaydir"], "Başlangıç kaydırma", azami=60) if "bas_kaydir" in veri else 0.0
    son = _sayi(veri["son_kaydir"], "Bitiş kaydırma", azami=60) if "son_kaydir" in veri else 0.0
    b0, b1 = paket.get("klip_baslangic_sn"), paket.get("klip_bitis_sn")
    if (bas or son) and isinstance(b0, (int, float)) and isinstance(b1, (int, float)):
        sure = (b1 + son) - (b0 + bas)
        if sure < 3:
            raise Hata(f"Kaydırınca klip {sure:.1f} sn kalır; en az 3 sn olmalı.")
        if sure > 180:
            raise Hata(f"Kaydırınca klip {sure:.0f} sn olur; en çok 180 sn olabilir.")
        if b0 + bas < 0:
            raise Hata("Başlangıç yayının başından öne kaydırılamaz.")
    if bas:  # '=' biçimi: negatif sayı seçenek sanılmasın
        arg.append(f"--bas-kaydir={bas:g}")
    if son:
        arg.append(f"--son-kaydir={son:g}")
    if "duzen" in veri:
        if veri["duzen"] not in DUZENLER:
            raise Hata("Düzen kamera, kadraj ya da şerit olmalı.")
        arg += [f"--duzen={veri['duzen']}"]
        kayit["duzen"] = veri["duzen"]
    if "kamera_kutu" in veri:
        k = veri["kamera_kutu"]
        if isinstance(k, str):
            k = [x for x in re.split(r"[\s,;]+", k.strip()) if x]
        if not isinstance(k, list) or len(k) != 4:
            raise Hata("Kamera kutusu 4 sayı olmalı (x, y, genişlik, yükseklik; 0 ile 1 arası).")
        x, y, w, h = (_sayi(v, "Kamera kutusu", azami=1) for v in k)
        if min(x, y) < 0 or w <= 0 or h <= 0 or x + w > 1.0001 or y + h > 1.0001:
            raise Hata("Kamera kutusu 0-1 arası olmalı ve görüntüden taşmamalı (x+genişlik ≤ 1, y+yükseklik ≤ 1).")
        metin = ",".join(f"{v:.4f}".rstrip("0").rstrip(".") or "0" for v in (x, y, w, h))
        arg += [f"--kamera-kutu={metin}"]
        kayit["kamera_kutu"] = [x, y, w, h]
    if not arg:
        raise Hata("Değiştirdiğin bir şey yok.")
    return arg, kayit
