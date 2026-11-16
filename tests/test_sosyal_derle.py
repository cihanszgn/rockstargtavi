import copy
import io
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
    def test_yeni_turler_ve_indirilemeyen_gorsel_derlemeyi_dusurmez(self):
        import sosyal_kuyruk as sk
        from PIL import Image
        haber = copy.deepcopy(json.loads((KOK / "data/icerik.json").read_text(encoding="utf-8"))[0])
        veri = []
        for tur in sk.TURLER[1:]:
            x = copy.deepcopy(haber)
            x.update(id=tur, sosyal_tur=tur, oyun="ÇokUzunBirOyunAdı" * 15,
                     gorsel={"url": "https://example.com/resim.jpg", "kaynak": "Studio"})
            for t in x['diller'].values():
                t['baslik'] = "UzunOyunAdı" * 70
                t['ozet'] = "Uzun özet cümlesi. " * 50
            veri.append(x)
        with tempfile.TemporaryDirectory() as t, patch.object(sd.urllib.request, "urlopen", side_effect=OSError("çevrimdışı")) as ag:
            sd.kartlar([], veri, cikti=pathlib.Path(t))
            self.assertEqual(ag.call_count, 1, "Aynı başarısız görsel dört dil ve tür için tekrar indirilmez")
            for x in veri:
                for d in sd.DILLER:
                    p = pathlib.Path(t) / pathlib.Path(sd.kart_ad(x['id'], d, 'ig')).name
                    with Image.open(p) as img:
                        self.assertEqual(img.size, (1080, 1350))

    def test_resmi_gorsel_onbellek_ve_bozuk_yanit(self):
        from PIL import Image
        ham = io.BytesIO()
        Image.new('RGB', (30, 20), 'red').save(ham, 'PNG')
        class Yanit(io.BytesIO):
            pass
        with patch.object(sd.urllib.request, 'urlopen', return_value=Yanit(ham.getvalue())) as ag:
            cache = {}
            g = {'url': 'https://example.com/test.png', 'kaynak': 'Studio'}
            self.assertEqual(sd.resmi_gorsel(g, cache).size, (30, 20))
            self.assertEqual(sd.resmi_gorsel(g, cache).getpixel((1, 1)), (255, 0, 0))
            self.assertEqual(ag.call_count, 1)
        with patch.object(sd.urllib.request, 'urlopen', return_value=Yanit(b'bozuk')):
            self.assertIsNone(sd.resmi_gorsel(g, {}))

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
