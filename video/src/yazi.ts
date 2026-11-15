import {loadFont} from '@remotion/fonts';
import {staticFile} from 'remotion';

// Archivo değişken yazı tipi (OFL) depodaki fonts/ klasöründen gelir; render.mjs onu public klasörüne kopyalar.
// loadFont kendisi delayRender/continueRender yapar: yazı tipi inmeden kare çekilmez.
let yuklendi = false;

export const yaziYukle = () => {
  if (yuklendi) return;
  yuklendi = true;
  loadFont({
    family: 'Archivo',
    url: staticFile('archivo.woff2'),
    weight: '100 900',
    stretch: '62% 125%',
    format: 'woff2',
  });
};
