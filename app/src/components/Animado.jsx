import { forwardRef, useEffect, useRef, useState } from 'react';
import { Box } from '@mui/material';
import { animate, motion, useReducedMotion } from 'framer-motion';

/*
 * Las animaciones de la app (23-10-2026), las mismas de las escenas de la landing pero cortas:
 * nada dura más de medio segundo, porque en la app se trabaja y nadie espera a que las cosas
 * se armen. Con "reducir movimiento" activado no se anima nada: se ve el estado final.
 */

export const EASE = [0.22, 1, 0.36, 1];
export const MotionBox = motion.create(Box);

// Un número que sube desde cero al aparecer y, si cambia, pasa del valor anterior al nuevo.
export function Numero({ valor, formato = (v) => Math.round(v).toLocaleString('es-CL'), duracion = 0.5 }) {
  const reducido = useReducedMotion();
  const destino = Number(valor) || 0;
  const [v, setV] = useState(reducido ? destino : 0);
  const previo = useRef(reducido ? destino : 0);
  useEffect(() => {
    if (reducido) { setV(destino); previo.current = destino; return undefined; }
    // El punto de partida es lo que se está mostrando: si el conteo se corta a la mitad
    // (otro valor, o React montando dos veces en desarrollo), el siguiente sigue desde ahí.
    const c = animate(previo.current, destino, {
      duration: duracion, ease: EASE, onUpdate: (x) => { previo.current = x; setV(x); },
    });
    return () => c.stop();
  }, [destino, duracion, reducido]);
  return formato(v);
}

// Lo que entra: aparece subiendo un poco. `retraso` sirve para escalonar una lista.
export function Entra({ retraso = 0, children, ...props }) {
  const reducido = useReducedMotion();
  return (
    <MotionBox
      initial={reducido ? false : { opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: EASE, delay: retraso }}
      {...props}
    >
      {children}
    </MotionBox>
  );
}

// Una barra de gráfico que crece desde abajo. `i` escalona las barras de una serie.
// Con forwardRef: va dentro de un Tooltip, que necesita llegar al elemento.
export const BarraQueCrece = forwardRef(function BarraQueCrece({ i = 0, sx, ...props }, ref) {
  const reducido = useReducedMotion();
  return (
    <MotionBox
      ref={ref}
      initial={reducido ? false : { scaleY: 0 }}
      animate={{ scaleY: 1 }}
      transition={{ duration: 0.4, ease: EASE, delay: 0.02 * i }}
      sx={{ transformOrigin: 'bottom', transition: 'background-color .3s', ...sx }}
      {...props}
    />
  );
});

// Lo recién hecho se ilumina un instante en verde (una carga, un cuadre).
// El verde va en una capa encima que se apaga, para no pisar el fondo propio de la pieza.
export function Destello({ children, sx, ...props }) {
  const reducido = useReducedMotion();
  return (
    <MotionBox
      initial={reducido ? false : { opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: EASE }}
      sx={{ position: 'relative', bgcolor: 'background.paper', ...sx }}
      {...props}
    >
      {!reducido && (
        <MotionBox
          aria-hidden
          initial={{ opacity: 1 }}
          animate={{ opacity: 0 }}
          transition={{ duration: 1.2, ease: 'easeOut' }}
          sx={{ position: 'absolute', inset: 0, borderRadius: 'inherit', bgcolor: 'rgba(15, 157, 107, 0.14)', pointerEvents: 'none' }}
        />
      )}
      {children}
    </MotionBox>
  );
}

// Los tres puntos de "Afable está escribiendo".
export function Escribiendo({ color = 'var(--af-color)' }) {
  const reducido = useReducedMotion();
  return (
    <Box component="span" sx={{ display: 'inline-flex', gap: '4px', alignItems: 'center' }}>
      {[0, 1, 2].map((i) => (
        <MotionBox
          key={i}
          component="span"
          animate={reducido ? undefined : { opacity: [0.25, 1, 0.25] }}
          transition={{ duration: 1.1, repeat: Infinity, delay: 0.18 * i }}
          sx={{ width: 5, height: 5, borderRadius: '50%', bgcolor: color, opacity: reducido ? 0.6 : undefined }}
        />
      ))}
    </Box>
  );
}
