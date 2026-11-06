import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Box, Button, Checkbox, Chip, CircularProgress, IconButton, InputBase, MenuItem, Select,
  Table, TableBody, TableCell, TableHead, TableRow, Typography, useTheme,
} from '@mui/material';
import { ArrowRight, Check, ChevronLeft, ChevronRight, Landmark, Lock, Plus, Undo2, Upload } from 'lucide-react';
import { toast } from 'react-toastify';
import { AnimatePresence } from 'framer-motion';
import { api } from '../../services/api';
import { EASE, MotionBox, Numero } from '../../components/Animado';
import { conPasos } from '../../components/ProgresoFlotante';
import { TONOS } from '../../theme/tonos';

/*
 * Conciliación bancaria, "El cuadre" (PMV financiero, 17-10-2026): se sube la cartola de cada
 * cuenta y Afable cruza solo lo que es claro. Lo demás queda en "Por revisar": por identificar,
 * posibles traspasos entre cuentas propias y los documentos sin su movimiento en el banco.
 */

const clp = (n) => `${n < 0 ? '−' : ''}$${Math.abs(Math.round(Number(n) || 0)).toLocaleString('es-CL')}`;
const MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
const Mes = (m) => MESES[m - 1].charAt(0).toUpperCase() + MESES[m - 1].slice(1);
const ddmm = (iso) => iso.split('-').reverse().slice(0, 2).join('-');
const SORA = "'Sora', sans-serif";
const NUM = { fontVariantNumeric: 'tabular-nums' };
const TIPOS = [
  ['retiro_dueno', 'Retiro del dueño'], ['aporte_capital', 'Aporte de capital'],
  ['comision', 'Comisión o gasto bancario'], ['remuneraciones', 'Remuneraciones'],
  ['impuestos', 'Pago de impuestos (F29, TGR)'], ['prestamo', 'Préstamo o crédito'], ['otro', 'Otro'],
];
// Las filas del cuadre: título, detalle, monto y flecha. En el teléfono el detalle baja bajo
// el título y el monto queda a la derecha de los dos.
const FILA_GRID = {
  display: 'grid', gridTemplateColumns: { xs: '1fr auto', md: '1fr auto 160px 24px' }, columnGap: 1,
  '& > :nth-child(2)': { gridRow: { xs: 2, md: 'auto' }, gridColumn: { xs: 1, md: 'auto' } },
  '& > :nth-child(3)': { gridRow: { xs: '1 / span 2', md: 'auto' }, gridColumn: { xs: 2, md: 'auto' } },
  '& > :nth-child(4)': { display: { xs: 'none', md: 'block' } },
};
const BANCOS = ['Santander', 'Banco de Chile', 'BCI', 'BancoEstado', 'Itaú', 'Scotiabank', 'BICE', 'Security', 'Falabella', 'Otro'];

function Tarjeta({ children, sx }) {
  return <Box sx={{ border: '1px solid', borderColor: 'divider', borderRadius: '14px', bgcolor: 'background.paper', ...sx }}>{children}</Box>;
}

function ElCuadre({ slug, esEditor, onIr, version }) {
  const [c, setC] = useState(null);
  const [pos, setPos] = useState(null);           // {anio, mes} elegido
  const cargar = useCallback(() => {
    api.finanzas.cuadre(slug, pos || {}).then(({ data }) => setC(data));
  }, [slug, pos]);
  useEffect(() => { cargar(); }, [cargar, version]);

  if (!c) return <CircularProgress size={20} sx={{ m: 'auto' }} />;
  if (!c.meses.length) {
    return (
      <Tarjeta sx={{ p: 5, textAlign: 'center' }}>
        <Box sx={{ display: 'inline-flex', p: 1.25, borderRadius: '10px', bgcolor: TONOS.pizarra.suave, color: TONOS.pizarra.color, mb: 1.5 }}><Landmark size={20} /></Box>
        <Typography sx={{ fontWeight: 600 }}>Todavía no hay cartolas</Typography>
        <Typography sx={{ fontSize: '0.88rem', color: 'text.secondary', mt: 0.5, mb: 2 }}>
          Agregue sus cuentas y suba la cartola de cada una. Afable cruza los movimientos con sus documentos del SII.
        </Typography>
        <Button variant="contained" size="small" onClick={() => onIr('cuentas')}>Agregar cuentas</Button>
      </Tarjeta>
    );
  }
  const i = c.meses.findIndex((x) => x.anio === c.anio && x.mes === c.mes);
  const mover = (d) => { const x = c.meses[i + d]; if (x) setPos(x); };
  const pct = c.porcentaje ?? 0;
  const cerrar = async () => {
    try {
      const { data } = c.cerrado ? await api.finanzas.reabrirMes(slug, c.anio, c.mes) : await api.finanzas.cerrarMes(slug, c.anio, c.mes);
      setC({ ...c, ...data });
      toast.success(data.cerrado ? `${Mes(c.mes)} quedó cerrado.` : `${Mes(c.mes)} quedó abierto.`);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'No se pudo.');
    }
  };
  const fila = (titulo, detalle, monto, ir) => (
    <Box onClick={ir} sx={{ ...FILA_GRID, alignItems: 'center', px: 2.5, py: 1.25, borderTop: '1px solid', borderColor: 'divider', cursor: ir ? 'pointer' : 'default', '&:hover': ir ? { bgcolor: 'action.hover' } : {} }}>
      <Typography sx={{ fontWeight: 600, fontSize: '0.92rem' }}>{titulo}</Typography>
      <Typography sx={{ fontSize: '0.82rem', color: 'text.secondary', mr: 2, ...NUM }}>{detalle}</Typography>
      <Typography sx={{ fontWeight: 700, textAlign: 'right', ...NUM }}>{monto}</Typography>
      {ir && <ArrowRight size={15} />}
    </Box>
  );

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 1 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, bgcolor: 'action.hover', borderRadius: '10px', p: 0.5 }}>
          <IconButton size="small" disabled={i >= c.meses.length - 1} onClick={() => mover(1)}><ChevronLeft size={16} /></IconButton>
          <Typography sx={{ fontWeight: 600, px: 1.5, py: 0.25, bgcolor: 'background.paper', borderRadius: '7px', whiteSpace: 'nowrap' }}>{Mes(c.mes)} {c.anio}</Typography>
          <IconButton size="small" disabled={i <= 0} onClick={() => mover(-1)}><ChevronRight size={16} /></IconButton>
        </Box>
        <Typography sx={{ fontSize: '0.85rem', color: 'text.secondary' }}>{c.cuentas} {c.cuentas === 1 ? 'cuenta' : 'cuentas'} · {c.movimientos} movimientos</Typography>
      </Box>

      <Box sx={{ textAlign: 'center', py: 1 }}>
        <Typography sx={{ fontFamily: SORA, fontWeight: 700, fontSize: { xs: '3rem', sm: '4rem' }, lineHeight: 1, ...NUM }}><Numero valor={pct} formato={(x) => `${Math.round(x)}%`} duracion={0.7} /></Typography>
        <Typography sx={{ fontSize: '1.05rem', fontWeight: 500, color: 'text.secondary', mt: 1 }}>De todo lo que se movió en {MESES[c.mes - 1]}</Typography>
        <Box sx={{ width: 520, maxWidth: '100%', height: 10, borderRadius: 5, bgcolor: 'action.hover', mx: 'auto', mt: 2, overflow: 'hidden' }}>
          <MotionBox initial={{ width: 0 }} animate={{ width: `${pct}%` }} transition={{ duration: 0.7, ease: EASE }} sx={{ height: '100%', bgcolor: '#0f9d6b' }} />
        </Box>
        <Typography sx={{ fontSize: '0.85rem', color: 'text.secondary', mt: 1 }}>
          <b style={{ color: '#007956' }}>{c.cuadraron_solos} cuadraron solos</b> · {c.los_cuadro_usted} los cuadró usted · {c.pendientes} pendientes
        </Typography>
      </Box>

      <Tarjeta sx={{ overflow: 'hidden' }}>
        <Box sx={{ ...FILA_GRID, alignItems: 'center', px: 2.5, py: 1.25, bgcolor: 'action.hover' }}>
          <Typography sx={{ fontSize: '0.74rem', fontWeight: 600, letterSpacing: '0.07em', textTransform: 'uppercase', color: 'text.secondary' }}>Su cartola</Typography>
          <Typography sx={{ fontWeight: 600, fontSize: '0.9rem', mr: 2 }}>{c.movimientos - c.pendientes} de {c.movimientos} líneas</Typography>
          <Typography sx={{ textAlign: 'right', ...NUM }}><b>{clp(c.sin_explicar)}</b> <span style={{ fontSize: '0.78rem', opacity: 0.7 }}>sin explicar</span></Typography>
          <span />
        </Box>
        {fila('Por identificar', `${c.por_identificar.cantidad} mov.`, clp(c.por_identificar.monto), c.por_identificar.cantidad ? () => onIr('revisar') : null)}
        {fila('Posibles traspasos', `${c.posibles_traspasos.pares} ${c.posibles_traspasos.pares === 1 ? 'par' : 'pares'}`, clp(c.posibles_traspasos.monto), c.posibles_traspasos.pares ? () => onIr('revisar') : null)}
        <Box sx={{ ...FILA_GRID, alignItems: 'center', px: 2.5, py: 1.25, bgcolor: 'action.hover', borderTop: '1px solid', borderColor: 'divider' }}>
          <Typography sx={{ fontSize: '0.74rem', fontWeight: 600, letterSpacing: '0.07em', textTransform: 'uppercase', color: 'text.secondary' }}>Lo anotado (documentos vencidos)</Typography>
          <Typography sx={{ fontWeight: 600, fontSize: '0.9rem', mr: 2 }}>{c.anotado.con_respaldo} de {c.anotado.registros} registros</Typography>
          <Typography sx={{ textAlign: 'right', ...NUM }}><b>{clp(c.anotado.sin_respaldo_monto)}</b> <span style={{ fontSize: '0.78rem', opacity: 0.7 }}>sin respaldo</span></Typography>
          <span />
        </Box>
        <Box sx={{ px: 2.5, py: 1.25, borderTop: '1px solid', borderColor: 'divider' }}>
          {c.anotado.registros === c.anotado.con_respaldo
            ? <Typography sx={{ fontSize: '0.88rem', color: '#007956', fontWeight: 500 }}><Check size={14} style={{ verticalAlign: '-2px' }} /> Todos sus documentos vencidos tienen su movimiento en el banco.</Typography>
            : <Typography sx={{ fontSize: '0.88rem', color: '#8a5a00' }}>{c.anotado.registros - c.anotado.con_respaldo} documentos vencidos todavía no aparecen en ninguna cartola.</Typography>}
        </Box>
      </Tarjeta>

      {esEditor && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, pt: 1 }}>
          <Button variant="outlined" startIcon={<Upload size={15} />} onClick={() => onIr('cuentas')}>Subir cartolas</Button>
          <Box sx={{ flex: 1 }} />
          <Button variant="outlined" startIcon={<Lock size={14} />} onClick={cerrar}>{c.cerrado ? `Reabrir ${MESES[c.mes - 1]}` : `Cerrar ${MESES[c.mes - 1]}`}</Button>
          {c.pendientes > 0 && !c.cerrado && <Button variant="contained" onClick={() => onIr('revisar', { anio: c.anio, mes: c.mes })}>Resolver {c.pendientes} pendientes</Button>}
        </Box>
      )}
    </Box>
  );
}

function Movimiento({ m, slug, esEditor, onCambio }) {
  const [sel, setSel] = useState(() => (m.candidatos || []).filter((d) => d.diferencia === 0).slice(0, 1).map((d) => d.id));
  const accion = async (a, datos) => {
    try {
      const { data } = await api.finanzas.accionMovimiento(slug, m.id, a, datos);
      onCambio(data);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'No se pudo.');
    }
  };
  const suma = (m.candidatos || []).filter((d) => sel.includes(d.id)).reduce((s, d) => s + d.monto, 0);
  return (
    <Tarjeta sx={{ p: 2 }}>
      <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1.5 }}>
        <Typography sx={{ fontSize: '0.82rem', color: 'text.secondary', ...NUM }}>{ddmm(m.fecha)}</Typography>
        <Typography sx={{ fontWeight: 600, flex: 1 }} noWrap>{m.descripcion || '(sin glosa)'}</Typography>
        <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary' }}>{m.cuenta_etiqueta}</Typography>
        <Typography sx={{ fontFamily: SORA, fontWeight: 600, color: m.monto > 0 ? '#007956' : 'text.primary', ...NUM }}>{m.monto > 0 ? '+' : ''}{clp(m.monto)}</Typography>
      </Box>
      {m.pareja ? (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mt: 1.5 }}>
          <Typography sx={{ fontSize: '0.86rem', flex: 1 }}>
            Posible traspaso con <b>{m.pareja.cuenta_etiqueta}</b> ({ddmm(m.pareja.fecha)}, {m.pareja.monto > 0 ? '+' : ''}{clp(m.pareja.monto)}). Un traspaso entre cuentas propias no es ingreso ni gasto.
          </Typography>
          {esEditor && <>
            <Button size="small" variant="contained" onClick={() => accion('traspaso')}>Es traspaso</Button>
            <Button size="small" onClick={() => accion('no-es-traspaso')}>No es traspaso</Button>
          </>}
        </Box>
      ) : (
        <Box sx={{ mt: 1.25 }}>
          {(m.candidatos || []).length > 0 && (
            <>
              <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary', mb: 0.5 }}>¿Qué {m.monto > 0 ? 'cobro' : 'pago'} es? Documentos sin movimiento, del más parecido al menos:</Typography>
              {m.candidatos.map((d) => (
                <Box key={d.id} sx={{ display: 'flex', alignItems: 'center', gap: 1, fontSize: '0.85rem', py: 0.1 }}>
                  <Checkbox size="small" disabled={!esEditor} checked={sel.includes(d.id)} sx={{ p: 0.5 }}
                    onChange={() => setSel((s) => (s.includes(d.id) ? s.filter((x) => x !== d.id) : [...s, d.id]))} />
                  <span style={{ flex: 1 }}>{d.tipo_nombre} {d.folio} · {d.razon_social} · {ddmm(d.fecha)}</span>
                  {d.nombre_coincide && <Chip size="small" label="Nombre en la glosa" sx={{ height: 18, fontSize: '0.66rem' }} />}
                  <span style={{ ...NUM, fontWeight: 600, color: d.diferencia === 0 ? '#007956' : 'inherit' }}>{clp(d.monto)}</span>
                </Box>
              ))}
            </>
          )}
          {esEditor && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25, mt: 1.25, flexWrap: 'wrap' }}>
              {(m.candidatos || []).length > 0 && (
                <Button size="small" variant="contained" disabled={!sel.length} onClick={() => accion('conciliar', { documentos: sel })}>
                  Cuadrar con {sel.length || ''} {sel.length === 1 ? 'documento' : 'documentos'}{sel.length ? ` (${clp(suma)})` : ''}
                </Button>
              )}
              <Select size="small" displayEmpty value="" onChange={(e) => accion('identificar', { tipo: e.target.value })}
                renderValue={() => 'No tiene documento: es…'} sx={{ fontSize: '0.82rem', minWidth: 230 }}>
                {TIPOS.map(([k, l]) => <MenuItem key={k} value={k}>{l}</MenuItem>)}
              </Select>
            </Box>
          )}
        </Box>
      )}
    </Tarjeta>
  );
}

function PorRevisar({ slug, esEditor, mes: inicial, onCambio }) {
  const [pos, setPos] = useState(inicial);
  const [movs, setMovs] = useState(null);
  const [verCuadrados, setVerCuadrados] = useState(false);
  useEffect(() => {
    if (pos) { api.finanzas.movimientos(slug, pos).then(({ data }) => setMovs(data)); return; }
    api.finanzas.cuadre(slug).then(({ data }) => setPos({ anio: data.anio, mes: data.mes }));
  }, [slug, pos]);
  if (!movs) return <CircularProgress size={20} sx={{ m: 'auto' }} />;
  const reemplazar = (nuevo) => { setMovs((ms) => ms.map((x) => (x.id === nuevo.id ? nuevo : x))); onCambio(); api.finanzas.movimientos(slug, pos).then(({ data }) => setMovs(data)); };
  const pendientes = movs.filter((m) => m.estado === 'pendiente');
  const listos = movs.filter((m) => m.estado !== 'pendiente');
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.25 }}>
      <Typography sx={{ fontFamily: SORA, fontWeight: 600, fontSize: '1.15rem' }}>
        {pendientes.length
          ? <><Numero valor={pendientes.length} /> por revisar en {MESES[pos.mes - 1]}</>
          : `Nada pendiente en ${MESES[pos.mes - 1]}.`}
      </Typography>
      {/* Lo que se cuadra sale de la lista con un destello verde y la lista se cierra. */}
      <AnimatePresence initial={false}>
        {pendientes.map((m) => (
          <MotionBox key={m.id} layout
            exit={{ opacity: 0, height: 0, backgroundColor: 'rgba(15, 157, 107, 0.18)', transition: { duration: 0.35, ease: EASE } }}
            sx={{ borderRadius: '14px', overflow: 'hidden' }}>
            <Movimiento m={m} slug={slug} esEditor={esEditor} onCambio={reemplazar} />
          </MotionBox>
        ))}
      </AnimatePresence>
      <Button size="small" sx={{ alignSelf: 'flex-start' }} onClick={() => setVerCuadrados((v) => !v)}>
        {verCuadrados ? 'Ocultar' : 'Ver'} los {listos.length} ya cuadrados
      </Button>
      {verCuadrados && (
        <Tarjeta sx={{ overflow: 'auto' }}>
          <Table size="small" sx={{ '& td': { fontSize: '0.84rem', borderColor: 'divider' } }}>
            <TableBody>
              {listos.map((m) => (
                <TableRow key={m.id} hover>
                  <TableCell sx={NUM}>{ddmm(m.fecha)}</TableCell>
                  <TableCell sx={{ maxWidth: 320, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{m.descripcion}</TableCell>
                  <TableCell align="right" sx={{ ...NUM, fontWeight: 600 }}>{clp(m.monto)}</TableCell>
                  <TableCell sx={{ color: 'text.secondary' }}>
                    {m.estado === 'conciliado' && m.documentos.map((d) => `${d.tipo_nombre} ${d.folio}`).join(', ')}
                    {m.estado === 'identificado' && m.tipo_nombre}
                    {m.estado === 'traspaso' && 'Traspaso entre cuentas'}
                    {m.origen === 'auto' && <Chip size="small" label="Solo" sx={{ height: 18, fontSize: '0.66rem', ml: 1 }} />}
                  </TableCell>
                  <TableCell padding="none">{esEditor && <IconButton size="small" title="Deshacer" onClick={async () => { const { data } = await api.finanzas.accionMovimiento(slug, m.id, 'deshacer'); reemplazar(data); }}><Undo2 size={14} /></IconButton>}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Tarjeta>
      )}
    </Box>
  );
}

export function MisCuentas({ slug, esEditor, onCambio }) {
  const [cuentas, setCuentas] = useState(null);
  const [nueva, setNueva] = useState(null);
  const [subiendo, setSubiendo] = useState(null);
  const input = useRef(null);
  const destino = useRef(null);
  const cargar = useCallback(() => api.finanzas.cuentas(slug).then(({ data }) => setCuentas(data)), [slug]);
  useEffect(() => { cargar(); }, [cargar]);

  const crear = async () => {
    try {
      await api.finanzas.crearCuenta(slug, nueva);
      setNueva(null);
      cargar();
    } catch (e) { toast.error(e.response?.data?.detail || 'No se pudo crear.'); }
  };
  const subir = async (archivo) => {
    const id = destino.current;
    setSubiendo(id);
    try {
      const { data } = await conPasos(['Leyendo la cartola', 'Agregando los movimientos nuevos', 'Cruzando con sus facturas', 'Buscando traspasos entre sus cuentas'],
        () => api.finanzas.subirCartola(slug, id, archivo));
      toast.success(`${data.nuevos} movimientos nuevos${data.duplicados ? `, ${data.duplicados} ya estaban` : ''}. Afable ya cruzó lo que calzaba.`);
      cargar();
      onCambio();
    } catch (e) { toast.error(e.response?.data?.detail || 'No se pudo leer la cartola.'); }
    finally { setSubiendo(null); }
  };

  if (!cuentas) return <CircularProgress size={20} sx={{ m: 'auto' }} />;
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
      <input ref={input} type="file" hidden accept=".csv,.xlsx,text/csv" onChange={(e) => { if (e.target.files?.[0]) subir(e.target.files[0]); e.target.value = ''; }} />
      {cuentas.map((x) => (
        <Tarjeta key={x.id} sx={{ p: 2, display: 'flex', alignItems: 'center', gap: 2 }}>
          <Box sx={{ display: 'flex', p: 1, borderRadius: '10px', bgcolor: TONOS.pizarra.suave, color: TONOS.pizarra.color }}><Landmark size={18} /></Box>
          <Box sx={{ flex: 1 }}>
            <Typography sx={{ fontWeight: 600 }}>{x.etiqueta}</Typography>
            <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary' }}>{x.movimientos} movimientos{x.saldo != null ? ` · saldo ${clp(x.saldo)} al ${ddmm(x.saldo_al)}` : ''}</Typography>
          </Box>
          {esEditor && (
            <Button size="small" variant="outlined" disabled={subiendo === x.id} startIcon={subiendo === x.id ? <CircularProgress size={13} /> : <Upload size={14} />}
              onClick={() => { destino.current = x.id; input.current.click(); }}>Subir cartola</Button>
          )}
        </Tarjeta>
      ))}
      {esEditor && (nueva ? (
        <Tarjeta sx={{ p: 2, display: 'flex', gap: 1.25, alignItems: 'center', flexWrap: 'wrap' }}>
          <Select size="small" displayEmpty value={nueva.banco} onChange={(e) => setNueva({ ...nueva, banco: e.target.value })}
            renderValue={(v) => v || 'Banco'} sx={{ minWidth: 170, fontSize: '0.86rem' }}>
            {BANCOS.map((b) => <MenuItem key={b} value={b}>{b}</MenuItem>)}
          </Select>
          <InputBase placeholder="Tipo (cuenta corriente, vista…)" value={nueva.nombre} onChange={(e) => setNueva({ ...nueva, nombre: e.target.value })}
            sx={{ border: '1px solid', borderColor: 'divider', borderRadius: '8px', px: 1.25, py: 0.4, fontSize: '0.86rem', width: 240 }} />
          <InputBase placeholder="Últimos dígitos" value={nueva.numero} onChange={(e) => setNueva({ ...nueva, numero: e.target.value })}
            sx={{ border: '1px solid', borderColor: 'divider', borderRadius: '8px', px: 1.25, py: 0.4, fontSize: '0.86rem', width: 140 }} />
          <Button size="small" variant="contained" disabled={!nueva.banco} onClick={crear}>Agregar</Button>
          <Button size="small" onClick={() => setNueva(null)}>Cancelar</Button>
        </Tarjeta>
      ) : (
        <Button size="small" variant="outlined" startIcon={<Plus size={14} />} sx={{ alignSelf: 'flex-start' }} onClick={() => setNueva({ banco: '', nombre: '', numero: '' })}>
          Agregar cuenta
        </Button>
      ))}
      <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary' }}>
        Suba la cartola en CSV o Excel tal como la descarga del banco. Si vuelve a subir los mismos días, no se repiten.
      </Typography>
    </Box>
  );
}

function Anteriores({ slug }) {
  const [cierres, setCierres] = useState(null);
  useEffect(() => { api.finanzas.cierres(slug).then(({ data }) => setCierres(data)); }, [slug]);
  if (!cierres) return <CircularProgress size={20} sx={{ m: 'auto' }} />;
  if (!cierres.length) return <Typography sx={{ color: 'text.secondary', fontSize: '0.9rem', py: 3 }}>Todavía no hay meses cerrados. Cierre un mes desde "El cuadre" cuando quede conforme.</Typography>;
  return (
    <Tarjeta sx={{ overflow: 'auto' }}>
      <Table size="small" sx={{ '& td, & th': { fontSize: '0.86rem', borderColor: 'divider' } }}>
        <TableHead><TableRow sx={{ '& th': { color: 'text.secondary', fontWeight: 600, fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.06em' } }}>
          <TableCell>Mes</TableCell><TableCell align="right">Cuadrado</TableCell><TableCell align="right">Movimientos</TableCell><TableCell align="right">Pendientes al cerrar</TableCell><TableCell>Cerrado</TableCell>
        </TableRow></TableHead>
        <TableBody>
          {cierres.map((x) => (
            <TableRow key={`${x.anio}-${x.mes}`}>
              <TableCell sx={{ fontWeight: 600 }}>{Mes(x.mes)} {x.anio}</TableCell>
              <TableCell align="right">{String(Number(x.porcentaje)).replace('.', ',')}%</TableCell>
              <TableCell align="right">{x.resumen.movimientos}</TableCell>
              <TableCell align="right">{x.resumen.pendientes}</TableCell>
              <TableCell>{ddmm(x.cerrado_en.slice(0, 10))}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Tarjeta>
  );
}

const SECCIONES = [['cuadre', 'El cuadre'], ['revisar', 'Por revisar'], ['cuentas', 'Mis cuentas'], ['anteriores', 'Cuadres anteriores']];

export default function Conciliacion({ slug, esEditor }) {
  const theme = useTheme();
  const [seccion, setSeccion] = useState('cuadre');
  const [mes, setMes] = useState(null);
  const [version, setVersion] = useState(0);
  const ir = (s, m) => { if (m) setMes(m); setSeccion(s); };
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Box sx={{ display: 'flex', gap: '2px', p: '3px', borderRadius: '9px', border: `1px solid ${theme.palette.divider}`, bgcolor: 'action.hover', alignSelf: 'flex-start', maxWidth: '100%', overflowX: 'auto' }}>
        {SECCIONES.map(([k, l]) => (
          <Box key={k} component="button" onClick={() => setSeccion(k)} sx={{
            border: 'none', cursor: 'pointer', fontFamily: 'inherit', fontSize: '0.84rem', fontWeight: 500, px: 1.5, py: 0.5, borderRadius: '7px', whiteSpace: 'nowrap', flexShrink: 0,
            bgcolor: seccion === k ? 'background.paper' : 'transparent', color: seccion === k ? 'text.primary' : 'text.secondary',
            boxShadow: seccion === k ? '0 1px 2px rgba(11,11,15,0.08)' : 'none',
          }}>{l}</Box>
        ))}
      </Box>
      {seccion === 'cuadre' && <ElCuadre slug={slug} esEditor={esEditor} onIr={ir} version={version} />}
      {seccion === 'revisar' && <PorRevisar slug={slug} esEditor={esEditor} mes={mes} onCambio={() => setVersion((v) => v + 1)} />}
      {seccion === 'cuentas' && <MisCuentas slug={slug} esEditor={esEditor} onCambio={() => setVersion((v) => v + 1)} />}
      {seccion === 'anteriores' && <Anteriores slug={slug} />}
    </Box>
  );
}
