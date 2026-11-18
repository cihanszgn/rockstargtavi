# Yayın klip hattı

Biten bir Kick yayınının (ya da `canli` komutuyla **süren** yayının) sohbetinden ve isteğe bağlı konuşma dökümünden, ayrıca aynı yayıncıların **YouTube** videolarının konuşmasından (altyazı/Whisper + Sonnet yargısı) 9:16 dikey klip paketi üretir. **Yayın yapmaz**: sosyal kuyruğa kayıt eklemez, hiçbir yere yüklemez. Çıktıyı (mp4 + json) sen incelersin.

Araç: `tools/yayin_klip.py` (YouTube bölümü `tools/klip_youtube.py`, konuşma katmanı `tools/klip_konusma.py`) · yayıncı listesi: `otomasyon/klip-yayincilar.json` · testler: `py -m unittest discover -s tests -p "test_*klip*.py"`

## Komutlar

```
py tools/yayin_klip.py tara                      # son 7 günün biten yayınları, işlenmişler atlanır
py tools/yayin_klip.py tara --yayinci jahrein --hepsi
py tools/yayin_klip.py analiz kick:<uuid>        # sohbeti indir, zirveleri bul (JSON yazdırır)
py tools/yayin_klip.py kes kick:<uuid>           # analiz + klipleri kes + paketle
py tools/yayin_klip.py otomatik --en-cok 3       # tara + kes (yeni yayınların ilk 3'ü)
py tools/yayin_klip.py canli                     # SÜREN yayınlarda tek tur: yeni biten kahkaha/konu anlarını keser
py tools/yayin_klip.py canli --kanal wtcn --kuru # yalnız sohbeti indir + analiz et, kesme (deneme)
py tools/yayin_klip.py kes youtube:<11 karakterlik id>   # YouTube videosu (adres de olur: youtu.be/…, youtube.com/watch?v=…); aşağıda "YouTube kaynağı"
py tools/yayin_klip.py aciklama-doldur [--klasor DIR] [--kuru]   # kisa_aciklamasi olmayan konuşma paketlerine TEK toplu model çağrısıyla açıklama yaz (dökümsüz pakete dokunmaz)
py tools/yayin_klip.py yeniden-uret PAKET.json... [--yedek DIR] [--aciklamasiz]   # paketin dikey mp4'ünü bugünkü düzenle yeniden üret (eski mp4 önce yedeğe kopyalanır)
```

`tara` Kick yayınlarını ve ayrıca listedeki beş yayıncının etkin YouTube kanallarının (`videos` + `streams` sekmeleri) son `son_gun` günlük videolarını bulur.

`canli` **tek seferlik** çalışır (kalıcı servis değildir); yayın sürerken 5–10 dk'da bir çağrılması yeterli (aşağıda "Yayın sürerken klip"). Tampon/kayıt gerekmez.

`<vod>` olarak `kick:<uuid>`, çıplak uuid veya `https://kick.com/<kanal>/videos/<uuid>` verilir. `analiz` ve `kes` için `--esik-k`, `--min-mesaj`, `--min-oran`, `--azami-klip`, `--bas-dislama-sn`, `--min-farkli-kullanici`, `--min-emote-disi-oran`, `--duzen kadraj|serit`, `--kadraj-oran`, `--yontem sinyal|yogunluk`, `--klip-baslangic dalga|tepe`, `--gulme-esik-k`, `--konu-min-kisi`, `--konu-min-lift`, `--max-gurultu-oran` ile o çalıştırmaya özel ayar verilir; `--yeniden` analizi önbellekten almaz, `--zorla` var olan klibi yeniden üretir, `--suzgecsiz` oyun süzgecine uymayan yayını da işler.

## Nasıl çalışır

Varsayılan yöntem **sinyal** (`yontem: sinyal`, 2026-11-17). Hedef: "sohbet kalabalık" değil "sohbet güldü / aynı konuda toplandı" anını bulmak. Bu bölüm konuşmasız yöntemi anlatır: model çağrısı yok, yalnız standart kütüphane; bütün listeler ve eşikler `klip-yayincilar.json` içindedir.

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
6. **Konuşmasız başlık/açıklama** sabit şablon ama baskın sinyale göre seçilir: `gulme` → sohbetin güldüğünü söyleyen ölçülü şablonlar; `konu` ve terim varsa → o terimli konu şablonu; baskın sinyal yoksa (eski yöntem) eski şablonlar. Paket JSON'una `baskin_sinyal`, `puan_bilesenleri` (G/K/Y puanı, kişi sayıları, gürültü dökümü), `dalga_basi_sn` yazılır.

### Eski yöntem (`yontem: yogunluk`)

Eşik = en büyük( ortalama + `esik_k`·std, `min_mesaj`, `min_oran`·ortalama ); eşiği geçen dilimler `birlestir_sn` (30) içinde tek klipte birleşir; klip ilk zirve diliminden 20 sn önce başlar; zayıf zirve elemesi (25 kişi / 0.25 emote dışı) aynıdır; puan = (zirve − ortalama)/std. Sorun: mesaj *sayısı* "1/2" oylarını da zirve sayar. Birim testlerin çoğu bu yöntemle çalışır (`AYAR`'da `yontem: yogunluk`).

### Klip üretimi (iki yöntemde de aynı)

- `kes` yalnız klip aralığını HLS'ten çeker (tüm yayını indirmez), 1080x1920 H.264+AAC yapar. Üç düzen var (`duzen` ayarı):
   - **kamera** (varsayılan, 2026-11-18): kesimden önce, klip başına bir kez, 8-12 kare örneklenir (`kamera_kare_sayisi` 10) ve OpenCV `FaceDetectorYN` + YuNet modeliyle (`otomasyon/modeller/face_detection_yunet_2023mar.onnx`; kaynak OpenCV Zoo `models/face_detection_yunet`, MIT, lisans `YUNET-LICENSE.txt`; sha256 8f2383e4…2fa4) yüzler bulunur. Kamera = karelerin çoğunda (`kamera_min_kare_orani` 0.5) aynı yerde duran yüz. Karar (`tools/klip_kamera.py`):
     - Köşede/kenar bandında (`kamera_kenar_bandi` 0.25) tek kararlı yüz, kamera kutusu alanı en çok `kamera_en_cok_alan` 0.3: **iki panel**. Pencere kenarı Sobel profiliyle aranır, yüz genişliği x `kamera_kutu_katsayi` 7.0 (en/boy `kamera_kutu_oran` 1.4) kutusuyla birleştirilir, kenara 0.05 içindeyse kenara yaslanır. Eleme sırası: (1) kesin sabit simge: yüz yaması std < `kamera_sabit_yuz_std` 2.0 (karar `sabit_simge`); (2) göreli: birden çok kararlı yüz varsa std'si en hareketlinin `kamera_sabit_goreli` 0.5 katından az olanlar (sabit avatar) elenir; tek kararlı yüzde eleme yok (sakin kamera std 10-14 olabilir; eski 14 eşiği gerçek kameraları yanlış eliyordu); (3) HUD: en büyük kararlı kümenin alanının `kamera_kucuk_kume_orani` 0.6 katından küçük kümeler yok sayılır. Izgara (Kemalcan) ve Tolunay klip-03 `cok_yuz` kalır; Kemalcan konusma-hizali-03'te en küçük yüz oranı 0.63 (eşiğe yakın), Eraycan konusma-01'de 0.49.
     - Kamera büyük, kutu alanı eşiği aşıyor, yüz ortada, birden çok kararlı yüz (grid), yüz yok ya da tespit kararsız/çelişkili: **tek panel** (eski kadraj). Tek büyük yüzde kırpma merkezi yüze kayar (yüz kesilmesin). Her hata güvenli tarafa (kadraj) düşer; neden pakette `kamera_plani.neden`.
     - Panel sırası: üstte içerik (oyun), altta kamera. Gerekçe: içerik yazının/oyunun bağlamıdır ve izleyicinin gözü ilk oraya düşer; kamera (yüz, tepki) altta durunca üstteki açıklama etiketine yakın okunur, alttaki 250 px (platform arayüzü) boş kalır. Ölçüler: içerik 590 + boşluk 10 + kamera 420 px, blok 430..1450.
     - İçerik paneli kamerayı dışarıda bırakacak biçimde kırpılır; panel oranını doldurmak kamerayı kesmeden mümkün değilse en az kesilir (`kamera_icerik_en_az_alan` 0.4, `kamera_icerik_pay` 1.12).
     - Elle ezme: yayıncı kaydına `"kamera_kutu": [x, y, w, h]` (0-1 oransal) tespiti ezer. Tüm eşikler `ayar` içinde `kamera_*` anahtarlarıyla değiştirilir; kesim aşaması ayarı olduklarından analiz önbelleğini bozmaz. Paket JSON'unda `kamera_plani` (seçilen düzen, kutu, neden) yazılır; `kamera_surumu` düzen imzasındadır.
     - **Sahne değişimi (yapılmadı, bilerek):** klip içinde düzen değişirse (örn. Jahrein klip-01 başı: ~0.4-0.6 sn tam ekran kamera, sonra oyun + köşe kamera) tüm klip için tek karar verilir; kareler tek plana göre kesilir. Dilimli (zaman aralıklı) düzen ffmpeg'de her aralık için ayrı tam filtre grafiği ve `overlay enable=between(t,..)` ister; saniyeden kısa geçişlerde kazanç küçük, hata riski ve test yükü büyük. Ölçülen: Jahrein klip-01'de tam ekran sahne 1 sn'den kısa. Gerekirse klip başlangıcı sahne geçişinden sonraya kaydırılır. Bilinen zayıflıklar: yüz görünmeyen/kameranın kapalı olduğu karelerde tek panele düşer; kamera yüzü sürekli hareket ederse (kararsız) tek panel; pencere kenarı tahmini tam isabetli değildir (oransal kutuyla birleştirilir, kenar bandı kesilebilir); çizgi film/maskeli avatar yüz sayılmayabilir (elle `kamera_kutu`).
   - **kadraj**: yayın ortadan kırpılır (`kadraj_oran` 1.2 ⇒ 1080x900 görüntü; 1.0 kare, 4/3 ⇒ 1080x810, 1.78 ⇒ kırpma yok) ve tam genişlikte, orta çizgisi y=880'de durur. Arkada bulanık kopya; yazılar görüntünün **dışında**: üstte yayıncı adı + oyun, altta "Kaynak: kick.com/<kanal>" ve marka; hiçbiri görüntünün üstüne binmez (testle güvenceli, yazı yeri görüntü yüksekliğine göre hesaplanır).
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

## Yayın sürerken klip (`canli`, 2026-11-17)

**Ölçüm (2026-11-17, wtcN ve Kemalcan canlı yayınları): yayın sürerken görüntü alınabiliyor → yol A. Yol B (kayıt/dönen tampon) gereksiz, yazılmadı.**

- Kick `/v2/channels/<kanal>/videos` listesinin ilk kaydı süren yayındır (`is_live`, `duration` 0, `source` dolu).
- `source` HLS adresi çalışır: ana liste → çeşit listesi, her güncellemede `#EXT-X-PLAYLIST-TYPE:EVENT` ve `#EXT-X-ENDLIST` birlikte gelir (yani liste "bitmiş" gibi görünür ama her yenilemede uzar), her bölümde `PROGRAM-DATE-TIME` var, görüntü gerçek saatin ≈20 sn gerisinde. ffmpeg süren listeden `-ss <sn> -t <süre>` ile klibi doğrudan keser; kesilen bölüm bittiyse bir daha değişmez.
- Sohbet `/v2/channels/<kanal_id>/messages?start_time=` canlıda da derin geçmişi veriyor (yayın başından itibaren alındı; `video_sn` 7930 anında 0–2560. sn'ler çekildi).
- Sohbet–video hiza kayması canlı ölçüldü: `hiz_kaymasi_sn` = 0.5–0.98 sn (liste içinde ilk ve son `PROGRAM-DATE-TIME` farkından ölçülür; tur raporunda yazar).
- *Yönetici notundaki "`source` ile 0 parça" bulgusu doğrulanamadı:* iki ayrı yayıncının süren yayınında `source` doğru parça listesi verdi.

**Tur akışı** (`canli_komutu`): canlı yayıncıları bul → `canli_min_sure_sn` (1200 sn) dolmayanı atla → sohbeti yayın başından "şimdi − `canli_sohbet_marj_sn` (20 sn)"ye kadar indir (`sohbet/kick-<uuid>.part.jsonl`'e yazar, sonraki tur kaldığı yerden sürer; tur başına `canli_sohbet_butce_sn` 240 sn indirme bütçesi, yetmezse "sohbet henüz yetişmedi" der ve sonraki turda sürer) → mevcut sinyal yöntemiyle zirveleri bul (`son_dislama_sn` canlıda 0; daha önce kesilmiş aralıklar `engelli` olarak o ana yeniden zirve seçilmesini engeller) → yalnız **kapanmış** dalgaları kes.

- **Kapalı-dalga kuralı:** klip ancak `kapanis = max(dalga_sonu + birlestir_sn (30), klip_bitis_sn) + canli_bekle_sn (20)` videonun uzunluğuna (`video_sn`) varınca kesilir. Yani kahkaha dalgası bitti ve aynı dalganın devamı (30 sn kümeleme penceresi) gelmedi, klibin bitişi videoda var ve üstüne 20 sn pay var ⇒ **yarım klip çıkmaz**. Dalga sürüyorsa tur "açık zirve" diye sayıp bırakır, sonraki tur keser (testli: dalga 3000'de, klip [2980, 3022], 3040'ta kesilmez, 3100'de kesilir).
- **Aynı an iki kez kesilmez:** kesilen klip `durum.json`'da `vod[kick:<uuid>].canli_klipler`'e **gerçek saat (epoch) aralığıyla** yazılır (yayın başı saati tur arası küçük oynasa da dayanır). Sonraki turlar o aralıkla örtüşen adayı atlar (kenar değme örtüşme sayılmaz). Aynı anda iki tur çalışmasın diye `canli.kilit` (O_EXCL; 3 saatten eskisi çökmüş sayılır).
- **Yayın bitince `tara`/`kes`:** canlıda kesilen aralıkla örtüşen klip "yayın sürerken zaten kesilmiş (canli-*.mp4), atlandı" diye **atlanır**, kalanlar normal kesilir; `canli_klipler` kaydı "islendi" durumunda silinmez. Sohbet önbelleği (`.part.jsonl`) final analizde yeniden kullanılır (17.11 wtcN yayınında canlıdayken indirilen ilk ≈2560 sn tekrar indirilmedi). Final seçim normal `azami_klip` ile yapılır, sonra canlıda kesilenler atlanır; yani canlıda kesilen bir an finalin en iyi 3'ünde olsa bile yerine sıradaki gelmez (en iyi 3'ün 1'i canlı kesilirse bitişte 2 yeni klip çıkar).
- **Çıktı:** `cikti/<yayinci>-<tarih>-<uuid8>/canli-NN.mp4` + `.json` (paket `canli_kesim: true`, `yayinlandi: false`). Final `klip-NN` dosyalarıyla karışmaz. Tur raporu (JSON, stdout) her yayıncı için `durum`, `video_sn`, `sohbet_hazir_sn`, `hiz_kaymasi_sn`, `acik_zirve`, klip listesini verir.
- `canli_min_puan` 0 (alt sınır yok): puanlar yayınlar arası kıyaslanamadığı için sabit bir eşik şimdilik veriyle desteklenmiyor. Gözlem: wtcN 17.11 yayınında seçilen anlar 81–83, yayının en iyi 14 anı 65–83; Kemalcan'ın ilk 20 dk'sında 22–55. Çok klip istemiyorsan `--azami-klip` / `canli_azami_klip` (yayın başına 6) ile sınırla; kalitesiz klip istemiyorsan `--min-puan 55` makul başlangıç (tahmin).

**Gerçek canlı deneme (Kemalcan, `kick:bf478c44…`, yayın sürerken):** `video_sn` 1385'te 4 klip kesildi (`canli-01..04.mp4`; hepsi 1080x1920, sesli, 42–55 sn). `canli-01` (zirve 5:30, puan 55.5, 22 kişi gülüyor): sohbetin gülme sayısı video 330–340. sn'de 14 ve 12 mesaja çıktı (öncesi 0–2), klip 310–352; klibin 20. sn'sindeki karede yayıncının ekranındaki sohbet bindirmesinde "…lan öptün" yazısı görülüyor ve aynı mesaj ("la niye alt dudumdan öptün") API sohbetinde video 327. sn'de ⇒ hiza ≈3 sn içinde doğrulandı. Kare: `C:\Cihan.Ai\.scratch\yayin-klip\kare\canli-01-orta.png`.

**wtcN 17.11 değerlendirmesi (kuaför/boya yayını, 7959 sn, 23 773 mesaj):** "saç/boya/pembe/mavi" konusu sohbette gerçekten patlıyor (0:48–2:00 arası sürekli; 30 sn'lik en yoğun dilimler 1:59:00, 1:13:30, 1:56:00, 1:25:00, 0:53:30; "saç" 295, "pembe" 276, "saçı" 114, "boya" 85 kez). Sistem konuyu görüyor (`konu` bileşeni: "saçı" 13 kişi @1:59:00) ama klip seçimi kahkaha ağırlıklı (0.5) olduğu için seçilen 3 an kahkaha dalgalarıdır: 1:17:20 (p82.6, "gerçek/3k sub sözü"), 1:33:10 (p81.3, "offf", "FERİDEMİN KUAFÖR GÜNLÜKLERİ DAY 1"), 1:44:10 (p82.2, "YAKIŞMIŞ/havuç olmuş/icardi gibi/saçın artmış", boyalı yeni saçın ilk görünüşü; kare: `wtcn-klip-03.png` turuncu saç). Klip 2 karesinde yayıncının başında folyo var (boya bekleme). Dürüst yargı: klip 3 iyi; klip 2 iyi/sınırda (komik kare + kuaför konusu, ama sohbet dalgasının sebebi "CHP'li teyze"); klip 1 sınırda (yalnız mesajlara bakıldı, kareye bakılmadı; "3k sub sözü" bağlamı klipte anlaşılmıyor olabilir). "Saçı yokki" konu zirvesi (1:59:00) yayının 14. anı (p64.8): konu bileşeni tam (1.0) ama gülme 0.57 ⇒ elendi. İstenirse konu ağırlığı artırılabilir; denenmedi.

**Maliyet (ölçüm/hesap, 2026-11-17):**
- *Disk:* sohbet önbelleği ≈0.2–0.45 KB/sn (Kemalcan 637 KB @1405 sn; wtcN 7959 sn → 1.3 MB). 2 saatlik yayın ≈1–3 MB. Klip mp4: 2.6–23.6 MB (42–55 sn; ölçüm, 4 klip ortalama 11.9 MB). Tampon yok (B yazılmadığı için ek disk yok).
- *Bant:* sohbet ≈10 sn sohbet/sn hızla iner (ilk tur: 2560 sn sohbet 240 sn bütçede); sonraki 5 dk'lık turlar ≈60 istek. Video: yalnız kesilen aralığı çeker (HLS 1080p60 ≈25 MB/dk akış hızı; 55 sn klip ≈23 MB indirme), tüm yayın indirilmez.
- *İstek hızı:* sohbet istekleri ortak `_hiz_siniri`ni kullanır (`KLIP_ISTEK_ARALIK` 0.4 sn), canlıda ayrı bir hız yoktur.

**Belirsizlikler:** (1) sohbet canlıda ≈20 sn ileride, video ≈20 sn geride; `canli_sohbet_marj_sn` bunu kapatır ama sohbetin gerçek yazılma gecikmesi ayrıca ölçülmedi (yalnız hiza kayması ölçüldü). (2) Süren yayının HLS listesi `ENDLIST` taşıyor; gerçek bir ağ kesintisi/yeniden başlama (yayıncı yayını kapatıp açarsa Kick yeni uuid veriyor, wtcN 17.11'de böyle oldu) yeni yayın sayılır; eski yayının canlı klipleri kendi uuid'sine bağlı kalır. (3) Kick uzun yayında listeyi kısaltırsa (yalnız son N bölüm tutma) `PROGRAM-DATE-TIME` t0'ı kayabilir: tur her seferinde yeniden ölçer, ama 8 saati aşan yayında denenmedi. (4) `canli` tek bir yayıncının iki eşzamanlı yayınını ayırt etmez (Kick kanalda tek canlı yayın tutuyor).

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
| duzen | kamera | `kamera` (kamera ayrı panel; bulunamazsa kadraj), `kadraj` (yayın büyür, yazılar dışında) ya da `serit` (eski tam genişlik şerit) |
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
| canli_min_sure_sn | 1200 | `canli`: bundan kısa süren yayın analiz edilmez |
| canli_azami_klip | 6 | `canli`: yayın başına canlı kesilecek en çok klip |
| canli_bekle_sn | 20 | `canli`: dalga kapanışı / klip bitişinden sonra güvenlik payı |
| canli_min_puan | 0.0 | `canli`: bu puanın altındaki zirve kesilmez |
| canli_sohbet_butce_sn | 240 | `canli`: tur başına sohbet indirme süre bütçesi |
| canli_sohbet_marj_sn | 20 | `canli`: sohbetin en yeni bu kadar sn'si indirilmez (yazılıyor olabilir) |
| konusma | false | konuşma katmanı; `--konusmasiz` ile tek çalıştırmalık kapatılır |
| konusma_model / konusma_kucuk_model | large-v3-turbo / small | tercih edilen ASR ve bellek/GPU hatasındaki yedek |
| konusma_cihaz | auto | `auto`, `cuda`, `cpu`; GPU yoksa küçük model CPU int8 |
| konusma_parca_sn / konusma_aday_parca_sn | 300 / 60 | tam döküm / aday için önbellek ızgarası; her iki yanda 15 sn bağlam |
| konusma_aday_sayisi / konusma_canli_aday_sayisi | 15 / 6 | bitmiş yayın / tek canlı turda değerlendirilecek aday sayısı |
| konusma_tam_tarama | true | bitmiş yayında ve GPU varken tam döküm taraması |
| konusma_pencere_sn / konusma_ortusme_sn | 1200 / 60 | modelin tam tarama penceresi ve örtüşmesi (2026-11-18: 240/45 idi; bkz. "Model çağrısı azaltma") |
| konusma_toplu | true | tek istekte birden çok pencere/aday yargılanır (`{"pencereler":[…]}`); false ise pencere başına bir çağrı |
| konusma_tarama_an | 8 | tarama penceresi başına en çok olay |
| konusma_cagri_butcesi | 15 | 2 saatlik (7200 sn) yayın başına model çağrısı tavanı; daha uzun yayında `ceil(süre/7200)` katı. Yeniden denemeler de sayılır, önbellek okuması sayılmaz. Aşılırsa "konuşma çağrı bütçesi doldu" hatası (kota değil): o istekteki pencereler yargısız kalır, yargısız aday tarama kapsıyorsa seçime girmez |
| youtube_min_sure_sn | 300 | bundan kısa YouTube videosu atlanır (`cok_kisa`) |
| youtube_liste_siniri | 50 | kanal sekmesinden bakılacak en yeni video sayısı |
| youtube_heatmap_agirlik / youtube_heatmap_min | 0.2 / 0.6 | YouTube "en çok izlenen" eğrisinin puana katkısı (0–1) ve yerel tepe eşiği; heatmap yalnız eski/çok izlenen videoda dolu |
| youtube_aday_whisper | true | altyazıdan bulunan adayların çevresi gerçek sınırlar ve ses hizası için Whisper ile yeniden dökülür |
| konusma_agirlik_sohbet / konusma_agirlik_icerik | 0.35 / 0.65 | birleşik 0–100 puan; konuşmanın 0–10 puanı önce 10 ile çarpılır |
| konusma_min_puan | 6.0 | bunun altındaki veya `anlasilir:false` yargılı aday elenir |
| konusma_azami_sn | 59 | cümle sınırlarıyla klip üst süresi; kod 59 sn'den yukarı çıkmaz |
| konusma_yargi_model | sonnet | mevcut haber model ayarındaki tercih edilen model adı |
| konusma_model_ayari | otomasyon/modeller.json | haber hattıyla ortak model taşıması/komutları |
| konusma_bulut | true | mevcut haber bulut modelinin seçilmesine izin ver; yeni servis/anahtar yok. `konusma:false` iken hiçbir çağrı yapılmaz |

## Dosyalar (hepsi depo dışında)

Taban klasör: Windows `C:\Cihan.Ai\.scratch\yayin-klip\`, Linux `~/.local/share/yayin-klip/`; `YAYIN_KLIP_DIZIN` ortam değişkeni veya `--dizin` ile değişir.

- `durum.json`: işlenmiş yayınlar (`kes` bitince `islendi`). `tara` bunları atlar.
- `canli.kilit`: aynı anda iki `canli` turu çalışmasın diye kilit (tur bitince silinir; çökerse 3 saat sonra yok sayılır). `durum.json` içinde `vod[...].canli_klipler`: canlıda kesilen aralıklar.
- `sohbet/`: indirilen sohbet (yarım kalırsa `.part.jsonl`'den devam eder; `canli` turları da buraya yazar, yayın bitince `tara`/`kes` aynı dosyadan sürer). Önbellek sürüm 2: her mesajla gönderen kimliği de saklanır (farklı kişi sayısı için). Gönderensiz eski (sürüm 1) önbellek geçersizdir, yeniden indirilir.
- `analiz/`: zirve JSON'u. `cikti/<yayinci>-<tarih>-<kısa id>/klip-NN.mp4` + `klip-NN.json` (yayıncı, platform, VOD ve zaman damgalı bağlantı, oyun, puan, önerilen başlık ve açıklama; açıklama yayıncıyı anar ve kanalına bağlanır; `yayinlandi: false`).

Konuşma yargısı geçerliyse başlık ve açıklama klipte anlatılan olaydan gelir; model yoksa eski şablonlar kullanılır. Paket JSON’unda konuşma puanı, gerekçesi, kaynakları ve klip aralığının döküm metni bulunur.

## Platform durumu

| Platform | Sohbet | Video | Durum |
|---|---|---|---|
| Kick | evet (`/api/v2/channels/<id>/messages`) | evet (HLS, ffmpeg) | çalışıyor; giriş/anahtar istemiyor |
| Twitch | — | — | desteklenmiyor: listedeki yayıncıların kayıtlı yayını (VOD) yok (2026-11-17) |
| YouTube | hayır (canlı sohbet tekrarı yazılmadı/denenmedi) | evet (yt-dlp aralık indirme, anahtarsız/çerezsiz) | **yalnız konuşma yöntemi**: altyazı/Whisper dökümü + Sonnet yargısı + heatmap; 3 gerçek videoda uçtan uca denendi (2026-11-18) |

Desteklenmeyen platformdaki yayıncı `tara`'da `desteksiz` altında nedeniyle raporlanır, diğerleri sürer.

## YouTube kaynağı (2026-11-18)

Kod: `tools/klip_youtube.py`; bütünleşme `yayin_klip.py` (`kes`, `analiz`, `tara`, `otomatik`). Yeni servis, anahtar, çerez veya hesap yoktur; yalnız `yt-dlp` (2026.10.26 denendi).

**Kanallar.** `klip-yayincilar.json` içinde her yayıncıda `youtube_kanallari: [{kanal_id, tanitici, etkin}]`. Etkin: Tolunay Ören `@TolunayOren`, wtcN `@wtcNFerit`, Jahrein `@jahreinboss`, Kemalcan Parlak `@KendineMüzisyenKM`, Eraycan `@erayozkenar`. Eski ikinci kanallar (`tolunayorentwitch`, `erayozkenaryt`) `etkin:false`. Paketteki "Kaynak: youtube.com/@<tanıtıcı>" yazısı buradan gelir.

**Akış.** `video_id` (adres/`youtube:<id>`) → tekil metadata → atlama süzgeci → konuşma yolu:
1. Döküm: otomatik altyazı (JSON3, `tr-orig`) varsa onunla **aday taraması**; yoksa bütün video Whisper'la (faster-whisper, 330 sn parça önbelleği) dökülür. Altyazı kelime sınırı için yeterince kesin değildir: seçilen adayların çevresi (±25 sn) ayrıca Whisper'la dökülüp yeniden yargılanır; kesim sınırı ve ses referansı bu gerçek dökümden gelir.
2. Tarama: 1200 sn pencereler (60 sn örtüşme), toplu yargı. Heatmap'te yerel tepe (`youtube_heatmap_min`) varsa çevresindeki ±45 sn de bağımsız aday olur (içerik yargısı yine zorunlu); heatmap yalnız puana `youtube_heatmap_agirlik` kadar katkı verir.
3. Kesim: tam cümle sınırı (30–55 sn, en çok 59), yalnız o aralık (+6 sn pay) `download_ranges` ile 1080p indirilir (tüm video inmez), kadraj düzeni, ses hizası doğrulaması, 1080x1920 h264+aac ≤60 sn. İndirme/ffmpeg çökmesinde bir kez yeniden denenir; bot/403'te `player_client=android,ios,tv` yedeği, üyelik/özel/erişilemez videoda yeniden deneme yok. Denenen 3 videonun hepsi normal istemciyle 1080p indi; indirilen yükseklik `video.youtube_indirme.yukseklik` alanında yazar.
4. Konuşma katmanı YouTube'da **zorunludur** (sohbet yok): `konusma:false` verilirse "YouTube sohbet içermez" hatası çıkar. Kick'te varsayılan yine kapalıdır.

**Atlananlar (`tara` → `youtube_atlanan`, kanal başına sayı ve nedenler `youtube_kanallar`).** `shorts`, `uyelere_ozel_veya_ozel`/`uyelere_ozel`, `canli_veya_islenmemis` (canlı/yaklaşan), `sure_bilinmiyor`, `cok_kisa` (<300 sn), `eski` (son 7 günden eski; liste girdisi 14 günden de eskiyse tekil metadata istenmeden `eski_yaklasik_tarih`), `tarih_bilinmiyor` (yeni olduğu varsayılmaz), `bilgi_hatasi`, `oyun_suzgeci`, `islenmis`.

**Paket JSON'u.** Kick alanları korunur; `platform:"youtube"`, `vod_id` = video kimliği, `vod_url`, `vod_zaman_damgali_url` = `https://youtu.be/<id>?t=<sn>` (`..._dogrulandi:true`), `kanal`, `kanal_url`, `yayin_basligi`, `aday_kaynaklari` (`altyazi_tarama` / `whisper_tarama` / `heatmap`), `video.youtube_indirme` (istemci, yükseklik, indirilen aralık).

**Kick + YouTube çift kaynak.** Aynı yayıncının aynı yayını iki platformda olabilir; aynı an iki kez kesilmesin diye: (a) `ayni_yayin` kimlik kesin değilse tarih (≤2 gün), süre (±%3, ≥90 dk) ve başlık benzerliğiyle `muhtemel_ayni_yayin_inceleme` der ve YouTube analizi **kesmeden** durur (`inceleme` listesi); (b) üretilen klibin dökümü başka platformdaki mevcut paketin dökümüyle ≥%80 benzerse (≥15 kelime) `cift_kaynak_dokum_eslesmesi` ile elenir. **Gerçek bir Kick+YouTube çiftiyle denenmedi** (66 çiftin metadatasında hepsi `belirsiz`; aşağıda bilinen belirsizlikler).

**Gerçek denemeler (2026-11-18).**

| Video | Süre | Altyazı | Heatmap | Klip | Whisper/Sonnet çağrı |
|---|---|---|---|---|---|
| `L7QH0sUtHJ0` Tolunay Ören (kurgulu) | 26 dk | tr-orig | dolu (1 tepe) | 3 (31.8, 49.0, 32.6 sn) | 682 satır altyazı, 4 çağrı |
| `r8v8zcyIYf4` Jahrein (CoD) | 30 dk | tr-orig | boş | 1 (34.0 sn) | 3 çağrı |
| `TE7Q0eKsIaY` Eraycan (final bölümü, kurgulu) | 3 sa 46 dk | tr-orig | boş | 2 (45.6, 37.5 sn) | 13 Sonnet çağrısı (12 tarama + 1 doğrulama; tavan 45; 12'si ffmpeg çökmesiyle biten ilk koşudan yargı önbelleğinden geldi, son koşu 1 yeni çağrı gösterir), 16 Whisper parçası (yalnız aday çevresi) |

Hepsi 1080x1920, h264+aac, ses hizası korelasyonu ≥0.97, 1080p indi. Klip başına değerlendirme, döküm alıntıları ve kare yolları: `C:\Cihan.Ai\.scratch\yayin-klip\youtube-rapor.md`. `tara` beş kanalda çalıştı (3 dk 19 sn): bulunan Tolunay 0 (üyelere özel 6, eski 70), wtcN 0 (eski 50), Jahrein 2, Kemalcan 0, Eraycan 10; atlanan toplam 264.

Kick sohbet sınırları: pencere başına 25 mesaj (araç kalanı devam sorgusuyla alır), saniye çözünürlüğü, hız sınırı (429). Araç istekleri ortak bir hız sınırıyla gönderir (`KLIP_ISTEK_ARALIK`, varsayılan 0.4 sn; 4 paralel + sınırsız hızda Kick 429 verdi; 429 gelirse bekleyip tekrar dener). Ölçüm: 139 dk'lık yayın (1583 pencere) ~12 dk; 6 saatlik yayın ~4300 pencere ≈ 30–40 dk. 403 gelirse araç "desteklenmiyor: bot koruması" der.

**Linux sunucu denemesi (2026-11-17, `cio-sunucu`, Ubuntu ARM, veri merkezi IP'si):** Kick kanal/yayın listesi, tek VOD ve sohbet (`/messages`) uçları HTTP 200 döndü, bot koruması görülmedi; gerçek HLS ana liste adresi de 200 verdi. Sunucuda Python 3.12.3 var, **ffmpeg ve yt-dlp yok**: `tara`/`analiz` (yalnız Python + ağ) sunucuda çalışır, `kes` için `apt install ffmpeg fonts-dejavu-core` gerekir. Deneme geçici dosyalarla yapıldı, hiçbir şey kurulmadı/bırakılmadı. Sunucuya yerleştirme henüz yapılmadı.

## ffmpeg, yt-dlp, yazı tipi

- **ffmpeg** aranma sırası: `FFMPEG` ortam değişkeni → PATH'teki `ffmpeg` (drawtext ve gblur süzgeçleri varsa) → `imageio-ffmpeg` paketinin ffmpeg'i. Kurulum (kullanıcı düzeyi): `py -m pip install --user imageio-ffmpeg`; Linux'ta `apt install ffmpeg` (libfreetype'lı). Remotion'un kırpılmış ffmpeg'i kullanılmaz.
- **yt-dlp** Kick için gerekmez (ffmpeg HLS'i doğrudan okur); YouTube kaynağı için lazım (`py -m pip install --user yt-dlp`, 2026.10.26 denendi). Çerez/oturum kullanılmaz.
- **ffprobe** yok; klip doğrulaması `ffmpeg -i` çıktısından yapılır (1080x1920, ≤60 sn, ses var; değilse klip reddedilir).
- **Yazı tipi:** `KLIP_FONT` → Windows `arialbd.ttf`/`segoeuib.ttf` → Linux DejaVuSans-Bold/LiberationSans-Bold/NotoSans-Bold (`apt install fonts-dejavu-core`). **Açıklama yazısı** bunlara bağlı değildir: depodaki `otomasyon/fontlar/Anton-Regular.ttf` (Anton, SIL Open Font License 1.1; lisans metni yanında `Anton-OFL.txt`; kaynak: github.com/google/fonts `ofl/anton`, 2026-11-18) kullanılır, bu yüzden Linux sunucuda sistem yazı tipi kurmadan aynı görünür. Açıklama katmanı **Pillow** ile çizilir (`py -m pip install --user pillow`; Linux: `pip install pillow`); `KLIP_ACIKLAMA_FONT` ortam değişkeni yazı tipini değiştirir.

## Bilinen belirsizlikler

- **YouTube (2026-11-18):** (1) Kick+YouTube **çift kaynak gerçek çiftle denenmedi**; 66 çiftin metadatasında hepsi `belirsiz` çıktı, `muhtemel_ayni_yayin_inceleme` ve döküm eşleşmesi yalnız birim testle doğrulandı. (2) Altyazı↔Whisper kalitesi tek videoda ölçüldü (wtcN `uuPCSH9CQic`): altyazı aday taraması için yeterli, kelime/cümle sınırı için değil; bu yüzden seçilen adaylarda Whisper doğrulaması zorunlu. (3) ≥2 saatlik denemede video kurgulu final bölümüydü (3 s 46 dk), canlı yayın kaydı değil; gerçek uzun canlı yayın kaydı (sessizlik, müzik, konuk) denenmedi. (4) Heatmap yalnız eski/çok izlenen videoda dolu (3 denemeden 1'inde); yeni videoda aday kaynağı altyazı taramasıdır. (5) `tara` hem `videos` hem `streams` sekmesine bakar; denenen 3 videonun hepsi kurgulu yüklemeydi, `streams` sekmesinden gelen bir canlı yayın kaydı kesilmedi. (6) Kare düzeni Kick için ayarlı: YouTube'un 16:9 kurgulu videosunda yüz kamerası/oyun kadrajı klip başına değişir; Jahrein klibinde ortadan kırpma yüz kamerasını ve menü yazısını kesti (zayıf). (7) Model küfürlü anları elemiyor; paketlerde küfür var, yayın öncesi insan incelemesi şart. (8) yt-dlp YouTube'a bağlıdır; YouTube değişirse `yt-dlp` güncellemesi gerekir. Erişim denemesinde engel çıkmadı, ama hesap/çerez olmadan üyelere özel/yaş sınırlı videolar atlanır.
- **Model çağrısı azaltma:** Kemalcan'ın eski iyi klibi (1470 sn) yeni yolda çıkmadı; nedeni ayrıca incelenmedi. Yargı kalitesi elle etiketlenmedi; çağrı sayısı düştü, "daha iyi" iddiası yok.

- Kick VOD adresine `?t=<sn>` eklemek belgelenmemiş; paket JSON'unda `vod_zaman_damgali_url_dogrulandi: false`. Açıklamada güvenli olan "yayının M:SS noktası" yazısı kullanılır.
- Yayıncıların görüntüsünü yeniden paylaşmanın izin/telif durumu araçtan bağımsız bir karardır: yayınlamadan önce yayıncılardan izin alınması önerilir.
- Konuşmasız kipte sohbeti olmayan/çok seyrek yayınlarda zirve çıkmaz. GPU ile tam döküm taraması sohbetten bağımsız aday da üretebilir; CPU ve canlı kipte yalnız sohbet adayları doğrulanır.
- **Konuşmasız kip yalnız sohbetle sınırlı:** sinyaller sohbetin tepkisini ölçer, yayında olanı değil. Sohbet güldüğünde gülünç olan şey bazen yalnız iç şaka ya da bir izleyici didişmesidir (Kemalcan 22:00 "sınırda"); sohbetin sustuğu ama yayının çok güldüğü anlar kaçar. Sohbet tabanlı vurgu yakalama literatürü de ses+görüntüyle birleşik yönteme göre daha zayıf sonuç bildirir.
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
- **Yapılabilir ve ucuz; aday üretici olarak henüz etkin değil.** Denenebilecek biçim: 160p akıştan `ebur128` ile 10 sn'lik kısa dönem yüksekliği → yayının kendi dağılımına göre z puanı → dördüncü sinyal ("ses sıçraması"), özellikle sohbet sessiz yayıncılar için yedek.
- **Henüz kanıt yok:** iki pencerelik ölçümde kahkaha anı zirve olmayan andan *daha yüksek değildi* (−20.7 vs −18.4 LUFS); bu tek örnek bir şey ispatlamaz, ama sesin tek başına güvenilir olmadığına işaret eder (konuşma düzeyi ve oyun müziği baskın olabilir). Koda eklemeden önce en az 10 işaretli klip anıyla (ses z puanı ↔ insan değerlendirmesi) denenmeli.

## Konuşma katmanı (2026-11-18)

Kod: `tools/klip_konusma.py`; bütünleşme: `analiz`, `kes`, `otomatik`, `canli`. Yalnız döküm/yargı görmek için `analiz` kullanılır; kesim veya yayın yapmaz. `--konusma` tek çalıştırmalık açık denemedir; `--konusmasiz` eski sohbet akışıdır; `yontem:yogunluk` konuşma ayarı açık olsa bile eski yöntemi seçer. Kod varsayılanı kapalıdır; proje ayarı yukarıdaki tabloda gösterilir.

### Kurulum ve cihaz

Windows 11 / Python 3.12 kullanıcı düzeyinde denenmiş kurulum:

```powershell
py -m pip install --user faster-whisper==1.2.1 av==16.1.0 nvidia-cublas-cu12 nvidia-cudnn-cu12
py -m unittest discover -s tests -p "test_klip_konusma.py"
```

Deneme sürümleri: CTranslate2 4.9.0, cuBLAS 12.9.2.10, cuDNN 9.28.1.4, NVIDIA sürücü 621.24. İlk model çalıştırması açık model ağırlıklarını Hugging Face önbelleğine indirir; sonraki çağrılar yereldir. **Tuzak:** otomatik gelen PyAV 19.0.2, faster-whisper 1.2.1'in `metadata_errors` parametresini kabul etmedi; PyAV 16.1.0 ile düzeldi. Windows'ta NVIDIA pip DLL klasörleri yalnız ASR alt sürecinin PATH/DLL arama yoluna eklenir, kalıcı sistem ayarı değiştirilmez. Resmî bağımlılık açıklaması: [faster-whisper README](https://github.com/SYSTRAN/faster-whisper#gpu) (18.11.2026).

ASR `int8_float16` ile GPU'da, `int8` ile CPU'da çalışır. GPU denemesi → küçük model GPU → küçük model CPU sırası bellek/CUDA hatasında geri düşer. ASR ayrı süreçtedir; CUDA'nın süreç sonlandıran hatası ana klip hattını düşürmez. Whisper'dan önce Ollama'daki yüklü modeller `keep_alive:0` ile boşaltılır; servis kapatılmaz. Önce bütün ASR, sonra bütün dil modeli çağrıları yapılır: 6 GB VRAM'de iki model aynı anda tutulmaz.

Linux ARM için kod yolu `konusma_cihaz:cpu`, `konusma_kucuk_model:small`; CPU otomatik kipinde bütün yayın taranmaz, yalnız sohbet adayları dökülür. Sunucuya paket kurulmadı ve ARM'da ASR çalıştırılmadı; Python bağımlılıklarının o mimaride kurulabilirliği ayrıca doğrulanmalı. Windows CPU denemesi aşağıdadır.

### Önbellek ve seçim

`dokum/kick-<uuid>/ses/` içinde 16 kHz mono PCM WAV bulunur. Ana HLS listesinin en düşük bant genişlikli çeşidi seçilir: denenen Kick yayınında 160p, 230.000 bit/sn, yalnız-ses çeşidi yoktur. Tam döküm 300 sn, CPU/canlı adayları 60 sn ızgaraya oturur; her parçanın iki yanında 15 sn bağlam indirilir. Aynı parçayı isteyen örtüşen adaylar yeniden indirme/döküm yapmaz. Döküm modeli/cihazı, parça boyu, algoritma sürümü ve HLS başlangıç saati imzaya dahildir. Tamamlanmış her parça atomik JSON'dur; yarım kalan parçadan sürer. Segment ve kelime zamanları, sözcük olasılığı ve konuşma-yok olasılığı `.worker.json` içinde; yayının mutlak saniyesindeki sözcükler parça JSON'undadır. `--yeniden` analizi yeniden hesaplar, geçerli ses/döküm/yargı önbelleğini silmez.

Sohbetten son üç yerine en iyi 15 örtüşmeyen aday alınır. Her adaya bağlamıyla cümle ID'leri verilir; dil modeli 0–10 puan, anlaşılabilirlik, kısa gerekçe, olayın ilk/son cümlesi ve somut Türkçe başlık döndürür. Serbest metinden JSON avlanmaz; yalnız nesne veya tek JSON kod çiti kabul edilir. Şema bozuksa bir kez yeniden istenir; ikinci hata o adayı konuşma puansız bırakır. Geçerli yargı veremeyen modellerin ortam hataları kalıcı yargı önbelleğine yazılmaz.

Bitmiş yayında GPU varsa 1200 sn (20 dk) pencereler, 60 sn örtüşmeyle ayrıca taranır (en çok `konusma_tarama_an` = 8 olay/pencere; 2026-11-18'e dek 240/45 sn ve 3 olaydı, bkz. "Model çağrısı azaltma"). Birbirinin kısa aralığının en az yarısını kaplayan adaylar tek olaya iner, en yüksek sohbet puanı korunur. Tam tarama sohbetin kaçırdığı aday üretebilir; görsel olayı görmez. Son puan `100 × (0.35 × sohbet/100 + 0.65 × konuşma/10)`; ağırlıklar normalize edilir. Konuşma puanı <6 veya `anlasilir:false` ise sohbet puanı ne olursa olsun elenir. Yargı yoksa eski sohbet puanı korunur; hiçbir çağrı/yargı yapılamazsa raporda **konuşma katmanı kapalı** ve neden yazar, sohbet yöntemiyle devam edilir.

Cümleler segment sınırından değil zaman damgalı kelimelerdeki `.?!…` işaretlerinden kurulur. Tam cümle başlangıç/bitişleri aranır; önce 30–55 sn denenir, yalnız gerekirse ayardaki 59 sn'ye esner. 350 ms ses payı da üst sınıra dahildir (üst süreye sığdığı kadar). Olay 59 sn'ye sığmıyorsa veya tam cümle çifti yoksa aday kesilmez. Noktalama ASR'nin tahminidir; konuşmacı ayrımı, üst üste konuşma ve gerçek sözdizimsel cümle sonu garantisi değildir.

Dil modeli taşıması haber hattının `model_ayari` ve `Hat.model` işlevleridir; `Hat.__init__` veya haber iş akışı çalıştırılmaz. Aynı `otomasyon/modeller.json` kullanılır. Ölçümde yerel modeller yetersiz bulunduğu için tercih mevcut haber yazar ayarındaki `sonnet` oldu; `konusma_bulut:true` bunu etkinleştirir. Yalnız adı seçilen model çağrılır; başarısız kalite ölçümü olan modele sessiz geri düşme yapılmaz. Sonnet çağrılamazsa sohbet yöntemi sürer. Yargıda araçlar ve MCP/kasa erişimi kapatılır; haber araştırmasının yetkileri taşınmaz (yerel Claude CLI yardımındaki `--tools ""` ile). `konusma_bulut:false` ile bulut modeli çağrılmaz; `konusma:false` ile tüm katman kapalıdır. Yeni servis/anahtar eklenmedi; mevcut Claude CLI oturumu kullanılır, bunun var olan plan kotasına etkisi vardır. Haber dosyaları, sosyal kuyruk, git ve site değişmez.

### Model çağrısı azaltma (2026-11-18)

Sorun: 240 sn'lik pencere başına bir Sonnet çağrısı 2 saatlik yayında 81–95 çağrı (Kemalcan 139 dk: 81 çağrı / 1473.5 sn; Eray 155 dk: 95 çağrı). Çözüm: (1) tarama penceresi 1200 sn / 60 sn örtüşme; (2) sohbet adayları ve heatmap adayları tek istekte toplu doğrulanır (`konusma_toplu`); (3) çağrı tavanı `konusma_cagri_butcesi` (2 saat için 15; yeniden denemeler dahil). Toplu şema `{"pencereler":[{"id":N,"anlar":[…]}]}`; her pencere ayrı doğrulanır: yapısal hata (id tekrarı, eksik/fazla pencere) bütün yanıtı reddeder ve hata mesajıyla bir kez yeniden istenir, tek pencerenin içerik hatası yalnız o pencereyi yargısız bırakır. Yalnız tamamen geçerli yanıt yargı önbelleğine yazılır. Yargısız kalan bir aday, tarama penceresi onu zaten kapsıyorsa seçime girmez (eski sohbet puanıyla "yargısız klip" çıkmaz).

Ölçüm (aynı gerçek döküm, **eski yargı önbelleği kullanılmadan**, `konusma_yargi_onbelleksiz`; Sonnet; betik `C:\Cihan.Ai\.scratch\yayin-klip\youtube-cagri-olcum2.py`):

| VOD | Önce | Sonra |
|---|---|---|
| Kemalcan `kick:9ae47b40…` (139 dk) | 81 çağrı, 1473.5 sn | **9 çağrı**, 361.9 sn model süresi (duvar 363.8 sn) |
| Eraycan `kick:d38999bc…` (155 dk) | 59 çağrı, 1056 sn (önceki ölçüm turu; ilk tam tarama 95) | **12 çağrı**, 344.4 sn duvar |

Nihai anlar (başlangıç sn, sohbet+konuşma birleşik puan / konuşma puanı):

| VOD | Eski | Yeni |
|---|---|---|
| Kemalcan | 1470 (57.3/6), 1704 (65.8/7), 2609 (74.8/8) | 1282 (72.1/7), 2229 (66.6/7), 2614 (74.8/8) |
| Eraycan | 585 (45.5/7), 1841 (45.5/7), 4774 (58.9/6) | 1904 (61.5/6), 4358 (45.5/7), 4774 (65.4/7) |

Okuma: iki VOD'da da çağrı ≤15 hedefinin içinde. Kemalcan'da 2609/2614 (şort/boxer) ortak kaldı, diğer iki an değişti: eski ilk an (1470, karnaval/basket) yeni listede **yok**; yeni ölçümde bunun neden elendiği ayrıca incelenmedi. Eraycan'da 4774 (patates soyma oyunu) ortak; eski 585 ve 1841 yerine 1904 (aynı patates esprisinin devamı) ve 4358 (havuç soyma) geldi. "Daha iyi" iddiası yoktur: yargı tek model çağrısı, elle etiket yok; çağrı sayısı düşerken seçilen ortak an sayısı Kemalcan'da 1/3, Eraycan'da 1/3 kaldı (tahmin: pencere büyüdükçe modelin her pencerede göstereceği an sayısı sınırlı). Aynı toplu yol YouTube'da da kullanılır (3 gerçek videoda 4, 3 ve 13 çağrı; en uzunu 3 s 46 dk: 12 tarama penceresi + 1 aday doğrulaması, tavan 45).

### Canlı kip

Yalnız kapanmış dalgaların aday çevresi dökülür; canlıda tam tarama yapılmaz. Böylece her 5–10 dakikalık tek turda geçmiş yayının tamamı yeniden işlenmez. 60 sn ızgara ve 15 sn bağlam nedeniyle tek adayın indirdiği/döktüğü süre önerilen yaklaşık 60 sn pencereden bir miktar geniş olabilir. Son 60 sn ses ızgarası ve 15 sn bağlam henüz kapanmamışsa aday sonraki tura bırakılır; kısmi kuyruk tamamlanmış önbellek sayılmaz. Yargıdan sonra cümleye oturan aralık için kapalı-dalga ve daha önce kesilmiş epoch aralığı denetimi tekrar yapılır. Mevcut `canli.kilit`, kesim başına durum kaydı ve yarım klibi reddetme korunur. Tur raporunda `tur_sn`, konuşma raporunda ASR/indirme/model çağrı süreleri yer alır.

### İlk ASR ölçümü (gerçek yayın, 18.11.2026)

Kemalcan 15.11, aynı 1200–1800 sn / 600 sn ses. RTX 3060 Laptop 6 GB, 31 GB RAM, Python 3.12. GPU öncesi Ollama boşaltıldı. Hız sütunu yalnız döküm süresinden, model yükleme ayrı; ilk ağırlık indirme dahil değil.

| Model / cihaz | Döküm | Yükleme | Hız | Tepe toplam VRAM |
|---|---:|---:|---:|---:|
| large-v3-turbo / GPU int8_float16 | 34.141 sn | 9.406 sn | 17.57× | 3116 MiB (önce 722) |
| small / GPU int8_float16 | 46.969 sn | 6.281 sn | 12.77× | 2540 MiB (önce 722) |
| small / CPU int8, 4 iş parçacığı | 131.671 sn | 7.407 sn | 4.56× | ASR CPU'da; eşzamanlı başka GPU işi olduğundan toplam VRAM kıyaslanmaz |

Aynı 10 dk'yı 160p'den WAV'a indirme 15.859 sn; master bant değerinden hesaplanan trafik 17.25 MB. Yalın 2 saatlik akış 207 MB; 300 sn ızgaradaki 15+15 sn bağlam yaklaşık %10 ek indirme/döküm getirir. 2 saatlik dökümün bu kısa örnekten düz hesabı turbo GPU 6.83 dk, small GPU 9.39 dk, small CPU 26.33 dk; model yükleme, her parçada süreç başlatma, ağ ve dil modeli çağrıları dahil değildir. Tam hat süreleri ayrıca ölçülür; bunlar bitmiş yayın ölçümü diye okunmamalıdır.

İki dökümün ilk 20 segmenti metin üzerinden yan yana incelendi. Turbo `Salçalı makarna. Çok güzel.` ve `Tamam et al yapıyorum.` yazarken small `Sağ ol, çalamakarla.` ve `Tamam, et almıyor, püüüüm.` üretti. İkisinde de `Neredesin aşkım sen?`, `Aşkım bugün bize ne yemek yapıyorsun bakalım ya?` ve çalışmaya inanılmadığı konuşması korunuyor. Turbo da `Et almıyorum çevre`, `Ahmadiko` gibi belirsiz/hatalı ifadeler üretiyor. Seçim: daha hızlı ve bu örnekte daha okunaklı **large-v3-turbo**; bu, elle dinlenmiş referans/WER ölçümü değildir. Döküm bir olayın geçtiğinin tek başına kesin kanıtı sayılmaz.

Aynı parçadaki ilk konuşmadan 15 cümle/ifade, metinlerin elle karşılaştırması (ses referansına göre doğruluk puanı değildir):

| Yaklaşık yayın zamanı | Turbo | Small | Metin üzerinden yargı |
|---|---|---|---|
| 20:00 | Neredesin aşkım sen? | Neredesin aşkım sen? | aynı |
| 20:02 | Mutfak. | Hıhı. | farklı; sonraki cümle mutfağa işaret ediyor |
| 20:03 | Mutfakta oturuyor. | Mutfakta hatırıya. | turbo daha anlaşılır |
| 20:04 | Aşkım bugün bize ne yemek yapıyorsun bakalım ya? | aynı cümle | aynı |
| 20:10 | Salçalı makarna. | Sağ ol, çalamakarla. | turbo anlamlı yemek adı |
| 20:12 | Çok güzel. | Çok güzel. | aynı |
| 20:15 | Aşkım bu şeylere ne zaman başlayacaksın böyle hani kordon bulu falan gibi şeyler yapmaya ne bileyim. | Aşkım bu şeylere ne zaman başlayacaksın? Böyle hani kordon blu falan gibi şeyler yapmaya ne bileyim. | içerik benzer; yemek adı ikisinde de sorunlu |
| 20:20 | Et almıyorum çevre. | Et almıyor, çelerti. | ikisi de belirsiz |
| 20:22 | Et almıyorum eve mi? | Et almıyor mu evime? | özne/ekler farklı; ses referansı olmadan karar yok |
| 20:23 | Almıyorum. | Almıyor. | kişi eki farklı; karar yok |
| 20:24 | Ulan burada bak oturmuş burada eşin çalışıyor işte iş başında şu an. | Ulan burada bak, oturmuş, burada eşin çalışıyor işte. İş başında şu an. | aynı anlam |
| 20:27 | Tamam et al yapıyorum. | Tamam, et almıyor, püüüüm. | turbo daha anlaşılır |
| 20:29 | Abi bu kız benim çalıştığıma bir türlü inanmıyor ya şu an ben çalışıyorum. | Abi bu kız benim çalıştığıma bir türlü inanmıyor ya. Şu an ben çalışıyorum. | aynı anlam |
| 20:33 | Ahmadiko / Ahmadım / bizim Ahmet değil mi | Ahmet İko / Ahmet'im / bizim Ahmet değil mi | small özel adda daha tutarlı |
| 20:38 | Ahmet'im çok çok teşekkür ediyorum. | Ahmet'im çok çok teşekkür ediyorum. | aynı |

### HLS zaman çizelgesi tuzağı (Eray 12.11, gerçek ölçüm)

Eray VOD API süresi 9322 sn; HLS medya süreleri toplamı 9269.019 sn, PDT duvar saati ekseni yaklaşık 9320.684 sn. 2489.251. medya saniyesinde `EXT-X-DISCONTINUITY` ve yaklaşık 52 sn duvar saati boşluğu var. Tam HLS listesine `ffmpeg -ss 6585 ... -t 330` denemesi 194.77 sn WAV verdi ve listedeki 700'lü segmentlere atladı: **kesintiden sonra global HLS seek yanlış bölümü seçebiliyor**. İstenen PDT aralığının 28 segmentinden yerel liste yapınca aynı deneme tam 330.0 sn verdi.

Konuşma ses yolu bu nedenle segmentleri `PROGRAM-DATE-TIME` ile eşler, sürekli kısımları ayrı indirir, gerçek yayın kesintisini sessizlikle aynı saniye ekseninde tutar. Konuşmalı klip kesimi de yalnız istenen segmentlerden yerel HLS listesi kullanır; kesintiyi aşan klip reddedilir. Kesintili VOD’un eski global-seek dökümlerinin tamamı `-pdt2` önbelleğinden ayrılır; kesinti öncesinin de varsayımla doğru olduğu kabul edilmez. Eray’ın ilk 40 dakikası da yeni yolla yeniden üretildi; bazı cümleler aynı çıksa da eski ve yeni parçalar karıştırılmadı. Şifreli HLS ve saat damgası olmayan kesinti desteklenmez; konuşma katmanı nedenini raporlayarak kapanır. Konuşmasız eski kesim yoluna müdahale edilmedi: **bu eski yoldaki Eray kesimlerinin kesinti sonrasındaki içerik hizası yeniden doğrulanmalıdır**. Önceki sohbet temelli iyi/sınırda etiketler bu kısıtla değerlendirilir.

### Ses olayı sinyali kararı (10 etiketli an)

Yeni ölçüm: iki gerçek yayının doğru PDT eksenindeki WAV'larında 10 sn RMS dBFS; her etiket için −30…+20 sn aralığındaki tepe, yayının RMS dağılımına göre z puanı. Bu, önceki LUFS/LRA denemesiyle aynı metrik değildir.

| Yayın / an | Önceki etiket | Tepe RMS z |
|---|---|---:|
| Kemalcan 6:20 | zayıf | 1.03 |
| Kemalcan 40:50 | zayıf | 0.15 |
| Kemalcan 22:00 | sınırda | 0.14 |
| Kemalcan 44:10 | iyi | 0.86 |
| Kemalcan 1:33:10 | iyi | 0.68 |
| Eray 13:30 | sınırda | 0.90 |
| Eray 31:50 | sınırda | 0.52 |
| Eray 49:50 | iyi | 0.15 |
| Eray 39:00 | zayıf | 0.80 |
| Eray 41:50 | zayıf | 0.64 |

Üç iyi anın ortalama tepe z'si 0.56; dört zayıf anın 0.66. `z≥1` üç iyi anın hiçbirini bulmuyor, bir zayıf anı buluyor (bu küçük kümede kesinlik 0/1, yakalama 0/3). Konuşma-yok olasılığı dökülmüş konuşma segmentlerinde dört ondalıkta yaklaşık sıfırdı; VAD'nin dışarıda bıraktığı sessizlik/kahkahayı temsil etmez. **Karar: ses yüksekliğini/kahkaha varsayımını aday üretici olarak ekleme.** n=10 küçük ve etiketler önceki sohbet incelemesinden; bu sonuç daha iyi bir kahkaha sınıflandırıcısının işe yaramayacağını kanıtlamaz.

Gerçek HLS bayt ölçümü: Kemalcan 1200–1800 hedefini örten 49 adet 160p segment, 608.333 sn medya, **22,065,560 bayt** (iki HTTP okuyucuyla 1.234 sn; yeniden döküm yapılmadı). Bu yaklaşık 290 kbit/sn gerçek TS trafiğidir; master'daki 230 kbit/sn değeriyle yapılan önceki 207 MB / 2 saat hesabı düşük kalıyor. Aynı örnek hızla 2 saat yaklaşık 261 MB; 15 sn bağlam ve segment kenarlarıyla 300 sn ızgarada yaklaşık **0.29–0.30 GB** indirme beklenir. Bunlar yayın boyunca sabit bitrate varsayımıdır, tüm iki saatin ağ sayacı ölçümü değildir.

### Dil modeli karşılaştırması (aynı sekiz gerçek pencere)

Önceki insan etiketleri kesin altın standart değildir: sohbet/kare incelemesinden gelir; konuşma dökümünde görünmeyen görsel olayları içerebilir. Buna rağmen aynı 80 sn döküm pencereleriyle karşılaştırıldı. Puan bandı: 0–3 zayıf, 4–5 sınırda, 6–10 iyi. `anlasilir:false` ayrıca vetodur. Aşağıda `—` iki denemede şema/cümle sınırı geçmemiş yargıdır.

| An / önceki etiket | Gemma 4B | Qwen 8B | Haiku | Sonnet |
|---|---:|---:|---:|---:|
| Kemalcan 6:20 / zayıf | 7 | 6 | 2 | 6 |
| Kemalcan 22:00 / sınırda | — | 6 | 2 | 5 |
| Kemalcan 44:10 / iyi | — | 6 | 2 | 6 |
| Kemalcan 1:33:10 / iyi | 8 | 5, anlaşılmaz | 2 | 4, anlaşılmaz |
| Eray 31:50 / sınırda | 9 | 7 | 2 | 4, anlaşılmaz |
| Eray 39:00 / zayıf | — | — | 2 | 3, anlaşılmaz |
| Eray 49:50 / iyi | 6 | 6 | 2 | 2, anlaşılmaz |
| wtcN 1:17:20, eski klip 1 / sınırda | 7 | 7 | 3 | 3, anlaşılmaz |

Gemma 5/8, Qwen 7/8, Haiku ve Sonnet 8/8 geçerli yargı verdi. Eski etiketle puan bandı örtüşmesi sırasıyla 2/8, 2/8, 2/8 ve 4/8. `puan≥6 && anlasilir` ile iyi önerme kesinliği Gemma 2/5 (%40), Qwen 2/6 (%33), Sonnet 1/2 (%50); Haiku hiç iyi önermedi ve üç iyi etiketli anın tamamını reddetti. Sekiz pencerenin toplam çağrı duvar süreleri Gemma 54.718 sn, Qwen 203.579 sn, Haiku yaklaşık 149 sn, Sonnet yaklaşık 106 sn; ilk model yüklemeleri ve yeniden denemeler dahil. Bu küçük ve gürültülü veriyle genel doğruluk iddiası yoktur.

Big Pickle mevcut ücretsiz yolunda ilk çağrı HTTP 429 / `FreeUsageLimitError` verdi; kalan örneklerde yeniden çağrılmadı. Yeni hesap/ödeme açılmadı. Mevcut Haiku/Sonnet CLI yolları çalıştı. Karar: **Sonnet ile deneme, en az 6 puan**; yerel modellerde anlaşılmaz metni absürt mizah sayma ve gerekçe/puan çelişkisi görüldü, Haiku ise aşırı muhafazakâr kaldı. Sonnet tek başına güvenilir otomatik editör sayılmaz: 6:20 oy şakasına 6 vererek eski zayıf etikete katılmadı; bu yanlış pozitif riski açıktır. Sohbetten elenmiş bu an tam taramada dönse bile sohbet puanı 0 olur ve diğer adaylarla birleşik puanda yarışır.

Özellikle istenen iki sınırda örnek: Sonnet Kemalcan 22:00'a **5**, “anneniz de dayınızın kardeşi” karşılığını kısmen anlaşılır ama chat bağlamına bağlı buldu; 6 eşiğinde elenir. wtcN eski klip 1'e **3 / anlaşılmaz**: “AI mı bu, gerçek mi” tepkisinin hangi görüntüye verildiği dökümden anlaşılmadı, elenir. Kemalcan 44:10'a 6 verip şort/boksör takasını somut olay olarak anlattı. Eray 49:50'de döküm rutin Discord bağlantısı gösteriyor; eski iyi etiketin dayandığı “Discord'u WhatsApp okudu” anı bu dar pencerede yoktur. Dökümde WhatsApp ifadeleri 48:04 ve 48:45'tedir; sohbet tepki gecikmesi ve önceki zaman hizası bu örnekte belirsizdir.

### Kesilen sesin gerçekten dökümle aynı olması

Yalnız kelime zamanına ve dosya süresine güvenilmez. Gerçek canlı benzetiminde 160p ASR sesi ile eski HD kesiminin ilk 15 sn dalga biçimi arasında **1.910 sn / korelasyon 0.996** fark bulundu. Küçük HLS listesindeki `-ss`yi `-i`nin **sonrasına** almak, denenen doğru kliplerde artık farkı yaklaşık **0.043 sn**'ye indirdi. Eski global/input seek sonuçlarını cümle sınırı doğrulaması olarak kullanmayın.

Her pozitif konuşma adayı, ilk ve son cümlenin döküldüğü gerçek 16 kHz WAV'a referans taşır. Kesilmiş HD klibin başı (en çok 15 sn) ve sonu (10 sn), ilgili WAV'la ±5 sn alanda 1500 Hz anti-alias filtresi sonrası normalize FFT korelasyonuyla eşlenir. En az 0.70 korelasyon ve en çok 0.12 sn artık fark gerekir. Gerekirse baş ve son ayrı düzeltilip tekrar kodlanır; en çok dört deneme. Düzeltme 30–59 sn sınırından, VOD'dan, HLS kesintisinden veya daha önce kesilmiş aralıktan taşamaz. Gerçek kodlanmış MP4 süresinin istenen süreden >0.15 sn sapması da yarım klip diye reddedilir. Başarısız aday nihai dosyaya taşınmaz; diğer adayların kesimi sürer. Hiç klip başarılamazsa VOD işlenmiş sayılmaz.

`video.ses_hizasi` baş/son korelasyonlarını ve düzeltmeleri kaydeder. `konusma_plan_araligi`, modelin ASR saati üzerindeki planıdır; paketin asıl başlangıç/bitişi doğrulanmış video saatidir. Bu ayrım, hizalanmış klibi her çağrıda yeniden kodlamadan önbellekten kullanmayı sağlar. Dalga eşleşmesi aynı sesin kesildiğini doğrular; ASR'nin kelimeyi doğru anladığını veya esprinin iyi olduğunu kanıtlamaz.

Canlı ilk turda en çok **6** aday dökülür (bitmiş yayında 15). Geçerli içerik/cümle vetoları `durum.json → konusma_elenen` içine gerçek saat aralığı ve model/ayar/prompt imzasıyla kaydedilir. Sonraki tur bu adaylarda takılmadan sıradakine ilerler; konuşmasız kip veto hafızasını dikkate almaz, model/eşik değişikliği yeniden değerlendirmeyi açar. Ortam/JSON hatası kalıcı veto değildir. Bu davranış birim ve bütünleşme testinde iki ardışık turla sınandı.


## Kısa açıklama (`kisa_aciklama`, 2026-11-18)

Cio'nun isteği: videolarda "Ferit saçlarını yayında boyatıyor" gibi çok kısa bir olay cümlesi olsun.

**Üretim (`tools/klip_konusma.py`).** Konuşma yargısı şemasına `kisa_aciklama` eklendi: klipte olanı söyleyen tek Türkçe cümle, ≤45 karakter, düz anlatım, özne yayıncının `kisa_ad`ı (wtcN→Ferit, Eraycan→Eray, Kemalcan Parlak→Kemalcan, Tolunay Ören→Tolunay, Jahrein→Jahrein; `klip-yayincilar.json`). Yargı çağrısının **içinde** istenir, ek model çağrısı yok. Kod güvenliği (`kisa_aciklama_dogrula`): 45'i aşan, yasak kelimeli (`aciklama_yasak_kelimeler` koddaki listeye eklenir), emoji/#etiket/büyük harf yığınlı veya boş metin `null` olur; **kısaltma yapılmaz** (yüklemi kesmek anlamı bozar). Anlamlı cümle yoksa model `null` verir → yazısız klip.

**Geri doldurma (`aciklama-doldur`).** `kisa_aciklama`sı olmayan ve döküm metni olan konuşma paketlerinin hepsi TEK toplu çağrıya girer; dökümsüz eski sohbet paketlerine dokunulmaz. Model hâlâ 45'i aşarsa en çok **1 ek çağrıyla** "tamir" yapılır (`aciklama_toplu(..., tamir=True)`: istemde `onceki` ve `onceki_uzunluk` verilir); sonuç paketteki `kisa_aciklama_tamir`/`kisa_aciklama_onceki_ham` alanlarına yazılır. Ölçüm: ilk çağrıda 19 paketin 12'si 45+ karakterdi (`null`); istem sertleştirilip tamir eklendikten sonra 19'unun 19'u geçerli. Bu işte açıklama için toplam 3 Sonnet çağrısı yapıldı (ilk toplu çağrı, tamir ve iki dayanaksız/muğlak açıklamanın notlu yeniden yazımı birleştirilerek); derleme ayrıca 1 çağrı yaptı. Analiz önbelleği: `analiz_onbellegine_isle` artık `vod_id` yoksa `vod_url`'den Kick uuid / YouTube 11 karakter id çıkarır (Kick paketleri `kick-None.json` arıyordu).

**Yazı (dikey klip, `tools/yayin_klip.py`).** `kisa_aciklama` varsa görüntü karesinin hemen ÜSTÜNDE, en büyük yazı olarak etiket biçiminde (satır başına bir kutu) durur; ≤2 satır. Ayrıntı, yerleşim ve stiller: aşağıdaki **Açıklama görünümü**. Açıklama yoksa filtre zinciri eski koddakiyle **birebir aynı** (`ALTIN_FILTRE` testi: kadraj, şerit, varsayılan; yazılar drawtext ile). `klip_aciklama_yazi: false` veya `--aciklamasiz` yazıyı kapatır; düzen imzası açıklamayı, stili ve tasarım sürümünü içerir (`paket_guncel` açıklama/stil değişince yeniden üretir). `GORSEL_AYAR` (`klip_aciklama_yazi`, `aciklama_yasak_kelimeler`, `klip_aciklama_stil`) analiz önbellek imzasına girmez; `gorselsiz()` ile ayrılır.

**Dürüst zayıflıklar.** (1) `konusma-hizali-*` paketleri analiz önbelleğindeki klip kaydıyla eşleşmiyor (yalnız `konusma-NN` eşleşti); `kes` yeniden çalıştırılırsa `paket_guncel` açıklamasız yeniden kesme riski var — ölçmedim, koddan çıkarım. (2) Açıklamalar dökümle elle karşılaştırıldı, hepsi dökümle uyumlu; ama "Eray ile arkadaşları '10'da 10 ama' oynuyor" doğru ama zayıf (şaka, olay değil). Eray konusma-hizali-01 `kisa_aciklama`sı ilk çağrıda dayanaksız çıktı ("tatil" dökümde yok); notlu yeniden yazımla düzeltildi (`kisa_aciklama_inceleme`). (3) Dökümsüz sohbet paketleri açıklamasız kalır.


<!-- KONUSMA-SON-OLCUM-BEGIN -->

### Açıklama görünümü (2026-11-18, Cio: "çok düz, fontu değiştir, biraz aşağı koy")

- **Yerleşim (1080x1920, kadraj varsayılanı: görüntü y=430–1330).** Açıklama etiketinin alt kenarı görüntü karesinin üstünden **40 px** yukarıdadır (`video_boslugu`); en üst **150 px boştur** (Shorts/Reels arayüzü; gölge payı 16 px dahil etiket en az y=166'da başlar). Yayıncı adı + oyun, kaynak ve marka satırları görüntünün **altında** (y≈1358'den) alt alta dizilir (`Ad · Oyun` tek satırda: ad beyaz, oyun sarı). Oyun adı yoksa yalnız ad. Aynı hesap serit düzeninde de geçerlidir (kare y=656'dan başlar).
- **Boyut.** Anton 78 pt'tan başlar; tek satır yalnız ≥64 pt'ta kabul edilir, değilse iki satıra bölünür (kelime ortasından değil, kısaltma yok); iki satır 54 pt'a kadar küçülür; üst sınıra sığmazsa açıklama çizilmez ve klip eski görünümle kesilir (`aciklama_yazisi.yazilmadi`).
- **Stil (`klip_aciklama_stil`, ayar bölümü `ayar`; varsayılan `A`; `A|B|C`, başka değer `KlipHatasi`).** `A`: dolu sarı (0xFFD54A) yuvarlak köşeli etiket + lacivert (0x0B0D17) yazı, satır başına kutu, hafif gölge. `B`: koyu lacivert yarı saydam etiket + sarı çerçeve, beyaz yazı, ilk kelime (özne) sarı. `C`: zeminsiz, kalın siyah kontur + gölge, beyaz yazı, ilk kelime sarı. Ad/oyun/kaynak/marka her stilde aynı (kontur + gölge, zeminsiz). Üç stilin geometrisi aynıdır; yalnız çizim değişir. Ayar `otomasyon/klip-yayincilar.json` > `ayar` > `klip_aciklama_stil`; stil değişince açıklamalı klipler `paket_guncel` ile yeniden üretilir (`yeniden-uret`).
- **Nasıl çizilir.** Açıklamalı klipte bütün yazılar tek şeffaf PNG katmanına çizilir (`aciklama_katmani`, Pillow, 2x çizim + LANCZOS küçültme) ve ffmpeg'e ikinci girdi olarak verilir (`[v0][1:v:0]overlay=0:0:format=auto`); drawtext, yazı tipi yolu veya Türkçe karakter kaçışı yoktur, Windows ve Linux'ta aynı çıkar. Girdi sırası tuzağı: PNG kaynağın hemen ardından gelir, yoksa yerel HLS'te `-ss` PNG'yi de kaydırırdı (`ffmpeg_komutu(..., katman=)`, testli).
- **Seçilen varsayılan: A.** Gerekçe, aynı gerçek karede (Kemalcan, parlak bulanık arka plan): sarı dolu etiket arka plandan en net ayrılan ve telefon boyutunda en okunaklı olandır; B şık ve okunaklı ama beyaz yazı ile çerçeve A kadar güçlü bir leke oluşturmaz; C zeminsiz olduğu için parlak/karışık arka planlarda en zayıfı.
- **Yazı tipi.** Anton, OFL 1.1 (`otomasyon/fontlar/`); Türkçe harfler (ç ğ ı İ ö ş ü) tam, `İğüşöçıĞÜŞÖÇ` gerçek kare üzerinde çizilip doğrulandı, testte fontTools ile de denetlenir.
- **Kareler (scratch):** `C:\Cihan.Ai\.scratch\yayin-klip\tasarim\aciklama-{A,B,C}.png`, `aciklama-karsilastirma.png`, `aciklama-uzun-2satir.png` (Eray), `aciklama-youtube-tolunay.png`.


## Yalnız sohbet ↔ sohbet + konuşma

Satırlar iki sıralı listeyi yan yana gösterir; aynı olayın zaman eşlemesi değildir. Yargılar döküm ve örnek karelerin elle incelemesidir, kör insan deneyi değildir. Her iki VOD’da tam döküm, geniş aday doğrulama, tam tarama ve gerçek kesim çalıştı.

### Kemalcan Parlak — Just Chatting

| Yalnız sohbet zirvesi | Yeni klip aralığı | Konuşma puanı / kısa gerekçe | Dökümden kısa alıntı | Benim değerlendirmem |
|---|---|---|---|---|
| 22:00 | 24:29–25:26 (56.84 sn) | 6/10 — Yayıncı karnaval oyunlarında kazandığı oyuncakları ve attığı basketle övünüyor, sevgilisi 'yalan söylüyorsun' diye itiraz ediyor. O da balonları ve oyuncakları kanıt g… | “Yalan söylüyorsun.” / “Hepsini ben kazandım.” | iyi — oyuncak iddiası ve sevgilisinin itirazı birlikte var. |
| 44:10 | 28:24–28:58 (34.07 sn) | 7/10 — Koltuk ve ezilmiş panda esprisi kendi içinde tamamlanıyor. | “Üç katın koltuk almışsın. İçinde kayboldu.” | sınırda — panda/koltuk şakası var; ilk cümleler dağınık, isimler belirsiz. |
| 1:33:10 | 43:29–44:24 (55.0 sn) | 8/10 — Biri şaka olsun diye arkadaşının şortunu indiriyor, altında boxer olduğu ortaya çıkıyor. Anlatan, adamın etrafına bakıp yavaşça çekmesini ve boxer düğmesinin açık olma… | “Ben de sana donumu vereyim dedi.” / “Abi ayıp olurdu.” | iyi — don hediyesiyle biten olay anlaşılıyor; bazı isim/özne ayrıntıları ASR’de belirsiz. |

### Eraycan — Potato Please

| Yalnız sohbet zirvesi | Yeni klip aralığı | Konuşma puanı / kısa gerekçe | Dökümden kısa alıntı | Benim değerlendirmem |
|---|---|---|---|---|
| 13:30 | 1:03:24–1:04:18 (54.2 sn) | 7/10 — İki aşamalı kız çocuğu tatil sorusu, 'yasak, evden çıkamaz' ve 'baba olunca düşünürüm' çıkışı | “Ben o ikinci aşamayı baba olunca düşünüyorum. Kardeşim bana ne ya.” | sınırda — tatil sorusu anlaşılır, önceki soru aşamasına atıfla başlıyor. |
| 31:50 | 1:09:37–1:10:22 (45.73 sn) | 7/10 — Arkadaşının sevgilisinin aldatması sorusuna 'üç gün beklerim' cevabı ve 'o yüke hazır olmak' açıklaması. | “Ben bir üç gün beklerim.” / “O yüke hazır olmak üç gün.” | iyi — soru, üç gün bekleme cevabı ve nedeni kendi başına anlaşılır. |
| 49:50 | 1:19:34–1:20:15 (40.8 sn) | 6/10 — '10'da 10 ama...' oyunu: biri 'evde patatesleri Eray gibi soyacak' diye laf atıyor, karşı taraf alınıp 'ben hep patates soydum' diye atışıyor. Ardından 'sizinlikten 24… | “10’da 10 ama evde patatesleri Eray gibi soyacak.” / “Olur, olur.” | sınırda — patates iç şakası önde; “kavga” başlıkta abartılı, sonraki ilişki soruları daha bağımsız. |

Konuşmanın sohbetin kaçırdığı **nihai** anları var: Eray 1:03:24–1:04:18 ve 1:09:37–1:10:22, yalnız `tarama` kaynağından geldi; ilk 15 sohbet adayı arasında da yoktu. Kemalcan’ın nihai üçünde konuşma + geniş sohbet listesi etkili, yalnız konuşmadan gelen bir nihai seçim **yok**. Kemalcan 22:00 Sonnet’te 5 / sınırda; wtcN eski klip 1, 1:17:20’de 3 / anlaşılmaz: ikisi de 6 eşiğinde elendi.

## Nihai MP4 ve paketler

- [C:\Cihan.Ai\.scratch\yayin-klip\cikti\kemalcan-parlak-20261115-9ae47b40\konusma-hizali-01.mp4](C:/Cihan.Ai/.scratch/yayin-klip/cikti/kemalcan-parlak-20261115-9ae47b40/konusma-hizali-01.mp4) — 56.84 sn; aynı adlı `.json` paket.
- [C:\Cihan.Ai\.scratch\yayin-klip\cikti\kemalcan-parlak-20261115-9ae47b40\konusma-hizali-02.mp4](C:/Cihan.Ai/.scratch/yayin-klip/cikti/kemalcan-parlak-20261115-9ae47b40/konusma-hizali-02.mp4) — 34.07 sn; aynı adlı `.json` paket.
- [C:\Cihan.Ai\.scratch\yayin-klip\cikti\kemalcan-parlak-20261115-9ae47b40\konusma-hizali-03.mp4](C:/Cihan.Ai/.scratch/yayin-klip/cikti/kemalcan-parlak-20261115-9ae47b40/konusma-hizali-03.mp4) — 55.0 sn; aynı adlı `.json` paket.
- [C:\Cihan.Ai\.scratch\yayin-klip\cikti\eraycan-20261112-d38999bc\konusma-hizali-01.mp4](C:/Cihan.Ai/.scratch/yayin-klip/cikti/eraycan-20261112-d38999bc/konusma-hizali-01.mp4) — 54.2 sn; aynı adlı `.json` paket.
- [C:\Cihan.Ai\.scratch\yayin-klip\cikti\eraycan-20261112-d38999bc\konusma-hizali-02.mp4](C:/Cihan.Ai/.scratch/yayin-klip/cikti/eraycan-20261112-d38999bc/konusma-hizali-02.mp4) — 45.73 sn; aynı adlı `.json` paket.
- [C:\Cihan.Ai\.scratch\yayin-klip\cikti\eraycan-20261112-d38999bc\konusma-hizali-03.mp4](C:/Cihan.Ai/.scratch/yayin-klip/cikti/eraycan-20261112-d38999bc/konusma-hizali-03.mp4) — 40.8 sn; aynı adlı `.json` paket.

Altısı da H.264 + sesli 1080×1920; 34.07–56.84 sn. Son bağımsız ses kontrolünde baş/son farkı 0.0427–0.0527 sn, normalize korelasyon 0.90440–0.99765. Tam doğrulama: `C:\Cihan.Ai\.scratch\yayin-klip\konusma-nihai-kontrol.json`. Eski `klip-*`, ilk `konusma-*` ve ara doğrulama varyantları silinmedi; incelemede yukarıdaki altı **konusma-hizali** dosyasını kullanın.

## Cümle sınırı kanıtı

ASR saati tek başına kabul edilmedi: gerçek kodlanmış klibin başı/sonu, ASR’nin dinlediği WAV ile eşleşti. Ayrıca MP4’ün ilk/son 5 sn sesi bağımsız döküldü; aşağıdaki bir saniyelik parçalar bunun içinden alınmıştır.

| Klip | İlk 1 sn / ilk tam cümle | Son 1 sn / son tam cümle |
|---|---|---|
| Kemalcan nihai 01 | “Bak” / “Bak bunların karnavalı görüyor musunuz?” | “ama nakoyemi” (bağımsız ASR yazımı belirsiz) / “…ev oyuncak doldu…” |
| Eray ek patates klibi | “Ben sakin” / “Ben sakin bir şekilde sohbet muhabbet eşliğinde patates soymak istiyorum.” | “Gayet iyiyim.” / “Gayet iyiyim.” |

İkinci kanıt klibi `C:\Cihan.Ai\.scratch\yayin-klip\cikti\eraycan-20261112-d38999bc\konusma-ek-patates.mp4`: ilk taramada bulundu, son ilk üç sıralamasında değil; ses/ölçüm kanıtı için ayrıca korundu. Kanıt JSON’ları `konusma-sinir-son.json` ve `konusma-sinir-eray.json`. Noktalama ve bazı kelimeler ASR tahmini; %100 dilsel doğruluk iddiası yok.

## Ölçümler

| Aynı 600 sn gerçek ses | Döküm | Yükleme | Hız | Toplam tepe VRAM |
|---|---:|---:|---:|---:|
| Turbo GPU int8_float16 | 34.141 sn | 9.406 sn | 17.57× | 3116 MiB (önce 722) |
| Small GPU int8_float16 | 46.969 sn | 6.281 sn | 12.77× | 2540 MiB |
| Small CPU int8, 4 iş parçacığı | 131.671 sn | 7.407 sn | 4.56× | CPU işi; eşzamanlı diğer GPU işi yüzünden toplam VRAM kıyası yok |

15 cümle/ifade metin üzerinden yan yana incelendi; Turbo daha okunaklı ve hızlı, fakat onda da isim/kelime hataları var. Elle dinlenmiş referans veya WER ölçümü yapılmadı. Gerçek tam dökümlerde toplam GPU belleği en çok Kemalcan’da 3180, Eray’da 3930 MiB görüldü; bunlar yalnız ASR tahsisi değil tüm GPU kullanımıdır.

VRAM, NVIDIA-SMI ile 1 sn aralıkla örneklendi; değerler örneklenen en yüksek toplam kullanımdır. CPU hızı Windows’taki bu koşulun ölçümüdür, ARM sunucu hızına genellenmez.

| Tam VOD | ASR / model yükleme / ses indirme süreleri toplamı | Dil modeli |
|---|---|---|
| Kemalcan, 139 dk | 302.359 / 197.297 / 240.843 sn; soğuk ASR duvar 834.031 sn | *eski (240 sn pencere)*: 81 çağrı, 1473.532 sn; analiz+ilk kesim 1520.157 sn (ASR önbellekte). *Güncel (1200 sn, toplu)*: 9 çağrı, 361.9 sn |
| Eray, 155 dk | son geçerli parçalarda 376.174 / 224.526 / 31.701 sn; tek kesintisiz soğuk yeniden ölçüm yok | *eski*: ilk tam tarama 95 çağrı / 1622.329 sn; bunun 36 çağrısı diğer VOD’la eşzamanlı yapıldı. *Güncel*: 12 çağrı, 344.4 sn |

Eray ilk 40 dk güvenli yolla yenilendikten sonra yalnız değişen pencereler yeniden değerlendirildi: 27 ek çağrı / 573.376 sn; gerçek standart `kes --konusma` turu 631.188 sn ve üç çıktı. Tekrar `kes --konusma` 1.750 sn sürdü, MP4 değişim saatlerinin üçü de aynı kaldı: yeniden döküm/model/kodlama yapılmadı.

2 saat için bu gerçek 139/155 dk koşularından **yaklaşık 31–35 dk** GPU ASR + Sonnet + üç klip üretimi öngörülür; ayrı tam soğuk 120 dk koşusu yapılmadı, model/bağlantı yükü değişebilir. 160p gerçek örnek trafik 608.333 sn için 22,065,560 bayt; 2 saat bağlam/segment kenarlarıyla yaklaşık **0.29–0.30 GB** ASR medya indirmesi, ayrıca normal HD klip indirmesi. WAV önbelleği 16 kHz mono PCM; ilk model/CUDA paket indirmeleri bu hesaba dahil değil.

Canlı: gerçek kanal kontrolü 3.047 sn, beş kanal da kapalı. **Gerçek canlıda denenmedi.** Kayıtlı Kemalcan’ın ilk 3000 sn’siyle benzetim: 14 ASR parçası, 90.502 sn döküm + 122.000 sn model yükleme + 9.686 sn ses indirme; 8 yargı çağrısı / 135.437 sn; ilk tur kesimle **442.453 sn (7 dk 22 sn)**. İkinci tur kota dolu / 0 sn, tekrar kesim yok. Model/ASR/kesim/kilit gerçektir; yalnız VOD keşfi ve sohbet sayfalaması kayıtlı veriye çevrildi. Sonraki sınır/hiza doğrulama işlemleri ilk tur süresine eklenmedi.

Güncel son kodla yeni test durum dizininde, aynı gerçek ASR/yargı önbelleği kullanılarak canlı benzetimi yeniden çalıştı: **16.625 sn**, 14 parça önbellekten, 0 yeni model çağrısı, sesin başı/sonu doğrulanmış bir klip; ikinci tur yine 0 sn ve yeni kesim yok. Kanıt: `konusma-canli-son-benzetim.json`.

Canlıda yeni bölümü tam tarama eklenmedi: aday yokken mevcut yol sıfır ASR/model çağrısı yapar. Beş kanalı her5dk zorunlu taramak, tek pencereyle bile en az60, örtüşen tam kapsamayla yaklaşık120 ek Sonnet çağrısı/saat demektir (hesap, gerçek canlı ölçümü değil; **eskidi**: 240 sn pencereye göre. 1200 sn pencere ve toplu yargıyla 2 saatlik yayın ≈9–13 çağrı ölçüldü, canlı için yeniden hesaplanmadı). Yargı kalitesi sınırlı, mevcut ücretsiz yol kotada ve soğuk aday turu7:22 sürdüğü için bu sürekli ek yük ucuz kabul edilmedi.

## Sınırlar ve test sonucu

Yerel Gemma/Qwen yeterli görülmedi. Sonnet, önceki sekiz etiketin puan bandıyla yalnız 4/8 örtüştü; düşük kaliteli ve sınırda öneri hâlâ gelebilir. Bu yüzden varsayılan kapalı ve çıktılar inceleme paketidir. Big Pickle 429 kota verdi; mevcut Haiku fazla muhafazakâr kaldı. Görsel espri, üst üste konuşma, ASR kelime/özne hatası ve chat gecikmesi belirsizliktir. Bir FPS adayının son ses korelasyonu güvenilir çıkmadı; nihai listeden çıkarıldı. Sorunun eski önbellekten kaynaklandığı kanıtlanmadı; güvenli sesin yeniden alınmasıyla tek başına düzelmedi, eşik düşürülmedi. ARM sunucuya kurulum yapılmadı; Windows CPU yolu çalıştırıldı, ARM bağımlılıkları denenmedi.

Ses olayı denemesinde 10 etiket: iyi anların ortalama RMS tepe z’si 0.56, zayıfların 0.66; z≥1 hiçbir iyiyi bulmayıp bir zayıfı buldu. Kahkaha/ses sıçraması aday üreticisi **eklenmedi**.

`py -m unittest discover -s tests -p "test_yayin_klip.py"`: **138 test, 4.295 sn, son satır `OK`** (2026-11-18, YouTube devrinden sonra).

`py -m unittest discover -s tests -p "test_klip_konusma.py"`: **44 test, 0.233 sn, son satır `OK`**.

`py -m unittest discover -s tests -p "test_klip_youtube.py"`: **21 test, 0.018 sn, son satır `OK`**.

`py -m unittest discover -s tests -p "test_*klip*.py"` (derleme testleri dahil): **404 test, ~20 sn, son satır `OK`** (2026-11-18, açıklama görünümü yenilemesi sonrası; önceki ölçüm 353).

Kick/konuşma/YouTube üç dosyada toplam **203 test geçti** (eski ölçüm: 174). Derleme kontrolü (`py_compile`) ve yalnız altı görev dosyasında `git diff --check` geçti. `--konusmasiz` gerçek iki VOD’da eski 22:00/44:10/1:33:10 ve 13:30/31:50/49:50 listelerini verdi; gerçek `yogunluk` 6:20/40:50/1:33:10 listesini verdi.


<!-- KONUSMA-SON-OLCUM-END -->

## Paylaşım (onay kapılı; 2026-11-18)

Karar (Cio): klipler ayrı kanalda değil, mevcut CTRL+A GAME hesaplarında (Instagram Reels + YouTube Shorts) paylaşılır. **Onaysız hiçbir klip paylaşılmaz.**

Akış:

1. **Üret (bilgisayar):** `yayin_klip.py` / `klip_youtube.py` klip paketlerini, `klip_derleme.py` 16:9 derlemeyi üretir (bu belgenin üst bölümleri).
2. **Listele (bilgisayar):** `py tools/klip_yayin.py liste` → tek sayfa `.scratch\yayin-klip\onay\index.html` (oynatıcı, başlık/açıklama, kaynak, döküm, uyarılar: küfür, 1080p değil, döküm yok). Numaralar kalıcıdır.
2b. **Butonlu onay sayfası (komut yazmadan):** `.scratch\yayin-klip\onay\Onay Sayfası.bat` dosyasına çift tıkla (ya da `py tools/klip_yayin.py sayfa [--kapi 8765] [--acma]`; `--acma` tarayıcıyı AÇMAZ, adresi yazar). Yalnız `127.0.0.1`'de çalışan küçük yerel sunucudur: her kartta **Onayla** / **Onayı geri al** düğmesi (derlemede önce küçük resme tıklanır), sayfa yenilenmeden durum güncellenir, hata kartın yanında Türkçe yazar, üstte "kaç onaylı / kaç yüklenmeyi bekliyor" özeti vardır. Durum değiştiren istekler POST + sayfaya gömülü rastgele belirteç + Origin/Host denetimi ister; dosya sunumu yalnız çalışma dizinindeki video/resimlerle sınırlıdır. **Onay yalnız işaretler; yükleme ve paylaşım ayrı adımdır** (sunucu yükleme, commit, push yapmaz). Kapı doluysa sıradaki boş kapı kullanılır. Pencereyi kapatınca sunucu durur. Durağan `liste` sayfası (`index.html`) aynen çalışır; komut satırındaki `onayla`/`geri-cek` aynı mantığı kullanır.
3. **Cio izler, karar verir.** Küfür uyarısı olanlar ve dökümü olmayanlar (konuşma denetlenemedi) kulakla dinlenir.
4. **Onayla (bilgisayar):** `py tools/klip_yayin.py onayla 3 7` (derleme için `--kucuk-resim 2`). Onay `data/klipler.json`a, paket+mp4 özetine bağlı yazılır; dosya sonradan değişirse onay düşer. Geri almak: `geri-cek 3`.
5. **Yükle (bilgisayar):** `py tools/klip_yayin.py yukle --kuru` (ne yükleneceğini gösterir), sonra `yukle`. 720/540/kapak ffmpeg ile üretilir, medya sunucusuna (`/var/www/medya/v/`, varsayılan hedef `oracle:` takma adı; `--hedef` ya da `KLIP_YUKLEME_HEDEFI` ile değişir) kopyalanır, manifestte "yayında" yazılır.
6. **Commit + push (bilgisayar, Cio onayıyla):** `data/klipler.json` depoya gider. Mp4'ler depoya girmez.
7. **Paylaş (GitHub Actions, `sosyal.yml`):** `sosyal_yayinla.py` yalnız `onay` + `yayinda` geçerli klipleri aday sayar. Reels + Shorts, yalnız Türkçe; derleme yalnız YouTube (normal video, `#Shorts` yok, bölüm zaman damgalı açıklama). Paylaşım bağlantıları `data/klipler.json`a ve kayıt `data/gonderilenler.json`a yazılır.

Sınırlar (`sosyal/ayarlar.json` → `klip`): platform başına günde 2 klip, derleme günde 1; `haber_varken_haber: true` iken paylaşılabilir haber adayı varsa sıra haberde; hesap başı genel günlük hak ayrıca geçerli; aynı klip aynı platforma iki kez gitmez; art arda iki klip gitmez (araya başka tür girer). Klipler haber sitesinde görünmez (ayrı manifest). YouTube: `containsSyntheticMedia: false`, kategori 20 (24 seçilebilir).

Bilinen sınırlar: Actions mp4'ü göremez, yalnız manifesti ve sunucudaki dosyaları; onay özeti bilgisayarda doğrulanır. Derleme üçüncü kişi videoları içerir (yeniden kullanım/telif riski Cio'nundur). Küfür denetimi sözlük tabanlıdır; dökümü olmayan klibi Cio dinler. Küçük resim yükleme kanal doğrulaması ister (reddedilirse video küçük resimsiz yayında kalır).
