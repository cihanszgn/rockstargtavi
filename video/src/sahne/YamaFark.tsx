import React from 'react';
import {Simge} from '../bilesen/Simge';
import {Tus} from '../bilesen/Tus';
import {mutlak, R} from '../tema';
import {yaziGenisligi} from '../olcu';
import type {Engel, Haber, Nokta, Sahne, SahneProps} from '../tipler';
import {basma, cikis, ilerle, karistir} from '../zaman';
import {IC, an, belir, engel, kay, tekSatirEngeli, veri, zemin} from './ortak';

type Satir = {ad: string; eski: string; yeni: string; birim: string; yon: string; eski_oran: number; yeni_oran: number; goster: number};
type YamaVeri = {baslik: string; satirlar: Satir[]};

const DEGER_W = 220;
const YENI_X = 360;
const BIRIM_X = 596;
// Bir satırın boyu: etiket, değer tuşları ve altındaki çubuk.
const SATIR_H = 166;

// Satırlar iç alanda dikeyde ortalanır.
const yerlesim = (s: Sahne) => {
  const v = veri<YamaVeri>(s);
  const n = Math.max(1, v.satirlar.length);
  // Adım en az 200: alttaki satırın yeni değer tuşuna konan maskot üstteki tuşlara değmesin.
  const adim = Math.min(210, 610 / n);
  const y0 = IC.ust + Math.max(14, (IC.alt - IC.ust - ((n - 1) * adim + SATIR_H)) / 2);
  return v.satirlar.map((r, k) => ({...r, goster: an(s, r.goster), y: y0 + k * adim}));
};

const yonRengi = (yon: string) => (yon === 'azalis' ? R.kirmizi : yon === 'artis' ? R.nane : R.soluk);

export const YamaFark: React.FC<SahneProps> = ({s, t}) => (
  <>
    {yerlesim(s).map((r, k) => {
      const ad = kay(t, s.bas + 0.3 + 0.1 * k, 24);
      const eski = kay(t, s.bas + 0.4 + 0.1 * k, 24);
      const cizik = cikis(ilerle(t, r.goster + 0.2, 0.25));
      const ok = cikis(ilerle(t, r.goster + 0.3, 0.2));
      const yeni = belir(t, r.goster + 0.4);
      const cubuk = cikis(ilerle(t, r.goster + 0.4, 0.5));
      const renk = yonRengi(r.yon);
      const oran = karistir(r.eski_oran, r.yeni_oran, cubuk);
      return (
        <React.Fragment key={k}>
          <div
            style={{
              position: 'absolute',
              left: IC.sol,
              top: r.y,
              width: IC.en,
              fontSize: 32,
              lineHeight: '40px',
              fontWeight: 800,
              letterSpacing: '0.03em',
              color: R.soluk,
              whiteSpace: 'nowrap',
              opacity: ad.saydam,
              transform: `translateY(${ad.dy}px)`,
            }}
          >
            {r.ad}
          </div>
          <Tus x={IC.sol} y={r.y + 48} w={DEGER_W} h={84} derinlik={6} saydam={eski.saydam} style={{transform: `translateY(${eski.dy}px)`}}>
            <span style={{fontSize: 44, fontWeight: 800, color: cizik > 0 ? R.soluk : R.yazi, position: 'relative'}}>
              {r.eski}
              <span style={{position: 'absolute', left: -8, top: '52%', height: 5, width: `calc(${cizik * 100}% + 16px)`, background: R.kirmizi, borderRadius: 3}} />
            </span>
          </Tus>
          <div style={{position: 'absolute', left: 260, top: r.y + 62, width: 100, display: 'flex', justifyContent: 'center', opacity: ok, transform: `translateX(${(1 - ok) * -20}px)`}}>
            <Simge ad="ok" boyut={56} renk={renk} kalinlik={3} />
          </div>
          <Tus
            x={YENI_X}
            y={r.y + 48}
            w={DEGER_W}
            h={84}
            derinlik={6}
            renk={R.kehribar}
            kenar="#C8912A"
            basili={basma(t - r.goster - 0.42)}
            olcek={yeni.olcek}
            saydam={yeni.saydam}
          >
            <span style={{fontSize: 44, fontWeight: 800, color: R.koyuYazi}}>{r.yeni}</span>
          </Tus>
          {r.birim ? (
            <div style={{position: 'absolute', left: BIRIM_X, top: r.y + 48, height: 84, lineHeight: '84px', fontSize: 28, fontWeight: 700, color: R.soluk, opacity: yeni.saydam}}>
              {r.birim}
            </div>
          ) : null}
          <div
            style={{
              position: 'absolute',
              left: IC.sag - 96,
              top: r.y + 52,
              width: 96,
              height: 76,
              borderRadius: 16,
              border: `2px solid ${renk}`,
              background: `${renk}22`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              opacity: ok,
            }}
          >
            <svg width="40" height="34" viewBox="0 0 40 34">
              <path d={r.yon === 'artis' ? 'M20 3 L37 31 L3 31 Z' : r.yon === 'azalis' ? 'M3 3 L37 3 L20 31 Z' : 'M4 13 H36 V21 H4 Z'} fill={renk} />
            </svg>
          </div>
          <div style={{position: 'absolute', left: IC.sol, top: r.y + 152, width: IC.en, height: 14, borderRadius: 7, background: R.tusAlt, overflow: 'hidden', opacity: eski.saydam}}>
            <div style={{width: `${oran * 100}%`, height: '100%', borderRadius: 7, background: cubuk > 0 ? renk : R.soluk}} />
          </div>
        </React.Fragment>
      );
    })}
  </>
);

export const yamaFarkNoktalar = (s: Sahne, _haber: Haber): Nokta[] =>
  yerlesim(s).map((r) => ({t: r.goster + 0.4, x: mutlak(YENI_X + DEGER_W / 2, 0).x, y: r.y + 48, eylem: 'bas' as const, zemin: zemin(YENI_X, DEGER_W)}));

export const yamaFarkEngeller = (s: Sahne, _haber: Haber): Engel[] =>
  yerlesim(s).flatMap((r) => [
    tekSatirEngeli(r.ad, 32, 800, IC.en, IC.sol, r.y, 40, 0.03),
    engel(IC.sol, r.y + 48, DEGER_W, 90),
    engel(282, r.y + 62, 56, 56),
    engel(YENI_X, r.y + 48, DEGER_W, 90),
    ...(r.birim ? [engel(BIRIM_X, r.y + 48, yaziGenisligi(r.birim, 28, 700) * 1.03, 84)] : []),
    engel(IC.sag - 96, r.y + 52, 96, 76),
  ]);
