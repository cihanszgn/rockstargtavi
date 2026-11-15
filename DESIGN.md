---
version: alpha
name: CTRL+A GAME
description: Oyun haberleri ve oyuna özel rehberler için renkli, klavye tuşlarından esinlenen portal.
colors:
  background: '#0B1322'
  surface: '#121C30'
  text: '#E9EEF8'
  muted: '#9AA8C3'
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
  panel: '14px'
  key: '6px'
spacing:
  page-max: '1200px'
components:
  news-card: {}
  rumor-card: {}
  filter: {}
  command-palette: {}
---

# CTRL+A GAME tasarım sistemi

## Overview

Türkçe, İngilizce, Fransızca ve İspanyolca oyun portalı. Kullanıcı oyun haberlerini, fırsatları, söylenti durumlarını ve kendi oyununun rehberini kolayca bulur. Cio'nun kabul ettiği yön: canlı oyuncu estetiği, gerçek haber görselleri ve her oyuna özel tema. İmza, Ctrl+A seçim vurgusu ve fiziksel klavye tuşlarıdır; uzun rehber metinleri sakin ve okunabilir kalır.

Token sahibi mevcut çalışma kodudur (Model B). Bu belge değerleri açıklar; CSS üretmez. `style.css :root` temel renk, boşluk ve ölçülerin; `[data-tema="acik"]` açık temanın sahibidir. Haber türü renkleri `--tc-*`, platform renkleri `--pl-*` üzerinden ortak kartlara aktarılır. Oyuna özel değerler `tools/oyun_tema.py` → `oyun-tema.css` → oyun/rehber/kapak bileşenleri yolunu izler; üretilen CSS elle düzenlenmez.

## Colors

Yukarıdaki koyu tema renkleri `--zemin`, `--yuzey`, `--yazi`, `--soluk`, `--secim`, `--tc-haber`, `--tc-guncelleme`, `--tc-indirim`, `--nane`, `--kehribar`, `--kirmizi` ile eşleşir. Açık temada zemin `#EDF1F7`, yüzey `#FFFFFF`, metin `#0E1A30`, seçim `#2453D8` olur; haber türleri daha koyu renklerle aynı anlamı korur. Doğrulandı/Doğrulanmadı/Yalanlandı durumu renge ek olarak metin, çerçeve ve damgayla belirtilir.

## Typography

Ana aile yerel Archivo'dur: gövde 1.0625rem/1.6, başlıklar 700–800 ağırlık ve geniş karakterler. Rehberler kendi yerel OFL yazı tipini yükler; Latin, Türkçe, Fransızca ve İspanyolca glifleri korunur. Uzun haber başlıkları ve oyun adları satır kırar; önemli içerik yalnız araç ipucunda bırakılmaz.

## Layout

`.wrap` en fazla 1200px, yatay boşluk 16–32px. Masaüstü haber listesi filtre sütunu ve görselli ızgaradır; telefonda filtreler açılır, kartlar tek sütuna iner. Haber görünümü liste/ızgara tercihini saklar. Görseller sabit oranlı alan ayırır; yüklenmeyen görsel aynı alandaki oyuna özel kapağı açığa çıkarır.

## Elevation & Depth

Koyu yüzeyler, ince renkli kenarlar ve bölüm ışımaları oyuncu kimliğini oluşturur. Hover yalnız kartın küçük yer değiştirmesi ve gölgesini değiştirir; metin ölçüsünü değiştirmez. Arama penceresi odağı tutan üst katmandır.

## Shapes

Paneller 14px, tuşlar 6px yarıçaplıdır. Oyuna özgü rehber kutuları tema üreticisinden gelir. Söylenti kartları durumlarına göre düz, kesik veya noktalı kenar kullanır.

## Components

Haber kartı: kaynak görseli + görünür görsel kaynağı, tür rozeti, tarih, oyun, platform, başlık. Kaynak görseli yoksa özgün SVG kapak; söylentide daima özgün kapak kullanılır. Filtrelerde tüm durumlar ve toplam adetleri sıfır olsa da görünür; sonuç sayısı canlı duyurulur ve boş durum filtreyi değiştirmeye yönlendirir. Düğmeler `site.js` içinde `data-*` işaretleriyle bağlanır; inline onclick gerektirmez.

Ctrl+K ve / aramayı açar, Escape kapatır. Tema ve görünüm tercihleri yerel saklanır. Hareket azaltma tercihinde ortam animasyonları, kaydırma ve kart hareketleri kapanır. Gündem şeridi ayrıca durdurulabilir. Odak göstergesi görünür ve dokunma hedefleri en az 44px'dir.

## Do's and Don'ts

Her söylentinin kaynak ve doğrulama durumu görünür kalmalı. Kaynak görseli başarısız olduğunda kırık görsel simgesi bırakma. Neon renklerini gövde metninin arkasında okunurluğu azaltacak şekilde kullanma. Yeni oyun temalarını merkezi üreticide tanımla; dil veya sayfa başına bağımsız CSS kopyaları üretme.
