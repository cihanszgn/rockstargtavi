"""Klip kanalı (ayrı hesap) + marka yazısı: kurulum aracı KLIP hedefi (sahte OAuth, gerçek ağ/tarayıcı/gh yok), marka ayarı,
panel kanal kutusu, `yukle` hedef hesabı, manifest hesap koruması. Hiçbir test gerçek sır, ağ ya da DPAPI dosyasına dokunmaz."""
import contextlib
import io
import json
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import klip_sosyal as ks  # noqa: E402
import klip_yayin as ky  # noqa: E402
import sosyal_kurulum as sk  # noqa: E402
import sosyal_yayinla as sy  # noqa: E402
import yayin_klip as yk  # noqa: E402
import test_klip_yayin as tky  # noqa: E402
from test_klip_yayin import KlipAg, oge, paket  # noqa: E402
from test_sosyal_yayinla import BUGUN, SIMDI, YasakAg  # noqa: E402


class HesapSabitleri(unittest.TestCase):
    def test_klip_hesabi_adi_her_yerde_ayni(self):
        self.assertEqual(sy.KLIP_HESABI, "klip")
        self.assertEqual(ks.KLIP_HESABI, sy.KLIP_HESABI)
        self.assertEqual(sk.KLIP_HESABI, sy.KLIP_HESABI)
        self.assertIn(sy.KLIP_HESABI, sk.HEDEF_AD)
        self.assertNotIn(sy.KLIP_HESABI, sy.DILLER)


class KurulumKlipHedefi(unittest.TestCase):
    """youtube_ekle("klip"): OAuth, gh, DPAPI ve ayar dosyası sahte; sır YALNIZ YT_KLIP_* adıyla yazılır."""

    def setUp(self):
        self.gecici = tempfile.TemporaryDirectory()
        self.addCleanup(self.gecici.cleanup)
        self.ayar = pathlib.Path(self.gecici.name) / "ayarlar.json"
        self.ayar.write_text(json.dumps({"hesaplar": {"tr": {"youtube": True}, "en": {"youtube": False}},
                                         "klip": {"youtube": False, "instagram": False}}), encoding="utf-8")
        self.sirlar = []
        self.saklanan = {}
        self.izin_sayisi = 0
        self.kayitli = {"tr": {"CLIENT_ID": "kayitli-cid", "CLIENT_SECRET": "kayitli-sec", "REFRESH_TOKEN": "tr-token"}}

    def calistir(self, refresh="klip-token", girdi=("",), tr_token="tr-token"):
        self.kayitli["tr"]["REFRESH_TOKEN"] = tr_token

        def izin(cid, sec):
            self.izin_sayisi += 1
            return refresh

        def yt_oku(dil):
            return self.kayitli.get(dil)

        def yt_sakla(dil, s):
            self.saklanan[dil] = dict(s)

        cikti = io.StringIO()
        with contextlib.redirect_stdout(cikti), \
                mock.patch.object(sk, "AYAR", self.ayar), \
                mock.patch.object(sk, "yt_izin_al", izin), \
                mock.patch.object(sk, "yt_dene", return_value="Komixsi"), \
                mock.patch.object(sk, "yt_oku", yt_oku), \
                mock.patch.object(sk, "yt_sakla", yt_sakla), \
                mock.patch.object(sk, "sir_yaz", lambda ad, d: self.sirlar.append((ad, d))), \
                mock.patch.object(sk.getpass, "getpass", side_effect=AssertionError("kayıtlı istemci varken sorulmamalı")), \
                mock.patch("builtins.input", side_effect=list(girdi)), \
                mock.patch.object(sk.webbrowser, "open", side_effect=AssertionError("tarayıcı açılmamalı")):
            sk.youtube_ekle(sk.KLIP_HESABI)
        return cikti.getvalue()

    def test_yalniz_yt_klip_sirlari_yazilir_ve_klip_ayari_acilir(self):
        cikti = self.calistir()
        self.assertEqual([a for a, _ in self.sirlar],
                         ["YT_KLIP_CLIENT_ID", "YT_KLIP_CLIENT_SECRET", "YT_KLIP_REFRESH_TOKEN"])
        self.assertEqual(dict(self.sirlar)["YT_KLIP_REFRESH_TOKEN"], "klip-token")
        self.assertEqual(list(self.saklanan), ["klip"])           # TR kaydına dokunulmaz
        ayar = json.loads(self.ayar.read_text(encoding="utf-8"))
        self.assertTrue(ayar["klip"]["youtube"])
        self.assertTrue(ayar["hesaplar"]["tr"]["youtube"])
        self.assertFalse(ayar["hesaplar"]["en"]["youtube"])
        self.assertIn("TAMAM", cikti)
        for ad, deger in self.sirlar:                              # sır değeri ekrana yazılmaz
            self.assertNotIn(deger, cikti)

    def test_tr_ile_ayni_izin_reddedilir_hicbir_sey_yazilmaz(self):
        cikti = self.calistir(refresh="tr-token")
        self.assertEqual(self.sirlar, [])
        self.assertEqual(self.saklanan, {})
        self.assertFalse(json.loads(self.ayar.read_text(encoding="utf-8"))["klip"]["youtube"])
        self.assertIn("OLMADI", cikti)

    def test_kayitli_istemci_reddedilirse_yeniden_sorulur(self):
        with self.assertRaises(AssertionError):                     # getpass çağrılır -> sahte tuzak patlar (kanıt: soruldu)
            self.calistir(girdi=("h",))
        self.assertEqual(self.sirlar, [])

    def test_diger_diller_eski_gibi_yt_dil_sirlari(self):
        self.sirlar.clear()
        with contextlib.redirect_stdout(io.StringIO()), \
                mock.patch.object(sk, "AYAR", self.ayar), \
                mock.patch.object(sk, "yt_izin_al", return_value="en-token"), \
                mock.patch.object(sk, "yt_dene", return_value="EN kanal"), \
                mock.patch.object(sk, "yt_sakla"), \
                mock.patch.object(sk, "sir_yaz", lambda ad, d: self.sirlar.append(ad)), \
                mock.patch.object(sk.getpass, "getpass", return_value="deger"):
            sk.youtube_ekle("en")
        self.assertEqual(self.sirlar, ["YT_EN_CLIENT_ID", "YT_EN_CLIENT_SECRET", "YT_EN_REFRESH_TOKEN"])

    def test_klip_sir_adlari_yayinla_ile_uyumlu(self):
        self.assertEqual(sorted(f"YT_KLIP_{a}" for a in sy.GEREKEN["youtube"]),
                         ["YT_KLIP_CLIENT_ID", "YT_KLIP_CLIENT_SECRET", "YT_KLIP_REFRESH_TOKEN"])


class MarkaAyari(unittest.TestCase):
    def test_marka_yazisi_varsayilan_ayar_ve_bos(self):
        self.assertEqual(yk.marka_yazisi({}), yk.MARKA_YAZI_VARSAYILAN)
        self.assertEqual(yk.marka_yazisi({"marka_yazi": "  Komixsi  "}), "Komixsi")
        self.assertEqual(yk.marka_yazisi({"marka_yazi": ""}), "")

    def test_repodaki_ayar_komixsi_ve_eski_marka_yok(self):
        a = json.loads((pathlib.Path(__file__).resolve().parents[1] / "otomasyon" / "klip-yayincilar.json")
                       .read_text(encoding="utf-8"))["ayar"]
        self.assertEqual(a["marka_yazi"], "Komixsi")
        self.assertEqual(yk.paylasim_imzasi(a), ("Komixsi", ["#Komixsi"]))

    def test_marka_degisince_imza_degisir_eski_marka_eski_imza(self):
        self.assertNotIn("marka", yk.duzen_imzasi({}))
        self.assertEqual(yk.duzen_imzasi({"marka_yazi": "Komixsi"})["marka"], "Komixsi")
        self.assertNotEqual(yk.duzen_imzasi({"marka_yazi": "A"}), yk.duzen_imzasi({"marka_yazi": "B"}))

    def test_marka_analiz_onbellegini_bozmaz(self):
        for k in ("marka_yazi", "klip_paylasim_imza", "klip_ek_etiketler"):
            self.assertIn(k, yk.GORSEL_AYAR)

    def test_marka_ayari_pakete_ozel(self):
        self.assertEqual(yk.marka_ayari("Yeni Kanal"),
                         {"marka_yazi": "Yeni Kanal", "klip_paylasim_imza": "Yeni Kanal", "klip_ek_etiketler": ["#YeniKanal"]})
        self.assertEqual(yk.marka_ayari("")["klip_ek_etiketler"], [])

    def test_aciklama_imza_ve_etiket_ayardan(self):
        vod = {"yayinci": "Eraycan", "platform": "kick", "tarih": "2026-11-12", "kanal_url": "https://kick.com/eray",
               "vod_url": "https://kick.com/eray/videos/a", "kanal": "eray"}
        klip = {"klip_baslangic_sn": 100.0, "klip_bitis_sn": 140.0}
        a = yk.aciklama_uret(vod, klip, {"klip_paylasim_imza": "Komixsi", "klip_ek_etiketler": ["#Komixsi"]})
        self.assertIn("Komixsi", a)
        self.assertIn("#Komixsi", a)
        self.assertNotIn("CTRL+A GAME", a)
        self.assertNotIn("ctrl-agame", a)
        self.assertNotIn("CTRLAGAME", a)
        bos = yk.aciklama_uret(vod, klip, {"klip_paylasim_imza": "", "klip_ek_etiketler": []})
        self.assertNotIn("Komixsi", bos)
        self.assertNotIn("CTRLAGAME", bos)

    def test_klip_metni_komixsi_ctrla_game_yok(self):
        ayar = {"klip_paylasim_imza": "Komixsi", "klip_ek_etiketler": ["#Komixsi"]}
        m = ks.klip_metni(paket(), "Eray", (), ayar)
        yazi = m["aciklama"] + " " + " ".join(m["etiketler"])
        self.assertIn("#Komixsi", m["etiketler"])
        self.assertTrue(m["aciklama"].rstrip().endswith("Komixsi"))
        for yasak in ("CTRLA_GAME", "CTRL+A GAME", "ctrl-agame"):
            self.assertNotIn(yasak, yazi)

    def test_klip_metni_ayarsiz_eski_davranis(self):
        m = ks.klip_metni(paket(), "Eray")
        self.assertIn("#CTRLA_GAME", m["etiketler"])

    def test_paket_markasi_ayari_ezer(self):
        p = paket(duzenleme={"marka_yazi": "Baska Kanal"})
        m = ks.klip_metni(p, "Eray", (), {"klip_paylasim_imza": "Komixsi", "klip_ek_etiketler": ["#Komixsi"]})
        self.assertIn("#BaskaKanal", m["etiketler"])
        self.assertNotIn("#Komixsi", m["etiketler"])
        self.assertTrue(m["aciklama"].rstrip().endswith("Baska Kanal"))
        self.assertEqual(ks.marka_paylasim(paket(duzenleme={"marka_yazi": ""}), {"klip_paylasim_imza": "Komixsi"}), ("", []))

    def test_derleme_metni_etiketi_ayardan(self):
        m = ks.derleme_metni({"baslik": "Kolaj", "aciklama": "x"}, (), {"klip_ek_etiketler": ["#Komixsi"]})
        self.assertEqual(m["etiketler"], ["#Komixsi", "#Kick"])

    def test_marka_ve_markasiz_birlikte_verilemez(self):
        with self.assertRaises(yk.KlipHatasi):
            yk.paketten_uret(pathlib.Path("yok.json"), {}, pathlib.Path("."), secenek={"marka": "X", "markasiz": True})

    def test_marka_komut_satirinda_tanimli(self):
        self.assertTrue(yk.MARKA_AZAMI >= 20)
        kaynak = (pathlib.Path(yk.__file__)).read_text(encoding="utf-8")
        self.assertIn("'--marka'", kaynak)
        self.assertIn("'--markasiz'", kaynak)


class PanelKanalKutusu(tky.KlipYayinTemel):
    def setUp(self):
        super().setUp()
        self.sakla = self.kok / "sakla"
        self.sakla.mkdir()
        self.ayar = {"ayar": {"marka_yazi": "Komixsi"}}

    def durum(self, yt_dosya=False, ig_dosya=False, **klip):
        if yt_dosya:
            (self.sakla / "yt_klip.bin").write_bytes(b"x")
        if ig_dosya:
            (self.sakla / "ig_klip.bin").write_bytes(b"x")
        return ky.klip_hesabi_durumu(self.ayar, {"klip": klip}, self.sakla)

    def test_bagli_degil_uyari_ve_ad(self):
        h = self.durum(youtube=True, instagram=False)
        self.assertEqual(h, {"ad": "Komixsi", "youtube": False, "instagram": False})
        k = ky.klip_hesabi_kutusu(h)
        self.assertIn("Klipler şu kanalda paylaşılır: <b>Komixsi</b> (bağlı değil)", k)
        self.assertIn("HİÇBİR hesaba gitmez", k)
        self.assertIn("YouTube kanalı bağla", k)

    def test_bagli(self):
        h = self.durum(yt_dosya=True, youtube=True)
        k = ky.klip_hesabi_kutusu(h)
        self.assertIn("<b>Komixsi</b> (bağlı)", k)
        self.assertNotIn("HİÇBİR", k)

    def test_ayar_kapaliysa_dosya_olsa_da_bagli_degil_ve_ig_ayri(self):
        self.assertFalse(self.durum(yt_dosya=True, youtube=False)["youtube"])
        self.assertFalse(self.durum(ig_dosya=True, instagram=False)["instagram"])
        self.assertTrue(self.durum(ig_dosya=True, instagram=True)["instagram"])

    def test_instagram_kutusu_klip_ig_yokken_kapali_ve_aciklamali(self):
        h = ky.html_uret(ky.tara(), self.man(), "z", None, {"ad": "Komixsi", "youtube": True, "instagram": False})
        self.assertIn("Klipler şu kanalda paylaşılır", h)
        # durağan sayfada düzen paneli yok; panel doğrudan denenir
        self.paket_yaz()
        self.cli("liste")
        o = dict(next(x for x in ky.tara() if x["tur"] == "klip"), no="1")
        pn = ky.duzen_paneli(o, None, False, "kamera", {"ad": "Komixsi", "youtube": True, "instagram": False})
        self.assertRegex(pn, r"name=p_instagram[^>]*disabled")
        self.assertIn("klip Instagram hesabı bağlı değil", pn)
        self.assertIn("YouTube Short (Komixsi)", pn)
        acik = ky.duzen_paneli(o, None, False, "kamera", {"ad": "Komixsi", "youtube": True, "instagram": True})
        self.assertNotRegex(acik, r"name=p_instagram[^>]*disabled")
        self.assertNotIn("klip Instagram hesabı bağlı değil", acik)


class YukleHedefHesap(tky.KlipYayinTemel):
    def test_kuru_cikti_hedef_hesap_klip(self):
        self.paket_yaz()
        self.cli("liste")
        self.cli("onayla", "1")
        with mock.patch("subprocess.run", side_effect=AssertionError("kuru çalıştırmada komut koştu")):
            kod, cikti = self.cli("yukle", "--kuru")
        self.assertEqual(kod, 0)
        self.assertIn("hedef hesap: klip", cikti)

    def test_manifest_hesap_alani_kayitta_yazili_sabit(self):
        self.assertEqual((ks.HESAP_ALANI, ks.KLIP_HESABI), ("hesap", "klip"))


class ManifestHesapKorumasi(tky.KlipPaylasim):
    """Manifestte hesap alanı klip dışı bir değerse klip gönderilmez; klip/boş ise klip hesabına gider (davranış testi)."""

    def gonder(self, hesap_alani):
        o = oge(yayinda=True)
        if hesap_alani is not None:
            o["yayinda"]["hesap"] = hesap_alani
        self.klip_yaz({"k1": o})
        ag = KlipAg()
        self.kos(ag, self.hesap_ayari(instagram=False))
        return ag, self.kayitlar()

    def test_klip_ya_da_bos_hesap_klip_kanalina_gider(self):
        for deger in ("klip", None):
            ag, kayit = self.gonder(deger)
            self.assertEqual(list(kayit), ["k1|klip|youtube|short"], deger)
            self.assertEqual(set(ag.yt_istemci), {"klip-cid"})
            self.kayit.unlink(missing_ok=True)

    def test_baska_hesap_yazan_klip_hicbir_yere_gitmez(self):
        ag, kayit = self.gonder("tr")
        self.assertEqual((kayit, ag.cagrilar, ag.yt_istemci), ({}, [], []))

    def test_dry_run_anahtarsiz_klip_hesabi_satirlari(self):
        self.klip_yaz({"k1": oge()})
        satirlar = []
        sy.calistir(self.hesap_ayari(instagram=False), [], kayit_yolu=self.kayit, manifest_yolu=self.manifest, tum={}, ag=YasakAg(),
                    dry_run=True, anahtarsiz_goster=True, bugun=BUGUN, simdi=SIMDI, cikti=satirlar.append, klip_yolu=self.klip)
        klip = [x for x in satirlar if "/klip  k1" in x]
        self.assertEqual(len(klip), 1, satirlar)
        self.assertIn("(hesap: klip)", klip[0])
        self.assertFalse(any("hesap: tr" in x and "klip" in x for x in satirlar))


if __name__ == "__main__":
    unittest.main()
