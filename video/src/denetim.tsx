import type React from 'react';
import {useLayoutEffect} from 'react';
import {continueRender, delayRender} from 'remotion';

// Güvenli alan denetimi (render.mjs --denetle): her karede ekranda görünen yazıların ve çiplerin (data-kutu)
// kare koordinatındaki dikdörtgeni ölçülüp konsola yazılır; sınırla karşılaştırma render.mjs'te yapılır.
// Görünen dikdörtgen: yazının kutusu, taşmayı kesen (overflow) atalarıyla kesişir; saydamlık atalar boyunca çarpılır.
export type Oge = {tur: 'yazi' | 'kutu'; metin: string; x0: number; y0: number; x1: number; y1: number; saydam: number};

const yuvarla = (v: number) => Math.round(v * 10) / 10;

const gorunurluk = (el: Element, kok: Element, kendisiKeser: boolean) => {
  let saydam = 1;
  let x0 = -1e9;
  let y0 = -1e9;
  let x1 = 1e9;
  let y1 = 1e9;
  for (let e: Element | null = el; e; e = e.parentElement) {
    const cs = getComputedStyle(e);
    if (cs.display === 'none' || cs.visibility === 'hidden') return null;
    saydam *= Number(cs.opacity);
    if ((e !== el || kendisiKeser) && (cs.overflowX !== 'visible' || cs.overflowY !== 'visible')) {
      const r = e.getBoundingClientRect();
      x0 = Math.max(x0, r.left);
      y0 = Math.max(y0, r.top);
      x1 = Math.min(x1, r.right);
      y1 = Math.min(y1, r.bottom);
    }
    if (e === kok) break;
  }
  return {saydam, x0, y0, x1, y1};
};

const olc = (kok: HTMLElement): Oge[] => {
  const k = kok.getBoundingClientRect();
  const out: Oge[] = [];
  const ekle = (tur: Oge['tur'], metin: string, r: DOMRect, el: Element, kendisiKeser: boolean) => {
    if (r.width <= 0 || r.height <= 0) return;
    const g = gorunurluk(el, kok, kendisiKeser);
    if (!g || g.saydam < 0.1) return;
    const x0 = Math.max(r.left, g.x0);
    const y0 = Math.max(r.top, g.y0);
    const x1 = Math.min(r.right, g.x1);
    const y1 = Math.min(r.bottom, g.y1);
    if (x1 - x0 < 0.5 || y1 - y0 < 0.5) return;
    out.push({tur, metin: metin.slice(0, 40), x0: yuvarla(x0 - k.left), y0: yuvarla(y0 - k.top), x1: yuvarla(x1 - k.left), y1: yuvarla(y1 - k.top), saydam: yuvarla(g.saydam)});
  };
  const yurur = document.createTreeWalker(kok, NodeFilter.SHOW_TEXT);
  const aralik = document.createRange();
  for (let n = yurur.nextNode(); n; n = yurur.nextNode()) {
    const metin = (n.textContent ?? '').trim();
    const el = n.parentElement;
    if (!metin || !el) continue;
    // Tamamen saydam renkli yazı görünmez.
    if (/rgba\(.*,\s*0\)$/.test(getComputedStyle(el).color)) continue;
    aralik.selectNodeContents(n);
    ekle('yazi', metin, aralik.getBoundingClientRect(), el, true);
  }
  kok.querySelectorAll('[data-kutu]').forEach((el) => ekle('kutu', el.getAttribute('data-kutu') || (el.textContent ?? '').trim(), el.getBoundingClientRect(), el, false));
  return out;
};

export const Denetim: React.FC<{kare: number; kapak: boolean}> = ({kare, kapak}) => {
  useLayoutEffect(() => {
    const tutamak = delayRender(`denetim ${kare}`);
    let bitti = false;
    const bitir = () => {
      if (bitti) return;
      bitti = true;
      continueRender(tutamak);
    };
    // Yazı tipi inmeden ölçülen genişlik yanlış olur.
    document.fonts.ready.then(() =>
      requestAnimationFrame(() => {
        if (bitti) return;
        const kok = document.querySelector('[data-denetim-kok]');
        const ogeler = kok instanceof HTMLElement ? olc(kok) : [];
        console.log(`DENETIM ${JSON.stringify({kare, kapak, ogeler})}`);
        bitir();
      }),
    );
    return bitir;
  }, [kare, kapak]);
  return null;
};
