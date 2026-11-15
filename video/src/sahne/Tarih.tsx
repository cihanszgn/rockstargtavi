import React from 'react';
import {Simge} from '../bilesen/Simge';
import {Tus} from '../bilesen/Tus';
import {yaziGenisligi} from '../olcu';
import {mutlak, R} from '../tema';
import type {Engel, Haber, Nokta, Sahne, SahneProps} from '../tipler';
import {basma, cikis, ilerle} from '../zaman';
import {Cip, IC, an, belir, engel, kay, satirli, veri, yaziEngeli, zemin} from './ortak';

type TarihVeri = {
  etiket: string;
  not: string;
  hafta: string[];
  gun_bas: number;
  gun_bit: number;
  ay_adi: string;
  yil_metin: string;
  ilk_haftagunu: number;
  gun_sayisi: number;
  haber_gunu: number;
};

// Kartın üstü başlık çubuğunun alt çizgisinden (iç y 76) bir maskot boyu ve biraz aşağıda: karta konan maskot
// çubuğa binmez. İki satırlık not tam iç alanın altında (740) biter.
const KART = {x: IC.sol, y: 192, w: 280, h: 300};
const IZGARA = {x: 356, ust: 192, satir: 236, hucre: 56, yukseklik: 48, ara: 8};
const CIP_Y = 584;
const NOT_Y = 652;

const cipMetni = (v: TarihVeri) => (v.yil_metin ? `${v.ay_adi} ${v.yil_metin}` : v.ay_adi);

const hucre = (v: TarihVeri, gun: number) => {
  const sira = v.ilk_haftagunu + gun - 1;
  return {x: IZGARA.x + (sira % 7) * (IZGARA.hucre + IZGARA.ara), y: IZGARA.satir + Math.floor(sira / 7) * (IZGARA.yukseklik + IZGARA.ara)};
};

const zamanlar = (s: Sahne) => {
  const v = veri<TarihVeri>(s);
  const kart = an(s, (s.veri.goster as number) ?? s.bas);
  const yak = kart + 0.9;
  const adim = 0.12;
  return {kart, yak, adim, son: yak + adim * (v.gun_bit - v.gun_bas)};
};

export const Tarih: React.FC<SahneProps> = ({s, t}) => {
  const v = veri<TarihVeri>(s);
  const z = zamanlar(s);
  const kb = belir(t, z.kart - 0.25);
  const gunMetni = v.gun_bas === v.gun_bit ? String(v.gun_bas) : `${v.gun_bas}–${v.gun_bit}`;
  const gunPunto = Math.min(150, 240 / (0.62 * gunMetni.length));
  const izgara = kay(t, s.bas + 0.35, 30);
  const alt = kay(t, z.son + 0.2, 24);
  const gunler = Array.from({length: v.gun_sayisi}, (_, i) => i + 1);

  return (
    <>
      <Tus x={KART.x} y={KART.y} w={KART.w} h={KART.h} derinlik={10} basili={basma(t - z.kart)} olcek={kb.olcek} saydam={kb.saydam} yaricap={26} style={{flexDirection: 'column', justifyContent: 'flex-start'}}>
        <div style={{width: '100%', height: 74, background: R.kehribar, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 34, fontWeight: 800, letterSpacing: '0.06em', color: R.koyuYazi}}>
          {v.ay_adi}
        </div>
        <div style={{flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: gunPunto, fontWeight: 800, color: R.yazi, whiteSpace: 'nowrap'}}>{gunMetni}</div>
      </Tus>
      <div style={{position: 'absolute', left: 0, top: 0, opacity: izgara.saydam, transform: `translateY(${izgara.dy}px)`}}>
        {v.hafta.map((h, i) => (
          <div
            key={i}
            style={{
              position: 'absolute',
              left: IZGARA.x + i * (IZGARA.hucre + IZGARA.ara),
              top: IZGARA.ust,
              width: IZGARA.hucre,
              height: 36,
              textAlign: 'center',
              fontSize: 22,
              lineHeight: '36px',
              fontWeight: 800,
              color: R.soluk,
            }}
          >
            {h}
          </div>
        ))}
        {gunler.map((g) => {
          const {x, y} = hucre(v, g);
          const aralikta = g >= v.gun_bas && g <= v.gun_bit;
          const uc = g === v.gun_bas || g === v.gun_bit;
          const yan = aralikta ? cikis(ilerle(t, z.yak + z.adim * (g - v.gun_bas), 0.15)) : 0;
          const d = aralikta ? basma(t - z.yak - z.adim * (g - v.gun_bas)) : 0;
          return (
            <div
              key={g}
              style={{
                position: 'absolute',
                left: x,
                top: y,
                width: IZGARA.hucre,
                height: IZGARA.yukseklik,
                boxSizing: 'border-box',
                borderRadius: 10,
                background: yan > 0 ? (uc ? R.kehribar : `rgba(245,184,61,${0.35 * yan})`) : R.tusUst,
                border: `2px solid ${g === v.haber_gunu ? R.secim : yan > 0 ? '#C8912A' : R.cizgi}`,
                boxShadow: `0 ${4 * (1 - d)}px 0 ${R.tusAlt}`,
                transform: `translateY(${4 * d}px)`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 24,
                fontWeight: 800,
                color: R.koyuYazi,
                opacity: uc && yan > 0 ? 1 : aralikta ? 0.6 + 0.4 * yan : 0.55,
              }}
            >
              {/* Yalnız haberde geçen günler yazılır; takvimin geri kalanı boş tuştur. */}
              {uc && yan > 0 ? g : null}
            </div>
          );
        })}
      </div>
      <div style={{position: 'absolute', left: IC.sol, top: CIP_Y, display: 'flex', gap: 12, opacity: alt.saydam, transform: `translateY(${alt.dy}px)`}}>
        <Cip renk={R.kehribar} style={{height: 56, fontSize: 26}}>
          <Simge ad="takvim" boyut={26} renk={R.kehribar} />
          {cipMetni(v)}
        </Cip>
      </div>
      {v.not ? (
        <div style={{position: 'absolute', left: IC.sol, top: NOT_Y, width: 760, fontSize: 36, lineHeight: '44px', fontWeight: 700, color: R.yazi, whiteSpace: 'pre', opacity: alt.saydam, transform: `translateY(${alt.dy}px)`}}>
          {satirli(v.not, 36, 700, 760)}
        </div>
      ) : null}
    </>
  );
};

export const tarihNoktalar = (s: Sahne, _haber: Haber): Nokta[] => {
  const v = veri<TarihVeri>(s);
  const z = zamanlar(s);
  const ilk = hucre(v, v.gun_bas);
  const noktalar: Nokta[] = [
    {t: z.kart, x: mutlak(KART.x + KART.w / 2, 0).x, y: KART.y, eylem: 'bas', zemin: zemin(KART.x, KART.w)},
    {t: z.yak, x: mutlak(ilk.x + IZGARA.hucre / 2, 0).x, y: ilk.y, eylem: 'bas'},
  ];
  if (v.gun_bit !== v.gun_bas) {
    const son = hucre(v, v.gun_bit);
    noktalar.push({t: Math.max(z.son, z.yak + 0.5), x: mutlak(son.x + IZGARA.hucre / 2, 0).x, y: son.y, eylem: 'bas'});
  }
  return noktalar;
};

// Kart, gün adları ve numaralı (aralığın ucu olan) hücreler; ara günler boş tuş olduğu için engel sayılmaz.
export const tarihEngeller = (s: Sahne, _haber: Haber): Engel[] => {
  const v = veri<TarihVeri>(s);
  const uclar = v.gun_bas === v.gun_bit ? [v.gun_bas] : [v.gun_bas, v.gun_bit];
  return [
    engel(KART.x, KART.y, KART.w, KART.h + 10),
    engel(IZGARA.x, IZGARA.ust, 7 * IZGARA.hucre + 6 * IZGARA.ara, 36),
    ...uclar.map((g) => {
      const h = hucre(v, g);
      return engel(h.x, h.y, IZGARA.hucre, IZGARA.yukseklik + 4);
    }),
    engel(IC.sol, CIP_Y, 72 + yaziGenisligi(cipMetni(v), 26, 800, 0.08) * 1.03, 56),
    ...(v.not ? yaziEngeli(v.not, 36, 700, 760, IC.sol, NOT_Y, 44) : []),
  ];
};
