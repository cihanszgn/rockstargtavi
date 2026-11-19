import json
import unittest
from unittest.mock import patch

from test_sosyal_yayinla import Temel, haber, ayar, SIRLAR, SIMDI, BUGUN, SahteAg, YasakAg
import sosyal_yayinla as sy
import video_site as vs


class GlobalInstagram(Temel):
    def ayar(self, **hesap):
        a = ayar(**hesap)
        a['hesaplar']['tr']['instagram_icerik'] = {'ana': 'en', 'ikinci': 'tr'}
        return a

    def haber(self):
        x = haber()
        x['otomasyon']['hype'] = 7
        x['diller']['en'].update(baslik='English title', ozet='English summary.',
                                 etiketler=['#Game', '#Patch', '#Shared'])
        x['diller']['tr'].update(baslik='Türkçe başlık', ozet='Türkçe özet.',
                                 etiketler=['#Oyun', '#Yama', '#shared', 'geçersiz'])
        return x

    def plan(self, a, x=None):
        satirlar, secilen = [], []
        sy.calistir(a, [x or self.haber()], kayit_yolu=self.kayit, manifest_yolu=self.manifest,
                    tum=SIRLAR, ag=YasakAg(), dry_run=True, bugun=BUGUN, simdi=SIMDI,
                    cikti=satirlar.append, secildi=lambda k, r: secilen.append((k, r)))
        return '\n'.join(satirlar), secilen

    def test_iki_dilli_aciklama_sirasi_cagri_ve_etiketler(self):
        x = self.haber()
        m = sy.ig_aciklama('tr', x, self.ayar())
        self.assertTrue(m.startswith('English title\n\nEnglish summary.\n\n---\n\nTürkçe başlık\n\nTürkçe özet.'))
        self.assertIn(sy.METIN['en']['devam'], m)
        self.assertIn(sy.paylasim_linki('en', x, 'instagram'), m)
        self.assertTrue(m.endswith('#Oyun #Game #Patch #GamingNews #Gaming'))

    def test_ikinci_dil_yoksa_aciklama_yalniz_ingilizce_kaynak_adi_yalin(self):
        x, a = self.haber(), self.ayar()
        a['hesaplar']['tr']['instagram_icerik'] = {'ana': 'en'}
        x['kaynaklar'][0]['ad'] = 'Steam resmî duyurusu'
        m = sy.ig_aciklama('tr', x, a)
        self.assertTrue(m.startswith('English title\n\nEnglish summary.\n\nSource: Steam\n'))
        for turkce in ('Türkçe', '---', 'resmî', '#Yama'):
            self.assertNotIn(turkce, m)

    def test_kaynak_adi_turkcede_aynen_baska_dilde_yalin(self):
        ad = sy.kaynak_adi
        self.assertEqual(ad('tr', 'Steam resmî duyurusu'), 'Steam resmî duyurusu')
        self.assertEqual(ad('en', 'Selaco — Steam resmî duyurusu'), 'Selaco')
        self.assertEqual(ad('en', 'Nintendo (resmî duyuru)'), 'Nintendo')
        self.assertEqual(ad('en', 'World of Warcraft (Blizzard)'), 'World of Warcraft (Blizzard)')

    def test_2200_sinirinda_once_ikinci_dilin_cumleleri_kisalir(self):
        x = self.haber()
        x['diller']['en']['ozet'] = 'English sentence. ' * 60
        x['diller']['tr']['ozet'] = 'Türkçe cümle. ' * 100
        m = sy.ig_aciklama('tr', x, self.ayar())
        self.assertLessEqual(len(m), 2200)
        self.assertIn(x['diller']['en']['ozet'].strip(), m)
        ikinci = m.split('Türkçe başlık\n\n')[1].split('\n\n')[0]
        self.assertTrue(ikinci.endswith('.'))
        self.assertLess(len(ikinci), len(x['diller']['tr']['ozet']))

    def test_ana_dil_de_cumle_sinirindan_kisalir_baslik_ve_cagri_korunur(self):
        x = self.haber()
        x['diller']['en']['ozet'] = 'English sentence. ' * 200
        x['diller']['tr']['ozet'] = 'Türkçe cümle. ' * 200
        m = sy.ig_aciklama('tr', x, self.ayar())
        self.assertLessEqual(len(m), 2200)
        self.assertIn('English title', m)
        self.assertIn('Türkçe başlık', m)
        self.assertNotIn('Türkçe cümle.', m)
        self.assertTrue(m.split('English title\n\n')[1].split('\n\n')[0].endswith('.'))
        self.assertIn(sy.paylasim_linki('en', x, 'instagram'), m)

    def test_uzun_tek_cumle_ve_ozet_yoksa_metin(self):
        x = self.haber()
        x['diller']['en'].update(ozet='', metin='Whole sentence. ' + 'word ' * 1000)
        m = sy.ig_aciklama('tr', x, self.ayar())
        self.assertLessEqual(len(m), 2200)
        self.assertIn('Whole sentence.', m)
        self.assertNotIn('word', m)

    def test_etiketler_ana_dilden_tekrarsiz_en_fazla_5(self):
        x = self.haber()
        x['diller']['en']['etiketler'] = ['#Same', '#same', 'boşluk var'] + [f'#English{i}' for i in range(8)]
        x['diller']['tr']['etiketler'] = ['#SAME'] + [f'#Turkce{i}' for i in range(30)]
        tags = sy.ig_aciklama('tr', x, self.ayar()).split('\n')[-1].split()
        self.assertEqual(len(tags), 5)  # Instagram gönderi başına en çok 5 hashtag kabul eder
        self.assertEqual(len({t.casefold() for t in tags}), 5)
        self.assertIn('#Same', tags)
        self.assertNotIn('#Turkce0', tags)  # etiketler ana dilden (en) gelir
        self.assertTrue(all(t.startswith('#') for t in tags))

    def test_ingilizce_kart_secimi_ve_hesap_anahtari(self):
        m, secilen = self.plan(self.ayar(instagram=True))
        self.assertIn('/kart/oyun-yama-1-en-ig.jpg', m)
        self.assertNotIn('/kart/oyun-yama-1-tr-ig.jpg', m)
        self.assertEqual(secilen[0][0], 'oyun-yama-1|tr|instagram|gorsel')
        self.assertEqual(secilen[0][1]['icerik_dili'], 'en')

    def test_ingilizce_video_secimi_ve_baglanti_ingilizce_manifeste(self):
        self.manifest_yaz(dil='en')
        manifest = json.loads(self.manifest.read_text(encoding='utf-8'))
        turkce = dict(manifest['videolar']['oyun-yama-1']['en'], mp4_1080='turkce1080.mp4')
        manifest['videolar']['oyun-yama-1']['tr'] = turkce
        self.manifest.write_text(json.dumps(manifest), encoding='utf-8')
        m, secilen = self.plan(self.ayar(instagram=True, instagram_reel=True))
        self.assertEqual(secilen[0][1]['bicim'], 'reel')
        self.assertIn('video: https://medya.test/v/a1080.mp4', m)
        self.assertNotIn('turkce1080.mp4', m)
        self.assertIn('English summary.', m)
        with patch.object(vs, 'baglanti_yaz', wraps=vs.baglanti_yaz) as yaz:
            g, hata, _ = self.calistir(SahteAg(), self.ayar(instagram_reel=True), [self.haber()])
        self.assertEqual((g, hata), (1, []))
        self.assertEqual(yaz.call_args.args[2], 'en')

    def test_yanit_kaybolunca_icerik_dili_kayittan_uzlastirilir(self):
        self.manifest_yaz(dil='en')
        a = self.ayar(instagram_reel=True)
        ag = SahteAg(mutasyon_hatasi={'media_publish': sy.PaylasimHatasi('zaman aşımı')})
        self.calistir(ag, a, [self.haber()])
        self.assertEqual(self.kayitlar()['oyun-yama-1|tr|instagram|reel']['icerik_dili'], 'en')
        with patch.object(vs, 'baglanti_yaz', wraps=vs.baglanti_yaz) as yaz:
            self.calistir(SahteAg(), ayar(instagram_reel=True), [self.haber()])
        self.assertEqual(yaz.call_args.args[2], 'en', 'ayar sonradan değişse de ilk video dili korunur')
        rec = self.kayitlar()['oyun-yama-1|en|instagram|reel']  # kayıt içerik diline taşınır, hesap alanı korunur
        self.assertEqual((rec['durum'], rec['dil'], rec['hesap']), ('tamam', 'en', 'tr'))

    def test_aciklama_tam_2200_ve_bir_karakter_fazlasi(self):
        x = self.haber()
        x['diller']['en']['ozet'] = 'A.'
        x['diller']['tr']['ozet'] = ''
        x['diller']['tr']['metin'] = ''
        m = sy.ig_aciklama('tr', x, self.ayar())
        x['diller']['en']['ozet'] = 'A' * (2200 - len(m) + 1) + '.'
        tam = sy.ig_aciklama('tr', x, self.ayar())
        self.assertEqual(len(tam), 2200)
        x['diller']['en']['ozet'] += 'A'
        fazla = sy.ig_aciklama('tr', x, self.ayar())
        self.assertLessEqual(len(fazla), 2200)
        self.assertIn('Türkçe başlık', fazla)

    def test_ingilizce_video_yoksa_turkceye_dusmez_gorsel_secili(self):
        self.manifest_yaz(dil='tr')
        m, secilen = self.plan(self.ayar(instagram=True, instagram_reel=True))
        self.assertEqual([r['bicim'] for _, r in secilen], ['gorsel'])
        self.assertNotIn('video:', m)

    def test_hype_esigi_korunur(self):
        self.manifest_yaz(dil='en')
        x = self.haber()
        x['otomasyon']['hype'] = 4
        a = self.ayar(instagram=True, instagram_reel=True)
        a['video'] = {'hype_esigi': 5}
        _, secilen = self.plan(a, x)
        self.assertEqual([r['bicim'] for _, r in secilen], ['gorsel'])

    def test_eski_turkce_gorsel_ve_reel_yeniden_paylasilmaz_kayit_degismez(self):
        self.manifest_yaz(dil='en')
        for son in ('', '|gorsel', '|reel'):
            for durum in ('tamam', 'niyet', 'elle_bak'):
                with self.subTest(son=son, durum=durum):
                    eski = {'oyun-yama-1|tr|instagram' + son:
                            {'id': 'oyun-yama-1', 'durum': durum, 'kimlik': 'eski', 'zaman': '2026-11-14T12:00:00Z'}}
                    self.kayit.write_text(json.dumps(eski), encoding='utf-8')
                    _, secilen = self.plan(self.ayar(instagram=True, instagram_reel=True))
                    self.assertEqual(secilen, [])
                    self.assertEqual(json.loads(self.kayit.read_text(encoding='utf-8')), eski)

    def test_konu_ayni_id_farkliysa_da_tekrar_yok(self):
        self.kayit.write_text(json.dumps({'ortak|tr|instagram|gorsel': {'durum': 'tamam'}}), encoding='utf-8')
        self.manifest_yaz(dil='en')
        x = self.haber()
        x['otomasyon']['konu'] = 'ortak'
        self.assertEqual(self.plan(self.ayar(instagram=True, instagram_reel=True), x)[1], [])

    def test_ayar_yokken_aciklama_ve_turkce_medya_ayni(self):
        x = self.haber()
        a = ayar(instagram=True)
        self.assertEqual(sy.ig_aciklama('tr', x, a), sy.ig_aciklama('tr', x))
        m, _ = self.plan(a, x)
        self.assertIn('/kart/oyun-yama-1-tr-ig.jpg', m)
        self.assertNotIn('English title', m)

    def test_ingilizce_icerik_yoksa_turkceye_dusmez(self):
        x = self.haber()
        del x['diller']['en']
        self.assertEqual(self.plan(self.ayar(instagram=True), x)[1], [])

    def test_kota_hesap_dilinde_sayilir(self):
        self.kayit.write_text(json.dumps({'onceki|tr|instagram|gorsel':
                                         {'durum': 'tamam', 'zaman': SIMDI.isoformat()}}), encoding='utf-8')
        a = self.ayar(instagram=True)
        a['gunluk_en_fazla']['instagram'] = 1
        self.assertEqual(self.plan(a)[1], [])

    def test_sayfa_bekleme_icerik_dili_youtube_hesap_dili(self):
        self.assertEqual(sy.paylasilacak_diller(self.ayar(instagram=True), SIRLAR), ['en'])
        self.assertEqual(sy.paylasilacak_diller(self.ayar(instagram=True, youtube=True), SIRLAR), ['tr', 'en'])

    def test_youtube_turkce_video_ve_metadata_degismez(self):
        self.manifest_yaz(dil='tr')
        normal = self.plan(ayar(youtube=True))
        global_ = self.plan(self.ayar(youtube=True))
        self.assertEqual(normal, global_)

    def test_gercek_ig_istegi_ingilizce_kart_ve_iki_dilli_aciklama(self):
        x, a, ag = self.haber(), self.ayar(instagram=True), SahteAg()
        with patch.object(ag, 'istek', wraps=ag.istek) as istek, patch.object(ag, 'yayinda_mi', return_value=True) as sayfa:
            self.assertEqual(self.calistir(ag, a, [x])[:2], (1, []))
        medya = next(c.kwargs['veri'] for c in istek.call_args_list if c.args[1].endswith('/media'))
        self.assertTrue(medya['image_url'].endswith('-en-ig.jpg'))
        self.assertEqual(medya['caption'], sy.ig_aciklama('tr', x, a))
        self.assertEqual(sayfa.call_args_list[0].args[0], sy.sayfa_adresi('en', x))


if __name__ == '__main__':
    unittest.main()
