// tools/video_uret.py `props_kur` çıktısının biçimi. Alan adları iki tarafta aynı kalmalı.

export type Kelime = {k: string; b: number; s: number};

export type Parca = {b: number; s: number; bitis: number; satirlar: number[][]; olcek: number};

export type AltKartVeri = {simge: string; baslik: string; alt: string; baslik_olcek: number; alt_olcek: number};

export type SablonAdi = 'baslik' | 'kaynak' | 'maddeler' | 'yama_fark' | 'tarih' | 'fiyat' | 'platform' | 'kapanis';

export type Sahne = {
  sablon: SablonAdi;
  bas: number;
  bit: number;
  // Şablona özgü veri; her şablon kendi tipine çevirir (sahne/*.tsx).
  veri: Record<string, unknown> & {pencere?: string};
  alt_kart: AltKartVeri;
  maskot: {hareket: string};
  altyazi: Kelime[];
};

export type Platform = {ad: string; renk: string};

export type Haber = {
  oyun: string;
  tur: string;
  tur_etiket: string;
  platformlar: Platform[];
  tarih: string;
  tarih_metin: string;
};

export type VideoProps = {
  surum: number;
  id: string;
  dil: string;
  fps: number;
  boyut: number[];
  ses: string;
  sure: number;
  haber: Haber;
  sahneler: Sahne[];
  kelimeler: Kelime[];
  parcalar: Parca[];
  // Kapak resminin karesi (tools/video_uret.py kapak_karesi): başlık sahnesinin girişleri bitmiş, kamera bütün başlıkta.
  kapak_kare?: number;
  // Yalnız HaberKapak kompozisyonu verir: altyazısız, sessiz, tek kare.
  kapak?: boolean;
  // Yalnız render.mjs --denetle verir: her karede yazıların ve çiplerin yeri konsola yazılır (src/denetim.tsx).
  denetim?: boolean;
};

export type SahneProps = {s: Sahne; t: number; haber: Haber};

// Maskotun duracağı yer: x mutlak merkez, y pencere üst kenarına göre ayak hizası.
// zemin: üstünde durduğu öğenin mutlak x aralığı; gövde bir yazıyı örterse maskot bu aralıkta kayar.
export type Nokta = {t: number; x: number; y: number; eylem: 'bas' | 'dur' | 'tara'; x2?: number; sure?: number; zemin?: [number, number]};

// Maskot gövdesinin örtmemesi gereken alan (yazı, tuş): x mutlak, y pencere iç üst kenarına göre.
// kamera: yalnız kameranın kaçındığı kutu (geniş bir tuşun boş ucu gibi); maskot üstüne basabilir.
export type Engel = {x0: number; x1: number; y0: number; y1: number; kamera?: boolean};

// Kameranın `t` anında yöneldiği yer: odak (x mutlak, y pencere iç üst kenarına göre) sahne ortasına gelir, k yakınlık.
export type KameraAnahtari = {t: number; x: number; y: number; k: number};
