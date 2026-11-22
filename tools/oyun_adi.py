"""Haber başlığında oyun adının geçip geçmediğini denetler ve gerekirse başlığın önüne ekler.

Sosyal gönderide başlık tek başına okunur: "Yeni güncelleme hataları düzeltiyor" hangi oyunun haberi olduğunu
söylemez. Kural hem haber yazım hattında (reddetme) hem sosyal kuyrukta (öne ekleme) kullanılır.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

ONEMSIZ = {"the", "of", "and", "for", "to", "in", "on", "a", "an", "de", "la", "le", "el", "ve", "ile"}
# Latin, rakam, noktalama ve genel simgeler dışındaki yazılar (Kana, Han, Hangul, Kiril, Arap...) oyun adında kabul edilmez:
# sosyal kart yazı tipi bunları çizemez ve okur adı tanıyamaz.
LATIN_DISI = re.compile(r"[Ͱ-᷿⺀-꓏가-힯豈-﫿＀-￯]")


def latin_mi(ad: str) -> bool:
    return bool(re.search(r"[A-Za-z]", ad or "")) and not LATIN_DISI.search(ad or "")


def _sade(s: str) -> str:
    s = (s or "").replace("ı", "i").replace("İ", "i")
    s = unicodedata.normalize("NFKD", s.casefold())
    return "".join(c for c in s if not unicodedata.combining(c))


def _sozcukler(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", _sade(s))


def _bitisik(s: str) -> str:
    return "".join(_sozcukler(s))


def takma_adlar(kok: Path) -> dict[str, list[str]]:
    """data/oyunlar.json içinden {sade oyun adı: [ad, kısa ad, eşleşmeler]}; dosya yoksa boş."""
    try:
        oyunlar = json.loads((Path(kok) / "data" / "oyunlar.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    sonuc: dict[str, list[str]] = {}
    for o in oyunlar if isinstance(oyunlar, list) else []:
        adlar = [a for a in [o.get("ad"), o.get("kisa"), *(o.get("eslesme") or [])] if isinstance(a, str) and a.strip()]
        for a in adlar:
            sonuc.setdefault(_bitisik(a), adlar)
    return sonuc


def gecer(baslik: str, oyun: str, takma: dict[str, list[str]] | None = None) -> bool:
    """Başlık oyunu tanıtıyor mu: tam ad, bilinen takma ad ya da adın önemli sözcüklerinin en az yarısı."""
    if not (oyun or "").strip():
        return True
    b_soz, b_bit = set(_sozcukler(baslik)), _bitisik(baslik)
    adlar = [oyun, *((takma or {}).get(_bitisik(oyun)) or [])]
    for ad in adlar:
        bit = _bitisik(ad)
        if not bit:
            continue
        # kısa takma ad (CS2, KO) yalnız ayrı sözcük olarak sayılır; uzun ad bitişik aramayla da bulunur
        if (len(bit) >= 5 and bit in b_bit) or bit in b_soz:
            return True
    onemli = [s for s in _sozcukler(oyun) if s not in ONEMSIZ and (len(s) >= 3 or s.isdigit())]
    harfli = [s for s in onemli if not s.isdigit()]
    if not harfli:
        return False
    if harfli[0] in b_soz:
        return True  # serinin adı (ARK, Zelda, Xbox) tek başına oyunu tanıtır
    bulunan = sum(1 for s in harfli if s in b_soz or any(k.startswith(s) and len(s) >= 4 for k in b_soz))
    return bulunan * 2 >= len(harfli)


def oyunlu_baslik(baslik: str, oyun: str, takma: dict[str, list[str]] | None = None) -> str:
    """Başlıkta oyun adı yoksa "Oyun: başlık" döndürür; ad Latin değilse dokunmaz (çizilemeyen ad eklenmez)."""
    if gecer(baslik, oyun, takma) or not latin_mi(oyun):
        return baslik
    ayrac = " — " if ":" in oyun or ":" in baslik else ": "
    return f"{oyun.strip()}{ayrac}{baslik.strip()}"
