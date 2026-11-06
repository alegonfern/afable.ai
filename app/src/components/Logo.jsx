import React, { useId } from 'react';

// Isotipo de Afable: asterisco de 8 brazos (desde el 17-10-2026; antes "núcleo abierto",
// anillo + 8 rayos). Cuatro barras rectas que se cruzan, puntas cuadradas. viewBox 0 0 512 512.
// Geometría sin color propio: el color lo pone quien lo usa, como relleno.
const CORE = (
  <>
    <rect x="220" y="41" width="72" height="430" />
    <rect x="220" y="41" width="72" height="430" transform="rotate(45 256 256)" />
    <rect x="220" y="41" width="72" height="430" transform="rotate(90 256 256)" />
    <rect x="220" y="41" width="72" height="430" transform="rotate(135 256 256)" />
  </>
);

// Solo el núcleo, monocromo — para colocar sobre fondos de color (sidebar/header)
export const AfableMark = ({ size = 15, color = '#fff' }) => (
  <svg width={size} height={size} viewBox="0 0 512 512" fill={color} aria-hidden="true">
    {CORE}
  </svg>
);

// Isotipo completo: baldosa con el asterisco CALADO (17-10-2026): el símbolo es un hueco por donde se ve
// el fondo. Desde el 30-10-2026 la baldosa es NEGRA (antes degradado índigo): es el logo oficial. Toma
// --af-acento, que es negro en modo claro y claro en modo oscuro, para que se vea en los dos.
export const Isotipo = ({ size = 28 }) => {
  const mid = useId();
  return (
    <svg width={size} height={size} viewBox="0 0 120 120" fill="none" aria-hidden="true">
      <defs>
        <mask id={mid}>
          <rect width="120" height="120" fill="#fff" />
          <g transform="translate(60 60) scale(0.185) translate(-256 -256)" fill="#000">
            {CORE}
          </g>
        </mask>
      </defs>
      <rect width="120" height="120" rx="27" mask={`url(#${mid})`} style={{ fill: 'var(--af-acento, #0b0b0f)' }} />
    </svg>
  );
};

// Wordmark: isotipo + "Afable" en Sora ExtraBold
export const Logo = ({ size = 26 }) => (
  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
    <Isotipo size={size} />
    <span
      style={{
        fontWeight: 800,
        fontSize: size * 0.7,
        letterSpacing: '-0.02em',
        color: 'var(--af-acento, #0b0b0f)',
        fontFamily: "'Sora', sans-serif",
      }}
    >
      Afable
    </span>
  </span>
);
