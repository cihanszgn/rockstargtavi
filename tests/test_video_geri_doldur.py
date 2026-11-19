import copy
import json
import pathlib
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

KOK = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK / 'tools'))
import video_geri_doldur as gd
import video_uret as vu


class GeriDoldurTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.kok = pathlib.Path(self.tmp.name)
        self.simdi = datetime(2026, 11, 16, 13, tzinfo=timezone.utc)
        oid = 'r6-siege-operation-vital-signal-duyuruldu-2026-11-15'
        self.h = next(x for x in gd.hh.oku(KOK / 'data/icerik.json') if x['id'] == oid)
        self.h['otomasyon']['hype'] = 8
        self.scenario = gd.hh.oku(KOK / f'video/senaryo/{oid}-tr.json')
        self.yaz('data/icerik.json', [self.h])
        self.yaz('sosyal/ayarlar.json', {'video': {'hype_esigi': 5}})
        self.yaz('video/senaryo/sema-tr.json', self.scenario)

    def yaz(self, yol, v):
        p = self.kok / yol
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(v, ensure_ascii=False), encoding='utf-8')

    def doldur(self, **kw):
        return gd.doldur(self.kok, simdi=self.simdi, cikti=lambda *_: None, **kw)

    def test_kuru_model_ve_dosya_yazma_yok(self):
        once = {p: p.read_bytes() for p in self.kok.rglob('*.json')}
        with patch.object(gd.hh, 'Hat', side_effect=AssertionError('Model çağrısı')):
            self.assertEqual(self.doldur(kuru=True), [self.h['id']])
        self.assertEqual(once, {p: p.read_bytes() for p in self.kok.rglob('*.json')})

    def test_uc_sahne_sablonu_mevcut_dogrulayicidan_gecer(self):
        ornek = gd.senaryo_ornegi(self.h, 'tr')
        vurgu = ornek['sahneler'][0]['veri']['vurgu']
        self.assertTrue(vurgu, 'kanca vurgusu boş bırakılmamalı')
        self.assertIn(vurgu[0], ornek['sahneler'][0]['veri']['baslik'])
        hazir = vu.senaryo_hazirla(ornek, self.h, 'tr')
        self.assertEqual(len(hazir['sahneler']), 3)
        self.assertTrue(20 <= hazir['tahmini_sure'] <= 80)

    def test_mevcut_dogrulayici_gecerli_senaryoyu_yazar_ve_tekrarlamaz(self):
        cagrilar = []
        def uret(prompt):
            cagrilar.append(prompt)
            return copy.deepcopy(self.scenario)
        self.assertEqual(self.doldur(uretici=uret), [self.h['id']])
        yol = self.kok / f"video/senaryo/{self.h['id']}-tr.json"
        self.assertEqual(vu.senaryo_dosyasi_denetle(yol, self.h, 'tr'), [])
        self.assertEqual(self.doldur(uretici=uret), [])
        self.assertEqual(len(cagrilar), 1)
        self.assertIn('35-65 words', cagrilar[0])
        self.assertIn('20-35 seconds', cagrilar[0])
        self.assertIn('2-second hook', cagrilar[0])
        self.assertEqual(gd.hh.oku(self.kok / 'data/icerik.json'), [self.h])

    def test_bozuk_senaryo_bir_duzeltme_sonra_kayit_yok(self):
        with patch.object(gd.hh, 'Hat', side_effect=AssertionError('İkinci model yok')):
            uret = unittest.mock.Mock(return_value={})
            with self.assertRaises(vu.SenaryoHatasi):
                self.doldur(uretici=uret)
        self.assertEqual(uret.call_count, 2)
        self.assertEqual(len(list((self.kok / 'video/senaryo').glob('*.json'))), 1)

    def test_bir_duzeltme_ile_gecerli_senaryo(self):
        uret = unittest.mock.Mock(side_effect=[{}, self.scenario])
        self.assertEqual(self.doldur(uretici=uret), [self.h['id']])
        self.assertIn('Şemayı düzelt', uret.call_args.args[0])

    def test_eski_kalici_haber_alinir_soylenti_kampanya_ve_dusuk_hype_alinmaz(self):
        veri = []
        for oid, tur, hype in [('kalici', 'guncelleme', 5), ('kampanya', 'indirim', 10),
                               ('soylenti', 'soylenti', 9), ('dusuk', 'guncelleme', 4)]:
            h = copy.deepcopy(self.h)
            h.update(id=oid, tarih='2026-11-01', tur=tur)
            h['otomasyon'] = {'hype': hype}
            # Kalıcı yama metni; mevcut örnek sezon/etkinlik içeriyor.
            h['diller'] = {'tr': {'baslik': 'Kayıt düzeltmesi', 'metin': 'Kayıtlar düzeltildi.', 'ozet': 'Yama.'}}
            h['kaynaklar'] = [{'ad': 'Studio', 'url': 'https://example.com/patch'}]
            veri.append(h)
        self.yaz('data/icerik.json', veri)
        self.assertEqual(self.doldur(kuru=True), ['kalici'])

    def test_video_bekleyenler_arsivi_yalniz_acikca_istenince_alir(self):
        h = {'id': 'eski-yama', 'tarih': '2026-11-01', 'tur': 'guncelleme', 'otomasyon': {'hype': 7},
             'diller': {'tr': {'baslik': 'Kayıt düzeltmesi', 'metin': 'Kayıt sorunu düzeltildi.', 'ozet': 'Yama.'}}}
        (self.kok / 'video/senaryo/eski-yama-tr.json').write_text('{}', encoding='utf-8')
        ayar = {'gunluk_en_fazla': 4, 'hype_esigi': 5, 'ses': 'azure', 'konusmaci': {}}
        with patch.object(vu, 'AYARLAR', self.kok / 'sosyal/ayarlar.json'), \
             patch.object(vu, 'SENARYO', self.kok / 'video/senaryo'), \
             patch.object(vu, 'haberler', return_value=[h]), \
             patch.object(vu, 'manifest_oku', return_value={'videolar': {}}), \
             patch.object(vu, 'video_ayari', return_value=ayar), \
             patch.object(vu, 'senaryo_hazirla'), patch.object(vu, 'anahtar', return_value='k'), \
             patch.object(vu, 'seslendirici'):
            self.assertEqual(vu.bekleyenler(bugun=self.simdi.date(), cikti=lambda *_: None), [])
            self.assertEqual(vu.bekleyenler(bugun=self.simdi.date(), arsiv=True, cikti=lambda *_: None), ['eski-yama'])


if __name__ == '__main__':
    unittest.main()
