import duzen from './olcu/duzen.json';

// Sitenin style.css renkleri (koyu tema). Site değişirse burası da güncellenir.
export const R = {
  zemin: '#0B1322',
  yuzey: '#121C30',
  yuzey2: '#1A2740',
  cizgi: '#2A3958',
  yazi: '#E9EEF8',
  soluk: '#9AA8C3',
  secim: '#3B6CF6',
  secimKoyu: '#2447B8',
  baglanti: '#8DB0FF',
  nane: '#3DDC97',
  kehribar: '#F5B83D',
  kirmizi: '#FF6B6B',
  pembe: '#FF6BB5',
  tusUst: '#1E2C47',
  tusAlt: '#060B15',
  koyuYazi: '#0A1430',
};

export const TUR_RENK: Record<string, string> = {
  haber: '#3BC9FF',
  guncelleme: '#B39DFF',
  indirim: '#FF6BB5',
  ucretsiz: '#3DDC97',
  cikis: '#FFB020',
};

export const PLATFORM_RENK: Record<string, string> = {
  ps: '#5B9BFF',
  xbox: '#4ADE80',
  switch: '#FF5A5F',
  pc: '#FF9F43',
  mobil: '#C084FC',
  diger: '#9AA8C3',
};

export const SIMGE_RENK: Record<string, string> = {
  haber: '#3BC9FF',
  guncelleme: '#B39DFF',
  indirim: '#FF6BB5',
  ucretsiz: '#3DDC97',
  cikis: '#FFB020',
  kaynak: '#8DB0FF',
  liste: '#F5B83D',
  yama: '#B39DFF',
  takvim: '#FF6B6B',
  fiyat: '#3DDC97',
  platform: '#FF9F43',
  site: '#3B6CF6',
};

export const YAZI = "Archivo, 'Arial Narrow', sans-serif";

export const D = duzen;

// Sahne değişiminde eski pencerenin yukarı kayıp yenisinin alttan geldiği süre (sn).
export const GECIS = 0.55;

const S = duzen.sahne;
export const PENCERE = {
  x: S.sol,
  y: S.pencere_ust,
  w: S.genislik,
  h: 780,
  cerceve: 2,
  cubuk: S.baslik_cubugu,
  ic: S.ic_bosluk,
};

// Pencere içi göreli koordinatı kare koordinatına çevirir (çerçeve kalınlığı dahil).
export const mutlak = (x: number, y: number) => ({x: PENCERE.x + PENCERE.cerceve + x, y: PENCERE.y + PENCERE.cerceve + y});

export const tusGolge = (derinlik: number, basili = 0) =>
  `0 ${Math.round(derinlik * (1 - basili) * 10) / 10}px 0 ${R.tusAlt}`;
