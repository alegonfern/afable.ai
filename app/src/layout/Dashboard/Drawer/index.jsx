import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import {
  Drawer as MuiDrawer,
  Box,
  Typography,
  Tooltip,
  useTheme,
  useMediaQuery,
  styled,
  Avatar,
  Collapse,
  IconButton,
  Menu,
  MenuItem,
  Divider,
} from '@mui/material';
import {
  MessageSquare, LayoutDashboard, Settings, Search, ChevronLeft, Plus, ChevronDown,
  ChevronRight, Zap, Bot, History,
  User, Building2, HelpCircle, LogOut, Timer, Layers, Users,
} from 'lucide-react';
import { toast } from 'react-toastify';
import { authService } from '../../../services/auth';
import { useNavigate, useLocation } from 'react-router-dom';
import { DRAWER_WIDTH, MINI_DRAWER_WIDTH } from '../../../config';
import { useApp } from '../../../context/AppContext';
import { api } from '../../../services/api';

const openedMixin = (theme) => ({
  width: DRAWER_WIDTH,
  borderRight: `1px solid ${theme.palette.divider}`,
  transition: theme.transitions.create('width', {
    easing: theme.transitions.easing.sharp,
    duration: theme.transitions.duration.enteringScreen,
  }),
  overflowX: 'hidden',
  boxShadow: 'none',
});

const closedMixin = (theme) => ({
  transition: theme.transitions.create('width', {
    easing: theme.transitions.easing.sharp,
    duration: theme.transitions.duration.leavingScreen,
  }),
  overflowX: 'hidden',
  width: MINI_DRAWER_WIDTH,
  borderRight: `1px solid ${theme.palette.divider}`,
});

const DrawerStyled = styled(MuiDrawer, { shouldForwardProp: (p) => p !== 'open' })(
  ({ theme, open }) => ({
    width: DRAWER_WIDTH,
    flexShrink: 0,
    whiteSpace: 'nowrap',
    boxSizing: 'border-box',
    ...(open && { ...openedMixin(theme), '& .MuiDrawer-paper': openedMixin(theme) }),
    ...(!open && { ...closedMixin(theme), '& .MuiDrawer-paper': closedMixin(theme) }),
  })
);

export default function Drawer({ open, handleDrawerToggle }) {
  const theme = useTheme();
  const navigate = useNavigate();
  const location = useLocation();
  const { currentUser } = useApp();
  const matchDownLG = useMediaQuery(theme.breakpoints.down('lg'));
  const d = theme.palette.mode === 'dark';

  const [conversations, setConversations] = useState([]);
  const [chatOpen, setChatOpen] = useState(true);
  const [userMenuAnchor, setUserMenuAnchor] = useState(null);
  const [modo, setModoState] = useState(() => localStorage.getItem('afable_modo') || 'trabajo');

  const setModo = (siguiente) => {
    setModoState(siguiente);
    localStorage.setItem('afable_modo', siguiente);
  };

  const handleLogout = () => {
    authService.logout();
    toast.success('Sesión cerrada');
    navigate('/login');
    setUserMenuAnchor(null);
  };

  useEffect(() => {
    api.getConversations().then(r => setConversations(r.data.slice(0, 10))).catch(() => {});
  }, []);


  // Contraste: los items en reposo estaban al 45% y los iconos al 28% sobre un
  // fondo casi negro — legible a duras penas y cansador. Se sube el piso sin
  // perder la jerarquia con el item activo, que va en indigo.
  const textMuted    = d ? 'rgba(255,255,255,0.74)' : 'rgba(0,0,0,0.70)';
  const textDisabled = d ? 'rgba(255,255,255,0.52)' : 'rgba(0,0,0,0.50)';
  const textActive   = theme.palette.text.primary;
  const bgHover      = d ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.04)';
  const keyHintBg    = d ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.06)';
  const keyHintColor = d ? 'rgba(255,255,255,0.25)' : 'rgba(0,0,0,0.3)';

  const isActive = (path) =>
    path === '/app' ? location.pathname === '/app' : location.pathname.startsWith(path);

  const itemSx = (active) => ({
    display: 'flex', alignItems: 'center', gap: 1.25,
    px: 1.5, py: 0.4, mx: 0.75, borderRadius: '5px', mb: 0.25,
    cursor: 'pointer', position: 'relative',
    bgcolor: active ? (d ? 'rgba(88, 106, 208,0.14)' : 'rgba(88, 106, 208,0.09)') : 'transparent',
    color: active ? '#586AD0' : textMuted,
    borderLeft: active ? '2px solid #586AD0' : '2px solid transparent',
    '&:hover': { bgcolor: active ? (d ? 'rgba(88, 106, 208,0.18)' : 'rgba(88, 106, 208,0.12)') : bgHover, color: active ? '#586AD0' : textActive },
    transition: 'all 0.12s',
  });

  const iconColor = (active) => active ? '#586AD0' : textDisabled;

  const userInitials = currentUser
    ? ((currentUser.first_name?.[0] || '') + (currentUser.last_name?.[0] || '') || currentUser.email?.[0] || 'U').toUpperCase()
    : 'U';

  // ── Los tres modos ──────────────────────────────────────────────────────────
  // Conmutador arriba a la izquierda: solo el modo activo muestra su etiqueta, los
  // otros dos son icono pelado. La barra cambia completa segun el modo.
  //   Trabajo  — el dia a dia: chat, conversaciones, agentes.
  //   Espacios — conocimiento y permisos, mas lo que los administra.
  //   Admin    — la empresa: personas, ajustes, plan.
  // Los items de cuenta (perfil, ayuda, cerrar sesion) viven en la ficha del
  // usuario, abajo, igual en los tres modos.
  const MODOS = [
    { key: 'trabajo',  label: 'Trabajo',  icon: <MessageSquare size={14} /> },
    { key: 'espacios', label: 'Espacios', icon: <Layers size={14} /> },
    { key: 'admin',    label: 'Admin',    icon: <Settings size={14} /> },
  ];

  const ITEMS_POR_MODO = {
    trabajo: {
      seccion: null,
      items: [
        { path: '/app/agentes',    label: 'Agentes', icon: <Bot size={15} /> },
        { path: '/app/tablero',    label: 'Tablero', icon: <LayoutDashboard size={15} /> },
      ],
    },
    espacios: {
      seccion: 'Administración',
      items: [
        { path: '/app/contexto',         label: 'Espacios',     icon: <Layers size={15} /> },
        { path: '/app/automatizaciones', label: 'Disparadores', icon: <Timer size={15} /> },
      ],
    },
    admin: {
      seccion: 'Workspace',
      items: [
        { path: '/app/admin/personas',  label: 'Personas',      icon: <Users size={14} /> },
        { path: '/app/admin/agentes',   label: 'Agentes',       icon: <Bot size={14} /> },
        { path: '/app/admin/workspace', label: 'Ajustes',       icon: <Building2 size={14} /> },
        { path: '/app/configuracion',   label: 'Configuración', icon: <Settings size={14} /> },
        { path: '/app/precios',         label: 'Plan',          icon: <Zap size={14} /> },
      ],
    },
  };

  useEffect(() => {
    // El chat y la home no estan en ninguna lista de items: son el modo Trabajo.
    const enChat = location.pathname === '/app' || location.pathname.startsWith('/app/chat');
    const dueño = enChat
      ? ['trabajo']
      : Object.entries(ITEMS_POR_MODO).find(([, { items }]) =>
          items.some((i) => location.pathname.startsWith(i.path)),
        );
    if (dueño && dueño[0] !== modo) setModo(dueño[0]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname]);

  // El chat y su historial solo viven en el modo Trabajo.
  const enTrabajo = modo === 'trabajo';
  const { seccion, items: itemsDelModo } = ITEMS_POR_MODO[modo] || ITEMS_POR_MODO.trabajo;

  // La ficha del usuario, igual en los tres modos.
  const accountMenuItems = [
    { path: '/app/perfil', label: 'Mi Perfil', icon: <User size={14} /> },
    { path: '/app/ayuda',  label: 'Ayuda',     icon: <HelpCircle size={14} /> },
  ];

  const drawer = (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>

      {/* ── Conmutador de modos ──────────────────────────────────────────────
          Tres iconos arriba a la izquierda; el activo lleva su etiqueta en una
          pastilla y los otros dos van sin texto. A la derecha, colapsar el panel. */}
      <Box sx={{
        display: 'flex', alignItems: 'center',
        justifyContent: open ? 'space-between' : 'center',
        gap: 0.5, px: open ? 1 : 0.5, py: 1, minHeight: 52, flexShrink: 0,
      }}>
        <Box sx={{
          display: 'flex', alignItems: 'center', gap: 0.25,
          flexDirection: open ? 'row' : 'column',
        }}>
          {MODOS.map((m) => {
            const activo = modo === m.key;
            return (
              <Tooltip key={m.key} title={activo && open ? '' : m.label} placement="right" arrow>
                <Box
                  component="button"
                  onClick={() => setModo(m.key)}
                  aria-pressed={activo}
                  sx={{
                    display: 'flex', alignItems: 'center', gap: 0.75,
                    px: activo && open ? 1.25 : 0.75, py: 0.6,
                    border: 'none', cursor: 'pointer', borderRadius: '6px',
                    fontFamily: 'inherit', fontSize: '0.875rem', fontWeight: 500,
                    color: activo ? textActive : textDisabled,
                    bgcolor: activo ? bgHover : 'transparent',
                    '&:hover': { color: activo ? textActive : textMuted, bgcolor: bgHover },
                    transition: 'all 0.12s',
                  }}
                >
                  <Box sx={{ display: 'flex' }}>{m.icon}</Box>
                  {activo && open && m.label}
                </Box>
              </Tooltip>
            );
          })}
        </Box>

        {open && (
          <Box component="button" onClick={handleDrawerToggle} sx={{
            border: 'none', background: 'transparent', color: textDisabled,
            cursor: 'pointer', display: 'flex', p: 0.5, borderRadius: '4px', flexShrink: 0,
            '&:hover': { color: textMuted, bgcolor: bgHover }, transition: 'all 0.12s',
          }}>
            <ChevronLeft size={15} />
          </Box>
        )}
      </Box>

      {!open && (
        <Tooltip title="Expandir" placement="right" arrow>
          <Box
            onClick={handleDrawerToggle}
            sx={{
              display: 'flex', justifyContent: 'center', py: 0.5, cursor: 'pointer',
              color: textDisabled, '&:hover': { color: textMuted },
            }}
          >
            <ChevronRight size={15} />
          </Box>
        </Tooltip>
      )}

      <Box sx={{ borderBottom: `1px solid ${theme.palette.divider}`, mx: 1.5, mb: 0.5 }} />

      {/* ── Search ── */}
      <Box sx={{ px: 1.25, py: 0.5, flexShrink: 0 }}>
        <Box onClick={() => window.dispatchEvent(new CustomEvent('afable-open-search'))} sx={{
          display: 'flex', alignItems: 'center', gap: open ? 1 : 0,
          justifyContent: open ? 'flex-start' : 'center',
          px: open ? 1.25 : 1, py: 0.6, borderRadius: '5px', cursor: 'pointer',
          color: textMuted, '&:hover': { bgcolor: bgHover, color: textActive }, transition: 'all 0.12s',
        }}>
          <Search size={14} style={{ flexShrink: 0 }} />
          {open && (
            <>
              <Typography sx={{ fontSize: '0.875rem', flex: 1, color: 'inherit' }}>Buscar...</Typography>
              <Typography sx={{ fontSize: '0.65rem', color: keyHintColor, bgcolor: keyHintBg, px: 0.6, py: 0.2, borderRadius: '3px', fontFamily: 'monospace', lineHeight: 1.6, flexShrink: 0 }}>
                ⌘K
              </Typography>
            </>
          )}
        </Box>
      </Box>

      {/* ── Main content (scrollable) ── */}
      <Box sx={{ flex: 1, overflowY: 'auto', overflowX: 'hidden', py: 0.5 }}>

        {/* Chat con su historial: solo en Trabajo */}
        {enTrabajo && (
          <Box sx={{ mb: 0.5 }}>
            <Tooltip title={!open ? 'Chat' : ''} placement="right" arrow>
              <Box sx={itemSx(isActive('/app/chat'))} onClick={() => navigate('/app/chat')}>
                <MessageSquare size={15} color={iconColor(isActive('/app/chat'))} style={{ flexShrink: 0 }} />
                {open && (
                  <>
                    <Typography sx={{ fontSize: '0.9rem', fontWeight: isActive('/app/chat') ? 500 : 400, color: 'inherit', flex: 1 }}>
                      Chat
                    </Typography>
                    <Box
                      onClick={(e) => { e.stopPropagation(); navigate('/app/chat'); }}
                      sx={{
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        width: 18, height: 18, borderRadius: '4px', flexShrink: 0,
                        color: textDisabled, '&:hover': { bgcolor: bgHover, color: textActive },
                      }}
                    >
                      <Plus size={12} />
                    </Box>
                    {conversations.length > 0 && (
                      <Box
                        onClick={(e) => { e.stopPropagation(); setChatOpen(p => !p); }}
                        sx={{ display: 'flex', p: 0.25, borderRadius: '4px', flexShrink: 0, '&:hover': { bgcolor: bgHover } }}
                      >
                        {chatOpen ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                      </Box>
                    )}
                  </>
                )}
              </Box>
            </Tooltip>

            {/* Conversaciones (ultimas 10) */}
            {open && conversations.length > 0 && (
              <Collapse in={chatOpen}>
                <Box sx={{ pl: 3.5, pr: 0.75, mt: 0.25 }}>
                  <Box
                    onClick={() => navigate('/app/chat')}
                    sx={{
                      display: 'flex', alignItems: 'center', gap: 0.75,
                      px: 1, py: 0.4, borderRadius: '4px', cursor: 'pointer',
                      color: textDisabled, '&:hover': { bgcolor: bgHover, color: textMuted },
                      transition: 'all 0.1s',
                    }}
                  >
                    <History size={14} />
                    <Typography sx={{ fontSize: '0.82rem' }}>Conversaciones</Typography>
                  </Box>
                  <Box sx={{ pl: 2.75 }}>
                    {conversations.map(conv => (
                      <Box
                        key={conv.id}
                        onClick={() => navigate('/app/chat', { state: { conversationId: conv.id } })}
                        sx={{
                          px: 1, py: 0.35, borderRadius: '4px', cursor: 'pointer',
                          color: textDisabled, '&:hover': { bgcolor: bgHover, color: textMuted },
                          transition: 'all 0.1s',
                        }}
                      >
                        <Typography sx={{ fontSize: '0.8rem', lineHeight: 1.4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '100%' }}>
                          {(conv.title || 'Conversación').slice(0, 30)}
                        </Typography>
                      </Box>
                    ))}
                  </Box>
                </Box>
              </Collapse>
            )}
          </Box>
        )}

        {/* Encabezado de la seccion del modo activo */}
        {open && seccion && (
          <Typography sx={{
            px: 2, pt: 1, pb: 0.5, fontSize: '0.72rem', fontWeight: 600,
            color: textDisabled, letterSpacing: '0.06em', textTransform: 'uppercase',
          }}>
            {seccion}
          </Typography>
        )}

        {/* Los items del modo activo */}
        {itemsDelModo.map(item => (
          <Tooltip key={item.path} title={!open ? item.label : ''} placement="right" arrow>
            <Box sx={itemSx(isActive(item.path))} onClick={() => navigate(item.path)}>
              <Box sx={{ color: iconColor(isActive(item.path)), flexShrink: 0, display: 'flex' }}>
                {item.icon}
              </Box>
              {open && (
                <Typography sx={{ fontSize: '0.9rem', fontWeight: isActive(item.path) ? 500 : 400, color: 'inherit' }}>
                  {item.label}
                </Typography>
              )}
            </Box>
          </Tooltip>
        ))}

      </Box>

      {/* ── Bottom: user ── */}
      <Box sx={{ borderTop: `1px solid ${theme.palette.divider}`, mx: 1.5, mt: 0.5 }} />
      <Box
        onClick={(e) => setUserMenuAnchor(e.currentTarget)}
        sx={{
          display: 'flex', alignItems: 'center',
          gap: open ? 1 : 0, justifyContent: open ? 'space-between' : 'center',
          px: open ? 1.5 : 1, py: 1, flexShrink: 0, cursor: 'pointer',
          borderRadius: '6px', mx: 0.75, mb: 0.5,
          '&:hover': { bgcolor: bgHover },
          transition: 'background 0.12s',
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 0 }}>
          <Avatar src={currentUser?.avatar_url} sx={{ width: 24, height: 24, fontSize: '0.65rem', bgcolor: '#586AD0', flexShrink: 0 }}>
            {userInitials}
          </Avatar>
          {open && (
            <Typography sx={{ fontSize: '0.75rem', color: textMuted, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 100 }}>
              {currentUser?.email || ''}
            </Typography>
          )}
        </Box>
      </Box>

      {/* User menu */}
      <Menu
        anchorEl={userMenuAnchor}
        open={Boolean(userMenuAnchor)}
        onClose={() => setUserMenuAnchor(null)}
        transformOrigin={{ horizontal: 'left', vertical: 'bottom' }}
        anchorOrigin={{ horizontal: 'left', vertical: 'top' }}
        PaperProps={{
          sx: {
            minWidth: 200,
            bgcolor: d ? '#252525' : '#fff',
            border: `1px solid ${theme.palette.divider}`,
            boxShadow: d ? '0 8px 32px rgba(0,0,0,0.4)' : '0 4px 20px rgba(0,0,0,0.12)',
            borderRadius: '8px',
          },
        }}
      >
        <Box sx={{ px: 1.75, py: 1.25 }}>
          <Typography sx={{ fontWeight: 600, fontSize: '0.9rem', color: 'text.primary' }}>
            {currentUser?.first_name ? `${currentUser.first_name} ${currentUser.last_name || ''}`.trim() : currentUser?.email?.split('@')[0]}
          </Typography>
          <Typography sx={{ fontSize: '0.75rem', color: textMuted, mt: 0.15 }}>
            {currentUser?.email}
          </Typography>
        </Box>
        <Divider sx={{ borderColor: theme.palette.divider }} />
        {accountMenuItems.map(item => (
          <MenuItem key={item.path} onClick={() => { navigate(item.path); setUserMenuAnchor(null); }}
            sx={{ gap: 1.5, fontSize: '0.9rem', color: textMuted, py: 0.875, mx: 0.75, borderRadius: '4px', mb: 0.25,
              '&:hover': { bgcolor: bgHover, color: 'text.primary' } }}>
            <Box sx={{ color: textDisabled, display: 'flex' }}>{item.icon}</Box>
            {item.label}
          </MenuItem>
        ))}
        <Divider sx={{ borderColor: theme.palette.divider, my: 0.5 }} />
        <MenuItem onClick={handleLogout}
          sx={{ gap: 1.5, fontSize: '0.9rem', color: '#ef4444', py: 0.875, mx: 0.75, mb: 0.75, borderRadius: '4px',
            '&:hover': { bgcolor: 'rgba(239,68,68,0.07)' } }}>
          <LogOut size={14} /> Cerrar sesión
        </MenuItem>
      </Menu>
    </Box>
  );

  if (matchDownLG) {
    return (
      <MuiDrawer
        anchor="left"
        open={open}
        onClose={handleDrawerToggle}
        ModalProps={{ keepMounted: true }}
        sx={{ '& .MuiDrawer-paper': { width: DRAWER_WIDTH, bgcolor: 'background.paper', borderRight: `1px solid ${theme.palette.divider}` } }}
      >
        {drawer}
      </MuiDrawer>
    );
  }

  return (
    <DrawerStyled variant="permanent" open={open}>
      {drawer}
    </DrawerStyled>
  );
}

Drawer.propTypes = {
  open: PropTypes.bool.isRequired,
  handleDrawerToggle: PropTypes.func.isRequired,
};
