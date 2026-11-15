import React from 'react';
import {Tus} from '../bilesen/Tus';
import {mutlak, R} from '../tema';
import {satirlaraBol, yaziGenisligi} from '../olcu';
import type {Engel, Haber, Nokta, Sahne, SahneProps} from '../tipler';
import {basma, cikis, ilerle} from '../zaman';
import {IC, an, belir, engel, satirli, veri, yaziEngeli, zemin} from './ortak';

type KapanisVeri = {cagri: string; alt: string; adres: string; goster: number};

// Tuşlar başlık çubuğundan, adres tuşu yazılardan bir maskot boyu uzakta: maskot konunca yazı örtülmez.
const TUS_Y = 172;
const CTRL = {x: 126, w: 300};
const A = {x: 532, w: 180};
const TUS_H = 180;
const ADRES_Y = 648;
const CAGRI_SATIR = 54;
const ALT_SATIR = 38;
const ALT_ARA = 22;

// Çağrı ve alt yazı, tuşların altı ile adres tuşunun maskot payı arasında dikeyde ortalanır.
const metinYerlesim = (v: KapanisVeri) => {
  const cagri = satirlaraBol(v.cagri, 46, 800, 760).length * CAGRI_SATIR;
  const alt = v.alt ? ALT_ARA + satirlaraBol(v.alt, 30, 700, 760).length * ALT_SATIR : 0;
  const ust = TUS_Y + TUS_H + 12;
  const bos = ADRES_Y - 116 - ust - cagri - alt;
  const y = ust + Math.max(16, bos / 2);
  return {y, altY: y + cagri + ALT_ARA};
};

const zamanlar = (s: Sahne) => {
  const g = an(s, veri<KapanisVeri>(s).goster);
  return {ctrl: g + 0.1, a: g + 0.7, yazi: g + 0.9, sec: g + 1.2, adres: g + 1.6};
};

const adresEni = (v: KapanisVeri) => Math.ceil(yaziGenisligi(v.adres, 40, 800) * 1.03) + 80;

export const Kapanis: React.FC<SahneProps> = ({s, t}) => {
  const v = veri<KapanisVeri>(s);
  const z = zamanlar(s);
  const ctrlBasili = t >= z.ctrl && t < z.sec ? cikis(ilerle(t, z.ctrl, 0.08)) : basma(t - z.sec + 0.08);
  const bc = belir(t, s.bas + 0.3);
  const ba = belir(t, s.bas + 0.4);
  const yazi = cikis(ilerle(t, z.yazi, 0.3));
  const sec = cikis(ilerle(t, z.sec, 0.25));
  const adres = belir(t, z.adres);
  const aw = adresEni(v);
  const my = metinYerlesim(v);
  const secimli: React.CSSProperties = {
    background: sec > 0 ? `rgba(59,108,246,${0.55 * sec})` : 'transparent',
    boxDecorationBreak: 'clone',
    WebkitBoxDecorationBreak: 'clone',
    borderRadius: 6,
  };
  return (
    <>
      <Tus x={CTRL.x} y={TUS_Y} w={CTRL.w} h={TUS_H} derinlik={12} basili={ctrlBasili} olcek={bc.olcek} saydam={bc.saydam} yaricap={30}>
        <span style={{fontSize: 84, fontWeight: 800, color: R.yazi}}>Ctrl</span>
      </Tus>
      <div style={{position: 'absolute', left: CTRL.x + CTRL.w, width: A.x - CTRL.x - CTRL.w, top: TUS_Y, height: TUS_H, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 72, fontWeight: 800, color: R.soluk, opacity: bc.saydam}}>
        +
      </div>
      <Tus x={A.x} y={TUS_Y} w={A.w} h={TUS_H} derinlik={12} basili={basma(t - z.a)} renk={R.secim} kenar={R.secimKoyu} olcek={ba.olcek} saydam={ba.saydam} yaricap={30}>
        <span style={{fontSize: 96, fontWeight: 800, color: '#FFFFFF'}}>A</span>
      </Tus>
      <div style={{position: 'absolute', left: IC.sol, top: my.y, width: 760, textAlign: 'center', whiteSpace: 'pre', opacity: yazi, transform: `translateY(${(1 - yazi) * 24}px)`}}>
        <div style={{fontSize: 46, lineHeight: `${CAGRI_SATIR}px`, fontWeight: 800, color: R.yazi}}>
          <span style={secimli}>{satirli(v.cagri, 46, 800, 760)}</span>
        </div>
        {v.alt ? (
          <div style={{marginTop: ALT_ARA, fontSize: 30, lineHeight: `${ALT_SATIR}px`, fontWeight: 700, color: R.soluk}}>
            <span style={secimli}>{satirli(v.alt, 30, 700, 760)}</span>
          </div>
        ) : null}
      </div>
      <Tus
        x={(IC.sol + IC.sag) / 2 - aw / 2}
        y={ADRES_Y}
        w={aw}
        h={84}
        derinlik={8}
        renk={R.kehribar}
        kenar="#C8912A"
        basili={basma(t - z.adres - 0.02)}
        olcek={adres.olcek}
        saydam={adres.saydam}
        yaricap={20}
      >
        <span style={{fontSize: 40, fontWeight: 800, color: R.koyuYazi, whiteSpace: 'nowrap'}}>{v.adres}</span>
      </Tus>
    </>
  );
};

export const kapanisNoktalar = (s: Sahne, _haber: Haber): Nokta[] => {
  const z = zamanlar(s);
  const aw = adresEni(veri<KapanisVeri>(s));
  return [
    {t: z.ctrl, x: mutlak(CTRL.x + CTRL.w / 2, 0).x, y: TUS_Y, eylem: 'bas', zemin: zemin(CTRL.x, CTRL.w)},
    {t: z.a, x: mutlak(A.x + A.w / 2, 0).x, y: TUS_Y, eylem: 'bas', zemin: zemin(A.x, A.w)},
    {t: z.adres, x: mutlak((IC.sol + IC.sag) / 2, 0).x, y: ADRES_Y, eylem: 'bas', zemin: zemin((IC.sol + IC.sag) / 2 - aw / 2, aw)},
  ];
};

export const kapanisEngeller = (s: Sahne, _haber: Haber): Engel[] => {
  const v = veri<KapanisVeri>(s);
  const my = metinYerlesim(v);
  const aw = adresEni(v);
  return [
    engel(CTRL.x, TUS_Y, A.x + A.w - CTRL.x, TUS_H + 12),
    ...yaziEngeli(v.cagri, 46, 800, 760, IC.sol, my.y, CAGRI_SATIR, 0, true),
    ...(v.alt ? yaziEngeli(v.alt, 30, 700, 760, IC.sol, my.altY, ALT_SATIR, 0, true) : []),
    engel((IC.sol + IC.sag) / 2 - aw / 2, ADRES_Y, aw, 92),
  ];
};
