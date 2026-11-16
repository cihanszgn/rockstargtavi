# CTRL+A GAME saatlik haber ve trafik düzeni

Cio'nun 15 Kasım 2026 isteği: küresel 10 oyun haber/mağaza kaynağını her saat başında araştır, doğrulanmış yeni içeriği otomatik siteye gönder. Kaynaklar erişim ve kapsama göre seçildi; ölçülmüş bir dünya ilk 10 trafik sıralaması iddia edilmiyor.

## Araştırma sonucu

Haber otomasyonu tazelik sağlar; kalıcı trafik için oyuncunun sorusunu çözen güncel rehberler, yamaların oyuncuya etkisi ve doğrulanmış ücretsiz oyun/mağaza bilgisi daha faydalı bir içerik düzenidir (uygulama önerim). Haber → ilgili oyun merkezi → mevcut rehber yolu zaten derleyicide var; oyun adını kayıtla eşleştirmek bu bağı kurar. Öncelik WoW, Knight Online ve sitedeki diğer oyunların oynanış/güncelleme ihtiyaçlarıdır.

Google, kullanıcıya değer katmayan toplu üretim/yeniden yazımı spam kapsamında değerlendirebilir. Bu nedenle kota doldurulmaz, kaynak metni kopyalanmaz, resmî teyit ve somut oyuncu faydası şarttır. Kaynak: [Google'ın yapay zekâ içerik rehberi](https://developers.google.com/search/docs/fundamentals/using-gen-ai-content), erişim 2026-11-15.

Görsel tıklanabilirliği için büyük, konuyla ilgili resim, açık başlık ve iyi sayfa deneyimi öneriliyor; görünürlük garantisi yok. NewsArticle içindeki gerçek yayıncı kimliği ve görsel bilgisi arama motorunun içeriği anlamasına yardım eder. Kaynak: [Discover](https://developers.google.com/search/docs/appearance/google-discover), [Article işaretlemesi](https://developers.google.com/search/docs/appearance/structured-data/article), erişim 2026-11-15.

Trafiğin artıp artmadığı Analytics/Search Console ölçümü olmadan söylenmez. Sonraki değerlendirmede organik tıklama, gösterim, tıklama oranı ve haberden rehbere geçiş karşılaştırılmalı; yeni servis/hesap kurulmadı. Search Console erişimi bu oturumda yoktur.

## İzlenen 10 kaynak

`kaynaklar.json` tek kaynak kaydıdır: IGN, GameSpot, PC Gamer, Eurogamer ve GamesRadar+ haber keşfi; PlayStation Blog, Xbox Wire, Nintendo, Steam ve Epic Games Store platform/mağaza duyuruları. PC Gamer ve GamesRadar'ın küresel oyun yayınları olduğu yayıncılarının [marka sayfasından](https://futureplc.com/our-brands/) kontrol edildi (2026-11-15). RSS/API erişimleri gerçek komutla denendi.

Nintendo HTML listesinden aday alınır ve tarih haber sayfasında doğrulanır. Epic haber sayfası Python'da 403 verebilir: ücretsiz oyun API'si yardımcıdır; ajan haber sayfasını web aracıyla ayrıca okur. Steam'in genel haber RSS'i üçüncü taraf basınını da içerir; Steam adresi görünmesi tek başına resmî teyit değildir. Erişilemeyen kaynak dürüstçe eksik olarak raporlanır.

## Zamanlama ve çalışma

Turu `py tools/haber_hatti.py` yönetir; pahalı bir yönetici model yoktur. Windows Görev Zamanlayıcı'daki `ctrl-agame saatlik haber` görevi her saat başında `conhost.exe --headless` üzerinden çalışır; çalışma klasörü proje köküdür. `otomasyon/zamanla.ps1` varsayılan olarak yalnız görev XML'ini önizler; yönetici incelemesi sonrası `-Kaydet` ile kaydedilir. Bu geçişte görev kaydedilmez/etkinleştirilmez. Eski T3 saatlik tetikleri artık kullanılmaz. Bilgisayarın ve kullanıcı oturumunun açık, CLI oturumlarının erişilebilir olması gerekir.

Python önce 45 dakikalık ortak kilidi alır, temiz main ve uzak HEAD eşitliğini kontrol eder, `git pull --ff-only` yapar ve başlangıç kopyasını saklar. `haber_oto.py tara` 10 kaynaktan adayları çıkarır. Qwen3 8B (yedek Gemma3 4B) küçük parçalar halinde kapsam, anlam tekrarı ve hype ön puanı verir; kod takipli oyunları/yüksek puanı önceleyip en çok üç aday seçer. Yerel karar ön elemedir; gerçek teyit yazara ve denetçiye aittir.

Yerel çağrı, mevcut `yerel_sor.py` içindeki model/adres kaydını yeniden kullanır; bu dosyayı değiştirmez. 6 GB VRAM için dört aday/parça, 4096 bağlam ve sınırlı JSON çıktısı kullanılır. Yerel zaman aşımı/erişim hatasında model o turun kalan parçalarında tekrar çağrılmaz; sıradaki yerel yedeğe geçilir. Model bulunamazsa adaylar teyitli kabul edilmez.

Yazar sırası OpenCode `opencode/big-pickle` → Haiku → Sonnet'tir. Yazar resmî sayfayı okuyup dört dili ve gerekiyorsa video senaryosunu JSON olarak döndürür; Python yalnız belirlenmiş çalışma dosyalarına kaydeder. Her çıktı mevcut `hazirla` komutuyla kuru doğrulanır; biçim/şema hatasında aynı modele bir düzeltme, sonra sıradaki modele geçiş yapılır. Ajanlar sır içermeyen geçici klasörde, yalnız web ve kasa arama araçlarıyla çalışır. Ücretsiz OpenCode çağrısı kullanıcı ortamı, global yapılandırma ve anahtarları taşımaz. Çalışma ağacındaki izinsiz değişiklik geri alınır ve çıktı reddedilir.

Sonnet paketteki her resmî sayfayı bağımsız okuyup onay/ret ve gerekirse düzeltilmiş hype verir; çağrı/JSON hatasında bir kez Opus denenir. Denetçi çalışmazsa yayın yoktur. Reddedilen haber çıkarılır; yükselen hype eşiği geçip senaryo yoksa haber bu tur atlanır. Python onaylı paketi yeniden `hazirla` ile doğrular; uygulama, görsel alma, derleme, bağlantı/test/diff kontrolleri geçerse yalnız izinli yayın dosyalarını commit/push eder. Push reddinde bir rebase ve yeniden kontrol yapılır; belirsizlikte ikinci push yoktur. Canlı yeni haber sayfası en çok beş dakika izlenir.

`py tools/haber_hatti.py --deneme` gerçek tarama, yerel eleme, yazar ve denetimi çalıştırır; yayın aşamasını tamamen atlar. Onaylı/yazılmış paket, denetim, deneme senaryoları ve `sonuc.json` `.git/haber-oto/` içinde kalır; depo başlangıç durumuna döner. `hat.log` her tur için tek satır yazar. Aşama başına sıralı model komutları ve zaman aşımları `modeller.json`, görev metinleri `yazar-gorev.txt` ve `denetci-gorev.txt` içindedir. Toplam süre 43 dakika ile sınırlıdır; kilit her çıkışta bırakılır. Kaynak erişim eksikleri sonuçta açıkça kaydedilir; bütün kaynakların tam araştırıldığı varsayılmaz.

Her tur 10 kaynak, son 48 saat; en fazla 3 haber/tur ve 12 haber/TR günü. Dört dil zorunlu. Aynı kaynak URL'si, normalize başlık, id veya olay kimliği yeniden eklenmez. `otomasyon.konu` aynı olayın farklı kaynaklarında da aynı kalmalıdır. Legacy kayıtlar için anlam denetimini ajan yapar. Kotalar `kaynaklar.json` içindedir. Haber doğrulamasını ajan yapar; Python içerik doğruluğunu veya özgünlüğünü kendi başına ispatlayamaz.

Günlük takvim/bakım akışı bu hattan ayrıdır; aynı yayın kilidini kullanmalıdır. Haber hattı sosyal paylaşım veya video üretim komutunu doğrudan çalıştırmaz; sosyal medya kotaları korunur.

## Komutlar

Python 3.12, Pillow (sosyal kartlar), Git/GitHub CLI ve bağlı araştırma araçları gerekir. Yeni API anahtarı gerekmez. Proje kökünde:

```powershell
py tools/haber_oto.py kilit-al
py tools/haber_oto.py tara
py tools/haber_oto.py hazirla --batch .git/haber-oto/batch.json
py tools/haber_oto.py hazirla --batch .git/haber-oto/batch.json --uygula --token TOKEN
py tools/gorsel_cek.py --id HABER-ID
py tools/sosyal_derle.py
py tools/haber_oto.py kontrol
py -m unittest discover -s tests -p test_haber_oto.py
py tools/haber_oto.py kilit-birak --token TOKEN
```

Token gerçek `kilit-al` çıktısından alınır. Adaylar, paket, önizleme, başlangıç içerik kopyası ve sonuç `.git/haber-oto/` içindedir; siteye/depoya yayımlanmaz. Kilit SQLite işlemiyle alınır, 45 dakika geçerlidir; sahibi olmayan iş bırakamaz/yayımlayamaz. Güncel ve temiz main dışında yayın yapılmaz; açık kullanıcı değişiklikleri otomatik commit edilmez.

Paket JSON listesinde normal `data/icerik.json` şemasına şu alan eklenir:

```json
"otomasyon": {
 "konu": "oyun-surum-olay-kimligi",
 "resmi_url": "https://blog.playstation.com/2026/11/13/ilgili-duyuru/",
 "teyit_zamani": "2026-11-15T04:05:00+03:00",
 "oyuncuya_fayda": "Yamanın hangi oyuncuları etkilediği ve ne yapabilecekleri.",
 "hype": 7
}
```

Bu bir alan örneğidir, yayınlanacak haber değildir. Resmî URL aynı haberin kaynaklar listesinde bulunmalı; izinli alan adı olmalı; son iki saatte gerçekten okunmuş olmalı. Haber tarihi kaynak tarihidir, ileri tarih veya iki günden eski haber reddedilir. Her dilin yeni metni 50–300 kelime ve başlık ≤100 karakterdir. Yapay bilgi/dolgu ile alt sınır tamamlanmaz; yeterli olgu yoksa yayın yapılmaz.

## Hype puanı

- Her yeni habere 1–10 arası tam sayı `otomasyon.hype` verilir; puan haberin kaç oyuncuyu ilgilendirdiğini ölçer, editörün beğenisini değil.
- 9–10: çok büyük oyunda (GTA, Call of Duty, Fortnite, Minecraft, EA Sports FC, League of Legends, Valorant, Counter-Strike 2 ve benzeri) çıkış tarihi, yeni oyun duyurusu, büyük ücretsiz oyun ya da herkesi etkileyen büyük değişiklik.
- 7–8: takipli oyunların yeni sezonu/büyük güncellemesi, bilinen bir oyunun çıkışı, büyük mağaza kampanyası ya da tanınmış ücretsiz oyun.
- 5–6: orta boy güncelleme, küçük ya da orta oyunun çıkışı, sınırlı kampanya.
- 1–4: küçük yama, geliştirici notu, dar kitleli haber.
- Eşik `sosyal/ayarlar.json` → `video.hype_esigi` (şu an 7). Eşiğe ulaşan haberin video senaryosu aynı turda yazılmak zorundadır, yoksa `hazirla` paketi reddeder. Eşiğin altındaki haber için senaryo yazılmaz; o haber sitede ve Instagram'da yalnız görsel olarak paylaşılır. Puan şişirilmez: kararsız kalınan haber düşük puanı alır.

## Video senaryosu

Habere dikey video senaryosu `video/senaryo/<haber id>-tr.json` dosyası olarak yazılır. Hype puanı eşiğe (şu an 7) ulaşan ya da üstünde olan haberde senaryo zorunludur ve aynı turda yazılır; eşiğin altındaki haberde senaryo yazılmaz. Dosya varsa `hazirla` onu haberin kendi metniyle denetler; hatalı senaryo bütün paketi reddeder. Video üretimi saatlik turun işi değildir (render ve günlük kota ayrı yürür).

```powershell
py tools/video_uret.py dogrula --id HABER-ID --dil tr
py tools/video_uret.py bekleyenler --gunluk
py tools/video_uret.py uret --id HABER-ID --dil tr
```

Senaryo yalnız veridir: alanlar düz metindir, kod ya da komut olarak çalıştırılmaz; bilinmeyen alan hatadır. Doğrulayıcının zorladığı kurallar:

- `id` haber kimliği, `dil` dosyanın dili; `fps` 30, `boyut` `[1080, 1920]`, `sablon_surumu` 1. `bas`, `bit`, `altyazi` yazılmaz: zamanlama sesten hesaplanır.
- 3–9 sahne; ilk sahne `baslik`, son sahne `kapanis`. Tahmini süre 20–80 sn olmalı; anlatımın toplamı 60–110 kelime önerilir (dışında uyarı).
- Ekranda görünen ya da söylenen her sayı haberin başlığında, özetinde, metninde, oyun adında veya haber tarihinde geçmelidir. `tarih` sahnesindeki gün ve ay ("1 Aralık", "13–16 Kasım") haber metninde aynen geçmelidir; yıl yalnız haberde yazıyorsa gösterilir. Haberde olmayan bilgi senaryoya eklenmez.
- Şablon seçimi habere göre yapılır: `guncelleme` → `maddeler`, `yama_fark`, `platform` sayı kutuları; `cikis` → `tarih`, `platform`; `ucretsiz`/`indirim` → `fiyat`, `tarih`, `platform`; `haber` → `kaynak`, `maddeler`. Her senaryoda bir `kaynak` sahnesi önerilir (haberin `kaynaklar` sırası, 0'dan; alıntı ≤150 karakter, kaynağın sadık özeti).
- Şablon sınırları: `baslik` başlık ≤90 karakter, `vurgu` başlıkta aynen geçen en çok 3 parça, `tuslar` 1–4 tuş (en çok 3 karakter); `maddeler` 2–4 madde (≤70); `yama_fark` 1–3 satır eski → yeni; `platform` haberin `platform` listesinden en çok 4 rozet ve/veya en çok 3 sayı kutusu; `fiyat` `durum` `ucretsiz` ya da `indirim`; `kapanis` çağrı ≤60, alt ≤70.
- Her sahnenin `alt_kart`ı: simge + başlık (≤26) + alt satır (≤40). Etiketler, pencere başlıkları ve kart yazıları BÜYÜK HARFLE gösterilir (Türkçe i → İ kuralı otomatik); kaynakta normal yazılabilir.
- Yazıların sığması piksel ölçüsüyle sınanır: alana sığmayan kelime ya da izinli satır sayısını aşan metin hatadır; kısaltılır.
- Madde, satır ve sayı kutularındaki `tetik`, öğenin belirdiği anı seçer; o sahnenin anlatımında geçen bir kelime (ya da kelime başı) olmalıdır.
- `anlatim` seslendirilen ve kelime kelime altyazıya dönen tam cümlelerdir. Türkçe ekler kesmeyle yazılır (`Doc'un`, `1 Aralık'ta`). Adlar ve kodlar kendi yazımıyla bırakılır (`Rainbow Six Siege'in`, `Operation Vital Signal`, `MBZ-19`, `ACS12`, `EA app`): ses (`tr-TR-Aydin:MAI-Voice-2.1`) onları kendisi okur. Türkçe okunuşa çevirmek (`Reynbou Siks Siyc'in`, `Em Be Ze on dokuz`) yasaktır: ses o metni hece hece okuyor.
- `okunus` sözlüğü varsayılan olarak boştur (`{}`). Yalnız sesin bir kelimeyi gerçekten yanlış okuduğu dinlenerek ya da konuşma tanımayla doğrulanmışsa tek tek eklenir; anahtar anlatımdaki kelime(ler)le tam eşleşir, kesmeden sonraki ek korunur, okunuştaki rakamlar da haberde geçmelidir. Kodları harf harf ayırmak (`A C S 12`) okunuşu bozdu (ölçüm 2026-11-16).
- Web adresi seslendirilmez: `ctrl-agame.com`, `www.`, `https://` ya da "nokta kom" anlatımda hatadır. Kapanış sitenin adını söyler: `… tamamı sitemizde, Control A Game'de.` Adres ekranda kapanış kartında zaten yazılıdır.
- `maskot.hareket`: `zipla`, `bas`, `tara` (yalnız `kaynak`), `bekle`. Maskotun yeri şablondan gelir.

Örnekler: `video/senaryo/r6-siege-operation-vital-signal-duyuruldu-2026-11-15-tr.json` (güncelleme) ve `video/senaryo/battlefield-6-ucretsiz-deneme-casino-heist-2026-11-13-tr.json` (ücretsiz deneme).

## Doğrulama ve hata yolu

Bir kaynak başarısız olsa da diğerleri araştırılır; eksik kaynağın kontrolü başarılı gösterilmez. Uygulama önce bütün paketi doğrular; geçersiz paket içerik dosyasına yazılmaz. Build, iç bağlantı ve testler geçmeden push yok. Başarısız tur kendi başlangıç kopyasından yalnız kendi değişikliğini geri alır; force push, kör reset/clean ve başka kullanıcının değişikliklerini stage etmek yasaktır.

Testler: id/URL/başlık/olay tekrarları, HTTPS/sahte alt alan adı, dört dil, eski/gelecek tarih, resmî kaynak şartı, günlük/tur kotası, kilit sahibi/süresi, RSS ayrıştırma ve kırık bağlantı. Canlı tarama 2026-11-15'te 10 kaynak ve 83 aday döndürdü. `kontrol` 313 sayfada 22.119 bağlantı, sıfır kırık bağlantı buldu (yeni içerikle adetler artabilir).

Otomasyonu durdurmak için Windows'ta `Disable-ScheduledTask -TaskName 'ctrl-agame saatlik haber'` kullanılır. Görev henüz kurulmamışsa durdurulacak saatlik tetik yoktur. Günlük bakım bağımsızdır; anahtarlar hiçbir dosyaya yazılmaz.
