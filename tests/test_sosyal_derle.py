import copy
import json
import pathlib
import sys
import tempfile
import unittest
from datetime import date
from unittest.mock import patch

KOK = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK / "tools"))
import sosyal_derle as sd  # noqa: E402

try:
    import PIL  # noqa: F401
    PIL_VAR = True
except ImportError:
    PIL_VAR = False


@unittest.skipUnless(PIL_VAR, "Pillow yok")
class KartTests(unittest.TestCase):
    def test_ig_karti_dort_dil_icin_hesap_ayarindan_bagimsiz_uretilir(self):
        haber = copy.deepcopy(json.loads((KOK / "data" / "icerik.json").read_text(encoding="utf-8"))[0])
        haber["tarih"] = date.today().isoformat()
        with tempfile.TemporaryDirectory() as t:
            kok = pathlib.Path(t)
            with patch.object(sd, "KOK", kok), \
                    patch.object(sd, "ayarlar", side_effect=AssertionError("kart üretimi hesap ayarına bakmamalı")):
                sd.kartlar([haber])
            for dil in sd.DILLER:
                self.assertTrue((kok / sd.kart_ad(haber["id"], dil, "ig")).exists(), f"{dil} IG kartı yok")
                self.assertTrue((kok / sd.kart_ad(haber["id"], dil, "og")).exists(), f"{dil} OG kartı yok")

    def test_eski_haber_ig_karti_uretilmez(self):
        haber = copy.deepcopy(json.loads((KOK / "data" / "icerik.json").read_text(encoding="utf-8"))[0])
        haber["tarih"] = "2020-01-01"
        with tempfile.TemporaryDirectory() as t:
            kok = pathlib.Path(t)
            with patch.object(sd, "KOK", kok):
                sd.kartlar([haber])
            self.assertFalse((kok / sd.kart_ad(haber["id"], "en", "ig")).exists())


if __name__ == "__main__":
    unittest.main()
