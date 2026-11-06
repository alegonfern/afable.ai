import { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion, useInView, useReducedMotion } from 'framer-motion';
import { Calculator, Check, ChevronRight, ShoppingCart, Zap } from 'lucide-react';
import IsotipoPensando from '../../../components/IsotipoPensando';
import { EASE } from './comun';
import './escenas.css';

/*
 * Dos animaciones chicas de la landing (25-10-2026), con el lenguaje de "Así trabaja Afable":
 *   - ModosAnimados: el selector Módulo / Automatización se desliza solo; en Automatización cada
 *     automatización corre (el signo girando) y se enciende.
 *   - RegistroEnVivo: los movimientos entran arriba de la tabla uno por uno, y el que espera
 *     confirmación pasa por el signo girando hasta quedar conciliado.
 * Corren mientras se ven; con "reducir movimiento" se muestran terminadas.
 */

const SECCIONES = [
  { icono: Calculator, modulo: 'Contabilidad', nombre: 'Resumen del mes' },
  { icono: Calculator, modulo: 'Contabilidad', nombre: 'Conciliación' },
  { icono: ShoppingCart, modulo: 'Ventas', nombre: 'Órdenes de venta' },
];
const AUTOMATIZACIONES = [
  { icono: Calculator, modulo: 'Contabilidad', nombre: 'Conciliar todos los días' },
  { icono: Calculator, modulo: 'Contabilidad', nombre: 'Preparar el F29 el día 10' },
  { icono: ShoppingCart, modulo: 'Ventas', nombre: 'Facturar al confirmar el pedido' },
];

// [modo, filas encendidas, milisegundo]: Módulo → Automatización, que se encienden de a una → vuelta.
const GUION_MODOS = [
  ['modulo', 0, 0], ['auto', 0, 1800], ['auto', 1, 2500], ['auto', 2, 3100], ['auto', 3, 3700],
];
const CICLO_MODOS = 6600;

export function ModosAnimados() {
  const ref = useRef(null);
  const visible = useInView(ref, { amount: 0.4 });
  const reducido = useReducedMotion();
  const [estado, setEstado] = useState(reducido ? ['auto', 3] : ['modulo', 0]);
  const [vuelta, setVuelta] = useState(0);

  useEffect(() => {
    if (reducido || !visible) return undefined;
    const relojes = GUION_MODOS.map(([modo, n, ms]) => setTimeout(() => setEstado([modo, n]), ms));
    relojes.push(setTimeout(() => setVuelta((v) => v + 1), CICLO_MODOS));
    return () => relojes.forEach(clearTimeout);
  }, [visible, reducido, vuelta]);

  const [modo, encendidas] = estado;
  const auto = modo === 'auto';
  return (
    <div className="lp-modos" ref={ref}>
      <div className="lp-modos__switch esm-switch">
        {['modulo', 'auto'].map((m) => (
          <span key={m} className={modo === m ? 'is-activo' : ''}>
            {modo === m && <motion.i layoutId="esm-pastilla" className="esm-switch__pastilla" transition={{ duration: 0.35, ease: EASE }} />}
            <em>{m === 'auto' && <Zap size={13} />}{m === 'auto' ? 'Agente' : 'Módulo'}</em>
          </span>
        ))}
      </div>
      <AnimatePresence mode="wait" initial={false}>
        <motion.div key={modo} initial={{ opacity: 0, x: auto ? 14 : -14 }} animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0 }} transition={{ duration: 0.3, ease: EASE }}>
          {(auto ? AUTOMATIZACIONES : SECCIONES).map((f, i) => {
            const Icono = f.icono;
            const encendida = auto && i < encendidas;
            const corriendo = auto && i === encendidas - 1;
            return (
              <motion.div key={f.nombre} className="lp-modos__fila" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, ease: EASE, delay: 0.06 * i }}>
                <Icono size={15} /> {f.modulo} <em>{f.nombre}</em>
                {auto ? (
                  <span className="esm-estado">
                    {corriendo && <span className="esm-corriendo"><IsotipoPensando size={11} color="var(--color)" /> Corriendo</span>}
                    {encendida && !corriendo && <Check size={13} strokeWidth={3} className="esm-ok" />}
                    <span className={`esp-interruptor${encendida ? ' is-on' : ''}`}><motion.i layout transition={{ duration: 0.3, ease: EASE }} /></span>
                  </span>
                ) : <ChevronRight size={15} className="esm-flecha" />}
              </motion.div>
            );
          })}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}

// Cada cuánto entra un movimiento nuevo, y cuánto tarda en confirmarse el que espera.
const CADA = 1100;
const CONFIRMA = 1300;

export function RegistroEnVivo({ movimientos, estados }) {
  const ref = useRef(null);
  const visible = useInView(ref, { amount: 0.3 });
  const reducido = useReducedMotion();
  const total = movimientos.length;
  // Cuántos ya entraron (el último de la lista entra primero: la tabla va de lo nuevo a lo viejo).
  const [entraron, setEntraron] = useState(reducido ? total : 0);
  const [confirmados, setConfirmados] = useState(reducido);
  const [vuelta, setVuelta] = useState(0);

  useEffect(() => {
    if (reducido || !visible) return undefined;
    setEntraron(0);
    setConfirmados(false);
    const relojes = movimientos.map((_, i) => setTimeout(() => setEntraron(i + 1), 300 + CADA * i));
    const fin = 300 + CADA * (total - 1);
    relojes.push(setTimeout(() => setConfirmados(true), fin + CONFIRMA));
    relojes.push(setTimeout(() => setVuelta((v) => v + 1), fin + CONFIRMA + 3500));
    return () => relojes.forEach(clearTimeout);
  }, [visible, reducido, vuelta, total]); // eslint-disable-line react-hooks/exhaustive-deps

  const filas = movimientos.slice(total - entraron);
  return (
    // El alto de la tabla llena se reserva desde el principio: si creciera fila a fila, empujaría
    // el resto de la página mientras se lee.
    <div className="lp-tabla esm-registro" ref={ref} style={{ '--esm-filas': total }}>
      <div className="lp-tabla__fila lp-tabla__fila--cab">
        <span>Fecha</span><span>Origen</span><span>Detalle</span><span>Monto</span>
        <span className="esm-vivo-cab">Estado <i className="esm-vivo"><b />En vivo</i></span>
      </div>
      <AnimatePresence initial={false}>
        {filas.map((m) => {
          const espera = m.estado === 'Por confirmar';
          const confirmando = espera && !confirmados && entraron === total;
          const estado = espera && confirmados ? 'Conciliado' : m.estado;
          return (
            <motion.div key={m.detalle} className="lp-tabla__fila" layout
              initial={{ opacity: 0, y: -12, backgroundColor: 'rgba(11,11,15,0.06)' }}
              animate={{ opacity: 1, y: 0, backgroundColor: 'rgba(11,11,15,0)' }}
              transition={{ duration: 0.45, ease: EASE, backgroundColor: { duration: 1.4 } }}>
              <span>{m.fecha}</span><span>{m.origen}</span><span>{m.detalle}</span>
              <span className="lp-num">{m.monto}</span>
              <span>
                <AnimatePresence mode="wait" initial={false}>
                  <motion.i key={confirmando ? 'confirmando' : estado}
                    className={`lp-estado lp-estado--${confirmando ? 'info' : estados[estado]}`}
                    initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }}
                    transition={{ duration: 0.25, ease: EASE }}>
                    {confirmando ? <><IsotipoPensando size={10} color="currentColor" /> Confirmando</>
                      : estado === 'Conciliado' && espera ? <><Check size={10} strokeWidth={3} /> Conciliado</> : estado}
                  </motion.i>
                </AnimatePresence>
              </span>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
