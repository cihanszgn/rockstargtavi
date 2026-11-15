import React from 'react';
import {Tus} from '../bilesen/Tus';
import {mutlak, PLATFORM_RENK, R} from '../tema';
import {satirlaraBol, yaziGenisligi} from '../olcu';
import type {Engel, Haber, Nokta, Sahne, SahneProps} from '../tipler';
import {basma, yay} from '../zaman';
import {IC, an, belir, engel, kay, satirli, veri, yaziEngeli, zemin} from './ortak';

type PlatformVeri = {
  baslik: string;
  platformlar: {ad: string; renk: string; goster: number}[];
  not: string;
  sayilar: {deger: string; etiket: string; goster: number}[];
};

const ARA = 28;
// Maskotun konduğu tuş ve karoların üstünde bir gövde boyu boşluk: üstteki yazıyı örtmesin.
const MASKOT_ARA = 116;
const TUS_H = 110;
const TUS_ARA = 20;
const KARO_H = 210;
const KARO_ARA = 24;

// Başlık, platform tuşları, sayı karoları ve not dikeyde ortalanır; yerler maskot için de aynı hesaptan gelir.
const yerlesim = (s: Sahne) => {
  const v = veri<PlatformVeri>(s);
  const baslikSatir = v.baslik ? satirlaraBol(v.baslik, 46, 800, 760).length : 0;
  const notSatir = v.not ? satirlaraBol(v.not, 36, 700, 760).length : 0;
  const tuslar: {ad: string; renk: string; goster: number; x: number; satir: number; w: number}[] = [];
  let x = 0;
  let satir = 0;
  for (const p of v.platformlar) {
    const w = Math.max(150, Math.ceil(yaziGenisligi(p.ad, 40, 800, 0.03) * 1.03) + 64);
    if (x > 0 && x + w > IC.en) {
      satir += 1;
      x = 0;
    }
    tuslar.push({...p, goster: an(s, p.goster), x, satir, w});
    x += w + TUS_ARA;
  }
  const tusSatir = tuslar.length ? satir + 1 : 0;
  const bloklar = [
    baslikSatir ? baslikSatir * 54 : 0,
    tusSatir ? tusSatir * TUS_H + (tusSatir - 1) * TUS_ARA : 0,
    v.sayilar.length ? KARO_H : 0,
    notSatir ? notSatir * 46 : 0,
  ];
  // Tuşlar (1) ve karolar (2) maskotun zeminidir; yer yetmezse aralar daralır, maskot da o noktayı atlar.
  const aralar = (genis: boolean) => {
    const sonuc: number[] = [];
    let onceVar = false;
    bloklar.forEach((b, k) => {
      sonuc.push(b > 0 && onceVar ? (genis && (k === 1 || k === 2) ? MASKOT_ARA : ARA) : 0);
      if (b > 0) onceVar = true;
    });
    return sonuc;
  };
  const yukseklik = (a: number[]) => bloklar.reduce((t, b, k) => t + b + a[k], 0);
  const genis = aralar(true);
  const ara = yukseklik(genis) <= IC.alt - IC.ust ? genis : aralar(false);
  let y = IC.ust + Math.max(0, (IC.alt - IC.ust - yukseklik(ara)) / 2);
  const yerler: number[] = [];
  bloklar.forEach((b, k) => {
    y += ara[k];
    yerler.push(y);
    y += b;
  });
  // Her satırdaki tuşlar kendi içinde ortalanır.
  for (let r = 0; r < tusSatir; r++) {
    const sira = tuslar.filter((k) => k.satir === r);
    const son = sira[sira.length - 1];
    const kay0 = (IC.en - (son.x + son.w)) / 2;
    for (const k of sira) k.x += kay0;
  }
  const karoW = (IC.en - (v.sayilar.length - 1) * KARO_ARA) / Math.max(1, v.sayilar.length);
  return {
    baslikY: yerler[0],
    tusY: yerler[1],
    tuslar,
    karoY: yerler[2],
    karoW,
    sayilar: v.sayilar.map((n, k) => ({...n, goster: an(s, n.goster), x: IC.sol + k * (karoW + KARO_ARA)})),
    notY: yerler[3],
  };
};

export const Platform: React.FC<SahneProps> = ({s, t}) => {
  const v = veri<PlatformVeri>(s);
  const y = yerlesim(s);
  const baslik = kay(t, s.bas + 0.3, 30);
  const not = kay(t, Math.max(s.bas + 0.8, ...y.sayilar.map((n) => n.goster + 0.3), ...y.tuslar.map((k) => k.goster + 0.3)), 24);
  return (
    <>
      {v.baslik ? (
        <div style={{position: 'absolute', left: IC.sol, top: y.baslikY, width: 760, fontSize: 46, lineHeight: '54px', fontWeight: 800, color: R.yazi, whiteSpace: 'pre', opacity: baslik.saydam, transform: `translateY(${baslik.dy}px)`}}>
          {satirli(v.baslik, 46, 800, 760)}
        </div>
      ) : null}
      {y.tuslar.map((k, i) => {
        const b = belir(t, k.goster - 0.3);
        const renk = PLATFORM_RENK[k.renk] ?? R.soluk;
        return (
          <Tus
            key={i}
            x={IC.sol + k.x}
            y={y.tusY + k.satir * (TUS_H + TUS_ARA)}
            w={k.w}
            h={TUS_H}
            derinlik={10}
            basili={basma(t - k.goster)}
            olcek={b.olcek}
            saydam={b.saydam}
            yaricap={22}
          >
            <span style={{fontSize: 40, fontWeight: 800, letterSpacing: '0.03em', color: R.yazi, whiteSpace: 'nowrap'}}>{k.ad}</span>
            <div style={{position: 'absolute', left: 0, right: 0, bottom: 0, height: 10, background: renk}} />
          </Tus>
        );
      })}
      {y.sayilar.map((n, i) => {
        const b = belir(t, n.goster - 0.35);
        const deger = yay(t - n.goster, 0.45, 18);
        return (
          <Tus key={i} x={n.x} y={y.karoY} w={y.karoW} h={KARO_H} derinlik={10} basili={basma(t - n.goster)} olcek={b.olcek} saydam={b.saydam} yaricap={26} style={{flexDirection: 'column', gap: 10}}>
            <div style={{fontSize: 72, lineHeight: '80px', fontWeight: 800, color: t >= n.goster ? R.kehribar : R.cizgi, transform: `scale(${t >= n.goster ? 0.7 + 0.3 * deger : 0.9})`}}>
              {n.deger}
            </div>
            <div style={{fontSize: 24, lineHeight: '30px', fontWeight: 700, letterSpacing: '0.04em', color: R.soluk, textAlign: 'center', padding: '0 14px'}}>{n.etiket}</div>
          </Tus>
        );
      })}
      {v.not ? (
        <div style={{position: 'absolute', left: IC.sol, top: y.notY, width: 760, fontSize: 36, lineHeight: '46px', fontWeight: 700, color: R.soluk, whiteSpace: 'pre', opacity: not.saydam, transform: `translateY(${not.dy}px)`}}>
          {satirli(v.not, 36, 700, 760)}
        </div>
      ) : null}
    </>
  );
};

export const platformNoktalar = (s: Sahne, _haber: Haber): Nokta[] => {
  const y = yerlesim(s);
  return [
    ...y.tuslar.map((k) => ({
      t: k.goster,
      x: mutlak(IC.sol + k.x + k.w / 2, 0).x,
      y: y.tusY + k.satir * (TUS_H + TUS_ARA),
      eylem: 'bas' as const,
      zemin: zemin(IC.sol + k.x, k.w),
    })),
    ...y.sayilar.map((n) => ({t: n.goster, x: mutlak(n.x + y.karoW / 2, 0).x, y: y.karoY, eylem: 'bas' as const, zemin: zemin(n.x, y.karoW)})),
  ].sort((a, b) => a.t - b.t);
};

export const platformEngeller = (s: Sahne, _haber: Haber): Engel[] => {
  const v = veri<PlatformVeri>(s);
  const y = yerlesim(s);
  return [
    ...(v.baslik ? yaziEngeli(v.baslik, 46, 800, 760, IC.sol, y.baslikY, 54) : []),
    ...y.tuslar.map((k) => engel(IC.sol + k.x, y.tusY + k.satir * (TUS_H + TUS_ARA), k.w, TUS_H + 10)),
    ...y.sayilar.map((n) => engel(n.x, y.karoY, y.karoW, KARO_H + 10)),
    ...(v.not ? yaziEngeli(v.not, 36, 700, 760, IC.sol, y.notY, 46) : []),
  ];
};
