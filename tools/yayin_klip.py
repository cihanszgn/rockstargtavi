"""Yayın klip hattı: biten yayının sohbet yoğunluğundan 9:16 dikey klip paketi üretir. Yayın YAPMAZ.

Komutlar: tara, analiz <vod>, kes <vod>, otomatik. Ayrıntı: otomasyon/KLIP-HATTI.md.
Model çağrısı yok; başlık ve açıklama şablonla üretilir. Büyük dosyalar depo dışına yazılır.
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
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
YAYINCI_DOSYASI = ROOT / 'otomasyon' / 'klip-yayincilar.json'

AYAR_VARSAYILAN = {
    'dilim_sn': 10,        # sohbet sayım dilimi
    'esik_k': 2.5,         # zirve eşiği: ortalama + esik_k * standart sapma
    'min_mesaj': 20,       # bir dilimde en az bu kadar mesaj (düşük hacimli yayında gürültüyü eler)
    'min_oran': 2.0,       # ve ortalamanın en az bu katı
    'onceden_sn': 20,      # klip zirveden bu kadar önce başlar
    'kuyruk_sn': 12,       # son zirve diliminden sonra klipte kalan süre
    'klip_min_sn': 30,
    'klip_azami_sn': 55,   # Shorts/Reels sınırı 60 sn; pay bırakılır
    'birlestir_sn': 30,    # bu kadar yakın zirveler tek klipte birleşir
    'azami_klip': 3,       # yayın başına en çok klip
    'bas_dislama_sn': 300, # yayın başı (selamlaşma patlaması)
    'son_dislama_sn': 180, # yayın sonu (veda / raid patlaması)
    'son_gun': 7,          # tara: bu kadar günden eski yayına bakma
}
SHORTS_AZAMI_SN = 60

# Dikey düzenin tek yeri: değerler 1080x1920 tuvale göre piksel.
DUZEN = {
    'genislik': 1080,
    'yukseklik': 1920,
    'fps': 30,
    'arka_blur': 8,          # küçültülmüş arka planda gblur sigma
    'arka_parlaklik': -0.12,
    'ust_ad': {'boyut': 76, 'y': 430},
    'ust_oyun': {'boyut': 46, 'y': 530},
    'alt_kaynak': {'boyut': 44, 'y': 1340},
    'alt_marka': {'boyut': 38, 'y': 1415},
    'marka': 'CTRL+A GAME  ·  ctrl-agame.com',
    'metin_azami_px': 980,
}

KICK_API = 'https://kick.com/api'
UA = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'}
KICK_PENCERE_SN = 5      # /messages?start_time= ucu 5 sn'lik pencere döndürür
KICK_SAYFA_LIMITI = 25   # ve pencere başına en çok 25 mesaj (fazlası kesilir)

DESTEK_YOK = {
    'twitch': 'listedeki yayıncıların Twitch hesabında kayıtlı yayın (VOD) yok (2026-11-17); sohbet indirici yazılmadı',
    'youtube': 'YouTube canlı sohbet tekrarı (yt-dlp live_chat) bu sürümde yazılmadı ve denenmedi',
}


class KlipHatasi(RuntimeError):
    pass


class Desteklenmiyor(KlipHatasi):
    pass


# ---------------------------------------------------------------- yollar ve durum

def calisma_dizini() -> pathlib.Path:
    """Büyük dosyalar ve durum depo dışında. YAYIN_KLIP_DIZIN ile değişir."""
    env = os.environ.get('YAYIN_KLIP_DIZIN')
    if env:
        return pathlib.Path(env)
    if os.name == 'nt':
        return pathlib.Path(r'C:\Cihan.Ai\.scratch\yayin-klip')
    return pathlib.Path.home() / '.local' / 'share' / 'yayin-klip'


def durum_oku(dizin: pathlib.Path) -> dict:
    yol = dizin / 'durum.json'
    if yol.exists():
        return json.loads(yol.read_text(encoding='utf-8'))
    return {'vod': {}}


def durum_yaz(dizin: pathlib.Path, durum: dict) -> None:
    dizin.mkdir(parents=True, exist_ok=True)
    gecici = dizin / 'durum.json.tmp'
    gecici.write_text(json.dumps(durum, ensure_ascii=False, indent=2), encoding='utf-8')
    gecici.replace(dizin / 'durum.json')


def durum_isaretle(dizin: pathlib.Path, vod_anahtar: str, **alanlar) -> None:
    d = durum_oku(dizin)
    kayit = d['vod'].setdefault(vod_anahtar, {})
    kayit.update(alanlar)
    kayit['guncellendi'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    durum_yaz(dizin, d)


def islendi_mi(durum: dict, vod_anahtar: str) -> bool:
    return durum.get('vod', {}).get(vod_anahtar, {}).get('durum') == 'islendi'


# ---------------------------------------------------------------- ayar

def ayar_yukle(yol: pathlib.Path | None = None) -> dict:
    yol = pathlib.Path(yol or os.environ.get('KLIP_YAYINCILAR') or YAYINCI_DOSYASI)
    ham = json.loads(yol.read_text(encoding='utf-8'))
    genel = dict(AYAR_VARSAYILAN)
    genel.update(ham.get('ayar') or {})
    yayincilar = []
    for y in ham.get('yayincilar') or []:
        for alan in ('ad', 'platform', 'kanal'):
            if not y.get(alan):
                raise KlipHatasi(f'yayıncı kaydında "{alan}" yok: {y}')
        e = dict(y)
        e['platform'] = e['platform'].lower()
        e['etkin'] = bool(e.get('etkin', True))
        e['ayar'] = {**genel, **(e.get('ayar') or {})}
        yayincilar.append(e)
    return {'ayar': genel, 'yayincilar': yayincilar}


def yayinci_bul(ayar: dict, platform: str, kanal: str) -> dict | None:
    for y in ayar['yayincilar']:
        if y['platform'] == platform and y['kanal'].lower() == kanal.lower():
            return y
    return None


# ---------------------------------------------------------------- yardımcılar

TR_KUCUK = str.maketrans({'I': 'ı', 'İ': 'i'})


def tr_kucuk(s: str) -> str:
    return s.translate(TR_KUCUK).lower()


def zaman_metni(sn: float) -> str:
    sn = int(sn)
    s, d, h = sn % 60, (sn // 60) % 60, sn // 3600
    return f'{h}:{d:02d}:{s:02d}' if h else f'{d}:{s:02d}'


def dosya_adi(s: str) -> str:
    tablo = str.maketrans({'ç': 'c', 'ğ': 'g', 'ı': 'i', 'ö': 'o', 'ş': 's', 'ü': 'u',
                           'Ç': 'c', 'Ğ': 'g', 'İ': 'i', 'I': 'i', 'Ö': 'o', 'Ş': 's', 'Ü': 'u'})
    s = s.translate(tablo).lower()
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-') or 'yayinci'


def iso_epoch(s: str) -> int:
    s = s.strip().replace(' ', 'T')
    if s.endswith('Z'):
        s = s[:-1] + '+00:00'
    d = datetime.fromisoformat(s)
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return int(d.timestamp())


def epoch_iso(t: int) -> str:
    return datetime.fromtimestamp(t, timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')


# ---------------------------------------------------------------- HTTP

_ISTEK_KILIDI = threading.Lock()
_SON_ISTEK = [0.0]


def _hiz_siniri() -> None:
    """Tüm iş parçacıkları için ortak asgari istek aralığı (Kick 429 verir). KLIP_ISTEK_ARALIK ile ayarlanır (sn)."""
    aralik = float(os.environ.get('KLIP_ISTEK_ARALIK', '0.4'))
    with _ISTEK_KILIDI:
        bekle = _SON_ISTEK[0] + aralik - time.monotonic()
        if bekle > 0:
            time.sleep(bekle)
        _SON_ISTEK[0] = time.monotonic()


def http_metin(url: str, deneme: int = 8, zaman_asimi: int = 30, bayt: int | None = None) -> str:
    son = None
    for i in range(deneme):
        bekle = min(2 ** i, 20)
        try:
            _hiz_siniri()
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=zaman_asimi) as r:
                veri = r.read(bayt) if bayt else r.read()
            return veri.decode('utf-8', 'replace')
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise Desteklenmiyor(f'sunucu {e.code} döndürdü (bot koruması veya giriş isteği): {url}')
            if e.code == 404:
                raise KlipHatasi(f'bulunamadı (404): {url}')
            if e.code == 429:
                try:
                    bekle = max(bekle, min(float(e.headers.get('Retry-After', 0)), 120))
                except (TypeError, ValueError):
                    pass
                bekle = max(bekle, 10 * (i + 1))
            son = e
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            son = e
        time.sleep(bekle)
    raise KlipHatasi(f'istek başarısız ({deneme} deneme): {url}: {son}')


def http_json(url: str) -> dict | list:
    return json.loads(http_metin(url))


# ---------------------------------------------------------------- Kick: yayın listesi ve bilgisi

def vod_normalle(girdi: dict, kanal: str, yayinci_ad: str) -> dict:
    """Kick yayın kaydını (v2 liste biçimi) hattın ortak VOD sözlüğüne çevirir."""
    video = girdi.get('video') or {}
    uuid = video.get('uuid')
    if not uuid:
        raise KlipHatasi('yayında video kimliği (uuid) yok')
    kat = (girdi.get('categories') or [{}])[0].get('name') or ''
    bas = iso_epoch(girdi['start_time'])
    return {
        'platform': 'kick',
        'vod_id': uuid,
        'anahtar': f'kick:{uuid}',
        'yayinci': yayinci_ad,
        'kanal': kanal,
        'kanal_id': girdi['channel_id'],
        'baslik': girdi.get('session_title') or '',
        'oyun': kat,
        'baslangic_epoch': bas,
        'sure_sn': int((girdi.get('duration') or 0) / 1000),
        'kaynak': girdi.get('source') or '',
        'canli': bool(girdi.get('is_live')),
        'vod_url': f'https://kick.com/{kanal}/videos/{uuid}',
        'kanal_url': f'https://kick.com/{kanal}',
        'tarih': datetime.fromtimestamp(bas, timezone.utc).strftime('%Y-%m-%d'),
    }


def kick_vodlar(kanal: str, yayinci_ad: str, http=http_json) -> list[dict]:
    liste = http(f'{KICK_API}/v2/channels/{kanal}/videos')
    sonuc = []
    for g in liste:
        try:
            sonuc.append(vod_normalle(g, kanal, yayinci_ad))
        except KlipHatasi:
            continue
    return sonuc


def kick_vod_bilgi(uuid: str, kanal_ipucu: str | None, ayar: dict, http=http_json) -> dict:
    d = http(f'{KICK_API}/v1/video/{uuid}')
    ls = d.get('livestream') or {}
    kanal = ((ls.get('channel') or {}).get('slug')) or kanal_ipucu
    if not kanal:
        raise KlipHatasi('VOD kanalı bulunamadı')
    giris = dict(ls)
    giris['video'] = {'uuid': d.get('uuid') or uuid}
    giris['source'] = d.get('source') or ls.get('source')
    y = yayinci_bul(ayar, 'kick', kanal)
    ad = y['ad'] if y else (((ls.get('channel') or {}).get('user') or {}).get('username') or kanal)
    return vod_normalle(giris, kanal, ad)


VOD_URL_RE = re.compile(r'kick\.com/([^/\s]+)/videos/([0-9a-fA-F-]{36})')
UUID_RE = re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')


def vod_coz(arguman: str) -> tuple[str, str | None]:
    """'kick:<uuid>', Kick VOD adresi veya çıplak uuid -> (uuid, kanal ipucu)."""
    a = arguman.strip()
    m = VOD_URL_RE.search(a)
    if m:
        return m.group(2).lower(), m.group(1)
    if a.lower().startswith('kick:'):
        a = a[5:]
    if UUID_RE.match(a):
        return a.lower(), None
    raise KlipHatasi(f'VOD tanınmadı (kick:<uuid>, uuid veya kick.com/<kanal>/videos/<uuid> ver): {arguman}')


# ---------------------------------------------------------------- Kick: sohbet kaydı

def kick_pencere(http, kanal_id: int, bas: int) -> list[tuple[str, int, str]]:
    """[bas, bas+5) penceresindeki tüm mesajlar. Pencere 25'e kesildiyse kaldığı yerden devam eder."""
    bitis = bas + KICK_PENCERE_SN
    gorulen: dict[str, tuple[str, int, str]] = {}
    ara = bas
    for _ in range(200):
        veri = http(f'{KICK_API}/v2/channels/{kanal_id}/messages?start_time={epoch_iso(ara)}')
        mesajlar = (veri.get('data') or {}).get('messages') or []
        son = ara
        for m in mesajlar:
            t = iso_epoch(m['created_at'])
            son = max(son, t)
            if bas <= t < bitis and m.get('type', 'message') in ('message', 'reply'):
                gorulen[m['id']] = (m['id'], t, m.get('content') or '')
        if len(mesajlar) < KICK_SAYFA_LIMITI or son >= bitis:
            break
        # Tam dolu sayfa: aynı saniyede 25+ mesaj varsa bir saniye atla (az sayılır, ama döngüye girmez).
        ara = son if son > ara else ara + 1
    return list(gorulen.values())


def kick_sohbet_indir(http, kanal_id: int, bas: int, sure_sn: int, part: pathlib.Path,
                      is_parcacigi: int = 4, ilerleme=None) -> list[tuple[int, str]]:
    """VOD süresince sohbeti indirir; yarım kalırsa part dosyasından devam eder."""
    pencereler = list(range(bas, bas + sure_sn + KICK_PENCERE_SN, KICK_PENCERE_SN))
    biten: set[int] = set()
    mesajlar: dict[str, tuple[int, str]] = {}
    if part.exists():
        for satir in part.read_text(encoding='utf-8').splitlines():
            try:
                k = json.loads(satir)
            except ValueError:
                continue
            biten.add(k['w'])
            for i, t, x in k['m']:
                mesajlar[i] = (t, x)
    kalan = [w for w in pencereler if w not in biten]
    part.parent.mkdir(parents=True, exist_ok=True)
    sayac = 0
    with part.open('a', encoding='utf-8') as f, ThreadPoolExecutor(max_workers=is_parcacigi) as havuz:
        for w, sonuc in zip(kalan, havuz.map(lambda w: kick_pencere(http, kanal_id, w), kalan)):
            f.write(json.dumps({'w': w, 'm': sonuc}, ensure_ascii=False) + '\n')
            for i, t, x in sonuc:
                mesajlar[i] = (t, x)
            sayac += 1
            if ilerleme and sayac % 200 == 0:
                ilerleme(sayac, len(kalan))
    return sorted(mesajlar.values())


def sohbet_al(vod: dict, dizin: pathlib.Path, http=http_json, ilerleme=None) -> list[tuple[int, str]]:
    """Sohbet önbelleği varsa onu, yoksa indirip önbelleğe yazar. [(epoch_sn, metin)]"""
    onbellek = dizin / 'sohbet' / f"{vod['platform']}-{vod['vod_id']}.json"
    if onbellek.exists():
        return [(t, x) for t, x in json.loads(onbellek.read_text(encoding='utf-8'))['mesajlar']]
    if vod['platform'] != 'kick':
        raise Desteklenmiyor(DESTEK_YOK.get(vod['platform'], 'platform tanınmıyor'))
    part = dizin / 'sohbet' / f"{vod['platform']}-{vod['vod_id']}.part.jsonl"
    mesajlar = kick_sohbet_indir(http, vod['kanal_id'], vod['t0_epoch'], vod['sure_sn'], part, ilerleme=ilerleme)
    onbellek.write_text(json.dumps({'vod': vod['anahtar'], 'mesajlar': mesajlar}, ensure_ascii=False), encoding='utf-8')
    part.unlink(missing_ok=True)
    return mesajlar


# ---------------------------------------------------------------- Kick: video akışı (HLS)

def hls_oynatma_listesi(master_url: str, http_text=http_metin) -> tuple[str, str]:
    """Ana listeden en yüksek bant genişlikli çeşidin adresini seçer. (çeşit adresi, master metni)"""
    master = http_text(master_url)
    taban = master_url.rsplit('/', 1)[0]
    en_iyi, en_bw = None, -1
    satirlar = master.splitlines()
    for i, s in enumerate(satirlar):
        if s.startswith('#EXT-X-STREAM-INF'):
            m = re.search(r'BANDWIDTH=(\d+)', s)
            bw = int(m.group(1)) if m else 0
            if i + 1 < len(satirlar) and not satirlar[i + 1].startswith('#') and bw > en_bw:
                en_iyi, en_bw = satirlar[i + 1].strip(), bw
    if not en_iyi:
        raise KlipHatasi('HLS ana listesinde video çeşidi yok')
    yol = en_iyi if en_iyi.startswith('http') else f'{taban}/{en_iyi}'
    return yol, master


def hls_t0(oynatma_metni: str) -> int | None:
    """İlk bölümün gerçek zamanı (#EXT-X-PROGRAM-DATE-TIME). Sohbet saatiyle video konumu arasındaki köprü."""
    m = re.search(r'#EXT-X-PROGRAM-DATE-TIME:(\S+)', oynatma_metni)
    return iso_epoch(m.group(1)) if m else None


def vod_t0_ekle(vod: dict, http_text=http_metin) -> dict:
    """vod['t0_epoch'] (video 0. sn'sinin gerçek saati) ve vod['hls'] (çeşit adresi) ekler."""
    vod['t0_epoch'] = vod['baslangic_epoch']
    vod['t0_kaynagi'] = 'start_time'
    vod['hls'] = vod.get('kaynak') or ''
    if vod['platform'] == 'kick' and vod.get('kaynak'):
        try:
            cesit, _ = hls_oynatma_listesi(vod['kaynak'], http_text)
            t0 = hls_t0(http_text(cesit, bayt=4096))
            vod['hls'] = cesit
            if t0:
                vod['t0_epoch'], vod['t0_kaynagi'] = t0, 'hls_program_date_time'
        except KlipHatasi:
            pass
    return vod


# ---------------------------------------------------------------- analiz

def dilim_say(zamanlar_sn: list[float], dilim_sn: int, toplam_sn: float) -> list[int]:
    """Video konumu (sn) listesinden dilim başına mesaj sayısı. Aralık dışı mesajlar atılır."""
    n = int(math.ceil(toplam_sn / dilim_sn))
    sayim = [0] * n
    for t in zamanlar_sn:
        if 0 <= t < toplam_sn:
            sayim[int(t // dilim_sn)] += 1
    return sayim


def istatistik(sayim: list[int], ayar: dict) -> dict:
    dilim = ayar['dilim_sn']
    lo = int(math.ceil(ayar['bas_dislama_sn'] / dilim))
    hi = int((len(sayim) * dilim - ayar['son_dislama_sn']) // dilim)
    parca = sayim[lo:hi]
    if len(parca) < 6:
        return {'lo': lo, 'hi': hi, 'ort': 0.0, 'std': 0.0, 'esik': float('inf')}
    ort = statistics.fmean(parca)
    std = statistics.pstdev(parca)
    esik = max(ort + ayar['esik_k'] * std, ayar['min_mesaj'], ayar['min_oran'] * ort)
    return {'lo': lo, 'hi': hi, 'ort': ort, 'std': std, 'esik': esik}


def zirveleri_bul(sayim: list[int], ayar: dict, toplam_sn: float) -> tuple[list[dict], dict]:
    """Eşiği aşan dilimleri kümeler, her küme için klip aralığı üretir; en iyi azami_klip tanesini döndürür."""
    dilim = ayar['dilim_sn']
    ist = istatistik(sayim, ayar)
    if ist['esik'] == float('inf'):
        return [], ist
    isaretli = [i for i in range(ist['lo'], ist['hi']) if sayim[i] >= ist['esik']]
    kumeler: list[list[int]] = []
    for i in isaretli:
        if kumeler and (i - kumeler[-1][-1]) * dilim <= ayar['birlestir_sn']:
            kumeler[-1].append(i)
        else:
            kumeler.append([i])
    adaylar = []
    for k in kumeler:
        tepe = max(k, key=lambda i: sayim[i])
        bas = k[0] * dilim - ayar['onceden_sn']
        bit = max((k[-1] + 1) * dilim + ayar['kuyruk_sn'], bas + ayar['klip_min_sn'])
        if bit - bas > ayar['klip_azami_sn']:
            bas = tepe * dilim - ayar['onceden_sn']
            bit = min((tepe + 1) * dilim + ayar['kuyruk_sn'], bas + ayar['klip_azami_sn'])
            bit = max(bit, bas + ayar['klip_min_sn'])
        if bas < 0:
            bit -= bas
            bas = 0
        if bit > toplam_sn:
            bas = max(0, bas - (bit - toplam_sn))
            bit = toplam_sn
        std = ist['std']
        adaylar.append({
            'zirve_sn': tepe * dilim,
            'mesaj': sayim[tepe],
            'puan': round(min((sayim[tepe] - ist['ort']) / std, 99.0), 2) if std > 0 else 99.0,
            'oran': round(sayim[tepe] / ist['ort'], 2) if ist['ort'] else 0.0,
            'zirve_dilimleri': [i * dilim for i in k],
            'klip_baslangic_sn': float(bas),
            'klip_bitis_sn': float(bit),
            'sure_sn': float(bit - bas),
        })
    secilen: list[dict] = []
    for a in sorted(adaylar, key=lambda a: (-a['puan'], a['zirve_sn'])):
        if len(secilen) >= ayar['azami_klip']:
            break
        if any(a['klip_baslangic_sn'] < s['klip_bitis_sn'] and s['klip_baslangic_sn'] < a['klip_bitis_sn'] for s in secilen):
            continue
        secilen.append(a)
    secilen.sort(key=lambda a: a['zirve_sn'])
    for n, a in enumerate(secilen, 1):
        a['no'] = n
        a['zirve_zaman'] = zaman_metni(a['zirve_sn'])
    return secilen, ist


DURAK = set('''bir bu şu ve ile de da mi mı mu mü ne ya ama çok daha gibi için kadar ben sen biz siz var yok
evet hayır tamam şey bak hadi olum lan abi abim reis kanka bence bana sana ona ben bende sende yani zaten
yine artık hala hâlâ sadece bile olan oldu olur ola mal'''.split())
EMOTE_RE = re.compile(r'\[emote:\d+:([^\]]+)\]')
KOMUT_RE = re.compile(r'(?:^|\s)![^\s]+')
URL_RE = re.compile(r'https?://\S+|@\S+')
KELIME_RE = re.compile(r'[a-zçğıöşü0-9]{3,}')


def sohbet_belirteci(metin: str) -> tuple[list[str], list[str]]:
    emojiler = EMOTE_RE.findall(metin)
    temiz = KOMUT_RE.sub(' ', URL_RE.sub(' ', EMOTE_RE.sub(' ', metin)))
    kelimeler = [k for k in KELIME_RE.findall(tr_kucuk(temiz)) if k not in DURAK and not k.isdigit()]
    return kelimeler, emojiler


def one_cikan(tepe_metinler: list[str], tum_metinler: list[str], n: int = 5) -> tuple[list[str], list[str]]:
    """Zirvede, yayının geri kalanına göre en çok öne çıkan kelimeler ve emojiler (lift)."""
    def say(metinler):
        k, e = Counter(), Counter()
        for m in metinler:
            kk, ee = sohbet_belirteci(m)
            k.update(kk)
            e.update(ee)
        return k, e
    pk, pe = say(tepe_metinler)
    gk, ge = say(tum_metinler)
    oran = len(tepe_metinler) / max(len(tum_metinler), 1)

    def sirala(p, g, en_az):
        puan = [(c / (g[w] * oran + 1.0), c, w) for w, c in p.items() if c >= en_az]
        puan.sort(key=lambda x: (-x[0], -x[1], x[2]))
        return [w for _, _, w in puan[:n]]
    return sirala(pk, gk, 3), sirala(pe, ge, 3)


def analiz_et(vod: dict, mesajlar: list[tuple[int, str]], ayar: dict) -> dict:
    t0 = vod['t0_epoch']
    toplam = vod['sure_sn']
    ham = [(t - t0, x) for t, x in mesajlar]
    sayim = dilim_say([t for t, _ in ham], ayar['dilim_sn'], toplam)
    klipler, ist = zirveleri_bul(sayim, ayar, toplam)
    tum = [x for t, x in ham if 0 <= t < toplam]
    for k in klipler:
        a = min(k['zirve_dilimleri'])
        b = max(k['zirve_dilimleri']) + ayar['dilim_sn']
        tepe = [x for t, x in ham if a <= t < b]
        k['kelimeler'], k['emojiler'] = one_cikan(tepe, tum)
        ornek = [x.strip() for x in tepe if 3 <= len(x.strip()) <= 80][:5]
        k['ornek_mesajlar'] = ornek
        k['zirve_mesaj_sayisi'] = len(tepe)
    return {
        'vod': {k: vod[k] for k in ('platform', 'vod_id', 'anahtar', 'yayinci', 'kanal', 'baslik', 'oyun',
                                      'sure_sn', 'vod_url', 'kanal_url', 'tarih', 't0_epoch', 't0_kaynagi')},
        'ayar': ayar,
        'istatistik': {'mesaj': len(tum), 'dilim': len(sayim), 'ortalama': round(ist['ort'], 2),
                       'std': round(ist['std'], 2),
                       'esik': None if ist['esik'] == float('inf') else round(ist['esik'], 2)},
        'dilim_sayimlari': sayim,
        'klipler': klipler,
    }


# ---------------------------------------------------------------- başlık ve açıklama (şablon)

BASLIK_SABLONLARI = (
    '{ad} yayınında chat patladı!{oyun}',
    '{ad} yayınında sohbetin en çılgın anı{oyun}',
    'Chat bir anda coştu: {ad} yayını{oyun}',
    '{ad} yayınında herkes aynı anda yazdı!{oyun}',
)


def baslik_uret(vod: dict, klip: dict) -> str:
    sec = int(hashlib.sha1(f"{vod['anahtar']}:{klip['no']}".encode()).hexdigest(), 16) % len(BASLIK_SABLONLARI)
    oyun = f" | {vod['oyun']}" if vod.get('oyun') else ''
    b = BASLIK_SABLONLARI[sec].format(ad=vod['yayinci'], oyun=oyun)
    return b if len(b) <= 95 else b[:94].rstrip() + '…'


def etiket(ad: str) -> str:
    return ''.join(w.capitalize() for w in re.split(r'[^0-9A-Za-zÇĞİÖŞÜçğıöşü]+', dosya_adi(ad).replace('-', ' ')) if w)


def zaman_damgali_baglanti(vod: dict, sn: float) -> tuple[str, bool]:
    """(adres, platformda doğrulandı mı). Kick'in belgelenmiş bir zaman parametresi yok: ?t= denenmedi."""
    if vod['platform'] == 'kick':
        return f"{vod['vod_url']}?t={int(sn)}", False
    return vod['vod_url'], False


def aciklama_uret(vod: dict, klip: dict) -> str:
    bas = klip['klip_baslangic_sn']
    konu = ''
    if klip.get('kelimeler') or klip.get('emojiler'):
        konu = ' Sohbette öne çıkanlar: ' + ', '.join((klip.get('kelimeler') or [])[:3] + (klip.get('emojiler') or [])[:2]) + '.'
    platform = vod['platform'].capitalize()
    return (
        f"{vod['yayinci']} canlı yayınından ({vod['tarih']}, {platform}) sohbetin en yoğunlaştığı an.{konu}\n\n"
        f"Yayıncı: {vod['yayinci']} — {vod['kanal_url']}\n"
        f"Kaynak yayın: {vod['vod_url']} (yayının {zaman_metni(bas)} noktası)\n"
        "Görüntü ve ses yayıncıya aittir; tam yayın için kanalına gidin.\n\n"
        "CTRL+A GAME · ctrl-agame.com\n"
        f"#Shorts #{platform} #{etiket(vod['yayinci'])} #CTRLAGAME"
    )


def paket_json(vod: dict, klip: dict, mp4: pathlib.Path, dogrulama: dict) -> dict:
    link, dogrulandi = zaman_damgali_baglanti(vod, klip['klip_baslangic_sn'])
    return {
        'yayinci': vod['yayinci'],
        'platform': vod['platform'],
        'kanal': vod['kanal'],
        'kanal_url': vod['kanal_url'],
        'vod_url': vod['vod_url'],
        'vod_zaman_damgali_url': link,
        'vod_zaman_damgali_url_dogrulandi': dogrulandi,
        'yayin_tarihi': vod['tarih'],
        'yayin_basligi': vod['baslik'],
        'oyun': vod['oyun'],
        'zirve_sn': klip['zirve_sn'],
        'zirve_zaman': klip['zirve_zaman'],
        'zirve_puani': klip['puan'],
        'zirve_mesaj_sayisi': klip.get('zirve_mesaj_sayisi'),
        'klip_baslangic_sn': klip['klip_baslangic_sn'],
        'klip_bitis_sn': klip['klip_bitis_sn'],
        'one_cikan_kelimeler': klip.get('kelimeler', []),
        'one_cikan_emojiler': klip.get('emojiler', []),
        'ornek_mesajlar': klip.get('ornek_mesajlar', []),
        'baslik': baslik_uret(vod, klip),
        'aciklama': aciklama_uret(vod, klip),
        'dosya': mp4.name,
        'video': dogrulama,
        'uretim': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'yayinlandi': False,
    }


# ---------------------------------------------------------------- ffmpeg

def _ffmpeg_yetenekli(yol: str) -> bool:
    try:
        r = subprocess.run([yol, '-hide_banner', '-filters'], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0 and ' drawtext ' in r.stdout and ' gblur ' in r.stdout


def ffmpeg_bul() -> str:
    """FFMPEG ortam değişkeni, sonra PATH'teki ffmpeg, sonra imageio-ffmpeg paketi. drawtext ve gblur şart."""
    adaylar = []
    if os.environ.get('FFMPEG'):
        adaylar.append(os.environ['FFMPEG'])
    yol = shutil.which('ffmpeg')
    if yol:
        adaylar.append(yol)
    try:
        import imageio_ffmpeg
        adaylar.append(imageio_ffmpeg.get_ffmpeg_exe())
    except Exception:
        pass
    for a in adaylar:
        if _ffmpeg_yetenekli(a):
            return a
    raise KlipHatasi('drawtext/gblur destekli ffmpeg yok: `py -m pip install --user imageio-ffmpeg` veya FFMPEG ortam değişkeni')


def font_bul() -> str:
    adaylar = [os.environ.get('KLIP_FONT', '')]
    if os.name == 'nt':
        w = pathlib.Path(os.environ.get('WINDIR', r'C:\Windows')) / 'Fonts'
        adaylar += [str(w / 'arialbd.ttf'), str(w / 'segoeuib.ttf'), str(w / 'verdanab.ttf')]
    adaylar += ['/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
                '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
                '/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf',
                '/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf']
    for a in adaylar:
        if a and pathlib.Path(a).is_file():
            return a
    raise KlipHatasi('kalın yazı tipi bulunamadı: KLIP_FONT=<ttf yolu> ver (Linux: apt install fonts-dejavu-core)')


def _fe(yol: str) -> str:
    """ffmpeg filtre seçeneği için yol kaçışı (Windows sürücü iki noktası)."""
    return yol.replace('\\', '/').replace(':', '\\:')


def metin_boyutu(metin: str, boyut: int, azami_px: int) -> int:
    return max(24, min(boyut, int(azami_px / (0.62 * max(len(metin), 1)))))


def filtre_yaz(font: str, metinler: dict[str, str], duzen: dict = DUZEN) -> str:
    """filter_complex betiği. Metinler çalışma klasöründe t_<ad>.txt dosyalarından okunur (kaçış derdi yok)."""
    w, h = duzen['genislik'], duzen['yukseklik']
    kucuk_w = w // 4
    kucuk_h = h // 4
    satirlar = [
        f"[0:v:0]fps={duzen['fps']},split=2[a][b]",
        f"[a]scale=-2:{kucuk_h},crop={kucuk_w}:{kucuk_h},gblur=sigma={duzen['arka_blur']},"
        f"scale={w}:{h},eq=brightness={duzen['arka_parlaklik']}:saturation=0.9[bg]",
        f"[b]scale={w}:-2:flags=lanczos[fg]",
        "[bg][fg]overlay=(W-w)/2:(H-h)/2[v0]",
    ]
    cizim = []
    for ad, bolum, renk in (('ad', 'ust_ad', 'white'), ('oyun', 'ust_oyun', '0xFFD54A'),
                            ('kaynak', 'alt_kaynak', 'white'), ('marka', 'alt_marka', '0xCCCCCC')):
        b = duzen[bolum]
        boyut = metin_boyutu(metinler[ad], b['boyut'], duzen['metin_azami_px'])
        cizim.append(
            f"drawtext=fontfile='{_fe(font)}':textfile='t_{ad}.txt':fontsize={boyut}:fontcolor={renk}:"
            f"borderw=4:bordercolor=black@0.85:x=(w-text_w)/2:y={b['y']}"
        )
    satirlar.append('[v0]' + ','.join(cizim) + ',setsar=1,format=yuv420p[v]')
    return ';\n'.join(satirlar) + '\n'


def klip_metinleri(vod: dict) -> dict[str, str]:
    return {
        'ad': vod['yayinci'],
        'oyun': vod.get('oyun') or '',
        'kaynak': f"Kaynak: kick.com/{vod['kanal']}" if vod['platform'] == 'kick' else f"Kaynak: {vod['kanal_url']}",
        'marka': DUZEN['marka'],
    }


def ffmpeg_komutu(ff: str, kaynak: str, bas: float, sure: float, cikti: str, filtre: str) -> list[str]:
    # -filter_complex_script ffmpeg 7+'da kalktı, -/filter_complex 6'da yok: süzgeç (~1 KB) argüman olarak verilir.
    return [ff, '-hide_banner', '-loglevel', 'error', '-y',
            '-ss', f'{bas:.3f}', '-i', kaynak, '-t', f'{sure:.3f}',
            '-filter_complex', filtre.replace('\n', ''),
            '-map', '[v]', '-map', '0:a:0',
            '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '21', '-pix_fmt', 'yuv420p',
            '-r', str(DUZEN['fps']), '-c:a', 'aac', '-b:a', '160k', '-ar', '48000', '-ac', '2',
            '-movflags', '+faststart', cikti]


def klip_dogrula(ff: str, mp4: pathlib.Path) -> dict:
    """ffprobe yerine ffmpeg -i çıktısı: boyut, süre, ses. Sınır dışıysa KlipHatasi."""
    r = subprocess.run([ff, '-hide_banner', '-i', str(mp4)], capture_output=True, text=True, encoding='utf-8', errors='replace')
    log = r.stderr
    d = re.search(r'Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)', log)
    v = re.search(r'Video:.*?,\s*(\d{3,5})x(\d{3,5})', log)
    if not (d and v):
        raise KlipHatasi(f'klip okunamadı: {mp4}')
    sure = int(d.group(1)) * 3600 + int(d.group(2)) * 60 + float(d.group(3))
    bilgi = {'genislik': int(v.group(1)), 'yukseklik': int(v.group(2)), 'sure_sn': round(sure, 2),
             'ses': 'Audio:' in log, 'boyut_mb': round(mp4.stat().st_size / 1e6, 2),
             'kodek': 'h264' if 'Video: h264' in log else 'diger'}
    if (bilgi['genislik'], bilgi['yukseklik']) != (DUZEN['genislik'], DUZEN['yukseklik']):
        raise KlipHatasi(f"klip boyutu {bilgi['genislik']}x{bilgi['yukseklik']}, 1080x1920 olmalı")
    if not bilgi['ses']:
        raise KlipHatasi('kliple ses yok')
    if bilgi['sure_sn'] > SHORTS_AZAMI_SN:
        raise KlipHatasi(f"klip {bilgi['sure_sn']} sn, Shorts/Reels sınırı {SHORTS_AZAMI_SN} sn")
    return bilgi


def klip_kes(vod: dict, klip: dict, hedef: pathlib.Path, ff: str, font: str) -> dict:
    """Yalnız klip aralığını HLS'ten çeker ve 1080x1920 H.264+AAC olarak yazar."""
    kaynak = vod.get('hls') or vod['kaynak']
    sure = min(klip['klip_bitis_sn'], vod['sure_sn']) - klip['klip_baslangic_sn']
    hedef.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='klip-') as tmp:
        tmp_yol = pathlib.Path(tmp)
        metinler = klip_metinleri(vod)
        for ad, m in metinler.items():
            (tmp_yol / f't_{ad}.txt').write_text(m or ' ', encoding='utf-8')
        gecici = tmp_yol / 'cikti.mp4'
        r = subprocess.run(ffmpeg_komutu(ff, kaynak, klip['klip_baslangic_sn'], sure, gecici.name, filtre_yaz(font, metinler)),
                           cwd=tmp, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=1200)
        if r.returncode != 0 or not gecici.exists():
            raise KlipHatasi(f'ffmpeg başarısız ({r.returncode}): {r.stderr[-800:]}')
        shutil.move(str(gecici), str(hedef))
    return klip_dogrula(ff, hedef)


# ---------------------------------------------------------------- akış

def vod_hazirla(arguman: str, ayar: dict, http=http_json, http_text=http_metin) -> tuple[dict, dict]:
    uuid, ipucu = vod_coz(arguman)
    vod = kick_vod_bilgi(uuid, ipucu, ayar, http)
    if vod['canli']:
        raise KlipHatasi('yayın hâlâ sürüyor; bittikten sonra işlenir')
    y = yayinci_bul(ayar, 'kick', vod['kanal'])
    vod_t0_ekle(vod, http_text)
    return vod, (y['ayar'] if y else dict(ayar['ayar']))


def analiz_komutu(arguman: str, dizin: pathlib.Path, ayar: dict, gecersiz: dict | None = None,
                  yeniden: bool = False) -> tuple[dict, dict]:
    vod, vayar = vod_hazirla(arguman, ayar)
    vayar = {**vayar, **(gecersiz or {})}
    yol = dizin / 'analiz' / f"{vod['platform']}-{vod['vod_id']}.json"
    if yol.exists() and not yeniden:
        sonuc = json.loads(yol.read_text(encoding='utf-8'))
        if sonuc.get('ayar') == vayar:
            return vod, sonuc
    def ilerleme(a, b):
        print(f'  sohbet: {a}/{b} pencere', file=sys.stderr, flush=True)
    mesajlar = sohbet_al(vod, dizin, ilerleme=ilerleme)
    sonuc = analiz_et(vod, mesajlar, vayar)
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(json.dumps(sonuc, ensure_ascii=False, indent=1), encoding='utf-8')
    durum_isaretle(dizin, vod['anahtar'], durum='analiz', yayinci=vod['yayinci'], klip=len(sonuc['klipler']))
    return vod, sonuc


def kes_komutu(arguman: str, dizin: pathlib.Path, ayar: dict, gecersiz: dict | None = None,
               zorla: bool = False, yeniden: bool = False) -> list[pathlib.Path]:
    vod, sonuc = analiz_komutu(arguman, dizin, ayar, gecersiz, yeniden)
    ff, font = ffmpeg_bul(), font_bul()
    cikti_dizini = dizin / 'cikti' / f"{dosya_adi(vod['yayinci'])}-{vod['tarih'].replace('-', '')}-{vod['vod_id'][:8]}"
    uretilen = []
    for klip in sonuc['klipler']:
        mp4 = cikti_dizini / f"klip-{klip['no']:02d}.mp4"
        paket = mp4.with_suffix('.json')
        if mp4.exists() and paket.exists() and not zorla:
            uretilen.append(mp4)
            continue
        print(f"  klip {klip['no']}: {zaman_metni(klip['klip_baslangic_sn'])}–{zaman_metni(klip['klip_bitis_sn'])}", file=sys.stderr, flush=True)
        bilgi = klip_kes(vod, klip, mp4, ff, font)
        paket.write_text(json.dumps(paket_json(vod, klip, mp4, bilgi), ensure_ascii=False, indent=2), encoding='utf-8')
        uretilen.append(mp4)
    durum_isaretle(dizin, vod['anahtar'], durum='islendi', yayinci=vod['yayinci'], klip=len(uretilen),
                   cikti=str(cikti_dizini))
    return uretilen


def tara(ayar: dict, dizin: pathlib.Path, yayinci: str | None = None, hepsi: bool = False,
         http=http_json, simdi: float | None = None) -> dict:
    """Etkin yayıncıların son biten yayınları; işlenmişler atlanır. Desteklenmeyen platform ayrı raporlanır."""
    durum = durum_oku(dizin)
    simdi = simdi if simdi is not None else time.time()
    bulunan, atlanan, desteksiz, hatalar = [], [], [], []
    for y in ayar['yayincilar']:
        if not y['etkin'] or (yayinci and yayinci.lower() not in (y['ad'].lower(), y['kanal'].lower())):
            continue
        if y['platform'] != 'kick':
            desteksiz.append({'yayinci': y['ad'], 'platform': y['platform'],
                              'neden': DESTEK_YOK.get(y['platform'], 'platform tanınmıyor')})
            continue
        try:
            vodlar = kick_vodlar(y['kanal'], y['ad'], http)
        except KlipHatasi as e:
            hatalar.append({'yayinci': y['ad'], 'hata': str(e)})
            continue
        sinir = simdi - y['ayar']['son_gun'] * 86400
        for v in vodlar:
            if v['canli'] or v['baslangic_epoch'] < sinir:
                continue
            satir = {'yayinci': y['ad'], 'anahtar': v['anahtar'], 'tarih': v['tarih'], 'sure_sn': v['sure_sn'],
                     'oyun': v['oyun'], 'baslik': v['baslik'], 'vod_url': v['vod_url']}
            if islendi_mi(durum, v['anahtar']) and not hepsi:
                atlanan.append(v['anahtar'])
            else:
                bulunan.append(satir)
    return {'yeni': bulunan, 'atlanan_islenmis': atlanan, 'desteksiz': desteksiz, 'hata': hatalar}


def _gecersiz(a) -> dict:
    g = {}
    for alan in ('esik_k', 'min_mesaj', 'azami_klip', 'bas_dislama_sn', 'min_oran'):
        v = getattr(a, alan, None)
        if v is not None:
            g[alan] = v
    return g


def main(argv=None) -> int:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    p = argparse.ArgumentParser(description='Yayın klip hattı (yayın yapmaz).')
    p.add_argument('--ayar', help='yayıncı ayar dosyası (varsayılan otomasyon/klip-yayincilar.json)')
    p.add_argument('--dizin', help='çalışma dizini (YAYIN_KLIP_DIZIN)')
    s = p.add_subparsers(dest='komut', required=True)
    t = s.add_parser('tara', help='son biten yayınları listele')
    t.add_argument('--yayinci')
    t.add_argument('--hepsi', action='store_true', help='işlenmişleri de göster')
    for ad, yardim in (('analiz', 'sohbeti indir, zirveleri bul'), ('kes', 'klipleri kes ve paketle')):
        k = s.add_parser(ad, help=yardim)
        k.add_argument('vod', help='kick:<uuid>, uuid veya kick.com/<kanal>/videos/<uuid>')
        k.add_argument('--esik-k', dest='esik_k', type=float)
        k.add_argument('--min-mesaj', dest='min_mesaj', type=int)
        k.add_argument('--min-oran', dest='min_oran', type=float)
        k.add_argument('--azami-klip', dest='azami_klip', type=int)
        k.add_argument('--bas-dislama-sn', dest='bas_dislama_sn', type=int)
        k.add_argument('--yeniden', action='store_true', help='analizi önbellekten alma')
        if ad == 'kes':
            k.add_argument('--zorla', action='store_true', help='var olan klibi yeniden üret')
    o = s.add_parser('otomatik', help='tara + analiz + kes (yeni yayınların hepsi)')
    o.add_argument('--yayinci')
    o.add_argument('--en-cok', dest='en_cok', type=int, default=3, help='bu çalıştırmada en çok kaç yayın')
    a = p.parse_args(argv)

    ayar = ayar_yukle(a.ayar)
    dizin = pathlib.Path(a.dizin) if a.dizin else calisma_dizini()
    try:
        if a.komut == 'tara':
            print(json.dumps(tara(ayar, dizin, a.yayinci, a.hepsi), ensure_ascii=False, indent=2))
        elif a.komut == 'analiz':
            vod, sonuc = analiz_komutu(a.vod, dizin, ayar, _gecersiz(a), a.yeniden)
            ozet = {k: v for k, v in sonuc.items() if k != 'dilim_sayimlari'}
            print(json.dumps(ozet, ensure_ascii=False, indent=2))
        elif a.komut == 'kes':
            for m in kes_komutu(a.vod, dizin, ayar, _gecersiz(a), a.zorla, a.yeniden):
                print(m)
        elif a.komut == 'otomatik':
            rapor = tara(ayar, dizin, a.yayinci)
            for k in rapor['desteksiz']:
                print(f"desteklenmiyor: {k['yayinci']} ({k['platform']}): {k['neden']}", file=sys.stderr)
            for v in rapor['yeni'][:a.en_cok]:
                print(f"{v['yayinci']} {v['tarih']} {v['baslik'][:50]}", file=sys.stderr)
                try:
                    for m in kes_komutu(v['anahtar'], dizin, ayar):
                        print(m)
                except KlipHatasi as e:
                    print(f"  atlandı: {e}", file=sys.stderr)
    except KlipHatasi as e:
        print(f'HATA: {e}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
