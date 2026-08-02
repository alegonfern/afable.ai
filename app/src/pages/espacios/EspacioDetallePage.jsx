import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Alert, Box, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent,
  DialogTitle, IconButton, List, ListItem, ListItemText, MenuItem, Select, Stack,
  Tab, Tabs, TextField, Typography, useTheme,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import LockOutlinedIcon from '@mui/icons-material/LockOutlined';
import PublicOutlinedIcon from '@mui/icons-material/PublicOutlined';
import PageHeader from '../../components/PageHeader';
import { api } from '../../services/api';
import { useWorkspace } from '../../context/WorkspaceContext';

// Cada pestaña es una colección del Espacio. `campo` es como viene en la ficha,
// `coleccion` es el segmento de la URL de la API — no siempre coinciden porque
// la API habla español y el modelo de datos inglés.
const PESTANAS = [
  { campo: 'connections', coleccion: 'conexiones', label: 'Fuentes',  vacio: 'Este Espacio todavía no tiene ninguna conexión enganchada.' },
  { campo: 'documents',   coleccion: 'documentos', label: 'Documentos', vacio: 'Ningún documento vive en este Espacio.' },
  { campo: 'agents',      coleccion: 'agentes',    label: 'Agentes',  vacio: 'Ningún agente trabaja todavía en este Espacio.' },
  { campo: 'members',     coleccion: 'personas',   label: 'Personas', vacio: 'Nadie está agregado a este Espacio.' },
];

function etiqueta(item, campo) {
  if (campo === 'documents') return item.title;
  if (campo === 'members') return item.full_name || item.email;
  return item.name;
}

function detalle(item, campo) {
  if (campo === 'connections') return item.connector_type;
  if (campo === 'documents') return item.category;
  if (campo === 'agents') return item.description || item.area;
  if (campo === 'members') return item.email;
  return '';
}

const PESTANA_CONVERSACIONES = 'conversaciones';

export default function EspacioDetallePage() {
  const theme = useTheme();
  const navigate = useNavigate();
  const { spaceSlug } = useParams();
  const { slug } = useWorkspace();

  const [espacio, setEspacio] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState('');
  const [tab, setTab] = useState('connections');
  const [disponibles, setDisponibles] = useState(null);
  const [eligiendo, setEligiendo] = useState(null); // la pestaña cuyo selector está abierto
  const [seleccion, setSeleccion] = useState([]);
  const [conversaciones, setConversaciones] = useState(null);

  const pestana = useMemo(() => PESTANAS.find((p) => p.campo === tab), [tab]);

  const cargar = useCallback(async () => {
    if (!slug || !spaceSlug) return;
    setCargando(true);
    try {
      const { data } = await api.getSpace(slug, spaceSlug);
      setEspacio(data);
      setError('');
    } catch {
      setError('Este Espacio no existe o no tiene acceso.');
    } finally {
      setCargando(false);
    }
  }, [slug, spaceSlug]);

  useEffect(() => { cargar(); }, [cargar]);

  // Las conversaciones se piden al entrar a su pestaña: es la lista que más
  // cambia y no tiene por qué viajar con la ficha.
  useEffect(() => {
    if (tab !== PESTANA_CONVERSACIONES || !slug || !spaceSlug) return;
    let vivo = true;
    api.getSpaceConversations(slug, spaceSlug)
      .then(({ data }) => { if (vivo) setConversaciones(data); })
      .catch(() => { if (vivo) setConversaciones([]); });
    return () => { vivo = false; };
  }, [tab, slug, spaceSlug]);

  const abrirSelector = async () => {
    setEligiendo(pestana);
    setSeleccion([]);
    try {
      const { data } = await api.getSpaceAvailable(slug, spaceSlug);
      setDisponibles(data);
    } catch {
      setDisponibles({});
      setError('No se pudo leer lo que hay para enganchar.');
    }
  };

  const enganchar = async () => {
    try {
      const { data } = await api.addToSpace(slug, spaceSlug, eligiendo.coleccion, seleccion);
      setEspacio(data);
      setEligiendo(null);
    } catch {
      setError('No se pudo enganchar. Revise que siga teniendo permisos de editor.');
    }
  };

  const soltar = async (id) => {
    try {
      const { data } = await api.removeFromSpace(slug, spaceSlug, pestana.coleccion, [id]);
      setEspacio(data);
    } catch {
      setError('No se pudo sacar del Espacio.');
    }
  };

  const cambiarVisibilidad = async (visibility) => {
    try {
      const { data } = await api.updateSpace(slug, spaceSlug, { visibility });
      setEspacio(data);
    } catch {
      setError('No se pudo cambiar quién entra a este Espacio.');
    }
  };

  if (cargando) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
        <CircularProgress size={24} />
      </Box>
    );
  }

  if (!espacio) {
    return (
      <Box sx={{ p: 3 }}>
        <PageHeader title="Espacio" back="/app/contexto?tab=espacios" backLabel="Espacios" />
        <Alert severity="warning" sx={{ mt: 2 }}>{error || 'Espacio no encontrado.'}</Alert>
      </Box>
    );
  }

  const items = pestana ? (espacio[pestana.campo] || []) : [];
  const paraElegir = (disponibles && eligiendo && disponibles[eligiendo.coleccion]) || [];

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100%' }}>
      <PageHeader
        title={`${espacio.icon || '📁'}  ${espacio.name}`}
        back="/app/contexto?tab=espacios" backLabel="Espacios"
      />

      <Box sx={{ px: { xs: 2, sm: 3 }, pt: 2 }}>
        {espacio.description && (
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5, maxWidth: 620 }}>
            {espacio.description}
          </Typography>
        )}
        <Stack direction="row" spacing={1.5} alignItems="center" sx={{ mb: 2 }}>
          <Chip
            size="small" variant="outlined"
            icon={espacio.visibility === 'abierto' ? <PublicOutlinedIcon /> : <LockOutlinedIcon />}
            label={espacio.visibility === 'abierto'
              ? 'Lo ve todo el equipo'
              : `Sólo ${espacio.members.length} persona${espacio.members.length === 1 ? '' : 's'}`}
          />
          <Select
            size="small" value={espacio.visibility}
            onChange={(ev) => cambiarVisibilidad(ev.target.value)}
            sx={{ fontSize: '0.8rem', minWidth: 150 }}
          >
            <MenuItem value="abierto" sx={{ fontSize: '0.8rem' }}>Abierto</MenuItem>
            <MenuItem value="restringido" sx={{ fontSize: '0.8rem' }}>Restringido</MenuItem>
          </Select>
        </Stack>
        {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>{error}</Alert>}
      </Box>

      <Box sx={{ borderBottom: `1px solid ${theme.palette.divider}`, px: { xs: 2, sm: 3 } }}>
        <Tabs
          value={tab} onChange={(_, v) => setTab(v)}
          sx={{ minHeight: 40, '& .MuiTab-root': { minHeight: 40, textTransform: 'none', fontSize: '0.82rem' } }}
        >
          {PESTANAS.map((p) => (
            <Tab
              key={p.campo} value={p.campo}
              label={`${p.label} (${(espacio[p.campo] || []).length})`}
            />
          ))}
          <Tab value={PESTANA_CONVERSACIONES} label="Conversaciones" />
        </Tabs>
      </Box>

      {tab === PESTANA_CONVERSACIONES ? (
        <Box sx={{ px: { xs: 2, sm: 3 }, pt: 2, pb: 5, maxWidth: 780, width: '100%' }}>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
            Lo que se trabajó en este Espacio. A diferencia de su historial personal,
            estas conversaciones las ve cualquiera que pertenezca al Espacio.
          </Typography>
          {conversaciones === null ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
              <CircularProgress size={20} />
            </Box>
          ) : conversaciones.length === 0 ? (
            <Typography variant="body2" color="text.secondary" sx={{ py: 3 }}>
              Todavía no se conversó nada en este Espacio. En el chat, elija «{espacio.name}»
              en el selector de Espacio y lo que hable queda acá.
            </Typography>
          ) : (
            <List dense sx={{ border: `1px solid ${theme.palette.divider}`, borderRadius: 1 }}>
              {conversaciones.map((c) => (
                <ListItem
                  key={c.id} divider button
                  onClick={() => navigate(`/app/chat?conversation=${c.id}`)}
                >
                  <ListItemText
                    primary={c.title}
                    secondary={[
                      c.agent_handle ? `@${c.agent_handle}` : c.agent,
                      c.es_mia ? 'usted' : c.author,
                    ].filter(Boolean).join(' · ')}
                    primaryTypographyProps={{ fontSize: '0.86rem' }}
                    secondaryTypographyProps={{ fontSize: '0.75rem' }}
                  />
                </ListItem>
              ))}
            </List>
          )}
        </Box>
      ) : (
      <Box sx={{ px: { xs: 2, sm: 3 }, pt: 2, pb: 5, maxWidth: 780, width: '100%' }}>
        <Button
          size="small" startIcon={<AddIcon />} onClick={abrirSelector}
          sx={{ textTransform: 'none', mb: 1 }}
        >
          Agregar {pestana.label.toLowerCase()}
        </Button>

        {items.length === 0 ? (
          <Typography variant="body2" color="text.secondary" sx={{ py: 3 }}>
            {pestana.vacio}
          </Typography>
        ) : (
          <List dense sx={{ border: `1px solid ${theme.palette.divider}`, borderRadius: 1 }}>
            {items.map((item) => (
              <ListItem
                key={item.id}
                divider
                secondaryAction={
                  <IconButton edge="end" size="small" onClick={() => soltar(item.id)} aria-label="Sacar del Espacio">
                    <DeleteOutlineIcon fontSize="small" />
                  </IconButton>
                }
              >
                <ListItemText
                  primary={etiqueta(item, pestana.campo)}
                  secondary={detalle(item, pestana.campo)}
                  primaryTypographyProps={{ fontSize: '0.86rem' }}
                  secondaryTypographyProps={{ fontSize: '0.75rem' }}
                />
              </ListItem>
            ))}
          </List>
        )}
      </Box>
      )}

      <Dialog open={Boolean(eligiendo)} onClose={() => setEligiendo(null)} fullWidth maxWidth="sm">
        <DialogTitle sx={{ fontSize: '1rem', fontWeight: 600 }}>
          Agregar {eligiendo?.label.toLowerCase()} al Espacio
        </DialogTitle>
        <DialogContent>
          {disponibles === null ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}><CircularProgress size={20} /></Box>
          ) : paraElegir.length === 0 ? (
            <Typography variant="body2" color="text.secondary" sx={{ py: 2 }}>
              No queda nada por enganchar acá. Cree la conexión o el documento primero en Contexto.
            </Typography>
          ) : (
            <TextField
              select fullWidth size="small" label="Elija uno o varios" sx={{ mt: 1 }}
              SelectProps={{ multiple: true, value: seleccion,
                onChange: (ev) => setSeleccion(ev.target.value) }}
            >
              {paraElegir.map((o) => (
                <MenuItem key={o.id} value={o.id} sx={{ fontSize: '0.85rem' }}>{o.label}</MenuItem>
              ))}
            </TextField>
          )}
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setEligiendo(null)} sx={{ textTransform: 'none' }}>Cancelar</Button>
          <Button
            variant="contained" onClick={enganchar} disabled={seleccion.length === 0}
            sx={{ textTransform: 'none' }}
          >
            Agregar
          </Button>
        </DialogActions>
      </Dialog>

      <Box sx={{ px: { xs: 2, sm: 3 }, pb: 4 }}>
        <Button
          size="small" color="error" sx={{ textTransform: 'none' }}
          onClick={async () => {
            await api.deleteSpace(slug, spaceSlug);
            navigate('/app/contexto?tab=espacios');
          }}
        >
          Eliminar este Espacio
        </Button>
      </Box>
    </Box>
  );
}
