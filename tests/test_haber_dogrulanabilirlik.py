import json
import pathlib
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import test_haber_hatti as fixtures

h = fixtures.h


class DogrulanabilirlikTests(unittest.TestCase):
    setUp = fixtures.HatTests.setUp
    tearDown = fixtures.HatTests.tearDown

    def aday(self, i, official=False, game=None, sources=1, title=None):
        c = {'baslik': title or f'Game update {i}', 'url': f'https://www.ign.com/news/{i}',
             'tarih': datetime.now(timezone.utc).isoformat(), 'on_puan': 5, 'oyun_eslesme': game}
        if official:
            c['url'] = f'https://news.xbox.com/en-us/2026/11/16/{i}/'
        if sources > 1:
            c['ilgili_kaynaklar'] = [{'url': f'https://www.gamespot.com/articles/{i}'}]
        return c

    def test_single_source_never_calls_writer_and_is_remembered(self):
        c = self.aday(0)
        with patch.object(self.hat, 'yaz') as writer:
            self.assertEqual(self.hat.adaylari_isle([c]), [])
        writer.assert_not_called()
        self.assertEqual(self.hat.gorulen[h.adres(c)]['neden'], 'tek kaynak, resmî teyit yok')

    def test_opinion_filter_only_touches_discovery(self):
        for title in ('Why the new game matters', 'Fans remember Game', 'Analyst predicts sales',
                      'Player turns hero into tank', 'Is this the future?', 'Community-run event'):
            self.assertIsNotNone(h.kesif_engeli(self.aday(0, sources=2, title=title)))
            self.assertIsNone(h.kesif_engeli(self.aday(1, official=True, title=title)))

    def test_same_event_merge_supplies_second_source(self):
        a, b = self.aday(0), self.aday(1)
        b['url'] = 'https://www.gamespot.com/articles/game'
        b['baslik'] = a['baslik']
        merged = h.olaylari_birlestir([a, b])
        self.assertEqual(len(merged), 1)
        self.assertIsNone(h.kesif_engeli(merged[0]))
        self.assertIsNotNone(h.kesif_engeli(h.olaylari_birlestir([a, dict(a)])[0]))

    def test_matched_official_url_and_epic_have_official_priority(self):
        press = self.aday(0, sources=2)
        press.update(takipli=True, on_puan=10)
        matched = dict(press, resmi_url='https://news.xbox.com/en-us/game/', takipli=False, on_puan=1)
        epic = dict(press, url='https://store.epicgames.com/en-US/p/game', takipli=False, on_puan=1)
        for c in (matched, epic):
            self.assertGreater(h.siralama(c), h.siralama(press))
            self.assertIsNone(h.kesif_engeli(c))

    def test_source_limit_keeps_official_before_followed_discovery(self):
        source = {'id': 'steam', 'aday_siniri': 1}
        candidates = [self.aday(0, title='GTA 6 update'), self.aday(1, official=True)]
        with patch.object(h.oto, '_kaynak_tara', return_value=({'id': 'steam'}, candidates)):
            status, kept = h.oto.kaynak_tara(source, h.oto.simdi())
        self.assertTrue(h.resmi_aday(kept[0]))
        self.assertEqual(status['sinir_elendi'], 1)

    def test_two_attempts_per_game_including_rejections(self):
        candidates = [self.aday(i, official=True, game='same') for i in range(4)] + [self.aday(5, official=True, game='other')]
        with patch.object(self.hat, 'yaz', return_value=None) as writer:
            self.hat.adaylari_isle(candidates)
        self.assertEqual([x.args[0]['baslik'] for x in writer.call_args_list],
                         [candidates[i]['baslik'] for i in (0, 1, 4)])

    def test_two_discovery_attempts_and_early_finish(self):
        candidates = [self.aday(i, sources=2) for i in range(7)]
        with patch.object(self.hat, 'yaz', return_value=None) as writer:
            self.hat.adaylari_isle(candidates)
        self.assertEqual(writer.call_count, 2)
        self.assertIn('keşif', self.hat.sonuc['erken_bitis'])

    def test_discovery_limit_does_not_skip_remaining_official(self):
        candidates = [self.aday(i, sources=2) for i in range(3)] + [self.aday(4, official=True)]
        with patch.object(self.hat, 'yaz', return_value=None) as writer:
            self.hat.adaylari_isle(candidates)
        self.assertEqual(writer.call_count, 3)
        self.assertEqual(writer.call_args.args[0], candidates[-1])

    def test_one_healthy_local_model_even_after_invalid_chunk(self):
        (self.root / 'data/oyunlar.json').write_text('[]', encoding='utf8')
        self.hat.config['eleme'] = [{'ad': 'gemma', 'tur': 'yerel', 'komut': ['unused']},
                                    {'ad': 'qwen', 'tur': 'yerel', 'komut': ['unused']}]
        candidates = [self.aday(i, official=True) for i in range(8)]
        def model(spec, prompt):
            if '--saglik' in spec['komut']:
                return '{}'
            if '"aday_id": 0' in prompt:
                return '{broken'
            return json.dumps({'kararlar': [{'aday_id': i, 'karar': 'al', 'hype': 5, 'neden': 'new'} for i in range(4, 8)]})
        with patch.object(self.hat, 'model', side_effect=model) as call:
            result = self.hat.ele(candidates)
        self.assertEqual(len(result), 8)
        self.assertEqual([x.args[0]['ad'] for x in call.call_args_list], ['gemma'] * 3)
        self.assertNotIn(h.adres(candidates[0]), self.hat.gorulen)

    def test_health_fallback_only_happens_before_selection(self):
        self.hat.config['eleme'] = [{'ad': 'gemma', 'komut': ['x']}, {'ad': 'qwen', 'komut': ['y']}]
        with patch.object(self.hat, 'model', side_effect=[TimeoutError('health'), '{}']) as call:
            self.assertEqual(self.hat.yerel_sec()['ad'], 'qwen')
            self.assertEqual(self.hat.yerel_sec()['ad'], 'qwen')
        self.assertEqual(call.call_count, 2)

    def test_pull_change_restarts_before_scan_and_keeps_lease(self):
        with patch.object(self.hat, 'hazirlik', side_effect=h.YenidenBaslat('new-head')), \
             patch.object(self.hat, 'tara') as scan, patch.object(self.hat, 'bitir') as finish:
            def child(head, token):
                self.assertEqual(head, 'new-head')
                h.oto.kilit_kontrol(self.hat.state / 'kilit.sqlite', token)
                self.assertIsNone(h.oto.kilit_al(self.hat.state / 'kilit.sqlite'))
                return 0
            with patch.object(self.hat, 'yeniden_baslat', side_effect=child) as restart:
                self.assertEqual(self.hat.calistir(), 0)
        restart.assert_called_once()
        scan.assert_not_called()
        finish.assert_not_called()
        token = h.oto.kilit_al(self.hat.state / 'kilit.sqlite')
        self.assertIsNotNone(token)
        h.oto.kilit_birak(self.hat.state / 'kilit.sqlite', token)

    def test_second_restart_is_blocked_and_lock_released(self):
        token = h.oto.kilit_al(self.hat.state / 'kilit.sqlite')
        with patch.object(self.hat, 'hazirlik', side_effect=h.YenidenBaslat('again')), \
             patch.object(self.hat, 'yeniden_baslat') as restart:
            self.assertEqual(self.hat.calistir({'token': token, 'start': self.hat.start,
                'deadline': self.hat.deadline}, 'first-head'), 1)
        restart.assert_not_called()
        self.assertIn('döngüsü', self.hat.sonuc['hata'])

    def test_real_pull_and_new_python_process(self):
        tools = self.root / 'tools'
        tools.mkdir()
        child = tools / 'haber_hatti.py'
        child.write_text('raise RuntimeError("old code ran")', encoding='utf8')
        subprocess.run(['git', 'add', 'tools'], cwd=self.root, check=True, capture_output=True)
        subprocess.run(['git', 'commit', '-m', 'old'], cwd=self.root, check=True, capture_output=True)
        clone = self.root.parent / (self.root.name + '-clone')
        try:
            subprocess.run(['git', 'clone', str(self.root), str(clone)], check=True, capture_output=True)
            child.write_text('import json,sys,sqlite3,pathlib\nd=json.load(sys.stdin)\np=pathlib.Path(".git/haber-oto")\nc=sqlite3.connect(p/"kilit.sqlite")\nassert c.execute("select token from lease where id=1").fetchone()[0]==d["token"]\n(p/"fresh-process.txt").write_text("new code")\n', encoding='utf8')
            subprocess.run(['git', 'add', 'tools'], cwd=self.root, check=True, capture_output=True)
            subprocess.run(['git', 'commit', '-m', 'new'], cwd=self.root, check=True, capture_output=True)
            runner = h.Hat(clone, deneme=True, config={})
            self.assertEqual(runner.calistir(), 0)
            self.assertEqual((runner.state / 'fresh-process.txt').read_text(), 'new code')
            self.assertFalse((runner.state / 'sonuc.json').exists())
        finally:
            h.shutil.rmtree(clone, ignore_errors=True)

    def test_cross_source_same_event_merges_rephrased_headlines_without_merging_distinct_events(self):
        oyunlar = [('gta 6', 'gta vi'), ('world of warcraft', 'world of warcraft'), ('wow', 'world of warcraft')]
        a = {'baslik': 'GTA 6 day-one sales are enormous, estimates suggest, making previous $2 billion opening weekend predictions seem conservative',
             'url': 'https://www.eurogamer.net/gta-6-day-one-sales', 'kaynak': 'eurogamer'}
        b = {'baslik': 'GTA 6 sold around 25 million copies and made $2.36 billion in its first day, estimates suggest',
             'url': 'https://www.videogameschronicle.com/news/gta-6-25-million/', 'kaynak': 'vgc'}
        c = {'baslik': 'The first GTA 6 speedrun is less than 40 hours',
             'url': 'https://www.gamesradar.com/gta-6-speedrun/', 'kaynak': 'gamesradar'}
        jp1 = {'baslik': '「アズールプロミリア」のガチャ情報発表', 'url': 'https://game.watch.impress.co.jp/docs/1.html', 'kaynak': 'gamewatch'}
        jp2 = {'baslik': '「アズールプロミリア」新キャラ登場', 'url': 'https://game.watch.impress.co.jp/docs/2.html', 'kaynak': 'gamewatch'}
        v1 = {'baslik': 'Zenless Zone Zero version 3.4 update launches December 2', 'url': 'https://www.gematsu.com/zzz-3-4', 'kaynak': 'gematsu'}
        v2 = {'baslik': 'Zenless Zone Zero version 3.5 update launches December 2', 'url': 'https://www.ign.com/news/zzz-3-5', 'kaynak': 'ign'}
        merged = h.olaylari_birlestir([a, b, c, jp1, jp2, v1, v2], oyunlar)
        self.assertEqual(len(merged), 6)
        self.assertEqual(len(merged[0]['ilgili_kaynaklar']), 2)
        self.assertIsNone(h.kesif_engeli(merged[0]))

    def test_guide_and_deal_filters_block_discovery_while_concrete_announcements_pass(self):
        for title in ('How to make money in GTA 6', 'GTA 6 Daily Driver Mission Walkthrough',
                      'All JoySystem Video Games In GTA 6', 'Surprise PS5 Black Friday Deals for GTA 6'):
            self.assertEqual(h.kesif_engeli(self.aday(0, sources=2, title=title)), 'rehber/liste/fırsat başlığı')
            self.assertIsNone(h.kesif_engeli(self.aday(1, official=True, title=title)))
        for title in ('Zenless Zone Zero version 3.4 update launches December 2',
                      'Xenoblade Chronicles 3 version 3.0.0 is now available, patch notes revealed',
                      'New World of Warcraft Forever patch notes buff Paladins'):
            self.assertIsNone(h.kesif_engeli(self.aday(2, sources=1, title=title)))

    def test_anti_cheat_official_announcement_is_not_blocked_as_cheats(self):
        (self.root / 'data/oyunlar.json').write_text('[]', encoding='utf-8')
        official = {'baslik': 'An Update from the Anti-Cheat Team - 11/19/2026',
                    'url': 'https://steamcommunity.com/games/1172470/announcements/detail/123',
                    'resmi_aday': True, 'tarih': datetime.now(timezone.utc).isoformat()}
        cheat = {'baslik': 'Free cheats for GTA 6 released online',
                 'url': 'https://www.ign.com/news/cheat', 'tarih': datetime.now(timezone.utc).isoformat()}
        decisions = [{'aday_id': 0, 'karar': 'al', 'hype': 5, 'neden': 'resmi'},
                     {'aday_id': 1, 'karar': 'al', 'hype': 5, 'neden': 'hile'}]
        with patch.object(self.hat, 'zincir', return_value=decisions):
            selected = self.hat.ele([official, cheat])
        self.assertEqual([x['baslik'] for x in selected], [official['baslik']])

    def test_subprocess_error_combines_stderr_and_stdout_for_quota_detection(self):
        code = 'import sys; sys.stderr.write("Reading prompt from stdin...\\n"); sys.stdout.write("{\\"error\\":\\"You have hit your usage limit\\"}\\n"); sys.exit(1)'
        with self.assertRaises(RuntimeError) as ctx:
            h.calistir([sys.executable, '-c', code], self.root, 10)
        self.assertIn('Reading prompt from stdin', str(ctx.exception))
        self.assertIn('usage limit', str(ctx.exception))
        self.assertEqual(h.kota_suresi(str(ctx.exception)), 43200)
