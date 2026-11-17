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

`<vod>` olarak `kick:<uuid>`, çıplak uuid veya `https://kick.com/<kanal>/videos/<uuid>` verilir. `analiz` ve `kes` için `--esik-k`, `--min-mesaj`, `--min-oran`, `--azami-klip`, `--bas-dislama-sn`, `--min-farkli-kullanici`, `--min-emote-disi-oran`, `--duzen kadraj|serit`, `--kadraj-oran` ile o çalıştırmaya özel ayar verilir; `--yeniden` analizi önbellekten almaz, `--zorla` var olan klibi yeniden üretir, `--suzgecsiz` oyun süzgecine uymayan yayını da işler.

## Nasıl çalışır

1. Sohbet 10 sn'lik dilimlere sayılır. Eşik = en büyük( ortalama + `esik_k`·std, `min_mesaj`, `min_oran`·ortalama ). Yayının ilk 5 dk'sı (selamlaşma) ve son 3 dk'sı (veda/raid) sayılmaz.
2. Eşiği geçen dilimler arasında `birlestir_sn` (30) veya daha az boşluk varsa tek klipte birleşir. Klip, ilk zirve diliminden **20 sn önce** başlar, son zirve diliminden 12 sn sonra biter; 30–55 sn arasında kalır (Shorts/Reels sınırı 60).
3. **Zayıf zirve elemesi** (seçimden önce): her zirvenin sohbeti iki ölçüyle bakılır: *kaç farklı kişi yazdı* (`min_farkli_kullanici`, 25) ve *emote olmayan mesaj oranı* (`min_emote_disi_oran`, 0.25; mesajdan `[emote:..]` atılınca boşluktan başka bir şey kalıyorsa emote dışıdır). Biri eşiğin altındaysa zirve elenir ve yerini sıradaki aday alır; elenenler analiz JSON'unda `elenen_zirveler` altında nedeniyle durur, seçilenlerde `farkli_kullanici` / `emote_disi_oran` yazar (paket JSON'unda `zirve_emote_disi_oran`).
4. Yayın başına en çok `azami_klip` (3) klip: puanı (zirve − ortalama)/std en yüksek olanlar, zamana göre sıralı.
5. `kes` yalnız klip aralığını HLS'ten çeker (tüm yayını indirmez), 1080x1920 H.264+AAC yapar. İki düzen var (`duzen` ayarı):
   - **kadraj** (varsayılan): yayın ortadan kırpılır (`kadraj_oran` 1.2 ⇒ 1080x900 görüntü; 1.0 kare, 4/3 ⇒ 1080x810, 1.78 ⇒ kırpma yok) ve tam genişlikte, orta çizgisi y=880'de durur. Arkada bulanık kopya; yazılar görüntünün **dışında**: üstte yayıncı adı + oyun, altta "Kaynak: kick.com/<kanal>" ve marka; hiçbiri görüntünün üstüne binmez (testle güvenceli, yazı yeri görüntü yüksekliğine göre hesaplanır).
   - **serit** (eski): tam genişlikte 16:9 şerit (1080x608), üst/altı bulanık.
   Düzen `tools/yayin_klip.py` içindeki `DUZEN` sözlüğünde. Düzen ya da klip penceresi değişince `kes` var olan klibi kendiliğinden yeniden üretir (paketteki `duzen` imzası ve klip aralığı karşılaştırılır).
6. Sohbet–video hizası: yayının gerçek başlangıcı HLS listesindeki ilk `PROGRAM-DATE-TIME`'dan alınır (API'deki `start_time` 3–6 sn geç kalıyor).

### Eleme ölçümü (gerçek veri)

Kemalcan Parlak yayını (`kick:9ae47b40-…`, 2026-11-15, 139 dk), eşikler 25 kişi / 0.25:

| Zirve | Mesaj | Farklı kişi | Emote dışı oran | Sonuç |
|---|---|---|---|---|
| 6:20 (eski klip-01) | 384 | 145 | 0.797 | kaldı |
| 8:20 (eski klip-02) | 162 | 83 | 0.142 | **elendi** (emote ağırlıklı) |
| 40:50 (eski klip-03) | 105 | 87 | 0.952 | kaldı |
| 32:40 | 42 | 37 | 0.238 | elendi (sınırda) |
| 1:33:10 | 62 | 46 | 0.306 | kaldı, elenenin yerine 3. klip oldu |

Eşikler tek yayına bakılarak seçildi; farklı kişi sayısı tek başına 8:20'yi (83) ve 40:50'yi (87) ayırmaz, ayıran emote dışı orandır. 6:20 ve 40:50 "1/2" gibi tek karakterli oylardır: ölçüt bunları yazı sayar (yalnız `[emote:..]` seli elenir). 0.25 sınırı 32:40'a çok yakın; gerekirse `min_emote_disi_oran` yayıncı bazında ayarlanır.

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
- Sohbeti olmayan/çok seyrek yayınlarda zirve çıkmaz (klip üretilmez). Sesin yükselmesine dayalı yedek yöntem düşünülebilir; yazılmadı.
