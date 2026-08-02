import React, { useId } from 'react';
import { useTheme } from '@mui/material';

// Isotipo canónico Afable "núcleo abierto" — anillo + 8 rayos (viewBox 0 0 512 512)
// nuevo_logo.svg: geometría sin color propio, el color lo define quien lo usa
const CORE = (
  <>
    <circle cx="256" cy="256" r="57" strokeWidth="44" />
    <g strokeLinecap="round" strokeWidth="48">
      <line x1="256" y1="137" x2="256" y2="49" />
      <line x1="256" y1="137" x2="256" y2="49" transform="rotate(45 256 256)" />
      <line x1="256" y1="137" x2="256" y2="49" transform="rotate(90 256 256)" />
      <line x1="256" y1="137" x2="256" y2="49" transform="rotate(135 256 256)" />
      <line x1="256" y1="137" x2="256" y2="49" transform="rotate(180 256 256)" />
      <line x1="256" y1="137" x2="256" y2="49" transform="rotate(225 256 256)" />
      <line x1="256" y1="137" x2="256" y2="49" transform="rotate(270 256 256)" />
      <line x1="256" y1="137" x2="256" y2="49" transform="rotate(315 256 256)" />
    </g>
  </>
);

// Solo el núcleo, monocromo — para colocar sobre fondos de color (sidebar/header)
export const AfableMark = ({ size = 15, color = '#fff' }) => (
  <svg width={size} height={size} viewBox="0 0 512 512" fill="none" stroke={color} aria-hidden="true">
    {CORE}
  </svg>
);

// Isotipo completo: tile con gradiente de marca + núcleo blanco knockout
export const Isotipo = ({ size = 28 }) => {
  const gid = useId();
  return (
    <svg width={size} height={size} viewBox="0 0 120 120" fill="none" aria-hidden="true">
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="120" y2="120" gradientUnits="userSpaceOnUse">
          <stop stopColor="#586AD0" />
          <stop offset="1" stopColor="#2F42A6" />
        </linearGradient>
      </defs>
      <rect width="120" height="120" rx="27" fill={`url(#${gid})`} />
      <g transform="translate(60 60) scale(0.185) translate(-256 -256)" fill="none" stroke="#fff">
        {CORE}
      </g>
    </svg>
  );
};

// Wordmark: isotipo + "Afable" en Sora ExtraBold
export const Logo = ({ size = 26 }) => {
  const theme = useTheme();
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
      <Isotipo size={size} />
      <span
        style={{
          fontWeight: 800,
          fontSize: size * 0.7,
          letterSpacing: '-0.02em',
          color: theme.palette.text.primary,
          fontFamily: "'Sora', sans-serif",
        }}
      >
        Afable
      </span>
    </span>
  );
};
