"""data/diller.json dil kaydının site derleyiciye uyumlu görünümleri."""
from diller import DILLER, KAYIT, alan
MARKA = 'CTRL+A GAME'
SAYFA = {k: {d: KAYIT[d]['sayfa'][k] for d in DILLER} for k in KAYIT['tr']['sayfa']}
ESLER = [{d: KAYIT[d]['eski'][i] for d in DILLER} for i in range(len(KAYIT['tr']['eski']))]
TEK_TR = ['acilis-saati.html', 'depolama.html', 'oyunlar.html', 'gta-3.html', 'gta-4.html', 'gta-5.html', 'gta-san-andreas.html', 'gta-vice-city.html']
GTA_SAYFALAR = alan('gta_sayfalar')
GTA_ALT_SAYI = 8
GTA_SERI = {'gta-3.html', 'gta-4.html', 'gta-5.html', 'gta-san-andreas.html', 'gta-vice-city.html'}
GTA_HEDEF = alan('gta_hedef')
GTA_TARIH = '2026-11-19'
GTA_UST = alan('gta_ust')
PLATFORMLAR = ('PS5', 'Xbox', 'Switch 2', 'PC')
AY_KISA, DIL_AD, COGUL, T = alan('ay_kisa'), alan('ad'), alan('cogul'), alan('ui')
OYUN_KLASOR, REHBER_KLASOR = alan('oyun_klasor'), alan('rehber_klasor')
PL_AD = {'Mobil': alan('mobil')}


def say(dil, n, ad):
    tekil, cogul = COGUL[dil][ad]
    return f'{n} {tekil if n == 1 else cogul}'
