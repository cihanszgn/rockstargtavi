import React from 'react';
import {Pencere} from '../bilesen/Pencere';
import {Simge} from '../bilesen/Simge';
import {Tus} from '../bilesen/Tus';
import type {Tuval} from '../kamera';
import {R} from '../tema';
import type {Engel, Haber, Nokta, Sahne, SahneProps} from '../tipler';
import {basma, basmalar, cikis, ilerle} from '../zaman';
import {
  ANA_Y,
  type Bakis,
  DAR,
  IC,
  IzleyenYazi,
  PANEL_ARA,
  SUTUN,
  an,
  bakis,
  belir,
  degisim,
  engel,
  etkinlik,
  genel,
  ilkKelime,
  izOrani,
  kelimeIzi,
  kenarDuraklari,
  ortakYazi,
  panelBaslikEngeli,
  panelGiris,
  sahneYolu,
  sonKelimeBitis,
  veri,
  yaziBoyu,
  yaziEngeli,
  yaziSec,
} from './ortak';

type MaddelerVeri = {baslik: string; maddeler: {metin: string; goster: number}[]};

const TUS = 88;
const SATIR_SOL = 148;
const SATIR_EN = SUTUN - SATIR_SOL;
const SATIR_ARA = 16;
// İkinci panel: anlatılan madde büyük yazılır, yanında her maddede basılan kehribar tuş.
const BUYUK = 150;
const B_SOL = IC.sol + BUYUK + 32;
const B_EN = SUTUN - B_SOL;
const SERIT = 26;

const duzen = (s: Sahne, haber: Haber) => {
  const v = veri<MaddelerVeri>(s);
  const baslik = yaziSec(v.baslik, 60, 800, 2, 30, DAR);
  const ogeler = v.maddeler.map((m) => ({metin: m.metin, goster: an(s, m.goster)}));
  const sYazi = ortakYazi(
    ogeler.map((m) => m.metin),
    46,
    700,
    2,
    38,
    600,
    SATIR_EN,
  );
  let y = IC.ust + yaziBoyu(baslik) + 28;
  const satirlar = ogeler.map((m, k) => {
    const h = Math.max(112, yaziBoyu(sYazi[k]) + 44);
    const r = {...m, yazi: sYazi[k], y, h, bit: ogeler[k + 1]?.goster ?? s.bit};
    y += h + SATIR_ARA;
    return r;
  });
  const H1 = y - SATIR_ARA + 40;
  const yB = H1 + PANEL_ARA;
  const bYazi = ortakYazi(
    ogeler.map((m) => m.metin),
    60,
    800,
    3,
    36,
    600,
    B_EN,
  );
  const bMetinH = Math.max(BUYUK, ...bYazi.map(yaziBoyu));
  const seritY = IC.ust + bMetinH + 32;
  const H2 = seritY + SERIT + 40;
  const tuval: Tuval = {ust: -2, alt: yB + H2 - 2};
  return {v, pencere: s.veri.pencere ?? '', baslik, satirlar, bYazi, bMetinH, seritY, H1, yB, H2, oyun: haber.oyun.toLocaleUpperCase('tr'), tuval};
};

// O an anlatılan madde (ilk maddeden önce -1).
const simdiki = (d: ReturnType<typeof duzen>, t: number) => {
  let k = -1;
  d.satirlar.forEach((r, i) => {
    if (t >= r.goster) k = i;
  });
  return k;
};

export const Maddeler: React.FC<SahneProps> = ({s, t, haber}) => {
  const d = duzen(s, haber);
  const yol = sahneYolu(s, maddelerKamera(s, haber), d.tuval);
  const g0 = d.satirlar[0]?.goster ?? s.bit;
  // Başlık anlatılırken kelime kelime işaretlenir, ilk maddede işaret geri çekilir.
  const baslikOran = izOrani(kelimeIzi(s, d.v.baslik, s.bas, g0), t) * (1 - cikis(ilerle(t, g0, 0.3)));
  const cur = simdiki(d, t);
  const anlar = d.satirlar.map((r) => r.goster);

  return (
    <>
      <Pencere baslik={d.pencere} h={d.H1} etkin={etkinlik(yol, 0, t)}>
        <IzleyenYazi
          satirlar={d.baslik.satirlar}
          oran={baslikOran}
          style={{position: 'absolute', left: IC.sol, top: IC.ust, fontSize: d.baslik.punto, lineHeight: `${d.baslik.lh}px`, fontWeight: 800, color: R.yazi}}
        />
        {d.satirlar.map((r, k) => {
          const acik = t >= r.goster;
          const u = cikis(ilerle(t, r.goster, 0.3));
          const b = belir(t, r.goster);
          const aktif = k === cur;
          return (
            // Satır tuşuyla birlikte kayar: yalnız satır kaysaydı yazısı yerinde duran tuşun altına girerdi.
            <div key={k} style={{position: 'absolute', left: 0, top: 0, width: '100%', height: '100%', transform: `translateX(${acik ? (u - 1) * 40 : 0}px)`}}>
              <div
                style={{
                  position: 'absolute',
                  left: IC.sol,
                  top: r.y,
                  width: IC.en,
                  height: r.h,
                  boxSizing: 'border-box',
                  borderRadius: 20,
                  background: acik ? R.tusUst : R.yuzey,
                  border: `3px solid ${aktif ? R.kehribar : R.cizgi}`,
                  boxShadow: acik ? `0 6px 0 ${R.tusAlt}` : 'none',
                }}
              >
                <div
                  style={{
                    position: 'absolute',
                    left: SATIR_SOL - IC.sol - 3,
                    top: (r.h - yaziBoyu(r.yazi)) / 2 - 3,
                    fontSize: r.yazi.punto,
                    lineHeight: `${r.yazi.lh}px`,
                    fontWeight: 700,
                    color: acik ? R.yazi : R.soluk,
                    opacity: acik ? 1 : 0.45,
                    whiteSpace: 'pre',
                  }}
                >
                  {r.yazi.satirlar.join('\n')}
                </div>
              </div>
              <Tus
                x={IC.sol + 12}
                y={r.y + (r.h - TUS) / 2}
                w={TUS}
                h={TUS}
                basili={basma(t - r.goster - 0.02)}
                renk={acik ? R.nane : R.yuzey2}
                kenar={acik ? '#22A877' : R.cizgi}
                olcek={acik ? b.olcek : 1}
                yaricap={20}
              >
                {/* Sıra numarası yazılmaz: ekrandaki her sayı haberin kendi metninden gelmeli. */}
                {acik ? <Simge ad="onay" boyut={50} renk={R.koyuYazi} kalinlik={3.2} /> : <div style={{width: 14, height: 14, borderRadius: 7, background: R.cizgi}} />}
              </Tus>
            </div>
          );
        })}
      </Pencere>
      <Pencere baslik={d.oyun} y={d.yB} h={d.H2} kaydir={panelGiris(t, g0)} etkin={etkinlik(yol, 1, t)}>
        <Tus x={IC.sol} y={IC.ust} w={BUYUK} h={BUYUK} derinlik={10} basili={basmalar(t, anlar)} renk={R.kehribar} kenar="#C98A1B" yaricap={28}>
          <Simge ad="onay" boyut={96} renk={R.koyuYazi} kalinlik={3.4} />
        </Tus>
        {cur >= 0
          ? [cur - 1, cur].map((k) => {
              if (k < 0) return null;
              const r = d.satirlar[k];
              const y = d.bYazi[k];
              const dg = degisim(t, d.satirlar[cur].goster);
              const hal = k === cur ? (cur > 0 ? dg.yeni : {dy: 0, saydam: 1}) : dg.eski;
              if (hal.saydam <= 0) return null;
              return (
                <IzleyenYazi
                  key={k}
                  satirlar={y.satirlar}
                  oran={izOrani(kelimeIzi(s, r.metin, r.goster, r.bit), t)}
                  style={{
                    position: 'absolute',
                    left: B_SOL,
                    top: IC.ust + (d.bMetinH - yaziBoyu(y)) / 2,
                    fontSize: y.punto,
                    lineHeight: `${y.lh}px`,
                    fontWeight: 800,
                    color: R.yazi,
                    transform: `translateY(${hal.dy}px)`,
                    opacity: hal.saydam,
                  }}
                />
              );
            })
          : null}
        {d.satirlar.map((r, k) => {
          const n = d.satirlar.length;
          const w = (SUTUN - IC.sol - (n - 1) * 12) / n;
          const dolu = k < cur ? 1 : k === cur ? izOrani(kelimeIzi(s, r.metin, r.goster, r.bit), t) : 0;
          return (
            <div
              key={k}
              style={{position: 'absolute', left: IC.sol + k * (w + 12), top: d.seritY, width: w, height: SERIT, borderRadius: 13, background: R.cizgi, overflow: 'hidden'}}
            >
              <div style={{width: `${dolu * 100}%`, height: '100%', background: k < cur ? R.nane : R.kehribar}} />
            </div>
          );
        })}
      </Pencere>
    </>
  );
};

// Kamera: başlık, sonra her maddede satıra yaklaşır, anlatım ilerleyince ikinci panele iner, sonra bütüne bakar.
export const maddelerKamera = (s: Sahne, haber: Haber): Bakis[] => {
  const d = duzen(s, haber);
  const g0 = d.satirlar[0]?.goster ?? s.bit;
  const out: Bakis[] = [bakis(s.bas, ANA_Y, 1, 0, 0)];
  const k1 = ilkKelime(s, s.bas + 0.6, g0 - 0.6);
  if (k1 !== undefined) {
    out.push(bakis(k1, IC.ust + yaziBoyu(d.baslik) / 2, 1.1, 0, 0));
    const k2 = ilkKelime(s, k1 + 1.2, g0 - 0.6);
    if (k2 !== undefined && d.satirlar.length) out.push(bakis(k2, (d.satirlar[0].y + d.H1) / 2, 1, undefined, 0));
  }
  d.satirlar.forEach((r, k) => {
    out.push(bakis(r.goster, r.y + r.h / 2, 1.1, r.y, 0));
    const b = ilkKelime(s, r.goster + 0.7, r.bit - 0.6);
    if (b === undefined) return;
    out.push(bakis(b, d.yB + d.H2 / 2, 1, d.yB, 1));
    if (k < d.satirlar.length - 1) {
      const c = ilkKelime(s, b + 1.3, r.bit - 0.6);
      if (c !== undefined) out.push(genel(c, d.tuval));
    } else {
      const c = Math.max(b + 1, sonKelimeBitis(s));
      if (c < s.bit - 0.6) out.push(bakis(c, d.yB + IC.ust + d.bMetinH / 2, 1.1, d.yB, 1));
    }
  });
  return out;
};

export const maddelerTuval = (s: Sahne, haber: Haber): Tuval => duzen(s, haber).tuval;

export const maddelerEngeller = (s: Sahne, haber: Haber): Engel[] => {
  const d = duzen(s, haber);
  return [
    ...yaziEngeli(d.v.baslik, d.baslik.punto, 800, d.baslik.en, IC.sol, IC.ust, d.baslik.lh),
    ...d.satirlar.flatMap((r) => [
      engel(IC.sol + 12, r.y + (r.h - TUS) / 2, TUS, TUS + 8),
      ...yaziEngeli(r.metin, r.yazi.punto, 700, r.yazi.en, SATIR_SOL, r.y + (r.h - yaziBoyu(r.yazi)) / 2, r.yazi.lh),
    ]),
    panelBaslikEngeli(0, d.yB, d.oyun),
    engel(IC.sol, d.yB + IC.ust, BUYUK, BUYUK + 10),
    ...d.bYazi.flatMap((y, k) => yaziEngeli(d.satirlar[k].metin, y.punto, 800, y.en, B_SOL, d.yB + IC.ust + (d.bMetinH - yaziBoyu(y)) / 2, y.lh)),
  ];
};

// Maskot sağ sütunda: kameranın baktığı satırın, pencerenin ya da ikinci panelin üst kenarına konar.
export const maddelerNoktalar = (s: Sahne, haber: Haber): Nokta[] => {
  const d = duzen(s, haber);
  const g0 = d.satirlar[0]?.goster ?? s.bit;
  return kenarDuraklari(sahneYolu(s, maddelerKamera(s, haber), d.tuval), [0, ...d.satirlar.map((r) => r.y), {y: d.yB, bas: g0 + 0.3}], maddelerEngeller(s, haber));
};
