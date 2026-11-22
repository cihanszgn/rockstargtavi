"""Günlük otomatik betik: sır maskeleme, yalnız etkin yayıncılar, kilit doluyken atlama, son satır. Gerçek klip çıkarma yok."""
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import klip_kilit as kk  # noqa: E402
import klip_otomatik as ko  # noqa: E402


class Otomatik(unittest.TestCase):
    def setUp(self):
        self.g = tempfile.TemporaryDirectory()
        self.addCleanup(self.g.cleanup)
        self.kok = pathlib.Path(self.g.name)
        self.ayar = self.kok / "ayar.json"
        self.ayar.write_text('{"yayincilar":[{"ad":"A","etkin":true},{"ad":"B","etkin":false},{"ad":"C"}]}', encoding="utf-8")
        for m in (mock.patch.object(ko, "AYAR", self.ayar), mock.patch.object(ko, "GUNLUK", self.kok / "gunluk"),
                  mock.patch.object(ko, "CALISMA", self.kok / "calisma")):
            m.start()
            self.addCleanup(m.stop)
        # gerçek otomatik gizli adımı (yükleme/push) hiçbir testte çalışmasın
        self.gizli = mock.patch.object(ko, "otomatik_gizli_calistir", return_value=0).start()
        self.addCleanup(mock.patch.stopall)

    def log_son(self):
        yol = next((self.kok / "gunluk").glob("klip-*.log"))
        return yol.read_text(encoding="utf-8").strip().splitlines()

    def test_etkin_yayincilar(self):
        self.assertEqual(ko.yayincilar(), ["A", "C"])

    def test_sir_maskelenir(self):
        self.assertNotIn("GIZLI", ko.temizle("git https://u:GIZLI@github.com/x token=GIZLI2 belirteç: GIZLI3"))

    def test_klipleri_sayar_ve_son_satir(self):
        with mock.patch.object(ko, "yayinci_calistir", lambda ad, log: 2 if ad == "A" else 1):
            self.assertEqual(ko.main(), 0)
        self.assertTrue(self.log_son()[-1].endswith("3 yeni klip onay bekliyor"))
        self.assertFalse((self.kok / "calisma" / kk.KILIT_ADI).exists())

    def test_kilit_doluysa_atlar(self):
        with kk.Kilit(self.kok / "calisma", "panel: X"), mock.patch.object(ko, "BEKLEME_SN", 0), \
                mock.patch.object(ko, "yayinci_calistir") as c:
            self.assertEqual(ko.main(), 0)
        c.assert_not_called()
        son = self.log_son()
        self.assertTrue(son[-1].endswith("0 yeni klip onay bekliyor"))
        self.assertTrue(any("atlandı" in s for s in son))

    def test_gizli_adim_uretimden_sonra_kilit_birakilinca_calisir(self):
        durum = {}

        def gizli(log):
            durum["kilit_var"] = (self.kok / "calisma" / kk.KILIT_ADI).exists()
            return 0
        with mock.patch.object(ko, "yayinci_calistir", lambda ad, log: 1), mock.patch.object(ko, "otomatik_gizli_calistir", gizli):
            self.assertEqual(ko.main(), 0)
        self.assertEqual(durum, {"kilit_var": False})
        son = self.log_son()
        self.assertTrue(any("otomatik gizli adımı bitti (çıkış kodu 0)" in s for s in son))
        self.assertTrue(son[-1].endswith("2 yeni klip onay bekliyor"))

    def test_gizli_adim_patlarsa_uretim_ve_cikis_kodu_bozulmaz(self):
        with mock.patch.object(ko, "yayinci_calistir", lambda ad, log: 1), \
                mock.patch.object(ko, "otomatik_gizli_calistir", side_effect=RuntimeError("ssh yok")):
            self.assertEqual(ko.main(), 0)
        son = self.log_son()
        self.assertTrue(any("UYARI: otomatik gizli adımı tamamlanamadı" in s for s in son))
        self.assertTrue(son[-1].endswith("2 yeni klip onay bekliyor"))

    def test_gizli_adim_hata_kodu_cikis_kodunu_bozmaz(self):
        with mock.patch.object(ko, "yayinci_calistir", lambda ad, log: 1), \
                mock.patch.object(ko, "otomatik_gizli_calistir", return_value=1):
            self.assertEqual(ko.main(), 0)

    def test_bir_yayinci_patlarsa_digeri_surer(self):
        def f(ad, log):
            if ad == "A":
                raise RuntimeError("patladı")
            return 1
        with mock.patch.object(ko, "yayinci_calistir", f):
            self.assertEqual(ko.main(), 1)
        self.assertTrue(self.log_son()[-1].endswith("1 yeni klip onay bekliyor"))


if __name__ == "__main__":
    unittest.main()
