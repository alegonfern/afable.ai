import { useEffect, useRef } from 'react';
import { Box, Typography, useTheme } from '@mui/material';
import { Bot } from 'lucide-react';

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

/** Los agentes que matchean lo tipeado, por handle o por nombre. */
export function filtrarAgentes(agentes, consulta) {
  if (!consulta) return agentes.slice(0, 6);
  const q = consulta.toLowerCase();
  return agentes
    .filter((a) => (a.handle || '').includes(q) || (a.name || '').toLowerCase().includes(q))
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
        position: 'absolute', bottom: 'calc(100% + 8px)', left: 0, right: 0,
        maxHeight: 240, overflowY: 'auto', zIndex: 20,
        bgcolor: d ? '#1e1e1e' : '#fff',
        border: `1px solid ${theme.palette.divider}`, borderRadius: '12px',
        boxShadow: '0 8px 24px rgba(0,0,0,0.16)', py: 0.5,
      }}
    >
      {agentes.map((a, i) => (
        <Box
          key={a.id}
          onMouseDown={(e) => { e.preventDefault(); onElegir(a); }}
          sx={{
            display: 'flex', alignItems: 'center', gap: 1.25, px: 1.5, py: 0.9, cursor: 'pointer',
            bgcolor: i === indice ? (d ? 'rgba(255,255,255,0.06)' : 'rgba(88,106,208,0.08)') : 'transparent',
          }}
        >
          <Box sx={{
            width: 24, height: 24, borderRadius: '7px', flexShrink: 0,
            background: 'linear-gradient(135deg, #586AD0 0%, #2F42A6 100%)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Bot size={12} color="#fff" />
          </Box>
          <Box sx={{ minWidth: 0 }}>
            <Typography sx={{ fontSize: '0.82rem', fontWeight: 600, lineHeight: 1.3 }}>
              @{a.handle}
            </Typography>
            <Typography noWrap sx={{ fontSize: '0.72rem', color: 'text.secondary' }}>
              {a.description || a.name}
            </Typography>
          </Box>
        </Box>
      ))}
    </Box>
  );
}
