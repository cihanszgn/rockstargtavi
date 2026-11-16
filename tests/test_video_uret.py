import copy
import json
import os
import pathlib
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
        'okunus': {'PlayStation': 'Pleysteyşın', "ctrl-agame.com'da": "kontrol ey geym nokta kom'da"},
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
             'anlatim': "Bütün yama notları ve ayrıntılar ctrl-agame.com'da.",
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
    def test_ornek_senaryo_gecer_ve_okunus_seslendirmeye_gider(self):
        hazir = v.senaryo_hazirla(senaryo(), haber(), 'tr')
        self.assertEqual([s['sablon'] for s in hazir['sahneler']],
                         ['baslik', 'kaynak', 'yama_fark', 'platform', 'tarih', 'kapanis'])
        self.assertIn('Pleysteyşın', hazir['tts'])
        self.assertIn("kontrol ey geym nokta kom'da", hazir['tts'])
        self.assertNotIn('PlayStation', hazir['tts'])
        self.assertTrue(v.EN_KISA <= hazir['tahmini_sure'] <= v.EN_UZUN)
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

    def test_depodaki_manifest_sozlesmeye_uyar(self):
        if not v.MANIFEST.exists():
            self.skipTest('data/videolar.json yok')
        m = v.json_oku(v.MANIFEST)
        self.assertEqual(set(m), {'surum', 'taban', 'videolar'})
        self.assertEqual((m['surum'], m['taban']), (1, 'https://medya.ctrl-agame.com/v/'))
        alanlar = {'anahtar', 'sure', 'mp4_1080', 'mp4_720', 'mp4_540', 'kapak', 'vtt', 'uretildi', 'youtube', 'instagram'}
        for kimlik, diller in m['videolar'].items():
            for dil, g in diller.items():
                with self.subTest(f'{kimlik}-{dil}'):
                    self.assertEqual(set(g), alanlar)
                    k = g['anahtar']
                    self.assertEqual(g['mp4_1080'], f'{kimlik}-{dil}-{k}-1080.mp4')
                    self.assertEqual(g['vtt'], f'{kimlik}-{dil}-{k}.vtt')
                    self.assertEqual(g['kapak'], f'{kimlik}-{dil}-{k}-kapak.jpg')

    def test_video_ayari_varsayilanlari(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(v.video_ayari(pathlib.Path(t) / 'yok.json'),
                             {'ses': 'azure', 'konusmaci': '', 'yukleme_hedefi': '', 'gunluk_en_fazla': 2})


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
        self.k = v.anahtar(haber(), 'tr', senaryo(), v.seslendirici('edge', '', 'tr').ayar())

    def test_hazir_video_yeniden_uretilmez(self):
        with tempfile.TemporaryDirectory() as t, Ortam(t, manifest={'surum': 1, 'taban': v.TABAN,
                                                                     'videolar': {KIMLIK: {'tr': kayit(self.k)}}}), \
                patch.object(v, '_calistir', durdur):
            mesaj = []
            sonuc = v.uret(KIMLIK, 'tr', yukle=True, cikti=mesaj.append)
        self.assertEqual(sonuc['anahtar'], self.k)
        self.assertIn(f'atlandı: {KIMLIK} tr zaten hazır (anahtar {self.k})', mesaj)
        self.assertIn('yükleme atlandı: sosyal/ayarlar.json içinde video.yukleme_hedefi boş', mesaj)

    def test_degisen_anahtar_yeniden_uretir(self):
        with tempfile.TemporaryDirectory() as t, Ortam(t, manifest={'surum': 1, 'taban': v.TABAN,
                                                                     'videolar': {KIMLIK: {'tr': kayit('eskieskieski')}}}), \
                patch.object(v, '_calistir', durdur), patch.object(v.shutil, 'which', return_value='uv'):
            with self.assertRaises(Durdu) as c:
                v.uret(KIMLIK, 'tr', cikti=lambda m: None)
            komut = c.exception.args[0]
            girdi = json.loads((pathlib.Path(t) / 'tmp' / 'ses').glob('*/tts-girdi.json').__next__().read_text('utf-8'))
        self.assertIn('edge-tts==7.3.1', komut)
        self.assertIn('Pleysteyşın', girdi['metin'])

    def test_bekleyenler_ve_gunluk_sinir(self):
        bugun = date(2026, 11, 16)
        with tempfile.TemporaryDirectory() as t, Ortam(t, manifest={'surum': 1, 'taban': v.TABAN, 'videolar': {}}):
            self.assertEqual(v.bekleyenler('tr', bugun=bugun, cikti=lambda m: None), [KIMLIK])
            self.assertEqual(v.bekleyenler('tr', bugun=date(2026, 11, 25), cikti=lambda m: None), [])
        dolu = {'surum': 1, 'taban': v.TABAN, 'videolar': {'baska-haber': {'tr': kayit('aaaaaaaaaaaa', '2026-11-16')}}}
        with tempfile.TemporaryDirectory() as t, Ortam(t, ayar={'ses': 'edge', 'gunluk_en_fazla': 1}, manifest=dolu):
            self.assertEqual(v.bekleyenler('tr', gunluk=True, bugun=bugun, cikti=lambda m: None), [])
            self.assertEqual(v.bekleyenler('tr', gunluk=False, bugun=bugun, cikti=lambda m: None), [KIMLIK])
        hazir = {'surum': 1, 'taban': v.TABAN, 'videolar': {KIMLIK: {'tr': kayit(self.k)}}}
        with tempfile.TemporaryDirectory() as t, Ortam(t, manifest=hazir):
            self.assertEqual(v.bekleyenler('tr', bugun=bugun, cikti=lambda m: None), [])

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


class SahteSdk:
    """azure-cognitiveservices-speech arayüzünün yardımcıda kullanılan kısmı."""

    SpeechSynthesisOutputFormat = SimpleNamespace(Audio24Khz96KBitRateMonoMp3='mp3-24k')
    ResultReason = SimpleNamespace(SynthesizingAudioCompleted='tamam')

    def __init__(self, sonuc='tamam'):
        sdk = self
        self.kayit = {}
        self.audio = SimpleNamespace(AudioOutputConfig=lambda filename: SimpleNamespace(filename=filename))

        class SpeechConfig:
            def __init__(self, subscription, region):
                sdk.kayit['abonelik'] = (subscription, region)

            def set_speech_synthesis_output_format(self, bicim):
                sdk.kayit['bicim'] = bicim

        class SpeechSynthesizer:
            def __init__(self, speech_config, audio_config):
                sdk.kayit['dosya'] = audio_config.filename
                self._dinleyiciler = []
                self.synthesis_word_boundary = SimpleNamespace(connect=self._dinleyiciler.append)

            def speak_ssml_async(self, ssml):
                sdk.kayit['ssml'] = ssml
                for olay in (SimpleNamespace(text='Merhaba', audio_offset=1_000_000, duration=timedelta(milliseconds=400),
                                             boundary_type='SpeechSynthesisBoundaryType.Word'),
                             SimpleNamespace(text=',', audio_offset=5_000_000, duration=timedelta(0),
                                             boundary_type='SpeechSynthesisBoundaryType.Punctuation')):
                    for d in self._dinleyiciler:
                        d(olay)
                return SimpleNamespace(get=lambda: SimpleNamespace(
                    reason=sonuc, cancellation_details=SimpleNamespace(error_details='kota bitti')))

        self.SpeechConfig, self.SpeechSynthesizer = SpeechConfig, SpeechSynthesizer


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

    def test_yardimci_bilinmeyen_saglayiciyi_reddeder(self):
        with self.assertRaises(SystemExit):
            yardimci.main(['python', 'a.json', 'b.mp3', 'c.json'])


def makale(oid='oyun-yama-1'):
    return {'id': oid, 'tarih': '2026-11-15', 'oyun': 'Oyun', 'tur': 'guncelleme',
            'kaynaklar': [{'url': 'https://blog.playstation.com/2026/11/15/game-patch/', 'ad': 'PlayStation Blog'}],
            'diller': {d: {'baslik': 'Yeni oyun yaması', 'ozet': 'Yama yayımlandı.',
                           'metin': ' '.join(['Bilgi'] * 60)} for d in haber_oto.DILLER},
            'otomasyon': {'konu': oid, 'resmi_url': 'https://blog.playstation.com/2026/11/15/game-patch/',
                          'teyit_zamani': '2026-11-15T08:00:00+00:00',
                          'oyuncuya_fayda': 'Kaydetme hatası giderildi; oyuncu yamasını kurabilir.'}}


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


if __name__ == '__main__':
    unittest.main()
