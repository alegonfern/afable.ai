import React, { useState, useEffect } from 'react';
import { Isotipo } from './Logo';
import './HeroScene.css';

import carla from '../assets/people/carla.jpg';
import tomas from '../assets/people/tomas.jpg';
import jorge from '../assets/people/jorge.jpg';
import valentina from '../assets/people/valentina.jpg';
import diego from '../assets/people/diego.jpg';
import rocio from '../assets/people/rocio.jpg';
import paula from '../assets/people/paula.jpg';
import marco from '../assets/people/marco.jpg';

/* ═══════════════════════════════════════════════════════════════
   HeroScene — escena isométrica bajo el hero.
   Cuatro áreas de la empresa, cada una con su gente conectada;
   una pasarela central donde vive el agente, y tarjetas de chat
   que muestran la información pasando de un área a otra.

   El plano se inclina con rotateX/rotateZ; los avatares y las
   etiquetas viven dentro del plano pero se contra-rotan para
   quedar de frente. Las tarjetas de chat NO entran al plano:
   flotan encima, en espacio de pantalla.
   ═══════════════════════════════════════════════════════════════ */

const ZONES = [
  {
    key: 'comercial',
    name: 'Comercial',
    x: 0, y: 0,
    people: [
      { img: jorge, name: 'Jorge', top: '64%', left: '24%' },
      { img: valentina, name: 'Valentina', top: '26%', left: '68%' },
    ],
  },
  {
    key: 'finanzas',
    name: 'Finanzas',
    x: 310, y: 0,
    people: [
      { img: carla, name: 'Carla', top: '64%', left: '24%' },
      { img: tomas, name: 'Tomás', top: '26%', left: '68%' },
    ],
  },
  {
    key: 'operaciones',
    name: 'Operaciones',
    x: 0, y: 310,
    people: [
      { img: diego, name: 'Diego', top: '66%', left: '26%' },
      { img: rocio, name: 'Rocío', top: '28%', left: '70%' },
    ],
  },
  {
    key: 'personas',
    name: 'Personas',
    x: 310, y: 310,
    people: [
      { img: paula, name: 'Paula', top: '66%', left: '26%' },
      { img: marco, name: 'Marco', top: '28%', left: '70%' },
    ],
  },
];

/* Cada acto: una persona pregunta desde su área, un agente responde. */
const ACTS = [
  {
    ask: { who: 'Carla', area: 'Finanzas', img: carla, text: '@ventas ¿cómo venimos contra la meta de julio?' },
    answer: { agent: '@ventas', text: 'Julio cierra en $412M, +12%. Falta el 8% de la meta.', source: 'Odoo · facturas' },
  },
  {
    ask: { who: 'Jorge', area: 'Comercial', img: jorge, text: '@contratos ¿este cliente tiene descuento pactado?' },
    answer: { agent: '@contratos', text: 'Sí, 8% por volumen. Cláusula 4.1 del contrato marco.', source: 'Drive · contrato-marco.pdf' },
  },
  {
    ask: { who: 'Diego', area: 'Operaciones', img: diego, text: '@stock ¿alcanzamos a despachar el pedido grande?' },
    answer: { agent: '@stock', text: 'Quedan 82 unidades en bodega central. Alcanza, con 12 de holgura.', source: 'Odoo · inventario' },
  },
];

const ACT_MS = 5200;

function Avatar({ img, name, style }) {
  return (
    <div className="hs-avatar" style={style}>
      <div className="hs-avatar-shadow" />
      <div className="hs-avatar-pic">
        <img src={img} alt={name} />
        <span className="hs-avatar-dot" title="conectado" />
      </div>
    </div>
  );
}

export default function HeroScene() {
  const [act, setAct] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setAct((a) => (a + 1) % ACTS.length), ACT_MS);
    return () => clearInterval(id);
  }, []);

  const current = ACTS[act];

  return (
    <div className="hs-wrap" aria-label="Equipos de la empresa trabajando con agentes de Afable">
      <div className="hs-stage">
        {/* La placa base va FUERA del plano: dentro del subárbol preserve-3d
            se dibuja por encima de las tarjetas de chat. */}
        <div className="hs-base" />

        <div className="hs-plane">
          <div className="hs-walk hs-walk--h" />
          <div className="hs-walk hs-walk--v" />
          <div className="hs-flow hs-flow--h"><i /><i /><i /></div>
          <div className="hs-flow hs-flow--v"><i /><i /><i /></div>

          {ZONES.map((z) => (
            <div
              key={z.key}
              className={`hs-zone hs-zone--${z.key}`}
              style={{ left: z.x, top: z.y }}
            >
              <span className="hs-zone-label">{z.name}</span>
              {z.people.map((p) => (
                <Avatar key={p.name} img={p.img} name={p.name} style={{ top: p.top, left: p.left }} />
              ))}
            </div>
          ))}

          <div className="hs-core">
            <div className="hs-core-ring" />
            <div className="hs-core-badge">
              <Isotipo size={22} bgColor="#FFFFFF" />
              <span>Afable</span>
            </div>
          </div>
        </div>
      </div>

      {/* Tarjetas de chat — fuera del escenario 3D, en espacio de pantalla.
          Si viven dentro de .hs-stage, el subárbol preserve-3d del plano se
          compone encima de ellas por más z-index que se les ponga. */}
      <div className="hs-cards">
          <div className="hs-card hs-card--ask" key={`ask-${act}`}>
            <div className="hs-card-head">
              <img src={current.ask.img} alt={current.ask.who} />
              <span className="hs-card-who">{current.ask.who}</span>
              <span className="hs-card-area">· {current.ask.area}</span>
            </div>
            <p>{current.ask.text}</p>
          </div>

          <div className="hs-card hs-card--answer" key={`ans-${act}`}>
            <div className="hs-card-head">
              <span className="hs-card-agent">
                <Isotipo size={13} bgColor="#FFFFFF" />
              </span>
              <span className="hs-card-who">{current.answer.agent}</span>
              <span className="hs-card-area">· agente</span>
            </div>
            <p>{current.answer.text}</p>
            <span className="hs-card-source">⛁ {current.answer.source}</span>
          </div>
      </div>

      <div className="hs-legend">
        <span><i className="hs-legend-dot" /> 8 personas conectadas</span>
        <span>4 areas con sus propios Workspaces</span>
        <span>3 agentes trabajando en el mismo hilo</span>
      </div>
    </div>
  );
}
