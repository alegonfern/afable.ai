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
 *
 * El panel (30-10-2026): agrupado por día, con un filtro Todas / Sin leer, el ícono de cada tipo
 * en su tono (theme/tonos.js), el detalle en dos líneas y los avisos repetidos juntos en uno
 * (el mismo aviso hacia el mismo lugar llegaba dos o tres veces). La campana se mueve cuando
 * llega algo nuevo.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Badge, Box, IconButton, Popover, Tooltip, Typography } from '@mui/material';
import { AnimatePresence, motion, useAnimationControls, useReducedMotion } from 'framer-motion';
import { Bell, CheckCheck, ChevronRight, FileText, MessageSquare, Sparkles } from 'lucide-react';
import IsotipoPensando from './IsotipoPensando';
import { TONOS } from '../theme/tonos';
import { api } from '../services/api';

const DISPLAY = `'Sora', 'Inter', sans-serif`;

// Cada cuánto se vuelve a preguntar. Un minuto: lo suficiente para enterarse mientras se
// trabaja, y lo bastante espaciado para no golpear la API por una campana.
const CADA = 60000;

const TIPOS = {
  mensaje: { icono: MessageSquare, tono: TONOS.pizarra },
  tarea: { icono: FileText, tono: TONOS.arena },
  // Los avisos de agente salen solo cuando la respuesta trae algo para confirmar (avisos.py).
  agente: { icono: Sparkles, tono: TONOS.malva, marca: 'Por confirmar' },
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

// El grupo de cada aviso según el día en que llegó.
function grupoDe(iso) {
  const dia = (x) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const dias = Math.round((dia(new Date()) - dia(new Date(iso))) / 86400000);
  if (dias <= 0) return 'Hoy';
  if (dias === 1) return 'Ayer';
  if (dias < 7) return 'Esta semana';
  return 'Antes';
}

// Junta los avisos iguales (mismo tipo, detalle y destino) en uno, con cuántas veces llegó.
function juntar(lista) {
  const vistos = new Map();
  const salida = [];
  lista.forEach((n) => {
    const clave = `${n.tipo}|${n.detalle}|${n.enlace}`;
    const ya = vistos.get(clave);
    if (ya) {
      ya.veces += 1;
      ya.ids.push(n.id);
      ya.leida = ya.leida && n.leida;
    } else {
      const nuevo = { ...n, veces: 1, ids: [n.id] };
      vistos.set(clave, nuevo);
      salida.push(nuevo);
    }
  });
  return salida;
}

function Aviso({ n, onAbrir }) {
  const tipo = TIPOS[n.tipo] || { icono: Bell, tono: TONOS.neutro };
  const Icono = tipo.icono;
  return (
    <Box
      component={motion.div}
      layout
      initial={{ opacity: 0, y: -6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, height: 0 }}
      transition={{ duration: 0.22 }}
      onClick={() => onAbrir(n)}
      sx={{
        position: 'relative', display: 'flex', gap: 1.5, mx: 1, px: 1.25, py: 1.25, borderRadius: '10px',
        cursor: 'pointer', transition: 'background-color .15s',
        '&:hover': { bgcolor: 'action.hover' },
        '&:hover .aviso-ir': { opacity: 1, transform: 'translateX(0)' },
      }}
    >
      <Box sx={{
        width: 32, height: 32, borderRadius: '9px', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
        bgcolor: n.leida ? 'action.hover' : tipo.tono.suave, color: n.leida ? 'text.disabled' : tipo.tono.color,
      }}>
        <Icono size={15} />
      </Box>
      <Box sx={{ minWidth: 0, flex: 1, pr: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, flexWrap: 'wrap' }}>
          <Typography sx={{ fontSize: '0.83rem', fontWeight: n.leida ? 500 : 600, lineHeight: 1.35, color: n.leida ? 'text.secondary' : 'text.primary' }}>
            {n.titulo}
          </Typography>
          {n.veces > 1 && (
            <Typography component="span" sx={{ fontSize: '0.66rem', fontWeight: 600, color: 'text.secondary', bgcolor: 'action.hover', px: 0.6, borderRadius: '4px' }}>
              ×{n.veces}
            </Typography>
          )}
        </Box>
        {n.detalle && (
          <Typography sx={{
            fontSize: '0.76rem', color: 'text.secondary', mt: 0.35, lineHeight: 1.45,
            display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden',
          }}>
            {n.detalle}
          </Typography>
        )}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.6 }}>
          <Typography sx={{ fontSize: '0.68rem', color: 'text.disabled' }}>{cuando(n.created_at)}</Typography>
          {tipo.marca && !n.leida && (
            <Typography component="span" sx={{
              fontSize: '0.66rem', fontWeight: 500, color: tipo.tono.color, bgcolor: tipo.tono.suave, px: 0.75, py: 0.1, borderRadius: '999px',
            }}>
              {tipo.marca}
            </Typography>
          )}
        </Box>
      </Box>
      {/* Sin leer: un punto a la derecha. Al pasar el mouse, la flecha dice que lleva a algún lugar. */}
      {!n.leida && (
        <Box sx={{ position: 'absolute', right: 12, top: 18, width: 7, height: 7, borderRadius: '50%', bgcolor: '#e5484d' }} />
      )}
      <Box className="aviso-ir" sx={{
        position: 'absolute', right: 8, bottom: 12, color: 'text.disabled', opacity: 0, transform: 'translateX(-4px)', transition: 'all .15s',
      }}>
        <ChevronRight size={15} />
      </Box>
    </Box>
  );
}

export default function Notificaciones({ color }) {
  const navigate = useNavigate();
  const reducido = useReducedMotion();
  const campana = useAnimationControls();

  const [ancla, setAncla] = useState(null);
  const [lista, setLista] = useState([]);
  const [sinLeer, setSinLeer] = useState(0);
  const [filtro, setFiltro] = useState('todas');
  const anterior = useRef(null);

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
    // El chat avisa cuando deja una notificación nueva (services/avisoRespuesta.js).
    window.addEventListener('afable-notificaciones', cargar);
    return () => { clearInterval(t); window.removeEventListener('afable-notificaciones', cargar); };
  }, [cargar]);

  // La campana se mueve cuando sube el número de sin leer (no al cargar la página).
  useEffect(() => {
    if (anterior.current !== null && sinLeer > anterior.current && !reducido) {
      campana.start({ rotate: [0, -16, 13, -9, 6, 0], transition: { duration: 0.7 } });
    }
    anterior.current = sinLeer;
  }, [sinLeer, campana, reducido]);

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
      const ids = new Set(n.ids);
      const cuantas = lista.filter((x) => ids.has(x.id) && !x.leida).length;
      setSinLeer((v) => Math.max(0, v - cuantas));
      setLista((prev) => prev.map((x) => (ids.has(x.id) ? { ...x, leida: true } : x)));
      n.ids.forEach((id) => api.marcarNotificacionLeida(id).catch(() => {}));
    }
    if (n.enlace) navigate(n.enlace);
  };

  const grupos = useMemo(() => {
    const visibles = juntar(filtro === 'sin-leer' ? lista.filter((n) => !n.leida) : lista);
    const orden = ['Hoy', 'Ayer', 'Esta semana', 'Antes'];
    const porGrupo = {};
    visibles.forEach((n) => { (porGrupo[grupoDe(n.created_at)] ||= []).push(n); });
    return orden.filter((g) => porGrupo[g]).map((g) => [g, porGrupo[g]]);
  }, [lista, filtro]);

  return (
    <>
      <Tooltip title={sinLeer ? `${sinLeer} sin leer` : 'Notificaciones'} arrow>
        <IconButton
          onClick={abrir}
          size="small"
          aria-label="Notificaciones"
          sx={{ color, '&:hover': { color: 'var(--af-acento)', bgcolor: 'action.hover' } }}
        >
          <Badge
            badgeContent={sinLeer}
            max={9}
            sx={{
              '& .MuiBadge-badge': {
                // Rojo (25-10-2026): lo sin leer tiene que saltar a la vista en la barra.
                bgcolor: '#e5484d', color: '#fff', fontSize: '0.6rem',
                minWidth: 15, height: 15,
              },
            }}
          >
            <motion.span animate={campana} style={{ display: 'inline-flex', transformOrigin: '50% 10%' }}>
              <Bell size={16} />
            </motion.span>
          </Badge>
        </IconButton>
      </Tooltip>

      <Popover
        anchorEl={ancla}
        open={Boolean(ancla)}
        onClose={() => setAncla(null)}
        transformOrigin={{ horizontal: 'right', vertical: 'top' }}
        anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
        PaperProps={{ sx: {
          mt: 1, width: 400, maxWidth: 'calc(100vw - 24px)', borderRadius: '16px', border: '1px solid', borderColor: 'divider',
          boxShadow: '0 1px 2px rgba(0,0,0,0.04), 0 24px 48px -16px rgba(0,0,0,0.22)', overflow: 'hidden',
        } }}
      >
        {/* Cabecera: título, cuántas sin leer y el filtro. */}
        <Box sx={{ px: 2, pt: 1.75, pb: 1.25 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography sx={{ fontFamily: DISPLAY, fontWeight: 600, fontSize: '1rem', letterSpacing: '-0.01em', flex: 1 }}>
              Notificaciones
            </Typography>
            {sinLeer > 0 && (
              <Box
                component="button"
                onClick={marcarTodas}
                sx={{
                  display: 'flex', alignItems: 'center', gap: 0.5, border: 0, bgcolor: 'transparent', p: 0.5, borderRadius: '6px',
                  cursor: 'pointer', fontFamily: 'inherit', fontSize: '0.74rem', color: 'text.secondary',
                  '&:hover': { color: 'text.primary', bgcolor: 'action.hover' },
                }}
              >
                <CheckCheck size={14} /> Marcar todas como leídas
              </Box>
            )}
          </Box>
          <Box sx={{ display: 'inline-flex', gap: 0.25, p: 0.375, mt: 1.25, borderRadius: '9px', bgcolor: 'action.hover' }}>
            {[['todas', 'Todas'], ['sin-leer', 'Sin leer']].map(([clave, nombre]) => (
              <Box
                key={clave}
                component="button"
                onClick={() => setFiltro(clave)}
                sx={{
                  display: 'flex', alignItems: 'center', gap: 0.75, border: 0, cursor: 'pointer', fontFamily: 'inherit',
                  fontSize: '0.76rem', fontWeight: 500, px: 1.25, py: 0.5, borderRadius: '7px',
                  bgcolor: filtro === clave ? 'background.paper' : 'transparent',
                  color: filtro === clave ? 'text.primary' : 'text.secondary',
                  boxShadow: filtro === clave ? '0 1px 2px rgba(0,0,0,0.1)' : 'none',
                }}
              >
                {nombre}
                {clave === 'sin-leer' && sinLeer > 0 && (
                  <Box component="span" sx={{ fontSize: '0.66rem', fontWeight: 600, color: '#fff', bgcolor: '#e5484d', px: 0.6, borderRadius: '999px', lineHeight: 1.5 }}>
                    {sinLeer}
                  </Box>
                )}
              </Box>
            ))}
          </Box>
        </Box>

        <Box sx={{ maxHeight: 440, overflowY: 'auto', pb: 1, borderTop: '1px solid', borderColor: 'divider' }}>
          {grupos.length === 0 ? (
            // Se dice qué va a aparecer acá. Un "no hay nada" a secas deja pensando si la
            // campana funciona o si nunca pasa nada.
            <Box sx={{ px: 3, py: 5, textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <Box sx={{ width: 44, height: 44, borderRadius: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center', bgcolor: 'action.hover', mb: 1.5 }}>
                <IsotipoPensando size={18} girando={false} />
              </Box>
              <Typography sx={{ fontSize: '0.86rem', fontWeight: 600 }}>
                {filtro === 'sin-leer' ? 'Está al día.' : 'Nada por ahora.'}
              </Typography>
              <Typography sx={{ fontSize: '0.76rem', color: 'text.secondary', mt: 0.5, maxWidth: 260, lineHeight: 1.5 }}>
                Acá va a llegar lo que escriban en sus Sesiones y las tareas que le asignen.
              </Typography>
            </Box>
          ) : (
            <AnimatePresence initial={false}>
              {grupos.map(([grupo, avisos]) => (
                <Box key={grupo}>
                  <Typography sx={{
                    px: 2.25, pt: 1.5, pb: 0.5, fontSize: '0.68rem', fontWeight: 600, letterSpacing: '0.07em',
                    textTransform: 'uppercase', color: 'text.disabled',
                  }}>
                    {grupo}
                  </Typography>
                  {avisos.map((n) => <Aviso key={n.ids.join('-')} n={n} onAbrir={abrirUna} />)}
                </Box>
              ))}
            </AnimatePresence>
          )}
        </Box>
      </Popover>
    </>
  );
}
