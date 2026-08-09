import { useState, useRef, useEffect, useCallback } from 'react';
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
  ArrowUpRight, X, Plug, GitBranch, Pencil,
} from 'lucide-react';
import { useNavigate, useLocation, useOutletContext } from 'react-router-dom';
import { toast } from 'react-toastify';
import { AfableMark } from '../components/Logo';
import { api } from '../services/api';
import AgentesGaleria from './trabajo/AgentesGaleria';
import SelectorAgente from './trabajo/SelectorAgente';
import MencionAgentes, { aplicarMencion, detectarMencion, filtrarAgentes }
  from '../components/MencionAgentes';
import { useApp } from '../context/AppContext';
import { useWorkspace } from '../context/WorkspaceContext';
import { DocumentoAlLado, TarjetaDeArtefacto } from '../components/DocumentoDelChat';
import ReactMarkdown, { defaultUrlTransform } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import Cookies2 from 'js-cookie';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001/api/v1';

const CONNECTOR_ICONS = { odoo: '🟢', mssql: '🔷', postgresql: '🐘', csv: '📄' };


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
      '& th': { bgcolor: d ? 'rgba(88, 106, 208,0.1)' : 'rgba(88, 106, 208,0.06)',
        px: 1.5, py: 0.875, textAlign: 'left', fontWeight: 600, fontSize: '0.78rem',
        borderBottom: `1px solid ${theme.palette.divider}`, color: d ? '#9BA6E3' : '#586AD0' },
      '& td': { px: 1.5, py: 0.75, borderBottom: `1px solid ${theme.palette.divider}` },
      '& tr:last-child td': { borderBottom: 'none' },
      '& tr:hover td': { bgcolor: d ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.02)' },
      '& blockquote': { borderLeft: '3px solid #586AD0', pl: 1.5, ml: 0, color: theme.palette.text.secondary, fontStyle: 'italic' },
      '& strong': { fontWeight: 600, color: theme.palette.text.primary },
      '& a': { color: '#586AD0', textDecoration: 'none', '&:hover': { textDecoration: 'underline' } },
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
      bgcolor: d ? 'rgba(88, 106, 208,0.06)' : 'rgba(88, 106, 208,0.04)',
      border: '1px solid rgba(88, 106, 208,0.15)', borderRadius: '10px', width: 'fit-content', maxWidth: 400 }}>
      <CircularProgress size={12} thickness={5} sx={{ color: '#586AD0' }} />
      <Typography sx={{ fontSize: '0.78rem', color: '#9BA6E3', fontFamily: '"JetBrains Mono","Fira Code",monospace' }}>
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
              fontSize: '0.7rem', color: '#9BA6E3',
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
function MessageBubble({ msg, onReintentar, onRamificar, onEditar, yoId, navigate, onAbrirDoc }) {
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
              sx={{ color: 'text.disabled', '&:hover': { color: '#9BA6E3' }, p: 0.4 }}
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
          <Typography sx={{ fontSize: '0.72rem', fontWeight: 600, color: '#9BA6E3', mb: 0.4, textAlign: 'right' }}>
            {msg.autor.nombre}
          </Typography>
        )}
        <Box sx={{ bgcolor: esMio ? '#586AD0' : (d ? '#33365e' : '#c7cdf0'),
          color: esMio ? '#fff' : (d ? '#e8e8ea' : '#1a1a1a'),
          px: 2, py: 1.25, borderRadius: '14px 14px 4px 14px', fontSize: '0.88rem', lineHeight: 1.65 }}>
          {stripAttachment(msg.content)}
          <AttachmentBadge content={msg.content} />
        </Box>
      </Box>
      <Avatar sx={{ width: 28, height: 28, bgcolor: d ? '#2a2a2a' : '#e5e5e5', flexShrink: 0, mt: 0.25 }}>
        <User size={14} color={d ? '#aaa' : '#666'} />
      </Avatar>
    </Box>
  );

  return (
    <Box sx={{ display: 'flex', gap: 1.5, mb: 2.5, alignItems: 'flex-start' }}>
      <Box sx={{ width: 28, height: 28, borderRadius: '8px', flexShrink: 0, mt: 0.25,
        background: 'linear-gradient(135deg, #586AD0 0%, #2F42A6 100%)',
        display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <AfableMark size={14} color="#fff" />
      </Box>
      <Box sx={{ flex: 1, minWidth: 0 }}>
        {/* Quien contesto ESTE mensaje. En un hilo pueden haber contestado
            varios agentes, y sin la firma todas las respuestas parecen del
            ultimo que quedo seleccionado. */}
        {(msg.agent_name || msg.agent_handle) && (
          <Typography sx={{ fontSize: '0.72rem', fontWeight: 600, color: '#9BA6E3', mb: 0.4 }}>
            {msg.agent_handle ? `@${msg.agent_handle}` : msg.agent_name}
          </Typography>
        )}
        <Box sx={{ bgcolor: d ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.02)',
          border: `1px solid ${theme.palette.divider}`,
          borderRadius: '4px 14px 14px 14px', px: 2, py: 1.5,
          fontSize: '0.88rem', color: theme.palette.text.primary }}>
          {msg.streaming ? (
            <Box sx={{ display: 'flex', alignItems: 'flex-start' }}>
              <Typography sx={{ fontSize: '0.88rem', color: 'text.primary', lineHeight: 1.7 }}>
                {cleanContent || ''}
              </Typography>
              <Box sx={{ display: 'flex', gap: '3px', alignItems: 'center', ml: 0.5, mt: 0.5, flexShrink: 0 }}>
                {[0,1,2].map(i => (
                  <Box key={i} sx={{ width: 4, height: 4, borderRadius: '50%', bgcolor: '#586AD0',
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
        {!msg.streaming && (
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mt: 0.5 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <SourceBadge content={msg.content || ''} fuentes={msg.fuentes} navigate={navigate} />
              <ModelBadge model={msg.model || msg.model_used} />
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
                    sx={{ color: 'text.disabled', '&:hover': { color: '#9BA6E3' }, p: 0.4 }}>
                    <RefreshCw size={11} />
                  </IconButton>
                </Tooltip>
              )}
              {onRamificar && (
                <Tooltip title="Seguir por otro camino desde acá, sin perder este" placement="top">
                  <IconButton size="small" onClick={onRamificar}
                    sx={{ color: 'text.disabled', '&:hover': { color: '#9BA6E3' }, p: 0.4 }}>
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

// ── KPI Card ──────────────────────────────────────────────────────────────────
function KpiCard({ conn }) {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const icon = CONNECTOR_ICONS[conn.connector_type] || '🔌';
  const isError = conn.status === 'error';

  return (
    <Box sx={{
      p: 2, borderRadius: '10px',
      bgcolor: d ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.02)',
      border: `1px solid ${isError ? 'rgba(239,68,68,0.2)' : theme.palette.divider}`,
      borderLeft: `3px solid ${isError ? '#f87171' : '#34D399'}`,
      minWidth: 200, flex: 1,
    }}>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1.5 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
          <Typography sx={{ fontSize: '1rem', lineHeight: 1 }}>{icon}</Typography>
          <Typography sx={{ fontSize: '0.78rem', fontWeight: 600, color: 'text.primary' }}>
            {conn.name}
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          {!isError && <Box sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: '#34D399' }} />}
          {isError && <AlertCircle size={12} color="#f87171" />}
          <Typography sx={{ fontSize: '0.65rem', color: 'text.disabled' }}>
            {conn.last_updated}
          </Typography>
        </Box>
      </Box>

      {isError ? (
        <Typography sx={{ fontSize: '0.75rem', color: '#f87171' }}>
          Error de conexión
        </Typography>
      ) : conn.kpis.length === 0 ? (
        <Typography sx={{ fontSize: '0.75rem', color: 'text.disabled' }}>
          Sin datos — sincroniza el sistema
        </Typography>
      ) : (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.75 }}>
          {conn.kpis.map((kpi, i) => (
            <Box key={i} sx={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 1 }}>
              <Typography sx={{ fontSize: '0.72rem', color: 'text.disabled', flexShrink: 0 }}>
                {kpi.label}
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                {kpi.alert && <AlertCircle size={11} color="#fbbf24" />}
                <Typography sx={{ fontSize: '0.82rem', fontWeight: 600,
                  color: kpi.alert ? '#fbbf24' : 'text.primary', fontVariantNumeric: 'tabular-nums' }}>
                  {kpi.value}
                </Typography>
                {kpi.trend && (
                  <Typography sx={{ fontSize: '0.68rem', color: '#34D399' }}>{kpi.trend}</Typography>
                )}
              </Box>
            </Box>
          ))}
        </Box>
      )}
    </Box>
  );
}

// ── Welcome / Dashboard ───────────────────────────────────────────────────────
function WelcomeScreen() {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const navigate = useNavigate();
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getDashboard()
      .then(r => setDashboard(r.data))
      .catch(() => setDashboard({ connections: [] }))
      .finally(() => setLoading(false));
  }, []);

  const hasConnections = dashboard?.connections?.length > 0;

  return (
    // Sin scroll propio: esta pantalla vive DENTRO de la caja de mensajes, que ya
    // scrollea. Con `overflowY: auto` acá quedaban dos contenedores con scroll uno
    // dentro del otro y, con la galería de agentes larga, dos barras a la vez.
    // `1 0 auto` para que no se encoja: crece con las tarjetas y scrollea el padre.
    <Box sx={{ flex: '1 0 auto', px: { xs: 2, sm: 3, md: 4 }, py: 3, maxWidth: 820, mx: 'auto', width: '100%' }}>

      {/* Header */}
      <Box sx={{ mb: 3 }}>
        <Typography sx={{ fontSize: '1.35rem', fontWeight: 700, color: 'text.primary', letterSpacing: '-0.3px', mb: 0.4 }}>
          {dashboard?.org_name ? `${dashboard.org_name}` : '¿En qué puedo ayudarte?'}
        </Typography>
        <Typography sx={{ fontSize: '0.83rem', color: 'text.disabled' }}>
          {hasConnections
            ? `${dashboard.connections.length} sistema${dashboard.connections.length > 1 ? 's' : ''} conectado${dashboard.connections.length > 1 ? 's' : ''} · datos en tiempo real`
            : 'Conecta tu ERP o base de datos para ver datos en tiempo real'}
        </Typography>
      </Box>

      {/* KPI Panel — la diferencia real vs ChatGPT */}
      {loading ? (
        <Box sx={{ display: 'flex', gap: 1.5, mb: 3, flexWrap: 'wrap' }}>
          {[1,2].map(i => (
            <Box key={i} sx={{ flex: 1, minWidth: 200, p: 2, borderRadius: '10px', border: `1px solid ${theme.palette.divider}` }}>
              <Skeleton variant="text" width="60%" height={16} sx={{ mb: 1.5 }} />
              <Skeleton variant="text" width="40%" height={24} />
              <Skeleton variant="text" width="70%" height={14} sx={{ mt: 0.75 }} />
            </Box>
          ))}
        </Box>
      ) : hasConnections ? (
        <Box sx={{ display: 'flex', gap: 1.5, mb: 3, flexWrap: 'wrap' }}>
          {dashboard.connections.map(conn => (
            <KpiCard key={conn.connection_id} conn={conn} />
          ))}
        </Box>
      ) : (
        <Box sx={{ mb: 3, p: 2.5, borderRadius: '10px',
          bgcolor: d ? 'rgba(88, 106, 208,0.05)' : 'rgba(88, 106, 208,0.03)',
          border: '1px dashed rgba(88, 106, 208,0.25)',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 2 }}>
          <Box>
            <Typography sx={{ fontSize: '0.85rem', fontWeight: 600, color: 'text.primary', mb: 0.25 }}>
              Sin sistemas conectados
            </Typography>
            <Typography sx={{ fontSize: '0.78rem', color: 'text.disabled' }}>
              Conecta Odoo, SAP u otra base de datos para ver KPIs en tiempo real aquí.
            </Typography>
          </Box>
          <Box onClick={() => navigate('/app/contexto?tab=integraciones')} sx={{
            display: 'flex', alignItems: 'center', gap: 0.5, cursor: 'pointer',
            color: '#9BA6E3', fontSize: '0.78rem', fontWeight: 500, flexShrink: 0,
            '&:hover': { color: '#586AD0' },
          }}>
            Conectar <ArrowUpRight size={13} />
          </Box>
        </Box>
      )}

      {/* Los agentes, en cualquier chat: es la misma galeria de la home de Trabajo.
          Abrir un chat nuevo y poder elegir con quien hablar es parte de la vista. */}
      <AgentesGaleria />
    </Box>
  );
}

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
  // La Sesion desde la que se abrio el hilo, si vino de una.
  //
  // Es una REFERENCIA y no estado a proposito: el mensaje inicial se manda en el mismo
  // tick en que llega la Sesion, y `setState` no se aplica hasta el dibujado siguiente
  // — con estado, el primer mensaje salia sin Sesion y la conversacion quedaba
  // personal. Una ref se lee al instante.
  const sesionDelHilo = useRef(null);

  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [convId, setConvId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [thinkStep, setThinkStep] = useState(0);
  const [liveStatus, setLiveStatus] = useState(null);
  const [showThinking, setShowThinking] = useState(false);
  const [showScrollBtn, setShowScrollBtn] = useState(false);
  const [activeAgent, setActiveAgent] = useState(null);   // {id, name} si se entra desde un agente
  const [galeriaAbierta, setGaleriaAbierta] = useState(false); // vitrina desplegada en el compositor
  // Mencionar un agente con @: la lista de la empresa y lo que se esta tipeando.
  const [agentesMencionables, setAgentesMencionables] = useState([]);
  const [mencion, setMencion] = useState(null);      // { consulta, desde } o null
  const [mencionIdx, setMencionIdx] = useState(0);

  const [attachment, setAttachment] = useState(null);     // {name, extracted_text, error}
  const [attaching, setAttaching] = useState(false);
  const [systems, setSystems] = useState(null);           // null = aún no cargados
  const [mentionAnchorEl, setMentionAnchorEl] = useState(null);
  const [mentionedSystem, setMentionedSystem] = useState(null); // {id, name, connector_type}

  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
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

  const openMention = useCallback((e) => {
    setMentionAnchorEl(e.currentTarget);
    if (systems === null) {
      api.getConnections().then(r => setSystems(r.data || [])).catch(() => setSystems([]));
    }
  }, [systems]);

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
          setMessages(r.data.messages || r.data || []);
          setConvId(cid);
          // El agente lo manda la conversación: si no se sincroniza acá, queda
          // el de la conversación anterior y al escribir se le cambiaría el
          // agente a este hilo sin que nadie lo pidiera.
          setActiveAgent(r.data.agent ? { id: r.data.agent, name: r.data.agent_name } : null);
          setTimeout(scrollToBottom, 100);
        })
        .catch(() => {});
    }
    // Entrada desde "Chatear" en un agente: reabre SU conversación (única por
    // agente), no una en blanco — así el historial queda diferenciado y
    // persiste entre visitas al mismo agente.
    if (location.state?.agentId && !cid) {
      const { agentId, agentName } = location.state;
      setActiveAgent({ id: agentId, name: agentName });
      api.getAgentConversations(agentId)
        .then(r => {
          const existing = (r.data || [])[0]; // ordenado por -updated_at
          if (existing) {
            return api.getConversationMessages(existing.id).then(m => {
              setMessages(m.data.messages || m.data || []);
              setConvId(existing.id);
              setTimeout(scrollToBottom, 100);
            });
          }
          setMessages([]);
          setConvId(null);
        })
        .catch(() => { setMessages([]); setConvId(null); });
    }
  }, [location.state, location.search]);

  const scrollToBottom = useCallback(() => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }), []);
  useEffect(() => { scrollToBottom(); }, [messages.length]);

  const handleScroll = () => {
    const el = messagesBoxRef.current;
    if (!el) return;
    setShowScrollBtn(el.scrollHeight - el.scrollTop - el.clientHeight > 200);
  };

  const sendMessage = useCallback(async (text) => {
    const msg = (text || input).trim();
    if (!msg || loading) return;
    setInput('');

    const pendingAttachment = attachment && !attachment.error ? attachment : null;
    const pendingSystemId = mentionedSystem?.id;
    setAttachment(null);
    setMentionedSystem(null);

    const finalMessage = pendingAttachment
      ? `${msg}\n\n[[ARCHIVO_ADJUNTO:${pendingAttachment.name}]]\n${pendingAttachment.extracted_text}\n[[/ARCHIVO_ADJUNTO]]`
      : msg;

    const uid = Date.now();
    const aid = uid + 1;

    setMessages(prev => [
      ...prev,
      { role: 'user', content: finalMessage, id: uid },
      { role: 'assistant', content: '', id: aid, streaming: true },
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
          system_id: pendingSystemId || undefined,
          // Va siempre: al iniciar define el agente del hilo, y en un hilo abierto
          // permite conmutar de agente sin perder la conversación.
          agent_id: activeAgent?.id || undefined,
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

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value);
        for (const line of chunk.split('\n')) {
          if (!line.startsWith('data: ')) continue;
          try {
            const data = JSON.parse(line.slice(6));
            if (data.conversation_id) setConvId(data.conversation_id);
            if (data.agent) {
              // Si el usuario menciono a otro agente, el backend ya decidio: la
              // barra y la firma del mensaje tienen que reflejar a QUIEN contesta.
              setActiveAgent({ id: data.agent.id, name: data.agent.name });
              setMessages(prev => prev.map(m => m.id === aid
                ? { ...m, agent_name: data.agent.name, agent_handle: data.agent.handle }
                : m));
            }
            if (data.model) {
              setMessages(prev => prev.map(m => m.id === aid ? { ...m, model: data.model } : m));
            }
            if (data.status) {
              // Estado real del agente: deja de ciclar pasos genéricos y muestra el progreso real.
              clearInterval(thinkIntervalRef.current);
              setLiveStatus(data.status);
              setShowThinking(true);
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
                  };
                }
                if (m.id === uid && data.user_message_id) {
                  return { ...m, id: data.user_message_id };
                }
                return m;
              }));
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
  }, [input, convId, loading, navigate, aiModel, activeAgent, attachment, mentionedSystem]);

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

  // Los agentes de la empresa, para el autocompletado de `@`. Se piden una vez:
  // la lista cambia poco y no vale la pena volver a consultarla por cada tecla.
  useEffect(() => {
    let vivo = true;
    api.getAgents()
      .then(({ data }) => { if (vivo) setAgentesMencionables(Array.isArray(data) ? data : []); })
      .catch(() => {});
    return () => { vivo = false; };
  }, []);

  const sugerencias = mencion ? filtrarAgentes(agentesMencionables, mencion.consulta) : [];

  const handleInputChange = (e) => {
    const texto = e.target.value;
    setInput(texto);
    const detectada = detectarMencion(texto, e.target.selectionStart ?? texto.length);
    setMencion(detectada);
    setMencionIdx(0);
  };

  const elegirMencion = (agente) => {
    const { texto, cursor } = aplicarMencion(input, mencion, agente.handle);
    setInput(texto);
    setMencion(null);
    // El agente mencionado pasa a ser el del hilo, para que la barra de arriba
    // no siga diciendo que se habla con otro.
    setActiveAgent({ id: agente.id, name: agente.name });
    requestAnimationFrame(() => {
      inputRef.current?.focus();
      inputRef.current?.setSelectionRange?.(cursor, cursor);
    });
  };

  const handleKeyDown = (e) => {
    // Con la lista de menciones abierta, el teclado es de la lista: Enter elige
    // un agente en vez de mandar el mensaje a medio escribir.
    if (mencion && sugerencias.length) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setMencionIdx((i) => (i + 1) % sugerencias.length);
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setMencionIdx((i) => (i - 1 + sugerencias.length) % sugerencias.length);
        return;
      }
      if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        elegirMencion(sugerencias[mencionIdx]);
        return;
      }
      if (e.key === 'Escape') { e.preventDefault(); setMencion(null); return; }
    }
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  };

  return (
    <Box sx={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', flex: 1, minWidth: 0, bgcolor: 'background.default', overflow: 'hidden' }}>

      {activeAgent && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, px: 3, py: 1,
          borderBottom: '1px solid', borderColor: 'divider', bgcolor: 'rgba(88, 106, 208,0.05)' }}>
          <AfableMark size={14} color="#9BA6E3" />
          <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary' }}>
            Hablando con el agente <strong style={{ color: '#9BA6E3' }}>{activeAgent.name}</strong>
          </Typography>
        </Box>
      )}

      {/* Messages / Welcome */}
      <Box ref={messagesBoxRef} onScroll={handleScroll}
        // minHeight:0 para que este bloque SÍ pueda encogerse: sin eso, cuando
        // el compositor se expande con la vitrina, en vez de ceder espacio
        // empuja el compositor fuera de la pantalla.
        sx={{ flex: 1, minHeight: 0, overflowY: 'auto', display: 'flex', flexDirection: 'column', position: 'relative' }}>
        {messages.length === 0 ? (
          <WelcomeScreen />
        ) : (
          <Box sx={{ px: { xs: 2, sm: 3, md: 4 }, py: 3, maxWidth: 780, width: '100%', mx: 'auto' }}>
            {messages.map((msg, idx) => (
              <MessageBubble
                key={msg.id || idx}
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
              />
            ))}
            {showThinking && (
              <Box sx={{ mb: 2.5, display: 'flex', gap: 1.5, alignItems: 'flex-start' }}>
                <Box sx={{ width: 28, height: 28, borderRadius: '8px', flexShrink: 0,
                  background: 'linear-gradient(135deg, #586AD0 0%, #2F42A6 100%)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <AfableMark size={14} color="#fff" />
                </Box>
                <ThinkingLoader step={thinkStep} label={liveStatus} />
              </Box>
            )}
            <div ref={messagesEndRef} />
          </Box>
        )}
        {showScrollBtn && (
          <Box onClick={scrollToBottom} sx={{ position: 'sticky', bottom: 16, display: 'flex', justifyContent: 'center' }}>
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
          border: `1.5px solid ${loading ? 'rgba(88, 106, 208,0.4)' : theme.palette.divider}`,
          borderRadius: '14px', bgcolor: d ? 'rgba(255,255,255,0.03)' : '#fff',
          transition: 'border-color 0.2s', '&:focus-within': { borderColor: 'rgba(88, 106, 208,0.5)' },
          boxShadow: d ? 'none' : '0 2px 12px rgba(0,0,0,0.06)',
        }}>
          {mencion && (
            <MencionAgentes
              agentes={sugerencias} indice={mencionIdx} onElegir={elegirMencion}
            />
          )}
          {(attachment || attaching || mentionedSystem) && (
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
              {mentionedSystem && (
                <Chip size="small" icon={<AtSign size={12} />} label={mentionedSystem.name}
                  onDelete={() => setMentionedSystem(null)} deleteIcon={<X size={12} />}
                  sx={{ fontSize: '0.72rem', bgcolor: 'rgba(88, 106, 208,0.12)', color: '#586AD0' }} />
              )}
            </Box>
          )}
          <TextField inputRef={inputRef} multiline maxRows={6} fullWidth
            placeholder="Escribe un mensaje... (Enter para enviar)"
            value={input} onChange={handleInputChange}
            onKeyDown={handleKeyDown} disabled={loading}
            variant="standard" InputProps={{ disableUnderline: true }}
            sx={{ px: 2, pt: 1.5, pb: 0.5,
              '& textarea': { fontSize: '0.9rem', lineHeight: 1.65, color: theme.palette.text.primary,
                '&::placeholder': { color: theme.palette.text.disabled } } }} />
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', px: 1.5, pb: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
              {/* Con quien se esta hablando, en cualquier conversacion. Es lo que
                  distingue esto de un chat generico: el agente siempre a la vista
                  y siempre cambiable. */}
              <SelectorAgente
                agenteActivo={activeAgent}
                abierto={galeriaAbierta}
                onToggle={() => setGaleriaAbierta(v => !v)}
              />
              {/* En que Espacio se esta trabajando: acota los agentes que se
                  ofrecen y donde queda guardada la conversacion. */}
              <Box sx={{ width: '1px', height: 16, bgcolor: 'divider', mx: 0.25 }} />
              <input ref={fileInputRef} type="file" hidden onChange={handleFileChange}
                accept=".pdf,.docx,.txt,.csv,.md,.xlsx,.xls,image/*" />
              <Tooltip title="Adjuntar archivo">
                <IconButton size="small" disabled={attaching} onClick={() => fileInputRef.current?.click()}
                  sx={{ color: 'text.disabled', '&:hover': { color: 'text.secondary' }, p: 0.5 }}>
                  <Paperclip size={15} />
                </IconButton>
              </Tooltip>
              <Tooltip title="Mencionar sistema">
                <IconButton size="small" onClick={openMention}
                  sx={{ color: 'text.disabled', '&:hover': { color: 'text.secondary' }, p: 0.5 }}>
                  <AtSign size={15} />
                </IconButton>
              </Tooltip>
              <Menu anchorEl={mentionAnchorEl} open={!!mentionAnchorEl} onClose={() => setMentionAnchorEl(null)}>
                {systems === null && <MenuItem disabled>Cargando sistemas...</MenuItem>}
                {systems && systems.length === 0 && <MenuItem disabled>No hay sistemas conectados</MenuItem>}
                {systems && systems.map(s => (
                  <MenuItem key={s.id} onClick={() => { setMentionedSystem(s); setMentionAnchorEl(null); }}>
                    <Plug size={13} style={{ marginRight: 8 }} /> {s.name}
                  </MenuItem>
                ))}
              </Menu>
            </Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              {loading && <Typography sx={{ fontSize: '0.72rem', color: '#9BA6E3' }}>Analizando datos...</Typography>}
              <Tooltip title="Enviar (Enter)">
                <span>
                  <IconButton size="small" onClick={() => sendMessage()}
                    disabled={!input.trim() || loading}
                    sx={{ bgcolor: input.trim() && !loading ? '#586AD0' : 'transparent',
                      color: input.trim() && !loading ? '#fff' : 'text.disabled',
                      border: `1px solid ${input.trim() && !loading ? '#586AD0' : theme.palette.divider}`,
                      borderRadius: '8px', p: 0.6,
                      '&:hover': input.trim() && !loading ? { bgcolor: '#2F42A6' } : {},
                      transition: 'all 0.15s' }}>
                    <Send size={14} />
                  </IconButton>
                </span>
              </Tooltip>
            </Box>
          </Box>

          {/* La vitrina de Agentes se despliega DENTRO del compositor, bajo la
              fila del selector: la caja de escribir crece y muestra las
              tarjetas. No es un panel flotante encima de la pantalla. */}
          <Collapse in={galeriaAbierta} timeout={220} unmountOnExit>
            <Box sx={{
              borderTop: `1px solid ${theme.palette.divider}`,
              px: 2, pt: 1.75, pb: 2,
              maxHeight: 340, overflowY: 'auto',
            }}>
              <AgentesGaleria
                embebida
                filtrarPorEspacio
                onElegir={(a) => { setActiveAgent(a); setGaleriaAbierta(false); }}
              />
            </Box>
          </Collapse>
        </Box>
        <Typography sx={{ fontSize: '0.68rem', color: 'text.disabled', textAlign: 'center', mt: 1 }}>
          Afable responde con datos reales de tus sistemas. Verifica información crítica con las fuentes.
        </Typography>
      </Box>

    </Box>

    {/* El documento al lado de la conversación. Se abre desde la tarjeta del mensaje:
        revisar lo que el agente escribió no debería costar salir del chat. */}
    {docAlLado && (
      <DocumentoAlLado
        docId={docAlLado} workspace={slug} onCerrar={() => setDocAlLado(null)}
      />
    )}
    </Box>
  );
}
