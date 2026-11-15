"""Archivo karakter genişlik tablosu üretir (video/src/olcu/genislik.json).

tools/video_uret.py altyazı satırlarını ve kutu/kart yazılarının sığmasını bu tabloyla hesaplar; böylece
çalışma anında Pillow gerekmez. Yazı tipi değişirse yeniden üretin:
    uv run --no-project --with pillow==12.0.0 python video/araclar/genislik_uret.py
Değerler em biriminde (1 = punto), wdth ekseni 100 (normal genişlik), harf aralığı yok, kerning yok sayılır.
"""
import json
from pathlib import Path

from PIL import ImageFont

KOK = Path(__file__).resolve().parents[2]
YAZI = KOK / "fonts" / "archivo.woff2"
CIKTI = KOK / "video" / "src" / "olcu" / "genislik.json"
OLCEK = 1000

HARFLER = (
    "".join(chr(c) for c in range(32, 127))
    + "çÇğĞıİöÖşŞüÜâÂîÎûÛäÄëËïÏÿŸàÀèÈéÉêÊôÔùÙœŒæÆñÑáÁíÍóÓúÚ¿¡«»"
    + "–—‘’“”•…×·°€£₺%"
)


def main() -> None:
    yazi = ImageFont.truetype(str(YAZI), OLCEK)
    tablo = {}
    for agirlik in (700, 800):
        yazi.set_variation_by_axes([agirlik, 100])
        tablo[str(agirlik)] = {h: round(yazi.getlength(h) / OLCEK, 4) for h in HARFLER}
    yazi.set_variation_by_axes([800, 100])
    varsayilan = round(yazi.getlength("M") / OLCEK, 4)
    CIKTI.parent.mkdir(parents=True, exist_ok=True)
    CIKTI.write_text(json.dumps({"birim": "em", "wdth": 100, "varsayilan": varsayilan, "agirlik": tablo},
                                ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(CIKTI, len(HARFLER), "harf")


if __name__ == "__main__":
    main()
