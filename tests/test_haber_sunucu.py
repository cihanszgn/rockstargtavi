import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tools'))
import haber_hatti as h


class SunucuTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        for args in [('init', '--initial-branch=main'), ('config', 'user.name', 'Test'),
                     ('config', 'user.email', 'test@example.invalid')]:
            subprocess.run(['git', *args], cwd=self.root, check=True, capture_output=True)
        (self.root / 'data').mkdir()
        (self.root / 'data/icerik.json').write_text('[]', encoding='utf-8')
        subprocess.run(['git', 'add', '.'], cwd=self.root, check=True, capture_output=True)
        subprocess.run(['git', 'commit', '-m', 'fixture'], cwd=self.root, check=True, capture_output=True)
        self.hat = h.Hat(self.root, config={'eleme': [], 'yazar': [], 'denetci': []})
        self.codex = {'ad': 'gpt-6-luna', 'tur': 'codex', 'komut': ['codex', '-a', 'never', 'exec']}

    def tearDown(self):
        self.temp.cleanup()

    def test_codex_jsonl_uses_final_completed_agent_message(self):
        raw = '\n'.join(json.dumps(x) for x in [
            {'type': 'thread.started'},
            {'type': 'item.completed', 'item': {'type': 'reasoning', 'text': 'not json'}},
            {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': 'working'}},
            {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': '{"ok":true}'}},
            {'type': 'turn.completed'}])
        self.assertEqual(h.model_json(h.codex_cikti(raw)), {'ok': True})

    def test_codex_incomplete_or_failed_turn_is_never_accepted(self):
        for raw in ['{"type":"turn.completed"}', '{"type":"error","message":"login required"}']:
            with self.assertRaises(RuntimeError):
                h.codex_cikti(raw)

    def test_codex_limit_is_persisted_and_next_provider_runs(self):
        def run(spec, prompt):
            if spec['tur'] == 'codex':
                return h.codex_cikti('{"type":"turn.failed","error":{"code":"rate_limit_exceeded","message":"usage limit"}}')
            return '{"ok":true}'
        models = [self.codex, {'ad': 'free', 'tur': 'opencode'}]
        with patch.object(self.hat, 'model', side_effect=run) as model:
            self.assertEqual(self.hat.zincir('yazar', models, '', lambda x: x), {'ok': True})
            self.assertEqual(model.call_count, 2)
        other = h.Hat(self.root, config=self.hat.config)
        with patch.object(other, 'model', return_value='{}') as model:
            other.zincir('denetci', [self.codex], '', lambda x: x)
            model.assert_not_called()

    def test_missing_auth_skips_codex_without_invocation_or_failed_run(self):
        free = {'ad': 'free', 'tur': 'opencode', 'komut': ['opencode']}
        original = h.calistir
        def dispatch(argv, *args, **kwargs):
            return '{"type":"text","part":{"text":"{}"}}' if argv[0] == 'opencode' else original(argv, *args, **kwargs)
        with patch.object(pathlib.Path, 'home', return_value=self.root), \
             patch.object(h, 'calistir', side_effect=dispatch) as run:
            self.assertEqual(self.hat.zincir('yazar', [self.codex, free], '', lambda x: x), {})
            self.assertEqual(sum(c.args[0][0] == 'opencode' for c in run.call_args_list), 1)
            self.assertFalse(any(c.args[0][0] == 'codex' for c in run.call_args_list))
        self.assertIn('oturumu yok', self.hat.sonuc['modeller'][0]['neden'])

    def test_codex_readonly_web_and_json_flags_no_user_config_or_secret_env(self):
        (self.root / '.codex').mkdir()
        (self.root / '.codex/auth.json').write_text('{}')
        raw = '{"type":"item.completed","item":{"type":"agent_message","text":"{}"}}\n{"type":"turn.completed"}'
        with patch.object(pathlib.Path, 'home', return_value=self.root), \
             patch.dict(os.environ, {'CLAUDE_CODE_OAUTH_TOKEN': 'do-not-forward'}), \
             patch.object(h, 'calistir', return_value=raw) as run:
            self.assertEqual(self.hat.model(self.codex, 'prompt'), '{}')
        argv = run.call_args.args[0]
        self.assertIn('--ignore-user-config', argv)
        self.assertIn('read-only', argv)
        self.assertIn('web_search="live"', argv)
        self.assertIn('features.shell_tool=false', argv)
        self.assertNotIn('CLAUDE_CODE_OAUTH_TOKEN', run.call_args.kwargs['env'])

    def test_server_model_file_env_cli_override_and_pc_default(self):
        default = h.model_ayari(h.ROOT)
        with patch.dict(os.environ, {'HABER_MODELLER': 'otomasyon/modeller-sunucu.json'}):
            server = h.model_ayari(h.ROOT)
            self.assertEqual(h.model_ayari(h.ROOT, 'otomasyon/modeller.json'), default)
        self.assertEqual([s['ad'] for s in server['yazar']],
                         ['opencode/big-pickle', 'gpt-6-luna', 'haiku', 'gpt-6.1-terra', 'sonnet'])
        self.assertEqual([s['ad'] for s in server['denetci']], ['sonnet', 'gpt-6.1-sol', 'opus'])
        self.assertEqual(server['eleme'], [])

    def test_auditor_prefers_different_provider_preserving_fallback_order(self):
        self.hat.yazar_saglayici = 'claude'
        models = [{'ad': 'sonnet', 'tur': 'claude'}, {'ad': 'sol', 'tur': 'codex'}, {'ad': 'opus', 'tur': 'claude'}]
        with patch.object(self.hat, 'model', return_value='{}') as run:
            self.hat.zincir('denetci', models, '', lambda x: x)
            self.assertEqual(run.call_args.args[0]['ad'], 'sol')

    def test_heartbeat_fifty_minute_boundary_missing_and_future(self):
        p = self.root / 'heartbeat'
        self.assertFalse(h.nabiz_taze(p))
        p.touch()
        now = time.time()
        for seconds, expected in [(2999, True), (3000, False), (3001, False), (-10, False)]:
            os.utime(p, (now - seconds, now - seconds))
            self.assertEqual(h.nabiz_taze(p, now), expected)

    def _enable_sync(self):
        (self.root / 'otomasyon').mkdir()
        (self.root / 'otomasyon/nabiz.json').write_text('{"etkin":true,"ssh_hedef":"oracle"}')

    def test_windows_heartbeat_short_noninteractive_ssh(self):
        self._enable_sync()
        with patch.object(sys, 'platform', 'win32'), patch.object(h, 'calistir') as run:
            self.hat.pc_esle()
        argv = run.call_args.args[0]
        self.assertIn('ConnectTimeout=5', argv)
        self.assertIn('BatchMode=yes', argv)
        self.assertIn('touch /home/haberci/pc-nabiz', argv[-1])

    def test_linux_dry_and_disabled_never_sync(self):
        self._enable_sync()
        with patch.object(h, 'calistir') as run:
            with patch.object(sys, 'platform', 'linux'):
                self.hat.pc_esle()
            with patch.object(sys, 'platform', 'win32'), patch.dict(os.environ, {'HABER_NABIZ': '0'}):
                self.hat.pc_esle()
            self.hat.deneme = True
            with patch.object(sys, 'platform', 'win32'):
                self.hat.pc_esle(hafiza=True)
            run.assert_not_called()

    def test_sync_failures_do_not_abort_real_turn_and_memory_is_saved(self):
        self._enable_sync()
        original = h.calistir
        platform = sys.platform
        def dispatch(argv, *args, **kwargs):
            if argv[0] == 'ssh':
                raise RuntimeError('ssh disconnected')
            # Windows koşulunu sınarken Linux shutil.which içindeki _winapi yoluna girme.
            with patch.object(sys, 'platform', platform):
                return original(argv, *args, **kwargs)
        with patch.object(sys, 'platform', 'win32'), \
             patch.object(h, 'calistir', side_effect=dispatch), \
             patch.object(self.hat, 'hazirlik'), \
             patch.object(self.hat, 'tara', return_value={'kaynaklar': [], 'adaylar': []}), \
             patch.object(self.hat, 'ele', return_value=[]), \
             patch.object(self.hat, 'adaylari_isle', return_value=[]):
            self.assertEqual(self.hat.calistir(), 0)
        result = h.oku(self.hat.state / 'sonuc.json')
        self.assertNotIn('hata', result)
        self.assertEqual([x['asama'] for x in result['esleme']], ['nabiz', 'hafiza', 'sonuc'])
        self.assertTrue(all(not x['ok'] for x in result['esleme']))
        self.assertTrue((self.hat.state / 'gorulen.json').exists())

    def test_memory_transferred_via_stdin_and_atomic_replace(self):
        self._enable_sync()
        text = '{"https://example.invalid/":{"neden":"örnek"}}'
        (self.hat.state / 'gorulen.json').write_text(text, encoding='utf-8')
        with patch.object(sys, 'platform', 'win32'), patch.object(h, 'calistir') as run:
            self.hat.pc_esle(hafiza=True)
        self.assertEqual(run.call_args.kwargs['stdin'], text)
        self.assertIn('os.replace', run.call_args.args[0][-1])
        self.assertNotIn(text, run.call_args.args[0])


if __name__ == '__main__':
    unittest.main()
