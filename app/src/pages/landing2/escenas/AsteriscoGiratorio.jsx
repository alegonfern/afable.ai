import { useEffect, useState } from 'react';
import { motion, useScroll, useTransform, useReducedMotion } from 'framer-motion';

/*
 * Asterisco de Afable fijo en la esquina inferior derecha de la landing 2 (06-11-2026, pedido de
 * Alexis): solo la parte de dentro del isotipo, sin la baldosa, y gira a medida que se baja la
 * página (una vuelta cada 800 px; vuelve al subir). Negro; pasa a blanco cuando queda sobre el pie
 * de página negro (`.lp2-pie`). No intercepta clics.
 */
const LADO = 24; // distancia al borde, en px

export default function AsteriscoGiratorio({ size = 40 }) {
  const { scrollY } = useScroll();
  const rotate = useTransform(scrollY, (y) => (y / 800) * 360);
  const reducir = useReducedMotion();
  const [sobrePie, setSobrePie] = useState(false);

  useEffect(() => {
    const revisar = () => {
      const pie = document.querySelector('.lp2-pie');
      if (!pie) return;
      const centro = window.innerHeight - LADO - size / 2;
      setSobrePie(pie.getBoundingClientRect().top < centro);
    };
    revisar();
    window.addEventListener('scroll', revisar, { passive: true });
    window.addEventListener('resize', revisar);
    return () => {
      window.removeEventListener('scroll', revisar);
      window.removeEventListener('resize', revisar);
    };
  }, [size]);

  return (
    <motion.div
      aria-hidden="true"
      style={{
        position: 'fixed', right: LADO, bottom: LADO, zIndex: 40, width: size, height: size,
        pointerEvents: 'none', rotate: reducir ? 0 : rotate,
      }}
    >
      <svg
        width={size} height={size} viewBox="0 0 512 512"
        fill={sobrePie ? '#ffffff' : '#0b0b0f'} style={{ display: 'block', transition: 'fill .3s' }}
      >
        <rect x="220" y="41" width="72" height="430" />
        <rect x="220" y="41" width="72" height="430" transform="rotate(45 256 256)" />
        <rect x="220" y="41" width="72" height="430" transform="rotate(90 256 256)" />
        <rect x="220" y="41" width="72" height="430" transform="rotate(135 256 256)" />
      </svg>
    </motion.div>
  );
}
