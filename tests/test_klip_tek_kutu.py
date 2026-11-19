"""Tek kutu ("Ekle ve klip çıkar"), klip çıkarma kilidi/kuyruğu/aşaması ve "Onaylananları yayınla" arka ucu.
Gerçek ağ, gerçek yükleme ve gerçek git push YOK: Kick/YouTube, `_kos` ve YUKLE_KOMUTU sahtelenir."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import klip_kilit as kk  # noqa: E402
import klip_yayinla as kyl  # noqa: E402
import klip_yayincilar as kyc  # noqa: E402
import test_klip_yayincilar as tky  # noqa: E402
betik_yaz, kick_yanit, yt_yanit = tky.betik_yaz, tky.kick_yanit, tky.yt_yanit


class KilitTesti(unittest.TestCase):
    def setUp(self):
        self.g = tempfile.TemporaryDirectory()
        self.addCleanup(self.g.cleanup)
        self.dizin = pathlib.Path(self.g.name)

    def test_al_birak_ve_cakisma(self):
        a = kk.Kilit(self.dizin, "panel: A").al()
        with self.assertRaises(kk.KilitDolu) as h:
            kk.Kilit(self.dizin, "gunluk").al()
        self.assertEqual(h.exception.sahip, "panel: A")
        a.birak()
        self.assertFalse((self.dizin / kk.KILIT_ADI).exists())
        with kk.Kilit(self.dizin, "gunluk"):
            self.assertTrue((self.dizin / kk.KILIT_ADI).exists())

    def test_olu_surecin_kilidi_bayat(self):
        (self.dizin / kk.KILIT_ADI).write_text(json.dumps({"pid": 2 ** 30, "sahip": "olu", "zaman": "x"}), encoding="utf-8")
        k = kk.Kilit(self.dizin, "yeni").al()
        self.assertTrue(k.elde)
        k.birak()

    def test_pid_canli(self):
        self.assertTrue(kk.pid_canli(os.getpid()))
        self.assertFalse(kk.pid_canli(2 ** 30))
        self.assertFalse(kk.pid_canli(0))


class AsamaTesti(unittest.TestCase):
    def test_asama_coz(self):
        self.assertEqual(kyc.asama_coz("C:/x/klip1.mp4"), "Klip hazır")
        self.assertEqual(kyc.asama_coz("  sohbet: 3/12 pencere"), "Sohbet indiriliyor (3/12)")
        self.assertEqual(kyc.asama_coz("klip 2: abc"), "Klip 2 kesiliyor")
        self.assertEqual(kyc.asama_coz("Hype 2026-11-18 Akşam sohbeti"), "Yayın bulundu, analiz ediliyor")
        self.assertIsNone(kyc.asama_coz("klip 1 elendi: kısa"))
        self.assertIsNone(kyc.asama_coz("  atlandı: x 2026-11-18"))
        self.assertIsNone(kyc.asama_coz(""))


class GirdiCozTesti(unittest.TestCase):
    def test_turler(self):
        self.assertEqual(kyc.girdi_coz("Hype"), ({"kick": "Hype"}, {"youtube": "@Hype"}))
        self.assertEqual(kyc.girdi_coz("kick.com/hype"), ({"kick": "kick.com/hype"}, None))
        self.assertEqual(kyc.girdi_coz("https://www.youtube.com/@abc"), ({"youtube": "https://www.youtube.com/@abc"}, None))
        self.assertEqual(kyc.girdi_coz("@abc"), ({"youtube": "@abc"}, None))

    def test_hatalar_turkce(self):
        for g in ("", "   ", "evil.com/x", "a:b", "x" * 301, None):
            with self.assertRaises(kyc.Hata, msg=repr(g)):
                kyc.girdi_coz(g)


class EkleVeCikarTesti(tky.AyarTemel):
    def setUp(self):
        super().setUp()
        self.yi = kyc.YayinciIsleri()
        self.addCleanup(self.yi.kapat)

    def test_kick_bulundu_ekler_ve_baslatir(self):
        cagri = []
        with mock.patch.object(kyc, "_kick_http", kick_yanit("hype", "Hype")):
            s = kyc.ekle_ve_cikar({"girdi": "Hype"}, self.yi, lambda ad: cagri.append(ad) or "basladi")
        self.assertEqual((s["ok"], s["klip_cikar"], cagri), (True, "basladi", ["Hype"]))
        self.assertEqual(self.veri()["yayincilar"][-1]["kanal"], "hype")

    def test_kick_yoksa_youtube_yedegi(self):
        with mock.patch.object(kyc, "_kick_http", kick_yanit("baska")),                 mock.patch.object(kyc, "_yt_bilgi", yt_yanit()):
            s = kyc.ekle_ve_cikar({"girdi": "yeniyt"}, self.yi, lambda ad: "sirada")
        self.assertEqual((s["ok"], s["klip_cikar"]), (True, "sirada"))
        self.assertEqual(self.veri()["yayincilar"][-1]["platform"], "youtube")

    def test_klip_baslamazsa_yayinci_yine_eklenir(self):
        def hata(ad):
            raise kyc.Hata("Zaten bir klip çıkarma işi sürüyor.")
        with mock.patch.object(kyc, "_kick_http", kick_yanit("hype", "Hype")):
            s = kyc.ekle_ve_cikar({"girdi": "kick.com/hype"}, self.yi, hata)
        self.assertEqual((s["ok"], s["klip_cikar"]), (True, "baslamadi"))
        self.assertIn("listeye eklendi", s["mesaj"])
        self.assertEqual(self.veri()["yayincilar"][-1]["ad"], "Hype")

    def test_yinelenen_ve_bulunamayan_hata(self):
        with self.assertRaises(kyc.Hata):
            kyc.ekle_ve_cikar({"girdi": "evil.com/x"}, self.yi, lambda ad: "basladi")
        with mock.patch.object(kyc, "_kick_http", kick_yanit("wtcn", "wtcN")):
            with self.assertRaises(kyc.Hata) as h:
                kyc.ekle_ve_cikar({"girdi": "kick.com/wtcn"}, self.yi, lambda ad: "basladi")
        self.assertIn("zaten", str(h.exception).lower())


class KuyrukVeKilit(tky.AyarTemel):
    def setUp(self):
        super().setUp()
        self.yi = kyc.YayinciIsleri()
        self.addCleanup(self.yi.kapat)
        self.k = betik_yaz(self.kok, "sahte", "import time;print('klip 1: x',flush=True);time.sleep(1.0);print('a.mp4',flush=True)")
        m = mock.patch.object(kyc, "CIKAR_KOMUTU", self.k)
        m.start()
        self.addCleanup(m.stop)

    def test_sirala_ve_sirayla_biter(self):
        self.assertEqual(self.yi.cikar.baslat("A"), "basladi")
        self.assertEqual(self.yi.cikar.baslat("B", sirala=True), "sirada")
        self.assertEqual(self.yi.cikar.goster()["sirada"], ["B"])
        with self.assertRaises(kyc.Hata):
            self.yi.cikar.baslat("B", sirala=True)      # aynı yayıncı iki kez sıraya girmez
        with self.assertRaises(kyc.Hata):
            self.yi.cikar.baslat("C")                    # sirala yok: "Zaten"
        self.assertTrue(self.yi.cikar.bekle(30))
        d = self.yi.cikar.goster()
        self.assertEqual((d["durum"], d["yayinci"], d["klip"]), ("bitti", "B", 1))

    def test_dosya_kilidi_dolu_iken_baslamaz_ve_is_bitince_birakir(self):
        kilit = self.kok / "calisma" / kk.KILIT_ADI
        with kk.Kilit(self.kok / "calisma", "gunluk"):
            with self.assertRaisesRegex(kyc.Hata, "gunluk"):
                self.yi.cikar.baslat("A")
        self.yi.cikar.baslat("A")
        self.assertTrue(kilit.exists())
        self.assertTrue(self.yi.cikar.bekle(30))
        self.assertFalse(kilit.exists())

    def test_iptal_kuyrugu_temizler(self):
        self.yi.cikar.baslat("A")
        self.yi.cikar.baslat("B", sirala=True)
        self.yi.cikar.iptal()
        self.assertTrue(self.yi.cikar.bekle(30))
        d = self.yi.cikar.goster()
        self.assertEqual((d["durum"], d["yayinci"], d["sirada"]), ("iptal", "A", []))

    def test_asama_gorunur(self):
        self.yi.cikar.baslat("A")
        for _ in range(100):
            if self.yi.cikar.goster()["asama"].startswith("Klip 1"):
                break
            time.sleep(0.05)
        self.assertEqual(self.yi.cikar.goster()["asama"], "Klip 1 kesiliyor")
        self.assertTrue(self.yi.cikar.bekle(30))


class Yayinlama(unittest.TestCase):
    """`_kos` sahte: gerçek yükleme ve gerçek push yok."""

    def setUp(self):
        self.g = tempfile.TemporaryDirectory()
        self.addCleanup(self.g.cleanup)
        self.dizin = pathlib.Path(self.g.name)
        self.yol = self.dizin / "klipler.json"
        self.cagrilar = []
        self.yanit = {}
        for m in (mock.patch.object(kyl, "bekleyen_say", lambda y: self.bekleyen),
                  mock.patch.object(kyl, "_kos", self.sahte_kos),
                  mock.patch.object(kyl, "YUKLE_KOMUTU", ["SAHTE-YUKLE"])):
            m.start()
            self.addCleanup(m.stop)
        self.bekleyen = 2
        self.y = kyl.Yayinla(lambda: self.yol, depo=self.dizin)

    def sahte_kos(self, argv, zaman_asimi, cwd=None):
        self.cagrilar.append(list(argv))
        anahtar = " ".join(argv[:3]) if argv[0] == "git" else "yukle"
        if argv[0] == "git" and argv[1] in ("add", "commit", "pull", "push", "rebase"):
            anahtar = f"git {argv[1]}"
        if argv[:3] == ["git", "diff", "--cached"]:
            anahtar = "git diff"
        rc, out, err = self.yanit.get(anahtar, (1 if anahtar == "git diff" else 0, "", ""))
        return subprocess.CompletedProcess(argv, rc, out, err)

    def bekle(self):
        for _ in range(200):
            if not self.y.mesgul():
                return self.y.goster()
            time.sleep(0.02)
        self.fail("yayınlama bitmedi")

    def adlar(self):
        return [" ".join(c[:2]) for c in self.cagrilar]

    def test_basari_sirasi(self):
        self.yanit["yukle"] = (0, "a: yüklendi, yayında\nb: yüklendi, yayında\n", "")
        self.assertTrue(self.y.baslat()["ok"])
        d = self.bekle()
        self.assertEqual(d["durum"], "bitti")
        self.assertIn("2 klip yüklendi", d["mesaj"])
        self.assertEqual(self.adlar(), ["SAHTE-YUKLE --manifest", "git add", "git diff", "git commit", "git pull", "git push"])
        self.assertIn("--autostash", self.cagrilar[4])
        self.assertIn("--rebase", self.cagrilar[4])
        self.assertEqual(self.cagrilar[0][-1], "yukle")
        self.assertIn("2 klip yayında", " ".join(self.cagrilar[3]))

    def test_yukleme_hatasinda_commit_push_yok(self):
        self.yanit["yukle"] = (1, "HATA a: boyut büyük\n", "")
        self.y.baslat()
        d = self.bekle()
        self.assertEqual(d["durum"], "hata")
        self.assertIn("Commit ve push yapılmadı", d["mesaj"])
        self.assertEqual(self.adlar(), ["SAHTE-YUKLE --manifest"])

    def test_cakismada_rebase_iptal_ve_push_yok(self):
        self.yanit["yukle"] = (0, "a: yüklendi, yayında\n", "")
        self.yanit["git pull"] = (1, "", "CONFLICT in data/klipler.json")
        self.y.baslat()
        d = self.bekle()
        self.assertEqual(d["durum"], "hata")
        self.assertIn("çakışma", d["mesaj"])
        self.assertIn("git rebase", self.adlar())
        self.assertIn(["git", "rebase", "--abort"], self.cagrilar)
        self.assertNotIn("git push", self.adlar())

    def test_push_hatasi_ve_sir_maskeleme(self):
        self.yanit["yukle"] = (0, "a: yüklendi, yayında\n", "")
        self.yanit["git push"] = (1, "", "fatal: https://kullanici:GIZLI123@github.com/x/y.git reddedildi")
        self.y.baslat()
        d = self.bekle()
        self.assertEqual(d["durum"], "hata")
        self.assertNotIn("GIZLI123", json.dumps(d))
        self.assertIn("push başarısız", d["mesaj"])

    def test_bekleyen_yoksa_baslamaz_ve_cift_baslamaz(self):
        self.bekleyen = 0
        with self.assertRaisesRegex(kyl.Hata, "onaylı klip yok"):
            self.y.baslat()
        self.assertEqual(self.cagrilar, [])
        self.bekleyen = 1
        olay = threading.Event()
        eski = self.sahte_kos

        def yavas(argv, z, cwd=None):
            olay.wait(5)
            return eski(argv, z, cwd)
        with mock.patch.object(kyl, "_kos", yavas):
            self.y.baslat()
            with self.assertRaisesRegex(kyl.Hata, "zaten sürüyor"):
                self.y.baslat()
            olay.set()
            self.bekle()

    def test_degisiklik_yoksa_commit_atilmaz(self):
        self.yanit["yukle"] = (0, "", "")
        self.yanit["git diff"] = (0, "", "")
        self.y.baslat()
        d = self.bekle()
        self.assertEqual(d["durum"], "bitti")
        self.assertNotIn("git commit", self.adlar())
        self.assertIn("git push", self.adlar())


class YayinlaRotalari(tky.PanelRotalari):
    def test_yayinla_belirtec_ve_durum(self):
        self.assertEqual(self.post("yayinla", {}, belirtec=False)[0], 403)
        self.assertEqual(self.post("yayinla", {}, origin="http://evil.com")[0], 403)
        self.assertEqual(self.al("yayinla-durum", belirtec=False)[0], 403)
        s, g = self.al("yayinla-durum")
        v = json.loads(g)
        self.assertEqual((s, v["ok"], v["durum"]), (200, True, "yok"))

    def test_yayinla_onaysiz_klip_yoksa_422(self):
        with mock.patch.object(kyl, "bekleyen_say", lambda y: 0), mock.patch.object(kyl, "_kos") as kos:
            s, v = self.post("yayinla", {})
        self.assertEqual(s, 422)
        self.assertIn("onaylı klip yok", v["mesaj"])
        kos.assert_not_called()

    def test_ekle_cikar_ucu(self):
        k = betik_yaz(self.kok, "sahte", "import time;print('klip 1: x',flush=True);time.sleep(30)")
        self.assertEqual(self.post("ekle-cikar", {"girdi": "evil.com/x"})[0], 422)
        self.assertEqual(self.post("ekle-cikar", {"girdi": "Hype"}, belirtec=False)[0], 403)
        with mock.patch.object(kyc, "CIKAR_KOMUTU", k), mock.patch.object(kyc, "_kick_http", kick_yanit("hype", "Hype")):
            s, v = self.post("ekle-cikar", {"girdi": "Hype"})
            self.assertEqual((s, v["ok"], v["klip_cikar"]), (200, True, "basladi"))
            d = json.loads(self.al("is")[1])
            self.assertEqual((d["durum"], d["yayinci"]), ("calisiyor", "Hype"))
            self.assertEqual(self.post("iptal", {})[0], 200)
            self.assertTrue(self.sunucu.yayinci.cikar.bekle(20))
        self.assertEqual(json.loads(self.al("liste")[1])["yayincilar"][-1]["ad"], "Hype")


if __name__ == "__main__":
    unittest.main()
