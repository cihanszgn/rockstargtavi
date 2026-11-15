import {yaziGenisligi} from './olcu';
import {SABLON} from './sahne';
import {D, GECIS, mutlak, PENCERE} from './tema';
import type {Engel, Haber, Nokta, Sahne} from './tipler';

// Maskotun bütün video boyunca nerede duracağını önceden planlar. Çizim (bilesen/Maskot.tsx) bu plana bakar.
export type Durak = {
  var: number; // konduğu an
  kalk: number; // sıçradığı an (son durakta sonsuz)
  x: number; // gövde ortası (kare koordinatı)
  y: number; // ayak hizası (kare koordinatı)
  eylem: 'bas' | 'dur' | 'tara';
  x2: number; // 'tara' yürüyüşünün bittiği x
  sure: number; // durakta yapılan eylemin süresi
  sahne: number;
  tepe: number; // buraya gelen sıçramanın yayı en çok bu kadar yükselir (piksel)
};

const M = D.maskot;
const ARA = 0.45; // aynı sahnede iki konuş arası en az
const ATLAMA = 0.42; // sahne içi sıçrama süresi
const TUNEK_X = 820; // pencerenin sağ üst kenarı: dayanak noktası yoksa buraya konar

const ayak = (yRel: number) => PENCERE.y + PENCERE.cerceve + yRel;
const xSinirla = (x: number) => Math.min(M.x_en_cok, Math.max(M.x_en_az, x));

const eylemCevir = (n: Nokta, hareket: string, sablon: string): Nokta => {
  if (n.eylem === 'tara' && (sablon !== 'kaynak' || hareket !== 'tara')) return {...n, eylem: 'dur', x2: undefined, sure: 0};
  if (hareket === 'zipla' && n.eylem === 'bas') return {...n, eylem: 'dur'};
  return n;
};

// Gövde (çerçeve pikselleri hariç) bir engelle kesişiyor mu? Ayak hizasındaki zemin öğesi engel sayılmaz.
const GOVDE_YARI = 42;
const carpar = (xa: number, xb: number, ayak: number, engeller: Engel[]) =>
  engeller.some((e) => xb + GOVDE_YARI > e.x0 && xa - GOVDE_YARI < e.x1 && ayak - M.yukseklik - 2 < e.y1 && ayak > e.y0 + 2);

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

// Sıçrama yayının tavanı: uçuş yolunun üstündeki yazıya gövde değmesin (iki tuş arası sıçrayış başlığa çıkıyordu).
const yayTavani = (xa: number, xb: number, yAyak: number, engeller: Engel[]) => {
  const ust = yAyak - PENCERE.y - PENCERE.cerceve - M.yukseklik;
  let tavan = Infinity;
  for (const e of engeller) {
    if (Math.max(xa, xb) + GOVDE_YARI > e.x0 && Math.min(xa, xb) - GOVDE_YARI < e.x1 && e.y1 <= ust + 2) tavan = Math.min(tavan, ust - e.y1 - 4);
  }
  return Math.max(8, tavan);
};

// Her pencerenin başlık çubuğu: üç tuş noktası (iç x 30..120) ve pencere adı (iç x 150'den).
const baslikEngeli = (s: Sahne): Engel => {
  const metin = (s.veri.pencere as string) ?? '';
  const w = metin ? Math.min(520, yaziGenisligi(metin, 26, 700, 0.08) * D.altyazi.pay) : 0;
  return {x0: mutlak(24, 0).x, x1: mutlak(150 + w, 0).x, y0: 20, y1: 54};
};

export const planla = (sahneler: Sahne[], haber: Haber): Durak[] => {
  const duraklar: Durak[] = [{var: 0.45, kalk: Infinity, x: TUNEK_X, y: ayak(0), eylem: 'dur', x2: TUNEK_X, sure: 0, sahne: 0, tepe: Infinity}];
  sahneler.forEach((s, i) => {
    const sablon = SABLON[s.sablon];
    if (!sablon) return;
    const hareket = s.maskot?.hareket || sablon.hareket;
    const enErken = i === 0 ? 0.9 : s.bas + GECIS + 0.12;
    const enGec = s.bit - 0.12;
    const engeller = [baslikEngeli(s), ...sablon.engeller(s, haber)];
    let adaylar = sablon
      .noktalar(s, haber)
      .map((n) => eylemCevir(n, hareket, s.sablon))
      .map((n) => yerlestir(n, engeller))
      .filter((n): n is Nokta => n !== null)
      .map((n) => ({...n, t: Math.max(n.t, enErken)}))
      .sort((a, b) => a.t - b.t);
    if (hareket === 'bekle') adaylar = adaylar.slice(0, 1).map((n) => ({...n, eylem: 'dur' as const}));

    const kabul: Durak[] = [];
    const sonrakiIcinEnErken = () => {
      const onceki = kabul.length ? kabul[kabul.length - 1] : duraklar[duraklar.length - 1];
      return kabul.length ? onceki.var + onceki.sure + ARA : Math.max(onceki.var + onceki.sure + 0.05, s.bas) + 0.5;
    };
    const ekle = (n: Nokta, sure: number) =>
      kabul.push({var: n.t, kalk: Infinity, x: xSinirla(n.x), y: ayak(n.y), eylem: n.eylem, x2: xSinirla(n.x2 ?? n.x), sure, sahne: i, tepe: Infinity});

    for (const n of adaylar) {
      const sure = Math.max(0, n.sure ?? 0);
      if (n.t < sonrakiIcinEnErken() || n.t + sure > enGec) continue;
      // İlk dayanak geç geliyorsa önce pencerenin kenarına kon: kayan eski pencerede havada asılı kalmasın.
      if (!kabul.length && n.t > enErken + 0.6 && enErken >= sonrakiIcinEnErken() && enErken + ARA <= n.t) {
        ekle({t: enErken, x: TUNEK_X, y: 0, eylem: 'dur'}, 0);
      }
      ekle(n, sure);
    }
    if (!kabul.length) {
      const t0 = Math.max(enErken, sonrakiIcinEnErken());
      if (t0 <= enGec) ekle({t: t0, x: TUNEK_X, y: 0, eylem: 'dur'}, 0);
    }
    if (!kabul.length) return;

    // Kalkış anları: sahne içinde konuştan hemen önce; sahne değişiminde eski pencere kaymaya başlarken.
    const onceki = duraklar[duraklar.length - 1];
    onceki.kalk = Math.max(onceki.var + onceki.sure + 0.05, Math.min(s.bas, kabul[0].var - 0.5));
    for (let k = 0; k + 1 < kabul.length; k++) {
      kabul[k].kalk = Math.max(kabul[k].var + kabul[k].sure, kabul[k + 1].var - ATLAMA);
    }
    kabul.forEach((d, k) => {
      const once = k ? kabul[k - 1] : onceki;
      d.tepe = yayTavani(once.x2, d.x, Math.min(once.y, d.y), engeller);
    });
    duraklar.push(...kabul);
  });
  return duraklar;
};

export type MaskotDurumu = {
  x: number;
  y: number; // ayak hizası
  havada: number; // 0 yerde, 1 sıçramanın tepesi
  yon: 1 | -1;
  konus: number; // son konuştan beri geçen süre (sn), havadaysa -1
  bas: boolean;
  yuruyor: boolean;
  bekleme: number; // aynı yerde durma süresi
  kalkisaKalan: number;
  golgeY: number;
  gorunur: number;
};

const kolay = (u: number) => 0.5 * (u + (u < 0.5 ? 2 * u * u : 1 - Math.pow(-2 * u + 2, 2) / 2));

export const durum = (plan: Durak[], t: number): MaskotDurumu => {
  const ilk = plan[0];
  if (t < ilk.var) {
    return {x: ilk.x, y: ilk.y, havada: 0, yon: -1, konus: 99, bas: false, yuruyor: false, bekleme: 0, kalkisaKalan: 9, golgeY: ilk.y, gorunur: t < 0.05 ? 0 : 1};
  }
  let k = 0;
  while (k + 1 < plan.length && plan[k + 1].var <= t) k++;
  const d = plan[k];
  const sonraki = plan[k + 1];
  const yonBul = (a: number, b: number, varsayilan: 1 | -1): 1 | -1 => (Math.abs(b - a) < 4 ? varsayilan : b > a ? 1 : -1);
  if (t < d.kalk || !sonraki) {
    const dt = t - d.var;
    const yuruyor = d.eylem === 'tara' && dt < d.sure;
    const u = d.eylem === 'tara' && d.sure > 0 ? Math.min(1, dt / d.sure) : 1;
    const x = d.x + (d.x2 - d.x) * u;
    const yon = yuruyor ? yonBul(d.x, d.x2, 1) : sonraki ? yonBul(x, sonraki.x, d.x2 >= d.x ? 1 : -1) : -1;
    return {
      x,
      y: d.y,
      havada: 0,
      yon,
      konus: k === 0 ? 99 : dt,
      bas: d.eylem === 'bas',
      yuruyor,
      bekleme: yuruyor ? 0 : dt - (d.eylem === 'tara' ? d.sure : 0),
      kalkisaKalan: sonraki ? d.kalk - t : 99,
      golgeY: d.y,
      gorunur: 1,
    };
  }
  const x0 = d.x2;
  const u = Math.min(1, (t - d.kalk) / Math.max(0.05, sonraki.var - d.kalk));
  const dx = sonraki.x - x0;
  const dy = sonraki.y - d.y;
  let H = 50 + 0.12 * Math.abs(dx) + 0.5 * Math.abs(dy);
  H = Math.min(H, Math.max(8, Math.min(d.y, sonraki.y) - 330), sonraki.tepe);
  const taban = d.y + dy * u;
  return {
    x: x0 + dx * kolay(u),
    y: taban - 4 * H * u * (1 - u),
    havada: Math.min(1, 4 * u * (1 - u) + 0.15),
    yon: yonBul(x0, sonraki.x, 1),
    konus: -1,
    bas: false,
    yuruyor: false,
    bekleme: 0,
    kalkisaKalan: 0,
    golgeY: taban,
    gorunur: 1,
  };
};
