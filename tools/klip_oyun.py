"""Klip için iki doğrulama: (A) oyun adı doğru mu, (B) dökümsüz klibin kendi sesinden paylaşım metni.

A: Kick yayının TEK kategorisini verir; yayın sırasında kategori değişirse kliplerin hepsine yanlış ad yazılırdı. Zamana
bağlı kategori kaynağı yok (ölçüldü: otomasyon/KLIP-HATTI.md), bu yüzden klibin 3 karesi görsel destekli modele sorulur:
"kategori bu mu; değilse hangi oyun; emin değilsen bilinmiyor". Karar: oyun adı ya DOĞRU yazılır ya hiç yazılmaz.
Klip başına en çok 1 model çağrısı; sonuç (kaynağıyla) pakete yazılır, tekrar sorulmaz (yalnız teknik hatada yeniden denenir).

B: sohbet sinyaliyle kesilmiş klibin döküm yoktur. Klibin kendi sesi (<=59 sn) mevcut Whisper yoluyla yazıya çevrilir,
mevcut yargı çağrısıyla kisa_aciklama + uzun başlık üretilir. Anlamsız/boş konuşmada metin üretilmez (şablona düşülür).
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone

import klip_konusma

OYUN_SURUMU = 1
KARE_SAYISI = 3
KARE_GENISLIK = 640
SORU_ZAMAN_ASIMI = 240
OYUN_AD_AZAMI = 40
MODEL_VARSAYILAN = 'sonnet'

SISTEM = 'You identify video games from livestream screenshots. Reply with a single JSON object only, no other text.'
ISTEM = ('Read the image file {dosya} (three video frames side by side, from one livestream clip). '
         'The streamer\'s stream category is "{kategori}". Is the game visible in these frames "{kategori}"? '
         'Answer ONLY JSON: {{"karar":"evet"|"hayir"|"bilinmiyor","oyun":"<actual game name if hayir and you are sure, '
         'else null>","kanit":"<short visible evidence: logo, UI text, HUD, character>"}}. '
         'If the frames do not clearly show a game (menu, desktop, loading screen, black screen, only a webcam) or you '
         'are not sure, answer "bilinmiyor". Never guess.')


class OyunHatasi(RuntimeError):
    pass


def _simdi() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _claude_gorsel(istem: str, cwd: str, model: str = MODEL_VARSAYILAN, zaman_asimi: int = SORU_ZAMAN_ASIMI) -> dict:
    """Ucuz görsel çağrı: ayar/MCP/skill yüklenmez, yalnız Read aracı, çalışma klasöründeki görseli okur.
    Dönüş: {'metin': yanıt, 'maliyet_usd': ...}."""
    exe = shutil.which('claude')
    if not exe:
        raise OyunHatasi('claude komutu bulunamadı')
    argv = [exe, '-p', '--model', model, '--output-format', 'json', '--permission-mode', 'dontAsk',
            '--tools', 'Read', '--allowedTools', 'Read', '--setting-sources', '', '--strict-mcp-config',
            '--disable-slash-commands', '--system-prompt', SISTEM]
    try:
        r = subprocess.run(argv, input=istem, cwd=cwd, capture_output=True, text=True, encoding='utf-8',
                           errors='replace', timeout=zaman_asimi,
                           creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise OyunHatasi(f'görsel model çağrısı: {type(e).__name__}') from e
    if r.returncode != 0:
        raise OyunHatasi(f'görsel model çağrısı başarısız ({r.returncode}): {(r.stderr or r.stdout)[-300:]}')
    try:
        veri = json.loads(r.stdout)
        metin = veri['result']
    except (ValueError, KeyError, TypeError) as e:
        raise OyunHatasi(f'görsel model çıktısı okunamadı: {r.stdout[-200:]}') from e
    if veri.get('is_error'):
        raise OyunHatasi(f'görsel model hatası: {str(metin)[-200:]}')
    return {'metin': str(metin), 'maliyet_usd': veri.get('total_cost_usd')}


def yaniti_coz(metin: str, kategori: str) -> dict:
    """Model yanıtı -> {'karar': 'evet'|'hayir'|'bilinmiyor', 'oyun': ad|None, 'kanit': str|None}.
    Şemaya uymayan, kanıtsız ya da adsız 'hayir' yanıtı 'bilinmiyor' sayılır (yanlış ad yazmaktansa yazmamak)."""
    try:
        v = json.loads(re.sub(r'^```(?:json)?\s*|\s*```$', '', str(metin).strip()))
    except ValueError:
        return {'karar': 'bilinmiyor', 'oyun': None, 'kanit': None, 'not': 'yanıt JSON değil'}
    if not isinstance(v, dict):
        return {'karar': 'bilinmiyor', 'oyun': None, 'kanit': None, 'not': 'yanıt nesne değil'}
    karar = str(v.get('karar') or '').strip().lower()
    kanit = str(v.get('kanit') or '').strip()[:200] or None
    oyun = v.get('oyun')
    oyun = re.sub(r'\s+', ' ', oyun).strip().strip('"“”\'`') if isinstance(oyun, str) else None
    if karar == 'evet' and kanit:
        return {'karar': 'evet', 'oyun': None, 'kanit': kanit}
    if karar == 'hayir' and kanit and oyun and oyun.lower() not in ('null', 'none', 'bilinmiyor', 'unknown') \
            and len(oyun) <= OYUN_AD_AZAMI and oyun.lower() != str(kategori).lower():
        return {'karar': 'hayir', 'oyun': oyun, 'kanit': kanit}
    return {'karar': 'bilinmiyor', 'oyun': None, 'kanit': kanit}


def kolaj_yaz(kareler: list, hedef: pathlib.Path) -> None:
    import cv2
    import numpy as np
    boy = min(k.shape[0] for k in kareler)
    sira = [k if k.shape[0] == boy else cv2.resize(k, (int(k.shape[1] * boy / k.shape[0]), boy)) for k in kareler]
    if not cv2.imwrite(str(hedef), np.hstack(sira), [cv2.IMWRITE_JPEG_QUALITY, 85]):
        raise OyunHatasi('kolaj yazılamadı')


def _ayni_aralik(a, b, tolerans: float = 3.0) -> bool:
    """Ses hizası düzeltmesi aralığı birkaç sn kaydırabilir; elle kaydırma önbelleği ayrıca düşürür."""
    try:
        return len(a) == 2 and len(b) == 2 and all(abs(float(x) - float(y)) <= tolerans for x, y in zip(a, b))
    except (TypeError, ValueError):
        return False


def onbellek_gecerli(onbellek: dict | None, kategori: str | None, aralik: list) -> bool:
    """Paketteki eski karar aynı kategori ve aynı klip aralığı için verilmişse yeniden sorulmaz."""
    return (isinstance(onbellek, dict) and onbellek.get('surum') == OYUN_SURUMU and onbellek.get('durum') == 'tamam'
            and onbellek.get('kategori') == kategori
            and _ayni_aralik(onbellek.get('aralik'), aralik))


def oyun_karari(kategori: str | None, aralik: list, kareler_fn, *, elle: str | None = None, onbellek: dict | None = None,
                sor=None, model: str = MODEL_VARSAYILAN, tmp: pathlib.Path | None = None) -> dict:
    """Klibin yazılacak oyun adını belirler. Dönüş (hep): {'oyun': ad|None, 'kaynak': ..., 'kategori', 'aralik', 'durum',
    'surum', 'zaman', ...}. kaynak: 'elle' | 'kategori-yok' | 'onbellek' | 'model-kare-onay' (kategori doğrulandı) |
    'model-kare' (kategori yanlış, modelin adı) | 'model-kare-bilinmiyor' (ad yazılmaz) | 'dogrulanamadi' (teknik hata,
    ad yazılmaz, tekrar denenir).  kareler_fn() -> BGR kare listesi; sor(istem, cwd) -> {'metin', 'maliyet_usd'}."""
    taban = {'surum': OYUN_SURUMU, 'kategori': kategori, 'aralik': [round(float(x), 3) for x in aralik], 'zaman': _simdi()}
    if elle is not None:
        return {**taban, 'oyun': elle or None, 'kaynak': 'elle', 'durum': 'tamam'}
    if not kategori:
        return {**taban, 'oyun': None, 'kaynak': 'kategori-yok', 'durum': 'tamam'}
    if onbellek_gecerli(onbellek, kategori, aralik):
        return {**onbellek, 'kaynak_ilk': onbellek.get('kaynak_ilk') or onbellek.get('kaynak'), 'kaynak': 'onbellek'}
    try:
        kareler = kareler_fn()
        with _gecici(tmp) as klasor:
            kolaj_yaz(kareler, klasor / 'kolaj.jpg')
            istem = ISTEM.format(dosya='kolaj.jpg', kategori=kategori)
            y = sor(istem, str(klasor)) if sor else _claude_gorsel(istem, str(klasor), model)
    except Exception as e:   # noqa: BLE001 - doğrulama yardımcıdır: hata = ad yazılmaz
        return {**taban, 'oyun': None, 'kaynak': 'dogrulanamadi', 'durum': 'hata', 'hata': f'{type(e).__name__}: {e}'[:300]}
    c = yaniti_coz(y['metin'], kategori)
    ortak = {**taban, 'durum': 'tamam', 'model': model, 'kanit': c.get('kanit'), 'maliyet_usd': y.get('maliyet_usd'),
             'model_karari': c['karar']}
    if c['karar'] == 'evet':
        return {**ortak, 'oyun': kategori, 'kaynak': 'model-kare-onay'}
    if c['karar'] == 'hayir':
        return {**ortak, 'oyun': c['oyun'], 'kaynak': 'model-kare', 'kategori_yanlis': True}
    return {**ortak, 'oyun': None, 'kaynak': 'model-kare-bilinmiyor'}


class _gecici:
    """tmp verilmişse onu (silmeden), verilmemişse geçici klasör kullanır."""
    def __init__(self, tmp):
        self.tmp, self.ic = tmp, None

    def __enter__(self):
        if self.tmp is not None:
            self.tmp.mkdir(parents=True, exist_ok=True)
            return self.tmp
        import tempfile
        self.ic = tempfile.TemporaryDirectory(prefix='oyun-')
        return pathlib.Path(self.ic.name)

    def __exit__(self, *a):
        if self.ic:
            self.ic.cleanup()


# ---------------------------------------------------------------- B: klibin kendi sesi

def ses_cikar(ff: str, kaynak: str, bas: float, sure: float, yerel: bool, hedef: pathlib.Path, zaman_asimi: int = 600) -> None:
    giris = (['-protocol_whitelist', 'file,http,https,tcp,tls,crypto', '-i', kaynak, '-ss', f'{bas:.3f}'] if yerel
             else ['-ss', f'{bas:.3f}', '-i', kaynak])
    r = subprocess.run([ff, '-hide_banner', '-loglevel', 'error', '-y', *giris, '-t', f'{sure:.3f}', '-vn',
                        '-ar', '16000', '-ac', '1', str(hedef)], capture_output=True, text=True, encoding='utf-8',
                       errors='replace', timeout=zaman_asimi)
    if r.returncode != 0 or not hedef.exists():
        raise OyunHatasi(f'klip sesi alınamadı ({r.returncode}): {r.stderr[-300:]}')


def varsayilan_yargi_modeli():
    return klip_konusma.ButceliModel(
        klip_konusma.ModelYolu({**klip_konusma.AYAR, 'konusma_yargi_model': 'sonnet', 'konusma_bulut': True}), 4)


def ses_onbellek_gecerli(onbellek: dict | None, aralik: list) -> bool:
    return (isinstance(onbellek, dict) and onbellek.get('durum') in ('tamam', 'bos')
            and _ayni_aralik(onbellek.get('aralik'), aralik))


def ses_yargisi(aralik: list, ad: str, ses_dosyasi: pathlib.Path, tmp: pathlib.Path, ayar: dict | None = None, *,
                yargi: bool = True, model=None, dok=None) -> dict:
    """Klip sesini yazıya çevirir; yargi=True ise kisa_aciklama + başlık üretir. Dönüş: {'durum': 'tamam'|'bos'|'hata',
    'dokum', 'kisa_aciklama', 'baslik', 'anlasilir', 'puan', 'gerekce', 'kaynak', 'aralik', 'zaman', ...}.
    'bos': konuşma yok/anlamsız (şablona düşülür); 'hata': teknik (önbelleğe alınmaz)."""
    cfg = {**klip_konusma.AYAR, **(ayar or {}), 'kisa_ad': ad, 'klip_aciklama_yazi': True}
    taban = {'kaynak': 'klip-sesi-whisper', 'aralik': [round(float(x), 3) for x in aralik], 'zaman': _simdi(),
             'kisa_aciklama': None, 'baslik': None, 'anlasilir': None, 'puan': None, 'gerekce': None, 'dokum': ''}
    try:
        tmp.mkdir(parents=True, exist_ok=True)
        raw = (dok or klip_konusma.dok_calistir)(ses_dosyasi, cfg['konusma_model'], cfg['konusma_cihaz'],
                                                  tmp / 'klip-dok.json', kucuk=cfg['konusma_kucuk_model'])
        kelimeler = [w for s in raw['segmentler'] for w in s['kelimeler']]
        cumle = klip_konusma.cumleler(kelimeler)
    except Exception as e:   # noqa: BLE001
        return {**taban, 'durum': 'hata', 'hata': f'{type(e).__name__}: {e}'[:300]}
    dokum = ' '.join(s['metin'] for s in cumle).strip()
    taban.update(dokum=dokum, whisper_model=raw.get('model'), kelime_sayisi=len(kelimeler))
    if len(dokum.split()) < 4:
        return {**taban, 'durum': 'bos', 'neden': 'konuşma yok ya da çok kısa'}
    if not yargi:
        return {**taban, 'durum': 'tamam', 'neden': 'yalnız döküm (açıklama elle verildi)'}
    model = model or varsayilan_yargi_modeli()
    cagri = {'n': 0}

    def sayan(istem):
        cagri['n'] += 1
        return model(istem)
    y = None
    try:
        y = klip_konusma.yargi_al(cumle, sayan, cfg=cfg)
        kisa = klip_konusma.kisa_aciklama_dogrula((y or {}).get('kisa_aciklama'), cfg)
        if y is None or (kisa is None and y.get('anlasilir') is not False):
            # Yargı çağrısı şemaya uymadıysa ya da yazı uzun/uygunsuzsa: mevcut toplu açıklama çağrısı (tamir dahil).
            t = klip_konusma.aciklama_toplu([{'id': '0', 'ad': ad, 'dokum': dokum,
                                              **({'baslik': y['baslik']} if y else {})}], sayan, cfg)
            kisa = t['0']['aciklama']
    except klip_konusma.ModelKotasi:
        raise
    except Exception as e:   # noqa: BLE001
        if y is None:
            return {**taban, 'durum': 'hata', 'hata': f'{type(e).__name__}: {e}'[:300], 'model_cagrisi': cagri['n']}
        kisa = None
    sonuc = {**taban, 'model_cagrisi': cagri['n'], 'whisper_dokum_sn': (raw.get('olcum') or {}).get('sure_sn')}
    if y:
        sonuc.update(anlasilir=y.get('anlasilir'), puan=y.get('puan'), gerekce=y.get('gerekce'))
    if not kisa or (y and y.get('anlasilir') is False):
        return {**sonuc, 'durum': 'bos', 'neden': 'model anlatacak bir şey bulmadı'}
    baslik = (y or {}).get('baslik')
    if baslik and klip_konusma.yasak_kelime_var(baslik):
        baslik = None
    return {**sonuc, 'durum': 'tamam', 'kisa_aciklama': kisa, 'baslik': baslik}
