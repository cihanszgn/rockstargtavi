#!/usr/bin/env python3
"""CTRL+A GAME derleyicisi: tek komutla bütün site (dil kaydı) ve paylaşım kartları.

data/icerik.json (+ data/soylentiler.json, takvim.json, indirimler.json, ucretsiz.json)
  →  ana sayfa, haber merkezi ve haber sayfaları, indirimler, ücretsiz oyunlar, söylentiler,
     takvim, GTA VI dosyası ve elle yazılmış sayfaların ortak kabuğu (tools/site_derle.py),
     RSS, site haritası, arama dizini, paylaşım kartları (kart/) ve og.png.

Kullanım:  py tools/sosyal_derle.py
Aynı girdiyle tekrar çalıştırmak aynı çıktıyı üretir (değişiklik yoksa git temiz kalır).
tools/sosyal_yayinla.py bu dosyadan DILLER, GORUNEN, KLASOR, M, SITE ve kart_ad'ı alır.
"""
from __future__ import annotations

import argparse
import html
import io
import json
import pathlib
import re
import sys
import urllib.request
from datetime import datetime, timezone
from email.utils import format_datetime

KOK = pathlib.Path(__file__).resolve().parent.parent
SITE = "https://ctrl-agame.com"
GORUNEN = "ctrl-agame.com"
MARKA = "CTRL+A GAME"
from diller import DILLER, KAYIT, alan, tarih_yaz
import oyun_adi

oyun_takma = oyun_adi.takma_adlar(KOK)
ONEK = {d: '/' + (k['klasor'] + '/' if k['klasor'] else '') for d, k in KAYIT.items()}
HUB = {d: k['sayfa']['haber'] for d, k in KAYIT.items()}
KLASOR, FEED = alan('haber_klasor'), alan('feed')
GTA_HABER = {d: k['eski'][3] for d, k in KAYIT.items()}
KART_KLASOR = "kart"
TUR = ("haber", "ucretsiz", "cikis", "indirim", "guncelleme")

AY, M = alan('ay'), alan('sosyal')

e = lambda s: html.escape(str(s), quote=True)  # noqa: E731


def kaynak_adi(dil, ad):
    """Kaynak adları veride Türkçe yazılır; başka dilde Türkçe niteleme atılır, yalın yayın adı kalır."""
    if dil == "tr":
        return ad
    return re.sub(r"\s*\(?resm[iî]\b.*$", "", ad.split(" — ")[0]).strip() or ad


def metni_sar(c, metin, f, gen):
    """CJK metnini karakterlerden, Latin sözcükleri bölmeden satırlara ayırır."""
    if not re.search(r'[\u3400-\u9fff]', metin):
        parcalar = [k + ' ' for k in metin.split()]
    else:
        parcalar = re.findall(r"[A-Za-z0-9]+(?:[-.:’'][A-Za-z0-9]+)*|\s+|.", metin)
    satir, satirlar = '', []
    for k in parcalar:
        if c.textlength((satir + k).rstrip(), font=f) <= gen:
            satir += k
        elif satir.strip():
            # Noktalama işareti tek başına yeni satıra düşmesin.
            # Yanında önceki satırın son karakteri iner; Latin sözcük/sayı (III, 3.0.1) bölünmeden iner.
            onceki = satir.rstrip()
            son = re.search(r"[A-Za-z0-9]+(?:[-.:’'][A-Za-z0-9]+)*$|.$", onceki, re.S)
            if k in '，。！？：；、）》】' and son and len(son.group(0)) < len(onceki):
                satirlar.append(onceki[:-len(son.group(0))].rstrip())
                satir = son.group(0) + k
            else:
                satirlar.append(satir.rstrip())
                satir = k.lstrip()
        else:
            satir = k.lstrip()
    if satir.strip():
        satirlar.append(satir.rstrip())
    return satirlar


# ---------------------------------------------------------------- doğrulama
def yukle() -> list[dict]:
    yol = KOK / "data" / "icerik.json"
    veri = json.loads(yol.read_text(encoding="utf-8"))
    hatalar, gorulen = [], set()
    for i, x in enumerate(veri):
        k = x.get("id", f"#{i}")
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", str(x.get("id", ""))):
            hatalar.append(f"{k}: id küçük harf/rakam/tire olmalı")
        if k in gorulen:
            hatalar.append(f"{k}: id tekrar ediyor")
        gorulen.add(k)
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(x.get("tarih", ""))):
            hatalar.append(f"{k}: tarih YYYY-AA-GG olmalı")
        if x.get("tur") not in TUR:
            hatalar.append(f"{k}: tur {TUR} içinden olmalı")
        if "platform" in x and not (isinstance(x["platform"], list) and all(isinstance(p, str) and p.strip() for p in x["platform"])):
            hatalar.append(f"{k}: platform metin listesi olmalı (ör. [\"PS5\", \"PC\"])")
        ks = x.get("kaynaklar") or []
        if not ks or not all(str(s.get("url", "")).startswith("https://") and s.get("ad") for s in ks):
            hatalar.append(f"{k}: en az bir https kaynak (url + ad) gerekli")
        for d in DILLER:
            t = (x.get("diller") or {}).get(d)
            if not t:
                hatalar.append(f"{k}: {d} dili eksik")
                continue
            for alan in ("baslik", "ozet", "metin"):
                if not str(t.get(alan, "")).strip():
                    hatalar.append(f"{k}/{d}: {alan} boş")
            if len(t.get("baslik", "")) > 100:
                hatalar.append(f"{k}/{d}: başlık 100 karakteri aşıyor")
            for et in t.get("etiketler", []):
                if not re.fullmatch(r"#[A-Za-z0-9]+", et):
                    hatalar.append(f"{k}/{d}: etiket '{et}' geçersiz")
    if hatalar:
        print("İÇERİK HATASI:\n  " + "\n  ".join(hatalar))
        sys.exit(1)
    veri.sort(key=lambda x: (x["tarih"], x["id"]), reverse=True)
    return veri


# ---------------------------------------------------------------- yardımcılar
def yaz(yol: pathlib.Path, metin: str) -> bool:
    yol.parent.mkdir(parents=True, exist_ok=True)
    eski = yol.read_text(encoding="utf-8") if yol.exists() else None
    if eski == metin:
        return False
    yol.write_text(metin, encoding="utf-8", newline="\n")
    return True


def sayfa_url(dil: str, oid: str) -> str:
    return f"{SITE}/{KLASOR[dil]}/{oid}.html"


def kart_ad(oid: str, dil: str, tip: str) -> str:
    return f"{KART_KLASOR}/{oid}-{dil}-{tip}." + ("png" if tip == "og" else "jpg")


IG_GUN = 3       # Instagram kartı yalnız son 3 günün haberleri için üretilir (paylaşım penceresi)
IG_SAKLA = 14    # Instagram paylaşınca görseli kendine kopyalar; 14 günden eski kartlar silinir


def ayarlar() -> dict:
    return json.loads((KOK / "sosyal" / "ayarlar.json").read_text(encoding="utf-8"))


# Sosyal ağdan gelen ziyaretçiyi tarayıcı diline yönlendirir (yalnız utm_source varsa, bir kez).
YONLENDIR = """<script>(function(){try{var q=new URLSearchParams(location.search);if(!q.has('utm_source')||q.has('r'))return;
var s=%s,h=document.documentElement.lang,l=(navigator.languages&&navigator.languages.length?navigator.languages:[navigator.language||'']);
for(var i=0;i<l.length;i++){var d=String(l[i]).slice(0,2).toLowerCase();if(s[d]){if(d!==h){q.set('r','1');location.replace(s[d]+'?'+q.toString()+location.hash);}return;}}}catch(e){}})();</script>
"""


def rss(dil: str, veri: list[dict]) -> str:
    m = M[dil]
    son = veri[0]["tarih"] if veri else "2026-11-14"
    tarih = lambda iso: format_datetime(datetime.fromisoformat(iso).replace(hour=12, tzinfo=timezone.utc), usegmt=True)  # noqa: E731
    ogeler = []
    for x in veri[:30]:
        t = x["diller"][dil]
        u = sayfa_url(dil, x["id"])
        ogeler.append(
            f"  <item><title>{e(t['baslik'])}</title><link>{u}</link><guid isPermaLink=\"true\">{u}</guid>"
            f"<pubDate>{tarih(x['tarih'])}</pubDate><description>{e(t['ozet'])}</description></item>\n"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n<channel>\n'
        f"  <title>{e(m['feed'])}</title>\n  <link>{SITE}/{HUB[dil]}</link>\n  <description>{e(m['hub_aciklama'])}</description>\n"
        f"  <language>{dil}</language>\n  <lastBuildDate>{tarih(son)}</lastBuildDate>\n"
        f'  <atom:link href="{SITE}/{FEED[dil]}" rel="self" type="application/rss+xml"/>\n'
        + "".join(ogeler)
        + "</channel>\n</rss>\n"
    )


# ---------------------------------------------------------------- kartlar
# Kimlik: lacivert zemin, tuş (keycap) logosu ve etiketleri, başlık "seçili metin" gibi mavi şeritler üstünde.
ZEMIN, YUZEY, CIZGI = (11, 19, 34), (30, 44, 71), (42, 57, 88)
YAZI, SOLUK, SECIM, SECIM_ALT, TUS_ALT = (233, 238, 248), (154, 168, 195), (59, 108, 246), (36, 71, 184), (6, 11, 21)
TUR_RENK = {"haber": YAZI, "ucretsiz": (61, 220, 151), "indirim": (245, 184, 61), "cikis": (141, 176, 255), "guncelleme": SOLUK}
YAZI_DOSYA = {"genis": "Archivo-ExpandedExtraBold.ttf", "yari": "Archivo-SemiBold.ttf", "duz": "Archivo-Regular.ttf",
              "dar": "../../otomasyon/fontlar/Anton-Regular.ttf"}   # dar ve iri afiş yazısı (Instagram kartı başlığı)
YEDEK_YAZI = {
    "dar": ["C:/Windows/Fonts/impact.ttf", "C:/Windows/Fonts/segoeuib.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
    "genis": ["C:/Windows/Fonts/segoeuib.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
    "yari": ["C:/Windows/Fonts/seguisb.ttf", "C:/Windows/Fonts/segoeuib.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
    "duz": ["C:/Windows/Fonts/segoeui.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
}


def resmi_gorsel(veri, onbellek):
    """Yalnız yerel görsel kaydının HTTPS adresi; hata durumunda kapak üretilir."""
    from PIL import Image
    if not veri or not str(veri.get("url", "")).startswith("https://"):
        return None
    url = veri["url"]
    if url not in onbellek:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "CTRL-A-GAME-social/1.0"})
            with urllib.request.urlopen(req, timeout=8) as r:
                ham = r.read(8 * 1024 * 1024 + 1)
            if len(ham) > 8 * 1024 * 1024:
                raise ValueError("Görsel çok büyük")
            with Image.open(io.BytesIO(ham)) as img:
                onbellek[url] = img.convert("RGB")
        except (OSError, ValueError, TimeoutError, Image.DecompressionBombError):
            onbellek[url] = None
    return onbellek[url]


def kartlar(veri: list[dict], sosyal=None, *, cikti=None) -> tuple[int, int]:
    from PIL import Image, ImageDraw, ImageFont, ImageOps
    from sosyal_kuyruk import SABLON

    onbellek: dict = {}
    kart_dili = 'tr'
    resimler = {}

    def font(tur: str, boy: int):
        anahtar = (kart_dili, tur, boy)
        if anahtar not in onbellek:
            adaylar = [str(KOK / "tools" / "yazi" / YAZI_DOSYA[tur])] + YEDEK_YAZI[tur]
            if kart_dili == 'zh':
                ad = 'NotoSansSC-Regular.otf' if tur == 'duz' else 'NotoSansSC-Bold.otf'
                adaylar = [str(pathlib.Path(__file__).resolve().parent / 'yazi' / ad)]
            for a in adaylar:
                if pathlib.Path(a).exists():
                    onbellek[anahtar] = ImageFont.truetype(a, boy)
                    break
            else:
                raise SystemExit("Yazı tipi bulunamadı (tools/yazi/Archivo-*.ttf, Segoe UI veya DejaVu Sans gerekli).")
        return onbellek[anahtar]

    def sar(c, metin, f, gen):
        return metni_sar(c, metin, f, gen)

    def sigdir(c, metin, tur, buyuk, kucuk, gen, en_cok):
        for boy in range(buyuk, kucuk - 1, -2):
            f = font(tur, boy)
            s = sar(c, metin, f, gen)
            if len(s) <= en_cok and all(c.textlength(x, font=f) <= gen for x in s):
                return f, s
        f = font(tur, kucuk)
        s = sar(c, metin, f, gen)[:en_cok]
        while s and c.textlength(s[-1] + "…", font=f) > gen:
            s[-1] = s[-1].rsplit(" ", 1)[0] if " " in s[-1] else s[-1][:-1]
        s[-1] = s[-1].rstrip(".,;:") + "…"
        return f, s

    def kisalt(c, metin, f, gen):
        if c.textlength(metin, font=f) <= gen:
            return metin
        while metin and c.textlength(metin + "…", font=f) > gen:
            metin = metin[:-1]
        return metin.rstrip() + "…"

    def tus(c, x, y, metin, f, h, *, mavi=False, renk=YAZI, olc=False):
        """Bir tuş çizer (ya da yalnız genişliğini ölçer); genişliği döndürür."""
        pad = round(h * 0.36)
        w = round(c.textlength(metin, font=f)) + 2 * pad
        if olc:
            return w
        alt = max(4, round(h * 0.1))
        r = round(h * 0.2)
        c.rounded_rectangle((x, y + alt, x + w, y + h + alt), radius=r, fill=SECIM_ALT if mavi else TUS_ALT)
        c.rounded_rectangle((x, y, x + w, y + h), radius=r, fill=SECIM if mavi else YUZEY,
                            outline=SECIM if mavi else CIZGI, width=2)
        c.text((x + w / 2, y + (h + f.size * 0.7) / 2), metin, font=f, fill=(255, 255, 255) if mavi else renk, anchor="ms")
        return w

    def logo(c, x, y, h):
        f = font("genis", round(h * 0.42))
        x += tus(c, x, y, "Ctrl", f, h) + round(h * 0.16)
        fa = font("yari", round(h * 0.5))
        c.text((x, y + (h + fa.size * 0.7) / 2), "+", font=fa, fill=SOLUK, anchor="ls")
        x += round(c.textlength("+", font=fa)) + round(h * 0.16)
        x += tus(c, x, y, "A", f, h, mavi=True) + round(h * 0.3)
        fg = font("genis", round(h * 0.62))
        c.text((x, y + (h + fg.size * 0.7) / 2), "GAME", font=fg, fill=YAZI, anchor="ls")
        return x + round(c.textlength("GAME", font=fg))

    def secili(c, x, y, satirlar, f):
        """Başlığı seçili metin gibi çizer: her satırın arkasında bitişik mavi şerit."""
        adim, pad = round(f.size * 1.2), round(f.size * 0.22)
        for i, s in enumerate(satirlar):
            ust = y + i * adim
            c.rectangle((x, ust, x + 2 * pad + round(c.textlength(s, font=f)), ust + adim), fill=SECIM)
        for i, s in enumerate(satirlar):
            c.text((x + pad, y + i * adim + round(f.size * 0.95)), s, font=f, fill=(255, 255, 255), anchor="ls")
        return len(satirlar) * adim

    gorsel_veri: dict = {}

    def haber_gorseli(x):
        """Haberin kendi görseli (data/gorseller.json), yoksa oyununun resmî görseli."""
        if not gorsel_veri:
            def oku(ad, yedek):
                try:
                    return json.loads((KOK / "data" / ad).read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    return yedek
            gorsel_veri["haber"] = oku("gorseller.json", {})
            og = oku("oyun_gorselleri.json", {})
            gorsel_veri["oyun"] = og.get("oyun", {}) if isinstance(og, dict) else {}
            adlar = {}
            for o in oku("oyunlar.json", []):
                for ad in [o.get("ad"), o.get("kisa"), *(o.get("eslesme") or [])]:
                    if isinstance(ad, str) and ad.strip():
                        adlar[ad.strip().casefold()] = o.get("id")
            gorsel_veri["ad"] = adlar
        g = gorsel_veri["haber"].get(x.get("id"))
        if isinstance(g, dict) and g.get("url"):
            return g
        oid = gorsel_veri["ad"].get(str(x.get("oyun") or "").strip().casefold())
        return gorsel_veri["oyun"].get(oid)

    def buyuk(dil, s):
        """Büyük harf; Türkçede i→İ, ı→I."""
        if dil == "tr":
            s = s.replace("i", "İ").replace("ı", "I")
        return s.upper()

    VURGU_DISI = {"THE", "OF", "AND", "A", "AN", "IN", "ON", "TO", "FOR", "DE", "LA", "LE", "DU", "EL", "VE", "İLE"}
    NOKTALAMA = ".,:;!?()\"“”«»-–—|"
    def vurgu_parcalari(dil, satirlar, oyun):
        """Her satırı (metin, vurgulu) parçalarına böler: oyun adı ve sayılar vurgu renginde yazılır."""
        oyun_kume = {k.strip(NOKTALAMA) for k in oyun.upper().split()} - VURGU_DISI - {""}
        sonuc, ad_durum = [], 0   # 0: oyun adı henüz geçmedi, 1: adın içindeyiz, 2: ad bitti (ikinci kez boyanmaz)
        for s in satirlar:
            if dil == "zh":
                p = re.split(r"([A-Za-z0-9][A-Za-z0-9 .:'’+&-]*)", s)
                sonuc.append([(k, i % 2 == 1) for i, k in enumerate(p) if k])
                continue
            satir = []
            for i, w in enumerate(s.split(" ")):
                cek = re.sub(r"['’].*$", "", w).strip(NOKTALAMA)
                adda = cek.upper() in oyun_kume and ad_durum < 2
                ad_durum = 1 if adda else (2 if ad_durum == 1 else ad_durum)
                satir.append(((" " if i else "") + w, bool(cek) and (adda or any(h.isdigit() for h in cek))))
            sonuc.append(satir)
        if sonuc and not any(v for s in sonuc for _, v in s):   # hiçbir sözcük tutmadıysa ilk satır vurgulanır
            sonuc[0] = [(k, True) for k, _ in sonuc[0]]
        return sonuc

    AFIS_SIYAH, AFIS_VURGU, AFIS_SOLUK = (7, 8, 12), (255, 200, 40), (190, 196, 208)

    def afis_seritleri(W, H):
        """Bütün paylaşımların ortak imzası: sağ üstte (ve sol altta küçük) sarı ışık şeritleri."""
        anahtar = ("serit", W, H)
        if anahtar not in onbellek:
            from PIL import ImageFilter
            kat = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ck = ImageDraw.Draw(kat)
            ck.polygon([(W - 280, 0), (W - 200, 0), (W, 200), (W, 280)], fill=AFIS_VURGU + (235,))
            ck.polygon([(W - 140, 0), (W - 108, 0), (W, 108), (W, 140)], fill=AFIS_VURGU + (150,))
            ck.polygon([(0, H - 44), (0, H - 22), (22, H), (44, H)], fill=AFIS_VURGU + (235,))
            onbellek[anahtar] = (kat.filter(ImageFilter.GaussianBlur(30)), kat.filter(ImageFilter.GaussianBlur(1.2)))
        return onbellek[anahtar]

    def dikey_kart(x, dil, W, H):
        """Instagram kartı, afiş düzeni: siyah zemin, üstte büyük resmî görsel, altında ortalı başlık.

        Başlıkta oyun adı ve sayılar sarı, gerisi beyazdır. Görsel alta doğru siyaha erir; yazı görselin
        üstüne binmez. Logo şeridi ve sağ üstteki sarı ışık şeritleri her paylaşımda aynıdır."""
        nonlocal kart_dili
        kart_dili = dil
        t, m = x["diller"][dil], M[dil]
        # Kart tek başına okunur: başlıkta oyun adı yoksa öne eklenir (site başlığı değişmez).
        t = {**t, "baslik": oyun_adi.oyunlu_baslik(t["baslik"], x.get("oyun") or "", oyun_takma)}
        P = 60
        gen = W - 2 * P
        sosyal_tur = x.get("sosyal_tur")
        tur_ad = SABLON[dil][sosyal_tur] if sosyal_tur and sosyal_tur != "haber" else m["tur"][x["tur"]]
        gkayit = x.get("gorsel") or haber_gorseli(x)
        foto = resmi_gorsel(gkayit, resimler)
        c = ImageDraw.Draw(Image.new("RGB", (8, 8)))   # ölçüm için; asıl tuval yerleşim belli olunca kurulur
        # --- başlık: sığan en iri boy (iri boyda en çok 3, küçülünce 4 satır)
        for boy in range(84, 46, -4):
            fb = font("genis", boy)
            sb = sar(c, t["baslik"], fb, gen)
            if len(sb) <= (3 if boy > 64 else 4) and all(c.textlength(s, font=fb) <= gen for s in sb):
                break
        else:
            fb, sb = sigdir(c, t["baslik"], "genis", 46, 40, gen, 4)
        badim = round(fb.size * 1.22)
        fo, so = sigdir(c, t["ozet"], "duz", 34, 28, gen, 2)
        oadim = round(fo.size * 1.36)
        yb = H - 62                                   # altbilgi taban çizgisi
        y_ozet = yb - 78 - len(so) * oadim
        y_bas = y_ozet - 26 - len(sb) * badim
        y_etiket = y_bas - 20                         # tür ve oyun satırının taban çizgisi
        UST = 128                                     # logo şeridi
        alan = y_etiket - 6 - UST                     # görsele kalan yükseklik (etiket satırının arkasına kadar iner)
        # --- zemin ve görsel
        img = Image.new("RGB", (W, H), AFIS_SIYAH)
        gecis = Image.linear_gradient("L")
        siyah = Image.new("RGB", (W, H), AFIS_SIYAH)
        yumusak = 320                                 # görselin alt kenarının siyaha erime payı
        if foto is not None:
            # Geniş görsel tam ene oturur (kenardaki oyun logosu kesilmesin, en çok %15 kırpılır);
            # çok yayvan görsel alanın en az %80'ini dolduracak kadar kırpılır.
            ih = min(alan, max(round(W * foto.height / foto.width * 1.15), round(alan * 0.8)))
            net = ImageOps.fit(foto, (W, ih), centering=(0.5, 0.3))
            if ih < alan:
                # Yayvan görsel alanı doldurmaz: arkaya aynı görselin bulanık ve koyu hâli serilir,
                # net görsel ortada durur ve üst-alt kenarı yumuşakça karışır (boş siyah bant kalmaz).
                from PIL import ImageFilter
                arka = ImageOps.fit(foto, (W // 8, max(1, alan // 8))).filter(ImageFilter.GaussianBlur(5)).resize((W, alan))
                img.paste(Image.blend(arka, siyah.crop((0, 0, W, alan)), 0.5), (0, UST))
                kenar = max(1, min(48, ih // 4))
                maske = Image.new("L", (W, ih), 255)
                maske.paste(gecis.resize((W, kenar)), (0, 0))
                maske.paste(ImageOps.flip(gecis).resize((W, kenar)), (0, ih - kenar))
                img.paste(net, (0, UST + (alan - ih) // 2), maske)
                yumusak = 200
            else:
                img.paste(net, (0, UST))
            ih = alan
        else:
            ih = alan
            koyu = tuple(round(v * 0.16 + z * 0.84) for v, z in zip(AFIS_VURGU, AFIS_SIYAH))
            cu = ImageDraw.Draw(img)
            for i in range(-ih, W, 56):   # çapraz şeritler: görselsiz kartta doku
                cu.line((i, UST + ih, i + ih, UST), fill=koyu, width=14)
            cu.rectangle((0, 0, W, UST), fill=AFIS_SIYAH)
        erime = min(ih, yumusak)
        img.paste(siyah.crop((0, 0, W, erime)), (0, UST + ih - erime),
                  gecis.resize((W, erime)).point(lambda v: min(255, round(v * 1.4))))
        img.paste(siyah.crop((0, 0, W, 56)), (0, UST), ImageOps.flip(gecis).resize((W, 56)))
        img.paste(siyah.crop((0, 0, W, H - UST - ih)), (0, UST + ih))
        parlak, keskin = afis_seritleri(W, H)
        img.paste(parlak, (0, 0), parlak)
        img.paste(keskin, (0, 0), keskin)
        c = ImageDraw.Draw(img)
        lx = logo(c, P, 38, 50)
        if foto is None:
            fg, sg = sigdir(c, x["oyun"], "genis", 110, 52, gen, 3)
            adim = round(fg.size * 1.16)
            y0 = UST + max(0, (ih - 120 - len(sg) * adim) // 2)
            for i, s in enumerate(sg):
                c.text((W // 2, y0 + round(fg.size * 0.95) + i * adim), s, font=fg, fill=(255, 255, 255), anchor="ms")
        elif isinstance(gkayit, dict) and gkayit.get("kaynak"):
            fa = font("duz", 20)
            atif = kisalt(c, f"{SABLON[dil]['gorsel']}: {gkayit['kaynak']}", fa, max(60, W - 310 - lx - 30))
            c.text((W - 310, 38 + 25), atif, font=fa, fill=AFIS_SOLUK, anchor="rm")
        # --- tür ve oyun adı: başlığın üstünde tek ince satır
        fe = font("yari", 28)
        etiket = kisalt(c, f"{buyuk(dil, tur_ad)}  •  {x['oyun'].upper()}", fe, gen)
        c.text((W // 2, y_etiket), etiket, font=fe, fill=AFIS_SOLUK, anchor="ms")
        # --- başlık: ortalı; oyun adı ve sayılar sarı
        for i, satir in enumerate(vurgu_parcalari(dil, sb, x["oyun"])):
            bx = (W - sum(c.textlength(parca, font=fb) for parca, _ in satir)) / 2
            by = y_bas + round(fb.size * 0.95) + i * badim
            for parca, v in satir:
                c.text((bx, by), parca, font=fb, fill=AFIS_VURGU if v else (255, 255, 255), anchor="ls")
                bx += c.textlength(parca, font=fb)
        # --- özet
        for i, s in enumerate(so):
            c.text((W // 2, y_ozet + i * oadim + round(fo.size * 0.95)), s, font=fo, fill=AFIS_SOLUK, anchor="ms")
        # --- altbilgi: site solda, kaynak sağda, arada ince çizgi
        fs = font("yari", 30)
        c.text((P, yb), GORUNEN, font=fs, fill=(255, 255, 255), anchor="ls")
        fk = font("duz", 24)
        iki_nokta = " : " if dil == "fr" else ": "
        sol_w = round(c.textlength(GORUNEN, font=fs))
        sag = kisalt(c, f"{m['kaynak']}{iki_nokta}{kaynak_adi(dil, x['kaynaklar'][0]['ad'])}", fk, gen - sol_w - 40)
        c.text((W - P, yb), sag, font=fk, fill=AFIS_SOLUK, anchor="rs")
        x0, x1 = P + sol_w + 26, W - P - round(c.textlength(sag, font=fk)) - 26
        if x1 - x0 > 40:
            c.line((x0, yb - 10, x1, yb - 10), fill=(120, 96, 20), width=2)
        return img

    def kart(x, dil, W, H, ozetli):
        nonlocal kart_dili
        if ozetli:
            return dikey_kart(x, dil, W, H)
        kart_dili = dil
        t, m = x["diller"][dil], M[dil]
        img = Image.new("RGB", (W, H), ZEMIN)
        c = ImageDraw.Draw(img)
        P = 64 if W >= 1200 else 76
        gen = W - 2 * P
        # üst satır: logo solda, oyun ve tür tuşları sağda
        lh = 52 if W >= 1200 else 60
        lx = logo(c, P, P, lh)
        th, ft = lh - 8, font("yari", round((lh - 8) * 0.46))
        sosyal_tur = x.get("sosyal_tur")
        tur_ad = SABLON[dil][sosyal_tur] if sosyal_tur and sosyal_tur != "haber" else m["tur"][x["tur"]]
        tw = tus(c, 0, 0, tur_ad, ft, th, olc=True)
        bosluk = W - P - (lx + 40) - tw - 12
        oyun = kisalt(c, x["oyun"], ft, max(60, bosluk - 2 * round(th * 0.36)))
        ow = tus(c, 0, 0, oyun, ft, th, olc=True)
        if ozetli:   # dikey kartta etiketler logonun altına iner
            ty, tx = P + lh + 40, P
        else:
            ty, tx = P + 4, W - P - tw - 12 - ow
        tx += tus(c, tx, ty, oyun, ft, th) + 12
        tus(c, tx, ty, tur_ad, ft, th, renk=TUR_RENK.get(x["tur"], YAZI))
        # alt bilgi
        yb = H - P
        c.line([(P, yb - 54), (W - P, yb - 54)], fill=CIZGI, width=2)
        fs = font("yari", 30 if W >= 1200 else 32)
        c.text((P, yb), GORUNEN, font=fs, fill=YAZI, anchor="ls")
        fk = font("duz", 26 if W >= 1200 else 28)
        iki_nokta = " : " if dil == "fr" else ": "
        sag = kisalt(c, f"{tarih_yaz(dil, x['tarih'])}   {m['kaynak']}{iki_nokta}{kaynak_adi(dil, x['kaynaklar'][0]['ad'])}", fk,
                     gen - round(c.textlength(GORUNEN, font=fs)) - 40)
        c.text((W - P, yb), sag, font=fk, fill=SOLUK, anchor="rs")
        # başlık (ve dikey kartta özet), üst ile alt bilgi arasında dikey ortalı
        pad = 2 * round(64 * 0.22)
        if ozetli and sosyal_tur and sosyal_tur != "haber":
            # Ayrı kart türleri aynı logo, tuş, mavi seçim ve altbilgiyi kullanır.
            # Görsel ve metin alanları ayrıdır; başlık fotoğrafın üstüne binmez.
            gy, gh = ty + th + 32, 300
            foto = resmi_gorsel(x.get("gorsel"), resimler)
            if foto is not None:
                img.paste(ImageOps.fit(foto, (gen, gh)), (P, gy))
                atif = kisalt(c, f"{SABLON[dil]['gorsel']}: {x['gorsel'].get('kaynak', '')}", font("duz", 19), gen - 28)
                aw = round(c.textlength(atif, font=font("duz", 19))) + 24
                c.rectangle((W - P - aw, gy + gh - 36, W - P, gy + gh), fill=ZEMIN)
                c.text((W - P - 12, gy + gh - 10), atif, font=font("duz", 19), fill=YAZI, anchor="rs")
            else:
                c.rounded_rectangle((P, gy, W - P, gy + gh), radius=18, fill=YUZEY, outline=CIZGI, width=2)
                for i in range(5):
                    c.line((P + 24 + i * 32, gy + 20, P + 140 + i * 32, gy + gh - 20), fill=CIZGI, width=3)
                fg, sg = sigdir(c, x["oyun"], "genis", 56, 30, gen - 80, 3)
                for i, s in enumerate(sg):
                    c.text((W // 2, gy + gh // 2 + (i - len(sg) / 2) * round(fg.size * 1.2)), s,
                           font=fg, fill=YAZI, anchor="mt")
            fb, sb = sigdir(c, t["baslik"], "genis", 60, 34, gen - pad, 4)
            fo, so = sigdir(c, t["ozet"], "duz", 34, 26, gen, 3)
            ust, alt = gy + gh + 34, yb - 54 - 30
        elif ozetli:
            fb, sb = sigdir(c, t["baslik"], "genis", 70, 44, gen - pad, 6)
            fo, so = sigdir(c, t["ozet"], "duz", 40, 30, gen, 6)
            ust, alt = ty + th + 40, yb - 54 - 40
        else:
            fb, sb = sigdir(c, t["baslik"], "genis", 58, 36, gen - pad, 4)
            fo, so = None, []
            ust, alt = P + lh + 34, yb - 54 - 30
        bh = len(sb) * round(fb.size * 1.2)
        oh = (36 + len(so) * round(fo.size * 1.35)) if so else 0
        y = ust + max(0, (alt - ust - bh - oh) // 2)
        y += secili(c, P, y, sb, fb)
        if so:
            y += 36
            for s in so:
                c.text((P, y + round(fo.size * 0.95)), s, font=fo, fill=SOLUK, anchor="ls")
                y += round(fo.size * 1.35)
        return img

    def marka_karti(W=1200, H=630):
        """Kökteki og.png: dilden bağımsız marka kartı."""
        img = Image.new("RGB", (W, H), ZEMIN)
        c = ImageDraw.Draw(img)
        P = 72
        h = 132
        f = font("genis", round(h * 0.42))
        fa = font("yari", round(h * 0.5))
        fg = font("genis", round(h * 0.6))
        # ölç, ortala
        w1, w2 = tus(c, 0, 0, "Ctrl", f, h, olc=True), tus(c, 0, 0, "A", f, h, olc=True)
        bos = round(h * 0.16)
        gpad = round(fg.size * 0.18)
        toplam = w1 + bos + round(c.textlength("+", font=fa)) + bos + w2 + round(h * 0.28) + round(c.textlength("GAME", font=fg)) + 2 * gpad
        x, y = (W - toplam) // 2, 150
        x += tus(c, x, y, "Ctrl", f, h) + bos
        c.text((x, y + (h + fa.size * 0.7) / 2), "+", font=fa, fill=SOLUK, anchor="ls")
        x += round(c.textlength("+", font=fa)) + bos
        x += tus(c, x, y, "A", f, h, mavi=True) + round(h * 0.28)
        gw = round(c.textlength("GAME", font=fg)) + 2 * gpad
        c.rectangle((x, y - 6, x + gw, y + h + 14), fill=SECIM)
        c.text((x + gpad, y + (h + fg.size * 0.7) / 2 + 4), "GAME", font=fg, fill=(255, 255, 255), anchor="ls")
        # platform tuşları
        fp = font("yari", 30)
        adlar = ["PlayStation", "Xbox", "Nintendo", "PC"]
        ph, ara = 60, 18
        gw = sum(tus(c, 0, 0, a, fp, ph, olc=True) for a in adlar) + ara * (len(adlar) - 1)
        x, y = (W - gw) // 2, 372
        for a in adlar:
            x += tus(c, x, y, a, fp, ph) + ara
        yb = H - P + 10
        c.line([(P, yb - 50), (W - P, yb - 50)], fill=CIZGI, width=2)
        fs = font("yari", 30)
        c.text((W // 2, yb), GORUNEN, font=fs, fill=SOLUK, anchor="ms")
        return img

    def kaydet(img, yol, tip):
        tmp = yol.with_name(yol.stem + ".tmp" + yol.suffix)
        if tip == "og":  # 128 renkli PNG: metin kartı için küçük dosya, depo şişmez
            img.quantize(128, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE).save(tmp, "PNG", optimize=True)
        else:            # Instagram yalnız JPEG kabul eder
            img.save(tmp, "JPEG", quality=85, optimize=True, subsampling=2)
        if yol.exists() and yol.read_bytes() == tmp.read_bytes():
            tmp.unlink()
            return 0
        tmp.replace(yol)
        return 1

    from datetime import date
    bugun = date.today()
    kart_kok = pathlib.Path(cikti) if cikti is not None else KOK / KART_KLASOR
    kart_kok.mkdir(parents=True, exist_ok=True)

    def kart_yolu(oid, dil, tip):
        return kart_kok / pathlib.Path(kart_ad(oid, dil, tip)).name
    gerekli, yeni = set(), 0
    if cikti is None:
        yeni += kaydet(marka_karti(), KOK / "og.png", "og")
    for x in veri:
        yas = (bugun - date.fromisoformat(x["tarih"])).days
        for dil in DILLER:
            yol = kart_yolu(x["id"], dil, "og")
            gerekli.add(yol.name)
            yeni += kaydet(kart(x, dil, 1200, 630, False), yol, "og")
            if yas <= IG_SAKLA:  # IG kartı her dilde üretilir; hesap anahtarı sonradan eklense de hazır olsun
                yol = kart_yolu(x["id"], dil, "ig")
                gerekli.add(yol.name)
                if yas <= IG_GUN or yol.exists():
                    yeni += kaydet(kart(x, dil, 1080, 1350, True), yol, "ig")
    for x in sosyal or []:
        if x.get("sosyal_tur") == "haber":
            continue
        for dil in x["diller"]:
            yol = kart_yolu(x["id"], dil, "ig")
            gerekli.add(yol.name)
            yeni += kaydet(kart(x, dil, 1080, 1350, True), yol, "ig")
    silinen = 0
    for f in kart_kok.iterdir():
        if f.name not in gerekli:
            f.unlink()
            silinen += 1
    return yeni, silinen


# ---------------------------------------------------------------- ana akış
def main(argv=None) -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import site_derle
    import sosyal_kuyruk

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--yalniz-kartlar", action="store_true", help="site sayfalarına dokunmadan paylaşım kartlarını derle")
    args = ap.parse_args(argv)

    veri = yukle()
    sonuc = None if args.yalniz_kartlar else site_derle.derle(veri)
    simdi = datetime.now(timezone.utc)
    sosyal = sosyal_kuyruk.adaylar(veri, KOK, ayarlar(), simdi.date(), simdi)
    yeni_kart, silinen = kartlar(veri, sosyal)
    if sonuc is None:
        print(f"Tamam: {yeni_kart} kart yazıldı, {silinen} eski kart silindi.")
        return
    print(f"Tamam: {len(veri)} haber, {sonuc['sayfa']} sayfa ({sonuc['degisen']} dosya değişti); "
          f"{sonuc['soylenti']} söylenti, {sonuc['takvim']} çıkış, {sonuc['firsat']} fırsat, {sonuc['epic']} Epic oyunu; "
          f"{yeni_kart} kart yazıldı, {silinen} eski kart silindi, {sonuc['uyari']} uyarı.")


if __name__ == "__main__":
    main()
