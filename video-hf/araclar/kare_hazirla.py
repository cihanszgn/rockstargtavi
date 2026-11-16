"""Tasarım denetimi için kare hazırlama aracı (üretim hattının parçası değil).
Var olan bir iş klasöründen (video/tmp/<taban>/: zamanli.json, tema.json, foto.jpg) geçici Hyperframes projesi kurar,
isteğe bağlı paketi zorlar ve her sahnenin 0.92 anında (açılış için ayrıca 0.25) kare alır.
Kullanım: py video-hf/araclar/kare_hazirla.py --is KLASOR --cikti DIR [--paket esports|gazete|neon|kolaj] [--ad on]"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KOK / "tools"))
import video_hf as hf  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--is", dest="is_klasoru", required=True)
    ap.add_argument("--cikti", required=True)
    ap.add_argument("--paket")
    ap.add_argument("--ad", default="")
    ap.add_argument("--olcek", default="0.5")
    a = ap.parse_args()
    isk = Path(a.is_klasoru)
    props = json.loads((isk / "zamanli.json").read_text(encoding="utf-8"))
    tema = json.loads((isk / "tema.json").read_text(encoding="utf-8"))
    foto = isk / "foto.jpg"
    foto = foto if foto.exists() else None
    if a.paket and a.paket != tema["paket"]:
        girdi = hf.tema_girdisi(props["haber"], None, None, a.paket)
        tema = hf.tema_sec(props["haber"], girdi, foto)
    cikti = Path(a.cikti)
    cikti.mkdir(parents=True, exist_ok=True)
    gecici = cikti / "_proje"
    ses = cikti / "_sessiz.mp3"
    ses.write_bytes(b"")
    hf.klasor_kur(gecici, props, tema, ses, foto)
    anlar = []
    for i, s in enumerate(props["sahneler"]):
        b, e = s["bas"], s["bit"]
        if i == 0:
            anlar.append(f"{a.ad}{i}-{s['sablon']}-a:{round(b + (e - b) * .25, 2)}")
        anlar.append(f"{a.ad}{i}-{s['sablon']}:{round(b + (e - b) * .92, 2)}")
    node = "node"
    r = subprocess.run([node, str(KOK / "video-hf" / "araclar" / "kare_al.mjs"), "--klasor", str(gecici), "--cikti", str(cikti),
                        "--anlar", ",".join(anlar), "--chrome", hf.tarayici_yolu(), "--hf", hf.hf_koku(), "--olcek", a.olcek])
    return r.returncode


if __name__ == "__main__":
    raise SystemExit(main())
