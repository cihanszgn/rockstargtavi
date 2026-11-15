// Haber videosunu Remotion ile çizer. tools/video_uret.py çağırır; elle de çalışır:
//   node render.mjs --girdi zamanli.json --ses ses.mp3 --video ham.mp4 --kapak kapak.jpg
//   node render.mjs --girdi zamanli.json --kareler klasor --kare 0,30,90   (yalnız tek kareler, inceleme için)
import {bundle} from '@remotion/bundler';
import {ensureBrowser, renderMedia, renderStill, selectComposition} from '@remotion/renderer';
import {copyFileSync, mkdirSync, mkdtempSync, readFileSync, rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const KOK = path.dirname(fileURLToPath(import.meta.url));
const YAZI_TIPI = path.join(KOK, '..', 'fonts', 'archivo.woff2');

const argumanlar = (liste) => {
  const a = {};
  for (let i = 0; i < liste.length; i++) {
    if (!liste[i].startsWith('--')) throw new Error(`beklenmeyen argüman: ${liste[i]}`);
    a[liste[i].slice(2)] = liste[i + 1];
    i++;
  }
  return a;
};

const sure = (bas) => `${((Date.now() - bas) / 1000).toFixed(1)} sn`;

const main = async () => {
  const a = argumanlar(process.argv.slice(2));
  if (!a.girdi) throw new Error('--girdi gerekli');
  const props = JSON.parse(readFileSync(a.girdi, 'utf8'));
  const genel = mkdtempSync(path.join(tmpdir(), 'haber-video-'));
  const basla = Date.now();
  try {
    copyFileSync(YAZI_TIPI, path.join(genel, 'archivo.woff2'));
    if (a.ses) {
      copyFileSync(a.ses, path.join(genel, 'ses.mp3'));
      props.ses = 'ses.mp3';
    } else {
      props.ses = '';
    }
    await ensureBrowser();
    const paket = await bundle({entryPoint: path.join(KOK, 'src', 'index.ts'), publicDir: genel});
    console.log(`paket hazır (${sure(basla)})`);
    const kompozisyon = await selectComposition({serveUrl: paket, id: 'HaberVideo', inputProps: props});
    console.log(`kompozisyon ${kompozisyon.width}x${kompozisyon.height} ${kompozisyon.fps} fps ${kompozisyon.durationInFrames} kare`);

    if (a.kareler) {
      mkdirSync(a.kareler, {recursive: true});
      const kareler = (a.kare ?? '0').split(',').map((k) => Number(k.trim())).filter((k) => Number.isFinite(k));
      for (const kare of kareler) {
        const cikti = path.join(a.kareler, `kare-${String(kare).padStart(5, '0')}.jpg`);
        await renderStill({composition: kompozisyon, serveUrl: paket, inputProps: props, frame: Math.min(kare, kompozisyon.durationInFrames - 1), output: cikti, imageFormat: 'jpeg', jpegQuality: 88});
      }
      console.log(`${kareler.length} kare yazıldı (${sure(basla)})`);
      return;
    }

    if (!a.video) throw new Error('--video gerekli');
    let son = -1;
    const cizim = Date.now();
    await renderMedia({
      composition: kompozisyon,
      serveUrl: paket,
      inputProps: props,
      codec: 'h264',
      crf: 18,
      x264Preset: 'medium',
      pixelFormat: 'yuv420p',
      // Varsayılan tam aralık (yuvj420p, bt470bg) bazı oynatıcılarda renkleri kaydırır; yayın standardı bt709 dar aralık.
      colorSpace: 'bt709',
      audioBitrate: '160k',
      outputLocation: a.video,
      onProgress: ({progress}) => {
        const yuzde = Math.floor(progress * 10) * 10;
        if (yuzde !== son) {
          son = yuzde;
          console.log(`çizim %${yuzde}`);
        }
      },
    });
    console.log(`video yazıldı: ${a.video} (çizim ${sure(cizim)})`);
    if (a.kapak) {
      await renderStill({composition: kompozisyon, serveUrl: paket, inputProps: {...props, kapak: true}, frame: 0, output: a.kapak, imageFormat: 'jpeg', jpegQuality: 90});
      console.log(`kapak yazıldı: ${a.kapak}`);
    }
    console.log(`toplam ${sure(basla)}`);
  } finally {
    rmSync(genel, {recursive: true, force: true});
  }
};

main().catch((hata) => {
  console.error(hata instanceof Error ? hata.message : hata);
  process.exit(1);
});
