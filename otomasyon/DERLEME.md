# Derleme aracı (`tools/klip_derleme.py`)

Türk yayıncıların Kick kesitlerinden ve viral kısa videolardan 10–12 dk'lık, 1920x1080 yatay, sesli YouTube **derleme videosu** üretir.
Yalnız paket üretir: hiçbir yere yüklemez, sosyal kuyruğa kayıt eklemez. Ayar: `otomasyon/derleme.json`. Testler: `tests/test_klip_derleme.py`.

## Komutlar (hepsi `tools/` içinden, `py` ile)

```
py klip_derleme.py topla  [--gun 7] [--kaynaklar paket,izleyici,viral] > adaylar.json   # aday listesi, indirmez
py klip_derleme.py uret   [--sure-dk 11] [--yalniz-yayinci] [--viral-oran 2] [--kuru]  # seç, indir/kes, tek mp4
py klip_derleme.py uret   --adaylar-dosyasi adaylar.json                               # toplamayı atla
py klip_derleme.py dogrula <derleme-klasoru>                                           # ölçüm + kare çıkarma
```
`--kuru`: yalnız plan (indirme/kodlama yok). `--zorla`: önceki parça dosyalarını yeniden üret. Kodlama yalnız CPU (libx264); GPU/NVENC kullanılmaz.

## Ne yapar

1. **Toplar** (3 kaynak): (a) `paket` — `tools/yayin_klip.py` paketleri (`cikti/*/klip-NN|canli-NN.json`); aynı aralık Kick HLS'ten **yatay** yeniden kesilir, yayın kalkmışsa dikey mp4'e düşülür; (b) `izleyici` — Kick izleyici klipleri `/api/v2/channels/<kanal>/clips?sort=view&time=…`; (c) `viral` — elle `ara-videolar/`, ayardaki bağlantılar, YouTube Shorts (yt-dlp).
2. **Süzer**: gün/izlenme/süre, kopya, aynı yayının örtüşen aralığı (`#EXT-X-PROGRAM-DATE-TIME` ile), daha önce kullanılmış video (`.scratch/yayin-klip/derleme/durum.json`).
3. **Planlar**: teaser (en iyi 2 andan 2'şer sn) → giriş kartı → döngü (1 yayıncı kesiti + `yayinci_basina_viral` viral) → kapanış kartı. Viral yoksa yalnız yayıncı/izleyici klibiyle de çıkar. Doğrudan kesme.
4. **Hazırlar**: her parça 1920x1080/30 fps/48 kHz stereo, iki geçişli loudnorm (−16 LUFS); dikey video yatay tuvalde kendi bulanık kopyası üstünde ortalı; köşede yarı saydam filigran; yayıncı kesitinde sol altta ilk 3 sn kaynak etiketi (Türkçe karakter doğru).
5. **Birleştirir** (concat demuxer, yeniden kodlama yok) ve yazar.

Çıktı: `.scratch/yayin-klip/derleme/<seri>-<sayı>/` → `derleme.mp4`, `derleme.json` (parça listesi, başlık, açıklama, `yayinlandi: false`, uyarılar, elenenler, ölçüm), `aciklama.txt` (yayıncı bağlantıları + zaman damgalı bölümler + her videonun kaynağı), `liste.txt`, `kucuk-resim-1..3.png` (en iyi 3 andan), `parcalar/`; `dogrula` ayrıca `dogrulama.json` ve `kareler/` yazar.
Başlık: `<BÜYÜK HARF OLAY> | <Seri Adı> #<Sayı>`. Seri sayısı `durum.json`da artar.

## Sıra kuralı
Değer: paket zirve puanı/100; izleyici ve viral için log izlenme (izleyici × `izleyici_agirlik` 0.75). En iyi parça başa, ikinci en iyi sona; aynı yayıncı art arda gelmez (önce orta takasla giderilir; yetmezse uyarı verilir).

## Ayarlar (`derleme.json` → `ayar`; yazılmayan koddaki varsayılanı alır)

| Ayar | Varsayılan | Anlam |
|---|---|---|
| `seri_adi`, `filigran_yazi` | Yayın Kolajı, CTRL+A GAME | başlık serisi, köşe yazısı |
| `sure_dk` / `sure_min_dk` / `sure_max_dk` | 11 / 10 / 12 | hedef ve sınırlar |
| `yayinci_basina_viral` | 2 | döngüde yayıncı kesiti başına viral sayısı (0 = yalnız yayıncı) |
| `viral_dolgu` | true | kesit bitince bütçeyi viralle doldur |
| `kesit_min/hedef/max_sn` | 12 / 22 / 28 | yayıncı kesiti süresi |
| `viral_min_sn` / `viral_max_sn`, `viral_uzun` | 5 / 15, `ele` | viral süre sınırı; uzunsa ele (`kirp` ilk kısmı alır) |
| `viral_min_izlenme`, `viral_gun` | 100000, 90 | Shorts süzgeci |
| `gun` | 7 | yayıncı kesiti/izleyici klibi yaş sınırı |
| `izleyici_min_izlenme`, `izleyici_max_sn`, `izleyici_uzun` | 5, 60, `kirp` | izleyici klibi süzgeci |
| `ses_hedef_lufs` | −16 | loudnorm hedefi |
| `ek_kick_kanallari`, `baglantilar`, `ara_video_klasoru`, `shorts_kaynaklari` | | ek kaynaklar |

## Elle viral video
`C:\Cihan.Ai\.scratch\yayin-klip\ara-videolar\` içine mp4 bırak (varsayılan klasör) veya `baglantilar` listesine bağlantı ekle; elle seçilenlere izlenme/tarih süzgeci uygulanmaz.

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
