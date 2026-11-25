#!/usr/bin/env python3
"""Sosyal paylaşım: data/icerik.json'daki yeni haberleri X, Reddit, Instagram (görsel + Reels) ve YouTube Shorts'a gönderir.

Tek hesap, çok dil: ayardaki `hesap_esleme.<platform>.<dil>` yabancı dilin hangi hesaptan çıkacağını söyler
(şimdi hepsi TR hesabı: IG_TR_*, YT_TR_*). Dilin kendi anahtarları girilirse o dil kendi hesabına döner. Yabancı dil
yalnız `ortak_hesap_bicimleri` (reel, short) ile çıkar; günlük sınır hesap başınadır, Türkçe payı `ana_dil_en_az`,
yabancı dil sırası `hesap_dil_sirasi` ile döner. Hesap anahtarları yoksa o hesap atlanır ("anahtar yok, atlandı"
diye çıktıda görünür); anahtarlar eklenince paylaşım kod değişmeden başlar.
Anahtarlar ortam değişkeninden okunur (GitHub Actions: her sır adıyla env olarak verilir).
Görsel gönderi her haberde, Reels ve Shorts yalnız hype puanı sosyal/ayarlar.json video.hype_esigi ve üstündeki
haberde gider (puanı olmayan eski haberde: manifestte video varsa gider).

  python tools/sosyal_yayinla.py --dry-run     # ne paylaşılacağını gösterir, hiçbir ağ çağrısı yapmaz, dosya yazmaz;
                                               # anahtarı olmayan hesap "anahtar yok, atlandı" diye listelenir
  python tools/sosyal_yayinla.py --dry-run --anahtarsiz-goster   # anahtarı olmayan hesapların planını da göster
  python tools/sosyal_yayinla.py               # gerçekten paylaşır, sosyal/gonderilenler.json'a yazar
  python tools/sosyal_yayinla.py --selftest    # OAuth imzası, kayıt göçü, metin sınırları sınanır (ağ yok)

Çift paylaşım koruması: kayıt anahtarı  <konu ya da id>|<dil>|<platform>|<biçim>  (biçim: gorsel | reel | short).
Her paylaşımdan ÖNCE kayda "niyet" yazılır, kimlikler (Instagram kapsayıcı, YouTube yükleme oturumu) gelir gelmez
kaydedilir, iş bitince "tamam" olur. Yanıtı kaybolan (zaman aşımı) paylaşım bir sonraki çalışmada platformdan
sorgulanıp tamamlanır; sorgulanamıyorsa "elle_bak" işaretlenir ve ASLA kendiliğinden yeniden denenmez.

Gerekli sırlar (DIL = hesap dili; şimdi yalnız TR gerekir, EN/ES/FR yalnız ayrı hesap açılırsa):
  X_DIL_API_KEY, X_DIL_API_SECRET, X_DIL_ACCESS_TOKEN, X_DIL_ACCESS_SECRET
  REDDIT_DIL_CLIENT_ID, REDDIT_DIL_CLIENT_SECRET, REDDIT_DIL_USERNAME, REDDIT_DIL_PASSWORD
  IG_DIL_USER_ID, IG_DIL_TOKEN                      (görsel ve Reels için aynı hesap)
  YT_DIL_CLIENT_ID, YT_DIL_CLIENT_SECRET, YT_DIL_REFRESH_TOKEN
Klip/derleme (yayıncı klipleri) AYRI hesaba gider: DIL yerine KLIP (YT_KLIP_CLIENT_ID, YT_KLIP_CLIENT_SECRET,
YT_KLIP_REFRESH_TOKEN; Instagram açılırsa IG_KLIP_USER_ID, IG_KLIP_TOKEN). Bu sırlar yoksa klip hiçbir hesaba gitmez.
Yalnız Python standart kütüphanesi kullanılır.
"""
from __future__ import annotations

import argparse
import base64
import copy
from collections import Counter
import hashlib
import hmac
import json
import os
import pathlib
import re
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

KOK = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK / "tools"))
from sosyal_derle import DILLER, GORUNEN, KLASOR, M, SITE, kart_ad, kaynak_adi  # noqa: E402
import video_site as vs  # noqa: E402
import sosyal_kuyruk as sk  # noqa: E402
import sosyal_etiket as se  # noqa: E402
import klip_sosyal as ks  # noqa: E402

KAYIT = KOK / "sosyal" / "gonderilenler.json"
AYAR = KOK / "sosyal" / "ayarlar.json"
ICERIK = KOK / "data" / "icerik.json"
UA = "rockstargtavi-sosyal/1.0"
IG_ETIKET_SINIRI = 5  # Instagram Aralık 2025'ten beri gönderi/Reel başına en çok 5 hashtag kabul eder
YT_ACIKLAMA_ETIKET = 3  # açıklamadaki ilk 3 hashtag başlığın üstünde görünür
BICIMLER = ("gorsel", "reel", "short")
MAX_VIDEO_BAYT = 256 * 1024 * 1024
# Derleme (16:9, ~11 dk) 300-420 MB görüldü; YouTube yüklemesi baytları bellekte tutar (Actions 7 GB RAM): tavan yalnız derlemede 512 MB.
MAX_DERLEME_BAYT = 512 * 1024 * 1024
KLIP_TURLERI = ks.KLIP_TURLERI
KLIP_SINIR_VARSAYILAN = {"instagram_reel": 2, "youtube": 2}
# Klip/derleme AYRI hesaba gider: sır öneki YT_KLIP_* / IG_KLIP_*. Bu sırlar yoksa klip hiçbir hesaba gitmez
# (haber hesaplarına, CTRL+A GAME kanalına ya da başka dilin hesabına ASLA düşmez). "klip" bir dil değil, hesap adıdır.
KLIP_HESABI = "klip"
KLIP_ICERIK_DILI = "tr"  # klip metni onay anında saklanır, yalnız Türkçe
YT_KATEGORILER = ("20", "24")

from diller import alan, HREFLANG
METIN = alan('paylasim')


class PaylasimHatasi(Exception):
    """kesin=True: sunucu isteği açıkça reddetti (4xx), hiçbir şey yayımlanmadı, yeniden denenebilir.
    kesin=False: sonuç bilinmiyor (zaman aşımı, bağlantı kopması, 5xx); paylaşım yapılmış olabilir."""

    def __init__(self, mesaj: str, kesin: bool = False, kota: bool = False):
        super().__init__(mesaj)
        self.kesin = kesin
        self.kota = kota  # kota/yetki sorunu (YouTube günlük kotası, yetki reddi): hata değil "sonra denenir" durumu


def kota_mi(kod: int, metin: str) -> bool:
    """YouTube kota ya da yetki reddi mi? (403/401 ve gövdede kota/yetki işareti.) Başka 4xx'ler bunu ETKİLEMEZ."""
    m = (metin or "").lower()
    if kod == 400:
        return "invalid_grant" in m or "unauthorized_client" in m  # yenileme anahtarı iptal/süresi dolmuş
    if kod not in (401, 403):
        return False
    return any(a in m for a in ("quotaexceeded", "uploadlimitexceeded", "ratelimitexceeded", "dailylimitexceeded",
                                "insufficientpermissions", "forbidden", "invalid_grant", "unauthorized_client",
                                "autherror", "invalid credentials", "youtubesignuprequired", "channelsuspended"))


ENGEL_MOLA_SAAT = (6, 12, 24)  # art arda engelde mola uzar; başarılı paylaşımda sıfırlanır
_META_ENGEL = re.compile(r'"error_subcode"\s*:\s*(2207051|5258005|2207042)\b|request limit reached', re.I)


def meta_engel_mi(metin: str) -> bool:
    """Instagram/Meta hesabı ya da uygulamayı geçici kısıtladı mı? (eylem engellendi 2207051, API erişimi engellendi 5258005,
    yayın sınırı 2207042, istek sınırı.) Bu bizim hatamız değil: saat başı yeniden denemek engeli uzatır, mola verilir."""
    return bool(_META_ENGEL.search(metin or ""))


def engel_oku(yol: pathlib.Path) -> dict:
    try:
        v = json.loads(yol.read_text(encoding="utf-8"))
        return v if isinstance(v, dict) else {}
    except (OSError, ValueError):
        return {}


def engel_yaz(yol: pathlib.Path, engel: dict) -> None:
    yol.write_text(json.dumps(engel, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def engel_mola_ver(engel: dict, yol: pathlib.Path, anahtar: str, simdi: datetime, neden: str) -> int:
    """Hesabı molaya alır (art arda engelde 6/12/24 saat), dosyaya yazar ve mola saatini döndürür."""
    sayi = int((engel.get(anahtar) or {}).get("sayi", 0)) + 1
    saat = ENGEL_MOLA_SAAT[min(sayi, len(ENGEL_MOLA_SAAT)) - 1]
    engel[anahtar] = {"bitis": (simdi + timedelta(hours=saat)).isoformat(timespec="seconds"), "sayi": sayi,
                      "son": simdi.isoformat(timespec="seconds"), "neden": neden[-260:]}
    engel_yaz(yol, engel)
    return saat


def engel_molada_mi(engel: dict, anahtar: str, simdi: datetime) -> str:
    """Mola sürüyorsa bitiş zamanını (ISO), sürmüyorsa boş metin döndürür. Bozuk kayıt mola sayılmaz."""
    try:
        bitis = (engel.get(anahtar) or {}).get("bitis") or ""
        return bitis if bitis and simdi < datetime.fromisoformat(bitis) else ""
    except (TypeError, ValueError, AttributeError):
        return ""


# ---------------------------------------------------------------- HTTP (testte yerine sahte Ag konur)
class Ag:
    def istek(self, method: str, url: str, *, veri=None, json_govde=None, basliklar=None, zaman=30):
        basliklar = {"User-Agent": UA, **(basliklar or {})}
        govde = None
        if json_govde is not None:
            govde = json.dumps(json_govde).encode()
            basliklar["Content-Type"] = "application/json"
        elif veri is not None:
            govde = urllib.parse.urlencode(veri).encode()
            basliklar["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=govde, headers=basliklar, method=method)
        try:
            with urllib.request.urlopen(req, timeout=zaman) as r:
                ham = r.read().decode("utf-8", "replace")
                return r.status, (json.loads(ham) if ham.strip().startswith(("{", "[")) else ham)
        except urllib.error.HTTPError as h:
            ham = h.read().decode("utf-8", "replace")
            raise PaylasimHatasi(f"{method} {url.split('?')[0]} → HTTP {h.code}: {ham[:400]}", kesin=400 <= h.code < 500,
                                 kota=kota_mi(h.code, ham)) from None
        except (urllib.error.URLError, TimeoutError, OSError) as u:
            raise PaylasimHatasi(f"{method} {url.split('?')[0]} → bağlantı hatası: {getattr(u, 'reason', u)}") from None

    def ham(self, method: str, url: str, *, govde: bytes | None = None, basliklar=None, zaman=300):
        """Başlıkları da döndürür; 308 (yükleme sürüyor) hata sayılmaz. -> (durum, {küçük harfli başlıklar}, metin)"""
        req = urllib.request.Request(url, data=govde, headers={"User-Agent": UA, **(basliklar or {})}, method=method)
        try:
            with urllib.request.urlopen(req, timeout=zaman) as r:
                return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as h:
            metin = h.read().decode("utf-8", "replace")
            if h.code == 308:
                return 308, {k.lower(): v for k, v in h.headers.items()}, metin
            raise PaylasimHatasi(f"{method} {url.split('?')[0]} → HTTP {h.code}: {metin[:400]}", kesin=400 <= h.code < 500 and h.code != 404,
                                 kota=kota_mi(h.code, metin)) from None
        except (urllib.error.URLError, TimeoutError, OSError) as u:
            raise PaylasimHatasi(f"{method} {url.split('?')[0]} → bağlantı hatası: {getattr(u, 'reason', u)}") from None

    def indir(self, url: str, azami: int | None = None) -> bytes:
        azami = azami or MAX_VIDEO_BAYT
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                veri = r.read(azami + 1)
        except (urllib.error.URLError, TimeoutError, OSError) as u:
            raise PaylasimHatasi(f"video indirilemedi ({url}): {getattr(u, 'reason', u)}", kesin=True) from None
        if len(veri) > azami:
            raise PaylasimHatasi(f"video çok büyük: {url}", kesin=True)
        return veri

    def yayinda_mi(self, url: str) -> bool:
        try:
            req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.status == 200
        except Exception:
            return False

    def uyku(self, sn: float) -> None:
        time.sleep(sn)


def istek(*a, **k):
    """Eski çağıranlar (sosyal_kurulum.py) için."""
    return Ag().istek(*a, **k)


def yayinda_mi(url: str) -> bool:
    return Ag().yayinda_mi(url)


# ---------------------------------------------------------------- X (OAuth 1.0a)
def _pct(s) -> str:
    return urllib.parse.quote(str(s), safe="-._~")


def oauth1_baslik(method, url, ck, cs, tk, ts, params=None, nonce=None, zaman=None) -> str:
    oauth = {
        "oauth_consumer_key": ck,
        "oauth_nonce": nonce or secrets.token_hex(16),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(zaman or int(time.time())),
        "oauth_token": tk,
        "oauth_version": "1.0",
    }
    tum = sorted((_pct(k), _pct(v)) for k, v in {**(params or {}), **oauth}.items())
    param_str = "&".join(f"{k}={v}" for k, v in tum)
    taban = "&".join([method.upper(), _pct(url), _pct(param_str)])
    anahtar = f"{_pct(cs)}&{_pct(ts)}"
    imza = base64.b64encode(hmac.new(anahtar.encode(), taban.encode(), hashlib.sha1).digest()).decode()
    oauth["oauth_signature"] = imza
    return "OAuth " + ", ".join(f'{_pct(k)}="{_pct(v)}"' for k, v in sorted(oauth.items()))


def x_metin(dil, x, link, mod) -> str:
    t = {k: emojisiz(v) if isinstance(v, str) else v for k, v in x["diller"][dil].items()}
    etiket = " ".join(t.get("etiketler", [])[:3])
    son = (f"{METIN[dil]['devam']} {link}" if mod == "gonderide" else METIN[dil]["profil"])
    sabit = 23 if mod == "gonderide" else 0  # X her bağlantıyı 23 karakter sayar

    def uzunluk(s):
        return len(s) - (len(link) - sabit if mod == "gonderide" else 0)

    for govde in (f"{t['baslik']}\n\n{t['ozet']}", t["baslik"]):
        metin = f"{govde}\n\n{son}" + (f"\n{etiket}" if etiket else "")
        if uzunluk(metin) <= 280:
            return metin
        metin = f"{govde}\n\n{son}"
        if uzunluk(metin) <= 280:
            return metin
    kalan = 280 - uzunluk(f"\n\n{son}") - 1
    return f"{t['baslik'][:kalan]}…\n\n{son}"


def x_paylas(ag, sir, dil, x, link, mod) -> dict:
    url = "https://api.x.com/2/tweets"
    bas = oauth1_baslik("POST", url, sir["API_KEY"], sir["API_SECRET"], sir["ACCESS_TOKEN"], sir["ACCESS_SECRET"])
    _, cevap = ag.istek("POST", url, json_govde={"text": x_metin(dil, x, link, mod)}, basliklar={"Authorization": bas})
    pid = cevap.get("data", {}).get("id") if isinstance(cevap, dict) else None
    if not pid:
        raise PaylasimHatasi(f"X beklenmeyen yanıt: {str(cevap)[:300]}")
    return {"kimlik": pid, "url": f"https://x.com/i/web/status/{pid}"}


# ---------------------------------------------------------------- Reddit
def reddit_paylas(ag, sir, dil, x, link, ayar) -> dict:
    kullanici = sir["USERNAME"]
    ua = {"User-Agent": f"web:rockstargtavi-sosyal:1.0 (by /u/{kullanici})"}
    kimlik = base64.b64encode(f"{sir['CLIENT_ID']}:{sir['CLIENT_SECRET']}".encode()).decode()
    _, tok = ag.istek(
        "POST", "https://www.reddit.com/api/v1/access_token",
        veri={"grant_type": "password", "username": kullanici, "password": sir["PASSWORD"]},
        basliklar={**ua, "Authorization": f"Basic {kimlik}"},
    )
    if not isinstance(tok, dict) or "access_token" not in tok:
        raise PaylasimHatasi(f"Reddit giriş başarısız: {str(tok)[:300]}", kesin=True)
    topluluk = (ayar.get("reddit_topluluk") or {}).get(dil) or f"u_{kullanici}"
    _, cevap = ag.istek(
        "POST", "https://oauth.reddit.com/api/submit",
        veri={"api_type": "json", "kind": "link", "sr": topluluk, "title": emojisiz(x["diller"][dil]["baslik"])[:300],
              "url": link, "resubmit": "true", "sendreplies": "false"},
        basliklar={**ua, "Authorization": f"bearer {tok['access_token']}"},
    )
    j = (cevap or {}).get("json", {}) if isinstance(cevap, dict) else {}
    if j.get("errors"):
        raise PaylasimHatasi(f"Reddit gönderim hatası: {j['errors']}", kesin=True)
    d = j.get("data", {})
    return {"kimlik": d.get("name") or d.get("id"), "url": d.get("url")}


# ---------------------------------------------------------------- Instagram (görsel + Reels)
def emojisiz(metin):
    # Şablonlarda emoji yok; kaynak başlık/özetteki emojiler de aktarılmaz.
    return re.sub(r'[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u200D\u20E3]', '', metin)


def ig_icerik_dilleri(dil, ayar):
    secim = (ayar or {}).get('hesaplar', {}).get(dil, {}).get('instagram_icerik') or {}
    ana = secim.get('ana') or dil
    ikinci = secim.get('ikinci')
    return ana, ikinci if ikinci != ana else None


def cumle_kisalt(metin, sinir):
    """Sığan son tam cümlede durur; sığan cümle yoksa gövdeyi kaldırır."""
    metin = metin.strip()
    if len(metin) <= sinir:
        return metin
    bitisler = [m.end() for m in re.finditer(r'[.!?](?=\s|$)|[。！？]', metin)
                if m.end() <= sinir]
    return metin[:bitisler[-1]] if bitisler else ''


# Yorum çağrısı: haber türüne göre gerçek, tartışmaya açık tek soru (etkileşim Shorts/Reels önerisini besler).
# Uydurma bilgi ya da kasıtlı hata içermez; soru okurun tercihine dairdir.
YORUM_SORUSU = {
    "guncelleme": {"tr": "Bu güncelleme yeterli mi, yoksa hâlâ eksik mi? Yorumlara yaz.",
                   "en": "Is this update enough, or is something still missing? Tell us in the comments.",
                   "es": "¿Basta con esta actualización o todavía falta algo? Cuéntalo en los comentarios.",
                   "fr": "Cette mise à jour suffit-elle, ou manque-t-il encore quelque chose ? Dis-le en commentaire.",
                   "de": "Reicht dieses Update oder fehlt noch etwas? Schreib es in die Kommentare.",
                   "nl": "Is deze update genoeg, of ontbreekt er nog iets? Laat het weten in de reacties.",
                   "zh": "这次更新够了吗，还是仍有不足？欢迎在评论区留言。"},
    "cikis": {"tr": "İlk gün alır mısın, yoksa indirimi mi beklersin? Yorumlara yaz.",
              "en": "Day-one buy, or waiting for a sale? Tell us in the comments.",
              "es": "¿Lo compras el primer día o esperas una oferta? Cuéntalo en los comentarios.",
              "fr": "Achat dès le premier jour ou attente d'une promo ? Dis-le en commentaire.",
              "de": "Kauf am ersten Tag oder lieber auf einen Sale warten? Schreib es in die Kommentare.",
              "nl": "Koop je hem op dag één of wacht je op een aanbieding? Laat het weten in de reacties.",
              "zh": "首发就买，还是等打折？欢迎在评论区留言。"},
    "ucretsiz": {"tr": "Kütüphanene ekledin mi, yoksa pas mı geçiyorsun? Yorumlara yaz.",
                 "en": "Claiming it, or skipping this one? Tell us in the comments.",
                 "es": "¿Lo reclamas o lo dejas pasar? Cuéntalo en los comentarios.",
                 "fr": "Tu le récupères ou tu passes ton tour ? Dis-le en commentaire.",
                 "de": "Holst du es dir oder lässt du es aus? Schreib es in die Kommentare.",
                 "nl": "Claim je hem of sla je deze over? Laat het weten in de reacties.",
                 "zh": "你领了吗，还是这次跳过？欢迎在评论区留言。"},
    "indirim": {"tr": "Bu fiyata alınır mı, yoksa daha da düşer mi? Yorumlara yaz.",
                "en": "Worth it at this price, or will it drop further? Tell us in the comments.",
                "es": "¿Merece la pena a este precio o bajará más? Cuéntalo en los comentarios.",
                "fr": "Ça vaut le coup à ce prix, ou ça baissera encore ? Dis-le en commentaire.",
                "de": "Lohnt es sich zu diesem Preis oder wird es noch günstiger? Schreib es in die Kommentare.",
                "nl": "Is het deze prijs waard, of zakt hij nog verder? Laat het weten in de reacties.",
                "zh": "这个价格值得入手吗，还是会再降？欢迎在评论区留言。"},
    "haber": {"tr": "Sence bu oyuncular için iyi haber mi, kötü haber mi? Yorumlara yaz.",
              "en": "Good news or bad news for players? Tell us in the comments.",
              "es": "¿Buena o mala noticia para los jugadores? Cuéntalo en los comentarios.",
              "fr": "Bonne ou mauvaise nouvelle pour les joueurs ? Dis-le en commentaire.",
              "de": "Gute oder schlechte Nachricht für Spieler? Schreib es in die Kommentare.",
              "nl": "Goed of slecht nieuws voor spelers? Laat het weten in de reacties.",
              "zh": "这对玩家来说是好消息还是坏消息？欢迎在评论区留言。"},
}


def yorum_sorusu(dil, x) -> str:
    """Yalnız haber gönderilerinde; tür tanınmıyorsa genel haber sorusu, dil yoksa boş."""
    if x.get("sosyal_tur", "haber") != "haber":
        return ""
    return (YORUM_SORUSU.get(x.get("tur")) or YORUM_SORUSU["haber"]).get(dil, "")


IG_METIN_OZETI = 700 # Instagram açıklamasına haber metninden eklenecek en çok karakter


def ig_aciklama(dil, x, ayar=None) -> str:
    if x.get('sosyal_tur') in KLIP_TURLERI:
        return emojisiz(x['diller'][dil]['ig_aciklama'])[:2200]  # klip metni onay anında saklanmış ve onaylanmıştır
    if (ayar or {}).get('hesaplar', {}).get(dil, {}).get('instagram_icerik'):
        ana, ikinci = ig_icerik_dilleri(dil, ayar)
        diller = [d for d in (ana, ikinci) if d and d in x['diller']]
        basliklar = [emojisiz(x['diller'][d]['baslik']) for d in diller]
        govdeler = [emojisiz(x['diller'][d].get('ozet') or x['diller'][d].get('metin') or '').strip()
                    for d in diller]
        # İkinci dil kısa özet olarak kalır; ana dil gerektiğinde tam metni kullanabilir.
        if len(govdeler) == 2:
            govdeler[1] = cumle_kisalt(govdeler[1], 500)
        tags = se.hashtagler(ana, x, IG_ETIKET_SINIRI)  # ana dil esas; Instagram toplam 5 hashtag kabul eder
        kay = emojisiz(', '.join(kaynak_adi(ana, s['ad']) for s in x['kaynaklar']))[:240]
        cagri = f"{METIN[ana]['devam']} {paylasim_linki(ana, x, 'instagram')}"

        def birlestir():
            bolumler = [b + (f'\n\n{g}' if g else '') for b, g in zip(basliklar, govdeler)]
            return ('\n\n---\n\n'.join(bolumler) + f"\n\n{M[ana]['kaynak']}: {kay}\n{cagri}"
                    + ('\n\n' + ' '.join(tags) if tags else ''))

        for i in reversed(range(len(govdeler))):
            fazla = len(birlestir()) - 2200
            if fazla <= 0:
                break
            govdeler[i] = cumle_kisalt(govdeler[i], max(0, len(govdeler[i]) - fazla))
        while len(birlestir()) > 2200 and tags:
            tags.pop()
        if len(birlestir()) > 2200:
            raise PaylasimHatasi('Instagram başlıkları ve bağlantı çağrısı 2200 karaktere sığmıyor', kesin=True)
        return birlestir()
    # İçerik ayarı olmayan hesaplarda eski açıklama aynen korunur.
    t = x["diller"][dil]
    kay = ", ".join(kaynak_adi(dil, s["ad"]) for s in x["kaynaklar"])
    etiket = " ".join(etiketler(dil, x))
    son = f"\n\n{M[dil]['kaynak']}: {kay[:240]}\n{METIN[dil]['devam']} {paylasim_linki(dil, x, 'instagram')}\n\n{etiket}"
    bas = t['baslik'][:300]
    # Açıklama haberi tek başına anlatmalı: özetin ardından haber metninin sığan ilk cümleleri gelir.
    ozet = (t.get('ozet') or '').strip()
    metin = (t.get('metin') or '').strip()
    ek = cumle_kisalt(metin, IG_METIN_OZETI) if metin and metin != ozet else ''
    govde = '\n\n'.join(b for b in (ozet, ek) if b)
    soru = yorum_sorusu(dil, x)
    if soru:
        son = f"\n\n{soru}{son}"
    yer =max(0, 2200 - len(bas) - len(son) - 2)
    if len(govde) > yer:
        govde = cumle_kisalt(govde, yer) or ozet[:yer]
    return emojisiz(f"{bas}\n\n{govde}{son}")


def etiketler(dil, x):
    """Instagram için keşif etiketleri (en çok 5): oyun adı, yazar, platform, konu, genel (sosyal_etiket)."""
    return se.hashtagler(dil, x, IG_ETIKET_SINIRI)


def ig_video_adresi(v: dict) -> str:
    return v.get("mp4_1080") or v["mp4_720"]


def ig_sunucu(token: str) -> str:
    """Meta'nın yeni uygulamalardaki "Unified login" yolu EAA ile başlayan anahtar verir ve graph.facebook.com
    üzerinden çalışır; eski Instagram girişi anahtarları (IG...) graph.instagram.com ister (denendi 2026-11-16)."""
    return "graph.facebook.com" if str(token).startswith("EAA") else "graph.instagram.com"


def ig_durum(ag, sir, surum, kid) -> str:
    _, d = ag.istek("GET", f"https://{ig_sunucu(sir['TOKEN'])}/{surum}/{kid}?" + urllib.parse.urlencode({"fields": "status_code", "access_token": sir["TOKEN"]}))
    kod = d.get("status_code") if isinstance(d, dict) else None
    if not kod:
        raise PaylasimHatasi(f"Instagram durum yanıtı anlaşılmadı: {str(d)[:200]}")
    return kod


def ig_bekle(ag, sir, surum, kid, deneme=12, aralik=5) -> str:
    """Kapsayıcı FINISHED (ya da zaten PUBLISHED) olana dek bekler. Hazır olmadan yayımlamaya izin vermez."""
    for i in range(deneme):
        kod = ig_durum(ag, sir, surum, kid)
        if kod in ("FINISHED", "PUBLISHED"):
            return kod
        if kod in ("ERROR", "EXPIRED"):
            raise PaylasimHatasi(f"Instagram medyayı işleyemedi ({kod}): {kid}", kesin=True)
        if i < deneme - 1:
            ag.uyku(aralik)
    raise PaylasimHatasi(f"Instagram kapsayıcı süre içinde hazır olmadı (FINISHED değil): {kid}")


def ig_yayimla(ag, sir, surum, kid) -> dict:
    taban = f"https://{ig_sunucu(sir['TOKEN'])}/{surum}/{sir['USER_ID']}"
    _, yay = ag.istek("POST", f"{taban}/media_publish", veri={"creation_id": kid, "access_token": sir["TOKEN"]})
    mid = yay.get("id") if isinstance(yay, dict) else None
    if not mid:
        raise PaylasimHatasi(f"Instagram yayımlanamadı: {str(yay)[:300]}")
    return {"kimlik": mid, "url": ig_baglanti(ag, sir, surum, mid)}


def ig_baglanti(ag, sir, surum, mid) -> str | None:
    """Yayımlanan gönderinin kalıcı bağlantısı; alınamazsa None (paylaşım zaten yapıldı, hata sayılmaz)."""
    try:
        _, d = ag.istek("GET", f"https://{ig_sunucu(sir['TOKEN'])}/{surum}/{mid}?" + urllib.parse.urlencode({"fields": "permalink", "access_token": sir["TOKEN"]}))
        p = d.get("permalink") if isinstance(d, dict) else None
        return p if isinstance(p, str) and p.startswith("https://") else None
    except PaylasimHatasi:
        return None


def ig_paylas(ag, sir, dil, x, ayar, ara, video=None) -> dict:
    surum = ayar.get("instagram_api_surumu", "v27.0")
    taban = f"https://{ig_sunucu(sir['TOKEN'])}/{surum}/{sir['USER_ID']}"
    if video:
        medya = ig_video_adresi(video)
        veri = {"media_type": "REELS", "video_url": medya, "cover_url": video["kapak"], "share_to_feed": "true"}
    else:
        medya = f"{SITE}/{kart_ad(x['id'], ig_icerik_dilleri(dil, ayar)[0], 'ig')}"
        veri = {"image_url": medya}
    if not ag.yayinda_mi(medya):
        raise PaylasimHatasi(f"Instagram medyası yayında değil: {medya}", kesin=True)
    veri.update({"caption": ig_aciklama(dil, x, ayar), "access_token": sir["TOKEN"]})
    _, kap = ag.istek("POST", f"{taban}/media", veri=veri)
    kid = kap.get("id") if isinstance(kap, dict) else None
    if not kid:
        raise PaylasimHatasi(f"Instagram kapsayıcı oluşmadı: {str(kap)[:300]}")
    ara(kapsayici=kid)  # yayımlamadan önce kaydedilir; yanıt kaybolursa sonraki çalışma buradan devam eder
    ig_bekle(ag, sir, surum, kid, deneme=24 if video else 12, aralik=10 if video else 5)
    return ig_yayimla(ag, sir, surum, kid)


# ---------------------------------------------------------------- YouTube Shorts
YT_UST = "https://www.googleapis.com/upload/youtube/v3/videos"
YT_GIZLILIK = ("private", "unlisted", "public")


def yt_baslik(dil, x) -> str:
    b = emojisiz(re.sub(r"[<>]", "", x["diller"][dil]["baslik"])).strip()
    b = b if len(b) <= 100 else b[:99].rstrip() + "…"
    if x.get("sosyal_tur") not in KLIP_TURLERI and "#" not in b:
        oyun = se.oyun_etiketleri(x)
        if oyun and len(b) + 1 + len(oyun[0]) <= 100:
            b = f"{b} {oyun[0]}"  # sığmazsa eklenmez, başlık kısaltılmaz
    return b


def yt_aciklama(dil, x, link) -> str:
    if x.get("sosyal_tur") in KLIP_TURLERI:
        metin = x["diller"][dil]["yt_aciklama"]
        if x["sosyal_tur"] == "klip":
            metin = (metin + " #Shorts").strip()  # dikey klip Shorts; derleme normal video (#Shorts yok)
        return emojisiz(re.sub(r"[<>]", "", metin))[:4900]
    t = x["diller"][dil]
    kay = ", ".join(kaynak_adi(dil, s["ad"]) for s in x["kaynaklar"])
    etiket = " ".join(se.hashtagler(dil, x, YT_ACIKLAMA_ETIKET))
    soru = yorum_sorusu(dil, x)
    metin = (f"{t['ozet']}\n\n" + (f"{soru}\n\n" if soru else "")
             + f"{METIN[dil]['devam']} {link}\n{M[dil]['kaynak']}: {kay}\n\n{etiket} #Shorts").strip()
    return emojisiz(re.sub(r"[<>]", "", metin))[:4900]


def yt_etiketler(dil, x) -> list:
    if x.get("sosyal_tur") not in KLIP_TURLERI:
        return se.yt_anahtar_kelimeler(dil, x)
    sonuc, toplam = [], 0
    for e in x["diller"][dil].get("etiketler", []):
        e = re.sub(r"[<>,#]", "", e).strip()
        if e and toplam + len(e) + 1 <= 400:
            sonuc.append(e)
            toplam += len(e) + 1
    return sonuc


def yt_govde(dil, x, link, ayar) -> dict:
    gizlilik = (ayar.get("youtube") or {}).get("gizlilik", "private")
    if gizlilik not in YT_GIZLILIK:
        gizlilik = "private"
    if x.get("sosyal_tur") in KLIP_TURLERI:
        # Gerçek yayın kesiti: yapay medya değil. Kategori ayardan (20 Oyun, 24 Eğlence); yerelleştirme yok (yalnız Türkçe).
        kat = str((ayar.get("klip") or {}).get("youtube_kategori", "20"))
        return {
            "snippet": {"title": yt_baslik(dil, x), "description": yt_aciklama(dil, x, link), "tags": yt_etiketler(dil, x),
                        "categoryId": kat if kat in YT_KATEGORILER else "20",
                        "defaultLanguage": HREFLANG[dil], "defaultAudioLanguage": HREFLANG[dil]},
            # Otomatik onaylı klip HER ZAMAN gizli yüklenir (ortak `youtube.gizlilik` ayarından bağımsız); Cio Studio'dan açar.
            "status": {"privacyStatus": "private" if x.get("otomatik_gizli") else gizlilik,
                       "selfDeclaredMadeForKids": False, "containsSyntheticMedia": False},
        }
    return {
        "snippet": {"title": yt_baslik(dil, x), "description": yt_aciklama(dil, x, link), "tags": yt_etiketler(dil, x),
                    "categoryId": "20", "defaultLanguage": HREFLANG[dil], "defaultAudioLanguage": HREFLANG[dil]},
        "localizations": {HREFLANG[d]: {"title": yt_baslik(d, x), "description": yt_aciklama(d, x, paylasim_linki(d, x, "youtube"))}
                          for d in DILLER if d != dil and x.get("diller", {}).get(d, {}).get("baslik") and x["diller"][d].get("ozet")},
        "status": {"privacyStatus": gizlilik, "selfDeclaredMadeForKids": False, "containsSyntheticMedia": True},
    }


def yt_erisim(ag, sir) -> str:
    _, c = ag.istek("POST", "https://oauth2.googleapis.com/token",
                    veri={"client_id": sir["CLIENT_ID"], "client_secret": sir["CLIENT_SECRET"],
                          "refresh_token": sir["REFRESH_TOKEN"], "grant_type": "refresh_token"})
    tok = c.get("access_token") if isinstance(c, dict) else None
    if not tok:
        raise PaylasimHatasi(f"YouTube erişim anahtarı alınamadı: {str(c)[:200]}", kesin=True, kota=True)
    return tok


def _yt_sonuc(durum, metin) -> dict:
    try:
        d = json.loads(metin)
    except ValueError:
        d = {}
    vid = d.get("id") if isinstance(d, dict) else None
    if durum in (200, 201) and vid:
        return {"kimlik": vid, "url": f"https://www.youtube.com/shorts/{vid}"}
    raise PaylasimHatasi(f"YouTube yükleme yanıtı anlaşılmadı (HTTP {durum}): {metin[:200]}")


def yt_yukle(ag, oturum, bayt: bytes, baslangic: int = 0) -> dict:
    toplam = len(bayt)
    govde = bayt[baslangic:]
    bas = {"Content-Type": "video/mp4", "Content-Length": str(len(govde))}
    if baslangic:
        bas["Content-Range"] = f"bytes {baslangic}-{toplam - 1}/{toplam}"
    durum, _, metin = ag.ham("PUT", oturum, govde=govde, basliklar=bas)
    return _yt_sonuc(durum, metin)


def yt_oturum_sorgu(ag, oturum, toplam: int):
    """Yükleme oturumuna nerede kaldığını sorar. -> ('bitti', sonuc) | ('surmekte', alinan_bayt)"""
    durum, bas, metin = ag.ham("PUT", oturum, govde=b"", basliklar={"Content-Length": "0", "Content-Range": f"bytes */{toplam}"}, zaman=60)
    if durum in (200, 201):
        return "bitti", _yt_sonuc(durum, metin)
    if durum == 308:
        m = re.search(r"bytes=0-(\d+)", bas.get("range", ""))
        return "surmekte", (int(m.group(1)) + 1 if m else 0)
    raise PaylasimHatasi(f"YouTube oturum sorgusu anlaşılmadı (HTTP {durum})")


def yt_url_duzelt(sonuc: dict, tur) -> dict:
    """Derleme normal videodur: /shorts/ yerine /watch?v= adresi."""
    if tur == "derleme" and sonuc.get("kimlik"):
        sonuc = {**sonuc, "url": f"https://www.youtube.com/watch?v={sonuc['kimlik']}"}
    return sonuc


YT_KAPAK_ONARIM_AZAMI = 4  # her saatlik turda en çok bu kadar eksik dikey kapak onarılır
YT_DIKEY_KAPAK ="https://i.ytimg.com/vi/{}/sardefault.jpg"  # yalnız dikey özel kapak işlendiyse 200 döner


def yt_kapak(ag, tok, video_kimlik, kapak_adresi) -> str | None:
    """Video küçük resmi (en iyi çaba: kanal doğrulanmamışsa ya da Shorts reddederse video yine yayında kalır). -> not | None"""
    try:
        resim = ag.indir(kapak_adresi)
        durum, _, metin = ag.ham("POST", f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={video_kimlik}",
                                 govde=resim, basliklar={"Authorization": f"Bearer {tok}", "Content-Type": "image/jpeg"}, zaman=120)
        return None if durum in (200, 201) else f"küçük resim yüklenmedi (HTTP {durum}): {metin[:200]}"
    except PaylasimHatasi as h:
        return f"küçük resim yüklenmedi: {str(h)[:320]}"


def yt_paylas(ag, sir, dil, x, link, ayar, ara, video) -> dict:
    medya = ig_video_adresi(video)
    tur = x.get("sosyal_tur")
    if not ag.yayinda_mi(medya):
        raise PaylasimHatasi(f"YouTube videosu yayında değil: {medya}", kesin=True)
    bayt = ag.indir(medya, MAX_DERLEME_BAYT) if tur == "derleme" else ag.indir(medya)
    tok = yt_erisim(ag, sir)
    parca = "snippet,status" if tur in KLIP_TURLERI else "snippet,status,localizations"
    durum, bas, metin = ag.ham(
        "POST", f"{YT_UST}?uploadType=resumable&part={parca}",
        govde=json.dumps(yt_govde(dil, x, link, ayar)).encode(),
        basliklar={"Authorization": f"Bearer {tok}", "Content-Type": "application/json; charset=UTF-8",
                   "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(len(bayt))}, zaman=60)
    oturum = bas.get("location")
    if not oturum or not oturum.startswith("https://"):
        raise PaylasimHatasi(f"YouTube yükleme oturumu açılamadı (HTTP {durum}): {metin[:200]}", kesin=True)
    ara(oturum=oturum, boyut=len(bayt))  # baytlar gitmeden önce kaydedilir
    sonuc = yt_url_duzelt(yt_yukle(ag, oturum, bayt), tur)
    if tur != "klip" and video.get("kapak"):
        kapak_not = yt_kapak(ag, tok, sonuc["kimlik"], video["kapak"])
        if kapak_not:
            sonuc = {**sonuc, "kapak_not": kapak_not}
    return sonuc


# ---------------------------------------------------------------- kayıt modeli
GEREKEN = {
    "x": ("API_KEY", "API_SECRET", "ACCESS_TOKEN", "ACCESS_SECRET"),
    "reddit": ("CLIENT_ID", "CLIENT_SECRET", "USERNAME", "PASSWORD"),
    "instagram": ("USER_ID", "TOKEN"),
    "youtube": ("CLIENT_ID", "CLIENT_SECRET", "REFRESH_TOKEN"),
}
ONEK_SIR = {"x": "X", "reddit": "REDDIT", "instagram": "IG", "youtube": "YT"}
# (platform, biçim, ayarlar.json'daki hesap anahtarı ve günlük sınır adı)
HEDEFLER = (("x", "gorsel", "x"), ("reddit", "gorsel", "reddit"), ("instagram", "reel", "instagram_reel"),
            ("instagram", "gorsel", "instagram"), ("youtube", "short", "youtube"))
VARSAYILAN_SINIR = {"x": 2, "reddit": 2, "instagram": 2, "instagram_reel": 2, "youtube": 2}


def _aralik_icinde_mi(c, saat: int) -> bool:
    if not isinstance(c, dict):
        return False
    bas, son = c.get("bas"), c.get("son")
    if any(isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= 23 for v in (bas, son)) or bas == son:
        return False
    return bas <= saat < son if bas < son else (saat >= bas or saat < son)


def sessiz_saat_mi(ayar: dict, saat: int) -> bool:
    """video_sessiz_saat_utc {bas, son} (UTC, gece yarısını aşabilir) içinde mi? Ayar yok/geçersizse False."""
    return _aralik_icinde_mi((ayar or {}).get("video_sessiz_saat_utc"), saat)


def klip_sessiz_saat_mi(ayar: dict, saat: int) -> bool:
    """Klip hesabı sessiz saati: klip.sessiz_saat_utc tanımlıysa onu (null/boş=kapalı), yoksa video_sessiz_saat_utc'yi kullanır."""
    k = (ayar or {}).get("klip")
    if isinstance(k, dict) and "sessiz_saat_utc" in k:
        return _aralik_icinde_mi(k.get("sessiz_saat_utc"), saat)
    return sessiz_saat_mi(ayar, saat)


def konu_veya_id(x: dict) -> str:
    return x.get("sosyal_anahtar") or (x.get("otomasyon") or {}).get("konu") or x["id"]


def anahtar(x: dict, dil: str, platform: str, bicim: str) -> str:
    return f"{konu_veya_id(x)}|{dil}|{platform}|{bicim}"


def kayit_goc(kayit: dict, veri: list) -> tuple[dict, bool]:
    """Eski kayıt (id|dil|platform) → yeni (konu|dil|platform|gorsel, durum=tamam). Yeni anahtarlar olduğu gibi kalır."""
    konu = {x["id"]: konu_veya_id(x) for x in veri}
    yeni, degisti = {}, False
    for k, v in kayit.items():
        p = k.split("|")
        if len(p) == 3:
            degisti = True
            rec = dict(v)
            rec.setdefault("durum", "tamam")
            rec.setdefault("id", p[0])
            rec.setdefault("dil", p[1])
            rec.setdefault("platform", p[2])
            rec.setdefault("bicim", "gorsel")
            yeni.setdefault(f"{konu.get(p[0], p[0])}|{p[1]}|{p[2]}|gorsel", rec)
        else:
            yeni[k] = v
    # Hesap dilinden başka dilde içerik yayımlamış eski kayıt (dil=tr, icerik_dili=en): kayıt, içeriğin diline taşınır
    # ve hesap alanı yazılır. Böylece Türkçe sürüm o kayıtla engellenmez, İngilizce sürüm de ikinci kez gitmez.
    for k, v in list(yeni.items()):
        p = k.split("|")
        icerik = v.get("icerik_dili")
        if len(p) != 4 or not icerik or icerik == p[1] or v.get("dil", p[1]) != p[1]:
            continue
        yk = f"{p[0]}|{icerik}|{p[2]}|{p[3]}"
        if yk in yeni:
            continue
        rec = dict(v)
        rec.update(dil=icerik, hesap=p[1])
        del yeni[k]
        yeni[yk] = rec
        degisti = True
    return yeni, degisti


def kayit_yaz(yol: pathlib.Path, kayit: dict) -> None:
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(json.dumps(kayit, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def sinir_adi(k: str) -> str:
    _, _, platform, bicim = k.split("|")
    return {"reel": "instagram_reel", "short": "youtube"}.get(bicim, platform)


def kayit_hesabi(k: str, rec: dict) -> str:
    """Kaydın yayınlandığı hesabın dili. Ortak hesaptan çıkan kayıtta `hesap` yazılıdır; yoksa hesap dili = kayıt dili."""
    return rec.get("hesap") or rec.get("dil") or k.split("|")[1]


def _sayilir(v: dict) -> bool:
    return v.get("durum") in ("tamam", "niyet", "elle_bak")


def _zaman_gunu(v: dict) -> str:
    return (v.get("niyet_zamani") or v.get("zaman") or "")[:10]


HABER_DISI_TURLER = ("takvim", "firsat", "ucretsiz", "rehber", "arsiv")


def bugunku_sayi(kayit: dict, ad: str, hesap: str, gun: str) -> int:
    """Günlük sınır HESAP başınadır: hesap = yayının çıktığı hesabın dili (ortak hesaba giden diller o hesaba yazılır)."""
    return sum(1 for k, v in kayit.items()
               if len(k.split("|")) == 4 and kayit_hesabi(k, v) == hesap and sinir_adi(k) == ad
               and _sayilir(v) and _zaman_gunu(v) == gun)


def bugunku_dil_sayisi(kayit: dict, ad: str, hesap: str, dil: str, gun: str) -> int:
    """Bir hesapta bugün çıkan, içeriği `dil` olan gönderiler (ana dil payı ve dil dönüşümü için)."""
    return sum(1 for k, v in kayit.items()
               if len(k.split("|")) == 4 and kayit_hesabi(k, v) == hesap and sinir_adi(k) == ad
               and (v.get("dil") or k.split("|")[1]) == dil and _sayilir(v) and _zaman_gunu(v) == gun)


def bugunku_tur_sayisi(kayit: dict, ad: str, hesap: str, gun: str, turler, gizli: bool | None = None) -> int:
    """Bugün hesapta çıkan, `sosyal_tur`u `turler` içinde olan gönderiler (klip/derleme günlük sınırı için).
    gizli=None hepsini sayar; False yalnız herkese açık (otomatik gizli yüklemeler HAKKI YEMEZ); True yalnız otomatik gizli."""
    return sum(1 for k, v in kayit.items()
               if len(k.split("|")) == 4 and kayit_hesabi(k, v) == hesap and sinir_adi(k) == ad
               and v.get("sosyal_tur") in turler and _sayilir(v) and _zaman_gunu(v) == gun
               and (gizli is None or bool(v.get("gizli")) == gizli))


def _tam_sayi(v, varsayilan: int) -> int:
    return varsayilan if isinstance(v, bool) or not isinstance(v, int) or v < 0 else v


def klip_ayari(ayar: dict) -> dict:
    k = ayar.get("klip") or {}
    ara = k.get("en_az_ara_saat", 0)
    min_konusma = _tam_sayi(k.get("otomatik_min_konusma_puani"), 8)
    return {"gunluk_en_fazla": {**KLIP_SINIR_VARSAYILAN, **(k.get("gunluk_en_fazla") or {})},
            "derleme_gunluk_en_fazla": int(k.get("derleme_gunluk_en_fazla", 1)),
            # Otomatik gizli yükleme (Cio onayı beklemeden, YouTube'a `private`): ana anahtar `klip.otomatik_gizli`;
            # kapalıyken onay.otomatik işaretli klipler HİÇBİR yere gitmez. Gizliler kendi günlük sınırına tabidir.
            "otomatik_gizli": k.get("otomatik_gizli") is True,
            "gizli_gunluk_en_fazla": _tam_sayi(k.get("gizli_gunluk_en_fazla"), 4),
            # Otomatik onay yalnız son N saatte kesilmiş klibe verilir (0: sınırsız). Birikmiş eski klipler otomatik akışa girmez.
            "otomatik_taze_saat": _tam_sayi(k.get("otomatik_taze_saat"), 24),
            # İçerik puanı zorunlu (0–10). İçerik puanı 9 ve üstüyse sohbet eşiği aranmaz.
            "otomatik_min_konusma_puani": min_konusma if min_konusma <= 10 else 8,
            "otomatik_min_sohbet_puani": _tam_sayi(k.get("otomatik_min_sohbet_puani"), 60),
            # Videoda (konuşmada) küfür geçen klip otomatik akışa girsin mi (2026-11-25, Cio: "küfürde sıkıntı yok").
            # Paylaşım METNİNDEKİ (başlık/açıklama) küfür her durumda engellenir (onayla_bir).
            "otomatik_kufurlu_izin": k.get("otomatik_kufurlu_izin") is True,
            # Bir günde aynı yayıncıdan otomatik onaylanan en çok klip (0: sınırsız).
            "otomatik_yayinci_basina": _tam_sayi(k.get("otomatik_yayinci_basina"), 2),
            "gizli_calisma_basina_en_fazla": _tam_sayi(k.get("gizli_calisma_basina_en_fazla"), _tam_sayi(k.get("gizli_gunluk_en_fazla"), 4)),
            "en_az_ara_saat": 0 if isinstance(ara, bool) or not isinstance(ara, (int, float)) or ara <= 0 else float(ara),
            # Hangi platforma klip gitsin: YouTube açık, Instagram varsayılan kapalı (açılsa da ayrı IG_KLIP_* sırrı ister).
            "platformlar": {"youtube": bool(k.get("youtube", True)), "instagram_reel": bool(k.get("instagram", False))}}


def video_baglanti_yaz(manifest_yolu, klip_yolu, tur, oge_id, dil, alan, url) -> bool:
    if tur in KLIP_TURLERI:
        return ks.baglanti_yaz(klip_yolu, oge_id, alan, url)
    return vs.baglanti_yaz(manifest_yolu, oge_id, dil, alan, url)


def son_gonderi(kayit: dict, hesap: str, ad: str, gizli_haric: bool = False) -> tuple[str, str | None, str | None]:
    """Hesabın bu sınır adındaki en son gönderisi -> (zaman, içerik dili, konu). Yoksa ("", None, None).
    gizli_haric=True: otomatik gizli yüklemeler sayılmaz (herkese açık paylaşımın `en_az_ara_saat` aralığını bozmasın)."""
    en = ("", None, None)
    for k, v in kayit.items():
        p = k.split("|")
        if len(p) != 4 or kayit_hesabi(k, v) != hesap or sinir_adi(k) != ad or not _sayilir(v):
            continue
        if gizli_haric and v.get("gizli"):
            continue
        z = v.get("zaman") or v.get("niyet_zamani") or ""
        if z >= en[0]:
            en = (z, v.get("dil") or p[1], p[0])
    return en


def son_platform_gonderisi(kayit: dict, hesap: str, platform: str) -> str:
    """Hesabın bu platformdaki (biçimden bağımsız: görsel veya Reels) en son gönderi zamanı."""
    en = ""
    for k, v in kayit.items():
        p = k.split("|")
        if len(p) != 4 or kayit_hesabi(k, v) != hesap or p[2] != platform or not _sayilir(v):
            continue
        z = v.get("zaman") or v.get("niyet_zamani") or ""
        if z >= en:
            en = z
    return en


def hesapta_konu_var_mi(kayit: dict, hesap: str, platform: str, x: dict) -> bool:
    """Aynı haber/konu bu hesapta ve platformda herhangi bir biçimde (görsel veya Reel) daha önce paylaşıldı mı?"""
    konu = konu_veya_id(x)
    xid = x.get("id")
    for k, v in kayit.items():
        p = k.split("|")
        if len(p) != 4 or kayit_hesabi(k, v) != hesap or p[2] != platform or not _sayilir(v):
            continue
        if p[0] == konu or (xid and (p[0] == xid or v.get("id") == xid)):
            return True
    return False


def ayni_konu_yakin(zaman_, simdi: datetime, ayar: dict) -> bool:
    """Son gönderi `ayni_konu_ara_saat` saatten yeni mi? (Eşikten sonra aynı haberin başka dil sürümü yeniden serbest.)"""
    saat = float((ayar or {}).get("ayni_konu_ara_saat", 0) or 0)
    dt = sk.zaman(zaman_) if zaman_ else None
    return bool(saat and dt and timedelta(0) <= simdi - dt < timedelta(hours=saat))


def son_gonderi_yakin(zaman_, simdi: datetime, saat) -> bool:
    """Son gönderi `saat` saatten yeni mi? (Aynı hesapta art arda video basmayı önler.)"""
    if isinstance(saat, bool) or not isinstance(saat, (int, float)) or saat <= 0:
        return False
    dt = sk.zaman(zaman_) if zaman_ else None
    return bool(dt and timedelta(0) <= simdi - dt < timedelta(hours=float(saat)))


def dil_sirasi(ayar, kuyruk, kayit, simdi, hesap, platform, uyeler, son_dil) -> list[str]:
    """Hesabın bu çalışmada deneyeceği içerik dilleri, sırayla.
    1) çıkışa yakın GTA VI önceliği bekleyen diller öne; 2) ana dil ile yabancı diller dönüşümlü (son gönderi ana dilse
    yabancı önce, değilse ana dil önce); 3) yabancılar kendi içinde en uzun süredir gönderisi olmayandan başlar."""
    yabanci_sira = [d for d in (ayar.get("hesap_dil_sirasi") or DILLER) if d in uyeler and d != hesap]
    yabanci_sira += [d for d in DILLER if d in uyeler and d != hesap and d not in yabanci_sira]
    en_son = {}
    for k, v in kayit.items():
        p = k.split("|")
        if len(p) == 4 and kayit_hesabi(k, v) == hesap and _sayilir(v) and p[2] == platform:
            d = v.get("dil") or p[1]
            en_son[d] = max(en_son.get(d, ""), v.get("zaman") or v.get("niyet_zamani") or "")
    yabanci = sorted(yabanci_sira, key=lambda d: (en_son.get(d, ""), yabanci_sira.index(d)))
    ana = [hesap] if hesap in uyeler else []
    sira = (yabanci + ana) if son_dil == hesap else (ana + yabanci)
    gta = [d for d in sira if sk.gta_bekliyor(kuyruk, d, platform, kayit, simdi)]
    return gta + [d for d in sira if d not in gta]


def sirlari_oku(ortam=None) -> dict:
    ortam = os.environ if ortam is None else ortam
    tum = {}
    ham = ortam.get("SOSYAL_SIRLAR")
    if ham:
        try:
            tum.update({k: v for k, v in json.loads(ham).items() if isinstance(v, str)})
        except json.JSONDecodeError:
            print("Uyarı: SOSYAL_SIRLAR okunamadı.")
    for k, v in ortam.items():
        if k.startswith(("X_", "REDDIT_", "IG_", "YT_")):
            tum.setdefault(k, v)
    return tum


def hesap_sirri(tum, platform, dil):
    on = f"{ONEK_SIR[platform]}_{dil.upper()}_"
    sir = {a: (tum.get(on + a) or "").strip() for a in GEREKEN[platform]}
    return sir if all(sir.values()) else None


def hesap_coz(ayar, tum, platform, dil):
    """İçerik dilinin yayınlanacağı hesap -> (hesap dili, anahtarlar | None).
    Dilin kendi anahtarları varsa kendi hesabı; yoksa ayardaki `hesap_esleme.<platform>.<dil>` ortak hesabı
    (ileride bir dile ayrı hesap açılıp anahtarları girilirse o dil kendiliğinden kendi hesabına döner)."""
    sir = hesap_sirri(tum, platform, dil)
    if sir:
        return dil, sir
    hesap = (((ayar or {}).get("hesap_esleme") or {}).get(platform) or {}).get(dil) or dil
    return hesap, hesap_sirri(tum, platform, hesap)


def eksik_sirlar(tum, platform, dil) -> list[str]:
    """Hesabın eksik ortam değişkeni adları (yalnız ad; değer yok)."""
    on = f"{ONEK_SIR[platform]}_{dil.upper()}_"
    return [on + a for a in GEREKEN[platform] if not (tum.get(on + a) or "").strip()]


def video_hakki(x: dict, ayar: dict) -> bool:
    """Reels/Shorts yalnız hype puanı eşiğe ulaşan haberde; puanı olmayan eski haberde manifestte video yeter."""
    hype = (x.get("otomasyon") or {}).get("hype")
    if hype is None:
        return True
    esik = int((ayar.get("video") or {}).get("hype_esigi", 7))
    return type(hype) is int and hype >= esik


def paylasim_linki(dil, x, platform) -> str:
    q = urllib.parse.urlencode({"utm_source": platform, "utm_medium": "social", "utm_campaign": "oyun-haberleri"})
    return sayfa_adresi(dil, x) + f"?{q}"


def sayfa_adresi(dil, x):
    return f"{SITE}/" + x.get("sayfalar", {}).get(dil, f"{KLASOR[dil]}/{x['id']}.html")


# ---------------------------------------------------------------- yarım kalan paylaşımları uzlaştır
def _tamamla(rec: dict, sonuc: dict, simdi: datetime) -> None:
    rec.update(durum="tamam", zaman=simdi.isoformat(timespec="seconds"), **sonuc)


def uzlastir(ag, kayit, tum, ayar, manifest_yolu, kaydet, simdi, klip_yolu=None, engel=None, engel_yolu=None,
             cikti=print) -> list:
    """Önceki çalışmadan kalan "niyet" kayıtlarını platformdan sorgulayıp tamamlar ya da elle_bak yapar.
    Hiçbir koşulda yeniden paylaşım denemez (yalnız zaten yaratılmış kapsayıcı/oturum devam ettirilir)."""
    mesajlar = []
    for k, rec in list(kayit.items()):
        if rec.get("durum") != "niyet":
            continue
        platform, bicim, dil = rec.get("platform"), rec.get("bicim"), rec.get("dil")
        sir = hesap_sirri(tum, platform, kayit_hesabi(k, rec)) if platform in ONEK_SIR else None

        def elle(neden):
            rec.update(durum="elle_bak", **{"not": neden})
            kaydet()
            mesajlar.append(f"ELLE BAK {k}: {neden}")

        if platform == "instagram" and rec.get("kapsayici"):
            if not sir:
                continue
            ek = f"instagram|{kayit_hesabi(k, rec)}"
            if engel is not None and engel_molada_mi(engel, ek, simdi):
                continue  # mola sürerken platforma hiç gidilmez; kayıt "niyet" olarak bekler
            surum = ayar.get("instagram_api_surumu", "v27.0")
            try:
                kod = ig_durum(ag, sir, surum, rec["kapsayici"])
                if kod == "PUBLISHED":
                    _tamamla(rec, {"kimlik": None, "url": None, "not": "kapsayıcı PUBLISHED çıktı; kimlik bilinmiyor"}, simdi)
                elif kod == "FINISHED":
                    _tamamla(rec, ig_yayimla(ag, sir, surum, rec["kapsayici"]), simdi)
                elif kod in ("ERROR", "EXPIRED"):
                    if rec.get("engel"):
                        # 2026-11-24 ölçümü (MOUSE): Instagram media_publish 2207051 döndürse de gönderiyi yayımlayıp
                        # 6-12 saat sonra kapsayıcıyı EXPIRED/ERROR gösterebiliyor. Kayıt silinirse aynı haber ikinci
                        # kez atılır! Tekrarı önlemek için kapatılır; asla yeniden denenmez.
                        _tamamla(rec, {"kimlik": None, "url": None,
                                       "not": f"Instagram engeli sonrası kapsayıcı {kod}; yayımlanmış olabileceğinden yeniden denenmedi"}, simdi)
                        rec.pop("engel", None)
                        kaydet()
                        cikti(f"::warning::Instagram kapsayıcı {kod} ({rec.get('id')}): engelde yayımlanmış olabileceğinden yeniden denenmedi")
                    else:
                        elle(f"Instagram kapsayıcı {kod}; yayımlanmadı, kontrol edip gerekirse kaydı silin")
                    continue
                else:
                    ilk = datetime.fromisoformat(rec["niyet_zamani"])
                    if simdi - ilk > timedelta(hours=24):
                        elle("Instagram kapsayıcı 24 saatten uzun işleniyor")
                    continue
            except PaylasimHatasi as h:
                if engel is not None and engel_yolu is not None and meta_engel_mi(str(h)):
                    saat = engel_mola_ver(engel, engel_yolu, ek, simdi, str(h))
                    cikti(f"::warning::Instagram engeli sürüyor; {saat} saat mola verildi, gönderi bekliyor ({rec.get('id')})")
                else:
                    mesajlar.append(f"Uzlaştırma bekliyor {k}: {h}")
                continue
            rec.pop("engel", None)
            kaydet()
            if engel is not None and engel_yolu is not None and engel.pop(ek, None) is not None:
                engel_yaz(engel_yolu, engel)
            if bicim == "reel" and rec.get("url"):
                video_baglanti_yaz(manifest_yolu, klip_yolu, rec.get("sosyal_tur"), rec["id"], rec.get('icerik_dili', dil), "instagram", rec["url"])
        elif platform == "youtube" and rec.get("oturum") and rec.get("boyut"):
            try:
                klip_mi = rec.get("sosyal_tur") in KLIP_TURLERI
                video = ks.bul(ks.yukle(klip_yolu), rec["id"]) if klip_mi else vs.bul(vs.yukle(manifest_yolu), rec["id"], dil)
                durum, s = yt_oturum_sorgu(ag, rec["oturum"], rec["boyut"])
                if durum == "surmekte":
                    if not video:
                        elle("YouTube yüklemesi yarım ama video manifestte yok")
                        continue
                    bayt = ag.indir(ig_video_adresi(video), MAX_DERLEME_BAYT) if rec.get("sosyal_tur") == "derleme" else ag.indir(ig_video_adresi(video))
                    if len(bayt) != rec["boyut"]:
                        elle("YouTube yüklemesi yarım ve video dosyası değişmiş")
                        continue
                    s = yt_yukle(ag, rec["oturum"], bayt, s)
                s = yt_url_duzelt(s, rec.get("sosyal_tur"))
            except PaylasimHatasi as h:
                if "HTTP 404" in str(h) or "HTTP 410" in str(h):
                    elle("YouTube yükleme oturumu bulunamadı (süresi dolmuş olabilir); YouTube Studio'da kontrol edin")
                else:
                    mesajlar.append(f"Uzlaştırma bekliyor {k}: {h}")
                continue
            _tamamla(rec, s, simdi)
            kaydet()
            video_baglanti_yaz(manifest_yolu, klip_yolu, rec.get("sosyal_tur"), rec["id"], dil, "youtube", s["url"])
        else:
            elle("yanıt kaybolmuş olabilir ve platformdan doğrulanamıyor; platformda gönderiye bakın, yoksa kaydı silin")
    return mesajlar


# ---------------------------------------------------------------- akış
def calistir(ayar: dict, veri: list, *, kayit_yolu: pathlib.Path, manifest_yolu: pathlib.Path, tum: dict, ag, dry_run: bool,
            bugun: date, simdi: datetime, cikti=print, anahtarsiz_goster: bool = False,
            kuyruk=None, bellek=None, secildi=None, klip_yolu=None, gizli_yuklenen: list | None = None) -> tuple[int, list, list]:
    ham = json.loads(kayit_yolu.read_text(encoding="utf-8")) if kayit_yolu.exists() else {}
    kayit, goc = kayit_goc(ham, veri) if bellek is None else (bellek, False)
    # Kütüphane çağıran eski istemciler yalnız verdikleri haberleri işler.
    # CLI ve derleyici ortak kuyruk üreticisini açıkça kullanır.
    kuyruk = kuyruk if kuyruk is not None else sk.adaylar(veri, kayit_yolu.parent.parent, ayar, bugun, simdi)
    manifest = vs.yukle(manifest_yolu)
    # Klip/derleme: Cio'nun onayladığı ve medya sunucusuna yüklenmiş olanlar yalnız AYRI klip hesabına gider
    # (YT_KLIP_* / IG_KLIP_*); onay/yükleme olmadıkça aday çıkmaz. Haber hesapları klip görmez.
    klip_yolu = pathlib.Path(klip_yolu) if klip_yolu else kayit_yolu.parent.parent / "data" / "klipler.json"
    klip_manifest = ks.yukle(klip_yolu)
    klipler = ks.adaylar(klip_manifest, ayar)  # haber kuyruğuna KATILMAZ: ayrı klip hesabının geçişinde işlenir
    kayar = klip_ayari(ayar)
    gun = simdi.strftime("%Y-%m-%d")
    hatalar, atlanan, gonderilen = [], [], 0
    # Platform engeli molası (sosyal/engel.json): denemede okunmaz/yazılmaz, yalnız gerçek turda geçerlidir.
    engel_yolu = kayit_yolu.parent / "engel.json"
    engel = {} if dry_run else engel_oku(engel_yolu)

    def kaydet():
        if not dry_run:
            kayit_yaz(kayit_yolu, kayit)

    if goc:
        kaydet()
    if not dry_run:
        onceki = {k for k, r in kayit.items() if r.get('durum') == 'niyet'}
        hatalar += uzlastir(ag, kayit, tum, ayar, manifest_yolu, kaydet, simdi, klip_yolu, engel, engel_yolu, cikti)
        manifest = vs.yukle(manifest_yolu)
        klip_manifest = ks.yukle(klip_yolu)
    else:
        onceki = set()
    kullanilan = {(kayit_hesabi(k, kayit[k]), k.split('|')[2]) for k in onceki if k in kayit and kayit[k].get('durum') == 'tamam'}

    ortak_bicim = tuple(ayar.get("ortak_hesap_bicimleri") or BICIMLER)
    hesap_hatasi: set = set()
    for platform, bicim, ad in HEDEFLER:
        # Hesap başına grup: kendi anahtarı olan dil kendi hesabına, olmayan dil ayardaki ortak hesaba gider.
        gruplar: dict[str, list[str]] = {}
        for dil in DILLER:
            if not ayar["hesaplar"].get(dil, {}).get(ad):
                continue
            hesap, sir = hesap_coz(ayar, tum, platform, dil)
            if hesap != dil and bicim not in ortak_bicim:
                continue  # başka dilin hesabından yalnız ayarda izinli biçimler (Reels/Shorts) çıkar
            if not sir and not (dry_run and anahtarsiz_goster):
                atlanan.append(f"{ad}/{dil}")
                if dry_run:
                    cikti(f"[DENEME] {ad}/{dil}: anahtar yok, atlandı ({', '.join(eksik_sirlar(tum, platform, hesap))})")
                continue
            gruplar.setdefault(hesap, []).append(dil)
        if gruplar and bicim in ("reel", "short") and sessiz_saat_mi(ayar, simdi.hour):
            cikti(f"{ad}: sessiz saat (UTC {simdi.hour}), Reels/Shorts bu çalışmada yayınlanmaz; sıradaki çalışmaya kalır")
            continue  # niyet kaydı yazılmaz
        for hesap, uyeler in gruplar.items():
            sir = hesap_sirri(tum, platform, hesap)
            if (hesap, platform) in kullanilan:
                continue
            mola = engel_molada_mi(engel, f"{platform}|{hesap}", simdi)
            if mola:
                cikti(f"{ad}/{hesap}: platform engeli molası ({mola} zamanına kadar), bu çalışmada denenmez")
                continue
            sinir = (ayar.get("gunluk_en_fazla") or {}).get(ad, VARSAYILAN_SINIR[ad])
            hak = min(1, ayar.get("calisma_basina_en_fazla", 1), sinir - bugunku_sayi(kayit, ad, hesap, gun))
            if hak <= 0:
                continue
            ortak = any(d != hesap for d in uyeler)
            en_az = int((ayar.get("ana_dil_en_az") or {}).get(ad, 0)) if ortak and hesap in uyeler else 0
            son_z, son_d, son_konu = son_gonderi(kayit, hesap, ad)
            if platform == "instagram" and ayar.get("instagram_en_az_ara_saat"):
                son_ig = son_platform_gonderisi(kayit, hesap, "instagram")
                if son_gonderi_yakin(son_ig, simdi, ayar.get("instagram_en_az_ara_saat")):
                    cikti(f"{ad}/{hesap}: son Instagram gönderisinden bu yana {ayar['instagram_en_az_ara_saat']} saat dolmadı, sıradaki çalışmaya kalır")
                    continue
            if bicim in ("reel", "short") and son_gonderi_yakin(son_z, simdi, ayar.get("video_en_az_ara_saat")):
                cikti(f"{ad}/{hesap}: son videodan bu yana {ayar['video_en_az_ara_saat']} saat dolmadı, sıradaki çalışmaya kalır")
                continue
            yasak_konu = son_konu if ortak and ayni_konu_yakin(son_z, simdi, ayar) else None
            # Haber dışı (dolgu) içeriğin hesap başına günlük payı; ayarda yoksa sınır uygulanmaz.
            hd_sinir = (ayar.get("haber_disi_gunluk_en_fazla") or {}).get(ad)
            haber_disi_doldu = (hd_sinir is not None and
                                bugunku_tur_sayisi(kayit, ad, hesap, gun, HABER_DISI_TURLER) >= int(hd_sinir))

            def adaylari(dil, hesap=hesap, platform=platform, bicim=bicim, yasak_konu=yasak_konu, ad=ad, uyeler=uyeler,
                         haber_disi_doldu=haber_disi_doldu):
                icerik_dili = ig_icerik_dilleri(dil, ayar)[0] if platform == 'instagram' else dil
                global_ig = platform == 'instagram' and bool(ayar['hesaplar'][dil].get('instagram_icerik'))
                ig_tek = platform == 'instagram' and bool(ayar.get('instagram_tek_gonderi'))
                ig_haber_reel = (platform == 'instagram' and bicim == 'gorsel'
                                 and bool(ayar.get('instagram_haber_yalniz_reel'))
                                 and bool(ayar['hesaplar'].get(dil, {}).get('instagram_reel')))
                for x in sk.oncelikli(kuyruk, dil, platform, kayit, simdi):
                    if x.get('sosyal_tur') in KLIP_TURLERI:
                        continue  # klip/derleme haber hesaplarına gitmez; ayrı klip hesabı geçişinde işlenir
                    if not sk.uygun(x, dil, platform, kayit, simdi):
                        continue
                    if x.get('sosyal_tur', 'haber') != 'haber' and haber_disi_doldu:
                        continue  # dolgu içerik (rehber, arşiv, takvim, fırsat) günlük payını doldurdu; haberler sınırsız sürer
                    if icerik_dili not in x.get('diller', {}):
                        continue  # Ana içerik dilinden hesap diline düşülmez.
                    k = anahtar(x, dil, platform, bicim)
                    if k in kayit:
                        continue
                    if ig_tek and hesapta_konu_var_mi(kayit, hesap, 'instagram', x):
                        continue  # Aynı haber Instagram'da (görsel veya Reels) ikinci kez paylaşılmaz.
                    if ig_haber_reel and x.get('sosyal_tur', 'haber') == 'haber' and video_hakki(x, ayar):
                        continue  # Video adayı haber statik görsel kart olarak atılmaz; videosu hazır olunca Reels çıkar.
                    if global_ig and any(p.split('|')[1:3] == [dil, platform] and
                                         (p.split('|')[0] == konu_veya_id(x) or
                                          (x.get('sosyal_tur', 'haber') in ('haber', 'arsiv') and
                                           (p.split('|')[0] == x['id'] or r.get('id') == x['id'])))
                                         for p, r in kayit.items()):
                        continue  # Eski TR gönderisi başka dil/biçimle yeniden paylaşılmaz.
                    if yasak_konu and konu_veya_id(x) == yasak_konu:
                        continue  # aynı haberin başka dil sürümü art arda gitmez; araya başka içerik girer
                    video = None
                    if bicim != "gorsel":
                        if not video_hakki(x, ayar):
                            continue  # hype puanı eşiğin altında: bu haber yalnız görsel gönderi alır
                        video = vs.bul(manifest, x["id"], icerik_dili)
                        if not video:
                            continue  # bu haber/dil için video henüz yok
                        if video.get("instagram" if bicim == "reel" else "youtube"):
                            continue  # manifest bu videonun bu platforma çıktığını söylüyor
                    yield x, k, video, icerik_dili

            toplam = bugunku_sayi(kayit, ad, hesap, gun)
            serbest_saat = int(ayar.get("ana_dil_payi_serbest_saat", 24))
            for dil in dil_sirasi(ayar, kuyruk, kayit, simdi, hesap, platform, uyeler, son_d):
                if hak <= 0 or (hesap, ad) in hesap_hatasi:
                    break
                if dil != hesap and en_az:
                    eksik = max(0, en_az - bugunku_dil_sayisi(kayit, ad, hesap, hesap, gun))
                    if eksik and sinir - toplam - eksik <= 0 and (simdi.hour < serbest_saat or next(adaylari(hesap), None) is not None):
                        continue  # kalan haklar o günkü ana dil payına ayrılmış (serbest saatten sonra yalnız ana dilde aday varsa)
                for x, k, video, icerik_dili in adaylari(dil):
                    if hak <= 0:
                        break
                    link = paylasim_linki(icerik_dili, x, platform)
                    sayfa = sayfa_adresi(icerik_dili, x)
                    if dry_run:
                        cikti(f"\n[DENEME] {ad}/{dil}  {x['id']}" + (f"  (hesap: {hesap})" if hesap != dil else "")
                              + ("" if sir else "  (hesap şifresi yok, gerçekte atlanır)"))
                        if platform == "x":
                            cikti(x_metin(dil, x, link, ayar.get("x_baglanti", "gonderide")))
                        elif platform == "reddit":
                            cikti(f"başlık: {x['diller'][dil]['baslik']}\nbağlantı: {link}")
                        elif bicim == "reel":
                            cikti(f"video: {ig_video_adresi(video)}\nkapak: {video['kapak']}\n{ig_aciklama(dil, x, ayar)}")
                        elif bicim == "short":
                            g = yt_govde(dil, x, link, ayar)
                            cikti('yerelleştirme gövdesi: ' + json.dumps(g, ensure_ascii=False, sort_keys=True))
                            cikti(f"video: {ig_video_adresi(video)}\nbaşlık: {g['snippet']['title']}\ngizlilik: {g['status']['privacyStatus']}\n{g['snippet']['description']}")
                        else:
                            cikti(f"görsel: {SITE}/{kart_ad(x['id'], icerik_dili, 'ig')}\n{ig_aciklama(dil, x, ayar)}")
                        rec = {"id": x['id'], "sosyal_tur": x.get('sosyal_tur', 'haber'), "dil": dil,
                               "platform": platform, "bicim": bicim, "durum": "tamam", "zaman": simdi.isoformat()}
                        if hesap != dil:
                            rec['hesap'] = hesap
                        if platform == 'instagram':
                            rec['icerik_dili'] = icerik_dili
                        kayit[k] = rec
                        kullanilan.add((hesap, platform))
                        if secildi:
                            secildi(k, rec)
                        hak -= 1
                        toplam += 1
                        continue
                    if not ag.yayinda_mi(sayfa):
                        cikti(f"Bekliyor (sayfa henüz yayında değil): {sayfa}")
                        continue
                    rec = {"id": x["id"], "dil": dil, "platform": platform, "bicim": bicim, "durum": "niyet",
                           "sosyal_tur": x.get('sosyal_tur', 'haber'),
                           "niyet_zamani": simdi.isoformat(timespec="seconds")}
                    if hesap != dil:
                        rec['hesap'] = hesap
                    if platform == 'instagram':
                        rec['icerik_dili'] = icerik_dili
                    kayit[k] = rec
                    kullanilan.add((hesap, platform))
                    kaydet()  # çağrıdan ÖNCE: çökse bile bir sonraki çalışma çift paylaşmaz

                    def ara(rec=rec, **alan):
                        rec.update(alan)
                        kaydet()
                    try:
                        if platform == "x":
                            sonuc = x_paylas(ag, sir, dil, x, link, ayar.get("x_baglanti", "gonderide"))
                        elif platform == "reddit":
                            sonuc = reddit_paylas(ag, sir, dil, x, link, ayar)
                        elif platform == "instagram":
                            sonuc = ig_paylas(ag, sir, dil, x, ayar, ara, video)
                        else:
                            sonuc = yt_paylas(ag, sir, dil, x, link, ayar, ara, video)
                    except PaylasimHatasi as h:
                        ig_engel = platform == "instagram" and h.kesin and meta_engel_mi(str(h))
                        if ig_engel and rec.get("kapsayici"):
                            # Instagram "engellendi" derken gönderiyi yine de yayımlayabiliyor (2026-11-23, Dawn of War IV):
                            # kayıt silinmez, "niyet" kalır; mola bitince kapsayıcı sorgulanır, yeni gönderi AÇILMAZ.
                            rec["engel"] = True
                            kaydet()
                        elif h.kesin:
                            del kayit[k]  # sunucu açıkça reddetti, yayımlanmadı: sonra yeniden denenir
                            kaydet()
                        if ig_engel:
                            # Platform kısıtı hata DEĞİL: tur kırmızıya düşmez (e-posta yağmaz), mola verilir; gönderi kuyrukta kalır.
                            saat = engel_mola_ver(engel, engel_yolu, f"{platform}|{hesap}", simdi, str(h))
                            cikti(f"::warning::Instagram ({hesap}) paylaşımı platformca engellendi; {saat} saat mola verildi, "
                                  f"gönderi kuyrukta bekliyor ({x['id']}): {str(h)[:300]}")
                        else:
                            hatalar.append(f"{ad}/{dil} {x['id']}: {h}" + ("" if h.kesin else "  [sonuç belirsiz; sonraki çalışmada platformdan sorgulanır]"))
                        hesap_hatasi.add((hesap, ad))
                        break  # bu hesapta sorun var; diğer hesaplara geç
                    _tamamla(rec, sonuc, simdi)
                    kaydet()
                    if engel.pop(f"{platform}|{hesap}", None) is not None:
                        engel_yaz(engel_yolu, engel)  # paylaşım geçti: engel bitti, mola sayacı sıfırlanır
                    if bicim in ("reel", "short") and sonuc.get("url"):
                        video_baglanti_yaz(manifest_yolu, klip_yolu, x.get('sosyal_tur'), x["id"], icerik_dili,
                                           "instagram" if bicim == "reel" else "youtube", sonuc["url"])
                    cikti(f"Paylaşıldı: {ad}/{dil} {x['id']} {sonuc.get('url') or sonuc.get('kimlik')}")
                    gonderilen += 1
                    kullanilan.add((hesap, platform))
                    hak -= 1
                    toplam += 1

    # ---- Klip/derleme: yalnız AYRI klip hesabına (YT_KLIP_* / IG_KLIP_*). Sır yoksa hiçbir yere gitmez.
    # Haber hesaplarının günlük hakkını/sırasını yemez, onlardan etkilenmez ("haber varken haber" klip hesabında yoktur).
    for platform, bicim, ad in HEDEFLER:
        if bicim == "gorsel" or not klipler:
            continue
        if not kayar["platformlar"].get(ad):
            if dry_run:
                cikti(f"[DENEME] {ad}/{KLIP_HESABI}: klip için kapalı (ayarlar.json klip.{'youtube' if platform == 'youtube' else 'instagram'}), atlandı")
            continue
        sir = hesap_sirri(tum, platform, KLIP_HESABI)
        if not sir and not (dry_run and anahtarsiz_goster):
            atlanan.append(f"{ad}/{KLIP_HESABI}")
            if dry_run:
                cikti(f"[DENEME] {ad}/{KLIP_HESABI}: klip hesabı anahtarı yok, klipler HİÇBİR hesaba gitmez "
                      f"({', '.join(eksik_sirlar(tum, platform, KLIP_HESABI))})")
            continue
        # Herkese açık (Cio'nun elle onayladığı) klip: eski kurallar AYNEN (sessiz saat, en az ara, günlük sınır).
        acik_hak = min(1, ayar.get("calisma_basina_en_fazla", 1))
        if (KLIP_HESABI, platform) in kullanilan:
            acik_hak = 0
        elif klip_sessiz_saat_mi(ayar, simdi.hour):
            cikti(f"{ad}/{KLIP_HESABI}: sessiz saat (UTC {simdi.hour}), klip bu çalışmada yayınlanmaz; sıradaki çalışmaya kalır")
            acik_hak = 0
        else:
            son_z, _, _ = son_gonderi(kayit, KLIP_HESABI, ad, gizli_haric=True)
            if son_gonderi_yakin(son_z, simdi, kayar["en_az_ara_saat"]):
                cikti(f"{ad}/{KLIP_HESABI}: son klipten bu yana {kayar['en_az_ara_saat']} saat dolmadı, sıradaki çalışmaya kalır")
                acik_hak = 0
        # Otomatik gizli (`onay.otomatik`): yalnız YouTube Shorts, `private`; sessiz saate/ara saate takılmaz, herkese açık hakkını
        # yemez, kendi günlük sınırı (`klip.gizli_gunluk_en_fazla`) vardır. Ana anahtar kapalıysa bu adaylar hiçbir yere gitmez.
        gizli_hak = 0
        if kayar["otomatik_gizli"] and bicim == "short":
            gizli_hak = max(0, min(kayar["gizli_calisma_basina_en_fazla"], kayar["gizli_gunluk_en_fazla"]
                                   - bugunku_tur_sayisi(kayit, ad, KLIP_HESABI, gun, ("klip",), gizli=True)))
        if acik_hak <= 0 and gizli_hak <= 0:
            continue
        for x in klipler:
            if (KLIP_HESABI, ad) in hesap_hatasi or (acik_hak <= 0 and gizli_hak <= 0):
                break
            tur = x["sosyal_tur"]
            gizli_aday = bool(x.get("otomatik_gizli"))
            if gizli_aday and gizli_hak <= 0:
                continue
            if not gizli_aday and acik_hak <= 0:
                continue
            if tur == "derleme" and platform != "youtube":
                continue  # derleme yalnız YouTube'a (normal video) gider
            if not gizli_aday:
                sinir_k = kayar["derleme_gunluk_en_fazla"] if tur == "derleme" else kayar["gunluk_en_fazla"].get(ad, KLIP_SINIR_VARSAYILAN.get(ad, 2))
                if bugunku_tur_sayisi(kayit, ad, KLIP_HESABI, gun, (tur,), gizli=False) >= sinir_k:
                    continue  # klip/derleme için klip hesabında ayrı günlük sınır (gizliler sayılmaz)
            k = anahtar(x, KLIP_HESABI, platform, bicim)
            if k in kayit or anahtar(x, KLIP_ICERIK_DILI, platform, bicim) in kayit:
                continue  # eskiden CTRL+A GAME hesabına gitmişse yeniden paylaşılmaz
            video = ks.bul(klip_manifest, x["id"])
            if not video or video.get("instagram" if bicim == "reel" else "youtube"):
                continue
            if (video.get("hesap") or KLIP_HESABI) != KLIP_HESABI:
                continue  # manifest başka bir hesap yazıyorsa klip hesabına gönderilmez (yalnız "klip" ya da boş)
            if (x.get("platformlar") or {}).get("instagram" if bicim == "reel" else "youtube") is False:
                continue  # onay panelinde bu platform kapatılmış
            d = KLIP_ICERIK_DILI
            if dry_run:
                cikti(f"\n[DENEME] {ad}/{KLIP_HESABI}  {x['id']}  (hesap: {KLIP_HESABI})  [{tur}]" + ("  [otomatik gizli]" if gizli_aday else "")
                      + ("" if sir else "  (hesap şifresi yok, gerçekte atlanır)"))
                if bicim == "reel":
                    cikti(f"video: {ig_video_adresi(video)}\nkapak: {video['kapak']}\n{ig_aciklama(d, x, ayar)}")
                else:
                    g = yt_govde(d, x, "", ayar)
                    cikti("klip gövdesi: " + json.dumps(g, ensure_ascii=False, sort_keys=True))
                    cikti(f"video: {ig_video_adresi(video)}\nbaşlık: {g['snippet']['title']}\ngizlilik: {g['status']['privacyStatus']}\n{g['snippet']['description']}")
                rec = {"id": x["id"], "sosyal_tur": tur, "dil": KLIP_HESABI, "hesap": KLIP_HESABI,
                       "platform": platform, "bicim": bicim, "durum": "tamam", "zaman": simdi.isoformat()}
                if gizli_aday:
                    rec["gizli"] = True
                kayit[k] = rec
                if gizli_aday:
                    gizli_hak -= 1
                else:
                    kullanilan.add((KLIP_HESABI, platform))
                    acik_hak -= 1
                if secildi:
                    secildi(k, rec)
                continue
            rec = {"id": x["id"], "dil": KLIP_HESABI, "hesap": KLIP_HESABI, "platform": platform, "bicim": bicim,
                   "durum": "niyet", "sosyal_tur": tur, "niyet_zamani": simdi.isoformat(timespec="seconds")}
            if gizli_aday:
                rec["gizli"] = True
            kayit[k] = rec
            if not gizli_aday:
                kullanilan.add((KLIP_HESABI, platform))
            kaydet()  # çağrıdan ÖNCE: çökse bile bir sonraki çalışma çift paylaşmaz

            def ara(rec=rec, **alan):
                rec.update(alan)
                kaydet()
            try:
                if bicim == "reel":
                    sonuc = ig_paylas(ag, sir, d, x, ayar, ara, video)
                else:
                    sonuc = yt_paylas(ag, sir, d, x, "", ayar, ara, video)
            except PaylasimHatasi as h:
                if h.kesin:
                    del kayit[k]  # sunucu açıkça reddetti, yayımlanmadı: sonra yeniden denenir
                    kaydet()
                if gizli_aday and h.kota and h.kesin:
                    # Kota/yetki sorunu hata DEĞİL: tur kırmızıya düşmez, kalıcı hata yazılmaz; klip sonraki çalışmada yeniden denenir.
                    cikti(f"UYARI {ad}/{KLIP_HESABI} {x['id']}: YouTube kota/yetki sorunu, otomatik gizli yükleme sonraki çalışmaya kaldı: {str(h)[:300]}")
                else:
                    hatalar.append(f"{ad}/{KLIP_HESABI} {x['id']}: {h}" + ("" if h.kesin else "  [sonuç belirsiz; sonraki çalışmada platformdan sorgulanır]"))
                hesap_hatasi.add((KLIP_HESABI, ad))
                break
            _tamamla(rec, sonuc, simdi)
            kaydet()
            if sonuc.get("url"):
                video_baglanti_yaz(manifest_yolu, klip_yolu, tur, x["id"], d, "instagram" if bicim == "reel" else "youtube", sonuc["url"])
            cikti(f"Paylaşıldı: {ad}/{KLIP_HESABI} {x['id']} {sonuc.get('url') or sonuc.get('kimlik')}" + (" [gizli]" if gizli_aday else ""))
            gonderilen += 1
            if gizli_aday:
                gizli_hak -= 1
                if gizli_yuklenen is not None:
                    gizli_yuklenen.append({"id": x["id"], "baslik": x["diller"][KLIP_ICERIK_DILI]["baslik"], "kimlik": sonuc.get("kimlik")})
            else:
                acik_hak -= 1
    return gonderilen, hatalar, atlanan


def paylasilacak_diller(ayar: dict, tum: dict | None = None) -> list[str]:
    """Ayarda açık hesapların içerik dilleri. `tum` verilirse yalnız anahtarı (kendi ya da ortak hesabı) tam olanlar kalır.
    --sayfa-bekle adımı sır görmez (env'de anahtar yok), bu yüzden orada yalnız ayara bakılır:
    anahtar sonradan eklenince bekleme de kod değişmeden o dili kapsar."""
    ortak = tuple(ayar.get("ortak_hesap_bicimleri") or BICIMLER)
    diller = set()
    for d in DILLER:
        for platform, bicim, ad in HEDEFLER:
            if not ayar['hesaplar'].get(d, {}).get(ad):
                continue
            if tum is None:
                hesap, sir = d, True
                if bicim not in ortak and ((ayar.get("hesap_esleme") or {}).get(platform) or {}).get(d, d) != d:
                    continue
            else:
                hesap, sir = hesap_coz(ayar, tum, platform, d)
                if hesap != d and bicim not in ortak:
                    continue
            if sir:
                diller.add(ig_icerik_dilleri(d, ayar)[0] if platform == 'instagram' else d)
    return [d for d in DILLER if d in diller]


def sayfa_bekle(ag, veri=None, deneme=40, aralik=15, diller=None) -> int:
    """GitHub Pages dağıtımı bitince en yeni haberin sayfası 200 verir; paylaşılacak her dilin sayfası beklenir
    (diller verilmezse hepsi, boş liste verilirse beklenecek bir şey yoktur). Süre dolarsa da 0 döner:
    asıl iş her haber için sayfayı yine kendisi sınar, hazır olmayanı sonraki çalışmaya bırakır."""
    veri = veri if veri is not None else json.loads(ICERIK.read_text(encoding="utf-8"))
    diller = list(DILLER if diller is None else diller)
    if not veri or not diller:
        return 0
    x = max(veri, key=lambda y: (y["tarih"], y["id"]))
    bekleyen = {d: f"{SITE}/{KLASOR[d]}/{x['id']}.html" for d in diller}
    for i in range(deneme):
        for d, url in list(bekleyen.items()):
            if ag.yayinda_mi(url):
                print(f"Sayfa yayında: {url}")
                del bekleyen[d]
        if not bekleyen:
            return 0
        if i < deneme - 1:
            ag.uyku(aralik)
    print("Uyarı: sayfa 10 dakikada açılmadı, devam ediliyor: " + ", ".join(bekleyen.values()))
    return 0


def benzet(ayar, veri, kayit, manifest_yolu, baslangic, saat, *, kok=KOK, cikti=print):
    """TR hesap yeteneklerini taklit eder; sır okumaz, ağa çıkmaz, kayıt yazmaz.

    Aynı yayın seçicisi ve gerçek kayıt/kota kullanılır. Videolar üretilmiş varsayılmaz.
    """
    bellek, _ = kayit_goc(copy.deepcopy(kayit), veri)
    tum = {f'{on}_TR_{ad}': 'BENZETIM' for on, adlar in (('IG', GEREKEN['instagram']), ('YT', GEREKEN['youtube'])) for ad in adlar}
    secimler = []
    cikti("BENZETİM: yalnız TR Instagram/YouTube anahtarları taklit edilir (ayardaki ortak hesap eşlemesiyle diğer diller de TR hesabından çıkar); ağ/model/yazma yok. Kota UTC gününe göre.")
    for i in range(saat):
        simdi = baslangic + timedelta(hours=i)
        aday = sk.adaylar(veri, kok, ayar, simdi.date(), simdi)
        secilen = []

        def secildi(k, r):
            secilen.append({**r, 'anahtar': k, 'saat': i})

        calistir(ayar, veri, kayit_yolu=kok / 'sosyal/gonderilenler.json', manifest_yolu=manifest_yolu,
                 tum=tum, ag=None, dry_run=True, bugun=simdi.date(), simdi=simdi,
                 kuyruk=aday, bellek=bellek, secildi=secildi, cikti=lambda *_: None)
        for r in secilen:
            cikti(f"{simdi.isoformat(timespec='minutes')} dil={r['dil']} platform={r['platform']} "
                  f"biçim={r['bicim']} tür={r['sosyal_tur']} id={r['id']}")
        for p in ('instagram', 'youtube'):
            if not any(r['platform'] == p for r in secilen):
                cikti(f"{simdi.isoformat(timespec='minutes')} dil=tr platform={p} tür=BOŞ id=- (uygun içerik/video veya günlük hak yok)")
        secimler.extend(secilen)
    sayilar = Counter(r['sosyal_tur'] for r in secimler)
    ig_saat = len({r['saat'] for r in secimler if r['platform'] == 'instagram'})
    cikti(f"ÖZET: Instagram {ig_saat}/{saat} saat; türler=" + json.dumps(dict(sayilar), ensure_ascii=False, sort_keys=True))
    return secimler


def _manifest_kapak(manifest: dict, haber_id: str, dil: str) -> str | None:
    """Manifestten haber/dil için kapak URL'si (zaten yayında olan video `beklet` olsa bile okur)."""
    if not manifest:
        return None
    taban = manifest.get("taban")
    v = ((manifest.get("videolar") or {}).get(haber_id) or {}).get(dil)
    if not (isinstance(taban, str) and taban.startswith("https://") and isinstance(v, dict)):
        return None
    ad = vs._dosya(v, "kapak")
    if not ad:
        return None
    return (taban if taban.endswith("/") else taban + "/") + ad


def yt_kapaklari_guncelle(*, kayit_yolu: pathlib.Path, manifest_yolu: pathlib.Path, tum: dict, ag,
                          dry_run: bool = False, yalniz_id: set[str] | None = None, yalniz_eksik: bool = False,
                          azami: int | None = None, cikti=print) -> dict:
    """Yayınlanmış haber YouTube Shorts videolarının kapaklarını silmeden, yalnızca thumbnails.set ile günceller.

    yalniz_eksik: yalnız dikey kapağı (sardefault.jpg) YouTube'da oluşmamış videolar. Yüklemenin hemen ardından
    yapılan thumbnails.set, video henüz Short olarak işlenmediği için yalnız yatay küçük resmi günceller; kanalın
    Shorts sekmesi o zaman videodan rastgele bir kare gösterir. İşlendikten sonra yeniden ayarlamak dikey kapağı üretir.
    azami: bir turda en çok kaç kapak (YouTube kısa sürede çok kapak yüklemeyi HTTP 429 ile keser)."""
    kayit = json.loads(kayit_yolu.read_text(encoding="utf-8")) if kayit_yolu.exists() else {}
    manifest = vs.yukle(manifest_yolu)
    hedefler = []
    for k, rec in sorted(kayit.items()):
        if rec.get("durum") != "tamam" or rec.get("platform") != "youtube" or rec.get("bicim") != "short":
            continue
        if rec.get("sosyal_tur") in KLIP_TURLERI:
            continue
        vid = rec.get("kimlik")
        hid = rec.get("id")
        dil = rec.get("dil") or (k.split("|")[1] if len(k.split("|")) == 4 else None)
        if not (vid and hid and dil):
            continue
        if yalniz_id and hid not in yalniz_id and vid not in yalniz_id:
            continue
        kapak = _manifest_kapak(manifest, hid, dil)
        hesap = kayit_hesabi(k, rec)
        hedefler.append((str(rec.get("zaman") or ""), hesap, hid, dil, vid, kapak))
    if yalniz_eksik:
        # En yeni önce; kapaksız kayıt ve dikey kapağı zaten olan video sessizce geçilir.
        hedefler = [h for h in sorted(hedefler, reverse=True) if h[5]]
        if not dry_run:
            hedefler = [h for h in hedefler if not ag.yayinda_mi(YT_DIKEY_KAPAK.format(h[4]))]
    if azami is not None:
        hedefler = hedefler[:azami]
    hedefler = [h[1:] for h in hedefler]

    ozet = {"guncellenen": 0, "hatali": 0, "atlanan": 0, "detay": []}
    if not hedefler:
        cikti("Güncellenecek yayınlanmış YouTube Shorts bulunamadı.")
        return ozet

    tok_onbellek: dict[str, str | None] = {}
    for hesap, hid, dil, vid, kapak in hedefler:
        if not kapak:
            ozet["atlanan"] += 1
            ozet["detay"].append({"id": hid, "dil": dil, "kimlik": vid, "durum": "atlandi", "not": "manifestte kapak yok"})
            cikti(f"ATLANDI {hid} ({dil}) [{vid}]: manifestte kapak yok")
            continue
        sir = hesap_sirri(tum, "youtube", hesap)
        if dry_run:
            ozet["guncellenen"] += 1
            ozet["detay"].append({"id": hid, "dil": dil, "kimlik": vid, "durum": "deneme", "kapak": kapak})
            cikti(f"[DENEME] {hid} ({dil}) [{vid}] (hesap: {hesap}) <- {kapak}" + ("" if sir else " (anahtar yok)"))
            continue
        if not sir:
            ozet["atlanan"] += 1
            ozet["detay"].append({"id": hid, "dil": dil, "kimlik": vid, "durum": "atlandi", "not": f"youtube/{hesap} anahtarı yok"})
            cikti(f"ATLANDI {hid} ({dil}) [{vid}]: youtube/{hesap} anahtarı yok ({', '.join(eksik_sirlar(tum, 'youtube', hesap))})")
            continue
        if hesap not in tok_onbellek:
            try:
                tok_onbellek[hesap] = yt_erisim(ag, sir)
            except PaylasimHatasi as h:
                tok_onbellek[hesap] = None
                cikti(f"HATA youtube/{hesap} erişim anahtarı alınamadı: {h}")
        tok = tok_onbellek[hesap]
        if not tok:
            ozet["hatali"] += 1
            ozet["detay"].append({"id": hid, "dil": dil, "kimlik": vid, "durum": "hata", "not": "erişim anahtarı alınamadı"})
            continue
        if not ag.yayinda_mi(kapak):
            ozet["hatali"] += 1
            ozet["detay"].append({"id": hid, "dil": dil, "kimlik": vid, "durum": "hata", "not": f"kapak yayında değil: {kapak}"})
            cikti(f"HATA {hid} ({dil}) [{vid}]: kapak yayında değil ({kapak})")
            continue
        hata_not = yt_kapak(ag, tok, vid, kapak)
        if hata_not:
            ozet["hatali"] += 1
            ozet["detay"].append({"id": hid, "dil": dil, "kimlik": vid, "durum": "hata", "not": hata_not})
            cikti(f"HATA {hid} ({dil}) [{vid}]: {hata_not}")
        else:
            ozet["guncellenen"] += 1
            ozet["detay"].append({"id": hid, "dil": dil, "kimlik": vid, "durum": "tamam", "kapak": kapak})
            cikti(f"GÜNCELLENDİ {hid} ({dil}) [{vid}] <- {kapak}")
    cikti(f"YouTube kapak güncellemesi bitti: {ozet['guncellenen']} güncellendi, {ozet['hatali']} hatalı, {ozet['atlanan']} atlandı.")
    return ozet


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", "--kuru", action="store_true", help="ağ çağrısı ve dosya yazma olmadan ne paylaşılacağını göster")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--saat-benzet", type=int, metavar="SAAT", help="--kuru ile ardışık saatleri bellekte taklit et (TR hesapları, sır okunmaz)")
    ap.add_argument("--baslangic", help="benzetim başlangıcı ISO tarih-saat (varsayılan şimdiki UTC saat)")
    ap.add_argument("--anahtarsiz-goster", action="store_true",
                    help="--dry-run ile: anahtarı olmayan hesapların planını da göster (önizleme)")
    ap.add_argument("--klip-manifest", metavar="YOL",
                    help="klip onay manifesti (varsayılan data/klipler.json); deneme için geçici kopya verilebilir")
    ap.add_argument("--sayfa-bekle", action="store_true", help="en yeni haberin sayfası yayında olana dek bekle (en çok 10 dk); sabit uyku yerine")
    ap.add_argument("--yt-kapak-guncelle", action="store_true",
                    help="yayınlanmış haber YouTube Shorts kapaklarını silmeden manifestteki güncel kapakla değiştir")
    ap.add_argument("--yt-sil", metavar="KIMLIK", help="tek bir YouTube videosunu kalıcı olarak sil (yalnız elle; geri alınamaz)")
    ap.add_argument("--yt-hesap", default="tr", help="--yt-sil için hesap (varsayılan tr)")
    ap.add_argument("--yt-id", help="--yt-kapak-guncelle için virgülle ayrılmış haber ya da YouTube video kimliği süzgeci")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if a.yt_sil:
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", a.yt_sil):
            ap.error("--yt-sil için 11 karakterlik tek bir YouTube video kimliği gerekir")
        sir = hesap_sirri(sirlari_oku(), "youtube", a.yt_hesap)
        if not sir:
            print(f"youtube/{a.yt_hesap} anahtarı yok; silinmedi.")
            return 1
        ag = Ag()
        try:
            durum, _, metin = ag.ham("DELETE", f"https://www.googleapis.com/youtube/v3/videos?id={a.yt_sil}",
                                     basliklar={"Authorization": f"Bearer {yt_erisim(ag, sir)}"}, zaman=60)
        except PaylasimHatasi as h:
            print(f"SİLİNEMEDİ {a.yt_sil}: {h}")
            return 1
        print(f"SİLİNDİ {a.yt_sil} (HTTP {durum})" if durum == 204 else f"SİLİNEMEDİ {a.yt_sil} (HTTP {durum}): {metin[:200]}")
        return 0 if durum == 204 else 1
    if a.yt_kapak_guncelle:
        suzgec = {s.strip() for s in a.yt_id.split(",") if s.strip()} if a.yt_id else None
        ozet = yt_kapaklari_guncelle(kayit_yolu=KAYIT, manifest_yolu=vs.MANIFEST_YOLU, tum=sirlari_oku(),
                                     ag=Ag(), dry_run=a.dry_run, yalniz_id=suzgec)
        return 0 if ozet["hatali"] == 0 else 1
    if a.saat_benzet is not None and (not a.dry_run or not 1 <= a.saat_benzet <= 168):
        ap.error('--saat-benzet için --kuru ve 1–168 saat gerekir')
    if a.baslangic and a.saat_benzet is None:
        ap.error('--baslangic yalnız --saat-benzet ile kullanılır')
    ayar = json.loads(AYAR.read_text(encoding="utf-8"))
    if a.saat_benzet is not None:
        veri = json.loads(ICERIK.read_text(encoding='utf-8'))
        kayit = json.loads(KAYIT.read_text(encoding='utf-8')) if KAYIT.exists() else {}
        simdi = sk.zaman(a.baslangic) if a.baslangic else datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        if simdi is None:
            ap.error('geçersiz --baslangic')
        secimler = benzet(ayar, veri, kayit, vs.MANIFEST_YOLU, simdi, a.saat_benzet)
        return 0 if len({r['saat'] for r in secimler if r['platform'] == 'instagram'}) == a.saat_benzet else 1
    if a.sayfa_bekle:
        return sayfa_bekle(Ag(), diller=paylasilacak_diller(ayar))
    veri = json.loads(ICERIK.read_text(encoding="utf-8"))
    simdi = datetime.now(timezone.utc)
    kuyruk = sk.adaylar(veri, KOK, ayar, simdi.date(), simdi)
    gizli_yuklenen: list = []
    gonderilen, hatalar, atlanan = calistir(ayar, veri, kayit_yolu=KAYIT, manifest_yolu=vs.MANIFEST_YOLU, tum=sirlari_oku(), ag=Ag(),
                                            dry_run=a.dry_run, bugun=simdi.date(), simdi=simdi,
                                            anahtarsiz_goster=a.anahtarsiz_goster, kuyruk=kuyruk,
                                            klip_yolu=pathlib.Path(a.klip_manifest) if a.klip_manifest else None,
                                            gizli_yuklenen=gizli_yuklenen)
    if atlanan and not a.dry_run:
        print("Anahtar yok, atlandı: " + ", ".join(atlanan))
    print(f"Bitti: {gonderilen} gönderi.")
    if gizli_yuklenen and not a.dry_run:
        klip_bildirimi_gonder(gizli_yuklenen)  # tur sonunda tek mesaj; hata turu düşürmez
    if not a.dry_run:
        # Önceki turlarda yüklenip dikey kapağı oluşmamış Shorts'ları onar (en iyi çaba; paylaşım sonucunu etkilemez).
        try:
            yt_kapaklari_guncelle(kayit_yolu=KAYIT, manifest_yolu=vs.MANIFEST_YOLU, tum=sirlari_oku(), ag=Ag(),
                                  yalniz_eksik=True, azami=YT_KAPAK_ONARIM_AZAMI)
        except Exception as h:  # noqa: BLE001 - kapak onarımı paylaşım turunu düşürmemeli
            print(f"Kapak onarımı atlandı: {h}")
    if hatalar:
        print("HATALAR:\n  " + "\n  ".join(hatalar))
        return 1
    return 0


BILDIRIM_SIRRI = "KLIP_BILDIRIM_ADRESI"


def _json_gonder(adres: str, govde: dict, zaman: float = 20) -> int:
    """JSON POST (yalnız standart kütüphane). Adres hata iletisine/loga ASLA yazılmaz. -> HTTP durum kodu; ağ hatasında OSError."""
    req = urllib.request.Request(adres, data=json.dumps(govde).encode("utf-8"), method="POST",
                                 headers={"Content-Type": "application/json", "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=zaman) as r:
            return r.status
    except urllib.error.HTTPError as h:
        return h.code


def klip_bildirimi_gonder(gizli: list[dict], ortam=None, cikti=print, gonder=None) -> bool:
    """Otomatik gizli yüklenen Shorts için tek Telegram mesajı (n8n webhook, sır KLIP_BILDIRIM_ADRESI).
    Yükleme yoksa mesaj yok; sır yoksa sessizce atlanır; hata turu DÜŞÜRMEZ (uyarı loglanır, adres yazılmaz). -> gönderildi mi"""
    gizli = [g for g in (gizli or []) if g.get("kimlik")]
    if not gizli:
        return False
    adres = ((os.environ if ortam is None else ortam).get(BILDIRIM_SIRRI) or "").strip()
    if not adres.startswith(("http://", "https://")):
        cikti(f"UYARI: Telegram bildirimi atlandı ({BILDIRIM_SIRRI} sırrı yok); {len(gizli)} gizli Shorts yüklendi.")
        return False
    try:
        kod = (gonder or _json_gonder)(adres, {"metin": ks.bildirim_metni(gizli)[:3500]})
    except Exception as h:  # noqa: BLE001 — bildirim hatası turu düşürmez; adres hata metnine sızmasın diye yalnız tür yazılır
        cikti(f"UYARI: Telegram bildirimi gönderilemedi ({type(h).__name__}); {len(gizli)} gizli Shorts yüklendi.")
        return False
    if 200 <= kod < 300:
        cikti(f"KLIP_BILDIRIM: gönderildi ({len(gizli)} gizli Shorts)")
        return True
    cikti(f"UYARI: Telegram bildirimi gönderilemedi (HTTP {kod}); {len(gizli)} gizli Shorts yüklendi.")
    return False


def selftest() -> int:
    # X (Twitter) resmî OAuth 1.0a imza örneği: "Creating a signature" belgesindeki değerler.
    bas = oauth1_baslik(
        "POST", "https://api.twitter.com/1.1/statuses/update.json",
        "xvz1evFS4wEEPTGEFPHBog", "kAcSOqF21Fu85e7zjz7ZN2U4ZRhfV3WpwPAoE3Z7kBw",
        "370773112-GmHxMAgYyLbNEtIKZeRNFsMKPR9EyMZeS9weJAEb", "LswwdoUaIvS8ltyTt5jkRh4J50vUPVVHtR2YPi5kE",
        params={"status": "Hello Ladies + Gentlemen, a signed OAuth request!", "include_entities": "true"},
        nonce="kYjzVBB8Y0ZFabxSWbWovY3uYSQ2pTgmZeNu2VS4cg", zaman=1318622958,
    )
    beklenen = 'oauth_signature="hCtSmYh%2BiHYCEqBWrE7C7hYmtUk%3D"'
    ok = beklenen in bas
    print("OAuth imza testi:", "GEÇTİ" if ok else f"KALDI\n{bas}")
    veri = json.loads(ICERIK.read_text(encoding="utf-8"))
    uzun = 0
    for x in veri:
        for d in DILLER:
            for mod in ("gonderide", "profilde"):
                m = x_metin(d, x, paylasim_linki(d, x, "x"), mod)
                n = len(m) - (len(paylasim_linki(d, x, "x")) - 23 if mod == "gonderide" else 0)
                if n > 280:
                    uzun += 1
                    print("UZUN:", d, x["id"], n)
            g = yt_govde(d, x, paylasim_linki(d, x, "youtube"), {})
            if len(ig_aciklama(d, x)) > 2200 or len(g["snippet"]["title"]) > 100 or len(g["snippet"]["description"].encode()) > 5000:
                uzun += 1
                print("UZUN (IG/YT):", d, x["id"])
    print("Metin uzunluk testi:", "GEÇTİ" if not uzun else f"KALDI ({uzun})")
    # kayıt göçü ve anahtar
    ornek = [{"id": "a-1", "otomasyon": {"konu": "konu-a"}}, {"id": "b-2"}]
    yeni, goc = kayit_goc({"a-1|tr|instagram": {"zaman": "2026-11-14T10:00:00+00:00", "kimlik": "1"},
                           "b-2|en|x|gorsel": {"durum": "tamam"}}, ornek)
    goc_ok = (goc and yeni["konu-a|tr|instagram|gorsel"]["durum"] == "tamam" and "b-2|en|x|gorsel" in yeni
              and anahtar(ornek[0], "tr", "instagram", "reel") == "konu-a|tr|instagram|reel")
    print("Kayıt göçü testi:", "GEÇTİ" if goc_ok else "KALDI")
    return 0 if ok and not uzun and goc_ok else 1


if __name__ == "__main__":
    sys.exit(main())
