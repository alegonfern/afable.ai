import { useCallback, useEffect, useState } from 'react';
import {
  Box, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent,
  DialogTitle, IconButton, MenuItem, Stack, TextField, Typography, useTheme,
} from '@mui/material';
import { Plus, Sparkles, Trash2 } from 'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../../services/api';

const VACIA = { name: '', description: '', instructions: '', agent_ids: [] };

/**
 * Admin › Agentes › Habilidades.
 *
 * Una Habilidad es un bloque de instrucciones escrito una vez y enganchado a
 * varios agentes. El caso típico es el tono: cómo le habla la empresa a sus
 * clientes se escribe acá, y lo aplican los cinco agentes que redactan hacia
 * afuera. Copiado en cinco lugares, corregirlo es acordarse de los cinco.
 */
export default function HabilidadesTab({ agentes = [] }) {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const textMuted = d ? 'rgba(255,255,255,0.66)' : 'rgba(0,0,0,0.62)';

  const [habilidades, setHabilidades] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [editando, setEditando] = useState(null);   // la habilidad abierta, o VACIA para una nueva
  const [guardando, setGuardando] = useState(false);

  const cargar = useCallback(async () => {
    try {
      const { data } = await api.getSkills();
      setHabilidades(data);
    } catch {
      toast.error('No se pudieron cargar las Habilidades.');
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => { cargar(); }, [cargar]);

  const abrirNueva = () => setEditando({ ...VACIA });

  const abrirExistente = (h) => setEditando({
    ...h, agent_ids: (h.agents || []).map((a) => a.id),
  });

  const guardar = async () => {
    setGuardando(true);
    try {
      const cuerpo = {
        name: editando.name.trim(),
        description: editando.description,
        instructions: editando.instructions,
        agent_ids: editando.agent_ids,
      };
      if (editando.id) await api.updateSkill(editando.id, cuerpo);
      else await api.createSkill(cuerpo);
      setEditando(null);
      await cargar();
      toast.success(editando.id ? 'Habilidad actualizada.' : 'Habilidad creada.');
    } catch (e) {
      const detalle = e?.response?.data;
      toast.error(
        detalle?.instructions?.[0] || detalle?.name?.[0] || 'No se pudo guardar la Habilidad.',
      );
    } finally {
      setGuardando(false);
    }
  };

  const borrar = async (h) => {
    try {
      await api.deleteSkill(h.id);
      await cargar();
      toast.success('Habilidad eliminada.');
    } catch {
      toast.error('No se pudo eliminar.');
    }
  };

  if (cargando) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
        <CircularProgress size={22} sx={{ color: '#586AD0' }} />
      </Box>
    );
  }

  return (
    <Box>
      <Stack direction="row" alignItems="flex-start" justifyContent="space-between" sx={{ mb: 2.5 }}>
        <Typography sx={{ color: textMuted, fontSize: '0.9375rem', maxWidth: 560 }}>
          Una Habilidad es un bloque de instrucciones que se escribe una vez y se le engancha a
          varios agentes. Cámbiela acá y cambia en todos los que la usan.
        </Typography>
        <Button
          variant="contained" size="small" startIcon={<Plus size={15} />}
          onClick={abrirNueva} sx={{ flexShrink: 0, textTransform: 'none' }}
        >
          Nueva Habilidad
        </Button>
      </Stack>

      {habilidades.length === 0 ? (
        <Box sx={{
          p: 4, textAlign: 'center', borderRadius: '10px',
          border: `1px dashed ${theme.palette.divider}`,
        }}>
          <Sparkles size={20} color={textMuted} strokeWidth={1.75} />
          <Typography sx={{ fontSize: '0.9375rem', mt: 1 }}>Todavía no hay Habilidades</Typography>
          <Typography sx={{ color: textMuted, fontSize: '0.875rem', mt: 0.5 }}>
            Una buena primera: el tono con el que la empresa le escribe a sus clientes.
          </Typography>
        </Box>
      ) : (
        <Stack spacing={1.25}>
          {habilidades.map((h) => (
            <Box
              key={h.id}
              onClick={() => abrirExistente(h)}
              sx={{
                p: 2, borderRadius: '10px', cursor: 'pointer',
                border: `1px solid ${theme.palette.divider}`,
                '&:hover': { bgcolor: d ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.02)' },
              }}
            >
              <Stack direction="row" alignItems="center" justifyContent="space-between">
                <Typography sx={{ fontSize: '0.9375rem', fontWeight: 600 }}>{h.name}</Typography>
                <IconButton
                  size="small"
                  onClick={(e) => { e.stopPropagation(); borrar(h); }}
                  aria-label={`Eliminar ${h.name}`}
                >
                  <Trash2 size={14} color={textMuted} />
                </IconButton>
              </Stack>
              {h.description && (
                <Typography sx={{ color: textMuted, fontSize: '0.875rem', mt: 0.25 }}>
                  {h.description}
                </Typography>
              )}
              <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap sx={{ mt: 1 }}>
                {(h.agents || []).length === 0 ? (
                  <Typography sx={{ color: textMuted, fontSize: '0.8rem', fontStyle: 'italic' }}>
                    Todavía no la usa ningún agente.
                  </Typography>
                ) : (
                  h.agents.map((a) => (
                    <Chip key={a.id} size="small" label={`@${a.handle}`} sx={{ fontSize: '0.72rem' }} />
                  ))
                )}
              </Stack>
            </Box>
          ))}
        </Stack>
      )}

      <Dialog open={Boolean(editando)} onClose={() => setEditando(null)} fullWidth maxWidth="sm">
        <DialogTitle sx={{ fontSize: '1rem', fontWeight: 600 }}>
          {editando?.id ? editando.name : 'Nueva Habilidad'}
        </DialogTitle>
        <DialogContent>
          {editando && (
            <Stack spacing={2} sx={{ pt: 1 }}>
              <TextField
                label="Nombre" size="small" fullWidth autoFocus
                placeholder="Tono de voz corporativo"
                value={editando.name}
                onChange={(e) => setEditando({ ...editando, name: e.target.value })}
              />
              <TextField
                label="Para qué sirve" size="small" fullWidth
                value={editando.description}
                onChange={(e) => setEditando({ ...editando, description: e.target.value })}
              />
              <TextField
                label="Instrucciones" size="small" fullWidth multiline rows={6}
                placeholder="Escriba en español neutro, tratando de usted. Nunca prometa plazos…"
                value={editando.instructions}
                onChange={(e) => setEditando({ ...editando, instructions: e.target.value })}
              />
              <TextField
                select label="Qué agentes la usan" size="small" fullWidth
                SelectProps={{
                  multiple: true, value: editando.agent_ids,
                  onChange: (e) => setEditando({ ...editando, agent_ids: e.target.value }),
                  renderValue: (ids) => agentes
                    .filter((a) => ids.includes(a.id))
                    .map((a) => a.name).join(', ') || 'Ninguno todavía',
                }}
              >
                {agentes.map((a) => (
                  <MenuItem key={a.id} value={a.id} sx={{ fontSize: '0.85rem' }}>{a.name}</MenuItem>
                ))}
              </TextField>
            </Stack>
          )}
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setEditando(null)} sx={{ textTransform: 'none' }}>Cancelar</Button>
          <Button
            variant="contained" onClick={guardar} sx={{ textTransform: 'none' }}
            disabled={guardando || !editando?.name?.trim() || !editando?.instructions?.trim()}
          >
            Guardar
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
