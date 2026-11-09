# xn--rockstargtav-d5b.com — GTA VI Türkçe Rehber

Bağımsız, Türkçe GTA VI hayran sitesi. Düz HTML + tek `style.css`, derleme adımı yok.
Yayın: GitHub Pages (`cihanszgn/rockstargtavi`, `main` dalı kökü), özel alan adı `CNAME` dosyasında.

## Kurallar
- Rockstar'a ait logo, görsel, yazı tipi kullanılmaz. Her haberin kaynağı yazılır; söylenti haber olmaz.
- Sızıntı, korsan, hile bağlantısı yok. Alt bilgideki "bağımsız hayran sitesi" uyarısı her sayfada kalır.
- Reklam/istatistik eklenirse `gizlilik.html` güncellenir.

## Güncelleme
Sayfayı düzenle → `git commit` → `git push`. 1-2 dakikada yayına çıkar. Yeni sayfa eklenirse `sitemap.xml`e ekle.

## DNS (Hostinger)
A `@` → 185.199.108.153 / .109.153 / .110.153 / .111.153, CNAME `www` → cihanszgn.github.io

## SEO
- hreflang: tr, en, fr, es ve x-default (=en). Her sayfa `canonical` + 5 `alternate` taşır; tr/en/fr/es karşılıkları `sitemap.xml`de `xhtml:link` ile de verilir. `oyunlar.html` ve `gta-*.html` yalnız Türkçe, hreflang'sızdır.
- RSS: `feed.xml` (TR), `en/feed.xml`, `fr/feed.xml`, `es/feed.xml`; her öğe haberler sayfasındaki `<li id="...">` çapasına bağlanır. Haber eklenince hem sayfaya hem feed'e öğe ekle.
- Paylaşım: `og.png` (1200x630) tüm sayfalarda Open Graph/Twitter görseli; Rockstar görseli içermez.
- JSON-LD: ana sayfalarda `WebSite`, SSS'li sayfalarda `FAQPage` (metin `<details>` ile aynı olmalı).
- IndexNow: kökteki `711f987a9d9616ba3f93c799dcb2030d.txt` anahtar dosyasıdır (içeriği dosya adıyla aynı). Gönderme elle yapılır.
- Yeni sayfa eklenince: `sitemap.xml`e ekle, menüye bağla, og/canonical/hreflang yaz; haber ise feed'i güncelle.
