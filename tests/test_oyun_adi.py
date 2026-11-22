import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import oyun_adi as oa  # noqa: E402

TAKMA = {"counterstrike2": ["Counter-Strike 2", "CS2"], "gtavi": ["GTA VI", "Grand Theft Auto VI", "GTA 6"]}


class OyunAdi(unittest.TestCase):
    def test_baslikta_oyun_adi_gecer(self):
        self.assertTrue(oa.gecer("World of Warships'e Avrupa kruvazörleri geldi", "World of Warships"))
        self.assertTrue(oa.gecer("CS2'ye Cobblestone eklendi", "Counter-Strike 2", TAKMA))
        self.assertTrue(oa.gecer("Grand Theft Auto VI resmen çıktı", "GTA VI", TAKMA))
        self.assertTrue(oa.gecer("ARK'ta Turkey Trial etkinliği başlıyor", "ARK: Survival Ascended"))
        self.assertTrue(oa.gecer("Zelda: Ocarina of Time kartları", "The Legend of Zelda: Ocarina of Time"))

    def test_oyun_adi_gecmeyen_baslik(self):
        self.assertFalse(oa.gecer("Yeni güncelleme görev ve görüntü hatalarını düzeltiyor", "The Seven Deadly Sins: Origin"))
        self.assertFalse(oa.gecer("Avrupa kruvazörleri erken erişimde", "World of Warships"))
        self.assertFalse(oa.gecer("Singapur 2026 Major eşyaları satışta", "Counter-Strike 2", TAKMA))

    def test_oyunlu_baslik_one_ekler(self):
        self.assertEqual(oa.oyunlu_baslik("Avrupa kruvazörleri erken erişimde", "World of Warships"),
                         "World of Warships: Avrupa kruvazörleri erken erişimde")
        self.assertEqual(oa.oyunlu_baslik("Knockout genişlemesi yayında", "Deep Rock Galactic: Survivor"),
                         "Deep Rock Galactic: Survivor — Knockout genişlemesi yayında")
        self.assertEqual(oa.oyunlu_baslik("CS2'ye Cobblestone eklendi", "Counter-Strike 2", TAKMA), "CS2'ye Cobblestone eklendi")

    def test_latin_disi_ad(self):
        self.assertFalse(oa.latin_mi("七つの大罪：Origin"))
        self.assertTrue(oa.latin_mi("The Seven Deadly Sins: Origin"))
        self.assertTrue(oa.latin_mi("Pokémon Pokopia"))
        # çizilemeyen ad başlığa eklenmez
        self.assertEqual(oa.oyunlu_baslik("Yeni güncelleme", "七つの大罪：Origin"), "Yeni güncelleme")


if __name__ == "__main__":
    unittest.main()
