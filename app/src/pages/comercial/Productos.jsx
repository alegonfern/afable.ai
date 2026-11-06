import { useCallback, useEffect, useState } from 'react';
import {
  Box, Button, Checkbox, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, FormControlLabel,
  IconButton, InputBase, MenuItem, Table, TableBody, TableCell, TableHead, TableRow, TextField, Tooltip, Typography,
} from '@mui/material';
import { Download, Plus, Search, Star, Upload, X } from 'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../../services/api';
import { BuscadorContacto, DialogoImportar, NUM, aNumero, cant, clp, descargar } from './comun';

/* Los precios de un producto para clientes puntuales (ventas) y de cada proveedor (compras). Se
   proponen solos al agregarlo a una línea de ese contacto; el proveedor preferido (o el más
   barato) es al que se le pide al reponer stock. */
function PreciosDelProducto({ slug, producto, esEditor }) {
  const [lista, setLista] = useState(null);
  const [nuevo, setNuevo] = useState({ venta: { contacto: null, precio: '' }, compra: { contacto: null, precio: '', preferido: false } });
  const cargar = useCallback(() => {
    api.comercial.precios(slug, { producto: producto.id }).then(({ data }) => setLista(data)).catch(() => setLista([]));
  }, [slug, producto.id]);
  useEffect(() => { cargar(); }, [cargar]);
  const agregar = async (tipo) => {
    const n = nuevo[tipo];
    try {
      await api.comercial.guardarPrecio(slug, { producto: producto.id, contacto: n.contacto, tipo, precio: aNumero(n.precio), preferido: n.preferido });
      setNuevo((x) => ({ ...x, [tipo]: { contacto: null, precio: '', preferido: false } }));
      cargar();
    } catch (e) { toast.error(e.response?.data?.detail || 'No se pudo guardar.'); }
  };
  const borrar = async (id) => {
    try { await api.comercial.borrarPrecio(slug, id); cargar(); } catch { toast.error('No se pudo borrar.'); }
  };
  const preferir = async (x) => {
    try { await api.comercial.guardarPrecio(slug, { producto: producto.id, contacto: x.contacto, tipo: 'compra', precio: x.precio, preferido: true }); cargar(); }
    catch { toast.error('No se pudo guardar.'); }
  };
  if (!lista) return <CircularProgress size={16} />;
  const grupo = (tipo, titulo, ayuda) => (
    <Box sx={{ mt: 2 }}>
      <Typography sx={{ fontWeight: 600, fontSize: '0.9rem' }}>{titulo}</Typography>
      <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary', mb: 0.75 }}>{ayuda}</Typography>
      {lista.filter((x) => x.tipo === tipo).map((x) => (
        <Box key={x.id} sx={{ display: 'flex', alignItems: 'center', gap: 1, py: 0.5, borderTop: '1px solid', borderColor: 'divider' }}>
          {tipo === 'compra' && (
            <Tooltip arrow title={x.preferido ? 'Proveedor preferido: a él se le pide al reponer' : 'Marcar como preferido'}>
              <IconButton size="small" disabled={!esEditor || x.preferido} onClick={() => preferir(x)} aria-label={`Preferir a ${x.contacto_nombre}`}>
                <Star size={14} fill={x.preferido ? 'currentColor' : 'none'} color={x.preferido ? '#c99a00' : undefined} />
              </IconButton>
            </Tooltip>
          )}
          <Typography sx={{ fontSize: '0.86rem', flex: 1 }}>{x.contacto_nombre}</Typography>
          <Typography sx={{ fontSize: '0.86rem', ...NUM }}>{clp(x.precio)}</Typography>
          {esEditor && <IconButton size="small" onClick={() => borrar(x.id)} aria-label={`Quitar el precio de ${x.contacto_nombre}`}><X size={14} /></IconButton>}
        </Box>
      ))}
      {esEditor && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.75, flexWrap: 'wrap' }}>
          <Box sx={{ flex: 1, minWidth: 200 }}>
            <BuscadorContacto slug={slug} rol={tipo === 'venta' ? 'cliente' : 'proveedor'} value={nuevo[tipo].contacto}
              onChange={(v) => setNuevo((x) => ({ ...x, [tipo]: { ...x[tipo], contacto: v } }))} />
          </Box>
          <TextField size="small" label="Precio sin IVA" value={nuevo[tipo].precio} sx={{ width: 140 }}
            onChange={(e) => setNuevo((x) => ({ ...x, [tipo]: { ...x[tipo], precio: e.target.value.replace(/[^\d,]/g, '') } }))} />
          <Button size="small" variant="outlined" disabled={!nuevo[tipo].contacto || !nuevo[tipo].precio} onClick={() => agregar(tipo)}>Agregar</Button>
        </Box>
      )}
    </Box>
  );
  return (
    <>
      {producto.se_vende && grupo('venta', 'Precios especiales por cliente', 'Si un cliente tiene precio propio, es el que se propone en sus cotizaciones.')}
      {producto.se_compra && grupo('compra', 'Proveedores', 'El precio de cada proveedor se propone en sus solicitudes. La estrella marca a quién se le pide al reponer stock.')}
    </>
  );
}

/*
 * Los productos y servicios (22-10-2026). Como en Odoo, cada uno es almacenable (lleva stock),
 * consumible o servicio; el precio de venta y el costo se proponen solos en las líneas.
 */

const TIPOS = { almacenable: 'Almacenable', consumible: 'Consumible', servicio: 'Servicio' };

export function FichaProducto({ slug, producto, esEditor, categorias, onCerrar, onGuardado }) {
  const [p, setP] = useState(producto ? {
    ...producto, precio_venta: cant(producto.precio_venta), costo: cant(producto.costo), stock_minimo: cant(producto.stock_minimo),
    cantidad_reorden: Number(producto.cantidad_reorden) ? cant(producto.cantidad_reorden) : '',
    stock_maximo: Number(producto.stock_maximo) ? cant(producto.stock_maximo) : '',
    familia: producto.familia || '', codigo_barras: producto.codigo_barras || '', ubicacion: producto.ubicacion || '',
  } : { nombre: '', codigo: '', tipo: 'almacenable', unidad: 'un', precio_venta: '', costo: '', stock_minimo: '', cantidad_reorden: '', stock_maximo: '', familia: '', codigo_barras: '', ubicacion: '', exento: false, se_vende: true, se_compra: true, descripcion: '', categoria_venta: '', categoria_compra: '' });
  const [guardando, setGuardando] = useState(false);
  const cambiar = (k, v) => setP((x) => ({ ...x, [k]: v }));
  const guardar = async () => {
    setGuardando(true);
    const datos = {
      ...p, precio_venta: aNumero(p.precio_venta) || '0', costo: aNumero(p.costo) || '0', stock_minimo: aNumero(p.stock_minimo) || '0',
      cantidad_reorden: aNumero(p.cantidad_reorden) || '0', stock_maximo: aNumero(p.stock_maximo) || '0',
      categoria_venta: p.categoria_venta || null, categoria_compra: p.categoria_compra || null,
    };
    try {
      const { data } = producto ? await api.comercial.actualizarProducto(slug, producto.id, datos) : await api.comercial.crearProducto(slug, datos);
      toast.success('Guardado.');
      onGuardado(data);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'No se pudo guardar.');
      setGuardando(false);
    }
  };
  const num = (k, etiqueta) => (
    <TextField size="small" label={etiqueta} value={p[k]} disabled={!esEditor} onChange={(e) => cambiar(k, e.target.value.replace(/[^\d,]/g, ''))} />
  );
  return (
    <Dialog open onClose={onCerrar} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ fontWeight: 600 }}>{producto ? producto.nombre : 'Nuevo producto'}</DialogTitle>
      <DialogContent>
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '2fr 1fr' }, gap: 1.5, mt: 1 }}>
          <TextField size="small" label="Nombre" value={p.nombre} disabled={!esEditor} onChange={(e) => cambiar('nombre', e.target.value)} autoFocus={!producto} />
          <TextField size="small" label="Código (opcional)" value={p.codigo} disabled={!esEditor} onChange={(e) => cambiar('codigo', e.target.value)} />
          <TextField size="small" select label="Tipo" value={p.tipo} disabled={!esEditor} onChange={(e) => cambiar('tipo', e.target.value)}
            helperText={p.tipo === 'almacenable' ? 'Lleva stock en bodega.' : p.tipo === 'consumible' ? 'Se compra y se usa, sin stock.' : 'No es físico.'}>
            {Object.entries(TIPOS).map(([v, n]) => <MenuItem key={v} value={v}>{n}</MenuItem>)}
          </TextField>
          <TextField size="small" label="Unidad" value={p.unidad} disabled={!esEditor} onChange={(e) => cambiar('unidad', e.target.value)} placeholder="un, kg, m, hr" />
          {num('precio_venta', 'Precio de venta (sin IVA)')}
          {num('costo', 'Costo (sin IVA)')}
          {p.tipo === 'almacenable' && num('stock_minimo', 'Stock mínimo')}
          {p.tipo === 'almacenable' && num('cantidad_reorden', 'Cuánto pedir al reponer')}
          {p.tipo === 'almacenable' && num('stock_maximo', 'Stock máximo (opcional)')}
          <TextField size="small" label="Familia (opcional)" value={p.familia} disabled={!esEditor} onChange={(e) => cambiar('familia', e.target.value)} placeholder="Ej: Cementos, Fierros" />
          <TextField size="small" label="Código de barras (opcional)" value={p.codigo_barras} disabled={!esEditor} onChange={(e) => cambiar('codigo_barras', e.target.value)} />
          {p.tipo === 'almacenable' && (
            <TextField size="small" label="Ubicación en bodega (opcional)" value={p.ubicacion} disabled={!esEditor} onChange={(e) => cambiar('ubicacion', e.target.value)} placeholder="Ej: Pasillo 3, estante B" />
          )}
          <TextField size="small" select label="Categoría al venderlo" value={p.categoria_venta || ''} disabled={!esEditor} onChange={(e) => cambiar('categoria_venta', e.target.value)}>
            <MenuItem value=""><em>Ninguna</em></MenuItem>
            {categorias.filter((c) => c.tipo === 'ingreso').map((c) => <MenuItem key={c.id} value={c.id}>{c.nombre}</MenuItem>)}
          </TextField>
          <TextField size="small" select label="Categoría al comprarlo" value={p.categoria_compra || ''} disabled={!esEditor} onChange={(e) => cambiar('categoria_compra', e.target.value)}>
            <MenuItem value=""><em>Ninguna</em></MenuItem>
            {categorias.filter((c) => c.tipo === 'gasto').map((c) => <MenuItem key={c.id} value={c.id}>{c.nombre}</MenuItem>)}
          </TextField>
        </Box>
        <TextField size="small" label="Descripción" multiline minRows={2} fullWidth value={p.descripcion} disabled={!esEditor} onChange={(e) => cambiar('descripcion', e.target.value)} sx={{ mt: 1.5 }} />
        <Box sx={{ display: 'flex', gap: 2, mt: 1, flexWrap: 'wrap' }}>
          <FormControlLabel control={<Checkbox size="small" checked={p.se_vende} disabled={!esEditor} onChange={(e) => cambiar('se_vende', e.target.checked)} />} label="Se vende" />
          <FormControlLabel control={<Checkbox size="small" checked={p.se_compra} disabled={!esEditor} onChange={(e) => cambiar('se_compra', e.target.checked)} />} label="Se compra" />
          <FormControlLabel control={<Checkbox size="small" checked={p.exento} disabled={!esEditor} onChange={(e) => cambiar('exento', e.target.checked)} />} label="Exento de IVA" />
          {producto && <FormControlLabel control={<Checkbox size="small" checked={p.activo} disabled={!esEditor} onChange={(e) => cambiar('activo', e.target.checked)} />} label="Activo" />}
        </Box>
        {producto ? <PreciosDelProducto slug={slug} producto={producto} esEditor={esEditor} /> : (
          <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary', mt: 1 }}>Después de guardarlo puede agregarle precios por cliente y proveedores.</Typography>
        )}
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onCerrar}>{esEditor ? 'Cancelar' : 'Cerrar'}</Button>
        {esEditor && <Button variant="contained" onClick={guardar} disabled={guardando || !p.nombre.trim()}>Guardar</Button>}
      </DialogActions>
    </Dialog>
  );
}

export default function Productos({ slug, esEditor, conInventario }) {
  const [lista, setLista] = useState(null);
  const [q, setQ] = useState('');
  const [abierto, setAbierto] = useState(null);
  const [categorias, setCategorias] = useState([]);
  const [importando, setImportando] = useState(false);
  const cargar = useCallback(() => {
    api.comercial.productos(slug, { q: q || undefined }).then(({ data }) => setLista(data)).catch(() => setLista([]));
  }, [slug, q]);
  useEffect(() => { const t = setTimeout(cargar, q ? 250 : 0); return () => clearTimeout(t); }, [cargar, q]);
  useEffect(() => { api.finanzas.categorias(slug).then(({ data }) => setCategorias(data)).catch(() => {}); }, [slug]);
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, border: '1px solid', borderColor: 'divider', borderRadius: '10px', px: 1.25, py: 0.5, flex: 1, minWidth: 220, maxWidth: 380, bgcolor: 'background.paper' }}>
          <Search size={15} style={{ opacity: 0.5 }} />
          <InputBase placeholder="Buscar por nombre o código" value={q} onChange={(e) => setQ(e.target.value)} sx={{ flex: 1, fontSize: '0.86rem' }} />
        </Box>
        <Box sx={{ flex: 1 }} />
        <Button size="small" variant="outlined" startIcon={<Download size={14} />} onClick={() => descargar(api.comercial.exportar(slug, 'productos'), 'Productos.xlsx')}>Exportar</Button>
        {esEditor && <Button size="small" variant="outlined" startIcon={<Upload size={14} />} onClick={() => setImportando(true)}>Importar</Button>}
        {esEditor && <Button size="small" variant="contained" startIcon={<Plus size={15} />} onClick={() => setAbierto('nuevo')}>Nuevo producto</Button>}
      </Box>
      {!lista ? <CircularProgress size={20} sx={{ m: 'auto', mt: 4 }} /> : lista.length === 0 ? (
        <Typography sx={{ textAlign: 'center', py: 8, color: 'text.secondary', fontSize: '0.9rem' }}>
          {q ? 'Nada coincide con la búsqueda.' : 'Todavía no hay productos. Créelos aquí, impórtelos desde Excel o escríbalos directo en una cotización.'}
        </Typography>
      ) : (
        <Box sx={{ border: '1px solid', borderColor: 'divider', borderRadius: '12px', overflow: 'auto', bgcolor: 'background.paper' }}>
          <Table size="small" sx={{ '& td, & th': { fontSize: '0.84rem', borderColor: 'divider', whiteSpace: 'nowrap' } }}>
            <TableHead>
              <TableRow sx={{ '& th': { color: 'text.secondary', fontWeight: 500, bgcolor: 'action.hover' } }}>
                <TableCell>Código</TableCell><TableCell>Producto</TableCell><TableCell>Tipo</TableCell>
                <TableCell align="right">Precio de venta</TableCell><TableCell align="right">Costo</TableCell>
                <TableCell align="right">Margen</TableCell>
                {conInventario && <TableCell align="right">Stock</TableCell>}
              </TableRow>
            </TableHead>
            <TableBody>
              {lista.map((p) => {
                const margen = Number(p.precio_venta) ? Math.round(((Number(p.precio_venta) - Number(p.costo)) * 100) / Number(p.precio_venta)) : null;
                const bajo = p.tipo === 'almacenable' && Number(p.stock_minimo) > 0 && Number(p.stock) < Number(p.stock_minimo);
                return (
                  <TableRow key={p.id} hover sx={{ cursor: 'pointer', opacity: p.activo ? 1 : 0.5 }} onClick={() => setAbierto(p)}>
                    <TableCell sx={{ color: 'text.secondary' }}>{p.codigo || '—'}</TableCell>
                    <TableCell sx={{ fontWeight: 500 }}>{p.nombre}</TableCell>
                    <TableCell sx={{ color: 'text.secondary' }}>{TIPOS[p.tipo]}</TableCell>
                    <TableCell align="right" sx={NUM}>{clp(p.precio_venta)}</TableCell>
                    <TableCell align="right" sx={NUM}>{clp(p.costo)}</TableCell>
                    <TableCell align="right" sx={NUM}>{margen == null ? '—' : `${margen}%`}</TableCell>
                    {conInventario && (
                      <TableCell align="right" sx={{ ...NUM, color: bajo ? 'error.main' : 'inherit' }}>
                        {p.tipo === 'almacenable' ? `${cant(p.stock)} ${p.unidad}` : '—'}
                      </TableCell>
                    )}
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </Box>
      )}
      {abierto && (
        <FichaProducto slug={slug} producto={abierto === 'nuevo' ? null : abierto} esEditor={esEditor} categorias={categorias}
          onCerrar={() => setAbierto(null)} onGuardado={() => { setAbierto(null); cargar(); }} />
      )}
      {importando && <DialogoImportar slug={slug} que="productos" onCerrar={() => setImportando(false)} onHecho={cargar} />}
    </Box>
  );
}
