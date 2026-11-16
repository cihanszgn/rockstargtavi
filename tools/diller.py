"""Site, haber hattı ve sosyal yayın için tek dil kaydı: data/diller.json."""
import json
import pathlib

KAYIT = json.loads((pathlib.Path(__file__).resolve().parents[1] / 'data/diller.json').read_text(encoding='utf-8'))
DILLER = tuple(KAYIT)
HREFLANG = {d: k['hreflang'] for d, k in KAYIT.items()}
HTML_LANG = {d: k['html_lang'] for d, k in KAYIT.items()}
# Site dil kaydını genişletmek video üretimini genişletmez.
SENARYO_DILLERI = ('tr', 'en', 'es', 'fr')


def alan(ad):
    return {d: k[ad] for d, k in KAYIT.items()}


def tarih_yaz(dil, iso):
    y, a, g = (int(x) for x in iso.split('-'))
    k = KAYIT[dil]
    return k['tarih'].format(y=y, a=a, g=g, ay=k['ay'][a - 1])
