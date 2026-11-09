import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowRight, ArrowUp, Calculator, Check, Menu,
  Package, ShoppingCart, Sparkles, X, Zap,
} from 'lucide-react';
import {
  odoo as odooLogo, sap as sapLogo, excel as excelLogo, googleDrive as driveLogo,
} from '../../assets/logos';
import santanderLogo from '../../assets/logos/integraciones/santander.svg';
import bancoChileLogo from '../../assets/logos/integraciones/bancochile.svg';
import bciLogo from '../../assets/logos/integraciones/bci.svg';
import biceLogo from '../../assets/logos/integraciones/bice.svg';
import itauLogo from '../../assets/logos/integraciones/itau.svg';
import bbvaLogo from '../../assets/logos/integraciones/bbva.svg';
import mercadoPagoLogo from '../../assets/logos/integraciones/mercadopago.svg';
import global66Logo from '../../assets/logos/integraciones/global66.svg';
import bukLogo from '../../assets/logos/integraciones/buk.svg';
import rindeGastosLogo from '../../assets/logos/integraciones/rindegastos.svg';
import hubspotLogo from '../../assets/logos/integraciones/hubspot.svg';
import stripeLogo from '../../assets/logos/integraciones/stripe.svg';
import salesforceLogo from '../../assets/logos/integraciones/salesforce.svg';
import EscenaFacturar from './escenas/EscenaFacturar';
import EscenaPrincipal from './escenas/EscenaPrincipal';
import HeroMarco, { FONDOS, FondoPintado, MarcoPintado, useFondos } from './escenas/HeroMarco';
import { RecorteLoQueHizoHoy } from './escenas/VistaAgente';
import { ModosAnimados, RegistroEnVivo } from './escenas/EscenasChicas';
import { AgentesAnimados, DoloresAnimados } from './escenas/EscenasAgentes';
import LogoNegro from './escenas/LogoNegro';
import AsteriscoGiratorio from './escenas/AsteriscoGiratorio';
import './Landing2Page.css';
import './Landing2Sobrio.css';

/*
 * La landing, rehecha el 14-10-2026 con el enfoque nuevo: Afable gestiona la empresa
 * desde un chat, con dos módulos (Ventas y Contabilidad) y sus automatizaciones.
 *
 * La estructura sigue a sintropix.com (titular de entrega diaria → el producto
 * trabajando → con qué se conecta → el problema → tres columnas → registro en vivo →
 * pasos verificables → bloque oscuro del agente → cierre). El menú y los botones
 * siguen a askbond.ai. Detalle en la memoria `afable-diseno-referencias`.
 *
 * Todas las cifras de los visuales son de una empresa de ejemplo y lo dicen.
 */

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001/api/v1';

const SUGERENCIAS = [
  '¿Qué hace Afable?',
  '¿Puede emitir mis facturas?',
  '¿Me ayuda con el F29?',
  'Quiero una demostración',
];

// El modelo a veces marca negritas con **…**: se muestran como negrita y no como asteriscos.
function ConNegritas({ texto }) {
  return texto.split('**').map((parte, i) => (i % 2 ? <b key={i}>{parte}</b> : parte));
}

/*
 * El chat del hero, como el de askbond: una caja grande con el botón redondo de enviar.
 * Es el mismo asistente de la landing anterior (`LandingLeadChat`, endpoint
 * `/leads/chat/`): responde de verdad, sin login, y si el visitante quiere que lo
 * contacten deja su correo como Lead.
 */
function ChatHero() {
  const [mensajes, setMensajes] = useState([]);
  const [texto, setTexto] = useState('');
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState(false);
  const [segmento, setSegmento] = useState(null);
  const [capturado, setCapturado] = useState(false);
  const cuerpo = useRef(null);

  useEffect(() => {
    if (cuerpo.current) cuerpo.current.scrollTop = cuerpo.current.scrollHeight;
  }, [mensajes, cargando]);

  const enviar = async (propio) => {
    const contenido = (propio ?? texto).trim();
    if (!contenido || cargando) return;
    const siguientes = [...mensajes, { role: 'user', content: contenido }];
    setMensajes(siguientes);
    setTexto('');
    setError(false);
    setCargando(true);
    try {
      const res = await fetch(`${API_URL}/leads/chat/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: siguientes }),
      });
      if (!res.ok) throw new Error('estado');
      const data = await res.json();
      setMensajes((prev) => [...prev, { role: 'assistant', content: data.reply }]);
      if (data.segment) setSegmento(data.segment);
      if (data.lead_captured) setCapturado(true);
    } catch {
      setError(true);
    } finally {
      setCargando(false);
    }
  };

  const alTeclear = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      enviar();
    }
  };

  const conversando = mensajes.length > 0;

  return (
    <div className="lp-chat">
      <div className={`lp-chat__caja${conversando ? ' is-conversando' : ''}`}>
        {conversando && (
          <div className="lp-chat__cuerpo" ref={cuerpo} aria-live="polite">
            {mensajes.map((m, i) => (
              <div key={i} className={`lp-msg${m.role === 'user' ? ' lp-msg--yo' : ' lp-msg--ia'}`}>
                <ConNegritas texto={m.content} />
              </div>
            ))}
            {cargando && <div className="lp-msg lp-msg--ia lp-chat__escribiendo"><span /><span /><span /></div>}
            {segmento === 'saas' && !capturado && (
              <div className="lp-chat__cta">
                <Link to="/register" className="lp-btn lp-btn--principal">Crear cuenta</Link>
              </div>
            )}
            {/* Quien pide una demostración puede agendarla él mismo, sin esperar el correo. */}
            {segmento === 'workflow' && (
              <div className="lp-chat__cta">
                <a href="#agendar" className="lp-btn lp-btn--principal">Agendar una demostración</a>
              </div>
            )}
            {capturado && <div className="lp-chat__aviso"><Check size={14} /> Listo, el equipo lo contactará por correo.</div>}
            {error && <div className="lp-chat__aviso lp-chat__aviso--error">No pudimos responder ahora. Intente de nuevo.</div>}
          </div>
        )}
        {!capturado && (
          <div className="lp-chat__entrada">
            <textarea
              value={texto}
              onChange={(e) => setTexto(e.target.value)}
              onKeyDown={alTeclear}
              placeholder={conversando ? 'Escriba su respuesta…' : 'Pregúntele a Afable lo que necesita su empresa…'}
              rows={conversando ? 1 : 3}
              disabled={cargando}
              aria-label="Escríbale a Afable"
            />
            <button
              type="button"
              className="lp-chat__enviar"
              onClick={() => enviar()}
              disabled={cargando || !texto.trim()}
              aria-label="Enviar"
            >
              <ArrowUp size={16} />
            </button>
          </div>
        )}
      </div>
      {!conversando && (
        <div className="lp-chat__sugerencias">
          {SUGERENCIAS.map((q) => (
            <button key={q} type="button" onClick={() => enviar(q)}>{q}</button>
          ))}
        </div>
      )}
    </div>
  );
}

/*
 * Agendar una reunión de 20 minutos con Alexis, con el embed en línea de Cal.com. Es el
 * mismo código que entrega Cal ("inline embed"), pasado a React: el cargador se agrega una
 * sola vez y el calendario se dibuja al montar la sección.
 */
const CAL_LINK = 'alexis-gonzalez-ymenrm/20min';
const CAL_NS = '20min';

function cargarCal() {
  /* eslint-disable */
  (function (C, A, L) { let p = function (a, ar) { a.q.push(ar); }; let d = C.document; C.Cal = C.Cal || function () { let cal = C.Cal; let ar = arguments; if (!cal.loaded) { cal.ns = {}; cal.q = cal.q || []; d.head.appendChild(d.createElement("script")).src = A; cal.loaded = true; } if (ar[0] === L) { const api = function () { p(api, arguments); }; const namespace = ar[1]; api.q = api.q || []; if (typeof namespace === "string") { cal.ns[namespace] = cal.ns[namespace] || api; p(cal.ns[namespace], ar); p(cal, ["initNamespace", namespace]); } else p(cal, ar); return; } p(cal, ar); }; })(window, "https://app.cal.com/embed/embed.js", "init");
  /* eslint-enable */
}

function AgendarDemo() {
  useEffect(() => {
    cargarCal();
    const { Cal } = window;
    if (!Cal.ns?.[CAL_NS]) {
      Cal('init', CAL_NS, { origin: 'https://app.cal.com' });
      Cal.config = Cal.config || {};
      Cal.config.forwardQueryParams = true;
    }
    Cal.ns[CAL_NS]('inline', {
      elementOrSelector: '#lp-cal-20min',
      config: { layout: 'month_view', useSlotsViewOnSmallScreen: 'true', theme: 'light' },
      calLink: CAL_LINK,
    });
    Cal.ns[CAL_NS]('ui', { theme: 'light', hideEventTypeDetails: false, layout: 'month_view' });
  }, []);

  return <div id="lp-cal-20min" className="lp-cal" />;
}

// La cinta de integraciones, copiada de sintropix.com (sección `#integraciones`): los
// mismos SVG de bancos y servicios (bajados de sintropix.com/logos el 15-10-2026, en
// `assets/logos/integraciones/`) con las mismas alturas, más SAP, Odoo, Drive y Excel, que
// ya estaban en el proyecto.
const LOGOS = [
  { src: sapLogo, alt: 'SAP Business One', h: 22 },
  { src: odooLogo, alt: 'Odoo', h: 20 },
  { src: santanderLogo, alt: 'Banco Santander', h: 21 },
  { src: bancoChileLogo, alt: 'Banco de Chile', h: 17 },
  { src: bciLogo, alt: 'BCI', h: 27 },
  { src: biceLogo, alt: 'Banco BICE', h: 13 },
  { src: itauLogo, alt: 'Itaú', h: 31 },
  { src: bbvaLogo, alt: 'BBVA', h: 28 },
  { src: mercadoPagoLogo, alt: 'Mercado Pago', h: 28 },
  { src: global66Logo, alt: 'Global66', h: 19 },
  { src: driveLogo, alt: 'Google Drive', h: 26 },
  { src: excelLogo, alt: 'Excel', h: 26 },
  { src: bukLogo, alt: 'Buk', h: 30 },
  { src: rindeGastosLogo, alt: 'Rinde Gastos', h: 18 },
  { src: hubspotLogo, alt: 'HubSpot', h: 22 },
  { src: stripeLogo, alt: 'Stripe', h: 26 },
  { src: salesforceLogo, alt: 'Salesforce', h: 24 },
];

const LINKS = [
  { href: '#como-funciona', label: 'Cómo funciona' },
  { href: '#agentes',       label: 'Agentes' },
  { href: '#modulos',       label: 'Módulos' },
  { href: '#preguntas',     label: 'Preguntas' },
  { href: '#a-medida',      label: 'Proyectos' },
  { href: '#agendar',       label: 'Agendar demo' },
];

function MenuPrincipal() {
  const [conScroll, setConScroll] = useState(false);
  const [abierto, setAbierto] = useState(false);

  // La pastilla de fondo aparece recién al bajar: arriba el menú flota sobre el hero.
  useEffect(() => {
    const alMover = () => setConScroll(window.scrollY > 12);
    alMover();
    window.addEventListener('scroll', alMover, { passive: true });
    return () => window.removeEventListener('scroll', alMover);
  }, []);

  return (
    <header className={`lp-nav${conScroll ? ' lp-nav--scroll' : ''}`}>
      <div className="lp-nav__inner">
        <div className="lp-nav__bg" aria-hidden="true" />
        <Link to="/" className="lp-nav__marca" aria-label="Afable, inicio"><LogoNegro size={24} /></Link>
        <nav className={`lp-nav__menu${abierto ? ' is-open' : ''}`}>
          <div className="lp-nav__links">
            {LINKS.map((l) => (
              <a key={l.href} href={l.href} className="lp-nav__link" onClick={() => setAbierto(false)}>
                {l.label}
              </a>
            ))}
          </div>
          <div className="lp-nav__botones">
            <Link to="/login" className="lp-btn lp-btn--secundario">Ingresar</Link>
            <Link to="/register" className="lp-btn lp-btn--principal">Crear cuenta</Link>
          </div>
        </nav>
        <button
          type="button"
          className="lp-nav__burger"
          aria-label={abierto ? 'Cerrar menú' : 'Abrir menú'}
          aria-expanded={abierto}
          onClick={() => setAbierto((v) => !v)}
        >
          {abierto ? <X size={20} /> : <Menu size={20} />}
        </button>
      </div>
    </header>
  );
}

const MOVIMIENTOS = [
  { fecha: '14 oct', origen: 'Banco', detalle: 'Transferencia Comercial Andes', monto: '$148.750', estado: 'Conciliado' },
  { fecha: '14 oct', origen: 'Venta', detalle: 'Factura N° 1043', monto: '$148.750', estado: 'Emitida' },
  { fecha: '13 oct', origen: 'Compra', detalle: 'Factura proveedor N° 88213', monto: '$412.000', estado: 'Por confirmar' },
  { fecha: '13 oct', origen: 'Banco', detalle: 'Pago arriendo oficina', monto: '$950.000', estado: 'Conciliado' },
  { fecha: '12 oct', origen: 'Venta', detalle: 'Factura N° 1042', monto: '$63.070', estado: 'Emitida' },
];

// Un pastel por estado, como las etiquetas de Sintropix.
const ESTADOS = { Conciliado: 'ok', Emitida: 'info', 'Por confirmar': 'pend' };

const PASOS = [
  { titulo: 'Llega la factura', texto: 'Adjunte el PDF o el XML en el chat.' },
  { titulo: 'Afable la lee', texto: 'Proveedor, fecha, neto, IVA y total: cinco campos.' },
  { titulo: 'La cruza con el banco', texto: 'Busca el pago y la marca como conciliada.' },
  { titulo: 'Queda registrada', texto: 'Lista para el libro y para el F29, sin digitar.' },
];

const PREGUNTAS = [
  {
    p: '¿Tengo que dejar el sistema que uso hoy?',
    r: 'No. Afable se conecta a donde hoy factura y lleva la contabilidad, y trabaja sobre eso.',
  },
  {
    p: '¿Qué puedo pedirle en el chat?',
    r: 'Las tareas administrativas: facturar, registrar compras, conciliar el banco, revisar ventas y preparar el F29. Lo que cambia algo le pide confirmación.',
  },
  {
    p: '¿Cómo cargo mis datos del SII?',
    r: 'Afable le muestra paso a paso cómo bajar el Registro de Compras y Ventas y las boletas de honorarios, y los carga ahí mismo.',
  },
  {
    p: '¿Qué es un agente de Afable?',
    r: 'Es la IA de cada módulo: conoce sus datos, hace el trabajo que le pida y le pide confirmación antes de cambiar algo.',
  },
  {
    p: '¿Afable hace cosas sin que yo lo sepa?',
    r: 'Solo lo que usted dejó activado como automatización. Cada una se ve, se pausa y se revisa en su módulo.',
  },
];

export default function Landing2Page() {
  const fondos = useFondos();
  return (
    <div className="lp lp2">
      <MenuPrincipal />
      <AsteriscoGiratorio />

      {/* 1 · Hero con marco: titular, descripción y botones centrados, y debajo la
          vista Agente de Finanzas sobre una pintura (detalle en HeroMarco.jsx). */}
      <HeroMarco
        fondo={fondos.hero}
        titulo={(
          <>
            <h1 className="lp-h1">Agentes de IA para la<br /><span className="lp-degradado">gestión interna</span> de empresas.</h1>
          </>
        )}
        lado={(
          <>
            <p className="lp-lead">
              Afable es una plataforma de agentes de IA para empresas. Ayuda en las tareas administrativas y
              repetitivas para que las personas se centren en lo importante.
            </p>
            <div className="lp-acciones">
              <Link to="/register" className="lp-btn lp-btn--grande lp-btn--principal">Crear cuenta</Link>
              <a href="#como-funciona" className="lp-btn lp-btn--texto">Ver cómo funciona <ArrowRight size={15} /></a>
            </div>
          </>
        )}
      />

      {/* 1b · Con qué se integra: la prueba social, justo bajo el hero (réplica de la franja de sintropix.com). */}
      <section className="lp-logos" id="integraciones">
        <div className="lp-wrap lp-logos__wrap">
          <h2 className="lp-logos__titulo">Integrado a las herramientas que ya usa.</h2>
          <div className="lp-logos__marco">
            <div className="lp-logos__ventana">
              {/* La lista va dos veces: la cinta se corre la mitad y vuelve a empezar sin salto. */}
              <div className="lp-logos__cinta">
                {[...LOGOS, ...LOGOS].map((l, i) => (
                  <img key={i} src={l.src} alt={i < LOGOS.length ? l.alt : ''}
                    aria-hidden={i >= LOGOS.length} style={{ height: l.h }} />
                ))}
              </div>
            </div>
            <div className="lp-logos__mas">
              <a href="#agendar">Más integraciones <ArrowRight size={16} /></a>
            </div>
          </div>
          <div className="lp-logos__mas-movil"><a href="#agendar">Más integraciones <ArrowRight size={16} /></a></div>
        </div>
      </section>

      {/* 2 · Lo que hoy le quita el día, resuelto (25-10-2026): el problema que reconoce quien llega. */}
      <section className="lp-seccion">
        <div className="lp-wrap">
          <h2 className="lp-h2">Lo que hoy le quita el día, resuelto.</h2>
          <DoloresAnimados />
        </div>
      </section>

      {/* 3 · Un agente detrás de cada módulo (25-10-2026): la respuesta de Afable. */}
      <section className="lp-seccion lp-seccion--fog" id="agentes">
        <div className="lp-wrap">
          <h2 className="lp-h2">Un especialista en cada área.</h2>
          <p className="lp-lead">
            Ventas, Compras, Contabilidad, Finanzas: a cada uno le puede pedir que gestione cosas por usted.
          </p>
          <AgentesAnimados />
        </div>
      </section>

      {/* 4 · Así trabaja: los cuatro capítulos en bucle, dentro de un marco con pintura como el hero. */}
      <section className="lp-seccion lp-seccion--escena" id="como-funciona">
        <div className="lp-wrap lp-wrap--ancho">
          <h2 className="lp-h2 lp-centro">Así trabaja Afable.</h2>
          <MarcoPintado fondo={fondos.escena} className="lp2-marco-escena"><EscenaPrincipal /></MarcoPintado>
        </div>
      </section>

      {/* 5 · Módulo | Agente */}
      <section className="lp-seccion lp-seccion--fog" id="modulos">
        <div className="lp-wrap lp-dos">
          <div>
            <h2 className="lp-h2">Cada módulo y su agente.</h2>
            <p className="lp-lead">
              En <b>Módulo</b> trabaja el formulario del módulo. En <b>Agente</b> conversa con el agente de ese
              módulo y ve lo que hace solo.
            </p>
          </div>
          <ModosAnimados />
        </div>
      </section>

      {/* 6 · Escena animada: facturar desde el chat */}
      <section className="lp-seccion" id="facturar">
        <div className="lp-wrap lp-dos">
          <div>
            <h2 className="lp-h2">Facture desde el chat.</h2>
            <p className="lp-lead">
              Pídalo como se lo diría a alguien, o pida facturar un pedido de venta. Afable emite la
              factura electrónica y la deja registrada en Ventas.
            </p>
            <p className="lp-nota">Empresa de ejemplo.</p>
          </div>
          <EscenaFacturar />
        </div>
      </section>

      {/* 7 · Pasos verificables: el mismo ejemplo, paso a paso. */}
      <section className="lp-seccion lp2-seccion--pegada">
        <div className="lp-wrap">
          <h2 className="lp-h2">De la factura al registro, paso a paso.</h2>
          <ol className="lp-pasos">
            {PASOS.map((p, i) => (
              <li key={p.titulo} className="lp-paso">
                <span className="lp-paso__n">{i === PASOS.length - 1 ? <Check size={14} /> : i + 1}</span>
                <h3>{p.titulo}</h3>
                <p>{p.texto}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* 8 · Vea cómo avanza su empresa: el registro en vivo */}
      <section className="lp-seccion lp-seccion--fog">
        <div className="lp-wrap">
          <h2 className="lp-h2">Vea cómo avanza su empresa.</h2>
          <p className="lp-lead">
            Cada factura, pago y movimiento queda registrado al momento, y el panel le dice qué necesita su atención.
          </p>
          <RegistroEnVivo movimientos={MOVIMIENTOS} estados={ESTADOS} />
          <p className="lp-nota">Movimientos de una empresa de ejemplo.</p>
        </div>
      </section>

      {/* 9 · Pregúntele a su empresa: el chat real de la landing, sobre una pintura oscurecida. */}
      <section className="lp-seccion lp-oscuro lp2-oscuro--pintado" id="chat">
        <FondoPintado fondo={fondos.chat} />
        <div className="lp-wrap lp-dos">
          <div>
            <h2 className="lp-h2">Pregúntele a <span className="lp-degradado">su empresa.</span></h2>
            <p className="lp-lead">
              Afable responde con los datos de su empresa, no con estimaciones. Y si le pide que
              haga algo, lo hace.
            </p>
          </div>
          <div className="lp2-chat"><ChatHero /></div>
        </div>
      </section>

      {/* 10 · Dos caminos (30-10-2026): Afable como su sistema de gestión, o sus agentes sobre el ERP que
          ya tiene (Afable Proyectos). Cada tarjeta lleva una pintura con un recorte de pantalla delante. */}
      <section className="lp-seccion" id="a-medida">
        <div className="lp-wrap">
          <h2 className="lp-h2">Con su sistema actual o sin él.</h2>
          <div className="lp2-caminos">
            <div className="lp2-camino">
              <MarcoPintado fondo={fondos.afable} className="lp2-camino__imagen"><RecorteLoQueHizoHoy /></MarcoPintado>
              <div className="lp2-camino__texto">
                <span className="lp-medida__etiqueta lp2-camino__etiqueta"><Sparkles size={13} /> Afable</span>
                <h3>Afable como su sistema de gestión.</h3>
                <p>Ventas, Compras, Contabilidad y Finanzas, cada uno con su agente. Se maneja desde un chat y usted confirma antes de que algo cambie.</p>
                <Link to="/register" className="lp-btn lp-btn--grande lp-btn--principal">Crear cuenta</Link>
              </div>
            </div>
            <div className="lp2-camino lp2-camino--oscuro">
              <MarcoPintado fondo={fondos.proyectos} className="lp2-camino__imagen">
                <div className="lp2-recorte-chat">
                  <div className="hx-derecha"><div className="hx-lat__yo">¿Qué pedidos de SAP siguen sin facturar?</div></div>
                  <div className="hx-lat__ia">
                    Hay <b>12 pedidos</b> en SAP Business One sin factura, por <b>$8.940.000</b>. ¿Le preparo las facturas?
                  </div>
                  <div className="lp2-recorte-chat__fuente">Empresa de ejemplo · SAP Business One</div>
                </div>
              </MarcoPintado>
              <div className="lp2-camino__texto">
                <span className="lp-medida__etiqueta"><Sparkles size={13} /> Afable Proyectos</span>
                <h3>¿Su empresa ya trabaja con SAP, Oracle u Odoo?</h3>
                <p>Le damos a sus sistemas la IA de Afable: agentes, automatizaciones y chat sobre los procesos que ya tiene. Es un proyecto a medida, aparte de la suscripción.</p>
                <a href="#agendar" className="lp-btn lp-btn--grande lp-medida__boton">Agendar una reunión <ArrowRight size={16} /></a>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 11 · Preguntas */}
      <section className="lp-seccion lp-seccion--fog" id="preguntas">
        <div className="lp-wrap lp-preguntas">
          <h2 className="lp-h2">Preguntas antes de empezar.</h2>
          {PREGUNTAS.map((q) => (
            <details key={q.p} className="lp-pregunta">
              <summary>{q.p}</summary>
              <p>{q.r}</p>
            </details>
          ))}
        </div>
      </section>

      {/* 12 · Agendar: reunión de 20 minutos por Cal.com */}
      <section className="lp-seccion" id="agendar">
        <div className="lp-wrap">
          <div className="lp-centro">
            <h2 className="lp-h2">Agende una demostración.</h2>
            <p className="lp-lead lp-lead--centro">
              20 minutos para ver Afable con los datos de su empresa. Elija el día y la hora que
              le acomoden.
            </p>
          </div>
          <AgendarDemo />
        </div>
      </section>

      {/* 13 · El pie invertido (30-10-2026, como harvey.ai): fondo negro. A la izquierda el cierre, "Opere su
          empresa con IA." con sus botones (antes era una sección aparte); a la derecha los enlaces. Abajo la
          marca, el año y de dónde salen las imágenes. */}
      <footer className="lp-footer lp2-pie">
        <div className="lp-wrap lp2-pie__arriba">
          <div className="lp2-pie__cierre">
            <h2 className="lp-h2">Agregue agentes a la <span className="lp-degradado">gestión diaria</span> de su empresa.</h2>
            <div className="lp-acciones">
              <Link to="/register" className="lp-btn lp-btn--grande lp2-pie__principal">Crear cuenta</Link>
              <Link to="/login" className="lp-btn lp-btn--grande lp2-pie__secundario">Ingresar</Link>
            </div>
          </div>
          <div className="lp2-pie__enlaces">
            <div>
              <h4>Producto</h4>
              <a href="#modulos">Ventas</a>
              <a href="#modulos">Compras</a>
              <a href="#modulos">Contabilidad</a>
              <a href="#modulos">Automatizaciones</a>
            </div>
            <div>
              <h4>Empresa</h4>
              <Link to="/seguridad">Seguridad</Link>
              <Link to="/privacidad">Privacidad</Link>
              <Link to="/terminos">Términos</Link>
            </div>
          </div>
        </div>
        <div className="lp-wrap lp2-pie__base">
          <LogoNegro size={22} claro />
          <span>Agentes de IA para la gestión interna de empresas.</span>
          <span className="lp2-pie__anio">© 2026 Afable</span>
        </div>
        <div className="lp-wrap lp2-creditos">
          Imágenes: {Object.values(fondos).map((f) => FONDOS[f].credito).join(' · ')}.
        </div>
      </footer>
    </div>
  );
}
