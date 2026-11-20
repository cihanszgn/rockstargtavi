import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "tools"))
import indexnow  # noqa: E402

KOK = "https://ornek.com"
HARITA = [f"{KOK}/", f"{KOK}/en/", f"{KOK}/haberler.html", f"{KOK}/en/news.html",
          f"{KOK}/haber/yeni.html", f"{KOK}/en/game-news/new.html", f"{KOK}/haber/eski.html"]


class IndexNowTest(unittest.TestCase):
    def test_adres(self):
        self.assertEqual(indexnow.adres("index.html", KOK), f"{KOK}/")
        self.assertEqual(indexnow.adres("en/index.html", KOK), f"{KOK}/en/")
        self.assertEqual(indexnow.adres("haber\\yeni.html", KOK), f"{KOK}/haber/yeni.html")

    def test_eklenen_ve_ana_sayfalar(self):
        degisen = [("A", "haber/yeni.html"), ("A", "en/game-news/new.html"), ("M", "index.html"),
                   ("M", "en/index.html"), ("M", "en/news.html"), ("M", "haber/eski.html"), ("A", "oyun/bos.html"), ("M", "data/x.json")]
        self.assertEqual(indexnow.secilenler(degisen, HARITA, KOK),
                         [f"{KOK}/haber/yeni.html", f"{KOK}/en/game-news/new.html", f"{KOK}/", f"{KOK}/en/"])

    def test_yeni_sayfa_yoksa_bos(self):
        self.assertEqual(indexnow.secilenler([("M", "index.html"), ("M", "haber/eski.html")], HARITA, KOK), [])

    def test_gercek_anahtar_ve_harita(self):
        self.assertRegex(indexnow.anahtar(), r"^[0-9a-f]{32}$")
        self.assertTrue(all(u.startswith(indexnow.site() + "/") for u in indexnow.harita_adresleri()))


if __name__ == "__main__":
    unittest.main()
