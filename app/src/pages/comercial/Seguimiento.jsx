import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box, CircularProgress, Table, TableBody, TableCell, TableHead, TableRow, Tooltip, Typography,
} from '@mui/material';
import { AlertTriangle } from 'lucide-react';
import { api } from '../../services/api';
import { ChipEtapa, Etiqueta, NUM, SORA, Tarjeta, cant, clp, fecha } from './comun';

/*
 * Lo que se sigue después de confirmar (22-10-2026): las entregas o recepciones hechas, lo que
 * falta por facturar (según la política de la empresa) y el resumen del embudo.
 */

export function Entregas({ slug, tipo, modulo }) {
  const navigate = useNavigate();
  const [lista, setLista] = useState(null);
  useEffect(() => { api.comercial.entregas(slug, tipo).then(({ data }) => setLista(data)).catch(() => setLista([])); }, [slug, tipo]);
  const venta = tipo === 'venta';
  if (!lista) return <CircularProgress size={20} sx={{ m: 'auto', mt: 4 }} />;
  if (!lista.length) {
    return (
      <Typography sx={{ textAlign: 'center', py: 8, color: 'text.secondary', fontSize: '0.9rem' }}>
        Todavía no hay {venta ? 'entregas' : 'recepciones'}. Se registran desde la orden de {venta ? 'venta' : 'compra'} confirmada.
      </Typography>
    );
  }
  return (
    <Box sx={{ border: '1px solid', borderColor: 'divider', borderRadius: '12px', overflow: 'auto', bgcolor: 'background.paper' }}>
      <Table size="small" sx={{ '& td, & th': { fontSize: '0.84rem', borderColor: 'divider' } }}>
        <TableHead>
          <TableRow sx={{ '& th': { color: 'text.secondary', fontWeight: 500, bgcolor: 'action.hover', whiteSpace: 'nowrap' } }}>
            <TableCell>Número</TableCell><TableCell>Fecha</TableCell><TableCell>Orden</TableCell>
            <TableCell>{venta ? 'Cliente' : 'Proveedor'}</TableCell><TableCell>Productos</TableCell><TableCell>Guía</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {lista.map((e) => (
            <TableRow key={e.id} hover sx={{ cursor: 'pointer', opacity: e.estado === 'anulada' ? 0.5 : 1 }}
              onClick={() => navigate(`/app/${modulo}/ordenes/${e.pedido}`)}>
              <TableCell sx={{ fontWeight: 500, whiteSpace: 'nowrap' }}>{e.numero}{e.estado === 'anulada' ? ' (anulada)' : ''}</TableCell>
              <TableCell sx={{ whiteSpace: 'nowrap' }}>{fecha(e.fecha)}</TableCell>
              <TableCell>{e.pedido_numero}</TableCell>
              <TableCell>{e.contacto_nombre}</TableCell>
              <TableCell sx={{ color: 'text.secondary' }}>{e.lineas.map((x) => `${cant(x.cantidad)} ${x.unidad} ${x.descripcion}`).join(' · ')}</TableCell>
              <TableCell sx={{ color: 'text.secondary' }}>{e.folio_guia || '—'}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Box>
  );
}

export function PorFacturar({ slug, tipo, modulo }) {
  const navigate = useNavigate();
  const [datos, setDatos] = useState(null);
  useEffect(() => { api.comercial.porFacturar(slug, tipo).then(({ data }) => setDatos(data)).catch(() => setDatos({ politica: 'pedido', pedidos: [] })); }, [slug, tipo]);
  const venta = tipo === 'venta';
  if (!datos) return <CircularProgress size={20} sx={{ m: 'auto', mt: 4 }} />;
  const total = datos.pedidos.reduce((s, p) => s + p.por_facturar_clp, 0);
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
      <Typography sx={{ fontSize: '0.86rem', color: 'text.secondary' }}>
        {venta ? 'Órdenes de venta' : 'Órdenes de compra'} con {datos.politica === 'entregado' ? (venta ? 'lo entregado' : 'lo recibido') : 'lo pedido'} todavía
        sin factura en el SII{venta ? '' : ', o con facturas que no cuadran'}. Al cargar el Registro de {venta ? 'Ventas' : 'Compras'}, las que cuadran se vinculan solas.
        {datos.pedidos.length > 0 && <b> En total: {clp(total)} sin IVA.</b>}
      </Typography>
      {datos.pedidos.length === 0 ? (
        <Typography sx={{ textAlign: 'center', py: 8, color: 'text.secondary', fontSize: '0.9rem' }}>Nada pendiente: todo lo confirmado tiene su factura.</Typography>
      ) : (
        <Box sx={{ border: '1px solid', borderColor: 'divider', borderRadius: '12px', overflow: 'auto', bgcolor: 'background.paper' }}>
          <Table size="small" sx={{ '& td, & th': { fontSize: '0.84rem', borderColor: 'divider', whiteSpace: 'nowrap' } }}>
            <TableHead>
              <TableRow sx={{ '& th': { color: 'text.secondary', fontWeight: 500, bgcolor: 'action.hover' } }}>
                <TableCell>Orden</TableCell><TableCell>Fecha</TableCell><TableCell>{venta ? 'Cliente' : 'Proveedor'}</TableCell>
                <TableCell align="right">Orden (sin IVA)</TableCell><TableCell align="right">{venta ? 'Entregado' : 'Recibido'}</TableCell>
                <TableCell align="right">Facturado</TableCell><TableCell align="right">Por facturar</TableCell><TableCell>Etapa</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {datos.pedidos.map((p) => (
                <TableRow key={p.id} hover sx={{ cursor: 'pointer' }} onClick={() => navigate(`/app/${modulo}/ordenes/${p.id}`)}>
                  <TableCell sx={{ fontWeight: 500 }}>{p.numero}</TableCell>
                  <TableCell>{fecha(p.fecha)}</TableCell>
                  <TableCell>{p.contacto_nombre}</TableCell>
                  <TableCell align="right" sx={NUM}>{clp(p.base_clp)}</TableCell>
                  <TableCell align="right" sx={NUM}>{clp(p.entregado_clp)}</TableCell>
                  <TableCell align="right" sx={NUM}>{clp(p.facturado_clp)}</TableCell>
                  <TableCell align="right" sx={{ ...NUM, fontWeight: 600 }}>
                    {clp(p.por_facturar_clp)}
                    {p.diferencias.length > 0 && (
                      <Tooltip arrow title={p.diferencias.join(' ')}>
                        <AlertTriangle size={14} style={{ color: '#c77700', marginLeft: 6, verticalAlign: -2 }} />
                      </Tooltip>
                    )}
                  </TableCell>
                  <TableCell><ChipEtapa etapa={p.etapa} /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Box>
      )}
    </Box>
  );
}

/* El embudo de cotizaciones a facturas, arriba del Resumen de Ventas o Compras. */
export function Embudo({ slug, tipo, modulo }) {
  const navigate = useNavigate();
  const [r, setR] = useState(null);
  useEffect(() => { api.comercial.resumen(slug, tipo).then(({ data }) => setR(data)).catch(() => {}); }, [slug, tipo]);
  if (!r) return null;
  const venta = tipo === 'venta';
  const tarjetas = [
    [venta ? 'Cotizaciones abiertas' : 'Solicitudes abiertas', r.cotizaciones_abiertas, clp(r.cotizado_clp), 'cotizaciones',
      r.tasa_cierre != null && venta ? `Cierra ${r.tasa_cierre}% de lo que envía.` : 'Sin IVA.'],
    [venta ? 'Por entregar' : 'Por recibir', r.por_entregar, clp(r.por_entregar_clp), 'ordenes', 'De órdenes confirmadas.'],
    ['Por facturar', r.por_facturar, clp(r.por_facturar_clp), 'por-facturar',
      r.con_diferencias ? `${r.con_diferencias} con diferencias.` : 'Sin factura en el SII todavía.'],
    [venta ? 'Vendido este mes' : 'Comprado este mes', r.confirmadas_mes, clp(r.confirmado_mes_clp), 'ordenes', 'Órdenes confirmadas en el mes.'],
  ];
  return (
    <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr', lg: 'repeat(4, 1fr)' }, gap: 2 }}>
      {tarjetas.map(([t, n, monto, ruta, d]) => (
        <Tarjeta key={t} sx={{ p: 2.25, cursor: 'pointer', '&:hover': { borderColor: 'var(--af-color)' } }}>
          <Box onClick={() => navigate(`/app/${modulo}/${ruta}`)}>
            <Etiqueta>{t}</Etiqueta>
            <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1, mt: 0.5 }}>
              <Typography sx={{ fontFamily: SORA, fontWeight: 600, fontSize: '1.5rem', ...NUM }}>{monto}</Typography>
              <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary' }}>· {n}</Typography>
            </Box>
            <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary', mt: 0.25 }}>{d}</Typography>
          </Box>
        </Tarjeta>
      ))}
    </Box>
  );
}
