import React from 'react';
import {Pencere} from '../bilesen/Pencere';
import {Tus} from '../bilesen/Tus';
import type {Tuval} from '../kamera';
import {yaziGenisligi} from '../olcu';
import {PLATFORM_RENK, R, TUR_RENK} from '../tema';
import type {Engel, Haber, Nokta, Sahne, SahneProps} from '../tipler';
import {basma, cikis, ilerle} from '../zaman';
import {
  type Bakis,
  Cip,
  DAR,
  IC,
  bakis,
  belir,
  engel,
  etkinlik,
  genel,
  kelimeIzi,
  kenarDuraklari,
  sade,
  sahneYolu,
  soylenme,
  tekSatirEngeli,
  veri,
  yaziBoyu,
  yaziEngeli,
  yaziSec,
} from './ortak';

type BaslikVeri = {ust_etiket: string; baslik: string; vurgu: {metin: string; goster: number}[]; tuslar: string[]};

const TUS = 150;
const TUS_ARA = 24;
const TUS_Y = 188;
// Kehribar şerit: üst etiketi taşır, sağ ucu maskotun basamağıdır.
const SERIT_Y = TUS_Y + TUS + 28;
const SERIT_H = 60;
const BASLIK_Y = SERIT_Y + SERIT_H + 28;

const CIP_ARA = 12;
type CipBilgi = {metin: string; renk: string; dolu?: boolean; tarih?: boolean; w: number};
const cip = (metin: string, renk: string, ek: {dolu?: boolean; tarih?: boolean} = {}): CipBilgi => ({
  metin,
  renk,
  ...ek,
  w: 36 + yaziGenisligi(metin, 22, 800, 0.08) * 1.03,
});

// Çipler tek satırdır ve maskotun sütununa girmez: sığmazsa önce tarih, sonra sondaki platformlar düşer.
const ciplar = (haber: Haber): CipBilgi[] => {
  const liste = [
    cip(haber.tur_etiket, TUR_RENK[haber.tur] ?? R.baglanti, {dolu: true}),
    ...haber.platformlar.map((p) => cip(p.ad, PLATFORM_RENK[p.renk] ?? R.soluk)),
    cip(haber.tarih_metin, R.soluk, {tarih: true}),
  ];
  const en = () => liste.reduce((t, c) => t + c.w, 0) + CIP_ARA * (liste.length - 1);
  while (liste.length > 1 && en() > DAR) {
    const tarih = liste.findIndex((c) => c.tarih);
    liste.splice(tarih >= 0 ? tarih : liste.length - 1, 1);
  }
  return liste;
};

// Başlıktaki vurgu öbeğinin kelime sıraları (büyük/küçük harf ve noktalama farkı gözetmeden).
const vurguSiralari = (kelimeler: string[], vurgu: BaslikVeri['vurgu']) => {
  const sonuc = new Map<number, {goster: number; sira: number}>();
  for (const v of vurgu) {
    const parca = v.metin.split(/\s+/).map(sade);
    for (let i = 0; i + parca.length <= kelimeler.length; i++) {
      if (parca.every((p, j) => sade(kelimeler[i + j]) === p)) {
        parca.forEach((_, j) => sonuc.set(i + j, {goster: v.goster, sira: j}));
        break;
      }
    }
  }
  return sonuc;
};

const duzen = (s: Sahne, haber: Haber) => {
  const v = veri<BaslikVeri>(s);
  const baslik = yaziSec(v.baslik, 72, 800, 3, 66, 760);
  const izler = kelimeIzi(s, v.baslik, s.bas, s.bit);
  const ilkSoz = izler[0] ?? s.bas + 1.5;
  // Tuşlar oyun adının kelimeleri söylenirken basılır (R, S, S = Rainbow Six Siege); bulunamazsa başlığa kadar yayılır.
  const oyunKelime = haber.oyun.split(/\s+/).filter(Boolean);
  const n = v.tuslar.length;
  const x0 = IC.sol + (DAR - (n * TUS + (n - 1) * TUS_ARA)) / 2;
  let arama = s.bas;
  const tuslar = v.tuslar.map((harf, k) => {
    const bulunan = oyunKelime[k] ? soylenme(s, oyunKelime[k], arama, ilkSoz + 0.05) : undefined;
    const yedek = s.bas + 0.5 + ((ilkSoz - 0.3 - s.bas - 0.5) * k) / Math.max(1, n - 1);
    const bas = Math.max(s.bas + 0.35, bulunan ?? yedek);
    arama = bas + 0.05;
    return {harf, x: x0 + k * (TUS + TUS_ARA), belir: s.bas + 0.1 + 0.06 * k, bas};
  });
  const etiket = v.ust_etiket || haber.tur_etiket;
  const H = BASLIK_Y + yaziBoyu(baslik) + 40;
  const tuval: Tuval = {ust: -2, alt: H - 2};
  return {v, baslik, izler, tuslar, etiket, cipler: ciplar(haber), H, tuval};
};

export const Baslik: React.FC<SahneProps> = ({s, t, haber}) => {
  const d = duzen(s, haber);
  const yol = sahneYolu(s, baslikKamera(s, haber), d.tuval, baslikEngeller(s, haber));
  const vurgular = vurguSiralari(d.v.baslik.split(/\s+/).filter(Boolean), d.v.vurgu);
  const serit = cikis(ilerle(t, s.bas + 0.2, 0.3));
  let j = 0;

  return (
    <Pencere baslik={s.veri.pencere ?? ''} h={d.H} etkin={etkinlik(yol, 0, t)}>
      <div style={{position: 'absolute', left: IC.sol, top: IC.ust, width: DAR, display: 'flex', gap: CIP_ARA}}>
        {d.cipler.map((c, k) => {
          const b = belir(t, s.bas + 0.15 + 0.08 * k);
          return (
            <Cip key={k} renk={c.renk} dolu={c.dolu} style={{opacity: b.saydam, transform: `scale(${b.olcek})`}}>
              {c.metin}
            </Cip>
          );
        })}
      </div>
      {d.tuslar.map((k) => {
        const b = belir(t, k.belir);
        const basildi = t >= k.bas + 0.04;
        return (
          <Tus
            key={k.x}
            x={k.x}
            y={TUS_Y}
            w={TUS}
            h={TUS}
            derinlik={12}
            basili={basma(t - k.bas)}
            olcek={b.olcek}
            saydam={b.saydam}
            renk={basildi ? R.secim : R.tusUst}
            kenar={basildi ? R.secimKoyu : R.cizgi}
            yaricap={28}
          >
            <span style={{fontSize: 84, fontWeight: 800, color: basildi ? '#FFFFFF' : R.yazi}}>{k.harf}</span>
          </Tus>
        );
      })}
      <div
        style={{
          position: 'absolute',
          left: IC.sol,
          top: SERIT_Y,
          width: IC.en,
          height: SERIT_H,
          borderRadius: 14,
          background: R.kehribar,
          boxShadow: `0 6px 0 ${R.tusAlt}`,
          transformOrigin: '0 50%',
          transform: `scaleX(${0.2 + 0.8 * serit})`,
          opacity: serit,
        }}
      >
        <div style={{position: 'absolute', left: 20, top: 0, lineHeight: `${SERIT_H}px`, fontSize: 30, fontWeight: 800, letterSpacing: '0.06em', color: R.koyuYazi, whiteSpace: 'nowrap'}}>
          {d.etiket}
        </div>
      </div>
      <div style={{position: 'absolute', left: IC.sol, top: BASLIK_Y, fontSize: d.baslik.punto, lineHeight: `${d.baslik.lh}px`, fontWeight: 800, whiteSpace: 'pre'}}>
        {d.baslik.satirlar.map((satir, r) => (
          <div key={r}>
            {satir.split(' ').map((k, q) => {
              const i = j++;
              const an = d.izler[i] ?? s.bas;
              // Kelime söylenene kadar soluk durur (pencere boş kalmaz), söylenince beyaza döner ve yerine oturur.
              const u = cikis(ilerle(t, an, 0.25));
              const vu = vurgular.get(i);
              const p = vu ? cikis(ilerle(t, vu.goster + 0.07 * vu.sira, 0.16)) : 0;
              return (
                <React.Fragment key={q}>
                  {q ? ' ' : ''}
                  <span
                    style={{
                      display: 'inline-block',
                      transform: `translateY(${(1 - u) * 18}px)`,
                      padding: '0 6px',
                      margin: '0 -6px',
                      borderRadius: 10,
                      backgroundImage: `linear-gradient(${R.secim}, ${R.secim})`,
                      backgroundRepeat: 'no-repeat',
                      backgroundSize: `${p * 100}% 100%`,
                      color: p > 0.5 ? '#FFFFFF' : u > 0.5 ? R.yazi : R.cizgi,
                    }}
                  >
                    {k}
                  </span>
                </React.Fragment>
              );
            })}
          </div>
        ))}
      </div>
    </Pencere>
  );
};

// Kamera: tuşlara yakın başlar, başlık söylenmeye başlayınca başlığa, vurguda vurgu satırına iner, sonra bütünü gösterir
// (kapak karesi en erken sahne sonundan 0.6 sn önce alınır, o an kamera bütün başlıktadır: video_uret.py kapak_karesi).
export const baslikKamera = (s: Sahne, haber: Haber): Bakis[] => {
  const d = duzen(s, haber);
  const baslikOrta = BASLIK_Y + yaziBoyu(d.baslik) / 2;
  const out: Bakis[] = [bakis(s.bas, TUS_Y + TUS / 2, 1.1, 0, 0)];
  const ilk = d.izler[0];
  if (ilk !== undefined && ilk < s.bit - 1.2) out.push(bakis(ilk, baslikOrta, 1.1, SERIT_Y, 0));
  const vurgu = d.v.vurgu.map((v) => v.goster).filter((g) => g > (ilk ?? s.bas) + 0.6 && g < s.bit - 1.2)[0];
  if (vurgu !== undefined) out.push(bakis(vurgu, baslikOrta + 40, 1.05, SERIT_Y, 0));
  const kapak = s.bit - 0.6 - 0.35;
  const son = Math.min(kapak, Math.max((vurgu ?? ilk ?? s.bas) + 0.7, d.izler[d.izler.length - 1] ?? s.bas));
  if (son > s.bas + 0.6) out.push(genel(son, d.tuval));
  return out;
};

export const baslikTuval = (s: Sahne, haber: Haber): Tuval => duzen(s, haber).tuval;

// Çip satırı, tuşlar, şerit yazısı ve başlık satırları.
export const baslikEngeller = (s: Sahne, haber: Haber): Engel[] => {
  const d = duzen(s, haber);
  const cipEni = d.cipler.reduce((t, c) => t + c.w, 0) + CIP_ARA * (d.cipler.length - 1);
  return [
    engel(IC.sol, IC.ust, cipEni, 44),
    ...d.tuslar.map((k) => engel(k.x, TUS_Y, TUS, TUS + 12)),
    tekSatirEngeli(d.etiket, 30, 800, IC.en - 20, IC.sol + 20, SERIT_Y, SERIT_H, 0.06),
    ...yaziEngeli(d.v.baslik, d.baslik.punto, 800, d.baslik.en, IC.sol, BASLIK_Y, d.baslik.lh),
  ];
};

// Maskot pencerenin üst kenarından kehribar şeridin sağ ucuna iner (ikisi de yazıların sağındaki sütunda).
export const baslikNoktalar = (s: Sahne, haber: Haber): Nokta[] => {
  const d = duzen(s, haber);
  return kenarDuraklari(sahneYolu(s, baslikKamera(s, haber), d.tuval, baslikEngeller(s, haber)), [0, SERIT_Y], baslikEngeller(s, haber));
};
