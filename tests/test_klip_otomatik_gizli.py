"""Otomatik gizli klip akışı (2026-11-22): onay beklemeden YouTube'a YALNIZ gizli (private) yükleme + tek Telegram mesajı.
Ağ, ssh, git, gh yok: hepsi sahte. Gerçek yükleme/push bu testlerde yapılmaz."""
import contextlib
import datetime
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
import klip_kilit as kk  # noqa: E402
import klip_sosyal as ks  # noqa: E402
import klip_yayin as ky  # noqa: E402
import sosyal_yayinla as sy  # noqa: E402
from test_klip_yayin import KLIP_SIRLARI, KlipAg, KlipYayinTemel, oge  # noqa: E402
from test_sosyal_yayinla import BUGUN, SIMDI, SIRLAR, Temel as SosyalTemel, ayar  # noqa: E402


def otomatik_oge(baslik="Eray otomatik klip | Eray", **ek):
    metin = {"baslik": baslik, "aciklama": "Kaynak: https://kick.com/eray", "etiketler": ["#Eray", "#Kick"]}
    return oge(baslik=baslik, onay={"zaman": "2026-11-22T10:00:00Z", "ozet": "ozet1", "metin_ozeti": ks.metin_ozeti(metin),
                                    "otomatik": True}, otomatik=True, **ek)


def elle_oge(baslik="Eray elle onaylı | Eray", **ek):
    return oge(baslik=baslik, **ek)


class GovdeKaydedenAg(KlipAg):
    """YouTube yükleme gövdesini (privacyStatus) kaydeder."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.govdeler = []

    def ham(self, method, url, *, govde=None, basliklar=None, zaman=300):
        if "uploadType=resumable" in url:
            self.govdeler.append(json.loads(govde))
        return super().ham(method, url, govde=govde, basliklar=basliklar, zaman=zaman)

    def gizlilikler(self):
        return [g["status"]["privacyStatus"] for g in self.govdeler]


class GizliPaylasim(SosyalTemel):
    """sosyal_yayinla.calistir: onay.otomatik klipler yalnız gizli gider; elle onaylı eski akış aynen."""

    def setUp(self):
        super().setUp()
        self.klip = self.kok / "data" / "klipler.json"
        self.klip.parent.mkdir(exist_ok=True)

    def klip_yaz(self, ogeler):
        m = ks.bos_manifest()
        m["taban"] = "https://medya.test/v/"
        m["ogeler"] = ogeler
        ks.kaydet(m, self.klip)

    def ayarlar(self, otomatik=True, **klip):
        a = ayar(instagram_reel=False, youtube=True)
        a["turler"] = {"haber": True, "klip": True, "derleme": True}
        a["youtube"] = {"gizlilik": "public"}  # ortak ayar HERKESE AÇIK: otomatik gizli buna bakmaz
        a["klip"] = {"gunluk_en_fazla": {"instagram_reel": 2, "youtube": 2}, "derleme_gunluk_en_fazla": 1,
                     "instagram": False, "youtube": True, "youtube_kategori": "20", "otomatik_gizli": otomatik,
                     "gizli_gunluk_en_fazla": 4}
        a["klip"].update(klip)
        return a

    def kos(self, ag, ayar_, simdi=SIMDI, gizli=None, cikti=None):
        return sy.calistir(ayar_, [], kayit_yolu=self.kayit, manifest_yolu=self.manifest, tum={**SIRLAR, **KLIP_SIRLARI}, ag=ag,
                           dry_run=False, bugun=simdi.date(), simdi=simdi, cikti=cikti or (lambda *_: None), klip_yolu=self.klip,
                           gizli_yuklenen=gizli)

    def test_otomatik_onayli_klip_gizli_yuklenir_ortak_ayar_acik_olsa_da(self):
        self.klip_yaz({"k1": otomatik_oge()})
        ag, gizli = GovdeKaydedenAg(), []
        g, hata, _ = self.kos(ag, self.ayarlar(), gizli=gizli)
        self.assertEqual((g, hata), (1, []))
        self.assertEqual(ag.gizlilikler(), ["private"])
        rec = self.kayitlar()["k1|klip|youtube|short"]
        self.assertTrue(rec["gizli"])
        self.assertEqual([(x["id"], x["kimlik"]) for x in gizli], [("k1", "YT1")])

    def test_elle_onayli_klip_ortak_ayara_gore_gider(self):
        self.klip_yaz({"k1": elle_oge()})
        ag, gizli = GovdeKaydedenAg(), []
        self.kos(ag, self.ayarlar(), gizli=gizli)
        self.assertEqual(ag.gizlilikler(), ["public"])
        self.assertNotIn("gizli", self.kayitlar()["k1|klip|youtube|short"])
        self.assertEqual(gizli, [])  # herkese açık paylaşım için gizli bildirimi yok

    def test_sessiz_saatte_otomatik_gider_elle_onayli_gitmez(self):
        a = self.ayarlar(sessiz_saat_utc={"bas": 10, "son": 14})  # SIMDI = UTC 12
        self.klip_yaz({"k1": elle_oge()})
        ag = GovdeKaydedenAg()
        self.kos(ag, a)
        self.assertEqual((ag.govdeler, self.kayitlar()), ([], {}))
        self.klip_yaz({"k2": otomatik_oge()})
        self.kos(ag, a)
        self.assertEqual(ag.gizlilikler(), ["private"])
        self.assertEqual(list(self.kayitlar()), ["k2|klip|youtube|short"])

    def test_en_az_ara_saat_gizliyi_engellemez(self):
        a = self.ayarlar(en_az_ara_saat=5)
        self.klip_yaz({"k1": elle_oge()})
        ag = GovdeKaydedenAg()
        self.kos(ag, a, simdi=SIMDI.replace(hour=12))
        self.klip_yaz({"k1": elle_oge(), "k2": otomatik_oge()})
        self.kos(ag, a, simdi=SIMDI.replace(hour=13))  # elle olan için 5 saat dolmadı; gizli için bu kural yok
        self.assertEqual(ag.gizlilikler(), ["public", "private"])

    def test_gizli_ve_acik_ayni_turda_ayri_hak(self):
        self.klip_yaz({"k1": elle_oge(), "k2": otomatik_oge()})
        ag = GovdeKaydedenAg()
        g, hata, _ = self.kos(ag, self.ayarlar())
        self.assertEqual((g, hata), (2, []))
        self.assertEqual(sorted(ag.gizlilikler()), ["private", "public"])

    def test_gizli_gunluk_sinir(self):
        a = self.ayarlar(gizli_gunluk_en_fazla=2)
        self.klip_yaz({f"k{i}": otomatik_oge(baslik=f"Eray klip {i} | Eray") for i in range(1, 6)})
        ag = GovdeKaydedenAg()
        self.kos(ag, a, simdi=SIMDI.replace(hour=12))
        self.kos(ag, a, simdi=SIMDI.replace(hour=13))
        self.kos(ag, a, simdi=SIMDI.replace(hour=14))  # sınır dolu: yenisi yok
        self.assertEqual(ag.gizlilikler(), ["private", "private"])
        self.kos(ag, a, simdi=SIMDI.replace(day=16, hour=12))  # ertesi gün hak yenilenir (yine en çok 2)
        self.kos(ag, a, simdi=SIMDI.replace(day=16, hour=13))
        self.assertEqual(len(ag.govdeler), 4)

    def test_gizli_calisma_basina_sinir(self):
        a = self.ayarlar(gizli_gunluk_en_fazla=4, gizli_calisma_basina_en_fazla=1)
        self.klip_yaz({f"k{i}": otomatik_oge(baslik=f"Eray klip {i} | Eray") for i in range(1, 4)})
        ag = GovdeKaydedenAg()
        self.kos(ag, a)
        self.assertEqual(len(ag.govdeler), 1)

    def test_ana_anahtar_kapaliysa_otomatik_klip_gitmez_elle_olan_eskisi_gibi(self):
        self.klip_yaz({"k1": otomatik_oge(), "k2": elle_oge()})
        ag = GovdeKaydedenAg()
        g, hata, _ = self.kos(ag, self.ayarlar(otomatik=False))
        self.assertEqual((g, hata), (1, []))
        self.assertEqual(ag.gizlilikler(), ["public"])
        self.assertEqual(list(self.kayitlar()), ["k2|klip|youtube|short"])
        # ayar hiç yazılmamışsa da kapalı
        self.assertFalse(sy.klip_ayari({})["otomatik_gizli"])

    def test_kota_hatasi_kalici_hata_degil_ve_tur_kirmiziya_dusmez(self):
        self.klip_yaz({"k1": otomatik_oge()})
        h = sy.PaylasimHatasi("quotaExceeded", kesin=True, kota=True)
        ag, gizli, satirlar = GovdeKaydedenAg(), [], []
        ag.hata = {"uploadType=resumable": h}
        g, hata, _ = self.kos(ag, self.ayarlar(), gizli=gizli, cikti=satirlar.append)
        self.assertEqual((g, hata, gizli), (0, [], []))
        self.assertEqual(self.kayitlar(), {})  # kayıt silindi: sonraki turda yeniden denenir (kalıcı hata yazılmadı)
        self.assertTrue(any("kota" in s.lower() and s.startswith("UYARI") for s in satirlar))
        # sonraki tur: kota açıldı, yükleme başarılı
        ag2 = GovdeKaydedenAg()
        g, hata, _ = self.kos(ag2, self.ayarlar(), gizli=gizli)
        self.assertEqual((g, hata), (1, []))

    def test_kota_olmayan_kesin_hata_yine_hata_sayilir(self):
        self.klip_yaz({"k1": otomatik_oge()})
        ag = GovdeKaydedenAg()
        ag.hata = {"uploadType=resumable": sy.PaylasimHatasi("boyut reddedildi", kesin=True)}
        g, hata, _ = self.kos(ag, self.ayarlar())
        self.assertEqual(g, 0)
        self.assertEqual(len(hata), 1)

    def test_kota_hatasi_elle_onayli_icin_hata_olarak_kalir(self):
        """Eski davranış değişmez: kota istisnası yalnız otomatik gizli yüklemeye uygulanır."""
        self.klip_yaz({"k1": elle_oge()})
        ag = GovdeKaydedenAg()
        ag.hata = {"uploadType=resumable": sy.PaylasimHatasi("quotaExceeded", kesin=True, kota=True)}
        _, hata, _ = self.kos(ag, self.ayarlar())
        self.assertEqual(len(hata), 1)

    def test_deneme_calismasi_gizli_isaretler_ve_ag_yok(self):
        self.klip_yaz({"k1": otomatik_oge()})
        cikti = []
        g, hata, _ = sy.calistir(self.ayarlar(), [], kayit_yolu=self.kayit, manifest_yolu=self.manifest,
                                 tum={**SIRLAR, **KLIP_SIRLARI}, ag=None, dry_run=True, bugun=BUGUN, simdi=SIMDI,
                                 cikti=cikti.append, klip_yolu=self.klip)
        self.assertEqual(hata, [])
        yazi = "\n".join(cikti)
        self.assertIn("[otomatik gizli]", yazi)
        self.assertIn("gizlilik: private", yazi)


class BildirimMetniVeGonderimi(unittest.TestCase):
    GIZLI = [{"id": "a", "baslik": "Birinci klip", "kimlik": "AAAAAAAAAAA"}, {"id": "b", "baslik": "İkinci klip", "kimlik": "BBBBBBBBBBB"}]

    def test_metin(self):
        t = ks.bildirim_metni(self.GIZLI)
        satirlar = t.splitlines()
        self.assertEqual(satirlar[0], "Komixsi: 2 Shorts gizli olarak yüklendi, onayını bekliyor.")
        self.assertIn("• Birinci klip", satirlar)
        self.assertIn("https://studio.youtube.com/video/AAAAAAAAAAA/edit", satirlar)
        self.assertIn("https://studio.youtube.com/video/BBBBBBBBBBB/edit", satirlar)

    def test_metin_markdown_ozel_karakterleri_kacirilir(self):
        """Kimlikte/başlıkta alt çizgi varken Telegram (eski Markdown) mesajı reddetmesin."""
        t = ks.bildirim_metni([{"id": "a", "baslik": "Eray_AWP *şov* [canlı]", "kimlik": "Alot59_uoT8"}])
        self.assertIn("https://studio.youtube.com/video/Alot59\\_uoT8/edit", t)
        self.assertIn("• Eray\\_AWP \\*şov\\* \\[canlı]", t)
        self.assertNotRegex(t, r"(?<!\\)[_*`\[]")

    def test_sir_varsa_tek_mesaj_gider_adres_loga_yazilmaz(self):
        yollar, cikti = [], []
        adres = "http://10.9.8.7/webhook/gizli-yol"
        ok = sy.klip_bildirimi_gonder(self.GIZLI, ortam={sy.BILDIRIM_SIRRI: adres}, cikti=cikti.append,
                                      gonder=lambda a, g: (yollar.append((a, g)), 200)[1])
        self.assertTrue(ok)
        self.assertEqual(len(yollar), 1)
        self.assertEqual(yollar[0][0], adres)
        self.assertEqual(yollar[0][1]["metin"], ks.bildirim_metni(self.GIZLI))
        self.assertIn("KLIP_BILDIRIM: gönderildi (2 gizli Shorts)", cikti)
        self.assertNotIn("10.9.8.7", "\n".join(cikti))

    def test_sir_yoksa_sessizce_atlanir_uyari_loglanir(self):
        cikti = []
        cagri = mock.Mock()
        self.assertFalse(sy.klip_bildirimi_gonder(self.GIZLI, ortam={}, cikti=cikti.append, gonder=cagri))
        cagri.assert_not_called()
        self.assertTrue(any(s.startswith("UYARI") and "atlandı" in s for s in cikti))

    def test_yukleme_yoksa_mesaj_yok(self):
        cagri = mock.Mock()
        self.assertFalse(sy.klip_bildirimi_gonder([], ortam={sy.BILDIRIM_SIRRI: "http://x/y"}, gonder=cagri))
        cagri.assert_not_called()

    def test_gonderim_hatasi_turu_dusurmez_ve_adres_sizmaz(self):
        cikti = []

        def patla(a, g):
            raise OSError(f"bağlanamadı {a}")
        self.assertFalse(sy.klip_bildirimi_gonder(self.GIZLI, ortam={sy.BILDIRIM_SIRRI: "http://10.9.8.7/x"}, cikti=cikti.append, gonder=patla))
        self.assertNotIn("10.9.8.7", "\n".join(cikti))
        self.assertTrue(any(s.startswith("UYARI") for s in cikti))
        cikti.clear()
        self.assertFalse(sy.klip_bildirimi_gonder(self.GIZLI, ortam={sy.BILDIRIM_SIRRI: "http://10.9.8.7/x"}, cikti=cikti.append,
                                                  gonder=lambda a, g: 500))
        self.assertTrue(any("HTTP 500" in s for s in cikti))

    def test_gecersiz_adres_gonderilmez(self):
        cagri = mock.Mock()
        self.assertFalse(sy.klip_bildirimi_gonder(self.GIZLI, ortam={sy.BILDIRIM_SIRRI: "ftp://x"}, cikti=lambda *_: None, gonder=cagri))
        cagri.assert_not_called()


class OtomatikOnay(KlipYayinTemel):
    """klip_yayin: otomatik onay, seçim kuralları, Cio kararının korunması."""

    def hazirla(self, n=1, **ek):
        ek.setdefault("sohbet_puani", 80)
        ek.setdefault("konusma_puani", 8)
        for i in range(1, n + 1):
            alanlar = {"baslik": f"Konu {i} başlığı uzun cümle", **ek}
            self.paket_yaz(klasor=f"eraycan-2026111{i}-aaa{i}", ad="klip-01", vod=f"https://kick.com/eray/videos/v{i}",
                           yayin_tarihi=f"2026-11-1{i}", **alanlar)

    def sec(self, kayit=None, sosyal=None, en_cok=None, manifest=None):
        ayar_ = ky.ayar_oku()
        ogeler = ky.tara(self.dizin, ayar_)
        manifest = manifest if manifest is not None else ks.yukle(self.manifest)
        sosyal = sosyal if sosyal is not None else {"klip": {"otomatik_gizli": True, "gizli_gunluk_en_fazla": 4}}
        return ky.otomatik_sec(ogeler, manifest, sosyal, kayit or {}, "2026-11-22", ayar_, en_cok), manifest

    def test_onay_otomatik_isaretlenir_ve_gecerlidir(self):
        self.hazirla()
        (secilen, notlar), m = self.sec()
        self.assertEqual((len(secilen), notlar), (1, []))
        e = next(iter(m["ogeler"].values()))
        self.assertIs(e["onay"]["otomatik"], True)
        self.assertIs(e["otomatik"], True)
        self.assertTrue(ks.onay_gecerli(e))
        self.assertEqual(ky.otomatik_bekleyenler(m), [e_id for e_id in m["ogeler"]])

    def test_en_yeni_yayin_once_ve_en_cok_sinirlar(self):
        self.hazirla(3)
        (secilen, _), _m = self.sec(en_cok=2)
        self.assertEqual([o["yayin_tarihi"] for o in secilen], ["2026-11-13", "2026-11-12"])

    def test_tazelik_sinirindan_eski_klip_otomatik_onaylanmaz(self):
        self.hazirla(3)
        ayar_ = ky.ayar_oku()
        ogeler = ky.tara(self.dizin, ayar_)
        eski = next(o for o in ogeler if o["yayin_tarihi"] == "2026-11-13")
        simdi = eski["mp4"].stat().st_mtime
        os.utime(eski["mp4"], (simdi - 48 * 3600, simdi - 48 * 3600))
        m = ks.yukle(self.manifest)
        sosyal = {"klip": {"otomatik_gizli": True, "gizli_gunluk_en_fazla": 4}}
        secilen, notlar = ky.otomatik_sec(ogeler, m, sosyal, {}, "2026-11-22", ayar_, None, simdi - 24 * 3600)
        self.assertEqual(sorted(o["yayin_tarihi"] for o in secilen), ["2026-11-11", "2026-11-12"])
        self.assertNotIn(eski["id"], m["ogeler"])
        self.assertTrue(any("1 eski klip" in n for n in notlar))
        self.assertEqual(sy.klip_ayari({})["otomatik_taze_saat"], 24)
        self.assertEqual(sy.klip_ayari({"klip": {"otomatik_taze_saat": 0}})["otomatik_taze_saat"], 0)

    def test_once_icerik_sonra_sohbet_puanina_gore_secim(self):
        # None ve 7 yüksek sohbete rağmen elenir; 8 için 60 yeter, 9 için sohbet gerekmez.
        puanlar = [(None, 100), (7, 100), (8, 59), (8, 60), (9, 0), (8, 95), (9, 80)]
        for i, (icerik, sohbet) in enumerate(puanlar, 1):
            self.paket_yaz(klasor=f"eraycan-2026111{i}-aaa{i}", ad="klip-01", vod=f"https://kick.com/eray/videos/v{i}",
                           yayin_tarihi=f"2026-11-1{i}", baslik=f"Konu {i} başlığı uzun cümle",
                           sohbet_puani=sohbet, konusma_puani=icerik)
        sosyal = {"klip": {"otomatik_gizli": True, "gizli_gunluk_en_fazla": 8, "otomatik_yayinci_basina": 0}}
        (secilen, notlar), _m = self.sec(sosyal=sosyal)
        self.assertEqual([o["yayin_tarihi"] for o in secilen], ["2026-11-17", "2026-11-15", "2026-11-16", "2026-11-14"])
        self.assertIn("içerik puanı düşük/yok: 2 klip", notlar)
        self.assertTrue(any("1 klip izleyici tepkisi zayıf" in n for n in notlar))
        sosyal["klip"]["otomatik_yayinci_basina"] = 2  # aynı yayıncıdan günde en çok 2
        (secilen, _), _m = self.sec(sosyal=sosyal)
        self.assertEqual([o["yayin_tarihi"] for o in secilen], ["2026-11-17", "2026-11-15"])
        sosyal["klip"].update(otomatik_min_sohbet_puani=0, otomatik_yayinci_basina=0)
        (secilen, _), _m = self.sec(sosyal=sosyal)
        self.assertEqual(len(secilen), 5)
        self.assertEqual((sy.klip_ayari({})["otomatik_min_sohbet_puani"], sy.klip_ayari({})["otomatik_yayinci_basina"]), (60, 2))

    def test_olculmemis_sohbet_ile_olculmus_dusuk_sohbet_ayrimi(self):
        # 1: tarama-only (sohbet ölçülmemiş, sohbet_puani=0, zirve_mesaj_sayisi=None) + kon 8 -> kabul
        self.paket_yaz(klasor="eraycan-20261111-aaa1", ad="klip-01", vod="https://kick.com/eray/videos/v1",
                       yayin_tarihi="2026-11-11", baslik="Tarama adayı güçlü espri yaptı",
                       aday_kaynaklari=["tarama"], sohbet_puani=0, zirve_mesaj_sayisi=None, konusma_puani=8)
        # 2: ölçülmüş düşük sohbet (40) + kon 8 -> ret
        self.paket_yaz(klasor="eraycan-20261112-aaa2", ad="klip-01", vod="https://kick.com/eray/videos/v2",
                       yayin_tarihi="2026-11-12", baslik="Ölçülmüş düşük sohbetli an",
                       aday_kaynaklari=["sohbet"], sohbet_puani=40, zirve_mesaj_sayisi=35, konusma_puani=8)
        # 3: ölçülmüş düşük sohbet (40) + kon 9 -> kabul
        self.paket_yaz(klasor="eraycan-20261113-aaa3", ad="klip-01", vod="https://kick.com/eray/videos/v3",
                       yayin_tarihi="2026-11-13", baslik="Çok güçlü dokuz puanlık espri",
                       aday_kaynaklari=["sohbet"], sohbet_puani=40, zirve_mesaj_sayisi=35, konusma_puani=9)
        # 4: kon None (sohbet ölçülmemiş) -> ret
        self.paket_yaz(klasor="eraycan-20261114-aaa4", ad="klip-01", vod="https://kick.com/eray/videos/v4",
                       yayin_tarihi="2026-11-14", baslik="İçerik puanı olmayan klip",
                       aday_kaynaklari=["tarama"], sohbet_puani=0, zirve_mesaj_sayisi=None, konusma_puani=None)
        # 5: ölçülmüş yüksek sohbet (75) + kon 8 -> tarama-only kon 8'den önce sıralanır
        self.paket_yaz(klasor="eraycan-20261115-aaa5", ad="klip-01", vod="https://kick.com/eray/videos/v5",
                       yayin_tarihi="2026-11-15", baslik="Yüksek sohbetli sekiz puanlık an",
                       aday_kaynaklari=["sohbet", "tarama"], sohbet_puani=75, zirve_mesaj_sayisi=None, konusma_puani=8)
        # 6: YouTube (sohbet yok) + kon 8 -> kabul
        self.paket_yaz(klasor="eraycan-20261116-aaa6", ad="klip-01", vod="https://www.youtube.com/watch?v=abcdefghijk",
                       platform="youtube", yayin_tarihi="2026-11-16", baslik="YouTube videosundan sekiz puanlık an",
                       aday_kaynaklari=["altyazi_tarama"], sohbet_puani=50, zirve_mesaj_sayisi=None, konusma_puani=8)
        sosyal = {"klip": {"otomatik_gizli": True, "gizli_gunluk_en_fazla": 8, "otomatik_yayinci_basina": 0}}
        (secilen, notlar), _m = self.sec(sosyal=sosyal)
        # Sıra: kon 9 (11-13) > kon 8 sohbet 75 (11-15) > kon 8 ölçülmemiş (11-16, 11-11 yeni önce)
        self.assertEqual([o["yayin_tarihi"] for o in secilen], ["2026-11-13", "2026-11-15", "2026-11-16", "2026-11-11"])
        self.assertIn("içerik puanı düşük/yok: 1 klip", notlar)
        self.assertTrue(any("1 klip izleyici tepkisi zayıf" in n for n in notlar))

    def test_icerik_esigi_ayarlanabilir_ve_gecersiz_deger_varsayilana_doner(self):
        anahtar = "otomatik_min_konusma_puani"
        self.assertEqual(sy.klip_ayari({})[anahtar], 8)
        for deger in (-1, 11, True, "10", None):
            with self.subTest(deger=deger):
                self.assertEqual(sy.klip_ayari({"klip": {anahtar: deger}})[anahtar], 8)
        self.hazirla(konusma_puani=9, sohbet_puani=100)
        (secilen, notlar), _m = self.sec(sosyal={"klip": {anahtar: 10}})
        self.assertEqual(secilen, [])
        self.assertIn("içerik puanı düşük/yok: 1 klip", notlar)

    def test_jenerik_paket_veya_paylasim_basligi_yuksek_puanla_da_elenir(self):
        for baslik, kisa in (
            ("Eraycan yayınında sohbet bir anda gülmeye başladı | GTA", "Eray siparişi çorapla ödedi"),
            ("Eray siparişi çorapla ödedi", "Eraycan yayınında chat kahkahaya boğuldu"),
            ("Eray siparişi çorapla ödedi", "Eraycan yayınından kesit"),
            (None, None),
        ):
            with self.subTest(baslik=baslik, kisa=kisa):
                self.hazirla(baslik=baslik, kisa_aciklama=kisa, konusma_puani=10)
                (secilen, notlar), m = self.sec()
                self.assertEqual((secilen, m["ogeler"]), ([], {}))
                self.assertIn("jenerik başlık: 1 klip", notlar)

    def test_gunluk_gizli_sinir_bugunku_yukleme_ve_bekleyenleri_sayar(self):
        self.hazirla(4)
        bugun = {"x|klip|youtube|short": {"id": "x", "sosyal_tur": "klip", "hesap": "klip", "platform": "youtube", "bicim": "short",
                                          "durum": "tamam", "zaman": "2026-11-22T08:00:00+00:00", "gizli": True}}
        sosyal = {"klip": {"otomatik_gizli": True, "gizli_gunluk_en_fazla": 3}}
        (secilen, _), m = self.sec(kayit=bugun, sosyal=sosyal)
        self.assertEqual(len(secilen), 2)  # 3 - 1 yüklenen
        (secilen2, _), _ = self.sec(kayit=bugun, sosyal=sosyal, manifest=m)  # 2 onaylı-bekleyen hakkı doldurdu
        self.assertEqual(secilen2, [])

    def test_dunku_gizli_yukleme_bugunku_hakki_yemez(self):
        self.hazirla(1)
        dun = {"x|klip|youtube|short": {"id": "x", "sosyal_tur": "klip", "hesap": "klip", "platform": "youtube", "bicim": "short",
                                        "durum": "tamam", "zaman": "2026-11-21T08:00:00+00:00", "gizli": True}}
        (secilen, _), _m = self.sec(kayit=dun, sosyal={"klip": {"otomatik_gizli": True, "gizli_gunluk_en_fazla": 1}})
        self.assertEqual(len(secilen), 1)

    def test_kufurlu_klip_otomatik_onaylanmaz(self):
        self.hazirla(1, dokum_metni="amk ne diyor bu")
        (secilen, notlar), m = self.sec()
        self.assertEqual(secilen, [])
        self.assertTrue(any("küfür" in n for n in notlar))
        self.assertEqual(m["ogeler"], {})

    def test_kufurlu_klip_izin_varsa_otomatik_onaylanir(self):
        self.hazirla(1, dokum_metni="amk ne diyor bu")
        (secilen, _n), _m = self.sec(sosyal={"klip": {"otomatik_gizli": True, "otomatik_kufurlu_izin": True}})
        self.assertEqual(len(secilen), 1)

    def test_kufurlu_izin_varsayilan_kapali(self):
        self.assertFalse(sy.klip_ayari({})["otomatik_kufurlu_izin"])
        self.assertFalse(sy.klip_ayari({"klip": {"otomatik_kufurlu_izin": "evet"}})["otomatik_kufurlu_izin"])

    def test_kufurlu_paylasim_metni_otomatik_onaylanmaz(self):
        self.hazirla(1, kisa_aciklama="Eray amk dedi")
        (secilen, notlar), _m = self.sec()
        self.assertEqual(secilen, [])
        self.assertTrue(notlar)

    def test_ayni_anin_onayli_baska_surumu_varsa_otomatik_onaylanmaz(self):
        # aynı VOD, çakışan saniyeler: biri elle onaylı, öbürü otomatik adayı
        a = self.paket_yaz(klasor="eraycan-20261112-aaa", ad="klip-01", bas=100.0, bit=140.0)
        self.paket_yaz(klasor="eraycan-20261112-bbb", ad="klip-01", bas=110.0, bit=150.0)
        ayar_ = ky.ayar_oku()
        ogeler = ky.tara(self.dizin, ayar_)
        m = ks.bos_manifest()
        # tekilleştirme yedeği sürümü gizler; kapıyı doğrudan sına
        birinci = next(o for o in ogeler if o["json"] == a)
        ikinci = next(o for o in ogeler if o["json"] != a)
        ky.onayla_bir(birinci, ogeler, m, None, ayar_)
        with self.assertRaises(ky.Hata) as h:
            ky.onayla_bir(ikinci, ogeler, m, None, ayar_, otomatik=True)
        self.assertIn("başka sürümü", str(h.exception))

    def test_cionun_kararlari_korunur(self):
        self.hazirla(3)
        ogeler = ky.tara(self.dizin, ky.ayar_oku())
        m = ks.bos_manifest()
        kimlikler = [o["id"] for o in ogeler]
        # 0: Cio elle onayladı, sonra geri çekti; 1: elle onaylı; 2: hiç dokunulmamış
        ky.onayla_bir(ogeler[0], ogeler, m, None, ky.ayar_oku())
        ky.geri_cek_oge(kimlikler[0], m)
        self.assertIs(m["ogeler"][kimlikler[0]]["otomatik_red"], True)
        ky.onayla_bir(ogeler[1], ogeler, m, None, ky.ayar_oku())
        (secilen, _), m = self.sec(manifest=m)
        self.assertEqual([o["id"] for o in secilen], [kimlikler[2]])

    def test_otomatik_kaydi_geri_cekilirse_bir_daha_onaylanmaz(self):
        self.hazirla(1)
        (secilen, _), m = self.sec()
        kimlik = secilen[0]["id"]
        ky.geri_cek_oge(kimlik, m)
        (secilen2, _), _ = self.sec(manifest=m)
        self.assertEqual(secilen2, [])

    def test_elle_onay_otomatik_onayi_acik_akisa_cevirir(self):
        self.hazirla(1)
        (secilen, _), m = self.sec()
        ogeler = ky.tara(self.dizin, ky.ayar_oku())
        mesaj = ky.onayla_bir(secilen[0] | {}, ogeler, m, None, ky.ayar_oku())
        self.assertNotIn("zaten", mesaj)
        e = m["ogeler"][secilen[0]["id"]]
        self.assertNotIn("otomatik", e["onay"])
        self.assertNotIn("otomatik", e)

    def test_ayni_otomatik_onay_ikinci_kez_zaten_onayli(self):
        self.hazirla(1)
        (secilen, _), m = self.sec()
        ogeler = ky.tara(self.dizin, ky.ayar_oku())
        self.assertIn("zaten onaylı", ky.onayla_bir(ogeler[0], ogeler, m, None, ky.ayar_oku(), otomatik=True))

    def test_derleme_otomatik_aday_olmaz(self):
        self.derleme_yaz()
        (secilen, _), m = self.sec()
        self.assertEqual((secilen, m["ogeler"]), ([], {}))

    def test_youtube_kapali_klip_secilmez(self):
        j = self.paket_yaz(sohbet_puani=80, konusma_puani=8)
        ogeler = ky.tara(self.dizin, ky.ayar_oku())
        ogeler[0]["platformlar"] = {"youtube": False, "instagram": False}
        m = ks.bos_manifest()
        secilen, _ = ky.otomatik_sec(ogeler, m, {"klip": {"otomatik_gizli": True}}, {}, "2026-11-22", ky.ayar_oku())
        self.assertEqual((secilen, j.exists()), ([], True))


class OtomatikGizliKomutu(KlipYayinTemel):
    """komut_otomatik_gizli: ana anahtar, kuru çalışma, kilit, sıra ve tek bildirim. git/gh/ssh/yükleme sahte."""

    def setUp(self):
        super().setUp()
        for i in (1, 2):
            self.paket_yaz(klasor=f"eraycan-2026111{i}-aaa{i}", ad="klip-01", vod=f"https://kick.com/eray/videos/v{i}",
                           yayin_tarihi=f"2026-11-1{i}", baslik=f"Konu {i} başlığı uzun cümle",
                           sohbet_puani=80, konusma_puani=8)
        self.sosyal = {"klip": {"otomatik_gizli": True, "gizli_gunluk_en_fazla": 4}}
        self.olaylar = []
        self.kayit = {}
        self.yamalar = {}

        def yukle_sahte(args):
            self.olaylar.append(("yukle", tuple(args.idler)))
            m = ks.yukle(self.manifest)
            for i in args.idler:
                m["ogeler"][i]["yayinda"] = {"zaman": "2026-11-22T11:00:00Z", "yuklenen_ozet": m["ogeler"][i]["onay"]["ozet"],
                                             "sure": 40.0, **ks.dosya_adlari(i, "klip")}
            ks.kaydet(m, self.manifest)
            return 0

        self.telegram = mock.Mock(return_value=True)
        for ad, yeni in {
            "sosyal_ayar_oku": lambda: self.sosyal,
            "gonderilenler_oku": lambda: self.kayit,
            "komut_yukle": yukle_sahte,
            "manifesti_gonder": lambda yol, mesaj: (self.olaylar.append(("push", mesaj)), True)[1],
            "paylasim_turu_baslat": lambda: (self.olaylar.append(("tur",)), 77)[1],
            "paylasim_turu_bekle": lambda tid, dk: (self.olaylar.append(("bekle", tid, dk)), "success")[1],
            "paylasim_turu_satirlari": lambda tid: [],
            "telegram_gonder": self.telegram,
        }.items():
            m = mock.patch.object(ky, ad, yeni)
            m.start()
            self.addCleanup(m.stop)

    def gizli_kayit_yaz(self, kimlikler):
        """Actions turunun yazdığı gizli paylaşım kayıtlarını taklit eder."""
        simdi = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
        for i, kimlik in zip(kimlikler, ("AAAAAAAAAAA", "BBBBBBBBBBB", "CCCCCCCCCCC")):
            self.kayit[f"{i}|klip|youtube|short"] = {"id": i, "sosyal_tur": "klip", "hesap": "klip", "platform": "youtube",
                                                     "bicim": "short", "durum": "tamam", "zaman": simdi, "gizli": True,
                                                     "kimlik": kimlik}

    def calis(self, *arg):
        return self.cli("otomatik-gizli", *arg)

    def test_ana_anahtar_kapaliysa_hicbir_sey_yapmaz(self):
        self.sosyal = {"klip": {"otomatik_gizli": False}}
        kod, cikti = self.calis()
        self.assertEqual(kod, 0)
        self.assertIn("kapalı", cikti)
        self.assertEqual((self.olaylar, self.man()["ogeler"]), ([], {}))
        self.telegram.assert_not_called()

    def test_kuru_calisma_hicbir_sey_yazmaz_gondermez(self):
        kod, cikti = self.calis("--kuru")
        self.assertEqual(kod, 0)
        self.assertEqual(cikti.count("[kuru] otomatik onay:"), 2)
        self.assertEqual((self.olaylar, self.man()["ogeler"]), ([], {}))
        self.assertFalse(self.manifest.exists())
        self.telegram.assert_not_called()

    def test_tam_calisma_sirasi_ve_tek_mesaj(self):
        # Actions turu çalışınca gizli kayıtlar yazılır: tur beklenirken taklit et
        def bekle(tid, dk):
            self.olaylar.append(("bekle", tid, dk))
            self.gizli_kayit_yaz(sorted(self.man()["ogeler"]))
            return "success"
        with mock.patch.object(ky, "paylasim_turu_bekle", bekle):
            kod, cikti = self.calis()
        self.assertEqual(kod, 0, cikti)
        adlar = [o[0] for o in self.olaylar]
        self.assertEqual(adlar, ["yukle", "push", "tur", "bekle"])
        m = self.man()
        for e in m["ogeler"].values():
            self.assertIs(e["onay"]["otomatik"], True)
        self.assertEqual(self.telegram.call_count, 1)
        metin = self.telegram.call_args[0][0]
        self.assertTrue(metin.startswith("Komixsi: 2 Shorts gizli olarak yüklendi, onayını bekliyor."))
        self.assertIn("https://studio.youtube.com/video/AAAAAAAAAAA/edit", metin)
        self.assertIn("TELEGRAM: gönderildi (2 gizli Shorts)", cikti)
        # aynı kayıtlar için ikinci çalışma tekrar mesaj atmaz
        self.olaylar.clear()
        kod, cikti = self.calis()
        self.assertEqual(self.telegram.call_count, 1)
        self.assertIn("bildirilecek yeni gizli Shorts yok", cikti)

    def test_en_cok_yeni_onayi_sinirlar(self):
        self.calis("--en-cok", "1", "--calisma-bekle", "0")
        self.assertEqual(len(self.man()["ogeler"]), 1)
        self.assertNotIn(("bekle",), [o[:1] for o in self.olaylar])  # --calisma-bekle 0: turu beklemez

    def test_yukleme_yoksa_mesaj_yok(self):
        self.sosyal = {"klip": {"otomatik_gizli": True, "gizli_gunluk_en_fazla": 0}}
        kod, cikti = self.calis()
        self.assertEqual(kod, 0)
        self.assertEqual(self.man()["ogeler"], {})
        self.assertIn("mesaj gitmedi", cikti)
        self.telegram.assert_not_called()

    def test_kilit_doluysa_atlar(self):
        with kk.Kilit(self.dizin, "panel: deneme"):
            kod, cikti = self.calis()
        self.assertEqual(kod, 0)
        self.assertIn("ATLANDI", cikti)
        self.assertEqual((self.olaylar, self.man()["ogeler"]), ([], {}))

    def test_kilit_islem_sonunda_birakilir(self):
        self.calis("--calisma-bekle", "0")
        self.assertFalse((self.dizin / kk.KILIT_ADI).exists())

    def test_telegram_hatasi_komutu_dusurmez_ve_sonra_yeniden_denenir(self):
        self.telegram.return_value = False
        self.gizli_kayit_yaz(["x1"])
        self.man_yaz_x1()
        kod, cikti = self.calis("--calisma-bekle", "0")
        self.assertEqual(kod, 0)
        self.assertIn("UYARI: Telegram bildirimi gönderilemedi", cikti)
        self.telegram.return_value = True
        self.calis("--calisma-bekle", "0")
        self.assertEqual(self.telegram.call_count, 2)  # ilk başarısızdı, ikincisi gitti
        self.calis("--calisma-bekle", "0")
        self.assertEqual(self.telegram.call_count, 2)  # üçüncüde bildirilecek kalmadı

    def man_yaz_x1(self):
        m = ks.yukle(self.manifest)
        m["ogeler"]["x1"] = oge()
        ks.kaydet(m, self.manifest)

    def test_actions_zaten_bildirdiyse_ssh_ile_tekrar_gonderilmez(self):
        def bekle(tid, dk):
            self.gizli_kayit_yaz(sorted(self.man()["ogeler"]))
            return "success"
        with mock.patch.object(ky, "paylasim_turu_bekle", bekle), \
                mock.patch.object(ky, "paylasim_turu_satirlari", lambda tid: ["KLIP_BILDIRIM: gönderildi (2 gizli Shorts)"]):
            kod, cikti = self.calis()
        self.assertEqual(kod, 0)
        self.telegram.assert_not_called()
        self.assertIn("GitHub turu zaten gönderdi", cikti)

    def test_push_hatasi_exit_kodu_1_ama_commit_yerelde_kalir(self):
        def patla(yol, mesaj):
            raise ky.Hata("git push başarısız")
        with mock.patch.object(ky, "manifesti_gonder", patla):
            kod, cikti = self.calis()
        self.assertEqual(kod, 1)
        self.assertIn("HATA: git push başarısız", cikti)
        self.assertNotIn("tur", [o[0] for o in self.olaylar])  # push olmadan tur başlatılmaz

    def test_bildirim_metni_yalniz_gizli_kayitlardan(self):
        """Elle (herkese açık) paylaşılmış kayıt ya da başka hesap bildirime girmez."""
        kayit = {"a|klip|youtube|short": {"id": "a", "sosyal_tur": "klip", "platform": "youtube", "durum": "tamam", "kimlik": "AAA",
                                          "zaman": datetime.datetime.now(datetime.timezone.utc).isoformat()},
                 "b|klip|youtube|short": {"id": "b", "sosyal_tur": "klip", "platform": "youtube", "durum": "niyet", "gizli": True,
                                          "kimlik": "BBB", "zaman": datetime.datetime.now(datetime.timezone.utc).isoformat()}}
        self.assertEqual(ky.gizli_bildirimleri(kayit, ks.bos_manifest(), set(), datetime.datetime.now(datetime.timezone.utc).date()), [])


class TelegramSsh(unittest.TestCase):
    def test_adres_komut_satirina_ve_ciktiya_gecmez_yalniz_sunucuda_okunur(self):
        gorulen = {}

        def kos(arg, **k):
            gorulen["arg"] = arg
            gorulen["girdi"] = k.get("input")
            return mock.Mock(returncode=0, stdout=b"200", stderr=b"curl: (7) Failed to connect to 10.9.8.7")
        with mock.patch.object(ky.shutil, "which", return_value="ssh"), mock.patch.object(ky.subprocess, "run", kos):
            self.assertTrue(ky.telegram_gonder("Komixsi: 1 Shorts"))
        self.assertEqual(json.loads(gorulen["girdi"].decode("utf-8")), {"metin": "Komixsi: 1 Shorts"})
        komut = gorulen["arg"][-1]
        self.assertIn("sudo -n cat " + ky.BILDIRIM_ADRES_DOSYASI, komut)
        self.assertNotIn("http://", komut)
        self.assertNotIn("https://", komut)

    def test_ssh_yoksa_ya_da_hata_kodunda_false(self):
        with mock.patch.object(ky.shutil, "which", return_value=None):
            self.assertFalse(ky.telegram_gonder("x"))
        with mock.patch.object(ky.shutil, "which", return_value="ssh"), \
                mock.patch.object(ky.subprocess, "run", return_value=mock.Mock(returncode=0, stdout=b"500", stderr=b"")):
            self.assertFalse(ky.telegram_gonder("x"))
        with mock.patch.object(ky.shutil, "which", return_value="ssh"), \
                mock.patch.object(ky.subprocess, "run", side_effect=OSError("yok")):
            self.assertFalse(ky.telegram_gonder("x"))


if __name__ == "__main__":
    unittest.main()
