import copy
import json
import pathlib
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import sosyal_kuyruk as sk
import sosyal_yayinla as sy

SIMDI = datetime(2026, 11, 16, 13, tzinfo=timezone.utc)


def haber(oid="yeni", gun="2026-11-16", tur="guncelleme", hype=5):
    return {"id": oid, "tarih": gun, "tur": tur, "oyun": "Test Game",
            "otomasyon": {"hype": hype}, "kaynaklar": [{"ad": "Studio", "url": "https://example.com"}],
            "diller": {d: {"baslik": "Test patch", "ozet": "Fixes for saves.", "metin": "Details.", "etiketler": []} for d in sk.DILLER}}


class YasakAg:
    def __getattr__(self, ad):
        raise AssertionError("Ağ kullanılmamalı: " + ad)


class KuyrukTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.kok = pathlib.Path(self.tmp.name)
        self.ayar = {"turler": {t: True for t in sk.TURLER}, "hesaplar": {d: {"instagram": True} for d in sk.DILLER},
                     "gunluk_en_fazla": {"instagram": 24}, "calisma_basina_en_fazla": 1}
        self.yaz("takvim.json", [{"id": "test", "oyun": "Test Game", "tarih": "2026-11-19", "kesin": True,
                                  "platform": ["PC"], "kaynak": {"ad": "Studio", "url": "https://example.com"}}])
        self.yaz("indirimler.json", {"guncel": "2026-11-16T12:00:00Z", "magazalar": [{"id": "1", "ad": "Steam"}],
                                    "firsatlar": [self.firsat("az", 25), self.firsat("cok", 90)]})
        self.yaz("ucretsiz.json", {"guncel": "2026-11-16T12:00:00Z", "epic": [
            {"slug": "free", "baslik": "Free Game", "baslangic": "2026-11-12T16:00:00Z", "bitis": "2026-11-19T16:00:00Z"}]})
        self.yaz("oyunlar.json", [{"id": "test", "ad": "Test Game"}])
        self.yaz("rehber/test.json", {"oyun": "test", "kaynaklar": [], "diller": {
            d: {"baslik": "Guide", "ozet": "A beginner guide.", "bolumler": [1]} for d in sk.DILLER}})

    def yaz(self, ad, v):
        yol = self.kok / "data" / ad
        yol.parent.mkdir(parents=True, exist_ok=True)
        yol.write_text(json.dumps(v, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def firsat(oid, savings):
        return {"dealID": oid, "title": oid, "savings": savings, "salePrice": 1, "normalPrice": 10, "storeID": "1"}

    def adaylar(self, veri=None, simdi=SIMDI):
        return sk.adaylar(veri if veri is not None else [haber(), haber("eski", "2026-11-10")],
                          self.kok, self.ayar, simdi.date(), simdi)

    def tur(self, tur):
        return next(x for x in self.adaylar() if x["sosyal_tur"] == tur)

    def sec(self, adaylar, kayit, simdi=SIMDI, tum=None):
        secilen = []
        sy.calistir(self.ayar, [], kayit_yolu=self.kok / "sosyal/gonderilenler.json", manifest_yolu=self.kok / "manifest.json",
                    tum=tum if tum is not None else {"IG_TR_USER_ID": "test", "IG_TR_TOKEN": "fake"},
                    ag=YasakAg(), dry_run=True, bugun=simdi.date(), simdi=simdi, kuyruk=adaylar, bellek=kayit,
                    secildi=lambda k, r: secilen.append(r), cikti=lambda *_: None)
        return secilen

    def test_oncelik_ve_indirim_sirasi(self):
        adaylar = self.adaylar()
        self.assertEqual([x["sosyal_tur"] for x in adaylar], ["haber", "takvim", "firsat", "firsat", "ucretsiz", "rehber", "arsiv"])
        self.assertEqual(adaylar[2]["oyun"], "cok")
        # Her öncelik düzeyini gerçekten yayın seçicisinden geçir.
        for i, tur in ((0, "haber"), (1, "takvim"), (2, "firsat"), (4, "ucretsiz"), (5, "rehber"), (6, "arsiv")):
            self.assertEqual(self.sec(adaylar[i:], {})[0]["sosyal_tur"], tur)

    def test_gta_cikis_haftasi_her_gun_bir_gta_gonderisi(self):
        self.yaz("takvim.json", [{"id": "gta-vi", "oyun": "Grand Theft Auto VI", "tarih": "2026-11-19", "kesin": True,
                                  "platform": ["PS5"], "kaynak": {"ad": "Rockstar", "url": "https://example.com"}}])
        diger = haber("baska-haber", "2026-11-16")
        for gun in (5, 2):  # 14 Kasım yok: 2 gün kala takvim kartı kural dışı gün olsa bile çıkar
            simdi = datetime(2026, 11, 19 - gun, 13, tzinfo=timezone.utc)
            adaylar = sk.adaylar([diger], self.kok, self.ayar, simdi.date(), simdi)
            takvim = [x for x in adaylar if x["sosyal_tur"] == "takvim"]
            self.assertEqual(len(takvim), 1)
            self.assertTrue(takvim[0]["gta_oncelik"])
            ilk = sk.oncelikli(adaylar, "tr", "instagram", {}, simdi)[0]
            self.assertEqual(ilk["id"], takvim[0]["id"])  # GTA kartı haberin önüne geçer
            kayit = {f"{takvim[0]['sosyal_anahtar']}|tr|instagram|gorsel": {
                "id": takvim[0]["id"], "durum": "tamam", "zaman": simdi.isoformat()}}
            self.assertEqual(sk.oncelikli(adaylar, "tr", "instagram", kayit, simdi), adaylar)  # bugün bir GTA var: sıra normal
        # Günlük sınır aşılmaz: hak yoksa hiçbir şey seçilmez.
        self.ayar["gunluk_en_fazla"] = {"instagram": 1}
        kayit = {"x|tr|instagram|gorsel": {"id": "x", "durum": "tamam", "zaman": simdi.isoformat()}}
        self.assertEqual(self.sec(adaylar, kayit, simdi), [])
        # Çıkıştan 8+ gün önce kural kapalı.
        erken = datetime(2026, 11, 10, 13, tzinfo=timezone.utc)
        self.assertFalse(any(x.get("gta_oncelik") for x in sk.adaylar([diger], self.kok, self.ayar, erken.date(), erken)))

    def test_kilometre_tasi_bir_kez_ve_sonraki_tas_ayri(self):
        x = self.tur("takvim")
        kayit = {}
        self.assertEqual(len(self.sec([x], kayit)), 1)
        self.assertEqual(self.sec([x], kayit, SIMDI + timedelta(hours=1)), [])
        sonraki = SIMDI + timedelta(days=2)
        yeni = next(x for x in self.adaylar([], sonraki) if x["sosyal_tur"] == "takvim")
        self.assertNotEqual(sy.anahtar(x, "tr", "instagram", "gorsel"), sy.anahtar(yeni, "tr", "instagram", "gorsel"))
        # Araya farklı tür girince sonraki kilometre taşı seçilir.
        self.sec([self.tur("rehber")], kayit, SIMDI + timedelta(days=1))
        self.assertEqual(len(self.sec([yeni], kayit, sonraki)), 1)

    def test_butun_kilometre_taslari_ve_belirsiz_tarih(self):
        for gun in (30, 14, 7, 3, 1, 0, 2, -1):
            tarih = datetime(2026, 11, 19, 13, tzinfo=timezone.utc) - timedelta(days=gun)
            self.assertEqual(any(x["sosyal_tur"] == "takvim" for x in self.adaylar([], tarih)), gun in (30, 14, 7, 3, 1, 0))

    def test_ayni_tur_art_arda_yok_haber_serbest(self):
        kayit = {}
        firsat = [x for x in self.adaylar() if x["sosyal_tur"] == "firsat"]
        self.sec(firsat, kayit)
        self.assertEqual(self.sec(firsat, kayit, SIMDI + timedelta(hours=1)), [])
        self.assertEqual(self.sec([self.tur("rehber")], kayit, SIMDI + timedelta(hours=2))[0]["sosyal_tur"], "rehber")
        self.assertEqual(self.sec(firsat, kayit, SIMDI + timedelta(hours=3))[0]["sosyal_tur"], "firsat")
        self.assertEqual(len(self.sec([haber("a")], kayit, SIMDI + timedelta(hours=4))), 1)
        self.assertEqual(len(self.sec([haber("b")], kayit, SIMDI + timedelta(hours=5))), 1)

    def test_rehber_14_gun_kayan_pencere(self):
        kayit = {}
        self.sec([self.tur("rehber")], kayit)
        self.sec([haber()], kayit, SIMDI + timedelta(hours=1))
        for gun, adet in ((13, 0), (14, 1)):
            simdi = SIMDI + timedelta(days=gun)
            self.assertEqual(len(self.sec([x for x in self.adaylar([], simdi) if x["sosyal_tur"] == "rehber"], kayit, simdi)), adet)

    def test_arsiv_soylenti_kampanya_ve_etkinlik_atlanir(self):
        veri = [haber("rumor", "2026-11-01", "soylenti", 10), haber("sale", "2026-11-01", "indirim", 10),
                haber("event", "2026-11-01", "guncelleme", 10), haber("safe-low", "2026-11-01", hype=5),
                haber("safe-high", "2026-11-01", hype=8)]
        veri[2]["diller"]["en"]["metin"] = "A limited-time event."
        self.assertEqual([x["id"] for x in self.adaylar(veri)], ["takvim-test-2026-11-19-3", sk.kimlik("firsat", "cok"),
                         sk.kimlik("firsat", "az"), self.tur("ucretsiz")["id"], "rehber-test", "safe-high", "safe-low"])

    def test_arsiv_fresh_konu_anahtarini_korur(self):
        x = haber("eski", "2026-11-01")
        x["otomasyon"]["konu"] = "ortak-konu"
        aday = next(x for x in self.adaylar([x]) if x["sosyal_tur"] == "arsiv")
        kayit = {"ortak-konu|tr|instagram|gorsel": {"durum": "tamam", "zaman": "2026-11-01"}}
        self.assertEqual(self.sec([aday], kayit), [])

    def test_arsiv_platformda_baska_bicimde_paylasilmis_haberi_atlar(self):
        x = self.tur('arsiv')
        kayit = {sy.anahtar(x, 'tr', 'instagram', 'reel'): {'id': x['id'], 'durum': 'tamam',
                                                          'zaman': '2026-11-01', 'sosyal_tur': 'haber'}}
        self.assertEqual(self.sec([x], kayit), [])

    def test_emojiler_ve_uzun_ozet_adres_ve_etiketleri_itmez(self):
        x = haber()
        x['diller']['tr'].update(baslik='🎮🚀 Haber', ozet='🎮🚀 ' * 2000)
        ig = sy.ig_aciklama('tr', x)
        self.assertNotIn('🎮', ig)
        self.assertNotIn('🚀', ig)
        self.assertLessEqual(len(ig), 2200)
        self.assertIn(sy.sayfa_adresi('tr', x), ig)
        self.assertIn('#Oyun', ig)

    def test_suresi_gecmis_ve_bayat_firsat_atlanir(self):
        f = self.firsat("expired", 99)
        f["bitis"] = "2026-11-15T12:00:00Z"
        self.yaz("indirimler.json", {"guncel": SIMDI.isoformat(), "firsatlar": [f]})
        self.assertFalse(any(x["sosyal_tur"] == "firsat" for x in self.adaylar()))
        self.assertFalse(any(x["sosyal_tur"] == "firsat" for x in self.adaylar([], SIMDI + timedelta(days=2))))

    def test_ucretsiz_kampanya_sinirlari_ve_anahtari(self):
        x = self.tur("ucretsiz")
        kayit = {}
        self.sec([x], kayit)
        self.sec([haber()], kayit, SIMDI + timedelta(hours=1))
        self.assertEqual(self.sec([x], kayit, SIMDI + timedelta(hours=2)), [])
        self.assertFalse(any(x["sosyal_tur"] == "ucretsiz" for x in self.adaylar([], SIMDI + timedelta(days=4))))

    def test_gunluk_sinir_ve_gece_yarisi(self):
        kayit = {}
        self.ayar["gunluk_en_fazla"]["instagram"] = 1
        self.assertEqual(len(self.sec([haber("a")], kayit)), 1)
        self.assertEqual(self.sec([haber("b")], kayit, SIMDI + timedelta(hours=1)), [])
        self.assertEqual(len(self.sec([haber("b")], kayit, SIMDI + timedelta(days=1))), 1)

    def test_dil_anahtarsizsa_secim_ve_ag_yok(self):
        self.assertEqual(self.sec(self.adaylar(), {}, tum={}), [])
        kayit = {}
        self.sec(self.adaylar(), kayit)
        self.assertEqual({r["dil"] for r in kayit.values()}, {"tr"})

    def test_tur_anahtari_kapatir_gelecek_haber_yok(self):
        self.ayar["turler"]["firsat"] = False
        self.assertFalse(any(x["sosyal_tur"] in ("firsat", "haber") for x in self.adaylar([haber(gun="2027-01-01")])))

    def test_metinde_dort_dil_tam_adres_ve_etiketler(self):
        for x in self.adaylar():
            for d in sk.DILLER:
                m = sy.ig_aciklama(d, x)
                self.assertIn(sy.sayfa_adresi(d, x), m)
                self.assertTrue(3 <= len(sy.etiketler(d, x)) <= 5)
                if x["sosyal_tur"] == "arsiv":
                    self.assertIn(sk.SABLON[d]["arsiv"], m)

    def test_her_platform_bir_kez_buyuk_calisma_kotasi_bile(self):
        self.ayar["calisma_basina_en_fazla"] = 100
        self.assertEqual(len(self.sec([haber("a"), haber("b")], {})), 1)

    def test_benzetim_24_saat_kaydi_ve_agi_degistirmez(self):
        # Gerçek seçiciye 24 farklı haber ver; hiçbir ortam sırrı okunmamalı.
        from unittest.mock import patch
        once = {p: p.read_bytes() for p in self.kok.rglob('*.json')}
        self.ayar['turler'] = {t: t == 'haber' for t in sk.TURLER}
        veri = [haber(f'h-{i:02d}') for i in range(24)]
        kayit = {}
        with patch.object(sy, 'sirlari_oku', side_effect=AssertionError('Sır okundu')):
            secimler = sy.benzet(self.ayar, veri, kayit, self.kok / 'manifest.json', SIMDI, 24,
                                kok=self.kok, cikti=lambda *_: None)
        self.assertEqual(len(secimler), 24)
        self.assertEqual(len({r['saat'] for r in secimler}), 24)
        self.assertEqual(len({r['anahtar'] for r in secimler}), 24)
        self.assertEqual(kayit, {})
        self.assertEqual(once, {p: p.read_bytes() for p in self.kok.rglob('*.json')})

    def test_instagram_reel_ve_gorsel_ayni_calismada_yok(self):
        self.ayar['hesaplar']['tr']['instagram_reel'] = True
        self.ayar['video'] = {'hype_esigi': 5}
        manifest = {'surum': 1, 'taban': 'https://example.com/', 'videolar': {'yeni': {'tr': {
            'anahtar': 'k', 'sure': 30, 'mp4_1080': 'a.mp4', 'mp4_720': 'b.mp4', 'mp4_540': 'c.mp4',
            'kapak': 'a.jpg', 'vtt': 'a.vtt', 'uretildi': SIMDI.isoformat(), 'onay': True}}}}
        (self.kok / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        kayit = {}
        secim = self.sec(self.adaylar(), kayit)
        self.assertEqual(len(secim), 1)
        self.assertEqual(secim[0]['bicim'], 'reel')

    def test_utf8_cli_windows_konsol_ayarindan_bagimsiz(self):
        env = os.environ.copy()
        env.pop('PYTHONIOENCODING', None)
        env.pop('PYTHONUTF8', None)
        kok = pathlib.Path(__file__).resolve().parents[1]
        for ad in ('sosyal_yayinla', 'sosyal_derle', 'video_geri_doldur', 'haber_oto'):
            r = subprocess.run([sys.executable, str(kok / f'tools/{ad}.py'), '--help'],
                               capture_output=True, env=env, timeout=15)
            self.assertEqual(r.returncode, 0)
            self.assertIn('usage:', r.stdout.decode('utf-8'))


if __name__ == "__main__":
    unittest.main()
