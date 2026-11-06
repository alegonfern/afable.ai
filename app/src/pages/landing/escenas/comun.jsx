import { useEffect, useRef, useState } from 'react';
import { animate, motion } from 'framer-motion';
import IsotipoPensando from '../../../components/IsotipoPensando';

// Lo que comparten las escenas: la curva de Sintropix, el formato de pesos y dos piezas.
export const EASE = [0.22, 1, 0.36, 1];
export const MS_POR_LETRA = 24;
export const pesos = (n) => `$${Math.round(n).toLocaleString('es-CL')}`;

// Un número que pasa del valor anterior al nuevo (o sube desde cero al aparecer).
export function Cuenta({ valor, desdeCero = false, retraso = 0, sinAnimar, formato = pesos }) {
  const [v, setV] = useState(sinAnimar || !desdeCero ? valor : 0);
  const previo = useRef(desdeCero ? 0 : valor);
  useEffect(() => {
    if (sinAnimar) { setV(valor); previo.current = valor; return undefined; }
    const c = animate(previo.current, valor, {
      duration: 0.8, ease: EASE, delay: retraso, onUpdate: (x) => { previo.current = x; setV(x); },
    });
    return () => c.stop();
  }, [valor, retraso, sinAnimar]);
  return formato(v);
}

// "Afable está trabajando": el signo girando, como en el chat de la app (IsotipoPensando), y los
// tres puntos.
export function Escribiendo() {
  return (
    <motion.div
      className="esc__escribiendo"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
    >
      <IsotipoPensando size={16} color="var(--color)" />
      {[0, 1, 2].map((i) => (
        <motion.span
          className="esc__punto"
          key={i}
          animate={{ opacity: [0.25, 1, 0.25] }}
          transition={{ duration: 1.1, repeat: Infinity, delay: 0.18 * i }}
        />
      ))}
    </motion.div>
  );
}
