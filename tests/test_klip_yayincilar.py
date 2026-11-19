"""Onay panelinin "Yayıncılar" bölümü: ekleme (sahte Kick/YouTube yanıtı), yinelenme, kaldır/geri getir, JSON biçimi,
arka plan klip çıkarma kuyruğu ve HTTP güvenliği. Gerçek ağ yok; gerçek ayar ve klip paketlerine dokunmaz (geçici dosyalar)."""
import copy
import json
import os
import pathlib
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import klip_yayin as ky  # noqa: E402
import klip_yayincilar as kyc  # noqa: E402
import yayin_klip as yk  # noqa: E402
from test_klip_yayin import KlipYayinTemel, SayfaSunucusu  # noqa: E402

GERCEK_AYAR = pathlib.Path(__file__).resolve().parents[1] / "otomasyon" / "klip-yayincilar.json"

AYAR_METNI = (
    '{\r\n'
    '  "_not": "Deneme notu: \\"tırnaklı\\" ve Türkçe ğüşiöç.",\r\n'
    '  "ayar": {\r\n'
    '    "dilim_sn": 10,\r\n'
    '    "gulme_tam_oran": 0.30,\r\n'
    '    "yontem": "sinyal",\r\n'
    '    "klip_ek_etiketler": ["#Komixsi"]\r\n'
    '  },\r\n'
    '  "yayincilar": [\r\n'
    '    {"ad": "Tolunay Ören", "kisa_ad": "Tolunay", "platform": "kick", "kanal": "tolunayoren", "etkin": true, '
    '"youtube_kanallari": [{"kanal_id": "UCssA44vdQ0dNEMHrpa8iC9Q", "tanitici": "TolunayOren", "etkin": true}]},\r\n'
    '    {"ad": "wtcN", "kisa_ad": "Ferit", "platform": "kick", "kanal": "wtcn", "etkin": true, "kamera_kutu": [0.7, 0.6, 0.3, 0.4]}\r\n'
    '  ]\r\n'
    '}\r\n')

UC_YENI = "UC" + "a" * 22
UC_BASKA = "UC" + "b" * 22


def kick_yanit(slug="yeniyayinci", kullanici="YeniYayıncı", canli=False, videolar=True):
    def f(url):
        if url.endswith("/videos"):
            if not videolar:
                raise yk.KlipHatasi("404")
            return json.dumps([{"session_title": "Akşam sohbeti", "start_time": "2026-11-17T18:00:00Z"}])
        if url.endswith(f"/channels/{slug}"):
            return json.dumps({"slug": slug, "user": {"username": kullanici},
                               "livestream": {"session_title": "Canlı başlık"} if canli else None})
        raise yk.KlipHatasi("404")
    return f


def yt_yanit(cid=UC_YENI, uid="@yeniyt", ad="Yeni YT"):
    return lambda url: {"channel_id": cid, "uploader_id": uid, "channel": ad, "entries": [{"title": "Son video başlığı"}]}


class AyarTemel(unittest.TestCase):
    def setUp(self):
        self.gecici = tempfile.TemporaryDirectory()
        self.addCleanup(self.gecici.cleanup)
        self.kok = pathlib.Path(self.gecici.name)
        self.ayar = self.kok / "klip-yayincilar.json"
        self.ayar.write_bytes(AYAR_METNI.encode("utf-8"))
        self.yedek = self.kok / "yedek"
        ort = mock.patch.dict(os.environ, {"KLIP_YAYINCILAR": str(self.ayar), "KLIP_YAYINCI_YEDEK": str(self.yedek),
                                           "YAYIN_KLIP_DIZIN": str(self.kok / "calisma")})
        ort.start()
        self.addCleanup(ort.stop)
        self.on = kyc.Onizlemeler()

    def veri(self):
        return json.loads(self.ayar.read_text(encoding="utf-8"))

    def ekle_kick(self, slug="yeniyayinci", **ek):
        ek.setdefault("ad", "Yeni")
        with mock.patch.object(kyc, "_kick_http", kick_yanit(slug)):
            o = kyc.onizle({"kick": f"kick.com/{slug}"}, self.on)
        return kyc.ekle({"jeton": o["jeton"], **ek}, self.on)


class Ayiklama(unittest.TestCase):
    def test_kick_girdileri(self):
        for g in ("kick.com/WtcN", "https://kick.com/wtcn/", "https://www.kick.com/wtcn?x=1", "wtcN", "@wtcn", " wtcn "):
            self.assertEqual(kyc.kick_kanali_ayikla(g), "wtcn", g)

    def test_kick_gecersiz(self):
        for g in ("", "a b", "evil.com/wtcn", "kick.com.evil.com/x", "https://kick.com/", "javascript:alert(1)", "x" * 41,
                  "kick.com/../etc", "wtcn;rm -rf", "ftp://kick.com/x", "https://kick.com@evil.com/x", "ğüş"):
            with self.assertRaises(kyc.Hata, msg=g):
                kyc.kick_kanali_ayikla(g)

    def test_youtube_girdileri(self):
        self.assertEqual(kyc.youtube_ayikla("@wtcNFerit"), ("tanitici", "wtcNFerit"))
        self.assertEqual(kyc.youtube_ayikla("https://www.youtube.com/@wtcNFerit/videos"), ("tanitici", "wtcNFerit"))
        self.assertEqual(kyc.youtube_ayikla(f"youtube.com/channel/{UC_YENI}"), ("id", UC_YENI))
        self.assertEqual(kyc.youtube_ayikla(UC_YENI), ("id", UC_YENI))
        self.assertEqual(kyc.youtube_ayikla("@KendineMüzisyenKM"), ("tanitici", "KendineMüzisyenKM"))

    def test_youtube_gecersiz(self):
        for g in ("", "https://youtube.com/watch?v=abc", "https://evil.com/@x", "youtube.com.evil.com/@abc", "@a", "a/b",
                  "https://www.youtube.com/", "@ab cd", "-flag --exec"):
            with self.assertRaises(kyc.Hata, msg=g):
                kyc.youtube_ayikla(g)


class Ekleme(AyarTemel):
    def test_kick_ekle_biçim_korunur(self):
        onceki = self.ayar.read_bytes().decode("utf-8")
        sonuc = self.ekle_kick(ad="Yeni Yayıncı")
        self.assertTrue(sonuc["ok"])
        v = self.veri()
        self.assertEqual([r["ad"] for r in v["yayincilar"]], ["Tolunay Ören", "wtcN", "Yeni Yayıncı"])
        yeni = v["yayincilar"][-1]
        self.assertEqual(yeni, {"ad": "Yeni Yayıncı", "kisa_ad": "Yeni", "platform": "kick", "kanal": "yeniyayinci", "etkin": True})
        ham = self.ayar.read_bytes().decode("utf-8")
        self.assertIn("\r\n", ham)
        self.assertNotIn("\n\n", ham.replace("\r\n", ""))
        self.assertEqual(ham.count("\n"), ham.count("\r\n"))     # satır sonu hep CRLF
        # önceki bölüm (``_not``, ``ayar``: 0.30, Türkçe) ve eski yayıncı satırları harfi harfine aynı
        self.assertEqual(ham.split('"yayincilar"')[0], onceki.split('"yayincilar"')[0])
        self.assertIn('"gulme_tam_oran": 0.30', ham)
        for satir in onceki.split("\r\n")[10:12]:
            self.assertIn(satir.rstrip(","), ham)
        self.assertIn("Tolunay Ören", ham)       # ensure_ascii kapalı
        # her yayıncı tek satır
        satirlar = [s for s in ham.split("\r\n") if s.strip().startswith('{"ad"')]
        self.assertEqual(len(satirlar), 3)
        yk.ayar_yukle(self.ayar)                  # hattın kendi okuyucusu kabul eder

    def test_yedek_alinir(self):
        self.ekle_kick()
        yedekler = list(self.yedek.glob("*"))
        self.assertEqual(len(yedekler), 1)
        self.assertEqual(yedekler[0].read_bytes(), AYAR_METNI.encode("utf-8"))   # yazımdan ÖNCEKİ hâl
        self.assertFalse(list(self.kok.glob("*.tmp")))

    def test_kisa_ad_bos_ilk_kelime(self):
        self.ekle_kick(ad="Ayşe Nur Kaya", kisa_ad="")
        self.assertEqual(self.veri()["yayincilar"][-1]["kisa_ad"], "Ayşe")

    def test_ad_ve_kisa_ad_duzenlenebilir(self):
        self.ekle_kick(ad="Özel Ad", kisa_ad="Özel")
        r = self.veri()["yayincilar"][-1]
        self.assertEqual((r["ad"], r["kisa_ad"]), ("Özel Ad", "Özel"))

    def test_onizleme_karti(self):
        with mock.patch.object(kyc, "_kick_http", kick_yanit(canli=True)), mock.patch.object(kyc, "_yt_bilgi", yt_yanit()):
            o = kyc.onizle({"kick": "https://kick.com/YeniYayinci", "youtube": "@yeniyt"}, self.on)
        k = o["kart"]
        self.assertEqual(k["ad"], "YeniYayıncı")
        self.assertEqual(k["kick"]["kanal"], "yeniyayinci")
        self.assertTrue(k["kick"]["canli"])
        self.assertIn("Akşam sohbeti", k["kick"]["son_yayin"])
        self.assertEqual(k["youtube"]["kanal_id"], UC_YENI)
        self.assertEqual(k["youtube"]["son_video"], "Son video başlığı")
        self.assertEqual(self.ayar.read_bytes(), AYAR_METNI.encode("utf-8"))   # önizleme dosyaya yazmaz

    def test_kick_ve_youtube_birlikte(self):
        with mock.patch.object(kyc, "_kick_http", kick_yanit()), mock.patch.object(kyc, "_yt_bilgi", yt_yanit()):
            o = kyc.onizle({"kick": "yeniyayinci", "youtube": "@yeniyt"}, self.on)
        kyc.ekle({"jeton": o["jeton"], "ad": "Yeni"}, self.on)
        r = self.veri()["yayincilar"][-1]
        self.assertEqual(r["youtube_kanallari"], [{"kanal_id": UC_YENI, "tanitici": "yeniyt", "etkin": True}])
        yk.ayar_yukle(self.ayar)

    def test_yalniz_youtube(self):
        with mock.patch.object(kyc, "_yt_bilgi", yt_yanit()):
            o = kyc.onizle({"youtube": "https://www.youtube.com/@yeniyt"}, self.on)
        self.assertIsNone(o["kart"]["kick"])
        s = kyc.ekle({"jeton": o["jeton"], "ad": "Yalnız YT"}, self.on)
        self.assertIn("Yalnız YouTube", s["mesaj"])
        r = self.veri()["yayincilar"][-1]
        self.assertEqual(r["platform"], "youtube")
        self.assertEqual(r["kanal"], "yeniyt")
        yay = yk.ayar_yukle(self.ayar)["yayincilar"]
        self.assertTrue(any(y.get("ad") == "Yalnız YT" for y in yay))

    def test_yalniz_youtube_taranir(self):
        """Yalnız-YouTube yayıncı tara()'da Kick'e gitmeden YouTube kanalından aranır."""
        with mock.patch.object(kyc, "_yt_bilgi", yt_yanit()):
            o = kyc.onizle({"youtube": "@yeniyt"}, self.on)
        kyc.ekle({"jeton": o["jeton"], "ad": "Yalnız YT"}, self.on)
        ayar = yk.ayar_yukle(self.ayar)
        y = next(x for x in ayar["yayincilar"] if x["ad"] == "Yalnız YT")
        self.assertEqual(y["youtube_kanallari"][0]["kanal_id"], UC_YENI)
        cagrilar = []

        def yt_tara(a, d, yayinci, hepsi, simdi):
            cagrilar.append([x["ad"] for x in a["yayincilar"] if x["etkin"]])
            return {"yeni": [], "atlanan_islenmis": [], "youtube_atlanan": [], "youtube_kanallar": [], "hata": []}
        with mock.patch.object(yk, "kick_vodlar", side_effect=AssertionError("Kick çağrılmamalı")) as kv, \
                mock.patch.object(yk.klip_youtube, "tara", yt_tara):
            r = yk.tara({**ayar, "yayincilar": [y]}, self.kok / "calisma")
        kv.assert_not_called()
        self.assertEqual(r["desteksiz"], [])              # "desteklenmeyen platform" sayılmaz
        self.assertEqual(r["hata"], [])
        self.assertEqual(cagrilar, [["Yalnız YT"]])       # YouTube taraması bu yayıncıyla çağrıldı

    def test_en_az_biri_sart(self):
        with self.assertRaises(kyc.Hata):
            kyc.onizle({"kick": "", "youtube": "  "}, self.on)
        with self.assertRaises(kyc.Hata):
            kyc.onizle({}, self.on)

    def test_kick_bulunamadi(self):
        def f(url):
            raise yk.KlipHatasi("HTTP 404")
        with mock.patch.object(kyc, "_kick_http", f):
            with self.assertRaisesRegex(kyc.Hata, "bulunamadı"):
                kyc.onizle({"kick": "yokboyle"}, self.on)

    def test_kick_bot_korumasi_ve_ag_hatasi(self):
        with mock.patch.object(kyc, "_kick_http", mock.Mock(side_effect=yk.Desteklenmiyor("bot"))):
            with self.assertRaisesRegex(kyc.Hata, "reddetti"):
                kyc.onizle({"kick": "yeni"}, self.on)
        with mock.patch.object(kyc, "_kick_http", mock.Mock(side_effect=yk.KlipHatasi("zaman aşımı"))):
            with self.assertRaisesRegex(kyc.Hata, "ulaşılamadı"):
                kyc.onizle({"kick": "yeni"}, self.on)
        with mock.patch.object(kyc, "_kick_http", mock.Mock(return_value="<html>")):
            with self.assertRaisesRegex(kyc.Hata, "anlaşılamadı"):
                kyc.onizle({"kick": "yeni"}, self.on)

    def test_kick_slug_uyusmazligi_reddedilir(self):
        def f(url):
            return json.dumps({"slug": "../kotu", "user": {"username": "x"}})
        with mock.patch.object(kyc, "_kick_http", f):
            with self.assertRaises(kyc.Hata):
                kyc.onizle({"kick": "yeni"}, self.on)

    def test_youtube_bulunamadi_ve_ulasilamadi(self):
        with mock.patch.object(kyc, "_yt_bilgi", mock.Mock(side_effect=Exception("HTTP Error 404: Not Found"))):
            with self.assertRaisesRegex(kyc.Hata, "bulunamadı"):
                kyc.onizle({"youtube": "@yokboyle"}, self.on)
        with mock.patch.object(kyc, "_yt_bilgi", mock.Mock(side_effect=Exception("getaddrinfo failed"))):
            with self.assertRaisesRegex(kyc.Hata, "ulaşılamadı"):
                kyc.onizle({"youtube": "@yokboyle"}, self.on)

    def test_youtube_kanal_kimligi_yok(self):
        with mock.patch.object(kyc, "_yt_bilgi", lambda u: {"channel_id": "", "entries": []}):
            with self.assertRaisesRegex(kyc.Hata, "kimliği"):
                kyc.onizle({"youtube": "@bosyt"}, self.on)

    def test_dis_cagri_zaman_asimi(self):
        def yavas():
            time.sleep(5)
        t0 = time.monotonic()
        with self.assertRaisesRegex(kyc.Hata, "zamanında"):
            kyc._sinirli(yavas, 0.2)
        self.assertLess(time.monotonic() - t0, 3)

    def test_jeton_olmadan_ekle_olmaz(self):
        for j in (None, "", "uydurma", 5, {"a": 1}):
            with self.assertRaises(kyc.Hata):
                kyc.ekle({"jeton": j, "ad": "X"}, self.on)
        self.assertEqual(self.ayar.read_bytes(), AYAR_METNI.encode("utf-8"))

    def test_jeton_bir_kez_kullanilir(self):
        with mock.patch.object(kyc, "_kick_http", kick_yanit()):
            o = kyc.onizle({"kick": "yeniyayinci"}, self.on)
        kyc.ekle({"jeton": o["jeton"], "ad": "Yeni"}, self.on)
        with self.assertRaises(kyc.Hata):
            kyc.ekle({"jeton": o["jeton"], "ad": "Yeni 2"}, self.on)

    def test_jeton_suresi_dolar(self):
        with mock.patch.object(kyc, "_kick_http", kick_yanit()):
            o = kyc.onizle({"kick": "yeniyayinci"}, self.on)
        with mock.patch.object(kyc, "ONIZLEME_OMRU", -1):
            with self.assertRaisesRegex(kyc.Hata, "süresi"):
                kyc.ekle({"jeton": o["jeton"], "ad": "Yeni"}, self.on)

    def test_ad_dogrulama(self):
        with mock.patch.object(kyc, "_kick_http", kick_yanit()):
            o = kyc.onizle({"kick": "yeniyayinci"}, self.on)
        for ad in ("", "   ", "x" * 500, 5, None):
            with self.assertRaises(kyc.Hata, msg=repr(ad)):
                kyc.ekle({"jeton": o["jeton"], "ad": ad}, self.on)
        self.assertEqual(self.ayar.read_bytes(), AYAR_METNI.encode("utf-8"))


    def test_ad_satir_sonu_ve_denetim_karakteri_temizlenir(self):
        self.ekle_kick(ad="Ali\nVeli\u0000 Can")
        ad = self.veri()["yayincilar"][-1]["ad"]
        self.assertNotIn("\n", ad)
        self.assertNotIn("\x00", ad)


class Yinelenme(AyarTemel):
    def test_ayni_kick_kanali_harf_duyarsiz(self):
        for g in ("wtcn", "WTCN", "https://kick.com/WtcN", "kick.com/wtcN/"):
            with mock.patch.object(kyc, "_kick_http", kick_yanit("wtcn")):
                with self.assertRaisesRegex(kyc.Hata, "zaten"):
                    kyc.onizle({"kick": g}, self.on)

    def test_ayni_youtube_kanali(self):
        with self.assertRaisesRegex(kyc.Hata, "zaten"):
            kyc.onizle({"youtube": "UCssA44vdQ0dNEMHrpa8iC9Q"}, self.on)
        with self.assertRaisesRegex(kyc.Hata, "zaten"):
            kyc.onizle({"youtube": "UCSSA44VDQ0DNEMHRPA8IC9Q"}, self.on)       # harf duyarsız
        with mock.patch.object(kyc, "_yt_bilgi", yt_yanit(cid="UCssA44vdQ0dNEMHrpa8iC9Q", uid="@TolunayOren")):
            with self.assertRaisesRegex(kyc.Hata, "zaten"):
                kyc.onizle({"youtube": "@TolunayOren"}, self.on)

    def test_ayni_ad(self):
        with mock.patch.object(kyc, "_kick_http", kick_yanit()):
            o = kyc.onizle({"kick": "yeniyayinci"}, self.on)
        with self.assertRaisesRegex(kyc.Hata, "zaten"):
            kyc.ekle({"jeton": o["jeton"], "ad": "WTCN"}, self.on)    # harf duyarsız

    def test_kaldirilan_yayinci_tekrar_eklenemez(self):
        an = kyc.anahtar(self.veri()["yayincilar"][1])
        kyc.kaldir({"anahtar": an})
        with mock.patch.object(kyc, "_kick_http", kick_yanit("wtcn")):
            with self.assertRaisesRegex(kyc.Hata, "(?i)kaldırılan|zaten"):
                kyc.onizle({"kick": "wtcn"}, self.on)

    def test_yarisan_iki_ekleme(self):
        """Aynı kanal için iki önizleme jetonu: yalnız biri yazılır (yinelenme yazma anında yeniden denetlenir)."""
        with mock.patch.object(kyc, "_kick_http", kick_yanit()):
            a = kyc.onizle({"kick": "yeniyayinci"}, self.on)
            b = kyc.onizle({"kick": "yeniyayinci"}, self.on)
        kyc.ekle({"jeton": a["jeton"], "ad": "Birinci"}, self.on)
        with self.assertRaisesRegex(kyc.Hata, "zaten"):
            kyc.ekle({"jeton": b["jeton"], "ad": "Ikinci"}, self.on)
        self.assertEqual(len(self.veri()["yayincilar"]), 3)


class KaldirGeriGetir(AyarTemel):
    def test_kaldir_silmez_yedege_yazar(self):
        an = kyc.anahtar(self.veri()["yayincilar"][0])
        kyc.kaldir({"anahtar": an})
        v = self.veri()
        self.assertEqual([r["ad"] for r in v["yayincilar"]], ["wtcN"])
        k = v["kaldirilanlar"][0]
        self.assertEqual(k["ad"], "Tolunay Ören")
        self.assertEqual(k["youtube_kanallari"][0]["kanal_id"], "UCssA44vdQ0dNEMHrpa8iC9Q")   # içerik kaybolmadı
        self.assertTrue(k["kaldirildi"].endswith("Z"))
        yk.ayar_yukle(self.ayar)

    def test_kaldirilan_taranmaz(self):
        kyc.kaldir({"anahtar": kyc.anahtar(self.veri()["yayincilar"][0])})
        adlar = [y["ad"] for y in yk.ayar_yukle(self.ayar)["yayincilar"]]
        self.assertNotIn("Tolunay Ören", adlar)

    def test_geri_getir_ayni_siraya(self):
        once = copy.deepcopy(self.veri()["yayincilar"])
        an = kyc.anahtar(once[0])
        kyc.kaldir({"anahtar": an})
        kyc.geri_getir({"anahtar": an})
        v = self.veri()
        self.assertEqual(v["yayincilar"], once)           # içerik ve sıra aynı
        self.assertNotIn("kaldirilanlar", v)
        self.assertNotIn("sira", json.dumps(v))

    def test_olmayan_yayinci(self):
        for f in (kyc.kaldir, kyc.geri_getir, kyc.duzenle):
            with self.assertRaises(kyc.Hata):
                f({"anahtar": "kick:yok"})
            with self.assertRaises(kyc.Hata):
                f({"anahtar": 5})

    def test_klip_klasorleri_silinmez(self):
        d = self.kok / "calisma" / "cikti" / "tolunay-1"
        d.mkdir(parents=True)
        (d / "klip-01.json").write_text("{}", encoding="utf-8")
        kyc.kaldir({"anahtar": kyc.anahtar(self.veri()["yayincilar"][0])})
        self.assertTrue((d / "klip-01.json").exists())

    def test_liste(self):
        kyc.kaldir({"anahtar": kyc.anahtar(self.veri()["yayincilar"][1])})
        l = kyc.liste({"Tolunay Ören": 4})
        self.assertEqual([y["ad"] for y in l["yayincilar"]], ["Tolunay Ören"])
        self.assertEqual(l["yayincilar"][0]["klip_sayisi"], 4)
        self.assertEqual(l["yayincilar"][0]["youtube"][0]["tanitici"], "TolunayOren")
        self.assertEqual(l["kaldirilanlar"][0]["ad"], "wtcN")
        self.assertEqual(l["kaldirilanlar"][0]["klip_sayisi"], 0)


class Duzenleme(AyarTemel):
    def test_ad_kisa_ad_etkin(self):
        an = kyc.anahtar(self.veri()["yayincilar"][1])
        kyc.duzenle({"anahtar": an, "ad": "Ferit Y", "kisa_ad": "", "etkin": False})
        r = self.veri()["yayincilar"][1]
        self.assertEqual((r["ad"], r["kisa_ad"], r["etkin"]), ("Ferit Y", "Ferit", False))
        self.assertEqual(r["kamera_kutu"], [0.7, 0.6, 0.3, 0.4])      # bilinmeyen alanlar korunur

    def test_youtube_kanal_anahtari(self):
        an = kyc.anahtar(self.veri()["yayincilar"][0])
        kyc.duzenle({"anahtar": an, "youtube": [{"kanal_id": "UCssA44vdQ0dNEMHrpa8iC9Q", "etkin": False}]})
        self.assertFalse(self.veri()["yayincilar"][0]["youtube_kanallari"][0]["etkin"])

    def test_gecersiz_degerler(self):
        an = kyc.anahtar(self.veri()["yayincilar"][1])
        for g in ({"etkin": "evet"}, {"ad": ""}, {"ad": "Tolunay Ören"}, {"kisa_ad": "x" * 500}, {"youtube": "x"}, {"youtube": [{"kanal_id": 5}]}):
            with self.assertRaises(kyc.Hata, msg=str(g)):
                kyc.duzenle({"anahtar": an, **g})
        self.assertEqual(self.ayar.read_bytes(), AYAR_METNI.encode("utf-8"))

    def test_degisiklik_yoksa_yazilmaz(self):
        an = kyc.anahtar(self.veri()["yayincilar"][1])
        kyc.duzenle({"anahtar": an, "etkin": True})
        self.assertEqual(self.ayar.read_bytes(), AYAR_METNI.encode("utf-8"))
        self.assertFalse(self.yedek.exists() and list(self.yedek.glob("*")))


class GuvenliYazim(AyarTemel):
    def test_bozuk_dosya_degismez(self):
        self.ayar.write_bytes(b"{ bozuk")
        with self.assertRaises(kyc.Hata):
            self.ekle_kick_hazir()

    def ekle_kick_hazir(self):
        with mock.patch.object(kyc, "_kick_http", kick_yanit()):
            o = kyc.onizle({"kick": "yeniyayinci"}, self.on)
        return kyc.ekle({"jeton": o["jeton"], "ad": "Yeni"}, self.on)

    def test_yazim_dogrulama_basarisizsa_geri_yuklenir(self):
        with mock.patch.object(yk, "ayar_yukle", side_effect=[yk.KlipHatasi("kasıtlı"), ]):
            with self.assertRaises(kyc.Hata):
                self.ekle_kick_hazir_sahte()
        self.assertEqual(self.ayar.read_bytes(), AYAR_METNI.encode("utf-8"))
        self.assertFalse(list(self.kok.glob("*.tmp")))

    def ekle_kick_hazir_sahte(self):
        with mock.patch.object(kyc, "_kick_http", kick_yanit()):
            o = kyc.onizle({"kick": "yeniyayinci"}, self.on)
        return kyc.ekle({"jeton": o["jeton"], "ad": "Yeni"}, self.on)

    def test_yazimdan_sonra_okuma_bozuksa_yedekten_donulur(self):
        gercek = yk.ayar_yukle
        sayac = {"n": 0}

        def f(yol=None):
            sayac["n"] += 1
            if sayac["n"] >= 2:      # 1: geçici dosya, 2: yazılmış asıl dosya
                raise yk.KlipHatasi("kasıtlı")
            return gercek(yol)
        with mock.patch.object(yk, "ayar_yukle", f):
            with self.assertRaisesRegex(kyc.Hata, "yedekten"):
                self.ekle_kick_hazir_sahte()
        self.assertEqual(self.ayar.read_bytes(), AYAR_METNI.encode("utf-8"))

    def test_eszamanli_yazimlar_kaybolmaz(self):
        hatalar = []

        def kick_hepsi(url):   # tek sahte yanıt: kanal adına göre (mock iş parçacıkları arasında paylaşılır)
            slug = url.split("/channels/")[1].split("/")[0]
            return kick_yanit(slug)(url)
        with mock.patch.object(kyc, "_kick_http", kick_hepsi):
            ts = [threading.Thread(target=lambda i=i: self._yaz(i, hatalar)) for i in range(6)]
            [t.start() for t in ts]
            [t.join(30) for t in ts]
        self.assertEqual(hatalar, [])
        self.assertEqual(len(self.veri()["yayincilar"]), 2 + 6)

    def _yaz(self, i, hatalar):
        try:
            o = kyc.onizle({"kick": f"kanal{i}"}, self.on)
            kyc.ekle({"jeton": o["jeton"], "ad": f"Yayıncı{i}"}, self.on)
        except Exception as e:  # noqa: BLE001
            hatalar.append(e)


class BicimlemeGercekDosya(unittest.TestCase):
    """Gerçek ayar dosyasının BİR KOPYASI üzerinde: hiçbir değişiklik yapmadan biçimleme dosyayı byte byte üretir."""

    @unittest.skipUnless(GERCEK_AYAR.exists(), "ayar dosyası yok")
    def test_cevrim_ayni(self):
        metin = GERCEK_AYAR.read_bytes().decode("utf-8")
        veri = json.loads(metin)
        self.assertEqual(kyc.bicimle(veri, metin).replace("\n", "\r\n" if "\r\n" in metin else "\n"), metin)

    @unittest.skipUnless(GERCEK_AYAR.exists(), "ayar dosyası yok")
    def test_gecici_kopyada_ekle_kaldir_geri_getir(self):
        with tempfile.TemporaryDirectory() as t:
            kopya = pathlib.Path(t) / "k.json"
            kopya.write_bytes(GERCEK_AYAR.read_bytes())
            onceki = GERCEK_AYAR.read_bytes()
            with mock.patch.dict(os.environ, {"KLIP_YAYINCILAR": str(kopya), "KLIP_YAYINCI_YEDEK": str(pathlib.Path(t) / "y")}):
                on = kyc.Onizlemeler()
                with mock.patch.object(kyc, "_kick_http", kick_yanit()):
                    o = kyc.onizle({"kick": "yeniyayinci"}, on)
                kyc.ekle({"jeton": o["jeton"], "ad": "Yeni"}, on)
                eklenmis = kopya.read_bytes().decode("utf-8")
                eski_satirlar = onceki.decode("utf-8").splitlines()
                yeni_satirlar = eklenmis.splitlines()
                # yalnız bir satır eklendi (yeni yayıncı, tek satır); diğer her satır aynı sırayla duruyor
                self.assertEqual(len(yeni_satirlar), len(eski_satirlar) + 1)
                kalan = [s for s in yeni_satirlar if '"ad": "Yeni"' not in s]
                self.assertEqual([s.rstrip(",") for s in kalan], [s.rstrip(",") for s in eski_satirlar])
                an = kyc.anahtar(json.loads(eklenmis)["yayincilar"][-1])
                kyc.kaldir({"anahtar": an})
                self.assertNotIn('"ad": "Yeni"', json.loads(json.dumps(kopya.read_text(encoding="utf-8"))).split('"kaldirilanlar"')[0])
                kyc.geri_getir({"anahtar": an})
                self.assertEqual(kopya.read_bytes().decode("utf-8"), eklenmis)    # kaldır + geri getir: byte byte aynı
            self.assertEqual(GERCEK_AYAR.read_bytes(), onceki)                     # gerçek dosyaya dokunulmadı


class SahteIs:
    """CIKAR_KOMUTU için: komut satırını okuyup kısa süren sahte bir "klip çıkar" işi."""

    @staticmethod
    def komut(kod: str):
        return [sys.executable, "-c", kod]


def betik_yaz(kok: pathlib.Path, ad: str, kaynak: str) -> list[str]:
    yol = kok / f"{ad}.py"
    yol.write_text(kaynak, encoding="utf-8")
    return [sys.executable, str(yol)]


class KlipCikarma(AyarTemel):
    def setUp(self):
        super().setUp()
        self.yi = kyc.YayinciIsleri()
        self.addCleanup(self.yi.kapat)
        self.an = kyc.anahtar(self.veri()["yayincilar"][1])

    def komut(self, kaynak):
        k = betik_yaz(self.kok, "sahte", kaynak)
        m = mock.patch.object(kyc, "CIKAR_KOMUTU", k)
        m.start()
        self.addCleanup(m.stop)

    def test_basarili_is_ve_arguman_listesi(self):
        self.komut("import sys,json;print('ARG',json.dumps(sys.argv[1:]),flush=True);print('islem sürüyor',flush=True)")
        s = self.yi.klip_cikar({"anahtar": self.an}, kesim_mesgul=False)
        self.assertTrue(s["ok"])
        self.assertTrue(self.yi.cikar.bekle(20))
        d = self.yi.cikar.goster()
        self.assertEqual(d["durum"], "bitti")
        self.assertEqual(d["yayinci"], "wtcN")
        self.assertEqual(d["son_satir"], "islem sürüyor")
        self.assertIn("yenile", d["mesaj"])

    def test_arguman_icerigi(self):
        cikti = self.kok / "arg.json"
        self.komut(f"import sys,json;open(r'{cikti}','w',encoding='utf-8').write(json.dumps(sys.argv[1:]))")
        self.yi.klip_cikar({"anahtar": self.an}, False)
        self.assertTrue(self.yi.cikar.bekle(20))
        a = json.loads(cikti.read_text(encoding="utf-8"))
        self.assertEqual(a[a.index("otomatik"):], ["otomatik", "--yayinci", "wtcN", "--en-cok", "1", "--konusma"])
        self.assertEqual(a[a.index("--ayar") + 1], str(self.ayar))
        self.assertEqual(a[a.index("--dizin") + 1], str(self.kok / "calisma"))

    def test_hatali_cikis(self):
        self.komut("import sys;print('patladı');sys.exit(3)")
        self.yi.klip_cikar({"anahtar": self.an}, False)
        self.assertTrue(self.yi.cikar.bekle(20))
        d = self.yi.cikar.goster()
        self.assertEqual(d["durum"], "hata")
        self.assertIn("kod 3", d["mesaj"])
        self.assertIn("patladı", d["mesaj"])

    def test_cikti_yoksa_yeni_yayin_yok_mesaji(self):
        self.komut("pass")
        self.yi.klip_cikar({"anahtar": self.an}, False)
        self.assertTrue(self.yi.cikar.bekle(20))
        self.assertIn("yeni yayın bulunamadı", self.yi.cikar.goster()["mesaj"])

    def test_tek_is_ve_iptal(self):
        self.komut("import time;print('basladi',flush=True);time.sleep(60)")
        self.yi.klip_cikar({"anahtar": self.an}, False)
        with self.assertRaisesRegex(kyc.Hata, "Zaten"):
            self.yi.klip_cikar({"anahtar": self.an}, False)
        for _ in range(100):
            if self.yi.cikar.goster().get("son_satir") == "basladi":
                break
            time.sleep(0.05)
        self.assertEqual(self.yi.cikar.goster()["durum"], "calisiyor")
        self.assertTrue(self.yi.calisiyor())
        self.yi.cikar.iptal()
        self.assertTrue(self.yi.cikar.bekle(20))
        self.assertEqual(self.yi.cikar.goster()["durum"], "iptal")
        self.assertFalse(self.yi.calisiyor())
        with self.assertRaises(kyc.Hata):
            self.yi.cikar.iptal()          # çalışan iş yok

    def test_kesim_mesgulken_baslamaz(self):
        self.komut("pass")
        with self.assertRaisesRegex(kyc.Hata, "yeniden kesiliyor"):
            self.yi.klip_cikar({"anahtar": self.an}, True)
        self.assertEqual(self.yi.cikar.goster()["durum"], "yok")

    def test_kapali_veya_olmayan_yayinci(self):
        self.komut("pass")
        kyc.duzenle({"anahtar": self.an, "etkin": False})
        with self.assertRaisesRegex(kyc.Hata, "kapalı"):
            self.yi.klip_cikar({"anahtar": self.an}, False)
        with self.assertRaisesRegex(kyc.Hata, "listede yok"):
            self.yi.klip_cikar({"anahtar": "kick:yok"}, False)
        with self.assertRaises(kyc.Hata):
            self.yi.klip_cikar({"anahtar": 7}, False)

    def test_kapat_calisan_isi_durdurur(self):
        self.komut("import time;time.sleep(60)")
        self.yi.klip_cikar({"anahtar": self.an}, False)
        self.yi.kapat()
        self.assertTrue(self.yi.cikar.bekle(20))
        self.assertFalse(self.yi.calisiyor())

    def test_zaman_asimi(self):
        self.komut("import time;time.sleep(60)")
        with mock.patch.object(kyc, "CIKAR_ZAMAN_ASIMI", 0.3):
            self.yi.klip_cikar({"anahtar": self.an}, False)
            self.assertTrue(self.yi.cikar.bekle(20))
        d = self.yi.cikar.goster()
        self.assertEqual(d["durum"], "hata")
        self.assertIn("durduruldu", d["mesaj"])

    def test_baslatilamayan_komut(self):
        with mock.patch.object(kyc, "CIKAR_KOMUTU", [str(self.kok / "yok.exe")]):
            with self.assertRaisesRegex(kyc.Hata, "başlatılamadı"):
                self.yi.klip_cikar({"anahtar": self.an}, False)
        self.assertFalse(self.yi.calisiyor())


class PanelRotalari(KlipYayinTemel, AyarTemel):
    """Gerçek sunucu (geçici kapı). Yayıncı uçları: belirteç, Origin, Host, gövde sınırı ve uçtan uca akış."""

    def setUp(self):
        AyarTemel.setUp(self)
        KlipYayinTemel.setUp(self)
        self.paket_yaz()
        self.sunucu = ky.sunucu_baslat(0, str(self.manifest))
        self.port = self.sunucu.port
        self.is_parcasi = threading.Thread(target=self.sunucu.serve_forever, daemon=True)
        self.is_parcasi.start()
        self.addCleanup(self._kapat)

    def _kapat(self):
        self.sunucu.shutdown()
        self.sunucu.server_close()
        self.is_parcasi.join(5)

    istek = SayfaSunucusu.istek

    def post(self, ad, govde, **k):
        s, _b, g = self.istek("POST", f"/api/yayinci/{ad}", govde, **k)
        return s, json.loads(g.decode("utf-8"))

    def al(self, ad, **k):
        s, _b, g = self.istek("GET", f"/api/yayinci/{ad}", **k)
        return s, g

    def test_sayfa_sekmeleri_ve_betik(self):
        s, b, g = self.istek("GET", "/")
        h = g.decode("utf-8")
        self.assertEqual(s, 200)
        for parca in ("data-sekme=klipler", "data-sekme=yayincilar", "id=sekme-yayincilar", "id=sekme-klipler", "/api/yayinci/onizle"):
            self.assertIn(parca, h)
        self.assertIn("script-src 'unsafe-inline'", b["Content-Security-Policy"])

    def test_liste_belirtec_ister(self):
        self.assertEqual(self.al("liste", belirtec=False)[0], 403)
        self.assertEqual(self.al("liste", belirtec="yanlis")[0], 403)
        self.assertEqual(self.al("liste", host="evil.com")[0], 403)
        s, g = self.al("liste")
        v = json.loads(g)
        self.assertEqual((s, v["ok"], [y["ad"] for y in v["yayincilar"]]), (200, True, ["Tolunay Ören", "wtcN"]))

    def test_post_koruma(self):
        g = {"anahtar": "kick:wtcn"}
        self.assertEqual(self.post("kaldir", g, belirtec=False)[0], 403)
        self.assertEqual(self.post("kaldir", g, origin=False)[0], 403)
        self.assertEqual(self.post("kaldir", g, origin="http://evil.com")[0], 403)
        self.assertEqual(self.post("kaldir", g, host="evil.com")[0], 403)
        self.assertEqual(self.post("bilinmeyen", g)[0], 404)
        s, _b, _g = self.istek("POST", "/api/yayinci/kaldir", ham=b"{}", baslik={"Content-Type": "text/plain"})
        self.assertEqual(s, 415)
        self.assertEqual(self.istek("POST", "/api/yayinci/kaldir", ham=b"x" * 9000, baslik={"Content-Type": "application/json"})[0], 400)
        self.assertEqual(self.istek("POST", "/api/yayinci/kaldir", ham=b"{bozuk", baslik={"Content-Type": "application/json"})[0], 400)
        self.assertEqual(self.istek("POST", "/api/yayinci/kaldir", ham=b"[1]", baslik={"Content-Type": "application/json"})[0], 400)
        self.assertEqual(self.ayar.read_bytes(), AYAR_METNI.encode("utf-8"))

    def test_uctan_uca_ekle_kaldir_geri_getir(self):
        with mock.patch.object(kyc, "_kick_http", kick_yanit()):
            s, o = self.post("onizle", {"kick": "kick.com/YeniYayinci"})
        self.assertEqual(s, 200)
        self.assertEqual(o["kart"]["ad"], "YeniYayıncı")
        s, e = self.post("ekle", {"jeton": o["jeton"], "ad": "YeniYayıncı", "kisa_ad": ""})
        self.assertEqual((s, e["ok"]), (200, True))
        s, g = self.al("liste")
        liste = json.loads(g)["yayincilar"]
        self.assertEqual(liste[-1]["ad"], "YeniYayıncı")
        self.assertEqual(liste[-1]["klip_sayisi"], 0)
        an = liste[-1]["anahtar"]
        self.assertEqual(self.post("duzenle", {"anahtar": an, "etkin": False})[0], 200)
        self.assertEqual(self.post("kaldir", {"anahtar": an})[0], 200)
        k = json.loads(self.al("liste")[1])
        self.assertEqual([y["ad"] for y in k["kaldirilanlar"]], ["YeniYayıncı"])
        self.assertEqual(self.post("geri-getir", {"anahtar": an})[0], 200)
        self.assertEqual(json.loads(self.al("liste")[1])["yayincilar"][-1]["ad"], "YeniYayıncı")

    def test_dogrulama_hatalari_422(self):
        s, v = self.post("onizle", {"kick": "", "youtube": ""})
        self.assertEqual(s, 422)
        self.assertIn("en az biri", v["mesaj"])
        s, v = self.post("onizle", {"kick": "evil.com/x"})
        self.assertEqual(s, 422)
        s, v = self.post("ekle", {"jeton": "yok", "ad": "A"})
        self.assertEqual(s, 422)

    def test_klip_sayisi_paketlerden(self):
        """KlipYayinTemel.paket_yaz paketi "Eraycan" yayıncısına aittir; listede yoksa sayı sıfır, ayarda varsa sayılır."""
        v = self.veri()
        v["yayincilar"].append({"ad": "Eraycan", "kisa_ad": "Eray", "platform": "kick", "kanal": "eray", "etkin": True})
        self.ayar.write_bytes(kyc.bicimle(v, AYAR_METNI).replace("\n", "\r\n").encode("utf-8"))
        s, g = self.al("liste")
        e = next(y for y in json.loads(g)["yayincilar"] if y["ad"] == "Eraycan")
        self.assertEqual(e["klip_sayisi"], 1)

    def test_klip_cikar_ve_durum_ve_kesimle_cakisma(self):
        k = betik_yaz(self.kok, "sahte", "import time;print('çalışıyor',flush=True);time.sleep(30)")
        an = kyc.anahtar(self.veri()["yayincilar"][1])
        with mock.patch.object(kyc, "CIKAR_KOMUTU", k):
            s, v = self.post("klip-cikar", {"anahtar": an})
            self.assertEqual((s, v["ok"]), (200, True))
            s, v = self.post("klip-cikar", {"anahtar": an})
            self.assertEqual(s, 422)                     # aynı anda tek iş
            for _ in range(100):
                d = json.loads(self.al("is")[1])
                if d.get("son_satir"):
                    break
                time.sleep(0.05)
            self.assertEqual((d["durum"], d["yayinci"], d["son_satir"]), ("calisiyor", "wtcN", "çalışıyor"))
            self.assertEqual(self.al("is", belirtec=False)[0], 403)
            # klip çıkarma sürerken yeniden kesim sıraya girmez
            o = next(x for x in ky.tara(yk.calisma_dizini(), ky.ayar_oku()))
            with self.assertRaisesRegex(ky.Hata, "klip çıkarma"):
                self.sunucu.kesim.ekle({**o, "no": "1"}, ["x"], {})
            self.assertEqual(self.post("iptal", {})[0], 200)
            self.assertTrue(self.sunucu.yayinci.cikar.bekle(20))
        d = json.loads(self.al("is")[1])
        self.assertEqual(d["durum"], "iptal")

    def test_kesim_sirasinda_klip_cikar_reddedilir(self):
        an = kyc.anahtar(self.veri()["yayincilar"][1])
        with mock.patch.object(self.sunucu.kesim, "mesgul", return_value=True):
            s, v = self.post("klip-cikar", {"anahtar": an})
        self.assertEqual(s, 422)
        self.assertIn("yeniden kesiliyor", v["mesaj"])

    def test_sunucu_kapaninca_is_durur(self):
        k = betik_yaz(self.kok, "sahte", "import time;time.sleep(60)")
        an = kyc.anahtar(self.veri()["yayincilar"][1])
        with mock.patch.object(kyc, "CIKAR_KOMUTU", k):
            self.assertEqual(self.post("klip-cikar", {"anahtar": an})[0], 200)
            self.assertTrue(self.sunucu.yayinci.calisiyor())
            self.sunucu.shutdown()
            self.sunucu.server_close()
            self.assertTrue(self.sunucu.yayinci.cikar.bekle(20))
        # _kapat tekrar çağrılır: ikinci kapatma zararsız olmalı
        self.sunucu.yayinci.kapat()


class BetikGuvenligi(unittest.TestCase):
    """Sunucudan gelen değerler sayfaya HTML olarak eklenmez."""

    def test_betikte_innerhtml_yok(self):
        import klip_yayinci_ui as yui
        for yasak in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function"):
            self.assertNotIn(yasak, yui.BETIK)

    def test_betik_govde_olusmadan_calismaz(self):
        """Betik <head> içinde yüklenir; gövdeyi beklemezse düğmeler hiç bağlanmaz (gerçek arıza)."""
        import klip_yayinci_ui as yui
        self.assertIn("document.readyState==='loading'", yui.BETIK)
        self.assertIn("addEventListener('DOMContentLoaded',basla)", yui.BETIK)

    def test_bolum_ve_sekmeler_sabit(self):
        import klip_yayinci_ui as yui
        self.assertIn("kapanırsa", yui.BOLUM)
        self.assertIn("id=y-kontrol", yui.BOLUM)


if __name__ == "__main__":
    unittest.main()
