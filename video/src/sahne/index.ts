import type React from 'react';
import type {Tuval} from '../kamera';
import type {Engel, Haber, KameraAnahtari, Nokta, Sahne, SablonAdi, SahneProps} from '../tipler';
import {Baslik, baslikEngeller, baslikKamera, baslikNoktalar, baslikTuval} from './Baslik';
import {Fiyat, fiyatEngeller, fiyatKamera, fiyatNoktalar, fiyatTuval} from './Fiyat';
import {Kaynak, kaynakEngeller, kaynakKamera, kaynakNoktalar, kaynakTuval} from './Kaynak';
import {Kapanis, kapanisEngeller, kapanisKamera, kapanisNoktalar, kapanisTuval} from './Kapanis';
import {Maddeler, maddelerEngeller, maddelerKamera, maddelerNoktalar, maddelerTuval} from './Maddeler';
import {Platform, platformEngeller, platformKamera, platformNoktalar, platformTuval} from './Platform';
import {Tarih, tarihEngeller, tarihKamera, tarihNoktalar, tarihTuval} from './Tarih';
import {YamaFark, yamaFarkEngeller, yamaFarkKamera, yamaFarkNoktalar, yamaFarkTuval} from './YamaFark';

type Sablon = {
  // Tuvali çizer: ana pencere (0, 0) ve varsa ikinci paneller.
  Bilesen: React.FC<SahneProps>;
  noktalar: (s: Sahne, haber: Haber) => Nokta[];
  // Maskotun örtmemesi gereken yazılar ve tuşlar (ikinci paneller dahil).
  engeller: (s: Sahne, haber: Haber) => Engel[];
  // Kameranın kelime anlarına bağlı yönelişleri ve tuvalin dikey kapsamı (ana pencere iç y'si).
  kamera: (s: Sahne, haber: Haber) => KameraAnahtari[];
  tuval: (s: Sahne, haber: Haber) => Tuval;
  hareket: string;
};

// Şablon sürümü tools/video_uret.py içindeki SABLON_SURUMU ile birlikte artar (görünüm değişince video anahtarı değişsin).
export const SABLON: Record<SablonAdi, Sablon> = {
  baslik: {Bilesen: Baslik, noktalar: baslikNoktalar, engeller: baslikEngeller, kamera: baslikKamera, tuval: baslikTuval, hareket: 'bas'},
  kaynak: {Bilesen: Kaynak, noktalar: kaynakNoktalar, engeller: kaynakEngeller, kamera: kaynakKamera, tuval: kaynakTuval, hareket: 'tara'},
  maddeler: {Bilesen: Maddeler, noktalar: maddelerNoktalar, engeller: maddelerEngeller, kamera: maddelerKamera, tuval: maddelerTuval, hareket: 'bas'},
  yama_fark: {Bilesen: YamaFark, noktalar: yamaFarkNoktalar, engeller: yamaFarkEngeller, kamera: yamaFarkKamera, tuval: yamaFarkTuval, hareket: 'bas'},
  tarih: {Bilesen: Tarih, noktalar: tarihNoktalar, engeller: tarihEngeller, kamera: tarihKamera, tuval: tarihTuval, hareket: 'zipla'},
  fiyat: {Bilesen: Fiyat, noktalar: fiyatNoktalar, engeller: fiyatEngeller, kamera: fiyatKamera, tuval: fiyatTuval, hareket: 'zipla'},
  platform: {Bilesen: Platform, noktalar: platformNoktalar, engeller: platformEngeller, kamera: platformKamera, tuval: platformTuval, hareket: 'zipla'},
  kapanis: {Bilesen: Kapanis, noktalar: kapanisNoktalar, engeller: kapanisEngeller, kamera: kapanisKamera, tuval: kapanisTuval, hareket: 'bas'},
};
