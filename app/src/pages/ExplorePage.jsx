import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import PageHeader from '../components/PageHeader';
import ProcessFlow from '../components/ProcessFlow';
import {
  Box, Typography, Button, Chip, CircularProgress, useTheme, Snackbar, Alert,
} from '@mui/material';
import { Compass, Users, Sparkles, Plus, Check } from 'lucide-react';
import { api } from '../services/api';

const CATEGORIES = ['Todas', 'Ventas', 'Finanzas', 'Inventario', 'Operaciones', 'RRHH', 'Atención'];

function TemplateCard({ tpl, onUse, busy, done }) {
  const theme = useTheme();
  const dark = theme.palette.mode === 'dark';
  const [hover, setHover] = useState(false);
  const accent = tpl.accent || '#586AD0';

  return (
    <Box
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      sx={{
        bgcolor: 'background.paper',
        border: `1px solid ${hover ? `${accent}66` : theme.palette.divider}`,
        borderRadius: '14px', overflow: 'hidden',
        display: 'flex', flexDirection: 'column',
        transition: 'all 0.18s',
        transform: hover ? 'translateY(-2px)' : 'none',
        boxShadow: hover ? `0 12px 30px ${accent}1f` : 'none',
      }}
    >
      {/* Imagen de proceso */}
      <Box sx={{ p: 1.5, pb: 0 }}>
        <ProcessFlow flow={tpl.flow} accent={accent} dark={dark} />
      </Box>

      <Box sx={{ p: 2, pt: 1.75, display: 'flex', flexDirection: 'column', gap: 1.25, flex: 1 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography sx={{ fontSize: '1.05rem', lineHeight: 1 }}>{tpl.icon}</Typography>
          <Typography sx={{ fontWeight: 600, fontSize: '0.92rem', color: 'text.primary', lineHeight: 1.2, flex: 1 }}>
            {tpl.name}
          </Typography>
          {tpl.category && (
            <Chip label={tpl.category} size="small" sx={{
              height: 19, fontSize: '0.66rem', fontWeight: 600,
              bgcolor: `${accent}1f`, color: accent,
              border: `0.5px solid ${accent}40`, '& .MuiChip-label': { px: 0.75 },
            }} />
          )}
        </Box>

        <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary', lineHeight: 1.55, flex: 1 }}>
          {tpl.description}
        </Typography>

        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mt: 0.25 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, color: 'text.disabled' }}>
            <Users size={12} />
            <Typography sx={{ fontSize: '0.7rem' }}>
              {tpl.author_name} · {tpl.uses_count} usos
            </Typography>
          </Box>
          <Button
            size="small"
            disabled={busy || done}
            startIcon={done ? <Check size={13} /> : <Plus size={13} />}
            onClick={() => onUse(tpl)}
            sx={{
              bgcolor: done ? 'rgba(52,211,153,0.14)' : `${accent}1f`,
              color: done ? '#34D399' : accent,
              border: `0.5px solid ${done ? 'rgba(52,211,153,0.4)' : `${accent}40`}`,
              borderRadius: '7px', fontSize: '0.76rem', fontWeight: 600, px: 1.5, py: 0.5,
              '&:hover': { bgcolor: done ? 'rgba(52,211,153,0.14)' : `${accent}33` },
              '&.Mui-disabled': { color: done ? '#34D399' : 'text.disabled' },
            }}
          >
            {busy ? <CircularProgress size={14} sx={{ color: accent }} /> : done ? 'Agregado' : 'Usar plantilla'}
          </Button>
        </Box>
      </Box>
    </Box>
  );
}

export default function ExplorePage() {
  const navigate = useNavigate();
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('Todas');
  const [busyId, setBusyId] = useState(null);
  const [doneIds, setDoneIds] = useState([]);
  const [toast, setToast] = useState(null);

  useEffect(() => {
    api.getTemplates({ kind: 'community' })
      .then(r => setTemplates(r.data || []))
      .catch(() => setTemplates([]))
      .finally(() => setLoading(false));
  }, []);

  const handleUse = async (tpl) => {
    setBusyId(tpl.id);
    try {
      const { data: agent } = await api.useTemplate(tpl.id);
      setDoneIds(prev => [...prev, tpl.id]);
      setToast({ name: agent.name, agentId: agent.id });
    } catch {
      setToast({ error: true });
    } finally {
      setBusyId(null);
    }
  };

  const shown = filter === 'Todas' ? templates : templates.filter(t => t.category === filter);

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100%' }}>
      <PageHeader title="Home" back="/app" backLabel="Chat" />

      <Box sx={{ p: { xs: 2, sm: 3 } }}>
        {/* Intro */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 0.75 }}>
          <Box sx={{
            width: 38, height: 38, borderRadius: '10px', flexShrink: 0,
            bgcolor: 'rgba(88, 106, 208,0.12)', border: '0.5px solid rgba(88, 106, 208,0.25)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Compass size={20} color="#9BA6E3" />
          </Box>
          <Box>
            <Typography sx={{ fontWeight: 700, fontSize: '1.15rem', color: 'text.primary', lineHeight: 1.2 }}>
              Plantillas de la comunidad
            </Typography>
            <Typography sx={{ fontSize: '0.83rem', color: 'text.secondary' }}>
              Agentes y automatizaciones que otros ya armaron. Úsalos en tu empresa en un clic y adáptalos a tus sistemas.
            </Typography>
          </Box>
        </Box>

        {/* Filtros */}
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, my: 2.5 }}>
          {CATEGORIES.map(c => {
            const sel = filter === c;
            return (
              <Chip
                key={c} label={c} onClick={() => setFilter(c)}
                sx={{
                  cursor: 'pointer', fontSize: '0.78rem', fontWeight: 600, borderRadius: '8px',
                  bgcolor: sel ? 'rgba(88, 106, 208,0.16)' : 'action.hover',
                  color: sel ? '#9BA6E3' : 'text.secondary',
                  border: `1px solid ${sel ? 'rgba(88, 106, 208,0.4)' : 'transparent'}`,
                  '&:hover': { bgcolor: sel ? 'rgba(88, 106, 208,0.22)' : 'action.selected' },
                }}
              />
            );
          })}
        </Box>

        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', pt: 8 }}>
            <CircularProgress sx={{ color: '#586AD0' }} />
          </Box>
        ) : shown.length === 0 ? (
          <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '40vh', gap: 2, textAlign: 'center' }}>
            <Sparkles size={30} color="#9BA6E3" />
            <Typography sx={{ color: 'text.secondary', fontSize: '0.9rem' }}>
              No hay plantillas en esta categoría todavía.
            </Typography>
          </Box>
        ) : (
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr', lg: '1fr 1fr 1fr' }, gap: 2.5 }}>
            {shown.map(tpl => (
              <TemplateCard
                key={tpl.id} tpl={tpl}
                busy={busyId === tpl.id}
                done={doneIds.includes(tpl.id)}
                onUse={handleUse}
              />
            ))}
          </Box>
        )}
      </Box>

      <Snackbar
        open={!!toast} autoHideDuration={5000} onClose={() => setToast(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        {toast?.error ? (
          <Alert severity="error" onClose={() => setToast(null)} sx={{ borderRadius: '10px' }}>
            No se pudo agregar la plantilla.
          </Alert>
        ) : (
          <Alert
            severity="success" onClose={() => setToast(null)}
            sx={{ borderRadius: '10px', alignItems: 'center' }}
            action={
              <Button
                size="small"
                onClick={() => navigate('/app', { state: { agentId: toast?.agentId, agentName: toast?.name } })}
                sx={{ color: '#586AD0', fontWeight: 700, fontSize: '0.78rem' }}
              >
                Chatear
              </Button>
            }
          >
            "{toast?.name}" agregado a tus agentes.
          </Alert>
        )}
      </Snackbar>
    </Box>
  );
}
