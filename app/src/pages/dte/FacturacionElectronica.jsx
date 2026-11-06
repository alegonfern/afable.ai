import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, IconButton, InputBase,
  MenuItem, Radio, RadioGroup, FormControlLabel, Select, Tab, Tabs, Tooltip, Typography, useMediaQuery,
} from '@mui/material';
import { Check, Circle, FileCode, FileText, Plus, RefreshCw, Trash2 } from 'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../../services/api';
import { NUM, Tarjeta, clp, descargar, fecha } from '../comercial/comun';
import Certificacion from './Certificacion';
import Casilla from './Casilla';
import { ElegirArchivo } from './piezas';

/*
 * El facturador electrónico de Afable (26-10-2026), en Ajustes › Empresas › (la empresa) › Facturación electrónica.
 *
 * - Emitidos: cada documento con su estado en el SII, su PDF y su XML, y las notas de crédito o
 *   débito que lo corrigen.
 * - Configuración: el alta de la empresa paso a paso (sus datos, el certificado, los folios y la
 *   autorización del SII) y el interruptor que deja a Ventas emitiendo con este facturador.
 * - Certificación: para la empresa que todavía no está autorizada por el SII.
 * - Casilla: dónde llegan las facturas de los proveedores (intercambio).
 */

const campoSx = { border: '1px solid', borderColor: 'divider', borderRadius: '8px', px: 1.25, py: 0.4, fontSize: '0.86rem' };
const AMBIENTES = { certificacion: 'Certificación', produccion: 'Producción' };
const msg = (e, porDefecto) => e?.response?.data?.detail || porDefecto;

function Rotulo({ children }) {
  return <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary', mb: 0.5 }}>{children}</Typography>;
}

function Campo({ rotulo, valor, onGuardar, ayuda, disabled, tipo = 'text', ancho = '100%' }) {
  return (
    <Box>
      <Rotulo>{rotulo}</Rotulo>
      <InputBase type={tipo} defaultValue={valor ?? ''} key={`${rotulo}-${valor ?? ''}`} disabled={disabled} placeholder={ayuda}
        inputProps={{ 'aria-label': rotulo }}
        onBlur={(e) => { if (e.target.value !== String(valor ?? '')) onGuardar(e.target.value); }}
        sx={{ ...campoSx, width: ancho }} />
    </Box>
  );
}

function ChipEstado({ estado, nombre, detalle }) {
  const color = { aceptado: '#0f9d6b', reparos: '#b45309', rechazado: '#c8102e' }[estado];
  return (
    <Tooltip title={detalle || ''}>
      <Chip size="small" label={nombre} sx={{
        bgcolor: color ? `${color}14` : 'action.selected', color: color || 'text.primary', fontWeight: 500,
        fontSize: '0.74rem', height: 22, fontFamily: 'inherit',
      }} />
    </Tooltip>
  );
}

// ── Configuración: el alta paso a paso ─────────────────────────────────────────────────────

function Paso({ paso, numero, children }) {
  return (
    <Tarjeta sx={{ p: 2.25, display: 'grid', gap: 1.5 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25 }}>
        <Box sx={{
          width: 24, height: 24, borderRadius: '50%', display: 'grid', placeItems: 'center', flexShrink: 0,
          bgcolor: paso.listo ? '#0f9d6b' : 'action.selected', color: paso.listo ? '#fff' : 'text.secondary', fontSize: '0.78rem', fontWeight: 600,
        }}>
          {paso.listo ? <Check size={14} /> : numero}
        </Box>
        <Typography sx={{ fontWeight: 600, fontSize: '0.95rem', flex: 1 }}>{paso.titulo}</Typography>
      </Box>
      {!paso.listo && paso.falta?.length > 0 && (
        <Typography sx={{ fontSize: '0.8rem', color: '#b45309' }}>Falta {paso.falta.join('; ')}.</Typography>
      )}
      {children}
    </Tarjeta>
  );
}

function SubirCertificado({ slug, onListo, disabled }) {
  const [archivo, setArchivo] = useState(null);
  const [clave, setClave] = useState('');
  const [subiendo, setSubiendo] = useState(false);
  const subir = async () => {
    setSubiendo(true);
    try {
      const { data } = await api.dte.subirCertificado(slug, archivo, clave);
      toast.success(`Certificado de ${data.titular} cargado.`);
      setArchivo(null); setClave('');
      onListo();
    } catch (e) { toast.error(msg(e, 'No se pudo cargar el certificado.')); }
    setSubiendo(false);
  };
  return (
    <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', alignItems: 'center' }}>
      <ElegirArchivo acepta=".pfx,.p12" onElegir={setArchivo} disabled={disabled}>{archivo ? archivo.name : 'Elegir .pfx'}</ElegirArchivo>
      <InputBase type="password" placeholder="Clave del certificado" value={clave} disabled={disabled}
        onChange={(e) => setClave(e.target.value)} sx={{ ...campoSx, width: 200 }} />
      <Button size="small" variant="contained" disabled={!archivo || subiendo || disabled} onClick={subir}>
        {subiendo ? 'Cargando…' : 'Cargar'}
      </Button>
    </Box>
  );
}

function Folios({ slug, estado, ambiente, esAdmin, onCambio }) {
  const [cafs, setCafs] = useState([]);
  const [primer, setPrimer] = useState('');
  const cargar = useCallback(() => api.dte.cafs(slug, ambiente).then(({ data }) => setCafs(data)).catch(() => {}), [slug, ambiente]);
  useEffect(() => { cargar(); }, [cargar]);
  const subir = async (archivo) => {
    try {
      const { data } = await api.dte.subirCaf(slug, archivo, primer);
      toast.success(`CAF de ${data.nombre.toLowerCase()} cargado: folios ${data.desde} a ${data.hasta}.`);
      setPrimer('');
      cargar(); onCambio();
    } catch (e) { toast.error(msg(e, 'No se pudo cargar el CAF.')); }
  };
  return (
    <>
      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(190px, 1fr))', gap: 1 }}>
        {estado.folios.map((f) => (
          <Box key={f.tipo} sx={{ border: '1px solid', borderColor: 'divider', borderRadius: '10px', px: 1.5, py: 1 }}>
            <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary' }}>{f.nombre} ({f.tipo})</Typography>
            <Typography sx={{ fontSize: '1.05rem', fontWeight: 600, ...NUM }}>{f.disponibles.toLocaleString('es-CL')}</Typography>
          </Box>
        ))}
      </Box>
      {cafs.length > 0 && (
        <Box sx={{ fontSize: '0.8rem', color: 'text.secondary', display: 'grid', gap: 0.25 }}>
          {cafs.map((c) => (
            <span key={c.id}>{c.nombre}: folios {c.desde}–{c.hasta}, siguiente {c.siguiente} · autorizado el {fecha(c.fecha_autorizacion)}</span>
          ))}
        </Box>
      )}
      {esAdmin && (
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', alignItems: 'center' }}>
          <ElegirArchivo acepta=".xml" onElegir={subir}>Subir CAF (.xml)</ElegirArchivo>
          <InputBase placeholder="Primer folio a usar (opcional)" value={primer} onChange={(e) => setPrimer(e.target.value.replace(/\D/g, ''))}
            sx={{ ...campoSx, width: 230 }} />
        </Box>
      )}
      <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary', lineHeight: 1.5 }}>
        {ambiente === 'certificacion'
          ? 'Los folios de prueba se piden en maullin.sii.cl, en el ambiente de certificación: «Timbraje electrónico» › «Solicitar timbraje».'
          : 'Los folios se piden en sii.cl › Servicios online › Factura electrónica › Sistema de facturación de mercado › «Timbraje electrónico».'}
        {' '}Si parte de los folios ya se usó en otro sistema, indique desde cuál seguir.
      </Typography>
    </>
  );
}

function Configuracion({ slug, estado, ambiente, setAmbiente, esAdmin, recargar }) {
  const cfg = estado.configuracion || {};
  const [emisor, setEmisor] = useState(null);
  const [probando, setProbando] = useState(false);
  const navigate = useNavigate();
  useEffect(() => { api.comercial.configuracion(slug).then(({ data }) => setEmisor(data.emisor)); }, [slug]);
  const pasos = Object.fromEntries(estado.pasos.map((p, i) => [p.clave, { ...p, numero: i + 1 }]));

  const guardar = async (cambios) => {
    try { await api.dte.guardarConfiguracion(slug, cambios); recargar(); } catch (e) { toast.error(msg(e, 'No se pudo guardar.')); }
  };
  const probar = async () => {
    setProbando(true);
    try {
      const { data } = await api.dte.probarConexion(slug, ambiente);
      toast.success(`El SII reconoce el certificado de ${data.titular} (${AMBIENTES[data.ambiente]}).`);
    } catch (e) { toast.error(msg(e, 'El SII no respondió.')); }
    setProbando(false);
  };
  const activar = async () => {
    try {
      await api.dte.activar(slug, ambiente);
      toast.success(ambiente === 'produccion' ? 'Listo: Ventas emite sus facturas con el SII.' : 'Listo: Ventas emite en el ambiente de certificación (pruebas).');
      recargar();
    } catch (e) { toast.error(msg(e, 'No se pudo activar.')); }
  };
  const apagar = async () => {
    if (!window.confirm('¿Apagar el facturador? Ventas deja de emitir facturas electrónicas hasta que lo vuelva a activar.')) return;
    try { await api.dte.desactivar(slug); recargar(); } catch (e) { toast.error(msg(e, 'No se pudo apagar.')); }
  };

  return (
    <Box sx={{ display: 'grid', gap: 2, maxWidth: 860 }}>
      <Tarjeta sx={{ p: 2.25, display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
        <Box sx={{ flex: 1, minWidth: 240 }}>
          <Typography sx={{ fontWeight: 600 }}>
            {estado.activo ? `Activo en ${AMBIENTES[estado.ambiente]?.toLowerCase()}` : 'Todavía no activo'}
          </Typography>
          <Typography sx={{ fontSize: '0.82rem', color: 'text.secondary', lineHeight: 1.5 }}>
            {estado.activo
              ? 'Las órdenes de venta se facturan desde Afable: se timbran, se firman y se envían al SII.'
              : 'Complete los pasos y actívelo. Mientras tanto, Ventas sigue como hoy.'}
          </Typography>
        </Box>
        <Box>
          <Rotulo>Revisar los pasos para</Rotulo>
          <Select size="small" value={ambiente} onChange={(e) => setAmbiente(e.target.value)} sx={{ fontSize: '0.86rem' }}>
            <MenuItem value="certificacion">Certificación (pruebas)</MenuItem>
            <MenuItem value="produccion">Producción</MenuItem>
          </Select>
        </Box>
      </Tarjeta>

      {estado.avisos?.map((a) => (
        <Typography key={a} sx={{ fontSize: '0.84rem', color: '#b45309' }}>⚠ {a}</Typography>
      ))}

      {/* Los datos de la empresa se editan en un solo lugar (Ajustes › Empresas › Datos y logo):
          aquí se muestran y se dice qué falta. */}
      <Paso paso={pasos.empresa} numero={pasos.empresa.numero}>
        {emisor && (
          <Box sx={{ fontSize: '0.84rem', lineHeight: 1.6 }}>
            <b>{emisor.razon_social || 'Sin razón social'}</b> · RUT {emisor.rut || '—'}<br />
            {[emisor.giro, emisor.direccion, [emisor.comuna, emisor.ciudad].filter(Boolean).join(', ')].filter(Boolean).join(' · ') || 'Sin giro ni dirección'}
            {(cfg.actecos || []).length > 0 && <><br />Actividad económica: {cfg.actecos.join(', ')}</>}
          </Box>
        )}
        <Box>
          <Button size="small" variant="outlined" onClick={() => navigate('/app/ajustes/general#facturar')}>
            Editar los datos de la empresa
          </Button>
        </Box>
      </Paso>

      <Paso paso={pasos.camino} numero={pasos.camino.numero}>
        <RadioGroup value={cfg.camino || ''} onChange={(e) => guardar({ camino: e.target.value })}>
          <FormControlLabel value="ya_emisor" disabled={!esAdmin} control={<Radio size="small" />} label={
            <Typography sx={{ fontSize: '0.86rem' }}>Sí, ya emite facturas electrónicas con otro sistema: solo cambia a Afable.</Typography>} />
          <FormControlLabel value="certificar" disabled={!esAdmin} control={<Radio size="small" />} label={
            <Typography sx={{ fontSize: '0.86rem' }}>No, o usa el sistema gratuito del SII: debe certificarse. Afable hace las pruebas por usted (pestaña Certificación).</Typography>} />
        </RadioGroup>
      </Paso>

      <Paso paso={pasos.certificado} numero={pasos.certificado.numero}>
        {estado.certificado && (
          <Typography sx={{ fontSize: '0.84rem' }}>
            {estado.certificado.titular} · RUT {estado.certificado.rut} · emitido por {estado.certificado.emitido_por} · vence el {fecha(estado.certificado.vence.slice(0, 10))}
          </Typography>
        )}
        <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary', lineHeight: 1.5 }}>
          El certificado digital de la persona que firma por la empresa (e-certchile, Acepta, E-Sign…). Esa persona debe estar
          autorizada en el SII para firmar y enviar documentos de la empresa. Se guarda cifrado.
        </Typography>
        {esAdmin && <SubirCertificado slug={slug} onListo={recargar} />}
        {estado.certificado && esAdmin && (
          <Box>
            <Button size="small" variant="outlined" startIcon={<RefreshCw size={14} />} onClick={probar} disabled={probando}>
              {probando ? 'Conectando…' : 'Probar conexión con el SII'}
            </Button>
          </Box>
        )}
      </Paso>

      <Paso paso={pasos.folios} numero={pasos.folios.numero}>
        <Folios slug={slug} estado={estado} ambiente={ambiente} esAdmin={esAdmin} onCambio={recargar} />
      </Paso>

      <Paso paso={pasos.resolucion} numero={pasos.resolucion.numero}>
        {ambiente === 'certificacion' ? (
          <Campo rotulo="Fecha de resolución del ambiente de certificación (la publica el SII en «datos de su empresa» en maullin)"
            tipo="date" valor={cfg.certificacion_fecha || ''} disabled={!esAdmin} ancho={200}
            onGuardar={(v) => guardar({ certificacion_fecha: v })} />
        ) : (
          <Box sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap' }}>
            <Campo rotulo="Número de resolución" valor={cfg.resolucion_numero ?? ''} disabled={!esAdmin} ancho={140}
              onGuardar={(v) => guardar({ resolucion_numero: v })} />
            <Campo rotulo="Fecha de resolución" tipo="date" valor={cfg.resolucion_fecha || ''} disabled={!esAdmin} ancho={180}
              onGuardar={(v) => guardar({ resolucion_fecha: v })} />
          </Box>
        )}
        <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary', lineHeight: 1.5 }}>
          {ambiente === 'certificacion'
            ? 'En certificación el número de resolución es siempre 0.'
            : 'Los datos de la autorización de la empresa como emisor electrónico: sii.cl › Factura electrónica › «Consultar empresas autorizadas».'}
        </Typography>
      </Paso>

      {esAdmin && (
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          <Button variant="contained" disabled={!estado.listo || (estado.activo && estado.ambiente === ambiente)} onClick={activar}>
            {estado.activo && estado.ambiente === ambiente ? `Activo en ${AMBIENTES[ambiente].toLowerCase()}` : `Activar en ${AMBIENTES[ambiente].toLowerCase()}`}
          </Button>
          {estado.activo && <Button variant="outlined" color="inherit" onClick={apagar}>Apagar</Button>}
        </Box>
      )}
      {!esAdmin && (
        <Typography sx={{ fontSize: '0.82rem', color: 'text.secondary' }}>Solo un administrador de la empresa puede cambiar esta configuración.</Typography>
      )}
    </Box>
  );
}

// ── Emitidos: la bitácora ──────────────────────────────────────────────────────────────────

const CODIGOS = [
  { valor: 1, nombre: 'Anula el documento', ayuda: 'Copia todas sus líneas: el documento queda sin efecto.' },
  { valor: 2, nombre: 'Corrige un texto', ayuda: 'Montos en cero. Escriba qué decía y qué debe decir (por ejemplo, la dirección).' },
  { valor: 3, nombre: 'Corrige montos', ayuda: 'Una devolución, un descuento posterior o un cobro adicional.' },
];

function DialogoNota({ slug, documento, onCerrar, onEmitida }) {
  const [tipo, setTipo] = useState(documento?.tipo === 61 ? 56 : 61);
  const [codigo, setCodigo] = useState(1);
  const [razon, setRazon] = useState('');
  const [lineas, setLineas] = useState([{ nombre: '', cantidad: '1', precio: '' }]);
  const [enviando, setEnviando] = useState(false);
  if (!documento) return null;
  const emitir = async () => {
    setEnviando(true);
    try {
      const datos = { tipo, codigo, razon };
      if (codigo === 3) datos.lineas = lineas.filter((l) => l.nombre && l.precio).map((l) => ({ ...l, cantidad: l.cantidad.replace(',', '.'), precio: l.precio.replace(/\./g, '').replace(',', '.') }));
      const { data } = await api.dte.nota(slug, documento.id, datos);
      toast.success(`${data.nombre} N° ${data.folio} emitida.`);
      onEmitida();
    } catch (e) { toast.error(msg(e, 'No se pudo emitir la nota.')); }
    setEnviando(false);
  };
  const cambiarLinea = (i, k, v) => setLineas((ls) => ls.map((l, j) => (j === i ? { ...l, [k]: v } : l)));
  return (
    <Dialog open onClose={onCerrar} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ fontWeight: 600 }}>Nota sobre {documento.nombre.toLowerCase()} N° {documento.folio}</DialogTitle>
      <DialogContent sx={{ display: 'grid', gap: 2 }}>
        <Select size="small" value={tipo} onChange={(e) => setTipo(e.target.value)} sx={{ fontSize: '0.86rem' }}>
          <MenuItem value={61}>Nota de crédito (resta)</MenuItem>
          <MenuItem value={56}>Nota de débito (suma)</MenuItem>
        </Select>
        <RadioGroup value={codigo} onChange={(e) => setCodigo(Number(e.target.value))}>
          {CODIGOS.map((c) => (
            <FormControlLabel key={c.valor} value={c.valor} control={<Radio size="small" />} label={
              <Box><Typography sx={{ fontSize: '0.86rem' }}>{c.nombre}</Typography>
                <Typography sx={{ fontSize: '0.76rem', color: 'text.secondary' }}>{c.ayuda}</Typography></Box>} />
          ))}
        </RadioGroup>
        <Box>
          <Rotulo>Razón (sale impresa y la ve el cliente)</Rotulo>
          <InputBase fullWidth value={razon} onChange={(e) => setRazon(e.target.value.slice(0, 90))}
            placeholder={codigo === 2 ? 'Donde dice … debe decir …' : 'Devolución de mercaderías'} sx={campoSx} />
        </Box>
        {codigo === 3 && (
          <Box sx={{ display: 'grid', gap: 1 }}>
            <Rotulo>Líneas (montos netos)</Rotulo>
            {lineas.map((l, i) => (
              <Box key={i} sx={{ display: 'flex', gap: 1 }}>
                <InputBase placeholder="Descripción" value={l.nombre} onChange={(e) => cambiarLinea(i, 'nombre', e.target.value)} sx={{ ...campoSx, flex: 1 }} />
                <InputBase placeholder="Cant." value={l.cantidad} onChange={(e) => cambiarLinea(i, 'cantidad', e.target.value)} sx={{ ...campoSx, width: 70 }} />
                <InputBase placeholder="Precio" value={l.precio} onChange={(e) => cambiarLinea(i, 'precio', e.target.value)} sx={{ ...campoSx, width: 110 }} />
                <IconButton size="small" onClick={() => setLineas((ls) => ls.filter((_, j) => j !== i))} disabled={lineas.length === 1}><Trash2 size={14} /></IconButton>
              </Box>
            ))}
            <Box><Button size="small" startIcon={<Plus size={14} />} onClick={() => setLineas((ls) => [...ls, { nombre: '', cantidad: '1', precio: '' }])}>Agregar línea</Button></Box>
          </Box>
        )}
      </DialogContent>
      <DialogActions>
        <Button color="inherit" onClick={onCerrar}>Cancelar</Button>
        <Button variant="contained" disabled={!razon.trim() || enviando} onClick={emitir}>{enviando ? 'Emitiendo…' : 'Emitir nota'}</Button>
      </DialogActions>
    </Dialog>
  );
}

function DialogoEnvio({ slug, envioId, onCerrar, esEditor }) {
  const [envio, setEnvio] = useState(null);
  const [trabajando, setTrabajando] = useState(false);
  useEffect(() => { if (envioId) api.dte.envio(slug, envioId).then(({ data }) => setEnvio(data)); }, [slug, envioId]);
  if (!envioId) return null;
  const reintentar = async () => {
    setTrabajando(true);
    try { const { data } = await api.dte.reintentar(slug, envioId); setEnvio(data); } catch (e) { toast.error(msg(e, 'No se pudo.')); }
    setTrabajando(false);
  };
  return (
    <Dialog open onClose={onCerrar} maxWidth="md" fullWidth>
      <DialogTitle sx={{ fontWeight: 600 }}>Envío al SII</DialogTitle>
      <DialogContent sx={{ display: 'grid', gap: 1.25 }}>
        {!envio ? <CircularProgress size={20} /> : (
          <>
            <Typography sx={{ fontSize: '0.88rem' }}>
              {AMBIENTES[envio.ambiente]} · {envio.estado_nombre}{envio.trackid ? ` · N° de seguimiento ${envio.trackid}` : ''}
              {envio.estado_sii ? ` · SII: ${envio.estado_sii}${envio.glosa ? ` (${envio.glosa})` : ''}` : ''}
            </Typography>
            {envio.error && <Typography sx={{ fontSize: '0.84rem', color: '#c8102e' }}>{envio.error}</Typography>}
            {envio.resumen?.map((r) => (
              <Typography key={r.tipo} sx={{ fontSize: '0.82rem', color: 'text.secondary' }}>
                Tipo {r.tipo}: {r.informados} informados, {r.aceptados} aceptados, {r.rechazados} rechazados, {r.reparos} con reparos
              </Typography>
            ))}
            {envio.siguiente_intento && !['aceptado', 'reparos', 'rechazado'].includes(envio.estado) && (
              <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary' }}>
                Próxima consulta al SII: {new Date(envio.siguiente_intento).toLocaleString('es-CL')} (intentos: {envio.intentos})
              </Typography>
            )}
            {envio.respuesta && (
              <Box component="pre" sx={{ fontSize: '0.72rem', bgcolor: 'action.hover', p: 1.25, borderRadius: '8px', overflow: 'auto', maxHeight: 240, m: 0 }}>
                {envio.respuesta}
              </Box>
            )}
          </>
        )}
      </DialogContent>
      <DialogActions>
        {esEditor && envio && !['aceptado', 'reparos', 'rechazado'].includes(envio.estado) && (
          <Button startIcon={<RefreshCw size={14} />} onClick={reintentar} disabled={trabajando}>
            {envio.estado === 'por_subir' ? 'Subir ahora' : 'Consultar ahora'}
          </Button>
        )}
        <Button onClick={onCerrar}>Cerrar</Button>
      </DialogActions>
    </Dialog>
  );
}

function Emitidos({ slug, esEditor }) {
  const [lista, setLista] = useState(null);
  const [filtro, setFiltro] = useState({ ambiente: '', estado: '' });
  const [nota, setNota] = useState(null);
  const [envio, setEnvio] = useState(null);
  const cargar = useCallback(() => {
    const params = Object.fromEntries(Object.entries(filtro).filter(([, v]) => v));
    api.dte.documentos(slug, params).then(({ data }) => setLista(data)).catch(() => setLista([]));
  }, [slug, filtro]);
  useEffect(() => { cargar(); }, [cargar]);
  // Mientras haya algo en revisión del SII, la lista se refresca sola.
  useEffect(() => {
    if (!lista?.some((d) => ['por_enviar', 'enviado'].includes(d.estado))) return undefined;
    const t = setInterval(cargar, 20000);
    return () => clearInterval(t);
  }, [lista, cargar]);

  const nombreArchivo = (d, ext) => `${d.nombre} ${d.folio}.${ext}`;
  const telefono = useMediaQuery('(max-width:700px)');
  const acciones = (d) => (
    <>
      <Tooltip title="PDF"><IconButton size="small" onClick={() => descargar(api.dte.pdf(slug, d.id), nombreArchivo(d, 'pdf'))}><FileText size={15} /></IconButton></Tooltip>
      {[33, 34, 52].includes(d.tipo) && (
        <Tooltip title="PDF copia cedible"><IconButton size="small" onClick={() => descargar(api.dte.pdf(slug, d.id, true), `${d.nombre} ${d.folio} cedible.pdf`)}><FileText size={15} strokeWidth={2.6} /></IconButton></Tooltip>
      )}
      <Tooltip title="XML"><IconButton size="small" onClick={() => descargar(api.dte.xml(slug, d.id), nombreArchivo(d, 'xml'))}><FileCode size={15} /></IconButton></Tooltip>
      {esEditor && [33, 34, 56, 61].includes(d.tipo) && d.estado !== 'rechazado' && (
        <Button size="small" sx={{ ml: 0.5, fontSize: '0.76rem' }} onClick={() => setNota(d)}>Nota</Button>
      )}
    </>
  );
  const estadoDe = (d) => (
    <Box sx={{ cursor: d.envio ? 'pointer' : 'default', display: 'inline-block' }} onClick={() => d.envio && setEnvio(d.envio)}>
      <ChipEstado estado={d.estado} nombre={d.estado_nombre} detalle={d.detalle_estado} />
    </Box>
  );
  return (
    <Box sx={{ display: 'grid', gap: 1.5 }}>
      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
        <Select size="small" displayEmpty value={filtro.ambiente} onChange={(e) => setFiltro((f) => ({ ...f, ambiente: e.target.value }))} sx={{ fontSize: '0.84rem', minWidth: 170 }}>
          <MenuItem value="">Todos los ambientes</MenuItem>
          <MenuItem value="produccion">Producción</MenuItem>
          <MenuItem value="certificacion">Certificación</MenuItem>
        </Select>
        <Select size="small" displayEmpty value={filtro.estado} onChange={(e) => setFiltro((f) => ({ ...f, estado: e.target.value }))} sx={{ fontSize: '0.84rem', minWidth: 170 }}>
          <MenuItem value="">Todos los estados</MenuItem>
          {[['por_enviar', 'Por enviar'], ['enviado', 'Enviado al SII'], ['aceptado', 'Aceptado'], ['reparos', 'Con reparos'], ['rechazado', 'Rechazado']]
            .map(([v, n]) => <MenuItem key={v} value={v}>{n}</MenuItem>)}
        </Select>
      </Box>
      {!lista ? <CircularProgress size={20} /> : lista.length === 0 ? (
        <Typography sx={{ color: 'text.secondary', fontSize: '0.88rem', py: 3 }}>
          Todavía no hay documentos emitidos. Se emiten desde cada orden de venta («Facturar») o pidiéndolo en el chat.
        </Typography>
      ) : telefono ? (
        <Box sx={{ display: 'grid', gap: 1 }}>
          {lista.map((d) => (
            <Tarjeta key={d.id} sx={{ p: 1.5, display: 'grid', gap: 0.75 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 1 }}>
                <Typography sx={{ fontSize: '0.88rem' }}>{d.nombre} <b>N° {d.folio}</b></Typography>
                <Typography sx={{ fontSize: '0.88rem', fontWeight: 600, ...NUM }}>{clp(d.monto_total)}</Typography>
              </Box>
              <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary' }}>
                {d.receptor_razon_social} · {fecha(d.fecha)}{d.ambiente === 'certificacion' ? ' · prueba' : ''}
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>{estadoDe(d)}<Box>{acciones(d)}</Box></Box>
            </Tarjeta>
          ))}
        </Box>
      ) : (
        <Tarjeta sx={{ overflowX: 'auto' }}>
          <Box component="table" sx={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem',
            '& th': { textAlign: 'left', fontWeight: 500, color: 'text.secondary', fontSize: '0.76rem', px: 1.5, py: 1, borderBottom: '1px solid', borderColor: 'divider' },
            '& td': { px: 1.5, py: 1, borderBottom: '1px solid', borderColor: 'divider', verticalAlign: 'middle' } }}>
            <thead><tr><th>Fecha</th><th>Documento</th><th>Cliente</th><th style={{ textAlign: 'right' }}>Total</th><th>Estado</th><th /></tr></thead>
            <tbody>
              {lista.map((d) => (
                <tr key={d.id}>
                  <td style={{ whiteSpace: 'nowrap' }}>{fecha(d.fecha)}</td>
                  <td>
                    {d.nombre} <b>N° {d.folio}</b>
                    {d.ambiente === 'certificacion' && <Chip size="small" label="prueba" sx={{ ml: 0.75, height: 18, fontSize: '0.68rem' }} />}
                  </td>
                  <td>{d.receptor_razon_social}<Typography component="span" sx={{ display: 'block', fontSize: '0.74rem', color: 'text.secondary' }}>{d.receptor_rut}</Typography></td>
                  <td style={{ textAlign: 'right', ...NUM }}>{clp(d.monto_total)}</td>
                  <td>{estadoDe(d)}</td>
                  <td style={{ whiteSpace: 'nowrap', textAlign: 'right' }}>{acciones(d)}</td>
                </tr>
              ))}
            </tbody>
          </Box>
        </Tarjeta>
      )}
      <DialogoNota key={nota?.id} slug={slug} documento={nota} onCerrar={() => setNota(null)} onEmitida={() => { setNota(null); cargar(); }} />
      <DialogoEnvio key={envio} slug={slug} envioId={envio} esEditor={esEditor} onCerrar={() => { setEnvio(null); cargar(); }} />
    </Box>
  );
}

// ── La página ──────────────────────────────────────────────────────────────────────────────

export default function FacturacionElectronica({ slug, esEditor, esAdmin }) {
  const [estado, setEstado] = useState(null);
  const [ambiente, setAmbiente] = useState(null);
  const [pestana, setPestana] = useState(null);
  const recargar = useCallback(() => {
    api.dte.estado(slug, ambiente || undefined).then(({ data }) => {
      setEstado(data);
      if (!ambiente) setAmbiente(data.ambiente_revisado);
      setPestana((p) => p || (data.activo ? 'emitidos' : 'configuracion'));
    }).catch(() => setEstado({ disponible: false }));
  }, [slug, ambiente]);
  useEffect(() => { recargar(); }, [recargar]);

  if (!estado) return <CircularProgress size={20} />;
  if (!estado.disponible) {
    return <Typography sx={{ color: 'text.secondary' }}>El facturador electrónico de Afable todavía no está habilitado para su empresa.</Typography>;
  }
  const certificar = estado.configuracion?.camino === 'certificar';
  return (
    <Box sx={{ display: 'grid', gap: 2 }}>
      <Tabs value={pestana} onChange={(_, v) => setPestana(v)} variant="scrollable" scrollButtons={false} sx={{ minHeight: 36, '& .MuiTab-root': { minHeight: 36, textTransform: 'none', fontSize: '0.88rem' } }}>
        <Tab value="emitidos" label="Emitidos" />
        <Tab value="configuracion" label={<Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>Configuración
          {!estado.listo && <Circle size={7} fill="#b45309" color="#b45309" />}</Box>} />
        {certificar && <Tab value="certificacion" label="Certificación" />}
        <Tab value="casilla" label="Casilla de intercambio" />
      </Tabs>
      {pestana === 'emitidos' && <Emitidos slug={slug} esEditor={esEditor} />}
      {pestana === 'configuracion' && ambiente && (
        <Configuracion slug={slug} estado={estado} ambiente={ambiente} setAmbiente={setAmbiente} esAdmin={esAdmin} recargar={recargar} />
      )}
      {pestana === 'certificacion' && <Certificacion slug={slug} esAdmin={esAdmin} />}
      {pestana === 'casilla' && <Casilla slug={slug} esAdmin={esAdmin} recargar={recargar} />}
    </Box>
  );
}
