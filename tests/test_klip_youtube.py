"""YouTube sözleşmeleri: ağ, hesap, ASR/model çağrısı gerektirmez."""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]/'tools'))
import klip_youtube as q
import klip_konusma as k
import yayin_klip as y

INFO = {'id': 'abcdefghijk', 'channel_id': 'UCtest', 'uploader_id': '@Örnek',
        'channel': 'Örnek', 'title': 'Bir olay', 'upload_date': '20261118',
        'duration': 1300, 'live_status': 'not_live'}
CFG = {**y.AYAR_VARSAYILAN, **q.AYAR}
SETTINGS = {'ayar': CFG, 'yayincilar': [{'ad': 'Örnek', 'platform': 'kick', 'kanal': 'test',
    'etkin': True, 'ayar': CFG, 'youtube_kanallari': [{'kanal_id': 'UCtest', 'tanitici': 'Örnek'}]}]}


class KimlikVeSüzme(unittest.TestCase):
    def test_video_adresleri(self):
        for url in ('youtube:abcdefghijk', 'https://youtu.be/abcdefghijk?t=10',
                    'https://www.youtube.com/watch?v=abcdefghijk&list=x',
                    'https://youtube.com/live/abcdefghijk'):
            self.assertEqual(q.video_id(url), 'abcdefghijk')
        for url in ('https://evil.com/watch?v=abcdefghijk', 'youtube:bad', 'kick:abc'):
            self.assertIsNone(q.video_id(url))

    def test_liste_suzme_nedenleri(self):
        for extra, reason in [({'webpage_url': 'https://youtube.com/shorts/abcdefghijk'}, 'shorts'),
            ({'availability': 'subscriber_only'}, 'uyelere_ozel_veya_ozel'),
            ({'live_status': 'post_live'}, 'canli_veya_islenmemis'),
            ({'is_live': True}, 'canli_veya_islenmemis'),
            ({'duration': 299}, 'cok_kisa'), ({'duration': None}, 'sure_bilinmiyor'),
            ({'upload_date': None}, 'tarih_bilinmiyor'), ({'upload_date': '20260101'}, 'eski')]:
            self.assertEqual(q.atlama_nedeni({**INFO, **extra}, CFG, 1795046400), reason)
        self.assertIsNone(q.atlama_nedeni(INFO, CFG, 1795046400))

    def test_yan_kanallar_kapali_kick_kalir(self):
        ayar = y.ayar_yukle()
        self.assertEqual(len(ayar['yayincilar']), 5)
        self.assertTrue(all(p['platform'] == 'kick' for p in ayar['yayincilar']))
        self.assertEqual(sum(len(q.yayin_kaydi(p)) for p in ayar['yayincilar']), 5)
        self.assertEqual(sum(not c['etkin'] for p in ayar['yayincilar'] for c in p['youtube_kanallari']), 2)

    def test_tara_tekrari_islenmisi_ve_sekmeleri(self):
        calls = []
        def get(url, **kwargs):
            calls.append(url)
            return {'entries': [INFO]} if kwargs.get('flat') else INFO
        with tempfile.TemporaryDirectory() as d:
            y.durum_isaretle(pathlib.Path(d), 'youtube:abcdefghijk', durum='islendi')
            r = q.tara(SETTINGS, d, simdi=1795046400, getir=get)
        self.assertEqual(r['yeni'], [])
        self.assertEqual(len(r['atlanan_islenmis']), 1)
        self.assertEqual(len(calls), 2)
        self.assertTrue(calls[0].endswith('/videos') and calls[1].endswith('/streams'))

    def test_tara_tarih_flatte_yoksa_tekil_bilgi(self):
        flat = {k:v for k,v in INFO.items() if k != 'upload_date'}
        get = Mock(side_effect=[{'entries': [flat]}, INFO, {'entries': []}])
        with tempfile.TemporaryDirectory() as d:
            r = q.tara(SETTINGS, d, simdi=1795046400, getir=get)
        self.assertEqual(len(r['yeni']), 1)
        self.assertEqual(get.call_count, 3)


class AltyaziVeHeatmap(unittest.TestCase):
    def test_json3_kelime_ofsetleri_ve_html(self):
        r = q.altyazi_json3({'events': [{'tStartMs': 1000, 'dDurationMs': 3000,
            'segs': [{'utf8': 'Merhaba &amp;', 'tOffsetMs': 0}, {'utf8': 'dünya', 'tOffsetMs': 1200}]}]})
        self.assertEqual((r[0]['bas'], r[0]['bit']), (1, 4))
        self.assertEqual(r[0]['metin'], 'Merhaba & dünya')
        self.assertTrue(r[0]['altyazi'])

    def test_kayan_satir_gelecek_evente_tasmaz(self):
        r = q.altyazi_json3({'events': [
            {'tStartMs': 0, 'dDurationMs': 20000, 'segs': [{'utf8': 'bir'}]},
            {'tStartMs': 4000, 'dDurationMs': 1000, 'segs': [{'utf8': 'iki'}]}]})
        self.assertEqual(r[-1]['bit'], 5)
        self.assertEqual(q.altyazi_json3({'events': []}), [])

    def test_otomatik_turkce_oncelik(self):
        http = Mock(return_value=json.dumps({'events': [{'tStartMs': 0, 'dDurationMs': 1000, 'segs': [{'utf8': 'Türkçe'}]}]}))
        r, lang = q.altyazi_al({'automatic_captions': {'tr-orig': [{'ext':'json3','url':'orig'}],
            'tr': [{'ext':'json3','url':'tr'}]}}, http)
        self.assertEqual(lang, 'tr-orig')
        http.assert_called_once_with('orig')

    def test_bos_altyazi_whisper_gerektirir(self):
        self.assertEqual(q.altyazi_al({}, Mock()), ([], None))

    def test_heatmap_yerel_tepe_ve_mesafe(self):
        points = [{'start_time': i*10, 'end_time': (i+1)*10, 'value': v}
                  for i,v in enumerate([.1,.8,.2,.9,.2])]
        self.assertEqual(q.heatmap_tepeleri(points, mesafe=10), [{'sn':15.,'deger':.8},{'sn':35.,'deger':.9}])
        self.assertEqual(q.heatmap_tepeleri(points), [{'sn':35.,'deger':.9}])
        self.assertEqual(q.heatmap_tepeleri(None), [])


class PaketVeCiftKaynak(unittest.TestCase):
    def test_normalle_ve_paket(self):
        v=q.normalle(INFO, SETTINGS)
        c={'no':1,'zirve_sn':100, 'zirve_zaman':'1:40','puan':70,'klip_baslangic_sn':80,'klip_bitis_sn':120}
        p=y.paket_json(v,c,pathlib.Path('x.mp4'),{})
        self.assertEqual(p['platform'],'youtube')
        self.assertEqual(p['vod_id'],INFO['id'])
        self.assertEqual(p['vod_zaman_damgali_url'],'https://youtu.be/abcdefghijk?t=80')
        self.assertEqual(p['yayin_basligi'],'Bir olay')
        self.assertEqual(y.klip_metinleri(v)['kaynak'],'Kaynak: youtube.com/@Örnek')
        self.assertFalse(p['yayinlandi'])

    def test_tarih_sure_baslik_yakinsa_inceleme(self):
        a={'platform':'youtube','yayinci':'Test','sure_sn':10000,'tarih':'2026-11-18','baslik':'COD 4 final beyler'}
        b={**a,'platform':'kick','sure_sn':10050,'tarih':'2026-11-17'}
        self.assertEqual(q.ayni_yayin(a,b),'muhtemel_ayni_yayin_inceleme')
        self.assertEqual(q.ayni_yayin(a,{**b,'baslik':'başka bir oyun'}),'belirsiz')
        self.assertEqual(q.ayni_yayin(a,{**b,'yayinci':'Başka'}),'farkli')

    def test_kurgulu_kayit_dokum_ile_teklenir(self):
        text='Bugün arkadaşım bir kapı açtı ve içeriden bir adam çıktı sonra ikisi de şaşırıp bir süre güldü.'
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/'cikti'/'test'/'klip-01.json'
            p.parent.mkdir(parents=True)
            p.write_text(json.dumps({'platform':'kick','yayinci':'Örnek','dokum_metni':text}),encoding='utf-8')
            v=q.normalle(INFO, SETTINGS)
            self.assertEqual(q.metin_tekrar({'dokum_metni':text},v,d),str(p))
            self.assertIsNone(q.metin_tekrar({'dokum_metni':'Merhaba dünya'},v,d))

    def test_referans_iki_ayri_ses_parcasi(self):
        item={'klip_baslangic_sn':290,'klip_bitis_sn':330}
        q.ses_referanslari(item,[{'aralik':[0,300],'youtube_ses':'a.wav','ses_bas_sn':0},
                                {'aralik':[300,600],'youtube_ses':'b.wav','ses_bas_sn':285}])
        self.assertEqual(item['konusma_ses_referansi']['dosya'],'a.wav')
        self.assertEqual(item['konusma_son_ses_referansi']['dosya'],'b.wav')


class Istemci(unittest.TestCase):
    def test_bot_engelinde_tek_geri_dusme(self):
        run=Mock(side_effect=[RuntimeError("Sign in to confirm you're not a bot"), {'id':'ok'}])
        value, client=q.istemciyle(run)
        self.assertEqual(client,'android,ios,tv')
        self.assertEqual(run.call_count,2)
        self.assertEqual(run.call_args[0][0]['extractor_args']['youtube']['player_client'],['android','ios','tv'])

    def test_normal_basari_yedek_yok(self):
        run=Mock(return_value={})
        self.assertEqual(q.istemciyle(run),({},'normal'))
        self.assertEqual(run.call_count,1)

    def test_uyelik_ve_ag_hatasi_bot_sayilmaz(self):
        for error in ('members-only', 'timed out'):
            run=Mock(side_effect=RuntimeError(error))
            with self.assertRaises(RuntimeError): q.istemciyle(run)
            self.assertEqual(run.call_count,1)

    def test_iki_istemci_de_engelliyse_hata(self):
        run=Mock(side_effect=RuntimeError('not a bot'))
        with self.assertRaises(RuntimeError):q.istemciyle(run)
        self.assertEqual(run.call_count,2)

    def test_gecici_indirme_hatasi_bir_kez_yeniden_denenir(self):
        islem=Mock(side_effect=[Exception('ffmpeg exited with code 3436169992'),'tamam'])
        with patch.object(q.time,'sleep'):
            self.assertEqual(q.dene(islem),'tamam')
        self.assertEqual(islem.call_count,2)

    def test_kalici_indirme_hatasi_runtimeerror_olur(self):
        islem=Mock(side_effect=Exception('ffmpeg exited with code 1'))
        with patch.object(q.time,'sleep'):
            with self.assertRaises(RuntimeError) as c: q.dene(islem)
        self.assertIn('ffmpeg',str(c.exception))
        self.assertEqual(islem.call_count,2)

    def test_uyelik_hatasi_yeniden_denenmez(self):
        islem=Mock(side_effect=Exception('Join this channel: members-only'))
        with self.assertRaises(RuntimeError): q.dene(islem)
        self.assertEqual(islem.call_count,1)


if __name__ == '__main__':
    unittest.main()
