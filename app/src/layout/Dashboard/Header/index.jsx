import PropTypes from 'prop-types';
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AppBar,
  Toolbar,
  IconButton,
  Box,
  Typography,
  Avatar,
  Menu,
  MenuItem,
  Divider,
  Tooltip,
  useTheme,
  useMediaQuery,
  styled,
  Chip,
} from '@mui/material';
import {
  Menu as MenuIcon,
  PanelLeftOpen,
  User,
  Settings,
  LogOut,
  Building2,
  HelpCircle,
  Sparkles,
  ChevronDown,
  Zap,
  Search,
  Sun,
  Moon,
  Brain,
  Cpu,
  // Building2 kept for user menu items only
} from 'lucide-react';
import { toast } from 'react-toastify';
import { authService } from '../../../services/auth';
import { api } from '../../../services/api';
import { DRAWER_WIDTH, MINI_DRAWER_WIDTH } from '../../../config';
import { useThemeMode } from '../../../context/ThemeContext';
import { useApp } from '../../../context/AppContext';

const KIND_META = {
  local: { badge: 'Local', color: '#34D399', icon: <Zap size={14} /> },
  cloud: { badge: 'Cloud', color: '#9BA6E3', icon: <Sparkles size={14} /> },
  anthropic: { badge: 'Anthropic', color: '#D97757', icon: <Brain size={14} /> },
  deepseek: { badge: 'DeepSeek', color: '#4D6BFE', icon: <Cpu size={14} /> },
};

const GROUP_ORDER = [
  { key: 'cloud', label: 'Cloud' },
  { key: 'local', label: 'Local' },
  { key: 'anthropic', label: 'Anthropic' },
  { key: 'deepseek', label: 'DeepSeek' },
];

const AppBarStyled = styled(AppBar, { shouldForwardProp: (p) => p !== 'open' })(
  ({ theme, open }) => ({
    zIndex: theme.zIndex.drawer + 1,
    backgroundColor: theme.palette.background.default,
    borderBottom: `1px solid ${theme.palette.divider}`,
    boxShadow: 'none',
    transition: theme.transitions.create(['width', 'margin'], {
      easing: theme.transitions.easing.sharp,
      duration: theme.transitions.duration.leavingScreen,
    }),
    ...(!open && { width: `calc(100% - ${MINI_DRAWER_WIDTH}px)` }),
    ...(open && {
      marginLeft: DRAWER_WIDTH,
      width: `calc(100% - ${DRAWER_WIDTH}px)`,
      transition: theme.transitions.create(['width', 'margin'], {
        easing: theme.transitions.easing.sharp,
        duration: theme.transitions.duration.enteringScreen,
      }),
    }),
  })
);

export default function Header({ open, handleDrawerToggle }) {
  const theme = useTheme();
  const { mode, toggleMode } = useThemeMode();
  const matchDownLG = useMediaQuery(theme.breakpoints.down('lg'));
  const navigate = useNavigate();
  const [anchorEl, setAnchorEl] = useState(null);
  const [modelAnchorEl, setModelAnchorEl] = useState(null);
  const { aiModel, setAiModel } = useApp();
  const [models, setModels] = useState([]);     // [{id,label,kind,default}]
  const [defaultModel, setDefaultModel] = useState(null);
  const [user, setUser] = useState(null);

  useEffect(() => {
    api.getModels()
      .then(res => {
        const list = res.data?.models || [];
        setModels(list);
        setDefaultModel(res.data?.default || null);
      })
      .catch(() => setModels([]));
  }, []);

  // Modelo activo: el elegido por el usuario, o el default del backend.
  const activeId = aiModel || defaultModel;
  const activeModel = models.find(m => m.id === activeId) || null;
  const activeKind = activeModel ? (KIND_META[activeModel.kind] || KIND_META.local) : KIND_META.local;
  const activeLabel = activeModel?.label || activeId || 'Modelo';

  // Agrupar por tipo para el menú (orden fijo: Cloud, Local, Anthropic, DeepSeek)
  const groups = GROUP_ORDER
    .map(g => ({ ...g, items: models.filter(m => m.kind === g.key) }))
    .filter(g => g.items.length);

  const d = mode === 'dark';
  const textMuted    = d ? 'rgba(255,255,255,0.66)' : 'rgba(0,0,0,0.62)';
  const textSemi     = d ? 'rgba(255,255,255,0.82)' : 'rgba(0,0,0,0.76)';
  const bgHover      = theme.palette.action.hover;
  const borderColor  = theme.palette.divider;
  const keyHintBg    = d ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.06)';
  const keyHintColor = d ? 'rgba(255,255,255,0.25)' : 'rgba(0,0,0,0.3)';
  const menuBg       = d ? '#252525' : '#ffffff';
  const menuBorder   = d ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)';

  useEffect(() => {
    api.getCurrentUser()
      .then((r) => setUser(r.data))
      .catch(() => {});
  }, []);

  const getInitials = (u) => {
    if (!u) return '?';
    if (u.first_name && u.last_name) return `${u.first_name[0]}${u.last_name[0]}`.toUpperCase();
    if (u.first_name) return u.first_name[0].toUpperCase();
    if (u.username) return u.username[0].toUpperCase();
    return '?';
  };

  const handleMenu = (e) => setAnchorEl(e.currentTarget);
  const handleClose = () => setAnchorEl(null);

  const handleLogout = () => {
    authService.logout();
    toast.success('Sesión cerrada');
    navigate('/login');
    handleClose();
  };

  const toolbarContent = (
    <>
      {/* Toggle sidebar */}
      <IconButton
        color="inherit"
        onClick={handleDrawerToggle}
        edge="start"
        sx={{
          mr: 1,
          color: textMuted,
          '&:hover': { color: theme.palette.text.primary, bgcolor: bgHover },
        }}
      >
        {open && !matchDownLG ? <PanelLeftOpen size={18} /> : <MenuIcon size={18} />}
      </IconButton>

      {/* Model selector */}
      <Box
        onClick={(e) => setModelAnchorEl(e.currentTarget)}
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 0.75,
          px: 1.25,
          py: 0.5,
          borderRadius: '6px',
          border: `1px solid ${borderColor}`,
          bgcolor: 'transparent',
          cursor: 'pointer',
          userSelect: 'none',
          transition: 'all 0.12s',
          '&:hover': { bgcolor: bgHover },
        }}
      >
        <Box sx={{ color: activeKind.color, display: 'flex', alignItems: 'center' }}>
          <Sparkles size={13} />
        </Box>
        <Typography sx={{ fontSize: '0.8125rem', fontWeight: 500, color: textSemi, whiteSpace: 'nowrap' }}>
          {activeLabel}
        </Typography>
        <ChevronDown size={12} color={textMuted} />
      </Box>

      <Menu
        anchorEl={modelAnchorEl}
        open={Boolean(modelAnchorEl)}
        onClose={() => setModelAnchorEl(null)}
        transformOrigin={{ horizontal: 'left', vertical: 'top' }}
        anchorOrigin={{ horizontal: 'left', vertical: 'bottom' }}
        PaperProps={{
          sx: {
            mt: 0.75,
            minWidth: 260,
            backgroundColor: menuBg,
            border: `1px solid ${menuBorder}`,
            boxShadow: d ? '0 8px 32px rgba(0,0,0,0.4)' : '0 4px 20px rgba(0,0,0,0.12)',
            borderRadius: '8px',
          },
        }}
      >
        {models.length === 0 && (
          <Typography sx={{ px: 2, py: 1.5, fontSize: '0.8125rem', color: textMuted }}>
            No hay modelos disponibles. Revisa que Ollama esté corriendo.
          </Typography>
        )}
        {groups.map((group, gi) => [
          gi > 0 && <Divider key={`div-${gi}`} sx={{ borderColor: d ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.07)', my: 0.5 }} />,
          <Typography
            key={`group-${gi}`}
            sx={{ px: 2, pt: gi === 0 ? 1.25 : 0.5, pb: 0.5, fontSize: '0.6875rem', fontWeight: 600, color: textMuted, letterSpacing: '0.07em', textTransform: 'uppercase' }}
          >
            {group.label}
          </Typography>,
          ...group.items.map((m) => {
            const meta = KIND_META[m.kind] || KIND_META.local;
            const isActive = activeId === m.id;
            return (
              <MenuItem
                key={m.id}
                selected={isActive}
                onClick={() => { setAiModel(m.id); setModelAnchorEl(null); }}
                sx={{
                  mx: 0.75,
                  borderRadius: '4px',
                  mb: 0.25,
                  gap: 1.5,
                  py: 0.875,
                  color: isActive ? theme.palette.text.primary : textSemi,
                  bgcolor: isActive ? theme.palette.action.selected : 'transparent',
                  '&:hover': { bgcolor: bgHover, color: theme.palette.text.primary },
                }}
              >
                <Box sx={{ color: meta.color, display: 'flex', alignItems: 'center' }}>{meta.icon}</Box>
                <Typography sx={{ fontSize: '0.875rem', fontWeight: 500, flex: 1, fontFamily: '"JetBrains Mono",monospace' }}>{m.label}</Typography>
                <Chip
                  label={m.default ? `${meta.badge} · default` : meta.badge}
                  size="small"
                  sx={{
                    height: 18,
                    fontSize: '0.6875rem',
                    fontWeight: 500,
                    bgcolor: d ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.05)',
                    color: textMuted,
                    border: `1px solid ${borderColor}`,
                    '& .MuiChip-label': { px: 0.75 },
                  }}
                />
              </MenuItem>
            );
          }),
        ])}
        <Box sx={{ pb: 0.75 }} />
      </Menu>

      {/* Search pill — center */}
      <Box sx={{ flexGrow: 1, display: 'flex', justifyContent: 'center', px: 2 }}>
        <Box
          onClick={() => window.dispatchEvent(new CustomEvent('afable-open-search'))}
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1,
            px: 1.5,
            py: 0.5,
            borderRadius: '6px',
            border: `1px solid ${borderColor}`,
            bgcolor: 'transparent',
            cursor: 'pointer',
            width: '100%',
            maxWidth: 360,
            transition: 'all 0.12s',
            '&:hover': { bgcolor: bgHover },
          }}
        >
          <Search size={14} color={textMuted} />
          <Typography sx={{ fontSize: '0.8125rem', color: textMuted, flex: 1 }}>
            Buscar en Afable...
          </Typography>
          <Typography
            sx={{
              fontSize: '0.6875rem',
              color: keyHintColor,
              bgcolor: keyHintBg,
              px: 0.75,
              py: 0.2,
              borderRadius: '3px',
              fontFamily: 'monospace',
              lineHeight: 1.7,
              whiteSpace: 'nowrap',
            }}
          >
            ⌘K
          </Typography>
        </Box>
      </Box>

      {/* Claro / oscuro: arriba a la derecha, donde se busca sin pensar.
          Un solo icono, el del modo activo. Antes había sol + interruptor +
          luna, que ocupaba el triple y obligaba a leer para saber en cuál se
          estaba. */}
      <Tooltip title={mode === 'dark' ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro'} arrow>
        <IconButton
          onClick={toggleMode}
          size="small"
          aria-label={mode === 'dark' ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro'}
          sx={{
            ml: 1, mr: 0.5,
            color: textMuted,
            '&:hover': { color: '#586AD0', bgcolor: 'action.hover' },
          }}
        >
          {mode === 'dark' ? <Moon size={16} /> : <Sun size={16} />}
        </IconButton>
      </Tooltip>

      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleClose}
        onClick={handleClose}
        transformOrigin={{ horizontal: 'right', vertical: 'top' }}
        anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
        PaperProps={{
          sx: {
            mt: 0.75,
            minWidth: 220,
            backgroundColor: menuBg,
            border: `1px solid ${menuBorder}`,
            boxShadow: d ? '0 8px 32px rgba(0,0,0,0.4)' : '0 4px 20px rgba(0,0,0,0.12)',
            borderRadius: '8px',
          },
        }}
      >
        <Box sx={{ px: 1.75, py: 1.25 }}>
          <Typography sx={{ fontWeight: 600, color: theme.palette.text.primary, fontSize: '0.875rem', lineHeight: 1.3 }}>
            {user?.full_name || user?.username || 'Usuario'}
          </Typography>
          <Typography sx={{ color: textMuted, fontSize: '0.8125rem', mt: 0.25 }}>
            {user?.email}
          </Typography>
        </Box>

        <Divider sx={{ borderColor: d ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.07)' }} />

        {[
          { label: 'Mi Perfil',      icon: <User size={15} />,       path: '/app/perfil' },
          { label: 'Workspace',      icon: <Building2 size={15} />,  path: '/app/admin/workspace' },
          { label: 'Configuración',  icon: <Settings size={15} />,   path: '/app/configuracion' },
          { label: 'Ayuda',          icon: <HelpCircle size={15} />, path: '/app/ayuda' },
        ].map(({ label, icon, path }) => (
          <MenuItem
            key={path}
            onClick={() => navigate(path)}
            sx={{
              mx: 0.75,
              borderRadius: '4px',
              gap: 1.5,
              color: textSemi,
              fontSize: '0.875rem',
              py: 1,
              '&:hover': { bgcolor: bgHover, color: theme.palette.text.primary },
            }}
          >
            <Box sx={{ color: textMuted, display: 'flex' }}>{icon}</Box>
            {label}
          </MenuItem>
        ))}

        <Divider sx={{ borderColor: d ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.07)', my: 0.5 }} />

        <MenuItem
          onClick={handleLogout}
          sx={{
            mx: 0.75,
            mb: 0.75,
            borderRadius: '4px',
            gap: 1.5,
            fontSize: '0.875rem',
            py: 1,
            color: '#ef4444',
            '&:hover': { bgcolor: 'rgba(239,68,68,0.07)' },
          }}
        >
          <LogOut size={15} /> Cerrar sesión
        </MenuItem>
      </Menu>
    </>
  );

  if (matchDownLG) {
    return (
      <>
        <AppBar
          position="fixed"
          elevation={0}
          sx={{
            backgroundColor: theme.palette.background.default,
            borderBottom: `1px solid ${theme.palette.divider}`,
          }}
        >
          <Toolbar sx={{ minHeight: '52px !important' }}>{toolbarContent}</Toolbar>
        </AppBar>
      </>
    );
  }

  return (
    <>
      <AppBarStyled position="fixed" open={open} elevation={0}>
        <Toolbar sx={{ minHeight: '52px !important' }}>{toolbarContent}</Toolbar>
      </AppBarStyled>
    </>
  );
}

Header.propTypes = {
  open: PropTypes.bool.isRequired,
  handleDrawerToggle: PropTypes.func.isRequired,
};
