import { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion, useInView, useReducedMotion } from 'framer-motion';
import { Calculator, Check, PackageOpen, ShoppingCart, Wallet } from 'lucide-react';
import IsotipoPensando from '../../../components/IsotipoPensando';
import { EASE } from './comun';
import './escenas.css';

/*
 * Dos secciones de la landing (25-10-2026):
 *   - AgentesAnimados: un agente detrás de cada módulo. Por turno, uno se enciende y muestra lo que
 *     está haciendo, con el signo girando (los textos de lo que hace son de una empresa de ejemplo).
 *   - DoloresAnimados: cada dolor se tacha y aparece cómo lo resuelve Afable, uno tras otro.
 * Con "reducir movimiento" se muestran quietas y terminadas.
 */

const AGENTES = [
  { icono: ShoppingCart, nombre: 'Agente de Ventas', hace: 'Cotiza, confirma órdenes, factura y registra cobros.', ahora: 'Emitiendo la factura N° 1044' },
  { icono: PackageOpen, nombre: 'Agente de Compras', hace: 'Arma solicitudes, registra facturas de proveedor y repone stock.', ahora: 'Armando la solicitud de reposición' },
  { icono: Calculator, nombre: 'Agente de Contabilidad', hace: 'Carga los libros del SII, clasifica documentos y prepara el F29.', ahora: 'Clasificando 12 documentos' },
  { icono: Wallet, nombre: 'Agente de Finanzas', hace: 'Concilia el banco y le dice cuánto le deben, cuánto debe y cómo cierra el mes.', ahora: 'Cruzando el banco con sus facturas' },
];
const TURNO = 2200;

export function AgentesAnimados() {
  const ref = useRef(null);
  const visible = useInView(ref, { amount: 0.3 });
  const reducido = useReducedMotion();
  const [activo, setActivo] = useState(-1);
  useEffect(() => {
    if (reducido || !visible) return undefined;
    setActivo(0);
    const t = setInterval(() => setActivo((a) => (a + 1) % AGENTES.length), TURNO);
    return () => clearInterval(t);
  }, [visible, reducido]);
  return (
    <div className="esm-agentes" ref={ref}>
      {AGENTES.map((a, i) => {
        const Icono = a.icono;
        const trabajando = i === activo;
        return (
          <motion.article key={a.nombre} className={`esm-agente${trabajando ? ' is-trabajando' : ''}`}
            initial={reducido ? false : { opacity: 0, y: 16 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }}
            transition={{ duration: 0.45, ease: EASE, delay: 0.08 * i }}>
            <div className="esm-agente__cab">
              <span className="esm-agente__icono"><Icono size={18} /></span>
              <b>{a.nombre}</b>
            </div>
            <p>{a.hace}</p>
            <div className="esm-agente__estado">
              <AnimatePresence mode="wait" initial={false}>
                {trabajando ? (
                  <motion.span key="trabaja" className="esm-agente__trabaja" initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -4 }} transition={{ duration: 0.25, ease: EASE }}>
                    <IsotipoPensando size={12} color="var(--color)" /> {a.ahora}…
                  </motion.span>
                ) : (
                  <motion.span key="atento" className="esm-agente__atento" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                    <i /> Atento
                  </motion.span>
                )}
              </AnimatePresence>
            </div>
          </motion.article>
        );
      })}
    </div>
  );
}

const DOLORES = [
  { dolor: 'Facturas que se digitan una por una', solucion: 'Pídala en el chat y queda emitida.' },
  { dolor: 'La conciliación que se deja para fin de mes', solucion: 'El Agente de Finanzas cruza el banco todos los días.' },
  { dolor: 'El F29 armado a última hora', solucion: 'Lo tiene calculado con sus libros del SII.' },
  { dolor: 'No saber cuánto le deben ni cuánto debe', solucion: 'Pregúntelo y lo ve al instante.' },
];

export function DoloresAnimados() {
  const ref = useRef(null);
  const visible = useInView(ref, { amount: 0.35, once: true });
  const reducido = useReducedMotion();
  const [resueltos, setResueltos] = useState(reducido ? DOLORES.length : 0);
  useEffect(() => {
    if (reducido || !visible) return undefined;
    const relojes = DOLORES.map((_, i) => setTimeout(() => setResueltos(i + 1), 500 + 750 * i));
    return () => relojes.forEach(clearTimeout);
  }, [visible, reducido]);
  return (
    <div className="esm-dolores" ref={ref}>
      {DOLORES.map((d, i) => {
        const ok = i < resueltos;
        return (
          <div key={d.dolor} className={`esm-dolor${ok ? ' is-resuelto' : ''}`}>
            <span className="esm-dolor__problema">{d.dolor}</span>
            <AnimatePresence>
              {ok && (
                <motion.span className="esm-dolor__solucion" initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.4, ease: EASE }}>
                  <Check size={14} strokeWidth={3} /> {d.solucion}
                </motion.span>
              )}
            </AnimatePresence>
          </div>
        );
      })}
    </div>
  );
}
