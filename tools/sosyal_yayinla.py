#!/usr/bin/env python3
"""Sosyal paylaşım: data/icerik.json'daki yeni haberleri X, Reddit, Instagram (görsel + Reels) ve YouTube Shorts'a gönderir.

Her dil ayrı hesaptır (tr, en, fr, es). Bir hesabın anahtarları yoksa o hesap atlanır ("anahtar yok, atlandı" diye
çıktıda görünür); anahtarlar eklenince paylaşım kod değişmeden başlar.
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

Gerekli sırlar (DIL = TR, EN, FR, ES):
  X_DIL_API_KEY, X_DIL_API_SECRET, X_DIL_ACCESS_TOKEN, X_DIL_ACCESS_SECRET
  REDDIT_DIL_CLIENT_ID, REDDIT_DIL_CLIENT_SECRET, REDDIT_DIL_USERNAME, REDDIT_DIL_PASSWORD
  IG_DIL_USER_ID, IG_DIL_TOKEN                      (görsel ve Reels için aynı hesap)
  YT_DIL_CLIENT_ID, YT_DIL_CLIENT_SECRET, YT_DIL_REFRESH_TOKEN
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
from sosyal_derle import DILLER, GORUNEN, KLASOR, M, SITE, kart_ad  # noqa: E402
import video_site as vs  # noqa: E402
import sosyal_kuyruk as sk  # noqa: E402

KAYIT = KOK / "sosyal" / "gonderilenler.json"
AYAR = KOK / "sosyal" / "ayarlar.json"
ICERIK = KOK / "data" / "icerik.json"
UA = "rockstargtavi-sosyal/1.0"
BICIMLER = ("gorsel", "reel", "short")
MAX_VIDEO_BAYT = 256 * 1024 * 1024

METIN = {
    "tr": {"devam": "Ayrıntılar ve kaynak:", "profil": "Ayrıntılar ve kaynak profildeki bağlantıda.", "ig_link": "Ayrıntılar ve resmî kaynak: profildeki bağlantı"},
    "en": {"devam": "Details and source:", "profil": "Details and source: link in bio.", "ig_link": "Details and official source: link in bio"},
    "fr": {"devam": "Détails et source :", "profil": "Détails et source : lien dans la bio.", "ig_link": "Détails et source officielle : lien dans la bio"},
    "es": {"devam": "Detalles y fuente:", "profil": "Detalles y fuente: enlace en la bio.", "ig_link": "Detalles y fuente oficial: enlace en la bio"},
}


class PaylasimHatasi(Exception):
    """kesin=True: sunucu isteği açıkça reddetti (4xx), hiçbir şey yayımlanmadı, yeniden denenebilir.
    kesin=False: sonuç bilinmiyor (zaman aşımı, bağlantı kopması, 5xx); paylaşım yapılmış olabilir."""

    def __init__(self, mesaj: str, kesin: bool = False):
        super().__init__(mesaj)
        self.kesin = kesin


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
            raise PaylasimHatasi(f"{method} {url.split('?')[0]} → HTTP {h.code}: {ham[:400]}", kesin=400 <= h.code < 500) from None
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
            raise PaylasimHatasi(f"{method} {url.split('?')[0]} → HTTP {h.code}: {metin[:400]}", kesin=400 <= h.code < 500 and h.code != 404) from None
        except (urllib.error.URLError, TimeoutError, OSError) as u:
            raise PaylasimHatasi(f"{method} {url.split('?')[0]} → bağlantı hatası: {getattr(u, 'reason', u)}") from None

    def indir(self, url: str) -> bytes:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                veri = r.read(MAX_VIDEO_BAYT + 1)
        except (urllib.error.URLError, TimeoutError, OSError) as u:
            raise PaylasimHatasi(f"video indirilemedi ({url}): {getattr(u, 'reason', u)}", kesin=True) from None
        if len(veri) > MAX_VIDEO_BAYT:
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
    t = x["diller"][dil]
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
        veri={"api_type": "json", "kind": "link", "sr": topluluk, "title": x["diller"][dil]["baslik"][:300],
              "url": link, "resubmit": "true", "sendreplies": "false"},
        basliklar={**ua, "Authorization": f"bearer {tok['access_token']}"},
    )
    j = (cevap or {}).get("json", {}) if isinstance(cevap, dict) else {}
    if j.get("errors"):
        raise PaylasimHatasi(f"Reddit gönderim hatası: {j['errors']}", kesin=True)
    d = j.get("data", {})
    return {"kimlik": d.get("name") or d.get("id"), "url": d.get("url")}


# ---------------------------------------------------------------- Instagram (görsel + Reels)
def ig_aciklama(dil, x) -> str:
    t = x["diller"][dil]
    kay = ", ".join(s["ad"] for s in x["kaynaklar"])
    etiket = " ".join(etiketler(dil, x))
    son = f"\n\n{M[dil]['kaynak']}: {kay[:240]}\n{paylasim_linki(dil, x, 'instagram')}\n\n{etiket}"
    bas = t['baslik'][:300]
    govde = t.get('ozet', '')[:max(0, 2200 - len(bas) - len(son) - 2)]
    return f"{bas}\n\n{govde}{son}"


def etiketler(dil, x):
    tags = list(dict.fromkeys(t for t in x['diller'][dil].get('etiketler', [])
                              if re.fullmatch(r'#[\w]+', t)))[:5]
    for t in sk.SABLON[dil]['etiket'].split():
        if len(tags) >= 3:
            break
        if t not in tags:
            tags.append(t)
    return tags


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
        medya = f"{SITE}/{kart_ad(x['id'], dil, 'ig')}"
        veri = {"image_url": medya}
    if not ag.yayinda_mi(medya):
        raise PaylasimHatasi(f"Instagram medyası yayında değil: {medya}", kesin=True)
    veri.update({"caption": ig_aciklama(dil, x), "access_token": sir["TOKEN"]})
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
    b = re.sub(r"[<>]", "", x["diller"][dil]["baslik"]).strip()
    return b if len(b) <= 100 else b[:99].rstrip() + "…"


def yt_aciklama(dil, x, link) -> str:
    t = x["diller"][dil]
    kay = ", ".join(s["ad"] for s in x["kaynaklar"])
    etiket = " ".join(etiketler(dil, x))
    metin = f"{t['ozet']}\n\n{METIN[dil]['devam']} {link}\n{M[dil]['kaynak']}: {kay}\n\n{etiket} #Shorts".strip()
    return re.sub(r"[<>]", "", metin)[:4900]


def yt_etiketler(dil, x) -> list:
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
    return {
        "snippet": {"title": yt_baslik(dil, x), "description": yt_aciklama(dil, x, link), "tags": yt_etiketler(dil, x),
                    "categoryId": "20", "defaultLanguage": dil, "defaultAudioLanguage": dil},
        "status": {"privacyStatus": gizlilik, "selfDeclaredMadeForKids": False, "containsSyntheticMedia": True},
    }


def yt_erisim(ag, sir) -> str:
    _, c = ag.istek("POST", "https://oauth2.googleapis.com/token",
                    veri={"client_id": sir["CLIENT_ID"], "client_secret": sir["CLIENT_SECRET"],
                          "refresh_token": sir["REFRESH_TOKEN"], "grant_type": "refresh_token"})
    tok = c.get("access_token") if isinstance(c, dict) else None
    if not tok:
        raise PaylasimHatasi(f"YouTube erişim anahtarı alınamadı: {str(c)[:200]}", kesin=True)
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


def yt_paylas(ag, sir, dil, x, link, ayar, ara, video) -> dict:
    medya = ig_video_adresi(video)
    if not ag.yayinda_mi(medya):
        raise PaylasimHatasi(f"YouTube videosu yayında değil: {medya}", kesin=True)
    bayt = ag.indir(medya)
    tok = yt_erisim(ag, sir)
    durum, bas, metin = ag.ham(
        "POST", f"{YT_UST}?uploadType=resumable&part=snippet,status",
        govde=json.dumps(yt_govde(dil, x, link, ayar)).encode(),
        basliklar={"Authorization": f"Bearer {tok}", "Content-Type": "application/json; charset=UTF-8",
                   "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(len(bayt))}, zaman=60)
    oturum = bas.get("location")
    if not oturum or not oturum.startswith("https://"):
        raise PaylasimHatasi(f"YouTube yükleme oturumu açılamadı (HTTP {durum}): {metin[:200]}", kesin=True)
    ara(oturum=oturum, boyut=len(bayt))  # baytlar gitmeden önce kaydedilir
    return yt_yukle(ag, oturum, bayt)


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
    return yeni, degisti


def kayit_yaz(yol: pathlib.Path, kayit: dict) -> None:
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(json.dumps(kayit, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def sinir_adi(k: str) -> str:
    _, _, platform, bicim = k.split("|")
    return {"reel": "instagram_reel", "short": "youtube"}.get(bicim, platform)


def bugunku_sayi(kayit: dict, ad: str, dil: str, gun: str) -> int:
    n = 0
    for k, v in kayit.items():
        p = k.split("|")
        if len(p) == 4 and p[1] == dil and sinir_adi(k) == ad and v.get("durum") in ("tamam", "niyet", "elle_bak") \
                and (v.get("niyet_zamani") or v.get("zaman") or "")[:10] == gun:
            n += 1
    return n


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


def uzlastir(ag, kayit, tum, ayar, manifest_yolu, kaydet, simdi) -> list:
    """Önceki çalışmadan kalan "niyet" kayıtlarını platformdan sorgulayıp tamamlar ya da elle_bak yapar.
    Hiçbir koşulda yeniden paylaşım denemez (yalnız zaten yaratılmış kapsayıcı/oturum devam ettirilir)."""
    mesajlar = []
    for k, rec in list(kayit.items()):
        if rec.get("durum") != "niyet":
            continue
        platform, bicim, dil = rec.get("platform"), rec.get("bicim"), rec.get("dil")
        sir = hesap_sirri(tum, platform, dil) if platform in ONEK_SIR else None

        def elle(neden):
            rec.update(durum="elle_bak", **{"not": neden})
            kaydet()
            mesajlar.append(f"ELLE BAK {k}: {neden}")

        if platform == "instagram" and rec.get("kapsayici"):
            if not sir:
                continue
            surum = ayar.get("instagram_api_surumu", "v27.0")
            try:
                kod = ig_durum(ag, sir, surum, rec["kapsayici"])
                if kod == "PUBLISHED":
                    _tamamla(rec, {"kimlik": None, "url": None, "not": "kapsayıcı PUBLISHED çıktı; kimlik bilinmiyor"}, simdi)
                elif kod == "FINISHED":
                    _tamamla(rec, ig_yayimla(ag, sir, surum, rec["kapsayici"]), simdi)
                elif kod in ("ERROR", "EXPIRED"):
                    elle(f"Instagram kapsayıcı {kod}; yayımlanmadı, kontrol edip gerekirse kaydı silin")
                    continue
                else:
                    ilk = datetime.fromisoformat(rec["niyet_zamani"])
                    if simdi - ilk > timedelta(hours=24):
                        elle("Instagram kapsayıcı 24 saatten uzun işleniyor")
                    continue
            except PaylasimHatasi as h:
                mesajlar.append(f"Uzlaştırma bekliyor {k}: {h}")
                continue
            kaydet()
            if bicim == "reel" and rec.get("url"):
                vs.baglanti_yaz(manifest_yolu, rec["id"], dil, "instagram", rec["url"])
        elif platform == "youtube" and rec.get("oturum") and rec.get("boyut"):
            try:
                video = vs.bul(vs.yukle(manifest_yolu), rec["id"], dil)
                durum, s = yt_oturum_sorgu(ag, rec["oturum"], rec["boyut"])
                if durum == "surmekte":
                    if not video:
                        elle("YouTube yüklemesi yarım ama video manifestte yok")
                        continue
                    bayt = ag.indir(ig_video_adresi(video))
                    if len(bayt) != rec["boyut"]:
                        elle("YouTube yüklemesi yarım ve video dosyası değişmiş")
                        continue
                    s = yt_yukle(ag, rec["oturum"], bayt, s)
            except PaylasimHatasi as h:
                if "HTTP 404" in str(h) or "HTTP 410" in str(h):
                    elle("YouTube yükleme oturumu bulunamadı (süresi dolmuş olabilir); YouTube Studio'da kontrol edin")
                else:
                    mesajlar.append(f"Uzlaştırma bekliyor {k}: {h}")
                continue
            _tamamla(rec, s, simdi)
            kaydet()
            vs.baglanti_yaz(manifest_yolu, rec["id"], dil, "youtube", s["url"])
        else:
            elle("yanıt kaybolmuş olabilir ve platformdan doğrulanamıyor; platformda gönderiye bakın, yoksa kaydı silin")
    return mesajlar


# ---------------------------------------------------------------- akış
def calistir(ayar: dict, veri: list, *, kayit_yolu: pathlib.Path, manifest_yolu: pathlib.Path, tum: dict, ag, dry_run: bool,
            bugun: date, simdi: datetime, cikti=print, anahtarsiz_goster: bool = False,
            kuyruk=None, bellek=None, secildi=None) -> tuple[int, list, list]:
    ham = json.loads(kayit_yolu.read_text(encoding="utf-8")) if kayit_yolu.exists() else {}
    kayit, goc = kayit_goc(ham, veri) if bellek is None else (bellek, False)
    # Kütüphane çağıran eski istemciler yalnız verdikleri haberleri işler.
    # CLI ve derleyici ortak kuyruk üreticisini açıkça kullanır.
    kuyruk = kuyruk if kuyruk is not None else sk.adaylar(veri, kayit_yolu.parent.parent, ayar, bugun, simdi)
    manifest = vs.yukle(manifest_yolu)
    gun = simdi.strftime("%Y-%m-%d")
    hatalar, atlanan, gonderilen = [], [], 0

    def kaydet():
        if not dry_run:
            kayit_yaz(kayit_yolu, kayit)

    if goc:
        kaydet()
    if not dry_run:
        onceki = {k for k, r in kayit.items() if r.get('durum') == 'niyet'}
        hatalar += uzlastir(ag, kayit, tum, ayar, manifest_yolu, kaydet, simdi)
        manifest = vs.yukle(manifest_yolu)
    else:
        onceki = set()
    kullanilan = {(k.split('|')[1], k.split('|')[2]) for k in onceki if kayit[k].get('durum') == 'tamam'}

    for dil in DILLER:
        for platform, bicim, ad in HEDEFLER:
            if not ayar["hesaplar"].get(dil, {}).get(ad):
                continue
            sir = hesap_sirri(tum, platform, dil)
            if not sir and not (dry_run and anahtarsiz_goster):
                atlanan.append(f"{ad}/{dil}")
                if dry_run:
                    cikti(f"[DENEME] {ad}/{dil}: anahtar yok, atlandı ({', '.join(eksik_sirlar(tum, platform, dil))})")
                continue
            if (dil, platform) in kullanilan:
                continue
            sinir = (ayar.get("gunluk_en_fazla") or {}).get(ad, VARSAYILAN_SINIR[ad])
            hak = min(1, ayar.get("calisma_basina_en_fazla", 1), sinir - bugunku_sayi(kayit, ad, dil, gun))
            for x in kuyruk:
                if hak <= 0:
                    break
                if not sk.uygun(x, dil, platform, kayit, simdi):
                    continue
                k = anahtar(x, dil, platform, bicim)
                if k in kayit:
                    continue
                video = None
                if bicim != "gorsel":
                    if not video_hakki(x, ayar):
                        continue  # hype puanı eşiğin altında: bu haber yalnız görsel gönderi alır
                    video = vs.bul(manifest, x["id"], dil)
                    if not video:
                        continue  # bu haber/dil için video henüz yok
                link = paylasim_linki(dil, x, platform)
                sayfa = sayfa_adresi(dil, x)
                if dry_run:
                    cikti(f"\n[DENEME] {ad}/{dil}  {x['id']}" + ("" if sir else "  (hesap şifresi yok, gerçekte atlanır)"))
                    if platform == "x":
                        cikti(x_metin(dil, x, link, ayar.get("x_baglanti", "gonderide")))
                    elif platform == "reddit":
                        cikti(f"başlık: {x['diller'][dil]['baslik']}\nbağlantı: {link}")
                    elif bicim == "reel":
                        cikti(f"video: {ig_video_adresi(video)}\nkapak: {video['kapak']}\n{ig_aciklama(dil, x)}")
                    elif bicim == "short":
                        g = yt_govde(dil, x, link, ayar)
                        cikti(f"video: {ig_video_adresi(video)}\nbaşlık: {g['snippet']['title']}\ngizlilik: {g['status']['privacyStatus']}\n{g['snippet']['description']}")
                    else:
                        cikti(f"görsel: {SITE}/{kart_ad(x['id'], dil, 'ig')}\n{ig_aciklama(dil, x)}")
                    rec = {"id": x['id'], "sosyal_tur": x.get('sosyal_tur', 'haber'), "dil": dil,
                           "platform": platform, "bicim": bicim, "durum": "tamam", "zaman": simdi.isoformat()}
                    kayit[k] = rec
                    kullanilan.add((dil, platform))
                    if secildi:
                        secildi(k, rec)
                    hak -= 1
                    continue
                if not ag.yayinda_mi(sayfa):
                    cikti(f"Bekliyor (sayfa henüz yayında değil): {sayfa}")
                    continue
                rec = {"id": x["id"], "dil": dil, "platform": platform, "bicim": bicim, "durum": "niyet",
                       "sosyal_tur": x.get('sosyal_tur', 'haber'),
                       "niyet_zamani": simdi.isoformat(timespec="seconds")}
                kayit[k] = rec
                kullanilan.add((dil, platform))
                kaydet()  # çağrıdan ÖNCE: çökse bile bir sonraki çalışma çift paylaşmaz

                def ara(**alan):
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
                    if h.kesin:
                        del kayit[k]  # sunucu açıkça reddetti, yayımlanmadı: sonra yeniden denenir
                        kaydet()
                    hatalar.append(f"{ad}/{dil} {x['id']}: {h}" + ("" if h.kesin else "  [sonuç belirsiz; sonraki çalışmada platformdan sorgulanır]"))
                    break  # bu hesapta sorun var; diğer hesaplara geç
                _tamamla(rec, sonuc, simdi)
                kaydet()
                if bicim in ("reel", "short") and sonuc.get("url"):
                    vs.baglanti_yaz(manifest_yolu, x["id"], dil, "instagram" if bicim == "reel" else "youtube", sonuc["url"])
                cikti(f"Paylaşıldı: {ad}/{dil} {x['id']} {sonuc.get('url') or sonuc.get('kimlik')}")
                gonderilen += 1
                kullanilan.add((dil, platform))
                hak -= 1
    return gonderilen, hatalar, atlanan


def paylasilacak_diller(ayar: dict, tum: dict | None = None) -> list[str]:
    """En az bir hesabı ayarda açık olan diller. `tum` verilirse yalnız anahtarı da tam olanlar kalır.
    --sayfa-bekle adımı sır görmez (env'de anahtar yok), bu yüzden orada yalnız ayara bakılır:
    anahtar sonradan eklenince bekleme de kod değişmeden o dili kapsar."""
    return [d for d in DILLER
            if any(ayar["hesaplar"].get(d, {}).get(ad) and (tum is None or hesap_sirri(tum, platform, d))
                   for platform, _, ad in HEDEFLER)]


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
    cikti("BENZETİM: yalnız TR Instagram/YouTube hesapları taklit edilir; ağ/model/yazma yok. Kota UTC gününe göre.")
    cikti("Anahtar yok, atlandı: en, fr, es (benzetim hesap profili).")
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
    ap.add_argument("--sayfa-bekle", action="store_true", help="en yeni haberin sayfası yayında olana dek bekle (en çok 10 dk); sabit uyku yerine")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
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
    gonderilen, hatalar, atlanan = calistir(ayar, veri, kayit_yolu=KAYIT, manifest_yolu=vs.MANIFEST_YOLU, tum=sirlari_oku(), ag=Ag(),
                                            dry_run=a.dry_run, bugun=simdi.date(), simdi=simdi,
                                            anahtarsiz_goster=a.anahtarsiz_goster, kuyruk=kuyruk)
    if atlanan and not a.dry_run:
        print("Anahtar yok, atlandı: " + ", ".join(atlanan))
    print(f"Bitti: {gonderilen} gönderi.")
    if hatalar:
        print("HATALAR:\n  " + "\n  ".join(hatalar))
        return 1
    return 0


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
