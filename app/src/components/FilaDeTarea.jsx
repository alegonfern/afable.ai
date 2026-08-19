import { useState } from 'react';
import {
  Alert, Box, Chip, CircularProgress, IconButton, MenuItem, Select, Stack, Typography,
  useTheme,
} from '@mui/material';
import { Play, Trash2 } from 'lucide-react';
import { Link } from 'react-router-dom';

/**
 * Cómo se ve una tarea. Uno solo, usado por la Sesión y por la lista de pendientes.
 *
 * Está afuera de las dos pantallas porque son la misma cosa mirada desde dos lados: dentro
 * de una Sesión, y cruzando todas. Con la fila duplicada, cualquier arreglo —el ▷ que solo
 * aparece con agente, el resultado desplegable— habría que hacerlo dos veces, y a la
 * segunda no se hace.
 *
 * `mostrarSesion` agrega de qué Sesión es, con enlace. Adentro de una Sesión ese dato es el
 * encabezado de la pantalla y repetirlo en cada fila sería ruido.
 */

export const ESTADOS = [
  { value: 'pendiente', label: 'Pendiente' },
  { value: 'en_curso', label: 'En curso' },
  { value: 'lista', label: 'Lista' },
];

export const COLOR_DE_ESTADO = {
  pendiente: { fg: '#f0b429', bg: 'rgba(240, 180, 41, 0.14)' },
  en_curso: { fg: '#586AD0', bg: 'rgba(88, 106, 208, 0.16)' },
  lista: { fg: '#34D399', bg: 'rgba(52, 211, 153, 0.14)' },
};

export default function FilaDeTarea({
  tarea, agentes = [], corriendo = false, mostrarSesion = false,
  onCambiar, onBorrar, onEjecutar,
}) {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const textMuted = d ? 'rgba(255,255,255,0.66)' : 'rgba(0,0,0,0.62)';
  const bgSuave = d ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.02)';
  const borde = theme.palette.divider;

  const [abierta, setAbierta] = useState(false);
  const t = tarea;
  const color = COLOR_DE_ESTADO[t.state] || COLOR_DE_ESTADO.pendiente;

  return (
    <Box sx={{
      p: 1.75, borderRadius: '10px', bgcolor: bgSuave, border: `1px solid ${borde}`,
      opacity: t.state === 'lista' ? 0.78 : 1,
    }}>
      <Stack direction="row" spacing={1.25} alignItems="flex-start">
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography sx={{
            fontSize: '0.9375rem', fontWeight: 600,
            textDecoration: t.state === 'lista' ? 'line-through' : 'none',
          }}>
            {t.title}
          </Typography>
          {t.description && (
            <Typography sx={{ fontSize: '0.875rem', color: textMuted, mt: 0.4 }}>
              {t.description}
            </Typography>
          )}
          <Stack direction="row" spacing={0.75} sx={{ mt: 1, flexWrap: 'wrap', gap: 0.75 }}>
            <Chip
              size="small" label={ESTADOS.find((e) => e.value === t.state)?.label || t.state}
              sx={{ bgcolor: color.bg, color: color.fg, fontWeight: 600, fontSize: '0.75rem' }}
            />
            {/* La Sesión va como enlace y no como etiqueta: quien mira sus pendientes
                quiere ir al trabajo donde está la tarea, no solo saber su nombre. */}
            {mostrarSesion && t.sesion && (
              <Chip
                size="small" variant="outlined" clickable
                component={Link} to={`/app/sesiones/${t.sesion.slug}?tab=tareas`}
                label={t.sesion.name}
                sx={{ fontSize: '0.75rem', borderColor: '#586AD0', color: '#9BA6E3' }}
              />
            )}
            {t.assignee_name && (
              <Chip size="small" variant="outlined"
                label={t.es_mia ? 'usted' : t.assignee_name} sx={{ fontSize: '0.75rem' }} />
            )}
            {t.agent_name && (
              <Chip size="small" variant="outlined" label={`@ ${t.agent_name}`} sx={{ fontSize: '0.75rem' }} />
            )}
          </Stack>
        </Box>

        <Select
          size="small" value={t.state}
          onChange={(e) => onCambiar(t, { state: e.target.value })}
          sx={{ fontSize: '0.8rem', minWidth: 118 }}
        >
          {ESTADOS.map((e) => (
            <MenuItem key={e.value} value={e.value} sx={{ fontSize: '0.8rem' }}>{e.label}</MenuItem>
          ))}
        </Select>

        <Select
          size="small" displayEmpty value={t.agent || ''}
          onChange={(e) => onCambiar(t, { agent: e.target.value || null })}
          sx={{ fontSize: '0.8rem', minWidth: 150 }}
        >
          <MenuItem value="" sx={{ fontSize: '0.8rem' }}>Sin agente</MenuItem>
          {agentes.map((a) => (
            <MenuItem key={a.id} value={a.id} sx={{ fontSize: '0.8rem' }}>{a.name}</MenuItem>
          ))}
        </Select>

        {/* Solo con agente: el botón sin agente no puede hacer nada, y ofrecerlo para
            que devuelva un error es peor que no estar. */}
        {t.agent && (
          <IconButton
            onClick={() => onEjecutar(t)} disabled={corriendo}
            title={`Pedirle a ${t.agent_name} que la haga`} size="small"
          >
            {corriendo
              ? <CircularProgress size={16} sx={{ color: '#586AD0' }} />
              : <Play size={15} />}
          </IconButton>
        )}
        <IconButton onClick={() => onBorrar(t)} title="Borrar la tarea" size="small">
          <Trash2 size={15} />
        </IconButton>
      </Stack>

      {t.resultado_error && (
        <Alert severity="warning" sx={{ mt: 1.25, fontSize: '0.82rem' }}>
          {t.resultado_error}
        </Alert>
      )}

      {t.resultado && (
        <Box sx={{ mt: 1.25 }}>
          <Box
            component="button"
            onClick={() => setAbierta(!abierta)}
            sx={{
              border: 'none', bgcolor: 'transparent', p: 0, cursor: 'pointer',
              fontFamily: 'inherit', fontSize: '0.8125rem', fontWeight: 600,
              color: '#9BA6E3', '&:hover': { textDecoration: 'underline' },
            }}
          >
            {abierta ? 'Ocultar lo que hizo' : `Ver lo que hizo ${t.agent_name || 'el agente'}`}
          </Box>
          {abierta && (
            <Typography sx={{
              fontSize: '0.875rem', mt: 1, p: 1.5, whiteSpace: 'pre-wrap',
              borderRadius: '8px', border: `1px solid ${borde}`,
              bgcolor: theme.palette.background.paper,
            }}>
              {t.resultado}
            </Typography>
          )}
        </Box>
      )}
    </Box>
  );
}
