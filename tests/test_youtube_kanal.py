import pathlib
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import sosyal_kurulum as sk  # noqa: E402
import youtube_kanal as yk  # noqa: E402

SIRLAR = {"CLIENT_ID": "kimlik", "CLIENT_SECRET": "sir", "REFRESH_TOKEN": "yenile"}


class YoutubeKanal(unittest.TestCase):
    def test_govde_oteki_ayarlari_korur(self):
        kanal = {"id": "UC1", "brandingSettings": {"channel": {"title": "ctrl-agame", "keywords": "oyun", "country": "TR",
                                                             "description": "eski"}, "image": {"x": 1}}}
        g = yk.aciklama_govdesi(kanal, "yeni")
        self.assertEqual(g, {"id": "UC1", "brandingSettings": {"channel": {
            "title": "ctrl-agame", "keywords": "oyun", "country": "TR", "description": "yeni"}}})
        self.assertEqual(kanal["brandingSettings"]["channel"]["description"], "eski")

    def test_govde_bos_kanal(self):
        self.assertEqual(yk.aciklama_govdesi({"id": "UC1"}, "yeni"),
                         {"id": "UC1", "brandingSettings": {"channel": {"description": "yeni"}}})

    def test_izin_kapsamdan_okunur(self):
        for kapsam, beklenen in ((sk.YT_KAPSAM, True), ("https://www.googleapis.com/auth/youtube.upload", False)):
            with patch.object(yk, "yt_oku", return_value=SIRLAR), \
                    patch.object(yk, "istek", return_value=(200, {"access_token": "a", "scope": kapsam})):
                self.assertEqual(yk.erisim("tr"), ("a", beklenen))

    def test_anahtar_yoksa_hata(self):
        with patch.object(yk, "yt_oku", return_value=None), self.assertRaises(yk.PaylasimHatasi):
            yk.erisim("tr")

    def test_saklama_gidis_donus(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d, patch.object(sk, "SAKLA", pathlib.Path(d)):
            self.assertIsNone(sk.yt_oku("tr"))
            sk.yt_sakla("tr", {**SIRLAR, "fazla": "x"})
            self.assertEqual(sk.yt_oku("tr"), SIRLAR)
            self.assertNotIn(b"yenile", (pathlib.Path(d) / "yt_tr.bin").read_bytes())


if __name__ == "__main__":
    unittest.main()
