"""Sessiz arıza bekçisi: bilgisayar turunun sonucu sunucuya gider, sunucu hatalı son turda
atlamaz, hata ve "uzun süredir haber yok" durumları yalnız değişince bildirilir.

Neden: 2026-11-16 akşamı bilgisayar hattı yayın adımında düştü, ama nabzı turun başında
bıraktığı için sunucu yedeği susup ~16 saat kimse fark etmedi.
"""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tools'))
import haber_hatti as h

SAAT = 3600


class IzlemeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        self.git(self.root, 'init', '--initial-branch=main')
        self.git(self.root, 'config', 'user.name', 'Test')
        self.git(self.root, 'config', 'user.email', 'test@example.invalid')
        (self.root / 'data').mkdir()
        (self.root / 'data/icerik.json').write_text('[]', encoding='utf-8')
        self.git(self.root, 'add', '.')
        self.git(self.root, 'commit', '-m', 'fixture')
        self.hat = h.Hat(self.root, config={'eleme': [], 'yazar': [], 'denetci': []})

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def git(cwd, *args, tarih=None):
        env = dict(os.environ)
        if tarih:
            env['GIT_AUTHOR_DATE'] = env['GIT_COMMITTER_DATE'] = f'{tarih} +0000'
        subprocess.run(['git', *args], cwd=cwd, check=True, capture_output=True, env=env)

    def etkinlestir(self):
        (self.root / 'otomasyon').mkdir(exist_ok=True)
        (self.root / 'otomasyon/nabiz.json').write_text('{"etkin":true,"ssh_hedef":"oracle"}')

    # --- Bilgisayar turunun sonucu sunucuya gider ---

    def tur(self, hazirlik=None):
        """Tam bir gerçek turu taklit eder; ssh çağrılarını (komut, stdin) olarak döndürür."""
        self.etkinlestir()
        kayit = []
        gercek, platform = h.calistir, sys.platform

        def sahte(argv, *args, **kwargs):
            if argv[0] != 'ssh':
                # Anlik'in git çağrıları gerçek çalışır; Windows koşulunu taklit ederken
                # Linux'ta shutil.which içindeki _winapi yoluna girmesin.
                with patch.object(sys, 'platform', platform):
                    return gercek(argv, *args, **kwargs)
            kayit.append((argv[-1], kwargs.get('stdin')))
            return ''

        with patch.object(sys, 'platform', 'win32'), patch.object(h, 'calistir', side_effect=sahte), \
             patch.object(self.hat, 'hazirlik', side_effect=hazirlik), \
             patch.object(self.hat, 'tara', return_value={'kaynaklar': [], 'adaylar': []}), \
             patch.object(self.hat, 'ele', return_value=[]), \
             patch.object(self.hat, 'adaylari_isle', return_value=[]):
            try:
                kod = self.hat.calistir()
            except Exception as exc:  # noqa: BLE001 - beklenmeyen istisnayı test eder
                kod = exc
        return kod, kayit

    def test_final_result_is_sent_last_and_ok_on_clean_turn(self):
        kod, kayit = self.tur()
        self.assertEqual(kod, 0)
        self.assertEqual(len(kayit), 3)
        self.assertIn('touch /home/haberci/pc-nabiz', kayit[0][0])
        self.assertIn('pc-gorulen.json', kayit[1][0])
        komut, govde = kayit[2]
        self.assertIn('/home/haberci/pc-sonuc.json', komut)
        self.assertIn('os.replace', komut)
        veri = json.loads(govde)
        self.assertTrue(veri['ok'])
        self.assertEqual((veri['hata'], veri['eklenen']), ('', 0))
        self.assertNotIn(govde, komut)

    def test_failed_turn_reports_error_text_and_added_count(self):
        def boz():
            self.hat.sonuc['eklenen'] = ['a', 'b']
            raise RuntimeError('[WinError 206] Dosya adı çok uzun\nikinci satır ' + 'x' * 400)

        kod, kayit = self.tur(boz)
        self.assertEqual(kod, 1)
        veri = json.loads(kayit[-1][1])
        self.assertFalse(veri['ok'])
        self.assertEqual(veri['eklenen'], 2)
        self.assertTrue(veri['hata'].startswith('[WinError 206] Dosya adı çok uzun ikinci satır'))
        self.assertLessEqual(len(veri['hata']), 300)
        self.assertNotIn('\n', veri['hata'])
        self.assertTrue(kayit[-1][1].isascii())  # uzak python3 ASCII yerel ayarda da bozmasın

    def test_unexpected_exception_is_recorded_as_error_then_reraised(self):
        def boz():
            raise subprocess.SubprocessError('beklenmedik')

        kod, kayit = self.tur(boz)
        self.assertIsInstance(kod, subprocess.SubprocessError)
        veri = json.loads(kayit[-1][1])
        self.assertFalse(veri['ok'])
        self.assertIn('SubprocessError', veri['hata'])
        self.assertIn('beklenmedik', h.oku(self.hat.state / 'sonuc.json')['hata'])

    def test_result_never_sent_on_linux_dry_run_or_disabled(self):
        self.etkinlestir()
        with patch.object(h, 'calistir') as run:
            with patch.object(sys, 'platform', 'linux'):
                self.hat.pc_esle(sonuc=True)
            with patch.object(sys, 'platform', 'win32'), patch.dict(os.environ, {'HABER_NABIZ': '0'}):
                self.hat.pc_esle(sonuc=True)
            self.hat.deneme = True
            with patch.object(sys, 'platform', 'win32'):
                self.hat.pc_esle(sonuc=True)
            run.assert_not_called()

    def test_result_ssh_failure_does_not_break_turn(self):
        self.etkinlestir()
        with patch.object(sys, 'platform', 'win32'), \
             patch.object(h, 'calistir', side_effect=RuntimeError('ssh disconnected')):
            self.hat.pc_esle(sonuc=True)
        kayit = self.hat.sonuc['esleme'][-1]
        self.assertEqual((kayit['asama'], kayit['ok']), ('sonuc', False))

    # --- Sunucu atlama kararı ---

    def nabiz_sonuc(self, sonuc_ok, sonuc_nabizdan_sonra=True, nabiz_yas=60):
        simdi = time.time()
        nabiz, sonuc = self.root / 'nabiz', self.root / 'sonuc.json'
        nabiz.touch()
        os.utime(nabiz, (simdi - nabiz_yas, simdi - nabiz_yas))
        if sonuc_ok is not None:
            sonuc.write_text(json.dumps({'ok': sonuc_ok, 'hata': 'x'}), encoding='utf-8')
            t = simdi - nabiz_yas + (10 if sonuc_nabizdan_sonra else -10)
            os.utime(sonuc, (t, t))
        return nabiz, sonuc, simdi

    def test_server_skips_only_when_pc_fresh_and_last_turn_not_failed(self):
        for ok, sonra, beklenen in [(True, True, 'atla'), (None, True, 'atla'), (False, True, 'hatali'),
                                    # sonuç nabızdan eski: bilgisayar yeni turun ortasında, çakışma olmasın
                                    (False, False, 'atla')]:
            nabiz, sonuc, simdi = self.nabiz_sonuc(ok, sonra)
            self.assertEqual(h.sunucu_atlasin(nabiz, sonuc, simdi), beklenen, (ok, sonra))

    def test_stale_heartbeat_always_runs_and_corrupt_result_is_ignored(self):
        nabiz, sonuc, simdi = self.nabiz_sonuc(False, nabiz_yas=50 * 60)
        self.assertEqual(h.sunucu_atlasin(nabiz, sonuc, simdi), 'eski')
        nabiz, sonuc, simdi = self.nabiz_sonuc(True)
        sonuc.write_text('{bozuk', encoding='utf-8')
        self.assertEqual(h.sunucu_atlasin(nabiz, sonuc, simdi), 'atla')
        sonuc.write_text('[]', encoding='utf-8')
        self.assertEqual(h.sunucu_atlasin(nabiz, sonuc, simdi), 'atla')

    def test_nabiz_kontrol_cli_prints_reason_and_sets_exit_code(self):
        nabiz, sonuc, _ = self.nabiz_sonuc(False)
        for argv, kod, yazi in [(['--nabiz-kontrol', str(nabiz), '--pc-sonuc', str(sonuc)], 1, 'hatali'),
                                (['--nabiz-kontrol', str(nabiz)], 0, 'atla'),  # eski çağrı biçimi
                                (['--nabiz-kontrol', str(self.root / 'yok')], 1, 'eski')]:
            with patch.object(sys, 'argv', ['haber_hatti.py', *argv]), patch('builtins.print') as yaz:
                self.assertEqual(h.main(), kod)
            yaz.assert_called_once_with(yazi)

    # --- İzleme kararları ---

    def test_pc_error_alerts_once_then_recovery_once(self):
        simdi = 1_000_000.0
        hatali = {'ok': False, 'hata': 'WinError 206\n' + 'x' * 500}
        ilk = h.izleme_karari(hatali, simdi - 60, simdi, 6, {})
        self.assertEqual([(a, d) for a, d, _ in ilk], [('pc', 'hata')])
        metin = ilk[0][2]
        self.assertIn('WinError 206 xxx', metin)
        self.assertNotIn('\n', metin)
        self.assertNotIn('x' * 201, metin)
        self.assertEqual(h.izleme_karari(hatali, simdi - 60, simdi, 6, {'pc': 'hata'}), [])
        duzeldi = h.izleme_karari({'ok': True}, simdi - 60, simdi, 6, {'pc': 'hata'})
        self.assertEqual([(a, d) for a, d, _ in duzeldi], [('pc', 'ok')])
        self.assertIn('düzeldi', duzeldi[0][2])
        self.assertEqual(h.izleme_karari({'ok': True}, simdi - 60, simdi, 6, {'pc': 'ok'}), [])

    def test_no_publish_alert_threshold_repeat_and_recovery(self):
        simdi = 1_000_000.0
        self.assertEqual(h.izleme_karari(None, simdi - 6 * SAAT, simdi, 6, {}), [])  # tam eşik: alarm yok
        uyari = h.izleme_karari(None, simdi - 6 * SAAT - 1, simdi, 6, {})
        self.assertEqual([(a, d) for a, d, _ in uyari], [('haber', 'yok')])
        self.assertIn('6 saattir', uyari[0][2])
        self.assertEqual(h.izleme_karari(None, simdi - 9 * SAAT, simdi, 6, {'haber': 'yok'}), [])
        duzeldi = h.izleme_karari(None, simdi - 100, simdi, 6, {'haber': 'yok'})
        self.assertEqual([(a, d) for a, d, _ in duzeldi], [('haber', 'ok')])
        self.assertIn('düzeldi', duzeldi[0][2])

    def test_unknown_inputs_never_alert_or_change_state(self):
        # Ağ yok (son yayın bilinmiyor) ve sonuç dosyası yok: ne sahte alarm ne sahte "düzeldi".
        self.assertEqual(h.izleme_karari(None, None, 1e6, 6, {'pc': 'hata', 'haber': 'yok'}), [])
        self.assertEqual(h.izleme_karari({'ok': 'belki'}, None, 1e6, 6, 'bozuk'), [])

    def test_both_alerts_can_fire_together(self):
        sonuc = h.izleme_karari({'ok': False, 'hata': 'e'}, 0, 7 * SAAT, 6, {})
        self.assertEqual({a for a, _, _ in sonuc}, {'pc', 'haber'})

    def test_state_file_written_atomically_and_keeps_other_keys(self):
        yol = self.root / 'durum.json'
        self.assertEqual(h.izleme_durumu_oku(yol), {})
        h.izleme_durumu_yaz(yol, 'pc', 'hata')
        h.izleme_durumu_yaz(yol, 'haber', 'yok')
        h.izleme_durumu_yaz(yol, 'pc', 'ok')
        self.assertEqual(h.izleme_durumu_oku(yol), {'pc': 'ok', 'haber': 'yok'})
        self.assertFalse((self.root / 'durum.json.tmp').exists())
        yol.write_text('{bozuk', encoding='utf-8')
        self.assertEqual(h.izleme_durumu_oku(yol), {})

    def test_threshold_precedence_argument_env_file_default(self):
        (self.root / 'otomasyon').mkdir(exist_ok=True)
        ayar = self.root / 'otomasyon/izleme.json'
        with patch.dict(os.environ):
            os.environ.pop('HABER_ESIK_SAAT', None)
            self.assertEqual(h.izleme_esigi(self.root), 6.0)  # dosya yok -> varsayılan
            ayar.write_text('{"haber_yok_saat": 4}', encoding='utf-8')
            self.assertEqual(h.izleme_esigi(self.root), 4.0)
            os.environ['HABER_ESIK_SAAT'] = '3'
            self.assertEqual(h.izleme_esigi(self.root), 3.0)
            self.assertEqual(h.izleme_esigi(self.root, '2.5'), 2.5)
            os.environ['HABER_ESIK_SAAT'] = 'abc'  # geçersiz değer dosyaya düşer
            self.assertEqual(h.izleme_esigi(self.root, '-1'), 4.0)
            ayar.write_text('{"haber_yok_saat": "x"}', encoding='utf-8')
            self.assertEqual(h.izleme_esigi(self.root), 6.0)

    def test_shipped_threshold_file_is_six_hours(self):
        with patch.dict(os.environ):
            os.environ.pop('HABER_ESIK_SAAT', None)
            self.assertEqual(h.izleme_esigi(h.ROOT), 6.0)

    # --- Son YAYIN commit'i (kod commit'i sayılmaz) ---

    def uzak_depo(self, ad='uzak'):
        uzak = self.root / ad
        uzak.mkdir()
        self.git(uzak, 'init', '--initial-branch=main')
        self.git(uzak, 'config', 'user.name', 'T')
        self.git(uzak, 'config', 'user.email', 't@example.invalid')
        (uzak / 'data').mkdir()
        (uzak / 'tools').mkdir()
        (uzak / 'sosyal').mkdir()

        def commit(mesaj, dosya, icerik, tarih):
            (uzak / dosya).write_text(icerik, encoding='utf-8')
            self.git(uzak, 'add', dosya)
            self.git(uzak, 'commit', '-m', mesaj, tarih=tarih)

        commit('haber: eski-haber', 'data/icerik.json', '[1]', 1_700_000_000)
        commit('haber: yeni-haber, ikinci-haber', 'data/icerik.json', '[1,2]', 1_700_100_000)
        # Aynı önekli ama yayın olmayan kod commit'i; başka dosyayı değiştiren sosyal commit'i;
        # önek farklı ama icerik.json'u değiştiren bakım commit'i: hiçbiri yayın sayılmaz.
        commit('haber: kuru bildirimde JSON üret', 'tools/kod.py', 'x', 1_700_200_000)
        commit('sosyal: gönderi kaydı', 'sosyal/kayit.json', '{}', 1_700_300_000)
        commit('chore: icerik biçimi', 'data/icerik.json', '[1, 2]', 1_700_400_000)
        return uzak

    def klonla(self, uzak, ad):
        klon = self.root / ad
        subprocess.run(['git', 'clone', '--quiet', str(uzak), str(klon)], check=True, capture_output=True)
        return klon

    def test_last_publish_is_haber_commit_touching_icerik_json_only(self):
        klon = self.klonla(self.uzak_depo(), 'klon')
        self.assertEqual(h.son_yayin_zamani(klon), 1_700_100_000)
        # Çekim ortak refs/remotes'a dokunmaz: yalnız özel ref oluşur
        refs = subprocess.run(['git', 'for-each-ref', '--format=%(refname)'], cwd=klon,
                              capture_output=True, text=True).stdout.split()
        self.assertIn('refs/izle/main', refs)

    def test_last_publish_unknown_when_remote_unreachable(self):
        self.assertIsNone(h.son_yayin_zamani(self.root))  # origin yok -> alarm için bilgi yok

    def test_last_publish_none_when_history_has_no_publish(self):
        uzak = self.root / 'bos'
        uzak.mkdir()
        self.git(uzak, 'init', '--initial-branch=main')
        self.git(uzak, 'config', 'user.name', 'T')
        self.git(uzak, 'config', 'user.email', 't@example.invalid')
        (uzak / 'a.txt').write_text('a', encoding='utf-8')
        self.git(uzak, 'add', 'a.txt')
        self.git(uzak, 'commit', '-m', 'sosyal: hiç yayın yok')
        self.assertIsNone(h.son_yayin_zamani(self.klonla(uzak, 'klon2')))

    def test_izle_ties_state_result_and_remote_together(self):
        klon = self.klonla(self.uzak_depo(), 'klon3')
        sonuc = self.root / 'pc.json'
        sonuc.write_text('{"ok": false, "hata": "bozuk"}', encoding='utf-8')
        durum = self.root / 'd.json'
        simdi = 1_700_100_000 + 7 * SAAT
        mesajlar = h.izle(klon, sonuc, durum, esik_saat=6, now=simdi)
        self.assertEqual({a for a, _, _ in mesajlar}, {'pc', 'haber'})
        # Eşik ayarı gerçekten etkili: 8 saat eşikte haber alarmı çıkmaz
        mesajlar = h.izle(klon, sonuc, durum, esik_saat=8, now=simdi)
        self.assertEqual({a for a, _, _ in mesajlar}, {'pc'})
        # Durum kaydedilince aynı alarm tekrar etmez
        h.izleme_durumu_yaz(durum, 'pc', 'hata')
        self.assertEqual(h.izle(klon, sonuc, durum, esik_saat=8, now=simdi), [])

    def test_izle_cli_prints_tab_separated_single_line_messages(self):
        klon = self.klonla(self.uzak_depo(), 'klon4')
        sonuc = self.root / 'pc.json'
        sonuc.write_text(json.dumps({'ok': False, 'hata': 'a\n\tb'}), encoding='utf-8')
        cikti = []
        with patch.object(h, 'ROOT', klon), patch.object(sys, 'argv', [
                'haber_hatti.py', '--izle', '--pc-sonuc', str(sonuc), '--izle-durum', str(self.root / 'd.json'),
                '--esik-saat', '6']), patch('builtins.print', side_effect=lambda x: cikti.append(x)):
            self.assertEqual(h.main(), 0)
        self.assertTrue(cikti)
        for satir in cikti:
            anahtar, durum, metin = satir.split('\t')  # metindeki sekme/satır sonu temizlenmiş olmalı
            self.assertIn(anahtar, ('pc', 'haber'))
            self.assertNotIn('\n', metin)

    def test_save_cli_writes_state(self):
        durum = self.root / 'd.json'
        with patch.object(sys, 'argv', ['haber_hatti.py', '--izle-kaydet', 'pc', 'hata', '--izle-durum', str(durum)]):
            self.assertEqual(h.main(), 0)
        self.assertEqual(h.izleme_durumu_oku(durum), {'pc': 'hata'})

    def test_wrapper_script_is_valid_bash(self):
        bash = shutil.which('bash')
        if not bash:
            self.skipTest('bash yok')
        betik = pathlib.Path(h.ROOT) / 'otomasyon/sunucu-haber.sh'
        self.assertEqual(subprocess.run([bash, '-n', str(betik)], capture_output=True).returncode, 0)


if __name__ == '__main__':
    unittest.main()
