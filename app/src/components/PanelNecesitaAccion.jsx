import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Box, Skeleton, Typography } from '@mui/material';
import { Check } from 'lucide-react';
import { Numero } from './Animado';
import { api } from '../services/api';

/*
 * El panel de la derecha del chat (25-10-2026), el mismo de la animación de la landing:
 * "Necesita acción" (lo que espera a alguien) y "Caja" (cómo está la plata), con los datos
 * reales de la empresa. Cada fila lleva a la pantalla donde se resuelve. Lo que falla en
 * cargar no se muestra: un cero inventado se leería como "no hay nada pendiente".
 */

const pesos = (v) => `$${Math.round(v).toLocaleString('es-CL')}`;

async function cargar(slug) {
  const [venta, compra, cuadre, caja, cobrar, pagar] = await Promise.allSettled([
    api.comercial.resumen(slug, 'venta'),
    api.comercial.resumen(slug, 'compra'),
    api.finanzas.cuadre(slug),
    api.finanzas.caja(slug),
    api.finanzas.cuentasPor(slug, 'cobrar'),
    api.finanzas.cuentasPor(slug, 'pagar'),
  ]);
  const de = (r) => (r.status === 'fulfilled' ? r.value.data : null);
  return { venta: de(venta), compra: de(compra), cuadre: de(cuadre), caja: de(caja), cobrar: de(cobrar), pagar: de(pagar) };
}

function Fila({ etiqueta, valor, formato, enlace, ok }) {
  const navigate = useNavigate();
  if (valor == null) return null;
  const listo = ok && Number(valor) === 0;
  return (
    <Box onClick={() => navigate(enlace)} sx={{
      display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 1.5, py: 0.8, px: 1, mx: -1,
      borderRadius: '8px', cursor: 'pointer', '&:hover': { bgcolor: 'action.hover' },
    }}>
      <Typography sx={{ fontSize: '0.84rem', color: 'text.secondary' }}>{etiqueta}</Typography>
      <Typography component="b" sx={{ fontSize: '0.88rem', fontWeight: 600, fontVariantNumeric: 'tabular-nums',
        color: listo ? '#0f9d6b' : 'text.primary', display: 'inline-flex', alignItems: 'center', gap: 0.4 }}>
        {listo && <Check size={13} strokeWidth={3} />}
        <Numero valor={valor} formato={formato} />
      </Typography>
    </Box>
  );
}

function Titulo({ children, sep }) {
  return (
    <Typography sx={{ fontSize: '0.7rem', fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase',
      color: 'text.disabled', mb: 0.5, mt: sep ? 3 : 0 }}>
      {children}
    </Typography>
  );
}

export default function PanelNecesitaAccion({ slug, refresco }) {
  const [datos, setDatos] = useState(null);

  // Se vuelve a pedir después de cada respuesta del chat: si Afable confirmó una orden o
  // registró un pago, el panel tiene que mostrarlo sin recargar.
  useEffect(() => {
    let vivo = true;
    if (!slug) return undefined;
    cargar(slug).then((d) => { if (vivo) setDatos(d); });
    return () => { vivo = false; };
  }, [slug, refresco]);

  const conteo = (n) => Math.round(n).toLocaleString('es-CL');
  const { venta, compra, cuadre, caja, cobrar, pagar } = datos || {};

  return (
    <Box component="aside" sx={{
      width: 300, flexShrink: 0, borderLeft: '1px solid', borderColor: 'divider', px: 2.5, py: 3, overflowY: 'auto',
      display: { xs: 'none', lg: 'block' },
    }}>
      <Titulo>Necesita acción</Titulo>
      {!datos ? (
        [0, 1, 2].map((i) => <Skeleton key={i} height={30} />)
      ) : (
        <>
          <Fila etiqueta="Movimientos por conciliar" valor={cuadre?.pendientes} formato={conteo} ok enlace="/app/contabilidad/conciliacion" />
          <Fila etiqueta="Ventas por facturar" valor={venta?.por_facturar} formato={conteo} ok enlace="/app/ventas/por-facturar" />
          <Fila etiqueta="Ventas por entregar" valor={venta?.por_entregar} formato={conteo} ok enlace="/app/ventas/entregas" />
          <Fila etiqueta="Solicitudes de compra abiertas" valor={compra?.cotizaciones_abiertas} formato={conteo} ok enlace="/app/compras/cotizaciones" />
        </>
      )}

      <Titulo sep>Caja</Titulo>
      {!datos ? (
        [0, 1, 2].map((i) => <Skeleton key={i} height={30} />)
      ) : (
        <>
          <Fila etiqueta="Saldo en bancos" valor={caja?.disponible} formato={pesos} enlace="/app/finanzas/caja" />
          <Fila etiqueta="Por cobrar" valor={cobrar?.total} formato={pesos} enlace="/app/finanzas/por-cobrar" />
          <Fila etiqueta="Por pagar" valor={pagar?.total} formato={pesos} enlace="/app/finanzas/por-pagar" />
          {caja?.saldo_30_dias != null && (
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', pt: 1.5, mt: 1,
              borderTop: '1px solid', borderColor: 'divider' }}>
              <Typography sx={{ fontSize: '0.84rem', color: 'text.secondary' }}>En 30 días</Typography>
              <Typography sx={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--af-color)', fontStyle: 'italic', fontVariantNumeric: 'tabular-nums' }}>
                <Numero valor={caja.saldo_30_dias} formato={pesos} duracion={0.8} />
              </Typography>
            </Box>
          )}
        </>
      )}
    </Box>
  );
}
