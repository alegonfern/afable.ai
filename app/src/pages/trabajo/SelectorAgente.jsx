import { Box, useTheme } from '@mui/material';
import { Bot, ChevronDown } from 'lucide-react';

/**
 * El agente con el que se esta hablando, dentro del compositor.
 *
 * Es lo que sostiene la diferencia con un chat generico: en CUALQUIER
 * conversacion, incluso a mitad de camino, se ve quien responde y se puede
 * cambiar.
 *
 * Acá solo vive la pastilla. La vitrina se despliega dentro del propio
 * compositor (ver ChatPage): no es un panel que aparece encima, es la caja de
 * escribir que se expande. Por eso el estado de abierto/cerrado lo lleva quien
 * monta el compositor y no este componente.
 */
export default function SelectorAgente({ agenteActivo, abierto = false, onToggle }) {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const textMuted = d ? 'rgba(255,255,255,0.66)' : 'rgba(0,0,0,0.62)';

  return (
    <Box
      onClick={onToggle}
      title="Elegir con qué agente hablar"
      sx={{
        display: 'flex', alignItems: 'center', gap: 0.6,
        px: 0.875, py: 0.4, borderRadius: '6px', cursor: 'pointer',
        color: agenteActivo ? '#9BA6E3' : textMuted,
        fontSize: '0.8125rem', fontWeight: 500, maxWidth: 190,
        bgcolor: abierto ? (d ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.04)') : 'transparent',
        '&:hover': { bgcolor: d ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.04)' },
      }}
    >
      <Bot size={14} style={{ flexShrink: 0 }} />
      <Box component="span" sx={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {agenteActivo?.name || 'Afable'}
      </Box>
      <ChevronDown
        size={12}
        style={{ flexShrink: 0, transform: abierto ? 'rotate(180deg)' : 'none', transition: 'transform .18s' }}
      />
    </Box>
  );
}
