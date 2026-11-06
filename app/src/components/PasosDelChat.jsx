import { useState } from 'react';
import { Box, Collapse, Typography } from '@mui/material';
import { Check, ChevronDown } from 'lucide-react';
import IsotipoPensando from './IsotipoPensando';
import { Entra } from './Animado';
import { TONOS } from '../theme/tonos';

/*
 * Los pasos que da Afable para responder, a la vista (25-10-2026): "Revisando las ventas…",
 * "Preparando el cambio…", "Emitiendo la factura electrónica…". Mientras trabaja se ven
 * desplegados, el último con el signo girando y los anteriores con su ✓; al terminar quedan
 * plegados en "Hizo N pasos", para ver cómo llegó a la respuesta sin que estorbe.
 * Salen de los estados reales del servidor (agent_service._tool_status), no de un guion.
 */
// "Agente de Ventas · Emitiendo la factura…" → ['Agente de Ventas', 'Emitiendo la factura…'] (25-10-2026).
const partir = (paso) => {
  const i = paso.indexOf(' · ');
  return i > 0 && paso.startsWith('Agente') ? [paso.slice(0, i), paso.slice(i + 3)] : [null, paso];
};

export default function PasosDelChat({ pasos, trabajando = false }) {
  const [abierto, setAbierto] = useState(false);
  if (!pasos?.length) return null;
  const visible = trabajando || abierto;
  // Quién está trabajando ahora: el agente del último paso.
  const [agenteActual] = partir(pasos[pasos.length - 1]);
  const agentes = [...new Set(pasos.map((p) => partir(p)[0]).filter(Boolean))];
  return (
    <Box sx={{ mb: 1.25, maxWidth: 520, border: '1px solid', borderColor: 'divider', borderRadius: '12px',
      bgcolor: 'background.paper', overflow: 'hidden' }}>
      <Box component={trabajando ? 'div' : 'button'} onClick={trabajando ? undefined : () => setAbierto((a) => !a)} sx={{
        display: 'flex', alignItems: 'center', gap: 1, width: '100%', px: 1.5, py: 1, border: 0, bgcolor: 'transparent',
        fontFamily: 'inherit', textAlign: 'left', cursor: trabajando ? 'default' : 'pointer',
        '&:hover': trabajando ? {} : { bgcolor: 'action.hover' },
      }}>
        {trabajando ? <IsotipoPensando size={16} /> : (
          <Box sx={{ width: 16, height: 16, borderRadius: '50%', bgcolor: TONOS.menta.suave, color: TONOS.menta.color,
            display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Check size={11} strokeWidth={3} />
          </Box>
        )}
        <Typography sx={{ flex: 1, fontSize: '0.82rem', color: 'text.secondary' }}>
          {trabajando
            ? (agenteActual ? <><b style={{ color: 'var(--af-color)', fontWeight: 600, fontStyle: 'italic' }}>{agenteActual}</b> trabajando…</> : 'Trabajando…')
            : `${agentes.length ? `${agentes.join(', ')} · ` : ''}${pasos.length} ${pasos.length === 1 ? 'paso' : 'pasos'}`}
        </Typography>
        {!trabajando && (
          <Box component="span" sx={{ display: 'inline-flex', color: 'text.disabled', transition: 'transform .2s',
            transform: abierto ? 'rotate(180deg)' : 'none' }}>
            <ChevronDown size={14} />
          </Box>
        )}
      </Box>
      <Collapse in={visible} timeout={200}>
        <Box component="ol" sx={{ listStyle: 'none', m: 0, px: 1.5, pb: 1.25, pt: 0.25, display: 'flex', flexDirection: 'column', gap: 0.6 }}>
          {pasos.map((paso, i) => {
            const enCurso = trabajando && i === pasos.length - 1;
            return (
              <Entra key={`${i}-${paso}`} component="li" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Box sx={{ width: 16, display: 'flex', justifyContent: 'center', flexShrink: 0 }}>
                  {enCurso ? <IsotipoPensando size={13} /> : <Check size={13} strokeWidth={2.5} color={TONOS.menta.color} />}
                </Box>
                <Typography sx={{ fontSize: '0.8rem', color: enCurso ? 'text.primary' : 'text.secondary' }}>
                  <Box component="span" sx={{ color: 'text.disabled', mr: 0.75, fontVariantNumeric: 'tabular-nums' }}>{i + 1}.</Box>
                  {partir(paso)[0] && <Box component="span" sx={{ fontWeight: 600, color: 'text.primary', mr: 0.5 }}>{partir(paso)[0]}:</Box>}
                  {partir(paso)[1].replace(/…$/, '')}{enCurso ? '…' : ''}
                </Typography>
              </Entra>
            );
          })}
        </Box>
      </Collapse>
    </Box>
  );
}
