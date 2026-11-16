import React from 'react';
import {Composition, Still, type CalculateMetadataFunction} from 'remotion';
import {HaberKapak, HaberVideo} from './HaberVideo';
import {ORNEK} from './ornek';
import type {VideoProps} from './tipler';

const FPS = 30;

// Süre senaryodan gelir: tools/video_uret.py seslendirmeyi ölçüp `sure` alanına yazar.
const olc: CalculateMetadataFunction<VideoProps> = ({props}) => ({
  durationInFrames: Math.max(1, Math.ceil(props.sure * FPS)),
});

export const Kok: React.FC = () => (
  <>
    <Composition
      id="HaberVideo"
      component={HaberVideo}
      width={1080}
      height={1920}
      fps={FPS}
      durationInFrames={Math.ceil(ORNEK.sure * FPS)}
      defaultProps={ORNEK}
      calculateMetadata={olc}
    />
    {/* Kapak resmi: başlık sahnesi girişleri bitmiş hâliyle, altyazısız (render.mjs --kapak). */}
    <Still id="HaberKapak" component={HaberKapak} width={1080} height={1920} defaultProps={ORNEK} />
  </>
);
