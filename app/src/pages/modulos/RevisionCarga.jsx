import { useMemo, useState } from 'react';
import {
  Box, Button, Checkbox, Chip, CircularProgress, Dialog, FormControlLabel, InputBase, MenuItem,
  Select, Typography, useTheme,
} from '@mui/material';
import { ChevronDown, ChevronRight, FileText, Search, Sparkles } from 'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../../services/api';
import { conPasos } from '../../components/ProgresoFlotante';
import { TONOS } from '../../theme/tonos';

/*
 * Revisar antes de importar (PMV financiero, etapa 1, 17-10-2026). La carga del SII queda en
 * borrador: acá se ve qué entra, cuánto suma, qué ya estaba, y se decide la categoría, el
 * proyecto y si cada documento ya está pagado. Recién al confirmar entran los documentos.
 * Agrupado por proveedor (o cliente): una decisión en el grupo vale para todas sus facturas.
 */

const clp = (n) => `$${Math.round(Number(n) || 0).toLocaleString('es-CL')}`;
const diaMes = (iso) => {
  const d = new Date(`${iso}T12:00:00`);
  return d.toLocaleDateString('es-CL', { weekday: 'short', day: 'numeric', month: 'short' });
};
const NOMBRES = {
  compras: { contraparte: 'proveedor', plural: 'proveedores', pagada: 'Pagada', porPagar: 'Por pagar' },
  honorarios: { contraparte: 'emisor', plural: 'emisores', pagada: 'Pagada', porPagar: 'Por pagar' },
  ventas: { contraparte: 'cliente', plural: 'clientes', pagada: 'Cobrada', porPagar: 'Por cobrar' },
};
const LIBRO = { compras: 'Compras', ventas: 'Ventas', honorarios: 'Honorarios' };

function Celda({ children, sx }) {
  return <Box sx={{ px: 1.25, py: 0.75, display: 'flex', alignItems: 'center', minWidth: 0, ...sx }}>{children}</Box>;
}

function Selector({ value, opciones, vacio, onChange, ancho = 190, mixto }) {
  const theme = useTheme();
  return (
    <Select size="small" displayEmpty value={value ?? ''} onChange={(e) => onChange(e.target.value === '' ? null : e.target.value)}
      sx={{ width: ancho, fontSize: '0.82rem', bgcolor: 'background.paper', '& .MuiSelect-select': { py: 0.5 } }}
      renderValue={(v) => {
        if (mixto) return <span style={{ color: theme.palette.text.secondary }}>Varias</span>;
        const o = opciones.find((x) => x.id === v);
        return o ? o.nombre : <span style={{ color: theme.palette.text.disabled }}>{vacio}</span>;
      }}>
      <MenuItem value=""><em>{vacio}</em></MenuItem>
      {opciones.map((o) => <MenuItem key={o.id} value={o.id}>{o.nombre}</MenuItem>)}
    </Select>
  );
}

export default function RevisionCarga({ carga: inicial, slug, categorias, proyectos, onCerrar, onImportada }) {
  const theme = useTheme();
  const [carga, setCarga] = useState(inicial);
  // Lo decidido por fila: arranca con lo que propuso Afable.
  const [filas, setFilas] = useState(() => inicial.filas_previas.map((f) => ({ ...f })));
  const [agrupar, setAgrupar] = useState(true);
  const [buscar, setBuscar] = useState('');
  const [cerrados, setCerrados] = useState({});
  const [sugiriendo, setSugiriendo] = useState(false);
  const [importando, setImportando] = useState(false);
  const [verYaEstaban, setVerYaEstaban] = useState(false);

  const n = NOMBRES[carga.libro] || NOMBRES.compras;
  const cats = categorias.filter((c) => (carga.libro === 'ventas') === (c.tipo === 'ingreso'));
  const opcionesPago = [{ id: 'si', nombre: n.pagada }, { id: 'no', nombre: n.porPagar }];

  const cambiar = (ns, cambios) => setFilas((fs) => fs.map((f) => (ns.includes(f.n) ? { ...f, ...cambios,
    // Si la persona cambia la categoría, deja de ser la sugerida.
    ...('categoria' in cambios ? { origen: '' } : {}) } : f)));

  const visibles = useMemo(() => {
    const q = buscar.trim().toLowerCase();
    return filas.filter((f) => !q || `${f.razon_social} ${f.rut} ${f.folio}`.toLowerCase().includes(q));
  }, [filas, buscar]);

  const grupos = useMemo(() => {
    const g = new Map();
    visibles.forEach((f) => {
      if (!g.has(f.rut)) g.set(f.rut, { rut: f.rut, nombre: f.razon_social, nueva: f.contraparte_nueva, plazo: f.plazo_dias, filas: [] });
      g.get(f.rut).filas.push(f);
    });
    return [...g.values()].sort((a, b) => b.filas.reduce((s, f) => s + f.monto_total, 0) - a.filas.reduce((s, f) => s + f.monto_total, 0));
  }, [visibles]);

  const total = filas.reduce((s, f) => s + f.signo * f.monto_total, 0);
  const sinCategoria = filas.filter((f) => !f.categoria);
  const sinProyecto = filas.filter((f) => !f.proyecto);
  const pagadas = filas.filter((f) => f.pagado);
  const nuevas = carga.resumen.contrapartes_nuevas;

  const sugerir = async () => {
    setSugiriendo(true);
    try {
      const { data } = await conPasos(['Leyendo los documentos sin categoría', 'Comparando con sus categorías', 'Proponiendo una para cada uno'],
        () => api.finanzas.sugerirCarga(slug, carga.id));
      // Solo se completan las que siguen sin categoría: lo que ya decidió la persona se respeta.
      const porN = Object.fromEntries(data.filas_previas.map((f) => [f.n, f]));
      setFilas((fs) => fs.map((f) => (!f.categoria && porN[f.n]?.categoria
        ? { ...f, categoria: porN[f.n].categoria, origen: 'ia' } : f)));
      setCarga(data);
      toast.success(data.sugeridos ? `La IA propuso categoría para ${data.sugeridos} documentos.` : 'La IA no encontró qué proponer.');
    } catch {
      toast.error('La IA no pudo responder ahora. Intente de nuevo.');
    } finally {
      setSugiriendo(false);
    }
  };

  const importar = async () => {
    setImportando(true);
    try {
      const decisiones = Object.fromEntries(filas.map((f) => [f.n, { categoria: f.categoria, proyecto: f.proyecto, pagado: f.pagado }]));
      const { data } = await api.finanzas.confirmarCarga(slug, carga.id, decisiones);
      onImportada(data);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'No se pudo importar.');
      setImportando(false);
    }
  };

  const cancelar = async () => {
    try { await api.finanzas.cancelarCarga(slug, carga.id); } catch { /* ya no existía */ }
    onCerrar();
  };

  const borde = `1px solid ${theme.palette.divider}`;
  const columnas = '1fr 130px 200px 140px 160px';

  const fila = (f, sangria) => (
    <Box key={f.n} sx={{ display: 'grid', gridTemplateColumns: columnas, borderTop: borde, alignItems: 'center' }}>
      <Celda sx={{ pl: sangria ? 5 : 1.25, gap: 1.5 }}>
        <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary', width: 92, flexShrink: 0, fontVariantNumeric: 'tabular-nums' }}>{diaMes(f.fecha)}</Typography>
        <Box sx={{ minWidth: 0 }}>
          <Typography sx={{ fontSize: '0.84rem' }} noWrap>{f.tipo_nombre} {f.folio}</Typography>
          {!agrupar && <Typography sx={{ fontSize: '0.75rem', color: 'text.secondary' }} noWrap>{f.razon_social}</Typography>}
        </Box>
      </Celda>
      <Celda sx={{ justifyContent: 'flex-end', fontVariantNumeric: 'tabular-nums', fontSize: '0.84rem', color: f.signo < 0 ? '#b42318' : 'inherit' }}>
        {f.signo < 0 && '−'}{clp(f.monto_total)}
      </Celda>
      <Celda sx={{ gap: 0.5 }}>
        <Selector value={f.categoria} opciones={cats} vacio="Sin categoría" onChange={(v) => cambiar([f.n], { categoria: v })} />
        {f.origen === 'ia' && <Sparkles size={13} color="var(--af-color)" title="Sugerida por la IA" />}
      </Celda>
      <Celda>
        <Selector ancho={130} value={f.pagado ? 'si' : 'no'} opciones={opcionesPago} vacio=""
          onChange={(v) => cambiar([f.n], { pagado: v === 'si' })} />
      </Celda>
      <Celda>
        <Selector ancho={150} value={f.proyecto} opciones={proyectos} vacio="Sin proyecto" onChange={(v) => cambiar([f.n], { proyecto: v })} />
      </Celda>
    </Box>
  );

  return (
    <Dialog open fullWidth maxWidth="lg" onClose={() => {}} PaperProps={{ sx: { height: '92vh', display: 'flex', flexDirection: 'column' } }}>
      {/* Encabezado */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25, px: 3, py: 2, borderBottom: borde }}>
        <Chip icon={<FileText size={13} />} label="SII" size="small" sx={{ bgcolor: TONOS.malva.suave, color: TONOS.malva.color, fontWeight: 600 }} />
        <Typography sx={{ fontFamily: "'Sora', sans-serif", fontWeight: 600, fontSize: '1.1rem' }}>Revisar antes de importar</Typography>
        <Typography sx={{ fontSize: '0.85rem', color: 'text.secondary' }}>{LIBRO[carga.libro]} · {carga.nombre_archivo}</Typography>
      </Box>

      {/* Resumen */}
      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: 'repeat(2, 1fr)', sm: 'repeat(5, 1fr)' }, mx: { xs: 2, sm: 3 }, mt: 2, border: borde, borderRadius: '12px', bgcolor: 'action.hover' }}>
        {[
          ['Nuevos', filas.length],
          ['Neto', clp(carga.resumen.neto)],
          ['IVA', clp(carga.resumen.iva)],
          ['Total', clp(carga.resumen.total)],
          ['Ya estaban · no se tocan', carga.ya_estaban.length],
        ].map(([t, v], i) => (
          <Box key={t} sx={{ py: 1.5, textAlign: 'center', borderLeft: i ? borde : 'none' }}>
            <Typography sx={{ fontFamily: "'Sora', sans-serif", fontWeight: 600, fontSize: '1.25rem', color: i === 4 ? 'text.secondary' : 'text.primary' }}>{v}</Typography>
            <Typography sx={{ fontSize: '0.72rem', letterSpacing: '0.06em', textTransform: 'uppercase', color: 'text.secondary' }}>{t}</Typography>
          </Box>
        ))}
      </Box>

      {/* Controles */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, px: 3, py: 1.5, flexWrap: 'wrap' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, border: borde, borderRadius: '8px', px: 1.25, width: 340 }}>
          <Search size={14} color={theme.palette.text.secondary} />
          <InputBase placeholder={`Buscar por ${n.contraparte}, RUT o folio`} value={buscar} onChange={(e) => setBuscar(e.target.value)} sx={{ flex: 1, fontSize: '0.85rem', py: 0.4 }} />
        </Box>
        <FormControlLabel control={<Checkbox size="small" checked={agrupar} onChange={(e) => setAgrupar(e.target.checked)} />}
          label={<Typography sx={{ fontSize: '0.85rem' }}>Agrupar por {n.contraparte}</Typography>} />
        {carga.ya_estaban.length > 0 && (
          <Button size="small" onClick={() => setVerYaEstaban((v) => !v)}>
            {verYaEstaban ? 'Ocultar' : 'Ver'} los {carga.ya_estaban.length} que ya estaban
          </Button>
        )}
        <Box sx={{ flex: 1 }} />
        {sinCategoria.length > 0 && (
          <Button size="small" variant="outlined" onClick={sugerir} disabled={sugiriendo}
            startIcon={sugiriendo ? <CircularProgress size={13} /> : <Sparkles size={14} color="var(--af-color)" />}>
            Sugerir categorías con IA
          </Button>
        )}
      </Box>

      {/* Tabla */}
      <Box sx={{ flex: 1, overflow: 'auto', mx: 3, border: borde, borderRadius: '12px' }}>
        <Box sx={{ display: 'grid', gridTemplateColumns: columnas, position: 'sticky', top: 0, zIndex: 1, bgcolor: 'background.paper',
          '& > div': { fontSize: '0.74rem', letterSpacing: '0.06em', textTransform: 'uppercase', color: 'text.secondary', py: 1 } }}>
          <Celda>Fecha · documento</Celda>
          <Celda sx={{ justifyContent: 'flex-end' }}>Total</Celda>
          <Celda>Categoría</Celda>
          <Celda>Pago</Celda>
          <Celda>Proyecto</Celda>
        </Box>
        {verYaEstaban && carga.ya_estaban.map((y) => (
          <Box key={`ya-${y.folio}-${y.razon_social}`} sx={{ display: 'grid', gridTemplateColumns: columnas, borderTop: borde, opacity: 0.55 }}>
            <Celda><Typography sx={{ fontSize: '0.82rem' }} noWrap>Folio {y.folio} · {y.razon_social}</Typography></Celda>
            <Celda sx={{ justifyContent: 'flex-end', fontSize: '0.82rem' }}>{clp(y.monto_total)}</Celda>
            <Celda><Typography sx={{ fontSize: '0.8rem', color: 'text.secondary' }}>Ya estaba · no se toca</Typography></Celda>
          </Box>
        ))}
        {agrupar ? grupos.map((g) => {
          const ns = g.filas.map((f) => f.n);
          const unico = (k) => { const v = new Set(g.filas.map((f) => f[k])); return v.size === 1 ? [...v][0] : undefined; };
          const abierto = !cerrados[g.rut];
          return (
            <Box key={g.rut}>
              <Box sx={{ display: 'grid', gridTemplateColumns: columnas, borderTop: `1.5px solid ${theme.palette.text.primary}22`, bgcolor: 'action.hover', alignItems: 'center' }}>
                <Celda sx={{ gap: 1, cursor: 'pointer' }}>
                  <Box onClick={() => setCerrados((c) => ({ ...c, [g.rut]: abierto }))} sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 0 }}>
                    {abierto ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
                    <Typography sx={{ fontWeight: 600, fontSize: '0.88rem' }} noWrap>{g.nombre || g.rut}</Typography>
                    <Typography sx={{ fontSize: '0.75rem', color: 'text.secondary', flexShrink: 0 }}>{g.rut} · {g.filas.length}</Typography>
                    {g.nueva && <Chip label="Nuevo" size="small" sx={{ height: 18, fontSize: '0.66rem', bgcolor: TONOS.salvia.suave, color: TONOS.salvia.color }} />}
                  </Box>
                </Celda>
                <Celda sx={{ justifyContent: 'flex-end', fontWeight: 600, fontSize: '0.86rem', fontVariantNumeric: 'tabular-nums' }}>
                  {clp(g.filas.reduce((s, f) => s + f.signo * f.monto_total, 0))}
                </Celda>
                <Celda><Selector value={unico('categoria') ?? null} mixto={unico('categoria') === undefined} opciones={cats} vacio="Sin categoría" onChange={(v) => cambiar(ns, { categoria: v })} /></Celda>
                <Celda><Typography sx={{ fontSize: '0.76rem', color: 'text.secondary' }}>{g.nueva ? `Plazo supuesto: ${g.plazo} días` : `Suele pagar a ${g.plazo} días`}</Typography></Celda>
                <Celda><Selector ancho={150} value={unico('proyecto') ?? null} mixto={unico('proyecto') === undefined} opciones={proyectos} vacio="Sin proyecto" onChange={(v) => cambiar(ns, { proyecto: v })} /></Celda>
              </Box>
              {abierto && g.filas.map((f) => fila(f, true))}
            </Box>
          );
        }) : visibles.map((f) => fila(f, false))}
      </Box>

      {/* Falta decidir */}
      <Box sx={{ px: 3, pt: 1.5, display: 'flex', flexDirection: 'column', gap: 0.75 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25, flexWrap: 'wrap', fontSize: '0.82rem' }}>
          <Typography sx={{ fontSize: '0.72rem', letterSpacing: '0.06em', textTransform: 'uppercase', color: 'text.secondary', mr: 0.5 }}>Falta decidir</Typography>
          {sinCategoria.length > 0 && (
            <>
              <Chip size="small" label={sinCategoria.length} sx={{ height: 20, bgcolor: '#fbe1d1', color: '#8a5a00' }} /> sin categoría
              <Select size="small" displayEmpty value="" renderValue={() => 'Asignar categoría'} onChange={(e) => cambiar(sinCategoria.map((f) => f.n), { categoria: e.target.value })}
                sx={{ fontSize: '0.78rem', height: 26 }}>
                {cats.map((c) => <MenuItem key={c.id} value={c.id}>{c.nombre}</MenuItem>)}
              </Select>
            </>
          )}
          {proyectos.length > 0 && sinProyecto.length > 0 && (
            <>
              <Chip size="small" label={sinProyecto.length} sx={{ height: 20, bgcolor: 'action.hover' }} /> sin proyecto
              <Select size="small" displayEmpty value="" renderValue={() => 'Asignar proyecto'} onChange={(e) => cambiar(sinProyecto.map((f) => f.n), { proyecto: e.target.value })}
                sx={{ fontSize: '0.78rem', height: 26 }}>
                {proyectos.map((p) => <MenuItem key={p.id} value={p.id}>{p.nombre}</MenuItem>)}
              </Select>
            </>
          )}
          {pagadas.length > 0 && (
            <>
              <Chip size="small" label={pagadas.length} sx={{ height: 20, bgcolor: '#d7ede0', color: '#007956' }} />
              ya vencieron y quedarán como {n.pagada.toLowerCase()}s
              <Button size="small" variant="outlined" sx={{ height: 26, fontSize: '0.76rem' }}
                onClick={() => cambiar(pagadas.map((f) => f.n), { pagado: false })}>Marcar las que no</Button>
            </>
          )}
          {sinCategoria.length === 0 && pagadas.length === 0 && (proyectos.length === 0 || sinProyecto.length === 0) && (
            <Typography sx={{ fontSize: '0.82rem', color: '#007956' }}>Todo decidido.</Typography>
          )}
        </Box>
        {nuevas.length > 0 && (
          <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary' }} noWrap>
            <b style={{ color: theme.palette.text.primary }}>Entran por primera vez:</b> {nuevas.length} {nuevas.length === 1 ? n.contraparte : n.plural} nuevos — {nuevas.join(' · ')}
          </Typography>
        )}
        {carga.errores.length > 0 && (
          <Typography sx={{ fontSize: '0.8rem', color: '#b45309' }}>
            {carga.errores.length} {carga.errores.length === 1 ? 'fila no se pudo leer' : 'filas no se pudieron leer'}: {carga.errores.slice(0, 3).map((e) => `fila ${e.fila}${e.folio ? ` (folio ${e.folio})` : ''}: ${e.motivo}`).join(' · ')}
          </Typography>
        )}
      </Box>

      {/* Pie */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, px: 3, py: 2 }}>
        <Box sx={{ flex: 1 }}>
          <Typography sx={{ fontWeight: 600 }}>{filas.length} documentos · {clp(total)}</Typography>
          <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary' }}>
            Con categoría entran confirmados; sin categoría quedan por revisar.
          </Typography>
        </Box>
        <Button onClick={cancelar} disabled={importando}>Cancelar</Button>
        <Button variant="contained" onClick={importar} disabled={importando || filas.length === 0}>
          {importando ? 'Importando…' : `Importar ${filas.length} documentos`}
        </Button>
      </Box>
    </Dialog>
  );
}
