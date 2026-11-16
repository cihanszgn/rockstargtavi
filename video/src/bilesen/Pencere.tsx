import React from 'react';
import {PENCERE, R} from '../tema';

// Uygulama penceresi taklidi: başlık çubuğu (üç tuş noktası + pencere adı) ve içerik alanı.
// x, y tuvalde dış sol üst köşe (ana pencere 0, 0); içerik koordinatları çerçevenin iç kenarından ölçülür
// (tema.mutlak ile aynı), böylece ikinci bir panelin içi ana pencere içi + (x, y) olur.
// etkin: anlatım bu pencereye geçince kenar mavi yanar.
export const Pencere: React.FC<{
  baslik: string;
  x?: number;
  y?: number;
  w?: number;
  h?: number;
  kaydir?: {dx?: number; dy?: number; saydam?: number};
  etkin?: number;
  children: React.ReactNode;
}> = ({baslik, x = 0, y = 0, w = PENCERE.w, h = PENCERE.h, kaydir, etkin = 0, children}) => (
  <div
    style={{
      position: 'absolute',
      left: x,
      top: y,
      width: w,
      height: h,
      boxSizing: 'border-box',
      background: R.yuzey,
      border: `${PENCERE.cerceve}px solid ${etkin > 0.5 ? R.secim : R.cizgi}`,
      borderRadius: 28,
      boxShadow: `0 10px 0 ${R.tusAlt}${etkin > 0 ? `, 0 0 0 ${Math.round(4 * etkin)}px ${R.secim}55` : ''}`,
      overflow: 'hidden',
      transform: kaydir ? `translate(${kaydir.dx ?? 0}px, ${kaydir.dy ?? 0}px)` : undefined,
      opacity: kaydir?.saydam ?? 1,
    }}
  >
    <div
      style={{
        position: 'absolute',
        left: 0,
        top: 0,
        right: 0,
        height: PENCERE.cubuk,
        background: R.yuzey2,
        borderBottom: `2px solid ${R.cizgi}`,
        display: 'flex',
        alignItems: 'center',
      }}
    >
      {[R.kirmizi, R.kehribar, R.nane].map((renk, i) => (
        <div
          key={renk}
          style={{
            position: 'absolute',
            left: 30 + i * 34,
            top: 26,
            width: 22,
            height: 22,
            borderRadius: 7,
            background: renk,
            boxShadow: `0 3px 0 ${R.tusAlt}`,
          }}
        />
      ))}
      <div
        style={{
          position: 'absolute',
          left: 150,
          width: Math.min(520, w - 190),
          top: 0,
          height: PENCERE.cubuk,
          lineHeight: `${PENCERE.cubuk}px`,
          fontSize: 26,
          fontWeight: 700,
          letterSpacing: '0.08em',
          color: R.soluk,
          whiteSpace: 'nowrap',
          overflow: 'hidden',
        }}
      >
        {baslik}
      </div>
    </div>
    {children}
  </div>
);
