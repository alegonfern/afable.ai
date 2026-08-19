import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Box, Button, CircularProgress, Dialog, DialogContent, DialogTitle,
  IconButton, Menu, MenuItem, TextField, Typography, useTheme,
} from '@mui/material';
import {
  Check, MoreHorizontal, Plus, RefreshCw, Search, Trash2, Users, X,
} from 'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../../services/api';
import { useApp } from '../../context/AppContext';
import { useWorkspace } from '../../context/WorkspaceContext';

const ROLES = [
  { value: 'miembro', label: 'Miembro' },
  { value: 'editor', label: 'Editor' },
  { value: 'admin', label: 'Administrador' },
];

const etiquetaRol = (valor) => (ROLES.find((r) => r.value === valor) || {}).label || valor;

const DISPLAY = `'Sora', 'Inter', sans-serif`;

export default function PersonasPage() {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const { slug, workspace, esAdmin, loading: cargandoWorkspace } = useWorkspace();
  const { currentUser } = useApp();

  const textMuted = d ? 'rgba(255,255,255,0.66)' : 'rgba(0,0,0,0.62)';
  const textSemi = d ? 'rgba(255,255,255,0.82)' : 'rgba(0,0,0,0.76)';
  const bgSuave = d ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.02)';
  const bgSegmentado = d ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.04)';
  const bgActivo = d ? '#000000' : '#ffffff';
  const borde = theme.palette.divider;

  const [pestana, setPestana] = useState('miembros');
  const [busqueda, setBusqueda] = useState('');
  const [miembros, setMiembros] = useState([]);
  const [invitaciones, setInvitaciones] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [modalAbierto, setModalAbierto] = useState(false);
  const [menu, setMenu] = useState({ anchor: null, membresia: null });

  const cargar = useCallback(async () => {
    if (!slug) return;
    try {
      setCargando(true);
      const pedidos = [api.getMembers(slug)];
      if (esAdmin) pedidos.push(api.getInvitations(slug));
      const [resMiembros, resInvitaciones] = await Promise.all(pedidos);
      setMiembros(resMiembros.data);
      setInvitaciones(resInvitaciones ? resInvitaciones.data : []);
    } catch {
      toast.error('No se pudieron cargar las personas de la Empresa.');
    } finally {
      setCargando(false);
    }
  }, [slug, esAdmin]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const filtrados = useMemo(() => {
    const q = busqueda.trim().toLowerCase();
    if (!q) return miembros;
    return miembros.filter(
      (m) =>
        m.user.email.toLowerCase().includes(q) ||
        (m.user.full_name || '').toLowerCase().includes(q),
    );
  }, [miembros, busqueda]);

  const invitacionesFiltradas = useMemo(() => {
    const q = busqueda.trim().toLowerCase();
    if (!q) return invitaciones;
    return invitaciones.filter((i) => i.email.toLowerCase().includes(q));
  }, [invitaciones, busqueda]);

  const cambiarRol = async (membresia, rol) => {
    setMenu({ anchor: null, membresia: null });
    if (membresia.role === rol) return;
    try {
      await api.updateMemberRole(slug, membresia.id, rol);
      toast.success(`${membresia.user.full_name} ahora es ${etiquetaRol(rol).toLowerCase()}.`);
      cargar();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'No se pudo cambiar el rol.');
    }
  };

  const sacar = async (membresia) => {
    setMenu({ anchor: null, membresia: null });
    try {
      await api.removeMember(slug, membresia.id);
      toast.success(`${membresia.user.full_name} salió de la Empresa.`);
      cargar();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'No se pudo sacar a esa persona.');
    }
  };

  const reenviar = async (invitacion) => {
    try {
      const { data } = await api.resendInvitation(slug, invitacion.id);
      toast[data.emailed ? 'success' : 'warning'](
        data.emailed
          ? `Invitación reenviada a ${invitacion.email}.`
          : 'Invitación renovada, pero el correo no salió.',
      );
      cargar();
    } catch {
      toast.error('No se pudo reenviar la invitación.');
    }
  };

  const revocar = async (invitacion) => {
    try {
      await api.revokeInvitation(slug, invitacion.id);
      toast.success(`Invitación a ${invitacion.email} revocada.`);
      cargar();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'No se pudo revocar la invitación.');
    }
  };

  // ── Piezas visuales ──

  const InsigniaRol = ({ rol }) => {
    const esAdminRol = rol === 'admin';
    return (
      <Box
        component="span"
        sx={{
          display: 'inline-block',
          px: 1,
          py: 0.25,
          borderRadius: '6px',
          fontSize: '0.75rem',
          fontWeight: 600,
          bgcolor: esAdminRol ? 'rgba(88, 106, 208, 0.14)' : bgSegmentado,
          color: esAdminRol ? (d ? '#9BA6E3' : '#2F42A6') : textSemi,
          border: `1px solid ${esAdminRol ? 'rgba(88, 106, 208, 0.28)' : borde}`,
        }}
      >
        {etiquetaRol(rol)}
      </Box>
    );
  };

  const Pestana = ({ valor, children }) => {
    const activa = pestana === valor;
    return (
      <Box
        component="button"
        onClick={() => setPestana(valor)}
        sx={{
          border: 'none',
          cursor: 'pointer',
          px: 1.75,
          py: 0.75,
          borderRadius: '7px',
          fontFamily: 'inherit',
          fontSize: '0.875rem',
          fontWeight: activa ? 600 : 500,
          color: activa ? theme.palette.text.primary : textSemi,
          bgcolor: activa ? bgActivo : 'transparent',
          boxShadow: activa ? (d ? 'none' : '0 1px 2px rgba(0,0,0,0.06)') : 'none',
          transition: 'background-color .15s, color .15s',
        }}
      >
        {children}
      </Box>
    );
  };

  const Celda = ({ children, ancho, alineacion = 'left', encabezado }) => (
    <Box
      sx={{
        flex: ancho,
        minWidth: 0,
        textAlign: alineacion,
        fontSize: encabezado ? '0.8rem' : '0.9375rem',
        fontWeight: encabezado ? 700 : 400,
        color: encabezado ? textSemi : theme.palette.text.primary,
        pr: 2,
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
      }}
    >
      {children}
    </Box>
  );

  if (cargandoWorkspace || (cargando && !miembros.length)) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', pt: 12 }}>
        <CircularProgress size={26} sx={{ color: '#586AD0' }} />
      </Box>
    );
  }

  if (!slug) {
    return (
      <Box sx={{ maxWidth: 860, mx: 'auto', px: 4, py: 8 }}>
        <Typography sx={{ color: textMuted, fontSize: '0.875rem' }}>
          Todavía no pertenece a ningún Workspace.
        </Typography>
      </Box>
    );
  }

  const filas = pestana === 'miembros' ? filtrados : invitacionesFiltradas;

  return (
    <Box sx={{ maxWidth: 1000, mx: 'auto', px: { xs: 2.5, md: 5 }, py: { xs: 4, md: 6 }, width: '100%' }}>
      {/* Encabezado: ícono, título display, subtítulo — el patrón de todas las páginas de Admin */}
      <Users size={24} color={textSemi} strokeWidth={1.75} />
      <Typography
        sx={{ fontFamily: DISPLAY, fontSize: '1.875rem', fontWeight: 600, mt: 1.5, letterSpacing: '-0.01em' }}
      >
        Personas
      </Typography>
      <Typography sx={{ color: textMuted, fontSize: '0.9375rem', mt: 0.75 }}>
        Administre las personas de la Empresa y sus roles.
      </Typography>

      {/* Fila de acción: buscador a la izquierda, acción primaria a la derecha */}
      <Box sx={{ display: 'flex', gap: 1.5, mt: 3, alignItems: 'stretch' }}>
        <TextField
          value={busqueda}
          onChange={(e) => setBusqueda(e.target.value)}
          placeholder="Buscar personas (correo)"
          fullWidth
          size="small"
          InputProps={{
            endAdornment: <Search size={16} color={textMuted} />,
            sx: {
              bgcolor: bgSuave,
              borderRadius: '8px',
              fontSize: '0.875rem',
              '& fieldset': { borderColor: borde },
              '&:hover fieldset': { borderColor: d ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.2)' },
              '&.Mui-focused fieldset': { borderColor: '#586AD0' },
            },
          }}
        />
        {esAdmin && (
          <Button
            onClick={() => setModalAbierto(true)}
            startIcon={<Plus size={16} />}
            sx={{
              flexShrink: 0,
              px: 2,
              borderRadius: '8px',
              textTransform: 'none',
              fontSize: '0.875rem',
              fontWeight: 600,
              whiteSpace: 'nowrap',
              color: d ? '#18181b' : theme.palette.text.primary,
              bgcolor: d ? '#ededed' : '#ffffff',
              border: `1px solid ${d ? 'transparent' : borde}`,
              boxShadow: d ? 'none' : '0 1px 2px rgba(0,0,0,0.06)',
              '&:hover': { bgcolor: d ? '#ffffff' : '#f4f4f3' },
            }}
          >
            Invitar miembros
          </Button>
        )}
      </Box>

      {/* Segmentado Miembros / Invitaciones */}
      <Box
        sx={{
          display: 'inline-flex',
          gap: 0.5,
          mt: 2.5,
          p: 0.5,
          borderRadius: '9px',
          bgcolor: bgSegmentado,
        }}
      >
        <Pestana valor="miembros">Miembros</Pestana>
        {esAdmin && <Pestana valor="invitaciones">Invitaciones</Pestana>}
      </Box>

      {/* Tabla */}
      <Box sx={{ mt: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', pb: 1.25, borderBottom: `1px solid ${borde}` }}>
          {pestana === 'miembros' ? (
            <>
              <Celda ancho={4} encabezado>Nombre</Celda>
              <Celda ancho={4} encabezado>Correo</Celda>
              <Celda ancho={2} encabezado>Rol</Celda>
              <Box sx={{ width: 40, flexShrink: 0 }} />
            </>
          ) : (
            <>
              <Celda ancho={4} encabezado>Correo</Celda>
              <Celda ancho={2} encabezado>Rol</Celda>
              <Celda ancho={3} encabezado>Invitada por</Celda>
              <Celda ancho={2} encabezado>Estado</Celda>
              <Box sx={{ width: 80, flexShrink: 0 }} />
            </>
          )}
        </Box>

        {filas.length === 0 && (
          <Typography sx={{ color: textMuted, fontSize: '0.875rem', py: 3 }}>
            {pestana === 'miembros'
              ? 'Ninguna persona coincide con la búsqueda.'
              : 'No hay invitaciones pendientes.'}
          </Typography>
        )}

        {pestana === 'miembros' &&
          filtrados.map((m) => {
            const soyYo = currentUser && m.user.id === currentUser.id;
            return (
              <Box
                key={m.id}
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  py: 1.5,
                  borderBottom: `1px solid ${borde}`,
                }}
              >
                <Celda ancho={4}>
                  {m.user.full_name}
                  {soyYo && (
                    <Box component="span" sx={{ color: textMuted, ml: 1 }}>
                      (usted)
                    </Box>
                  )}
                </Celda>
                <Celda ancho={4}>{m.user.email}</Celda>
                <Celda ancho={2}>
                  <InsigniaRol rol={m.role} />
                </Celda>
                <Box sx={{ width: 40, flexShrink: 0, textAlign: 'right' }}>
                  {esAdmin && (
                    <IconButton
                      size="small"
                      onClick={(e) => setMenu({ anchor: e.currentTarget, membresia: m })}
                      sx={{ color: textMuted }}
                    >
                      <MoreHorizontal size={16} />
                    </IconButton>
                  )}
                </Box>
              </Box>
            );
          })}

        {pestana === 'invitaciones' &&
          invitacionesFiltradas.map((i) => (
            <Box
              key={i.id}
              sx={{ display: 'flex', alignItems: 'center', py: 1.5, borderBottom: `1px solid ${borde}` }}
            >
              <Celda ancho={4}>{i.email}</Celda>
              <Celda ancho={2}>
                <InsigniaRol rol={i.role} />
              </Celda>
              <Celda ancho={3}>{i.invited_by_name || '—'}</Celda>
              <Celda ancho={2}>
                <Box component="span" sx={{ color: i.status === 'vencida' ? '#d97706' : textSemi, fontSize: '0.875rem' }}>
                  {i.status === 'vencida' ? 'Vencida' : 'Pendiente'}
                </Box>
              </Celda>
              <Box sx={{ width: 80, flexShrink: 0, textAlign: 'right' }}>
                <IconButton size="small" onClick={() => reenviar(i)} title="Reenviar" sx={{ color: textMuted }}>
                  <RefreshCw size={15} />
                </IconButton>
                <IconButton size="small" onClick={() => revocar(i)} title="Revocar" sx={{ color: textMuted }}>
                  <Trash2 size={15} />
                </IconButton>
              </Box>
            </Box>
          ))}

        {/* Contador al pie, alineado a la derecha */}
        <Typography sx={{ color: textMuted, fontSize: '0.75rem', textAlign: 'right', mt: 1.5 }}>
          {filas.length} {filas.length === 1 ? 'ítem' : 'ítems'}
        </Typography>
      </Box>

      {/* Menú de fila: cambiar rol o sacar del Workspace */}
      <Menu
        anchorEl={menu.anchor}
        open={Boolean(menu.anchor)}
        onClose={() => setMenu({ anchor: null, membresia: null })}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        transformOrigin={{ vertical: 'top', horizontal: 'right' }}
      >
        {ROLES.map((r) => (
          <MenuItem
            key={r.value}
            onClick={() => cambiarRol(menu.membresia, r.value)}
            sx={{ fontSize: '0.875rem', gap: 1 }}
          >
            <Box sx={{ width: 16, display: 'flex' }}>
              {menu.membresia && menu.membresia.role === r.value && <Check size={14} color="#586AD0" />}
            </Box>
            {r.label}
          </MenuItem>
        ))}
        <MenuItem
          onClick={() => sacar(menu.membresia)}
          sx={{ fontSize: '0.875rem', gap: 1, color: '#dc2626', borderTop: `1px solid ${borde}`, mt: 0.5 }}
        >
          <Box sx={{ width: 16, display: 'flex' }}>
            <Trash2 size={14} />
          </Box>
          Sacar del Workspace
        </MenuItem>
      </Menu>

      <ModalInvitar
        abierto={modalAbierto}
        cerrar={() => setModalAbierto(false)}
        slug={slug}
        alInvitar={cargar}
      />
    </Box>
  );
}

function ModalInvitar({ abierto, cerrar, slug, alInvitar }) {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const textMuted = d ? 'rgba(255,255,255,0.66)' : 'rgba(0,0,0,0.62)';
  const borde = theme.palette.divider;

  const [correo, setCorreo] = useState('');
  const [rol, setRol] = useState('miembro');
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    if (abierto) {
      setCorreo('');
      setRol('miembro');
    }
  }, [abierto]);

  const enviar = async () => {
    if (!correo.trim()) return;
    try {
      setEnviando(true);
      const { data } = await api.createInvitation(slug, { email: correo.trim(), role: rol });
      if (data.emailed) {
        toast.success(`Invitación enviada a ${data.email}.`);
      } else {
        toast.warning(`Invitación creada, pero el correo a ${data.email} no salió.`);
      }
      cerrar();
      alInvitar();
    } catch (e) {
      const detalle = e.response?.data;
      toast.error(detalle?.email?.[0] || detalle?.detail || 'No se pudo enviar la invitación.');
    } finally {
      setEnviando(false);
    }
  };

  return (
    <Dialog open={abierto} onClose={cerrar} maxWidth="xs" fullWidth>
      <DialogTitle
        sx={{
          fontFamily: DISPLAY,
          fontSize: '1.125rem',
          fontWeight: 600,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        Invitar miembros
        <IconButton size="small" onClick={cerrar} sx={{ color: textMuted }}>
          <X size={16} />
        </IconButton>
      </DialogTitle>
      <DialogContent>
        <Typography sx={{ color: textMuted, fontSize: '0.875rem', mb: 2 }}>
          Le llega un correo con un enlace para entrar. La invitación vence en 7 días.
        </Typography>

        <TextField
          value={correo}
          onChange={(e) => setCorreo(e.target.value)}
          placeholder="persona@empresa.cl"
          type="email"
          fullWidth
          size="small"
          autoFocus
          onKeyDown={(e) => e.key === 'Enter' && enviar()}
          sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px', fontSize: '0.875rem' } }}
        />

        <Box sx={{ display: 'flex', gap: 0.75, mt: 2 }}>
          {ROLES.map((r) => (
            <Box
              key={r.value}
              component="button"
              onClick={() => setRol(r.value)}
              sx={{
                cursor: 'pointer',
                flex: 1,
                py: 0.75,
                borderRadius: '8px',
                fontFamily: 'inherit',
                fontSize: '0.875rem',
                fontWeight: rol === r.value ? 600 : 500,
                color: rol === r.value ? (d ? '#9BA6E3' : '#2F42A6') : theme.palette.text.secondary,
                bgcolor: rol === r.value ? 'rgba(88, 106, 208, 0.12)' : 'transparent',
                border: `1px solid ${rol === r.value ? 'rgba(88, 106, 208, 0.35)' : borde}`,
              }}
            >
              {r.label}
            </Box>
          ))}
        </Box>

        <Button
          onClick={enviar}
          disabled={enviando || !correo.trim()}
          fullWidth
          variant="contained"
          sx={{ mt: 3, mb: 1, borderRadius: '8px', textTransform: 'none', fontWeight: 600 }}
        >
          {enviando ? 'Enviando…' : 'Enviar invitación'}
        </Button>
      </DialogContent>
    </Dialog>
  );
}
