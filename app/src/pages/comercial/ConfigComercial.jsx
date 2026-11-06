import { useEffect, useState } from 'react';
import {
  Box, Button, Chip, CircularProgress, InputBase, MenuItem, Radio, RadioGroup, FormControlLabel, Select, Typography,
} from '@mui/material';
import { Plus, Star } from 'lucide-react';
import { toast } from 'react-toastify';
import { useWorkspace } from '../../context/WorkspaceContext';
import { api } from '../../services/api';
import { avisarCambioDeConfiguracion } from '../modulos/Configuraciones';
import { useNavigate } from 'react-router-dom';
import { useDteDisponible } from '../dte/useDte';
import { Estado, Tarjeta } from '../ajustes/piezas';

/*
 * La configuración de Ventas, Compras e Inventario (22-10-2026). Desde el 28-10-2026 vive en
 * Configuración › Módulos (antes, en el panel de la derecha): cada sección es una tarjeta.
 */

const campoSx = { border: '1px solid', borderColor: 'divider', borderRadius: '8px', px: 1.25, py: 0.4, fontSize: '0.86rem' };

function Rotulo({ children }) {
  return <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary', mb: 0.5 }}>{children}</Typography>;
}
// Cada campo se guarda al salir de él (o al elegir), así que las tarjetas no llevan botón.
function Seccion({ titulo, ayuda, pie, children }) {
  return (
    <Tarjeta titulo={titulo} descripcion={ayuda} pie={pie}>
      <Box sx={{ display: 'grid', gap: 2 }}>{children}</Box>
    </Tarjeta>
  );
}

export function Bodegas({ slug, esEditor }) {
  const [lista, setLista] = useState(null);
  const [nueva, setNueva] = useState('');
  useEffect(() => { api.comercial.bodegas(slug).then(({ data }) => setLista(data)).catch(() => setLista([])); }, [slug]);
  const crear = async () => {
    if (!nueva.trim()) return;
    try {
      const { data } = await api.comercial.crearBodega(slug, { nombre: nueva.trim() });
      setLista((l) => [...l, data]);
      setNueva('');
      avisarCambioDeConfiguracion();
    } catch (e) { toast.error(e.response?.data?.detail || 'No se pudo crear.'); }
  };
  const principal = async (b) => {
    try {
      const { data } = await api.comercial.actualizarBodega(slug, b.id, { principal: true });
      setLista((l) => l.map((x) => (x.id === data.id ? data : { ...x, principal: false })));
      avisarCambioDeConfiguracion();
    } catch (e) { toast.error(e.response?.data?.detail || 'No se pudo.'); }
  };
  if (!lista) return <CircularProgress size={18} />;
  return (
    <>
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75 }}>
        {lista.map((b) => (
          <Chip key={b.id} size="small" label={b.nombre} icon={b.principal ? <Star size={12} /> : undefined}
            onClick={esEditor && !b.principal ? () => principal(b) : undefined}
            title={b.principal ? 'Bodega principal: la que se usa si no se elige otra' : 'Clic para dejarla como principal'} />
        ))}
      </Box>
      {esEditor && (
        <Box sx={{ display: 'flex', gap: 1 }}>
          <InputBase placeholder="Nombre de la bodega" value={nueva} onChange={(e) => setNueva(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && crear()} sx={{ ...campoSx, flex: 1 }} />
          <Button size="small" variant="outlined" startIcon={<Plus size={14} />} onClick={crear}>Agregar</Button>
        </Box>
      )}
    </>
  );
}

function ConfigComercial({ modulo }) {
  const { slug, esEditor } = useWorkspace();
  const [cfg, setCfg] = useState(null);
  const dte = useDteDisponible(slug);
  const navigate = useNavigate();
  useEffect(() => { if (slug) api.comercial.configuracion(slug).then(({ data }) => setCfg(data)); }, [slug]);
  if (!slug) return <Typography sx={{ color: 'text.secondary' }}>Primero tiene que crear su empresa en Afable.</Typography>;
  if (!cfg) return <CircularProgress size={20} />;

  const guardar = async (cambios) => {
    try {
      const { data } = await api.comercial.guardarConfiguracion(slug, cambios);
      setCfg(data);
      avisarCambioDeConfiguracion();
      toast.success('Guardado.', { autoClose: 1500 });
    } catch (e) { toast.error(e.response?.data?.detail || 'No se pudo guardar.'); }
  };
  const numero = (k, sufijo) => (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
      <InputBase defaultValue={String(cfg[k]).replace('.', ',')} disabled={!esEditor} key={`${k}-${cfg[k]}`}
        onBlur={(e) => { const v = e.target.value.replace(',', '.'); if (v && v !== String(cfg[k])) guardar({ [k]: v }); }}
        sx={{ ...campoSx, width: 80 }} />
      <Typography sx={{ fontSize: '0.84rem', color: 'text.secondary' }}>{sufijo}</Typography>
    </Box>
  );
  const venta = modulo === 'ventas';

  return (
    <Box sx={{ display: 'grid', gap: 2.5 }}>
      {venta ? (
        <Seccion titulo="Cotizaciones" ayuda="Lo que se propone al crear una cotización nueva.">
          <Box><Rotulo>Validez</Rotulo>{numero('validez_cotizacion_dias', 'días')}</Box>
          <Box><Rotulo>Avisar si no hay respuesta después de</Rotulo>{numero('dias_sin_respuesta', 'días (automatización «Cotizaciones sin respuesta»)')}</Box>
          <Box>
            <Rotulo>Condiciones de venta (salen en el PDF)</Rotulo>
            <InputBase multiline minRows={3} defaultValue={cfg.condiciones_venta} disabled={!esEditor} key={cfg.condiciones_venta}
              placeholder="Forma de pago, despacho, garantía…"
              onBlur={(e) => { if (e.target.value !== cfg.condiciones_venta) guardar({ condiciones_venta: e.target.value }); }}
              sx={{ ...campoSx, width: '100%', py: 1 }} />
          </Box>
        </Seccion>
      ) : null}

      <Seccion titulo="Qué se espera ver facturado"
        ayuda="Decide qué aparece en «Por facturar». Las facturas llegan del SII al cargar el Registro de Compras y Ventas.">
        <RadioGroup value={venta ? cfg.facturar_ventas : cfg.facturar_compras}
          onChange={(e) => guardar({ [venta ? 'facturar_ventas' : 'facturar_compras']: e.target.value })}>
          <FormControlLabel value="pedido" disabled={!esEditor} control={<Radio size="small" />}
            label={<Typography sx={{ fontSize: '0.86rem' }}>{venta ? 'Lo vendido, apenas se confirma la orden' : 'Lo pedido, apenas se confirma la OC'}</Typography>} />
          <FormControlLabel value="entregado" disabled={!esEditor} control={<Radio size="small" />}
            label={<Typography sx={{ fontSize: '0.86rem' }}>{venta ? 'Solo lo entregado' : 'Solo lo recibido'}</Typography>} />
        </RadioGroup>
        <Box><Rotulo>Diferencia aceptada entre la orden y la factura</Rotulo>{numero('tolerancia_pct', '%')}</Box>
      </Seccion>


      {venta && (
        <Seccion titulo="Facturación"
          ayuda={cfg.emision_disponible
            ? 'Conectada: las órdenes de venta se facturan desde Afable, en la orden o pidiéndolo en el chat.'
            : 'Todavía no conectada. Emita sus facturas como siempre: al cargar el Registro de Ventas, cada una se vincula sola a su orden.'}
          pie={cfg.emisor_faltan?.length
            ? <Estado ok={false}>Para facturar falta: {cfg.emisor_faltan.join(', ')}.</Estado>
            : <Estado ok>Lista para facturar.</Estado>}>
          {/* Los datos del emisor se editan en un solo lugar: Configuración › General. */}
          <Box sx={{ fontSize: '0.86rem', lineHeight: 1.6, p: 1.5, borderRadius: '8px', bgcolor: 'action.hover' }}>
            <b>{cfg.emisor?.razon_social || '—'}</b> · RUT {cfg.emisor?.rut || '—'}<br />
            <Box component="span" sx={{ color: 'text.secondary' }}>
              {[cfg.emisor?.giro, cfg.emisor?.direccion, [cfg.emisor?.comuna, cfg.emisor?.ciudad].filter(Boolean).join(', ')].filter(Boolean).join(' · ') || 'Sin giro ni dirección'}
            </Box>
          </Box>
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            <Button size="small" variant="outlined" sx={{ borderRadius: '8px', textTransform: 'none', fontWeight: 600 }}
              onClick={() => navigate('/app/ajustes/general#facturar')}>Editar los datos para facturar</Button>
            {dte && (
              <Button size="small" sx={{ borderRadius: '8px', textTransform: 'none', fontWeight: 600 }}
                onClick={() => navigate('/app/ajustes/facturacion-electronica')}>Facturador electrónico</Button>
            )}
          </Box>
        </Seccion>
      )}
    </Box>
  );
}

export const ConfigVentas = () => <ConfigComercial modulo="ventas" />;

/* La configuración del módulo Inventario: el nivel (sin inventario, básico o completo) y las
   bodegas. Antes estaba repetida en Ventas y en Compras. */
export function ConfigInventario() {
  const { slug, esEditor } = useWorkspace();
  const [cfg, setCfg] = useState(null);
  useEffect(() => { if (slug) api.comercial.configuracion(slug).then(({ data }) => setCfg(data)); }, [slug]);
  if (!slug) return <Typography sx={{ color: 'text.secondary' }}>Primero tiene que crear su empresa en Afable.</Typography>;
  if (!cfg) return <CircularProgress size={20} />;
  const guardar = async (cambios) => {
    try {
      const { data } = await api.comercial.guardarConfiguracion(slug, cambios);
      setCfg(data);
      avisarCambioDeConfiguracion();
      toast.success('Guardado.', { autoClose: 1500 });
    } catch (e) { toast.error(e.response?.data?.detail || 'No se pudo guardar.'); }
  };
  return (
    <Box sx={{ display: 'grid', gap: 2.5 }}>
      <Seccion titulo="Nivel de inventario" ayuda="Lo usan Compras (recepciones) y Ventas (entregas). Puede cambiarlo cuando quiera: el historial se conserva.">
        <Select size="small" value={cfg.nivel_inventario} disabled={!esEditor} onChange={(e) => guardar({ nivel_inventario: e.target.value })} sx={{ fontSize: '0.86rem' }}>
          {cfg.niveles.map((n) => <MenuItem key={n.valor} value={n.valor}>{n.nombre}</MenuItem>)}
        </Select>
        <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary', lineHeight: 1.5 }}>
          {{ ninguno: 'Se registra lo entregado y lo recibido, sin llevar stock.',
            basico: 'Cada recepción suma y cada entrega resta stock de cada producto almacenable.',
            completo: 'Stock por bodega: cada orden y cada entrega dice de qué bodega sale o a cuál llega, y hay traspasos entre bodegas.' }[cfg.nivel_inventario]}
        </Typography>
        {cfg.nivel_inventario === 'completo' && <Box><Rotulo>Bodegas</Rotulo><Bodegas slug={slug} esEditor={esEditor} /></Box>}
      </Seccion>
    </Box>
  );
}
export const ConfigCompras = () => <ConfigComercial modulo="compras" />;
