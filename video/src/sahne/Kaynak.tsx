import React from 'react';
import {Simge} from '../bilesen/Simge';
import {D, mutlak, R} from '../tema';
import {satirlaraBol, yaziGenisligi} from '../olcu';
import type {Engel, Haber, Nokta, Sahne, SahneProps} from '../tipler';
import {cikis, ilerle, sinirla} from '../zaman';
import {Cip, IC, an, engel, kay, satirli, veri, yaziEngeli, zemin} from './ortak';

type KaynakVeri = {alan: string; yol: string; ad: string; etiket: string; alinti: string; tarih: string; goster: number};

const ADRES_Y = 116;
const AD_Y = 204;
const AD_SATIR = 42;
// Damga ile alıntı kutusu arası maskotun yürüyüş yolu: gövde boyu (108) ve biraz pay.
const YOL = 116;

const damgaEni = (v: KaynakVeri) => Math.ceil(yaziGenisligi(v.etiket, 26, 800, 0.06) * 1.03) + 36 + 6;
const tarihEni = (v: KaynakVeri) => (v.tarih ? 68 + yaziGenisligi(v.tarih, 22, 800, 0.08) * D.altyazi.pay : 0);

// Ad 1-2 satır olabilir; damga onun altına, alıntı kutusu damganın bir maskot boyu altına iner.
const yerlesim = (v: KaynakVeri) => {
  const damgaY = AD_Y + Math.max(1, satirlaraBol(v.ad, 34, 700, 760).length) * AD_SATIR + 22;
  // Döndürülmüş damga 52 piksellik kutusundan yaklaşık 10 piksel taşar.
  const damgaAlt = damgaY + 62;
  const kutuBoy = 56 + 52 * satirlaraBol(v.alinti, 40, 700, 680).length + 4 + 8;
  return {damgaY, damgaAlt, alintiY: Math.min(damgaAlt + YOL, IC.alt - kutuBoy)};
};

const alintiSatirli = (v: KaynakVeri) => satirli(v.alinti, 40, 700, 680);

const zamanlar = (s: Sahne) => {
  const v = veri<KaynakVeri>(s);
  const damga = an(s, v.goster);
  const yazBas = damga + 0.6;
  const harf = [...alintiSatirli(v)].length;
  const hiz = Math.max(30, harf / Math.max(0.5, s.bit - 1.2 - yazBas));
  const yazBit = yazBas + harf / hiz;
  return {damga, yazBas, hiz, yazBit};
};

export const Kaynak: React.FC<SahneProps> = ({s, t}) => {
  const v = veri<KaynakVeri>(s);
  const z = zamanlar(s);
  const y = yerlesim(v);
  const adres = `${v.alan}${v.yol}`;
  const yazilan = Math.floor(sinirla((t - s.bas - 0.2) * 40, 0, adres.length));
  const ad = kay(t, s.bas + 0.35);
  const d = ilerle(t, z.damga, 0.18);
  const damgaOlcek = t < z.damga ? 0 : 1 + 0.9 * (1 - cikis(d));
  const sarsinti = t >= z.damga && t < z.damga + 0.25 ? Math.sin((t - z.damga) * 70) * 3 * (1 - (t - z.damga) / 0.25) : 0;
  const tarih = kay(t, z.damga + 0.15, 20);
  const harfler = [...alintiSatirli(v)];
  const n = Math.floor(sinirla((t - z.yazBas) * z.hiz, 0, harfler.length));
  const kutu = kay(t, z.damga + 0.3, 30);
  const sec = cikis(ilerle(t, z.yazBit + 0.35, 0.25));
  const imlec = t < z.yazBit + 0.35 && Math.floor(t * 3) % 2 === 0;

  return (
    <>
      <div
        style={{
          position: 'absolute',
          left: IC.sol,
          top: ADRES_Y,
          width: IC.en,
          height: 64,
          boxSizing: 'border-box',
          borderRadius: 16,
          border: `2px solid ${R.cizgi}`,
          background: R.zemin,
          display: 'flex',
          alignItems: 'center',
          paddingLeft: 20,
          gap: 14,
          overflow: 'hidden',
        }}
      >
        <Simge ad="kilit" boyut={28} renk={R.nane} />
        <div
          style={{
            fontSize: 28,
            fontWeight: 700,
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            width: IC.en - 90,
            maskImage: 'linear-gradient(to right, black 88%, transparent)',
            WebkitMaskImage: 'linear-gradient(to right, black 88%, transparent)',
          }}
        >
          <span style={{color: R.yazi}}>{adres.slice(0, Math.min(yazilan, v.alan.length))}</span>
          <span style={{color: R.soluk}}>{adres.slice(v.alan.length, Math.max(v.alan.length, yazilan))}</span>
        </div>
      </div>
      <div
        style={{
          position: 'absolute',
          left: IC.sol,
          top: AD_Y,
          width: 760,
          fontSize: 34,
          lineHeight: `${AD_SATIR}px`,
          fontWeight: 700,
          color: R.yazi,
          whiteSpace: 'pre',
          opacity: ad.saydam,
          transform: `translateY(${ad.dy}px)`,
        }}
      >
        {satirli(v.ad, 34, 700, 760)}
      </div>
      <div style={{position: 'absolute', left: IC.sol, top: y.damgaY, display: 'flex', alignItems: 'center', gap: 24}}>
        <div
          style={{
            width: damgaEni(v),
            boxSizing: 'border-box',
            height: 52,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            border: `3px solid ${R.nane}`,
            borderRadius: 10,
            color: R.nane,
            background: `${R.nane}1A`,
            fontSize: 26,
            fontWeight: 800,
            letterSpacing: '0.06em',
            whiteSpace: 'nowrap',
            transform: `rotate(-4deg) scale(${damgaOlcek}) translateX(${sarsinti}px)`,
            opacity: t < z.damga ? 0 : cikis(d * 2),
          }}
        >
          {v.etiket}
        </div>
        {v.tarih ? (
          <Cip renk={R.soluk} style={{opacity: tarih.saydam, transform: `translateY(${tarih.dy}px)`}}>
            <Simge ad="takvim" boyut={22} renk={R.soluk} />
            {v.tarih}
          </Cip>
        ) : null}
      </div>
      <div
        style={{
          position: 'absolute',
          left: IC.sol,
          top: y.alintiY,
          width: IC.en,
          boxSizing: 'border-box',
          padding: '28px 32px 28px 44px',
          borderRadius: 20,
          background: R.tusUst,
          border: `2px solid ${R.cizgi}`,
          boxShadow: `0 8px 0 ${R.tusAlt}`,
          opacity: kutu.saydam,
          transform: `translateY(${kutu.dy}px)`,
          overflow: 'hidden',
        }}
      >
        <div style={{position: 'absolute', left: 0, top: 0, bottom: 0, width: 10, background: R.kehribar}} />
        <div style={{fontSize: 40, lineHeight: '52px', fontWeight: 700, color: R.yazi, whiteSpace: 'pre'}}>
          <span
            style={{
              background: sec > 0 ? `rgba(59,108,246,${0.55 * sec})` : 'transparent',
              boxDecorationBreak: 'clone',
              WebkitBoxDecorationBreak: 'clone',
              borderRadius: 6,
            }}
          >
            {harfler.slice(0, n).join('')}
          </span>
          {imlec ? <span style={{display: 'inline-block', width: 0, position: 'relative'}}><span style={{position: 'absolute', left: 2, top: 6, width: 4, height: 42, background: R.kehribar}} /></span> : null}
          <span style={{color: 'transparent'}}>{harfler.slice(n).join('')}</span>
        </div>
      </div>
    </>
  );
};

// Maskot alıntı yazılırken kutunun üstünde yürür; damgaya basmaz (damga adın hemen altında, üstünde yer yok).
export const kaynakNoktalar = (s: Sahne, _haber: Haber): Nokta[] => {
  const v = veri<KaynakVeri>(s);
  const z = zamanlar(s);
  const y = yerlesim(v);
  const sol = mutlak(IC.sol + 70, 0).x;
  const sag = mutlak(IC.sag - 70, 0).x;
  return [{t: z.yazBas, x: sol, y: y.alintiY, eylem: 'tara', x2: sag, sure: Math.min(z.yazBit, s.bit - 0.6) - z.yazBas, zemin: zemin(IC.sol, IC.en)}];
};

export const kaynakEngeller = (s: Sahne, _haber: Haber): Engel[] => {
  const v = veri<KaynakVeri>(s);
  const y = yerlesim(v);
  return [
    engel(IC.sol, ADRES_Y, IC.en, 64),
    ...yaziEngeli(v.ad, 34, 700, 760, IC.sol, AD_Y, AD_SATIR),
    engel(IC.sol, y.damgaY - 10, damgaEni(v) + (v.tarih ? 24 + tarihEni(v) : 0), y.damgaAlt - y.damgaY + 10),
  ];
};
