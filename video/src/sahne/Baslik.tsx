import React from 'react';
import {Tus} from '../bilesen/Tus';
import {satirlaraBol, yaziGenisligi} from '../olcu';
import {PENCERE, PLATFORM_RENK, R, TUR_RENK, mutlak} from '../tema';
import type {Engel, Haber, Nokta, Sahne, SahneProps} from '../tipler';
import {basma, cikis, ilerle} from '../zaman';
import {Cip, IC, belir, engel, tekSatirEngeli, veri, yaziEngeli, zemin} from './ortak';

type BaslikVeri = {ust_etiket: string; baslik: string; vurgu: {metin: string; goster: number}[]; tuslar: string[]};

const TUS = 130;
const ARA = 24;
// Üç satırlık başlık 464'te biter; tuşa konan maskot (108) başlığa değmesin.
const TUS_Y = 580;
const BASLIK_Y = 236;
const BASLIK_SATIR = 76;

const CIP_ARA = 12;
type CipBilgi = {metin: string; renk: string; dolu?: boolean; tarih?: boolean; w: number};
const cip = (metin: string, renk: string, ek: {dolu?: boolean; tarih?: boolean} = {}): CipBilgi => ({
  metin,
  renk,
  ...ek,
  w: 36 + yaziGenisligi(metin, 22, 800, 0.08) * 1.03,
});

// Çipler tek satırdır (ikinci satır üst etikete biner): sığmazsa önce tarih, sonra sondaki platformlar düşer.
const ciplar = (haber: Haber): CipBilgi[] => {
  const liste = [
    cip(haber.tur_etiket, TUR_RENK[haber.tur] ?? R.baglanti, {dolu: true}),
    ...haber.platformlar.map((p) => cip(p.ad, PLATFORM_RENK[p.renk] ?? R.soluk)),
    cip(haber.tarih_metin, R.soluk, {tarih: true}),
  ];
  const en = () => liste.reduce((t, c) => t + c.w, 0) + CIP_ARA * (liste.length - 1);
  while (liste.length > 1 && en() > IC.en) {
    const tarih = liste.findIndex((c) => c.tarih);
    liste.splice(tarih >= 0 ? tarih : liste.length - 1, 1);
  }
  return liste;
};

const tuslarYerlesim = (s: Sahne) => {
  const v = veri<BaslikVeri>(s);
  const n = v.tuslar.length;
  const toplam = n * TUS + (n - 1) * ARA;
  const x0 = (PENCERE.w - 2 * PENCERE.cerceve - toplam) / 2;
  const adim = Math.min(0.9, (s.bit - 0.8 - s.bas - 1.0) / Math.max(1, n - 1));
  return v.tuslar.map((harf, k) => ({harf, x: x0 + k * (TUS + ARA), belir: s.bas + 0.5 + 0.08 * k, bas: s.bas + 1.0 + k * Math.max(0.45, adim)}));
};

// Başlıktaki vurgu öbeğinin kelime sıraları (büyük/küçük harf ve noktalama farkı gözetmeden).
const sade = (k: string) => k.toLocaleLowerCase('tr').replace(/[^\p{L}\p{N}]/gu, '');
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

export const Baslik: React.FC<SahneProps> = ({s, t, haber}) => {
  const v = veri<BaslikVeri>(s);
  const kelimeler = v.baslik.split(/\s+/).filter(Boolean);
  const vurgular = vurguSiralari(kelimeler, v.vurgu);
  // Satır sonları ölçü tablosundan: maskotun kaçtığı satırlar ekrandakilerle aynı.
  const satirBasi = new Set<number>();
  let sira = 0;
  for (const satir of satirlaraBol(v.baslik, 66, 800, 760)) {
    satirBasi.add(sira);
    sira += satir.split(' ').length;
  }
  const ust = cikis(ilerle(t, s.bas + 0.2, 0.3));

  return (
    <>
      <div style={{position: 'absolute', left: IC.sol, top: IC.ust, width: IC.en, display: 'flex', gap: CIP_ARA}}>
        {ciplar(haber).map((c, k) => {
          const b = belir(t, s.bas + 0.15 + 0.08 * k);
          return (
            <Cip key={k} renk={c.renk} dolu={c.dolu} style={{opacity: b.saydam, transform: `scale(${b.olcek})`}}>
              {c.metin}
            </Cip>
          );
        })}
      </div>
      {v.ust_etiket ? (
        <div
          style={{
            position: 'absolute',
            left: IC.sol,
            top: 186,
            width: IC.en,
            fontSize: 30,
            lineHeight: '40px',
            fontWeight: 800,
            letterSpacing: '0.06em',
            color: R.kehribar,
            opacity: ust,
            transform: `translateX(${(1 - ust) * -30}px)`,
            whiteSpace: 'nowrap',
          }}
        >
          {v.ust_etiket}
        </div>
      ) : null}
      <div style={{position: 'absolute', left: IC.sol, top: BASLIK_Y, width: 760, fontSize: 66, lineHeight: `${BASLIK_SATIR}px`, fontWeight: 800, color: R.yazi, whiteSpace: 'pre'}}>
        {kelimeler.map((k, j) => {
          const u = cikis(ilerle(t, s.bas + 0.3 + 0.07 * j, 0.3));
          const vu = vurgular.get(j);
          const p = vu ? cikis(ilerle(t, vu.goster + 0.07 * vu.sira, 0.16)) : 0;
          return (
            <React.Fragment key={j}>
              {j > 0 ? (satirBasi.has(j) ? '\n' : ' ') : null}
              <span
                style={{
                  display: 'inline-block',
                  opacity: u,
                  transform: `translateY(${(1 - u) * 26}px)`,
                  padding: '0 6px',
                  margin: '0 -6px',
                  borderRadius: 10,
                  backgroundImage: `linear-gradient(${R.secim}, ${R.secim})`,
                  backgroundRepeat: 'no-repeat',
                  backgroundSize: `${p * 100}% 100%`,
                  color: p > 0.5 ? '#FFFFFF' : R.yazi,
                }}
              >
                {k}
              </span>
            </React.Fragment>
          );
        })}
      </div>
      {tuslarYerlesim(s).map((k) => {
        const b = belir(t, k.belir);
        const d = basma(t - k.bas);
        const basildi = t >= k.bas + 0.04;
        return (
          <Tus
            key={k.x}
            x={k.x}
            y={TUS_Y}
            w={TUS}
            h={TUS}
            derinlik={10}
            basili={d}
            olcek={b.olcek}
            saydam={b.saydam}
            renk={basildi ? R.secim : R.tusUst}
            kenar={basildi ? R.secimKoyu : R.cizgi}
            yaricap={24}
          >
            <span style={{fontSize: 72, fontWeight: 800, color: basildi ? '#FFFFFF' : R.yazi}}>{k.harf}</span>
          </Tus>
        );
      })}
    </>
  );
};

export const baslikNoktalar = (s: Sahne, _haber: Haber): Nokta[] =>
  tuslarYerlesim(s).map((k) => ({t: k.bas, x: mutlak(k.x + TUS / 2, 0).x, y: TUS_Y, eylem: 'bas' as const, zemin: zemin(k.x, TUS)}));

// Çip satırı, üst etiket, başlık satırları ve tuşlar.
export const baslikEngeller = (s: Sahne, haber: Haber): Engel[] => {
  const v = veri<BaslikVeri>(s);
  const cipler = ciplar(haber);
  const cipEni = cipler.reduce((t, c) => t + c.w, 0) + CIP_ARA * (cipler.length - 1);
  return [
    engel(IC.sol, IC.ust, cipEni, 44),
    ...(v.ust_etiket ? [tekSatirEngeli(v.ust_etiket, 30, 800, IC.en, IC.sol, 186, 40, 0.06)] : []),
    ...yaziEngeli(v.baslik, 66, 800, 760, IC.sol, BASLIK_Y, BASLIK_SATIR),
    ...tuslarYerlesim(s).map((k) => engel(k.x, TUS_Y, TUS, TUS + 10)),
  ];
};
