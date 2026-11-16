# CTRL+A GAME etkileşim sözleşmesi

Kaynak: Cio'nun istekleri ve `site.js` / `tools/site_derle.py` / `tools/site_oyun.py` uygulaması.

## Canonical UI Map

| Capability | Canonical owner | Source of truth | Allowed variants | Verification |
|---|---|---|---|---|
| Select/Listbox | native | indirim sıralaması, site.js | işletim sisteminin select menüsü | klavye ve dar ekran |
| Form | site.js | data-suzgec, data-arama | gönderimsiz yerel arama/süzme | sonuç, boş durum, temizleme |
| Scrollbar | style.css | global renkler | forced-colors sistem renkleri | yatay taşma kontrolü |
| Toast | site.js | ortak bildirim işlevi | kopyalama/takip geri bildirimi | canlı bölge ve klavye |

## Liste ve detay

Haber, oyun ve rehber listeleri kendi detay sayfasına gider. Filtreler aynı sayfada uygulanır ve URL'ye yansır. Yenileme ve doğrudan filtreli URL aynı sonucu verir. Durum seçenekleri kayıt sayısından bağımsızdır. Eşleşme yokken sonuç sayısı sıfırdır, önceki kartlar görünmez ve temizleme erişilebilirdir. Gizli filtreler mobilde düğmeyle açılır; arama alanı görünür etiket taşır.

## Görseller ve tercihler

Görsel yüklenirken alanı ayrılmıştır. Kaynak görseli yüklenmezse aynı boyutta temalı kapak kalır ve kaynak görseli notu gizlenir. Izgara/liste, açık/koyu tema, takip listesi ve gündem durdurma tercihi tarayıcıda saklanır; depolama engellense de temel akış çalışır. JavaScript kapalıyken bütün içerik ve kapaklar görünür; yalnız JavaScript gerektiren denetimler gizlenir.

## Erişilebilirlik ve diller

Arama penceresi açılışta odağı arama alanına taşır, Escape ile kapanır ve odağı açan denetime verir. Filtre durumu aria-pressed, sonuç sayısı aria-live ile aktarılır. Oyun durumu yalnız renkle açıklanmaz. Dört dilde aynı durum anahtarları ve yerelleştirilmiş etiketler kullanılır. Hareket azaltma tercihi korunur; masaüstü ve telefonda yatay sayfa taşması olmaz.

## Çıkış kartı ve görsel sözleşmesi — 2026-11-16

Ana sayfa ile aylık takvim aynı `cikis_satir()` üreticisini kullanır. Oyun adı `.cikis-adi` içinde tam metindir; bilinen oyunda merkez bağlantısı, diğerinde düz başlıktır. Adın kutusu sıfırdan büyük, görünür ve gerçek yüzey üzerinde en az 4.5:1 kontrastlı olmalıdır. Tür/platform, kalan gün, künye ve işlemler birbirinin alanına yerleşmez. Başlıkta line-clamp, sabit yükseklik veya taşanı gizleme kullanılmaz.

`data/oyun_gorselleri.json` salt okunur kaynaktır. Takvimde önce takvim id'si, sonra eşleşen oyun kaydı; dizin/merkezde oyun id'si seçilir. Merkezde `genis` varsa o kullanılır. Bütün uzak resimler boyut/alan ayırır, lazy yüklenir ve no-referrer kullanır. Yükleme hatası resmi kaldırır; altındaki üretilmiş kapak ve oyun adı kalır, atıf gizlenir. Geniş resmi olmayan 460px kapaklar büyütülmez.

Klavye kısayolları, `data-*` ve id bağları korunur. Süzgeç, boş sonuç/temizleme, Ctrl+K/Escape, tema, takip/kalıcılık, görünüm, ICS, gündem durdurma ve video düğmeleri aynı `site.js` sahipliğindedir. Mobilde temel düğmeler en az 44px; metin bağlantıları paragraf akışını korur. 390px'te içerik tek sütundur ve yatay taşma olmaz. Koyu/açık tema ile dört dil aynı bileşen sözleşmesini kullanır. JavaScript kapalıyken statik içerik görünürdür; kaydırma animasyonu içerik görünürlüğünün önkoşulu değildir.

Görsel değerler ve kırılma noktaları [DESIGN.md](DESIGN.md) içinde kayıtlıdır. Statik premium denetleyici `data-*` üzerinden olay delegasyonunu tanımadığı için düğmeleri eylemsiz raporlayabilir; gerçek olay bağları tarayıcıda denenerek değerlendirilir, bu uyarıyı susturmak için inline onclick eklenmez.

Canlı mağaza isteği 10 saniyede tamamlanmazsa iptal edilir ve tarihli yerel liste gösterilir. İstek sürerken boş sonuç mesajı gizlenir; sonuç veya yedek geldiğinde iskeletler ve aria-busy kaldırılır. Yerel liste de boşsa yalnız açıklayıcı boş durum görünür.
