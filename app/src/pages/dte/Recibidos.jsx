import { useCallback, useEffect, useState } from 'react';
import {
  Box, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, FormControlLabel, IconButton,
  InputBase, MenuItem, Select, Switch, Tooltip, Typography, useMediaQuery,
} from '@mui/material';
import { Check, FileCode, RefreshCw, TriangleAlert } from 'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../../services/api';
import { NUM, Tarjeta, clp, descargar, fecha } from '../comercial/comun';
import { ElegirArchivo } from './piezas';

/*
 * Compras › Documentos recibidos (26-10-2026): las facturas que los proveedores le mandan a la
 * empresa en XML, por la casilla de intercambio o subidas a mano. Afable revisa cada una (esquema,
 * firma y timbre), acusa recibo y la deja en el Libro de Compras. Aquí se acepta o se reclama: eso
 * queda registrado en el SII (Ley 20.956, 8 días desde que el SII la recibió).
 */

const campoSx = { border: '1px solid', borderColor: 'divider', borderRadius: '8px', px: 1.25, py: 0.4, fontSize: '0.86rem' };
const msg = (e, d) => e?.response?.data?.detail || d;
const RECLAMOS = [
  ['RCD', 'Reclamo al contenido del documento'],
  ['RFP', 'Falta parcial de mercaderías'],
  ['RFT', 'Falta total de mercaderías'],
];

function Revision({ d }) {
  const malas = [!d.esquema_ok && 'esquema', !d.firma_ok && 'firma', !d.timbre_ok && 'timbre'].filter(Boolean);
  if (!malas.length) return <Tooltip title="Esquema, firma y timbre en regla"><Check size={15} color="#0f9d6b" /></Tooltip>;
  return (
    <Tooltip title={`No calza: ${malas.join(', ')}. ${d.observaciones || ''}`}>
      <TriangleAlert size={15} color="#b45309" />
    </Tooltip>
  );
}

function DialogoReclamo({ slug, documento, onCerrar, onListo }) {
  const [accion, setAccion] = useState('RCD');
  const [motivo, setMotivo] = useState('');
  const [enviando, setEnviando] = useState(false);
  if (!documento) return null;
  const reclamar = async () => {
    setEnviando(true);
    try {
      await api.dte.reclamarRecibido(slug, documento.id, { accion, motivo });
      toast.success('Reclamo registrado en el SII y avisado al proveedor.');
      onListo();
    } catch (e) { toast.error(msg(e, 'No se pudo reclamar.')); }
    setEnviando(false);
  };
  return (
    <Dialog open onClose={onCerrar} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ fontWeight: 600 }}>Reclamar {documento.nombre.toLowerCase()} N° {documento.folio}</DialogTitle>
      <DialogContent sx={{ display: 'grid', gap: 1.5 }}>
        <Typography sx={{ fontSize: '0.82rem', color: 'text.secondary', lineHeight: 1.5 }}>
          El reclamo queda registrado en el SII y el proveedor deberá emitir una nota de crédito. Hay 8 días
          desde que el SII recibió el documento.
        </Typography>
        <Select size="small" value={accion} onChange={(e) => setAccion(e.target.value)} sx={{ fontSize: '0.86rem' }}>
          {RECLAMOS.map(([v, n]) => <MenuItem key={v} value={v}>{n}</MenuItem>)}
        </Select>
        <InputBase fullWidth multiline minRows={2} placeholder="Motivo (se le informa al proveedor)" value={motivo}
          onChange={(e) => setMotivo(e.target.value)} sx={{ ...campoSx, py: 1 }} />
      </DialogContent>
      <DialogActions>
        <Button color="inherit" onClick={onCerrar}>Cancelar</Button>
        <Button variant="contained" color="error" disabled={!motivo.trim() || enviando} onClick={reclamar}>
          {enviando ? 'Registrando…' : 'Reclamar'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

function DialogoAceptar({ slug, documento, onCerrar, onListo }) {
  const [mercaderias, setMercaderias] = useState(true);
  const [recinto, setRecinto] = useState('');
  const [enviando, setEnviando] = useState(false);
  if (!documento) return null;
  const aceptar = async () => {
    setEnviando(true);
    try {
      await api.dte.aceptarRecibido(slug, documento.id, { recibo_mercaderias: mercaderias, recinto });
      toast.success('Aceptado: queda registrado en el SII y se le avisó al proveedor.');
      onListo();
    } catch (e) { toast.error(msg(e, 'No se pudo aceptar.')); }
    setEnviando(false);
  };
  return (
    <Dialog open onClose={onCerrar} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ fontWeight: 600 }}>Aceptar {documento.nombre.toLowerCase()} N° {documento.folio}</DialogTitle>
      <DialogContent sx={{ display: 'grid', gap: 1.5 }}>
        <Typography sx={{ fontSize: '0.84rem' }}>{documento.emisor_razon_social} · {clp(documento.monto_total)}</Typography>
        <FormControlLabel control={<Switch checked={mercaderias} onChange={(e) => setMercaderias(e.target.checked)} />}
          label={<Typography sx={{ fontSize: '0.86rem' }}>También dar recibo de las mercaderías o servicios (Ley 19.983)</Typography>} />
        {mercaderias && (
          <InputBase placeholder="Recinto donde se recibieron (opcional)" value={recinto} onChange={(e) => setRecinto(e.target.value)} sx={campoSx} />
        )}
        <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary', lineHeight: 1.5 }}>
          Una vez aceptado, ya no se puede reclamar. Con el recibo de mercaderías la factura queda cedible.
        </Typography>
      </DialogContent>
      <DialogActions>
        <Button color="inherit" onClick={onCerrar}>Cancelar</Button>
        <Button variant="contained" disabled={enviando} onClick={aceptar}>{enviando ? 'Registrando…' : 'Aceptar'}</Button>
      </DialogActions>
    </Dialog>
  );
}

export default function Recibidos({ slug, esEditor }) {
  const [lista, setLista] = useState(null);
  const [estado, setEstado] = useState('');
  const [reclamo, setReclamo] = useState(null);
  const [aceptar, setAceptar] = useState(null);
  const [revisando, setRevisando] = useState(false);
  const telefono = useMediaQuery('(max-width:700px)');
  const cargar = useCallback(() => {
    api.dte.recibidos(slug, estado ? { estado } : {}).then(({ data }) => setLista(data)).catch(() => setLista([]));
  }, [slug, estado]);
  useEffect(() => { cargar(); }, [cargar]);

  const subir = async (archivo) => {
    try {
      const { data } = await api.dte.subirRecibido(slug, archivo);
      const n = data.recibidos?.length ?? 0;
      toast.success(n ? `${n} documento${n === 1 ? '' : 's'} recibido${n === 1 ? '' : 's'}.` : (data.glosa || 'El archivo no traía documentos para su empresa.'));
      cargar();
    } catch (e) { toast.error(msg(e, 'No se pudo leer el archivo.')); }
  };
  const revisarCasilla = async () => {
    setRevisando(true);
    try { await api.dte.revisarCasilla(slug); cargar(); } catch (e) { toast.error(msg(e, 'No se pudo revisar la casilla.')); }
    setRevisando(false);
  };

  return (
    <Box sx={{ display: 'grid', gap: 1.5 }}>
      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', alignItems: 'center' }}>
        <Select size="small" displayEmpty value={estado} onChange={(e) => setEstado(e.target.value)} sx={{ fontSize: '0.84rem', minWidth: 170 }}>
          <MenuItem value="">Todos</MenuItem>
          <MenuItem value="recibido">Por revisar</MenuItem>
          <MenuItem value="aceptado">Aceptados</MenuItem>
          <MenuItem value="reclamado">Reclamados</MenuItem>
        </Select>
        <Box sx={{ flex: 1 }} />
        {esEditor && (
          <>
            <Button size="small" startIcon={<RefreshCw size={14} />} onClick={revisarCasilla} disabled={revisando}>
              {revisando ? 'Revisando…' : 'Revisar la casilla'}
            </Button>
            <ElegirArchivo acepta=".xml" onElegir={subir}>Subir XML</ElegirArchivo>
          </>
        )}
      </Box>
      {!lista ? <CircularProgress size={20} /> : lista.length === 0 ? (
        <Typography sx={{ color: 'text.secondary', fontSize: '0.88rem', py: 3, lineHeight: 1.6 }}>
          Todavía no hay documentos recibidos. Llegan solos a la casilla de intercambio (Ajustes › Empresas › Facturación electrónica ›
          Casilla de intercambio) o puede subir el XML que le mandó un proveedor.
        </Typography>
      ) : telefono ? (
        <Box sx={{ display: 'grid', gap: 1 }}>
          {lista.map((d) => (
            <Tarjeta key={d.id} sx={{ p: 1.5, display: 'grid', gap: 0.75 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 1 }}>
                <Typography sx={{ fontSize: '0.88rem' }}>{d.nombre} <b>N° {d.folio}</b></Typography>
                <Typography sx={{ fontSize: '0.88rem', fontWeight: 600, ...NUM }}>{clp(d.monto_total)}</Typography>
              </Box>
              <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary' }}>{d.emisor_razon_social} · {fecha(d.fecha)}</Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Revision d={d} />
                <Typography sx={{ fontSize: '0.8rem', flex: 1 }}>{d.estado_nombre}</Typography>
                {esEditor && d.estado === 'recibido' && (
                  <>
                    <Button size="small" sx={{ fontSize: '0.76rem' }} onClick={() => setAceptar(d)}>Aceptar</Button>
                    <Button size="small" color="error" sx={{ fontSize: '0.76rem' }} onClick={() => setReclamo(d)}>Reclamar</Button>
                  </>
                )}
              </Box>
            </Tarjeta>
          ))}
        </Box>
      ) : (
        <Tarjeta sx={{ overflowX: 'auto' }}>
          <Box component="table" sx={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem',
            '& th': { textAlign: 'left', fontWeight: 500, color: 'text.secondary', fontSize: '0.76rem', px: 1.5, py: 1, borderBottom: '1px solid', borderColor: 'divider' },
            '& td': { px: 1.5, py: 1, borderBottom: '1px solid', borderColor: 'divider', verticalAlign: 'middle' } }}>
            <thead><tr><th>Fecha</th><th>Proveedor</th><th>Documento</th><th style={{ textAlign: 'right' }}>Total</th><th>Revisión</th><th>Estado</th><th /></tr></thead>
            <tbody>
              {lista.map((d) => (
                <tr key={d.id}>
                  <td style={{ whiteSpace: 'nowrap' }}>{fecha(d.fecha)}</td>
                  <td>{d.emisor_razon_social}<Typography component="span" sx={{ display: 'block', fontSize: '0.74rem', color: 'text.secondary' }}>{d.emisor_rut}</Typography></td>
                  <td>{d.nombre} <b>N° {d.folio}</b></td>
                  <td style={{ textAlign: 'right', ...NUM }}>{clp(d.monto_total)}</td>
                  <td><Revision d={d} /></td>
                  <td>
                    <Tooltip title={d.respuesta_sii || ''}>
                      <Chip size="small" label={d.estado_nombre} sx={{ height: 22, fontSize: '0.74rem', fontFamily: 'inherit',
                        bgcolor: d.estado === 'aceptado' ? '#0f9d6b14' : d.estado === 'reclamado' ? '#c8102e14' : 'action.selected',
                        color: d.estado === 'aceptado' ? '#0f9d6b' : d.estado === 'reclamado' ? '#c8102e' : 'text.primary' }} />
                    </Tooltip>
                  </td>
                  <td style={{ whiteSpace: 'nowrap', textAlign: 'right' }}>
                    <Tooltip title="XML"><IconButton size="small" onClick={() => descargar(api.dte.xmlRecibido(slug, d.id), `${d.nombre} ${d.folio} ${d.emisor_rut}.xml`)}><FileCode size={15} /></IconButton></Tooltip>
                    {esEditor && d.estado === 'recibido' && (
                      <>
                        <Button size="small" sx={{ fontSize: '0.76rem' }} onClick={() => setAceptar(d)}>Aceptar</Button>
                        <Button size="small" color="error" sx={{ fontSize: '0.76rem' }} onClick={() => setReclamo(d)}>Reclamar</Button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </Box>
        </Tarjeta>
      )}
      <DialogoReclamo key={`r${reclamo?.id}`} slug={slug} documento={reclamo} onCerrar={() => setReclamo(null)} onListo={() => { setReclamo(null); cargar(); }} />
      <DialogoAceptar key={`a${aceptar?.id}`} slug={slug} documento={aceptar} onCerrar={() => setAceptar(null)} onListo={() => { setAceptar(null); cargar(); }} />
    </Box>
  );
}
