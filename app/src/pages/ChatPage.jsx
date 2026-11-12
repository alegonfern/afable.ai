import { useState, useRef, useEffect, useCallback, useLayoutEffect } from 'react';
import Cookies from 'js-cookie';
import {
  Box, Typography, IconButton, TextField,
  Tooltip, Chip, CircularProgress, useTheme, Avatar, Skeleton,
  Button, Menu, MenuItem, Collapse,
} from '@mui/material';
import {
  Send, Paperclip, AtSign, User, Sparkles,
  Database, FileText, TrendingUp, BarChart2, Users,
  Copy, ThumbsUp, ChevronDown, AlertCircle, RefreshCw,
  ArrowUpRight, X, Plug, GitBranch, Pencil, ArrowUp, Mic, Square,
} from 'lucide-react';
import { hayDictado, useDictado, leerEnVoz, callar } from '../services/voz';
import { useNavigate, useLocation, useOutletContext } from 'react-router-dom';
import { toast } from 'react-toastify';
import { AfableMark } from '../components/Logo';
import { Entra } from '../components/Animado';
import { api } from '../services/api';
import TarjetasDelChat from '../components/TarjetasDelChat';
import IsotipoPensando from '../components/IsotipoPensando';
import PasosDelChat from '../components/PasosDelChat';
import { avisarRespuesta, pedirPermisoDeAvisos } from '../services/avisoRespuesta';
import PanelNecesitaAccion from '../components/PanelNecesitaAccion';
import { useApp } from '../context/AppContext';
import { useWorkspace } from '../context/WorkspaceContext';
import { DocumentoAlLado, TarjetaDeArtefacto } from '../components/DocumentoDelChat';
import ReactMarkdown, { defaultUrlTransform } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import Cookies2 from 'js-cookie';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001/api/v1';


const TERMINAL_STEPS = [
  'Conectando con el modelo',
  'Procesando contexto empresarial',
  'Consultando fuentes de datos',
  'Generando respuesta',
];

// ── Markdown ──────────────────────────────────────────────────────────────────
// react-markdown sanitiza data-URIs por defecto; las figuras del análisis Python
// llegan como data:image/png — hay que dejarlas pasar explícitamente.
const allowChartImages = (url) =>
  url.startsWith('data:image/') ? url : defaultUrlTransform(url);

function MarkdownContent({ content }) {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  return (
    <Box sx={{
      '& p': { m: 0, mb: 0.75, lineHeight: 1.7, '&:last-child': { mb: 0 } },
      '& h1,& h2,& h3': { fontWeight: 600, mb: 1, mt: 1.5, '&:first-of-type': { mt: 0 } },
      '& h1': { fontSize: '1.05rem' }, '& h2': { fontSize: '0.95rem' },
      '& h3': { fontSize: '0.88rem', color: theme.palette.text.secondary },
      '& ul,& ol': { pl: 2.5, mb: 0.75 }, '& li': { mb: 0.3, lineHeight: 1.7 },
      '& code': { fontFamily: '"JetBrains Mono","Fira Code",monospace', fontSize: '0.79rem',
        bgcolor: d ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)', px: 0.6, py: 0.15, borderRadius: '4px' },
      '& pre': { bgcolor: d ? '#161616' : '#f0f0f0', border: `1px solid ${theme.palette.divider}`,
        borderRadius: '8px', p: 1.5, mb: 1, overflowX: 'auto', '& code': { bgcolor: 'transparent', p: 0 } },
      '& table': { width: '100%', borderCollapse: 'collapse', mb: 1.5, fontSize: '0.83rem',
        borderRadius: '8px', overflow: 'hidden', border: `1px solid ${theme.palette.divider}` },
      '& th': { bgcolor: d ? 'color-mix(in srgb, var(--af-acento) 10%, transparent)' : 'color-mix(in srgb, var(--af-acento) 6%, transparent)',
        px: 1.5, py: 0.875, textAlign: 'left', fontWeight: 600, fontSize: '0.78rem',
        borderBottom: `1px solid ${theme.palette.divider}`, color: d ? 'var(--af-acento-suave)' : 'var(--af-acento)' },
      '& td': { px: 1.5, py: 0.75, borderBottom: `1px solid ${theme.palette.divider}` },
      '& tr:last-child td': { borderBottom: 'none' },
      '& tr:hover td': { bgcolor: d ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.02)' },
      '& blockquote': { borderLeft: '3px solid var(--af-acento)', pl: 1.5, ml: 0, color: theme.palette.text.secondary, fontStyle: 'italic' },
      '& strong': { fontWeight: 600, color: theme.palette.text.primary },
      '& a': { color: 'var(--af-acento)', textDecoration: 'none', '&:hover': { textDecoration: 'underline' } },
      '& img': { maxWidth: '100%', borderRadius: '10px', my: 1, display: 'block',
        border: `1px solid ${theme.palette.divider}`, bgcolor: '#ffffff', p: 0.75 },
    }}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} urlTransform={allowChartImages}>{content}</ReactMarkdown>
    </Box>
  );
}

// ── Thinking ──────────────────────────────────────────────────────────────────
function ThinkingLoader({ step, label }) {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  // `label` = estado real del agente (consultando tablas, ejecutando SQL…).
  // Si no hay estado real aún, cae al ciclo genérico de pasos.
  const text = label || TERMINAL_STEPS[Math.min(step, TERMINAL_STEPS.length - 1)];
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, py: 1, px: 1.5,
      bgcolor: d ? 'color-mix(in srgb, var(--af-acento) 6%, transparent)' : 'color-mix(in srgb, var(--af-acento) 4%, transparent)',
      border: '1px solid color-mix(in srgb, var(--af-acento) 15%, transparent)', borderRadius: '10px', width: 'fit-content', maxWidth: 400 }}>
      <CircularProgress size={12} thickness={5} sx={{ color: 'var(--af-acento)' }} />
      <Typography sx={{ fontSize: '0.78rem', color: 'var(--af-acento-suave)', fontFamily: '"JetBrains Mono","Fira Code",monospace' }}>
        {text}
      </Typography>
    </Box>
  );
}

// ── Source badge ──────────────────────────────────────────────────────────────
/**
 * En qué se apoyó la respuesta, y **se puede abrir de un clic**.
 *
 * Antes decía el nombre del documento en texto gris: quien quería comprobar la cifra
 * tenía que ir a Archivos y buscarlo a mano. Para una empresa que va a DECIDIR con esa
 * respuesta, poder verificarla en un clic es lo que separa un juguete de una herramienta.
 *
 * `fuentes` llega como dato (`[{id, titulo}]`) y se guarda en el mensaje, así que
 * sobrevive a recargar. El texto plano se sigue leyendo como respaldo: los mensajes
 * anteriores a este cambio no tienen `fuentes` y no por eso deben quedarse sin su cita.
 */
function SourceBadge({ content, fuentes, navigate }) {
  const conId = (fuentes || []).filter((f) => f && f.id);
  if (conId.length) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mt: 0.75, flexWrap: 'wrap' }}>
        <Database size={11} color="#555" />
        {conId.map((f) => (
          <Box
            key={f.id}
            onClick={() => navigate(`/app/archivos/${f.id}`)}
            title="Abrir el documento"
            sx={{
              display: 'inline-flex', alignItems: 'center', gap: 0.4,
              px: 0.75, py: 0.15, borderRadius: '5px', cursor: 'pointer',
              fontSize: '0.7rem', color: 'var(--af-acento-suave)',
              border: '1px solid rgba(155, 166, 227, 0.3)',
              '&:hover': { bgcolor: 'rgba(155, 166, 227, 0.12)' },
            }}
          >
            {f.titulo}
          </Box>
        ))}
      </Box>
    );
  }

  const match = (content || '').match(/\[Fuente:\s*([^\]]+)\]/);
  if (!match) return null;
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mt: 0.75 }}>
      <Database size={11} color="#555" />
      <Typography sx={{ fontSize: '0.7rem', color: 'text.disabled', fontStyle: 'italic' }}>
        {match[1]}
      </Typography>
    </Box>
  );
}

function ModelBadge({ model }) {
  if (!model) return null;
  return (
    <Typography sx={{ fontSize: '0.65rem', color: 'text.disabled', mt: 0.75 }}>
      {model}
    </Typography>
  );
}

// Marca un archivo adjunto embebido en el content (ver ChatPage sendMessage).
const ATTACHMENT_RE = /\n?\[\[ARCHIVO_ADJUNTO:([^\]]+)\]\][\s\S]*?\[\[\/ARCHIVO_ADJUNTO\]\]/;

function stripAttachment(content) {
  return (content || '').replace(ATTACHMENT_RE, '').trim();
}

function AttachmentBadge({ content }) {
  const match = (content || '').match(ATTACHMENT_RE);
  if (!match) return null;
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mt: 0.5 }}>
      <Paperclip size={11} color="rgba(255,255,255,0.75)" />
      <Typography sx={{ fontSize: '0.7rem', color: 'rgba(255,255,255,0.75)' }}>
        {match[1]}
      </Typography>
    </Box>
  );
}

// ── Message bubble ────────────────────────────────────────────────────────────
function MessageBubble({ msg, onReintentar, onRamificar, onEditar, onResponder, yoId, navigate, onAbrirDoc }) {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const [copied, setCopied] = useState(false);
  const [editando, setEditando] = useState(false);
  const [borrador, setBorrador] = useState('');
  const isUser = msg.role === 'user';
  // Un mensaje sin autor es de antes de que los hilos fueran de a varios: se trata
  // como propio, que es lo que era.
  const esMio = !msg.autor || msg.autor.id === yoId;

  // Strip source citation from visible content
  const cleanContent = stripAttachment((msg.content || '').replace(/\n?\[Fuente:[^\]]+\]/g, '')).trim();

  // Corregir en el lugar: la burbuja se convierte en el campo. Un prompt del
  // navegador encima de la app se ve como un error, no como una función.
  if (isUser && editando) return (
    <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 2 }}>
      <Box sx={{ width: '72%', minWidth: 260 }}>
        <TextField
          value={borrador} onChange={(e) => setBorrador(e.target.value)}
          multiline fullWidth autoFocus size="small"
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              if (borrador.trim()) onEditar(borrador.trim());
              setEditando(false);
            }
            if (e.key === 'Escape') setEditando(false);
          }}
          sx={{ '& .MuiInputBase-root': { fontSize: '0.88rem', borderRadius: '14px' } }}
        />
        <Box sx={{ display: 'flex', gap: 1, justifyContent: 'flex-end', mt: 0.75 }}>
          <Button size="small" onClick={() => setEditando(false)} sx={{ textTransform: 'none', fontSize: '0.78rem' }}>
            Cancelar
          </Button>
          <Button
            size="small" variant="contained" disabled={!borrador.trim()}
            onClick={() => { onEditar(borrador.trim()); setEditando(false); }}
            sx={{ textTransform: 'none', fontSize: '0.78rem' }}
          >
            Corregir y volver a preguntar
          </Button>
        </Box>
        <Typography sx={{ fontSize: '0.7rem', color: 'text.disabled', textAlign: 'right', mt: 0.4 }}>
          Lo que viene después se borra: respondía a la pregunta anterior.
        </Typography>
      </Box>
    </Box>
  );

  if (!isUser && msg.streaming && !cleanContent && !msg.acciones?.length) return null;

  if (isUser) return (
    <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 2, gap: 1.25, alignItems: 'flex-start',
      '&:hover .acciones-usuario': { opacity: 1 } }}>
      {/* Corregir la propia pregunta. Aparece al pasar por encima para no
          ensuciar el hilo con botones que casi nunca se usan. */}
      {onEditar && (
        <Box className="acciones-usuario" sx={{ opacity: 0, transition: 'opacity .15s', alignSelf: 'center' }}>
          <Tooltip title="Corregir esta pregunta y volver a preguntar" placement="top">
            <IconButton
              size="small"
              onClick={() => { setBorrador(stripAttachment(msg.content)); setEditando(true); }}
              sx={{ color: 'text.disabled', '&:hover': { color: 'var(--af-acento-suave)' }, p: 0.4 }}
            >
              <Pencil size={11} />
            </IconButton>
          </Tooltip>
        </Box>
      )}
      <Box sx={{ maxWidth: '72%' }}>
        {/* Quien pregunto. Solo cuando NO fui yo: en un hilo propio, firmar cada
            mensaje con el nombre de uno mismo es ruido. */}
        {msg.autor && !esMio && (
          <Typography sx={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--af-acento-suave)', mb: 0.4, textAlign: 'right' }}>
            {msg.autor.nombre}
          </Typography>
        )}
        <Box sx={{ bgcolor: d ? '#232326' : '#f2f2f4', color: d ? '#e8e8ea' : '#1a1a1a',
          px: 2, py: 1.1, borderRadius: '14px', fontSize: '0.9rem', lineHeight: 1.6 }}>
          {stripAttachment(msg.content)}
          <AttachmentBadge content={msg.content} />
        </Box>
      </Box>
    </Box>
  );

  return (
    <Box sx={{ display: 'flex', gap: 1.5, mb: 2.5, alignItems: 'flex-start' }}>
      <Box sx={{ width: 28, height: 28, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <IsotipoPensando girando={false} size={20} />
      </Box>
      <Box sx={{ flex: 1, minWidth: 0 }}>
        {/* Lo que hizo o consultó en el ERP, como en la animación de la landing: va antes
            del texto, que lo cuenta (components/TarjetasDelChat). */}
        {/* Cómo llegó a la respuesta: los pasos, plegados (components/PasosDelChat). */}
        <PasosDelChat pasos={msg.pasos} />
        <TarjetasDelChat acciones={msg.acciones} onResponder={onResponder} animar={Boolean(msg.nuevo)} />
        {(cleanContent || msg.streaming) && (
        <Box sx={{ px: 0.25, py: 0.25,
          fontSize: '0.9rem', color: theme.palette.text.primary }}>
          {msg.streaming ? (
            <Box sx={{ display: 'flex', alignItems: 'flex-start' }}>
              <Typography sx={{ fontSize: '0.88rem', color: 'text.primary', lineHeight: 1.7 }}>
                {cleanContent || ''}
              </Typography>
              <Box sx={{ display: 'flex', gap: '3px', alignItems: 'center', ml: 0.5, mt: 0.5, flexShrink: 0 }}>
                {[0,1,2].map(i => (
                  <Box key={i} sx={{ width: 4, height: 4, borderRadius: '50%', bgcolor: 'var(--af-acento)',
                    animation: 'blink 1.2s ease-in-out infinite', animationDelay: `${i*0.2}s`,
                    '@keyframes blink': { '0%,100%': { opacity: 0.3 }, '50%': { opacity: 1 } } }} />
                ))}
              </Box>
            </Box>
          ) : <MarkdownContent content={cleanContent} /> }
          {/* Lo que el agente dejó ESCRITO en esta respuesta. Va dentro de la burbuja y
              no al pie con las fuentes: no es en qué se apoyó, es lo que hizo. */}
          {!msg.streaming && onAbrirDoc && (
            <TarjetaDeArtefacto artefactos={msg.artefactos} onAbrir={onAbrirDoc} />
          )}
        </Box>
        )}
        {!msg.streaming && (
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mt: 0.5 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <SourceBadge content={msg.content || ''} fuentes={msg.fuentes} navigate={navigate} />
            </Box>
            <Box sx={{ display: 'flex', gap: 0.5 }}>
              <Tooltip title={copied ? '¡Copiado!' : 'Copiar'} placement="top">
                <IconButton size="small" onClick={() => { navigator.clipboard.writeText(cleanContent); setCopied(true); setTimeout(() => setCopied(false), 1500); }}
                  sx={{ color: 'text.disabled', '&:hover': { color: 'text.secondary' }, p: 0.4 }}>
                  <Copy size={11} />
                </IconButton>
              </Tooltip>
              {onReintentar && (
                <Tooltip title="Volver a preguntar lo mismo" placement="top">
                  <IconButton size="small" onClick={onReintentar}
                    sx={{ color: 'text.disabled', '&:hover': { color: 'var(--af-acento-suave)' }, p: 0.4 }}>
                    <RefreshCw size={11} />
                  </IconButton>
                </Tooltip>
              )}
              {onRamificar && (
                <Tooltip title="Seguir por otro camino desde acá, sin perder este" placement="top">
                  <IconButton size="small" onClick={onRamificar}
                    sx={{ color: 'text.disabled', '&:hover': { color: 'var(--af-acento-suave)' }, p: 0.4 }}>
                    <GitBranch size={11} />
                  </IconButton>
                </Tooltip>
              )}
              <Tooltip title="Útil" placement="top">
                <IconButton size="small" sx={{ color: 'text.disabled', '&:hover': { color: '#34D399' }, p: 0.4 }}>
                  <ThumbsUp size={11} />
                </IconButton>
              </Tooltip>
            </Box>
          </Box>
        )}
      </Box>
    </Box>
  );
}

// ── Bienvenida ────────────────────────────────────────────────────────────────
// El chat vacío (25-10-2026), como el de la animación de la landing: lo principal es
// pedirle cosas al ERP. Las sugerencias son las mismas del panel lateral de cada módulo
// (layout/Dashboard/ChatLateral.jsx).
const SUGERENCIAS = [
  '¿Cómo va mi empresa este mes?',
  '¿Qué órdenes de venta me faltan por facturar?',
  '¿Qué productos están bajo el stock mínimo?',
  '¿Cuánto IVA tengo que pagar este mes?',
  '¿Quién me debe y desde cuándo?',
  '¿Qué tengo que pagar esta semana?',
];

function Bienvenida({ onPreguntar }) {
  return (
    <Box sx={{ flex: '1 0 auto', display: 'flex', flexDirection: 'column', justifyContent: 'flex-end',
      px: { xs: 2, sm: 3, md: 4 }, pb: 2, maxWidth: 780, mx: 'auto', width: '100%' }}>
      <Entra>
        <Typography sx={{ fontSize: { xs: '1.5rem', md: '1.85rem' }, fontWeight: 600, letterSpacing: '-0.03em', mb: 2 }}>
          Pídale algo a <Box component="span" sx={{ fontStyle: 'italic', pr: '0.1em', background: 'var(--af-degradado)', WebkitBackgroundClip: 'text',
            backgroundClip: 'text', color: 'transparent' }}>Afable</Box>
        </Typography>
      </Entra>
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
        {SUGERENCIAS.map((texto, i) => (
          <Entra key={texto} retraso={0.04 * i}>
            <Box component="button" onClick={() => onPreguntar(texto)} sx={{
              px: 1.75, py: 0.85, borderRadius: '999px', cursor: 'pointer', fontFamily: 'inherit', fontSize: '0.86rem',
              color: 'text.secondary', bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider',
              transition: 'all 0.12s', '&:hover': { color: 'text.primary', borderColor: 'var(--af-color)' },
            }}>
              {texto}
            </Box>
          </Entra>
        ))}
      </Box>
    </Box>
  );
}

// Lo que se estaba viendo al salir del chat (25-10-2026): la conversación y hasta dónde se había
// bajado. La página se desmonta al ir a un módulo; sin esto, al volver se rearmaba vacía, cargaba
// el hilo y bajaba animada hasta el final, que se veía como un salto. El "+" de la barra entra con
// `state.nueva` y empieza de cero.
const memoria = { convId: null, messages: [], scrollTop: null };

// ── Main ──────────────────────────────────────────────────────────────────────
export default function ChatPage() {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const navigate = useNavigate();
  const location = useLocation();
  const { focusMode } = useOutletContext() || {};
  const { aiModel, currentUser } = useApp();
  const { slug, espacioSlug } = useWorkspace();
  // Qué documento está abierto al lado. Uno solo: dos paneles competirían por el ancho y
  // la conversación quedaría en una franja.
  const [docAlLado, setDocAlLado] = useState(null);
  // Sube cada vez que el agente deja algo escrito, para que el panel abierto se ponga al día.
  const [refrescoDoc, setRefrescoDoc] = useState(0);
  // La Sesion desde la que se abrio el hilo, si vino de una.
  //
  // Es una REFERENCIA y no estado a proposito: el mensaje inicial se manda en el mismo
  // tick en que llega la Sesion, y `setState` no se aplica hasta el dibujado siguiente
  // — con estado, el primer mensaje salia sin Sesion y la conversacion quedaba
  // personal. Una ref se lee al instante.
  const sesionDelHilo = useRef(null);

  // ¿Se vuelve a lo que se estaba viendo? Solo si no se pidió otra conversación ni una nueva.
  const restaurado = useRef(null);
  if (restaurado.current === null) {
    const pedida = location.state?.conversationId || new URLSearchParams(location.search).get('conversation');
    if (location.state?.nueva) Object.assign(memoria, { convId: null, messages: [], scrollTop: null });
    restaurado.current = !location.state?.nueva && memoria.messages.length > 0
      && (!pedida || Number(pedida) === memoria.convId);
  }
  const [messages, setMessages] = useState(() => (restaurado.current ? memoria.messages : []));
  const [input, setInput] = useState('');
  const [convId, setConvId] = useState(() => (restaurado.current ? memoria.convId : null));
  const [loading, setLoading] = useState(false);
  const [thinkStep, setThinkStep] = useState(0);
  const [liveStatus, setLiveStatus] = useState(null);
  const [showThinking, setShowThinking] = useState(false);
  const [showScrollBtn, setShowScrollBtn] = useState(false);
  // Sube después de cada respuesta: el panel de la derecha se pone al día con lo que hizo.
  const [refrescoPanel, setRefrescoPanel] = useState(0);

  const [attachment, setAttachment] = useState(null);     // {name, extracted_text, error}
  const [attaching, setAttaching] = useState(false);

  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  // Si la pregunta se dictó, la respuesta se lee en voz alta al terminar.
  const responderEnVoz = useRef(false);
  const messagesBoxRef = useRef(null);
  const thinkIntervalRef = useRef(null);
  const fileInputRef = useRef(null);

  const handleFileChange = useCallback(async (e) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    setAttaching(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await api.uploadChatAttachment(fd);
      setAttachment({ name: res.data.filename, extracted_text: res.data.extracted_text, error: res.data.error });
    } catch {
      setAttachment({ name: file.name, extracted_text: '', error: 'No se pudo procesar el archivo.' });
    } finally {
      setAttaching(false);
    }
  }, []);

  useEffect(() => {
    // Por `state` cuando se navega desde dentro de la app, y por `?conversation=`
    // para que la conversación tenga una URL que se pueda enlazar y pegar. Sin lo
    // segundo, el link desde las conversaciones de un Espacio abría un chat vacío.
    const params = new URLSearchParams(location.search);
    const deLaUrl = parseInt(params.get('conversation'), 10);
    const cid = location.state?.conversationId || (Number.isFinite(deLaUrl) ? deLaUrl : null);
    if (cid && cid !== convId) {
      api.getConversationMessages(cid)
        .then(r => {
          saltoRef.current = true;   // un hilo que se abre aparece ya abajo, sin animar
          setMessages(r.data.messages || r.data || []);
          setConvId(cid);
        })
        .catch(() => {});
    }
  }, [location.state, location.search]);

  const scrollToBottom = useCallback((behavior = 'smooth') => messagesEndRef.current?.scrollIntoView({ behavior }), []);
  // Bajar suave es para los mensajes nuevos. Al volver al chat se queda donde estaba, y un hilo
  // recién abierto aparece ya abajo.
  const saltoRef = useRef(false);
  // Se baja solo cuando de verdad cambió la cantidad de mensajes: comparar con el largo anterior
  // (y no con una marca de "primera vez") aguanta que React corra los efectos dos veces.
  const largoPrevio = useRef(messages.length);
  useEffect(() => {
    if (messages.length === largoPrevio.current) return;
    largoPrevio.current = messages.length;
    if (saltoRef.current) {
      saltoRef.current = false;
      requestAnimationFrame(() => scrollToBottom('auto'));
      return;
    }
    scrollToBottom();
  }, [messages.length]); // eslint-disable-line react-hooks/exhaustive-deps

  useLayoutEffect(() => {
    if (restaurado.current && memoria.scrollTop != null && messagesBoxRef.current) {
      messagesBoxRef.current.scrollTop = memoria.scrollTop;
    }
  }, []);

  // El "+" estando ya en el chat: la página no se rearma, así que se empieza de cero aquí.
  const llegada = useRef(location.key);
  useEffect(() => {
    if (!location.state?.nueva || location.key === llegada.current) return;
    Object.assign(memoria, { convId: null, messages: [], scrollTop: null });
    setMessages([]);
    setConvId(null);
    setInput('');
  }, [location.key]); // eslint-disable-line react-hooks/exhaustive-deps

  // Lo que se está viendo queda guardado para la vuelta.
  useEffect(() => {
    memoria.messages = messages.filter((m) => !m.streaming);
    memoria.convId = convId;
  }, [messages, convId]);

  // Si se salió mientras Afable respondía, al volver se trae la respuesta terminada.
  useEffect(() => {
    if (!restaurado.current || !memoria.convId) return;
    api.getConversationMessages(memoria.convId)
      .then((r) => {
        const frescos = r.data.messages || r.data || [];
        if (frescos.length !== memoria.messages.length) setMessages(frescos);
      })
      .catch(() => {});
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleScroll = () => {
    const el = messagesBoxRef.current;
    if (!el) return;
    memoria.scrollTop = el.scrollTop;
    setShowScrollBtn(el.scrollHeight - el.scrollTop - el.clientHeight > 200);
  };

  const sendMessage = useCallback(async (text) => {
    const msg = (text || input).trim();
    if (!msg || loading) return;
    callar();
    setInput('');
    pedirPermisoDeAvisos();

    const pendingAttachment = attachment && !attachment.error ? attachment : null;
    setAttachment(null);

    const finalMessage = pendingAttachment
      ? `${msg}\n\n[[ARCHIVO_ADJUNTO:${pendingAttachment.name}]]\n${pendingAttachment.extracted_text}\n[[/ARCHIVO_ADJUNTO]]`
      : msg;

    const uid = Date.now();
    const aid = uid + 1;

    setMessages(prev => [
      ...prev,
      { role: 'user', content: finalMessage, id: uid },
      // `nuevo`: la respuesta de esta visita; sus tarjetas se animan (la factura, por ejemplo).
      { role: 'assistant', content: '', id: aid, streaming: true, nuevo: true },
    ]);
    setLoading(true);
    setShowThinking(true);
    setThinkStep(0);
    setLiveStatus(null);

    thinkIntervalRef.current = setInterval(() => {
      setThinkStep(s => Math.min(s + 1, TERMINAL_STEPS.length - 1));
    }, 1800);

    try {
      const token = Cookies.get('access_token');
      const res = await fetch(`${API_URL}/agents/direct-chat/stream/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          message: finalMessage,
          conversation_id: convId,
          model: aiModel || undefined,
          // El Espacio activo: la conversación nueva queda ahí, a la vista de
          // quienes pertenecen al Espacio. Sin Espacio, el hilo es personal.
          workspace: slug || undefined,
          space: espacioSlug || undefined,
          // La Sesion: el hilo queda colgado de ella y lo ve cualquiera que entre.
          sesion: sesionDelHilo.current || undefined,
        }),
      });

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let accumulated = '';
      let convActual = convId;   // la conversación de esta respuesta, para el aviso

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value);
        for (const line of chunk.split('\n')) {
          if (!line.startsWith('data: ')) continue;
          try {
            const data = JSON.parse(line.slice(6));
            if (data.conversation_id) convActual = data.conversation_id;
            if (data.conversation_id && data.conversation_id !== convId) {
              setConvId(data.conversation_id);
              // Recien creada: la barra tiene que reflejarla sin recargar. La
              // comparacion es para no avisar en cada trozo del stream.
              window.dispatchEvent(new Event('afable-conversaciones'));
            }
            if (data.acciones && !data.done) {
              // Lo que hizo en el ERP llega antes del texto: las tarjetas aparecen primero.
              clearInterval(thinkIntervalRef.current);
              setShowThinking(false);
              setLiveStatus(null);
              setMessages(prev => prev.map(m => m.id === aid ? { ...m, acciones: data.acciones } : m));
            }
            if (data.model) {
              setMessages(prev => prev.map(m => m.id === aid ? { ...m, model: data.model } : m));
            }
            if (data.status) {
              // Estado real del agente: deja de ciclar pasos genéricos y muestra el progreso real.
              clearInterval(thinkIntervalRef.current);
              setLiveStatus(data.status);
              setShowThinking(true);
              // Cada estado nuevo es un paso de la tarjeta de progreso.
              setMessages(prev => prev.map(m => {
                if (m.id !== aid) return m;
                const pasos = m.pasos || [];
                return pasos[pasos.length - 1] === data.status ? m : { ...m, pasos: [...pasos, data.status] };
              }));
            }
            if (data.chunk) {
              accumulated += data.chunk;
              clearInterval(thinkIntervalRef.current);
              setShowThinking(false);
              setLiveStatus(null);
              setMessages(prev => prev.map(m => m.id === aid ? { ...m, content: accumulated, streaming: true } : m));
            }
            if (data.done) {
              // Si el modelo respondió solo con la acción, muestra su mensaje
              // (mismo fallback que aplica el backend al guardar el historial).
              const fallback = !accumulated.trim() && data.action?.message ? data.action.message : null;
              // Se cambian los ids provisorios (Date.now()) por los de la base.
              // Sin esto, ramificar o corregir apuntan a un mensaje que no existe.
              setMessages(prev => prev.map(m => {
                if (m.id === aid) {
                  return {
                    ...m, ...(fallback ? { content: fallback } : {}), streaming: false,
                    ...(data.message_id ? { id: data.message_id } : {}),
                    // Lo que el agente dejó escrito, para que la tarjeta aparezca al
                    // terminar y no recién al recargar el hilo.
                    artefactos: data.artefactos || [],
                    // Y en qué se apoyó. El backend ya las mandaba y la pantalla las
                    // tiraba: la cita que se abre de un clic solo aparecía al recargar,
                    // o sea justo cuando ya nadie va a comprobar el dato.
                    fuentes: data.fuentes || [],
                    acciones: data.acciones || m.acciones || [],
                    pasos: data.pasos || m.pasos || [],
                  };
                }
                if (m.id === uid && data.user_message_id) {
                  return { ...m, id: data.user_message_id };
                }
                return m;
              }));
              if (responderEnVoz.current) {
                responderEnVoz.current = false;
                leerEnVoz(fallback || accumulated);
              }
              if (data.artefactos?.length) setRefrescoDoc((n) => n + 1);
              setRefrescoPanel((n) => n + 1);
              const conversacion = convActual;
              avisarRespuesta({
                notificacionId: data.notificacion_id, conversacionId: conversacion, detalle: accumulated,
                alAbrir: () => navigate(`/app/chat?conversation=${conversacion}`),
              });
              if (data.action?.type === 'navigate') navigate(data.action.path);
              if (data.action?.type === 'save_document' && data.action?.success) {
                setSavedDoc({ title: data.action.document_title });
              }
            }
          } catch { /* ignore */ }
        }
      }
    } catch {
      clearInterval(thinkIntervalRef.current);
      setShowThinking(false);
      setMessages(prev => prev.map(m => m.id === aid
        ? { ...m, content: 'Error al conectar con el servidor. Intenta de nuevo.', streaming: false } : m));
    } finally {
      clearInterval(thinkIntervalRef.current);
      setShowThinking(false);
      setLoading(false);
    }
  }, [input, convId, loading, navigate, aiModel, attachment, slug, espacioSlug]);

  /**
   * Vuelve a hacer la misma pregunta.
   *
   * Sirve cuando la respuesta se colgo, salio a medias o el modelo devolvio algo
   * inservible. Quita la ultima respuesta y reenvia el ultimo mensaje del usuario
   * tal cual, sin que tenga que volver a escribirlo.
   */
  const reintentar = useCallback(() => {
    if (loading) return;
    const ultimaPregunta = [...messages].reverse().find((m) => m.role === 'user');
    if (!ultimaPregunta) return;
    setMessages((previos) => {
      const corte = [...previos];
      while (corte.length && corte[corte.length - 1].role === 'assistant') corte.pop();
      while (corte.length && corte[corte.length - 1].role === 'user') corte.pop();
      return corte;
    });
    setTimeout(() => sendMessage(stripAttachment(ultimaPregunta.content)), 0);
  }, [messages, loading, sendMessage]);

  // Ramificar: el hilo original queda intacto y la rama arranca con todo el
  // contexto que habia hasta ese mensaje. Sirve para probar otro camino sin
  // perder el que ya funcionaba.
  const ramificar = useCallback(async (mensaje) => {
    if (!convId || loading) return;
    try {
      const { data } = await api.branchConversation(convId, mensaje.id);
      setConvId(data.id);
      setMessages(data.messages || []);
      toast.success('Rama nueva: siga por acá sin perder la conversación original.');
    } catch {
      toast.error('No se pudo ramificar la conversación.');
    }
  }, [convId, loading]);

  // Corregir la propia pregunta. Lo que venia despues se borra: respondia a la
  // version anterior. Quien quiera conservarlo, ramifica primero.
  const editar = useCallback(async (mensaje, texto) => {
    if (!convId || loading) return;
    const limpio = (texto || '').trim();
    if (!limpio) return;
    try {
      // El backend corta el hilo DESDE ese mensaje (inclusive) y devuelve el texto
      // corregido; la versión nueva se manda como mensaje nuevo. Si el editado
      // sobreviviera, la misma pregunta quedaría dos veces seguidas.
      await api.editMessage(convId, mensaje.id, limpio);
      setMessages((previos) => {
        const corte = previos.findIndex((m) => m.id === mensaje.id);
        return corte < 0 ? previos : previos.slice(0, corte);
      });
      setTimeout(() => sendMessage(limpio), 0);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'No se pudo corregir el mensaje.');
    }
  }, [convId, loading, sendMessage]);

  // Mensaje escrito en la home de Trabajo: se manda apenas se abre el chat, una
  // sola vez (se limpia el state para que recargar no lo repita).
  const mensajeInicialEnviado = useRef(false);
  useEffect(() => {
    const inicial = location.state?.initialMessage;
    const deSesion = location.state?.sesionSlug;
    if (deSesion) sesionDelHilo.current = deSesion;
    if (inicial && !mensajeInicialEnviado.current) {
      mensajeInicialEnviado.current = true;
      navigate(location.pathname, { replace: true, state: {} });
      sendMessage(inicial);
    }
  }, [location.state, location.pathname, navigate, sendMessage]);

  const handleInputChange = (e) => setInput(e.target.value);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  };

  // Dictado: lo que se va entendiendo aparece en el cuadro y, al dejar de hablar, se envía.
  const dictado = useDictado({
    alCambiar: (texto) => setInput(texto),
    alTerminar: (texto) => { responderEnVoz.current = true; sendMessage(texto); },
  });

  return (
    <Box sx={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', flex: 1, minWidth: 0, bgcolor: 'background.default', overflow: 'hidden' }}>

      {/* Messages / Welcome */}
      <Box ref={messagesBoxRef} onScroll={handleScroll}
        // minHeight:0 para que este bloque SÍ pueda encogerse: sin eso, cuando
        // el compositor se expande con la vitrina, en vez de ceder espacio
        // empuja el compositor fuera de la pantalla.
        sx={{ flex: 1, minHeight: 0, overflowY: 'auto', display: 'flex', flexDirection: 'column', position: 'relative' }}>
        {messages.length === 0 ? (
          <Bienvenida onPreguntar={sendMessage} />
        ) : (
          <Box sx={{ px: { xs: 2, sm: 3, md: 4 }, py: 3, maxWidth: 780, width: '100%', mx: 'auto' }}>
            {messages.map((msg, idx) => (
              // Cada mensaje nuevo entra subiendo un poco (components/Animado).
              <Entra key={msg.id || idx}>
              <MessageBubble
                msg={msg}
                yoId={currentUser?.id}
                navigate={navigate}
                onAbrirDoc={setDocAlLado}
                onReintentar={
                  msg.role === 'assistant' && idx === messages.length - 1 && !loading
                    ? reintentar
                    : undefined
                }
                onRamificar={
                  // Solo desde una respuesta ya guardada, y no desde la última:
                  // ahí ramificar no agregaría nada, es donde ya se está.
                  msg.role === 'assistant' && msg.id && !loading && idx < messages.length - 1
                    ? () => ramificar(msg)
                    : undefined
                }
                onEditar={
                  msg.role === 'user' && msg.id && !loading
                    ? (texto) => editar(msg, texto)
                    : undefined
                }
                // Confirmar o cancelar desde la tarjeta: solo en la última respuesta.
                onResponder={
                  msg.role === 'assistant' && idx === messages.length - 1 && !loading
                    ? (texto) => sendMessage(texto)
                    : undefined
                }
              />
              </Entra>
            ))}
            {showThinking && (
              messages[messages.length - 1]?.pasos?.length ? (
                // Con pasos reales: la tarjeta de progreso, desplegada mientras trabaja.
                <Entra sx={{ mb: 2.5, display: 'flex', gap: 1.5, alignItems: 'flex-start' }}>
                  <Box sx={{ width: 28, height: 28, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <IsotipoPensando girando={false} size={20} />
                  </Box>
                  <Box sx={{ flex: 1, minWidth: 0 }}>
                    <PasosDelChat pasos={messages[messages.length - 1].pasos} trabajando />
                  </Box>
                </Entra>
              ) : (
                <Entra sx={{ mb: 2.5, display: 'flex', gap: 1.5, alignItems: 'center' }}>
                  <IsotipoPensando size={22} />
                  <Typography sx={{ fontSize: '0.86rem', color: 'text.secondary' }}>
                    {liveStatus || TERMINAL_STEPS[Math.min(thinkStep, TERMINAL_STEPS.length - 1)]}
                  </Typography>
                </Entra>
              )
            )}
            <div ref={messagesEndRef} />
          </Box>
        )}
        {showScrollBtn && (
          <Box onClick={() => scrollToBottom()} sx={{ position: 'sticky', bottom: 16, display: 'flex', justifyContent: 'center' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5,
              bgcolor: d ? '#333' : '#fff', border: `1px solid ${theme.palette.divider}`,
              borderRadius: '20px', px: 1.5, py: 0.4, cursor: 'pointer',
              boxShadow: '0 4px 12px rgba(0,0,0,0.15)', '&:hover': { bgcolor: d ? '#3a3a3a' : '#f5f5f5' } }}>
              <ChevronDown size={14} color={theme.palette.text.secondary} />
              <Typography sx={{ fontSize: '0.72rem', color: 'text.secondary', ml: 0.5 }}>Bajar</Typography>
            </Box>
          </Box>
        )}
      </Box>

      {/* Input */}
      <Box sx={{ flexShrink: 0, px: { xs: 2, sm: 3, md: 4 }, pt: 1.5, pb: 2.5, maxWidth: 780, width: '100%', mx: 'auto' }}>
        <Box sx={{
          position: 'relative',
          border: `1.5px solid ${loading ? 'color-mix(in srgb, var(--af-acento) 40%, transparent)' : theme.palette.divider}`,
          borderRadius: '18px', bgcolor: d ? 'rgba(255,255,255,0.03)' : '#fff',
          transition: 'border-color 0.2s', '&:focus-within': { borderColor: 'color-mix(in srgb, var(--af-acento) 50%, transparent)' },
          boxShadow: d ? 'none' : '0 2px 12px rgba(0,0,0,0.06)',
        }}>
          {(attachment || attaching) && (
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75, px: 2, pt: 1.25 }}>
              {attaching && (
                <Chip size="small" icon={<CircularProgress size={11} sx={{ color: 'inherit' }} />}
                  label="Procesando archivo..." sx={{ fontSize: '0.72rem' }} />
              )}
              {attachment && (
                <Chip size="small" icon={<Paperclip size={12} />}
                  label={attachment.error ? `${attachment.name} — ${attachment.error}` : attachment.name}
                  color={attachment.error ? 'error' : 'default'}
                  onDelete={() => setAttachment(null)} deleteIcon={<X size={12} />}
                  sx={{ fontSize: '0.72rem' }} />
              )}
            </Box>
          )}
          <TextField inputRef={inputRef} multiline maxRows={6} fullWidth
            placeholder="Pídale algo a Afable…"
            value={input} onChange={handleInputChange}
            onKeyDown={handleKeyDown} disabled={loading}
            variant="standard" InputProps={{ disableUnderline: true }}
            sx={{ px: 2, pt: 1.5, pb: 0.5,
              '& textarea': { fontSize: '0.9rem', lineHeight: 1.65, color: theme.palette.text.primary,
                '&::placeholder': { color: theme.palette.text.disabled } } }} />
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', px: 1.5, pb: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
              <input ref={fileInputRef} type="file" hidden onChange={handleFileChange}
                accept=".pdf,.xml,.docx,.txt,.csv,.md,.xlsx,.xls,image/*" />
              <Tooltip title="Adjuntar archivo">
                <IconButton size="small" disabled={attaching} onClick={() => fileInputRef.current?.click()}
                  sx={{ color: 'text.disabled', '&:hover': { color: 'text.secondary' }, p: 0.5 }}>
                  <Paperclip size={15} />
                </IconButton>
              </Tooltip>
              {hayDictado && (
                <Tooltip title={dictado.escuchando ? 'Detener' : 'Hablar con Afable'}>
                  <span>
                    <IconButton size="small" disabled={loading}
                      onClick={dictado.escuchando ? dictado.detener : dictado.empezar}
                      aria-label={dictado.escuchando ? 'Detener el dictado' : 'Hablar con Afable'}
                      sx={dictado.escuchando
                        ? { color: '#b42318', bgcolor: 'rgba(180,35,24,0.08)', p: 0.5,
                          animation: 'afPulsoVoz 1.2s ease-in-out infinite',
                          '@keyframes afPulsoVoz': { '0%,100%': { boxShadow: '0 0 0 0 rgba(180,35,24,0.25)' }, '50%': { boxShadow: '0 0 0 5px rgba(180,35,24,0)' } } }
                        : { color: 'text.disabled', '&:hover': { color: 'text.secondary' }, p: 0.5 }}>
                      {dictado.escuchando ? <Square size={13} fill="currentColor" /> : <Mic size={15} />}
                    </IconButton>
                  </span>
                </Tooltip>
              )}
            </Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>

              <Tooltip title="Enviar (Enter)">
                <span>
                  <IconButton size="small" onClick={() => sendMessage()}
                    disabled={!input.trim() || loading}
                    sx={{ bgcolor: input.trim() && !loading ? 'var(--af-acento)' : 'action.disabledBackground',
                      color: input.trim() && !loading ? 'var(--af-sobre-acento)' : 'text.disabled',
                      borderRadius: '50%', width: 32, height: 32,
                      '&:hover': input.trim() && !loading ? { bgcolor: 'var(--af-acento-hover)' } : {},
                      '&.Mui-disabled': { bgcolor: 'action.disabledBackground' },
                      transition: 'all 0.15s' }}>
                    <ArrowUp size={16} />
                  </IconButton>
                </span>
              </Tooltip>
            </Box>
          </Box>

        </Box>
        <Typography sx={{ fontSize: '0.68rem', color: 'text.disabled', textAlign: 'center', mt: 1 }}>
          Afable responde con datos reales de sus sistemas. Compruebe con la fuente lo que sea crítico.
        </Typography>
      </Box>

    </Box>

    {/* Necesita acción y Caja, como en la animación de la landing. Cede el lugar al
        documento abierto: dos paneles dejarían la conversación en una franja. */}
    {!docAlLado && !focusMode && <PanelNecesitaAccion slug={slug} refresco={refrescoPanel} />}

    {/* El documento al lado de la conversación. Se abre desde la tarjeta del mensaje:
        revisar lo que el agente escribió no debería costar salir del chat. */}
    {docAlLado && (
      <DocumentoAlLado
        docId={docAlLado} workspace={slug} refresco={refrescoDoc}
        onCerrar={() => setDocAlLado(null)}
      />
    )}
    </Box>
  );
}
