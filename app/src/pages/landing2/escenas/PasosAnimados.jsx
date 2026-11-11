import { useEffect, useRef, useState } from 'react';
import { motion, useInView, useReducedMotion } from 'framer-motion';
import { Check } from 'lucide-react';
import { Isotipo } from './Ilustraciones';

/*
 * "Empieza hoy, sin implementación" (11-11-2026, landing principal): los tres pasos se encienden por
 * turno y cada uno anima su dibujo, en los colores de Afable.
 *   1 Conecta:  el SII, el banco y el ERP se unen por líneas al isotipo de Afable.
 *   2 Pide:     en el chat aparece el pedido y el agente responde.
 *   3 Confirma: la factura lista, el cursor presiona "Confirmar" y aparece el check.
 * Arriba de cada paso, una barra se llena mientras está encendido. Con "reducir movimiento" todo
 * queda quieto y terminado.
 */

const TURNO = 3600;
const NEGRO = '#0b0b0f';
const GRIS = '#e6e5e2';
const FUENTE = { fontFamily: "'Inter', sans-serif" };
const trazo = { stroke: NEGRO, strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round' };

// Aparece en `delay` segundos solo si el paso está animando; si no, ya está.
function aparece(animar, delay, desde = { opacity: 0, y: 6 }) {
  if (!animar) return { initial: false, animate: { opacity: 1, y: 0, scale: 1 } };
  return { initial: desde, animate: { opacity: 1, y: 0, scale: 1 }, transition: { duration: 0.4, delay, ease: [0.22, 1, 0.36, 1] } };
}

function Conecta({ animar, quieto }) {
  const lineas = [
    'M70 35 C 130 35, 140 75, 186 75',
    'M70 75 H186',
    'M70 115 C 130 115, 140 75, 186 75',
  ];
  return (
    <svg viewBox="0 0 260 150" width="100%" height="100%" aria-hidden="true">
      {lineas.map((d, i) => (
        <g key={d}>
          <motion.path d={d} fill="none" stroke={NEGRO} strokeWidth="1.8"
            initial={animar ? { pathLength: 0 } : false} animate={{ pathLength: 1 }}
            transition={{ duration: 0.7, delay: 0.2 + i * 0.35, ease: 'easeInOut' }} />
          {animar && !quieto && (
            <circle r="3.5" fill={NEGRO}>
              <animateMotion dur="1.4s" begin={`${1.2 + i * 0.35}s`} repeatCount="indefinite" path={d} />
            </circle>
          )}
        </g>
      ))}
      {/* SII */}
      <g transform="translate(44 35)">
        <rect x="-18" y="-15" width="36" height="30" rx="6" fill="#fff" {...trazo} />
        <text y="4" textAnchor="middle" fontSize="10" fontWeight="700" fill={NEGRO} style={FUENTE}>SII</text>
      </g>
      {/* Banco */}
      <g transform="translate(44 75)">
        <rect x="-18" y="-15" width="36" height="30" rx="6" fill="#fff" {...trazo} />
        <path d="M-9 -3 L0 -9 L9 -3 Z M-7 -1 V6 M0 -1 V6 M7 -1 V6 M-10 8 H10" fill="none" {...trazo} strokeWidth="1.6" />
      </g>
      {/* ERP */}
      <g transform="translate(44 115)">
        <rect x="-18" y="-15" width="36" height="30" rx="6" fill={GRIS} {...trazo} />
        <text y="4" textAnchor="middle" fontSize="10" fontWeight="700" fill={NEGRO} style={FUENTE}>ERP</text>
      </g>
      <motion.g {...aparece(animar, 1.2, { opacity: 0, scale: 0.6 })} style={{ originX: '210px', originY: '75px' }}>
        <g transform="translate(212 75)"><Isotipo s={46} quieto={quieto || !animar} dur="10s" /></g>
      </motion.g>
    </svg>
  );
}

function Pide({ animar }) {
  return (
    <svg viewBox="0 0 260 150" width="100%" height="100%" aria-hidden="true">
      <rect x="18" y="14" width="224" height="122" rx="12" fill="#fff" {...trazo} strokeWidth="1.6" />
      <motion.g {...aparece(animar, 0.2)}>
        <rect x="84" y="30" width="144" height="28" rx="14" fill={NEGRO} />
        <text x="156" y="48" textAnchor="middle" fontSize="11" fill="#fff" style={FUENTE}>Factura el pedido 142</text>
      </motion.g>
      {/* El agente escribe… */}
      {animar && (
        <motion.g initial={{ opacity: 0 }} animate={{ opacity: [0, 1, 1, 0] }}
          transition={{ duration: 1.3, delay: 0.8, times: [0, 0.15, 0.85, 1] }}>
          <rect x="32" y="70" width="52" height="26" rx="13" fill={GRIS} />
          {[0, 1, 2].map((i) => (
            <motion.circle key={i} cx={46 + i * 12} cy="83" r="3" fill={NEGRO}
              animate={{ y: [0, -3, 0] }} transition={{ duration: 0.6, repeat: Infinity, delay: i * 0.12 }} />
          ))}
        </motion.g>
      )}
      {/* …y responde */}
      <motion.g {...aparece(animar, 2.1)}>
        <rect x="32" y="70" width="150" height="28" rx="14" fill={GRIS} />
        <text x="46" y="88" fontSize="11" fill={NEGRO} style={FUENTE}>Lista para revisar.</text>
        <rect x="32" y="104" width="104" height="20" rx="10" fill="#fff" {...trazo} strokeWidth="1.4" />
        <text x="46" y="118" fontSize="10" fill={NEGRO} style={FUENTE}>Factura N° 1044</text>
      </motion.g>
    </svg>
  );
}

function Confirma({ animar }) {
  return (
    <svg viewBox="0 0 260 150" width="100%" height="100%" aria-hidden="true">
      <rect x="34" y="14" width="192" height="122" rx="12" fill="#fff" {...trazo} strokeWidth="1.6" />
      <text x="50" y="38" fontSize="11.5" fontWeight="700" fill={NEGRO} style={FUENTE}>Factura N° 1044</text>
      <path d="M50 54 H150 M50 68 H122" {...trazo} strokeWidth="1.6" stroke="#c9c8c4" />
      <text x="50" y="94" fontSize="13" fontWeight="700" fill={NEGRO} style={FUENTE}>$148.750</text>
      {/* Botón Confirmar: se hunde cuando llega el cursor */}
      <motion.g style={{ originX: '170px', originY: '111px' }}
        initial={false} animate={animar ? { scale: [1, 1, 0.92, 1] } : { scale: 1 }}
        transition={{ duration: 1.8, times: [0, 0.72, 0.8, 0.9] }}>
        <rect x="128" y="100" width="84" height="24" rx="12" fill={NEGRO} />
        <text x="170" y="116" textAnchor="middle" fontSize="10.5" fontWeight="600" fill="#fff" style={FUENTE}>Confirmar</text>
      </motion.g>
      {/* Cursor */}
      {animar && (
        <motion.path d="M0 0 L0 15 L4 11 L7 18 L10 17 L7 10 L12 10 Z" fill="#fff" stroke={NEGRO} strokeWidth="1.4" strokeLinejoin="round"
          initial={{ x: 236, y: 150, opacity: 0 }} animate={{ x: 176, y: 108, opacity: [0, 1, 1] }}
          transition={{ duration: 1.1, delay: 0.3, ease: [0.22, 1, 0.36, 1] }} />
      )}
      {/* Check */}
      <motion.g {...aparece(animar, 1.8, { opacity: 0, scale: 0.4 })} style={{ originX: '214px', originY: '22px' }}>
        <circle cx="214" cy="22" r="13" fill="#007956" />
        <path d="M208 22 l4 4 l7 -8" fill="none" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
      </motion.g>
    </svg>
  );
}

const DIBUJOS = [Conecta, Pide, Confirma];

export default function PasosAnimados({ pasos }) {
  const ref = useRef(null);
  const visible = useInView(ref, { amount: 0.35 });
  const quieto = useReducedMotion();
  const [activo, setActivo] = useState(-1);
  const [vuelta, setVuelta] = useState(0);

  useEffect(() => {
    if (quieto || !visible) return undefined;
    setActivo(0);
    const t = setInterval(() => {
      setActivo((a) => {
        if (a === pasos.length - 1) setVuelta((v) => v + 1);
        return (a + 1) % pasos.length;
      });
    }, TURNO);
    return () => clearInterval(t);
  }, [visible, quieto, pasos.length]);

  return (
    <ol className="lp-pasos lp3-pasos" ref={ref}>
      {pasos.map((p, i) => {
        const Dibujo = DIBUJOS[i];
        const encendido = quieto || i === activo;
        return (
          <li key={p.titulo} className={`lp-paso lp3-paso${encendido ? ' is-activo' : ''}`}
            style={{ '--turno': `${TURNO}ms` }}>
            <span className="lp3-paso__barra" key={`b-${vuelta}-${i === activo}`} aria-hidden="true" />
            <div className="lp3-paso__dibujo">
              <Dibujo key={`${vuelta}-${i === activo}`} animar={!quieto && i === activo} quieto={quieto} />
            </div>
            <span className="lp-paso__n">{i === pasos.length - 1 ? <Check size={14} /> : i + 1}</span>
            <h3>{p.titulo}</h3>
            <p>{p.texto}</p>
          </li>
        );
      })}
    </ol>
  );
}
