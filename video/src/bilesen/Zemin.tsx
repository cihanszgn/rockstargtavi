import React from 'react';
import {AbsoluteFill} from 'remotion';
import {R} from '../tema';

// Koyu zemin, yavaş kayan nokta ızgarası ve hafif mavi parıltı: sahne boş görünmesin, hareket hiç durmasın.
export const Zemin: React.FC<{t: number}> = ({t}) => (
  <AbsoluteFill style={{background: R.zemin}}>
    <AbsoluteFill
      style={{
        backgroundImage: 'radial-gradient(circle, rgba(141,176,255,0.11) 2px, transparent 2.6px)',
        backgroundSize: '48px 48px',
        backgroundPosition: `0px ${(-t * 12) % 48}px`,
      }}
    />
    <AbsoluteFill style={{background: 'radial-gradient(ellipse 70% 40% at 45% 38%, rgba(59,108,246,0.20), transparent 70%)'}} />
    <AbsoluteFill style={{background: 'radial-gradient(ellipse 60% 22% at 45% 82%, rgba(245,184,61,0.07), transparent 70%)'}} />
    <AbsoluteFill style={{background: 'radial-gradient(ellipse 85% 75% at 50% 50%, transparent 60%, rgba(0,0,0,0.45))'}} />
  </AbsoluteFill>
);
