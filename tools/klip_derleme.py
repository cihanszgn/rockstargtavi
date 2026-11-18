#!/usr/bin/env python3
"""Yayın kesitlerinden ve viral kısa videolardan YouTube için yatay (16:9) derleme videosu üretir.

Yalnız video paketi üretir; hiçbir yere yüklemez, sosyal kuyruğa kayıt eklemez.

Kaynaklar (araç bunlardan parça toplar):
  1. paket     : tools/yayin_klip.py'nin ürettiği klip paketleri (cikti/*/klip-NN.json, canli-NN.json).
                 Aynı aralık Kick HLS'ten YATAY (1080p) yeniden kesilir; yayın kalkmışsa dikey mp4'e düşülür.
  2. izleyici  : Kick izleyici klipleri (/api/v2/channels/<kanal>/clips?sort=view&time=...).
  3. viral     : elle bırakılan videolar (ara-videolar/), ayardaki bağlantılar ve YouTube Shorts kaynakları (yt-dlp).

Alt komutlar:  topla (aday listesi, indirmez)  ·  uret (seç, indir/kes, tek mp4)  ·  dogrula (ölçüm + kare çıkarma)
Belge: otomasyon/DERLEME.md · ayar: otomasyon/derleme.json · testler: tests/test_klip_derleme.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

TOOLS = pathlib.Path(__file__).resolve().parent
ROOT = TOOLS.parent
AYAR_DOSYASI = ROOT / 'otomasyon' / 'derleme.json'
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


class DerlemeHatasi(RuntimeError):
    pass


# ---------------------------------------------------------------- tools/yayin_klip.py içe aktarımı (tek yer)
# Başka çalışan yayin_klip.py üzerinde çalışıyor: kullandığımız adların HEPSİ burada. Biri kaybolursa anlaşılır
# hata verilir (imza değişimi için kullanım yerleri: kick_vod_bilgi, vod_t0_ekle, hls_t0, ffmpeg_bul, font_bul).
YK_ADLARI = ('KlipHatasi', 'calisma_dizini', 'ayar_yukle', 'kick_vod_bilgi', 'vod_t0_ekle', 'hls_t0',
             'http_json', 'http_metin', 'ffmpeg_bul', 'font_bul', 'KICK_API')
_YK = []


def yk_yukle():
    """yayin_klip modülünü (bir kez) yükler ve gereken adları denetler."""
    if _YK:
        return _YK[0]
    try:
        import yayin_klip as yk
    except Exception as e:  # noqa: BLE001 - içe aktarma her türlü hatayla düşebilir
        raise DerlemeHatasi(f'tools/yayin_klip.py yüklenemedi ({type(e).__name__}: {e}); başka bir çalışan '
                            'değiştiriyor olabilir, bir süre sonra tekrar dene') from e
    eksik = [a for a in YK_ADLARI if not hasattr(yk, a)]
    if eksik:
        raise DerlemeHatasi('tools/yayin_klip.py içinde bulunamayan adlar: ' + ', '.join(eksik) +
                            '. Fonksiyon adları/imzaları değişmiş olabilir: tools/klip_derleme.py başındaki '
                            'YK_ADLARI listesini ve kullanım yerlerini güncelle.')
    _YK.append(yk)
    return yk


# ---------------------------------------------------------------- ayar

AYAR_VARSAYILAN = {
    # seri ve görünüm
    'seri_adi': 'Yayın Kolajı',
    'filigran_yazi': 'CTRL+A GAME',
    'filigran_opaklik': 0.35,
    'giris_alt_yazi': 'Bu hafta yayınlarda ve internette öne çıkan anlar',
    'kapanis_yazi': 'İZLEDİĞİNİZ İÇİN TEŞEKKÜRLER',
    'kapanis_alt_yazi': 'Abone ol · En sevdiğin anı yorumlara yaz',
    'kaynak_etiketi_sn': 3.0,        # yayıncı kesitinde sol alt kaynak etiketinin görünme süresi
    'viral_etiketi': False,          # viral parçalarda da kaynak etiketi (varsayılan kapalı: örnek kanallar basmıyor)
    # biçim
    'genislik': 1920, 'yukseklik': 1080,
    'fps': 30,                       # 60 fps üretim süresini uzatır; ölçüm DERLEME.md'de
    'crf': 20, 'kodlama_on_ayar': 'medium', 'ses_kbps': 192,
    'ara_crf': 16, 'ara_on_ayar': 'veryfast',
    'arka_blur': 6, 'arka_parlaklik': -0.12,
    'is_parcacigi': 3,               # eşzamanlı parça hazırlama (Kick hız sınırı için düşük tut)
    # ses
    'ses_hedef_lufs': -16.0, 'ses_tepe_db': -1.5, 'ses_lra': 11.0,
    # süre ve yapı
    'sure_dk': 11.0, 'sure_min_dk': 10.0, 'sure_max_dk': 12.0,
    'giris_karti_sn': 3.0, 'kapanis_karti_sn': 5.0, 'teaser_adet': 2, 'teaser_sn': 2.0,
    'yayinci_basina_viral': 2,
    'viral_dolgu': True,             # yayıncı kesiti tükenirse artan viralleri de yerleştir
    # yayıncı kesiti kısaltma
    'kesit_min_sn': 12.0, 'kesit_hedef_sn': 22.0, 'kesit_max_sn': 28.0,
    'dalga_oncesi_sn': 8.0,          # kesit, kahkaha dalgasının başlangıcından bu kadar önce başlar
    'cumle_payi_sn': 4.0,            # konuşma cümle sınırına en çok bu kadar oturtulur
    # kaynak seçimi
    'gun': 7,                        # son kaç günün malzemesi (paket/izleyici)
    'viral_gun': 90,                 # viral videolar için (kaynak başına 'gun' ile ezilebilir)
    'paket_klasor_haric': ['ESKI'],  # bu önekle başlayan cikti klasörleri (eski yöntem) atlanır
    'izleyici_etkin': True,
    'izleyici_sayfa': 1,             # kanal başına istenen sayfa (her sayfa 20 klip)
    'izleyici_min_izlenme': 5,
    'izleyici_min_sn': 5.0, 'izleyici_max_sn': 60.0,
    'izleyici_uzun': 'kirp',         # max_sn altında ama kesit_max_sn üstündeki klip: kirp | tam
    'izleyici_konum': 'son',         # kırparken kesit: son | bas | orta
    'izleyici_agirlik': 0.75,         # izleyici klibinin değeri bu çarpanla azalır: kendi yayıncı kesitimiz eşitlikte öne geçer
    'izleyici_tam_izlenme': 300,     # değer = log(1+izlenme) / log(1+bu)  (1.0'a ulaşan izlenme)
    'ortusme_esik_sn': 5.0,          # iki parçanın gerçek-zaman örtüşmesi bu kadar sn ise biri elenir
    'ek_kick_kanallari': [],         # klip-yayincilar.json dışındaki Kick kanalları (slug)
    'viral_min_izlenme': 100000,
    'viral_tam_izlenme': 1000000,
    'viral_uzun': 'ele',             # shorts kaynaklarında viral_max_sn'den uzun video: ele | kirp
    'ara_video_deger': 0.9,
    'shorts_detay_azami': 40,        # kaynak başına ayrıntısı çözülecek en çok video (izlenmeye göre ilk N)
    'shorts_kaynaklari': [],
    'baglantilar': [],
    'ara_video_klasoru': None,       # varsayılan: <çalışma dizini>/ara-videolar
    'viral_min_sn': 5.0, 'viral_max_sn': 15.0,
}

IZLEYICI_SIRALA = 'view'


def ayar_yukle_d(yol: pathlib.Path | str | None = None) -> dict:
    yol = pathlib.Path(yol or os.environ.get('KLIP_DERLEME_AYAR') or AYAR_DOSYASI)
    ayar = dict(AYAR_VARSAYILAN)
    if yol.exists():
        try:
            ham = json.loads(yol.read_text(encoding='utf-8'))
        except json.JSONDecodeError as e:
            raise DerlemeHatasi(f'ayar dosyası bozuk ({yol}): {e}') from e
        ayar.update(ham.get('ayar') or {})
    return ayar


def calisma_dizini_d() -> pathlib.Path:
    """Klip hattının çalışma dizini (yayin_klip ile aynı; yüklenemezse aynı kuralı kendisi uygular)."""
    try:
        return pathlib.Path(yk_yukle().calisma_dizini())
    except DerlemeHatasi:
        env = os.environ.get('YAYIN_KLIP_DIZIN')
        if env:
            return pathlib.Path(env)
        if os.name == 'nt':
            return pathlib.Path(r'C:\Cihan.Ai\.scratch\yayin-klip')
        return pathlib.Path.home() / '.local' / 'share' / 'yayin-klip'


# ---------------------------------------------------------------- küçük yardımcılar

def simdi_utc() -> datetime:
    return datetime.now(timezone.utc)


def zaman_m(sn: float) -> str:
    """Bölüm zaman damgası: m:ss ya da h:mm:ss (YouTube bölüm biçimi)."""
    sn = int(sn)
    s, d, h = sn % 60, (sn // 60) % 60, sn // 3600
    return f'{h}:{d:02d}:{s:02d}' if h else f'{d}:{s:02d}'


def tr_buyuk(s: str) -> str:
    return s.replace('i', 'İ').replace('ı', 'I').upper()


def slug(s: str) -> str:
    tablo = str.maketrans({'ç': 'c', 'ğ': 'g', 'ı': 'i', 'ö': 'o', 'ş': 's', 'ü': 'u',
                           'Ç': 'c', 'Ğ': 'g', 'İ': 'i', 'I': 'i', 'Ö': 'o', 'Ş': 's', 'Ü': 'u'})
    s = s.translate(tablo).lower()
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-') or 'seri'


def sinirla(x: float, a: float = 0.0, b: float = 1.0) -> float:
    return max(a, min(b, x))


def deger_izlenme(izlenme: int | float | None, tam: float) -> float:
    """İzlenmeden 0–1 değer: log(1+izlenme)/log(1+tam). İzlenme yoksa 0."""
    if not izlenme or izlenme <= 0:
        return 0.0
    return sinirla(math.log10(1 + izlenme) / math.log10(1 + max(tam, 2)))


def deger_paket(puan: float | None) -> float:
    return sinirla((puan or 0.0) / 100.0)


def log(*a) -> None:
    print(*a, file=sys.stderr, flush=True)


# ---------------------------------------------------------------- kesit kısaltma (saf)

def _cumleler(klip: dict) -> list[tuple[float, float]]:
    """Paket JSON'unda konuşma cümle sınırları varsa (yakında eklenecek; alan adı henüz sabit değil, bu yüzden birkaç
    aday adı denenir) [(bas, bit)] döndürür; yoksa boş liste. Değerler yayının mutlak saniyesidir."""
    for ad in ('cumleler', 'konusma_cumleleri', 'dokum_cumleleri', 'cumle_sinirlari'):
        ham = klip.get(ad)
        if not isinstance(ham, list) or not ham:
            continue
        sonuc = []
        for c in ham:
            try:
                if isinstance(c, dict):
                    b = next(c[k] for k in ('bas', 'bas_sn', 'baslangic_sn', 'start') if k in c)
                    e = next(c[k] for k in ('bit', 'bit_sn', 'bitis_sn', 'end') if k in c)
                else:
                    b, e = c[0], c[1]
                b, e = float(b), float(e)
            except (StopIteration, TypeError, ValueError, IndexError, KeyError):
                continue
            if e > b:
                sonuc.append((b, e))
        if sonuc:
            return sorted(sonuc)
    return []


def cumleye_oturt(bas: float, bit: float, cumleler: list[tuple[float, float]], alt: float, ust: float,
                  max_sn: float, pay: float) -> tuple[float, float]:
    """Kesit başını bir cümlenin başına, sonunu bir cümlenin sonuna (en çok `pay` sn kayarak) oturtur."""
    yeni_bas, yeni_bit = bas, bit
    basaylar = [b for b, e in cumleler if b <= bas and bas - b <= pay and b >= alt]
    if basaylar:
        yeni_bas = max(basaylar)
    bitenler = [e for b, e in cumleler if e >= bit and e - bit <= pay and e <= ust]
    if bitenler:
        yeni_bit = min(bitenler)
    if yeni_bit - yeni_bas > max_sn:   # sığmıyorsa değişen tarafı geri al
        yeni_bas = bas if yeni_bit - bas <= max_sn else yeni_bas
        if yeni_bit - yeni_bas > max_sn:
            yeni_bit = bit
        if yeni_bit - yeni_bas > max_sn:
            yeni_bas, yeni_bit = bas, bit
    return yeni_bas, yeni_bit


def kesit_araligi(klip: dict, ayar: dict) -> dict:
    """Paket klibinin (30–55 sn) derlemelik kesiti: en yoğun bölüm.
    Dönüş: bas/bit (yayının mutlak sn'si), sure, tepe (kesit içindeki an: kahkaha dalgasının başı), yontem.
    Kural: tepe = dalga_basi_sn (yoksa zirve_sn); kesit tepe−dalga_oncesi_sn'den başlar, kesit_hedef_sn sürer,
    klip aralığının dışına taşmaz; konuşma cümle sınırı varsa oraya oturur; kesit_min..max dışına çıkmaz."""
    kb, ke = float(klip['klip_baslangic_sn']), float(klip['klip_bitis_sn'])
    mn, hedef, mx = float(ayar['kesit_min_sn']), float(ayar['kesit_hedef_sn']), float(ayar['kesit_max_sn'])
    tepe_mutlak = klip.get('dalga_basi_sn')
    if tepe_mutlak is None:
        tepe_mutlak = klip.get('zirve_sn')
    if tepe_mutlak is None:
        tepe_mutlak = kb + 20.0
    tepe_mutlak = sinirla(float(tepe_mutlak), kb, ke)
    yontem = 'tam'
    if ke - kb <= mx:
        bas, bit = kb, ke
    else:
        yontem = 'dalga'
        bas = tepe_mutlak - float(ayar['dalga_oncesi_sn'])
        bit = bas + hedef
        if bit > ke:
            bit = ke
            bas = bit - hedef
        if bas < kb:
            bas = kb
            bit = min(ke, bas + hedef)
        cumleler = _cumleler(klip)
        if cumleler:
            b2, e2 = cumleye_oturt(bas, bit, cumleler, kb, ke, mx, float(ayar['cumle_payi_sn']))
            if (b2, e2) != (bas, bit):
                yontem = 'dalga+cumle'
            bas, bit = b2, e2
        # asgari süre: önce sona, sonra başa uzat
        if bit - bas < mn:
            bit = min(ke, bas + mn)
            bas = max(kb, bit - mn)
    sure = bit - bas
    return {'bas': round(bas, 2), 'bit': round(bit, 2), 'sure': round(sure, 2),
            'tepe': round(max(0.0, tepe_mutlak - bas), 2), 'yontem': yontem}


def izleyici_araligi(sure: float, ayar: dict) -> dict:
    """Kick izleyici klibi için kesit: (klip içi başlangıç, süre). kesit_max_sn'ye sığıyorsa tamamı."""
    mx, hedef = float(ayar['kesit_max_sn']), float(ayar['kesit_hedef_sn'])
    if sure <= mx or ayar.get('izleyici_uzun') == 'tam':
        return {'bas': 0.0, 'sure': round(sure, 2), 'tepe': round(sure * 0.4, 2), 'yontem': 'tam'}
    konum = ayar.get('izleyici_konum', 'son')
    if konum == 'bas':
        bas = 0.0
    elif konum == 'orta':
        bas = (sure - hedef) / 2
    else:
        bas = max(0.0, sure - hedef - 2.0)   # klip çoğu kez olaydan hemen sonra alınır: son bölümü tut
    return {'bas': round(bas, 2), 'sure': round(hedef, 2), 'tepe': round(hedef * 0.5, 2), 'yontem': konum}


def viral_araligi(sure: float, ayar: dict, uzun: str) -> dict | None:
    """Viral video için (bas=0, süre). viral_max_sn'den uzunsa: 'ele' -> None, 'kirp' -> ilk viral_max_sn."""
    mx = float(ayar['viral_max_sn'])
    if sure <= mx:
        return {'bas': 0.0, 'sure': round(sure, 2), 'tepe': round(sure * 0.3, 2), 'yontem': 'tam'}
    if uzun == 'kirp':
        return {'bas': 0.0, 'sure': round(mx, 2), 'tepe': round(mx * 0.3, 2), 'yontem': 'bastan_kirpildi'}
    return None


# ---------------------------------------------------------------- aday ayıklama, örtüşme, tekrar kullanmama (saf)

def aralik_ortusme_sn(a0: float, a1: float, b0: float, b1: float) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def ortusenleri_ele(adaylar: list[dict], esik_sn: float) -> tuple[list[dict], list[dict], int]:
    """Gerçek-zaman (epoch) aralığı bilinen adaylardan örtüşenlerin birini bırakır: yayıncı paketi > izleyici klibi,
    aynı türde yüksek değer kalır. Aralığı bilinmeyen (epoch_bas yok) aday elenmez; sayısı üçüncü dönüş değeridir
    (örtüşme anlaşılamadı)."""
    sira_oncelik = {'yayinci': 0, 'izleyici': 1, 'viral': 2}
    sirali = sorted(adaylar, key=lambda a: (sira_oncelik.get(a['tur'], 3), -a.get('deger', 0.0)))
    kabul: list[dict] = []
    elenen: list[dict] = []
    belirsiz = 0
    for a in sirali:
        if a.get('epoch_bas') is None or a.get('epoch_bit') is None:
            if a['tur'] in ('yayinci', 'izleyici'):
                belirsiz += 1
            kabul.append(a)
            continue
        cakisan = next((k for k in kabul if k.get('epoch_bas') is not None and
                        aralik_ortusme_sn(a['epoch_bas'], a['epoch_bit'], k['epoch_bas'], k['epoch_bit']) >= esik_sn), None)
        if cakisan:
            elenen.append({'id': a['id'], 'neden': 'ortusme', 'ortusen': cakisan['id']})
        else:
            kabul.append(a)
    kabul_idler = {a['id'] for a in kabul}
    return [a for a in adaylar if a['id'] in kabul_idler], elenen, belirsiz


def kullanilanlari_ele(adaylar: list[dict], durum: dict) -> tuple[list[dict], list[dict]]:
    kul = durum.get('kullanilan', {})
    kalan, elenen = [], []
    for a in adaylar:
        if a['id'] in kul:
            elenen.append({'id': a['id'], 'neden': 'onceki_derlemede_kullanildi', 'derleme': kul[a['id']].get('derleme')})
        else:
            kalan.append(a)
    return kalan, elenen


def kopyalari_ele(adaylar: list[dict]) -> tuple[list[dict], list[dict]]:
    """Aynı kimlikli adaydan birini tutar (en yüksek değer)."""
    en_iyi: dict[str, dict] = {}
    for a in adaylar:
        if a['id'] not in en_iyi or a.get('deger', 0) > en_iyi[a['id']].get('deger', 0):
            en_iyi[a['id']] = a
    kalan = [a for a in adaylar if en_iyi[a['id']] is a]
    return kalan, [{'id': a['id'], 'neden': 'kopya'} for a in adaylar if en_iyi[a['id']] is not a]


# ---------------------------------------------------------------- sıralama ve plan (saf)

def _ardisik_ihlal(sira: list[dict], anahtar) -> int:
    return sum(1 for i in range(1, len(sira)) if anahtar(sira[i]) == anahtar(sira[i - 1]))


def duzenle(ogeler: list[dict], anahtar) -> list[dict]:
    """Sıra kuralı: en yüksek değerli başa, ikinci en yüksek SONA (güçlü kapanış), ortadakiler azalan değerle;
    `anahtar` (yayıncı/kanal) art arda gelmez (kaçınılamıyorsa en az ihlal)."""
    s = sorted(ogeler, key=lambda a: -a.get('deger', 0.0))
    if len(s) <= 2:
        return s
    ilk, son, orta = s[0], s[1], list(s[2:])
    sonuc = [ilk]
    while orta:
        onceki = anahtar(sonuc[-1])
        secim = next((i for i, a in enumerate(orta) if anahtar(a) != onceki), 0)
        sonuc.append(orta.pop(secim))
    sonuc.append(son)
    # önce yalnız ortadaki elemanların yerini değiştirerek ihlalleri gider (ilk ve son sabit kalır)
    ihlal = _ardisik_ihlal(sonuc, anahtar)
    gelisti = ihlal > 0
    while gelisti and ihlal > 0:
        gelisti = False
        for i in range(1, len(sonuc) - 1):
            for j in range(i + 1, len(sonuc) - 1):
                aday = list(sonuc)
                aday[i], aday[j] = aday[j], aday[i]
                ih = _ardisik_ihlal(aday, anahtar)
                if ih < ihlal:
                    sonuc, ihlal, gelisti = aday, ih, True
    # son eleman komşusuyla aynı anahtardaysa: ortadan uygun birini sona al, son'u onun yerine koy (en az ihlal)
    if anahtar(sonuc[-1]) == anahtar(sonuc[-2]):
        en_iyi, en_ihlal = sonuc, _ardisik_ihlal(sonuc, anahtar)
        for i in range(1, len(sonuc) - 1):
            aday = list(sonuc)
            aday[i], aday[-1] = aday[-1], aday[i]   # son'u i. yere, i. elemanı sona al
            # i. eleman artık "ikinci en iyi" değil: yalnız ihlal azalıyorsa kabul et
            ih = _ardisik_ihlal(aday, anahtar)
            if ih < en_ihlal:
                en_iyi, en_ihlal = aday, ih
        sonuc = en_iyi
    return sonuc


def yayinci_anahtari(a: dict) -> str:
    return (a.get('yayinci') or a.get('kanal') or '').lower()


def viral_anahtari(a: dict) -> str:
    return (a.get('kanal_adi') or a.get('yayinci') or a.get('id') or '').lower()


def plan_olustur(adaylar: list[dict], ayar: dict, hedef_sn: float | None = None,
                 turler: tuple[str, ...] = ('yayinci', 'izleyici', 'viral')) -> dict:
    """Seçim + sıra. Adaylar `tur`, `deger`, `kes_sure_sn` taşır. Döngü: 1 yayıncı kesiti + `yayinci_basina_viral`
    viral; süre bütçesi dolana dek en değerliden başlayarak. Malzeme yetmezse (viral yok vb.) geri düşer ve uyarır."""
    hedef = float(hedef_sn if hedef_sn is not None else ayar['sure_dk'] * 60)
    giris, kapanis = float(ayar['giris_karti_sn']), float(ayar['kapanis_karti_sn'])
    teaser_n = int(ayar['teaser_adet'])
    teaser_sn = float(ayar['teaser_sn'])
    oran = max(0, int(ayar['yayinci_basina_viral']))
    kesitler = sorted([a for a in adaylar if a['tur'] in ('yayinci', 'izleyici') and a['tur'] in turler],
                      key=lambda a: -a['deger'])
    virallar = sorted([a for a in adaylar if a['tur'] == 'viral' and 'viral' in turler], key=lambda a: -a['deger'])
    sabit = giris + kapanis + teaser_n * teaser_sn
    butce = hedef - sabit
    uyarilar: list[str] = []
    secK: list[dict] = []
    secV: list[dict] = []
    toplam = 0.0
    ki = vi = 0
    while True:
        bu_dongu: list[dict] = []
        if ki < len(kesitler):
            bu_dongu.append(kesitler[ki])
        elif not (ayar.get('viral_dolgu', True) and vi < len(virallar)):
            break
        for j in range(oran):
            if vi + j < len(virallar):
                bu_dongu.append(virallar[vi + j])
        if not bu_dongu:
            break
        sigmayan = False
        for a in bu_dongu:
            if toplam + a['kes_sure_sn'] <= butce:
                toplam += a['kes_sure_sn']
                (secK if a['tur'] in ('yayinci', 'izleyici') else secV).append(a)
            else:
                sigmayan = True
        ki += 1 if (ki < len(kesitler)) else 0
        vi += min(oran, len(virallar) - vi)
        if sigmayan:
            break
    # artık bütçe: kalan adaylardan en değerli sığanı ekle (sıra kuralı sonra yine uygulanır)
    kalanlar = [a for a in kesitler + virallar if a not in secK and a not in secV]
    for a in sorted(kalanlar, key=lambda a: -a['deger']):
        if a['tur'] == 'viral' and not ayar.get('viral_dolgu', True) and len(secV) >= len(secK) * oran:
            continue                      # viral_dolgu kapalıyken oran aşılmaz
        if toplam + a['kes_sure_sn'] <= butce:
            toplam += a['kes_sure_sn']
            (secK if a['tur'] in ('yayinci', 'izleyici') else secV).append(a)
    # sıra
    Kdz = duzenle(secK, yayinci_anahtari)
    Vdz = duzenle(secV, viral_anahtari)
    dongu_sayisi = max(len(Kdz), math.ceil(len(Vdz) / oran) if oran else 0)
    parcalar: list[dict] = []
    en_iyiler = sorted(secK + secV, key=lambda a: -a['deger'])[:teaser_n]
    for a in en_iyiler:
        parcalar.append({'rol': 'teaser', 'aday': a, 'sure_sn': teaser_sn})
    parcalar.append({'rol': 'giris', 'aday': None, 'sure_sn': giris})
    for j in range(dongu_sayisi):
        if j < len(Kdz):
            parcalar.append({'rol': Kdz[j]['tur'], 'aday': Kdz[j], 'sure_sn': Kdz[j]['kes_sure_sn'], 'dongu': j + 1})
        for v in Vdz[j * oran:(j + 1) * oran] if oran else []:
            parcalar.append({'rol': 'viral', 'aday': v, 'sure_sn': v['kes_sure_sn'], 'dongu': j + 1})
    parcalar.append({'rol': 'kapanis', 'aday': None, 'sure_sn': kapanis})
    t = 0.0
    for p in parcalar:
        p['plan_bas_sn'] = round(t, 2)
        t += p['sure_sn']
        p['plan_bit_sn'] = round(t, 2)
    govde = [p for p in parcalar if p['rol'] in ('yayinci', 'izleyici', 'viral')]
    toplam_sn = round(t, 2)
    if toplam_sn < ayar['sure_min_dk'] * 60:
        uyarilar.append(f'malzeme yetmedi: toplam {zaman_m(toplam_sn)} < asgari {ayar["sure_min_dk"]} dk '
                        f'(yayıncı/izleyici kesiti {len(kesitler)}, viral {len(virallar)} aday vardı; '
                        f'{len(secK)} kesit + {len(secV)} viral yerleştirildi)')
    if oran and len(secV) < len(secK) * oran and 'viral' in turler:
        uyarilar.append(f'viral yetmedi: {len(secK)} kesit için {len(secK) * oran} viral istendi, {len(secV)} var')
    kesit_sirasi = [a for a in Kdz]
    ihlal = _ardisik_ihlal(kesit_sirasi, yayinci_anahtari) if kesit_sirasi else 0
    if ihlal:
        uyarilar.append(f'aynı yayıncı art arda: {ihlal} yerde kaçınılamadı (yayıncı çeşitliliği az)')
    return {
        'hedef_sn': round(hedef, 1), 'toplam_sn': toplam_sn, 'parcalar': parcalar,
        'sayilar': {'yayinci': sum(1 for p in govde if p['rol'] == 'yayinci'),
                    'izleyici': sum(1 for p in govde if p['rol'] == 'izleyici'),
                    'viral': sum(1 for p in govde if p['rol'] == 'viral'),
                    'govde_parca': len(govde), 'toplam_parca': len(parcalar), 'dongu': dongu_sayisi,
                    'teaser': len(en_iyiler)},
        'uyarilar': uyarilar,
    }


def plan_ozeti(plan: dict) -> dict:
    """Plan JSON'u: aday sözlüğünü kısaltır (yazdırma/kaydetme için)."""
    parcalar = []
    for p in plan['parcalar']:
        a = p.get('aday')
        parcalar.append({
            'rol': p['rol'], 'sure_sn': p['sure_sn'], 'plan_bas_sn': p['plan_bas_sn'], 'plan_bit_sn': p['plan_bit_sn'],
            **({'id': a['id'], 'yayinci': a.get('yayinci'), 'baslik': a.get('baslik'), 'deger': round(a['deger'], 3),
                'izlenme': a.get('izlenme'), 'dongu': p.get('dongu')} if a else {})})
    return {**{k: v for k, v in plan.items() if k != 'parcalar'}, 'parcalar': parcalar}


# ---------------------------------------------------------------- durum (kullanılanlar, seri sayısı)

def derleme_dizini(dizin: pathlib.Path) -> pathlib.Path:
    return dizin / 'derleme'


def durum_oku(dizin: pathlib.Path) -> dict:
    yol = derleme_dizini(dizin) / 'durum.json'
    if yol.exists():
        d = json.loads(yol.read_text(encoding='utf-8'))
        d.setdefault('seri', {})
        d.setdefault('kullanilan', {})
        return d
    return {'seri': {}, 'kullanilan': {}}


def durum_yaz(dizin: pathlib.Path, durum: dict) -> None:
    kok = derleme_dizini(dizin)
    kok.mkdir(parents=True, exist_ok=True)
    gecici = kok / 'durum.json.tmp'
    gecici.write_text(json.dumps(durum, ensure_ascii=False, indent=2), encoding='utf-8')
    gecici.replace(kok / 'durum.json')


def sonraki_sayi(durum: dict, seri_adi: str) -> int:
    return int(durum.get('seri', {}).get(slug(seri_adi), {}).get('son_sayi', 0)) + 1


def kullanilanlari_isle(durum: dict, seri_adi: str, sayi: int, derleme_adi: str, parcalar: list[dict]) -> dict:
    """Üretim başarıyla bitince çağrılır: kullanılan adayları kaydeder, seri sayısını artırır."""
    durum.setdefault('seri', {})[slug(seri_adi)] = {'ad': seri_adi, 'son_sayi': sayi}
    kul = durum.setdefault('kullanilan', {})
    zaman = simdi_utc().strftime('%Y-%m-%dT%H:%M:%SZ')
    for p in parcalar:
        a = p.get('aday')
        if a and p['rol'] in ('yayinci', 'izleyici', 'viral'):
            kul[a['id']] = {'derleme': derleme_adi, 'tur': a['tur'], 'tarih': zaman}
    return durum


# ---------------------------------------------------------------- Kick: izleyici klipleri

KICK_UA = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
_KICK_KILIT = threading.Lock()
_KICK_SON = [0.0]


class KickEngeli(DerlemeHatasi):
    """Kick bot koruması/erişim engeli: araç durur ve raporlar."""


def kick_json(url: str, deneme: int = 5, zaman_asimi: int = 30):
    son = None
    for i in range(deneme):
        with _KICK_KILIT:
            bekle = _KICK_SON[0] + 0.4 - time.monotonic()
            if bekle > 0:
                time.sleep(bekle)
            _KICK_SON[0] = time.monotonic()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=KICK_UA), timeout=zaman_asimi) as r:
                return json.loads(r.read().decode('utf-8', 'replace'))
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise KickEngeli(f'Kick erişimi engellendi (HTTP {e.code}): {url}') from e
            if e.code == 404:
                raise DerlemeHatasi(f'bulunamadı (404): {url}') from e
            son = e
            time.sleep(min(10 * (i + 1), 60) if e.code == 429 else 2 ** i)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            son = e
            time.sleep(2 ** i)
    raise DerlemeHatasi(f'Kick isteği başarısız ({deneme} deneme): {url}: {son}')


def izleyici_zaman_parametresi(gun: float) -> str:
    return 'day' if gun <= 1 else ('week' if gun <= 7 else 'month')


def kick_klipler(kanal: str, gun: float, sayfa: int = 1, json_al=kick_json) -> list[dict]:
    """Kick izleyici klipleri, izlenmeye göre azalan (ölçüldü: sort=view her sayfada azalan izlenme verir)."""
    sonuc: list[dict] = []
    imle = None
    for _ in range(max(1, sayfa)):
        url = f'https://kick.com/api/v2/channels/{kanal}/clips?sort={IZLEYICI_SIRALA}&time={izleyici_zaman_parametresi(gun)}'
        if imle:
            url += '&cursor=' + urllib.parse.quote(imle if isinstance(imle, str) else json.dumps(imle, separators=(',', ':')))
        d = json_al(url)
        sonuc.extend(d.get('clips') or [])
        imle = d.get('nextCursor')
        if not imle:
            break
    return sonuc


def _tarih_epoch(s: str | None) -> float | None:
    if not s:
        return None
    try:
        s = s.strip().replace(' ', 'T')
        if s.endswith('Z'):
            s = s[:-1] + '+00:00'
        d = datetime.fromisoformat(s)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.timestamp()
    except ValueError:
        return None


def izleyici_ele_nedeni(k: dict, ayar: dict, kesim_epoch: float) -> str | None:
    """Ham Kick klip kaydı için eleme nedeni (yoksa None). Saf: ağ yok."""
    if (k.get('privacy') or 'public') != 'public':
        return 'herkese_acik_degil'
    if not (k.get('clip_url') or k.get('video_url')) or not k.get('id'):
        return 'adres_yok'
    d = float(k.get('duration') or 0)
    if d < float(ayar['izleyici_min_sn']):
        return 'cok_kisa'
    if d > float(ayar['izleyici_max_sn']):
        return 'cok_uzun'
    if int(k.get('views') or k.get('view_count') or 0) < int(ayar['izleyici_min_izlenme']):
        return 'dusuk_izlenme'
    olusma = _tarih_epoch(k.get('created_at'))
    if olusma is not None and olusma < kesim_epoch:
        return 'gun_disi'
    return None


def izleyici_adayi(k: dict, kanal: str, yayinci_ad: str, ayar: dict, pdt_epoch: float | None) -> dict:
    sure = float(k['duration'])
    kes = izleyici_araligi(sure, ayar)
    izlenme = int(k.get('views') or k.get('view_count') or 0)
    epoch_bas = pdt_epoch + kes['bas'] if pdt_epoch else None
    tarih_kaynak = pdt_epoch or _tarih_epoch(k.get('created_at'))
    return {
        'id': 'kick-klip:' + k['id'], 'tur': 'izleyici', 'kaynak': 'kick_klip',
        'yayinci': yayinci_ad, 'kanal': kanal, 'kanal_url': f'https://kick.com/{kanal}',
        'baslik': (k.get('title') or '').strip(), 'izlenme': izlenme,
        'deger': deger_izlenme(izlenme, ayar['izleyici_tam_izlenme']) * float(ayar['izleyici_agirlik']),
        'sure_sn': sure, 'kes': kes, 'kes_sure_sn': kes['sure'],
        'tarih': datetime.fromtimestamp(tarih_kaynak, timezone.utc).strftime('%Y-%m-%d') if tarih_kaynak else None,
        'klip_url': k.get('clip_url') or k.get('video_url'),
        'web_url': f'https://kick.com/{kanal}/clips/{k["id"]}',
        'olusturan': ((k.get('creator') or {}).get('username')),
        'oyun': ((k.get('category') or {}).get('name')),
        'epoch_bas': epoch_bas, 'epoch_bit': (epoch_bas + kes['sure']) if epoch_bas else None,
    }


def izleyici_topla(ayar: dict, kanallar: list[tuple[str, str]], gun: float, kesim_epoch: float,
                   rapor: dict, json_al=kick_json, pdt_al=None) -> list[dict]:
    """kanallar: [(slug, yayıncı adı)]. rapor['izleyici'] doldurulur (bulunan/elenen/kalan, kanal başına)."""
    yk = None
    if pdt_al is None:
        yk = yk_yukle()

        def pdt_al(url):  # noqa: E306
            try:
                return yk.hls_t0(yk.http_metin(url, bayt=4096))
            except Exception:  # noqa: BLE001 - liste okunamazsa örtüşme "belirsiz" kalır
                return None
    sonuc: list[dict] = []
    r = rapor.setdefault('izleyici', {'bulunan': 0, 'elenen': {}, 'kalan': 0, 'kanal': {}, 'hata': {}})
    nedenler = Counter()
    for slug_, ad in kanallar:
        try:
            ham = kick_klipler(slug_, gun, int(ayar['izleyici_sayfa']), json_al)
        except KickEngeli:
            raise
        except DerlemeHatasi as e:
            r['hata'][slug_] = str(e)
            continue
        kanal_say = {'bulunan': len(ham), 'kalan': 0}
        for k in ham:
            neden = izleyici_ele_nedeni(k, ayar, kesim_epoch - 86400)  # created_at, yayın saatinden geç olabilir: 1 gün pay
            if neden:
                nedenler[neden] += 1
                continue
            pdt = pdt_al(k.get('clip_url') or k.get('video_url'))
            if pdt is not None and pdt < kesim_epoch:
                nedenler['gun_disi'] += 1
                continue
            sonuc.append(izleyici_adayi(k, slug_, ad, ayar, pdt))
            kanal_say['kalan'] += 1
        r['bulunan'] += len(ham)
        r['kanal'][slug_] = kanal_say
    r['elenen'] = dict(nedenler)
    r['kalan'] = len(sonuc)
    return sonuc


# ---------------------------------------------------------------- yayıncı paketleri (kendi kliplerimiz)

VOD_URL_RE = re.compile(r'kick\.com/([^/\s]+)/videos/([0-9a-fA-F-]{36})')


def paket_dosyalari(dizin: pathlib.Path, ayar: dict) -> tuple[list[pathlib.Path], int]:
    """cikti/<yayinci-tarih-id>/klip-NN.json ve canli-NN.json; haric önekli klasörler (eski yöntem) atlanır."""
    kok = dizin / 'cikti'
    dosyalar: list[pathlib.Path] = []
    haric = 0
    if not kok.is_dir():
        return dosyalar, haric
    oneks = tuple(ayar.get('paket_klasor_haric') or ())
    for klasor in sorted(p for p in kok.iterdir() if p.is_dir()):
        if oneks and klasor.name.startswith(oneks):
            haric += len(list(klasor.glob('klip-*.json')) + list(klasor.glob('canli-*.json')))
            continue
        dosyalar += sorted(klasor.glob('klip-*.json')) + sorted(klasor.glob('canli-*.json'))
    return dosyalar, haric


def paket_ele_nedeni(paket: dict, ayar: dict, kesim_tarih: str) -> str | None:
    if not paket.get('vod_url') or not VOD_URL_RE.search(paket['vod_url']):
        return 'vod_adresi_yok'
    for alan in ('klip_baslangic_sn', 'klip_bitis_sn', 'yayinci'):
        if paket.get(alan) is None:
            return f'alan_eksik:{alan}'
    t = paket.get('yayin_tarihi')
    if t and t < kesim_tarih:
        return 'gun_disi'
    return None


def vod_getir(uuid: str, kanal: str) -> dict:
    """Kick VOD bilgisi + HLS çeşidi + gerçek-zaman başlangıcı (t0). Başarısızsa DerlemeHatasi."""
    yk = yk_yukle()
    try:
        yk_ayar = yk.ayar_yukle()
    except Exception:  # noqa: BLE001 - ayar dosyası okunamasa da VOD bilgisi alınabilir
        yk_ayar = {'ayar': {}, 'yayincilar': []}
    ham: dict = {}

    def http(url):
        d = yk.http_json(url)
        ham['video'] = d
        return d
    try:
        vod = yk.kick_vod_bilgi(uuid, kanal, yk_ayar, http)
        yk.vod_t0_ekle(vod)
    except TypeError as e:
        raise DerlemeHatasi(f'yayin_klip.kick_vod_bilgi/vod_t0_ekle imzası değişmiş: {e}') from e
    except Exception as e:  # noqa: BLE001 - KlipHatasi dahil: yayın kalkmış olabilir
        raise DerlemeHatasi(f'VOD alınamadı ({uuid[:8]}): {e}') from e
    vod['livestream_id'] = (ham.get('video') or {}).get('live_stream_id')
    if (ham.get('video') or {}).get('is_pruned'):
        vod['hls'] = ''
    return vod


def paket_adayi(klasor_adi: str, dosya_adi: str, paket: dict, vod: dict | None, mp4: pathlib.Path, ayar: dict) -> tuple[dict | None, str | None]:
    """(aday, eleme nedeni). VOD yoksa/HLS yoksa dikey mp4'e düşer (erisim='dikey'), o da yoksa elenir."""
    m = VOD_URL_RE.search(paket['vod_url'])
    kanal, uuid = m.group(1), m.group(2).lower()
    hls = (vod or {}).get('hls') or ''
    erisim = 'hls' if hls else ('dikey' if mp4.exists() else None)
    if erisim is None:
        return None, 'kaynak_yok'
    kes = kesit_araligi(paket, ayar)
    if vod and vod.get('sure_sn') and kes['bit'] > vod['sure_sn'] + 1:
        return None, 'klip_vod_disinda'
    t0 = (vod or {}).get('t0_epoch')
    return {
        'id': f'paket:{klasor_adi}/{dosya_adi}', 'tur': 'yayinci', 'kaynak': 'paket',
        'yayinci': paket['yayinci'], 'kanal': paket.get('kanal') or kanal, 'kanal_url': paket.get('kanal_url') or f'https://kick.com/{kanal}',
        'baslik': (paket.get('baslik') or '').strip(), 'puan': paket.get('zirve_puani'), 'izlenme': None,
        'deger': deger_paket(paket.get('zirve_puani')), 'tarih': paket.get('yayin_tarihi'),
        'vod_url': paket['vod_url'], 'vod_uuid': uuid, 'oyun': paket.get('oyun'),
        'klip_baslangic_sn': float(paket['klip_baslangic_sn']), 'klip_bitis_sn': float(paket['klip_bitis_sn']),
        'sure_sn': float(paket['klip_bitis_sn']) - float(paket['klip_baslangic_sn']),
        'kes': kes, 'kes_sure_sn': kes['sure'],
        'hls': hls or None, 'dikey_mp4': str(mp4) if mp4.exists() else None, 'erisim': erisim,
        'epoch_bas': (t0 + kes['bas']) if t0 else None, 'epoch_bit': (t0 + kes['bit']) if t0 else None,
        'dokum_metni': paket.get('dokum_metni'),
    }, None


def paket_topla(ayar: dict, dizin: pathlib.Path, gun: float, simdi: datetime, rapor: dict, vod_al=vod_getir) -> list[dict]:
    kesim_tarih = (simdi - timedelta(days=gun)).strftime('%Y-%m-%d')
    dosyalar, haric = paket_dosyalari(dizin, ayar)
    r = rapor.setdefault('paket', {'bulunan': 0, 'elenen': {}, 'kalan': 0, 'vod_hata': {}, 'dikey_geri_dusme': 0})
    nedenler = Counter()
    if haric:
        nedenler['eski_yontem_klasoru'] = haric
    r['bulunan'] = len(dosyalar) + haric
    vodlar: dict[str, dict | None] = {}
    sonuc: list[dict] = []
    for j in dosyalar:
        try:
            paket = json.loads(j.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            nedenler['okunamadi'] += 1
            continue
        neden = paket_ele_nedeni(paket, ayar, kesim_tarih)
        if neden:
            nedenler[neden] += 1
            continue
        m = VOD_URL_RE.search(paket['vod_url'])
        uuid = m.group(2).lower()
        if uuid not in vodlar:
            try:
                vodlar[uuid] = vod_al(uuid, m.group(1))
            except DerlemeHatasi as e:
                vodlar[uuid] = None
                r['vod_hata'][uuid[:8]] = str(e)
        aday, neden = paket_adayi(j.parent.name, j.stem, paket, vodlar[uuid], j.with_suffix('.mp4'), ayar)
        if neden:
            nedenler[neden] += 1
            continue
        if aday['erisim'] == 'dikey':
            r['dikey_geri_dusme'] += 1
        sonuc.append(aday)
    r['elenen'] = dict(nedenler)
    r['kalan'] = len(sonuc)
    return sonuc


# ---------------------------------------------------------------- viral videolar (elle, bağlantı, Shorts)

VIDEO_UZANTILARI = ('.mp4', '.mov', '.webm', '.mkv', '.m4v')


def ytdlp_calistir(args: list[str], zaman_asimi: int = 300) -> str:
    """yt-dlp çalıştırır. YouTube "bot değilsin" (oturum iste) engelinde çerez kullanmadan,
    farklı istemci türleriyle (android/ios/tv) bir kez daha dener."""
    def calistir(ek: list[str]):
        try:
            return subprocess.run([sys.executable, '-m', 'yt_dlp', *ek, *args], capture_output=True, text=True,
                                  encoding='utf-8', errors='replace', timeout=zaman_asimi)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise DerlemeHatasi(f'yt-dlp çalışmadı: {e} (py -m pip install --user yt-dlp)') from e
    r = calistir([])
    if r.returncode != 0 and re.search(r'not a bot|Sign in to confirm', r.stderr or ''):
        r = calistir(['--extractor-args', 'youtube:player_client=android,ios,tv'])
    if r.returncode != 0:
        raise DerlemeHatasi('yt-dlp hatası: ' + (r.stderr.strip().splitlines() or ['?'])[-1][:300])
    return r.stdout


def shorts_hedef_url(kaynak: dict) -> str:
    tur, hedef = kaynak.get('tur', 'kanal'), kaynak['hedef']
    kac = int(kaynak.get('kac', 30))
    if tur == 'kanal':
        return hedef if hedef.startswith('http') else f'https://www.youtube.com/{hedef}/shorts'
    if tur == 'etiket':
        return f'https://www.youtube.com/hashtag/{urllib.parse.quote(hedef.lstrip("#"))}/shorts'
    if tur == 'arama':
        return f'ytsearch{kac}:{hedef}'
    return hedef


def shorts_liste(kaynak: dict) -> list[dict]:
    kac = int(kaynak.get('kac', 30))
    cikti = ytdlp_calistir(['--flat-playlist', '--playlist-items', f'1:{kac}', '--dump-json', '--no-warnings',
                            shorts_hedef_url(kaynak)])
    return [json.loads(s) for s in cikti.splitlines() if s.strip().startswith('{')]


def video_detay(url: str) -> dict:
    return json.loads(ytdlp_calistir(['--skip-download', '--dump-single-json', '--no-warnings', '--no-playlist', url], 120))


def upload_tarih(d: dict) -> str | None:
    u = d.get('upload_date')
    if u and re.fullmatch(r'\d{8}', str(u)):
        return f'{u[:4]}-{u[4:6]}-{u[6:]}'
    if d.get('timestamp'):
        return datetime.fromtimestamp(d['timestamp'], timezone.utc).strftime('%Y-%m-%d')
    return None


def viral_ele_nedeni(d: dict, ayar: dict, kesim_tarih: str | None, uzun: str, serbest: bool = False) -> str | None:
    """yt-dlp ayrıntısından eleme nedeni. serbest=True: elle seçilmiş (bağlantı/dosya) — izlenme/tarih süzgeci yok."""
    sure = d.get('duration')
    if not sure:
        return 'sure_yok'
    if sure < float(ayar['viral_min_sn']):
        return 'cok_kisa'
    if viral_araligi(float(sure), ayar, uzun) is None:
        return 'cok_uzun'
    if d.get('is_live') or d.get('live_status') in ('is_live', 'is_upcoming', 'post_live'):
        return 'canli'
    if d.get('availability') not in (None, 'public', 'unlisted'):
        return 'herkese_acik_degil'
    if not serbest:
        if int(d.get('view_count') or 0) < int(ayar['viral_min_izlenme']):
            return 'dusuk_izlenme'
        t = upload_tarih(d)
        if kesim_tarih and t and t < kesim_tarih:
            return 'gun_disi'
    return None


def viral_adayi(d: dict, kaynak_adi: str, ayar: dict, uzun: str, deger: float | None = None) -> dict:
    sure = float(d['duration'])
    kes = viral_araligi(sure, ayar, uzun)
    izlenme = int(d.get('view_count') or 0)
    vid = d.get('id') or hashlib.sha1((d.get('webpage_url') or d.get('title') or '').encode()).hexdigest()[:11]
    yt = (d.get('extractor_key') or '').lower().startswith('youtube')
    return {
        'id': ('yt:' if yt else f'{(d.get("extractor") or "url").lower()}:') + vid,
        'tur': 'viral', 'kaynak': 'shorts', 'yayinci': None,
        'kanal_adi': d.get('channel') or d.get('uploader') or '', 'kanal_url': d.get('channel_url') or d.get('uploader_url') or '',
        'baslik': (d.get('title') or '').strip(), 'izlenme': izlenme or None,
        'deger': deger if deger is not None else deger_izlenme(izlenme, ayar['viral_tam_izlenme']),
        'sure_sn': sure, 'kes': kes, 'kes_sure_sn': kes['sure'], 'tarih': upload_tarih(d),
        'url': d.get('webpage_url') or d.get('original_url') or (f'https://www.youtube.com/watch?v={vid}' if yt else ''),
        'kaynak_listesi': kaynak_adi, 'yerel': None,
    }


def shorts_topla(ayar: dict, simdi: datetime, rapor: dict, gun: float | None, liste_al=shorts_liste, detay_al=video_detay) -> list[dict]:
    r = rapor.setdefault('viral', {})
    sr = r.setdefault('shorts', {})
    sonuc: list[dict] = []
    gorulen: set[str] = set()
    for kaynak in ayar.get('shorts_kaynaklari') or []:
        ad = kaynak.get('ad') or kaynak['hedef']
        kayit = {'listelenen': 0, 'detay_cozulen': 0, 'elenen': {}, 'kalan': 0}
        sr[ad] = kayit
        try:
            liste = liste_al(kaynak)
        except DerlemeHatasi as e:
            kayit['hata'] = str(e)
            continue
        kayit['listelenen'] = len(liste)
        k_gun = kaynak.get('gun', gun if gun is not None else ayar['viral_gun'])
        kesim = (simdi - timedelta(days=float(k_gun))).strftime('%Y-%m-%d') if k_gun else None
        nedenler = Counter()
        # izlenmeye göre en yüksek N'nin ayrıntısı çözülür (ayrıntı çağrısı ~2 sn)
        eslesen = []
        for e in liste:
            vid = e.get('id')
            if not vid or ('yt:' + vid) in gorulen:
                nedenler['kopya'] += 1
                continue
            if int(e.get('view_count') or 0) < int(ayar['viral_min_izlenme']):
                nedenler['dusuk_izlenme'] += 1
                continue
            if e.get('duration') and e['duration'] > 3600:
                nedenler['cok_uzun'] += 1
                continue
            eslesen.append(e)
        eslesen.sort(key=lambda e: -int(e.get('view_count') or 0))
        eslesen = eslesen[:int(ayar['shorts_detay_azami'])]
        uzun = kaynak.get('uzun', ayar['viral_uzun'])

        def coz(e):
            try:
                return e, detay_al(e.get('webpage_url') or e.get('url') or f'https://www.youtube.com/watch?v={e["id"]}'), None
            except DerlemeHatasi as ex:
                return e, None, str(ex)
        with ThreadPoolExecutor(max_workers=4) as havuz:
            sonuclar = list(havuz.map(coz, eslesen))
        for e, d, hata in sonuclar:
            if d is None:
                nedenler['detay_cozulemedi'] += 1
                continue
            kayit['detay_cozulen'] += 1
            neden = viral_ele_nedeni(d, ayar, kesim, uzun)
            if neden:
                nedenler[neden] += 1
                continue
            a = viral_adayi(d, ad, ayar, uzun)
            if a['id'] in gorulen:
                nedenler['kopya'] += 1
                continue
            gorulen.add(a['id'])
            sonuc.append(a)
            kayit['kalan'] += 1
        kayit['elenen'] = dict(nedenler)
    return sonuc


def video_bilgi(ff: str, yol: str) -> dict:
    """ffprobe yok: `ffmpeg -i` çıktısından süre, boyut (döndürme dahil), ses, başlangıç."""
    r = subprocess.run([ff, '-hide_banner', '-i', yol], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120)
    log_ = r.stderr
    d = re.search(r'Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)', log_)
    v = re.search(r'Video:.*?,\s*(\d{2,5})x(\d{2,5})', log_)
    if not (d and v):
        raise DerlemeHatasi(f'video okunamadı: {yol}: {log_.strip().splitlines()[-1] if log_.strip() else "?"}')
    w, h = int(v.group(1)), int(v.group(2))
    rot = re.search(r'rotation of (-?[\d.]+) degrees', log_)
    if rot and abs(round(float(rot.group(1)))) % 180 == 90:
        w, h = h, w
    fps = re.search(r'(\d+(?:\.\d+)?) fps', log_)
    return {'sure_sn': int(d.group(1)) * 3600 + int(d.group(2)) * 60 + float(d.group(3)), 'genislik': w, 'yukseklik': h,
            'ses': 'Audio:' in log_, 'fps': float(fps.group(1)) if fps else None}


def ara_video_topla(ayar: dict, dizin: pathlib.Path, rapor: dict, ff: str) -> list[dict]:
    kok = pathlib.Path(ayar.get('ara_video_klasoru') or dizin / 'ara-videolar')
    r = rapor.setdefault('viral', {}).setdefault('ara_video', {'klasor': str(kok), 'bulunan': 0, 'elenen': {}, 'kalan': 0})
    sonuc: list[dict] = []
    if not kok.is_dir():
        return sonuc
    nedenler = Counter()
    for f in sorted(kok.iterdir()):
        if f.suffix.lower() not in VIDEO_UZANTILARI:
            continue
        r['bulunan'] += 1
        yan = {}
        if f.with_suffix('.json').exists():
            try:
                yan = json.loads(f.with_suffix('.json').read_text(encoding='utf-8'))
            except (OSError, json.JSONDecodeError):
                yan = {}
        try:
            b = video_bilgi(ff, str(f))
        except DerlemeHatasi:
            nedenler['okunamadi'] += 1
            continue
        d = {'duration': b['sure_sn'], 'title': yan.get('baslik') or f.stem, 'channel': yan.get('kanal') or yan.get('kaynak') or '',
             'channel_url': yan.get('kaynak_url') or '', 'webpage_url': yan.get('kaynak_url') or '', 'view_count': yan.get('izlenme'),
             'id': 'dosya-' + hashlib.sha1(f.name.encode()).hexdigest()[:10], 'extractor': 'dosya'}
        neden = viral_ele_nedeni(d, ayar, None, 'kirp', serbest=True)
        if neden:
            nedenler[neden] += 1
            continue
        a = viral_adayi(d, 'ara-videolar', ayar, 'kirp', deger=float(yan.get('deger', ayar['ara_video_deger'])))
        a['id'] = 'dosya:' + f.name
        a['kaynak'] = 'ara_video'
        a['yerel'] = str(f)
        a['kaynak_bilgi'] = yan.get('kaynak') or '(belirtilmedi)'
        sonuc.append(a)
    r['elenen'] = dict(nedenler)
    r['kalan'] = len(sonuc)
    return sonuc


def baglanti_topla(ayar: dict, rapor: dict, detay_al=video_detay) -> list[dict]:
    r = rapor.setdefault('viral', {}).setdefault('baglanti', {'bulunan': 0, 'elenen': {}, 'kalan': 0})
    sonuc: list[dict] = []
    nedenler = Counter()
    for b in ayar.get('baglantilar') or []:
        url = b if isinstance(b, str) else b.get('url')
        if not url:
            continue
        r['bulunan'] += 1
        try:
            d = detay_al(url)
        except DerlemeHatasi:
            nedenler['cozulemedi'] += 1
            continue
        neden = viral_ele_nedeni(d, ayar, None, 'kirp', serbest=True)
        if neden:
            nedenler[neden] += 1
            continue
        a = viral_adayi(d, 'baglantilar', ayar, 'kirp', deger=float(ayar['ara_video_deger']))
        a['kaynak'] = 'baglanti'
        sonuc.append(a)
    r['elenen'] = dict(nedenler)
    r['kalan'] = len(sonuc)
    return sonuc


# ---------------------------------------------------------------- toplama (hepsi)

def kick_kanallari(ayar: dict) -> list[tuple[str, str]]:
    """(slug, yayıncı adı): klip-yayincilar.json içindeki etkin Kick kanalları + ayardaki ek kanallar."""
    kanallar: list[tuple[str, str]] = []
    try:
        yk_ayar = yk_yukle().ayar_yukle()
        for y in yk_ayar['yayincilar']:
            if y['platform'] == 'kick' and y.get('etkin', True):
                kanallar.append((y['kanal'], y['ad']))
    except (DerlemeHatasi, KeyError, OSError, ValueError):
        pass
    var = {k.lower() for k, _ in kanallar}
    for k in ayar.get('ek_kick_kanallari') or []:
        ad = k if isinstance(k, str) else (k.get('kanal') or '')
        ad_goster = k if isinstance(k, str) else (k.get('ad') or ad)
        if ad and ad.lower() not in var:
            kanallar.append((ad, ad_goster))
    return kanallar


def aday_topla(ayar: dict, dizin: pathlib.Path, kaynaklar: tuple[str, ...] = ('paket', 'izleyici', 'viral'),
               gun: float | None = None, simdi: datetime | None = None, durum: dict | None = None) -> tuple[list[dict], dict]:
    """Kaynaklardan aday listesi + rapor. İndirme yok (yalnız API/liste/ayrıntı istekleri ve küçük m3u8 okuma)."""
    simdi = simdi or simdi_utc()
    gun_deger = float(gun if gun is not None else ayar['gun'])
    rapor: dict = {'olusturma': simdi.strftime('%Y-%m-%dT%H:%M:%SZ'), 'gun': gun_deger,
                   'viral_gun': float(gun) if gun is not None else float(ayar['viral_gun']), 'kaynaklar': list(kaynaklar)}
    kesim_epoch = (simdi - timedelta(days=gun_deger)).timestamp()
    adaylar: list[dict] = []
    if 'paket' in kaynaklar:
        adaylar += paket_topla(ayar, dizin, gun_deger, simdi, rapor)
    if 'izleyici' in kaynaklar and ayar.get('izleyici_etkin', True):
        adaylar += izleyici_topla(ayar, kick_kanallari(ayar), gun_deger, kesim_epoch, rapor)
    if 'viral' in kaynaklar:
        ff = yk_yukle().ffmpeg_bul()
        adaylar += ara_video_topla(ayar, dizin, rapor, ff)
        adaylar += baglanti_topla(ayar, rapor)
        adaylar += shorts_topla(ayar, simdi, rapor, float(gun) if gun is not None else None)
    adaylar, kopya = kopyalari_ele(adaylar)
    adaylar, ortusen, belirsiz = ortusenleri_ele(adaylar, float(ayar['ortusme_esik_sn']))
    kul = kullanilanlari_ele(adaylar, durum if durum is not None else durum_oku(dizin))
    adaylar, kullanilmis = kul
    rapor['ortusme'] = {'elenen': ortusen, 'belirsiz_adayi_sayisi': belirsiz,
                        'not': 'epoch aralığı bilinmeyen paket/izleyici adayı (VOD ya da klip listesi PROGRAM-DATE-TIME vermedi) '
                               'örtüşme denetimine giremez; ikisi de kalır'}
    rapor['kopya_elenen'] = len(kopya)
    rapor['onceki_derlemede_kullanilan'] = kullanilmis
    rapor['aday_sayilari'] = {t: sum(1 for a in adaylar if a['tur'] == t) for t in ('yayinci', 'izleyici', 'viral')}
    return adaylar, rapor


# ---------------------------------------------------------------- başlık ve açıklama (saf; model çağrısı yok)

# tools/yayin_klip.py'nin şablon başlıkları (kopya; yk_yukle() ile gelenler de eklenir): vurucu sayılmaz.
SABLON_YEDEK = (
    '{ad} yayınında chat patladı!{oyun}', '{ad} yayınında sohbetin en çılgın anı{oyun}',
    'Chat bir anda coştu: {ad} yayını{oyun}', '{ad} yayınında herkes aynı anda yazdı!{oyun}',
    '{ad} yayınında chat kahkahaya boğuldu{oyun}', '{ad} yayınında sohbet bir anda gülmeye başladı{oyun}',
    '{ad} yayınında chat gülmekten kırıldı{oyun}', '{ad} yayınında chat aynı kelimede buluştu: “{terim}”{oyun}',
    '{ad} yayınında herkes aynı şeyi yazdı: “{terim}”{oyun}',
)


def _sablon_re(sablon: str) -> re.Pattern:
    parcalar = re.split(r'\{[a-z_]+\}', sablon)
    return re.compile('^' + '.*?'.join(re.escape(p) for p in parcalar) + '$', re.I | re.S)


def sablon_listesi() -> list[str]:
    s = list(SABLON_YEDEK)
    try:
        yk = yk_yukle()
        for ad in ('BASLIK_SABLONLARI', 'BASLIK_GULME', 'BASLIK_KONU'):
            s += list(getattr(yk, ad, ()) or ())
    except DerlemeHatasi:
        pass
    return s


def temiz_baslik(b: str | None, azami: int = 58) -> str:
    """Etiket, emoji ve süs karakterlerini atar; azami uzunlukta kelime sınırından keser."""
    b = re.sub(r'#\S+', ' ', b or '')
    b = ''.join(ch for ch in b if unicodedata.category(ch) not in ('So', 'Cs', 'Cn', 'Sk', 'Cf')
                and not 0xFE00 <= ord(ch) <= 0xFE0F)
    b = re.sub(r'\s+', ' ', b).strip(' -–—|·:;,.')
    if len(b) > azami:
        b = b[:azami].rsplit(' ', 1)[0].rstrip(' -–—|·:;,.')
    return b


def baslik_sablon_mu(b: str | None, sablonlar: list[str] | None = None) -> bool:
    b = (b or '').strip()
    if not b:
        return False
    for s in (sablonlar if sablonlar is not None else sablon_listesi()):
        if _sablon_re(s).match(b):
            return True
    return bool(re.search(r'yayınında .*(chat|sohbet|herkes)', b, re.I))


def vurucu_mu(b: str | None, sablonlar: list[str] | None = None) -> bool:
    t = temiz_baslik(b)
    if len(t) < 8 or len(t.split()) < 2:
        return False
    return not baslik_sablon_mu(b, sablonlar)


def baslik_sec(parcalar: list[dict], ayar: dict, sayi: int, sablonlar: list[str] | None = None) -> dict:
    """Önerilen başlık: `<BÜYÜK HARF OLAY> | <Seri> #<Sayı>`. Olay: en değerli parçanın başlığı vurucuysa o; değilse en çok
    izlenen vurucu izleyici klibi; o da yoksa en çok izlenen vurucu parça; hiçbiri yoksa genel başlık."""
    sablonlar = sablonlar if sablonlar is not None else sablon_listesi()
    adaylar = [p['aday'] for p in parcalar if p.get('aday') and p['rol'] in ('yayinci', 'izleyici', 'viral')]
    secim, neden = None, 'genel'
    if adaylar:
        en_iyi = max(adaylar, key=lambda a: a['deger'])
        if vurucu_mu(en_iyi.get('baslik'), sablonlar):
            secim, neden = en_iyi, 'en_degerli_parca'
        else:
            izl = [a for a in adaylar if a['tur'] == 'izleyici' and vurucu_mu(a.get('baslik'), sablonlar)]
            if izl:
                secim, neden = max(izl, key=lambda a: a.get('izlenme') or 0), 'en_cok_izlenen_izleyici_klibi'
            else:
                izl = [a for a in adaylar if (a.get('izlenme') or 0) > 0 and vurucu_mu(a.get('baslik'), sablonlar)]
                if izl:
                    secim, neden = max(izl, key=lambda a: a.get('izlenme') or 0), 'en_cok_izlenen_parca'
    olay = tr_buyuk(temiz_baslik(secim['baslik'])) if secim else 'EN ÇOK KONUŞULAN ANLAR'
    son = f' | {ayar["seri_adi"]} #{sayi}'
    if len(olay) + len(son) > 100:
        olay = olay[:100 - len(son) - 1].rsplit(' ', 1)[0]
    return {'baslik': olay + son, 'olay': olay, 'neden': neden, 'kaynak_aday': secim['id'] if secim else None}


def bolum_listesi(zamanli: list[dict], en_az_sn: float = 10.0) -> list[tuple[float, str]]:
    """YouTube bölümleri (≥10 sn, ilki 0:00): giriş + her yayıncı/izleyici kesiti. Yalnız viral varsa viral parçalar."""
    adaylar: list[tuple[float, str]] = []
    kesitler = [p for p in zamanli if p['rol'] in ('yayinci', 'izleyici')]
    kaynak_parcalar = kesitler or [p for p in zamanli if p['rol'] == 'viral']
    for p in kaynak_parcalar:
        a = p['aday']
        ad = a.get('yayinci') or a.get('kanal_adi') or 'Viral'
        t = temiz_baslik(a.get('baslik'), 45)
        adaylar.append((p['bas_sn'], f'{ad}: {t}' if t else ad))
    sonuc: list[tuple[float, str]] = [(0.0, 'Giriş')]
    for sn, ad in adaylar:
        if sn - sonuc[-1][0] < en_az_sn:
            if len(sonuc) == 1 and sonuc[0][1] == 'Giriş':
                sonuc[0] = (0.0, f'Giriş · {ad}')
            continue
        sonuc.append((sn, ad))
    return sonuc


def _kaynak_satirlari(zamanli: list[dict], ayrinti: int) -> list[str]:
    s: list[str] = []
    yayincilar: dict[str, str] = {}
    for p in zamanli:
        a = p.get('aday')
        if a and p['rol'] in ('yayinci', 'izleyici') and a.get('kanal_url'):
            yayincilar.setdefault(a['yayinci'], a['kanal_url'])
    if yayincilar:
        s.append('Yayıncılar:')
        s += [f'{ad} — {url}' for ad, url in yayincilar.items()]
        s.append('')
    kes = [p for p in zamanli if p['rol'] in ('yayinci', 'izleyici')]
    if kes:
        s.append('Yayın kesitleri:')
        for p in kes:
            a = p['aday']
            if p['rol'] == 'yayinci':
                nokta = f' (yayının {zaman_m(a["kes"]["bas"])} noktası, {a.get("tarih")})' if ayrinti == 0 else ''
                s.append(f'{zaman_m(p["bas_sn"])} {a["yayinci"]} — {a["vod_url"]}{nokta}')
            else:
                kim = f' (klibi oluşturan: {a["olusturan"]})' if ayrinti == 0 and a.get('olusturan') else ''
                s.append(f'{zaman_m(p["bas_sn"])} {a["yayinci"]} — Kick klibi: {a["web_url"]}{kim}')
        s.append('')
    vir = [p for p in zamanli if p['rol'] == 'viral']
    if vir and ayrinti <= 2:
        s.append('Viral videolar:')
        for p in vir:
            a = p['aday']
            kanal = a.get('kanal_adi') or a.get('kaynak_bilgi') or 'kaynak'
            baslik = f'{temiz_baslik(a.get("baslik"), 40)} — ' if ayrinti == 0 and a.get('baslik') else ''
            adres = a.get('url') or a.get('kanal_url') or ''
            s.append(f'{zaman_m(p["bas_sn"])} {baslik}{kanal}' + (f': {adres}' if adres else ''))
        s.append('')
    elif vir:
        s.append(f'Viral videolar ({len(vir)} adet): kaynakların tam listesi derleme.json içinde.')
        s.append('')
    return s


def aciklama_uret(zamanli: list[dict], ayar: dict, sayi: int, baslik: str, sinir: int = 4800) -> str:
    """Açıklama: özet, zaman damgalı bölümler, yayıncı bağlantıları, her kesit/viral videonun kaynağı. YouTube sınırı
    5000 karakter: sığmazsa ayrıntı kademeli azaltılır."""
    sayim = Counter(p['rol'] for p in zamanli)
    parcalar_ozet = [f'{sayim[r]} {ad}' for r, ad in (('yayinci', 'yayıncı kesiti'), ('izleyici', 'izleyici klibi'), ('viral', 'viral video')) if sayim[r]]
    bolumler = bolum_listesi(zamanli)
    ust = [baslik, '', 'Derleme: ' + ', '.join(parcalar_ozet) + '.', '']
    if len(bolumler) >= 3:
        ust += ['Bölümler:'] + [f'{zaman_m(sn)} {ad}' for sn, ad in bolumler] + ['']
    alt = ['Görüntü ve sesler ilgili yayıncılara ve hesap sahiplerine aittir; tam içerik için yukarıdaki kaynak bağlantılarına gidin.',
           ayar.get('filigran_yazi', ''), ' '.join(ayar.get('etiketler') or ['#Derleme', '#YayınKesitleri', '#Kick'])]
    for ayrinti in range(4):
        metin = '\n'.join(ust + _kaynak_satirlari(zamanli, ayrinti) + alt).strip() + '\n'
        if len(metin) <= sinir:
            return metin
    return metin[:sinir - 40].rsplit('\n', 1)[0] + '\n(Kaynak listesinin tamamı derleme.json içinde.)\n'


# ---------------------------------------------------------------- ffmpeg: parça hazırlama

def _fe(yol: str) -> str:
    """ffmpeg filtre seçeneği için yol kaçışı (Windows sürücü iki noktası)."""
    return yol.replace('\\', '/').replace(':', '\\:')


def ffmpeg_dene(ff: str, args: list[str], cwd: str | pathlib.Path | None = None, zaman_asimi: int = 1800, ad: str = '') -> None:
    try:
        r = subprocess.run([ff, '-hide_banner', '-loglevel', 'error', '-nostdin', '-y', *args], cwd=cwd,
                           capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=zaman_asimi)
    except subprocess.TimeoutExpired as e:
        raise DerlemeHatasi(f'ffmpeg zaman aşımı {ad}') from e
    if r.returncode != 0:
        raise DerlemeHatasi(f'ffmpeg başarısız {ad}: {r.stderr.strip()[-700:]}')


def etiket_metni(a: dict, ayar: dict) -> str | None:
    """Parçanın kaynak etiketi (sol alt, ilk kaynak_etiketi_sn sn). Yayıncı kesitinde yayıncı adı."""
    if a['tur'] == 'yayinci':
        return f'Yayıncı: {a["yayinci"]}  ·  kick.com/{a["kanal"]}'
    if a['tur'] == 'izleyici':
        return f'Kick klibi  ·  {a["yayinci"]}  ·  kick.com/{a["kanal"]}'
    if ayar.get('viral_etiketi'):
        return f'Kaynak: {a.get("kanal_adi") or a.get("kaynak_bilgi") or ""}'.strip()
    return None


def video_filtresi(w: int, h: int, ayar: dict, font: str, etiket: bool, sure: float) -> str:
    """Her parça 1920x1080/fps/SAR1. 16:9'a yakın kaynak doğrudan ölçeklenir; dikey/kare/4:3 kaynak ortalanır, arkada
    kendi bulanık kopyası durur. Filigran (köşede yarı saydam) hep, kaynak etiketi (sol alt, ilk N sn) isteğe bağlı."""
    W, H, fps = int(ayar['genislik']), int(ayar['yukseklik']), int(ayar['fps'])
    if h and abs(w / h - W / H) < 0.03:
        ana = f'[0:v:0]fps={fps},scale={W}:{H}:flags=lanczos,setsar=1[v0]'
    else:
        kw, kh = W // 4, H // 4
        ana = (f'[0:v:0]fps={fps},split=2[a][b];'
               f'[a]scale={kw}:{kh}:force_original_aspect_ratio=increase,crop={kw}:{kh},gblur=sigma={ayar["arka_blur"]},'
               f'scale={W}:{H},eq=brightness={ayar["arka_parlaklik"]}:saturation=0.9[bg];'
               f'[b]scale={W}:{H}:force_original_aspect_ratio=decrease:force_divisible_by=2:flags=lanczos[fg];'
               f'[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1[v0]')
    f = _fe(font)
    cizim = [f"drawtext=fontfile='{f}':textfile='t_filigran.txt':expansion=none:fontsize=44:"
             f"fontcolor=white@{ayar['filigran_opaklik']}:shadowcolor=black@0.3:shadowx=2:shadowy=2:x=w-text_w-52:y=40"]
    if etiket:
        cizim.append(f"drawtext=fontfile='{f}':textfile='t_etiket.txt':expansion=none:fontsize=40:fontcolor=white:"
                     f"box=1:boxcolor=black@0.55:boxborderw=16:x=56:y=h-text_h-62:enable='lt(t,{ayar['kaynak_etiketi_sn']})'")
    # tpad: kaynak birkaç kare kısa kalırsa son kare tekrarlanır (ses/görüntü süresi eşit kalsın)
    return ana + ';[v0]' + ','.join(cizim) + f',tpad=stop_mode=clone:stop_duration=2,trim=duration={sure:.3f},setpts=PTS-STARTPTS,format=yuv420p[v]'


def ses_olc(ff: str, wav: pathlib.Path, ayar: dict) -> dict | None:
    """loudnorm 1. geçiş: ölçüm (JSON). Sessizse None."""
    r = subprocess.run([ff, '-hide_banner', '-nostats', '-nostdin', '-i', str(wav), '-af',
                        f'loudnorm=I={ayar["ses_hedef_lufs"]}:TP={ayar["ses_tepe_db"]}:LRA={ayar["ses_lra"]}:print_format=json',
                        '-f', 'null', '-'], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=300)
    bloklar = re.findall(r'\{[^{}]*"input_i"[^{}]*\}', r.stderr, re.S)
    if not bloklar:
        raise DerlemeHatasi('loudnorm ölçümü okunamadı: ' + r.stderr.strip()[-300:])
    j = json.loads(bloklar[-1])
    try:
        ii = float(j['input_i'])
    except ValueError:
        return None
    if not math.isfinite(ii) or ii < -60:
        return None
    return {k: float(j[k]) for k in ('input_i', 'input_tp', 'input_lra', 'input_thresh', 'target_offset')}


def ses_filtresi(olcum: dict | None, sure: float, ayar: dict) -> str:
    kenar = 0.015
    son = f'aresample=48000,afade=t=in:d={kenar},afade=t=out:st={max(sure - kenar, 0):.3f}:d={kenar},apad=whole_dur={sure:.3f}'
    if olcum is None:
        return son
    return (f'loudnorm=I={ayar["ses_hedef_lufs"]}:TP={ayar["ses_tepe_db"]}:LRA={ayar["ses_lra"]}:'
            f'measured_I={olcum["input_i"]}:measured_TP={olcum["input_tp"]}:measured_LRA={olcum["input_lra"]}:'
            f'measured_thresh={olcum["input_thresh"]}:offset={olcum["target_offset"]}:linear=true,' + son)


def parca_uret(ff: str, font: str, ad: str, k: dict, etiket: str | None, calisma: pathlib.Path, ayar: dict, zorla: bool = False) -> dict:
    """Tek parçayı hazırlar: kaynaktan kes → 1920x1080/fps/48 kHz stereo → ses düzeyi eşitle → <ad>.mkv (H.264 + PCM).
    k: {'yol','ss','sure','w','h','ses'}. Aynı ada kayıtlı geçerli dosya varsa yeniden kullanılır."""
    cikis = calisma / f'{ad}.mkv'
    D = float(k['sure'])
    if cikis.exists() and not zorla:
        try:
            b = video_bilgi(ff, str(cikis))
            if abs(b['sure_sn'] - D) < 0.25 and b['ses']:
                return {'dosya': str(cikis), 'sure_sn': b['sure_sn'], 'yeniden_kullanildi': True}
        except DerlemeHatasi:
            pass
    gec = calisma / f'_{ad}'
    gec.mkdir(parents=True, exist_ok=True)
    (gec / 't_filigran.txt').write_text(ayar['filigran_yazi'], encoding='utf-8')
    (gec / 't_etiket.txt').write_text(etiket or ' ', encoding='utf-8')
    girdi = ['-ss', f'{k["ss"]:.3f}', '-i', k['yol']]
    amap = '0:a:0'
    if not k.get('ses', True):
        girdi += ['-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo']
        amap = '1:a:0'
    filtre = video_filtresi(k['w'], k['h'], ayar, font, bool(etiket), D)
    ffmpeg_dene(ff, [*girdi, '-filter_complex', filtre,
                     '-map', '[v]', '-an', '-c:v', 'libx264', '-preset', ayar['ara_on_ayar'], '-crf', str(ayar['ara_crf']),
                     '-pix_fmt', 'yuv420p', '-r', str(ayar['fps']), '-t', f'{D:.3f}', 'video.mp4',
                     '-map', amap, '-vn', '-af',
                     f'aresample=48000:async=1,aformat=sample_fmts=s16:channel_layouts=stereo,apad=whole_dur={D:.3f}',
                     '-c:a', 'pcm_s16le', '-t', f'{D:.3f}', 'ham.wav'], cwd=gec, ad=ad)
    olcum = ses_olc(ff, gec / 'ham.wav', ayar)
    ffmpeg_dene(ff, ['-i', 'video.mp4', '-i', 'ham.wav', '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy',
                     '-af', ses_filtresi(olcum, D, ayar), '-c:a', 'pcm_s16le', '-ar', '48000', '-ac', '2',
                     '-t', f'{D:.3f}', 'parca.mkv'], cwd=gec, ad=ad + '/ses')
    shutil.move(str(gec / 'parca.mkv'), str(cikis))
    b = video_bilgi(ff, str(cikis))
    return {'dosya': str(cikis), 'sure_sn': b['sure_sn'], 'ses_once_lufs': olcum['input_i'] if olcum else None,
            'ses_once_tepe_db': olcum['input_tp'] if olcum else None, 'sessiz': olcum is None, 'yeniden_kullanildi': False}


def kart_uret(ff: str, font: str, ad: str, sure: float, satirlar: list[tuple[str, int, str, int]], calisma: pathlib.Path, ayar: dict) -> dict:
    """Giriş/kapanış kartı: koyu zemin, ortalanmış yazı satırları [(metin, boyut, renk, y_kayma)], sessiz stereo ses."""
    cikis = calisma / f'{ad}.mkv'
    gec = calisma / f'_{ad}'
    gec.mkdir(parents=True, exist_ok=True)
    W, H = int(ayar['genislik']), int(ayar['yukseklik'])
    f = _fe(font)
    cizim = [f'drawbox=x=0:y=ih/2-230:w=iw:h=8:color=0xFFD54A@1:t=fill', f'drawbox=x=0:y=ih/2+250:w=iw:h=8:color=0xFFD54A@1:t=fill']
    for i, (metin, boyut, renk, ky) in enumerate(satirlar):
        (gec / f't{i}.txt').write_text(metin, encoding='utf-8')
        boyut = max(28, min(boyut, int((W - 160) / (0.60 * max(len(metin), 1)))))
        cizim.append(f"drawtext=fontfile='{f}':textfile='t{i}.txt':expansion=none:fontsize={boyut}:fontcolor={renk}:"
                     f"borderw=3:bordercolor=black@0.6:x=(w-text_w)/2:y=(h-text_h)/2+({ky})")
    ffmpeg_dene(ff, ['-f', 'lavfi', '-i', f'color=c=0x0B0D17:s={W}x{H}:r={ayar["fps"]}', '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo',
                     '-vf', ','.join(cizim) + ',format=yuv420p', '-t', f'{sure:.3f}', '-c:v', 'libx264', '-preset', ayar['ara_on_ayar'],
                     '-crf', str(ayar['ara_crf']), '-pix_fmt', 'yuv420p', '-r', str(ayar['fps']), '-c:a', 'pcm_s16le', '-ar', '48000',
                     '-ac', '2', '-shortest', str(cikis)], cwd=gec, ad=ad)
    return {'dosya': str(cikis), 'sure_sn': video_bilgi(ff, str(cikis))['sure_sn']}


def teaser_uret(ff: str, parca: str, tepe: float, sure: float, parca_sure: float, cikis: pathlib.Path, ayar: dict) -> dict:
    """Hazır (ses düzeyi eşitlenmiş) parçadan `sure` sn'lik teaser: tepe anının 1 sn öncesinden başlar."""
    bas = max(0.0, min(tepe - 1.0, parca_sure - sure))
    kenar = 0.015
    ffmpeg_dene(ff, ['-ss', f'{bas:.3f}', '-i', parca, '-t', f'{sure:.3f}', '-c:v', 'libx264', '-preset', ayar['ara_on_ayar'],
                     '-crf', str(ayar['ara_crf']), '-pix_fmt', 'yuv420p', '-r', str(ayar['fps']),
                     '-af', f'afade=t=in:d={kenar},afade=t=out:st={sure - kenar:.3f}:d={kenar}', '-c:a', 'pcm_s16le',
                     '-ar', '48000', '-ac', '2', str(cikis)], ad=cikis.name)
    return {'dosya': str(cikis), 'sure_sn': video_bilgi(ff, str(cikis))['sure_sn'], 'kaynak_bas_sn': round(bas, 2)}


def birlestir(ff: str, dosyalar: list[str], liste: pathlib.Path, cikis: pathlib.Path, ayar: dict) -> None:
    """Concat demuxer + tek seferde son kodlama (H.264 + AAC). Parçalar zaten aynı biçimde; ses PCM'den tek akışta
    AAC'ye çevrildiği için parça sınırlarında AAC dolgu boşluğu/kayma oluşmaz."""
    satirlar = []
    for d in dosyalar:
        satirlar.append("file '" + d.replace('\\', '/').replace("'", "'\\''") + "'")
    liste.write_text('\n'.join(satirlar) + '\n', encoding='utf-8')
    ffmpeg_dene(ff, ['-f', 'concat', '-safe', '0', '-i', str(liste), '-c:v', 'libx264', '-preset', ayar['kodlama_on_ayar'],
                     '-crf', str(ayar['crf']), '-pix_fmt', 'yuv420p', '-r', str(ayar['fps']), '-c:a', 'aac',
                     '-b:a', f'{ayar["ses_kbps"]}k', '-ar', '48000', '-ac', '2', '-movflags', '+faststart', str(cikis)],
                zaman_asimi=7200, ad='birlestir')


def kare_cikar(ff: str, kaynak: str, t: float, cikis: pathlib.Path) -> None:
    ffmpeg_dene(ff, ['-ss', f'{max(t, 0):.3f}', '-i', kaynak, '-frames:v', '1', str(cikis)], ad=cikis.name)


# ---------------------------------------------------------------- kaynak çözme / indirme

def guvenli_ad(s: str) -> str:
    return re.sub(r'[^A-Za-z0-9._-]+', '_', s)[:60]


def viral_indir(ff: str, a: dict, dizin: pathlib.Path) -> tuple[str, int]:
    """Viral aday için yerel dosya yolu ve bu çağrıda indirilen bayt. Elle bırakılan dosyalar indirilmez."""
    if a.get('yerel'):
        return a['yerel'], 0
    hedef = derleme_dizini(dizin) / 'indirilen'
    hedef.mkdir(parents=True, exist_ok=True)
    gid = guvenli_ad(a['id'])
    mevcut = [p for p in hedef.glob(gid + '.*') if p.suffix.lower() in VIDEO_UZANTILARI]
    if mevcut:
        return str(mevcut[0]), 0
    ytdlp_calistir(['-S', 'res:1080', '-f', 'bv*+ba/b', '--merge-output-format', 'mp4', '--ffmpeg-location', ff, '--no-playlist',
                    '--no-warnings', '--no-progress', '-o', str(hedef / f'{gid}.%(ext)s'), a['url']], 600)
    dosyalar = [p for p in hedef.glob(gid + '.*') if p.suffix.lower() in VIDEO_UZANTILARI]
    if not dosyalar:
        raise DerlemeHatasi(f'indirilen dosya bulunamadı: {a["url"]}')
    return str(dosyalar[0]), dosyalar[0].stat().st_size


def kaynak_belirle(ff: str, a: dict, yol_yerel: str | None, geri_dus: bool = False) -> dict:
    """Adayın kesim girdisi. geri_dus=True: yayıncı paketi için dikey mp4 (yayın kalkmış/HLS açılmadı)."""
    kes = a['kes']
    if a['tur'] == 'yayinci':
        if not geri_dus and a.get('hls'):
            return {'yol': a['hls'], 'ss': kes['bas'], 'sure': kes['sure'], 'w': 1920, 'h': 1080, 'ses': True, 'tur': 'hls'}
        mp4 = a.get('dikey_mp4')
        if not mp4 or not pathlib.Path(mp4).exists():
            raise DerlemeHatasi('yayın kaynağı kullanılamıyor ve dikey mp4 yok')
        b = video_bilgi(ff, mp4)
        ss = max(0.0, kes['bas'] - a['klip_baslangic_sn'])
        sure = min(kes['sure'], b['sure_sn'] - ss - 0.05)
        return {'yol': mp4, 'ss': ss, 'sure': round(sure, 2), 'w': b['genislik'], 'h': b['yukseklik'], 'ses': b['ses'], 'tur': 'dikey_mp4'}
    if a['tur'] == 'izleyici':
        w, h, ses = 1920, 1080, True
        try:   # klip çözünürlüğü/sesi gerçekten okunur (küçük m3u8 isteği); okunamazsa 1080p varsayılır
            b = video_bilgi(ff, a['klip_url'])
            w, h, ses = b['genislik'], b['yukseklik'], b['ses']
        except (DerlemeHatasi, subprocess.SubprocessError, OSError):
            pass
        return {'yol': a['klip_url'], 'ss': kes['bas'], 'sure': kes['sure'], 'w': w, 'h': h, 'ses': ses, 'tur': 'kick_klip'}
    b = video_bilgi(ff, yol_yerel)
    sure = min(kes['sure'], b['sure_sn'] - 0.05)
    return {'yol': yol_yerel, 'ss': 0.0, 'sure': round(sure, 2), 'w': b['genislik'], 'h': b['yukseklik'], 'ses': b['ses'],
            'tur': 'dosya' if a.get('yerel') else 'indirilen'}


def aday_parcasi(ff: str, font: str, ad: str, a: dict, yol_yerel: str | None, calisma: pathlib.Path, ayar: dict, zorla: bool) -> dict:
    """Adayı hazırlar. Yayıncı paketinde HLS başarısız olursa dikey mp4'e düşer ve bunu sonuca yazar."""
    etiket = etiket_metni(a, ayar)
    deneme = [False] if a['tur'] != 'yayinci' else ([False, True] if a.get('hls') and a.get('dikey_mp4') else [not a.get('hls')])
    son_hata = None
    for geri in deneme:
        try:
            k = kaynak_belirle(ff, a, yol_yerel, geri_dus=geri)
            if geri and a['tur'] == 'yayinci':
                etiket = etiket  # dikey mp4 kendi yazılarını taşır; yine de kaynak etiketi kalır (tutarlılık)
            s = parca_uret(ff, font, ad, k, etiket, calisma, ayar, zorla)
            s.update({'kaynak_turu': k['tur'], 'kaynak_ss': k['ss'], 'kaynak_sure': k['sure'],
                      'kaynak_w': k['w'], 'kaynak_h': k['h']})
            if geri and a.get('hls'):
                s['geri_dusme'] = f'HLS açılamadı, dikey mp4 kullanıldı: {son_hata}'
            elif geri:
                s['geri_dusme'] = 'yayın kaynağı (HLS) yok, dikey mp4 kullanıldı'
            return s
        except DerlemeHatasi as e:
            son_hata = str(e)[:200]
    raise DerlemeHatasi(f'{a["id"]}: {son_hata}')


# ---------------------------------------------------------------- üretim (orkestrasyon)

def parca_adi(a: dict) -> str:
    return 'p-' + guvenli_ad(a['id'])[:40] + '-' + hashlib.sha1(a['id'].encode()).hexdigest()[:6]


def _hazirla_bir(ff: str, font: str, a: dict, dizin: pathlib.Path, calisma: pathlib.Path, ayar: dict, zorla: bool) -> dict:
    """Adayı indirir (viral) ve parça dosyasına çevirir. Hata -> DerlemeHatasi."""
    yerel, bayt = (None, 0)
    if a['tur'] == 'viral':
        yerel, bayt = viral_indir(ff, a, dizin)
    s = aday_parcasi(ff, font, parca_adi(a), a, yerel, calisma, ayar, zorla)
    s['indirilen_bayt'] = bayt
    return s


def tepe_sn(a: dict, parca_sure: float) -> float:
    """Aday parçasındaki 'en iyi an' (teaser ve küçük resim için)."""
    t = float((a.get('kes') or {}).get('tepe') or parca_sure * 0.4)
    return sinirla(t, 0.0, max(parca_sure - 0.1, 0.0))


def gercek_toplam(plan: dict, hazir: dict, ayar: dict) -> float:
    t = float(ayar['giris_karti_sn']) + float(ayar['kapanis_karti_sn'])
    for p in plan['parcalar']:
        if p['rol'] == 'teaser':
            t += p['sure_sn']
        elif p['aday'] is not None:
            t += hazir[p['aday']['id']]['sure_sn']
    return t


def planla_ve_hazirla(adaylar: list[dict], ayar: dict, hedef_sn: float, turler: tuple[str, ...], ff: str, font: str,
                      dizin: pathlib.Path, calisma: pathlib.Path, zorla: bool = False, tur_siniri: int = 4) -> tuple[dict, dict, list[dict]]:
    """Plan kur → parçaları hazırla → başarısız adayı ele, süre sapmasını düzeltip yeniden planla.
    Dönüş: (plan, hazir{aday_id: sonuç}, elenenler[{id, neden}])."""
    elenen: dict[str, str] = {}
    hazir: dict[str, dict] = {}
    hedef = hedef_sn
    en_iyi_plan = None
    asgari, azami = ayar['sure_min_dk'] * 60, ayar['sure_max_dk'] * 60
    for tur in range(tur_siniri):
        plan = plan_olustur([a for a in adaylar if a['id'] not in elenen], ayar, hedef, turler)
        gerekli = {p['aday']['id']: p['aday'] for p in plan['parcalar'] if p['aday'] is not None and p['rol'] != 'teaser'}
        bekleyen = [a for i, a in gerekli.items() if i not in hazir]
        log(f'[tur {tur + 1}] plan: {plan["sayilar"]["govde_parca"]} parça, {zaman_m(plan["toplam_sn"])}; hazırlanacak {len(bekleyen)}')
        if bekleyen:
            with ThreadPoolExecutor(max_workers=max(1, int(ayar['is_parcacigi']))) as ex:
                gelecek = {a['id']: ex.submit(_hazirla_bir, ff, font, a, dizin, calisma, ayar, zorla) for a in bekleyen}
                for i, g in gelecek.items():
                    try:
                        hazir[i] = g.result()
                        log(f'  hazır {i} ({hazir[i]["sure_sn"]:.1f} sn)')
                    except (DerlemeHatasi, subprocess.SubprocessError, OSError) as e:
                        elenen[i] = str(e)[:220]
                        log(f'  ELENDİ {i}: {elenen[i]}')
        if any(i in elenen for i in gerekli):
            continue                      # başarısızlar çıktı: yeniden planla
        toplam = gercek_toplam(plan, hazir, ayar)
        plan['gercek_toplam_sn'] = round(toplam, 2)
        en_iyi_plan = plan
        if asgari <= toplam <= azami:
            break
        hedef += (hedef_sn - toplam)      # sapmayı hedefe ekle ve yeniden planla
        log(f'  süre {zaman_m(toplam)} aralık dışı; hedef {zaman_m(hedef)} ile yeniden plan')
    if en_iyi_plan is None:
        raise DerlemeHatasi('hiçbir plan hazırlanamadı (adayların hepsi başarısız oldu)')
    return en_iyi_plan, hazir, [{'id': i, 'neden': n} for i, n in elenen.items()]


def kart_satirlari(ayar: dict, sayi: int, giris: bool) -> list[tuple[str, int, str, int]]:
    if giris:
        return [(tr_buyuk(ayar['seri_adi']), 120, 'white', -50), (f'#{sayi}', 90, '0xFFD54A', 70),
                (ayar['giris_alt_yazi'], 40, 'white', 170)]
    return [(ayar['kapanis_yazi'], 100, 'white', -40), (ayar['kapanis_alt_yazi'], 44, '0xFFD54A', 100),
            (ayar['filigran_yazi'], 36, 'white', 190)]


def parca_kaydi(p: dict, sira: int, bas: float, sure: float, hz: dict | None) -> dict:
    a = p['aday']
    k = {'sira': sira, 'rol': p['rol'], 'bas_sn': round(bas, 2), 'bit_sn': round(bas + sure, 2), 'sure_sn': round(sure, 2)}
    if a:
        kes = a['kes']
        ss = (hz or {}).get('kaynak_ss', kes['bas'])
        k.update({'tur': a['tur'], 'id': a['id'], 'kaynak': a.get('kaynak'), 'yayinci': a.get('yayinci'),
                  'kanal': a.get('kanal') or a.get('kanal_adi'), 'baslik': a.get('baslik'),
                  'adres': a.get('vod_url') or a.get('web_url') or a.get('url'), 'izlenme': a.get('izlenme'),
                  'puan': a.get('puan'), 'deger': round(a['deger'], 3), 'kaynak_bas_sn': round(ss, 2),
                  'kaynak_bit_sn': round(ss + sure, 2), 'kaynak_turu': (hz or {}).get('kaynak_turu'),
                  'kaynak_cozunurluk': f'{hz.get("kaynak_w")}x{hz.get("kaynak_h")}' if hz else None,
                  'ses_once_lufs': (hz or {}).get('ses_once_lufs'), 'geri_dusme': (hz or {}).get('geri_dusme')})
    return k


def uret(ayar: dict, dizin: pathlib.Path, kaynaklar: tuple[str, ...] = ('paket', 'izleyici', 'viral'), gun: float | None = None,
         hedef_dk: float | None = None, turler: tuple[str, ...] = ('yayinci', 'izleyici', 'viral'), kuru: bool = False,
         adaylar_dosyasi: pathlib.Path | None = None, zorla: bool = False) -> dict:
    t_basla = time.time()
    yk = yk_yukle()
    ff, font = yk.ffmpeg_bul(), yk.font_bul()
    durum = durum_oku(dizin)
    if adaylar_dosyasi:
        yuk = json.loads(pathlib.Path(adaylar_dosyasi).read_text(encoding='utf-8'))
        adaylar, toplama_rapor = yuk['adaylar'], yuk.get('rapor', {})
        adaylar, _kul = kullanilanlari_ele(adaylar, durum)
    else:
        adaylar, toplama_rapor = aday_topla(ayar, dizin, kaynaklar, gun, durum=durum)
    toplama_sn = time.time() - t_basla
    hedef_sn = float(hedef_dk if hedef_dk is not None else ayar['sure_dk']) * 60
    if kuru:
        plan = plan_olustur(adaylar, ayar, hedef_sn, turler)
        return {'kuru': True, 'plan': plan_ozeti(plan), 'toplama': toplama_rapor}
    sayi = sonraki_sayi(durum, ayar['seri_adi'])
    ad = f'{slug(ayar["seri_adi"])}-{sayi}'
    kok = derleme_dizini(dizin) / ad
    calisma = kok / 'parcalar'
    calisma.mkdir(parents=True, exist_ok=True)
    plan, hazir, elenenler = planla_ve_hazirla(adaylar, ayar, hedef_sn, turler, ff, font, dizin, calisma, zorla)
    hazirlama_sn = time.time() - t_basla - toplama_sn

    # kartlar ve teaser
    giris_p = next(p for p in plan['parcalar'] if p['rol'] == 'giris')
    kap_p = next(p for p in plan['parcalar'] if p['rol'] == 'kapanis')
    giris = kart_uret(ff, font, 'giris', giris_p['sure_sn'], kart_satirlari(ayar, sayi, True), calisma, ayar)
    kapanis = kart_uret(ff, font, 'kapanis', kap_p['sure_sn'], kart_satirlari(ayar, sayi, False), calisma, ayar)
    sira: list[tuple[dict, str, float]] = []        # (plan parçası, dosya, gerçek süre)
    tn = 0
    for p in plan['parcalar']:
        if p['rol'] == 'teaser':
            tn += 1
            hz = hazir[p['aday']['id']]
            t = teaser_uret(ff, hz['dosya'], tepe_sn(p['aday'], hz['sure_sn']), p['sure_sn'], hz['sure_sn'],
                            calisma / f'teaser-{tn}.mkv', ayar)
            sira.append((p, t['dosya'], t['sure_sn']))
        elif p['rol'] == 'giris':
            sira.append((p, giris['dosya'], giris['sure_sn']))
        elif p['rol'] == 'kapanis':
            sira.append((p, kapanis['dosya'], kapanis['sure_sn']))
        else:
            hz = hazir[p['aday']['id']]
            sira.append((p, hz['dosya'], hz['sure_sn']))
    cikis = kok / 'derleme.mp4'
    birlestir(ff, [d for _, d, _ in sira], kok / 'liste.txt', cikis, ayar)
    # zaman çizelgesi (gerçek parça süreleri; derleme zamanı = ardışık toplam)
    t = 0.0
    kayitlar, zamanli = [], []
    for i, (p, d, sure) in enumerate(sira, 1):
        hz = hazir.get(p['aday']['id']) if p['aday'] else None
        kayitlar.append(parca_kaydi(p, i, t, sure, hz))
        if p['rol'] in ('yayinci', 'izleyici', 'viral'):
            zamanli.append({'rol': p['rol'], 'aday': p['aday'], 'bas_sn': t})
        t += sure
    govde = [p for p, _, _ in sira if p['rol'] in ('yayinci', 'izleyici', 'viral')]
    b = video_bilgi(ff, str(cikis))
    en_degerli = sorted({p['aday']['id']: p['aday'] for p in govde}.values(), key=lambda a: -a['deger'])[:3]
    kucukler = []
    for n, a in enumerate(en_degerli, 1):
        k = next(x for x in kayitlar if x.get('id') == a['id'] and x['rol'] != 'teaser')
        yol = kok / f'kucuk-resim-{n}.png'
        kare_cikar(ff, str(cikis), k['bas_sn'] + tepe_sn(a, k['sure_sn']), yol)
        kucukler.append({'dosya': str(yol), 'aday': a['id'], 'yayinci': a.get('yayinci'), 'baslik': a.get('baslik')})
    bsl = baslik_sec([{'aday': p['aday'], 'rol': p['rol']} for p in govde], ayar, sayi)
    aciklama = aciklama_uret(zamanli, ayar, sayi, bsl['baslik'])
    sayilar = {r: sum(1 for p in govde if p['rol'] == r) for r in ('yayinci', 'izleyici', 'viral')}
    bayt = sum(h.get('indirilen_bayt', 0) for h in hazir.values())
    sonuc = {
        'seri': ayar['seri_adi'], 'sayi': sayi, 'ad': ad, 'olusturma': simdi_utc().strftime('%Y-%m-%dT%H:%M:%SZ'),
        'baslik': bsl['baslik'], 'baslik_bilgi': {k: bsl[k] for k in ('olay', 'neden', 'kaynak_aday')},
        'aciklama': aciklama, 'yayinlandi': False,
        'dosya': str(cikis), 'sure_sn': round(b['sure_sn'], 2), 'cozunurluk': f'{b["genislik"]}x{b["yukseklik"]}',
        'fps': ayar['fps'], 'sayilar': sayilar, 'parcalar': kayitlar, 'kucuk_resimler': kucukler,
        'uyarilar': plan['uyarilar'], 'elenen_adaylar': elenenler,
        'olcum': {'toplama_sn': round(toplama_sn, 1), 'hazirlama_sn': round(hazirlama_sn, 1),
                  'toplam_uretim_sn': round(time.time() - t_basla, 1), 'indirilen_bayt': bayt,
                  'cikti_bayt': cikis.stat().st_size, 'toplama': toplama_rapor},
    }
    (kok / 'derleme.json').write_text(json.dumps(sonuc, ensure_ascii=False, indent=2), encoding='utf-8')
    (kok / 'aciklama.txt').write_text(aciklama, encoding='utf-8')
    durum = durum_oku(dizin)
    kullanilanlari_isle(durum, ayar['seri_adi'], sayi, ad, [{'aday': p['aday'], 'rol': p['rol']} for p in govde])
    durum_yaz(dizin, durum)
    log(f'tamam: {cikis} ({zaman_m(b["sure_sn"])}, {cikis.stat().st_size / 1e6:.0f} MB, üretim {sonuc["olcum"]["toplam_uretim_sn"]:.0f} sn)')
    return sonuc


# ---------------------------------------------------------------- doğrulama

def _son_sure(metin: str) -> float | None:
    t = re.findall(r'time=(\d+):(\d+):(\d+(?:\.\d+)?)', metin)
    return int(t[-1][0]) * 3600 + int(t[-1][1]) * 60 + float(t[-1][2]) if t else None


def akis_sure(ff: str, yol: str, harita: str) -> float | None:
    r = subprocess.run([ff, '-hide_banner', '-nostdin', '-i', yol, '-map', f'0:{harita}', '-c', 'copy', '-f', 'null', '-'],
                       capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=900)
    return _son_sure(r.stderr)


def lufs_olc(ff: str, yol: str, bas: float, sure: float) -> float | None:
    r = subprocess.run([ff, '-hide_banner', '-nostats', '-nostdin', '-ss', f'{bas:.3f}', '-t', f'{sure:.3f}', '-i', yol, '-vn',
                        '-af', 'ebur128=framelog=quiet', '-f', 'null', '-'],
                       capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=300)
    m = re.findall(r'\bI:\s+(-?\d+(?:\.\d+)?)\s+LUFS', r.stderr)
    return float(m[-1]) if m else None


def sahne_gecisleri(ff: str, yol: str, bas: float, sure: float, esik: float = 0.25) -> list[float]:
    """[bas, bas+sure] aralığındaki sahne geçişlerinin (mutlak) zamanları."""
    r = subprocess.run([ff, '-hide_banner', '-nostdin', '-ss', f'{bas:.3f}', '-t', f'{sure:.3f}', '-copyts', '-i', yol, '-an',
                        '-vf', f"select='gt(scene,{esik})',showinfo", '-f', 'null', '-'],
                       capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=300)
    return [float(x) for x in re.findall(r'pts_time:(\d+(?:\.\d+)?)', r.stderr)]


def _dikey_mi(coz: str | None) -> bool:
    try:
        w, h = (int(x) for x in (coz or '').split('x'))
        return h > w * 0.9
    except ValueError:
        return False


def dogrula(ayar: dict, klasor: pathlib.Path, en_az_lufs_parca: int = 5, en_az_kare: int = 8) -> dict:
    """Bitmiş derlemeyi ölçer: biçim, ses düzeyi (parça başına LUFS), ses/görüntü eşliği, kare çıkarma."""
    ff = yk_yukle().ffmpeg_bul()
    meta = json.loads((klasor / 'derleme.json').read_text(encoding='utf-8'))
    mp4 = str(klasor / 'derleme.mp4')
    b = video_bilgi(ff, mp4)
    kayit = meta['parcalar']
    sonuc: dict = {'dosya': mp4, 'sure_sn': round(b['sure_sn'], 2), 'cozunurluk': f'{b["genislik"]}x{b["yukseklik"]}',
                   'fps': b['fps'], 'ses_var': b['ses'], 'cikti_bayt': pathlib.Path(mp4).stat().st_size}
    sonuc['sure_uygun'] = ayar['sure_min_dk'] * 60 <= b['sure_sn'] <= ayar['sure_max_dk'] * 60
    # ses/görüntü akış süreleri
    sv, sa = akis_sure(ff, mp4, 'v:0'), akis_sure(ff, mp4, 'a:0')
    sonuc['akis_sureleri'] = {'goruntu_sn': sv, 'ses_sn': sa, 'fark_sn': round(abs(sv - sa), 3) if sv and sa else None}
    # plan zamanı ile gerçek zaman: kapanış kartının başladığı sahne geçişi
    kap = next(k for k in kayit if k['rol'] == 'kapanis')
    gecis = sahne_gecisleri(ff, mp4, max(kap['bas_sn'] - 3, 0), 6)
    en_yakin = min(gecis, key=lambda x: abs(x - kap['bas_sn'])) if gecis else None
    sonuc['kapanis_esligi'] = {'plan_bas_sn': kap['bas_sn'], 'gercek_gecis_sn': en_yakin,
                               'fark_sn': round(abs(en_yakin - kap['bas_sn']), 3) if en_yakin is not None else None}
    # ses düzeyi: gövde parçalarından eşit aralıklı en az N tane
    govde = [k for k in kayit if k['rol'] in ('yayinci', 'izleyici', 'viral')]
    adim = max(1, len(govde) // max(en_az_lufs_parca, 1))
    secim = govde[::adim][:max(en_az_lufs_parca, 6)]
    olcumler = []
    for k in secim:
        olcumler.append({'sira': k['sira'], 'rol': k['rol'], 'bas_sn': k['bas_sn'], 'lufs': lufs_olc(ff, mp4, k['bas_sn'], k['sure_sn'])})
    hedef = float(ayar['ses_hedef_lufs'])
    gecerli = [o for o in olcumler if o['lufs'] is not None]
    sonuc['lufs'] = {'hedef': hedef, 'olcumler': olcumler,
                     'hepsi_icinde': all(abs(o['lufs'] - hedef) <= 2.0 for o in gecerli) and len(gecerli) >= en_az_lufs_parca}
    # kare çıkarma
    kare_dizin = klasor / 'kareler'
    kare_dizin.mkdir(exist_ok=True)
    istek: list[tuple[str, float]] = []
    teaser = [k for k in kayit if k['rol'] == 'teaser']
    if teaser:
        istek.append(('teaser', teaser[0]['bas_sn'] + 0.8))
    giris = next((k for k in kayit if k['rol'] == 'giris'), None)
    if giris:
        istek.append(('giris-karti', giris['bas_sn'] + giris['sure_sn'] / 2))
    kes = [k for k in govde if k['rol'] in ('yayinci', 'izleyici')]
    for n, k in enumerate(kes[:2], 1):
        istek.append((f'yayinci{n}-etiketli', k['bas_sn'] + 1.5))
    if kes:
        istek.append(('yayinci-orta', kes[0]['bas_sn'] + kes[0]['sure_sn'] / 2))
    vir = [k for k in govde if k['rol'] == 'viral']
    dikey = [k for k in vir if _dikey_mi(k.get('kaynak_cozunurluk'))]
    yatay = [k for k in vir if k not in dikey]
    for n, k in enumerate((dikey[:2] + yatay[:1]), 1):
        istek.append((f'viral{n}' + ('-dikey' if k in dikey else '-yatay'), k['bas_sn'] + min(2.0, k['sure_sn'] / 2)))
    if govde:
        orta = govde[len(govde) // 2]
        istek.append(('orta', orta['bas_sn'] + orta['sure_sn'] / 2))
        son = govde[-1]
        istek.append(('son-parca', son['bas_sn'] + son['sure_sn'] - 1.0))
    kapk = next((k for k in kayit if k['rol'] == 'kapanis'), None)
    if kapk:
        istek.append(('kapanis-karti', kapk['bas_sn'] + 2.0))
    kareler = []
    for n, (ad, t) in enumerate(istek, 1):
        yol = kare_dizin / f'kare-{n:02d}-{ad}.png'
        kare_cikar(ff, mp4, min(t, b['sure_sn'] - 0.2), yol)
        kareler.append({'ad': ad, 't_sn': round(t, 2), 'dosya': str(yol)})
    sonuc['kareler'] = kareler
    sonuc['kare_yeterli'] = len(kareler) >= en_az_kare
    akis_fark = sonuc['akis_sureleri']['fark_sn']
    kap_fark = sonuc['kapanis_esligi']['fark_sn']
    sonuc['gecti'] = bool(sonuc['sure_uygun'] and sonuc['cozunurluk'] == f'{ayar["genislik"]}x{ayar["yukseklik"]}' and b['ses']
                          and sonuc['lufs']['hepsi_icinde'] and sonuc['kare_yeterli']
                          and akis_fark is not None and akis_fark <= 0.1 and kap_fark is not None and kap_fark <= 0.1)
    (klasor / 'dogrulama.json').write_text(json.dumps(sonuc, ensure_ascii=False, indent=2), encoding='utf-8')
    return sonuc


# ---------------------------------------------------------------- komut satırı

def _kaynaklar(s: str) -> tuple[str, ...]:
    ge = tuple(x.strip() for x in s.split(',') if x.strip())
    kotu = [x for x in ge if x not in ('paket', 'izleyici', 'viral')]
    if kotu:
        raise argparse.ArgumentTypeError(f'bilinmeyen kaynak: {kotu} (paket, izleyici, viral)')
    return ge


def main(argv: list[str] | None = None) -> int:
    for akis in (sys.stdout, sys.stderr):
        try:
            akis.reconfigure(encoding='utf-8', errors='replace')   # Windows konsolunda Türkçe karakter
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description='Yayın kesitleri + viral videolardan YouTube derlemesi (yüklemez).')
    ap.add_argument('--ayar', help='ayar dosyası (varsayılan otomasyon/derleme.json)')
    sp = ap.add_subparsers(dest='komut', required=True)
    t = sp.add_parser('topla', help='aday listesi (indirmez)')
    t.add_argument('--kaynaklar', type=_kaynaklar, default=('paket', 'izleyici', 'viral'))
    t.add_argument('--gun', type=float)
    t.add_argument('--cikti', help='aday JSON dosyası')
    u = sp.add_parser('uret', help='derleme üret')
    u.add_argument('--kaynaklar', type=_kaynaklar, default=('paket', 'izleyici', 'viral'))
    u.add_argument('--gun', type=float)
    u.add_argument('--sure-dk', type=float, help='hedef süre (dk)')
    u.add_argument('--yalniz-yayinci', action='store_true', help='viral kullanma (yalnız yayıncı kesiti + izleyici klibi)')
    u.add_argument('--viral-oran', type=int, help='yayıncı kesiti başına viral (ayarı ezer)')
    u.add_argument('--adaylar-dosyasi', help='topla çıktısı (toplamayı atlar)')
    u.add_argument('--kuru', action='store_true', help='yalnız plan (indirme/kodlama yok)')
    u.add_argument('--zorla', action='store_true', help='önceki parça dosyalarını yeniden üret')
    d = sp.add_parser('dogrula', help='bitmiş derlemeyi ölç, kare çıkar')
    d.add_argument('klasor')
    a = ap.parse_args(argv)
    try:
        ayar = ayar_yukle_d(a.ayar)
        dizin = calisma_dizini_d()
        if a.komut == 'topla':
            adaylar, rapor = aday_topla(ayar, dizin, a.kaynaklar, a.gun)
            if a.cikti:
                pathlib.Path(a.cikti).write_text(json.dumps({'adaylar': adaylar, 'rapor': rapor}, ensure_ascii=False, indent=1), encoding='utf-8')
            print(json.dumps({'aday_sayilari': rapor['aday_sayilari'], 'rapor': rapor}, ensure_ascii=False, indent=2))
        elif a.komut == 'uret':
            if a.viral_oran is not None:
                ayar['yayinci_basina_viral'] = a.viral_oran
            kaynaklar, turler = a.kaynaklar, ('yayinci', 'izleyici', 'viral')
            if a.yalniz_yayinci:
                kaynaklar, turler = tuple(k for k in kaynaklar if k != 'viral'), ('yayinci', 'izleyici')
            s = uret(ayar, dizin, kaynaklar, a.gun, a.sure_dk, turler, a.kuru,
                     pathlib.Path(a.adaylar_dosyasi) if a.adaylar_dosyasi else None, a.zorla)
            ozet = s if s.get('kuru') else {k: s[k] for k in ('ad', 'baslik', 'dosya', 'sure_sn', 'cozunurluk', 'sayilar',
                                                              'uyarilar', 'elenen_adaylar', 'olcum')}
            print(json.dumps(ozet, ensure_ascii=False, indent=2))
        else:
            s = dogrula(ayar, pathlib.Path(a.klasor))
            print(json.dumps(s, ensure_ascii=False, indent=2))
            return 0 if s['gecti'] else 3
    except DerlemeHatasi as e:
        print(f'HATA: {e}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
