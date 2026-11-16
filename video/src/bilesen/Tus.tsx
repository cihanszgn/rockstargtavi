import React from 'react';
import {R, tusGolge} from '../tema';

// Sitenin klavye tuşu görünümü: düz üst yüz, ince çerçeve, altta koyu "kenar" gölgesi. Basılınca kenar kadar iner.
type TusProps = {
  x: number;
  y: number;
  w: number;
  h: number;
  basili?: number;
  derinlik?: number;
  renk?: string;
  kenar?: string;
  yaricap?: number;
  olcek?: number;
  saydam?: number;
  style?: React.CSSProperties;
  children?: React.ReactNode;
};

export const Tus: React.FC<TusProps> = ({
  x,
  y,
  w,
  h,
  basili = 0,
  derinlik = 8,
  renk = R.tusUst,
  kenar = R.cizgi,
  yaricap = 18,
  olcek = 1,
  saydam = 1,
  style,
  children,
}) => (
  <div
    data-kutu="tuş"
    style={{
      position: 'absolute',
      left: x,
      top: y,
      width: w,
      height: h,
      boxSizing: 'border-box',
      background: renk,
      border: `2px solid ${kenar}`,
      borderRadius: yaricap,
      boxShadow: `${tusGolge(derinlik, basili)}, inset 0 2px 0 rgba(255,255,255,0.07)`,
      transform: `translateY(${derinlik * basili}px) scale(${olcek})`,
      transformOrigin: '50% 100%',
      opacity: saydam,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      overflow: 'hidden',
      ...style,
    }}
  >
    {children}
  </div>
);
