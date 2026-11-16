import React from 'react';
import {Pencere} from '../bilesen/Pencere';
import {Simge} from '../bilesen/Simge';
import {Tus} from '../bilesen/Tus';
import {SAHNE_YARI, type Tuval} from '../kamera';
import {yaziGenisligi} from '../olcu';
import {D, R} from '../tema';
import type {Engel, Haber, Nokta, Sahne, SahneProps} from '../tipler';
import {basma, cikis, ilerle, sinirla} from '../zaman';
import {
  type Bakis,
  Cip,
  DAR,
  IC,
  IzleyenYazi,
  type Kenar,
  PANEL_ARA,
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
  siganPunto,
  soylenme,
  veri,
  yaziEngeli,
  yaziSec,
} from './ortak';

type FiyatVeri = {
  durum: string;
  etiket: string;
  bitis: string;
  eski_fiyat: string;
  yeni_fiyat: string;
  indirim: string;
  magazalar: {ad: string; goster: number}[];
  goster: number;
};

// Damga döndürülünce köşeleri ~20 piksel taşar; altındaki kutu o kadar aşağıda başlar.
const DAMGA_Y = IC.ust + 12;
const DAMGA_ARA = 44;
// Fiyat ve bitiş tam genişlik kutularda: kutuların üst kenarı maskotun basamağıdır.
const KUTU_SOL = 28;
const ARA = 22;
const KUTU_ARA = 24;
// Mağazalar ikinci panelde iki sütun.
const MAGAZA_H = 88;
const MAGAZA_ARA = 16;
const MAGAZA_W = (DAR - MAGAZA_ARA) / 2;
// Mağaza paneli yoksa damga ve kutular büyür: ana pencere sahnenin bu kadarını doldurur.
const HEDEF_H = 620;

const cipEni = (metin: string, p: number) => 40 + yaziGenisligi(metin, p, 800, 0.04) * D.altyazi.pay;

// Fiyat satırı (eski fiyat, ok, yeni fiyat, indirim çipi) kutuya sığan en büyük puntoda.
const fiyatSatiri = (v: FiyatVeri, enCok: number, ok: number) => {
  const en = (p: number) => {
    const parca = [
      v.eski_fiyat ? yaziGenisligi(v.eski_fiyat, p, 800) * D.altyazi.pay : 0,
      v.eski_fiyat && v.yeni_fiyat ? ok : 0,
      v.yeni_fiyat ? yaziGenisligi(v.yeni_fiyat, p, 800) * D.altyazi.pay : 0,
      v.indirim ? cipEni(v.indirim, Math.round(p * 0.55)) : 0,
    ].filter((w) => w > 0);
    return parca.reduce((a, b) => a + b, 0) + ARA * Math.max(0, parca.length - 1);
  };
  let p = enCok;
  while (p > 40 && en(p) > DAR - KUTU_SOL - 12) p -= 2;
  return {punto: p, en: en(p)};
};

const olculer = (o: number) => ({
  damgaH: Math.round(124 * o),
  damgaIdeal: Math.round(64 * o),
  kutuH: Math.round(148 * o),
  fiyatIdeal: Math.round(72 * o),
  ok: Math.round(52 * o),
  bitisH: Math.round(128 * o),
  bitisIdeal: Math.round(46 * o),
  saat: Math.round(92 * o),
});

const duzen = (s: Sahne, haber: Haber) => {
  const v = veri<FiyatVeri>(s);
  const renk = v.durum === 'indirim' ? R.pembe : R.nane;
  const fiyatVar = Boolean(v.eski_fiyat || v.yeni_fiyat || v.indirim);
  const yerlesim = (m: ReturnType<typeof olculer>) => {
    const kutuY = DAMGA_Y + m.damgaH + DAMGA_ARA;
    const bitisY = fiyatVar ? kutuY + m.kutuH + KUTU_ARA : kutuY;
    const H1 = (v.bitis ? bitisY + m.bitisH : fiyatVar ? kutuY + m.kutuH : DAMGA_Y + m.damgaH + 20) + 40;
    return {kutuY, bitisY, H1};
  };
  const o = v.magazalar.length ? 1 : sinirla(HEDEF_H / yerlesim(olculer(1)).H1, 1, 1.5);
  const m = olculer(o);
  const {kutuY, bitisY, H1} = yerlesim(m);
  const damgaPunto = siganPunto(v.etiket, m.damgaIdeal, 800, DAR - 80, 1, 40);
  const damgaW = Math.min(DAR - 20, Math.ceil(yaziGenisligi(v.etiket, damgaPunto, 800) * D.altyazi.pay) + 64);
  const fs = fiyatSatiri(v, m.fiyatIdeal, m.ok);
  const bitis = v.bitis ? yaziSec(v.bitis, m.bitisIdeal, 800, 2, 30, 600, DAR - m.saat - 56) : undefined;
  const yB = H1 + PANEL_ARA;
  const g = an(s, v.goster);
  // Eski fiyat söylenince satır yanar, yeni fiyat söylenince eskisinin üstü çizilir ve yenisi çıkar.
  const ilk = (metin: string) => metin.split(/\s+/)[0] ?? '';
  const tEski = Math.max(g + 0.3, (v.eski_fiyat ? soylenme(s, ilk(v.eski_fiyat), g) : undefined) ?? g + 0.5);
  const yeniSoz = v.yeni_fiyat ? soylenme(s, ilk(v.yeni_fiyat), tEski + 0.05) : v.indirim ? soylenme(s, v.indirim, tEski - 0.25) : undefined;
  const tYeni = Math.min(s.bit - 0.5, Math.max(tEski + 0.4, yeniSoz ?? tEski + 0.8));
  const sonraki = fiyatVar ? tYeni + 0.6 : g + 0.4;
  const tBitis = bitis ? Math.min(s.bit - 0.5, Math.max(sonraki, soylenme(s, ilk(v.bitis), sonraki - 0.3) ?? araKelime(s, sonraki, s.bit, 0.3) ?? sonraki + 0.4)) : undefined;
  const magazalar = v.magazalar.map((mg, k) => ({
    ad: mg.ad,
    goster: Math.max(an(s, mg.goster), (tBitis ?? sonraki) + 0.3),
    x: IC.sol + (k % 2) * (MAGAZA_W + MAGAZA_ARA),
    y: yB + IC.ust + Math.floor(k / 2) * (MAGAZA_H + MAGAZA_ARA),
  }));
  const tB = magazalar.length ? Math.min(...magazalar.map((mg) => mg.goster)) : undefined;
  const H2 = magazalar.length ? IC.ust + Math.ceil(magazalar.length / 2) * (MAGAZA_H + MAGAZA_ARA) - MAGAZA_ARA + 40 : 0;
  const tuval: Tuval = {ust: -2, alt: magazalar.length ? yB + H2 - 2 : H1 - 2};
  return {v, m, renk, damgaPunto, damgaW, fiyatVar, fs, kutuY, bitisY, bitis, H1, yB, g, tEski, tYeni, tBitis, magazalar, tB, H2, oyun: haber.oyun.toLocaleUpperCase('tr'), tuval};
};

export const Fiyat: React.FC<SahneProps> = ({s, t, haber}) => {
  const d = duzen(s, haber);
  const {v, m, renk, fs} = d;
  const yol = sahneYolu(s, fiyatKamera(s, haber), d.tuval, fiyatEngeller(s, haber));
  const dg = ilerle(t, d.g, 0.2);
  // Damga sol kenarına basılır ve içerik alanının sağ ucunu geçecek kadar büyümez; sarsıntı yalnız sağa: yazı her
  // karede güvenli alanda kalır (kamera içerik alanını güvenli alanda tutar).
  const damgaPay = sinirla((IC.en - 16 - d.damgaW) / d.damgaW, 0, 0.9);
  const damgaOlcek = t < d.g ? 0 : 1 + damgaPay * (1 - cikis(dg));
  const sarsinti = t >= d.g && t < d.g + 0.25 ? Math.abs(Math.sin((t - d.g) * 60)) * 4 * (1 - (t - d.g) / 0.25) : 0;
  const kutu = cikis(ilerle(t, d.tEski - 0.25, 0.25));
  const eskiYandi = t >= d.tEski;
  const cizik = cikis(ilerle(t, d.tYeni - 0.1, 0.2));
  const yeni = belir(t, d.tYeni);
  const indirim = belir(t, d.tYeni + 0.15);
  // Kutu hiç boş görünmez: eski fiyat baştan soluk durur; eski fiyat yoksa yeni fiyat ve çip soluk bekler.
  const bekleyen = v.eski_fiyat ? 0 : 0.35;
  const bitisGir = d.tBitis !== undefined ? belir(t, d.tBitis) : undefined;
  const saatBoy = Math.round(m.saat * 0.56);

  return (
    <>
      <Pencere baslik={s.veri.pencere ?? ''} h={d.H1} etkin={etkinlik(yol, 0, t)}>
        <div
          style={{
            position: 'absolute',
            left: IC.sol,
            top: DAMGA_Y,
            width: d.damgaW,
            height: m.damgaH,
            boxSizing: 'border-box',
            border: `6px solid ${renk}`,
            borderRadius: 20,
            background: `${renk}24`,
            color: renk,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: d.damgaPunto,
            fontWeight: 800,
            whiteSpace: 'nowrap',
            transformOrigin: '0 50%',
            transform: `rotate(-5deg) scale(${damgaOlcek}) translateX(${sarsinti}px)`,
            opacity: t < d.g ? 0 : cikis(dg * 2),
            boxShadow: `0 8px 0 ${R.tusAlt}`,
          }}
        >
          {v.etiket}
        </div>
        {d.fiyatVar ? (
          <div
            style={{
              position: 'absolute',
              left: IC.sol,
              top: d.kutuY,
              width: IC.en,
              height: m.kutuH,
              boxSizing: 'border-box',
              borderRadius: 22,
              background: R.tusUst,
              border: `3px solid ${t >= d.tYeni ? renk : R.cizgi}`,
              boxShadow: `0 6px 0 ${R.tusAlt}`,
              opacity: 0.35 + 0.65 * kutu,
            }}
          >
            <div style={{position: 'absolute', left: KUTU_SOL, top: 0, height: m.kutuH - 6, display: 'flex', alignItems: 'center', gap: ARA}}>
              {v.eski_fiyat ? (
                <span style={{position: 'relative', fontSize: fs.punto, fontWeight: 800, color: eskiYandi && t < d.tYeni ? R.yazi : R.soluk, whiteSpace: 'nowrap'}}>
                  {v.eski_fiyat}
                  <span style={{position: 'absolute', left: -4, top: '52%', height: Math.round(7 * m.ok / 52), width: `calc(${cizik * 100}% + 8px)`, borderRadius: 4, background: R.kirmizi, transform: 'rotate(-6deg)'}} />
                </span>
              ) : null}
              {v.eski_fiyat && v.yeni_fiyat ? (
                <span style={{opacity: yeni.saydam, display: 'flex'}}>
                  <Simge ad="ok" boyut={m.ok} renk={renk} kalinlik={3} />
                </span>
              ) : null}
              {v.yeni_fiyat ? (
                <span
                  style={{
                    fontSize: fs.punto,
                    fontWeight: 800,
                    color: t >= d.tYeni ? R.kehribar : R.soluk,
                    opacity: Math.max(bekleyen, yeni.saydam),
                    transform: `scale(${bekleyen && t < d.tYeni ? 1 : yeni.olcek})`,
                    whiteSpace: 'nowrap',
                  }}
                >
                  {v.yeni_fiyat}
                </span>
              ) : null}
              {v.indirim ? (
                <Cip
                  renk={R.pembe}
                  dolu
                  style={{
                    height: Math.round(fs.punto * 0.95),
                    fontSize: Math.round(fs.punto * 0.55),
                    opacity: Math.max(bekleyen, indirim.saydam),
                    transform: `scale(${bekleyen && t < d.tYeni + 0.15 ? 1 : indirim.olcek})`,
                  }}
                >
                  {v.indirim}
                </Cip>
              ) : null}
            </div>
          </div>
        ) : null}
        {d.bitis && d.tBitis !== undefined && bitisGir ? (
          <div
            style={{
              position: 'absolute',
              left: IC.sol,
              top: d.bitisY,
              width: IC.en,
              height: m.bitisH,
              boxSizing: 'border-box',
              borderRadius: 22,
              background: R.yuzey2,
              border: `2px solid ${t >= d.tBitis ? R.kehribar : R.cizgi}`,
              opacity: 0.35 + 0.65 * bitisGir.saydam,
            }}
          >
            <Tus x={18} y={(m.bitisH - 4 - m.saat - 8) / 2} w={m.saat} h={m.saat} derinlik={8} basili={basma(t - d.tBitis)} renk={R.kehribar} kenar="#C98A1B" yaricap={20} olcek={bitisGir.olcek}>
              <Simge ad="saat" boyut={saatBoy} renk={R.koyuYazi} kalinlik={2.8} />
            </Tus>
            <IzleyenYazi
              satirlar={d.bitis.satirlar}
              oran={izOrani(kelimeIzi(s, v.bitis, d.tBitis - 0.05, s.bit), t)}
              style={{position: 'absolute', left: m.saat + 38, top: (m.bitisH - 4 - d.bitis.satirlar.length * d.bitis.lh) / 2, fontSize: d.bitis.punto, lineHeight: `${d.bitis.lh}px`, fontWeight: 800, color: R.yazi}}
            />
          </div>
        ) : null}
      </Pencere>
      {d.tB !== undefined ? (
        <Pencere baslik={d.oyun} y={d.yB} h={d.H2} kaydir={panelGiris(t, d.tB)} etkin={etkinlik(yol, 1, t)}>
          {d.magazalar.map((mg, k) => {
            const b = belir(t, mg.goster);
            const yandi = t >= mg.goster;
            return (
              <Tus
                key={k}
                x={mg.x}
                y={mg.y - d.yB}
                w={MAGAZA_W}
                h={MAGAZA_H}
                derinlik={8}
                basili={basma(t - mg.goster)}
                kenar={yandi ? renk : R.cizgi}
                olcek={yandi ? b.olcek : 1}
                saydam={yandi ? 1 : 0.5}
                yaricap={18}
                style={{justifyContent: 'flex-start', gap: 14, paddingLeft: 22}}
              >
                <Simge ad="magaza" boyut={34} renk={yandi ? renk : R.soluk} kalinlik={2.4} />
                <span style={{fontSize: 28, fontWeight: 700, color: R.yazi, whiteSpace: 'nowrap'}}>{mg.ad}</span>
              </Tus>
            );
          })}
        </Pencere>
      ) : null}
    </>
  );
};

// Kamera: damgaya yakın, eski fiyat söylenince fiyat kutusuna, bitiş söylenince saate, ilk mağazada mağaza paneli, sonra bütün.
export const fiyatKamera = (s: Sahne, haber: Haber): Bakis[] => {
  const d = duzen(s, haber);
  const {m} = d;
  const out: Bakis[] = [bakis(s.bas, DAMGA_Y + m.damgaH / 2 + 80, 1.1, 0, 0)];
  if (d.fiyatVar) out.push(bakis(d.tEski, d.kutuY + m.kutuH / 2, 1.1, d.kutuY, 0));
  if (d.tBitis !== undefined) out.push(bakis(d.tBitis, d.bitisY + m.bitisH / 2 - 30, 1.05, d.bitisY, 0));
  if (d.tB !== undefined) {
    // Tuval sığmayınca kamera alta dayanır ve üst kenar damgayı ortadan keser: biraz yaklaşıp damgayı tümüyle dışarıda bırakır.
    const ustKenar = d.tuval.alt + 30 - 2 * SAHNE_YARI;
    const yakin = (2 * SAHNE_YARI) / (d.tuval.alt + 30 - (d.kutuY - 30));
    const satirVar = d.fiyatVar || Boolean(d.v.bitis);
    out.push(kenardan(d.tB, d.yB, satirVar && ustKenar > DAMGA_Y - 12 && yakin <= 1.1 ? Math.max(1, yakin) : 1, 1));
  }
  const son = Math.max(...d.magazalar.map((mg) => mg.goster), d.tBitis ?? d.tYeni);
  const tGenel = Math.max(son + 0.9, araKelime(s, son + 0.3, s.bit, 0.5) ?? son + 0.9);
  if (tGenel < s.bit - 0.6) out.push(genel(tGenel, d.tuval));
  return out;
};

export const fiyatTuval = (s: Sahne, haber: Haber): Tuval => duzen(s, haber).tuval;

// Damga (döndürülünce köşeleri taşar), fiyat satırı, saat tuşu ve bitiş yazısı, mağaza adları.
export const fiyatEngeller = (s: Sahne, haber: Haber): Engel[] => {
  const d = duzen(s, haber);
  const {v, m} = d;
  return [
    engel(IC.sol - 6, DAMGA_Y - 22, d.damgaW + 12, m.damgaH + 44),
    ...(d.fiyatVar ? [engel(IC.sol + KUTU_SOL, d.kutuY, d.fs.en, m.kutuH)] : []),
    ...(d.bitis
      ? [
          engel(IC.sol + 18, d.bitisY + 8, m.saat, m.saat + 8),
          ...yaziEngeli(v.bitis, d.bitis.punto, 800, d.bitis.en, IC.sol + m.saat + 38, d.bitisY + (m.bitisH - 4 - d.bitis.satirlar.length * d.bitis.lh) / 2, d.bitis.lh),
        ]
      : []),
    ...(d.magazalar.length ? [panelBaslikEngeli(0, d.yB, d.oyun)] : []),
    ...d.magazalar.map((mg) => engel(mg.x, mg.y, Math.min(MAGAZA_W, 80 + yaziGenisligi(mg.ad, 28, 700) * D.altyazi.pay), MAGAZA_H + 8)),
  ];
};

// Maskot sağ sütunda: pencere kenarı, fiyat ve bitiş kutuları ve mağaza paneli arasında kameranın baktığı yere konar.
export const fiyatNoktalar = (s: Sahne, haber: Haber): Nokta[] => {
  const d = duzen(s, haber);
  const kenarlar: Kenar[] = [0, ...(d.fiyatVar ? [d.kutuY] : []), ...(d.bitis ? [d.bitisY] : []), ...(d.tB !== undefined ? [{y: d.yB, bas: d.tB + 0.3}] : [])];
  return kenarDuraklari(sahneYolu(s, fiyatKamera(s, haber), d.tuval, fiyatEngeller(s, haber)), kenarlar, fiyatEngeller(s, haber), 'dur');
};
