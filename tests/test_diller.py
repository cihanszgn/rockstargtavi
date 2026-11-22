import copy
import json
import pathlib
import sys
import unittest
import subprocess
import shutil
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import haber_oto as oto
import sosyal_yayinla as sy
import sosyal_etiket as se
from test_haber_oto import article, NOW


class DilTests(unittest.TestCase):
    def test_cince_tarih_ve_kart_satirlari(self):
        from PIL import Image, ImageDraw, ImageFont
        from diller import tarih_yaz
        from sosyal_derle import metni_sar
        self.assertEqual(tarih_yaz('zh', '2026-11-16'), '2026年11月16日')
        f = ImageFont.truetype(str(ROOT / 'tools/yazi/NotoSansSC-Regular.otf'), 40)
        c = ImageDraw.Draw(Image.new('RGB', (1080, 1350)))
        text = 'Borderlands 社区打破 The Hunt 募捐纪录。'
        lines = metni_sar(c, text, f, 500)
        self.assertTrue(any('Borderlands' in x for x in lines))
        self.assertTrue(any('Hunt' in x for x in lines))
        self.assertFalse(any(x[0] in '，。！？' for x in lines))
        self.assertEqual(''.join(''.join(lines).split()), ''.join(text.split()))
        self.assertTrue(all(c.textlength(x, font=f) <= 500 for x in lines))

    def test_yeni_dil_senaryolari_dogrulanir(self):
        import tempfile
        from test_video_uret import senaryo, haber
        import video_uret
        original = dict(video_uret.AYLAR)
        for lang, date in [('de', '1. Dezember'), ('nl', '1 december'), ('zh', '12月1日')]:
            x, s = haber(), senaryo()
            x['diller'][lang] = copy.deepcopy(x['diller']['tr'])
            x['diller'][lang]['metin'] = x['diller'][lang]['metin'].replace('1 Aralık', date)
            s['dil'] = lang
            for scene in s['sahneler']:
                scene['anlatim'] = scene['anlatim'].replace('1 Aralık', date)
                if scene['sablon'] == 'tarih':
                    scene['veri']['tarih'] = date
            with self.subTest(lang=lang), tempfile.TemporaryDirectory() as tmp:
                path = pathlib.Path(tmp) / f"{x['id']}-{lang}.json"
                path.write_text(json.dumps(s, ensure_ascii=False), encoding='utf-8')
                self.assertEqual(oto.senaryo_dosyasi_denetle(path, x, lang), [])
                self.assertEqual(video_uret.AYLAR, original)

    def test_dil_onerisi_dom(self):
        node = shutil.which('node')
        self.assertIsNotNone(node, 'DOM testi için Node gerekli')
        r = subprocess.run([node, str(ROOT / 'tests/test_dil_oneri.cjs')], capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_yayin_izinleri(self):
        from haber_hatti import yayin_dosyasi_izinli
        for path in ['rehber/minecraft.html', 'de/spiele-news/neu.html', 'nl/gamenieuws/nieuw.html',
                     'zh/youxi-xinwen/xin.html', 'ara-de.json', 'ara-nl.json', 'ara-zh.json',
                     'de/ratgeber/minecraft.html', 'oyun/index.html',
                     'etiket/pc.html', 'en/tag/pc.html', 'news-sitemap.xml']:
            self.assertTrue(yayin_dosyasi_izinli(path), path)
        self.assertTrue(yayin_dosyasi_izinli('video/senaryo/haber-zh.json', {'video/senaryo/haber-zh.json'}))
        for path in ['tools/haber_oto.py', 'video/senaryo/haber-zh.json', '../de/test.html', 'ara-xx.json']:
            self.assertFalse(yayin_dosyasi_izinli(path), path)

    def test_yeni_sayfalar_hreflang_ve_arama(self):
        import contextlib
        import io
        import tempfile
        import site_derle as st
        import sosyal_derle as sd
        from diller import HREFLANG, KAYIT
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            shutil.copytree(ROOT / 'data', root / 'data')
            for lang in ('tr', 'en', 'es', 'fr'):
                for name in KAYIT[lang]['eski'] + (st.TEK_TR if lang == 'tr' else []):
                    dest = root / name
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(ROOT / name, dest)
            with patch.object(st, 'KOK', root), patch.object(sd, 'KOK', root), contextlib.redirect_stdout(io.StringIO()):
                news = sd.yukle()
                st.derle(news)
            for lang in ('de', 'nl', 'zh'):
                path = root / KAYIT[lang]['haber_klasor'] / (news[0]['id'] + '.html')
                page = path.read_text(encoding='utf-8')
                self.assertIn(f'<html lang="{HREFLANG[lang]}"', page)
                for code in HREFLANG.values():
                    self.assertIn(f'hreflang="{code}"', page)
                self.assertIn('hreflang="x-default" href="https://ctrl-agame.com/en/', page)
                index = json.loads((root / f'ara-{lang}.json').read_text(encoding='utf-8'))
                self.assertTrue(any(x['t'] == news[0]['diller'][lang]['baslik'] for x in index))
            self.assertIn('游戏', st.norm('免费游戏'))
            self.assertIn('hreflang="zh-Hans"', (root / 'sitemap.xml').read_text(encoding='utf-8'))

    def test_yedi_dil_zorunlu(self):
        self.assertEqual(set(oto.DILLER), {'tr', 'en', 'es', 'fr', 'de', 'nl', 'zh'})
        for lang in oto.DILLER:
            x = article()
            del x['diller'][lang]
            with self.subTest(lang=lang), self.assertRaisesRegex(ValueError, lang + ':'):
                oto.hazirla([], [x], NOW)

    def test_cince_karakter_sinirlari(self):
        for length, valid in [(159, False), (160, True), (600, True), (601, False)]:
            x = article()
            x['diller']['zh'].update(baslik='游戏更新', ozet='更新已发布。',
                                    metin='游' * 80 + '\n\n' + '游' * (length - 80))
            with self.subTest(length=length):
                if valid:
                    self.assertEqual(len(oto.hazirla([], [x], NOW)[1]), 1)
                else:
                    with self.assertRaisesRegex(ValueError, 'zh:'):
                        oto.hazirla([], [x], NOW)
        x = article()
        x['diller']['zh']['baslik'] = '游' * 51
        with self.assertRaisesRegex(ValueError, 'zh:'):
            oto.hazirla([], [x], NOW)

    def test_youtube_yerellestirme_yalniz_mevcut_diller(self):
        x = article()
        x['diller']['zh'] = {'baslik': '游戏更新', 'ozet': '新补丁已发布。'}
        body = sy.yt_govde('tr', x, sy.paylasim_linki('tr', x, 'youtube'), {})
        self.assertEqual(body['snippet']['defaultLanguage'], 'tr')
        self.assertIn('zh-Hans', body['localizations'])
        for lang in ('en', 'de', 'nl'):
            self.assertEqual(body['localizations'][lang]['title'], x['diller'][lang]['baslik'] + ' ' + se.oyun_etiketleri(x)[0])  # başlığa oyun etiketi eklenir
            self.assertIn('/' + lang + '/', body['localizations'][lang]['description'])
        del x['diller']['nl']
        self.assertNotIn('nl', sy.yt_govde('tr', x, '', {})['localizations'])


if __name__ == '__main__':
    unittest.main()
