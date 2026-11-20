import json
import pathlib
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import sosyal_yayinla as sy  # noqa: E402
import video_site as vs  # noqa: E402

SIMDI = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)
BUGUN = date(2026, 11, 15)


def haber(oid="oyun-yama-1", konu=None):
    return {"id": oid, "tarih": "2026-11-15", "oyun": "Oyun",
            "kaynaklar": [{"url": "https://example.com/a", "ad": "Kaynak"}],
            "diller": {d: {"baslik": "Yeni oyun yaması", "ozet": "Yama yayımlandı.", "metin": "Bilgi " * 40,
                           "etiketler": ["#Oyun", "#Yama"]} for d in sy.DILLER},
            "otomasyon": {"konu": konu or oid}}


def ayar(**hesap):
    h = {"x": False, "reddit": False, "instagram": False, "instagram_reel": False, "youtube": False}
    h.update(hesap)
    return {"en_eski_gun": 3, "calisma_basina_en_fazla": 1,
            "gunluk_en_fazla": {"x": 2, "reddit": 2, "instagram": 2, "instagram_reel": 2, "youtube": 2},
            "x_baglanti": "gonderide", "instagram_api_surumu": "v27.0",
            "hesaplar": {d: dict(h) for d in sy.DILLER}, "youtube": {"gizlilik": "private"}, "reddit_topluluk": {}}


SIRLAR = {"IG_TR_USER_ID": "17841", "IG_TR_TOKEN": "tok",
          "YT_TR_CLIENT_ID": "cid", "YT_TR_CLIENT_SECRET": "csec", "YT_TR_REFRESH_TOKEN": "rt",
          "X_TR_API_KEY": "a", "X_TR_API_SECRET": "b", "X_TR_ACCESS_TOKEN": "c", "X_TR_ACCESS_SECRET": "d"}


class SahteAg:
    """Ağ yerine geçer: her çağrıyı kaydeder; `yanit` ile istenen çağrı için yanıt/hata verilir."""

    def __init__(self, durumlar=None, mutasyon_hatasi=None):
        self.cagrilar = []
        self.durumlar = list(durumlar or ["FINISHED"])  # kapsayıcı durum dizisi
        self.hata = mutasyon_hatasi or {}  # {"media_publish": PaylasimHatasi(...)}
        self.yayinda = True
        self.indirilen = 0

    def _hata(self, url):
        for k, h in self.hata.items():
            if k in url:
                raise h

    def istek(self, method, url, *, veri=None, json_govde=None, basliklar=None, zaman=30):
        self.cagrilar.append((method, url.split("?")[0]))
        self._hata(url)
        if url.endswith("/media") and method == "POST":
            return 200, {"id": "KAP1"}
        if "media_publish" in url:
            return 200, {"id": "MED1"}
        if "fields=status_code" in url:
            d = self.durumlar.pop(0) if len(self.durumlar) > 1 else self.durumlar[0]
            return 200, {"status_code": d}
        if "fields=permalink" in url:
            return 200, {"permalink": "https://www.instagram.com/reel/ABC/"}
        if "oauth2.googleapis.com" in url:
            return 200, {"access_token": "erisim"}
        if "api.x.com" in url:
            return 200, {"data": {"id": "TW1"}}
        raise AssertionError(f"beklenmeyen istek {method} {url}")

    def ham(self, method, url, *, govde=None, basliklar=None, zaman=300):
        self.cagrilar.append((method, url.split("?")[0]))
        self._hata(url)
        if "uploadType=resumable" in url:
            return 200, {"location": "https://upload.example/oturum1"}, ""
        if url == "https://upload.example/oturum1":
            if govde == b"":  # oturum sorgusu
                return 308, {"range": "bytes=0-9"}, ""
            return 200, {}, json.dumps({"id": "YT1"})
        if "thumbnails/set" in url:
            return 200, {}, "{}"
        raise AssertionError(f"beklenmeyen ham {method} {url}")

    def indir(self, url):
        self.indirilen += 1
        return b"0123456789ABCDEF"

    def yayinda_mi(self, url):
        return self.yayinda

    def uyku(self, sn):
        pass


class YasakAg(SahteAg):
    """Dry-run denemesi: herhangi bir ağ çağrısı testi düşürür."""

    def istek(self, *a, **k):
        raise AssertionError("dry-run ağ çağrısı yaptı (istek)")

    def ham(self, *a, **k):
        raise AssertionError("dry-run ağ çağrısı yaptı (ham)")

    def indir(self, *a, **k):
        raise AssertionError("dry-run ağ çağrısı yaptı (indir)")

    def yayinda_mi(self, *a, **k):
        raise AssertionError("dry-run ağ çağrısı yaptı (yayinda_mi)")


class Temel(unittest.TestCase):
    def setUp(self):
        self.gecici = tempfile.TemporaryDirectory()
        self.kok = pathlib.Path(self.gecici.name)
        self.kayit = self.kok / "gonderilenler.json"
        self.manifest = self.kok / "videolar.json"

    def tearDown(self):
        self.gecici.cleanup()

    def manifest_yaz(self, hid="oyun-yama-1", dil="tr"):
        self.manifest.write_text(json.dumps({"surum": 1, "taban": "https://medya.test/v/", "videolar": {hid: {dil: {
            "anahtar": "k", "sure": 30.0, "mp4_1080": "a1080.mp4", "mp4_720": "a720.mp4", "mp4_540": "a540.mp4",
            "kapak": "a.jpg", "vtt": "a.vtt", "uretildi": "2026-11-15T10:00:00+00:00", "ozel": "kalsin", "onay": True}}}}), encoding="utf-8")

    def calistir(self, ag, ayar_, veri=None, dry=False, tum=None, simdi=SIMDI):
        return sy.calistir(ayar_, veri if veri is not None else [haber()], kayit_yolu=self.kayit, manifest_yolu=self.manifest,
                           tum=SIRLAR if tum is None else tum, ag=ag, dry_run=dry, bugun=BUGUN, simdi=simdi, cikti=lambda *_: None)

    def kayitlar(self):
        return json.loads(self.kayit.read_text(encoding="utf-8")) if self.kayit.exists() else {}


class AnahtarVeGoc(Temel):
    def test_anahtar_konu_yoksa_id(self):
        self.assertEqual(sy.anahtar(haber("a", "konu-1"), "tr", "instagram", "reel"), "konu-1|tr|instagram|reel")
        x = haber("b")
        del x["otomasyon"]
        self.assertEqual(sy.anahtar(x, "en", "x", "gorsel"), "b|en|x|gorsel")

    def test_eski_kayit_goc_eder_ve_tamam_olur(self):
        yeni, goc = sy.kayit_goc({"oyun-yama-1|tr|instagram": {"zaman": "2026-11-14T10:00:00+00:00", "kimlik": "9", "url": "u"}},
                                 [haber("oyun-yama-1", "konu-z")])
        self.assertTrue(goc)
        rec = yeni["konu-z|tr|instagram|gorsel"]
        self.assertEqual((rec["durum"], rec["kimlik"], rec["bicim"]), ("tamam", "9", "gorsel"))
        again, goc2 = sy.kayit_goc(yeni, [haber("oyun-yama-1", "konu-z")])
        self.assertFalse(goc2)
        self.assertEqual(again, yeni)

    def test_eski_kayitli_haber_yeniden_paylasilmaz(self):
        self.kayit.write_text(json.dumps({"oyun-yama-1|tr|instagram": {"zaman": "2026-11-14T10:00:00+00:00", "kimlik": "9"}}), encoding="utf-8")
        ag = SahteAg()
        g, hata, _ = self.calistir(ag, ayar(instagram=True))
        self.assertEqual((g, hata), (0, []))
        self.assertEqual(ag.cagrilar, [])
        self.assertIn("oyun-yama-1|tr|instagram|gorsel", self.kayitlar())  # göç yazıldı

    def test_konu_ayni_ama_id_farkliysa_cift_paylasim_yok(self):
        ag = SahteAg()
        self.calistir(ag, ayar(instagram=True), [haber("id-1", "ortak-konu")])
        n = len(ag.cagrilar)
        self.calistir(ag, ayar(instagram=True), [haber("id-2", "ortak-konu")])
        self.assertEqual(len(ag.cagrilar), n)


class Gorsel(Temel):
    def test_niyet_tamam_ve_ikinci_calisma_cagri_yapmaz(self):
        ag = SahteAg()
        g, hata, _ = self.calistir(ag, ayar(instagram=True))
        self.assertEqual((g, hata), (1, []))
        rec = self.kayitlar()["oyun-yama-1|tr|instagram|gorsel"]
        self.assertEqual((rec["durum"], rec["kimlik"], rec["kapsayici"]), ("tamam", "MED1", "KAP1"))
        n = len(ag.cagrilar)
        g2, _, _ = self.calistir(ag, ayar(instagram=True))
        self.assertEqual(g2, 0)
        self.assertEqual(len(ag.cagrilar), n)

    def test_finished_olmadan_yayimlanmaz(self):
        ag = SahteAg(durumlar=["IN_PROGRESS"])
        g, hata, _ = self.calistir(ag, ayar(instagram=True))
        self.assertEqual(g, 0)
        self.assertFalse(any("media_publish" in u for _, u in ag.cagrilar))
        self.assertEqual(len(hata), 1)
        rec = self.kayitlar()["oyun-yama-1|tr|instagram|gorsel"]
        self.assertEqual((rec["durum"], rec["kapsayici"]), ("niyet", "KAP1"))  # kapsayıcı kaydedildi, sonra devam edilir

    def test_in_progress_sonra_finished_yayimlar(self):
        ag = SahteAg(durumlar=["IN_PROGRESS", "IN_PROGRESS", "FINISHED"])
        g, _, _ = self.calistir(ag, ayar(instagram=True))
        self.assertEqual(g, 1)
        yollar = [u for _, u in ag.cagrilar]
        self.assertLess(max(i for i, u in enumerate(yollar) if "KAP1" in u), yollar.index([u for u in yollar if "media_publish" in u][0]))

    def test_error_durumu_kesin_hata_ve_kayit_silinir(self):
        ag = SahteAg(durumlar=["ERROR"])
        g, hata, _ = self.calistir(ag, ayar(instagram=True))
        self.assertEqual(g, 0)
        self.assertEqual(len(hata), 1)
        self.assertNotIn("oyun-yama-1|tr|instagram|gorsel", self.kayitlar())

    def test_hesap_sirri_yoksa_atlanir(self):
        ag = SahteAg()
        g, hata, atlanan = self.calistir(ag, ayar(instagram=True), tum={})
        self.assertEqual((g, hata), (0, []))
        self.assertIn("instagram/tr", atlanan)
        self.assertEqual(ag.cagrilar, [])

    def test_gunluk_sinir(self):
        a = ayar(instagram=True)
        a["gunluk_en_fazla"]["instagram"] = 1
        ag = SahteAg()
        self.calistir(ag, a, [haber("a1"), haber("a2")])
        n = len(ag.cagrilar)
        g, _, _ = self.calistir(ag, a, [haber("a1"), haber("a2")])
        self.assertEqual(g, 0)
        self.assertEqual(len(ag.cagrilar), n)


class KayipYanit(Temel):
    def test_x_zaman_asimi_sonrasi_elle_bak_ve_tekrar_denenmez(self):
        ag = SahteAg(mutasyon_hatasi={"api.x.com": sy.PaylasimHatasi("zaman aşımı")})
        g, hata, _ = self.calistir(ag, ayar(x=True))
        self.assertEqual(g, 0)
        self.assertEqual(self.kayitlar()["oyun-yama-1|tr|x|gorsel"]["durum"], "niyet")
        self.assertIn("belirsiz", hata[0])
        ag2 = SahteAg()
        g2, hata2, _ = self.calistir(ag2, ayar(x=True))
        self.assertEqual(g2, 0)
        self.assertEqual(self.kayitlar()["oyun-yama-1|tr|x|gorsel"]["durum"], "elle_bak")
        self.assertTrue(any("ELLE BAK" in h for h in hata2))
        self.assertEqual(ag2.cagrilar, [])  # X'e ikinci kez gönderi atılmadı
        ag3 = SahteAg()
        self.calistir(ag3, ayar(x=True))
        self.assertEqual(ag3.cagrilar, [])

    def test_instagram_yayimla_yaniti_kayboldu_sonra_published_tamamlar(self):
        ag = SahteAg(mutasyon_hatasi={"media_publish": sy.PaylasimHatasi("zaman aşımı")})
        self.calistir(ag, ayar(instagram=True))
        self.assertEqual(self.kayitlar()["oyun-yama-1|tr|instagram|gorsel"]["durum"], "niyet")
        ag2 = SahteAg(durumlar=["PUBLISHED"])
        self.calistir(ag2, ayar(instagram=True))
        self.assertEqual(self.kayitlar()["oyun-yama-1|tr|instagram|gorsel"]["durum"], "tamam")
        self.assertFalse(any("media_publish" in u or u.endswith("/media") for _, u in ag2.cagrilar))

    def test_instagram_kapsayici_finished_kalmissa_yayimlar_ama_yeni_kapsayici_acmaz(self):
        ag = SahteAg(mutasyon_hatasi={"media_publish": sy.PaylasimHatasi("zaman aşımı")})
        self.calistir(ag, ayar(instagram=True))
        ag2 = SahteAg(durumlar=["FINISHED"])
        self.calistir(ag2, ayar(instagram=True))
        yollar = [u for _, u in ag2.cagrilar]
        self.assertEqual(sum("media_publish" in u for u in yollar), 1)
        self.assertFalse(any(u.endswith("/media") for u in yollar))
        self.assertEqual(self.kayitlar()["oyun-yama-1|tr|instagram|gorsel"]["durum"], "tamam")

    def test_instagram_expired_elle_bak(self):
        ag = SahteAg(mutasyon_hatasi={"media_publish": sy.PaylasimHatasi("zaman aşımı")})
        self.calistir(ag, ayar(instagram=True))
        ag2 = SahteAg(durumlar=["EXPIRED"])
        _, hata, _ = self.calistir(ag2, ayar(instagram=True))
        self.assertEqual(self.kayitlar()["oyun-yama-1|tr|instagram|gorsel"]["durum"], "elle_bak")
        self.assertTrue(any("ELLE BAK" in h for h in hata))

    def test_kesin_4xx_reddinde_kayit_silinir_ve_sonra_denenir(self):
        ag = SahteAg(mutasyon_hatasi={"api.x.com": sy.PaylasimHatasi("HTTP 403", kesin=True)})
        self.calistir(ag, ayar(x=True))
        self.assertNotIn("oyun-yama-1|tr|x|gorsel", self.kayitlar())
        g, _, _ = self.calistir(SahteAg(), ayar(x=True))
        self.assertEqual(g, 1)


class Reel(Temel):
    def test_reel_manifest_yoksa_atlanir(self):
        ag = SahteAg()
        g, _, _ = self.calistir(ag, ayar(instagram_reel=True))
        self.assertEqual((g, ag.cagrilar), (0, []))

    def test_reel_paylasilir_baglanti_manifeste_yazilir_diger_alanlar_korunur(self):
        self.manifest_yaz()
        ag = SahteAg()
        g, hata, _ = self.calistir(ag, ayar(instagram_reel=True))
        self.assertEqual((g, hata), (1, []))
        self.assertIn("oyun-yama-1|tr|instagram|reel", self.kayitlar())
        v = json.loads(self.manifest.read_text(encoding="utf-8"))["videolar"]["oyun-yama-1"]["tr"]
        self.assertEqual(v["instagram"], "https://www.instagram.com/reel/ABC/")
        self.assertEqual((v["ozel"], v["mp4_540"], v["sure"]), ("kalsin", "a540.mp4", 30.0))

    def test_gorsel_ve_reel_ayri_anahtar_ayri_gonderi(self):
        self.manifest_yaz()
        ag = SahteAg()
        a = ayar(instagram=True, instagram_reel=True)
        self.calistir(ag, a)
        self.calistir(ag, a)
        self.assertEqual({"oyun-yama-1|tr|instagram|gorsel", "oyun-yama-1|tr|instagram|reel"}, set(self.kayitlar()))

    def test_reel_finished_beklemeden_yayimlanmaz(self):
        self.manifest_yaz()
        ag = SahteAg(durumlar=["IN_PROGRESS"])
        g, _, _ = self.calistir(ag, ayar(instagram_reel=True))
        self.assertEqual(g, 0)
        self.assertFalse(any("media_publish" in u for _, u in ag.cagrilar))


class Short(Temel):
    def test_short_yuklenir_oturum_ve_kimlik_kaydedilir(self):
        self.manifest_yaz()
        ag = SahteAg()
        g, hata, _ = self.calistir(ag, ayar(youtube=True))
        self.assertEqual((g, hata), (1, []))
        rec = self.kayitlar()["oyun-yama-1|tr|youtube|short"]
        self.assertEqual((rec["durum"], rec["kimlik"], rec["oturum"]), ("tamam", "YT1", "https://upload.example/oturum1"))
        v = json.loads(self.manifest.read_text(encoding="utf-8"))["videolar"]["oyun-yama-1"]["tr"]
        self.assertEqual(v["youtube"], "https://www.youtube.com/shorts/YT1")
        self.assertTrue(any("thumbnails/set" in u for _, u in ag.cagrilar), ag.cagrilar)

    def test_short_govdesi(self):
        x = haber()
        x["diller"]["tr"]["baslik"] = "A" * 150
        g = sy.yt_govde("tr", x, "https://ctrl-agame.com/x", {})
        self.assertLessEqual(len(g["snippet"]["title"]), 100)
        self.assertEqual(g["status"], {"privacyStatus": "private", "selfDeclaredMadeForKids": False, "containsSyntheticMedia": True})
        self.assertEqual(g["snippet"]["defaultLanguage"], "tr")
        self.assertIn("https://ctrl-agame.com/x", g["snippet"]["description"])
        self.assertEqual(sy.yt_govde("tr", x, "u", {"youtube": {"gizlilik": "public"}})["status"]["privacyStatus"], "public")
        self.assertEqual(sy.yt_govde("tr", x, "u", {"youtube": {"gizlilik": "bozuk"}})["status"]["privacyStatus"], "private")

    def test_yukleme_yaniti_kayboldu_oturum_sorgulanip_devam_eder(self):
        self.manifest_yaz()
        ag = SahteAg(mutasyon_hatasi={})

        orijinal = ag.ham

        def ham(method, url, *, govde=None, basliklar=None, zaman=300):
            if url == "https://upload.example/oturum1" and govde not in (b"", None):
                ag.cagrilar.append((method, url))
                raise sy.PaylasimHatasi("zaman aşımı")
            return orijinal(method, url, govde=govde, basliklar=basliklar, zaman=zaman)
        ag.ham = ham
        self.calistir(ag, ayar(youtube=True))
        rec = self.kayitlar()["oyun-yama-1|tr|youtube|short"]
        self.assertEqual((rec["durum"], rec["oturum"]), ("niyet", "https://upload.example/oturum1"))
        ag2 = SahteAg()
        self.calistir(ag2, ayar(youtube=True))
        self.assertEqual(self.kayitlar()["oyun-yama-1|tr|youtube|short"]["durum"], "tamam")
        self.assertFalse(any("uploadType=resumable" in u for _, u in ag2.cagrilar))  # yeni oturum açılmadı

    def test_oturumsuz_niyet_elle_bak(self):
        self.kayit.write_text(json.dumps({"oyun-yama-1|tr|youtube|short": {
            "id": "oyun-yama-1", "dil": "tr", "platform": "youtube", "bicim": "short", "durum": "niyet",
            "niyet_zamani": "2026-11-15T09:00:00+00:00"}}), encoding="utf-8")
        self.manifest_yaz()
        ag = SahteAg()
        self.calistir(ag, ayar(youtube=True))
        self.assertEqual(self.kayitlar()["oyun-yama-1|tr|youtube|short"]["durum"], "elle_bak")
        self.assertEqual(ag.cagrilar, [])


class HypeKurali(Temel):
    def hypeli(self, puan):
        x = haber()
        x["otomasyon"]["hype"] = puan
        return [x]

    def test_hype_esigin_altinda_reels_ve_shorts_gitmez_gorsel_gider(self):
        self.manifest_yaz()
        ag = SahteAg()
        a = ayar(instagram=True, instagram_reel=True, youtube=True)
        a["video"] = {"hype_esigi": 7}
        g, hata, _ = self.calistir(ag, a, veri=self.hypeli(6))
        self.assertEqual((g, hata), (1, []))
        self.assertEqual(set(self.kayitlar()), {"oyun-yama-1|tr|instagram|gorsel"})
        self.assertFalse(any("googleapis" in u for _, u in ag.cagrilar), "Shorts yüklenmez")

    def test_hype_esikte_reels_ve_shorts_gider(self):
        self.manifest_yaz()
        a = ayar(instagram_reel=True, youtube=True)
        a["video"] = {"hype_esigi": 7}
        a["calisma_basina_en_fazla"] = 2
        g, hata, _ = self.calistir(SahteAg(), a, veri=self.hypeli(7))
        self.assertEqual(hata, [])
        self.assertEqual(set(self.kayitlar()), {"oyun-yama-1|tr|instagram|reel", "oyun-yama-1|tr|youtube|short"})

    def test_puansiz_eski_haberde_manifestte_video_varsa_gider(self):
        self.manifest_yaz()
        a = ayar(instagram_reel=True)
        a["video"] = {"hype_esigi": 7}
        g, _, _ = self.calistir(SahteAg(), a)  # haber() hype içermez
        self.assertEqual(g, 1)

    def test_video_hakki_birim(self):
        a = {"video": {"hype_esigi": 8}}
        for hype, beklenen in ((None, True), (7, False), (8, True), (10, True), ("9", False), (True, False)):
            x = {"otomasyon": {"hype": hype}} if hype is not None else {"otomasyon": {}}
            self.assertEqual(sy.video_hakki(x, a), beklenen, hype)
        self.assertTrue(sy.video_hakki({"otomasyon": {"hype": 7}}, {}), "ayar yoksa eşik 7")
        self.assertFalse(sy.video_hakki({"otomasyon": {"hype": 6}}, {}))


class AnahtarsizDil(Temel):
    def test_anahtari_olmayan_dil_atlanir_ve_dort_dil_icin_ayar_acik(self):
        self.manifest_yaz()
        a = ayar(instagram=True)  # dört dilde de açık; yalnız tr anahtarı var
        ag = SahteAg()
        g, hata, atlanan = self.calistir(ag, a)
        self.assertEqual((g, hata), (1, []))
        self.assertEqual(set(self.kayitlar()), {"oyun-yama-1|tr|instagram|gorsel"})
        self.assertEqual(sorted(atlanan), [f"instagram/{d}" for d in sorted(sy.DILLER) if d != "tr"])

    def test_anahtar_eklenince_kod_degismeden_paylasilir(self):
        a = ayar(instagram=True)
        a["calisma_basina_en_fazla"] = 1
        tum = dict(SIRLAR, IG_EN_USER_ID="999", IG_EN_TOKEN="tok2")
        g, hata, atlanan = self.calistir(SahteAg(), a, tum=tum)
        self.assertEqual(hata, [])
        self.assertEqual(g, 2)
        self.assertEqual(set(self.kayitlar()), {"oyun-yama-1|tr|instagram|gorsel", "oyun-yama-1|en|instagram|gorsel"})
        self.assertEqual(sorted(atlanan), [f"instagram/{d}" for d in sorted(sy.DILLER) if d not in ("tr", "en")])

    def test_dry_run_anahtarsiz_hesabi_atlandi_diye_yazar_tr_planlanir(self):
        self.manifest_yaz()
        satirlar = []
        a = ayar(instagram=True, instagram_reel=True, youtube=True)
        g, hata, atlanan = sy.calistir(a, [haber()], kayit_yolu=self.kayit, manifest_yolu=self.manifest, tum=SIRLAR,
                                       ag=YasakAg(), dry_run=True, bugun=BUGUN, simdi=SIMDI, cikti=satirlar.append)
        self.assertEqual(hata, [])
        metin = "\n".join(map(str, satirlar))
        for dil in ("en", "es", "fr"):
            self.assertIn(f"instagram/{dil}: anahtar yok, atlandı", metin)
            self.assertIn(f"youtube/{dil}: anahtar yok, atlandı", metin)
            self.assertIn(f"IG_{dil.upper()}_TOKEN", metin, "eksik değişkenin yalnız adı yazılır")
        self.assertNotIn("instagram/tr: anahtar yok", metin)
        self.assertIn("oyun-yama-1", metin, "tr planlanmış görünür")
        self.assertIn('yerelleştirme gövdesi:', metin)
        self.assertIn('"localizations":', metin)
        self.assertIn('"defaultLanguage": "tr"', metin)
        self.assertNotIn("tok", metin.replace("TOKEN", ""), "değer yazılmaz")

    def test_anahtarsiz_goster_eski_onizlemeyi_korur(self):
        satirlar = []
        a = ayar(instagram=True)
        sy.calistir(a, [haber()], kayit_yolu=self.kayit, manifest_yolu=self.manifest, tum={}, ag=YasakAg(), dry_run=True,
                    bugun=BUGUN, simdi=SIMDI, cikti=satirlar.append, anahtarsiz_goster=True)
        self.assertFalse(any("anahtar yok" in str(x) for x in satirlar))
        self.assertTrue(any("oyun-yama-1" in str(x) for x in satirlar))

    def test_paylasilacak_diller_yalniz_anahtari_olan_acik_hesaplar(self):
        a = ayar(instagram=True)
        self.assertEqual(sy.paylasilacak_diller(a, SIRLAR), ["tr"])
        self.assertEqual(sy.paylasilacak_diller(a, dict(SIRLAR, IG_FR_USER_ID="1", IG_FR_TOKEN="t")), ["tr", "fr"])
        self.assertEqual(sy.paylasilacak_diller(a, {}), [])
        self.assertEqual(sy.paylasilacak_diller(ayar(), SIRLAR), [], "ayarda kapalıysa beklenmez")
        self.assertEqual(sy.paylasilacak_diller(a), list(sy.DILLER), "anahtar verilmezse yalnız ayara bakılır")


class DryRun(Temel):
    def test_dry_run_hic_ag_cagrisi_ve_yazma_yapmaz(self):
        self.manifest_yaz()
        a = ayar(x=True, instagram=True, instagram_reel=True, youtube=True)
        g, hata, _ = self.calistir(YasakAg(), a, dry=True, tum={})
        self.assertEqual((g, hata), (0, []))
        self.assertFalse(self.kayit.exists())
        self.assertEqual(json.loads(self.manifest.read_text(encoding="utf-8"))["videolar"]["oyun-yama-1"]["tr"].get("youtube"), None)

    def test_dry_run_eski_kaydi_dosyaya_gocurmez(self):
        eski = {"oyun-yama-1|tr|instagram": {"zaman": "2026-11-14T10:00:00+00:00"}}
        self.kayit.write_text(json.dumps(eski), encoding="utf-8")
        self.calistir(YasakAg(), ayar(instagram=True), dry=True)
        self.assertEqual(json.loads(self.kayit.read_text(encoding="utf-8")), eski)


class Metin(unittest.TestCase):
    def test_x_metni_sinirda(self):
        x = haber()
        x["diller"]["tr"]["baslik"] = "B" * 300
        for mod in ("gonderide", "profilde"):
            m = sy.x_metin("tr", x, "https://ctrl-agame.com/tr/a.html?utm_source=x", mod)
            n = len(m) - (len("https://ctrl-agame.com/tr/a.html?utm_source=x") - 23 if mod == "gonderide" else 0)
            self.assertLessEqual(n, 280)

    def test_sayfa_bekle_hazirsa_uyumaz(self):
        ag = SahteAg()
        self.assertEqual(sy.sayfa_bekle(ag, [haber()]), 0)

    def test_sayfa_bekle_her_paylasilacak_dilin_sayfasini_sorar(self):
        sorulan = []

        class Ag(SahteAg):
            def yayinda_mi(self, url):
                sorulan.append(url)
                return True

        self.assertEqual(sy.sayfa_bekle(Ag(), [haber()], diller=["tr", "en", "fr"]), 0)
        self.assertEqual(len(sorulan), 3)
        self.assertTrue(any("/en/game-news/" in u for u in sorulan))
        self.assertTrue(any("/fr/" in u for u in sorulan))
        self.assertFalse(any("/es/" in u for u in sorulan), "paylaşılmayacak dil beklenmez")

    def test_sayfa_bekle_bir_dil_gec_acilirsa_onu_bekler(self):
        sayac = {"en": 0}

        class Ag(SahteAg):
            def yayinda_mi(self, url):
                if "/en/" in url:
                    sayac["en"] += 1
                    return sayac["en"] >= 3
                return True

        self.assertEqual(sy.sayfa_bekle(Ag(), [haber()], deneme=5, aralik=0, diller=["tr", "en"]), 0)
        self.assertEqual(sayac["en"], 3)

    def test_sayfa_bekle_bos_dil_listesi_beklemez(self):
        ag = SahteAg()
        ag.yayinda = False
        self.assertEqual(sy.sayfa_bekle(ag, [haber()], diller=[]), 0)

    def test_sayfa_bekle_sure_dolunca_yine_de_devam_eder(self):
        ag = SahteAg()
        ag.yayinda = False
        self.assertEqual(sy.sayfa_bekle(ag, [haber()], deneme=3, aralik=0), 0)


class IgSunucuTests(unittest.TestCase):
    def test_anahtar_turune_gore_sunucu(self):
        self.assertEqual(sy.ig_sunucu("EAAYabc"), "graph.facebook.com")
        self.assertEqual(sy.ig_sunucu("IGAAabc"), "graph.instagram.com")


class SessizSaat(Temel):
    """video_sessiz_saat_utc: bu aralıkta Reels/Shorts gitmez, görsel gider, niyet kaydı yazılmaz."""

    def ayari(self, sessiz=None):
        a = ayar(instagram=True, instagram_reel=True, youtube=True)
        a["calisma_basina_en_fazla"] = 1
        if sessiz is not None:
            a["video_sessiz_saat_utc"] = sessiz
        return a

    def saat(self, h):
        return datetime(2026, 11, 15, h, 17, tzinfo=timezone.utc)

    def test_sessiz_saatte_video_gitmez_kayit_yazilmaz_gorsel_gider(self):
        for h in (23, 21, 0, 3):
            self.tearDown()
            self.setUp()
            self.manifest_yaz()
            ag = SahteAg()
            g, hata, _ = self.calistir(ag, self.ayari({"bas": 21, "son": 4}), simdi=self.saat(h))
            self.assertEqual((g, hata), (1, []), h)
            self.assertEqual(set(self.kayitlar()), {"oyun-yama-1|tr|instagram|gorsel"}, h)
            self.assertTrue(all(r["durum"] == "tamam" for r in self.kayitlar().values()))
            self.assertFalse(any("googleapis" in u for _, u in ag.cagrilar), "Shorts yüklenmez")

    def test_sessiz_saat_cikti_nedeni_yazar(self):
        self.manifest_yaz()
        satirlar = []
        sy.calistir(self.ayari({"bas": 21, "son": 4}), [haber()], kayit_yolu=self.kayit, manifest_yolu=self.manifest,
                    tum=SIRLAR, ag=SahteAg(), dry_run=False, bugun=BUGUN, simdi=self.saat(23), cikti=satirlar.append)
        self.assertTrue(any("sessiz saat" in s and "instagram_reel" in s for s in satirlar))
        self.assertTrue(any("sessiz saat" in s and "youtube" in s for s in satirlar))

    def test_saat_disinda_ve_sonraki_calismada_video_gider(self):
        for h in (4, 12, 20):
            self.tearDown()
            self.setUp()
            self.manifest_yaz()
            g, hata, _ = self.calistir(SahteAg(), self.ayari({"bas": 21, "son": 4}), simdi=self.saat(h))
            self.assertEqual(hata, [], h)
            self.assertIn("oyun-yama-1|tr|instagram|reel", self.kayitlar(), h)
            self.assertIn("oyun-yama-1|tr|youtube|short", self.kayitlar(), h)
        # sessiz saatte atlanan video, sıradaki çalışmada normal yayınlanır
        self.tearDown()
        self.setUp()
        self.manifest_yaz()
        a = self.ayari({"bas": 21, "son": 4})
        self.calistir(SahteAg(), a, simdi=self.saat(23))
        self.calistir(SahteAg(), a, simdi=self.saat(5))
        self.assertIn("oyun-yama-1|tr|instagram|reel", self.kayitlar())
        self.assertIn("oyun-yama-1|tr|youtube|short", self.kayitlar())

    def test_ayar_yoksa_ya_da_gecersizse_kisit_yok(self):
        for sessiz in (None, {}, "gece", {"bas": 21}, {"bas": 5, "son": 5}, {"bas": "21", "son": 4},
                       {"bas": 25, "son": 4}, {"bas": True, "son": 4}, [21, 4]):
            self.tearDown()
            self.setUp()
            self.manifest_yaz()
            g, hata, _ = self.calistir(SahteAg(), self.ayari(sessiz), simdi=self.saat(23))
            self.assertEqual(hata, [], sessiz)
            self.assertIn("oyun-yama-1|tr|instagram|reel", self.kayitlar(), sessiz)
            self.assertIn("oyun-yama-1|tr|youtube|short", self.kayitlar(), sessiz)

    def test_gece_yarisini_asmayan_aralik(self):
        self.assertTrue(sy.sessiz_saat_mi({"video_sessiz_saat_utc": {"bas": 1, "son": 5}}, 1))
        self.assertTrue(sy.sessiz_saat_mi({"video_sessiz_saat_utc": {"bas": 1, "son": 5}}, 4))
        self.assertFalse(sy.sessiz_saat_mi({"video_sessiz_saat_utc": {"bas": 1, "son": 5}}, 5))
        self.assertFalse(sy.sessiz_saat_mi({"video_sessiz_saat_utc": {"bas": 1, "son": 5}}, 0))
        self.assertFalse(sy.sessiz_saat_mi({"video_sessiz_saat_utc": {"bas": 1, "son": 5}}, 23))

    def test_gece_yarisini_asan_aralik_sinirlari(self):
        a = {"video_sessiz_saat_utc": {"bas": 21, "son": 4}}
        icinde = [h for h in range(24) if sy.sessiz_saat_mi(a, h)]
        self.assertEqual(icinde, [0, 1, 2, 3, 21, 22, 23])
        self.assertFalse(sy.sessiz_saat_mi({}, 23))

    def test_dry_run_ve_benzet_ayni_kurali_gorur(self):
        self.manifest_yaz()
        secilen = []
        sy.calistir(self.ayari({"bas": 21, "son": 4}), [haber()], kayit_yolu=self.kayit, manifest_yolu=self.manifest,
                    tum=SIRLAR, ag=YasakAg(), dry_run=True, bugun=BUGUN, simdi=self.saat(23),
                    cikti=lambda *_: None, secildi=lambda k, r: secilen.append(r))
        self.assertEqual({r["bicim"] for r in secilen}, {"gorsel"})
        r = sy.benzet(self.ayari({"bas": 21, "son": 4}), [haber()], {}, self.manifest, self.saat(22), 8,
                      kok=self.kok, cikti=lambda *_: None)
        for x in r:
            if x["bicim"] in ("reel", "short"):
                self.assertNotIn((x["saat"] + 22) % 24, (21, 22, 23, 0, 1, 2, 3), x)

    def test_klip_hesabi_etkilenmez(self):
        # klip hesabı ayrı geçiştir; sessiz saat yalnız haber hesaplarının Reels/Shorts'unu durdurur
        import inspect
        kaynak = inspect.getsource(sy.calistir)
        self.assertEqual(kaynak.count("sessiz_saat_mi("), 1)
        self.assertLess(kaynak.index("sessiz_saat_mi("), kaynak.index("# ---- Klip/derleme"))


class YtKapakGuncelle(Temel):
    def _hazirla(self):
        self.manifest.write_text(json.dumps({
            "surum": 1,
            "taban": "https://medya.test/v/",
            "videolar": {
                "oyun-a": {"tr": {"kapak": "oyun-a-tr-kapak.jpg", "mp4_540": "a540.mp4", "mp4_720": "a720.mp4", "sure": 30.0}},
                "oyun-beklet": {"tr": {"kapak": "oyun-beklet-tr-kapak.jpg", "mp4_540": "b540.mp4", "mp4_720": "b720.mp4", "sure": 30.0, "beklet": True}},
            },
        }), encoding="utf-8")
        self.kayit.write_text(json.dumps({
            "konu-a|tr|youtube|short": {"id": "oyun-a", "dil": "tr", "platform": "youtube", "bicim": "short", "durum": "tamam", "kimlik": "VID_A"},
            "konu-b|tr|youtube|short": {"id": "oyun-beklet", "dil": "tr", "platform": "youtube", "bicim": "short", "durum": "tamam", "kimlik": "VID_B"},
            "klip-1|klip|youtube|short": {"id": "klip-1", "dil": "klip", "hesap": "klip", "platform": "youtube", "bicim": "short", "sosyal_tur": "klip", "durum": "tamam", "kimlik": "VID_K"},
            "konu-a|tr|instagram|reel": {"id": "oyun-a", "dil": "tr", "platform": "instagram", "bicim": "reel", "durum": "tamam", "kimlik": "IG_A"},
            "konu-c|tr|youtube|short": {"id": "oyun-yok", "dil": "tr", "platform": "youtube", "bicim": "short", "durum": "tamam", "kimlik": "VID_C"},
        }), encoding="utf-8")

    def test_yayinlanmis_haber_shortlari_guncellenir_beklet_dahil_klip_atlanir(self):
        self._hazirla()
        ag = SahteAg()
        ozet = sy.yt_kapaklari_guncelle(kayit_yolu=self.kayit, manifest_yolu=self.manifest, tum=SIRLAR, ag=ag, cikti=lambda *_: None)
        self.assertEqual((ozet["guncellenen"], ozet["hatali"], ozet["atlanan"]), (2, 0, 1))
        thumb_cagrilar = [u for _, u in ag.cagrilar if "thumbnails/set" in u]
        self.assertEqual(len(thumb_cagrilar), 2)
        self.assertEqual(sum("oauth2.googleapis.com" in u for _, u in ag.cagrilar), 1)
        self.assertFalse(any("uploadType=resumable" in u for _, u in ag.cagrilar))

    def test_dry_run_ag_cagrisi_yapmaz(self):
        self._hazirla()
        ozet = sy.yt_kapaklari_guncelle(kayit_yolu=self.kayit, manifest_yolu=self.manifest, tum={}, ag=YasakAg(), dry_run=True, cikti=lambda *_: None)
        self.assertEqual((ozet["guncellenen"], ozet["hatali"], ozet["atlanan"]), (2, 0, 1))

    def test_yalniz_id_suzgeci(self):
        self._hazirla()
        ag = SahteAg()
        ozet = sy.yt_kapaklari_guncelle(kayit_yolu=self.kayit, manifest_yolu=self.manifest, tum=SIRLAR, ag=ag, yalniz_id={"VID_A"}, cikti=lambda *_: None)
        self.assertEqual((ozet["guncellenen"], ozet["hatali"], ozet["atlanan"]), (1, 0, 0))


if __name__ == "__main__":
    unittest.main()
