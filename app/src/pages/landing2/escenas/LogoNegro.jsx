import { useId } from 'react';

/*
 * El logo negro de la landing 2 (30-10-2026, pedido de Alexis): el mismo logo de Afable (baldosa
 * con el asterisco calado + "Afable" en Sora ExtraBold, como `Logo` de components/Logo.jsx), con la
 * baldosa negra en vez del degradado azul. Solo en la landing 2: el `Logo` compartido no cambia.
 */
function IsotipoNegro({ size, color }) {
  const mid = useId();
  return (
    <svg width={size} height={size} viewBox="0 0 120 120" fill="none" aria-hidden="true">
      <defs>
        <mask id={mid}>
          <rect width="120" height="120" fill="#fff" />
          <g transform="translate(60 60) scale(0.185) translate(-256 -256)" fill="#000">
            <rect x="220" y="41" width="72" height="430" />
            <rect x="220" y="41" width="72" height="430" transform="rotate(45 256 256)" />
            <rect x="220" y="41" width="72" height="430" transform="rotate(90 256 256)" />
            <rect x="220" y="41" width="72" height="430" transform="rotate(135 256 256)" />
          </g>
        </mask>
      </defs>
      <rect width="120" height="120" rx="27" fill={color} mask={`url(#${mid})`} />
    </svg>
  );
}

// `claro`: sobre fondo negro (el pie de página) la baldosa y el nombre van en blanco; el asterisco sigue
// calado, así que se ve el negro del fondo.
export default function LogoNegro({ size = 26, claro = false }) {
  const color = claro ? '#ffffff' : '#0b0b0f';
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
      <IsotipoNegro size={size} color={color} />
      <span style={{ fontWeight: 800, fontSize: size * 0.7, letterSpacing: '-0.02em', color, fontFamily: "'Sora', sans-serif" }}>
        Afable
      </span>
    </span>
  );
}
