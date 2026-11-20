import json
import pathlib
import re
import sys
import tempfile
from datetime import date, datetime, time
import unittest

KOK = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK / "tools"))
import video_site as vs  # noqa: E402
import site_derle as sd  # noqa: E402

TABAN = "https://medya.test/v/"


def girdi(**degisim):
    v = {"anahtar": "k", "sure": 31.4, "mp4_1080": "a1080.mp4", "mp4_720": "a720.mp4", "mp4_540": "a540.mp4",
         "kapak": "a.jpg", "vtt": "a.vtt", "uretildi": "2026-11-15T10:00:00+00:00", "youtube": None, "instagram": None,
         "onay": True}
    v.update(degisim)
    return v


class OnayTests(unittest.TestCase):
    def test_onaysiz_video_yok_sayilir(self):
        self.assertIsNone(vs.bul(manifest("h1", onay=False), "h1", "tr"))
        eksik = manifest("h1")
        del eksik["videolar"]["h1"]["tr"]["onay"]
        self.assertIsNone(vs.bul(eksik, "h1", "tr"))
        self.assertIsNotNone(vs.bul(manifest("h1"), "h1", "tr"))

    def test_onay_gerekli_kapatilinca_onaysiz_da_gorunur(self):
        m = manifest("h1", onay=False)
        m["onay_gerekli"] = False
        self.assertIsNotNone(vs.bul(m, "h1", "tr"))

    def test_onay_yaz_ve_bekleyenler(self):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / "videolar.json"
            p.write_text(json.dumps(manifest("h1", onay=False, ozel="kalsin")), encoding="utf-8")
            self.assertEqual(vs.onay_bekleyenler(vs.yukle(p)), [("h1", "tr", TABAN + "a540.mp4")])
            self.assertTrue(vs.onay_yaz(p, "h1", "tr"))
            yeni = vs.yukle(p)
            self.assertEqual(vs.onay_bekleyenler(yeni), [])
            self.assertEqual(yeni["videolar"]["h1"]["tr"]["ozel"], "kalsin")
            self.assertIsNotNone(vs.bul(yeni, "h1", "tr"))
            self.assertTrue(vs.onay_yaz(p, "h1", "tr", False))
            self.assertIsNone(vs.bul(vs.yukle(p), "h1", "tr"))
            self.assertFalse(vs.onay_yaz(p, "yok", "tr"))


def manifest(hid, dil="tr", **degisim):
    return {"surum": 1, "taban": TABAN, "videolar": {hid: {dil: girdi(**degisim)}}}


class ManifestTests(unittest.TestCase):
    def test_dosya_yoksa_bos(self):
        self.assertEqual(vs.yukle(pathlib.Path("yok/videolar.json")), {})

    def test_bozuk_ya_da_yanlis_sema_bos(self):
        with tempfile.TemporaryDirectory() as t:
            p = pathlib.Path(t) / "m.json"
            for icerik in ("{bozuk", "[]", json.dumps({"taban": "http://x/", "videolar": {}}), json.dumps({"taban": TABAN})):
                p.write_text(icerik, encoding="utf-8")
                self.assertEqual(vs.yukle(p), {})

    def test_bul_tam_adres_ve_eksik_girdi_yok_sayilir(self):
        v = vs.bul(manifest("h1"), "h1", "tr")
        self.assertEqual((v["mp4_540"], v["kapak"], v["vtt"]), (TABAN + "a540.mp4", TABAN + "a.jpg", TABAN + "a.vtt"))
        self.assertIsNone(vs.bul(manifest("h1"), "h1", "en"))       # o dilde video yok
        self.assertIsNone(vs.bul(manifest("h1"), "baska", "tr"))
        self.assertIsNone(vs.bul({}, "h1", "tr"))
        self.assertIsNone(vs.bul(manifest("h1", mp4_540=None), "h1", "tr"))
        self.assertIsNone(vs.bul(manifest("h1", sure=0), "h1", "tr"))
        self.assertIsNone(vs.bul(manifest("h1", kapak="../kac.jpg"), "h1", "tr"))

    def test_baglanti_yaz_diger_alanlari_korur(self):
        with tempfile.TemporaryDirectory() as t:
            p = pathlib.Path(t) / "m.json"
            m = manifest("h1", ozel="kalsin")
            p.write_text(json.dumps(m), encoding="utf-8")
            self.assertTrue(vs.baglanti_yaz(p, "h1", "tr", "youtube", "https://www.youtube.com/shorts/X"))
            yeni = json.loads(p.read_text(encoding="utf-8"))
            v = yeni["videolar"]["h1"]["tr"]
            self.assertEqual((v["youtube"], v["ozel"], v["mp4_720"], yeni["taban"]), ("https://www.youtube.com/shorts/X", "kalsin", "a720.mp4", TABAN))
            self.assertFalse(vs.baglanti_yaz(p, "yok", "tr", "youtube", "https://x"))
            self.assertFalse(vs.baglanti_yaz(p, "h1", "tr", "baska", "https://x"))
            self.assertFalse(vs.baglanti_yaz(p, "h1", "tr", "youtube", "http://x"))

    def test_bugun_uretilen(self):
        m = manifest("h1")
        m["videolar"]["h2"] = {"en": girdi(uretildi="2026-11-14T10:00:00+00:00")}
        self.assertEqual(vs.bugun_uretilen(m, "2026-11-15"), 1)
        self.assertEqual(vs.bugun_uretilen({}, "2026-11-15"), 0)
        m["videolar"]["h1"]["en"] = girdi(uretildi="2026-11-15T11:00:00+00:00")
        self.assertEqual(vs.bugun_uretilen(m, "2026-11-15"), 2)
        self.assertEqual(vs.bugun_uretilen(m, "2026-11-15", "tr"), 1, "kota dil başına sayılır")
        self.assertEqual(vs.bugun_uretilen(m, "2026-11-15", "en"), 1)
        self.assertEqual(vs.bugun_uretilen(m, "2026-11-15", "fr"), 0)


class SiteHtmlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.veri = json.loads((KOK / "data" / "icerik.json").read_text(encoding="utf-8"))
        cls.x = cls.veri[0]
        # derle() dosya yazmadan haber_kart/haber_sayfasi çağrılabilsin diye gereken modül durumu
        sd.so.bagla(sd)
        sd.BUGUN = date.fromisoformat("2026-11-15")
        sd.SIMDI = datetime.combine(sd.BUGUN, time(0), sd.TRT)
        sd.SURUM.update({"css": "t", "js": "t", **{"ara-" + d: "t" for d in ("tr", "en", "fr", "es")}})
        sd.so.yukle()

    def tearDown(self):
        sd.VIDEO.clear()

    def kart(self, dil="tr"):
        return sd.haber_kart(dil, self.x)

    def sayfa(self, dil="tr"):
        return sd.haber_sayfasi(dil, self.x, self.veri)

    def test_manifest_yokken_video_isareti_yok(self):
        sd.VIDEO.clear()
        for dil in ("tr", "en", "fr", "es"):
            for h in (self.kart(dil), self.sayfa(dil)):
                for iz in ("data-video", "kg-videolu", 'class="vp"', "VideoObject", "hd-vid", "<video"):
                    self.assertNotIn(iz, h)

    def test_kartta_video_nitelikleri_ve_sure_rozeti(self):
        sd.VIDEO.update(manifest(self.x["id"], sure=75))
        h = self.kart()
        self.assertIn(f'data-video="{TABAN}a540.mp4"', h)
        self.assertIn(f'data-kapak="{TABAN}a.jpg"', h)
        self.assertIn("kg-videolu", h)
        self.assertIn("1:15", h)
        self.assertIn("data-video-dugme", h)
        self.assertNotRegex(h, r"\son(click|load|error)=")
        self.assertNotIn("<video", h)  # kartta bayt çekilmez; <video> JS ile oynatılırken eklenir

    def test_baska_dilde_video_yoksa_kart_degismez(self):
        sd.VIDEO.update(manifest(self.x["id"], dil="tr"))
        self.assertNotIn("data-video", self.kart("en"))
        self.assertNotIn("data-video", self.sayfa("fr"))
        self.assertIn("data-video", self.kart("tr"))

    def test_sayfada_oynatici_altyazi_baglantilar_ve_jsonld(self):
        sd.VIDEO.update(manifest(self.x["id"], youtube="https://www.youtube.com/shorts/X", instagram="https://www.instagram.com/reel/Y/"))
        h = self.sayfa()
        self.assertEqual(h.count('class="vp"'), 1)
        self.assertIn(f'poster="{TABAN}a.jpg"', h)
        self.assertIn(f'<track kind="captions" src="{TABAN}a.vtt"', h)
        self.assertIn(f'src="{TABAN}a720.mp4"', h)
        self.assertIn('preload="none"', h)
        self.assertIn("https://www.youtube.com/shorts/X", h)
        self.assertIn("https://www.instagram.com/reel/Y/", h)
        self.assertNotRegex(h, r"\son(click|load|error)=")
        ld = [json.loads(m) for m in re.findall(r'<script type="application/ld\+json">(.*?)</script>', h, re.S)]
        vo = [d for d in ld if d.get("@type") == "VideoObject"]
        self.assertEqual(len(vo), 1)
        self.assertEqual((vo[0]["contentUrl"], vo[0]["duration"], vo[0]["thumbnailUrl"]), (TABAN + "a720.mp4", "PT31S", [TABAN + "a.jpg"]))

    def test_vtt_yoksa_track_ve_cc_yok(self):
        sd.VIDEO.update(manifest(self.x["id"], vtt=None))
        h = self.sayfa()
        self.assertNotIn("<track", h)
        self.assertNotIn("data-video-cc", h)

    def test_harita_girdisi_ve_kacis(self):
        v = vs.bul(manifest("h1"), "h1", "tr")
        g = vs.harita_girdisi(v, ad="A & B <c>", aciklama="d", tarih="2026-11-15")
        self.assertIn("<video:duration>31</video:duration>", g)
        self.assertIn("A &amp; B &lt;c&gt;", g)
        self.assertIn(f"<video:content_loc>{TABAN}a720.mp4</video:content_loc>", g)

    def test_manifest_birlestir_eszamanli_degisiklikleri_korur(self):
        eski = {"surum": 1, "taban": TABAN, "videolar": {
            "h1": {"tr": {"anahtar": "a1", "sure": 30.0, "youtube": "", "instagram": ""}},
        }}
        yerel = {"surum": 1, "taban": TABAN, "videolar": {
            "h1": {"tr": {"anahtar": "a1", "sure": 30.0, "youtube": "", "instagram": ""}},
            "h2": {"en": {"anahtar": "b1", "sure": 41.2, "youtube": "", "instagram": ""}},
        }}
        guncel = {"surum": 1, "taban": TABAN, "videolar": {
            "h1": {"tr": {"anahtar": "a1", "sure": 30.0, "youtube": "https://youtu.be/X", "instagram": ""}},
            "h3": {"es": {"anahtar": "c1", "sure": 35.0, "youtube": "", "instagram": ""}},
        }}
        sonuc, degisen = vs.manifest_birlestir(eski, yerel, guncel)
        self.assertEqual(degisen, 1)
        self.assertEqual(sonuc["videolar"]["h1"]["tr"]["youtube"], "https://youtu.be/X", "sosyal.yml linki korunur")
        self.assertIn("h3", sonuc["videolar"], "main'e arada gelen başka video korunur")
        self.assertEqual(sonuc["videolar"]["h2"]["en"]["anahtar"], "b1", "yeni üretilen video eklenir")
        # Aynı kayda eşzamanlı youtube linki gelmişse yeniden üretim onu silmez
        yerel_guncel = {"surum": 1, "taban": TABAN, "videolar": {
            "h1": {"tr": {"anahtar": "a2", "sure": 31.0, "youtube": "", "instagram": ""}},
        }}
        sonuc2, degisen2 = vs.manifest_birlestir(eski, yerel_guncel, guncel)
        self.assertEqual(degisen2, 1)
        self.assertEqual(sonuc2["videolar"]["h1"]["tr"]["anahtar"], "a2")
        self.assertEqual(sonuc2["videolar"]["h1"]["tr"]["youtube"], "https://youtu.be/X")


if __name__ == "__main__":
    unittest.main()
