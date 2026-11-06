import { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion, useInView, useReducedMotion } from 'framer-motion';
import { ArrowUp, Check, FileText, LoaderCircle, Receipt } from 'lucide-react';
import { Cuenta, EASE, Escribiendo, MS_POR_LETRA, pesos } from './comun';
import './escenas.css';

/*
 * Escena 1 de la landing: facturar desde el chat (23-10-2026).
 *
 * Como las de sintropix.com: no es un video ni un componente de la app, es una maqueta
 * que cuenta la historia en unos segundos. Se reproduce al entrar en pantalla, se repite
 * mientras se ve y, con "reducir movimiento" activado, muestra directo el final.
 *
 * Guion: se escribe el pedido → se envía → Afable escribe → arma la factura (líneas y
 * total que sube) → la envía al SII → emitida con folio → queda registrada en Ventas.
 */

const PEDIDO = 'Factura a Comercial Andes 12 sillas a $45.000 y 2 escritorios a $180.000';
const LINEAS = [
  { detalle: 'Silla ergonómica', cantidad: 12, precio: 45000 },
  { detalle: 'Escritorio 140 cm', cantidad: 2, precio: 180000 },
];
const NETO = LINEAS.reduce((s, l) => s + l.cantidad * l.precio, 0);
const IVA = Math.round(NETO * 0.19);
const TOTAL = NETO + IVA;

// Fases: 1 escribe · 2 enviado · 3 Afable escribe · 4 factura · 5 al SII · 6 emitida · 7 en Ventas
const INICIO_TECLEO = 300;
const FIN_TECLEO = INICIO_TECLEO + PEDIDO.length * MS_POR_LETRA;
// Acelerado al 80% (25-10-2026), igual que EscenaPrincipal.
const RITMO = 0.8;
const GUION_BASE = [
  [1, INICIO_TECLEO],
  [2, FIN_TECLEO + 300],
  [3, FIN_TECLEO + 600],
  [4, FIN_TECLEO + 1700],
  [5, FIN_TECLEO + 3700],
  [6, FIN_TECLEO + 5200],
  [7, FIN_TECLEO + 5800],
];
const FINAL = 7;
const GUION = GUION_BASE.map(([n, ms]) => [n, Math.round(ms * RITMO)]);
const REINICIO = Math.round((FIN_TECLEO + 10000) * RITMO);

function Factura({ fase, sinAnimar }) {
  const estado = fase >= 6 ? 'emitida' : fase === 5 ? 'enviando' : 'borrador';
  return (
    <motion.div
      className={`esc-fact esc-fact--${estado}`}
      initial={{ opacity: 0, y: 14, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.5, ease: EASE, delay: 0.15 }}
    >
      <div className="esc-fact__cab">
        <span className="esc-fact__tipo"><FileText size={14} /> Factura electrónica</span>
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
            {estado === 'enviando' && <><LoaderCircle size={11} className="esc-gira" /> Enviando al SII</>}
            {estado === 'emitida' && <><Check size={11} strokeWidth={3} /> Emitida · Folio 1044</>}
          </motion.i>
        </AnimatePresence>
      </div>

      <div className="esc-fact__cliente">
        <b>Comercial Andes SpA</b>
        <span>RUT 76.123.456-7 · Pago a 30 días</span>
      </div>

      <div className="esc-fact__lineas">
        {LINEAS.map((l, i) => (
          <motion.div
            key={l.detalle}
            className="esc-fact__linea"
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.35, ease: EASE, delay: 0.45 + 0.18 * i }}
          >
            <span>{l.detalle}</span>
            <span className="esc-fact__cant">{l.cantidad} × {pesos(l.precio)}</span>
            <b>{pesos(l.cantidad * l.precio)}</b>
          </motion.div>
        ))}
      </div>

      <motion.div
        className="esc-fact__totales"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.3, delay: 0.85 }}
      >
        <div><span>Neto</span><span>{pesos(NETO)}</span></div>
        <div><span>IVA 19%</span><span>{pesos(IVA)}</span></div>
        <div className="esc-fact__total">
          <span>Total</span>
          <b><Cuenta valor={TOTAL} desdeCero retraso={0.9} sinAnimar={sinAnimar} /></b>
        </div>
      </motion.div>

      {/* El envío al SII: la barra avanza mientras se envía y se completa al emitir. */}
      <div className="esc-fact__sii">
        <motion.span
          initial={{ width: '0%' }}
          animate={{ width: fase >= 6 ? '100%' : fase === 5 ? '85%' : '0%' }}
          transition={{ duration: fase === 5 ? 1.5 : 0.3, ease: fase === 5 ? 'linear' : EASE }}
        />
      </div>
    </motion.div>
  );
}

export default function EscenaFacturar() {
  const ref = useRef(null);
  const visible = useInView(ref, { amount: 0.4 });
  const reducido = useReducedMotion();
  const [fase, setFase] = useState(0);
  const [letras, setLetras] = useState(0);
  const [vuelta, setVuelta] = useState(0);

  useEffect(() => {
    if (reducido) { setFase(FINAL); setLetras(PEDIDO.length); return undefined; }
    if (!visible) return undefined;
    setFase(0);
    setLetras(0);
    let tecleo;
    const timers = GUION.map(([f, ms]) => setTimeout(() => setFase(f), ms));
    timers.push(setTimeout(() => {
      tecleo = setInterval(() => {
        setLetras((n) => {
          if (n + 1 >= PEDIDO.length) clearInterval(tecleo);
          return n + 1;
        });
      }, MS_POR_LETRA);
    }, INICIO_TECLEO));
    timers.push(setTimeout(() => setVuelta((v) => v + 1), REINICIO));
    return () => { timers.forEach(clearTimeout); clearInterval(tecleo); };
  }, [visible, reducido, vuelta]);

  const tecleando = fase === 1 && letras > 0;

  return (
    <div
      ref={ref}
      className="esc"
      role="img"
      aria-label="Animación: se le pide a Afable en el chat que facture; arma la factura, la emite en el SII y queda registrada en Ventas."
    >
      <div className="esc__barra">
        <span /><span /><span />
        <em>Chat · Empresa de ejemplo</em>
        <i className="esc__vivo"><b />En línea</i>
      </div>

      <div className="esc__chat">
        <AnimatePresence>
          {fase >= 2 && (
            <motion.div
              key={`yo-${vuelta}`}
              className="lp-msg lp-msg--yo"
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.45, ease: EASE }}
            >
              {PEDIDO}
            </motion.div>
          )}
        </AnimatePresence>

        <AnimatePresence mode="wait">
          {fase === 3 && (
            <Escribiendo key="escribiendo" />
          )}
          {fase >= 4 && (
            <motion.div
              key={`respuesta-${vuelta}`}
              className="esc__respuesta"
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.45, ease: EASE }}
            >
              <div className="lp-msg lp-msg--ia">Listo. Armé la factura y la emito en el SII:</div>
              <Factura fase={fase} sinAnimar={reducido} />
              <AnimatePresence>
                {fase >= 7 && (
                  <motion.div
                    className="esc__registro"
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.4, ease: EASE }}
                  >
                    <Receipt size={13} /> Registrada en Ventas · Libro de ventas de octubre
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <div className="esc__entrada">
        <span className={tecleando ? 'esc__texto' : 'esc__texto is-vacio'}>
          {tecleando ? PEDIDO.slice(0, letras) : 'Pídale algo a Afable…'}
          {tecleando && <i className="esc__cursor" />}
        </span>
        <span className={`esc__enviar${tecleando ? ' is-listo' : ''}`}><ArrowUp size={14} /></span>
      </div>
    </div>
  );
}
