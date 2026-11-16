import {GECIS, PENCERE} from './tema';
import type {KameraAnahtari, Sahne} from './tipler';
import {cikis, girisCikis, ilerle, karistir, sinirla} from './zaman';

// Sahne kamerası: pencereler bir "tuval" üstünde durur, kamera anlatıma göre yaklaşır ve kayar.
// Koordinatlar maskot ve engellerle aynı: x kare koordinatı, y ana pencerenin iç üst kenarına göre.
// Ekran = (nokta - odak) * k + sahne ortası.
export type Kamera = {k: number; x: number; y: number};
export type Tuval = {ust: number; alt: number};

const IC_UST = PENCERE.y + PENCERE.cerceve;
export const ORTA = {x: 480, y: 730};
export const DUZ: Kamera = {k: 1, x: ORTA.x, y: ORTA.y - IC_UST};
export const KAMERA_GECIS = 0.3;
// İki kamera hareketi arası en az bu kadar: daha sık oynayan kamera titreşim gibi görünür.
const EN_SIK = 0.6;
export const SAHNE_YARI = 420;

// İçerik (kare x 102..858) yaklaşınca da 24..900 arasında kalır: sağdaki uygulama düğmeleri yazıyı örtmez.
const sinirlaKamera = (a: Kamera, tuval: Tuval): Kamera => {
  const k = sinirla(a.k, 0.9, 1.1);
  const xEnAz = 858 - (900 - ORTA.x) / k;
  const xEnCok = 102 + (ORTA.x - 24) / k;
  const x = xEnAz <= xEnCok ? sinirla(a.x, xEnAz, xEnCok) : (xEnAz + xEnCok) / 2;
  const yari = SAHNE_YARI / k;
  const yEnAz = tuval.ust - 30 + yari;
  const yEnCok = tuval.alt + 30 - yari;
  const y = yEnAz <= yEnCok ? sinirla(a.y, yEnAz, yEnCok) : (tuval.ust + tuval.alt) / 2;
  return {k, x, y};
};

// Anahtarlar sıraya dizilir, birbirine çok yakın olanlar birleşir (sonraki hedef kazanır), her biri tuvale sığdırılır.
export const kameraYolu = (anahtarlar: KameraAnahtari[], tuval: Tuval, bas: number): KameraAnahtari[] => {
  const sirali = [...anahtarlar].filter((a) => Number.isFinite(a.t)).sort((a, b) => a.t - b.t);
  const yol: KameraAnahtari[] = [];
  for (const a of sirali) {
    const s = {...a, ...sinirlaKamera(a, tuval), t: Math.max(bas, a.t)};
    const onceki = yol[yol.length - 1];
    if (onceki && s.t - onceki.t < EN_SIK) yol[yol.length - 1] = {...s, t: onceki.t};
    else yol.push(s);
  }
  if (!yol.length) yol.push({...sinirlaKamera(DUZ, tuval), t: bas});
  return yol;
};

export const kameraAn = (yol: KameraAnahtari[], t: number): Kamera => {
  let st: Kamera = {k: yol[0].k, x: yol[0].x, y: yol[0].y};
  for (let i = 1; i < yol.length && yol[i].t <= t; i++) {
    const u = girisCikis(ilerle(t, yol[i].t, KAMERA_GECIS));
    st = {k: karistir(st.k, yol[i].k, u), x: karistir(st.x, yol[i].x, u), y: karistir(st.y, yol[i].y, u)};
  }
  return st;
};

// Sahne değişimi: eski tuval yukarı kayar, yenisi alttan gelir (ilk sahne hafifçe yükselerek belirir).
export const KAYMA = 860;
export const sahneKaymasi = (sahneler: Sahne[], i: number, t: number) => {
  const s = sahneler[i];
  let dy = 0;
  let saydam = 1;
  if (i === 0) {
    const u = cikis(ilerle(t, 0, 0.3));
    dy += 90 * (1 - u);
    saydam = u;
  } else {
    dy += KAYMA * (1 - girisCikis(ilerle(t, s.bas, GECIS)));
  }
  if (i < sahneler.length - 1) dy -= KAYMA * girisCikis(ilerle(t, s.bit, GECIS));
  return {dy, saydam};
};

export type Ekran = (sahne: number, t: number) => Kamera & {dy: number};

// Tuval noktasını ekrana çevirir (y ana pencere içine göre).
export const ekranda = (e: Kamera & {dy: number}, x: number, yIc: number) => ({
  x: (x - e.x) * e.k + ORTA.x,
  y: (yIc - e.y) * e.k + ORTA.y + e.dy,
});

export const IC_UST_Y = IC_UST;
