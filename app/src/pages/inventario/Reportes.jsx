import { useEffect, useState } from 'react';
import {
  Box, Button, CircularProgress, MenuItem, Select, Tab, Table, TableBody, TableCell, TableHead, TableRow, Tabs, TextField, Typography,
} from '@mui/material';
import { Download } from 'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../../services/api';
import { NUM, Tarjeta, cant, clp, descargar, fecha } from '../comercial/comun';
import { msg } from './piezas';

/*
 * Inventario › Reportes (26-10-2026): cuánto valía el inventario a una fecha (para el cierre o
 * el balance), y la rotación: cuántos días de stock hay de cada producto y qué está inmovilizado.
 */

const tabla = { '& td, & th': { fontSize: '0.82rem', whiteSpace: 'nowrap' }, '& th': { color: 'text.secondary', fontWeight: 500 } };

function Valorizacion({ slug }) {
  const hoy = new Date().toISOString().slice(0, 10);
  const [dia, setDia] = useState(hoy);
  const [datos, setDatos] = useState(null);
  useEffect(() => {
    setDatos(null);
    api.inventario.valorizacion(slug, { fecha: dia }).then(({ data }) => setDatos(data)).catch((e) => { toast.error(msg(e, 'No se pudo calcular.')); setDatos({ productos: [], por_familia: [], total: 0 }); });
  }, [slug, dia]);
  return (
    <Box sx={{ display: 'grid', gap: 1.5 }}>
      <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
        <TextField size="small" type="date" label="Al día" InputLabelProps={{ shrink: true }} value={dia} onChange={(e) => setDia(e.target.value || hoy)} />
        <Typography sx={{ fontSize: '0.84rem', color: 'text.secondary', flex: 1 }}>
          Cantidades y costo promedio con lo registrado hasta ese día. Sirve para el cierre de mes y el balance.
        </Typography>
        <Button size="small" startIcon={<Download size={14} />} onClick={() => descargar(api.inventario.exportar(slug, 'valorizacion', { fecha: dia }), `Valorización ${dia}.xlsx`)}>Excel</Button>
      </Box>
      {!datos ? <CircularProgress size={20} /> : (
        <>
          <Tarjeta sx={{ p: 2, display: 'flex', gap: 4, flexWrap: 'wrap' }}>
            <Box><Typography sx={{ fontSize: '0.74rem', color: 'text.secondary' }}>Valor al {fecha(datos.fecha)}</Typography>
              <Typography sx={{ fontFamily: "'Sora', sans-serif", fontWeight: 600, fontSize: '1.4rem', ...NUM }}>{clp(datos.total)}</Typography></Box>
            {datos.por_familia.map((f) => (
              <Box key={f.familia || '—'}><Typography sx={{ fontSize: '0.74rem', color: 'text.secondary' }}>{f.familia || 'Sin familia'}</Typography>
                <Typography sx={{ fontWeight: 600, ...NUM }}>{clp(f.valor)}</Typography></Box>
            ))}
          </Tarjeta>
          <Tarjeta sx={{ overflowX: 'auto' }}>
            <Table size="small" sx={tabla}>
              <TableHead><TableRow>
                <TableCell>Producto</TableCell><TableCell>Familia</TableCell><TableCell align="right">Cantidad</TableCell>
                <TableCell align="right">Costo promedio</TableCell><TableCell align="right">Valor</TableCell>
              </TableRow></TableHead>
              <TableBody>
                {datos.productos.map((p) => (
                  <TableRow key={p.id} hover>
                    <TableCell>{p.codigo ? `${p.codigo} · ` : ''}{p.nombre}</TableCell>
                    <TableCell sx={{ color: 'text.secondary' }}>{p.familia || '—'}</TableCell>
                    <TableCell align="right" sx={NUM}>{cant(p.cantidad)}</TableCell>
                    <TableCell align="right" sx={NUM}>{clp(p.costo_promedio)}</TableCell>
                    <TableCell align="right" sx={{ ...NUM, fontWeight: 500 }}>{clp(p.valor)}</TableCell>
                  </TableRow>
                ))}
                {datos.productos.length === 0 && <TableRow><TableCell colSpan={5} sx={{ color: 'text.secondary' }}>Sin stock a esa fecha.</TableCell></TableRow>}
              </TableBody>
            </Table>
          </Tarjeta>
        </>
      )}
    </Box>
  );
}

function Rotacion({ slug }) {
  const [dias, setDias] = useState(90);
  const [datos, setDatos] = useState(null);
  useEffect(() => {
    setDatos(null);
    api.inventario.rotacion(slug, { dias }).then(({ data }) => setDatos(data)).catch((e) => { toast.error(msg(e, 'No se pudo calcular.')); setDatos({ productos: [], inmovilizados: [] }); });
  }, [slug, dias]);
  const filas = (lista) => lista.map((p) => (
    <TableRow key={p.id} hover>
      <TableCell>{p.codigo ? `${p.codigo} · ` : ''}{p.nombre}</TableCell>
      <TableCell align="right" sx={NUM}>{cant(p.stock)}</TableCell>
      <TableCell align="right" sx={NUM}>{cant(p.salidas)}</TableCell>
      <TableCell align="right" sx={{ ...NUM, fontWeight: 600, color: p.dias_inventario == null ? 'text.disabled' : p.dias_inventario > 180 ? '#b45309' : 'text.primary' }}>
        {p.dias_inventario == null ? 'no vende' : `${Math.round(p.dias_inventario)} días`}
      </TableCell>
      <TableCell sx={{ color: 'text.secondary' }}>{p.ultimo_movimiento ? `${fecha(p.ultimo_movimiento)} (${p.dias_sin_movimiento} d)` : '—'}</TableCell>
      <TableCell align="right" sx={NUM}>{clp(p.valor)}</TableCell>
    </TableRow>
  ));
  const cabeza = (
    <TableHead><TableRow>
      <TableCell>Producto</TableCell><TableCell align="right">Stock</TableCell><TableCell align="right">Vendido en {dias} días</TableCell>
      <TableCell align="right">Días de inventario</TableCell><TableCell>Último movimiento</TableCell><TableCell align="right">Valor</TableCell>
    </TableRow></TableHead>
  );
  return (
    <Box sx={{ display: 'grid', gap: 1.5 }}>
      <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
        <Select size="small" value={dias} onChange={(e) => setDias(e.target.value)} sx={{ fontSize: '0.84rem' }}>
          {[30, 60, 90, 180, 365].map((d) => <MenuItem key={d} value={d}>Últimos {d} días</MenuItem>)}
        </Select>
        <Typography sx={{ fontSize: '0.84rem', color: 'text.secondary' }}>
          Días de inventario = stock de hoy ÷ lo que se vende al día. Mucho stock y poca venta es plata detenida.
        </Typography>
      </Box>
      {!datos ? <CircularProgress size={20} /> : (
        <>
          {datos.inmovilizados.length > 0 && (
            <Tarjeta sx={{ overflowX: 'auto' }}>
              <Typography sx={{ fontWeight: 600, fontSize: '0.92rem', px: 2, pt: 1.5 }}>
                Inmovilizado: con stock y sin ventas en {dias} días · {clp(datos.inmovilizados.reduce((a, p) => a + (p.valor || 0), 0))}
              </Typography>
              <Table size="small" sx={tabla}>{cabeza}<TableBody>{filas(datos.inmovilizados)}</TableBody></Table>
            </Tarjeta>
          )}
          <Tarjeta sx={{ overflowX: 'auto' }}>
            <Typography sx={{ fontWeight: 600, fontSize: '0.92rem', px: 2, pt: 1.5 }}>Rotación por producto</Typography>
            <Table size="small" sx={tabla}>{cabeza}<TableBody>
              {filas(datos.productos)}
              {datos.productos.length === 0 && <TableRow><TableCell colSpan={6} sx={{ color: 'text.secondary' }}>Sin productos con stock o ventas.</TableCell></TableRow>}
            </TableBody></Table>
          </Tarjeta>
        </>
      )}
    </Box>
  );
}

export default function Reportes({ slug }) {
  const [pestana, setPestana] = useState('valorizacion');
  return (
    <Box sx={{ display: 'grid', gap: 1.5 }}>
      <Tabs value={pestana} onChange={(_, v) => setPestana(v)} sx={{ minHeight: 36, '& .MuiTab-root': { minHeight: 36, textTransform: 'none', fontSize: '0.88rem' } }}>
        <Tab value="valorizacion" label="Valorización" />
        <Tab value="rotacion" label="Rotación e inmovilizado" />
      </Tabs>
      {pestana === 'valorizacion' ? <Valorizacion slug={slug} /> : <Rotacion slug={slug} />}
    </Box>
  );
}
