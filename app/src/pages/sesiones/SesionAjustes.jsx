import { useCallback, useEffect, useState } from 'react';
import {
  Alert, Box, Button, Chip, Divider, IconButton, MenuItem,
  Select, Stack, TextField, Typography, useTheme,
} from '@mui/material';
import { Archive, Globe, Lock, Trash2, UserPlus } from 'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../../services/api';

const DISPLAY = `'Sora', 'Inter', sans-serif`;

const Etiqueta = ({ children }) => (
  <Typography sx={{
    fontSize: '0.6875rem', fontWeight: 700, letterSpacing: '0.08em',
    textTransform: 'uppercase', color: '#586AD0', mb: 1.25,
  }}>
    {children}
  </Typography>
);

/**
 * Los Ajustes de una Sesión: nombre, descripción, quién entra, quién participa, y la
 * zona de riesgo.
 *
 * Solo un editor de la Sesión llega acá con permiso de escritura (el backend responde
 * 403 si no), y borrar exige ser administrador del Workspace: archivar la saca de la
 * vista, borrar se lleva el trabajo del equipo.
 */
export default function SesionAjustes({ sesion, slug, onCambio, onBorrada }) {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const textMuted = d ? 'rgba(255,255,255,0.66)' : 'rgba(0,0,0,0.62)';
  const bgSuave = d ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.02)';
  const borde = theme.palette.divider;

  const puedo = sesion.puedo_administrar;

  const [form, setForm] = useState({
    name: sesion.name, description: sesion.description || '', icon: sesion.icon || '',
    instrucciones_para_agentes: sesion.instrucciones_para_agentes || '',
  });
  const [agentes, setAgentes] = useState([]);
  const [habilidades, setHabilidades] = useState([]);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState('');
  const [disponibles, setDisponibles] = useState([]);
  const [aAgregar, setAAgregar] = useState('');
  const [confirmando, setConfirmando] = useState(false);

  const campoSx = {
    '& .MuiOutlinedInput-root': {
      bgcolor: bgSuave, borderRadius: '8px', fontSize: '0.9375rem',
      '& fieldset': { borderColor: borde },
      '&.Mui-focused fieldset': { borderColor: '#586AD0' },
    },
  };

  const cargarDisponibles = useCallback(async () => {
    if (!slug || !puedo) return;
    try {
      const { data } = await api.getSesionDisponibles(sesion.slug, slug);
      setDisponibles(data.personas || []);
      setAgentes(data.agentes || []);
      setHabilidades(data.habilidades || []);
    } catch { /* la lista de a quién agregar es accesoria */ }
  }, [sesion.slug, slug, puedo]);

  useEffect(() => { cargarDisponibles(); }, [cargarDisponibles]);

  const guardar = async (extra = {}) => {
    try {
      setGuardando(true);
      setError('');
      const { data } = await api.updateSesion(sesion.slug, { workspace: slug, ...form, ...extra });
      onCambio(data);
      // La barra lateral tiene la lista de Sesiones: sin este aviso, renombrar o
      // archivar no se refleja hasta recargar la página.
      window.dispatchEvent(new Event('afable-sesiones'));
      toast.success('Sesión actualizada.');
    } catch (e) {
      setError(e.response?.data?.detail || 'No se pudo guardar.');
    } finally {
      setGuardando(false);
    }
  };

  const agregar = async () => {
    if (!aAgregar) return;
    try {
      const { data } = await api.addSesionMiembros(sesion.slug, {
        workspace: slug, ids: [aAgregar],
      });
      onCambio(data);
      setAAgregar('');
      await cargarDisponibles();
    } catch (e) {
      setError(e.response?.data?.detail || 'No se pudo agregar.');
    }
  };

  const sacar = async (id) => {
    try {
      const { data } = await api.removeSesionMiembros(sesion.slug, { workspace: slug, ids: [id] });
      onCambio(data);
      await cargarDisponibles();
    } catch {
      setError('No se pudo sacar a esa persona.');
    }
  };

  const cambiarRol = async (id, role) => {
    try {
      const { data } = await api.addSesionMiembros(sesion.slug, {
        workspace: slug, ids: [id], role,
      });
      onCambio(data);
    } catch {
      setError('No se pudo cambiar el rol.');
    }
  };

  const borrar = async () => {
    try {
      await api.deleteSesion(sesion.slug, slug);
      window.dispatchEvent(new Event('afable-sesiones'));
      toast.success('Sesión eliminada.');
      onBorrada();
    } catch (e) {
      setError(
        e.response?.status === 403
          ? 'Solo un administrador del Workspace puede eliminar una Sesión.'
          : 'No se pudo eliminar.',
      );
      setConfirmando(false);
    }
  };

  if (!puedo) {
    return (
      <Box sx={{ px: { xs: 2.5, sm: 4 }, pt: 2, pb: 6, maxWidth: 760 }}>
        <Typography sx={{ fontSize: '0.9375rem', color: textMuted }}>
          Solo un editor de esta Sesión cambia su configuración. Usted entra como
          miembro: puede conversar, tomar tareas y dejar archivos.
        </Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ px: { xs: 2.5, sm: 4 }, pt: 2, pb: 6, maxWidth: 760, width: '100%' }}>
      {error && <Alert severity="error" sx={{ mb: 2.5 }} onClose={() => setError('')}>{error}</Alert>}

      <Etiqueta>Nombre</Etiqueta>
      <Stack direction="row" spacing={1.25} sx={{ mb: 3 }}>
        <TextField
          value={form.icon}
          onChange={(e) => setForm({ ...form, icon: e.target.value })}
          placeholder="💠" size="small"
          sx={{ ...campoSx, width: 74, '& input': { textAlign: 'center', fontSize: '1.1rem' } }}
        />
        <TextField
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
          fullWidth size="small" sx={campoSx}
        />
      </Stack>

      <Etiqueta>De qué se trata</Etiqueta>
      <TextField
        value={form.description}
        onChange={(e) => setForm({ ...form, description: e.target.value })}
        placeholder="Un cliente, un proyecto, un cierre de mes…"
        multiline minRows={3} fullWidth size="small" sx={{ ...campoSx, mb: 2 }}
      />
      <Button
        onClick={() => guardar()} variant="contained" disabled={guardando || !form.name.trim()}
        sx={{ textTransform: 'none', borderRadius: '8px', fontWeight: 600, px: 3, mb: 4 }}
      >
        {guardando ? 'Guardando…' : 'Guardar'}
      </Button>

      <Divider sx={{ borderColor: borde, mb: 3 }} />

      {/* Lo que hace que la Sesión no sea una carpeta: lo que le dice a sus agentes. */}
      <Etiqueta>Instrucciones para sus agentes</Etiqueta>
      <Typography sx={{ fontSize: '0.8125rem', color: textMuted, mb: 1.5, mt: -0.75 }}>
        Lo ven TODOS los agentes que trabajen en esta Sesión, además de sus propias
        instrucciones. Por ejemplo: «acá hablamos del cliente Rever; nunca prometas
        fechas de entrega».
      </Typography>
      <TextField
        value={form.instrucciones_para_agentes}
        onChange={(e) => setForm({ ...form, instrucciones_para_agentes: e.target.value })}
        placeholder="Lo que cualquier agente debe saber al trabajar acá…"
        multiline minRows={4} fullWidth size="small" sx={{ ...campoSx, mb: 2 }}
      />
      <Button
        onClick={() => guardar()} variant="contained" disabled={guardando}
        sx={{ textTransform: 'none', borderRadius: '8px', fontWeight: 600, px: 3, mb: 4 }}
      >
        {guardando ? 'Guardando…' : 'Guardar instrucciones'}
      </Button>

      <Divider sx={{ borderColor: borde, mb: 3 }} />

      <Etiqueta>Con quién contesta</Etiqueta>
      <Typography sx={{ fontSize: '0.8125rem', color: textMuted, mb: 1.5, mt: -0.75 }}>
        El agente que toma un hilo nuevo si nadie eligió otro. Una mención con @ le gana
        siempre.
      </Typography>
      <Select
        size="small" displayEmpty value={sesion.agente_por_defecto || ''}
        onChange={(e) => guardar({ agente_por_defecto: e.target.value || null })}
        sx={{ fontSize: '0.8125rem', minWidth: 260, mb: 4 }}
      >
        <MenuItem value="" sx={{ fontSize: '0.8125rem' }}>El de siempre</MenuItem>
        {agentes.map((a) => (
          <MenuItem key={a.id} value={a.id} sx={{ fontSize: '0.8125rem' }}>{a.name}</MenuItem>
        ))}
      </Select>

      <Divider sx={{ borderColor: borde, mb: 3 }} />

      <Etiqueta>Habilidades que aplica siempre</Etiqueta>
      <Typography sx={{ fontSize: '0.8125rem', color: textMuted, mb: 1.5, mt: -0.75 }}>
        Se suman a las que cada agente ya trae. Se crean en Admin › Agentes › Habilidades.
      </Typography>
      {habilidades.length === 0 ? (
        <Typography sx={{ fontSize: '0.875rem', color: textMuted, fontStyle: 'italic', mb: 4 }}>
          Todavía no hay habilidades en esta empresa.
        </Typography>
      ) : (
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 4 }}>
          {habilidades.map((h) => {
            const activa = (sesion.habilidad_ids || []).includes(h.id);
            return (
              <Chip
                key={h.id} label={h.name}
                onClick={() => guardar({
                  habilidad_ids: activa
                    ? (sesion.habilidad_ids || []).filter((i) => i !== h.id)
                    : [...(sesion.habilidad_ids || []), h.id],
                })}
                variant={activa ? 'filled' : 'outlined'}
                sx={{
                  borderRadius: '8px', fontSize: '0.8125rem', cursor: 'pointer',
                  ...(activa
                    ? { bgcolor: 'rgba(88, 106, 208, 0.16)', color: '#586AD0', border: '1px solid rgba(88, 106, 208, 0.4)', fontWeight: 600 }
                    : { borderColor: borde, color: textMuted }),
                }}
              />
            );
          })}
        </Box>
      )}

      <Divider sx={{ borderColor: borde, mb: 3 }} />

      <Etiqueta>Quién entra</Etiqueta>
      <Stack direction="row" spacing={1.5} alignItems="center" sx={{ mb: 1 }}>
        <Chip
          size="small" variant="outlined"
          icon={sesion.visibility === 'abierta' ? <Globe size={13} /> : <Lock size={13} />}
          label={sesion.visibility === 'abierta'
            ? 'Cualquiera del Workspace'
            : `Solo ${sesion.miembros.length} persona${sesion.miembros.length === 1 ? '' : 's'}`}
        />
        <Select
          size="small" value={sesion.visibility}
          onChange={(e) => guardar({ visibility: e.target.value })}
          sx={{ fontSize: '0.8125rem', minWidth: 160 }}
        >
          <MenuItem value="abierta" sx={{ fontSize: '0.8125rem' }}>Abierta</MenuItem>
          <MenuItem value="restringida" sx={{ fontSize: '0.8125rem' }}>Restringida</MenuItem>
        </Select>
      </Stack>
      <Typography sx={{ fontSize: '0.8125rem', color: textMuted, mb: 4 }}>
        Abierta, cualquier miembro del Workspace la encuentra y entra. Restringida, solo
        quien esté en la lista de abajo.
      </Typography>

      <Divider sx={{ borderColor: borde, mb: 3 }} />

      <Etiqueta>Quiénes participan</Etiqueta>
      <Stack spacing={1} sx={{ mb: 2 }}>
        {sesion.miembros.map((m) => (
          <Stack key={m.id} direction="row" spacing={1.25} alignItems="center"
            sx={{ p: 1.25, borderRadius: '8px', bgcolor: bgSuave, border: `1px solid ${borde}` }}>
            <Box sx={{ flex: 1, minWidth: 0 }}>
              <Typography sx={{ fontSize: '0.9375rem', fontWeight: 600 }}>{m.name}</Typography>
              <Typography sx={{ fontSize: '0.8125rem', color: textMuted }}>{m.email}</Typography>
            </Box>
            <Select
              size="small" value={m.role}
              onChange={(e) => cambiarRol(m.id, e.target.value)}
              sx={{ fontSize: '0.8rem', minWidth: 112 }}
            >
              <MenuItem value="miembro" sx={{ fontSize: '0.8rem' }}>Miembro</MenuItem>
              <MenuItem value="editor" sx={{ fontSize: '0.8rem' }}>Editor</MenuItem>
            </Select>
            <IconButton onClick={() => sacar(m.id)} title="Sacar de la Sesión" size="small">
              <Trash2 size={15} />
            </IconButton>
          </Stack>
        ))}
        {sesion.miembros.length === 0 && (
          <Typography sx={{ fontSize: '0.875rem', color: textMuted, fontStyle: 'italic' }}>
            Nadie agregado todavía.
          </Typography>
        )}
      </Stack>

      {disponibles.length > 0 && (
        <Stack direction="row" spacing={1.25} sx={{ mb: 4 }}>
          <Select
            size="small" displayEmpty value={aAgregar}
            onChange={(e) => setAAgregar(e.target.value)}
            sx={{ fontSize: '0.8125rem', minWidth: 240 }}
          >
            <MenuItem value="" sx={{ fontSize: '0.8125rem' }}>Elegir a alguien del Workspace…</MenuItem>
            {disponibles.map((p) => (
              <MenuItem key={p.id} value={p.id} sx={{ fontSize: '0.8125rem' }}>
                {p.name} · {p.email}
              </MenuItem>
            ))}
          </Select>
          <Button
            onClick={agregar} disabled={!aAgregar} startIcon={<UserPlus size={15} />}
            sx={{ textTransform: 'none', fontWeight: 600 }}
          >
            Agregar
          </Button>
        </Stack>
      )}

      <Divider sx={{ borderColor: borde, mb: 3 }} />

      <Typography sx={{
        fontFamily: DISPLAY, fontSize: '1.0625rem', fontWeight: 600, color: '#e5484d', mb: 2,
      }}>
        Zona de riesgo
      </Typography>

      <Box sx={{ mb: 3 }}>
        <Typography sx={{ fontSize: '0.9375rem', fontWeight: 600, mb: 0.5 }}>
          {sesion.archivada ? 'Desarchivar' : 'Archivar'}
        </Typography>
        <Typography sx={{ fontSize: '0.8125rem', color: textMuted, mb: 1.25 }}>
          {sesion.archivada
            ? 'Vuelve a la barra lateral y al listado.'
            : 'Sale de la barra lateral. Su contenido queda intacto y se puede volver a abrir.'}
        </Typography>
        <Button
          onClick={() => guardar({ archivada: !sesion.archivada })}
          startIcon={<Archive size={15} />}
          sx={{ textTransform: 'none', fontWeight: 600, color: '#f0b429' }}
        >
          {sesion.archivada ? 'Desarchivar' : 'Archivar'}
        </Button>
      </Box>

      <Box>
        <Typography sx={{ fontSize: '0.9375rem', fontWeight: 600, mb: 0.5 }}>Eliminar</Typography>
        <Typography sx={{ fontSize: '0.8125rem', color: textMuted, mb: 1.25 }}>
          Se lleva las conversaciones, las tareas y los archivos de esta Sesión. No se
          puede deshacer, y solo lo puede hacer un administrador del Workspace.
        </Typography>
        {!confirmando ? (
          <Button
            onClick={() => setConfirmando(true)} startIcon={<Trash2 size={15} />}
            sx={{ textTransform: 'none', fontWeight: 600, color: '#e5484d' }}
          >
            Eliminar la Sesión
          </Button>
        ) : (
          <Stack direction="row" spacing={1} alignItems="center">
            <Typography sx={{ fontSize: '0.875rem', fontWeight: 600 }}>
              ¿Seguro? Esto no se deshace.
            </Typography>
            <Button
              onClick={borrar} variant="contained"
              sx={{ textTransform: 'none', fontWeight: 600, bgcolor: '#e5484d', '&:hover': { bgcolor: '#c93b3f' } }}
            >
              Sí, eliminar
            </Button>
            <Button onClick={() => setConfirmando(false)} sx={{ textTransform: 'none', color: textMuted }}>
              Cancelar
            </Button>
          </Stack>
        )}
      </Box>
    </Box>
  );
}
