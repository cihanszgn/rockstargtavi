"""Oyun merkezleri, oyuna özel temalı rehber sayfaları ve dizinleri (site_derle'nin parçası).

Sayfalar:
  oyun/<id>.html · en/game/<id>.html · fr/jeu/<id>.html · es/juego/<id>.html      (oyun merkezi)
  rehber/<id>.html · en/guide/<id>.html · fr/guide/<id>.html · es/guia/<id>.html  (rehber; yalnız veri varsa)
  oyun/index.html (SAYFA["oyunlar"]) ve rehberler.html (SAYFA["rehberler"]) dizinleri.
Veri: data/oyunlar.json, data/rehber/<oyun-id>.json, data/rehberler.json. Biri yoksa ya da bozuksa
derleme çökmez: uyarı yazılır, o parça basılmaz.

site_derle bu modülü içe aktarır, bagla() ile kendini S olarak verir, yukle() ile veriyi okutur.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import pathlib
import re
import urllib.parse

import oyun_tema as ot
from site_metin import ESLER, MARKA, OYUN_KLASOR, PL_AD, PLATFORMLAR, REHBER_KLASOR, SAYFA, T

S = None  # site_derle modülü (bagla ile)
OYUNLAR: list[dict] = []
OYUN: dict[str, dict] = {}
ESLES: dict[str, str] = {}      # ham anahtar -> oyun id
REHBER: dict[str, dict] = {}    # oyun id -> rehber
KAYNAKLAR: list[dict] = []      # rehberler.json (dış ücretsiz kaynaklar)
SURUM = {"css": "0"}
SIMDI_HUB: str | None = None    # merkez sayfası basılırken o oyunun çipi bağlantı olmaz
_UYARILAN: set = set()

# Bölüm kimliği bunlarla çakışırsa başına "b-" eklenir (kabuk, ana sayfa ve site.js kimlikleri).
AYRILMIS = {"main", "site-haritasi", "cag-metin", "takip", "takip-veri", "indirim-veri", "palet-liste", "haberler",
            "firsatlar", "ucretsiz", "radar", "yaklasan", "gta", "populer", "gundem", "suzgec-form"}
KATEGORI_SIRA = ("resmi", "baslangic", "wiki", "ileri", "arac")
# tur.en içinde aranan sözcükler -> filtre grubu (sıra önemli: MMORPG, RPG'den önce)
TUR_GRUP = [("br", ("battle",)), ("moba", ("moba",)), ("mmorpg", ("mmo",)), ("ryo", ("rpg",)),
            ("spor", ("football", "soccer", "sport")), ("acik", ("open-world", "open world")),
            ("sandbox", ("sandbox", "platform")), ("nisanci", ("fps", "shooter"))]
PL_SIRA = tuple(PLATFORMLAR) + ("Mobil",)
KALIN = re.compile(r"\*\*(.+?)\*\*")
ROMA = ((10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"))


def bagla(mod) -> None:
    global S
    S = mod


# ---------------------------------------------------------------- küçük yardımcılar
def _metin(v) -> str:
    if v is None or isinstance(v, (dict, list, tuple, bool)):
        return ""
    return str(v).strip()


def satir_ici(s) -> str:
    """Kaçışlanmış metin; yalnız **kalın** işlenir."""
    return KALIN.sub(r"<strong>\1</strong>", S.e(_metin(s)))


def duz(s) -> str:
    return KALIN.sub(r"\1", _metin(s))


def kisalt(s: str, n: int = 165) -> str:
    s = " ".join(str(s).split())
    if len(s) <= n:
        return s
    return s[:n].rsplit(" ", 1)[0].rstrip(",;:.–—-") + "…"


def roma(n: int) -> str:
    h = ""
    for d, r in ROMA:
        while n >= d:
            h, n = h + r, n - d
    return h


def adim_no(t: dict, i: int) -> str:
    a = t["adim"]
    if a in ("roma", "roma-halka"):
        return roma(i)
    if a == "kod":
        return f"{i:02d}"
    if a == "koordinat":
        return f"{chr(65 + (i - 1) // 9)}{(i - 1) % 9 + 1}"
    return str(i)


def baslik_bol(s: str) -> tuple[str, str]:
    """'Oyun Rehberi: alt başlık' -> (ana, vurgu). Ayraç yoksa vurgu boş."""
    for a in (": ", " – ", " — ", " - "):
        i = s.find(a)
        if 2 < i and len(s) - i - len(a) >= 3:
            return s[:i].strip(), s[i + len(a):].strip()
    return s, ""


def tur_grup(tur_en: str) -> str:
    t = tur_en.lower()
    return next((g for g, sozler in TUR_GRUP if any(k in t for k in sozler)), "diger")


def pl_ad(dil: str, p: str) -> str:
    return PL_AD.get(p, {}).get(dil, p)


def alan(url: str) -> str:
    return re.sub(r"^www\.", "", urllib.parse.urlsplit(url).hostname or "")


def _toplu(v) -> list[str]:
    """Bloktaki bütün metin parçaları (bilinmeyen blok türü ve okuma süresi için)."""
    if isinstance(v, dict):
        return [m for k, w in v.items() if k != "tip" for m in _toplu(w)]
    if isinstance(v, list):
        return [m for w in v for m in _toplu(w)]
    m = _metin(v)
    return [m] if m else []


# ---------------------------------------------------------------- veri
def yukle() -> None:
    for x in (OYUNLAR, KAYNAKLAR):
        x.clear()
    for x in (OYUN, ESLES, REHBER):
        x.clear()
    _UYARILAN.clear()
    _oyunlari_oku()
    _rehberleri_oku()
    _kaynaklari_oku()


def _oyunlari_oku() -> None:
    for i, x in enumerate(S._liste(S._json("oyunlar.json", False), "oyunlar")):
        if not isinstance(x, dict):
            S.uyar(f"oyunlar.json #{i}: nesne değil; atlandı.")
            continue
        k, ad = x.get("id"), _metin(x.get("ad"))
        if not (isinstance(k, str) and S.SLUG.fullmatch(k)) or k == "index" or k in OYUN or not ad:
            S.uyar(f"oyunlar.json #{i} ({k}): id veya ad geçersiz; atlandı.")
            continue
        tur_h = x.get("tur") if isinstance(x.get("tur"), dict) else {}
        dl_h = x.get("diller") if isinstance(x.get("diller"), dict) else {}

        def tanim(d: str) -> str:
            v = dl_h.get(d)
            return _metin(v.get("tanim")) if isinstance(v, dict) else ""

        tur = {d: _metin(tur_h.get(d)) or _metin(tur_h.get("en")) or _metin(tur_h.get("tr")) for d in S.DILLER}
        r = x.get("resmi")
        resmi = {"url": r["url"], "ad": _metin(r.get("ad")) or ad} if isinstance(r, dict) and S.https(r.get("url")) else None
        o = {"id": k, "ad": ad, "kisa": _metin(x.get("kisa")) or ad,
             "eslesme": [_metin(s) for s in x.get("eslesme") or [] if _metin(s)],
             "tur": tur, "tanim": {d: tanim(d) or tanim("en") or tanim("tr") for d in S.DILLER},
             "platform": [_metin(p) for p in x.get("platform") or [] if _metin(p)],
             "gelistirici": _metin(x.get("gelistirici")), "resmi": resmi}
        o["tema"] = ot.tema_al(k, tur["en"])
        o["grup"] = tur_grup(tur["en"])
        OYUNLAR.append(o)
        OYUN[k] = o
    # eşleştirme: önce kimlik ve ad, sonra kısa ad ve eşleşme listesi, en son tema takma adları
    for o in OYUNLAR:
        for s in (o["id"], o["ad"]):
            ESLES.setdefault(S.ham_anahtar(s), o["id"])
    for o in OYUNLAR:
        for s in (o["kisa"], *o["eslesme"]):
            a = S.ham_anahtar(s)
            if a:
                ESLES.setdefault(a, o["id"])
    for takma, hedef in ot.TAKMA.items():
        if hedef in OYUN:
            ESLES.setdefault(takma, hedef)


def _rehber_klasoru() -> pathlib.Path:
    deneme = os.environ.get("SITE_DENEME_VERI")
    if deneme and (pathlib.Path(deneme) / "rehber").is_dir():
        return pathlib.Path(deneme) / "rehber"
    return S.KOK / "data" / "rehber"


def _rehberleri_oku() -> None:
    klasor = _rehber_klasoru()
    for y in sorted(klasor.glob("*.json")) if klasor.is_dir() else []:
        ad = f"rehber/{y.name}"
        try:
            metin = y.read_text(encoding="utf-8").strip()
            v = json.loads(metin) if metin else None
        except (OSError, ValueError) as h:
            S.uyar(f"{ad} okunamadı ({h}); atlandı.")
            continue
        if not isinstance(v, dict):
            S.uyar(f"{ad}: boş ya da nesne değil; atlandı.")
            continue
        oid = ESLES.get(S.ham_anahtar(_metin(v.get("oyun")) or y.stem))
        if not oid:
            S.uyar(f"{ad}: oyun '{v.get('oyun') or y.stem}' oyunlar.json'da yok; atlandı.")
            continue
        if oid in REHBER:
            S.uyar(f"{ad}: {oid} için ikinci rehber; atlandı.")
            continue
        g = _metin(v.get("guncelleme"))[:10]
        if g and not S.iso_gun(g):
            S.uyar(f"{ad}: guncelleme '{v.get('guncelleme')}' geçersiz; tarih gösterilmedi.")
            g = ""
        kaynaklar = [{"url": k["url"], "ad": _metin(k.get("ad"))} for k in v.get("kaynaklar") or []
                     if isinstance(k, dict) and S.https(k.get("url")) and _metin(k.get("ad"))]
        dl_h = v.get("diller") if isinstance(v.get("diller"), dict) else {}
        diller = {}
        for d in S.DILLER:
            t = dl_h.get(d)
            if not isinstance(t, dict):
                S.uyar(f"{ad}: {d} dili yok; o dilde sayfa basılmadı.")
                continue
            bolumler, gorulen = [], set()
            for j, b in enumerate(t.get("bolumler") or []):
                if not isinstance(b, dict):
                    continue
                bb = _metin(b.get("baslik"))
                bloklar = [x for x in b.get("bloklar") or [] if isinstance(x, dict)]
                if not bb or not bloklar:
                    S.uyar(f"{ad} ({d}) bölüm #{j + 1}: başlık ya da blok yok; atlandı.")
                    continue
                bid = S.slug(_metin(b.get("id"))) or S.slug(bb) or f"bolum-{j + 1}"
                if bid.startswith(("o-", "po-")) or bid in AYRILMIS or bid[0].isdigit():
                    bid = "b-" + bid
                aday, n = bid, 2
                while aday in gorulen:
                    aday, n = f"{bid}-{n}", n + 1
                gorulen.add(aday)
                bolumler.append({"id": aday, "baslik": bb, "bloklar": bloklar})
            baslik, ozet = _metin(t.get("baslik")), _metin(t.get("ozet"))
            if not (baslik and ozet and bolumler):
                S.uyar(f"{ad}: {d} dilinde başlık, özet ya da bölüm eksik; o dilde sayfa basılmadı.")
                continue
            ham_k = t.get("kunye") if isinstance(t.get("kunye"), list) else []
            kunye = [{"ad": _metin(k.get("ad")), "deger": _metin(k.get("deger"))} for k in ham_k
                     if isinstance(k, dict) and _metin(k.get("ad")) and _metin(k.get("deger"))]
            # sürüm rozeti: Türkçede üst düzey 'surum'; diğer dillerde o dilin künyesindeki 4. satır
            surum = _metin(v.get("surum")) if d == "tr" else ""
            if not surum and len(ham_k) > 3 and isinstance(ham_k[3], dict):
                surum = _metin(ham_k[3].get("deger"))
            kelime = len(re.findall(r"\w+", " ".join(_toplu([baslik, ozet, bolumler]))))
            diller[d] = {"baslik": baslik, "ozet": ozet, "kunye": kunye, "bolumler": bolumler, "surum": surum,
                         "dk": max(1, math.ceil(kelime / 200))}
        if not diller:
            S.uyar(f"{ad}: geçerli dil yok; rehber basılmadı.")
            continue
        REHBER[oid] = {"oyun": oid, "guncelleme": g, "kaynaklar": kaynaklar, "diller": diller}


def _kaynaklari_oku() -> None:
    gorulen = set()
    for i, x in enumerate(S._liste(S._json("rehberler.json", False), "rehberler", "kaynaklar")):
        if not isinstance(x, dict):
            continue
        hub = _metin(x.get("hub"))
        hedef = "genel" if hub == "genel" else (hub if hub in OYUN else ESLES.get(S.ham_anahtar(hub or _metin(x.get("oyun")))))
        if not hedef or not S.https(x.get("url")):
            S.uyar(f"rehberler.json #{i} ({x.get('id')}): oyun ya da https adresi yok; atlandı.")
            continue
        if (hedef, x["url"]) in gorulen:
            continue
        gorulen.add((hedef, x["url"]))
        dl_h = x.get("diller") if isinstance(x.get("diller"), dict) else {}

        def al(d: str, k: str) -> str:
            v = dl_h.get(d)
            return _metin(v.get(k)) if isinstance(v, dict) else ""

        KAYNAKLAR.append({
            "hub": hedef, "url": x["url"], "kaynak": _metin(x.get("kaynak")), "kategori": _metin(x.get("kategori")),
            "dil": [_metin(l).lower() for l in x.get("dil") or [] if _metin(l)], "lisans": _metin(x.get("lisans")),
            "acik": x.get("acik") is True,
            "diller": {d: (al(d, "baslik") or al("en", "baslik") or al("tr", "baslik") or _metin(x.get("kaynak")) or alan(x["url"]),
                           al(d, "aciklama") or al("en", "aciklama") or al("tr", "aciklama")) for d in S.DILLER}})
    KAYNAKLAR.sort(key=lambda k: KATEGORI_SIRA.index(k["kategori"]) if k["kategori"] in KATEGORI_SIRA else len(KATEGORI_SIRA))


# ---------------------------------------------------------------- eşleştirme ve yollar
def oyun_id(ad) -> str | None:
    return ESLES.get(S.ham_anahtar(ad)) if ad and ESLES else None


def oyun_bul(ad) -> dict | None:
    return OYUN.get(oyun_id(ad))


def takip_anahtar(ad) -> str:
    """Takip anahtarı: bilinen oyunun bütün adları tek anahtara iner."""
    o = oyun_bul(ad)
    return S.ham_anahtar(o["ad"] if o else ad)


def hub_yol(dil: str, oid: str) -> str:
    return f"{OYUN_KLASOR[dil]}/{oid}.html"


def rehber_yol(dil: str, oid: str) -> str:
    return f"{REHBER_KLASOR[dil]}/{oid}.html"


def rehber_var(oid: str, dil: str) -> bool:
    r = REHBER.get(oid)
    return bool(r and dil in r["diller"])


def cip(dil: str, ad: str) -> str:
    """Oyun çipi oyunun tema renginde (t-<id> ya da genel renk kovası tv-<n>; renk oyun-tema.css'ten, yoksa site rengi)."""
    o = oyun_bul(ad) if dil else None
    renk = S.kapak_tema(ad)[0].split()[0]
    if o and o["id"] != SIMDI_HUB:
        return f'<a class="cip cip-oyun cip-tema {renk}" href="{S.u(hub_yol(dil, o["id"]))}">{S.e(ad)}</a>'
    return f'<span class="cip cip-oyun cip-tema {renk}">{S.e(ad)}</span>'


def oyun_adi_html(dil: str, ad: str) -> str:
    """Takvim satırındaki oyun adı: biliniyorsa merkez sayfasına bağlanır."""
    o = oyun_bul(ad)
    if o and o["id"] != SIMDI_HUB:
        return f'<a href="{S.u(hub_yol(dil, o["id"]))}">{S.e(ad)}</a>'
    return S.e(ad)


def bas_ek(t: dict | None = None) -> str:
    """Tema stil dosyası (+ temanın başlık yazı tipi ön yüklemesi)."""
    if not OYUNLAR:
        return ""
    h = f'<link rel="stylesheet" href="/oyun-tema.css?v={SURUM["css"]}">\n'
    if t:
        dosya = ot.YAZILAR.get(t["yazi"], ot.YAZILAR["archivo"])[1]
        if dosya:
            h += f'<link rel="preload" href="/fonts/oyun/{dosya}.woff2" as="font" type="font/woff2" crossorigin>\n'
    return h


def _ld(veri) -> str:
    return f'<script type="application/ld+json">{S.gom(veri)}</script>\n'


def _iz(dil: str, parcalar: list[tuple[str, str | None]]) -> tuple[str, str]:
    li = "".join(f'<li><a href="{S.u(y)}">{S.e(a)}</a></li>' if y else f'<li aria-current="page">{S.e(a)}</li>'
                 for a, y in parcalar)
    ld = {"@context": "https://schema.org", "@type": "BreadcrumbList",
          "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": a, **({"item": S.tam(y)} if y else {})}
                              for i, (a, y) in enumerate(parcalar)]}
    return f'<nav class="o-iz" aria-label="{S.e(T[dil]["o_iz"])}"><ol>{li}</ol></nav>', _ld(ld)


def _kahraman(dil: str, o: dict, iz: str, ust: str, ana: str, vurgu: str, ozet: str, ek: str) -> str:
    t = o["tema"]
    v = f'<span class="o-h1-vurgu">{S.e(vurgu)}</span>' if vurgu else ""
    # tek kelimesi uzun başlık (ör. ES "principiantes", "BATTLEGROUNDS") dar ekranda kutusundan taşmasın: CSS yazıyı küçültür
    uzun = " o-h1-uzun" if max((len(p) for p in re.split(r"[\s\-–/]+", ana)), default=0) >= 12 else ""
    gor = S.oyun_gorsel(o["id"]) if hasattr(S, "oyun_gorsel") else None
    gorsel_kutu = f'<div class="o-amblem" aria-hidden="true">{ot.amblem(t)}</div>'
    if gor:
        src = gor.get("genis") or gor["url"]
        gorsel_kutu = (f'<div class="o-amblem o-amblem-gorsel">{ot.amblem(t)}'
                       f'<img class="kg-img o-kahraman-img" src="{S.e(src)}" alt="{S.e(o["ad"])}" '
                       f'width="{gor["en"]}" height="{gor["boy"]}" loading="lazy" decoding="async" '
                       'referrerpolicy="no-referrer" onerror="this.remove()">'
                       f'<span class="kg-not">{S.e(T[dil]["gorsel_not"])}: {S.e(gor["kaynak"])}</span></div>')
    return (f'<header class="o-kahraman{" o-kahraman-gorselli" if gor else ""}"><div class="o-motif" aria-hidden="true"></div>'
            f'<span class="o-dev" aria-hidden="true">{S.e(o["kisa"])}</span>\n'
            f'<div class="wrap o-k-ic">{iz}<div class="o-k-metin"><p class="o-ust-et">{ust}</p>'
            f'<h1 class="o-h1{uzun}"><span class="o-h1-ana">{S.e(ana)}</span>{v}</h1>'
            f'<p class="o-ozet">{S.e(ozet)}</p>{ek}</div>\n'
            f'{gorsel_kutu}</div></header>\n')


def _rozet(deger: str, baslik: str = "", sinif: str = "", title: str = "") -> str:
    b = f"<b>{S.e(baslik)}</b>" if baslik else ""
    tt = f' title="{S.e(title)}"' if title else ""
    return f'<li class="o-rozet{sinif}"{tt}>{b}<span class="o-rozet-deger">{deger}</span></li>'


# ---------------------------------------------------------------- rehber blokları
def _blok(dil: str, t: dict, oid: str, x: dict, bolum: str, sss: list) -> str:
    tt, tip = T[dil], x.get("tip")
    if tip == "p" and _metin(x.get("metin")):
        return f"<p>{satir_ici(x['metin'])}</p>"
    if tip in ("ipucu", "uyari") and _metin(x.get("metin")):
        return (f'<aside class="o-kutu o-{tip}"><p class="o-kutu-et">{S.e(tt["r_" + tip])}</p>'
                f"<p>{satir_ici(x['metin'])}</p></aside>")
    og = x.get("ogeler") if isinstance(x.get("ogeler"), list) else []
    if tip == "liste":
        li = "".join(f"<li>{satir_ici(s)}</li>" for s in og if _metin(s))
        if li:
            return f'<ul class="o-liste">{li}</ul>'
    elif tip == "adimlar":
        li, n = [], 0
        for s in og:
            if not isinstance(s, dict) or not (_metin(s.get("baslik")) or _metin(s.get("metin"))):
                continue
            n += 1
            bas = f'<strong class="o-adim-bas">{satir_ici(s.get("baslik"))}</strong>' if _metin(s.get("baslik")) else ""
            m = f"<p>{satir_ici(s.get('metin'))}</p>" if _metin(s.get("metin")) else ""
            li.append(f'<li><span class="o-adim-no" aria-hidden="true"><span>{adim_no(t, n)}</span></span>'
                      f'<div class="o-adim-ic">{bas}{m}</div></li>')
        if li:
            return f'<ol class="o-adimlar">{"".join(li)}</ol>'
    elif tip == "tablo":
        bas = [_metin(c) for c in x.get("basliklar") or []] if isinstance(x.get("basliklar"), list) else []
        satirlar = [r for r in x.get("satirlar") or [] if isinstance(r, list) and any(_metin(c) for c in r)]
        if satirlar:
            th = "".join(f'<th scope="col">{satir_ici(c)}</th>' for c in bas)
            tr = []
            for r in satirlar:
                h = [f'<th scope="row">{satir_ici(r[0])}</th>']
                for j, c in enumerate(r[1:], 1):
                    et = f' data-et="{S.e(duz(bas[j]))}"' if j < len(bas) and bas[j] else ""
                    h.append(f"<td{et}>{satir_ici(c)}</td>")
                tr.append(f"<tr>{''.join(h)}</tr>")
            return (f'<div class="o-tablo" role="region" tabindex="0" aria-label="{S.e(duz(bolum))}"><table>'
                    + (f"<thead><tr>{th}</tr></thead>" if th else "") + f"<tbody>{''.join(tr)}</tbody></table></div>")
    elif tip == "sss":
        ci = []
        for s in og:
            if isinstance(s, dict) and _metin(s.get("s")) and _metin(s.get("c")):
                ci.append(f"<details><summary>{satir_ici(s['s'])}</summary><p>{satir_ici(s['c'])}</p></details>")
                sss.append((duz(s["s"]), duz(s["c"])))
        if ci:
            return f'<div class="o-sss">{"".join(ci)}</div>'
    # bilinmeyen ya da boş blok: uyar, bulunan metni düz paragraf bas
    anahtar = (oid, str(tip))
    if anahtar not in _UYARILAN:
        _UYARILAN.add(anahtar)
        S.uyar(f"rehber/{oid}: '{tip}' blok türü tanınmadı ya da boş; düz paragraf basıldı.")
    metin = " ".join(_toplu(x))
    return f"<p>{satir_ici(metin)}</p>" if metin else ""


def _ucretsiz_liste(dil: str, oid: str, genel: bool = True) -> str:
    tt = T[dil]
    ogeler = [k for k in KAYNAKLAR if k["hub"] == oid] + ([k for k in KAYNAKLAR if k["hub"] == "genel"] if genel else [])
    li = []
    for k in ogeler:
        baslik, aciklama = k["diller"][dil]
        meta = []
        if k["kategori"]:
            meta.append(f'<span class="cip">{S.e(tt["r_kategori"].get(k["kategori"], k["kategori"]))}</span>')
        if k["dil"]:
            meta.append(f'<span class="cip"><span class="gizli">{S.e(tt["r_dil"])}: </span>{S.e(", ".join(l.upper() for l in k["dil"]))}</span>')
        if k["acik"]:
            meta.append(f'<span class="cip" title="{S.e(k["lisans"])}">{S.e(tt["r_acik"])}</span>')
        li.append(f'<li><a href="{S.e(k["url"])}" rel="noopener">{S.e(baslik)}</a>'
                  + (f"<p>{S.e(aciklama)}</p>" if aciklama else "")
                  + f'<p class="o-kmeta">{"".join(meta)}<span class="gizli"> · </span><span class="o-alan">{S.e(alan(k["url"]))}</span></p></li>')
    return f'<ul class="o-ucretsiz-liste">{"".join(li)}</ul>' if li else ""


def _rehber_sirasi(dil: str) -> list[str]:
    return sorted((oid for oid in REHBER if rehber_var(oid, dil) and oid in OYUN), key=lambda i: S.norm(OYUN[i]["ad"]))


# ---------------------------------------------------------------- rehber sayfası
def rehber_sayfasi(dil: str, oid: str) -> str:
    o, r, tt = OYUN[oid], REHBER[oid], T[dil]
    t, rd = o["tema"], r["diller"][dil]
    yol = rehber_yol(dil, oid)
    iz, iz_ld = _iz(dil, [(tt["nav"]["ana"], SAYFA["ana"][dil]), (tt["nav"]["rehberler"], SAYFA["rehberler"][dil]), (o["ad"], None)])

    rozet = []
    if r["guncelleme"]:
        rozet.append(_rozet(S.zaman_etiketi(dil, r["guncelleme"]), tt["r_guncel"]))
    rozet.append(_rozet(S.e(tt["r_okuma"].format(n=rd["dk"]))))
    kisa_surum = rd["surum"].split(";")[0].strip()
    if kisa_surum:
        rozet.append(_rozet(S.e(kisa_surum), tt["r_surum"], " o-rozet-surum", rd["surum"]))
    arac = (f'<div class="o-k-arac">{S.takip_dugme(dil, o["ad"])}'
            f'<a class="dugme" href="{S.u(hub_yol(dil, oid))}">{S.e(tt["r_hub"])}</a></div>')
    ana, vurgu = baslik_bol(rd["baslik"])
    ust = f'{S.e(tt["tur_ara"]["rehber"])} · {S.e(o["ad"])}'
    hero = _kahraman(dil, o, iz, ust, ana, vurgu, rd["ozet"], f'<ul class="o-rozetler">{"".join(rozet)}</ul>{arac}')

    sss: list = []
    bolumler = []
    for b in rd["bolumler"]:
        ic = "".join(_blok(dil, t, oid, x, b["baslik"], sss) for x in b["bloklar"])
        bolumler.append(f'<section class="o-bolum" id="{b["id"]}"><div class="o-bolum-bas"><h2>{satir_ici(b["baslik"])}</h2>'
                        f'<a class="o-capa" href="#{b["id"]}" aria-label="{S.e(tt["r_capa"])}: {S.e(duz(b["baslik"]))}">#</a></div>\n'
                        f'{ic}</section>\n')
    toc = [(b["id"], duz(b["baslik"])) for b in rd["bolumler"]]
    bas_ek_bolum = ""
    if rd["kunye"]:
        dl = "".join(f"<dt>{S.e(k['ad'])}</dt><dd>{satir_ici(k['deger'])}</dd>" for k in rd["kunye"])
        bas_ek_bolum = (f'<section class="o-ek o-ek-bas" id="o-kunye"><h2>{S.e(tt["r_kunye"])}</h2>'
                        f'<dl class="o-kunye-liste">{dl}</dl></section>\n')
        toc.insert(0, ("o-kunye", tt["r_kunye"]))
    son = []
    if r["kaynaklar"]:
        li = "".join(f'<li><a href="{S.e(k["url"])}" rel="noopener">{S.e(k["ad"])}</a><span class="o-alan">{S.e(alan(k["url"]))}</span></li>'
                     for k in r["kaynaklar"])
        son.append(f'<section class="o-ek" id="o-kaynaklar"><h2>{S.e(tt["r_kaynaklar"])}</h2><p class="not">{S.e(tt["r_kaynak_not"])}</p>'
                   f'<ol class="o-kaynak-liste">{li}</ol></section>\n')
        toc.append(("o-kaynaklar", tt["r_kaynaklar"]))
    uc = _ucretsiz_liste(dil, oid)
    if uc:
        son.append(f'<section class="o-ek" id="o-ucretsiz"><h2>{S.e(tt["r_ucretsiz"])}</h2><p class="not">{S.e(tt["r_ucretsiz_not"])}</p>{uc}</section>\n')
        toc.append(("o-ucretsiz", tt["r_ucretsiz"]))

    sira = _rehber_sirasi(dil)
    i = sira.index(oid)
    komsu = []
    for j, sinif, et in ((i - 1, "o-onceki", tt["r_onceki"]), (i + 1, "o-sonraki", tt["r_sonraki"])):
        if 0 <= j < len(sira):
            k = OYUN[sira[j]]
            komsu.append(f'<a class="{sinif} t-{k["id"]}" href="{S.u(rehber_yol(dil, k["id"]))}" rel="{"prev" if j < i else "next"}">'
                         f'<small>{S.e(et)}</small><b>{S.e(k["ad"])}</b></a>')
    komsu_html = f'<nav class="o-komsu" aria-label="{S.e(tt["r_tum"])}">{"".join(komsu)}</nav>\n' if komsu else ""

    okuma = S.e(tt["r_okuma"].format(n=rd["dk"]))
    ic = (f'<nav class="o-ic" aria-label="{S.e(tt["r_icindekiler"])}">'
          f'<button type="button" class="o-ic-ac js-only" aria-expanded="false" aria-controls="o-ic-liste">'
          f'<span class="o-ic-et">{S.e(tt["r_icindekiler"])}</span><span class="o-ic-simdi">{S.e(toc[0][1])}</span></button>'
          f'<h2 class="o-ic-bas">{S.e(tt["r_icindekiler"])}</h2>'
          f'<ol class="o-ic-liste" id="o-ic-liste">{"".join(f"<li><a href=\"#{a}\">{S.e(b)}</a></li>" for a, b in toc)}</ol>'
          f'<p class="o-ic-sure">{okuma} · <a href="#main">{S.e(tt["r_yukari"])}</a></p></nav>\n')
    govde = ('<div class="o-ilerleme js-only" aria-hidden="true"><span></span></div>\n' + hero
             + f'<div class="wrap o-govde">\n{ic}<article class="o-makale">\n{bas_ek_bolum}'
             + (ot.ayrac(t) if bas_ek_bolum and bolumler else "")
             + ot.ayrac(t).join(bolumler) + "".join(son) + komsu_html + '</article>\n</div>\n'
             + '<p class="gizli" id="o-duyuru" aria-live="polite"></p>\n')

    esler = {d: rehber_yol(d, oid) for d in S.DILLER if rehber_var(oid, d)}
    hedefler = {d: esler.get(d, SAYFA["rehberler"][d]) for d in S.DILLER}
    makale = {"@context": "https://schema.org", "@type": "Article", "headline": kisalt(rd["baslik"], 110),
              "description": kisalt(rd["ozet"], 300), "inLanguage": dil, "mainEntityOfPage": S.tam(yol),
              "author": {"@type": "Organization", "name": MARKA, "url": S.SITE + "/"},
              "publisher": {"@type": "Organization", "name": MARKA, "url": S.SITE + "/",
                            "logo": {"@type": "ImageObject", "url": S.SITE + "/favicon.svg"}},
              "about": {"@type": "VideoGame", "name": o["ad"], **({"url": o["resmi"]["url"]} if o["resmi"] else {})},
              "image": S.SITE + "/og.png"}
    if r["guncelleme"]:
        makale["datePublished"] = makale["dateModified"] = r["guncelleme"]
    if r["kaynaklar"]:
        makale["isBasedOn"] = [k["url"] for k in r["kaynaklar"]]
    ld = _ld(makale) + iz_ld
    if sss:
        ld += _ld({"@context": "https://schema.org", "@type": "FAQPage",
                   "mainEntity": [{"@type": "Question", "name": s, "acceptedAnswer": {"@type": "Answer", "text": c}} for s, c in sss]})
    return S.kabuk(dil, yol, rd["baslik"], kisalt(tt["r_desc"].format(oyun=o["ad"], ozet=rd["ozet"])), govde, esler=esler,
                   bolum="rehberler", tip="article", ek_bas=bas_ek(t) + ld, sayfa_turu="rehber", hedefler=hedefler,
                   ana_sinif=ot.siniflar(t))


# ---------------------------------------------------------------- oyun merkezi
def _panel(baslik: str, ic: str, link: tuple[str, str] | None = None) -> str:
    a = f'<a class="panel-link" href="{S.u(link[0])}">{S.e(link[1])}</a>' if link else ""
    return f'<section class="panel blok-panel"><div class="panel-bas"><h2>{S.e(baslik)}</h2>{a}</div>\n{ic}</section>\n'


def _kapak_kutu(dil: str, o: dict, *, buyuk: bool = False, ek: str = "") -> str:
    t = o["tema"]
    gor = S.oyun_gorsel(o["id"]) if hasattr(S, "oyun_gorsel") else None
    img = ""
    if gor:
        src = (gor.get("genis") or gor["url"]) if buyuk else gor["url"]
        img = (f'<img class="kg-img" src="{S.e(src)}" alt="{S.e(o["ad"])}" width="{gor["en"]}" height="{gor["boy"]}" '
               'loading="lazy" decoding="async" referrerpolicy="no-referrer" onerror="this.remove()">'
               f'<span class="kg-not">{S.e(T[dil]["gorsel_not"])}: {S.e(gor["kaynak"])}</span>')
    sinir = " kg-sinirli" if buyuk and gor and not gor.get("genis") else ""
    return f'<div class="kg o-kart-kg{sinir}">{ot.kapak(t, S.e(o["kisa"]), buyuk=buyuk, ek=ek)}{img}</div>'


def kayitlar(oid: str, dil: str, veri: list, soy: list, tak: list) -> tuple[list, list, list]:
    return ([x for x in veri if oyun_id(x["oyun"]) == oid],
            [s for s in soy if dil in s["diller"] and oyun_id(s["oyun"]) == oid],
            [c for c in tak if oyun_id(c["oyun"]) == oid])


def hub_bos(oid: str, veri: list, soy: list, tak: list) -> bool:
    """Oyun sayfasında hiçbir dilde içerik yoksa (haber, söylenti, tarih, rehber, kaynak) True döner.

    Boş sayfa arama motoruna kapatılır (noindex, site haritası dışı): yalnız kısa tanımdan oluşan yüzlerce sayfa
    Search Console'da "Tarandı, dizine eklenmedi" olarak birikiyor ve sitenin geri kalanını da aşağı çekiyordu.
    İlk kayıt geldiğinde sayfa kendiliğinden yeniden dizine açılır. Ölçüt dilden bağımsızdır ki hreflang eşleri tutarlı kalsın.
    """
    if oid == "gta-6" or oid in REHBER or any(k["hub"] == oid for k in KAYNAKLAR):
        return False
    return not any(oyun_id(x["oyun"]) == oid for x in list(veri) + list(soy) + list(tak))


def merkez_sayfasi(dil: str, oid: str, veri: list, soy: list, tak: list) -> str:
    global SIMDI_HUB
    SIMDI_HUB = oid
    try:
        return _merkez(dil, oid, veri, soy, tak)
    finally:
        SIMDI_HUB = None


def _merkez(dil: str, oid: str, veri: list, soy: list, tak: list) -> str:
    o, tt, m = OYUN[oid], T[dil], S.M[dil]
    t = o["tema"]
    yol = hub_yol(dil, oid)
    haber, soy_d, tak_d = kayitlar(oid, dil, veri, soy, tak)
    iz, iz_ld = _iz(dil, [(tt["nav"]["ana"], SAYFA["ana"][dil]), (tt["nav"]["oyunlar"], SAYFA["oyunlar"][dil]), (o["ad"], None)])

    rozet = []
    if o["platform"]:
        rozet.append(_rozet(S.e(", ".join(pl_ad(dil, p) for p in o["platform"])), tt["o_platform"]))
    if o["gelistirici"]:
        rozet.append(_rozet(S.e(o["gelistirici"]), tt["o_gelistirici"]))
    dugmeler = [S.takip_dugme(dil, o["ad"])]
    if rehber_var(oid, dil):
        dugmeler.append(f'<a class="dugme dugme-dolu" href="{S.u(rehber_yol(dil, oid))}">{S.e(tt["o_rehber"])}</a>')
    elif oid == "gta-6":
        dugmeler.append(f'<a class="dugme dugme-dolu" href="{S.u(SAYFA["gta"][dil])}">{S.e(tt["o_gta"])}</a>')
    if o["resmi"]:
        dugmeler.append(f'<a class="dugme" href="{S.e(o["resmi"]["url"])}" rel="noopener">{S.e(tt["o_resmi"])}</a>')
    sayim = S.e(tt["o_kayit"]).format(h=f"<b>{len(haber)}</b>", s=f"<b>{len(soy_d)}</b>", c=f"<b>{len(tak_d)}</b>")
    ek = (f'<p class="o-sayim">{sayim}</p>' + (f'<ul class="o-rozetler">{"".join(rozet)}</ul>' if rozet else "")
          + f'<div class="o-k-arac">{"".join(dugmeler)}</div>')
    ust = S.e(tt["o_yazi_bas"]) + (f' · {S.e(o["tur"][dil])}' if o["tur"][dil] else "")
    ozet = o["tanim"][dil] or tt["o_hub_desc"].format(oyun=o["ad"])
    hero = _kahraman(dil, o, iz, ust, o["ad"], "", ozet, ek)

    ana = []
    if rehber_var(oid, dil):
        rd = REHBER[oid]["diller"][dil]
        ana.append(f'<section class="o-tanitim">{_kapak_kutu(dil, o, buyuk=True, ek="t")}<div class="o-tanitim-metin">'
                   f'<h2>{S.e(rd["baslik"])}</h2><p>{S.e(rd["ozet"])}</p>'
                   f'<p><a class="dugme dugme-dolu" href="{S.u(rehber_yol(dil, oid))}">{S.e(tt["r_oku"])}</a></p></div></section>\n')
    elif oid == "gta-6":
        ana.append(f'<section class="o-tanitim">{_kapak_kutu(dil, o, buyuk=True, ek="t")}<div class="o-tanitim-metin">'
                   f'<h2>{S.e(tt["r_gta_ad"])}</h2><p>{S.e(tt["r_gta_tanim"])}</p>'
                   f'<p><a class="dugme dugme-dolu" href="{S.u(ESLER[1][dil])}">{S.e(tt["r_oku"])}</a></p></div></section>\n')
    h_ic = ('<ul class="satirlar">\n' + "".join(S.haber_satir(dil, x) for x in haber[:8]) + "</ul>\n") if haber else S.bos_kutu(tt["o_bos"])
    ana.append(_panel(tt["o_haberler"], h_ic, (SAYFA["haber"][dil], tt["tum_haberler"])))
    s_ic = ('<ul class="radar-liste">\n' + "".join(S.soylenti_kisa(dil, s, kapak=False) for s in soy_d[:6]) + "</ul>\n") if soy_d else S.bos_kutu(tt["o_bos"])
    ana.append(_panel(tt["o_soylentiler"], s_ic, (SAYFA["soylenti"][dil], tt["tum_soylenti"])))
    c_ic = ('<ul class="takvim-liste">\n' + "".join(S.cikis_satir(dil, c, oge=False, arac=False, kapak=False) for c in tak_d[:8]) + "</ul>\n") if tak_d else S.bos_kutu(tt["o_bos"])
    ana.append(_panel(tt["o_takvim"], c_ic, (SAYFA["takvim"][dil], tt["tum_takvim"])))

    bilgi = []
    if o["tur"][dil]:
        bilgi.append(f'<dt>{S.e(tt["o_tur"])}</dt><dd>{S.e(o["tur"][dil])}</dd>')
    if o["platform"]:
        bilgi.append(f'<dt>{S.e(tt["o_platform"])}</dt><dd>{S.e(", ".join(pl_ad(dil, p) for p in o["platform"]))}</dd>')
    if o["gelistirici"]:
        bilgi.append(f'<dt>{S.e(tt["o_gelistirici"])}</dt><dd>{S.e(o["gelistirici"])}</dd>')
    if o["resmi"]:
        bilgi.append(f'<dt>{S.e(tt["o_resmi"])}</dt><dd><a href="{S.e(o["resmi"]["url"])}" rel="noopener">{S.e(alan(o["resmi"]["url"]))}</a></dd>')
    yan = []
    if bilgi:
        yan.append(f'<section class="panel blok-panel"><div class="panel-bas"><h2>{S.e(o["ad"])}</h2></div>'
                   f'<dl class="o-hub-bilgi">{"".join(bilgi)}</dl></section>\n')
    uc = _ucretsiz_liste(dil, oid, genel=False)
    if uc:
        yan.append(f'<section class="o-ek"><h2>{S.e(tt["r_ucretsiz"])}</h2><p class="not">{S.e(tt["r_ucretsiz_not"])}</p>{uc}</section>\n')
    govde = (hero + '<div class="wrap o-merkez-govde">\n<div class="o-merkez-ana">\n' + "".join(ana) + '</div>\n'
             + '<aside class="o-merkez-yan">\n' + "".join(yan) + '</aside>\n</div>\n')
    esler = {d: hub_yol(d, oid) for d in S.DILLER}
    baslik = f'{o["ad"]} – {tt["o_yazi_bas"]}'
    return S.kabuk(dil, yol, baslik, kisalt(tt["o_hub_desc"].format(oyun=o["ad"])), govde, esler=esler, bolum="oyunlar",
                   ek_bas=bas_ek(t) + iz_ld, sayfa_turu="oyun", ana_sinif=ot.siniflar(t),
                   dizinle=not hub_bos(oid, veri, soy, tak))


# ---------------------------------------------------------------- dizinler
def skorlar(dil: str, veri: list, soy: list, tak: list) -> dict[str, int]:
    s: dict[str, int] = {}
    for x in veri:
        k = oyun_id(x["oyun"])
        if k:
            s[k] = s.get(k, 0) + 3
    for x in soy:
        k = oyun_id(x["oyun"])
        if k and dil in x["diller"]:
            s[k] = s.get(k, 0) + 2
    for x in tak:
        k = oyun_id(x["oyun"])
        if k:
            s[k] = s.get(k, 0) + 1
    return s


def _gruplar(dil: str, ogeler: list[dict]) -> list:
    tt = T[dil]
    var_g = {o["grup"] for o in ogeler}
    turler = [(g, tt["o_grup"][g]) for g, _ in TUR_GRUP + [("diger", ())] if g in var_g]
    var_p = {p for o in ogeler for p in o["platform"]}
    pl = [(S.slug(p), pl_ad(dil, p)) for p in PL_SIRA if p in var_p]
    return [("tur", tt["o_tur"], turler if len(turler) > 1 else []), ("platform", tt["o_platform"], pl if len(pl) > 1 else [])]


def _kart(dil: str, o: dict, href: str, ad: str, alt_baslik: str, ozet: str, alt: str, cta: str, ara: str, ek_sinif: str = "",
          kapak_ek: str = "", buyuk: bool = False, h: str = "h2", oge: bool = True) -> str:
    t = o["tema"]
    attr = ""
    if oge:
        attr = (f' data-oge data-tur="{o["grup"]}" data-platform="{" ".join(S.slug(p) for p in o["platform"])}"'
                f' data-oyun="{takip_anahtar(o["ad"])}" data-ara="{S.e(S.norm(ara))}"')
    return (f'<li class="o-kart{ek_sinif} t-{o["id"]} d-{t["duzen"]}"{attr}><a href="{S.u(href)}">'
            f'{_kapak_kutu(dil, o, buyuk=buyuk, ek=kapak_ek)}<div class="o-kart-metin">'
            f'<{h} class="o-kart-ad">{S.e(ad)}</{h}>' + (f'<p class="o-kart-tur">{S.e(alt_baslik)}</p>' if alt_baslik else "")
            + (f'<p class="o-kart-ozet">{S.e(ozet)}</p>' if ozet else "")
            + f'<p class="o-kart-alt">{alt}<span class="o-kart-cta">{S.e(cta)}</span></p></div></a></li>\n')


def _dizin_govde(dil: str, bolum: str, h1: str, giris: str, kartlar: str, ogeler: list, ad: str) -> str:
    tt = T[dil]
    if not kartlar:
        return S.sayfa_bas(dil, bolum, h1, S.e(giris)) + f'<div class="wrap">{S.bos_kutu(tt["o_bos"])}</div>\n'
    return (S.sayfa_bas(dil, bolum, h1, S.e(giris))
            + '<div class="wrap liste-duzen" data-suzgec-kok>\n<aside class="liste-yan">'
            + S.suzgec(dil, _gruplar(dil, ogeler), ad) + '</aside>\n<div class="liste-ana">\n'
            + f'<ul class="o-izgara">\n{kartlar}</ul>\n' + S.bos_kutu("", tt["bos_filtre"]) + '</div>\n</div>\n')


def oyunlar_dizini(dil: str, veri: list, soy: list, tak: list) -> str:
    tt = T[dil]
    skor = skorlar(dil, veri, soy, tak)
    sira = sorted(OYUNLAR, key=lambda o: (-skor.get(o["id"], 0), S.norm(o["ad"])))
    kartlar = []
    for o in sira:
        alt = "".join(f'<span class="cip">{S.e(pl_ad(dil, p))}</span>' for p in o["platform"][:4])
        if rehber_var(o["id"], dil):
            alt += f'<span class="cip cip-rehber">{S.e(tt["tur_ara"]["rehber"])}</span>'
        ara = " ".join([o["ad"], o["kisa"], *o["eslesme"], o["tur"][dil], o["gelistirici"], *o["platform"]])
        kartlar.append(_kart(dil, o, hub_yol(dil, o["id"]), o["ad"], o["tur"][dil], kisalt(o["tanim"][dil], 130), alt,
                             tt["r_hub"], ara, kapak_ek="k" + o["id"]))
    govde = _dizin_govde(dil, "oyunlar", tt["oyunlar_h1"], tt["oyunlar_giris"], "".join(kartlar), sira, "oyun")
    return S.kabuk(dil, SAYFA["oyunlar"][dil], tt["oyunlar_title"], tt["oyunlar_desc"], govde, esler=SAYFA["oyunlar"],
                   bolum="oyunlar", ek_bas=bas_ek(), sayfa_turu="oyunlar")


def rehberler_dizini(dil: str) -> str:
    tt = T[dil]
    kartlar, ogeler = [], []
    g = OYUN.get("gta-6")
    if g:
        kartlar.append(_kart(dil, g, ESLER[1][dil], tt["r_gta_ad"], g["tur"][dil], tt["r_gta_tanim"], "", tt["r_oku"],
                             " ".join([g["ad"], g["kisa"], *g["eslesme"], tt["r_gta_ad"], tt["r_gta_tanim"]]),
                             ek_sinif=" o-kart-gta", kapak_ek="kgta", buyuk=True))
        ogeler.append(g)
    for oid in _rehber_sirasi(dil):
        o, r = OYUN[oid], REHBER[oid]
        rd = r["diller"][dil]
        alt = f'<span class="cip">{S.e(tt["r_okuma"].format(n=rd["dk"]))}</span>'
        if r["guncelleme"]:
            alt += f'<span class="cip">{S.zaman_etiketi(dil, r["guncelleme"])}</span>'
        ara = " ".join([o["ad"], o["kisa"], *o["eslesme"], rd["baslik"], rd["ozet"], o["tur"][dil], *(b["baslik"] for b in rd["bolumler"])])
        kartlar.append(_kart(dil, o, rehber_yol(dil, oid), o["ad"], baslik_bol(rd["baslik"])[1] or rd["baslik"], kisalt(rd["ozet"], 150),
                             alt, tt["r_oku"], ara, kapak_ek="r" + oid))
        ogeler.append(o)
    govde = _dizin_govde(dil, "rehberler", tt["rehberler_h1"], tt["rehberler_giris"], "".join(kartlar), ogeler, "rehber")
    return S.kabuk(dil, SAYFA["rehberler"][dil], tt["rehberler_title"], tt["rehberler_desc"], govde, esler=SAYFA["rehberler"],
                   bolum="rehberler", ek_bas=bas_ek(), sayfa_turu="rehberler")


def populer_serit(dil: str, veri: list, soy: list, tak: list) -> str:
    """Ana sayfadaki 'Popüler oyunlar' şeridi (en çok kaydı olan 8 oyun)."""
    if not OYUNLAR:
        return ""
    tt = T[dil]
    skor = skorlar(dil, veri, soy, tak)
    sec = sorted(OYUNLAR, key=lambda o: (-skor.get(o["id"], 0), S.norm(o["ad"])))[:8]
    kartlar = "".join(_kart(dil, o, hub_yol(dil, o["id"]), o["ad"], o["tur"][dil], "", "", tt["r_hub"], "", kapak_ek="p" + o["id"],
                            h="h3", oge=False) for o in sec)
    return (f'<section class="blok populer" id="populer" aria-labelledby="b-populer"><div class="wrap">\n'
            f'<div class="blok-bas"><h2 id="b-populer">{S.e(tt["populer"])}</h2><p>{S.e(tt["populer_not"])}</p>'
            f'<a class="panel-link" href="{S.u(SAYFA["oyunlar"][dil])}">{S.e(tt["o_tum"])}</a></div>\n'
            f'<ul class="o-izgara o-populer">\n{kartlar}</ul>\n</div></section>\n')


# ---------------------------------------------------------------- arama dizini, tema dosyası, yazma
def ara_ekleri(dil: str) -> list[tuple]:
    """(başlık, adres, tür, oyun, gün, ek) — site_derle.ara_dizini ekler."""
    d = []
    for o in OYUNLAR:
        d.append((o["ad"], S.u(hub_yol(dil, o["id"])), "oyun", "", "",
                  " ".join([o["kisa"], *o["eslesme"], o["tur"][dil], o["gelistirici"]])))
    for oid in _rehber_sirasi(dil):
        o, r = OYUN[oid], REHBER[oid]
        rd, adres = r["diller"][dil], S.u(rehber_yol(dil, oid))
        d.append((rd["baslik"], adres, "rehber", o["ad"], r["guncelleme"], rd["ozet"]))
        for b in rd["bolumler"]:
            d.append((duz(b["baslik"]), f"{adres}#{b['id']}", "bolum", o["ad"], "", rd["baslik"]))
    return d


def tema_yaz() -> int:
    """oyun-tema.css (temel + her oyunun paleti); karşıtlık sorunları uyarı olur."""
    if not OYUNLAR:
        return 0
    css, sorunlar = ot.css_uret(OYUNLAR)
    for w in sorunlar:
        S.uyar("tema karşıtlığı: " + w)
    SURUM["css"] = hashlib.sha1(css.encode("utf-8")).hexdigest()[:8]
    return int(S.sd.yaz(S.KOK / "oyun-tema.css", css))


HARITA_DISI: set[str] = set()   # bu derlemede yazılan ama site haritasına girmeyen (noindex) oyun sayfaları


def sayfalari_yaz(dil: str, veri: list, soy: list, tak: list) -> int:
    degisen = S.sayfa_yaz(SAYFA["oyunlar"][dil], oyunlar_dizini(dil, veri, soy, tak), esler=SAYFA["oyunlar"])
    degisen += S.sayfa_yaz(SAYFA["rehberler"][dil], rehberler_dizini(dil), esler=SAYFA["rehberler"])
    for o in OYUNLAR:
        esler = {d: hub_yol(d, o["id"]) for d in S.DILLER}
        bos = hub_bos(o["id"], veri, soy, tak)
        (HARITA_DISI.add if bos else HARITA_DISI.discard)(esler[dil])
        degisen += S.sayfa_yaz(esler[dil], merkez_sayfasi(dil, o["id"], veri, soy, tak), esler=esler, harita=not bos)
    for oid in _rehber_sirasi(dil):
        esler = {d: rehber_yol(d, oid) for d in S.DILLER if rehber_var(oid, d)}
        degisen += S.sayfa_yaz(esler[dil], rehber_sayfasi(dil, oid), esler=esler)
    return degisen


def artiklari_temizle(uretilen: dict) -> int:
    """Veriden çıkarılmış oyunun/rehberin eski sayfasını kaldırır (bu derlemede yazılmayan, bizim ürettiğimiz sayfa).

    Veri hiç okunamadıysa (oyunlar.json ya da rehber klasörü yok/boş) dokunmaz: kazara silinen veri sayfaları götürmesin.
    """
    klasorler = []
    if OYUNLAR:
        klasorler += list(OYUN_KLASOR.values())
        if REHBER and _rehber_klasoru().is_dir():
            klasorler += list(REHBER_KLASOR.values())
    silinen = 0
    for k in klasorler:
        p = S.KOK / k
        for f in sorted(p.glob("*.html")) if p.is_dir() else []:
            yol = f"{k}/{f.name}"
            if f.name == "index.html" or yol in uretilen or yol in HARITA_DISI:
                continue
            try:
                if 'class="o-sayfa t-' not in f.read_text(encoding="utf-8", errors="ignore"):
                    continue
                f.unlink()
            except OSError as h:
                S.uyar(f"{yol} kaldırılamadı ({h}).")
                continue
            S.uyar(f"{yol}: verisi kalmadığı için kaldırıldı.")
            silinen += 1
    return silinen
