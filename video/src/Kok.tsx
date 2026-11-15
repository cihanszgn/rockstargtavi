import React from 'react';
import {Composition, type CalculateMetadataFunction} from 'remotion';
import {HaberVideo} from './HaberVideo';
import {ORNEK} from './ornek';
import type {VideoProps} from './tipler';

const FPS = 30;

// Süre senaryodan gelir: tools/video_uret.py seslendirmeyi ölçüp `sure` alanına yazar.
const olc: CalculateMetadataFunction<VideoProps> = ({props}) => ({
  durationInFrames: Math.max(1, Math.ceil(props.sure * FPS)),
});

export const Kok: React.FC = () => (
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
);
