import React from 'react';
import {Simge} from '../bilesen/Simge';
import {mutlak, R} from '../tema';
import {yaziGenisligi} from '../olcu';
import type {Engel, Haber, Nokta, Sahne, SahneProps} from '../tipler';
import {basma, cikis, ilerle} from '../zaman';
import {Cip, IC, an, belir, engel, kay, veri, zemin} from './ortak';

type FiyatVeri = {
  durum: string;
  etiket: string;
  bitis: string;
  eski_fiyat: string;
  yeni_fiyat: string;
  indirim: string;
  magazalar: {ad: string; goster: number}[];
  goster: number;
};

// Damganın üstüne konan maskot pencere adını örtmesin diye damga 176'da; mağazalar sığmazsa 130'a kadar çıkar.
const DAMGA_Y = 176;
const DAMGA_Y_EN_AZ = 130;
const CIP_W = 368;
const CIP_H = 76;

const yerlesim = (s: Sahne) => {
  const v = veri<FiyatVeri>(s);
  const fiyatVar = Boolean(v.eski_fiyat || v.yeni_fiyat);
  const satir = Math.ceil(v.magazalar.length / 2);
  const altKenar = (d: number) => {
    const bitisY = fiyatVar ? d + 270 : d + 182;
    const y0 = (v.bitis ? bitisY + 88 : bitisY) + 10;
    return {bitisY, y0, son: satir ? y0 + (satir - 1) * (CIP_H + 16) + CIP_H : y0};
  };
  const damgaY = Math.max(DAMGA_Y_EN_AZ, DAMGA_Y - Math.max(0, altKenar(DAMGA_Y).son - IC.alt));
  const {bitisY, y0} = altKenar(damgaY);
  const adim = Math.min(CIP_H + 16, (IC.alt - y0) / Math.max(1, satir));
  const damgaW = Math.ceil(yaziGenisligi(v.etiket, 60, 800) * 1.03) + 56 + 10;
  return {
    damga: an(s, v.goster),
    damgaY,
    damgaW,
    fiyatVar,
    fiyatY: damgaY + 170,
    bitisY,
    magazalar: v.magazalar.map((m, k) => ({ad: m.ad, goster: an(s, m.goster), x: IC.sol + (k % 2) * (CIP_W + 20), y: y0 + Math.floor(k / 2) * adim})),
  };
};

// Fiyat satırındaki öğelerin toplam genişliği (eski fiyat, ok, yeni fiyat, indirim çipi; aralar 22).
const fiyatEni = (v: FiyatVeri) => {
  const parcalar = [
    v.eski_fiyat ? yaziGenisligi(v.eski_fiyat, 56, 800) : 0,
    v.eski_fiyat && v.yeni_fiyat ? 48 : 0,
    v.yeni_fiyat ? yaziGenisligi(v.yeni_fiyat, 56, 800) : 0,
    v.indirim ? 36 + yaziGenisligi(v.indirim, 30, 800, 0.08) : 0,
  ].filter((w) => w > 0);
  return parcalar.reduce((a, b) => a + b, 0) * 1.03 + 22 * Math.max(0, parcalar.length - 1);
};

export const Fiyat: React.FC<SahneProps> = ({s, t}) => {
  const v = veri<FiyatVeri>(s);
  const y = yerlesim(s);
  const renk = v.durum === 'indirim' ? R.pembe : R.nane;
  const d = ilerle(t, y.damga, 0.2);
  const damgaOlcek = t < y.damga ? 0 : 1 + 1.1 * (1 - cikis(d));
  const sarsinti = t >= y.damga && t < y.damga + 0.3 ? Math.sin((t - y.damga) * 60) * 5 * (1 - (t - y.damga) / 0.3) : 0;
  const fiyat = kay(t, y.damga + 0.35, 24);
  const bitis = kay(t, y.damga + 0.55, 24);

  return (
    <>
      <div
        style={{
          position: 'absolute',
          left: IC.sol,
          top: y.damgaY,
          width: y.damgaW,
          height: 130,
          boxSizing: 'border-box',
          border: `6px solid ${renk}`,
          borderRadius: 20,
          background: `${renk}1F`,
          color: renk,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 60,
          fontWeight: 800,
          whiteSpace: 'nowrap',
          transform: `rotate(-6deg) scale(${damgaOlcek}) translateX(${sarsinti}px)`,
          opacity: t < y.damga ? 0 : cikis(d * 2),
          boxShadow: `0 8px 0 ${R.tusAlt}`,
        }}
      >
        {v.etiket}
      </div>
      {y.fiyatVar ? (
        <div style={{position: 'absolute', left: IC.sol, top: y.fiyatY, height: 76, display: 'flex', alignItems: 'center', gap: 22, opacity: fiyat.saydam, transform: `translateY(${fiyat.dy}px)`}}>
          {v.eski_fiyat ? (
            <span style={{fontSize: 56, fontWeight: 800, color: R.soluk, textDecoration: 'line-through', textDecorationColor: R.kirmizi, textDecorationThickness: 5}}>{v.eski_fiyat}</span>
          ) : null}
          {v.eski_fiyat && v.yeni_fiyat ? <Simge ad="ok" boyut={48} renk={renk} kalinlik={3} /> : null}
          {v.yeni_fiyat ? <span style={{fontSize: 56, fontWeight: 800, color: R.kehribar}}>{v.yeni_fiyat}</span> : null}
          {v.indirim ? (
            <Cip renk={R.pembe} dolu style={{height: 56, fontSize: 30}}>
              {v.indirim}
            </Cip>
          ) : null}
        </div>
      ) : null}
      {v.bitis ? (
        <div style={{position: 'absolute', left: IC.sol, top: y.bitisY, opacity: bitis.saydam, transform: `translateY(${bitis.dy}px)`}}>
          <Cip renk={R.kehribar} style={{height: 64, fontSize: 30, letterSpacing: '0.04em', gap: 14}}>
            <Simge ad="saat" boyut={32} renk={R.kehribar} kalinlik={2.6} />
            {v.bitis}
          </Cip>
        </div>
      ) : null}
      {y.magazalar.map((m, k) => {
        const b = belir(t, m.goster);
        const bas = basma(t - m.goster - 0.02);
        return (
          <div
            key={k}
            style={{
              position: 'absolute',
              left: m.x,
              top: m.y,
              width: CIP_W,
              height: CIP_H,
              boxSizing: 'border-box',
              borderRadius: 18,
              background: R.tusUst,
              border: `2px solid ${R.cizgi}`,
              boxShadow: `0 ${6 * (1 - bas)}px 0 ${R.tusAlt}`,
              display: 'flex',
              alignItems: 'center',
              gap: 14,
              paddingLeft: 22,
              overflow: 'hidden',
              opacity: b.saydam,
              transform: `translateY(${6 * bas}px) scale(${b.olcek})`,
            }}
          >
            <div style={{position: 'absolute', left: 0, top: 0, bottom: 0, width: 8, background: renk}} />
            <Simge ad="magaza" boyut={32} renk={renk} kalinlik={2.4} />
            <span style={{fontSize: 28, fontWeight: 700, color: R.yazi, whiteSpace: 'nowrap'}}>{m.ad}</span>
          </div>
        );
      })}
    </>
  );
};

export const fiyatNoktalar = (s: Sahne, _haber: Haber): Nokta[] => {
  const y = yerlesim(s);
  return [
    {t: y.damga, x: mutlak(IC.sol + y.damgaW / 2, 0).x, y: y.damgaY - 6, eylem: 'bas' as const, zemin: zemin(IC.sol, y.damgaW)},
    ...y.magazalar.map((m) => ({t: m.goster, x: mutlak(m.x + CIP_W / 2, 0).x, y: m.y, eylem: 'bas' as const, zemin: zemin(m.x, CIP_W)})),
  ];
};

// Damga (döndürülünce altı ~18 piksel taşar; üstü maskotun zemini), fiyat satırı, bitiş çipi ve mağaza adları.
export const fiyatEngeller = (s: Sahne, _haber: Haber): Engel[] => {
  const v = veri<FiyatVeri>(s);
  const y = yerlesim(s);
  return [
    engel(IC.sol, y.damgaY - 4, y.damgaW, 130 + 22 + 8),
    ...(y.fiyatVar ? [engel(IC.sol, y.fiyatY, fiyatEni(v), 76)] : []),
    ...(v.bitis ? [engel(IC.sol, y.bitisY, 82 + yaziGenisligi(v.bitis, 30, 800, 0.04) * 1.03, 64)] : []),
    ...y.magazalar.map((m) => engel(m.x + 22, m.y, 46 + yaziGenisligi(m.ad, 28, 700) * 1.03, CIP_H + 6)),
  ];
};
