# CTRL+A GAME etkileşim sözleşmesi

Kaynak: Cio'nun istekleri ve `site.js` / `tools/site_derle.py` / `tools/site_oyun.py` uygulaması.

## Canonical UI Map

| Capability | Canonical owner | Source of truth | Allowed variants | Verification |
|---|---|---|---|---|
| Select/Listbox | native | indirim sıralaması, site.js | işletim sisteminin select menüsü | klavye ve dar ekran |
| Form | site.js | data-suzgec, data-arama | gönderimsiz yerel arama/süzme | sonuç, boş durum, temizleme |
| Scrollbar | style.css | global renkler | forced-colors sistem renkleri | yatay taşma kontrolü |
| Toast | site.js | ortak bildirim işlevi | kopyalama/takip geri bildirimi | canlı bölge ve klavye |

## Gezinme ve hiyerarşi

Üst menüde en çok 6 ana başlık yer alır: Haberler, Oyunlar, Fırsatlar (İndirimler + Ücretsiz açılır menü), Takvim, Rehberler, Söylentiler. Fırsatlar alt sayfalarında (`indirimler.html`, `ucretsiz.html` ve diğer 6 dildeki karşılıkları) sayfa içi `.alt-sekme` bağlantıları iki alt bölüm arasında tek tık geçiş sağlar. GTA VI sayfaları üst menüde yer almaz; Oyunlar dizini, `oyun/gta-6.html`, alt bilgi ve arama dizini (`ara-<dil>.json`) üzerinden erişilir; `.dosya-nav` yalnız GTA VI sayfalarının içinde görünür.

Ana sayfa ilk ekranda doğrudan manşet vitrinini (1 ana manşet + 4 ikincil haber) gösterir; ardından tarih sıralı yatay haber akışı ve sağ sütunda popüler oyunlar, yaklaşan çıkışlar, günün fırsatları ve ücretsiz oyunlar yer alır. Haber detay sayfası kırıntı izi (`.o-iz`), başlık + meta/takip şeridi, geniş 16:9 kapak, tek sütun okuma metni (60–75 karakter satır; video varsa 2 sütun `.hd-vid`), kaynak/paylaşım/etiket kutuları ve 3 sütun ilgili haberlerden oluşur.

## Liste ve detay

Haber, oyun ve rehber listeleri kendi detay sayfasına gider. Filtreler aynı sayfada uygulanır ve URL'ye yansır. Yenileme ve doğrudan filtreli URL aynı sonucu verir. Durum seçenekleri kayıt sayısından bağımsızdır. Eşleşme yokken sonuç sayısı sıfırdır, önceki kartlar görünmez ve temizleme erişilebilirdir. Gizli filtreler mobilde düğmeyle açılır; arama alanı görünür etiket taşır.

## Görseller ve tercihler

Görsel yüklenirken alanı ayrılmıştır (16:9). Kaynak görseli yüklenmezse aynı boyutta temalı SVG kapak kalır ve kaynak görseli notu gizlenir. İlk ekrandaki ana manşet ve haber detay kapak görselleri `loading="eager"` ile, ekran altındaki görseller `loading="lazy"` ile yüklenir; tüm uzak görseller `referrerpolicy="no-referrer"` taşır.

Koyu tema varsayılandır (`<html data-tema="koyu">`); sistem açık tema ayarı varsayılanı ezmez. Izgara/liste, açık/koyu tema, takip listesi ve gündem durdurma tercihi `localStorage` içinde saklanır; depolama engellense de temel akış çalışır. JavaScript kapalıyken bütün içerik, alt sekmeler ve kapaklar görünür; yalnız JavaScript gerektiren denetimler `.no-js .js-only` ile gizlenir.

## Erişilebilirlik ve diller

Arama penceresi açılışta odağı arama alanına taşır, Escape ile kapanır ve odağı açan denetime verir. Filtre durumu `aria-pressed`, sonuç sayısı `aria-live` ile aktarılır. Oyun ve söylenti durumu yalnız renkle açıklanmaz. Yedi dilde (`tr, en, fr, es, de, nl, zh`) aynı durum anahtarları ve yerelleştirilmiş etiketler kullanılır (`data/diller.json`). Hareket azaltma tercihi (`prefers-reduced-motion`) korunur; masaüstünde ve 360px–390px telefonda yatay sayfa taşması olmaz. Tüm temel etkileşim hedefleri en az 44×44px'tir.

## Çıkış kartı ve görsel sözleşmesi

Ana sayfa alt çıkış bandı ile aylık takvim aynı `cikis_satir()` üreticisini kullanır. Oyun adı `.cikis-adi` içinde tam metindir; bilinen oyunda merkez bağlantısı, diğerinde düz başlıktır. Adın kutusu sıfırdan büyük, görünür ve gerçek yüzey üzerinde en az 4.5:1 kontrastlı olmalıdır. Tür/platform, kalan gün, künye ve işlemler birbirinin alanına yerleşmez. Hiçbir haber veya oyun başlığında `line-clamp`, sabit yükseklik veya taşanı gizleme kullanılmaz.

`data/oyun_gorselleri.json` salt okunur kaynaktır. Takvimde önce takvim id'si, sonra eşleşen oyun kaydı; dizin/merkezde oyun id'si seçilir. Merkezde `genis` varsa o kullanılır. Yükleme hatası resmi kaldırır; altındaki üretilmiş kapak ve oyun adı kalır, atıf gizlenir. Geniş resmi olmayan 460px kapaklar büyütülmez.

Klavye kısayolları, `data-*` ve id bağları korunur. Süzgeç, boş sonuç/temizleme, Ctrl+K/Escape, tema, takip/kalıcılık, görünüm, ICS, gündem durdurma ve video düğmeleri aynı `site.js` sahipliğindedir. Görsel değerler ve kırılma noktaları [DESIGN.md](DESIGN.md) içinde kayıtlıdır. Düğmeler `data-*` üzerinden olay delegasyonuyla bağlanır; inline `onclick` eklenmez.

Canlı mağaza isteği 10 saniyede tamamlanmazsa iptal edilir ve tarihli yerel liste gösterilir. İstek sürerken boş sonuç mesajı gizlenir; sonuç veya yedek geldiğinde iskeletler ve `aria-busy` kaldırılır. Yerel liste de boşsa yalnız açıklayıcı boş durum görünür.
