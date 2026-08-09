/**
 * La campana: lo que pasó mientras esta persona no estaba mirando.
 *
 * ⭐ **Por qué hace falta.** Afable dejó de ser una app de una sola persona: en una Sesión
 * escriben varios y las tareas se asignan. Todo eso ya quedaba registrado, pero había que
 * ir a buscarlo pantalla por pantalla — y lo que hay que ir a buscar, no se busca.
 *
 * Dos decisiones que la hacen útil en vez de ruido:
 *
 * - **Cada aviso lleva a un lugar.** Un aviso que no se puede abrir solo informa que uno
 *   se perdió algo, sin decir dónde.
 * - **No se avisa de lo propio** (lo resuelve el backend). Es la forma más rápida de que
 *   la campana se vuelva ruido y se deje de mirar.
 */
import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Badge, Box, Divider, IconButton, Menu, Tooltip, Typography, useTheme,
} from '@mui/material';
import { Bell, CheckCheck, FileText, MessageSquare, Sparkles } from 'lucide-react';
import { api } from '../services/api';

const DISPLAY = `'Sora', 'Inter', sans-serif`;

// Cada cuánto se vuelve a preguntar. Un minuto: lo suficiente para enterarse mientras se
// trabaja, y lo bastante espaciado para no golpear la API por una campana.
const CADA = 60000;

const ICONO = {
  mensaje: MessageSquare,
  tarea: FileText,
  agente: Sparkles,
};

function cuando(iso) {
  const t = new Date(iso).getTime();
  const min = Math.floor((Date.now() - t) / 60000);
  if (min < 1) return 'recién';
  if (min < 60) return `hace ${min} min`;
  const horas = Math.floor(min / 60);
  if (horas < 24) return `hace ${horas} h`;
  const dias = Math.floor(horas / 24);
  return dias === 1 ? 'ayer' : `hace ${dias} días`;
}

export default function Notificaciones({ color }) {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const navigate = useNavigate();

  const [ancla, setAncla] = useState(null);
  const [lista, setLista] = useState([]);
  const [sinLeer, setSinLeer] = useState(0);

  const cargar = useCallback(async () => {
    try {
      const { data } = await api.getNotificaciones();
      setLista(data.notificaciones || []);
      setSinLeer(data.sin_leer || 0);
    } catch {
      // Una campana que no carga no puede romper la barra superior: se queda callada.
    }
  }, []);

  useEffect(() => {
    cargar();
    const t = setInterval(cargar, CADA);
    return () => clearInterval(t);
  }, [cargar]);

  const abrir = (e) => { setAncla(e.currentTarget); cargar(); };

  const marcarTodas = async () => {
    try {
      await api.marcarNotificacionesLeidas();
      setLista((prev) => prev.map((n) => ({ ...n, leida: true })));
      setSinLeer(0);
    } catch { /* si falla, quedan sin leer: no se miente en la pantalla */ }
  };

  const abrirUna = async (n) => {
    setAncla(null);
    if (!n.leida) {
      setSinLeer((v) => Math.max(0, v - 1));
      setLista((prev) => prev.map((x) => (x.id === n.id ? { ...x, leida: true } : x)));
      api.marcarNotificacionLeida(n.id).catch(() => {});
    }
    if (n.enlace) navigate(n.enlace);
  };

  return (
    <>
      <Tooltip title={sinLeer ? `${sinLeer} sin leer` : 'Notificaciones'} arrow>
        <IconButton
          onClick={abrir}
          size="small"
          aria-label="Notificaciones"
          sx={{ color, '&:hover': { color: '#586AD0', bgcolor: 'action.hover' } }}
        >
          <Badge
            badgeContent={sinLeer}
            max={9}
            sx={{
              '& .MuiBadge-badge': {
                bgcolor: '#586AD0', color: '#fff', fontSize: '0.6rem',
                minWidth: 15, height: 15,
              },
            }}
          >
            <Bell size={16} />
          </Badge>
        </IconButton>
      </Tooltip>

      <Menu
        anchorEl={ancla}
        open={Boolean(ancla)}
        onClose={() => setAncla(null)}
        transformOrigin={{ horizontal: 'right', vertical: 'top' }}
        anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
        PaperProps={{ sx: { mt: 0.75, width: 360, borderRadius: '12px' } }}
      >
        <Box sx={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          px: 1.75, py: 1.25,
        }}>
          <Typography sx={{ fontFamily: DISPLAY, fontWeight: 700, fontSize: '0.9rem' }}>
            Notificaciones
          </Typography>
          {sinLeer > 0 && (
            <Box
              onClick={marcarTodas}
              sx={{
                display: 'flex', alignItems: 'center', gap: 0.5, cursor: 'pointer',
                fontSize: '0.72rem', color: 'text.disabled',
                '&:hover': { color: '#586AD0' },
              }}
            >
              <CheckCheck size={13} /> Marcar todas
            </Box>
          )}
        </Box>
        <Divider />

        {lista.length === 0 ? (
          // Se dice qué va a aparecer acá. Un "no hay nada" a secas deja pensando si la
          // campana funciona o si nunca pasa nada.
          <Box sx={{ px: 1.75, py: 3, textAlign: 'center' }}>
            <Typography sx={{ fontSize: '0.8rem', color: 'text.disabled' }}>
              Nada por ahora.
            </Typography>
            <Typography sx={{ fontSize: '0.72rem', color: 'text.disabled', mt: 0.5 }}>
              Acá va a llegar lo que escriban en tus Sesiones y las tareas que te asignen.
            </Typography>
          </Box>
        ) : (
          <Box sx={{ maxHeight: 380, overflowY: 'auto' }}>
            {lista.map((n) => {
              const Icono = ICONO[n.tipo] || Bell;
              return (
                <Box
                  key={n.id}
                  onClick={() => abrirUna(n)}
                  sx={{
                    display: 'flex', gap: 1.25, px: 1.75, py: 1.25, cursor: 'pointer',
                    bgcolor: n.leida
                      ? 'transparent'
                      : (d ? 'rgba(88,106,208,0.10)' : 'rgba(88,106,208,0.05)'),
                    '&:hover': { bgcolor: 'action.hover' },
                  }}
                >
                  <Box sx={{ pt: 0.25 }}>
                    <Icono size={15} color={n.leida ? '#888' : '#7B8AE0'} />
                  </Box>
                  <Box sx={{ minWidth: 0, flex: 1 }}>
                    <Typography sx={{
                      fontSize: '0.82rem', fontWeight: n.leida ? 500 : 700,
                      lineHeight: 1.35,
                    }}>
                      {n.titulo}
                    </Typography>
                    {n.detalle && (
                      <Typography sx={{
                        fontSize: '0.75rem', color: 'text.secondary', mt: 0.25,
                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                      }}>
                        {n.detalle}
                      </Typography>
                    )}
                    <Typography sx={{ fontSize: '0.68rem', color: 'text.disabled', mt: 0.35 }}>
                      {cuando(n.created_at)}
                    </Typography>
                  </Box>
                </Box>
              );
            })}
          </Box>
        )}
      </Menu>
    </>
  );
}
