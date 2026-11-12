import { Link } from 'react-router-dom';
import { ArrowRight, Check, Sparkles, X } from 'lucide-react';
import EscenaFacturar from './escenas/EscenaFacturar';
import HeroMarco, { FONDOS, useFondos } from './escenas/HeroMarco';
import { ConApps, ConErp, SinSistema } from './escenas/Ilustraciones';
import { AgentesAnimados } from './escenas/EscenasAgentes';
import PasosAnimados from './escenas/PasosAnimados';
import McpAnimado from './escenas/McpAnimado';
import BienvenidaModal from './escenas/BienvenidaModal';
import LogoNegro from './escenas/LogoNegro';
import AsteriscoGiratorio from './escenas/AsteriscoGiratorio';
import { AgendarDemo, LOGOS, MenuPrincipal } from './Landing2Page';
import './Landing2Page.css';
import './Landing2Sobrio.css';
import './Landing3.css';

/*
 * La landing principal desde el 11-11-2026 (antes en prueba en /landing-nueva). Ideas de Alexis: "Simplifica la operación de tu empresa con IA",
 * "El primer ERP agéntico", "Agrega agentes a tu operación", dos formas de usarlo (plataforma
 * web para el dueño, API para la empresa, que incluye los proyectos sobre SAP, Oracle u Odoo),
 * la facturación y la conciliación al centro, y el contraste con los ERP de implementaciones
 * eternas. Va de tú, como los videos. Reutiliza las escenas de la landing 2.
 */

const LINKS = [
  { href: '#como-funciona', label: 'Cómo funciona' },
  { href: '#agentes',   label: 'Agentes' },
  { href: '#formas',    label: 'Formas de uso' },
  { href: '#facturar',  label: 'Facturación' },
  { href: '#preguntas', label: 'Preguntas' },
  { href: '#agendar',   label: 'Agendar demo' },
];

// Cómo funciona, en tres pasos generales (11-11-2026): refuerza que se empieza sin implementación.
const PASOS = [
  { titulo: 'Conecta', texto: 'Tu SII, tu banco y, si tienes, tu ERP. En minutos, no en meses.' },
  { titulo: 'Pide', texto: 'Escribe en el chat lo que necesitas: facturar, conciliar, cobrar, preparar el F29.' },
  { titulo: 'Confirma', texto: 'Tu agente lo hace y te muestra el resultado antes de confirmar por su cuenta.' },
];

// El contraste con los ERP tradicionales, sin nombrar marcas.
const CONTRASTE = [
  { tema: 'Implementación', antes: 'Meses', afable: 'El mismo día' },
  { tema: 'Cómo se usa', antes: 'Capacitación y consultores', afable: 'Lo pides en un chat' },
  { tema: 'Costo', antes: 'Licencias más implementación', afable: 'Un plan mensual' },
];

const PREGUNTAS = [
  {
    p: '¿Qué es un ERP agéntico?',
    r: 'Un ERP donde las tareas administrativas las hacen agentes de IA: tú se las pides en un chat y confirmas antes de que algo cambie.',
  },
  {
    p: '¿Tengo que dejar el sistema que uso hoy?',
    r: 'No. Afable se conecta a donde hoy facturas y llevas la contabilidad, y trabaja sobre eso. Si tu empresa usa SAP, Oracle u Odoo, la API conecta los agentes a ese sistema.',
  },
  {
    p: '¿Qué puedo pedirle en el chat?',
    r: 'Las tareas administrativas: facturar, registrar compras, conciliar el banco, revisar ventas y preparar el F29. Lo que cambia algo te pide confirmación.',
  },
  {
    p: '¿Cómo cargo mis datos del SII?',
    r: 'Afable te muestra paso a paso cómo bajar el Registro de Compras y Ventas y las boletas de honorarios, y los carga ahí mismo.',
  },
  {
    p: '¿Afable hace cosas sin que yo lo sepa?',
    r: 'Solo lo que dejaste activado como automatización. Cada una se ve, se pausa y se revisa en su módulo.',
  },
];

export default function Landing3Page() {
  const fondos = useFondos();
  return (
    <div className="lp lp2 lp3">
      <MenuPrincipal links={LINKS} />
      <AsteriscoGiratorio />
      <BienvenidaModal />

      {/* 1 · Hero: titular, el primer ERP agéntico y las dos puertas de entrada. */}
      <HeroMarco
        fondo={fondos.hero}
        titulo={<h1 className="lp-h1">Simplifica la operación<br />de tu empresa <span className="lp-degradado">con IA.</span></h1>}
        lado={(
          <>
            <p className="lp-lead">
              El primer ERP agéntico. Gestiona y automatiza las tareas administrativas con nuestros agentes de
              Finanzas, Contabilidad y más, desde un chat.
            </p>
            <div className="lp-acciones">
              <Link to="/register" className="lp-btn lp-btn--grande lp-btn--principal">Probar la plataforma</Link>
              <a href="#formas" className="lp-btn lp-btn--texto">Conectar vía API <ArrowRight size={15} /></a>
            </div>
          </>
        )}
      />

      {/* 2 · Con qué se integra. */}
      <section className="lp-logos" id="integraciones">
        <div className="lp-wrap lp-logos__wrap">
          <h2 className="lp-logos__titulo">Integrado a las herramientas que ya usas.</h2>
          <div className="lp-logos__marco">
            <div className="lp-logos__ventana">
              <div className="lp-logos__cinta">
                {[...LOGOS, ...LOGOS].map((l, i) => (
                  <img key={i} src={l.src} alt={i < LOGOS.length ? l.alt : ''}
                    aria-hidden={i >= LOGOS.length} style={{ height: l.h }} />
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 3 · Cómo funciona: tres pasos animados, justo bajo las integraciones. */}
      <section className="lp-seccion" id="como-funciona">
        <div className="lp-wrap">
          <h2 className="lp-h2">Empieza hoy, sin implementación.</h2>
          <PasosAnimados pasos={PASOS} />
        </div>
      </section>

      {/* 4 · Agrega agentes: un especialista en cada área. */}
      <section className="lp-seccion lp-seccion--fog" id="agentes">
        <div className="lp-wrap">
          <h2 className="lp-h2">Agrega agentes a tu operación.</h2>
          <p className="lp-lead">
            Un especialista en cada área: Ventas, Compras, Contabilidad y Finanzas. Le pides que gestione las
            cosas por ti.
          </p>
          <AgentesAnimados />
        </div>
      </section>

      {/* 5 · Tres formas de usar Afable: plataforma web (dueños), API (empresas, con proyectos) y apps sobre sus datos. */}
      <section className="lp-seccion" id="formas">
        <div className="lp-wrap">
          <h2 className="lp-h2">Tres formas de usar Afable.</h2>
          <div className="lp2-caminos lp3-caminos">
            <div className="lp2-camino">
              <div className="lp2-camino__imagen lp3-ilus"><SinSistema /></div>
              <div className="lp2-camino__texto">
                <span className="lp-medida__etiqueta lp2-camino__etiqueta"><Sparkles size={13} /> Plataforma web</span>
                <h3>¿No tienes sistema?</h3>
                <p>Una plataforma autoadministrable de agentes para tus tareas administrativas. Ventas, Compras, Contabilidad y Finanzas, cada uno con su agente.</p>
                <Link to="/register" className="lp-btn lp-btn--grande lp-btn--principal">Crear cuenta</Link>
              </div>
            </div>
            <div className="lp2-camino lp2-camino--oscuro">
              <div className="lp2-camino__imagen lp3-ilus"><ConErp /></div>
              <div className="lp2-camino__texto">
                <span className="lp-medida__etiqueta"><Sparkles size={13} /> API</span>
                <h3>¿Ya tienes un sistema ERP?</h3>
                <p>Hazle un upgrade agregándole IA y automatiza las tareas repetitivas con nuestra API. Sobre SAP, Oracle u Odoo: lo armamos contigo como proyecto.</p>
                <a href="#agendar" className="lp-btn lp-btn--grande lp-medida__boton">Agendar una reunión <ArrowRight size={16} /></a>
              </div>
            </div>
            <div className="lp2-camino">
              <div className="lp2-camino__imagen lp3-ilus"><ConApps /></div>
              <div className="lp2-camino__texto">
                <span className="lp-medida__etiqueta lp2-camino__etiqueta"><Sparkles size={13} /> Apps</span>
                <h3>¿Necesitas tus propios agentes?</h3>
                <p>Páginas y apps creadas en base a tus datos y tus automatizaciones, para tu equipo.</p>
                <a href="#agendar" className="lp-btn lp-btn--grande lp-btn--principal">Agendar una reunión</a>
              </div>
            </div>
          </div>
          {/* Frase de ejemplo (11-11-2026), sin firma: reemplazar por un testimonio real con permiso del cliente. */}
          <figure className="lp3-cita">
            <blockquote>“Afable nos resolvió la brecha entre la IA y nuestro ERP.”</blockquote>
          </figure>
        </div>
      </section>

      {/* 5b · MCP (11-11-2026): gestionar la empresa desde la IA que ya usas, como sección aparte. */}
      <section className="lp-seccion lp-oscuro lp3-oscuro" id="mcp">
        <div className="lp-wrap lp-dos">
          <div>
            <span className="lp-medida__etiqueta"><Sparkles size={13} /> MCP</span>
            <h2 className="lp-h2">Gestiona tu empresa desde <em>tu IA.</em></h2>
            <p className="lp-lead">
              Conecta Afable por MCP a la IA que ya usas: ChatGPT, Claude, Gemini, Copilot o Perplexity. Pídele que
              facture, concilie o te diga cuánto te deben, con los datos reales de tu empresa.
            </p>
            <div className="lp-acciones">
              <a href="#agendar" className="lp-btn lp-btn--grande lp-medida__boton">Agendar una reunión <ArrowRight size={16} /></a>
            </div>
          </div>
          <McpAnimado />
        </div>
      </section>

      {/* 6 · Facturar desde el chat. */}
      <section className="lp-seccion lp-seccion--fog" id="facturar">
        <div className="lp-wrap lp-dos">
          <div>
            <h2 className="lp-h2">Factura desde el chat.</h2>
            <p className="lp-lead">
              Pídelo como se lo dirías a alguien, o pide facturar un pedido de venta. Afable emite la factura
              electrónica y la deja registrada en Ventas.
            </p>
            <p className="lp-nota">Empresa de ejemplo.</p>
          </div>
          <EscenaFacturar />
        </div>
      </section>

      {/* 7 · El contraste: un ERP más afable. */}
      <section className="lp-seccion" id="contraste">
        <div className="lp-wrap">
          <h2 className="lp-h2">Un ERP más afable.</h2>
          <p className="lp-lead">Sin implementaciones eternas, sin sistemas complejos y sin licencias caras.</p>
          <div className="lp3-tabla" role="table" aria-label="ERP tradicional comparado con Afable">
            <div className="lp3-tabla__fila lp3-tabla__cab" role="row">
              <span role="columnheader" />
              <span role="columnheader">ERP tradicional</span>
              <span role="columnheader" className="lp3-tabla__afable"><LogoNegro size={18} /></span>
            </div>
            {CONTRASTE.map((c) => (
              <div key={c.tema} className="lp3-tabla__fila" role="row">
                <span role="rowheader" className="lp3-tabla__tema">{c.tema}</span>
                <span role="cell" className="lp3-tabla__antes"><X size={15} /> {c.antes}</span>
                <span role="cell" className="lp3-tabla__afable"><Check size={15} /> {c.afable}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 8 · Preguntas */}
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

      {/* 9 · Agendar */}
      <section className="lp-seccion" id="agendar">
        <div className="lp-wrap">
          <div className="lp-centro">
            <h2 className="lp-h2">Agenda una demostración.</h2>
            <p className="lp-lead lp-lead--centro">
              20 minutos para ver Afable con los datos de tu empresa. Elige el día y la hora que te acomoden.
            </p>
          </div>
          <AgendarDemo />
        </div>
      </section>

      {/* 10 · Pie */}
      <footer className="lp-footer lp2-pie">
        <div className="lp-wrap lp2-pie__arriba">
          <div className="lp2-pie__cierre">
            <h2 className="lp-h2">Agrega agentes a tu <span className="lp-degradado">operación.</span></h2>
            <div className="lp-acciones">
              <Link to="/register" className="lp-btn lp-btn--grande lp2-pie__principal">Crear cuenta</Link>
              <Link to="/login" className="lp-btn lp-btn--grande lp2-pie__secundario">Ingresar</Link>
            </div>
          </div>
          <div className="lp2-pie__enlaces">
            <div>
              <h4>Producto</h4>
              <a href="#agentes">Agentes</a>
              <a href="#facturar">Facturación</a>
              <a href="#como-funciona">Cómo funciona</a>
              <a href="#formas">API</a>
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
          <span>El primer ERP agéntico.</span>
          <span className="lp2-pie__anio">© 2026 Afable</span>
        </div>
        <div className="lp-wrap lp2-creditos">
          Imágenes: {Object.values(fondos).map((f) => FONDOS[f].credito).join(' · ')}.
        </div>
      </footer>
    </div>
  );
}
