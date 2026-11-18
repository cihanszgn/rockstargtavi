#!/usr/bin/env python3
"""Sosyal ölçüm: yayınlanmış gönderilerin izlenme/etkileşim sayılarını ve hesap toplamlarını toplar.

Kaynak: sosyal/gonderilenler.json (durum=tamam kayıtları) ve data/videolar.json (YouTube bağlantıları).
Çıktı : sosyal/olcum.json (her çalıştırmada hesap toplamı kaydı + gönderi başına son değerler)
        sosyal/olcum_ozet.md (en çok izlenen 10, tür/saat ortalaması, takipçi/abone değişimi, alınamayanlar)

  python tools/sosyal_olcum.py            # ölçer, iki dosyayı yazar
  python tools/sosyal_olcum.py --selftest # sahte ağ ile ayrıştırma ve çıktı sınanır (ağ yok, dosya yazmaz)

Yalnız OKUMA çağrıları yapılır (GET). Anahtarı olmayan hesap sessizce atlanır; ağ/API hatası aracı düşürmez
(çıkış kodu her zaman 0; hata özet dosyasına ve günlüğe yazılır). Sırlar hiçbir çıktıya yazılmaz.
Anahtarlar sosyal_yayinla.py ile aynıdır: YT_<DIL>_CLIENT_ID/CLIENT_SECRET/REFRESH_TOKEN, IG_<DIL>_USER_ID/TOKEN.
Yalnız Python standart kütüphanesi.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import tempfile
import urllib.parse
from datetime import datetime, timedelta, timezone

KOK = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK / "tools"))
import sosyal_yayinla as sy  # noqa: E402  (Ag, sir okuma, YouTube erişim anahtarı, Instagram sunucusu yeniden kullanılır)

KAYIT = KOK / "sosyal" / "gonderilenler.json"
MANIFEST = KOK / "data" / "videolar.json"
AYAR = KOK / "sosyal" / "ayarlar.json"
OLCUM = KOK / "sosyal" / "olcum.json"
OZET = KOK / "sosyal" / "olcum_ozet.md"
MAX_KAYIT = 400          # hesap toplamı geçmişi (günde bir çalışma: ~1 yıl)
TR_FARK = timedelta(hours=3)   # Türkiye saati (UTC+3, yaz saati yok)
YT_API = "https://www.googleapis.com/youtube/v3"

# Instagram gönderi ölçüleri (resmî doküman: instagram-media/insights, 2026-11-17'de doğrulandı).
# impressions ve plays KALDIRILDI; yerine views. Hepsi birden istenir, reddedilirse ölçü ölçü denenir.
IG_ORTAK = ("reach", "views", "saved", "shares", "total_interactions", "likes", "comments")
IG_REEL_EK = ("ig_reels_avg_watch_time",)
IG_HESAP_GUNLUK = ("reach", "views")   # kullanıcı ölçüsü: period=day, metric_type=total_value


class Gunluk:
    def __init__(self, sirlar: list[str]):
        self.sirlar = [s for s in sirlar if s and len(s) >= 6]
        self.satirlar: list[str] = []

    def temiz(self, m) -> str:
        m = str(m)
        for s in self.sirlar:
            m = m.replace(s, "***")
        m = re.sub(r"(access_token|client_secret|refresh_token)=[^&\s\"']+", r"\1=***", m)
        m = re.sub(r"(Bearer\s+)[A-Za-z0-9._\-]+", r"\1***", m)
        return m

    def __call__(self, m) -> None:
        m = self.temiz(m)
        self.satirlar.append(m)
        print(m)


def kisa_hata(h) -> str:
    """Hata metninden okunur kısa neden (adres ve gövde kırpılır)."""
    m = str(h)
    ic = re.search(r'"message"\s*:\s*"([^"]+)"', m)
    kod = re.search(r"HTTP (\d+)", m)
    alt = re.search(r'"code"\s*:\s*(\d+)', m)
    parca = []
    if kod:
        parca.append(f"HTTP {kod.group(1)}")
    if alt:
        parca.append(f"kod {alt.group(1)}")
    parca.append(ic.group(1) if ic else m.split("→")[-1].strip())
    return " ".join(parca)[:220]


def izin_notu(neden: str) -> str:
    n = neden.lower()
    if "insufficientpermissions" in n or "insufficient permission" in n or "scope" in n:
        return "izin (scope) eksik"
    if "permission" in n or "(#10)" in n or "(#200)" in n or "instagram_manage_insights" in n:
        return "izin eksik olabilir"
    if "access blocked" in n or "5258005" in n:
        return "Meta API erişimi engelli"
    return ""


# ---------------------------------------------------------------- hedef listesi
def yt_kimligi(url: str) -> str | None:
    m = re.search(r"(?:/shorts/|[?&]v=|youtu\.be/)([A-Za-z0-9_-]{6,})", url or "")
    return m.group(1) if m else None


def hedefler(kayit: dict, manifest: dict) -> list[dict]:
    """Yayınlanmış gönderiler: {platform, kimlik, dil (içerik dili), hesap (yayının çıktığı hesabın dili; manifestten
    gelen kayıtta None, ölçümde ayardan çözülür), bicim, tur, id, url, zaman}. platform+kimlik tekil."""
    sonuc, gorulen = [], set()
    for k, r in kayit.items():
        p = k.split("|")
        if len(p) != 4 or r.get("durum") != "tamam" or not r.get("kimlik"):
            continue
        if r.get("platform") not in ("instagram", "youtube"):
            continue
        a = (r["platform"], str(r["kimlik"]))
        if a in gorulen:
            continue
        gorulen.add(a)
        sonuc.append({"anahtar": k, "platform": r["platform"], "kimlik": a[1], "dil": r.get("dil") or p[1],
                      "hesap": sy.kayit_hesabi(k, r), "bicim": r.get("bicim") or p[3], "tur": r.get("sosyal_tur", "haber"), "id": r.get("id", p[0]),
                      "url": r.get("url"), "zaman": r.get("zaman") or r.get("niyet_zamani")})
    for vid, diller in (manifest.get("videolar") or {}).items():
        for dil, v in (diller or {}).items():
            yid = yt_kimligi(v.get("youtube", "")) if isinstance(v, dict) else None
            if yid and ("youtube", yid) not in gorulen:
                gorulen.add(("youtube", yid))
                sonuc.append({"anahtar": f"{vid}|{dil}|youtube|short", "platform": "youtube", "kimlik": yid, "dil": dil,
                              "hesap": None, "bicim": "short", "tur": "haber", "id": vid, "url": v.get("youtube"),
                              "zaman": v.get("uretildi")})
    return sonuc


def sayi(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- YouTube
def youtube_olc(ag, sir, dil, hedef: list[dict], gunluk, hatalar: list, simdi: str):
    """(hesap_toplami | None, {kimlik: ölçüler}). Hata atmaz."""
    try:
        tok = sy.yt_erisim(ag, sir)
    except sy.PaylasimHatasi as h:
        hatalar.append({"platform": "youtube", "dil": dil, "ne": "erişim anahtarı", "neden": kisa_hata(h)})
        return None, {}
    bas = {"Authorization": f"Bearer {tok}"}
    gunluk.sirlar.append(tok)
    hesap, gonderi = None, {}
    try:
        _, d = ag.istek("GET", f"{YT_API}/channels?" + urllib.parse.urlencode({"part": "statistics,snippet", "mine": "true"}), basliklar=bas)
        ogeler = d.get("items") if isinstance(d, dict) else None
        if not ogeler:
            raise sy.PaylasimHatasi(f"kanal bulunamadı (items boş): {str(d)[:120]}")
        s = ogeler[0].get("statistics") or {}
        hesap = {"abone": None if s.get("hiddenSubscriberCount") else sayi(s.get("subscriberCount")),
                 "izlenme": sayi(s.get("viewCount")), "video": sayi(s.get("videoCount")),
                 "kanal": (ogeler[0].get("snippet") or {}).get("title")}
    except sy.PaylasimHatasi as h:
        hatalar.append({"platform": "youtube", "dil": dil, "ne": "kanal toplamları (channels.list)", "neden": kisa_hata(h)})
    kimlikler = [x["kimlik"] for x in hedef]
    for i in range(0, len(kimlikler), 50):
        parca = kimlikler[i:i + 50]
        try:
            _, d = ag.istek("GET", f"{YT_API}/videos?" + urllib.parse.urlencode({"part": "statistics", "id": ",".join(parca)}), basliklar=bas)
        except sy.PaylasimHatasi as h:
            hatalar.append({"platform": "youtube", "dil": dil, "ne": "video sayıları (videos.list)", "neden": kisa_hata(h)})
            break
        for o in (d.get("items") if isinstance(d, dict) else None) or []:
            s = o.get("statistics") or {}
            gonderi[o.get("id")] = {k: v for k, v in {"izlenme": sayi(s.get("viewCount")), "begeni": sayi(s.get("likeCount")),
                                                       "yorum": sayi(s.get("commentCount"))}.items() if v is not None}
        yok = [k for k in parca if k not in gonderi]
        if yok:
            hatalar.append({"platform": "youtube", "dil": dil, "ne": "video bulunamadı (silinmiş/gizli olabilir)", "neden": f"{len(yok)} video"})
    return hesap, gonderi


# ---------------------------------------------------------------- Instagram
def ig_deger(o: dict):
    v = o.get("values")
    if isinstance(v, list) and v and isinstance(v[0], dict):
        return sayi(v[0].get("value"))
    tv = o.get("total_value")
    return sayi(tv.get("value")) if isinstance(tv, dict) else None


def ig_olculer(ag, taban: str, tok: str, yol: str, olculer, hatalar: list, bilgi: dict, ek: dict | None = None) -> dict:
    """Önce hepsi birden, reddedilirse ölçü ölçü. Reddedilen ölçü diğerlerini düşürmez."""
    cikti: dict = {}

    def sor(liste):
        q = {"metric": ",".join(liste), "access_token": tok, **(ek or {})}
        _, d = ag.istek("GET", f"{taban}/{yol}/insights?" + urllib.parse.urlencode(q))
        for o in (d.get("data") if isinstance(d, dict) else None) or []:
            v = ig_deger(o)
            if v is not None and o.get("name"):
                cikti[o["name"]] = v

    try:
        sor(list(olculer))
        return cikti
    except sy.PaylasimHatasi as h:
        ilk = kisa_hata(h)
        if izin_notu(ilk):
            # Tek tek denemek aynı izin/engel hatasını yüzlerce kez alır: bir kez yaz, bırak.
            hatalar.append({**bilgi, "ne": "ölçüler (insights)", "neden": ilk})
            cikti["_izinsiz"] = 1
            return cikti
    for m in olculer:
        if m in cikti:
            continue
        try:
            sor([m])
        except sy.PaylasimHatasi as h:
            hatalar.append({**bilgi, "ne": f"ölçü {m}", "neden": kisa_hata(h)})
    return cikti


def instagram_olc(ag, sir, dil, hedef: list[dict], surum: str, hatalar: list):
    """(hesap_toplami | None, {kimlik: ölçüler}). Hata atmaz."""
    tok = sir["TOKEN"]
    taban = f"https://{sy.ig_sunucu(tok)}/{surum}"
    bilgi = {"platform": "instagram", "dil": dil}
    try:
        _, d = ag.istek("GET", f"{taban}/{sir['USER_ID']}?" + urllib.parse.urlencode(
            {"fields": "username,followers_count,follows_count,media_count", "access_token": tok}))
        if not isinstance(d, dict) or "followers_count" not in d:
            raise sy.PaylasimHatasi(f"hesap yanıtı anlaşılmadı: {str(d)[:120]}")
        hesap = {"takipci": sayi(d.get("followers_count")), "takip": sayi(d.get("follows_count")),
                 "medya": sayi(d.get("media_count")), "kullanici": d.get("username")}
    except sy.PaylasimHatasi as h:
        hatalar.append({**bilgi, "ne": "hesap bilgisi", "neden": kisa_hata(h)})
        return None, {}   # hesap düzeyinde sorun (engel/süresi dolmuş anahtar): gönderilere yüklenme
    # Hesabın son 24 saatlik erişim/izlenmesi (varsa); reddedilirse yalnız not düşülür.
    gun = ig_olculer(ag, taban, tok, sir["USER_ID"], IG_HESAP_GUNLUK, hatalar, {**bilgi, "ne": "hesap"},
                     {"period": "day", "metric_type": "total_value"})
    izinsiz = bool(gun.pop("_izinsiz", 0))
    for k, v in gun.items():
        hesap[f"{k}_gunluk"] = v
    gonderi = {}
    for h in hedef:
        mid = h["kimlik"]
        o: dict = {}
        tur = None
        try:
            _, m = ag.istek("GET", f"{taban}/{mid}?" + urllib.parse.urlencode(
                {"fields": "media_product_type,like_count,comments_count,timestamp,permalink", "access_token": tok}))
            if isinstance(m, dict):
                tur = m.get("media_product_type")
                if sayi(m.get("like_count")) is not None:
                    o["likes"] = sayi(m["like_count"])
                if sayi(m.get("comments_count")) is not None:
                    o["comments"] = sayi(m["comments_count"])
                if m.get("permalink"):
                    o["_url"] = m["permalink"]
        except sy.PaylasimHatasi as e:
            hatalar.append({**bilgi, "ne": f"gönderi {mid}", "neden": kisa_hata(e)})
            continue
        olculer = IG_ORTAK + (IG_REEL_EK if (tur == "REELS" or h["bicim"] == "reel") else ())
        if not izinsiz:
            r = ig_olculer(ag, taban, tok, mid, olculer, hatalar, {**bilgi, "ne": "gönderi"})
            izinsiz = bool(r.pop("_izinsiz", 0))   # izin yoksa kalan gönderilerde insights denenmez
            o.update(r)
        gonderi[mid] = o
    return hesap, gonderi


# ---------------------------------------------------------------- çıktı
def yukle(yol: pathlib.Path) -> dict:
    try:
        d = json.loads(yol.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def izlenme(g: dict) -> int | None:
    s = g.get("son") or {}
    for a in ("izlenme", "views", "reach"):
        if isinstance(s.get(a), int):
            return s[a]
    return None


def etkilesim(g: dict) -> int:
    s = g.get("son") or {}
    if g.get("platform") == "youtube":
        return (s.get("begeni") or 0) + (s.get("yorum") or 0)
    return s.get("total_interactions") if isinstance(s.get("total_interactions"), int) else \
        sum(s.get(a) or 0 for a in ("likes", "comments", "saved", "shares"))


def ortalama(liste: list[int]) -> str:
    return f"{sum(liste) / len(liste):.1f}" if liste else "-"


def ozet_yaz(olcum: dict, atlanan: list[str], hatalar: list[dict], simdi: datetime) -> str:
    L = [f"# Sosyal ölçüm özeti", "", f"Son ölçüm: {simdi:%Y-%m-%d %H:%M} UTC. Ham veri: `sosyal/olcum.json`.", ""]
    kayitlar = olcum.get("kayitlar") or []
    son = kayitlar[-1]["hesaplar"] if kayitlar else {}
    # hesap toplamları ve değişim
    L += ["## Hesaplar", ""]
    if not son:
        L += ["Hesap toplamı alınamadı (anahtar yok ya da API hatası; aşağıya bak).", ""]
    for ad, v in sorted(son.items()):
        plat, dil = ad.split("|")
        anahtar = "abone" if plat == "youtube" else "takipci"
        etiket = "abone" if plat == "youtube" else "takipçi"
        ilk = next((k["hesaplar"][ad][anahtar] for k in kayitlar if ad in k.get("hesaplar", {}) and k["hesaplar"][ad].get(anahtar) is not None), None)
        dun = None
        esik = (kayitlar[-1]["zaman"])[:10]
        for k in reversed(kayitlar[:-1]):
            if k["zaman"][:10] < esik and ad in k.get("hesaplar", {}):
                dun = k["hesaplar"][ad].get(anahtar)
                break
        simdiki = v.get(anahtar)
        degisim = ""
        if simdiki is not None and dun is not None:
            degisim += f", önceki günden {simdiki - dun:+d}"
        if simdiki is not None and ilk is not None and ilk != simdiki:
            degisim += f", ilk ölçümden {simdiki - ilk:+d}"
        ek = f", toplam izlenme {v['izlenme']}, video {v.get('video')}" if plat == "youtube" and v.get("izlenme") is not None else ""
        if plat == "instagram":
            ek = f", medya {v.get('medya')}" + "".join(f", son gün {k.replace('_gunluk', '')} {x}" for k, x in v.items() if k.endswith("_gunluk"))
        L.append(f"- {plat} / {dil}: {etiket} {simdiki if simdiki is not None else '?'}{degisim}{ek}")
    if atlanan:
        L.append(f"- Anahtarı olmadığı için atlanan: {', '.join(atlanan)}")
    L.append("")
    gon = [g for g in (olcum.get("gonderiler") or {}).values() if izlenme(g) is not None]
    L += ["## En çok izlenen 10 içerik", ""]
    if not gon:
        L += ["İzlenme sayısı alınabilen gönderi yok.", ""]
    else:
        L += ["| # | Platform | Tür | İçerik | İzlenme | Etkileşim | Yayın (TR) |", "|---|---|---|---|---|---|---|"]
        for i, g in enumerate(sorted(gon, key=lambda g: (-izlenme(g), g["id"]))[:10], 1):
            z = zaman_oku(g.get("zaman"))
            yay = f"{z + TR_FARK:%d.%m %H:%M}" if z else "?"
            ad = g["id"][:48]
            L.append(f"| {i} | {g['platform']}/{g['dil']} | {g['bicim']} | {ad} | {izlenme(g)} | {etkilesim(g)} | {yay} |")
        L.append("")
    if olcum.get("gonderiler"):
        L += ["## Tür ortalaması (gönderi başına izlenme)", "", "| Platform / biçim | Gönderi | Ort. izlenme | Ort. etkileşim |", "|---|---|---|---|"]
        gr: dict = {}
        for g in (olcum.get("gonderiler") or {}).values():
            gr.setdefault(f"{g['platform']} / {g['bicim']}", []).append(g)
        for a, l in sorted(gr.items()):
            L.append(f"| {a} | {len(l)} | {ortalama([izlenme(g) for g in l if izlenme(g) is not None])} | {ortalama([etkilesim(g) for g in l])} |")
        L += ["", "## Yayın saatine göre (Türkiye saati)", "", "| Saat dilimi | Gönderi | Ort. izlenme |", "|---|---|---|"]
        sa: dict = {}
        for g in gon:
            z = zaman_oku(g.get("zaman"))
            if z:
                s = (z + TR_FARK).hour // 4 * 4
                sa.setdefault(f"{s:02d}-{s + 3:02d}", []).append(izlenme(g))
        for a, l in sorted(sa.items()):
            L.append(f"| {a} | {len(l)} | {ortalama(l)} |")
        L.append("")
        L.append("Not: Instagram izlenmesi `views` (yoksa `reach`; alınamazsa tabloda eksik; etkileşim beğeni+yorum'a düşer), YouTube izlenmesi `viewCount`. Yeni gönderide sayılar henüz küçüktür; yaşa dikkat.")
        L.append("")
    L += ["## Alınamayanlar", ""]
    if not hatalar:
        L.append("Yok.")
    else:
        grup: dict = {}
        for h in hatalar:
            grup.setdefault((h["platform"], h["dil"], h["ne"].split(" ")[0] if h["ne"].startswith("gönderi") else h["ne"], h["neden"]), 0)
            grup[(h["platform"], h["dil"], h["ne"].split(" ")[0] if h["ne"].startswith("gönderi") else h["ne"], h["neden"])] += 1
        for (p, d, ne, neden), n in sorted(grup.items()):
            nt = izin_notu(neden)
            L.append(f"- {p}/{d} {ne} ({n}x): {neden}" + (f" [{nt}]" if nt else ""))
    L.append("")
    return "\n".join(L)


def zaman_oku(s):
    try:
        z = datetime.fromisoformat(s)
        return z if z.tzinfo else z.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def calistir(*, kayit_yolu=KAYIT, manifest_yolu=MANIFEST, ayar_yolu=AYAR, olcum_yolu=OLCUM, ozet_yolu=OZET,
             tum: dict, ag, simdi: datetime, yaz: bool = True) -> tuple[dict, str, list]:
    gunluk = Gunluk(list(tum.values()))
    ayar = yukle(ayar_yolu)
    surum = ayar.get("instagram_api_surumu", "v27.0")
    hedef = hedefler(yukle(kayit_yolu), yukle(manifest_yolu))
    olcum = yukle(olcum_yolu)
    olcum.setdefault("surum", 1)
    olcum.setdefault("gonderiler", {})
    olcum.setdefault("kayitlar", [])
    hatalar: list[dict] = []
    atlanan: list[str] = []
    hesaplar: dict = {}
    za = simdi.isoformat(timespec="seconds")
    for platform in ("youtube", "instagram"):
        for dil in (*sy.DILLER, sy.KLIP_HESABI):
            sir = sy.hesap_sirri(tum, platform, dil)
            liste = [x for x in hedef if x["platform"] == platform and
                     (x.get("hesap") or sy.hesap_coz(ayar, tum, platform, x["dil"])[0]) == dil]
            if not sir:
                if liste:
                    atlanan.append(f"{platform}/{dil}")
                continue
            gunluk(f"Ölçülüyor: {platform}/{dil} ({len(liste)} gönderi)")
            try:
                if platform == "youtube":
                    hesap, gon = youtube_olc(ag, sir, dil, liste, gunluk, hatalar, za)
                else:
                    gunluk.sirlar.append(sir["TOKEN"])
                    hesap, gon = instagram_olc(ag, sir, dil, liste, surum, hatalar)
            except Exception as e:  # her koşulda düşmez
                hatalar.append({"platform": platform, "dil": dil, "ne": "beklenmeyen hata", "neden": f"{type(e).__name__}: {e}"[:200]})
                continue
            if hesap:
                hesaplar[f"{platform}|{dil}"] = {k: v for k, v in hesap.items() if v is not None}
            for x in liste:
                o = gon.get(x["kimlik"])
                if not o:
                    continue
                url = o.pop("_url", None) or x.get("url")
                g = olcum["gonderiler"].setdefault(f"{platform}|{x['kimlik']}", {})
                g.update({"platform": platform, "dil": x["dil"], "bicim": x["bicim"], "tur": x["tur"], "id": x["id"],
                          "kimlik": x["kimlik"], "url": url, "zaman": x["zaman"]})
                g["son"] = {**(g.get("son") or {}), **o, "olculdu": za}
    if hesaplar:
        olcum["kayitlar"].append({"zaman": za, "hesaplar": hesaplar})
        olcum["kayitlar"] = olcum["kayitlar"][-MAX_KAYIT:]
    olcum["guncelleme"] = za
    ozet = ozet_yaz(olcum, atlanan, hatalar, simdi)
    ozet = gunluk.temiz(ozet)
    if yaz:
        olcum_yolu.parent.mkdir(parents=True, exist_ok=True)
        if hesaplar or any(g.get("son", {}).get("olculdu") == za for g in olcum["gonderiler"].values()):
            olcum_yolu.write_text(gunluk.temiz(json.dumps(olcum, ensure_ascii=False, indent=1, sort_keys=True)) + "\n", encoding="utf-8")
        ozet_yolu.write_text(ozet + "\n", encoding="utf-8")
    sayac: dict = {}
    for h in hatalar:  # aynı hata yüzlerce gönderide tekrarlanır: günlükte bir kez, adetle
        a = (h["platform"], h["dil"], h["ne"] if not h["ne"].startswith("gönderi ") else "gönderi", h["neden"])
        sayac[a] = sayac.get(a, 0) + 1
    for (p, d, ne, neden), n in sayac.items():
        gunluk(f"::warning::{p}/{d} {ne}: {neden}" + (f" ({n}x)" if n > 1 else ""))
    if atlanan:
        gunluk("Anahtar yok, atlandı: " + ", ".join(atlanan))
    if not hesaplar and not hatalar:
        gunluk("Ölçülecek hesap yok (anahtar tanımlı değil), atlandı.")
    return olcum, ozet, hatalar


# ---------------------------------------------------------------- sınama
class SahteAg:
    """Resmî yanıt biçimlerini taklit eder; sy.Ag.istek ile aynı imza. Bazı ölçüler reddedilir."""

    def __init__(self):
        self.cagri = []

    def istek(self, method, url, *, veri=None, json_govde=None, basliklar=None, zaman=30):
        self.cagri.append(url)
        yol, _, q = url.partition("?")
        q = dict(urllib.parse.parse_qsl(q))
        if "oauth2.googleapis.com" in yol:
            return 200, {"access_token": "ya29.SAHTE-ERISIM-ANAHTARI"}
        if yol.endswith("/youtube/v3/channels"):
            return 200, {"items": [{"snippet": {"title": "K"}, "statistics": {"subscriberCount": "12", "viewCount": "3456", "videoCount": "5"}}]}
        if yol.endswith("/youtube/v3/videos"):
            return 200, {"items": [{"id": i, "statistics": {"viewCount": str(100 * n), "likeCount": str(n), "commentCount": "1"}}
                                   for n, i in enumerate(q["id"].split(","), 1) if i != "yokvideo"]}
        if yol.endswith("/insights"):
            if "period" in q:  # hesap
                return 200, {"data": [{"name": m, "values": [], "total_value": {"value": 77}} for m in q["metric"].split(",")]}
            if "," in q["metric"]:
                raise sy.PaylasimHatasi('GET x → HTTP 400: {"error":{"message":"(#100) metric[4] must be one of the following values","code":100}}', kesin=True)
            if q["metric"] == "shares":
                raise sy.PaylasimHatasi('GET x → HTTP 400: {"error":{"message":"Permission denied (#10) instagram_manage_insights","code":10}}', kesin=True)
            return 200, {"data": [{"name": q["metric"], "period": "lifetime", "values": [{"value": 9}]}]}
        if q.get("fields", "").startswith("username"):
            return 200, {"username": "ctrlagame", "followers_count": 321, "follows_count": 4, "media_count": 25, "id": "1"}
        if "media_product_type" in q.get("fields", ""):
            return 200, {"media_product_type": "REELS" if url.split("/")[-1].startswith("r") else "FEED", "like_count": 5,
                         "comments_count": 2, "permalink": "https://www.instagram.com/p/X/"}
        raise sy.PaylasimHatasi(f"beklenmeyen {url}")


def selftest() -> int:
    kayit = {
        "a|tr|youtube|short": {"durum": "tamam", "platform": "youtube", "dil": "tr", "bicim": "short", "kimlik": "vid1", "id": "a", "zaman": "2026-11-16T08:00:00+00:00", "sosyal_tur": "haber"},
        "b|tr|youtube|short": {"durum": "tamam", "platform": "youtube", "dil": "tr", "bicim": "short", "kimlik": "yokvideo", "id": "b", "zaman": "2026-11-16T09:00:00+00:00"},
        "c|tr|instagram|reel": {"durum": "tamam", "platform": "instagram", "dil": "tr", "bicim": "reel", "kimlik": "r1", "id": "c", "zaman": "2026-11-16T10:00:00+00:00"},
        "d|tr|instagram|gorsel": {"durum": "tamam", "platform": "instagram", "dil": "tr", "bicim": "gorsel", "kimlik": "g1", "id": "d", "zaman": "2026-11-16T22:00:00+00:00"},
        "e|tr|instagram|gorsel": {"durum": "niyet", "platform": "instagram", "dil": "tr", "bicim": "gorsel", "kimlik": "g2", "id": "e"},
    }
    manifest = {"videolar": {"z": {"tr": {"youtube": "https://www.youtube.com/shorts/vid9abcdefg"}}}}
    sirlar = {"YT_TR_CLIENT_ID": "cid-sahte", "YT_TR_CLIENT_SECRET": "csecret-sahte", "YT_TR_REFRESH_TOKEN": "rt-sahte-123456",
              "IG_TR_USER_ID": "1784", "IG_TR_TOKEN": "EAAsahte-ig-anahtar-9999"}
    with tempfile.TemporaryDirectory() as t:
        t = pathlib.Path(t)
        (t / "k.json").write_text(json.dumps(kayit), encoding="utf-8")
        (t / "m.json").write_text(json.dumps(manifest), encoding="utf-8")
        yollar = dict(kayit_yolu=t / "k.json", manifest_yolu=t / "m.json", ayar_yolu=t / "yok.json",
                      olcum_yolu=t / "o.json", ozet_yolu=t / "o.md")
        hedef = hedefler(kayit, manifest)
        assert len(hedef) == 5, hedef   # niyet kaydı sayılmaz, manifest videosu eklenir
        ag = SahteAg()
        simdi = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)
        o, ozet, hata = calistir(tum=sirlar, ag=ag, simdi=simdi, **yollar)
        g = o["gonderiler"]
        assert g["youtube|vid1"]["son"]["izlenme"] == 100 and "youtube|yokvideo" not in g
        assert o["kayitlar"][0]["hesaplar"]["youtube|tr"]["abone"] == 12
        assert o["kayitlar"][0]["hesaplar"]["instagram|tr"]["takipci"] == 321
        assert g["instagram|r1"]["son"]["views"] == 9 and "shares" not in g["instagram|r1"]["son"], g["instagram|r1"]
        assert g["instagram|r1"]["son"]["likes"] in (5, 9)
        assert any("shares" in h["ne"] for h in hata) and any(h["ne"].startswith("video bulunamadı") for h in hata)
        gizli = ("SAHTE-ERISIM", "csecret-sahte", "rt-sahte", "sahte-ig-anahtar", "access_token")
        tum = (t / "o.json").read_text(encoding="utf-8") + (t / "o.md").read_text(encoding="utf-8")
        assert not any(s in tum for s in gizli), "sır sızdı"
        assert "En çok izlenen 10" in ozet and "izin eksik" in ozet
        # ikinci gün: değişim ve gönderi değerlerinin korunması
        o2, ozet2, _ = calistir(tum=sirlar, ag=SahteAg(), simdi=simdi + timedelta(days=1), **yollar)
        assert len(o2["kayitlar"]) == 2 and "önceki günden +0" in ozet2
        # anahtarsız: sessiz atlanır, dosya bozulmaz
        o3, ozet3, h3 = calistir(tum={}, ag=SahteAg(), simdi=simdi + timedelta(days=2), **yollar)
        assert len(o3["kayitlar"]) == 2 and not h3 and "atlan" in ozet3
        # tümden bozuk ağ: hata özetlenir, istisna yok
        class Bozuk:
            def istek(self, *a, **k):
                raise sy.PaylasimHatasi("GET x → HTTP 400: " + json.dumps({"error": {"message": "API access blocked", "code": 200, "error_subcode": 5258005}}))
        o4, ozet4, h4 = calistir(tum=sirlar, ag=Bozuk(), simdi=simdi + timedelta(days=3), **yollar)
        assert h4 and "engelli" in ozet4 and len(o4["kayitlar"]) == 2
    print("selftest tamam")
    return 0


def main(argv=None) -> int:
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    try:
        calistir(tum=sy.sirlari_oku(), ag=sy.Ag(), simdi=datetime.now(timezone.utc))
    except Exception as e:  # ölçüm hiçbir koşulda iş akışını düşürmez
        print(f"::warning::ölçüm beklenmeyen hatayla durdu: {type(e).__name__}: {str(e)[:200]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
