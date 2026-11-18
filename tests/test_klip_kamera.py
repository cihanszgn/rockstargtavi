"""Kamera bulma ve 'kamera' düzeni testleri. Ağ, ffmpeg ve model gerekmez; tespitler sentetiktir."""
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tools'))
import klip_kamera as kk  # noqa: E402
import yayin_klip as yk  # noqa: E402

ORAN = 16 / 9
FONT = 'C:\\Windows\\Fonts\\arialbd.ttf'
METIN = {'ad': 'a', 'oyun': 'b', 'kaynak': 'c', 'marka': 'd'}


def sabit(n=10, cx=0.12, cy=0.66, w=0.03, h=0.06, gurultu=0.002):
    """n karede aynı yerde (küçük titreşimle) tek yüz."""
    return [[(cx + gurultu * (i % 3 - 1), cy, w, h, 0.9)] for i in range(n)]


def std(deger):
    return lambda kumeler: [deger] * len(kumeler)


class KumelemeTesti(unittest.TestCase):
    def test_ayni_yer_tek_kume(self):
        k = kk.kumele(sabit(), ORAN)
        self.assertEqual(len(k), 1)
        self.assertEqual(k[0]['kare'], 10)
        self.assertEqual(k[0]['oran'], 1.0)
        self.assertLess(k[0]['kayma'], 0.2)

    def test_iki_uzak_yuz_iki_kume(self):
        t = [[(0.12, 0.66, 0.03, 0.06, 0.9), (0.8, 0.3, 0.03, 0.06, 0.9)] for _ in range(8)]
        k = kk.kumele(t, ORAN)
        self.assertEqual([c['kare'] for c in k], [8, 8])

    def test_kume_karede_bir_kez_sayilir(self):
        t = [[(0.12, 0.66, 0.03, 0.06, 0.9), (0.121, 0.661, 0.03, 0.06, 0.8)] for _ in range(5)]
        k = kk.kumele(t, ORAN)
        self.assertEqual(max(c['kare'] for c in k), 5)

    def test_bos(self):
        self.assertEqual(kk.kumele([[], [], []], ORAN), [])
        self.assertEqual(kk.kumele([], ORAN), [])


class KararTesti(unittest.TestCase):
    def plan(self, tesp, **kw):
        return kk.plan_kur(tesp, ORAN, kw.pop('ayar', None), zaman_std=kw.pop('zaman_std', std(30.0)), **kw)

    def test_kose_kamera(self):
        p = self.plan(sabit())
        self.assertEqual((p['duzen'], p['neden']), ('kamera', 'kucuk_kamera'))
        x, y, w, h = p['kamera_kutu']
        self.assertEqual(x, 0.0)   # köşeye yaslanır
        self.assertTrue(kk.kutu_gecerli(p['kamera_kutu']))
        self.assertLessEqual(w * h, kk.VARSAYILAN['kamera_en_cok_alan'])

    def test_yuz_yok(self):
        p = self.plan([[] for _ in range(10)])
        self.assertEqual((p['duzen'], p['neden']), ('tek', 'yuz_yok'))

    def test_grid_cok_yuz(self):
        t = [[(0.2, 0.3, 0.05, 0.1, .9), (0.6, 0.3, 0.05, 0.1, .9), (0.2, 0.7, 0.05, 0.1, .9)] for _ in range(10)]
        self.assertEqual(self.plan(t)['neden'], 'cok_yuz')

    def test_kararsiz_yuz(self):
        t = [[(0.1 + 0.05 * i, 0.6, 0.03, 0.06, .9)] if i < 5 else [] for i in range(10)]
        self.assertEqual(self.plan(t)['duzen'], 'tek')

    def test_celiskili_yuz(self):
        t = sabit()
        for i in range(4):   # ikinci, yarı sürede görünen uzak yüz
            t[i] = t[i] + [(0.8, 0.3, 0.03, 0.06, .9)]
        p = self.plan(t)
        self.assertEqual((p['duzen'], p['neden']), ('tek', 'celiskili_yuz'))

    def test_ortadaki_buyuk_yuz(self):
        p = self.plan(sabit(cx=0.5, cy=0.5, w=0.15, h=0.3))
        self.assertEqual((p['duzen'], p['neden']), ('tek', 'yuz_ortada'))

    def test_sabit_avatar_yok_sayilir(self):
        t = [a + [(0.97, 0.63, 0.04, 0.1, .9)] for a in sabit()]
        std_ = lambda kumeler: [30.0 if c['cx'] < 0.5 else 10.0 for c in kumeler]   # noqa: E731
        p = self.plan(t, zaman_std=std_)
        self.assertEqual(p['duzen'], 'kamera')
        self.assertLess(p['yuz'][0], 0.5)

    def test_kucuk_hud_yuzu_elenir(self):
        # baskın köşe kamerası + çok küçük (alan < %60) HUD yüzü: kamera kalır
        t = [a + [(0.9, 0.2, 0.012, 0.02, .9)] for a in sabit(w=0.04, h=0.08)]
        p = self.plan(t)
        self.assertEqual((p['duzen'], p['neden']), ('kamera', 'kucuk_kamera'))

    def test_esit_boy_iki_yuz_cok_yuz(self):
        t = [a + [(0.9, 0.2, 0.03, 0.06, .9)] for a in sabit()]
        self.assertEqual(self.plan(t)['neden'], 'cok_yuz')

    def test_kucuk_kume_orani_ayardan(self):
        t = [a + [(0.9, 0.2, 0.012, 0.02, .9)] for a in sabit(w=0.04, h=0.08)]
        p = self.plan(t, ayar={'kamera_kucuk_kume_orani': 0.0})
        self.assertEqual(p['neden'], 'cok_yuz')

    def test_kesin_sabit_simge(self):
        p = self.plan(sabit(), zaman_std=std(1.0))
        self.assertEqual((p['duzen'], p['neden']), ('tek', 'sabit_simge'))

    def test_tek_sakin_kamera_tutulur(self):
        # sakin oturan gerçek kamera (std 10.8): tek kararlı yüzde göreli eleme yok
        p = self.plan(sabit(), zaman_std=std(10.8))
        self.assertEqual((p['duzen'], p['neden']), ('kamera', 'kucuk_kamera'))

    def test_goreli_sabit_avatar_elenir_ama_canli_kalir(self):
        t = [a + [(0.9, 0.2, 0.03, 0.06, .9)] for a in sabit()]
        std_ = lambda kumeler: [11.0 if c['cx'] < 0.5 else 3.0 for c in kumeler]   # noqa: E731
        self.assertEqual(self.plan(t, zaman_std=std_)['duzen'], 'kamera')
        std2 = lambda kumeler: [11.0 for _ in kumeler]   # noqa: E731
        self.assertEqual(self.plan(t, zaman_std=std2)['neden'], 'cok_yuz')

    def test_izgara_tek_panel_kalir(self):
        t = [[(0.2, 0.3, 0.05, 0.1, .9), (0.6, 0.3, 0.05, 0.1, .9), (0.2, 0.7, 0.045, 0.09, .9)] for _ in range(10)]
        self.assertEqual(self.plan(t, zaman_std=std(12.0))['neden'], 'cok_yuz')

    def test_seyrek_kamera_w003(self):
        p = self.plan(sabit(w=0.03, h=0.055))
        self.assertEqual(p['duzen'], 'kamera')

    def test_alan_siniri_kamera_buyuk(self):
        p = self.plan(sabit(w=0.12, h=0.2, cx=0.2, cy=0.3))
        self.assertEqual((p['duzen'], p['neden']), ('tek', 'kamera_buyuk'))
        self.assertNotIn('kamera_kutu', p)

    def test_esik_ayardan(self):
        p = self.plan(sabit(), ayar={'kamera_en_cok_alan': 0.001})
        self.assertEqual(p['neden'], 'kamera_buyuk')

    def test_elle_kutu_tespiti_ezer(self):
        p = self.plan([[] for _ in range(10)], elle_kutu=(0.0, 0.5, 0.25, 0.3))
        self.assertEqual((p['duzen'], p['neden'], p['kutu_kaynagi']), ('kamera', 'elle_kutu', 'elle'))

    def test_elle_kutu_gecersiz(self):
        for k in ((0.9, 0.5, 0.3, 0.3), (0, 0, 0, 0.2), 'x'):
            with self.assertRaises(kk.KameraHatasi):
                self.plan(sabit(), elle_kutu=k)

    def test_kenar_bulucu_hatasi_orantiliya_duser(self):
        def bozuk(yuz):
            raise RuntimeError('x')
        p = self.plan(sabit(), kenar_bulucu=bozuk)
        self.assertEqual((p['duzen'], p['kutu_kaynagi']), ('kamera', 'yuz'))


class KutuTesti(unittest.TestCase):
    def test_sikistir(self):
        x, y, w, h = kk.kutu_sikistir((-0.1, 0.9, 0.3, 0.3))
        self.assertGreaterEqual(x, 0)
        self.assertLessEqual(y + h, 1.0 + 1e-9)
        self.assertEqual(kk.kutu_sikistir((0, 0, 3, 3)), (0.0, 0.0, 1.0, 1.0))

    def test_gecerli(self):
        self.assertTrue(kk.kutu_gecerli((0, 0, 0.2, 0.2)))
        self.assertFalse(kk.kutu_gecerli((0.9, 0, 0.3, 0.2)))
        self.assertFalse(kk.kutu_gecerli(None))

    def test_kenara_yasla(self):
        self.assertEqual(kk.kenara_yasla((0.03, 0.55, 0.2, 0.3))[0], 0.0)
        self.assertEqual(kk.kenara_yasla((0.3, 0.3, 0.2, 0.2)), (0.3, 0.3, 0.2, 0.2))

    def test_kutuyu_yuze_sar(self):
        x, y, w, h = kk.kutuyu_yuze_sar((0.1, 0.1, 0.05, 0.05), (0.3, 0.3, 0.04, 0.08))
        self.assertTrue(x + w >= 0.32 and y + h >= 0.34)

    def test_merkez_x_sinirli(self):
        self.assertEqual(kk.merkez_x((0.05, 0.5, .1, .2), ORAN, 0.6), 0.3)
        self.assertEqual(kk.merkez_x((0.5, 0.5, .1, .2), ORAN, 1.0), 0.5)


class KirpmaTesti(unittest.TestCase):
    def test_icerik_kamerayi_disarida_birakir(self):
        kamera = (0.0, 0.56, 0.21, 0.22)
        kirp, durum = kk.icerik_kirpma(kamera, ORAN, 1080 / 590)
        self.assertEqual(durum, 'disarida')
        x, y, w, h = kirp
        self.assertGreaterEqual(x, kamera[0] + kamera[2] - 1e-6)   # kameranın sağında
        self.assertLessEqual(x + w, 1.0 + 1e-6)
        self.assertAlmostEqual(w * ORAN / h, 1080 / 590, places=2)

    def test_icerik_kamera_cok_buyukse_kapsanmis(self):
        kirp, durum = kk.icerik_kirpma((0.1, 0.1, 0.8, 0.8), ORAN, 1080 / 590)
        self.assertEqual(durum, 'kapsanmis')
        self.assertEqual(kirp, kk.tam_kirpma(ORAN, 1080 / 590))

    def test_kamera_kirpma_oran_ve_yuz(self):
        kutu, yuz = (0.0, 0.5, 0.25, 0.3), (0.1, 0.65, 0.03, 0.06)
        po = 1080 / 420
        x, y, w, h = kk.kamera_kirpma(kutu, yuz, ORAN, po)
        self.assertAlmostEqual(w * ORAN / h, po, places=2)    # bozulma yok
        self.assertTrue(kutu[0] - 1e-6 <= x and x + w <= kutu[0] + kutu[2] + 1e-6)
        self.assertTrue(kutu[1] - 1e-6 <= y and y + h <= kutu[1] + kutu[3] + 1e-6)
        self.assertTrue(y <= yuz[1] - yuz[3] / 2 and y + h >= yuz[1] + yuz[3] / 2)   # yüz kesilmez

    def test_kesim_plani_kamera_ve_merkez(self):
        plan = kk.plan_kur(sabit(), ORAN, zaman_std=std(30.0))
        k = kk.kesim_plani(plan, ORAN, 1080 / 590, 1080 / 420, 1.2)
        self.assertIn('icerik_kirpma', k)
        self.assertIn('kamera_kirpma', k)
        tek = kk.kesim_plani({'duzen': 'tek', 'neden': 'yuz_ortada', 'yuz': (0.3, 0.5, .2, .4)}, ORAN, 1.8, 2.5, 1.2)
        self.assertIn('merkez_x', tek)
        yok = kk.kesim_plani({'duzen': 'tek', 'neden': 'cok_yuz', 'yuz': None}, ORAN, 1.8, 2.5, 1.2)
        self.assertNotIn('merkez_x', yok)


class DuzenTesti(unittest.TestCase):
    def kamera_ayar(self):
        plan = kk.plan_kur(sabit(), ORAN, zaman_std=std(30.0))
        pn = yk.yerlesim({'duzen': 'kamera'})['paneller']
        plan = kk.kesim_plani(plan, ORAN, pn['icerik']['oran'], pn['kamera']['oran'], 1.2)
        return {**yk.AYAR_VARSAYILAN, 'duzen': 'kamera', '_kamera_plan': plan}

    def test_varsayilan_kamera(self):
        self.assertEqual(yk.AYAR_VARSAYILAN['duzen'], 'kamera')

    def test_yerlesim_alt_250_bos_ve_cakisma_yok(self):
        yz = yk.yerlesim({'duzen': 'kamera'})
        ic, km = yz['paneller']['icerik'], yz['paneller']['kamera']
        self.assertLessEqual(ic['y'] + ic['h'], km['y'])
        self.assertLessEqual(km['y'] + km['h'], 1920 - 250)
        y = yz['y']
        self.assertLessEqual(y['ust_oyun'] + 40, yz['gorsel_y'])
        self.assertGreaterEqual(y['alt_kaynak'], km['y'] + km['h'])
        self.assertLessEqual(y['alt_marka'] + 40, 1920 - 250)
        self.assertLess(y['ust_ad'], y['ust_oyun'])

    def test_filtre_kamera(self):
        f = yk.filtre_yaz(FONT, METIN, ayar=self.kamera_ayar())
        self.assertIn('split=3', f)
        self.assertIn('[ic]', f)
        self.assertIn('[km]', f)
        self.assertIn('[v]', f)
        self.assertEqual(f.count('crop=w=trunc'), 2)

    def test_filtre_plansiz_hata(self):
        with self.assertRaises(yk.KlipHatasi):
            yk.filtre_yaz(FONT, METIN, ayar={'duzen': 'kamera'})

    def test_eski_duzenler_etkilenmez(self):
        for d in ('kadraj', 'serit'):
            f = yk.filtre_yaz(FONT, METIN, ayar={'duzen': d})
            self.assertNotIn('split=3', f)

    def test_kadraj_merkez_x(self):
        f = yk.filtre_yaz(FONT, METIN, ayar={'duzen': 'kadraj', '_kamera_merkez_x': 0.3})
        self.assertIn('0.3000*iw-out_w/2', f)

    def test_imza(self):
        a = yk.duzen_imzasi({**yk.AYAR_VARSAYILAN, 'duzen': 'kamera'})
        self.assertEqual(a['duzen'], 'kamera')
        self.assertEqual(a['kamera_surumu'], kk.KAMERA_SURUMU)
        self.assertNotIn('kamera_surumu', yk.duzen_imzasi({**yk.AYAR_VARSAYILAN, 'duzen': 'kadraj'}))

    def test_gorsel_ayar_onbellegi_bozmaz(self):
        for k in ('duzen', 'kadraj_oran', *kk.VARSAYILAN):
            self.assertIn(k, yk.GORSEL_AYAR)

    def test_kamera_karari_hatada_kadraja_duser(self):
        with mock.patch.object(kk, 'kamera_bul', side_effect=RuntimeError('model yok')):
            ayar, bilgi = yk.kamera_karari({}, dict(yk.AYAR_VARSAYILAN), 'ffmpeg', 'k', 0, 30, False)
        self.assertEqual(ayar['duzen'], 'kadraj')
        self.assertEqual(bilgi['neden'], 'hata')

    def test_kamera_karari_kamera_plani(self):
        plan = kk.plan_kur(sabit(), ORAN, zaman_std=std(30.0))
        plan['kare_oran'] = ORAN
        with mock.patch.object(kk, 'kamera_bul', return_value=plan):
            ayar, bilgi = yk.kamera_karari({}, dict(yk.AYAR_VARSAYILAN), 'ffmpeg', 'k', 0, 30, False)
        self.assertEqual(ayar['duzen'], 'kamera')
        self.assertIn('_kamera_plan', ayar)
        self.assertEqual(bilgi['duzen'], 'kamera')


if __name__ == '__main__':
    unittest.main()
