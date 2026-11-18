"""tools/klip_derleme.py için ağ ve ffmpeg gerektirmeyen birim testleri.

Çalıştırma:  py -m unittest discover -s tests -p "test_klip_derleme.py"
"""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest

TOOLS = pathlib.Path(__file__).resolve().parents[1] / 'tools'
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import klip_derleme as kd  # noqa: E402


def ayar(**ek) -> dict:
    a = dict(kd.AYAR_VARSAYILAN)
    a.update(ek)
    return a


def aday(tur: str, i: int, deger: float, sure: float = 22.0, yayinci: str | None = None) -> dict:
    a = {'id': f'{tur}:{i}', 'tur': tur, 'deger': deger, 'kes_sure_sn': sure, 'baslik': f'{tur} başlık {i} burada',
         'kes': {'bas': 0.0, 'sure': sure, 'tepe': sure * 0.4, 'yontem': 'tam'}, 'izlenme': 1000 * (i + 1), 'tarih': '2026-11-15'}
    if tur == 'viral':
        a.update({'kanal_adi': f'Kanal{i % 5}', 'kanal_url': f'https://youtube.com/@k{i % 5}', 'url': f'https://youtube.com/shorts/v{i}'})
    else:
        y = yayinci or f'Yayıncı{i % 5}'
        a.update({'yayinci': y, 'kanal': y.lower(), 'kanal_url': f'https://kick.com/{y.lower()}',
                  'vod_url': f'https://kick.com/{y.lower()}/videos/{i:036d}', 'web_url': f'https://kick.com/{y.lower()}/clips/c{i}'})
        a['kes']['bas'] = 100.0 + i
    return a


def malzeme(kesit: int, viral: int, kesit_sure: float = 22.0, viral_sure: float = 8.0, yayinci_sayisi: int = 5) -> list[dict]:
    adaylar = [aday('yayinci' if i % 2 else 'izleyici', i, 0.95 - i * 0.01, kesit_sure, f'Yayıncı{i % yayinci_sayisi}') for i in range(kesit)]
    adaylar += [aday('viral', i, 0.9 - i * 0.005, viral_sure) for i in range(viral)]
    return adaylar


def govde(plan: dict) -> list[dict]:
    return [p for p in plan['parcalar'] if p['rol'] in ('yayinci', 'izleyici', 'viral')]


class SecimVeSiraTesti(unittest.TestCase):
    def test_sure_hedefi_ve_yapi(self):
        plan = kd.plan_olustur(malzeme(25, 60), ayar())
        self.assertGreaterEqual(plan['toplam_sn'], 600)
        self.assertLessEqual(plan['toplam_sn'], 720)
        roller = [p['rol'] for p in plan['parcalar']]
        self.assertEqual(roller[:2], ['teaser', 'teaser'])
        self.assertEqual(roller[2], 'giris')
        self.assertEqual(roller[-1], 'kapanis')
        self.assertTrue(45 <= plan['sayilar']['govde_parca'] <= 60, plan['sayilar'])

    def test_zaman_cizelgesi_ardisik(self):
        plan = kd.plan_olustur(malzeme(20, 40), ayar())
        t = 0.0
        for p in plan['parcalar']:
            self.assertAlmostEqual(p['plan_bas_sn'], t, places=1)
            t += p['sure_sn']
        self.assertAlmostEqual(plan['toplam_sn'], t, places=1)

    def test_dongu_bir_kesit_iki_viral(self):
        plan = kd.plan_olustur(malzeme(10, 40), ayar(yayinci_basina_viral=2, viral_dolgu=False))
        g = govde(plan)
        # her döngü: kesit ardından en çok 2 viral
        i, n_dongu = 0, 0
        while i < len(g):
            self.assertIn(g[i]['rol'], ('yayinci', 'izleyici'))
            j = i + 1
            while j < len(g) and g[j]['rol'] == 'viral':
                j += 1
            self.assertEqual(j - i - 1, 2, f'döngü {n_dongu}')
            i, n_dongu = j, n_dongu + 1

    def test_viral_dolgu_kesit_bitince_viral_ile_doldurur(self):
        kapali = kd.plan_olustur(malzeme(6, 80), ayar(viral_dolgu=False))
        acik = kd.plan_olustur(malzeme(6, 80), ayar(viral_dolgu=True))
        self.assertEqual(kapali['sayilar']['viral'], 12)
        self.assertGreater(acik['sayilar']['viral'], 12)
        self.assertGreater(acik['toplam_sn'], kapali['toplam_sn'])

    def test_oran_ayardan_degisir(self):
        plan = kd.plan_olustur(malzeme(10, 40), ayar(yayinci_basina_viral=1))
        g = govde(plan)
        self.assertEqual([p['rol'] != 'viral' for p in g[:4]], [True, False, True, False])
        plan0 = kd.plan_olustur(malzeme(10, 40), ayar(yayinci_basina_viral=0))
        self.assertEqual(plan0['sayilar']['viral'], 0)

    def test_en_iyi_basa_ikinci_en_iyi_sona(self):
        plan = kd.plan_olustur(malzeme(20, 40), ayar())
        kesitler = [p['aday'] for p in govde(plan) if p['rol'] != 'viral']
        deg = sorted((a['deger'] for a in kesitler), reverse=True)
        self.assertEqual(kesitler[0]['deger'], deg[0])
        self.assertEqual(kesitler[-1]['deger'], deg[1])

    def test_ayni_yayinci_art_arda_gelmez(self):
        plan = kd.plan_olustur(malzeme(20, 40, yayinci_sayisi=4), ayar())
        kesitler = [p['aday'] for p in govde(plan) if p['rol'] != 'viral']
        for a, b in zip(kesitler, kesitler[1:]):
            self.assertNotEqual(a['yayinci'], b['yayinci'])
        self.assertFalse([u for u in plan['uyarilar'] if 'art arda' in u])

    def test_teaser_en_iyi_iki_aday(self):
        plan = kd.plan_olustur(malzeme(20, 40), ayar())
        teaser = [p for p in plan['parcalar'] if p['rol'] == 'teaser']
        self.assertEqual(len(teaser), 2)
        self.assertTrue(all(p['sure_sn'] == 2.0 for p in teaser))
        en_iyi = sorted((p['aday']['deger'] for p in govde(plan)), reverse=True)[:2]
        self.assertEqual(sorted((p['aday']['deger'] for p in teaser), reverse=True), en_iyi)

    def test_tekrar_kullanmama_ayni_derlemede(self):
        plan = kd.plan_olustur(malzeme(25, 60), ayar())
        idler = [p['aday']['id'] for p in govde(plan)]
        self.assertEqual(len(idler), len(set(idler)))

    def test_onceki_derlemede_kullanilan_elenir_ve_sayi_artar(self):
        adaylar = malzeme(6, 6)
        durum = {'seri': {}, 'kullanilan': {}}
        self.assertEqual(kd.sonraki_sayi(durum, 'Yayın Kolajı'), 1)
        plan = kd.plan_olustur(adaylar, ayar(sure_dk=3, sure_min_dk=2, sure_max_dk=4))
        kd.kullanilanlari_isle(durum, 'Yayın Kolajı', 1, 'yayin-kolaji-1', [p for p in plan['parcalar'] if p['aday']])
        self.assertEqual(kd.sonraki_sayi(durum, 'Yayın Kolajı'), 2)
        kalan, elenen = kd.kullanilanlari_ele(adaylar, durum)
        kullanilan = {p['aday']['id'] for p in govde(plan)}
        self.assertTrue(kullanilan)
        self.assertTrue(all(a['id'] not in kullanilan for a in kalan))
        self.assertEqual({e['id'] for e in elenen}, kullanilan)
        plan2 = kd.plan_olustur(kalan, ayar(sure_dk=3, sure_min_dk=2, sure_max_dk=4))
        self.assertFalse(kullanilan & {p['aday']['id'] for p in govde(plan2)})

    def test_durum_dosyasi_gidis_donus(self):
        with tempfile.TemporaryDirectory() as d:
            dizin = pathlib.Path(d)
            self.assertEqual(kd.durum_oku(dizin), {'seri': {}, 'kullanilan': {}})
            kd.durum_yaz(dizin, {'seri': {'yayin-kolaji': {'ad': 'Yayın Kolajı', 'son_sayi': 4}}, 'kullanilan': {'x': {'derleme': 'a'}}})
            durum = kd.durum_oku(dizin)
            self.assertEqual(kd.sonraki_sayi(durum, 'Yayın Kolajı'), 5)
            self.assertIn('x', durum['kullanilan'])


class EksikKaynaktaGeriDusmeTesti(unittest.TestCase):
    def test_viral_yoksa_yalniz_yayinci_kesitiyle_derleme(self):
        plan = kd.plan_olustur(malzeme(30, 0), ayar(), turler=('yayinci', 'izleyici'))
        self.assertEqual(plan['sayilar']['viral'], 0)
        self.assertGreaterEqual(plan['toplam_sn'], 600)
        self.assertLessEqual(plan['toplam_sn'], 720)

    def test_viral_adaylari_var_ama_tur_kisitli(self):
        plan = kd.plan_olustur(malzeme(30, 30), ayar(), turler=('yayinci', 'izleyici'))
        self.assertEqual(plan['sayilar']['viral'], 0)

    def test_kesit_yoksa_yalniz_viral_dolgu(self):
        plan = kd.plan_olustur(malzeme(0, 80, viral_sure=10.0), ayar())
        self.assertEqual(plan['sayilar']['yayinci'] + plan['sayilar']['izleyici'], 0)
        self.assertGreater(plan['sayilar']['viral'], 40)
        self.assertGreaterEqual(plan['toplam_sn'], 600)

    def test_malzeme_yetmezse_uyari_ve_eldekiyle_devam(self):
        plan = kd.plan_olustur(malzeme(3, 4), ayar())
        self.assertTrue(any('malzeme yetmedi' in u for u in plan['uyarilar']), plan['uyarilar'])
        self.assertEqual(plan['sayilar']['govde_parca'], 7)
        self.assertEqual(plan['parcalar'][-1]['rol'], 'kapanis')

    def test_viral_az_ise_uyari(self):
        plan = kd.plan_olustur(malzeme(10, 5), ayar())
        self.assertTrue(any('viral yetmedi' in u for u in plan['uyarilar']), plan['uyarilar'])

    def test_hic_aday_yok_cokmez(self):
        plan = kd.plan_olustur([], ayar())
        self.assertEqual([p['rol'] for p in plan['parcalar']], ['giris', 'kapanis'])

    def test_hedef_sure_degisir(self):
        kisa = kd.plan_olustur(malzeme(25, 60), ayar(), hedef_sn=300)
        self.assertLessEqual(kisa['toplam_sn'], 310)
        self.assertGreater(kisa['toplam_sn'], 250)


class OrtusmeVeKopyaTesti(unittest.TestCase):
    def _a(self, i, tur, bas, bit, deger=0.5):
        a = aday(tur, i, deger)
        a['epoch_bas'], a['epoch_bit'] = bas, bit
        return a

    def test_ortusen_izleyici_klibi_elenir_paket_kalir(self):
        paket = self._a(1, 'yayinci', 1000.0, 1022.0, 0.4)
        klip = self._a(2, 'izleyici', 1010.0, 1032.0, 0.9)
        uzak = self._a(3, 'izleyici', 5000.0, 5020.0, 0.3)
        kalan, elenen, _ = kd.ortusenleri_ele([paket, klip, uzak], 5.0)
        self.assertEqual({a['id'] for a in kalan}, {paket['id'], uzak['id']})
        self.assertEqual(elenen[0]['neden'], 'ortusme')

    def test_kucuk_ortusme_esigin_altinda_kalir(self):
        a, b = self._a(1, 'izleyici', 1000.0, 1022.0), self._a(2, 'izleyici', 1020.0, 1042.0)
        kalan, elenen, _ = kd.ortusenleri_ele([a, b], 5.0)
        self.assertEqual(len(kalan), 2)
        self.assertEqual(elenen, [])

    def test_zamani_bilinmeyen_elenmez_ve_sayilir(self):
        a = aday('izleyici', 1, 0.5)
        a['epoch_bas'] = a['epoch_bit'] = None
        b = aday('yayinci', 2, 0.5)
        kalan, elenen, belirsiz = kd.ortusenleri_ele([a, b], 5.0)
        self.assertEqual(len(kalan), 2)
        self.assertEqual(belirsiz, 2)

    def test_kopyalar_yuksek_degerle_tek_kalir(self):
        a, b = aday('viral', 1, 0.3), aday('viral', 1, 0.8)
        kalan, kopya = kd.kopyalari_ele([a, b])
        self.assertEqual(kalan, [b])
        self.assertEqual(kopya[0]['neden'], 'kopya')


class KesitKisaltmaTesti(unittest.TestCase):
    def klip(self, kb=1000.0, ke=1060.0, **ek):
        return {'klip_baslangic_sn': kb, 'klip_bitis_sn': ke, **ek}

    def test_kisa_klip_oldugu_gibi_kalir(self):
        k = kd.kesit_araligi(self.klip(1000, 1020), ayar())
        self.assertEqual((k['bas'], k['bit'], k['yontem']), (1000.0, 1020.0, 'tam'))

    def test_uzun_klip_hedef_surede_kesilir_ve_aralik_icinde(self):
        k = kd.kesit_araligi(self.klip(1000, 1060, dalga_basi_sn=1030), ayar())
        self.assertAlmostEqual(k['sure'], 22.0, places=1)
        self.assertGreaterEqual(k['bas'], 1000.0)
        self.assertLessEqual(k['bit'], 1060.0)
        self.assertAlmostEqual(k['bas'], 1022.0, places=1)           # dalga başlangıcından 8 sn önce
        self.assertAlmostEqual(k['tepe'], 8.0, places=1)

    def test_kenarlara_tasmaz(self):
        bas = kd.kesit_araligi(self.klip(1000, 1060, dalga_basi_sn=1002), ayar())
        self.assertEqual(bas['bas'], 1000.0)
        son = kd.kesit_araligi(self.klip(1000, 1060, dalga_basi_sn=1059), ayar())
        self.assertEqual(son['bit'], 1060.0)

    def test_sure_min_max_araliginda(self):
        for dalga in (1001, 1015, 1030, 1050, 1059):
            for ke in (1040, 1050, 1070, 1100):
                k = kd.kesit_araligi(self.klip(1000, ke, dalga_basi_sn=dalga), ayar())
                self.assertGreaterEqual(k['sure'], 12.0 - 1e-6, (dalga, ke, k))
                self.assertLessEqual(k['sure'], 28.0 + 1e-6, (dalga, ke, k))

    def test_dalga_yoksa_zirveye_dayanir(self):
        k = kd.kesit_araligi(self.klip(1000, 1060, zirve_sn=1040), ayar())
        self.assertAlmostEqual(k['bas'], 1032.0, places=1)

    def test_cumle_sinirina_oturur_ama_azami_asmaz(self):
        k = kd.kesit_araligi(self.klip(1000, 1060, dalga_basi_sn=1030,
                                       cumleler=[{'bas': 1020.0, 'bit': 1024.0}, {'bas': 1040.0, 'bit': 1046.0}]), ayar())
        self.assertAlmostEqual(k['bas'], 1020.0, places=1)            # 1022 -> cümle başı 1020
        self.assertLessEqual(k['sure'], 28.0)
        self.assertIn('cumle', k['yontem'])

    def test_izleyici_kisa_tam_uzun_kirpilir(self):
        self.assertEqual(kd.izleyici_araligi(20.0, ayar())['sure'], 20.0)
        uzun = kd.izleyici_araligi(55.0, ayar())
        self.assertEqual(uzun['sure'], 22.0)
        self.assertGreater(uzun['bas'], 0)
        self.assertEqual(kd.izleyici_araligi(55.0, ayar(izleyici_konum='bas'))['bas'], 0.0)
        self.assertEqual(kd.izleyici_araligi(55.0, ayar(izleyici_uzun='tam'))['sure'], 55.0)

    def test_viral_araligi(self):
        self.assertEqual(kd.viral_araligi(9.0, ayar(), 'ele')['sure'], 9.0)
        self.assertIsNone(kd.viral_araligi(40.0, ayar(), 'ele'))
        self.assertEqual(kd.viral_araligi(40.0, ayar(), 'kirp')['sure'], 15.0)


class BaslikVeAciklamaTesti(unittest.TestCase):
    def parcalar(self, n=14, viral_n=28):
        plan = kd.plan_olustur(malzeme(n, viral_n), ayar())
        return plan, [{'rol': p['rol'], 'aday': p['aday'], 'bas_sn': p['plan_bas_sn']} for p in govde(plan)]

    def test_zaman_ve_buyuk_harf(self):
        self.assertEqual(kd.zaman_m(0), '0:00')
        self.assertEqual(kd.zaman_m(75), '1:15')
        self.assertEqual(kd.zaman_m(3725), '1:02:05')
        self.assertEqual(kd.tr_buyuk('istanbul ışık'), 'İSTANBUL IŞIK')

    def test_baslik_bicimi(self):
        a = aday('izleyici', 1, 0.9)
        a['baslik'] = 'Madara olduk ilginç an'
        s = kd.baslik_sec([{'rol': 'izleyici', 'aday': a}], ayar(), 7, sablonlar=[])
        self.assertEqual(s['baslik'], 'MADARA OLDUK İLGİNÇ AN | Yayın Kolajı #7')
        self.assertLessEqual(len(s['baslik']), 100)

    def test_sablon_baslik_en_son_care(self):
        # gerçek (konuşma/izleyici) başlığı yoksa eski şablon, yayıncı parçasından, en son çare olarak kullanılır
        a = aday('yayinci', 1, 0.9)
        a['baslik'] = 'Eraycan yayınında chat kahkahaya boğuldu'
        s = kd.baslik_sec([{'rol': 'yayinci', 'aday': a}], ayar(), 2, sablonlar=[])
        self.assertEqual(s['neden'], 'eski_sablon_yayinci')
        self.assertEqual(s['olay'], 'ERAYCAN YAYININDA CHAT KAHKAHAYA BOĞULDU')
        self.assertTrue(s['baslik'].endswith('| Yayın Kolajı #2'))
        # yayıncı yoksa genel başlık
        v = aday('viral', 2, 0.9)
        v['baslik'] = 'Eraycan yayınında chat kahkahaya boğuldu'
        g = kd.baslik_sec([{'rol': 'viral', 'aday': v}], ayar(), 2, sablonlar=[])
        self.assertEqual(g['olay'], 'EN ÇOK KONUŞULAN ANLAR')

    def test_uzun_baslik_sinira_kesilir(self):
        a = aday('viral', 1, 0.9)
        a['baslik'] = 'kelime ' * 40
        s = kd.baslik_sec([{'rol': 'viral', 'aday': a}], ayar(), 12, sablonlar=[])
        self.assertLessEqual(len(s['baslik']), 100)

    def test_bolumler_ilk_sifir_ve_en_az_on_saniye(self):
        _, z = self.parcalar()
        b = kd.bolum_listesi(z)
        self.assertEqual(b[0][0], 0.0)
        for (t0, _), (t1, _) in zip(b, b[1:]):
            self.assertGreaterEqual(t1 - t0, 10.0)
        self.assertGreaterEqual(len(b), 3)

    def test_aciklama_icerigi(self):
        plan, z = self.parcalar()
        s = kd.aciklama_uret(z, ayar(), 3, 'BAŞLIK | Yayın Kolajı #3')
        self.assertIn('Bölümler:', s)
        self.assertIn('0:00 Giriş', s)
        self.assertIn('https://kick.com/yayıncı0', s)                       # yayıncı bağlantısı
        yk = next(p for p in z if p['rol'] == 'yayinci')['aday']
        self.assertIn(yk['vod_url'], s)                                        # kesitin kaynağı
        ik = next(p for p in z if p['rol'] == 'izleyici')['aday']
        self.assertIn(ik['web_url'], s)
        vr = next(p for p in z if p['rol'] == 'viral')['aday']
        self.assertIn(vr['url'], s)                                            # viral kaynağı
        self.assertIn(kd.zaman_m(next(p for p in z if p['rol'] == 'yayinci')['bas_sn']), s)

    def test_aciklama_youtube_sinirini_asmaz(self):
        _, z = self.parcalar(30, 120)
        for p in z:
            p['aday']['baslik'] = 'çok uzun başlık ' * 5
        s = kd.aciklama_uret(z, ayar(), 3, 'B')
        self.assertLessEqual(len(s), 5000)

    def test_yalniz_viral_derleme_aciklamasi(self):
        plan = kd.plan_olustur(malzeme(0, 70, viral_sure=10.0), ayar())
        z = [{'rol': p['rol'], 'aday': p['aday'], 'bas_sn': p['plan_bas_sn']} for p in govde(plan)]
        s = kd.aciklama_uret(z, ayar(), 1, 'B')
        self.assertIn('Viral videolar', s)
        self.assertGreaterEqual(len(kd.bolum_listesi(z)), 3)


class FiltreVeAdTesti(unittest.TestCase):
    def test_yatay_dogrudan_olceklenir(self):
        f = kd.video_filtresi(1920, 1080, ayar(), 'C:/Windows/Fonts/arialbd.ttf', True, 20.0)
        self.assertNotIn('gblur', f)
        self.assertIn('scale=1920:1080', f)
        self.assertIn("t_filigran.txt", f)
        self.assertIn("enable='lt(t,3.0)'", f)

    def test_dikey_bulanik_arka_planla_ortalanir(self):
        f = kd.video_filtresi(1080, 1920, ayar(), 'C:/Windows/Fonts/arialbd.ttf', False, 9.0)
        self.assertIn('gblur', f)
        self.assertIn('overlay=(W-w)/2:(H-h)/2', f)
        self.assertNotIn('t_etiket.txt', f)

    def test_font_yolu_kacisi(self):
        self.assertEqual(kd._fe('C:\\Windows\\Fonts\\a.ttf'), 'C\\:/Windows/Fonts/a.ttf')

    def test_parca_adi_kararli_ve_guvenli(self):
        a = aday('yayinci', 1, 0.5)
        a['id'] = 'paket:eraycan-2026/klip-01'
        self.assertEqual(kd.parca_adi(a), kd.parca_adi(dict(a)))
        self.assertRegex(kd.parca_adi(a), r'^[A-Za-z0-9._-]+$')
        b = dict(a, id='paket:eraycan-2026/klip-02')
        self.assertNotEqual(kd.parca_adi(a), kd.parca_adi(b))

    def test_etiket_metni(self):
        y = aday('yayinci', 1, 0.5, yayinci='Eraycan')
        self.assertIn('Eraycan', kd.etiket_metni(y, ayar()))
        self.assertIsNone(kd.etiket_metni(aday('viral', 1, 0.5), ayar()))
        self.assertIsNotNone(kd.etiket_metni(aday('viral', 1, 0.5), ayar(viral_etiketi=True)))

    def test_deger_izlenme_artan_ve_sinirli(self):
        self.assertEqual(kd.deger_izlenme(0, 300), 0.0)
        d = [kd.deger_izlenme(n, 300) for n in (1, 10, 100, 300, 10000)]
        self.assertEqual(d, sorted(d))
        self.assertEqual(d[-1], 1.0)

    def test_ayar_dosyasi_okunur_ve_varsayilanla_birlesir(self):
        with tempfile.TemporaryDirectory() as t:
            yol = pathlib.Path(t) / 'a.json'
            yol.write_text(json.dumps({'ayar': {'seri_adi': 'Deneme', 'sure_dk': 9}}), encoding='utf-8')
            a = kd.ayar_yukle_d(yol)
            self.assertEqual(a['seri_adi'], 'Deneme')
            self.assertEqual(a['fps'], kd.AYAR_VARSAYILAN['fps'])
            yol.write_text('{bozuk', encoding='utf-8')
            with self.assertRaises(kd.DerlemeHatasi):
                kd.ayar_yukle_d(yol)

    def test_repodaki_ayar_dosyasi_gecerli(self):
        a = kd.ayar_yukle_d(kd.AYAR_DOSYASI)
        self.assertLessEqual(a['sure_min_dk'], a['sure_dk'])
        self.assertLessEqual(a['sure_dk'], a['sure_max_dk'])


class TurkceVeKaynakSuzgeciTesti(unittest.TestCase):
    """Derleme düzeltmeleri (2. tur): Shorts Türkçe süzgeci, kanal üst sınırı, eleme kayıtları."""
    KESIM = None

    def _viral(self, baslik, dil=None, sure=10.0, izlenme=2_000_000, kanal='Kanal', **ek):
        d = {'id': 'v' + str(abs(hash(baslik)) % 99999), 'title': baslik, 'duration': sure, 'view_count': izlenme,
             'channel': kanal, 'upload_date': '20261116', 'availability': 'public'}
        if dil is not None:
            d['language'] = dil
        d.update(ek)
        return d

    def _neden(self, d, **ayar_ek):
        return kd.viral_ele_nedeni(d, ayar(**ayar_ek), None, 'ele')

    def test_yabanci_ve_etiket_yigini_elenir(self):
        self.assertEqual(self._neden(self._viral('초콜릿으로 진짜부자 구별하는법🤙🤪🤙')), 'baslik_latin_disi')
        self.assertEqual(self._neden(self._viral("How a Spider Bite Can Change Your Family's Destiny", kanal='Carlos Reig')),
                         'turkce_izi_yok')
        self.assertIn(self._neden(self._viral('#funny #comedy #challenge #memes #family', kanal='Bro Mode ON')),
                      ('turkce_izi_yok', 'baslik_cok_az_kelime'))

    def test_turkce_baslik_gecer(self):
        self.assertIsNone(self._neden(self._viral('Köpeğe rüşvet verdiler 🐶😂', kanal='Bir Mesele Var', sure=14.0)))
        self.assertIsNone(self._neden(self._viral('Tavşan Dağa Küsmüş', kanal='Malafaith', sure=5.0)))

    def test_dil_alani_once_gelir(self):
        self.assertEqual(self._neden(self._viral('Köpeğe rüşvet verdiler', dil='en')), 'dil_turkce_degil')
        self.assertIsNone(self._neden(self._viral('Bro mode on always', dil='tr')))

    def test_elle_secilen_turkce_suzgecine_girmez(self):
        d = self._viral('How a Spider Bite Can Change', kanal='Carlos')
        self.assertIsNone(kd.viral_ele_nedeni(d, ayar(), None, 'kirp', serbest=True))

    def test_turkce_suzgeci_kapatilabilir(self):
        d = self._viral('How a Spider Bite Can Change', kanal='Carlos')
        self.assertIsNone(self._neden(d, viral_turkce_sart=False))

    def test_etiketler_atilinca_kelime_sayisi(self):
        self.assertEqual(kd.kelime_sayisi('#komik #komedi #kedi'), 0)
        self.assertEqual(kd.kelime_sayisi('Kandıramadı🦁🐈 fear😹#komik'), 2)
        self.assertEqual(kd.kelime_sayisi('😂😂'), 0)

    def test_latin_disi_tespiti(self):
        self.assertTrue(kd.latin_disi_mi('초콜릿 abc'))
        self.assertTrue(kd.latin_disi_mi('Привет'))
        self.assertFalse(kd.latin_disi_mi('Şişli ığdır ÖZGÜR çok'))

    def test_shorts_ayni_kanal_en_cok_iki_ve_kayit(self):
        simdi = kd.datetime(2026, 11, 18, tzinfo=kd.timezone.utc)
        videolar = {f'v{i}': self._viral(f'Bir komik olay çok {i}', dil='tr', kanal='Tek Kanal', id=f'v{i}') for i in range(4)}
        videolar['x'] = self._viral('Bir komik olay başka kanal', dil='tr', kanal='Diğer', id='x')
        liste = [{'id': k, 'view_count': v['view_count'], 'title': v['title'], 'duration': v['duration']} for k, v in videolar.items()]
        rapor: dict = {}
        ayr = ayar(shorts_kaynaklari=[{'ad': 't', 'tur': 'etiket', 'hedef': 'komik', 'kac': 5}], viral_kanal_ust=2)
        sonuc = kd.shorts_topla(ayr, simdi, rapor, None, liste_al=lambda k: liste, detay_al=lambda url: videolar[url.split('=')[-1]])
        self.assertEqual(len(sonuc), 3)
        self.assertEqual(sum(1 for a in sonuc if a['kanal_adi'] == 'Tek Kanal'), 2)
        elenen = rapor['elenen_adaylar']
        # aynı kanaldan 4 video: 2'si kabul, 2'si 'kanal_ust' olarak kayda geçer
        self.assertEqual([e['neden'] for e in elenen if e['neden'] == 'kanal_ust'], ['kanal_ust', 'kanal_ust'])

    def test_izleyici_eleme_kanal_bazinda_yazilir(self):
        klip = {'id': 'k1', 'privacy': 'public', 'clip_url': 'https://x/k1.mp4', 'duration': 20, 'views': 2, 'title': 'ss',
                'created_at': '2026-11-17 10:00:00'}
        rapor: dict = {}
        kanallar = [('kanalA', 'Yayıncı A')]
        kd.izleyici_topla(ayar(), kanallar, 7, 0.0, rapor, json_al=lambda url: {'clips': [klip], 'nextCursor': None},
                          pdt_al=lambda url: None)
        self.assertEqual(rapor['izleyici']['kanal']['kanalA']['elenen'], {'dusuk_izlenme': 1})
        self.assertEqual(rapor['elenen_adaylar'][0]['id'], 'kick-klip:k1')

    def test_yayinci_basina_izleyici_ve_toplam_ust_siniri(self):
        adaylar = [aday('izleyici', i, 0.9 - i * 0.01, 22.0, 'Tek') for i in range(6)]
        adaylar += [aday('yayinci', 10 + i, 0.5 - i * 0.01, 22.0, 'Tek') for i in range(6)]
        adaylar += [aday('izleyici', 30, 0.2, 22.0, 'Diger'), aday('yayinci', 31, 0.2, 22.0, 'Diger')]
        adaylar += [aday('viral', i, 0.6 - i * 0.01) for i in range(20)]
        plan = kd.plan_olustur(adaylar, ayar(izleyici_kanal_ust=2, yayinci_toplam_ust=3, viral_dolgu=True))
        kesit = [p['aday'] for p in govde(plan) if p['rol'] in ('yayinci', 'izleyici')]
        tek = [a for a in kesit if a['yayinci'] == 'Tek']
        self.assertLessEqual(len(tek), 3)
        self.assertLessEqual(sum(1 for a in tek if a['tur'] == 'izleyici'), 2)
        self.assertTrue(any(a['yayinci'] == 'Diger' for a in kesit))
        self.assertIn('izleyici_kanal_ust', {e['neden'] for e in plan['ust_elenen']})
        self.assertIn('yayinci_toplam_ust', {e['neden'] for e in plan['ust_elenen']})

    def test_teaser_yayinci_iceriginden(self):
        adaylar = malzeme(8, 6) + [aday('viral', 99, 0.999)]
        plan = kd.plan_olustur(adaylar, ayar())
        teaser = [p for p in plan['parcalar'] if p['rol'] == 'teaser']
        self.assertTrue(teaser)
        self.assertTrue(all(p['aday']['tur'] in ('yayinci', 'izleyici') for p in teaser))

    def test_teaser_yayinci_yoksa_viral(self):
        plan = kd.plan_olustur([aday('viral', i, 0.9 - i * 0.01) for i in range(10)], ayar())
        teaser = [p for p in plan['parcalar'] if p['rol'] == 'teaser']
        self.assertTrue(all(p['aday']['tur'] == 'viral' for p in teaser))


class PaketOnceligiVeKesitTesti(unittest.TestCase):
    def test_paket_turu(self):
        self.assertEqual(kd.paket_turu('konusma-hizali-01'), 'konusma-hizali')
        self.assertEqual(kd.paket_turu('konusma-ek-patates'), 'konusma')
        self.assertEqual(kd.paket_turu('konusma-01'), 'konusma')
        self.assertEqual(kd.paket_turu('canli-02'), 'canli')
        self.assertEqual(kd.paket_turu('klip-03'), 'klip')

    def _p(self, i, turu, bas, bit, deger, vod='u1'):
        return {'id': f'paket:{i}', 'vod_uuid': vod, 'klip_baslangic_sn': bas, 'klip_bitis_sn': bit, 'deger': deger,
                'paket_turu': turu, 'baslik': f'b{i}'}

    def test_ortusende_konusma_kalir_klip_elenir(self):
        klip = self._p(1, 'klip', 100.0, 140.0, 0.9)
        konusma = self._p(2, 'konusma-hizali', 105.0, 130.0, 0.4)
        kalan, elenen = kd.paket_ortusmesini_ele([klip, konusma], 5.0)
        self.assertEqual([a['id'] for a in kalan], ['paket:2'])
        self.assertEqual(elenen[0]['id'], 'paket:1')
        self.assertEqual(elenen[0]['neden'], 'paket_ortusme')

    def test_farkli_yayin_ve_kucuk_ortusme_korunur(self):
        a = self._p(1, 'klip', 100.0, 140.0, 0.9, vod='u1')
        b = self._p(2, 'klip', 100.0, 140.0, 0.8, vod='u2')
        c = self._p(3, 'klip', 138.0, 160.0, 0.7, vod='u1')    # 2 sn örtüşme < 5 sn eşik
        kalan, elenen = kd.paket_ortusmesini_ele([a, b, c], 5.0)
        self.assertEqual(len(kalan), 3)
        self.assertEqual(elenen, [])

    def test_konusma_kesiti_model_araligi_basindan(self):
        klip = {'klip_baslangic_sn': 585.95, 'klip_bitis_sn': 623.36, 'zirve_sn': 604.655, 'konusma_puani': 7}
        k = kd.kesit_araligi(klip, ayar())
        self.assertEqual(k['yontem'], 'konusma_bas')
        self.assertEqual(k['bas'], 585.95)
        self.assertEqual(k['sure'], 22.0)

    def test_kisa_konusma_paketi_oldugu_gibi(self):
        klip = {'klip_baslangic_sn': 100.0, 'klip_bitis_sn': 120.0, 'zirve_sn': 110.0, 'konusma_puani': 3}
        k = kd.kesit_araligi(klip, ayar())
        self.assertEqual((k['bas'], k['bit']), (100.0, 120.0))


class BaslikKaynagiTesti(unittest.TestCase):
    def _b(self, tur, i, deger, baslik, izlenme=1000, turu=None):
        a = aday(tur, i, deger)
        a['baslik'] = baslik
        a['izlenme'] = izlenme
        if turu:
            a['paket_turu'] = turu
        return {'rol': tur, 'aday': a}

    def test_anlamsiz_baslik(self):
        for t in ('ss', 'zzz', 'QWEQWEEWQWEQWEQ'):
            self.assertTrue(kd.anlamsiz_baslik(t), t)
        self.assertFalse(kd.anlamsiz_baslik('Madara olduk ilginç an'))

    def test_konusma_basligi_once_viral_asla(self):
        parcalar = [self._b('viral', 1, 0.99, 'Kandıramadı FEAR kedi videosu', 10**7),
                    self._b('yayinci', 2, 0.5, "Takım B'ye saldıran rakiplerin koşarak vurmasına isyan ediyor", 0, 'konusma'),
                    self._b('izleyici', 3, 0.4, 'QWEQWEEWQWEQWEQ', 9_000_000)]
        s = kd.baslik_sec(parcalar, ayar(), 1, sablonlar=[])
        self.assertEqual(s['neden'], 'konusma_katmani')
        self.assertTrue(s['olay'].startswith("TAKIM B'YE"))
        self.assertNotIn('KANDIRAMADI', s['baslik'])

    def test_anlamsiz_izleyici_basligi_secilmez(self):
        parcalar = [self._b('izleyici', 1, 0.9, 'ss', 9_000_000),
                    self._b('izleyici', 2, 0.5, 'Madara olduk ilginç an', 500)]
        s = kd.baslik_sec(parcalar, ayar(), 1, sablonlar=[])
        self.assertEqual(s['neden'], 'en_cok_izlenen_izleyici_klibi')
        self.assertEqual(s['olay'], 'MADARA OLDUK İLGİNÇ AN')

    def test_yalniz_anlamsiz_izleyici_sablon_yedegi(self):
        parcalar = [self._b('izleyici', 1, 0.9, 'zzz', 9_000_000),
                    self._b('izleyici', 2, 0.5, 'Kemalcan Parlak yayınında sohbet bir anda gülmeye başladı', 100)]
        s = kd.baslik_sec(parcalar, ayar(), 1)
        self.assertEqual(s['neden'], 'eski_sablon_izleyici')
        self.assertNotIn('ZZZ', s['olay'])

    def test_viral_yalniz_yayinci_yoksa(self):
        s = kd.baslik_sec([self._b('viral', 1, 0.9, 'Madara olduk ilginç an', 10**6)], ayar(), 1, sablonlar=[])
        self.assertEqual(s['neden'], 'viral_yedek')
        parcalar = [self._b('viral', 1, 0.9, 'Madara olduk ilginç an', 10**6),
                    self._b('izleyici', 2, 0.1, 'zzz', 100)]
        s2 = kd.baslik_sec(parcalar, ayar(), 1, sablonlar=[])
        self.assertNotEqual(s2['neden'], 'viral_yedek')


class AnlamliBaslikTesti(unittest.TestCase):
    def test_bosluk_ve_kisa_baslik_anlamli_degil(self):
        self.assertFalse(kd.anlamli_mi('ss'))
        self.assertFalse(kd.anlamli_mi(None))
        self.assertTrue(kd.anlamli_mi('Eraycan yayınında chat kahkahaya boğuldu'))


if __name__ == '__main__':
    unittest.main()
