// Güvenli alan kuralı (render.mjs --denetle): ekranda görünen her yazı ve çip (src/denetim.tsx ölçer) karenin
// güvenli dikdörtgeninde kalır ve sağdaki uygulama düğmelerinin bandına (ray) girmez. Sınırlar src/olcu/duzen.json
// "guvenli" alanında; ölçümü ve kaynağı orada yazılı.
const PAY = 0.5;

export const ihlalleri = (oge, g) => {
  const out = [];
  if (oge.x0 < g.sol - PAY) out.push(['sol', g.sol - oge.x0]);
  if (oge.x1 > g.sag + PAY) out.push(['sag', oge.x1 - g.sag]);
  if (oge.y0 < g.ust - PAY) out.push(['ust', g.ust - oge.y0]);
  if (oge.y1 > g.alt + PAY) out.push(['alt', oge.y1 - g.alt]);
  if (oge.x1 > g.ray_x + PAY && oge.y1 > g.ray_y + PAY) out.push(['ray', Math.min(oge.x1 - g.ray_x, oge.y1 - g.ray_y)]);
  return out;
};

// olcumler: [{kare, kapak, ogeler}] -> rapor. Aynı öğenin aynı yöndeki ihlalleri tek satırda toplanır.
export const denetle = (olcumler, g) => {
  const gruplar = new Map();
  let ogeSayisi = 0;
  let ihlalliKare = 0;
  for (const o of olcumler) {
    let ihlalli = false;
    for (const oge of o.ogeler) {
      ogeSayisi++;
      for (const [yon, asim] of ihlalleri(oge, g)) {
        ihlalli = true;
        const anahtar = `${oge.tur}|${oge.metin}|${yon}`;
        const yer = o.kapak ? 'kapak' : o.kare;
        const v = gruplar.get(anahtar) ?? {tur: oge.tur, metin: oge.metin, yon, kareler: [], en_cok: 0, ornek: null};
        v.kareler.push(yer);
        if (asim > v.en_cok) {
          v.en_cok = Math.round(asim * 10) / 10;
          v.ornek = {yer, x0: oge.x0, y0: oge.y0, x1: oge.x1, y1: oge.y1};
        }
        gruplar.set(anahtar, v);
      }
    }
    if (ihlalli) ihlalliKare++;
  }
  const sira = (a, b) => (a === 'kapak') - (b === 'kapak') || a - b;
  const ihlaller = [...gruplar.values()].map((v) => ({...v, kare_sayisi: v.kareler.length, kareler: [...v.kareler].sort(sira).slice(0, 12)}));
  ihlaller.sort((a, b) => b.kare_sayisi - a.kare_sayisi || b.en_cok - a.en_cok);
  return {kare_sayisi: olcumler.length, oge_sayisi: ogeSayisi, ihlalli_kare: ihlalliKare, ihlal_sayisi: ihlaller.reduce((n, v) => n + v.kare_sayisi, 0), ihlaller};
};
