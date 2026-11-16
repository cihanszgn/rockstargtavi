import pathlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock
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
        for lang in h.DILLER:
            (self.klasor / f'hype-test-{lang}.json').write_text('{}', encoding='utf-8')
        with patch.object(h, 'senaryo_denetle', return_value=[]):
            self.assertEqual(len(h.hazirla([], [self.haber(7)], NOW, self.klasor)[1]), 1)

    def test_missing_locale_requires_explicit_drop_but_turkish_cannot_drop(self):
        x = self.haber(7)
        for lang in h.DILLER:
            (self.klasor / f'hype-test-{lang}.json').write_text('{}', encoding='utf-8')
        with patch.object(h, 'senaryo_denetle', return_value=[]):
            (self.klasor / 'hype-test-fr.json').unlink()
            with self.assertRaisesRegex(ValueError, 'fr:'):
                h.hazirla([], [x], NOW, self.klasor)
            x['otomasyon']['senaryo_atlanan'] = {'fr': 'Tek düzeltme sonrası: geçersiz tarih'}
            self.assertEqual(len(h.hazirla([], [x], NOW, self.klasor)[1]), 1)
            (self.klasor / 'hype-test-tr.json').unlink()
            x['otomasyon']['senaryo_atlanan']['tr'] = 'hata'
            with self.assertRaises(ValueError):
                h.hazirla([], [x], NOW, self.klasor)

class NewsTests(unittest.TestCase):
    def test_raw_source_bodies_remain_internal_and_existing_content_is_preserved(self):
        new, old = article('new'), article('old')
        new['otomasyon']['kaynak_metinleri'] = [{'kaynak_metni': 'raw article body'}]
        old['otomasyon']['kaynak_metinleri'] = [{'kaynak_metni': 'already existing'}]
        public = h.yayin_verisi([new, old], [new])
        self.assertNotIn('kaynak_metinleri', public[0]['otomasyon'])
        self.assertIs(public[1], old)
        self.assertIn('kaynak_metinleri', new['otomasyon'])

    def test_python_source_timestamp_is_recent_read_evidence(self):
        x = article()
        x['otomasyon']['teyit_zamani'] = (NOW - timedelta(hours=3)).isoformat()
        url = x['otomasyon']['resmi_url']
        x['otomasyon']['kaynak_metinleri'] = [dict(url=url, kaynak_metni='Gerçek kaynak metni',
            kaynak_metni_url='https://blog.playstation.com/feed/', kaynak_metni_alani='content:encoded',
            kaynak_metni_zamani=NOW.isoformat())]
        self.assertEqual(len(h.hazirla([], [x], NOW)[1]), 1)
        x['otomasyon']['kaynak_metinleri'][0]['kaynak_metni_zamani'] = (NOW-timedelta(hours=3)).isoformat()
        with self.assertRaises(ValueError):
            h.hazirla([], [x], NOW)
    def test_followed_game_matching_uses_word_boundaries(self):
        self.assertFalse(h.oyun_eslesir('Trust keyboard sale', 'rust'))
        self.assertTrue(h.oyun_eslesir('Rust update', 'rust'))
        self.assertTrue(h.oyun_eslesir('New GTA 6 announcement', 'gta 6'))

    def test_date_prefilter_and_unknown(self):
        items = [{'baslik': '11/05/26 Old Nintendo', 'url': 'https://www.nintendo.com/us/whatsnew/old/'},
                 {'baslik': 'New', 'tarih': NOW.isoformat()}, {'baslik': 'Unknown'}]
        self.assertEqual([x['baslik'] for x in h.tarih_suz(items, NOW)], ['New', 'Unknown'])

    def test_atom_rdf_and_steam_official_parsers(self):
        atom = b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>FFXIV patch</title><link href="https://na.finalfantasyxiv.com/lodestone/news/detail/a"/><published>2026-11-15T06:00:00Z</published></entry></feed>'
        source = {'id': 'ffxiv', 'ad': 'FFXIV', 'rss': 'https://example.org/feed'}
        with patch.object(h, 'getir', return_value=atom):
            status, items = h.kaynak_tara(source, NOW)
        self.assertEqual(status['adet'], 1)
        self.assertTrue(items[0]['resmi_aday'])
        rdf = b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns="http://purl.org/rss/1.0/"><item><title>JP patch</title><link>https://game.watch.impress.co.jp/docs/a.html</link></item></rdf:RDF>'
        self.assertEqual(h.rss_oku(rdf, source, NOW)[0]['baslik'], 'JP patch')
        source = {'id': 'valve', 'ad': 'Valve', 'api': 'https://api.steampowered.com/a', 'bicim': 'steam', 'appid': 730}
        raw = {'appnews': {'newsitems': [{'title': 'Patch', 'gid': '123', 'date': int(NOW.timestamp()), 'feedname': 'steam_community_announcements'}, {'title': 'Press', 'feedname': 'pcgamer'}]}}
        with patch.object(h, 'getir', return_value=json.dumps(raw).encode()), \
                patch.object(h, 'steam_adresi', return_value='https://steamcommunity.com/games/CSGO/announcements/detail/456') as resolve:
            status, items = h.kaynak_tara(source, NOW)
        self.assertEqual(len(items), 1)
        self.assertTrue(h.resmi(items[0]['url']))
        resolve.assert_called_once_with('123')

    def test_primary_confirmation_requires_two_independent_named_reports(self):
        x = article()
        x['kaynaklar'] = [{'ad': 'IGN', 'url': 'https://www.ign.com/articles/interview'}, {'ad': 'VGC', 'url': 'https://www.videogameschronicle.com/news/interview/'}]
        x['otomasyon'].update(teyit_turu='birincil', resmi_url='', birincil_kaynak={'kisi': 'Jane Smith', 'gorev': 'Director', 'kurum': 'Studio', 'tur': 'roportaj', 'olgu': 'Yeni yamanın oyunculara sunulduğunu açıkladı.'}, capraz_kaynaklar=[s['url'] for s in x['kaynaklar']])
        for content in x['diller'].values():
            content['metin'] += ' IGN VGC'
        self.assertEqual(len(h.hazirla([], [x], NOW)[1]), 1)
        valid = json.loads(json.dumps(x))
        for field in ('kisi', 'gorev', 'kurum'):
            invalid = json.loads(json.dumps(valid)); del invalid['otomasyon']['birincil_kaynak'][field]
            with self.assertRaises(ValueError): h.hazirla([], [invalid], NOW)
        invalid = json.loads(json.dumps(valid)); invalid['otomasyon']['capraz_kaynaklar'].pop()
        with self.assertRaises(ValueError): h.hazirla([], [invalid], NOW)
        invalid = json.loads(json.dumps(valid)); invalid['diller']['fr']['metin'] = ' '.join(['Texte'] * 60)
        with self.assertRaises(ValueError): h.hazirla([], [invalid], NOW)
        invalid = json.loads(json.dumps(valid)); invalid['diller']['en']['baslik'] = 'New game reportedly leaked'
        with self.assertRaises(ValueError): h.hazirla([], [invalid], NOW)
        invalid = json.loads(json.dumps(valid))
        invalid['kaynaklar'][1] = {'ad': 'Eurogamer', 'url': 'https://www.eurogamer.net/report'}
        invalid['otomasyon']['capraz_kaynaklar'][1] = invalid['kaynaklar'][1]['url']
        with self.assertRaises(ValueError): h.hazirla([], [invalid], NOW)
        x['otomasyon']['birincil_kaynak']['tur'] = 'sizinti'
        with self.assertRaises(ValueError): h.hazirla([], [x], NOW)
        x['otomasyon']['birincil_kaynak']['tur'] = 'roportaj'
        x['kaynaklar'][1]['url'] = 'https://www.ign.com/articles/another'
        x['otomasyon']['capraz_kaynaklar'] = [s['url'] for s in x['kaynaklar']]
        with self.assertRaises(ValueError): h.hazirla([], [x], NOW)

    def test_steam_news_gid_is_resolved_to_real_announcement_id(self):
        response = MagicMock()
        response.__enter__.return_value.geturl.return_value = 'https://steamcommunity.com/games/CSGO/announcements/detail/456'
        with patch.object(h.urllib.request, 'urlopen', return_value=response):
            self.assertEqual(h.steam_adresi('123'), 'https://steamcommunity.com/games/CSGO/announcements/detail/456')
        response.__enter__.return_value.geturl.return_value = 'https://steamcommunity.com/games/CSGO/announcements'
        with patch.object(h.urllib.request, 'urlopen', return_value=response), self.assertRaises(ValueError):
            h.steam_adresi('123')

    def test_source_filters_dates_before_cap_and_does_not_accept_html_feed(self):
        items = [{'baslik': f'Old {i}', 'tarih': '2026-11-01T00:00:00Z'} for i in range(10)]
        items += [{'baslik': 'Fresh', 'tarih': NOW.isoformat()}, {'baslik': 'Unknown'}]
        source = {'id': 'test', 'ad': 'Test'}
        with patch.object(h, '_kaynak_tara', return_value=({'id': 'test', 'durum': 'ok'}, items)):
            status, kept = h.kaynak_tara(source, NOW)
        self.assertEqual(status['tarih_elendi'], 10)
        self.assertEqual([x['baslik'] for x in kept], ['Fresh', 'Unknown'])
        with self.assertRaises(ValueError): h.rss_oku(b'<html><body>Not a feed</body></html>', source, NOW)

    def test_source_cap_keeps_followed_news_before_newer_unrelated_items(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp); (root / 'data').mkdir()
            (root / 'data/oyunlar.json').write_text('[{"ad":"Takipli","eslesme":[]}]', encoding='utf-8')
            source = {'id': 'test', 'ad': 'Test', 'aday_siniri': 1}
            unrelated = {'baslik': 'Other game', 'tarih': NOW.isoformat()}
            followed = {'baslik': 'Takipli concrete patch', 'tarih': (NOW-timedelta(hours=5)).isoformat()}
            with patch.object(h, 'ROOT', root), patch.object(h, '_kaynak_tara', return_value=({'id': 'test', 'durum': 'ok'}, [unrelated, followed])):
                status, kept = h.kaynak_tara(source, NOW)
                self.assertEqual(kept[0]['baslik'], followed['baslik'])
                self.assertEqual(status['sinir_elendi'], 1)
                followed['tarih'] = None
                self.assertEqual(h.kaynak_tara(source, NOW)[1][0]['baslik'], unrelated['baslik'])

    def test_epic_api_is_official_confirmation(self):
        x = article()
        url = next(s['api'] for s in h.CONFIG['kaynaklar'] if s['id'] == 'epic')
        store = 'https://store.epicgames.com/en-US/p/game'
        x['kaynaklar'] = [{'ad': 'Epic API', 'url': url}, {'ad': 'Store', 'url': store}]
        x['otomasyon'].update(teyit_turu='resmi', resmi_url=url, resmi_veri={
            'api_url': url, 'oyun': 'Game', 'alinma_zamani': NOW.isoformat(), 'ulke': 'TR',
            'magaza_url': store, 'baslangic': (NOW - timedelta(hours=1)).isoformat(), 'bitis': (NOW + timedelta(days=6)).isoformat()})
        self.assertEqual(len(h.hazirla([], [x], NOW)[1]), 1)
        other = json.loads(json.dumps(x))
        other['id'] = other['otomasyon']['konu'] = 'other-game'
        for content in other['diller'].values(): content['baslik'] = 'Other game'
        other['kaynaklar'][1]['url'] += '-other'
        other['otomasyon']['resmi_veri']['magaza_url'] += '-other'
        self.assertEqual(len(h.hazirla([x], [other], NOW)[1]), 1)
        x['otomasyon']['resmi_veri']['api_url'] = 'https://evil.example/api'
        with self.assertRaises(ValueError): h.hazirla([], [x], NOW)

    def test_epic_scanner_preserves_only_free_unexpired_campaign_facts(self):
        source = next(s for s in h.CONFIG['kaynaklar'] if s['id'] == 'epic')
        offer = {'startDate': (NOW - timedelta(hours=1)).isoformat(), 'endDate': (NOW + timedelta(days=6)).isoformat(), 'discountSetting': {'discountPercentage': 0}}
        game = {'title': 'Game', 'productSlug': 'game/home', 'promotions': {'promotionalOffers': [{'promotionalOffers': [offer]}]}}
        raw = {'data': {'Catalog': {'searchStore': {'elements': [game]}}}}
        with patch.object(h, 'getir', return_value=json.dumps(raw).encode()):
            status, items = h.kaynak_tara(source, NOW)
        self.assertEqual(status['durum'], 'ok')
        self.assertEqual(items[0]['resmi_veri']['oyun'], 'Game')
        self.assertEqual(items[0]['url'], 'https://store.epicgames.com/en-US/p/game')
        self.assertEqual(items[0]['resmi_veri']['api_url'], source['api'])

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
