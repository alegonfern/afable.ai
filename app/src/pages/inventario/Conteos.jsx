import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Box, Button, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, FormControlLabel, InputBase, LinearProgress,
  MenuItem, Select, Switch, Table, TableBody, TableCell, TableHead, TableRow, TextField, Typography,
} from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Check, ClipboardList, Download, Plus, ScanLine, Upload } from 'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../../services/api';
import { NUM, Tarjeta, aNumero, cant, clp, descargar, fecha } from '../comercial/comun';
import { msg } from './piezas';

/*
 * Inventario › Toma de inventario (26-10-2026): se abre un conteo (de una bodega, de una familia
 * o de todo), se cuenta en pantalla —buscando o escaneando el código— o en la planilla Excel, se
 * revisan las diferencias y se aplican de una vez. Lo contado manda: el ajuste se calcula contra
 * el stock del momento de aplicar.
 */

function DialogoNuevo({ slug, onCerrar, onCreado }) {
  const [opciones, setOpciones] = useState({ bodegas: [], familias: [] });
  const [d, setD] = useState({ bodega: '', familia: '', solo_con_stock: false });
  const [creando, setCreando] = useState(false);
  useEffect(() => {
    api.inventario.stock(slug).then(({ data }) => setOpciones({ bodegas: data.bodegas || [], familias: data.familias || [] })).catch(() => {});
  }, [slug]);
  const crear = async () => {
    setCreando(true);
    try {
      const { data } = await api.inventario.crearConteo(slug, { bodega: d.bodega || null, familia: d.familia || '', solo_con_stock: d.solo_con_stock });
      toast.success(`Conteo ${data.numero} abierto con ${data.lineas?.length ?? data.lineas} productos.`);
      onCreado(data);
    } catch (e) { toast.error(msg(e, 'No se pudo abrir el conteo.')); }
    setCreando(false);
  };
  return (
    <Dialog open onClose={onCerrar} maxWidth="xs" fullWidth>
      <DialogTitle sx={{ fontWeight: 600 }}>Nueva toma de inventario</DialogTitle>
      <DialogContent sx={{ display: 'grid', gap: 1.5, pt: '8px !important' }}>
        <Typography sx={{ fontSize: '0.84rem', color: 'text.secondary', lineHeight: 1.5 }}>
          Afable anota lo que dice el sistema de cada producto; usted anota lo que hay. Mientras cuenta, la operación sigue normal.
        </Typography>
        {opciones.bodegas.length > 1 && (
          <TextField select size="small" label="Bodega" value={d.bodega} onChange={(e) => setD((x) => ({ ...x, bodega: e.target.value }))}>
            <MenuItem value="">Todas</MenuItem>
            {opciones.bodegas.map((b) => <MenuItem key={b.id} value={b.id}>{b.nombre}</MenuItem>)}
          </TextField>
        )}
        {opciones.familias.length > 0 && (
          <TextField select size="small" label="Familia" value={d.familia} onChange={(e) => setD((x) => ({ ...x, familia: e.target.value }))}>
            <MenuItem value="">Todas</MenuItem>
            {opciones.familias.map((f) => <MenuItem key={f} value={f}>{f}</MenuItem>)}
          </TextField>
        )}
        <FormControlLabel control={<Switch checked={d.solo_con_stock} onChange={(e) => setD((x) => ({ ...x, solo_con_stock: e.target.checked }))} />}
          label={<Typography sx={{ fontSize: '0.86rem' }}>Solo productos con stock en el sistema</Typography>} />
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onCerrar}>Cancelar</Button>
        <Button variant="contained" onClick={crear} disabled={creando}>{creando ? 'Abriendo…' : 'Abrir el conteo'}</Button>
      </DialogActions>
    </Dialog>
  );
}

function Lista({ slug, esEditor }) {
  const navigate = useNavigate();
  const [lista, setLista] = useState(null);
  const [nuevo, setNuevo] = useState(false);
  useEffect(() => { api.inventario.conteos(slug).then(({ data }) => setLista(data)).catch(() => setLista([])); }, [slug]);
  if (!lista) return <CircularProgress size={20} />;
  return (
    <Box sx={{ display: 'grid', gap: 1.5 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <Typography sx={{ fontSize: '0.86rem', color: 'text.secondary', flex: 1 }}>
          Cuente lo que hay en bodega y Afable ajusta el stock con las diferencias. Hágalo completo a fin de año o por familias durante el año.
        </Typography>
        {esEditor && <Button variant="contained" size="small" startIcon={<Plus size={14} />} onClick={() => setNuevo(true)}>Nuevo conteo</Button>}
      </Box>
      {lista.length === 0 ? (
        <Tarjeta sx={{ p: 4, textAlign: 'center', color: 'text.secondary', fontSize: '0.88rem' }}>
          <ClipboardList size={28} style={{ opacity: 0.4 }} />
          <Typography sx={{ mt: 1, fontSize: '0.88rem' }}>Todavía no hay tomas de inventario.</Typography>
        </Tarjeta>
      ) : (
        <Tarjeta sx={{ overflowX: 'auto' }}>
          <Table size="small" sx={{ '& td, & th': { fontSize: '0.82rem', whiteSpace: 'nowrap' }, '& th': { color: 'text.secondary', fontWeight: 500 } }}>
            <TableHead>
              <TableRow>
                <TableCell>Conteo</TableCell><TableCell>Fecha</TableCell><TableCell>Alcance</TableCell><TableCell>Estado</TableCell>
                <TableCell align="right">Contados</TableCell><TableCell align="right">Con diferencia</TableCell><TableCell align="right">Valor de la diferencia</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {lista.map((c) => (
                <TableRow key={c.id} hover sx={{ cursor: 'pointer' }} onClick={() => navigate(`/app/inventario/conteos/${c.id}`)}>
                  <TableCell sx={{ fontWeight: 500 }}>{c.numero}</TableCell>
                  <TableCell>{fecha(c.fecha)}</TableCell>
                  <TableCell>{[c.bodega || 'Todas las bodegas', c.familia].filter(Boolean).join(' · ')}</TableCell>
                  <TableCell>{c.estado_nombre}</TableCell>
                  <TableCell align="right" sx={NUM}>{c.contadas} de {c.lineas}</TableCell>
                  <TableCell align="right" sx={NUM}>{c.con_diferencia}</TableCell>
                  <TableCell align="right" sx={{ ...NUM, color: c.valor_diferencia < 0 ? '#c8102e' : 'text.primary' }}>{clp(c.valor_diferencia)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Tarjeta>
      )}
      {nuevo && <DialogoNuevo slug={slug} onCerrar={() => setNuevo(false)} onCreado={(c) => navigate(`/app/inventario/conteos/${c.id}`)} />}
    </Box>
  );
}

function Detalle({ slug, id, esEditor }) {
  const navigate = useNavigate();
  const [c, setC] = useState(null);
  const [valores, setValores] = useState({});
  const [buscar, setBuscar] = useState('');
  const [ver, setVer] = useState('todos');
  const [trabajando, setTrabajando] = useState(false);
  const refs = useRef({});

  const tomar = useCallback((data) => {
    setC(data);
    setValores(Object.fromEntries(data.lineas.map((l) => [l.id, l.contada == null ? '' : cant(l.contada)])));
  }, []);
  useEffect(() => { api.inventario.conteo(slug, id).then(({ data }) => tomar(data)).catch((e) => toast.error(msg(e, 'No se pudo abrir el conteo.'))); }, [slug, id, tomar]);

  const filas = useMemo(() => {
    if (!c) return [];
    const q = buscar.trim().toLowerCase();
    return c.lineas.filter((l) => {
      if (q && ![l.nombre, l.codigo, l.codigo_barras, l.ubicacion].some((x) => (x || '').toLowerCase().includes(q))) return false;
      if (ver === 'sin_contar') return l.contada == null;
      if (ver === 'diferencia') return l.contada != null && Number(l.diferencia) !== 0;
      return true;
    });
  }, [c, buscar, ver]);

  if (!c) return <CircularProgress size={20} />;
  const abierto = c.estado === 'contando' || c.estado === 'borrador';
  const editable = abierto && esEditor;

  const guardarLinea = async (l) => {
    const v = valores[l.id];
    const anterior = l.contada == null ? '' : cant(l.contada);
    if (v === anterior) return;
    try {
      const { data } = await api.inventario.contar(slug, id, [{ id: l.id, contada: v === '' ? null : aNumero(v) }]);
      tomar(data);
    } catch (e) { toast.error(msg(e, 'No se pudo guardar.')); }
  };
  // Buscar o escanear: con Enter, salta a la cantidad del producto (si hay uno solo).
  const alBuscar = (e) => {
    if (e.key !== 'Enter') return;
    if (filas.length === 1) refs.current[filas[0].id]?.focus();
  };
  const aplicar = async () => {
    const sinContar = c.lineas.filter((l) => l.contada == null).length;
    if (!window.confirm(`¿Aplicar el conteo ${c.numero}? Se ajustan ${c.con_diferencia} productos con diferencia (${clp(c.valor_diferencia)}).`
      + (sinContar ? ` Los ${sinContar} sin contar no se tocan.` : ''))) return;
    setTrabajando(true);
    try { const { data } = await api.inventario.aplicarConteo(slug, id); tomar(data); toast.success('Conteo aplicado: el stock quedó como lo contado.'); }
    catch (e) { toast.error(msg(e, 'No se pudo aplicar.')); }
    setTrabajando(false);
  };
  const cancelar = async () => {
    if (!window.confirm(`¿Cancelar el conteo ${c.numero}? No se ajusta nada.`)) return;
    try { const { data } = await api.inventario.cancelarConteo(slug, id); tomar(data); } catch (e) { toast.error(msg(e, 'No se pudo cancelar.')); }
  };
  const subirPlanilla = async (archivo) => {
    setTrabajando(true);
    try { const { data } = await api.inventario.subirPlanillaConteo(slug, id, archivo); tomar(data); toast.success('Planilla cargada.'); }
    catch (e) { toast.error(msg(e, 'No se pudo leer la planilla.')); }
    setTrabajando(false);
  };
  const avance = c.lineas.length ? Math.round((c.contadas / c.lineas.length) * 100) : 0;

  return (
    <Box sx={{ display: 'grid', gap: 1.5 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
        <Button size="small" startIcon={<ArrowLeft size={14} />} onClick={() => navigate('/app/inventario/conteos')}>Conteos</Button>
        <Typography sx={{ fontWeight: 600, fontSize: '1.05rem' }}>{c.numero}</Typography>
        <Typography sx={{ fontSize: '0.84rem', color: 'text.secondary' }}>
          {fecha(c.fecha)} · {[c.bodega || 'Todas las bodegas', c.familia].filter(Boolean).join(' · ')} · {c.estado_nombre}
        </Typography>
        <Box sx={{ flex: 1 }} />
        <Button size="small" startIcon={<Download size={14} />} onClick={() => descargar(api.inventario.planillaConteo(slug, id), `Conteo ${c.numero}.xlsx`)}>Planilla</Button>
        {editable && (
          <>
            <Button component="label" size="small" startIcon={<Upload size={14} />} disabled={trabajando}>
              Subir planilla<input hidden type="file" accept=".xlsx,.csv" onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ''; if (f) subirPlanilla(f); }} />
            </Button>
            <Button size="small" color="inherit" onClick={cancelar}>Cancelar conteo</Button>
            <Button size="small" variant="contained" startIcon={<Check size={14} />} onClick={aplicar} disabled={trabajando || !c.contadas}>Aplicar</Button>
          </>
        )}
      </Box>

      <Tarjeta sx={{ p: 2, display: 'grid', gridTemplateColumns: { xs: '1fr 1fr', md: 'repeat(4, 1fr)' }, gap: 2 }}>
        <Box><Typography sx={{ fontSize: '0.74rem', color: 'text.secondary' }}>Avance</Typography>
          <Typography sx={{ fontWeight: 600, ...NUM }}>{c.contadas} de {c.lineas.length} · {avance}%</Typography>
          <LinearProgress variant="determinate" value={avance} sx={{ mt: 0.75, height: 6, borderRadius: 3 }} /></Box>
        <Box><Typography sx={{ fontSize: '0.74rem', color: 'text.secondary' }}>Con diferencia</Typography>
          <Typography sx={{ fontWeight: 600, ...NUM }}>{c.con_diferencia}</Typography></Box>
        <Box><Typography sx={{ fontSize: '0.74rem', color: 'text.secondary' }}>Valor de la diferencia</Typography>
          <Typography sx={{ fontWeight: 600, ...NUM, color: c.valor_diferencia < 0 ? '#c8102e' : 'text.primary' }}>{clp(c.valor_diferencia)}</Typography></Box>
        <Box><Typography sx={{ fontSize: '0.74rem', color: 'text.secondary' }}>Sin contar</Typography>
          <Typography sx={{ fontWeight: 600, ...NUM }}>{c.lineas.length - c.contadas}</Typography></Box>
      </Tarjeta>

      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', alignItems: 'center' }}>
        <InputBase autoFocus placeholder="Buscar o escanear el código y Enter" value={buscar} onChange={(e) => setBuscar(e.target.value)} onKeyDown={alBuscar}
          startAdornment={<ScanLine size={15} style={{ marginRight: 6, opacity: 0.55 }} />}
          sx={{ border: '1px solid', borderColor: 'divider', borderRadius: '8px', px: 1.25, py: 0.4, fontSize: '0.88rem', minWidth: 300, bgcolor: 'background.paper' }} />
        <Select size="small" value={ver} onChange={(e) => setVer(e.target.value)} sx={{ fontSize: '0.84rem' }}>
          <MenuItem value="todos">Todos</MenuItem>
          <MenuItem value="sin_contar">Sin contar</MenuItem>
          <MenuItem value="diferencia">Con diferencia</MenuItem>
        </Select>
      </Box>

      <Tarjeta sx={{ overflowX: 'auto' }}>
        <Table size="small" sx={{ '& td, & th': { fontSize: '0.84rem', whiteSpace: 'nowrap' }, '& th': { color: 'text.secondary', fontWeight: 500 } }}>
          <TableHead>
            <TableRow>
              <TableCell>Producto</TableCell><TableCell>Ubicación</TableCell><TableCell>Bodega</TableCell>
              <TableCell align="right">Sistema</TableCell><TableCell align="right" sx={{ width: 140 }}>Contado</TableCell>
              <TableCell align="right">Diferencia</TableCell><TableCell align="right">Valor</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {filas.map((l) => {
              const dif = l.contada == null ? null : Number(l.diferencia);
              return (
                <TableRow key={l.id} hover>
                  <TableCell sx={{ maxWidth: 300 }}>
                    <Box sx={{ fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis' }}>{l.nombre}</Box>
                    <Typography component="span" sx={{ fontSize: '0.72rem', color: 'text.secondary' }}>{[l.codigo, l.codigo_barras].filter(Boolean).join(' · ') || l.unidad}</Typography>
                  </TableCell>
                  <TableCell sx={{ color: 'text.secondary' }}>{l.ubicacion || '—'}</TableCell>
                  <TableCell>{l.bodega}</TableCell>
                  <TableCell align="right" sx={NUM}>{cant(l.sistema)}</TableCell>
                  <TableCell align="right">
                    {editable ? (
                      <InputBase inputRef={(el) => { refs.current[l.id] = el; }} value={valores[l.id] ?? ''} placeholder="—"
                        inputProps={{ 'aria-label': `Contado de ${l.nombre}`, style: { textAlign: 'right' } }}
                        onChange={(e) => setValores((v) => ({ ...v, [l.id]: e.target.value.replace(/[^\d,]/g, '') }))}
                        onBlur={() => guardarLinea(l)}
                        onKeyDown={(e) => { if (e.key === 'Enter') { e.currentTarget.blur(); setBuscar(''); } }}
                        sx={{ width: 110, border: '1px solid', borderColor: l.contada == null ? 'divider' : 'text.primary', borderRadius: '6px', px: 1, fontSize: '0.88rem', ...NUM }} />
                    ) : (l.contada == null ? '—' : cant(l.contada))}
                  </TableCell>
                  <TableCell align="right" sx={{ ...NUM, fontWeight: dif ? 600 : 400, color: dif == null ? 'text.disabled' : dif < 0 ? '#c8102e' : dif > 0 ? '#0f9d6b' : 'text.secondary' }}>
                    {dif == null ? '—' : `${dif > 0 ? '+' : ''}${cant(l.diferencia)}`}
                  </TableCell>
                  <TableCell align="right" sx={{ ...NUM, color: 'text.secondary' }}>{dif ? clp(l.valor_diferencia) : '—'}</TableCell>
                </TableRow>
              );
            })}
            {filas.length === 0 && <TableRow><TableCell colSpan={7} sx={{ color: 'text.secondary' }}>Nada con ese filtro.</TableCell></TableRow>}
          </TableBody>
        </Table>
      </Tarjeta>
    </Box>
  );
}

export default function Conteos({ slug, esEditor, id }) {
  return id ? <Detalle key={id} slug={slug} id={id} esEditor={esEditor} /> : <Lista slug={slug} esEditor={esEditor} />;
}
