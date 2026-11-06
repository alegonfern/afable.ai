import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Box, Button, Chip, CircularProgress, Tooltip, Typography } from '@mui/material';
import { api } from '../../services/api';
import { usePantalla } from '../../layout/Dashboard/PanelLateral';
import { BarraQueCrece, Numero } from '../../components/Animado';
import { TONOS } from '../../theme/tonos';

/*
 * Lo vendido según el Registro de Ventas del SII (PMV financiero, 18-10-2026): mes a mes, número
 * de facturas, promedio y de quién depende. Desde el 22-10-2026 es un bloque del Resumen de
 * Ventas (`pages/comercial/ComercialPage`), debajo de cotizaciones y órdenes.
 */

const clp = (n) => (n == null ? '—' : `${n < 0 ? '−' : ''}$${Math.abs(Math.round(Number(n) || 0)).toLocaleString('es-CL')}`);
const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
const SORA = "'Sora', sans-serif";
const NUM = { fontVariantNumeric: 'tabular-nums' };
const pct = (v) => `${String(v).replace('.', ',')}%`;

function Tarjeta({ children, sx }) {
  return <Box sx={{ border: '1px solid', borderColor: 'divider', borderRadius: '14px', bgcolor: 'background.paper', ...sx }}>{children}</Box>;
}
function Etiqueta({ children }) {
  return <Typography sx={{ fontSize: '0.74rem', fontWeight: 600, letterSpacing: '0.07em', textTransform: 'uppercase', color: 'text.secondary' }}>{children}</Typography>;
}

function Resumen({ datos }) {
  const max = Math.max(1, ...datos.meses.map((m) => m.monto));
  const conDatos = datos.meses.filter((m) => m.con_datos);
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr', lg: 'repeat(4, 1fr)' }, gap: 2 }}>
        {[
          // Las cifras suben desde cero al aparecer (components/Animado).
          ['Ventas del año', <Numero valor={datos.total} formato={clp} />, 'Sin IVA, con las notas de crédito restadas.'],
          ['Facturas', <Numero valor={datos.facturas} />, `${conDatos.length} ${conDatos.length === 1 ? 'mes' : 'meses'} con ventas.`],
          ['Promedio por factura', <Numero valor={datos.promedio} formato={clp} />, 'Cuánto vende en cada documento.'],
          ['Su cliente más grande', <Numero valor={datos.concentracion_top1} formato={(x) => pct(Math.round(x * 10) / 10)} />, `Los tres más grandes: ${pct(datos.concentracion_top3)} de lo vendido.`],
        ].map(([t, v, d]) => (
          <Tarjeta key={t} sx={{ p: 2.5 }}>
            <Etiqueta>{t}</Etiqueta>
            <Typography sx={{ fontFamily: SORA, fontWeight: 600, fontSize: '1.6rem', mt: 0.5, ...NUM }}>{v}</Typography>
            <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary', mt: 0.5 }}>{d}</Typography>
          </Tarjeta>
        ))}
      </Box>
      {datos.concentracion_top1 >= 30 && (
        <Box sx={{ px: 1.75, py: 1.25, borderRadius: '10px', bgcolor: '#fbe1d1', color: '#8a5a00', fontSize: '0.86rem' }}>
          Un solo cliente es el {pct(datos.concentracion_top1)} de sus ventas: si se atrasa o se va, se nota en la caja.
        </Box>
      )}
      <Tarjeta sx={{ p: 2.5 }}>
        <Etiqueta>Ventas por mes</Etiqueta>
        <Box sx={{ display: 'flex', alignItems: 'flex-end', gap: 1, height: 170, mt: 2 }}>
          {datos.meses.map((m) => (
            <Tooltip key={m.mes} arrow title={m.con_datos ? `${clp(m.monto)} · ${m.facturas} facturas${m.notas_credito ? ` · ${m.notas_credito} NC` : ''}` : 'Sin ventas cargadas'}>
              <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 0.5, height: '100%', justifyContent: 'flex-end' }}>
                {m.con_datos && <Typography sx={{ fontSize: '0.7rem', color: 'text.secondary', ...NUM }}>{Math.round(m.monto / 1e6 * 10) / 10}M</Typography>}
                <BarraQueCrece i={m.mes} sx={{ width: '100%', borderRadius: '4px 4px 0 0', height: m.con_datos ? `${Math.max(4, (m.monto / max) * 100)}%` : 4,
                  background: m.con_datos ? TONOS.salvia.color : 'rgba(60,45,20,0.07)' }} />
                <Typography sx={{ fontSize: '0.72rem', color: 'text.secondary' }}>{MESES[m.mes - 1]}</Typography>
              </Box>
            </Tooltip>
          ))}
        </Box>
      </Tarjeta>
    </Box>
  );
}

/* Lo vendido según el Registro de Ventas del SII, por año. Va debajo del embudo de cotizaciones
   y órdenes en Ventas › Resumen (22-10-2026). */
export function ResumenVentasSII({ slug }) {
  const navigate = useNavigate();
  const [anio, setAnio] = useState(new Date().getFullYear());
  const [datos, setDatos] = useState(null);
  usePantalla(`año ${anio}`);

  useEffect(() => {
    if (!slug) return;
    api.finanzas.ventas(slug, anio).then(({ data }) => {
      setDatos(data);
      if (!data.total && data.anios.length && !data.anios.includes(anio)) setAnio(data.anios[0]);
    });
  }, [slug, anio]);

  if (!datos) return <CircularProgress size={20} sx={{ m: 'auto' }} />;
  return (
    <>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 1 }}>
        <Typography sx={{ fontFamily: SORA, fontWeight: 600, fontSize: '1.15rem', flex: 1 }}>Lo facturado en {anio}, según el SII</Typography>
        {datos.anios.length > 1 && datos.anios.map((a) => (
          <Chip key={a} label={a} size="small" onClick={() => setAnio(a)} variant={a === anio ? 'filled' : 'outlined'} />
        ))}
      </Box>
      {datos.total === 0 && datos.facturas === 0 ? (
        <Tarjeta sx={{ p: 4, textAlign: 'center' }}>
          <Typography sx={{ color: 'text.secondary', mb: 1.5 }}>Todavía no hay ventas cargadas. Suba el Registro de Ventas del SII en Contabilidad › Documentos.</Typography>
          <Button variant="contained" size="small" onClick={() => navigate('/app/contabilidad/documentos')}>Cargar del SII</Button>
        </Tarjeta>
      ) : <Resumen datos={datos} />}
    </>
  );
}
