import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Box, CircularProgress, TextField, Typography, useTheme } from '@mui/material';
import { Bot, ChevronRight, Search } from 'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../../services/api';
import { useWorkspace } from '../../context/WorkspaceContext';

const DISPLAY = `'Sora', 'Inter', sans-serif`;

/**
 * Admin › Agentes.
 *
 * El agente llega sabiendo su oficio; no sabe nada de ESTA empresa. Acá se ve
 * cuáles ya recibieron lo suyo y cuáles siguen pendientes. Solo administradores.
 */
export default function AgentesAdminPage() {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const navigate = useNavigate();
  const { slug, esAdmin, loading: cargandoWorkspace } = useWorkspace();

  const textMuted = d ? 'rgba(255,255,255,0.66)' : 'rgba(0,0,0,0.62)';
  const textSemi = d ? 'rgba(255,255,255,0.82)' : 'rgba(0,0,0,0.76)';
  const bgSuave = d ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.02)';
  const borde = theme.palette.divider;

  const [agentes, setAgentes] = useState([]);
  const [pendientes, setPendientes] = useState(0);
  const [busqueda, setBusqueda] = useState('');
  const [cargando, setCargando] = useState(true);

  const cargar = useCallback(async () => {
    if (!slug || !esAdmin) return;
    try {
      setCargando(true);
      const { data } = await api.getAdminAgents(slug);
      setAgentes(data.results);
      setPendientes(data.pendientes);
    } catch {
      toast.error('No se pudieron cargar los agentes.');
    } finally {
      setCargando(false);
    }
  }, [slug, esAdmin]);

  useEffect(() => { cargar(); }, [cargar]);

  const filtrados = useMemo(() => {
    const q = busqueda.trim().toLowerCase();
    if (!q) return agentes;
    return agentes.filter((a) => a.name.toLowerCase().includes(q));
  }, [agentes, busqueda]);

  if (cargandoWorkspace || (cargando && !agentes.length)) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', pt: 12 }}>
        <CircularProgress size={26} sx={{ color: '#586AD0' }} />
      </Box>
    );
  }

  if (!esAdmin) {
    return (
      <Box sx={{ maxWidth: 1000, mx: 'auto', px: 5, py: 6 }}>
        <Typography sx={{ color: textMuted, fontSize: '0.9375rem' }}>
          Solo un administrador del Workspace configura los agentes.
        </Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ maxWidth: 1000, mx: 'auto', px: { xs: 2.5, md: 5 }, py: { xs: 4, md: 6 }, width: '100%' }}>
      <Bot size={24} color={textSemi} strokeWidth={1.75} />
      <Typography sx={{ fontFamily: DISPLAY, fontSize: '1.875rem', fontWeight: 600, mt: 1.5, letterSpacing: '-0.01em' }}>
        Agentes
      </Typography>
      <Typography sx={{ color: textMuted, fontSize: '0.9375rem', mt: 0.75 }}>
        Cada agente sabe su oficio, pero no sabe nada de su empresa. Acá le entrega sus datos, sus
        reglas y lo que le conviene saber.
      </Typography>

      {pendientes > 0 && (
        <Box sx={{
          mt: 3, p: 1.75, borderRadius: '10px',
          border: '1px solid rgba(240, 180, 41, 0.35)', bgcolor: 'rgba(240, 180, 41, 0.08)',
        }}>
          <Typography sx={{ fontSize: '0.9375rem', color: theme.palette.text.primary }}>
            {pendientes === 1
              ? 'Hay 1 agente sin configurar: todavía responde sin saber nada de su empresa.'
              : `Hay ${pendientes} agentes sin configurar: todavía responden sin saber nada de su empresa.`}
          </Typography>
        </Box>
      )}

      <TextField
        value={busqueda}
        onChange={(e) => setBusqueda(e.target.value)}
        placeholder="Buscar agentes"
        fullWidth size="small"
        sx={{ mt: 3 }}
        InputProps={{
          endAdornment: <Search size={16} color={textMuted} />,
          sx: {
            bgcolor: bgSuave, borderRadius: '8px', fontSize: '0.9375rem',
            '& fieldset': { borderColor: borde },
            '&.Mui-focused fieldset': { borderColor: '#586AD0' },
          },
        }}
      />

      <Box sx={{ mt: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', pb: 1.25, borderBottom: `1px solid ${borde}` }}>
          <Typography sx={{ flex: 5, fontSize: '0.8rem', fontWeight: 700, color: textSemi }}>Nombre</Typography>
          <Typography sx={{ flex: 3, fontSize: '0.8rem', fontWeight: 700, color: textSemi }}>Estado</Typography>
          <Box sx={{ width: 32 }} />
        </Box>

        {filtrados.map((a) => (
          <Box
            key={a.id}
            onClick={() => navigate(`/app/admin/agentes/${a.id}`)}
            sx={{
              display: 'flex', alignItems: 'center', py: 1.75, cursor: 'pointer',
              borderBottom: `1px solid ${borde}`,
              '&:hover': { bgcolor: bgSuave },
            }}
          >
            <Box sx={{ flex: 5, minWidth: 0, pr: 2 }}>
              <Typography sx={{ fontSize: '0.9375rem', fontWeight: 500 }}>{a.name}</Typography>
              <Typography sx={{
                fontSize: '0.875rem', color: textMuted,
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>
                {a.description || 'Sin descripción.'}
              </Typography>
            </Box>
            <Box sx={{ flex: 3 }}>
              <Box component="span" sx={{
                px: 1, py: 0.25, borderRadius: '6px', fontSize: '0.8125rem', fontWeight: 600,
                bgcolor: a.configurado ? 'rgba(52, 211, 153, 0.14)' : 'rgba(240, 180, 41, 0.14)',
                color: a.configurado ? '#34D399' : '#f0b429',
                border: `1px solid ${a.configurado ? 'rgba(52, 211, 153, 0.3)' : 'rgba(240, 180, 41, 0.3)'}`,
              }}>
                {a.configurado ? 'Configurado' : 'Pendiente'}
              </Box>
            </Box>
            <Box sx={{ width: 32, display: 'flex', justifyContent: 'flex-end', color: textMuted }}>
              <ChevronRight size={16} />
            </Box>
          </Box>
        ))}

        {filtrados.length === 0 && (
          <Typography sx={{ color: textMuted, fontSize: '0.9375rem', py: 3 }}>
            Ningún agente coincide con la búsqueda.
          </Typography>
        )}

        <Typography sx={{ color: textMuted, fontSize: '0.8125rem', textAlign: 'right', mt: 1.5 }}>
          {filtrados.length} {filtrados.length === 1 ? 'agente' : 'agentes'}
        </Typography>
      </Box>
    </Box>
  );
}
