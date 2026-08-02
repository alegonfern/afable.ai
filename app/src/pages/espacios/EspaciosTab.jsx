import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Alert, Box, Button, Card, CardActionArea, Chip, CircularProgress, Dialog,
  DialogActions, DialogContent, DialogTitle, MenuItem, Stack, TextField,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import LockOutlinedIcon from '@mui/icons-material/LockOutlined';
import PublicOutlinedIcon from '@mui/icons-material/PublicOutlined';
import { api } from '../../services/api';
import { useWorkspace } from '../../context/WorkspaceContext';

const VISIBILIDADES = [
  { value: 'abierto', label: 'Abierto — lo ve todo el equipo' },
  { value: 'restringido', label: 'Restringido — sólo quienes agregue' },
];

const VACIO = { name: '', description: '', icon: '', visibility: 'abierto' };

export default function EspaciosTab() {
  const navigate = useNavigate();
  const { slug } = useWorkspace();

  const [espacios, setEspacios] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState('');
  const [abierto, setAbierto] = useState(false);
  const [form, setForm] = useState(VACIO);
  const [guardando, setGuardando] = useState(false);

  const cargar = useCallback(async () => {
    if (!slug) return;
    setCargando(true);
    try {
      const { data } = await api.getSpaces(slug);
      setEspacios(data);
      setError('');
    } catch {
      setError('No se pudieron cargar los Espacios.');
    } finally {
      setCargando(false);
    }
  }, [slug]);

  useEffect(() => { cargar(); }, [cargar]);

  const crear = async () => {
    setGuardando(true);
    try {
      const { data } = await api.createSpace(slug, form);
      setAbierto(false);
      setForm(VACIO);
      navigate(`/app/espacios/${data.slug}`);
    } catch (e) {
      setError(e?.response?.data?.detail || 'No se pudo crear el Espacio.');
    } finally {
      setGuardando(false);
    }
  };

  if (cargando) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
        <CircularProgress size={24} />
      </Box>
    );
  }

  return (
    <Box sx={{ pt: 2.5, pb: 5, px: { xs: 2, sm: 3 }, maxWidth: 980, width: '100%' }}>
      <Stack direction="row" alignItems="flex-start" justifyContent="space-between" sx={{ mb: 2.5 }}>
        <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 560 }}>
          Un Espacio junta las fuentes, los agentes y las personas de un área. El agente de
          un Espacio sólo alcanza los datos de ese Espacio: es la forma de que Ventas no
          lea las carpetas de Personas.
        </Typography>
        <Button
          variant="contained" size="small" startIcon={<AddIcon />}
          onClick={() => setAbierto(true)} sx={{ flexShrink: 0, textTransform: 'none' }}
        >
          Nuevo Espacio
        </Button>
      </Stack>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {espacios.length === 0 ? (
        <Card variant="outlined" sx={{ p: 4, textAlign: 'center', borderStyle: 'dashed' }}>
          <Typography variant="subtitle2" sx={{ mb: 0.5 }}>Todavía no hay Espacios</Typography>
          <Typography variant="body2" color="text.secondary">
            Cree uno por área — Ventas, Finanzas, Personas — y enganche ahí sus conexiones y documentos.
          </Typography>
        </Card>
      ) : (
        <Box sx={{
          display: 'grid', gap: 1.5,
          gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', lg: 'repeat(3, 1fr)' },
        }}>
          {espacios.map((e) => (
            <Card key={e.id} variant="outlined">
              <CardActionArea
                onClick={() => navigate(`/app/espacios/${e.slug}`)}
                sx={{ p: 2, height: '100%', alignItems: 'flex-start' }}
              >
                <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 0.5 }}>
                  <Typography component="span" sx={{ fontSize: '1.1rem' }}>{e.icon || '📁'}</Typography>
                  <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>{e.name}</Typography>
                </Stack>
                <Typography
                  variant="body2" color="text.secondary"
                  sx={{ minHeight: 34, mb: 1.25, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}
                >
                  {e.description || 'Sin descripción.'}
                </Typography>
                <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap>
                  <Chip
                    size="small" variant="outlined"
                    icon={e.visibility === 'abierto' ? <PublicOutlinedIcon /> : <LockOutlinedIcon />}
                    label={e.visibility === 'abierto' ? 'Abierto' : 'Restringido'}
                  />
                  <Chip size="small" label={`${e.counts.connections} conexiones`} />
                  <Chip size="small" label={`${e.counts.documents} documentos`} />
                  <Chip size="small" label={`${e.counts.agents} agentes`} />
                </Stack>
              </CardActionArea>
            </Card>
          ))}
        </Box>
      )}

      <Dialog open={abierto} onClose={() => setAbierto(false)} fullWidth maxWidth="sm">
        <DialogTitle sx={{ fontSize: '1rem', fontWeight: 600 }}>Nuevo Espacio</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <Stack direction="row" spacing={1.5}>
              <TextField
                label="Emoji" size="small" sx={{ width: 90 }}
                value={form.icon} onChange={(ev) => setForm({ ...form, icon: ev.target.value })}
              />
              <TextField
                label="Nombre" size="small" fullWidth autoFocus
                placeholder="Ventas, Finanzas, Personas…"
                value={form.name} onChange={(ev) => setForm({ ...form, name: ev.target.value })}
              />
            </Stack>
            <TextField
              label="Para qué sirve" size="small" fullWidth multiline rows={2}
              value={form.description} onChange={(ev) => setForm({ ...form, description: ev.target.value })}
            />
            <TextField
              select label="Quién entra" size="small" fullWidth
              value={form.visibility} onChange={(ev) => setForm({ ...form, visibility: ev.target.value })}
            >
              {VISIBILIDADES.map((v) => (
                <MenuItem key={v.value} value={v.value} sx={{ fontSize: '0.85rem' }}>{v.label}</MenuItem>
              ))}
            </TextField>
            <Typography variant="caption" color="text.secondary">
              Después de crearlo enganche sus conexiones, documentos y agentes desde la ficha del Espacio.
            </Typography>
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setAbierto(false)} sx={{ textTransform: 'none' }}>Cancelar</Button>
          <Button
            variant="contained" onClick={crear} sx={{ textTransform: 'none' }}
            disabled={guardando || !form.name.trim()}
          >
            Crear Espacio
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
