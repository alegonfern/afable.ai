import { useState, useEffect, useCallback } from 'react';
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
  InputBase,
} from '@mui/material';
import {
  MessageSquare, LayoutDashboard, Settings, Search, ChevronLeft, Plus, ChevronDown,
  ChevronRight, Zap, Bot, History, Boxes,
  User, Building2, HelpCircle, LogOut, Timer, Layers, Users,
  Plug, FolderOpen, BookOpen, CheckSquare, CreditCard,
  ShoppingCart, Calculator, Wallet, PackageOpen,
} from 'lucide-react';
import { toast } from 'react-toastify';
import { authService } from '../../../services/auth';
import { useNavigate, useLocation } from 'react-router-dom';
import { DRAWER_WIDTH, MINI_DRAWER_WIDTH } from '../../../config';
import { useApp } from '../../../context/AppContext';
import { api } from '../../../services/api';
import MenuDeFila, { DialogoCompartir } from './MenuDeFila';
import { Isotipo, Logo } from '../../../components/Logo';
import { MODULOS, moduloDeRuta, rutaDe, seccionesDe, vistaGuardada } from '../modulos';
import { useWorkspace } from '../../../context/WorkspaceContext';
import { useDteDisponible } from '../../../pages/dte/useDte';
import { tonoModulo } from '../../../theme/tonos';

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
  const { slug: empresaSlug } = useWorkspace();
  const dteDisponible = useDteDisponible(empresaSlug);
  const matchDownLG = useMediaQuery(theme.breakpoints.down('lg'));
  const d = theme.palette.mode === 'dark';

  const [conversations, setConversations] = useState([]);
  // El historial se despliega bajo Chat cuando se está en el chat, como el submenú de un
  // módulo bajo el módulo abierto; la flecha lo abre o cierra a mano desde cualquier lado.
  const [chatOpen, setChatOpen] = useState(() => location.pathname.startsWith('/app/chat'));
  useEffect(() => { setChatOpen(location.pathname.startsWith('/app/chat')); }, [location.pathname]);
  // Las Sesiones del Workspace activo: es la seccion que las vuelve alcanzables. Sin
  // esto, una Sesion existe pero no hay por donde llegar a ella.
  const [sesiones, setSesiones] = useState([]);
  const [sesionesOpen, setSesionesOpen] = useState(true);
  const [userMenuAnchor, setUserMenuAnchor] = useState(null);
  const handleLogout = () => {
    authService.logout();
    toast.success('Sesión cerrada');
    navigate('/login');
    setUserMenuAnchor(null);
  };

  // El limite lo pone el servidor: antes se pedian TODAS para mostrar diez.
  const cargarConversaciones = useCallback(() => {
    api.getConversations({ limite: 10 })
      .then(r => setConversations(r.data))
      .catch(() => {});
  }, []);

  useEffect(() => { cargarConversaciones(); }, [cargarConversaciones]);

  // El Drawer vive en el layout permanente: no se vuelve a montar al navegar, asi que
  // sin esto una conversacion nueva no aparecia hasta recargar la pagina entera. Mismo
  // patron que las Sesiones, mas abajo.
  useEffect(() => {
    const alCambiar = () => cargarConversaciones();
    window.addEventListener('afable-conversaciones', alCambiar);
    return () => window.removeEventListener('afable-conversaciones', alCambiar);
  }, [cargarConversaciones]);

  const wsSlug = localStorage.getItem('afable_workspace_slug');
  // El Workspace elegido acota las Sesiones de la barra, igual que en Archivos.
  const espacioSlug = localStorage.getItem(`afable_espacio_slug:${wsSlug}`);
  const cargarSesiones = useCallback(() => {
    if (!wsSlug) return;
    // ⭐ La barra NO filtra por el Workspace elegido, a diferencia de Archivos o la
    // galería de agentes. Es la NAVEGACIÓN: esconder acá no acota una búsqueda, hace
    // creer que el trabajo se perdió — y quien no tiene claro que arriba hay un filtro
    // no relaciona una cosa con la otra. Cada Sesión dice a qué Workspace pertenece,
    // que informa sin ocultar.
    api.getSesiones(wsSlug)
      .then(r => setSesiones(r.data.results || []))
      .catch(() => setSesiones([]));
  }, [wsSlug]);

  useEffect(() => { cargarSesiones(); }, [cargarSesiones]);

  // La etiqueta del Workspace solo aparece si la lista mezcla varios. Con uno solo diría
  // lo mismo en todas las filas, y una etiqueta que nunca cambia se deja de leer.
  const variosWorkspaces = new Set(
    sesiones.map((s) => s.workspace).filter(Boolean),
  ).size > 1;
  // Al crear, archivar o borrar una Sesion la barra tiene que reflejarlo sin recargar.
  useEffect(() => {
    const alCambiar = () => cargarSesiones();
    window.addEventListener('afable-sesiones', alCambiar);
    return () => window.removeEventListener('afable-sesiones', alCambiar);
  }, [cargarSesiones]);

  // El nombre se escribe EN la barra, no en un `window.prompt`: un prompt del
  // navegador se ve como un error del sistema, no como una parte de la app.
  const [nombreNueva, setNombreNueva] = useState(null);   // null = no se está creando
  // La fila sobre la que está el mouse: los tres puntos solo se muestran ahí. Un icono
  // fijo en cada línea hace la lista más difícil de leer que la lista sola.
  const [encima, setEncima] = useState(null);
  const [compartiendo, setCompartiendo] = useState(null);   // la conversación a compartir

  const accionDeConversacion = async (conv, clave) => {
    try {
      if (clave === 'eliminar') {
        await api.deleteConversation(conv.id);
        setConversations((cs) => cs.filter((c) => c.id !== conv.id));
        toast.success('Conversación eliminada.');
        if (location.pathname.startsWith('/app/chat')) navigate('/app/chat', { state: { nueva: true } });
      }
      if (clave === 'compartir') setCompartiendo(conv);
    } catch {
      toast.error('No se pudo completar la acción.');
    }
  };

  const compartir = async (sesionSlug) => {
    const conv = compartiendo;
    setCompartiendo(null);
    try {
      await api.updateConversation(conv.id, {
        workspace: wsSlug, sesion: sesionSlug,
      });
      const { data } = await api.getConversations();
      setConversations(data.slice(0, 10));
      toast.success(
        sesionSlug ? 'La conversación ahora la ve el equipo de la Sesión.'
                   : 'Volvió a su historial privado.',
      );
    } catch (e) {
      toast.error(e.response?.data?.detail || 'No se pudo compartir.');
    }
  };

  const accionDeSesion = async (sesion, clave) => {
    try {
      if (clave === 'copiar') {
        await navigator.clipboard.writeText(`${window.location.origin}/app/sesiones/${sesion.slug}`);
        toast.success('Enlace copiado.');
        return;
      }
      if (clave === 'archivar') {
        await api.updateSesion(sesion.slug, { workspace: wsSlug, archivada: !sesion.archivada });
        toast.success(sesion.archivada ? 'Sesión desarchivada.' : 'Sesión archivada.');
      }
      if (clave === 'eliminar') {
        await api.deleteSesion(sesion.slug, wsSlug);
        toast.success('Sesión eliminada.');
        if (location.pathname === `/app/sesiones/${sesion.slug}`) navigate('/app');
      }
      await cargarSesiones();
    } catch (e) {
      toast.error(
        e.response?.status === 403
          ? 'Solo un administrador de la Empresa puede eliminar una Sesión.'
          : 'No se pudo completar la acción.',
      );
    }
  };

  const crearSesion = async () => {
    const nombre = (nombreNueva || '').trim();
    if (!wsSlug || !nombre) return;
    try {
      // Nace donde se está trabajando: si hay un Workspace elegido arriba, ahí — si no,
      // la Sesión se crearía en otro lado y desaparecería de la barra.
      const { data } = await api.createSesion({
        workspace: wsSlug, name: nombre,
        ...(espacioSlug ? { espacio: espacioSlug } : {}),
      });
      setNombreNueva(null);
      await cargarSesiones();
      navigate(`/app/sesiones/${data.slug}`);
    } catch {
      toast.error('No se pudo crear la Sesión.');
    }
  };


  // Contraste: los items en reposo estaban al 45% y los iconos al 28% sobre un
  // fondo casi negro — legible a duras penas y cansador. Se sube el piso sin
  // perder la jerarquia con el item activo, que va en indigo.
  const textMuted    = d ? 'rgba(255,255,255,0.74)' : 'rgba(0,0,0,0.70)';
  const textDisabled = d ? 'rgba(255,255,255,0.52)' : 'rgba(0,0,0,0.50)';
  const textActive   = theme.palette.text.primary;
  const bgHover      = d ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.04)';
  const keyHintBg    = d ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.06)';
  const keyHintColor = d ? 'rgba(255,255,255,0.25)' : 'rgba(0,0,0,0.3)';

  // Compara tambien el `?tab=`: las pestañas del hub de Espacios son items
  // distintos del menu y apuntan todas a /app/contexto. Sin esto se encendian las
  // cuatro juntas.
  // El módulo de un hilo del panel lateral, que se guarda como "<empresa>:<módulo>".
  const moduloDeConversacion = (conv) =>
    MODULOS.find((m) => m.slug === (conv.contexto || '').split(':')[1])?.label || null;
  const tonoDeConversacion = (conv) => tonoModulo((conv.contexto || '').split(':')[1]);

  const isActive = (path) => {
    if (path === '/app') return location.pathname === '/app';
    const [ruta, query] = path.split('?');
    if (!location.pathname.startsWith(ruta)) return false;
    if (!query) return true;
    const pedida = new URLSearchParams(query).get('tab');
    const actual = new URLSearchParams(location.search).get('tab');
    // Sin ?tab= en la URL, el hub abre en su primera pestaña.
    return actual ? actual === pedida : pedida === 'espacios';
  };

  const itemSx = (active) => ({
    display: 'flex', alignItems: 'center', gap: 1.25,
    px: 1.5, py: 0.4, mx: 0.75, borderRadius: '5px', mb: 0.25,
    cursor: 'pointer', position: 'relative',
    bgcolor: active ? (d ? 'color-mix(in srgb, var(--af-acento) 14%, transparent)' : 'color-mix(in srgb, var(--af-acento) 9%, transparent)') : 'transparent',
    color: active ? 'var(--af-acento)' : textMuted,
    // La línea del ítem activo es el único toque de color de la barra.
    borderLeft: active ? '2px solid var(--af-color)' : '2px solid transparent',
    '&:hover': { bgcolor: active ? (d ? 'color-mix(in srgb, var(--af-acento) 18%, transparent)' : 'color-mix(in srgb, var(--af-acento) 12%, transparent)') : bgHover, color: active ? 'var(--af-acento)' : textActive },
    transition: 'all 0.12s',
  });

  const iconColor = (active) => active ? 'var(--af-acento)' : textDisabled;

  const userInitials = currentUser
    ? ((currentUser.first_name?.[0] || '') + (currentUser.last_name?.[0] || '') || currentUser.email?.[0] || 'U').toUpperCase()
    : 'U';

  // Los módulos de la barra. El selector Módulo / Automatización se mudó al encabezado
  // (15-10-2026, como Kapso): la barra dice DÓNDE se está, el selector QUÉ se ve de ahí.
  // Cada módulo lleva a la última vista elegida.
  const ICONOS = {
    ventas:       <ShoppingCart size={15} />,
    compras:      <PackageOpen size={15} />,
    inventario:   <Boxes size={15} />,
    contabilidad: <Calculator size={15} />,
    finanzas:     <Wallet size={15} />,
  };
  const moduloAbierto = moduloDeRuta(location.pathname);
  // Los módulos desplegados en la barra. El módulo en el que se está se despliega solo al
  // entrar; la flecha (o un clic en el módulo en el que ya se está) lo pliega o despliega a
  // mano, y cualquier otro se puede desplegar sin salir de donde se está.
  const [desplegados, setDesplegados] = useState(() => new Set(moduloAbierto ? [moduloAbierto.slug] : []));
  useEffect(() => {
    if (moduloAbierto?.slug) setDesplegados((d) => (d.has(moduloAbierto.slug) ? d : new Set(d).add(moduloAbierto.slug)));
  }, [moduloAbierto?.slug]);
  const alternarModulo = (slug) => setDesplegados((d) => {
    const n = new Set(d);
    if (n.has(slug)) n.delete(slug); else n.add(slug);
    return n;
  });

  // ── Los tres modos ── ⛔ DESCONECTADOS el 2026-10-14 ─────────────────────────
  // El conmutador los reemplazó por Módulo / Automatización. Quedan acá, como los
  // items de abajo, por si alguno vuelve.
  //   Trabajo  — el dia a dia: chat, agentes, disparadores, tablero.
  //   Espacios — de donde sale lo que el agente sabe: espacios, conexiones,
  //              documentos y el contexto de la empresa.
  //   Admin    — la empresa: personas, agentes, ajustes, plan.
  // eslint-disable-next-line no-unused-vars
  const MODOS_DESCONECTADOS = [
    { key: 'trabajo',  label: 'Trabajo',  icon: <MessageSquare size={14} /> },
    { key: 'espacios', label: 'Workspaces', icon: <Layers size={14} /> },
    { key: 'admin',    label: 'Admin',    icon: <Settings size={14} /> },
  ];

  const ITEMS_DESCONECTADOS = {
    trabajo: {
      seccion: null,
      items: [
        // Las Tareas estaban SOLO adentro de su Sesion, cuatro niveles abajo: "que tengo
        // pendiente" no se podia contestar sin abrir Sesion por Sesion. Sube al menu del
        // dia a dia, que es cuando se hace esa pregunta.
        { path: '/app/tareas',           label: 'Tareas',       icon: <CheckSquare size={15} /> },
        // Los Disparadores estaban en el modo Espacios, donde no son un espacio.
        // Automatizar lo que uno quiere OBTENER de Afable es trabajo del dia a dia.
        { path: '/app/automatizaciones', label: 'Disparadores', icon: <Timer size={15} /> },
        { path: '/app/tablero',          label: 'Tablero',      icon: <LayoutDashboard size={15} /> },
      ],
    },
    espacios: {
      seccion: 'Conocimiento',
      // Las cuatro pestañas del hub suben al menu. Estaban un nivel mas abajo,
      // dentro de una pantalla titulada "Espacios": quien buscaba donde conectar
      // su Odoo tenia que adivinar que estaba ahi.
      items: [
        { path: '/app/contexto?tab=espacios',     label: 'Workspaces', icon: <Layers size={15} /> },
        { path: '/app/contexto?tab=integraciones', label: 'Conexiones', icon: <Plug size={15} /> },
        { path: '/app/archivos',                  label: 'Archivos',    icon: <FolderOpen size={15} /> },
        { path: '/app/contexto?tab=mi-contexto',  label: 'Contexto de la empresa', icon: <BookOpen size={15} /> },
      ],
    },
    admin: {
      seccion: 'Empresa',
      items: [
        { path: '/app/admin/personas',  label: 'Personas',      icon: <Users size={14} /> },
        { path: '/app/admin/workspace', label: 'Su empresa',    icon: <Building2 size={14} /> },
        { path: '/app/configuracion',   label: 'Configuración', icon: <Settings size={14} /> },
        // Decia "Plan" y llevaba a la vitrina de precios, que no dice con que se esta
        // pagando ni que se cobro. La pantalla real es Facturacion.
        { path: '/app/admin/facturacion', label: 'Facturación', icon: <CreditCard size={14} /> },
      ],
    },
  };

  // ⛔ DESCONECTADO el 2026-09-01, por decisión del usuario: se rehace la funcionalidad
  // interna desde cero y cada item se vuelve a enchufar cuando su pantalla esté lista y
  // en el lugar que le corresponde.
  //
  // NADA SE BORRÓ. El menú de tres modos sigue completo arriba, en
  // `ITEMS_DESCONECTADOS`; las rutas siguen definidas en `App.jsx` y los endpoints
  // siguen respondiendo. Reconectar un item es moverlo de esa constante a esta.
  //
  // Lo único vivo adentro es el CHAT y su historial de conversaciones.
  // El 2026-10-14 los modos se reemplazaron por Módulo / Automatización: lo vivo en la
  // barra es el chat y los MODULOS de más arriba.

  // La lista de Sesiones de la barra viaja con el resto: vuelve cuando volvamos a
  // enchufar Sesiones. La carga de datos se deja como está para no tocar su lógica.
  const MOSTRAR_SESIONES = false;
  // El Chat salió de la barra el 18-10-2026 y volvió el 25-10-2026 como lo principal, arriba
  // de los módulos: lleva al chat completo. El panel lateral sigue siendo el chat de cada
  // módulo, y sus hilos aparecen aquí en el historial con el nombre del módulo.
  const MOSTRAR_CHAT = true;

  // El buscador de la barra. Sale por lo mismo que el del encabezado: con el menú
  // desconectado no hay qué buscar todavía. El bloque queda entero abajo.
  const MOSTRAR_BUSCADOR = false;

  // La ficha del usuario, igual en los tres modos.
  const accountMenuItems = [
    { path: '/app/ajustes/perfil', label: 'Mi perfil', icon: <User size={14} /> },
    { path: '/app/ajustes', label: 'Configuración', icon: <Settings size={14} /> },
    { path: '/app/ayuda',  label: 'Ayuda',     icon: <HelpCircle size={14} /> },
  ];

  const drawer = (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>

      {/* ── La marca ─────────────────────────────────────────────────────────
          Arriba a la izquierda, donde se busca sin pensar y donde lleva de vuelta
          al inicio. Estaba solo en login, registro y la landing: adentro de la app
          no aparecía en ninguna parte, así que el producto no se nombraba a sí
          mismo. Plegada la barra queda solo el isotipo. */}
      <Box
        onClick={() => navigate('/app')}
        sx={{
          display: 'flex', alignItems: 'center', flexShrink: 0, cursor: 'pointer',
          justifyContent: open ? 'flex-start' : 'center',
          px: open ? 1.5 : 0.5, pt: 1.5, pb: 1,
          '&:hover': { opacity: 0.85 }, transition: 'opacity 0.12s',
        }}
      >
        {open ? <Logo size={22} /> : <Isotipo size={22} />}
        {/* Colapsar, en la misma fila de la marca (como Kapso). Antes iba en una fila
            propia junto al conmutador de modos, que se mudó al encabezado. */}
        {open && (
          <Box component="button" aria-label="Colapsar el panel"
            onClick={(e) => { e.stopPropagation(); handleDrawerToggle(); }}
            sx={{
              ml: 'auto', border: 'none', background: 'transparent', color: textDisabled,
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

      {/* ── Search ── desconectado, ver la bandera arriba */}
      {MOSTRAR_BUSCADOR && (
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
      )}

      {/* ── Main content (scrollable) ── */}
      <Box sx={{ flex: 1, overflowY: 'auto', overflowX: 'hidden', py: 0.5 }}>

        {/* Chat con su historial: desde aquí se maneja todo, así que va primero y en
            las dos posiciones del selector. */}
        {MOSTRAR_CHAT && (
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
                      onClick={(e) => { e.stopPropagation(); navigate('/app/chat', { state: { nueva: true } }); }}
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
                    {/* La barra muestra las diez ultimas a proposito. El buscador es la
                        salida: sin el, diez es un tope que se lee como "no hay mas". */}
                    <Box
                      onClick={() => window.dispatchEvent(new Event('afable-open-search'))}
                      sx={{
                        display: 'flex', alignItems: 'center', gap: 0.75,
                        px: 1, py: 0.35, borderRadius: '4px', cursor: 'pointer',
                        color: textDisabled, '&:hover': { bgcolor: bgHover, color: textMuted },
                        transition: 'all 0.1s',
                      }}
                    >
                      <Search size={13} />
                      <Typography sx={{ fontSize: '0.78rem' }}>Buscar conversaciones</Typography>
                    </Box>
                    {conversations.map(conv => (
                      <Box
                        key={conv.id}
                        onClick={() => navigate('/app/chat', { state: { conversationId: conv.id } })}
                        onMouseEnter={() => setEncima(`conv-${conv.id}`)}
                        onMouseLeave={() => setEncima(null)}
                        sx={{
                          display: 'flex', alignItems: 'center', gap: 0.5,
                          px: 1, py: 0.35, borderRadius: '4px', cursor: 'pointer',
                          color: textDisabled, '&:hover': { bgcolor: bgHover, color: textMuted },
                          transition: 'all 0.1s',
                        }}
                      >
                        <Typography sx={{ fontSize: '0.8rem', lineHeight: 1.4, flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {(conv.title || 'Conversación').slice(0, 28)}
                        </Typography>
                        {/* Un hilo del panel lateral dice de qué módulo es: es la misma
                            conversación que sigue al abrir el chat dentro de ese módulo. */}
                        {moduloDeConversacion(conv) && (
                          <Typography sx={{ fontSize: '0.68rem', fontWeight: 500, flexShrink: 0, color: tonoDeConversacion(conv).color, px: 0.6, borderRadius: '4px', bgcolor: tonoDeConversacion(conv).suave }}>
                            {moduloDeConversacion(conv)}
                          </Typography>
                        )}
                        {/* Un hilo compartido se distingue de un vistazo: si no, no hay
                            forma de saber qué ve el equipo y qué no. */}
                        {conv.sesion_nombre && (
                          <Typography
                            title={`Compartida en ${conv.sesion_nombre}`}
                            sx={{ fontSize: '0.7rem', flexShrink: 0, color: 'var(--af-acento-suave)' }}
                          >
                            ●
                          </Typography>
                        )}
                        <MenuDeFila
                          visible={encima === `conv-${conv.id}`}
                          titulo={conv.title || 'Conversación'}
                          acciones={[
                            {
                              clave: 'compartir',
                              label: conv.sesion_nombre ? 'Cambiar de Sesión…' : 'Compartir con el equipo…',
                            },
                            {
                              clave: 'eliminar', label: 'Eliminar', color: '#e5484d',
                              confirmar: true,
                              aviso: 'Se borran los mensajes de esta conversación. No se puede deshacer.',
                            },
                          ]}
                          onElegir={(clave) => accionDeConversacion(conv, clave)}
                        />
                      </Box>
                    ))}
                  </Box>
                </Box>
              </Collapse>
            )}
          </Box>
        )}

        {/* Sesiones: donde trabaja el equipo. Solo en Trabajo, como el chat.
            ⛔ Desconectada el 2026-09-01 con `MOSTRAR_SESIONES`. El bloque queda entero:
            volver a mostrarla es poner esa bandera en true. */}
        {MOSTRAR_SESIONES && (
          <Box sx={{ mb: 0.5 }}>
            <Tooltip title={!open ? 'Sesiones' : ''} placement="right" arrow>
              <Box sx={itemSx(isActive('/app/sesiones'))} onClick={() => setSesionesOpen(p => !p)}>
                <Boxes size={15} color={iconColor(isActive('/app/sesiones'))} style={{ flexShrink: 0 }} />
                {open && (
                  <>
                    <Typography sx={{ fontSize: '0.9rem', color: 'inherit', flex: 1 }}>
                      Sesiones
                    </Typography>
                    <Box
                      onClick={(e) => { e.stopPropagation(); setSesionesOpen(true); setNombreNueva(''); }}
                      title="Nueva Sesión"
                      sx={{
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        width: 18, height: 18, borderRadius: '4px', flexShrink: 0,
                        color: textDisabled, '&:hover': { bgcolor: bgHover, color: textActive },
                      }}
                    >
                      <Plus size={12} />
                    </Box>
                    {sesiones.length > 0 && (
                      <Box sx={{ display: 'flex', p: 0.25, borderRadius: '4px', flexShrink: 0 }}>
                        {sesionesOpen ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                      </Box>
                    )}
                  </>
                )}
              </Box>
            </Tooltip>

            {open && (
              <Collapse in={sesionesOpen}>
                <Box sx={{ pl: 3.5, pr: 0.75, mt: 0.25 }}>
                  {nombreNueva !== null && (
                    <InputBase
                      autoFocus
                      value={nombreNueva}
                      onChange={(e) => setNombreNueva(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') crearSesion();
                        if (e.key === 'Escape') setNombreNueva(null);
                      }}
                      onBlur={() => { if (!nombreNueva.trim()) setNombreNueva(null); }}
                      placeholder="Nombre de la Sesión"
                      sx={{
                        px: 1, py: 0.35, mb: 0.25, width: '100%', fontSize: '0.8rem',
                        borderRadius: '4px', bgcolor: bgHover, color: textActive,
                      }}
                    />
                  )}
                  {sesiones.length === 0 && nombreNueva === null ? (
                    <Typography sx={{ fontSize: '0.78rem', color: textDisabled, px: 1, py: 0.4 }}>
                      Ninguna todavía.
                    </Typography>
                  ) : sesiones.map(s => {
                    const activa = location.pathname === `/app/sesiones/${s.slug}`;
                    return (
                      <Box
                        key={s.id}
                        onClick={() => navigate(`/app/sesiones/${s.slug}`)}
                        onMouseEnter={() => setEncima(`ses-${s.id}`)}
                        onMouseLeave={() => setEncima(null)}
                        sx={{
                          display: 'flex', alignItems: 'center', gap: 0.75,
                          px: 1, py: 0.35, borderRadius: '4px', cursor: 'pointer',
                          color: activa ? 'var(--af-acento)' : textDisabled,
                          '&:hover': { bgcolor: bgHover, color: activa ? 'var(--af-acento)' : textMuted },
                          transition: 'all 0.1s',
                        }}
                      >
                        <Typography sx={{ fontSize: '0.8rem', flexShrink: 0 }}>{s.icon || '💠'}</Typography>
                        <Box sx={{ flex: 1, minWidth: 0 }}>
                          <Typography sx={{
                            fontSize: '0.8rem', lineHeight: 1.4,
                            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                            fontWeight: activa ? 600 : 400,
                          }}>
                            {s.name}
                          </Typography>
                          {/* De dónde viene. Es la alternativa a esconderla: quien eligió
                              un Workspace arriba entiende por qué está acá una Sesión de
                              otro, en vez de creer que se perdió la que buscaba. */}
                          {variosWorkspaces && s.workspace_name && (
                            <Typography sx={{
                              fontSize: '0.66rem', lineHeight: 1.3, color: textDisabled,
                              overflow: 'hidden', textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                            }}>
                              {s.workspace_name}
                            </Typography>
                          )}
                        </Box>
                        <MenuDeFila
                          visible={encima === `ses-${s.id}`}
                          titulo={s.name}
                          acciones={[
                            { clave: 'copiar', label: 'Copiar enlace' },
                            {
                              clave: 'archivar',
                              label: s.archivada ? 'Desarchivar' : 'Archivar',
                              aviso: 'Sale de la barra lateral. Su contenido queda intacto.',
                            },
                            {
                              clave: 'eliminar', label: 'Eliminar', color: '#e5484d',
                              confirmar: true,
                              aviso: 'Se llevan las conversaciones, las tareas y los archivos de '
                                   + 'esta Sesión. No se puede deshacer.',
                            },
                          ]}
                          onElegir={(clave) => accionDeSesion(s, clave)}
                        />
                        {s.pendientes > 0 && (
                          <Typography sx={{
                            fontSize: '0.68rem', fontWeight: 700, flexShrink: 0,
                            px: 0.5, borderRadius: '4px',
                            bgcolor: 'rgba(240, 180, 41, 0.16)', color: '#f0b429',
                          }}>
                            {s.pendientes}
                          </Typography>
                        )}
                      </Box>
                    );
                  })}
                </Box>
              </Collapse>
            )}
          </Box>
        )}

        {/* Los módulos. */}
        {open && (
          <Typography sx={{
            px: 2, pt: 1, pb: 0.5, fontSize: '0.72rem', fontWeight: 600,
            color: textDisabled, letterSpacing: '0.06em', textTransform: 'uppercase',
          }}>
            Módulos
          </Typography>
        )}

        {MODULOS.map((m) => {
          // Encendido en sus dos páginas: el selector ya dice en cuál de ellas se está.
          const activo = moduloAbierto?.slug === m.slug;
          // Las secciones del módulo, como submenú plegable.
          const secciones = seccionesDe(m.slug, { dte: dteDisponible });
          const conSubmenu = open && secciones.length > 0;
          const desplegado = conSubmenu && desplegados.has(m.slug);
          return (
            <Box key={m.slug}>
              <Tooltip title={!open ? m.label : ''} placement="right" arrow>
                <Box sx={itemSx(activo)} onClick={() => (activo && conSubmenu ? alternarModulo(m.slug) : navigate(rutaDe(m.slug, vistaGuardada())))}>
                  <Box sx={{ color: iconColor(activo), flexShrink: 0, display: 'flex' }}>
                    {ICONOS[m.slug]}
                  </Box>
                  {open && (
                    <Typography sx={{ fontSize: '0.9rem', fontWeight: activo ? 500 : 400, color: 'inherit', flex: 1 }}>
                      {m.label}
                    </Typography>
                  )}
                  {conSubmenu && (
                    <Box
                      onClick={(e) => { e.stopPropagation(); alternarModulo(m.slug); }}
                      sx={{ display: 'flex', p: 0.25, borderRadius: '4px', flexShrink: 0, color: textDisabled, '&:hover': { bgcolor: bgHover, color: textActive } }}
                    >
                      {desplegado ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                    </Box>
                  )}
                </Box>
              </Tooltip>
              {conSubmenu && (
                <Collapse in={desplegado}>
                <Box sx={{ pl: 3.5, pr: 0.75, mt: 0.25, mb: 0.5 }}>
                  {secciones.map((sec) => {
                    const actual = activo && moduloAbierto.vista === 'modulo' && moduloAbierto.seccion === sec.slug;
                    return (
                      <Box key={sec.slug} onClick={() => navigate(`/app/${m.slug}/${sec.slug}`)}
                        sx={{
                          px: 1, py: 0.4, borderRadius: '4px', cursor: 'pointer',
                          fontSize: '0.84rem', lineHeight: 1.45,
                          color: actual ? textActive : textDisabled,
                          fontWeight: actual ? 500 : 400,
                          borderLeft: actual ? '2px solid var(--af-color)' : '2px solid transparent',
                          '&:hover': { bgcolor: bgHover, color: textActive },
                          transition: 'all 0.1s',
                        }}>
                        {sec.label}
                      </Box>
                    );
                  })}
                </Box>
                </Collapse>
              )}
            </Box>
          );
        })}

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
          <Avatar src={currentUser?.avatar_url} sx={{ width: 24, height: 24, fontSize: '0.65rem', bgcolor: 'var(--af-acento)', flexShrink: 0 }}>
            {userInitials}
          </Avatar>
          {open && (
            <Typography sx={{ fontSize: '0.75rem', color: textMuted, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 100 }}>
              {currentUser?.email || ''}
            </Typography>
          )}
        </Box>
      </Box>

      {/* Compartir una conversación = moverla a una Sesión: deja el historial privado
          y pasa a verla el equipo de esa Sesión. */}
      <DialogoCompartir
        abierto={Boolean(compartiendo)}
        onCerrar={() => setCompartiendo(null)}
        sesiones={sesiones}
        sesionActual={compartiendo?.sesion_slug || ''}
        conversacion={compartiendo}
        onCompartir={compartir}
      />

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
