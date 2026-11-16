import React from 'react';
import {Pencere} from '../bilesen/Pencere';
import {Simge} from '../bilesen/Simge';
import {Tus} from '../bilesen/Tus';
import type {Tuval} from '../kamera';
import {R} from '../tema';
import type {Engel, Haber, Nokta, Sahne, SahneProps} from '../tipler';
import {basma, cikis, ilerle, karistir} from '../zaman';
import {
  type Bakis,
  DAR,
  IC,
  PANEL_ARA,
  an,
  bakis,
  belir,
  degisim,
  engel,
  etkinlik,
  genel,
  kenarDuraklari,
  kenardan,
  panelBaslikEngeli,
  panelGiris,
  sahneYolu,
  siganPunto,
  soylenme,
  tekSatirEngeli,
  veri,
} from './ortak';

type Satir = {ad: string; eski: string; yeni: string; birim: string; yon: string; eski_oran: number; yeni_oran: number; goster: number};
type YamaVeri = {baslik: string; satirlar: Satir[]};

// Satır kutusu tam genişlikte (üst kenarı maskotun basamağı); içindekiler sütunun solunda kalır.
const SATIR_H = 196;
const SATIR_ARA = 16;
const SOL = IC.sol + 20;
const DEGER_W = 200;
const DEGER_H = 88;
const OK_X = SOL + DEGER_W + 16;
const YENI_X = OK_X + 80 + 16;
const ROZET_X = YENI_X + DEGER_W + 28;
const ROZET_W = 100;
const CUBUK_EN = DAR - 40;
// İkinci panel: eski ve yeni değerin büyük çubukları; yeni çubuk yeni değer söylenince kısalır ya da uzar.
const BAR_H = 100;
const BAR_ARA = 20;

const yonRengi = (yon: string) => (yon === 'azalis' ? R.kirmizi : yon === 'artis' ? R.nane : R.soluk);

const duzen = (s: Sahne) => {
  const v = veri<YamaVeri>(s);
  const satirlar = v.satirlar.map((r, k) => {
    const goster = an(s, r.goster);
    const sonra = v.satirlar[k + 1] ? an(s, v.satirlar[k + 1].goster) : s.bit;
    // Eski ve yeni değer anlatımda söylendiği anda belirir ("69'dan", "45'e").
    const tEski = Math.max(goster, soylenme(s, r.eski, goster - 0.05, sonra) ?? goster + 0.35);
    const tYeni = Math.max(tEski + 0.3, soylenme(s, r.yeni, tEski + 0.05, sonra) ?? tEski + 0.6);
    return {...r, goster, tEski, tYeni, y: IC.ust + k * (SATIR_H + SATIR_ARA)};
  });
  const H1 = IC.ust + satirlar.length * (SATIR_H + SATIR_ARA) - SATIR_ARA + 40;
  const yB = H1 + PANEL_ARA;
  const H2 = IC.ust + 2 * BAR_H + BAR_ARA + 40;
  const punto = Math.min(60, ...v.satirlar.flatMap((r) => [r.eski, r.yeni].map((d) => siganPunto(`${d} ${r.birim}`.trim(), 60, 800, 300, 1, 36))));
  const tB = satirlar[0]?.tEski ?? s.bit;
  const tuval: Tuval = {ust: -2, alt: yB + H2 - 2};
  return {v, satirlar, H1, yB, H2, punto, tB, tuval};
};

const simdiki = (d: ReturnType<typeof duzen>, t: number) => {
  let k = -1;
  d.satirlar.forEach((r, i) => {
    if (t >= r.goster) k = i;
  });
  return k;
};

const Cubuklar: React.FC<{r: ReturnType<typeof duzen>['satirlar'][number]; t: number; punto: number}> = ({r, t, punto}) => {
  const eskiU = cikis(ilerle(t, r.tEski, 0.3));
  const yeniU = cikis(ilerle(t, r.tYeni, 0.3));
  const renk = yonRengi(r.yon);
  const enCok = Math.max(r.eski_oran, r.yeni_oran, 1e-6);
  const eskiW = (r.eski_oran / enCok) * CUBUK_EN;
  const yeniW = karistir(eskiW, (r.yeni_oran / enCok) * CUBUK_EN, yeniU);
  const deger = (d: string) => `${d}${r.birim ? ` ${r.birim}` : ''}`;
  const bar = (top: number, w: number, zemin: string, yazi: string, metin: string, olcek: number) => (
    <div style={{position: 'absolute', left: IC.sol, top, width: CUBUK_EN, height: BAR_H, borderRadius: 22, background: R.yuzey2}}>
      {/* Değer söylenmeden önce soluk yer tutucu: panel boş çubuklarla beklemez, renkli dolgu bunun üstüne yayılır. */}
      <div style={{position: 'absolute', left: 0, top: 0, width: Math.max(BAR_H, w), height: BAR_H, borderRadius: 22, background: R.cizgi, opacity: 0.55 * (1 - olcek)}} />
      <div
        style={{
          position: 'absolute',
          left: 0,
          top: 0,
          width: Math.max(BAR_H, w),
          height: BAR_H,
          borderRadius: 22,
          background: zemin,
          boxShadow: `0 6px 0 ${R.tusAlt}`,
          transformOrigin: '0 50%',
          transform: `scaleX(${olcek})`,
        }}
      />
      <div style={{position: 'absolute', left: 28, top: 0, lineHeight: `${BAR_H}px`, fontSize: punto, fontWeight: 800, color: olcek > 0.5 ? yazi : R.soluk, whiteSpace: 'nowrap', opacity: 0.4 + 0.6 * olcek}}>
        {metin}
      </div>
    </div>
  );
  return (
    <>
      {bar(IC.ust, eskiW, R.cizgi, R.yazi, deger(r.eski), eskiU)}
      {bar(IC.ust + BAR_H + BAR_ARA, yeniW, yeniU > 0 ? renk : R.cizgi, yeniU > 0.5 ? R.koyuYazi : R.soluk, deger(r.yeni), eskiU)}
    </>
  );
};

export const YamaFark: React.FC<SahneProps> = ({s, t, haber}) => {
  const d = duzen(s);
  const yol = sahneYolu(s, yamaFarkKamera(s, haber), d.tuval, yamaFarkEngeller(s, haber));
  const cur = simdiki(d, t);

  return (
    <>
      <Pencere baslik={s.veri.pencere ?? ''} h={d.H1} etkin={etkinlik(yol, 0, t)}>
        {d.satirlar.map((r, k) => {
          const acik = t >= r.goster;
          const u = cikis(ilerle(t, r.goster, 0.3));
          const eski = t >= r.tEski;
          const yeni = t >= r.tYeni;
          const cizik = cikis(ilerle(t, r.tYeni - 0.1, 0.25));
          const ok = cikis(ilerle(t, r.tYeni - 0.1, 0.2));
          const yb = belir(t, r.tYeni);
          const cubuk = cikis(ilerle(t, r.tYeni, 0.3));
          const renk = yonRengi(r.yon);
          return (
            <div
              key={k}
              style={{
                position: 'absolute',
                left: IC.sol,
                top: r.y,
                width: IC.en,
                height: SATIR_H,
                boxSizing: 'border-box',
                borderRadius: 22,
                background: acik ? R.tusUst : R.yuzey,
                border: `3px solid ${k === cur ? R.kehribar : R.cizgi}`,
                boxShadow: acik ? `0 6px 0 ${R.tusAlt}` : 'none',
                opacity: acik ? 1 : 0.5,
                // Kısa kayış: kamera sol kenara yaslıyken satırın yazısı güvenli alandan çıkmaz.
                transform: `translateX(${acik ? (u - 1) * 20 : 0}px)`,
              }}
            >
              <div style={{position: 'absolute', left: SOL - IC.sol - 3, top: 14, width: DAR - 40, lineHeight: '44px', fontSize: 34, fontWeight: 800, letterSpacing: '0.03em', color: acik ? R.yazi : R.soluk, whiteSpace: 'nowrap', overflow: 'hidden'}}>
                {r.ad}
              </div>
              <Tus x={SOL - IC.sol - 3} y={64} w={DEGER_W} h={DEGER_H} derinlik={6} basili={basma(t - r.tEski)} renk={eski ? R.yuzey2 : R.yuzey} kenar={eski ? R.soluk : R.cizgi}>
                <span style={{fontSize: 46, fontWeight: 800, color: cizik > 0 ? R.soluk : eski ? R.yazi : R.cizgi, position: 'relative'}}>
                  {r.eski}
                  <span style={{position: 'absolute', left: -8, top: '52%', height: 6, width: `calc(${cizik * 100}% + 16px)`, background: R.kirmizi, borderRadius: 3}} />
                </span>
              </Tus>
              <div style={{position: 'absolute', left: OK_X - IC.sol - 3, top: 64 + 16, width: 80, display: 'flex', justifyContent: 'center', opacity: 0.25 + 0.75 * ok, transform: `translateX(${(1 - ok) * -16}px)`}}>
                <Simge ad="ok" boyut={56} renk={ok > 0 ? renk : R.cizgi} kalinlik={3} />
              </div>
              <Tus
                x={YENI_X - IC.sol - 3}
                y={64}
                w={DEGER_W}
                h={DEGER_H}
                derinlik={6}
                renk={yeni ? R.kehribar : R.yuzey}
                kenar={yeni ? '#C8912A' : R.cizgi}
                basili={basma(t - r.tYeni - 0.02)}
                olcek={yeni ? yb.olcek : 1}
              >
                <span style={{fontSize: 46, fontWeight: 800, color: yeni ? R.koyuYazi : R.cizgi}}>{r.yeni}</span>
              </Tus>
              <div
                style={{
                  position: 'absolute',
                  left: ROZET_X - IC.sol - 3,
                  top: 64 + 6,
                  width: ROZET_W,
                  height: DEGER_H - 12,
                  boxSizing: 'border-box',
                  borderRadius: 16,
                  border: `2px solid ${ok > 0 ? renk : R.cizgi}`,
                  background: ok > 0 ? `${renk}22` : 'transparent',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <svg width="40" height="34" viewBox="0 0 40 34" style={{opacity: 0.3 + 0.7 * ok}}>
                  <path d={r.yon === 'artis' ? 'M20 3 L37 31 L3 31 Z' : r.yon === 'azalis' ? 'M3 3 L37 3 L20 31 Z' : 'M4 13 H36 V21 H4 Z'} fill={ok > 0 ? renk : R.cizgi} />
                </svg>
              </div>
              <div style={{position: 'absolute', left: SOL - IC.sol - 3, top: 166, width: CUBUK_EN - 40, height: 12, borderRadius: 6, background: R.tusAlt, overflow: 'hidden'}}>
                <div style={{width: `${karistir(r.eski_oran, r.yeni_oran, cubuk) * 100}%`, height: '100%', borderRadius: 6, background: cubuk > 0 ? renk : R.soluk, opacity: eski ? 1 : 0.4}} />
              </div>
            </div>
          );
        })}
      </Pencere>
      <Pencere baslik={cur >= 0 ? d.satirlar[cur].ad : d.v.baslik} y={d.yB} h={d.H2} kaydir={panelGiris(t, d.tB)} etkin={etkinlik(yol, 1, t)}>
        {cur >= 0
          ? [cur - 1, cur].map((k) => {
              if (k < 0) return null;
              const dg = degisim(t, d.satirlar[cur].goster, 70);
              const hal = k === cur ? (cur > 0 ? dg.yeni : {dy: 0, saydam: 1}) : dg.eski;
              if (hal.saydam <= 0) return null;
              return (
                <div key={k} style={{position: 'absolute', left: 0, top: 0, right: 0, bottom: 0, transform: `translateY(${hal.dy}px)`, opacity: hal.saydam}}>
                  <Cubuklar r={d.satirlar[k]} t={t} punto={d.punto} />
                </div>
              );
            })
          : null}
      </Pencere>
    </>
  );
};

// Kamera her satırda: satıra yaklaşır, eski değerde çubuk paneline, yeni değerde çubuklara yaklaşır;
// sonraki satır gelince bütüne, sonra yeniden satıra bakar.
export const yamaFarkKamera = (s: Sahne, _haber: Haber): Bakis[] => {
  const d = duzen(s);
  const out: Bakis[] = [bakis(s.bas, Math.min(d.H1 / 2, 388), 1, 0, 0)];
  const bOrta = d.yB + d.H2 / 2;
  d.satirlar.forEach((r, k) => {
    out.push(k === 0 ? bakis(r.goster, r.y + SATIR_H / 2, 1.1, r.y, 0) : genel(r.goster, d.tuval, r.y));
    out.push(k === 0 ? kenardan(r.tEski, d.yB, 1, 1) : bakis(r.tEski, r.y + SATIR_H / 2, 1.1, r.y, 0));
    out.push(bakis(r.tYeni, bOrta, 1.1, d.yB, 1));
  });
  return out;
};

export const yamaFarkTuval = (s: Sahne, _haber: Haber): Tuval => duzen(s).tuval;

export const yamaFarkEngeller = (s: Sahne, _haber: Haber): Engel[] => {
  const d = duzen(s);
  return [
    ...d.satirlar.flatMap((r) => [
      tekSatirEngeli(r.ad, 34, 800, DAR - 40, SOL, r.y + 14, 44, 0.03),
      engel(SOL, r.y + 64, DEGER_W, DEGER_H + 8),
      engel(OK_X, r.y + 80, 80, 56),
      engel(YENI_X, r.y + 64, DEGER_W, DEGER_H + 8),
      engel(ROZET_X, r.y + 70, ROZET_W, DEGER_H - 12),
    ]),
    ...d.satirlar.map((r) => panelBaslikEngeli(0, d.yB, r.ad)),
    panelBaslikEngeli(0, d.yB, d.v.baslik),
    engel(IC.sol, d.yB + IC.ust, CUBUK_EN, 2 * BAR_H + BAR_ARA + 8),
  ];
};

// Maskot sağ sütunda: pencere, satır kutuları ve çubuk paneli kenarlarında kameranın baktığı yere konar.
export const yamaFarkNoktalar = (s: Sahne, haber: Haber): Nokta[] => {
  const d = duzen(s);
  return kenarDuraklari(sahneYolu(s, yamaFarkKamera(s, haber), d.tuval, yamaFarkEngeller(s, haber)), [0, ...d.satirlar.map((r) => r.y), {y: d.yB, bas: d.tB + 0.3}], yamaFarkEngeller(s, haber));
};
