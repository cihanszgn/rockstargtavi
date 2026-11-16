import json
import pathlib
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tools'))
import haber_oto as oto
import haber_hatti as hat

NOW = datetime(2026, 11, 16, 14, tzinfo=timezone.utc)
SOURCE = {'id': 'xbox', 'ad': 'Xbox', 'rss': 'https://news.xbox.com/en-us/feed/'}
URL = 'https://news.xbox.com/en-us/2026/11/16/game/'


class KaynakMetniTests(unittest.TestCase):
    def test_steam_press_groups_are_not_official_confirmation(self):
        self.assertFalse(oto.resmi('https://store.steampowered.com/news/group/38509069/view/692025835039753452'))
        self.assertTrue(oto.resmi('https://store.steampowered.com/news/app/394360/view/684144008188920528'))

    def test_rss_content_encoded_wins_over_description(self):
        raw = f'<rss xmlns:content="http://purl.org/rss/1.0/modules/content/"><channel><item><title>Game</title><link>{URL}</link><description>short</description><content:encoded><![CDATA[<p>{"olgu " * 140}</p>]]></content:encoded></item></channel></rss>'.encode()
        c = oto.rss_oku(raw, SOURCE, NOW)[0]
        self.assertGreater(len(c['kaynak_metni']), 400)
        self.assertEqual(c['kaynak_metni_alani'], 'content:encoded')
        self.assertEqual(c['kaynak_metni_url'], SOURCE['rss'])
        self.assertEqual(c['kaynak_metni_zamani'], NOW.isoformat())

    def test_atom_xhtml_content_and_summary(self):
        raw = f'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Game</title><link href="{URL}"/><summary>short</summary><content type="xhtml"><div xmlns="http://www.w3.org/1999/xhtml"><p>Gerçek &amp; olgu</p></div></content></entry></feed>'.encode()
        c = oto.rss_oku(raw, SOURCE, NOW)[0]
        self.assertEqual(c['kaynak_metni'], 'Gerçek & olgu')
        self.assertEqual(c['kaynak_metni_alani'], 'content')

    def test_html_cleanup_limit_and_no_script(self):
        text = oto.duz_metin('<style>bad</style><script>bad</script><p>A &amp; B</p><p>' + 'ö' * 7000 + '</p>')
        self.assertTrue(text.startswith('A & B '))
        self.assertNotIn('bad', text)
        self.assertEqual(len(text), 6000)

    def test_steam_json_contents(self):
        source = dict(SOURCE, api='https://api.steampowered.com/news', bicim='steam')
        del source['rss']
        raw = {'appnews': {'newsitems': [{'title': 'Game', 'gid': '123', 'date': NOW.timestamp(), 'feedname': 'steam_community_announcements', 'contents': '<p>Steam olgusu</p>'}]}}
        with patch.object(oto, 'getir', return_value=json.dumps(raw).encode()):
            c = oto._kaynak_tara(source, NOW)[1][0]
        self.assertEqual(c['kaynak_metni'], 'Steam olgusu')
        self.assertEqual(c['kaynak_metni_alani'], 'contents')

    def test_page_fallback_main_only_and_failure_marker(self):
        c = {'url': URL, 'kaynak_metni': 'short'}
        with patch.object(oto, 'getir', return_value=('<html><nav>bad</nav><article><p>' + 'olgu ' * 120 + '</p></article><footer>bad</footer></html>').encode()) as fetch:
            oto.kaynak_tamamla(c, NOW)
        self.assertNotIn('bad', c['kaynak_metni'])
        self.assertEqual(c['kaynak_metni_alani'], 'sayfa:ana_metin')
        self.assertEqual(fetch.call_args.kwargs['timeout'], 10)
        c = {'url': URL}
        with patch.object(oto, 'getir', side_effect=OSError('403')):
            oto.kaynak_tamamla(c, NOW)
        self.assertEqual(c['kaynak_metni'], '')
        self.assertEqual(c['kaynak_metni_durumu'], 'indirilemedi')

    def test_sufficient_feed_body_never_downloads_page(self):
        c = {'url': URL, 'kaynak_metni': 'olgu ' * 120}
        with patch.object(oto, 'getir') as fetch:
            oto.kaynak_tamamla(c, NOW)
        fetch.assert_not_called()

    def test_empty_xbox_body_does_not_fall_back_to_recommendation_cards(self):
        c = {'url': URL, 'kaynak_metni': 'The post Game appeared first on Xbox Wire.'}
        raw = '<main><div>Editor November 16</div><article class="art-body"></article><section>Keep reading Games Other story</section></main>'
        with patch.object(oto, 'getir', return_value=raw.encode()):
            oto.kaynak_tamamla(c, NOW)
        self.assertEqual(c['kaynak_metni_durumu'], 'govde_yok')
        self.assertNotIn('Keep reading', c['kaynak_metni'])

    def test_explicit_entry_content_wins_over_main_navigation(self):
        text = oto.duz_metin('<main>Trending Stories<article><div class="entry-content"><p>Actual game patch</p></div>Comments</article>Other game</main>', True)
        self.assertEqual(text, 'Actual game patch')
        self.assertEqual(oto.duz_metin('<nav>Menu</nav><div>Other links</div>', True), '')
        self.assertEqual(oto.duz_metin('<main><div class="navigation-menu">Home Games</div><section class="related">Other games</section></main>', True), '')

    def test_encoded_body_preferred_even_if_description_is_longer(self):
        raw = f'<rss xmlns:content="http://purl.org/rss/1.0/modules/content/"><channel><item><title>Game</title><link>{URL}</link><description>{"menu " * 100}</description><content:encoded><![CDATA[<p>Actual fact</p>]]></content:encoded></item></channel></rss>'.encode()
        self.assertEqual(oto.rss_oku(raw, SOURCE, NOW)[0]['kaynak_metni'], 'Actual fact')

    def test_steam_page_uses_requested_announcement_not_adjacent_story(self):
        import html
        events = [{'announcement_body': {'gid': 'other', 'body': 'Wrong story'}},
                  {'announcement_body': {'gid': '123', 'body': '[p]Real update[/p]'}}]
        raw = '<div data-partnereventstore="' + html.escape(json.dumps(events), quote=True) + '" data-partnereventadjacents="' + html.escape(json.dumps([{'announcementGID': '123'}]), quote=True) + '"></div>'
        self.assertEqual(oto.duz_metin(raw, True), 'Real update')

    def test_attempt_ceiling_is_eight(self):
        self.assertEqual(oto.CONFIG['sinirlar']['yazim_deneme'], 8)

    def test_read_evidence_matches_source_and_time(self):
        auto = {'resmi_url': URL, 'kaynak_metinleri': [dict(url=URL, kaynak_metni='olgu', kaynak_metni_url=SOURCE['rss'], kaynak_metni_zamani=NOW.isoformat(), kaynak_metni_alani='description')]}
        self.assertTrue(oto.kaynak_okunmus(auto, {oto.kanonik(URL)}, NOW))
        auto['kaynak_metinleri'][0]['url'] = 'https://example.org/other'
        self.assertFalse(oto.kaynak_okunmus(auto, {oto.kanonik(URL)}, NOW))


if __name__ == '__main__':
    unittest.main()
