import contextlib
import io
import json
import pathlib
import re
import shutil
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from datetime import date
from html import escape
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import site_derle as site
from test_haber_oto import article


def json_ld(html):
    return {x["@type"]: x for raw in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
            if isinstance(x := json.loads(raw), dict) and isinstance(x.get("@type"), str)}


class SeoTests(unittest.TestCase):
    def test_short_descriptions_add_new_text_at_word_boundary(self):
        ozet = "Sunucular yeniden açıldı."
        metin = (ozet + " Yama, iki yeni görev ve yeni kayıt noktaları getiriyor. "
                 "Oyuncular bu hafta tüm haritalarda yeni ödülleri kazanabilmek için oturum açabilir.")
        aciklama = site.meta_aciklama("tr", ozet, metin)
        self.assertEqual(aciklama.count(ozet), 1)
        self.assertIn("iki yeni görev", aciklama)
        self.assertTrue(110 <= len(aciklama) <= 155)
        self.assertTrue(metin.startswith(aciklama))
        self.assertEqual(metin[len(aciklama)], " ")

        ozet = "赛季正式开启。"
        aciklama = site.meta_aciklama("zh", ozet, ozet + "玩家可以使用新的装备与地图。" * 8 + "每周活动提供不同奖励。")
        self.assertEqual(aciklama.count(ozet), 1)
        self.assertLessEqual(len(aciklama), 78)
        self.assertIn("新的装备与地图", aciklama)

    def test_publication_uses_only_known_dates_and_offsets(self):
        x = article()
        x["otomasyon"]["eklenme"] = "2026-11-15T08:10:05Z"
        self.assertEqual(site.haber_yayim(x), "2026-11-15T08:10:05+00:00")
        x["guncelleme"] = "2026-11-16T14:00:00+03:00"
        self.assertEqual(site.haber_degisim(x, site.haber_yayim(x)), x["guncelleme"])
        for eklenme in ("2026-11-16T08:10:05+03:00", "2026-11-15T08:10:05", "2026-11-15", "bozuk"):
            x["otomasyon"]["eklenme"] = eklenme
            self.assertEqual(site.haber_yayim(x), "2026-11-15")

    def test_news_sitemap_has_two_calendar_days_and_all_available_languages(self):
        bugun, dun, eski, ileri = [article(i) for i in ("bugun", "dun", "eski", "ileri")]
        bugun["tarih"] = "2026-11-15"
        bugun["otomasyon"]["eklenme"] = "2026-11-15T23:59:59+03:00"
        bugun["diller"]["zh"]["baslik"] = "新章节 & 活动"
        dun["tarih"], eski["tarih"], ileri["tarih"] = "2026-11-14", "2026-11-13", "2026-11-16"
        ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9", "n": "http://www.google.com/schemas/sitemap-news/0.9"}
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            path = root / "news-sitemap.xml"
            with patch.object(site, "KOK", root), patch.object(site, "BUGUN", date(2026, 11, 15)):
                self.assertEqual(site.haber_haritasi([bugun, dun, eski, ileri]), 1)
                self.assertEqual(site.haber_haritasi([bugun, dun, eski, ileri]), 0)
                xml = ET.parse(path)
                self.assertEqual(len(xml.findall("s:url", ns)), 14)
                self.assertEqual({e.text for e in xml.findall(".//n:language", ns)},
                                 {*site.DILLER} - {"zh"} | {"zh-cn"})
                self.assertEqual({e.text for e in xml.findall(".//n:publication_date", ns)},
                                 {"2026-11-14", "2026-11-15T23:59:59+03:00"})
                self.assertIn("新章节 & 活动", [e.text for e in xml.findall(".//n:title", ns)])
                self.assertEqual(site.haber_haritasi([eski, ileri]), 1)
                self.assertEqual(ET.parse(path).findall("s:url", ns), [])

    def test_build_preserves_legacy_news_and_builds_only_mature_topics(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "data").mkdir()
            for ad in ("icerik.json", "etiket_esles.json", "sabit_sayfalar.json"):
                shutil.copyfile(ROOT / "data" / ad, root / "data" / ad)
            oyunlar = json.loads((ROOT / "data" / "oyunlar.json").read_text(encoding="utf-8"))
            (root / "data" / "oyunlar.json").write_text(json.dumps([o for o in oyunlar if o["id"] == "gta-6"]), encoding="utf-8")
            for yol in {"hakkinda.html", *site.sd.GTA_HABER.values()}:
                (root / yol).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / yol, root / yol)
            veri = [article(n) for n in ("demo-a", "demo-b", "demo-c")]
            for i, x in enumerate(veri):
                x["oyun"] = "Grand Theft Auto VI"
                x["platform"] = ["PC", "PS5"] if i < 2 else ["PC"]
                x["diller"]["tr"]["etiketler"] = ["#GTA6" if i == 0 else "#gtavi", "#Konu", "#PC"]
                x["diller"]["en"]["etiketler"] = ["#Konu"] if i < 2 else []
            x = veri[0]
            dl = x["diller"]["tr"]
            dl.update(baslik="Grand Theft Auto VI yaması", ozet="Yama çıktı.",
                      metin="Yama çıktı. Yeni görevler ve kaydetme değişiklikleri oyuna eklendi.")
            x["otomasyon"]["eklenme"] = "2026-11-15T15:08:00+03:00"
            (root / "data" / "gorseller.json").write_text(json.dumps({
                x["id"]: {"url": "https://example.com/kapak.jpg", "kaynak": "Test", "en": 1200, "boy": 630}
            }), encoding="utf-8")
            with (patch.object(site, "KOK", root), patch.object(site.sd, "KOK", root),
                  patch.dict("os.environ", {"SITE_BUGUN": "2026-11-15"}), contextlib.redirect_stdout(io.StringIO())):
                arsiv = site.sd.yukle()
                eski = next(x for x in arsiv if "PS5" not in (x.get("platform") or []) and not x["diller"]["tr"].get("etiketler")
                            and len(x["diller"]["tr"]["metin"].split()) < 80)
                site.derle([*veri, eski])
                self.assertEqual(site.derle([*veri, eski])["degisen"], 0)
                sayfa = (root / site.haber_url("tr", x).lstrip("/")).read_text(encoding="utf-8")
                self.assertIn(f"<title>{dl['baslik']} | CTRL+A GAME</title>", sayfa)
                self.assertIn(f'property="og:title" content="{dl["baslik"]} | CTRL+A GAME"', sayfa)
                self.assertIn(f'name="twitter:title" content="{dl["baslik"]} | CTRL+A GAME"', sayfa)
                self.assertIn(f'<p class="giris">{dl["ozet"]}</p>', sayfa)
                self.assertIn('loading="eager" fetchpriority="high"', sayfa)
                self.assertIn('<a class="cip cip-etiket" href="/etiket/pc.html">PC</a>', sayfa)
                self.assertNotIn('>#PC</a>', sayfa)
                self.assertIn('<span class="cip cip-etiket">PS5</span>', sayfa)
                self.assertIn('<a class="cip cip-etiket" href="/etiket/gtavi.html">#GTAVI</a>', sayfa)
                meta = json_ld(sayfa)
                haber = meta["NewsArticle"]
                self.assertEqual(haber["datePublished"], x["otomasyon"]["eklenme"])
                self.assertEqual(haber["dateModified"], haber["datePublished"])
                self.assertEqual(haber["about"], {"@type": "VideoGame", "name": "GTA VI",
                                                 "url": site.SITE + "/oyun/gta-6.html"})
                self.assertEqual(haber["articleSection"], site.M["tr"]["tur"][x["tur"]])
                self.assertIn("#GTAVI", haber["keywords"])
                self.assertEqual(haber["publisher"]["logo"]["@type"], "ImageObject")
                self.assertTrue(haber["publisher"]["logo"]["url"].endswith("/yayinci-logo.png"))
                aciklama = escape(haber["description"], quote=True)
                self.assertIn("Yeni görevler", aciklama)
                for attr in ('name="description"', 'property="og:description"', 'name="twitter:description"'):
                    self.assertIn(f'{attr} content="{aciklama}"', sayfa)
                self.assertEqual([e.get("item") for e in meta["BreadcrumbList"]["itemListElement"]],
                                 [site.SITE + "/", site.SITE + "/oyun-haberleri.html", site.SITE + "/oyun/gta-6.html", None])

                topic_file = root / "etiket" / "konu.html"
                topic = topic_file.read_text(encoding="utf-8")
                self.assertEqual(topic.count("<h1>"), 1)
                self.assertNotIn("hreflang=", topic.split("</head>", 1)[0])
                self.assertFalse((root / "en" / "tag" / "konu.html").exists())
                self.assertIn('loading="lazy"', topic)
                self.assertIn('href="/oyun/gta-6.html"', topic)
                self.assertEqual(len(json_ld(topic)["CollectionPage"]["mainEntity"]["itemListElement"]), 3)
                self.assertIn("BreadcrumbList", json_ld(topic))
                self.assertIn("etiket/konu.html", (root / "sitemap.xml").read_text(encoding="utf-8"))
                for bolum in ("haber", "indirim", "ucretsiz", "takvim", "soylenti", "oyunlar", "rehberler", "hakkinda"):
                    metin = (root / site.SAYFA[bolum]["tr"]).read_text(encoding="utf-8")
                    self.assertIn("BreadcrumbList", json_ld(metin), bolum)
                    if bolum == "haber":
                        self.assertIn('href="/etiket/konu.html"', metin)
                        self.assertEqual(len(json_ld(metin)["CollectionPage"]["mainEntity"]["itemListElement"]), 4)
                self.assertIn("Organization", json_ld((root / "index.html").read_text(encoding="utf-8")))
                site.derle([*veri[:2], eski])
                self.assertFalse(topic_file.exists())
                self.assertNotIn("etiket/konu.html", (root / "sitemap.xml").read_text(encoding="utf-8"))
