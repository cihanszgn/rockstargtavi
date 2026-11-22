"""Ağsız sosyal içerik kuyruğu. Kaynak verileri değiştirmez, model çağırmaz."""
from __future__ import annotations

import copy
import hashlib
import json
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import oyun_adi
from site_metin import SAYFA, REHBER_KLASOR

DILLER = ("tr", "en", "fr", "es", "de", "nl", "zh")
TURLER = ("haber", "takvim", "firsat", "ucretsiz", "rehber", "arsiv")
SABLON = {
    "tr": {"takvim": "Çıkış takvimi", "firsat": "Günün fırsatı", "ucretsiz": "Ücretsiz oyun", "rehber": "Rehber", "arsiv": "Arşivden",
           "kalan": "{oyun}: çıkışa {gun} gün", "bugun": "{oyun}: çıkış günü",
           "tarih": "Planlanan çıkış: {tarih}. Platformlar: {platform}.",
           "indirim": "{oyun}: %{oran} indirim", "fiyat": "{magaza}: {fiyat} USD (liste fiyatı {normal} USD). Fiyat ve stok değişebilir; mağazada kontrol edin.",
           "bedava": "{oyun} şu an ücretsiz", "kampanya": "Epic Games Store kampanyası {bitis} tarihinde sona eriyor (UTC).",
           "bedava_anlik": "{magaza} verisinde ücretsiz görünüyor. Güncel fiyatı mağazada kontrol edin.",
           "rehber_baslik": "{oyun}: rehbere göz atın", "arsiv_not": "Arşivden · {tarih}. Bu içerik yayımlandığı tarihteki durumu anlatır.",
           "gorsel": "Görsel", "etiket": "#Oyun #PCGaming #CTRLA_GAME"},
    "en": {"takvim": "Release calendar", "firsat": "Deal of the day", "ucretsiz": "Free game", "rehber": "Guide", "arsiv": "From the archive",
           "kalan": "{oyun}: {gun} days until release", "bugun": "{oyun}: release day",
           "tarih": "Scheduled release: {tarih}. Platforms: {platform}.",
           "indirim": "{oyun}: {oran}% off", "fiyat": "{magaza}: {fiyat} USD (list price {normal} USD). Price and availability may change; check the store.",
           "bedava": "{oyun} is currently free", "kampanya": "The Epic Games Store promotion ends on {bitis} (UTC).",
           "bedava_anlik": "Listed as free by {magaza}. Check the current price in the store.",
           "rehber_baslik": "{oyun}: explore the guide", "arsiv_not": "From the archive · {tarih}. This article describes the situation at publication.",
           "gorsel": "Image", "etiket": "#Gaming #PCGaming #CTRLA_GAME"},
    "de": {"takvim": "Release-Kalender", "firsat": "Angebot des Tages", "ucretsiz": "Gratis-Spiel", "rehber": "Guide", "arsiv": "Aus dem Archiv",
           "kalan": "{oyun}: noch {gun} Tage bis zum Release", "bugun": "{oyun}: Release-Tag",
           "tarih": "Geplanter Release: {tarih}. Plattformen: {platform}.",
           "indirim": "{oyun}: {oran} % Rabatt", "fiyat": "{magaza}: {fiyat} USD (Listenpreis {normal} USD). Preis und Verfügbarkeit können sich ändern; bitte im Shop prüfen.",
           "bedava": "{oyun} ist derzeit kostenlos", "kampanya": "Die Aktion im Epic Games Store endet am {bitis} (UTC).",
           "bedava_anlik": "Laut {magaza} derzeit kostenlos. Aktuellen Preis im Shop prüfen.",
           "rehber_baslik": "{oyun}: zum Guide", "arsiv_not": "Aus dem Archiv · {tarih}. Dieser Beitrag beschreibt den Stand zum Zeitpunkt der Veröffentlichung.",
           "gorsel": "Bild", "etiket": "#Gaming #PCGaming #CTRLA_GAME"},
    "nl": {"takvim": "Releasekalender", "firsat": "Deal van de dag", "ucretsiz": "Gratis game", "rehber": "Gids", "arsiv": "Uit het archief",
           "kalan": "{oyun}: nog {gun} dagen tot de release", "bugun": "{oyun}: releasedag",
           "tarih": "Geplande release: {tarih}. Platforms: {platform}.",
           "indirim": "{oyun}: {oran}% korting", "fiyat": "{magaza}: {fiyat} USD (adviesprijs {normal} USD). Prijs en beschikbaarheid kunnen wijzigen; controleer de winkel.",
           "bedava": "{oyun} is nu gratis", "kampanya": "De actie in de Epic Games Store eindigt op {bitis} (UTC).",
           "bedava_anlik": "Volgens {magaza} nu gratis. Controleer de actuele prijs in de winkel.",
           "rehber_baslik": "{oyun}: bekijk de gids", "arsiv_not": "Uit het archief · {tarih}. Dit artikel beschrijft de situatie op het moment van publicatie.",
           "gorsel": "Beeld", "etiket": "#Gaming #PCGaming #CTRLA_GAME"},
    "zh": {"takvim": "发售日历", "firsat": "今日特惠", "ucretsiz": "免费游戏", "rehber": "攻略", "arsiv": "往期回顾",
           "kalan": "{oyun}：距发售还有 {gun} 天", "bugun": "{oyun}：今日发售",
           "tarih": "计划发售日期：{tarih}。平台：{platform}。",
           "indirim": "{oyun}：优惠 {oran}%", "fiyat": "{magaza}：{fiyat} 美元（原价 {normal} 美元）。价格和库存可能变动，请以商店为准。",
           "bedava": "{oyun} 现在免费", "kampanya": "Epic Games Store 活动将于 {bitis}（UTC）结束。",
           "bedava_anlik": "{magaza} 数据显示目前免费。请在商店确认当前价格。",
           "rehber_baslik": "{oyun}：查看攻略", "arsiv_not": "往期回顾 · {tarih}。本文描述的是发布时的情况。",
           "gorsel": "图片", "etiket": "#游戏 #PCGaming #CTRLA_GAME"},
    "fr": {"takvim": "Calendrier des sorties", "firsat": "Offre du jour", "ucretsiz": "Jeu gratuit", "rehber": "Guide", "arsiv": "Dans les archives",
           "kalan": "{oyun} : sortie dans {gun} jours", "bugun": "{oyun} : jour de sortie",
           "tarih": "Sortie prévue : {tarih}. Plateformes : {platform}.",
           "indirim": "{oyun} : réduction de {oran} %", "fiyat": "{magaza} : {fiyat} USD (prix catalogue {normal} USD). Prix et disponibilité variables ; vérifiez en boutique.",
           "bedava": "{oyun} est gratuit en ce moment", "kampanya": "La promotion Epic Games Store se termine le {bitis} (UTC).",
           "bedava_anlik": "Gratuit selon les données de {magaza}. Vérifiez le prix actuel en boutique.",
           "rehber_baslik": "{oyun} : découvrez le guide", "arsiv_not": "Dans les archives · {tarih}. Cet article décrit la situation à sa publication.",
           "gorsel": "Image", "etiket": "#JeuxVideo #PCGaming #CTRLA_GAME"},
    "es": {"takvim": "Calendario de lanzamientos", "firsat": "Oferta del día", "ucretsiz": "Juego gratis", "rehber": "Guía", "arsiv": "Del archivo",
           "kalan": "{oyun}: faltan {gun} días", "bugun": "{oyun}: día de lanzamiento",
           "tarih": "Lanzamiento previsto: {tarih}. Plataformas: {platform}.",
           "indirim": "{oyun}: {oran}% de descuento", "fiyat": "{magaza}: {fiyat} USD (precio de lista {normal} USD). Precio y disponibilidad sujetos a cambios; compruébalos en la tienda.",
           "bedava": "{oyun} está gratis ahora", "kampanya": "La promoción de Epic Games Store termina el {bitis} (UTC).",
           "bedava_anlik": "Gratis según los datos de {magaza}. Comprueba el precio actual en la tienda.",
           "rehber_baslik": "{oyun}: consulta la guía", "arsiv_not": "Del archivo · {tarih}. Este artículo describe la situación en su fecha de publicación.",
           "gorsel": "Imagen", "etiket": "#Videojuegos #PCGaming #CTRLA_GAME"},
}


def oku(kok: Path, ad: str, yedek):
    yol = kok / "data" / ad
    return json.loads(yol.read_text(encoding="utf-8")) if yol.exists() else yedek


def zaman(s) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except (ValueError, TypeError):
        return None


def norm(s):
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower())


def kimlik(tur, deger):
    return tur + "-" + hashlib.sha256(str(deger).encode("utf-8")).hexdigest()[:20]


def arsive_uygun(x):
    # Haber türü tek başına kalıcılık kanıtı değil. Yalnız yama/çıkış kayıtları;
    # sezon, etkinlik, kampanya ve söylenti içerenleri temkinli biçimde dışla.
    if x.get("tur") not in ("guncelleme", "cikis"):
        return False
    metin = json.dumps(x, ensure_ascii=False)
    metin = unicodedata.normalize("NFKD", metin).encode("ascii", "ignore").decode().lower()
    return not re.search(r"rumou?r|leak|soylenti|sizinti|etkinlik|event|campaign|kampanya|promotion|limited.time|sezon|season|free.week|ucretsiz", metin)


def adaylar(veri, kok: Path, ayar, bugun: date, simdi: datetime):
    """Öncelik sıralı, haber kartı/yayın şemasına uyarlanmış anlık adaylar."""
    sonuc = []
    pencere = ayar.get("en_eski_gun", 3)
    haberler = sorted(veri, key=lambda x: (x["tarih"], x["id"]), reverse=True)
    takma = oyun_adi.takma_adlar(kok)

    def oyunlu(x):
        """Sosyal gönderide başlık tek başına okunur: oyun adı geçmiyorsa başlığın önüne eklenir (site verisi değişmez)."""
        y = copy.deepcopy(x)
        for t in y.get("diller", {}).values():
            if isinstance(t, dict) and t.get("baslik"):
                t["baslik"] = oyun_adi.oyunlu_baslik(t["baslik"], x.get("oyun") or "", takma)
        return y

    for x in haberler:
        if 0 <= (bugun - date.fromisoformat(x["tarih"])).days <= pencere:
            sonuc.append({**oyunlu(x), "sosyal_tur": "haber"})

    gorseller = oku(kok, "oyun_gorselleri.json", {})
    oyunlar = oku(kok, "oyunlar.json", [])

    def gorsel(oid, ad):
        for bolum in ("takvim", "oyun"):
            if oid in gorseller.get(bolum, {}):
                return gorseller[bolum][oid]
        for o in oyunlar:
            if norm(ad) in {norm(o.get("ad")), *map(norm, o.get("eslesme", []))}:
                return gorseller.get("oyun", {}).get(o["id"])
        return None

    def ekle(oid, tur, oyun, kaynaklar, metinler, sayfalar, *, anahtar=None, resim=None):
        sonuc.append({"id": oid, "sosyal_tur": tur, "sosyal_anahtar": anahtar or oid,
                      "oyun": oyun, "tarih": bugun.isoformat(), "tur": "haber", "kaynaklar": kaynaklar,
                      "sayfalar": sayfalar, "gorsel": resim,
                      "diller": {d: {"baslik": b, "ozet": o, "metin": o, "etiketler": SABLON[d]["etiket"].split()}
                                 for d, (b, o) in metinler.items()}})

    for x in oku(kok, "takvim.json", []):
        if not x.get("tarih") or not x.get("kesin"):
            continue
        gun = (date.fromisoformat(x["tarih"]) - bugun).days
        if gun not in (30, 14, 7, 3, 1, 0) and not (x.get("id") == GTA_ID and 0 <= gun <= GTA_ONCELIK_GUN):
            continue
        oid = f"takvim-{x['id']}-{x['tarih']}-{gun}"
        ekle(oid, "takvim", x["oyun"], [x["kaynak"]],
             {d: (SABLON[d]["bugun" if gun == 0 else "kalan"].format(oyun=x["oyun"], gun=gun),
                  SABLON[d]["tarih"].format(tarih=x["tarih"], platform=", ".join(x.get("platform", [])))) for d in DILLER},
             SAYFA["takvim"], resim=gorsel(x["id"], x["oyun"]))

    def guncel(v):
        dt = zaman(v.get("guncel"))
        # CheapShark bitiş tarihi sağlamıyor: yalnız son 24 saatlik anlık liste.
        return dt is not None and timedelta(0) <= simdi - dt < timedelta(hours=24)

    indirim = oku(kok, "indirimler.json", {})
    magazalar = {str(m["id"]): m["ad"] for m in indirim.get("magazalar", [])}
    if guncel(indirim):
        for f in sorted(indirim.get("firsatlar", []), key=lambda x: float(x.get("savings", 0)), reverse=True):
            bit = zaman(f.get("bitis"))
            if (bit and bit <= simdi) or float(f.get("salePrice", -1)) <= 0 or float(f.get("savings", 0)) <= 0:
                continue
            mag = magazalar.get(str(f.get("storeID")), "CheapShark")
            ekle(kimlik("firsat", f["dealID"]), "firsat", f["title"], [{"ad": mag, "url": "https://www.cheapshark.com"}],
                 {d: (SABLON[d]["indirim"].format(oyun=f["title"], oran=f"{float(f['savings']):.0f}"),
                      SABLON[d]["fiyat"].format(magaza=mag, fiyat=f"{float(f['salePrice']):.2f}", normal=f"{float(f['normalPrice']):.2f}")) for d in DILLER},
                 SAYFA["indirim"], resim=gorsel(f.get("gameID"), f["title"]))

    bedava = oku(kok, "ucretsiz.json", {})
    epic_adlari = set()
    for f in bedava.get("epic", []):
        bas, bit = zaman(f.get("baslangic")), zaman(f.get("bitis"))
        if not bas or not bit or not bas <= simdi < bit:
            continue
        epic_adlari.add(norm(f["baslik"]))
        ekle(kimlik("ucretsiz", f"epic:{f.get('slug') or f['baslik']}:{bas.isoformat()}:{bit.isoformat()}"),
             "ucretsiz", f["baslik"], [{"ad": "Epic Games Store", "url": "https://store.epicgames.com/free-games"}],
             {d: (SABLON[d]["bedava"].format(oyun=f["baslik"]), SABLON[d]["kampanya"].format(bitis=bit.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M"))) for d in DILLER},
             SAYFA["ucretsiz"], resim=gorsel(f.get("slug"), f["baslik"]))
    if guncel(bedava):
        for f in bedava.get("cheapshark", []):
            bit = zaman(f.get("bitis"))
            if norm(f["title"]) in epic_adlari or float(f.get("salePrice", -1)) != 0 or (bit and bit <= simdi):
                continue
            mag = magazalar.get(str(f.get("storeID")), "CheapShark")
            ekle(kimlik("ucretsiz", f["dealID"]), "ucretsiz", f["title"], [{"ad": mag, "url": "https://www.cheapshark.com"}],
                 {d: (SABLON[d]["bedava"].format(oyun=f["title"]), SABLON[d]["bedava_anlik"].format(magaza=mag)) for d in DILLER},
                 SAYFA["ucretsiz"], resim=gorsel(f.get("gameID"), f["title"]))

    oyun_ad = {o["id"]: o["ad"] for o in oyunlar}
    for yol in sorted((kok / "data" / "rehber").glob("*.json")):
        r = json.loads(yol.read_text(encoding="utf-8"))
        oid = r.get("oyun", yol.stem)
        if oid not in oyun_ad:
            continue
        ad = oyun_ad[oid]
        dl = {d: (SABLON[d]["rehber_baslik"].format(oyun=ad), t["ozet"]) for d, t in r.get("diller", {}).items()
              if d in DILLER and t.get("ozet") and t.get("baslik") and t.get("bolumler")}
        ekle("rehber-" + oid, "rehber", ad, r.get("kaynaklar") or [{"ad": "CTRL+A GAME", "url": "https://ctrl-agame.com"}],
             dl, {d: f"{REHBER_KLASOR[d]}/{oid}.html" for d in dl},
             anahtar=f"rehber-{oid}-{bugun.isoformat()}", resim=gorsel(oid, ad))

    for x in sorted(haberler, key=lambda x: (x.get("otomasyon", {}).get("hype", 0), x["tarih"], x["id"]), reverse=True):
        if (bugun - date.fromisoformat(x["tarih"])).days <= pencere or not arsive_uygun(x):
            continue
        a = copy.deepcopy(x)
        a["sosyal_tur"] = "arsiv"
        a["gorsel"] = gorsel(None, x.get("oyun", ""))
        for d, t in a["diller"].items():
            t["baslik"] = f"{SABLON[d]['arsiv']}: {t['baslik']}"
            t["ozet"] = SABLON[d]["arsiv_not"].format(tarih=x["tarih"]) + " " + t["ozet"]
            t["metin"] = t["ozet"]
        sonuc.append(a)
    sonuc = [x for x in sonuc if ayar.get("turler", {}).get(x["sosyal_tur"], True)]
    cikis = next((date.fromisoformat(x["tarih"]) for x in oku(kok, "takvim.json", [])
                  if x.get("id") == GTA_ID and x.get("kesin") and x.get("tarih")), None)
    if cikis and 0 <= (cikis - bugun).days <= GTA_ONCELIK_GUN:
        for x in sonuc:
            if x["sosyal_tur"] != "arsiv" and gta_mi(x):
                x["gta_oncelik"] = True
    return sonuc


GTA_ID = "gta-vi"
GTA_ONCELIK_GUN = 7  # çıkışa bu kadar gün kala her gün en az bir GTA VI gönderisi


def gta_mi(x) -> bool:
    return (norm(x.get("oyun")) in {"gta vi", "grand theft auto vi", "gta 6"}
            or str(x.get("id", "")).startswith((GTA_ID + "-", "gta6-", "takvim-" + GTA_ID + "-")))


def oncelikli(kuyruk, dil, platform, kayit, simdi):
    """Çıkışa kalan son günlerde, bu (dil, platform) için bugün henüz GTA VI gönderisi yoksa GTA VI adayları öne alınır.
    Günlük sınırlar çağıranda uygulanır; GTA gönderisi çıkınca sıra normale döner (GTA kuyruğu tüm hakkı yemez)."""
    if not any(x.get("gta_oncelik") for x in kuyruk):
        return kuyruk
    gun = simdi.strftime("%Y-%m-%d")
    for k, r in kayit.items():
        p = k.split("|")
        bugun_mu = (r.get("niyet_zamani") or r.get("zaman") or "")[:10] == gun
        if (len(p) == 4 and p[1:3] == [dil, platform] and bugun_mu
                and r.get("durum") in ("tamam", "niyet", "elle_bak") and gta_mi({"id": r.get("id", "")})):
            return kuyruk
    return sorted(kuyruk, key=lambda x: not x.get("gta_oncelik"))


def gta_bekliyor(kuyruk, dil, platform, kayit, simdi) -> bool:
    """Çıkış haftasında bu (dil, platform) için bugün henüz GTA VI gönderisi yok ve kuyrukta GTA VI adayı var mı?
    `oncelikli` ile aynı kural; hesap içinde hangi dilin önce deneneceğini belirlemek için kullanılır."""
    if not any(x.get("gta_oncelik") and dil in x.get("diller", {}) for x in kuyruk):
        return False
    gun = simdi.strftime("%Y-%m-%d")
    for k, r in kayit.items():
        p = k.split("|")
        bugun_mu = (r.get("niyet_zamani") or r.get("zaman") or "")[:10] == gun
        if (len(p) == 4 and p[1:3] == [dil, platform] and bugun_mu
                and r.get("durum") in ("tamam", "niyet", "elle_bak") and gta_mi({"id": r.get("id", "")})):
            return False
    return True


def son_tur(kayit, dil, platform):
    son = [(v.get("zaman") or v.get("niyet_zamani") or "", v.get("sosyal_tur", "haber"))
           for k, v in kayit.items() if k.split("|")[1:3] == [dil, platform]
           and v.get("durum", "tamam") in ("tamam", "niyet", "elle_bak")]
    return max(son, default=("", None), key=lambda v: v[0])[1]


def uygun(x, dil, platform, kayit, simdi):
    tur = x.get("sosyal_tur", "haber")
    if dil not in x.get("diller", {}):
        return False
    if tur != "haber" and tur == son_tur(kayit, dil, platform):
        return False
    if tur == "arsiv":
        konu = x.get("otomasyon", {}).get("konu") or x["id"]
        if any(k.split("|")[1:3] == [dil, platform] and
               (k.split("|")[0] in (konu, x["id"]) or r.get("id") == x["id"])
               for k, r in kayit.items()):
            return False
    if tur == "rehber":
        for k, r in kayit.items():
            if k.split("|")[1:3] != [dil, platform] or r.get("id") != x["id"]:
                continue
            dt = zaman(r.get("zaman") or r.get("niyet_zamani"))
            if dt and simdi - dt < timedelta(days=14):
                return False
    return True
