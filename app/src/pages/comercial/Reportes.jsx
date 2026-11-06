import { useEffect, useState } from 'react';
import {
  Box, Button, CircularProgress, InputBase, Table, TableBody, TableCell, TableHead, TableRow, ToggleButton,
  ToggleButtonGroup, Typography,
} from '@mui/material';
import { Download } from 'lucide-react';
import { api } from '../../services/api';
import { usePantalla } from '../../layout/Dashboard/PanelLateral';
import { Etiqueta, NUM, SORA, Tarjeta, clp, descargar } from './comun';

/*
 * Reportes de Ventas y de Compras (24-10-2026): por producto, por cliente o proveedor y por mes,
 * con las órdenes confirmadas del período. En ventas va el margen, con el costo promedio de lo
 * recibido (o el de la ficha del producto); las líneas sin producto no tienen costo.
 */

const hoy = () => new Date().toISOString().slice(0, 10);
const inicioDeAnio = () => `${new Date().getFullYear()}-01-01`;
const pct = (v) => (v == null ? '—' : `${String(v).replace('.', ',')}%`);
const campoSx = { border: '1px solid', borderColor: 'divider', borderRadius: '8px', px: 1, py: 0.25, fontSize: '0.84rem', bgcolor: 'background.paper' };

export default function Reportes({ slug, tipo }) {
  const venta = tipo === 'venta';
  const [por, setPor] = useState('producto');
  const [desde, setDesde] = useState(inicioDeAnio());
  const [hasta, setHasta] = useState(hoy());
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState(false);
  usePantalla(`reporte de ${venta ? 'ventas' : 'compras'} por ${por}, ${desde} a ${hasta}`);

  useEffect(() => {
    setDatos(null);
    setError(false);
    let vigente = true;      // solo la última consulta pinta (ver ListaPedidos)
    api.comercial.reporte(slug, { tipo, por, desde, hasta })
      .then(({ data }) => { if (vigente) setDatos(data); }).catch(() => { if (vigente) setError(true); });
    return () => { vigente = false; };
  }, [slug, tipo, por, desde, hasta]);

  const quien = venta ? 'cliente' : 'proveedor';
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
        <ToggleButtonGroup size="small" exclusive value={por} onChange={(_, v) => v && setPor(v)}>
          <ToggleButton value="producto" sx={{ textTransform: 'none', px: 1.75 }}>Por producto</ToggleButton>
          <ToggleButton value="contacto" sx={{ textTransform: 'none', px: 1.75 }}>Por {quien}</ToggleButton>
          <ToggleButton value="mes" sx={{ textTransform: 'none', px: 1.75 }}>Por mes</ToggleButton>
        </ToggleButtonGroup>
        <InputBase type="date" value={desde} onChange={(e) => setDesde(e.target.value)} inputProps={{ 'aria-label': 'Desde' }} sx={campoSx} />
        <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary' }}>a</Typography>
        <InputBase type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} inputProps={{ 'aria-label': 'Hasta' }} sx={campoSx} />
        <Box sx={{ flex: 1 }} />
        <Button size="small" variant="outlined" startIcon={<Download size={14} />}
          onClick={() => descargar(api.comercial.exportar(slug, 'reporte', { tipo, por, desde, hasta }), `${venta ? 'Ventas' : 'Compras'} por ${por === 'contacto' ? quien : por}.xlsx`)}>
          Exportar
        </Button>
      </Box>

      {error ? <Typography sx={{ color: 'text.secondary', textAlign: 'center', py: 6 }}>No se pudo armar el reporte. Revise las fechas.</Typography>
        : !datos ? <CircularProgress size={20} sx={{ m: 'auto', mt: 4 }} /> : (
          <>
            <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: venta ? 'repeat(3, 1fr)' : 'repeat(2, 1fr)' }, gap: 2 }}>
              <Tarjeta sx={{ p: 2 }}>
                <Etiqueta>{venta ? 'Vendido' : 'Comprado'} sin IVA</Etiqueta>
                <Typography sx={{ fontFamily: SORA, fontWeight: 600, fontSize: '1.5rem', ...NUM }}>{clp(datos.total.monto)}</Typography>
                <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary' }}>{datos.total.pedidos} órdenes confirmadas.</Typography>
              </Tarjeta>
              {venta && (
                <Tarjeta sx={{ p: 2 }}>
                  <Etiqueta>Margen</Etiqueta>
                  <Typography sx={{ fontFamily: SORA, fontWeight: 600, fontSize: '1.5rem', color: 'var(--af-color)', fontStyle: 'italic', ...NUM }}>
                    {datos.total.margen == null ? '—' : clp(datos.total.margen)}
                  </Typography>
                  <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary' }}>{pct(datos.total.margen_pct)} de lo vendido con costo conocido.</Typography>
                </Tarjeta>
              )}
              <Tarjeta sx={{ p: 2 }}>
                <Etiqueta>{por === 'mes' ? 'Meses' : por === 'producto' ? 'Productos' : `${quien === 'cliente' ? 'Clientes' : 'Proveedores'}`}</Etiqueta>
                <Typography sx={{ fontFamily: SORA, fontWeight: 600, fontSize: '1.5rem' }}>{datos.filas.length}</Typography>
                <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary' }}>En el período.</Typography>
              </Tarjeta>
            </Box>

            {datos.filas.length === 0 ? (
              <Typography sx={{ textAlign: 'center', py: 6, color: 'text.secondary', fontSize: '0.9rem' }}>
                No hay órdenes {venta ? 'de venta' : 'de compra'} confirmadas en el período.
              </Typography>
            ) : (
              <Box sx={{ border: '1px solid', borderColor: 'divider', borderRadius: '12px', overflow: 'auto', bgcolor: 'background.paper' }}>
                <Table size="small" sx={{ '& td, & th': { fontSize: '0.84rem', borderColor: 'divider', whiteSpace: 'nowrap' } }}>
                  <TableHead>
                    <TableRow sx={{ '& th': { color: 'text.secondary', fontWeight: 500, bgcolor: 'action.hover' } }}>
                      <TableCell>{por === 'producto' ? 'Producto' : por === 'mes' ? 'Mes' : (venta ? 'Cliente' : 'Proveedor')}</TableCell>
                      {por === 'producto' && <TableCell align="right">Cantidad</TableCell>}
                      {por !== 'producto' && <TableCell align="right">Órdenes</TableCell>}
                      <TableCell align="right">{venta ? 'Vendido' : 'Comprado'}</TableCell>
                      {venta && <TableCell align="right">Costo</TableCell>}
                      {venta && <TableCell align="right">Margen</TableCell>}
                      {venta && <TableCell align="right">Margen %</TableCell>}
                      {por !== 'mes' && <TableCell align="right">Del total</TableCell>}
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {datos.filas.map((f) => (
                      <TableRow key={f.clave} hover>
                        <TableCell sx={{ fontWeight: 500, maxWidth: 320, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {f.nombre}{f.rut ? <Typography component="span" sx={{ fontSize: '0.74rem', color: 'text.secondary', ml: 0.75 }}>{f.rut}</Typography> : null}
                        </TableCell>
                        {por === 'producto' && <TableCell align="right" sx={NUM}>{String(f.cantidad).replace('.', ',')} {f.unidad}</TableCell>}
                        {por !== 'producto' && <TableCell align="right" sx={NUM}>{f.pedidos}</TableCell>}
                        <TableCell align="right" sx={{ ...NUM, fontWeight: 600 }}>{clp(f.monto)}</TableCell>
                        {venta && <TableCell align="right" sx={NUM}>{f.margen == null ? '—' : clp(f.costo)}</TableCell>}
                        {venta && <TableCell align="right" sx={{ ...NUM, color: f.margen < 0 ? 'error.main' : 'inherit' }}>{f.margen == null ? '—' : clp(f.margen)}</TableCell>}
                        {venta && <TableCell align="right" sx={NUM}>{pct(f.margen_pct)}</TableCell>}
                        {por !== 'mes' && <TableCell align="right" sx={{ ...NUM, color: 'text.secondary' }}>{pct(f.participacion_pct)}</TableCell>}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Box>
            )}
            {venta && datos.filas.some((f) => f.sin_costo) && (
              <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary' }}>
                Las líneas escritas a mano (sin producto del catálogo) no tienen costo: cuentan en lo vendido, no en el margen.
              </Typography>
            )}
          </>
        )}
    </Box>
  );
}
