import React, {useMemo} from 'react';
import {AbsoluteFill, Html5Audio, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {AltKart} from './bilesen/AltKart';
import {Altyazi} from './bilesen/Altyazi';
import {Maskot} from './bilesen/Maskot';
import {Pencere} from './bilesen/Pencere';
import {UstSerit} from './bilesen/UstSerit';
import {Zemin} from './bilesen/Zemin';
import {planla} from './maskot';
import {SABLON} from './sahne';
import {D, GECIS, PENCERE, R, YAZI} from './tema';
import type {Haber, Sahne, VideoProps} from './tipler';
import {cikis, girisCikis, ilerle} from './zaman';
import {yaziYukle} from './yazi';

yaziYukle();

const SAHNE = D.sahne;
const KAYMA = 860;

const SahneKatmani: React.FC<{s: Sahne; i: number; son: boolean; t: number; haber: Haber}> = ({s, i, son, t, haber}) => {
  const sablon = SABLON[s.sablon];
  if (!sablon) return null;
  let dy = 0;
  let saydam = 1;
  if (i === 0) {
    const u = cikis(ilerle(t, 0, 0.45));
    dy += 90 * (1 - u);
    saydam = u;
  } else {
    dy += KAYMA * (1 - girisCikis(ilerle(t, s.bas, GECIS)));
  }
  if (!son) dy -= KAYMA * girisCikis(ilerle(t, s.bit, GECIS));
  const {Bilesen} = sablon;
  return (
    <div style={{position: 'absolute', left: PENCERE.x, top: PENCERE.y - SAHNE.ust, width: PENCERE.w, height: PENCERE.h + 12, transform: `translateY(${dy}px)`, opacity: saydam}}>
      <Pencere baslik={(s.veri.pencere as string) ?? ''}>
        <Bilesen s={s} t={t} haber={haber} />
      </Pencere>
    </div>
  );
};

export const HaberVideo: React.FC<VideoProps> = (props) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const {sahneler, haber} = props;
  // Kapak karesi: ilk sahnenin sonu (başlık, tuşlar ve vurgu yerinde), altyazısız.
  const t = props.kapak && sahneler.length ? Math.max(0, sahneler[0].bit - 0.6) : frame / fps;
  const plan = useMemo(() => planla(sahneler, haber), [sahneler, haber]);

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
          return gorunur ? <SahneKatmani key={i} s={s} i={i} son={son} t={t} haber={haber} /> : null;
        })}
      </div>
      <UstSerit haber={haber} sahneler={sahneler} t={t} />
      <Maskot plan={plan} t={t} />
      {props.kapak ? null : <Altyazi parcalar={props.parcalar} kelimeler={props.kelimeler} t={t} />}
      <AltKart sahneler={sahneler} t={t} />
      {props.ses && !props.kapak ? <Html5Audio src={staticFile(props.ses)} /> : null}
    </AbsoluteFill>
  );
};
