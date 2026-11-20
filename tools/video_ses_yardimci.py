"""Seslendirme yardımcısı: metni sese çevirir ve kelime sınırlarını yazar.

tools/video_uret.py bunu `uv run --no-project --with <paket> python -I` ile çağırır; böylece edge-tts ya da Azure
SDK'sı proje ortamına kurulmaz. Metin dosyadan okunur (kabuğa hiç girmez), çıktı iki dosyadır:
    py video_ses_yardimci.py <edge|azure> girdi.json ses.mp3 olaylar.json
    py video_ses_yardimci.py tani girdi.json ses.wav olaylar.json     (kelime sınırı vermeyen sesler için)
girdi.json: {"metin", "konusmaci", "hiz", "dil"} ya da tani için {"dil"};
olaylar.json: {"olaylar": [{"metin", "bas", "sure"}]} (100 ns birim).
"""
import asyncio
import json
import os
import re
import sys
from xml.sax.saxutils import escape

TIK = 10_000_000  # saniyedeki 100 ns sayısı
_XML_KONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_DIK_CIZGI = re.compile(r"\s*\|\s*")


def _yaz(yol, deger):
    with open(yol, "w", encoding="utf-8", newline="\n") as f:
        json.dump(deger, f, ensure_ascii=False, indent=1)
        f.write("\n")


async def _edge(girdi, ses_yolu):
    import edge_tts

    iletisim = edge_tts.Communicate(girdi["metin"], girdi["konusmaci"], rate=girdi.get("hiz", "+0%"),
                                    boundary="WordBoundary")
    olaylar = []
    with open(ses_yolu, "wb") as ses:
        async for parca in iletisim.stream():
            if parca["type"] == "audio":
                ses.write(parca["data"])
            elif parca["type"] == "WordBoundary":
                olaylar.append({"metin": parca["text"], "bas": int(parca["offset"]), "sure": int(parca["duration"])})
    return olaylar


def edge(girdi, ses_yolu):
    return asyncio.run(_edge(girdi, ses_yolu))


def _ssml_metin(metin):
    """Azure MAI-Voice-2.1 `|` (ör. 'Xbox Series X|S') karakterinde 1007/invalid_request veriyor;
    okunuşu bozmadan boşluğa çevrilir, XML 1.0 dışı kontrol karakterleri temizlenir."""
    temiz = _XML_KONTROL.sub("", str(metin))
    return _DIK_CIZGI.sub(" ", temiz)


def ssml(girdi):
    dil = girdi.get("dil") or girdi["konusmaci"][:5]
    return (f"<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='{escape(dil)}'>"
            f"<voice name='{escape(girdi['konusmaci'])}'><prosody rate='{escape(girdi.get('hiz', '+0%'))}'>"
            f"{escape(_ssml_metin(girdi['metin']))}</prosody></voice></speak>")


def _tik(deger):
    """SDK süreyi timedelta, konumu 100 ns tamsayı verir."""
    if hasattr(deger, "total_seconds"):
        return int(round(deger.total_seconds() * TIK))
    return int(deger)


def azure(girdi, ses_yolu, sdk=None):
    if sdk is None:
        import azure.cognitiveservices.speech as sdk
    anahtar, bolge = os.environ.get("AZURE_SPEECH_KEY"), os.environ.get("AZURE_SPEECH_REGION")
    if not anahtar or not bolge:
        raise SystemExit("AZURE_SPEECH_KEY ve AZURE_SPEECH_REGION gerekli")
    ayar = sdk.SpeechConfig(subscription=anahtar, region=bolge)
    ayar.set_speech_synthesis_output_format(sdk.SpeechSynthesisOutputFormat.Audio24Khz96KBitRateMonoMp3)
    sentez = sdk.SpeechSynthesizer(speech_config=ayar, audio_config=sdk.audio.AudioOutputConfig(filename=ses_yolu))
    olaylar = []

    def sinir(olay):
        tur = str(getattr(olay, "boundary_type", "Word"))
        if tur.endswith("Word") or tur == "Word":
            olaylar.append({"metin": olay.text, "bas": _tik(olay.audio_offset), "sure": _tik(olay.duration)})

    sentez.synthesis_word_boundary.connect(sinir)
    sonuc = sentez.speak_ssml_async(ssml(girdi)).get()
    if sonuc.reason != sdk.ResultReason.SynthesizingAudioCompleted:
        ayrinti = getattr(sonuc, "cancellation_details", None)
        neden = getattr(ayrinti, "error_details", "") or getattr(ayrinti, "reason", "") or sonuc.reason
        raise SystemExit(f"Azure seslendirme başarısız: {neden}")
    # MAI-Voice sesleri (ör. tr-TR-Aydin:MAI-Voice-2.1) hiç kelime sınırı göndermiyor (ölçüm 2026-11-16); boş liste
    # dönünce video_uret zamanları sesin kendisinden `tani` ile çıkarır.
    return olaylar


def tani(girdi, wav_yolu, sdk=None, bekleme=600):
    """Azure konuşma tanıma: WAV'daki her kelimenin sesteki başı ve süresi (100 ns).

    Kelimeler sözlü biçimde gelir (1 → "bir"); video_uret bunları bilinen anlatıma harf düzeyinde eşler. Tanıyıcıya
    anlatımdan ipucu listesi verilmez: denemede (2026-11-16) ipucu, sözleri rakam ve birleşik ifade olarak döndürüp
    kelime başlarını 0,5 sn'ye kadar kaydırdı; ipucusuz tanımada yanlış duyulan adlar yalnız eşleşmeyen harf kalıyor."""
    if sdk is None:
        import azure.cognitiveservices.speech as sdk
    import threading

    anahtar, bolge = os.environ.get("AZURE_SPEECH_KEY"), os.environ.get("AZURE_SPEECH_REGION")
    if not anahtar or not bolge:
        raise SystemExit("AZURE_SPEECH_KEY ve AZURE_SPEECH_REGION gerekli")
    ayar = sdk.SpeechConfig(subscription=anahtar, region=bolge)
    ayar.speech_recognition_language = girdi["dil"]
    ayar.request_word_level_timestamps()
    ayar.output_format = sdk.OutputFormat.Detailed
    tanici = sdk.SpeechRecognizer(speech_config=ayar, audio_config=sdk.audio.AudioConfig(filename=wav_yolu))
    olaylar, hatalar, bitti = [], [], threading.Event()

    def tanindi(olay):
        if olay.result.reason != sdk.ResultReason.RecognizedSpeech:
            return
        en_iyi = (json.loads(olay.result.json).get("NBest") or [{}])[0]
        for k in en_iyi.get("Words") or []:
            olaylar.append({"metin": k["Word"], "bas": int(k["Offset"]), "sure": int(k["Duration"])})

    def iptal(olay):
        ayrinti = olay.cancellation_details
        if ayrinti.reason != sdk.CancellationReason.EndOfStream:
            hatalar.append(f"{ayrinti.reason} {ayrinti.error_details}")
        bitti.set()

    tanici.recognized.connect(tanindi)
    tanici.canceled.connect(iptal)
    tanici.session_stopped.connect(lambda olay: bitti.set())
    tanici.start_continuous_recognition()
    tamam = bitti.wait(bekleme)
    tanici.stop_continuous_recognition()
    if hatalar:
        raise SystemExit(f"Azure konuşma tanıma başarısız: {hatalar[0]}")
    if not tamam:
        raise SystemExit(f"Azure konuşma tanıma {bekleme} sn içinde bitmedi")
    return sorted(olaylar, key=lambda o: o["bas"])


SAGLAYICILAR = {"edge": edge, "azure": azure, "tani": tani}


def main(argv):
    if len(argv) != 4 or argv[0] not in SAGLAYICILAR:
        raise SystemExit("kullanım: video_ses_yardimci.py <edge|azure> girdi.json ses.mp3 olaylar.json\n"
                         "          video_ses_yardimci.py tani girdi.json ses.wav olaylar.json")
    saglayici, girdi_yolu, ses_yolu, olay_yolu = argv
    with open(girdi_yolu, encoding="utf-8") as f:
        girdi = json.load(f)
    olaylar = SAGLAYICILAR[saglayici](girdi, ses_yolu)
    if not olaylar and saglayici != "azure":
        raise SystemExit("kelime sınırı gelmedi" if saglayici == "edge" else "seste kelime tanınmadı")
    _yaz(olay_yolu, {"saglayici": saglayici, "konusmaci": girdi.get("konusmaci", ""), "olaylar": olaylar})


if __name__ == "__main__":
    main(sys.argv[1:])
