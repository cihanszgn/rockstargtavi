// Zaman eğrileri. Bütün hareket `t` (saniye) üzerinden hesaplanır, durum tutulmaz: her kare kendi başına çizilir.

export const sinirla = (v: number, a = 0, b = 1) => Math.min(b, Math.max(a, v));

export const ilerle = (t: number, t0: number, sure: number) => (sure <= 0 ? (t >= t0 ? 1 : 0) : sinirla((t - t0) / sure));

export const cikis = (u: number) => 1 - Math.pow(1 - sinirla(u), 3);

export const girisCikis = (u: number) => {
  const x = sinirla(u);
  return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;
};

// Sönümlü yay: 0'dan 1'e biraz taşarak oturur. dt < 0 ise 0.
export const yay = (dt: number, sonum = 0.55, w = 14) => {
  if (dt <= 0) return 0;
  const wd = w * Math.sqrt(1 - sonum * sonum);
  return 1 - Math.exp(-sonum * w * dt) * (Math.cos(wd * dt) + ((sonum * w) / wd) * Math.sin(wd * dt));
};

// Tuşa basma: 0.08 sn'de iner, 0.22 sn'de geri çıkar. 0 = yukarıda, 1 = tam basılı.
export const basma = (dt: number) => {
  if (dt < 0 || dt > 0.3) return 0;
  if (dt < 0.08) return cikis(dt / 0.08);
  return 1 - cikis((dt - 0.08) / 0.22);
};

// Birden çok basma anından en etkilisini verir.
export const basmalar = (t: number, anlar: number[]) => anlar.reduce((m, a) => Math.max(m, basma(t - a)), 0);

export const karistir = (a: number, b: number, u: number) => a + (b - a) * u;

// Belirli aralıkta görünürlük: girişte ve (istenirse) çıkışta yumuşak.
export const gorunur = (t: number, bas: number, giris = 0.25) => cikis(ilerle(t, bas, giris));
