---
version: v2
name: CTRL+A GAME
description: Gerçek oyun görselleri, editoryal bilgi hiyerarşisi ve klavye kimliğiyle yedi dilli oyun haber portalı.
colors:
  background: '#0B101B'
  band: '#101726'
  surface: '#151E2E'
  surface-alt: '#1D293D'
  border: '#263449'
  text: '#F1F5FC'
  muted: '#9FB0C8'
  primary: '#2D5CE0'
  link: '#79A6FF'
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
  panel: '12px'
  key: '6px'
spacing:
  page-max: '1280px'
  card-gap: '20px'
  card-padding: '20px'
  section: '48px'
components:
  spotlight: {}
  news-stream: {}
  news-card: {}
  rumor-card: {}
  filter: {}
  command-palette: {}
---

# CTRL+A GAME tasarım sistemi

## Overview

Türkçe, İngilizce, Fransızca, İspanyolca, Almanca, Felemenkçe ve Basitleştirilmiş Çince statik oyun haber portalı. Editoryal v2 yönü: küresel oyun medyasının (IGN, GameSpot, Eurogamer, PC Gamer) kanıtlanmış bilgi mimarisiyle CTRL+A GAME marka kimliğini (fiziksel klavye tuşu logosu, Ctrl+A seçim vurgusu, koyu varsayılan tema) birleştirir. İlk ekranda doğrudan günün manşetleri yer alır; bölümler belirgin başlık şeritleri ve dönüşümlü arka plan tonlarıyla ayrılır. Görsel üzerine haber başlığı bindirilmez. Oyun merkezleri ve rehberler oyunun temasını korur; ortak dizin ve haberlerde yerel Archivo hiyerarşisi kullanılır.

Token sahibi mevcut çalışma kodudur (Model B). Bu belge değerleri açıklar; CSS üretmez. `style.css :root` koyu tema temel renk, boşluk ve ölçülerinin; `[data-tema="acik"]` açık temanın sahibidir. Haber türü renkleri `--tc-*`, platform renkleri `--pl-*` üzerinden ortak bileşenlere aktarılır. Oyuna özel değerler `tools/oyun_tema.py` → `oyun-tema.css` → oyun/rehber/kapak bileşenleri yolunu izler; üretilen CSS elle düzenlenmez.

## Colors

Koyu tema varsayılandır (`#0B101B` zemin, `#101726` dönüşümlü bant, `#151E2E` kart yüzeyi, `#1D293D` ikincil yüzey, `#263449` sınır). Sistemin `prefers-color-scheme: light` tercihi varsayılan koyu kimliği ezmez; ziyaretçi isterse üst çubuktaki düğmeyle açık temaya geçebilir ve tercih `localStorage` içinde saklanır. Açık temada zemin `#F5F7FB`, bant `#EBF0F8`, yüzey `#FFFFFF`, metin `#111C2E`, soluk `#4B5D77`, seçim `#1E4AD1` olur. Tüm metin/arka plan çiftleri ve beyaz-üzeri-seçim (`#fff` / `#2D5CE0` koyuda ≥5.5:1, `#fff` / `#1E4AD1` açıkta ≥7.5:1) WCAG AA karşıtlık eşiğini sağlar. Doğrulandı/Doğrulanmadı/Yalanlandı durumu renge ek olarak metin, kenarlık türü ve damgayla belirtilir.

## Typography

Ana yazı tipi yerel `fonts/archivo.woff2` (harici CDN yok): gövde `--text-base` 1rem / `--leading-body` 1.65 (haber metninde 1.08rem / 1.82); kart başlığı `--text-card` 1.15rem / 1.3; ikincil metin `--text-sm` .9rem; meta `--text-xs` .78rem; bölüm başlığı `--text-section` 1.35–1.75rem. Başlık ağırlıkları 750–800. Oyuna özgü yerel OFL aileleri merkez ve rehber başlıklarında korunur. Çince için `PingFang SC`, `Microsoft YaHei`, `Noto Sans CJK SC` sistem yedekleri kullanılır. Uzun haber ve oyun başlıkları satır kırar; başlıklarda kesme/ellipsis veya `line-clamp` yoktur.

## Navigation & Information Architecture

Üst menü en çok 6 ana başlıktan oluşur (`tools/site_derle.py`): **Haberler**, **Oyunlar**, **Fırsatlar ▾** (İndirimler + Ücretsiz açılır alt menü ve sayfa içi alt sekmeler), **Takvim**, **Rehberler**, **Söylentiler**. Belirli bir oyun (GTA VI) üst menüde ayrı sekme olarak yer almaz; GTA VI sayfaları silinmeden ve adresleri değişmeden Oyunlar merkezi (`oyun/gta-6.html`), Rehberler, alt bilgi (`alt_gta` sütunu) ve Ctrl+K araması üzerinden erişilir. `.dosya-nav` ikinci şeridi yalnız GTA VI sayfalarının içinde görünür.

## Layout

`.wrap` ve `.ust-ic` en fazla `--page-max` 1280px; `--page-pad` 16–32px. Yapışkan üst çubuk masaüstünde 68px, 960px altında 62px yüksekliğindedir. Bölüm arası boşluk 48px (mobilde 36px); tam genişlikte bölümler `--zemin` ve `--zemin-bant` (`.bant-ton`) arasında dönüşerek görsel olarak ayrılır. Her bölüm başlığı (`.bolum-bas`, `.blok-bas`) sol vurgu çubuğu, alt çizgi ve sağda "tümünü gör" bağlantısı taşır.

Ana sayfa akışı:
1. **Gündem şeridi** (`.gundem`): 46px tek satır kayan başlıklar + durdurma düğmesi.
2. **Kompakt başlık şeridi** (`.vitrin-ust`): tek satırda site başlığı/kısa açıklama ve 3 haftalık durum göstergesi (haber, çıkış, ücretsiz).
3. **Manşet vitrini** (`.manset`, `.bant-ton` tonu): ilk ekranda solda 1 büyük 16:9 ana manşet (`.manset-ana`), sağda 4 ikincil haberlik yığın (`.manset-yan` / `.mk`).
4. **Kişisel takip bloğu** (`.takip-blok`, yalnız takip edilen oyun varsa açılır).
5. **İki sütun editoryal çekirdek** (`.ana-izgara`, `1fr 340px`): solda tarih sıralı **Son haberler** yatay akışı (`.haber-akis` / `.akis-satir`: 236px 16:9 küçük resim solda, meta + başlık + 2 satır özet + kaynak sağda, altta "Bütün haberler →"); sağ sütunda (`.yan-kol`) sırasıyla **Popüler oyunlar** (01–05 numaralı liste), **Yaklaşan çıkışlar** (en yakın 5 çıkış), **Günün fırsatları** (5 canlı/yerel fırsat) ve **Ücretsiz oyunlar** (Epic).
6. **Tam genişlikli dönüşümlü alt bantlar**: **Popüler oyunlar** (`.bant-ton`, 4×2 ızgara), **Söylenti radarı** (3 sütun), **Yaklaşan çıkışlar** (`.bant-ton`, 3×2 simetrik 6 kartlık ızgara).

Haber detay sayfası (`.haber-detay`): üstte `.o-iz` kırıntı izi (`Ana sayfa / Haberler / Oyun`), ardından başlık + özet + tarih/kaynak/takip şeridi (`.hd-bas` / `.hd-meta-cubuk`, max 820px), altında geniş 16:9 kapak görseli (`.hd-kapak`, max 960px), altında tek sütun 68ch okuma metni (`.hd-govde`, max 720px; dikey video varsa `.hd-vid` 2 sütuna geçer), altında kaynak/paylaşım/etiket kutuları (`.hd-yan`), en altta tam genişlikte 3 sütun **İlgili haberler** (`.ilgili` / `.hi-ilgili`).

Duyarlı kırılımlar: ≤1160px sıkılaştırılmış masaüstü, ≤960px tek sütun ana akış + 2 sütun yan paneller + sabit mobil alt menü, ≤640px (360px dahil) tam tek sütun, yatay taşmasız, ≥44px dokunma hedefli düzen.

## Elevation & Depth

Yüzeyler net, nötr sınırlarla (`--cizgi`, `--cizgi-guclu`) ve bant tonu ayrımıyla katmanlanır. Gölgeler yalnız klavye tuşlarında, açılır menülerde ve arama penceresinde tutulur. Hover başlık rengi/alt çizgisi, sınır tonu veya görselde hafif `scale(1.03)` değişimi uygular; metin ölçüsü değişmez.

## Shapes

Paneller 12px, tuşlar ve düğmeler 6px, akış/manşet küçük resimleri 6–8px yarıçaplıdır. Fırsat alt sekmeleri ve kategori/platform çipleri tam yuvarlak (999px) biçimdedir. Söylenti kartları durumlarına göre düz (doğrulandı), kesik (doğrulanmadı) veya noktalı (yalanlandı) kenar kullanır.

## Components

- **Manşet ve akış satırı**: gerçek 16:9 görsel (yoksa üretilmiş SVG kapak), altında veya yanında kategori/oyun/platform metası, tam başlık, özet ve kaynak. İlk ekran manşet görseli ve haber detay kapağı `loading="eager"` + `fetchpriority="high"` ile yüklenir; ekran altı görseller `loading="lazy"` kullanır.
- **Çıkış kartı**: 16:9 kapak üzerinde tarih tuşu, altında `.cikis-adi`, kalan gün, tür/platform, geliştirici/yayıncı/kaynak, alt satırda takip ve ICS.
- **Filtre ve arama**: Ctrl+K ve `/` arama paletini açar, Escape kapatır. Düğmeler `site.js` içinde `data-*` işaretleriyle bağlanır; inline `onclick` kullanılmaz. İçerik kaydırma animasyonuna bağlı gizlenmez.

## Do's and Don'ts

- Her söylentinin kaynak ve doğrulama durumu görünür kalmalı.
- Kaynak görseli başarısız olduğunda kırık görsel simgesi bırakma; SVG kapak görünür kalmalı.
- Tekil oyunlar (GTA VI vb.) üst menüde ayrı sekme açmaz; Oyunlar dizini, alt bilgi ve arama üzerinden erişilir.
- Başlıklarda `line-clamp` veya metin kesme kullanma; uzun başlıklar tüm dillerde tam satır kırar.
- Yeni oyun temalarını merkezi üreticide (`tools/oyun_tema.py`) tanımla; harici CDN veya font ekleme.

## 2026-11-22 editoryal yeniden tasarım (tasarim-v2)

Cio'nun geri bildirimi doğrultusunda üst menü 6 ana başlığa indirildi (GTA 6 sekmesi kaldırıldı, sayfaları ve URL'leri korundu), ana sayfa üstündeki büyük kısayol duvarı yerine kompakt başlık şeridi + 1 büyük / 4 küçük manşet vitrini + kronolojik yatay haber akışı + dengeli sağ yan sütun + dönüşümlü tam genişlikli bantlar kuruldu; haber detay sayfası kırıntı izli tek sütun okuma düzenine geçirildi; koyu tema gerçek varsayılan yapıldı ve sayfa genişliği 1280px'e dengelendi. Yeni kütüphane, CDN veya dış yazı tipi eklenmedi; tüm SEO/JSON-LD/hreflang/URL sözleşmeleri korundu.

## Dil önerisi

`data/diller.json` dil adı, URL, arayüz metni ve tarih biçimlerinin sahibidir. Dil önerisi mevcut `--yuzey-2` ve `--yazi` renklerini kullanır; sayfa üstünde ince bir şerittir. Tarayıcının ilk desteklenen dili mevcut sayfadan farklıysa yalnız o sayfanın gerçek karşılığı önerilir. Otomatik yönlendirme ve ülke/IP sorgusu yoktur. Açma veya kapatma tercihi `localStorage` içinde hatırlanır; klavyeyle erişilen bağlantı ve en az 44px kapatma düğmesi kullanılır.
