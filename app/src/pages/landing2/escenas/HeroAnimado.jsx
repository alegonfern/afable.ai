import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { AnimatePresence, motion, useInView, useReducedMotion, useScroll, useSpring, useTransform } from 'framer-motion';
import {
  ArrowRight, ArrowUp, Bell, Boxes, Calculator, ChevronDown, ChevronLeft, ChevronRight, MessageSquare,
  PackageOpen, PanelLeft, Plus, ShoppingCart, SlidersHorizontal, Sun, Wallet,
} from 'lucide-react';
import LogoNegro from './LogoNegro';
import { EASE, Escribiendo } from './comun';
import './escenas.css';

/*
 * El hero animado por scroll (23-10-2026), con la lógica del hero de sintropix.com: la
 * sección mide 2,4 pantallas, la vista queda fija y el scroll mueve la animación. Las
 * piezas empiezan desparramadas alrededor del titular y, al bajar, vuelan a su lugar y
 * arman una pantalla del producto. El 27-10-2026 se volvió a esta versión (la de la pregunta
 * que viaja al chat no gustó), con dos cambios: las piezas llegan en curva (no en línea
 * recta) y el avance va suavizado con un resorte.
 *
 * La pantalla es la de Afable tal como es: barra lateral con los módulos, barra de arriba
 * con el selector Módulo / Automatización, migas Inicio / Contabilidad / Resumen,
 * Contabilidad › Resumen (`pages/modulos/Numeros.jsx`, ResumenVista) y el chat lateral
 * abierto (`layout/Dashboard/ChatLateral.jsx`) respondiendo una de sus sugerencias.
 *
 *   0–11 %   el titular y el chat del hero suben y se desvanecen
 *   13–40 %  aparece y se va "Todo su ERP, desde un chat."
 *   30–54 %  aparece la ventana: barra lateral, encabezado y la tarjeta del mes
 *   30–72 %  Ganancia, Ingresos, Gastos, el F29 y la respuesta del chat vuelan a su lugar
 *   58–80 %  aparecen las demás filas del Resumen y la pregunta del chat
 *
 * Bajo 1024 px se muestra el titular y debajo la misma pantalla en vertical, que se arma
 * sola al aparecer (25-10-2026): el lienzo de 1180 px no se lee achicado a un teléfono, y
 * una vista pegada al scroll es incómoda en el celular. Con "reducir movimiento" se muestra
 * ya armada. Todas las cifras son de una empresa de ejemplo.
 */

export const ANCHO = 1180;
export const ALTO = 700;

// Fracción del avance dentro de un tramo [a, b], entre 0 y 1.
const tramo = (a, b) => (v) => Math.min(1, Math.max(0, (v - a) / (b - a)));

/* ── Las piezas, copiadas de las pantallas de Afable ── */

const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];

// Barras de los 12 meses, como `Barras` de Numeros.jsx: el elegido en índigo.
function Barras({ valores, elegido }) {
  const max = Math.max(...valores.filter((v) => v != null));
  return (
    <div className="hx-barras">
      <div className="hx-barras__fila">
        {valores.map((v, i) => (
          <span
            key={i}
            className={i === elegido ? 'is-elegido' : v == null ? 'is-vacio' : ''}
            style={{ height: v == null ? 4 : `${Math.max(6, (v / max) * 100)}%` }}
          />
        ))}
      </div>
      <div className="hx-barras__eje"><span>ene</span><span>dic</span></div>
    </div>
  );
}

const OCT = 9;
const SERIES = {
  ganancia: [1.2, 1.6, 2.1, 1.9, 2.4, 2.2, 2.9, 3.1, 3.7, 4.18, null, null],
  ingresos: [9.8, 10.4, 11.2, 11.0, 12.6, 12.9, 14.1, 15.0, 16.4, 18.42, null, null],
  gastos: [8.6, 8.8, 9.1, 9.1, 10.2, 10.7, 11.2, 11.9, 12.7, 14.24, null, null],
};

function Cifra({ titulo, valor, cambio, serie, grande }) {
  return (
    <div className={`hx-cifra${grande ? ' hx-cifra--grande' : ''}`}>
      <span className="hx-etiqueta">{titulo}</span>
      <span className="hx-cifra__valor">{valor}</span>
      <span className="hx-chip">{cambio} vs {MESES[OCT - 1]}</span>
      <Barras valores={serie} elegido={OCT} />
    </div>
  );
}
const GANANCIA = <Cifra titulo="Ganancia" valor="+$4.180.000" cambio="▲ 13%" serie={SERIES.ganancia} grande />;
const INGRESOS = <Cifra titulo="Ingresos" valor="$18.420.000" cambio="▲ 12%" serie={SERIES.ingresos} />;
const GASTOS = <Cifra titulo="Gastos" valor="$14.240.000" cambio="▲ 12%" serie={SERIES.gastos} />;

function FilaResumen({ titulo, valor, color, children }) {
  return (
    <div className="hx-fila">
      <span className="hx-etiqueta">{titulo}</span>
      <b style={color ? { color } : undefined}>{valor}</b>
      <span>{children}</span>
    </div>
  );
}
const MARGEN = <FilaResumen titulo="Margen neto" valor="+22,7%">de cada $100 que vendió (sin IVA), quedan $23.</FilaResumen>;
const RESULTADO = <FilaResumen titulo="Resultado de 2026" valor="+$25.280.000">ganancia acumulada del año, sin IVA.</FilaResumen>;
const F29 = (
  <FilaResumen titulo="F29 de oct · a pagar" valor="$1.284.300" color="var(--color)">
    Vence el 20 de noviembre de 2026. No es suya, es del SII: apártela hoy.{' '}
    <em>Ver el desglose <ArrowRight size={12} /></em>
  </FilaResumen>
);

const PREGUNTA = <div className="hx-lat__yo">¿Cuánto IVA tengo que pagar este mes?</div>;
const RESPUESTA = (
  <div className="hx-lat__ia">
    El F29 de octubre queda en <b>$1.284.300</b> a pagar: <b>$1.071.800</b> de IVA y{' '}
    <b>$212.500</b> de PPM. Vence el 20 de noviembre.
  </div>
);

// La barra lateral tal como está en la app: logo, Chat, Módulos con su flecha, el submenú
// del módulo abierto y la cuenta abajo. Sin Buscar (apagado con MOSTRAR_BUSCADOR en
// Drawer/index.jsx).
export function BarraLateral({ abierto: elAbierto = 'Contabilidad', secciones = ['Resumen', 'Documentos', 'Impuestos', 'Conciliación', 'Categorías', 'Proyectos'], activa = 'Resumen' }) {
  const modulos = [
    ['Ventas', ShoppingCart], ['Compras', PackageOpen], ['Inventario', Boxes], ['Contabilidad', Calculator], ['Finanzas', Wallet],
  ];
  return (
    <div className="hx-lado">
      <div className="hx-lado__logo"><LogoNegro size={20} /><ChevronLeft size={14} /></div>
      <div className="hx-lado__item"><MessageSquare size={15} /> <span>Chat</span></div>
      <div className="hx-lado__titulo">Módulos</div>
      {modulos.map(([nombre, Icono]) => {
        const abierto = nombre === elAbierto;
        return (
          <div key={nombre}>
            <div className={`hx-lado__item${abierto ? ' is-activo' : ''}`}>
              <Icono size={15} /> <span>{nombre}</span>
              {abierto ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
            </div>
            {abierto && (
              <div className="hx-lado__sub">
                {secciones.map((x) => <span key={x} className={x === activa ? 'is-activo' : ''}>{x}</span>)}
              </div>
            )}
          </div>
        );
      })}
      <div className="hx-lado__cuenta"><i>C</i> Cuenta de ejemplo</div>
    </div>
  );
}

// La barra de arriba: el menú a la izquierda, el selector al centro y, a la derecha, la campana,
// el modo claro/oscuro, la configuración del módulo y el chat (encendido: el panel está abierto).
export function Encabezado({ modo = 'Módulo' }) {
  return (
    <div className="hx-cab">
      <span className="hx-cab__iconos"><PanelLeft size={15} /></span>
      <span className="hx-cab__selector">{['Módulo', 'Agente'].map((x) => (x === modo ? <b key={x}>{x}</b> : <span key={x}>{x}</span>))}</span>
      <span className="hx-cab__iconos hx-cab__iconos--der"><Bell size={15} /><Sun size={15} /><SlidersHorizontal size={15} /><i><MessageSquare size={15} /></i></span>
    </div>
  );
}

// El encabezado de la página (PageHeader): volver y las migas.
export function CabezaPagina({ modulo = 'Contabilidad', pagina = 'Resumen' }) {
  return (
    <div className="hx-pag">
      <span className="hx-pag__volver"><ChevronLeft size={14} /></span>
      <span className="hx-pag__migas">Inicio <i>/</i> {modulo} <i>/</i> <b>{pagina}</b></span>
    </div>
  );
}

function Meses() {
  return (
    <div className="hx-meses">
      <span>Agosto</span><span>Septiembre</span><span className="is-activo">Octubre</span>
    </div>
  );
}

function CabezaTarjeta() {
  return (
    <div className="hx-tarjeta__cab">
      <b>Octubre 2026</b>
      <span>Sin IVA y antes del impuesto a la renta</span>
    </div>
  );
}

function EntradaLateral() {
  return <div className="hx-lat__entrada">Pregúntele a Afable…<i><ArrowUp size={13} /></i></div>;
}

/* ── El lienzo: coordenadas de cada pieza en la pantalla armada ── */

const LADO = 205;
const CAB = 46;
const PAG = 50;
const LAT_X = 875;
const MAIN_X = 225;
const MAIN_W = 630;
const MESES_Y = CAB + PAG + 14;
const TARJ_Y = MESES_Y + 40;
const CIFRAS_Y = TARJ_Y + 46;
const CIFRAS_H = 190;
const COL = [MAIN_X, MAIN_X + 258, MAIN_X + 258 + 186];
const ANCHOS = [258, 186, 186];
const FILAS_Y = CIFRAS_Y + CIFRAS_H + 8;
const FILA_H = 54;

// Las piezas que empiezan desparramadas: dónde terminan y desde dónde llegan.
const VUELAN = [
  { el: GANANCIA, x: COL[0], y: CIFRAS_Y, w: ANCHOS[0], h: CIFRAS_H, desde: { x: -60, y: 40, rot: -6, scale: 0.9 }, r: [0.3, 0.66] },
  { el: INGRESOS, x: COL[1], y: CIFRAS_Y, w: ANCHOS[1], h: CIFRAS_H, desde: { x: 940, y: 30, rot: 5, scale: 0.95 }, r: [0.32, 0.68] },
  { el: GASTOS, x: COL[2], y: CIFRAS_Y, w: ANCHOS[2], h: CIFRAS_H, desde: { x: 980, y: 330, rot: 7, scale: 0.95 }, r: [0.34, 0.7] },
  { el: F29, x: MAIN_X, y: FILAS_Y + 2 * FILA_H, w: MAIN_W, h: FILA_H, desde: { x: -200, y: 600, rot: -4, scale: 0.62 }, r: [0.33, 0.69] },
  { el: RESPUESTA, x: LAT_X + 16, y: 150, w: 268, h: 120, desde: { x: 940, y: 560, rot: 4, scale: 0.95 }, r: [0.36, 0.72] },
  { el: <Meses />, x: MAIN_X, y: MESES_Y, w: 300, h: 30, desde: { x: -10, y: 330, rot: -7, scale: 1 }, r: [0.35, 0.71] },
];

// Una pieza desparramada que vuelve a su lugar. Mientras vuela es una tarjeta suelta; al
// llegar, su marco se apaga y queda como parte de la pantalla.
// El horizontal se resuelve antes que el vertical: la pieza llega en curva, no en línea recta.
const salida = (t) => 1 - (1 - t) ** 2;
const entrada = (t) => t ** 1.6;

function Desparramada({ avance, x, y, w, h, desde, r, children }) {
  const t = tramo(r[0], r[1]);
  const dx = useTransform(avance, (v) => (desde.x - x) * (1 - salida(t(v))));
  const dy = useTransform(avance, (v) => (desde.y - y) * (1 - entrada(t(v))));
  const rot = useTransform(avance, r, [desde.rot, 0]);
  const esc = useTransform(avance, r, [desde.scale, 1]);
  const marco = useTransform(avance, (v) => 1 - tramo(r[1] - 0.04, r[1])(v));
  return (
    <motion.div className="hx-pieza" style={{ left: x, top: y, width: w, height: h, x: dx, y: dy, rotate: rot, scale: esc }}>
      <motion.i className="hx-marco" style={{ opacity: marco }} />
      <div className="hx-pieza__contenido">{children}</div>
    </motion.div>
  );
}

// Una pieza que aparece subiendo.
function Aparece({ avance, r, desdeY = 0, className, style, children }) {
  const opacidad = useTransform(avance, tramo(r[0], r[1]));
  const y = useTransform(avance, r, [desdeY, 0]);
  return <motion.div className={className} style={{ ...style, opacity: opacidad, y }}>{children}</motion.div>;
}

export function Lienzo({ avance }) {
  const opacidad = useTransform(avance, tramo(0.3, 0.54));
  const escala = useTransform(avance, [0.28, 0.6], [0.965, 1]);
  return (
    <div className="hx-lienzo" style={{ width: ANCHO, height: ALTO }}>
      <motion.div className="hx-ventana" style={{ opacity: opacidad, scale: escala }}>
        <div className="hx-ventana__lado" style={{ width: LADO }}><BarraLateral /></div>
        <div className="hx-ventana__cab" style={{ left: LADO, height: CAB }}><Encabezado /></div>
        <div className="hx-ventana__pag" style={{ left: LADO, top: CAB, width: LAT_X - LADO, height: PAG }}><CabezaPagina /></div>
        <div className="hx-ventana__lat" style={{ left: LAT_X, top: CAB }}>
          <div className="hx-lat__nueva"><Plus size={13} /> Nueva conversación</div>
          <EntradaLateral />
        </div>
        {/* La tarjeta del mes: se arma alrededor de las cifras que llegan volando. */}
        <div className="hx-tarjeta" style={{ left: MAIN_X, top: TARJ_Y, width: MAIN_W, height: FILAS_Y + 3 * FILA_H + 8 - TARJ_Y }}>
          <CabezaTarjeta />
        </div>
        <i className="hx-divisor" style={{ left: COL[1], top: CIFRAS_Y, height: CIFRAS_H }} />
        <i className="hx-divisor" style={{ left: COL[2], top: CIFRAS_Y, height: CIFRAS_H }} />
        <i className="hx-divisor hx-divisor--h" style={{ left: MAIN_X, top: FILAS_Y - 4, width: MAIN_W }} />
      </motion.div>

      <Aparece avance={avance} r={[0.58, 0.68]} desdeY={10} className="hx-pieza" style={{ left: MAIN_X, top: FILAS_Y, width: MAIN_W, height: FILA_H }}>{MARGEN}</Aparece>
      <Aparece avance={avance} r={[0.62, 0.72]} desdeY={10} className="hx-pieza" style={{ left: MAIN_X, top: FILAS_Y + FILA_H, width: MAIN_W, height: FILA_H }}>{RESULTADO}</Aparece>
      <Aparece avance={avance} r={[0.6, 0.7]} desdeY={10} className="hx-pieza hx-derecha" style={{ left: LAT_X + 16, top: 92, width: 268 }}>{PREGUNTA}</Aparece>

      {VUELAN.map((p, i) => <Desparramada key={i} avance={avance} {...p}>{p.el}</Desparramada>)}
    </div>
  );
}

// En el celular las piezas entran en orden al aparecer la pantalla: el mes, las tres cifras
// (con sus barras creciendo), las filas del Resumen y, en el chat, la pregunta, los puntos
// de "escribiendo" y la respuesta. Cada número es el paso desde el que se ve la pieza.
const PASOS_MOVIL = [500, 900, 1250, 1600, 2100, 2400, 2700, 3300, 3900, 5000];

function usePasoMovil(ref, animada) {
  const visible = useInView(ref, { once: true, amount: 0.3 });
  const [paso, setPaso] = useState(animada ? 0 : PASOS_MOVIL.length);
  useEffect(() => {
    if (!animada || !visible) return undefined;
    const relojes = PASOS_MOVIL.map((ms, i) => setTimeout(() => setPaso(i + 1), ms));
    return () => relojes.forEach(clearTimeout);
  }, [animada, visible]);
  return paso;
}

// Una pieza que sube y aparece desde su paso. Ocupa su lugar desde el principio, para que
// la pantalla no salte mientras se arma.
function Entra({ paso, desde, className, children }) {
  const ya = paso >= desde;
  return (
    <motion.div
      className={`${className || ''}${ya ? ' is-dentro' : ''}`}
      initial={false}
      animate={{ opacity: ya ? 1 : 0, y: ya ? 0 : 14 }}
      transition={{ duration: 0.5, ease: EASE }}
    >
      {children}
    </motion.div>
  );
}

// La pantalla en vertical: armada (con "reducir movimiento") o armándose (en el celular).
export function PantallaFija({ animada = false }) {
  const ref = useRef(null);
  const paso = usePasoMovil(ref, animada);
  return (
    <div ref={ref} className={`hx-fijo${animada ? ' hx-fijo--animada' : ''}`} role="img" aria-label="Afable: Contabilidad › Resumen de octubre, con la ganancia, los ingresos, los gastos y el F29, y el chat lateral respondiendo cuánto IVA hay que pagar.">
      <Encabezado />
      <CabezaPagina />
      <div className="hx-fijo__cuerpo">
        <Entra paso={paso} desde={1} className="hx-fijo__meses"><Meses /></Entra>
        <Entra paso={paso} desde={1} className="hx-tarjeta hx-tarjeta--fija">
          <CabezaTarjeta />
          <div className="hx-fijo__cifras">
            <Entra paso={paso} desde={2}>{GANANCIA}</Entra>
            <Entra paso={paso} desde={3}>{INGRESOS}</Entra>
            <Entra paso={paso} desde={4}>{GASTOS}</Entra>
          </div>
          <div className="hx-fijo__filas">
            <Entra paso={paso} desde={5}>{MARGEN}</Entra>
            <Entra paso={paso} desde={6}>{RESULTADO}</Entra>
            <Entra paso={paso} desde={7}>{F29}</Entra>
          </div>
        </Entra>
        <div className="hx-fijo__lat">
          <Entra paso={paso} desde={8} className="hx-derecha">{PREGUNTA}</Entra>
          <AnimatePresence mode="wait" initial={false}>
            {paso === 9 && <Escribiendo key="escribiendo" />}
            {paso >= 10 && (
              <motion.div key="respuesta" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, ease: EASE }}>
                {RESPUESTA}
              </motion.div>
            )}
          </AnimatePresence>
          <EntradaLateral />
        </div>
      </div>
    </div>
  );
}

function useEscala() {
  const [escala, setEscala] = useState(0.88);
  useLayoutEffect(() => {
    const medir = () => setEscala(Math.max(0.6, Math.min(0.92, (window.innerWidth - 64) / ANCHO, (window.innerHeight - 290) / ALTO)));
    medir();
    window.addEventListener('resize', medir);
    return () => window.removeEventListener('resize', medir);
  }, []);
  return escala;
}

export function useEscritorio() {
  const consulta = '(min-width: 1024px)';
  const [si, setSi] = useState(() => typeof window !== 'undefined' && window.matchMedia(consulta).matches);
  useLayoutEffect(() => {
    const m = window.matchMedia(consulta);
    const cambiar = () => setSi(m.matches);
    cambiar();
    m.addEventListener('change', cambiar);
    return () => m.removeEventListener('change', cambiar);
  }, []);
  return si;
}

function HeroConScroll({ children }) {
  const ref = useRef(null);
  const escala = useEscala();
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start start', 'end end'] });
  // Suavizado: la rueda del mouse avanza a saltos; el resorte sigue al scroll con un leve arrastre.
  const avance = useSpring(scrollYProgress, { stiffness: 55, damping: 20, mass: 0.6, restDelta: 0.0005 });

  const fondo = useTransform(avance, [0, 0.5], [1, 0.25]);
  const textoOpacidad = useTransform(avance, (v) => 1 - tramo(0.03, 0.11)(v));
  const textoY = useTransform(avance, [0.03, 0.11], [0, -28]);
  const textoEscala = useTransform(avance, [0.03, 0.11], [1, 0.96]);
  const textoClics = useTransform(avance, (v) => (v > 0.1 ? 'none' : 'auto'));
  const fraseOpacidad = useTransform(avance, (v) => Math.min(tramo(0.13, 0.21)(v), 1 - tramo(0.3, 0.4)(v)));
  const fraseY = useTransform(avance, [0.13, 0.21], [26, 0]);

  return (
    <section ref={ref} className="hx">
      <div className="hx__fijo">
        <motion.div className="lp-hero__fondo" aria-hidden="true" style={{ opacity: fondo }} />
        <div className="hx__escena">
          <div style={{ transform: `scale(${escala})` }} aria-hidden="true">
            <Lienzo avance={avance} />
          </div>
          <motion.div
            className="hx__texto"
            style={{ opacity: textoOpacidad, y: textoY, scale: textoEscala, pointerEvents: textoClics }}
          >
            {children}
          </motion.div>
          <motion.div className="hx__frase" style={{ opacity: fraseOpacidad, y: fraseY }}>
            <h2 className="lp-h2">Todo su ERP, desde un chat.</h2>
          </motion.div>
        </div>
      </div>
    </section>
  );
}

export default function HeroAnimado({ children }) {
  const escritorio = useEscritorio();
  const reducido = useReducedMotion();
  if (escritorio && !reducido) return <HeroConScroll>{children}</HeroConScroll>;
  return (
    <section className="lp-hero">
      <div className="lp-hero__fondo" aria-hidden="true" />
      <div className="lp-wrap lp-hero__texto">{children}</div>
      <div className="lp-wrap lp-wrap--ancho"><PantallaFija animada={!reducido} /></div>
    </section>
  );
}

