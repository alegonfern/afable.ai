import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Box, Button, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, MenuItem,
  Table, TableBody, TableCell, TableHead, TableRow, TextField, Typography,
} from '@mui/material';
import { AlertTriangle, CheckCircle2, CircleSlash, Download, MinusCircle, TrendingUp } from 'lucide-react';
import { Link } from 'react-router-dom';
import { toast } from 'react-toastify';
import { api } from '../../services/api';
import { NUM, aNumero, cant, clp, descargar, fecha } from '../comercial/comun';

/*
 * Piezas compartidas del módulo Inventario (26-10-2026): el estado del stock, el diálogo de
 * entradas, salidas, ajustes y traspasos, el gráfico del saldo y el kardex de un producto.
 */

export const msg = (e, d) => e?.response?.data?.detail || d;

// El estado del stock: lleva ícono y palabra (nunca solo color), con los colores de estado.
const ESTADOS = {
  negativo: { nombre: 'Negativo', color: '#c8102e', Icono: MinusCircle },
  sin_stock: { nombre: 'Sin stock', color: '#c8102e', Icono: CircleSlash },
  bajo_minimo: { nombre: 'Bajo el mínimo', color: '#b45309', Icono: AlertTriangle },
  sobre_maximo: { nombre: 'Sobre el máximo', color: '#6b7280', Icono: TrendingUp },
  ok: { nombre: 'Bien', color: '#0f9d6b', Icono: CheckCircle2 },
};

export function EstadoStock({ estado }) {
  const e = ESTADOS[estado] || ESTADOS.ok;
  const { Icono } = e;
  return (
    <Box component="span" sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5, fontSize: '0.78rem', color: 'text.primary', whiteSpace: 'nowrap' }}>
      <Icono size={13} color={e.color} />{e.nombre}
    </Box>
  );
}

export const ESTADOS_STOCK = Object.entries(ESTADOS).map(([valor, e]) => ({ valor, nombre: e.nombre }));

const TITULOS = { entrada: 'Entrada de stock', salida: 'Salida de stock', ajuste: 'Ajustar al conteo', traspaso: 'Traspasar entre bodegas' };

/* Entrada, salida (con su motivo), ajuste al conteo o traspaso de un producto. */
export function DialogoMovimiento({ slug, modo, producto, bodegas, motivos, onCerrar, onHecho }) {
  const principal = bodegas.find((b) => b.principal)?.id || bodegas[0]?.id || '';
  const [d, setD] = useState({
    bodega: principal, origen: principal, destino: bodegas.find((b) => b.id !== principal)?.id || '',
    cantidad: '', costo: '', motivo: (motivos?.[modo] || [])[0]?.valor || '', referencia: '', fecha: '',
  });
  const [guardando, setGuardando] = useState(false);
  const cambiar = (k) => (e) => setD((x) => ({ ...x, [k]: e.target.value }));
  const numero = (k) => (e) => setD((x) => ({ ...x, [k]: e.target.value.replace(/[^\d,]/g, '') }));
  const guardar = async () => {
    setGuardando(true);
    try {
      const base = { producto: producto.id, cantidad: aNumero(d.cantidad) };
      if (modo === 'entrada') {
        await api.inventario.entrada(slug, { ...base, bodega: d.bodega, motivo: d.motivo, referencia: d.referencia,
          costo_unitario: d.costo ? aNumero(d.costo) : undefined, fecha: d.fecha || undefined });
      } else if (modo === 'salida') {
        await api.inventario.salida(slug, { ...base, bodega: d.bodega, motivo: d.motivo, referencia: d.referencia, fecha: d.fecha || undefined });
      } else if (modo === 'ajuste') {
        await api.comercial.ajustar(slug, { ...base, bodega: d.bodega, motivo: d.referencia });
      } else {
        await api.comercial.traspasar(slug, { ...base, origen: d.origen, destino: d.destino });
      }
      toast.success({ entrada: 'Entrada registrada.', salida: 'Salida registrada.', ajuste: 'Stock ajustado.', traspaso: 'Traspaso hecho.' }[modo]);
      onHecho();
    } catch (e) { toast.error(msg(e, 'No se pudo registrar.')); }
    setGuardando(false);
  };
  const selector = (k, rotulo) => (
    <TextField select size="small" label={rotulo} value={d[k]} onChange={cambiar(k)}>
      {bodegas.map((b) => <MenuItem key={b.id} value={b.id}>{b.nombre}</MenuItem>)}
    </TextField>
  );
  return (
    <Dialog open onClose={onCerrar} maxWidth="xs" fullWidth>
      <DialogTitle sx={{ fontWeight: 600, pb: 0.5 }}>{TITULOS[modo]}</DialogTitle>
      <Typography sx={{ px: 3, fontSize: '0.84rem', color: 'text.secondary' }}>
        {producto.codigo ? `${producto.codigo} · ` : ''}{producto.nombre} · hay {cant(producto.fisico)} {producto.unidad}
      </Typography>
      <DialogContent sx={{ display: 'grid', gap: 1.5, pt: '14px !important' }}>
        {modo === 'traspaso' ? (
          <>{selector('origen', 'Desde')}{selector('destino', 'Hacia')}</>
        ) : bodegas.length > 1 && selector('bodega', 'Bodega')}
        {(modo === 'entrada' || modo === 'salida') && (
          <TextField select size="small" label="Motivo" value={d.motivo} onChange={cambiar('motivo')}>
            {(motivos?.[modo] || []).map((m) => <MenuItem key={m.valor} value={m.valor}>{m.nombre}</MenuItem>)}
          </TextField>
        )}
        <TextField size="small" autoFocus value={d.cantidad} onChange={numero('cantidad')}
          label={modo === 'ajuste' ? `Cantidad contada (${producto.unidad})` : `Cantidad (${producto.unidad})`}
          helperText={modo === 'ajuste' ? 'Lo que hay físicamente: Afable registra la diferencia.' : undefined} />
        {modo === 'entrada' && (
          <TextField size="small" label="Costo unitario sin IVA (opcional)" value={d.costo} onChange={numero('costo')}
            helperText={`Si queda vacío, el costo promedio (${clp(producto.costo_promedio)}).`} />
        )}
        {modo !== 'traspaso' && (
          <TextField size="small" label={modo === 'ajuste' ? 'Motivo (opcional)' : 'Referencia (opcional)'} value={d.referencia}
            onChange={cambiar('referencia')} placeholder={modo === 'salida' ? 'Ej: caja rota en bodega' : 'Ej: guía 1234, lote de producción'} />
        )}
        {(modo === 'entrada' || modo === 'salida') && (
          <TextField size="small" type="date" label="Fecha" InputLabelProps={{ shrink: true }} value={d.fecha} onChange={cambiar('fecha')}
            helperText="Vacía: hoy." />
        )}
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onCerrar}>Cancelar</Button>
        <Button variant="contained" onClick={guardar} disabled={!d.cantidad || guardando}>{guardando ? 'Guardando…' : 'Guardar'}</Button>
      </DialogActions>
    </Dialog>
  );
}

/* El saldo de un producto en el tiempo: una serie, área con línea de 2 px, cruz y tooltip al pasar. */
export function GraficoSaldo({ serie, unidad, alto = 140 }) {
  const ref = useRef(null);
  const [ancho, setAncho] = useState(560);
  const [hover, setHover] = useState(null);
  useEffect(() => {
    if (!ref.current) return undefined;
    const o = new ResizeObserver(([e]) => setAncho(Math.max(240, e.contentRect.width)));
    o.observe(ref.current);
    return () => o.disconnect();
  }, []);
  const puntos = useMemo(() => (serie || []).map((p) => ({ ...p, v: Number(p.saldo) })), [serie]);
  if (puntos.length < 2) {
    return <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary' }}>Todavía no hay movimientos suficientes para graficar.</Typography>;
  }
  const izq = 44; const der = 8; const arr = 8; const abj = 22;
  const max = Math.max(...puntos.map((p) => p.v), 0);
  const min = Math.min(...puntos.map((p) => p.v), 0);
  const rango = max - min || 1;
  const x = (i) => izq + (i / (puntos.length - 1)) * (ancho - izq - der);
  const y = (v) => arr + (1 - (v - min) / rango) * (alto - arr - abj);
  const linea = puntos.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p.v).toFixed(1)}`).join(' ');
  const area = `${linea} L${x(puntos.length - 1)},${y(min)} L${x(0)},${y(min)} Z`;
  const mover = (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    const i = Math.round(((e.clientX - r.left - izq) / (ancho - izq - der)) * (puntos.length - 1));
    setHover(Math.min(puntos.length - 1, Math.max(0, i)));
  };
  const h = hover != null ? puntos[hover] : null;
  return (
    <Box ref={ref} sx={{ position: 'relative', width: '100%' }}>
      <svg width={ancho} height={alto} role="img" aria-label={`Saldo en ${unidad} de ${fecha(puntos[0].fecha)} a ${fecha(puntos[puntos.length - 1].fecha)}`}
        onMouseMove={mover} onMouseLeave={() => setHover(null)} style={{ display: 'block', cursor: 'crosshair' }}>
        {[max, (max + min) / 2, min].map((v) => (
          <g key={v}>
            <line x1={izq} x2={ancho - der} y1={y(v)} y2={y(v)} stroke="currentColor" strokeOpacity={0.08} />
            <text x={izq - 6} y={y(v) + 3.5} textAnchor="end" fontSize={10.5} fill="currentColor" fillOpacity={0.55}>
              {Number(v.toFixed(2)).toLocaleString('es-CL')}
            </text>
          </g>
        ))}
        <text x={izq} y={alto - 5} fontSize={10.5} fill="currentColor" fillOpacity={0.55}>{fecha(puntos[0].fecha)}</text>
        <text x={ancho - der} y={alto - 5} fontSize={10.5} textAnchor="end" fill="currentColor" fillOpacity={0.55}>{fecha(puntos[puntos.length - 1].fecha)}</text>
        <path d={area} fill="var(--af-acento, #5b5fc7)" fillOpacity={0.12} />
        <path d={linea} fill="none" stroke="var(--af-acento, #5b5fc7)" strokeWidth={2} strokeLinejoin="round" />
        {h && (
          <g>
            <line x1={x(hover)} x2={x(hover)} y1={arr} y2={alto - abj} stroke="currentColor" strokeOpacity={0.3} />
            <circle cx={x(hover)} cy={y(h.v)} r={4.5} fill="var(--af-acento, #5b5fc7)" stroke="#fff" strokeWidth={2} />
          </g>
        )}
      </svg>
      {h && (
        <Box sx={{ position: 'absolute', top: 0, left: Math.min(x(hover) + 10, ancho - 150), pointerEvents: 'none', bgcolor: 'background.paper',
          border: '1px solid', borderColor: 'divider', borderRadius: '8px', px: 1, py: 0.5, fontSize: '0.78rem', boxShadow: 1 }}>
          <b>{cant(h.saldo)} {unidad}</b><Box component="span" sx={{ color: 'text.secondary' }}> · {fecha(h.fecha)}</Box>
        </Box>
      )}
    </Box>
  );
}

/* El kardex de un producto: saldo inicial, cada movimiento con su saldo corrido y valor, y el gráfico. */
export function DialogoKardex({ slug, producto, bodegas, onCerrar }) {
  const [filtro, setFiltro] = useState({ bodega: '', desde: '', hasta: '' });
  const [datos, setDatos] = useState(null);
  useEffect(() => {
    const params = Object.fromEntries(Object.entries(filtro).filter(([, v]) => v));
    setDatos(null);
    api.inventario.kardex(slug, producto.id, params).then(({ data }) => setDatos(data)).catch((e) => { toast.error(msg(e, 'No se pudo leer el kardex.')); setDatos({ movimientos: [] }); });
  }, [slug, producto.id, filtro]);
  const p = datos?.producto || producto;
  return (
    <Dialog open onClose={onCerrar} maxWidth="lg" fullWidth>
      <DialogTitle sx={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: 1 }}>
        <Box sx={{ flex: 1 }}>Kardex · {p.codigo ? `${p.codigo} · ` : ''}{p.nombre}</Box>
        <Button size="small" startIcon={<Download size={14} />}
          onClick={() => descargar(api.inventario.exportar(slug, `kardex/${producto.id}`, filtro.bodega ? { bodega: filtro.bodega } : {}), `Kardex ${p.nombre}.xlsx`)}>
          Excel
        </Button>
      </DialogTitle>
      <DialogContent sx={{ display: 'grid', gap: 2 }}>
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          {bodegas.length > 1 && (
            <TextField select size="small" label="Bodega" value={filtro.bodega} onChange={(e) => setFiltro((f) => ({ ...f, bodega: e.target.value }))} sx={{ minWidth: 180 }}>
              <MenuItem value="">Todas</MenuItem>
              {bodegas.map((b) => <MenuItem key={b.id} value={b.id}>{b.nombre}</MenuItem>)}
            </TextField>
          )}
          <TextField size="small" type="date" label="Desde" InputLabelProps={{ shrink: true }} value={filtro.desde} onChange={(e) => setFiltro((f) => ({ ...f, desde: e.target.value }))} />
          <TextField size="small" type="date" label="Hasta" InputLabelProps={{ shrink: true }} value={filtro.hasta} onChange={(e) => setFiltro((f) => ({ ...f, hasta: e.target.value }))} />
        </Box>
        {!datos ? <CircularProgress size={20} /> : (
          <>
            <Box>
              <Typography sx={{ fontSize: '0.8rem', fontWeight: 600, mb: 0.5 }}>Saldo en el tiempo ({p.unidad})</Typography>
              <GraficoSaldo serie={datos.serie} unidad={p.unidad} />
            </Box>
            <Box sx={{ overflowX: 'auto' }}>
              <Table size="small" sx={{ '& td, & th': { fontSize: '0.8rem', whiteSpace: 'nowrap' } }}>
                <TableHead>
                  <TableRow>
                    <TableCell>Fecha</TableCell><TableCell>Movimiento</TableCell><TableCell>Documento</TableCell><TableCell>Bodega</TableCell>
                    <TableCell align="right">Entrada</TableCell><TableCell align="right">Salida</TableCell><TableCell align="right">Saldo</TableCell>
                    <TableCell align="right">Costo unit.</TableCell><TableCell align="right">Valor del saldo</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {datos.saldo_inicial && (
                    <TableRow sx={{ '& td': { color: 'text.secondary' } }}>
                      <TableCell colSpan={6}>Saldo inicial</TableCell>
                      <TableCell align="right" sx={NUM}>{cant(datos.saldo_inicial.cantidad)}</TableCell><TableCell />
                      <TableCell align="right" sx={NUM}>{clp(datos.saldo_inicial.valor)}</TableCell>
                    </TableRow>
                  )}
                  {datos.movimientos.map((m) => (
                    <TableRow key={m.id} hover>
                      <TableCell>{fecha(m.fecha)}</TableCell>
                      <TableCell>{m.tipo_nombre}{m.motivo_nombre ? ` · ${m.motivo_nombre}` : ''}
                        {m.referencia && <Typography component="span" sx={{ display: 'block', fontSize: '0.72rem', color: 'text.secondary' }}>{m.referencia}</Typography>}</TableCell>
                      <TableCell>{m.documento ? (m.documento.enlace ? <Link to={m.documento.enlace}>{m.documento.numero}</Link> : m.documento.numero) : '—'}</TableCell>
                      <TableCell>{m.bodega}</TableCell>
                      <TableCell align="right" sx={NUM}>{Number(m.entrada) ? cant(m.entrada) : ''}</TableCell>
                      <TableCell align="right" sx={NUM}>{Number(m.salida) ? cant(m.salida) : ''}</TableCell>
                      <TableCell align="right" sx={{ ...NUM, fontWeight: 600 }}>{cant(m.saldo)}</TableCell>
                      <TableCell align="right" sx={NUM}>{m.costo_unitario != null ? clp(m.costo_unitario) : '—'}</TableCell>
                      <TableCell align="right" sx={NUM}>{clp(m.valor_saldo)}</TableCell>
                    </TableRow>
                  ))}
                  {datos.movimientos.length === 0 && (
                    <TableRow><TableCell colSpan={9} sx={{ color: 'text.secondary' }}>Sin movimientos en el período.</TableCell></TableRow>
                  )}
                </TableBody>
              </Table>
            </Box>
            {datos.saldo_final && (
              <Typography sx={{ fontSize: '0.84rem', textAlign: 'right' }}>
                Saldo final: <b>{cant(datos.saldo_final.cantidad)} {p.unidad}</b> · {clp(datos.saldo_final.valor)}
              </Typography>
            )}
          </>
        )}
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}><Button onClick={onCerrar}>Cerrar</Button></DialogActions>
    </Dialog>
  );
}

export function Kpi({ titulo, valor, detalle, alerta }) {
  return (
    <Box sx={{ border: '1px solid', borderColor: 'divider', borderRadius: '14px', bgcolor: 'background.paper', p: 2 }}>
      <Typography sx={{ fontSize: '0.72rem', fontWeight: 600, letterSpacing: '0.07em', textTransform: 'uppercase', color: 'text.secondary' }}>{titulo}</Typography>
      <Typography sx={{ fontFamily: "'Sora', sans-serif", fontWeight: 600, fontSize: '1.45rem', mt: 0.25, ...NUM, color: alerta ? '#c8102e' : 'text.primary' }}>{valor}</Typography>
      {detalle && <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary' }}>{detalle}</Typography>}
    </Box>
  );
}

