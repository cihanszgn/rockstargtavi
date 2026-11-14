# Sosyal hesap kurulumu: Cio'nun yapacakları

Sistem kurulu. Claude her gün teyitli oyun haberlerini siteye ekliyor; GitHub günde 5 kez
(TR saatiyle 10:17, 13:17, 16:17, 19:17 ve 22:17) yeni haberleri hesaplara paylaşıyor. Her
gönderi sitedeki haber sayfasına bağlanıyor. Sayfa, ziyaretçinin tarayıcı diline
(TR, EN, FR veya ES) kendiliğinden geçiyor.

Senin yapacağın tek şey hesapları açıp anahtarları kurulum yardımcısına yapıştırmak.
Yardımcı anahtarları dener, doğruysa GitHub'a gizli olarak kaydeder.

**Önerilen başlangıç:** İngilizce (EN) ve Türkçe (TR) hesaplar. Fransızca ve İspanyolca
hesapları sonra aynı yolla eklersin.

**E-posta ipucu:** her hesap ayrı e-posta ister. Gmail'de `adın+gtatr@gmail.com` gibi `+`
eklenmiş adresler aynı kutuya gelir; çoğu site bunu kabul eder.

Menü adları değişmiş olabilir. Bir adım ekrandakiyle uyuşmazsa ekran görüntüsünü Claude'a
at, birlikte bakarız.

---

## 1. X (Twitter): her dil için ayrı hesap

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

## 2. Reddit: her dil için ayrı hesap

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
   - TR: `https://rockstargtavı.com/oyun-haberleri.html`
   - EN: `https://rockstargtavı.com/en/game-news.html`
   - FR: `https://rockstargtavı.com/fr/actus-jeux.html`
   - ES: `https://rockstargtavı.com/es/noticias-juegos.html`
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

## Nasıl çalışıyor (bilgi için)

- Haberler: `data/icerik.json`. Claude her gün 10:00'da resmî kaynaktan teyit edip ekler.
  `tools/sosyal_derle.py` sayfaları, paylaşım görsellerini, RSS'i ve site haritasını üretir.
- Paylaşım: `.github/workflows/sosyal.yml` → `tools/sosyal_yayinla.py`.
  - Son 3 günün paylaşılmamış haberleri gider.
  - Her hesap için her çalışmada 1 gönderi, günde en çok 2 gönderi atılır
    (`sosyal/ayarlar.json`).
  - Gönderilenler `sosyal/gonderilenler.json`'a yazılır, aynı haber iki kez gitmez.
- Şifresi girilmemiş hesap atlanır. Bir hesap hata verirse GitHub sana "failed" e-postası
  atar; o e-postayı Claude'a göster.
