import { useCallback, useEffect, useState } from 'react';
import {
  Alert, Box, Button, CircularProgress, MenuItem,
  Select, Stack, TextField, ToggleButton, ToggleButtonGroup, Typography, useTheme,
} from '@mui/material';
import { api } from '../../services/api';
import FilaDeTarea from '../../components/FilaDeTarea';

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
          {tareas.map((t) => (
            <FilaDeTarea
              key={t.id} tarea={t} agentes={agentes} corriendo={corriendo === t.id}
              onCambiar={cambiar} onBorrar={borrar} onEjecutar={ejecutar}
            />
          ))}
        </Stack>
      )}
    </Box>
  );
}
