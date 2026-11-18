"""Yayıncı yönetimi (onay panelindeki "Yayıncılar" sekmesi): ekle, düzenle, kaldır / geri getir, "son yayından klip çıkar".
Hepsi `otomasyon/klip-yayincilar.json` üstünde çalışır (yol: KLIP_YAYINCILAR ya da varsayılan). Cio JSON düzenlemez; panel bu modülü çağırır.

Güvenlik: kanal adı girdisi sıkı doğrulanır (bağlantıdan ayıklanır), dış isteklere zaman aşımı, alt süreçler liste argümanıyla (kabuk yok).
Dosya yazımı: yedek -> geçici dosya -> doğrula -> değiştir (os.replace) -> yeniden oku ve doğrula; olmazsa yedekten geri döner.
Biçim: dosyanın mevcut düzeni (2 boşluk, `ayar` anahtarı başına satır, yayıncı kaydı tek satır, satır sonu CRLF/LF) aynen korunur."""
from __future__ import annotations

import copy
import json
import os
import pathlib
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
from datetime import datetime, timezone

KOK = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK / "tools"))
import klip_duzenle as kd  # noqa: E402
import klip_youtube as kyt  # noqa: E402
import yayin_klip as yk  # noqa: E402


class Hata(Exception):
    pass


KANAL_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
UC_RE = re.compile(r"^UC[A-Za-z0-9_-]{22}$")
TANITICI_RE = re.compile(r"^[\w.\-]{3,60}$")      # \w: Türkçe harfler dahil (KendineMüzisyenKM)
KICK_HOSTLAR = ("kick.com", "www.kick.com", "m.kick.com")
YT_HOSTLAR = ("youtube.com", "www.youtube.com", "m.youtube.com")
ONIZLEME_OMRU = 900          # sn
ONIZLEME_AZAMI = 20
YEDEK_SAYISI = 30
CIKAR_ZAMAN_ASIMI = 3 * 3600
BITTI_SURESI = 600
CIKAR_KOMUTU: list[str] | None = None   # yalnız test: gerçek yayin_klip.py yerine sahte komut
_YAZIM_KILIDI = threading.Lock()


# ---------------------------------------------------------------- yollar
def ayar_dosyasi() -> pathlib.Path:
    return pathlib.Path(os.environ.get("KLIP_YAYINCILAR") or yk.YAYINCI_DOSYASI)


def yedek_dizini() -> pathlib.Path:
    """Yazmadan önceki kopyalar. KLIP_YAYINCI_YEDEK ile değişir (test); Cio'nun bilgisayarında C:\\Cihan.Ai\\_yedek\\klip-yayincilar."""
    env = os.environ.get("KLIP_YAYINCI_YEDEK")
    if env:
        return pathlib.Path(env)
    ana = pathlib.Path(r"C:\Cihan.Ai\_yedek")
    return ana / "klip-yayincilar" if ana.is_dir() else yk.calisma_dizini() / "yedek" / "klip-yayincilar"


# ---------------------------------------------------------------- biçim ve güvenli yazım
def bicimle(veri: dict, orijinal: str | None = None) -> str:
    """Dosyanın mevcut biçimi: üst düzey anahtar başına satır; `ayar` içinde anahtar başına satır (listeler tek satır);
    yayincilar / kaldirilanlar içinde kayıt başına tek satır. Satır sonu LF (yazarken dosyanınkine çevrilir).
    `orijinal` verilirse `"yayincilar"` satırından ÖNCEKİ bölüm (`_not`, `ayar`) harfi harfine korunur (elle yazılmış 0.30 gibi
    biçimler değişmez); yalnız yayıncı listeleri yeniden yazılır."""
    d = json.dumps
    anahtarlar = list(veri)
    onek = ""
    if orijinal is not None and "yayincilar" in veri:
        duz = orijinal.replace("\r\n", "\n")
        m = re.search(r'^  "yayincilar": \[', duz, re.M)
        if m:
            onek = duz[:m.start()]
            anahtarlar = anahtarlar[anahtarlar.index("yayincilar"):]
    satir = [] if onek else ["{"]
    for i, k in enumerate(anahtarlar):
        v = veri[k]
        virgul = "" if i == len(anahtarlar) - 1 else ","
        ka = d(k, ensure_ascii=False)
        if k == "ayar" and isinstance(v, dict) and v:
            satir.append(f"  {ka}: {{")
            oge = list(v.items())
            for j, (ak, av) in enumerate(oge):
                satir.append(f"    {d(ak, ensure_ascii=False)}: {d(av, ensure_ascii=False)}" + ("," if j < len(oge) - 1 else ""))
            satir.append("  }" + virgul)
        elif k in ("yayincilar", "kaldirilanlar") and isinstance(v, list) and v:
            satir.append(f"  {ka}: [")
            for j, r in enumerate(v):
                satir.append("    " + d(r, ensure_ascii=False) + ("," if j < len(v) - 1 else ""))
            satir.append("  ]" + virgul)
        else:
            satir.append(f"  {ka}: {d(v, ensure_ascii=False)}{virgul}")
    if not onek:
        satir.append("}")
        return "\n".join(satir) + "\n"
    return onek + "\n".join(satir) + "\n}\n"


def _yedek_al(yol: pathlib.Path) -> pathlib.Path:
    dizin = yedek_dizini()
    dizin.mkdir(parents=True, exist_ok=True)
    ad = datetime.now().strftime("klip-yayincilar-%Y%m%d-%H%M%S-%f.json")
    hedef = dizin / ad
    shutil.copyfile(yol, hedef)
    eskiler = sorted(dizin.glob("klip-yayincilar-*.json"))
    for e in eskiler[:-YEDEK_SAYISI]:
        try:
            e.unlink()
        except OSError:
            pass
    return hedef


def _degistir_dosya(gecici: pathlib.Path, yol: pathlib.Path) -> None:
    son = None
    for _ in range(8):
        try:
            os.replace(gecici, yol)
            return
        except PermissionError as e:   # Windows: dosya o an okunuyor olabilir
            son = e
            time.sleep(0.05)
    raise Hata(f"Ayar dosyası yazılamadı (başka bir program kullanıyor olabilir): {son}")


def dosyayi_guncelle(degistir) -> object:
    """`degistir(veri)` ayar sözlüğünü yerinde değiştirir ve bir sonuç döndürür. Dosya yalnız her şey doğrulanırsa değişir."""
    yol = ayar_dosyasi()
    with _YAZIM_KILIDI:
        try:
            ham = yol.read_bytes()
            metin = ham.decode("utf-8")
            veri = json.loads(metin)
        except (OSError, ValueError) as e:
            raise Hata(f"Ayar dosyası okunamadı: {e}") from e
        if not isinstance(veri, dict) or not isinstance(veri.get("yayincilar", []), list):
            raise Hata("Ayar dosyasının yapısı beklenmedik (yayincilar listesi yok); dokunulmadı.")
        veri.setdefault("yayincilar", [])
        yeni = copy.deepcopy(veri)
        sonuc = degistir(yeni)
        if yeni == veri:
            return sonuc
        cizgi = "\r\n" if "\r\n" in metin else "\n"
        yeni_metin = bicimle(yeni, metin).replace("\n", cizgi)
        yedek = _yedek_al(yol)
        gecici = yol.with_name(yol.name + ".tmp")
        try:
            with open(gecici, "wb") as f:
                f.write(yeni_metin.encode("utf-8"))
                f.flush()
                os.fsync(f.fileno())
            try:
                if json.loads(gecici.read_text(encoding="utf-8")) != yeni:
                    raise Hata("Yazılacak dosya doğrulanamadı; dokunulmadı.")
                yk.ayar_yukle(gecici)   # hattın kendi okuyucusu kabul etmeli
            except (ValueError, yk.KlipHatasi) as e:
                raise Hata(f"Yeni ayar hattın okuyucusunda geçmedi, dokunulmadı: {e}") from e
            _degistir_dosya(gecici, yol)
        finally:
            try:
                gecici.unlink()
            except OSError:
                pass
        try:
            son = json.loads(yol.read_text(encoding="utf-8"))
            yk.ayar_yukle(yol)
            if son != yeni:
                raise ValueError("içerik farklı")
        except (OSError, ValueError, yk.KlipHatasi) as e:
            shutil.copyfile(yedek, yol)
            raise Hata(f"Yazılan dosya doğrulanamadı, yedekten geri yüklendi: {e}") from e
        return sonuc


def dosyayi_oku() -> dict:
    try:
        veri = json.loads(ayar_dosyasi().read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Hata(f"Ayar dosyası okunamadı: {e}") from e
    if not isinstance(veri, dict):
        raise Hata("Ayar dosyasının yapısı beklenmedik.")
    veri.setdefault("yayincilar", [])
    return veri


# ---------------------------------------------------------------- kimlik, yinelenme
def anahtar(rec: dict) -> str:
    """Listede yayıncıyı belirleyen kararlı kimlik: Kick kanalı varsa kick:<kanal>, yoksa youtube:<kanal>."""
    return f"{'kick' if str(rec.get('platform')).lower() == 'kick' else 'youtube'}:{str(rec.get('kanal') or '').lower()}"


def _kimlikler(rec: dict) -> set[str]:
    k = set()
    if str(rec.get("platform")).lower() == "kick" and rec.get("kanal"):
        k.add("kick:" + str(rec["kanal"]).lower())
    for c in rec.get("youtube_kanallari") or []:
        if isinstance(c, dict) and c.get("kanal_id"):
            k.add("yt:" + str(c["kanal_id"]).lower())
    return k


def _yinelenme(veri: dict, kimlikler: set[str], haric: str | None = None) -> str | None:
    """Bu kanallardan biri zaten ekliyse ya da kaldırılanlardaysa Türkçe ileti döndürür."""
    for liste, ek in (("yayincilar", ""), ("kaldirilanlar", " (Kaldırılanlar listesinde: oradan Geri getir)")):
        for r in veri.get(liste) or []:
            if isinstance(r, dict) and anahtar(r) != haric and kimlikler & _kimlikler(r):
                return f'Bu kanal zaten ekli: {r.get("ad")}.{ek}'
    return None


def _ad_temiz(v, alan: str, bos_olur: bool = False) -> str:
    try:
        return kd._ad(v if v is not None else "", alan, bos_olur=bos_olur)
    except kd.Hata as e:
        raise Hata(str(e)) from e


def kisa_ad_oner(ad: str) -> str:
    p = ad.split()
    return p[0] if p else ""


# ---------------------------------------------------------------- girdi ayıklama
def kick_kanali_ayikla(girdi) -> str:
    g = str(girdi or "").strip()
    if not g or len(g) > 300:
        raise Hata("Kick kanalı boş ya da çok uzun.")
    if "/" in g or "." in g or ":" in g:
        u = urllib.parse.urlparse(g if "://" in g else "//" + g)
        if u.scheme not in ("", "http", "https") or (u.hostname or "").lower() not in KICK_HOSTLAR:
            raise Hata("Kick bağlantısı kick.com/kanaladi biçiminde olmalı.")
        parca = [p for p in u.path.split("/") if p]
        if not parca:
            raise Hata("Bağlantıda kanal adı yok; kick.com/kanaladi yaz.")
        ad = urllib.parse.unquote(parca[0])
    else:
        ad = g.lstrip("@")
    if not KANAL_RE.fullmatch(ad):
        raise Hata("Kick kanal adı yalnız harf, rakam, alt çizgi ve tire içerebilir (örnek: kick.com/wtcn).")
    return ad.lower()


def youtube_ayikla(girdi) -> tuple[str, str]:
    """@tanıtıcı, youtube.com/@tanıtıcı, youtube.com/channel/UC... ya da çıplak UC... -> ("tanitici"|"id", değer)."""
    g = str(girdi or "").strip()
    if not g or len(g) > 300:
        raise Hata("YouTube kanalı boş ya da çok uzun.")
    if re.match(r"^(https?://)?((www|m)\.)?youtube\.com(/|$)", g, re.I):
        u = urllib.parse.urlparse(g if "://" in g else "//" + g)
        if (u.hostname or "").lower() not in YT_HOSTLAR:
            raise Hata("YouTube bağlantısı youtube.com/@tanıtıcı biçiminde olmalı.")
        parca = [urllib.parse.unquote(p) for p in u.path.split("/") if p]
        if parca and parca[0].startswith("@"):
            ad = parca[0][1:]
        elif len(parca) >= 2 and parca[0] == "channel" and UC_RE.fullmatch(parca[1]):
            return "id", parca[1]
        else:
            raise Hata("YouTube bağlantısını youtube.com/@tanıtıcı ya da youtube.com/channel/UC... biçiminde ver (video bağlantısı olmaz).")
    elif UC_RE.fullmatch(g):
        return "id", g
    elif "/" in g or ":" in g:
        raise Hata("YouTube bağlantısı youtube.com/@tanıtıcı biçiminde olmalı.")
    else:
        ad = g.lstrip("@")
    if not TANITICI_RE.fullmatch(ad):
        raise Hata("YouTube tanıtıcısı harf, rakam, nokta, alt çizgi ve tireden oluşmalı (örnek: @wtcNFerit).")
    return "tanitici", ad


# ---------------------------------------------------------------- dış doğrulama (Kick, YouTube)
def _kick_http(url: str) -> str:
    return yk.http_metin(url, deneme=2, zaman_asimi=15)


def _yt_bilgi(url: str):
    return kyt.bilgi(url, flat=True, limit=1)


def _sinirli(islem, saniye: float):
    """Yavaş dış çağrıyı en çok `saniye` bekler (iş parçacığı arka planda kalabilir; zaman aşımı kendi içinde de var)."""
    kutu: dict = {}

    def kos():
        try:
            kutu["d"] = islem()
        except BaseException as e:  # noqa: BLE001 — hata çağırana taşınır
            kutu["h"] = e
    t = threading.Thread(target=kos, daemon=True)
    t.start()
    t.join(saniye)
    if t.is_alive():
        raise Hata("Dış site zamanında yanıt vermedi; biraz sonra yeniden dene.")
    if "h" in kutu:
        raise kutu["h"]
    return kutu["d"]


def _tarih(epoch_iso) -> str:
    return str(epoch_iso or "")[:10]


def kick_coz(kanal: str) -> dict:
    """Kick kanalı var mı; görünen ad, canlı mı, son yayın. Yoksa Türkçe Hata."""
    try:
        d = json.loads(_kick_http(f"{yk.KICK_API}/v2/channels/{kanal}"))
    except yk.Desteklenmiyor:
        raise Hata("Kick bu bilgisayardan gelen isteği reddetti (bot koruması). Biraz sonra yeniden dene.") from None
    except yk.KlipHatasi as e:
        if "404" in str(e):
            raise Hata(f'Kick\'te "{kanal}" adında bir kanal bulunamadı. Adı kick.com/ sonrası yazıldığı gibi gir.') from None
        raise Hata("Kick'e ulaşılamadı; internet bağlantını kontrol edip yeniden dene.") from None
    except ValueError:
        raise Hata("Kick yanıtı anlaşılamadı; biraz sonra yeniden dene.") from None
    if not isinstance(d, dict) or not d.get("slug"):
        raise Hata(f'Kick\'te "{kanal}" adında bir kanal bulunamadı.')
    if d.get("is_banned"):
        raise Hata(f'Kick kanalı "{kanal}" yasaklı görünüyor; eklenemez.')
    slug = str(d["slug"])
    if not KANAL_RE.fullmatch(slug):
        raise Hata("Kick'ten gelen kanal adı beklenmedik biçimde; eklenemedi.")
    ad = str(((d.get("user") or {}).get("username")) or slug)
    canli = isinstance(d.get("livestream"), dict)
    son = ""
    try:
        for v in json.loads(_kick_http(f"{yk.KICK_API}/v2/channels/{slug}/videos")) or []:
            if not isinstance(v, dict):
                continue
            son = f"{str(v.get('session_title') or '').strip()[:120]} ({_tarih(v.get('start_time'))})".strip()
            break
    except (yk.KlipHatasi, ValueError, TypeError):
        pass   # son yayın bilgisi isteğe bağlı
    if canli and not son:
        son = f"şu an canlı: {str((d['livestream'] or {}).get('session_title') or '')[:120]}"
    return {"kanal": slug.lower(), "ad": ad, "canli": canli, "son_yayin": son}


def youtube_coz(tur: str, deger: str) -> dict:
    """@tanıtıcı ya da kanal kimliği -> kanal_id, görünen ad, tanıtıcı, son video başlığı. Bulunamazsa Türkçe Hata."""
    taban = (f"https://www.youtube.com/channel/{deger}" if tur == "id"
             else "https://www.youtube.com/@" + urllib.parse.quote(deger))
    bilgi, son_hata = None, None
    for ek in ("/videos", ""):
        try:
            bilgi = _sinirli(lambda: _yt_bilgi(taban + ek), 90)
            break
        except Hata:
            raise
        except ImportError:
            raise Hata("YouTube kanalı çözmek için yt-dlp gerekli (bu bilgisayarda yüklü değil).") from None
        except Exception as e:  # noqa: BLE001 — yt-dlp hata türleri çok
            son_hata = str(e)
    if bilgi is None:
        m = (son_hata or "").lower()
        if any(s in m for s in ("404", "not exist", "not found", "unavailable", "does not")):
            raise Hata("YouTube'da böyle bir kanal bulunamadı. @tanıtıcıyı kanal sayfasındaki gibi yaz.")
        raise Hata("YouTube'a ulaşılamadı ya da kanal okunamadı; biraz sonra yeniden dene.")
    cid = str(bilgi.get("channel_id") or "")
    if not UC_RE.fullmatch(cid):
        raise Hata("YouTube kanalı bulundu ama kanal kimliği okunamadı; bağlantıyı /channel/UC... biçiminde dene.")
    if tur == "id" and cid != deger:
        raise Hata("YouTube kanal kimliği eşleşmedi.")
    uid = str(bilgi.get("uploader_id") or "")
    tanitici = uid[1:] if uid.startswith("@") and TANITICI_RE.fullmatch(uid[1:]) else (deger if tur == "tanitici" else cid)
    ad = str(bilgi.get("channel") or bilgi.get("uploader") or tanitici)
    son = ""
    for e in bilgi.get("entries") or []:
        if isinstance(e, dict) and e.get("title"):
            son = str(e["title"])[:120]
            break
    return {"kanal_id": cid, "tanitici": tanitici, "ad": ad, "son_video": son}


# ---------------------------------------------------------------- önizleme + ekleme
class Onizlemeler:
    """Önizleme çözümlemesini sunucuda tutar; "Ekle" yalnız bu jetonla gelir (istemci kanal bilgisi uyduramaz)."""

    def __init__(self):
        self.kilit = threading.Lock()
        self.kayit: dict[str, dict] = {}

    def ver(self, icerik: dict) -> str:
        with self.kilit:
            simdi = time.monotonic()
            for k in [k for k, v in self.kayit.items() if simdi - v["t"] > ONIZLEME_OMRU]:
                del self.kayit[k]
            while len(self.kayit) >= ONIZLEME_AZAMI:
                del self.kayit[min(self.kayit, key=lambda k: self.kayit[k]["t"])]
            jeton = secrets.token_urlsafe(16)
            self.kayit[jeton] = {**icerik, "t": simdi}
            return jeton

    def al(self, jeton) -> dict:
        with self.kilit:
            v = self.kayit.get(jeton) if isinstance(jeton, str) else None
            if v is None or time.monotonic() - v["t"] > ONIZLEME_OMRU:
                raise Hata("Önizleme süresi doldu; kanalı yeniden kontrol et.")
            return v

    def at(self, jeton) -> None:
        with self.kilit:
            self.kayit.pop(jeton, None)


def onizle(girdi: dict, onizlemeler: Onizlemeler) -> dict:
    kick_g, yt_g = str(girdi.get("kick") or "").strip(), str(girdi.get("youtube") or "").strip()
    if not kick_g and not yt_g:
        raise Hata("Kick kanalı ya da YouTube kanalı yaz; en az biri şart.")
    kick = yt = None
    kanal = youtube = None
    if kick_g:
        kanal = kick_kanali_ayikla(kick_g)
        m = _yinelenme(dosyayi_oku(), {"kick:" + kanal})
        if m:
            raise Hata(m)
    if yt_g:
        youtube = youtube_ayikla(yt_g)
        if youtube[0] == "id":
            m = _yinelenme(dosyayi_oku(), {"yt:" + youtube[1].lower()})
            if m:
                raise Hata(m)
    if kanal:
        kick = kick_coz(kanal)
    if youtube:
        yt = youtube_coz(*youtube)
    kimlik = ({"kick:" + kick["kanal"]} if kick else set()) | ({"yt:" + yt["kanal_id"].lower()} if yt else set())
    m = _yinelenme(dosyayi_oku(), kimlik)
    if m:
        raise Hata(m)
    ad = (kick or yt)["ad"] if (kick or yt) else ""
    ad = _ad_temiz(ad, "Ad", bos_olur=True) or (kick or {}).get("kanal") or ""
    jeton = onizlemeler.ver({"kick": kick, "youtube": yt})
    return {"ok": True, "jeton": jeton,
            "kart": {"ad": ad, "kisa_ad": kisa_ad_oner(ad), "kick": kick, "youtube": yt}}


def ekle(girdi: dict, onizlemeler: Onizlemeler) -> dict:
    on = onizlemeler.al(girdi.get("jeton"))
    kick, yt = on["kick"], on["youtube"]
    if not kick and not yt:
        raise Hata("Önizleme geçersiz.")
    ad = _ad_temiz(girdi.get("ad"), "Ad")
    kisa = _ad_temiz(girdi.get("kisa_ad"), "Kısa ad", bos_olur=True) or kisa_ad_oner(ad)
    if not kisa:
        raise Hata("Kısa ad boş olamaz.")
    kimlik = ({"kick:" + kick["kanal"]} if kick else set()) | ({"yt:" + yt["kanal_id"].lower()} if yt else set())

    def islem(veri: dict):
        m = _yinelenme(veri, kimlik)
        if m:
            raise Hata(m)
        for r in veri["yayincilar"] + (veri.get("kaldirilanlar") or []):
            if str(r.get("ad", "")).casefold() == ad.casefold():
                raise Hata(f'"{ad}" adında bir yayıncı zaten var; adı değiştir.')
        if kick:
            rec = {"ad": ad, "kisa_ad": kisa, "platform": "kick", "kanal": kick["kanal"], "etkin": True}
        else:
            rec = {"ad": ad, "kisa_ad": kisa, "platform": "youtube", "kanal": yt["tanitici"].lower(), "etkin": True}
        if yt:
            rec["youtube_kanallari"] = [{"kanal_id": yt["kanal_id"], "tanitici": yt["tanitici"], "etkin": True}]
        veri["yayincilar"].append(rec)
        return rec
    rec = dosyayi_guncelle(islem)
    onizlemeler.at(girdi.get("jeton"))
    return {"ok": True, "mesaj": f"{ad} eklendi. Bir sonraki klip taramasında yayınları aranır."
            + ("" if kick else " (Yalnız YouTube kaynağı)"), "anahtar": anahtar(rec)}


# ---------------------------------------------------------------- düzenle, kaldır, geri getir
def _bul(veri: dict, liste: str, an) -> tuple[int, dict]:
    for i, r in enumerate(veri.get(liste) or []):
        if isinstance(r, dict) and anahtar(r) == an:
            return i, r
    raise Hata("Bu yayıncı listede yok; sayfayı yenile.")


def duzenle(girdi: dict) -> dict:
    an = girdi.get("anahtar")
    if not isinstance(an, str):
        raise Hata("Geçersiz yayıncı.")
    ad_yeni = _ad_temiz(girdi["ad"], "Ad") if "ad" in girdi else None
    kisa_yeni = _ad_temiz(girdi["kisa_ad"], "Kısa ad", bos_olur=True) if "kisa_ad" in girdi else None
    etkin = girdi.get("etkin")
    if etkin is not None and not isinstance(etkin, bool):
        raise Hata("Açık/kapalı değeri geçersiz.")
    yt = girdi.get("youtube")
    if yt is not None and not (isinstance(yt, list) and all(isinstance(x, dict) and isinstance(x.get("etkin"), bool)
                                                              and isinstance(x.get("kanal_id"), str) for x in yt)):
        raise Hata("YouTube kanal listesi geçersiz.")

    def islem(veri: dict):
        _i, r = _bul(veri, "yayincilar", an)
        if ad_yeni is not None and ad_yeni != r.get("ad"):
            for o in veri["yayincilar"] + (veri.get("kaldirilanlar") or []):
                if o is not r and str(o.get("ad", "")).casefold() == ad_yeni.casefold():
                    raise Hata(f'"{ad_yeni}" adında başka bir yayıncı var.')
            r["ad"] = ad_yeni
        if kisa_yeni is not None:
            r["kisa_ad"] = kisa_yeni or kisa_ad_oner(r["ad"])
        if etkin is not None:
            r["etkin"] = etkin
        for x in yt or []:
            for c in r.get("youtube_kanallari") or []:
                if c.get("kanal_id") == x["kanal_id"]:
                    c["etkin"] = x["etkin"]
        return r["ad"]
    ad = dosyayi_guncelle(islem)
    return {"ok": True, "mesaj": f"{ad} güncellendi."}


def kaldir(girdi: dict) -> dict:
    an = girdi.get("anahtar")
    if not isinstance(an, str):
        raise Hata("Geçersiz yayıncı.")

    def islem(veri: dict):
        i, r = _bul(veri, "yayincilar", an)
        del veri["yayincilar"][i]
        veri.setdefault("kaldirilanlar", []).append(
            {**r, "kaldirildi": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "sira": i})
        return r["ad"]
    ad = dosyayi_guncelle(islem)
    return {"ok": True, "mesaj": f"{ad} listeden çıkarıldı. Kayıtlı klipleri silinmedi; \"Kaldırılanlar\"dan geri getirebilirsin."}


def geri_getir(girdi: dict) -> dict:
    an = girdi.get("anahtar")
    if not isinstance(an, str):
        raise Hata("Geçersiz yayıncı.")

    def islem(veri: dict):
        i, r = _bul(veri, "kaldirilanlar", an)
        rec = {k: v for k, v in r.items() if k not in ("kaldirildi", "sira")}
        sira = r.get("sira") if isinstance(r.get("sira"), int) else len(veri["yayincilar"])
        del veri["kaldirilanlar"][i]
        m = _yinelenme(veri, _kimlikler(rec))
        if m:
            raise Hata(m)
        for o in veri["yayincilar"]:
            if str(o.get("ad", "")).casefold() == str(rec.get("ad", "")).casefold():
                raise Hata(f'"{rec.get("ad")}" adında başka bir yayıncı var; önce onun adını değiştir.')
        veri["yayincilar"].insert(max(0, min(sira, len(veri["yayincilar"]))), rec)
        if not veri["kaldirilanlar"]:
            del veri["kaldirilanlar"]
        return rec["ad"]
    ad = dosyayi_guncelle(islem)
    return {"ok": True, "mesaj": f"{ad} geri getirildi."}


def liste(klip_sayilari: dict[str, int] | None = None) -> dict:
    """Panelin listesi. Yalnız düz veri döner (HTML üretilmez; sayfa değerleri textContent ile yazar)."""
    veri = dosyayi_oku()
    sayilar = klip_sayilari or {}

    def ozet(r: dict, kaldirildi: bool = False) -> dict:
        o = {"anahtar": anahtar(r), "ad": str(r.get("ad") or ""), "kisa_ad": str(r.get("kisa_ad") or ""),
             "platform": str(r.get("platform") or ""), "kanal": str(r.get("kanal") or ""),
             "etkin": bool(r.get("etkin", True)),
             "youtube": [{"kanal_id": str(c.get("kanal_id") or ""), "tanitici": str(c.get("tanitici") or ""),
                          "etkin": bool(c.get("etkin", True))}
                         for c in (r.get("youtube_kanallari") or []) if isinstance(c, dict) and c.get("kanal_id")],
             "klip_sayisi": int(sayilar.get(r.get("ad"), 0))}
        if kaldirildi:
            o["kaldirildi"] = str(r.get("kaldirildi") or "")
        return o
    return {"ok": True, "yayincilar": [ozet(r) for r in veri["yayincilar"] if isinstance(r, dict)],
            "kaldirilanlar": [ozet(r, True) for r in (veri.get("kaldirilanlar") or []) if isinstance(r, dict)]}


# ---------------------------------------------------------------- "son yayından klip çıkar"
def _pencere_var() -> bool:
    if os.name != "nt":
        return False
    try:
        import ctypes
        return bool(ctypes.windll.kernel32.GetConsoleWindow())
    except Exception:  # noqa: BLE001
        return False


def _agaci_oldur(proc: subprocess.Popen) -> None:
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, timeout=30,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        else:
            import signal
            os.killpg(proc.pid, signal.SIGTERM)
    except Exception:  # noqa: BLE001
        pass
    try:
        proc.kill()
    except OSError:
        pass


class KlipCikar:
    """Yayından klip çıkarma: aynı anda TEK iş. `yayin_klip.py otomatik --yayinci <ad> --en-cok 1 --konusma` alt süreci,
    çıktısı satır satır okunur (durum satırı için). Sunucu kapanırsa iş de durdurulur."""

    def __init__(self):
        self.kilit = threading.Lock()
        self.durum: dict | None = None
        self.proc: subprocess.Popen | None = None
        self.iptal_istendi = False
        self.zaman_asimi = False
        self.zamanlayici: threading.Timer | None = None

    def mesgul(self) -> bool:
        with self.kilit:
            return bool(self.durum and self.durum["durum"] == "calisiyor")

    def baslat(self, ad: str) -> None:
        komut = (list(CIKAR_KOMUTU) if CIKAR_KOMUTU else [sys.executable, str(KOK / "tools" / "yayin_klip.py")])
        komut += ["--ayar", str(ayar_dosyasi()), "--dizin", str(yk.calisma_dizini()), "otomatik",
                  "--yayinci", ad, "--en-cok", "1", "--konusma"]
        env = {**os.environ, "PYTHONUTF8": "1", "KLIP_YAYINCILAR": str(ayar_dosyasi()),
               "YAYIN_KLIP_DIZIN": str(yk.calisma_dizini())}
        with self.kilit:
            if self.durum and self.durum["durum"] == "calisiyor":
                raise Hata("Zaten bir klip çıkarma işi sürüyor; bitmesini bekle ya da iptal et.")
            bayrak = 0 if (os.name != "nt" or _pencere_var()) else getattr(subprocess, "CREATE_NO_WINDOW", 0)
            try:
                self.proc = subprocess.Popen(komut, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                             text=True, encoding="utf-8", errors="replace", env=env, creationflags=bayrak,
                                             start_new_session=(os.name != "nt"))
            except OSError as e:
                raise Hata(f"İş başlatılamadı: {e}") from e
            self.iptal_istendi = False
            self.zaman_asimi = False
            self.durum = {"durum": "calisiyor", "yayinci": ad, "baslangic": time.monotonic(), "bitis": None,
                          "son_satir": "", "satir": 0, "mesaj": ""}
            proc = self.proc
        threading.Thread(target=self._oku, args=(proc,), name="klip-cikar", daemon=True).start()
        zamanlayici = threading.Timer(CIKAR_ZAMAN_ASIMI, self._zaman_asimi, args=(proc,))
        zamanlayici.daemon = True
        with self.kilit:
            self.zamanlayici = zamanlayici
        zamanlayici.start()

    def _zaman_asimi(self, proc) -> None:
        if proc.poll() is None:
            with self.kilit:
                self.zaman_asimi = True
            _agaci_oldur(proc)

    def _oku(self, proc: subprocess.Popen) -> None:
        try:
            for ham in proc.stdout:
                s = " ".join(ham.split())[:300]
                if s:
                    with self.kilit:
                        self.durum["son_satir"] = s
                        self.durum["satir"] += 1
        except (OSError, ValueError):
            pass
        finally:
            try:
                proc.stdout.close()
            except OSError:
                pass
        rc = proc.wait()
        with self.kilit:
            if self.zamanlayici is not None:
                self.zamanlayici.cancel()
            d = self.durum
            d["bitis"] = time.monotonic()
            if self.zaman_asimi:
                d["durum"], d["mesaj"] = "hata", f"{CIKAR_ZAMAN_ASIMI // 3600} saatte bitmedi, durduruldu."
            elif self.iptal_istendi:
                d["durum"], d["mesaj"] = "iptal", "İptal edildi. Yarım kalan iş varsa bir sonraki çalıştırmada tekrar denenir."
            elif rc == 0:
                d["durum"] = "bitti"
                d["mesaj"] = ("Bitti. Yeni klipler Klipler sekmesinde; listeyi yenile." if d["satir"]
                              else "Bitti: işlenecek yeni yayın bulunamadı (son 7 günde, daha önce işlenmemiş).")
            else:
                d["durum"], d["mesaj"] = "hata", f"Başarısız (kod {rc}): {d['son_satir'] or 'çıktı yok'}"

    def iptal(self) -> None:
        with self.kilit:
            if not (self.durum and self.durum["durum"] == "calisiyor" and self.proc):
                raise Hata("Çalışan bir iş yok.")
            self.iptal_istendi = True
            proc = self.proc
        _agaci_oldur(proc)

    def durdur(self) -> None:
        """Sunucu kapanırken: iş de durur."""
        with self.kilit:
            proc = self.proc if (self.durum and self.durum["durum"] == "calisiyor") else None
            self.iptal_istendi = True
        if proc is not None:
            _agaci_oldur(proc)

    def bekle(self, saniye: float = 30.0) -> bool:
        bitis = time.monotonic() + saniye
        while time.monotonic() < bitis:
            if not self.mesgul():
                return True
            time.sleep(0.02)
        return False

    def goster(self) -> dict:
        with self.kilit:
            d = self.durum
            if d is None:
                return {"durum": "yok"}
            simdi = time.monotonic()
            if d["bitis"] is not None and simdi - d["bitis"] > BITTI_SURESI:
                self.durum = None
                return {"durum": "yok"}
            gecen = int((d["bitis"] or simdi) - d["baslangic"])
            return {"durum": d["durum"], "yayinci": d["yayinci"], "gecen_sn": gecen, "son_satir": d["son_satir"],
                    "mesaj": d["mesaj"]}


class YayinciIsleri:
    """Sunucunun yayıncı yönetimi durumu: önizleme jetonları + klip çıkarma işi."""

    def __init__(self):
        self.onizlemeler = Onizlemeler()
        self.cikar = KlipCikar()

    def klip_cikar(self, girdi: dict, kesim_mesgul: bool) -> dict:
        an = girdi.get("anahtar")
        if not isinstance(an, str):
            raise Hata("Geçersiz yayıncı.")
        r = next((x for x in dosyayi_oku()["yayincilar"] if isinstance(x, dict) and anahtar(x) == an), None)
        if r is None:
            raise Hata("Bu yayıncı listede yok; sayfayı yenile.")
        if not r.get("etkin", True):
            raise Hata("Bu yayıncı kapalı; önce \"Açık\" anahtarını aç.")
        if kesim_mesgul:
            raise Hata("Şu an bir klip yeniden kesiliyor; bitince dene.")
        self.cikar.baslat(str(r["ad"]))
        return {"ok": True, "mesaj": f"{r['ad']} için son yayından klip çıkarma başladı."}

    def calisiyor(self) -> bool:
        return self.cikar.mesgul()

    def kapat(self) -> None:
        self.cikar.durdur()
