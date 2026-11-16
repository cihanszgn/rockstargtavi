import React from 'react';
import {Pencere} from '../bilesen/Pencere';
import {Simge} from '../bilesen/Simge';
import type {Tuval} from '../kamera';
import {yaziGenisligi} from '../olcu';
import {D, R} from '../tema';
import type {Engel, Haber, Nokta, Sahne, SahneProps} from '../tipler';
import {cikis, ilerle, sinirla} from '../zaman';
import {
  type Bakis,
  Cip,
  DAR,
  IC,
  IzleyenYazi,
  PANEL_ARA,
  SUTUN,
  an,
  araKelime,
  bakis,
  engel,
  etkinlik,
  genel,
  ilkKelime,
  izOrani,
  kay,
  kelimeIzi,
  kenarDuraklari,
  kenardan,
  okunan,
  panelBaslikEngeli,
  panelGiris,
  sahneYolu,
  sonKelimeBitis,
  veri,
  yaziBoyu,
  yaziEngeli,
  yaziSec,
} from './ortak';

type KaynakVeri = {alan: string; yol: string; ad: string; etiket: string; alinti: string; tarih: string; goster: number};

const ADRES_Y = IC.ust;
const ADRES_H = 64;
const AD_Y = ADRES_Y + ADRES_H + 32;
// Damga ve tarih tam genişlik bir kutuda: kutunun üst kenarı maskotun basamağıdır.
const KUTU_H = 92;
const DAMGA_H = 56;
// Alıntı kehribar çubuğun sağında başlar.
const ALINTI_SOL = IC.sol + 34;
const ALINTI_EN = SUTUN - ALINTI_SOL;

const damgaEni = (v: KaynakVeri) => Math.ceil(yaziGenisligi(v.etiket, 28, 800, 0.06) * D.altyazi.pay) + 44;

const duzen = (s: Sahne, haber: Haber) => {
  const v = veri<KaynakVeri>(s);
  const ad = yaziSec(v.ad, 58, 800, 2, 34, 760);
  const kutuY = AD_Y + yaziBoyu(ad) + 28;
  const H1 = kutuY + KUTU_H + 40;
  const yB = H1 + PANEL_ARA;
  const alinti = yaziSec(v.alinti, 50, 700, 5, 40, 680, ALINTI_EN);
  const H2 = IC.ust + yaziBoyu(alinti) + 40;
  const damga = an(s, v.goster);
  // Alıntı anlatımın üçte birinde gelir ve kalan kelimelerle birlikte yazılır.
  const tAlinti = Math.max(damga + 0.7, araKelime(s, s.bas, s.bit, 0.35) ?? s.bas + 0.4 * (s.bit - s.bas));
  const tGenel = araKelime(s, tAlinti + 1.4, s.bit, 0.5);
  const tSec = Math.max((tGenel ?? tAlinti) + 1, sonKelimeBitis(s));
  const tuval: Tuval = {ust: -2, alt: yB + H2 - 2};
  return {v, ad, kutuY, H1, yB, alinti, H2, damga, tAlinti, tGenel, tSec, oyun: haber.oyun.toLocaleUpperCase('tr'), tuval};
};

export const Kaynak: React.FC<SahneProps> = ({s, t, haber}) => {
  const d = duzen(s, haber);
  const {v} = d;
  const yol = sahneYolu(s, kaynakKamera(s, haber), d.tuval, kaynakEngeller(s, haber));
  const adres = `${v.alan}${v.yol}`;
  const yazilan = Math.floor(sinirla((t - s.bas - 0.2) * 40, 0, adres.length));
  // Kaynağın adı söylendikçe işaretlenir, alıntıya geçince işaret çekilir.
  const adOran = izOrani(kelimeIzi(s, v.ad, s.bas, d.tAlinti), t) * (1 - cikis(ilerle(t, d.tAlinti, 0.3)));
  const dg = ilerle(t, d.damga, 0.18);
  const damgaOlcek = t < d.damga ? 0 : 1 + 0.9 * (1 - cikis(dg));
  const sarsinti = t >= d.damga && t < d.damga + 0.25 ? Math.sin((t - d.damga) * 70) * 3 * (1 - (t - d.damga) / 0.25) : 0;
  const tarih = kay(t, d.damga + 0.15, 20);
  const satirlar = d.alinti.satirlar;
  const toplam = satirlar.reduce((n, r) => n + r.length, 0);
  // Alıntı anlatımla birlikte yazılır; yazılmamış harfler soluk durur (panel hiç boş görünmez).
  const yazildi = Math.round(toplam * okunan(s, d.tAlinti, s.bit, t));
  const imlec = t < d.tSec && Math.floor(t * 3) % 2 === 0;
  const sec = cikis(ilerle(t, d.tSec, 0.3));
  let kalan = yazildi;

  return (
    <>
      <Pencere baslik={s.veri.pencere ?? ''} h={d.H1} etkin={etkinlik(yol, 0, t)}>
        <div
          style={{
            position: 'absolute',
            left: IC.sol,
            top: ADRES_Y,
            width: IC.en,
            height: ADRES_H,
            boxSizing: 'border-box',
            borderRadius: 16,
            border: `2px solid ${R.cizgi}`,
            background: R.zemin,
          }}
        >
          <Simge ad="kilit" boyut={30} renk={R.nane} style={{position: 'absolute', left: 18, top: 15}} />
          <div
            style={{
              position: 'absolute',
              left: 64,
              top: 0,
              width: DAR - 66,
              lineHeight: `${ADRES_H - 4}px`,
              fontSize: 30,
              fontWeight: 700,
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              maskImage: 'linear-gradient(to right, black 88%, transparent)',
              WebkitMaskImage: 'linear-gradient(to right, black 88%, transparent)',
            }}
          >
            <span style={{color: R.yazi}}>{adres.slice(0, Math.min(yazilan, v.alan.length))}</span>
            <span style={{color: R.soluk}}>{adres.slice(v.alan.length, Math.max(v.alan.length, yazilan))}</span>
          </div>
        </div>
        <IzleyenYazi
          satirlar={d.ad.satirlar}
          oran={adOran}
          style={{position: 'absolute', left: IC.sol, top: AD_Y, fontSize: d.ad.punto, lineHeight: `${d.ad.lh}px`, fontWeight: 800, color: R.yazi}}
        />
        <div
          style={{
            position: 'absolute',
            left: IC.sol,
            top: d.kutuY,
            width: IC.en,
            height: KUTU_H,
            boxSizing: 'border-box',
            borderRadius: 20,
            background: R.tusUst,
            border: `3px solid ${t >= d.damga ? R.nane : R.cizgi}`,
            boxShadow: `0 6px 0 ${R.tusAlt}`,
          }}
        >
          <div style={{position: 'absolute', left: 20, top: (KUTU_H - 6 - DAMGA_H) / 2, display: 'flex', alignItems: 'center', gap: 24}}>
            <div
              data-kutu="damga"
              style={{
                width: damgaEni(v),
                boxSizing: 'border-box',
                height: DAMGA_H,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                border: `3px solid ${R.nane}`,
                borderRadius: 10,
                color: R.koyuYazi,
                background: R.nane,
                fontSize: 28,
                fontWeight: 800,
                letterSpacing: '0.06em',
                whiteSpace: 'nowrap',
                // Sol kenarına basılır: ortasından büyüse sol ucu karenin dışına taşardı.
                transformOrigin: '0 50%',
                transform: `rotate(-4deg) scale(${damgaOlcek}) translateX(${sarsinti}px)`,
                opacity: t < d.damga ? 0 : cikis(dg * 2),
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
        </div>
      </Pencere>
      <Pencere baslik={d.oyun} y={d.yB} h={d.H2} kaydir={panelGiris(t, d.tAlinti)} etkin={etkinlik(yol, 1, t)}>
        <div style={{position: 'absolute', left: IC.sol, top: IC.ust, width: 10, height: yaziBoyu(d.alinti), borderRadius: 5, background: R.kehribar}} />
        <div style={{position: 'absolute', left: ALINTI_SOL, top: IC.ust, fontSize: d.alinti.punto, lineHeight: `${d.alinti.lh}px`, fontWeight: 700, whiteSpace: 'pre'}}>
          {satirlar.map((satir, r) => {
            const n = Math.max(0, Math.min(satir.length, kalan));
            kalan -= satir.length;
            const son = n > 0 && n < satir.length;
            return (
              <div key={r}>
                <span
                  style={{
                    color: R.yazi,
                    background: sec > 0 ? `rgba(59,108,246,${0.6 * sec})` : 'transparent',
                    borderRadius: 6,
                  }}
                >
                  {satir.slice(0, n)}
                </span>
                {imlec && son ? <span style={{display: 'inline-block', width: 0, position: 'relative'}}><span style={{position: 'absolute', left: 2, top: 8, width: 5, height: d.alinti.lh - 14, background: R.kehribar}} /></span> : null}
                <span style={{color: R.cizgi}}>{satir.slice(n)}</span>
              </div>
            );
          })}
        </div>
      </Pencere>
    </>
  );
};

// Kamera: adres çubuğu ve kaynak adı yakından, alıntı gelince ikinci panel, sonra bütün, en son seçilen alıntıya yakın.
export const kaynakKamera = (s: Sahne, haber: Haber): Bakis[] => {
  const d = duzen(s, haber);
  const out: Bakis[] = [bakis(s.bas, ADRES_Y + 60, 1.1, 0, 0)];
  const k1 = ilkKelime(s, s.bas + 0.6, d.tAlinti - 0.6);
  if (k1 !== undefined) out.push(bakis(k1, (AD_Y + d.kutuY + KUTU_H) / 2, 1.05, d.kutuY, 0));
  out.push(kenardan(d.tAlinti, d.yB, 1, 1));
  if (d.tGenel !== undefined) out.push(genel(d.tGenel, d.tuval));
  if (d.tSec < s.bit - 0.6) out.push(bakis(d.tSec, d.yB + IC.ust + yaziBoyu(d.alinti) / 2, 1.1, d.yB, 1));
  return out;
};

export const kaynakTuval = (s: Sahne, haber: Haber): Tuval => duzen(s, haber).tuval;

export const kaynakEngeller = (s: Sahne, haber: Haber): Engel[] => {
  const d = duzen(s, haber);
  const {v} = d;
  const tarihEni = v.tarih ? 24 + 68 + yaziGenisligi(v.tarih, 22, 800, 0.08) * D.altyazi.pay : 0;
  return [
    engel(IC.sol, ADRES_Y, DAR, ADRES_H),
    ...yaziEngeli(v.ad, d.ad.punto, 800, d.ad.en, IC.sol, AD_Y, d.ad.lh),
    // Döndürülmüş damga kutusundan birkaç piksel taşar.
    engel(IC.sol + 14, d.kutuY + 8, damgaEni(v) + tarihEni + 12, KUTU_H - 10),
    panelBaslikEngeli(0, d.yB, d.oyun),
    ...yaziEngeli(v.alinti, d.alinti.punto, 700, d.alinti.en, ALINTI_SOL, d.yB + IC.ust, d.alinti.lh),
  ];
};

// Maskot sağ sütunda: pencere kenarı, damga kutusu ve alıntı paneli arasında kameranın baktığı yere konar.
export const kaynakNoktalar = (s: Sahne, haber: Haber): Nokta[] => {
  const d = duzen(s, haber);
  return kenarDuraklari(sahneYolu(s, kaynakKamera(s, haber), d.tuval, kaynakEngeller(s, haber)), [0, d.kutuY, {y: d.yB, bas: d.tAlinti + 0.3}], kaynakEngeller(s, haber));
};
