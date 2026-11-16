import React from 'react';
import {D, R, TUR_RENK} from '../tema';
import type {Haber, Sahne} from '../tipler';
import {basmalar, cikis, ilerle} from '../zaman';
import {Tus} from './Tus';

const M = D.marka;
const KAPAK = M.yukseklik - 6;

// Üstteki marka şeridi: sitenin "Ctrl + A GAME" logosu ve haber türü çipi. Tuşlar her sahne başında basılır.
export const UstSerit: React.FC<{haber: Haber; sahneler: Sahne[]; t: number}> = ({haber, sahneler, t}) => {
  const anlar = sahneler.map((s) => s.bas + 0.05);
  const giris = cikis(ilerle(t, 0, 0.4));
  const turRenk = TUR_RENK[haber.tur] ?? R.baglanti;
  return (
    // Şerit güvenli alanın sol kenarında başlar ve yerinde belirir: yukarıdan inse bir an uygulamanın geri/arama
    // simgelerinin altında kalırdı.
    <div style={{position: 'absolute', left: D.guvenli.sol, top: M.ust, height: M.yukseklik, width: 840, opacity: giris, transform: `translateY(${(1 - giris) * 12}px)`}}>
      <Tus x={0} y={0} w={104} h={KAPAK} derinlik={6} basili={basmalar(t, anlar)} yaricap={12}>
        <span style={{fontSize: 28, fontWeight: 800, color: R.yazi}}>Ctrl</span>
      </Tus>
      <div style={{position: 'absolute', left: 114, top: 0, height: KAPAK, lineHeight: `${KAPAK}px`, fontSize: 30, fontWeight: 800, color: R.soluk}}>+</div>
      <Tus x={142} y={0} w={KAPAK + 4} h={KAPAK} derinlik={6} renk={R.secim} kenar={R.secimKoyu} basili={basmalar(t, anlar.map((a) => a + 0.12))} yaricap={12}>
        <span style={{fontSize: 28, fontWeight: 800, color: '#FFFFFF'}}>A</span>
      </Tus>
      <div
        style={{
          position: 'absolute',
          left: 208,
          top: 0,
          height: KAPAK,
          lineHeight: `${KAPAK}px`,
          fontSize: 34,
          fontWeight: 800,
          fontStretch: '125%',
          letterSpacing: '0.02em',
          color: R.yazi,
        }}
      >
        GAME
      </div>
      <div
        data-kutu="tür çipi"
        style={{
          position: 'absolute',
          left: 364,
          top: 5,
          height: 38,
          padding: '0 16px',
          display: 'flex',
          alignItems: 'center',
          borderRadius: 12,
          border: `2px solid ${turRenk}`,
          background: `${turRenk}22`,
          color: turRenk,
          fontSize: 22,
          fontWeight: 800,
          letterSpacing: '0.08em',
          whiteSpace: 'nowrap',
        }}
      >
        {haber.tur_etiket}
      </div>
    </div>
  );
};
