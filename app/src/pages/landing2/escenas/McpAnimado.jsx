import { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion, useInView, useReducedMotion } from 'framer-motion';
import { Isotipo } from './Ilustraciones';

/*
 * Afable por MCP (11-11-2026, landing principal): la IA que el cliente ya usa conversa con Afable.
 * Arriba, las cinco IA; por turno se enciende una y abajo aparece una pregunta hecha desde ella y la
 * respuesta con datos de Afable (empresa de ejemplo). Con "reducir movimiento" queda la primera.
 */

export const IAS = [
  { nombre: 'ChatGPT', pide: '¿Cuánto me deben este mes?', responde: '$1.920.000 en 3 facturas vencidas. ¿Te armo los recordatorios?' },
  { nombre: 'Claude', pide: 'Factura el pedido 142.', responde: 'Lista la factura N° 1044 por $148.750. ¿La confirmas?' },
  { nombre: 'Gemini', pide: 'Concilia el banco de octubre.', responde: '41 de 46 movimientos calzan. Te dejo 5 para revisar.' },
  { nombre: 'Copilot', pide: '¿Cuánto IVA pago este mes?', responde: 'El F29 de octubre sale en $612.400.' },
  { nombre: 'Perplexity', pide: '¿Qué proveedores pago esta semana?', responde: '3 pagos por $1.050.000; el más grande, Distribuidora Sur.' },
];

const TURNO = 3200;
const EASE = [0.22, 1, 0.36, 1];

export default function McpAnimado() {
  const ref = useRef(null);
  const visible = useInView(ref, { amount: 0.35 });
  const quieto = useReducedMotion();
  const [activo, setActivo] = useState(0);

  useEffect(() => {
    if (quieto || !visible) return undefined;
    const t = setInterval(() => setActivo((a) => (a + 1) % IAS.length), TURNO);
    return () => clearInterval(t);
  }, [visible, quieto]);

  const ia = IAS[activo];
  return (
    <div className="lp3-mcp" ref={ref}>
      <div className="lp3-mcp__ias">
        {IAS.map((x, i) => (
          <span key={x.nombre} className={`lp3-mcp__ia${i === activo ? ' is-activa' : ''}`}>{x.nombre}</span>
        ))}
      </div>

      {/* La conexión: la IA elegida ↔ MCP ↔ Afable */}
      <div className="lp3-mcp__puente" aria-hidden="true">
        <span className="lp3-mcp__linea">
          {!quieto && <motion.i key={activo} initial={{ left: '0%' }} animate={{ left: '100%' }} transition={{ duration: 1.1, ease: 'easeInOut' }} />}
        </span>
        <span className="lp3-mcp__etiqueta">MCP</span>
        <span className="lp3-mcp__linea">
          {!quieto && <motion.i key={`b${activo}`} initial={{ left: '0%' }} animate={{ left: '100%' }} transition={{ duration: 1.1, delay: 0.5, ease: 'easeInOut' }} />}
        </span>
        <svg width="40" height="40" viewBox="-20 -20 40 40"><Isotipo s={34} quieto={quieto} dur="10s" /></svg>
      </div>

      <div className="lp3-mcp__chat">
        <AnimatePresence mode="wait" initial={false}>
          <motion.div key={ia.nombre} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.35, ease: EASE }}>
            <div className="lp3-mcp__desde">Desde {ia.nombre}</div>
            <div className="lp3-mcp__yo">{ia.pide}</div>
            <motion.div className="lp3-mcp__afable" initial={quieto ? false : { opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: 0.9, ease: EASE }}>
              <svg width="16" height="16" viewBox="-8 -8 16 16" aria-hidden="true"><Isotipo s={16} quieto /></svg>
              <span>{ia.responde}</span>
            </motion.div>
          </motion.div>
        </AnimatePresence>
        <div className="lp3-mcp__nota">Empresa de ejemplo.</div>
      </div>
    </div>
  );
}
