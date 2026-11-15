import React from 'react';
import {PENCERE, R} from '../tema';

// Uygulama penceresi taklidi: başlık çubuğu (üç tuş noktası + pencere adı) ve içerik alanı.
// İçerik koordinatları çerçevenin iç kenarından ölçülür (tema.mutlak ile aynı).
export const Pencere: React.FC<{baslik: string; children: React.ReactNode}> = ({baslik, children}) => (
  <div
    style={{
      position: 'absolute',
      left: 0,
      top: 0,
      width: PENCERE.w,
      height: PENCERE.h,
      boxSizing: 'border-box',
      background: R.yuzey,
      border: `${PENCERE.cerceve}px solid ${R.cizgi}`,
      borderRadius: 28,
      boxShadow: `0 10px 0 ${R.tusAlt}`,
      overflow: 'hidden',
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
          width: 520,
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
