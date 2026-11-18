"""Oyun adı doğrulaması (A), dökümsüz klip metni (B) ve yeniden-uret düzenleme seçenekleri (C). Ağ/model/ffmpeg yok."""
import contextlib
import io
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tools'))
import klip_oyun as ko  # noqa: E402
import yayin_klip as yk  # noqa: E402

ARALIK = [100.0, 150.0]


def sorucu(metin, sayac=None):
    def sor(istem, cwd):
        if sayac is not None:
            sayac.append(istem)
        return {'metin': metin, 'maliyet_usd': 0.01}
    return sor


def kareler():
    return [object()] * 3


@contextlib.contextmanager
def kolajsiz():
    with mock.patch.object(ko, 'kolaj_yaz', lambda k, h: None):
        yield


class YanitCozmeTesti(unittest.TestCase):
    def test_evet_kanitla(self):
        c = ko.yaniti_coz('{"karar":"evet","oyun":null,"kanit":"Potato Please menüsü"}', 'Potato Please')
        self.assertEqual((c['karar'], c['oyun']), ('evet', None))

    def test_evet_kanitsiz_bilinmiyor(self):
        self.assertEqual(ko.yaniti_coz('{"karar":"evet","oyun":null}', 'X')['karar'], 'bilinmiyor')

    def test_hayir_adli_kanitli(self):
        c = ko.yaniti_coz('```json\n{"karar":"hayir","oyun":"Counter-Strike 2","kanit":"HUD"}\n```', 'Potato Please')
        self.assertEqual((c['karar'], c['oyun']), ('hayir', 'Counter-Strike 2'))

    def test_hayir_adsiz_ya_da_ayni_ad_bilinmiyor(self):
        self.assertEqual(ko.yaniti_coz('{"karar":"hayir","oyun":null,"kanit":"x"}', 'A')['karar'], 'bilinmiyor')
        self.assertEqual(ko.yaniti_coz('{"karar":"hayir","oyun":"a","kanit":"x"}', 'A')['karar'], 'bilinmiyor')
        self.assertEqual(ko.yaniti_coz('{"karar":"hayir","oyun":"unknown","kanit":"x"}', 'A')['karar'], 'bilinmiyor')

    def test_bozuk_yanit_bilinmiyor(self):
        self.assertEqual(ko.yaniti_coz('bence evet', 'A')['karar'], 'bilinmiyor')
        self.assertEqual(ko.yaniti_coz('[1]', 'A')['karar'], 'bilinmiyor')


class OyunKarariTesti(unittest.TestCase):
    def karar(self, metin, kategori='Potato Please', **kw):
        cagri = []
        with kolajsiz():
            k = ko.oyun_karari(kategori, ARALIK, kareler, sor=sorucu(metin, cagri), **kw)
        return k, cagri

    def test_onay_kategoriyi_yazar(self):
        k, c = self.karar('{"karar":"evet","oyun":null,"kanit":"logo"}')
        self.assertEqual((k['oyun'], k['kaynak'], len(c)), ('Potato Please', 'model-kare-onay', 1))

    def test_yanlis_kategori_modelin_adini_yazar(self):
        k, _ = self.karar('{"karar":"hayir","oyun":"Counter-Strike 2","kanit":"HUD"}')
        self.assertEqual((k['oyun'], k['kaynak']), ('Counter-Strike 2', 'model-kare'))
        self.assertEqual(k['kategori'], 'Potato Please')

    def test_emin_degil_ad_yazilmaz(self):
        k, _ = self.karar('{"karar":"bilinmiyor","oyun":null,"kanit":null}')
        self.assertEqual((k['oyun'], k['kaynak']), (None, 'model-kare-bilinmiyor'))

    def test_teknik_hata_ad_yazilmaz_ve_onbellege_alinmaz(self):
        def patla(istem, cwd):
            raise ko.OyunHatasi('model yok')
        with kolajsiz():
            k = ko.oyun_karari('X', ARALIK, kareler, sor=patla)
        self.assertEqual((k['oyun'], k['kaynak'], k['durum']), (None, 'dogrulanamadi', 'hata'))
        self.assertFalse(ko.onbellek_gecerli(k, 'X', ARALIK))

    def test_kare_alinamazsa_ad_yazilmaz(self):
        def yok():
            raise RuntimeError('kare yok')
        k = ko.oyun_karari('X', ARALIK, yok, sor=sorucu('{}'))
        self.assertEqual((k['oyun'], k['durum']), (None, 'hata'))

    def test_kategori_yoksa_model_cagrilmaz(self):
        cagri = []
        k = ko.oyun_karari(None, ARALIK, kareler, sor=sorucu('{}', cagri))
        self.assertEqual((k['oyun'], k['kaynak'], cagri), (None, 'kategori-yok', []))

    def test_elle_oyun_ve_oyunsuz_model_cagirmaz(self):
        cagri = []
        a = ko.oyun_karari('X', ARALIK, kareler, elle='Elden Ring', sor=sorucu('{}', cagri))
        b = ko.oyun_karari('X', ARALIK, kareler, elle='', sor=sorucu('{}', cagri))
        self.assertEqual((a['oyun'], a['kaynak'], b['oyun'], b['kaynak'], cagri), ('Elden Ring', 'elle', None, 'elle', []))

    def test_onbellek_ikinci_cagriyi_onler(self):
        ilk, c1 = self.karar('{"karar":"hayir","oyun":"CS2","kanit":"HUD"}')
        ikinci, c2 = self.karar('{"karar":"evet","oyun":null,"kanit":"x"}', onbellek=ilk)
        self.assertEqual((len(c1), len(c2), ikinci['oyun'], ikinci['kaynak']), (1, 0, 'CS2', 'onbellek'))

    def test_onbellek_kategori_ya_da_aralik_degisince_gecersiz(self):
        ilk, _ = self.karar('{"karar":"evet","oyun":null,"kanit":"x"}')
        self.assertTrue(ko.onbellek_gecerli(ilk, 'Potato Please', [101.5, 148.0]))
        self.assertFalse(ko.onbellek_gecerli(ilk, 'Baska', ARALIK))
        self.assertFalse(ko.onbellek_gecerli(ilk, 'Potato Please', [110.0, 160.0]))


class SesYargisiTesti(unittest.TestCase):
    def dok(self, metin):
        kelimeler = [{'bas': i * 0.5, 'bit': i * 0.5 + 0.4, 'metin': (' ' if i else '') + w} for i, w in enumerate(metin.split())]
        return lambda ses, model, cihaz, hedef, kucuk=None: {'segmentler': [{'kelimeler': kelimeler}], 'model': 'sahte',
                                                              'olcum': {'sure_sn': 1}}

    def yargi(self, kisa, baslik='Eray vuranlara uzun uzun isyan ediyor', anlasilir=True, puan=7):
        yanit = json.dumps({'puan': puan, 'gerekce': 'g', 'anlasilir': anlasilir, 'bas_cumle': 0, 'son_cumle': 0,
                            'baslik': baslik, 'kisa_aciklama': kisa}, ensure_ascii=False)
        return lambda istem: yanit

    def calistir(self, metin, model, **kw):
        with tempfile.TemporaryDirectory() as t:
            return ko.ses_yargisi(ARALIK, 'Eray', pathlib.Path(t) / 'a.wav', pathlib.Path(t), {}, model=model,
                                  dok=self.dok(metin), **kw)

    def test_anlamli_konusma_metin_uretir(self):
        s = self.calistir('Abi bunlar koşarak vuruyor yani bu ne ya. Hiç adil değil.', self.yargi('Eray koşarak vuranlara isyan ediyor'))
        self.assertEqual((s['durum'], s['kisa_aciklama']), ('tamam', 'Eray koşarak vuranlara isyan ediyor'))
        self.assertIn('koşarak', s['dokum'])
        self.assertEqual(s['kaynak'], 'klip-sesi-whisper')

    def test_bos_konusma_model_cagirmaz(self):
        sayac = []
        s = self.calistir('hmm', lambda i: sayac.append(i))
        self.assertEqual((s['durum'], sayac), ('bos', []))

    def test_model_anlatacak_bir_sey_bulmazsa_bos(self):
        s = self.calistir('Şey evet yani tamam o zaman bakalım ne olacak.', self.yargi(None, anlasilir=False, puan=1))
        self.assertEqual((s['durum'], s['kisa_aciklama']), ('bos', None))
        self.assertTrue(s['dokum'])

    def test_kufurlu_kisa_aciklama_atilir(self):
        s = self.calistir('Abi bu ne ya bu ne yani hiç adil değil.', self.yargi('Eray amk diye bağırıyor', anlasilir=False))
        self.assertIsNone(s['kisa_aciklama'])

    def test_yalniz_dokum_modu(self):
        s = self.calistir('Abi bunlar koşarak vuruyor yani bu ne ya.', lambda i: self.fail('model çağrılmamalı'), yargi=False)
        self.assertEqual((s['durum'], s['kisa_aciklama']), ('tamam', None))
        self.assertTrue(s['dokum'])

    def test_dok_hatasi_hata_durumu_onbellege_alinmaz(self):
        def patla(*a, **k):
            raise RuntimeError('gpu yok')
        with tempfile.TemporaryDirectory() as t:
            s = ko.ses_yargisi(ARALIK, 'Eray', pathlib.Path(t) / 'a.wav', pathlib.Path(t), {}, dok=patla, model=lambda i: '')
        self.assertEqual(s['durum'], 'hata')
        self.assertFalse(ko.ses_onbellek_gecerli(s, ARALIK))

    def test_onbellek_gecerli(self):
        s = {'durum': 'bos', 'aralik': [100.0, 150.0]}
        self.assertTrue(ko.ses_onbellek_gecerli(s, ARALIK))
        self.assertFalse(ko.ses_onbellek_gecerli(s, [200.0, 250.0]))


VOD = {'yayinci': 'Eraycan', 'kisa_ad': 'Eray', 'platform': 'kick', 'oyun': 'Potato Please', 'sure_sn': 5000, 'anahtar': 'k:1',
       'vod_id': 'abcdefgh', 'kanal': 'eray', 'kanal_url': 'https://kick.com/eray', 'vod_url': 'https://kick.com/video/abcdefgh',
       'baslik': 'yayin', 'tarih': '2026-11-12'}


class ZenginlestirTesti(unittest.TestCase):
    def calis(self, klip, ayar=None):
        with tempfile.TemporaryDirectory() as t, mock.patch.object(yk.klip_kamera, 'kareleri_ornekle', lambda *a, **k: kareler()), \
                mock.patch.object(ko, 'ses_cikar', lambda *a, **k: None), kolajsiz():
            return yk.klip_zenginlestir(VOD, klip, ayar, 'ff', 'k', 0.0, 50.0, False, pathlib.Path(t))

    def klip(self, **kw):
        return {'klip_baslangic_sn': 100.0, 'klip_bitis_sn': 150.0, **kw}

    def test_yanlis_kategori_duzelir_ve_pakete_gider(self):
        k = self.klip()
        vod = self.calis(k, {'_oyun_sor': sorucu('{"karar":"hayir","oyun":"Counter-Strike 2","kanit":"HUD"}'),
                              'klip_ses_yargisi': False})
        self.assertEqual(vod['oyun'], 'Counter-Strike 2')
        p = yk.paket_json(VOD, {**k, 'zirve_sn': 120, 'zirve_zaman': '0:02:00', 'puan': 5, 'no': 1}, pathlib.Path('k.mp4'), {})
        self.assertEqual(p['oyun'], 'Counter-Strike 2')
        self.assertTrue(p['baslik'].endswith('| Counter-Strike 2'))
        self.assertEqual(p['oyun_dogrulama']['kaynak'], 'model-kare')

    def test_emin_degilse_ne_videoda_ne_basliktta_oyun_adi_olur(self):
        k = self.klip()
        vod = self.calis(k, {'_oyun_sor': sorucu('{"karar":"bilinmiyor","oyun":null,"kanit":null}'), 'klip_ses_yargisi': False})
        self.assertIsNone(vod['oyun'])
        p = yk.paket_json(VOD, {**k, 'zirve_sn': 120, 'zirve_zaman': '0:02:00', 'puan': 5, 'no': 1}, pathlib.Path('k.mp4'), {})
        self.assertIsNone(p['oyun'])
        self.assertNotIn('Potato', p['baslik'])

    def test_dokumsuz_klip_kendi_sesinden_metin_alir(self):
        k = self.klip()
        yanit = json.dumps({'puan': 7, 'gerekce': 'g', 'anlasilir': True, 'bas_cumle': 0, 'son_cumle': 0,
                            'baslik': 'Eray koşarak vuran rakiplere uzun uzun isyan ediyor', 'kisa_aciklama': 'Eray koşarak vuranlara isyan ediyor'},
                           ensure_ascii=False)
        dok = lambda *a, **kw: {'segmentler': [{'kelimeler': [{'bas': 0, 'bit': .4, 'metin': 'Abi'}, {'bas': .5, 'bit': .9, 'metin': ' bunlar'},
                                {'bas': 1, 'bit': 1.4, 'metin': ' koşarak'}, {'bas': 1.5, 'bit': 1.9, 'metin': ' vuruyor.'}]}], 'model': 'm'}
        self.calis(k, {'klip_oyun_dogrula': False, '_ses_dok': dok, '_ses_yargi_modeli': lambda i: yanit})
        self.assertEqual(k['konusma_kisa_aciklama'], 'Eray koşarak vuranlara isyan ediyor')
        self.assertIn('koşarak', k['dokum_metni'])
        p = yk.paket_json(VOD, {**k, 'zirve_sn': 120, 'zirve_zaman': '0:02:00', 'puan': 5, 'no': 1}, pathlib.Path('k.mp4'), {},
                          {'klip_aciklama_yazi': True})
        self.assertEqual(p['kisa_aciklama'], 'Eray koşarak vuranlara isyan ediyor')
        self.assertEqual(p['ses_yargisi']['durum'], 'tamam')

    def test_bos_konusmada_sablon_baslik_kalir(self):
        k = self.klip()
        dok = lambda *a, **kw: {'segmentler': [{'kelimeler': []}], 'model': 'm'}
        self.calis(k, {'klip_oyun_dogrula': False, '_ses_dok': dok, '_ses_yargi_modeli': lambda i: self.fail('çağrılmamalı')})
        self.assertNotIn('konusma_baslik', k)
        self.assertEqual(k['ses_yargisi']['durum'], 'bos')

    def test_dokumlu_klipte_ses_yargisi_calismaz(self):
        k = self.klip(dokum_metni='zaten var')
        self.calis(k, {'klip_oyun_dogrula': False, '_ses_dok': lambda *a, **kw: self.fail('çağrılmamalı')})
        self.assertNotIn('ses_yargisi', k)

    def test_elle_metin_varsa_yalniz_dokum(self):
        k = self.klip(aciklama_elle='Eray bir şey yapıyor')
        dok = lambda *a, **kw: {'segmentler': [{'kelimeler': [{'bas': i * .5, 'bit': i * .5 + .4, 'metin': w}
                                for i, w in enumerate(['Abi', ' bunlar', ' koşarak', ' vuruyor.'])]}], 'model': 'm'}
        self.calis(k, {'klip_oyun_dogrula': False, '_ses_dok': dok, '_ses_yargi_modeli': lambda i: self.fail('çağrılmamalı')})
        self.assertTrue(k['dokum_metni'])
        self.assertNotIn('konusma_baslik', k)

    def test_onbellekli_ses_yargisi_yeniden_calismaz(self):
        k = self.klip(ses_yargisi={'durum': 'bos', 'aralik': ARALIK, 'dokum': 'eski'})
        self.calis(k, {'klip_oyun_dogrula': False, '_ses_dok': lambda *a, **kw: self.fail('çağrılmamalı')})
        self.assertEqual(k['dokum_metni'], 'eski')


class DogrulamaTesti(unittest.TestCase):
    def test_aciklama_45_karakter(self):
        self.assertEqual(yk.aciklama_metni_dogrula('Eray koşarak vuranlara isyan ediyor'), 'Eray koşarak vuranlara isyan ediyor')
        with self.assertRaisesRegex(yk.KlipHatasi, '46 karakter'):
            yk.aciklama_metni_dogrula('a' * 44 + ' b')

    def test_aciklama_yasak_kelime_ve_bos(self):
        with self.assertRaisesRegex(yk.KlipHatasi, 'yasak kelime'):
            yk.aciklama_metni_dogrula('Eray amk diye bağırıyor')
        with self.assertRaisesRegex(yk.KlipHatasi, 'boş'):
            yk.aciklama_metni_dogrula('  ')
        with self.assertRaisesRegex(yk.KlipHatasi, 'uygun değil'):
            yk.aciklama_metni_dogrula('Tek')

    def test_kamera_kutusu(self):
        self.assertEqual(yk.kamera_kutusu_coz('0.02,0.6,0.28,0.38'), (0.02, 0.6, 0.28, 0.38))
        for kotu in ('1,2', 'a,b,c,d', '0.9,0.9,0.5,0.5', '0,0,0,0'):
            with self.assertRaises(yk.KlipHatasi, msg=kotu):
                yk.kamera_kutusu_coz(kotu)

    def test_baslik_oyun_eki(self):
        self.assertEqual(yk.baslik_oyun_duzelt('Eray gülüyor | Potato Please', 'Potato Please', None), 'Eray gülüyor')
        self.assertEqual(yk.baslik_oyun_duzelt('Eray gülüyor | Potato Please', 'Potato Please', 'CS2'), 'Eray gülüyor | CS2')
        self.assertEqual(yk.baslik_oyun_duzelt('Eray gülüyor', None, None), 'Eray gülüyor')
        self.assertEqual(yk.baslik_oyun_duzelt('Eray gülüyor | CS2', 'CS2', 'CS2'), 'Eray gülüyor | CS2')


class YenidenUretSecenekTesti(unittest.TestCase):
    """paketten_uret: doğrulama + kalıcılık. vod_hazirla ve klip_kes sahte; mp4 yok."""

    def kur(self, **paket):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        kok = pathlib.Path(t.name)
        yol = kok / 'p' / 'klip-01.json'
        yol.parent.mkdir()
        yol.with_suffix('.mp4').write_bytes(b'x')
        d = {'yayinci': 'Eraycan', 'vod_url': VOD['vod_url'], 'klip_baslangic_sn': 100.0, 'klip_bitis_sn': 150.0, 'oyun': 'Potato Please',
             'baslik': 'Eraycan yayınında chat kahkahaya boğuldu | Potato Please', 'kisa_aciklama': None, **paket}
        yol.write_text(json.dumps(d), encoding='utf-8')
        return kok, yol

    def uret(self, yol, kok, secenek=None, oyun_sor=None, **kw):
        goruldu = {}

        def sahte_kes(vod, klip, hedef, ff, font, ayar):
            goruldu.update(vod=vod, klip=dict(klip), ayar=ayar)
            klip['oyun_dogrulama'] = ko.oyun_karari(vod.get('oyun'), [klip['klip_baslangic_sn'], klip['klip_bitis_sn']], kareler,
                                                     elle=klip.get('oyun_elle'), onbellek=klip.get('oyun_dogrulama'),
                                                     sor=oyun_sor or sorucu('{"karar":"evet","oyun":null,"kanit":"x"}'))
            return {'genislik': 1080, 'yukseklik': 1920, 'sure_sn': klip['klip_bitis_sn'] - klip['klip_baslangic_sn'], 'ses': True,
                    'aciklama_yazisi': None}
        with mock.patch.object(yk, 'vod_hazirla', lambda a, b: (dict(VOD), {})), mock.patch.object(yk, 'klip_kes', sahte_kes), \
                mock.patch.object(yk, 'ffmpeg_bul', lambda: 'ff'), mock.patch.object(yk, 'font_bul', lambda: 'f'), kolajsiz():
            cikti = yk.paketten_uret(yol, {'ayar': {}}, kok, kok / 'yedek', secenek=secenek, **kw)
        return cikti, goruldu, json.loads(yol.read_text(encoding='utf-8'))

    def test_kaydirma_sure_siniri(self):
        kok, yol = self.kur()
        for sec, parca in (({'son_kaydir': 20}, '70.0 sn olurdu'), ({'bas_kaydir': 50}, '0.0 sn olurdu'),
                           ({'son_kaydir': -48}, '2.0 sn olurdu')):
            with self.assertRaisesRegex(yk.KlipHatasi, parca):
                self.uret(yol, kok, sec)
        with self.assertRaisesRegex(yk.KlipHatasi, 'önceye gidiyor'):
            self.uret(yol, kok, {'bas_kaydir': -150, 'son_kaydir': -145})

    def test_kaydirma_kalici_ve_zaman_damgasi(self):
        kok, yol = self.kur()
        _, g, d = self.uret(yol, kok, {'bas_kaydir': -4, 'son_kaydir': 3})
        self.assertEqual((d['klip_baslangic_sn'], d['klip_bitis_sn']), (96.0, 153.0))
        self.assertEqual(d['duzenleme']['bas_kaydir_toplam'], -4.0)
        self.assertTrue(d['vod_zaman_damgali_url'].endswith('?t=96'))
        # ikinci yeniden kesim seçeneksiz: aralık korunur, bir daha kaydırılmaz
        _, g2, d2 = self.uret(yol, kok)
        self.assertEqual((d2['klip_baslangic_sn'], d2['klip_bitis_sn']), (96.0, 153.0))

    def test_oyun_ve_oyunsuz_kalici(self):
        kok, yol = self.kur()
        _, g, d = self.uret(yol, kok, {'oyun': 'Counter-Strike 2'})
        self.assertEqual((d['oyun'], d['oyun_dogrulama']['kaynak']), ('Counter-Strike 2', 'elle'))
        self.assertTrue(d['baslik'].endswith('| Counter-Strike 2'))
        _, g, d = self.uret(yol, kok)    # seçenek yok: elle ad korunur
        self.assertEqual(d['oyun'], 'Counter-Strike 2')
        _, g, d = self.uret(yol, kok, {'oyunsuz': True})
        self.assertIsNone(d['oyun'])
        self.assertNotIn('|', d['baslik'])
        _, g, d = self.uret(yol, kok)
        self.assertIsNone(d['oyun'])

    def test_oyun_ve_oyunsuz_birlikte_hata(self):
        kok, yol = self.kur()
        with self.assertRaisesRegex(yk.KlipHatasi, 'birlikte verilemez'):
            self.uret(yol, kok, {'oyun': 'A', 'oyunsuz': True})

    def test_aciklama_metni_kalici_baslik_ve_kisa(self):
        kok, yol = self.kur()
        _, g, d = self.uret(yol, kok, {'aciklama_metni': 'Eray koşarak vuranlara isyan ediyor'})
        self.assertEqual((d['kisa_aciklama'], d['baslik']), ('Eray koşarak vuranlara isyan ediyor',) * 2)
        self.assertEqual(g['klip']['konusma_kisa_aciklama'], 'Eray koşarak vuranlara isyan ediyor')
        _, g, d = self.uret(yol, kok)
        self.assertEqual(g['klip']['konusma_kisa_aciklama'], 'Eray koşarak vuranlara isyan ediyor')

    def test_aciklama_hatalari_pakete_dokunmaz(self):
        kok, yol = self.kur()
        once = yol.read_text(encoding='utf-8')
        for metin in ('a' * 46, 'Eray amk diye bağırıyor'):
            with self.assertRaises(yk.KlipHatasi):
                self.uret(yol, kok, {'aciklama_metni': metin})
        self.assertEqual(yol.read_text(encoding='utf-8'), once)
        self.assertFalse((kok / 'yedek').exists())

    def test_aciklamasiz_kalici(self):
        kok, yol = self.kur(kisa_aciklama='Eray bir şey yapıyor')
        _, g, d = self.uret(yol, kok, aciklamasiz=True)
        self.assertIs(g['ayar']['klip_aciklama_yazi'], False)
        self.assertEqual(d['kisa_aciklama'], 'Eray bir şey yapıyor')     # paylaşım metni korunur
        _, g, d = self.uret(yol, kok)
        self.assertIs(g['ayar']['klip_aciklama_yazi'], False)

    def test_aciklama_ve_aciklamasiz_birlikte_hata(self):
        kok, yol = self.kur()
        with self.assertRaisesRegex(yk.KlipHatasi, 'birlikte verilemez'):
            self.uret(yol, kok, {'aciklama_metni': 'Eray bir şey yapıyor'}, aciklamasiz=True)

    def test_yayinci_adi_duzen_ve_kamera_kutusu_kalici(self):
        kok, yol = self.kur()
        cikti, g, d = self.uret(yol, kok, {'yayinci_adi': 'Eray', 'duzen': 'kadraj', 'kamera_kutu': (0.02, 0.6, 0.28, 0.38)})
        self.assertEqual((g['vod']['yayinci'], g['ayar']['duzen'], g['vod']['kamera_kutu']), ('Eray', 'kadraj', (0.02, 0.6, 0.28, 0.38)))
        self.assertEqual((d['yayinci'], d['yayinci_adi']), ('Eraycan', 'Eray'))
        self.assertEqual(json.loads(json.dumps(cikti))['duzenleme']['duzen'], 'kadraj')
        _, g, d = self.uret(yol, kok)
        self.assertEqual((g['vod']['yayinci'], g['ayar']['duzen'], list(g['vod']['kamera_kutu'])), ('Eray', 'kadraj', [0.02, 0.6, 0.28, 0.38]))

    def test_gecersiz_duzen_ve_kutu(self):
        kok, yol = self.kur()
        with self.assertRaisesRegex(yk.KlipHatasi, 'düzen'):
            self.uret(yol, kok, {'duzen': 'x'})
        with self.assertRaises(yk.KlipHatasi):
            self.uret(yol, kok, {'kamera_kutu': (0.9, 0.9, 0.5, 0.5)})

    def test_dogrulanan_oyun_ve_ikinci_kesimde_onbellek(self):
        kok, yol = self.kur()
        sor = sorucu('{"karar":"hayir","oyun":"Counter-Strike 2","kanit":"HUD"}')
        _, g, d = self.uret(yol, kok, oyun_sor=sor)
        self.assertEqual((d['oyun'], d['oyun_dogrulama']['kaynak']), ('Counter-Strike 2', 'model-kare'))
        cagri = []
        _, g, d = self.uret(yol, kok, oyun_sor=sorucu('{"karar":"evet","oyun":null,"kanit":"x"}', cagri))
        self.assertEqual((d['oyun'], cagri, d['oyun_dogrulama']['kaynak']), ('Counter-Strike 2', [], 'onbellek'))

    def test_kaydirma_oyun_onbellegini_dusurur(self):
        kok, yol = self.kur()
        self.uret(yol, kok, oyun_sor=sorucu('{"karar":"hayir","oyun":"CS2","kanit":"HUD"}'))
        cagri = []
        _, g, d = self.uret(yol, kok, {'bas_kaydir': -5, 'son_kaydir': -5}, oyun_sor=sorucu('{"karar":"evet","oyun":null,"kanit":"x"}', cagri))
        self.assertEqual(len(cagri), 1)
        self.assertEqual(d['oyun'], 'Potato Please')


class KomutSatiriTesti(unittest.TestCase):
    """Panelin çağıracağı sözleşme: tek satır Türkçe stderr + sıfırdan farklı çıkış kodu."""

    def calistir(self, *argv):
        err, out = io.StringIO(), io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
            try:
                kod = yk.main(['yeniden-uret', *argv])
            except SystemExit as e:
                kod = e.code
        return kod, out.getvalue(), err.getvalue()

    def test_hata_tek_satir_ve_kod(self):
        for argv in (['x.json', '--bas-kaydir', 'abc'], ['x.json', '--oyun', 'A', '--oyunsuz'], ['x.json', '--kamera-kutu', '1,2'],
                     ['x.json', '--duzen', 'foo'], ['x.json', '--aciklama-metni', 'Eray amk diye bağırıyor'],
                     ['yok.json', '--aciklama-metni', 'Eray bir şey yapıyor']):
            kod, out, err = self.calistir(*argv)
            self.assertNotEqual(kod, 0, argv)
            self.assertEqual(out, '')
            self.assertTrue(err.startswith('HATA: '), (argv, err))
            self.assertEqual(len(err.strip().splitlines()), 1, (argv, err))

    def test_basari_tek_satir_json(self):
        with tempfile.TemporaryDirectory() as t:
            yol = pathlib.Path(t) / 'klip-01.json'
            yol.write_text('{}', encoding='utf-8')
            cikti = {'paket': str(yol), 'oyun': None}
            with mock.patch.object(yk, 'paketten_uret', mock.Mock(return_value=cikti)) as m:
                kod, out, err = self.calistir(str(yol), '--oyun', 'Elden Ring', '--bas-kaydir', '-3', '--son-kaydir', '2.5',
                                              '--kamera-kutu', '0.1,0.2,0.3,0.4', '--yayinci-adi', 'Eray', '--duzen', 'serit')
            self.assertEqual((kod, err), (0, ''))
            self.assertEqual(len(out.strip().splitlines()), 1)
            self.assertEqual(json.loads(out), cikti)
            sec = m.call_args.args[5]
            self.assertEqual(sec, {'oyun': 'Elden Ring', 'yayinci_adi': 'Eray', 'bas_kaydir': -3.0, 'son_kaydir': 2.5,
                                   'duzen': 'serit', 'kamera_kutu': (0.1, 0.2, 0.3, 0.4)})


if __name__ == '__main__':
    unittest.main()
