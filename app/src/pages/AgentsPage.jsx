import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import PageHeader from '../components/PageHeader';
import { Box, Typography, Button, Chip, Modal, CircularProgress, useTheme } from '@mui/material';
import { Wrench, Clock, X, MessageSquare } from 'lucide-react';
import { api } from '../services/api';

// Card de un agente fijo (siempre disponible, sin "agregar"): clic abre la
// tarjeta de detalle. El chat real se crea/reusa recién al presionar "Chat".
function AgentCard({ tpl, onOpen }) {
  const theme = useTheme();
  const [hover, setHover] = useState(false);
  const accent = tpl.accent || '#586AD0';
  return (
    <Box
      onClick={() => onOpen(tpl)}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      sx={{
        bgcolor: 'background.paper',
        border: `1px solid ${hover ? `${accent}66` : theme.palette.divider}`,
        borderRadius: '12px', p: 2.25, cursor: 'pointer',
        display: 'flex', flexDirection: 'column', gap: 1.25,
        transition: 'all 0.18s',
        transform: hover ? 'translateY(-2px)' : 'none',
        boxShadow: hover ? `0 10px 26px ${accent}1f` : 'none',
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25 }}>
        <Box sx={{
          width: 40, height: 40, borderRadius: '10px', flexShrink: 0,
          bgcolor: `${accent}18`, border: `0.5px solid ${accent}40`,
          display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.15rem',
        }}>
          {tpl.icon}
        </Box>
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography sx={{ fontWeight: 600, fontSize: '0.88rem', color: 'text.primary', lineHeight: 1.2 }}>
            {tpl.name}
          </Typography>
          <Chip label={tpl.category} size="small" sx={{
            height: 18, fontSize: '0.64rem', fontWeight: 600, mt: 0.4,
            bgcolor: `${accent}1f`, color: accent,
            border: `0.5px solid ${accent}40`, '& .MuiChip-label': { px: 0.75 },
          }} />
        </Box>
      </Box>

      <Typography sx={{ fontSize: '0.79rem', color: 'text.secondary', lineHeight: 1.55, flex: 1, minHeight: 38 }}>
        {tpl.description}
      </Typography>

      <Typography sx={{ fontSize: '0.78rem', fontWeight: 600, color: accent }}>
        Ver detalles →
      </Typography>
    </Box>
  );
}

// "Tarjeta del agente": ventana de detalle antes de chatear — qué hace, cómo
// analiza, qué herramientas usa y cada cuánto conviene accionarlo. El botón
// "Chat" recién ahí crea/reusa el Agent real y abre su historial único.
function AgentDetailModal({ tpl, onClose, onChat, chatting }) {
  const theme = useTheme();
  if (!tpl) return null;
  const accent = tpl.accent || '#586AD0';
  return (
    <Modal open={!!tpl} onClose={onClose}>
      <Box sx={{
        position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%,-50%)',
        width: 460, maxWidth: '92vw', maxHeight: '86vh', overflowY: 'auto', bgcolor: 'background.paper',
        border: '1px solid', borderColor: 'divider', borderRadius: '14px', p: 3,
        boxShadow: '0 24px 60px rgba(0,0,0,0.2)',
      }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25 }}>
            <Box sx={{
              width: 44, height: 44, borderRadius: '10px', flexShrink: 0,
              bgcolor: `${accent}18`, border: `0.5px solid ${accent}40`,
              display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.3rem',
            }}>
              {tpl.icon}
            </Box>
            <Box>
              <Typography sx={{ fontWeight: 700, fontSize: '1.05rem', color: 'text.primary' }}>{tpl.name}</Typography>
              <Chip label={tpl.category} size="small" sx={{
                height: 18, fontSize: '0.64rem', fontWeight: 600, mt: 0.4,
                bgcolor: `${accent}1f`, color: accent,
                border: `0.5px solid ${accent}40`, '& .MuiChip-label': { px: 0.75 },
              }} />
            </Box>
          </Box>
          <Box onClick={onClose} sx={{ cursor: 'pointer', color: 'text.disabled', '&:hover': { color: 'text.primary' }, display: 'flex' }}>
            <X size={18} />
          </Box>
        </Box>

        <Typography sx={{ fontSize: '0.85rem', color: 'text.secondary', lineHeight: 1.6, mb: 2.5 }}>
          {tpl.description}
        </Typography>

        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.75, mb: 2.75 }}>
          <Box sx={{ display: 'flex', gap: 1.25, alignItems: 'flex-start' }}>
            <Wrench size={15} style={{ marginTop: 2, flexShrink: 0 }} color={theme.palette.text.disabled} />
            <Box>
              <Typography sx={{ fontSize: '0.68rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'text.disabled' }}>
                Cómo analiza
              </Typography>
              <Typography sx={{ fontSize: '0.82rem', color: 'text.primary', mt: 0.25 }}>
                {tpl.tools_summary || 'Consulta tus sistemas conectados y responde citando la fuente.'}
              </Typography>
            </Box>
          </Box>
          <Box sx={{ display: 'flex', gap: 1.25, alignItems: 'flex-start' }}>
            <Clock size={15} style={{ marginTop: 2, flexShrink: 0 }} color={theme.palette.text.disabled} />
            <Box>
              <Typography sx={{ fontSize: '0.68rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'text.disabled' }}>
                Frecuencia recomendada
              </Typography>
              <Typography sx={{ fontSize: '0.82rem', color: 'text.primary', mt: 0.25 }}>
                {tpl.recommended_frequency || 'Cuando lo necesites'}
              </Typography>
            </Box>
          </Box>
        </Box>

        <Button
          fullWidth
          disabled={chatting}
          startIcon={chatting ? <CircularProgress size={14} sx={{ color: '#fff' }} /> : <MessageSquare size={15} />}
          onClick={() => onChat(tpl)}
          sx={{
            bgcolor: '#586AD0', color: '#fff', borderRadius: '8px', fontWeight: 600, py: 0.9,
            '&:hover': { bgcolor: '#2F42A6' },
          }}
        >
          Chat
        </Button>
      </Box>
    </Modal>
  );
}

export default function AgentsPage() {
  const navigate = useNavigate();
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [detailTpl, setDetailTpl] = useState(null);
  const [chatting, setChatting] = useState(false);

  useEffect(() => {
    api.getTemplates({ kind: 'role' })
      .then(r => setTemplates(r.data || []))
      .catch(() => setTemplates([]))
      .finally(() => setLoading(false));
  }, []);

  const handleChat = async (tpl) => {
    setChatting(true);
    try {
      const { data: agent } = await api.useTemplate(tpl.id);
      setDetailTpl(null);
      navigate('/app', { state: { agentId: agent.id, agentName: agent.name } });
    } catch {
      setChatting(false);
    }
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100%' }}>
      <PageHeader title="Agentes" back="/app" backLabel="Chat" />
      <Box sx={{ p: { xs: 2, sm: 3 } }}>
        <Typography sx={{ fontSize: '0.83rem', color: 'text.secondary', mb: 2.5 }}>
          Un agente listo para cada foco de tu negocio. Haz clic para ver qué hace y empezar a chatear.
        </Typography>

        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', pt: 8 }}>
            <CircularProgress sx={{ color: '#586AD0' }} />
          </Box>
        ) : (
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr', lg: '1fr 1fr 1fr 1fr' }, gap: 2 }}>
            {templates.map(tpl => (
              <AgentCard key={tpl.id} tpl={tpl} onOpen={setDetailTpl} />
            ))}
          </Box>
        )}
      </Box>

      <AgentDetailModal
        tpl={detailTpl}
        onClose={() => setDetailTpl(null)}
        onChat={handleChat}
        chatting={chatting}
      />
    </Box>
  );
}
