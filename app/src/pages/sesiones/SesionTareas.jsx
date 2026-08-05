import { useCallback, useEffect, useState } from 'react';
import {
  Alert, Box, Button, Chip, CircularProgress, IconButton, MenuItem,
  Select, Stack, TextField, ToggleButton, ToggleButtonGroup, Typography, useTheme,
} from '@mui/material';
import { Play, Trash2 } from 'lucide-react';
import { api } from '../../services/api';

const ESTADOS = [
  { value: 'pendiente', label: 'Pendiente' },
  { value: 'en_curso', label: 'En curso' },
  { value: 'lista', label: 'Lista' },
];

const COLOR_DE_ESTADO = {
  pendiente: { fg: '#f0b429', bg: 'rgba(240, 180, 41, 0.14)' },
  en_curso: { fg: '#586AD0', bg: 'rgba(88, 106, 208, 0.16)' },
  lista: { fg: '#34D399', bg: 'rgba(52, 211, 153, 0.14)' },
};

const FILTROS_ESTADO = [
  { value: 'abiertas', label: 'Abiertas' },
  { value: '', label: 'Todas' },
  { value: 'lista', label: 'Listas' },
];

/**
 * Las Tareas de una Sesión.
 *
 * Lo que la separa de una lista de pendientes es el ▷: la descripción de la tarea es
 * la instrucción del agente asignado, y el resultado queda guardado acá para que el
 * equipo lo lea sin abrir la conversación.
 */
export default function SesionTareas({ sesion, slug }) {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const textMuted = d ? 'rgba(255,255,255,0.66)' : 'rgba(0,0,0,0.62)';
  const bgSuave = d ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.02)';
  const borde = theme.palette.divider;

  const [tareas, setTareas] = useState(null);
  const [error, setError] = useState('');
  const [titulo, setTitulo] = useState('');
  const [creando, setCreando] = useState(false);
  const [soloMias, setSoloMias] = useState(false);
  const [filtroEstado, setFiltroEstado] = useState('abiertas');
  const [corriendo, setCorriendo] = useState(null);
  const [abierta, setAbierta] = useState(null);
  const [agentes, setAgentes] = useState([]);

  const cargar = useCallback(async () => {
    if (!slug) return;
    try {
      const { data } = await api.getSesionTareas(sesion.slug, slug, {
        ...(soloMias ? { mias: 1 } : {}),
        ...(filtroEstado ? { estado: filtroEstado } : {}),
      });
      setTareas(data.results);
    } catch {
      setError('No se pudieron leer las tareas.');
      setTareas([]);
    }
  }, [sesion.slug, slug, soloMias, filtroEstado]);

  useEffect(() => { cargar(); }, [cargar]);

  // Los agentes de la empresa, para poder asignar uno a una tarea.
  useEffect(() => {
    if (!slug) return;
    api.getAgentGallery({ workspace: slug, tab: 'todos', page: 1 })
      .then(({ data }) => setAgentes(data.results || []))
      .catch(() => {});
  }, [slug]);

  const crear = async () => {
    if (!titulo.trim()) return;
    try {
      setCreando(true);
      await api.createSesionTarea(sesion.slug, { workspace: slug, title: titulo });
      setTitulo('');
      await cargar();
    } catch (e) {
      setError(e.response?.data?.detail || 'No se pudo crear la tarea.');
    } finally {
      setCreando(false);
    }
  };

  const cambiar = async (tarea, datos) => {
    try {
      const { data } = await api.updateSesionTarea(sesion.slug, tarea.id, { workspace: slug, ...datos });
      setTareas((ts) => ts.map((t) => (t.id === data.id ? data : t)));
    } catch (e) {
      setError(e.response?.data?.detail || 'No se pudo guardar el cambio.');
    }
  };

  const borrar = async (tarea) => {
    try {
      await api.deleteSesionTarea(sesion.slug, tarea.id, slug);
      setTareas((ts) => ts.filter((t) => t.id !== tarea.id));
    } catch {
      setError('No se pudo borrar la tarea.');
    }
  };

  const ejecutar = async (tarea) => {
    try {
      setCorriendo(tarea.id);
      setError('');
      const { data } = await api.runSesionTarea(sesion.slug, tarea.id, slug);
      setTareas((ts) => ts.map((t) => (t.id === data.id ? data : t)));
      setAbierta(data.id);
    } catch (e) {
      setError(e.response?.data?.detail || 'El agente no pudo completar la tarea.');
      await cargar();
    } finally {
      setCorriendo(null);
    }
  };

  if (tareas === null) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
        <CircularProgress size={22} sx={{ color: '#586AD0' }} />
      </Box>
    );
  }

  return (
    <Box sx={{ px: { xs: 2.5, sm: 4 }, pt: 2, pb: 6, maxWidth: 900, width: '100%' }}>
      {/* Alta rápida: una línea, como en el cuadro de referencia */}
      <Stack direction="row" spacing={1} sx={{ mb: 1.75 }}>
        <TextField
          value={titulo}
          onChange={(e) => setTitulo(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') crear(); }}
          placeholder="Agregar una tarea…"
          fullWidth size="small"
          sx={{
            '& .MuiOutlinedInput-root': {
              bgcolor: bgSuave, borderRadius: '8px', fontSize: '0.9375rem',
              '& fieldset': { borderColor: borde },
              '&.Mui-focused fieldset': { borderColor: '#586AD0' },
            },
          }}
        />
        <Button
          onClick={crear} variant="contained" disabled={creando || !titulo.trim()}
          sx={{ textTransform: 'none', borderRadius: '8px', fontWeight: 600, px: 2.5 }}
        >
          Agregar
        </Button>
      </Stack>

      <Stack direction="row" spacing={1.25} sx={{ mb: 2.5, flexWrap: 'wrap', gap: 1.25 }}>
        <ToggleButtonGroup
          exclusive size="small" value={soloMias ? 'mias' : 'todas'}
          onChange={(_, v) => { if (v) setSoloMias(v === 'mias'); }}
          sx={{
            '& .MuiToggleButton-root': {
              textTransform: 'none', fontSize: '0.8125rem', px: 1.75, py: 0.4,
              borderColor: borde,
              '&.Mui-selected': { bgcolor: 'rgba(88, 106, 208, 0.16)', color: '#586AD0', fontWeight: 600 },
            },
          }}
        >
          <ToggleButton value="mias">Mías</ToggleButton>
          <ToggleButton value="todas">De todos</ToggleButton>
        </ToggleButtonGroup>

        <Select
          size="small" value={filtroEstado}
          onChange={(e) => setFiltroEstado(e.target.value)}
          displayEmpty
          sx={{ fontSize: '0.8125rem', minWidth: 130 }}
        >
          {FILTROS_ESTADO.map((f) => (
            <MenuItem key={f.value} value={f.value} sx={{ fontSize: '0.8125rem' }}>{f.label}</MenuItem>
          ))}
        </Select>
      </Stack>

      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>{error}</Alert>}

      {tareas.length === 0 ? (
        <Typography sx={{ fontSize: '0.9375rem', color: textMuted, py: 2 }}>
          {soloMias
            ? 'No tiene tareas asignadas en esta Sesión.'
            : 'Todavía no hay tareas en esta Sesión.'}
        </Typography>
      ) : (
        <Stack spacing={1.25}>
          {tareas.map((t) => {
            const color = COLOR_DE_ESTADO[t.state] || COLOR_DE_ESTADO.pendiente;
            const estaCorriendo = corriendo === t.id;
            return (
              <Box
                key={t.id}
                sx={{
                  p: 1.75, borderRadius: '10px', bgcolor: bgSuave,
                  border: `1px solid ${borde}`,
                  opacity: t.state === 'lista' ? 0.78 : 1,
                }}
              >
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
                    onChange={(e) => cambiar(t, { state: e.target.value })}
                    sx={{ fontSize: '0.8rem', minWidth: 118 }}
                  >
                    {ESTADOS.map((e) => (
                      <MenuItem key={e.value} value={e.value} sx={{ fontSize: '0.8rem' }}>{e.label}</MenuItem>
                    ))}
                  </Select>

                  <Select
                    size="small" displayEmpty value={t.agent || ''}
                    onChange={(e) => cambiar(t, { agent: e.target.value || null })}
                    sx={{ fontSize: '0.8rem', minWidth: 150 }}
                  >
                    <MenuItem value="" sx={{ fontSize: '0.8rem' }}>Sin agente</MenuItem>
                    {agentes.map((a) => (
                      <MenuItem key={a.id} value={a.id} sx={{ fontSize: '0.8rem' }}>{a.name}</MenuItem>
                    ))}
                  </Select>

                  {/* Solo con agente: el botón sin agente no puede hacer nada, y
                      ofrecerlo para que devuelva un error es peor que no estar. */}
                  {t.agent && (
                    <IconButton
                      onClick={() => ejecutar(t)} disabled={estaCorriendo}
                      title={`Pedirle a ${t.agent_name} que la haga`} size="small"
                    >
                      {estaCorriendo
                        ? <CircularProgress size={16} sx={{ color: '#586AD0' }} />
                        : <Play size={15} />}
                    </IconButton>
                  )}
                  <IconButton onClick={() => borrar(t)} title="Borrar la tarea" size="small">
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
                      onClick={() => setAbierta(abierta === t.id ? null : t.id)}
                      sx={{
                        border: 'none', bgcolor: 'transparent', p: 0, cursor: 'pointer',
                        fontFamily: 'inherit', fontSize: '0.8125rem', fontWeight: 600,
                        color: '#9BA6E3', '&:hover': { textDecoration: 'underline' },
                      }}
                    >
                      {abierta === t.id ? 'Ocultar lo que hizo' : `Ver lo que hizo ${t.agent_name || 'el agente'}`}
                    </Box>
                    {abierta === t.id && (
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
          })}
        </Stack>
      )}
    </Box>
  );
}
