import {yaziGenisligi} from './olcu';
import {D, GECIS, mutlak, PENCERE} from './tema';
import type {Engel, KameraAnahtari, Sahne} from './tipler';
import {cikis, girisCikis, ilerle, karistir, sinirla} from './zaman';

// Sahne kamerası: pencereler bir "tuval" üstünde durur, kamera anlatıma göre yaklaşır ve kayar.
// Koordinatlar maskot ve engellerle aynı: x kare koordinatı, y ana pencerenin iç üst kenarına göre.
// Ekran = (nokta - odak) * k + sahne ortası.
export type Kamera = {k: number; x: number; y: number};
export type Tuval = {ust: number; alt: number};

const G = D.guvenli;
const SAHNE = D.sahne;
const IC_UST = PENCERE.y + PENCERE.cerceve;
export const ORTA = {x: 480, y: (SAHNE.ust + SAHNE.alt) / 2};
export const SAHNE_YARI = (SAHNE.alt - SAHNE.ust) / 2;
export const DUZ: Kamera = {k: 1, x: ORTA.x, y: ORTA.y - IC_UST};
export const KAMERA_GECIS = 0.3;
// İki kamera hareketi arası en az bu kadar: daha sık oynayan kamera titreşim gibi görünür.
const EN_SIK = 0.6;
// Sahne değişimi: eski tuval yukarı kayar, yenisi alttan gelir.
export const KAYMA = 860;

const K_EN_AZ = 0.9;
const K_EN_COK = 1.1;
const K_ADIM = 0.005;
// Pencere içeriğinin kare x aralığı (iç 40..796): okunan her yazı bu aralıkta.
const ICERIK = {sol: mutlak(40, 0).x, sag: mutlak(796, 0).x};
// Yazının güvenli sınırlara kalan payı: geçişte k ile odak birlikte değişir, ara karelerde yazı iki uçtaki duruştan
// birkaç piksel öteye gidebilir.
const PAY = 8;
// Sahne içindeki girişler (ikinci panel alttan 90 px kayarak gelir) yazıyı duruştaki yerinin bu kadar altında gösterir.
const GIRIS_PAYI = 90;
// Geçişin ara karelerinden örneklenenler.
const ARA = [0.25, 0.5, 0.75];

// Ana pencerenin başlık çubuğundaki yazı (simge iç x 24'te, ad 150'de başlar). Kamera ve maskot ikisi de kaçınır.
export const baslikEngeli = (s: Sahne): Engel => {
  const metin = (s.veri.pencere as string) ?? '';
  const w = metin ? Math.min(520, yaziGenisligi(metin, 26, 700, 0.08) * D.altyazi.pay) : 0;
  return {x0: mutlak(24, 0).x, x1: mutlak(150 + w, 0).x, y0: 20, y1: 54};
};

const odakY = (y: number, k: number, tuval: Tuval) => {
  const yari = SAHNE_YARI / k;
  const az = tuval.ust - 30 + yari;
  const cok = tuval.alt + 30 - yari;
  return az <= cok ? sinirla(y, az, cok) : (tuval.ust + tuval.alt) / 2;
};

// Kameranın bir görünüşü: duruşu ve o sırada tuvalin dikey kayma aralığı (sahne girişi/çıkışı).
type Gorus = {k: number; y: number; dyAz: number; dyCok: number};

// Engel bu görünüşte sağdaki uygulama düğmelerinin bandına (ekranda y > ray_y, sahnenin altına kadar) girebilir mi?
const bantta = (e: Engel, g: Gorus) => {
  const y0 = (e.y0 - g.y) * g.k + ORTA.y;
  const y1 = (e.y1 - g.y) * g.k + ORTA.y;
  // Kayma aralığında (dyAz..dyCok) engelin bandı kestiği bir dy var mı: dy > alt sınır ve dy < üst sınır.
  const az = G.ray_y - GIRIS_PAYI - y1;
  const cok = SAHNE.alt - y0;
  return az < cok && az < g.dyCok && cok > g.dyAz;
};

// Yakınlık 1/k üzerinden karışır: odak ve 1/k doğrusal değişince yatay sınırlar (x <= sol + pay/k gibi) geçişin her
// karesinde, iki uçtaki duruşta sağlandıkları için kendiliğinden sağlanır.
const kKaristir = (a: number, b: number, u: number) => 1 / karistir(1 / a, 1 / b, u);

const ara = (a: {k: number; y: number}, b: {k: number; y: number}, u: number, dyAz = 0, dyCok = 0): Gorus => ({
  k: kKaristir(a.k, b.k, u),
  y: karistir(a.y, b.y, u),
  dyAz,
  dyCok,
});

type Komsu = {onceki?: Kamera; sonraki?: Kamera; ilk: boolean; son: boolean; cikista: boolean};

// Bir duruşu güvenli alana sığdırır. Kare: içerik (ve dolayısıyla her yazı) yatayda güvenli dikdörtgende kalır.
// Ray: duruşta, komşu duruşlara geçerken ya da sahne kayarken banda girebilecek yazıların sağ ucu ray_x'i geçmez.
// İkisi birlikte sağlanamazsa yakınlık azalır; y tuvalin dışına 30 px'ten fazla bakmaz.
const yerlestir = (a: KameraAnahtari, tuval: Tuval, engeller: Engel[], n: Komsu): Kamera => {
  const ust = Math.min(K_EN_COK, Math.max(K_EN_AZ, a.k));
  let son: Kamera | undefined;
  for (let k = ust; k >= K_EN_AZ - 1e-9; k -= K_ADIM) {
    const y = odakY(a.y, k, tuval);
    const bu = {k, y};
    const gorusler: Gorus[] = [{k, y, dyAz: 0, dyCok: 0}];
    // Sahnenin ilk duruşu tuval alttan gelirken, son duruşu yukarı kayarken görünür (ilk ve son sahne de aynı
    // sayılır: sahne bileşenleri ile video aynı yolu bulmalı).
    if (n.ilk) gorusler.push({k, y, dyAz: 0, dyCok: KAYMA});
    if (n.son) gorusler.push({k, y, dyAz: -KAYMA, dyCok: 0});
    if (n.onceki) for (const u of ARA) gorusler.push(ara(n.onceki, bu, u, n.cikista ? -KAYMA : 0));
    if (n.sonraki) for (const u of ARA) gorusler.push(ara(bu, n.sonraki, u));
    let sag = -Infinity;
    for (const e of engeller) if (e.x1 > sag && gorusler.some((g) => bantta(e, g))) sag = e.x1;
    const az = Math.max(ICERIK.sag - (G.sag - PAY - ORTA.x) / k, sag - (G.ray_x - PAY - ORTA.x) / k);
    const cok = ICERIK.sol + (ORTA.x - G.sol - PAY) / k;
    son = {k, x: (az + cok) / 2, y};
    if (az <= cok) return {k, x: sinirla(a.x, az, cok), y};
  }
  return son ?? {...DUZ};
};

// Anahtarlar sıraya dizilir, birbirine çok yakın olanlar birleşir (sonraki hedef kazanır), her biri güvenli alana
// sığdırılır. Komşu duruşlar birbirini etkilediği için sığdırma birkaç tur yinelenir.
export const kameraYolu = (anahtarlar: KameraAnahtari[], tuval: Tuval, s: Sahne, sahneEngelleri: Engel[]): KameraAnahtari[] => {
  const engeller = [baslikEngeli(s), ...sahneEngelleri];
  const sirali = [...anahtarlar].filter((a) => Number.isFinite(a.t)).sort((a, b) => a.t - b.t);
  const ham: KameraAnahtari[] = [];
  for (const a of sirali) {
    const b = {...a, t: Math.max(s.bas, a.t)};
    const onceki = ham[ham.length - 1];
    if (onceki && b.t - onceki.t < EN_SIK) ham[ham.length - 1] = {...b, t: onceki.t};
    else ham.push(b);
  }
  if (!ham.length) ham.push({...DUZ, t: s.bas});
  let yol: Kamera[] = ham.map((a) => ({k: Math.min(K_EN_COK, Math.max(K_EN_AZ, a.k)), x: a.x, y: odakY(a.y, a.k, tuval)}));
  for (let tur = 0; tur < 3; tur++) {
    yol = ham.map((a, i) =>
      yerlestir(a, tuval, engeller, {
        onceki: yol[i - 1],
        sonraki: yol[i + 1],
        ilk: i === 0,
        son: i === ham.length - 1,
        cikista: i === ham.length - 1 && a.t + KAMERA_GECIS > s.bit,
      }),
    );
  }
  return ham.map((a, i) => ({...a, ...yol[i]}));
};

export const kameraAn = (yol: KameraAnahtari[], t: number): Kamera => {
  let st: Kamera = {k: yol[0].k, x: yol[0].x, y: yol[0].y};
  for (let i = 1; i < yol.length && yol[i].t <= t; i++) {
    const u = girisCikis(ilerle(t, yol[i].t, KAMERA_GECIS));
    st = {k: kKaristir(st.k, yol[i].k, u), x: karistir(st.x, yol[i].x, u), y: karistir(st.y, yol[i].y, u)};
  }
  return st;
};

// Sahne değişimi: eski tuval yukarı kayar, yenisi alttan gelir (ilk sahne hafifçe yükselerek belirir).
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
