import React from 'react';
import {D, R, SIMGE_RENK, tusGolge} from '../tema';
import type {AltKartVeri, Sahne} from '../tipler';
import {basma, cikis, ilerle} from '../zaman';
import {Simge} from './Simge';

const K = D.kart;
const DEGISIM = 0.35;

const Yazilar: React.FC<{kart: AltKartVeri; dy: number; saydam: number}> = ({kart, dy, saydam}) => {
  const en = K.genislik - K.yazi_sol - K.yazi_sag;
  const ortak: React.CSSProperties = {whiteSpace: 'nowrap', transformOrigin: '0 50%', width: en};
  return (
    <div
      style={{
        position: 'absolute',
        left: K.yazi_sol,
        top: 0,
        height: K.yukseklik,
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        gap: 10,
        transform: `translateY(${dy}px)`,
        opacity: saydam,
      }}
    >
      <div style={{...ortak, fontSize: K.baslik_punto, lineHeight: '52px', fontWeight: 800, color: R.yazi, transform: `scaleX(${kart.baslik_olcek})`}}>
        {kart.baslik}
      </div>
      {kart.alt ? (
        <div style={{...ortak, fontSize: K.alt_punto, lineHeight: '36px', fontWeight: 700, color: R.kehribar, letterSpacing: '0.02em', transform: `scaleX(${kart.alt_olcek})`}}>
          {kart.alt}
        </div>
      ) : null}
    </div>
  );
};

// Ekranın altında hep duran bilgi kartı: simge tuşu + kalın başlık + kehribar alt başlık. Her sahnede kısa geçişle değişir.
export const AltKart: React.FC<{sahneler: Sahne[]; t: number}> = ({sahneler, t}) => {
  let i = 0;
  for (let j = 0; j < sahneler.length; j++) if (sahneler[j].bas <= t) i = j;
  const yeni = sahneler[i];
  const eski = i > 0 ? sahneler[i - 1] : null;
  const e = eski ? ilerle(t, yeni.bas, DEGISIM) : 1;
  const giris = cikis(ilerle(t, 0, 0.45));
  const ikinciYari = e >= 0.5;
  const simgeKart = !eski || ikinciYari ? yeni.alt_kart : eski.alt_kart;
  const renk = simgeKart.simge === 'site' ? R.secim : SIMGE_RENK[simgeKart.simge] ?? R.baglanti;
  const cizgi = simgeKart.simge === 'site' ? '#FFFFFF' : R.koyuYazi;
  const bas = basma(t - yeni.bas - DEGISIM * 0.5);

  return (
    <div
      style={{
        position: 'absolute',
        left: K.sol,
        top: K.ust,
        width: K.genislik,
        height: K.yukseklik,
        boxSizing: 'border-box',
        background: R.yuzey,
        border: `2px solid ${R.cizgi}`,
        borderRadius: 28,
        boxShadow: `0 10px 0 ${R.tusAlt}`,
        overflow: 'hidden',
        transform: `translateY(${(1 - giris) * 280}px)`,
        opacity: giris,
      }}
    >
      <div
        style={{
          position: 'absolute',
          left: K.simge_sol - 2,
          top: (K.yukseklik - K.simge) / 2 - 6,
          width: K.simge,
          height: K.simge,
          borderRadius: 22,
          background: renk,
          boxShadow: tusGolge(6, bas),
          transform: `translateY(${6 * bas}px) scaleX(${eski ? Math.abs(Math.cos(Math.PI * e)) : 1})`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <Simge ad={simgeKart.simge} boyut={54} renk={cizgi} kalinlik={2.4} />
      </div>
      {eski && e < 1 ? <Yazilar kart={eski.alt_kart} dy={-24 * cikis(e)} saydam={1 - cikis(Math.min(1, e * 2))} /> : null}
      <Yazilar
        kart={yeni.alt_kart}
        dy={eski ? 24 * (1 - cikis(ilerle(e, 0.3, 0.7))) : 0}
        saydam={eski ? cikis(ilerle(e, 0.3, 0.7)) : 1}
      />
    </div>
  );
};
