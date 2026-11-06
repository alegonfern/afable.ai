import { useEffect, useState } from 'react';
import {
  Box, CircularProgress, InputBase, MenuItem, Select, Table, TableBody, TableCell, TableHead, TableRow, TextField, Typography,
} from '@mui/material';
import { Link } from 'react-router-dom';
import { Search } from 'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../../services/api';
import { NUM, Tarjeta, cant, clp, fecha } from '../comercial/comun';
import { msg } from './piezas';

/*
 * Inventario › Movimientos (26-10-2026): todo lo que entró y salió, de dónde vino y quién lo hizo.
 */

const TIPOS = [
  ['compra', 'Recepción de compra'], ['venta', 'Entrega de venta'], ['devolucion', 'Devolución'], ['entrada', 'Entrada manual'],
  ['salida', 'Salida manual'], ['ajuste', 'Ajuste'], ['conteo', 'Toma de inventario'], ['traspaso', 'Traspaso'],
  ['inicial', 'Stock inicial'], ['anulacion', 'Anulación'],
];

export default function Movimientos({ slug }) {
  const [filtro, setFiltro] = useState({ q: '', tipo: '', bodega: '', desde: '', hasta: '' });
  const [lista, setLista] = useState(null);
  const [bodegas, setBodegas] = useState([]);
  useEffect(() => { api.comercial.bodegas(slug).then(({ data }) => setBodegas(data.filter((b) => b.activa))).catch(() => {}); }, [slug]);
  useEffect(() => {
    const params = Object.fromEntries(Object.entries(filtro).filter(([, v]) => v));
    const t = setTimeout(() => api.inventario.movimientos(slug, params).then(({ data }) => setLista(data))
      .catch((e) => { toast.error(msg(e, 'No se pudieron leer los movimientos.')); setLista([]); }), filtro.q ? 250 : 0);
    return () => clearTimeout(t);
  }, [slug, filtro]);
  const cambiar = (k) => (e) => setFiltro((f) => ({ ...f, [k]: e.target.value }));
  return (
    <Box sx={{ display: 'grid', gap: 1.5 }}>
      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', alignItems: 'center' }}>
        <InputBase placeholder="Producto o referencia" value={filtro.q} onChange={cambiar('q')}
          startAdornment={<Search size={14} style={{ marginRight: 6, opacity: 0.5 }} />}
          sx={{ border: '1px solid', borderColor: 'divider', borderRadius: '8px', px: 1.25, py: 0.3, fontSize: '0.85rem', minWidth: 240, bgcolor: 'background.paper' }} />
        <Select size="small" displayEmpty value={filtro.tipo} onChange={cambiar('tipo')} sx={{ fontSize: '0.84rem', minWidth: 180 }}>
          <MenuItem value="">Todos los movimientos</MenuItem>
          {TIPOS.map(([v, n]) => <MenuItem key={v} value={v}>{n}</MenuItem>)}
        </Select>
        {bodegas.length > 1 && (
          <Select size="small" displayEmpty value={filtro.bodega} onChange={cambiar('bodega')} sx={{ fontSize: '0.84rem', minWidth: 160 }}>
            <MenuItem value="">Todas las bodegas</MenuItem>
            {bodegas.map((b) => <MenuItem key={b.id} value={b.id}>{b.nombre}</MenuItem>)}
          </Select>
        )}
        <TextField size="small" type="date" label="Desde" InputLabelProps={{ shrink: true }} value={filtro.desde} onChange={cambiar('desde')} />
        <TextField size="small" type="date" label="Hasta" InputLabelProps={{ shrink: true }} value={filtro.hasta} onChange={cambiar('hasta')} />
      </Box>
      {!lista ? <CircularProgress size={20} /> : lista.length === 0 ? (
        <Tarjeta sx={{ p: 4, textAlign: 'center', color: 'text.secondary', fontSize: '0.88rem' }}>No hay movimientos con ese filtro.</Tarjeta>
      ) : (
        <Tarjeta sx={{ overflowX: 'auto' }}>
          <Table size="small" sx={{ '& td, & th': { fontSize: '0.82rem', whiteSpace: 'nowrap' }, '& th': { color: 'text.secondary', fontWeight: 500 } }}>
            <TableHead>
              <TableRow>
                <TableCell>Fecha</TableCell><TableCell>Producto</TableCell><TableCell>Movimiento</TableCell><TableCell>Documento</TableCell>
                <TableCell>Bodega</TableCell><TableCell align="right">Cantidad</TableCell><TableCell align="right">Costo unit.</TableCell><TableCell>Quién</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {lista.map((m) => {
                const n = Number(m.cantidad);
                return (
                  <TableRow key={m.id} hover>
                    <TableCell>{fecha(m.fecha)}</TableCell>
                    <TableCell sx={{ maxWidth: 260, overflow: 'hidden', textOverflow: 'ellipsis' }}>{m.producto}</TableCell>
                    <TableCell>{m.tipo_nombre}{m.motivo_nombre ? ` · ${m.motivo_nombre}` : ''}
                      {m.referencia && <Typography component="span" sx={{ display: 'block', fontSize: '0.72rem', color: 'text.secondary' }}>{m.referencia}</Typography>}</TableCell>
                    <TableCell>{m.documento ? (m.documento.enlace ? <Link to={m.documento.enlace}>{m.documento.numero}</Link> : m.documento.numero) : '—'}</TableCell>
                    <TableCell>{m.bodega}</TableCell>
                    <TableCell align="right" sx={{ ...NUM, fontWeight: 600, color: n < 0 ? '#c8102e' : '#0f9d6b' }}>{n > 0 ? '+' : ''}{cant(m.cantidad)}</TableCell>
                    <TableCell align="right" sx={NUM}>{m.costo_unitario != null ? clp(m.costo_unitario) : '—'}</TableCell>
                    <TableCell sx={{ color: 'text.secondary' }}>{m.usuario || '—'}</TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </Tarjeta>
      )}
      {lista?.length >= 500 && <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary' }}>Se muestran los 500 más recientes: acote con los filtros.</Typography>}
    </Box>
  );
}
