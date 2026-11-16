# Sosyal hesap kurulumu: Cio'nun yapacakları

Sistem kurulu. Haber hattı teyitli oyun haberlerini siteye ekliyor; GitHub her saatin 17. dakikasında
paylaşım kuyruğunu işler (`17 * * * *`, UTC). GitHub zamanlı işleri gecikebilir; bu bir dakika garantisi değildir.
Her gönderi sitedeki ilgili sayfaya bağlanır. Haber sayfası, ziyaretçinin tarayıcı diline
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
kota dil başınadır (her dil için en çok 4 video). Aynı videoyu Instagram Reels'e ve YouTube Shorts'a yollamak için
aşağıdakiler gerekir. Hesabın anahtarı yoksa o hesap atlanır (paylaşım çıktısında "anahtar yok, atlandı" yazar),
site videoları yine çalışır.

**Hangi haber video alır:** hype puanı eşiğe (`sosyal/ayarlar.json` → `video.hype_esigi`, şu an 5) ulaşan haber
geçerli senaryo ve hazır/onaylı video varsa Reels ve Shorts adayıdır. Instagram'da aynı çalışmada
en çok bir gönderi seçilir; hazır Reel önceliklidir, yoksa görsel seçilir. Eşiğin altındaki haber yalnız görsel adayıdır.

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
6. Not: yeni kanalın kısa video yükleme kotası günlük sınırlıdır; sistem her dil kanalına günde en çok 4
   Short yükler (`gunluk_en_fazla.youtube`).

### 5.2 Anahtarı yardımcıya ver

1. `C:\Cihan.Ai\03-Web\rockstargtavi\sosyal\kurulum.bat` dosyasına çift tıkla.
2. Menüden **YouTube kanalı bağla (Shorts)** → dil → Client ID ve Client secret'ı yapıştır
   (ekranda görünmez, bu normal).
3. Tarayıcı açılır: kanalın Google hesabıyla gir, **İzin ver**'e bas. Sekmeyi kapat.
4. Yardımcı kanal adını gösterirse doğru demektir. Üç değeri (`YT_<DİL>_CLIENT_ID`,
   `YT_<DİL>_CLIENT_SECRET`, `YT_<DİL>_REFRESH_TOKEN`) GitHub'a gizli yazar.
5. YouTube görünürlüğü `sosyal/ayarlar.json → youtube.gizlilik` ile seçilir (mevcut değer `public`).
   İlk video onayı `data/videolar.json` içindeki mevcut onay düzeniyle ayrıca korunur.
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
6. Video sesi dil başına seçilir (`sosyal/ayarlar.json` → `video.konusmaci`, dil → ses adı haritası). TR sesi
   `tr-TR-Aydin:MAI-Voice-2.1`; EN, ES ve FR için doğal erkek nöral sesler tanımlı. Değiştirmek için o dilin
   satırını düzelt; harita dışı kalan dil varsayılan sese düşer.

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

- Haberler: `data/icerik.json`. Saatlik haber hattı kaynakları teyit edip ekler.
  `tools/sosyal_derle.py` sayfaları, paylaşım görsellerini, RSS'i ve site haritasını üretir.
- Paylaşım: `.github/workflows/sosyal.yml` → `tools/sosyal_yayinla.py`.
  - Son 3 günün paylaşılmamış haberleri önceliklidir; boşluklar aşağıdaki kuyruktan doldurulur.
  - Her dil/platform için her çalışmada en çok 1 gönderi; günlük görsel Instagram 24, Reels 4, Shorts 4
    (`sosyal/ayarlar.json`; sınır dil ve biçim başınadır, sosyal yayın günleri UTC'dir).
  - Instagram'da hazır/onaylı Reel önceliklidir, aksi halde görsel seçilir. Reels ve Shorts hype eşiğini korur.
  - Gönderilenler `sosyal/gonderilenler.json`'a yazılır, aynı haber iki kez gitmez.
- Anahtarı girilmemiş hesap atlanır ("anahtar yok, atlandı"). Bir hesap hata verirse GitHub sana "failed" e-postası
  atar; o e-postayı Claude'a göster.
- Videolar: `.github/workflows/video.yml` yeni haberler için `tools/video_uret.py` ile video üretir ve
  `data/videolar.json`'a yazar. Paylaşım yalnız video hazır olunca (`sosyal.yml`) Reels/Shorts olarak gider.
  - Her paylaşımdan önce kayda "niyet" yazılır. Yanıtı kaybolan bir paylaşım kendiliğinden yeniden
    DENENMEZ; platformdan sorgulanır, bulunamazsa `sosyal/gonderilenler.json`'da `elle_bak` olur.
    Platformda gönderiye bak: varsa kaydı `tamam` yap, yoksa o kaydı sil, sistem yeniden dener.

## Saatlik içerik kuyruğu ve ağsız deneme

`turler` nesnesindeki `haber`, `takvim`, `firsat`, `ucretsiz`, `rehber`, `arsiv` anahtarları
`true/false` ile açılıp kapanır. Sıra: taze haber → kesin tarihli çıkışa 30/14/7/3/1/0 gün
kalmış oyun → en yüksek indirimli uygun fırsat → şu anda ücretsiz oyun → rehber → arşiv.
Haber dışında aynı tür aynı hesapta art arda seçilmez; başka uygun tür yoksa o saat boş kalır.
Takvimde her tarih/kilometre taşı, fırsatta her `dealID`, ücretsiz oyunda her kampanya bir kez;
rehber aynı platform/dilde kayan 14 günde bir kez seçilir. Anahtar biçimi `konu|dil|platform|bicim` korunur.
Arşiv, o platform/dilde hiçbir biçimde paylaşılmamış kalıcı yama/çıkış haberleriyle sınırlıdır;
söylenti, sezon, etkinlik, kampanya içerenler elenir ve metin eski yayın tarihini belirtir.

Fırsat ve tarihsiz ücretsiz fiyat verisi `indirimler.json` / `ucretsiz.json` içinden, en çok 24 saatlik
önbellekten alınır; varsa bitiş tarihi de denetlenir. CheapShark'ın anlık verisi bitiş tarihi sağlamaz;
metin mağazada fiyat kontrolü ister. Epic kampanyasının başlangıç/bitişi ayrıca uygulanır.
Takvim/rehber/oyun kartları `oyun_gorselleri.json` kaydındaki resmî görseli ve küçük kaynak atfını kullanır;
kayıt yoksa veya indirme başarısızsa kapak üretilir. Kartlar 1080×1350 JPEG'dir. Dört dilde şablon metni,
tam sayfa adresi ve 3–6 etiket kullanılır; sosyal metin üretimi model çağırmaz.

```powershell
py tools/sosyal_yayinla.py --kuru --saat-benzet 24
py tools/sosyal_yayinla.py --kuru --saat-benzet 24 --baslangic 2026-11-16T19:00:00Z
```

Benzetim gerçek kayıt ve veriyi okuyup yalnız bellekte ilerler: sır okumaz, ağ çağırmaz, kayıt yazmaz.
Yalnız TR Instagram/YouTube hesapları varmış gibi davranır; hazır/onaylı olmayan videoyu var saymaz.
Her saatin dil/platform/biçim/tür/id seçimini ve tür sayılarını yazar; Instagram'da boş saat varsa çıkış kodu 1'dir.
Gerçek akış kartları üretir, kaydeder, mevcut Pages yayınının ilgili commit'le bitmesini bekler, sonra paylaşır;
anahtarsız hesapları tek özet satırında atlar. Sonlu kuyruk ve günlük kota saatlik paylaşımı kısıtlayabilir.

Eksik eski haber senaryolarını mevcut yerel Ollama yardımcısıyla küçük partilerde tamamlamak için:

```powershell
py tools/video_geri_doldur.py --kuru --dil tr --en-fazla 1
py tools/video_geri_doldur.py --dil tr --en-fazla 1 --model gemma3-4b
py tools/video_uret.py bekleyenler --dil tr --arsiv --gunluk
```

Gerçek geri doldurma yalnız eksik senaryoyu yazar; mevcut dosyayı ve haber verisini değiştirmez.
`modeller.json` içindeki yerel yardımcı/model çağrısını ve `video_uret.senaryo_hazirla` doğrulamasını kullanır;
bir düzeltme hakkından sonra geçersiz çıktı yazılmaz. Video render/yükleme/paylaşımı çalıştırmaz.
Sonraki video iş akışı kalıcı arşiv senaryolarını da işler; video üretim kotası dil başına 4'tür ve mevcut onay korunur.
