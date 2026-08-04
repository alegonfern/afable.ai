import { useCallback, useEffect, useState } from 'react';
import {
  Alert, Box, Button, Chip, CircularProgress, IconButton, MenuItem,
  Select, Stack, TextField, Typography, useTheme,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
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

/**
 * Las Tareas de un Espacio.
 *
 * Lo que la separa de una lista de pendientes cualquiera es el botón de ejecutar:
 * la descripción de la tarea es la instrucción del agente asignado, y el resultado
 * queda guardado en la tarea para que lo lea el equipo sin abrir la conversación.
 *
 * Vive en su propio archivo porque `EspacioDetallePage` ya maneja las cuatro
 * colecciones del Espacio, su visibilidad y las conversaciones.
 */
export default function TareasTab({ slug, spaceSlug, agentes = [], personas = [] }) {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const textMuted = d ? 'rgba(255,255,255,0.66)' : 'rgba(0,0,0,0.62)';
  const bgSuave = d ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.02)';

  const [tareas, setTareas] = useState(null);
  const [error, setError] = useState('');
  const [nueva, setNueva] = useState({ title: '', description: '', agent: '', assignee: '' });
  const [abriendo, setAbriendo] = useState(false);
  const [creando, setCreando] = useState(false);
  // Qué tarea está corriendo ahora: el botón de ejecutar espera al modelo y sin
  // esto no hay nada que indique que algo está pasando.
  const [corriendo, setCorriendo] = useState(null);
  const [abierta, setAbierta] = useState(null);

  const cargar = useCallback(async () => {
    if (!slug || !spaceSlug) return;
    try {
      const { data } = await api.getSpaceTasks(slug, spaceSlug);
      setTareas(data.results);
    } catch {
      setError('No se pudieron leer las tareas de este Espacio.');
      setTareas([]);
    }
  }, [slug, spaceSlug]);

  useEffect(() => { cargar(); }, [cargar]);

  const crear = async () => {
    if (!nueva.title.trim()) return;
    try {
      setCreando(true);
      await api.createSpaceTask(slug, spaceSlug, {
        title: nueva.title,
        description: nueva.description,
        agent: nueva.agent || null,
        assignee: nueva.assignee || null,
      });
      setNueva({ title: '', description: '', agent: '', assignee: '' });
      setAbriendo(false);
      await cargar();
    } catch (e) {
      setError(e.response?.data?.detail || 'No se pudo crear la tarea.');
    } finally {
      setCreando(false);
    }
  };

  const cambiar = async (tarea, datos) => {
    try {
      const { data } = await api.updateSpaceTask(slug, spaceSlug, tarea.id, datos);
      setTareas((ts) => ts.map((t) => (t.id === data.id ? data : t)));
    } catch (e) {
      setError(e.response?.data?.detail || 'No se pudo guardar el cambio.');
    }
  };

  const borrar = async (tarea) => {
    try {
      await api.deleteSpaceTask(slug, spaceSlug, tarea.id);
      setTareas((ts) => ts.filter((t) => t.id !== tarea.id));
    } catch {
      setError('No se pudo borrar la tarea.');
    }
  };

  const ejecutar = async (tarea) => {
    try {
      setCorriendo(tarea.id);
      setError('');
      const { data } = await api.runSpaceTask(slug, spaceSlug, tarea.id);
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
    <Box sx={{ px: { xs: 2, sm: 3 }, pt: 2, pb: 5, maxWidth: 820, width: '100%' }}>
      <Typography variant="body2" sx={{ color: textMuted, mb: 1.5 }}>
        Lo que falta hacer en este Espacio. Una tarea la puede tomar una persona o un
        agente: si le asigna un agente, su descripción es la instrucción y el resultado
        queda guardado acá.
      </Typography>

      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>{error}</Alert>}

      {!abriendo ? (
        <Button
          onClick={() => setAbriendo(true)}
          startIcon={<AddIcon fontSize="small" />}
          sx={{ textTransform: 'none', mb: 2 }}
        >
          Nueva tarea
        </Button>
      ) : (
        <Box sx={{ p: 2, mb: 2, borderRadius: '10px', bgcolor: bgSuave, border: `1px solid ${theme.palette.divider}` }}>
          <TextField
            value={nueva.title}
            onChange={(e) => setNueva({ ...nueva, title: e.target.value })}
            placeholder="Qué hay que hacer"
            fullWidth size="small" autoFocus sx={{ mb: 1.25 }}
          />
          <TextField
            value={nueva.description}
            onChange={(e) => setNueva({ ...nueva, description: e.target.value })}
            placeholder="El detalle. Si la toma un agente, esto es lo que le va a pedir."
            fullWidth size="small" multiline minRows={2} sx={{ mb: 1.25 }}
          />
          <Stack direction="row" spacing={1.25} sx={{ mb: 1.5, flexWrap: 'wrap', gap: 1.25 }}>
            <Select
              size="small" displayEmpty value={nueva.assignee}
              onChange={(e) => setNueva({ ...nueva, assignee: e.target.value })}
              sx={{ fontSize: '0.85rem', minWidth: 190 }}
            >
              <MenuItem value="" sx={{ fontSize: '0.85rem' }}>Sin responsable</MenuItem>
              {personas.map((p) => (
                <MenuItem key={p.id} value={p.id} sx={{ fontSize: '0.85rem' }}>
                  {p.full_name || p.email}
                </MenuItem>
              ))}
            </Select>
            <Select
              size="small" displayEmpty value={nueva.agent}
              onChange={(e) => setNueva({ ...nueva, agent: e.target.value })}
              sx={{ fontSize: '0.85rem', minWidth: 190 }}
            >
              <MenuItem value="" sx={{ fontSize: '0.85rem' }}>Sin agente</MenuItem>
              {agentes.map((a) => (
                <MenuItem key={a.id} value={a.id} sx={{ fontSize: '0.85rem' }}>{a.name}</MenuItem>
              ))}
            </Select>
          </Stack>
          <Stack direction="row" spacing={1}>
            <Button
              onClick={crear} variant="contained" size="small"
              disabled={creando || !nueva.title.trim()}
              sx={{ textTransform: 'none' }}
            >
              {creando ? 'Creando…' : 'Crear'}
            </Button>
            <Button onClick={() => setAbriendo(false)} size="small" sx={{ textTransform: 'none', color: textMuted }}>
              Cancelar
            </Button>
          </Stack>
          {agentes.length === 0 && (
            <Typography sx={{ fontSize: '0.8rem', color: textMuted, mt: 1.5, fontStyle: 'italic' }}>
              Este Espacio no tiene agentes enganchados, así que se puede asignar cualquiera
              de la empresa. Para acotarlo, agréguelos en la pestaña Agentes.
            </Typography>
          )}
        </Box>
      )}

      {tareas.length === 0 ? (
        <Typography sx={{ fontSize: '0.9rem', color: textMuted, py: 2 }}>
          Todavía no hay tareas en este Espacio.
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
                  border: `1px solid ${theme.palette.divider}`,
                  opacity: t.state === 'lista' ? 0.75 : 1,
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
                        <Chip size="small" variant="outlined" label={t.assignee_name} sx={{ fontSize: '0.75rem' }} />
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

                  {/* Solo si tiene agente: el botón sin agente asignado no puede hacer
                      nada, y ofrecerlo para que devuelva un error es peor que no estar. */}
                  {t.agent && (
                    <IconButton
                      onClick={() => ejecutar(t)} disabled={estaCorriendo}
                      title={`Pedirle a ${t.agent_name} que la haga`} size="small"
                    >
                      {estaCorriendo
                        ? <CircularProgress size={16} sx={{ color: '#586AD0' }} />
                        : <PlayArrowIcon fontSize="small" />}
                    </IconButton>
                  )}
                  <IconButton onClick={() => borrar(t)} title="Borrar la tarea" size="small">
                    <DeleteOutlineIcon fontSize="small" />
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
                        borderRadius: '8px', border: `1px solid ${theme.palette.divider}`,
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
