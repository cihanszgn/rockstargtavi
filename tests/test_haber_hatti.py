import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tools'))
import haber_hatti as h


class HatTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        for args in [('init', '--initial-branch=main'), ('config', 'user.name', 'Test'),
                     ('config', 'user.email', 'test@example.invalid')]:
            subprocess.run(['git', *args], cwd=self.root, check=True, capture_output=True)
        (self.root / 'data').mkdir()
        (self.root / 'data/icerik.json').write_text('[]\n', encoding='utf-8')
        (self.root / 'koru.txt').write_bytes(b'original\r\n')
        subprocess.run(['git', 'add', '.'], cwd=self.root, check=True, capture_output=True)
        subprocess.run(['git', 'commit', '-m', 'fixture'], cwd=self.root, check=True, capture_output=True)
        self.hat = h.Hat(self.root, deneme=True, config={'eleme': [], 'yazar': [], 'denetci': []})

    def tearDown(self):
        self.temp.cleanup()

    def test_json_retry_then_next_model_in_order(self):
        models = [{'ad': 'local'}, {'ad': 'backup'}]
        with patch.object(self.hat, 'model', side_effect=['bad', '{}', '{"ok":true}']) as run:
            result = self.hat.zincir('eleme', models, 'prompt', lambda x: x if x.get('ok') is True else h.hata('schema'))
        self.assertTrue(result['ok'])
        self.assertEqual([c.args[0]['ad'] for c in run.call_args_list], ['local', 'local', 'backup'])

    def test_invalid_json_reasks_same_model_once(self):
        with patch.object(self.hat, 'model', side_effect=['bad', '{"ok":true}']) as run:
            self.hat.zincir('eleme', [{'ad': 'local'}], 'prompt', lambda x: x)
        self.assertEqual(run.call_count, 2)

    def test_writer_model_order_and_forbidden_edit_rejects_output(self):
        models = h.oku(h.ROOT / 'otomasyon/modeller.json')['yazar']
        def model(spec, prompt):
            if spec['ad'] == 'opencode/big-pickle':
                (self.root / 'koru.txt').write_bytes(b'illegal')
                return '{"ok":true}'
            if spec['ad'] == 'haiku':
                raise RuntimeError('quota')
            return '{"ok":true}'
        with patch.object(self.hat, 'model', side_effect=model) as run:
            self.assertTrue(self.hat.zincir('yazar', models, 'write', lambda x: x)['ok'])
        self.assertEqual([x.args[0]['ad'] for x in run.call_args_list], ['opencode/big-pickle', 'haiku', 'sonnet'])
        self.assertEqual((self.root / 'koru.txt').read_bytes(), b'original\r\n')
        self.assertFalse(self.hat.sonuc['modeller'][0]['tuttu'])

    def test_unavailable_local_model_is_not_repeated_for_every_chunk(self):
        models = [{'ad': 'local'}, {'ad': 'backup'}]
        with patch.object(self.hat, 'model', side_effect=[TimeoutError('timeout'), '{"ok":true}', '{"ok":true}']) as run:
            for _ in range(2):
                self.hat.zincir('eleme', models, 'prompt', lambda x: x)
        self.assertEqual([c.args[0]['ad'] for c in run.call_args_list], ['local', 'backup', 'backup'])

    def test_writer_forbidden_changes_restored_including_index_and_new_files(self):
        before = h.Anlik(self.root)
        (self.root / 'koru.txt').write_text('tampered', encoding='utf-8')
        (self.root / 'evil.txt').write_text('new', encoding='utf-8')
        subprocess.run(['git', 'add', '.'], cwd=self.root, check=True, capture_output=True)
        self.assertEqual(set(before.koru(set())), {'koru.txt', 'evil.txt'})
        self.assertEqual((self.root / 'koru.txt').read_bytes(), b'original\r\n')
        self.assertFalse((self.root / 'evil.txt').exists())
        self.assertEqual(self.hat.git('status', '--porcelain'), '')

    def test_audit_rejection_removes_article_and_hype_is_rechecked(self):
        articles = [{'id': 'a', 'otomasyon': {'hype': 3}}, {'id': 'b', 'otomasyon': {'hype': 3}}]
        self.hat.config['denetci'] = [{'ad': 'sonnet'}]
        verdict = {'kararlar': [{'id': 'a', 'karar': 'ret', 'neden': 'kaynak yok', 'hype': 3},
                                {'id': 'b', 'karar': 'onay', 'neden': 'uygun', 'hype': 8}]}
        with patch.object(self.hat, 'model', return_value=json.dumps(verdict)), patch.object(self.hat, 'prompt', return_value='audit'):
            self.assertEqual(self.hat.denetle(articles), [])
        self.assertEqual(len(self.hat.sonuc['atlanan']), 2)

    def test_auditor_failure_never_publishes(self):
        self.hat.config['denetci'] = [{'ad': 'sonnet'}, {'ad': 'opus'}]
        with patch.object(self.hat, 'model', side_effect=RuntimeError('quota')) as run, patch.object(self.hat, 'prompt', return_value='audit'):
            self.assertEqual(self.hat.denetle([{'id': 'a'}]), [])
        self.assertEqual([c.args[0]['ad'] for c in run.call_args_list], ['sonnet', 'opus'])

    def test_failed_audit_blocks_live_publish_path(self):
        self.hat.deneme = False
        self.hat.config['denetci'] = [{'ad': 'sonnet'}, {'ad': 'opus'}]
        scan = {'kaynaklar': [], 'adaylar': [{'baslik': 'test'}]}
        with patch.object(self.hat, 'hazirlik'), patch.object(self.hat, 'tara', return_value=scan), \
                patch.object(self.hat, 'ele', return_value=scan['adaylar']), \
                patch.object(self.hat, 'yaz', return_value={'id': 'test'}), \
                patch.object(self.hat, 'model', side_effect=RuntimeError('quota')), \
                patch.object(self.hat, 'prompt', return_value='audit'), patch.object(self.hat, 'yayinla') as publish:
            self.assertEqual(self.hat.calistir(), 0)
        publish.assert_not_called()

    def test_finalization_failure_still_releases_lock(self):
        with patch.object(self.hat, 'hazirlik', side_effect=ValueError('stop')), \
                patch.object(self.hat, 'bitir', side_effect=OSError('disk error')):
            with self.assertRaises(OSError):
                self.hat.calistir()
        token = h.oto.kilit_al(self.hat.state / 'kilit.sqlite')
        self.assertIsNotNone(token)
        h.oto.kilit_birak(self.hat.state / 'kilit.sqlite', token)

    def test_dry_run_restores_scenarios_and_never_calls_publish(self):
        scan = {'kaynaklar': [], 'adaylar': [{'baslik': 'test'}]}
        def write(_):
            path = self.root / 'video/senaryo/test-tr.json'
            path.parent.mkdir(parents=True)
            path.write_text('{}', encoding='utf-8')
            return {'id': 'test'}
        with patch.object(self.hat, 'hazirlik'), patch.object(self.hat, 'tara', return_value=scan), \
                patch.object(self.hat, 'ele', return_value=scan['adaylar']), \
                patch.object(self.hat, 'yaz', side_effect=write), \
                patch.object(self.hat, 'denetle', return_value=[{'id': 'test'}]), \
                patch.object(self.hat, 'paket_kontrol', return_value=[{'id': 'test'}]), \
                patch.object(self.hat, 'yayinla') as publish:
            self.assertEqual(self.hat.calistir(), 0)
        publish.assert_not_called()
        self.assertFalse((self.root / 'video/senaryo/test-tr.json').exists())
        self.assertEqual(self.hat.git('status', '--porcelain'), '')
        self.assertTrue((self.hat.state / 'sonuc.json').exists())

    def test_dirty_tree_exits_before_pull_and_preserves_user_file(self):
        (self.root / 'koru.txt').write_text('user', encoding='utf-8')
        with patch.object(self.hat, 'tara') as scan:
            self.assertEqual(self.hat.calistir(), 1)
        scan.assert_not_called()
        self.assertEqual((self.root / 'koru.txt').read_text(), 'user')

    def test_filter_requires_exact_ids_and_bounded_integer_scores(self):
        candidates = [{'aday_id': 0}, {'aday_id': 1}]
        with self.assertRaises(ValueError):
            h.eleme_sema({'kararlar': [{'aday_id': 0, 'karar': 'al', 'hype': True, 'neden': 'x'}]}, candidates)

    def test_selection_prioritizes_followed_games_and_logs_run_cap(self):
        (self.root / 'data/oyunlar.json').write_text('[{"ad":"Takipli","eslesme":[]}]', encoding='utf-8')
        candidates = [{'baslik': 'Takipli yama' if i == 0 else f'Oyun {i}'} for i in range(5)]
        decisions = [{'aday_id': i, 'karar': 'al', 'hype': 4 if i == 0 else 9, 'neden': 'yeni'} for i in range(5)]
        with patch.object(self.hat, 'zincir', side_effect=[decisions[:4], decisions[4:]]):
            result = self.hat.ele(candidates)
        self.assertEqual(len(result), 5)
        self.assertEqual(result[0]['baslik'], 'Takipli yama')
        self.assertEqual(len(self.hat.sonuc['atlanan']), 0)

    def test_secret_environment_is_allowlisted(self):
        with patch.dict('os.environ', {'API_KEY': 'secret', 'SOMETHING_TOKEN': 'secret', 'PATH': 'ok'}):
            env = h.temiz_ortam()
        self.assertNotIn('API_KEY', env)
        self.assertNotIn('SOMETHING_TOKEN', env)
        self.assertEqual(env['PYTHONIOENCODING'], 'utf-8')

    def test_free_model_gets_isolated_home_and_only_web_and_library_permissions(self):
        self.hat.config = h.oku(h.ROOT / 'otomasyon/modeller.json')
        def run(argv, cwd, timeout, **kwargs):
            env = kwargs['env']
            self.assertNotEqual(pathlib.Path(env['USERPROFILE']), pathlib.Path.home())
            self.assertNotIn('API_KEY', env)
            config = h.oku(cwd / 'opencode.json')
            self.assertEqual(config['permission']['*'], 'deny')
            self.assertEqual(config['permission']['webfetch'], 'allow')
            self.assertEqual(list(config['mcp']), ['cio_librarian'])
            return '{"type":"text","part":{"text":"{}"}}\n'
        with patch.dict('os.environ', {'API_KEY': 'secret'}), patch.object(h, 'calistir', side_effect=run):
            self.assertEqual(self.hat.model(self.hat.config['yazar'][0], 'prompt'), '{}')

    def test_subprocess_timeout_terminates_process(self):
        with self.assertRaises(TimeoutError):
            h.calistir([sys.executable, '-c', 'import time; time.sleep(30)'], self.root, 1)

    def test_local_adapter_reuses_helper_and_limits_context_without_changing_it(self):
        helper = self.root / 'helper.py'
        helper.write_text('SINIR=24000\nADRES="http://localhost:11434/api/generate"\nMODELLER={"iyi":"qwen-test"}\n', encoding='utf-8')
        response = MagicMock()
        response.__enter__.return_value.__iter__.return_value = [b'{"response":"{}","done":true}\n']
        stdin = MagicMock()
        stdin.buffer.read.return_value = b'prompt'
        with patch.object(h.sys, 'stdin', stdin), patch.object(h.urllib.request, 'urlopen', return_value=response) as request, patch('builtins.print'):
            self.assertEqual(h.yerel_tek(helper, 'iyi', 4096), 0)
        body = json.loads(request.call_args.args[0].data)
        self.assertEqual(body['model'], 'qwen-test')
        self.assertEqual(body['options']['num_ctx'], 4096)
        self.assertEqual(body['format'], 'json')

    # --- aday hafızası ---
    def _oyunlar(self, games):
        (self.root / 'data/oyunlar.json').write_text(json.dumps(games, ensure_ascii=False), encoding='utf-8')

    def _aday(self, i, baslik, ad='IGN'):
        return {'baslik': baslik, 'ad': ad, 'ozet': '', 'kaynak': 'ign', 'tarih': '',
                'url': f'https://www.ign.com/haber/{i}'}

    def _al(self, hype_of):
        """Sahte eleme modeli: her aday 'al', puanı hype_of[aday_id]."""
        def run(stage, models, prompt, validate, **kwargs):
            items = json.loads(prompt.rsplit('ADAYLAR:', 1)[1])
            return [{'aday_id': x['aday_id'], 'karar': 'al', 'hype': hype_of[x['aday_id']], 'neden': 'yeni'} for x in items]
        return run

    def test_second_turn_uses_memory_and_skips_eleme_model(self):
        self._oyunlar([])
        candidates = [self._aday(0, 'Yama notu A'), self._aday(1, 'Yama notu B')]
        with patch.object(self.hat, 'zincir', side_effect=self._al({0: 5, 1: 6})) as first:
            self.hat.ele(candidates)
        self.assertEqual(first.call_count, 1)
        with patch.object(self.hat, 'zincir') as second:
            self.hat.ele(candidates)
        second.assert_not_called()
        self.assertEqual(self.hat.sonuc['hafizadan'], 2)

    def test_cached_rejections_do_not_consume_new_candidate_budget(self):
        self._oyunlar([])
        candidates = [self._aday(0, 'Rejected old event'), self._aday(1, 'Fresh event')]
        self.hat.hafiza_kaydet(h.adres(candidates[0]), 'al', 9, 'teyit yok', 'yazar')
        with patch.dict(h.oto.CONFIG['sinirlar'], {'yerel_aday': 1}), \
                patch.object(self.hat, 'zincir', side_effect=self._al({1: 5})) as run:
            selected = self.hat.ele(candidates)
        self.assertEqual([x['baslik'] for x in selected], ['Fresh event'])
        self.assertEqual(self.hat.sonuc['yeni_aday'], 1)
        self.assertEqual(run.call_count, 1)

    def test_writer_skip_is_remembered_and_not_selected_next_turn(self):
        self._oyunlar([])
        candidate = self._aday(0, 'Yama notu A')
        candidate['on_puan'] = 6
        with patch.object(self.hat, 'prompt', return_value='write'), \
                patch.object(self.hat, 'zincir', return_value={'durum': 'atla', 'neden': 'güncel değil'}):
            self.assertIsNone(self.hat.yaz(candidate))
        with patch.object(self.hat, 'zincir') as run:
            selected = self.hat.ele([candidate])
        run.assert_not_called()
        self.assertEqual(selected, [])
        self.assertIn('önceki turda atlandı: güncel değil', self.hat.sonuc['atlanan'][-1]['neden'])

    def test_old_records_are_dropped_and_corrupt_file_does_not_stop_run(self):
        now = datetime.now(timezone.utc)
        url_new = 'https://www.ign.com/haber/1'
        path = self.hat.state / 'gorulen.json'
        path.write_text(json.dumps({
            'https://www.ign.com/haber/0': {'karar': 'ele', 'hype': 1, 'neden': 'eski',
                                            'zaman': (now - timedelta(hours=73)).isoformat(), 'asama': 'eleme'},
            url_new: {'karar': 'ele', 'hype': 1, 'neden': 'yeni', 'zaman': now.isoformat(), 'asama': 'eleme'}}),
            encoding='utf-8')
        loaded = h.Hat(self.root, deneme=True, config={'eleme': [], 'yazar': [], 'denetci': []})
        self.assertEqual(set(loaded.gorulen), {url_new})
        path.write_text('{bozuk', encoding='utf-8')
        broken = h.Hat(self.root, deneme=True, config={'eleme': [], 'yazar': [], 'denetci': []})
        self.assertEqual(broken.gorulen, {})

    def test_same_game_other_events_remain_available_as_reserves(self):
        self._oyunlar([{'ad': 'Takipli', 'eslesme': []}])
        candidates = [self._aday(0, 'Takipli yama A'), self._aday(1, 'Takipli yama B'),
                      self._aday(2, 'Diger haber C'), self._aday(3, 'Diger haber D')]
        with patch.object(self.hat, 'zincir', side_effect=self._al({0: 10, 1: 9, 2: 8, 3: 7})):
            result = self.hat.ele(candidates)
        self.assertEqual([x['baslik'] for x in result], ['Takipli yama A', 'Takipli yama B', 'Diger haber C', 'Diger haber D'])

    def test_same_game_reserve_is_tried_after_rejection_but_skipped_after_approval(self):
        candidates = [dict(self._aday(i, f'Yama {i}'), oyun_eslesme='takipli') for i in range(3)]
        with patch.object(self.hat, 'yaz', side_effect=[{'id': 'a'}, {'id': 'b'}]) as write, \
                patch.object(self.hat, 'denetle', side_effect=[[], [{'id': 'b'}]]), \
                patch.object(self.hat, 'paket_kontrol', side_effect=lambda xs: xs):
            self.assertEqual(self.hat.adaylari_isle(candidates), [{'id': 'b'}])
        self.assertEqual(write.call_count, 2)

    def test_higher_score_beats_official_role(self):
        self._oyunlar([])
        candidates = [self._aday(0, 'Basın haberi', ad='IGN'), self._aday(1, 'Resmi duyuru', ad='PlayStation Blog')]
        with patch.object(self.hat, 'zincir', side_effect=self._al({0: 9, 1: 4})):
            result = self.hat.ele(candidates)
        self.assertEqual(result[0]['ad'], 'IGN')

    def test_known_old_dates_never_reach_local_model_and_unknown_goes_last(self):
        self._oyunlar([])
        candidates = [self._aday(0, '11/05/26 Eski Nintendo'), self._aday(1, 'Bilinmeyen'), self._aday(2, 'Taze')]
        candidates[2]['tarih'] = datetime.now(timezone.utc).isoformat()
        with patch.object(self.hat, 'zincir', side_effect=self._al({0: 10, 1: 4})) as run:
            result = self.hat.ele(candidates)
        self.assertNotIn('Eski Nintendo', run.call_args.args[2])
        self.assertEqual([x['baslik'] for x in result], ['Taze', 'Bilinmeyen'])

    def test_published_url_or_exact_locale_title_never_reaches_model(self):
        self._oyunlar([])
        existing = [{'kaynaklar': [{'url': 'https://www.ign.com/haber/0'}], 'diller': {'en': {'baslik': 'Already published'}}}]
        (self.root / 'data/icerik.json').write_text(json.dumps(existing), encoding='utf-8')
        candidates = [self._aday(0, 'Different headline'), self._aday(1, 'Already published'), self._aday(2, 'Fresh event')]
        with patch.object(self.hat, 'zincir', side_effect=self._al({0: 5})) as run:
            selected = self.hat.ele(candidates)
        self.assertEqual([x['baslik'] for x in selected], ['Fresh event'])
        self.assertEqual(self.hat.sonuc['yayinda_elendi'], 2)
        self.assertNotIn('Different headline', run.call_args.args[2].split('ADAYLAR:')[1])

    def test_quota_cooldown_persists_and_skips_until_expiry(self):
        models = [{'ad': 'free'}, {'ad': 'backup'}]
        with patch.object(self.hat, 'model', side_effect=[ValueError('FreeUsageLimitError retryAfterMs: 7200000'), '{"ok":true}']):
            self.assertTrue(self.hat.zincir('yazar', models, 'prompt', lambda x: x)['ok'])
        again = h.Hat(self.root, config={'eleme': [], 'yazar': [], 'denetci': []})
        with patch.object(again, 'model', return_value='{}') as run:
            again.zincir('yazar', models, 'prompt', lambda x: x)
        self.assertEqual([x.args[0]['ad'] for x in run.call_args_list], ['backup'])
        again.kotalar['free']['bitis'] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        with patch.object(again, 'model', return_value='{}') as run:
            again.zincir('yazar', models, 'prompt', lambda x: x)
        self.assertEqual(run.call_args.args[0]['ad'], 'free')

    def test_rejected_candidates_use_reserve_and_stop_at_three_approved(self):
        candidates = [self._aday(i, f'Haber {i}') for i in range(6)]
        articles = [{'id': str(i)} for i in range(6)]
        with patch.object(self.hat, 'yaz', side_effect=articles) as write, \
                patch.object(self.hat, 'denetle', side_effect=[[], [], [articles[2]], [articles[3]], [articles[4]]]), \
                patch.object(self.hat, 'paket_kontrol', side_effect=lambda xs: xs):
            result = self.hat.adaylari_isle(candidates)
        self.assertEqual([x['id'] for x in result], ['2', '3', '4'])
        self.assertEqual(write.call_count, 5)

    def test_publish_reads_approved_packet_instead_of_last_writer_draft(self):
        approved = [{'id': 'approved'}]
        h.oto.json_yaz(self.hat.state / 'onayli-paket.json', approved)
        h.oto.json_yaz(self.hat.state / 'paket.json', [{'id': 'rejected-later-draft'}])
        captured = []
        def validate_only(*args, **kwargs):
            captured.extend(h.oku(pathlib.Path(args[2])))
            raise ValueError('stop before applying or publishing')
        with patch.object(self.hat, 'oto', side_effect=validate_only), \
                self.assertRaisesRegex(ValueError, 'stop before'):
            self.hat.yayinla(approved, 'test-owner-token')
        self.assertEqual(captured, approved)

    def test_configured_attempt_ceiling_and_time_budget(self):
        limit = h.oto.CONFIG['sinirlar']['yazim_deneme']
        candidates = [self._aday(i, f'Haber {i}') for i in range(limit + 3)]
        with patch.object(self.hat, 'yaz', return_value=None) as write:
            self.assertEqual(self.hat.adaylari_isle(candidates), [])
        self.assertEqual(write.call_count, limit)
        self.hat.deadline = h.time.monotonic() + 119
        with patch.object(self.hat, 'yaz') as write:
            self.assertEqual(self.hat.adaylari_isle(candidates), [])
        write.assert_not_called()

    def test_unreliable_local_veto_does_not_hide_followed_or_high_hype(self):
        self._oyunlar([{'ad': 'Takipli', 'eslesme': []}])
        candidates = [self._aday(0, 'Takipli yeni sezon'), self._aday(1, 'Yeni oyun duyurusu'), self._aday(2, 'New game reportedly leaked')]
        decisions = [{'aday_id': i, 'karar': 'ele', 'hype': score, 'neden': 'anlamsız gerekçe'} for i, score in enumerate([4, 9, 10])]
        with patch.object(self.hat, 'zincir', return_value=decisions):
            selected = self.hat.ele(candidates)
        self.assertEqual([x['baslik'] for x in selected], ['Takipli yeni sezon', 'Yeni oyun duyurusu'])

    def test_freshness_then_official_only_break_score_ties(self):
        now = datetime.now(timezone.utc)
        def candidate(score, age, official=False, followed=False):
            return {'on_puan': score, 'tarih': (now-timedelta(hours=age)).isoformat(), 'resmi': official, 'takipli': followed}
        self.assertGreater(h.siralama(candidate(9, 20)), h.siralama(candidate(4, 1, True)))
        self.assertGreater(h.siralama(candidate(7, 1)), h.siralama(candidate(7, 2, True)))
        self.assertGreater(h.siralama(candidate(7, 1, True)), h.siralama(candidate(7, 1)))

    def test_quota_duration_from_response_or_twelve_hour_default(self):
        self.assertEqual(h.kota_suresi('FreeUsageLimitError {"retryAfterMs":7200000}'), 7200)
        self.assertEqual(h.kota_suresi('HTTP 429'), 43200)
        self.assertIsNone(h.kota_suresi('connection refused'))

    def test_same_event_keeps_official_url_and_independent_reports(self):
        candidates = [self._aday(0, 'New Game patch released'), self._aday(1, 'New Game patch released', ad='PlayStation Blog')]
        candidates[1]['url'] = 'https://blog.playstation.com/2026/11/16/new-game/'
        candidates[1]['resmi_aday'] = True
        merged = h.olaylari_birlestir(candidates)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]['resmi_url'], candidates[1]['url'])
        self.assertEqual(len(merged[0]['ilgili_kaynaklar']), 2)

    def test_dry_run_never_writes_memory(self):
        self._oyunlar([])
        with patch.object(self.hat, 'zincir', side_effect=self._al({0: 5})):
            self.hat.ele([self._aday(0, 'Yama notu A')])
        self.hat.bitir()
        self.assertFalse((self.hat.state / 'gorulen.json').exists())

    def test_real_run_saves_memory_for_next_turn(self):
        self._oyunlar([])
        config = {'eleme': [], 'yazar': [], 'denetci': []}
        live = h.Hat(self.root, deneme=False, config=config)
        with patch.object(live, 'zincir', side_effect=self._al({0: 5})):
            live.ele([self._aday(0, 'Yama notu A')])
        live.bitir()
        again = h.Hat(self.root, deneme=False, config=config)
        self.assertEqual(again.gorulen['https://www.ign.com/haber/0']['asama'], 'eleme')

    def test_fallback_decision_when_models_fail_is_not_remembered(self):
        self._oyunlar([])
        with patch.object(self.hat, 'zincir', return_value=None):
            self.hat.ele([self._aday(0, 'Yama notu A')])
        self.assertEqual(self.hat.gorulen, {})

    def test_local_outage_prioritizes_concrete_patch_without_marking_it_verified(self):
        self._oyunlar([{'ad': 'Takipli', 'eslesme': []}])
        candidates = [self._aday(0, 'Takipli cultural moment'), self._aday(1, 'Takipli hotfix removes dungeon EXP')]
        with patch.object(self.hat, 'zincir', return_value=None):
            selected = self.hat.ele(candidates)
        self.assertEqual(selected[0]['baslik'], candidates[1]['baslik'])
        self.assertEqual([x['on_puan'] for x in selected], [5, 3])
        self.assertTrue(all(not x.get('resmi') for x in selected))
        self.assertEqual(self.hat.gorulen, {})

    def test_audit_rejection_is_remembered_for_the_article_source(self):
        self.hat.haber_adres['a'] = 'https://www.ign.com/haber/0'
        self.hat.config['denetci'] = [{'ad': 'sonnet'}]
        verdict = {'kararlar': [{'id': 'a', 'karar': 'ret', 'neden': 'kaynak yok', 'hype': 3}]}
        with patch.object(self.hat, 'model', return_value=json.dumps(verdict)), patch.object(self.hat, 'prompt', return_value='audit'):
            self.hat.denetle([{'id': 'a', 'otomasyon': {'hype': 3}}])
        self.assertEqual(self.hat.gorulen['https://www.ign.com/haber/0']['asama'], 'denetci')


if __name__ == '__main__':
    unittest.main()
