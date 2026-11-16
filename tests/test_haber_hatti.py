import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
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
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]['baslik'], 'Takipli yama')
        self.assertEqual(len(self.hat.sonuc['atlanan']), 2)

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


if __name__ == '__main__':
    unittest.main()
