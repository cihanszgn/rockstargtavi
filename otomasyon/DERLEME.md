# Derleme aracı (`tools/klip_derleme.py`)

Türk yayıncıların Kick kesitlerinden ve viral kısa videolardan 10–12 dk'lık, 1920x1080 yatay, sesli YouTube **derleme videosu** üretir.
Yalnız paket üretir: hiçbir yere yüklemez, sosyal kuyruğa kayıt eklemez. Ayar: `otomasyon/derleme.json`. Testler: `tests/test_klip_derleme.py`.

## Komutlar (hepsi `tools/` içinden, `py` ile)

```
py klip_derleme.py topla  [--gun 7] [--kaynaklar paket,izleyici,viral] > adaylar.json   # aday listesi, indirmez
py klip_derleme.py uret   [--sure-dk 11] [--yalniz-yayinci] [--viral-oran 2] [--kuru]  # seç, indir/kes, tek mp4
py klip_derleme.py uret   --adaylar-dosyasi adaylar.json                               # toplamayı atla
py klip_derleme.py dogrula <derleme-klasoru>                                           # ölçüm + kare çıkarma
py klip_derleme.py uret   --deneme                                                     # deneme: durum.json'a yazmaz
```
`--kuru`: yalnız plan (indirme/kodlama yok). `--zorla`: önceki parça dosyalarını yeniden üret. Kodlama yalnız CPU (libx264); GPU/NVENC kullanılmaz.

`--deneme`: çıktı `derleme/deneme-<tarihsaat>/` klasörüne gider; `durum.json` okunur ama **yazılmaz** (seri sayısı ve kullanılanlar değişmez) ve daha önce kullanılmış videolar da aday sayılır. Deneme derlemesi yayınlanmış sayılmaz; gerçek derleme için `--deneme` olmadan üret.

## Ne yapar

1. **Toplar** (3 kaynak): (a) `paket` — `tools/yayin_klip.py` paketleri (`cikti/*/klip-NN|canli-NN.json`); aynı aralık Kick HLS'ten **yatay** yeniden kesilir, yayın kalkmışsa dikey mp4'e düşülür; (b) `izleyici` — Kick izleyici klipleri `/api/v2/channels/<kanal>/clips?sort=view&time=…`; (c) `viral` — elle `ara-videolar/`, ayardaki bağlantılar, YouTube Shorts (yt-dlp).
2. **Süzer**: gün/izlenme/süre, kopya, aynı yayının örtüşen aralığı (`#EXT-X-PROGRAM-DATE-TIME` ile), daha önce kullanılmış video (`.scratch/yayin-klip/derleme/durum.json`).
3. **Planlar**: teaser (en iyi 2 andan 2'şer sn) → giriş kartı → döngü (1 yayıncı kesiti + `yayinci_basina_viral` viral) → kapanış kartı. Viral yoksa yalnız yayıncı/izleyici klibiyle de çıkar. Doğrudan kesme.
4. **Hazırlar**: her parça 1920x1080/30 fps/48 kHz stereo, iki geçişli loudnorm (−16 LUFS); dikey video yatay tuvalde kendi bulanık kopyası üstünde ortalı; köşede yarı saydam filigran; yayıncı kesitinde sol altta ilk 3 sn kaynak etiketi (Türkçe karakter doğru).
5. **Birleştirir** (concat demuxer, son libx264/AAC kodlaması) ve yazar.

Çıktı: `.scratch/yayin-klip/derleme/<seri>-<sayı>/` → `derleme.mp4`, `derleme.json` (parça listesi, başlık, açıklama, `yayinlandi: false`, uyarılar, elenenler, ölçüm), `aciklama.txt` (yayıncı bağlantıları + zaman damgalı bölümler + her videonun kaynağı), `liste.txt`, `kucuk-resim-1..3.png` (en iyi 3 andan), `parcalar/`; `dogrula` ayrıca `dogrulama.json` ve `kareler/` yazar.
Başlık: `<BÜYÜK HARF OLAY> | <Seri Adı> #<Sayı>`. Seri sayısı `durum.json`da artar.

## Seçim kuralları (2. tur)
- **Paket öncelik ve örtüşme:** aynı yayında (VOD) zaman aralığı örtüşen yayıncı paketlerinden yalnız biri kullanılır. Öncelik `konusma-hizali` > `konusma` (`konusma-ek-*` dahil) > `canli` > `klip`; eşitlikte yüksek değer. Örtüşme `ortusme_esik_sn` (5 sn) üstüyse eleme olur (`paket_ortusme`).
- **Konuşma paketi kesiti:** paketlerde cümle zamanı yok (`konusma_puani`, `konusma_plan_araligi`, `dokum_metni` var). Bu yüzden konuşma paketinde kesit, modelin verdiği aralığın **başından** alınır (yöntem `konusma_bas`); bitiş cümle sonuna oturmayabilir. Cümle zamanı paketlere eklenirse `_cumleler` onu okur.
- **Türkçe süzgeci (Shorts):** dil alanı `tr` ise geçer; başka dil elenir (`dil_turkce_degil`). Dil boşsa başlık + kanal + açıklamanın ilk 200 karakterinde Türkçe harf (ç ğ ı İ ö ş ü) ya da ayardaki kelimelerden 2 ya da fazlası aranır (`turkce_izi_yok`). Başlıkta Latin dışı yazı varsa `baslik_latin_disi`. Etiketler atılınca başlıkta `viral_min_kelime` (2) kelimeden az kalırsa `baslik_cok_az_kelime`. `viral_turkce_sart: false` ile kapanır. Elle seçilen (bağlantı, ara-videolar) videolara uygulanmaz.
- **Eşik:** `viral_min_izlenme` 250 000 (100 000'den yükseltildi). Gerekçe: ham Shorts listesinde (195 aday, 2026-11-18) 100 000–250 000 bandı 26 aday (%13); `keşfet` etiketi bu bantta ilgisiz içerik getiriyor. Eşik 250 000 ile 136 aday kalıyor.
- **Kanal sınırı:** aynı Shorts kanalından en çok `viral_kanal_ust` (2) video (`kanal_ust`).
- **Yayıncı başına üst sınır:** izleyici klibi en çok `izleyici_kanal_ust` (3); derlemede yayıncı başına toplam kesit (yayıncı kesiti + izleyici klibi) en çok `yayinci_toplam_ust` (6). Taşan adaylar `izleyici_kanal_ust` / `yayinci_toplam_ust` nedeniyle elenir.
- **Başlık kaynağı (sırayla):** (1) konuşma paketinin başlığı (en değerli, vurucu); (2) en çok izlenen anlamlı izleyici klibi başlığı; (3) eski şablon başlık (yayıncı kesiti, yoksa izleyici klibi) en son çare. Viral yalnız hiç yayıncı/izleyici parçası yoksa kullanılır. Anlamsız başlıklar (3 harften kısa, ünlüsüz, ya da en çok 3 farklı harfli klavye ezmesi: `ss`, `zzz`, `QWEQWEEWQWEQWEQ`) başlık ve teaser adayı olamaz; parça olarak kalabilir.
- **Teaser:** yalnız yayıncı/izleyici içeriğinden; yayıncı yoksa viral.
- **Elenen adaylar:** `derleme.json` → `elenen_adaylar`: her elenen aday için `id`, `neden`, `baslik`, `kaynak` (süzgeçler, üst sınırlar, örtüşme, önceki derlemede kullanılma, hazırlama hatası).

## Sıra kuralı
Değer: paket zirve puanı/100; izleyici ve viral için log izlenme (izleyici × `izleyici_agirlik` 0.75). En iyi parça başa, ikinci en iyi sona; aynı yayıncı art arda gelmez (önce orta takasla giderilir; yetmezse uyarı verilir). Art arda sayımı yayıncı kesiti ve izleyici klibini birlikte sayar; viral aradaysa da bitişik sayılır.

## Ayarlar (`derleme.json` → `ayar`; yazılmayan koddaki varsayılanı alır)

| Ayar | Varsayılan | Anlam |
|---|---|---|
| `seri_adi`, `filigran_yazi` | Yayın Kolajı, CTRL+A GAME | başlık serisi, köşe yazısı |
| `sure_dk` / `sure_min_dk` / `sure_max_dk` | 11 / 10 / 12 | hedef ve sınırlar |
| `yayinci_basina_viral` | 2 | döngüde yayıncı kesiti başına viral sayısı (0 = yalnız yayıncı) |
| `viral_dolgu` | true | kesit bitince bütçeyi viralle doldur |
| `kesit_min/hedef/max_sn` | 12 / 22 / 28 | yayıncı kesiti süresi |
| `viral_min_sn` / `viral_max_sn`, `viral_uzun` | 5 / 30, `ele` | viral süre sınırı; uzunsa ele (`kirp` ilk kısmı alır) |
| `viral_min_izlenme`, `viral_gun` | 100000, 90 | Shorts süzgeci |
| `gun` | 7 | yayıncı kesiti/izleyici klibi yaş sınırı |
| `izleyici_min_izlenme`, `izleyici_max_sn`, `izleyici_uzun` | 5, 60, `kirp` | izleyici klibi süzgeci |
| `ses_hedef_lufs` | −16 | loudnorm hedefi |
| `ek_kick_kanallari`, `baglantilar`, `ara_video_klasoru`, `shorts_kaynaklari` | | ek kaynaklar |

## Elle viral video
`C:\Cihan.Ai\.scratch\yayin-klip\ara-videolar\` içine mp4 bırak (varsayılan klasör) veya `baglantilar` listesine bağlantı ekle; elle seçilenlere izlenme/tarih süzgeci uygulanmaz.

## Deneme (2. tur, 2026-11-18): `uret --deneme`

Çıktı: `.scratch/yayin-klip/derleme/deneme-20261118-090034/` (`derleme.mp4`, 287 MB, 10:37 = 637,67 sn, 1920x1080/30 fps). Üretim 666 sn (CPU). `durum.json` hash'i üretimden önce ve sonra aynı (değişmedi).
- Parça: 10 yayıncı kesiti, 11 izleyici klibi, 15 viral (+2 teaser, giriş, kapanış). Yayıncı dağılımı: Kemalcan Parlak 6, Eraycan 6, wtcN 4, Jahrein 3, Tolunay Ören 2 (önceki derlemede Eraycan 9 izleyici klibiyle tek başına baskındı).
- Başlık: `ZEHRA'NIN DİSCORDUNU DENEYELİM` (`en_cok_izlenen_izleyici_klibi`); bu planda konuşma paketi yoktu. Teaser yalnız yayıncı kesitlerinden.
- Uyarı: `viral yetmedi: 21 kesit için 42 viral istendi, 15 var`. Kesit sayısı 21'de kaldı (`izleyici_kanal_ust` 41 aday, `yayinci_toplam_ust` 13 aday elendi); süre yine de 10–12 dk aralığında.
- Doğrulama (`dogrula`, geçti): görüntü 637,6 / ses 637,65 sn (fark 0,05 sn); kapanış geçişi 0,007 sn sapma; 6 parçada LUFS −15,3…−17,0 (hedef −16 ±2 içinde); 10 kare + 1 izleyici klibi karesi (`kareler/`).
- Elenenler (`elenen_adaylar`): cok_uzun 116, dusuk_izlenme 57, izleyici_kanal_ust 41, dil_turkce_degil 17, yayinci_toplam_ust 13, gun_disi 10, ortusme 8, baslik_latin_disi 4, baslik_cok_az_kelime 3, onceki_derlemede_kullanildi (genel süzgeçte, ayrı sayılır).

**Açık kalanlar:** viral havuzu yetersiz (15 < 42). En büyük neden `viral_max_sn` 15 sn (`cok_uzun` 116). Hedef 11 dk'ya yaklaşmak için `viral_uzun: kirp` ya da kesit üst sınırını artırmak gerekir; kaliteyi düşürmeden bu tur yapılmadı.

## Ölçümler (2026-11-18, gerçek veri, bu bilgisayar)

Derleme `yayin-kolaji-1`: 10:56,9 (656,93 sn), 1920x1080, 30 fps, 327 MB; 44 parça = 6 yayıncı kesiti + 9 izleyici klibi + 29 viral (+2 teaser, giriş, kapanış).
- Süre: toplama ≈ 3 dk (YouTube Shorts ayrıntı çözümü yavaş); hazırlama 125,6 sn; toplam üretim 356,5 sn (CPU, libx264 medium); indirilen 24,7 MB (HLS kesitleri + Shorts + klipler), çıktı 327 MB.
- Kaynak başına (bulunan → kalan): paket 16 → 13 (3 eski yöntem klasörü elendi); izleyici klibi 100 → 73 (20 çok uzun, 7 gün dışı; kanal başına 20 → 13–16); Shorts etiketleri (30'ar): komik 8, mizah 9, keşfet 16, komedi 4 kaldı (çoğu `cok_uzun`: Shorts 15 sn'den uzun); yayıncı kanalı Shorts'ları (15'er) kalan 0 (düşük izlenme / ayrıntı çözülemedi).
- Doğrulama (`dogrula`, hepsi geçti): akış süreleri görüntü 656,86 / ses 656,93 sn (fark 0,07 sn); kapanış kartı plan 651,94 sn / gerçek geçiş 651,93 sn (fark 0,007 sn); 6 parçada LUFS −15,6…−16,2 (hedef −16 ±2); 10 kare çıkarıldı ve gözle bakıldı.
- Yalnız yayıncı modu (`--yalniz-yayinci`, kuru plan): 4 yayıncı + 26 izleyici klibi, 656 sn, uyarısız.

### Kick ölçümü (izleyici klipleri)
`sort=view` her zaman izlenmeye göre azalan sıralar (`sort=date` tarihe göre değil); `time=day|week|month` pencereleri gerçekten farklı sonuç verir. İstek başlığı `User-Agent: Mozilla/5.0` gerekir. İzleyici klipleri çoğunlukla düşük izlenmelidir (eşik 5).

### YouTube "bot değilsin" engeli
yt-dlp, çerezsiz ilk denemede bazı videolarda `Sign in to confirm you're not a bot` verebilir. Araç bu durumda çerez kullanmadan `--extractor-args youtube:player_client=android,ios,tv` ile bir kez daha dener (çalıştı; indirilen Shorts 360p'ye düşebilir). Yine olmazsa video elenir, plan yenisini seçer. Çerez/oturum kullanılmaz.

## Bilinen belirsizlikler ve zayıflıklar
- Yayıncı çeşitliliği az (3 yayıncı): aynı yayıncı art arda gelmeden kaçınılamıyor (uyarı verir); derlemede 6 yerde oldu.
- Viral hedefi tutmadı (15 kesit için 30 istendi, 29 geldi). Shorts'ların çoğu >15 sn olduğundan `viral_uzun: ele` ile elenir; `kirp` ayarı yoluyla alınabilir ama kesik başlar.
- Örtüşme tespiti için yayın zaman damgası gerekir; epoch bilgisi olmayan adaylar (örtüşmesi bilinmeyen) elenmez, aynı anın iki kez girmesi mümkündür.
- YouTube Shorts üçüncü kişi içeriğidir (telif/izin riski); yayın öncesi kaynak bağlantılarını ve izni gözden geçirin. Shorts yalnız ev IP'sinden çalışır; veri merkezi sunucusu bot engeline takılır.
- Kaynak etiketi oyun içi sohbet/arayüzle çakışabilir; filigran küçük (opaklık 0,35).
- 30 fps'e eşitlenir; 60 fps kaynaklar 30'a iner. Üretim yalnız CPU; ~6 dk'lık iş bu bilgisayarı meşgul eder.

## Yapay görüntü süzgeci ve kısa olay yazıları (18.11.2026)

`viral_max_sn` artık **30** (önceki ölçümlerdeki 15 sn sınırı tarihseldir). Yayıncı/viral sıra kuralı ve üst sınırlar değişmedi.
`viral_yz_izleri` başlık, açıklama, etiket, kanal/yükleyen adı, kanal açıklaması, kategori, alternatif başlık,
sanatçı/parça/albüm ve bölüm adlarında Unicode kelime bütünüyle aranır. URL, biçim/codec kimliği, yorum ve öneriler taranmaz.
Shorts düz listesinde görünen iz hemen elenir; ayrıntı çözülünce yeniden denetlenir. Eleme nedeni `yapay_zeka`dır.
Kanal açıklaması yt-dlp kanal çıktısından alınır ve aynı çalıştırmada kanal başına bir kez okunur; okunamazsa uyarı yazılır.
`viral_kanal_kara_liste` kanal adı, @kullanıcı adı veya kanal kimliğini tam eşleştirir; büyük/küçük harf duyarsızdır.
Bağlantı/dosya kaynakları ve dışarıdan okunan aday listeleri de süzgece girer. Dosya yanındaki JSON üst verisi kullanılır.

Varsayılan izler: `ai`, `ai generated`, `ai video`, `yapay zeka`, `yapay zekâ`, `yz ile`, `sora`, `veo 3`, `veo3`,
`kling`, `runway`, `midjourney`, `pika`, `hailuo`, `luma`, `suno`, `aiart`, `aivideo`, `chatgpt`, `gemini`, `deepfake`.
NFKC dönüşümü süslü Unicode AI yazısını da yakalar. `kaIl`, `Aile`, `said`, `Dubai`, `Soralım`, `Pikachu` elenmez.
Temkinli kuralın bedeli: **“Gemini burcu”, “runway defilesi”, yapay zekâyı tartışan gerçek kayıt veya “AI kullanılmadı”**
da elenebilir. Bu kelimeleri gerçekten kullanan içerik gerekiyorsa ayardaki ilgili izi kaldırmak gerekir.
Bir kanaldaki AI beyanı o kanalın bütün videolarını engeller; karışık üretim yapan kanalda gerçek video da elenebilir.
Yapay sesle anlatılan gerçek görüntü bu isteğin kapsamı dışındadır; sesin yapaylığını sınıflandıran adım yoktur.

### Görsel denetim ve gerçek yt-dlp ölçümü

`klip_konusma.ModelYolu.__call__(prompt)` → `haber_hatti.Hat.model(spec,prompt)` yalnız metni stdin olarak gönderiyor.
Görüntü içerik bloğu/dosya eki arayüzü yok; Sonnet çağrısında `--tools ''`, dosya ve MCP erişimi kapalı.
Dolayısıyla kare yolu yazmak görüntüyü aktarmıyor. Güvenilir olmayan bir kontrol eklenmedi; `viral_yz_gorsel_denetim`
anahtarı da desteklenmiyor. Otomatik görsel çağrı sayısı **0**. Üst verisinde beyan bulunmayan yeni yapay içerik kaçabilir.
İki kareyle insan incelemesi de kesin köken kanıtı değildir; şüpheli bilinen kanallar temkinli kara listeye alınabilir.

yt-dlp **2026.10.26**, çerezsiz video ayrıntısı + kanal ayrıntısı ile 18.11.2026'da ölçüldü:
bilinen yapay Shorts `86WgQG3Sj4o` (başlıkta `#AI`, kanalında “Yapay zekâ ile hazırlanan komedi videoları”)
ve gerçek çekim `oeRMmxrdPgk` (Mehmet Ali Doğan), ayrıca son denemenin 15 virali.
Bu **16 çıktıda** ayrı `synthetic`/`altered`/`generated`/`disclosure`/`ai_` bildirim alanı **yoktu**.
Kurulu YouTube extractor kaynak kodunda da `synthetic|altered|is_ai|ai_generated` araması eşleşmedi.
Bu, YouTube arayüzünde bildirim bulunmadığını veya gelecekte yt-dlp'nin alan eklemeyeceğini söylemez.
Ham ölçüm (video + kanal açıklamaları): `C:\Cihan.Ai\.scratch\yayin-klip\derleme\scratch\yz-olcum-20261118.json`.

Önceki `deneme-20261118-090034` içindeki 15 viral yeniden değerlendirildi:
`ysX6QNRgYOo` **Büyümez Bunlar** kanal açıklamasındaki “AI destekli görsel/metin araçları” nedeniyle elenir.
30 karelik elle incelemede yapay görüntü şüphesiyle **Bir Mesele Var** (`FpFFyUgcTHk`),
**Muzo | Her İşin Adamı** (`6McE2tRwZIc`), **FATOŞ'un MUTFAĞI** (`kFQwQG35RWk`) da kanal kimliğiyle kara listeye alındı;
bu üçü kesin teknik köken tespiti değildir. Kalan 11 videoda süzgeç eşleşmedi; bu bir gerçeklik sertifikası değildir.
İlk derlemedeki `86WgQG3Sj4o` hem `#AI` hem kanal beyanıyla elenir; bu video son denemenin 15'i arasında değildi.
Kareler: `C:\Cihan.Ai\.scratch\yayin-klip\derleme\scratch\onceki-yz-kareler\grup-1..3.jpg`.
Yeni adayların elle kare incelemesinde ayrıca **Dur Ben Bir Maymunluk Yapayım** (`UCB4xCns2J6LjQOLhO6le6_w`)
ve **Hüseyin Akça** (`UCgC06bb0m0JypfNu65yPZ4g`) temkinli listeye alındı. Bu iki kanalda üst veri beyanı
bulunmadı; görüntüdeki stil/beden-oranları nedeniyle şüpheli kabul edildiler. Yanlış eleme olasılığı vardır;
bu karar otomatik sınıflandırma başarısı veya doğrulanmış üretim kökeni olarak sayılmaz.

### Açıklama yazısının kaynağı ve görünümü

Sıra: (1) konuşma paketinin anlamlı başlığı, yoksa gerekçesi; (2) anlamlı izleyici klibi başlığı;
(3) kısa ve anlamlı viral başlığı; (4) kesin kesitin ses dökümüyle **tek toplu Sonnet çağrısı**.
Eski “yayınında sohbet bir anda gülmeye başladı” başlıkları olay açıklaması sayılmaz.
`ss`, `.`, `...`, `aaaa`, `zzz`, `pembiş` gibi belirsiz tek kelimeler, emoji/etiket yığınları ve tık tuzağı reddedilir.
Uzun metnin yüklemi körlemesine kesilmez; 45 karakteri aşarsa döküm/model aşamasına bırakılır.
Kullanıcının verdiği klip başlığının doğruluğu otomatik kanıtlanmış değildir; model yalnız dökümü görür.
Görülmeyen olay tahmin edilmemesi istenir; belirsiz dökümde `null` → yazısız parça.

Mevcut `klip_konusma.dok_calistir` içe aktarılır: **small / CPU / int8 / yedek=False**.
Kesin hazırlanmış parçanın sesi kullanılır; başka çalışanın GPU dökümüne/ayarlarına dokunulmaz.
Gerekli arayüz değişirse uyarı verilir; araç açıklamasız devam eder.
Yeni servis/anahtar yok: haber ayarındaki Sonnet taşıması kullanılır. Bütün eksik açıklamalar bir JSON isteğine girer.
`aciklama_model_butcesi` üst tavanı **3** (kodda da 3'e sınırlı); mevcut akışta tek toplu istek, yeniden deneme yoktur.
Görsel çağrı yoktur. Bütçe 0, kota, bozuk JSON veya taşıma hatası üretimi çökertmez; uyarıyla yazısız devam edilir.
Sonuç/null/hata ve döküm, `derleme/aciklama-onbellek/<kesit-imzası>/` içinde saklanır; aynı kesit yeniden modele gönderilmez.
Kesim aralığı, gerçek süre, kısa adlar, uzunluk ve CPU model adı imzaya girer. Hata sonucu da saklanır.

`aciklama_etkin:true`; `--aciklamasiz` veya `aciklama_etkin:false` yazı/döküm/model aşamalarını kapatır.
`aciklama_sn:0` parçanın tamamı, pozitif N yalnız ilk N saniye. Varsayılan tam süre seçildi: izleyici parçaya sonradan
baktığında da bağlamı görür. `aciklama_azami_karakter:45`, `aciklama_punto:54`, `aciklama_dokum_model:"small"`.
`yayinci_kisa_adlar`: wtcN→Ferit, Eraycan→Eray, Kemalcan Parlak→Kemalcan, Tolunay Ören→Tolunay, Jahrein→Jahrein.
Etiket/emoji atılır, büyük harf yığını sadeleşir. Fontun gerçek piksel ölçümüyle en çok iki satır kullanılır.
1920×1080 tuvalde yazı yatay ortalı, alt kenardan 138 piksel yukarıda biter; beyaz 54 punto, siyah %62 bant.
Kaynak etiketinin kutusu alttaki 130 piksel, filigran sağ üsttedir; konum kutuları kesişmez.
Alt bant yüzlerin genellikle bulunduğu üst yarıyı açık bırakır; otomatik yüz/nesne takibi yoktur.
Dikey videoda da aynı tuval konumu kullanılır. Örnek kanal kareleri incelendi (`bk_127_grid36`, `mo_785_intro20`).

Her parça kaydında `aciklama`, `aciklama_kaynagi` bulunur (boşsa null). Bölümler açıklamayı kullanır;
olay açıklaması yoksa yalnız yayıncı/kanal adı yazılır. Derleme başlığında açıklaması olan en değerli yayıncı/izleyici
parçası önce gelir. Kaynaklar `konusma_paketi`, `izleyici_basligi`, `viral_basligi`, `dokum_model` olarak raporlanır.
