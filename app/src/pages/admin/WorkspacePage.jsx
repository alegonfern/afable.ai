import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Box, Button, CircularProgress, Dialog, DialogContent, DialogTitle,
  IconButton, MenuItem, TextField, Typography, useTheme,
} from '@mui/material';
import { Building2, Plus, Users, X } from 'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../../services/api';
import { useWorkspace } from '../../context/WorkspaceContext';

const POLITICAS = [
  { value: 'todos', label: 'Todos los miembros' },
  { value: 'editores', label: 'Editores y administradores' },
  { value: 'admins', label: 'Solo administradores' },
];

const DISPLAY = `'Sora', 'Inter', sans-serif`;

/**
 * Workspace: el entorno de la empresa. **Uno por empresa, 1 a 1.**
 *
 * Reemplaza a la pantalla "Mis Empresas", que administraba el modelo Organization y
 * trataba las empresas como una lista. Aca no se coleccionan Workspace: son los
 * ajustes de SU empresa. Lo que se crea y se recorre dentro de ella son los
 * Espacios (conocimiento y permisos) y las Salas.
 *
 * Lo que se edita aca el backend lo refleja en la Organization enlazada, mientras el
 * chat, las conexiones y los documentos sigan colgando de ella
 * (ver Workspace.mirror_to_organization).
 */
export default function WorkspacePage() {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const { workspace, slug, esAdmin, seleccionar, recargar, loading } = useWorkspace();

  const textMuted = d ? 'rgba(255,255,255,0.66)' : 'rgba(0,0,0,0.62)';
  const bgSuave = d ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.02)';
  const borde = theme.palette.divider;

  const [sectores, setSectores] = useState([]);
  const [form, setForm] = useState(null);
  const [guardando, setGuardando] = useState(false);
  const [modalAbierto, setModalAbierto] = useState(false);

  useEffect(() => {
    api.getSectors().then((r) => setSectores(r.data)).catch(() => setSectores([]));
  }, []);

  useEffect(() => {
    if (!workspace) return setForm(null);
    setForm({
      name: workspace.name || '',
      sector: workspace.sector || '',
      employees: workspace.employees || '',
      tax_id: workspace.tax_id || '',
      description: workspace.description || '',
      agent_creation_policy: workspace.agent_creation_policy || 'editores',
    });
  }, [workspace]);

  const guardar = useCallback(async () => {
    if (!form.name.trim()) {
      toast.error('El Workspace necesita un nombre.');
      return;
    }
    try {
      setGuardando(true);
      await api.updateWorkspace(slug, form);
      await recargar();
      toast.success('Workspace actualizado.');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'No se pudo guardar.');
    } finally {
      setGuardando(false);
    }
  }, [form, slug, recargar]);

  const campoSx = {
    '& .MuiOutlinedInput-root': {
      bgcolor: bgSuave,
      borderRadius: '8px',
      fontSize: '0.875rem',
      '& fieldset': { borderColor: borde },
      '&.Mui-focused fieldset': { borderColor: '#586AD0' },
    },
    '& .MuiInputLabel-root': { fontSize: '0.875rem', color: textMuted },
    '& .MuiInputLabel-root.Mui-focused': { color: '#9BA6E3' },
  };

  if (loading || (workspace && !form)) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', pt: 12 }}>
        <CircularProgress size={26} sx={{ color: '#586AD0' }} />
      </Box>
    );
  }

  return (
    <Box sx={{ maxWidth: 1000, mx: 'auto', px: { xs: 2.5, md: 5 }, py: { xs: 4, md: 6 }, width: '100%' }}>
      <Building2 size={24} color={textMuted} strokeWidth={1.75} />
      <Typography sx={{ fontFamily: DISPLAY, fontSize: '1.875rem', fontWeight: 600, mt: 1.5, letterSpacing: '-0.01em' }}>
        Workspace
      </Typography>
      <Typography sx={{ color: textMuted, fontSize: '0.9375rem', mt: 0.75 }}>
        El entorno de su empresa: sus datos, sus miembros y quién puede crear agentes.
      </Typography>

      {!workspace ? (
        <Box sx={{ mt: 4 }}>
          <Typography sx={{ color: textMuted, fontSize: '0.875rem' }}>
            Todavía no tiene un Workspace. Cree el de su empresa para empezar.
          </Typography>
          <Button
            onClick={() => setModalAbierto(true)}
            startIcon={<Plus size={15} />}
            variant="contained"
            sx={{ mt: 2, borderRadius: '8px', textTransform: 'none', fontWeight: 600 }}
          >
            Crear el Workspace
          </Button>
        </Box>
      ) : (
        <>
          {!esAdmin && (
            <Typography sx={{ color: textMuted, fontSize: '0.875rem', mt: 3 }}>
              Su rol en este Workspace es {workspace.my_role}: puede ver estos datos, pero solo un
              administrador los edita.
            </Typography>
          )}

          <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, mt: 3.5 }}>
            <TextField
              label="Nombre"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              disabled={!esAdmin}
              size="small" sx={campoSx}
            />
            <TextField
              select
              label="Sector"
              value={sectores.some((s) => s.value === form.sector) ? form.sector : ''}
              onChange={(e) => setForm({ ...form, sector: e.target.value })}
              disabled={!esAdmin}
              size="small" sx={campoSx}
            >
              {sectores.map((s) => (
                <MenuItem key={s.value} value={s.value} sx={{ fontSize: '0.875rem' }}>
                  {s.label}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              label="Número de personas"
              value={form.employees}
              onChange={(e) => setForm({ ...form, employees: e.target.value })}
              disabled={!esAdmin}
              placeholder="Ej: 25"
              size="small" sx={campoSx}
            />
            <TextField
              label="RUT / NIF"
              value={form.tax_id}
              onChange={(e) => setForm({ ...form, tax_id: e.target.value })}
              disabled={!esAdmin}
              placeholder="Ej: 76.123.456-7"
              size="small" sx={campoSx}
            />
          </Box>

          <TextField
            label="Qué hace la empresa"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            disabled={!esAdmin}
            placeholder="Los agentes usan esta descripción para entender su operación."
            multiline minRows={3}
            fullWidth size="small"
            sx={{ ...campoSx, mt: 2 }}
          />

          <Typography sx={{ fontSize: '0.6875rem', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: '#586AD0', mt: 4, mb: 1.5 }}>
            Quién puede crear agentes
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75 }}>
            {POLITICAS.map((p) => {
              const activa = form.agent_creation_policy === p.value;
              return (
                <Box
                  key={p.value}
                  component="button"
                  disabled={!esAdmin}
                  onClick={() => esAdmin && setForm({ ...form, agent_creation_policy: p.value })}
                  sx={{
                    cursor: esAdmin ? 'pointer' : 'default',
                    px: 1.75, py: 0.875, borderRadius: '8px',
                    fontFamily: 'inherit', fontSize: '0.875rem',
                    fontWeight: activa ? 600 : 500,
                    color: activa ? (d ? '#9BA6E3' : '#2F42A6') : theme.palette.text.secondary,
                    bgcolor: activa ? 'rgba(88, 106, 208, 0.12)' : 'transparent',
                    border: `1px solid ${activa ? 'rgba(88, 106, 208, 0.35)' : borde}`,
                  }}
                >
                  {p.label}
                </Box>
              );
            })}
          </Box>

          {/* Los miembros se administran en Personas, no acá: una sola pantalla para eso. */}
          <Box
            sx={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              gap: 2, mt: 4, p: 2, borderRadius: '10px', border: `1px solid ${borde}`, bgcolor: bgSuave,
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
              <Users size={18} color={textMuted} />
              <Box>
                <Typography sx={{ fontSize: '0.875rem', fontWeight: 600 }}>
                  {workspace.member_count} {workspace.member_count === 1 ? 'persona' : 'personas'}
                </Typography>
                <Typography sx={{ fontSize: '0.875rem', color: textMuted }}>
                  Los miembros, sus roles y las invitaciones se administran en Personas.
                </Typography>
              </Box>
            </Box>
            <Button
              component={Link}
              to="/app/admin/personas"
              sx={{ textTransform: 'none', fontSize: '0.875rem', fontWeight: 600, whiteSpace: 'nowrap' }}
            >
              Ir a Personas
            </Button>
          </Box>

          {esAdmin && (
            <Button
              onClick={guardar}
              disabled={guardando}
              variant="contained"
              sx={{ mt: 3.5, borderRadius: '8px', textTransform: 'none', fontWeight: 600, px: 3 }}
            >
              {guardando ? 'Guardando…' : 'Guardar cambios'}
            </Button>
          )}
        </>
      )}

      <ModalNuevoWorkspace
        abierto={modalAbierto}
        cerrar={() => setModalAbierto(false)}
        sectores={sectores}
        alCrear={async (nuevo) => {
          await recargar();
          seleccionar(nuevo.slug);
        }}
      />
    </Box>
  );
}

function ModalNuevoWorkspace({ abierto, cerrar, sectores, alCrear }) {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const textMuted = d ? 'rgba(255,255,255,0.66)' : 'rgba(0,0,0,0.62)';

  const [nombre, setNombre] = useState('');
  const [sector, setSector] = useState('');
  const [creando, setCreando] = useState(false);

  useEffect(() => {
    if (abierto) {
      setNombre('');
      setSector('');
    }
  }, [abierto]);

  const crear = async () => {
    if (!nombre.trim()) return;
    try {
      setCreando(true);
      const { data } = await api.createWorkspace({ name: nombre.trim(), sector });
      toast.success(`Workspace ${data.name} creado.`);
      cerrar();
      alCrear(data);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'No se pudo crear el Workspace.');
    } finally {
      setCreando(false);
    }
  };

  return (
    <Dialog open={abierto} onClose={cerrar} maxWidth="xs" fullWidth>
      <DialogTitle
        sx={{
          fontFamily: DISPLAY, fontSize: '1.125rem', fontWeight: 600,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}
      >
        Nuevo Workspace
        <IconButton size="small" onClick={cerrar} sx={{ color: textMuted }}>
          <X size={16} />
        </IconButton>
      </DialogTitle>
      <DialogContent>
        <Typography sx={{ color: textMuted, fontSize: '0.875rem', mb: 2 }}>
          Queda como administrador y puede invitar personas desde Personas.
        </Typography>
        <TextField
          value={nombre}
          onChange={(e) => setNombre(e.target.value)}
          placeholder="Nombre de la empresa"
          fullWidth size="small" autoFocus
          onKeyDown={(e) => e.key === 'Enter' && crear()}
          sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px', fontSize: '0.875rem' } }}
        />
        <TextField
          select
          value={sector}
          onChange={(e) => setSector(e.target.value)}
          label="Sector"
          fullWidth size="small"
          sx={{ mt: 2, '& .MuiOutlinedInput-root': { borderRadius: '8px', fontSize: '0.875rem' } }}
        >
          {sectores.map((s) => (
            <MenuItem key={s.value} value={s.value} sx={{ fontSize: '0.875rem' }}>
              {s.label}
            </MenuItem>
          ))}
        </TextField>
        <Button
          onClick={crear}
          disabled={creando || !nombre.trim()}
          fullWidth variant="contained"
          sx={{ mt: 3, mb: 1, borderRadius: '8px', textTransform: 'none', fontWeight: 600 }}
        >
          {creando ? 'Creando…' : 'Crear Workspace'}
        </Button>
      </DialogContent>
    </Dialog>
  );
}
