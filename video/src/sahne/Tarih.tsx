import React from 'react';
import {Pencere} from '../bilesen/Pencere';
import {Simge} from '../bilesen/Simge';
import {Tus} from '../bilesen/Tus';
import type {Tuval} from '../kamera';
import {R} from '../tema';
import type {Engel, Haber, Nokta, Sahne, SahneProps} from '../tipler';
import {basma, cikis, ilerle} from '../zaman';
import {
  type Bakis,
  IC,
  IzleyenYazi,
  PANEL_ARA,
  SUTUN,
  an,
  araKelime,
  bakis,
  belir,
  engel,
  etkinlik,
  genel,
  izOrani,
  kelimeIzi,
  kenarDuraklari,
  kenardan,
  panelBaslikEngeli,
  panelGiris,
  sahneYolu,
  soylenme,
  veri,
  yaziBoyu,
  yaziEngeli,
  yaziSec,
} from './ortak';

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
  goster: number;
};

// Kart ve takvim ızgarası tam genişlik bir tepside: tepsinin üst kenarı maskotun basamağıdır.
const TEPSI_IC = 20;
const KART_X = IC.sol + TEPSI_IC;
const KART_W = 276;
const HUCRE = 48;
const ARA = 7;
const IZGARA_X = SUTUN - 8 - (7 * HUCRE + 6 * ARA);
const BASLIK_H = 36;
const SATIR_H = 44;
// İkinci panel: takvim tuşu ve not.
const SIMGE = 132;
const NOT_SOL = IC.sol + SIMGE + 28;
const NOT_EN = SUTUN - NOT_SOL;

const duzen = (s: Sahne) => {
  const v = veri<TarihVeri>(s);
  const baslik = yaziSec(v.etiket, 62, 800, 2, 36, 760);
  const tepsiY = IC.ust + yaziBoyu(baslik) + 28;
  const ust = tepsiY + TEPSI_IC;
  const haftalar = Math.ceil((v.ilk_haftagunu + v.gun_sayisi) / 7);
  const izgaraH = BASLIK_H + 8 + haftalar * (SATIR_H + ARA) - ARA;
  const kartH = Math.max(300, izgaraH);
  const tepsiH = kartH + 2 * TEPSI_IC + 8;
  const H1 = tepsiY + tepsiH + 40;
  const yB = H1 + PANEL_ARA;
  const not = v.not ? yaziSec(v.not, 52, 700, 3, 36, 600, NOT_EN) : undefined;
  const H2 = not ? IC.ust + Math.max(SIMGE + 10, yaziBoyu(not)) + 40 : 0;
  const kart = an(s, v.goster ?? s.bas);
  // Not anlatımda ilk kelimesi söylenince gelir; gün, kendi sayısı söylenince yanar.
  const notIlk = v.not ? v.not.split(/\s+/)[0] : '';
  const tNot = not ? Math.max(kart + 0.6, soylenme(s, notIlk, kart, s.bit) ?? araKelime(s, kart, s.bit, 0.45) ?? s.bas + 0.5 * (s.bit - s.bas)) : undefined;
  const tGun = Math.max(kart + 0.5, soylenme(s, String(v.gun_bas), tNot ?? kart, s.bit) ?? soylenme(s, String(v.gun_bas), kart, s.bit) ?? kart + 0.9);
  const adim = 0.12;
  const tuval: Tuval = {ust: -2, alt: not ? yB + H2 - 2 : H1 - 2};
  return {v, baslik, tepsiY, ust, tepsiH, kartH, H1, yB, not, H2, kart, tNot, tGun, adim, tuval};
};

const hucre = (d: ReturnType<typeof duzen>, gun: number) => {
  const sira = d.v.ilk_haftagunu + gun - 1;
  return {x: IZGARA_X + (sira % 7) * (HUCRE + ARA), y: d.ust + BASLIK_H + 8 + Math.floor(sira / 7) * (SATIR_H + ARA)};
};

export const Tarih: React.FC<SahneProps> = ({s, t, haber}) => {
  const d = duzen(s);
  const {v} = d;
  const yol = sahneYolu(s, tarihKamera(s, haber), d.tuval);
  const ilkPanel = d.tNot ?? s.bit;
  const baslikOran = izOrani(kelimeIzi(s, v.etiket, s.bas, ilkPanel), t) * (1 - cikis(ilerle(t, ilkPanel, 0.3)));
  const kb = belir(t, d.kart - 0.25);
  const gunMetni = v.gun_bas === v.gun_bit ? String(v.gun_bas) : `${v.gun_bas}–${v.gun_bit}`;
  const gunPunto = Math.min(150, 236 / (0.62 * gunMetni.length));
  const gunler = Array.from({length: v.gun_sayisi}, (_, i) => i + 1);
  const yandi = cikis(ilerle(t, d.tGun, 0.2));

  return (
    <>
      <Pencere baslik={s.veri.pencere ?? ''} h={d.H1} etkin={etkinlik(yol, 0, t)}>
        <IzleyenYazi
          satirlar={d.baslik.satirlar}
          oran={baslikOran}
          style={{position: 'absolute', left: IC.sol, top: IC.ust, fontSize: d.baslik.punto, lineHeight: `${d.baslik.lh}px`, fontWeight: 800, color: R.yazi}}
        />
        <div style={{position: 'absolute', left: IC.sol, top: d.tepsiY, width: IC.en, height: d.tepsiH, boxSizing: 'border-box', borderRadius: 24, background: R.yuzey2, border: `2px solid ${R.cizgi}`}} />
        <Tus
          x={KART_X}
          y={d.ust}
          w={KART_W}
          h={d.kartH}
          derinlik={10}
          basili={basma(t - d.kart) + basma(t - d.tGun)}
          olcek={kb.olcek}
          saydam={kb.saydam}
          yaricap={26}
          kenar={yandi > 0.5 ? R.kehribar : R.cizgi}
          style={{flexDirection: 'column', justifyContent: 'flex-start'}}
        >
          <div style={{width: '100%', height: 76, background: R.kehribar, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 36, fontWeight: 800, letterSpacing: '0.06em', color: R.koyuYazi}}>
            {v.ay_adi}
          </div>
          <div style={{flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: gunPunto, fontWeight: 800, color: yandi > 0.5 ? R.kehribar : R.yazi, whiteSpace: 'nowrap'}}>{gunMetni}</div>
          {v.yil_metin ? <div style={{height: 56, fontSize: 30, fontWeight: 800, letterSpacing: '0.08em', color: R.soluk}}>{v.yil_metin}</div> : null}
        </Tus>
        {v.hafta.map((h, i) => (
          <div key={i} style={{position: 'absolute', left: IZGARA_X + i * (HUCRE + ARA), top: d.ust, width: HUCRE, height: BASLIK_H, textAlign: 'center', fontSize: 22, lineHeight: `${BASLIK_H}px`, fontWeight: 800, color: R.soluk}}>
            {h}
          </div>
        ))}
        {gunler.map((g) => {
          const {x, y} = hucre(d, g);
          const aralikta = g >= v.gun_bas && g <= v.gun_bit;
          const uc = g === v.gun_bas || g === v.gun_bit;
          const an0 = d.tGun + d.adim * (g - v.gun_bas);
          const yan = aralikta ? cikis(ilerle(t, an0, 0.15)) : 0;
          const bs = aralikta ? basma(t - an0) : 0;
          const pop = aralikta && uc ? belir(t, an0).olcek : 1;
          return (
            <div
              key={g}
              style={{
                position: 'absolute',
                left: x,
                top: y,
                width: HUCRE,
                height: SATIR_H,
                boxSizing: 'border-box',
                borderRadius: 10,
                background: yan > 0 ? (uc ? R.kehribar : `rgba(245,184,61,${0.35 * yan})`) : R.tusUst,
                border: `2px solid ${g === v.haber_gunu ? R.secim : yan > 0 ? '#C8912A' : R.cizgi}`,
                boxShadow: `0 ${4 * (1 - bs)}px 0 ${R.tusAlt}`,
                transform: `translateY(${4 * bs}px) scale(${t >= an0 ? pop : 1})`,
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
      </Pencere>
      {d.not && d.tNot !== undefined ? (
        <Pencere baslik={v.etiket} y={d.yB} h={d.H2} kaydir={panelGiris(t, d.tNot)} etkin={etkinlik(yol, 1, t)}>
          <Tus x={IC.sol} y={IC.ust} w={SIMGE} h={SIMGE} derinlik={10} basili={basma(t - d.tGun)} renk={R.kehribar} kenar="#C98A1B" yaricap={26}>
            <Simge ad="takvim" boyut={72} renk={R.koyuYazi} kalinlik={3.2} />
          </Tus>
          <IzleyenYazi
            satirlar={d.not.satirlar}
            oran={izOrani(kelimeIzi(s, v.not, d.tNot, s.bit), t)}
            style={{position: 'absolute', left: NOT_SOL, top: IC.ust + Math.max(0, (SIMGE - yaziBoyu(d.not)) / 2), fontSize: d.not.punto, lineHeight: `${d.not.lh}px`, fontWeight: 700, color: R.yazi}}
          />
        </Pencere>
      ) : null}
    </>
  );
};

// Kamera: başlık yakından, not anlatılınca not paneli, gün söylenince takvime yakın, sonra bütün.
export const tarihKamera = (s: Sahne, _haber: Haber): Bakis[] => {
  const d = duzen(s);
  const out: Bakis[] = [bakis(s.bas, IC.ust + yaziBoyu(d.baslik) / 2 + 60, 1.1, 0, 0)];
  if (d.tNot !== undefined) out.push(kenardan(d.tNot, d.yB, 1, 1));
  out.push(bakis(d.tGun, d.ust + d.kartH / 2, 1.1, d.tepsiY, 0));
  const once = Math.max(d.tGun + 0.8, araKelime(s, d.tGun + 0.3, s.bit, 0.5) ?? d.tGun + 0.8);
  if (once < s.bit - 0.6) out.push(genel(once, d.tuval));
  return out;
};

export const tarihTuval = (s: Sahne, _haber: Haber): Tuval => duzen(s).tuval;

// Başlık, kart, gün adları, numaralı (aralığın ucu olan) hücreler ve not; ara günler boş tuş olduğu için engel sayılmaz.
export const tarihEngeller = (s: Sahne, _haber: Haber): Engel[] => {
  const d = duzen(s);
  const {v} = d;
  const uclar = v.gun_bas === v.gun_bit ? [v.gun_bas] : [v.gun_bas, v.gun_bit];
  return [
    ...yaziEngeli(v.etiket, d.baslik.punto, 800, d.baslik.en, IC.sol, IC.ust, d.baslik.lh),
    engel(KART_X, d.ust, KART_W, d.kartH + 10),
    engel(IZGARA_X, d.ust, 7 * HUCRE + 6 * ARA, BASLIK_H),
    ...uclar.map((g) => {
      const h = hucre(d, g);
      return engel(h.x - 4, h.y - 4, HUCRE + 8, SATIR_H + 8);
    }),
    ...(d.not
      ? [
          panelBaslikEngeli(0, d.yB, v.etiket),
          engel(IC.sol, d.yB + IC.ust, SIMGE, SIMGE + 10),
          ...yaziEngeli(v.not, d.not.punto, 700, d.not.en, NOT_SOL, d.yB + IC.ust + Math.max(0, (SIMGE - yaziBoyu(d.not)) / 2), d.not.lh),
        ]
      : []),
  ];
};

// Maskot sağ sütunda: pencere kenarı, takvim tepsisi ve not paneli arasında kameranın baktığı yere konar.
export const tarihNoktalar = (s: Sahne, haber: Haber): Nokta[] => {
  const d = duzen(s);
  const kenarlar = [0, d.tepsiY, ...(d.tNot !== undefined ? [{y: d.yB, bas: d.tNot + 0.3}] : [])];
  return kenarDuraklari(sahneYolu(s, tarihKamera(s, haber), d.tuval), kenarlar, tarihEngeller(s, haber), 'dur');
};
