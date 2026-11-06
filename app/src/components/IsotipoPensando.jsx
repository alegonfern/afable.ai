import { motion, useReducedMotion } from 'framer-motion';
import { AfableMark } from './Logo';

/*
 * El signo de Afable (negro desde el 30-10-2026, como el logo oficial; antes índigo), girando mientras Afable trabaja (25-10-2026), al estilo del
 * logo de Claude cuando piensa: gira un cuarto de vuelta, se detiene un instante y sigue,
 * con una leve pulsación en cada giro. Media vuelta por ciclo, porque el asterisco se ve
 * igual a los 180°: así el ciclo empalma sin salto. Quieto, es el signo del asistente.
 * Con "reducir movimiento" no gira.
 */
export default function IsotipoPensando({ girando = true, size = 20, color = 'var(--af-acento, #0b0b0f)' }) {
  const reducido = useReducedMotion();
  const anima = girando && !reducido;
  return (
    <motion.span
      aria-hidden="true"
      style={{ display: 'inline-flex', width: size, height: size, flexShrink: 0, transformOrigin: '50% 50%' }}
      animate={anima ? { rotate: [0, 90, 90, 180, 180], scale: [1, 0.82, 1, 0.82, 1] } : { rotate: 0, scale: 1 }}
      transition={anima
        ? { duration: 1.4, times: [0, 0.3, 0.5, 0.8, 1], ease: 'easeInOut', repeat: Infinity }
        : { duration: 0.3 }}
    >
      <AfableMark size={size} color={color} />
    </motion.span>
  );
}
