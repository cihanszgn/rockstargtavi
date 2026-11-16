// Haber videosunu Remotion ile çizer. tools/video_uret.py çağırır; elle de çalışır:
//   node render.mjs --girdi zamanli.json --ses ses.mp3 --video ham.mp4 --kapak kapak.jpg
//   node render.mjs --girdi zamanli.json --kapak kapak.jpg                (yalnız kapak resmi)
//   node render.mjs --girdi zamanli.json --kareler klasor --kare 0,30,90   (yalnız tek kareler, inceleme için)
//   node render.mjs --girdi zamanli.json --denetle rapor.json [--adim 1]  (güvenli alan denetimi: her adımda bir kare
//     ve kapak; bir yazı ya da çip güvenli alandan çıkarsa rapor yazılır ve çıkış kodu 3 olur)
import {bundle} from '@remotion/bundler';
import {ensureBrowser, renderFrames, renderMedia, renderStill, selectComposition} from '@remotion/renderer';
import {copyFileSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {denetle} from './guvenli.mjs';

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

    if (a.denetle) {
      const guvenli = JSON.parse(readFileSync(path.join(KOK, 'src', 'olcu', 'duzen.json'), 'utf8')).guvenli;
      const adim = Math.max(1, Number(a.adim ?? 1));
      const dprops = {...props, denetim: true};
      const olcumler = new Map();
      const dinle = (log) => {
        if (!log.text.startsWith('DENETIM ')) return;
        const o = JSON.parse(log.text.slice(8));
        olcumler.set(o.kapak ? 'kapak' : o.kare, o);
      };
      const son = kompozisyon.durationInFrames - 1;
      const kareler = [];
      for (let k = 0; k <= son; k += adim) kareler.push(k);
      const cikti = path.join(genel, 'denetim');
      mkdirSync(cikti);
      // Bileşen seçilen kompozisyonun props'unu alır: denetim bayrağı seçimde verilmeli.
      const dkomp = await selectComposition({serveUrl: paket, id: 'HaberVideo', inputProps: dprops});
      await renderFrames({
        composition: dkomp,
        serveUrl: paket,
        inputProps: dprops,
        frameRange: [0, son],
        everyNthFrame: adim,
        imageFormat: 'jpeg',
        jpegQuality: 10,
        outputDir: cikti,
        onBrowserLog: dinle,
        onStart: () => {},
        onFrameUpdate: () => {},
      });
      if (kareler[kareler.length - 1] !== son) {
        kareler.push(son);
        await renderStill({composition: dkomp, serveUrl: paket, inputProps: dprops, frame: son, output: path.join(cikti, 'son.jpg'), imageFormat: 'jpeg', onBrowserLog: dinle});
      }
      const kapak = await selectComposition({serveUrl: paket, id: 'HaberKapak', inputProps: dprops});
      await renderStill({composition: kapak, serveUrl: paket, inputProps: dprops, frame: 0, output: path.join(cikti, 'kapak.jpg'), imageFormat: 'jpeg', onBrowserLog: dinle});
      const eksik = kareler.filter((k) => !olcumler.has(k));
      if (eksik.length || !olcumler.has('kapak')) throw new Error(`denetim ölçümü gelmedi: ${eksik.length} kare${olcumler.has('kapak') ? '' : ', kapak'}`);
      const rapor = {guvenli, adim, ...denetle([...olcumler.values()], guvenli)};
      writeFileSync(a.denetle, JSON.stringify(rapor, null, 1));
      console.log(`denetim: ${rapor.kare_sayisi} ölçüm (${adim} karede bir + kapak), ${rapor.oge_sayisi} öğe, ${rapor.ihlal_sayisi} ihlal, ${rapor.ihlalli_kare} ihlalli ölçüm (${sure(basla)})`);
      for (const v of rapor.ihlaller.slice(0, 15)) console.log(`  ${v.yon} ${v.tur} "${v.metin}" ${v.kare_sayisi} kare, en çok ${v.en_cok} px (${v.ornek.yer})`);
      if (rapor.ihlal_sayisi) process.exitCode = 3;
      return;
    }

    if (!a.video && !a.kapak) throw new Error('--video ya da --kapak gerekli');
    if (a.video) {
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
    }
    if (a.kapak) {
      // Kapak ayrı Still kompozisyonudur: renderStill bileşene seçilen kompozisyonun props'unu verir.
      const kapak = await selectComposition({serveUrl: paket, id: 'HaberKapak', inputProps: props});
      await renderStill({composition: kapak, serveUrl: paket, inputProps: props, frame: 0, output: a.kapak, imageFormat: 'jpeg', jpegQuality: 90});
      console.log(`kapak yazıldı: ${a.kapak} (kare ${props.kapak_kare ?? 'yok'})`);
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
