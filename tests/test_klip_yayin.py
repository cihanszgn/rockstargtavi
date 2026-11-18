"""Klip/derleme paylaşım hattı: onay kapısı, manifest, metin, paylaşım seçimi. Ağ ve gerçek dosya yok (geçici klasör)."""
import contextlib
import http.client
import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import klip_sosyal as ks  # noqa: E402
import klip_yayin as ky  # noqa: E402
import sosyal_yayinla as sy  # noqa: E402
import video_site as vs  # noqa: E402
from test_sosyal_yayinla import BUGUN, SIMDI, SIRLAR, SahteAg, YasakAg, ayar, haber  # noqa: E402
from test_sosyal_yayinla import Temel as SosyalTemel  # noqa: E402


def paket(ad="Kesit", vod="https://kick.com/eray/videos/aaa", bas=100.0, bit=140.0, **ek):
    p = {"yayinci": "Eraycan", "platform": "kick", "kanal": "eray", "kanal_url": "https://kick.com/eray", "vod_url": vod,
         "vod_zaman_damgali_url": vod, "vod_zaman_damgali_url_dogrulandi": False, "yayin_tarihi": "2026-11-12",
         "oyun": "Potato Please", "klip_baslangic_sn": bas, "klip_bitis_sn": bit, "baslik": f"{ad} başlığı uzun cümle",
         "kisa_aciklama": f"Eray {ad} yapıyor", "dokum_metni": "temiz bir konuşma", "konusma_puani": 7,
         "video": {"genislik": 1080, "yukseklik": 1920, "sure_sn": 40.0}}
    p.update(ek)
    return p


def oge(baslik="Eray patates soyuyor | Eray", yayinda=True, tur="klip", **ek):
    metin = {"baslik": baslik, "aciklama": "Kaynak: https://kick.com/eray", "etiketler": ["#Eray", "#Kick"]}
    o = {"tur": tur, "paket": "cikti/x/klip-01.json", "yayinci": "Eraycan", "oyun": "Potato Please",
         "kanal_url": "https://kick.com/eray", "sure": 40.0, "yayin_tarihi": "2026-11-12", "metin": metin,
         "onay": {"zaman": "2026-11-18T10:00:00Z", "ozet": "ozet1", "metin_ozeti": ks.metin_ozeti(metin)}}
    if yayinda:
        adlar = ks.dosya_adlari("kimlik", tur)
        o["yayinda"] = {"zaman": "2026-11-18T11:00:00Z", "yuklenen_ozet": "ozet1", "sure": 40.0, **adlar}
    o.update(ek)
    return o


class KlipYayinTemel(unittest.TestCase):
    """Geçici çalışma dizini (YAYIN_KLIP_DIZIN) ve geçici manifest."""

    def setUp(self):
        self.gecici = tempfile.TemporaryDirectory()
        self.kok = pathlib.Path(self.gecici.name)
        self.dizin = self.kok / "calisma"
        (self.dizin / "cikti").mkdir(parents=True)
        self.manifest = self.kok / "klipler.json"
        ort = mock.patch.dict(os.environ, {"YAYIN_KLIP_DIZIN": str(self.dizin)})
        ort.start()
        self.addCleanup(ort.stop)
        self.addCleanup(self.gecici.cleanup)

    def paket_yaz(self, klasor="eraycan-20261112-aaa", ad="klip-01", mp4=None, **ek):
        k = self.dizin / "cikti" / klasor
        k.mkdir(parents=True, exist_ok=True)
        (k / f"{ad}.json").write_text(json.dumps(paket(ad, **ek), ensure_ascii=False), encoding="utf-8")
        (k / f"{ad}.mp4").write_bytes(mp4 or f"mp4:{klasor}/{ad}".encode())
        return k / f"{ad}.json"

    def derleme_yaz(self, ad="yayin-kolaji-1", **ek):
        k = self.dizin / "derleme" / ad
        k.mkdir(parents=True, exist_ok=True)
        d = {"baslik": "Yayın Kolajı #1: haftanın en iyileri", "aciklama": "Bölümler:\n0:00 Giriş\n1:00 Bir", "sure_sn": 660,
             "cozunurluk": "1920x1080", "uyarilar": []}
        d.update(ek)
        (k / "derleme.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        (k / "derleme.mp4").write_bytes(b"derleme-mp4")
        (k / "kucuk-resim-1.png").write_bytes(b"png1")
        (k / "kucuk-resim-2.png").write_bytes(b"png2")
        return k / "derleme.json"

    def cli(self, *arg):
        cikti = io.StringIO()
        with contextlib.redirect_stdout(cikti):
            kod = ky.ana(["--manifest", str(self.manifest), *arg])
        return kod, cikti.getvalue()

    def man(self):
        return ks.yukle(self.manifest)

    def yayinda_yap(self, oge_id):
        m = self.man()
        o = m["ogeler"][oge_id]
        o["yayinda"] = {"zaman": "2026-11-18T11:00:00Z", "yuklenen_ozet": o["onay"]["ozet"], "sure": 40.0,
                        **ks.dosya_adlari(oge_id, o["tur"])}
        ks.kaydet(m, self.manifest)


class OnayKapisi(KlipYayinTemel):
    def test_onaysiz_klip_aday_olmaz(self):
        self.paket_yaz()
        self.cli("liste")
        self.assertEqual(ks.adaylar(self.man()), [])
        m = ks.bos_manifest()
        m["ogeler"]["k1"] = oge(onay=None)
        del m["ogeler"]["k1"]["onay"]
        self.assertEqual(ks.adaylar(m), [])

    def test_onayli_ama_yuklenmemis_aday_olmaz(self):
        self.paket_yaz()
        self.cli("liste")
        kod, _ = self.cli("onayla", "1")
        self.assertEqual(kod, 0)
        self.assertEqual(len(self.man()["ogeler"]), 1)
        self.assertEqual(ks.adaylar(self.man()), [])

    def test_onayli_ve_yuklenmis_aday_olur_yalniz_turkce(self):
        self.paket_yaz()
        self.cli("liste")
        self.cli("onayla", "1")
        self.yayinda_yap("eraycan-20261112-aaa-klip-01")
        a = ks.adaylar(self.man())
        self.assertEqual(len(a), 1)
        self.assertEqual((a[0]["sosyal_tur"], list(a[0]["diller"])), ("klip", ["tr"]))
        self.assertIn("Kaynak: https://kick.com/eray", a[0]["diller"]["tr"]["yt_aciklama"])

    def test_mp4_degisince_onay_duser(self):
        j = self.paket_yaz()
        self.cli("liste")
        self.cli("onayla", "1")
        j.with_suffix(".mp4").write_bytes(b"baska video")
        kod, cikti = self.cli("yukle")
        self.assertEqual(kod, 1)
        self.assertIn("ONAY DÜŞTÜ", cikti)
        self.assertNotIn("onay", next(iter(self.man()["ogeler"].values())))

    def test_paket_degisince_onay_duser_ve_durum_gorunur(self):
        j = self.paket_yaz()
        self.cli("liste")
        self.cli("onayla", "1")
        p = json.loads(j.read_text(encoding="utf-8"))
        p["baslik"] = "değişti"
        j.write_text(json.dumps(p, ensure_ascii=False), encoding="utf-8")
        o = next(x for x in ky.tara() if x["json"] == j)
        self.assertEqual(ky.durum_metni(o, self.man())[1], "dustu")
        kod, cikti = self.cli("yukle")
        self.assertIn("ONAY DÜŞTÜ", cikti)

    def test_yuklemeden_sonra_dosya_degisirse_aday_olmaz(self):
        m = ks.bos_manifest()
        m["ogeler"]["k1"] = oge()
        m["ogeler"]["k1"]["yayinda"]["yuklenen_ozet"] = "baska"
        self.assertEqual(ks.adaylar(m), [])

    def test_metin_elle_degisirse_onay_gecersiz(self):
        m = ks.bos_manifest()
        m["ogeler"]["k1"] = oge()
        m["ogeler"]["k1"]["metin"]["baslik"] = "Cio onaylamadı bunu"
        self.assertEqual(ks.adaylar(m), [])

    def test_beklet_ve_geri_cek_adayi_kaldirir(self):
        m = ks.bos_manifest()
        m["ogeler"]["k1"] = oge()
        self.assertEqual(len(ks.adaylar(m)), 1)
        m["ogeler"]["k1"]["beklet"] = True
        self.assertEqual(ks.adaylar(m), [])
        self.paket_yaz()
        self.cli("liste")
        self.cli("onayla", "1")
        self.yayinda_yap("eraycan-20261112-aaa-klip-01")
        self.assertEqual(len(ks.adaylar(self.man())), 1)
        self.cli("geri-cek", "1")
        self.assertEqual(ks.adaylar(self.man()), [])

    def test_liste_eskidiyse_numarayla_onay_reddedilir(self):
        j = self.paket_yaz()
        self.cli("liste")
        j.with_suffix(".mp4").write_bytes(b"izlenenden farkli")
        kod, cikti = self.cli("onayla", "1")
        self.assertEqual(kod, 1)
        self.assertIn("değişmiş", cikti)
        self.assertEqual(self.man()["ogeler"], {})

    def test_numaralar_kalici(self):
        self.paket_yaz(ad="klip-01")
        self.cli("liste")
        self.paket_yaz(ad="klip-00")  # sıralamada öne düşer ama numarası yeni
        self.cli("liste")
        kayit = ky.liste_kaydi_oku()["ogeler"]
        self.assertEqual(kayit["1"]["paket"], "cikti/eraycan-20261112-aaa/klip-01.json")
        self.assertEqual(kayit["2"]["paket"], "cikti/eraycan-20261112-aaa/klip-00.json")

    def test_ortusen_varyant_listede_gizlenir_ve_ikincisi_onaylanamaz(self):
        self.paket_yaz(ad="konusma-hizali-01", bas=100, bit=140)
        self.paket_yaz(ad="canli-01", bas=105, bit=145)
        ogeler = ky.tara()
        goruner = [o["goreli"] for o in ogeler if not o["yok_notu"]]
        self.assertEqual(goruner, ["cikti/eraycan-20261112-aaa/konusma-hizali-01.json"])
        self.cli("liste")
        self.assertEqual(self.cli("onayla", "1")[0], 0)
        kod, cikti = self.cli("onayla", str(self.dizin / "cikti" / "eraycan-20261112-aaa" / "canli-01.json"))
        self.assertEqual(kod, 1)
        self.assertIn("zaten onaylı", cikti)

    def test_eski_ve_deneme_klasorleri_listelenmez(self):
        self.paket_yaz(klasor="ESKI-yogunluk-x", ad="klip-01")
        self.paket_yaz(klasor="eski", ad="klip-02")
        self.derleme_yaz("deneme-20261118-090034")
        self.derleme_yaz("yayin-kolaji-1")
        self.assertEqual([o["id"] for o in ky.tara()], ["derleme-yayin-kolaji-1"])

    def test_kufurlu_derleme_metni_onaylanamaz(self):
        self.derleme_yaz(baslik="Amk ne olay #1")
        self.cli("liste")
        kod, cikti = self.cli("onayla", "1")
        self.assertEqual(kod, 1)
        self.assertIn("küfür", cikti)
        self.assertEqual(self.man()["ogeler"], {})

    def test_kufurlu_klip_metni_yedekle_degisir_ve_uyari_listede(self):
        self.paket_yaz(kisa_aciklama="Eray siktir çekiyor", baslik="amk ne yaptı bu")
        o = ky.tara()[0]
        self.assertNotIn("siktir", o["metin"]["baslik"].lower())
        self.assertTrue(o["kufur"])
        self.assertFalse(ks.kufur_var(o["metin"]["baslik"] + o["metin"]["aciklama"]))

    def test_dokumdeki_kufur_uyarisi_ve_dokumsuz_uyari(self):
        self.paket_yaz(ad="klip-01", dokum_metni="bu amk çok iyi", bas=10, bit=20)
        self.paket_yaz(ad="klip-02", dokum_metni="", bas=500, bit=540)
        ogeler = {o["json"].stem: o for o in ky.tara()}
        self.assertTrue(ogeler["klip-01"]["kufur"])
        self.assertFalse(ogeler["klip-02"]["kufur"])
        self.assertTrue(any(u.startswith("döküm yok") for u in ogeler["klip-02"]["uyarilar"]))

    def test_kaynak_1080_degilse_uyari(self):
        self.paket_yaz(video={"genislik": 720, "yukseklik": 1280, "sure_sn": 30})
        self.assertTrue(any("1080p değil" in u for u in ky.tara()[0]["uyarilar"]))

    def test_derleme_kucuk_resim_secimi_onaya_baglanir(self):
        d = self.derleme_yaz()
        self.cli("liste")
        self.assertEqual(self.cli("onayla", "1", "--kucuk-resim", "2")[0], 0)
        o = self.man()["ogeler"]["derleme-yayin-kolaji-1"]
        self.assertEqual(o["onay"]["kucuk_resim"], "kucuk-resim-2.png")
        (d.parent / "kucuk-resim-2.png").write_bytes(b"degisti")
        self.assertEqual(ky.durum_metni(ky.tara()[0], self.man())[1], "dustu")

    def test_yukle_kuru_hicbir_sey_calistirmaz_ve_yazmaz(self):
        self.paket_yaz()
        self.cli("liste")
        self.cli("onayla", "1")
        once = self.manifest.read_text(encoding="utf-8")
        with mock.patch.object(subprocess, "run", side_effect=AssertionError("kuru çalıştırmada komut koştu")):
            kod, cikti = self.cli("yukle", "--kuru")
        self.assertEqual(kod, 0)
        self.assertIn("klip-eraycan-20261112-aaa-klip-01-1080.mp4", cikti)
        self.assertIn("oracle:/var/www/medya/v/", cikti)
        self.assertEqual(self.manifest.read_text(encoding="utf-8"), once)

    def test_yukle_hedef_bicimi_denetlenir(self):
        self.assertRaises(ky.Hata, ky.hedef_dogrula, "-oProxyCommand=x")
        self.assertRaises(ky.Hata, ky.hedef_dogrula, "bosluklu hedef:/a")


class SayfaSunucusu(KlipYayinTemel):
    """`sayfa`: yerel onay sunucusu. Geçici kapı (0), geçici manifest ve geçici çalışma dizini; gerçek data/klipler.json'a dokunmaz."""

    MP4 = bytes(range(256)) * 4  # 1024 bayt
    KLIP_MP4 = "/dosya/cikti/eraycan-20261112-aaa/klip-01.mp4"

    def setUp(self):
        super().setUp()
        self.paket_yaz(mp4=self.MP4)
        self.sunucu = ky.sunucu_baslat(0, str(self.manifest))
        self.port = self.sunucu.port
        self.is_parcasi = threading.Thread(target=self.sunucu.serve_forever, daemon=True)
        self.is_parcasi.start()
        self.addCleanup(self._kapat)

    def _kapat(self):
        self.sunucu.shutdown()
        self.sunucu.server_close()
        self.is_parcasi.join(5)

    def istek(self, yontem, yol, govde=None, baslik=None, host=True, origin=True, belirtec=True, ham=None):
        b = {}
        if origin is True:
            b["Origin"] = f"http://127.0.0.1:{self.port}"
        elif origin:
            b["Origin"] = origin
        if belirtec is True:
            b["X-Belirtec"] = self.sunucu.belirtec
        elif belirtec:
            b["X-Belirtec"] = belirtec
        if govde is not None:
            b["Content-Type"] = "application/json"
            govde = json.dumps(govde).encode("utf-8")
        if ham is not None:
            govde = ham
        b.update(baslik or {})
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            c.putrequest(yontem, yol, skip_host=True)
            c.putheader("Host", f"127.0.0.1:{self.port}" if host is True else host)
            for k, v in b.items():
                c.putheader(k, v)
            if govde is not None:
                c.putheader("Content-Length", str(len(govde)))
            c.endheaders(govde)
            r = c.getresponse()
            return r.status, dict(r.getheaders()), r.read()
        finally:
            c.close()

    def sayfa(self):
        kod, _, g = self.istek("GET", "/")
        self.assertEqual(kod, 200)
        return g.decode("utf-8")

    def post(self, yol, veri, **kw):
        kod, _, g = self.istek("POST", yol, veri, **kw)
        return kod, json.loads(g.decode("utf-8"))

    def derleme_no(self):
        liste = json.loads((self.dizin / "onay" / "liste.json").read_text(encoding="utf-8"))["ogeler"]
        return next(n for n, v in liste.items() if v["paket"].startswith("derleme/"))

    def test_yalniz_127_0_0_1_dinler(self):
        self.assertEqual(self.sunucu.server_address[0], "127.0.0.1")

    def test_sayfa_butonlari_belirteci_ve_notu_icerir(self):
        h = self.sayfa()
        for parca in ("Onayla", "Onayı geri al", self.sunucu.belirtec, "Onay yalnız işaretler; paylaşım için yükleme ve gönderim ayrı adımdır.",
                      "yüklenmeyi bekliyor", self.KLIP_MP4, 'name="viewport"'):
            self.assertIn(parca, h)
        self.assertNotIn("file:///", h)

    def test_belirtecsiz_ve_yanlis_belirtecli_post_reddedilir(self):
        self.sayfa()
        for bel in (False, "yanlis"):
            kod, v = self.post("/api/onayla", {"no": "1"}, belirtec=bel)
            self.assertEqual(kod, 403)
            self.assertFalse(v["ok"])
        self.assertFalse(self.manifest.exists())

    def test_yanlis_origin_host_ve_icerik_turu_reddedilir(self):
        self.sayfa()
        for kw in ({"origin": "http://evil.example"}, {"origin": False}, {"origin": f"http://127.0.0.1:{self.port + 1}"}):
            self.assertEqual(self.post("/api/onayla", {"no": "1"}, **kw)[0], 403)
        self.assertEqual(self.post("/api/onayla", {"no": "1"}, host="evil.example")[0], 403)
        self.assertEqual(self.istek("GET", "/", host="evil.example")[0], 403)
        kod, _, _ = self.istek("POST", "/api/onayla", baslik={"Content-Type": "text/plain"}, ham=b'{"no":"1"}')
        self.assertEqual(kod, 415)
        self.assertFalse(self.manifest.exists())

    def test_onayla_manifeste_yazar_geri_al_siler(self):
        self.sayfa()
        kod, v = self.post("/api/onayla", {"no": "1"})
        self.assertEqual((kod, v["ok"]), (200, True))
        self.assertEqual(v["durum"]["sinif"], "onayli")
        self.assertTrue(v["durum"]["onayli"])
        self.assertEqual((v["ozet"]["onayli"], v["ozet"]["bekleyen"]), (1, 1))
        oid = ks.klip_id(self.dizin / "cikti" / "eraycan-20261112-aaa" / "klip-01.json")
        self.assertTrue(ks.onay_gecerli(self.man()["ogeler"][oid]))
        self.assertIn("Onayı geri al", self.sayfa())
        kod, v = self.post("/api/geri-al", {"no": "1"})
        self.assertEqual((kod, v["ok"]), (200, True))
        self.assertFalse(v["durum"]["onayli"])
        self.assertEqual(v["ozet"]["onayli"], 0)
        self.assertNotIn("onay", self.man()["ogeler"][oid])

    def test_komut_satiri_ile_ayni_sonuc(self):
        self.sayfa()
        self.post("/api/onayla", {"no": "1"})
        sayfa_onay = {k: v["onay"]["ozet"] for k, v in self.man()["ogeler"].items()}
        self.assertEqual(self.cli("geri-cek", "1")[0], 0)
        self.assertEqual(self.man()["ogeler"][next(iter(sayfa_onay))].get("onay"), None)
        self.assertEqual(self.cli("onayla", "1")[0], 0)
        self.assertEqual({k: v["onay"]["ozet"] for k, v in self.man()["ogeler"].items()}, sayfa_onay)

    def test_derlemede_kucuk_resim_secilmeden_onaylanamaz(self):
        self.derleme_yaz()
        self.sayfa()
        dno = self.derleme_no()
        kod, v = self.post("/api/onayla", {"no": dno})
        self.assertEqual(kod, 409)
        self.assertIn("Küçük resim", v["mesaj"])
        self.assertEqual(self.man()["ogeler"], {})
        self.assertEqual(self.post("/api/onayla", {"no": dno, "kucuk_resim": 9})[0], 409)
        self.assertEqual(self.post("/api/onayla", {"no": dno, "kucuk_resim": "2"})[0], 409)
        kod, v = self.post("/api/onayla", {"no": dno, "kucuk_resim": 2})
        self.assertEqual(kod, 200)
        self.assertEqual(self.man()["ogeler"]["derleme-yayin-kolaji-1"]["onay"]["kucuk_resim"], "kucuk-resim-2.png")
        h = self.sayfa()
        self.assertIn("type=radio", h)
        self.assertIn("/dosya/derleme/yayin-kolaji-1/kucuk-resim-2.png", h)

    def test_kufurlu_metin_turkce_hata_verir_ve_onaylamaz(self):
        self.derleme_yaz(baslik="Amk ne olay #1")
        self.sayfa()
        kod, v = self.post("/api/onayla", {"no": self.derleme_no(), "kucuk_resim": 1})
        self.assertEqual(kod, 409)
        self.assertIn("küfür", v["mesaj"])
        self.assertEqual(self.man()["ogeler"], {})

    def test_kufur_uyarili_kart_belirgin_isaretlenir(self):
        self.paket_yaz(ad="klip-02", dokum_metni="bu amk çok iyi", bas=500, bit=540)
        h = self.sayfa()
        self.assertIn("KÜFÜR UYARISI", h)
        self.assertIn('data-kufur="1"', h)

    def test_gecersiz_numara_ve_govde_reddedilir(self):
        self.sayfa()
        self.assertEqual(self.post("/api/onayla", {"no": "99"})[0], 409)
        self.assertEqual(self.post("/api/onayla", {"no": "../x"})[0], 409)
        self.assertEqual(self.post("/api/onayla", {})[0], 409)
        self.assertEqual(self.istek("POST", "/api/onayla", baslik={"Content-Type": "application/json"}, ham=b"{bozuk")[0], 400)
        self.assertEqual(self.istek("POST", "/api/onayla", baslik={"Content-Type": "application/json"}, ham=b"[1]")[0], 400)
        self.assertEqual(self.post("/api/baska", {"no": "1"})[0], 404)
        self.assertFalse(self.manifest.exists())

    def test_dosya_yol_kacisi_reddedilir(self):
        (self.kok / "gizli.mp4").write_bytes(b"gizli")
        for yol in ("/dosya/../gizli.mp4", "/dosya/%2e%2e/gizli.mp4", "/dosya/cikti/../../gizli.mp4",
                    "/dosya/cikti%2f..%2f..%2fgizli.mp4", "/dosya/..%5cgizli.mp4", "/dosya/C:/Windows/win.ini", "/dosya//gizli.mp4"):
            kod, _, g = self.istek("GET", yol)
            self.assertIn(kod, (400, 404), yol)
            self.assertNotIn(b"gizli", g, yol)

    def test_yalniz_bilinen_medya_uzantilari_sunulur(self):
        self.assertEqual(self.istek("GET", "/dosya/cikti/eraycan-20261112-aaa/klip-01.json")[0], 404)
        self.assertEqual(self.istek("GET", "/dosya/cikti/yok.mp4")[0], 404)
        kod, h, g = self.istek("GET", self.KLIP_MP4)
        self.assertEqual((kod, g), (200, self.MP4))
        self.assertEqual(h["Content-Type"], "video/mp4")
        self.assertEqual(h["Accept-Ranges"], "bytes")

    def test_range_206_ve_416(self):
        kod, h, g = self.istek("GET", self.KLIP_MP4, baslik={"Range": "bytes=10-19"})
        self.assertEqual((kod, g), (206, self.MP4[10:20]))
        self.assertEqual(h["Content-Range"], "bytes 10-19/1024")
        kod, h, g = self.istek("GET", self.KLIP_MP4, baslik={"Range": "bytes=1000-"})
        self.assertEqual((kod, g, h["Content-Range"]), (206, self.MP4[1000:], "bytes 1000-1023/1024"))
        kod, h, g = self.istek("GET", self.KLIP_MP4, baslik={"Range": "bytes=-4"})
        self.assertEqual((kod, g), (206, self.MP4[-4:]))
        kod, h, g = self.istek("GET", self.KLIP_MP4, baslik={"Range": "bytes=5000-"})
        self.assertEqual((kod, h["Content-Range"]), (416, "bytes */1024"))
        kod, h, g = self.istek("HEAD", self.KLIP_MP4, baslik={"Range": "bytes=0-9"})
        self.assertEqual((kod, g, h["Content-Length"]), (206, b"", "10"))

    def test_aralik_coz(self):
        self.assertIsNone(ky.aralik_coz(None, 10))
        self.assertIsNone(ky.aralik_coz("bytes=0-1,4-5", 10))
        self.assertIsNone(ky.aralik_coz("bytes=-", 10))
        self.assertEqual(ky.aralik_coz("bytes=2-", 10), (2, 9))
        self.assertEqual(ky.aralik_coz("bytes=2-99", 10), (2, 9))
        self.assertEqual(ky.aralik_coz("bytes=-3", 10), (7, 9))
        self.assertEqual(ky.aralik_coz("bytes=-30", 10), (0, 9))
        self.assertEqual(ky.aralik_coz("bytes=10-", 10), "yok")
        self.assertEqual(ky.aralik_coz("bytes=5-2", 10), "yok")

    def test_dolu_kapida_siradaki_bos_kapi_ve_tumu_doluysa_anlasilir_hata(self):
        ikinci = ky.sunucu_baslat(self.port, str(self.manifest))
        self.addCleanup(ikinci.server_close)
        self.assertNotEqual(ikinci.port, self.port)
        with mock.patch.object(ky, "OnaySunucusu", side_effect=OSError("dolu")):
            with self.assertRaises(ky.Hata) as h:
                ky.sunucu_baslat(self.port, str(self.manifest))
        self.assertIn("dolu", str(h.exception))

    def test_sunucu_yukleme_ya_da_komut_calistirmaz(self):
        self.sayfa()
        with mock.patch.object(subprocess, "run", side_effect=AssertionError("komut koştu")), \
                mock.patch.object(subprocess, "Popen", side_effect=AssertionError("komut koştu")):
            self.assertEqual(self.post("/api/onayla", {"no": "1"})[0], 200)
            self.assertEqual(self.post("/api/geri-al", {"no": "1"})[0], 200)
        for o in self.man()["ogeler"].values():
            self.assertNotIn("yayinda", o)

    def test_duragan_liste_notu_ve_baslatici(self):
        self.cli("liste")
        h = (self.dizin / "onay" / "index.html").read_text(encoding="utf-8")
        self.assertIn("butonlar için: Onay Sayfası.bat", h)
        self.assertNotIn("<button", h)
        bat = (self.dizin / "onay" / "Onay Sayfası.bat").read_bytes()
        self.assertFalse(bat.startswith(b"\xef\xbb\xbf"))
        t = bat.decode("utf-8")
        self.assertIn("chcp 65001", t)
        self.assertIn(r"py tools\klip_yayin.py sayfa", t)
        self.assertIn(str(ky.KOK), t)
        self.assertIn("\r\n", t)


class Metin(unittest.TestCase):
    def test_klip_metni_kaynak_ve_etiketler_shorts_yok(self):
        m = ks.klip_metni(paket(), "Eray")
        self.assertIn("Eray", m["baslik"])
        self.assertLessEqual(len(m["baslik"]), ks.BASLIK_AZAMI)
        self.assertIn("Kaynak: https://kick.com/eray", m["aciklama"])
        self.assertNotIn("#Shorts", " ".join(m["etiketler"]) + m["aciklama"])
        self.assertLessEqual(len(m["etiketler"]), 5)

    def test_vod_baglantisi_yalniz_dogrulanmissa(self):
        vod = "https://kick.com/eray/videos/aaa?t=100"
        yok = ks.klip_metni(paket(vod_zaman_damgali_url=vod))["aciklama"]
        var = ks.klip_metni(paket(vod_zaman_damgali_url=vod, vod_zaman_damgali_url_dogrulandi=True))["aciklama"]
        self.assertNotIn(vod, yok)
        self.assertIn(vod, var)

    def test_baslik_kisalir(self):
        m = ks.klip_metni(paket(kisa_aciklama="çok " * 60))
        self.assertLessEqual(len(m["baslik"]), ks.BASLIK_AZAMI)

    def test_derleme_metni_json_den(self):
        m = ks.derleme_metni({"baslik": "Kolaj #1", "aciklama": "0:00 Giriş\n1:00 Bir"})
        self.assertEqual((m["baslik"], m["aciklama"], m["uyarilar"]), ("Kolaj #1", "0:00 Giriş\n1:00 Bir", []))
        self.assertTrue(ks.derleme_metni({"baslik": "amk", "aciklama": ""})["uyarilar"])

    def test_eski_turkce_hakaretler_de_yakalanir(self):
        for m in ("veledi zina", "veled-i zina", "kelp", "kelpler"):
            self.assertTrue(ks.kufur_var(m), m)
        self.assertFalse(ks.kufur_var("kelebek ve kelime"))

    def test_kufur_denetimi_tam_kelime(self):
        self.assertTrue(ks.kufur_var("bu amk çok iyi"))
        self.assertFalse(ks.kufur_var("topu götürüyor ve sıçrıyor"))


class YoutubeGovdesi(unittest.TestCase):
    def adaylar(self):
        m = ks.bos_manifest()
        m["ogeler"]["k1"] = oge()
        m["ogeler"]["d1"] = oge(baslik="Yayın Kolajı #1", tur="derleme")
        m["ogeler"]["d1"]["metin"]["aciklama"] = "0:00 Giriş\n1:00 Bir"
        m["ogeler"]["d1"]["onay"]["metin_ozeti"] = ks.metin_ozeti(m["ogeler"]["d1"]["metin"])
        m["ogeler"]["d1"]["yayinda"] = {**m["ogeler"]["d1"]["yayinda"], **ks.dosya_adlari("d1", "derleme")}
        return {a["id"]: a for a in ks.adaylar(m)}

    def test_klipte_sentetik_medya_false_haberde_true(self):
        a = self.adaylar()["k1"]
        g = sy.yt_govde("tr", a, "", {"youtube": {"gizlilik": "public"}})
        self.assertIs(g["status"]["containsSyntheticMedia"], False)
        self.assertEqual(g["snippet"]["categoryId"], "20")
        self.assertNotIn("localizations", g)
        self.assertIn("#Shorts", g["snippet"]["description"])
        h = sy.yt_govde("tr", haber(), "https://ctrl-agame.com/x", {})
        self.assertIs(h["status"]["containsSyntheticMedia"], True)

    def test_kategori_ayardan(self):
        a = self.adaylar()["k1"]
        self.assertEqual(sy.yt_govde("tr", a, "", {"klip": {"youtube_kategori": "24"}})["snippet"]["categoryId"], "24")
        self.assertEqual(sy.yt_govde("tr", a, "", {"klip": {"youtube_kategori": "99"}})["snippet"]["categoryId"], "20")

    def test_derlemede_shorts_yok_zaman_damgalari_var(self):
        a = self.adaylar()["d1"]
        g = sy.yt_govde("tr", a, "", {})
        self.assertNotIn("#Shorts", g["snippet"]["description"])
        self.assertIn("1:00 Bir", g["snippet"]["description"])
        self.assertIs(g["status"]["containsSyntheticMedia"], False)

    def test_derleme_url_normal_video(self):
        self.assertTrue(sy.yt_url_duzelt({"kimlik": "ABC", "url": "x"}, "derleme")["url"] == "https://www.youtube.com/watch?v=ABC")
        self.assertEqual(sy.yt_url_duzelt({"kimlik": "ABC", "url": "x"}, "klip")["url"], "x")


class DerlemeAg(SahteAg):
    """Derleme: indir(azami) ve küçük resim yükleme (thumbnails.set) çağrılarını da karşılar."""

    def indir(self, url, azami=None):
        self.indirilen += 1
        return b"0123456789ABCDEF"

    def ham(self, method, url, *, govde=None, basliklar=None, zaman=300):
        if "thumbnails/set" in url:
            self.cagrilar.append((method, url.split("?")[0]))
            return 200, {}, "{}"
        return super().ham(method, url, govde=govde, basliklar=basliklar, zaman=zaman)


class KlipPaylasim(SosyalTemel):
    """sosyal_yayinla.calistir: klip adayları haber akışına nasıl katılır."""

    def setUp(self):
        super().setUp()
        self.klip = self.kok / "data" / "klipler.json"
        self.klip.parent.mkdir(exist_ok=True)

    def klip_yaz(self, ogeler):
        m = ks.bos_manifest()
        m["taban"] = "https://medya.test/v/"
        m["ogeler"] = ogeler
        ks.kaydet(m, self.klip)

    def kos(self, ag, ayar_, veri=None, dry=False, simdi=SIMDI, **ek):
        return sy.calistir(ayar_, veri if veri is not None else [], kayit_yolu=self.kayit, manifest_yolu=self.manifest,
                           tum=SIRLAR, ag=ag, dry_run=dry, bugun=BUGUN, simdi=simdi, cikti=lambda *_: None,
                           klip_yolu=self.klip, **ek)

    def hesap_ayari(self, **ek):
        a = ayar(instagram_reel=True, youtube=True)
        a["turler"] = {"haber": True, "klip": True, "derleme": True}
        a["klip"] = {"gunluk_en_fazla": {"instagram_reel": 2, "youtube": 2}, "derleme_gunluk_en_fazla": 1,
                     "haber_varken_haber": True, "youtube_kategori": "20"}
        a["klip"].update(ek)
        return a

    def test_klip_reel_ve_short_gider_baglanti_klip_manifestine_yazilir(self):
        self.klip_yaz({"k1": oge()})
        ag = SahteAg()
        a = self.hesap_ayari()
        self.kos(ag, a)
        self.kos(ag, a, simdi=SIMDI.replace(hour=15))
        anahtarlar = set(self.kayitlar())
        self.assertEqual(anahtarlar, {"k1|tr|instagram|reel", "k1|tr|youtube|short"})
        m = ks.yukle(self.klip)["ogeler"]["k1"]
        self.assertEqual(m["instagram"], "https://www.instagram.com/reel/ABC/")
        self.assertTrue(m["youtube"].startswith("https://www.youtube.com/shorts/"))
        self.assertTrue(all(r["sosyal_tur"] == "klip" for r in self.kayitlar().values()))

    def test_onaysiz_klip_hicbir_cagri_yapmaz(self):
        o = oge()
        del o["onay"]
        self.klip_yaz({"k1": o})
        ag = SahteAg()
        self.kos(ag, self.hesap_ayari())
        self.assertEqual((ag.cagrilar, self.kayitlar()), ([], {}))

    def test_ayni_klip_ayni_platforma_iki_kez_gitmez(self):
        self.klip_yaz({"k1": oge()})
        ag = SahteAg()
        a = self.hesap_ayari()
        for saat in (12, 14, 16, 18):
            self.kos(ag, a, simdi=SIMDI.replace(hour=saat))
        self.assertEqual(sorted(self.kayitlar()), ["k1|tr|instagram|reel", "k1|tr|youtube|short"])
        self.assertEqual(sum(1 for _, u in ag.cagrilar if "media_publish" in u), 1)

    def test_yalniz_turkce_yabanci_dil_hesaplari_klip_almaz(self):
        self.klip_yaz({"k1": oge()})
        ag = SahteAg()
        a = self.hesap_ayari()
        for saat in (12, 14, 16):
            self.kos(ag, a, simdi=SIMDI.replace(hour=saat))
        self.assertTrue(self.kayitlar())
        self.assertTrue(all(k.split("|")[1] == "tr" for k in self.kayitlar()))

    def test_klip_gunluk_siniri(self):
        self.klip_yaz({"k1": oge(), "k2": oge(baslik="Eray ikinci klip | Eray", onay={
            "zaman": "2026-11-18T10:05:00Z", "ozet": "ozet1", "metin_ozeti": ks.metin_ozeti(
                {"baslik": "Eray ikinci klip | Eray", "aciklama": "Kaynak: https://kick.com/eray",
                 "etiketler": ["#Eray", "#Kick"]})})})
        ag = SahteAg()
        a = self.hesap_ayari(gunluk_en_fazla={"instagram_reel": 1, "youtube": 1})
        a["hesaplar"]["tr"]["youtube"] = False
        # bugün bir klip Reel zaten gitmiş, ondan sonra bir haber gitmiş (art arda aynı tür kuralı devre dışı kalsın)
        self.kayit_yaz(klip_zamani="2026-11-15T03:00:00+00:00")
        self.kos(ag, a, simdi=SIMDI.replace(hour=20))
        self.assertEqual([k for k in self.kayitlar() if k.startswith("k")], [])

    def kayit_yaz(self, klip_zamani):
        r = {"dil": "tr", "platform": "instagram", "bicim": "reel", "durum": "tamam"}
        self.kayit.write_text(json.dumps({
            "eski|tr|instagram|reel": {**r, "id": "eski", "sosyal_tur": "klip", "zaman": klip_zamani},
            "haberx|tr|instagram|reel": {**r, "id": "haberx", "sosyal_tur": "haber", "zaman": "2026-11-15T10:00:00+00:00"}}),
            encoding="utf-8")

    def test_klip_gunluk_siniri_dun_sayilmaz(self):
        self.klip_yaz({"k1": oge()})
        a = self.hesap_ayari(gunluk_en_fazla={"instagram_reel": 1, "youtube": 1})
        a["hesaplar"]["tr"]["youtube"] = False
        self.kayit_yaz(klip_zamani="2026-11-14T03:00:00+00:00")  # dünkü klip bugünün hakkını yemez
        self.kos(SahteAg(), a, simdi=SIMDI.replace(hour=20))
        self.assertEqual([k for k in self.kayitlar() if k.startswith("k1")], ["k1|tr|instagram|reel"])

    def test_haber_varken_sira_haberde(self):
        self.klip_yaz({"k1": oge()})
        self.manifest_yaz()
        ag = SahteAg()
        a = self.hesap_ayari()
        a["hesaplar"]["tr"]["youtube"] = False
        self.kos(ag, a, veri=[haber()])
        self.assertEqual(list(self.kayitlar()), ["oyun-yama-1|tr|instagram|reel"])

    def test_haber_yoksa_klip_gider_ve_haber_varken_haber_kapatilabilir(self):
        self.klip_yaz({"k1": oge()})
        self.manifest_yaz()
        a = self.hesap_ayari(haber_varken_haber=False)
        a["hesaplar"]["tr"]["youtube"] = False
        self.kos(SahteAg(), a, veri=[haber()])
        self.assertEqual(len(self.kayitlar()), 1)  # çalışma başına tek gönderi: haber ya da klip yarışır
        self.kayit.unlink()
        b = self.hesap_ayari()
        b["hesaplar"]["tr"]["youtube"] = False
        self.kos(SahteAg(), b, veri=[])
        self.assertEqual(list(self.kayitlar()), ["k1|tr|instagram|reel"])

    def test_derleme_yalniz_youtube_instagram_a_gitmez(self):
        self.klip_yaz({"d1": oge(baslik="Yayın Kolajı #1", tur="derleme", yayinda=False)})
        m = ks.yukle(self.klip)
        m["ogeler"]["d1"]["yayinda"] = {"zaman": "z", "yuklenen_ozet": "ozet1", "sure": 660.0,
                                        **ks.dosya_adlari("d1", "derleme")}
        ks.kaydet(m, self.klip)

        ag = DerlemeAg()
        a = self.hesap_ayari()
        for saat in (12, 14, 16):
            self.kos(ag, a, simdi=SIMDI.replace(hour=saat))
        self.assertEqual(list(self.kayitlar()), ["d1|tr|youtube|short"])
        self.assertFalse(any("media" in u for _, u in ag.cagrilar))
        self.assertTrue(ks.yukle(self.klip)["ogeler"]["d1"]["youtube"].startswith("https://www.youtube.com/watch?v="))

    def test_dry_run_klip_basligi_ve_govdesi(self):
        self.klip_yaz({"k1": oge()})
        satirlar = []
        a = self.hesap_ayari()
        sy.calistir(a, [], kayit_yolu=self.kayit, manifest_yolu=self.manifest, tum=SIRLAR, ag=YasakAg(), dry_run=True,
                    bugun=BUGUN, simdi=SIMDI, cikti=satirlar.append, klip_yolu=self.klip)
        yazi = "\n".join(satirlar)
        self.assertIn("[klip]", yazi)
        self.assertIn("Eray patates soyuyor | Eray", yazi)
        self.assertIn('"containsSyntheticMedia": false', yazi)
        self.assertFalse(self.kayit.exists())  # kuru çalışma kayıt yazmaz

    def test_klip_yokken_haber_akisi_birebir_ayni(self):
        sonuclar = []
        for klip_yolu in (self.kok / "yok" / "klipler.json", None):
            self.kayit.unlink(missing_ok=True)
            self.manifest_yaz()
            ag = SahteAg()
            a = ayar(instagram_reel=True, youtube=True, instagram=True)
            sy.calistir(a, [haber()], kayit_yolu=self.kayit, manifest_yolu=self.manifest, tum=SIRLAR, ag=ag, dry_run=False,
                        bugun=BUGUN, simdi=SIMDI, cikti=lambda *_: None, klip_yolu=klip_yolu)
            kay = {k: {a_: b for a_, b in r.items() if a_ != "niyet_zamani"} for k, r in self.kayitlar().items()}
            sonuclar.append((ag.cagrilar, kay))
        self.klip_yaz({})  # boş ama var olan manifest de aynı sonucu verir
        self.kayit.unlink(missing_ok=True)
        self.manifest_yaz()
        ag = SahteAg()
        a = ayar(instagram_reel=True, youtube=True, instagram=True)
        sy.calistir(a, [haber()], kayit_yolu=self.kayit, manifest_yolu=self.manifest, tum=SIRLAR, ag=ag, dry_run=False,
                    bugun=BUGUN, simdi=SIMDI, cikti=lambda *_: None, klip_yolu=self.klip)
        kay = {k: {a_: b for a_, b in r.items() if a_ != "niyet_zamani"} for k, r in self.kayitlar().items()}
        sonuclar.append((ag.cagrilar, kay))
        self.assertTrue(sonuclar[0][1])
        self.assertEqual(sonuclar[0], sonuclar[1])
        self.assertEqual(sonuclar[0], sonuclar[2])


class SiteGorunumu(unittest.TestCase):
    def test_klip_manifesti_haber_videosu_manifestinden_ayri(self):
        self.assertNotEqual(ks.MANIFEST_YOLU, vs.MANIFEST_YOLU)
        with tempfile.TemporaryDirectory() as t:
            yol = pathlib.Path(t) / "klipler.json"
            m = ks.bos_manifest()
            m["ogeler"]["k1"] = oge()
            ks.kaydet(m, yol)
            # video_site klipler.json'u hiç okumaz: aynı kimlikle sorgulansa bile haber videosu çıkmaz
            self.assertIsNone(vs.bul(vs.yukle(yol), "k1", "tr"))
            self.assertEqual(vs.onay_bekleyenler(vs.yukle(yol)), [])

    def test_site_kodu_klip_manifestini_anmaz(self):
        for ad in ("video_site.py", "site_uret.py", "haber_uret.py"):
            yol = pathlib.Path(__file__).resolve().parents[1] / "tools" / ad
            if yol.exists():
                self.assertNotIn("klipler.json", yol.read_text(encoding="utf-8"), ad)


class Baglanti(unittest.TestCase):
    def test_baglanti_yaz_yalniz_istenen_alani_degistirir(self):
        with tempfile.TemporaryDirectory() as t:
            yol = pathlib.Path(t) / "klipler.json"
            m = ks.bos_manifest()
            m["ogeler"]["k1"] = oge()
            ks.kaydet(m, yol)
            self.assertTrue(ks.baglanti_yaz(yol, "k1", "youtube", "https://www.youtube.com/shorts/X"))
            self.assertFalse(ks.baglanti_yaz(yol, "yok", "youtube", "https://x"))
            self.assertFalse(ks.baglanti_yaz(yol, "k1", "onay", "https://x"))
            o = ks.yukle(yol)["ogeler"]["k1"]
            self.assertEqual(o["youtube"], "https://www.youtube.com/shorts/X")
            self.assertEqual(o["onay"], m["ogeler"]["k1"]["onay"])

    def test_bozuk_manifest_bos_sayilir(self):
        with tempfile.TemporaryDirectory() as t:
            yol = pathlib.Path(t) / "klipler.json"
            yol.write_text("{bozuk", encoding="utf-8")
            self.assertEqual(ks.yukle(yol)["ogeler"], {})
            self.assertEqual(ks.adaylar(ks.yukle(yol)), [])


if __name__ == "__main__":
    unittest.main()
