import React from 'react';
import {Pencere} from '../bilesen/Pencere';
import {Tus} from '../bilesen/Tus';
import {SAHNE_YARI, type Tuval} from '../kamera';
import {yaziGenisligi} from '../olcu';
import {PLATFORM_RENK, R} from '../tema';
import type {Engel, Haber, Nokta, Sahne, SahneProps} from '../tipler';
import {basma, basmalar, cikis, ilerle, yay} from '../zaman';
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
  degisim,
  engel,
  etkinlik,
  kelimeIzi,
  kenarDuraklari,
  kenardan,
  izOrani,
  ortakYazi,
  panelBaslikEngeli,
  panelGiris,
  sade,
  sahneYolu,
  siganPunto,
  soylenme,
  sonKelimeBitis,
  veri,
  yaziBoyu,
  yaziEngeli,
  yaziSec,
} from './ortak';

type PlatformVeri = {
  baslik: string;
  platformlar: {ad: string; renk: string; goster: number}[];
  not: string;
  sayilar: {deger: string; etiket: string; goster: number}[];
};

// Tepsi: platform tuşları ile sayı karolarını taşıyan tam genişlik kutu; üst kenarı maskotun basamağıdır.
const TEPSI_IC = 20;
const TUS_H = 104;
const TUS_ARA = 16;
const KARO_H = 176;
const KARO_ARA = 20;
const ICERIK_SOL = IC.sol + TEPSI_IC;
const ICERIK_EN = SUTUN - TEPSI_IC - ICERIK_SOL;
// İkinci panel: anlatılan sayı büyük kehribar blokta, etiketi yanında; sayı değiştikçe ikisi birlikte değişir.
const BLOK_W = 300;
const BLOK_H = 220;
const ETIKET_SOL = IC.sol + BLOK_W + 32;
const ETIKET_EN = SUTUN - ETIKET_SOL;
const SERIT = 26;

const duzen = (s: Sahne, _haber: Haber) => {
  const v = veri<PlatformVeri>(s);
  const baslik = v.baslik ? yaziSec(v.baslik, 64, 800, 2, 46, 760) : undefined;
  let y = IC.ust + (baslik ? yaziBoyu(baslik) + 28 : 0);
  const tepsiY = y;
  y += TEPSI_IC;
  // Platform tuşları satırlara dizilir, her satır kendi içinde ortalanır.
  const tuslar: {ad: string; renk: string; goster: number; x: number; y: number; w: number}[] = [];
  let x = 0;
  let satir: typeof tuslar = [];
  const satiriKapat = () => {
    if (!satir.length) return;
    const son = satir[satir.length - 1];
    const kay0 = (ICERIK_EN - (son.x + son.w)) / 2;
    for (const k of satir) k.x += kay0;
    tuslar.push(...satir);
    satir = [];
    x = 0;
    y += TUS_H + TUS_ARA;
  };
  for (const p of v.platformlar) {
    const w = Math.min(ICERIK_EN, Math.max(150, Math.ceil(yaziGenisligi(p.ad, 40, 800, 0.03) * 1.03) + 64));
    if (x > 0 && x + w > ICERIK_EN) satiriKapat();
    satir.push({...p, goster: an(s, p.goster), x, y, w});
    x += w + TUS_ARA;
  }
  satiriKapat();
  const n = v.sayilar.length;
  const karoW = (ICERIK_EN - (n - 1) * KARO_ARA) / Math.max(1, n);
  const karoY = y;
  if (n) y += KARO_H + TUS_ARA;
  const sayilar = v.sayilar.map((m, k) => ({...m, goster: an(s, m.goster), x: ICERIK_SOL + k * (karoW + KARO_ARA)}));
  const tepsiH = y - TUS_ARA + TEPSI_IC - tepsiY;
  const tepsi = tuslar.length || n;
  const H1 = (tepsi ? tepsiY + tepsiH : y) + 40;
  const yB = H1 + PANEL_ARA;
  const degerPunto = Math.min(...v.sayilar.map((m) => siganPunto(m.deger, 140, 800, BLOK_W - 40, 1, 56)), 140);
  const etiketler = ortakYazi(
    v.sayilar.map((m) => m.etiket),
    52,
    800,
    3,
    24,
    200,
    ETIKET_EN,
  );
  const seritY = IC.ust + BLOK_H + 32;
  const H2 = n ? seritY + SERIT + 40 : 0;
  const not = v.not ? yaziSec(v.not, 52, 700, 3, 36, 760) : undefined;
  const H3 = not ? IC.ust + yaziBoyu(not) + 40 : 0;
  // Sayılar ikinci panelde anlatılır; not, sayılar bitince aynı yere gelen panelde (sayı yoksa anlatımın ortasında).
  const tB = n ? sayilar[0].goster : undefined;
  const sonSayi = n ? sayilar[n - 1].goster : undefined;
  const tC = not
    ? sonSayi !== undefined
      ? Math.min(s.bit - 1, Math.max(sonSayi + 0.9, sonKelimeBitis(s) - 0.4))
      : (araKelime(s, s.bas + 0.9, s.bit, 0.5) ?? s.bas + 0.5 * (s.bit - s.bas))
    : undefined;
  const cVar = tC !== undefined && (sonSayi === undefined || tC >= sonSayi + 0.6);
  const altBoy = Math.max(H2, cVar ? H3 : 0);
  const tuval: Tuval = {ust: -2, alt: altBoy ? yB + altBoy - 2 : H1 - 2};
  // Not anlatımda geçiyorsa söylendikçe işaretlenir.
  const notSoz = !!v.not && v.not.split(/\s+/).some((k) => sade(k).length >= 4 && soylenme(s, k, s.bas, s.bit) !== undefined);
  return {v, baslik, tepsiY, tepsiH, tepsi, tuslar, karoY, karoW, sayilar, H1, yB, degerPunto, etiketler, seritY, H2, not, H3, tB, tC: cVar ? tC : undefined, notSoz, tuval};
};

const simdiki = (d: ReturnType<typeof duzen>, t: number) => {
  let k = -1;
  d.sayilar.forEach((m, i) => {
    if (t >= m.goster) k = i;
  });
  return k;
};

export const Platform: React.FC<SahneProps> = ({s, t, haber}) => {
  const d = duzen(s, haber);
  const {v} = d;
  const yol = sahneYolu(s, platformKamera(s, haber), d.tuval);
  const ilk = Math.min(d.tB ?? s.bit, d.tuslar[0]?.goster ?? s.bit, d.tC ?? s.bit);
  const baslikOran = izOrani(kelimeIzi(s, v.baslik, s.bas, ilk), t) * (1 - cikis(ilerle(t, ilk, 0.3)));
  const cur = simdiki(d, t);
  const cGir = d.tC !== undefined ? cikis(ilerle(t, d.tC, 0.3)) : 0;
  const bGir = d.tB !== undefined ? panelGiris(t, d.tB) : undefined;

  return (
    <>
      <Pencere baslik={s.veri.pencere ?? ''} h={d.H1} etkin={etkinlik(yol, 0, t)}>
        {d.baslik ? (
          <IzleyenYazi
            satirlar={d.baslik.satirlar}
            oran={baslikOran}
            style={{position: 'absolute', left: IC.sol, top: IC.ust, fontSize: d.baslik.punto, lineHeight: `${d.baslik.lh}px`, fontWeight: 800, color: R.yazi}}
          />
        ) : null}
        {d.tepsi ? (
          <div
            style={{
              position: 'absolute',
              left: IC.sol,
              top: d.tepsiY,
              width: IC.en,
              height: d.tepsiH,
              boxSizing: 'border-box',
              borderRadius: 24,
              background: R.yuzey2,
              border: `2px solid ${R.cizgi}`,
            }}
          />
        ) : null}
        {d.tuslar.map((k, i) => {
          // Rozetler sahne açılırken soluk dizilir (tepsi boş kalmaz), söylenince yanar.
          const b = belir(t, Math.max(s.bas + 0.15, Math.min(k.goster - 0.3, s.bas + 0.25 + 0.08 * i)));
          const acik = t >= k.goster;
          const renk = PLATFORM_RENK[k.renk] ?? R.soluk;
          return (
            <Tus
              key={i}
              x={ICERIK_SOL + k.x}
              y={k.y}
              w={k.w}
              h={TUS_H}
              derinlik={10}
              basili={basma(t - k.goster)}
              olcek={b.olcek}
              saydam={b.saydam}
              renk={acik ? R.tusUst : R.yuzey}
              kenar={acik ? renk : R.cizgi}
              yaricap={22}
            >
              <span style={{fontSize: 40, fontWeight: 800, letterSpacing: '0.03em', color: acik ? R.yazi : R.soluk, whiteSpace: 'nowrap'}}>{k.ad}</span>
              <div style={{position: 'absolute', left: 0, right: 0, bottom: 0, height: 10, background: renk, opacity: acik ? 1 : 0.35}} />
            </Tus>
          );
        })}
        {d.sayilar.map((m, i) => {
          const acik = t >= m.goster;
          const deger = yay(t - m.goster, 0.45, 18);
          return (
            <Tus
              key={i}
              x={m.x}
              y={d.karoY}
              w={d.karoW}
              h={KARO_H}
              derinlik={10}
              basili={basma(t - m.goster)}
              renk={acik ? R.tusUst : R.yuzey}
              kenar={i === cur ? R.kehribar : R.cizgi}
              yaricap={24}
              style={{flexDirection: 'column', gap: 8, opacity: acik ? 1 : 0.55}}
            >
              <div style={{fontSize: 68, lineHeight: '76px', fontWeight: 800, color: acik ? R.kehribar : R.cizgi, transform: `scale(${acik ? 0.7 + 0.3 * deger : 0.9})`}}>{m.deger}</div>
              <div style={{fontSize: 22, lineHeight: '28px', fontWeight: 700, letterSpacing: '0.04em', color: acik ? R.yazi : R.soluk, textAlign: 'center', padding: '0 12px'}}>{m.etiket}</div>
            </Tus>
          );
        })}
      </Pencere>
      {bGir && d.H2 ? (
        <Pencere
          baslik={v.baslik}
          y={d.yB}
          h={d.H2}
          // Not paneli gelince sayı paneli aşağı kayıp söner.
          kaydir={{dy: bGir.dy + 90 * cGir, saydam: bGir.saydam * (1 - cGir)}}
          etkin={etkinlik(yol, 1, t)}
        >
          <Tus x={IC.sol} y={IC.ust} w={BLOK_W} h={BLOK_H} derinlik={12} basili={basmalar(t, d.sayilar.map((m) => m.goster))} renk={R.kehribar} kenar="#C98A1B" yaricap={30}>
            {cur >= 0
              ? [cur - 1, cur].map((k) => {
                  if (k < 0) return null;
                  const dg = degisim(t, d.sayilar[cur].goster, 70);
                  const hal = k === cur ? (cur > 0 ? dg.yeni : {dy: 0, saydam: 1}) : dg.eski;
                  if (hal.saydam <= 0) return null;
                  return (
                    <div
                      key={k}
                      style={{
                        position: 'absolute',
                        left: 0,
                        right: 0,
                        top: 0,
                        bottom: 0,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: d.degerPunto,
                        fontWeight: 800,
                        color: R.koyuYazi,
                        transform: `translateY(${hal.dy}px)`,
                        opacity: hal.saydam,
                      }}
                    >
                      {d.sayilar[k].deger}
                    </div>
                  );
                })
              : null}
          </Tus>
          {cur >= 0
            ? [cur - 1, cur].map((k) => {
                if (k < 0) return null;
                const y = d.etiketler[k];
                const dg = degisim(t, d.sayilar[cur].goster);
                const hal = k === cur ? (cur > 0 ? dg.yeni : {dy: 0, saydam: 1}) : dg.eski;
                if (hal.saydam <= 0) return null;
                return (
                  <div
                    key={k}
                    style={{
                      position: 'absolute',
                      left: ETIKET_SOL,
                      top: IC.ust + (BLOK_H - yaziBoyu(y)) / 2,
                      fontSize: y.punto,
                      lineHeight: `${y.lh}px`,
                      fontWeight: 800,
                      color: R.yazi,
                      whiteSpace: 'pre',
                      transform: `translateY(${hal.dy}px)`,
                      opacity: hal.saydam,
                    }}
                  >
                    {y.satirlar.join('\n')}
                  </div>
                );
              })
            : null}
          {d.sayilar.map((m, k) => {
            const n = d.sayilar.length;
            const w = (SUTUN - IC.sol - (n - 1) * 12) / n;
            const dolu = k < cur ? 1 : k === cur ? cikis(ilerle(t, m.goster, 0.3)) : 0;
            return (
              <div key={k} style={{position: 'absolute', left: IC.sol + k * (w + 12), top: d.seritY, width: w, height: SERIT, borderRadius: 13, background: R.cizgi, overflow: 'hidden'}}>
                <div style={{width: `${dolu * 100}%`, height: '100%', background: k < cur ? R.nane : R.kehribar}} />
              </div>
            );
          })}
        </Pencere>
      ) : null}
      {d.not && d.tC !== undefined ? (
        <Pencere baslik={v.baslik || (s.veri.pencere ?? '')} y={d.yB} h={d.H3} kaydir={panelGiris(t, d.tC)} etkin={etkinlik(yol, 2, t)}>
          <IzleyenYazi
            satirlar={d.not.satirlar}
            oran={d.notSoz ? izOrani(kelimeIzi(s, v.not, d.tC, s.bit), t) : 0}
            style={{position: 'absolute', left: IC.sol, top: IC.ust, fontSize: d.not.punto, lineHeight: `${d.not.lh}px`, fontWeight: 700, color: R.yazi}}
          />
        </Pencere>
      ) : null}
    </>
  );
};

// Kamera: başlık ve tepsi yakından; ilk sayıda sayı paneli, ikincide bütün, üçüncüde sayı paneline yakın, sonra not paneli.
export const platformKamera = (s: Sahne, haber: Haber): Bakis[] => {
  const d = duzen(s, haber);
  const ustOrta = d.tepsi ? (IC.ust + d.tepsiY + d.tepsiH) / 2 : IC.ust + 80;
  const out: Bakis[] = [bakis(s.bas, ustOrta, 1.1, 0, 0)];
  const bOrta = d.yB + d.H2 / 2;
  // Ana pencere ile sayı paneli birlikte (not paneli henüz yok); ikisi sahneye sığmazsa panelin altı sahnenin altına oturur.
  const ikiPencere = Math.max((d.yB + d.H2 - 4) / 2, d.yB + d.H2 + 24 - SAHNE_YARI / 0.9);
  d.sayilar.forEach((m, k) => {
    const sira = k % 3;
    if (sira === 0) out.push(kenardan(m.goster, d.yB, 1, 1));
    else if (sira === 1) out.push(bakis(m.goster, ikiPencere, 0.9, d.tepsiY));
    else out.push(bakis(m.goster, bOrta, 1.1, d.yB, 1));
  });
  if (!d.sayilar.length && d.tuslar.length) out.push(bakis(d.tuslar[0].goster, d.tepsiY + d.tepsiH / 2, 1.1, d.tepsiY, 0));
  if (d.tC !== undefined) out.push(kenardan(d.tC, d.yB, 1, 2));
  return out;
};

export const platformTuval = (s: Sahne, haber: Haber): Tuval => duzen(s, haber).tuval;

export const platformEngeller = (s: Sahne, haber: Haber): Engel[] => {
  const d = duzen(s, haber);
  const {v} = d;
  return [
    ...(d.baslik ? yaziEngeli(v.baslik, d.baslik.punto, 800, d.baslik.en, IC.sol, IC.ust, d.baslik.lh) : []),
    ...d.tuslar.map((k) => engel(ICERIK_SOL + k.x, k.y, k.w, TUS_H + 10)),
    ...d.sayilar.map((m) => engel(m.x, d.karoY, d.karoW, KARO_H + 10)),
    ...(d.H2 ? [panelBaslikEngeli(0, d.yB, v.baslik), engel(IC.sol, d.yB + IC.ust, BLOK_W, BLOK_H + 12)] : []),
    ...d.etiketler.flatMap((y, k) => yaziEngeli(v.sayilar[k].etiket, y.punto, 800, y.en, ETIKET_SOL, d.yB + IC.ust + (BLOK_H - yaziBoyu(y)) / 2, y.lh)),
    ...(d.not && d.tC !== undefined ? yaziEngeli(v.not, d.not.punto, 700, d.not.en, IC.sol, d.yB + IC.ust, d.not.lh) : []),
  ];
};

// Maskot sağ sütunda: pencere kenarı, tepsi ve alttaki panelin üst kenarı arasında kameranın baktığı yere konar.
export const platformNoktalar = (s: Sahne, haber: Haber): Nokta[] => {
  const d = duzen(s, haber);
  const ilkPanel = Math.min(d.tB ?? Infinity, d.tC ?? Infinity);
  const kenarlar = [0, ...(d.tepsi ? [d.tepsiY] : []), ...(Number.isFinite(ilkPanel) ? [{y: d.yB, bas: ilkPanel + 0.3}] : [])];
  return kenarDuraklari(sahneYolu(s, platformKamera(s, haber), d.tuval), kenarlar, platformEngeller(s, haber), 'dur');
};
