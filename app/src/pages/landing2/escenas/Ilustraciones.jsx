import { useReducedMotion } from 'framer-motion';

/*
 * Ilustraciones de "Dos formas de usar Afable" (11-11-2026, landing principal). Dibujos planos y
 * minimalistas en los colores de Afable (negro, blanco y grises cálidos), con trazo de tinta redondeado y una animación lenta en bucle (SMIL, sin
 * librerías). Con "reducir movimiento" quedan quietas.
 *
 *   SinSistema: papeles sueltos que pasan, por un camino punteado, a una ventana ordenada donde se
 *               van marcando las tareas.
 *   ConErp:     el ERP que ya existe (bloques apilados) conectado por un cable al isotipo de
 *               Afable; por el cable viaja la IA y el engranaje del ERP empieza a girar solo.
 */

// Los colores de Afable: el negro del logo, blanco y los grises cálidos de la landing (--fog, --borde…).
const C = {
  tinta: '#0b0b0f',
  marfil: '#f6f6f4',
  arena: '#e6e5e2',
  arcilla: '#0b0b0f',
  oliva: '#8e8e93',
  cielo: '#c9c8c4',
  durazno: '#ebeae7',
};

// Color (11-11-2026): el fondo de cada forma lleva un pastel de los estados de la app (verde de
// "Conciliado", durazno de "Por confirmar", celeste de "Emitida"); las líneas y el isotipo siguen negros.
// El verde de los checks es el mismo --ok de la app: significa "listo".
const TONOS = {
  verde: { fondo: '#d7ede0', claro: '#e9f6ee', oscuro: '#bfe0cd' },
  durazno: { fondo: '#fbe1d1', claro: '#fdefe6', oscuro: '#f5ccb3' },
  celeste: { fondo: '#d3e3fc', claro: '#e6effe', oscuro: '#bcd3f7' },
};
C.verde = '#007956';

const trazo = { stroke: C.tinta, strokeWidth: 2.5, strokeLinecap: 'round', strokeLinejoin: 'round' };

// El asterisco del isotipo de Afable (cuatro barras rectas, proporción 72×430), centrado en (0,0).
function Asterisco({ r = 14, color = C.tinta }) {
  const w = r * 0.335;
  return (
    <g fill={color}>
      {[0, 45, 90, 135].map((a) => (
        <rect key={a} x={-w / 2} y={-r} width={w} height={r * 2} transform={`rotate(${a})`} />
      ))}
    </g>
  );
}

// El isotipo de Afable: baldosa negra con el asterisco calado (como LogoNegro), de lado `s`, centrado en (0,0).
// El asterisco gira lento dentro de la baldosa, como el asterisco de la esquina de la landing.
export function Isotipo({ s, quieto, dur = '14s' }) {
  return (
    <g>
      <rect x={-s / 2} y={-s / 2} width={s} height={s} rx={s * 0.225} fill={C.tinta} />
      <g>
        {!quieto && <animateTransform attributeName="transform" type="rotate" from="0" to="360" dur={dur} repeatCount="indefinite" />}
        <Asterisco r={s * 0.331} color="#fff" />
      </g>
    </g>
  );
}

// Un papel suelto que se balancea.
function Papel({ x, y, rot, fondo, quieto, dur }) {
  return (
    <g transform={`translate(${x} ${y}) rotate(${rot})`}>
      <g>
        {!quieto && (
          <animateTransform attributeName="transform" type="rotate" values="-4;4;-4" dur={dur} repeatCount="indefinite" />
        )}
        <rect x="-30" y="-38" width="60" height="76" rx="6" fill={fondo} {...trazo} />
        <path d="M-18 -20 H18 M-18 -8 H12 M-18 4 H16" {...trazo} strokeWidth="2" fill="none" />
      </g>
    </g>
  );
}

export function SinSistema() {
  const quieto = useReducedMotion();
  const filas = [
    { y: 128, color: C.verde, inicio: 0 },
    { y: 162, color: C.verde, inicio: 0.25 },
    { y: 196, color: C.verde, inicio: 0.5 },
  ];
  return (
    <svg viewBox="0 0 480 300" width="100%" height="100%" preserveAspectRatio="xMidYMid slice" role="img" aria-label="Papeles sueltos que pasan a una ventana ordenada">
      <rect width="480" height="300" fill={TONOS.verde.fondo} />
      {/* Manchas de color de fondo */}
      <circle cx="96" cy="230" r="70" fill={TONOS.verde.claro} />
      <circle cx="390" cy="70" r="54" fill={TONOS.verde.oscuro} />

      {/* Papeles sueltos */}
      <Papel x={78} y={118} rot={-14} fondo="#fff" quieto={quieto} dur="5s" />
      <Papel x={120} y={160} rot={9} fondo={C.arena} quieto={quieto} dur="6.5s" />
      <Papel x={70} y={196} rot={-4} fondo="#fff" quieto={quieto} dur="5.8s" />

      {/* Camino punteado hacia la ventana */}
      <path d="M160 150 C 200 100, 228 210, 268 152" fill="none" {...trazo} strokeDasharray="2 10">
        {!quieto && <animate attributeName="stroke-dashoffset" from="24" to="0" dur="1.2s" repeatCount="indefinite" />}
      </path>
      <path d="M258 144 L270 152 L258 162" fill="none" {...trazo} />

      {/* La ventana ordenada */}
      <rect x="284" y="78" width="160" height="160" rx="14" fill="#fff" {...trazo} />
      <path d="M284 104 H444" {...trazo} />
      <circle cx="300" cy="91" r="3.5" fill={C.arcilla} />
      <circle cx="313" cy="91" r="3.5" fill={C.oliva} />
      <circle cx="326" cy="91" r="3.5" fill={C.cielo} />
      {filas.map((f) => (
        <g key={f.y}>
          <rect x="300" y={f.y - 9} width="18" height="18" rx="5" fill={f.color} {...trazo} strokeWidth="2">
            {!quieto && (
              <animate attributeName="opacity" values="0;0;1;1;0" keyTimes={`0;${f.inicio};${f.inicio + 0.1};0.9;1`}
                dur="6s" repeatCount="indefinite" />
            )}
          </rect>
          <path d={`M304 ${f.y} l3.5 3.5 l6 -7`} fill="none" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            {!quieto && (
              <animate attributeName="opacity" values="0;0;1;1;0" keyTimes={`0;${f.inicio};${f.inicio + 0.1};0.9;1`}
                dur="6s" repeatCount="indefinite" />
            )}
          </path>
          <path d={`M330 ${f.y} H${f.y === 162 ? 404 : 420}`} {...trazo} strokeWidth="2" fill="none" />
        </g>
      ))}

      {/* El isotipo de Afable en la esquina de la ventana */}
      <g transform="translate(444 238)">
        <Isotipo s={44} quieto={quieto} dur="12s" />
      </g>
    </svg>
  );
}

// Un destello de cuatro puntas que late.
function Destello({ x, y, s = 1, color, quieto, retraso }) {
  return (
    <g transform={`translate(${x} ${y}) scale(${s})`}>
      <path d="M0 -12 C 2 -3, 3 -2, 12 0 C 3 2, 2 3, 0 12 C -2 3, -3 2, -12 0 C -3 -2, -2 -3, 0 -12 Z" fill={color}>
        {!quieto && (
          <animateTransform attributeName="transform" type="scale" values="0.6;1.1;0.6" dur="2.4s" begin={retraso} repeatCount="indefinite" />
        )}
      </path>
    </g>
  );
}

export function ConErp() {
  const quieto = useReducedMotion();
  const cable = 'M196 150 C 250 150, 262 222, 318 196 S 352 150, 356 150';
  return (
    <svg viewBox="0 0 480 300" width="100%" height="100%" preserveAspectRatio="xMidYMid slice" role="img" aria-label="Un ERP conectado por un cable a la IA de Afable">
      <rect width="480" height="300" fill={TONOS.durazno.fondo} />
      <circle cx="80" cy="60" r="60" fill={TONOS.durazno.claro} />
      <circle cx="420" cy="250" r="72" fill={TONOS.durazno.oscuro} />

      {/* El ERP que ya existe: bloques apilados */}
      {[
        { y: 92, fondo: C.cielo },
        { y: 136, fondo: '#fff' },
        { y: 180, fondo: C.arena },
      ].map((b) => (
        <g key={b.y}>
          <rect x="70" y={b.y} width="126" height="38" rx="9" fill={b.fondo} {...trazo} />
          <circle cx="90" cy={b.y + 19} r="4" fill={C.tinta} />
          <path d={`M106 ${b.y + 19} H170`} {...trazo} strokeWidth="2" fill="none" />
        </g>
      ))}

      {/* Engranaje del ERP: gira solo, como las tareas repetitivas */}
      <g transform="translate(70 92)">
        <g>
          {!quieto && <animateTransform attributeName="transform" type="rotate" from="0" to="360" dur="8s" repeatCount="indefinite" />}
          <circle r="17" fill={C.oliva} {...trazo} />
          {[0, 60, 120, 180, 240, 300].map((a) => (
            <rect key={a} x="-4" y="-25" width="8" height="10" rx="2" fill={C.oliva} {...trazo} strokeWidth="2" transform={`rotate(${a})`} />
          ))}
          <circle r="6" fill={TONOS.durazno.fondo} {...trazo} strokeWidth="2" />
        </g>
      </g>

      {/* El cable con el enchufe */}
      <path d={cable} fill="none" {...trazo} strokeWidth="3" />
      <rect x="190" y="141" width="14" height="18" rx="3" fill={C.tinta} />
      {!quieto && (
        <circle r="6" fill={C.arcilla} stroke="#fff" strokeWidth="2">
          <animateMotion dur="2.6s" repeatCount="indefinite" keyPoints="1;0" keyTimes="0;1" calcMode="linear" path={cable} />
        </circle>
      )}

      {/* Afable: el isotipo */}
      <g transform="translate(392 150)">
        <Isotipo s={76} quieto={quieto} />
      </g>

      {/* Destellos: el upgrade */}
      <Destello x={214} y={88} s={1.1} color={C.tinta} quieto={quieto} retraso="0s" />
      <Destello x={238} y={116} s={0.6} color={C.arcilla} quieto={quieto} retraso="0.8s" />
      <Destello x={60} y={246} s={0.8} color={C.cielo} quieto={quieto} retraso="1.4s" />
    </svg>
  );
}

/*
 * ConApps: una página que se arma sola con tus datos. Las barras del gráfico crecen, las filas de la
 * tabla aparecen una a una y el isotipo de Afable la va construyendo.
 */
export function ConApps() {
  const quieto = useReducedMotion();
  const barras = [
    { x: 120, alto: 46, inicio: 0 },
    { x: 146, alto: 70, inicio: 0.08 },
    { x: 172, alto: 34, inicio: 0.16 },
    { x: 198, alto: 86, inicio: 0.24 },
  ];
  const filas = [
    { y: 196, inicio: 0.35 },
    { y: 216, inicio: 0.45 },
    { y: 236, inicio: 0.55 },
  ];
  const aparecer = (inicio) => (quieto ? null : (
    <animate attributeName="opacity" values="0;0;1;1;0" keyTimes={`0;${inicio};${inicio + 0.08};0.92;1`}
      dur="7s" repeatCount="indefinite" />
  ));
  return (
    <svg viewBox="0 0 480 300" width="100%" height="100%" preserveAspectRatio="xMidYMid slice" role="img" aria-label="Una página que se arma con tus datos">
      <rect width="480" height="300" fill={TONOS.celeste.fondo} />
      <circle cx="420" cy="60" r="64" fill={TONOS.celeste.oscuro} />
      <circle cx="60" cy="260" r="58" fill={TONOS.celeste.claro} />

      {/* La página */}
      <rect x="96" y="48" width="288" height="216" rx="14" fill="#fff" {...trazo} />
      <path d="M96 74 H384" {...trazo} />
      <circle cx="112" cy="61" r="3.5" fill={C.tinta} />
      <circle cx="125" cy="61" r="3.5" fill={C.oliva} />
      <circle cx="138" cy="61" r="3.5" fill={C.cielo} />

      {/* Gráfico de barras */}
      <path d="M112 176 H232" {...trazo} strokeWidth="2" />
      {barras.map((b) => (
        <rect key={b.x} x={b.x} y={176 - b.alto} width="18" height={b.alto} rx="3"
          fill={b.x === 198 ? C.tinta : C.cielo} {...trazo} strokeWidth="2">
          {aparecer(b.inicio)}
        </rect>
      ))}

      {/* Tarjeta con una cifra */}
      <rect x="252" y="90" width="116" height="86" rx="10" fill={C.marfil} {...trazo} strokeWidth="2" />
      <path d="M266 112 H318" {...trazo} strokeWidth="2" />
      <path d="M266 142 H348" stroke={C.tinta} strokeWidth="9" strokeLinecap="round">{aparecer(0.2)}</path>
      <path d="M266 160 H300" {...trazo} strokeWidth="2" />

      {/* Tabla */}
      {filas.map((f) => (
        <g key={f.y}>
          {aparecer(f.inicio)}
          <rect x="112" y={f.y - 7} width="14" height="14" rx="4" fill={C.arena} {...trazo} strokeWidth="1.8" />
          <path d={`M136 ${f.y} H268`} {...trazo} strokeWidth="2" />
          <path d={`M300 ${f.y} H352`} {...trazo} strokeWidth="2" />
        </g>
      ))}

      {/* El isotipo de Afable, que arma la página */}
      <g transform="translate(384 264)">
        <Isotipo s={48} quieto={quieto} dur="12s" />
      </g>
      <Destello x={74} y={92} s={0.9} color={C.tinta} quieto={quieto} retraso="0.4s" />
      <Destello x={428} y={150} s={0.6} color={C.oliva} quieto={quieto} retraso="1.2s" />
    </svg>
  );
}
