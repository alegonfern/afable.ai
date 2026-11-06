import { useCallback, useEffect, useState } from 'react';
import {
  Box, Button, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, IconButton, InputBase, Menu, MenuItem,
  Select, Table, TableBody, TableCell, TableHead, TableRow, Tooltip, Typography,
} from '@mui/material';
import { Download, History, MoreHorizontal, PackagePlus, Search, Upload } from 'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../../services/api';
import { NUM, Tarjeta, cant, clp, descargar } from '../comercial/comun';
import { DialogoKardex, DialogoMovimiento, ESTADOS_STOCK, EstadoStock, msg } from './piezas';

/*
 * Inventario › Stock (26-10-2026): cada producto con lo que hay (físico), lo comprometido en
 * órdenes de venta, lo disponible para vender, lo que viene en órdenes de compra y lo proyectado.
 * Desde cada fila: entrada, salida, ajuste al conteo, traspaso y su kardex.
 */

function DialogoInicial({ slug, onCerrar, onHecho }) {
  const [archivo, setArchivo] = useState(null);
  const [resultado, setResultado] = useState(null);
  const [subiendo, setSubiendo] = useState(false);
  const subir = async () => {
    setSubiendo(true);
    try {
      const { data } = await api.inventario.importarInicial(slug, archivo);
      setResultado(data);
      if (data.creados) onHecho();
    } catch (e) { toast.error(msg(e, 'No se pudo leer el archivo.')); }
    setSubiendo(false);
  };
  return (
    <Dialog open onClose={onCerrar} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ fontWeight: 600 }}>Cargar el stock inicial</DialogTitle>
      <DialogContent sx={{ display: 'grid', gap: 1.5 }}>
        <Typography sx={{ fontSize: '0.86rem', color: 'text.secondary', lineHeight: 1.6 }}>
          Para partir: una planilla con el código (o el nombre) de cada producto, la cantidad y su costo unitario sin IVA.
          Si lleva varias bodegas, una columna con la bodega. Cada fila queda como «Stock inicial» en el kardex.
        </Typography>
        <Box>
          <Button size="small" startIcon={<Download size={14} />} onClick={() => descargar(api.inventario.plantillaInicial(slug), 'Plantilla stock inicial.xlsx')}>
            Descargar la plantilla
          </Button>
        </Box>
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
          <Button component="label" size="small" variant="outlined" startIcon={<Upload size={14} />}>
            {archivo ? archivo.name : 'Elegir planilla (.xlsx o .csv)'}
            <input hidden type="file" accept=".xlsx,.csv" onChange={(e) => { setArchivo(e.target.files?.[0] || null); setResultado(null); }} />
          </Button>
        </Box>
        {resultado && (
          <Box sx={{ fontSize: '0.84rem' }}>
            <Typography sx={{ fontSize: '0.86rem', fontWeight: 600 }}>{resultado.creados} producto{resultado.creados === 1 ? '' : 's'} con stock inicial.</Typography>
            {resultado.errores?.length > 0 && (
              <Box component="ul" sx={{ m: 0, pl: 2.5, color: '#b45309' }}>
                {resultado.errores.slice(0, 20).map((e) => <li key={`${e.fila}-${e.error}`}>Fila {e.fila}: {e.error}</li>)}
              </Box>
            )}
          </Box>
        )}
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onCerrar}>Cerrar</Button>
        <Button variant="contained" disabled={!archivo || subiendo} onClick={subir}>{subiendo ? 'Cargando…' : 'Cargar'}</Button>
      </DialogActions>
    </Dialog>
  );
}

function Num({ v, fuerte, alerta, vacio = '0' }) {
  const n = Number(v);
  return (
    <TableCell align="right" sx={{ ...NUM, fontWeight: fuerte ? 600 : 400, color: alerta && n < 0 ? '#c8102e' : n === 0 ? 'text.disabled' : 'text.primary' }}>
      {v == null ? '—' : n === 0 ? vacio : cant(v)}
    </TableCell>
  );
}

export default function Stock({ slug, esEditor, abrirConfig }) {
  const [filtro, setFiltro] = useState({ q: '', bodega: '', familia: '', estado: '' });
  const [datos, setDatos] = useState(null);
  const [menu, setMenu] = useState(null);
  const [dialogo, setDialogo] = useState(null);
  const [kardex, setKardex] = useState(null);
  const [inicial, setInicial] = useState(false);

  const cargar = useCallback(() => {
    const params = Object.fromEntries(Object.entries(filtro).filter(([, v]) => v));
    api.inventario.stock(slug, params).then(({ data }) => setDatos(data)).catch((e) => toast.error(msg(e, 'No se pudo leer el stock.')));
  }, [slug, filtro]);
  useEffect(() => { const t = setTimeout(cargar, filtro.q ? 250 : 0); return () => clearTimeout(t); }, [cargar, filtro.q]);

  if (!datos) return <CircularProgress size={20} />;
  if (datos.nivel === 'ninguno') {
    return (
      <Tarjeta sx={{ p: 4, textAlign: 'center', maxWidth: 560, mx: 'auto', mt: 4 }}>
        <Typography sx={{ fontWeight: 600, mb: 1 }}>El inventario está desactivado</Typography>
        <Typography sx={{ fontSize: '0.88rem', color: 'text.secondary', mb: 2, lineHeight: 1.6 }}>
          Hoy se registra lo entregado y lo recibido, sin llevar stock. Active el inventario básico (stock por producto) o el
          completo (por bodega, con traspasos) en la configuración de Inventario.
        </Typography>
        <Button variant="contained" size="small" onClick={abrirConfig}>Abrir configuración</Button>
      </Tarjeta>
    );
  }
  const varias = datos.bodegas.length > 1;
  const motivos = { entrada: datos.motivos_entrada, salida: datos.motivos_salida };
  const accion = (modo) => { setDialogo({ modo, producto: menu.producto }); setMenu(null); };
  const campo = { border: '1px solid', borderColor: 'divider', borderRadius: '8px', px: 1.25, py: 0.3, fontSize: '0.85rem', bgcolor: 'background.paper' };

  return (
    <Box sx={{ display: 'grid', gap: 1.5 }}>
      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', alignItems: 'center' }}>
        <InputBase placeholder="Buscar por nombre, código o código de barras" value={filtro.q}
          onChange={(e) => setFiltro((f) => ({ ...f, q: e.target.value }))}
          startAdornment={<Search size={14} style={{ marginRight: 6, opacity: 0.5 }} />} sx={{ ...campo, minWidth: 280, flex: '1 1 280px', maxWidth: 420 }} />
        {varias && (
          <Select size="small" displayEmpty value={filtro.bodega} onChange={(e) => setFiltro((f) => ({ ...f, bodega: e.target.value }))} sx={{ fontSize: '0.84rem', minWidth: 160 }}>
            <MenuItem value="">Todas las bodegas</MenuItem>
            {datos.bodegas.map((b) => <MenuItem key={b.id} value={b.id}>{b.nombre}</MenuItem>)}
          </Select>
        )}
        {datos.familias.length > 0 && (
          <Select size="small" displayEmpty value={filtro.familia} onChange={(e) => setFiltro((f) => ({ ...f, familia: e.target.value }))} sx={{ fontSize: '0.84rem', minWidth: 160 }}>
            <MenuItem value="">Todas las familias</MenuItem>
            {datos.familias.map((x) => <MenuItem key={x} value={x}>{x}</MenuItem>)}
          </Select>
        )}
        <Select size="small" displayEmpty value={filtro.estado} onChange={(e) => setFiltro((f) => ({ ...f, estado: e.target.value }))} sx={{ fontSize: '0.84rem', minWidth: 160 }}>
          <MenuItem value="">Todos los estados</MenuItem>
          {ESTADOS_STOCK.map((x) => <MenuItem key={x.valor} value={x.valor}>{x.nombre}</MenuItem>)}
        </Select>
        <Box sx={{ flex: 1 }} />
        <Button size="small" startIcon={<Download size={14} />} onClick={() => descargar(api.inventario.exportar(slug, 'stock', filtro.bodega ? { bodega: filtro.bodega } : {}), 'Stock.xlsx')}>Excel</Button>
        {esEditor && <Button size="small" variant="outlined" startIcon={<PackagePlus size={14} />} onClick={() => setInicial(true)}>Stock inicial</Button>}
      </Box>

      <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary' }}>
        {datos.totales.productos} producto{datos.totales.productos === 1 ? '' : 's'} · valor {clp(datos.totales.valor)} al costo promedio, sin IVA.
        {' '}<b>Disponible</b> = físico − comprometido en órdenes de venta · <b>Proyectado</b> = disponible + por recibir.
      </Typography>

      {datos.productos.length === 0 ? (
        <Tarjeta sx={{ p: 4, textAlign: 'center', color: 'text.secondary', fontSize: '0.88rem' }}>
          No hay productos almacenables {filtro.q || filtro.familia || filtro.estado ? 'con ese filtro' : 'todavía. Créelos en Ventas o Compras › Productos, con el tipo «Almacenable»'}.
        </Tarjeta>
      ) : (
        <Tarjeta sx={{ overflowX: 'auto' }}>
          <Table size="small" sx={{ '& td, & th': { fontSize: '0.82rem', whiteSpace: 'nowrap', px: 1.25 }, '& th': { color: 'text.secondary', fontWeight: 500 } }}>
            <TableHead>
              <TableRow>
                <TableCell>Producto</TableCell>
                <TableCell>Estado</TableCell>
                <TableCell align="right">Físico</TableCell>
                <TableCell align="right">
                  <Tooltip title="En órdenes de venta confirmadas, todavía sin entregar"><span>Comprometido</span></Tooltip></TableCell>
                <TableCell align="right">Disponible</TableCell>
                <TableCell align="right"><Tooltip title="En órdenes de compra confirmadas, todavía sin recibir"><span>Por recibir</span></Tooltip></TableCell>
                <TableCell align="right">Proyectado</TableCell>
                <TableCell align="right">Mín / máx</TableCell>
                <TableCell align="right">Costo prom.</TableCell>
                <TableCell align="right">Valor</TableCell>
                <TableCell />
              </TableRow>
            </TableHead>
            <TableBody>
              {datos.productos.map((p) => (
                <TableRow key={p.id} hover>
                  <TableCell sx={{ maxWidth: 240 }}>
                    <Box sx={{ fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis' }}>{p.nombre}</Box>
                    <Typography component="span" sx={{ fontSize: '0.72rem', color: 'text.secondary' }}>
                      {[p.codigo, p.familia, p.ubicacion && `Ubic. ${p.ubicacion}`].filter(Boolean).join(' · ') || p.unidad}
                    </Typography>
                    {varias && !filtro.bodega && p.por_bodega?.length > 1 && (
                      <Typography component="span" sx={{ display: 'block', fontSize: '0.72rem', color: 'text.secondary' }}>
                        {p.por_bodega.filter((b) => Number(b.cantidad)).map((b) => `${b.nombre}: ${cant(b.cantidad)}`).join(' · ')}
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell><EstadoStock estado={p.estado} /></TableCell>
                  <Num v={p.fisico} fuerte alerta />
                  <Num v={p.reservado} vacio="—" />
                  <Num v={p.disponible} fuerte alerta />
                  <Num v={p.por_recibir} vacio="—" />
                  <Num v={p.proyectado} alerta />
                  <TableCell align="right" sx={{ ...NUM, color: 'text.secondary' }}>
                    {Number(p.stock_minimo) || Number(p.stock_maximo) ? `${cant(p.stock_minimo)} / ${Number(p.stock_maximo) ? cant(p.stock_maximo) : '—'}` : '—'}
                  </TableCell>
                  <TableCell align="right" sx={NUM}>{clp(p.costo_promedio)}</TableCell>
                  <TableCell align="right" sx={{ ...NUM, fontWeight: 500 }}>{clp(p.valor)}</TableCell>
                  <TableCell align="right">
                    <Tooltip title="Kardex"><IconButton size="small" onClick={() => setKardex(p)}><History size={15} /></IconButton></Tooltip>
                    {esEditor && (
                      <IconButton size="small" aria-label={`Acciones de ${p.nombre}`} onClick={(e) => setMenu({ el: e.currentTarget, producto: p })}><MoreHorizontal size={15} /></IconButton>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Tarjeta>
      )}

      <Menu anchorEl={menu?.el} open={Boolean(menu)} onClose={() => setMenu(null)}>
        <MenuItem onClick={() => accion('entrada')} sx={{ fontSize: '0.86rem' }}>Entrada (producción, stock inicial…)</MenuItem>
        <MenuItem onClick={() => accion('salida')} sx={{ fontSize: '0.86rem' }}>Salida (merma, consumo, muestra…)</MenuItem>
        <MenuItem onClick={() => accion('ajuste')} sx={{ fontSize: '0.86rem' }}>Ajustar a lo contado</MenuItem>
        {varias && <MenuItem onClick={() => accion('traspaso')} sx={{ fontSize: '0.86rem' }}>Traspasar entre bodegas</MenuItem>}
      </Menu>
      {dialogo && (
        <DialogoMovimiento slug={slug} modo={dialogo.modo} producto={dialogo.producto} bodegas={datos.bodegas} motivos={motivos}
          onCerrar={() => setDialogo(null)} onHecho={() => { setDialogo(null); cargar(); }} />
      )}
      {kardex && <DialogoKardex slug={slug} producto={kardex} bodegas={datos.bodegas} onCerrar={() => setKardex(null)} />}
      {inicial && <DialogoInicial slug={slug} onCerrar={() => setInicial(false)} onHecho={cargar} />}
    </Box>
  );
}
