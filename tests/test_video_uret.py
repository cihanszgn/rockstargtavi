import copy
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import haber_oto  # noqa: E402
import video_ses_yardimci as yardimci  # noqa: E402
import video_uret as v  # noqa: E402

KIMLIK = 'ornek-oyun-yama-2026-11-15'
METIN = ("Ornek Oyun'un 2. sezon yaması 1 Aralık'ta PC ve PlayStation için çıkıyor. "
         "Tüfeğin hasarı 40'tan 32'ye iniyor, maçlarda oyuncu sınırı 64 oluyor.")


def haber():
    return {'id': KIMLIK, 'tarih': '2026-11-15', 'oyun': 'Ornek Oyun', 'tur': 'guncelleme',
            'platform': ['PC', 'PlayStation'],
            'kaynaklar': [{'ad': 'Ornek geliştirici blogu', 'url': 'https://example.com/blog/yama-notlari',
                           'tarih': '2026-11-15'}],
            'diller': {'tr': {'baslik': "Ornek Oyun yaması 1 Aralık'ta geliyor", 'ozet': 'Yeni sezon yaması duyuruldu.',
                              'metin': METIN}}}


def senaryo():
    return {
        'id': KIMLIK, 'dil': 'tr', 'fps': 30, 'boyut': [1080, 1920], 'sablon_surumu': 1,
        'okunus': {},
        'sahneler': [
            {'sablon': 'baslik',
             'anlatim': "Ornek Oyun'un ikinci sezon yaması 1 Aralık'ta PC ve PlayStation için geliyor.",
             'veri': {'ust_etiket': '2. sezon', 'baslik': "Ornek Oyun yaması 1 Aralık'ta", 'vurgu': ["1 Aralık'ta"]},
             'alt_kart': {'simge': 'guncelleme', 'baslik': 'ORNEK OYUN', 'alt': '2. SEZON YAMASI'},
             'maskot': {'hareket': 'bas'}},
            {'sablon': 'kaynak',
             'anlatim': 'Geliştiricinin blog yazısına göre yama notları yayımlandı ve değişiklikler oldukça büyük.',
             'veri': {'kaynak': 0, 'alinti': "Yama 1 Aralık'ta PC ve PlayStation için çıkıyor."},
             'alt_kart': {'simge': 'kaynak', 'baslik': 'RESMÎ KAYNAK', 'alt': 'GELİŞTİRİCİ BLOGU'},
             'maskot': {'hareket': 'tara'}},
            {'sablon': 'yama_fark',
             'anlatim': "Tüfeğin hasarı 40'tan 32'ye iniyor, bu yüzden yakın mesafede daha dikkatli oynamak gerekecek.",
             'veri': {'baslik': 'Silah dengesi',
                      'satirlar': [{'ad': 'Tüfek hasarı', 'eski': '40', 'yeni': '32', 'tetik': 'hasarı'}]},
             'alt_kart': {'simge': 'yama', 'baslik': 'TÜFEĞE DÜŞÜŞ', 'alt': "HASAR 40'TAN 32'YE"},
             'maskot': {'hareket': 'bas'}},
            {'sablon': 'platform',
             'anlatim': 'Yama PC ve PlayStation için geliyor, maçlarda oyuncu sınırı da 64 kişiye çıkıyor.',
             'veri': {'baslik': 'Platformlar', 'sayilar': [{'deger': '64', 'etiket': 'OYUNCU', 'tetik': '64'}]},
             'alt_kart': {'simge': 'platform', 'baslik': 'PC VE PLAYSTATION', 'alt': '64 OYUNCU'},
             'maskot': {'hareket': 'zipla'}},
            {'sablon': 'tarih',
             'anlatim': "Takviminize not edin: yama 1 Aralık'ta yükleniyor ve sunucular kısa süre kapalı kalacak.",
             'veri': {'etiket': 'Yama günü', 'tarih': '1 Aralık', 'not': 'Sunucular kısa süre kapalı kalacak.'},
             'alt_kart': {'simge': 'takvim', 'baslik': 'YAMA GÜNÜ', 'alt': '1 ARALIK'},
             'maskot': {'hareket': 'zipla'}},
            {'sablon': 'kapanis',
             'anlatim': "Bütün yama notları ve ayrıntılar sitemizde, Control A Game'de.",
             'veri': {'cagri': 'Bütün ayrıntılar sitede'},
             'alt_kart': {'simge': 'site', 'baslik': 'CTRL+A GAME', 'alt': 'CTRL-AGAME.COM'},
             'maskot': {'hareket': 'bas'}},
        ]}


def hatalar(sen, h=None):
    """Senaryonun hata listesi; senaryo geçerliyse test başarısız olur."""
    try:
        v.senaryo_hazirla(sen, h or haber(), 'tr')
    except v.SenaryoHatasi as e:
        return e.hatalar
    raise AssertionError('SenaryoHatasi bekleniyordu')


def sahte_sinirlar(tts, bas=0.3, kelime=0.4, ara=1.0):
    """Seslendiricinin vereceği gibi noktalamasız kelime sınırları; sahneler arasında durak."""
    sinirlar, t = [], bas
    for satir in tts.split('\n'):
        for k in satir.split():
            k = k.strip(v.NOKTALAMA)
            if k:
                sinirlar.append({'k': k, 'b': round(t, 3), 's': round(t + kelime, 3)})
                t += kelime
        t += ara
    return sinirlar


class Kosucu:
    """subprocess.run yerine: komutu kaydeder, isteğe göre dosya yazar; kabuk hiç kullanılmaz."""

    def __init__(self, yap=None, kod=0):
        self.cagrilar, self.yap, self.kod = [], yap, kod

    def __call__(self, komut, **kw):
        self.cagrilar.append((komut, kw))
        if self.yap:
            self.yap(komut)
        return subprocess.CompletedProcess(komut, self.kod, stdout='', stderr='hata ayrıntısı')


def ses_yaz(komut):
    pathlib.Path(komut[-2]).write_bytes(b'ID3')
    pathlib.Path(komut[-1]).write_text(json.dumps({'olaylar': [
        {'metin': 'dünya', 'bas': 5_000_000, 'sure': 3_000_000},
        {'metin': 'Merhaba', 'bas': 1_000_000, 'sure': 4_000_000},
        {'metin': ' ', 'bas': 0, 'sure': 1}]}), encoding='utf-8')


class GecerlilikTests(unittest.TestCase):
    def test_ornek_senaryo_gecer_ve_duz_yazimla_seslendirilir(self):
        hazir = v.senaryo_hazirla(senaryo(), haber(), 'tr')
        self.assertEqual([s['sablon'] for s in hazir['sahneler']],
                         ['baslik', 'kaynak', 'yama_fark', 'platform', 'tarih', 'kapanis'])
        # Ses adları kendi yazımıyla okur; site adı söylenir, adres okunmaz.
        self.assertIn('PlayStation', hazir['tts'])
        self.assertIn("sitemizde, Control A Game'de.", hazir['tts'])
        self.assertNotIn('nokta', hazir['tts'])
        self.assertNotIn('ctrl-agame', hazir['tts'].lower())
        self.assertTrue(v.EN_KISA <= hazir['tahmini_sure'] <= v.EN_UZUN)
        # okunus gerekirse yine çalışır: yalnız seslendirmeye gider, altyazı yazılan kelimeyi gösterir.
        s = senaryo()
        s['okunus'] = {'PlayStation': 'Pleysteyşın'}
        okunuslu = v.senaryo_hazirla(s, haber(), 'tr')
        self.assertIn('Pleysteyşın', okunuslu['tts'])
        self.assertNotIn('PlayStation', okunuslu['tts'])
        self.assertIn('PlayStation', okunuslu['sahneler'][0]['kelimeler'])
        platform = hazir['sahneler'][3]['veri']
        self.assertEqual([p['ad'] for p in platform['platformlar']], ['PC', 'PLAYSTATION'])
        self.assertEqual(platform['pencere'], 'ORNEK OYUN')
        tarih = hazir['sahneler'][4]['veri']
        self.assertEqual((tarih['gun_bas'], tarih['ay'], tarih['yil']), (1, 12, 2026))
        self.assertEqual(tarih['yil_metin'], '2026', 'yıl haberin kendi tarihinden gelir')
        h = haber()
        h['tarih'] = '2026-12-20'
        h['diller']['tr']['metin'] = METIN.replace("1 Aralık'ta", "1 Ocak'ta")
        s = senaryo()
        for sahne in s['sahneler']:
            sahne['anlatim'] = sahne['anlatim'].replace("1 Aralık'ta", "1 Ocak'ta")
        s['sahneler'][0]['veri']['baslik'] = "Ornek Oyun yaması 1 Ocak'ta"
        s['sahneler'][0]['veri']['vurgu'] = ["1 Ocak'ta"]
        s['sahneler'][1]['veri']['alinti'] = "Yama 1 Ocak'ta PC ve PlayStation için çıkıyor."
        s['sahneler'][4]['veri']['tarih'] = '1 Ocak'
        s['sahneler'][4]['alt_kart']['alt'] = '1 OCAK'
        s['id'] = h['id']
        tarih = v.senaryo_hazirla(s, h, 'tr')['sahneler'][4]['veri']
        self.assertEqual((tarih['yil'], tarih['yil_metin']), (2027, ''), 'haberde geçmeyen yıl ekrana yazılmaz')
        self.assertEqual(hazir['sahneler'][0]['veri']['ust_etiket'], '2. SEZON')

    def test_gercek_senaryolar_haber_metniyle_tutarli(self):
        if not v.ICERIK.exists():
            self.skipTest('data/icerik.json yok')
        icerik = {x['id']: x for x in v.haberler()}
        dosyalar = sorted(v.SENARYO.glob('*.json'))
        self.assertGreaterEqual(len(dosyalar), 2)
        for yol in dosyalar:
            kimlik, dil = yol.stem.rsplit('-', 1)
            with self.subTest(yol.name):
                if kimlik not in icerik:
                    self.skipTest(f'{kimlik} haberi yok')
                self.assertEqual(v.senaryo_dosyasi_denetle(yol, icerik[kimlik], dil), [])

    def test_haberde_olmayan_sayi_reddedilir(self):
        s = senaryo()
        s['sahneler'][2]['veri']['satirlar'][0]['yeni'] = '99'
        self.assertIn('sahneler[2].veri.satirlar[0].yeni: "99" sayısı haber metninde yok', hatalar(s))
        s = senaryo()
        s['sahneler'][1]['anlatim'] += ' Oyuncu sayısı 120 bine çıktı.'
        self.assertTrue(any('"120" sayısı haber metninde yok' in e for e in hatalar(s)))
        s = senaryo()
        s['okunus']['PlayStation'] = 'Pleysteyşın 5'
        self.assertTrue(any(e.startswith('okunus.PlayStation') and '"5"' in e for e in hatalar(s)))

    def test_web_adresi_seslendirilmez(self):
        for anlatim in ("Bütün ayrıntılar ctrl-agame.com'da.", 'Ayrıntılar www.ornek.net adresinde.',
                        'Notlar https://example.com/blog sayfasında.', "Ayrıntılar kontrol ey geym nokta kom'da."):
            s = senaryo()
            s['sahneler'][5]['anlatim'] = anlatim
            with self.subTest(anlatim):
                self.assertTrue(any(e.startswith('sahneler[5].anlatim: web adresi') for e in hatalar(s)))
        # okunusla sokulan adres de yakalanır: seslendirmeye giden metin denetlenir.
        s = senaryo()
        s['okunus'] = {'Control A Game': 'kontrol ey geym nokta kom'}
        self.assertTrue(any(e.startswith('sahneler[5].anlatim: web adresi') for e in hatalar(s)))
        for temiz in ('Sürüm 1.5 bugün EA app üzerinden geliyor.', "MBZ-19 ve ACS12 Siege'in yeni silahları."):
            self.assertIsNone(v.WEB_ADRESI.search(temiz), temiz)

    def test_tarih_haberde_aynen_gecmeli(self):
        s = senaryo()
        s['sahneler'][4]['veri']['tarih'] = '2 Aralık'
        self.assertIn('sahneler[4].veri.tarih: "2 Aralık" haber metninde aynen geçmiyor', hatalar(s))
        s['sahneler'][4]['veri']['tarih'] = 'yakında'
        self.assertTrue(any('gün ve ay adı olmalı' in e for e in hatalar(s)))

    def test_yapi_hatalari(self):
        s = senaryo()
        s['calistir'] = 'rm -rf /'
        self.assertIn('senaryo.calistir: bilinmeyen alan', hatalar(s))
        s = senaryo()
        s['sahneler'] = s['sahneler'][1:]
        self.assertIn('sahneler: ilk sahne baslik, son sahne kapanis olmalı', hatalar(s))
        s = senaryo()
        s['sahneler'] = s['sahneler'][:2]
        self.assertEqual(hatalar(s), ['sahneler: 3–9 sahnelik liste olmalı'])
        s = senaryo()
        s['id'] = 'baska-haber'
        self.assertTrue(any(e.startswith('id: haber kimliğiyle aynı olmalı') for e in hatalar(s)))
        s = senaryo()
        s['sahneler'][2]['sablon'] = 'video_oynat'
        self.assertTrue(any(e.startswith('sahneler[2].sablon: şunlardan biri olmalı') for e in hatalar(s)))
        s = senaryo()
        s['sahneler'][2]['veri']['satirlar'][0]['tetik'] = 'zırh'
        self.assertTrue(any('"zırh" bu sahnenin anlatımında geçmiyor' in e for e in hatalar(s)))
        s = senaryo()
        s['sahneler'][0]['maskot']['hareket'] = 'uc'
        self.assertTrue(any(e.startswith('sahneler[0].maskot.hareket') for e in hatalar(s)))
        s = senaryo()
        s['sablon_surumu'] = v.SABLON_SURUMU + 1
        self.assertTrue(any(e.startswith('sablon_surumu: şunlardan biri olmalı') for e in hatalar(s)))
        for surum in v.OKUNAN_SURUMLER:
            s['sablon_surumu'] = surum
            v.senaryo_hazirla(s, haber(), 'tr')

    def test_tasma_ve_uzunluk_sinirlari(self):
        s = senaryo()
        s['sahneler'][0]['alt_kart']['baslik'] = 'ORNEK OYUN İKİNCİ SEZON YAMASI GELİYOR'
        self.assertTrue(any(e.startswith('sahneler[0].alt_kart.baslik: en çok 26 karakter') for e in hatalar(s)))
        s = senaryo()
        s['sahneler'][3]['veri']['sayilar'][0]['etiket'] = 'AZAMİOYUNCUKAPASİTESİ'
        self.assertIn('sahneler[3].veri.sayilar[0].etiket: "AZAMİOYUNCUKAPASİTESİ" kelimesi alana sığmıyor', hatalar(s))
        s = senaryo()
        s['sahneler'][1]['veri']['alinti'] = ' '.join(['Yama notları uzun bir açıklama içeriyor.'] * 4)
        self.assertTrue(any(e.startswith('sahneler[1].veri.alinti: en çok 150 karakter') for e in hatalar(s)))
        s = senaryo()
        for sahne in s['sahneler']:
            sahne['anlatim'] = sahne['anlatim'].split()[0] + ' ' + sahne['anlatim'].split()[-1]
        for sahne in s['sahneler']:
            for oge in sahne['veri'].get('satirlar', []) + sahne['veri'].get('sayilar', []):
                oge.pop('tetik', None)
        self.assertTrue(any(e.startswith('sahneler: tahmini süre') for e in hatalar(s)))

    def test_zamanlama_alanlari_yok_sayilir_uyari_verir(self):
        s = senaryo()
        s['sahneler'][1]['bas'] = 3.0
        s['sahneler'][1]['maskot']['konum'] = [10, 10]
        uyarilar = v.senaryo_hazirla(s, haber(), 'tr')['uyarilar']
        self.assertIn('sahneler[1].bas: zamanlamadan hesaplanır, yazılan değer yok sayıldı', uyarilar)
        self.assertTrue(any('maskot.konum' in u for u in uyarilar))

    def test_senaryo_oku_kimligi_yol_olarak_kullanmaz(self):
        for kimlik, dil in (('../../etc/passwd', 'tr'), ('ornek-oyun', 'tr/../x'), ('A b', 'tr')):
            with self.assertRaises(v.SenaryoHatasi):
                v.senaryo_oku(kimlik, dil, pathlib.Path(tempfile.gettempdir()))

    def test_bozuk_json_hata_listesi_verir(self):
        with tempfile.TemporaryDirectory() as t:
            yol = pathlib.Path(t) / f'{KIMLIK}-tr.json'
            yol.write_text('{bozuk', encoding='utf-8')
            sonuc = v.senaryo_dosyasi_denetle(yol, haber(), 'tr')
            self.assertEqual(len(sonuc), 1)
            self.assertIn('JSON okunamadı', sonuc[0])


class MetinTests(unittest.TestCase):
    def test_turkce_buyuk_harf(self):
        self.assertEqual(v.tr_upper('dereceli ikiye ayrılıyor'), 'DERECELİ İKİYE AYRILIYOR')
        self.assertEqual(v.tr_upper('battle pass', 'en'), 'BATTLE PASS')

    def test_okunus_eki_ve_noktalamayi_korur(self):
        self.assertEqual(v.okunus_uygula(['Rainbow', 'Six', "Siege'in", 'yeni'], {'Rainbow Six Siege': 'Reynbou Siks Siyc'}),
                         [([0, 1, 2], "Reynbou Siks Siyc'in"), ([3], 'yeni')])
        self.assertEqual(v.okunus_uygula(['Steam,'], {'Steam': 'Stiim'}), [([0], 'Stiim,')])
        self.assertEqual(v.okunus_uygula(['steam', 'Steamy'], {'Steam': 'Stiim'}), [([0], 'steam'), ([1], 'Steamy')])

    def test_kapanis_site_adini_soylemeli(self):
        s = senaryo()
        s['sahneler'][-1]['anlatim'] = 'Bütün yama notları ve ayrıntılar sitemizde yayında.'
        self.assertTrue(any('sitenin adını' in str(h) for h in hatalar(s)))

    def test_pencere_basligi(self):
        D = v.Denetci(haber(), 'tr')
        self.assertEqual(v._pencere(D, 'platform', {'baslik': 'PLATFORMLAR'}), 'ORNEK OYUN')
        self.assertEqual(v._pencere(D, 'kaynak', {'alan': 'example.com'}), 'example.com')
        self.assertEqual(v._pencere(D, 'maddeler', {'baslik': 'DOC YENİLENİYOR'}), 'DOC YENİLENİYOR')
        self.assertTrue(v._pencere(D, 'maddeler', {'baslik': 'Ç' * 80}).endswith('…'))


class ZamanlamaTests(unittest.TestCase):
    def test_kelime_sahne_ve_altyazi_zamanlari(self):
        hazir = v.senaryo_hazirla(senaryo(), haber(), 'tr')
        sinirlar = sahte_sinirlar(hazir['tts'])
        z = v.zamanla(hazir, sinirlar, sinirlar[-1]['s'] + 0.5)
        kel = z['kelimeler']
        self.assertEqual(len(kel), hazir['kelime_sayisi'])
        for a, b in zip(kel, kel[1:]):
            self.assertLessEqual(a['b'], b['b'])
            self.assertLess(a['b'], a['s'])
        sahneler = z['sahneler']
        self.assertEqual(sahneler[0]['bas'], 0.0)
        for a, b in zip(sahneler, sahneler[1:]):
            self.assertEqual(a['bit'], b['bas'])
            self.assertLess(a['bas'], a['bit'])
        self.assertEqual(sahneler[-1]['bit'], z['sure'])
        self.assertGreaterEqual(z['sure'], kel[-1]['s'] + v.KUYRUK)
        # sahne, ilk sözünden ONDEN kadar önce açılır
        ilk_soz = sahneler[2]['altyazi'][0]['b']
        self.assertAlmostEqual(sahneler[2]['bas'], ilk_soz - v.ONDEN, places=3)
        satir = sahneler[2]['veri']['satirlar'][0]
        self.assertTrue(sahneler[2]['bas'] <= satir['goster'] <= sahneler[2]['bit'])
        self.assertNotIn('tetik', satir)
        A = v.duzen()['altyazi']
        self.assertLessEqual(A['en_cok_kelime'], 6)
        sira = []
        for p in z['parcalar']:
            idx = [i for s in p['satirlar'] for i in s]
            self.assertLessEqual(len(p['satirlar']), 2)
            self.assertLessEqual(len(idx), A['en_cok_kelime'])
            self.assertLessEqual(p['b'], p['s'])
            self.assertLessEqual(p['s'], p['bitis'] + 1e-9)
            sira += idx
        self.assertEqual(sira, list(range(len(kel))), 'her kelime bir kez ve sırayla altyazıda')
        sahne_no = [si for si, s in enumerate(hazir['sahneler']) for _ in s['kelimeler']]
        for p in z['parcalar']:
            idx = [i for s in p['satirlar'] for i in s]
            self.assertEqual(len({sahne_no[i] for i in idx}), 1, 'altyazı parçası sahne sınırını aşmaz')
        vtt = v.vtt_yaz(kel, z['parcalar'])
        self.assertTrue(vtt.startswith('WEBVTT\n\n'))
        self.assertEqual(vtt.count(' --> '), len(z['parcalar']))

    def test_altyazi_kirma_cezasi(self):
        self.assertEqual(v.kirma_cezasi('750', 'mermi'), v.KIRILMAZ, 'sayı birimden ayrılmaz')
        self.assertEqual(v.kirma_cezasi('11.', 'yılın'), v.KIRILMAZ, 'sıra sayısı kelimesinden ayrılmaz')
        self.assertEqual(v.kirma_cezasi('atıyor,', 'şarjör'), 0.0, 'noktalamada kırmak bedava')
        self.assertEqual(v.kirma_cezasi('yeni', 'silah'), 0.8)
        self.assertGreater(v.kirma_cezasi('ve', 'Jäger'), v.kirma_cezasi('Thunderbird', 've'), 'bağlaçta bitmek pahalı')
        self.assertGreater(v.kirma_cezasi('sunucular', 'de'), v.kirma_cezasi('sunucular', 'kapalı'), 'ekle başlamak pahalı')
        self.assertLess(v.kirma_cezasi('2,', '3'), v.KIRILMAZ, 'sayı dizisi gerekirse kırılabilir')

    def test_altyazi_parcalari_ortalama_ve_sinirlar(self):
        metin = ('Yeni hafif makineli MBZ-19 dakikada 750 mermi atıyor, 64 mermilik şarjör taşıyor ve 33 hasar veriyor. '
                 'Warden, Thunderbird ve Jäger kullanabilecek.')
        kel = [{'k': k, 'b': round(i * 0.35, 3), 's': round(i * 0.35 + 0.3, 3), 'sahne': 0} for i, k in enumerate(metin.split())]
        parcalar = v.parcalara_bol(kel)
        A = v.duzen()['altyazi']
        boylar = []
        for p in parcalar:
            idx = [i for s in p['satirlar'] for i in s]
            self.assertLessEqual(len(p['satirlar']), A['en_cok_satir'])
            self.assertLessEqual(len(idx), A['en_cok_kelime'])
            boylar.append(len(idx))
        self.assertTrue(3 <= sum(boylar) / len(boylar) <= 5, boylar)
        sonlar = [kel[p['satirlar'][-1][-1]]['k'] for p in parcalar]
        self.assertIn('veriyor.', sonlar, 'cümle sonu parçayı bitirir')
        for a, b in zip(parcalar, parcalar[1:]):
            self.assertLess(v.kirma_cezasi(kel[a['satirlar'][-1][-1]]['k'], kel[b['satirlar'][0][0]]['k']), v.KIRILMAZ)

    def test_vtt_html_kacisi(self):
        kel = [{'k': '<b>', 'b': 0.0, 's': 0.5}, {'k': 'A&B', 'b': 0.5, 's': 1.0}]
        vtt = v.vtt_yaz(kel, [{'b': 0.0, 's': 1.0, 'bitis': 1.2, 'satirlar': [[0, 1]]}])
        self.assertIn('00:00:00.000 --> 00:00:01.200', vtt)
        self.assertIn('&lt;b&gt; A&amp;B', vtt)

    def test_sesle_hizala(self):
        kel = [{'k': 'a', 'b': 0.0, 's': 0.5}, {'k': 'b', 'b': 0.5, 's': 1.0}, {'k': 'c', 'b': 1.6, 's': 2.5}]
        yeni = v.sesle_hizala(kel, [(1.1, 2.0)])
        self.assertEqual([(w['b'], w['s']) for w in yeni], [(0.1, 0.6), (0.6, 1.1), (2.0, 2.6)])
        self.assertEqual(kel[0]['b'], 0.0, 'girdi değişmez')
        self.assertEqual(v.sesle_hizala(kel, []), kel)
        # durakla kelime bitişi arasındaki fark mantıksızsa sabit kayma uygulanmaz
        uzak = v.sesle_hizala(kel, [(1.6, 2.0)])
        self.assertEqual((uzak[0]['b'], uzak[0]['s']), (0.0, 0.5))
        # kayma en çok 0.25 sn
        tek = v.sesle_hizala([{'k': 'a', 'b': 0.0, 's': 0.5}], [(0.78, 1.2)])
        self.assertEqual(tek[0]['b'], 0.25)

    def test_olaylar_saniyeye_cevrilir(self):
        ham = {'olaylar': [{'metin': 'b', 'bas': 20_000_000, 'sure': 5_000_000},
                           {'metin': 'a', 'bas': 10_000_000, 'sure': 5_000_000}, {'metin': ' ', 'bas': 0, 'sure': 1}]}
        self.assertEqual(v.olaylari_kelimeye(ham), [{'k': 'a', 'b': 1.0, 's': 1.5}, {'k': 'b', 'b': 2.0, 's': 2.5}])

    def araliklar_esit(self, bulunan, beklenen):
        self.assertEqual(len(bulunan), len(beklenen))
        for x, y in zip(bulunan, beklenen):
            if y is None:
                self.assertIsNone(x)
            else:
                self.assertAlmostEqual(x[0], y[0], places=6)
                self.assertAlmostEqual(x[1], y[1], places=6)

    def test_turkce_sayi_okunusu(self):
        for n, soz in ((0, 'sıfır'), (11, 'on bir'), (100, 'yüz'), (750, 'yedi yüz elli'), (1000, 'bin'),
                       (1500, 'bin beş yüz'), (2026, 'iki bin yirmi altı'), (64000, 'altmış dört bin')):
            self.assertEqual(v.sayi_oku_tr(n), soz)
        self.assertEqual(v._soz_norm('1.500', 'tr'), 'binbeşyüz', 'binlik ayırıcılı sayı tek sayıdır')
        self.assertEqual(v._soz_norm("11.", 'tr'), 'onbir')
        self.assertEqual(v._soz_norm("750'ye", 'tr'), 'yediyüzelliye')
        self.assertEqual(v._soz_norm('750', None), '750', 'dili tanınmayan metne dokunulmaz')

    def test_sayi_okunusu_en_es_fr(self):
        for n, en, es, fr in ((750, 'seven hundred fifty', 'setecientos cincuenta', 'sept cent cinquante'),
                              (2026, 'two thousand twenty-six', 'dos mil veintiséis', 'deux mille vingt-six'),
                              (80, 'eighty', 'ochenta', 'quatre-vingts'),
                              (200, 'two hundred', 'doscientos', 'deux cents'),
                              (64, 'sixty-four', 'sesenta y cuatro', 'soixante-quatre'),
                              (100, 'one hundred', 'cien', 'cent')):
            self.assertEqual(v.sayi_oku_en(n), en)
            self.assertEqual(v.sayi_oku_es(n), es)
            self.assertEqual(v.sayi_oku_fr(n), fr)
        self.assertEqual(v.yil_oku_en(2026), 'twenty twenty-six')
        self.assertEqual(v.sira_oku_en(21), 'twenty-first')
        self.assertEqual(v._soz_norm('750 rounds', 'en'), 'sevenhundredfiftyrounds')
        self.assertEqual(v._soz_norm('1,500', 'en'), 'onethousandfivehundred')
        self.assertEqual(v._soz_norm('1.500', 'es'), 'milquinientos')
        self.assertEqual(v._soz_norm('1.500', 'fr'), 'millecinqcents')
        self.assertEqual(v._soz_norm('3,5', 'fr'), 'troisvirgulecinq')
        self.assertEqual(v._soz_norm('750', 'tr'), 'yediyüzelli', 'Türkçe davranış değişmedi')

    def test_dil_kurali_tablosu_ve_kapanis(self):
        self.assertEqual(v.dil_kurali('tr'), v.dil_kurali(None))
        self.assertEqual(v.dil_kurali('xx'), v.dil_kurali('tr'), 'bilinmeyen dil Türkçe kuralına düşer')
        self.assertEqual(v.BAGLI_SON, v.DIL_KURALI['tr']['bagli_son'])
        for dil in ('tr', 'en', 'es', 'fr'):
            c = v.kapanis_cumlesi(dil)
            self.assertIn(v.SITE_ADI, c, f'{dil}: kapanışta site adı söylenir')
            self.assertNotIn('.com', c)
            self.assertNotIn('ctrl-agame', c.lower(), f'{dil}: web adresi seslendirilmez')
            self.assertTrue(v.site_adi_var(c))
        self.assertFalse(v.site_adi_var('Bütün ayrıntılar sitede.'))

    def test_dil_kuralina_gore_bagli_kelime(self):
        self.assertGreater(v.kirma_cezasi('the', 'rifle', 'en'), v.kirma_cezasi('rifle', 'the', 'en'),
                           'İngilizcede "the" satır sonunda kalmaz')
        self.assertGreater(v.kirma_cezasi('de', 'armas', 'es'), v.kirma_cezasi('armas', 'de', 'es'),
                           'İspanyolcada "de" satır sonunda kalmaz')
        self.assertGreater(v.kirma_cezasi('le', 'fusil', 'fr'), v.kirma_cezasi('fusil', 'le', 'fr'),
                           'Fransızcada "le" satır sonunda kalmaz')
        self.assertEqual(v.kirma_cezasi('yeni', 'silah', 'tr'), 0.8)

    def test_fransizca_kesme_okunusu(self):
        okunus = {'Operation': 'Opereyşın'}
        self.assertEqual(v.okunus_uygula(["l'Operation"], okunus, dil='fr'), [([0], "l'Opereyşın")])
        self.assertEqual(v.okunus_uygula(["d'Operation,"], okunus, dil='fr'), [([0], "d'Opereyşın,")])
        self.assertEqual(v.okunus_uygula(["Operation"], okunus, dil='fr'), [([0], 'Opereyşın')])
        self.assertEqual(v.okunus_uygula(["l'Operation"], okunus, dil='tr'), [([0], "l'Operation")],
                         'kesme ayırma yalnız Fransızcada')

    def test_hizala_tanimadaki_sozlu_sayilari_esler(self):
        # Konuşma tanıma rakamı sözle yazar; iki taraf aynı çevrildiği için "750" üç tanıma kelimesine oturur.
        tani = [{'k': 'dakikada', 'b': 0.0, 's': 0.5}, {'k': 'yedi', 'b': 0.5, 's': 0.7}, {'k': 'yüz', 'b': 0.7, 's': 0.9},
                {'k': 'elli', 'b': 0.9, 's': 1.2}, {'k': 'mermi', 'b': 1.2, 's': 1.6}]
        birimler = ['dakikada', '750', 'mermi']
        self.araliklar_esit(v.hizala(birimler, tani, 'tr'), [(0.0, 0.5), (0.5, 1.2), (1.2, 1.6)])
        self.araliklar_esit(v.hizala(birimler, tani), [(0.0, 0.5), None, (1.2, 1.6)])

    def test_hizala_birlesik_tanima_kelimesini_ara_birimlere_boler(self):
        # "EA app, Steam, Epic" tek kelime ("eapic") duyuldu: iki uç arasındaki birimler o sürede söylenmiştir.
        tani = [{'k': 'eapic', 'b': 1.0, 's': 3.6}]
        self.araliklar_esit(v.hizala(['EA', 'app,', 'Steam,', 'Epic'], tani, 'tr'),
                            [(1.0, 1.4), (1.4, 2.0), (2.0, 3.0), (3.0, 3.6)])

    def test_duraklara_yerlestir(self):
        d = [(2.0, 2.5)]
        self.araliklar_esit(v._duraklara_yerlestir([(2.1, 2.9)], d), [(2.5, 2.9)])      # durakta başlayan, durak bitince
        self.araliklar_esit(v._duraklara_yerlestir([(1.5, 2.2)], d), [(1.5, 2.0)])      # durağa taşan, durak başında biter
        self.araliklar_esit(v._duraklara_yerlestir([(1.8, 2.8)], d), [(1.8, 2.8)])      # durağı kapsayan (MBZ-19) olduğu gibi
        self.araliklar_esit(v._duraklara_yerlestir([(1.0, 2.0), (2.6, 3.0)], d), [(1.0, 2.0), (2.5, 3.0)])  # geç başlayan
        self.araliklar_esit(v._duraklara_yerlestir([(1.0, 1.85), (2.5, 3.0)], d), [(1.0, 2.0), (2.5, 3.0)])  # erken biten
        self.araliklar_esit(v._duraklara_yerlestir([(1.0, 1.6), (2.9, 3.2)], d), [(1.0, 1.6), (2.9, 3.2)])   # 0,25 sn'den uzak
        self.assertEqual(v._duraklara_yerlestir([(1.0, 1.6)], ()), [(1.0, 1.6)])

    def test_sessizlikler_bolunmus_duragi_birlestirir(self):
        stderr = ('[silencedetect @ 0] silence_start: -0.01\n[silencedetect @ 0] silence_end: 0.2 | silence_duration: 0.21\n'
                  'silence_start: 12.09\nsilence_end: 12.98 | silence_duration: 0.89\n'
                  'silence_start: 12.99\nsilence_end: 13.53 | silence_duration: 0.54\n'
                  'silence_start: 20.0\nsilence_end: 20.3 | silence_duration: 0.3\n')
        cagrilar = []

        def kos(komut, **kw):
            cagrilar.append(komut)
            return subprocess.CompletedProcess(komut, 0, '', stderr)

        with patch.object(v, '_node', return_value='node'), patch.object(v, '_kos', kos):
            self.assertEqual(v.sessizlikler(pathlib.Path('ses.mp3')), [(0.0, 0.2), (12.09, 13.53), (20.0, 20.3)])
        self.assertIn(f'silencedetect=noise={v.DURAK_DB}dB:d={v.DURAK_SN}', cagrilar[0])

    def test_tanima_sonlarini_kirp(self):
        kel = [{'k': 'a', 'b': 1.0, 's': 2.15}, {'k': 'b', 'b': 2.5, 's': 3.0},
               {'k': 'c', 'b': 3.05, 's': 5.0},   # birleşik tanıma kelimesi: içindeki durakta kesilmez
               {'k': 'd', 'b': 5.1, 's': 6.3}, {'k': 'e', 'b': 6.32, 's': 7.0}]  # durak kelime ortasında
        yeni = v.tanima_sonlarini_kirp(kel, [(2.0, 2.5), (3.5, 3.8), (6.2, 6.6)])
        self.assertEqual([(w['b'], w['s']) for w in yeni], [(1.0, 2.0), (2.5, 3.0), (3.05, 5.0), (5.1, 6.3), (6.32, 7.0)])
        self.assertEqual(kel[0]['s'], 2.15, 'girdi değişmez')
        self.assertEqual(v.tanima_sonlarini_kirp([{'k': 'a', 'b': 1.98, 's': 2.1}], [(2.0, 2.5)])[0]['s'], 2.03)

    def test_sesle_hizala_durak_oncesinden_gelen_kelimeyi_tasimaz(self):
        # Durağı çok önceden başlayıp içine alan birleşik tanıma kelimesi durak sonrasına çekilmez.
        self.assertEqual(v.sesle_hizala([{'k': 'epic', 'b': 1.0, 's': 3.0}], [(2.0, 2.3)])[0]['b'], 1.0)
        self.assertEqual(v.sesle_hizala([{'k': 'epic', 'b': 1.95, 's': 3.0}], [(2.0, 2.3)])[0]['b'], 2.3)

    def test_zamanla_duraklari_kullanir(self):
        hazir = v.senaryo_hazirla(senaryo(), haber(), 'tr')
        sinirlar = sahte_sinirlar(hazir['tts'])
        n = len(hazir['sahneler'][0]['kelimeler'])
        son, ilk = sinirlar[n - 1]['s'], sinirlar[n]['b']
        duraklar = [(son + 0.1, ilk - 0.1)]
        duz = v.zamanla(hazir, sinirlar, sinirlar[-1]['s'] + 0.5)['kelimeler']
        z = v.zamanla(hazir, sinirlar, sinirlar[-1]['s'] + 0.5, duraklar)['kelimeler']
        self.assertEqual((duz[n - 1]['s'], duz[n]['b']), (round(son, 3), round(ilk, 3)), 'durak verilmezse değişmez')
        self.assertEqual((z[n - 1]['s'], z[n]['b']), (round(son + 0.1, 3), round(ilk - 0.1, 3)))
        self.assertEqual([(w['b'], w['s']) for w in z[:n - 1]], [(w['b'], w['s']) for w in duz[:n - 1]])


def baslik_sahnesi(son_soz=4.632, bit=5.733):
    """R6 haberinin başlık sahnesi zamanları (edge sesi): son söz `son_soz`ta biter, sahne `bit`te kayar."""
    kel = [('Rainbow', 0.296, 0.733), ('Six', 0.733, 0.92), ("Siege'in", 0.92, 1.357), ('yeni', 1.357, 1.62),
           ('sezonu', 1.62, 2.02), ('Operation', 2.02, 2.65), ('Vital', 2.65, 3.0), ('Signal,', 3.0, 3.42),
           ('1', 3.595, 3.664), ("Aralık'ta", 3.664, 4.22), ('geliyor.', 4.22, 4.632)]
    olcek = son_soz / 4.632
    return {'sablon': 'baslik', 'bas': 0.0, 'bit': bit,
            'veri': {'baslik': "Operation Vital Signal 1 Aralık'ta geliyor", 'tuslar': ['R', 'S', 'S'],
                     'vurgu': [{'metin': "1 Aralık'ta", 'goster': round(3.595 * olcek, 3)}]},
            'altyazi': [{'k': k, 'b': round(b * olcek, 3), 's': round(s * olcek, 3)} for k, b, s in kel]}


class KapakTests(unittest.TestCase):
    # Şablonlardaki giriş süreleri (video/src): kapak bunların hepsinden sonra, pencere kaymadan önce alınmalı.
    SABIT_GIRIS = max(0.3,                     # ilk pencere belirir (kamera.ts sahneKaymasi)
                      0.4,                     # marka şeridi (UstSerit)
                      0.3,                     # alt bilgi kartı (AltKart)
                      0.15 + 0.08 * 5 + 0.3,   # en çok 6 çip, yaylı belirme ~0.3 sn'de oturur (Baslik)
                      0.1 + 0.06 * 3 + 0.3,    # tuşların belirmesi
                      0.2 + 0.3)               # kehribar şerit

    def kontrol(self, sahne, fps=30):
        kare = v.kapak_karesi(sahne, fps)
        an = kare / fps
        self.assertIsInstance(kare, int)
        self.assertGreater(kare, 0, 'ilk kare boş zemindir')
        self.assertLess(an, sahne['bit'] - 0.05, 'pencere kaymaya başlamadan önce')
        return an

    def test_kapak_karesi_baslik_girisinden_sonra(self):
        s = baslik_sahnesi()
        an = self.kontrol(s)
        self.assertGreaterEqual(an, self.SABIT_GIRIS)
        self.assertGreaterEqual(an, s['altyazi'][-1]['s'] + 0.25, 'son başlık kelimesi yerine oturmuş')
        vurgu = s['veri']['vurgu'][0]
        self.assertGreaterEqual(an, vurgu['goster'] + 0.07 + 0.16, 'vurgu kutusu dolmuş')
        self.assertGreaterEqual(an, s['bit'] - 0.6, 'kamera bütün başlığı gösteriyor (baslikKamera)')
        self.assertEqual(v.kapak_karesi(s, 30), v.kapak_karesi(copy.deepcopy(s), 30), 'kararlı')

    def test_kapak_karesi_kisa_ve_sona_dayanan_baslik(self):
        # Anlatım sahne sonuna dayanırsa kare yine pencere kaymadan öncedir (şablon kapakta başlığı tam çizer).
        dayanan = baslik_sahnesi(son_soz=5.6, bit=5.733)
        self.assertLessEqual(self.kontrol(dayanan), dayanan['bit'] - 0.1 + 1e-9)
        # Sabit girişlerden kısa sahne olmaz (sonraki sahne en az 0.8 sn sonra başlar) ama olursa da sahne içinde kalır.
        kisa = baslik_sahnesi(son_soz=0.6, bit=0.9)
        self.assertLessEqual(self.kontrol(kisa), 0.8 + 1e-9)

    def test_props_kapak_karesini_tasir(self):
        hazir = v.senaryo_hazirla(senaryo(), haber(), 'tr')
        sinirlar = sahte_sinirlar(hazir['tts'])
        z = v.zamanla(hazir, sinirlar, sinirlar[-1]['s'] + 0.5)
        props = v.props_kur(haber(), 'tr', hazir, z)
        s = z['sahneler'][0]
        an = props['kapak_kare'] / props['fps']
        self.assertGreaterEqual(an, self.SABIT_GIRIS)
        self.assertGreaterEqual(an, s['altyazi'][-1]['s'] + 0.25)
        self.assertGreaterEqual(an, s['bit'] - 0.6)
        self.assertLess(an, s['bit'])

    def test_kapak_ayri_still_kompozisyonundan_cizilir(self):
        # renderStill bileşene seçilen kompozisyonun props'unu verir: `kapak` alanı ancak ayrı kompozisyonla ulaşır.
        kok = (v.VIDEO / 'src' / 'Kok.tsx').read_text(encoding='utf-8')
        render = (v.VIDEO / 'render.mjs').read_text(encoding='utf-8')
        self.assertIn('<Still', kok)
        self.assertIn('id="HaberKapak"', kok)
        self.assertIn("id: 'HaberKapak'", render)
        self.assertNotIn('kapak: true', render)


class AnahtarManifestTests(unittest.TestCase):
    AYAR ={'saglayici': 'edge', 'konusmaci': 'tr-TR-AhmetNeural', 'hiz': '+0%', 'paket': 'edge-tts==7.3.1'}

    def test_anahtar_kararli_ve_degisikliğe_duyarli(self):
        h, s = haber(), senaryo()
        k = v.anahtar(h, 'tr', s, self.AYAR)
        self.assertRegex(k, r'^[0-9a-f]{12}$')
        ters = json.loads(json.dumps(dict(reversed(list(h.items())))))
        self.assertEqual(v.anahtar(ters, 'tr', copy.deepcopy(s), dict(reversed(list(self.AYAR.items())))), k)
        h2 = haber()
        h2['diller']['tr']['metin'] += ' Ek bilgi.'
        self.assertNotEqual(v.anahtar(h2, 'tr', s, self.AYAR), k)
        self.assertNotEqual(v.anahtar(h, 'tr', s, {**self.AYAR, 'konusmaci': 'tr-TR-EmelNeural'}), k)
        s2 = senaryo()
        s2['sahneler'][1]['anlatim'] += ' Ek.'
        self.assertNotEqual(v.anahtar(h, 'tr', s2, self.AYAR), k)
        with patch.object(v, 'SABLON_SURUMU', v.SABLON_SURUMU + 1):
            self.assertNotEqual(v.anahtar(h, 'tr', s, self.AYAR), k)

    def test_manifest_youtube_instagram_ve_bilinmeyen_alanlari_korur(self):
        with tempfile.TemporaryDirectory() as t:
            yol = pathlib.Path(t) / 'videolar.json'
            m = v.manifest_oku(yol)
            self.assertEqual(m, {'surum': 1, 'taban': v.TABAN, 'videolar': {}})
            m['videolar'] = {'x': {'tr': {'anahtar': 'eski', 'youtube': 'https://youtu.be/abc', 'instagram': 'ig',
                                          'site_alani': 1}}}
            v.manifest_guncelle(m, 'x', 'tr', {'anahtar': 'yeni', 'sure': 30.0})
            v.manifest_guncelle(m, 'y', 'tr', {'anahtar': 'ilk'})
            v.manifest_yaz(m, yol)
            okunan = v.manifest_oku(yol)
            self.assertEqual(okunan['videolar']['x']['tr'], {'anahtar': 'yeni', 'sure': 30.0, 'youtube': 'https://youtu.be/abc',
                                                              'instagram': 'ig', 'site_alani': 1})
            self.assertEqual(okunan['videolar']['y']['tr'], {'anahtar': 'ilk', 'youtube': '', 'instagram': ''})
            self.assertEqual(yol.read_text(encoding='utf-8'),
                             json.dumps(okunan, ensure_ascii=False, indent=1, sort_keys=True) + '\n')
            yol.write_text('[]', encoding='utf-8')
            with self.assertRaises(v.UretimHatasi):
                v.manifest_oku(yol)

    def test_onay_yalniz_ayni_anahtarda_kalir(self):
        m = {'videolar': {'x': {'tr': {'anahtar': 'a1', 'onay': True, 'youtube': 'yt'}}}}
        v.manifest_guncelle(m, 'x', 'tr', {'anahtar': 'a1', 'sure': 30.0})  # aynı içerik --zorla ile yeniden üretildi
        self.assertIs(m['videolar']['x']['tr']['onay'], True)
        v.manifest_guncelle(m, 'x', 'tr', {'anahtar': 'b2', 'sure': 31.0})  # yeni ses/senaryo: yeniden onay gerekir
        self.assertNotIn('onay', m['videolar']['x']['tr'])
        self.assertEqual(m['videolar']['x']['tr']['youtube'], 'yt')
        m['videolar']['x']['tr']['onay'] = False
        v.manifest_guncelle(m, 'x', 'tr', {'anahtar': 'c3'})
        self.assertNotIn('onay', m['videolar']['x']['tr'])

    def test_depodaki_manifest_sozlesmeye_uyar(self):
        if not v.MANIFEST.exists():
            self.skipTest('data/videolar.json yok')
        m = v.json_oku(v.MANIFEST)
        # 'onay_gerekli' isteğe bağlıdır: false ise videolar onay beklemeden yayımlanır (Cio'nun kararı, 2026-11-17)
        self.assertEqual(set(m) - {'onay_gerekli'}, {'surum', 'taban', 'videolar'})
        self.assertEqual((m['surum'], m['taban']), (1, 'https://medya.ctrl-agame.com/v/'))
        alanlar = {'anahtar', 'sure', 'mp4_1080', 'mp4_720', 'mp4_540', 'kapak', 'vtt', 'uretildi', 'youtube', 'instagram'}
        for kimlik, diller in m['videolar'].items():
            for dil, g in diller.items():
                with self.subTest(f'{kimlik}-{dil}'):
                    # 'onay' isteğe bağlıdır: Cio onaylayınca tools/video_site.py yazar
                    self.assertEqual(set(g) - {'onay'}, alanlar)
                    k = g['anahtar']
                    self.assertEqual(g['mp4_1080'], f'{kimlik}-{dil}-{k}-1080.mp4')
                    self.assertEqual(g['vtt'], f'{kimlik}-{dil}-{k}.vtt')
                    self.assertEqual(g['kapak'], f'{kimlik}-{dil}-{k}-kapak.jpg')

    def test_video_ayari_varsayilanlari(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(v.video_ayari(pathlib.Path(t) / 'yok.json'),
                             {'ses': 'azure', 'konusmaci': {}, 'yukleme_hedefi': '', 'gunluk_en_fazla': 2, 'hype_esigi': 7})

    def test_video_ayari_hype_esigi_dosyadan_okunur(self):
        with tempfile.TemporaryDirectory() as t:
            yol = pathlib.Path(t) / 'ayarlar.json'
            yol.write_text(json.dumps({'video': {'hype_esigi': 9}}), encoding='utf-8')
            self.assertEqual(v.video_ayari(yol)['hype_esigi'], 9)


class HypeTests(unittest.TestCase):
    def test_hype_yeterli(self):
        self.assertTrue(v.hype_yeterli({'otomasyon': {}}, 7))
        self.assertTrue(v.hype_yeterli({'otomasyon': {'hype': 7}}, 7))
        self.assertTrue(v.hype_yeterli({'otomasyon': {'hype': 9}}, 7))
        self.assertFalse(v.hype_yeterli({'otomasyon': {'hype': 6}}, 7))
        self.assertFalse(v.hype_yeterli({'otomasyon': {'hype': True}}, 1))
        self.assertFalse(v.hype_yeterli({'otomasyon': {'hype': '9'}}, 7))

    def test_bekleyenler_hype_esik_altini_atlar(self):
        bugun = date(2026, 11, 16)
        with tempfile.TemporaryDirectory() as t, Ortam(t, manifest={'surum': 1, 'taban': v.TABAN, 'videolar': {}}):
            icerik = pathlib.Path(t) / 'icerik.json'
            x = haber()
            x['otomasyon'] = {'hype': 3}
            icerik.write_text(json.dumps([x], ensure_ascii=False), encoding='utf-8')
            self.assertEqual(v.bekleyenler('tr', bugun=bugun, cikti=lambda m: None, motor='remotion'), [])
            x['otomasyon']['hype'] = 7
            icerik.write_text(json.dumps([x], ensure_ascii=False), encoding='utf-8')
            self.assertEqual(v.bekleyenler('tr', bugun=bugun, cikti=lambda m: None, motor='remotion'), [KIMLIK])


class Ortam:
    """uret/bekleyenler için geçici depo: içerik, senaryo, ayar ve manifest yolları test klasörüne yönlenir."""

    def __init__(self, t, ayar=None, manifest=None):
        self.t = pathlib.Path(t)
        (self.t / 'senaryo').mkdir()
        (self.t / 'icerik.json').write_text(json.dumps([haber()], ensure_ascii=False), encoding='utf-8')
        (self.t / 'senaryo' / f'{KIMLIK}-tr.json').write_text(json.dumps(senaryo(), ensure_ascii=False), encoding='utf-8')
        (self.t / 'ayarlar.json').write_text(json.dumps({'video': ayar or {'ses': 'edge'}}), encoding='utf-8')
        if manifest is not None:
            v.manifest_yaz(manifest, self.t / 'videolar.json')
        self.yamalar = [patch.object(v, ad, self.t / dosya) for ad, dosya in
                        (('ICERIK', 'icerik.json'), ('SENARYO', 'senaryo'), ('AYARLAR', 'ayarlar.json'),
                         ('MANIFEST', 'videolar.json'), ('GECICI', 'tmp'), ('CIKTI', 'cikti'))]

    def __enter__(self):
        for y in self.yamalar:
            y.start()
        return self

    def __exit__(self, *a):
        for y in reversed(self.yamalar):
            y.stop()


def kayit(k, gun='2026-11-15'):
    taban = f'{KIMLIK}-tr-{k}'
    return {'anahtar': k, 'sure': 40.0, 'mp4_1080': f'{taban}-1080.mp4', 'mp4_720': f'{taban}-720.mp4',
            'mp4_540': f'{taban}-540.mp4', 'kapak': f'{taban}-kapak.jpg', 'vtt': f'{taban}.vtt',
            'uretildi': f'{gun}T10:00:00+03:00', 'youtube': '', 'instagram': ''}


class Durdu(Exception):
    pass


def durdur(komut, **kw):
    raise Durdu(komut)


class UretTests(unittest.TestCase):
    def setUp(self):
        # Bu sınıf eski (Remotion) yolun anahtarını sınar; Hyperframes anahtarı tests/test_video_hf.py'de.
        self.k = v.anahtar(haber(), 'tr', senaryo(), v.seslendirici('edge', '', 'tr', KIMLIK).ayar())

    def test_hazir_video_yeniden_uretilmez(self):
        with tempfile.TemporaryDirectory() as t, Ortam(t, manifest={'surum': 1, 'taban': v.TABAN,
                                                                     'videolar': {KIMLIK: {'tr': kayit(self.k)}}}), \
                patch.object(v, '_calistir', durdur):
            mesaj = []
            sonuc = v.uret(KIMLIK, 'tr', yukle=True, cikti=mesaj.append, motor='remotion')
        self.assertEqual(sonuc['anahtar'], self.k)
        self.assertIn(f'atlandı: {KIMLIK} tr zaten hazır (anahtar {self.k})', mesaj)
        self.assertIn('yükleme atlandı: sosyal/ayarlar.json içinde video.yukleme_hedefi boş', mesaj)

    def test_degisen_anahtar_yeniden_uretir(self):
        with tempfile.TemporaryDirectory() as t, Ortam(t, manifest={'surum': 1, 'taban': v.TABAN,
                                                                     'videolar': {KIMLIK: {'tr': kayit('eskieskieski')}}}), \
                patch.object(v, '_calistir', durdur), patch.object(v.shutil, 'which', return_value='uv'):
            with self.assertRaises(Durdu) as c:
                v.uret(KIMLIK, 'tr', cikti=lambda m: None, motor='remotion')
            komut = c.exception.args[0]
            girdi = json.loads((pathlib.Path(t) / 'tmp' / 'ses').glob('*/tts-girdi.json').__next__().read_text('utf-8'))
        self.assertIn('edge-tts==7.3.1', komut)
        self.assertIn("Control A Game'de.", girdi['metin'])
        self.assertNotIn('nokta', girdi['metin'])

    def test_bekleyenler_ve_gunluk_sinir(self):
        bugun = date(2026, 11, 16)
        with tempfile.TemporaryDirectory() as t, Ortam(t, manifest={'surum': 1, 'taban': v.TABAN, 'videolar': {}}):
            self.assertEqual(v.bekleyenler('tr', bugun=bugun, cikti=lambda m: None, motor='remotion'), [KIMLIK])
            self.assertEqual(v.bekleyenler('tr', bugun=date(2026, 11, 25), cikti=lambda m: None, motor='remotion'), [])
        dolu = {'surum': 1, 'taban': v.TABAN, 'videolar': {'baska-haber': {'tr': kayit('aaaaaaaaaaaa', '2026-11-16')}}}
        with tempfile.TemporaryDirectory() as t, Ortam(t, ayar={'ses': 'edge', 'gunluk_en_fazla': 1}, manifest=dolu):
            self.assertEqual(v.bekleyenler('tr', gunluk=True, bugun=bugun, cikti=lambda m: None, motor='remotion'), [])
            self.assertEqual(v.bekleyenler('tr', gunluk=False, bugun=bugun, cikti=lambda m: None, motor='remotion'), [KIMLIK])
        hazir = {'surum': 1, 'taban': v.TABAN, 'videolar': {KIMLIK: {'tr': kayit(self.k)}}}
        with tempfile.TemporaryDirectory() as t, Ortam(t, manifest=hazir):
            self.assertEqual(v.bekleyenler('tr', bugun=bugun, cikti=lambda m: None, motor='remotion'), [])

    def test_kota_dil_basina_sayilir(self):
        # Türkçede kota dolu; İngilizce kendi kotasını bağımsız kullanır.
        bugun = date(2026, 11, 16)
        dolu = {'surum': 1, 'taban': v.TABAN, 'videolar': {'a': {'tr': kayit('a' * 12, '2026-11-16')},
                                                          'b': {'tr': kayit('b' * 12, '2026-11-16')}}}
        with tempfile.TemporaryDirectory() as t, Ortam(t, ayar={'ses': 'edge', 'gunluk_en_fazla': 2}, manifest=dolu):
            self.assertEqual(v.bugun_uretilen_dil(v.manifest_oku(), 'tr', bugun), 2)
            self.assertEqual(v.bugun_uretilen_dil(v.manifest_oku(), 'en', bugun), 0)
            self.assertEqual(v.bekleyenler('tr', gunluk=True, bugun=bugun, cikti=lambda m: None, motor='remotion'), [])
            self.assertEqual(v.bekleyenler('tr', gunluk=False, bugun=bugun, cikti=lambda m: None, motor='remotion'), [KIMLIK])

    def test_dogrula_cikis_kodu(self):
        with tempfile.TemporaryDirectory() as t, Ortam(t):
            mesaj = []
            self.assertEqual(v.dogrula(KIMLIK, 'tr', cikti=mesaj.append), 0)
            self.assertTrue(mesaj[-1].startswith(f'geçerli: {KIMLIK}-tr (6 sahne'))
            mesaj = []
            self.assertEqual(v.dogrula('olmayan-haber', 'tr', cikti=mesaj.append), 1)
            self.assertTrue(mesaj[0].startswith('hata: senaryo yok'))


class YuklemeTests(unittest.TestCase):
    def test_bos_hedef_atlanir(self):
        mesaj = []
        self.assertFalse(v.yukle_dosyalar([pathlib.Path('yok.mp4')], '', mesaj.append))
        self.assertEqual(mesaj, ['yükleme atlandı: sosyal/ayarlar.json içinde video.yukleme_hedefi boş'])

    def test_gecersiz_hedef_reddedilir(self):
        for hedef in ('-oProxyCommand=calc:/x', 'kullanici@sunucu:/yol; rm -rf /', 'sunucu', 'a b:/c', '$(id):/v'):
            with self.subTest(hedef), self.assertRaises(v.UretimHatasi):
                v.yukle_dosyalar([], hedef, lambda m: None)

    def test_scp_liste_argumaniyla_cagrilir(self):
        with tempfile.TemporaryDirectory() as t:
            dosyalar = [pathlib.Path(t) / 'a-1080.mp4', pathlib.Path(t) / 'a.vtt']
            for d in dosyalar:
                d.write_bytes(b'x')
            kosucu = Kosucu()
            with patch.object(v, '_calistir', kosucu), patch.object(v.shutil, 'which', return_value='scp'):
                self.assertTrue(v.yukle_dosyalar(dosyalar, 'medya@sunucu.example:/srv/v/', lambda m: None))
                with self.assertRaises(v.UretimHatasi):
                    v.yukle_dosyalar(dosyalar + [pathlib.Path(t) / 'eksik.jpg'], 'medya@sunucu.example:/srv/v/',
                                     lambda m: None)
        komut, kw = kosucu.cagrilar[0]
        self.assertEqual(komut, ['scp', '-q', '-B', '--', *map(str, dosyalar), 'medya@sunucu.example:/srv/v/'])
        self.assertNotIn('shell', kw)
        self.assertEqual(len(kosucu.cagrilar), 1)


class SeslendirmeTests(unittest.TestCase):
    def test_konusmaci_secimi(self):
        self.assertEqual(v.seslendirici('edge', 'tr-TR-AhmetNeural', 'en').konusmaci, 'en-US-AndrewNeural')
        self.assertEqual(v.seslendirici('azure', 'tr-TR-EmelNeural', 'tr').konusmaci, 'tr-TR-EmelNeural')
        self.assertEqual(v.seslendirici('edge', '', 'tr').konusmaci, 'tr-TR-AhmetNeural')
        self.assertEqual(v.seslendirici('edge', '', 'tr').ayar()['paket'], 'edge-tts==7.3.1')
        with self.assertRaises(v.UretimHatasi):
            v.seslendirici('google', '', 'tr')
        with self.assertRaises(v.UretimHatasi):
            v.seslendirici('edge', 'tr-TR-Ahmet;calc', 'tr')
        self.assertEqual(v.seslendirici('azure', 'tr-TR-Aydin:MAI-Voice-2.1', 'tr').konusmaci, 'tr-TR-Aydin:MAI-Voice-2.1')
        for kotu in ('tr-TR-Aydin:MAI;calc', 'tr-TR-Aydin:', 'tr-TR-Aydin:MAI-Voice-2.', "tr-TR-Aydin:MAI'><x",
                     'tr-TR-Aydin:MAI Voice', 'tr-TR-Aydin', 'tr-TR-Aydin:-MAI'):
            with self.subTest(kotu), self.assertRaises(v.UretimHatasi):
                v.seslendirici('azure', kotu, 'tr')

    def test_depodaki_ses_ayari_gecerli_ve_aynen_kullanilir(self):
        if not v.AYARLAR.exists():
            self.skipTest('sosyal/ayarlar.json yok')
        ayar = v.video_ayari()
        self.assertEqual(set(ayar['konusmaci']), {'tr', 'en', 'es', 'fr', 'de', 'nl', 'zh'},
                         'her dilin kendi 3 sesli listesi var')
        for dil, liste in ayar['konusmaci'].items():
            self.assertEqual(len(liste), 3, f'{dil}: üç ses')
            self.assertEqual(len(set(liste)), 3, f'{dil}: sesler birbirinden farklı')
            for hid in ('a', 'b', 'c', 'd', 'e', 'f'):
                self.assertIn(v.seslendirici(ayar['ses'], ayar['konusmaci'], dil, hid).konusmaci, liste,
                              f'{dil}: ayardaki ses varsayılana düşmeden kullanılır')
        self.assertEqual(ayar['konusmaci']['tr'][0], 'tr-TR-Aydin:MAI-Voice-2.1', 'Türkçe mevcut ses değişmedi')

    def test_konusmaci_dil_basina_secilir(self):
        harita = {'tr': 'tr-TR-Aydin:MAI-Voice-2.1', 'en': 'en-US-GuyNeural', 'es': 'es-ES-AlvaroNeural'}
        for dil, ad in harita.items():
            self.assertEqual(v.seslendirici('azure', harita, dil).konusmaci, ad)
        self.assertEqual(v.seslendirici('azure', harita, 'fr').konusmaci, v.VARSAYILAN_KONUSMACI['fr'],
                         'haritada olmayan dil varsayılana düşer')
        with tempfile.TemporaryDirectory() as t:
            yol = pathlib.Path(t) / 'a.json'
            yol.write_text(json.dumps({'video': {'konusmaci': 'tr-TR-Aydin:MAI-Voice-2.1'}}), encoding='utf-8')
            self.assertEqual(v.video_ayari(yol)['konusmaci'], {'tr': ['tr-TR-Aydin:MAI-Voice-2.1']},
                             'eski tek değerli biçim kendi dilinin sesi olarak okunur')

    def test_azure_sinirsiz_ses_zamanlari_tanimadan_alir(self):
        # MAI sesi kelime sınırı göndermez: mp3 WAV'a açılır, aynı yardımcı `tani` kipinde çalışır, durak önündeki
        # tanıma bitişleri kırpılır. Metin ve anahtar hiçbir komuta girmez; tanımaya metin de gitmez.
        metin = 'Merhaba $(calc) dünya'
        ffmpeg_cagrilari = []

        def yap(komut):
            if komut[9] == 'azure':
                pathlib.Path(komut[-2]).write_bytes(b'ID3')
                pathlib.Path(komut[-1]).write_text(json.dumps({'olaylar': []}), encoding='utf-8')
            else:
                pathlib.Path(komut[-1]).write_text(json.dumps({'olaylar': [
                    {'metin': 'dünya', 'bas': 12_000_000, 'sure': 4_000_000},
                    {'metin': 'merhaba', 'bas': 1_000_000, 'sure': 8_500_000}]}), encoding='utf-8')

        def sahte_ffmpeg(*arg):
            ffmpeg_cagrilari.append(arg)
            pathlib.Path(arg[-1]).write_bytes(b'RIFF')

        kosucu = Kosucu(yap)
        with patch.dict(os.environ, {'AZURE_SPEECH_KEY': 'sahte-anahtar-123', 'AZURE_SPEECH_REGION': 'northeurope'}), \
                tempfile.TemporaryDirectory() as t, patch.object(v, '_calistir', kosucu), \
                patch.object(v.shutil, 'which', return_value='uv'), patch.object(v, 'ffmpeg', sahte_ffmpeg), \
                patch.object(v, 'sessizlikler', return_value=[(0.8, 1.2)]):
            klasor = pathlib.Path(t) / 'ses'
            ses, kel = v.seslendirici('azure', 'tr-TR-Aydin:MAI-Voice-2.1', 'tr').seslendir(metin, klasor)
            tts_girdi = json.loads((klasor / 'tts-girdi.json').read_text(encoding='utf-8'))
            tani_girdi = json.loads((klasor / 'tani-girdi.json').read_text(encoding='utf-8'))
        self.assertEqual([k[9] for k, _ in kosucu.cagrilar], ['azure', 'tani'])
        komut, kw = kosucu.cagrilar[1]
        self.assertEqual(komut[:9], ['uv', 'run', '--quiet', '--no-project', '--with',
                                     'azure-cognitiveservices-speech==1.53.1', 'python', '-I', str(v.YARDIMCI)])
        self.assertEqual(komut[10:], [str(klasor / 'tani-girdi.json'), str(klasor / 'tani.wav'),
                                      str(klasor / 'tani-olaylar.json')])
        self.assertNotIn('shell', kw)
        for k, _ in kosucu.cagrilar:
            self.assertFalse(any('calc' in a or 'sahte-anahtar' in a for a in k))
        self.assertEqual(ffmpeg_cagrilari, [('-i', str(ses), '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le',
                                             str(klasor / 'tani.wav'))])
        self.assertEqual(tts_girdi['konusmaci'], 'tr-TR-Aydin:MAI-Voice-2.1')
        self.assertEqual(tani_girdi, {'dil': 'tr-TR'})
        self.assertEqual(kel, [{'k': 'merhaba', 'b': 0.1, 's': 0.8}, {'k': 'dünya', 'b': 1.2, 's': 1.6}])

    def test_azure_tanima_basarisizsa_hata_verir(self):
        def kosucu(komut, **kw):
            if komut[9] == 'azure':
                pathlib.Path(komut[-2]).write_bytes(b'ID3')
                pathlib.Path(komut[-1]).write_text(json.dumps({'olaylar': []}), encoding='utf-8')
                return subprocess.CompletedProcess(komut, 0, '', '')
            return subprocess.CompletedProcess(komut, 1, '', 'Azure konuşma tanıma başarısız: kota')

        with patch.dict(os.environ, {'AZURE_SPEECH_KEY': 'x', 'AZURE_SPEECH_REGION': 'northeurope'}), \
                tempfile.TemporaryDirectory() as t, patch.object(v, '_calistir', kosucu), \
                patch.object(v.shutil, 'which', return_value='uv'), \
                patch.object(v, 'ffmpeg', lambda *a: pathlib.Path(a[-1]).write_bytes(b'RIFF')), \
                self.assertRaises(v.UretimHatasi) as c:
            v.seslendirici('azure', 'tr-TR-Aydin:MAI-Voice-2.1', 'tr').seslendir('Merhaba', pathlib.Path(t))
        self.assertIn('azure konuşma tanıma başarısız', str(c.exception))
        self.assertIn('kota', str(c.exception))

    def test_azure_ortam_degiskeni_yoksa_durur(self):
        with patch.dict(os.environ):
            os.environ.pop('AZURE_SPEECH_KEY', None)
            os.environ.pop('AZURE_SPEECH_REGION', None)
            with tempfile.TemporaryDirectory() as t, patch.object(v, '_calistir', durdur), \
                    self.assertRaises(v.UretimHatasi) as c:
                v.seslendirici('azure', '', 'tr').seslendir('Merhaba', pathlib.Path(t))
        self.assertIn('AZURE_SPEECH_KEY', str(c.exception))

    def test_azure_sahte_kosucuyla_metin_dosyadan_gider(self):
        metin = 'Merhaba $(calc) `id` ; dünya'
        kosucu = Kosucu(ses_yaz)
        with patch.dict(os.environ, {'AZURE_SPEECH_KEY': 'sahte-anahtar-123', 'AZURE_SPEECH_REGION': 'westeurope'}), \
                tempfile.TemporaryDirectory() as t, patch.object(v, '_calistir', kosucu), \
                patch.object(v.shutil, 'which', return_value='uv'):
            ses, kel = v.seslendirici('azure', '', 'tr').seslendir(metin, pathlib.Path(t) / 'ses')
            girdi = (pathlib.Path(t) / 'ses' / 'tts-girdi.json').read_text(encoding='utf-8')
            self.assertTrue(ses.exists())
        komut, kw = kosucu.cagrilar[0]
        self.assertEqual(komut[:9], ['uv', 'run', '--quiet', '--no-project', '--with',
                                     'azure-cognitiveservices-speech==1.53.1', 'python', '-I', str(v.YARDIMCI)])
        self.assertEqual(komut[9], 'azure')
        self.assertNotIn('shell', kw)
        self.assertFalse(any(metin in a or 'sahte-anahtar' in a for a in komut))
        self.assertEqual(json.loads(girdi), {'metin': metin, 'konusmaci': 'tr-TR-AhmetNeural', 'hiz': '+0%', 'dil': 'tr-TR'})
        self.assertNotIn('sahte-anahtar', girdi)
        self.assertEqual(kel, [{'k': 'Merhaba', 'b': 0.1, 's': 0.5}, {'k': 'dünya', 'b': 0.5, 's': 0.8}])

    def test_basarisiz_seslendirme_hata_verir(self):
        with tempfile.TemporaryDirectory() as t, patch.object(v, '_calistir', Kosucu(kod=1)), \
                patch.object(v.shutil, 'which', return_value='uv'), self.assertRaises(v.UretimHatasi) as c:
            v.seslendirici('edge', '', 'tr').seslendir('Merhaba', pathlib.Path(t))
        self.assertIn('edge seslendirme başarısız', str(c.exception))


def tanima_sonucu(*kelimeler, neden='tanindi'):
    """Tanıyıcının `recognized` olayı: Detailed biçimli JSON (100 ns birim)."""
    sozler = [{'Word': k, 'Offset': b, 'Duration': s} for k, b, s in kelimeler]
    return SimpleNamespace(result=SimpleNamespace(reason=neden, json=json.dumps({'NBest': [{'Words': sozler}]})))


class SahteSdk:
    """azure-cognitiveservices-speech arayüzünün yardımcıda kullanılan kısmı (seslendirme ve konuşma tanıma)."""

    SpeechSynthesisOutputFormat = SimpleNamespace(Audio24Khz96KBitRateMonoMp3='mp3-24k')
    ResultReason = SimpleNamespace(SynthesizingAudioCompleted='tamam', RecognizedSpeech='tanindi')
    OutputFormat = SimpleNamespace(Detailed='ayrintili')
    CancellationReason = SimpleNamespace(EndOfStream='akis_bitti', Error='hata')

    def __init__(self, sonuc='tamam', sinirlar=True, tanima=(), iptal='akis_bitti', biter=True):
        sdk = self
        self.kayit = {}
        self.audio = SimpleNamespace(AudioOutputConfig=lambda filename: SimpleNamespace(filename=filename),
                                     AudioConfig=lambda filename: SimpleNamespace(filename=filename))

        class SpeechConfig:
            def __init__(self, subscription, region):
                sdk.kayit['abonelik'] = (subscription, region)
                sdk.kayit['ayar'] = self

            def set_speech_synthesis_output_format(self, bicim):
                sdk.kayit['bicim'] = bicim

            def request_word_level_timestamps(self):
                sdk.kayit['kelime_zamani'] = True

        class SpeechSynthesizer:
            def __init__(self, speech_config, audio_config):
                sdk.kayit['dosya'] = audio_config.filename
                self._dinleyiciler = []
                self.synthesis_word_boundary = SimpleNamespace(connect=self._dinleyiciler.append)

            def speak_ssml_async(self, ssml):
                sdk.kayit['ssml'] = ssml
                olaylar = (SimpleNamespace(text='Merhaba', audio_offset=1_000_000, duration=timedelta(milliseconds=400),
                                           boundary_type='SpeechSynthesisBoundaryType.Word'),
                           SimpleNamespace(text=',', audio_offset=5_000_000, duration=timedelta(0),
                                           boundary_type='SpeechSynthesisBoundaryType.Punctuation'))
                for olay in olaylar if sinirlar else ():
                    for d in self._dinleyiciler:
                        d(olay)
                return SimpleNamespace(get=lambda: SimpleNamespace(
                    reason=sonuc, cancellation_details=SimpleNamespace(error_details='kota bitti')))

        class SpeechRecognizer:
            def __init__(self, speech_config, audio_config):
                sdk.kayit['wav'] = audio_config.filename
                self._d = {'recognized': [], 'canceled': [], 'session_stopped': []}
                for ad, liste in self._d.items():
                    setattr(self, ad, SimpleNamespace(connect=liste.append))

            def _ates(self, ad, olay):
                for d in self._d[ad]:
                    d(olay)

            def start_continuous_recognition(self):
                if not biter:
                    return
                for olay in tanima:
                    self._ates('recognized', olay)
                self._ates('canceled', SimpleNamespace(cancellation_details=SimpleNamespace(
                    reason=iptal, error_details='kota bitti' if iptal != 'akis_bitti' else '')))
                self._ates('session_stopped', SimpleNamespace())

            def stop_continuous_recognition(self):
                sdk.kayit['durdu'] = True

        self.SpeechConfig, self.SpeechSynthesizer, self.SpeechRecognizer = SpeechConfig, SpeechSynthesizer, SpeechRecognizer


class YardimciTests(unittest.TestCase):
    GIRDI = {'metin': "A <b> & C'", 'konusmaci': 'tr-TR-AhmetNeural', 'hiz': '+0%', 'dil': 'tr-TR'}

    def test_azure_sahte_sdk(self):
        sdk = SahteSdk()
        with patch.dict(os.environ, {'AZURE_SPEECH_KEY': 'sahte', 'AZURE_SPEECH_REGION': 'westeurope'}):
            olaylar = yardimci.azure(self.GIRDI, 'ses.mp3', sdk=sdk)
        self.assertEqual(olaylar, [{'metin': 'Merhaba', 'bas': 1_000_000, 'sure': 4_000_000}])
        self.assertEqual(sdk.kayit['abonelik'], ('sahte', 'westeurope'))
        self.assertEqual((sdk.kayit['bicim'], sdk.kayit['dosya']), ('mp3-24k', 'ses.mp3'))
        self.assertIn('A &lt;b&gt; &amp; C', sdk.kayit['ssml'])
        self.assertNotIn('<b>', sdk.kayit['ssml'])
        self.assertIn("<voice name='tr-TR-AhmetNeural'>", sdk.kayit['ssml'])

    def test_azure_iptal_ve_eksik_anahtar(self):
        with patch.dict(os.environ, {'AZURE_SPEECH_KEY': 'sahte', 'AZURE_SPEECH_REGION': 'westeurope'}), \
                self.assertRaises(SystemExit) as c:
            yardimci.azure(self.GIRDI, 'ses.mp3', sdk=SahteSdk(sonuc='iptal'))
        self.assertIn('kota bitti', str(c.exception))
        with patch.dict(os.environ):
            os.environ.pop('AZURE_SPEECH_KEY', None)
            with self.assertRaises(SystemExit):
                yardimci.azure(self.GIRDI, 'ses.mp3', sdk=SahteSdk())

    def test_azure_mai_sesi_sinirsiz_doner(self):
        sdk = SahteSdk(sinirlar=False)
        with patch.dict(os.environ, {'AZURE_SPEECH_KEY': 'sahte', 'AZURE_SPEECH_REGION': 'northeurope'}):
            olaylar = yardimci.azure({**self.GIRDI, 'konusmaci': 'tr-TR-Aydin:MAI-Voice-2.1'}, 'ses.mp3', sdk=sdk)
        self.assertEqual(olaylar, [])
        self.assertIn("<voice name='tr-TR-Aydin:MAI-Voice-2.1'>", sdk.kayit['ssml'])

    def test_tani_kelime_zamanlarini_sirali_verir(self):
        sdk = SahteSdk(tanima=(tanima_sonucu(('dünya', 12_000_000, 3_000_000)),
                               tanima_sonucu(('boş', 0, 1), neden='eslesmedi'),
                               tanima_sonucu(('merhaba', 1_000_000, 4_000_000), ('güzel', 6_000_000, 2_000_000))))
        with patch.dict(os.environ, {'AZURE_SPEECH_KEY': 'sahte', 'AZURE_SPEECH_REGION': 'northeurope'}):
            olaylar = yardimci.tani({'dil': 'tr-TR'}, 'tani.wav', sdk=sdk)
        self.assertEqual(olaylar, [{'metin': 'merhaba', 'bas': 1_000_000, 'sure': 4_000_000},
                                   {'metin': 'güzel', 'bas': 6_000_000, 'sure': 2_000_000},
                                   {'metin': 'dünya', 'bas': 12_000_000, 'sure': 3_000_000}])
        ayar = sdk.kayit['ayar']
        self.assertEqual((ayar.speech_recognition_language, ayar.output_format), ('tr-TR', 'ayrintili'))
        self.assertTrue(sdk.kayit['kelime_zamani'])
        self.assertEqual((sdk.kayit['abonelik'], sdk.kayit['wav']), (('sahte', 'northeurope'), 'tani.wav'))
        self.assertTrue(sdk.kayit['durdu'])

    def test_tani_hata_zaman_asimi_ve_eksik_anahtar(self):
        with patch.dict(os.environ, {'AZURE_SPEECH_KEY': 'sahte', 'AZURE_SPEECH_REGION': 'northeurope'}):
            with self.assertRaises(SystemExit) as c:
                yardimci.tani({'dil': 'tr-TR'}, 'tani.wav', sdk=SahteSdk(iptal='hata'))
            self.assertIn('kota bitti', str(c.exception))
            with self.assertRaises(SystemExit) as c:
                yardimci.tani({'dil': 'tr-TR'}, 'tani.wav', sdk=SahteSdk(biter=False), bekleme=0.01)
            self.assertIn('bitmedi', str(c.exception))
        with patch.dict(os.environ):
            os.environ.pop('AZURE_SPEECH_KEY', None)
            with self.assertRaises(SystemExit):
                yardimci.tani({'dil': 'tr-TR'}, 'tani.wav', sdk=SahteSdk())

    def test_main_bos_sinir_yalniz_azurede_kabul(self):
        with tempfile.TemporaryDirectory() as t:
            girdi, olay = pathlib.Path(t) / 'girdi.json', pathlib.Path(t) / 'olay.json'
            girdi.write_text(json.dumps({'metin': 'a', 'konusmaci': 'tr-TR-Aydin:MAI-Voice-2.1'}), encoding='utf-8')
            bos = lambda g, s: []  # noqa: E731
            with patch.dict(yardimci.SAGLAYICILAR, {'azure': bos, 'edge': bos, 'tani': bos}):
                yardimci.main(['azure', str(girdi), 'ses.mp3', str(olay)])
                self.assertEqual(json.loads(olay.read_text(encoding='utf-8')),
                                 {'saglayici': 'azure', 'konusmaci': 'tr-TR-Aydin:MAI-Voice-2.1', 'olaylar': []})
                for saglayici, mesaj in (('edge', 'kelime sınırı gelmedi'), ('tani', 'seste kelime tanınmadı')):
                    with self.subTest(saglayici), self.assertRaises(SystemExit) as c:
                        yardimci.main([saglayici, str(girdi), 'ses.mp3', str(pathlib.Path(t) / 'yok.json')])
                    self.assertIn(mesaj, str(c.exception))

    def test_yardimci_bilinmeyen_saglayiciyi_reddeder(self):
        with self.assertRaises(SystemExit):
            yardimci.main(['python', 'a.json', 'b.mp3', 'c.json'])


def makale(oid='oyun-yama-1'):
    return {'id': oid, 'tarih': '2026-11-15', 'oyun': 'Oyun', 'tur': 'guncelleme',
            'kaynaklar': [{'url': 'https://blog.playstation.com/2026/11/15/game-patch/', 'ad': 'PlayStation Blog'}],
            'diller': {d: {'baslik': 'Yeni oyun yaması', 'ozet': 'Yama yayımlandı.',
                           'metin': '游' * 120 if d == 'zh' else ' '.join(['Bilgi'] * 60)} for d in haber_oto.DILLER},
            'otomasyon': {'konu': oid, 'resmi_url': 'https://blog.playstation.com/2026/11/15/game-patch/',
                          'teyit_zamani': '2026-11-15T08:00:00+00:00',
                          'oyuncuya_fayda': 'Kaydetme hatası giderildi; oyuncu yamasını kurabilir.',
                          'hype': 3}}


class HaberOtoTests(unittest.TestCase):
    def test_senaryo_denetle(self):
        with tempfile.TemporaryDirectory() as t:
            klasor = pathlib.Path(t)
            self.assertEqual(haber_oto.senaryo_denetle(haber(), klasor), [])
            (klasor / f'{KIMLIK}-tr.json').write_text(json.dumps(senaryo(), ensure_ascii=False), encoding='utf-8')
            self.assertEqual(haber_oto.senaryo_denetle(haber(), klasor), [])
            s = senaryo()
            s['sahneler'][2]['veri']['satirlar'][0]['yeni'] = '99'
            (klasor / f'{KIMLIK}-tr.json').write_text(json.dumps(s, ensure_ascii=False), encoding='utf-8')
            hata = haber_oto.senaryo_denetle(haber(), klasor)
            self.assertEqual(hata, [f'{KIMLIK}-tr.json: sahneler[2].veri.satirlar[0].yeni: "99" sayısı haber metninde yok'])

    def test_hazirla_bozuk_senaryolu_haberi_yayimlamaz(self):
        from datetime import datetime, timezone
        simdi = datetime(2026, 11, 15, 8, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as t, patch.object(haber_oto, 'SENARYO', pathlib.Path(t)):
            self.assertEqual(len(haber_oto.hazirla([], [makale()], simdi)[1]), 1)
            (pathlib.Path(t) / 'oyun-yama-1-tr.json').write_text(
                json.dumps({'id': 'oyun-yama-1', 'dil': 'tr', 'sahneler': []}), encoding='utf-8')
            with self.assertRaises(ValueError) as c:
                haber_oto.hazirla([], [makale()], simdi)
        self.assertIn('video senaryosu', str(c.exception))
        self.assertIn('3–9 sahnelik', str(c.exception))



# guvenli.mjs kuralını sentetik ölçümlerle çalıştırır: ölçüm JSON'u stdin'den gelir, modülün yolu argümandır.
GUVENLI_KOSUCU = ("import {pathToFileURL} from 'node:url';"
                  "const {denetle} = await import(pathToFileURL(process.argv[1]).href);"
                  "let girdi = ''; for await (const p of process.stdin) girdi += p;"
                  "const {olcumler, guvenli} = JSON.parse(girdi);"
                  "process.stdout.write(JSON.stringify(denetle(olcumler, guvenli)));")


class GuvenliAlanTests(unittest.TestCase):
    def setUp(self):
        self.g = v.duzen()['guvenli']
        # Sentetik ölçüm deneyi Remotion çalıştırmaz; yalnız Node gerekir.
        import shutil
        node = shutil.which('node')
        if not node:
            self.skipTest('Node bulunamadı')
        p = patch.object(v, '_node', return_value=node)
        p.start()
        self.addCleanup(p.stop)

    def denetle(self, olcumler):
        r = subprocess.run([shutil.which('node'), '--input-type=module', '-e', GUVENLI_KOSUCU, str(v.VIDEO / 'guvenli.mjs')],
                           input=json.dumps({'olcumler': olcumler, 'guvenli': self.g}), capture_output=True,
                           text=True, encoding='utf-8', timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_kural_karenin_disini_ve_dugme_rayini_yakalar(self):
        g = self.g
        oge = lambda metin, x0, y0, x1, y1: {'tur': 'yazi', 'metin': metin, 'x0': x0, 'y0': y0, 'x1': x1, 'y1': y1}
        olcumler = [
            {'kare': 0, 'ogeler': [oge('içeride', g['sol'], g['ust'], g['sag'], g['ust'] + 40),
                                   oge('raydan önce', 600, 1200, g['ray_x'], 1260),
                                   oge('rayın üstünde', 700, 800, 950, g['ray_y'])]},
            {'kare': 1, 'ogeler': [oge('solda', g['sol'] - 3, 500, 300, 540)]},
            {'kare': 2, 'ogeler': [oge('rayda', 700, 1100, g['ray_x'] + 12, 1160)]},
            {'kapak': True, 'ogeler': [oge('altta', 100, 1450, 400, g['alt'] + 6), oge('solda', g['sol'] - 9, 500, 300, 540)]},
        ]
        r = self.denetle(olcumler)
        self.assertEqual((r['kare_sayisi'], r['oge_sayisi'], r['ihlalli_kare'], r['ihlal_sayisi']), (4, 7, 3, 4))
        bulunan = {(i['metin'], i['yon']): (i['kareler'], i['en_cok']) for i in r['ihlaller']}
        self.assertEqual(bulunan, {('solda', 'sol'): ([1, 'kapak'], 9), ('rayda', 'ray'): ([2], 12),
                                   ('altta', 'alt'): (['kapak'], 6)})

    def test_alt_kart_ve_altyazi_platform_arayuzunden_uzak(self):
        # YouTube uygulamasında ölçülen kanal adı/başlık bandı (y >= 1534) ve sağ düğme rayı (x >= 906, y >= 1046)
        # güvenli sınırların dışında kalır; kart ve altyazı kutusu bu sınırların içindedir.
        d = v.duzen()
        g, kart, a = d['guvenli'], d['kart'], d['altyazi']
        self.assertLessEqual(g['alt'], 1534)
        self.assertLessEqual(g['ray_x'], 906)
        self.assertLessEqual(g['ray_y'], 1046)
        self.assertGreaterEqual(kart['sol'], g['sol'])
        self.assertLessEqual(kart['sol'] + kart['genislik'], g['ray_x'])
        self.assertLessEqual(kart['ust'] + kart['yukseklik'], g['alt'])
        self.assertGreaterEqual(a['merkez_x'] - a['en_genis_kutu'] / 2, g['sol'])
        self.assertLessEqual(a['merkez_x'] + a['en_genis_kutu'] / 2, g['ray_x'])
        self.assertLessEqual(d['sahne']['alt'], kart['ust'])

    def test_ihlal_uretimi_durdurur(self):
        rapor = {'kare_sayisi': 3, 'oge_sayisi': 9, 'ihlalli_kare': 1, 'ihlal_sayisi': 2,
                 'ihlaller': [{'tur': 'yazi', 'metin': 'Steam', 'yon': 'sol', 'kareler': [4, 5], 'kare_sayisi': 2,
                               'en_cok': 7.5, 'ornek': None}]}

        def kos(komut, **kw):
            pathlib.Path(komut[komut.index('--denetle') + 1]).write_text(json.dumps(rapor), encoding='utf-8')
            return subprocess.CompletedProcess(komut, 3, '', '')

        with tempfile.TemporaryDirectory() as t, patch.object(v, '_calistir', kos), patch.object(v, '_node', lambda: 'node'):
            with self.assertRaises(v.UretimHatasi) as c:
                v.guvenli_denetle(pathlib.Path(t), cikti=lambda m: None)
            self.assertIn("2 ihlal ('Steam' sol 2 kare, en çok 7.5 px)", str(c.exception))
            rapor.update(ihlal_sayisi=0, ihlalli_kare=0, ihlaller=[])
            mesaj = []
            v.guvenli_denetle(pathlib.Path(t), cikti=mesaj.append)
        self.assertEqual(mesaj, ['güvenli alan denetimi: 3 ölçüm, 9 öğe, ihlal yok'])


if __name__ == '__main__':
    unittest.main()
