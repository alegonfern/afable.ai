import { useCallback, useEffect, useState } from 'react';
import {
  Box, Button, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, FormControlLabel, InputBase, Switch,
  TextField, Typography,
} from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { CheckCircle2, ExternalLink, RefreshCw, XCircle } from 'lucide-react';
import { toast } from 'react-toastify';
import { useWorkspace } from '../../context/WorkspaceContext';
import { api } from '../../services/api';

/*
 * Conectar y gestionar un conector que ya funciona (27-10-2026): cómo se conecta, sus opciones,
 * sincronizar ahora, el último resultado y el historial. Lo propio de cada tipo está en TEXTOS y en
 * las opciones; el resto es igual para todos.
 */

const msg = (e, d) => e?.response?.data?.detail || d;
const cuando = (iso) => (iso ? new Date(iso).toLocaleString('es-CL', { dateStyle: 'short', timeStyle: 'short' }) : '—');

const TEXTOS = {
  hubspot: {
    queHace: 'Trae las empresas y contactos de HubSpot como clientes de Afable, y convierte cada negocio ganado en una cotización en borrador para revisar y confirmar.',
    pasos: [
      'En HubSpot, entre a Configuración (el engranaje) › Integraciones › Apps privadas › Crear una app privada.',
      'Póngale de nombre «Afable» y, en Alcances, marque crm.objects.companies.read, crm.objects.contacts.read y crm.objects.deals.read (y crm.schemas.companies.read si guarda el RUT en una propiedad propia).',
      'Cree la app, copie el token de acceso (empieza con «pat-») y péguelo aquí.',
    ],
    opciones: [
      ['importar_empresas', 'Importar las empresas como clientes'],
      ['importar_contactos', 'Importar los contactos'],
      ['negocios_a_cotizacion', 'Cada negocio ganado crea una cotización en borrador'],
      ['automatico', 'Sincronizar solo cada 6 horas'],
    ],
  },
  sii_rcv: {
    queHace: 'Descarga del SII el Registro de Compras y Ventas de la empresa con su certificado digital y lo deja listo para revisar en Contabilidad › Documentos, sin bajar ni subir archivos.',
    pasos: [
      'Usa el certificado digital que la empresa ya subió para la facturación electrónica. Si todavía no lo tiene, súbalo en Ajustes › Empresas › Facturación electrónica.',
      'La persona del certificado debe tener habilitada la autenticación con certificado en sii.cl.',
    ],
    opciones: [
      ['automatico', 'Descargar solo cada día (7:00)'],
      ['confirmar_solo', 'Confirmar la carga sin revisar (si no, queda para revisar)'],
    ],
  },
};

function Resultado({ tipo, r }) {
  const navigate = useNavigate();
  if (!r || !Object.keys(r).length) return null;
  if (tipo === 'hubspot') {
    const p = (o) => (o ? `${o.nuevas ?? o.nuevos ?? 0} nuevas, ${o.actualizadas ?? o.ya_estaban ?? 0} ${o.actualizadas != null ? 'actualizadas' : 'ya estaban'}` : '—');
    return (
      <Box sx={{ fontSize: '0.82rem', color: 'text.secondary', display: 'grid', gap: 0.25 }}>
        <span>Empresas: {p(r.empresas)}</span>
        <span>Contactos: {p(r.contactos)}</span>
        <span>Cotizaciones: {p(r.cotizaciones)}</span>
        {r.avisos?.map((a) => <span key={a}>· {a}</span>)}
      </Box>
    );
  }
  return (
    <Box sx={{ fontSize: '0.82rem', color: 'text.secondary', display: 'grid', gap: 0.25 }}>
      {(r.cargas || []).map((c) => (
        <span key={`${c.libro}-${c.periodo}`}>
          Libro de {c.libro} {c.periodo}: {c.filas} documentos · {c.nuevos ?? 0} nuevos · {c.ya_estaban ?? 0} ya estaban
          {c.errores?.length ? ` · ${c.errores.length} con problemas` : ''}
        </span>
      ))}
      {(r.cargas || []).length === 0 && <span>Sin documentos nuevos en el período.</span>}
      {r.enlace && <Box><Button size="small" sx={{ px: 0 }} onClick={() => navigate(r.enlace)}>Revisar en Contabilidad › Documentos</Button></Box>}
    </Box>
  );
}

export default function DialogoConector({ tipo, nombre, onCerrar, onCambio }) {
  const { slug, esAdmin, esEditor } = useWorkspace();
  const navigate = useNavigate();
  const [c, setC] = useState(null);
  const [historial, setHistorial] = useState([]);
  const [token, setToken] = useState('');
  const [periodo, setPeriodo] = useState(() => new Date().toISOString().slice(0, 7));
  const [trabajando, setTrabajando] = useState('');
  const t = TEXTOS[tipo];

  const cargar = useCallback(() => {
    api.conectores.detalle(slug, tipo).then(({ data }) => setC(data)).catch((e) => toast.error(msg(e, 'No se pudo leer el conector.')));
    api.conectores.historial(slug, tipo).then(({ data }) => setHistorial(data)).catch(() => {});
  }, [slug, tipo]);
  useEffect(() => { cargar(); }, [cargar]);

  const hacer = async (clave, llamada, exito) => {
    setTrabajando(clave);
    try { await llamada(); if (exito) toast.success(exito); cargar(); onCambio?.(); }
    catch (e) { toast.error(msg(e, 'No se pudo.')); cargar(); }
    setTrabajando('');
  };
  const conectar = () => hacer('conectar', () => api.conectores.conectar(slug, tipo, tipo === 'hubspot' ? { token: token.trim() } : {}), `${nombre} conectado.`);
  const sincronizar = () => hacer('sincronizar', () => api.conectores.sincronizar(slug, tipo, tipo === 'sii_rcv' ? { periodo: periodo.replace('-', '') } : {}), 'Sincronización terminada.');
  const desconectar = () => {
    if (!window.confirm(`¿Desconectar ${nombre}? Lo ya importado se queda en Afable.`)) return;
    hacer('desconectar', () => api.conectores.desconectar(slug, tipo), `${nombre} desconectado.`);
  };
  const opcion = (k, v) => hacer('opcion', () => api.conectores.opciones(slug, tipo, { [k]: v }));
  const libros = c?.config?.libros || [];
  const cambiarLibro = (l, on) => opcion('libros', on ? [...new Set([...libros, l])] : libros.filter((x) => x !== l));

  const conectado = c && c.estado !== 'desconectado';
  return (
    <Dialog open onClose={onCerrar} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: 1 }}>
        <Box sx={{ flex: 1 }}>{nombre}</Box>
        {c && (
          <Box component="span" sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5, fontSize: '0.8rem', fontWeight: 500 }}>
            {c.estado === 'conectado' ? <CheckCircle2 size={15} color="#0f9d6b" /> : c.estado === 'error' ? <XCircle size={15} color="#c8102e" /> : null}
            {{ conectado: 'Conectado', error: 'Con error', desconectado: 'Sin conectar' }[c.estado]}
          </Box>
        )}
      </DialogTitle>
      <DialogContent sx={{ display: 'grid', gap: 2 }}>
        {!c ? <CircularProgress size={20} /> : (
          <>
            <Typography sx={{ fontSize: '0.86rem', lineHeight: 1.6 }}>{t.queHace}</Typography>

            {c.requisitos?.length > 0 && (
              <Box sx={{ border: '1px solid', borderColor: '#f3d9b1', bgcolor: '#fffaf2', borderRadius: '10px', p: 1.5, fontSize: '0.84rem' }}>
                <b>Antes de conectar falta:</b>
                <Box component="ul" sx={{ m: 0, mt: 0.5, pl: 2.5 }}>{c.requisitos.map((r) => <li key={r}>{r}</li>)}</Box>
                {tipo === 'sii_rcv' && (
                  <Button size="small" sx={{ mt: 0.5, px: 0 }} onClick={() => navigate('/app/ajustes/facturacion-electronica')}>
                    Ir a subir el certificado
                  </Button>
                )}
              </Box>
            )}

            {!conectado && (
              <Box sx={{ display: 'grid', gap: 1 }}>
                <Typography sx={{ fontWeight: 600, fontSize: '0.88rem' }}>Cómo conectarlo</Typography>
                <Box component="ol" sx={{ m: 0, pl: 2.5, fontSize: '0.84rem', lineHeight: 1.6, color: 'text.secondary' }}>
                  {t.pasos.map((p) => <li key={p}>{p}</li>)}
                </Box>
                {tipo === 'hubspot' && esAdmin && (
                  <InputBase type="password" placeholder="pat-na1-…" value={token} onChange={(e) => setToken(e.target.value)}
                    inputProps={{ 'aria-label': 'Token de la app privada de HubSpot' }}
                    sx={{ border: '1px solid', borderColor: 'divider', borderRadius: '8px', px: 1.25, py: 0.5, fontSize: '0.88rem' }} />
                )}
                {tipo === 'hubspot' && (
                  <Typography component="a" href="https://developers.hubspot.com/docs/api/private-apps" target="_blank" rel="noreferrer"
                    sx={{ fontSize: '0.8rem', display: 'inline-flex', alignItems: 'center', gap: 0.5 }}>
                    Guía de HubSpot sobre apps privadas <ExternalLink size={12} />
                  </Typography>
                )}
              </Box>
            )}

            {conectado && (
              <>
                {Object.keys(c.cuenta || {}).length > 0 && (
                  <Typography sx={{ fontSize: '0.82rem', color: 'text.secondary' }}>
                    {tipo === 'hubspot'
                      ? `Portal ${c.cuenta.portal_id || ''}${c.cuenta.moneda ? ` · ${c.cuenta.moneda}` : ''}`
                      : `RUT ${c.cuenta.rut || ''}${c.cuenta.titular ? ` · certificado de ${c.cuenta.titular}` : ''}`}
                  </Typography>
                )}
                <Box sx={{ display: 'grid' }}>
                  {tipo === 'sii_rcv' && ['compras', 'ventas'].map((l) => (
                    <FormControlLabel key={l} disabled={!esAdmin || !!trabajando}
                      control={<Switch size="small" checked={libros.includes(l)} onChange={(e) => cambiarLibro(l, e.target.checked)} />}
                      label={<Typography sx={{ fontSize: '0.86rem' }}>Libro de {l}</Typography>} />
                  ))}
                  {t.opciones.map(([k, n]) => (
                    <FormControlLabel key={k} disabled={!esAdmin || !!trabajando}
                      control={<Switch size="small" checked={!!c.config?.[k]} onChange={(e) => opcion(k, e.target.checked)} />}
                      label={<Typography sx={{ fontSize: '0.86rem' }}>{n}</Typography>} />
                  ))}
                </Box>
                {c.ultimo_error && (
                  <Box sx={{ border: '1px solid', borderColor: '#f5c2c7', bgcolor: '#fff5f5', borderRadius: '10px', p: 1.5, fontSize: '0.84rem', color: '#8a1020' }}>
                    {c.ultimo_error}
                  </Box>
                )}
                <Box sx={{ display: 'grid', gap: 0.75 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                    <Typography sx={{ fontWeight: 600, fontSize: '0.88rem', flex: 1 }}>
                      Última sincronización: <Box component="span" sx={{ fontWeight: 400, color: 'text.secondary' }}>{cuando(c.ultima_sincronizacion)}</Box>
                    </Typography>
                    {tipo === 'sii_rcv' && (
                      <TextField size="small" type="month" label="Período" InputLabelProps={{ shrink: true }} value={periodo} onChange={(e) => setPeriodo(e.target.value)} />
                    )}
                    {esEditor && (
                      <Button size="small" variant="contained" startIcon={<RefreshCw size={14} />} onClick={sincronizar} disabled={!!trabajando}>
                        {trabajando === 'sincronizar' ? 'Sincronizando…' : tipo === 'sii_rcv' ? 'Descargar ahora' : 'Sincronizar ahora'}
                      </Button>
                    )}
                  </Box>
                  <Resultado tipo={tipo} r={c.ultimo_resultado} />
                </Box>
                {historial.length > 0 && (
                  <Box>
                    <Typography sx={{ fontWeight: 600, fontSize: '0.84rem', mb: 0.5 }}>Historial</Typography>
                    <Box sx={{ display: 'grid', gap: 0.25, fontSize: '0.78rem', color: 'text.secondary', maxHeight: 160, overflow: 'auto' }}>
                      {historial.map((h) => (
                        <span key={h.id}>
                          {cuando(h.inicio)} · {h.automatica ? 'automática' : (h.usuario || 'manual')} · {h.estado === 'ok' ? 'bien' : `error: ${h.error}`}
                        </span>
                      ))}
                    </Box>
                  </Box>
                )}
              </>
            )}
          </>
        )}
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        {conectado && esAdmin && <Button color="inherit" onClick={desconectar} disabled={!!trabajando} sx={{ mr: 'auto' }}>Desconectar</Button>}
        <Button onClick={onCerrar}>Cerrar</Button>
        {c && !conectado && esAdmin && (
          <Button variant="contained" onClick={conectar}
            disabled={!!trabajando || (tipo === 'hubspot' && !token.trim()) || (c.requisitos?.length > 0)}>
            {trabajando === 'conectar' ? 'Conectando…' : 'Conectar'}
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
}
