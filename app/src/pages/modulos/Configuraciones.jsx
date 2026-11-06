import { useCallback, useEffect, useState } from 'react';
import { Box, Button, Chip, CircularProgress, InputBase, MenuItem, Select, Typography } from '@mui/material';
import { Plus } from 'lucide-react';
import { toast } from 'react-toastify';
import { useWorkspace } from '../../context/WorkspaceContext';
import { api } from '../../services/api';
import { MisCuentas } from './Conciliacion';
import { ConfigCompras, ConfigInventario, ConfigVentas } from '../comercial/ConfigComercial';
import { BotonGuardar, Tarjeta } from '../ajustes/piezas';

/*
 * La configuración de cada módulo (18-10-2026). Desde el 28-10-2026 vive en Configuración ›
 * Módulos, en tarjetas (antes en el panel de la derecha). Al cambiar algo se avisa con el
 * evento `afable-finanzas-config`, para que la pantalla abierta recargue lo que muestra.
 */

const pct = (v) => `${String(Number(v)).replace('.', ',')}%`;
export const avisarCambioDeConfiguracion = () => window.dispatchEvent(new Event('afable-finanzas-config'));

/* Sube cada vez que cambia la configuración: usado como `key`, rehace la vista con los datos nuevos. */
export function useVersionDeConfiguracion() {
  const [version, setVersion] = useState(0);
  useEffect(() => {
    const subir = () => setVersion((v) => v + 1);
    window.addEventListener('afable-finanzas-config', subir);
    return () => window.removeEventListener('afable-finanzas-config', subir);
  }, []);
  return version;
}

function Rotulo({ children }) {
  return <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary', mb: 0.5 }}>{children}</Typography>;
}

/* La cuenta contable de cada categoría (22-10-2026). Hoy no cambia ningún cálculo: deja
   asociado lo clasificado para cuando Afable lleve la contabilidad formal. */
function CuentasContables({ slug, esEditor }) {
  const [categorias, setCategorias] = useState(null);
  useEffect(() => {
    api.finanzas.categorias(slug).then(({ data }) => setCategorias(data));
  }, [slug]);
  if (!categorias) return <CircularProgress size={20} />;

  const cambiar = (id, campo, valor) =>
    setCategorias((cs) => cs.map((x) => (x.id === id ? { ...x, [campo]: valor } : x)));
  const guardar = async (cat, campo) => {
    try {
      await api.finanzas.actualizarCategoria(slug, cat.id, { [campo]: cat[campo] });
    } catch (e) { toast.error(e.response?.data?.detail || 'No se pudo guardar.'); }
  };
  const campo = (cat, nombre, placeholder, ancho) => (
    <InputBase value={cat[nombre]} placeholder={placeholder} disabled={!esEditor}
      onChange={(e) => cambiar(cat.id, nombre, e.target.value)}
      onBlur={() => guardar(cat, nombre)}
      sx={{ width: ancho, flex: ancho ? 'none' : 1, border: '1px solid', borderColor: 'divider', borderRadius: '7px', px: 1, py: 0.25, fontSize: '0.84rem' }} />
  );

  return ['ingreso', 'gasto'].map((tipo) => (
    <Box key={tipo} sx={{ mb: 1.5 }}>
      <Typography sx={{ fontSize: '0.74rem', color: 'text.secondary', textTransform: 'uppercase', letterSpacing: '0.04em', mb: 0.75 }}>
        {tipo === 'ingreso' ? 'Ingresos' : 'Gastos'}
      </Typography>
      <Box sx={{ display: 'grid', gap: 0.75 }}>
        {/* Una fila por categoría: su nombre, el código y el nombre de la cuenta. */}
        {categorias.filter((x) => x.tipo === tipo).map((cat) => (
          <Box key={cat.id} sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '200px 1fr' }, gap: { xs: 0.5, sm: 1.5 }, alignItems: 'center' }}>
            <Typography sx={{ fontSize: '0.84rem' }}>{cat.nombre}</Typography>
            <Box sx={{ display: 'flex', gap: 0.75 }}>
              {campo(cat, 'cuenta_codigo', 'Código', 90)}
              {campo(cat, 'cuenta_nombre', 'Nombre de la cuenta')}
            </Box>
          </Box>
        ))}
      </Box>
    </Box>
  ));
}

function ConfigContabilidad() {
  const { slug, esEditor } = useWorkspace();
  const [cfg, setCfg] = useState(null);
  const [regimen, setRegimen] = useState('');
  const [tasa, setTasa] = useState('');
  const [proyectos, setProyectos] = useState([]);
  const [nuevoProyecto, setNuevoProyecto] = useState('');
  const [guardando, setGuardando] = useState(false);

  const cargarProyectos = useCallback(() => {
    api.finanzas.proyectos(slug).then(({ data }) => setProyectos(data));
  }, [slug]);
  useEffect(() => {
    if (!slug) return;
    api.finanzas.configuracion(slug).then(({ data }) => {
      setCfg(data); setRegimen(data.regimen); setTasa(String(Number(data.tasa_ppm)).replace('.', ','));
    });
    cargarProyectos();
  }, [slug, cargarProyectos]);

  if (!slug) return <Typography sx={{ color: 'text.secondary' }}>Primero tiene que crear su empresa en Afable.</Typography>;
  if (!cfg) return <CircularProgress size={20} />;
  const sugerida = cfg.regimenes.find((r) => r.valor === regimen)?.ppm_sugerida;

  const tasaGuardada = String(Number(cfg.tasa_ppm)).replace('.', ',');
  const cambios = regimen !== cfg.regimen || tasa !== tasaGuardada;
  const guardar = async () => {
    setGuardando(true);
    try {
      const { data } = await api.finanzas.guardarConfiguracion(slug, { regimen, tasa_ppm: tasa });
      setCfg(data);
      setTasa(String(Number(data.tasa_ppm)).replace('.', ','));
      toast.success('Configuración guardada.');
      avisarCambioDeConfiguracion();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'No se pudo guardar.');
    } finally { setGuardando(false); }
  };
  const agregarProyecto = async () => {
    const nombre = nuevoProyecto.trim();
    if (!nombre) return;
    try {
      await api.finanzas.crearProyecto(slug, nombre);
      setNuevoProyecto('');
      cargarProyectos();
      avisarCambioDeConfiguracion();
    } catch (e) { toast.error(e.response?.data?.detail || 'No se pudo crear.'); }
  };

  return (
    <Box sx={{ display: 'grid', gap: 2.5 }}>
      <Tarjeta titulo="Impuestos" descripcion="Con esto Afable calcula el IVA y el PPM de cada mes, y arma el F29."
        pie={cfg.tasa_ppm_confirmada ? 'Tasa de PPM confirmada.' : <b>Hoy se usa la tasa sugerida, sin confirmar.</b>}
        accion={esEditor && <BotonGuardar guardando={guardando} cambios={cambios} onClick={guardar} />}>
        <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' } }}>
          <Box>
            <Rotulo>Régimen tributario</Rotulo>
            <Select fullWidth size="small" value={regimen} disabled={!esEditor} sx={{ fontSize: '0.875rem', borderRadius: '8px' }}
              onChange={(e) => {
                setRegimen(e.target.value);
                const s = cfg.regimenes.find((r) => r.valor === e.target.value)?.ppm_sugerida;
                if (s) setTasa(String(Number(s)).replace('.', ','));
              }}>
              {cfg.regimenes.map((r) => <MenuItem key={r.valor} value={r.valor}>{r.nombre}</MenuItem>)}
            </Select>
          </Box>
          <Box>
            <Rotulo>Tasa de PPM (%)</Rotulo>
            <InputBase value={tasa} disabled={!esEditor} onChange={(e) => setTasa(e.target.value)}
              sx={{ width: '100%', border: '1px solid', borderColor: 'divider', borderRadius: '8px', px: 1.25, py: 0.6, fontSize: '0.875rem' }} />
          </Box>
        </Box>
        <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary', mt: 1.25, lineHeight: 1.5 }}>
          Sugerida para este régimen: {pct(sugerida)}. La tasa real de su empresa está en su último F29: confírmela ahí.
        </Typography>
        <Box sx={{ display: 'flex', gap: 4, mt: 2, pt: 2, borderTop: '1px solid', borderColor: 'divider', flexWrap: 'wrap' }}>
          <Box>
            <Rotulo>IVA</Rotulo>
            <Typography sx={{ fontWeight: 600, fontSize: '0.9rem' }}>{pct(cfg.iva)}</Typography>
          </Box>
          <Box>
            <Rotulo>Retención de honorarios (por ley, según el año)</Rotulo>
            <Typography sx={{ fontSize: '0.86rem' }}>
              {Object.entries(cfg.retencion_honorarios).map(([a, t]) => `${a}: ${pct(t)}`).join(' · ')}
            </Typography>
          </Box>
        </Box>
      </Tarjeta>

      <Tarjeta titulo="Proyectos" descripcion="Obras, locales, clientes o líneas de producto: para ver ingresos y gastos por cada uno.">
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75, mb: esEditor ? 1.5 : 0 }}>
          {proyectos.length === 0 && <Typography sx={{ fontSize: '0.84rem', color: 'text.disabled' }}>Ninguno todavía.</Typography>}
          {proyectos.map((p) => <Chip key={p.id} label={p.nombre} size="small" />)}
        </Box>
        {esEditor && (
          <Box sx={{ display: 'flex', gap: 1, maxWidth: 480 }}>
            <InputBase placeholder="Nombre del proyecto" value={nuevoProyecto}
              onChange={(e) => setNuevoProyecto(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && agregarProyecto()}
              sx={{ flex: 1, border: '1px solid', borderColor: 'divider', borderRadius: '8px', px: 1.25, py: 0.4, fontSize: '0.875rem' }} />
            <Button size="small" variant="outlined" startIcon={<Plus size={14} />} onClick={agregarProyecto}
              sx={{ borderRadius: '8px', textTransform: 'none', fontWeight: 600 }}>Agregar</Button>
          </Box>
        )}
      </Tarjeta>

      <Tarjeta titulo="Cuentas contables"
        descripcion="Opcional. La cuenta de su plan de cuentas que corresponde a cada categoría. Hoy no cambia ningún cálculo: queda lista para llevar la contabilidad formal."
        pie="Cada cuenta se guarda al salir del campo.">
        <CuentasContables slug={slug} esEditor={esEditor} />
      </Tarjeta>
    </Box>
  );
}

function ConfigFinanzas() {
  const { slug, esEditor } = useWorkspace();
  if (!slug) return <Typography sx={{ color: 'text.secondary' }}>Primero tiene que crear su empresa en Afable.</Typography>;
  return (
    <Tarjeta titulo="Cuentas bancarias" descripcion="Con sus cartolas, Afable calcula la caja y cuadra el banco con lo del SII.">
      <MisCuentas slug={slug} esEditor={esEditor} onCambio={avisarCambioDeConfiguracion} />
    </Tarjeta>
  );
}

// Qué módulo tiene configuración (Ventas y Compras desde el 22-10-2026).
export const CONFIGURACION_DE_MODULO = {
  ventas: ConfigVentas,
  compras: ConfigCompras,
  inventario: ConfigInventario,
  contabilidad: ConfigContabilidad,
  finanzas: ConfigFinanzas,
};
