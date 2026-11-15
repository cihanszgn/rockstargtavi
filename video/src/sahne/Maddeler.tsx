import React from 'react';
import {Simge} from '../bilesen/Simge';
import {Tus} from '../bilesen/Tus';
import {satirlaraBol} from '../olcu';
import {mutlak, R} from '../tema';
import type {Engel, Haber, Nokta, Sahne, SahneProps} from '../tipler';
import {basma, cikis, ilerle} from '../zaman';
import {IC, an, belir, engel, satirli, veri, yaziEngeli, zemin} from './ortak';

type MaddelerVeri = {baslik: string; maddeler: {metin: string; goster: number}[]};

const TUS = 88;
const ARA = 22;
const METIN_SOL = 136;

// Kartlar iç alanda dikeyde ortalanır.
const satirlar = (s: Sahne) => {
  const v = veri<MaddelerVeri>(s);
  const n = Math.max(1, v.maddeler.length);
  const adim = Math.min(168, 610 / n);
  const h = adim - ARA;
  const y0 = IC.ust + Math.max(14, (IC.alt - IC.ust - (n * adim - ARA)) / 2);
  return v.maddeler.map((m, k) => ({metin: m.metin, goster: an(s, m.goster), y: y0 + k * adim, h}));
};

export const Maddeler: React.FC<SahneProps> = ({s, t}) => {
  return (
    <>
      {satirlar(s).map((m, k) => {
        const acik = t >= m.goster;
        const u = cikis(ilerle(t, m.goster, 0.35));
        const b = belir(t, m.goster);
        const tusY = m.y + (m.h - TUS) / 2;
        return (
          <React.Fragment key={k}>
            <div
              style={{
                position: 'absolute',
                left: IC.sol,
                top: m.y,
                width: IC.en,
                height: m.h,
                boxSizing: 'border-box',
                borderRadius: 20,
                border: `2px dashed ${R.cizgi}`,
                opacity: 1 - u,
              }}
            />
            <div
              style={{
                position: 'absolute',
                left: IC.sol,
                top: m.y,
                width: IC.en,
                height: m.h,
                boxSizing: 'border-box',
                borderRadius: 20,
                background: R.tusUst,
                border: `2px solid ${R.cizgi}`,
                boxShadow: `0 6px 0 ${R.tusAlt}`,
                opacity: u,
                transform: `translateX(${(1 - u) * 60}px)`,
              }}
            >
              <div
                style={{
                  position: 'absolute',
                  left: METIN_SOL,
                  width: 600,
                  top: 0,
                  bottom: 0,
                  display: 'flex',
                  alignItems: 'center',
                  fontSize: 38,
                  lineHeight: '46px',
                  fontWeight: 700,
                  color: R.yazi,
                  whiteSpace: 'pre',
                }}
              >
                {satirli(m.metin, 38, 700, 600)}
              </div>
            </div>
            <Tus
              x={IC.sol + 20}
              y={tusY}
              w={TUS}
              h={TUS}
              derinlik={8}
              basili={basma(t - m.goster - 0.02)}
              renk={acik ? R.nane : R.yuzey2}
              kenar={acik ? '#22A877' : R.cizgi}
              olcek={acik ? b.olcek : 1}
              yaricap={20}
            >
              {/* Sıra numarası yazılmaz: ekrandaki her sayı haberin kendi metninden gelmeli. */}
              {acik ? <Simge ad="onay" boyut={50} renk={R.koyuYazi} kalinlik={3.2} /> : <div style={{width: 14, height: 14, borderRadius: 7, background: R.cizgi}} />}
            </Tus>
          </React.Fragment>
        );
      })}
    </>
  );
};

// Maskot açılan kartın üst kenarına konar; bir önceki kartın yazısını örtmeyecek yere kayar.
export const maddelerNoktalar = (s: Sahne, _haber: Haber): Nokta[] =>
  satirlar(s).map((m) => ({t: m.goster, x: mutlak(IC.sol + 20 + TUS / 2, 0).x, y: m.y, eylem: 'bas' as const, zemin: zemin(IC.sol, IC.en)}));

export const maddelerEngeller = (s: Sahne, _haber: Haber): Engel[] =>
  satirlar(s).flatMap((m) => {
    const satir = satirlaraBol(m.metin, 38, 700, 600).length;
    return [
      engel(IC.sol + 20, m.y + (m.h - TUS) / 2, TUS, TUS + 8),
      ...yaziEngeli(m.metin, 38, 700, 600, IC.sol + METIN_SOL, m.y + (m.h - satir * 46) / 2, 46),
    ];
  });
