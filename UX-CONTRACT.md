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
