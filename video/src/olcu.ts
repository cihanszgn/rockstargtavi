import genislik from './olcu/genislik.json';
import {D} from './tema';

// tools/video_uret.py `yazi_genisligi` / `satirlara_bol` ile aynı hesap: yerleşim iki tarafta aynı satır sayısını bulur.
type Tablo = {agirlik: Record<string, Record<string, number>>; varsayilan: number};
const T = genislik as unknown as Tablo;

export const yaziGenisligi = (metin: string, punto: number, agirlik = 800, aralik = 0) => {
  const harf = T.agirlik[String(agirlik)] ?? T.agirlik['800'];
  let w = 0;
  for (const h of metin) w += (harf[h] ?? T.varsayilan) + aralik;
  return punto * w;
};

export const satirlaraBol = (metin: string, punto: number, agirlik: number, en: number, aralik = 0) => {
  const pay = D.altyazi.pay;
  const satirlar: string[] = [];
  let simdiki = '';
  for (const kelime of metin.split(/\s+/).filter(Boolean)) {
    const aday = simdiki ? `${simdiki} ${kelime}` : kelime;
    if (!simdiki || yaziGenisligi(aday, punto, agirlik, aralik) * pay <= en) simdiki = aday;
    else {
      satirlar.push(simdiki);
      simdiki = kelime;
    }
  }
  if (simdiki) satirlar.push(simdiki);
  return satirlar;
};

// Tek satıra sığmayan kısa metin için yatay sıkıştırma oranı (en az `enAz`).
export const sigdirOlcek = (metin: string, punto: number, agirlik: number, en: number, enAz = 0.7, aralik = 0) => {
  const w = yaziGenisligi(metin, punto, agirlik, aralik) * D.altyazi.pay;
  return w <= en ? 1 : Math.max(enAz, en / w);
};
