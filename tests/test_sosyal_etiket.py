import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import sosyal_etiket as se  # noqa: E402
import sosyal_kuyruk as sk  # noqa: E402

DILLER = ("tr", "en", "fr", "es", "de", "nl", "zh")


def oge(oyun="Selaco", platform=("PC",), tur="guncelleme", etiketler=None, **ek):
    x = {"id": "x-1", "oyun": oyun, "platform": list(platform), "tur": tur,
         "diller": {d: {"baslik": "B", "ozet": "Ö"} for d in DILLER}}
    if etiketler is not None:
        for d in DILLER:
            x["diller"][d]["etiketler"] = list(etiketler)
    x.update(ek)
    return x


class Temel(unittest.TestCase):
    def setUp(self):
        se.onbellek_temizle()

    def tearDown(self):
        se.onbellek_temizle()


class OyunEtiketi(Temel):
    def test_ad_donusumu_ozgun_buyuk_kucuk_harf(self):
        self.assertEqual(se.oyun_etiketleri(oge("Counter-Strike 2"))[0], "#CounterStrike2")
        self.assertEqual(se.oyun_etiketleri(oge("PUBG: BATTLEGROUNDS"))[0], "#PUBGBATTLEGROUNDS")
        self.assertEqual(se.oyun_etiketleri(oge("Pokémon Pokopia"))[0], "#PokémonPokopia")
        self.assertEqual(se.oyun_etiketleri(oge("World of Warcraft"))[0], "#WorldofWarcraft")

    def test_uzun_alt_baslikta_yalniz_iki_nokta_oncesi(self):
        self.assertEqual(se.oyun_etiketleri(oge("Melvor Idle 2: A RuneScape Adventure")), ["#MelvorIdle2"])
        # kısa kalan alt başlık korunur
        self.assertEqual(se.oyun_etiketleri(oge("PUBG: BATTLEGROUNDS"))[0], "#PUBGBATTLEGROUNDS")

    def test_kisa_ad_ikinci_etiket(self):
        self.assertEqual(se.oyun_etiketleri(oge("World of Warcraft")), ["#WorldofWarcraft", "#WoW"])
        self.assertEqual(se.oyun_etiketleri(oge("Counter-Strike 2")), ["#CounterStrike2", "#CS2"])
        self.assertEqual(se.oyun_etiketleri(oge("PUBG: BATTLEGROUNDS")), ["#PUBGBATTLEGROUNDS", "#PUBG"])
        self.assertEqual(se.oyun_etiketleri(oge("VALORANT")), ["#VALORANT"])  # kısa ad addan farklı değil

    def test_kisa_ad_eslesme_takma_adindan_da_bulunur(self):
        self.assertEqual(se.oyun_etiketleri(oge("WoW: Forever"))[-1:], ["#WoW"])

    def test_gta_vi_ozel_durumu_rakamli_once(self):
        for ad in ("GTA VI", "Grand Theft Auto VI", "gta vi"):
            self.assertEqual(se.oyun_etiketleri(oge(ad)), ["#GTA6", "#GTAVI"], ad)

    def test_platform_ya_da_magaza_oyun_gibi_islenir(self):
        self.assertEqual(se.oyun_etiketleri(oge("Epic Games Store")), ["#EpicGamesStore"])
        self.assertEqual(se.oyun_etiketleri(oge("Nintendo eShop")), ["#NintendoeShop"])
        self.assertEqual(se.oyun_etiketleri(oge("PlayStation 5")), ["#PlayStation5"])

    def test_bos_oyun_etiketsiz(self):
        self.assertEqual(se.oyun_etiketleri(oge("")), [])
        self.assertEqual(se.oyun_etiketleri(oge("2026")), [])  # yalnız rakam hashtag olmaz


class OyunlarJsonYok(Temel):
    def test_dosya_yok_ya_da_bozuksa_calisir(self):
        eski = se.OYUNLAR_YOLU
        try:
            with tempfile.TemporaryDirectory() as d:
                se.OYUNLAR_YOLU = pathlib.Path(d) / "yok.json"
                self.assertEqual(se.oyunlar(), [])
                self.assertEqual(se.oyun_etiketleri(oge("World of Warcraft")), ["#WorldofWarcraft"])
                self.assertEqual(se.oyun_etiketleri(oge("GTA VI")), ["#GTA6", "#GTAVI"])
                self.assertIn("World of Warcraft", se.yt_anahtar_kelimeler("en", oge("World of Warcraft")))
                bozuk = pathlib.Path(d) / "bozuk.json"
                bozuk.write_text("{degil json", encoding="utf-8")
                se.OYUNLAR_YOLU = bozuk
                se.onbellek_temizle()
                self.assertEqual(se.oyunlar(), [])
                self.assertTrue(se.hashtagler("tr", oge("World of Warcraft"), 5))
        finally:
            se.OYUNLAR_YOLU = eski

    def test_dosya_bir_kez_okunur(self):
        a = se.oyunlar()
        self.assertIs(a, se.oyunlar())


class YazarEtiketleri(Temel):
    def test_sablon_etiketleri_yazar_sayilmaz(self):
        for d in DILLER:
            x = oge(etiketler=sk.SABLON[d]["etiket"].split())
            self.assertEqual(se.yazar_etiketleri(d, x), [], d)
            self.assertNotIn("#CTRLA_GAME", se.hashtagler(d, x, 5))

    def test_gecerli_yazar_etiketleri_gelir_bicimsiz_atilir(self):
        x = oge(etiketler=["#Yama", "Yama2", "#Çok Kelime", "#yama", "#Sezon3"])
        self.assertEqual(se.yazar_etiketleri("tr", x), ["#Yama", "#Sezon3"])

    def test_yazar_etiketi_yoksa_alan_eksik_calisir(self):
        x = oge()
        self.assertEqual(se.yazar_etiketleri("tr", x), [])
        self.assertEqual(se.yazar_etiketleri("tr", {"diller": {}}), [])


class Platform(Temel):
    def test_platform_esleme(self):
        p = se.platform_etiketi
        self.assertEqual(p(oge(platform=["PS5"])), "#PS5")
        self.assertEqual(p(oge(platform=["PlayStation"])), "#PS5")
        self.assertEqual(p(oge(platform=["Xbox Series X|S"])), "#Xbox")
        self.assertEqual(p(oge(platform=["Nintendo Switch 2"])), "#NintendoSwitch2")
        self.assertEqual(p(oge(platform=["Switch 2"])), "#NintendoSwitch2")
        self.assertEqual(p(oge(platform=["Nintendo Switch"])), "#NintendoSwitch")
        self.assertEqual(p(oge(platform=["PC"])), "#PCGaming")
        self.assertEqual(p(oge(platform=["Mobil"])), "#MobileGaming")
        self.assertIsNone(p(oge(platform=["Bulut"])))
        self.assertIsNone(p(oge(platform=[])))

    def test_listedeki_ilk_eslesen(self):
        self.assertEqual(se.platform_etiketi(oge(platform=["Bulut", "Xbox", "PC"])), "#Xbox")

    def test_oyunla_ayni_ise_atlanir(self):
        t = se.hashtagler("tr", oge("Xbox", platform=["Xbox"]), 5)
        self.assertEqual([x.casefold() for x in t].count("#xbox"), 1)


class Konu(Temel):
    def test_tur_konu_tablosu(self):
        beklenen = {"ucretsiz": {"tr": "#BedavaOyun", "en": "#FreeGames", "de": "#GratisSpiele", "fr": "#JeuxGratuits",
                                 "es": "#JuegosGratis", "nl": "#GratisGames", "zh": "#免费游戏"},
                    "indirim": {"tr": "#OyunFırsatları", "en": "#GameDeals", "de": "#GamingDeals", "fr": "#BonsPlansJeux",
                                "es": "#OfertasJuegos", "nl": "#GameDeals", "zh": "#游戏折扣"},
                    "guncelleme": {"tr": "#OyunHaberleri", "en": "#GamingNews", "de": "#GamingNews", "fr": "#ActuJeuxVideo",
                                   "es": "#NoticiasGaming", "nl": "#GameNieuws", "zh": "#游戏新闻"}}
        for tur, dd in beklenen.items():
            for d, t in dd.items():
                self.assertEqual(se.konu_etiketi(d, oge(tur=tur)), t, (tur, d))
                self.assertIn(t, se.hashtagler(d, oge(tur=tur), 5))
        for tur in ("haber", "cikis"):
            self.assertEqual(se.konu_etiketi("en", oge(tur=tur)), "#GamingNews")

    def test_takvim_firsat_ucretsiz_sosyal_tur(self):
        self.assertEqual(se.konu_etiketi("en", oge(tur="haber", sosyal_tur="firsat")), "#GameDeals")
        self.assertEqual(se.konu_etiketi("en", oge(tur="haber", sosyal_tur="ucretsiz")), "#FreeGames")
        self.assertEqual(se.konu_etiketi("en", oge(tur="haber", sosyal_tur="takvim")), "#GamingNews")


class Hashtagler(Temel):
    def test_sira_ve_genel_etiket_yedi_dil(self):
        genel = {"tr": "#Oyun", "en": "#Gaming", "de": "#Gaming", "nl": "#Gaming", "fr": "#JeuxVideo",
                 "es": "#Videojuegos", "zh": "#游戏"}
        for d in DILLER:
            x = oge("World of Warcraft", platform=["PC"], etiketler=["#Yama"])
            t = se.hashtagler(d, x, 6)
            self.assertEqual(t[:3], ["#WorldofWarcraft", "#WoW", "#Yama"], d)
            self.assertEqual(t[3], "#PCGaming")
            self.assertEqual(t[4], se.konu_etiketi(d, x))
            self.assertEqual(t[-1], genel[d])
            self.assertEqual(len(t), 6)

    def test_yasak_etiketler_uretilmez(self):
        for d in DILLER:
            t = [h.casefold() for h in se.hashtagler(d, oge(), 10)]
            for y in ("#ctrla_game", "#reels", "#shorts"):
                self.assertNotIn(y, t)

    def test_sinir_5_ve_3_ve_oncelik(self):
        x = oge("World of Warcraft", platform=["PC"], etiketler=["#Yama", "#Sezon", "#Raid"])
        t5 = se.hashtagler("tr", x, 5)
        self.assertEqual(t5, ["#WorldofWarcraft", "#WoW", "#Yama", "#PCGaming", "#OyunHaberleri"])
        t3 = se.hashtagler("tr", x, 3)
        self.assertEqual(t3, ["#WorldofWarcraft", "#WoW", "#Yama"])
        self.assertEqual(se.hashtagler("tr", x, 1), ["#WorldofWarcraft"])
        self.assertEqual(se.hashtagler("tr", x, 0), [])

    def test_yazar_yoksa_platform_konu_gelir(self):
        t = se.hashtagler("en", oge("World of Warcraft", platform=["PS5"]), 4)
        self.assertEqual(t, ["#WorldofWarcraft", "#WoW", "#PS5", "#GamingNews"])

    def test_yer_kalirsa_kalan_yazar_etiketleri(self):
        x = oge("Selaco", platform=[], etiketler=["#A1", "#B2", "#C3", "#D4", "#E5", "#F6"])
        t = se.hashtagler("tr", x, 5)
        self.assertEqual(len(t), 5)
        self.assertEqual(t[0], "#Selaco")
        self.assertIn("#OyunHaberleri", t)
        self.assertIn("#Oyun", t)

    def test_buyuk_kucuk_harf_duyarsiz_tekil(self):
        x = oge("Selaco", etiketler=["#selaco", "#SELACO", "#Yama", "#yama", "#pcgaming"])
        t = [h.casefold() for h in se.hashtagler("tr", x, 10)]
        self.assertEqual(len(t), len(set(t)))
        self.assertEqual(t.count("#selaco"), 1)
        self.assertEqual(t.count("#pcgaming"), 1)

    def test_gta_vi_videosunda_gta6_var(self):
        t = se.hashtagler("tr", oge("GTA VI", platform=["PS5", "Xbox"]), 5)
        self.assertEqual(t[:2], ["#GTA6", "#GTAVI"])

    def test_sablon_etiketli_turetilmis_ogede_oyun_etiketi_gelir(self):
        x = oge("Selaco", etiketler=sk.SABLON["tr"]["etiket"].split())
        t = se.hashtagler("tr", x, 5)
        self.assertEqual(t[0], "#Selaco")
        self.assertNotIn("#CTRLA_GAME", t)

    def test_dil_eksikse_calisir(self):
        x = oge()
        x["diller"] = {}
        self.assertTrue(se.hashtagler("tr", x, 5))
        self.assertTrue(se.hashtagler("xx", x, 5))  # bilinmeyen dil: İngilizce konu/genel


class YtAnahtarKelimeler(Temel):
    def test_icerik_ve_sira(self):
        x = oge("World of Warcraft", platform=["PC", "PS5"], etiketler=["#Yama"])
        k = se.yt_anahtar_kelimeler("en", x)
        self.assertEqual(k[0], "World of Warcraft")
        self.assertIn("WoW", k)
        self.assertIn("WoW: Forever", k)
        self.assertIn("World of Warcraft news", k)
        self.assertIn("PC", k)
        self.assertIn("PS5", k)
        self.assertIn("gaming news", k)
        self.assertIn("Yama", k)
        self.assertEqual(k[-1], "CTRL+A GAME")

    def test_takma_ad_en_cok_4(self):
        x = oge("World of Warcraft")
        k = se.yt_anahtar_kelimeler("tr", x)
        takma = {"WoW", "WoW: Forever", "World of Warcraft: Forever"}
        self.assertTrue(takma <= set(k))
        for kayit in se.oyunlar():
            if kayit["ad"] == "World of Warcraft":
                diger = [a for a in kayit["eslesme"] if a not in ("World of Warcraft", "WoW")]
                self.assertLessEqual(len(diger), 4)

    def test_kurallar_tekil_yasak_karakter_400(self):
        x = oge("Oyun <Adı>, Deneme", platform=["PC", "Xbox", "PS5", "Switch 2", "Mobil"],
                etiketler=["#E" + "x" * 30 + str(i) for i in range(40)])
        for d in DILLER:
            k = se.yt_anahtar_kelimeler(d, x)
            self.assertEqual(len(k), len({e.casefold() for e in k}))
            for e in k:
                self.assertFalse(set("<>,#") & set(e), e)
                self.assertEqual(e, e.strip())
            self.assertLessEqual(sum(len(e) + 1 for e in k), 400)
            self.assertTrue(k[0].startswith("Oyun"))

    def test_yedi_dilde_haber_sozu_ve_genel_ifade(self):
        for d in DILLER:
            k = se.yt_anahtar_kelimeler(d, oge("Selaco"))
            self.assertIn(f"Selaco {se.HABER_SOZU[d]}", k, d)
            for f in se.GENEL_IFADE[d]:
                self.assertIn(f, k, d)

    def test_sablon_etiketleri_anahtar_kelimeye_girmez(self):
        x = oge("Selaco", etiketler=sk.SABLON["tr"]["etiket"].split())
        k = se.yt_anahtar_kelimeler("tr", x)
        self.assertNotIn("Oyun", k)
        self.assertNotIn("CTRLA_GAME", k)


if __name__ == "__main__":
    unittest.main()
