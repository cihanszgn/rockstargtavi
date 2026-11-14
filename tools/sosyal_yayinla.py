#!/usr/bin/env python3
"""Sosyal paylaşım: data/icerik.json'daki yeni haberleri X, Reddit ve Instagram'a gönderir.

Her dil ayrı hesaptır (tr, en, fr, es). Bir hesabın şifreleri yoksa o hesap sessizce atlanır.
Şifreler ortam değişkeninden okunur (GitHub Actions: her sır adıyla env olarak verilir).

  python tools/sosyal_yayinla.py --dry-run     # ne paylaşılacağını gösterir, hiçbir şey göndermez
  python tools/sosyal_yayinla.py               # gerçekten paylaşır, sosyal/gonderilenler.json'a yazar
  python tools/sosyal_yayinla.py --selftest    # OAuth imzasını resmî örnekle sınar

Gerekli sırlar (DIL = TR, EN, FR, ES):
  X_DIL_API_KEY, X_DIL_API_SECRET, X_DIL_ACCESS_TOKEN, X_DIL_ACCESS_SECRET
  REDDIT_DIL_CLIENT_ID, REDDIT_DIL_CLIENT_SECRET, REDDIT_DIL_USERNAME, REDDIT_DIL_PASSWORD
  IG_DIL_USER_ID, IG_DIL_TOKEN
Yalnız Python standart kütüphanesi kullanılır.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import pathlib
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone

KOK = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK / "tools"))
from sosyal_derle import DILLER, GORUNEN, KLASOR, M, SITE, kart_ad  # noqa: E402

KAYIT = KOK / "sosyal" / "gonderilenler.json"
UA = "rockstargtavi-sosyal/1.0"

METIN = {
    "tr": {"devam": "Ayrıntılar ve kaynak:", "profil": "Ayrıntılar ve kaynak profildeki bağlantıda.", "ig_link": "Ayrıntılar ve resmî kaynak: profildeki bağlantı"},
    "en": {"devam": "Details and source:", "profil": "Details and source: link in bio.", "ig_link": "Details and official source: link in bio"},
    "fr": {"devam": "Détails et source :", "profil": "Détails et source : lien dans la bio.", "ig_link": "Détails et source officielle : lien dans la bio"},
    "es": {"devam": "Detalles y fuente:", "profil": "Detalles y fuente: enlace en la bio.", "ig_link": "Detalles y fuente oficial: enlace en la bio"},
}


class PaylasimHatasi(Exception):
    pass


# ---------------------------------------------------------------- HTTP
def istek(method: str, url: str, *, veri=None, json_govde=None, basliklar=None, zaman=30):
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
        raise PaylasimHatasi(f"{method} {url.split('?')[0]} → HTTP {h.code}: {ham[:400]}") from None
    except urllib.error.URLError as u:
        raise PaylasimHatasi(f"{method} {url.split('?')[0]} → bağlantı hatası: {u.reason}") from None


def yayinda_mi(url: str) -> bool:
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status == 200
    except Exception:
        return False


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


def x_paylas(sir, dil, x, link, mod) -> dict:
    url = "https://api.x.com/2/tweets"
    bas = oauth1_baslik("POST", url, sir["API_KEY"], sir["API_SECRET"], sir["ACCESS_TOKEN"], sir["ACCESS_SECRET"])
    _, cevap = istek("POST", url, json_govde={"text": x_metin(dil, x, link, mod)}, basliklar={"Authorization": bas})
    pid = cevap.get("data", {}).get("id") if isinstance(cevap, dict) else None
    if not pid:
        raise PaylasimHatasi(f"X beklenmeyen yanıt: {str(cevap)[:300]}")
    return {"kimlik": pid, "url": f"https://x.com/i/web/status/{pid}"}


# ---------------------------------------------------------------- Reddit
def reddit_paylas(sir, dil, x, link, ayar) -> dict:
    kullanici = sir["USERNAME"]
    ua = {"User-Agent": f"web:rockstargtavi-sosyal:1.0 (by /u/{kullanici})"}
    kimlik = base64.b64encode(f"{sir['CLIENT_ID']}:{sir['CLIENT_SECRET']}".encode()).decode()
    _, tok = istek(
        "POST", "https://www.reddit.com/api/v1/access_token",
        veri={"grant_type": "password", "username": kullanici, "password": sir["PASSWORD"]},
        basliklar={**ua, "Authorization": f"Basic {kimlik}"},
    )
    if not isinstance(tok, dict) or "access_token" not in tok:
        raise PaylasimHatasi(f"Reddit giriş başarısız: {str(tok)[:300]}")
    topluluk = (ayar.get("reddit_topluluk") or {}).get(dil) or f"u_{kullanici}"
    _, cevap = istek(
        "POST", "https://oauth.reddit.com/api/submit",
        veri={"api_type": "json", "kind": "link", "sr": topluluk, "title": x["diller"][dil]["baslik"][:300],
              "url": link, "resubmit": "true", "sendreplies": "false"},
        basliklar={**ua, "Authorization": f"bearer {tok['access_token']}"},
    )
    j = (cevap or {}).get("json", {}) if isinstance(cevap, dict) else {}
    if j.get("errors"):
        raise PaylasimHatasi(f"Reddit gönderim hatası: {j['errors']}")
    d = j.get("data", {})
    return {"kimlik": d.get("name") or d.get("id"), "url": d.get("url")}


# ---------------------------------------------------------------- Instagram
def ig_aciklama(dil, x) -> str:
    t = x["diller"][dil]
    kay = ", ".join(s["ad"] for s in x["kaynaklar"])
    etiket = " ".join(t.get("etiketler", []) + ["#" + ("OyunHaberleri" if dil == "tr" else "GamingNews" if dil == "en" else "ActuJeuxVideo" if dil == "fr" else "NoticiasVideojuegos")])
    metin = f"{t['baslik']}\n\n{t['metin']}\n\n{M[dil]['kaynak']}: {kay}\n{METIN[dil]['ig_link']} ({GORUNEN})\n\n{etiket}"
    return metin[:2200]


def ig_paylas(sir, dil, x, ayar) -> dict:
    surum = ayar.get("instagram_api_surumu", "v27.0")
    taban = f"https://graph.instagram.com/{surum}/{sir['USER_ID']}"
    gorsel = f"{SITE}/{kart_ad(x['id'], dil, 'ig')}"
    if not yayinda_mi(gorsel):
        raise PaylasimHatasi(f"Instagram görseli yayında değil: {gorsel}")
    _, kap = istek("POST", f"{taban}/media", veri={"image_url": gorsel, "caption": ig_aciklama(dil, x), "access_token": sir["TOKEN"]})
    kid = kap.get("id") if isinstance(kap, dict) else None
    if not kid:
        raise PaylasimHatasi(f"Instagram kapsayıcı oluşmadı: {str(kap)[:300]}")
    for _ in range(12):  # en çok ~1 dakika hazır olmasını bekle
        _, durum = istek("GET", f"https://graph.instagram.com/{surum}/{kid}?" + urllib.parse.urlencode({"fields": "status_code", "access_token": sir["TOKEN"]}))
        kod = durum.get("status_code") if isinstance(durum, dict) else None
        if kod == "FINISHED":
            break
        if kod in ("ERROR", "EXPIRED"):
            raise PaylasimHatasi(f"Instagram görseli işleyemedi: {durum}")
        time.sleep(5)
    _, yay = istek("POST", f"{taban}/media_publish", veri={"creation_id": kid, "access_token": sir["TOKEN"]})
    mid = yay.get("id") if isinstance(yay, dict) else None
    if not mid:
        raise PaylasimHatasi(f"Instagram yayımlanamadı: {str(yay)[:300]}")
    return {"kimlik": mid, "url": None}


# ---------------------------------------------------------------- akış
GEREKEN = {
    "x": ("API_KEY", "API_SECRET", "ACCESS_TOKEN", "ACCESS_SECRET"),
    "reddit": ("CLIENT_ID", "CLIENT_SECRET", "USERNAME", "PASSWORD"),
    "instagram": ("USER_ID", "TOKEN"),
}
ONEK_SIR = {"x": "X", "reddit": "REDDIT", "instagram": "IG"}


def sirlari_oku() -> dict:
    tum = {}
    ham = os.environ.get("SOSYAL_SIRLAR")
    if ham:
        try:
            tum.update({k: v for k, v in json.loads(ham).items() if isinstance(v, str)})
        except json.JSONDecodeError:
            print("Uyarı: SOSYAL_SIRLAR okunamadı.")
    for k, v in os.environ.items():
        if k.startswith(("X_", "REDDIT_", "IG_")):
            tum.setdefault(k, v)
    return tum


def hesap_sirri(tum, platform, dil):
    on = f"{ONEK_SIR[platform]}_{dil.upper()}_"
    sir = {a: (tum.get(on + a) or "").strip() for a in GEREKEN[platform]}
    return sir if all(sir.values()) else None


def paylasim_linki(dil, x, platform) -> str:
    q = urllib.parse.urlencode({"utm_source": platform, "utm_medium": "social", "utm_campaign": "oyun-haberleri"})
    return f"{SITE}/{KLASOR[dil]}/{x['id']}.html?{q}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="hiçbir şey göndermeden ne paylaşılacağını göster")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    ayar = json.loads((KOK / "sosyal" / "ayarlar.json").read_text(encoding="utf-8"))
    veri = json.loads((KOK / "data" / "icerik.json").read_text(encoding="utf-8"))
    veri.sort(key=lambda x: (x["tarih"], x["id"]), reverse=True)
    kayit = json.loads(KAYIT.read_text(encoding="utf-8")) if KAYIT.exists() else {}
    tum = sirlari_oku()
    bugun = date.today()
    bugun_s = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    hatalar, gonderilen, atlanan = [], 0, []

    for dil in DILLER:
        for platform in ("x", "reddit", "instagram"):
            if not ayar["hesaplar"].get(dil, {}).get(platform):
                continue
            sir = hesap_sirri(tum, platform, dil)
            if not sir and not a.dry_run:
                atlanan.append(f"{platform}/{dil}")
                continue
            anahtar_on = f"|{dil}|{platform}"
            bugunku = sum(1 for k, v in kayit.items() if k.endswith(anahtar_on) and v.get("zaman", "").startswith(bugun_s))
            hak = min(ayar.get("calisma_basina_en_fazla", 1), ayar["gunluk_en_fazla"].get(platform, 2) - bugunku)
            for x in veri:
                if hak <= 0:
                    break
                if (bugun - date.fromisoformat(x["tarih"])).days > ayar.get("en_eski_gun", 3):
                    break
                k = f"{x['id']}{anahtar_on}"
                if k in kayit:
                    continue
                link = paylasim_linki(dil, x, platform)
                sayfa = f"{SITE}/{KLASOR[dil]}/{x['id']}.html"
                if a.dry_run:
                    print(f"\n[DENEME] {platform}/{dil}  {x['id']}" + ("" if sir else "  (hesap şifresi yok, gerçekte atlanır)"))
                    if platform == "x":
                        print(x_metin(dil, x, link, ayar.get("x_baglanti", "gonderide")))
                    elif platform == "reddit":
                        print(f"başlık: {x['diller'][dil]['baslik']}\nbağlantı: {link}")
                    else:
                        print(f"görsel: {SITE}/{kart_ad(x['id'], dil, 'ig')}\n{ig_aciklama(dil, x)}")
                    hak -= 1
                    continue
                if not yayinda_mi(sayfa):
                    print(f"Bekliyor (sayfa henüz yayında değil): {sayfa}")
                    continue
                try:
                    if platform == "x":
                        sonuc = x_paylas(sir, dil, x, link, ayar.get("x_baglanti", "gonderide"))
                    elif platform == "reddit":
                        sonuc = reddit_paylas(sir, dil, x, link, ayar)
                    else:
                        sonuc = ig_paylas(sir, dil, x, ayar)
                except PaylasimHatasi as h:
                    hatalar.append(f"{platform}/{dil} {x['id']}: {h}")
                    break  # bu hesapta sorun var; diğer hesaplara geç
                kayit[k] = {"zaman": datetime.now(timezone.utc).isoformat(timespec="seconds"), **sonuc}
                KAYIT.write_text(json.dumps(kayit, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
                print(f"Paylaşıldı: {platform}/{dil} {x['id']} {sonuc.get('url') or sonuc.get('kimlik')}")
                gonderilen += 1
                hak -= 1

    if atlanan:
        print("Hesap şifresi girilmemiş, atlandı: " + ", ".join(atlanan))
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
    veri = json.loads((KOK / "data" / "icerik.json").read_text(encoding="utf-8"))
    uzun = 0
    for x in veri:
        for d in DILLER:
            for mod in ("gonderide", "profilde"):
                m = x_metin(d, x, paylasim_linki(d, x, "x"), mod)
                n = len(m) - (len(paylasim_linki(d, x, "x")) - 23 if mod == "gonderide" else 0)
                if n > 280:
                    uzun += 1
                    print("UZUN:", d, x["id"], n)
            if len(ig_aciklama(d, x)) > 2200:
                uzun += 1
    print("Metin uzunluk testi:", "GEÇTİ" if not uzun else f"KALDI ({uzun})")
    return 0 if ok and not uzun else 1


if __name__ == "__main__":
    sys.exit(main())
