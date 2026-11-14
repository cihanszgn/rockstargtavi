#!/usr/bin/env python3
"""Sosyal hesap kurulum yardımcısı (Windows, Cio'nun bilgisayarı).

Çift tıkla: sosyal\\kurulum.bat   ya da   py tools\\sosyal_kurulum.py

Ne yapar:
  1) Hesap bilgilerini gizli sorar (ekranda görünmez), hesabı dener, doğruysa GitHub Secrets'a yazar.
  2) Instagram anahtarını bu bilgisayarda Windows şifrelemesiyle (DPAPI) saklar ve
     --ig-yenile ile 60 günlük süresini uzatır (haftalık Windows görevi bunu çağırır).
Şifreler hiçbir dosyaya düz metin yazılmaz, ekrana basılmaz.
"""
from __future__ import annotations

import base64
import ctypes
import getpass
import json
import os
import pathlib
import subprocess
import sys
import urllib.parse
from datetime import datetime

KOK = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK / "tools"))
from sosyal_yayinla import GEREKEN, ONEK_SIR, PaylasimHatasi, istek, oauth1_baslik  # noqa: E402

REPO = "cihanszgn/rockstargtavi"
AYAR = KOK / "sosyal" / "ayarlar.json"
SAKLA = pathlib.Path(os.environ.get("LOCALAPPDATA", str(pathlib.Path.home()))) / "rockstargtavi-sosyal"
DIL_AD = {"tr": "Türkçe", "en": "İngilizce", "fr": "Fransızca", "es": "İspanyolca"}

SORU = {
    "x": [("API_KEY", "API Key (Consumer Key)", True), ("API_SECRET", "API Key Secret", True),
          ("ACCESS_TOKEN", "Access Token", True), ("ACCESS_SECRET", "Access Token Secret", True)],
    "reddit": [("USERNAME", "Reddit kullanıcı adı (u/ olmadan)", False), ("PASSWORD", "Reddit şifresi", True),
               ("CLIENT_ID", "Uygulama kimliği (uygulama adının altındaki kısa yazı)", True), ("CLIENT_SECRET", "secret", True)],
    "instagram": [("TOKEN", "Instagram erişim anahtarı (Generate token ile alınan uzun yazı)", True)],
}


# ---------------------------------------------------------------- Windows DPAPI
class _BLOB(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _dpapi(veri: bytes, koru: bool) -> bytes:
    tampon = ctypes.create_string_buffer(veri, len(veri))
    giris = _BLOB(len(veri), ctypes.cast(tampon, ctypes.POINTER(ctypes.c_char)))
    cikis = _BLOB()
    f = ctypes.windll.crypt32.CryptProtectData if koru else ctypes.windll.crypt32.CryptUnprotectData
    if not f(ctypes.byref(giris), None, None, None, None, 0, ctypes.byref(cikis)):
        raise OSError("Windows şifreleme (DPAPI) başarısız")
    try:
        return ctypes.string_at(cikis.pbData, cikis.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(cikis.pbData)


def ig_sakla(dil: str, token: str) -> None:
    SAKLA.mkdir(parents=True, exist_ok=True)
    (SAKLA / f"ig_{dil}.bin").write_bytes(_dpapi(token.encode(), True))
    (SAKLA / f"ig_{dil}.json").write_text(json.dumps({"yenilendi": datetime.now().isoformat(timespec="seconds")}), encoding="utf-8")


def ig_oku(dil: str) -> str | None:
    p = SAKLA / f"ig_{dil}.bin"
    return _dpapi(p.read_bytes(), False).decode() if p.exists() else None


# ---------------------------------------------------------------- GitHub
def gh(*arg, girdi: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["gh", *arg], input=girdi, text=True, capture_output=True)


def sir_yaz(ad: str, deger: str) -> None:
    r = gh("secret", "set", ad, "--repo", REPO, girdi=deger)
    if r.returncode != 0:
        raise SystemExit(f"GitHub'a yazılamadı ({ad}): {r.stderr.strip()}")


# ---------------------------------------------------------------- hesap denemeleri
def dene(platform: str, s: dict) -> str:
    if platform == "x":
        url = "https://api.x.com/2/users/me"
        _, c = istek("GET", url, basliklar={"Authorization": oauth1_baslik("GET", url, s["API_KEY"], s["API_SECRET"], s["ACCESS_TOKEN"], s["ACCESS_SECRET"])})
        return "@" + c["data"]["username"]
    if platform == "reddit":
        ua = {"User-Agent": f"web:rockstargtavi-sosyal:1.0 (by /u/{s['USERNAME']})"}
        kim = base64.b64encode(f"{s['CLIENT_ID']}:{s['CLIENT_SECRET']}".encode()).decode()
        _, t = istek("POST", "https://www.reddit.com/api/v1/access_token",
                     veri={"grant_type": "password", "username": s["USERNAME"], "password": s["PASSWORD"]},
                     basliklar={**ua, "Authorization": f"Basic {kim}"})
        if "access_token" not in t:
            raise PaylasimHatasi(f"Reddit girişi olmadı: {t}")
        _, me = istek("GET", "https://oauth.reddit.com/api/v1/me", basliklar={**ua, "Authorization": f"bearer {t['access_token']}"})
        return "u/" + me["name"]
    _, me = istek("GET", "https://graph.instagram.com/me?" + urllib.parse.urlencode({"fields": "user_id,username", "access_token": s["TOKEN"]}))
    s["USER_ID"] = str(me.get("user_id") or me.get("id"))
    return "@" + me.get("username", "?")


def hesap_ekle() -> None:
    dil = secim("Hangi dilin hesabı?", list(DIL_AD), lambda d: f"{d.upper()} — {DIL_AD[d]}")
    platform = secim("Hangi platform?", ["x", "reddit", "instagram"], lambda p: {"x": "X (Twitter)", "reddit": "Reddit", "instagram": "Instagram"}[p])
    print("\nBilgileri yapıştır (sağ tık ya da Ctrl+V). Gizli alanlar ekranda görünmez, bu normal.")
    s = {}
    for anahtar, soru, gizli in SORU[platform]:
        deger = (getpass.getpass(f"  {soru}: ") if gizli else input(f"  {soru}: ")).strip()
        if not deger:
            print("Boş bırakıldı, iptal.")
            return
        s[anahtar] = deger
    print("Hesap deneniyor...")
    try:
        ad = dene(platform, s)
    except (PaylasimHatasi, KeyError) as h:
        print(f"\nOLMADI: {h}\nBilgileri kontrol et; çözülmezse bu ekranın görüntüsünü Claude'a at (şifre görünmez).")
        return
    print(f"Doğru: {ad}")
    for a in GEREKEN[platform]:
        sir_yaz(f"{ONEK_SIR[platform]}_{dil.upper()}_{a}", s[a])
    if platform == "instagram":
        ig_sakla(dil, s["TOKEN"])
    ayar = json.loads(AYAR.read_text(encoding="utf-8"))
    if not ayar["hesaplar"][dil].get(platform):
        ayar["hesaplar"][dil][platform] = True
        AYAR.write_text(json.dumps(ayar, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print("Not: ayarlar.json'da bu hesap açıldı; Claude'a 'sosyal ayarı pushla' de.")
    print(f"\nTAMAM: {platform} / {dil.upper()} hesabı ({ad}) kuruldu. Yeni haberler otomatik paylaşılacak.")


def ig_yenile(sessiz: bool = False) -> int:
    hata = 0
    for dil in DIL_AD:
        tok = ig_oku(dil)
        if not tok:
            continue
        try:
            _, c = istek("GET", "https://graph.instagram.com/refresh_access_token?" + urllib.parse.urlencode({"grant_type": "ig_refresh_token", "access_token": tok}))
            yeni = c["access_token"]
        except (PaylasimHatasi, KeyError) as h:
            print(f"Instagram {dil.upper()} yenilenemedi: {h}")
            hata += 1
            continue
        ig_sakla(dil, yeni)
        sir_yaz(f"IG_{dil.upper()}_TOKEN", yeni)
        if not sessiz:
            print(f"Instagram {dil.upper()} anahtarı 60 gün uzatıldı.")
    return 1 if hata else 0


def durum() -> None:
    r = gh("secret", "list", "--repo", REPO)
    if r.returncode != 0:
        print("GitHub'a bağlanılamadı:", r.stderr.strip())
        return
    var = {satir.split()[0] for satir in r.stdout.splitlines() if satir.strip()}
    ayar = json.loads(AYAR.read_text(encoding="utf-8"))
    print("\nHesap durumu (✓ kurulu, · eksik, - kapalı):")
    for dil in DIL_AD:
        parca = []
        for p in ("x", "reddit", "instagram"):
            if not ayar["hesaplar"][dil].get(p):
                isaret = "-"
            else:
                isaret = "✓" if all(f"{ONEK_SIR[p]}_{dil.upper()}_{a}" in var for a in GEREKEN[p]) else "·"
            parca.append(f"{p} {isaret}")
        print(f"  {dil.upper()}: " + "   ".join(parca))


def deneme() -> None:
    r = gh("workflow", "run", "sosyal.yml", "--repo", REPO, "-f", "deneme=true")
    print("Deneme çalıştırması başlatıldı (hiçbir şey gönderilmez). Sonuç: https://github.com/" + REPO + "/actions" if r.returncode == 0 else r.stderr)


def secim(soru, secenekler, ad):
    print(f"\n{soru}")
    for i, s in enumerate(secenekler, 1):
        print(f"  {i}) {ad(s)}")
    while True:
        g = input("Numara yaz: ").strip()
        if g.isdigit() and 1 <= int(g) <= len(secenekler):
            return secenekler[int(g) - 1]


def main() -> int:
    if "--ig-yenile" in sys.argv:
        return ig_yenile(sessiz="--sessiz" in sys.argv)
    if gh("auth", "status").returncode != 0:
        print("GitHub girişi yok. Önce PowerShell'de:  gh auth login")
        return 1
    while True:
        is_ = secim("Ne yapalım?", ["ekle", "durum", "deneme", "ig", "cik"], lambda k: {
            "ekle": "Hesap ekle (X / Reddit / Instagram)", "durum": "Hangi hesaplar kurulu?",
            "deneme": "Deneme çalıştırması (gönderi atmadan)", "ig": "Instagram anahtarını şimdi yenile", "cik": "Çık"}[k])
        if is_ == "ekle":
            hesap_ekle()
        elif is_ == "durum":
            durum()
        elif is_ == "deneme":
            deneme()
        elif is_ == "ig":
            ig_yenile()
        else:
            return 0


if __name__ == "__main__":
    sys.exit(main())
