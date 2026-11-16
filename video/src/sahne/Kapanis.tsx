import React from 'react';
import {Pencere} from '../bilesen/Pencere';
import {Simge} from '../bilesen/Simge';
import {Tus} from '../bilesen/Tus';
import type {Tuval} from '../kamera';
import {yaziGenisligi} from '../olcu';
import {D, R} from '../tema';
import type {Engel, Haber, Nokta, Sahne, SahneProps} from '../tipler';
import {basma, cikis, ilerle, sinirla} from '../zaman';
import {
  type Bakis,
  DAR,
  IC,
  IzleyenYazi,
  type Yazi,
  an,
  araKelime,
  bakis,
  belir,
  engel,
  etkinlik,
  genel,
  kelimeAnlari,
  kelimeIzi,
  izOrani,
  kenarDuraklari,
  sahneYolu,
  siganPunto,
  soylenme,
  sonKelimeBitis,
  veri,
  yaziBoyu,
  yaziEngeli,
  yaziSec,
} from './ortak';

type KapanisVeri = {cagri: string; alt: string; adres: string; goster: number};

// Ctrl + A tuşları tam genişlik bir tepside, adres tam genişlik bir kehribar tuşta: ikisinin üst kenarı maskotun basamağıdır.
const TUS_H = 168;
const CTRL_W = 300;
const ARTI_W = 80;
const A_W = 168;
const TEPSI_IC = 20;
const TEPSI_H = TUS_H + 2 * TEPSI_IC + 14;
const TUS_X = IC.sol + (DAR - (CTRL_W + ARTI_W + A_W)) / 2;
const ADRES_H = 112;
const SIMGE_SOL = 28;
const SIMGE = 52;
const ADRES_SOL = SIMGE_SOL + SIMGE + 24;

const duzen = (s: Sahne) => {
  const v = veri<KapanisVeri>(s);
  const cagri = yaziSec(v.cagri, 64, 800, 2, 46, 760);
  const altY = IC.ust + yaziBoyu(cagri) + 20;
  const alt: Yazi | undefined = v.alt ? yaziSec(v.alt, 40, 700, 2, 30, 760) : undefined;
  const tepsiY = (alt ? altY + yaziBoyu(alt) : altY - 20) + 32;
  const adresY = tepsiY + TEPSI_H + 28;
  const H = adresY + ADRES_H + 40;
  const adresPunto = siganPunto(v.adres, 56, 800, DAR - ADRES_SOL - 20, 1, 36);
  const g = an(s, v.goster);
  // A tuşu adres söylenince basılır, Ctrl ondan önceki kelimede; ikisi birden "hepsini seç" olur.
  const tA = Math.max(g + 0.6, soylenme(s, v.adres, g) ?? araKelime(s, g, s.bit, 0.75) ?? s.bas + 0.6 * (s.bit - s.bas));
  const once = kelimeAnlari(s).filter((b) => b >= g && b < tA - 0.15);
  const tCtrl = Math.max(g + 0.3, once.length ? once[once.length - 1] : tA - 0.5);
  const tSec = tA + 0.12;
  // Çağrı ve alt yazı Ctrl'e kadar söylenen kelimelerle sırayla işaretlenir.
  const izler = kelimeIzi(s, `${v.cagri} ${v.alt}`, s.bas, tCtrl);
  const nCagri = v.cagri.split(/\s+/).filter(Boolean).length;
  const tuval: Tuval = {ust: -2, alt: H - 2};
  return {v, cagri, altY, alt, tepsiY, adresY, H, adresPunto, tA, tCtrl, tSec, izler, nCagri, tuval};
};

// Hepsini seç: satır satır soldan sağa yayılan mavi seçim (yazının arkasında).
// Koyu zeminde yarı saydam, kehribar tuşun üstünde tam renk: açık zeminde yarı saydam mavi bulanık griye döner.
const Secim: React.FC<{satirlar: string[]; punto: number; agirlik: number; lh: number; sol: number; ust: number; t: number; t0: number; renk?: string}> = ({
  satirlar,
  punto,
  agirlik,
  lh,
  sol,
  ust,
  t,
  t0,
  renk = 'rgba(59,108,246,0.6)',
}) => (
  <>
    {satirlar.map((satir, r) => {
      const u = cikis(ilerle(t, t0 + 0.05 * r, 0.22));
      if (u <= 0) return null;
      const w = yaziGenisligi(satir, punto, agirlik) * D.altyazi.pay;
      return <div key={r} style={{position: 'absolute', left: sol - 8, top: ust + r * lh + 4, width: (w + 16) * u, height: lh - 6, borderRadius: 8, background: renk}} />;
    })}
  </>
);

export const Kapanis: React.FC<SahneProps> = ({s, t, haber}) => {
  const d = duzen(s);
  const {v} = d;
  const yol = sahneYolu(s, kapanisKamera(s, haber), d.tuval);
  const sec = cikis(ilerle(t, d.tSec, 0.3));
  const cagriOran = izOrani(d.izler.slice(0, d.nCagri), t) * (1 - sec);
  const altOran = izOrani(d.izler.slice(d.nCagri), t) * (1 - sec);
  const tepsi = cikis(ilerle(t, s.bas + 0.15, 0.3));
  const bc = belir(t, s.bas + 0.25);
  const ba = belir(t, s.bas + 0.32);
  const ctrlBasili = t >= d.tCtrl && t < d.tSec + 0.2 ? cikis(ilerle(t, d.tCtrl, 0.08)) : t >= d.tSec + 0.2 ? 1 - cikis(ilerle(t, d.tSec + 0.2, 0.12)) : 0;
  const yazilan = Math.floor(sinirla((t - d.tA) * 45, 0, v.adres.length));
  const adresIc = IC.sol + ADRES_SOL;
  const adresUst = d.adresY + (ADRES_H - 8 - Math.round(d.adresPunto * 1.18)) / 2;

  return (
    <Pencere baslik={s.veri.pencere ?? ''} h={d.H} etkin={etkinlik(yol, 0, t)}>
      <Secim satirlar={d.cagri.satirlar} punto={d.cagri.punto} agirlik={800} lh={d.cagri.lh} sol={IC.sol} ust={IC.ust} t={t} t0={d.tSec} />
      <IzleyenYazi
        satirlar={d.cagri.satirlar}
        oran={cagriOran}
        style={{position: 'absolute', left: IC.sol, top: IC.ust, fontSize: d.cagri.punto, lineHeight: `${d.cagri.lh}px`, fontWeight: 800, color: R.yazi}}
      />
      {d.alt ? (
        <>
          <Secim satirlar={d.alt.satirlar} punto={d.alt.punto} agirlik={700} lh={d.alt.lh} sol={IC.sol} ust={d.altY} t={t} t0={d.tSec + 0.1} />
          <IzleyenYazi
            satirlar={d.alt.satirlar}
            oran={altOran}
            style={{position: 'absolute', left: IC.sol, top: d.altY, fontSize: d.alt.punto, lineHeight: `${d.alt.lh}px`, fontWeight: 700, color: sec > 0.5 ? R.yazi : R.soluk}}
          />
        </>
      ) : null}
      <div
        style={{
          position: 'absolute',
          left: IC.sol,
          top: d.tepsiY,
          width: IC.en,
          height: TEPSI_H,
          boxSizing: 'border-box',
          borderRadius: 24,
          background: R.yuzey2,
          border: `2px solid ${t >= d.tCtrl ? R.secim : R.cizgi}`,
          opacity: tepsi,
        }}
      />
      <Tus x={TUS_X} y={d.tepsiY + TEPSI_IC} w={CTRL_W} h={TUS_H} derinlik={12} basili={ctrlBasili} olcek={bc.olcek} saydam={bc.saydam} yaricap={30}>
        <span style={{fontSize: 84, fontWeight: 800, color: R.yazi}}>Ctrl</span>
      </Tus>
      <div style={{position: 'absolute', left: TUS_X + CTRL_W, top: d.tepsiY + TEPSI_IC, width: ARTI_W, height: TUS_H, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 72, fontWeight: 800, color: R.soluk, opacity: bc.saydam}}>
        +
      </div>
      <Tus
        x={TUS_X + CTRL_W + ARTI_W}
        y={d.tepsiY + TEPSI_IC}
        w={A_W}
        h={TUS_H}
        derinlik={12}
        basili={basma(t - d.tA)}
        renk={R.secim}
        kenar={R.secimKoyu}
        olcek={ba.olcek}
        saydam={ba.saydam}
        yaricap={30}
      >
        <span style={{fontSize: 96, fontWeight: 800, color: '#FFFFFF'}}>A</span>
      </Tus>
      <Tus x={IC.sol} y={d.adresY} w={IC.en} h={ADRES_H} derinlik={8} renk={R.kehribar} kenar="#C8912A" basili={basma(t - d.tA - 0.35)} yaricap={22} style={{justifyContent: 'flex-start'}}>
        <Simge ad="site" boyut={SIMGE} renk={R.koyuYazi} kalinlik={2.6} style={{position: 'absolute', left: SIMGE_SOL, top: (ADRES_H - 8 - SIMGE) / 2}} />
      </Tus>
      <Secim satirlar={[v.adres]} punto={d.adresPunto} agirlik={800} lh={Math.round(d.adresPunto * 1.18)} sol={adresIc} ust={adresUst} t={t} t0={d.tSec + 0.2} renk={R.secim} />
      {/* Adres söylenince yazılır; yazılmamış harfler soluk durur, tuş hiç boş görünmez. */}
      <div style={{position: 'absolute', left: adresIc, top: adresUst, fontSize: d.adresPunto, lineHeight: `${Math.round(d.adresPunto * 1.18)}px`, fontWeight: 800, whiteSpace: 'nowrap'}}>
        <span style={{color: t >= d.tSec + 0.3 ? '#FFFFFF' : R.koyuYazi}}>{v.adres.slice(0, yazilan)}</span>
        <span style={{color: 'rgba(10,20,48,0.35)'}}>{v.adres.slice(yazilan)}</span>
      </div>
    </Pencere>
  );
};

// Kamera: çağrıya yakın, Ctrl basılınca tuşlara, hepsi seçilince bütün, söz bitince adrese yakın.
export const kapanisKamera = (s: Sahne, _haber: Haber): Bakis[] => {
  const d = duzen(s);
  const out: Bakis[] = [bakis(s.bas, IC.ust + yaziBoyu(d.cagri) / 2 + 60, 1.1, 0, 0)];
  if (d.tCtrl > s.bas + 0.6) out.push(bakis(d.tCtrl, d.tepsiY + TEPSI_H / 2, 1.1, d.tepsiY, 0));
  const tGenel = d.tSec + 0.15;
  out.push(genel(tGenel, d.tuval, d.tepsiY));
  const tAdres = Math.max(tGenel + 1.2, sonKelimeBitis(s) + 0.3);
  if (tAdres < s.bit - 0.8) out.push(bakis(tAdres, d.adresY + ADRES_H / 2 - 40, 1.1, d.adresY, 0));
  return out;
};

export const kapanisTuval = (s: Sahne, _haber: Haber): Tuval => duzen(s).tuval;

// Çağrı ve alt yazı satırları, tuşlar ve adres yazısı (tepsinin ve adres tuşunun sağ ucu boş: maskotun yeri).
export const kapanisEngeller = (s: Sahne, _haber: Haber): Engel[] => {
  const d = duzen(s);
  const {v} = d;
  return [
    ...yaziEngeli(v.cagri, d.cagri.punto, 800, d.cagri.en, IC.sol, IC.ust, d.cagri.lh),
    ...(d.alt ? yaziEngeli(v.alt, d.alt.punto, 700, d.alt.en, IC.sol, d.altY, d.alt.lh) : []),
    engel(TUS_X, d.tepsiY + TEPSI_IC, CTRL_W + ARTI_W + A_W, TUS_H + 14),
    engel(IC.sol, d.adresY, ADRES_SOL + yaziGenisligi(v.adres, d.adresPunto, 800) * D.altyazi.pay + 12, ADRES_H),
  ];
};

export const kapanisNoktalar = (s: Sahne, haber: Haber): Nokta[] => {
  const d = duzen(s);
  return kenarDuraklari(sahneYolu(s, kapanisKamera(s, haber), d.tuval), [0, d.tepsiY, d.adresY], kapanisEngeller(s, haber));
};
