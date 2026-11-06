import { useCallback, useEffect, useState } from 'react';
import {
  Box, Button, Chip, CircularProgress, IconButton, InputBase, MenuItem, Select, Tooltip, Typography,
} from '@mui/material';
import { Check, FileCode, RefreshCw } from 'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../../services/api';
import { Tarjeta, descargar } from '../comercial/comun';
import { ElegirArchivo } from './piezas';

/*
 * La certificación ante el SII (26-10-2026), para la empresa que todavía no está autorizada como
 * emisor electrónico. Afable arma y envía todo lo que el SII pide en el ambiente de pruebas
 * (maullin); la persona solo hace lo que el SII exige con su clave: postular, descargar el set y
 * declarar el avance.
 */

const campoSx = { border: '1px solid', borderColor: 'divider', borderRadius: '8px', px: 1.25, py: 0.6, fontSize: '0.84rem' };
const msg = (e, d) => e?.response?.data?.detail || d;

/* Un blob de error trae el JSON del detalle adentro: se lee para mostrarlo. */
async function errorDeBlob(e, porDefecto) {
  try { return JSON.parse(await e.response.data.text()).detail || porDefecto; } catch { return porDefecto; }
}

function PasoCert({ p, numero }) {
  return (
    <Tarjeta sx={{ p: 2, display: 'grid', gap: 1, borderColor: p.actual ? 'text.primary' : 'divider' }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25 }}>
        <Box sx={{ width: 24, height: 24, borderRadius: '50%', display: 'grid', placeItems: 'center', flexShrink: 0, fontSize: '0.78rem', fontWeight: 600,
          bgcolor: p.listo ? '#0f9d6b' : p.actual ? 'text.primary' : 'action.selected', color: p.listo || p.actual ? 'background.paper' : 'text.secondary' }}>
          {p.listo ? <Check size={14} /> : numero}
        </Box>
        <Typography sx={{ fontWeight: 600, fontSize: '0.92rem', flex: 1 }}>{p.titulo}</Typography>
        {p.actual && <Chip size="small" label="Ahora" sx={{ height: 20, fontSize: '0.7rem' }} />}
      </Box>
      {p.afable && <Typography sx={{ fontSize: '0.82rem', lineHeight: 1.5 }}><b>Afable:</b> {p.afable}</Typography>}
      {p.usted?.length > 0 && (
        <Box component="ul" sx={{ m: 0, pl: 2.5, fontSize: '0.82rem', lineHeight: 1.6, color: 'text.secondary' }}>
          {p.usted.map((u) => <li key={u}>{u}</li>)}
        </Box>
      )}
    </Tarjeta>
  );
}

export default function Certificacion({ slug, esAdmin }) {
  const [estado, setEstado] = useState(null);
  const [texto, setTexto] = useState('');
  const [cantidad, setCantidad] = useState('20');
  const [trabajando, setTrabajando] = useState('');
  const cargar = useCallback(() => api.dte.certificacion(slug).then(({ data }) => setEstado(data)).catch((e) => {
    toast.error(msg(e, 'No se pudo leer la certificación.'));
    setEstado({ pasos: [], sets: [], envios: [], requisitos: [], aceptados: [] });
  }), [slug]);
  useEffect(() => { cargar(); }, [cargar]);

  const hacer = async (clave, llamada, exito) => {
    setTrabajando(clave);
    try {
      const { data } = await llamada();
      if (data && data.pasos) setEstado(data);
      if (exito) toast.success(typeof exito === 'function' ? exito(data) : exito);
    } catch (e) { toast.error(msg(e, 'No se pudo.')); }
    setTrabajando('');
  };
  const cargarSet = (archivo) => hacer('set', () => api.dte.cargarSet(slug, archivo ? null : texto, archivo),
    'Set de pruebas cargado. Revise cómo quedó interpretado antes de generar.');
  const intercambio = async (archivo) => {
    setTrabajando('intercambio');
    try { await descargar(api.dte.intercambioCertificacion(slug, archivo), 'Respuestas de intercambio.zip'); }
    catch (e) { toast.error(await errorDeBlob(e, 'No se pudieron armar las respuestas.')); }
    setTrabajando('');
  };

  if (!estado) return <CircularProgress size={20} />;
  const ocupado = !!trabajando || !esAdmin;
  return (
    <Box sx={{ display: 'grid', gap: 2, maxWidth: 940 }}>
      {estado.requisitos?.length > 0 && (
        <Typography sx={{ fontSize: '0.84rem', color: '#b45309' }}>Falta: {estado.requisitos.join('; ')}.</Typography>
      )}

      <Box sx={{ display: 'grid', gap: 1.25 }}>
        {estado.pasos.map((p, i) => <PasoCert key={p.clave} p={p} numero={i + 1} />)}
      </Box>

      <Tarjeta sx={{ p: 2.25, display: 'grid', gap: 1.5 }}>
        <Typography sx={{ fontWeight: 600 }}>Set de pruebas</Typography>
        <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary', lineHeight: 1.5 }}>
          Descárguelo en maullin.sii.cl › «Set de prueba» y péguelo aquí tal cual (o suba el archivo). Afable lo interpreta caso por caso.
        </Typography>
        {esAdmin && (
          <>
            <InputBase multiline minRows={4} maxRows={14} value={texto} onChange={(e) => setTexto(e.target.value)}
              placeholder="SET BASICO - NUMERO DE ATENCION: …" sx={{ ...campoSx, fontFamily: 'monospace' }} />
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
              <Button size="small" variant="contained" disabled={!texto.trim() || ocupado} onClick={() => cargarSet(null)}>Cargar el texto</Button>
              <ElegirArchivo acepta=".txt,.text" onElegir={cargarSet} disabled={ocupado}>Subir archivo del set</ElegirArchivo>
            </Box>
          </>
        )}
        {estado.sets?.map((s) => (
          <Box key={`${s.tipo_set}-${s.atencion}`} sx={{ borderTop: '1px solid', borderColor: 'divider', pt: 1.25 }}>
            <Typography sx={{ fontSize: '0.86rem', fontWeight: 600 }}>{s.nombre} · atención {s.atencion}</Typography>
            {s.problemas?.length > 0 && <Typography sx={{ fontSize: '0.8rem', color: '#b45309' }}>{s.problemas.join('; ')}</Typography>}
            <Box sx={{ fontSize: '0.8rem', color: 'text.secondary', display: 'grid', gap: 0.25, mt: 0.5 }}>
              {s.casos?.map((c) => (
                <span key={c.caso}>
                  Caso {c.caso}: {c.documento}{c.items?.length ? ` · ${c.items.length} ítem${c.items.length === 1 ? '' : 's'}` : ''}
                  {c.referencia_caso ? ` · referencia al caso ${c.referencia_caso}` : ''}{c.razon ? ` (${c.razon})` : ''}
                  {c.problemas?.length ? <b style={{ color: '#b45309' }}> · {c.problemas.join('; ')}</b> : null}
                </span>
              ))}
              {s.compras?.length > 0 && <span>{s.compras.length} documentos de compra para el libro de compras</span>}
            </Box>
          </Box>
        ))}
      </Tarjeta>

      <Tarjeta sx={{ p: 2.25, display: 'grid', gap: 1.5 }}>
        <Typography sx={{ fontWeight: 600 }}>Generar y enviar a maullin</Typography>
        {estado.folios && (
          <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary' }}>
            Folios de certificación: {Object.entries(estado.folios).map(([t, n]) => `${t}: ${n}`).join(' · ') || 'ninguno'}
          </Typography>
        )}
        {esAdmin && (
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', alignItems: 'center' }}>
            <Button size="small" variant="outlined" disabled={ocupado} onClick={() => hacer('set', () => api.dte.generarCertificacion(slug, 'set'),
              (d) => `Set generado: ${d.generados?.length ?? 0} envío(s).`)}>Generar el set</Button>
            <Button size="small" variant="outlined" disabled={ocupado} onClick={() => hacer('libros', () => api.dte.generarCertificacion(slug, 'libros'),
              'Libros generados.')}>Generar los libros</Button>
            <InputBase value={cantidad} onChange={(e) => setCantidad(e.target.value.replace(/\D/g, ''))} sx={{ ...campoSx, width: 60 }} />
            <Button size="small" variant="outlined" disabled={ocupado} onClick={() => hacer('simulacion',
              () => api.dte.generarCertificacion(slug, 'simulacion', { cantidad: Number(cantidad) || 20 }), 'Simulación generada.')}>
              Generar la simulación
            </Button>
            <Box sx={{ flex: 1 }} />
            <Button size="small" variant="contained" disabled={ocupado} onClick={() => hacer('subir', () => api.dte.subirCertificacion(slug),
              (d) => `${d.subidos?.length ?? 0} envío(s) subido(s) a maullin.`)}>Subir lo pendiente</Button>
            <Button size="small" startIcon={<RefreshCw size={14} />} disabled={ocupado} onClick={() => hacer('consultar', () => api.dte.consultarCertificacion(slug))}>
              Consultar al SII
            </Button>
          </Box>
        )}
        {estado.envios?.length > 0 && (
          <Box component="table" sx={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem',
            '& th': { textAlign: 'left', fontWeight: 500, color: 'text.secondary', fontSize: '0.74rem', py: 0.75, pr: 1.5, borderBottom: '1px solid', borderColor: 'divider' },
            '& td': { py: 0.75, pr: 1.5, borderBottom: '1px solid', borderColor: 'divider', verticalAlign: 'top' } }}>
            <thead><tr><th>Qué</th><th>Estado</th><th>N° de seguimiento</th><th>SII</th><th /></tr></thead>
            <tbody>
              {estado.envios.map((e) => (
                <tr key={e.id}>
                  <td>{e.proposito_nombre}<Typography component="span" sx={{ display: 'block', fontSize: '0.74rem', color: 'text.secondary' }}>{e.descripcion}</Typography></td>
                  <td>{e.estado_nombre}{e.error && <Typography component="span" sx={{ display: 'block', fontSize: '0.74rem', color: '#c8102e' }}>{e.error}</Typography>}</td>
                  <td>{e.trackid || '—'}</td>
                  <td>{e.estado_sii ? `${e.estado_sii}${e.glosa ? ` · ${e.glosa}` : ''}` : '—'}</td>
                  <td><Tooltip title="XML"><IconButton size="small" onClick={() => descargar(api.dte.xmlCertificacion(slug, e.id), `${e.proposito} ${e.id}.xml`)}><FileCode size={14} /></IconButton></Tooltip></td>
                </tr>
              ))}
            </tbody>
          </Box>
        )}
        {estado.aceptados?.length > 0 && (
          <Box>
            <Typography sx={{ fontSize: '0.84rem', fontWeight: 600, mb: 0.5 }}>Para declarar el avance en maullin</Typography>
            {estado.aceptados.map((a) => (
              <Typography key={a.trackid} sx={{ fontSize: '0.8rem', color: 'text.secondary' }}>
                {a.descripcion}: N° de envío {a.trackid}, del {a.fecha}
              </Typography>
            ))}
          </Box>
        )}
      </Tarjeta>

      <Tarjeta sx={{ p: 2.25, display: 'grid', gap: 1.25 }}>
        <Typography sx={{ fontWeight: 600 }}>Intercambio y muestras impresas</Typography>
        <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary', lineHeight: 1.5 }}>
          Intercambio: descargue de maullin el envío que le manda el SII y súbalo aquí; Afable devuelve los tres archivos
          de respuesta (acuse, resultado y recibo) para subirlos en maullin. Muestras: los PDF del set, para enviarlos al SII.
        </Typography>
        {esAdmin && (
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            <ElegirArchivo acepta=".xml" onElegir={intercambio} disabled={ocupado}>
              {trabajando === 'intercambio' ? 'Armando…' : 'Subir el envío del SII'}
            </ElegirArchivo>
            <Button size="small" variant="outlined" disabled={ocupado} onClick={async () => {
              setTrabajando('muestras');
              try { await descargar(api.dte.muestrasCertificacion(slug), 'Muestras impresas.zip'); } catch (e) { toast.error(await errorDeBlob(e, 'No se pudieron armar.')); }
              setTrabajando('');
            }}>Descargar las muestras (PDF)</Button>
          </Box>
        )}
      </Tarjeta>

      {esAdmin && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography sx={{ fontSize: '0.84rem', color: 'text.secondary' }}>Paso actual:</Typography>
          <Select size="small" value={estado.paso || 'set_pruebas'} sx={{ fontSize: '0.84rem' }}
            onChange={(e) => hacer('paso', () => api.dte.pasoCertificacion(slug, e.target.value))}>
            {estado.pasos.filter((p) => p.clave !== 'postulacion').map((p) => <MenuItem key={p.clave} value={p.clave}>{p.titulo}</MenuItem>)}
          </Select>
        </Box>
      )}
    </Box>
  );
}
