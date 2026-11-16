#!/usr/bin/env python3
"""Azure seslerini karşılaştırmak için: hesaptaki ses listesi ve aday seslerden kısa örnek ses dosyaları.

Komutlar:
  py tools/ses_ornek.py liste --diller tr,en,es,fr,de,nl,zh
      Azure ses listesini çeker, verilen dillerin seslerini yazar; ses-listesi.json dosyasına da kaydeder.
  py tools/ses_ornek.py ornek --sesler "ad1,ad2" --dil tr [--yukle]
      Her ses için o dilin sabit örnek metnini seslendirir (mp3). --yukle: videoların yüklendiği sunucuda
      ornek/ klasörüne koyar ve açık adreslerini yazar.

Anahtar: AZURE_SPEECH_KEY ve AZURE_SPEECH_REGION ortam değişkenlerinden okunur; hiçbir yerde yazdırılmaz.
Sentez, video_uret.AzureSes ile aynı yardımcıyı (video_ses_yardimci.py) kullanır: aynı SSML, hız ve çıktı biçimi.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import video_uret as v  # noqa: E402  (AzureSes, _kos, yukle_dosyalar, manifest_oku aynı kodu paylaşır)

VARSAYILAN_DILLER = "tr,en,es,fr,de,nl,zh"
LISTE_CIKTI = Path("ses-listesi.json")
ORNEK_KLASOR = ROOT / "ornek-cikti"
DOGAL_IPUCLARI = ("MAI", "HD", "Dragon", "Multilingual", "Turbo")

# Diller için yerel ayar ön ekleri
YEREL_AYAR_ON_EKLERI = {
    "tr": ("tr-TR",),
    "en": ("en-US", "en-GB"),
    "es": ("es-ES", "es-MX"),
    "fr": ("fr-FR",),
    "de": ("de-DE",),
    "nl": ("nl-NL",),
    "zh": ("zh-CN",),
}

# Haber tonunda, bir oyun adı, bir tarih ve bir sayı içeren ikişer cümle.
ORNEK_METINLER = {
    "tr": "Rainbow Six Siege'in yeni sezonu Operation Vital Signal, 1 Aralık'ta geliyor. "
          "Yeni silah dakikada 750 mermi atıyor ve 64 mermilik şarjör taşıyor.",
    "en": "The new Rainbow Six Siege season, Operation Vital Signal, arrives on December 1. "
          "The new weapon fires 750 rounds per minute and carries a 64-round magazine.",
    "es": "La nueva temporada de Rainbow Six Siege, Operation Vital Signal, llega el 1 de diciembre. "
          "El nuevo arma dispara 750 proyectiles por minuto y lleva un cargador de 64 balas.",
    "fr": "La nouvelle saison de Rainbow Six Siege, Operation Vital Signal, arrive le 1er décembre. "
          "La nouvelle arme tire 750 balles par minute et dispose d'un chargeur de 64 munitions.",
    "de": "Die neue Saison von Rainbow Six Siege, Operation Vital Signal, startet am 1. Dezember. "
          "Die neue Waffe feuert 750 Schuss pro Minute und hat ein Magazin mit 64 Patronen.",
    "nl": "Het nieuwe seizoen van Rainbow Six Siege, Operation Vital Signal, begint op 1 december. "
          "Het nieuwe wapen schiet 750 kogels per minuut en heeft een magazijn van 64 patronen.",
    "zh": "彩虹六号：围攻的新赛季“Operation Vital Signal”将于12月1日上线。"
          "新武器每分钟可射出750发子弹，并配备64发弹匣。",
}


def anahtar_bilgisi() -> tuple[str, str]:
    anahtar, bolge = os.environ.get("AZURE_SPEECH_KEY", ""), os.environ.get("AZURE_SPEECH_REGION", "")
    if not anahtar or not bolge:
        raise SystemExit("AZURE_SPEECH_KEY ve AZURE_SPEECH_REGION ortam değişkenleri gerekli")
    return anahtar, bolge


def sesleri_getir(anahtar: str, bolge: str) -> list[dict]:
    """Azure ses listesi uç noktası. Anahtar yalnız başlıkta gider, mesajlara yazılmaz."""
    url = f"https://{bolge}.tts.speech.microsoft.com/cognitiveservices/voices/list"
    istek = urllib.request.Request(url, headers={"Ocp-Apim-Subscription-Key": anahtar})
    try:
        with urllib.request.urlopen(istek, timeout=60) as yanit:
            return json.loads(yanit.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise SystemExit(f"ses listesi alınamadı: HTTP {e.code} {e.reason}")


def yerel_ayar(kayit: dict) -> str:
    ayar = kayit.get("Locale") or "-".join(str(kayit.get("ShortName", "")).split("-")[:2])
    return str(ayar)


def izinli_yereller(diller: list[str]) -> list[str]:
    onekler = []
    for d in diller:
        d_lower = d.strip().lower()
        if d_lower in YEREL_AYAR_ON_EKLERI:
            onekler.extend(YEREL_AYAR_ON_EKLERI[d_lower])
        else:
            onekler.append(d.strip())
    return onekler


def sesleri_sec(kayitlar: list[dict], diller: list[str]) -> tuple[list[dict], list[dict]]:
    """(dil/yerel filtresinden geçen sesler, bunlardan doğal aday olanlar)."""
    onekler = izinli_yereller(diller)
    secilen = [
        k for k in kayitlar
        if any(yerel_ayar(k).lower().startswith(on.lower()) for on in onekler)
    ]
    dogal = [
        k for k in secilen
        if any(i.lower() in str(k.get("ShortName", "") + k.get("Name", "")).lower() for i in DOGAL_IPUCLARI)
    ]
    return secilen, dogal


def _etiket(kayit: dict) -> str:
    etiket = kayit.get("VoiceTag")
    if isinstance(etiket, dict):
        parcalar = []
        for anahtar in ("TailoredScenarios", "VoicePersonalities"):
            val = etiket.get(anahtar)
            if val:
                parcalar.append(f"{anahtar}={','.join(map(str, val)) if isinstance(val, list) else val}")
        for k, v in etiket.items():
            if k not in ("TailoredScenarios", "VoicePersonalities") and v:
                parcalar.append(f"{k}={','.join(map(str, v)) if isinstance(v, list) else v}")
        return "; ".join(parcalar)
    kisilik = kayit.get("VoicePersonalities") or kayit.get("Personalities")
    if kisilik:
        return f"VoicePersonalities={','.join(map(str, kisilik)) if isinstance(kisilik, list) else kisilik}"
    return ""


def satir(kayit: dict) -> str:
    alanlar = [str(kayit.get("ShortName") or kayit.get("Name", "?"))]
    if kayit.get("Gender"):
        alanlar.append(str(kayit["Gender"]))
    if kayit.get("VoiceType"):
        alanlar.append(str(kayit["VoiceType"]))
    if kayit.get("WordsPerMinute"):
        alanlar.append(f"{kayit['WordsPerMinute']} kelime/dk")
    etiket = _etiket(kayit)
    if etiket:
        alanlar.append(etiket)
    return " | ".join(alanlar)


def liste(diller: list[str], cikti_yolu: Path = LISTE_CIKTI, kayitlar: list[dict] | None = None) -> int:
    if kayitlar is None:
        anahtar, bolge = anahtar_bilgisi()
        kayitlar = sesleri_getir(anahtar, bolge)
    if not kayitlar:
        raise SystemExit("ses listesi boş döndü")
    print("İlk kaydın alanları: " + ", ".join(sorted(kayitlar[0].keys())))
    secilen, dogal = sesleri_sec(kayitlar, diller)
    print(f"Toplam {len(kayitlar)} ses; {', '.join(diller)} dillerinde {len(secilen)} ses.\n")
    print("== Doğal adaylar (MAI / HD / Dragon / Multilingual / Turbo) ==")
    for k in dogal:
        print(satir(k))
    print("\n== Dillere göre tüm sesler ==")
    for dil in diller:
        print(f"-- {dil}")
        dil_onekler = [on.lower() for on in YEREL_AYAR_ON_EKLERI.get(dil.lower(), (dil.lower(),))]
        for k in secilen:
            if any(yerel_ayar(k).lower().startswith(on) for on in dil_onekler):
                print(satir(k))
    cikti_yolu.write_text(
        json.dumps({"diller": diller, "dogal_adaylar": dogal, "sesler": secilen}, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"\nYazıldı: {cikti_yolu.resolve()}")
    return 0


def dosya_adi(dil: str, ses: str) -> str:
    guvenli = re.sub(r"[^A-Za-z0-9._-]+", "-", ses).strip("-")
    return f"ses-ornek-{dil}-{guvenli}.mp3"


def sentezle(ses: str, dil: str, metin: str, klasor: Path) -> Path:
    """Tek ses için örnek mp3. video_uret.AzureSes ile aynı yardımcı ve SSML kullanılır."""
    sentez = v.AzureSes(ses, dil)
    klasor.mkdir(parents=True, exist_ok=True)
    yol = klasor / dosya_adi(dil, ses)
    girdi, olay = klasor / f"girdi-{yol.stem}.json", klasor / f"olaylar-{yol.stem}.json"
    v.json_yaz(girdi, {"metin": metin, "konusmaci": ses, "hiz": v.HIZ, "dil": ses[:5]})
    sentez._yardimci("azure", girdi, yol, olay, "örnek seslendirme", yol)  # noqa: SLF001
    return yol


def ornekle(sesler: list[str], dil: str, klasor: Path, sentez=sentezle, cikti=print) -> tuple[list[Path], list[str]]:
    """Her sesi ayrı dener: bir sesin hatası diğerlerini durdurmaz. (üretilen dosyalar, hata satırları)."""
    if dil not in ORNEK_METINLER:
        raise SystemExit(f"bu dil için örnek metin yok: {dil} (desteklenen: {', '.join(ORNEK_METINLER)})")
    yollar, hatalar = [], []
    for ses in sesler:
        try:
            if not ses.lower().startswith(dil.lower() + "-"):
                raise ValueError(f"ses bu dile ait değil ({dil} bekleniyor)")
            yollar.append(sentez(ses, dil, ORNEK_METINLER[dil], klasor))
            cikti(f"tamam: {ses}")
        except (Exception, SystemExit) as e:  # noqa: BLE001 - her ses için hatayı yazıp devam et
            mesaj = f"{ses}: {e}"
            hatalar.append(mesaj)
            cikti(f"HATA: {mesaj}")
    return yollar, hatalar


def yukle(yollar: list[Path], cikti=print) -> list[str]:
    """Videoların yüklendiği sunucuda ornek/ klasörüne koyar; açık adresleri yazar."""
    hedef = v.video_ayari()["yukleme_hedefi"]
    if not hedef or not v.HEDEF.match(hedef):
        raise SystemExit("video.yukleme_hedefi boş ya da geçersiz (sosyal/ayarlar.json)")
    host, _, yol = hedef.partition(":")
    uzak = yol.rstrip("/") + "/ornek"
    ssh = shutil.which("ssh")
    if not ssh:
        raise SystemExit("ssh bulunamadı")
    v._kos([ssh, "-o", "BatchMode=yes", host, f"mkdir -p -- '{uzak}'"], timeout=120)  # noqa: SLF001
    v.yukle_dosyalar(yollar, f"{host}:{uzak}/", cikti)
    taban = str(v.manifest_oku().get("taban") or v.TABAN).rstrip("/")
    adresler = [f"{taban}/ornek/{p.name}" for p in yollar]
    for a in adresler:
        cikti(f"adres: {a}")
    return adresler


def ornek(sesler_metni: str, dil: str, yukle_mi: bool, klasor: Path = ORNEK_KLASOR) -> int:
    sesler = [s.strip() for s in sesler_metni.split(",") if s.strip()]
    if not sesler:
        raise SystemExit("--sesler boş")
    anahtar_bilgisi()
    yollar, hatalar = ornekle(sesler, dil, klasor)
    if yukle_mi and yollar:
        yukle(yollar)
    print(f"\nÖzet: {len(yollar)} başarılı, {len(hatalar)} hatalı.")
    for h in hatalar:
        print(f"  hata: {h}")
    return 1 if hatalar else 0


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    alt = p.add_subparsers(dest="komut", required=True)
    l = alt.add_parser("liste")
    l.add_argument("--diller", default=VARSAYILAN_DILLER)
    o = alt.add_parser("ornek")
    o.add_argument("--sesler", required=True)
    o.add_argument("--dil", required=True, choices=sorted(ORNEK_METINLER))
    o.add_argument("--yukle", action="store_true")
    a = p.parse_args(argv)
    if a.komut == "liste":
        return liste([d.strip().lower() for d in a.diller.split(",") if d.strip()])
    return ornek(a.sesler, a.dil, a.yukle)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
