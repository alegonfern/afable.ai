import { useEffect, useState } from 'react';
import {
  Autocomplete, Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, TextField, Typography,
  createFilterOptions,
} from '@mui/material';
import { Download, Upload } from 'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../../services/api';
import { conPasos } from '../../components/ProgresoFlotante';
import { tonoEtapa } from '../../theme/tonos';

/*
 * Piezas compartidas de Compras y Ventas (22-10-2026): formatos de montos y cantidades, el
 * chip de la etapa del documento y el buscador de contactos (que deja crear uno nuevo).
 */

export const SORA = "'Sora', sans-serif";
export const NUM = { fontVariantNumeric: 'tabular-nums' };
const DECIMALES = { CLP: 0, USD: 2, UF: 4 };

export const clp = (n) => (n == null ? '—'
  : `${n < 0 ? '−' : ''}$${Math.abs(Math.round(Number(n) || 0)).toLocaleString('es-CL')}`);

export function dinero(n, moneda = 'CLP') {
  if (n == null) return '—';
  const d = DECIMALES[moneda] ?? 0;
  const texto = Math.abs(Number(n) || 0).toLocaleString('es-CL', { minimumFractionDigits: d, maximumFractionDigits: d });
  const signo = Number(n) < 0 ? '−' : '';
  return { CLP: `${signo}$${texto}`, USD: `${signo}US$ ${texto}`, UF: `${signo}UF ${texto}` }[moneda] || texto;
}

// "12.5" del servidor → "12,5" en pantalla; y al revés al escribir.
export const cant = (v) => (v == null ? '' : String(v).replace('.', ','));
export const aNumero = (v) => String(v ?? '').replace(/\./g, '').replace(',', '.');
export const fecha = (iso) => (iso ? iso.split('-').reverse().join('-') : '—');

export function Tarjeta({ children, sx }) {
  return <Box sx={{ border: '1px solid', borderColor: 'divider', borderRadius: '14px', bgcolor: 'background.paper', ...sx }}>{children}</Box>;
}

export function Etiqueta({ children }) {
  return <Typography sx={{ fontSize: '0.74rem', fontWeight: 600, letterSpacing: '0.07em', textTransform: 'uppercase', color: 'text.secondary' }}>{children}</Typography>;
}

// El tono de cada etapa (30-10-2026; antes todas en negro): apagado, como los de harvey.ai, para ver de
// un vistazo en qué punto del camino va cada documento (theme/tonos.js).
export function ChipEtapa({ etapa }) {
  const t = tonoEtapa(etapa);
  return <Chip size="small" label={etapa} sx={{ bgcolor: t.suave, color: t.color, fontWeight: 500, fontSize: '0.74rem', height: 22, fontFamily: 'inherit' }} />;
}

const filtro = createFilterOptions();

/* Elegir un cliente o proveedor; escribir un nombre nuevo ofrece crearlo ahí mismo. */
export function BuscadorContacto({ slug, rol, value, onChange, disabled, autoFocus }) {
  const [opciones, setOpciones] = useState([]);
  useEffect(() => {
    if (slug) api.comercial.contactos(slug, { rol }).then(({ data }) => setOpciones(data));
  }, [slug, rol]);
  const elegido = opciones.find((c) => c.id === value) || null;
  return (
    <Autocomplete size="small" options={opciones} value={elegido} disabled={disabled}
      getOptionLabel={(c) => (c.inputValue ? `Crear «${c.inputValue}»` : c.razon_social)}
      isOptionEqualToValue={(o, v) => o.id === v.id}
      filterOptions={(ops, params) => {
        const filtradas = filtro(ops, params);
        if (params.inputValue.trim() && !ops.some((o) => o.razon_social.toLowerCase() === params.inputValue.trim().toLowerCase())) {
          filtradas.push({ inputValue: params.inputValue.trim(), razon_social: params.inputValue.trim() });
        }
        return filtradas;
      }}
      renderOption={(props, c) => (
        <li {...props} key={c.id || `nuevo-${c.inputValue}`}>
          <Box>
            <Typography sx={{ fontSize: '0.86rem' }}>{c.inputValue ? `Crear «${c.inputValue}»` : c.razon_social}</Typography>
            {c.rut && <Typography sx={{ fontSize: '0.74rem', color: 'text.secondary' }}>{c.rut}</Typography>}
          </Box>
        </li>
      )}
      onChange={async (_, c) => {
        if (c?.inputValue) {
          try {
            const { data } = await api.comercial.crearContacto(slug, {
              razon_social: c.inputValue, es_cliente: rol === 'cliente', es_proveedor: rol === 'proveedor',
            });
            setOpciones((os) => [...os, data]);
            onChange(data.id, data);
          } catch (e) { toast.error(e.response?.data?.detail || 'No se pudo crear.'); }
        } else {
          onChange(c?.id || null, c);
        }
      }}
      renderInput={(params) => (
        <TextField {...params} autoFocus={autoFocus} placeholder={rol === 'proveedor' ? 'Proveedor' : 'Cliente'} />
      )}
      sx={{ minWidth: 280 }} />
  );
}

/* Bajar un archivo que llega como blob (Excel, PDF). Con un enlace y no con window.open: en el
   teléfono el navegador bloquea las ventanas que se abren después de esperar al servidor. */
export async function descargar(pedido, nombre) {
  try {
    const { data } = await pedido;
    const url = URL.createObjectURL(data);
    const a = document.createElement('a');
    a.href = url;
    a.download = nombre;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  } catch {
    toast.error('No se pudo descargar el archivo.');
  }
}

/* Importar productos o contactos desde Excel o CSV, con la plantilla para descargar. */
export function DialogoImportar({ slug, que, onCerrar, onHecho }) {
  const [archivo, setArchivo] = useState(null);
  const [subiendo, setSubiendo] = useState(false);
  const [resultado, setResultado] = useState(null);
  const nombre = que === 'productos' ? 'productos' : 'clientes y proveedores';
  const subir = async () => {
    setSubiendo(true);
    try {
      const { data } = await conPasos(['Leyendo la planilla', 'Revisando cada fila', 'Guardando lo nuevo'],
        () => api.comercial.importar(slug, que, archivo));
      setResultado(data);
      if (data.creados || data.actualizados) onHecho();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'No se pudo leer el archivo.');
    } finally { setSubiendo(false); }
  };
  return (
    <Dialog open onClose={onCerrar} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ fontWeight: 600 }}>Importar {nombre}</DialogTitle>
      <DialogContent>
        {resultado ? (
          <Box>
            <Typography sx={{ fontSize: '0.92rem' }}>
              <b>{resultado.creados}</b> nuevos y <b>{resultado.actualizados}</b> actualizados.
              {resultado.errores.length > 0 && ` ${resultado.errores.length} filas no se pudieron cargar:`}
            </Typography>
            {resultado.errores.slice(0, 20).map((e) => (
              <Typography key={e.fila} sx={{ fontSize: '0.82rem', color: 'text.secondary', mt: 0.5 }}>Fila {e.fila}: {e.motivo}</Typography>
            ))}
          </Box>
        ) : (
          <>
            <Typography sx={{ fontSize: '0.86rem', color: 'text.secondary', mb: 1.5, lineHeight: 1.6 }}>
              Suba un Excel (.xlsx) o CSV con las columnas de la plantilla. {que === 'productos'
                ? 'Si el código (o el nombre) ya existe, se actualiza.' : 'Si el RUT ya existe, se actualiza.'} Lo demás se crea.
            </Typography>
            <Button size="small" startIcon={<Download size={14} />} sx={{ mb: 2 }}
              onClick={() => descargar(api.comercial.plantilla(slug, que), `Plantilla ${nombre}.xlsx`)}>
              Descargar la plantilla
            </Button>
            <Box component="label" sx={{ display: 'block', border: '1.5px dashed', borderColor: 'divider', borderRadius: '12px', p: 3, textAlign: 'center', cursor: 'pointer', '&:hover': { borderColor: 'var(--af-color)' } }}>
              <input type="file" hidden accept=".xlsx,.csv" onChange={(e) => setArchivo(e.target.files?.[0] || null)} />
              <Upload size={18} style={{ opacity: 0.6 }} />
              <Typography sx={{ fontSize: '0.88rem', mt: 0.5 }}>{archivo ? archivo.name : 'Elegir archivo'}</Typography>
            </Box>
          </>
        )}
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onCerrar}>{resultado ? 'Cerrar' : 'Cancelar'}</Button>
        {!resultado && <Button variant="contained" disabled={!archivo || subiendo} onClick={subir}>Importar</Button>}
      </DialogActions>
    </Dialog>
  );
}

/* La configuración de Compras y Ventas, para saber si hay inventario y las monedas. */
export function useConfigComercial(slug, version = 0) {
  const [cfg, setCfg] = useState(null);
  useEffect(() => {
    if (slug) api.comercial.configuracion(slug).then(({ data }) => setCfg(data)).catch(() => setCfg(null));
  }, [slug, version]);
  return cfg;
}

export const TIPO_DE_MODULO = { ventas: 'venta', compras: 'compra' };
