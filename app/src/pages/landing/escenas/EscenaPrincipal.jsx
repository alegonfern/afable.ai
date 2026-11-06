import { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion, useInView, useReducedMotion } from 'framer-motion';
import {
  ArrowUp, Calculator, Check, FileText, MessageSquare, PackageOpen, ShoppingCart, Wallet, Zap,
} from 'lucide-react';
import { Cuenta, EASE, Escribiendo, MS_POR_LETRA, pesos } from './comun';
import IsotipoPensando from '../../../components/IsotipoPensando';
import './escenas.css';

/*
 * La animación principal de la landing (23-10-2026): Afable completo, trabajando.
 * Va bajo el hero, donde sintropix.com muestra "el producto trabajando".
 *
 * Cuatro capítulos en bucle, con su barra de avance debajo (se pueden pulsar):
 *   0 · Concilia solo: Afable avisa en el chat que concilió el banco; el pendiente baja a 0.
 *   1 · Factura desde el chat: se pide la factura y queda emitida en el SII.
 *   2 · Responde con sus números: "¿Cuánto me deben y cuánto debo?", con la caja al cierre.
 *   3 · Trabaja en automático: el selector pasa a Automatización y se encienden las suyas.
 *
 * Cada capítulo tiene un guion de pasos con su milisegundo. Lo de capítulos anteriores
 * queda en su estado final; lo de los siguientes no se muestra. Corre solo mientras se ve
 * y, con "reducir movimiento", muestra cada capítulo terminado.
 * Todas las cifras son de una empresa de ejemplo.
 */

// El guion a velocidad 1; RITMO lo acelera entero (25-10-2026: "un poco más rápidas").
const RITMO = 0.8;
const GUION_BASE = [
  {
    titulo: 'Concilia solo',
    dura: 6000,
    pasos: [[1, 300], [2, 1300], [3, 1800], [4, 2300], [5, 2800], [6, 3400]],
  },
  {
    titulo: 'Factura desde el chat',
    dura: 8200,
    pedido: 'Factura a Comercial Andes el plan anual: 12 licencias a $89.000',
    pasos: [[1, 300], [2, 2400], [3, 2700], [4, 3600], [5, 5000], [6, 6200]],
  },
  {
    titulo: 'Responde con sus números',
    pedido: '¿Cuánto me deben y cuánto debo?',
    dura: 9200,
    pasos: [[1, 300], [2, 1300], [3, 1600], [4, 3500], [5, 3900], [6, 5100]],
  },
  {
    titulo: 'Trabaja en automático',
    dura: 6500,
    pasos: [[1, 400], [2, 1000], [3, 1700], [4, 2300], [5, 2900], [6, 3600]],
  },
];
const CAPITULOS = GUION_BASE.map((c) => ({
  ...c, dura: Math.round(c.dura * RITMO), pasos: c.pasos.map(([n, ms]) => [n, Math.round(ms * RITMO)]),
}));
const FINAL = 99;

const MOVIMIENTOS = [
  { banco: 'Abono Stripe', doc: '4 facturas de suscripción', monto: 2340000 },
  { banco: 'Cargo AWS', doc: 'Factura de compra 88213', monto: -1212400 },
  { banco: 'Transferencia Comercial Andes', doc: 'Factura 1043', monto: 1071000 },
  { banco: 'Pago Buk · sueldos', doc: 'Liquidaciones de octubre', monto: -24100000 },
];

const LICENCIAS = 12;
const PRECIO = 89000;
const NETO = LICENCIAS * PRECIO;
const TOTAL = NETO + Math.round(NETO * 0.19);

// Flujo de caja del mes: lo que hay en bancos, lo que le deben y lo que debe.
const CAJA = 42.6;
const POR_COBRAR = 31.4;
const POR_PAGAR = 18.9;
const AL_CIERRE = CAJA + POR_COBRAR - POR_PAGAR;
const PARTIDAS = [
  { nombre: 'Le deben sus clientes', monto: POR_COBRAR },
  { nombre: 'Debe a proveedores', monto: 13.2 },
  { nombre: 'IVA de octubre (F29)', monto: 5.7 },
];
const millones = (n) => `$${n.toLocaleString('es-CL', { minimumFractionDigits: 1, maximumFractionDigits: 1 })} M`;

const AUTOMATIZACIONES = [
  { modulo: 'Contabilidad', nombre: 'Conciliar el banco', cuando: 'Todos los días · 09:00', ultima: 'Hoy 09:00 · 12 movimientos' },
  { modulo: 'Ventas', nombre: 'Facturar al confirmar el pedido', cuando: 'Cada pedido confirmado', ultima: 'Hoy 11:42 · Folio 1044' },
  { modulo: 'Contabilidad', nombre: 'Preparar el F29', cuando: 'El día 10 de cada mes', ultima: 'Próxima: 10 de noviembre' },
];

const aparece = {
  initial: { opacity: 0, y: 14 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0 },
  transition: { duration: 0.45, ease: EASE },
};

// Quién habla en cada capítulo: el agente del módulo (25-10-2026), como en la app.
function Agente({ nombre }) {
  return <div className="esp-agente"><IsotipoPensando size={11} girando={false} color="var(--color)" /> {nombre}</div>;
}

/* ── Capítulo 0: Afable avisa que concilió ── */
function CapConcilia({ p }) {
  if (p < 1) return null;
  return (
    <motion.div className="esc__respuesta" {...aparece}>
      <Agente nombre="Agente de Finanzas" />
      <div className="lp-msg lp-msg--ia">Buenos días. Concilié los movimientos de ayer con sus facturas:</div>
      <div className="esp-conc">
        {MOVIMIENTOS.map((m, i) => {
          const ok = p >= 2 + i;
          const cruzando = !ok && p === 1 + i;
          return (
            <motion.div
              key={m.banco}
              className="esp-conc__fila"
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0, backgroundColor: ok ? ['rgba(215,237,224,0.9)', 'rgba(215,237,224,0)'] : 'rgba(215,237,224,0)' }}
              transition={{ duration: 0.35, ease: EASE, delay: p === 1 ? 0.1 * i : 0, backgroundColor: { duration: 0.9 } }}
            >
              <span className="esp-conc__texto"><b>{m.banco}</b><small>↔ {m.doc}</small></span>
              <span className="esp-conc__monto">{m.monto < 0 ? '−' : ''}{pesos(Math.abs(m.monto))}</span>
              <i className={`lp-estado ${ok ? 'lp-estado--ok' : 'esp-estado--gris'}`}>
                {ok ? <><Check size={10} strokeWidth={3} /> Conciliado</>
                  : cruzando ? <><IsotipoPensando size={10} color="currentColor" /> Cruzando</> : 'Por conciliar'}
              </i>
            </motion.div>
          );
        })}
        <AnimatePresence>
          {p >= 6 && (
            <motion.div className="esp-conc__pie" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              y 8 movimientos más · <b>0 pendientes</b>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}

/* ── Capítulo 1: factura desde el chat ── */
function CapFactura({ p, pedido, sinAnimar }) {
  if (p < 2) return null;
  const estado = p >= 6 ? 'emitida' : p === 5 ? 'enviando' : 'borrador';
  return (
    <>
      <motion.div className="lp-msg lp-msg--yo" {...aparece}>{pedido}</motion.div>
      <AnimatePresence mode="wait">
        {p === 3 && <Escribiendo key="escribiendo" />}
        {p >= 4 && (
          <motion.div key="respuesta" className="esc__respuesta" {...aparece}>
            <Agente nombre="Agente de Ventas" />
            <div className="lp-msg lp-msg--ia">Listo. La emito en el SII:</div>
            <motion.div
              className={`esc-fact esc-fact--${estado}`}
              initial={{ opacity: 0, y: 10, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              transition={{ duration: 0.45, ease: EASE, delay: 0.1 }}
            >
              <div className="esc-fact__cab">
                <span className="esc-fact__tipo"><FileText size={14} /> Factura · Comercial Andes SpA</span>
                <AnimatePresence mode="wait" initial={false}>
                  <motion.i
                    key={estado}
                    className={`lp-estado esc-fact__estado esc-fact__estado--${estado}`}
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -4 }}
                    transition={{ duration: 0.25, ease: EASE }}
                  >
                    {estado === 'borrador' && 'Borrador'}
                    {estado === 'enviando' && <><IsotipoPensando size={11} color="currentColor" /> Enviando al SII</>}
                    {estado === 'emitida' && <><Check size={11} strokeWidth={3} /> Emitida · Folio 1044</>}
                  </motion.i>
                </AnimatePresence>
              </div>
              <div className="esc-fact__lineas">
                <div className="esc-fact__linea">
                  <span>Plan anual</span>
                  <span className="esc-fact__cant">{LICENCIAS} × {pesos(PRECIO)}</span>
                  <b>{pesos(NETO)}</b>
                </div>
              </div>
              <div className="esc-fact__totales">
                <div className="esc-fact__total">
                  <span>Total con IVA</span>
                  <b><Cuenta valor={TOTAL} desdeCero retraso={0.4} sinAnimar={sinAnimar} /></b>
                </div>
              </div>
              <div className="esc-fact__sii">
                <motion.span
                  initial={{ width: '0%' }}
                  animate={{ width: p >= 6 ? '100%' : p === 5 ? '85%' : '0%' }}
                  transition={{ duration: p === 5 ? 1.2 : 0.3, ease: p === 5 ? 'linear' : EASE }}
                />
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

/* ── Capítulo 2: cuánto le deben y cuánto debe ── */
function CapCaja({ p, pedido }) {
  if (p < 2) return null;
  const mayor = PARTIDAS[0].monto;
  return (
    <>
      <motion.div className="lp-msg lp-msg--yo" {...aparece}>{pedido}</motion.div>
      <AnimatePresence mode="wait">
        {p === 3 && <PasosEscena key="pasos" pasos={['Revisando los bancos', 'Revisando quién le debe', 'Revisando lo que debe pagar']} />}
        {p >= 4 && (
          <motion.div key="respuesta" className="lp-msg lp-msg--ia esp-runway" {...aparece}>
            <p>
              Le deben <b>{millones(POR_COBRAR)}</b> y usted debe <b>{millones(POR_PAGAR)}</b>. Con
              lo que tiene en bancos, cierra el mes con <b className="esp-resalta">{millones(AL_CIERRE)}</b>:
            </p>
            {PARTIDAS.map((x, i) => (
              <div key={x.nombre} className="esp-runway__fila">
                <div><span>{x.nombre}</span><span>{millones(x.monto)}</span></div>
                <div className="esp-runway__barra">
                  <motion.span
                    initial={{ width: 0 }}
                    animate={{ width: p >= 5 ? `${(x.monto / mayor) * 100}%` : 0 }}
                    transition={{ duration: 0.7, ease: EASE, delay: 0.14 * i }}
                  />
                </div>
              </div>
            ))}
            <AnimatePresence>
              {p >= 6 && (
                <motion.div className="esp-runway__fuentes" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                  Fuentes: Banco · Libro de ventas · Libro de compras
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

/* La tarjeta de pasos del chat de la app (PasosDelChat): cada paso con el signo girando mientras
   corre y su ✓ al terminar. */
function PasosEscena({ pasos }) {
  const [hechos, setHechos] = useState(0);
  useEffect(() => {
    const relojes = pasos.slice(0, -1).map((_, i) => setTimeout(() => setHechos(i + 1), 450 * (i + 1)));
    return () => relojes.forEach(clearTimeout);
  }, [pasos]);
  return (
    <motion.div className="esc-pasos" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
      transition={{ duration: 0.3, ease: EASE }}>
      <div className="esc-pasos__cab"><IsotipoPensando size={13} color="var(--color)" /> <b>Agente de Finanzas</b> trabajando…</div>
      {pasos.slice(0, hechos + 1).map((paso, i) => (
        <motion.div key={paso} className="esc-pasos__paso" initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.25, ease: EASE }}>
          {i < hechos ? <Check size={11} strokeWidth={3} className="esc-pasos__ok" /> : <IsotipoPensando size={11} color="var(--color)" />}
          <span>{i + 1}. {paso}{i < hechos ? '' : '…'}</span>
        </motion.div>
      ))}
    </motion.div>
  );
}

/* ── Capítulo 3: las automatizaciones del módulo ── */
function Automatizaciones({ p }) {
  return (
    <div className="esp-auto">
      <div className="esp-auto__titulo">Automatizaciones activas</div>
      {AUTOMATIZACIONES.map((a, i) => {
        const activa = p >= 3 + i;
        return (
          <motion.div
            key={a.nombre}
            className="esp-auto__fila"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, ease: EASE, delay: 0.1 * i }}
          >
            <span className="esp-auto__icono">{a.modulo === 'Ventas' ? <ShoppingCart size={14} /> : <Calculator size={14} />}</span>
            <span className="esp-auto__texto">
              <b>{a.nombre}</b>
              <small>{a.modulo} · {a.cuando}</small>
              <AnimatePresence mode="wait">
                {p >= 6 ? (
                  <motion.small key="ultima" className="esp-auto__ultima" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                    <Check size={10} strokeWidth={3} /> {a.ultima}
                  </motion.small>
                ) : activa ? (
                  <motion.small key="corriendo" className="esp-auto__ultima esp-auto__corriendo" initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                    <IsotipoPensando size={10} color="var(--color)" /> Corriendo…
                  </motion.small>
                ) : null}
              </AnimatePresence>
            </span>
            <span className={`esp-interruptor${activa ? ' is-on' : ''}`}><motion.i layout transition={{ duration: 0.3, ease: EASE }} /></span>
          </motion.div>
        );
      })}
    </div>
  );
}

// El módulo donde quedó registrado lo último se ilumina un momento.
function Destello() {
  return (
    <motion.i
      className="esp-destello"
      initial={{ opacity: 1 }}
      animate={{ opacity: 0 }}
      transition={{ duration: 1.4, ease: 'easeOut' }}
    />
  );
}

export default function EscenaPrincipal() {
  const ref = useRef(null);
  const visible = useInView(ref, { amount: 0.35 });
  const reducido = useReducedMotion();
  const [cap, setCap] = useState(0);
  const [paso, setPaso] = useState(0);
  const [letras, setLetras] = useState(0);
  const [corrida, setCorrida] = useState(0);

  useEffect(() => {
    if (reducido) { setPaso(FINAL); return undefined; }
    if (!visible) return undefined;
    setPaso(0);
    setLetras(0);
    const c = CAPITULOS[cap];
    let tecleo;
    const timers = c.pasos.map(([p, ms]) => setTimeout(() => setPaso(p), ms));
    if (c.pedido) {
      timers.push(setTimeout(() => {
        tecleo = setInterval(() => {
          setLetras((n) => {
            if (n + 1 >= c.pedido.length) clearInterval(tecleo);
            return n + 1;
          });
        }, MS_POR_LETRA);
      }, c.pasos[0][1]));
    }
    timers.push(setTimeout(() => {
      setCap((x) => (x + 1) % CAPITULOS.length);
      setCorrida((n) => n + 1);
    }, c.dura));
    return () => { timers.forEach(clearTimeout); clearInterval(tecleo); };
  }, [cap, corrida, visible, reducido]);

  const ir = (i) => { setCap(i); setCorrida((n) => n + 1); };

  // Cómo va cada capítulo: terminado si ya pasó, en curso, o sin empezar.
  const pasoDe = (i) => (i < cap ? FINAL : i === cap ? paso : -1);
  const hecho = (i, p) => pasoDe(i) >= p;

  const pedido = CAPITULOS[cap].pedido;
  const tecleando = Boolean(pedido) && paso === 1 && letras > 0;
  const modoAuto = hecho(3, 1);
  const vistaAuto = hecho(3, 2);

  const porConciliar = hecho(0, 5) ? 0 : hecho(0, 2) ? 12 - 3 * (pasoDe(0) - 1) : 12;
  const porEmitir = hecho(1, 6) ? 2 : 3;
  const cierre = hecho(2, 4);

  return (
    <div className="esp" ref={ref}>
      <div
        className="lp-app esp__ventana"
        role="img"
        aria-label="Animación de Afable: concilia el banco solo, emite una factura pedida en el chat, responde cuánto le deben y cuánto debe, y muestra sus automatizaciones activas."
      >
        <div className="lp-app__barra">
          <span /><span /><span />
          <em>Empresa de ejemplo · hoy, 09:00</em>
          <i className="esc__vivo"><b />En línea</i>
        </div>
        <div className="lp-app__cuerpo esp__cuerpo">
          <aside className="lp-app__lado">
            <div className="esp-switch">
              {['Módulo', 'Automatización'].map((m) => {
                const activo = (m === 'Automatización') === modoAuto;
                return (
                  <span key={m} className={activo ? 'is-activo' : ''}>
                    {activo && <motion.i layoutId="esp-switch" className="esp-switch__pastilla" transition={{ duration: 0.4, ease: EASE }} />}
                    <em>{m === 'Automatización' && <Zap size={11} />}{m}</em>
                  </span>
                );
              })}
            </div>
            <div className={`lp-app__item${!modoAuto ? ' is-activo' : ''}`}><MessageSquare size={14} /> Chat</div>
            <div className="lp-app__seccion">Módulos</div>
            <div className="lp-app__item esp-item">
              {hecho(1, 6) && cap === 1 && <Destello />}
              <ShoppingCart size={14} /> Ventas
            </div>
            {/* Los cuatro módulos de la app real (Compras y Finanzas se sumaron el 25-10-2026). */}
            <div className="lp-app__item esp-item"><PackageOpen size={14} /> Compras</div>
            <div className={`lp-app__item esp-item${modoAuto ? ' is-activo' : ''}`}>
              {hecho(0, 5) && cap === 0 && <Destello />}
              <Calculator size={14} /> Contabilidad
            </div>
            <div className="lp-app__item esp-item">
              {hecho(2, 4) && cap === 2 && <Destello />}
              <Wallet size={14} /> Finanzas
            </div>
          </aside>

          <div className="esp__centro">
            <AnimatePresence mode="wait" initial={false}>
              {vistaAuto ? (
                <motion.div key="auto" className="esp__vista" initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.4, ease: EASE }}>
                  <Automatizaciones p={pasoDe(3)} />
                </motion.div>
              ) : (
                <motion.div key="chat" className="esp__vista esp__hilo" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.3 }}>
                  <AnimatePresence>
                    <CapConcilia key="c0" p={pasoDe(0)} />
                  </AnimatePresence>
                  <CapFactura p={pasoDe(1)} pedido={CAPITULOS[1].pedido} sinAnimar={reducido} />
                  <CapCaja p={pasoDe(2)} pedido={CAPITULOS[2].pedido} />
                </motion.div>
              )}
            </AnimatePresence>
            {!vistaAuto && (
              <div className="esc__entrada esp__entrada">
                <span className={tecleando ? 'esc__texto' : 'esc__texto is-vacio'}>
                  {tecleando ? pedido.slice(0, letras) : 'Pídale algo a Afable…'}
                  {tecleando && <i className="esc__cursor" />}
                </span>
                <span className={`esc__enviar${tecleando ? ' is-listo' : ''}`}><ArrowUp size={14} /></span>
              </div>
            )}
          </div>

          <div className="lp-app__panel">
            <div className="lp-panel__titulo">Necesita acción</div>
            <div className="lp-panel__fila">
              <span>Movimientos por conciliar</span>
              <b className={porConciliar === 0 ? 'esp-ok' : ''}>
                {porConciliar === 0 ? <><Check size={12} strokeWidth={3} /> 0</> : <Cuenta valor={porConciliar} sinAnimar={reducido} formato={Math.round} />}
              </b>
            </div>
            <div className="lp-panel__fila"><span>Facturas por emitir</span><b><Cuenta valor={porEmitir} sinAnimar={reducido} formato={Math.round} /></b></div>
            <div className="lp-panel__fila"><span>Compras por confirmar</span><b>2</b></div>

            <div className="lp-panel__titulo lp-panel__titulo--sep">Caja</div>
            <div className="lp-panel__fila"><span>Saldo en bancos</span><b>{millones(CAJA)}</b></div>
            <div className="lp-panel__fila"><span>Por cobrar</span><b>{millones(POR_COBRAR)}</b></div>
            <div className="lp-panel__fila"><span>Por pagar</span><b>{millones(POR_PAGAR)}</b></div>
            <div className="esp-runway-kpi">
              <span>Al cierre del mes</span>
              <b>{cierre ? <Cuenta valor={AL_CIERRE} desdeCero sinAnimar={reducido} formato={millones} /> : '—'}</b>
            </div>
          </div>
        </div>
      </div>

      {/* Los capítulos, con su avance. Pulsar uno lo reproduce desde el inicio. */}
      <div className="esp-caps">
        {CAPITULOS.map((c, i) => (
          <button key={c.titulo} type="button" className={i === cap ? 'is-activo' : ''} onClick={() => ir(i)}>
            <span className="esp-caps__barra">
              <motion.span
                key={`${i}-${corrida}`}
                initial={{ width: i < cap ? '100%' : '0%' }}
                animate={{ width: i < cap || (i === cap && (visible || reducido)) ? '100%' : '0%' }}
                transition={{ duration: i === cap && !reducido ? c.dura / 1000 : 0, ease: 'linear' }}
              />
            </span>
            {c.titulo}
          </button>
        ))}
      </div>
    </div>
  );
}
