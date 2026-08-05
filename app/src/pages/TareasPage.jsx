import { useCallback, useEffect, useState } from 'react';
import {
  Alert, Badge, Box, CircularProgress, MenuItem, Select, Stack, Tab, Tabs, Typography,
  useTheme,
} from '@mui/material';
import { Link } from 'react-router-dom';
import { CheckSquare } from 'lucide-react';
import { api } from '../services/api';
import { useWorkspace } from '../context/WorkspaceContext';
import PageHeader from '../components/PageHeader';
import FilaDeTarea from '../components/FilaDeTarea';

/**
 * Todo lo pendiente de la empresa, cruzando Sesiones.
 *
 * La pantalla que faltaba. Las tareas existían solo adentro de su Sesión, cuatro niveles
 * adentro de la barra lateral, así que la pregunta que uno se hace de verdad —"¿qué tengo
 * pendiente?"— no se podía contestar sin abrir Sesión por Sesión y acordarse de todas. Una
 * tarea que hay que ir a buscar no es un pendiente: es un papel perdido.
 *
 * Las cuatro pestañas son las cuatro preguntas reales, en orden de urgencia: lo mío, lo del
 * equipo, lo que le toca a un agente, y el archivo de lo hecho. Cada una lleva su número
 * SIN filtrar por la pestaña en la que se está — una pestaña que cuenta solo lo que ya está
 * a la vista no sirve para decidir a cuál ir.
 *
 * Cada tarea muestra de qué Sesión es, y ese nombre es un enlace: quien mira sus pendientes
 * quiere ir al trabajo donde está la tarea.
 */
const PESTANAS = [
  { value: 'mias',       label: 'Mías',       contador: 'mias' },
  { value: 'abiertas',   label: 'Del equipo', contador: 'pendientes' },
  { value: 'de_agentes', label: 'De agentes', contador: 'de_agentes' },
  { value: 'lista',      label: 'Hechas',     contador: null },
];

// Qué le pide cada pestaña al backend. Un solo lugar donde se traduce.
const CONSULTA = {
  mias:       { mias: 1, estado: 'abiertas' },
  abiertas:   { estado: 'abiertas' },
  de_agentes: { agente: 1, estado: 'abiertas' },
  lista:      { estado: 'lista' },
};

const VACIO = {
  mias: 'No tiene nada asignado. Cuando alguien le asigne una tarea, o se asigne una, aparece acá.',
  abiertas: 'No hay tareas abiertas en ninguna Sesión.',
  de_agentes: 'Ningún agente tiene una tarea asignada. Asígnele una desde la Sesión y el agente la ejecuta.',
  lista: 'Todavía no hay tareas terminadas.',
};

export default function TareasPage() {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const textMuted = d ? 'rgba(255,255,255,0.66)' : 'rgba(0,0,0,0.62)';
  const borde = theme.palette.divider;

  const { slug } = useWorkspace();

  const [pestana, setPestana] = useState('mias');
  const [sesionFiltro, setSesionFiltro] = useState('');
  const [datos, setDatos] = useState(null);
  const [agentes, setAgentes] = useState([]);
  const [corriendo, setCorriendo] = useState(null);
  const [error, setError] = useState('');

  const cargar = useCallback(async () => {
    if (!slug) return;
    try {
      const { data } = await api.getTareasDelWorkspace(slug, CONSULTA[pestana]);
      setDatos(data);
    } catch {
      setError('No se pudieron leer las tareas.');
      setDatos({ results: [], totales: {} });
    }
  }, [slug, pestana]);

  useEffect(() => { cargar(); }, [cargar]);

  useEffect(() => {
    if (!slug) return;
    api.getAgentGallery({ workspace: slug, tab: 'todos', page: 1 })
      .then(({ data }) => setAgentes(data.results || []))
      .catch(() => {});
  }, [slug]);

  // Los cambios se hacen contra la Sesión de la tarea, que es donde vive el endpoint:
  // esta pantalla es otra vista de lo mismo, no otro dueño.
  const cambiar = async (tarea, cambios) => {
    try {
      const { data } = await api.updateSesionTarea(tarea.sesion.slug, tarea.id, {
        workspace: slug, ...cambios,
      });
      // Un cambio de estado puede sacar la tarea de la pestaña en la que se está, y los
      // contadores de las demás también se mueven: hay que recargar, no parchear la fila.
      if ('state' in cambios) await cargar();
      else setDatos((v) => ({
        ...v,
        results: v.results.map((t) => (t.id === data.id ? { ...data, sesion: tarea.sesion } : t)),
      }));
    } catch (e) {
      setError(e.response?.data?.detail || 'No se pudo guardar el cambio.');
    }
  };

  const borrar = async (tarea) => {
    try {
      await api.deleteSesionTarea(tarea.sesion.slug, tarea.id, slug);
      await cargar();
    } catch {
      setError('No se pudo borrar la tarea.');
    }
  };

  const ejecutar = async (tarea) => {
    try {
      setCorriendo(tarea.id);
      setError('');
      const { data } = await api.runSesionTarea(tarea.sesion.slug, tarea.id, slug);
      setDatos((v) => ({
        ...v,
        results: v.results.map((t) => (t.id === data.id ? { ...data, sesion: tarea.sesion } : t)),
      }));
    } catch (e) {
      setError(e.response?.data?.detail || 'El agente no pudo completar la tarea.');
      await cargar();
    } finally {
      setCorriendo(null);
    }
  };

  const totales = datos?.totales || {};
  // Las Sesiones que aparecen en lo que se está mirando: el filtro se arma con lo que hay,
  // no con la lista entera. Ofrecer una Sesión que dejaría la lista vacía es una trampa.
  const sesiones = [...new Map(
    (datos?.results || []).filter((t) => t.sesion).map((t) => [t.sesion.slug, t.sesion]),
  ).values()];

  const visibles = (datos?.results || []).filter(
    (t) => !sesionFiltro || t.sesion?.slug === sesionFiltro,
  );

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100%' }}>
      <PageHeader title="Tareas" back="/app" backLabel="Chat" />

      <Box sx={{ borderBottom: `1px solid ${borde}`, px: { xs: 2, sm: 3 } }}>
        <Tabs
          value={pestana}
          onChange={(_, v) => { setPestana(v); setSesionFiltro(''); }}
          variant="scrollable" scrollButtons="auto"
          sx={{
            minHeight: 40,
            '& .MuiTab-root': { minHeight: 40, textTransform: 'none', fontSize: '0.82rem' },
          }}
        >
          {PESTANAS.map((p) => {
            const n = p.contador ? totales[p.contador] : 0;
            return (
              <Tab
                key={p.value} value={p.value}
                label={
                  <Badge
                    badgeContent={n || 0} invisible={!n} color="primary"
                    sx={{ '& .MuiBadge-badge': { right: -14, top: 2, fontSize: '0.65rem', height: 16, minWidth: 16 } }}
                  >
                    {p.label}
                  </Badge>
                }
              />
            );
          })}
        </Tabs>
      </Box>

      <Box sx={{ px: { xs: 2.5, sm: 4 }, pt: 2.5, pb: 6, maxWidth: 900, width: '100%' }}>
        {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>{error}</Alert>}

        {/* El filtro por Sesión solo aparece cuando hay más de una: con una sola no
            filtra nada y sería un control que no hace nada. */}
        {sesiones.length > 1 && (
          <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }}>
            <Select
              size="small" displayEmpty value={sesionFiltro}
              onChange={(e) => setSesionFiltro(e.target.value)}
              sx={{ fontSize: '0.8125rem', minWidth: 210 }}
            >
              <MenuItem value="" sx={{ fontSize: '0.8125rem' }}>Todas las Sesiones</MenuItem>
              {sesiones.map((s) => (
                <MenuItem key={s.slug} value={s.slug} sx={{ fontSize: '0.8125rem' }}>{s.name}</MenuItem>
              ))}
            </Select>
            <Typography sx={{ fontSize: '0.8125rem', color: textMuted }}>
              {visibles.length} {visibles.length === 1 ? 'tarea' : 'tareas'}
            </Typography>
          </Stack>
        )}

        {datos === null ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
            <CircularProgress size={22} sx={{ color: '#586AD0' }} />
          </Box>
        ) : visibles.length === 0 ? (
          <Stack spacing={1.5} sx={{ py: 4, alignItems: 'flex-start' }}>
            <CheckSquare size={22} color={textMuted} strokeWidth={1.75} />
            <Typography sx={{ fontSize: '0.9375rem', color: textMuted, maxWidth: 460 }}>
              {VACIO[pestana]}
            </Typography>
            {/* Una pantalla vacía tiene que decir cómo se llena. Las tareas se crean
                dentro de una Sesión, y desde acá eso no se adivina. */}
            <Typography sx={{ fontSize: '0.875rem', color: textMuted }}>
              Las tareas se crean dentro de una{' '}
              <Box component={Link} to="/app/contexto?tab=espacios" sx={{ color: '#9BA6E3', fontWeight: 600 }}>
                Sesión
              </Box>
              , en su pestaña Tareas.
            </Typography>
          </Stack>
        ) : (
          <Stack spacing={1.25}>
            {visibles.map((t) => (
              <FilaDeTarea
                key={t.id} tarea={t} agentes={agentes} mostrarSesion
                corriendo={corriendo === t.id}
                onCambiar={cambiar} onBorrar={borrar} onEjecutar={ejecutar}
              />
            ))}
          </Stack>
        )}
      </Box>
    </Box>
  );
}
