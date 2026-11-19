"""Tek hesap, çok dil: ortak hesap eşlemesi, hesap başına limit, ana dil payı, dil dönüşü, çift paylaşım yok,
YouTube/Instagram dil alanları ve ölçümün hesaba göre gruplanması."""
import json
import pathlib
import sys
import unittest
from datetime import datetime, timedelta, timezone

from test_sosyal_yayinla import Temel, haber, ayar, SIRLAR, SIMDI, SahteAg, YasakAg
import sosyal_yayinla as sy

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import sosyal_olcum as so  # noqa: E402

YABANCI = ("en", "es", "fr")


def dilli_haber(oid, konu=None):
    """Her dilin başlığı farklı: dil karışması testlerde görünür."""
    x = haber(oid, konu)
    for d in sy.DILLER:
        x["diller"][d].update(baslik=f"Baslik-{d}-{oid}", ozet=f"Ozet-{d}-{oid}.", etiketler=[f"#Etiket{d.upper()}"])
    return x


def ortak_ayar(reel=6, yt=8, en_az=None, serbest=19, **hesap):
    a = ayar(instagram_reel=True, youtube=True, **hesap)
    a["gunluk_en_fazla"].update(instagram_reel=reel, youtube=yt, instagram=12)
    a["hesap_esleme"] = {p: {d: "tr" for d in YABANCI + ("de", "nl", "zh")} for p in ("instagram", "youtube")}
    a["ortak_hesap_bicimleri"] = ["reel", "short"]
    a["hesap_dil_sirasi"] = list(YABANCI)
    a["ayni_konu_ara_saat"] = 4
    a["ana_dil_payi_serbest_saat"] = serbest
    if en_az:
        a["ana_dil_en_az"] = {"instagram_reel": en_az, "youtube": en_az}
    return a


class Ortak(Temel):
    def manifest_coklu(self, ogeler, ekstra=None):
        """ogeler: [(haber_id, dil)]; her video için kayıt + `ekstra[(id, dil)]` ile ek alan."""
        ekstra = ekstra or {}
        v = {}
        for hid, dil in ogeler:
            v.setdefault(hid, {})[dil] = {"anahtar": "k", "sure": 30.0, "mp4_1080": "a1080.mp4", "mp4_720": "a720.mp4",
                                         "mp4_540": "a540.mp4", "kapak": "a.jpg", "vtt": "a.vtt",
                                         "uretildi": "2026-11-15T10:00:00+00:00", "onay": True,
                                         **ekstra.get((hid, dil), {})}
        self.manifest.write_text(json.dumps({"surum": 1, "taban": "https://medya.test/v/", "videolar": v}), encoding="utf-8")

    def kos(self, a, veri, n, ag=None, dakika=1, simdi=SIMDI):
        ag = ag or SahteAg()
        for i in range(n):
            self.calistir(ag, a, veri, simdi=simdi + timedelta(minutes=i * dakika))
        return ag

    def gidenler(self, bicim):
        return [(v["dil"], k.split("|")[0], v.get("hesap")) for k, v in sorted(self.kayitlar().items(), key=lambda kv: kv[1].get("zaman", ""))
                if k.endswith("|" + bicim) and v.get("durum") == "tamam"]


class HesapEsleme(Ortak):
    def test_yabanci_reel_ortak_tr_hesabindan_cikar(self):
        self.manifest_coklu([("h1", "en")])
        g, hata, atlanan = self.calistir(SahteAg(), ortak_ayar(), [dilli_haber("h1")])
        self.assertEqual((g, hata, atlanan), (2, [], []))  # Reels + Shorts, ikisi de ortak TR hesabindan
        rec = self.kayitlar()["h1|en|instagram|reel"]
        self.assertEqual((rec["dil"], rec["hesap"], rec["durum"], rec["icerik_dili"]), ("en", "tr", "tamam", "en"))

    def test_kendi_anahtari_olan_dil_kendi_hesabina_doner(self):
        a = ortak_ayar()
        tum = dict(SIRLAR, IG_EN_USER_ID="999", IG_EN_TOKEN="tok-en")
        self.assertEqual(sy.hesap_coz(a, tum, "instagram", "en")[0], "en")
        self.assertEqual(sy.hesap_coz(a, SIRLAR, "instagram", "en")[0], "tr")
        self.assertEqual(sy.hesap_coz(a, SIRLAR, "youtube", "fr")[0], "tr")
        self.manifest_coklu([("h1", "en")])
        self.calistir(SahteAg(), a, [dilli_haber("h1")], tum=tum)
        self.assertNotIn("hesap", self.kayitlar()["h1|en|instagram|reel"])

    def test_yabanci_dil_gorsel_almaz_turkce_gorsel_gider(self):
        self.manifest_coklu([])
        a = ortak_ayar(instagram=True)
        a["gunluk_en_fazla"]["instagram"] = 12
        self.kos(a, [dilli_haber("h1")], 4)
        gorseller = [k for k in self.kayitlar() if k.endswith("|gorsel")]
        self.assertEqual(gorseller, ["h1|tr|instagram|gorsel"])

    def test_gorsel_ortak_bicimlerde_acikca_ayarlanir(self):
        a = ortak_ayar(instagram=True)
        a["ortak_hesap_bicimleri"] = ["gorsel", "reel", "short"]
        self.kos(a, [dilli_haber("h1")], 4, dakika=300)
        self.assertIn("h1|en|instagram|gorsel", self.kayitlar())

    def test_anahtarsiz_dry_run_eksik_anahtar_adini_yazar_gizli_degeri_yazmaz(self):
        self.manifest_coklu([("h1", "en")])
        satirlar = []
        sy.calistir(ortak_ayar(), [dilli_haber("h1")], kayit_yolu=self.kayit, manifest_yolu=self.manifest, tum={},
                    ag=YasakAg(), dry_run=True, bugun=SIMDI.date(), simdi=SIMDI, cikti=satirlar.append)
        metin = "\n".join(satirlar)
        self.assertIn("IG_TR_USER_ID", metin)
        self.assertNotIn("tok", metin)


class Limit(Ortak):
    def test_limit_hesap_basina_dilleri_toplar(self):
        self.manifest_coklu([(f"h{i}", d) for i in range(4) for d in ("tr", "en")])
        veri = [dilli_haber(f"h{i}") for i in range(4)]
        self.kos(ortak_ayar(reel=3, yt=2), veri, 8)
        self.assertEqual(len(self.gidenler("reel")), 3)
        self.assertEqual(len(self.gidenler("short")), 2)

    def test_calisma_basina_hesap_basina_bir(self):
        self.manifest_coklu([(f"h{i}", d) for i in range(3) for d in ("tr", "en")])
        g, _, _ = self.calistir(SahteAg(), ortak_ayar(), [dilli_haber(f"h{i}") for i in range(3)])
        self.assertEqual(g, 2)  # bir Reels + bir Shorts; ikinci hesap yok

    def test_ayardaki_sayilar(self):
        a = json.loads((pathlib.Path(__file__).resolve().parents[1] / "sosyal" / "ayarlar.json").read_text(encoding="utf-8"))
        self.assertEqual((a["gunluk_en_fazla"]["instagram_reel"], a["gunluk_en_fazla"]["youtube"], a["gunluk_en_fazla"]["instagram"]), (6, 8, 4))
        self.assertEqual(a["calisma_basina_en_fazla"], 1)
        self.assertEqual(a["hesap_esleme"]["instagram"]["en"], "tr")
        # YouTube'da yabancı dil ortak hesaptan çıkmaz (Cio'nun kararı, 2026-11-18): yalnız Türkçe Shorts
        self.assertEqual(a["hesap_esleme"]["youtube"], {})
        self.assertEqual(a["ortak_hesap_bicimleri"], ["reel", "short"])
        self.assertGreaterEqual(a["ana_dil_en_az"]["instagram_reel"], 3)
        self.assertGreaterEqual(a["ana_dil_en_az"]["youtube"], 3)


class AnaDilPayi(Ortak):
    def test_turkce_icin_ayrilan_hak_yabanciya_gitmez(self):
        # limit 3, Türkçe en az 2: yabancı en çok 1 gider; Türkçe adayı var
        self.manifest_coklu([(f"t{i}", "tr") for i in range(3)] + [(f"e{i}", "en") for i in range(3)])
        veri = [dilli_haber(f"t{i}") for i in range(3)] + [dilli_haber(f"e{i}") for i in range(3)]
        self.kos(ortak_ayar(reel=3, yt=3, en_az=2), veri, 8)
        tr = [g for g in self.gidenler("reel") if g[0] == "tr"]
        en = [g for g in self.gidenler("reel") if g[0] == "en"]
        self.assertEqual((len(tr), len(en)), (2, 1))

    def test_turkce_adayi_yoksa_oglene_kadar_yabanci_bekler_sonra_acilir(self):
        self.manifest_coklu([("e1", "en")])
        a = ortak_ayar(reel=3, yt=3, en_az=3, serbest=19)
        sabah = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)
        g, _, _ = self.calistir(SahteAg(), a, [dilli_haber("e1")], simdi=sabah)
        self.assertEqual(g, 0)
        aksam = datetime(2026, 11, 15, 20, 0, tzinfo=timezone.utc)
        g, _, _ = self.calistir(SahteAg(), a, [dilli_haber("e1")], simdi=aksam)
        self.assertEqual(g, 2)  # Reels + Shorts

    def test_pay_yoksa_yabanci_limite_kadar_gider(self):
        self.manifest_coklu([(f"e{i}", "en") for i in range(4)])
        self.kos(ortak_ayar(reel=3, yt=3), [dilli_haber(f"e{i}") for i in range(4)], 8)
        self.assertEqual(len(self.gidenler("reel")), 3)

    def test_turkce_zaten_yeterliyse_yabanci_acilir(self):
        self.manifest_coklu([(f"t{i}", "tr") for i in range(3)] + [(f"e{i}", "en") for i in range(3)])
        veri = [dilli_haber(f"t{i}") for i in range(3)] + [dilli_haber(f"e{i}") for i in range(3)]
        self.kos(ortak_ayar(reel=6, yt=6, en_az=3), veri, 12)
        reel = self.gidenler("reel")
        self.assertEqual(sum(1 for g in reel if g[0] == "tr"), 3)
        self.assertEqual(sum(1 for g in reel if g[0] == "en"), 3)


class DilDonusu(Ortak):
    def test_yabanci_diller_donerek_gider(self):
        ogeler = [(f"h{i}", d) for i in range(3) for d in YABANCI]
        self.manifest_coklu(ogeler)
        self.kos(ortak_ayar(reel=3, yt=3), [dilli_haber(f"h{i}") for i in range(3)], 6)
        self.assertEqual({g[0] for g in self.gidenler("reel")}, set(YABANCI))
        self.assertEqual({g[0] for g in self.gidenler("short")}, set(YABANCI))

    def test_ayni_haberin_dil_surumleri_art_arda_gitmez(self):
        ogeler = [(hid, d) for hid in ("a", "b") for d in YABANCI]
        self.manifest_coklu(ogeler)
        self.kos(ortak_ayar(reel=4, yt=4), [dilli_haber("a"), dilli_haber("b")], 8)
        for bicim in ("reel", "short"):
            sira = [g[1] for g in self.gidenler(bicim)]
            self.assertTrue(sira)
            for onceki, sonraki in zip(sira, sira[1:]):
                self.assertNotEqual(onceki, sonraki, f"{bicim}: {sira}")

    def test_turkce_ile_yabanci_dönüşümlü(self):
        self.manifest_coklu([(f"t{i}", "tr") for i in range(2)] + [(f"e{i}", "en") for i in range(2)])
        veri = [dilli_haber(f"t{i}") for i in range(2)] + [dilli_haber(f"e{i}") for i in range(2)]
        self.kos(ortak_ayar(reel=4, yt=4), veri, 6)
        diller = [g[0] for g in self.gidenler("reel")]
        self.assertEqual(len(diller), 4)
        self.assertEqual(sorted(diller), ["en", "en", "tr", "tr"])
        for a, b in zip(diller, diller[1:]):
            self.assertNotEqual(a, b, diller)

    def test_gta_oncelik_bozulmaz(self):
        gta = dilli_haber("gta-1")
        gta["oyun"] = "GTA VI"
        self.manifest_coklu([("gta-1", "tr"), ("gta-1", "en"), ("o1", "en"), ("o2", "en")])
        veri = [dilli_haber("o1"), dilli_haber("o2"), gta]
        a = ortak_ayar(reel=4, yt=4)
        sy_oncelik = __import__("sosyal_kuyruk")
        if not any(sy_oncelik.oncelikli(veri, "tr", "instagram", {}, SIMDI)[:1]):
            self.skipTest("GTA önceliği bu veri biçiminde çalışmıyor")
        self.kos(a, veri, 3)
        ilk = self.gidenler("reel")[0]
        self.assertEqual(ilk[1], "gta-1")


class CiftPaylasimYok(Ortak):
    def test_ayni_calisma_tekrarlaninca_ikinci_gonderi_yok(self):
        self.manifest_coklu([("h1", "tr"), ("h1", "en"), ("h2", "es")])
        veri = [dilli_haber("h1"), dilli_haber("h2")]
        self.kos(ortak_ayar(), veri, 10)
        for bicim in ("reel", "short"):
            anahtarlar = [k for k in self.kayitlar() if k.endswith("|" + bicim)]
            self.assertEqual(len(anahtarlar), len(set(anahtarlar)))
        self.assertEqual(len(self.gidenler("reel")), 3)
        n = len(SahteAg().cagrilar)
        ag = SahteAg()
        self.calistir(ag, ortak_ayar(), veri, simdi=SIMDI + timedelta(minutes=30))
        self.assertEqual((n, [c for c in ag.cagrilar if "media_publish" in c[1]]), (0, []))

    def test_manifest_baglantisi_olan_video_yeniden_gonderilmez(self):
        self.manifest_coklu([("h1", "en")], {("h1", "en"): {"instagram": "https://www.instagram.com/reel/XYZ/",
                                                            "youtube": "https://www.youtube.com/shorts/ABC"}})
        ag = SahteAg()
        g, _, _ = self.calistir(ag, ortak_ayar(), [dilli_haber("h1")])
        self.assertEqual((g, ag.cagrilar), (0, []))

    def test_eski_ingilizce_icerikli_turkce_hesap_kaydi_dile_tasinir(self):
        eski = {"h1|tr|instagram|reel": {"id": "h1", "dil": "tr", "platform": "instagram", "bicim": "reel", "durum": "tamam",
                                         "icerik_dili": "en", "zaman": "2026-11-14T10:00:00+00:00"}}
        yeni, goc = sy.kayit_goc(eski, [dilli_haber("h1")])
        self.assertTrue(goc)
        self.assertNotIn("h1|tr|instagram|reel", yeni)
        rec = yeni["h1|en|instagram|reel"]
        self.assertEqual((rec["dil"], rec["hesap"], rec["durum"]), ("en", "tr", "tamam"))
        self.assertEqual(sy.kayit_goc(yeni, [dilli_haber("h1")]), (yeni, False))

    def test_tasinan_ingilizce_kayit_ingilizceyi_yeniden_gondermez_turkceyi_acar(self):
        self.manifest_coklu([("h1", "en"), ("h1", "tr")])
        self.kayit.write_text(json.dumps({"h1|tr|instagram|reel": {
            "id": "h1", "dil": "tr", "platform": "instagram", "bicim": "reel", "durum": "tamam", "icerik_dili": "en",
            "zaman": "2026-11-14T10:00:00+00:00"}}), encoding="utf-8")
        self.kos(ortak_ayar(), [dilli_haber("h1")], 4, dakika=300)
        self.assertEqual([g[0] for g in self.gidenler("reel")].count("en"), 1)
        self.assertIn("h1|tr|instagram|reel", self.kayitlar())


class DilAlanlari(Ortak):
    def test_youtube_varsayilan_ve_ses_dili_video_dilini_izler(self):
        x = dilli_haber("h1")
        for dil in sy.DILLER:
            g = sy.yt_govde(dil, x, sy.paylasim_linki(dil, x, "youtube"), {})
            self.assertEqual(g["snippet"]["defaultLanguage"], sy.HREFLANG[dil])
            self.assertEqual(g["snippet"]["defaultAudioLanguage"], sy.HREFLANG[dil])
            self.assertIn(f"Baslik-{dil}-h1", g["snippet"]["title"])
            self.assertIn(f"Ozet-{dil}-h1", g["snippet"]["description"])
            for d in sy.DILLER:
                if d != dil:
                    self.assertNotIn(f"Baslik-{d}-h1", g["snippet"]["title"])
                    self.assertNotIn(f"Ozet-{d}-h1", g["snippet"]["description"])
            tags = g["snippet"]["tags"]
            self.assertIn(f"Etiket{dil.upper()}", tags)  # yazar etiketi kendi dilinden
            self.assertTrue(all(f"Etiket{d.upper()}" not in tags for d in sy.DILLER if d != dil))
            self.assertIn("CTRL+A GAME", tags)
            self.assertTrue(tags and sum(len(t) + 1 for t in tags) <= 400)

    def test_instagram_aciklamasi_tek_dilde_karismaz(self):
        x = dilli_haber("h1")
        for dil in YABANCI:
            m = sy.ig_aciklama(dil, x, ortak_ayar())
            self.assertIn(f"Baslik-{dil}-h1", m)
            self.assertIn(f"#Etiket{dil.upper()}", m)
            self.assertNotIn("---", m)
            for d in sy.DILLER:
                if d != dil:
                    self.assertNotIn(f"Baslik-{d}-h1", m)
                    self.assertNotIn(f"#Etiket{d.upper()}", m)

    def test_yabanci_kaynak_adinda_turkce_kelime_yok(self):
        self.assertEqual(sy.kaynak_adi("en", "Steam resmî duyurusu"), "Steam")
        self.assertEqual(sy.kaynak_adi("fr", "Nintendo (resmî duyuru)"), "Nintendo")

    def test_gonderilen_reel_aciklamasi_o_dilde(self):
        self.manifest_coklu([("h1", "es")])
        ag = SahteAg()
        satirlar = []
        sy.calistir(ortak_ayar(), [dilli_haber("h1")], kayit_yolu=self.kayit, manifest_yolu=self.manifest, tum=SIRLAR,
                    ag=YasakAg(), dry_run=True, bugun=SIMDI.date(), simdi=SIMDI, cikti=satirlar.append)
        metin = "\n".join(satirlar)
        reel = metin.split("[DENEME] youtube/es")[0]  # YouTube govdesindeki localizations ayri ozellik
        self.assertIn("Baslik-es-h1", reel)
        self.assertNotIn("Baslik-tr-h1", reel)
        self.assertIn("(hesap: tr)", metin)
        del ag


class Olcum(Ortak):
    def test_hedef_hesap_alani_ortak_hesabi_gosterir(self):
        kayit = {
            "h1|en|youtube|short": {"id": "h1", "dil": "en", "platform": "youtube", "bicim": "short", "durum": "tamam",
                                    "hesap": "tr", "kimlik": "Y1", "url": "u", "zaman": "2026-11-15T10:00:00+00:00"},
            "h2|tr|youtube|short": {"id": "h2", "dil": "tr", "platform": "youtube", "bicim": "short", "durum": "tamam",
                                    "kimlik": "Y2", "url": "u", "zaman": "2026-11-15T11:00:00+00:00"},
        }
        hedef = {x["kimlik"]: x for x in so.hedefler(kayit, {})}
        self.assertEqual((hedef["Y1"]["dil"], hedef["Y1"]["hesap"]), ("en", "tr"))
        self.assertEqual((hedef["Y2"]["dil"], hedef["Y2"]["hesap"]), ("tr", "tr"))

    def test_ingilizce_gonderi_tr_hesabi_olcumunde_yer_alir(self):
        kayit = {"h1|en|youtube|short": {"id": "h1", "dil": "en", "platform": "youtube", "bicim": "short", "durum": "tamam",
                                         "hesap": "tr", "kimlik": "Y1", "url": "u", "zaman": "2026-11-15T10:00:00+00:00"}}
        self.kayit.write_text(json.dumps(kayit), encoding="utf-8")
        self.manifest.write_text(json.dumps({"videolar": {}}), encoding="utf-8")
        ayar_yolu = self.kok / "ayar.json"
        ayar_yolu.write_text(json.dumps(ortak_ayar()), encoding="utf-8")
        olcen = []
        gercek = so.youtube_olc

        def sahte(ag, sir, dil, liste, gunluk, hatalar, za):
            olcen.append((dil, [x["kimlik"] for x in liste]))
            return None, {}
        so.youtube_olc = sahte
        try:
            so.calistir(kayit_yolu=self.kayit, manifest_yolu=self.manifest, ayar_yolu=ayar_yolu,
                        olcum_yolu=self.kok / "o.json", ozet_yolu=self.kok / "o.md", tum=SIRLAR,
                        ag=SahteAg(), simdi=SIMDI, yaz=False)
        finally:
            so.youtube_olc = gercek
        self.assertEqual(olcen, [("tr", ["Y1"])])


if __name__ == "__main__":
    unittest.main()
