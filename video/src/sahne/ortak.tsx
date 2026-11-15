import React from 'react';
import {satirlaraBol, yaziGenisligi} from '../olcu';
import {D, GECIS, mutlak, R} from '../tema';
import type {Engel, Sahne} from '../tipler';
import {cikis, ilerle, yay} from '../zaman';

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

// Yaylı belirme: ölçek ve saydamlık.
export const belir = (t: number, t0: number) => {
  const y = yay(t - t0, 0.5, 16);
  return {olcek: t < t0 ? 0.6 : 0.6 + 0.4 * y, saydam: cikis(ilerle(t, t0, 0.18))};
};

export const kay = (t: number, t0: number, mesafe = 40, sure = 0.35) => {
  const u = cikis(ilerle(t, t0, sure));
  return {dy: mesafe * (1 - u), saydam: u};
};

export const Cip: React.FC<{renk: string; children: React.ReactNode; style?: React.CSSProperties; dolu?: boolean}> = ({
  renk,
  children,
  style,
  dolu,
}) => (
  <div
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
