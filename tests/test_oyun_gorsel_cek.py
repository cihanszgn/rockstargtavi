import json
import pathlib
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tools'))
import oyun_gorsel_cek as og


class AdEslesmesi(unittest.TestCase):
    def test_normalize_isaretleri_ve_buyuk_kucuk_harf_atar(self):
        self.assertEqual(og.norm('Hela: of Mice & Magic'), og.norm('Hela: Of Mice & Magic™'))

    def test_farkli_surum_eslesmez(self):
        self.assertNotEqual(og.norm('Grand Theft Auto VI'), og.norm('Grand Theft Auto V'))

    @patch('oyun_gorsel_cek.time.sleep')
    def test_steam_tam_eslesmeyi_kabul_eder(self, _sleep):
        yanit = {'items': [{'type': 'app', 'name': 'Hela: Of Mice & Magic™', 'id': 3161310}]}
        with patch('oyun_gorsel_cek.json_al', return_value=yanit):
            self.assertEqual(og.steam_bul(['Hela: of Mice & Magic']), (3161310, 'Hela: Of Mice & Magic™'))

    @patch('oyun_gorsel_cek.time.sleep')
    def test_steam_yanlis_suru_reddeder(self, _sleep):
        yanit = {'items': [{'type': 'app', 'name': 'Grand Theft Auto V', 'id': 271590}]}
        with patch('oyun_gorsel_cek.json_al', return_value=yanit):
            self.assertIsNone(og.steam_bul(['Grand Theft Auto VI']))


class CiktiBicimi(unittest.TestCase):
    def test_alan_sirasi_ve_eksik_genis_yazilmaz(self):
        kayit = {'boy': 353, 'en': 616, 'kaynak': 'Steam', 'url': 'https://x/a.jpg'}
        self.assertEqual(list(og.alanlari_sirala(kayit)), ['url', 'kaynak', 'en', 'boy'])
        kayit['genis'] = 'https://x/b.jpg'
        self.assertEqual(list(og.alanlari_sirala(kayit)), ['url', 'genis', 'kaynak', 'en', 'boy'])

    def test_sirali_iki_bolum_ve_utf8_json(self):
        yeni = {'oyun': {'b': {'url': 'u', 'kaynak': 'Ş'}, 'a': {'url': 'u', 'kaynak': 'Ş'}}, 'takvim': {}}
        s = og.sirali(yeni)
        self.assertEqual(list(s), ['takvim', 'oyun'])
        self.assertEqual(list(s['oyun']), ['a', 'b'])
        self.assertIn('Ş', json.dumps(s, ensure_ascii=False))


class Toplama(unittest.TestCase):
    def setUp(self):
        self.bolumler = {
            'takvim': [('t1', ['Oyun Bir'], 'https://r/1', 'Yayıncı'),
                       ('t2', ['Oyun İki'], 'https://r/2', 'Yayıncı')],
            'oyun': [('o1', ['Oyun Üç'], 'https://r/3', 'Geliştirici')],
        }

    def test_var_olan_kayit_yeniden_cekilmez(self):
        eski = {'takvim': {'t1': {'url': 'eski', 'kaynak': 'Steam', 'en': 616, 'boy': 353}}}
        cagrilar = []

        def bul(adlar, url, ad):
            cagrilar.append(adlar[0])
            return {'url': 'yeni', 'kaynak': 'Steam', 'en': 1, 'boy': 1}, 'ok'

        yeni, sayac = self._calistir(eski, False, bul)
        self.assertEqual(yeni['takvim']['t1']['url'], 'eski')
        self.assertNotIn('Oyun Bir', cagrilar)
        self.assertEqual(sayac['denenen'], 2)  # t2 ve o1

    def test_yenile_var_olani_gunceller(self):
        eski = {'takvim': {'t1': {'url': 'eski', 'kaynak': 'Steam', 'en': 616, 'boy': 353}}}

        def bul(adlar, url, ad):
            return {'url': 'yeni', 'kaynak': 'Steam', 'en': 616, 'boy': 353}, 'ok'

        yeni, _ = self._calistir(eski, True, bul)
        self.assertEqual(yeni['takvim']['t1']['url'], 'yeni')

    def test_ag_hatasi_kaydi_atlar_digerleri_devam_eder(self):
        def bul(adlar, url, ad):
            if adlar[0] == 'Oyun Bir':
                raise OSError('zaman aşımı')
            return {'url': 'ok', 'kaynak': 'Steam', 'en': 616, 'boy': 353}, 'ok'

        with patch('oyun_gorsel_cek.time.sleep'):
            yeni, sayac = og.topla(self.bolumler, {}, False, [], bul)
        self.assertNotIn('t1', yeni['takvim'])
        self.assertIn('t2', yeni['takvim'])
        self.assertIn('o1', yeni['oyun'])
        self.assertEqual(sayac['atlanan'], 1)

    def test_bulunamayan_eski_kayit_korunur(self):
        eski = {'oyun': {'o1': {'url': 'eski', 'kaynak': 'Geliştirici', 'en': 700, 'boy': 400}}}

        def bul(adlar, url, ad):
            return None, 'yok'

        yeni, _ = self._calistir(eski, True, bul)
        self.assertEqual(yeni['oyun']['o1']['url'], 'eski')

    def _calistir(self, eski, yenile, bul):
        with patch('oyun_gorsel_cek.time.sleep'):
            return og.topla(self.bolumler, eski, yenile, [], bul)


if __name__ == '__main__':
    unittest.main()
