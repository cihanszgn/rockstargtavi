import React from 'react';
import {KAMERA_GECIS, kameraYolu, ORTA, type Tuval} from '../kamera';
import {satirlaraBol, yaziGenisligi} from '../olcu';
import {D, GECIS, mutlak, R} from '../tema';
import type {Engel, KameraAnahtari, Nokta, Sahne} from '../tipler';
import {cikis, ilerle, sinirla, yay} from '../zaman';

// Maskotun sağ sütunu: içerik iç x 748'de biter, maskot pencere kenarlarına kare x 852'de konar ve
// pencereler arasında bu sütundan dikine sıçrar; böylece hiçbir yazının üstünden geçmez.
export const SUTUN = 748;
export const PANEL_ARA = 28;
// Sütuna sığan yazı genişliği (iç x 40'tan başlayınca).
export const DAR = SUTUN - 40;
const MASKOT_X = D.maskot.x_en_cok;
const GOVDE_YARI = 42;
const SUTUN_X = mutlak(SUTUN, 0).x;

// Yazıyı büyük göstermek için en büyük punto (ideal'den 2'şer iner): en çok `satir` satıra sığmalı.
export const siganPunto = (metin: string, ideal: number, agirlik: number, en: number, satir: number, enAz: number, aralik = 0) => {
  for (let p = ideal; p > enAz; p -= 2) if (satirlaraBol(metin, p, agirlik, en, aralik).length <= satir) return p;
  return enAz;
};

export type Yazi = {punto: number; en: number; satirlar: string[]; lh: number};
const satirYuk = (p: number) => Math.round(p * 1.18);

// Metinlerin hepsine birden uyan en büyük punto, sütun genişliğinde (dar). Hiçbiri sığmazsa ölçü tablosunun
// puntosu ve genişliği (enAz, tabloEn) kalır: tablo yazının o puntoda o genişliğe sığdığını zaten denetler.
export const ortakYazi = (metinler: string[], ideal: number, agirlik: number, satir: number, enAz: number, tabloEn: number, dar = DAR, aralik = 0): Yazi[] => {
  const dene = (p: number, en: number) => metinler.map((m) => ({punto: p, en, satirlar: satirlaraBol(m, p, agirlik, en, aralik), lh: satirYuk(p)}));
  for (let p = ideal; p > enAz; p -= 2) {
    const d = dene(p, dar);
    if (d.every((y) => y.satirlar.length <= satir)) return d;
  }
  const d = dene(enAz, dar);
  return d.every((y) => y.satirlar.length <= satir) ? d : dene(enAz, Math.max(dar, tabloEn));
};
export const yaziSec = (metin: string, ideal: number, agirlik: number, satir: number, enAz: number, tabloEn: number, dar = DAR, aralik = 0): Yazi =>
  ortakYazi([metin], ideal, agirlik, satir, enAz, tabloEn, dar, aralik)[0];
export const yaziBoyu = (y: Yazi) => y.satirlar.length * y.lh;

// Kameranın bir duruşu. kenar: maskotun bu duruşta konmak istediği pencere üst kenarı (ana pencere içi y);
// pano: kameranın baktığı pencere (0 ana, 1, 2 ikinci paneller), o pencerenin kenarı mavi yanar.
export type Bakis = KameraAnahtari & {kenar?: number; pano?: number};
// Odak yatayda ortadadır; kameraYolu onu yazılar güvenli alanda kalacak yere kaydırır.
export const bakis = (t: number, yIc: number, k: number, kenar?: number, pano?: number): Bakis => ({t, x: ORTA.x, y: yIc, k, kenar, pano});

// Panelin üst kenarı, üstünde maskot sığacak kadar aşağıda görünür.
export const kenardan = (t: number, kenarY: number, k: number, pano?: number): Bakis =>
  bakis(t, kenarY + (ORTA.y - (D.sahne.ust + 14 + D.maskot.yukseklik * k)) / k, k, kenarY, pano);

// Bütün tuvale uzaktan bakış.
export const genel = (t: number, tuval: Tuval, kenar?: number): Bakis => bakis(t, (tuval.ust + tuval.alt) / 2, 0.9, kenar);

// Sahnenin kamera yolu (HaberVideo ile aynı hesap, aynı engellerle): pencerelerin etkinliği ve maskot durakları buna bakar.
export const sahneYolu = (s: Sahne, anahtarlar: Bakis[], tuval: Tuval, engeller: Engel[]) => kameraYolu(anahtarlar, tuval, s, engeller) as Bakis[];

// Kamera bir pencereye geçince o pencerenin kenarı 0.2 sn'de yanar, başka yere geçince söner.
export const etkinlik = (yol: Bakis[], pano: number, t: number) => {
  let e = 0;
  for (const a of yol) {
    if (a.t > t) break;
    const u = cikis(ilerle(t, a.t, 0.2));
    e = a.pano === pano ? e + (1 - e) * u : e * (1 - u);
  }
  return e;
};

// İçerik değişimi: eski yukarı kayıp söner, yeni alttan gelir (0.3 sn).
export const degisim = (t: number, t0: number, mesafe = 56) => {
  const u = cikis(ilerle(t, t0, 0.3));
  return {eski: {dy: -mesafe * u, saydam: 1 - u}, yeni: {dy: mesafe * (1 - u), saydam: u}, u};
};

// Ekrandaki öğenin söylendiği an: [t0, t1) aralığında `parca` ile başlayan ilk kelime (ek farkı gözetmez).
export const soylenme = (s: Sahne, parca: string, t0 = s.bas, t1 = s.bit) => {
  const p = sade(parca);
  if (!p) return undefined;
  return (s.altyazi ?? []).find((k) => k.b >= t0 - 0.05 && k.b < t1 && sade(k.k).startsWith(p))?.b;
};

// Ana pencere (kamera tuvalin üstünde, k = 1).
export const ANA_Y = ORTA.y - mutlak(0, 0).y;

// Her kamera duruşunda maskot görünen bir pencere kenarına konar: önce duruşun istediği, sonra durduğu kenar,
// sonra ekranın ortasına en yakın olanı. Kamera oturduktan sonra konar (sıçrayışı kamerayla birlikte akar).
// İki kenar arasındaki sütuna giren bir yazı varsa (ölçü tablosu genişliğinde yazılan uzun satır) o sıçrama yapılmaz.
// Kenar: sayı ya da sonradan gelen panel için {y, bas} (panel gelmeden maskot oraya konmaz).
export type Kenar = number | {y: number; bas: number};
export const kenarDuraklari = (yol: Bakis[], tumKenarlar: Kenar[], engeller: Engel[], eylem: 'bas' | 'dur' = 'bas'): Nokta[] => {
  const ekranY = (a: KameraAnahtari, y: number) => (y - a.y) * a.k + ORTA.y;
  // Maskot sahnede görünür, üstteki uygulama simgelerinin altında ve sağdaki düğme sırasının dışında kalır.
  const uygun = (a: KameraAnahtari, y: number) => {
    const ex = (MASKOT_X - a.x) * a.k + ORTA.x;
    const tavan = ex - GOVDE_YARI * a.k > 640 ? D.guvenli.ust : D.sahne.ust + 6;
    const ey = ekranY(a, y);
    const rayda = ey > D.guvenli.ray_y && ex + GOVDE_YARI * a.k > D.guvenli.ray_olculen_x;
    return ey - D.maskot.yukseklik * a.k >= tavan + 6 && ey <= D.sahne.alt - 40 && !rayda;
  };
  const acik = (p: number, q: number) =>
    !engeller.some((e) => !e.kamera && e.x1 > SUTUN_X + 0.5 && e.x0 < MASKOT_X + GOVDE_YARI && e.y1 > Math.min(p, q) - D.maskot.yukseklik - 10 && e.y0 < Math.max(p, q));
  const out: Nokta[] = [];
  let onceki: number | undefined;
  for (const a of yol) {
    const varis = a.t + KAMERA_GECIS;
    const kenarlar = tumKenarlar.flatMap((k) => (typeof k === 'number' ? [k] : varis >= k.bas ? [k.y] : []));
    const yakin = [...kenarlar].sort((p, q) => Math.abs(ekranY(a, p) - 620) - Math.abs(ekranY(a, q) - 620));
    const sira = [...(a.kenar !== undefined && kenarlar.includes(a.kenar) ? [a.kenar] : []), ...(onceki !== undefined ? [onceki] : []), ...yakin];
    const y = sira.find((y) => uygun(a, y) && (onceki === undefined || y === onceki || acik(onceki, y)));
    if (y === undefined || y === onceki) continue;
    out.push({t: varis, x: MASKOT_X, y, eylem, zemin: [mutlak(540, 0).x, mutlak(836, 0).x]});
    onceki = y;
  }
  return out;
};

// İki rengin karışımı (#RRGGBB).
export const renkKarisim = (a: string, b: string, u: number) => {
  const c = (h: string, i: number) => parseInt(h.slice(1 + 2 * i, 3 + 2 * i), 16);
  const v = sinirla(u);
  return `rgb(${[0, 1, 2].map((i) => Math.round(c(a, i) + (c(b, i) - c(a, i)) * v)).join(',')})`;
};

// Pencere yerine oturduktan sonraki ilk an: maskot ve ana vurgu bundan önce başlamaz.
export const ILK = GECIS + 0.12;

export const an = (s: Sahne, t: number) => Math.max(t, s.bas + ILK);

export const veri = <T,>(s: Sahne) => s.veri as unknown as T;

// İç alan: pencerenin çerçeve içi genişliği 836, içerik 40..796.
export const IC = {sol: 40, sag: 796, en: 756, ust: 116, alt: 740};

// Maskotun örtmemesi gereken dikdörtgen; sol pencere içi x, üst/boy pencere içi y.
export const engel = (sol: number, ust: number, en: number, boy: number): Engel => ({x0: mutlak(sol, 0).x, x1: mutlak(sol + en, 0).x, y0: ust, y1: ust + boy});

// Yazı, ölçü tablosunun bulduğu satır sonlarıyla çizilir (kapsayıcıda whiteSpace 'pre'): tarayıcı başka yerden
// kırarsa maskotun kaçtığı alan ile ekrandaki yazı ayrışır.
export const satirli = (metin: string, punto: number, agirlik: number, enCok: number, aralik = 0) =>
  satirlaraBol(metin, punto, agirlik, enCok, aralik).join('\n');

// Satırlara bölünen yazının kapladığı alan, satır satır (kısa son satırın yanı boş kalır).
export const yaziEngeli = (metin: string, punto: number, agirlik: number, enCok: number, sol: number, ust: number, satirYuk: number, aralik = 0, ortali = false): Engel[] =>
  satirlaraBol(metin, punto, agirlik, enCok, aralik).map((satir, k) => {
    const w = Math.min(enCok, yaziGenisligi(satir, punto, agirlik, aralik) * D.altyazi.pay);
    return engel(ortali ? sol + (enCok - w) / 2 : sol, ust + k * satirYuk, w, satirYuk);
  });

// Tek satırlık (kesilmeyen) yazı.
export const tekSatirEngeli = (metin: string, punto: number, agirlik: number, enCok: number, sol: number, ust: number, boy: number, aralik = 0): Engel =>
  engel(sol, ust, Math.min(enCok, yaziGenisligi(metin, punto, agirlik, aralik) * D.altyazi.pay), boy);

// Öğenin mutlak x aralığı (maskotun üstünde kayabileceği zemin).
export const zemin = (sol: number, en: number): [number, number] => [mutlak(sol, 0).x, mutlak(sol + en, 0).x];

// Yaylı belirme: ölçek ve saydamlık. Yay 0.3 sn içinde oturur (geçişler 300 ms'yi aşmaz).
export const belir = (t: number, t0: number) => {
  const y = yay(t - t0, 0.62, 24);
  return {olcek: t < t0 ? 0.6 : 0.6 + 0.4 * y, saydam: cikis(ilerle(t, t0, 0.18))};
};

export const kay = (t: number, t0: number, mesafe = 40, sure = 0.3) => {
  const u = cikis(ilerle(t, t0, sure));
  return {dy: mesafe * (1 - u), saydam: u};
};

// İkinci panel anlatım ona geçince alttan kayarak gelir.
export const panelGiris = (t: number, t0: number) => {
  const u = cikis(ilerle(t, t0, 0.3));
  return {dy: 90 * (1 - u), saydam: u};
};

// x, y'de duran panelin başlık çubuğundaki yazı (pencere adı iç x 150'den başlar).
export const panelBaslikEngeli = (px: number, py: number, metin: string): Engel => {
  const w = metin ? Math.min(520, yaziGenisligi(metin, 26, 700, 0.08) * D.altyazi.pay) : 0;
  return engel(px + 24, py + 20, 126 + w, 34);
};

// Anlatımdaki kelime anları. Hareketler sabit gecikmeyle değil, konuşulan kelimeye bağlı başlar.
export const kelimeAnlari = (s: Sahne) => (s.altyazi ?? []).map((k) => k.b).filter((b) => b >= s.bas - 0.05 && b < s.bit);

// Sahne kelimelerinin `oran` kadarı söylendiği an (en erken `enErken`). Kelime yoksa sahne süresiyle orantılı.
export const bolumAni = (s: Sahne, oran: number, enErken = s.bas) => {
  const anlar = kelimeAnlari(s).filter((b) => b >= enErken);
  if (!anlar.length) return Math.max(enErken, s.bas + oran * (s.bit - s.bas));
  return anlar[Math.min(anlar.length - 1, Math.floor(oran * anlar.length))];
};

// [enErken, enGec) aralığında başlayan ilk kelime.
export const ilkKelime = (s: Sahne, enErken: number, enGec = s.bit) => kelimeAnlari(s).find((b) => b >= enErken && b < enGec);

// [t0, t1) aralığındaki kelimelerin `oran` kadarının söylendiği an.
export const araKelime = (s: Sahne, t0: number, t1: number, oran: number) => {
  const a = kelimeAnlari(s).filter((b) => b >= t0 && b < t1);
  return a.length ? a[Math.min(a.length - 1, Math.floor(oran * a.length))] : undefined;
};

// Sahnede söylenen son kelimenin bittiği an.
export const sonKelimeBitis = (s: Sahne) => {
  const k = (s.altyazi ?? []).filter((w) => w.b >= s.bas - 0.05 && w.b < s.bit);
  return k.length ? k[k.length - 1].s : s.bit - 0.8;
};

// Büyük/küçük harf ve noktalama farkı gözetmeyen kelime.
export const sade = (k: string) => k.toLocaleLowerCase('tr').replace(/[^\p{L}\p{N}]/gu, '');
const benzer = (a: string, b: string) => {
  if (!a || !b) return false;
  if (a === b) return true;
  let n = 0;
  while (n < a.length && n < b.length && a[n] === b[n]) n++;
  return n >= 3 && n >= Math.min(5, a.length, b.length);
};

// Ekrandaki yazının her kelimesinin söylendiği an: [t0, t1) aralığındaki anlatımla sırayla eşleşir (ek farkı
// gözetmez). Anlatımda geçmeyen kelimeler komşu eşleşmelerin arasına, sondakiler aralığın son kelimesine yayılır.
export const kelimeIzi = (s: Sahne, metin: string, t0: number, t1: number): number[] => {
  const soz = (s.altyazi ?? []).filter((k) => k.b >= t0 - 0.05 && k.b < t1);
  const hedef = metin.split(/\s+/).filter(Boolean).map(sade);
  const anlar: (number | undefined)[] = [];
  let j = 0;
  for (const h of hedef) {
    let bul = -1;
    for (let q = j; q < soz.length; q++) {
      if (benzer(h, sade(soz[q].k))) {
        bul = q;
        break;
      }
    }
    anlar.push(bul >= 0 ? soz[bul].b : undefined);
    if (bul >= 0) j = bul + 1;
  }
  const son = Math.max(t0 + 0.4, soz.length ? soz[soz.length - 1].s : t0 + 0.4);
  const out: number[] = [];
  for (let i = 0; i < anlar.length; ) {
    if (anlar[i] !== undefined) {
      out.push(anlar[i] as number);
      i++;
      continue;
    }
    let e = i;
    while (e < anlar.length && anlar[e] === undefined) e++;
    const a = i > 0 ? out[i - 1] : t0;
    const b = e < anlar.length ? (anlar[e] as number) : Math.max(son, a + 0.3);
    for (let q = i; q < e; q++) out.push(a + ((b - a) * (q - i + 1)) / (e - i + 1));
    i = e;
  }
  return out;
};

// Kelime anlarına göre işaretlenen oran (IzleyenYazi için); her kelime 0.12 sn'de dolar.
export const izOrani = (anlar: number[], t: number) => (anlar.length ? anlar.reduce((n, a) => n + cikis(ilerle(t, a, 0.12)), 0) / anlar.length : 0);

// [t0, t1) aralığında söylenen kelimelerin `t` anına kadar söylenmiş oranı; her kelime 0.12 sn'de dolar.
export const okunan = (s: Sahne, t0: number, t1: number, t: number) => {
  const anlar = kelimeAnlari(s).filter((b) => b >= t0 - 0.05 && b < t1);
  if (!anlar.length) return ilerle(t, t0, Math.max(0.3, t1 - t0));
  let n = 0;
  for (const b of anlar) n += cikis(ilerle(t, b, 0.12));
  return n / anlar.length;
};

// Konuşmayı izleyen işaretleme: satırlardaki kelimeler oran ilerledikçe sırayla kehribar zemine geçer.
export const IzleyenYazi: React.FC<{satirlar: string[]; oran: number; renk?: string; style?: React.CSSProperties}> = ({satirlar, oran, renk = R.kehribar, style}) => {
  const kelimeler = satirlar.map((s) => s.split(' '));
  const toplam = kelimeler.reduce((a, k) => a + k.length, 0);
  let sira = 0;
  return (
    <div style={{whiteSpace: 'pre', ...style}}>
      {kelimeler.map((satir, r) => (
        <div key={r}>
          {satir.map((k, j) => {
            const u = sinirla(oran * toplam - sira++);
            return (
              <React.Fragment key={j}>
                {j ? ' ' : ''}
                <span style={{background: u > 0 ? `${renk}${Math.round(u * 0xdd).toString(16).padStart(2, '0')}` : 'transparent', color: u > 0.5 ? R.koyuYazi : undefined, borderRadius: 6}}>{k}</span>
              </React.Fragment>
            );
          })}
        </div>
      ))}
    </div>
  );
};

export const Cip: React.FC<{renk: string; children: React.ReactNode; style?: React.CSSProperties; dolu?: boolean}> = ({
  renk,
  children,
  style,
  dolu,
}) => (
  <div
    data-kutu="cip"
    style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 10,
      height: 44,
      padding: '0 16px',
      boxSizing: 'border-box',
      borderRadius: 12,
      border: `2px solid ${renk}`,
      background: dolu ? renk : `${renk}22`,
      color: dolu ? R.koyuYazi : renk,
      fontSize: 22,
      fontWeight: 800,
      letterSpacing: '0.08em',
      whiteSpace: 'nowrap',
      ...style,
    }}
  >
    {children}
  </div>
);
