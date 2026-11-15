import type {VideoProps} from './tipler';

// Studio'da açılınca görünen küçük, sessiz örnek. Gerçek videolar tools/video_uret.py'nin ürettiği props ile çizilir.
export const ORNEK: VideoProps = {
  surum: 1,
  id: 'ornek',
  dil: 'tr',
  fps: 30,
  boyut: [1080, 1920],
  ses: '',
  sure: 9,
  haber: {
    oyun: 'Örnek Oyun',
    tur: 'haber',
    tur_etiket: 'HABER',
    platformlar: [{ad: 'PC', renk: 'pc'}],
    tarih: '2026-11-16',
    tarih_metin: '16 KASIM 2026',
  },
  sahneler: [
    {
      sablon: 'baslik',
      bas: 0,
      bit: 4.5,
      veri: {ust_etiket: 'ÖRNEK', baslik: 'Örnek başlık burada duruyor', vurgu: [], tuslar: ['Ö', 'O'], pencere: 'ÖRNEK OYUN'},
      alt_kart: {simge: 'haber', baslik: 'ÖRNEK OYUN', alt: 'ÖRNEK ALT YAZI', baslik_olcek: 1, alt_olcek: 1},
      maskot: {hareket: 'bas'},
      altyazi: [],
    },
    {
      sablon: 'kapanis',
      bas: 4.5,
      bit: 9,
      veri: {cagri: 'Ayrıntılar sitede', alt: 'Kaynak haberde.', adres: 'ctrl-agame.com', pencere: 'ctrl-agame.com', goster: 4.95},
      alt_kart: {simge: 'site', baslik: 'CTRL+A GAME', alt: 'CTRL-AGAME.COM', baslik_olcek: 1, alt_olcek: 1},
      maskot: {hareket: 'bas'},
      altyazi: [],
    },
  ],
  kelimeler: [
    {k: 'Örnek', b: 0.2, s: 0.7},
    {k: 'başlık', b: 0.7, s: 1.2},
    {k: 'burada', b: 1.2, s: 1.7},
    {k: 'duruyor.', b: 1.7, s: 2.4},
  ],
  parcalar: [{b: 0.2, s: 2.4, bitis: 3.4, satirlar: [[0, 1, 2, 3]], olcek: 1}],
};
