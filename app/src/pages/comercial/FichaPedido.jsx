import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Alert, Autocomplete, Box, Button, Checkbox, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle,
  IconButton, InputBase, Menu, MenuItem, Select, Table, TableBody, TableCell, TableHead, TableRow, TextField,
  Tooltip, Typography,
} from '@mui/material';
import {
  ArrowLeft, Check, Download, FileText, Mail, MoreHorizontal, PackageCheck, Plus, Receipt, Trash2, Truck, Wallet, X,
} from 'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../../services/api';
import { usePantalla } from '../../layout/Dashboard/PanelLateral';
import { BuscadorContacto, ChipEtapa, NUM, SORA, Tarjeta, aNumero, cant, clp, descargar, dinero, fecha } from './comun';
import { conPasos } from '../../components/ProgresoFlotante';

/*
 * La ficha de una cotización u orden (22-10-2026), al estilo Odoo: arriba la barra de etapas y
 * las acciones que tocan ahora; al medio la cabecera y las líneas; abajo las entregas y las
 * facturas del SII vinculadas. Mientras es cotización se edita todo; confirmada, las cantidades
 * y precios quedan fijos (para cambiarlos se vuelve a borrador, si no tiene entregas ni facturas).
 */

const campoSx = { border: '1px solid', borderColor: 'divider', borderRadius: '8px', px: 1, py: 0.25, fontSize: '0.86rem', bgcolor: 'background.paper' };
const ETAPAS = {
  venta: ['Cotización', 'Cotización enviada', 'Orden de venta', 'Entregada', 'Facturada'],
  compra: ['Solicitud de cotización', 'Solicitud enviada', 'Orden de compra', 'Recibida', 'Facturada'],
};

function BarraEtapas({ p }) {
  const etapas = ETAPAS[p.tipo];
  // Las etapas intermedias ("Entrega parcial", "Facturada, falta entregar") caen en su escalón.
  const normal = { 'Entrega parcial': 2, 'Recepción parcial': 2, 'Facturada, falta entregar': 4, 'Facturada, falta recibir': 4 };
  const actual = p.estado === 'cancelado' ? -1 : (normal[p.etapa] ?? etapas.indexOf(p.etapa));
  return (
    <Box sx={{ display: 'flex', borderRadius: '10px', overflow: 'hidden', border: '1px solid', borderColor: 'divider', bgcolor: 'background.paper' }}>
      {etapas.map((e, i) => (
        <Box key={e} sx={{
          flex: 1, px: 1.25, py: 0.75, textAlign: 'center', fontSize: '0.78rem', whiteSpace: 'nowrap',
          borderRight: i < etapas.length - 1 ? '1px solid' : 'none', borderColor: 'divider',
          bgcolor: i === actual ? 'var(--af-color)' : 'transparent',
          color: i === actual ? '#fff' : i < actual ? 'text.primary' : 'text.disabled', fontWeight: i === actual ? 600 : 400,
        }}>
          {i < actual && <Check size={11} style={{ marginRight: 4, verticalAlign: -1 }} />}{e}
        </Box>
      ))}
    </Box>
  );
}

function Campo({ etiqueta, children }) {
  return (
    <Box>
      <Typography sx={{ fontSize: '0.74rem', color: 'text.secondary', mb: 0.4 }}>{etiqueta}</Typography>
      {children}
    </Box>
  );
}

/* Registrar una entrega (venta) o recepción (compra): cuánto de cada línea, por defecto todo lo pendiente. */
/* La guía de despacho electrónica de una entrega (26-10-2026): sale con el facturador nativo,
   con los datos de transporte si se conocen (si no, el destino es la dirección del cliente). */
function DialogoGuia({ p, entrega, slug, onCerrar, onHecho }) {
  const [datos, setDatos] = useState({ patente: '', rut_transportista: '', direccion_destino: '', comuna_destino: '' });
  const [enviando, setEnviando] = useState(false);
  const emitir = async () => {
    setEnviando(true);
    try {
      const { data } = await api.comercial.emitirGuia(slug, p.id, entrega.id, datos);
      const hecha = data.entregas.find((x) => x.id === entrega.id);
      toast.success(`Guía de despacho N° ${hecha?.folio_guia} emitida.`);
      onHecho(data);
    } catch (e) { toast.error(e.response?.data?.detail || 'No se pudo emitir la guía.'); }
    setEnviando(false);
  };
  const campo = (k, rotulo, ayuda) => (
    <Box>
      <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary', mb: 0.5 }}>{rotulo}</Typography>
      <InputBase value={datos[k]} placeholder={ayuda} onChange={(e) => setDatos((d) => ({ ...d, [k]: e.target.value }))}
        sx={{ ...campoSx, width: '100%' }} />
    </Box>
  );
  return (
    <Dialog open onClose={onCerrar} maxWidth="xs" fullWidth>
      <DialogTitle sx={{ fontWeight: 600 }}>Guía de despacho · {entrega.numero}</DialogTitle>
      <DialogContent sx={{ display: 'grid', gap: 1.5 }}>
        <Typography sx={{ fontSize: '0.82rem', color: 'text.secondary', lineHeight: 1.5 }}>
          {entrega.tipo === 'devolucion' ? 'Guía de devolución' : 'Guía de venta'} con lo de esta {entrega.tipo === 'devolucion' ? 'devolución' : 'entrega'}.
          El transporte es opcional: sin destino, va la dirección de {p.contacto_nombre || 'el cliente'}.
        </Typography>
        {campo('patente', 'Patente (opcional)', 'AB1234')}
        {campo('rut_transportista', 'RUT del transportista (opcional)', '')}
        {campo('direccion_destino', 'Dirección de destino (opcional)', '')}
        {campo('comuna_destino', 'Comuna de destino (opcional)', '')}
      </DialogContent>
      <DialogActions>
        <Button color="inherit" onClick={onCerrar}>Cancelar</Button>
        <Button variant="contained" disabled={enviando} onClick={emitir}>{enviando ? 'Emitiendo…' : 'Emitir guía'}</Button>
      </DialogActions>
    </Dialog>
  );
}

function DialogoEntrega({ p, slug, bodegas, onCerrar, onHecho }) {
  const venta = p.tipo === 'venta';
  const pendientes = p.lineas.filter((l) => Number(l.pendiente) > 0);
  const [cants, setCants] = useState(Object.fromEntries(pendientes.map((l) => [l.id, cant(l.pendiente)])));
  const [hoy] = useState(new Date().toISOString().slice(0, 10));
  const [datos, setDatos] = useState({ fecha: hoy, bodega: p.bodega || '', folio_guia: '', notas: '' });
  const [enviando, setEnviando] = useState(false);
  const guardar = async () => {
    setEnviando(true);
    try {
      const cantidades = Object.fromEntries(Object.entries(cants).map(([k, v]) => [k, aNumero(v) || '0']));
      const { data } = await api.comercial.entregar(slug, p.id, { ...datos, bodega: datos.bodega || undefined, cantidades });
      toast.success(venta ? 'Entrega registrada.' : 'Recepción registrada.');
      onHecho(data);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'No se pudo registrar.');
      setEnviando(false);
    }
  };
  return (
    <Dialog open onClose={onCerrar} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ fontWeight: 600 }}>{venta ? 'Registrar entrega' : 'Registrar recepción'} · {p.numero}</DialogTitle>
      <DialogContent>
        <Table size="small" sx={{ mb: 2, '& td, & th': { fontSize: '0.84rem', borderColor: 'divider' } }}>
          <TableHead>
            <TableRow sx={{ '& th': { color: 'text.secondary' } }}>
              <TableCell>Producto</TableCell><TableCell align="right">Pendiente</TableCell>
              <TableCell align="right">{venta ? 'Entregar ahora' : 'Recibido ahora'}</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {pendientes.map((l) => (
              <TableRow key={l.id}>
                <TableCell>{l.descripcion}</TableCell>
                <TableCell align="right">{cant(l.pendiente)} {l.unidad}</TableCell>
                <TableCell align="right">
                  <InputBase value={cants[l.id]} onChange={(e) => setCants((c) => ({ ...c, [l.id]: e.target.value.replace(/[^\d,]/g, '') }))}
                    inputProps={{ style: { textAlign: 'right' }, 'aria-label': `Cantidad de ${l.descripcion}` }} sx={{ ...campoSx, width: 90 }} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, gap: 1.5 }}>
          <Campo etiqueta="Fecha">
            <InputBase type="date" value={datos.fecha} onChange={(e) => setDatos((d) => ({ ...d, fecha: e.target.value }))} sx={{ ...campoSx, width: '100%' }} />
          </Campo>
          {p.con_inventario && bodegas.length > 1 && (
            <Campo etiqueta="Bodega">
              <Select size="small" fullWidth value={datos.bodega || ''} onChange={(e) => setDatos((d) => ({ ...d, bodega: e.target.value }))} sx={{ fontSize: '0.86rem' }}>
                {bodegas.filter((b) => b.activa).map((b) => <MenuItem key={b.id} value={b.id}>{b.nombre}</MenuItem>)}
              </Select>
            </Campo>
          )}
          <Campo etiqueta={venta ? 'Folio de la guía de despacho (opcional)' : 'Folio de la guía del proveedor (opcional)'}>
            <InputBase value={datos.folio_guia} onChange={(e) => setDatos((d) => ({ ...d, folio_guia: e.target.value }))} sx={{ ...campoSx, width: '100%' }} />
          </Campo>
          <Campo etiqueta="Notas">
            <InputBase value={datos.notas} onChange={(e) => setDatos((d) => ({ ...d, notas: e.target.value }))} sx={{ ...campoSx, width: '100%' }} />
          </Campo>
        </Box>
        {!p.con_inventario && (
          <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary', mt: 1.5 }}>
            El inventario está desactivado: se registran las cantidades, sin mover stock. Se activa en la configuración.
          </Typography>
        )}
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onCerrar}>Cancelar</Button>
        <Button variant="contained" onClick={guardar} disabled={enviando}>Registrar</Button>
      </DialogActions>
    </Dialog>
  );
}

/* Las facturas del SII de ese RUT que podrían ser de este pedido. */
function DialogoFacturas({ p, slug, onCerrar, onHecho }) {
  const [candidatas, setCandidatas] = useState(null);
  const [montos, setMontos] = useState({});
  useEffect(() => {
    api.comercial.candidatas(slug, p.id).then(({ data }) => {
      setCandidatas(data);
      const pendiente = Math.max(p.base_clp - p.facturado_clp, 0);
      setMontos(Object.fromEntries(data.map((c) => [c.documento, String(c.disponible < 0 ? c.disponible : Math.min(c.disponible, pendiente || c.disponible))])));
    });
  }, [slug, p.id, p.base_clp, p.facturado_clp]);
  const vincular = async (doc) => {
    try {
      const { data } = await api.comercial.vincular(slug, p.id, { documento: doc, monto: montos[doc] });
      toast.success('Factura vinculada.');
      onHecho(data);
    } catch (e) { toast.error(e.response?.data?.detail || 'No se pudo vincular.'); }
  };
  return (
    <Dialog open onClose={onCerrar} maxWidth="md" fullWidth>
      <DialogTitle sx={{ fontWeight: 600 }}>Vincular factura del SII · {p.numero}</DialogTitle>
      <DialogContent>
        <Typography sx={{ fontSize: '0.84rem', color: 'text.secondary', mb: 1.5 }}>
          Facturas de {p.contacto_nombre} cargadas desde el Registro de {p.tipo === 'venta' ? 'Ventas' : 'Compras'}, la más parecida primero.
          Montos sin IVA. Falta por facturar {clp(Math.max(p.base_clp - p.facturado_clp, 0))}.
        </Typography>
        {!candidatas ? <CircularProgress size={18} /> : candidatas.length === 0 ? (
          <Typography sx={{ fontSize: '0.86rem', py: 2 }}>
            No hay facturas de este {p.tipo === 'venta' ? 'cliente' : 'proveedor'} sin vincular. Cargue el Registro de {p.tipo === 'venta' ? 'Ventas' : 'Compras'} en Contabilidad › Documentos: si una cuadra con esta orden, se vincula sola.
          </Typography>
        ) : (
          <Box sx={{ overflowX: 'auto' }}>
          <Table size="small" sx={{ '& td, & th': { fontSize: '0.84rem', borderColor: 'divider', whiteSpace: 'nowrap' } }}>
            <TableHead>
              <TableRow sx={{ '& th': { color: 'text.secondary' } }}>
                <TableCell>Documento</TableCell><TableCell>Fecha</TableCell><TableCell align="right">Sin vincular</TableCell>
                <TableCell align="right">Monto para esta orden</TableCell><TableCell />
              </TableRow>
            </TableHead>
            <TableBody>
              {candidatas.map((c) => (
                <TableRow key={c.documento}>
                  <TableCell>{c.tipo_documento === '61' ? 'NC' : 'Factura'} {c.folio}</TableCell>
                  <TableCell>{fecha(c.fecha)}</TableCell>
                  <TableCell align="right" sx={NUM}>{clp(c.disponible)}</TableCell>
                  <TableCell align="right">
                    <InputBase value={montos[c.documento] ?? ''} onChange={(e) => setMontos((m) => ({ ...m, [c.documento]: e.target.value.replace(/[^\d-]/g, '') }))}
                      inputProps={{ style: { textAlign: 'right' } }} sx={{ ...campoSx, width: 110 }} />
                  </TableCell>
                  <TableCell><Button size="small" onClick={() => vincular(c.documento)}>Vincular</Button></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          </Box>
        )}
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}><Button onClick={onCerrar}>Cerrar</Button></DialogActions>
    </Dialog>
  );
}

/* Una devolución: lo que el cliente devuelve, o lo que se le devuelve al proveedor. */
function DialogoDevolucion({ p, slug, onCerrar, onHecho }) {
  const venta = p.tipo === 'venta';
  const entregadas = p.lineas.filter((l) => Number(l.cantidad_entregada) > 0);
  const [cants, setCants] = useState(Object.fromEntries(entregadas.map((l) => [l.id, ''])));
  const [notas, setNotas] = useState('');
  const [enviando, setEnviando] = useState(false);
  const guardar = async () => {
    setEnviando(true);
    try {
      const cantidades = Object.fromEntries(Object.entries(cants).filter(([, v]) => v).map(([k, v]) => [k, aNumero(v)]));
      const { data } = await api.comercial.devolver(slug, p.id, { cantidades, notas });
      toast.success('Devolución registrada.');
      onHecho(data);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'No se pudo registrar.');
      setEnviando(false);
    }
  };
  return (
    <Dialog open onClose={onCerrar} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ fontWeight: 600 }}>{venta ? 'Devolución del cliente' : 'Devolución al proveedor'} · {p.numero}</DialogTitle>
      <DialogContent>
        <Typography sx={{ fontSize: '0.84rem', color: 'text.secondary', mb: 1 }}>
          {venta ? 'Lo que el cliente devuelve vuelve a bodega' : 'Lo que se le devuelve al proveedor sale de bodega'} y
          se resta de lo {venta ? 'entregado' : 'recibido'}. Si corresponde una nota de crédito, se vincula cuando llegue del SII.
        </Typography>
        <Box sx={{ overflowX: 'auto' }}>
          <Table size="small" sx={{ mb: 2, '& td, & th': { fontSize: '0.84rem', borderColor: 'divider' } }}>
            <TableHead>
              <TableRow sx={{ '& th': { color: 'text.secondary' } }}>
                <TableCell>Producto</TableCell><TableCell align="right">{venta ? 'Entregado' : 'Recibido'}</TableCell>
                <TableCell align="right">Devuelve</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {entregadas.map((l) => (
                <TableRow key={l.id}>
                  <TableCell>{l.descripcion}</TableCell>
                  <TableCell align="right">{cant(l.cantidad_entregada)} {l.unidad}</TableCell>
                  <TableCell align="right">
                    <InputBase value={cants[l.id]} placeholder="0" onChange={(e) => setCants((c) => ({ ...c, [l.id]: e.target.value.replace(/[^\d,]/g, '') }))}
                      inputProps={{ style: { textAlign: 'right' }, 'aria-label': `Devuelve de ${l.descripcion}` }} sx={{ ...campoSx, width: 90 }} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Box>
        <TextField size="small" fullWidth label="Motivo (opcional)" value={notas} onChange={(e) => setNotas(e.target.value)} placeholder="Producto dañado, error de despacho…" />
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onCerrar}>Cancelar</Button>
        <Button variant="contained" onClick={guardar} disabled={enviando || !Object.values(cants).some((v) => Number(aNumero(v)) > 0)}>Registrar</Button>
      </DialogActions>
    </Dialog>
  );
}

const MEDIOS = [['transferencia', 'Transferencia'], ['efectivo', 'Efectivo'], ['tarjeta', 'Tarjeta'], ['cheque', 'Cheque'], ['otro', 'Otro']];

/* Un cobro (orden de venta) o un pago (orden de compra), en pesos y con IVA. */
function DialogoPago({ p, slug, onCerrar, onHecho }) {
  const venta = p.tipo === 'venta';
  const [datos, setDatos] = useState({ monto: String(p.por_pagar_clp), fecha: new Date().toISOString().slice(0, 10), medio: 'transferencia', referencia: '' });
  const [enviando, setEnviando] = useState(false);
  const cambiar = (k, v) => setDatos((d) => ({ ...d, [k]: v }));
  const guardar = async () => {
    setEnviando(true);
    try {
      const { data } = await api.comercial.pagar(slug, p.id, { ...datos, monto: aNumero(datos.monto) });
      toast.success(venta ? 'Cobro registrado.' : 'Pago registrado.');
      onHecho(data);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'No se pudo registrar.');
      setEnviando(false);
    }
  };
  return (
    <Dialog open onClose={onCerrar} maxWidth="xs" fullWidth>
      <DialogTitle sx={{ fontWeight: 600 }}>{venta ? 'Registrar cobro' : 'Registrar pago'} · {p.numero}</DialogTitle>
      <DialogContent sx={{ display: 'grid', gap: 1.5, pt: '8px !important' }}>
        <TextField size="small" label="Monto (con IVA)" value={datos.monto} autoFocus
          onChange={(e) => cambiar('monto', e.target.value.replace(/[^\d]/g, ''))}
          helperText={`Falta ${venta ? 'cobrar' : 'pagar'} ${clp(p.por_pagar_clp)} de ${clp(p.total_clp)}.`} />
        <TextField size="small" type="date" label="Fecha" value={datos.fecha} onChange={(e) => cambiar('fecha', e.target.value)} InputLabelProps={{ shrink: true }} />
        <TextField size="small" select label="Medio" value={datos.medio} onChange={(e) => cambiar('medio', e.target.value)}>
          {MEDIOS.map(([v, n]) => <MenuItem key={v} value={v}>{n}</MenuItem>)}
        </TextField>
        <TextField size="small" label="Referencia (opcional)" value={datos.referencia} onChange={(e) => cambiar('referencia', e.target.value)} placeholder="N° de transferencia, cheque…" />
        <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary' }}>
          Con la orden {venta ? 'cobrada' : 'pagada'} completa, sus facturas del SII quedan pagadas en Finanzas.
        </Typography>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onCerrar}>Cancelar</Button>
        <Button variant="contained" onClick={guardar} disabled={enviando || !Number(datos.monto)}>Registrar</Button>
      </DialogActions>
    </Dialog>
  );
}

function DialogoCorreo({ p, slug, onCerrar, onHecho }) {
  const [para, setPara] = useState(p.contacto_email || '');
  const [mensaje, setMensaje] = useState('');
  const [enviando, setEnviando] = useState(false);
  const enviar = async () => {
    setEnviando(true);
    try {
      const { data } = await api.comercial.enviarCorreo(slug, p.id, { para, mensaje });
      toast.success(`Enviado a ${para}.`);
      onHecho(data);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'No se pudo enviar.');
      setEnviando(false);
    }
  };
  return (
    <Dialog open onClose={onCerrar} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ fontWeight: 600 }}>Enviar {p.numero} por correo</DialogTitle>
      <DialogContent sx={{ display: 'grid', gap: 1.5 }}>
        <TextField size="small" label="Para" value={para} onChange={(e) => setPara(e.target.value)} sx={{ mt: 1 }} />
        <TextField size="small" label="Mensaje (opcional)" multiline minRows={4} value={mensaje} onChange={(e) => setMensaje(e.target.value)}
          placeholder="Si lo deja vacío, va un saludo breve con el PDF adjunto." />
        <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary' }}>Va con el PDF adjunto. Las respuestas le llegan a usted.</Typography>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onCerrar}>Cancelar</Button>
        <Button variant="contained" startIcon={<Mail size={14} />} onClick={enviar} disabled={!para || enviando}>Enviar</Button>
      </DialogActions>
    </Dialog>
  );
}

const lineaVacia = () => ({ clave: Math.random().toString(36).slice(2), producto: null, descripcion: '', cantidad: '1', unidad: 'un', precio_unitario: '', descuento_pct: '', exento: false });
const deServidor = (l) => ({ ...l, clave: String(l.id), cantidad: cant(l.cantidad), precio_unitario: cant(l.precio_unitario), descuento_pct: Number(l.descuento_pct) ? cant(l.descuento_pct) : '' });

export default function FichaPedido({ slug, id, modulo, seccion, esEditor }) {
  const navigate = useNavigate();
  const [p, setP] = useState(null);
  const [cab, setCab] = useState({});
  const [lineas, setLineas] = useState([]);
  const [sucio, setSucio] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [productos, setProductos] = useState([]);
  const [proyectos, setProyectos] = useState([]);
  const [bodegas, setBodegas] = useState([]);
  const [dialogo, setDialogo] = useState(null);
  const [guia, setGuia] = useState(null);
  const [menu, setMenu] = useState(null);
  const [menuEmitir, setMenuEmitir] = useState(null);   // el ancla del menú «Emitir factura»

  const aplicar = useCallback((data) => {
    setP(data);
    setCab({
      contacto: data.contacto, fecha: data.fecha, valida_hasta: data.valida_hasta || '', fecha_compromiso: data.fecha_compromiso || '',
      plazo_dias: data.plazo_dias ?? '', referencia: data.referencia, moneda: data.moneda, tipo_cambio: cant(data.tipo_cambio),
      proyecto: data.proyecto || '', bodega: data.bodega || '', notas: data.notas, condiciones: data.condiciones,
    });
    setLineas(data.lineas.map(deServidor));
    setSucio(false);
  }, []);
  useEffect(() => {
    api.comercial.pedido(slug, id).then(({ data }) => aplicar(data)).catch(() => setP(false));
  }, [slug, id, aplicar]);
  useEffect(() => {
    if (!p) return;
    api.comercial.productos(slug, { activos: 1, uso: p.tipo }).then(({ data }) => setProductos(data));
    api.finanzas.proyectos(slug).then(({ data }) => setProyectos(data)).catch(() => {});
    if (p.con_inventario) api.comercial.bodegas(slug).then(({ data }) => setBodegas(data));
  }, [slug, p?.tipo, p?.con_inventario]); // eslint-disable-line react-hooks/exhaustive-deps
  usePantalla(p ? `${p.numero} (${p.etapa}, ${p.contacto_nombre})` : '');

  const totales = useMemo(() => {
    let neto = 0; let exento = 0;
    for (const l of lineas) {
      const bruto = Number(aNumero(l.cantidad) || 0) * Number(aNumero(l.precio_unitario) || 0);
      const sub = bruto - (bruto * Number(aNumero(l.descuento_pct) || 0)) / 100;
      if (l.exento) exento += sub; else neto += sub;
    }
    return { neto, exento, iva: neto * 0.19, total: neto * 1.19 + exento };
  }, [lineas]);

  if (p === null) return <CircularProgress size={20} sx={{ m: 'auto', mt: 6 }} />;
  if (p === false) return <Typography sx={{ color: 'text.secondary', mt: 4 }}>No existe o no tiene acceso.</Typography>;

  const venta = p.tipo === 'venta';
  const editable = esEditor && p.editable;
  const libre = esEditor && p.estado !== 'cancelado';         // lo que se cambia aun confirmado
  const cambiarCab = (k, v) => { setCab((c) => ({ ...c, [k]: v })); setSucio(true); };
  const cambiarLinea = (clave, k, v) => { setLineas((ls) => ls.map((l) => (l.clave === clave ? { ...l, [k]: v } : l))); setSucio(true); };
  const elegirProducto = (clave, prod) => {
    setLineas((ls) => ls.map((l) => (l.clave !== clave ? l : prod ? {
      ...l, producto: prod.id, descripcion: prod.nombre, unidad: prod.unidad, exento: prod.exento,
      precio_unitario: cant(venta ? prod.precio_venta : prod.costo),
    } : { ...l, producto: null })));
    setSucio(true);
  };

  const guardar = async () => {
    setGuardando(true);
    try {
      const datos = editable ? {
        ...cab, tipo_cambio: aNumero(cab.tipo_cambio), proyecto: cab.proyecto || null, bodega: cab.bodega || null,
        lineas: lineas.filter((l) => l.descripcion.trim()).map((l) => ({
          producto: l.producto, descripcion: l.descripcion, cantidad: aNumero(l.cantidad) || '0', unidad: l.unidad,
          precio_unitario: aNumero(l.precio_unitario) || '0', descuento_pct: aNumero(l.descuento_pct) || '0', exento: l.exento,
        })),
      } : { fecha_compromiso: cab.fecha_compromiso, referencia: cab.referencia, notas: cab.notas, proyecto: cab.proyecto || null, bodega: cab.bodega || null };
      const { data } = await api.comercial.actualizarPedido(slug, p.id, datos);
      aplicar(data);
      toast.success('Guardado.');
      return true;
    } catch (e) {
      toast.error(e.response?.data?.detail || 'No se pudo guardar.');
      return false;
    } finally { setGuardando(false); }
  };
  const accion = async (a, extra = {}) => {
    setMenu(null);
    setMenuEmitir(null);
    if (sucio && !(await guardar())) return;
    try {
      const llamar = () => api.comercial.accion(slug, p.id, a, extra);
      const { data } = a === 'emitir'
        ? await conPasos(['Armando la factura', 'Firmando', 'Enviando al SII'], llamar)
        : await llamar();
      if (a === 'duplicar') {
        toast.success(`Listo: ${data.numero} es una copia de ${p.numero}.`);
        navigate(`/app/${modulo}/cotizaciones/${data.id}`);
        return;
      }
      aplicar(data);
      if (a === 'confirmar') toast.success(venta ? 'Confirmada: ahora es orden de venta.' : 'Confirmada: ahora es orden de compra.');
      // La dirección sigue a lo que el documento es ahora (cotización u orden).
      const destino = data.estado === 'confirmado' ? 'ordenes' : 'cotizaciones';
      if (seccion !== destino && (seccion === 'ordenes' || seccion === 'cotizaciones')) {
        navigate(`/app/${modulo}/${destino}/${p.id}`, { replace: true });
      }
    } catch (e) { toast.error(e.response?.data?.detail || 'No se pudo.'); }
  };
  const borrar = async () => {
    setMenu(null);
    try {
      await api.comercial.borrarPedido(slug, p.id);
      navigate(`/app/${modulo}/cotizaciones`);
    } catch (e) { toast.error(e.response?.data?.detail || 'No se pudo borrar.'); }
  };
  const verPdf = async () => {
    if (sucio && !(await guardar())) return;
    await descargar(api.comercial.pdf(slug, p.id), `${p.numero}.pdf`);
  };
  const traerCambio = async (moneda) => {
    try {
      const { data } = await api.comercial.tipoCambio(slug, moneda, cab.fecha);
      cambiarCab('tipo_cambio', cant(data.valor));
    } catch (e) { toast.error(e.response?.data?.detail || 'No se pudo traer el tipo de cambio.'); }
  };
  const anular = async (entrega) => {
    try {
      const { data } = await api.comercial.anularEntrega(slug, entrega);
      aplicar(data);
    } catch (e) { toast.error(e.response?.data?.detail || 'No se pudo anular.'); }
  };
  const desvincular = async (doc) => {
    try {
      const { data } = await api.comercial.desvincular(slug, p.id, doc);
      aplicar(data);
    } catch (e) { toast.error(e.response?.data?.detail || 'No se pudo desvincular.'); }
  };
  const borrarPago = async (pago) => {
    try {
      const { data } = await api.comercial.borrarPago(slug, p.id, pago);
      aplicar(data);
    } catch (e) { toast.error(e.response?.data?.detail || 'No se pudo borrar.'); }
  };

  const pendienteEntrega = p.lineas.some((l) => Number(l.pendiente) > 0);
  const esOrden = p.estado === 'confirmado';
  const entregasHechas = p.entregas.filter((e) => e.estado === 'hecha' && e.tipo !== 'devolucion');
  const algoEntregado = p.lineas.some((l) => Number(l.cantidad_entregada) > 0);

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, maxWidth: 1180 }}>
      {/* Acciones */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
        <IconButton size="small" onClick={() => navigate(`/app/${modulo}/${seccion}`)} aria-label="Volver"><ArrowLeft size={16} /></IconButton>
        <Typography sx={{ fontFamily: SORA, fontWeight: 600, fontSize: '1.35rem' }}>{p.numero}</Typography>
        <ChipEtapa etapa={p.etapa} />
        <Box sx={{ flex: 1 }} />
        {sucio && <Button variant="contained" size="small" onClick={guardar} disabled={guardando}>Guardar</Button>}
        {esEditor && !esOrden && p.estado !== 'cancelado' && (
          <>
            <Button size="small" variant="outlined" startIcon={<Mail size={14} />} onClick={() => setDialogo('correo')}>Enviar</Button>
            <Button size="small" variant={sucio ? 'outlined' : 'contained'} startIcon={<Check size={14} />} onClick={() => accion('confirmar')}>Confirmar</Button>
          </>
        )}
        {esEditor && esOrden && pendienteEntrega && (
          <Button size="small" variant="contained" startIcon={venta ? <Truck size={14} /> : <PackageCheck size={14} />} onClick={() => setDialogo('entrega')}>
            {venta ? 'Registrar entrega' : 'Registrar recepción'}
          </Button>
        )}
        {esEditor && esOrden && p.por_pagar_clp > 0 && (
          <Button size="small" variant="outlined" startIcon={<Wallet size={14} />} onClick={() => setDialogo('pago')}>
            {venta ? 'Registrar cobro' : 'Registrar pago'}
          </Button>
        )}
        {esEditor && esOrden && (
          <Button size="small" variant="outlined" startIcon={<Receipt size={14} />} onClick={() => setDialogo('facturas')}>Vincular factura</Button>
        )}
        {esEditor && esOrden && venta && p.emision_disponible && (() => {
          // Facturar lo vendido o lo entregado (25-10-2026): si se entregó una parte, se elige en un
          // menú con los dos montos; si hay una sola opción, el botón la emite directo.
          const f = p.facturable || { vendido: 0, entregado: 0 };
          const opciones = [
            { que: 'vendido', texto: 'Facturar lo vendido', monto: f.vendido },
            { que: 'entregado', texto: 'Facturar lo entregado', monto: f.entregado },
          ].filter((o) => o.monto > 0 && !(o.que === 'entregado' && o.monto === f.vendido));
          if (!opciones.length) return null;
          return (
            <>
              <Button size="small" variant="outlined" startIcon={<FileText size={14} />}
                onClick={(e) => (opciones.length > 1 ? setMenuEmitir(e.currentTarget) : accion('emitir', { que: opciones[0].que }))}>
                Emitir factura
              </Button>
              <Menu anchorEl={menuEmitir} open={Boolean(menuEmitir)} onClose={() => setMenuEmitir(null)}>
                {opciones.map((o) => (
                  <MenuItem key={o.que} onClick={() => accion('emitir', { que: o.que })} sx={{ fontSize: '0.86rem', gap: 3 }}>
                    <span>{o.texto}</span><span style={{ marginLeft: 'auto', fontVariantNumeric: 'tabular-nums' }}>{clp(o.monto)}</span>
                  </MenuItem>
                ))}
              </Menu>
            </>
          );
        })()}
        <Button size="small" variant="outlined" startIcon={<Download size={14} />} onClick={verPdf}>PDF</Button>
        {esEditor && (
          <>
            <IconButton size="small" onClick={(e) => setMenu(e.currentTarget)} aria-label="Más acciones"><MoreHorizontal size={16} /></IconButton>
            <Menu anchorEl={menu} open={Boolean(menu)} onClose={() => setMenu(null)}>
              <MenuItem onClick={() => accion('duplicar')}>Duplicar</MenuItem>
              {esOrden && <MenuItem onClick={() => setDialogo('correo')}>Enviar por correo</MenuItem>}
              {esOrden && algoEntregado && (
                <MenuItem onClick={() => { setMenu(null); setDialogo('devolucion'); }}>{venta ? 'Registrar devolución del cliente' : 'Registrar devolución al proveedor'}</MenuItem>
              )}
              {(esOrden || p.estado === 'cancelado') && <MenuItem onClick={() => accion('borrador')}>Volver a cotización</MenuItem>}
              {p.estado !== 'cancelado' && <MenuItem onClick={() => accion('cancelar')}>Cancelar</MenuItem>}
              {p.estado === 'borrador' && <MenuItem onClick={borrar} sx={{ color: 'error.main' }}>Borrar</MenuItem>}
            </Menu>
          </>
        )}
      </Box>

      <BarraEtapas p={p} />

      {p.diferencias.length > 0 && <Alert severity="warning" sx={{ fontSize: '0.86rem' }}>{p.diferencias.join(' ')}</Alert>}
      {p.origen === 'reposicion' && !esOrden && (
        <Alert severity="info" sx={{ fontSize: '0.86rem' }}>La armó Afable para reponer lo que está bajo el stock mínimo. Revise cantidades y precios, y envíela o confírmela.</Alert>
      )}
      {p.moneda !== 'CLP' && !esOrden && editable && !Number(aNumero(cab.tipo_cambio)) && (
        <Alert severity="info" sx={{ fontSize: '0.86rem' }}>Falta el tipo de cambio para confirmar.</Alert>
      )}

      {/* Cabecera */}
      <Tarjeta sx={{ p: 2.5 }}>
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1.4fr 1fr 1fr 1fr' }, gap: 2 }}>
          <Campo etiqueta={venta ? 'Cliente' : 'Proveedor'}>
            {editable
              ? <BuscadorContacto slug={slug} rol={venta ? 'cliente' : 'proveedor'} value={cab.contacto} onChange={(v) => v && cambiarCab('contacto', v)} />
              : <Typography sx={{ fontWeight: 500 }}>{p.contacto_nombre} <Typography component="span" sx={{ fontSize: '0.78rem', color: 'text.secondary' }}>{p.contacto_rut}</Typography></Typography>}
          </Campo>
          <Campo etiqueta="Fecha">
            <InputBase type="date" disabled={!editable} value={cab.fecha} onChange={(e) => cambiarCab('fecha', e.target.value)} sx={{ ...campoSx, width: '100%' }} />
          </Campo>
          {venta && !esOrden ? (
            <Campo etiqueta="Válida hasta">
              <InputBase type="date" disabled={!editable} value={cab.valida_hasta} onChange={(e) => cambiarCab('valida_hasta', e.target.value)} sx={{ ...campoSx, width: '100%' }} />
            </Campo>
          ) : <Box />}
          <Campo etiqueta={venta ? 'Fecha de entrega' : 'Llegada esperada'}>
            <InputBase type="date" disabled={!libre} value={cab.fecha_compromiso} onChange={(e) => cambiarCab('fecha_compromiso', e.target.value)} sx={{ ...campoSx, width: '100%' }} />
          </Campo>
          <Campo etiqueta={venta ? 'OC del cliente' : 'Cotización del proveedor'}>
            <InputBase disabled={!libre} value={cab.referencia} onChange={(e) => cambiarCab('referencia', e.target.value)} sx={{ ...campoSx, width: '100%' }} />
          </Campo>
          <Campo etiqueta="Plazo de pago (días)">
            <InputBase disabled={!editable} value={cab.plazo_dias} onChange={(e) => cambiarCab('plazo_dias', e.target.value.replace(/\D/g, ''))} sx={{ ...campoSx, width: '100%' }} />
          </Campo>
          <Campo etiqueta="Moneda">
            <Box sx={{ display: 'flex', gap: 0.75 }}>
              <Select size="small" disabled={!editable} value={cab.moneda} sx={{ fontSize: '0.86rem', minWidth: 80 }}
                onChange={(e) => { cambiarCab('moneda', e.target.value); if (e.target.value !== 'CLP') traerCambio(e.target.value); }}>
                {['CLP', 'USD', 'UF'].map((m) => <MenuItem key={m} value={m}>{m}</MenuItem>)}
              </Select>
              {cab.moneda !== 'CLP' && (
                <Tooltip arrow title="Pesos por unidad, del día del documento (dólar observado o UF). Se trae solo; puede corregirlo.">
                  <InputBase disabled={!editable} value={cab.tipo_cambio} onChange={(e) => cambiarCab('tipo_cambio', e.target.value.replace(/[^\d,]/g, ''))}
                    sx={{ ...campoSx, flex: 1 }} inputProps={{ 'aria-label': 'Tipo de cambio' }} />
                </Tooltip>
              )}
            </Box>
          </Campo>
          <Campo etiqueta="Proyecto">
            <Select size="small" fullWidth displayEmpty disabled={!libre} value={cab.proyecto} onChange={(e) => cambiarCab('proyecto', e.target.value)} sx={{ fontSize: '0.86rem' }}>
              <MenuItem value=""><em>Sin proyecto</em></MenuItem>
              {proyectos.map((x) => <MenuItem key={x.id} value={x.id}>{x.nombre}</MenuItem>)}
            </Select>
          </Campo>
          {p.con_inventario && bodegas.length > 1 && (
            <Campo etiqueta="Bodega">
              <Select size="small" fullWidth disabled={!libre} value={cab.bodega} onChange={(e) => cambiarCab('bodega', e.target.value)} sx={{ fontSize: '0.86rem' }}>
                {bodegas.filter((b) => b.activa).map((b) => <MenuItem key={b.id} value={b.id}>{b.nombre}</MenuItem>)}
              </Select>
            </Campo>
          )}
        </Box>
      </Tarjeta>

      {/* Líneas */}
      <Tarjeta sx={{ overflow: 'auto' }}>
        <Table size="small" sx={{ '& td, & th': { fontSize: '0.84rem', borderColor: 'divider' } }}>
          <TableHead>
            <TableRow sx={{ '& th': { color: 'text.secondary', fontWeight: 500, bgcolor: 'action.hover', whiteSpace: 'nowrap' } }}>
              <TableCell sx={{ minWidth: 260 }}>Producto o descripción</TableCell>
              <TableCell align="right">Cantidad</TableCell>
              <TableCell align="right">Precio unitario</TableCell>
              <TableCell align="right">Desc. %</TableCell>
              <TableCell align="center">Exento</TableCell>
              <TableCell align="right">Subtotal</TableCell>
              {esOrden && <TableCell align="right">{venta ? 'Entregado' : 'Recibido'}</TableCell>}
              {editable && <TableCell />}
            </TableRow>
          </TableHead>
          <TableBody>
            {lineas.map((l) => {
              const bruto = Number(aNumero(l.cantidad) || 0) * Number(aNumero(l.precio_unitario) || 0);
              const sub = bruto - (bruto * Number(aNumero(l.descuento_pct) || 0)) / 100;
              const original = p.lineas.find((x) => String(x.id) === l.clave);
              return (
                <TableRow key={l.clave}>
                  <TableCell>
                    {editable ? (
                      <Autocomplete size="small" freeSolo options={productos} value={productos.find((x) => x.id === l.producto) || l.descripcion}
                        getOptionLabel={(o) => (typeof o === 'string' ? o : `${o.codigo ? `[${o.codigo}] ` : ''}${o.nombre}`)}
                        onChange={(_, v) => (typeof v === 'string' ? cambiarLinea(l.clave, 'descripcion', v) : elegirProducto(l.clave, v))}
                        onInputChange={(_, v, motivo) => { if (motivo === 'input') { cambiarLinea(l.clave, 'descripcion', v); cambiarLinea(l.clave, 'producto', null); } }}
                        renderInput={(params) => <TextField {...params} placeholder="Producto o servicio" variant="standard" InputProps={{ ...params.InputProps, disableUnderline: true, sx: { fontSize: '0.86rem' } }} />} />
                    ) : l.descripcion}
                  </TableCell>
                  <TableCell align="right" sx={{ whiteSpace: 'nowrap' }}>
                    {editable ? <InputBase value={l.cantidad} onChange={(e) => cambiarLinea(l.clave, 'cantidad', e.target.value.replace(/[^\d,]/g, ''))} inputProps={{ style: { textAlign: 'right' }, 'aria-label': 'Cantidad' }} sx={{ ...campoSx, width: 70 }} />
                      : cant(l.cantidad)} <Typography component="span" sx={{ fontSize: '0.76rem', color: 'text.secondary' }}>{l.unidad}</Typography>
                  </TableCell>
                  <TableCell align="right">
                    {editable ? <InputBase value={l.precio_unitario} onChange={(e) => cambiarLinea(l.clave, 'precio_unitario', e.target.value.replace(/[^\d,]/g, ''))} inputProps={{ style: { textAlign: 'right' }, 'aria-label': 'Precio unitario' }} sx={{ ...campoSx, width: 110 }} />
                      : dinero(aNumero(l.precio_unitario), p.moneda)}
                  </TableCell>
                  <TableCell align="right">
                    {editable ? <InputBase value={l.descuento_pct} placeholder="0" onChange={(e) => cambiarLinea(l.clave, 'descuento_pct', e.target.value.replace(/[^\d,]/g, ''))} inputProps={{ style: { textAlign: 'right' }, 'aria-label': 'Descuento' }} sx={{ ...campoSx, width: 56 }} />
                      : (l.descuento_pct || '—')}
                  </TableCell>
                  <TableCell align="center"><Checkbox size="small" checked={l.exento} disabled={!editable} onChange={(e) => cambiarLinea(l.clave, 'exento', e.target.checked)} /></TableCell>
                  <TableCell align="right" sx={NUM}>{dinero(sub, cab.moneda)}</TableCell>
                  {esOrden && <TableCell align="right" sx={NUM}>{original ? `${cant(original.cantidad_entregada)} de ${cant(original.cantidad)}` : ''}</TableCell>}
                  {editable && (
                    <TableCell><IconButton size="small" aria-label="Quitar línea" onClick={() => { setLineas((ls) => ls.filter((x) => x.clave !== l.clave)); setSucio(true); }}><Trash2 size={14} /></IconButton></TableCell>
                  )}
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
        {editable && (
          <Box sx={{ p: 1 }}>
            <Button size="small" startIcon={<Plus size={14} />} onClick={() => { setLineas((ls) => [...ls, lineaVacia()]); setSucio(true); }}>Agregar línea</Button>
          </Box>
        )}
        <Box sx={{ display: 'flex', justifyContent: 'flex-end', p: 2, borderTop: '1px solid', borderColor: 'divider' }}>
          <Box sx={{ display: 'grid', gridTemplateColumns: 'auto auto', columnGap: 4, rowGap: 0.5, fontSize: '0.88rem', ...NUM }}>
            <Typography sx={{ color: 'text.secondary', fontSize: 'inherit' }}>Neto</Typography><Typography align="right" sx={{ fontSize: 'inherit' }}>{dinero(totales.neto, cab.moneda)}</Typography>
            {totales.exento > 0 && <><Typography sx={{ color: 'text.secondary', fontSize: 'inherit' }}>Exento</Typography><Typography align="right" sx={{ fontSize: 'inherit' }}>{dinero(totales.exento, cab.moneda)}</Typography></>}
            <Typography sx={{ color: 'text.secondary', fontSize: 'inherit' }}>IVA 19%</Typography><Typography align="right" sx={{ fontSize: 'inherit' }}>{dinero(totales.iva, cab.moneda)}</Typography>
            <Typography sx={{ fontWeight: 600, fontSize: '1rem' }}>Total</Typography><Typography align="right" sx={{ fontWeight: 600, fontSize: '1rem' }}>{dinero(totales.total, cab.moneda)}</Typography>
            {cab.moneda !== 'CLP' && <><Typography sx={{ color: 'text.secondary', fontSize: '0.78rem' }}>En pesos</Typography><Typography align="right" sx={{ fontSize: '0.78rem', color: 'text.secondary' }}>{clp(totales.total * Number(aNumero(cab.tipo_cambio) || 0))}</Typography></>}
          </Box>
        </Box>
      </Tarjeta>

      {/* Notas */}
      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: venta ? '1fr 1fr' : '1fr' }, gap: 2 }}>
        {venta && (
          <Campo etiqueta="Condiciones (salen en el PDF)">
            <InputBase multiline minRows={3} disabled={!editable} value={cab.condiciones} onChange={(e) => cambiarCab('condiciones', e.target.value)} sx={{ ...campoSx, width: '100%', py: 1 }} />
          </Campo>
        )}
        <Campo etiqueta="Notas">
          <InputBase multiline minRows={3} disabled={!libre} value={cab.notas} onChange={(e) => cambiarCab('notas', e.target.value)} sx={{ ...campoSx, width: '100%', py: 1 }} />
        </Campo>
      </Box>

      {/* Entregas y facturas */}
      {esOrden || p.entregas.length || p.facturas.length ? (
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr', lg: '1fr 1fr 1fr' }, gap: 2 }}>
          <Tarjeta sx={{ p: 2 }}>
            <Typography sx={{ fontWeight: 600, mb: 1 }}>{venta ? 'Entregas' : 'Recepciones'} · {entregasHechas.length}</Typography>
            {p.entregas.length === 0 ? <Typography sx={{ fontSize: '0.84rem', color: 'text.secondary' }}>Ninguna todavía.</Typography>
              : p.entregas.map((e) => (
                <Box key={e.id} sx={{ display: 'flex', alignItems: 'flex-start', gap: 1, py: 0.75, borderTop: '1px solid', borderColor: 'divider', opacity: e.estado === 'anulada' ? 0.5 : 1 }}>
                  <Box sx={{ flex: 1 }}>
                    <Typography sx={{ fontSize: '0.86rem', fontWeight: 500 }}>
                      {e.tipo === 'devolucion' ? 'Devolución ' : ''}{e.numero} · {fecha(e.fecha)}{e.bodega ? ` · ${e.bodega}` : ''}{e.folio_guia ? ` · guía ${e.folio_guia}` : ''}{e.estado === 'anulada' ? ' · anulada' : ''}
                    </Typography>
                    <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary' }}>{e.lineas.map((x) => `${cant(x.cantidad)} ${x.unidad} ${x.descripcion}`).join(' · ')}</Typography>
                  </Box>
                  {e.guia_documento ? (
                    <Button size="small" sx={{ fontSize: '0.74rem', whiteSpace: 'nowrap' }} startIcon={<Download size={13} />}
                      onClick={() => descargar(api.dte.pdf(slug, e.guia_documento), `Guía ${e.folio_guia}.pdf`)}>
                      Guía N° {e.folio_guia}
                    </Button>
                  ) : esEditor && e.guia_disponible && (
                    <Button size="small" sx={{ fontSize: '0.74rem', whiteSpace: 'nowrap' }} onClick={() => setGuia(e)}>Emitir guía</Button>
                  )}
                  {esEditor && e.estado === 'hecha' && (
                    <Tooltip arrow title="Anular (devuelve el stock)"><IconButton size="small" onClick={() => anular(e.id)} aria-label={`Anular ${e.numero}`}><X size={14} /></IconButton></Tooltip>
                  )}
                </Box>
              ))}
          </Tarjeta>
          <Tarjeta sx={{ p: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1, mb: 1 }}>
              <Typography sx={{ fontWeight: 600 }}>Facturas del SII · {p.facturas.length}</Typography>
              <Box sx={{ flex: 1 }} />
              <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary', ...NUM }}>
                {clp(p.facturado_clp)} de {clp(p.base_clp)} sin IVA{p.por_facturar_clp > 0 ? ` · faltan ${clp(p.por_facturar_clp)}` : ''}
              </Typography>
            </Box>
            {p.facturas.length === 0 ? (
              <Typography sx={{ fontSize: '0.84rem', color: 'text.secondary' }}>
                Ninguna. Cuando cargue el Registro de {venta ? 'Ventas' : 'Compras'}, la factura que cuadre con esta orden se vincula sola.
              </Typography>
            ) : p.facturas.map((f) => (
              <Box key={f.documento} sx={{ display: 'flex', alignItems: 'center', gap: 1, py: 0.75, borderTop: '1px solid', borderColor: 'divider' }}>
                <Typography sx={{ fontSize: '0.86rem', flex: 1 }}>
                  {f.tipo_documento === '61' ? 'Nota de crédito' : 'Factura'} {f.folio} · {fecha(f.fecha)}
                  {f.origen === 'auto' && <Typography component="span" sx={{ fontSize: '0.74rem', color: 'text.secondary', ml: 0.75 }}>vinculada sola</Typography>}
                </Typography>
                <Typography sx={{ fontSize: '0.86rem', ...NUM }}>{clp(f.monto)}</Typography>
                {/* La factura emitida desde Afable tiene su PDF (comercial/pdf_factura.py). */}
                {f.emitida && (
                  <IconButton size="small" onClick={() => descargar(api.comercial.pdfFactura(slug, f.documento), `Factura-${f.folio}.pdf`)}
                    aria-label={`PDF de la factura ${f.folio}`}><Download size={14} /></IconButton>
                )}
                {esEditor && <IconButton size="small" onClick={() => desvincular(f.documento)} aria-label={`Desvincular folio ${f.folio}`}><X size={14} /></IconButton>}
              </Box>
            ))}
          </Tarjeta>
          <Tarjeta sx={{ p: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1, mb: 1 }}>
              <Typography sx={{ fontWeight: 600 }}>{venta ? 'Cobros' : 'Pagos'} · {p.pagos.length}</Typography>
              <Box sx={{ flex: 1 }} />
              <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary', ...NUM }}>
                {clp(p.pagado_clp)} de {clp(p.total_clp)}{p.por_pagar_clp > 0 ? ` · faltan ${clp(p.por_pagar_clp)}` : ''}
              </Typography>
            </Box>
            {p.pagos.length === 0 ? (
              <Typography sx={{ fontSize: '0.84rem', color: 'text.secondary' }}>
                Ninguno todavía. {esOrden ? `Regístrelo con «${venta ? 'Registrar cobro' : 'Registrar pago'}».` : 'Se registran cuando es orden.'}
              </Typography>
            ) : p.pagos.map((x) => (
              <Box key={x.id} sx={{ display: 'flex', alignItems: 'center', gap: 1, py: 0.75, borderTop: '1px solid', borderColor: 'divider' }}>
                <Typography sx={{ fontSize: '0.86rem', flex: 1 }}>
                  {fecha(x.fecha)} · {x.medio_nombre}{x.referencia ? ` · ${x.referencia}` : ''}
                </Typography>
                <Typography sx={{ fontSize: '0.86rem', ...NUM }}>{clp(x.monto)}</Typography>
                {esEditor && <IconButton size="small" onClick={() => borrarPago(x.id)} aria-label={`Borrar el pago de ${clp(x.monto)}`}><X size={14} /></IconButton>}
              </Box>
            ))}
          </Tarjeta>
        </Box>
      ) : null}

      {guia && <DialogoGuia p={p} entrega={guia} slug={slug} onCerrar={() => setGuia(null)} onHecho={(d) => { aplicar(d); setGuia(null); }} />}
      {dialogo === 'entrega' && <DialogoEntrega p={p} slug={slug} bodegas={bodegas} onCerrar={() => setDialogo(null)} onHecho={(d) => { aplicar(d); setDialogo(null); }} />}
      {dialogo === 'facturas' && <DialogoFacturas p={p} slug={slug} onCerrar={() => setDialogo(null)} onHecho={(d) => { aplicar(d); setDialogo(null); }} />}
      {dialogo === 'devolucion' && <DialogoDevolucion p={p} slug={slug} onCerrar={() => setDialogo(null)} onHecho={(d) => { aplicar(d); setDialogo(null); }} />}
      {dialogo === 'pago' && <DialogoPago p={p} slug={slug} onCerrar={() => setDialogo(null)} onHecho={(d) => { aplicar(d); setDialogo(null); }} />}
      {dialogo === 'correo' && <DialogoCorreo p={p} slug={slug} onCerrar={() => setDialogo(null)} onHecho={(d) => { aplicar(d); setDialogo(null); }} />}
    </Box>
  );
}
