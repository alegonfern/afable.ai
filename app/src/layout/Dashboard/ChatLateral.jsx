import { useEffect, useRef, useState } from 'react';
import Cookies from 'js-cookie';
import { useNavigate } from 'react-router-dom';
import { Box, Button, CircularProgress, IconButton, InputBase, Tooltip, Typography } from '@mui/material';
import { ArrowUp, Maximize2, Plus } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useWorkspace } from '../../context/WorkspaceContext';
import { usePanelLateral } from './panelContexto';
import { Entra, Escribiendo } from '../../components/Animado';
import TarjetasDelChat from '../../components/TarjetasDelChat';
import IsotipoPensando from '../../components/IsotipoPensando';
import PasosDelChat from '../../components/PasosDelChat';
import { avisarRespuesta, pedirPermisoDeAvisos } from '../../services/avisoRespuesta';

/*
 * El chat del panel lateral (18-10-2026). Es el mismo chat de Afable (el mismo endpoint y la
 * misma conversación, que se puede seguir en la página de Chat), con dos diferencias: cada
 * mensaje lleva la pantalla que el usuario tiene abierta, y el agente la usa para entender
 * "esto", "este mes" o "estos documentos"; y el hilo es el de su contexto (ver PanelLateral).
 */

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001/api/v1';
const CHAT_NUEVO = { convId: null, mensajes: [], cargado: true };

const SUGERENCIAS = {
  ventas: ['¿Qué órdenes de venta me faltan por facturar?', 'Cotízale 10 unidades de mi producto más vendido a mi cliente más grande'],
  compras: ['¿Qué órdenes de compra están atrasadas?', '¿Qué productos están bajo el stock mínimo?'],
  contabilidad: ['¿Cuánto IVA tengo que pagar este mes?', '¿En qué categoría gasté más este mes?'],
  finanzas: ['¿Cuánto puedo retirar sin quedar corto?', '¿Quién me debe y desde cuándo?'],
  general: ['¿Cómo va mi empresa este mes?', '¿Qué tengo que pagar esta semana?'],
};

function Mensaje({ m, onResponder }) {
  if (m.role === 'user') {
    return (
      <Box sx={{ alignSelf: 'flex-end', maxWidth: '85%', px: 1.5, py: 1, borderRadius: '12px', bgcolor: 'action.hover', fontSize: '0.88rem', whiteSpace: 'pre-wrap' }}>
        {m.content}
      </Box>
    );
  }
  return (
    <Box sx={{ fontSize: '0.88rem', lineHeight: 1.6, '& p': { my: 0.75 }, '& table': { borderCollapse: 'collapse', fontSize: '0.8rem', display: 'block', overflowX: 'auto' },
      '& td, & th': { border: '1px solid', borderColor: 'divider', px: 0.75, py: 0.25 }, '& ul, & ol': { pl: 2.5, my: 0.5 } }}>
      {/* Lo que hizo o consultó en el ERP, las mismas tarjetas del chat completo. */}
      {/* Los pasos: desplegados mientras trabaja, plegados al terminar (components/PasosDelChat). */}
      <PasosDelChat pasos={m.pasos} trabajando={!m.content && !m.acciones?.length && !m.listo} />
      <TarjetasDelChat acciones={m.acciones} onResponder={onResponder} animar={Boolean(m.nuevo)} />
      {m.content
        ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
        : (
          m.pasos?.length || m.acciones?.length || m.listo ? null : (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, color: 'text.secondary', fontSize: '0.82rem' }}>
              <IsotipoPensando size={18} /> {m.estado || 'Pensando…'}
            </Box>
          )
        )}
    </Box>
  );
}

export default function ChatLateral() {
  const navigate = useNavigate();
  const { slug } = useWorkspace();
  const { chat, setChatDe, contexto, pantalla, modulo } = usePanelLateral();
  const [texto, setTexto] = useState('');
  const [enviando, setEnviando] = useState(false);
  const fondo = useRef(null);

  useEffect(() => { fondo.current?.scrollIntoView({ block: 'end' }); }, [chat.mensajes]);

  const enviar = async (propio) => {
    const msg = (propio ?? texto).trim();
    if (!msg || enviando || !chat.cargado) return;
    // Lo que llegue se anota en el hilo donde se preguntó, aunque el usuario cambie de módulo.
    const clave = contexto;
    const setChat = (cambio) => setChatDe(clave, cambio);
    const cambiarUltimo = (cambios) => setChat((c) => ({
      ...c, mensajes: c.mensajes.map((m, i) => (i === c.mensajes.length - 1 ? { ...m, ...cambios } : m)),
    }));
    setTexto('');
    setEnviando(true);
    pedirPermisoDeAvisos();
    setChat((c) => ({ ...c, mensajes: [...c.mensajes, { role: 'user', content: msg }, { role: 'assistant', content: '', nuevo: true }] }));
    let acumulado = '';
    let convActual = chat.convId;   // la conversación de esta respuesta, para el aviso
    try {
      const res = await fetch(`${API_URL}/agents/direct-chat/stream/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${Cookies.get('access_token')}` },
        body: JSON.stringify({ message: msg, conversation_id: chat.convId, workspace: slug || undefined, pantalla, contexto: clave }),
      });
      const lector = res.body.getReader();
      const decoder = new TextDecoder();
      for (;;) {
        const { done, value } = await lector.read();
        if (done) break;
        for (const linea of decoder.decode(value).split('\n')) {
          if (!linea.startsWith('data: ')) continue;
          try {
            const d = JSON.parse(linea.slice(6));
            if (d.conversation_id) {
              convActual = d.conversation_id;
              setChat((c) => (c.convId === d.conversation_id ? c : { ...c, convId: d.conversation_id }));
              window.dispatchEvent(new Event('afable-conversaciones'));
            }
            if (d.status) {
              setChat((c) => ({
                ...c, mensajes: c.mensajes.map((m, i) => {
                  if (i !== c.mensajes.length - 1) return m;
                  const pasos = m.pasos || [];
                  return { ...m, estado: d.status, pasos: pasos[pasos.length - 1] === d.status ? pasos : [...pasos, d.status] };
                }),
              }));
            }
            if (d.acciones && !d.done) cambiarUltimo({ acciones: d.acciones });
            if (d.chunk) { acumulado += d.chunk; cambiarUltimo({ content: acumulado }); }
            if (d.done && !acumulado.trim() && d.action?.message) cambiarUltimo({ content: d.action.message });
            if (d.done) {
              cambiarUltimo({ listo: true, ...(d.pasos ? { pasos: d.pasos } : {}) });
              const conv = convActual;
              avisarRespuesta({ notificacionId: d.notificacion_id, conversacionId: conv, detalle: acumulado,
                alAbrir: conv ? () => navigate('/app/chat', { state: { conversationId: conv } }) : undefined });
            }
          } catch { /* trozo incompleto */ }
        }
      }
    } catch {
      cambiarUltimo({ content: 'No se pudo conectar con el servidor. Intente de nuevo.' });
    } finally {
      setEnviando(false);
    }
  };

  const vacio = chat.mensajes.length === 0;
  return (
    <Box sx={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
      <Box sx={{ display: 'flex', gap: 0.5, px: 1.5, pt: 1 }}>
        <Button size="small" startIcon={<Plus size={13} />} disabled={vacio || enviando}
          onClick={() => setChatDe(contexto, CHAT_NUEVO)}>Nueva conversación</Button>
        <Box sx={{ flex: 1 }} />
        {chat.convId && (
          <Tooltip title="Seguir en el chat completo" arrow>
            <IconButton size="small" onClick={() => navigate('/app/chat', { state: { conversationId: chat.convId } })}><Maximize2 size={14} /></IconButton>
          </Tooltip>
        )}
      </Box>
      <Box sx={{ flex: 1, overflow: 'auto', px: 2, py: 1.5, display: 'flex', flexDirection: 'column', gap: 1.5 }}>
        {!chat.cargado ? (
          <Box sx={{ m: 'auto' }}><CircularProgress size={18} /></Box>
        ) : vacio ? (
          <Box sx={{ m: 'auto', textAlign: 'center', px: 1 }}>
            <Typography sx={{ fontSize: '0.88rem', color: 'text.secondary', mb: 1.5 }}>
              {modulo
                ? `Soy el ${modulo.agente}. Conozco esta pantalla y los datos de ${modulo.label.toLowerCase()}: pídame lo que necesite.`
                : 'Pregúntele a Afable lo que necesite sobre su empresa.'}
            </Typography>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.75 }}>
              {(SUGERENCIAS[modulo?.slug || 'general'] || []).map((s) => (
                <Button key={s} size="small" variant="outlined" onClick={() => enviar(s)}
                  sx={{ textTransform: 'none', justifyContent: 'flex-start', textAlign: 'left', fontSize: '0.82rem' }}>{s}</Button>
              ))}
            </Box>
          </Box>
        ) : chat.mensajes.map((m, i) => (
          // Cada mensaje nuevo entra subiendo un poco; los ya mostrados no se vuelven a animar.
          <Entra key={i} sx={{ display: 'flex', flexDirection: 'column' }}>
            <Mensaje m={m} onResponder={i === chat.mensajes.length - 1 && !enviando ? enviar : undefined} />
          </Entra>
        ))}
        <div ref={fondo} />
      </Box>
      <Box sx={{ p: 1.5, borderTop: '1px solid', borderColor: 'divider' }}>
        <Box sx={{ display: 'flex', alignItems: 'flex-end', gap: 1, border: '1px solid', borderColor: 'divider', borderRadius: '12px', px: 1.25, py: 0.75 }}>
          <InputBase multiline maxRows={6} fullWidth autoFocus placeholder={modulo ? `Pídale algo al ${modulo.agente}…` : 'Pregúntele a Afable…'} value={texto}
            onChange={(e) => setTexto(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); enviar(); } }}
            sx={{ fontSize: '0.88rem' }} />
          <IconButton size="small" onClick={() => enviar()} disabled={!texto.trim() || enviando} aria-label="Enviar"
            sx={{ bgcolor: 'var(--af-acento)', color: 'var(--af-sobre-acento)', '&:hover': { bgcolor: 'var(--af-acento-hover)' }, '&.Mui-disabled': { bgcolor: 'action.disabledBackground' } }}>
            {enviando ? <CircularProgress size={14} sx={{ color: 'inherit' }} /> : <ArrowUp size={15} />}
          </IconButton>
        </Box>
      </Box>
    </Box>
  );
}
