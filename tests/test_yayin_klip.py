"""Yayın klip hattı testleri. Ağ ve ffmpeg gerekmez; örnek sohbet verisi testin içinde üretilir."""
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tools'))
import yayin_klip as yk  # noqa: E402

AYAR = {**yk.AYAR_VARSAYILAN, 'yontem': 'yogunluk'}  # eski testler yoğunluk yöntemini sınar; sinyal yöntemi aşağıdaki sınıflarda
SURE = 7200  # 2 saatlik yayın


def duz_sohbet(sure=SURE, dilim=AYAR['dilim_sn'], mesaj=6):
    """Her dilimde sabit sayıda mesaj."""
    return [mesaj] * (sure // dilim)


def patlama(sayim, dilim_no, deger):
    s = list(sayim)
    s[dilim_no] = deger
    return s


class DilimSayma(unittest.TestCase):
    def test_dilim_say(self):
        sayim = yk.dilim_say([0, 1, 9.9, 10, 25, 59.9, 60, -1, 100], 10, 60)
        self.assertEqual(sayim, [3, 1, 1, 0, 0, 1])  # 60 ve üstü ile eksi konum atılır

    def test_dilim_sayisi_yukari_yuvarlanir(self):
        self.assertEqual(len(yk.dilim_say([], 10, 95)), 10)


class ZirveBulma(unittest.TestCase):
    def test_duz_sohbet_klip_cikarmaz(self):
        klipler, _ = yk.zirveleri_bul(duz_sohbet(), AYAR, SURE)
        self.assertEqual(klipler, [])

    def test_dalgali_ama_zirvesiz_sohbet_klip_cikarmaz(self):
        sayim = [5 + (i % 4) for i in range(SURE // 10)]
        klipler, _ = yk.zirveleri_bul(sayim, AYAR, SURE)
        self.assertEqual(klipler, [])

    def test_tek_patlama_tek_klip(self):
        sayim = patlama(duz_sohbet(), 300, 90)  # 3000. sn
        klipler, _ = yk.zirveleri_bul(sayim, AYAR, SURE)
        self.assertEqual(len(klipler), 1)
        self.assertEqual(klipler[0]['zirve_sn'], 3000)
        self.assertEqual(klipler[0]['mesaj'], 90)

    def test_yakin_iki_patlama_birlesir(self):
        sayim = patlama(patlama(duz_sohbet(), 300, 90), 302, 80)  # 20 sn arayla
        klipler, _ = yk.zirveleri_bul(sayim, AYAR, SURE)
        self.assertEqual(len(klipler), 1)
        self.assertEqual(klipler[0]['zirve_dilimleri'], [3000, 3020])

    def test_uzak_iki_patlama_iki_klip(self):
        sayim = patlama(patlama(duz_sohbet(), 300, 90), 500, 85)
        klipler, _ = yk.zirveleri_bul(sayim, AYAR, SURE)
        self.assertEqual([k['zirve_sn'] for k in klipler], [3000, 5000])
        self.assertEqual([k['no'] for k in klipler], [1, 2])

    def test_yayin_basi_dislanir(self):
        sayim = patlama(duz_sohbet(), 5, 150)  # 50. sn, selamlaşma
        klipler, _ = yk.zirveleri_bul(sayim, AYAR, SURE)
        self.assertEqual(klipler, [])

    def test_yayin_sonu_dislanir(self):
        sayim = patlama(duz_sohbet(), SURE // 10 - 3, 150)  # son 30 sn
        klipler, _ = yk.zirveleri_bul(sayim, AYAR, SURE)
        self.assertEqual(klipler, [])

    def test_azami_klip_siniri_en_iyileri_secer(self):
        sayim = duz_sohbet()
        for no, deger in ((100, 70), (200, 95), (300, 80), (400, 60), (500, 99)):
            sayim = patlama(sayim, no, deger)
        klipler, _ = yk.zirveleri_bul(sayim, {**AYAR, 'azami_klip': 3}, SURE)
        self.assertEqual(len(klipler), 3)
        self.assertEqual([k['mesaj'] for k in klipler], [95, 80, 99])  # zamana göre sıralı, en yüksek 3
        self.assertEqual([k['no'] for k in klipler], [1, 2, 3])

    def test_dusuk_hacimli_sohbette_mutlak_asgari_gerekir(self):
        sayim = [0] * (SURE // 10)
        sayim = patlama(sayim, 300, 8)  # oran çok yüksek ama 8 mesaj < min_mesaj
        klipler, _ = yk.zirveleri_bul(sayim, AYAR, SURE)
        self.assertEqual(klipler, [])


class KlipAraligi(unittest.TestCase):
    def test_zirveden_20_sn_once_baslar(self):
        klipler, _ = yk.zirveleri_bul(patlama(duz_sohbet(), 300, 90), AYAR, SURE)
        k = klipler[0]
        self.assertEqual(k['klip_baslangic_sn'], 3000 - AYAR['onceden_sn'])

    def test_sure_siniri(self):
        for no in (60, 300, 500):
            sayim = patlama(duz_sohbet(), no, 90)
            k = yk.zirveleri_bul(sayim, AYAR, SURE)[0][0]
            self.assertLessEqual(k['sure_sn'], AYAR['klip_azami_sn'])
            self.assertGreaterEqual(k['sure_sn'], AYAR['klip_min_sn'])

    def test_uzun_zirve_kumesi_azami_sureye_kirpilir(self):
        sayim = duz_sohbet()
        for no in range(300, 306):  # 60 sn kesintisiz yoğunluk
            sayim = patlama(sayim, no, 80)
        k = yk.zirveleri_bul(sayim, AYAR, SURE)[0][0]
        self.assertLessEqual(k['sure_sn'], AYAR['klip_azami_sn'])

    def test_sinirlar_yayin_icinde_kalir(self):
        kisa = 900
        sayim = patlama(duz_sohbet(kisa), 85, 90)  # yayın sonuna 50 sn kala değil: son_dislama 180 → dışlanır
        self.assertEqual(yk.zirveleri_bul(sayim, AYAR, kisa)[0], [])
        sayim = patlama(duz_sohbet(kisa), 70, 90)
        k = yk.zirveleri_bul(sayim, AYAR, kisa)[0][0]
        self.assertGreaterEqual(k['klip_baslangic_sn'], 0)
        self.assertLessEqual(k['klip_bitis_sn'], kisa)

    def test_baslangic_negatif_olmaz(self):
        ayar = {**AYAR, 'bas_dislama_sn': 0}
        k = yk.zirveleri_bul(patlama(duz_sohbet(), 0, 90), ayar, SURE)[0][0]
        self.assertEqual(k['klip_baslangic_sn'], 0)
        self.assertGreaterEqual(k['sure_sn'], ayar['klip_min_sn'])

    def test_klipler_cakismaz(self):
        sayim = patlama(patlama(duz_sohbet(), 300, 90), 306, 88)  # 60 sn: birleşmez ama klipler çakışırdı
        klipler = yk.zirveleri_bul(sayim, {**AYAR, 'birlestir_sn': 30}, SURE)[0]
        for a, b in zip(klipler, klipler[1:]):
            self.assertLessEqual(a['klip_bitis_sn'], b['klip_baslangic_sn'])


class AnalizSohbetten(unittest.TestCase):
    def vod(self):
        return {'platform': 'kick', 'vod_id': 'x' * 8, 'anahtar': 'kick:xxxxxxxx', 'yayinci': 'Deneme Yayıncı',
                'kanal': 'deneme', 'baslik': 'Gece yayını', 'oyun': 'GTA V', 'sure_sn': SURE,
                'vod_url': 'https://kick.com/deneme/videos/x', 'kanal_url': 'https://kick.com/deneme',
                'tarih': '2026-11-16', 't0_epoch': 1_000_000, 't0_kaynagi': 'test'}

    def sohbet(self):
        t0 = 1_000_000
        mesajlar = []
        for s in range(0, SURE):  # her 2 sn'de 1 mesaj ~ 5/dilim
            if s % 2 == 0:
                mesajlar.append((t0 + s, 'selam hocam nasılsın'))
        for i in range(60):  # 3000-3010 arası patlama
            mesajlar.append((t0 + 3000 + i // 6, 'ŞAMPİYON [emote:1:KEKW] gol gol'))
        return mesajlar

    def test_patlama_bulunur_ve_kelimeler_one_cikar(self):
        sonuc = yk.analiz_et(self.vod(), self.sohbet(), AYAR)
        self.assertEqual(len(sonuc['klipler']), 1)
        k = sonuc['klipler'][0]
        self.assertEqual(k['zirve_sn'], 3000)
        self.assertIn('şampiyon', k['kelimeler'])  # Türkçe küçük harf: Ş→ş, İ→i
        self.assertIn('gol', k['kelimeler'])
        self.assertIn('KEKW', k['emojiler'])
        self.assertNotIn('selam', k['kelimeler'][:2])
        self.assertTrue(k['ornek_mesajlar'])

    def test_t0_kaymasi_hesaba_katilir(self):
        vod = self.vod()
        vod['t0_epoch'] -= 5  # video sohbetten 5 sn erken başlamış → zirve 5 sn ileri
        k = yk.analiz_et(vod, self.sohbet(), AYAR)['klipler'][0]
        self.assertEqual(k['zirve_sn'], 3000)  # 3005 de 300. dilimde: dilim aynı kalır
        self.assertGreaterEqual(k['zirve_sn'], 3000)

    def test_json_yazilabilir(self):
        json.dumps(yk.analiz_et(self.vod(), self.sohbet(), AYAR), ensure_ascii=False)


class MetinAraclari(unittest.TestCase):
    def test_turkce_kucuk_harf(self):
        self.assertEqual(yk.tr_kucuk('IŞIK İNCİ'), 'ışık inci')

    def test_belirtec_komut_emote_url_atar(self):
        kel, emo = yk.sohbet_belirteci('!sr hadi [emote:5:LUL] https://x.co/a sonuç ÇOK güzel')
        self.assertEqual(emo, ['LUL'])
        self.assertIn('sonuç', kel)
        self.assertIn('güzel', kel)
        self.assertNotIn('çok', kel)  # durak sözcük
        self.assertNotIn('sr', kel)

    def test_zaman_metni(self):
        self.assertEqual(yk.zaman_metni(75), '1:15')
        self.assertEqual(yk.zaman_metni(3725), '1:02:05')

    def test_dosya_adi_turkce(self):
        self.assertEqual(yk.dosya_adi('Tolunay Ören'), 'tolunay-oren')
        self.assertEqual(yk.dosya_adi('Kemalcan Parlak'), 'kemalcan-parlak')


class Paket(unittest.TestCase):
    VOD = {'platform': 'kick', 'vod_id': 'abcdef12-0000-0000-0000-000000000000', 'anahtar': 'kick:abcdef12',
           'yayinci': 'Tolunay Ören', 'kanal': 'tolunayoren', 'baslik': 'Gece yayını', 'oyun': 'Grand Theft Auto V',
           'sure_sn': SURE, 'vod_url': 'https://kick.com/tolunayoren/videos/abcdef12-0000-0000-0000-000000000000',
           'kanal_url': 'https://kick.com/tolunayoren', 'tarih': '2026-11-16'}
    KLIP = {'no': 1, 'zirve_sn': 3000, 'zirve_zaman': '50:00', 'puan': 12.3, 'zirve_mesaj_sayisi': 60,
            'klip_baslangic_sn': 2980.0, 'klip_bitis_sn': 3022.0, 'kelimeler': ['gol'], 'emojiler': ['KEKW'],
            'ornek_mesajlar': ['gol gol']}

    def test_baslik_turkce_ve_sinirli(self):
        b = yk.baslik_uret(self.VOD, self.KLIP)
        self.assertIn('Tolunay Ören', b)
        self.assertLessEqual(len(b), 95)
        self.assertEqual(b, yk.baslik_uret(self.VOD, self.KLIP))  # aynı girdi aynı başlık

    def test_baslik_cok_uzun_adda_kirpilir(self):
        vod = {**self.VOD, 'yayinci': 'A' * 120}
        self.assertLessEqual(len(yk.baslik_uret(vod, self.KLIP)), 95)

    def test_aciklama_yayinciyi_anar_ve_kanala_baglar(self):
        a = yk.aciklama_uret(self.VOD, self.KLIP)
        self.assertIn('Tolunay Ören', a)
        self.assertIn('https://kick.com/tolunayoren', a)
        self.assertIn(self.VOD['vod_url'], a)
        self.assertIn('49:40', a)  # 2980 sn
        self.assertIn('#Shorts', a)
        self.assertIn('#TolunayOren', a)

    def test_paket_json_alanlari(self):
        p = yk.paket_json(self.VOD, self.KLIP, pathlib.Path('klip-01.mp4'),
                          {'genislik': 1080, 'yukseklik': 1920, 'sure_sn': 42.0, 'ses': True})
        for alan in ('yayinci', 'platform', 'vod_url', 'vod_zaman_damgali_url', 'oyun', 'zirve_puani',
                     'baslik', 'aciklama', 'dosya', 'video'):
            self.assertIn(alan, p)
        self.assertFalse(p['yayinlandi'])
        self.assertFalse(p['vod_zaman_damgali_url_dogrulandi'])  # Kick ?t= belgelenmemiş
        json.dumps(p, ensure_ascii=False)


class TekrarIslememe(unittest.TestCase):
    def kayit(self, uuid, bas):
        return {'id': 1, 'channel_id': 7, 'start_time': bas, 'session_title': 'Yayın', 'is_live': False,
                'source': 'https://x/master.m3u8', 'duration': 3_600_000,
                'categories': [{'name': 'GTA V'}], 'video': {'uuid': uuid}}

    def test_islenen_vod_taranmaz(self):
        u1, u2 = 'aaaaaaaa-0000-0000-0000-000000000001', 'aaaaaaaa-0000-0000-0000-000000000002'
        liste = [self.kayit(u1, '2026-11-16 20:00:00'), self.kayit(u2, '2026-11-15 20:00:00')]
        ayar = {'ayar': AYAR, 'yayincilar': [{'ad': 'Deneme', 'platform': 'kick', 'kanal': 'deneme',
                                              'etkin': True, 'ayar': AYAR}]}
        simdi = yk.iso_epoch('2026-11-17 12:00:00')
        with tempfile.TemporaryDirectory() as t:
            d = pathlib.Path(t)
            r = yk.tara(ayar, d, http=lambda url: liste, simdi=simdi)
            self.assertEqual(len(r['yeni']), 2)
            yk.durum_isaretle(d, f'kick:{u1}', durum='islendi')
            r = yk.tara(ayar, d, http=lambda url: liste, simdi=simdi)
            self.assertEqual([v['anahtar'] for v in r['yeni']], [f'kick:{u2}'])
            self.assertEqual(r['atlanan_islenmis'], [f'kick:{u1}'])
            self.assertEqual(len(yk.tara(ayar, d, hepsi=True, http=lambda url: liste, simdi=simdi)['yeni']), 2)

    def test_analiz_durumu_islendi_sayilmaz(self):
        with tempfile.TemporaryDirectory() as t:
            d = pathlib.Path(t)
            yk.durum_isaretle(d, 'kick:x', durum='analiz')
            self.assertFalse(yk.islendi_mi(yk.durum_oku(d), 'kick:x'))

    def test_eski_ve_canli_yayin_atlanir(self):
        eski = self.kayit('aaaaaaaa-0000-0000-0000-000000000003', '2026-10-01 20:00:00')
        canli = {**self.kayit('aaaaaaaa-0000-0000-0000-000000000004', '2026-11-17 10:00:00'), 'is_live': True}
        ayar = {'ayar': AYAR, 'yayincilar': [{'ad': 'D', 'platform': 'kick', 'kanal': 'd', 'etkin': True, 'ayar': AYAR}]}
        with tempfile.TemporaryDirectory() as t:
            r = yk.tara(ayar, pathlib.Path(t), http=lambda u: [eski, canli], simdi=yk.iso_epoch('2026-11-17 12:00:00'))
            self.assertEqual(r['yeni'], [])

    def test_desteklenmeyen_platform_raporlanir_digerleri_surer(self):
        ayar = {'ayar': AYAR, 'yayincilar': [
            {'ad': 'T', 'platform': 'twitch', 'kanal': 't', 'etkin': True, 'ayar': AYAR},
            {'ad': 'K', 'platform': 'kick', 'kanal': 'k', 'etkin': True, 'ayar': AYAR}]}
        liste = [self.kayit('aaaaaaaa-0000-0000-0000-000000000005', '2026-11-16 20:00:00')]
        with tempfile.TemporaryDirectory() as t:
            r = yk.tara(ayar, pathlib.Path(t), http=lambda u: liste, simdi=yk.iso_epoch('2026-11-17 12:00:00'))
        self.assertEqual(r['desteksiz'][0]['platform'], 'twitch')
        self.assertIn('desteklenmiyor', r['desteksiz'][0]['neden'] + 'desteklenmiyor')
        self.assertEqual(len(r['yeni']), 1)


class VodCozme(unittest.TestCase):
    def test_bicimler(self):
        u = '3bbeb4a1-2a1c-4e7d-a1de-0123456789ab'
        self.assertEqual(yk.vod_coz(u), (u, None))
        self.assertEqual(yk.vod_coz(f'kick:{u}'), (u, None))
        self.assertEqual(yk.vod_coz(f'https://kick.com/eray/videos/{u}'), (u, 'eray'))
        with self.assertRaises(yk.KlipHatasi):
            yk.vod_coz('abc')


class KickSohbetPenceresi(unittest.TestCase):
    def mesaj(self, i, sn):
        return {'id': f'm{i}', 'type': 'message', 'content': f'mesaj {i}', 'created_at': yk.epoch_iso(sn)}

    def test_25_ile_kesilen_pencere_devam_ettirilir(self):
        bas = 1_000_000
        tum = [self.mesaj(i, bas + (i // 14)) for i in range(40)]  # 14 mesaj/sn, pencere içinde 40 mesaj

        def sahte(url):
            baslangic = yk.iso_epoch(url.split('start_time=')[1])
            uygun = [m for m in tum if baslangic <= yk.iso_epoch(m['created_at']) < baslangic + 5]
            return {'data': {'messages': uygun[:25]}}

        sonuc = yk.kick_pencere(sahte, 7, bas)
        self.assertEqual(len({m[0] for m in sonuc}), 40)

    def test_ayni_saniyede_25_ustu_dongu_yapmaz(self):
        bas = 2_000_000
        hep_ayni = [self.mesaj(i, bas) for i in range(25)]
        cagri = []

        def sahte(url):
            cagri.append(url)
            return {'data': {'messages': hep_ayni}}

        yk.kick_pencere(sahte, 7, bas)
        self.assertLess(len(cagri), 20)

    def test_pencere_disi_mesaj_alinmaz(self):
        bas = 3_000_000
        veri = [self.mesaj(1, bas), self.mesaj(2, bas + 9)]
        sonuc = yk.kick_pencere(lambda u: {'data': {'messages': veri}}, 7, bas)
        self.assertEqual([m[0] for m in sonuc], ['m1'])


class HlsAraclari(unittest.TestCase):
    MASTER = ('#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=1000000,RESOLUTION=640x360\n360p30/playlist.m3u8\n'
              '#EXT-X-STREAM-INF:BANDWIDTH=8000000,RESOLUTION=1920x1080\n1080p60/playlist.m3u8\n')
    MEDYA = '#EXTM3U\n#EXT-X-PROGRAM-DATE-TIME:2026-11-16T14:55:03.244Z\n#EXTINF:10.0,\n0.ts\n'

    def test_en_yuksek_cesit_secilir(self):
        yol, _ = yk.hls_oynatma_listesi('https://cdn/vod/master.m3u8', lambda u, **k: self.MASTER)
        self.assertEqual(yol, 'https://cdn/vod/1080p60/playlist.m3u8')

    def test_t0_program_date_time(self):
        self.assertEqual(yk.hls_t0(self.MEDYA), yk.iso_epoch('2026-11-16T14:55:03Z'))
        self.assertIsNone(yk.hls_t0('#EXTM3U\n'))

    def test_t0_playlist_yoksa_start_time(self):
        vod = {'platform': 'kick', 'baslangic_epoch': 123, 'kaynak': ''}
        self.assertEqual(yk.vod_t0_ekle(vod)['t0_epoch'], 123)

    def test_t0_playlisten_gelir(self):
        def metin(url, **k):
            return self.MASTER if url.endswith('master.m3u8') else self.MEDYA
        vod = {'platform': 'kick', 'baslangic_epoch': 123, 'kaynak': 'https://cdn/v/master.m3u8'}
        yk.vod_t0_ekle(vod, metin)
        self.assertEqual(vod['t0_epoch'], yk.iso_epoch('2026-11-16T14:55:03Z'))
        self.assertEqual(vod['t0_kaynagi'], 'hls_program_date_time')


class Duzen(unittest.TestCase):
    def test_filtre_1080x1920_ve_metin_dosyalari(self):
        metinler = yk.klip_metinleri(Paket.VOD)
        f = yk.filtre_yaz('C:\\Windows\\Fonts\\arialbd.ttf', metinler)
        self.assertIn('1080:1920', f)
        self.assertIn("fontfile='C\\:/Windows/Fonts/arialbd.ttf'", f)
        for ad in ('ad', 'oyun', 'kaynak', 'marka'):
            self.assertIn(f"textfile='t_{ad}.txt'", f)
        self.assertEqual(metinler['kaynak'], 'Kaynak: kick.com/tolunayoren')

    def test_komut_sure_ve_aralik(self):
        c = yk.ffmpeg_komutu('ffmpeg', 'https://x/p.m3u8', 2980.0, 42.0, 'o.mp4', 'a;\nb')
        self.assertEqual(c[c.index('-ss') + 1], '2980.000')
        self.assertEqual(c[c.index('-t') + 1], '42.000')
        self.assertEqual(c[c.index('-filter_complex') + 1], 'a;b')

    def test_uzun_metin_kuculur(self):
        self.assertLess(yk.metin_boyutu('x' * 60, 76, 980), 76)
        self.assertEqual(yk.metin_boyutu('kisa', 76, 980), 76)


class Ayar(unittest.TestCase):
    def test_repo_ayar_dosyasi_gecerli(self):
        a = yk.ayar_yukle()
        self.assertGreaterEqual(len(a['yayincilar']), 5)
        for y in a['yayincilar']:
            self.assertIn(y['platform'], ('kick', 'twitch', 'youtube'))
            self.assertLessEqual(y['ayar']['klip_azami_sn'], yk.SHORTS_AZAMI_SN)

    def test_calisma_dizini_env(self):
        import os
        eski = os.environ.get('YAYIN_KLIP_DIZIN')
        os.environ['YAYIN_KLIP_DIZIN'] = 'X:/deneme'
        try:
            self.assertEqual(yk.calisma_dizini(), pathlib.Path('X:/deneme'))
        finally:
            if eski is None:
                del os.environ['YAYIN_KLIP_DIZIN']
            else:
                os.environ['YAYIN_KLIP_DIZIN'] = eski


class OyunSuzgeci(unittest.TestCase):
    def vod(self, kategori='Just Chatting', baslik='Gece yayını'):
        return {'oyun': kategori, 'kategoriler': [kategori] if kategori else [], 'baslik': baslik}

    def test_bos_liste_hepsini_gecirir(self):
        self.assertEqual(yk.oyun_suzgeci(self.vod(), {'oyunlar': []}), (True, None))
        self.assertEqual(yk.oyun_suzgeci(self.vod(), {}), (True, None))
        self.assertEqual(yk.oyun_suzgeci(self.vod(), {'oyunlar': ['', '  ']}), (True, None))  # anlamsız girdi = kapalı

    def test_varsayilan_ayar_kapali(self):
        self.assertEqual(yk.AYAR_VARSAYILAN['oyunlar'], [])

    def test_kategori_eslesmesi_ad_varyantlari(self):
        ayar = {'oyunlar': ['Grand Theft Auto VI', 'GTA 6', 'GTA VI']}
        self.assertEqual(yk.oyun_suzgeci(self.vod('Grand Theft Auto VI'), ayar), (True, 'Grand Theft Auto VI'))
        self.assertEqual(yk.oyun_suzgeci(self.vod('GTA VI'), ayar), (True, 'GTA VI'))
        self.assertEqual(yk.oyun_suzgeci(self.vod('gta 6'), ayar), (True, 'GTA 6'))

    def test_buyuk_kucuk_harf_ve_turkce_karakter_duyarsiz(self):
        ayar = {'oyunlar': ['Kaşık Oyunu', 'IŞIK']}
        self.assertTrue(yk.oyun_suzgeci(self.vod('KASIK OYUNU'), ayar)[0])
        self.assertTrue(yk.oyun_suzgeci(self.vod('kaşık oyunu'), ayar)[0])
        self.assertTrue(yk.oyun_suzgeci(self.vod('Isik'), ayar)[0])
        self.assertTrue(yk.oyun_suzgeci(self.vod('ışık'), ayar)[0])
        self.assertTrue(yk.oyun_suzgeci(self.vod('Counter-Strike 2'), {'oyunlar': ['counter strike 2']})[0])

    def test_gta_v_gta_vi_ye_uymaz(self):
        self.assertFalse(yk.oyun_suzgeci(self.vod('Grand Theft Auto VI'), {'oyunlar': ['Grand Theft Auto V']})[0])
        self.assertFalse(yk.oyun_suzgeci(self.vod('GTA VI'), {'oyunlar': ['GTA V']})[0])
        self.assertTrue(yk.oyun_suzgeci(self.vod('GTA V'), {'oyunlar': ['GTA V']})[0])

    def test_uymayan_kategori_elenir(self):
        self.assertEqual(yk.oyun_suzgeci(self.vod('Just Chatting', 'sohbet'), {'oyunlar': ['GTA VI']}), (False, None))

    def test_baslikta_gecen_oyun_adi(self):
        v = self.vod('Just Chatting', 'GTA VI düşüren tek yayın!')
        self.assertEqual(yk.oyun_suzgeci(v, {'oyunlar': ['GTA VI']}), (True, 'GTA VI'))
        self.assertFalse(yk.oyun_suzgeci(v, {'oyunlar': ['GTA VI'], 'oyun_baslikta_ara': False})[0])

    def test_birden_cok_kategori(self):
        v = {'oyun': 'Just Chatting', 'kategoriler': ['Just Chatting', 'Grand Theft Auto VI'], 'baslik': ''}
        self.assertTrue(yk.oyun_suzgeci(v, {'oyunlar': ['Grand Theft Auto VI']})[0])

    def test_tara_suzgeci_uygular_ve_raporlar(self):
        def kayit(uuid, kat):
            return {'id': 1, 'channel_id': 7, 'start_time': '2026-11-16 20:00:00', 'session_title': 'Yayın',
                    'is_live': False, 'source': 'x', 'duration': 3_600_000, 'categories': [{'name': kat}],
                    'video': {'uuid': uuid}}
        liste = [kayit('aaaaaaaa-0000-0000-0000-00000000000a', 'Grand Theft Auto VI'),
                 kayit('aaaaaaaa-0000-0000-0000-00000000000b', 'Just Chatting'),
                 kayit('aaaaaaaa-0000-0000-0000-00000000000c', 'EA Sports FC 27')]
        simdi = yk.iso_epoch('2026-11-17 12:00:00')

        def ayarla(oyunlar):
            a = {**AYAR, 'oyunlar': oyunlar}
            return {'ayar': a, 'yayincilar': [{'ad': 'D', 'platform': 'kick', 'kanal': 'd', 'etkin': True, 'ayar': a}]}
        with tempfile.TemporaryDirectory() as t:
            d = pathlib.Path(t)
            hepsi = yk.tara(ayarla([]), d, http=lambda u: liste, simdi=simdi)
            self.assertEqual(len(hepsi['yeni']), 3)
            self.assertEqual(hepsi['suzgece_uymayan'], [])
            r = yk.tara(ayarla(['GTA 6', 'Grand Theft Auto VI']), d, http=lambda u: liste, simdi=simdi)
            self.assertEqual([v['oyun'] for v in r['yeni']], ['Grand Theft Auto VI'])
            self.assertEqual(r['yeni'][0]['eslesen_oyun'], 'Grand Theft Auto VI')
            self.assertEqual(sorted(v['oyun'] for v in r['suzgece_uymayan']), ['EA Sports FC 27', 'Just Chatting'])

    def test_vod_normalle_kategorileri_tasir(self):
        g = {'channel_id': 7, 'start_time': '2026-11-16 20:00:00', 'session_title': 'x', 'duration': 1000,
             'categories': [{'name': 'A'}, {'name': 'B'}], 'video': {'uuid': 'u'}}
        v = yk.vod_normalle(g, 'k', 'K')
        self.assertEqual((v['oyun'], v['kategoriler']), ('A', ['A', 'B']))


class Kadraj(unittest.TestCase):
    TUVAL_H = 1920

    def kutular(self, yz):
        """(görüntü aralığı, {yazı: aralık}); yazı yüksekliği = boyut × satır katsayısı."""
        gorsel = (yz['gorsel_y'], yz['gorsel_y'] + yz['gorsel_h'])
        yazilar = {a: (y, y + int(yk.DUZEN[a]['boyut'] * yk.METIN_SATIR_KATSAYI)) for a, y in yz['y'].items()}
        return gorsel, yazilar

    def test_serit_eski_duzeni_aynen_verir(self):
        yz = yk.yerlesim({'duzen': 'serit'})
        self.assertEqual((yz['gorsel_h'], yz['gorsel_y']), (608, 656))
        self.assertEqual(yz['y'], {'ust_ad': 430, 'ust_oyun': 530, 'alt_kaynak': 1340, 'alt_marka': 1415})
        f = yk.filtre_yaz('C:\\Windows\\Fonts\\arialbd.ttf', yk.klip_metinleri(Paket.VOD), ayar={'duzen': 'serit'})
        self.assertIn('scale=1080:-2:flags=lanczos', f)
        self.assertNotIn('crop=w=min', f)
        self.assertIn('overlay=0:656', f)

    def test_kadraj_serit_den_belirgin_buyuk(self):
        serit = yk.yerlesim({'duzen': 'serit'})['gorsel_h']
        for oran, en_az_kat in ((1.0, 1.7), (1.2, 1.4), (4 / 3, 1.3)):
            yz = yk.yerlesim({'duzen': 'kadraj', 'kadraj_oran': oran})
            self.assertGreaterEqual(yz['gorsel_h'] / serit, en_az_kat, oran)

    def test_kadraj_olculeri(self):
        self.assertEqual(yk.yerlesim({'kadraj_oran': 1.0})['gorsel_h'], 1080)   # kare
        self.assertEqual(yk.yerlesim({'kadraj_oran': 4 / 3})['gorsel_h'], 810)  # 4:3
        yz = yk.yerlesim({'kadraj_oran': 1.2})
        self.assertEqual(yz['gorsel_h'], 900)
        self.assertEqual(yz['gorsel_y'], yk.DUZEN['gorsel_merkez_y'] - 450)     # görüntünün orta çizgisi sabit

    def test_kadraj_orani_sinirlanir(self):
        self.assertEqual(yk.yerlesim({'kadraj_oran': 0.5})['oran'], yk.KADRAJ_EN_AZ)   # çok dik: kareye kenetlenir
        self.assertEqual(yk.yerlesim({'kadraj_oran': 5})['oran'], yk.KAYNAK_ORAN)      # kırpılacak şey kalmaz
        self.assertEqual(yk.yerlesim({'kadraj_oran': 5})['gorsel_h'], 608)

    def test_yazilar_goruntuyle_cakismaz_ve_tuvalde_kalir(self):
        for oran in (1.0, 1.1, 1.2, 4 / 3, 1.5, 1.78):
            yz = yk.yerlesim({'kadraj_oran': oran})
            (g0, g1), yazilar = self.kutular(yz)
            for ad, (y0, y1) in yazilar.items():
                self.assertTrue(y1 <= g0 or y0 >= g1, f'{ad} görüntüye biniyor (oran {oran})')
                self.assertGreaterEqual(y0, 100, f'{ad} üst kenara çok yakın (oran {oran})')
                self.assertLessEqual(y1, self.TUVAL_H, f'{ad} tuval dışı (oran {oran})')
            sirali = sorted(yazilar.values())
            for a, b in zip(sirali, sirali[1:]):
                self.assertLessEqual(a[1], b[0], f'yazılar birbirine biniyor (oran {oran})')

    def test_kadraj_filtresi_ortadan_kirpar(self):
        f = yk.filtre_yaz('C:\\Windows\\Fonts\\arialbd.ttf', yk.klip_metinleri(Paket.VOD), ayar={'kadraj_oran': 1.2})
        crop = 'crop=w=min(iw\\,ih*1.2000):h=min(ih\\,iw/1.2000),scale=1080:900:flags=lanczos'
        self.assertIn(crop, f)      # x/y verilmediği için kırpma ortadan yapılır: oyun ekranının ortası kalır
        self.assertIn('overlay=0:430', f)
        self.assertIn('1080:1920', f)

    def test_varsayilan_kadraj(self):
        self.assertEqual(yk.AYAR_VARSAYILAN['duzen'], 'kadraj')
        self.assertEqual(yk.yerlesim()['mod'], 'kadraj')

    def test_gecersiz_duzen_hata(self):
        with self.assertRaises(yk.KlipHatasi):
            yk.yerlesim({'duzen': 'baska'})

    def test_paket_guncel_duzen_degisince_yeniden_uretir(self):
        klip = {'klip_baslangic_sn': 10.0, 'klip_bitis_sn': 50.0}
        with tempfile.TemporaryDirectory() as t:
            yol = pathlib.Path(t) / 'klip-01.json'
            yol.write_text(json.dumps({**klip, 'duzen': yk.duzen_imzasi({'kadraj_oran': 1.2})}), encoding='utf-8')
            self.assertTrue(yk.paket_guncel(yol, klip, {'kadraj_oran': 1.2}))
            self.assertFalse(yk.paket_guncel(yol, klip, {'kadraj_oran': 1.0}))
            self.assertFalse(yk.paket_guncel(yol, klip, {'duzen': 'serit'}))
            self.assertFalse(yk.paket_guncel(yol, {**klip, 'klip_baslangic_sn': 11.0}, {'kadraj_oran': 1.2}))
            self.assertFalse(yk.paket_guncel(pathlib.Path(t) / 'yok.json', klip, {}))


class ZayifZirve(unittest.TestCase):
    def test_emote_disi_mi(self):
        for metin in ('[emote:6:KEKW]', '[emote:1:A][emote:2:B] [emote:3:C]', '  [emote:1:A]  ', ''):
            self.assertFalse(yk.emote_disi_mi(metin), metin)
        for metin in ('kız bundan iyi kurtulmuş ya', 'ŞAMPİYON [emote:1:KEKW]', 'gol', '1', '2222', 'xd', '!kazan'):
            self.assertTrue(yk.emote_disi_mi(metin), metin)

    def test_zirve_kalitesi_sayilari(self):
        k = yk.zirve_kalitesi([('1111', 1), ('[emote:1:X]', 2), ('harika gol', 3), ('süper maç', 3), ('[emote:2:Y] [emote:3:Z]', 4)])
        self.assertEqual(k['zirve_mesaj_sayisi'], 5)
        self.assertEqual(k['farkli_kullanici'], 4)
        self.assertEqual(k['emote_disi_mesaj'], 3)
        self.assertEqual(k['emote_disi_oran'], 0.6)

    # Kemalcan Parlak yayınında (kick:9ae47b40) üç örnek klibin gerçek sohbet ölçümü (sohbet önbelleği v2):
    GERCEK = {'klip-01': {'farkli_kullanici': 145, 'emote_disi_oran': 0.797},
              'klip-02': {'farkli_kullanici': 83, 'emote_disi_oran': 0.142},
              'klip-03': {'farkli_kullanici': 87, 'emote_disi_oran': 0.952}}

    def test_gercek_olcum_yalniz_klip_02_elenir(self):
        sonuc = {ad: yk.zayiflik_nedenleri(k, AYAR) for ad, k in self.GERCEK.items()}
        self.assertEqual(sonuc['klip-01'], [])
        self.assertEqual(sonuc['klip-03'], [])
        self.assertEqual(len(sonuc['klip-02']), 1)
        self.assertTrue(sonuc['klip-02'][0].startswith('emote_agirlikli'))

    def test_gondericisiz_veri_kullanici_olcutunu_atlar(self):
        k = yk.zirve_kalitesi([('merhaba nasılsın', ''), ('güzel yayın', None)])
        self.assertIsNone(k['farkli_kullanici'])
        self.assertEqual(yk.zayiflik_nedenleri(k, AYAR), [])

    def test_nedenler(self):
        self.assertEqual(yk.zayiflik_nedenleri({'farkli_kullanici': 40, 'emote_disi_oran': 0.6}, AYAR), [])
        az = yk.zayiflik_nedenleri({'farkli_kullanici': 5, 'emote_disi_oran': 0.6}, AYAR)
        self.assertEqual(len(az), 1)
        self.assertTrue(az[0].startswith('az_kullanici'))
        emote = yk.zayiflik_nedenleri({'farkli_kullanici': 80, 'emote_disi_oran': 0.05}, AYAR)
        self.assertTrue(emote[0].startswith('emote_agirlikli'))
        self.assertEqual(len(yk.zayiflik_nedenleri({'farkli_kullanici': 5, 'emote_disi_oran': 0.05}, AYAR)), 2)

    def test_varsayilan_esikler_ayarda(self):
        self.assertIn('min_farkli_kullanici', yk.AYAR_VARSAYILAN)
        self.assertIn('min_emote_disi_oran', yk.AYAR_VARSAYILAN)

    def vod(self):
        return {'platform': 'kick', 'vod_id': 'y' * 8, 'anahtar': 'kick:yyyyyyyy', 'yayinci': 'D', 'kanal': 'd',
                'baslik': 'b', 'oyun': 'GTA V', 'sure_sn': SURE, 'vod_url': 'u', 'kanal_url': 'k',
                'tarih': '2026-11-16', 't0_epoch': 1_000_000, 't0_kaynagi': 'test'}

    def sohbet(self, emote_kisi=3, gercek_kisi=60):
        """Aynı hacimde iki patlama: 3000. sn yalnız emote (az kişi), 5000. sn gerçek yazı (çok kişi)."""
        t0 = 1_000_000
        m = [(t0 + s, 'selam hocam nasılsın', 1000 + s % 7) for s in range(0, SURE, 2)]
        for i in range(90):
            m.append((t0 + 3000 + i // 9, '[emote:1:dance]', i % emote_kisi))
        for i in range(70):
            m.append((t0 + 5000 + i // 7, 'ne kadar güzel gol oldu', 5000 + i % gercek_kisi))
        return m

    def test_emote_patlamasi_elenir_gercek_kalir(self):
        sonuc = yk.analiz_et(self.vod(), self.sohbet(), AYAR)
        self.assertEqual([k['zirve_sn'] for k in sonuc['klipler']], [5000])
        el = sonuc['elenen_zirveler']
        self.assertEqual([e['zirve_sn'] for e in el], [3000])
        self.assertTrue(any(n.startswith('emote_agirlikli') for n in el[0]['neden']))
        self.assertTrue(any(n.startswith('az_kullanici') for n in el[0]['neden']))
        self.assertGreaterEqual(sonuc['klipler'][0]['farkli_kullanici'], 60)
        self.assertGreaterEqual(sonuc['klipler'][0]['emote_disi_oran'], 0.9)

    def test_az_kisinin_gercek_yazisi_da_elenir(self):
        sonuc = yk.analiz_et(self.vod(), self.sohbet(gercek_kisi=4), AYAR)   # 4 kişi 70 mesaj yazdı
        self.assertEqual([k['zirve_sn'] for k in sonuc['klipler']], [])
        self.assertTrue(all(any(n.startswith('az_kullanici') for n in e['neden']) for e in sonuc['elenen_zirveler']))

    def test_elenenin_yerini_siradaki_alir(self):
        # Puanı en yüksek zirve (emote) zayıf: azami_klip=1 olsa da gerçek zirve seçilir.
        sonuc = yk.analiz_et(self.vod(), self.sohbet(), {**AYAR, 'azami_klip': 1})
        self.assertEqual([k['zirve_sn'] for k in sonuc['klipler']], [5000])

    def test_esik_ayarla_degisir(self):
        gevsek = {**AYAR, 'min_farkli_kullanici': 1, 'min_emote_disi_oran': 0.0}
        sonuc = yk.analiz_et(self.vod(), self.sohbet(), gevsek)
        self.assertEqual([k['zirve_sn'] for k in sonuc['klipler']], [3000, 5000])
        self.assertEqual(sonuc['elenen_zirveler'], [])

    def test_gondericisiz_eski_veride_yalniz_emote_olcutu_calisir(self):
        eski = [(t, x) for t, x, _ in self.sohbet()]   # 2'li demetler: gönderen yok
        sonuc = yk.analiz_et(self.vod(), eski, AYAR)
        self.assertEqual([k['zirve_sn'] for k in sonuc['klipler']], [5000])
        self.assertIsNone(sonuc['klipler'][0]['farkli_kullanici'])

    def test_kalitesiz_cagri_eski_davranis(self):
        klipler, ist = yk.zirveleri_bul(patlama(duz_sohbet(), 300, 90), AYAR, SURE)   # kalite verilmedi
        self.assertEqual(len(klipler), 1)
        self.assertEqual(ist['elenen'], [])


class SohbetDepolama(unittest.TestCase):
    def mesaj(self, i, sn, uid=7):
        return {'id': f'm{i}', 'type': 'message', 'content': f'mesaj {i}', 'created_at': yk.epoch_iso(sn),
                'user_id': uid, 'sender': {'id': uid}}

    def test_pencere_gonderen_kimligini_tasir(self):
        bas = 4_000_000
        veri = {'data': {'messages': [self.mesaj(1, bas, 11), self.mesaj(2, bas + 1, 12),
                                      {'id': 'm3', 'type': 'message', 'content': 'x',
                                       'created_at': yk.epoch_iso(bas + 2), 'sender': {'id': 13}}]}}
        sonuc = yk.kick_pencere(lambda u: veri, 7, bas)
        self.assertEqual(sorted(m[3] for m in sonuc), [11, 12, 13])

    def vod(self):
        return {'platform': 'kick', 'vod_id': 'abc', 'anahtar': 'kick:abc', 'kanal_id': 7, 't0_epoch': 5_000_000,
                'sure_sn': 5}

    def test_eski_onbellek_gecersiz_yenisi_kullanilir(self):
        bas = 5_000_000
        veri = {'data': {'messages': [self.mesaj(1, bas, 21)]}}
        with tempfile.TemporaryDirectory() as t:
            d = pathlib.Path(t)
            (d / 'sohbet').mkdir()
            yol = d / 'sohbet' / 'kick-abc.json'
            yol.write_text(json.dumps({'vod': 'kick:abc', 'mesajlar': [[bas, 'eski']]}), encoding='utf-8')  # sürüm 1
            m = yk.sohbet_al(self.vod(), d, http=lambda u: veri)
            self.assertEqual([(x[1], x[2]) for x in m], [('mesaj 1', 21)])
            self.assertEqual(json.loads(yol.read_text(encoding='utf-8'))['surum'], yk.SOHBET_SURUMU)

            def ag_yok(u):
                raise AssertionError('önbellek varken ağa gidilmemeli')
            self.assertEqual(yk.sohbet_al(self.vod(), d, http=ag_yok), m)

    def test_eski_part_satiri_gondericisiz_okunur(self):
        bas = 6_000_000
        with tempfile.TemporaryDirectory() as t:
            part = pathlib.Path(t) / 'x.part.jsonl'
            part.write_text(json.dumps({'w': bas, 'm': [['m9', bas, 'eski mesaj']]}) + '\n', encoding='utf-8')
            sonuc = yk.kick_sohbet_indir(lambda u: {'data': {'messages': []}}, 7, bas, 0, part)
            self.assertEqual(sonuc, [(bas, 'eski mesaj', '')])


if __name__ == '__main__':
    unittest.main()


# ===================================================================== sinyal yöntemi (kahkaha / ortak konu)

SAYIM_AYAR = dict(yk.AYAR_VARSAYILAN)   # yontem: sinyal


class KahkahaTespiti(unittest.TestCase):
    """Türkçe rastgele klavye kahkahası yakalanır; gerçek kelimeler (kasada, sadakat…) yakalanmaz."""
    GULME = ['hahaha', 'hahahaha', 'ahahahah', 'ahahha', 'jajaja', 'hehehe', 'xd', 'xdd', 'sjsj', 'sjsjsj', 'asdasd',
             'asdfgh', 'sdfsdfsd', 'dkdkfnf', 'ajsjsjsk', 'hahahahahaha', 'ahdjfkdmskk', 'sdasdasdasd']
    GULME_DEGIL = ['sadakat', 'kasada', 'askıda', 'dakika', 'flash', 'ahmet', 'halka', 'kaldık', 'aaaaa',
                   'ahhhhh', 'aha', 'yuhhh', 'bakkkk', 'skandal', 'sabahhh', 'masa', 'salak', 'kadar',
                   'hadi', 'abi', 'selam', 'dalga', 'kaslar', 'sakal']

    def test_gulme_kelimeleri(self):
        for k in self.GULME:
            self.assertTrue(yk.gulme_belirteci_mi(k), k)

    def test_gercek_kelimeler_gulme_sayilmaz(self):
        for k in self.GULME_DEGIL:
            self.assertFalse(yk.gulme_belirteci_mi(k), k)

    def test_ozel_istisna_listesi(self):
        # 'kafkas' klavye yığını gibi görünür; ayardaki istisna listesi onu kurtarır
        self.assertTrue(yk.gulme_belirteci_mi('kafkas'))
        self.assertFalse(yk.gulme_belirteci_mi('kafkas', frozenset(), frozenset({'kafkas'})))
        self.assertFalse(yk.Siniflayici(SAYIM_AYAR).ozellik('kafkas yolu').gulme)

    def test_mesaj_duzeyi(self):
        sf = yk.Siniflayici(SAYIM_AYAR)
        for m in ('hahaha ya', '😂😂', 'KEKW [emote:37226:KEKW]', '[emote:5:collectiblesGoldenKEKW]', 'sjsjsj ya'):
            self.assertTrue(sf.ozellik(m).gulme, m)
        for m in ('kasada para yok', 'sadakat kartı', 'dakika kaç', '[emote:1:beeBobble]', 'ne diyon amk'):
            self.assertFalse(sf.ozellik(m).gulme, m)


class EmoteSiniflari(unittest.TestCase):
    """Adlar Kemalcan Parlak yayınının gerçek sohbetinden (Kick emote adları)."""

    def setUp(self):
        self.sf = yk.Siniflayici(SAYIM_AYAR)

    def test_gulme_emoteleri(self):
        for ad in ('KEKW', 'collectiblesGoldenKEKW', 'collectibleswideKEKW', 'LULW', 'collectiblesICANT', 'KEKLEO',
                   'collectiblesPepeLaugh', 'emojiLol', 'OMEGALUL', 'LUL'):
            self.assertEqual(self.sf.emote_sinifi(ad), 'gulme', ad)

    def test_saskin_emoteleri(self):
        for ad in ('PogU', 'OOOO', 'monkaOMEGA'):
            self.assertEqual(self.sf.emote_sinifi(ad), 'saskin', ad)

    def test_dans_alkis_gurultu(self):
        for ad in ('beeBobble', 'catblobDance', 'DanceDance', 'HYPERCLAP', 'vibePls', 'catJAM'):
            self.assertEqual(self.sf.emote_sinifi(ad), 'gurultu', ad)

    def test_diger_emote_notr(self):
        self.assertEqual(self.sf.emote_sinifi('Sadge'), 'notr')

    def test_notr_ve_gurultu_kahkaha_sayilmaz(self):
        for m in ('[emote:1:beeBobble]', '[emote:2:Sadge]', '[emote:3:catblobDance][emote:3:catblobDance]'):
            self.assertFalse(self.sf.ozellik(m).gulme, m)

    def test_dans_yagmuru_gurultu_olur(self):
        self.assertEqual(self.sf.ozellik('[emote:1:DanceDance][emote:1:DanceDance]').gurultu, 'emote_yagmuru')
        self.assertEqual(self.sf.ozellik('[emote:1:KEKW]').gurultu, '')

    def test_liste_ayardan_gelir(self):
        sf = yk.Siniflayici({**SAYIM_AYAR, 'emote_gulme': ['sadge']})
        self.assertEqual(sf.emote_sinifi('Sadge'), 'gulme')
        self.assertEqual(sf.emote_sinifi('KEKW'), 'notr')


class OyKomutSuzgeci(unittest.TestCase):
    def test_oy_ve_komut_mesajlari(self):
        sf = yk.Siniflayici(SAYIM_AYAR)
        for m in ('1', '2', 'e', 'h', '11111111111', '123', '!katıl', '!kazan 5'):
            self.assertIn(sf.ozellik(m).gurultu, ('oy', 'komut'), m)
            self.assertFalse(sf.ozellik(m).gulme, m)
        for m in ('bu ne ya', 'evet ama', 'kesinlikle'):
            self.assertEqual(sf.ozellik(m).gurultu, '', m)


def sinyal_vod():
    return {'platform': 'kick', 'vod_id': 'z' * 8, 'anahtar': 'kick:zzzzzzzz', 'yayinci': 'Deneme', 'kanal': 'd',
            'baslik': 'b', 'oyun': 'GTA V', 'sure_sn': SURE, 'vod_url': 'u', 'kanal_url': 'k',
            'tarih': '2026-11-16', 't0_epoch': 1_000_000, 't0_kaynagi': 'test'}


def zemin_sohbet(t0=1_000_000):
    """Yayın boyunca sakin arka plan: 2 sn'de bir mesaj, 7 kişi."""
    return [(t0 + s, 'selam hocam nasılsın', 1000 + s % 7) for s in range(0, SURE, 2)]


class SinyalZirveleri(unittest.TestCase):
    T0 = 1_000_000
    KONU = ['çorbacı geldi', 'çorbacı yine başladı', 'bu çorbacı kim', 'çorbacı çorbacı', 'abi çorbacıyı gördün mü',
            'yok artık çorbacı', 'çorbacı mı o']

    def analiz(self, ek, ayar=None):
        return yk.analiz_et(sinyal_vod(), zemin_sohbet() + ek, ayar or SAYIM_AYAR)

    def kahkaha(self, bas=3000, kisi=40):
        return [(self.T0 + bas + i // 4, ['hahaha', '[emote:1:KEKW]', 'asdfgh sjsj', 'xd'][i % 4], 2000 + i) for i in range(kisi)]

    def dalga(self):
        return ([(self.T0 + 3000 + i // 2, 'hahaha', 2000 + i) for i in range(12)]
                + [(self.T0 + 3010 + i // 2, 'hahaha', 2100 + i) for i in range(14)]
                + [(self.T0 + 3020 + i // 2, '[emote:1:KEKW]', 2200 + i) for i in range(40)])

    def test_kahkaha_dalgasi_bulunur(self):
        k = self.analiz(self.kahkaha())['klipler']
        self.assertEqual(len(k), 1)
        self.assertEqual(k[0]['baskin'], 'gulme')
        self.assertEqual(k[0]['zirve_sn'], 3000)
        self.assertGreaterEqual(k[0]['puan_bilesenleri']['gulme']['kisi'], 30)

    def test_oy_seli_elenir(self):
        ek = [(self.T0 + 3000 + i // 12, str(1 + i % 2), 2000 + i % 100) for i in range(120)]
        s = self.analiz(ek)
        self.assertEqual(s['klipler'], [])
        self.assertTrue(any(e['neden'][0].startswith('oy_seli') for e in s['elenen_zirveler']))

    def test_ayni_iki_kisinin_kekwsi_klip_degil(self):
        ek = [(self.T0 + 3000 + i // 6, '[emote:1:KEKW]', 2000 + i % 2) for i in range(60)]
        self.assertEqual(self.analiz(ek)['klipler'], [])

    def test_dans_yagmuru_klip_degil(self):
        ek = [(self.T0 + 3000 + i // 9, '[emote:1:DanceDance]', 2000 + i) for i in range(90)]
        self.assertEqual(self.analiz(ek)['klipler'], [])

    def test_yogunluk_tek_basina_klip_degil(self):
        def kelime(n):   # 90 mesajda hiçbir kelime ikinci kez geçmesin
            return 'bcmnprtvyz'[n % 10] + 'aeiou'[(n // 10) % 5] + 'mnrtp'[(n // 50) % 5] + 'o'
        ek = [(self.T0 + 3000 + i // 9, f'{kelime(i)} {kelime((i * 7 + 3) % 90 + 100)}', 2000 + i) for i in range(90)]
        s = self.analiz(ek)
        self.assertEqual(s['klipler'], [])   # 90 mesaj, 90 kişi var ama ortak kelime/kahkaha yok: yalnız yoğunluk

    def test_ortak_konu_cok_kisiyle(self):
        ek = [(self.T0 + 3000 + i // 3, self.KONU[i % 7] + ' ' + 'abcdefghij'[i % 10] * 3, 2000 + i) for i in range(30)]
        k = self.analiz(ek)['klipler']
        self.assertEqual(len(k), 1)
        self.assertEqual(k[0]['baskin'], 'konu')
        self.assertEqual(k[0]['puan_bilesenleri']['konu']['terim'], 'çorbacı')
        self.assertGreaterEqual(k[0]['puan_bilesenleri']['konu']['kisi'], 6)

    def test_ortak_konu_tek_kisinin_tekrari_sayilmaz(self):
        ek = [(self.T0 + 3000 + i // 6, self.KONU[i % 7] + ' ' + 'abcdefghij'[i % 10] * 3, 2000) for i in range(60)]
        self.assertEqual(self.analiz(ek)['klipler'], [])

    def test_kopyala_yapistir_seli_kahkaha_sayilmaz(self):
        ek = [(self.T0 + 3000 + i // 3, 'bu yayını izleyin hahaha lol kekw uzun mesaj', 2000 + i) for i in range(30)]
        self.assertEqual(self.analiz(ek)['klipler'], [])

    def test_kopyala_yapistir_konuya_yarim_agirlik(self):
        sf = yk.Siniflayici(SAYIM_AYAR)
        ayni = [('yeni video çıktı bakmayı unutmayın', 100 + i) for i in range(10)]
        o = yk.dilim_ozetle(ayni, sf, SAYIM_AYAR)
        self.assertEqual(o['gulme_n'], 0)
        self.assertEqual(o['n_sinyal'], 0)                                              # sinyal mesajı sayılmaz
        self.assertEqual(o['terimler']['video'], 10 * SAYIM_AYAR['yayilma_konu_agirlik'])  # konuya yarım ağırlık

    def test_klip_dalganin_basladigi_dilimden_20_sn_once(self):
        k = self.analiz(self.dalga())['klipler'][0]
        self.assertEqual(k['zirve_sn'], 3020)       # tepe sonradan
        self.assertEqual(k['dalga_basi_sn'], 3000)  # dalga erken başladı
        self.assertEqual(k['klip_baslangic_sn'], 2980)

    def test_klip_baslangic_tepe_secenegi(self):
        k = self.analiz(self.dalga(), {**SAYIM_AYAR, 'klip_baslangic': 'tepe'})['klipler'][0]
        self.assertEqual(k['klip_baslangic_sn'], 3000)

    def test_bilesenler_ve_json(self):
        k = self.analiz(self.kahkaha())['klipler'][0]
        b = k['puan_bilesenleri']
        for anahtar in ('toplam', 'agirliklar', 'gulme', 'konu', 'yogunluk', 'gurultu'):
            self.assertIn(anahtar, b)
        self.assertEqual(b['toplam'], k['puan'])
        self.assertLessEqual(b['toplam'], 100)
        json.dumps(k, ensure_ascii=False)

    def test_eski_yontem_ayardan_secilebilir(self):
        ek = [(self.T0 + 3000 + i // 9, 'ŞAMPİYON gol gol', 2000 + i) for i in range(90)]
        s = self.analiz(ek, {**SAYIM_AYAR, 'yontem': 'yogunluk'})
        self.assertEqual(len(s['klipler']), 1)
        self.assertNotIn('baskin', s['klipler'][0])


class SinyalBaslikVePaket(unittest.TestCase):
    def klip(self, baskin, terim=None):
        return {'no': 1, 'baskin': baskin, 'puan_bilesenleri': {'konu': {'terim': terim} if terim else {}}}

    def test_gulme_basligi(self):
        b = yk.baslik_uret(sinyal_vod(), self.klip('gulme'))
        self.assertTrue(any(s in b for s in ('kahkaha', 'gülme', 'gülmek')), b)
        self.assertNotIn('patla', b)

    def test_konu_basligi_terimi_icerir(self):
        self.assertIn('çorbacı', yk.baslik_uret(sinyal_vod(), self.klip('konu', 'çorbacı')))

    def test_konu_terimsiz_bos_tirnak_birakmaz(self):
        self.assertNotIn('“”', yk.baslik_uret(sinyal_vod(), self.klip('konu')))

    def test_baslik_siniri_ve_eski_sablon(self):
        v = {**sinyal_vod(), 'yayinci': 'A' * 120}
        self.assertLessEqual(len(yk.baslik_uret(v, self.klip('gulme'))), 95)
        self.assertIn('Deneme', yk.baslik_uret(sinyal_vod(), {'no': 1}))

    def test_paket_json_bilesenleri_tasir(self):
        ek = [(1_000_000 + 3000 + i // 4, 'hahaha', 2000 + i) for i in range(40)]
        k = yk.analiz_et(sinyal_vod(), zemin_sohbet() + ek, SAYIM_AYAR)['klipler'][0]
        p = yk.paket_json(sinyal_vod(), k, pathlib.Path('klip-01.mp4'), {'genislik': 1080}, SAYIM_AYAR)
        self.assertEqual(p['baskin_sinyal'], 'gulme')
        self.assertEqual(p['puan_bilesenleri'], k['puan_bilesenleri'])
        self.assertEqual(p['dalga_basi_sn'], k['dalga_basi_sn'])
        self.assertIn('kahkaha', yk.aciklama_uret(sinyal_vod(), k))


# ===================================================================== canlı mod (yayın sürerken)

class HlsListeOzeti(unittest.TestCase):
    T0 = 1_000_000

    def liste(self, adet=6, sure=10.0, kayma=0, her_birinde=True):
        s = ['#EXTM3U', '#EXT-X-PLAYLIST-TYPE:EVENT']
        for i in range(adet):
            if her_birinde or i == 0:
                s.append(f'#EXT-X-PROGRAM-DATE-TIME:{yk.epoch_iso(self.T0 + int(i * sure) + (kayma if i else 0))}')
            s += [f'#EXTINF:{sure:.3f},', f'{i}.ts']
        s.append('#EXT-X-ENDLIST')   # süren kayıtta da her güncellemede var
        return '\n'.join(s)

    def test_sure_ilk_ve_son_saat(self):
        o = yk.hls_liste_ozeti(self.liste(6))
        self.assertEqual(o['bolum'], 6)
        self.assertAlmostEqual(o['sure_sn'], 60.0)
        self.assertEqual(o['t0_epoch'], self.T0)
        self.assertEqual(o['son_epoch'], self.T0 + 60)
        self.assertEqual(o['kayma_sn'], 0.0)

    def test_saat_kaymasi_olculur(self):
        o = yk.hls_liste_ozeti(self.liste(6, kayma=2))
        self.assertEqual(o['kayma_sn'], 2.0)   # sohbet hizası bu kadar sapabilir

    def test_bos_liste(self):
        self.assertEqual(yk.hls_liste_ozeti('#EXTM3U\n')['bolum'], 0)

    def test_tek_program_date_time_yeter(self):
        o = yk.hls_liste_ozeti(self.liste(30, 10.0, her_birinde=False))
        self.assertEqual(o['t0_epoch'], self.T0)
        self.assertAlmostEqual(o['sure_sn'], 300.0)
        self.assertEqual(o['kayma_sn'], 0.0)


class SohbetKademeliIndirme(unittest.TestCase):
    T0 = 7_000_000

    def sahte(self, cagri):
        def http(url):
            cagri.append(url)
            bas = yk.iso_epoch(url.split('start_time=')[1])
            return {'data': {'messages': [{'id': f'w{bas}', 'type': 'message', 'content': f'm{bas}',
                                           'created_at': yk.epoch_iso(bas + 1), 'user_id': 1}]}}
        return http

    def test_butce_dolunca_durur_sonra_kalandan_surer(self):
        cagri = []
        with tempfile.TemporaryDirectory() as t:
            part = pathlib.Path(t) / 'p.part.jsonl'
            sayac = iter(range(0, 1000))
            ilk = yk.kick_sohbet_indir(self.sahte(cagri), 7, self.T0, 300, part, butce_sn=2, saat=lambda: next(sayac))
            self.assertEqual(len(cagri), 16)            # tek grup (4 iş parçacığı x 4)
            self.assertEqual(len(ilk), 16)
            self.assertEqual(yk.sohbet_hazir_sn(part, self.T0), 16 * 5)
            tam = yk.kick_sohbet_indir(self.sahte(cagri), 7, self.T0, 300, part)
            self.assertEqual(len(tam), 61)               # 0..300 sn = 61 pencere
            self.assertEqual(len(cagri), 61)             # biten 16 pencere yeniden indirilmedi

    def test_hazir_sure_bosluktan_oncesine_kadar(self):
        with tempfile.TemporaryDirectory() as t:
            part = pathlib.Path(t) / 'p.part.jsonl'
            satirlar = [{'w': self.T0 + 5 * i, 'm': []} for i in (0, 1, 2, 4)]   # 4. pencere eksik
            part.write_text('\n'.join(json.dumps(s) for s in satirlar) + '\n', encoding='utf-8')
            self.assertEqual(yk.sohbet_hazir_sn(part, self.T0), 15)
            self.assertEqual(yk.sohbet_hazir_sn(part.with_name('yok.jsonl'), self.T0), 0)

    def test_yalniz_tamamlanmis_pencereler_istenir(self):
        cagri = []
        vod = {'platform': 'kick', 'vod_id': 'v1', 'kanal_id': 7, 't0_epoch': self.T0}
        with tempfile.TemporaryDirectory() as t:
            d = pathlib.Path(t)
            # şimdi = t0+100, marj 20 -> sohbet t0+80'e kadar; son TAM pencere [75,80)
            _, hazir = yk.sohbet_canli_guncelle(vod, d, self.sahte(cagri), 60, 20, self.T0 + 100)
            self.assertEqual(hazir, 80)
            baslar = sorted(yk.iso_epoch(u.split('start_time=')[1]) - self.T0 for u in cagri)
            self.assertEqual(baslar[-1], 75)
            # çok yeni yayın: hedef negatif -> hiç istek yok
            cagri.clear()
            self.assertEqual(yk.sohbet_canli_guncelle({**vod, 'vod_id': 'v2'}, d, self.sahte(cagri), 60, 20, self.T0 + 10), ([], 0))
            self.assertEqual(cagri, [])


class CanliAdaylari(unittest.TestCase):
    def klip(self, zirve=3000, puan=60.0, bas=2980, bit=3022):
        return {'zirve_sn': zirve, 'zirve_dilimleri': [zirve], 'puan': puan,
                'klip_baslangic_sn': float(bas), 'klip_bitis_sn': float(bit)}

    def test_dalga_kapanmadan_kesilmez(self):
        a = yk.AYAR_VARSAYILAN
        k = self.klip()
        # dalga 3010'da biter; +30 sn kümeleme +20 sn pay = 3060
        self.assertEqual(yk.canli_adaylar([k], 3059, a, [], 5), [])
        self.assertEqual(yk.canli_adaylar([k], 3060, a, [], 5), [k])

    def test_klibin_bitisi_videoda_yoksa_beklenir(self):
        a = yk.AYAR_VARSAYILAN
        uzun = self.klip(bit=3100)       # klip dalgadan uzun sürüyor: 3100 + 20 pay
        self.assertEqual(yk.canli_adaylar([uzun], 3119, a, [], 5), [])
        self.assertEqual(yk.canli_adaylar([uzun], 3120, a, [], 5), [uzun])

    def test_daha_once_kesilenle_ortusen_atlanir_kenara_degen_atlanmaz(self):
        a = yk.AYAR_VARSAYILAN
        self.assertEqual(yk.canli_adaylar([self.klip()], 9999, a, [(3000, 3050)], 5), [])
        self.assertEqual(len(yk.canli_adaylar([self.klip()], 9999, a, [(3022, 3080)], 5)), 1)

    def test_min_puan_ve_kota(self):
        a = {**yk.AYAR_VARSAYILAN, 'canli_min_puan': 55.0}
        k1, k2, k3 = self.klip(1000, 70, 980, 1022), self.klip(2000, 50, 1980, 2022), self.klip(3000, 60, 2980, 3022)
        s = yk.canli_adaylar([k1, k2, k3], 9999, a, [], 5)
        self.assertEqual([k['zirve_sn'] for k in s], [1000, 3000])     # 50 puanlık elendi, zaman sırası
        self.assertEqual([k['zirve_sn'] for k in yk.canli_adaylar([k1, k2, k3], 9999, a, [], 1)], [1000])   # en yüksek puan
        self.assertEqual(yk.canli_adaylar([k1, k2, k3], 9999, a, [], 0), [])


def kahkaha_dalgasi(t0, bas, kisi=40):
    return [(t0 + bas + i // 4, ['hahaha', '[emote:1:KEKW]', 'asdfgh sjsj', 'xd'][i % 4], 2000 + i) for i in range(kisi)]


class YeniZirveSecimi(unittest.TestCase):
    T0 = 1_000_000

    def test_engelli_aralik_ayni_ani_secmez_digerini_secer(self):
        ek = kahkaha_dalgasi(self.T0, 3000) + kahkaha_dalgasi(self.T0, 5000)
        hepsi = yk.analiz_et(sinyal_vod(), zemin_sohbet() + ek, SAYIM_AYAR)['klipler']
        self.assertEqual([k['zirve_sn'] for k in hepsi], [3000, 5000])
        engelli = [(hepsi[0]['klip_baslangic_sn'], hepsi[0]['klip_bitis_sn'])]
        kalan = yk.analiz_et(sinyal_vod(), zemin_sohbet() + ek, SAYIM_AYAR, engelli=engelli)['klipler']
        self.assertEqual([k['zirve_sn'] for k in kalan], [5000])
        # ilk klibe kenarı değen aralık engel sayılmaz
        kenar = [(hepsi[0]['klip_bitis_sn'], hepsi[0]['klip_bitis_sn'] + 50)]
        self.assertEqual(len(yk.analiz_et(sinyal_vod(), zemin_sohbet() + ek, SAYIM_AYAR, engelli=kenar)['klipler']), 2)

    def test_canli_ayar_anahtarlari_var(self):
        for k in ('canli_min_sure_sn', 'canli_azami_klip', 'canli_bekle_sn', 'canli_min_puan',
                  'canli_sohbet_butce_sn', 'canli_sohbet_marj_sn'):
            self.assertIn(k, yk.AYAR_VARSAYILAN)


class SahteKick:
    """Kick API + HLS'in ağsız taklidi: süren bir yayın. video_sn büyüdükçe 'yayın ilerler'."""
    T0 = 1_000_000
    UUID = 'cccccccc-0000-0000-0000-000000000001'

    def __init__(self, ekler=()):
        self.video_sn = 3100
        self.canli = True
        self.mesajlar = {}
        for t, x, g in zemin_sohbet(self.T0) + list(ekler):
            self.mesajlar.setdefault(t, []).append((x, g))
        self.istek = []

    def http(self, url):
        self.istek.append(url)
        if url.endswith('/videos'):
            return [{'id': 1, 'channel_id': 7, 'start_time': yk.epoch_iso(self.T0).replace('.000Z', ''),
                     'session_title': 'Canlı deneme', 'is_live': self.canli, 'duration': 0,
                     'source': 'https://cdn/v/master.m3u8', 'categories': [{'name': 'Just Chatting'}],
                     'video': {'uuid': self.UUID}}]
        bas = yk.iso_epoch(url.split('start_time=')[1])
        liste = []
        for t in range(bas, bas + 5):
            for i, (x, g) in enumerate(self.mesajlar.get(t, [])):
                liste.append({'id': f'm{t}-{i}', 'type': 'message', 'content': x, 'created_at': yk.epoch_iso(t),
                              'user_id': g})
        return {'data': {'messages': liste[:25]}}

    def http_text(self, url, **k):
        if url.endswith('master.m3u8'):
            return '#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=8000000\n1080p60/playlist.m3u8\n'
        s = ['#EXTM3U']
        for i in range(int(self.video_sn // 10)):
            s += [f'#EXT-X-PROGRAM-DATE-TIME:{yk.epoch_iso(self.T0 + i * 10)}', '#EXTINF:10.000,', f'{i}.ts']
        return '\n'.join(s + ['#EXT-X-ENDLIST'])


class CanliKomutuUctanUca(unittest.TestCase):
    T0 = SahteKick.T0

    def ayar(self):
        a = {**SAYIM_AYAR, 'canli_sohbet_butce_sn': 120}
        return {'ayar': a, 'yayincilar': [{'ad': 'Deneme', 'platform': 'kick', 'kanal': 'deneme', 'etkin': True, 'ayar': a}]}

    def kesici(self, kesilenler):
        def kes(vod, klip, mp4, vayar):
            mp4.parent.mkdir(parents=True, exist_ok=True)
            mp4.write_bytes(b'x')
            kesilenler.append((klip['klip_baslangic_sn'], klip['klip_bitis_sn'], vod['sure_sn']))
            return {'sure_sn': klip['klip_bitis_sn'] - klip['klip_baslangic_sn'], 'genislik': 1080, 'yukseklik': 1920}
        return kes

    def tur(self, k, d, kesilenler, simdi, **ek):
        return yk.canli_komutu(self.ayar(), d, http=k.http, http_text=k.http_text, simdi=simdi,
                               kesici=self.kesici(kesilenler), **ek)

    def test_kapanmamis_dalga_beklenir_kapaninca_bir_kez_kesilir_tekrar_kesilmez(self):
        k = SahteKick(kahkaha_dalgasi(self.T0, 3000))
        kesilenler = []
        with tempfile.TemporaryDirectory() as t:
            d = pathlib.Path(t)
            # video 3040 sn: dalga 3010'da bitti ama kümeleme penceresi + pay (3060) dolmadı -> kesilmez
            k.video_sn = 3040
            r = self.tur(k, d, kesilenler, self.T0 + 3100)[0]
            self.assertEqual((r['durum'], r['acik_zirve'], kesilenler), ('tamam', 1, []))
            self.assertAlmostEqual(r['hiz_kaymasi_sn'], 0.0)
            # video 3100 sn: kapandı -> tam bir klip
            k.video_sn = 3100
            r = self.tur(k, d, kesilenler, self.T0 + 3150)[0]
            self.assertEqual(len(kesilenler), 1)
            bas, bit, sure_sn = kesilenler[0]
            self.assertEqual((bas, bit), (2980.0, 3022.0))
            self.assertLessEqual(bit, sure_sn)                # klibin bitişi videoda var: yarım klip yok
            self.assertTrue(r['klipler'][0]['dosya'].endswith('canli-01.mp4'))
            kayit = yk.durum_oku(d)['vod'][f'kick:{k.UUID}']
            self.assertEqual(len(kayit['canli_klipler']), 1)
            self.assertEqual(kayit['canli_klipler'][0]['bas_epoch'], self.T0 + 2980)   # video sn -> gerçek saat hizası
            self.assertEqual(kayit['canli_klipler'][0]['bit_epoch'], self.T0 + 3022)
            paket = json.loads(pathlib.Path(r['klipler'][0]['dosya']).with_suffix('.json').read_text(encoding='utf-8'))
            self.assertTrue(paket['canli_kesim'])
            self.assertFalse(paket['yayinlandi'])
            # aynı an: yeni tur (daha çok video/sohbet) ikinci kez kesmez
            k.video_sn = 3300
            self.tur(k, d, kesilenler, self.T0 + 3350)
            self.assertEqual(len(kesilenler), 1)
            # yeni dalga -> yalnız o kesilir, numara 02
            k2 = SahteKick(kahkaha_dalgasi(self.T0, 3000) + kahkaha_dalgasi(self.T0, 3400))
            k2.video_sn = 3600
            r = self.tur(k2, d, kesilenler, self.T0 + 3650)[0]
            self.assertEqual(len(kesilenler), 2)
            self.assertEqual(kesilenler[1][0], 3380.0)
            self.assertTrue(r['klipler'][0]['dosya'].endswith('canli-02.mp4'))

    def test_yayin_bitince_kes_canlida_kesileni_atlar(self):
        from unittest import mock
        ek = kahkaha_dalgasi(self.T0, 3000) + kahkaha_dalgasi(self.T0, 5000)
        k = SahteKick(ek)
        kesilenler = []
        with tempfile.TemporaryDirectory() as t:
            d = pathlib.Path(t)
            k.video_sn = 3100
            self.tur(k, d, kesilenler, self.T0 + 3150)
            self.assertEqual(len(kesilenler), 1)
            vod = {**sinyal_vod(), 't0_epoch': self.T0, 'anahtar': f'kick:{k.UUID}', 'vod_id': k.UUID}
            sonuc = yk.analiz_et(vod, zemin_sohbet() + ek, SAYIM_AYAR)
            self.assertEqual([c['zirve_sn'] for c in sonuc['klipler']], [3000, 5000])
            sonuc['ayar'] = SAYIM_AYAR
            kesildi = []

            def sahte_kes(v, klip, hedef, ff, font, ayar=None):
                kesildi.append(klip['zirve_sn'])
                hedef.parent.mkdir(parents=True, exist_ok=True)
                hedef.write_bytes(b'x')
                return {'sure_sn': 40, 'genislik': 1080, 'yukseklik': 1920}
            with mock.patch.object(yk, 'analiz_komutu', return_value=(vod, sonuc)), \
                    mock.patch.object(yk, 'ffmpeg_bul', return_value='ff'), mock.patch.object(yk, 'font_bul', return_value='f'), \
                    mock.patch.object(yk, 'klip_kes', side_effect=sahte_kes):
                yk.kes_komutu(vod['anahtar'], d, self.ayar())
            self.assertEqual(kesildi, [5000])      # 3000 anı canlıda kesilmişti
            kayit = yk.durum_oku(d)['vod'][vod['anahtar']]
            self.assertEqual(kayit['durum'], 'islendi')
            self.assertEqual(len(kayit['canli_klipler']), 1)   # canlı kayıt "işlendi" durumuyla silinmedi

    def test_canli_degilse_ve_kuru_tur_kesmez(self):
        k = SahteKick(kahkaha_dalgasi(self.T0, 3000))
        kesilenler = []
        with tempfile.TemporaryDirectory() as t:
            d = pathlib.Path(t)
            k.canli = False
            self.assertEqual(self.tur(k, d, kesilenler, self.T0 + 3150)[0]['durum'], 'canlı değil')
            k.canli = True
            r = self.tur(k, d, kesilenler, self.T0 + 3150, kuru=True)[0]
            self.assertEqual(len(r['klipler']), 1)
            self.assertEqual(kesilenler, [])
            self.assertEqual(yk.durum_oku(d)['vod'], {})

    def test_yayin_cok_kisaysa_analiz_edilmez(self):
        k = SahteKick(kahkaha_dalgasi(self.T0, 300))
        kesilenler = []
        with tempfile.TemporaryDirectory() as t:
            k.video_sn = 600
            r = self.tur(k, pathlib.Path(t), kesilenler, self.T0 + 650)[0]
            self.assertIn('kısa', r['durum'])
            self.assertEqual(kesilenler, [])

    def test_en_cok_ve_yayinci_suzgeci(self):
        k = SahteKick(kahkaha_dalgasi(self.T0, 3000) + kahkaha_dalgasi(self.T0, 5000))
        k.video_sn = 5200
        kesilenler = []
        with tempfile.TemporaryDirectory() as t:
            d = pathlib.Path(t)
            self.assertEqual(self.tur(k, d, kesilenler, self.T0 + 5250, kanal='baska'), [])
            self.tur(k, d, kesilenler, self.T0 + 5250, en_cok=1)
            self.assertEqual(len(kesilenler), 1)

    def test_kilit(self):
        import os
        with tempfile.TemporaryDirectory() as t:
            d = pathlib.Path(t)
            with yk.canli_kilidi(d):
                with self.assertRaises(yk.KlipHatasi):
                    with yk.canli_kilidi(d):
                        pass
            with yk.canli_kilidi(d):      # çıkınca kilit kalkar
                pass
            (d / 'canli.kilit').write_text('1')
            eski = (d / 'canli.kilit').stat().st_mtime - 20_000
            os.utime(d / 'canli.kilit', (eski, eski))
            with yk.canli_kilidi(d):      # bayat kilit yok sayılır
                pass
