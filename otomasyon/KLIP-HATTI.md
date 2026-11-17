# Yayın klip hattı

Biten bir yayının sohbet yoğunluğundan 9:16 dikey klip paketi üretir. **Yayın yapmaz**: sosyal kuyruğa kayıt eklemez, hiçbir yere yüklemez. Çıktıyı (mp4 + json) sen incelersin.

Araç: `tools/yayin_klip.py` · yayıncı listesi: `otomasyon/klip-yayincilar.json` · testler: `py -m unittest discover -s tests -p "test_yayin_klip.py"`

## Komutlar

```
py tools/yayin_klip.py tara                      # son 7 günün biten yayınları, işlenmişler atlanır
py tools/yayin_klip.py tara --yayinci jahrein --hepsi
py tools/yayin_klip.py analiz kick:<uuid>        # sohbeti indir, zirveleri bul (JSON yazdırır)
py tools/yayin_klip.py kes kick:<uuid>           # analiz + klipleri kes + paketle
py tools/yayin_klip.py otomatik --en-cok 3       # tara + kes (yeni yayınların ilk 3'ü)
```

`<vod>` olarak `kick:<uuid>`, çıplak uuid veya `https://kick.com/<kanal>/videos/<uuid>` verilir. `analiz` ve `kes` için `--esik-k`, `--min-mesaj`, `--min-oran`, `--azami-klip`, `--bas-dislama-sn`, `--min-farkli-kullanici`, `--min-emote-disi-oran`, `--duzen kadraj|serit`, `--kadraj-oran`, `--yontem sinyal|yogunluk`, `--klip-baslangic dalga|tepe`, `--gulme-esik-k`, `--konu-min-kisi`, `--konu-min-lift`, `--max-gurultu-oran` ile o çalıştırmaya özel ayar verilir; `--yeniden` analizi önbellekten almaz, `--zorla` var olan klibi yeniden üretir, `--suzgecsiz` oyun süzgecine uymayan yayını da işler.

## Nasıl çalışır

Varsayılan yöntem **sinyal** (`yontem: sinyal`, 2026-11-17). Hedef: "sohbet kalabalık" değil "sohbet güldü / aynı konuda toplandı" anını bulmak. Model çağrısı yok, yalnız standart kütüphane; bütün listeler ve eşikler `klip-yayincilar.json` içindedir.

1. **Mesaj sınıfı.** Sohbet 10 sn'lik dilimlere ayrılır; her mesaj tek tek sınıflanır:
   - *gürültü* (kahkaha sayılmaz, dilimin `gurultu_oran`ına girer): **komut** (`!` ile başlayan), **oy** (tek karakter, yalnız rakam/noktalama, ya da `oy_kelimeleri`: evet, hayır, katıl…), **emote yağmuru** (yazısız, yalnız dans/alkış sınıfı emote'lar: `emote_gurultu`). Ayrıca **yayılma** (aynı metnin kopyası: ≥12 karakter, ≥3 kelime, ≥6 farklı kişi) kahkaha ve yoğunluk sayımına girmez; yalnız konu bileşenine yarım ağırlıkla (`yayilma_konu_agirlik` 0.5) girer.
   - *kahkaha*: HAHA/XD/SJ kalıpları; **klavye ezmesi** (≥5 harf, harflerin ≥%80'i orta sıra `asdfghjkl`, ünlü oranı ≤%34 ve ayrıca ünlüsüz / 3 ardışık ünsüz / klavye dizisi / tekrarlı ikili; "bakkkk" gibi 3+ uzatma önce tek harfe iner); `gulme_kelimeleri`; `gulme_emojileri`; `emote_gulme` sınıfındaki emote'lar. **Gerçek kelime sayılmaz** (testli: "sadakat", "kasada", "askıda", "dakika"); `gulme_istisna` listesindeki kelime ("kafkas") kahkaha olmaz.
   - *şaşkınlık* (`emote_saskin`): pozitif ama kahkahanın yarısı kadar (`saskin_agirlik` 0.5).
   - Aynı kişi bir dilimde bir kez sayılır.
2. **Üç bileşen** (her dilim için 0–1):
   - **G, kahkaha**: dilimde gülen *farklı kişi* sayısı (şaşkınlar yarım) `gulme_tam_kisi` (15) ve gülen mesaj oranı `gulme_tam_oran` (0.30) üzerinden, ikisi yarı yarıya.
   - **K, ortak konu**: yayının geri kalanında nadir olup dilimde **birçok FARKLI kişi** tarafından yazılan kelime/ikili (`konu_min_kisi` 6, yayının kalanına göre `konu_min_lift` 10; `konu_tam_kisi` 12 kişide tam puan). Örn. "ana bacı" (7 kişi, kalanından ~280 kat sık).
   - **Y, yoğunluk**: gürültüsüz mesaj sayısının z puanı (`yogunluk_tam_z` 6'da tam). Yalnız bileşen; **tek başına zirve yapmaz**.
   - Toplam (0–100) = 100·(0.5·G + 0.3·K + 0.2·Y) (`agirlik_gulme/konu/yogunluk`).
3. **Zirve koşulu.** Dilim ancak (a) gülen kişi sayısı `max(gulme_min_kisi 6, ortalama + gulme_esik_k·std)` eşiğini ve gülen mesaj oranı `gulme_min_oran` (0.15) değerini geçerse ya da (b) ortak konu bulunursa aday olur; en az `min_sinyal_mesaj` (10) gürültüsüz mesaj gerekir. Gürültü oranı ≥ `max_gurultu_oran` (0.5) olan dilim **`oy_seli`** diye elenir (aday olacaktı ya da eski eşiği geçiyordu). Kalan adaylara eski **zayıf zirve elemesi** yine uygulanır (`min_farkli_kullanici` 25, `min_emote_disi_oran` 0.25); elenenler analiz JSON'unda `elenen_zirveler` altında nedeniyle durur.
4. **Klip başlangıcı.** Kahkaha olaydan *sonra* gelir; referans kahkaha dalgasının **başladığı dilimdir**: ilk uygun dilimden geriye en çok `dalga_geri_azami_dilim` (3) dilim yürünür, sinyal eşiğin `dalga_geri_oran` (0.4) katının üstünde kaldığı sürece. Klip dalga başından **`onceden_sn` (20) önce** başlar, son zirve diliminden `kuyruk_sn` (12) sonra biter, 30–55 sn arası kalır. `klip_baslangic: tepe` eski davranıştır (en yüksek dilimin 20 sn öncesi). Dalga başı paket JSON'unda `dalga_basi_sn`.
5. Yayın başına en çok `azami_klip` (3) klip, birbiriyle örtüşmeyen, toplam puanı en yüksek olanlar; çıktı zamana göre sıralı. Yayının ilk 5 dk'sı (`bas_dislama_sn`) ve son 3 dk'sı (`son_dislama_sn`) sayılmaz.
6. **Başlık/açıklama** hâlâ sabit şablon (model yok) ama baskın sinyale göre seçilir: `gulme` → sohbetin güldüğünü söyleyen ölçülü şablonlar; `konu` ve terim varsa → o terimli konu şablonu; baskın sinyal yoksa (eski yöntem) eski şablonlar. Paket JSON'una `baskin_sinyal`, `puan_bilesenleri` (G/K/Y puanı, kişi sayıları, gürültü dökümü), `dalga_basi_sn` yazılır.

### Eski yöntem (`yontem: yogunluk`)

Eşik = en büyük( ortalama + `esik_k`·std, `min_mesaj`, `min_oran`·ortalama ); eşiği geçen dilimler `birlestir_sn` (30) içinde tek klipte birleşir; klip ilk zirve diliminden 20 sn önce başlar; zayıf zirve elemesi (25 kişi / 0.25 emote dışı) aynıdır; puan = (zirve − ortalama)/std. Sorun: mesaj *sayısı* "1/2" oylarını da zirve sayar. Birim testlerin çoğu bu yöntemle çalışır (`AYAR`'da `yontem: yogunluk`).

### Klip üretimi (iki yöntemde de aynı)

- `kes` yalnız klip aralığını HLS'ten çeker (tüm yayını indirmez), 1080x1920 H.264+AAC yapar. İki düzen var (`duzen` ayarı):
   - **kadraj** (varsayılan): yayın ortadan kırpılır (`kadraj_oran` 1.2 ⇒ 1080x900 görüntü; 1.0 kare, 4/3 ⇒ 1080x810, 1.78 ⇒ kırpma yok) ve tam genişlikte, orta çizgisi y=880'de durur. Arkada bulanık kopya; yazılar görüntünün **dışında**: üstte yayıncı adı + oyun, altta "Kaynak: kick.com/<kanal>" ve marka; hiçbiri görüntünün üstüne binmez (testle güvenceli, yazı yeri görüntü yüksekliğine göre hesaplanır).
   - **serit** (eski): tam genişlikte 16:9 şerit (1080x608), üst/altı bulanık.
   Düzen `tools/yayin_klip.py` içindeki `DUZEN` sözlüğünde. Düzen ya da klip penceresi değişince `kes` var olan klibi kendiliğinden yeniden üretir (paketteki `duzen` imzası ve klip aralığı karşılaştırılır).
- Sohbet–video hizası: yayının gerçek başlangıcı HLS listesindeki ilk `PROGRAM-DATE-TIME`'dan alınır (API'deki `start_time` 3–6 sn geç kalıyor).

### Eleme ölçümü, eski yöntem (gerçek veri)

Kemalcan Parlak yayını (`kick:9ae47b40-…`, 2026-11-15, 139 dk), eşikler 25 kişi / 0.25:

| Zirve | Mesaj | Farklı kişi | Emote dışı oran | Sonuç |
|---|---|---|---|---|
| 6:20 (eski klip-01) | 384 | 145 | 0.797 | kaldı |
| 8:20 (eski klip-02) | 162 | 83 | 0.142 | **elendi** (emote ağırlıklı) |
| 40:50 (eski klip-03) | 105 | 87 | 0.952 | kaldı |
| 32:40 | 42 | 37 | 0.238 | elendi (sınırda) |
| 1:33:10 | 62 | 46 | 0.306 | kaldı, elenenin yerine 3. klip oldu |

Eşikler tek yayına bakılarak seçildi; farklı kişi sayısı tek başına 8:20'yi (83) ve 40:50'yi (87) ayırmaz, ayıran emote dışı orandır. 6:20 ve 40:50 "1/2" gibi tek karakterli oylardır: ölçüt bunları yazı sayar (yalnız `[emote:..]` seli elenir). 0.25 sınırı 32:40'a çok yakın; gerekirse `min_emote_disi_oran` yayıncı bazında ayarlanır.

### Eski ↔ yeni yöntem (gerçek veri, 2026-11-17)

İki yayın: Kemalcan Parlak, Just Chatting, 15.11 (`kick:9ae47b40-…`, 11 461 mesaj) ve Eraycan, Potato Please, 12.11 (`kick:d38999bc-…`, 20 077 mesaj). Değerlendirme (iyi / sınırda / zayıf) tek insan gözüyle, mesaj örneklerine ve klibe bakılarak yapıldı; kesin ölçü değil.

| Yayın · an | Eski yöntem | Yeni yöntem (G kahkaha kişi · K konu · toplam) | Örnek mesajlar | Değerlendirme |
|---|---|---|---|---|
| Kemalcan 6:20 | klip-01 (113 mesaj) | **elendi: oy_seli 0.91** (102 oy) | "2", "1", "11", `1000X` emote, "AAAA…" | eski **zayıf** |
| Kemalcan 8:20 | elendi (emote ağırlıklı) | elendi: oy_seli 0.69 (43 emote yağmuru) | emote yağmuru | – |
| Kemalcan 40:50 | klip-02 (105 mesaj) | **elendi: oy_seli 0.86** (90 oy) | "1", "2", "HAFTADIR YOKTUN ADAM MİLLİ OLMUŞ", X topluluğu reklamı | eski **zayıf** |
| Kemalcan 22:00 | seçilmedi | **klip-01**: G 13 kişi, K "ana bacı" 7 kişi, 75.9 | "olm ana bacı yapma", "SAÇINI SİKTİĞİME BAK", `KEKW`, "o ney amk" | **sınırda** (didişme, az gerçek kahkaha) |
| Kemalcan 44:10 | seçilmedi | **klip-02**: G 26 kişi, 65.1 | `ICANT`, `GoldenKEKW`, "AWDWALDAİDKAWDKAW", "döllenmis boxer", "BUNLAR NE KADAR PİSLİK YA" | **iyi** |
| Kemalcan 1:33:10 | klip-03 (eski, 62 mesaj) | **klip-03**: G 30 kişi, 69.9 | `LULW`, `KEKW`, "MAYINA BASTI", "MAYIN" | **iyi** (eskide de vardı) |
| Eraycan 13:30 | klip-01 (82 mesaj) | **klip-01**: G 31 kişi, 64.9 | `GoldenKEKW`, `HYPERCLAP`, `KEKW` | **iyi/sınırda** |
| Eraycan 31:50 | seçilmedi | **klip-02**: G 12 kişi, K "yarısı" 6 kişi, 64.3 | `KEKW` ×6, "bitti", "nabiyon" | **sınırda** |
| Eraycan 49:50 | **elendi** (emote ağırlıklı 0.216) | **klip-03**: G 61 kişi, 68.8 | `KEKW`, "hehe", "ADAM DİSCORDU WHATSAPP DİYE OKUDU" | **iyi** (eski yöntem kaçırmıştı) |
| Eraycan 39:00 | klip-02 (100 mesaj) | seçilmedi (4. sırada, 52.5) | "GELDİ", "HAYDAAA", "geldi" | eski **zayıf**: oyun olayı, kahkaha yok |
| Eraycan 41:50 | klip-03 (87 mesaj) | seçilmedi | "gg", "GG", "1 milyon Kanka" | eski **sınırda/zayıf**: oyun sonu kutlaması |

Sonuç: oy seli (Kemalcan'ın iki "1/2" zirvesi) artık seçilmiyor; gerçek kahkaha dalgaları (Kemalcan 44:10, Eraycan 49:50) yakalanıyor. Kemalcan'da yeni 22:00 klibi eski yöntemin hiç göremediği, ama tartışmalı bir an. Eskiden seçilen oyun-olayı kalabalıkları ("geldi", "gg") elendi.

**Sınırı gösteren sayılar:** `min_farkli_kullanici` 25 yüzünden Kemalcan'da 17–24 kişilik altı küçük zirve elendi (35:50, 41:30, 43:00, 48:00, 1:43:00, 2:09:20…). Bunların içeriğine tek tek bakılmadı; bu eşik gerçek kahkaha anlarını da kesebilir.

## Emote sınıfları (Kick, gerçek sohbetten)

İki yayının kayıtlı sohbetinden en sık emote adları sayıldı; sınıf listeleri bunlara göre yazıldı (parça eşleşmesi: küçük harfli ad, `collectibles` öneki atılır, ad listedeki parçayı içeriyorsa sınıf o; sıra gülme > şaşkınlık > gürültü; listede olmayan **nötr** kalır).

| Sınıf | Sık görülen gerçek adlar (adet, iki yayın) | Listedeki parçalar |
|---|---|---|
| gülme | KEKW 1918, collectiblesGoldenKEKW 524, collectibleswideKEKW 135, LULW 51, collectiblesICANT 40, collectiblesKEKL 30, collectiblesPepeLaugh 22, KEKLEO 20, emojiLol 19 | `emote_gulme`: kek, lul, icant, pepelaugh, lmao, emojilol, haha, hehe, giggle, rofl |
| şaşkınlık | OOOO 53, PogU 12 | `emote_saskin`: pog, coggers, noway, oooo, aaaa, sheesh, ayooo, caught, astonished, omg, monkaomega |
| gürültü (dans/alkış yağmuru) | beeBobble 635, catblobDance 334, DanceDance 220, HYPERCLAP 169, vibePls 134 | `emote_gurultu`: dance, dans, clap, jam, vibe, disco, dj, edmusic, bobble, twerk, headbang, boogie, shake, hopp, gachigasm |

Not: `asmonSmash` (278) hiçbir listede yok, nötr kalır. `HYPERCLAP` alkış olduğu için gürültü sınıfında; tek başına yağmur olduğunda dilim elenir, kahkaha ile karışıksa (Eraycan 13:30) kahkaha emote'ları sayıyı taşır. Yeni yayıncıda ilk iş `sohbet/*.json` içinden en sık emote adlarına bakıp listeleri genişletmektir.

## Oyun süzgeci

`oyunlar` listesi boşsa bütün yayınlar işlenir. Doluysa yalnız kategorisi (ya da `oyun_baslikta_ara: true` iken başlığı) listedeki adlardan biriyle eşleşen yayın işlenir; uymayanlar `tara`'da `suzgece_uymayan` altında nedeniyle yazılır, `analiz`/`kes` reddeder (`--suzgecsiz` ile atlanır). Eşleşme harf ve Türkçe karakter duyarsızdır (`İ/ı`, `ş`…), kelime bütünüdür: `GTA V` listede ise "GTA VI"yı **eşleştirmez**, tersi de öyle; "GTA 6", "Grand Theft Auto VI" için ayrı yazılır.

```json
"oyunlar": ["Grand Theft Auto VI", "GTA 6", "GTA VI"]
```

**Kick sınırı:** Kick her yayın kaydı (VOD) için yalnız **tek bir kategori listesi** verir; yayın sırasında kategorinin ne zaman değiştiğini vermez. Yani bir yayın 2 saat GTA VI + 3 saat başka oyun ise süzgeç tüm yayını geçirir (kategori listesinde GTA VI varsa) ve klibin tam o anda GTA VI olup olmadığı bilinemez. Bu yüzden süzgeç yayın düzeyinde çalışır, klip düzeyinde değil.

## Ayarlar (`otomasyon/klip-yayincilar.json`)

`ayar` bölümü hepsi için varsayılandır; bir yayıncı kaydına `"ayar": {...}` eklenirse yalnız onun için geçer. Yayıncı eklemek: `yayincilar` listesine `{"ad": "...", "platform": "kick", "kanal": "<kick adı>", "etkin": true}` satırı. Sıra: kod varsayılanı ← dosya `ayar` ← yayıncı `ayar` ← komut satırı.

| Ayar | Varsayılan | Anlamı |
|---|---|---|
| dilim_sn | 10 | sayım dilimi |
| esik_k / min_mesaj / min_oran | 2.5 / 20 / 2.0 | zirve eşiği |
| onceden_sn / kuyruk_sn | 20 / 12 | zirveden önce / sonra |
| klip_min_sn / klip_azami_sn | 30 / 55 | klip süresi |
| birlestir_sn | 30 | yakın zirveleri birleştirme |
| azami_klip | 3 | yayın başına klip |
| bas_dislama_sn / son_dislama_sn | 300 / 180 | yayın başı / sonu |
| son_gun | 7 | `tara` kaç gün geriye baksın |
| duzen | kadraj | `kadraj` (yayın büyür, yazılar dışında) ya da `serit` (eski tam genişlik şerit) |
| kadraj_oran | 1.2 | kadraj en/boy oranı: 1.0 kare … 1.78 kırpma yok (1.0–1.78 arasına sıkıştırılır) |
| oyunlar / oyun_baslikta_ara | [] / true | oyun süzgeci; boş = hepsi |
| min_farkli_kullanici | 25 | zirvede en az bu kadar farklı kişi yazmış olmalı |
| min_emote_disi_oran | 0.25 | zirve mesajlarının en az bu oranı emote dışında bir şey içermeli |
| yontem | sinyal | `sinyal` (kahkaha/konu) ya da `yogunluk` (eski, yalnız mesaj sayısı) |
| klip_baslangic | dalga | `dalga`: kahkaha dalgasının başladığı dilim − `onceden_sn`; `tepe`: en yüksek dilim − `onceden_sn` |
| dalga_geri_oran / dalga_geri_azami_dilim | 0.4 / 3 | dalga başı için geriye yürürken sinyalin eşiğe oranı / en çok kaç dilim |
| gulme_min_kisi / gulme_esik_k / gulme_min_oran | 6 / 2.0 / 0.15 | kahkaha adaylığı: gülen kişi alt sınırı, ortalama + k·std, gülen mesaj oranı |
| gulme_tam_kisi / gulme_tam_oran | 15 / 0.30 | G bileşeninin tam puan verdiği kişi sayısı / oran |
| saskin_agirlik | 0.5 | şaşkın emote yazan kişinin gülen kişiye göre ağırlığı |
| konu_min_kisi / konu_min_lift / konu_tam_kisi | 6 / 10 / 12 | ortak konu: en az farklı kişi, yayının kalanına göre sıklık katı, tam puan kişisi |
| yayilma_min_kisi / _min_uzunluk / _min_kelime / yayilma_konu_agirlik | 6 / 12 / 3 / 0.5 | kopyala-yapıştır seli tanımı ve konu bileşenindeki ağırlığı (kahkaha ve yoğunluğa girmez) |
| max_gurultu_oran / min_sinyal_mesaj | 0.5 / 10 | oy/komut/emote-yağmuru oranı bundan yüksekse `oy_seli` elemesi / dilimde en az gürültüsüz mesaj |
| agirlik_gulme / agirlik_konu / agirlik_yogunluk | 0.5 / 0.3 / 0.2 | toplam puan ağırlıkları |
| yogunluk_tam_z | 6.0 | Y bileşeninin tam puan verdiği z |
| emote_gulme / emote_saskin / emote_gurultu | listeler | emote sınıf parçaları (yukarıdaki bölüm) |
| gulme_kelimeleri / gulme_emojileri / gulme_istisna | listeler | ek kahkaha kelimeleri / emojileri / kahkaha sayılmayacak kelimeler ("kafkas") |
| oy_kelimeleri | liste | oy sayılan kısa cevaplar ("evet", "hayır", "katıl"…) |

## Dosyalar (hepsi depo dışında)

Taban klasör: Windows `C:\Cihan.Ai\.scratch\yayin-klip\`, Linux `~/.local/share/yayin-klip/`; `YAYIN_KLIP_DIZIN` ortam değişkeni veya `--dizin` ile değişir.

- `durum.json`: işlenmiş yayınlar (`kes` bitince `islendi`). `tara` bunları atlar.
- `sohbet/`: indirilen sohbet (yarım kalırsa `.part.jsonl`'den devam eder). Önbellek sürüm 2: her mesajla gönderen kimliği de saklanır (farklı kişi sayısı için). Gönderensiz eski (sürüm 1) önbellek geçersizdir, yeniden indirilir.
- `analiz/`: zirve JSON'u. `cikti/<yayinci>-<tarih>-<kısa id>/klip-NN.mp4` + `klip-NN.json` (yayıncı, platform, VOD ve zaman damgalı bağlantı, oyun, puan, önerilen başlık ve açıklama; açıklama yayıncıyı anar ve kanalına bağlanır; `yayinlandi: false`).

Başlık ve açıklama sabit şablonlardan gelir (model çağrısı yok).

## Platform durumu

| Platform | Sohbet | Video | Durum |
|---|---|---|---|
| Kick | evet (`/api/v2/channels/<id>/messages`) | evet (HLS, ffmpeg) | çalışıyor; giriş/anahtar istemiyor |
| Twitch | — | — | desteklenmiyor: listedeki yayıncıların kayıtlı yayını (VOD) yok (2026-11-17) |
| YouTube | — | — | desteklenmiyor: yazılmadı/denenmedi (yt-dlp `live_chat` ile eklenebilir) |

Desteklenmeyen platformdaki yayıncı `tara`'da `desteksiz` altında nedeniyle raporlanır, diğerleri sürer.

Kick sohbet sınırları: pencere başına 25 mesaj (araç kalanı devam sorgusuyla alır), saniye çözünürlüğü, hız sınırı (429). Araç istekleri ortak bir hız sınırıyla gönderir (`KLIP_ISTEK_ARALIK`, varsayılan 0.4 sn; 4 paralel + sınırsız hızda Kick 429 verdi; 429 gelirse bekleyip tekrar dener). Ölçüm: 139 dk'lık yayın (1583 pencere) ~12 dk; 6 saatlik yayın ~4300 pencere ≈ 30–40 dk. 403 gelirse araç "desteklenmiyor: bot koruması" der.

**Linux sunucu denemesi (2026-11-17, `cio-sunucu`, Ubuntu ARM, veri merkezi IP'si):** Kick kanal/yayın listesi, tek VOD ve sohbet (`/messages`) uçları HTTP 200 döndü, bot koruması görülmedi; gerçek HLS ana liste adresi de 200 verdi. Sunucuda Python 3.12.3 var, **ffmpeg ve yt-dlp yok**: `tara`/`analiz` (yalnız Python + ağ) sunucuda çalışır, `kes` için `apt install ffmpeg fonts-dejavu-core` gerekir. Deneme geçici dosyalarla yapıldı, hiçbir şey kurulmadı/bırakılmadı. Sunucuya yerleştirme henüz yapılmadı.

## ffmpeg, yt-dlp, yazı tipi

- **ffmpeg** aranma sırası: `FFMPEG` ortam değişkeni → PATH'teki `ffmpeg` (drawtext ve gblur süzgeçleri varsa) → `imageio-ffmpeg` paketinin ffmpeg'i. Kurulum (kullanıcı düzeyi): `py -m pip install --user imageio-ffmpeg`; Linux'ta `apt install ffmpeg` (libfreetype'lı). Remotion'un kırpılmış ffmpeg'i kullanılmaz.
- **yt-dlp** Kick için gerekmez (ffmpeg HLS'i doğrudan okur). Yalnız ileride YouTube eklenirse lazım (`py -m pip install --user yt-dlp`).
- **ffprobe** yok; klip doğrulaması `ffmpeg -i` çıktısından yapılır (1080x1920, ≤60 sn, ses var; değilse klip reddedilir).
- **Yazı tipi:** `KLIP_FONT` → Windows `arialbd.ttf`/`segoeuib.ttf` → Linux DejaVuSans-Bold/LiberationSans-Bold/NotoSans-Bold (`apt install fonts-dejavu-core`).

## Bilinen belirsizlikler

- Kick VOD adresine `?t=<sn>` eklemek belgelenmemiş; paket JSON'unda `vod_zaman_damgali_url_dogrulandi: false`. Açıklamada güvenli olan "yayının M:SS noktası" yazısı kullanılır.
- Yayıncıların görüntüsünü yeniden paylaşmanın izin/telif durumu araçtan bağımsız bir karardır: yayınlamadan önce yayıncılardan izin alınması önerilir.
- Sohbeti olmayan/çok seyrek yayınlarda zirve çıkmaz (klip üretilmez).
- **Yalnız sohbetle sınırlı:** sinyaller sohbetin tepkisini ölçer, yayında olanı değil. Sohbet güldüğünde gülünç olan şey bazen yalnız iç şaka ya da bir izleyici didişmesidir (Kemalcan 22:00 "sınırda"); sohbetin sustuğu ama yayının çok güldüğü anlar kaçar. Sohbet tabanlı vurgu yakalama literatürü de ses+görüntüyle birleşik yönteme göre daha zayıf sonuç bildirir.
- **Veri azlığı:** eşikler ve emote listeleri iki yayına (biri Just Chatting, biri oyun) bakılarak seçildi. Üçüncü bir yayıncıda yeniden bakılmalı; özellikle farklı dilli ya da farklı emote kültürlü sohbetlerde.
- **Kopyala-yapıştır seli ağırlığı** (`yayilma_konu_agirlik` 0.5) veriyle desteklenmiyor: Kemalcan'da ≥4 kişilik yayılma yok, Eraycan'da en çok 6–8 kişilik. Sel zaten kahkaha ve yoğunluktan sayılmıyor; konuya yarım kredi verilmesi tahmindir.
- **`min_farkli_kullanici` 25**, 17–24 kişilik sınırda kahkaha anlarını eler (Kemalcan'da 6 zirve). Küçük sohbetli yayıncıda yayıncı bazında düşürülmeli (`ayar` içinde).
- **Oyun olayı konuları:** "geldi", "gg" gibi oyun olayı kalabalıkları kahkaha taşımadığı için artık seçilmiyor, ama yayılma eşiğinin altında kalan ortak kelime ("yarısı") yine konu olarak sayılabilir (Eraycan 31:50, "sınırda").
- **Kaçırılan kahkaha biçimleri:** uzatılmış/yazım hatalı olanlar ("KERKW") listelerde yoksa sayılmaz; uzun harf koşuları tek harfe indirilir.
- **Başlangıç kuralı:** kahkaha dalgası ilk eşik diliminin ≤3 dilim (30 sn) gerisine kadar izlenir; olay çok daha önceyse klip olayı kaçırabilir, "20 sn önce" iki yayında yeterli göründü ama kanıtlanmış değil.
- **Puan ölçeği:** puanlar (0–100) yayınlar arası kıyaslanamaz; yalnız aynı yayının klipleri sıralanır.

## Ses (yük) ölçümü: değerlendirme (2026-11-17, koda eklenmedi)

Soru: sesin yükselmesi ikinci bir sinyal olarak kullanılabilir mi? Gerçek ölçüm (Kemalcan yayını, HLS'ten `ffmpeg -ss <sn> -i <hls> -t 60 -vn -af ebur128=peak=true -f null -`, ek paket gerekmedi):

| Pencere | LUFS (I) | Dalgalanma (LRA) | Süre |
|---|---|---|---|
| 22:00 (yeni klip-01 anı), 1080p60 akış, 60 sn | −20.7 | 9.3 LU | 1.2 sn |
| 50:00 (zirve olmayan an), aynı | −18.4 | 12.4 LU | 1.3 sn |
| 20:00'den 10 dk, 160p akış | −19.9 | – | 2.5 sn |

- **Maliyet:** HLS ana listesinde yalnız-ses akışı yok (çeşitler 1080p60 … 160p, hepsi görüntülü); ses için en ucuz çeşit 160p (≈230 kbit/sn). 10 dk = 2.5 sn ⇒ 139 dk'lık yayın ≈ 35 sn, indirme ≈ 240 MB (hesap: bant genişliği × süre). 1080p60 akışta 60 sn = 1.2 sn, bütün yayın ≈ 3 dk ama ≈ 3.5 GB.
- **Yapılabilir ve ucuz.** Önerilen biçim: 160p akıştan `ebur128` ile 10 sn'lik kısa dönem yüksekliği → yayının kendi dağılımına göre z puanı → dördüncü sinyal ("ses sıçraması"), özellikle sohbet sessiz yayıncılar için yedek.
- **Henüz kanıt yok:** iki pencerelik ölçümde kahkaha anı zirve olmayan andan *daha yüksek değildi* (−20.7 vs −18.4 LUFS); bu tek örnek bir şey ispatlamaz, ama sesin tek başına güvenilir olmadığına işaret eder (konuşma düzeyi ve oyun müziği baskın olabilir). Koda eklemeden önce en az 10 işaretli klip anıyla (ses z puanı ↔ insan değerlendirmesi) denenmeli.
