import json
import pathlib
import sys
import tempfile
import unittest

KOK = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK / "tools"))
import ses_ornek as so  # noqa: E402


class SesOrnekTests(unittest.TestCase):
    def test_ornek_metinler_yedi_dili_kapsar(self):
        beklenen_diller = {"tr", "en", "es", "fr", "de", "nl", "zh"}
        self.assertEqual(set(so.ORNEK_METINLER.keys()), beklenen_diller)
        for dil, metin in so.ORNEK_METINLER.items():
            self.assertTrue(len(metin.strip()) > 30, f"{dil} metni çok kısa")
            # En az bir sayı ve tarih/oyun ipucu kontrolü
            self.assertTrue(any(c.isdigit() for c in metin), f"{dil} metninde sayı yok")

    def test_guvenli_dosya_adi(self):
        self.assertEqual(
            so.dosya_adi("tr", "tr-TR-Aydin:MAI-Voice-2.1"),
            "ses-ornek-tr-tr-TR-Aydin-MAI-Voice-2.1.mp3",
        )
        self.assertEqual(
            so.dosya_adi("en", "en-US-BrianNeural"),
            "ses-ornek-en-en-US-BrianNeural.mp3",
        )
        self.assertEqual(
            so.dosya_adi("es", "es-ES-Alvaro Neural/Test"),
            "ses-ornek-es-es-ES-Alvaro-Neural-Test.mp3",
        )

    def test_ses_listesi_suzgeci(self):
        sahte_kayitlar = [
            {"ShortName": "tr-TR-Aydin:MAI-Voice-2.1", "Locale": "tr-TR", "Gender": "Male", "VoiceType": "Neural"},
            {"ShortName": "tr-TR-EmelNeural", "Locale": "tr-TR", "Gender": "Female", "VoiceType": "Neural"},
            {"ShortName": "en-US-AndrewNeural", "Locale": "en-US", "Gender": "Male", "VoiceType": "Neural"},
            {"ShortName": "en-GB-RyanNeural", "Locale": "en-GB", "Gender": "Male", "VoiceType": "Neural"},
            {"ShortName": "en-CA-ClaraNeural", "Locale": "en-CA", "Gender": "Female", "VoiceType": "Neural"},
            {"ShortName": "es-ES-AlvaroNeural", "Locale": "es-ES", "Gender": "Male", "VoiceType": "Neural"},
            {"ShortName": "es-MX-JorgeNeural", "Locale": "es-MX", "Gender": "Male", "VoiceType": "Neural"},
            {"ShortName": "es-AR-TomasNeural", "Locale": "es-AR", "Gender": "Male", "VoiceType": "Neural"},
            {"ShortName": "fr-FR-RemyMultilingualNeural", "Locale": "fr-FR", "Gender": "Male", "VoiceType": "Neural"},
            {"ShortName": "de-DE-ChristophNeural", "Locale": "de-DE", "Gender": "Male", "VoiceType": "Neural"},
            {"ShortName": "nl-NL-MaartenNeural", "Locale": "nl-NL", "Gender": "Male", "VoiceType": "Neural"},
            {"ShortName": "zh-CN-YunxiNeural", "Locale": "zh-CN", "Gender": "Male", "VoiceType": "Neural"},
            {"ShortName": "ja-JP-NanamiNeural", "Locale": "ja-JP", "Gender": "Female", "VoiceType": "Neural"},
            {"ShortName": "en-US-JennyHDLatestNeural", "Locale": "en-US", "Gender": "Female", "VoiceType": "Neural"},
            {"ShortName": "en-US-DragonNeural", "Locale": "en-US", "Gender": "Male", "VoiceType": "Neural"},
            {"ShortName": "en-US-TurboNeural", "Locale": "en-US", "Gender": "Male", "VoiceType": "Neural"},
        ]

        secilen, dogal = so.sesleri_sec(sahte_kayitlar, ["tr", "en", "es", "fr", "de", "nl", "zh"])

        secilen_adlar = [k["ShortName"] for k in secilen]
        dogal_adlar = [k["ShortName"] for k in dogal]

        # Kabul edilen diller ve yereller listede olmalı
        self.assertIn("tr-TR-Aydin:MAI-Voice-2.1", secilen_adlar)
        self.assertIn("tr-TR-EmelNeural", secilen_adlar)
        self.assertIn("en-US-AndrewNeural", secilen_adlar)
        self.assertIn("en-GB-RyanNeural", secilen_adlar)
        self.assertIn("es-ES-AlvaroNeural", secilen_adlar)
        self.assertIn("es-MX-JorgeNeural", secilen_adlar)
        self.assertIn("fr-FR-RemyMultilingualNeural", secilen_adlar)
        self.assertIn("de-DE-ChristophNeural", secilen_adlar)
        self.assertIn("nl-NL-MaartenNeural", secilen_adlar)
        self.assertIn("zh-CN-YunxiNeural", secilen_adlar)

        # Filtrelenmesi gereken yereller elenmeli
        self.assertNotIn("en-CA-ClaraNeural", secilen_adlar)
        self.assertNotIn("es-AR-TomasNeural", secilen_adlar)
        self.assertNotIn("ja-JP-NanamiNeural", secilen_adlar)

        # Doğal adaylar (MAI, HD, Dragon, Multilingual, Turbo)
        self.assertIn("tr-TR-Aydin:MAI-Voice-2.1", dogal_adlar)
        self.assertIn("fr-FR-RemyMultilingualNeural", dogal_adlar)
        self.assertIn("en-US-JennyHDLatestNeural", dogal_adlar)
        self.assertIn("en-US-DragonNeural", dogal_adlar)
        self.assertIn("en-US-TurboNeural", dogal_adlar)
        self.assertNotIn("tr-TR-EmelNeural", dogal_adlar)

    def test_satir_bicimlendirme(self):
        kayit = {
            "ShortName": "tr-TR-Aydin:MAI-Voice-2.1",
            "Gender": "Male",
            "VoiceType": "Neural",
            "WordsPerMinute": "150",
            "VoiceTag": {"VoicePersonalities": ["Friendly", "Positive"]},
        }
        cikti = so.satir(kayit)
        self.assertIn("tr-TR-Aydin:MAI-Voice-2.1", cikti)
        self.assertIn("Male", cikti)
        self.assertIn("Neural", cikti)
        self.assertIn("150 kelime/dk", cikti)
        self.assertIn("Friendly,Positive", cikti)

    def test_ornekle_bir_sesin_hatasi_digerlerini_durdurmaz(self):
        ciktilar = []

        def sahte_sentez(ses, dil, metin, klasor):
            if "hata" in ses:
                raise RuntimeError("sentez patladı")
            return pathlib.Path(klasor) / f"{ses}.mp3"

        sesler = ["tr-TR-Ses1Neural", "tr-TR-hata-ses", "tr-TR-Ses2Neural"]
        yollar, hatalar = so.ornekle(
            sesler,
            "tr",
            pathlib.Path("/tmp/test"),
            sentez=sahte_sentez,
            cikti=ciktilar.append,
        )

        self.assertEqual(len(yollar), 2)
        self.assertEqual(len(hatalar), 1)
        self.assertIn("tr-TR-hata-ses", hatalar[0])
        self.assertEqual(yollar[0].name, "tr-TR-Ses1Neural.mp3")
        self.assertEqual(yollar[1].name, "tr-TR-Ses2Neural.mp3")

    def test_deneme_her_kaydi_ayri_seslendirir(self):
        import json
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as g:
            dosya = Path(g) / 'deneme.json'
            dosya.write_text(json.dumps([{'ad': 'tr-a', 'ses': 'tr-TR-EmelNeural', 'metin': 'Merhaba.'},
                                         {'ad': 'Kötü Ad', 'ses': 'tr-TR-EmelNeural', 'metin': 'Merhaba.'},
                                         {'ad': 'tr-b', 'ses': 'tr-TR-EmelNeural', 'metin': ''}]), encoding='utf-8')
            cagri, satirlar = [], []
            kod = so.deneme(dosya, Path(g), sentez=lambda ses, metin, yol: cagri.append((ses, metin, yol.name)),
                            cikti=satirlar.append)
        self.assertEqual(kod, 1)
        self.assertEqual(cagri, [('tr-TR-EmelNeural', 'Merhaba.', 'deneme-tr-a.mp3')])
        self.assertEqual([x.split(':')[0] for x in satirlar], ['tamam', 'HATA', 'HATA'])

    def test_ornekle_dil_uyusmazligi_hata_olarak_kaydedilir(self):
        ciktilar = []

        def sahte_sentez(ses, dil, metin, klasor):
            return pathlib.Path(klasor) / f"{ses}.mp3"

        yollar, hatalar = so.ornekle(
            ["en-US-BrianNeural"],
            "tr",
            pathlib.Path("/tmp/test"),
            sentez=sahte_sentez,
            cikti=ciktilar.append,
        )
        self.assertEqual(len(yollar), 0)
        self.assertEqual(len(hatalar), 1)
        self.assertIn("en-US-BrianNeural", hatalar[0])

    def test_liste_komutu_dosyaya_yazar(self):
        sahte_kayitlar = [
            {"ShortName": "tr-TR-Aydin:MAI-Voice-2.1", "Locale": "tr-TR", "Gender": "Male"},
            {"ShortName": "tr-TR-EmelNeural", "Locale": "tr-TR", "Gender": "Female"},
        ]
        with tempfile.TemporaryDirectory() as td:
            cikti_dosyasi = pathlib.Path(td) / "ses-listesi.json"
            sonuc = so.liste(["tr"], cikti_yolu=cikti_dosyasi, kayitlar=sahte_kayitlar)
            self.assertEqual(sonuc, 0)
            self.assertTrue(cikti_dosyasi.exists())
            veri = json.loads(cikti_dosyasi.read_text(encoding="utf-8"))
            self.assertEqual(veri["diller"], ["tr"])
            self.assertEqual(len(veri["sesler"]), 2)
            self.assertEqual(len(veri["dogal_adaylar"]), 1)


if __name__ == "__main__":
    unittest.main()
