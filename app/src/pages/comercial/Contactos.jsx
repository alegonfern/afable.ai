import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box, Button, Checkbox, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, FormControlLabel,
  InputBase, MenuItem, Select, Table, TableBody, TableCell, TableHead, TableRow, TextField, Typography,
} from '@mui/material';
import { Archive, Download, Plus, Search, Upload } from 'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../../services/api';
import { ChipEtapa, DialogoImportar, NUM, clp, descargar, dinero, fecha } from './comun';

/*
 * Clientes (en Ventas) y Proveedores (en Compras): la MISMA ficha de contacto, como en Odoo
 * (22-10-2026). Un RUT, con las casillas cliente y proveedor. Lo que depende del rol (el plazo de
 * pago y la regla de categoría para sus facturas del SII) se edita por separado en la ficha.
 */

const LIBRO = { ventas: 'Como cliente', compras: 'Como proveedor', honorarios: 'Honorarios' };

function FichaContacto({ slug, id, rol, esEditor, onCerrar, onGuardado }) {
  const navigate = useNavigate();
  const [c, setC] = useState(id ? null : { razon_social: '', rut: '', es_cliente: rol === 'cliente', es_proveedor: rol === 'proveedor', activo: true, roles: [], pedidos: [] });
  const [categorias, setCategorias] = useState([]);
  const [guardando, setGuardando] = useState(false);
  useEffect(() => {
    if (id) api.comercial.contacto(slug, id).then(({ data }) => setC(data)).catch(() => { toast.error('No se pudo abrir el contacto.'); onCerrar(); });
    api.finanzas.categorias(slug).then(({ data }) => setCategorias(data)).catch(() => {});
  }, [slug, id]);
  if (!c) return null;
  const cambiar = (k, v) => setC((x) => ({ ...x, [k]: v }));
  const guardar = async () => {
    setGuardando(true);
    try {
      const campos = ['razon_social', 'rut', 'giro', 'direccion', 'comuna', 'ciudad', 'email', 'telefono', 'persona_contacto', 'notas', 'es_cliente', 'es_proveedor', 'activo'];
      const datos = Object.fromEntries(campos.filter((k) => k in c).map((k) => [k, c[k]]));
      const { data } = id ? await api.comercial.actualizarContacto(slug, id, datos) : await api.comercial.crearContacto(slug, datos);
      toast.success('Guardado.');
      onGuardado(data);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'No se pudo guardar.');
      setGuardando(false);
    }
  };
  const guardarRol = async (r, cambios) => {
    try {
      await api.finanzas.actualizarContraparte(slug, r.id, cambios);
      setC((x) => ({ ...x, roles: x.roles.map((y) => (y.id === r.id ? { ...y, ...cambios } : y)) }));
    } catch (e) { toast.error(e.response?.data?.detail || 'No se pudo guardar.'); }
  };
  const campo = (k, etiqueta, props = {}) => (
    <TextField size="small" label={etiqueta} value={c[k] || ''} disabled={!esEditor} onChange={(e) => cambiar(k, e.target.value)} {...props} />
  );
  return (
    <Dialog open onClose={onCerrar} maxWidth="md" fullWidth>
      <DialogTitle sx={{ fontWeight: 600 }}>{id ? c.razon_social : 'Nuevo contacto'}</DialogTitle>
      <DialogContent>
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '2fr 1fr' }, gap: 1.5, mt: 1 }}>
          {campo('razon_social', 'Nombre o razón social')}
          {campo('rut', 'RUT', { disabled: !esEditor || c.roles.length > 0, helperText: c.roles.length ? 'Viene del SII' : '' })}
          {campo('giro', 'Giro')}
          {campo('persona_contacto', 'Persona de contacto')}
          {campo('direccion', 'Dirección')}
          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1.5 }}>{campo('comuna', 'Comuna')}{campo('ciudad', 'Ciudad')}</Box>
          {campo('email', 'Correo')}
          {campo('telefono', 'Teléfono')}
        </Box>
        <Box sx={{ display: 'flex', gap: 2, mt: 1 }}>
          <FormControlLabel control={<Checkbox size="small" checked={c.es_cliente} disabled={!esEditor} onChange={(e) => cambiar('es_cliente', e.target.checked)} />} label="Cliente" />
          <FormControlLabel control={<Checkbox size="small" checked={c.es_proveedor} disabled={!esEditor} onChange={(e) => cambiar('es_proveedor', e.target.checked)} />} label="Proveedor" />
          {id && (
            <FormControlLabel control={<Checkbox size="small" checked={!c.activo} disabled={!esEditor} onChange={(e) => cambiar('activo', !e.target.checked)} />}
              label="Archivado (no aparece en las listas ni al cotizar)" />
          )}
        </Box>
        {campo('notas', 'Notas', { multiline: true, minRows: 2, fullWidth: true, sx: { mt: 1 } })}

        {c.roles.length > 0 && (
          <Box sx={{ mt: 2.5 }}>
            <Typography sx={{ fontWeight: 600, fontSize: '0.92rem', mb: 0.5 }}>En el SII</Typography>
            <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary', mb: 1 }}>
              El plazo con que se calcula el vencimiento de sus documentos y la categoría con que se clasifican solos.
            </Typography>
            {c.roles.map((r) => (
              <Box key={r.id} sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap', py: 0.75, borderTop: '1px solid', borderColor: 'divider' }}>
                <Typography sx={{ fontSize: '0.84rem', width: 130 }}>{LIBRO[r.libro]}</Typography>
                <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary', width: 160 }}>{r.documentos} documentos · {clp(r.pendiente)} pendiente</Typography>
                <InputBase defaultValue={r.plazo_dias ?? ''} placeholder={String(r.plazo_por_defecto)} disabled={!esEditor}
                  onBlur={(e) => { if (String(e.target.value) !== String(r.plazo_dias ?? '')) guardarRol(r, { plazo_dias: e.target.value }); }}
                  sx={{ width: 56, border: '1px solid', borderColor: 'divider', borderRadius: '6px', px: 1, fontSize: '0.82rem' }} />
                <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary' }}>días</Typography>
                <Select size="small" displayEmpty disabled={!esEditor} value={r.regla_activa ? (r.categoria || '') : ''}
                  onChange={(e) => guardarRol(r, e.target.value ? { categoria: e.target.value, regla_activa: true } : { regla_activa: false })}
                  sx={{ width: 220, fontSize: '0.82rem', '& .MuiSelect-select': { py: 0.5 } }}
                  renderValue={(v) => (v ? categorias.find((x) => x.id === v)?.nombre : 'Sin regla de categoría')}>
                  <MenuItem value=""><em>Sin regla</em></MenuItem>
                  {categorias.filter((x) => (r.libro === 'ventas') === (x.tipo === 'ingreso')).map((x) => <MenuItem key={x.id} value={x.id}>{x.nombre}</MenuItem>)}
                </Select>
              </Box>
            ))}
          </Box>
        )}

        {c.pedidos.length > 0 && (
          <Box sx={{ mt: 2.5 }}>
            <Typography sx={{ fontWeight: 600, fontSize: '0.92rem', mb: 0.5 }}>Cotizaciones y órdenes</Typography>
            {c.pedidos.map((p) => (
              <Box key={p.id} onClick={() => navigate(`/app/${p.tipo === 'venta' ? 'ventas' : 'compras'}/${/^(Cotización|Solicitud)/.test(p.etapa) ? 'cotizaciones' : 'ordenes'}/${p.id}`)}
                sx={{ display: 'flex', alignItems: 'center', gap: 1.5, py: 0.6, borderTop: '1px solid', borderColor: 'divider', cursor: 'pointer', '&:hover': { bgcolor: 'action.hover' } }}>
                <Typography sx={{ fontSize: '0.84rem', fontWeight: 500, width: 80 }}>{p.numero}</Typography>
                <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary', width: 90 }}>{fecha(p.fecha)}</Typography>
                <Typography sx={{ fontSize: '0.84rem', flex: 1, ...NUM }}>{dinero(p.total, p.moneda)}</Typography>
                <ChipEtapa etapa={p.etapa} />
              </Box>
            ))}
          </Box>
        )}
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onCerrar}>{esEditor ? 'Cancelar' : 'Cerrar'}</Button>
        {esEditor && <Button variant="contained" onClick={guardar} disabled={guardando || !c.razon_social?.trim()}>Guardar</Button>}
      </DialogActions>
    </Dialog>
  );
}

export default function Contactos({ slug, rol, esEditor }) {
  const [lista, setLista] = useState(null);
  const [q, setQ] = useState('');
  const [abierto, setAbierto] = useState(null);           // id, 'nuevo' o null
  const [archivados, setArchivados] = useState(false);
  const [importando, setImportando] = useState(false);
  const cargar = useCallback(() => {
    api.comercial.contactos(slug, { rol, q: q || undefined, archivados: archivados ? 'solo' : undefined })
      .then(({ data }) => setLista(data)).catch(() => setLista([]));
  }, [slug, rol, q, archivados]);
  useEffect(() => { const t = setTimeout(cargar, q ? 250 : 0); return () => clearTimeout(t); }, [cargar, q]);
  const cliente = rol === 'cliente';
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, border: '1px solid', borderColor: 'divider', borderRadius: '10px', px: 1.25, py: 0.5, flex: 1, minWidth: 220, maxWidth: 380, bgcolor: 'background.paper' }}>
          <Search size={15} style={{ opacity: 0.5 }} />
          <InputBase placeholder="Buscar por nombre o RUT" value={q} onChange={(e) => setQ(e.target.value)} sx={{ flex: 1, fontSize: '0.86rem' }} />
        </Box>
        <Button size="small" variant={archivados ? 'contained' : 'text'} color="inherit" startIcon={<Archive size={14} />} onClick={() => setArchivados((v) => !v)}>
          {archivados ? 'Viendo archivados' : 'Archivados'}
        </Button>
        <Box sx={{ flex: 1 }} />
        <Button size="small" variant="outlined" startIcon={<Download size={14} />}
          onClick={() => descargar(api.comercial.exportar(slug, 'contactos', { rol }), `${cliente ? 'Clientes' : 'Proveedores'}.xlsx`)}>Exportar</Button>
        {esEditor && <Button size="small" variant="outlined" startIcon={<Upload size={14} />} onClick={() => setImportando(true)}>Importar</Button>}
        {esEditor && <Button size="small" variant="contained" startIcon={<Plus size={15} />} onClick={() => setAbierto('nuevo')}>{cliente ? 'Nuevo cliente' : 'Nuevo proveedor'}</Button>}
      </Box>
      {!lista ? <CircularProgress size={20} sx={{ m: 'auto', mt: 4 }} /> : lista.length === 0 ? (
        <Typography sx={{ textAlign: 'center', py: 8, color: 'text.secondary', fontSize: '0.9rem' }}>
          {q ? 'Nada coincide con la búsqueda.' : archivados ? 'No hay contactos archivados.'
            : `Aparecen al importar el Registro de ${cliente ? 'Ventas' : 'Compras'} del SII, o créelos aquí (uno a uno o desde Excel con «Importar»).`}
        </Typography>
      ) : (
        <Box sx={{ border: '1px solid', borderColor: 'divider', borderRadius: '12px', overflow: 'auto', bgcolor: 'background.paper' }}>
          <Table size="small" sx={{ '& td, & th': { fontSize: '0.84rem', borderColor: 'divider', whiteSpace: 'nowrap' } }}>
            <TableHead>
              <TableRow sx={{ '& th': { color: 'text.secondary', fontWeight: 500, bgcolor: 'action.hover' } }}>
                <TableCell>{cliente ? 'Cliente' : 'Proveedor'}</TableCell>
                <TableCell>RUT</TableCell>
                <TableCell>Correo</TableCell>
                <TableCell align="right">Documentos SII</TableCell>
                <TableCell align="right">Total</TableCell>
                <TableCell align="right">{cliente ? 'Por cobrar' : 'Por pagar'}</TableCell>
                <TableCell />
              </TableRow>
            </TableHead>
            <TableBody>
              {lista.map((c) => (
                <TableRow key={c.id} hover sx={{ cursor: 'pointer' }} onClick={() => setAbierto(c.id)}>
                  <TableCell sx={{ maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', fontWeight: 500 }}>{c.razon_social}</TableCell>
                  <TableCell sx={{ color: 'text.secondary' }}>{c.rut || '—'}</TableCell>
                  <TableCell sx={{ color: 'text.secondary' }}>{c.email || '—'}</TableCell>
                  <TableCell align="right">{c.documentos}</TableCell>
                  <TableCell align="right" sx={NUM}>{clp(c.total)}</TableCell>
                  <TableCell align="right" sx={{ ...NUM, color: c.pendiente ? 'text.primary' : 'text.disabled' }}>{clp(c.pendiente)}</TableCell>
                  <TableCell sx={{ color: 'text.secondary', fontSize: '0.76rem !important' }}>
                    {c.es_cliente && c.es_proveedor ? 'Cliente y proveedor' : ''}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Box>
      )}
      {abierto && (
        <FichaContacto slug={slug} id={abierto === 'nuevo' ? null : abierto} rol={rol} esEditor={esEditor}
          onCerrar={() => setAbierto(null)} onGuardado={() => { setAbierto(null); cargar(); }} />
      )}
      {importando && <DialogoImportar slug={slug} que="contactos" onCerrar={() => setImportando(false)} onHecho={cargar} />}
    </Box>
  );
}
