"""Hyperframes video motoru: tema seçimi, kontrast, ses seçimi, veri dosyası, güvenli alan, eski senaryoların geçerliliği."""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(pathlib.Path(__file__).parent))

import video_hf as hf  # noqa: E402
import video_uret as v  # noqa: E402
from test_video_uret import KIMLIK, haber, senaryo  # noqa: E402


def sahte_haber(i, tur='haber', oyun='Oyun', gun=1):
    return {'id': f'{oyun.lower().replace(" ", "-")}-{tur}-{i}-2026-11-{gun:02d}', 'tarih': f'2026-11-{gun:02d}',
            'oyun': oyun, 'tur': tur}


def zincir_haberleri(n=60):
    turler = ('haber', 'guncelleme', 'indirim', 'ucretsiz', 'cikis')
    return [sahte_haber(i, turler[i % 5], oyun=f'Oyun {i}', gun=1 + i // 3) for i in range(n)]


class TemaSecimiTests(unittest.TestCase):
    def test_ayni_haber_ayni_paket_her_dilde_ve_her_calismada(self):
        h = haber()
        ilk = hf.tema_girdisi(h, senaryo())['paket']
        self.assertIn(ilk, hf.PAKETLER)
        for _ in range(3):
            self.assertEqual(hf.tema_girdisi(h, senaryo())['paket'], ilk)
        # dil tema girdisine girmez: aynı haberin dört dili aynı temayı alır
        self.assertEqual(hf.tema_girdisi(h, {**senaryo(), 'dil': 'en'})['paket'], ilk)

    def test_ardisik_haberler_ayni_pakette_olmaz(self):
        icerik = zincir_haberleri()
        zincir = hf.paket_zinciri(icerik)
        sirali = sorted(icerik, key=lambda x: (x['tarih'], x['id']))
        for a, b in zip(sirali, sirali[1:]):
            self.assertNotEqual(zincir[a['id']], zincir[b['id']], f"{a['id']} / {b['id']}")

    def test_dort_paket_de_kullanilir_ve_ayni_turde_bile_degisir(self):
        icerik = zincir_haberleri(80)
        zincir = hf.paket_zinciri(icerik)
        self.assertEqual(set(zincir.values()), set(hf.PAKETLER), 'dört paket de gerçekten seçiliyor')
        for tur in ('haber', 'guncelleme', 'indirim', 'ucretsiz', 'cikis'):
            paketler = {zincir[h['id']] for h in icerik if h['tur'] == tur}
            self.assertGreaterEqual(len(paketler), 2, f'{tur}: tek pakete kilitlenmiş')

    def test_tur_paket_egilimi(self):
        icerik = zincir_haberleri(80)
        zincir = hf.paket_zinciri(icerik)
        def pay(tur, paket):
            ler = [zincir[h['id']] for h in icerik if h['tur'] == tur]
            return ler.count(paket) / len(ler)
        self.assertGreater(pay('guncelleme', 'esports') + pay('guncelleme', 'neon'), 0.3)
        self.assertGreater(pay('haber', 'gazete'), pay('cikis', 'gazete'))

    def test_eski_haberin_paketi_yeni_haberle_degismez(self):
        icerik = zincir_haberleri(30)
        once = hf.paket_zinciri(icerik)
        yeni = icerik + [sahte_haber(999, 'haber', 'Yeni Oyun', gun=28)]
        sonra = hf.paket_zinciri(yeni)
        for h in icerik:
            self.assertEqual(once[h['id']], sonra[h['id']])

    def test_gercek_icerikte_ardisik_haberler_farkli(self):
        yol = ROOT / 'data' / 'icerik.json'
        if not yol.exists():
            self.skipTest('data/icerik.json yok')
        icerik = json.loads(yol.read_text(encoding='utf-8'))
        zincir = hf.paket_zinciri(icerik)
        sirali = sorted(icerik, key=lambda x: (x.get('tarih', ''), x.get('id', '')))
        for a, b in zip(sirali, sirali[1:]):
            self.assertNotEqual(zincir[a['id']], zincir[b['id']])

    def test_senaryodaki_tema_ve_zorla_paket(self):
        h = haber()
        self.assertEqual(hf.tema_girdisi(h, {'tema': {'paket': 'kolaj'}})['paket'], 'kolaj')
        self.assertEqual(hf.tema_girdisi(h, {'tema': {'paket': 'kolaj'}}, zorla_paket='neon')['paket'], 'neon')
        with self.assertRaises(hf.TemaHatasi):
            hf.tema_girdisi(h, None, zorla_paket='yok')
        with self.assertRaises(hf.TemaHatasi):
            hf.tema_girdisi(h, {'tema': {'paket': 'yok'}})

    def test_anahtar_temayla_degisir_ve_eski_biçim_bozulmaz(self):
        h, s = haber(), senaryo()
        ses = v.seslendirici('edge', '', 'tr', KIMLIK).ayar()
        eski = v.anahtar(h, 'tr', s, ses)
        a = v.anahtar(h, 'tr', s, ses, hf.anahtar_eki(hf.tema_girdisi(h, s, zorla_paket='neon')))
        b = v.anahtar(h, 'tr', s, ses, hf.anahtar_eki(hf.tema_girdisi(h, s, zorla_paket='kolaj')))
        self.assertEqual(len({eski, a, b}), 3)
        self.assertEqual(v.anahtar(h, 'tr', s, ses, None), eski, 'temasız (Remotion) anahtar değişmedi')


class OyunDokunusuTests(unittest.TestCase):
    def test_tablo_oyunlari_ve_oge_siniri(self):
        tablo = hf.tablo_oku()
        self.assertGreaterEqual(len(tablo['oyunlar']), 5)
        for o in tablo['oyunlar']:
            self.assertTrue(o['anahtar'], o)
            self.assertIn(o.get('oge'), (None, 'piksel', 'gunbatimi', 'keskin', 'altigen'), o)
            if o.get('palet'):
                self.assertEqual(set(o['palet']) - {'ana', 'ana2', 'vurgu', 'bg'}, set(), o)

    def test_gta_gunbatimi_minecraft_piksel_cs_keskin(self):
        tablo = hf.tablo_oku()
        for oyun, oge in (('Grand Theft Auto VI', 'gunbatimi'), ('Minecraft', 'piksel'), ('Fortnite', 'altigen'),
                          ('Counter-Strike 2', 'keskin'), ('Valorant', 'keskin')):
            anahtar, kayit = hf.oyun_dokunusu({'id': 'x-2026-11-01', 'oyun': oyun}, tablo)
            self.assertIsNotNone(kayit, oyun)
            self.assertEqual(kayit['oge'], oge, oyun)

    def test_bilinmeyen_oyunda_dokunus_yok_ve_palet_oyundan_gelir(self):
        tablo = hf.tablo_oku()
        self.assertEqual(hf.oyun_dokunusu({'id': 'z-1', 'oyun': 'Bilinmeyen Oyun'}, tablo), (None, None))
        h = {'id': 'gta-6-fragman-2026-11-10', 'oyun': 'Grand Theft Auto VI', 'tur': 'haber', 'tarih': '2026-11-10'}
        girdi = hf.tema_girdisi(h, None, None)
        tema = hf.tema_sec(h, girdi)
        self.assertEqual(tema['renk'], 'oyun')
        self.assertEqual(tema['oge'], ['gunbatimi'])
        self.assertEqual(tema['palet']['bg'][0], '#')

    def test_senaryo_ozel_palet_ve_oge_kullanilir(self):
        h = haber()
        s = {'tema': {'paket': 'neon', 'palet': {'ana': '#2266ee'}, 'oge': ['piksel', 'keskin']}}
        tema = hf.tema_sec(h, hf.tema_girdisi(h, s))
        self.assertEqual(tema['oge'], ['piksel', 'keskin'])
        self.assertEqual(hf.hex_hsl(tema['palet']['ana'])[0] // 1, hf.hex_hsl('#2266ee')[0] // 1)


class KontrastTests(unittest.TestCase):
    def test_kontrast_orani_bilinen_degerler(self):
        self.assertAlmostEqual(hf.kontrast_orani('#000000', '#ffffff'), 21.0, places=1)
        self.assertAlmostEqual(hf.kontrast_orani('#ffffff', '#ffffff'), 1.0, places=2)

    def test_her_paket_tur_ve_tonda_palet_okunur(self):
        for paket in hf.PAKETLER:
            for tur in hf.TURLER:
                for ton in range(0, 360, 20):
                    for doygun in (0.2, 0.8):
                        p = hf.palet_kur(paket, tur, ton, doygun, None)
                        self.assertEqual(hf.tema_hatalari(p), [], (paket, tur, ton, doygun))

    def test_acik_renkli_oyun_paleti_de_duzeltilir(self):
        p = hf.palet_kur('esports', 'haber', 40, 0.8, None, {'bg': '#f5f0e0', 'ana': '#fffbe6', 'vurgu': '#ffffe0'})
        self.assertEqual(hf.tema_hatalari(p), [])

    def test_okunmaz_palet_yakalanir(self):
        kotu = hf.palet_kur('neon', 'haber', 200, 0.8, None)
        gri = {**kotu, 'bg': '#808080', 'ana-acik': '#777777'}
        hatalar = hf.tema_hatalari(gri)
        self.assertGreaterEqual(len(hatalar), 2)
        self.assertTrue(any('ana-acik' in h for h in hatalar), hatalar)
        # düzeltici zemin/açık ton ayrımını geri getirir
        self.assertEqual(hf.tema_hatalari(hf.kontrast_duzelt(gri)), [])
        # yazı rengi sabit beyazdır; bozulursa denetim yakalar (düzeltici dokunmaz)
        soluk = {**kotu, 'yazi': '#8a8a8a'}
        self.assertTrue(any(h.startswith('yazi ') for h in hf.tema_hatalari(hf.kontrast_duzelt(soluk))))

    def test_eksik_anahtar_hata_sayilir(self):
        self.assertTrue(any('palette yok' in h for h in hf.tema_hatalari({'yazi': '#ffffff'})))


class SesSecimiTests(unittest.TestCase):
    LISTE = ['tr-TR-Aydin:MAI-Voice-2.1', 'tr-TR-EmelNeural', 'tr-TR-AhmetNeural']

    def test_secim_sabit_ve_uc_sese_dagilir(self):
        idler = [f'haber-{i}-2026-11-15' for i in range(60)]
        secilen = [hf.ses_sec(self.LISTE, i) for i in idler]
        self.assertEqual(secilen, [hf.ses_sec(self.LISTE, i) for i in idler], 'aynı haber aynı ses')
        self.assertEqual(set(secilen), set(self.LISTE), 'üç ses de kullanılıyor')
        for ses in self.LISTE:
            self.assertGreater(secilen.count(ses), 8, ses)

    def test_edge_mai_sesini_atlar(self):
        for i in range(40):
            self.assertNotIn(':', hf.ses_sec(self.LISTE, f'x-{i}', edge=True))
        self.assertEqual(hf.ses_sec([], 'x'), '')
        self.assertEqual(hf.ses_sec(['a:b'], 'x', edge=True), 'a:b', 'tek aday MAI ise yine de döner')

    def test_ayardaki_her_dilde_uc_ses_ve_bir_kadin(self):
        ayarlar = json.loads((ROOT / 'sosyal' / 'ayarlar.json').read_text(encoding='utf-8'))['video']['konusmaci']
        # Doğal ses ailesi (MAI-Voice-2.1); standart Neural sesler robotik bulundu (Cio, 2026-11-16).
        kadin = {'tr': 'Elif', 'en': 'Harper', 'es': 'Elvira', 'fr': 'Denise', 'de': 'Mia', 'nl': 'Harper',
                 'zh': 'Lan'}
        for dil, liste in ayarlar.items():
            self.assertEqual(len(liste), 3, dil)
            self.assertEqual(sum(any(k in s for k in kadin.values()) for s in liste), 1, f'{dil}: tam bir kadın sesi')
            self.assertIn(kadin[dil], liste[1], f'{dil}: kadın ses ikinci sırada')
            for s in liste:
                self.assertTrue(s.startswith(dil), (dil, s))

    def test_seslendirici_dil_basina_uc_sesten_secer(self):
        ayar = v.video_ayari()
        for dil in ('tr', 'en', 'es', 'fr', 'de', 'nl', 'zh'):
            sesler = {v.seslendirici('azure', ayar['konusmaci'], dil, f'h-{i}').konusmaci for i in range(40)}
            self.assertEqual(sesler, set(ayar['konusmaci'][dil]), dil)
            edge = {v.seslendirici('edge', ayar['konusmaci'], dil, f'h-{i}').konusmaci for i in range(40)}
            self.assertTrue(all(':' not in s for s in edge), dil)


def sahte_props(dil='tr', metin='Örnek Oyun yaması geliyor'):
    return {'surum': 1, 'id': 'ornek-yama-2026-11-15', 'dil': dil, 'fps': 30, 'boyut': [1080, 1920], 'ses': 'ses.mp3',
            'sure': 12.0, 'kapak_kare': 40,
            'haber': {'oyun': 'Örnek Oyun', 'tur': 'guncelleme', 'tur_etiket': 'YAMA', 'platformlar': [],
                      'tarih': '2026-11-15', 'tarih_metin': '15 Kasım 2026'},
            'sahneler': [{'sablon': 'baslik', 'bas': 0, 'bit': 6.0, 'veri': {'baslik': metin, 'vurgu': []}},
                         {'sablon': 'kapanis', 'bas': 6.0, 'bit': 12.0, 'veri': {'ust': 'Takipte kal'}}],
            'kelimeler': [{'k': 'Örnek', 'b': 0.1, 's': 0.5}], 'parcalar': [{'metin': metin, 'b': 0.1, 's': 2.0}]}


class VeriDosyasiTests(unittest.TestCase):
    def test_veri_senaryodan_gelir(self):
        tema = {'paket': 'gazete', 'palet': {'bg': '#101010'}, 'oge': ['keskin']}
        veri = hf.veri_olustur(sahte_props(), tema, 'assets/img/foto.jpg')
        self.assertEqual(veri['tema'], {'paket': 'gazete', 'oge': ['keskin']})
        self.assertEqual(veri['foto'], 'assets/img/foto.jpg')
        self.assertEqual([s['sablon'] for s in veri['sahneler']], ['baslik', 'kapanis'])
        self.assertEqual(veri['sahneler'][0]['veri']['baslik'], 'Örnek Oyun yaması geliyor')
        self.assertEqual(veri['haber']['tarih_metin'], '15 Kasım 2026')
        self.assertEqual(veri['dil'], 'tr')

    def test_klasor_kur_dosyalari_yazar_ve_yer_tutucu_birakmaz(self):
        with tempfile.TemporaryDirectory() as t:
            ses = pathlib.Path(t) / 'ses.mp3'
            ses.write_bytes(b'ID3')
            tema = hf.tema_sec(haber(), hf.tema_girdisi(haber(), None, None, 'kolaj'))
            k = hf.klasor_kur(pathlib.Path(t) / 'hf', sahte_props('zh', '生存游戏更新'), tema, ses, None)
            html = (k / 'index.html').read_text(encoding='utf-8')
            veri = (k / 'assets' / 'data.js').read_text(encoding='utf-8')
            self.assertNotRegex(html, r'__[A-Z]+__')
            self.assertIn('lang="zh"', html)
            self.assertIn('p-kolaj', html)
            self.assertIn(f"--bg:{tema['palet']['bg']}", html)
            self.assertIn('data-duration="6.0"', html)
            self.assertTrue(veri.startswith('window.VIDEO = '))
            self.assertIn('生存游戏更新', veri)
            self.assertTrue((k / 'assets' / 'ses' / 'ses.mp3').exists())
            self.assertTrue(any((k / 'assets' / 'fonts').glob('*.woff2')))
            for ad in hf.STATIK:
                self.assertTrue((k / ad).exists(), ad)

    def test_sablon_ve_motorda_habere_ozel_sabit_yazi_yok(self):
        # Haber metinleri yalnız üretilen veri dosyasından gelir; şablonda bir oyun/haber adı gömülü olmamalı.
        kaynak = ' '.join((hf.HF / ad).read_text(encoding='utf-8') for ad in ('index.html', 'motor.js'))
        for yasak in ('Siege', 'Battlefield', 'Casino Heist', 'Vital Signal', 'rainbow'):
            self.assertNotIn(yasak, kaynak, yasak)

    def test_sekiz_sahne_turunun_sablonu_var(self):
        motor = (hf.HF / 'motor.js').read_text(encoding='utf-8')
        for sablon in ('baslik', 'maddeler', 'yama_fark', 'platform', 'tarih', 'fiyat', 'kaynak', 'kapanis'):
            self.assertIn(sablon, motor, sablon)
        taban = (hf.HF / 'taban.css').read_text(encoding='utf-8')
        for onek in ('.bk-', '.kn-', '.mp-', '.yf-', '.pf-', '.tr-', '.fy-', '.kp-'):
            self.assertIn(onek, taban, onek)

    def test_dort_paket_ve_dort_oge_css_de_tanimli(self):
        css = (hf.HF / 'temalar.css').read_text(encoding='utf-8')
        for p in hf.PAKETLER:
            self.assertIn(f'.p-{p}', css, p)

    def test_yazi_tipleri_depoda_ve_lisansli(self):
        fontlar = hf.HF / 'assets' / 'fonts'
        css = (hf.HF / 'fontlar.css').read_text(encoding='utf-8')
        import re
        for ad in re.findall(r'url\(["\']?assets/fonts/([^"\')]+)', css):
            self.assertTrue((fontlar / ad).exists(), ad)
        self.assertGreaterEqual(len(list(fontlar.glob('LICENSE-*.txt'))), 4)


class GuvenliAlanTests(unittest.TestCase):
    def test_sinirlar_kisa_icerik_kurallari(self):
        g = hf.GUVENLI
        self.assertGreaterEqual(g['ust'], 220)
        self.assertLessEqual(g['alt'], 1500)
        self.assertLessEqual(g['sag_alt'], 930)

    def kos_ihlal(self, rapor, kod=3):
        def kos(komut, **kw):
            if '--rapor' in komut:
                pathlib.Path(komut[komut.index('--rapor') + 1]).write_text(json.dumps(rapor), encoding='utf-8')
                return subprocess.CompletedProcess(komut, kod, '', '')
            return subprocess.CompletedProcess(komut, 0, '', '')
        return kos

    def test_ihlal_uretimi_durdurur(self):
        rapor = {'olcum_sayisi': 6, 'metin_sayisi': 30, 'ihlal_sayisi': 1, 'sinir': hf.GUVENLI,
                 'ihlaller': [{'sahne': 1, 'an': 4.2, 'metin': 'Steam', 'yon': 'alt', 'deger': 1544, 'kutu': [1, 2, 3, 4]}]}
        with tempfile.TemporaryDirectory() as t, patch.object(hf, 'tarayici_yolu', lambda kos=None: 'chrome'), \
                patch.object(hf, 'hf_koku', lambda kos=None: 'kok'):
            with self.assertRaises(hf.TemaHatasi) as c:
                hf.guvenli_denetle(pathlib.Path(t), sahte_props(), pathlib.Path(t) / 'r.json', lambda m: None,
                                   kos=self.kos_ihlal(rapor))
            self.assertIn("1 ihlal ('Steam' alt 4.2 sn, 1544 px)", str(c.exception))
            rapor.update(ihlal_sayisi=0, ihlaller=[])
            mesaj = []
            hf.guvenli_denetle(pathlib.Path(t), sahte_props(), pathlib.Path(t) / 'r.json', mesaj.append,
                               kos=self.kos_ihlal(rapor, 0))
        self.assertEqual(mesaj, ['güvenli alan denetimi: 6 ölçüm, 30 metin, ihlal yok'])

    def test_calismayan_denetim_uretimi_durdurur(self):
        def kos(komut, **kw):
            return subprocess.CompletedProcess(komut, 1, '', 'patladı')
        with tempfile.TemporaryDirectory() as t, patch.object(hf, 'tarayici_yolu', lambda kos=None: 'chrome'), \
                patch.object(hf, 'hf_koku', lambda kos=None: 'kok'):
            with self.assertRaises(hf.TemaHatasi):
                hf.guvenli_denetle(pathlib.Path(t), sahte_props(), pathlib.Path(t) / 'r.json', lambda m: None, kos=kos)

    def test_gercek_tarayicida_ihlal_yakalanir(self):
        """guvenli_alan.mjs'i gerçek Chrome'da küçük bir sayfada çalıştırır: sınır içindeki yazı geçer, üst/alt/sağ-alt
        dışındakiler ve taşan .fit kutusu ihlal sayılır. Chrome ya da global hyperframes yoksa atlanır."""
        try:
            chrome, kok = hf.tarayici_yolu(), hf.hf_koku()
        except (hf.TemaHatasi, OSError, IndexError):
            self.skipTest('Chrome / global hyperframes yok')
        sayfa = """<!doctype html><meta charset=utf-8><style>body{margin:0;width:1080px;height:1920px}
        .sc{position:absolute;left:0;top:0;width:1080px;height:1920px} p{position:absolute;margin:0;font:40px sans-serif}
        .fit{position:absolute;left:100px;top:700px;width:300px;height:60px;font:40px/50px sans-serif;overflow:hidden}</style>
        <section class="sc" id="s0"><p style="left:100px;top:400px">içeride</p>%s</section>
        <script>window.__timelines={main:{seek(){}}}</script>"""
        durumlar = {
            'temiz': ('', 0),
            'ust': ('<p style="left:100px;top:120px">çok yukarıda</p>', 3),
            'alt': ('<p style="left:100px;top:1480px">çok aşağıda</p>', 3),
            'sag_alt': ('<p style="left:800px;top:1100px">sağ alt köşe taşkın</p>', 3),
            'tasma': ('<div class="fit">bu metin kutuya sığmayacak kadar uzun bir metin dizisidir</div>', 3),
        }
        for ad, (ek, beklenen) in durumlar.items():
            with self.subTest(ad), tempfile.TemporaryDirectory() as t:
                klasor = pathlib.Path(t)
                (klasor / 'index.html').write_text(sayfa % ek, encoding='utf-8')
                komut = ['node', str(hf.GUVENLI_BETIK), '--klasor', str(klasor), '--rapor', str(klasor / 'r.json'),
                         '--chrome', chrome, '--hf', kok, '--sahneler', '[[0,4]]', '--sure', '4',
                         '--sinir', json.dumps(hf.GUVENLI)]
                r = subprocess.run(komut, capture_output=True, text=True, encoding='utf-8', timeout=120)
                self.assertEqual(r.returncode, beklenen, r.stderr)
                rapor = json.loads((klasor / 'r.json').read_text(encoding='utf-8'))
                self.assertEqual(bool(rapor['ihlal_sayisi']), bool(beklenen))


class DolulukTests(unittest.TestCase):
    def test_esikler_tanimli(self):
        self.assertEqual(hf.GUVENLI['doluluk_min'], 0.7)
        self.assertEqual(hf.GUVENLI['baslik_min'], 96)

    def test_komut_sahne_turunu_tasir(self):
        gorulen = []

        def kos(komut, **kw):
            gorulen.append(komut)
            rapor = {'olcum_sayisi': 3, 'metin_sayisi': 9, 'ihlal_sayisi': 0, 'sinir': hf.GUVENLI, 'ihlaller': [],
                     'doluluk': [{'sahne': 0, 'sablon': 'baslik', 'oran': 0.9}, {'sahne': 1, 'sablon': 'maddeler', 'oran': 0.81},
                                 {'sahne': 2, 'sablon': 'maddeler', 'oran': 0.74}]}
            if '--rapor' in komut:
                pathlib.Path(komut[komut.index('--rapor') + 1]).write_text(json.dumps(rapor), encoding='utf-8')
            return subprocess.CompletedProcess(komut, 0, '', '')
        mesaj = []
        with tempfile.TemporaryDirectory() as t, patch.object(hf, 'tarayici_yolu', lambda kos=None: 'chrome'),                 patch.object(hf, 'hf_koku', lambda kos=None: 'kok'):
            hf.guvenli_denetle(pathlib.Path(t), sahte_props(), pathlib.Path(t) / 'r.json', mesaj.append, kos=kos)
        sahneler = json.loads(gorulen[0][gorulen[0].index('--sahneler') + 1])
        self.assertTrue(all(len(x) == 3 for x in sahneler))
        self.assertEqual([x[2] for x in sahneler], [s['sablon'] for s in sahte_props()['sahneler']])
        self.assertIn('  doluluk maddeler: en düşük %74', mesaj)
        self.assertIn('  doluluk baslik: en düşük %90', mesaj)

    def test_gercek_tarayicida_doluluk_ve_baslik_boyutu(self):
        """Ön plan ([data-on]) kutusu güvenli alanın %70'inden kısaysa ve açılış başlığı 96 px'ten küçükse ihlal sayılır."""
        try:
            chrome, kok = hf.tarayici_yolu(), hf.hf_koku()
        except (hf.TemaHatasi, OSError, IndexError):
            self.skipTest('Chrome / global hyperframes yok')
        sayfa = """<!doctype html><meta charset=utf-8><style>body{margin:0;width:1080px;height:1920px}
        .sc{position:absolute;left:0;top:0;width:1080px;height:1920px} div{position:absolute;margin:0;left:100px;width:800px}
        </style><section class="sc" id="s0">%s</section>
        <script>window.__timelines={main:{seek(){}}}</script>"""
        durumlar = {
            'dolu': ('<div data-on="1" style="top:300px;height:950px"></div>', 'maddeler', 0, 0.74),
            'dolu-iki-blok': ('<div data-on="1" style="top:300px;height:400px"></div><div data-on="1" style="top:850px;height:400px"></div>',
                              'maddeler', 0, 0.74),
            'kisa': ('<div data-on="1" style="top:300px;height:600px"></div>', 'maddeler', 3, 0.47),
            'bos': ('', 'kapanis', 3, 0),
            'baslik-iri': ('<div data-on="1" style="top:300px;height:1000px"></div><div class="bk-bas" style="top:300px;height:100px;font-size:140px">x</div>',
                           'baslik', 0, 0.78),
            'baslik-kucuk': ('<div data-on="1" style="top:300px;height:1000px"></div><div class="bk-bas" style="top:300px;height:100px;font-size:80px">x</div>',
                             'baslik', 3, 0.78),
        }
        for ad, (ek, sablon, beklenen, _) in durumlar.items():
            with self.subTest(ad), tempfile.TemporaryDirectory() as t:
                klasor = pathlib.Path(t)
                (klasor / 'index.html').write_text(sayfa % ek, encoding='utf-8')
                komut = ['node', str(hf.GUVENLI_BETIK), '--klasor', str(klasor), '--rapor', str(klasor / 'r.json'),
                         '--chrome', chrome, '--hf', kok, '--sahneler', json.dumps([[0, 4, sablon]]), '--sure', '4',
                         '--sinir', json.dumps(hf.GUVENLI)]
                r = subprocess.run(komut, capture_output=True, text=True, encoding='utf-8', timeout=120)
                self.assertEqual(r.returncode, beklenen, r.stderr)
                rapor = json.loads((klasor / 'r.json').read_text(encoding='utf-8'))
                self.assertEqual(rapor['doluluk'][0]['sablon'], sablon)
                if beklenen:
                    self.assertIn(rapor['ihlaller'][0]['yon'], ('doluluk', 'başlık-boyutu'))

    def test_ilk_kare_kancasi_bos_degil_ve_vurgu_erken_yanar(self):
        """İlk karede (t=0) başlık kelimeleri, etiket ve tür damgası görünür (opacity>=0.9); vurgu ilk 0.55 sn içinde yanar."""
        try:
            chrome, kok = hf.tarayici_yolu(), hf.hf_koku()
        except (hf.TemaHatasi, OSError, IndexError):
            self.skipTest('Chrome / global hyperframes yok')
        h = haber()
        s = senaryo()
        hazir = v.senaryo_hazirla(s, h, 'tr')
        kel, t = [], 0.1
        for sh in hazir['sahneler']:
            for k in sh['kelimeler']:
                kel.append({'k': k, 'b': round(t, 3), 's': round(t + 0.32, 3)})
                t += 0.35
        zaman = v.zamanla(hazir, kel, t + 1.0)
        props = v.props_kur(h, 'tr', hazir, zaman)
        betik = r"""
const { createRequire } = require('node:module');
const { pathToFileURL } = require('node:url');
const path = require('node:path');
(async () => {
  const [chrome, kok, ...klasorler] = process.argv.slice(1);
  const puppeteer = createRequire(path.join(kok, 'package.json'))('puppeteer-core');
  const browser = await puppeteer.launch({
    executablePath: chrome, headless: 'shell',
    args: ['--no-sandbox', '--disable-gpu', '--allow-file-access-from-files'],
  });
  const sonuclar = {};
  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1080, height: 1920, deviceScaleFactor: 1 });
    for (const k of klasorler) {
      await page.goto(pathToFileURL(path.join(k, 'index.html')).href, { waitUntil: 'load' });
      await page.evaluate(() => document.fonts.ready);
      await page.waitForFunction(() => !!(window.__timelines && window.__timelines.main));
      const t0 = await page.evaluate(() => {
        window.__timelines.main.seek(0);
        const op = (el) => parseFloat(getComputedStyle(el).opacity || '0');
        const words = [...document.querySelectorAll('#s0 .bk-bas .bw')];
        const chip = document.querySelector('#s0 .bk-ust .chip');
        const damga = document.querySelector('#s0 .bk-damga');
        return {
          wordCount: words.length,
          minWordOp: words.length ? Math.min(...words.map(op)) : 0,
          chipOp: chip ? op(chip) : 0,
          damgaOp: damga ? op(damga) : 0,
          baslikH: document.querySelector('#s0 .bk-bas')?.getBoundingClientRect().height || 0,
        };
      });
      const t55 = await page.evaluate(() => {
        window.__timelines.main.seek(0.55);
        const bgOn = [...document.querySelectorAll('#s0 .bk-bas .bg.on')];
        const hls = [...document.querySelectorAll('#s0 .bk-bas .bg.on .hl')];
        const maxHlW = hls.length ? Math.max(...hls.map((e) => e.getBoundingClientRect().width)) : 0;
        const onBw = document.querySelector('#s0 .bk-bas .bg.on .bw');
        const onBg = onBw ? getComputedStyle(onBw).backgroundColor : '';
        return { bgOnCount: bgOn.length, maxHlW, onBg };
      });
      sonuclar[path.basename(k)] = { t0, t55 };
    }
  } finally {
    await browser.close();
  }
  console.log(JSON.stringify(sonuclar));
})();
"""
        with tempfile.TemporaryDirectory() as tmp:
            ses = pathlib.Path(tmp) / 'ses.mp3'
            ses.write_bytes(b'ID3')
            klasorler = []
            for paket in hf.PAKETLER:
                tema = hf.tema_sec(h, {'paket': paket}, None)
                klasorler.append(str(hf.klasor_kur(pathlib.Path(tmp) / paket, props, tema, ses, None)))
            r = subprocess.run(['node', '-e', betik, chrome, kok, *klasorler],
                               capture_output=True, text=True, encoding='utf-8', timeout=120)
            self.assertEqual(r.returncode, 0, r.stderr)
            veri = json.loads(r.stdout.strip().splitlines()[-1])
            for paket in hf.PAKETLER:
                with self.subTest(paket):
                    olcum = veri[paket]
                    self.assertGreater(olcum['t0']['wordCount'], 0)
                    self.assertGreaterEqual(olcum['t0']['minWordOp'], 0.9)
                    self.assertGreaterEqual(olcum['t0']['chipOp'], 0.9)
                    self.assertGreaterEqual(olcum['t0']['damgaOp'], 0.9)
                    self.assertGreater(olcum['t0']['baslikH'], 80)
                    self.assertGreaterEqual(olcum['t55']['bgOnCount'], 1)
                    self.assertGreater(olcum['t55']['maxHlW'], 20)


class EskiSenaryoTests(unittest.TestCase):
    def test_depodaki_butun_senaryolar_gecerli(self):
        dosyalar = sorted((ROOT / 'video' / 'senaryo').glob('*.json'))
        self.assertGreaterEqual(len(dosyalar), 5)
        for d in dosyalar:
            kimlik, dil = d.stem.rsplit('-', 1)
            with self.subTest(d.stem):
                self.assertEqual(v.dogrula(kimlik, dil, cikti=lambda m: None), 0)

    def test_tema_alani_isteğe_bağlı_ve_denetlenir(self):
        h = haber()
        s = senaryo()
        self.assertEqual(v.senaryo_hazirla(s, h, 'tr')['tema'], {})
        s['tema'] = {'paket': 'gazete', 'palet': {'ana': '#aa2233'}, 'oge': ['piksel']}
        self.assertEqual(v.senaryo_hazirla(s, h, 'tr')['tema']['paket'], 'gazete')
        for kotu in ({'paket': 'yok'}, {'palet': {'ana': 'kirmizi'}}, {'palet': {'bilinmeyen': '#ffffff'}},
                     {'oge': ['piksel', 'keskin', 'altigen', 'gunbatimi']}, {'oge': ['ejderha']}, {'baska': 1}, 'gazete'):
            s['tema'] = kotu
            with self.subTest(kotu), self.assertRaises(v.SenaryoHatasi):
                v.senaryo_hazirla(s, h, 'tr')

    def test_yeni_diller_tanimli(self):
        for dil in ('de', 'nl', 'zh'):
            self.assertIn(dil, v.VARSAYILAN_KONUSMACI)
            self.assertIn(dil, v.TUR_ETIKET)
            self.assertIn(dil, v.KELIME_ARALIGI)
            self.assertTrue(v.tarih_metni('2026-11-15', dil))
        self.assertEqual(v.tarih_metni('2026-11-15', 'zh'), '2026年11月15日')


class UretimYoluTests(unittest.TestCase):
    def test_varsayilan_motor_hyperframes_ve_remotion_geri_donusu(self):
        self.assertEqual(v.MOTORLAR[0], 'hyperframes')
        self.assertIn('remotion', v.MOTORLAR)
        with self.assertRaises(v.UretimHatasi):
            v.uret(KIMLIK, 'tr', motor='yok')
        with self.assertRaises(v.UretimHatasi):
            v.uret(KIMLIK, 'tr', motor='remotion', onizleme=pathlib.Path('x'), tema_paketi='neon')
        with self.assertRaises(v.UretimHatasi):
            v.uret(KIMLIK, 'tr', onizleme=pathlib.Path('x'), yukle=True)

    def test_iş_akisi_hyperframes_kurar_ve_yasak_komut_kullanmaz(self):
        yol = ROOT / '.github' / 'workflows' / 'video.yml'
        metin = yol.read_text(encoding='utf-8')
        self.assertIn(f'HF_SURUMU: "{hf.HF_SURUMU}"', metin)
        self.assertIn('npm install -g "hyperframes@${HF_SURUMU}"', metin)
        self.assertIn('HYPERFRAMES_NO_TELEMETRY', metin)
        for yasak in ('hyperframes publish', 'hyperframes share', 'hyperframes cloud', 'hyperframes auth',
                      'hyperframes templates', 'hyperframes billing'):
            self.assertNotIn(yasak, metin, yasak)
        paket = json.loads((hf.HF / 'package.json').read_text(encoding='utf-8'))
        self.assertNotIn('publish', paket.get('scripts', {}))


class KapakAfisTests(unittest.TestCase):
    def test_gorsel_adresi_oyun_gorseline_duser_ve_haber_gorseli_onceliklidir(self):
        with tempfile.TemporaryDirectory() as t:
            g_yol = pathlib.Path(t) / 'gorseller.json'
            og_yol = pathlib.Path(t) / 'oyun_gorselleri.json'
            g_yol.write_text(json.dumps({'ozel-haber': {'url': 'https://cdn.example/haber.jpg'}}), encoding='utf-8')
            og_yol.write_text(json.dumps({
                'oyun': {'gta-6': {'url': 'https://cdn.example/gta6.jpg'},
                         'counter-strike-2': {'url': 'https://cdn.example/cs2.jpg'}},
                'takvim': {'fable': {'url': 'https://cdn.example/fable.jpg'}},
            }), encoding='utf-8')
            # Haber görseli varsa öncelikli
            self.assertEqual(hf.gorsel_adresi('ozel-haber', g_yol, haber={'oyun': 'Grand Theft Auto VI'}, oyun_yol=og_yol),
                             'https://cdn.example/haber.jpg')
            # Haber görseli yoksa oyunun resmî görseline düşer (GTA VI -> gta-6, CS2 -> counter-strike-2)
            self.assertEqual(hf.gorsel_adresi('yok', g_yol, haber={'oyun': 'Grand Theft Auto VI'}, oyun_yol=og_yol),
                             'https://cdn.example/gta6.jpg')
            self.assertEqual(hf.gorsel_adresi('yok', g_yol, haber={'oyun': 'Counter-Strike 2'}, oyun_yol=og_yol),
                             'https://cdn.example/cs2.jpg')
            self.assertEqual(hf.gorsel_adresi('yok', g_yol, haber={'oyun': 'Fable'}, oyun_yol=og_yol),
                             'https://cdn.example/fable.jpg')
            self.assertIsNone(hf.gorsel_adresi('yok', g_yol, haber={'oyun': 'Bilinmeyen Oyun'}, oyun_yol=og_yol))

    def test_gercek_gta6_haberleri_oyun_gorseli_bulur(self):
        url = hf.gorsel_adresi('gta-vi-kacta-aciliyor-2026-11-17', haber={'oyun': 'Grand Theft Auto VI'})
        self.assertIsNotNone(url)
        self.assertTrue(url.startswith('https://'))

    def test_kapak_ciz_yatay_dikey_gorselsiz_ve_turkce_cjk(self):
        from PIL import Image
        palet = hf.palet_kur('esports', 'cikis', 330, 0.85, 45)
        with tempfile.TemporaryDirectory() as t:
            tmp = pathlib.Path(t)
            yatay = tmp / 'yatay.jpg'
            dikey = tmp / 'dikey.jpg'
            Image.new('RGB', (1200, 630), (210, 60, 140)).save(yatay)
            Image.new('RGB', (600, 900), (240, 130, 20)).save(dikey)

            for ad, foto, baslik, vurgu, dil in (
                ('yatay', yatay, 'GTA VI yerel gece yarısı açılıyor', [{'metin': 'gece yarısı', 'tetik': 'gece'}], 'tr'),
                ('dikey', dikey, 'Cobblestone eşleşmeye eklendi', ['Cobblestone'], 'tr'),
                ('gorselsiz', None, "Ocarina of Time Switch 2'de yayında", ['Switch 2'], 'tr'),
                ('cjk', yatay, '新版本正式上线支持中文', ['正式上线'], 'zh'),
            ):
                with self.subTest(ad):
                    cikti = hf.kapak_ciz(tmp / f'{ad}.jpg', foto=foto, baslik=baslik, vurgu=vurgu,
                                         tur_etiket='ÇIKIŞ', oyun='Grand Theft Auto VI', palet=palet, dil=dil)
                    self.assertTrue(cikti.exists())
                    with Image.open(cikti) as im:
                        self.assertEqual(im.size, (1080, 1920))
                        self.assertEqual(im.format, 'JPEG')

    def test_kapak_yenile_manifest_kapaklarini_uretir(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as t:
            tmp = pathlib.Path(t)
            manifest = tmp / 'videolar.json'
            manifest.write_text(json.dumps({
                'surum': 1, 'taban': 'https://medya.test/v/',
                'videolar': {KIMLIK: {'tr': {'anahtar': 'abc', 'kapak': 'test-kapak.jpg'}}},
            }), encoding='utf-8')
            cikti_dir = tmp / 'cikti'
            with patch.object(v, 'MANIFEST', manifest), patch.object(v, 'CIKTI', cikti_dir), \
                    patch.object(v, 'GECICI', tmp / 'gecici'), \
                    patch.object(v, 'haberler', lambda: [haber()]), \
                    patch.object(v, 'senaryo_oku', lambda hid, d: senaryo()), \
                    patch.object(hf, 'foto_hazirla', lambda *a, **kw: None):
                dosyalar = v.kapak_yenile(cikti=lambda *_: None)
            self.assertEqual(len(dosyalar), 1)
            self.assertRegex(dosyalar[0].name, r'^test-kapak-[0-9a-f]{6}\.jpg$')
            guncel = json.loads(manifest.read_text(encoding='utf-8'))
            self.assertEqual(guncel['videolar'][KIMLIK]['tr']['kapak'], dosyalar[0].name)
            with Image.open(dosyalar[0]) as im:
                self.assertEqual(im.size, (1080, 1920))


class OyunVideoTests(unittest.TestCase):
    def test_steam_appid_kaynak_ve_gorsel_urlden_cozulur(self):
        h = {'id': 'x', 'oyun': 'MOUSE: P.I. For Hire',
             'kaynaklar': [{'url': 'https://store.steampowered.com/news/app/2416450/view/702159569166533175'}]}
        self.assertEqual(hf.steam_appid_bul(h, 'x', ag_ara=False), '2416450')
        with tempfile.TemporaryDirectory() as t:
            gy = pathlib.Path(t) / 'g.json'
            gy.write_text(json.dumps({'y': {'url': 'https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/2272360/header.jpg'}}), encoding='utf-8')
            self.assertEqual(hf.steam_appid_bul({'id': 'y', 'oyun': 'Dawn of War IV', 'kaynaklar': []}, 'y', gorsel_yol=gy, ag_ara=False), '2272360')

    def test_steam_ad_eslesmesi_yanlis_oyunu_reddeder(self):
        self.assertTrue(hf._steam_ad_eslesir_mi("MOUSE: P.I. For Hire", "MOUSE: P.I. For Hire"))
        self.assertTrue(hf._steam_ad_eslesir_mi("Zombies Arent Real", "Zombies Aren't Real"))
        self.assertFalse(hf._steam_ad_eslesir_mi("Grand Theft Auto VI", "Grand Theft Auto V"))
        self.assertFalse(hf._steam_ad_eslesir_mi("Wave Race: Blue Storm", "Blue Storm Racing"))

    def test_fragman_secimi_oynanisi_accolades_onune_alir(self):
        filmler = [
            {"name": "MOUSE: Accolades trailer", "highlight": True},
            {"name": "MOUSE: Out Now trailer", "highlight": True},
            {"name": "MOUSE: Official Gameplay Trailer", "highlight": False},
        ]
        sirali = [m["name"] for _, m in sorted(enumerate(filmler), key=lambda x: hf._fragman_puani(x[1], x[0]))]
        self.assertEqual(sirali[0], "MOUSE: Official Gameplay Trailer")
        self.assertEqual(sirali[-1], "MOUSE: Accolades trailer")

    def test_klasor_kur_oyun_videosu_ekler(self):
        with tempfile.TemporaryDirectory() as t:
            ses = pathlib.Path(t) / 'ses.mp3'
            ses.write_bytes(b'ID3')
            vid = pathlib.Path(t) / 'oyun.mp4'
            vid.write_bytes(b'\x00\x00\x00\x18ftypmp42')
            tema = hf.tema_sec(haber(), hf.tema_girdisi(haber(), None, None, 'esports'))
            k = hf.klasor_kur(pathlib.Path(t) / 'hf', sahte_props(), tema, ses, None, oyun_video=vid)
            html = (k / 'index.html').read_text(encoding='utf-8')
            veri = (k / 'assets' / 'data.js').read_text(encoding='utf-8')
            self.assertIn('p-esports has-video', html)
            self.assertIn('<video id="zm-vid"', html)
            self.assertIn('assets/video/oyun.mp4', html)
            self.assertIn('"oyun_video": "assets/video/oyun.mp4"', veri)
            self.assertTrue((k / 'assets' / 'video' / 'oyun.mp4').exists())


if __name__ == '__main__':
    unittest.main()
