import { useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Box, IconButton, Typography, useTheme } from '@mui/material';
import { Bot, Paperclip, SendHorizontal, Wrench } from 'lucide-react';
import { useApp } from '../../context/AppContext';
import AgentesGaleria from './AgentesGaleria';
import MencionAgentes, { useMenciones } from '../../components/MencionAgentes';
import { useWorkspace } from '../../context/WorkspaceContext';
import PrimerosPasos from '../../components/PrimerosPasos';
import LoQueHizoAfable from '../../components/LoQueHizoAfable';

const SALUDOS = [
  { texto: 'Qué bueno verlo', emoji: '👋' },
  { texto: 'A ponerse al día', emoji: '☕' },
  { texto: 'Manos a la obra', emoji: '💪' },
  { texto: 'Todo listo para trabajar', emoji: '✨' },
];

/**
 * La home del modo Trabajo.
 *
 * Saludo, una sola caja grande para escribir, y debajo la galeria de Agentes.
 * Lo que se escribe aca no se responde aca: se manda al chat (/app/chat), que es
 * el que sabe de streaming, adjuntos y menciones.
 */
export default function TrabajoHome() {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const navigate = useNavigate();
  const { currentUser } = useApp();

  const textMuted = d ? 'rgba(255,255,255,0.66)' : 'rgba(0,0,0,0.62)';
  const bgCaja = d ? '#1a1a1a' : '#ffffff';
  const borde = theme.palette.divider;

  const [texto, setTexto] = useState('');
  const campoRef = useRef(null);
  const { slug } = useWorkspace();

  // También acá: la portada es donde más gente escribe su primer mensaje, y si el `@` no
  // ofrece nada la funcionalidad más propia del producto pasa desapercibida.
  const menciones = useMenciones({
    texto, setTexto, workspace: slug, inputRef: campoRef,
  });

  const nombre = currentUser?.first_name || (currentUser?.email || '').split('@')[0] || '';
  // Un saludo por sesion: cambia al recargar, no mientras se escribe.
  const saludo = useMemo(() => SALUDOS[Math.floor(Math.random() * SALUDOS.length)], []);

  const enviar = () => {
    const mensaje = texto.trim();
    if (!mensaje) return;
    navigate('/app/chat', { state: { initialMessage: mensaje } });
  };

  return (
    <Box sx={{ maxWidth: 820, mx: 'auto', px: { xs: 2.5, md: 4 }, py: { xs: 4, md: 6 }, width: '100%' }}>
      {/* Lo que le falta a la empresa. Se dibuja solo mientras falte algo, y solo al
          administrador: los pasos son cosas que unicamente el puede hacer. */}
      {/* Primero lo que Afable hizo solo —es la razón por la que se vuelve— y después
          lo que falta configurar. */}
      <LoQueHizoAfable />
      <PrimerosPasos />

      <Typography
        sx={{
          textAlign: 'center', fontSize: '1.5rem', fontWeight: 600,
          letterSpacing: '-0.01em', mb: 3,
        }}
      >
        {saludo.texto}{nombre ? `, ${nombre}` : ''} {saludo.emoji}
      </Typography>

      {/* Una sola caja: escribir y mandar */}
      <Box sx={{
        position: 'relative',
        border: `1px solid ${borde}`, borderRadius: '12px', bgcolor: bgCaja,
        px: 2, pt: 1.75, pb: 1,
        '&:focus-within': { borderColor: 'rgba(88, 106, 208, 0.5)' },
        transition: 'border-color .15s',
      }}>
        {menciones.mencion && (
          <MencionAgentes
            agentes={menciones.sugerencias}
            indice={menciones.indice}
            onElegir={menciones.elegir}
          />
        )}
        <Box
          component="textarea"
          ref={campoRef}
          value={texto}
          onChange={menciones.alEscribir}
          onKeyDown={(e) => {
            if (menciones.alTeclear(e)) return;
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); enviar(); }
          }}
          placeholder="¿En qué trabajamos hoy? Escriba @ para llamar a un agente"
          rows={2}
          sx={{
            width: '100%', border: 'none', outline: 'none', resize: 'none',
            bgcolor: 'transparent', color: theme.palette.text.primary,
            fontFamily: 'inherit', fontSize: '0.9375rem', lineHeight: 1.6,
            '&::placeholder': { color: textMuted },
          }}
        />

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mt: 0.5 }}>
          {/* Agente activo */}
          <Box sx={{
            display: 'flex', alignItems: 'center', gap: 0.75,
            px: 1, py: 0.4, borderRadius: '6px', color: textMuted,
            fontSize: '0.8125rem', fontWeight: 500,
          }}>
            <Bot size={15} />
            Afable
          </Box>

          <IconButton size="small" onClick={() => navigate('/app/contexto')} title="Herramientas y conexiones" sx={{ color: textMuted }}>
            <Wrench size={15} />
          </IconButton>
          <IconButton size="small" onClick={() => navigate('/app/chat')} title="Adjuntar un archivo" sx={{ color: textMuted }}>
            <Paperclip size={15} />
          </IconButton>

          <Box sx={{ flex: 1 }} />

          <IconButton
            size="small"
            onClick={enviar}
            disabled={!texto.trim()}
            title="Enviar"
            sx={{
              bgcolor: texto.trim() ? '#586AD0' : 'transparent',
              color: texto.trim() ? '#fff' : textMuted,
              '&:hover': { bgcolor: texto.trim() ? '#2F42A6' : 'transparent' },
            }}
          >
            <SendHorizontal size={16} />
          </IconButton>
        </Box>
      </Box>

      <AgentesGaleria />
    </Box>
  );
}
