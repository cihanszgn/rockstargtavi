import React from 'react';

// Basit çizgi simgeler (24x24 tuval). Hepsi bu proje için çizildi; dış simge seti kullanılmadı.
const YOLLAR: Record<string, React.ReactNode> = {
  haber: (
    <>
      <rect x="3" y="4" width="14" height="16" rx="2" />
      <path d="M17 8h3v10a2 2 0 0 1-4 0" />
      <path d="M7 8.5h6M7 12h6M7 15.5h4" />
    </>
  ),
  guncelleme: (
    <>
      <path d="M19.5 10A8 8 0 0 0 5.6 7.2L4 9" />
      <path d="M4 4.5V9h4.5" />
      <path d="M4.5 14a8 8 0 0 0 13.9 2.8L20 15" />
      <path d="M20 19.5V15h-4.5" />
    </>
  ),
  indirim: (
    <>
      <circle cx="7" cy="7" r="2.6" />
      <circle cx="17" cy="17" r="2.6" />
      <path d="M18.5 5.5l-13 13" />
    </>
  ),
  ucretsiz: (
    <>
      <rect x="3.5" y="9" width="17" height="11.5" rx="1.5" />
      <path d="M3.5 13h17M12 9v11.5" />
      <path d="M12 9C10.5 5.5 6.5 4.8 6.5 7.2 6.5 8.6 9 9 12 9c3 0 5.5-.4 5.5-1.8 0-2.4-4-1.7-5.5 1.8z" />
    </>
  ),
  cikis: <path d="M12 2.8l2.3 6 6 2.2-6 2.3-2.3 6-2.3-6-6-2.3 6-2.2z" />,
  kaynak: (
    <>
      <path d="M12 3l8 3v6c0 4.6-3.4 8-8 9-4.6-1-8-4.4-8-9V6z" />
      <path d="M8.3 12.2l2.6 2.6 4.8-5.2" />
    </>
  ),
  liste: (
    <>
      <path d="M9.5 6.5H20M9.5 12H20M9.5 17.5H20" />
      <path d="M4 6.5h1.5M4 12h1.5M4 17.5h1.5" />
    </>
  ),
  yama: (
    <>
      <path d="M4 7h9.5M18.5 7H20M4 17h3.5M12.5 17H20" />
      <circle cx="16" cy="7" r="2.5" />
      <circle cx="10" cy="17" r="2.5" />
    </>
  ),
  takvim: (
    <>
      <rect x="3.5" y="5" width="17" height="15.5" rx="2" />
      <path d="M3.5 10h17M8 3v4M16 3v4" />
      <path d="M8 14h2M14 14h2M8 17h2" />
    </>
  ),
  fiyat: (
    <>
      <path d="M3.5 12.5l9-9h8v8l-9 9z" />
      <circle cx="16" cy="8" r="1.6" />
    </>
  ),
  platform: (
    <>
      <path d="M7.5 8h9a4.8 4.8 0 0 1 4.6 6.2l-.9 3a2.4 2.4 0 0 1-4 1L14.4 16H9.6l-1.8 2.2a2.4 2.4 0 0 1-4-1l-.9-3A4.8 4.8 0 0 1 7.5 8z" />
      <path d="M8 10.5v3.4M6.3 12.2h3.4" />
      <path d="M15.5 11.5h.01M17.5 13.3h.01" />
    </>
  ),
  site: (
    <>
      <circle cx="12" cy="12" r="8.8" />
      <path d="M3.2 12h17.6" />
      <path d="M12 3.2c2.4 2.4 3.6 5.3 3.6 8.8s-1.2 6.4-3.6 8.8c-2.4-2.4-3.6-5.3-3.6-8.8S9.6 5.6 12 3.2z" />
    </>
  ),
  kilit: (
    <>
      <rect x="5" y="10.5" width="14" height="10" rx="2" />
      <path d="M8 10.5V8a4 4 0 0 1 8 0v2.5" />
    </>
  ),
  saat: (
    <>
      <circle cx="12" cy="12" r="8.8" />
      <path d="M12 7v5.2l3.2 2" />
    </>
  ),
  onay: <path d="M5 12.5l4.5 4.5L19 7.5" />,
  ok: <path d="M4 12h15M13 6l6 6-6 6" />,
  magaza: (
    <>
      <path d="M5 8h14l-1.2 12.5H6.2z" />
      <path d="M9 10V6.5a3 3 0 0 1 6 0V10" />
    </>
  ),
};

export const Simge: React.FC<{ad: string; boyut: number; renk: string; kalinlik?: number; style?: React.CSSProperties}> = ({
  ad,
  boyut,
  renk,
  kalinlik = 2.2,
  style,
}) => (
  <svg
    width={boyut}
    height={boyut}
    viewBox="0 0 24 24"
    fill="none"
    stroke={renk}
    strokeWidth={kalinlik}
    strokeLinecap="round"
    strokeLinejoin="round"
    style={{display: 'block', ...style}}
  >
    {YOLLAR[ad] ?? YOLLAR.haber}
  </svg>
);
