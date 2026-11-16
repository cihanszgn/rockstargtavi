"""video-hf için varlık hazırlığı: resmî görselden duotone varyantlar ve zamanlama verisi (data.js).
Kullanım: py araclar/hazirla.py   (video-hf klasöründe)"""
import json, pathlib
from PIL import Image, ImageOps, ImageFilter

K = pathlib.Path(__file__).resolve().parents[1]
ham = Image.open(K / "assets/img/r6-ham.jpg").convert("RGB")
# 2x büyütme: dikey kareye kırpınca yumuşamasın
ham2 = ham.resize((ham.width * 2, ham.height * 2), Image.LANCZOS)

def duo(img, golge, orta, isik):
    g = ImageOps.autocontrast(ImageOps.grayscale(img), cutoff=1)
    g = ImageOps.autocontrast(g.point(lambda v: int(255 * (v / 255) ** 0.85)))
    return ImageOps.colorize(g, black=golge, white=isik, mid=orta)

duo(ham2, "#050a1e", "#2a4fd6", "#bcd2ff").save(K / "assets/img/duo-mavi.jpg", quality=88)
duo(ham2, "#1a0d00", "#c98a00", "#ffe45c").save(K / "assets/img/duo-sari.jpg", quality=88)
duo(ham2, "#1b0508", "#c01f2f", "#ffd9d0").save(K / "assets/img/duo-kirmizi.jpg", quality=88)
ham2.save(K / "assets/img/r6.jpg", quality=90)
(K / "assets/img/r6-ham.jpg").unlink(missing_ok=True) if False else None

z = json.loads((K / "assets/ses/zamanli.json").read_text(encoding="utf-8"))
veri = {"sure": z["sure"], "sahneler": [{"sablon": s["sablon"], "bas": s["bas"], "bit": s["bit"]} for s in z["sahneler"]],
        "kelimeler": z["kelimeler"], "parcalar": z["parcalar"]}
(K / "assets/data.js").write_text("window.ZAMAN = " + json.dumps(veri, ensure_ascii=False) + ";\n", encoding="utf-8")
print("tamam", z["sure"], len(z["kelimeler"]), len(z["parcalar"]))
