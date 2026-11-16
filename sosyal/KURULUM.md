# Sosyal hesap kurulumu: Cio'nun yapacakları

Sistem kurulu. Claude her gün teyitli oyun haberlerini siteye ekliyor; GitHub günde 5 kez
(TR saatiyle 10:17, 13:17, 16:17, 19:17 ve 22:17) yeni haberleri hesaplara paylaşıyor. Her
gönderi sitedeki haber sayfasına bağlanıyor. Sayfa, ziyaretçinin tarayıcı diline
(TR, EN, FR veya ES) kendiliğinden geçiyor.

Senin yapacağın tek şey hesapları açıp anahtarları kurulum yardımcısına yapıştırmak.
Yardımcı anahtarları dener, doğruysa GitHub'a gizli olarak kaydeder.

> **Askıda (Cio'nun kararı, 2026-11-14):** şimdilik yalnız Instagram kullanılıyor. X ve Reddit bölümleri ileride açmak için duruyor; açarken Claude'a "X'i/Reddit'i aç" de (`sosyal/ayarlar.json`).

**Durum:** Haberler dört dilde (TR, EN, ES, FR) yayınlanır. Kartlar, açıklamalar ve videolar dört dil için de
şimdiden üretilir. Şu an yalnız TR hesabının anahtarları kurulu; EN, ES ve FR hesapları açılıp anahtarları
eklenince paylaşım kod değişmeden o dilde de başlar (bkz. 6. bölüm).

**E-posta ipucu:** her hesap ayrı e-posta ister. Gmail'de `adın+gtatr@gmail.com` gibi `+`
eklenmiş adresler aynı kutuya gelir; çoğu site bunu kabul eder.

Menü adları değişmiş olabilir. Bir adım ekrandakiyle uyuşmazsa ekran görüntüsünü Claude'a
at, birlikte bakarız.

---

## 1. X (Twitter): ASKIDA

1. x.com'da hesabı aç (ad önerisi: "GTA VI Rehber" / "Game News Hub").
   - Profilde Ayarlar → Hesabın → **Otomatik hesap (Automated)** etiketini aç. X kuralı
     böyle istiyor.
   - Profil bağlantısına site adresini yaz.
2. **developer.x.com**'a aynı hesapla gir ve geliştirici hesabını oluştur. Bir **Project**
   ve içinde bir **App** aç.
3. App ayarlarında **User authentication settings** → **App permissions: Read and write**.
   - Bu adımı anahtarları üretmeden ÖNCE yap. Sonra yaparsan anahtarları yeniden üretmen
     gerekir.
   - Callback/Website alanına site adresini yazabilirsin.
4. **Keys and tokens** sekmesinden 4 değeri al: API Key, API Key Secret, Access Token,
   Access Token Secret.
5. **Ücret:** X API artık kullandıkça ödemeli (kaynak: docs.x.com/x-api/getting-started/pricing,
   2026-11-14 kontrolü).
   - Bağlantılı gönderinin tanesi yaklaşık 0,20 $. Günde 2 gönderi, hesap başına ayda
     ~12 $ eder.
   - Developer Console'da kredi yükle ve **aylık harcama sınırı** koy (ör. 15 $).
   - Daha ucuz seçenek: Claude'a "X bağlantıyı profile koysun" de.
     - Gönderinin tanesi ~0,015 $ olur.
     - Gönderide bağlantı yerine "ayrıntılar profildeki bağlantıda" yazar.

## 2. Reddit: ASKIDA

1. reddit.com'da hesap aç. **İki adımlı doğrulamayı (2FA) açma**, açarsan otomatik giriş
   çalışmaz.
2. Hesabı birkaç gün normal kullan (yorum, oy). Yeni hesapların bağlantıları sık sık
   spam'e düşer.
3. **API izni:** Reddit 2025 sonundan beri yeni API kullanımını önce onaylıyor (ikinci el
   kaynaklar; resmî sayfa kontrol sırasında açılmadı).
   - reddit.com/prefs/apps sayfasına gir. Onay formuna yönlendirirse kullanım amacını
     yaz: "Kendi profilime günde 1-2 oyun haberi bağlantısı paylaşan kişisel betik".
   - Cevap yaklaşık 1 hafta sürebilir.
4. İzin gelince aynı sayfada **create app**.
   - Tür: **script**.
   - redirect uri: `http://localhost:8080`.
   - Uygulama adının altındaki kısa yazı **client id**, "secret" satırı **client secret**.
5. Gönderiler hesabın **kendi profiline** gider, başka topluluklara değil (reklam kuralı
   sorunu olmasın diye).

## 3. Instagram: her dil için ayrı hesap

1. Instagram hesabını aç.
2. Ayarlar → Hesap türü → **Profesyonel hesaba geç**. Üretici (Creator) ya da İşletme
   (Business) seç.
3. Profil bağlantısına haber sayfasını yaz:
   - TR: `https://ctrl-agame.com/oyun-haberleri.html`
   - EN: `https://ctrl-agame.com/en/game-news.html`
   - FR: `https://ctrl-agame.com/fr/actus-jeux.html`
   - ES: `https://ctrl-agame.com/es/noticias-juegos.html`
4. **developers.facebook.com** → My Apps → **Create app**. Tür: Business veya "Other",
   sonra Business.
5. Uygulamaya **Instagram** ürününü ekle → **API setup with Instagram business login** →
   hesabını ekle → hesabın yanındaki **Generate token**.
   - Çıkan uzun yazı erişim anahtarıdır, 60 gün geçerli.
   - Yardımcı onu bu bilgisayarda şifreli saklar ve her pazartesi kendiliğinden uzatır.
   - Bilgisayar 60 gün hiç açılmazsa anahtarı yeniden üretip yardımcıya girmen gerekir.

## 4. Anahtarları gir (her hesap için bir kez)

1. Dosya Gezgini'nde `C:\Cihan.Ai\03-Web\rockstargtavi\sosyal\kurulum.bat` dosyasına çift
   tıkla.
2. **1) Hesap ekle** → dil → platform → istenen değerleri yapıştır. Gizli alanlarda yazı
   görünmez, bu normal.
3. "TAMAM" yazısını gör. Hata çıkarsa ekran görüntüsünü Claude'a at (şifreler görünmez).
4. **2) Hangi hesaplar kurulu?** ile kontrol et.
5. **3) Deneme çalıştırması** gönderi atmadan neyin paylaşılacağını gösterir. Sonucu
   github.com/cihanszgn/rockstargtavi/actions sayfasında görürsün.

## 5. Haber videoları: YouTube Shorts ve Instagram Reels

Videolar kendiliğinden üretilir (`video.yml`) ve sitede haberin üstünde oynar. Dört dilde de üretilir; günlük
kota dil başınadır (her dil için en çok 2 video). Aynı videoyu Instagram Reels'e ve YouTube Shorts'a yollamak için
aşağıdakiler gerekir. Hesabın anahtarı yoksa o hesap atlanır (paylaşım çıktısında "anahtar yok, atlandı" yazar),
site videoları yine çalışır.

**Hangi haber video alır:** hype puanı eşiğe (`sosyal/ayarlar.json` → `video.hype_esigi`, şu an 7) ulaşan haber her
dilde görsel gönderi + Reels + Shorts alır. Eşiğin altındaki haber yalnız görsel gönderi alır.

**Instagram Reels için ekstra bir şey yok:** 3. bölümdeki Instagram hesabı yeter. Sonra Claude'a
"Reels'i aç" de (`sosyal/ayarlar.json` içinde o dilin `instagram_reel` değeri `true` olur).

### 5.1 YouTube kanalı ve Google Cloud projesi (bir kez)

Menü adları zamanla değişir. Ekrandakiyle uyuşmayan adım olursa **ekran görüntüsü at,
birlikte bakalım**.

1. youtube.com'da kanalı aç (dil başına ayrı kanal ister, ilk adım için tek kanal yeter).
   Kanalın bağlı olduğu Google hesabını not et.
2. **console.cloud.google.com** adresine aynı hesapla gir. Üstteki proje seçiciden **Yeni proje**
   aç (ad: "ctrl-agame video").
3. Sol menüden **APIs & Services → Library** (Kitaplık) → **YouTube Data API v3** → **Enable**
   (Etkinleştir).
4. **APIs & Services → OAuth consent screen** (İzin ekranı):
   - Kullanıcı türü **External** (Harici).
   - Uygulama adı ve e-posta alanlarını doldur, kaydet.
   - **ÇOK ÖNEMLİ: Publishing status (Yayın durumu) "In production" olmalı.** "Testing"
     (Test) modunda kalırsa Google yenileme anahtarını **7 günde** öldürür ve paylaşım bir hafta
     sonra sessizce durur. "Publish app" (Uygulamayı yayınla) düğmesine bas. Doğrulama
     isteyen bir uyarı çıkabilir. Yalnız kendi hesabın kullanacağı için doğrulamayı
     beklemeden devam edebilirsin; giriş sırasında "Google bu uygulamayı doğrulamadı"
     uyarısı çıkar, **Advanced → Go to (unsafe)** de.
5. **APIs & Services → Credentials → Create credentials → OAuth client ID**:
   - Application type: **Desktop app**.
   - Çıkan **Client ID** ve **Client secret** değerlerini bir yere kopyala (birazdan
     yapıştıracaksın).
6. Not: yeni kanalın kısa video yükleme kotası günlük sınırlıdır; sistem her dil kanalına günde en çok 2
   Short yükler (`gunluk_en_fazla.youtube`).

### 5.2 Anahtarı yardımcıya ver

1. `C:\Cihan.Ai\03-Web\rockstargtavi\sosyal\kurulum.bat` dosyasına çift tıkla.
2. Menüden **YouTube kanalı bağla (Shorts)** → dil → Client ID ve Client secret'ı yapıştır
   (ekranda görünmez, bu normal).
3. Tarayıcı açılır: kanalın Google hesabıyla gir, **İzin ver**'e bas. Sekmeyi kapat.
4. Yardımcı kanal adını gösterirse doğru demektir. Üç değeri (`YT_<DİL>_CLIENT_ID`,
   `YT_<DİL>_CLIENT_SECRET`, `YT_<DİL>_REFRESH_TOKEN`) GitHub'a gizli yazar.
5. Videolar önce **özel (private)** yüklenir. YouTube Studio'da bir video açıp bak. Memnunsan
   Claude'a "YouTube gizliliğini public yap" de.
6. Her dil için ayrı Google/YouTube hesabı kullanacaksan 2. ve 3. adımı dil başına tekrar et.

### 5.3 Azure Speech anahtarı (video sesi için)

1. portal.azure.com'da hesapla gir (ücretsiz katman yeter: ayda 500 bin karaktere kadar).
2. **Create a resource → Speech** (Konuşma hizmeti) → bölge seç (ör. West Europe) → fiyat
   katmanı **Free F0** → oluştur.
3. Kaynağa gir → **Keys and Endpoint**: **KEY 1** ve **Location/Region** (örn. `westeurope`)
   değerlerini al.
4. `kurulum.bat` → **Azure Speech anahtarı ekle** → anahtarı ve bölgeyi yapıştır.
   Yardımcı dener, doğruysa `AZURE_SPEECH_KEY` ve `AZURE_SPEECH_REGION` olarak GitHub'a yazar.
5. Anahtar yoksa videolar üretilmez, site eskisi gibi çalışır.
6. Video sesi dil başına **3 sesli liste**dir (`sosyal/ayarlar.json` → `video.konusmaci`, dil → ses listesi; her listede
   sırayla erkek, **kadın**, erkek). Hangi sesin okuyacağı haber kimliğinden türeyen sabit sayıyla seçilir: aynı haber
   her çalışmada aynı sesi alır, farklı haberler üç sese dağılır. TR listesi `tr-TR-Aydin:MAI-Voice-2.1` (mevcut ses),
   `tr-TR-EmelNeural` (kadın), `tr-TR-AhmetNeural`. Hazır diller: tr, en, es, fr, de, nl, zh. Değiştirmek için o dilin
   satırını düzelt; listede dili tutmayan ses ya da boş liste varsayılan sese düşer. Yerel önizlemede (`--ses edge`)
   Edge'de olmayan MAI sesi atlanır. Azure'da bölgenin ses adını tanımadığı durum (örn. kaldırılmış ad) üretimi durdurur;
   ayarda adı değiştirmek yeter.

## 6. Yeni dil hesabı nasıl eklenir

Dil başına kod, ayar veya iş akışı değişikliği gerekmez; yalnız hesabı açıp anahtarı girersin.

1. O dilin Instagram hesabını (3. bölüm) ve YouTube kanalını (5.1) aç. EN, ES, FR için `sosyal/ayarlar.json`
   içinde `instagram`, `instagram_reel` ve `youtube` zaten `true`; X ve Reddit askıda olduğu için `false`.
2. `kurulum.bat` → **Hesap ekle** → dili ve platformu seç, değerleri yapıştır. Yardımcı anahtarları GitHub'a şu
   adlarla yazar (`<DİL>` = TR, EN, ES veya FR):
   - Instagram: `IG_<DİL>_USER_ID`, `IG_<DİL>_TOKEN`
   - YouTube: `YT_<DİL>_CLIENT_ID`, `YT_<DİL>_CLIENT_SECRET`, `YT_<DİL>_REFRESH_TOKEN`
   - `.github/workflows/sosyal.yml` bu adların dört dil için de olanlarını zaten okur.
3. Sonraki paylaşım çalışmasında o dilin hesabı kendiliğinden devreye girer. **Deneme çalıştırması** (`--dry-run`)
   anahtarı olmayan hesapları "anahtar yok, atlandı" diye listeler; anahtar eklenince o satır kaybolur.
4. Kartlar ve videolar zaten üretildiği için eski görsellerin yeniden üretilmesi gerekmez. Paylaşım penceresi
   (son 3 gün) içindeki haberler yeni hesaba da gider.

## Nasıl çalışıyor (bilgi için)

- Haberler: `data/icerik.json`. Claude her gün 10:00'da resmî kaynaktan teyit edip ekler.
  `tools/sosyal_derle.py` sayfaları, paylaşım görsellerini, RSS'i ve site haritasını üretir.
- Paylaşım: `.github/workflows/sosyal.yml` → `tools/sosyal_yayinla.py`.
  - Son 3 günün paylaşılmamış haberleri gider.
  - Her hesap için her çalışmada 1 gönderi, günde en çok 2 gönderi atılır
    (`sosyal/ayarlar.json`; sınır dil başınadır).
  - Görsel gönderi her haberde gider. Reels ve Shorts yalnız hype puanı eşiğe ulaşan haberde gider.
  - Gönderilenler `sosyal/gonderilenler.json`'a yazılır, aynı haber iki kez gitmez.
- Anahtarı girilmemiş hesap atlanır ("anahtar yok, atlandı"). Bir hesap hata verirse GitHub sana "failed" e-postası
  atar; o e-postayı Claude'a göster.
- Videolar: `.github/workflows/video.yml` yeni haberler için `tools/video_uret.py` ile video üretir ve
  `data/videolar.json`'a yazar. Paylaşım yalnız video hazır olunca (`sosyal.yml`) Reels/Shorts olarak gider.
  - Her paylaşımdan önce kayda "niyet" yazılır. Yanıtı kaybolan bir paylaşım kendiliğinden yeniden
    DENENMEZ; platformdan sorgulanır, bulunamazsa `sosyal/gonderilenler.json`'da `elle_bak` olur.
    Platformda gönderiye bak: varsa kaydı `tamam` yap, yoksa o kaydı sil, sistem yeniden dener.
