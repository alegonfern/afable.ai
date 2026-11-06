import { useEffect, useState } from 'react';
import { Box, Button, CircularProgress, Typography } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { AlertTriangle, CircleSlash, MinusCircle, PackagePlus, ShoppingCart } from 'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../../services/api';
import { NUM, Tarjeta, clp } from '../comercial/comun';
import { conPasos } from '../../components/ProgresoFlotante';
import { Kpi, msg } from './piezas';

/*
 * Inventario › Resumen (26-10-2026): cuánto vale lo que hay, qué está por acabarse, qué está
 * vendido y no alcanza, y qué lleva meses sin moverse. Desde aquí se repone.
 */

const ICONOS_ALERTA = {
  negativo: [MinusCircle, '#c8102e'], sin_stock: [CircleSlash, '#c8102e'],
  comprometido: [ShoppingCart, '#c8102e'], bajo_minimo: [AlertTriangle, '#b45309'],
};

function Reparto({ titulo, filas, total }) {
  if (!filas?.length) return null;
  return (
    <Tarjeta sx={{ p: 2, display: 'grid', gap: 1 }}>
      <Typography sx={{ fontWeight: 600, fontSize: '0.92rem' }}>{titulo}</Typography>
      {filas.map((f) => {
        const pct = total ? Math.round((f.valor / total) * 100) : 0;
        return (
          <Box key={f.nombre} sx={{ display: 'grid', gridTemplateColumns: 'minmax(110px, 1fr) 2fr auto', gap: 1.25, alignItems: 'center', fontSize: '0.82rem' }}>
            <span>{f.nombre}</span>
            <Box sx={{ height: 8, borderRadius: '4px', bgcolor: 'action.hover', overflow: 'hidden' }} title={`${pct}%`}>
              <Box sx={{ width: `${pct}%`, height: '100%', bgcolor: 'var(--af-acento, #5b5fc7)', borderRadius: '4px' }} />
            </Box>
            <Box component="span" sx={{ ...NUM, textAlign: 'right', minWidth: 120 }}>{clp(f.valor)} <Box component="span" sx={{ color: 'text.secondary' }}>· {pct}%</Box></Box>
          </Box>
        );
      })}
    </Tarjeta>
  );
}

export default function Resumen({ slug, esEditor, abrirConfig }) {
  const navigate = useNavigate();
  const [datos, setDatos] = useState(null);
  const [reponiendo, setReponiendo] = useState(false);
  const cargar = () => api.inventario.resumen(slug).then(({ data }) => setDatos(data)).catch((e) => toast.error(msg(e, 'No se pudo leer el inventario.')));
  useEffect(() => { cargar(); }, [slug]); // eslint-disable-line react-hooks/exhaustive-deps

  const reponer = async () => {
    setReponiendo(true);
    try {
      const { data } = await conPasos(['Revisando qué está bajo el mínimo', 'Eligiendo proveedor', 'Armando las solicitudes'], () => api.comercial.reponer(slug));
      const n = data?.solicitudes?.length || 0;
      toast.success(n ? `Armé ${n} solicitud${n === 1 ? '' : 'es'} de compra para reponer. Revíselas en Compras › Solicitudes.` : 'No hay nada nuevo que reponer.');
      if (data?.sin_proveedor?.length) toast.info(`Sin proveedor para: ${data.sin_proveedor.join(', ')}. Asígnele uno en la ficha del producto.`);
      cargar();
    } catch (e) { toast.error(msg(e, 'No se pudo reponer.')); }
    setReponiendo(false);
  };

  if (!datos) return <CircularProgress size={20} />;
  if (datos.nivel === 'ninguno') {
    return (
      <Tarjeta sx={{ p: 4, textAlign: 'center', maxWidth: 560, mx: 'auto', mt: 4 }}>
        <Typography sx={{ fontWeight: 600, mb: 1 }}>El inventario está desactivado</Typography>
        <Typography sx={{ fontSize: '0.88rem', color: 'text.secondary', mb: 2 }}>Actívelo en la configuración de Inventario para llevar stock.</Typography>
        <Button variant="contained" size="small" onClick={abrirConfig}>Abrir configuración</Button>
      </Tarjeta>
    );
  }
  const k = datos.kpis;
  const total = k.valor_total;
  return (
    <Box sx={{ display: 'grid', gap: 2 }}>
      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr 1fr', md: 'repeat(4, 1fr)' }, gap: 1.5 }}>
        <Kpi titulo="Valor del inventario" valor={clp(k.valor_total)} detalle={`${k.con_stock} de ${k.productos} productos con stock`} />
        <Kpi titulo="Sin stock" valor={k.sin_stock} detalle="Productos almacenables en cero" alerta={k.sin_stock > 0} />
        <Kpi titulo="Bajo el mínimo" valor={k.bajo_minimo} detalle={k.comprometido_sin_stock ? `${k.comprometido_sin_stock} con ventas que no alcanzan` : 'Disponible bajo su stock mínimo'} alerta={k.bajo_minimo > 0} />
        <Kpi titulo="Inmovilizado" valor={clp(k.inmovilizado_valor)} detalle={`${k.inmovilizado_productos} productos sin ventas en 90 días`} />
      </Box>

      <Tarjeta sx={{ p: 2, display: 'grid', gap: 1 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
          <Typography sx={{ fontWeight: 600, fontSize: '0.92rem', flex: 1 }}>Lo que necesita atención</Typography>
          {esEditor && (k.bajo_minimo > 0 || k.sin_stock > 0) && (
            <Button size="small" variant="contained" startIcon={<PackagePlus size={14} />} onClick={reponer} disabled={reponiendo}>
              {reponiendo ? 'Armando…' : 'Armar las solicitudes para reponer'}
            </Button>
          )}
        </Box>
        {datos.alertas.length === 0 ? (
          <Typography sx={{ fontSize: '0.85rem', color: 'text.secondary' }}>Todo en orden: nada bajo el mínimo ni comprometido sin stock.</Typography>
        ) : datos.alertas.slice(0, 12).map((a) => {
          const [Icono, color] = ICONOS_ALERTA[a.tipo] || ICONOS_ALERTA.bajo_minimo;
          return (
            <Box key={`${a.tipo}-${a.producto_id}`} sx={{ display: 'flex', gap: 1, alignItems: 'baseline', fontSize: '0.85rem', cursor: 'pointer',
              '&:hover b': { textDecoration: 'underline' } }} onClick={() => navigate(`/app/inventario/stock?producto=${a.producto_id}`)}>
              <Icono size={14} color={color} style={{ flexShrink: 0, alignSelf: 'center' }} />
              <b style={{ fontWeight: 500 }}>{a.nombre}</b>
              <Box component="span" sx={{ color: 'text.secondary' }}>{a.detalle}</Box>
            </Box>
          );
        })}
        {datos.alertas.length > 12 && (
          <Button size="small" sx={{ justifySelf: 'start' }} onClick={() => navigate('/app/inventario/stock')}>Ver los {datos.alertas.length} en Stock</Button>
        )}
      </Tarjeta>

      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 1.5 }}>
        <Reparto titulo="Valor por familia" total={total} filas={(datos.por_familia || []).map((f) => ({ nombre: f.familia || 'Sin familia', valor: f.valor }))} />
        {datos.por_bodega?.length > 1 && (
          <Reparto titulo="Valor por bodega" total={total} filas={datos.por_bodega.map((b) => ({ nombre: b.nombre, valor: b.valor }))} />
        )}
      </Box>
    </Box>
  );
}
