import {baslikEngeli, type Ekran, ekranda, IC_UST_Y} from './kamera';
import {SABLON} from './sahne';
import {D, GECIS} from './tema';
import type {Engel, Haber, Nokta, Sahne} from './tipler';
import {ilerle} from './zaman';

// Maskotun bütün video boyunca nerede duracağını önceden planlar. Çizim (bilesen/Maskot.tsx) bu plana bakar.
// Duraklar tuval koordinatında (x kare, y ana pencere içi + IC_UST_Y); ekrana kamera ve sahne kayması çevirir.
// Sahne değişiminde maskot eski pencereyle birlikte kayıp gider, yeni sahnenin ilk durağında belirir:
// hızla kayan iki pencerenin yazıları arasından uçmaz.
export type Durak = {
  var: number; // konduğu an
  kalk: number; // sıçradığı an (son durakta sonsuz)
  x: number; // gövde ortası
  y: number; // ayak hizası
  eylem: 'bas' | 'dur' | 'tara';
  x2: number; // 'tara' yürüyüşünün bittiği x
  sure: number; // durakta yapılan eylemin süresi
  sahne: number;
  sahneBit: number; // pencerenin kayıp gitmeye başladığı an (son sahnede sonsuz)
  tepe: number; // buraya gelen sıçramanın yay yüksekliği (tuval pikseli)
};

const M = D.maskot;
const ARA = 0.45; // aynı sahnede iki konuş arası en az
const ATLAMA = 0.42; // sahne içi sıçrama süresi
const TUNEK_X = 820; // pencerenin sağ üst kenarı: dayanak noktası yoksa buraya konar
const GOVDE_YARI = 42; // görünen gövdenin yarı genişliği (çerçeve pikselleri hariç)
export const TAVAN = D.sahne.ust - 10; // uçarken bile sahnenin üstündeki marka şeridine çıkmaz
// Marka şeridinin yazısı x 600 civarında biter; sağı boştur, maskot orada şeride çıkabilir ama uygulamanın üstteki
// arama/menü simgelerinin (güvenli alanın üstü) altında kalır.
const SERIT_BOS_X = 640;
const tavan = (xSol: number) => (xSol > SERIT_BOS_X ? D.guvenli.ust : TAVAN);
const ORNEK = 24; // bir sıçrama yayında denetlenen nokta sayısı

const ayak = (yRel: number) => IC_UST_Y + yRel;
const xSinirla = (x: number) => Math.min(M.x_en_cok, Math.max(M.x_en_az, x));

const eylemCevir = (n: Nokta, hareket: string, sablon: string): Nokta => {
  if (n.eylem === 'tara' && (sablon !== 'kaynak' || hareket !== 'tara')) return {...n, eylem: 'dur', x2: undefined, sure: 0};
  if (hareket === 'zipla' && n.eylem === 'bas') return {...n, eylem: 'dur'};
  return n;
};

// Gövde bir engelle kesişiyor mu? Ayak hizasındaki zemin öğesi engel sayılmaz.
const carpar = (xa: number, xb: number, ayakY: number, engeller: Engel[], k = 1) =>
  engeller.some((e) => !e.kamera && xb + GOVDE_YARI * k > e.x0 && xa - GOVDE_YARI * k < e.x1 && ayakY - M.yukseklik * k - 2 < e.y1 && ayakY > e.y0 + 2);

// Maskot hiçbir yazıyı örtmez: nokta yazıya biniyorsa zemini üstünde en yakın boş yere kayar, yer yoksa atlanır.
const yerlestir = (n: Nokta, engeller: Engel[]): Nokta | null => {
  const x2 = n.x2 ?? n.x;
  const bos = (dx: number) => !carpar(Math.min(n.x, x2) + dx, Math.max(n.x, x2) + dx, n.y, engeller);
  if (bos(0)) return n;
  if (!n.zemin || n.eylem === 'tara') return null;
  const a = Math.max(M.x_en_az, n.zemin[0] + 30);
  const b = Math.min(M.x_en_cok, n.zemin[1] - 30);
  for (let d = 8; d <= b - a; d += 8) {
    for (const dx of [d, -d]) {
      const x = n.x + dx;
      if (x >= a && x <= b && bos(dx)) return {...n, x, x2: x};
    }
  }
  return null;
};

const kolay = (u: number) => 0.5 * (u + (u < 0.5 ? 2 * u * u : 1 - Math.pow(-2 * u + 2, 2) / 2));

// Sıçrama yayındaki yer: yol tuvalde çizilir, kamerayla birlikte ekrana taşınır.
const ucus = (d: Durak, n: Durak, u: number, H: number, ekran: Ekran) => {
  const e = ekran(n.sahne, d.kalk + u * (n.var - d.kalk));
  const x = d.x2 + (n.x - d.x2) * kolay(u);
  const taban = d.y + (n.y - d.y) * u;
  const p = ekranda(e, x, taban - 4 * H * u * (1 - u) - IC_UST_Y);
  return {x: p.x, y: p.y, k: e.k, golgeY: ekranda(e, x, taban - IC_UST_Y).y, tuvalY: taban - 4 * H * u * (1 - u), tuvalX: x};
};

export const planla = (sahneler: Sahne[], haber: Haber, ekran: Ekran): Durak[] => {
  const engeller: Engel[][] = sahneler.map((s) => (SABLON[s.sablon] ? [baslikEngeli(s), ...SABLON[s.sablon].engeller(s, haber)] : []));
  const bitler = sahneler.map((s, i) => (i === sahneler.length - 1 ? Infinity : s.bit));
  const duraklar: Durak[] = [{var: 0.45, kalk: Infinity, x: TUNEK_X, y: ayak(0), eylem: 'dur', x2: TUNEK_X, sure: 0, sahne: 0, sahneBit: bitler[0] ?? Infinity, tepe: 0}];
  sahneler.forEach((s, i) => {
    const sablon = SABLON[s.sablon];
    if (!sablon) return;
    const hareket = s.maskot?.hareket || sablon.hareket;
    const enErken = i === 0 ? 0.9 : s.bas + GECIS + 0.12;
    const enGec = s.bit - 0.12;
    let adaylar = sablon
      .noktalar(s, haber)
      .map((n) => eylemCevir(n, hareket, s.sablon))
      .map((n) => yerlestir(n, engeller[i]))
      .filter((n): n is Nokta => n !== null)
      .map((n) => ({...n, t: Math.max(n.t, enErken)}))
      .sort((a, b) => a.t - b.t);
    if (hareket === 'bekle') adaylar = adaylar.slice(0, 1).map((n) => ({...n, eylem: 'dur' as const}));

    const kabul: Durak[] = [];
    const sonrakiIcinEnErken = () => {
      const onceki = kabul.length ? kabul[kabul.length - 1] : duraklar[duraklar.length - 1];
      return kabul.length ? onceki.var + onceki.sure + ARA : Math.max(onceki.var + onceki.sure + 0.05, enErken);
    };
    const ekle = (n: Nokta, sure: number) =>
      kabul.push({var: n.t, kalk: Infinity, x: xSinirla(n.x), y: ayak(n.y), eylem: n.eylem, x2: xSinirla(n.x2 ?? n.x), sure, sahne: i, sahneBit: bitler[i], tepe: 0});

    for (const n of adaylar) {
      const sure = Math.max(0, n.sure ?? 0);
      if (n.t < sonrakiIcinEnErken() || n.t + sure > enGec) continue;
      // İlk dayanak geç geliyorsa önce pencerenin kenarında belir: sahne boşken maskot kaybolmuş görünmesin.
      if (!kabul.length && n.t > enErken + 0.9) ekle({t: enErken, x: TUNEK_X, y: 0, eylem: 'dur'}, 0);
      ekle(n, sure);
    }
    if (!kabul.length) {
      const t0 = Math.max(enErken, sonrakiIcinEnErken());
      if (t0 <= enGec) ekle({t: t0, x: TUNEK_X, y: 0, eylem: 'dur'}, 0);
    }
    duraklar.push(...kabul);
  });

  // Kalkış anları: sahne içinde konuştan hemen önce. Sahne değişiminde kalkış yok (maskot pencereyle gider).
  const kalklar = () => {
    duraklar.forEach((d, k) => {
      const n = duraklar[k + 1];
      if (!n) d.kalk = Infinity;
      else if (n.sahne === d.sahne) d.kalk = Math.max(d.var + d.sure, n.var - ATLAMA);
      else d.kalk = n.var;
    });
  };
  kalklar();

  // Kamera yaklaşıp kayınca durak sahnenin dışında kalmasın: durduğu süre boyunca ayakları ve gövdesi görünür olmalı.
  const gorunur = (d: Durak) => {
    const son = Math.min(d.kalk, d.var + 8, sahneler[d.sahne].bit) - 0.02;
    const adim = Math.max(0.05, Math.min(0.2, son - d.var));
    for (let tau = d.var; tau <= son + 1e-6; tau += adim) {
      const e = ekran(d.sahne, tau);
      for (const x of [d.x, d.x2]) {
        const p = ekranda(e, x, d.y - IC_UST_Y);
        const sol = p.x - GOVDE_YARI * e.k;
        const ustSinir = sol > SERIT_BOS_X ? tavan(sol) : D.sahne.ust + 6;
        const sag = p.x + GOVDE_YARI * e.k;
        if (p.y > D.sahne.alt - 6 || p.y < D.sahne.ust + 20 || p.y - M.yukseklik * e.k < ustSinir || sol < 8 || sag > 1072) return false;
        // Sağdaki uygulama düğmelerinin altına girmez.
        if (p.y > D.guvenli.ray_y && sag > D.guvenli.ray_olculen_x) return false;
      }
    }
    return true;
  };
  for (let k = duraklar.length - 1; k >= 1; k--) {
    if (!gorunur(duraklar[k])) {
      duraklar.splice(k, 1);
      kalklar();
    }
  }

  // Sıçrama yolu hiçbir yazıya değmez: yay tuvalde örneklenir, değiyorsa yükseklik değişir; hiçbiri olmuyorsa varış
  // durağı atlanır. Ekranda sahnenin üstüne (marka şeridi) taşan yay da kabul edilmez.
  const temiz = (d: Durak, n: Durak, H: number) => {
    for (let j = 1; j < ORNEK; j++) {
      const p = ucus(d, n, j / ORNEK, H, ekran);
      if (p.y - M.yukseklik * p.k < tavan(p.x - GOVDE_YARI * p.k)) return false;
      if (carpar(p.tuvalX, p.tuvalX, p.tuvalY - IC_UST_Y, engeller[n.sahne])) return false;
    }
    return true;
  };
  const yukseklik = (d: Durak, n: Durak) => {
    const temel = 50 + 0.12 * Math.abs(n.x - d.x2) + 0.5 * Math.abs(n.y - d.y);
    return [1, 0.7, 1.4, 0.45, 1.9, 0.25, 2.6, 3.4, 0.1].map((c) => temel * c).find((H) => temiz(d, n, H));
  };
  for (let k = 0; k + 1 < duraklar.length; ) {
    const d = duraklar[k];
    const n = duraklar[k + 1];
    if (n.sahne !== d.sahne) {
      k++;
      continue;
    }
    const H = yukseklik(d, n);
    if (H !== undefined) {
      n.tepe = H;
      k++;
    } else if (k + 2 < duraklar.length && duraklar[k + 2].sahne === d.sahne) {
      // Bu sıçrama yazıya değmeden yapılamıyor: maskot bir sonraki durağa kadar yerinde kalır.
      duraklar.splice(k + 1, 1);
      kalklar();
    } else {
      // Sahnenin son durağına güvenli yol yok: maskot sahne bitene kadar yerinde kalır.
      duraklar.splice(k + 1, 1);
      kalklar();
    }
  }
  return duraklar;
};

export type MaskotDurumu = {
  x: number;
  y: number; // ayak hizası (ekran)
  k: number; // kamera yakınlığı: maskot tuvalle birlikte büyür
  havada: number; // 0 yerde, 1 sıçramanın tepesi
  yon: 1 | -1;
  konus: number; // son konuştan beri geçen süre (sn), havadaysa -1
  bas: boolean;
  yuruyor: boolean;
  bekleme: number; // aynı yerde durma süresi
  kalkisaKalan: number;
  golgeY: number;
  belirme: number; // bu sahnede belirdiğinden beri geçen süre (sn); belirme yayı için
  saydam: number; // pencere kayıp giderken maskot da hızla söner
};

export const durum = (plan: Durak[], t: number, ekran: Ekran): MaskotDurumu => {
  const yerde = (d: Durak, x: number, an: number) => {
    const e = ekran(d.sahne, an);
    const p = ekranda(e, x, d.y - IC_UST_Y);
    return {x: p.x, y: p.y, k: e.k};
  };
  const ilk = plan[0];
  if (t < ilk.var) {
    const p = yerde(ilk, ilk.x, t);
    return {...p, havada: 0, yon: -1, konus: 99, bas: false, yuruyor: false, bekleme: 0, kalkisaKalan: 9, golgeY: p.y, belirme: t - 0.05, saydam: 1};
  }
  let k = 0;
  while (k + 1 < plan.length && plan[k + 1].var <= t) k++;
  const d = plan[k];
  const sonraki = plan[k + 1];
  const ayni = !!sonraki && sonraki.sahne === d.sahne;
  // Sahnedeki ilk durak: maskot burada belirir (önceki sahnenin penceresiyle gitmişti).
  let bas = k;
  while (bas > 0 && plan[bas - 1].sahne === d.sahne) bas--;
  const belirme = bas === 0 ? t - 0.05 : t - plan[bas].var;
  const yonBul = (a: number, b: number, varsayilan: 1 | -1): 1 | -1 => (Math.abs(b - a) < 4 ? varsayilan : b > a ? 1 : -1);
  if (t < d.kalk || !ayni) {
    const dt = t - d.var;
    const yuruyor = d.eylem === 'tara' && dt < d.sure;
    const u = d.eylem === 'tara' && d.sure > 0 ? Math.min(1, dt / d.sure) : 1;
    const x = d.x + (d.x2 - d.x) * u;
    const yon = yuruyor ? yonBul(d.x, d.x2, 1) : ayni ? yonBul(x, sonraki.x, d.x2 >= d.x ? 1 : -1) : -1;
    const p = yerde(d, x, t);
    return {
      ...p,
      havada: 0,
      yon,
      konus: k === 0 || k === bas ? 99 : dt,
      bas: d.eylem === 'bas' && k !== bas,
      yuruyor,
      bekleme: yuruyor ? 0 : dt - (d.eylem === 'tara' ? d.sure : 0),
      kalkisaKalan: ayni ? d.kalk - t : 99,
      golgeY: p.y,
      belirme,
      saydam: ayni ? 1 : 1 - ilerle(t, d.sahneBit, 0.1),
    };
  }
  const u = Math.min(1, (t - d.kalk) / Math.max(0.05, sonraki.var - d.kalk));
  const p = ucus(d, sonraki, u, sonraki.tepe, ekran);
  return {
    x: p.x,
    y: p.y,
    k: p.k,
    havada: Math.min(1, 4 * u * (1 - u) + 0.15),
    yon: yonBul(d.x2, sonraki.x, 1),
    konus: -1,
    bas: false,
    yuruyor: false,
    bekleme: 0,
    kalkisaKalan: 0,
    golgeY: p.golgeY,
    belirme,
    saydam: 1,
  };
};
