import pathlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tools'))
import haber_oto as h

NOW = datetime(2026, 11, 15, 8, tzinfo=timezone.utc)

def article(oid='oyun-yama-1'):
    return {'id': oid, 'tarih': '2026-11-15', 'oyun': 'Oyun', 'tur': 'guncelleme',
            'kaynaklar': [{'url': 'https://blog.playstation.com/2026/11/15/game-patch/', 'ad': 'PlayStation Blog'}],
            'diller': {d: {'baslik': 'Yeni oyun yaması', 'ozet': 'Yama yayımlandı.',
                          'metin': ' '.join(['Bilgi'] * 60)} for d in h.DILLER},
            'otomasyon': {'konu': oid, 'resmi_url': 'https://blog.playstation.com/2026/11/15/game-patch/',
                          'teyit_zamani': NOW.isoformat(), 'oyuncuya_fayda': 'Kaydetme hatası giderildi; oyuncu yamasını kurabilir.',
                          'hype': 3}}

class HypeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.klasor = pathlib.Path(self.temp.name)
        self.esik = patch.object(h, 'hype_esigi', return_value=7)
        self.esik.start()

    def tearDown(self):
        self.esik.stop()
        self.temp.cleanup()

    def haber(self, hype):
        x = article('hype-test')
        if hype is None:
            del x['otomasyon']['hype']
        else:
            x['otomasyon']['hype'] = hype
        return x

    def test_hype_eksik_veya_gecersiz_reddedilir(self):
        for hype in [None, 0, 11, '7', True]:
            with self.subTest(hype=hype), self.assertRaises(ValueError) as c:
                h.hazirla([], [self.haber(hype)], NOW, self.klasor)
            self.assertIn('otomasyon.hype: 1–10 arası tam sayı gerekli', str(c.exception))

    def test_dusuk_hype_senaryosuz_kabul_edilir(self):
        for hype in [3, 6]:
            with self.subTest(hype=hype):
                self.assertEqual(len(h.hazirla([], [self.haber(hype)], NOW, self.klasor)[1]), 1)

    def test_esige_ulasan_hype_senaryosuz_reddedilir(self):
        with self.assertRaises(ValueError) as c:
            h.hazirla([], [self.haber(7)], NOW, self.klasor)
        self.assertIn('otomasyon.hype eşiğe ulaştı', str(c.exception))

    def test_esige_ulasan_hype_gecerli_senaryoyla_kabul_edilir(self):
        (self.klasor / 'hype-test-tr.json').write_text('{}', encoding='utf-8')
        with patch.object(h, 'senaryo_denetle', return_value=[]):
            self.assertEqual(len(h.hazirla([], [self.haber(7)], NOW, self.klasor)[1]), 1)

class NewsTests(unittest.TestCase):
    def test_duplicate_url_title_and_topic_are_not_published_again(self):
        existing = article()
        for alter in ('url', 'title', 'topic'):
            new = article('another-news')
            if alter != 'url':
                new['kaynaklar'][0]['url'] += 'new'
                new['otomasyon']['resmi_url'] += 'new'
            if alter == 'topic':
                new['diller']['tr']['baslik'] = 'Farklı bir başlık'
                new['otomasyon']['konu'] = existing['otomasyon']['konu']
            self.assertEqual(h.hazirla([existing], [new], NOW)[1], [])

    def test_canonical_tracking_and_https(self):
        self.assertEqual(h.kanonik('https://BLOG.playstation.com/post/?utm_source=rss#x'),
                         h.kanonik('https://blog.playstation.com/post'))
        for url in ['http://blog.playstation.com/post', 'https://blog.playstation.com.evil.example/post',
                    'https://blog.playstation.com@evil.example/post', 'https://127.0.0.1/post',
                    'https://blog.playstation.com/', 'https://steamcommunity.com/id/random-user']:
            x = article(); x['otomasyon']['resmi_url'] = url; x['kaynaklar'][0]['url'] = url
            with self.assertRaises(ValueError): h.hazirla([], [x], NOW)

    def test_missing_locale_old_future_and_unverified_fail(self):
        for kind in ['locale', 'old', 'future', 'unverified']:
            x = article()
            if kind == 'locale': del x['diller']['fr']
            elif kind == 'old': x['tarih'] = '2026-11-10'
            elif kind == 'future': x['tarih'] = '2026-11-16'
            else: x['otomasyon']['resmi_url'] = 'https://www.ign.com/articles/report'
            with self.assertRaises(ValueError): h.hazirla([], [x], NOW)

    def test_daily_and_per_run_caps(self):
        old=[]
        for i in range(12):
            x=article(f'old-{i}'); x['kaynaklar'][0]['url'] += str(i); old.append(x)
        x=article('fresh'); x['kaynaklar'][0]['url'] += 'fresh';x['otomasyon']['resmi_url'] += 'fresh'
        x['diller']['tr']['baslik']='Yeni bir başlık'
        self.assertEqual(h.hazirla(old,[x],NOW)[1],[])
        with self.assertRaises(ValueError): h.hazirla([], [article(str(i)) for i in range(4)], NOW)

    def test_lock_lease_owner_and_expiry(self):
        with tempfile.TemporaryDirectory() as temp:
            db=pathlib.Path(temp)/'lock.sqlite'
            first=h.kilit_al(db,NOW)
            self.assertTrue(first)
            self.assertIsNone(h.kilit_al(db,NOW))
            with self.assertRaises(ValueError): h.kilit_kontrol(db,'wrong',NOW)
            h.kilit_kontrol(db,first,NOW)
            self.assertFalse(h.kilit_birak(db,'wrong'))
            self.assertTrue(h.kilit_birak(db,first))
            second=h.kilit_al(db,NOW)
            third=h.kilit_al(db,NOW+timedelta(hours=2))
            self.assertNotEqual(second,third)
            with self.assertRaises(ValueError): h.kilit_kontrol(db,second,NOW+timedelta(hours=2))

    def test_rss_does_not_treat_remote_text_as_code(self):
        raw=b'<rss><channel><item><title>Patch &amp; update</title><link>https://blog.playstation.com/post/</link><pubDate>Sun, 15 Nov 2026 06:00:00 GMT</pubDate></item></channel></rss>'
        got=h.rss_oku(raw, {'id':'test','ad':'Test','url':'https://blog.playstation.com/'},NOW)
        self.assertEqual(got[0]['baslik'],'Patch & update')
        self.assertEqual(got[0]['url'],'https://blog.playstation.com/post/')

    def test_link_checker_finds_broken_local_link(self):
        with tempfile.TemporaryDirectory() as temp:
            root=pathlib.Path(temp)
            (root/'index.html').write_text('<h1 id="ok">OK</h1><a href="missing.html">link</a>',encoding='utf-8')
            with self.assertRaises(ValueError):h.baglantilari_kontrol(root)
            (root/'missing.html').write_text('<a href="/index.html#ok">back</a>',encoding='utf-8')
            self.assertEqual(h.baglantilari_kontrol(root)['bozuk'],0)

    def test_source_failure_is_reported_without_fabricated_items(self):
        with patch.object(h, 'getir', side_effect=OSError('source unavailable')):
            status, items = h.kaynak_tara(h.CONFIG['kaynaklar'][0], NOW)
        self.assertEqual(status['durum'], 'hata')
        self.assertTrue(status['web_gerekli'])
        self.assertEqual(items, [])

    def test_cli_applies_once_with_owner_token_and_preserves_invalid_attempt(self):
        # Tam CLI akışı yalnız geçici test deposunda çalışır; bu örnek haber yayımlanmaz.
        with tempfile.TemporaryDirectory() as temp:
            root=pathlib.Path(temp)
            for directory in ('tools','otomasyon','data'):(root/directory).mkdir()
            shutil.copy2(h.ROOT/'tools/haber_oto.py',root/'tools/haber_oto.py')
            shutil.copy2(h.ROOT/'otomasyon/kaynaklar.json',root/'otomasyon/kaynaklar.json')
            (root/'data/icerik.json').write_text('[]\n',encoding='utf-8')
            def run(*args):
                return subprocess.run(args,cwd=root,capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(run('git','init','--initial-branch=main').returncode,0)
            self.assertEqual(run('git','add','.').returncode,0)
            self.assertEqual(run('git','-c','user.name=Test','-c','user.email=test@example.invalid','commit','-m','fixture').returncode,0)
            def cli(*args):return run(sys.executable,'tools/haber_oto.py',*args)
            acquired=cli('kilit-al')
            self.assertEqual(acquired.returncode,0,acquired.stderr)
            token=json.loads(acquired.stdout)['token']
            x=article()
            now=datetime.now(timezone.utc)
            x['tarih']=now.astimezone(h.TRT).date().isoformat()
            x['otomasyon']['teyit_zamani']=now.isoformat()
            package=root/'.git/haber-oto/batch.json'
            package.write_text(json.dumps([x]),encoding='utf-8')
            invalid=cli('hazirla','--batch',str(package),'--uygula','--token','wrong')
            self.assertNotEqual(invalid.returncode,0)
            self.assertEqual(json.loads((root/'data/icerik.json').read_text()),[])
            applied=cli('hazirla','--batch',str(package),'--uygula','--token',token)
            self.assertEqual(applied.returncode,0,applied.stderr)
            self.assertEqual(json.loads(applied.stdout)['adet'],1)
            rerun=cli('hazirla','--batch',str(package),'--uygula','--token',token)
            self.assertEqual(rerun.returncode,0,rerun.stderr)
            self.assertEqual(json.loads(rerun.stdout)['adet'],0)
            self.assertEqual(len(json.loads((root/'data/icerik.json').read_text())),1)
            self.assertTrue(json.loads(cli('kilit-birak','--token',token).stdout)['birakildi'])

if __name__ == '__main__': unittest.main()
