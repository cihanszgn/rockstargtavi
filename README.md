# ctrl-agame.com — CTRL+A GAME

Bütün oyunlar tek yerde: haberler, günün indirimleri, ücretsiz oyunlar, söylenti radarı, çıkış takvimi, oyun merkezleri,
oyuna özel temalı rehberler ve GTA VI dosyası.
Dört dil (tr, en, fr, es). Düz statik HTML + tek `style.css` + tek `site.js`; çalışırken CDN, çerçeve veya sunucu yok.
Yayın: GitHub Pages (`cihanszgn/rockstargtavi`), özel alan adı `CNAME` dosyasında.

## Derleme
```
py tools/sosyal_derle.py
```
Tek komut bütün siteyi dört dilde yeniden yazar, sonra sosyal kartları (`kart/`) üretir. Değişmeyen dosyaya dokunmaz;
iki kez üst üste çalıştırınca ikincisi "0 dosya değişti" der (git diff boş kalır).

- Yalnız site (Pillow gerekmez, GitHub Actions bunu kullanır): `py tools/site_derle.py`
- İndirim/ücretsiz anlık görüntüsünü yenile: `py tools/indirim_cek.py` (sonra derle)
- Derleme tarihini elle vermek (geri sayım/"kaç gün kaldı" denemesi): `SITE_BUGUN=2026-11-20`
- Deneme verisiyle derlemek: `SITE_DENEME_VERI=<klasör>` (klasörde `soylentiler.json` / `takvim.json` vb. varsa onlar okunur)

Gereken: Python 3.12, Pillow (yalnız kartlar için). Yerelde bakmak için: `py -m http.server 8765` → http://127.0.0.1:8765/

## Yapı
| Yol | Ne |
|---|---|
| `tools/site_derle.py` | Sayfa üreticisi: ana sayfa, haber merkezi + haber sayfaları, indirimler, ücretsiz, söylentiler, takvim, GTA VI dosyası, 404, RSS, `sitemap.xml`, arama dizinleri (`ara-*.json`) |
| `tools/site_metin.py` | Bütün arayüz metinleri (4 dil), sayfa yolları (`SAYFA`), GTA VI tarihi (`GTA_TARIH`) |
| `tools/site_oyun.py` | Oyunlar dizini (`oyun/index.html`), oyun merkezleri (`oyun/<id>.html`), rehber dizini (`rehberler.html`), rehber sayfaları (`rehber/<id>.html`); dört dilde (`en/game/`, `en/guide/`, `fr/jeu/`, `fr/guide/`, `es/juego/`, `es/guia/`). Verisi kalkan oyunun/rehberin eski sayfasını derlemede kaldırır |
| `tools/oyun_tema.py`, `tools/oyun_tema_temel.css` | Oyun başına tema (renk, yazı tipi, düzen, amblem, kutu/adım/tablo biçimi) → derlemede `oyun-tema.css`. Amblemler tamamen üretilmiş soyut SVG; oyun logosu/görseli/yazı tipi taklidi yok |
| `tools/sosyal_derle.py` | Giriş noktası; `data/icerik.json` doğrulaması, kartlar (`kart/*.png|jpg`), kök `og.png`. `sosyal_yayinla.py` buradan `DILLER, GORUNEN, KLASOR, M, SITE, kart_ad` alır |
| `tools/indirim_cek.py` | CheapShark + Epic ücretsiz oyun anlık görüntüsü (yalnız standart kütüphane) |
| `style.css`, `site.js` | Tek stil ve tek betik. Sürüm eki (`?v=`) derlemede içerikten hesaplanır |
| `fonts/` | Archivo (OFL), siteyle birlikte sunulur. `fonts/oyun/`: tema yazı tipleri (16 adet, hepsi OFL, tek ağırlık, Latin + Türkçe/Fransızca/İspanyolca alt kümesi, 7–21 KB; lisanslar `fonts/oyun/lisans/`). Her rehber yalnız kendi temasının yazı tipini yükler |
| `gta-6.html` ve eski sayfalar | Elle yazılmış rehber sayfaları. Derleyici yalnız kabuğu (üst menü, alt bilgi, `<head>`) yeniler; `<main>` içeriğine dokunmaz. `gta-6.html`deki işaretli bloklar (`gta-ust`, `gta-haber`, `gta-dizin`) otomatik dolar |
| `.github/workflows/indirim.yml` | Her gün 07:23 (TR) ve perşembe 19:09: veriyi çeker, siteyi derler, değişeni yazar |
| `.github/workflows/sosyal.yml`, `sosyal/` | Sosyal medya paylaşımı (bu yapı değiştirmez) |

Dokunulmayanlar: `anma.js`, `CNAME`, `711f987a9d9616ba3f93c799dcb2030d.txt` (IndexNow anahtarı), GA etiketi.

## Veri dosyaları (`data/`)
Hepsi UTF-8 JSON. Eksik veya boş dosya derlemeyi bozmaz; ilgili bölüm "henüz yok" durumunu gösterir. Geçersiz öğe atlanır ve uyarı basılır.

**`icerik.json` — haberler** (liste). Zorunlu: `id` (küçük harf-rakam-tire, değişmez: haber adresi ve kart adı buna bağlı),
`tarih` (YYYY-AA-GG), `oyun`, `tur` (`haber|ucretsiz|cikis|indirim|guncelleme`), `kaynaklar` ([{`url` https, `ad`, `tarih`?}]),
`diller.tr|en|fr|es` ({`baslik` ≤100, `ozet`, `metin`, `etiketler`?}). İsteğe bağlı: `platform` (["PS5","PC"…]).
Hata varsa derleme durur ve satırı söyler.

**`soylentiler.json` — söylenti radarı** (liste). `id`, `tarih`, `oyun`, `guven` (`dusuk|orta|yuksek`),
`durum` (`dogrulanmadi|dogrulandi|yalanlandi`), `kaynaklar` ([{`url`, `ad`, `tarih`?}]), `platform`?,
`diller.<dil>` ({`baslik`, `ozet`, `metin`?, `guven_nedeni`?}). Bir dil eksikse söylenti o dilde gösterilmez.

**`takvim.json` — çıkış takvimi** (liste). `id`, `oyun`, `kaynak` ({`url`, `ad`}); `tarih` (YYYY-AA-GG veya `null` = tarih belli değil),
`pencere` ({dil: "2027 başı"…}, tarihsizler için), `platform`, `tur` ({dil: tür adı}), `gelistirici`, `yayinci`, `kesin`.

**`oyunlar.json` — oyun merkezleri** (liste ya da {`oyunlar`: [...]}). `id` (slug, değişmez: merkez adresi), `ad`, `kisa`?,
`eslesme`? (haber/söylenti/takvimdeki `oyun` adlarını bu oyuna bağlayan diğer adlar), `tur` ({dil: tür}), `platform`, `gelistirici`,
`resmi` ({`url` https, `ad`}), `diller.<dil>.tanim`. Her oyun için merkez sayfası basılır; haber, söylenti ve takvim öğeleri `oyun` adıyla eşleşir.

**`rehberler.json` — rehber kaynak bağlantıları** (liste ya da {`rehberler`: [...]}). Öğe: `hub` (oyun `id`si ya da `genel`), `url` https, `kaynak`, `kategori`, `dil`?, `lisans`?, `acik`?,
`diller.<dil>` ({`baslik`, `aciklama`}). Bağlantılar o oyunun rehberinde yalnız son bölümde (`genel` olanlarla birlikte) ve merkez sayfasında görünür.

**`rehber/<oyun-id>.json` — oyuna özel rehber** (bir oyun, bir dosya; dosya yoksa rehber sayfası ve bağlantısı basılmaz):
```
{"oyun": "<id>", "guncelleme": "YYYY-AA-GG", "surum": "Sezon 3 / 1.2", "kaynaklar": [{"url": "https://…", "ad": "…"}],
 "diller": {"tr": {"baslik": "…", "ozet": "…", "kunye": [{"ad": "…", "deger": "…"} ×5],
                   "bolumler": [{"id": "baslangic", "baslik": "…", "bloklar": [{"tip": "p", "metin": "…"}]}]}, "en": {…}, "fr": {…}, "es": {…}}}
```
Blok tipleri: `p`, `ipucu`, `uyari` (`metin`); `liste` (`ogeler`: [metin]); `adimlar` (`ogeler`: [{`baslik`, `metin`}]);
`tablo` (`basliklar`: [..], `satirlar`: [[..]]); `sss` (`ogeler`: [{`s`, `c`}]). Bilinmeyen tip uyarı verir ve düz paragraf olur.
Metin her zaman kaçışlanır; yalnız `**kalın**` işlenir. Eksik dil o dilde basılmaz (hreflang ve site haritası da atlar).
Sürüm rozeti: Türkçede `surum`, diğer dillerde o dilin `kunye` 4. satırı (yoksa rozet gizli).

**`indirimler.json`, `ucretsiz.json`** — `indirim_cek.py` yazar, elle düzenlenmez. Tarayıcı canlı fiyatı CheapShark'tan alır;
bu dosyalar JavaScript kapalıyken ve CheapShark'a ulaşılamazken gösterilir. Yalnız resmî/yetkili mağazalar (`indirim_cek.py` içindeki izin listesi).

**`sayfalar.json`** — derleyicinin yazdığı sayfa listesi (site haritası ve dil karşılıkları için). Elle düzenlenmez.

## İçerik ekleme
1. Haber: `data/icerik.json`a yeni öğe (4 dil + kaynak) → `py tools/sosyal_derle.py`. Haber sayfası, merkez listesi, RSS, site haritası ve kartlar kendiliğinden oluşur.
2. Söylenti: `data/soylentiler.json`a öğe; güven ve durum alanı zorunlu. Söylenti yalnız Söylentiler bölümünde ve ana sayfadaki radarda görünür, haber olarak basılmaz.
3. Çıkış: `data/takvim.json`a öğe; tarih kesinleşince `tarih` doldurulur, `pencere` boşaltılır.
4. Yeni elle yazılmış sayfa: dosyayı oluştur (`<main>` içeriğiyle), `tools/site_metin.py`de dört dilliyse `ESLER`e, yalnız Türkçeyse `TEK_TR`ye ekle
   (GTA VI dosyasının parçasıysa `GTA_SAYFALAR`a da). Kabuk, menü ve site haritası derlemede gelir.
5. Yeni oyun: `data/oyunlar.json`a öğe → merkez sayfası dört dilde oluşur. Temasız oyun türüne göre varsayılan tema alır;
   özel tema için `tools/oyun_tema.py` `TEMALAR`a `"<id>": dict(...)` ekle (renkler `koyu`/`acik` paleti, `yazi` = `fonts/oyun/` adı,
   `duzen` = amblem/kahraman düzeni `AMBLEM` anahtarlarından biri, `kutu`, `adim`, `tablo`, `hareket`). Derleme renk karşıtlığı AA altına düşerse uyarır.
6. Yeni rehber: `data/rehber/<oyun-id>.json` (yukarıdaki şema) → rehber sayfası, dizin kartı, merkez bağlantısı ve site haritası kendiliğinden gelir.
   Yeni yazı tipi gerekirse yalnız OFL; tek ağırlık + Latin/Türkçe/Fransızca/İspanyolca alt küme woff2 olarak `fonts/oyun/`a, lisansı `fonts/oyun/lisans/`a
   (fontTools ile; woff2 için brotli gerekir: `uv run --with fonttools --with brotli python …`). `oyun_tema.py` `YAZILAR`a anahtarını ekle.
7. Derle, `py -m http.server` ile bak, sonra commit.

## Hareket ve etkileşim (`site.js`, `style.css`)
Sayfa geçişleri (`@view-transition`), ana sayfa kahraman tuvali, yazılan başlık, kaydırınca beliren öğeler, sayı sayma, kart eğimi,
gündem şeridi (durdur düğmesi, seçim saklanır), süzgeçte FLIP yer değiştirme, tema düğmesinde dairesel geçiş, iskelet yükleyiciler;
rehberde içindekiler (etkin bölüm, okuma çubuğu, mobilde açılır panel, Esc ile kapanır) ve bölüm bağlantısı kopyalama.
Kurallar: yalnız `transform`/`opacity`; `prefers-reduced-motion` açıkken hepsi kapanır; sekme gizliyken ya da öğe ekran dışındayken durur;
gizli başlayan her stil `.js` sınıfına bağlı (JavaScript kapalıyken bütün içerik görünür); dış kütüphane/CDN yok.

## Kurallar
- Her haberin ve söylentinin kaynağı yazılır; söylenti yalnız kendi etiketli bölümünde durur.
- Sızıntı/çalıntı içerik, korsan, hile/mod menüsü, hesap/anahtar satıcısı, bahis bağlantısı yok.
- Firma logosu ve oyun görseli haberlerde kullanılmaz; indirim/ücretsiz listelerindeki küçük resimler mağaza API'sinden gelir.
- Olmayan veri basılmaz (yer tutucu haber, sahte fiyat yok).
- Reklam/istatistik değişirse `gizlilik.html` güncellenir.

## SEO
- Her sayfada `canonical`, dört dil + `x-default` (=en) `hreflang`, Open Graph/Twitter etiketleri; `sitemap.xml` `xhtml:link` ile dil karşılıklarını verir.
- RSS: `oyun-haberleri.xml`, `en/game-news.xml`, `fr/actus-jeux.xml`, `es/noticias-juegos.xml` (haber akışı) ve her dilde `feed.xml`.
- Haber sayfalarında `NewsArticle`, ana sayfada `WebSite` JSON-LD. Paylaşım görseli `og.png` (1200x630, `sosyal_derle.py` üretir).
- IndexNow anahtarı kökte; gönderme elle yapılır.

## DNS (Hostinger)
A `@` → 185.199.108.153 / .109.153 / .110.153 / .111.153, CNAME `www` → cihanszgn.github.io
