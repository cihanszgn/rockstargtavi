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
import secrets
import subprocess
import sys
import threading
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

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
    "youtube": [("CLIENT_ID", "Google OAuth istemci kimliği (Client ID)", True), ("CLIENT_SECRET", "Google OAuth istemci sırrı (Client secret)", True)],
}
# force-ssl: kanal açıklaması ve video bilgisi gibi ayarları değiştirmek için (tools/youtube_kanal.py kullanır).
YT_YONETIM = "https://www.googleapis.com/auth/youtube.force-ssl"
YT_KAPSAM = ("https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly "
             + YT_YONETIM)


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


def yt_sakla(dil: str, s: dict) -> None:
    """YouTube anahtarlarını bu bilgisayarda da saklar; kanal ayarları (youtube_kanal.py) buradan okur."""
    SAKLA.mkdir(parents=True, exist_ok=True)
    veri = json.dumps({a: s[a] for a in GEREKEN["youtube"]}).encode()
    (SAKLA / f"yt_{dil}.bin").write_bytes(_dpapi(veri, True))


def yt_oku(dil: str) -> dict | None:
    p = SAKLA / f"yt_{dil}.bin"
    return json.loads(_dpapi(p.read_bytes(), False).decode()) if p.exists() else None


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


def yt_izin_al(client_id: str, client_secret: str) -> str:
    """Tarayıcıda Google izin ekranını açar, bu bilgisayardaki geçici adrese (127.0.0.1) dönen kodu yakalar,
    yenileme anahtarını (refresh token) döndürür. Anahtar ekrana yazılmaz."""
    durum_kodu = secrets.token_urlsafe(16)
    sonuc: dict = {}

    class Isleyici(BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if q.get("state", [""])[0] == durum_kodu and ("code" in q or "error" in q):
                sonuc["code"] = q.get("code", [""])[0]
                sonuc["error"] = q.get("error", [""])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("<p>Tamam, bu sekmeyi kapatıp kurulum penceresine dönebilirsin.</p>".encode("utf-8"))

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), Isleyici)
    port = srv.server_address[1]
    yonlendir = f"http://127.0.0.1:{port}"
    adres = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": client_id, "redirect_uri": yonlendir, "response_type": "code", "scope": YT_KAPSAM,
        "access_type": "offline", "prompt": "consent", "state": durum_kodu})
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print("\nTarayıcı açılıyor. YouTube kanalının bağlı olduğu Google hesabıyla gir ve İzin ver'e bas.")
    print("Açılmazsa şu adresi tarayıcıya yapıştır:\n" + adres)
    webbrowser.open(adres)
    for _ in range(300):  # en çok 5 dakika bekle
        if sonuc:
            break
        threading.Event().wait(1)
    srv.shutdown()
    if not sonuc.get("code"):
        raise PaylasimHatasi(f"İzin alınamadı ({sonuc.get('error') or 'zaman aşımı'})", kesin=True)
    _, c = istek("POST", "https://oauth2.googleapis.com/token", veri={
        "code": sonuc["code"], "client_id": client_id, "client_secret": client_secret,
        "redirect_uri": yonlendir, "grant_type": "authorization_code"})
    if not isinstance(c, dict) or not c.get("refresh_token"):
        raise PaylasimHatasi("Google yenileme anahtarı vermedi. Hesap izinlerinden bu uygulamanın erişimini kaldırıp yeniden dene.", kesin=True)
    return c["refresh_token"]


def yt_dene(s: dict) -> str:
    _, t = istek("POST", "https://oauth2.googleapis.com/token", veri={
        "client_id": s["CLIENT_ID"], "client_secret": s["CLIENT_SECRET"], "refresh_token": s["REFRESH_TOKEN"], "grant_type": "refresh_token"})
    _, k = istek("GET", "https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true", basliklar={"Authorization": "Bearer " + t["access_token"]})
    ogeler = k.get("items") or []
    if not ogeler:
        raise PaylasimHatasi("Bu Google hesabında YouTube kanalı görünmüyor.", kesin=True)
    return ogeler[0]["snippet"]["title"]


def youtube_ekle() -> None:
    dil = secim("Hangi dilin YouTube kanalı?", list(DIL_AD), lambda d: f"{d.upper()} — {DIL_AD[d]}")
    print("\nGoogle Cloud'dan aldığın Client ID ve Client secret'ı yapıştır (ekranda görünmez, bu normal).")
    s = {}
    for anahtar, soru, _gizli in SORU["youtube"]:
        deger = getpass.getpass(f"  {soru}: ").strip()
        if not deger:
            print("Boş bırakıldı, iptal.")
            return
        s[anahtar] = deger
    try:
        s["REFRESH_TOKEN"] = yt_izin_al(s["CLIENT_ID"], s["CLIENT_SECRET"])
        print("İzin alındı, kanal deneniyor...")
        ad = yt_dene(s)
    except (PaylasimHatasi, KeyError) as h:
        print(f"\nOLMADI: {h}\nBu ekranın görüntüsünü Claude'a at (şifreler görünmez).")
        return
    print(f'Doğru: kanal "{ad}"')
    for a in GEREKEN["youtube"]:
        sir_yaz(f"YT_{dil.upper()}_{a}", s[a])
    yt_sakla(dil, s)
    ayar = json.loads(AYAR.read_text(encoding="utf-8"))
    ayar["hesaplar"][dil]["youtube"] = True
    ayar.setdefault("youtube", {}).setdefault("gizlilik", "private")
    AYAR.write_text(json.dumps(ayar, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f'\nTAMAM: YouTube / {dil.upper()} ("{ad}") kuruldu. Videolar önce ÖZEL (private) yüklenir; '
          'Studio\'da bakıp memnunsan ayarlar.json\'da "gizlilik" değerini "public" yapmasını Claude\'dan iste.')


def azure_ekle() -> None:
    print("\nAzure Speech anahtarını ve bölgesini yapıştır (anahtar ekranda görünmez).")
    anahtar = getpass.getpass("  Azure Speech KEY 1: ").strip()
    bolge = input("  Bölge (örn. westeurope, northeurope): ").strip().lower()
    if not anahtar or not bolge:
        print("Boş bırakıldı, iptal.")
        return
    try:
        req = urllib.request.Request(f"https://{bolge}.api.cognitive.microsoft.com/sts/v1.0/issueToken", data=b"",
                                     headers={"Ocp-Apim-Subscription-Key": anahtar}, method="POST")
        with urllib.request.urlopen(req, timeout=30):
            pass
    except Exception as h:  # hata metni anahtarı içerebilir; yalnız türü gösterilir
        print(f"\nOLMADI: anahtar ya da bölge yanlış görünüyor ({type(h).__name__}). Ekran görüntüsünü Claude'a at.")
        return
    sir_yaz("AZURE_SPEECH_KEY", anahtar)
    sir_yaz("AZURE_SPEECH_REGION", bolge)
    print("\nTAMAM: Azure Speech anahtarı ve bölgesi GitHub'a yazıldı. Video üretimi bunu kullanır.")


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
        for p in ("x", "reddit", "instagram", "youtube"):
            if not ayar["hesaplar"][dil].get(p):
                isaret = "-"
            else:
                isaret = "✓" if all(f"{ONEK_SIR[p]}_{dil.upper()}_{a}" in var for a in GEREKEN[p]) else "·"
            parca.append(f"{p} {isaret}")
        print(f"  {dil.upper()}: " + "   ".join(parca))
    print("  Azure Speech: " + ("✓ kurulu" if {"AZURE_SPEECH_KEY", "AZURE_SPEECH_REGION"} <= var else "· eksik"))


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
        is_ = secim("Ne yapalım?", ["ekle", "durum", "deneme", "ig", "youtube", "azure", "cik"], lambda k: {
            "ekle": "Hesap ekle (X / Reddit / Instagram)", "durum": "Hangi hesaplar kurulu?",
            "deneme": "Deneme çalıştırması (gönderi atmadan)", "ig": "Instagram anahtarını şimdi yenile", "youtube": "YouTube kanalı bağla (Shorts)",
            "azure": "Azure Speech anahtarı ekle (video sesi)", "cik": "Çık"}[k])
        if is_ == "ekle":
            hesap_ekle()
        elif is_ == "youtube":
            youtube_ekle()
        elif is_ == "azure":
            azure_ekle()
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
