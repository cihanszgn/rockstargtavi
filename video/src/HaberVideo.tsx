import React, {useMemo} from 'react';
import {AbsoluteFill, Html5Audio, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {AltKart} from './bilesen/AltKart';
import {Altyazi} from './bilesen/Altyazi';
import {Maskot} from './bilesen/Maskot';
import {UstSerit} from './bilesen/UstSerit';
import {Zemin} from './bilesen/Zemin';
import {type Ekran, kameraAn, kameraYolu, ORTA, sahneKaymasi} from './kamera';
import {type Durak, durum, planla} from './maskot';
import {SABLON} from './sahne';
import {D, GECIS, PENCERE, R, YAZI} from './tema';
import type {Haber, KameraAnahtari, Sahne, VideoProps} from './tipler';
import {yaziYukle} from './yazi';
import {cikis, ilerle} from './zaman';

yaziYukle();

const SAHNE = D.sahne;

// Tuval katmanı: içindeki (0, 0) ana pencerenin dış sol üst köşesi; kamera ölçeği ve kayması tek transform.
// Kapakta pencerenin içi sahne sonundan 1 sn sonraki hâliyle çizilir: içindeki girişlerin hepsi (en geç sahne sonunda
// başlayıp 0.3 sn sürer) bitmiştir; kamera ve kayma kapak anında kalır.
const SahneKatmani: React.FC<{s: Sahne; i: number; t: number; haber: Haber; ekran: Ekran; kapak: boolean}> = ({s, i, t, haber, ekran, kapak}) => {
  const sablon = SABLON[s.sablon];
  if (!sablon) return null;
  const e = ekran(i, t);
  const saydam = i === 0 ? cikis(ilerle(t, 0, 0.3)) : 1;
  const tx = (PENCERE.x - e.x) * e.k + ORTA.x - PENCERE.x;
  const ty = (-PENCERE.cerceve - e.y) * e.k + ORTA.y - PENCERE.y + e.dy;
  const {Bilesen} = sablon;
  const ic = kapak ? Math.max(t, s.bit + 1) : t;
  return (
    <div
      style={{
        position: 'absolute',
        left: PENCERE.x,
        top: PENCERE.y - SAHNE.ust,
        width: PENCERE.w,
        height: PENCERE.h,
        transformOrigin: '0 0',
        transform: `translate(${tx}px, ${ty}px) scale(${e.k})`,
        opacity: saydam,
      }}
    >
      <Bilesen s={s} t={ic} haber={haber} />
    </div>
  );
};

// Kapak anı: tools/video_uret.py'nin seçtiği kareden (başlık girişleri bitmiş, kamera bütün başlıkta) başlar; maskot o an
// havadaysa indiği ilk kareye geçer. Başlık sahnesinin son durağı sahne bitmeden konduğu için pencere kaymadan bulunur.
const kapakAni = (props: VideoProps, plan: Durak[], ekran: Ekran) => {
  const s = props.sahneler[0];
  if (!s) return 0;
  const fps = props.fps || 30;
  const ilk = Math.max(0, props.kapak_kare ?? Math.ceil((s.bit - 0.6) * fps));
  const son = Math.floor((s.bit - 0.03) * fps);
  for (let k = ilk; k <= son; k++) {
    const st = durum(plan, k / fps, ekran);
    if (st.havada === 0 && !st.yuruyor) return k / fps;
  }
  return ilk / fps;
};

export const HaberVideo: React.FC<VideoProps> = (props) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const {sahneler, haber} = props;
  const kapak = !!props.kapak;
  const yollar = useMemo<KameraAnahtari[][]>(
    () => sahneler.map((s) => (SABLON[s.sablon] ? kameraYolu(SABLON[s.sablon].kamera(s, haber), SABLON[s.sablon].tuval(s, haber), s.bas) : kameraYolu([], {ust: -2, alt: 778}, s.bas))),
    [sahneler, haber],
  );
  const ekran = useMemo<Ekran>(() => (i, an) => ({...kameraAn(yollar[i], an), dy: sahneKaymasi(sahneler, i, an).dy}), [yollar, sahneler]);
  const plan = useMemo(() => planla(sahneler, haber, ekran), [sahneler, haber, ekran]);
  const t = kapak ? kapakAni(props, plan, ekran) : frame / fps;

  return (
    <AbsoluteFill style={{fontFamily: YAZI, color: R.yazi, fontKerning: 'normal'}}>
      <Zemin t={t} />
      <div
        style={{
          position: 'absolute',
          left: 0,
          top: SAHNE.ust,
          width: 1080,
          height: SAHNE.alt - SAHNE.ust,
          overflow: 'hidden',
          maskImage: 'linear-gradient(to bottom, transparent 0, black 24px, black calc(100% - 30px), transparent 100%)',
          WebkitMaskImage: 'linear-gradient(to bottom, transparent 0, black 24px, black calc(100% - 30px), transparent 100%)',
        }}
      >
        {sahneler.map((s, i) => {
          const son = i === sahneler.length - 1;
          const gorunur = t >= s.bas - 0.01 && (son || t < s.bit + GECIS);
          return gorunur ? <SahneKatmani key={i} s={s} i={i} t={t} haber={haber} ekran={ekran} kapak={kapak} /> : null;
        })}
      </div>
      <UstSerit haber={haber} sahneler={sahneler} t={t} />
      <Maskot plan={plan} t={t} ekran={ekran} sabit={kapak} />
      {kapak ? null : <Altyazi parcalar={props.parcalar} kelimeler={props.kelimeler} t={t} />}
      <AltKart sahneler={sahneler} t={t} />
      {props.ses && !kapak ? <Html5Audio src={staticFile(props.ses)} /> : null}
    </AbsoluteFill>
  );
};

// Kapak resmi (site posteri, Reels kapağı, YouTube küçük resmi) ayrı bir Still kompozisyonudur: renderStill bileşene
// seçilen kompozisyonun props'unu verir, o çağrıya eklenen alanı değil; `kapak` ancak böyle ulaşır.
export const HaberKapak: React.FC<VideoProps> = (props) => <HaberVideo {...props} kapak />;
