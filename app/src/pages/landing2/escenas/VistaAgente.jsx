import { useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Check, ChevronRight, Landmark, ShoppingCart, Wallet, Zap } from 'lucide-react';
import IsotipoPensando from '../../../components/IsotipoPensando';
import { BarraLateral, CabezaPagina, Encabezado } from './HeroAnimado';
import { EASE, Escribiendo } from './comun';
import { TONOS, tonoHecho, tonoModulo } from '../../../theme/tonos';

/*
 * La vista "Agente" de Finanzas tal como es en la app (`pages/modulos/AgentePage.jsx`): a la
 * izquierda la conversación con el agente; a la derecha "Lo que hizo hoy" en vivo y "Lo que hace
 * solo" (sus automatizaciones, con los nombres de `finanzas/automatizaciones.py`). Los títulos de
 * los hechos siguen a `finanzas/actividad.py`. Todas las cifras son de una empresa de ejemplo.
 *
 * Se anima una vez al aparecer: la pregunta, los pasos del agente, la respuesta con su tarjeta
 * para confirmar y, al final, un hecho nuevo que entra arriba en "Lo que hizo hoy".
 */

export const ANCHO = 1180;
export const ALTO = 700;

const HECHOS = [
  { icono: Landmark, tipo: 'cartola', titulo: 'Cruzó la cartola de Banco de Chile', detalle: '41 movimientos conciliados', hora: '12:31', nuevo: true },
  { icono: Wallet, tipo: 'pago', titulo: 'Registró un cobro de OV-0142', detalle: 'Comercial Andes · $148.750', hora: '11:48' },
  { icono: Wallet, tipo: 'pago', titulo: 'Registró un pago de OC-0087', detalle: 'Distribuidora Sur · $412.000', hora: '10:20' },
  { icono: Zap, tipo: 'automatizacion', titulo: 'Avisarme los cobros vencidos', detalle: '3 facturas vencidas por $1.920.000', hora: '08:00' },
  { icono: ShoppingCart, tipo: 'orden', titulo: 'Confirmó OV-0141', detalle: 'Ferretería Los Robles · $63.070', hora: '07:55' },
];

const AUTOMATIZACIONES = [
  { nombre: 'Avisarme los cobros vencidos', cuando: 'Todos los días, 8:00', activa: true },
  { nombre: 'Lo que hay que pagar esta semana', cuando: 'Lunes, 9:00', activa: true },
  { nombre: 'Avisarme si la caja se va a quedar corta', cuando: 'Todos los días, 18:00', activa: false },
];

// Momentos de la animación (ms desde que aparece): pregunta, pasos, respuesta, tarjeta, hecho nuevo.
const MOMENTOS = [300, 1100, 2900, 3500, 4600];

function useMomento(activa, reducido) {
  const [paso, setPaso] = useState(reducido ? MOMENTOS.length : 0);
  useEffect(() => {
    if (reducido || !activa) return undefined;
    const relojes = MOMENTOS.map((ms, i) => setTimeout(() => setPaso(i + 1), ms));
    return () => relojes.forEach(clearTimeout);
  }, [activa, reducido]);
  return paso;
}

const entra = { initial: { opacity: 0, y: 10 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.45, ease: EASE } };

function Conversacion({ paso }) {
  return (
    <div className="va-conv">
      <div className="va-conv__cab">
        <span className="va-avatar" style={{ background: tonoModulo('finanzas').suave, color: tonoModulo('finanzas').color }}><Wallet size={16} /><i><IsotipoPensando size={11} girando={false} /></i></span>
        <div>
          <b>Agente de Finanzas</b>
          <span>Conoce los datos de finanzas, hace el trabajo que le pida y le pide confirmación antes de cambiar algo.</span>
        </div>
      </div>
      <div className="va-conv__hilo">
        <AnimatePresence initial={false}>
          {paso >= 1 && <motion.div key="yo" className="hx-derecha" {...entra}><div className="hx-lat__yo">Concilia el banco de octubre.</div></motion.div>}
          {paso >= 2 && (
            <motion.div key="pasos" className="va-pasos" {...entra}>
              {paso < 3 ? <IsotipoPensando size={13} /> : <Check size={13} color={TONOS.menta.color} />}
              <span>Agente de Finanzas · {paso < 3 ? 'Cruzando el banco con sus facturas…' : 'Cruzó 46 movimientos'}</span>
            </motion.div>
          )}
          {paso === 2 && <motion.div key="esc" {...entra}><Escribiendo /></motion.div>}
          {paso >= 3 && (
            <motion.div key="resp" className="hx-lat__ia" {...entra}>
              Crucé los <b>46 movimientos</b> de la cartola de octubre del Banco de Chile. <b>41</b> calzan con sus
              facturas y <b>5</b> necesitan su revisión.
            </motion.div>
          )}
          {paso >= 4 && (
            <motion.div key="tarjeta" className="va-tarjeta" {...entra}>
              <div className="va-tarjeta__fila"><span>Conciliar 41 movimientos</span><b>$12.480.300</b></div>
              <div className="va-tarjeta__fila va-tarjeta__fila--suave"><span>5 por revisar</span><span>$1.036.900</span></div>
              <div className="va-tarjeta__botones"><b>Confirmar</b><span>Revisar los 5</span></div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
      <div className="hx-lat__entrada va-conv__entrada">Pregúntele al Agente de Finanzas…<i><ChevronRight size={13} /></i></div>
    </div>
  );
}

function Hecho({ h, destella }) {
  const Icono = h.icono;
  return (
    <motion.div
      layout
      className="va-hecho"
      initial={{ opacity: 0, y: -10, backgroundColor: 'rgba(11,11,15,0.06)' }}
      animate={{ opacity: 1, y: 0, backgroundColor: 'rgba(11,11,15,0)' }}
      transition={{ duration: 0.45, ease: EASE, backgroundColor: { duration: destella ? 1.6 : 0 } }}
    >
      <span className="va-hecho__icono" style={{ background: tonoHecho(h.tipo).suave, color: tonoHecho(h.tipo).color }}><Icono size={14} /></span>
      <span className="va-hecho__texto"><b>{h.titulo}</b><span>{h.detalle}</span></span>
      <span className="va-hecho__hora">{h.hora}</span>
    </motion.div>
  );
}

function Costado({ paso }) {
  const hechos = HECHOS.filter((h) => !h.nuevo || paso >= 5);
  return (
    <div className="va-costado">
      <div className="va-titulo">Lo que hizo hoy <span className="va-vivo"><i /> En vivo</span></div>
      <AnimatePresence initial={false}>
        {hechos.map((h) => <Hecho key={h.titulo} h={h} destella={h.nuevo} />)}
      </AnimatePresence>
      <div className="va-titulo va-titulo--segundo">Lo que hace solo</div>
      {AUTOMATIZACIONES.map((a) => (
        <div key={a.nombre} className="va-auto">
          <span className="va-hecho__texto"><b>{a.nombre}</b><span>{a.cuando}</span></span>
          <i className={`va-interruptor${a.activa ? ' is-activa' : ''}`} />
        </div>
      ))}
    </div>
  );
}

// `compacta`: la versión de teléfono, sin barra lateral y en una columna, con su alto natural.
export function VistaAgente({ activa = true, reducido = false, compacta = false }) {
  const paso = useMomento(activa, reducido);
  return (
    <div className={`va${compacta ? ' va--compacta' : ''}`} style={compacta ? undefined : { width: ANCHO, height: ALTO }}>
      <div className="va__lado"><BarraLateral abierto="Finanzas" secciones={['Caja', 'Por cobrar', 'Por pagar', 'Su cuenta con la empresa']} activa="" /></div>
      <div className="va__cab"><Encabezado modo="Agente" /></div>
      <div className="va__pag"><CabezaPagina modulo="Finanzas" pagina="Agente de Finanzas" /></div>
      <div className="va__cuerpo">
        <Conversacion paso={paso} />
        <Costado paso={paso} />
      </div>
    </div>
  );
}

// Un recorte de "Lo que hizo hoy" para las tarjetas de la landing 2 (sin animación).
export function RecorteLoQueHizoHoy({ cuantos = 3 }) {
  return (
    <div className="va va-recorte">
      <div className="va-titulo">Lo que hizo hoy <span className="va-vivo"><i /> En vivo</span></div>
      {HECHOS.slice(0, cuantos).map((h) => {
        const Icono = h.icono;
        return (
          <div key={h.titulo} className="va-hecho">
            <span className="va-hecho__icono" style={{ background: tonoHecho(h.tipo).suave, color: tonoHecho(h.tipo).color }}><Icono size={14} /></span>
            <span className="va-hecho__texto"><b>{h.titulo}</b><span>{h.detalle}</span></span>
            <span className="va-hecho__hora">{h.hora}</span>
          </div>
        );
      })}
    </div>
  );
}
