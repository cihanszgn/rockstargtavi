import React from 'react';
import {D, R} from '../tema';
import type {Kelime, Parca} from '../tipler';
import {ilerle, yay} from '../zaman';

const A = D.altyazi;

// Alt üçte birdeki kelime kelime altyazı: parça (4–6 kelime, en çok 2 satır) birden görünür, söylenen kelime kehribar.
export const Altyazi: React.FC<{parcalar: Parca[]; kelimeler: Kelime[]; t: number}> = ({parcalar, kelimeler, t}) => {
  let i = -1;
  for (let j = 0; j < parcalar.length; j++) if (parcalar[j].b - 0.05 <= t) i = j;
  if (i < 0) return null;
  const p = parcalar[i];
  const sonraki = parcalar[i + 1];
  const bosluk = sonraki ? sonraki.b - p.bitis > 0.05 : true;
  if (t > p.bitis && bosluk) {
    const kalan = 1 - ilerle(t, p.bitis, 0.15);
    if (kalan <= 0) return null;
  }
  const solma = bosluk ? 1 - ilerle(t, p.bitis, 0.15) : 1;
  const acilis = yay(t - p.b + 0.05, 0.6, 18);
  let simdiki = -1;
  for (const satir of p.satirlar) for (const k of satir) if (kelimeler[k] && kelimeler[k].b <= t + 0.03) simdiki = k;
  const punto = A.punto * p.olcek;

  return (
    <div
      style={{
        position: 'absolute',
        left: A.merkez_x - A.en_genis_kutu / 2,
        width: A.en_genis_kutu,
        top: A.merkez_y - 150,
        height: 300,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        opacity: solma,
      }}
    >
      <div
        data-kutu="altyazı"
        style={{
          boxSizing: 'border-box',
          maxWidth: A.en_genis_kutu,
          padding: `${A.dolgu_y}px ${A.dolgu_x}px`,
          background: R.tusUst,
          border: `${A.cerceve}px solid ${R.cizgi}`,
          borderRadius: 22,
          boxShadow: `0 8px 0 ${R.tusAlt}`,
          transform: `scale(${0.9 + 0.1 * acilis})`,
          textAlign: 'center',
        }}
      >
        {p.satirlar.map((satir, si) => (
          <div
            key={si}
            style={{
              whiteSpace: 'nowrap',
              fontSize: punto,
              lineHeight: `${A.satir_yuksekligi * p.olcek}px`,
              fontWeight: A.agirlik,
            }}
          >
            {satir.map((k, ki) => {
              const kel = kelimeler[k];
              if (!kel) return null;
              // Yalnız renk değişir: büyütme, dar boşluklu satırda kelimeleri birbirine yapıştırıyordu.
              return (
                <React.Fragment key={k}>
                  {ki > 0 ? ' ' : null}
                  <span style={{color: k === simdiki ? R.kehribar : R.yazi}}>{kel.k}</span>
                </React.Fragment>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
};
