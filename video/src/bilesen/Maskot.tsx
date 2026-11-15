import React from 'react';
import {type Durak, durum} from '../maskot';
import {D} from '../tema';
import {basma, yay} from '../zaman';

// Özgün piksel maskot: sitenin logosundaki mavi "A" tuşu, gözleri ve bacakları olan küçük bir tuş.
// 16x18 hücre, hücre 6 px → 96x108. Harfler: o kontur, t üst ışık, f yüz, s yan (tuşun kenarı), w beyaz.
const GOVDE = [
  '..oooooooooooo..',
  '.otttttttttttto.',
  'otffffffffffffto',
  'offffffffffffffo',
  'offffffffffffffo',
  'offffffffffffffo',
  'offffffwwffffffo',
  'offfffwffwfffffo',
  'offfffwwwwfffffo',
  'offfffwffwfffffo',
  'offfffwffwfffffo',
  'offffffffffffffo',
  'osssssssssssssso',
  '.osssssssssssso.',
  '..oooooooooooo..',
];

const BACAK = {
  dur: ['....oo....oo....', '....oo....oo....', '...ooo....ooo...'],
  adimA: ['....oo....oo....', '...ooo....oo....', '..........ooo...'],
  adimB: ['....oo....oo....', '....oo....ooo...', '...ooo..........'],
  havada: ['....oo....oo....', '...ooo....ooo...', '................'],
};

const RENK: Record<string, string> = {o: '#0A1430', t: '#6E93FF', f: '#3B6CF6', s: '#2447B8', w: '#FFFFFF'};
const H = 6;
const M = D.maskot;

type Goz = {kapali: boolean; bakX: -1 | 1; yukari: boolean};

const satirlar = (goz: Goz, bacak: string[]) => {
  const g = GOVDE.map((r) => r.split(''));
  for (const [sol, sag] of [
    [4, 5],
    [10, 11],
  ]) {
    if (goz.kapali) {
      g[4][sol] = 'o';
      g[4][sag] = 'o';
    } else {
      for (const r of [3, 4]) {
        g[r][sol] = 'w';
        g[r][sag] = 'w';
      }
      const bebekR = goz.yukari ? 3 : 4;
      g[bebekR][goz.bakX > 0 ? sag : sol] = 'o';
    }
  }
  return [...g.map((r) => r.join('')), ...bacak];
};

// Aynı renkteki yan yana hücreler tek dikdörtgen olur: kare başına çizilen öğe sayısı düşük kalır.
const Pikseller: React.FC<{rows: string[]}> = ({rows}) => (
  <>
    {rows.flatMap((satir, r) => {
      const parcalar: React.ReactNode[] = [];
      let c = 0;
      while (c < satir.length) {
        const h = satir[c];
        let e = c + 1;
        while (e < satir.length && satir[e] === h) e++;
        if (RENK[h]) parcalar.push(<rect key={`${r}-${c}`} x={c * H} y={r * H} width={(e - c) * H} height={H} fill={RENK[h]} />);
        c = e;
      }
      return parcalar;
    })}
  </>
);

export const Maskot: React.FC<{plan: Durak[]; t: number}> = ({plan, t}) => {
  const st = durum(plan, t);
  let dy = 0;
  let sx = 1;
  let sy = 1;
  let bacak = BACAK.dur;
  let yukari = false;
  const pop = t < plan[0].var ? yay(t - 0.05, 0.45, 12) : 1;

  if (st.havada > 0) {
    sy *= 1 + 0.1 * st.havada;
    sx *= 1 - 0.07 * st.havada;
    bacak = BACAK.havada;
    yukari = true;
  } else {
    sy *= 1 + 0.02 * Math.sin((2 * Math.PI * t) / 1.4);
    if (st.konus >= 0 && st.konus < 0.6) {
      const q = 0.22 * Math.exp(-8 * st.konus) * Math.cos(18 * st.konus);
      sy *= 1 - q;
      sx *= 1 + 0.7 * q;
    }
    if (st.bas && st.konus >= 0) dy += 10 * basma(st.konus);
    if (st.kalkisaKalan < 0.1) {
      const c = 1 - st.kalkisaKalan / 0.1;
      sy *= 1 - 0.12 * c;
      sx *= 1 + 0.08 * c;
    }
    if (st.yuruyor) {
      const adim = Math.floor(t / 0.13) % 2;
      bacak = adim ? BACAK.adimA : BACAK.adimB;
      dy -= 3 * Math.abs(Math.sin((t * Math.PI) / 0.13));
    } else if (st.bekleme > 2.2 && st.kalkisaKalan > 0.9) {
      // Uzun beklemede yerinde küçük sekme: maskot hiç donup kalmaz.
      const faz = (st.bekleme - 2.2) % 2.6;
      if (faz < 0.36) {
        const u = faz / 0.36;
        dy -= 26 * 4 * u * (1 - u);
        bacak = BACAK.havada;
        yukari = true;
      }
    }
  }
  const kapali = st.havada === 0 && t % 2.7 < 0.12;
  const yerdenYukseklik = Math.max(0, st.golgeY - (st.y + dy));
  const golge = 1 - Math.min(1, yerdenYukseklik / 160) * 0.5;

  return (
    <div style={{position: 'absolute', left: 0, top: 0, width: 1080, height: 1920, opacity: st.gorunur, pointerEvents: 'none'}}>
      <div
        style={{
          position: 'absolute',
          left: st.x - 34 * golge,
          top: st.golgeY - 7,
          width: 68 * golge,
          height: 14,
          borderRadius: '50%',
          background: `rgba(0,0,0,${0.38 * golge * pop})`,
        }}
      />
      <div
        style={{
          position: 'absolute',
          left: st.x - M.genislik / 2,
          top: st.y - M.yukseklik + dy,
          width: M.genislik,
          height: M.yukseklik,
          transform: `scale(${sx * pop}, ${sy * pop})`,
          transformOrigin: '50% 100%',
        }}
      >
        <svg width={M.genislik} height={M.yukseklik} viewBox={`0 0 ${16 * H} ${18 * H}`} shapeRendering="crispEdges" style={{display: 'block', overflow: 'visible'}}>
          <Pikseller rows={satirlar({kapali, bakX: st.yon, yukari}, bacak)} />
          <rect x={2 * H} y={5 * H} width={H} height={H} fill="#FF6BB5" opacity={0.6} />
          <rect x={13 * H} y={5 * H} width={H} height={H} fill="#FF6BB5" opacity={0.6} />
        </svg>
      </div>
    </div>
  );
};
