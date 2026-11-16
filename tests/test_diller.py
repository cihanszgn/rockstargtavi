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
from test_haber_oto import article, NOW


class DilTests(unittest.TestCase):
    def test_dil_onerisi_dom(self):
        node = shutil.which('node')
        self.assertIsNotNone(node, 'DOM testi için Node gerekli')
        r = subprocess.run([node, str(ROOT / 'tests/test_dil_oneri.cjs')], capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_yayin_izinleri(self):
        from haber_hatti import yayin_dosyasi_izinli
        for path in ['rehber/minecraft.html', 'de/spiele-news/neu.html', 'nl/gamenieuws/nieuw.html',
                     'zh/youxi-xinwen/xin.html', 'ara-de.json', 'ara-nl.json', 'ara-zh.json',
                     'de/ratgeber/minecraft.html', 'oyun/index.html']:
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
            x['diller']['zh'] = {'baslik': '游戏更新', 'ozet': '修复存档问题。', 'metin': '游戏更新修复存档问题。' * 12}
            del x['diller'][lang]
            with self.subTest(lang=lang), self.assertRaisesRegex(ValueError, lang + ':'):
                oto.hazirla([], [x], NOW)

    def test_cince_karakter_sinirlari(self):
        for length, valid in [(99, False), (100, True), (600, True), (601, False)]:
            x = article()
            x['diller']['zh'] = {'baslik': '游戏更新', 'ozet': '更新已发布。', 'metin': '游' * length}
            with self.subTest(length=length):
                if valid:
                    self.assertEqual(len(oto.hazirla([], [x], NOW)[1]), 1)
                else:
                    with self.assertRaisesRegex(ValueError, 'zh:'):
                        oto.hazirla([], [x], NOW)
        x['diller']['zh']['metin'] = '游' * 100
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
            self.assertEqual(body['localizations'][lang]['title'], x['diller'][lang]['baslik'])
            self.assertIn('/' + lang + '/', body['localizations'][lang]['description'])
        del x['diller']['nl']
        self.assertNotIn('nl', sy.yt_govde('tr', x, '', {})['localizations'])


if __name__ == '__main__':
    unittest.main()
