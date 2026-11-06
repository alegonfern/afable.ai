import { useCallback, useEffect, useState } from 'react';
import {
  Box, Button, CircularProgress, FormControlLabel, IconButton, InputBase, Radio, RadioGroup, Switch, Tooltip, Typography,
} from '@mui/material';
import { Copy, RefreshCw } from 'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../../services/api';
import { Tarjeta } from '../comercial/comun';

/*
 * La casilla de intercambio (26-10-2026): el correo que la empresa declara en el SII para recibir
 * las facturas de sus proveedores (XML) y mandar las suyas. Dos formas:
 *
 * - La casilla de Afable (recomendada): una dirección propia de la empresa en Afable
 *   (dte-<rut>-<dv>@…). Lo que llega se procesa al instante, sin claves que guardar.
 * - Su propia casilla: Afable la revisa por IMAP cada 15 minutos.
 *
 * En los dos casos lo recibido queda en Compras › Documentos recibidos.
 */

const campoSx = { border: '1px solid', borderColor: 'divider', borderRadius: '8px', px: 1.25, py: 0.4, fontSize: '0.86rem' };
const msg = (e, d) => e?.response?.data?.detail || d;

function Rotulo({ children }) {
  return <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary', mb: 0.5 }}>{children}</Typography>;
}

function Opcion({ titulo, ayuda }) {
  return (
    <Box>
      <Typography sx={{ fontSize: '0.88rem' }}>{titulo}</Typography>
      <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary' }}>{ayuda}</Typography>
    </Box>
  );
}

export default function Casilla({ slug, esAdmin, recargar }) {
  const [c, setC] = useState(null);
  const [datos, setDatos] = useState(null);
  const [trabajando, setTrabajando] = useState(false);

  const cargar = useCallback(() => api.dte.casilla(slug).then(({ data }) => {
    setC(data);
    setDatos({ correo_intercambio: data.casilla_afable ? '' : (data.correo_intercambio || ''), imap_servidor: data.imap_servidor || '',
      imap_puerto: String(data.imap_puerto || 993), imap_usuario: data.imap_usuario || '', clave: '' });
  }).catch((e) => toast.error(msg(e, 'No se pudo leer la casilla.'))), [slug]);
  useEffect(() => { cargar(); }, [cargar]);

  if (!c || !datos) return <CircularProgress size={20} />;
  const cambiar = (k) => (e) => setDatos((d) => ({ ...d, [k]: e.target.value }));

  const guardar = async (cuerpo, aviso = 'Casilla guardada.') => {
    setTrabajando(true);
    try {
      const { data } = await api.dte.guardarCasilla(slug, cuerpo);
      setC(data);
      setDatos((d) => ({ ...d, clave: '' }));
      if (aviso) toast.success(aviso);
      recargar?.();
    } catch (e) { toast.error(msg(e, 'No se pudo guardar.')); }
    setTrabajando(false);
  };
  const guardarPropia = () => {
    const cuerpo = { ...datos };
    if (!cuerpo.clave) delete cuerpo.clave; // vacía = se conserva la guardada
    guardar(cuerpo);
  };
  const probar = async () => {
    setTrabajando(true);
    try {
      await api.dte.probarCasilla(slug);
      toast.success('Afable entró a la casilla.');
      cargar();
    } catch (e) { toast.error(msg(e, 'No se pudo entrar a la casilla.')); }
    setTrabajando(false);
  };
  const copiar = async () => {
    try { await navigator.clipboard.writeText(c.direccion_afable); toast.success('Dirección copiada.'); }
    catch { toast.error('No se pudo copiar: selecciónela y cópiela a mano.'); }
  };

  const modo = c.casilla_afable ? 'afable' : 'propia';
  return (
    <Box sx={{ display: 'grid', gap: 2, maxWidth: 760 }}>
      <Tarjeta sx={{ p: 2.25, display: 'grid', gap: 1.5 }}>
        <Typography sx={{ fontWeight: 600 }}>Correo de intercambio</Typography>
        <Typography sx={{ fontSize: '0.82rem', color: 'text.secondary', lineHeight: 1.5 }}>
          Es el correo que su empresa registra en el SII para el intercambio de documentos electrónicos. Ahí le llegan
          las facturas de sus proveedores en XML: Afable valida cada una, acusa recibo y la deja en Compras.
        </Typography>
        <RadioGroup value={modo} onChange={(e) => guardar({ casilla_afable: e.target.value === 'afable' },
          e.target.value === 'afable' ? 'Listo: su casilla de Afable está activa.' : 'Listo: use su propia casilla.')}>
          <FormControlLabel value="afable" disabled={!esAdmin || !c.casilla_afable_disponible || trabajando} control={<Radio size="small" />}
            label={<Opcion titulo={c.casilla_afable_disponible ? 'Casilla de Afable (recomendado)' : 'Casilla de Afable · disponible pronto'}
              ayuda="Una dirección de su empresa en Afable. Lo que llega se procesa al instante, sin claves ni configuración de correo." />} />
          <FormControlLabel value="propia" disabled={!esAdmin || trabajando} control={<Radio size="small" />}
            label={<Opcion titulo="Mi propia casilla (IMAP)" ayuda="Afable revisa su correo cada 15 minutos con una clave de aplicación." />} />
        </RadioGroup>
      </Tarjeta>

      {modo === 'afable' ? (
        <Tarjeta sx={{ p: 2.25, display: 'grid', gap: 1.25 }}>
          <Rotulo>Su casilla de intercambio en Afable</Rotulo>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography sx={{ fontFamily: 'monospace', fontSize: '0.95rem', ...campoSx, py: 0.75, flex: 1, wordBreak: 'break-all' }}>
              {c.direccion_afable}
            </Typography>
            <Tooltip title="Copiar"><IconButton onClick={copiar} size="small"><Copy size={16} /></IconButton></Tooltip>
          </Box>
          <Typography sx={{ fontSize: '0.82rem', fontWeight: 500, mt: 0.5 }}>Regístrela en el SII:</Typography>
          <Box component="ol" sx={{ m: 0, pl: 2.5, fontSize: '0.82rem', lineHeight: 1.7, color: 'text.secondary' }}>
            <li>Entre a sii.cl con la clave de la empresa.</li>
            <li>Servicios online › Factura electrónica › Sistema de facturación de mercado › «Actualización de datos de la empresa».</li>
            <li>En «Mail de contacto para el intercambio de información», pegue la dirección de arriba y guarde.</li>
          </Box>
          <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary' }}>
            Desde ese momento los proveedores le mandan sus XML a esa dirección y aparecen solos en Compras › Documentos recibidos.
          </Typography>
        </Tarjeta>
      ) : (
        <Tarjeta sx={{ p: 2.25, display: 'grid', gap: 1.5 }}>
          <Box>
            <Rotulo>Correo de intercambio (el registrado en el SII)</Rotulo>
            <InputBase value={datos.correo_intercambio} onChange={cambiar('correo_intercambio')} disabled={!esAdmin}
              placeholder="dte@suempresa.cl" sx={{ ...campoSx, width: '100%' }} />
          </Box>
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '2fr 1fr' }, gap: 1.5 }}>
            <Box><Rotulo>Servidor IMAP</Rotulo>
              <InputBase value={datos.imap_servidor} onChange={cambiar('imap_servidor')} disabled={!esAdmin} placeholder="imap.gmail.com" sx={{ ...campoSx, width: '100%' }} /></Box>
            <Box><Rotulo>Puerto</Rotulo>
              <InputBase value={datos.imap_puerto} onChange={cambiar('imap_puerto')} disabled={!esAdmin} sx={{ ...campoSx, width: '100%' }} /></Box>
            <Box><Rotulo>Usuario</Rotulo>
              <InputBase value={datos.imap_usuario} onChange={cambiar('imap_usuario')} disabled={!esAdmin} sx={{ ...campoSx, width: '100%' }} /></Box>
            <Box><Rotulo>{c.tiene_clave ? 'Clave (guardada; escriba otra para cambiarla)' : 'Clave'}</Rotulo>
              <InputBase type="password" value={datos.clave} onChange={cambiar('clave')} disabled={!esAdmin} sx={{ ...campoSx, width: '100%' }} /></Box>
          </Box>
          <Typography sx={{ fontSize: '0.76rem', color: 'text.secondary' }}>
            En Gmail o Microsoft 365 use una «contraseña de aplicación», no la clave normal. Se guarda cifrada.
          </Typography>
          {c.imap_revisado_en && (
            <Typography sx={{ fontSize: '0.8rem', color: c.imap_error ? '#c8102e' : 'text.secondary' }}>
              Última revisión: {new Date(c.imap_revisado_en).toLocaleString('es-CL')}{c.imap_error ? ` · ${c.imap_error}` : ' · sin problemas'}
            </Typography>
          )}
          {esAdmin && (
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
              <Button variant="contained" size="small" onClick={guardarPropia} disabled={trabajando}>Guardar</Button>
              <Button variant="outlined" size="small" startIcon={<RefreshCw size={14} />} onClick={probar}
                disabled={trabajando || !c.imap_servidor}>Probar la casilla</Button>
            </Box>
          )}
        </Tarjeta>
      )}

      <Tarjeta sx={{ p: 2.25 }}>
        <FormControlLabel disabled={!esAdmin || trabajando} control={
          <Switch checked={!!c.enviar_a_clientes} onChange={(e) => guardar({ enviar_a_clientes: e.target.checked })} />}
          label={<Opcion titulo="Mandarle a cada cliente el XML y el PDF de lo que se le emite"
            ayuda="Cuando el SII acepta el documento, a su correo de la ficha. Solo en producción." />} />
      </Tarjeta>
    </Box>
  );
}
