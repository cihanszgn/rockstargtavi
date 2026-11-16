"""Yeni dillerin isteğe bağlı senaryolarını mevcut doğrulayıcıya uyarlar.

Video motoru dosyaları ve üretim kapsamı değişmez. Uyarlama yalnız senaryo
denetimi süresince geçerlidir; mevcut dört dilin kurallarına dokunulmaz.
"""
from contextlib import contextmanager
import re
from diller import KAYIT, SENARYO_DILLERI


@contextmanager
def dogrulama_dili(motor, dil):
    if dil in SENARYO_DILLERI:
        yield
        return
    aylar, coz = motor.AYLAR, motor.tarih_coz

    def tarih_coz(metin, haber_tarihi, lang):
        if lang == 'zh':
            m = re.fullmatch(r'(?:(\d{4})年)?(\d{1,2})月(\d{1,2})日', metin.strip())
            if m:
                yil, ay, gun = m.groups()
                if not 1 <= int(ay) <= 12:
                    return None
                return coz(f'{gun} {aylar["en"][int(ay) - 1]}' + (f' {yil}' if yil else ''), haber_tarihi, 'en')
        # Almanca günün noktasını çıkar; ay adları ortak kayıttan gelir.
        if lang == 'de':
            metin = re.sub(r'^(\d{1,2})\.\s*', r'\1 ', metin)
        return coz(metin, haber_tarihi, lang)

    motor.AYLAR = {**aylar, dil: [x.casefold() for x in KAYIT[dil]['ay']]}
    motor.tarih_coz = tarih_coz
    try:
        yield
    finally:
        motor.AYLAR, motor.tarih_coz = aylar, coz
