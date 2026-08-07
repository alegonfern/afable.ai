import { useEffect, useRef, useState } from 'react';
import { Box, CircularProgress, IconButton, Stack, Typography, useTheme } from '@mui/material';
import { SendHorizontal } from 'lucide-react';
import { api } from '../../services/api';
import { AfableMark } from '../../components/Logo';
import { useApp } from '../../context/AppContext';

/**
 * Un hilo de la Sesion, abierto ahi mismo y con su campo para responder.
 *
 * Antes el feed listaba los hilos y al abrir uno **se salia al chat**: seguir una
 * conversacion costaba cambiar de pantalla y perder de vista todo lo demas que estaba
 * pasando en la Sesion. Con esto la Sesion deja de ser un muro de hilos sueltos y pasa a
 * ser una conversacion del equipo.
 *
 * ⭐ **El agente contesta solo si lo mencionan.** En un hilo donde hay mas de una persona,
 * un asistente que responde cada mensaje interrumpe la conversacion entre humanos — es lo
 * que termina con los bots apagados. El backend decide lo mismo
 * (`le_hablan_a_la_ia`); aca solo se avisa, para que nadie escriba esperando respuesta y
 * se quede mirando la pantalla.
 */
export default function HiloDeLaSesion({ conversationId, workspaceSlug }) {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const { currentUser } = useApp();

  const [mensajes, setMensajes] = useState(null);
  const [texto, setTexto] = useState('');
  const [enviando, setEnviando] = useState(false);
  const finRef = useRef(null);

  const textMuted = d ? 'rgba(255,255,255,0.66)' : 'rgba(0,0,0,0.62)';
  const borde = theme.palette.divider;

  useEffect(() => {
    let vivo = true;
    api.getConversationMessages(conversationId)
      .then(({ data }) => { if (vivo) setMensajes(data.messages || []); })
      .catch(() => { if (vivo) setMensajes([]); });
    return () => { vivo = false; };
  }, [conversationId]);

  useEffect(() => {
    finRef.current?.scrollIntoView({ block: 'nearest' });
  }, [mensajes]);

  // Con equipo adentro, el agente solo entra si lo llaman. Se calcula con lo que ya
  // esta a la vista para no pedirle al backend algo que se puede deducir.
  const personas = new Set(
    (mensajes || []).filter((m) => m.role === 'user' && m.autor).map((m) => m.autor.id),
  );
  const hayEquipo = personas.size > 1;
  const llamaAlAgente = texto.includes('@');

  const enviar = async () => {
    const mensaje = texto.trim();
    if (!mensaje || enviando) return;
    const mio = {
      id: `tmp-${Date.now()}`, role: 'user', content: mensaje,
      autor: { id: currentUser?.id, nombre: currentUser?.first_name || 'Yo' },
    };
    setMensajes((ms) => [...(ms || []), mio]);
    setTexto('');
    try {
      setEnviando(true);
      const { data } = await api.responderEnHilo(conversationId, mensaje, {
        workspace: workspaceSlug,
      });
      if (data.message) {
        setMensajes((ms) => [...ms, { id: `r-${Date.now()}`, role: 'assistant', content: data.message }]);
      }
    } catch {
      setMensajes((ms) => ms.filter((m) => m.id !== mio.id));
      setTexto(mensaje);
    } finally {
      setEnviando(false);
    }
  };

  if (mensajes === null) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
        <CircularProgress size={18} sx={{ color: '#586AD0' }} />
      </Box>
    );
  }

  return (
    <Box sx={{ borderTop: `1px solid ${borde}`, mt: 1.5, pt: 1.5 }}>
      <Stack spacing={1.5} sx={{ maxHeight: 380, overflowY: 'auto', pr: 0.5 }}>
        {mensajes.map((m) => {
          const esAgente = m.role === 'assistant';
          const esMio = !m.autor || m.autor.id === currentUser?.id;
          return (
            <Stack key={m.id} direction="row" spacing={1.25} alignItems="flex-start">
              <Box sx={{
                width: 24, height: 24, borderRadius: '7px', flexShrink: 0, mt: 0.25,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                background: esAgente
                  ? 'linear-gradient(135deg, #586AD0 0%, #2F42A6 100%)'
                  : (d ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)'),
                fontSize: '0.68rem', fontWeight: 700,
                color: esAgente ? '#fff' : textMuted,
              }}>
                {esAgente
                  ? <AfableMark size={12} color="#fff" />
                  : (m.autor?.nombre || '?').slice(0, 1).toUpperCase()}
              </Box>
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography sx={{
                  fontSize: '0.72rem', fontWeight: 600, mb: 0.25,
                  color: esAgente ? '#9BA6E3' : textMuted,
                }}>
                  {esAgente ? (m.agent_name || 'Afable') : (esMio ? 'Usted' : m.autor?.nombre)}
                </Typography>
                <Typography sx={{ fontSize: '0.875rem', lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
                  {m.content}
                </Typography>
              </Box>
            </Stack>
          );
        })}
        <div ref={finRef} />
      </Stack>

      <Box sx={{
        display: 'flex', alignItems: 'flex-end', gap: 1, mt: 1.5,
        border: `1px solid ${borde}`, borderRadius: '10px', px: 1.5, py: 1,
        '&:focus-within': { borderColor: 'rgba(88, 106, 208, 0.5)' },
      }}>
        <Box
          component="textarea"
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); enviar(); }
          }}
          onClick={(e) => e.stopPropagation()}
          placeholder={hayEquipo ? 'Responder — escriba @ para llamar al agente' : 'Responder...'}
          rows={1}
          sx={{
            flex: 1, border: 'none', outline: 'none', resize: 'none', bgcolor: 'transparent',
            color: theme.palette.text.primary, fontFamily: 'inherit', fontSize: '0.875rem',
            lineHeight: 1.6, py: 0.5, '&::placeholder': { color: textMuted },
          }}
        />
        <IconButton
          size="small" onClick={(e) => { e.stopPropagation(); enviar(); }}
          disabled={!texto.trim() || enviando}
          sx={{ color: texto.trim() ? '#586AD0' : textMuted }}
        >
          <SendHorizontal size={16} />
        </IconButton>
      </Box>

      {hayEquipo && !llamaAlAgente && (
        <Typography sx={{ fontSize: '0.75rem', color: textMuted, mt: 0.75 }}>
          Esto lo lee el equipo. El agente no responde salvo que lo llame con @.
        </Typography>
      )}
    </Box>
  );
}
