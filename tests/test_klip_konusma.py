"""Ağ, model indirme ve GPU gerektirmeyen konuşma katmanı sözleşmeleri."""
import json
import pathlib
import sys
import tempfile
import unittest
import subprocess
from unittest.mock import Mock, patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tools'))
import klip_konusma as k
import yayin_klip as y


CFG = {**y.AYAR_VARSAYILAN, 'konusma': True, 'konusma_cihaz': 'cpu', 'konusma_tam_tarama': False}
VOD = {'anahtar': 'kick:test', 't0_epoch': 100, 'sure_sn': 900, 'kaynak': 'https://a/master.m3u8'}


def sentences():
    return [{'bas': float(i), 'bit': float(i+9), 'metin': f'{i} numaralı tam cümle.',
             'tam': True, 'bas_tam': True} for i in range(0, 900, 10)]


def aday(peak=340, score=80):
    return {'zirve_sn': peak, 'puan': score, 'klip_baslangic_sn': peak-20,
            'klip_bitis_sn': peak+22, 'zirve_dilimleri': [peak], 'no': 1}


def answer(**extra):
    return {'puan': 7, 'gerekce': 'Beklenmedik cevap kendi başına anlaşılır.', 'anlasilir': True,
            'bas_cumle': 1, 'son_cumle': 4, 'baslik': 'Yanlış kapıyı açınca şaşırdı.', **extra}


class Puan(unittest.TestCase):
    def test_agirlikli_olcek(self):
        self.assertAlmostEqual(k.puan_birlestir(80, 6, CFG), 67)

    def test_yargi_yok_ayni_puan(self):
        self.assertEqual(k.puan_birlestir(80, None, CFG), 80)

    def test_agirliklar_normalize(self):
        self.assertEqual(k.puan_birlestir(80, 6, {**CFG, 'konusma_agirlik_sohbet': 2,
                                                'konusma_agirlik_icerik': 2}), 70)

    def test_gecersiz_agirlik(self):
        with self.assertRaises(ValueError):
            k.puan_birlestir(80, 6, {**CFG, 'konusma_agirlik_icerik': -1})


class Sinir(unittest.TestCase):
    def test_olayin_tum_cumleleri_korunur(self):
        a, b = k.sinira_oturt(sentences(), 321, 342)
        self.assertEqual((a, b), (319.65, 349.35))

    def test_18_saniyelik_tam_cumle_kabul_edilir(self):
        self.assertEqual(k.sinira_oturt([{'bas': 0, 'bit': 18}], 0, 18, maximum=18), (0, 18))

    def test_17_saniyelik_tek_cumle_reddedilir(self):
        self.assertIsNone(k.sinira_oturt([{'bas': 0, 'bit': 17}], 0, 17))

    def test_20_saniyelik_olaya_komsu_cumleler_eklenmez(self):
        rows = [{'bas': 20, 'bit': 30}, {'bas': 31, 'bit': 51}, {'bas': 52, 'bit': 64}]
        self.assertEqual(k.sinira_oturt(rows, 31, 51), (30.65, 51.35))

    def test_uzun_olay_kesilmez(self):
        self.assertIsNone(k.sinira_oturt(sentences(), 310, 390))

    def test_tam_cumle_yoksa_reddet(self):
        self.assertIsNone(k.sinira_oturt([{'bas': 0, 'bit': 40, 'tam': False}], 0, 39))

    def test_baslangici_yarim_reddet(self):
        self.assertIsNone(k.sinira_oturt([{'bas': 0, 'bit': 40, 'bas_tam': False}], 0, 39))

    def test_59_saniye_sert_sinir(self):
        a, b = k.sinira_oturt([{'bas': 20, 'bit': 79}], 20, 79, maximum=80)
        self.assertEqual(b-a, 59)

    def test_kelime_segmenti_cumle_degildir(self):
        rows = k.cumleler([{'bas': 0, 'bit': 1, 'metin': ' Merhaba'},
                          {'bas': 1, 'bit': 2, 'metin': ' dünya.'},
                          {'bas': 2, 'bit': 3, 'metin': ' Nasılsın?'}])
        self.assertEqual([r['metin'] for r in rows], ['Merhaba dünya.', 'Nasılsın?'])
        self.assertTrue(all(r['bas_tam'] and r['tam'] for r in rows))


class Birlestirme(unittest.TestCase):
    def test_ayni_an_tek_olur_sohbet_puani_korunur(self):
        a = {**aday(), 'sohbet_puani': 80, 'kaynaklar': ['sohbet']}
        b = {**aday(345), 'konusma_puani': 8, 'sohbet_puani': 0, 'kaynaklar': ['tarama']}
        r = k.aday_birlestir([a, b])
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]['sohbet_puani'], 80)
        self.assertEqual(r[0]['kaynaklar'], ['sohbet', 'tarama'])

    def test_ayri_anlar_birlesmez(self):
        self.assertEqual(len(k.aday_birlestir([aday(340), aday(400)])), 2)

    def test_engelli_ve_son_kota(self):
        r = k.son_secim([aday(340), aday(500)], {**CFG, 'azami_klip': 1}, [(310, 330)])
        self.assertEqual([a['zirve_sn'] for a in r], [500])


class ModelYaniti(unittest.TestCase):
    def test_haber_tasimasi_kullanilir_ama_yargi_arac_ve_kasaya_erisemez(self):
        import haber_hatti as h
        config={'librarian':{'command':'private'},'eleme':[],
                'yazar':[{'ad':'sonnet','tur':'claude','komut':['claude','-p','--model','sonnet',
                    '--tools','WebFetch,WebSearch','--allowedTools','mcp__cio_librarian__library_search']} ]}
        with patch.object(h,'model_ayari',return_value=config):
            model=k.ModelYolu({**CFG,'konusma_yargi_model':'sonnet','konusma_bulut':True})
        self.assertNotIn('librarian',model.hat.config)
        self.assertEqual(model.specs[0]['komut'][-2:],['--tools',''])
        self.assertNotIn('--allowedTools',model.specs[0]['komut'])
        self.assertIn('librarian',config)
        self.assertIn('WebFetch,WebSearch',config['yazar'][0]['komut'])

    def test_bozuk_json_bir_kez_yeniden(self):
        model = Mock(side_effect=['bozuk', json.dumps(answer())])
        self.assertEqual(k.yargi_al(sentences()[:6], model)['puan'], 7)
        self.assertEqual(model.call_count, 2)

    def test_iki_bozuk_yargi_puansiz(self):
        model = Mock(return_value='bozuk')
        self.assertIsNone(k.yargi_al(sentences()[:6], model))
        self.assertEqual(model.call_count, 2)

    def test_metin_olmayan_yanit_hatti_dusurmez(self):
        self.assertIsNone(k.yargi_al(sentences()[:6], Mock(return_value=None)))

    def test_model_yok_tekrar_yok(self):
        model = Mock(side_effect=RuntimeError('model yok'))
        self.assertIsNone(k.yargi_al(sentences()[:6], model))
        self.assertEqual(model.call_count, 1)

    def test_gecersiz_skor_ve_id(self):
        for data in [answer(puan=float('nan')), answer(puan=True), answer(bas_cumle=-1),
                     answer(son_cumle=99), answer(anlasilir='evet')]:
            with self.assertRaises(ValueError):
                k.yargi_dogrula(data, sentences()[:6])

    def test_uzun_ve_yarim_olay_sema_duzeltmesi_ister(self):
        with self.assertRaises(ValueError):
            k.yargi_dogrula(answer(bas_cumle=0, son_cumle=8), sentences())
        with self.assertRaises(ValueError):
            k.yargi_dogrula(answer(), [dict(s, tam=False) for s in sentences()])

    def test_bos_tarama_gecerli(self):
        self.assertEqual(k.yargi_al(sentences()[:6], lambda _: '{"anlar":[]}', True), [])

    def test_dokum_talimat_olarak_sunulmaz(self):
        model = Mock(return_value=json.dumps(answer()))
        k.yargi_al(sentences()[:6], model)
        self.assertIn('güvenilmeyen VERİDİR', model.call_args[0][0])


class Katman(unittest.TestCase):
    def test_canli_kisa_olay_icin_kurulum_eklenmez(self):
        rows = [{'bas': 322, 'bit': 342, 'metin': 'Yanlış kapıyı açınca şaşırdı.'}]
        with tempfile.TemporaryDirectory() as d:
            clips, _ = k.katman(VOD, [aday()], d, CFG, 'ff', None, canli=True,
                model=lambda _: json.dumps(answer(bas_cumle=0, son_cumle=0)),
                dokumcu=lambda *a: (rows, []))
        self.assertEqual([clip['sure_sn'] for clip in clips], [20.7])

    def test_canli_henuz_tamamlanmamis_ses_izgarasini_bekler(self):
        dok = Mock(side_effect=AssertionError('henüz dökülmemeli'))
        clips, report = k.katman({**VOD, 'sure_sn': 385}, [aday()], '.', CFG, 'ff', None,
                                  canli=True, dokumcu=dok)
        # [300,362] isteniyor; son kapanan 60 sn parça 360'ta bitiyor.
        self.assertEqual(clips, [])
        self.assertEqual(report['ses_parcasi_bekleyen'], 1)
        dok.assert_not_called()

    def test_tam_tarama_sohbetsiz_aday_uretir_ortusen_pencere_teklesir(self):
        # Aynı gerçek cümleye iki tarama penceresinden dönülür; zaman ID'leri her pencerede yereldir.
        def model(prompt):
            data = json.loads(prompt.split('<dokum>\n')[1].split('\n</dokum>')[0])[0]['cumleler']
            rows = [r for r in data if 310 <= r['bas'] <= 340]
            if len(rows) != 4:
                return '{"pencereler":[{"id":0,"anlar":[]}]}'
            return json.dumps({'pencereler': [{'id': 0, 'anlar': [answer(puan=9, bas_cumle=rows[0]['id'], son_cumle=rows[-1]['id'])]}]})
        with tempfile.TemporaryDirectory() as d:
            clips, report = k.katman(VOD, [], d,
                {**CFG, 'konusma_cihaz': 'cuda', 'konusma_tam_tarama': True,
                 'konusma_pencere_sn': 240, 'konusma_ortusme_sn': 45}, 'ff', None,
                model=model, dokumcu=lambda *a: (sentences(), []))
        self.assertTrue(report['tam_tarama'])
        self.assertEqual(len(clips), 1)
        self.assertEqual(clips[0]['kaynaklar'], ['tarama'])
        self.assertEqual(clips[0]['konusma_puani'], 9)

    def test_model_yokken_sohbete_geri_duser(self):
        with tempfile.TemporaryDirectory() as d:
            clips, report = k.katman(VOD, [aday()], d, CFG, 'ff', None,
                model=Mock(side_effect=RuntimeError('yok')), dokumcu=lambda *a: (sentences(), []))
        self.assertEqual(clips[0]['puan'], 80)
        self.assertEqual(report['durum'], 'konuşma katmanı kapalı')

    def test_icerik_vetosu_yuksek_sohbeti_eler(self):
        with tempfile.TemporaryDirectory() as d:
            clips, report = k.katman(VOD, [aday(score=100)], d, CFG, 'ff', None,
                model=lambda _: json.dumps(answer(puan=2, anlasilir=False)),
                dokumcu=lambda *a: (sentences(), []))
        self.assertEqual(clips, [])
        self.assertEqual(report['durum'], 'açık')

    def test_kapaliyken_ag_ve_asr_cagrilmaz(self):
        dok = Mock(side_effect=AssertionError('çağrılmamalı'))
        k.katman(VOD, [aday()], '.', {**CFG, 'konusma': False}, 'ff', None, dokumcu=dok)
        dok.assert_not_called()

    def test_cpu_ve_canli_tam_yayini_dokmez(self):
        for live, device in [(False, 'cpu'), (True, 'cuda')]:
            calls = []
            def dok(v, ranges, *args):
                calls.extend(ranges)
                return sentences(), []
            with tempfile.TemporaryDirectory() as d:
                clips, report = k.katman(VOD, [aday()], d,
                    {**CFG, 'konusma_cihaz': device, 'konusma_tam_tarama': True}, 'ff', None,
                    canli=live, model=lambda _: json.dumps(answer()), dokumcu=dok)
            self.assertEqual(calls, [(300, 362)])
            self.assertFalse(report['tam_tarama'])

    def test_model_basligi_ve_dokum_pakette(self):
        with tempfile.TemporaryDirectory() as d:
            clips, report = k.katman(VOD, [aday()], d, CFG, 'ff', None,
                model=lambda _: json.dumps(answer()), dokumcu=lambda *a: (sentences(), []))
        self.assertTrue(clips[0]['dokum_metni'])
        self.assertEqual(y.baslik_uret({}, clips[0]), answer()['baslik'])


class TopluYargi(unittest.TestCase):
    def test_iki_saat_en_cok_15_cagri(self):
        rows=[{'bas':i,'bit':i+9,'metin':'Tam bir cümle.','tam':True,'bas_tam':True} for i in range(0,7200,10)]
        calls=[]
        def model(prompt):
            calls.append(prompt)
            data=json.loads(prompt.split('<dokum>\n')[1].split('\n</dokum>')[0])
            return json.dumps({'pencereler':[{'id':r['id'],'anlar':[]} for r in data]})
        with tempfile.TemporaryDirectory() as d:
            clips,report=k.katman({**VOD,'sure_sn':7200},[aday(300+i*100) for i in range(15)],d,
                {**CFG,**k.AYAR,'konusma':True,'konusma_cihaz':'cuda','konusma_tam_tarama':True},'ff',None,
                model=model,dokumcu=lambda *a:(rows,[]))
        self.assertEqual(len(calls),8)  # 1 toplu aday + 7 tam tarama
        self.assertLessEqual(report['cagrilar'],15)
        self.assertEqual(clips,[])  # geçerli boş yargı adayları veto eder

    def test_yeniden_denemeler_butceye_dahil(self):
        model=Mock(return_value='bozuk')
        limited=k.ButceliModel(model,3)
        with tempfile.TemporaryDirectory() as d:
            for _ in range(4):k.toplu_yargi([sentences()[:6]],limited,pathlib.Path(d),{**CFG,'konusma_yargi_onbelleksiz':True})
        self.assertEqual(model.call_count,3)

    def test_pencere_id_tekrari_reddedilir(self):
        model=Mock(return_value=json.dumps({'pencereler':[{'id':0,'anlar':[]},{'id':0,'anlar':[]}]}))
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(k.toplu_yargi([sentences()[:6]]*2,model,pathlib.Path(d),CFG),[None,None])
        self.assertEqual(model.call_count,2)

    def test_tek_pencerenin_gecersiz_yargisi_digerlerini_atmaz(self):
        sent=sentences()[:6]
        iyi={'puan':7,'gerekce':'komik','anlasilir':True,'bas_cumle':0,'son_cumle':2,'baslik':'Olay'}
        kotu={**iyi,'puan':99}
        model=Mock(return_value=json.dumps({'pencereler':[{'id':0,'anlar':[iyi]},{'id':1,'anlar':[kotu]}]}))
        with tempfile.TemporaryDirectory() as d:
            sonuc=k.toplu_yargi([sent,sent],model,pathlib.Path(d),CFG)
        self.assertEqual(model.call_count,2)  # geçersiz pencere için bir yeniden deneme
        self.assertEqual(sonuc[0][0]['puan'],7)
        self.assertIsNone(sonuc[1])

    def test_yargisiz_aday_tarama_kapsiyorsa_secime_girmez(self):
        rows=[{'bas':i,'bit':i+9,'metin':'Tam bir cümle.','tam':True,'bas_tam':True} for i in range(0,400,10)]
        def model(prompt):
            data=json.loads(prompt.split('<dokum>\n')[1].split('\n</dokum>')[0])
            if 'BAŞTAN SONA' in prompt:
                return json.dumps({'pencereler':[{'id':r['id'],'anlar':[]} for r in data]})
            return 'bozuk'
        with tempfile.TemporaryDirectory() as d:
            clips,report=k.katman({**VOD,'sure_sn':400},[aday(300),aday(350)],d,
                {**CFG,**k.AYAR,'konusma':True,'konusma_cihaz':'cuda','konusma_tam_tarama':True},'ff',None,
                model=model,dokumcu=lambda *a:(rows,[]))
        self.assertEqual(clips,[])
        self.assertTrue(any('tarama penceresi kapsıyor' in x['sonuc'] for x in report['kararlar']))

    def test_kota_sessizce_yutulmaz(self):
        with self.assertRaises(k.ModelKotasi):
            k.yargi_al(sentences(),Mock(side_effect=k.ModelKotasi('quota')))

    def test_toplu_onbellek_atlanabilir(self):
        model=Mock(return_value='{"pencereler":[{"id":0,"anlar":[]}]}')
        with tempfile.TemporaryDirectory() as d:
            for _ in range(2):k.toplu_yargi([sentences()],model,pathlib.Path(d),CFG)
            self.assertEqual(model.call_count,1)
            k.toplu_yargi([sentences()],model,pathlib.Path(d),{**CFG,'konusma_yargi_onbelleksiz':True})
            self.assertEqual(model.call_count,2)


class Onbellek(unittest.TestCase):
    def test_worker_bitmis_ust_surec_kapanmissa_asr_tekrarlanmaz(self):
        calls=[]
        raw={'segmentler':[],'olcum':{},'model':'small','cihaz':'cpu'}
        original=k.json_yaz
        def transcribe(audio,model,device,path,**kwargs):
            calls.append(audio);original(path,raw);return raw
        def interrupted(path,value):
            if pathlib.Path(path).name=='00000.json':
                raise OSError('üst süreç kesildi')
            return original(path,value)
        with tempfile.TemporaryDirectory() as d:
            def run():
                return k.dokum_al(VOD,[(0,30)],d,CFG,'ff',
                    lambda _: '#EXT-X-STREAM-INF:BANDWIDTH=230000\na.m3u8',
                    calistir=transcribe,indir=lambda *a:{'sure_sn':0})
            with patch.object(k,'json_yaz',side_effect=interrupted):
                with self.assertRaises(OSError):run()
            run()
        self.assertEqual(len(calls),1)

    def test_ses_korelasyonu_bilinen_kaymayi_bulur(self):
        import numpy as np
        import wave
        rng = np.random.default_rng(17)
        reference = rng.integers(-10000,10000,20*16000,dtype=np.int16)
        clip = reference[int(6.2*16000):int(14.2*16000)]
        with tempfile.TemporaryDirectory() as d:
            files = []
            for name, data in [('ref',reference),('clip',clip)]:
                p = pathlib.Path(d)/(name+'.wav')
                with wave.open(str(p),'wb') as f:
                    f.setnchannels(1); f.setsampwidth(2); f.setframerate(16000); f.writeframes(data.tobytes())
                files.append(p)
            result = k.dalga_hizasi(*files,5)
        self.assertAlmostEqual(result['ofset_sn'],1.2,places=3)
        self.assertGreater(result['korelasyon'],.99)

    def test_hls_kesinti_sonrasi_duvar_saati_ile_pencere(self):
        source = '#EXTM3U\n#EXT-X-PROGRAM-DATE-TIME:2026-11-12T00:00:00Z\n#EXTINF:10,\n1.ts\n'
        source += '#EXT-X-DISCONTINUITY\n#EXT-X-PROGRAM-DATE-TIME:2026-11-12T00:01:00Z\n#EXTINF:10,\n2.ts\n'
        rows = k.hls_bolumleri('https://a/x.m3u8', source)
        self.assertEqual([(x['bas'], x['bit']) for x in rows], [(0, 10), (60, 70)])
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / 'p.m3u8'
            self.assertEqual(k.hls_pencere(rows, 63, 68, p), 3)
            self.assertIn('https://a/2.ts', p.read_text())
            self.assertNotIn('https://a/1.ts', p.read_text())
            with self.assertRaises(RuntimeError):
                k.hls_pencere(rows, 5, 65, p)

    def test_gpu_hatasi_kucuk_model_sonra_cpuya_duser(self):
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / 'worker.json'
            def run(args, **kwargs):
                if args[-2] == 'cpu':
                    k.json_yaz(path, {'model': args[-3], 'cihaz': 'cpu'})
                    return subprocess.CompletedProcess(args, 0, b'', b'')
                return subprocess.CompletedProcess(args, 1, b'', b'CUDA out of memory')
            with patch.object(k, 'ollama_bosalt'), patch.object(k.subprocess, 'run', side_effect=run) as call:
                result = k.dok_calistir('a.wav', 'large-v3-turbo', 'cuda', path)
        self.assertEqual(result['cihaz'], 'cpu')
        self.assertEqual(result['model'], 'small')
        self.assertEqual(len(result['geri_dusme']), 2)
        self.assertEqual(call.call_count, 3)

    def test_tamamlanan_parca_tekrar_dokulmez(self):
        calls = []
        def dok(*args, **kwargs):
            calls.append(args[0])
            return {'segmentler': [{'kelimeler': [{'bas': 1, 'bit': 2, 'metin': ' Selam.'}]}],
                    'olcum': {'dokum_sn': 1}, 'model': 'small', 'cihaz': 'cpu'}
        with tempfile.TemporaryDirectory() as d:
            for _ in range(2):
                k.dokum_al(VOD, [(0, 30)], d, CFG, 'ff', lambda _: '#EXT-X-STREAM-INF:BANDWIDTH=230000\na.m3u8',
                           calistir=dok, indir=lambda *a: {'sure_sn': 1})
        self.assertEqual(len(calls), 1)

    def test_yarim_is_sonraki_parcadan_surer(self):
        calls = []
        def dok(*args, **kwargs):
            calls.append(args[0])
            if len(calls) == 2:
                raise RuntimeError('kesinti')
            return {'segmentler': [], 'olcum': {}, 'model': 'small', 'cihaz': 'cpu'}
        with tempfile.TemporaryDirectory() as d:
            run = lambda: k.dokum_al(VOD, [(0, 600)], d, CFG, 'ff',
                lambda _: '#EXT-X-STREAM-INF:BANDWIDTH=230000\na.m3u8', calistir=dok,
                indir=lambda *a: {'sure_sn': 1})
            with self.assertRaises(RuntimeError):
                run()
            run()
        self.assertEqual(len(calls), 3)  # ilk parça yeniden dökülmedi

    def test_yargi_onbellekten_okunur(self):
        model = Mock(return_value=json.dumps(answer()))
        with tempfile.TemporaryDirectory() as d:
            for _ in range(2):
                k.yargi_onbellek(sentences()[:6], model, pathlib.Path(d), False, CFG)
        self.assertEqual(model.call_count, 1)

    def test_160p_goreli_uri(self):
        url, bw = k.ucuz_hls('https://a/b/master.m3u8', lambda _: (
            '#EXT-X-STREAM-INF:BANDWIDTH=5000000\n1080.m3u8\n'
            '#EXT-X-STREAM-INF:BANDWIDTH=230000\n../160/index.m3u8'))
        self.assertEqual((url, bw), ('https://a/160/index.m3u8', 230000))
class KisaAciklamaDogrulamaTesti(unittest.TestCase):
    def test_temiz_cumle_ilk_harf_buyur_nokta_atilir(self):
        self.assertEqual(k.kisa_aciklama_dogrula('Ferit saçlarını yayında boyatıyor.'), 'Ferit saçlarını yayında boyatıyor')
        self.assertEqual(k.kisa_aciklama_dogrula('  "ilk gün sahte canlıyı fark ediyor"  '), 'İlk gün sahte canlıyı fark ediyor')

    def test_uzun_kisaltilmaz_none_olur(self):
        uzun = 'Ferit yayında saçlarını boyatırken bir anda hepsini döküyor'
        self.assertGreater(len(uzun), k.ACIKLAMA_AZAMI)
        self.assertIsNone(k.kisa_aciklama_dogrula(uzun))
        self.assertEqual(len(k.kisa_aciklama_dogrula('a' * 20 + ' ' + 'b' * 24)), 45)   # tam sınır geçer
        self.assertIsNone(k.kisa_aciklama_dogrula('a' * 20 + ' ' + 'b' * 25))             # 46 -> None

    def test_bos_null_ve_tur_hatasi(self):
        for v in (None, '', '   ', '...', 12, ['x y'], {}, 'tek'):
            self.assertIsNone(k.kisa_aciklama_dogrula(v), v)

    def test_yasak_kelime_none(self):
        for v in ('Ferit amk diyerek kızıyor', 'Eray siktir çekiyor', 'Kemalcan götünü kaldırıyor'):
            self.assertIsNone(k.kisa_aciklama_dogrula(v), v)
        self.assertEqual(k.kisa_aciklama_dogrula('Eray tavuğu götürüyor'), 'Eray tavuğu götürüyor')   # tam kelime kuralı
        self.assertIsNone(k.kisa_aciklama_dogrula('Eray tavuğu çıldırıyor', {'aciklama_yasak_kelimeler': ['çıldır*']}))

    def test_tik_tuzagi_emoji_etiket_buyuk_harf_yayinci_basi(self):
        for v in ('Ferit inanılmaz bir şey yapıyor', 'Ferit saç boyatıyor #klip', 'Ferit saç boyatıyor 😂',
                  'Ferit saç boyatıyor!', 'FERİT SAÇ BOYATIYOR', 'Yayıncı saç boyatıyor', 'Ferit yoruma yaz diyor'):
            self.assertIsNone(k.kisa_aciklama_dogrula(v), v)


class YargiSemasiAciklamaTesti(unittest.TestCase):
    def deger(self, **ek):
        return {'puan': 7, 'gerekce': 'g', 'anlasilir': True, 'bas_cumle': 0, 'son_cumle': 3, 'baslik': 'b', **ek}

    def test_alan_dogrulanir_ve_pakete_gider(self):
        s = k.yargi_dogrula(self.deger(kisa_aciklama='Ferit saçlarını yayında boyatıyor'), sentences())
        self.assertEqual(s['kisa_aciklama'], 'Ferit saçlarını yayında boyatıyor')

    def test_gecersiz_alan_none_ama_yargi_kabul(self):
        for v in ('Ferit saçını yayında boyatırken hepsini birden döküyor', 'Ferit amk diyor', None, ''):
            s = k.yargi_dogrula(self.deger(kisa_aciklama=v), sentences())
            self.assertIsNone(s['kisa_aciklama'], v)

    def test_alan_yoksa_eski_yanit_aynen_gecerli(self):
        s = k.yargi_dogrula(self.deger(), sentences())
        self.assertNotIn('kisa_aciklama', s)

    def test_yarginin_isteminde_ad_ve_ek_cagri_yok(self):
        cagri = []

        def model(prompt):
            cagri.append(prompt)
            return json.dumps({'puan': 7, 'gerekce': 'g', 'anlasilir': True, 'bas_cumle': 0, 'son_cumle': 3,
                               'baslik': 'b', 'kisa_aciklama': 'Ferit saçlarını yayında boyatıyor'})
        cfg = {**CFG, 'kisa_ad': 'Ferit'}
        sonuc = k.yargi_al(sentences(), model, False, cfg)
        self.assertEqual(len(cagri), 1)                 # kisa_aciklama aynı çağrının içinde: ek model çağrısı yok
        self.assertIn('Ferit', cagri[0])
        self.assertEqual(sonuc['kisa_aciklama'], 'Ferit saçlarını yayında boyatıyor')

    def test_aciklamasiz_ayarda_istem_notu_yok(self):
        self.assertEqual(k.aciklama_notu({**CFG, 'klip_aciklama_yazi': False}), '')
        self.assertIn('kisa_aciklama', k.aciklama_notu({**CFG, 'kisa_ad': 'Eray'}))


class AciklamaTopluTesti(unittest.TestCase):
    KAYIT = [{'id': 'a', 'ad': 'Ferit', 'dokum': 'saçımı boyatıyorum yayında'},
             {'id': 'b', 'ad': 'Eray', 'dokum': 'patates soyuyorum'}]

    def test_tek_cagri_ve_dogrulama(self):
        model = Mock(return_value=json.dumps({'aciklamalar': [
            {'id': 'a', 'kisa_aciklama': 'Ferit saçlarını yayında boyatıyor'},
            {'id': 'b', 'kisa_aciklama': 'Eray amk diye bağırıyor'}]}))
        s = k.aciklama_toplu(self.KAYIT, model)
        self.assertEqual(model.call_count, 1)
        self.assertEqual(s['a']['aciklama'], 'Ferit saçlarını yayında boyatıyor')
        self.assertIsNone(s['b']['aciklama'])                       # yasak kelime
        self.assertEqual(s['b']['ham'], 'Eray amk diye bağırıyor')  # ham metin raporlanabilsin

    def test_null_kabul_edilir(self):
        model = Mock(return_value=json.dumps({'aciklamalar': [
            {'id': 'a', 'kisa_aciklama': None}, {'id': 'b', 'kisa_aciklama': 'Eray patates soyuyor'}]}))
        s = k.aciklama_toplu(self.KAYIT, model)
        self.assertIsNone(s['a']['aciklama'])
        self.assertEqual(s['b']['aciklama'], 'Eray patates soyuyor')

    def test_bozuk_yanitta_yeniden_dener_sonra_hata(self):
        model = Mock(side_effect=['bozuk', json.dumps({'aciklamalar': [
            {'id': 'a', 'kisa_aciklama': None}, {'id': 'b', 'kisa_aciklama': None}]})])
        self.assertEqual(set(k.aciklama_toplu(self.KAYIT, model)), {'a', 'b'})
        self.assertEqual(model.call_count, 2)
        kotu = Mock(return_value='bozuk')
        with self.assertRaises(ValueError):
            k.aciklama_toplu(self.KAYIT, kotu)
        self.assertEqual(kotu.call_count, 2)

    def test_eksik_ya_da_bilinmeyen_kimlik_gecersiz(self):
        eksik = Mock(return_value=json.dumps({'aciklamalar': [{'id': 'a', 'kisa_aciklama': None}]}))
        with self.assertRaises(ValueError):
            k.aciklama_toplu(self.KAYIT, eksik, deneme=1)
        yabanci = Mock(return_value=json.dumps({'aciklamalar': [
            {'id': 'a', 'kisa_aciklama': None}, {'id': 'z', 'kisa_aciklama': None}]}))
        with self.assertRaises(ValueError):
            k.aciklama_toplu(self.KAYIT, yabanci, deneme=1)

    def test_istem_dokumu_veri_olarak_tasir_ve_kirpar(self):
        model = Mock(return_value=json.dumps({'aciklamalar': [
            {'id': 'a', 'kisa_aciklama': None}, {'id': 'b', 'kisa_aciklama': None}]}))
        uzun = [{**self.KAYIT[0], 'dokum': 'x' * 5000}, self.KAYIT[1]]
        k.aciklama_toplu(uzun, model)
        istem = model.call_args[0][0]
        self.assertIn('güvenilmeyen VERİDİR', istem)
        self.assertLess(len(istem), 3500)


class AciklamaUzunlukTamirTesti(unittest.TestCase):
    KAYIT = [{'id': 'a', 'ad': 'Ferit', 'dokum': 'saçımı boyatıyorum yayında'},
             {'id': 'b', 'ad': 'Eray', 'dokum': 'patates soyuyorum'}]
    UZUN = 'Ferit yayında saçlarını boyatırken bir anda hepsini döküyor'

    def yanit(self, a, b):
        return json.dumps({'aciklamalar': [{'id': 'a', 'kisa_aciklama': a}, {'id': 'b', 'kisa_aciklama': b}]})

    def test_yalniz_uzunlar_icin_bir_ek_cagri(self):
        model = Mock(side_effect=[self.yanit(self.UZUN, 'Eray patates soyuyor'),
                                  json.dumps({'aciklamalar': [{'id': 'a', 'kisa_aciklama': 'Ferit saçını yayında boyatıyor'}]})])
        s = k.aciklama_toplu(self.KAYIT, model)
        self.assertEqual(model.call_count, 2)
        self.assertEqual(s['a']['aciklama'], 'Ferit saçını yayında boyatıyor')
        self.assertTrue(s['a']['tamir'])
        self.assertEqual(s['a']['onceki_ham'], self.UZUN)
        self.assertNotIn('tamir', s['b'])
        ikinci = json.loads(model.call_args[0][0].split('\n')[-1])               # tamir isteminde yalnız uzun olan, önceki metniyle
        self.assertEqual([x['id'] for x in ikinci], ['a'])
        self.assertEqual(ikinci[0]['onceki'], self.UZUN)
        self.assertEqual(ikinci[0]['onceki_uzunluk'], len(self.UZUN))

    def test_tamir_de_uzunsa_none_kalir_kisaltma_yok(self):
        model = Mock(side_effect=[self.yanit(self.UZUN, None),
                                  json.dumps({'aciklamalar': [{'id': 'a', 'kisa_aciklama': self.UZUN}]})])
        s = k.aciklama_toplu(self.KAYIT, model)
        self.assertEqual(model.call_count, 2)
        self.assertIsNone(s['a']['aciklama'])
        self.assertEqual(s['a']['ham'], self.UZUN)

    def test_tamir_yaniti_bozuksa_ilk_sonuc_kalir(self):
        model = Mock(side_effect=[self.yanit(self.UZUN, 'Eray patates soyuyor'), 'bozuk'])
        s = k.aciklama_toplu(self.KAYIT, model)
        self.assertEqual(model.call_count, 2)
        self.assertIsNone(s['a']['aciklama'])
        self.assertEqual(s['b']['aciklama'], 'Eray patates soyuyor')

    def test_yasak_kelime_uzunluk_sayilmaz_tamir_yok(self):
        model = Mock(return_value=self.yanit('Ferit amk diyor', 'Eray patates soyuyor'))
        s = k.aciklama_toplu(self.KAYIT, model)
        self.assertEqual(model.call_count, 1)
        self.assertIsNone(s['a']['aciklama'])

    def test_tamir_kapatilabilir(self):
        model = Mock(return_value=self.yanit(self.UZUN, None))
        k.aciklama_toplu(self.KAYIT, model, tamir=False)
        self.assertEqual(model.call_count, 1)

    def test_uzun_mu(self):
        self.assertTrue(k.uzun_mu(self.UZUN))
        self.assertFalse(k.uzun_mu('Ferit saçını yayında boyatıyor.'))
        self.assertFalse(k.uzun_mu(None))
        self.assertTrue(k.uzun_mu('a' * 20 + ' ' + 'b' * 25))
        self.assertFalse(k.uzun_mu('a' * 20 + ' ' + 'b' * 24))


if __name__ == '__main__':
    unittest.main()
