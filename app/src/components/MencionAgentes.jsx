import { useCallback, useEffect, useRef, useState } from 'react';
import { Box, Typography, useTheme } from '@mui/material';
import { Bot, User } from 'lucide-react';

// La `@` cuenta como mención sólo si arranca palabra: en "correo@empresa.cl" no
// se abre nada, que es lo que uno espera al escribir un correo en el chat.
const PATRON = /(?:^|\s)@([a-z0-9-]*)$/i;

/**
 * Lee el texto hasta el cursor y dice si ahí hay una mención empezada.
 * Devuelve `{ consulta, desde }` o `null`. `desde` es la posición de la `@`,
 * que es lo que después hay que reemplazar al aceptar.
 */
export function detectarMencion(texto, cursor) {
  const antes = texto.slice(0, cursor);
  const match = antes.match(PATRON);
  if (!match) return null;
  return { consulta: match[1].toLowerCase(), desde: cursor - match[1].length - 1 };
}

/** Mete el handle elegido en el texto, dejando un espacio detrás. */
export function aplicarMencion(texto, mencion, handle) {
  const antes = texto.slice(0, mencion.desde);
  const despues = texto.slice(mencion.desde + mencion.consulta.length + 1);
  const nuevo = `${antes}@${handle} ${despues.startsWith(' ') ? despues.slice(1) : despues}`;
  return { texto: nuevo, cursor: (antes + '@' + handle + ' ').length };
}

/** Lo que matchea lo tipeado, por handle o por nombre. Agentes Y personas. */
export function filtrarAgentes(mencionables, consulta) {
  if (!consulta) return mencionables.slice(0, 6);
  const q = consulta.toLowerCase();
  return mencionables
    .filter((m) => (m.handle || '').includes(q)
      || (m.nombre || m.name || '').toLowerCase().includes(q))
    .slice(0, 6);
}

/**
 * La lista que se despliega sobre el compositor mientras se escribe `@`.
 *
 * No maneja el teclado: de eso se encarga el compositor, que es quien tiene el
 * foco. Acá sólo se dibuja y se avisa qué se eligió.
 */
export default function MencionAgentes({ agentes, indice, onElegir }) {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const contenedor = useRef(null);
  // Hacia dónde abrirse. Un compositor al pie de la pantalla necesita la lista arriba;
  // uno al tope de la página —como el de "Empezar algo en esta Sesión"— la necesita
  // abajo, o se corta contra el borde y no se ve lo que se está eligiendo.
  const [haciaArriba, setHaciaArriba] = useState(true);

  useEffect(() => {
    const caja = contenedor.current?.parentElement?.getBoundingClientRect();
    if (caja) setHaciaArriba(caja.top > 280);
  }, [agentes.length]);

  // Que el resaltado siempre quede a la vista cuando se navega con las flechas.
  useEffect(() => {
    const activo = contenedor.current?.children[indice];
    if (activo?.scrollIntoView) activo.scrollIntoView({ block: 'nearest' });
  }, [indice]);

  if (!agentes.length) return null;

  return (
    <Box
      ref={contenedor}
      sx={{
        position: 'absolute', left: 0, right: 0,
        ...(haciaArriba
          ? { bottom: 'calc(100% + 8px)' }
          : { top: 'calc(100% + 8px)' }),
        maxHeight: 240, overflowY: 'auto', zIndex: 20,
        bgcolor: d ? '#1e1e1e' : '#fff',
        border: `1px solid ${theme.palette.divider}`, borderRadius: '12px',
        boxShadow: '0 8px 24px rgba(0,0,0,0.16)', py: 0.5,
      }}
    >
      {agentes.map((a, i) => {
        const esPersona = a.tipo === 'persona';
        const cara = a.cara || {};
        return (
          <Box
            key={`${a.tipo || 'agente'}-${a.handle}`}
            onMouseDown={(e) => { e.preventDefault(); onElegir(a); }}
            sx={{
              display: 'flex', alignItems: 'center', gap: 1.25, px: 1.5, py: 0.9, cursor: 'pointer',
              bgcolor: i === indice ? (d ? 'rgba(255,255,255,0.06)' : 'rgba(88,106,208,0.08)') : 'transparent',
            }}
          >
            {/* La cara del agente, o la silueta de una persona. Se distinguen de un
                vistazo porque mencionar a un colega y mencionar a un agente hacen cosas
                muy distintas: una avisa, la otra contesta. */}
            <Box sx={{
              width: 24, height: 24, borderRadius: esPersona ? '50%' : '7px', flexShrink: 0,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 12, lineHeight: 1, color: '#fff',
              bgcolor: esPersona
                ? (d ? 'rgba(255,255,255,0.14)' : 'rgba(0,0,0,0.14)')
                : (cara.icon ? `${cara.accent}26` : (cara.accent || '#586AD0')),
              border: !esPersona && cara.icon ? `1px solid ${cara.accent}59` : 'none',
            }}>
              {esPersona
                ? <User size={12} />
                : (cara.icon || <Bot size={12} color="#fff" />)}
            </Box>
            <Box sx={{ minWidth: 0 }}>
              <Typography sx={{ fontSize: '0.82rem', fontWeight: 600, lineHeight: 1.3 }}>
                @{a.handle}
              </Typography>
              <Typography noWrap sx={{ fontSize: '0.72rem', color: 'text.secondary' }}>
                {esPersona ? a.nombre : (a.detalle || a.description || a.nombre || a.name)}
              </Typography>
            </Box>
          </Box>
        );
      })}
    </Box>
  );
}


/**
 * Todo lo que hace falta para que un compositor entienda `@`.
 *
 * ⭐ **Existe porque la lógica vivía suelta dentro de ChatPage**, así que el selector solo
 * funcionaba ahí: en el hilo de una Sesión —justo donde mencionar a una PERSONA tiene
 * sentido— escribir `@` no mostraba nada. Un mecanismo que hay que copiar a mano a cada
 * pantalla termina existiendo en una sola.
 *
 * Devuelve el estado y los tres enganches que el compositor tiene que conectar:
 * `alEscribir`, `alTeclear` y qué dibujar.
 */
export function useMenciones({ texto, setTexto, workspace, sesion, inputRef }) {
  const [mencionables, setMencionables] = useState([]);
  const [mencion, setMencion] = useState(null);
  const [indice, setIndice] = useState(0);

  useEffect(() => {
    let vivo = true;
    if (!workspace) return undefined;
    import('../services/api').then(({ api }) => {
      api.getMencionables(workspace, sesion || undefined)
        .then(({ data }) => { if (vivo) setMencionables(data.mencionables || []); })
        .catch(() => {});
    });
    return () => { vivo = false; };
  }, [workspace, sesion]);

  const sugerencias = mencion ? filtrarAgentes(mencionables, mencion.consulta) : [];

  const alEscribir = useCallback((e) => {
    const valor = e.target.value;
    setTexto(valor);
    const detectada = detectarMencion(valor, e.target.selectionStart ?? valor.length);
    setMencion(detectada);
    setIndice(0);
  }, [setTexto]);

  const elegir = useCallback((quien) => {
    if (!mencion) return;
    const { texto: nuevo, cursor } = aplicarMencion(texto, mencion, quien.handle);
    setTexto(nuevo);
    setMencion(null);
    // El cursor queda después de la mención: si volviera al final o al principio, seguir
    // escribiendo sería reacomodar el texto a mano.
    requestAnimationFrame(() => {
      const campo = inputRef?.current;
      if (campo?.setSelectionRange) {
        campo.focus();
        campo.setSelectionRange(cursor, cursor);
      }
    });
  }, [mencion, texto, setTexto, inputRef]);

  /** Devuelve true si se comió la tecla: ahí el compositor NO debe enviar. */
  const alTeclear = useCallback((e) => {
    if (!mencion || !sugerencias.length) return false;
    if (e.key === 'ArrowDown') {
      e.preventDefault(); setIndice((i) => (i + 1) % sugerencias.length); return true;
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      setIndice((i) => (i - 1 + sugerencias.length) % sugerencias.length);
      return true;
    }
    if (e.key === 'Enter' || e.key === 'Tab') {
      e.preventDefault(); elegir(sugerencias[indice]); return true;
    }
    if (e.key === 'Escape') { e.preventDefault(); setMencion(null); return true; }
    return false;
  }, [mencion, sugerencias, indice, elegir]);

  return { mencion, sugerencias, indice, alEscribir, alTeclear, elegir };
}
