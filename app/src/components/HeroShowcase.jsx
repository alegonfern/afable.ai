import React, { useState, useEffect, useRef } from 'react';

/* ═══════════════════════════════════════════════════════════════
   HeroShowcase — carrusel bajo el hero (estilo littlebird):
   tabs pill + tarjeta grande que muestra 3 funciones reales:
   1. Conversaciones (animado: alguien le escribe a un agente y responde)
   2. Personas y accesos
   3. Disparadores
   Los slides replican la interfaz de la app EN MODO CLARO
   (bg #f7f7f5, ventana blanca, rombo ◆ + V, índigo #586AD0).
   ═══════════════════════════════════════════════════════════════ */

const MONO = '"JetBrains Mono","Fira Code","Cascadia Code","Courier New",monospace';
const INDIGO = '#586AD0';
const INK = 'rgba(17,17,17,0.88)';
const MUTED = 'rgba(17,17,17,0.5)';
const FAINT = 'rgba(17,17,17,0.35)';
const LINE = 'rgba(17,17,17,0.09)';

/* ─── Chrome compartido: canvas + ventana como la app (tema claro) ─── */

function Canvas({ children, height = 560 }) {
  return (
    <div style={{
      position: 'relative', width: '100%', height,
      background: '#f7f7f5',
      backgroundImage: 'radial-gradient(circle, rgba(17,17,17,0.06) 1px, transparent 1px)',
      backgroundSize: '24px 24px',
      borderRadius: 16, overflow: 'hidden',
      border: '1px solid rgba(17,17,17,0.06)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: 24,
    }}>
      {children}
    </div>
  );
}

function AppWindow({ title, width = 520, children, footer }) {
  return (
    <div style={{
      width: '100%', maxWidth: width,
      display: 'flex', flexDirection: 'column',
      background: '#ffffff',
      border: '1px solid rgba(88,106,208,0.4)',
      borderRadius: 10,
      boxShadow: '0 12px 44px rgba(33,30,23,0.14), 0 0 0 1px rgba(88,106,208,0.08)',
      overflow: 'hidden',
    }}>
      <div style={{
        height: 40, flexShrink: 0,
        display: 'flex', alignItems: 'center',
        padding: '0 10px', gap: 8,
        background: 'rgba(88,106,208,0.06)',
        borderBottom: `1px solid ${LINE}`,
      }}>
        <div style={{
          width: 7, height: 7, flexShrink: 0, background: INDIGO,
          transform: 'rotate(45deg)', borderRadius: 1.5,
          boxShadow: '0 0 6px rgba(88,106,208,0.45)',
        }} />
        <span style={{
          fontSize: 10, fontWeight: 700, letterSpacing: '0.06em',
          color: INDIGO, textTransform: 'uppercase', fontFamily: MONO,
        }}>V</span>
        <span style={{
          flex: 1, fontSize: 12, fontWeight: 500, color: INK,
          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', textAlign: 'center',
        }}>{title}</span>
        <div style={{ display: 'flex', gap: 4, flexShrink: 0 }}>
          {['—', '×'].map((c) => (
            <span key={c} style={{
              width: 24, height: 18, display: 'flex', alignItems: 'center', justifyContent: 'center',
              border: '1px solid rgba(17,17,17,0.14)', borderRadius: 4,
              color: FAINT, fontSize: 11, lineHeight: 1,
            }}>{c}</span>
          ))}
        </div>
      </div>
      <div style={{ flex: 1, overflowY: 'auto', padding: '14px 16px' }}>{children}</div>
      {footer}
    </div>
  );
}

/* ─── Piezas del chat (mismas de la app, tema claro) ─── */

function BotIcon() {
  return (
    <div style={{
      width: 24, height: 24, borderRadius: 7, flexShrink: 0, marginTop: 2,
      background: `linear-gradient(135deg,${INDIGO},#2F42A6)`,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      <svg width="13" height="13" viewBox="0 0 512 512" fill="none" stroke="#fff" aria-hidden="true">
        <circle cx="256" cy="256" r="57" strokeWidth="44" />
        <g strokeLinecap="round" strokeWidth="48">
          {[0, 45, 90, 135, 180, 225, 270, 315].map((deg) => (
            <line key={deg} x1="256" y1="137" x2="256" y2="49" transform={`rotate(${deg} 256 256)`} />
          ))}
        </g>
      </svg>
    </div>
  );
}

function UserMsg({ children }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
      <div style={{
        background: INDIGO, color: '#fff',
        borderRadius: '14px 14px 4px 14px',
        padding: '7px 13px', fontSize: 12.5, maxWidth: '82%', lineHeight: 1.5,
      }}>{children}</div>
    </div>
  );
}

function BotMsg({ children }) {
  return (
    <div style={{ display: 'flex', gap: 9, alignItems: 'flex-start' }}>
      <BotIcon />
      <div style={{
        flex: 1, minWidth: 0,
        background: 'rgba(17,17,17,0.02)',
        border: `1px solid ${LINE}`,
        borderRadius: 12, padding: '10px 13px',
        fontSize: 12.5, color: INK, lineHeight: 1.55,
      }}>{children}</div>
    </div>
  );
}

/* ─── Slide 1: Chat animado (escribe → pasos → respuesta) ─── */

const QUESTION = '¿Cuánto vendimos esta semana?';
const STEPS = ['Conectando a Odoo ERP', 'Consultando facturas', 'Cruzando con la semana anterior'];

// Fases del loop: typing → sent → step0..2 → answer → hold → reinicio
function ChatSlide({ active }) {
  const [typed, setTyped] = useState('');
  const [sent, setSent] = useState(false);
  const [stepsShown, setStepsShown] = useState(0);
  const [answered, setAnswered] = useState(false);
  const timers = useRef([]);

  useEffect(() => {
    if (!active) return undefined;
    let cancelled = false;
    const t = (fn, ms) => { const id = setTimeout(() => { if (!cancelled) fn(); }, ms); timers.current.push(id); };

    const run = () => {
      setTyped(''); setSent(false); setStepsShown(0); setAnswered(false);
      // tipeo del mensaje
      QUESTION.split('').forEach((_, i) => t(() => setTyped(QUESTION.slice(0, i + 1)), 400 + i * 55));
      const afterTyping = 400 + QUESTION.length * 55;
      t(() => setSent(true), afterTyping + 350);
      STEPS.forEach((_, i) => t(() => setStepsShown(i + 1), afterTyping + 950 + i * 650));
      t(() => setAnswered(true), afterTyping + 950 + STEPS.length * 650 + 450);
      t(run, afterTyping + 950 + STEPS.length * 650 + 450 + 6000); // hold y reinicio
    };
    run();

    return () => {
      cancelled = true;
      timers.current.forEach(clearTimeout);
      timers.current = [];
    };
  }, [active]);

  return (
    <Canvas>
      <AppWindow
        title="@ventas · esta semana"
        footer={(
          <div style={{ padding: '8px 12px 10px', flexShrink: 0 }}>
            <div style={{
              display: 'flex', alignItems: 'center', gap: 8,
              background: 'rgba(17,17,17,0.03)',
              border: '1px solid rgba(17,17,17,0.11)',
              borderRadius: 10, padding: '7px 12px',
            }}>
              <span style={{ flex: 1, fontSize: 12, color: sent || !typed ? FAINT : INK }}>
                {sent || !typed ? 'Escribe un mensaje... (Enter para enviar)' : (
                  <>{typed}<span className="lp-caret" /></>
                )}
              </span>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={INDIGO} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M22 2 11 13" /><path d="M22 2 15 22 11 13 2 9 22 2Z" />
              </svg>
            </div>
          </div>
        )}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 9, minHeight: 330 }}>
          <BotMsg>Soy @ventas. Pregúntame por facturación, clientes o metas del mes — respondo con los datos reales de tus sistemas.</BotMsg>
          {sent && <UserMsg>{QUESTION}</UserMsg>}
          {stepsShown > 0 && (
            <BotMsg>
              <div style={{ fontFamily: MONO, fontSize: 10.5, color: MUTED, display: 'flex', flexDirection: 'column', gap: 3 }}>
                {STEPS.slice(0, stepsShown).map((s, i) => (
                  <div key={s}>
                    {i < stepsShown - 1 || answered
                      ? <span style={{ color: '#059669' }}>✓</span>
                      : <span className="lp-dot-pulse" style={{ color: INDIGO }}>●</span>} {s}
                  </div>
                ))}
              </div>
              {answered && (
                <>
                  <div style={{ fontWeight: 700, fontSize: 13, margin: '9px 0 0', color: '#111' }}>
                    Ventas de la semana: $48,2M <span style={{ color: '#059669', fontWeight: 600, fontSize: 11.5 }}>+12% vs semana pasada</span>
                  </div>
                  <p style={{ margin: '8px 0 0' }}>
                    62 facturas emitidas. El lunes fue el día más fuerte ($11,4M). ¿Quieres el detalle por producto?
                  </p>
                  <div style={{ marginTop: 8, fontSize: 10, fontStyle: 'italic', color: FAINT }}>
                    ⛁ Fuente: Comercial › Odoo·facturas · consultado recién
                  </div>
                </>
              )}
            </BotMsg>
          )}
        </div>
      </AppWindow>
    </Canvas>
  );
}

/* ─── Slide 2: Equipos y roles ─── */

function RoleChip({ children, dim }) {
  return (
    <span style={{
      fontSize: 10.5, fontFamily: MONO,
      color: dim ? MUTED : INDIGO,
      background: dim ? 'rgba(17,17,17,0.04)' : 'rgba(88,106,208,0.1)',
      border: `1px solid ${dim ? 'rgba(17,17,17,0.12)' : 'rgba(88,106,208,0.35)'}`,
      borderRadius: 999, padding: '3px 9px', whiteSpace: 'nowrap',
    }}>{children}</span>
  );
}

function TeamSlide() {
  const members = [
    { init: 'PA', name: 'Paula Andrade', role: 'Admin', sees: ['Todas las Fuentes'] },
    { init: 'CM', name: 'Carla Mena', role: 'Editor', sees: ['Finanzas', 'Comercial'] },
    { init: 'JR', name: 'Jorge Rojas', role: 'Miembro', sees: ['Comercial'] },
    { init: 'DL', name: 'Diego Lara', role: 'Miembro', sees: ['Inventario'] },
  ];
  return (
    <Canvas>
      <AppWindow title="Admin › Personas" width={560}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <span style={{ fontSize: 11.5, color: MUTED, fontFamily: MONO }}>4 miembros</span>
          <span style={{
            fontSize: 12, fontWeight: 600, color: '#fff',
            background: INDIGO, borderRadius: 7, padding: '5px 12px',
          }}>+ Invitar miembros</span>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {members.map((m, i) => (
            <div key={m.name} style={{
              display: 'flex', alignItems: 'center', gap: 11,
              padding: '11px 8px',
              borderBottom: i < members.length - 1 ? `1px solid ${LINE}` : 'none',
              background: i === 1 ? 'rgba(88,106,208,0.05)' : 'transparent',
              borderRadius: i === 1 ? 8 : 0,
            }}>
              <span style={{
                width: 30, height: 30, borderRadius: '50%', flexShrink: 0,
                background: 'rgba(88,106,208,0.12)', color: INDIGO,
                fontSize: 10.5, fontWeight: 700,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>{m.init}</span>
              <span style={{ flex: 1, fontSize: 12.5, color: INK }}>{m.name}</span>
              <RoleChip dim>{m.role}</RoleChip>
              <div style={{ display: 'flex', gap: 5 }}>
                {m.sees.map((s) => <RoleChip key={s}>{s}</RoleChip>)}
              </div>
            </div>
          ))}
        </div>
        <div style={{
          marginTop: 12, fontSize: 11, color: MUTED,
          display: 'flex', alignItems: 'center', gap: 6,
        }}>
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <rect x="3" y="11" width="18" height="11" rx="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" />
          </svg>
          Cada persona accede solo a las Fuentes que tiene asignadas — y sus agentes también.
        </div>
      </AppWindow>
    </Canvas>
  );
}

/* ─── Slide 3: Disparadores ─── */

function Toggle({ on }) {
  return (
    <span style={{
      width: 30, height: 17, borderRadius: 999, flexShrink: 0,
      background: on ? INDIGO : 'rgba(17,17,17,0.18)',
      position: 'relative', display: 'inline-block', transition: 'background 0.2s',
    }}>
      <span style={{
        position: 'absolute', top: 2, left: on ? 15 : 2,
        width: 13, height: 13, borderRadius: '50%', background: '#fff',
        transition: 'left 0.2s',
        boxShadow: '0 1px 2px rgba(0,0,0,0.15)',
      }} />
    </span>
  );
}

function SelectBox({ label, value }) {
  return (
    <div style={{ flex: 1, minWidth: 0 }}>
      <div style={{ fontSize: 10, fontFamily: MONO, letterSpacing: '0.06em', textTransform: 'uppercase', color: MUTED, marginBottom: 5 }}>
        {label}
      </div>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8,
        background: '#fff', border: '1px solid rgba(17,17,17,0.14)',
        borderRadius: 8, padding: '8px 11px', fontSize: 12, color: INK,
      }}>
        <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{value}</span>
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="rgba(17,17,17,0.4)" strokeWidth="2" aria-hidden="true">
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </div>
    </div>
  );
}

function AutomationSlide() {
  const existing = [
    { icon: '🗓️', name: '@ventas · resumen diario', meta: 'programado · 08:00', on: true },
    { icon: '🔔', name: '@stock · quiebre de inventario', meta: 'evento · Odoo', on: true },
  ];
  return (
    <Canvas>
      <AppWindow title="Disparadores" width={560}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 14 }}>
          {existing.map((a) => (
            <div key={a.name} style={{
              display: 'flex', alignItems: 'center', gap: 10,
              background: 'rgba(17,17,17,0.02)', border: `1px solid ${LINE}`,
              borderRadius: 10, padding: '10px 12px',
            }}>
              <span style={{ fontSize: 15 }}>{a.icon}</span>
              <span style={{ flex: 1, fontSize: 12.5, color: INK }}>
                {a.name} <span style={{ color: MUTED, fontSize: 11.5 }}>· {a.meta}</span>
              </span>
              <Toggle on={a.on} />
            </div>
          ))}
        </div>

        <div style={{
          background: 'rgba(88,106,208,0.04)', border: '1px dashed rgba(88,106,208,0.45)',
          borderRadius: 12, padding: '13px 14px',
        }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: INDIGO, marginBottom: 11 }}>
            + Nuevo disparador
          </div>
          <div style={{ marginBottom: 10 }}>
            <div style={{ fontSize: 10, fontFamily: MONO, letterSpacing: '0.06em', textTransform: 'uppercase', color: MUTED, marginBottom: 5 }}>
              Encárgale al agente
            </div>
            <div style={{
              background: '#fff', border: '1px solid rgba(17,17,17,0.14)',
              borderRadius: 8, padding: '8px 11px', fontSize: 12, color: INK,
            }}>
              "Resume las ventas de la semana y publica el detalle por vendedor"
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 10 }}>
            <SelectBox label="Cuándo" value="Cada 6 horas" />
            <SelectBox label="Entrega" value="Sala Comercial" />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 13 }}>
            <span style={{ fontSize: 11, color: MUTED }}>
              Sin programar — lo describes y el agente lo hace.
            </span>
            <span style={{
              fontSize: 12, fontWeight: 600, color: '#fff',
              background: INDIGO, borderRadius: 7, padding: '6px 14px',
            }}>Activar</span>
          </div>
        </div>
      </AppWindow>
    </Canvas>
  );
}

/* ─── Carrusel principal ─── */

const SLIDES = [
  {
    key: 'conversaciones',
    tab: 'Conversaciones',
    caption: 'Llamas al agente con @su-nombre y responde con los datos reales de tu empresa, citando la fuente.',
  },
  {
    key: 'personas',
    tab: 'Personas y accesos',
    caption: 'Cada persona entra solo a las Fuentes que le corresponden — y sus agentes también.',
  },
  {
    key: 'disparadores',
    tab: 'Disparadores',
    caption: 'Un horario, un webhook o un evento ponen al agente a trabajar sin que nadie se lo pida.',
  },
];

const AUTO_ADVANCE_MS = 12000;

export default function HeroShowcase() {
  const [active, setActive] = useState(0);
  const timer = useRef(null);

  useEffect(() => {
    timer.current = setInterval(() => setActive((a) => (a + 1) % SLIDES.length), AUTO_ADVANCE_MS);
    return () => clearInterval(timer.current);
  }, []);

  const select = (i) => {
    setActive(i);
    clearInterval(timer.current);
    timer.current = setInterval(() => setActive((a) => (a + 1) % SLIDES.length), AUTO_ADVANCE_MS);
  };

  return (
    <div>
      <div className="lp-showcase-bar">
        <div className="lp-tabs" role="tablist">
          {SLIDES.map((s, i) => (
            <button
              key={s.key}
              role="tab"
              aria-selected={i === active}
              className={`lp-tab${i === active ? ' active' : ''}`}
              onClick={() => select(i)}
            >
              {s.tab}
            </button>
          ))}
        </div>
        <p className="lp-showcase-caption">{SLIDES[active].caption}</p>
      </div>

      <div className="lp-stage-card">
        {active === 0 && <ChatSlide active={active === 0} />}
        {active === 1 && <TeamSlide />}
        {active === 2 && <AutomationSlide />}
      </div>
    </div>
  );
}
