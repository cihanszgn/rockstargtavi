#!/usr/bin/env python3
"""Haber videoları: manifest okuma, site için kart/oynatıcı HTML'i, VideoObject JSON-LD ve video site haritası girdisi.

Manifest `data/videolar.json` (tools/video_uret.py yazar; bu dosya yalnız okur ve yayın bağlantısı alanlarını doldurur):
  {"surum": 1, "taban": "https://medya.ctrl-agame.com/v/",
   "videolar": {"<haber id>": {"<dil>": {"anahtar", "sure", "mp4_1080", "mp4_720", "mp4_540", "kapak", "vtt",
                                          "uretildi", "youtube", "instagram"}}}}
Dosya yoksa, bozuksa ya da haber/dil için kayıt yoksa her şey video yokmuş gibi çalışır (çıktı eskisiyle aynı).
Yalnız standart kütüphane.
"""
from __future__ import annotations

import html
import json
import pathlib
import re

KOK = pathlib.Path(__file__).resolve().parent.parent
MANIFEST_YOLU = KOK / "data" / "videolar.json"
DOSYA_AD = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")

# Etiketler video varken sayfaya yazılır; video yokken hiçbir yere girmez (eski sayfalar değişmez).
METIN = {
    "tr": {"oynat": "Videoyu oynat", "durdur": "Videoyu durdur", "ses_ac": "Sesi aç", "ses_kapat": "Sesi kapat",
           "altyazi": "Altyazı", "baslik": "Haberin videosu", "youtube": "YouTube'da izle", "instagram": "Instagram'da izle",
           "sure": "Video süresi"},
    "en": {"oynat": "Play video", "durdur": "Pause video", "ses_ac": "Turn sound on", "ses_kapat": "Turn sound off",
           "altyazi": "Captions", "baslik": "News video", "youtube": "Watch on YouTube", "instagram": "Watch on Instagram",
           "sure": "Video length"},
    "fr": {"oynat": "Lire la vidéo", "durdur": "Mettre la vidéo en pause", "ses_ac": "Activer le son", "ses_kapat": "Couper le son",
           "altyazi": "Sous-titres", "baslik": "La vidéo de l'actu", "youtube": "Regarder sur YouTube",
           "instagram": "Voir sur Instagram", "sure": "Durée de la vidéo"},
    "es": {"oynat": "Reproducir el vídeo", "durdur": "Pausar el vídeo", "ses_ac": "Activar el sonido", "ses_kapat": "Silenciar",
           "altyazi": "Subtítulos", "baslik": "Vídeo de la noticia", "youtube": "Ver en YouTube", "instagram": "Ver en Instagram",
           "sure": "Duración del vídeo"},
}
IK_OYNAT = '<svg class="vd-ik vd-oynat" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M8 5.5v13l11-6.5z" fill="currentColor"/></svg>'
IK_DURDUR = '<svg class="vd-ik vd-durdur" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M7 5h3.6v14H7zM13.4 5H17v14h-3.4z" fill="currentColor"/></svg>'
IK_SES = ('<svg class="vd-ik vd-ses-ac" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M4 9.5h3.5L12 6v12l-4.5-3.5H4z" fill="currentColor"/>'
          '<path d="M15.5 9a4.2 4.2 0 0 1 0 6M17.8 6.8a7.4 7.4 0 0 1 0 10.4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>')
IK_SESSIZ = ('<svg class="vd-ik vd-ses-kapali" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M4 9.5h3.5L12 6v12l-4.5-3.5H4z" fill="currentColor"/>'
             '<path d="m15.5 9.5 5 5m0-5-5 5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>')


def e(s) -> str:
    return html.escape(str(s), quote=True)


# ---------------------------------------------------------------- manifest
def yukle(yol: pathlib.Path | None = None) -> dict:
    """Manifesti okur. Yok, bozuk ya da şeması yanlışsa boş manifest döner (site videosuz derlenir)."""
    yol = yol or MANIFEST_YOLU
    try:
        ham = json.loads(yol.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    taban = ham.get("taban") if isinstance(ham, dict) else None
    videolar = ham.get("videolar") if isinstance(ham, dict) else None
    if not (isinstance(taban, str) and taban.startswith("https://") and isinstance(videolar, dict)):
        return {}
    return ham


def _dosya(v: dict, alan: str) -> str | None:
    ad = v.get(alan)
    return ad if isinstance(ad, str) and DOSYA_AD.fullmatch(ad) and ".." not in ad else None


def bul(manifest: dict, haber_id: str, dil: str) -> dict | None:
    """Haber/dil için oynatılabilir video bilgisi (tam adresleriyle) ya da None.
    Kart ve sayfa için 540 ve 720 sürümleri ile kapak şart; eksikse video yok sayılır."""
    if not manifest:
        return None
    v = ((manifest.get("videolar") or {}).get(haber_id) or {}).get(dil)
    if not isinstance(v, dict):
        return None
    # İlk videolar Cio'nun onayıyla yayımlanır: onaylanmamış video üretilip sunucuda durur,
    # ama sitede ve sosyal paylaşımda yok sayılır. Onay: `py tools/video_site.py onayla <haber id>`.
    if manifest.get("onay_gerekli", True) and v.get("onay") is not True:
        return None
    taban = manifest["taban"] if manifest["taban"].endswith("/") else manifest["taban"] + "/"
    ad = {a: _dosya(v, a) for a in ("mp4_540", "mp4_720", "mp4_1080", "kapak", "vtt")}
    sure = v.get("sure")
    if not (ad["mp4_540"] and ad["mp4_720"] and ad["kapak"]) or isinstance(sure, bool) or not isinstance(sure, (int, float)) or sure <= 0:
        return None
    cikti = {a: taban + n for a, n in ad.items() if n}
    cikti["sure"] = float(sure)
    cikti["uretildi"] = v["uretildi"] if isinstance(v.get("uretildi"), str) else ""
    for p in ("youtube", "instagram"):
        cikti[p] = v[p] if isinstance(v.get(p), str) and v[p].startswith("https://") else ""
    return cikti


def baglanti_yaz(yol: pathlib.Path, haber_id: str, dil: str, alan: str, url: str) -> bool:
    """Yayın sonrası youtube/instagram bağlantısını manifeste yazar; başka hiçbir alana dokunmaz.
    Kayıt yoksa yazmaz (False). Aynı değer varsa dosyayı yeniden yazmaz."""
    if alan not in ("youtube", "instagram") or not url.startswith("https://"):
        return False
    try:
        ham = json.loads(yol.read_text(encoding="utf-8"))
        v = ham["videolar"][haber_id][dil]
    except (OSError, ValueError, KeyError, TypeError):
        return False
    if v.get(alan) == url:
        return True
    v[alan] = url
    yol.write_text(json.dumps(ham, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return True


def onay_yaz(yol: pathlib.Path, haber_id: str, dil: str, onay: bool = True) -> bool:
    """Videoyu yayına açar (ya da geri çeker); başka hiçbir alana dokunmaz. Kayıt yoksa False."""
    try:
        ham = json.loads(yol.read_text(encoding="utf-8"))
        v = ham["videolar"][haber_id][dil]
    except (OSError, ValueError, KeyError, TypeError):
        return False
    if v.get("onay") is not onay:
        v["onay"] = onay
        yol.write_text(json.dumps(ham, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return True


def onay_bekleyenler(manifest: dict) -> list[tuple[str, str, str]]:
    """(haber id, dil, 540 sürümünün adresi): üretilmiş ama henüz onaylanmamış videolar."""
    taban = (manifest.get("taban") or "").rstrip("/") + "/"
    return [(hid, dil, taban + str(v.get("mp4_540") or ""))
            for hid, diller in sorted((manifest.get("videolar") or {}).items())
            for dil, v in sorted((diller or {}).items())
            if isinstance(v, dict) and v.get("onay") is not True]


# ---------------------------------------------------------------- HTML
def sure_yaz(sn: float) -> str:
    t = max(0, int(round(sn)))
    return f"{t // 60}:{t % 60:02d}"


def iso_sure(sn: float) -> str:
    return f"PT{max(1, int(round(sn)))}S"


def kart_nitelik(v: dict) -> str:
    """Haber kartı kapağına (.kg) eklenecek nitelikler; video adresi yalnız veri, bayt çekilmez."""
    return f' data-video="{e(v["mp4_540"])}" data-kapak="{e(v["kapak"])}" data-sure="{int(round(v["sure"]))}"'


def kart_arac(dil: str, v: dict) -> str:
    """Süre rozeti + oynat/durdur tuşu (yalnız JavaScript açıkken görünür)."""
    m = METIN[dil]
    return (f'<span class="kg-vid-ui js-only"><span class="kg-sure" title="{e(m["sure"])}">{sure_yaz(v["sure"])}</span>'
            f'<button type="button" class="tus kg-oynat" data-video-dugme aria-label="{e(m["oynat"])}" '
            f'data-etiket-oynat="{e(m["oynat"])}" data-etiket-durdur="{e(m["durdur"])}">{IK_OYNAT}{IK_DURDUR}</button></span>')


def sayfa_oynatici(dil: str, v: dict, baslik: str) -> str:
    """Haber sayfası 9:16 oynatıcı. JavaScript yokken yerel denetimler (controls) çalışır;
    JavaScript açılınca onları kaldırıp klavye tuşu düğmeleri takar."""
    m = METIN[dil]
    iz = (f'<track kind="captions" src="{e(v["vtt"])}" srclang="{dil}" label="{e(m["altyazi"])}" default>' if v.get("vtt") else "")
    cc = (f'<button type="button" class="tus vp-tus" data-video-cc aria-pressed="true" aria-label="{e(m["altyazi"])}">CC</button>'
          if v.get("vtt") else "")
    linkler = "".join(f'<a class="dugme" href="{e(v[p])}" rel="noopener">{e(m[p])}</a>' for p in ("youtube", "instagram") if v.get(p))
    return (f'<section class="kutu hd-video" aria-labelledby="b-video"><h2 id="b-video">{e(m["baslik"])}</h2>\n'
            f'<div class="vp" data-video="{e(v["mp4_720"])}" data-kapak="{e(v["kapak"])}" data-sure="{int(round(v["sure"]))}">'
            f'<video class="vp-v" poster="{e(v["kapak"])}" preload="none" muted loop playsinline controls width="720" height="1280" '
            f'aria-label="{e(baslik)}"><source src="{e(v["mp4_720"])}" type="video/mp4">{iz}</video>'
            f'<div class="vp-arac js-only">'
            f'<button type="button" class="tus vp-tus" data-video-dugme aria-label="{e(m["oynat"])}" '
            f'data-etiket-oynat="{e(m["oynat"])}" data-etiket-durdur="{e(m["durdur"])}">{IK_OYNAT}{IK_DURDUR}</button>'
            f'<button type="button" class="tus vp-tus" data-video-ses aria-label="{e(m["ses_ac"])}" '
            f'data-etiket-ac="{e(m["ses_ac"])}" data-etiket-kapat="{e(m["ses_kapat"])}">{IK_SES}{IK_SESSIZ}</button>{cc}'
            f'</div></div>'
            + (f'\n<div class="paylas vp-link">{linkler}</div>' if linkler else "") + '</section>\n')


# ---------------------------------------------------------------- arama motoru
def video_ld(v: dict, *, ad: str, aciklama: str, tarih: str, dil: str) -> dict:
    return {"@context": "https://schema.org", "@type": "VideoObject", "name": ad[:100], "description": aciklama[:2000],
            "thumbnailUrl": [v["kapak"]], "uploadDate": v["uretildi"] or tarih, "duration": iso_sure(v["sure"]),
            "contentUrl": v["mp4_720"], "inLanguage": dil}


def ld_etiket(ld: dict) -> str:
    return '<script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False).replace("</", "<\\/") + "</script>\n"


def harita_girdisi(v: dict, *, ad: str, aciklama: str, tarih: str) -> str:
    """Site haritasındaki <url> içine konacak <video:video> bloğu."""
    return ("<video:video>"
            f"<video:thumbnail_loc>{e(v['kapak'])}</video:thumbnail_loc>"
            f"<video:title>{e(ad[:100])}</video:title>"
            f"<video:description>{e(aciklama[:2000])}</video:description>"
            f"<video:content_loc>{e(v['mp4_720'])}</video:content_loc>"
            f"<video:duration>{max(1, int(round(v['sure'])))}</video:duration>"
            f"<video:publication_date>{e(v['uretildi'] or tarih)}</video:publication_date>"
            "</video:video>")


def bugun_uretilen(manifest: dict, gun: str) -> int:
    """Manifestte `uretildi` tarihi verilen güne (YYYY-MM-DD) ait video sayısı; günlük üretim sınırı için."""
    n = 0
    for diller in (manifest.get("videolar") or {}).values():
        for v in (diller or {}).values():
            if isinstance(v, dict) and str(v.get("uretildi") or "")[:10] == gun:
                n += 1
    return n


if __name__ == "__main__":
    import sys
    from datetime import datetime, timezone
    if sys.argv[1:2] == ["bugun"]:  # workflow: bugün kaç video üretildi
        print(bugun_uretilen(yukle(), datetime.now(timezone.utc).strftime("%Y-%m-%d")))
    elif sys.argv[1:2] == ["onay-bekleyenler"]:
        for hid, dil, adres in onay_bekleyenler(yukle()):
            print(hid, dil, adres)
    elif sys.argv[1:2] in (["onayla"], ["geri-cek"]) and len(sys.argv) >= 3:
        dil = sys.argv[3] if len(sys.argv) > 3 else "tr"
        tamam = onay_yaz(MANIFEST_YOLU, sys.argv[2], dil, sys.argv[1] == "onayla")
        print("tamam" if tamam else "kayıt bulunamadı")
        sys.exit(0 if tamam else 1)
