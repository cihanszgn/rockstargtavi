---
version: alpha
name: CTRL+A GAME
description: Gerçek oyun görselleri, açık bilgi hiyerarşisi ve klavye kimliğiyle dört dilli oyun portalı.
colors:
  background: '#0D1420'
  surface: '#151F2E'
  text: '#F1F4FA'
  muted: '#AFBCD0'
  primary: '#3B6CF6'
  news: '#3BC9FF'
  updates: '#B39DFF'
  deals: '#FF6BB5'
  success: '#3DDC97'
  warning: '#F5B83D'
  danger: '#FF6B6B'
typography:
  sans:
    fontFamily: 'Archivo, Segoe UI, system-ui, sans-serif'
  mono:
    fontFamily: 'ui-monospace, Consolas, Cascadia Mono, monospace'
rounded:
  panel: '16px'
  key: '6px'
spacing:
  page-max: '1536px'
  card-gap: '24px'
  card-padding: '24px'
  section: '72px'
components:
  news-card: {}
  rumor-card: {}
  filter: {}
  command-palette: {}
---

# CTRL+A GAME tasarım sistemi

## Overview

Türkçe, İngilizce, Fransızca ve İspanyolca oyun portalı. 16 Kasım 2026 yönü: mağaza vitrini kadar görselli, oyun dergisi kadar okunabilir; geniş boşluklar, görselin altında tam oyun adı ve sade yüzeyler. İmza Ctrl+A seçim vurgusu ve fiziksel klavye tuşlarıdır. Neon çerçeveler ve görsel üzerine bindirilmiş haber başlıkları kullanılmaz. Merkez ve rehberler oyunun temasını korur; dizin kartlarında ortak Archivo hiyerarşisi kullanılır.

Token sahibi mevcut çalışma kodudur (Model B). Bu belge değerleri açıklar; CSS üretmez. `style.css :root` temel renk, boşluk ve ölçülerin; `[data-tema="acik"]` açık temanın sahibidir. Haber türü renkleri `--tc-*`, platform renkleri `--pl-*` üzerinden ortak kartlara aktarılır. Oyuna özel değerler `tools/oyun_tema.py` → `oyun-tema.css` → oyun/rehber/kapak bileşenleri yolunu izler; üretilen CSS elle düzenlenmez.

## Colors

Yukarıdaki koyu tema renkleri `--zemin`, `--yuzey`, `--yazi`, `--soluk`, `--secim`, `--tc-haber`, `--tc-guncelleme`, `--tc-indirim`, `--nane`, `--kehribar`, `--kirmizi` ile eşleşir. Açık temada zemin `#F3F5F9`, yüzey `#FFFFFF`, metin `#152238`, seçim `#2453D8` olur; haber türleri daha koyu renklerle aynı anlamı korur. Doğrulandı/Doğrulanmadı/Yalanlandı durumu renge ek olarak metin, çerçeve ve damgayla belirtilir.

## Typography

Ana aile yerel Archivo'dur: gövde `--text-base` 1.0625rem / `--leading-body` 1.65; kart başlığı `--text-card` 1.25rem / 1.3; ikincil metin `--text-sm` .9rem; meta `--text-xs` .78rem. `--text-section` 1.6–2.25rem; başlık ağırlıkları 750–800. Oyuna özgü yerel OFL aileleri merkez ve rehber başlıklarında korunur. Latin, Türkçe, Fransızca ve İspanyolca glifleri desteklenir. Uzun başlık ve oyun adları satır kırar; başlıklarda kesme/ellipsis yoktur.

## Layout

`.wrap` ve `.ust-ic` en fazla `--page-max` 1536px; `--page-pad` 20–48px. `--space-1…9` ölçeği 4, 8, 12, 16, 24, 32, 48, 72, 96px; kart arası/içi 24px, ana bölüm arası 72px. Telefonda bölüm arası 48px ve kart içi 22px. Uzun okuma metinleri 68–78ch ile sınırlıdır. Bu değerler CSS'ten belgelenir (Model B); belge bağımsız CSS üretmez.

Ana sayfada kısa giriş + sağda klavye kısayolları, gündem, takip, haberler/fırsatlar, popüler, radar, yaklaşan çıkışlar ve GTA bandı bulunur. Yaklaşan çıkışlar 1440px'te üç, 1600px üstünde dört sütundur; takvim aylara göre aynı kartları kullanır. Yan filtreli kart ızgaraları 1350px altında iki, 640px altında tek sütuna iner. 960px altında filtre açılır; haber listesi görünüm tercihini saklar. Telefonda iki görünüm de tam genişlikte okunur karttır.

Görseller 16:9 alan ayırır; öne çıkan haber 2.15:1 olabilir. 460×215 Steam görselleri takvim/oyun kartlarında 460px'i aşmaz. Merkez başlık görseli en fazla 460px'tir ve varsa `genis` adresini kullanır. Büyük rehber vitrini için geniş kayıt yoksa gerçek görsel, üretilmiş kapağın üzerinde kendi çözünürlüğünde ortalanır. Görsel yüklenmezse aynı alandaki SVG kapak kalır.

## Elevation & Depth

Yüzeyler ince, nötr sınırlarla ayrılır. Anlam renkleri bölüm işareti, rozet ve durumlarda kullanılır; çevresel ışıma yoktur. Gölgeler klavye tuşunda ve arama penceresinde tutulur. Hover başlık alt çizgisini veya sınır rengini değiştirir; metin ölçüsü değişmez. Arama penceresi odağı tutan üst katmandır.

## Shapes

Paneller 16px, tuşlar 6px yarıçaplıdır. Oyuna özgü rehber kutuları tema üreticisinden gelir. Söylenti kartları durumlarına göre düz, kesik veya noktalı kenar kullanır.

## Components

Haber kartı: kaynak görseli ve görünür küçük atıf, ardından meta, tam başlık, özet ve haber kaynağı. Çıkış kartı: 16:9 kapak üzerinde tarih tuşu, altında `.cikis-adi`, kalan gün, tür/platform, geliştirici/yayıncı/kaynak, ayrı alt satırda takip ve ICS. Eski `.c-ad` sınıfı kaldırılmıştır; başlık görünürlüğü reklam benzeri bir sınıfa veya animasyona bağlanmaz. Kaynak görseli yoksa özgün SVG kapak; söylentide daima özgün kapak kullanılır. Filtrelerde tüm durumlar ve toplam adetleri sıfır olsa da görünür; sonuç sayısı canlı duyurulur ve boş durum filtreyi değiştirmeye yönlendirir. Düğmeler `site.js` içinde `data-*` işaretleriyle bağlanır; inline onclick gerektirmez.

Ctrl+K ve / aramayı açar, Escape kapatır. Tema ve görünüm tercihleri yerel saklanır. İçerik kaydırma animasyonu beklerken gizlenmez. Hareket azaltma tercihinde ortam animasyonları, kaydırma ve kart hareketleri kapanır. Gündem şeridi ayrıca durdurulabilir. Odak göstergesi görünür ve dokunma hedefleri en az 44px'dir.

## Do's and Don'ts

Her söylentinin kaynak ve doğrulama durumu görünür kalmalı. Kaynak görseli başarısız olduğunda kırık görsel simgesi bırakma. Neon renklerini gövde metninin arkasında okunurluğu azaltacak şekilde kullanma. Yeni oyun temalarını merkezi üreticide tanımla; dil veya sayfa başına bağımsız CSS kopyaları üretme.

## 2026-11-16 tasarım uzlaştırması

Önceki 1200px genişlik, renkli kart çerçeveleri, haber üstü başlıklar ve küçük takvim satırları Cio'nun yeniden tasarım isteğiyle değiştirildi. Yeni ölçülerin sahibi `style.css :root`; oyun başlığı/kapak düzeninin sahibi `tools/oyun_tema_temel.css` → `tools/oyun_tema.py` → üretilen `oyun-tema.css`. Yeni kütüphane, CDN veya yazı tipi eklenmedi. İçerik verisi değiştirilmedi.
