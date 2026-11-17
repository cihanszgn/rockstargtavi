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

`<vod>` olarak `kick:<uuid>`, çıplak uuid veya `https://kick.com/<kanal>/videos/<uuid>` verilir. `analiz` ve `kes` için `--esik-k`, `--min-mesaj`, `--min-oran`, `--azami-klip`, `--bas-dislama-sn` ile o çalıştırmaya özel ayar verilir; `--yeniden` analizi önbellekten almaz, `--zorla` var olan klibi yeniden üretir.

## Nasıl çalışır

1. Sohbet 10 sn'lik dilimlere sayılır. Eşik = en büyük( ortalama + `esik_k`·std, `min_mesaj`, `min_oran`·ortalama ). Yayının ilk 5 dk'sı (selamlaşma) ve son 3 dk'sı (veda/raid) sayılmaz.
2. Eşiği geçen dilimler arasında `birlestir_sn` (30) veya daha az boşluk varsa tek klipte birleşir. Klip, ilk zirve diliminden **20 sn önce** başlar, son zirve diliminden 12 sn sonra biter; 30–55 sn arasında kalır (Shorts/Reels sınırı 60).
3. Yayın başına en çok `azami_klip` (3) klip: puanı (zirve − ortalama)/std en yüksek olanlar, zamana göre sıralı.
4. `kes` yalnız klip aralığını HLS'ten çeker (tüm yayını indirmez), 1080x1920 H.264+AAC yapar. Düzen: bulanık arka plan (üst/alt), tam genişlikte video ortada, üstte yayıncı adı + oyun, altta "Kaynak: kick.com/<kanal>" ve marka. Düzen `tools/yayin_klip.py` içindeki `DUZEN` sözlüğünde tek yerde.
5. Sohbet–video hizası: yayının gerçek başlangıcı HLS listesindeki ilk `PROGRAM-DATE-TIME`'dan alınır (API'deki `start_time` 3–6 sn geç kalıyor).

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

## Dosyalar (hepsi depo dışında)

Taban klasör: Windows `C:\Cihan.Ai\.scratch\yayin-klip\`, Linux `~/.local/share/yayin-klip/`; `YAYIN_KLIP_DIZIN` ortam değişkeni veya `--dizin` ile değişir.

- `durum.json`: işlenmiş yayınlar (`kes` bitince `islendi`). `tara` bunları atlar.
- `sohbet/`: indirilen sohbet (yarım kalırsa `.part.jsonl`'den devam eder).
- `analiz/`: zirve JSON'u. `cikti/<yayinci>-<tarih>-<kısa id>/klip-NN.mp4` + `klip-NN.json` (yayıncı, platform, VOD ve zaman damgalı bağlantı, oyun, puan, önerilen başlık ve açıklama; açıklama yayıncıyı anar ve kanalına bağlanır; `yayinlandi: false`).

Başlık ve açıklama sabit şablonlardan gelir (model çağrısı yok).

## Platform durumu

| Platform | Sohbet | Video | Durum |
|---|---|---|---|
| Kick | evet (`/api/v2/channels/<id>/messages`) | evet (HLS, ffmpeg) | çalışıyor; giriş/anahtar istemiyor |
| Twitch | — | — | desteklenmiyor: listedeki yayıncıların kayıtlı yayını (VOD) yok (2026-11-17) |
| YouTube | — | — | desteklenmiyor: yazılmadı/denenmedi (yt-dlp `live_chat` ile eklenebilir) |

Desteklenmeyen platformdaki yayıncı `tara`'da `desteksiz` altında nedeniyle raporlanır, diğerleri sürer.

Kick sohbet sınırları: pencere başına 25 mesaj (araç kalanı devam sorgusuyla alır), saniye çözünürlüğü, hız sınırı (429). Araç istekleri ortak bir hız sınırıyla gönderir (`KLIP_ISTEK_ARALIK`, varsayılan 0.4 sn; 4 paralel + sınırsız hızda Kick 429 verdi; 429 gelirse bekleyip tekrar dener). Ölçüm: 139 dk'lık yayın (1583 pencere) ~12 dk; 6 saatlik yayın ~4300 pencere ≈ 30–40 dk. Linux sunucudaki (veri merkezi IP'si) Kick erişimi **denenmedi**; 403 gelirse araç "desteklenmiyor: bot koruması" der.

## ffmpeg, yt-dlp, yazı tipi

- **ffmpeg** aranma sırası: `FFMPEG` ortam değişkeni → PATH'teki `ffmpeg` (drawtext ve gblur süzgeçleri varsa) → `imageio-ffmpeg` paketinin ffmpeg'i. Kurulum (kullanıcı düzeyi): `py -m pip install --user imageio-ffmpeg`; Linux'ta `apt install ffmpeg` (libfreetype'lı). Remotion'un kırpılmış ffmpeg'i kullanılmaz.
- **yt-dlp** Kick için gerekmez (ffmpeg HLS'i doğrudan okur). Yalnız ileride YouTube eklenirse lazım (`py -m pip install --user yt-dlp`).
- **ffprobe** yok; klip doğrulaması `ffmpeg -i` çıktısından yapılır (1080x1920, ≤60 sn, ses var; değilse klip reddedilir).
- **Yazı tipi:** `KLIP_FONT` → Windows `arialbd.ttf`/`segoeuib.ttf` → Linux DejaVuSans-Bold/LiberationSans-Bold/NotoSans-Bold (`apt install fonts-dejavu-core`).

## Bilinen belirsizlikler

- Kick VOD adresine `?t=<sn>` eklemek belgelenmemiş; paket JSON'unda `vod_zaman_damgali_url_dogrulandi: false`. Açıklamada güvenli olan "yayının M:SS noktası" yazısı kullanılır.
- Yayıncıların görüntüsünü yeniden paylaşmanın izin/telif durumu araçtan bağımsız bir karardır: yayınlamadan önce yayıncılardan izin alınması önerilir.
- Sohbeti olmayan/çok seyrek yayınlarda zirve çıkmaz (klip üretilmez). Sesin yükselmesine dayalı yedek yöntem düşünülebilir; yazılmadı.
