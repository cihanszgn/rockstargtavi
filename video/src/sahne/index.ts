import type React from 'react';
import type {Engel, Haber, Nokta, Sahne, SablonAdi, SahneProps} from '../tipler';
import {Baslik, baslikEngeller, baslikNoktalar} from './Baslik';
import {Fiyat, fiyatEngeller, fiyatNoktalar} from './Fiyat';
import {Kaynak, kaynakEngeller, kaynakNoktalar} from './Kaynak';
import {Kapanis, kapanisEngeller, kapanisNoktalar} from './Kapanis';
import {Maddeler, maddelerEngeller, maddelerNoktalar} from './Maddeler';
import {Platform, platformEngeller, platformNoktalar} from './Platform';
import {Tarih, tarihEngeller, tarihNoktalar} from './Tarih';
import {YamaFark, yamaFarkEngeller, yamaFarkNoktalar} from './YamaFark';

type Sablon = {
  Bilesen: React.FC<SahneProps>;
  noktalar: (s: Sahne, haber: Haber) => Nokta[];
  // Maskotun örtmemesi gereken yazılar ve tuşlar.
  engeller: (s: Sahne, haber: Haber) => Engel[];
  hareket: string;
};

// Şablon sürümü tools/video_uret.py içindeki SABLON_SURUMU ile birlikte artar (görünüm değişince video anahtarı değişsin).
export const SABLON: Record<SablonAdi, Sablon> = {
  baslik: {Bilesen: Baslik, noktalar: baslikNoktalar, engeller: baslikEngeller, hareket: 'bas'},
  kaynak: {Bilesen: Kaynak, noktalar: kaynakNoktalar, engeller: kaynakEngeller, hareket: 'tara'},
  maddeler: {Bilesen: Maddeler, noktalar: maddelerNoktalar, engeller: maddelerEngeller, hareket: 'bas'},
  yama_fark: {Bilesen: YamaFark, noktalar: yamaFarkNoktalar, engeller: yamaFarkEngeller, hareket: 'bas'},
  tarih: {Bilesen: Tarih, noktalar: tarihNoktalar, engeller: tarihEngeller, hareket: 'zipla'},
  fiyat: {Bilesen: Fiyat, noktalar: fiyatNoktalar, engeller: fiyatEngeller, hareket: 'zipla'},
  platform: {Bilesen: Platform, noktalar: platformNoktalar, engeller: platformEngeller, hareket: 'zipla'},
  kapanis: {Bilesen: Kapanis, noktalar: kapanisNoktalar, engeller: kapanisEngeller, hareket: 'bas'},
};
