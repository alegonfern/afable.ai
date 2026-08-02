import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Isotipo } from '../components/Logo';
import ProcessFlow from '../components/ProcessFlow';
import HeroShowcase from '../components/HeroShowcase';
import HeroScene from '../components/HeroScene';
import LandingLeadChat from '../components/LandingLeadChat';
import { odoo as odooLogo, sap as sapLogo, googleDrive as driveLogo } from '../assets/logos';
import './LandingPage.css';
import './LandingPageThemes.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001/api/v1';

// Vitrina de la comunidad si el backend no responde (landing nunca queda vacío)
const FALLBACK_TEMPLATES = [
  { id: 'f1', name: '@contratos — responde citando la cláusula', category: 'Legal', icon: '📑', accent: '#586AD0',
    description: 'Lee los contratos de tu Fuente legal y responde cualquier duda citando el párrafo exacto del documento.',
    author_name: 'Equipo Afable', uses_count: 587,
    flow: [{ app: 'Drive', icon: '📁', color: '#1A73E8' }, { app: 'Afable', icon: '✦', color: '#586AD0' }, { app: 'Slack', icon: '#️⃣', color: '#611f69' }] },
  { id: 'f2', name: '@stock — avisa antes del quiebre', category: 'Inventario', icon: '📦', accent: '#34D399',
    description: 'Vigila el inventario en tu ERP y le avisa al equipo antes de que un producto se agote.',
    author_name: 'Tienda Norte', uses_count: 412,
    flow: [{ app: 'Odoo', icon: '🟣', color: '#714B67' }, { app: 'Afable', icon: '✦', color: '#586AD0' }, { app: 'WhatsApp', icon: '💬', color: '#25D366' }] },
  { id: 'f3', name: '@ventas — publica el resumen del día', category: 'Ventas', icon: '📈', accent: '#586AD0',
    description: 'Cada mañana arma el resumen del día anterior y lo publica solo en la Sala del equipo comercial.',
    author_name: 'Comercial Andes', uses_count: 318,
    flow: [{ app: 'Odoo', icon: '🟣', color: '#714B67' }, { app: 'Afable', icon: '✦', color: '#586AD0' }, { app: 'Sala', icon: '🗂️', color: '#586AD0' }] },
];

/* ─── Visuales de las narrativas (estilo tarjeta de producto flotante) ─── */

function SystemsVisual() {
  const pills = ['Notion', 'Slack', 'GitHub', 'PostgreSQL', 'HubSpot', 'Excel', 'MSSQL'];
  return (
    <div className="lp-n-card">
      <div className="lp-n-card-head">Conexiones</div>
      <div className="lp-sys-partners">
        <span className="lp-sys-partner"><img src={odooLogo} alt="Odoo" /></span>
        <span className="lp-sys-partner"><img src={sapLogo} alt="SAP Business One" /><b>B1</b></span>
        <span className="lp-sys-partner lp-sys-partner--icono"><img src={driveLogo} alt="Google Drive" /></span>
      </div>
      <div className="lp-sys-pills">
        {pills.map(p => <span key={p}>{p}</span>)}
      </div>
      <div className="lp-n-card-foot">+142 conectores más</div>
    </div>
  );
}

function AgentsVisual() {
  const agents = [
    { icon: '🧠', name: '@afable', meta: 'todas las Fuentes abiertas' },
    { icon: '📑', name: '@contratos', meta: 'Fuente Legal · restringida' },
    { icon: '📈', name: '@ventas', meta: 'Odoo + CRM · equipo comercial' },
    { icon: '🎧', name: '@soporte', meta: 'tickets · en construcción' },
  ];
  return (
    <div className="lp-n-card">
      <div className="lp-n-card-head">Agentes del workspace</div>
      <div className="lp-file-rows">
        {agents.map(a => (
          <div key={a.name} className="lp-file-row">
            <span className="lp-file-icon">{a.icon}</span>
            <span className="lp-file-name">{a.name}</span>
            <span className="lp-file-meta">{a.meta}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function TeamVisual() {
  const members = [
    { initials: 'CM', name: 'Carla', area: 'Editor', sees: 'Finanzas + Ventas' },
    { initials: 'JR', name: 'Jorge', area: 'Miembro', sees: 'Ventas' },
    { initials: 'PA', name: 'Paula', area: 'Admin', sees: 'Todas las Fuentes' },
    { initials: 'DL', name: 'Diego', area: 'Miembro', sees: 'Inventario' },
  ];
  return (
    <div className="lp-n-card">
      <div className="lp-n-card-head">Personas y accesos</div>
      <div className="lp-team-rows">
        {members.map(m => (
          <div key={m.name} className="lp-team-row">
            <span className="lp-team-avatar">{m.initials}</span>
            <span className="lp-team-name">{m.name} <em>· {m.area}</em></span>
            <span className="lp-team-sees">{m.sees}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function TriggersVisual() {
  const routines = [
    { icon: '🗓️', name: 'Resumen de ventas', meta: 'programado · 08:00', state: '✓ en la Sala' },
    { icon: '🔔', name: 'Quiebre de stock', meta: 'evento · inventario', state: 'vigilando' },
    { icon: '🪝', name: 'Ticket nuevo', meta: 'webhook · soporte', state: '12 hoy' },
    { icon: '✋', name: 'Acción que escribe', meta: 'pide aprobación', state: '1 pendiente' },
  ];
  return (
    <div className="lp-n-card">
      <div className="lp-n-card-head">Disparadores activos</div>
      <div className="lp-file-rows">
        {routines.map(r => (
          <div key={r.name} className="lp-file-row">
            <span className="lp-file-icon">{r.icon}</span>
            <span className="lp-file-name">{r.name}<em className="lp-routine-meta"> · {r.meta}</em></span>
            <span className="lp-file-meta">{r.state}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function LandingPage() {
  const navigate = useNavigate();

  const [darkMode, setDarkMode] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const closeMenu = () => setMenuOpen(false);

  // href real (se puede abrir en pestaña nueva) + navegación SPA en el clic normal
  const goTo = (path) => (e) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
    e.preventDefault();
    navigate(path);
  };

  const [formData, setFormData] = useState({ name: '', email: '', company: '', message: '' });
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [formError, setFormError] = useState(false);
  const [openFaq, setOpenFaq] = useState(null);
  const [templates, setTemplates] = useState(FALLBACK_TEMPLATES);

  useEffect(() => {
    fetch(`${API_URL}/agents/templates/?featured=1`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => { if (Array.isArray(data) && data.length) setTemplates(data.slice(0, 3)); })
      .catch(() => {});
  }, []);

  const handleChange = (e) => setFormData((prev) => ({ ...prev, [e.target.name]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setFormError(false);
    try {
      const formId = import.meta.env.VITE_FORMSPREE_ID;
      const res = await fetch(`https://formspree.io/f/${formId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify(formData),
      });
      if (res.ok) {
        setSubmitted(true);
        setFormData({ name: '', email: '', company: '', message: '' });
      } else {
        setFormError(true);
      }
    } catch {
      setFormError(true);
    } finally {
      setSubmitting(false);
    }
  };

  const faqs = [
    {
      q: '¿Qué es exactamente un agente?',
      a: 'Un asistente de IA que tú configuras: le escribes sus instrucciones en español, eliges a qué datos de la empresa puede acceder, qué herramientas puede usar y con qué modelo piensa. Se llama con @su-nombre en cualquier conversación y responde con la información real de tu empresa, citando de dónde la sacó.',
    },
    {
      q: '¿Esto reemplaza a mi equipo?',
      a: 'No reemplazamos personas, las hacemos 10X más eficientes. El agente se hace cargo de buscar, cruzar y repetir; tu equipo se queda con el criterio y la decisión. Nadie deja de trabajar: cada persona trabaja con más alcance del que tenía sola.',
    },
    {
      q: '¿Necesito saber programar?',
      a: 'No. Los agentes se arman en pantalla, escribiendo en lenguaje natural lo que quieres que hagan. Si tu caso necesita una automatización más profunda entre sistemas, eso lo montamos nosotros con Workflow.',
    },
    {
      q: '¿Qué puedo conectar?',
      a: 'Google Drive, Notion, Slack, GitHub, tu ERP (SAP, Odoo), tu CRM, bases de datos, planillas y páginas web. También puedes subir archivos directamente. Si usas algo que no está en la lista, escríbenos y lo conectamos.',
    },
    {
      q: '¿Cómo controlo quién ve qué?',
      a: 'Organizas el conocimiento en Fuentes abiertas o restringidas y decides quién entra a cada una. Los tres roles — Miembro, Editor y Administrador — definen quién usa, quién crea agentes y quién administra el workspace. Los agentes heredan esos permisos: el dato de una Fuente restringida no llega a quien no tiene acceso.',
    },
    {
      q: '¿Un agente puede ejecutar acciones, o solo responder?',
      a: 'Puede ejecutar. Con sus herramientas conectadas escribe en tus sistemas, envía correos y dispara procesos. Y hay una regla que no se puede saltar: antes de cualquier acción que escriba, el agente te muestra qué va a hacer y espera tu aprobación.',
    },
    {
      q: '¿Mis datos están seguros?',
      a: 'Sí. Las credenciales se guardan cifradas, los datos de tus sistemas se consultan en vivo en el momento de cada pregunta, y tu información no se usa para entrenar modelos. Tu información sigue siendo tuya.',
    },
  ];

  const narratives = [
    {
      key: 'conexiones',
      title: <>Conecta tus<br />datos.</>,
      text: 'Google Drive, Notion, Slack, GitHub, tu ERP, tus bases de datos y los archivos que hoy viven sueltos en carpetas. Se conectan en minutos y se mantienen sincronizados. No cambias nada de lo que ya usas: Afable trabaja encima.',
      visual: <SystemsVisual />,
    },
    {
      key: 'fuentes',
      title: <>Cada equipo<br />ve lo suyo.</>,
      text: 'El conocimiento se organiza en Fuentes, abiertas para todo el workspace o restringidas a quienes tú designes. Ventas no ve los contratos de personas, y los agentes tampoco: cuando alguien no tiene acceso, el dato simplemente no llega a la respuesta.',
      visual: <TeamVisual />,
    },
    {
      key: 'agentes',
      title: <>Crea tus<br />agentes.</>,
      text: 'Sin escribir código: le dictas las instrucciones en español, eliges qué Fuentes puede consultar, qué herramientas puede usar y con qué modelo piensa. Lo publicas para ti, para tu equipo o para toda la empresa, y desde ahí cualquiera lo llama con @su-nombre.',
      visual: <AgentsVisual />,
    },
    {
      key: 'disparadores',
      title: <>Que trabajen<br />solos.</>,
      text: 'Un horario, un webhook o un evento en tus sistemas ponen al agente a trabajar sin que nadie abra la app: entrega el resultado por correo o lo publica en la Sala del equipo. Y si la tarea escribe en un sistema, primero te muestra qué va a hacer y espera tu aprobación.',
      visual: <TriggersVisual />,
    },
  ];

  const memoryCards = [
    { tag: '@ventas', line: 'Julio cerró en $412M · +12%', quote: '"¿Cómo venimos este mes?"' },
    { tag: '@contratos', line: 'Cláusula 8.2 — confidencialidad', quote: '"¿Qué firmamos con este cliente?"' },
    { tag: '@soporte', line: '14 tickets sin responder', quote: '"¿Qué quedó pendiente ayer?"' },
    { tag: '@personas', line: 'Te quedan 12 días de vacaciones', quote: '"¿Cuántos días tengo disponibles?"' },
  ];

  return (
    <div className={`lp-page ${darkMode ? 'dark' : 'light'}`}>

      {/* Nav */}
      <nav className="lp-nav">
        <div className="lp-logo"><Isotipo bgColor="#FFFFFF" /><span>Afable</span></div>

        <div className="lp-nav-links">
          <a href="#producto">Producto</a>
          <span className="lp-nav-sep" />
          <a href="#como-funciona">Cómo funciona</a>
          <span className="lp-nav-sep" />
          <a href="#precios">Precios</a>
          <span className="lp-nav-sep" />
          <a href="#workflow">Workflow</a>
          <span className="lp-nav-sep" />
          <a href="#faq">FAQ</a>
        </div>

        <div className="lp-nav-right">
          <button
            className="lp-theme-toggle"
            onClick={() => setDarkMode(!darkMode)}
            aria-label={darkMode ? 'Modo claro' : 'Modo oscuro'}
          >
            {darkMode ? (
              <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="4"/>
                <line x1="12" y1="2" x2="12" y2="4"/><line x1="12" y1="20" x2="12" y2="22"/>
                <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
                <line x1="2" y1="12" x2="4" y2="12"/><line x1="20" y1="12" x2="22" y2="12"/>
                <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
              </svg>
            ) : (
              <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
              </svg>
            )}
          </button>
          <button className="lp-btn-signin" onClick={() => navigate('/login')}>Iniciar sesión</button>
          <button className="lp-btn-pill" onClick={() => navigate('/register')}>Comenzar gratis</button>
        </div>

        <button
          className={`lp-hamburger${menuOpen ? ' open' : ''}`}
          onClick={() => setMenuOpen((v) => !v)}
          aria-label="Abrir menú"
        >
          <span /><span /><span />
        </button>
      </nav>

      {menuOpen && (
        <div className="lp-mobile-menu">
          <a href="#producto" onClick={closeMenu}>Producto</a>
          <a href="#como-funciona" onClick={closeMenu}>Cómo funciona</a>
          <a href="#precios" onClick={closeMenu}>Precios</a>
          <a href="#workflow" onClick={closeMenu}>Workflow</a>
          <a href="#faq" onClick={closeMenu}>FAQ</a>
          <button className="lp-btn-signin lp-btn-signin--mobile" onClick={() => { closeMenu(); navigate('/login'); }}>Iniciar sesión</button>
          <button className="lp-btn-pill" onClick={() => { closeMenu(); navigate('/register'); }}>Comenzar gratis</button>
        </div>
      )}

      {/* Hero: copy a la izquierda, escena a la derecha */}
      <header className="lp-hero">
        <div className="lp-hero-inner">
          <div className="lp-hero-copy">
            <h1>IA para <em>equipos.</em></h1>
            <p className="lp-hero-sub">Agentes de IA conectados a los datos de tu empresa. Responden en el chat, ejecutan tareas y siguen trabajando cuando tú no estás.</p>
            <div className="lp-hero-ctas">
              <button className="lp-btn-pill lp-btn-pill--big" onClick={() => navigate('/register')}>Empezar gratis →</button>
            </div>
            <LandingLeadChat navigate={navigate} />
            <div className="lp-hero-trust">Sin tarjeta de crédito · Listo en minutos · Funciona con los sistemas que ya usas</div>
          </div>
          <div className="lp-hero-art">
            <HeroScene />
          </div>
        </div>
      </header>

      {/* Demo del producto, protagonista bajo el hero — carrusel de 3 funciones */}
      <section className="lp-stage" id="producto">
        <HeroShowcase />
      </section>

      {/* Statement — el eslogan */}
      <section className="lp-memory">
        <h2 className="lp-display">No reemplazamos<br />personas.</h2>
        <p className="lp-section-sub lp-center">Las hacemos 10X más eficientes. Cada persona del equipo trabaja con agentes que ya conocen tus datos, tus procesos y tus reglas — y resuelven en minutos lo que antes tomaba una tarde entera.</p>
        <div className="lp-float-grid">
          {memoryCards.map((c) => (
            <div key={c.tag} className="lp-float-item">
              <div className="lp-float-card">
                <span className="lp-float-tag">{c.tag}</span>
                <span className="lp-float-line">{c.line}</span>
              </div>
              <div className="lp-float-quote">{c.quote}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Narrativas alternadas */}
      <section className="lp-narratives" id="como-funciona">
        {narratives.map((n, i) => (
          <div key={n.key} className={`lp-narrative${i % 2 ? ' reverse' : ''}`}>
            <div className="lp-n-visual">{n.visual}</div>
            <div className="lp-n-copy">
              <h2 className="lp-display">{n.title}</h2>
              <p>{n.text}</p>
              <button className="lp-btn-ghost" onClick={() => navigate('/register')}>Comenzar →</button>
            </div>
          </div>
        ))}
      </section>

      {/* Explorar — vitrina de la comunidad */}
      <section className="lp-explore" id="explorar">
        <h2 className="lp-display lp-center">Empieza con agentes<br />que ya funcionan.</h2>
        <p className="lp-section-sub lp-center">Una comunidad que comparte sus agentes. Tómalos como punto de partida, apúntalos a tus propias Fuentes y adáptalos a tu empresa — sin empezar de cero.</p>
        <div className="lp-explore-grid">
          {templates.map((tpl) => {
            const accent = tpl.accent || '#586AD0';
            return (
              <div
                key={tpl.id}
                className="lp-explore-card"
                onClick={() => navigate('/register')}
                style={{ '--accent': accent }}
              >
                <div className="lp-explore-flow">
                  <ProcessFlow flow={tpl.flow} accent={accent} dark={darkMode} />
                </div>
                <div className="lp-explore-body">
                  <div className="lp-explore-head">
                    <span className="lp-explore-icon">{tpl.icon}</span>
                    <span className="lp-explore-name">{tpl.name}</span>
                  </div>
                  <p className="lp-explore-desc">{tpl.description}</p>
                  <div className="lp-explore-foot">
                    <span className="lp-explore-meta">{tpl.author_name} · {tpl.uses_count} usos</span>
                    <span className="lp-explore-cta">Comencemos →</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* Seguridad — statement */}
      <section className="lp-security">
        <h2 className="lp-display">Tus datos siguen<br />siendo tuyos.</h2>
        <p className="lp-section-sub lp-center">Cada persona entra solo a las Fuentes que le corresponden, y cada agente consulta solo las que le asignaste. Las credenciales se guardan cifradas, los datos se leen en vivo en el momento de cada pregunta, y ninguna acción que escriba en tus sistemas se ejecuta sin tu aprobación.</p>
        <div className="lp-security-chips">
          <span>Credenciales cifradas</span>
          <span>Datos consultados en vivo, no almacenados</span>
          <span>Permisos por Fuente y por rol</span>
          <span>Aprobación humana para escribir</span>
        </div>
      </section>

      {/* Precios */}
      <section className="lp-pricing" id="precios">
        <h2 className="lp-display lp-center">Tu equipo con IA,<br />desde hoy.</h2>
        <p className="lp-section-sub lp-center">Creas tu cuenta, conectas tus datos y armas tus agentes tú mismo. Todos los planes incluyen 14 días gratis y no piden tarjeta de crédito para empezar.</p>
        <div className="lp-plans">
          <div className="lp-plan">
            <div className="lp-plan-name">Starter</div>
            <div className="lp-plan-price">$99 <span>/ mes</span></div>
            <div className="lp-plan-desc">Para equipos que están creando sus primeros agentes.</div>
            <ul className="lp-plan-feat">
              <li>5 agentes activos</li>
              <li>10 conexiones de datos</li>
              <li>5.000 mensajes/mes</li>
              <li>Fuentes abiertas y restringidas</li>
              <li>Disparadores programados</li>
              <li>Soporte por correo</li>
            </ul>
            <button className="lp-btn-ghost lp-btn-ghost--full" onClick={() => navigate('/register')}>Empezar gratis</button>
          </div>
          <div className="lp-plan featured">
            <div className="lp-plan-badge">Más popular</div>
            <div className="lp-plan-name">Growth</div>
            <div className="lp-plan-price">$299 <span>/ mes</span></div>
            <div className="lp-plan-desc">Para equipos que ya trabajan con sus agentes todos los días.</div>
            <ul className="lp-plan-feat">
              <li>Todo en Starter</li>
              <li>Agentes ilimitados</li>
              <li>50 conexiones de datos</li>
              <li>50.000 mensajes/mes</li>
              <li>Salas de trabajo del equipo</li>
              <li>Disparadores por webhook y evento</li>
              <li>Roles y permisos por Fuente</li>
              <li>Soporte prioritario</li>
            </ul>
            <button className="lp-btn-pill lp-btn-pill--full" onClick={() => navigate('/register')}>Empezar gratis</button>
          </div>
          <div className="lp-plan">
            <div className="lp-plan-name">Enterprise</div>
            <div className="lp-plan-price">Custom</div>
            <div className="lp-plan-desc">Para empresas con requerimientos específicos de escala o seguridad.</div>
            <ul className="lp-plan-feat">
              <li>Todo en Growth</li>
              <li>Conectores a medida</li>
              <li>Modelos y claves propias</li>
              <li>SSO / SAML</li>
              <li>SLA garantizado</li>
              <li>Onboarding dedicado</li>
            </ul>
            <button className="lp-btn-ghost lp-btn-ghost--full" onClick={() => { document.getElementById('contacto').scrollIntoView({ behavior: 'smooth' }); }}>Hablar con ventas</button>
          </div>
        </div>
      </section>

      {/* Workflow — automatizaciones a medida */}
      <section className="lp-workflow" id="workflow">
        <div className="lp-offer-band">
          <div className="lp-offer-card">
            <span className="lp-offer-tag lp-offer-tag--wf">Workflow</span>
            <h3>Conoce Workflow</h3>
            <p className="lp-offer-lead">Automatizaciones a medida, potenciadas con nuestra IA.</p>
            <p>Hay procesos que ninguna plataforma trae listos: los que cruzan tres sistemas, los que tienen las reglas de tu empresa metidas en el medio, los que hoy alguien hace a mano cada semana. Esos los diseñamos y los montamos nosotros — y quedan conectados a tus agentes, para que la parte que necesita criterio la resuelva la IA y el resto corra solo.</p>
            <div className="lp-workflow-points">
              <span>Lo diseña y lo monta nuestro equipo</span>
              <span>Conectado a los agentes de tu workspace</span>
              <span>Corriendo 24/7, sin que abras la app</span>
            </div>
            <button className="lp-btn-pill" onClick={() => { const el = document.getElementById('asistente'); if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' }); }}>Cuéntanos tu proceso →</button>
          </div>
        </div>
      </section>

      {/* FAQ minimalista */}
      <section className="lp-faq" id="faq">
        <h2 className="lp-display lp-center">Preguntas frecuentes.</h2>
        <div className="lp-faq-list">
          {faqs.map((item, i) => (
            <div key={i} className={`lp-faq-item${openFaq === i ? ' open' : ''}`}>
              <button className="lp-faq-q" onClick={() => setOpenFaq(openFaq === i ? null : i)}>
                <span>{item.q}</span>
                <span className="lp-faq-plus" aria-hidden="true">{openFaq === i ? '−' : '+'}</span>
              </button>
              {openFaq === i && <div className="lp-faq-a">{item.a}</div>}
            </div>
          ))}
        </div>
      </section>

      {/* Contacto */}
      <section className="lp-contact-section" id="contacto">
        <div className="lp-contact-inner">
          <div className="lp-contact-copy">
            <h2 className="lp-display">Listo para darle IA<br />a tu equipo?</h2>
            <p>Cuéntanos con qué datos trabaja tu equipo y qué tarea les come el día. Armamos contigo el primer agente — y el equipo lo empieza a usar ese mismo día.</p>
            <div className="lp-contact-bullets">
              <div className="lp-contact-bullet">✓ Armamos contigo tu primer agente</div>
              <div className="lp-contact-bullet">✓ Tu equipo con acceso desde el primer día</div>
              <div className="lp-contact-bullet">✓ Tus datos quedan bajo tu control</div>
            </div>
            <button className="lp-btn-pill lp-btn-pill--big" onClick={() => navigate('/register')} style={{ marginTop: 28 }}>
              Empezar gratis →
            </button>
          </div>
          <form className="lp-contact-form" onSubmit={handleSubmit}>
            <input
              type="text" name="name" placeholder="Tu nombre"
              value={formData.name} onChange={handleChange} required
            />
            <input
              type="email" name="email" placeholder="Tu email de trabajo"
              value={formData.email} onChange={handleChange} required
            />
            <input
              type="text" name="company" placeholder="Tu empresa (opcional)"
              value={formData.company} onChange={handleChange}
            />
            <textarea
              name="message" placeholder="¿En qué podemos ayudarte?"
              rows={4} value={formData.message} onChange={handleChange} required
            />
            <button
              type="submit" className="lp-btn-pill lp-btn-pill--full"
              disabled={submitting}
            >
              {submitting ? 'Enviando...' : 'Enviar mensaje'}
            </button>
            {submitted && <p className="lp-form-success">¡Mensaje enviado! Te contactaremos pronto.</p>}
            {formError && <p className="lp-form-error">Hubo un error al enviar. Intenta de nuevo.</p>}
          </form>
        </div>
      </section>

      {/* Footer */}
      <footer className="lp-footer">
        <div className="lp-footer-grid">

          <div className="lp-footer-brand">
            <div className="lp-footer-logo"><Isotipo size={18} bgColor="#FFFFFF" /><span>Afable</span></div>
            <p className="lp-footer-tagline">IA para equipos.</p>
            <ul className="lp-footer-contact">
              <li><a href="mailto:hi@getafable.com">hi@getafable.com</a></li>
              <li>
                <a href="https://wa.me/56955181000" target="_blank" rel="noopener noreferrer">
                  +569 5518 1000
                </a>
              </li>
            </ul>
          </div>

          <div className="lp-footer-col">
            <h4>Producto</h4>
            <ul>
              <li><a href="#producto">Qué es Afable</a></li>
              <li><a href="#como-funciona">Cómo funciona</a></li>
              <li><a href="#explorar">Agentes</a></li>
              <li><a href="#precios">Precios</a></li>
              <li><a href="#workflow">Workflow</a></li>
            </ul>
          </div>

          <div className="lp-footer-col">
            <h4>Conexiones</h4>
            <ul>
              <li><a href="#producto">Odoo</a></li>
              <li><a href="#producto">SAP Business One</a></li>
              <li><a href="#producto">SQL Server</a></li>
              <li><a href="#producto">PostgreSQL</a></li>
              <li><a href="#producto">Google Drive</a></li>
              <li><a href="#producto">Excel y CSV</a></li>
              <li><a className="lp-footer-more" href="#contacto">Pedir una conexión →</a></li>
            </ul>
          </div>

          <div className="lp-footer-col">
            <h4>Soporte</h4>
            <ul>
              <li><a href="#faq">Preguntas frecuentes</a></li>
              <li><a href="#contacto">Contacto</a></li>
              <li>
                <a href="https://wa.me/56955181000" target="_blank" rel="noopener noreferrer">
                  WhatsApp
                </a>
              </li>
              <li><a href="/login" onClick={goTo('/login')}>Iniciar sesión</a></li>
              <li><a href="/register" onClick={goTo('/register')}>Comenzar gratis</a></li>
            </ul>
          </div>

        </div>

        <div className="lp-footer-bottom">
          <span className="lp-footer-copy">© 2026 Afable · Hecho en Chile</span>
          <div className="lp-footer-legal">
            <a href="/privacidad" onClick={goTo('/privacidad')}>Privacidad</a>
            <a href="/terminos" onClick={goTo('/terminos')}>Términos</a>
            <a href="/seguridad" onClick={goTo('/seguridad')}>Seguridad</a>
          </div>
        </div>
      </footer>

      {/* WhatsApp Floating Button */}
      <a
        href="https://wa.me/56955181000"
        className="lp-wsp-float"
        target="_blank"
        rel="noopener noreferrer"
        aria-label="Contactar por WhatsApp"
      >
        <svg viewBox="0 0 24 24" fill="currentColor">
          <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-1.061-1.623-.075-.015-.458-.064-.73.05-.272.114-1.078.693-1.078 1.693s.73 1.97 1.156 2.503c.426.533 1.438 2.316 3.486 3.203.487.213.868.341 1.164.436.488.155.933.133 1.285.08.392-.058 1.207-.493 1.376-.967.17-.474.17-.88.12-.966-.05-.087-.184-.139-.481-.288zM12 0c-6.627 0-12 5.373-12 12 0 2.113.547 4.095 1.507 5.823l-1.507 5.488 5.617-1.474c1.674.887 3.58 1.391 5.601 1.391 6.627 0 12-5.373 12-12s-5.373-12-12-12zm.173 21.644c-1.901 0-3.69-.49-5.244-1.346l-.376-.206-3.292.863.878-3.197-.226-.361c-.933-1.488-1.427-3.213-1.427-5.018 0-5.18 4.214-9.394 9.394-9.394 5.18 0 9.394 4.214 9.394 9.394s-4.214 9.394-9.394 9.394z"/>
        </svg>
      </a>

    </div>
  );
}
