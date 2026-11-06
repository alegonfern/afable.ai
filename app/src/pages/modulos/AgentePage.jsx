import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Box, Typography } from '@mui/material';
import { AnimatePresence } from 'framer-motion';
import {
  ArrowRight, Boxes, Calculator, FileText, Landmark, PackageCheck, PackageOpen, Receipt, ShoppingCart, Upload, Wallet, Zap,
} from 'lucide-react';
import PageHeader from '../../components/PageHeader';
import IsotipoPensando from '../../components/IsotipoPensando';
import { EASE, MotionBox } from '../../components/Animado';
import ChatLateral from '../../layout/Dashboard/ChatLateral';
import { MODULOS } from '../../layout/Dashboard/modulos';
import { useWorkspace } from '../../context/WorkspaceContext';
import { api } from '../../services/api';
import AutomatizacionesPage from './AutomatizacionesPage';
import { tonoHecho, tonoModulo } from '../../theme/tonos';

/*
 * La vista "Agente" de un módulo (25-10-2026; antes "Automatización"): el espacio de IA del
 * módulo. A la izquierda, la conversación con su agente —el mismo hilo del panel lateral de ese
 * módulo—; a la derecha, "Lo que hizo hoy" en vivo (finanzas/actividad.py) y sus automatizaciones.
 * Es donde el dueño ve su empresa moverse: cada hecho nuevo entra animado mientras ocurre.
 */

const ICONO_MODULO = { ventas: ShoppingCart, compras: PackageOpen, inventario: Boxes, contabilidad: Calculator, finanzas: Wallet };
const ICONO_HECHO = {
  orden: ShoppingCart, pago: Wallet, entrega: PackageCheck, factura: Receipt, carga: Upload, cartola: Landmark, stock: Boxes,
  automatizacion: Zap,
};
const CADA = 15000;   // cada cuánto se vuelve a mirar si hizo algo nuevo

function Hecho({ h, nuevo }) {
  const navigate = useNavigate();
  const Icono = ICONO_HECHO[h.tipo] || FileText;
  const tono = tonoHecho(h.tipo);
  return (
    <MotionBox
      layout
      initial={{ opacity: 0, y: -10, backgroundColor: nuevo ? 'rgba(11,11,15,0.08)' : 'rgba(11,11,15,0)' }}
      animate={{ opacity: 1, y: 0, backgroundColor: 'rgba(11,11,15,0)' }}
      transition={{ duration: 0.45, ease: EASE, backgroundColor: { duration: 1.6 } }}
      onClick={h.enlace ? () => navigate(h.enlace) : undefined}
      sx={{ display: 'flex', gap: 1.25, px: 1.25, py: 1, mx: -1.25, borderRadius: '10px', cursor: h.enlace ? 'pointer' : 'default',
        '&:hover': h.enlace ? { bgcolor: 'action.hover' } : {} }}>
      <Box sx={{ width: 28, height: 28, borderRadius: '8px', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
        bgcolor: tono.suave, color: tono.color }}>
        <Icono size={14} />
      </Box>
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Typography sx={{ fontSize: '0.84rem', fontWeight: 500, lineHeight: 1.35 }}>{h.titulo}</Typography>
        <Typography sx={{ fontSize: '0.76rem', color: 'text.secondary', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {h.detalle}
        </Typography>
      </Box>
      <Typography sx={{ fontSize: '0.72rem', color: 'text.disabled', fontVariantNumeric: 'tabular-nums', flexShrink: 0 }}>{h.hora}</Typography>
    </MotionBox>
  );
}

function LoQueHizoHoy({ slug, modulo, agente }) {
  const [hechos, setHechos] = useState(null);
  const vistos = useRef(null);
  useEffect(() => {
    let vivo = true;
    const cargar = () => api.finanzas.actividadAgente(slug, modulo)
      .then(({ data }) => { if (vivo) setHechos(data); }).catch(() => { if (vivo) setHechos((h) => h || []); });
    cargar();
    const t = setInterval(cargar, CADA);
    return () => { vivo = false; clearInterval(t); };
  }, [slug, modulo]);
  // Lo que ya estaba al abrir no destella; lo que llega después, sí.
  const claves = (hechos || []).map((h) => `${h.hora}-${h.titulo}`);
  if (hechos && vistos.current === null) vistos.current = new Set(claves);
  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
        <Typography sx={{ fontSize: '0.72rem', fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'text.disabled', flex: 1 }}>
          Lo que hizo hoy
        </Typography>
        <Box sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.6, fontSize: '0.72rem', fontWeight: 500, color: '#0f9d6b' }}>
          <Box sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: '#0f9d6b',
            animation: 'latido 1.4s ease-in-out infinite',
            '@keyframes latido': { '0%,100%': { opacity: 1, transform: 'scale(1)' }, '50%': { opacity: 0.35, transform: 'scale(0.7)' } } }} />
          En vivo
        </Box>
      </Box>
      {hechos === null ? null : hechos.length === 0 ? (
        <Box sx={{ display: 'flex', gap: 1.25, alignItems: 'center', py: 1.5, color: 'text.secondary' }}>
          <IsotipoPensando size={16} />
          <Typography sx={{ fontSize: '0.82rem' }}>El {agente} está atento. Lo que haga hoy aparece aquí.</Typography>
        </Box>
      ) : (
        <AnimatePresence initial={false}>
          {hechos.map((h, i) => (
            <Hecho key={claves[i]} h={h} nuevo={!vistos.current?.has(claves[i])} />
          ))}
        </AnimatePresence>
      )}
    </Box>
  );
}

export default function AgentePage({ modulo }) {
  const navigate = useNavigate();
  const { slug } = useWorkspace();
  const m = MODULOS.find((x) => x.slug === modulo);
  const Icono = ICONO_MODULO[modulo] || ShoppingCart;
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', minWidth: 0, width: '100%' }}>
      <PageHeader title={m.agente} crumbs={[{ label: m.label, to: `/app/${modulo}` }]} back="/app" backLabel="Inicio" />
      <Box sx={{ flex: 1, minHeight: 0, display: 'grid', gridTemplateColumns: { xs: '1fr', lg: 'minmax(0, 1fr) 380px' }, gap: 2.5,
        px: 3, py: 2.5, overflow: { xs: 'auto', lg: 'hidden' } }}>
        {/* La conversación con el agente: el mismo hilo del panel lateral de este módulo. */}
        <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: { xs: 520, lg: 0 }, border: '1px solid', borderColor: 'divider',
          borderRadius: '16px', bgcolor: 'background.paper', overflow: 'hidden' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25, px: 2, py: 1.5, borderBottom: '1px solid', borderColor: 'divider' }}>
            <Box sx={{ position: 'relative', width: 34, height: 34, borderRadius: '10px', display: 'flex', alignItems: 'center',
              justifyContent: 'center', bgcolor: tonoModulo(modulo).suave, color: tonoModulo(modulo).color }}>
              <Icono size={16} />
              <Box sx={{ position: 'absolute', right: -3, bottom: -3, width: 16, height: 16, borderRadius: '50%', bgcolor: 'background.paper',
                display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <IsotipoPensando size={11} girando={false} />
              </Box>
            </Box>
            <Box sx={{ flex: 1 }}>
              <Typography sx={{ fontWeight: 600, fontSize: '0.95rem' }}>{m.agente}</Typography>
              <Typography sx={{ fontSize: '0.76rem', color: 'text.secondary' }}>
                Conoce los datos de {m.label.toLowerCase()}, hace el trabajo que le pida y le pide confirmación antes de cambiar algo.
              </Typography>
            </Box>
          </Box>
          <ChatLateral />
        </Box>

        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3, overflow: { lg: 'auto' }, pr: { lg: 0.5 } }}>
          {slug && <LoQueHizoHoy slug={slug} modulo={modulo} agente={m.agente} />}
          <Box>
            <Typography sx={{ fontSize: '0.72rem', fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'text.disabled', mb: 1 }}>
              Lo que hace solo
            </Typography>
            <AutomatizacionesPage modulo={modulo} embebida />
            <Box component="button" onClick={() => navigate('/app/chat')} sx={{
              mt: 1.25, display: 'inline-flex', alignItems: 'center', gap: 0.5, border: 0, bgcolor: 'transparent', p: 0, cursor: 'pointer',
              fontFamily: 'inherit', fontSize: '0.8rem', fontWeight: 500, color: 'text.secondary', '&:hover': { color: 'text.primary' },
            }}>
              ¿Necesita otra automatización? Pídasela al {m.agente} <ArrowRight size={13} />
            </Box>
          </Box>
        </Box>
      </Box>
    </Box>
  );
}
