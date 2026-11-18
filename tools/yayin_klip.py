"""Yayın klip hattı: biten ya da SÜREN yayının sohbet sinyalinden 9:16 dikey klip paketi üretir. Yayın YAPMAZ.

Komutlar: tara, analiz <vod>, kes <vod>, otomatik, canli (yayın sürerken). Ayrıntı: otomasyon/KLIP-HATTI.md.
İsteğe bağlı konuşma katmanı içerik yargısı ve başlık üretir. Büyük dosyalar depo dışına yazılır.
"""
from __future__ import annotations

import argparse
import contextlib
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
import unicodedata
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import klip_kamera
import klip_konusma
import klip_oyun
import klip_youtube

ROOT = pathlib.Path(__file__).resolve().parents[1]
YAYINCI_DOSYASI = ROOT / 'otomasyon' / 'klip-yayincilar.json'

# Emote sınıfları: emote adında (küçük harf, 'collectibles' önekiyle) geçen parçalar. Sınıf sırası: gülme > şaşkınlık > gürültü.
# Gerçek Kick adları Kemalcan Parlak 15.11.2026 sohbetinden çıkarıldı (KLIP-HATTI.md "Emote sınıfları"); asıl liste ayar dosyasındadır.
EMOTE_GULME = ['kek', 'lul', 'icant', 'pepelaugh', 'lmao', 'emojilol', 'haha', 'hehe', 'giggle', 'rofl']
EMOTE_SASKIN = ['pog', 'coggers', 'noway', 'oooo', 'aaaa', 'sheesh', 'ayooo', 'caught', 'astonished', 'omg', 'monkaomega']
EMOTE_GURULTU = ['dance', 'dans', 'clap', 'jam', 'vibe', 'disco', 'dj', 'edmusic', 'bobble', 'twerk', 'headbang',
                 'boogie', 'shake', 'hopp', 'gachigasm']
OY_KELIMELERI = ['evet', 'hayır', 'hayir', 'e', 'h', 'yes', 'no', 'katıl', 'katil', 'katılıyorum', 'katiliyorum',
                 'katıldım', 'katildim', 'çekiliş', 'cekilis', 'giveaway']
GULME_KELIMELERI = ['lol', 'lmao', 'lmfao', 'rofl', 'kahkaha', 'gülmekten', 'güldüm', 'yırtıldım']
GULME_ISTISNA = ['kafkas']   # klavye-yığını biçimine uyan gerçek sözcükler (asla kahkaha sayılmaz)

AYAR_VARSAYILAN = {
    **klip_konusma.AYAR,
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
    # zayıf zirve elemesi (yalnız emote / tek karakter tekrarı patlamaları)
    'min_farkli_kullanici': 25,  # zirvede en az bu kadar farklı kişi yazmış olmalı
    'min_emote_disi_oran': 0.25,    # zirvedeki mesajların en az bu oranı emote dışında bir şey içermeli (gülme/şaşkınlık emote'u yazı sayılır)
    # sohbet sinyalleri (yontem='sinyal'): kahkaha, ortak konu, yoğunluk bileşenleri; oy/komut seli elenir
    'yontem': 'sinyal',          # 'sinyal' (yeni) | 'yogunluk' (eski: yalnız mesaj sayısı)
    'klip_baslangic': 'dalga',   # 'dalga': klip, kahkaha/konu dalgasının başladığı dilimden onceden_sn önce başlar; 'tepe': en yoğun dilimden
    'dalga_geri_oran': 0.4,      # önceki dilimde sinyal eşiğin bu oranını aşıyorsa dalga oradan başlamış sayılır
    'dalga_geri_azami_dilim': 3, # dalga başlangıcı en çok bu kadar dilim geriye uzatılır
    'gulme_min_kisi': 6,         # bir dilimde en az bu kadar farklı kişi gülmüş olmalı
    'gulme_esik_k': 2.0,         # ve yayının dilim başına ortalama gülen kişi sayısı + gulme_esik_k * std'yi aşmalı
    'gulme_min_oran': 0.15,      # gülen mesajlar, sinyalli mesajların en az bu oranı
    'gulme_tam_kisi': 15,        # kahkaha bileşeni: bu kadar gülen kişi = tam puan
    'gulme_tam_oran': 0.30,      # ve gülen mesaj oranı bu değerde tam puan
    'saskin_agirlik': 0.5,       # şaşkınlık emote'u yazan (gülmeyen) kişi kahkaha sayısına bu ağırlıkla katılır
    'konu_min_kisi': 6,          # ortak konu: aynı kelimeyi bir dilimde en az bu kadar FARKLI kişi yazmış olmalı
    'konu_min_lift': 10.0,       # ve kelimenin dilimdeki payı, yayının geri kalanındaki payının en az bu katı
    'konu_tam_kisi': 12,         # konu bileşeni: bu kadar farklı kişi = tam puan
    'yayilma_min_kisi': 6,       # aynı uzun metni (kopyala-yapıştır) bu kadar kişi yazdıysa yayılma sayılır
    'yayilma_min_uzunluk': 12,
    'yayilma_min_kelime': 3,
    'yayilma_konu_agirlik': 0.5, # yayılma kahkaha sayılmaz; konu puanına bu ağırlıkla sınırlı katkı verir
    'max_gurultu_oran': 0.5,     # dilimde oy/komut/dans-emote mesajları bu orana ulaşırsa zirve elenir
    'min_sinyal_mesaj': 10,      # gürültü (oy, komut) çıkarıldıktan sonra dilimde en az bu kadar mesaj
    'agirlik_gulme': 0.5,        # toplam puan ağırlıkları (normalize edilir)
    'agirlik_konu': 0.3,
    'agirlik_yogunluk': 0.2,
    'yogunluk_tam_z': 6.0,       # yoğunluk bileşeni: bu kadar std üstü = tam puan
    'gulme_emojileri': ['😂', '🤣', '😹', '😆'],
    'gulme_kelimeleri': GULME_KELIMELERI,
    'gulme_istisna': GULME_ISTISNA,
    'emote_gulme': EMOTE_GULME,
    'emote_saskin': EMOTE_SASKIN,
    'emote_gurultu': EMOTE_GURULTU,
    'oy_kelimeleri': OY_KELIMELERI,
    # canlı mod (`canli` komutu: yayın sürerken)
    'canli_min_sure_sn': 1200,   # yayının en az bu kadarı (sohbet + kayıt) geçmeden canlı klip kesilmez (istatistik oturmaz)
    'canli_azami_klip': 6,       # yayın başına canlı kesilecek en çok klip (sonradan `tara` kendi azami_klip'ini ayrıca keser)
    'canli_bekle_sn': 20,        # dalga bittikten (kümeleme penceresi dahil) ve klip bitişinden sonra bu kadar süre beklenir
    'canli_min_puan': 0.0,       # bu puanın altındaki canlı aday kesilmez
    'canli_sohbet_butce_sn': 240,  # tek turda bir yayıncının sohbetini indirmeye en çok bu kadar süre
    'canli_sohbet_marj_sn': 20,  # sohbetin "şimdi"den bu kadar gerisine kadarı tamam sayılır
    # görüntü düzeni
    'duzen': 'kamera',     # 'kamera': yayıncı kamerası bulunup AYRI panelde gösterilir (bulunamazsa 'kadraj'a düşer);
                           # 'kadraj': yayın ortadan kırpılıp büyütülür; 'serit': eski tam genişlik şerit
    'kadraj_oran': 1.2,    # kırpılan bölgenin genişlik/yükseklik oranı (1.0 = kare, 1.33 = 4:3, 1.78 = kırpma yok)
    **klip_kamera.VARSAYILAN,   # kamera_* eşikleri (klip_kamera.py'de açıklamalı)
    # oyun süzgeci
    'oyunlar': [],         # boş = bütün yayınlar; doluysa yalnız kategorisi/başlığı bu adlardan birine uyanlar
    'oyun_baslikta_ara': True,  # kategori uymasa da yayın başlığında geçen oyun adı kabul edilir
}
# Kısa olay açıklaması ayarları (konuşma yargısındaki kisa_aciklama; dikey klipte üst bölgeye büyük yazılır):
#   klip_aciklama_yazi      true (varsayılan) | false  -> false ya da --aciklamasiz: yazısız eski görünüm
#   aciklama_yasak_kelimeler  listeyi genişletir (klip_konusma.ACIKLAMA_YASAK_VARSAYILAN'a eklenir)
#   klip_aciklama_stil      A | B | C (varsayılan ACIKLAMA_STIL_VARSAYILAN): A dolu sarı etiket, B koyu etiket + sarı ad,
#                           C zeminsiz kalın kontur. Ayrıntı: otomasyon/KLIP-HATTI.md "Açıklama görünümü".
# Bunlar AYAR_VARSAYILAN'a GİRMEZ ve analiz önbelleği karşılaştırmasında yok sayılır: yalnız görünümü etkiler,
# yoksa her ayar değişikliği (pahalı) sohbet/yargı analizini geçersiz kılardı.
# Kesim aşaması ayarları (düzen, kadraj oranı, kamera eşikleri) da burada: yalnız KESİMİ etkiler, analiz önbelleğini bozmaz.
GORSEL_AYAR = ('klip_aciklama_yazi', 'aciklama_yasak_kelimeler', 'klip_aciklama_stil', 'duzen', 'kadraj_oran',
               'marka_yazi', 'klip_paylasim_imza', 'klip_ek_etiketler', *klip_kamera.VARSAYILAN)
# Marka (klip hesabı ayrı kanal): videonun altındaki marka satırı, paylaşım açıklamasındaki imza ve ek etiketler AYARDAN gelir
# (otomasyon/klip-yayincilar.json -> ayar.marka_yazi / klip_paylasim_imza / klip_ek_etiketler). Ayar YOKSA eski görünüm.
#   marka_yazi: videoya yazılan marka satırı; boş metin = marka satırı yok.  Pakete özel: `yeniden-uret --marka "..." | --markasiz`.
#   klip_paylasim_imza: paket açıklamasındaki imza satırı (boş = satır yok).  klip_ek_etiketler: açıklama sonu etiketleri (boş = yok).
MARKA_YAZI_VARSAYILAN = 'CTRL+A GAME  ·  ctrl-agame.com'
PAYLASIM_IMZA_VARSAYILAN = 'CTRL+A GAME · ctrl-agame.com'
EK_ETIKET_VARSAYILAN = ('#CTRLAGAME',)
MARKA_AZAMI = 40
ACIKLAMA_STILLERI = ('A', 'B', 'C')
ACIKLAMA_STIL_VARSAYILAN = 'A'
ACIKLAMA_TASARIM_SURUMU = 2   # düzen imzasına girer: tasarım değişince açıklamalı klipler 'güncel değil' olur
ACIKLAMA_FONT_DOSYASI = ROOT / 'otomasyon' / 'fontlar' / 'Anton-Regular.ttf'   # SIL OFL 1.1, lisans yanında (Anton-OFL.txt)
MARKA_SARI = (255, 213, 74)      # derleme giriş kartıyla aynı: 0xFFD54A
MARKA_LACIVERT = (11, 13, 23)    # derleme kart zemini: 0x0B0D17
SHORTS_AZAMI_SN = 60

# Dikey düzenin tek yeri: değerler 1080x1920 tuvale göre piksel.
DUZEN = {
    'genislik': 1080,
    'yukseklik': 1920,
    'fps': 30,
    'arka_blur': 8,          # küçültülmüş arka planda gblur sigma
    'arka_parlaklik': -0.12,
    'gorsel_merkez_y': 880,  # kadraj düzeninde görüntünün orta çizgisi (Shorts/Reels alt arayüzüne pay için biraz yukarıda)
    'ust_ad': {'boyut': 76, 'y_serit': 430},
    'ust_oyun': {'boyut': 46, 'y_serit': 530},
    'alt_kaynak': {'boyut': 44, 'y_serit': 1340},
    'alt_marka': {'boyut': 38, 'y_serit': 1415},
    'marka': 'CTRL+A GAME  ·  ctrl-agame.com',
    'metin_azami_px': 980,
    # 'kamera' düzeni: üstte içerik (oyun) paneli, altında yayıncı kamerası paneli; ikisi blok olarak 'kadraj'ın
    # görüntü kutusunun yerine geçer. Blok üstü (etiket altı) 430, alt kenarı 1450: alttaki yazı bloğu (~190 px)
    # 1670'te biter, son 250 px (platform arayüzü) boş kalır.
    'kamera': {'ust': 430, 'icerik_h': 590, 'bosluk': 10, 'kamera_h': 420},
    # Açıklama yazısı (yalnız açıklama varsa): görüntü karesinin HEMEN ÜSTÜNDE etiket (video_boslugu px aralıkla);
    # en üst 'ust_sinir' px boş kalır (Shorts/Reels üst çubuğu). Yayıncı adı + oyun, kaynak ve marka satırları
    # görüntünün ALTINA iner. Hepsi tek PNG katmanı olarak çizilir (aciklama_katmani), ffmpeg yalnız bindirir.
    'aciklama': {'boyut': 78, 'tek_satir_en_az': 64, 'en_az': 54, 'satir_arasi': 8, 'pad_x': 30, 'pad_y': 10,
                 'yaricap': 22, 'video_boslugu': 40, 'ust_sinir': 150, 'golge_pay': 16,
                 'ad_boyut': 44, 'kaynak_boyut': 34, 'marka_boyut': 30, 'alt_bosluk': 28, 'alt_satir_arasi': 6},
}
KAYNAK_ORAN = 16 / 9       # Kick yayını 16:9; kadraj oranı bundan büyük olamaz (kırpılacak şey kalmaz)
KADRAJ_EN_AZ = 1.0         # kareden dik kırpma yok: yazı bloğuna yer kalsın
METIN_SATIR_KATSAYI = 1.25 # yazı kutusu yüksekliği ≈ boyut × bu (kenar çizgisi dahil)

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


def oyun_belirtecleri(s: str) -> list[str]:
    """Oyun adını büyük-küçük harf, Türkçe karakter ve noktalamadan bağımsız kelime listesine çevirir."""
    d = unicodedata.normalize('NFKD', tr_kucuk(s))
    d = ''.join(c for c in d if not unicodedata.combining(c)).replace('ı', 'i')
    return re.findall(r'[a-z0-9]+', d)


def _dizi_icerir(buyuk: list[str], kucuk: list[str]) -> bool:
    n = len(kucuk)
    return n > 0 and any(buyuk[i:i + n] == kucuk for i in range(len(buyuk) - n + 1))


def oyun_suzgeci(vod: dict, ayar: dict) -> tuple[bool, str | None]:
    """(uygun mu, eşleşen oyun adı). `oyunlar` boşsa süzgeç kapalıdır: her yayın uygundur.
    Eşleşme kelime dizisi olarak yapılır: 'GTA V', 'GTA VI' kategorisine uymaz; 'GTA 6' ile 'GTA VI' ayrı yazılır."""
    liste = [str(o) for o in (ayar.get('oyunlar') or []) if oyun_belirtecleri(str(o))]
    if not liste:
        return True, None
    alanlar = [oyun_belirtecleri(k) for k in (vod.get('kategoriler') or [vod.get('oyun') or ''])]
    if ayar.get('oyun_baslikta_ara', True):
        alanlar.append(oyun_belirtecleri(vod.get('baslik') or ''))
    for ad in liste:
        t = oyun_belirtecleri(ad)
        if any(_dizi_icerir(a, t) for a in alanlar):
            return True, ad
    return False, None


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
    kategoriler = [c.get('name') for c in (girdi.get('categories') or []) if c.get('name')]
    kat = kategoriler[0] if kategoriler else ''
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
        'kategoriler': kategoriler,
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

def kick_pencere(http, kanal_id: int, bas: int) -> list[tuple[str, int, str, int | str]]:
    """[bas, bas+5) penceresindeki tüm mesajlar: (id, epoch, metin, gönderen kimliği).
    Pencere 25'e kesildiyse kaldığı yerden devam eder."""
    bitis = bas + KICK_PENCERE_SN
    gorulen: dict[str, tuple[str, int, str, int | str]] = {}
    ara = bas
    for _ in range(200):
        veri = http(f'{KICK_API}/v2/channels/{kanal_id}/messages?start_time={epoch_iso(ara)}')
        mesajlar = (veri.get('data') or {}).get('messages') or []
        son = ara
        for m in mesajlar:
            t = iso_epoch(m['created_at'])
            son = max(son, t)
            if bas <= t < bitis and m.get('type', 'message') in ('message', 'reply'):
                gonderen = m.get('user_id') or (m.get('sender') or {}).get('id') or ''
                gorulen[m['id']] = (m['id'], t, m.get('content') or '', gonderen)
        if len(mesajlar) < KICK_SAYFA_LIMITI or son >= bitis:
            break
        # Tam dolu sayfa: aynı saniyede 25+ mesaj varsa bir saniye atla (az sayılır, ama döngüye girmez).
        ara = son if son > ara else ara + 1
    return list(gorulen.values())


def _part_oku(part: pathlib.Path) -> tuple[set[int], dict[str, tuple[int, str, int | str]]]:
    """Kısmi sohbet dosyası: (bitmiş pencereler, mesajlar). Bozuk satır atlanır; eski satırlarda gönderen yok."""
    biten: set[int] = set()
    mesajlar: dict[str, tuple[int, str, int | str]] = {}
    if part.exists():
        for satir in part.read_text(encoding='utf-8').splitlines():
            try:
                k = json.loads(satir)
            except ValueError:
                continue
            biten.add(k['w'])
            for i, t, x, *g in k['m']:
                mesajlar[i] = (t, x, g[0] if g else '')
    return biten, mesajlar


def kick_sohbet_indir(http, kanal_id: int, bas: int, sure_sn: int, part: pathlib.Path,
                      is_parcacigi: int = 4, ilerleme=None, butce_sn: float | None = None,
                      saat=time.monotonic) -> list[tuple[int, str, int | str]]:
    """VOD süresince sohbeti indirir; yarım kalırsa part dosyasından devam eder. [(epoch, metin, gönderen)]
    butce_sn verilirse pencereler sırayla küçük gruplar halinde indirilir ve süre dolunca durulur
    (canlı yayında uzun geriden gelen sohbet birkaç turda yetişir; biten pencereler hep baştan ardışıktır)."""
    pencereler = list(range(bas, bas + sure_sn + KICK_PENCERE_SN, KICK_PENCERE_SN))
    biten, mesajlar = _part_oku(part)
    kalan = [w for w in pencereler if w not in biten]
    part.parent.mkdir(parents=True, exist_ok=True)
    sayac = 0
    bitis = None if butce_sn is None else saat() + butce_sn
    grup = len(kalan) if bitis is None else max(is_parcacigi * 4, 1)
    with part.open('a', encoding='utf-8') as f, ThreadPoolExecutor(max_workers=is_parcacigi) as havuz:
        for g0 in range(0, len(kalan), max(grup, 1)):
            if bitis is not None and saat() >= bitis:
                break
            parca = kalan[g0:g0 + grup]
            for w, sonuc in zip(parca, havuz.map(lambda w: kick_pencere(http, kanal_id, w), parca)):
                f.write(json.dumps({'w': w, 'm': sonuc}, ensure_ascii=False) + '\n')
                for i, t, x, g in sonuc:
                    mesajlar[i] = (t, x, g)
                sayac += 1
                if ilerleme and sayac % 200 == 0:
                    ilerleme(sayac, len(kalan))
            f.flush()
    return sorted(mesajlar.values(), key=lambda m: (m[0], m[1]))


SOHBET_SURUMU = 2  # 2: her mesajda gönderen kimliği var (farklı kullanıcı sayısı için)


def sohbet_al(vod: dict, dizin: pathlib.Path, http=http_json, ilerleme=None) -> list[tuple[int, str, int | str]]:
    """Sohbet önbelleği varsa onu, yoksa indirip önbelleğe yazar. [(epoch_sn, metin, gönderen)].
    Gönderensiz eski (sürüm 1) önbellek geçersizdir: yeniden indirilir."""
    onbellek = dizin / 'sohbet' / f"{vod['platform']}-{vod['vod_id']}.json"
    if onbellek.exists():
        eski = json.loads(onbellek.read_text(encoding='utf-8'))
        if eski.get('surum') == SOHBET_SURUMU:
            return [(t, x, g) for t, x, g in eski['mesajlar']]
    if vod['platform'] != 'kick':
        raise Desteklenmiyor(DESTEK_YOK.get(vod['platform'], 'platform tanınmıyor'))
    part = dizin / 'sohbet' / f"{vod['platform']}-{vod['vod_id']}.part.jsonl"
    mesajlar = kick_sohbet_indir(http, vod['kanal_id'], vod['t0_epoch'], vod['sure_sn'], part, ilerleme=ilerleme)
    onbellek.write_text(json.dumps({'vod': vod['anahtar'], 'surum': SOHBET_SURUMU, 'mesajlar': mesajlar},
                                   ensure_ascii=False), encoding='utf-8')
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


def hls_liste_ozeti(metin: str) -> dict:
    """Süren (büyüyen) çeşit listesinin özeti: video süresi, ilk/son bölümün gerçek saati ve saat kayması.
    sure_sn = bölüm sürelerinin toplamı (video konumu); kayma_sn = bölümlerin PROGRAM-DATE-TIME'ı ile
    birikmiş video süresi arasındaki en büyük fark (sohbet saatiyle video konumu arasındaki hata payı)."""
    toplam, ilk, son_epoch, kayma, bolum = 0.0, None, None, 0.0, 0
    bekleyen = None
    for s in metin.splitlines():
        s = s.strip()
        if s.startswith('#EXT-X-PROGRAM-DATE-TIME:'):
            bekleyen = iso_epoch(s.split(':', 1)[1])
        elif s.startswith('#EXTINF:'):
            try:
                sure = float(s[8:].split(',', 1)[0])
            except ValueError:
                continue
            if bekleyen is not None:
                if ilk is None:
                    ilk = bekleyen
                kayma = max(kayma, abs((bekleyen - ilk) - toplam))
                son_epoch = bekleyen + sure
                bekleyen = None
            toplam += sure
            bolum += 1
    return {'sure_sn': toplam, 'bolum': bolum, 't0_epoch': ilk, 'son_epoch': son_epoch, 'kayma_sn': round(kayma, 2)}


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


def zirveleri_bul(sayim: list[int], ayar: dict, toplam_sn: float, kalite=None) -> tuple[list[dict], dict]:
    """Eşiği aşan dilimleri kümeler, her küme için klip aralığı üretir; en iyi azami_klip tanesini döndürür.
    kalite(bas_sn, bit_sn) -> zirve_kalitesi sözlüğü verilirse zayıf zirveler (az kişi / yalnız emote) seçime
    girmeden elenir ve ist['elenen']'e nedenleriyle yazılır; elenenin yerini sıradaki aday alır."""
    dilim = ayar['dilim_sn']
    ist = istatistik(sayim, ayar)
    ist['elenen'] = []
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
        kalite_alani = {}
        if kalite:
            kalite_alani = kalite(k[0] * dilim, (k[-1] + 1) * dilim)
            neden = zayiflik_nedenleri(kalite_alani, ayar)
            if neden:
                ist['elenen'].append({'zirve_sn': tepe * dilim, 'zirve_zaman': zaman_metni(tepe * dilim),
                                      'mesaj': sayim[tepe], 'neden': neden, **kalite_alani})
                continue
        adaylar.append({
            **kalite_alani,
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


def emote_disi_mi(metin: str) -> bool:
    """[emote:..] belirteçleri atıldıktan sonra boşluk dışında bir şey kalıyorsa mesaj emote'tan ibarettir değildir.
    Ölçüt bilerek düz tutuldu: '1', '2', 'xd' gibi kısa oylar da yazıdır; oran yalnız emote seline bakar."""
    return bool(EMOTE_RE.sub('', metin).strip())


def zirve_kalitesi(mesajlar: list[tuple[str, object]], sf=None) -> dict:
    """[(metin, gönderen)] -> farklı kullanıcı sayısı ve emote olmayan mesaj oranı.
    Gönderen bilgisi yoksa (eski önbellek) farkli_kullanici None olur ve o ölçüt uygulanmaz.
    sf (Siniflayici) verilirse gülme/şaşkınlık emote'u içeren mesaj da yazı sayılır: KEKW seli kahkahadır, emote yağmuru değil."""
    n = len(mesajlar)
    kisiler = {g for _, g in mesajlar if g not in ('', None)}
    yazi = sum(1 for x, _ in mesajlar if emote_disi_mi(x) or (sf is not None and sf.ozellik(x).emote_anlamli))
    return {'zirve_mesaj_sayisi': n, 'farkli_kullanici': len(kisiler) if kisiler else None,
            'emote_disi_mesaj': yazi, 'emote_disi_oran': round(yazi / n, 3) if n else 0.0}


def zayiflik_nedenleri(kalite: dict, ayar: dict) -> list[str]:
    neden = []
    if kalite['farkli_kullanici'] is not None and kalite['farkli_kullanici'] < ayar['min_farkli_kullanici']:
        neden.append(f"az_kullanici({kalite['farkli_kullanici']}<{ayar['min_farkli_kullanici']})")
    if kalite['emote_disi_oran'] < ayar['min_emote_disi_oran']:
        neden.append(f"emote_agirlikli({kalite['emote_disi_oran']}<{ayar['min_emote_disi_oran']})")
    return neden


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


# ---------------------------------------------------------------- sohbet sinyalleri
# Kahkaha, emote sınıfı, ortak konu ve oy/komut seli. Hepsi düz kural: model çağrısı yok, rastgelelik yok.

_HARF_RE = re.compile(r'[a-zçğıöşü]+')
_UNLU = frozenset('aeıioöuü')
_SIRA = frozenset('asdfghjkl')
_KLAVYE_DIZI = tuple(s[i:i + 4] for s in ('asdfghjkl', 'lkjhgfdsa') for i in range(6))
_HAHA_RE = re.compile(r'(?:[hj][aeıi]){2,}[hj]?|(?:[aeıi][hj]){2,}[aeıi]?')
_XD_RE = re.compile(r'(?:x+d+)+')
_SJ_RE = re.compile(r'(?:sj|js|ks|sk|hs|sh|jk|kj|hj|jh){2,}')
_ARDISIK_RE = re.compile(r'(.)\1+')
_UZATMA_RE = re.compile(r'(.)\1{2,}')             # 'bakkkk' -> 'bak' (3+ tekrar uzatmadır)
_UNSUZ_KUMESI_RE = re.compile(r'[^aeıioöuü]{3}')   # üç ardışık ünsüz: Türkçe sözcüklerde nadir, klavye yığınında sık
_RAKAM_RE = re.compile(r'[\d\s.,:+\-/*]+')


def _klavye_yigini_mi(tok: str) -> bool:
    """Rastgele klavye vuruşu ('asdasd', 'ahsjdhd'): ≥5 harf, en az 3 farklı harf, harflerin ≥%80'i orta sıra (asdfghjkl),
    ünlü oranı ≤%34 ve ayrıca ünlüsüzlük, 3 ardışık ünsüz, klavye dizisi ('asdf') ya da tekrarlı ikili ('asdasd') aranır;
    böylece 'sadakat', 'kasada', 'askıda', 'dakika' (ünlü oranı ≥%43), 'skandal', 'flash' gibi sözcükler kahkaha sayılmaz.
    3+ tekrarlı harf koşuları önce tek harfe indirilir ('bakkkk' -> 'bak'): uzatılmış sözcük kahkaha değildir."""
    n = len(tok)
    if n < 5 or len(set(tok)) < 3:
        return False
    sira = sum(1 for c in tok if c in _SIRA)
    unlu = sum(1 for c in tok if c in _UNLU)
    if sira / n < 0.8 or unlu / n > 0.34:
        return False
    if unlu == 0 or _UNSUZ_KUMESI_RE.search(tok):
        return True
    if any(d in tok for d in _KLAVYE_DIZI):
        return True
    return any(tok.count(tok[i:i + 2]) >= 2 for i in range(n - 1))


def gulme_belirteci_mi(tok: str, ek: frozenset = frozenset(), istisna: frozenset = frozenset()) -> bool:
    """tok: küçük harfli, yalnız harflerden oluşan tek kelime. Kahkaha biçimi mi?"""
    if tok in istisna:
        return False
    if tok in ek:
        return True
    k = _ARDISIK_RE.sub(r'\1', tok)      # 'hahahaaa' -> 'hahaha'
    if len(k) >= 4 and _HAHA_RE.fullmatch(k):
        return True
    if _XD_RE.fullmatch(k):
        return True
    if len(k) >= 4 and _SJ_RE.fullmatch(k):
        return True
    return _klavye_yigini_mi(_UZATMA_RE.sub(r'\1', tok))


class MesajOzelligi:
    __slots__ = ('gurultu', 'gulme', 'saskin', 'emote_anlamli', 'kelimeler')

    def __init__(self, gurultu: str, gulme: bool, saskin: bool, emote_anlamli: bool, kelimeler: tuple):
        self.gurultu, self.gulme, self.saskin = gurultu, gulme, saskin
        self.emote_anlamli, self.kelimeler = emote_anlamli, kelimeler


class Siniflayici:
    """Ayardaki listelerle tek mesajı sınıflar. gurultu: '' | 'komut' | 'oy' | 'emote_yagmuru'.
    Kahkaha: kahkaha biçimli kelime, gülme emojisi ya da gülme sınıfı emote; oy/komut mesajı kahkaha sayılmaz."""

    def __init__(self, ayar: dict):
        a = {**AYAR_VARSAYILAN, **ayar}
        self.emojiler = tuple(a['gulme_emojileri'])
        self.gulme_kel = frozenset(tr_kucuk(k) for k in a['gulme_kelimeleri'])
        self.istisna = frozenset(tr_kucuk(k) for k in a['gulme_istisna'])
        self.oy_kel = frozenset(tr_kucuk(k) for k in a['oy_kelimeleri'])
        self.sinif_listeleri = (('gulme', tuple(s.lower() for s in a['emote_gulme'])),
                                ('saskin', tuple(s.lower() for s in a['emote_saskin'])),
                                ('gurultu', tuple(s.lower() for s in a['emote_gurultu'])))
        self._onbellek: dict[str, str] = {}
        self.yuzey: dict[str, str] = {}   # sadeleşmiş terim -> yazılışı (başlık için)

    def emote_sinifi(self, ad: str) -> str:
        s = self._onbellek.get(ad)
        if s is None:
            a = ad.lower()
            if a.startswith('collectibles'):
                a = a[len('collectibles'):]
            s = next((sinif for sinif, liste in self.sinif_listeleri if any(p in a for p in liste)), 'notr')
            self._onbellek[ad] = s
        return s

    def kahkaha_kelimesi(self, tok: str) -> bool:
        return gulme_belirteci_mi(tok, self.gulme_kel, self.istisna)

    def ozellik(self, metin: str) -> MesajOzelligi:
        siniflar = [self.emote_sinifi(a) for a in EMOTE_RE.findall(metin)]
        govde = EMOTE_RE.sub(' ', metin).strip()
        if govde.startswith('!'):
            return MesajOzelligi('komut', False, False, False, ())
        kel = tuple(_HARF_RE.findall(tr_kucuk(URL_RE.sub(' ', govde))))
        gulme_emote, saskin = 'gulme' in siniflar, 'saskin' in siniflar
        if not (gulme_emote or saskin):
            tek = len(re.sub(r'[\W_]+', '', govde)) == 1
            if govde and (tek or _RAKAM_RE.fullmatch(govde) or ' '.join(kel) in self.oy_kel):
                return MesajOzelligi('oy', False, False, False, ())
            if not govde and siniflar and all(s == 'gurultu' for s in siniflar):
                return MesajOzelligi('emote_yagmuru', False, False, False, ())
        gulme = (gulme_emote or any(e in govde for e in self.emojiler)
                 or any(self.kahkaha_kelimesi(t) for t in kel))
        return MesajOzelligi('', gulme, saskin, bool(kel) or gulme_emote or saskin, kel)

    def terimler(self, kel: tuple) -> list[str]:
        """Konu adayı terimler: gürültü kelimesi, sayı ve kahkaha olmayan kelimeler ile ardışık ikililer."""
        temiz = []
        for k in kel:
            if len(k) < 3 or k in DURAK or self.kahkaha_kelimesi(k):
                continue
            s = _ARDISIK_RE.sub(r'\1', k)
            self.yuzey.setdefault(s, k)
            temiz.append(s)
        cikti = list(temiz)
        for a, b in zip(temiz, temiz[1:]):
            self.yuzey.setdefault(f'{a} {b}', f'{self.yuzey[a]} {self.yuzey[b]}')
            cikti.append(f'{a} {b}')
        return cikti


def _yayilma_anahtari(metin: str) -> str:
    return ' '.join(tr_kucuk(metin).split())


def dilim_ozetle(mesajlar: list[tuple[str, object]], sf: Siniflayici, ayar: dict) -> dict:
    """Tek dilimin sinyal özeti. mesajlar: [(metin, gönderen)]. Aynı kişinin tekrarı terim ve kahkaha sayısında bir kez sayılır."""
    ozel = [sf.ozellik(x) for x, _ in mesajlar]
    grup: dict[str, set] = {}
    for (x, g), o in zip(mesajlar, ozel):
        if not o.gurultu:
            a = _yayilma_anahtari(x)
            if len(a) >= ayar['yayilma_min_uzunluk'] and len(o.kelimeler) >= ayar['yayilma_min_kelime']:
                grup.setdefault(a, set()).add(g)
    yayilma = {a for a, s in grup.items() if len(s) >= ayar['yayilma_min_kisi']}
    gurultu: Counter = Counter()
    kisi, gulen, saskin = set(), set(), set()
    n_sinyal = gulme_n = 0
    agirlik: dict[tuple, float] = {}
    for (x, g), o in zip(mesajlar, ozel):
        kisi.add(g)
        if o.gurultu:
            gurultu[o.gurultu] += 1
            continue
        sel = _yayilma_anahtari(x) in yayilma
        if sel:
            gurultu['yayilma'] += 1
        else:
            n_sinyal += 1
            if o.gulme:
                gulme_n += 1
                gulen.add(g)
            elif o.saskin:
                saskin.add(g)
        w = ayar['yayilma_konu_agirlik'] if sel else 1.0
        for t in sf.terimler(o.kelimeler):
            agirlik[(t, g)] = max(agirlik.get((t, g), 0.0), w)
    terimler: Counter = Counter()
    for (t, _), w in agirlik.items():
        terimler[t] += w
    n = len(mesajlar)
    saf_gurultu = gurultu['komut'] + gurultu['oy'] + gurultu['emote_yagmuru']
    return {'n': n, 'n_sinyal': n_sinyal, 'kisi': len(kisi), 'gulme_n': gulme_n, 'gulme_kisi': len(gulen),
            'saskin_kisi': len(saskin - gulen), 'gurultu': dict(gurultu),
            'gurultu_oran': round(saf_gurultu / n, 3) if n else 0.0, 'terimler': terimler}


def konu_bul(o: dict, genel: Counter, genel_kisi: int, ayar: dict, sf: Siniflayici) -> dict | None:
    """Dilimde, yayının geri kalanına göre nadir olup çok FARKLI kişinin yazdığı kelime/ikili. Yoksa None."""
    en = None
    for t, dc in o['terimler'].items():
        if dc < ayar['konu_min_kisi']:
            continue
        p_dilim = dc / max(o['kisi'], 1)
        p_genel = (genel[t] - dc + 1.0) / max(genel_kisi - o['kisi'], 1)
        lift = p_dilim / p_genel
        if lift < ayar['konu_min_lift']:
            continue
        aday = {'anahtar': t, 'terim': sf.yuzey.get(t, t), 'kisi': round(dc, 1), 'lift': round(lift, 1)}
        if en is None or (aday['kisi'], aday['lift']) > (en['kisi'], en['lift']):
            en = aday
    if en and ' ' not in en['anahtar']:
        # kelime bir ikilinin parçasıysa ve ikili neredeyse aynı kişi sayısına ulaşıyorsa ikiliyi tercih et
        for t, dc in o['terimler'].items():
            if ' ' in t and en['anahtar'] in t.split() and dc >= 0.8 * en['kisi'] and dc >= ayar['konu_min_kisi']:
                p_genel = (genel[t] - dc + 1.0) / max(genel_kisi - o['kisi'], 1)
                if dc / max(o['kisi'], 1) / p_genel >= ayar['konu_min_lift']:
                    en = {'anahtar': t, 'terim': sf.yuzey.get(t, t), 'kisi': round(dc, 1),
                          'lift': round(dc / max(o['kisi'], 1) / p_genel, 1)}
                    break
    return en


def dilim_bilesenleri(o: dict, ort_s: float, std_s: float, konu: dict | None, ayar: dict) -> dict:
    """0-1 arası üç bileşen ve ağırlıklı toplam (0-100)."""
    etkin = o['gulme_kisi'] + ayar['saskin_agirlik'] * o['saskin_kisi']
    oran = o['gulme_n'] / max(o['n_sinyal'], 1)
    g = (0.5 * min(1.0, etkin / ayar['gulme_tam_kisi']) + 0.5 * min(1.0, oran / ayar['gulme_tam_oran'])) if o['gulme_n'] else 0.0
    k = min(1.0, konu['kisi'] / ayar['konu_tam_kisi']) if konu else 0.0
    z = (o['n_sinyal'] - ort_s) / std_s if std_s > 0 else 0.0
    y = min(1.0, max(0.0, z) / ayar['yogunluk_tam_z'])
    wg, wk, wy = ayar['agirlik_gulme'], ayar['agirlik_konu'], ayar['agirlik_yogunluk']
    return {'gulme': round(g, 3), 'konu': round(k, 3), 'yogunluk': round(y, 3), 'gulme_etkin_kisi': round(etkin, 1),
            'gulme_oran': round(oran, 3), 'yogunluk_z': round(z, 2),
            'toplam': round(100 * (wg * g + wk * k + wy * y) / (wg + wk + wy), 1)}


def _kumele(indeksler: list[int], dilim: int, birlestir_sn: float) -> list[list[int]]:
    kumeler: list[list[int]] = []
    for i in indeksler:
        if kumeler and (i - kumeler[-1][-1]) * dilim <= birlestir_sn:
            kumeler[-1].append(i)
        else:
            kumeler.append([i])
    return kumeler


def sinyal_ozetleri(ham: list[tuple], toplam_sn: float, ayar: dict, sf: Siniflayici | None = None) -> tuple[list[dict], Siniflayici]:
    """ham: (video_sn, metin, gönderen). Her dilim için dilim_ozetle."""
    sf = sf or Siniflayici(ayar)
    dilim = ayar['dilim_sn']
    kovalar: list[list] = [[] for _ in range(int(math.ceil(toplam_sn / dilim)))]
    for i, (t, x, g) in enumerate(ham):
        if 0 <= t < toplam_sn:
            kovalar[int(t // dilim)].append((x, g if g not in ('', None) else f'#{i}'))
    return [dilim_ozetle(k, sf, ayar) for k in kovalar], sf


def araliklar_orter(bas: float, bit: float, araliklar: list[tuple[float, float]] | None) -> bool:
    """[bas, bit) aralığı verilen aralıklardan biriyle örtüşüyor mu? (kenar kenara değmek örtüşme sayılmaz)"""
    return any(bas < b and a < bit for a, b in (araliklar or []))


def sinyal_zirveleri(ozetler: list[dict], ayar: dict, toplam_sn: float, sf: Siniflayici, kalite=None,
                     engelli: list[tuple[float, float]] | None = None) -> tuple[list[dict], dict]:
    """Kahkaha ya da ortak konu sinyali taşıyan dilimleri kümeler; oy/komut seli ve zayıf zirveler elenir.
    Yoğunluk tek başına zirve yapmaz. En iyi azami_klip tanesi (örtüşmeyen) döndürülür.
    engelli: (başlangıç_sn, bitiş_sn) aralıkları; bunlarla örtüşen aday seçilmez (canlıda zaten kesilmiş anlar)."""
    dilim = ayar['dilim_sn']
    sayim = [o['n'] for o in ozetler]
    eski = istatistik(sayim, ayar)
    ist = {'lo': eski['lo'], 'hi': eski['hi'], 'ort': eski['ort'], 'std': eski['std'], 'esik': eski['esik'], 'elenen': []}
    lo, hi = eski['lo'], eski['hi']
    if hi - lo < 6:
        return [], ist
    ort_s = statistics.fmean(o['n_sinyal'] for o in ozetler[lo:hi])
    std_s = statistics.pstdev(o['n_sinyal'] for o in ozetler[lo:hi])
    etkinler = [o['gulme_kisi'] + ayar['saskin_agirlik'] * o['saskin_kisi'] for o in ozetler[lo:hi]]
    ort_g, std_g = statistics.fmean(etkinler), statistics.pstdev(etkinler)
    gulme_esigi = max(ayar['gulme_min_kisi'], ort_g + ayar['gulme_esik_k'] * std_g)
    ist.update(gulme_ort=ort_g, gulme_std=std_g, gulme_esigi=gulme_esigi, sinyal_ort=ort_s, sinyal_std=std_s)
    genel: Counter = Counter()
    genel_kisi = 0
    for o in ozetler:
        genel.update(o['terimler'])
        genel_kisi += o['kisi']
    uygun, gurultulu = [], []
    for i in range(lo, hi):
        o = ozetler[i]
        o['konu'] = konu_bul(o, genel, genel_kisi, ayar, sf)
        o['b'] = b = dilim_bilesenleri(o, ort_s, std_s, o['konu'], ayar)
        gulme_uygun = b['gulme_etkin_kisi'] >= gulme_esigi and o['gulme_n'] / max(o['n_sinyal'], 1) >= ayar['gulme_min_oran']
        konu_uygun = o['konu'] is not None
        o['uygun'] = (gulme_uygun, konu_uygun)
        if (gulme_uygun or konu_uygun or o['n'] >= eski['esik']) and o['gurultu_oran'] >= ayar['max_gurultu_oran']:
            gurultulu.append(i)
        elif (gulme_uygun or konu_uygun) and o['n_sinyal'] >= ayar['min_sinyal_mesaj']:
            uygun.append(i)
    for k in _kumele(gurultulu, dilim, ayar['birlestir_sn']):
        tepe = max(k, key=lambda i: ozetler[i]['n'])
        o = ozetler[tepe]
        ist['elenen'].append({'zirve_sn': tepe * dilim, 'zirve_zaman': zaman_metni(tepe * dilim), 'mesaj': o['n'],
                              'neden': [f"oy_seli({o['gurultu_oran']}>={ayar['max_gurultu_oran']})"], 'gurultu': o['gurultu']})
    adaylar = []
    for k in _kumele(uygun, dilim, ayar['birlestir_sn']):
        tepe = max(k, key=lambda i: ozetler[i]['b']['toplam'])
        t = ozetler[tepe]
        wg, wk = ayar['agirlik_gulme'], ayar['agirlik_konu']
        g_en = max(ozetler[i]['b']['gulme'] for i in k)
        k_en = max(ozetler[i]['b']['konu'] for i in k)
        baskin = 'gulme' if wg * g_en >= wk * k_en else 'konu'
        # dalga başlangıcı: kahkaha/konu OLAYDAN SONRA gelir; eşiği aşan ilk dilimden geriye, sinyal sürdüğü sürece
        if baskin == 'gulme':
            olcu = lambda i: (ozetler[i]['gulme_kisi'] + ayar['saskin_agirlik'] * ozetler[i]['saskin_kisi']) / gulme_esigi
            terim = None
        else:
            terim = max((ozetler[i]['konu'] for i in k if ozetler[i]['konu']), key=lambda c: (c['kisi'], c['lift']))
            olcu = lambda i: ozetler[i]['terimler'].get(terim['anahtar'], 0.0) / ayar['konu_min_kisi']
        dalga = k[0]
        for j in range(k[0] - 1, max(-1, k[0] - 1 - ayar['dalga_geri_azami_dilim']), -1):
            if j < 0 or olcu(j) < ayar['dalga_geri_oran']:
                break
            dalga = j
        referans = dalga if ayar['klip_baslangic'] == 'dalga' else tepe
        bas = referans * dilim - ayar['onceden_sn']
        bit = max((k[-1] + 1) * dilim + ayar['kuyruk_sn'], bas + ayar['klip_min_sn'])
        bit = min(bit, bas + ayar['klip_azami_sn'])
        if bas < 0:
            bit -= bas
            bas = 0
        if bit > toplam_sn:
            bas = max(0, bas - (bit - toplam_sn))
            bit = toplam_sn
        kalite_alani = {}
        if kalite:
            kalite_alani = kalite(k[0] * dilim, (k[-1] + 1) * dilim)
            neden = zayiflik_nedenleri(kalite_alani, ayar)
            if neden:
                ist['elenen'].append({'zirve_sn': tepe * dilim, 'zirve_zaman': zaman_metni(tepe * dilim),
                                      'mesaj': t['n'], 'neden': neden, **kalite_alani})
                continue
        b = t['b']
        konu = terim if baskin == 'konu' else t['konu']
        adaylar.append({
            **kalite_alani,
            'zirve_sn': tepe * dilim,
            'mesaj': t['n'],
            'puan': b['toplam'],
            'oran': round(t['n'] / ist['ort'], 2) if ist['ort'] else 0.0,
            'baskin': baskin,
            'zirve_dilimleri': [i * dilim for i in k],
            'dalga_basi_sn': dalga * dilim,
            'klip_baslangic_sn': float(bas),
            'klip_bitis_sn': float(bit),
            'sure_sn': float(bit - bas),
            'puan_bilesenleri': {
                'toplam': b['toplam'],
                'agirliklar': {'gulme': wg, 'konu': wk, 'yogunluk': ayar['agirlik_yogunluk']},
                'gulme': {'puan': b['gulme'], 'kisi': t['gulme_kisi'], 'etkin_kisi': b['gulme_etkin_kisi'],
                          'mesaj': t['gulme_n'], 'oran': b['gulme_oran'], 'esik_kisi': round(gulme_esigi, 1)},
                'konu': {'puan': b['konu'], **({k_: konu[k_] for k_ in ('terim', 'kisi', 'lift')} if konu else {})},
                'yogunluk': {'puan': b['yogunluk'], 'sinyal_mesaj': t['n_sinyal'], 'ham_mesaj': t['n'], 'z': b['yogunluk_z']},
                'gurultu': {'oran': t['gurultu_oran'], **t['gurultu']},
            },
        })
    secilen: list[dict] = []
    for a in sorted(adaylar, key=lambda a: (-a['puan'], a['zirve_sn'])):
        if len(secilen) >= ayar['azami_klip']:
            break
        if any(a['klip_baslangic_sn'] < s['klip_bitis_sn'] and s['klip_baslangic_sn'] < a['klip_bitis_sn'] for s in secilen):
            continue
        if araliklar_orter(a['klip_baslangic_sn'], a['klip_bitis_sn'], engelli):
            continue
        secilen.append(a)
    secilen.sort(key=lambda a: a['zirve_sn'])
    for n, a in enumerate(secilen, 1):
        a['no'] = n
        a['zirve_zaman'] = zaman_metni(a['zirve_sn'])
    return secilen, ist


def analiz_et(vod: dict, mesajlar: list[tuple], ayar: dict, engelli: list[tuple[float, float]] | None = None) -> dict:
    """mesajlar: (epoch, metin) veya (epoch, metin, gönderen). engelli: yalnız sinyal yönteminde (bkz. sinyal_zirveleri)."""
    ayar = {**AYAR_VARSAYILAN, **ayar}
    t0 = vod['t0_epoch']
    toplam = vod['sure_sn']
    ham = [(m[0] - t0, m[1], m[2] if len(m) > 2 else '') for m in mesajlar]
    sayim = dilim_say([t for t, _, _ in ham], ayar['dilim_sn'], toplam)
    ek = {}
    if ayar['yontem'] == 'yogunluk':
        klipler, ist = zirveleri_bul(sayim, ayar, toplam,
                                     kalite=lambda a, b: zirve_kalitesi([(x, g) for t, x, g in ham if a <= t < b]))
    else:
        ozetler, sf = sinyal_ozetleri(ham, toplam, ayar)
        klipler, ist = sinyal_zirveleri(ozetler, ayar, toplam, sf,
                                        kalite=lambda a, b: zirve_kalitesi([(x, g) for t, x, g in ham if a <= t < b], sf),
                                        engelli=engelli)
        if 'gulme_esigi' in ist:
            ek = {'gulme_ortalama': round(ist['gulme_ort'], 2), 'gulme_std': round(ist['gulme_std'], 2),
                  'gulme_esigi': round(ist['gulme_esigi'], 2)}
    tum = [x for t, x, _ in ham if 0 <= t < toplam]
    for k in klipler:
        a = min(k['zirve_dilimleri'])
        b = max(k['zirve_dilimleri']) + ayar['dilim_sn']
        tepe = [x for t, x, _ in ham if a <= t < b]
        k['kelimeler'], k['emojiler'] = one_cikan(tepe, tum)
        ornek = [x.strip() for x in tepe if 3 <= len(x.strip()) <= 80][:5]
        k['ornek_mesajlar'] = ornek
    return {
        'vod': {k: vod.get(k) for k in ('platform', 'vod_id', 'anahtar', 'yayinci', 'kanal', 'baslik', 'oyun', 'kategoriler',
                                      'sure_sn', 'vod_url', 'kanal_url', 'tarih', 't0_epoch', 't0_kaynagi')},
        'ayar': ayar,
        'istatistik': {'mesaj': len(tum), 'dilim': len(sayim), 'ortalama': round(ist['ort'], 2),
                       'std': round(ist['std'], 2),
                       'esik': None if ist['esik'] == float('inf') else round(ist['esik'], 2), **ek},
        'dilim_sayimlari': sayim,
        'klipler': klipler,
        'elenen_zirveler': ist['elenen'],
    }


# ---------------------------------------------------------------- başlık ve açıklama (şablon)

BASLIK_SABLONLARI = (
    '{ad} yayınında chat patladı!{oyun}',
    '{ad} yayınında sohbetin en çılgın anı{oyun}',
    'Chat bir anda coştu: {ad} yayını{oyun}',
    '{ad} yayınında herkes aynı anda yazdı!{oyun}',
)


BASLIK_GULME = (
    '{ad} yayınında chat kahkahaya boğuldu{oyun}',
    '{ad} yayınında sohbet bir anda gülmeye başladı{oyun}',
    '{ad} yayınında chat gülmekten kırıldı{oyun}',
)
BASLIK_KONU = (
    '{ad} yayınında chat aynı kelimede buluştu: “{terim}”{oyun}',
    '{ad} yayınında herkes aynı şeyi yazdı: “{terim}”{oyun}',
)


def baslik_uret(vod: dict, klip: dict) -> str:
    """Başlık baskın sinyale göre seçilir; sinyal bilgisi yoksa (eski yöntem) yoğunluk şablonları kullanılır.
    Konu şablonu yalnız sohbetten gerçekten çıkarılmış bir terim varsa kullanılır; yoksa kahkaha şablonuna düşer."""
    if klip.get('konusma_baslik'):
        b = klip['konusma_baslik'].strip()
        return b if len(b) <= 95 else b[:94].rsplit(' ', 1)[0] + '…'
    sec = int(hashlib.sha1(f"{vod['anahtar']}:{klip['no']}".encode()).hexdigest(), 16)
    oyun = f" | {vod['oyun']}" if vod.get('oyun') else ''
    baskin = klip.get('baskin')
    terim = ((klip.get('puan_bilesenleri') or {}).get('konu') or {}).get('terim')
    if baskin == 'konu' and terim:
        sablon = BASLIK_KONU[sec % len(BASLIK_KONU)]
    elif baskin in ('gulme', 'konu'):
        sablon = BASLIK_GULME[sec % len(BASLIK_GULME)]
    else:
        sablon = BASLIK_SABLONLARI[sec % len(BASLIK_SABLONLARI)]
    b = sablon.format(ad=vod['yayinci'], oyun=oyun, terim=terim or '')
    return b if len(b) <= 95 else b[:94].rstrip() + '…'


def etiket(ad: str) -> str:
    return ''.join(w.capitalize() for w in re.split(r'[^0-9A-Za-zÇĞİÖŞÜçğıöşü]+', dosya_adi(ad).replace('-', ' ')) if w)


def zaman_damgali_baglanti(vod: dict, sn: float) -> tuple[str, bool]:
    """(adres, platformda doğrulandı mı). Kick'in belgelenmiş bir zaman parametresi yok: ?t= denenmedi."""
    if vod['platform'] == 'kick':
        return f"{vod['vod_url']}?t={int(sn)}", False
    if vod['platform'] == 'youtube':
        return f"https://youtu.be/{vod['vod_id']}?t={int(sn)}", True
    return vod['vod_url'], False


def _an_tarifi(klip: dict) -> str:
    if klip.get('konusma_baslik'):
        return klip['konusma_baslik'].rstrip('.!?')
    b = klip.get('baskin')
    if b == 'gulme':
        return 'sohbetin kahkahaya boğulduğu an'
    if b == 'konu':
        return 'sohbetin aynı konuda toplandığı an'
    return 'sohbetin en yoğunlaştığı an'


def marka_yazisi(ayar: dict | None = None) -> str:
    """Videoya yazılan marka satırı. Ayarda anahtar varsa (boş dahil) o; yoksa eski sabit."""
    m = (ayar or {}).get('marka_yazi')
    return MARKA_YAZI_VARSAYILAN if m is None else re.sub(r'\s+', ' ', str(m)).strip()


def marka_ayari(marka: str) -> dict:
    """Pakete özel marka: video yazısı + paylaşım imzası aynı metin, ek etiket markadan türer (boş marka = hiçbiri)."""
    kelime = re.sub(r'[^\w]', '', marka or '')
    return {'marka_yazi': marka, 'klip_paylasim_imza': marka, 'klip_ek_etiketler': ['#' + kelime] if kelime else []}


def paylasim_imzasi(ayar: dict | None = None) -> tuple[str, list[str]]:
    """(imza satırı, ek etiketler). Boş imza = satır yok; boş liste = ek etiket yok."""
    a = ayar or {}
    imza = a.get('klip_paylasim_imza')
    imza = PAYLASIM_IMZA_VARSAYILAN if imza is None else str(imza).strip()
    ek = a.get('klip_ek_etiketler')
    ek = list(EK_ETIKET_VARSAYILAN) if ek is None else [str(e).strip() for e in ek if str(e).strip()]
    return imza, ek


def aciklama_uret(vod: dict, klip: dict, ayar: dict | None = None) -> str:
    bas = klip['klip_baslangic_sn']
    konu = ''
    if klip.get('kelimeler') or klip.get('emojiler'):
        konu = ' Sohbette öne çıkanlar: ' + ', '.join((klip.get('kelimeler') or [])[:3] + (klip.get('emojiler') or [])[:2]) + '.'
    youtube = vod['platform'] == 'youtube'
    platform = 'YouTube' if youtube else vod['platform'].capitalize()
    kaynak = 'videosundan' if youtube else 'canlı yayınından'
    imza, ek = paylasim_imzasi(ayar)
    return (
        f"{vod['yayinci']} {kaynak} ({vod['tarih']}, {platform}) {_an_tarifi(klip)}.{konu}\n\n"
        f"Yayıncı: {vod['yayinci']} — {vod['kanal_url']}\n"
        f"Kaynak yayın: {vod['vod_url']} (yayının {zaman_metni(bas)} noktası)\n"
        "Görüntü ve ses yayıncıya aittir; tam yayın için kanalına gidin.\n\n"
        + (imza + "\n" if imza else "")
        + ' '.join([f"#Shorts #{platform} #{etiket(vod['yayinci'])}", *ek]).strip()
    )


def paket_json(vod: dict, klip: dict, mp4: pathlib.Path, dogrulama: dict, ayar: dict | None = None,
               ekstra: dict | None = None) -> dict:
    link, dogrulandi = zaman_damgali_baglanti(vod, klip['klip_baslangic_sn'])
    ok = klip.get('oyun_dogrulama')
    if isinstance(ok, dict):   # oyun adı DOĞRU yazılır ya da hiç yazılmaz: kategori ancak doğrulanınca kullanılır
        vod = {**vod, 'oyun': ok.get('oyun')}
    return {**{
        'yayinci': vod['yayinci'],
        'platform': vod['platform'],
        'vod_id': vod['vod_id'],
        'kaynak_sure_sn': vod['sure_sn'],
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
        'baskin_sinyal': klip.get('baskin'),
        'puan_bilesenleri': klip.get('puan_bilesenleri'),
        'dalga_basi_sn': klip.get('dalga_basi_sn'),
        'sohbet_puani': klip.get('sohbet_puani', klip['puan']),
        'konusma_puani': klip.get('konusma_puani'),
        'konusma_gerekce': klip.get('konusma_gerekce'),
        'dokum_metni': klip.get('dokum_metni'),
        'konusma_plan_araligi': klip.get('konusma_plan_araligi'),
        'aday_kaynaklari': klip.get('kaynaklar', ['sohbet']),
        'zirve_mesaj_sayisi': klip.get('zirve_mesaj_sayisi'),
        'zirve_farkli_kullanici': klip.get('farkli_kullanici'),
        'zirve_emote_disi_oran': klip.get('emote_disi_oran'),
        'klip_baslangic_sn': klip['klip_baslangic_sn'],
        'klip_bitis_sn': klip['klip_bitis_sn'],
        'one_cikan_kelimeler': klip.get('kelimeler', []),
        'one_cikan_emojiler': klip.get('emojiler', []),
        'ornek_mesajlar': klip.get('ornek_mesajlar', []),
        'baslik': baslik_uret(vod, klip),
        'aciklama': aciklama_uret(vod, klip, ayar),
        'dosya': mp4.name,
        'video': dogrulama,
        'kisa_aciklama': klip_aciklamasi(klip, ayar),
        'aciklama_yazisi': dogrulama.get('aciklama_yazisi'),
        **({'kamera_plani': dogrulama['kamera']} if dogrulama.get('kamera') else {}),
        'duzen': duzen_imzasi(ayar or AYAR_VARSAYILAN, klip_aciklamasi(klip, ayar)),
        **({'oyun_dogrulama': ok} if isinstance(ok, dict) else {}),
        **({'ses_yargisi': klip['ses_yargisi']} if isinstance(klip.get('ses_yargisi'), dict) else {}),
        'uretim': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'yayinlandi': False,
    }, **(ekstra or {})}


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


def _aciklamayi_isle(yz: dict, aciklama: dict | None) -> dict:
    """Açıklama yerleşimi (aciklama_duzeni sonucu) varsa yerleşime ekler. Görüntü kutusu ve eski yazı konumları
    değişmez; açıklamalı klipte yazıların hepsini aciklama['alt'] ve aciklama['y'] belirler (PNG katmanı)."""
    if aciklama:
        yz['aciklama'] = aciklama
    return yz


def yazi_genisligi(font: str, metin: str, boyut: int, kenar: int = 0) -> float:
    """drawtext çıktısının yaklaşık genişliği (PIL ile ölçülür; PIL yoksa 0.62 em tahmini) + iki yan kenar çizgisi."""
    try:
        from PIL import ImageFont
        return ImageFont.truetype(font, boyut).getlength(metin) + 2 * kenar
    except Exception:
        return 0.62 * boyut * len(metin) + 2 * kenar


def aciklama_satirlari(metin: str, font: str, boyut: int, azami_px: float, kenar: int,
                       tek_satir: bool) -> list[str] | None:
    """Metni ≤2 satıra böler (kelime ortasından değil, kısaltmadan); sığmıyorsa None.
    tek_satir=True ise sığıyorsa tek satır tercih edilir; değilse en dengeli ikili bölüm aranır."""
    kelimeler = metin.split()
    if not kelimeler:
        return None
    if tek_satir and yazi_genisligi(font, ' '.join(kelimeler), boyut, kenar) <= azami_px:
        return [' '.join(kelimeler)]
    en_iyi = None
    for i in range(1, len(kelimeler)):
        a, b = ' '.join(kelimeler[:i]), ' '.join(kelimeler[i:])
        w = max(yazi_genisligi(font, a, boyut, kenar), yazi_genisligi(font, b, boyut, kenar))
        if w <= azami_px and (en_iyi is None or w < en_iyi[0]):
            en_iyi = (w, [a, b])
    return en_iyi[1] if en_iyi else None


def aciklama_stili(ayar: dict | None = None) -> str:
    """Ayardaki klip_aciklama_stil (A|B|C); yoksa varsayılan. Geçersiz değer sessizce yutulmaz."""
    s = str((ayar or {}).get('klip_aciklama_stil') or ACIKLAMA_STIL_VARSAYILAN).strip().upper()
    if s not in ACIKLAMA_STILLERI:
        raise KlipHatasi(f"klip_aciklama_stil {'/'.join(ACIKLAMA_STILLERI)} olmalı: {s!r}")
    return s


def aciklama_fontu() -> str:
    """Açıklama yazı tipi: KLIP_ACIKLAMA_FONT, depodaki Anton (OFL), yoksa sistemin kalın yazı tipi."""
    env = os.environ.get('KLIP_ACIKLAMA_FONT', '')
    for a in (env, str(ACIKLAMA_FONT_DOSYASI)):
        if a and pathlib.Path(a).is_file():
            return a
    return font_bul()


def _murekkep(font: str, metinler: list[str], boyut: int) -> tuple[int, int]:
    """Taban çizgisine göre mürekkep sınırı (üst eksi): verilen satırlar + 'Kg' (büyük harf ve alt uzantı payı).
    Etiket yüksekliği buradan çıkar: diakritikli büyük harf (Ğ İ Ü) satırdaysa etiket onu da kapsar."""
    try:
        from PIL import ImageFont
        f = ImageFont.truetype(font, boyut)
        ust = alt = 0
        for t in [*metinler, 'Kg']:
            b = f.getbbox(t, anchor='ls')
            ust, alt = min(ust, b[1]), max(alt, b[3])
        return ust, alt
    except Exception:   # noqa: BLE001 - PIL/yazı tipi yoksa kaba tahmin (katman zaten çizilemez)
        return -int(boyut * 1.1), int(boyut * 0.3)


def _alt_satir_yuksekligi(boyut: int) -> int:
    return int(boyut * 1.4)


def aciklama_duzeni(metin: str | None, font: str, ayar: dict | None = None, duzen: dict = DUZEN,
                    oyun_var: bool = True) -> dict | None:
    """Kısa açıklamanın yeri: görüntü karesinin hemen ÜSTÜNDE (alt kenar = kare üstü - video_boslugu), ≤2 satır,
    en üst 'ust_sinir' px boş. Satır başına bir etiket kutusu (kutular), hepsi aynı yükseklikte.
    Yayıncı adı + oyun, kaynak ve marka görüntünün ALTINA dizilir ('alt').
    Tek satır yalnız 'tek_satir_en_az' pt ve üstünde, iki satır 'en_az' pt'e kadar küçülür.
    Sığmıyorsa None (açıklama çizilmez, eski görünüm). 'font' ölçüm içindir: çizimde de aynı yazı tipi kullanılır."""
    if not metin or not metin.strip():
        return None
    c = duzen['aciklama']
    stil = aciklama_stili(ayar)
    yz = yerlesim(ayar, duzen)
    y0 = yz['gorsel_y']
    gorsel_alt = y0 + yz['gorsel_h']
    alt = y0 - c['video_boslugu']
    for boyut in range(c['boyut'], c['en_az'] - 1, -2):
        satirlar = aciklama_satirlari(metin, font, boyut, duzen['metin_azami_px'], c['pad_x'],
                                      tek_satir=boyut >= c['tek_satir_en_az'])
        if not satirlar:
            continue
        ust_m, alt_m = _murekkep(font, satirlar, boyut)
        kutu_h = (alt_m - ust_m) + 2 * c['pad_y']
        toplam = kutu_h * len(satirlar) + c['satir_arasi'] * (len(satirlar) - 1)
        ust = alt - toplam
        if ust < c['ust_sinir'] + c['golge_pay']:   # gölge/kontur 150 px sınırına taşmasın
            continue
        ys = [ust + i * (kutu_h + c['satir_arasi']) for i in range(len(satirlar))]
        kutular = []
        for y, s in zip(ys, satirlar):
            w = yazi_genisligi(font, s, boyut, c['pad_x'])
            x0 = (duzen['genislik'] - w) / 2
            kutular.append((round(x0, 1), y, round(x0 + w, 1), y + kutu_h))
        alt_satirlar, y_alt = {}, gorsel_alt + c['alt_bosluk']
        for ad, b in (('ad_oyun', c['ad_boyut']), ('kaynak', c['kaynak_boyut']), ('marka', c['marka_boyut'])):
            alt_satirlar[ad] = {'y': y_alt, 'boyut': b, 'h': _alt_satir_yuksekligi(b)}
            y_alt += _alt_satir_yuksekligi(b) + c['alt_satir_arasi']
        return {'satirlar': satirlar, 'boyut': boyut, 'y': ys, 'kutu_h': kutu_h, 'kutular': kutular,
                'taban': [y + c['pad_y'] - ust_m for y in ys], 'ust': ust, 'alt': alt, 'stil': stil, 'font': font,
                'alt_satirlar': alt_satirlar, 'oyun_var': bool(oyun_var), 'alt_son': y_alt - c['alt_satir_arasi']}
    return None


def yerlesim(ayar: dict | None = None, duzen: dict = DUZEN, aciklama: dict | None = None) -> dict:
    """Görüntü kutusu ve yazı konumları (1080x1920 tuvalde piksel).
    'kadraj': yayın ortadan kadraj_oran'a kırpılıp genişliğe sığdırılır; yazılar görüntünün üstünde/altında kalır.
    'serit': eski düzen, kırpmasız tam genişlik 16:9 şerit ve sabit yazı konumları."""
    ayar = ayar or {}
    w, h = duzen['genislik'], duzen['yukseklik']
    mod = ayar.get('duzen', AYAR_VARSAYILAN['duzen'])
    if mod not in ('kamera', 'kadraj', 'serit'):
        raise KlipHatasi(f"duzen 'kamera', 'kadraj' veya 'serit' olmalı: {mod!r}")
    yazilar = ('ust_ad', 'ust_oyun', 'alt_kaynak', 'alt_marka')
    if mod == 'kamera':
        k = duzen['kamera']
        gh = k['icerik_h'] + k['bosluk'] + k['kamera_h']
        kaynak_y = k['ust'] + gh + 34
        marka_y = kaynak_y + int(duzen['alt_kaynak']['boyut'] * METIN_SATIR_KATSAYI) + 10
        oyun_y = k['ust'] - 30 - int(duzen['ust_oyun']['boyut'] * METIN_SATIR_KATSAYI)
        return _aciklamayi_isle({
            'mod': mod, 'oran': None, 'gorsel_y': k['ust'], 'gorsel_h': gh,
            'paneller': {'icerik': {'y': k['ust'], 'h': k['icerik_h'], 'oran': round(w / k['icerik_h'], 4)},
                         'kamera': {'y': k['ust'] + k['icerik_h'] + k['bosluk'], 'h': k['kamera_h'],
                                    'oran': round(w / k['kamera_h'], 4)}},
            'y': {'ust_ad': oyun_y - 18 - int(duzen['ust_ad']['boyut'] * METIN_SATIR_KATSAYI),
                  'ust_oyun': oyun_y, 'alt_kaynak': kaynak_y, 'alt_marka': marka_y}}, aciklama)
    if mod == 'serit':
        gh = int(round(w / KAYNAK_ORAN / 2)) * 2
        return _aciklamayi_isle({'mod': mod, 'oran': None, 'gorsel_y': (h - gh) // 2, 'gorsel_h': gh,
                                 'y': {a: duzen[a]['y_serit'] for a in yazilar}}, aciklama)
    oran = min(max(float(ayar.get('kadraj_oran', AYAR_VARSAYILAN['kadraj_oran'])), KADRAJ_EN_AZ), KAYNAK_ORAN)
    gh = int(round(w / oran / 2)) * 2
    y0 = int(duzen['gorsel_merkez_y'] - gh / 2)
    kat = METIN_SATIR_KATSAYI
    oyun_y = y0 - 30 - int(duzen['ust_oyun']['boyut'] * kat)
    ad_y = oyun_y - 18 - int(duzen['ust_ad']['boyut'] * kat)
    kaynak_y = y0 + gh + 34
    marka_y = kaynak_y + int(duzen['alt_kaynak']['boyut'] * kat) + 10
    return _aciklamayi_isle({'mod': mod, 'oran': oran, 'gorsel_y': y0, 'gorsel_h': gh,
                             'y': {'ust_ad': ad_y, 'ust_oyun': oyun_y, 'alt_kaynak': kaynak_y,
                                   'alt_marka': marka_y}}, aciklama)


def aciklama_katmani(aciklama: dict, metinler: dict[str, str], duzen: dict = DUZEN):
    """Açıklamalı klibin TÜM yazılarını (açıklama etiketi, yayıncı adı · oyun, kaynak, marka) tek şeffaf RGBA katmanına
    çizer (1080x1920, PIL; ffmpeg yazı tipi/drawtext kaçışı gerekmez, Linux'ta da aynı). Etiket ve metin 2x çizilip
    küçültülür (yumuşak kenar); gölge 1x çizilip bulanıklaştırılır. Stil: A dolu sarı etiket + lacivert yazı,
    B koyu yarı saydam etiket + sarı çerçeve, beyaz yazı + sarı ad, C zeminsiz: kalın siyah kontur + gölge, beyaz/sarı."""
    try:
        from PIL import Image, ImageDraw, ImageFilter, ImageFont
    except ImportError as e:
        raise KlipHatasi('açıklama yazısı için Pillow gerekli: py -m pip install --user pillow') from e
    c = duzen['aciklama']
    W, H, k = duzen['genislik'], duzen['yukseklik'], 2
    stil, fyol = aciklama['stil'], aciklama['font']
    beyaz, gri = (255, 255, 255, 255), (204, 204, 204, 255)
    sari, lacivert = (*MARKA_SARI, 255), (*MARKA_LACIVERT, 255)
    golge = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    ust = Image.new('RGBA', (W * k, H * k), (0, 0, 0, 0))
    dg, du = ImageDraw.Draw(golge), ImageDraw.Draw(ust)

    def font(boyut: int, kat: int = k):
        return ImageFont.truetype(fyol, boyut * kat)

    def yaz(x: float, taban: float, parca: list, boyut: int, kontur: int, golge_oteleme: int,
            golge_alfa: int = 190) -> None:
        """parca = [(metin, renk)] soldan sağa; x = ilk parçanın sol kenarı, taban = taban çizgisi (1x px)."""
        f1, f2 = font(boyut, 1), font(boyut)
        for metin, renk in parca:
            if kontur or golge_oteleme:
                dg.text((x, taban + golge_oteleme), metin, font=f1, fill=(0, 0, 0, golge_alfa), anchor='ls',
                        stroke_width=kontur, stroke_fill=(0, 0, 0, golge_alfa))
            du.text((x * k, taban * k), metin, font=f2, fill=renk, anchor='ls',
                    stroke_width=kontur * k, stroke_fill=(0, 0, 0, 255) if kontur else None)
            x += f2.getlength(metin) / k

    # -- açıklama etiketleri
    for i, (satir, (x0, y0, x1, y1), taban) in enumerate(zip(aciklama['satirlar'], aciklama['kutular'], aciklama['taban'])):
        if stil == 'A':
            dg.rounded_rectangle((x0, y0 + 8, x1, y1 + 8), radius=c['yaricap'], fill=(0, 0, 0, 150))
            du.rounded_rectangle((x0 * k, y0 * k, x1 * k, y1 * k), radius=c['yaricap'] * k, fill=sari)
            parca = [(satir, lacivert)]
        elif stil == 'B':
            dg.rounded_rectangle((x0, y0 + 8, x1, y1 + 8), radius=c['yaricap'], fill=(0, 0, 0, 150))
            du.rounded_rectangle((x0 * k, y0 * k, x1 * k, y1 * k), radius=c['yaricap'] * k, fill=(*MARKA_LACIVERT, 214),
                                 outline=sari, width=3 * k)
            parca = [(satir, beyaz)]
        else:
            parca = [(satir, beyaz)]
        if stil != 'A' and i == 0:   # ilk kelime (açıklamanın öznesi) sarı
            ilk, _, kalan = satir.partition(' ')
            parca = [(ilk + ' ', sari)] + ([(kalan, beyaz)] if kalan else [])
        yaz(x0 + c['pad_x'], taban, parca, aciklama['boyut'], kontur=9 if stil == 'C' else 0,
            golge_oteleme=8 if stil == 'C' else 0, golge_alfa=215)

    # -- altta: yayıncı adı · oyun, kaynak, marka (kontur + gölge, zeminsiz)
    azami = duzen['metin_azami_px']

    def alt_satir(ad: str, parcalar: list) -> None:
        a = aciklama['alt_satirlar'][ad]
        boyut = a['boyut']
        while boyut > 20 and sum(font(boyut, 1).getlength(m) for m, _ in parcalar) > azami:
            boyut -= 2
        w = sum(font(boyut, 1).getlength(m) for m, _ in parcalar)
        yaz((W - w) / 2, a['y'] + int(boyut * 1.1), parcalar, boyut, kontur=5, golge_oteleme=4, golge_alfa=170)

    ad_parca = [(metinler['ad'], beyaz)]
    if aciklama['oyun_var'] and metinler.get('oyun'):
        ad_parca += [('  \u00b7  ', gri), (metinler['oyun'], sari)]
    alt_satir('ad_oyun', ad_parca)
    alt_satir('kaynak', [(metinler['kaynak'], beyaz)])
    alt_satir('marka', [(metinler['marka'], gri)])

    golge = golge.filter(ImageFilter.GaussianBlur(6))
    ust = ust.resize((W, H), Image.LANCZOS)
    return Image.alpha_composite(golge, ust)


def filtre_yaz(font: str, metinler: dict[str, str], duzen: dict = DUZEN, ayar: dict | None = None,
               aciklama: dict | None = None) -> str:
    """filter_complex betiği. Metinler çalışma klasöründe t_<ad>.txt dosyalarından okunur (kaçış derdi yok)."""
    w, h = duzen['genislik'], duzen['yukseklik']
    kucuk_w = w // 4
    kucuk_h = h // 4
    yz = yerlesim(ayar, duzen, aciklama)
    if yz['mod'] == 'kamera':
        return _kamera_filtresi(font, metinler, duzen, ayar, aciklama, yz)
    if yz['mod'] == 'serit':
        on = f"scale={w}:-2:flags=lanczos"
    else:
        r = f"{yz['oran']:.4f}"
        # Ortadan kırp: kaynak hedeften darsa yükseklikten değil genişlikten kırpılır (min ile).
        mx = (ayar or {}).get('_kamera_merkez_x')
        # tek büyük yüz varsa kırpma merkezi yüze kayar (yüz kesilmesin); yoksa ortadan (eski çıktı birebir)
        konum = f":x=min(max({float(mx):.4f}*iw-out_w/2\\,0)\\,iw-out_w):y=(ih-out_h)/2" if mx is not None else ''
        on = (f"crop=w=min(iw\\,ih*{r}):h=min(ih\\,iw/{r}){konum},"
              f"scale={w}:{yz['gorsel_h']}:flags=lanczos")
    satirlar = [
        f"[0:v:0]fps={duzen['fps']},split=2[a][b]",
        f"[a]scale=-2:{kucuk_h},crop={kucuk_w}:{kucuk_h},gblur=sigma={duzen['arka_blur']},"
        f"scale={w}:{h},eq=brightness={duzen['arka_parlaklik']}:saturation=0.9[bg]",
        f"[b]{on}[fg]",
        f"[bg][fg]overlay=0:{yz['gorsel_y']}[v0]",
    ]
    return _yazilari_ekle(satirlar, font, metinler, duzen, aciklama, yz)


def _yazilari_ekle(satirlar: list[str], font: str, metinler: dict[str, str], duzen: dict, aciklama: dict | None,
                   yz: dict) -> str:
    """Süzgeç zincirinin sonu: [v0] üstüne yazılar (PNG katmanı ya da drawtext) ve [v] çıkışı."""
    if aciklama:   # tüm yazılar ikinci girdideki PNG katmanında (aciklama_katmani); drawtext yok
        satirlar.append('[v0][1:v:0]overlay=0:0:format=auto,setsar=1,format=yuv420p[v]')
        return ';\n'.join(satirlar) + '\n'
    cizim = []
    for ad, bolum, renk in (('ad', 'ust_ad', 'white'), ('oyun', 'ust_oyun', '0xFFD54A'),
                            ('kaynak', 'alt_kaynak', 'white'), ('marka', 'alt_marka', '0xCCCCCC')):
        b = duzen[bolum]
        boyut = metin_boyutu(metinler[ad], yz.get('boyut', {}).get(bolum, b['boyut']), duzen['metin_azami_px'])
        cizim.append(
            f"drawtext=fontfile='{_fe(font)}':textfile='t_{ad}.txt':fontsize={boyut}:fontcolor={renk}:"
            f"borderw=4:bordercolor=black@0.85:x=(w-text_w)/2:y={yz['y'][bolum]}"
        )
    satirlar.append('[v0]' + ','.join(cizim) + ',setsar=1,format=yuv420p[v]')
    return ';\n'.join(satirlar) + '\n'


def _kirpma_ifadesi(k: tuple, w: int, h: int) -> str:
    """Oransal (x,y,w,h) kutusu için ffmpeg crop ifadesi (konum ve boyut çift piksele indirilir)."""
    return (f"crop=w=trunc(iw*{k[2]:.5f}/2)*2:h=trunc(ih*{k[3]:.5f}/2)*2:"
            f"x=trunc(iw*{k[0]:.5f}/2)*2:y=trunc(ih*{k[1]:.5f}/2)*2,scale={w}:{h}:flags=lanczos")


def _kamera_filtresi(font: str, metinler: dict[str, str], duzen: dict, ayar: dict | None, aciklama: dict | None,
                     yz: dict) -> str:
    """'kamera' düzeni: kaynak üçe bölünür (bulanık arka plan, içerik paneli, kamera paneli)."""
    w, h = duzen['genislik'], duzen['yukseklik']
    plan = (ayar or {}).get('_kamera_plan')
    if not plan or plan.get('duzen') != 'kamera':
        raise KlipHatasi("'kamera' düzeni için kamera planı yok (klip_kes önce kamerayı bulmalı)")
    ic, km = yz['paneller']['icerik'], yz['paneller']['kamera']
    satirlar = [
        f"[0:v:0]fps={duzen['fps']},split=3[a][b][c]",
        f"[a]scale=-2:{h // 4},crop={w // 4}:{h // 4},gblur=sigma={duzen['arka_blur']},"
        f"scale={w}:{h},eq=brightness={duzen['arka_parlaklik']}:saturation=0.9[bg]",
        f"[b]{_kirpma_ifadesi(tuple(plan['icerik_kirpma']), w, ic['h'])}[ic]",
        f"[c]{_kirpma_ifadesi(tuple(plan['kamera_kirpma']), w, km['h'])}[km]",
        f"[bg][ic]overlay=0:{ic['y']}[v1]",
        f"[v1][km]overlay=0:{km['y']}[v0]",
    ]
    return _yazilari_ekle(satirlar, font, metinler, duzen, aciklama, yz)


def klip_metinleri(vod: dict, aciklama: dict | None = None, ayar: dict | None = None) -> dict[str, str]:
    m = {
        'ad': vod['yayinci'],
        'oyun': vod.get('oyun') or '',
        'kaynak': (f"Kaynak: kick.com/{vod['kanal']}" if vod['platform'] == 'kick' else
                   f"Kaynak: youtube.com/@{vod['kanal']}" if vod['platform'] == 'youtube' else f"Kaynak: {vod['kanal_url']}"),
        'marka': marka_yazisi(ayar),
    }
    for i, satir in enumerate((aciklama or {}).get('satirlar', [])):
        m[f'aciklama{i + 1}'] = satir
    return m


def ffmpeg_komutu(ff: str, kaynak: str, bas: float, sure: float, cikti: str, filtre: str,
                  yerel_hls: bool = False, katman: str | None = None) -> list[str]:
    # -filter_complex_script ffmpeg 7+'da kalktı, -/filter_complex 6'da yok: süzgeç (~1 KB) argüman olarak verilir.
    return [ff, '-hide_banner', '-loglevel', 'error', '-y',
            *(['-protocol_whitelist', 'file,http,https,tcp,tls,crypto'] if yerel_hls else []),
            # katman (PNG) kaynağın hemen ardından gelir: yerel_hls'te sonraki -ss çıkış seçeneği kalır, PNG'yi kaydırmaz
            *(['-i', kaynak, *(['-i', katman] if katman else []), '-ss', f'{bas:.3f}'] if yerel_hls else
              ['-ss', f'{bas:.3f}', '-i', kaynak, *(['-i', katman] if katman else [])]),
            '-t', f'{sure:.3f}',
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


def kamera_karari(vod: dict, ayar: dict, ff: str, kaynak: str, bas: float, sure: float, yerel: bool) -> tuple[dict, dict]:
    """'kamera' düzeni için klip başına bir kez kamera bulur. Dönüş: (etkin ayar, plan özeti). Etkin ayarda duzen
    'kamera' (plan '_kamera_plan'da) ya da tek panel ('kadraj'; tek büyük yüz varsa '_kamera_merkez_x'). Herhangi bir
    hata (model yok, kare alınamadı, OpenCV) güvenli tarafa düşer: eski tek panel; neden 'hata' + metin plana yazılır."""
    pn = yerlesim({**ayar, 'duzen': 'kamera'})['paneller']
    kadraj = {**ayar, 'duzen': 'kadraj'}
    try:
        plan = klip_kamera.kamera_bul(ff, kaynak, bas, sure, yerel, ayar, vod.get('kamera_kutu'))
        plan = klip_kamera.kesim_plani(plan, plan['kare_oran'], pn['icerik']['oran'], pn['kamera']['oran'],
                                       min(max(float(ayar.get('kadraj_oran', AYAR_VARSAYILAN['kadraj_oran'])),
                                               KADRAJ_EN_AZ), KAYNAK_ORAN), ayar)
    except Exception as e:   # noqa: BLE001 - kamera bulma yardımcıdır: her hatada eski düzenle kesilir
        return kadraj, {'duzen': 'tek', 'neden': 'hata', 'hata': f'{type(e).__name__}: {e}'[:300]}
    if plan['duzen'] == 'kamera':
        return {**ayar, 'duzen': 'kamera', '_kamera_plan': plan}, plan
    return ({**kadraj, '_kamera_merkez_x': plan['merkez_x']} if 'merkez_x' in plan else kadraj), plan


def klip_zenginlestir(vod: dict, klip: dict, ayar: dict | None, ff: str, kaynak: str, bas_t: float, sure: float,
                      yerel: bool, tmp_yol: pathlib.Path) -> dict:
    """(A) Yayın kategorisi klibin karelerine göre doğrulanır: dönen vod'da 'oyun' doğrulanmış ad ya da None.
    (B) Dökümü olmayan klip için klibin kendi sesi yazıya çevrilir, kisa_aciklama + başlık üretilir.
    Sonuçlar klip['oyun_dogrulama'] / klip['ses_yargisi'] (paket_json pakete yazar), metin alanları klibe işlenir.
    Test/özelleştirme kancaları ayarda: _oyun_sor, _ses_dok, _ses_yargi_modeli. Hata = güvenli taraf (ad/metin yok)."""
    ayar = ayar or {}
    aralik = [klip['klip_baslangic_sn'], klip['klip_baslangic_sn'] + sure]
    if ayar.get('klip_oyun_dogrula', True) or klip.get('oyun_elle') is not None:
        karar = klip_oyun.oyun_karari(
            vod.get('oyun'), aralik,
            lambda: klip_kamera.kareleri_ornekle(ff, kaynak, bas_t, sure, yerel, klip_oyun.KARE_SAYISI,
                                                 klip_oyun.KARE_GENISLIK, tmp_yol / 'oyunkare'),
            elle=klip.get('oyun_elle'), onbellek=klip.get('oyun_dogrulama'), sor=ayar.get('_oyun_sor'),
            tmp=tmp_yol / 'oyun')
        klip['oyun_dogrulama'] = karar
        vod = {**vod, 'oyun': karar['oyun']}
    if ayar.get('klip_ses_yargisi', True) and not str(klip.get('dokum_metni') or '').strip():
        elle_metin = klip.get('aciklama_elle')
        s = klip.get('ses_yargisi')
        if not klip_oyun.ses_onbellek_gecerli(s, aralik):
            try:
                wav = tmp_yol / 'klip-ses.wav'
                klip_oyun.ses_cikar(ff, kaynak, bas_t, sure, yerel, wav)
                s = klip_oyun.ses_yargisi(aralik, vod.get('kisa_ad') or vod['yayinci'], wav, tmp_yol / 'ses', ayar,
                                          yargi=not elle_metin, model=ayar.get('_ses_yargi_modeli'),
                                          dok=ayar.get('_ses_dok'))
            except Exception as e:   # noqa: BLE001 - metin üretimi yardımcıdır; hata = şablon metin
                s = {'durum': 'hata', 'kaynak': 'klip-sesi-whisper', 'aralik': aralik, 'hata': f'{type(e).__name__}: {e}'[:300]}
        klip['ses_yargisi'] = s
        if s.get('dokum'):
            klip['dokum_metni'] = s['dokum']
        if s.get('durum') == 'tamam' and s.get('kisa_aciklama') and not elle_metin:
            klip['konusma_kisa_aciklama'] = s['kisa_aciklama']
            klip['konusma_baslik'] = s.get('baslik') or s['kisa_aciklama']
    return vod


def klip_kes(vod: dict, klip: dict, hedef: pathlib.Path, ff: str, font: str, ayar: dict | None = None) -> dict:
    """Yalnız klip aralığını HLS'ten çeker ve 1080x1920 H.264+AAC olarak yazar. ayar: duzen, kadraj_oran."""
    kaynak = vod.get('hls') or vod['kaynak']
    sure = min(klip['klip_bitis_sn'], vod['sure_sn']) - klip['klip_baslangic_sn']
    hedef.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='klip-') as tmp:
        tmp_yol = pathlib.Path(tmp)
        gecici = tmp_yol / 'cikti.mp4'
        bas, yerel = klip['klip_baslangic_sn'], False
        plan_bas = bas
        hizalar = []
        bolumler, origin = None, 0.0
        youtube_indirme = None
        if vod['platform'] == 'youtube':
            origin = max(0, bas-6)
            try:
                media, youtube_indirme = klip_youtube.bolum_indir(vod, origin,
                    min(vod['sure_sn'], bas+sure+6), tmp_yol/'youtube.mkv', ff)
            except (OSError, RuntimeError, ValueError) as e:
                raise KlipHatasi(f'YouTube kesit indirilemedi: {e}') from e
            kaynak, yerel = str(media), True
        elif (ayar or {}).get('konusma'):
            try:
                bolumler = klip_konusma.hls_bolumleri(kaynak, http_metin(kaynak))
                playlist = tmp_yol / 'klip.m3u8'
                # Aynı yerel listenin başlangıcı düzeltme denemeleri arasında sabit kalsın.
                pre = max(0, bas-5)
                try:
                    seek = klip_konusma.hls_pencere(bolumler, pre, min(vod['sure_sn'],bas+sure+5), playlist)
                except RuntimeError:
                    pre = bas
                    seek = klip_konusma.hls_pencere(bolumler, pre, pre+sure, playlist)
                origin = pre-seek
                kaynak, yerel = str(playlist), True
            except (RuntimeError, ValueError) as e:
                raise KlipHatasi(f'klip HLS zamanlaması: {e}') from e
        # Kamera bulma klip başına BİR kez, kesimden önce (yerel kaynakta zaman çizgisi bas-origin). Sonuca göre etkin
        # düzen belli olur ('kamera' ya da tek panel); açıklama/yazı yerleşimi bundan sonra, etkin düzenle hesaplanır.
        kamera_bilgisi = None
        ayar_k = ayar
        if (ayar or {}).get('duzen', AYAR_VARSAYILAN['duzen']) == 'kamera':
            ayar_k, kamera_bilgisi = kamera_karari(vod, ayar or {}, ff, kaynak, bas-origin if yerel else bas, sure, yerel)
        # (A) oyun adı doğrulaması ve (B) dökümsüz klibin kendi sesinden metin: kesimden önce (yazı videoya yanar).
        vod = klip_zenginlestir(vod, klip, ayar, ff, kaynak, bas-origin if yerel else bas, sure, yerel, tmp_yol)
        aciklama_metni = klip_aciklamasi(klip, ayar)
        aciklama = aciklama_duzeni(aciklama_metni, aciklama_fontu(), ayar_k, oyun_var=bool(vod.get('oyun')))
        metinler = klip_metinleri(vod, aciklama, ayar)
        for ad, m in metinler.items():
            (tmp_yol / f't_{ad}.txt').write_text(m or ' ', encoding='utf-8')
        katman = None
        if aciklama:
            aciklama_katmani(aciklama, metinler).save(tmp_yol / 'katman.png')
            katman = 'katman.png'
        aligned = False
        for attempt in range(4):
            if bas < 0 or bas+sure > vod['sure_sn']+.01:
                raise KlipHatasi('ses hizası düzeltmesi videonun dışına taşıyor')
            if bolumler:
                try:
                    klip_konusma.hls_pencere(bolumler, bas, bas+sure, tmp_yol/'kontrol.m3u8')
                except RuntimeError as e:
                    raise KlipHatasi(str(e)) from e
            r = subprocess.run(ffmpeg_komutu(ff, kaynak, bas-origin if yerel else bas, sure, gecici.name,
                                             filtre_yaz(font, metinler, ayar=ayar_k, aciklama=aciklama), yerel, katman),
                               cwd=tmp, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=1200)
            if r.returncode != 0 or not gecici.exists():
                raise KlipHatasi(f'ffmpeg başarısız ({r.returncode}): {r.stderr[-800:]}')
            temp_info = klip_dogrula(ff, gecici)
            if abs(temp_info['sure_sn']-sure) > .15:
                raise KlipHatasi(f"yarım klip reddedildi: {temp_info['sure_sn']}/{sure:.3f} sn")
            ref = klip.get('konusma_ses_referansi')
            if not ref:
                aligned = True
                break
            ses = tmp_yol/'hiza.wav'
            r = subprocess.run([ff, '-hide_banner', '-loglevel', 'error', '-y', '-i', str(gecici),
                                '-t', '15', '-vn', '-ar', '16000', '-ac', '1', str(ses)], capture_output=True, timeout=60)
            if r.returncode:
                raise KlipHatasi('klibin hizalama sesi okunamadı')
            try:
                hiza = klip_konusma.dalga_hizasi(ref['dosya'], ses, ref['hedef_bas_sn']-ref['bas_sn'])
            except (OSError, RuntimeError, ValueError) as e:
                raise KlipHatasi(f'konuşma ses hizası: {e}') from e
            hizalar.append({**hiza, 'uc': 'bas'})
            if hiza['korelasyon'] < .70:
                raise KlipHatasi(f'konuşma sesi güvenle eşleşmedi: {hiza}')
            if abs(hiza['ofset_sn']) > .12:
                bas = round(bas-hiza['ofset_sn'], 4)
                continue
            end_ref = klip.get('konusma_son_ses_referansi')
            if end_ref:
                tail = tmp_yol/'hiza-son.wav'
                r = subprocess.run([ff,'-hide_banner','-loglevel','error','-y','-i',str(gecici),
                    '-ss',str(sure-10),'-t','10','-vn','-ar','16000','-ac','1',str(tail)],
                    capture_output=True,timeout=60)
                if r.returncode:
                    raise KlipHatasi('klibin son hizalama sesi okunamadı')
                try:
                    end = klip_konusma.dalga_hizasi(end_ref['dosya'],tail,
                        end_ref['hedef_bitis_sn']-10-end_ref['bas_sn'])
                except (OSError,RuntimeError,ValueError) as e:
                    raise KlipHatasi(f'konuşma sonu ses hizası: {e}') from e
                hizalar.append({**end,'uc':'son'})
                if end['korelasyon'] < .70:
                    raise KlipHatasi(f'konuşma sonu güvenle eşleşmedi: {end}')
                if abs(end['ofset_sn']) > .12:
                    sure = round(sure-end['ofset_sn'],4)
                    if not 30 <= sure <= 59:
                        raise KlipHatasi('hizalanmış konuşma 30–59 sn aralığına sığmıyor')
                    continue
            aligned = True
            break
        if not aligned:
            raise KlipHatasi(f'konuşma sesi dört denemede hizalanmadı: {hizalar}')
        if araliklar_orter(bas, bas+sure, klip.get('_engelli')):
            raise KlipHatasi('hizalanmış klip daha önce kesilmiş aralıkla örtüşüyor')
        if hizalar:
            klip['konusma_plan_araligi'] = klip.get('konusma_plan_araligi', [plan_bas, plan_bas+sure])
            klip['klip_baslangic_sn'], klip['klip_bitis_sn'] = round(bas,3), round(bas+sure,3)
            klip['sure_sn'] = round(sure,3)
        shutil.move(str(gecici), str(hedef))
    bilgi = klip_dogrula(ff, hedef)
    if hizalar:
        bilgi['ses_hizasi'] = {'denemeler': hizalar, 'kaydirma_sn': round(bas-plan_bas,4)}
    if youtube_indirme:
        bilgi['youtube_indirme'] = youtube_indirme
    if kamera_bilgisi:
        bilgi['kamera'] = kamera_bilgisi
    if aciklama_metni:
        bilgi['aciklama_yazisi'] = ({'metin': aciklama_metni, 'satirlar': aciklama['satirlar'],
                                     'boyut': aciklama['boyut'], 'y': aciklama['y'], 'stil': aciklama['stil'],
                                     'yazi_tipi': pathlib.Path(aciklama['font']).name} if aciklama else
                                    {'metin': aciklama_metni, 'yazilmadi': 'üst bölgeye sığmadı'})
    return bilgi


# ---------------------------------------------------------------- akış

def vod_hazirla(arguman: str, ayar: dict, http=http_json, http_text=http_metin) -> tuple[dict, dict]:
    vid = klip_youtube.video_id(arguman)
    if vid:
        try:
            info = klip_youtube.bilgi(f'https://www.youtube.com/watch?v={vid}')
            vod = klip_youtube.normalle(info, ayar)
            y, c = klip_youtube.yayinci(ayar, vod['kanal_id'])
            cfg = {**klip_youtube.AYAR, **(y['ayar'] if y else ayar['ayar']),
                   'konusma': True, 'bas_dislama_sn': 0, 'son_dislama_sn': 0,
                   **((c or {}).get('ayar') or {})}
            reason = klip_youtube.atlama_nedeni(info, cfg, tarih_suz=False)
            if reason:
                raise KlipHatasi(f'YouTube video atlandı: {reason}')
            vod['_youtube_bilgi'] = info
            vod['kisa_ad'] = (y or {}).get('kisa_ad')
            vod['kamera_kutu'] = (y or {}).get('kamera_kutu')
            return vod, cfg
        except (OSError, RuntimeError, ValueError) as e:
            raise KlipHatasi(str(e)) from e
    uuid, ipucu = vod_coz(arguman)
    vod = kick_vod_bilgi(uuid, ipucu, ayar, http)
    if vod['canli']:
        raise KlipHatasi('yayın hâlâ sürüyor; bittikten sonra işlenir')
    y = yayinci_bul(ayar, 'kick', vod['kanal'])
    vod_t0_ekle(vod, http_text)
    vod['kisa_ad'] = (y or {}).get('kisa_ad')
    vod['kamera_kutu'] = (y or {}).get('kamera_kutu')   # elle kamera kutusu (oransal x,y,w,h); tespiti ezer
    return vod, (y['ayar'] if y else dict(ayar['ayar']))


def gorselsiz(ayar: dict | None) -> dict | None:
    """Analiz önbelleği karşılaştırması için yalnız görünümü etkileyen ayarlar atılır (GORSEL_AYAR)."""
    return {k: v for k, v in ayar.items() if k not in GORSEL_AYAR} if isinstance(ayar, dict) else ayar


def analiz_komutu(arguman: str, dizin: pathlib.Path, ayar: dict, gecersiz: dict | None = None,
                  yeniden: bool = False, suzgecsiz: bool = False) -> tuple[dict, dict]:
    vod, vayar = vod_hazirla(arguman, ayar)
    vayar = {**vayar, **(gecersiz or {})}
    uygun, _ = oyun_suzgeci(vod, vayar)
    if not uygun and not suzgecsiz:
        raise KlipHatasi(f"yayın oyun süzgecine uymuyor (kategori: {', '.join(vod['kategoriler']) or '-'}; "
                         f"başlık: {vod['baslik'][:50]}); yine de işlemek için --suzgecsiz")
    yol = dizin / 'analiz' / f"{vod['platform']}-{vod['vod_id']}.json"
    if yol.exists() and not yeniden:
        sonuc = json.loads(yol.read_text(encoding='utf-8'))
        if gorselsiz(sonuc.get('ayar')) == gorselsiz(vayar) and (not vayar.get('konusma') or
                (sonuc.get('konusma', {}).get('durum') == 'açık' and
                 sonuc.get('konusma_surumu') == klip_konusma.SURUM)):
            sonuc['ayar'] = vayar   # görünüm ayarı (açıklama yazısı vb.) bu çalıştırmanınki; diske yazılmaz
            return vod, sonuc
    def ilerleme(a, b):
        print(f'  sohbet: {a}/{b} pencere', file=sys.stderr, flush=True)
    if vod['platform'] == 'youtube':
        info = vod.pop('_youtube_bilgi')
        try:
            sonuc = klip_youtube.analiz(vod, info, dizin, vayar, ffmpeg_bul(), http_metin)
        except (OSError, RuntimeError, ValueError) as e:
            raise KlipHatasi(f'YouTube analiz: {e}') from e
        klip_konusma.json_yaz(yol, sonuc)
        durum_isaretle(dizin, vod['anahtar'], durum='analiz', yayinci=vod['yayinci'], klip=len(sonuc['klipler']))
        return vod, sonuc
    mesajlar = sohbet_al(vod, dizin, ilerleme=ilerleme)
    konusma_acik = vayar.get('konusma') and vayar['yontem'] == 'sinyal'
    sonuc = analiz_et(vod, mesajlar, {**vayar, 'azami_klip': max(vayar['azami_klip'],
                        vayar['konusma_aday_sayisi'])} if konusma_acik else vayar)
    if konusma_acik:
        try:
            sonuc['klipler'], sonuc['konusma'] = klip_konusma.katman(
                vod, sonuc['klipler'], dizin, vayar, ffmpeg_bul(), http_metin)
        except (KlipHatasi, klip_konusma.ModelKotasi) as e:
            sonuc['klipler'] = klip_konusma.son_secim(sonuc['klipler'], vayar)
            sonuc['konusma'] = {'durum': 'konuşma katmanı kapalı', 'neden': str(e)}
        print(f"  {sonuc['konusma']['durum']}: {sonuc['konusma'].get('neden', '')}", file=sys.stderr, flush=True)
    else:
        sonuc['konusma'] = {'durum': 'konuşma katmanı kapalı'}
    sonuc['ayar'] = vayar
    sonuc['konusma_surumu'] = klip_konusma.SURUM
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(json.dumps(sonuc, ensure_ascii=False, indent=1), encoding='utf-8')
    durum_isaretle(dizin, vod['anahtar'], durum='analiz', yayinci=vod['yayinci'], klip=len(sonuc['klipler']))
    return vod, sonuc


def klip_aciklamasi(klip: dict, ayar: dict | None = None) -> str | None:
    """Klibe yazılacak kısa açıklama: konuşma yargısından gelen konusma_kisa_aciklama, yeniden doğrulanmış.
    Ayarda klip_aciklama_yazi=false (ya da --aciklamasiz) ise None: eski, yazısız görünüm."""
    ayar = ayar or {}
    if ayar.get('klip_aciklama_yazi') is False:
        return None
    return klip_konusma.kisa_aciklama_dogrula(klip.get('konusma_kisa_aciklama') or klip.get('kisa_aciklama'), ayar)


def duzen_imzasi(ayar: dict, aciklama: str | None = None) -> dict:
    """Görünüm imzası; açıklama yazılacaksa metni de girer (açıklama ya da düzen değişince klip yeniden üretilir).
    Açıklamasız klipte imza eskisiyle birebir aynıdır."""
    yz = yerlesim(ayar)
    return {'duzen': yz['mod'], 'kadraj_oran': yz['oran'],
            **({'kamera_surumu': klip_kamera.KAMERA_SURUMU} if yz['mod'] == 'kamera' else {}),
            **({'konusma_saat_surumu': 3} if ayar.get('konusma') else {}),
            **({'aciklama': aciklama, 'aciklama_stil': aciklama_stili(ayar),
                'aciklama_tasarim': ACIKLAMA_TASARIM_SURUMU} if aciklama else {}),
            # marka yazısı videoya yanar: eski sabitten başkaysa imzaya girer (marka değişince klip 'güncel değil' olur)
            **({'marka': marka_yazisi(ayar)} if marka_yazisi(ayar) != marka_yazisi({}) else {})}


def paket_guncel(paket: pathlib.Path, klip: dict, ayar: dict) -> bool:
    """Var olan klip bu analizin bu zirvesi ve bu düzenle mi üretilmiş? Değilse yeniden üretilir."""
    try:
        eski = json.loads(paket.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return False
    if klip.get('konusma_plan_araligi'):
        return eski.get('konusma_plan_araligi') == klip['konusma_plan_araligi'] and eski.get('duzen') == duzen_imzasi(ayar, klip_aciklamasi(klip, ayar))
    return (eski.get('klip_baslangic_sn') == klip['klip_baslangic_sn']
            and eski.get('klip_bitis_sn') == klip['klip_bitis_sn']
            and eski.get('duzen') == duzen_imzasi(ayar, klip_aciklamasi(klip, ayar)))


def kes_komutu(arguman: str, dizin: pathlib.Path, ayar: dict, gecersiz: dict | None = None,
               zorla: bool = False, yeniden: bool = False, suzgecsiz: bool = False) -> list[pathlib.Path]:
    vod, sonuc = analiz_komutu(arguman, dizin, ayar, gecersiz, yeniden, suzgecsiz)
    vayar = sonuc['ayar']
    ff, font = ffmpeg_bul(), font_bul()
    cikti_dizini = dizin / 'cikti' / f"{dosya_adi(vod['yayinci'])}-{vod['tarih'].replace('-', '')}-{vod['vod_id'][:8]}"
    uretilen = []
    canli_engel = canli_aralik_listesi(durum_oku(dizin)['vod'].get(vod['anahtar'], {}), vod['t0_epoch'])
    for klip in sonuc['klipler']:
        tekrar = klip_youtube.metin_tekrar(klip, vod, dizin)
        if tekrar:
            sonuc.setdefault('kesimde_elenen', []).append({'zirve_sn': klip['zirve_sn'],
                'neden': 'çift kaynak döküm eşleşmesi', 'paket': tekrar})
            continue
        if araliklar_orter(klip['klip_baslangic_sn'], klip['klip_bitis_sn'], canli_engel):
            print(f"  klip {klip['no']}: yayın sürerken zaten kesilmiş (canli-*.mp4), atlandı", file=sys.stderr, flush=True)
            continue
        mp4 = cikti_dizini / f"klip-{klip['no']:02d}.mp4"
        paket = mp4.with_suffix('.json')
        if mp4.exists() and paket_guncel(paket, klip, vayar) and not zorla:
            if klip.get('konusma_puani') is not None:
                # Aralık aynı kalsa da yeni içerik yargısı/başlık pakete yansısın.
                bilgi = klip_dogrula(ff, mp4)
                eski = json.loads(paket.read_text(encoding='utf-8'))
                klip['klip_baslangic_sn'], klip['klip_bitis_sn'] = eski['klip_baslangic_sn'], eski['klip_bitis_sn']
                if eski.get('video', {}).get('ses_hizasi'):
                    bilgi['ses_hizasi'] = eski['video']['ses_hizasi']
                if eski.get('video', {}).get('aciklama_yazisi'):
                    bilgi['aciklama_yazisi'] = eski['video']['aciklama_yazisi']
                for anahtar in ('oyun_dogrulama', 'ses_yargisi'):
                    if isinstance(eski.get(anahtar), dict):
                        klip[anahtar] = eski[anahtar]
                paket.write_text(json.dumps(paket_json(vod, klip, mp4, bilgi, vayar),
                                             ensure_ascii=False, indent=2), encoding='utf-8')
            uretilen.append(mp4)
            canli_engel.append((klip['klip_baslangic_sn'], klip['klip_bitis_sn']))
            continue
        print(f"  klip {klip['no']}: {zaman_metni(klip['klip_baslangic_sn'])}–{zaman_metni(klip['klip_bitis_sn'])}", file=sys.stderr, flush=True)
        klip['_engelli'] = canli_engel
        try:
            bilgi = klip_kes(vod, klip, mp4, ff, font, vayar)
        except KlipHatasi as e:
            if not vayar.get('konusma'):
                raise
            sonuc.setdefault('kesimde_elenen', []).append({'zirve_sn':klip['zirve_sn'],'neden':str(e)})
            print(f"  klip {klip['no']} elendi: {e}",file=sys.stderr,flush=True)
            continue
        paket.write_text(json.dumps(paket_json(vod, klip, mp4, bilgi, vayar), ensure_ascii=False, indent=2), encoding='utf-8')
        uretilen.append(mp4)
        canli_engel.append((klip['klip_baslangic_sn'], klip['klip_bitis_sn']))
    # Yeni analiz daha az klip verdiyse eski numaralı artıkları sil değil, eski/ klasörüne taşı.
    for artik in sorted(cikti_dizini.glob('klip-*.*')) if cikti_dizini.exists() else []:
        m = re.match(r'klip-(\d+)\.(mp4|json)$', artik.name)
        if m and int(m.group(1)) > len(sonuc['klipler']):
            (cikti_dizini / 'eski').mkdir(exist_ok=True)
            artik.replace(cikti_dizini / 'eski' / artik.name)
    durum_isaretle(dizin, vod['anahtar'], durum=('kesim_hatasi' if not uretilen and sonuc.get('kesimde_elenen') else 'islendi'),
                   yayinci=vod['yayinci'], klip=len(uretilen),
                   cikti=str(cikti_dizini))
    if vayar.get('konusma'):
        for k in sonuc['klipler']:
            k.pop('_engelli', None)
        (dizin/'analiz').mkdir(parents=True,exist_ok=True)
        (dizin/'analiz'/f"{vod['platform']}-{vod['vod_id']}.json").write_text(
            json.dumps(sonuc,ensure_ascii=False,indent=1),encoding='utf-8')
    return uretilen


def tara(ayar: dict, dizin: pathlib.Path, yayinci: str | None = None, hepsi: bool = False,
         http=http_json, simdi: float | None = None) -> dict:
    """Etkin yayıncıların son biten yayınları; işlenmişler atlanır. Desteklenmeyen platform ayrı raporlanır."""
    durum = durum_oku(dizin)
    simdi = simdi if simdi is not None else time.time()
    bulunan, atlanan, desteksiz, hatalar, suzgece_uymayan = [], [], [], [], []
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
            uygun, eslesen = oyun_suzgeci(v, y['ayar'])
            if not uygun:
                suzgece_uymayan.append({k: satir[k] for k in ('yayinci', 'anahtar', 'tarih', 'oyun', 'baslik')})
                continue
            if eslesen:
                satir['eslesen_oyun'] = eslesen
            if islendi_mi(durum, v['anahtar']) and not hepsi:
                atlanan.append(v['anahtar'])
            else:
                bulunan.append(satir)
    yt = klip_youtube.tara(ayar, dizin, yayinci, hepsi, simdi)
    return {'yeni': bulunan + yt['yeni'], 'atlanan_islenmis': atlanan + yt['atlanan_islenmis'],
            'suzgece_uymayan': suzgece_uymayan, 'desteksiz': desteksiz, 'hata': hatalar + yt['hata'],
            'youtube_atlanan': yt['youtube_atlanan'], 'youtube_kanallar': yt['youtube_kanallar']}


# ---------------------------------------------------------------- canlı: yayın sürerken klip

@contextlib.contextmanager
def canli_kilidi(dizin: pathlib.Path, bayat_sn: float = 3 * 3600):
    """Aynı anda iki canlı tur çalışmasın (zamanlayıcı üst üste binerse aynı anı iki kez keserdi).
    Kilit dosyası bayat_sn'den eskiyse (çöken tur) yok sayılır."""
    dizin.mkdir(parents=True, exist_ok=True)
    yol = dizin / 'canli.kilit'
    for _ in range(2):
        try:
            fd = os.open(str(yol), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            try:
                yas = time.time() - yol.stat().st_mtime
            except OSError:
                continue
            if yas < bayat_sn:
                raise KlipHatasi('başka bir canlı tur çalışıyor (canli.kilit); çökmüşse dosyayı silin')
            yol.unlink(missing_ok=True)
    else:
        raise KlipHatasi('canlı tur kilidi alınamadı')
    try:
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        yield
    finally:
        yol.unlink(missing_ok=True)


def sohbet_hazir_sn(part: pathlib.Path, t0: int) -> int:
    """Sohbeti baştan itibaren kesintisiz indirilmiş süre (sn). Yarım/boşluklu pencerelerin ötesi sayılmaz."""
    biten, _ = _part_oku(part)
    n = 0
    while t0 + n * KICK_PENCERE_SN in biten:
        n += 1
    return n * KICK_PENCERE_SN


def canli_vod(y: dict, http=http_json, http_text=http_metin) -> dict | None:
    """Yayıncının SÜREN yayını (yoksa None). vod['sure_sn'] = şu an videosu alınabilen süre (HLS bölümlerinin toplamı);
    t0_epoch = video 0. sn'sinin gerçek saati (ilk bölümün PROGRAM-DATE-TIME'ı). Sohbet bu saatle hizalanır."""
    for v in kick_vodlar(y['kanal'], y['ad'], http):
        if not v['canli']:
            continue
        vod_t0_ekle(v, http_text)
        ozet = hls_liste_ozeti(http_text(v['hls']))
        if not ozet['bolum']:
            raise KlipHatasi('canlı yayının video listesi boş veya okunamadı')
        v['video_sn'] = ozet['sure_sn']
        v['kayma_sn'] = ozet['kayma_sn']
        v['sure_sn'] = int(ozet['sure_sn'])
        return v
    return None


def sohbet_canli_guncelle(vod: dict, dizin: pathlib.Path, http=http_json, butce_sn: float = 240,
                          marj_sn: float = 20, simdi: float | None = None) -> tuple[list[tuple], int]:
    """Sohbeti yayın başından 'şimdi - marj' e kadar tamamlar; yalnız eksik pencereleri indirir (önceki turların
    part dosyası ortak önbellektir; yayın bitince normal analiz de aynı dosyadan devam eder).
    (mesajlar, baştan kesintisiz hazır süre sn)."""
    simdi = simdi if simdi is not None else time.time()
    part = dizin / 'sohbet' / f"{vod['platform']}-{vod['vod_id']}.part.jsonl"
    hedef = int(simdi - marj_sn - vod['t0_epoch']) - KICK_PENCERE_SN   # son TAM pencerenin başlangıcı
    if hedef < 0:
        return [], 0
    mesajlar = kick_sohbet_indir(http, vod['kanal_id'], vod['t0_epoch'], hedef, part, butce_sn=butce_sn)
    return mesajlar, sohbet_hazir_sn(part, vod['t0_epoch'])


def canli_adaylar(klipler: list[dict], toplam_sn: float, ayar: dict,
                  engelli: list[tuple[float, float]], kota: int) -> list[dict]:
    """Analizdeki zirvelerden şimdi kesilebilecekler: dalga KAPANMIŞ (son dilimden sonra kümeleme penceresi ve
    bekleme payı geçmiş, klibin bitişi de videoda var), puanı yeterli, daha önce kesilen aralıkla örtüşmeyen.
    En yüksek puanlı kota tanesi zaman sırasıyla döner."""
    dilim = ayar['dilim_sn']
    uygun = []
    for k in klipler:
        dalga_sonu = max(k['zirve_dilimleri']) + dilim
        kapanis = max(dalga_sonu + ayar['birlestir_sn'], k['klip_bitis_sn']) + ayar['canli_bekle_sn']
        if kapanis > toplam_sn or k['puan'] < ayar['canli_min_puan']:
            continue
        if araliklar_orter(k['klip_baslangic_sn'], k['klip_bitis_sn'], engelli):
            continue
        uygun.append(k)
    uygun.sort(key=lambda k: (-k['puan'], k['zirve_sn']))
    return sorted(uygun[:max(kota, 0)], key=lambda k: k['zirve_sn'])


def canli_kesim_kaydet(dizin: pathlib.Path, vod: dict, kayit: dict) -> None:
    """Kesilen anı kalıcı yazar (durum.json): sonraki turlar ve yayın bitince `kes` aynı anı yeniden kesmez."""
    d = durum_oku(dizin)
    k = d['vod'].setdefault(vod['anahtar'], {})
    k.setdefault('durum', 'canli')
    k['yayinci'] = vod['yayinci']
    k.setdefault('canli_klipler', []).append(kayit)
    k['guncellendi'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    durum_yaz(dizin, d)


def canli_aralik_listesi(kayit: dict, t0: float) -> list[tuple[float, float]]:
    """Durumdaki canlı klip kayıtları -> bu VOD'un video saniyesinde (başlangıç, bitiş) aralıkları (gerçek saatten)."""
    return [(c['bas_epoch'] - t0, c['bit_epoch'] - t0) for c in kayit.get('canli_klipler', [])]


def konusma_veto_araliklari(kayit: dict, t0: float, ayar: dict) -> list[tuple[float, float]]:
    if not ayar.get('konusma'):
        return []
    imza = klip_konusma.karar_imzasi(ayar)
    return [(r['bas_epoch']-t0, r['bit_epoch']-t0) for r in kayit.get('konusma_elenen', []) if r['imza'] == imza]


def konusma_veto_kaydet(dizin: pathlib.Path, vod: dict, rapor: dict, ayar: dict) -> int:
    vetolar = [r for r in rapor.get('kararlar', []) if r['sonuc'] != 'seçim havuzunda' and r.get('yargi') is not None]
    if not vetolar:
        return 0
    durum = durum_oku(dizin)
    kayit = durum['vod'].setdefault(vod['anahtar'], {})
    onceki = kayit.setdefault('konusma_elenen', [])
    imza = klip_konusma.karar_imzasi(ayar)
    eklendi = 0
    for r in vetolar:
        bas, bit = vod['t0_epoch']+r['klip_baslangic_sn'], vod['t0_epoch']+r['klip_bitis_sn']
        if any(x['imza'] == imza and x['bas_epoch'] == bas and x['bit_epoch'] == bit for x in onceki):
            continue
        onceki.append({'bas_epoch': bas, 'bit_epoch': bit, 'imza': imza, 'neden': r['sonuc']})
        eklendi += 1
    durum_yaz(dizin, durum)
    return eklendi


def canli_komutu(ayar: dict, dizin: pathlib.Path, kanal: str | None = None, en_cok: int | None = None,
                 gecersiz: dict | None = None, butce_sn: float | None = None, kuru: bool = False,
                 suzgecsiz: bool = False, http=http_json, http_text=http_metin, simdi: float | None = None,
                 kesici=None) -> list[dict]:
    """Tek seferlik tur: etkin yayıncılardan CANLI olanlarda, yayın başından şu ana kadar olan sohbeti (yalnız
    yeni kısmı indirerek) analiz eder; dalgası kapanmış, daha önce kesilmemiş en iyi anları kesip dizin/cikti
    altına canli-NN.mp4 yazar. Her kesim durum.json'a yazılır. kuru: indirir ve analiz eder ama kesmez.
    kesici(vod, klip, mp4, vayar) -> doğrulama sözlüğü (testler için); varsayılan ffmpeg ile klip_kes."""
    rapor, kesilen_toplam = [], 0
    ff_font: list = []
    if kesici is None:
        def kesici(vod, klip, mp4, vayar):
            if not ff_font:
                ff_font.extend((ffmpeg_bul(), font_bul()))
            return klip_kes(vod, klip, mp4, ff_font[0], ff_font[1], vayar)
    for y in ayar['yayincilar']:
        if not y['etkin'] or y['platform'] != 'kick':
            continue
        if kanal and kanal.lower() not in (y['ad'].lower(), y['kanal'].lower()):
            continue
        tur_bas = time.monotonic()
        satir: dict = {'yayinci': y['ad']}
        rapor.append(satir)
        try:
            vod = canli_vod(y, http, http_text)
            if vod is None:
                satir['durum'] = 'canlı değil'
                continue
            vayar = {**y['ayar'], **(gecersiz or {})}
            if vayar['yontem'] != 'sinyal':
                raise KlipHatasi("canlı mod yalnız 'sinyal' yöntemiyle çalışır")
            uygun, _ = oyun_suzgeci(vod, vayar)
            satir.update(anahtar=vod['anahtar'], baslik=vod['baslik'], oyun=vod['oyun'])
            if not uygun and not suzgecsiz:
                satir['durum'] = 'oyun süzgecine uymuyor'
                continue
            tur_simdi = simdi if simdi is not None else time.time()
            kayit = durum_oku(dizin)['vod'].get(vod['anahtar'], {})
            kesilmis = kayit.get('canli_klipler', [])
            if len(kesilmis) >= vayar['canli_azami_klip']:
                satir['durum'] = 'yayın canlı klip kotası doldu'
                continue
            mesajlar, hazir = sohbet_canli_guncelle(
                vod, dizin, http, butce_sn if butce_sn is not None else vayar['canli_sohbet_butce_sn'],
                vayar['canli_sohbet_marj_sn'], tur_simdi)
            dilim = vayar['dilim_sn']
            toplam = int(min(vod['video_sn'], hazir) // dilim) * dilim
            satir.update(video_sn=round(vod['video_sn']), sohbet_hazir_sn=hazir, analiz_sn=toplam,
                         hiz_kaymasi_sn=vod['kayma_sn'], kesilmis=len(kesilmis))
            if toplam < vayar['canli_min_sure_sn']:
                satir['durum'] = ('sohbet henüz yetişmedi (sonraki turlarda sürer)' if hazir < vod['video_sn'] - 60
                                  else 'yayın henüz kısa (analiz için en az canli_min_sure_sn gerekir)')
                continue
            engelli = canli_aralik_listesi(kayit, vod['t0_epoch'])
            vetolar = konusma_veto_araliklari(kayit, vod['t0_epoch'], vayar)
            engelli += vetolar
            satir['konusma_veto_atlanan'] = len(vetolar)
            sonuc = analiz_et({**vod, 'sure_sn': toplam}, mesajlar,
                              {**vayar, 'azami_klip': 50, 'son_dislama_sn': 0}, engelli=engelli)
            adaylar = canli_adaylar(sonuc['klipler'], toplam, vayar, engelli,
                                    vayar.get('konusma_canli_aday_sayisi', 6)
                                    if vayar.get('konusma') else vayar['canli_azami_klip'] - len(kesilmis))
            acik_zirve = len(sonuc['klipler']) - len(adaylar)
            if vayar.get('konusma') and adaylar:
                try:
                    adaylar, satir['konusma'] = klip_konusma.katman(
                        {**vod, 'sure_sn': toplam}, adaylar, dizin,
                        {**vayar, 'son_dislama_sn': 0, 'azami_klip': vayar['canli_azami_klip'] - len(kesilmis)},
                        ffmpeg_bul(), http_text, canli=True, engelli=engelli)
                except (KlipHatasi, klip_konusma.ModelKotasi) as e:
                    satir['konusma'] = {'durum': 'konuşma katmanı kapalı', 'neden': str(e)}
                if not kuru:
                    satir['konusma_veto_yeni'] = konusma_veto_kaydet(dizin, vod, satir['konusma'], vayar)
                # Cümleye oturtma aralığı uzatabilir: kapanış ve epoch çakışması yeniden denetlenir.
                adaylar = canli_adaylar(adaylar, toplam, vayar, engelli,
                                        vayar['canli_azami_klip'] - len(kesilmis))
            else:
                satir['konusma'] = {'durum': 'konuşma katmanı kapalı' if not vayar.get('konusma') else 'kapalı aday yok'}
            satir['durum'] = 'tamam'
            satir['acik_zirve'] = acik_zirve
            satir['klipler'] = []
            cikti_dizini = dizin / 'cikti' / f"{dosya_adi(vod['yayinci'])}-{vod['tarih'].replace('-', '')}-{vod['vod_id'][:8]}"
            for k in adaylar:
                if en_cok is not None and kesilen_toplam >= en_cok:
                    break
                bilgi_satiri = {'zirve': k['zirve_zaman'], 'klip_sn': [k['klip_baslangic_sn'], k['klip_bitis_sn']],
                                'puan': k['puan'], 'baskin': k.get('baskin'), 'ornek_mesajlar': k.get('ornek_mesajlar', [])}
                satir['klipler'].append(bilgi_satiri)
                if kuru:
                    continue
                no = len(kesilmis) + 1
                mp4 = cikti_dizini / f'canli-{no:02d}.mp4'
                print(f"  {y['ad']} canlı klip {no}: {zaman_metni(k['klip_baslangic_sn'])}–{zaman_metni(k['klip_bitis_sn'])}",
                      file=sys.stderr, flush=True)
                try:
                    vod_kes = {**vod, 'sure_sn': toplam}
                    k['_engelli'] = engelli
                    bilgi = kesici(vod_kes, k, mp4, vayar)
                    mp4.with_suffix('.json').write_text(json.dumps(paket_json(
                        vod_kes, k, mp4, bilgi, vayar,
                        ekstra={'canli_kesim': True, 'kesimde_video_sn': round(vod['video_sn']),
                                'kesimde_sohbet_sn': hazir, 'hiz_kaymasi_sn': vod['kayma_sn']}),
                        ensure_ascii=False, indent=2), encoding='utf-8')
                except KlipHatasi as e:
                    bilgi_satiri['hata'] = str(e)
                    continue
                t0 = vod['t0_epoch']
                kayit_yeni = {'no': no, 'dosya': str(mp4), 'bas_sn': k['klip_baslangic_sn'], 'bit_sn': k['klip_bitis_sn'],
                              'bas_epoch': t0 + k['klip_baslangic_sn'], 'bit_epoch': t0 + k['klip_bitis_sn'],
                              'zirve_sn': k['zirve_sn'], 'puan': k['puan'], 'video': bilgi,
                              'kesim': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}
                canli_kesim_kaydet(dizin, vod, kayit_yeni)
                kesilmis = kesilmis + [kayit_yeni]
                kesilen_toplam += 1
                engelli.append((k['klip_baslangic_sn'], k['klip_bitis_sn']))
                bilgi_satiri['dosya'] = str(mp4)
        except KlipHatasi as e:
            satir['durum'] = 'hata'
            satir['hata'] = str(e)
        finally:
            satir['tur_sn'] = round(time.monotonic() - tur_bas, 3)
    return rapor


# ---------------------------------------------------------------- kısa açıklama: geri doldurma ve yeniden üretim

def paket_yollari(dizin: pathlib.Path, klasor: pathlib.Path | None = None) -> list[pathlib.Path]:
    kok = klasor or (dizin / 'cikti')
    return sorted(y for y in kok.rglob('*.json') if 'eski' not in {x.lower() for x in y.parts}
                  and not y.name.startswith('_') and y.with_suffix('.mp4').exists())


def yayinci_kisa_ad(ayar: dict, paket: dict) -> str:
    for y in ayar.get('yayincilar', []):
        if y['ad'] == paket.get('yayinci') or (y['platform'] == paket.get('platform') and
                                             y['kanal'].lower() == str(paket.get('kanal') or '').lower()):
            return y.get('kisa_ad') or y['ad']
    return paket.get('yayinci') or ''


def analiz_onbellegine_isle(dizin: pathlib.Path, paket: dict, metin: str | None) -> bool:
    """Analiz önbelleğindeki aynı klibe de açıklamayı yazar; yoksa sonraki `kes` klibi açıklamasız yeniden keserdi."""
    vod_id = paket.get('vod_id')
    if not vod_id:   # Kick konuşma paketlerinde vod_id yok: adresten çıkar (Kick VOD uuid'i / YouTube video kimliği)
        m = re.search(r'kick\.com/[^/\s]+/videos/([0-9a-fA-F-]{36})', str(paket.get('vod_url') or '')) or             re.search(r'(?:youtube\.com/watch\?(?:[^#\s]*&)?v=|youtu\.be/)([\w-]{11})', str(paket.get('vod_url') or ''))
        vod_id = m.group(1) if m else None
    yol = dizin / 'analiz' / f"{paket.get('platform')}-{vod_id}.json"
    if not yol.exists():
        return False
    sonuc = json.loads(yol.read_text(encoding='utf-8'))
    degisti = False
    for k in sonuc.get('klipler', []):
        ayni = (k.get('konusma_plan_araligi') and k.get('konusma_plan_araligi') == paket.get('konusma_plan_araligi')) or \
               (k.get('zirve_sn') == paket.get('zirve_sn') and k.get('klip_baslangic_sn') == paket.get('klip_baslangic_sn'))
        if ayni and k.get('konusma_kisa_aciklama') != metin:
            k['konusma_kisa_aciklama'] = metin
            degisti = True
    if degisti:
        yol.write_text(json.dumps(sonuc, ensure_ascii=False, indent=1), encoding='utf-8')
    return degisti


def aciklama_doldur(ayar: dict, dizin: pathlib.Path, klasor: pathlib.Path | None = None, model=None,
                    kuru: bool = False, parca: int = 20) -> dict:
    """kisa_aciklama anahtarı olmayan konuşma paketlerinin (döküm metni olanlar) hepsi için TEK toplu model çağrısı
    (parça sayısı `parca`'yı aşarsa parça başına bir). Dökümsüz eski sohbet paketlerine dokunulmaz.
    Sonuç paket JSON'una `kisa_aciklama` (doğrulanmış metin ya da null) ve `kisa_aciklama_ham` olarak yazılır."""
    aday, atlanan = [], []
    for yol in paket_yollari(dizin, klasor):
        try:
            d = json.loads(yol.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if not isinstance(d, dict):
            continue
        # Daha önce yargılanmış paket tekrar sorulmaz; tek istisna: model metni yalnız uzunluk yüzünden null kalmış
        # ve henüz tamir edilmemiş (kisa_aciklama_tamir yok) -> yeniden yazdırılır.
        tamirlik = ('kisa_aciklama' in d and d['kisa_aciklama'] is None and not d.get('kisa_aciklama_tamir')
                    and klip_konusma.uzun_mu(d.get('kisa_aciklama_ham'), ayar.get('ayar')))
        if 'kisa_aciklama' in d and not tamirlik:
            continue
        if not str(d.get('dokum_metni') or '').strip():
            atlanan.append(str(yol))
            continue
        d['_tamirlik'] = tamirlik   # yalnız bellekte; dosyaya yazılmadan silinir
        aday.append((yol, d))
    rapor = {'aday': len(aday), 'model_cagrisi': 0, 'atlanan_dokumsuz': atlanan, 'paketler': []}
    sayac = {'n': 0}
    if not aday or kuru:
        return rapor
    if model is None:
        model = klip_konusma.ButceliModel(
            klip_konusma.ModelYolu({**klip_konusma.AYAR, 'konusma_yargi_model': 'sonnet', 'konusma_bulut': True}), 4)
    cfg = {**AYAR_VARSAYILAN, **(ayar.get('ayar') or {})}
    gercek_model = model

    def model(istem):   # noqa: F811 - gerçek model çağrılarını sayar (ilk çağrı + varsa biçim/uzunluk tamiri)
        sayac['n'] += 1
        return gercek_model(istem)
    for i in range(0, len(aday), parca):
        grup = aday[i:i + parca]
        kayit = [{'id': str(n), 'ad': yayinci_kisa_ad(ayar, d), 'oyun': d.get('oyun'), 'baslik': d.get('baslik'),
                  'gerekce': d.get('konusma_gerekce'), 'dokum': d.get('dokum_metni'),
                  **({'onceki': d['kisa_aciklama_ham'], 'onceki_uzunluk': klip_konusma._temiz_uzunluk(d['kisa_aciklama_ham'])}
                     if d['_tamirlik'] else {})}
                 for n, (_, d) in enumerate(grup, start=i)]
        try:
            yanit = klip_konusma.aciklama_toplu(kayit, model, cfg)
        finally:
            rapor['model_cagrisi'] = sayac['n']
        for n, (yol, d) in enumerate(grup, start=i):
            y = yanit[str(n)]
            tamirlikti = d.pop('_tamirlik')
            if tamirlikti or y.get('tamir'):
                d['kisa_aciklama_onceki_ham'] = y.get('onceki_ham') or d.get('kisa_aciklama_ham')
            d['kisa_aciklama'] = y['aciklama']
            d['kisa_aciklama_ham'] = y['ham']
            if tamirlikti or y.get('tamir') or klip_konusma.uzun_mu(y['ham'], cfg):
                d['kisa_aciklama_tamir'] = True   # bir kez denendi: tekrar sorulmaz
            yol.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding='utf-8')
            analiz_onbellegine_isle(dizin, d, y['aciklama'])
            rapor['paketler'].append({'paket': str(yol), 'yayinci': d.get('yayinci'),
                                      'kisa_aciklama': y['aciklama'], 'ham': y['ham'], 'tamir': bool(y.get('tamir'))})
    return rapor


def yedekle(paket: pathlib.Path, yedek: pathlib.Path) -> list[str]:
    """mp4 + json'u yedek klasörüne KOPYALAR (üzerine yazılmadan önce); aynı adlı yedek varsa dokunmaz."""
    hedef_klasor = yedek / paket.parent.name
    hedef_klasor.mkdir(parents=True, exist_ok=True)
    kopya = []
    for yol in (paket.with_suffix('.mp4'), paket):
        h = hedef_klasor / yol.name
        if not h.exists():
            shutil.copy2(yol, h)
        kopya.append(str(h))
    return kopya


KLIP_EN_AZ_SN, KLIP_EN_COK_SN = 5.0, 59.0


def kamera_kutusu_coz(metin) -> tuple[float, float, float, float]:
    """'x,y,w,h' (kare genişliği/yüksekliğine oransal, 0–1) -> dörtlü. Geçersizse anlaşılır KlipHatasi."""
    try:
        kutu = tuple(float(v) for v in str(metin).replace(';', ',').split(','))
    except ValueError:
        raise KlipHatasi(f'kamera kutusu sayı olmalı: x,y,w,h (örnek 0.02,0.60,0.28,0.38); verilen: {metin}') from None
    if len(kutu) != 4 or not klip_kamera.kutu_gecerli(kutu):
        raise KlipHatasi('kamera kutusu geçersiz: x,y,w,h oransal (0–1) olmalı, w ve h > 0, kutu kareden taşmamalı '
                         f'(örnek 0.02,0.60,0.28,0.38); verilen: {metin}')
    return tuple(round(v, 5) for v in kutu)


def aciklama_metni_dogrula(metin: str, ayar: dict | None = None) -> str:
    """--aciklama-metni: 45 karakter sınırı ve yasak kelime denetimi (model çıktısıyla aynı kural). Neden anlaşılır."""
    ham = re.sub(r'\s+', ' ', str(metin or '')).strip().strip('"“”\'`').strip().rstrip('.').strip()
    azami = int((ayar or {}).get('aciklama_azami_karakter', klip_konusma.ACIKLAMA_AZAMI))
    if not ham:
        raise KlipHatasi('açıklama metni boş')
    if len(ham) > azami:
        raise KlipHatasi(f'açıklama metni {len(ham)} karakter; en çok {azami} olabilir')
    if klip_konusma.yasak_kelime_var(ham, [*klip_konusma.ACIKLAMA_YASAK_VARSAYILAN,
                                           *((ayar or {}).get('aciklama_yasak_kelimeler') or [])]):
        raise KlipHatasi('açıklama metninde yasak kelime (küfür/argo) var')
    temiz = klip_konusma.kisa_aciklama_dogrula(ham, ayar)
    if temiz is None:
        raise KlipHatasi('açıklama metni uygun değil: en az 2 kelime olmalı; ünlem yığını, emoji, #etiket, büyük harf '
                         'yığını, "yayıncı ..." ile başlama ve tık tuzağı kalıpları kullanılmaz')
    return temiz


def baslik_oyun_duzelt(baslik: str | None, eski_oyun: str | None, yeni_oyun: str | None) -> str | None:
    """Şablon başlığın sonundaki ' | <oyun>' eki yeni oyun adına uyar: eski ek atılır, yeni ad varsa eklenir."""
    if not baslik:
        return baslik
    if eski_oyun and baslik.endswith(f' | {eski_oyun}'):
        baslik = baslik[:-len(f' | {eski_oyun}')].rstrip()
    if yeni_oyun and not baslik.endswith(f' | {yeni_oyun}'):
        baslik = f'{baslik} | {yeni_oyun}'
    return baslik


def paketten_uret(paket_yolu: pathlib.Path, ayar: dict, dizin: pathlib.Path, yedek: pathlib.Path | None = None,
                  aciklamasiz: bool = False, secenek: dict | None = None) -> dict:
    """Var olan klibi paketindeki (ses hizası düzeltilmiş) aralıkla, bugünkü düzenle ve paketteki kisa_aciklama ile
    YENİDEN keser. Eski mp4/json önce yedeğe kopyalanır; paketin diğer alanları korunur.

    secenek (hepsi isteğe bağlı; verilen değer pakete KALICI yazılır -> `duzenleme`, sonraki yeniden kesimlerde korunur):
      marka (yazı) | markasiz (bool), oyun (ad) | oyunsuz (bool), aciklama_metni (45 kr, yasak kelimesiz) | aciklamasiz (bool), yayinci_adi,
      bas_kaydir / son_kaydir (sn, eksi = daha erken; süre 5–59 sn), duzen (kamera|kadraj|serit), kamera_kutu (x,y,w,h oransal).
    Oyun adı kategori+kare doğrulamasından (klip_oyun) ya da --oyun/--oyunsuz'dan gelir; dökümsüz klip için kendi sesinden
    metin üretilir (klip_oyun.ses_yargisi). Önbellekteki karar/metin aynı aralık için tekrar sorulmaz."""
    sec = dict(secenek or {})
    if aciklamasiz:
        sec['aciklamasiz'] = True
    if sec.get('oyun') is not None and sec.get('oyunsuz'):
        raise KlipHatasi('--oyun ile --oyunsuz birlikte verilemez')
    if sec.get('aciklama_metni') is not None and sec.get('aciklamasiz'):
        raise KlipHatasi('--aciklama-metni ile --aciklamasiz birlikte verilemez')
    if sec.get('marka') is not None and sec.get('markasiz'):
        raise KlipHatasi('--marka ile --markasiz birlikte verilemez')
    d = json.loads(paket_yolu.read_text(encoding='utf-8'))
    dz = dict(d.get('duzenleme') or {})
    cfg_ac = {**AYAR_VARSAYILAN, **(ayar.get('ayar') or {})}
    if sec.get('oyun') is not None:
        ad = re.sub(r'\s+', ' ', str(sec['oyun'])).strip()
        if not ad or len(ad) > klip_oyun.OYUN_AD_AZAMI:
            raise KlipHatasi(f'oyun adı boş olamaz ve en çok {klip_oyun.OYUN_AD_AZAMI} karakter olabilir')
        dz['oyun'] = ad
        dz.pop('oyunsuz', None)
    if sec.get('oyunsuz'):
        dz['oyunsuz'] = True
        dz.pop('oyun', None)
    if sec.get('aciklama_metni') is not None:
        dz['aciklama_metni'] = aciklama_metni_dogrula(sec['aciklama_metni'], cfg_ac)
        dz['aciklamasiz'] = False
    if sec.get('aciklamasiz'):
        dz['aciklamasiz'] = True
    if sec.get('marka') is not None:
        m = re.sub(r'\s+', ' ', str(sec['marka'])).strip()
        if not m or len(m) > MARKA_AZAMI:
            raise KlipHatasi(f'marka yazısı boş olamaz (markasız için --markasiz) ve en çok {MARKA_AZAMI} karakter olabilir')
        dz['marka_yazi'] = m
    if sec.get('markasiz'):
        dz['marka_yazi'] = ''
    if sec.get('yayinci_adi') is not None:
        ad = re.sub(r'\s+', ' ', str(sec['yayinci_adi'])).strip()
        if not ad or len(ad) > 40:
            raise KlipHatasi('yayıncı adı boş olamaz ve en çok 40 karakter olabilir')
        dz['yayinci_adi'] = ad
    if sec.get('duzen') is not None:
        if sec['duzen'] not in ('kamera', 'kadraj', 'serit'):
            raise KlipHatasi(f"düzen kamera, kadraj ya da serit olmalı; verilen: {sec['duzen']}")
        dz['duzen'] = sec['duzen']
    if sec.get('kamera_kutu') is not None:
        kutu = kamera_kutusu_coz(sec['kamera_kutu']) if isinstance(sec['kamera_kutu'], str) else tuple(sec['kamera_kutu'])
        if len(kutu) != 4 or not klip_kamera.kutu_gecerli(kutu):
            raise KlipHatasi('kamera kutusu geçersiz (oransal x,y,w,h)')
        dz['kamera_kutu'] = list(kutu)
    bk, sk = float(sec.get('bas_kaydir') or 0), float(sec.get('son_kaydir') or 0)
    eski_bas, eski_bit = float(d['klip_baslangic_sn']), float(d['klip_bitis_sn'])
    bas, bit = round(eski_bas + bk, 3), round(eski_bit + sk, 3)
    sure = bit - bas
    if sure < KLIP_EN_AZ_SN - 1e-6 or sure > KLIP_EN_COK_SN + 1e-6:
        raise KlipHatasi(f'klip {sure:.1f} sn olurdu (şimdi {eski_bit - eski_bas:.1f} sn); süre {KLIP_EN_AZ_SN:.0f}–'
                         f'{KLIP_EN_COK_SN:.0f} sn arasında olmalı')
    if bas < 0:
        raise KlipHatasi(f'başlangıç yayının başından {-bas:.1f} sn önceye gidiyor')
    kaydirildi = bool(bk or sk)
    if kaydirildi:
        dz['bas_kaydir_toplam'] = round(float(dz.get('bas_kaydir_toplam') or 0) + bk, 3)
        dz['son_kaydir_toplam'] = round(float(dz.get('son_kaydir_toplam') or 0) + sk, 3)
    vod, vayar = vod_hazirla(d['vod_url'], ayar)
    if bit > vod['sure_sn'] + .01:
        raise KlipHatasi(f"bitiş yayının süresini ({vod['sure_sn']:.0f} sn) {bit - vod['sure_sn']:.1f} sn aşıyor")
    yedek = yedek or (pathlib.Path(r'C:\Cihan.Ai\_yedek') / f"yayin-klip-{datetime.now().strftime('%Y%m%d')}"
                      if os.name == 'nt' else dizin / 'yedek')
    kopya = yedekle(paket_yolu, yedek)
    vayar = {**vayar, 'konusma': True, **({'klip_aciklama_yazi': False} if dz.get('aciklamasiz') else {}),
             **({'duzen': dz['duzen']} if dz.get('duzen') else {}),
             **(marka_ayari(dz['marka_yazi']) if 'marka_yazi' in dz else {})}
    vod_ad = d.get('yayinci')
    if dz.get('yayinci_adi'):
        vod = {**vod, 'yayinci': dz['yayinci_adi'], 'kisa_ad': dz['yayinci_adi']}
    if dz.get('kamera_kutu'):
        vod['kamera_kutu'] = tuple(dz['kamera_kutu'])
    elle_metin = dz.get('aciklama_metni')
    onbellek = {} if kaydirildi else {k: d[k] for k in ('oyun_dogrulama', 'ses_yargisi') if isinstance(d.get(k), dict)}
    klip = {'klip_baslangic_sn': bas, 'klip_bitis_sn': bit, 'baskin': d.get('baskin_sinyal'),
            'kelimeler': d.get('one_cikan_kelimeler'), 'emojiler': d.get('one_cikan_emojiler'),
            'konusma_kisa_aciklama': elle_metin or d.get('kisa_aciklama'),
            'dokum_metni': None if kaydirildi else d.get('dokum_metni'),
            **({'aciklama_elle': elle_metin} if elle_metin else {}), **onbellek,
            **({'oyun_elle': ''} if dz.get('oyunsuz') else {'oyun_elle': dz['oyun']} if dz.get('oyun') else {})}
    bilgi = klip_kes(vod, klip, paket_yolu.with_suffix('.mp4'), ffmpeg_bul(), font_bul(), vayar)
    d.pop('kamera_plani', None)
    if bilgi.get('kamera'):
        d['kamera_plani'] = bilgi['kamera']
    ok = klip.get('oyun_dogrulama')
    eski_oyun = d.get('oyun')
    yeni_oyun = ok['oyun'] if isinstance(ok, dict) else eski_oyun
    s = klip.get('ses_yargisi') if isinstance(klip.get('ses_yargisi'), dict) else None
    metin_yeni = bool(elle_metin) or bool(s and s.get('durum') == 'tamam' and s.get('kisa_aciklama'))
    if elle_metin:
        d['baslik'] = elle_metin
    elif metin_yeni and klip.get('konusma_baslik'):
        d['baslik'] = klip['konusma_baslik']
    else:
        d['baslik'] = baslik_oyun_duzelt(d.get('baslik'), eski_oyun, yeni_oyun)
    if metin_yeni or dz.get('yayinci_adi') or 'marka_yazi' in dz:
        d['aciklama'] = aciklama_uret({**vod, 'oyun': yeni_oyun}, {**klip, 'konusma_baslik': d['baslik']}, vayar)
    if kaydirildi:
        d['klip_baslangic_sn'], d['klip_bitis_sn'] = bas, bit
        d['vod_zaman_damgali_url'], d['vod_zaman_damgali_url_dogrulandi'] = zaman_damgali_baglanti(vod, bas)
    d['oyun'] = yeni_oyun
    if isinstance(ok, dict):
        d['oyun_dogrulama'] = ok
    elif kaydirildi:
        d.pop('oyun_dogrulama', None)
    if s:
        d['ses_yargisi'] = s
    elif kaydirildi:
        d.pop('ses_yargisi', None)
    if klip.get('dokum_metni'):
        d['dokum_metni'] = klip['dokum_metni']
    if dz.get('yayinci_adi'):
        d['yayinci_adi'] = dz['yayinci_adi']
    d['yayinci'] = vod_ad
    if dz:
        d['duzenleme'] = dz
    d.update({'kisa_aciklama': klip.get('konusma_kisa_aciklama'), 'aciklama_yazisi': bilgi.get('aciklama_yazisi'),
              'video': bilgi, 'duzen': duzen_imzasi(vayar, klip_aciklamasi(klip, vayar)),
              'uretim': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')})
    paket_yolu.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding='utf-8')
    return {'paket': str(paket_yolu), 'mp4': str(paket_yolu.with_suffix('.mp4')), 'yedek': kopya,
            'aciklama_yazisi': bilgi.get('aciklama_yazisi'),
            'video': {k: bilgi[k] for k in ('genislik', 'yukseklik', 'sure_sn', 'ses')},
            'oyun': d.get('oyun'), 'oyun_kaynagi': ok.get('kaynak') if isinstance(ok, dict) else None,
            'baslik': d.get('baslik'), 'kisa_aciklama': d.get('kisa_aciklama'), 'duzenleme': d.get('duzenleme')}


def _gecersiz(a) -> dict:
    g = {}
    if getattr(a, 'konusmasiz', False):
        g['konusma'] = False
    elif getattr(a, 'konusma', False):
        g['konusma'] = True
    if getattr(a, 'aciklamasiz', False):
        g['klip_aciklama_yazi'] = False
    for alan in ('esik_k', 'min_mesaj', 'azami_klip', 'bas_dislama_sn', 'min_oran', 'min_farkli_kullanici',
                 'min_emote_disi_oran', 'kadraj_oran', 'duzen', 'yontem', 'klip_baslangic',
                 'gulme_esik_k', 'konu_min_kisi', 'konu_min_lift', 'max_gurultu_oran'):
        v = getattr(a, alan, None)
        if v is not None:
            g[alan] = v
    return g


class _TrParser(argparse.ArgumentParser):
    """Komut satırı hatası: tek satır Türkçe stderr ('HATA: ...') ve çıkış kodu 2 (kullanım dökümü yok)."""
    def error(self, message):
        for en, tr in (('expected one argument', 'değer eksik'), ('unrecognized arguments', 'tanınmayan seçenek'),
                       ('the following arguments are required', 'gerekli değer eksik'),
                       ('invalid choice', 'geçersiz seçim'), ('argument ', 'seçenek '), ('not allowed with', 'birlikte verilemez')):
            message = message.replace(en, tr)
        print('HATA: komut satırı: ' + ' '.join(message.split()), file=sys.stderr)
        sys.exit(2)


def _sn_tipi(metin: str) -> float:
    try:
        v = float(metin)
    except ValueError:
        raise argparse.ArgumentTypeError(f'saniye sayı olmalı (eksi = daha erken); verilen: {metin}') from None
    if not math.isfinite(v):
        raise argparse.ArgumentTypeError(f'saniye sonlu bir sayı olmalı; verilen: {metin}')
    return v


def _konusma_bayraklari(parser):
    g = parser.add_mutually_exclusive_group()
    g.add_argument('--konusma',action='store_true',help='konuşma katmanını bu çalıştırmada aç')
    g.add_argument('--konusmasiz',action='store_true',help='konuşma katmanını bu çalıştırmada kapat')


def main(argv=None) -> int:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    p = _TrParser(description='Yayın klip hattı (yayın yapmaz).')
    p.add_argument('--ayar', help='yayıncı ayar dosyası (varsayılan otomasyon/klip-yayincilar.json)')
    p.add_argument('--dizin', help='çalışma dizini (YAYIN_KLIP_DIZIN)')
    s = p.add_subparsers(dest='komut', required=True)
    t = s.add_parser('tara', help='son biten yayınları listele')
    t.add_argument('--yayinci')
    t.add_argument('--hepsi', action='store_true', help='işlenmişleri de göster')
    for ad, yardim in (('analiz', 'sohbeti indir, zirveleri bul'), ('kes', 'klipleri kes ve paketle')):
        k = s.add_parser(ad, help=yardim)
        k.add_argument('vod', help='kick:<uuid>, Kick adresi, youtube:<id> veya YouTube video adresi')
        k.add_argument('--esik-k', dest='esik_k', type=float)
        k.add_argument('--min-mesaj', dest='min_mesaj', type=int)
        k.add_argument('--min-oran', dest='min_oran', type=float)
        k.add_argument('--azami-klip', dest='azami_klip', type=int)
        k.add_argument('--bas-dislama-sn', dest='bas_dislama_sn', type=int)
        k.add_argument('--min-farkli-kullanici', dest='min_farkli_kullanici', type=int)
        k.add_argument('--min-emote-disi-oran', dest='min_emote_disi_oran', type=float)
        k.add_argument('--yontem', choices=('sinyal', 'yogunluk'), help='sinyal = kahkaha/ortak konu/yoğunluk; yogunluk = eski yalnız mesaj sayısı')
        k.add_argument('--klip-baslangic', dest='klip_baslangic', choices=('dalga', 'tepe'),
                       help='kliplerin başlangıç referansı: kahkaha dalgasının başladığı dilim ya da tepe dilimi')
        k.add_argument('--gulme-esik-k', dest='gulme_esik_k', type=float)
        k.add_argument('--konu-min-kisi', dest='konu_min_kisi', type=int)
        k.add_argument('--konu-min-lift', dest='konu_min_lift', type=float)
        k.add_argument('--max-gurultu-oran', dest='max_gurultu_oran', type=float)
        k.add_argument('--suzgecsiz', action='store_true', help='oyun süzgecine uymasa da işle')
        _konusma_bayraklari(k)
        k.add_argument('--yeniden', action='store_true', help='analizi önbellekten alma')
        if ad == 'kes':
            k.add_argument('--zorla', action='store_true', help='var olan klibi yeniden üret')
            k.add_argument('--aciklamasiz', action='store_true',
                           help='klibe kısa açıklama yazısı koyma (ayar: klip_aciklama_yazi=false)')
            k.add_argument('--duzen', choices=('kamera', 'kadraj', 'serit'), help='görüntü düzeni (ayardakini bu çalıştırma için değiştirir)')
            k.add_argument('--kadraj-oran', dest='kadraj_oran', type=float, help='kırpılan bölgenin genişlik/yükseklik oranı')
    ad_ = s.add_parser('aciklama-doldur', help='kisa_aciklama olmayan konuşma paketlerine TEK toplu model çağrısıyla açıklama yaz')
    ad_.add_argument('--klasor', help='yalnız bu klasördeki paketler (varsayılan: çalışma dizini/cikti)')
    ad_.add_argument('--kuru', action='store_true', help='yalnız kaç paketin dolacağını say')
    yu = s.add_parser('yeniden-uret', help='var olan klibi paketindeki aralık ve kisa_aciklama ile yeniden kes (önce yedeğe kopyalar)')
    yu.add_argument('paket', nargs='+', help='klip paket .json yolu')
    yu.add_argument('--yedek', help='yedek klasörü (varsayılan: C:\\Cihan.Ai\\_yedek\\yayin-klip-<tarih>)')
    yu.add_argument('--aciklamasiz', action='store_true', help='açıklama yazısı koyma (kalıcı)')
    yu.add_argument('--oyun', help='videoya/pakete yazılacak oyun adı (kalıcı; doğrulamayı atlar)')
    yu.add_argument('--oyunsuz', action='store_true', help='oyun adı yazma (kalıcı)')
    yu.add_argument('--aciklama-metni', dest='aciklama_metni', help='klip açıklaması (en çok 45 karakter, yasak kelimesiz; kalıcı)')
    yu.add_argument('--marka', help='videonun altındaki marka yazısı + paylaşım imzası (en çok 40 karakter; kalıcı)')
    yu.add_argument('--markasiz', action='store_true', help='marka satırı ve imza koyma (kalıcı)')
    yu.add_argument('--yayinci-adi', dest='yayinci_adi', help='videoda yazan yayıncı adı (kalıcı)')
    yu.add_argument('--bas-kaydir', dest='bas_kaydir', type=_sn_tipi, help='başlangıcı kaydır, sn (eksi = daha erken; kalıcı)')
    yu.add_argument('--son-kaydir', dest='son_kaydir', type=_sn_tipi, help='bitişi kaydır, sn (eksi = daha erken; kalıcı)')
    yu.add_argument('--duzen', choices=('kamera', 'kadraj', 'serit'), help='görüntü düzeni (kalıcı)')
    yu.add_argument('--kamera-kutu', dest='kamera_kutu', help='kamera kutusu x,y,w,h oransal (tespiti ezer; kalıcı)')
    o = s.add_parser('otomatik', help='tara + analiz + kes (yeni yayınların hepsi)')
    o.add_argument('--yayinci')
    _konusma_bayraklari(o)
    o.add_argument('--en-cok', dest='en_cok', type=int, default=3, help='bu çalıştırmada en çok kaç yayın')
    c = s.add_parser('canli', help='yayın SÜRERKEN: canlı yayıncılarda kapanmış kahkaha/konu anlarını kes (tek seferlik tur)')
    c.add_argument('--kanal', help='yalnız bu yayıncı (ad veya kanal)')
    _konusma_bayraklari(c)
    c.add_argument('--en-cok', dest='en_cok', type=int, help='bu turda en çok kaç klip')
    c.add_argument('--kuru', action='store_true', help='sohbeti indir ve analiz et, ama kesme')
    c.add_argument('--sohbet-butcesi-sn', dest='sohbet_butcesi_sn', type=float,
                   help='bir yayıncının sohbetini indirmeye bu turda en çok bu kadar sn (ayar: canli_sohbet_butce_sn)')
    c.add_argument('--min-puan', dest='canli_min_puan', type=float, help='canlı kesim için asgari puan (ayar: canli_min_puan)')
    c.add_argument('--azami-klip', dest='canli_azami_klip', type=int, help='yayın başına en çok canlı klip (ayar: canli_azami_klip)')
    c.add_argument('--suzgecsiz', action='store_true', help='oyun süzgecine uymasa da işle')
    a = p.parse_args(argv)

    ayar = ayar_yukle(a.ayar)
    dizin = pathlib.Path(a.dizin) if a.dizin else calisma_dizini()
    try:
        if a.komut == 'tara':
            print(json.dumps(tara(ayar, dizin, a.yayinci, a.hepsi), ensure_ascii=False, indent=2))
        elif a.komut == 'analiz':
            vod, sonuc = analiz_komutu(a.vod, dizin, ayar, _gecersiz(a), a.yeniden, a.suzgecsiz)
            ozet = {k: v for k, v in sonuc.items() if k != 'dilim_sayimlari'}
            print(json.dumps(ozet, ensure_ascii=False, indent=2))
        elif a.komut == 'kes':
            for m in kes_komutu(a.vod, dizin, ayar, _gecersiz(a), a.zorla, a.yeniden, a.suzgecsiz):
                print(m)
        elif a.komut == 'aciklama-doldur':
            try:
                print(json.dumps(aciklama_doldur(ayar, dizin, pathlib.Path(a.klasor) if a.klasor else None, kuru=a.kuru),
                                 ensure_ascii=False, indent=2))
            except (klip_konusma.ModelKotasi, ValueError, RuntimeError) as e:
                raise KlipHatasi(f'açıklama doldurma: {e}') from e
        elif a.komut == 'yeniden-uret':
            sec = {k: getattr(a, k) for k in ('oyun', 'aciklama_metni', 'yayinci_adi', 'bas_kaydir', 'son_kaydir', 'duzen', 'marka')
                   if getattr(a, k) is not None}
            if a.oyunsuz:
                sec['oyunsuz'] = True
            if a.markasiz:
                sec['markasiz'] = True
            if a.marka is not None and a.markasiz:
                raise KlipHatasi('--marka ile --markasiz birlikte verilemez')
            if a.kamera_kutu is not None:
                sec['kamera_kutu'] = kamera_kutusu_coz(a.kamera_kutu)
            if 'oyun' in sec and a.oyunsuz:
                raise KlipHatasi('--oyun ile --oyunsuz birlikte verilemez')
            if 'aciklama_metni' in sec and a.aciklamasiz:
                raise KlipHatasi('--aciklama-metni ile --aciklamasiz birlikte verilemez')
            for yol in a.paket:
                if not pathlib.Path(yol).is_file():
                    raise KlipHatasi(f'paket dosyası bulunamadı: {yol}')
                try:
                    cikti = paketten_uret(pathlib.Path(yol), ayar, dizin, pathlib.Path(a.yedek) if a.yedek else None,
                                          a.aciklamasiz, sec)
                except (OSError, ValueError, KeyError, TypeError) as e:   # tek satır, anlaşılır hata
                    raise KlipHatasi(f'{pathlib.Path(yol).name}: {type(e).__name__}: {str(e)[:200]}') from e
                print(json.dumps(cikti, ensure_ascii=False))
        elif a.komut == 'canli':
            gec = {k: getattr(a, k) for k in ('canli_min_puan', 'canli_azami_klip') if getattr(a, k) is not None}
            gec.update(_gecersiz(a))
            with canli_kilidi(dizin):
                rapor = canli_komutu(ayar, dizin, a.kanal, a.en_cok, gec, a.sohbet_butcesi_sn, a.kuru, a.suzgecsiz)
            print(json.dumps(rapor, ensure_ascii=False, indent=2))
        elif a.komut == 'otomatik':
            rapor = tara(ayar, dizin, a.yayinci)
            for k in rapor['desteksiz']:
                print(f"desteklenmiyor: {k['yayinci']} ({k['platform']}): {k['neden']}", file=sys.stderr)
            for v in rapor['yeni'][:a.en_cok]:
                print(f"{v['yayinci']} {v['tarih']} {v['baslik'][:50]}", file=sys.stderr)
                try:
                    for m in kes_komutu(v['anahtar'], dizin, ayar, _gecersiz(a)):
                        print(m)
                except KlipHatasi as e:
                    print(f"  atlandı: {e}", file=sys.stderr)
    except KlipHatasi as e:
        print('HATA: ' + ' '.join(str(e).split()), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
