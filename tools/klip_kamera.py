"""Yayıncı kamerası (facecam) bulma: klip aralığından birkaç kare örneklenir, yüz bulunur, karelerin çoğunda aynı
yerde duran tek yüz "yayıncı kamerası" sayılır ve kamera kutusu çıkarılır.

Bu modül yalnız KESİM aşamasında kullanılır (analiz önbelleğine dokunmaz). Tüm kutular KARE BOYUTUNA ORANSALDIR:
(x, y, w, h), her biri 0..1 (sol-üst köşe + genişlik/yükseklik). Mantık (kümeleme, karar, kutu hesabı) saf
Python'dur ve sentetik veriyle test edilir; yalnız `yuzleri_bul`, `kenar_ara` ve `kareleri_ornekle` OpenCV/ffmpeg ister.
Herhangi bir hata ya da kararsızlık → plan 'tek' (eski tek panel düzen; güvenli taraf).

Yüz modeli: otomasyon/modeller/face_detection_yunet_2023mar.onnx (OpenCV Zoo, YuNet, MIT lisansı;
kaynak: https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet, lisans: YUNET-LICENSE.txt).
"""
from __future__ import annotations

import math
import pathlib
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
YUZ_MODELI = ROOT / 'otomasyon' / 'modeller' / 'face_detection_yunet_2023mar.onnx'
KAMERA_SURUMU = 1   # düzen imzasına girer: algoritma değişince 'kamera' düzenli klipler güncel değil olur

# Ayar anahtarları (AYAR_VARSAYILAN'a yayin_klip.py eklenir; burası tek doğru kaynak).
VARSAYILAN = {
    'kamera_kare_sayisi': 10,        # klip aralığından örneklenen kare sayısı
    'kamera_kare_genislik': 960,     # tespit için kare genişliği (px); yükseklik orantılı
    'kamera_yuz_skor': 0.7,          # YuNet skor eşiği
    'kamera_min_kare_orani': 0.5,    # yüz karelerin en az bu kesrinde (aynı yerde) görülmeli
    'kamera_kume_mesafe': 0.6,       # aynı yüz sayılmak için en çok mesafe (yüz boyutu cinsinden)
    'kamera_en_cok_kayma': 0.6,      # kümenin merkez sapması (yüz boyutu cinsinden) bunu aşarsa yüz sabit değil
    'kamera_ikincil_orani': 0.4,     # başka bir (sabit olmayan) kümenin kare oranı bunu geçerse çelişkili sayılır
    'kamera_en_cok_alan': 0.3,       # kamera kutusu kare alanının bu kesrini aşarsa kamera zaten büyük: tek panel
    'kamera_kutu_katsayi': 7.0,      # kenar bulunamazsa kamera kutusu genişliği = yüz genişliği × bu (YuNet kutusu sıkıdır;
                                     # ölçülen pencere/yüz oranı 5.6–8.7)
    'kamera_kenar_bandi': 0.25,      # kamera yüzü kare kenarına bu kesir içindeyse (köşe/kenar pencere) kamera sayılır;
                                     # daha içerideyse (ekranın ortasında yüz) büyük çekim sayılır: tek panel
    'kamera_sabit_yuz_std': 2.0,     # yüz yaması kareler arası sapması bunun altındaysa KESİN sabit simge/çizim sayılır, yok sayılır
                                     # (canlı kamera ölçümde 10.8+, çizgi karakter sırası 0.01)
    'kamera_sabit_goreli': 0.5,      # birden çok kararlı yüz varsa: sapması en hareketli kararlı yüzün bu kesrinden azsa
                                     # (ör. sabit avatar 10.2 / canlı kamera 30.3) simge sayılır, yok sayılır
    'kamera_kucuk_kume_orani': 0.6,  # kararlı kümelerin en büyüğünün alanının bu kesrinden küçük kümeler (HUD avatarı,
                                     # oyun arayüzü yüzü) yok sayılır; benzer boyutlu yüzler (ızgara) sayılmaya devam eder
    'kamera_kutu_oran': 1.4,         # kamera panelindeki kırpmanın genişlik/yükseklik oranı
    'kamera_kenar_ara': True,        # kamera penceresinin gerçek kenarlarını da ara
    'kamera_kenar_esik': 8.0,        # kenar belirginliği eşiği (gri seviye / px; kareler arası medyan, tepe - yan ortalama)
    'kamera_icerik_en_az_alan': 0.4, # kamera dışarıda bırakılınca içerik kırpması kaynak alanının en az bu kesri kalmalı
    'kamera_icerik_pay': 1.12,       # kamera dışarı bırakılırken kutu bu katsayıyla büyütülür
}

KUTU_KENARLARI = ('x', 'y', 'w', 'h')


class KameraHatasi(RuntimeError):
    pass


# ---------------------------------------------------------------- saf mantık (OpenCV'siz)

def ayarla(ayar: dict | None) -> dict:
    a = dict(VARSAYILAN)
    for k in VARSAYILAN:
        if ayar and ayar.get(k) is not None:
            a[k] = ayar[k]
    return a


def kutu_sikistir(kutu, en_az: float = 0.02) -> tuple[float, float, float, float]:
    """Kutuyu 0..1 kare sınırlarına sıkıştırır (taşan taraf içeri çekilir, kutu çok büyükse kareye küçülür)."""
    x, y, w, h = (float(v) for v in kutu)
    w, h = min(max(w, en_az), 1.0), min(max(h, en_az), 1.0)
    x, y = min(max(x, 0.0), 1.0 - w), min(max(y, 0.0), 1.0 - h)
    return (round(x, 5), round(y, 5), round(w, 5), round(h, 5))


def kutu_gecerli(kutu) -> bool:
    try:
        x, y, w, h = (float(v) for v in kutu)
    except (TypeError, ValueError):
        return False
    return w > 0.01 and h > 0.01 and x >= -1e-6 and y >= -1e-6 \
        and x + w <= 1 + 1e-6 and y + h <= 1 + 1e-6


def kutu_orani(kutu, kare_oran: float) -> float:
    """Kutunun piksel cinsinden genişlik/yükseklik oranı (kare_oran = kare genişliği/yüksekliği)."""
    return (kutu[2] * kare_oran) / kutu[3]


def kumele(tespitler: list[list[tuple]], kare_oran: float, ayar: dict | None = None) -> list[dict]:
    """tespitler: her kare için [(cx, cy, w, h, skor), ...] (oransal, merkez + boyut). Aynı yerde duran yüzleri
    kümeler. Her küme bir karede en çok bir kez sayılır (o karedeki en yakın/en yüksek skorlu yüz).
    Dönüş: kare sayısına göre azalan sıralı küme listesi: {'kare', 'oran', 'cx','cy','w','h' (ortalama), 'kayma'}."""
    a = ayarla(ayar)
    n = len(tespitler)
    kumeler: list[dict] = []   # {'uyeler': [(kare_no, cx, cy, w, h)], 'cx','cy','sz'}

    def boyut(w, h):
        return max(w * kare_oran, h)

    for k, yuzler in enumerate(tespitler):
        for cx, cy, w, h, skor in sorted(yuzler, key=lambda t: -t[4]):
            sz = boyut(w, h)
            en_iyi, en_d = None, None
            for c in kumeler:
                if c['uyeler'] and c['uyeler'][-1][0] == k:
                    continue   # bu karede zaten bir üye var
                d = math.hypot((cx - c['cx']) * kare_oran, cy - c['cy']) / max(sz, c['sz'])
                if d <= a['kamera_kume_mesafe'] and (en_d is None or d < en_d):
                    en_iyi, en_d = c, d
            if en_iyi is None:
                kumeler.append({'uyeler': [(k, cx, cy, w, h)], 'cx': cx, 'cy': cy, 'sz': sz})
                continue
            en_iyi['uyeler'].append((k, cx, cy, w, h))
            m = len(en_iyi['uyeler'])
            en_iyi['cx'] = sum(u[1] for u in en_iyi['uyeler']) / m
            en_iyi['cy'] = sum(u[2] for u in en_iyi['uyeler']) / m
            en_iyi['sz'] = sum(boyut(u[3], u[4]) for u in en_iyi['uyeler']) / m
    sonuc = []
    for c in kumeler:
        u = c['uyeler']
        m = len(u)
        ort = lambda i: sum(t[i] for t in u) / m   # noqa: E731
        sx = math.sqrt(sum(((t[1] - c['cx']) * kare_oran) ** 2 for t in u) / m)
        sy = math.sqrt(sum((t[2] - c['cy']) ** 2 for t in u) / m)
        sonuc.append({'kare': m, 'oran': round(m / n, 3) if n else 0.0, 'cx': ort(1), 'cy': ort(2),
                      'w': ort(3), 'h': ort(4), 'kayma': round(max(sx, sy) / c['sz'], 3) if c['sz'] else 9.0})
    return sorted(sonuc, key=lambda c: -c['kare'])


def sabit_simge_mi(k: dict, ayar: dict) -> bool:
    """Yüz yaması kareler arası neredeyse hiç değişmiyorsa (ölçülmüşse) bu bir simge/çizim, canlı kamera değil."""
    s = k.get('zaman_std')
    return s is not None and s < ayar['kamera_sabit_yuz_std']


def goreli_sabit_ele(kumeler: list[dict], ayar: dict) -> list[dict]:
    """Birden çok KARARLI yüz varsa, yaması en hareketli olanın 'kamera_sabit_goreli' kesrinden az oynayanlar (sabit avatar)
    elenir. Tek kararlı yüzde eleme yok: sakin oturan canlı kamera (std ≈ 11-14) tek başına simge sayılmaz."""
    kararli = [k for k in kumeler if kararli_mi(k, ayar) and k.get('zaman_std') is not None]
    if len(kararli) < 2:
        return kumeler
    azami = max(k['zaman_std'] for k in kararli)
    atilan = [k for k in kararli if k['zaman_std'] < ayar['kamera_sabit_goreli'] * azami]
    return [k for k in kumeler if not any(k is a for a in atilan)]


def kucuk_kumeleri_ele(kumeler: list[dict], ayar: dict) -> list[dict]:
    """En büyük kararlı kümenin alanının 'kamera_kucuk_kume_orani' kesrinden küçük kümeleri (HUD avatarı) atar."""
    kararli = [k for k in kumeler if kararli_mi(k, ayar)]
    if not kararli:
        return kumeler
    en_buyuk = max(k['w'] * k['h'] for k in kararli)
    return [k for k in kumeler if k['w'] * k['h'] >= ayar['kamera_kucuk_kume_orani'] * en_buyuk]


def kenara_yakin_mi(k: dict, ayar: dict) -> bool:
    """Yüz kare kenarlarından birine 'kamera_kenar_bandi' kesri içinde mi (köşe/kenar kamera penceresi)."""
    return min(k['cx'], 1 - k['cx'], k['cy'], 1 - k['cy']) <= ayar['kamera_kenar_bandi']


def kararli_mi(k: dict, ayar: dict) -> bool:
    return k['oran'] >= ayar['kamera_min_kare_orani'] and k['kare'] >= 3 and k['kayma'] <= ayar['kamera_en_cok_kayma']


def karar_ver(kumeler: list[dict], ayar: dict | None = None) -> dict:
    """Küme listesinden düzen kararı. Dönüş: {'duzen': 'kamera'|'tek', 'neden': str, 'yuz': (cx,cy,w,h)|None}.
    'kamera' yalnız şu durumda: tek kararlı küçük yüz ve başka çelişen küme yok. Her şüphede 'tek'."""
    a = ayarla(ayar)
    if not kumeler:
        return {'duzen': 'tek', 'neden': 'yuz_yok', 'yuz': None}
    ilk = len(kumeler)
    kumeler = [k for k in kumeler if not sabit_simge_mi(k, a)]   # kesin sabit simge/çizim yok sayılır
    kumeler = goreli_sabit_ele(kumeler, a)                       # canlı kameranın yanındaki sabit avatar yok sayılır
    if not kumeler:
        return {'duzen': 'tek', 'neden': 'sabit_simge' if ilk else 'yuz_yok', 'yuz': None}
    kumeler = kucuk_kumeleri_ele(kumeler, a)                     # baskın yüzün yanındaki küçük HUD yüzleri yok sayılır
    kararli = [k for k in kumeler if kararli_mi(k, a)]
    if len(kararli) >= 2:
        return {'duzen': 'tek', 'neden': 'cok_yuz', 'yuz': None}
    if not kararli:
        zayif = kumeler[0]['oran'] >= a['kamera_ikincil_orani']
        return {'duzen': 'tek', 'neden': 'yuz_kararsiz' if zayif else 'yuz_yok', 'yuz': None}
    k = kararli[0]
    yuz = (k['cx'], k['cy'], k['w'], k['h'])
    if any(d is not k and d['oran'] >= a['kamera_ikincil_orani'] for d in kumeler):
        return {'duzen': 'tek', 'neden': 'celiskili_yuz', 'yuz': yuz}
    if not kenara_yakin_mi(k, a):
        return {'duzen': 'tek', 'neden': 'yuz_ortada', 'yuz': yuz}   # ekranın ortasında büyük çekim: kamera penceresi değil
    return {'duzen': 'kamera', 'neden': 'kucuk_kamera', 'yuz': yuz}


def merkez_x(yuz, kare_oran: float, kirpma_w: float) -> float:
    """Tek panelde kırpma merkezi: yüzü ortalar; kırpma (kare genişliğinin kesri kirpma_w) kare dışına taşmaz."""
    cx = min(max(float(yuz[0]), kirpma_w / 2), 1 - kirpma_w / 2) if kirpma_w < 1 else 0.5
    return round(cx, 4)


def kamera_kutusu_yuzden(yuz, kare_oran: float, ayar: dict | None = None) -> tuple[float, float, float, float]:
    """Kenar bulunamayınca: yüzün çevresinde orantılı kutu (genişlik = yüz × katsayı, oran = kamera_kutu_oran),
    yüz kutunun biraz üst yarısında; kare sınırlarına sıkıştırılmış."""
    a = ayarla(ayar)
    cx, cy, fw, fh = yuz
    w = fw * a['kamera_kutu_katsayi']
    h = w * kare_oran / a['kamera_kutu_oran']
    kutu = (cx - w / 2, cy - h * 0.48, w, h)
    # kare sınırına sıkıştırılınca boyut korunur (kaydırma), ama kutu kareden büyükse küçülür
    return kutu_sikistir(kutu)


def kenara_yasla(kutu, ayar: dict | None = None, pay: float = 0.05) -> tuple[float, float, float, float]:
    """Kutunun bir kenarı kare sınırına 'pay' kadar yakınsa sınıra yaslar (kamera pencereleri köşeye dayalıdır;
    aradaki ince şerit içerik panelinde kamera kalıntısı olarak görünürdü)."""
    x, y, w, h = kutu
    x1, y1 = x + w, y + h
    x, y = (0.0 if x <= pay else x), (0.0 if y <= pay else y)
    x1, y1 = (1.0 if x1 >= 1 - pay else x1), (1.0 if y1 >= 1 - pay else y1)
    return kutu_sikistir((x, y, x1 - x, y1 - y))


def kutuyu_yuze_sar(kutu, yuz, pay: float = 0.15) -> tuple[float, float, float, float]:
    """Bulunan (kenarlardan gelen) kutu yüzü kesiyorsa kutuyu yüzü (payla) kapsayacak kadar genişletir."""
    x, y, w, h = kutu
    cx, cy, fw, fh = yuz
    x0, y0 = min(x, cx - fw / 2 - fw * pay), min(y, cy - fh / 2 - fh * pay)
    x1, y1 = max(x + w, cx + fw / 2 + fw * pay), max(y + h, cy + fh / 2 + fh * pay)
    return kutu_sikistir((x0, y0, x1 - x0, y1 - y0))


def kutu_makul_mu(kutu, yuz, kare_oran: float) -> bool:
    """Kenarlardan gelen kutu makul mü: yüzü kapsar, yüzün 1.4–6 katı genişlikte, oranı 0.8–2.4."""
    if not kutu_gecerli(kutu):
        return False
    x, y, w, h = kutu
    cx, cy, fw, fh = yuz
    if not (x <= cx - fw * 0.4 and x + w >= cx + fw * 0.4 and y <= cy - fh * 0.4 and y + h >= cy + fh * 0.4):
        return False
    return 1.4 <= w / fw <= 6.0 and 0.8 <= kutu_orani(kutu, kare_oran) <= 2.4


def icerik_kirpma(kamera, kare_oran: float, panel_oran: float, ayar: dict | None = None) -> tuple[tuple, str]:
    """İçerik paneli için kaynaktan kırpılacak kutu (oransal). panel_oran: içerik panelinin genişlik/yükseklik oranı.
    Kamera kutusu (pay ile büyütülmüş) kırpmanın DIŞINDA kalacak şekilde, dört yandan (sol/sağ/üst/alt şerit atılarak)
    en geniş kırpma seçilir. Kırpma kaynak alanının en az 'kamera_icerik_en_az_alan' kesrini korumuyorsa kamera
    içerikte kalır (kutu tüm kareyi kapsar; kamera kesilmez). Dönüş: (kutu, 'disarida'|'kapsanmis')."""
    a = ayarla(ayar)
    x, y, w, h = kamera
    p = a['kamera_icerik_pay']
    cx, cy = x + w / 2, y + h / 2
    x0, y0 = max(0.0, cx - w * p / 2), max(0.0, cy - h * p / 2)
    x1, y1 = min(1.0, cx + w * p / 2), min(1.0, cy + h * p / 2)
    bolgeler = [(x1, 0.0, 1.0 - x1, 1.0),       # kameranın sağında kalan dikey şerit
                (0.0, 0.0, x0, 1.0),            # solunda
                (0.0, y1, 1.0, 1.0 - y1),       # altında
                (0.0, 0.0, 1.0, y0)]            # üstünde
    en_iyi = None
    for bx, by, bw, bh in bolgeler:
        if bw <= 0.05 or bh <= 0.05:
            continue
        # bölgeye sığan, panel_oran'lı en büyük kırpma (piksel oranına göre)
        kw = min(bw, bh * panel_oran / kare_oran)
        kh = kw * kare_oran / panel_oran
        alan = kw * kh
        if en_iyi is None or alan > en_iyi[0]:
            en_iyi = (alan, bx, by, bw, bh, kw, kh)
    if en_iyi and en_iyi[0] >= a['kamera_icerik_en_az_alan'] * _tam_kirpma_alani(kare_oran, panel_oran):
        _, bx, by, bw, bh, kw, kh = en_iyi
        # bölge içinde ortala (kamera kenarına yaslama yok: kamera dışarıda kalsın, kırpma bölge ortasında)
        return (round(bx + (bw - kw) / 2, 5), round(by + (bh - kh) / 2, 5), round(kw, 5), round(kh, 5)), 'disarida'
    return tam_kirpma(kare_oran, panel_oran), 'kapsanmis'


def _tam_kirpma_alani(kare_oran: float, panel_oran: float) -> float:
    k = tam_kirpma(kare_oran, panel_oran)
    return k[2] * k[3]


def tam_kirpma(kare_oran: float, panel_oran: float) -> tuple[float, float, float, float]:
    """Kameraya bakmadan, ortadan panel_oran'lı en büyük kırpma."""
    if panel_oran >= kare_oran:
        w, h = 1.0, kare_oran / panel_oran
    else:
        w, h = panel_oran / kare_oran, 1.0
    return (round((1 - w) / 2, 5), round((1 - h) / 2, 5), round(w, 5), round(h, 5))


def kamera_kirpma(kutu, yuz, kare_oran: float, panel_oran: float) -> tuple[float, float, float, float]:
    """Kamera paneline girecek kırpma (oransal): kamera kutusunun genişliği, panelin piksel oranına (genişlik/yükseklik)
    TAM uyan yükseklikle; yatay-dikey bozulma olmaz. Kutu o oranda gereğinden yüksekse dikey dilim yüzü ortalar
    (kutu içinde kalır, yüz kesilmez); kutu gereğinden alçaksa genişlik kısılır. yuz None ise kutu ortası."""
    x, y, w, h = kutu
    gerekli_h = w * kare_oran / panel_oran          # kutu genişliğinde panele uyan yükseklik (kare yüksekliği kesri)
    if gerekli_h <= h:
        kh, kw = gerekli_h, w
    else:
        kh, kw = h, h * panel_oran / kare_oran
    kx = x + (w - kw) / 2
    cy = yuz[1] if yuz else y + h / 2
    ky = min(max(cy - kh / 2, y), y + h - kh)
    return kutu_sikistir((kx, ky, kw, kh))


def kesim_plani(plan: dict, kare_oran: float, icerik_panel_oran: float, kamera_panel_oran: float,
                kadraj_oran: float, ayar: dict | None = None) -> dict:
    """kamera_bul/plan_kur çıktısına kesim kırpmalarını ekler (oransal kutular):
    'kamera' planı: icerik_kirpma (kamera dışarıda bırakılmış içerik kırpması), icerik_durumu, kamera_kirpma.
    'tek' planı: tek yüz büyük çekimde (kamera_buyuk, yuz_ortada) kadraj kırpma merkezi 'merkez_x' yüze kaydırılır;
    diğer nedenlerde (yüz yok, kare/çok yüz, kararsız) merkez ortada kalır (eski düzen birebir)."""
    a = ayarla(ayar)
    plan = dict(plan)
    if plan.get('duzen') == 'kamera':
        kutu = tuple(plan['kamera_kutu'])
        kirp, durum = icerik_kirpma(kutu, kare_oran, icerik_panel_oran, a)
        plan.update({'icerik_kirpma': kirp, 'icerik_durumu': durum,
                     'kamera_kirpma': kamera_kirpma(kutu, plan.get('yuz'), kare_oran, kamera_panel_oran)})
    elif plan.get('yuz') and plan.get('neden') in ('kamera_buyuk', 'yuz_ortada'):
        kw = min(1.0, kadraj_oran / kare_oran)      # kadraj genişliğinin kare genişliğine oranı
        plan['merkez_x'] = merkez_x(plan['yuz'], kare_oran, kw)
    return plan


def plan_kur(tespitler: list[list[tuple]], kare_oran: float, ayar: dict | None = None, elle_kutu=None,
             kenar_bulucu=None, zaman_std=None) -> dict:
    """Tespitlerden tam plan. elle_kutu (yayıncı kaydındaki kamera_kutu) tespiti ezer. kenar_bulucu(yuz) -> kutu|None
    (kenar bulma; yoksa None). zaman_std(kumeler) -> [float] (yüz yaması hareketi; yoksa None). Plan 'duzen' = 'kamera' | 'tek'. Hepsi JSON'a yazılabilir."""
    a = ayarla(ayar)
    kumeler = kumele(tespitler, kare_oran, a)
    if zaman_std:
        for c, z in zip(kumeler, zaman_std(kumeler)):
            c['zaman_std'] = z
    ozet = [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in c.items()} for c in kumeler[:4]]
    plan: dict = {'surum': KAMERA_SURUMU, 'kare': len(tespitler), 'kumeler': ozet}
    if elle_kutu is not None:
        if not kutu_gecerli(elle_kutu):
            raise KameraHatasi(f'kamera_kutu geçersiz (oransal x,y,w,h olmalı): {elle_kutu!r}')
        kutu = tuple(float(v) for v in elle_kutu)
        yuz = None
        if kumeler:
            ky = [k for k in kumeler if kararli_mi(k, a)]
            if ky:
                yuz = (ky[0]['cx'], ky[0]['cy'], ky[0]['w'], ky[0]['h'])
        plan.update({'duzen': 'kamera', 'neden': 'elle_kutu', 'yuz': yuz, 'kamera_kutu': kutu, 'kutu_kaynagi': 'elle'})
        return plan
    karar = karar_ver(kumeler, a)
    plan.update(karar)
    if karar['duzen'] != 'kamera':
        if karar['yuz'] and karar['neden'] == 'kamera_buyuk':
            plan['yuz'] = tuple(round(v, 4) for v in karar['yuz'])
        return plan
    yuz = karar['yuz']
    kutu, kaynak = None, 'yuz'
    if a['kamera_kenar_ara'] and kenar_bulucu is not None:
        try:
            aday = kenar_bulucu(yuz)
        except Exception:   # noqa: BLE001 - kenar bulma opsiyonel: hata olursa orantılı kutu
            aday = None
        if aday is not None:
            aday = kutuyu_yuze_sar(aday, yuz)
            if kutu_makul_mu(aday, yuz, kare_oran):
                kutu, kaynak = aday, 'kenar'
    oranli = kamera_kutusu_yuzden(yuz, kare_oran, a)
    if kutu is None:
        kutu = oranli
    else:
        # bulunan kenarlar güvenilir değil (ölçüm: pencere içindeki parlak/koyu çizgiler de tepe verir): kutu, yüzün
        # çevresindeki orantılı kutuyla BİRLEŞTİRİLİR (fazla kutu zararsız: içerik kırpması daha çok pay alır;
        # eksik kutu yüzü keser ya da kamerayı içerikte bırakır)
        kutu = kutu_sikistir((min(kutu[0], oranli[0]), min(kutu[1], oranli[1]),
                              max(kutu[0] + kutu[2], oranli[0] + oranli[2]) - min(kutu[0], oranli[0]),
                              max(kutu[1] + kutu[3], oranli[1] + oranli[3]) - min(kutu[1], oranli[1])))
    kutu = kenara_yasla(kutu, a)
    plan.update({'kamera_kutu': tuple(round(v, 5) for v in kutu), 'kutu_kaynagi': kaynak,
                 'yuz': tuple(round(v, 4) for v in yuz)})
    if kutu[2] * kutu[3] > a['kamera_en_cok_alan']:
        plan.update({'duzen': 'tek', 'neden': 'kamera_buyuk'})
        plan.pop('kamera_kutu')
        return plan
    return plan


# ---------------------------------------------------------------- OpenCV / ffmpeg bölümü

def kareleri_ornekle(ff: str, kaynak: str, bas: float, sure: float, yerel_hls: bool, n: int, genislik: int,
                     tmp: pathlib.Path, zaman_asimi: int = 600) -> list:
    """Klip aralığından n kare (eşit aralıklı, baştan ve sondan pay bırakarak) BGR numpy dizisi olarak döner.
    ffmpeg_komutu ile aynı -ss/-i sırası (yerel HLS'te -i önce)."""
    import cv2
    tmp.mkdir(parents=True, exist_ok=True)
    aralik = sure / n
    giris = (['-protocol_whitelist', 'file,http,https,tcp,tls,crypto', '-i', kaynak, '-ss', f'{bas:.3f}'] if yerel_hls
             else ['-ss', f'{bas:.3f}', '-i', kaynak])
    komut = [ff, '-hide_banner', '-loglevel', 'error', '-y', *giris, '-t', f'{sure:.3f}', '-an',
             '-vf', f'fps=1/{aralik:.4f}:start_time={aralik / 2:.4f},scale={genislik}:-2', '-frames:v', str(n),
             str(tmp / 'kare%02d.png')]
    r = subprocess.run(komut, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=zaman_asimi)
    if r.returncode != 0:
        raise KameraHatasi(f'kare örnekleme başarısız ({r.returncode}): {r.stderr[-300:]}')
    kareler = []
    for yol in sorted(tmp.glob('kare*.png')):
        im = cv2.imread(str(yol))
        if im is not None:
            kareler.append(im)
    if len(kareler) < max(3, n // 2):
        raise KameraHatasi(f'yeterli kare alınamadı: {len(kareler)}/{n}')
    return kareler


def yuzleri_bul(kareler: list, ayar: dict | None = None) -> list[list[tuple]]:
    """Her kare için [(cx, cy, w, h, skor)] (oransal). YuNet (cv2.FaceDetectorYN)."""
    import cv2
    a = ayarla(ayar)
    if not YUZ_MODELI.is_file():
        raise KameraHatasi(f'yüz modeli yok: {YUZ_MODELI}')
    if not hasattr(cv2, 'FaceDetectorYN'):
        raise KameraHatasi('OpenCV FaceDetectorYN yok')
    h0, w0 = kareler[0].shape[:2]
    det = cv2.FaceDetectorYN.create(str(YUZ_MODELI), '', (w0, h0), a['kamera_yuz_skor'], 0.3, 20)
    sonuc = []
    for im in kareler:
        h, w = im.shape[:2]
        det.setInputSize((w, h))
        _, yuzler = det.detect(im)
        satir = []
        for f in (yuzler if yuzler is not None else []):
            x, y, fw, fh, skor = float(f[0]), float(f[1]), float(f[2]), float(f[3]), float(f[-1])
            x0, y0 = max(x, 0.0), max(y, 0.0)
            x1, y1 = min(x + fw, w), min(y + fh, h)
            if x1 - x0 < 4 or y1 - y0 < 4:
                continue
            satir.append(((x0 + x1) / 2 / w, (y0 + y1) / 2 / h, (x1 - x0) / w, (y1 - y0) / h, skor))
        sonuc.append(satir)
    return sonuc


def kume_hareketi(kareler: list, kumeler: list[dict]) -> list[float]:
    """Her küme için 'zaman_std' listesi döner: yüz yamasının kareler arası piksel sapması (gri seviye). Gerçek kamera görüntüsü
    yüksek (≈20+), sabit bir simge/avatar (aynı yerde duran çizim) düşük çıkar; karar_ver düşükleri yok sayar."""
    import cv2
    import numpy as np
    h, w = kareler[0].shape[:2]
    sonuc = []
    for c in kumeler:
        x0, x1 = int(max(c['cx'] - c['w'] / 2, 0) * w), int(min(c['cx'] + c['w'] / 2, 1) * w)
        y0, y1 = int(max(c['cy'] - c['h'] / 2, 0) * h), int(min(c['cy'] + c['h'] / 2, 1) * h)
        if x1 - x0 < 3 or y1 - y0 < 3:
            sonuc.append(99.0)
            continue
        yama = np.stack([cv2.cvtColor(k[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY).astype(np.float32) for k in kareler])
        sonuc.append(round(float(yama.std(axis=0).mean()), 2))
    return sonuc


def tepe_bul(profil, bas: int, son: int, onem_pay: int = 4, onem_genis: int = 9) -> list[tuple[int, float]]:
    """[bas, son) içindeki yerel tepeler: (indeks, belirginlik). Belirginlik = tepe değeri - iki yandaki
    (onem_pay..onem_genis) px'in ortalaması: ince/keskin çizgi yüksek, geniş yumuşak kenar düşük çıkar."""
    n = len(profil)
    sonuc = []
    for i in range(max(bas, onem_genis), min(son, n - onem_genis)):
        if profil[i] < profil[i - 1] or profil[i] < profil[i + 1]:
            continue
        sol = sum(profil[i - onem_genis:i - onem_pay]) / (onem_genis - onem_pay)
        sag = sum(profil[i + onem_pay + 1:i + onem_genis + 1]) / (onem_genis - onem_pay)
        sonuc.append((i, float(profil[i]) - (sol + sag) / 2))
    return sonuc


def kenar_sec(profil, merkez: float, uzak_min: float, uzak_maks: float, yon: int, sinir: int, boyut: int,
              esik: float, bant: float):
    """Bir kenar için en belirgin keskin çizgiyi seçer. yon = -1 (sol/üst) ya da +1 (sağ/alt); merkez yüz merkezi (px);
    uzaklıklar yüze göre px. Kare sınırı da aday: yüz sınıra 'bant' kesri içindeyse sınır adayı (belirginlik 1.5×eşik)
    olur, kamera pencereleri köşeye/kenara dayalı olur ve sınırda gradyan yoktur. Dönüş: (konum px, belirginlik) ya da None."""
    a, b = merkez + yon * uzak_maks, merkez + yon * uzak_min
    bas, son = int(min(a, b)), int(max(a, b)) + 1
    adaylar = [(i, v) for i, v in tepe_bul(profil, max(bas, 0), min(son, len(profil))) if v >= esik]
    sinira_uzak = merkez if yon < 0 else boyut - merkez
    if sinira_uzak / boyut <= bant and sinira_uzak <= uzak_maks:
        adaylar.append((sinir, esik * 1.5))
    return max(adaylar, key=lambda t: t[1]) if adaylar else None


def kenar_ara(kareler: list, yuz, ayar: dict | None = None):
    """Kamera penceresinin gerçek kenarlarını arar: kareler arası MEDYAN kenar gücü (sabit sınır korunur, oyun
    içeriğinin değişen kenarları silinir); her yönde (sol, sağ, üst, alt) yüzden dışa en keskin sabit çizgi,
    yüz kare sınırına yakınsa sınır da aday. Dört kenarın hepsi bulunmazsa None (çağıran orantılı kutuya düşer).
    Dönüş: oransal (x, y, w, h)."""
    import cv2
    import numpy as np
    a = ayarla(ayar)
    if len(kareler) < 4:
        return None
    h, w = kareler[0].shape[:2]
    gx_l, gy_l = [], []
    for im in kareler:
        g = cv2.GaussianBlur(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), (3, 3), 0).astype(np.float32)
        gx_l.append(np.abs(cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)) / 8.0)
        gy_l.append(np.abs(cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)) / 8.0)
    gx, gy = np.median(np.stack(gx_l), axis=0), np.median(np.stack(gy_l), axis=0)
    cx, cy, fw, fh = yuz[0] * w, yuz[1] * h, yuz[2] * w, yuz[3] * h
    y_a, y_b = int(max(cy - fh * 0.9, 0)), int(min(cy + fh * 0.9, h))
    x_a, x_b = int(max(cx - fw * 0.9, 0)), int(min(cx + fw * 0.9, w))
    sut = gx[y_a:y_b, :].mean(axis=0)
    satir = gy[:, x_a:x_b].mean(axis=1)
    e, bant = a['kamera_kenar_esik'], a['kamera_kenar_bandi']
    sol = kenar_sec(sut, cx, fw * 0.75, fw * 10, -1, 0, w, e, bant)
    sag = kenar_sec(sut, cx, fw * 0.75, fw * 10, +1, w, w, e, bant)
    ust = kenar_sec(satir, cy, fh * 0.75, fh * 6, -1, 0, h, e, bant)
    alt = kenar_sec(satir, cy, fh * 0.75, fh * 6, +1, h, h, e, bant)
    if None in (sol, sag, ust, alt):
        return None
    return (sol[0] / w, ust[0] / h, (sag[0] - sol[0]) / w, (alt[0] - ust[0]) / h)


def kamera_bul(ff: str, kaynak: str, bas: float, sure: float, yerel_hls: bool, ayar: dict | None = None,
               elle_kutu=None, kare_oran: float = 16 / 9) -> dict:
    """Klip başına bir kez: kare örnekle, yüz bul, planı kur. Hata olursa KameraHatasi (çağıran 'tek'e düşer)."""
    a = ayarla(ayar)
    with tempfile.TemporaryDirectory(prefix='kamera-') as t:
        kareler = kareleri_ornekle(ff, kaynak, bas, sure, yerel_hls, int(a['kamera_kare_sayisi']),
                                   int(a['kamera_kare_genislik']), pathlib.Path(t))
        h, w = kareler[0].shape[:2]
        oran = w / h
        tesp = yuzleri_bul(kareler, a)
        plan = plan_kur(tesp, oran, a, elle_kutu, kenar_bulucu=lambda yuz: kenar_ara(kareler, yuz, a),
                        zaman_std=lambda kumeler: kume_hareketi(kareler, kumeler))
        plan['kare_oran'] = round(oran, 4)
        return plan
