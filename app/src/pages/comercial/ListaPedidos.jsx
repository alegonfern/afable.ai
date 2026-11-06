import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, InputBase, LinearProgress,
  MenuItem, Select, Table, TableBody, TableCell, TableHead, TableRow, Tooltip, Typography,
} from '@mui/material';
import { AlertTriangle, Download, Plus, Search, Sparkles } from 'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../../services/api';
import { BuscadorContacto, ChipEtapa, NUM, clp, descargar, dinero, fecha } from './comun';

// Las etapas que se pueden filtrar en cada lista.
const ETAPAS = {
  venta: { cotizaciones: ['Cotización', 'Cotización enviada'],
    ordenes: ['Orden de venta', 'Entrega parcial', 'Entregada', 'Facturada, falta entregar', 'Facturada'] },
  compra: { cotizaciones: ['Solicitud de cotización', 'Solicitud enviada'],
    ordenes: ['Orden de compra', 'Recepción parcial', 'Recibida', 'Facturada, falta recibir', 'Facturada'] },
};

/*
 * Las cotizaciones u órdenes de un lado (venta o compra). Clic en una fila abre la ficha.
 * "Nueva" pide solo el cliente o proveedor: lo demás se completa en la ficha.
 */

export function NuevoPedido({ slug, tipo, modulo, onCerrar }) {
  const navigate = useNavigate();
  const [contacto, setContacto] = useState(null);
  const [creando, setCreando] = useState(false);
  const crear = async () => {
    setCreando(true);
    try {
      const { data } = await api.comercial.crearPedido(slug, { tipo, contacto });
      navigate(`/app/${modulo}/cotizaciones/${data.id}`);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'No se pudo crear.');
      setCreando(false);
    }
  };
  return (
    <Dialog open onClose={onCerrar} maxWidth="xs" fullWidth>
      <DialogTitle sx={{ fontWeight: 600 }}>{tipo === 'venta' ? 'Nueva cotización' : 'Nueva solicitud de cotización'}</DialogTitle>
      <DialogContent>
        <Typography sx={{ fontSize: '0.84rem', color: 'text.secondary', mb: 1.5 }}>
          {tipo === 'venta' ? '¿A quién le cotiza?' : '¿A qué proveedor le pide precio?'} Si es nuevo, escriba el nombre y créelo aquí.
        </Typography>
        <BuscadorContacto slug={slug} rol={tipo === 'venta' ? 'cliente' : 'proveedor'} value={contacto}
          onChange={(id) => setContacto(id)} autoFocus />
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onCerrar}>Cancelar</Button>
        <Button variant="contained" disabled={!contacto || creando} onClick={crear}>Crear</Button>
      </DialogActions>
    </Dialog>
  );
}

export default function ListaPedidos({ slug, tipo, modulo, vista, esEditor }) {
  const navigate = useNavigate();
  const [pedidos, setPedidos] = useState(null);
  const [q, setQ] = useState('');
  const [etapa, setEtapa] = useState('');
  const [desde, setDesde] = useState('');
  const [hasta, setHasta] = useState('');
  const [error, setError] = useState(false);
  const [nuevo, setNuevo] = useState(false);
  useEffect(() => {
    setPedidos(null);
    setError(false);
    // Solo vale la respuesta de la última consulta: si se cambian los filtros rápido, una
    // respuesta anterior que llega tarde no pisa la lista filtrada.
    let vigente = true;
    const t = setTimeout(() => {
      api.comercial.pedidos(slug, { tipo, vista, q: q || undefined, etapa: etapa || undefined, desde: desde || undefined, hasta: hasta || undefined })
        .then(({ data }) => { if (vigente) setPedidos(data); }).catch(() => { if (vigente) setError(true); });
    }, q ? 250 : 0);
    return () => { vigente = false; clearTimeout(t); };
  }, [slug, tipo, vista, q, etapa, desde, hasta]);
  const filtrando = Boolean(q || etapa || desde || hasta);

  const venta = tipo === 'venta';
  const esOrden = vista === 'ordenes';
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, border: '1px solid', borderColor: 'divider', borderRadius: '10px', px: 1.25, py: 0.5, flex: 1, minWidth: 220, maxWidth: 380, bgcolor: 'background.paper' }}>
          <Search size={15} style={{ opacity: 0.5 }} />
          <InputBase placeholder={`Buscar por número o ${venta ? 'cliente' : 'proveedor'}`} value={q}
            onChange={(e) => setQ(e.target.value)} sx={{ flex: 1, fontSize: '0.86rem' }} />
        </Box>
        <Box sx={{ flex: 1 }} />
        <Button size="small" variant="outlined" startIcon={<Download size={14} />}
          onClick={() => descargar(api.comercial.exportar(slug, 'pedidos', { tipo, vista }), `${venta ? 'Ventas' : 'Compras'} - ${vista}.xlsx`)}>
          Exportar
        </Button>
        {esEditor && (
          <Button variant="contained" size="small" startIcon={<Plus size={15} />} onClick={() => setNuevo(true)}>
            {venta ? 'Nueva cotización' : 'Nueva solicitud'}
          </Button>
        )}
      </Box>

      {/* Filtros: etapa y fechas. */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
        <Select size="small" displayEmpty value={etapa} onChange={(e) => setEtapa(e.target.value)} sx={{ fontSize: '0.84rem', minWidth: 190 }}
          inputProps={{ 'aria-label': 'Etapa' }}>
          <MenuItem value="">Todas las etapas</MenuItem>
          {(ETAPAS[tipo][vista] || []).map((e) => <MenuItem key={e} value={e}>{e}</MenuItem>)}
        </Select>
        <InputBase type="date" value={desde} onChange={(e) => setDesde(e.target.value)} inputProps={{ 'aria-label': 'Desde' }}
          sx={{ border: '1px solid', borderColor: 'divider', borderRadius: '8px', px: 1, py: 0.25, fontSize: '0.84rem', bgcolor: 'background.paper' }} />
        <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary' }}>a</Typography>
        <InputBase type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} inputProps={{ 'aria-label': 'Hasta' }}
          sx={{ border: '1px solid', borderColor: 'divider', borderRadius: '8px', px: 1, py: 0.25, fontSize: '0.84rem', bgcolor: 'background.paper' }} />
        {filtrando && <Button size="small" onClick={() => { setQ(''); setEtapa(''); setDesde(''); setHasta(''); }}>Quitar filtros</Button>}
      </Box>

      {error ? (
        <Typography sx={{ textAlign: 'center', py: 6, color: 'text.secondary' }}>No se pudo cargar la lista. Recargue la página.</Typography>
      ) : !pedidos ? <CircularProgress size={20} sx={{ m: 'auto', mt: 4 }} /> : pedidos.length === 0 ? (
        <Box sx={{ textAlign: 'center', py: 8, color: 'text.secondary' }}>
          <Typography sx={{ fontSize: '0.92rem', mb: 0.5 }}>
            {filtrando ? 'Nada coincide con los filtros.' : esOrden
              ? `Todavía no hay órdenes de ${venta ? 'venta' : 'compra'}. Una ${venta ? 'cotización' : 'solicitud'} confirmada pasa a ser orden.`
              : `Todavía no hay ${venta ? 'cotizaciones' : 'solicitudes de cotización'}.`}
          </Typography>
          {!filtrando && <Typography sx={{ fontSize: '0.84rem' }}>También puede pedírsela al chat: «cotízale 10 sacos de cemento a Constructora Andes».</Typography>}
        </Box>
      ) : (
        <Box sx={{ border: '1px solid', borderColor: 'divider', borderRadius: '12px', overflow: 'auto', bgcolor: 'background.paper' }}>
          <Table size="small" sx={{ '& td, & th': { fontSize: '0.84rem', borderColor: 'divider', whiteSpace: 'nowrap' } }}>
            <TableHead>
              <TableRow sx={{ '& th': { color: 'text.secondary', fontWeight: 500, bgcolor: 'action.hover' } }}>
                <TableCell>Número</TableCell>
                <TableCell>Fecha</TableCell>
                <TableCell>{venta ? 'Cliente' : 'Proveedor'}</TableCell>
                <TableCell align="right">Total</TableCell>
                {esOrden && <TableCell>{venta ? 'Entregado' : 'Recibido'}</TableCell>}
                {esOrden && <TableCell align="right">Facturado</TableCell>}
                {esOrden && <TableCell align="right">{venta ? 'Cobrado' : 'Pagado'}</TableCell>}
                <TableCell>Etapa</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {pedidos.map((p) => (
                <TableRow key={p.id} hover sx={{ cursor: 'pointer' }} onClick={() => navigate(`/app/${modulo}/${vista || 'cotizaciones'}/${p.id}`)}>
                  <TableCell sx={{ fontWeight: 500 }}>
                    {p.numero}
                    {p.origen === 'reposicion' && (
                      <Tooltip arrow title="La armó Afable para reponer stock">
                        <Chip size="small" icon={<Sparkles size={11} />} label="Afable" sx={{ ml: 1, height: 20, fontSize: '0.7rem' }} />
                      </Tooltip>
                    )}
                  </TableCell>
                  <TableCell>{fecha(p.fecha)}</TableCell>
                  <TableCell sx={{ maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis' }}>{p.contacto_nombre}</TableCell>
                  <TableCell align="right" sx={NUM}>
                    {dinero(p.total, p.moneda)}
                    {p.moneda !== 'CLP' && <Typography component="div" sx={{ fontSize: '0.72rem', color: 'text.secondary' }}>{clp(p.total_clp)}</Typography>}
                  </TableCell>
                  {esOrden && (
                    <TableCell sx={{ minWidth: 120 }}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <LinearProgress variant="determinate" value={p.entregado_pct} sx={{ flex: 1, height: 5, borderRadius: 3 }} />
                        <Typography sx={{ fontSize: '0.76rem', color: 'text.secondary', width: 34 }}>{p.entregado_pct}%</Typography>
                      </Box>
                    </TableCell>
                  )}
                  {esOrden && (
                    <TableCell align="right" sx={NUM}>
                      {clp(p.facturado_clp)}
                      {p.diferencias.length > 0 && (
                        <Tooltip arrow title={p.diferencias.join(' ')}>
                          <AlertTriangle size={14} style={{ color: '#c77700', marginLeft: 6, verticalAlign: -2 }} />
                        </Tooltip>
                      )}
                    </TableCell>
                  )}
                  {esOrden && (
                    <TableCell align="right" sx={{ ...NUM, color: p.por_pagar_clp > 0 ? 'text.primary' : 'success.main' }}>
                      {clp(p.pagado_clp)}
                    </TableCell>
                  )}
                  <TableCell><ChipEtapa etapa={p.etapa} /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Box>
      )}
      {nuevo && <NuevoPedido slug={slug} tipo={tipo} modulo={modulo} onCerrar={() => setNuevo(false)} />}
    </Box>
  );
}
