import { useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Box, Drawer, IconButton, Tooltip, Typography } from '@mui/material';
import { MessageSquare, Settings2, X } from 'lucide-react';
import { moduloDeRuta, seccionDe } from './modulos';
import ChatLateral from './ChatLateral';
import IsotipoPensando from '../../components/IsotipoPensando';
import { PanelContext, usePanelLateral } from './panelContexto';
import { CONFIGURACION_DE_MODULO } from '../../pages/modulos/Configuraciones';
import { useWorkspace } from '../../context/WorkspaceContext';
import { api } from '../../services/api';

/*
 * El panel de la derecha (18-10-2026): la barra superior muestra siempre el chat y, dentro
 * de un módulo que la tenga, su configuración. Los dos se abren al costado sin salir de la
 * pantalla. El chat sabe qué está mirando el usuario: el módulo y la sección salen de la
 * dirección, y cada pantalla puede agregar el detalle (el libro, el año) con usePantalla.
 *
 * Cada contexto (un módulo, o "general" fuera de ellos) tiene su propio hilo, guardado en el
 * servidor con `contexto = "<empresa>:<módulo>"`: al volver, sigue la misma conversación.
 */

export const ANCHO_PANEL = 420;
const CHAT_VACIO = { convId: null, mensajes: [], cargado: true };

export function PanelLateralProvider({ children }) {
  const [abierto, setAbierto] = useState(null);       // 'chat' | 'config' | null
  const [detalle, setDetalle] = useState('');
  const [chats, setChats] = useState({}); // { [contexto]: { convId, mensajes, cargado } }
  const { pathname } = useLocation();
  const { slug } = useWorkspace();
  const modulo = moduloDeRuta(pathname);
  const tieneConfig = Boolean(modulo && CONFIGURACION_DE_MODULO[modulo.slug]);
  const contexto = `${slug || 'personal'}:${modulo?.slug || 'general'}`;
  const chat = chats[contexto] || CHAT_VACIO;

  // Sin configuración en la pantalla nueva, ese panel se cierra. En el chat completo, el
  // panel de chat sobra.
  useEffect(() => {
    if (abierto === 'config' && !tieneConfig) setAbierto(null);
    if (abierto === 'chat' && (pathname.startsWith('/app/chat') || modulo?.vista === 'automatizacion')) setAbierto(null);
  }, [modulo?.slug, tieneConfig, pathname]); // eslint-disable-line react-hooks/exhaustive-deps

  // El hilo de este contexto se trae del servidor la primera vez que se abre el chat aquí.
  useEffect(() => {
    if (abierto !== 'chat' || chats[contexto]) return;
    setChats((cs) => ({ ...cs, [contexto]: { ...CHAT_VACIO, cargado: false } }));
    (async () => {
      let hilo = CHAT_VACIO;
      try {
        const { data } = await api.getConversations({ contexto, limite: 1 });
        if (data[0]) {
          const { data: conv } = await api.getConversationMessages(data[0].id);
          hilo = { convId: conv.id, cargado: true, mensajes: conv.messages.map((m) => ({ role: m.role, content: m.content, acciones: m.acciones || [], pasos: m.pasos || [], listo: true })) };
        }
      } catch { /* sin historial: se empieza de cero */ }
      setChats((cs) => ({ ...cs, [contexto]: hilo }));
    })();
  }, [abierto, contexto]); // eslint-disable-line react-hooks/exhaustive-deps

  // Cambia el hilo de UN contexto: el de la pregunta, aunque el usuario ya se haya movido.
  const setChatDe = useCallback((clave, cambio) => setChats((cs) => {
    const actual = cs[clave] || CHAT_VACIO;
    return { ...cs, [clave]: typeof cambio === 'function' ? cambio(actual) : cambio };
  }), []);

  const pantalla = useMemo(() => {
    if (!modulo) return '';
    const partes = [modulo.label,
      modulo.vista === 'automatizacion' ? 'Automatizaciones' : seccionDe(modulo.slug, modulo.seccion)?.label];
    return [...partes.filter(Boolean), detalle].filter(Boolean).join(' › ');
  }, [modulo?.slug, modulo?.vista, modulo?.seccion, detalle]); // eslint-disable-line react-hooks/exhaustive-deps

  const valor = {
    abierto, modulo, tieneConfig, pantalla, contexto, chat, setChatDe, setDetalle,
    abrir: (p) => setAbierto((a) => (a === p ? null : p)),
    cerrar: () => setAbierto(null),
  };
  return <PanelContext.Provider value={valor}>{children}</PanelContext.Provider>;
}

/* Una pantalla le cuenta al chat lo que muestra además del módulo y la sección. */
export function usePantalla(detalle) {
  const ctx = useContext(PanelContext);
  const set = ctx?.setDetalle;
  useEffect(() => {
    if (!set) return undefined;
    set(detalle || '');
    return () => set('');
  }, [set, detalle]);
}

/* Los botones de la barra superior, a la derecha. */
export function BotonesPanel({ color }) {
  const ctx = usePanelLateral();
  const { pathname } = useLocation();
  const navigate = useNavigate();
  if (!ctx || pathname.startsWith('/app/chat')) return null;
  // En la vista "Agente" la conversación ya está en la página: el botón de chat sobraría.
  const enAgente = ctx.modulo?.vista === 'automatizacion';
  const conQuien = ctx.modulo ? `Hablar con el ${ctx.modulo.agente}` : 'Preguntarle a Afable';
  // La configuración del módulo vive en Configuración › Módulos (28-10-2026); el chat, al costado.
  const abrir = (clave) => (clave === 'config' ? navigate(`/app/ajustes/modulos/${ctx.modulo.slug}`) : ctx.abrir(clave));
  const boton = (clave, titulo, Icono) => (
    <Tooltip title={titulo} arrow>
      <IconButton size="small" aria-label={titulo} onClick={() => abrir(clave)}
        sx={{
          color: ctx.abierto === clave ? 'var(--af-acento)' : color,
          bgcolor: ctx.abierto === clave ? 'action.selected' : 'transparent',
          '&:hover': { color: 'var(--af-acento)', bgcolor: 'action.hover' },
        }}>
        <Icono size={16} />
      </IconButton>
    </Tooltip>
  );
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.25, ml: 'auto' }}>
      {ctx.tieneConfig && boton('config', `Configuración de ${ctx.modulo.label.toLowerCase()}`, Settings2)}
      {!enAgente && boton('chat', conQuien, MessageSquare)}
    </Box>
  );
}

/* Lo que estorba con el panel abierto (la burbuja de soporte tapa el botón de enviar). */
export function SoloSinPanel({ children }) {
  const ctx = usePanelLateral();
  return ctx?.abierto ? null : children;
}

/* El panel en sí: una capa a la derecha, sobre toda la pantalla, con el fondo oscurecido.
   Se cierra con la X, con Escape o con un clic afuera. */
export function PanelLateral() {
  const ctx = usePanelLateral();
  const abierto = Boolean(ctx?.abierto === 'chat' || (ctx?.abierto === 'config' && ctx.modulo));
  if (!abierto) return null;
  const Config = ctx.modulo && CONFIGURACION_DE_MODULO[ctx.modulo.slug];
  // El chat de un módulo es la conversación con su agente (25-10-2026).
  const titulo = ctx.abierto === 'chat'
    ? (ctx.modulo ? ctx.modulo.agente : 'Afable')
    : `Configuración de ${ctx.modulo.label.toLowerCase()}`;
  return (
    // Encima de todo, también de la barra superior (que está en drawer + 1).
    <Drawer anchor="right" open onClose={ctx.cerrar} sx={{ zIndex: (t) => t.zIndex.modal }}
      slotProps={{ backdrop: { sx: { bgcolor: 'rgba(10, 10, 15, 0.35)' } } }}
      PaperProps={{ component: 'aside', sx: {
        width: ANCHO_PANEL, maxWidth: '100vw', bgcolor: 'background.paper', backgroundImage: 'none',
        display: 'flex', flexDirection: 'column', boxShadow: '0 0 40px rgba(0,0,0,0.18)',
      } }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, px: 2, py: 1.25, borderBottom: '1px solid', borderColor: 'divider' }}>
        {ctx.abierto === 'chat' && (
          <Box sx={{ width: 30, height: 30, borderRadius: '9px', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
            bgcolor: 'var(--af-color-suave)' }}>
            <IsotipoPensando girando={false} size={15} />
          </Box>
        )}
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography sx={{ fontFamily: "'Sora', sans-serif", fontWeight: 600, fontSize: '0.95rem' }}>{titulo}</Typography>
          {ctx.abierto === 'chat' && ctx.pantalla && (
            <Typography noWrap sx={{ fontSize: '0.74rem', color: 'text.secondary' }}>Viendo: {ctx.pantalla}</Typography>
          )}
        </Box>
        <IconButton size="small" onClick={ctx.cerrar} aria-label="Cerrar panel"><X size={16} /></IconButton>
      </Box>
      <Box sx={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
        {ctx.abierto === 'chat' ? <ChatLateral /> : Config && <Box sx={{ flex: 1, overflow: 'auto', p: 2 }}><Config /></Box>}
      </Box>
    </Drawer>
  );
}
