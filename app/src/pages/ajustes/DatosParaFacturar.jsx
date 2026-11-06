import { useCallback, useEffect, useMemo, useState } from 'react';
import { Box, TextField } from '@mui/material';
import { toast } from 'react-toastify';
import { useWorkspace } from '../../context/WorkspaceContext';
import { api } from '../../services/api';
import { useDteDisponible } from '../dte/useDte';
import { BotonGuardar, Cargando, Estado, Tarjeta, campoSx } from './piezas';

/*
 * Los datos con que la empresa factura (26-10-2026): el ÚNICO lugar donde se editan. Están en
 * Configuración › General; Ventas y el facturador electrónico los muestran y llevan acá.
 *
 * Razón social, giro y dirección viven en la configuración comercial (son los del emisor de toda
 * factura, también la del facturador simulado); la actividad económica, el teléfono, el correo,
 * la sucursal y la oficina del SII, en la del facturador electrónico. Desde el 28-10-2026 se
 * guardan juntos con el botón de la tarjeta, como el resto de Configuración.
 */

export const enlaceDatosParaFacturar = '/app/ajustes/general#facturar';

const EMISOR = ['razon_social', 'giro', 'direccion', 'comuna', 'ciudad'];
const DTE = ['actecos', 'telefono', 'correo_emisor', 'codigo_sucursal', 'oficina_sii'];

export default function DatosParaFacturar() {
  const { slug, esAdmin } = useWorkspace();
  const dte = useDteDisponible(slug);
  const [original, setOriginal] = useState(null);
  const [form, setForm] = useState(null);
  const [faltan, setFaltan] = useState([]);
  const [conDte, setConDte] = useState(false);
  const [guardando, setGuardando] = useState(false);

  const cargar = useCallback(async () => {
    if (!slug) return;
    const [{ data: com }, dteCfg] = await Promise.all([
      api.comercial.configuracion(slug),
      api.dte.estado(slug).then(({ data }) => data.configuracion || null).catch(() => null),
    ]);
    const valores = Object.fromEntries(EMISOR.map((k) => [k, com.emisor?.[k] || '']));
    if (dteCfg) {
      DTE.forEach((k) => { valores[k] = k === 'actecos' ? (dteCfg.actecos || []).join(', ') : (dteCfg[k] || ''); });
    }
    setConDte(Boolean(dteCfg));
    setOriginal(valores); setForm(valores); setFaltan(com.emisor_faltan || []);
  }, [slug]);
  useEffect(() => { cargar(); }, [cargar]);

  const cambiados = useMemo(() => (form && original ? Object.keys(form).filter((k) => form[k] !== original[k]) : []), [form, original]);

  if (!form) return <Tarjeta titulo="Datos para facturar"><Cargando /></Tarjeta>;

  const guardar = async () => {
    setGuardando(true);
    try {
      const emisor = Object.fromEntries(cambiados.filter((k) => EMISOR.includes(k)).map((k) => [k, form[k].trim()]));
      const delDte = Object.fromEntries(cambiados.filter((k) => DTE.includes(k)).map((k) => [k,
        k === 'actecos' ? form[k].split(/[,\s]+/).filter(Boolean) : form[k].trim()]));
      if (Object.keys(emisor).length) {
        const { data } = await api.comercial.guardarConfiguracion(slug, { emisor });
        setFaltan(data.emisor_faltan || []);
      }
      if (Object.keys(delDte).length) await api.dte.guardarConfiguracion(slug, delDte);
      setOriginal(form);
      toast.success('Datos para facturar guardados.');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'No se pudieron guardar.');
    } finally { setGuardando(false); }
  };

  const campo = (k, rotulo, ayuda, ancho) => (
    <TextField key={k} label={rotulo} value={form[k]} disabled={!esAdmin} placeholder={ayuda} size="small"
      sx={{ ...campoSx, ...(ancho ? { gridColumn: '1 / -1' } : {}) }}
      onChange={(e) => setForm({ ...form, [k]: e.target.value })} inputProps={{ 'aria-label': rotulo }} />
  );

  return (
    <Box id="facturar" sx={{ scrollMarginTop: 24 }}>
      <Tarjeta
        titulo="Datos para facturar"
        descripcion="Salen como emisor en cada factura, cotización y orden de venta. Deben coincidir con lo inscrito en el SII; el RUT es el de la empresa."
        pie={esAdmin ? (faltan.length ? <Estado ok={false}>Para facturar falta: {faltan.join(', ')}.</Estado> : <Estado ok>Completos para facturar.</Estado>)
          : 'Solo un administrador puede editar estos datos.'}
        accion={esAdmin && <BotonGuardar guardando={guardando} cambios={cambiados.length > 0} onClick={guardar} />}
      >
        <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' } }}>
          {campo('razon_social', 'Razón social', 'Como está inscrita en el SII')}
          {campo('giro', 'Giro', 'La actividad que sale en la factura')}
          {campo('direccion', 'Dirección', 'Calle, número, oficina', true)}
          {campo('comuna', 'Comuna')}
          {campo('ciudad', 'Ciudad')}
          {dte && conDte && (
            <>
              {campo('actecos', 'Actividad económica (códigos del SII)', '620200, separados por coma', true)}
              {campo('telefono', 'Teléfono (opcional)')}
              {campo('correo_emisor', 'Correo en la factura (opcional)')}
              {campo('codigo_sucursal', 'Código de sucursal del SII (opcional)')}
              {campo('oficina_sii', 'Oficina del SII (opcional)', 'Ej: SANTIAGO ORIENTE; vacío = la comuna')}
            </>
          )}
        </Box>
      </Tarjeta>
    </Box>
  );
}
