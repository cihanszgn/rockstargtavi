# CTRL+A GAME saatlik haber ve trafik düzeni

Cio'nun 15 Kasım 2026 isteği: küresel oyun haber/mağaza kaynaklarını her saat başında araştır, doğrulanmış yeni içeriği otomatik siteye gönder. Kaynaklar erişim ve kapsama göre seçildi; ölçülmüş bir trafik sıralaması iddia edilmiyor.

## Araştırma sonucu

Haber otomasyonu tazelik sağlar; kalıcı trafik için oyuncunun sorusunu çözen güncel rehberler, yamaların oyuncuya etkisi ve doğrulanmış ücretsiz oyun/mağaza bilgisi daha faydalı bir içerik düzenidir (uygulama önerim). Haber → ilgili oyun merkezi → mevcut rehber yolu zaten derleyicide var; oyun adını kayıtla eşleştirmek bu bağı kurar. Öncelik WoW, Knight Online ve sitedeki diğer oyunların oynanış/güncelleme ihtiyaçlarıdır.

Google, kullanıcıya değer katmayan toplu üretim/yeniden yazımı spam kapsamında değerlendirebilir. Bu nedenle kota doldurulmaz, kaynak metni kopyalanmaz, kaynaklı teyit ve somut oyuncu faydası şarttır. Kaynak: [Google'ın yapay zekâ içerik rehberi](https://developers.google.com/search/docs/fundamentals/using-gen-ai-content), erişim 2026-11-15.

Görsel tıklanabilirliği için büyük, konuyla ilgili resim, açık başlık ve iyi sayfa deneyimi öneriliyor; görünürlük garantisi yok. NewsArticle içindeki gerçek yayıncı kimliği ve görsel bilgisi arama motorunun içeriği anlamasına yardım eder. Kaynak: [Discover](https://developers.google.com/search/docs/appearance/google-discover), [Article işaretlemesi](https://developers.google.com/search/docs/appearance/structured-data/article), erişim 2026-11-15.

Trafiğin artıp artmadığı Analytics/Search Console ölçümü olmadan söylenmez. Sonraki değerlendirmede organik tıklama, gösterim, tıklama oranı ve haberden rehbere geçiş karşılaştırılmalı; yeni servis/hesap kurulmadı. Search Console erişimi bu oturumda yoktur.

## İzlenen 22 kaynak

`kaynaklar.json` tek kaynak kaydıdır. Keşif: IGN, GameSpot, PC Gamer, Eurogamer, GamesRadar+, VGC, Rock Paper Shotgun, Gematsu, Jeuxvideo.com (FR), 3DJuegos (ES), GAME Watch (JP). Resmî/mağaza: PlayStation Blog, Xbox Wire, Nintendo, Epic Games Store, Final Fantasy XIV Lodestone ve Valve CS2/Dota 2, EA Apex Legends, Capcom Street Fighter 6, Bethesda Skyrim resmî Steam duyuruları. Genel Steam RSS'i karma keşiftir; üçüncü taraf basın yazıları resmî teyit değildir.

Eklenen 12 RSS/Atom/RDF/JSON akışı 2026-11-16'da gerçek HTTPS isteği ve ayrıştırmayla denendi. Rockstar, Blizzard, Riot, Ubisoft, EA, Bethesda, Capcom ve Bandai Namco için denenip hata/HTML dönen doğrudan RSS adresleri eklenmedi. Çalışan Square Enix akışı FFXIV Lodestone Atom'dur. Steam JSON yalnız `steam_community_announcements` kayıtlarını alır ve haber yönlendiricisini izleyip gerçek resmî duyuru detay adresini çözer (API gid değeri duyuru kimliği değildir); forum/haricî basın kabul edilmez.

RSS pubDate, Atom published/updated, RDF dc:date, Steam zaman damgası ve Nintendo başlığındaki AA/GG/YY tarihleri kodda çözülür. Son 48 saat dışı veya gelecekteki bilinen tarihler yerel modelden önce elenir. Yayımlanmış kaynak URL’si veya herhangi bir dilde birebir başlık tekrarı da kodda modelden önce elenir; ortak API adresi tek başına olay kimliği sayılmaz. Kaynak sınırından önce de takipli oyunlar öne alınır; sırf daha yeni magazin/donanım başlığı somut yamayı sınır dışına itemez. Oyun adları kelime sınırıyla eşleşir (Trust donanımı Rust oyunu sayılmaz). Kaynak başına en çok altı aday kalır; tarihsiz aday atılmaz, sıralamada en sona gider. Tarama her kaynak için bulunan/tarih nedeniyle elenen/sınır nedeniyle elenen/kalan/tarihsiz adetlerini kaydeder.

Epic API'nin oyun adı, kampanya başlangıç/bitiş tarihi, TR bölgesi ve mağaza adresi `resmi_veri` olarak yazara ve denetçiye taşınır; epicgames.com API yanıtı resmî teyittir. Mağaza sayfasının 403 dönmesi tek başına ret nedeni değildir. Eski kampanya yeni haber sayılmaz; gelecekteki kampanyanın duyuru tarihi ayrıca teyit edilir.

## Zamanlama ve çalışma

Turu `py tools/haber_hatti.py` yönetir; pahalı bir yönetici model yoktur. Windows Görev Zamanlayıcı'daki `ctrl-agame saatlik haber` görevi her saat başında `conhost.exe --headless` üzerinden çalışır; canlı çalışma kopyası `C:\Cihan.Ai\03-Web\rockstargtavi-hat` klasörüdür ve her saat `origin/main` çekilir. Geliştirme kopyası `C:\Cihan.Ai\03-Web\rockstargtavi` ayrıdır; canlı kopyanın durum dosyaları geliştirme sırasında salt okunur kanıttır. `otomasyon/zamanla.ps1` varsayılan olarak yalnız görev XML'ini önizler; yönetici incelemesi sonrası `-Kaydet` ile kaydedilir. Eski T3 saatlik tetikleri artık kullanılmaz. Bilgisayar açıkken Windows hattı, kapalıyken aşağıdaki uzak sunucu hattı çalışır.

Python önce 45 dakikalık ortak kilidi alır, temiz main kontrolünden sonra `git pull --ff-only` yapar. Pull HEAD'i değiştirirse aynı kilit sahipliğini stdin üzerinden yeni Python sürecine devrederek bir kez yeniden başlar; eski süreç tarama/model çağrısı yapmaz ve çocuğun sonuç dosyasını ezmez. İkinci HEAD değişiminde döngü korumasıyla durur. 43 dakikalık tur bütçesi ve kilit süresi yeniden başlamaz; uzak HEAD eşitliği yeni süreçte de kontrol edilir.

`haber_oto.py tara` 22 kaynağı toplar. Aynı olayın mevcut yakın başlık/olay eşleştirmesi resmî URL'yi ve diğer kaynakları korur. Sıralama doğrulanabilirlik önceliklidir: tarihli resmî alan/resmî URL eşleşmesi olan adaylar (Epic API dahil), sonra tarihli keşif adayları, en sonda tarihsizler; her grupta takipli oyun → hype ön puanı → tazelik. Bu öncelik yerel 72 aday sınırından önce de uygulanır. Takipli oyun resmî adayın önüne geçmez. Yerel ret tek başına takipli/yüksek hype/resmî adayı engellemez; açık sızıntı ve söylenti kodda da elenir. Gerçek teyit yazara ve denetçiye aittir.

Yerel çağrı mevcut `yerel_sor.py` model/adres kaydını kullanır; yardımcı dosyayı veya Ollama'nın genel ayarlarını değiştirmez. Tur başında gerçek üretimle 30 saniyelik sağlık denemesini geçen ilk model (Gemma3 4B, yalnız sağlıkta başarısızsa Qwen3 8B) turun tek eleme modelidir. Dört aday/parça, 4096 bağlam, 768 çıktı token'ı, 60 saniyelik istek/75 saniyelik dış süreç sınırı ve 45 dakika sıcak tutma kullanılır. Canlı Gemma ölçümü 768 token için 9,43 saniyedir; 60 saniye bunun üzerinde pay bırakır. Parça hatasında ikinci modele veya düzeltme çağrısına geçilmez; somut yama/güncelleme/XP başlıkları `yedek_puan` ile 5, diğerleri 3 araştırma ön puanı alır. Ortam hatasında kalan parçalar da kod yedeğiyle devam eder. Bu puan teyit veya yayın hype puanı değildir.

Yazımdan önce model çağrısı olmadan keşif ön koşulu uygulanır: aynı olayın en az iki ayrı keşif kaynağı adayında görülmesi gerekir; tek kaynak “tek kaynak, resmî teyit yok” gerekçesiyle hafızaya yazılır. Görüş/yorum/analiz/geri bakış/topluluk işaretleri ve soru başlıkları keşifte elenir; bu süzgeç resmî adaylara uygulanmaz. İki aday kaynağı yalnız ucuz ön koşuldur; adı/görevi/kurumu belli yetkili ve iki bağımsız yayın grubu dahil asıl birincil teyit şartları değişmez.

RSS `content:encoded` önceliklidir. Sayfa yedeği özel haber gövdesini (entry-content/art-body vb.), yoksa article/main kapsayıcısını seçer; özel gövde boşken geniş main içindeki öneri kartları alınmaz, `govde_yok` kaydedilir. Steam'in yapılandırılmış sayfa verisinde yalnız istenen duyuru kimliğinin gövdesi okunur. Xbox Minecraft Dungeons II adayının 2026-11-16 gerçek yanıtında akış yalnız 103 karakterlik bağlantı, art-body ise boştur; başlıktan içerik üretilmez.

Yazar sırası OpenCode `opencode/big-pickle` → Haiku → Sonnet'tir. 429/FreeUsageLimitError/kota yanıtında model `retryAfterMs` süresince, süre yoksa 12 saat atlanır; bekleme `.git/haber-oto/model-kotalari.json` içinde turlar arasında korunur. Yazar tercih edilen resmî teyit veya aşağıdaki birincil teyit yoluyla yedi dili ve gerekiyorsa video senaryosunu JSON olarak döndürür; Python yalnız belirlenmiş çalışma dosyalarına kaydeder. Her çıktı mevcut `hazirla` komutuyla kuru doğrulanır; biçim/şema hatasında aynı modele bir düzeltme, sonra sıradaki modele geçiş yapılır. Ajanlar sır içermeyen geçici klasörde, yalnız web ve kasa arama araçlarıyla çalışır. Ücretsiz OpenCode çağrısı kullanıcı ortamı, global yapılandırma ve anahtarları taşımaz. Çalışma ağacındaki izinsiz değişiklik geri alınır ve çıktı reddedilir.

Sonnet her adayın gerekli teyit kaynaklarını bağımsız inceleyip onay/ret ve gerekirse düzeltilmiş hype verir; çağrı/JSON hatasında bir kez Opus denenir. Denetçi çalışmazsa yayın yoktur. Her aday yazımından sonra denetlenir; ret/atlamada sıralı yedeğe geçilir. Üç onaya ulaşılınca veya 8 yazım denemesi/süre bütçesi dolunca durulur. Her yazım denemesi model çağrısı harcadığından araştırma sınırı sekizdir. Aynı oyuna turda en fazla iki yazım denemesi, keşif adaylarına toplam en fazla iki yazım denemesi ayrılır; aynı oyundan bir haber onaylanınca diğerleri atlanır. Resmî aday kalmadıysa ve keşif hakkı dolduysa yeni model çağrısı yapılmadan tur biter. Reddedilen haber çıkarılır; yükselen hype eşiği geçip senaryo yoksa haber bu tur atlanır. Python yalnız `onayli-paket.json` dosyasını `hazirla --uygula` ile yeniden doğrulayıp uygular; yedek adayın son yazım taslağı yayın girdisi olamaz. Görsel alma, derleme, bağlantı/test/diff kontrolleri geçerse yalnız izinli yayın dosyalarını commit/push eder. Push reddinde bir rebase ve yeniden kontrol yapılır; belirsizlikte ikinci push yoktur. Canlı yeni haber sayfası en çok beş dakika izlenir.

`py tools/haber_hatti.py --deneme` gerçek tarama, yerel eleme, yazar ve denetimi çalıştırır; yayın aşamasını tamamen atlar. Deneme saat başı ile sonraki 15 dakika arasında başlatılmaz. Gönderilmemiş yerel commit veya izlenmeyen kullanıcı klasörü varsa, yerel depoyu origin kabul eden temiz geçici bir main kopyası kullanılır. Deneme kopyasında önce `git pull --ff-only`, ardından yeni Python süreci başlatılır; hat ayrıca kendi pull işleminden sonra HEAD değişimini otomatik yeniden başlatmayla karşılar. Canlı kopya bu amaçla kullanılmaz. Onaylı/yazılmış paket, denetim, deneme senaryoları ve `sonuc.json` `.git/haber-oto/` içinde kalır; depo başlangıç durumuna döner. `hat.log` her tur için tek satır yazar. Aşama başına sıralı model komutları ve zaman aşımları `modeller.json`, görev metinleri `yazar-gorev.txt` ve `denetci-gorev.txt` içindedir. Toplam süre 43 dakika ile sınırlıdır; kilit her çıkışta bırakılır. Kaynak erişim eksikleri sonuçta açıkça kaydedilir; bütün kaynakların tam araştırıldığı varsayılmaz.

Her tur yapılandırılmış kaynaklar, son 48 saat; en fazla 3 haber/tur ve 12 haber/TR günü. Yedi dil zorunlu: tr, en, es, fr, de, nl, zh. Tek kayıt `data/diller.json` dosyasıdır. Aynı kaynak URL'si, normalize başlık, id veya olay kimliği yeniden eklenmez. `otomasyon.konu` aynı olayın farklı kaynaklarında da aynı kalmalıdır. Legacy kayıtlar için anlam denetimini ajan yapar. Kotalar `kaynaklar.json` içindedir. Haber doğrulamasını ajan yapar; Python içerik doğruluğunu veya özgünlüğünü kendi başına ispatlayamaz.

Günlük takvim/bakım akışı bu hattan ayrıdır; sunucuda aynı calisma.kilit ve depo içindeki SQLite yayın kilidini kullanır. Haber hattı sosyal paylaşım veya video üretim komutunu doğrudan çalıştırmaz; sosyal medya kotaları korunur.


## Uzak sunucu

17 Kasım 2026 geçişi: saatlik yürütme `haberci` kullanıcısıyla `/home/haberci/rockstargtavi` deposunda, mevcut `~/venv` ve `~/bin/py` ile yapılır. Aynı depo ve `~/calisma.kilit` korunur: günlük bakımın `calistir.sh gunluk` akışıyla hem dosya kilidi hem `.git/haber-oto/kilit.sqlite` ortaktır. Ayrı depo kopyası kullanılmaz; iki bağımsız SQLite kilidi oluşması önlenir. Günlük servis/timer ve eski `calistir.sh` değiştirilmez.

`haber-oto.service` → `/home/haberci/haber-hatti.sh` (depodaki `otomasyon/sunucu-haber.sh` kopyası) → `tools/haber_hatti.py --modeller otomasyon/modeller-sunucu.json`. Timer her saat **:10** çalışır. Sarmalayıcı ortamı `~/.haber.env` üzerinden yükler; `~/gunluk/YYYY-AA-GG.log`, tur günlüğü ve `son-durum-saatlik.txt` yazar. Hata durum değişimi ve yayın aynı `~/.bildirim-adresi` üzerinden Telegram'a gider. Sır dosyalarının içeriği günlüğe yazılmaz.

Sunucu yazarı: OpenCode ücretsiz `opencode/big-pickle` → Codex `gpt-6-luna` (medium) → Claude Haiku → Codex `gpt-6.1-terra` (medium) → Claude Sonnet. Denetçi: Claude Sonnet → Codex `gpt-6.1-sol` (high) → Claude Opus. Yazar Claude ise farklı sağlayıcı olan Codex denetçi önce denenir; kalan sıra korunur. Denetçisiz yayın yapılmaz. Codex `exec --json`, salt okunur sandbox, canlı web ve kabuk araçları kapalı olarak ayrı geçici klasörde çalışır; kullanıcı yapılandırması yüklenmez. Oturumsuz sağlayıcı atlanır; kota/rate-limit hatası mevcut `model-kotalari.json` beklemesine yazılır. Sunucu Ollama kurmaz, eleme boşsa kodun mevcut yedek sıralaması kullanılır. Kasa MCP'si bulunmadığında görev onu atlayarak devam eder. Windows model zinciri değişmemiştir; dosya `--modeller` veya `HABER_MODELLER` ile seçilir ve pull sonrası yeniden başlatmada korunur.

Windows hattı her gerçek turun başında `ssh -o ConnectTimeout=5 -o BatchMode=yes oracle` üzerinden `/home/haberci/pc-nabiz` bırakır; sonundaki `gorulen.json` atomik olarak `/home/haberci/pc-gorulen.json` dosyasına gönderilir. `otomasyon/nabiz.json` → `etkin:false` veya `HABER_NABIZ=0` ile kapatılır. Linux ve `--deneme` bu ekleri çalıştırmaz; ağ hatası sonucu bozmaz, `sonuc.json` içindeki `esleme` alanına kaydedilir. Sunucuda nabız **50 dakikadan yeniyse ve bilgisayarın son BİTEN turu hatasızsa** tur atlanır; tam 50 dakika ve sonrası tur çalışır. İki hafızada URL başına en yeni karar korunur. Windows canlı kopyası kodu yalnız git pull ile alır.

**Sessiz arıza koruması (17 Kasım 2026).** 16 Kasım akşamı bilgisayar hattı her saat yayın adımında düştü (`git add` argv'si WinError 206), ama nabız turun başında bırakıldığı için sunucu yedeği "bilgisayar çalışıyor" deyip ~16 saat hiç tur atmadı ve kimseye haber gitmedi. Üç önlem: (1) Bilgisayar turu bitince (`bitir`, nabız ve hafızadan sonra, en son) `/home/haberci/pc-sonuc.json` dosyasını aynı ssh/atomik yazım yoluyla bırakır: `{zaman, ok, hata (ilk 300 karakter), eklenen, sure}`; yeni sır veya bağlantı yoktur, ağ hatası turu bozmaz (`esleme` kaydında `asama: sonuc`). Beklenmeyen istisna da `hata` olarak yazılır. (2) Sunucu sarmalayıcısı `--nabiz-kontrol ... --pc-sonuc ...` ile karar verir: nabız taze **ve** sonuç hatasızsa atlar; sonuç `ok:false` ve nabızdan yeniyse (son tur bitmiş, hatalı) çalışır; sonuç nabızdan eskiyse bilgisayar yeni turun ortasındadır, çakışmamak için atlar (tur ölürse nabız 50 dakikada bayatlar). Sonuç dosyası yok/bozuksa eski davranış. (3) Sarmalayıcı her çağrıda (tur atlansa bile) `izle` çalıştırır ve Telegram'a yalnız DURUM DEĞİŞİNCE yazar, düzelince "düzeldi" der: (a) bilgisayarın son turu hatalı (hata metninin ilk 200 karakteri); (b) origin/main'de son yayın commit'inden (`haber: ` ile başlayan VE `data/icerik.json`'u değiştiren; kod commit'leri sayılmaz) bu yana eşikten fazla süre geçti. Eşik `otomasyon/izleme.json` → `haber_yok_saat` (6), `HABER_ESIK_SAAT` ortam değişkeniyle geçici değiştirilir. Durum `/home/haberci/izleme-durum.json` içindedir; bildirim gitmezse durum kaydedilmez ve ertesi saat yeniden denenir. Son yayın zamanı özel ref `refs/izle/main`'e `--no-write-fetch-head` ile çekilir (pull/günlük bakımla ref kilidi çakışmaz); ağ yoksa bilgi yoktur, alarm da yoktur.

Deneme: `sudo -u haberci /home/haberci/haber-hatti.sh --deneme --nabiz-yoksay`. Bildirim fonksiyonunun ağsız denemesi: `sudo -u haberci /home/haberci/haber-hatti.sh --bildirim-deneme`. Atlama ve izleme kararlarının bildirimsiz denemesi (durum dosyası ve Telegram değişmez; yalnız `NABIZ_KARARI:` ve `IZLEME_KURU:` satırları yazar): `sudo -u haberci /home/haberci/haber-hatti.sh --izle-deneme`; yolları `PC_NABIZ`, `PC_SONUC`, `IZLE_DURUM` ve `HABER_ESIK_SAAT` ortam değişkenleriyle değiştirerek senaryo denenir (`sudo -u haberci env PC_SONUC=/tmp/x ... betik --izle-deneme`). Yalnız saatliği durdurma: `sudo systemctl stop haber-oto.timer haber-oto.service`. Günlük bakım bundan bağımsızdır.

Değiştirilen eski birimler `/home/haberci/yedek-2026-11-17/` altına alınır; eski `calistir.sh` yerinde kalır. Geri alma:

```bash
sudo systemctl stop haber-oto.timer haber-oto.service
sudo cp -p /home/haberci/yedek-2026-11-17/haber-oto.service /etc/systemd/system/haber-oto.service
sudo cp -p /home/haberci/yedek-2026-11-17/haber-oto.timer /etc/systemd/system/haber-oto.timer
sudo systemctl daemon-reload
sudo systemctl start haber-oto.timer
```

Yedek birimler eski `/home/haberci/calistir.sh saatlik` yoluna ve saat başı zamanına döndürür; günlük servise dokunulmaz.

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
 "teyit_turu": "resmi",
 "resmi_url": "https://blog.playstation.com/2026/11/13/ilgili-duyuru/",
 "teyit_zamani": "2026-11-15T04:05:00+03:00",
 "oyuncuya_fayda": "Yamanın hangi oyuncuları etkilediği ve ne yapabilecekleri.",
 "hype": 7
}
```

Bu bir alan örneğidir, yayınlanacak haber değildir. `teyit_turu` resmi veya birincil olabilir; eski paketlerde eksikse resmi kabul edilir. Resmî yolda izinli `resmi_url` kaynaklar içinde yer alır. Epic için bu adres resmî API olabilir; API olguları `resmi_veri` ile taşınır. Teyit son iki saat içinde yapılmalı, oyuncuya fayda en az 30 karakterle açıklanmalıdır.

Resmî haber sayfası yoksa birincil yol yalnız adı/görevi/kurumu belli geliştirici veya yayıncı yetkilisinin doğrudan açıklaması, röportajı, resmî sosyal medya/YouTube paylaşımındaki aynı olgu için kullanılabilir. `otomasyon.birincil_kaynak`: `kisi`, `gorev`, `kurum`, `tur` (`aciklama`, `roportaj`, `resmi_sosyal`, `resmi_youtube`), `olgu`. `otomasyon.capraz_kaynaklar` en az iki bağımsız izinli keşif yayınının gerçekten okunan haber URL'sini içerir; ikisi `kaynaklar` listesinde de olmalıdır. Aynı yayın grubu bağımsız sayılmaz. Grup kayıtlarının dayanağı: [IGN’in Gamer Network açıklaması](https://www.linkedin.com/posts/ign-entertainment_ign-entertainment-acquires-eurogamer-gi-activity-7199137991993229315-mc6n), [Webedia’nın marka açıklaması](https://webedia-group.com/news/corporate/the-webedia-elephant-group-now-attracts-over-380-million-unique-visitors-a-month-to-its-digital-content-according-to-comscore/), Future için [marka kaydı](https://futureplc.com/our-brands/); erişim 2026-11-16. Her dilde kaynak açıkça anılır (ör. “IGN'in aktardığına göre…”). Resmî yol tercih edilir. Söylenti/sızıntı, isimsiz kaynak, reportedly türü iddia veya aynı söylentiyi tekrarlayan iki yayın bu yoldan geçemez; içerik ve bağımsızlık denetçi tarafından ayrıca doğrulanır.

Haber tarihi gerçek kaynak tarihidir, ileri tarih veya 48 saatten eski haber reddedilir. tr/en/es/fr/de/nl için metin 50–300 kelime, başlık ≤100 karakterdir. Basitleştirilmiş Çince (zh) için metin 100–600 Çince karakter, başlık ≤50 karakterdir. Yapay bilgi/dolgu ile alt sınır tamamlanmaz; yeterli olgu yoksa yayın yapılmaz.

## Hype puanı

- Her yeni habere 1–10 arası tam sayı `otomasyon.hype` verilir; puan haberin kaç oyuncuyu ilgilendirdiğini ölçer, editörün beğenisini değil.
- 9–10: çok büyük oyunda (GTA, Call of Duty, Fortnite, Minecraft, EA Sports FC, League of Legends, Valorant, Counter-Strike 2 ve benzeri) çıkış tarihi, yeni oyun duyurusu, büyük ücretsiz oyun ya da herkesi etkileyen büyük değişiklik.
- 7–8: takipli oyunların yeni sezonu/büyük güncellemesi, bilinen bir oyunun çıkışı, büyük mağaza kampanyası ya da tanınmış ücretsiz oyun.
- 5–6: orta boy güncelleme, küçük ya da orta oyunun çıkışı, sınırlı kampanya.
- 1–4: küçük yama, geliştirici notu, dar kitleli haber.
- Yayın alt sınırı `kaynaklar.json` → `sinirlar.en_az_hype` (şu an 3): denetçinin verdiği puan bunun altındaysa (ör. bakım duyurusu) haber onaylansa da yayımlanmaz.
- Eşik `sosyal/ayarlar.json` → `video.hype_esigi` (şu an 5). Eşiğe ulaşan haberin video senaryosu aynı turda yazılmak zorundadır, yoksa `hazirla` paketi reddeder. Eşiğin altındaki haber için senaryo yazılmaz; o haber sitede ve Instagram'da yalnız görsel olarak paylaşılır. Puan şişirilmez: kararsız kalınan haber düşük puanı alır.

## Video senaryosu

Hype `sosyal/ayarlar.json → video.hype_esigi` (varsayılan 7) eşiğine ulaşınca aynı turda `video/senaryo/<id>-{tr,en,es,fr}.json` yazılır. `hazirla` her dosyayı `video_uret.py dogrula` ile aynı doğrulayıcıdan geçirir. Her dil için yazara bir düzeltme hakkı verilir; yine geçersiz en/es/fr dosyası atılır ve gerekçe `otomasyon.senaryo_atlanan` içine Python tarafından yazılır. Haber geçerli kalan senaryolarla yayımlanabilir; Türkçe senaryo zorunludur. de/nl/zh senaryosu şimdilik istenmez; dosya gelirse doğrulama ve yayın izin listesi kabul eder. Video üretimi ayrı hatta ve dil başına kotayla yürür.

Mevcut ayarda eşik 5, video üretim kotası dil başına 4'tür. Senaryosuz eski haberler için
`py tools/video_geri_doldur.py --kuru --dil tr --en-fazla 1` ile aday görülür; `--kuru` kaldırılınca
yalnız mevcut yerel Ollama yardımcısıyla senaryo yazılıp aynı doğrulayıcıdan geçirilir. Haber verisi,
mevcut senaryolar, render ve yayın değişmez. `video_uret.py bekleyenler --arsiv --gunluk` kalıcı eski
haberlerin geçerli senaryolarını da listeler. Saatlik sosyal kuyruk ve ağsız 24 saat denemesi için `sosyal/KURULUM.md`.

```powershell
py tools/video_uret.py dogrula --id HABER-ID --dil tr
py tools/video_uret.py bekleyenler --gunluk
py tools/video_uret.py uret --id HABER-ID --dil tr
```

Senaryo yalnız veridir: alanlar düz metindir, kod ya da komut olarak çalıştırılmaz; bilinmeyen alan hatadır. Doğrulayıcının zorladığı kurallar:

- `id` haber kimliği, `dil` dosyanın dili; `fps` 30, `boyut` `[1080, 1920]`, `sablon_surumu` 1. `bas`, `bit`, `altyazi` yazılmaz: zamanlama sesten hesaplanır.
- 3–9 sahne (hedef 4–5 sahne); ilk sahne `baslik`, son sahne `kapanis`. Tahmini süre sert sınırda 15–80 sn olmalı; kısa dikey video için hedef 20–35 sn (40 sn üzeri uyarı), anlatımın toplamı tr için 35–65, en/es/fr için 55–95 kelime önerilir (dışında uyarı).
- İlk 2 saniye kancası: `baslik` sahnesi anlatımı kısa ve çarpıcı tek cümle olmalı (tr ≤18, en/es/fr ≤24 kelime; doğrulanmış en kritik olgu/oyuncu etkisi/soru ile hemen açılır). `baslik.veri.baslik` tercihen ≤45 karakter, `baslik.veri.vurgu` ise ilk 0.5 sn'de yanacak 1–2 kanca kelimesi içermelidir (boşsa uyarı).
- Ekranda görünen ya da söylenen her sayı haberin başlığında, özetinde, metninde, oyun adında veya haber tarihinde geçmelidir. `tarih` sahnesindeki gün ve ay ("1 Aralık", "13–16 Kasım") haber metninde aynen geçmelidir; yıl yalnız haberde yazıyorsa gösterilir. Haberde olmayan bilgi senaryoya eklenmez.
- Şablon seçimi habere göre yapılır: `guncelleme` → `maddeler`, `yama_fark`, `platform` sayı kutuları; `cikis` → `tarih`, `platform`; `ucretsiz`/`indirim` → `fiyat`, `tarih`, `platform`; `haber` → `kaynak`, `maddeler`. `kaynak` sahnesi başlıkta söylenen bilgiyi aynen tekrar etmemeli; yalnız yeni bilgi veya güçlü alıntı katıyorsa eklenir (haberin `kaynaklar` sırası, 0'dan; alıntı ≤150 karakter, kaynağın sadık özeti).
- Şablon sınırları: `baslik` başlık ≤90 karakter (kısa kanca için ≤45 önerilir), `vurgu` başlıkta aynen geçen 1–3 parça, `tuslar` 1–4 tuş (en çok 3 karakter); `maddeler` 2–4 madde (≤70); `yama_fark` 1–3 satır eski → yeni; `platform` haberin `platform` listesinden en çok 4 rozet ve/veya en çok 3 sayı kutusu; `fiyat` `durum` `ucretsiz` ya da `indirim`; `kapanis` çağrı ≤60, alt ≤70.
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

Testler: id/URL/başlık/olay tekrarları, HTTPS/sahte alt alan adı, yedi dil, eski/gelecek tarih, resmî/Epic API/birincil teyit ve sızıntı reddi, bağımsız yayın grupları, günlük/tur/yazım kotası, kilit sahibi/süresi, RSS/Atom/RDF/Steam ayrıştırma, sıralama/yedek aday, model kota beklemesi ve kırık bağlantı. Gerçek taramanın kaynak başına durum/adetleri `adaylar.json`, deneme kanıtları `onayli-paket.json`, `denetimler.json` ve `sonuc.json` içindedir. Sayfa/bağlantı ve aday adetleri içerikle değiştiğinden doğrulama anında ölçülür.

Otomasyonu durdurmak için Windows'ta `Disable-ScheduledTask -TaskName 'ctrl-agame saatlik haber'` kullanılır. Günlük bakım bağımsızdır; anahtarlar hiçbir dosyaya yazılmaz.

## Hat tarafından alınmış kaynak metni

Tarama RSS content:encoded önceliğiyle description, Atom content/summary ve Steam JSON contents gövdelerini HTML/script/style ve Steam BBCode etiketlerinden arındırır; aday başına en çok 6000 karakter saklar. kaynak_metni_alani, kaynak_metni_url ve kaynak_metni_zamani kökeni gösterir. metin_var/metin_yok/metin_yeterli sayıları her kaynakta raporlanır. Gövdesi 400 karakterden kısa adayın sayfası yalnız yazıma geldiğinde Python tarafından 10 sn zaman aşımıyla indirilir; turda en çok sekiz sayfa isteği. Ana içerik yoksa veya indirme başarısızsa durum ve hata açıkça işaretlenir; kısa akış kanıtı varsa korunur.

Yazar ve denetçi metni açık JSON sınırlayıcıları içinde veri olarak alır; içindeki talimatlar uygulanmaz. Python'un adayın kendi kaynağından aldığı metin okunmuş kaynaktır; web aracının 403 vermesi tek başına ret nedeni değildir. Resmî alanın kendi akış/sayfası resmî teyit, keşif yayını yalnız aktardığı olgunun kanıtıdır. Birincil yol (adı/görevi/kurumu belli yetkili + iki bağımsız yayın), 48 saat, özgünlük ve oyuncuya fayda şartları sürer; metinde olmayan olgu yazılamaz. Python otomasyon.kaynak_metinleri alanını kendisi taşır; hazirla teyit yolunun gerekli URL'lerinin son iki saat içinde alınmış metnini de okuma kanıtı sayar.

Sağlıklı tags/ps yanıtı tek başına üretim sağlığı sayılmaz; sağlık denemesi yalnız tur başında yapılır. Paylaşılan Ollama servisi bu hat tarafından yeniden başlatılmaz. Büyük yedi dil girdileri Windows komut satırı sınırına takılmaması için OpenCode'a stdin üzerinden verilir.

Ham kaynak gövdeleri adaylar/onaylı paket ve denetim kanıtında kalır; hazirla --uygula yalnız yeni haberlerin kamuya açık veri kopyasından kaynak_metinleri alanını çıkarır. Mevcut yayımlanmış kayıtları değiştirmez.

## Dil kaydı ve yayın çıktıları

Dil adı, adresler, hreflang (zh-Hans), arayüz ve tarih biçimleri `data/diller.json` içinde tutulur. Mevcut dört dilin adresleri değişmez. `haber_hatti.yayin_dosyasi_izinli` bu kayıttan dil klasörlerini, haber/oyun/rehber klasörlerini ve `ara-<dil>.json` dosyalarını alır. Türkçe `rehber/` çıktıları da izinlidir. Haber kimliği bütün dillerde aynıdır.
