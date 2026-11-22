"""data/diller.json dil kaydının site derleyiciye uyumlu görünümleri."""
from diller import DILLER, KAYIT, alan
MARKA = 'CTRL+A GAME'
SAYFA = {k: {d: KAYIT[d]['sayfa'][k] for d in DILLER} for k in KAYIT['tr']['sayfa']}
ESLER = [{d: KAYIT[d]['eski'][i] for d in DILLER} for i in range(len(KAYIT['tr']['eski']))]
TEK_TR = ['acilis-saati.html', 'bilinenler.html', 'depolama.html', 'oyunlar.html', 'gta-3.html', 'gta-4.html', 'gta-5.html', 'gta-san-andreas.html', 'gta-vice-city.html']
GTA_SAYFALAR = alan('gta_sayfalar')
GTA_ALT_SAYI = 8
GTA_SERI = {'gta-3.html', 'gta-4.html', 'gta-5.html', 'gta-san-andreas.html', 'gta-vice-city.html'}
GTA_HEDEF = alan('gta_hedef')
GTA_TARIH = '2026-11-19'
GTA_UST = alan('gta_ust')
PLATFORMLAR = ('PS5', 'Xbox', 'Switch 2', 'PC')
AY_KISA, DIL_AD, COGUL, T = alan('ay_kisa'), alan('ad'), alan('cogul'), alan('ui')
OYUN_KLASOR, REHBER_KLASOR = alan('oyun_klasor'), alan('rehber_klasor')
ETIKET_KLASOR = alan('etiket_klasor')
PL_AD = {'Mobil': alan('mobil')}

# Başlık, açıklama ve haber merkezindeki şerit.
KONU_METIN = {
    'tr': ('{ad} haberleri', '{ad} hakkında yayımladığımız oyun haberleri ve duyurular.',
           'Öne çıkan konular'),
    'en': ('{ad} news', 'Browse our coverage of {ad}, including announcements and recent news.',
           'Trending topics'),
    'fr': ('Actualités · {ad}', 'Retrouvez nos articles et les dernières annonces sur {ad}.',
           'Sujets populaires'),
    'es': ('Noticias sobre {ad}', 'Consulta nuestras noticias y anuncios sobre {ad}.',
           'Temas destacados'),
    'de': ('News zu {ad}', 'Hier findest du unsere Meldungen und Ankündigungen zu {ad}.',
           'Beliebte Themen'),
    'nl': ('Nieuws over {ad}', 'Lees ons nieuws en de recentste aankondigingen over {ad}.',
           'Populaire onderwerpen'),
    'zh': ('{ad}新闻', '浏览本站发布的{ad}相关新闻与公告。',
           '热门话题'),
}
KONU_TURLERI = {
    'tr': dict(haber='Genel oyun gündemi', ucretsiz='Ücretsiz oyun haberleri', cikis='Oyun çıkışları',
               indirim='Oyun indirimleri', guncelleme='Oyun güncellemeleri'),
    'en': dict(haber='General gaming news', ucretsiz='Free game news', cikis='Game releases',
               indirim='Game deals', guncelleme='Game updates'),
    'fr': dict(haber='Actualités générales du jeu vidéo', ucretsiz='Jeux gratuits', cikis='Sorties de jeux',
               indirim='Promotions sur les jeux', guncelleme='Mises à jour de jeux'),
    'es': dict(haber='Actualidad general de los videojuegos', ucretsiz='Juegos gratis', cikis='Lanzamientos de videojuegos',
               indirim='Ofertas de videojuegos', guncelleme='Actualizaciones de videojuegos'),
    'de': dict(haber='Allgemeine Spiele-News', ucretsiz='Kostenlose Spiele', cikis='Spieleveröffentlichungen',
               indirim='Spieleangebote', guncelleme='Spiele-Updates'),
    'nl': dict(haber='Algemeen gamenieuws', ucretsiz='Gratis games', cikis='Gamereleases',
               indirim='Gameaanbiedingen', guncelleme='Game-updates'),
    'zh': dict(haber='综合游戏资讯', ucretsiz='免费游戏资讯', cikis='游戏发售信息',
               indirim='游戏优惠资讯', guncelleme='游戏更新资讯'),
}


def say(dil, n, ad):
    tekil, cogul = COGUL[dil][ad]
    return f'{n} {tekil if n == 1 else cogul}'
