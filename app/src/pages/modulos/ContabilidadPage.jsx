import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { seccionDe } from '../../layout/Dashboard/modulos';
import {
  Box, Button, Checkbox, Chip, CircularProgress, Dialog, DialogActions, DialogContent,
  DialogTitle, IconButton, InputBase, Menu, MenuItem, Select, Table, TableBody, TableCell,
  TableHead, TableRow, Tooltip, Typography, useTheme,
} from '@mui/material';
import {
  AlertTriangle, Check, CheckCircle2, FileUp, MoreHorizontal, Plus, Sparkles,
} from 'lucide-react';
import { toast } from 'react-toastify';
import PageHeader from '../../components/PageHeader';
import { useWorkspace } from '../../context/WorkspaceContext';
import { api } from '../../services/api';
import RevisionCarga from './RevisionCarga';
import GuiaLibrosSII from '../../components/GuiaLibrosSII';
import { Destello, Numero } from '../../components/Animado';
import { CategoriasVista, ImpuestosVista, ProyectosVista, ResumenVista } from './Numeros';
import Conciliacion from './Conciliacion';
import Reparto from './Reparto';
import { useVersionDeConfiguracion } from './Configuraciones';
import { usePanelLateral } from '../../layout/Dashboard/panelContexto';
import { usePantalla } from '../../layout/Dashboard/PanelLateral';
import { conPasos } from '../../components/ProgresoFlotante';
import { TONOS } from '../../theme/tonos';

/*
 * Contabilidad › Módulo (PMV financiero, etapa 1, 17-10-2026): la empresa sube lo que
 * descarga del SII —el Registro de Compras y Ventas y las boletas de honorarios— y lo deja
 * clasificado. La IA propone la categoría; la persona confirma. "Siempre así para este
 * proveedor" crea una regla que se aplica hacia atrás y en las cargas siguientes.
 */

const LIBROS = [
  { key: 'compras', label: 'Compras' },
  { key: 'ventas', label: 'Ventas' },
  { key: 'honorarios', label: 'Honorarios' },
];

// Porcentajes a la chilena: 0,25% y no 0.25%.
const clp = (n) => `$${Math.round(Number(n) || 0).toLocaleString('es-CL')}`;
const fecha = (iso) => {
  const [a, m, d] = iso.split('-');
  return `${d}-${m}-${a}`;
};

function ZonaDeCarga({ onArchivo, cargando, compacta }) {
  const theme = useTheme();
  const input = useRef(null);
  const [encima, setEncima] = useState(false);
  return (
    <Box
      onClick={() => !cargando && input.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setEncima(true); }}
      onDragLeave={() => setEncima(false)}
      onDrop={(e) => {
        e.preventDefault(); setEncima(false);
        if (e.dataTransfer.files?.[0]) onArchivo(e.dataTransfer.files[0]);
      }}
      sx={{
        border: `1.5px dashed ${encima ? 'var(--af-color)' : theme.palette.divider}`,
        bgcolor: encima ? 'var(--af-color-suave)' : 'transparent',
        borderRadius: '14px', cursor: cargando ? 'default' : 'pointer',
        p: compacta ? 2 : 5, textAlign: 'center', transition: 'all .15s',
        '&:hover': { borderColor: 'var(--af-color)' },
      }}
    >
      <input ref={input} type="file" accept=".csv,text/csv" hidden
        onChange={(e) => { if (e.target.files?.[0]) onArchivo(e.target.files[0]); e.target.value = ''; }} />
      {cargando ? <CircularProgress size={22} /> : (
        <>
          <Box sx={{ display: 'inline-flex', p: 1.25, borderRadius: '10px', bgcolor: TONOS.arena.suave, color: TONOS.arena.color, mb: 1.25 }}>
            <FileUp size={20} />
          </Box>
          <Typography sx={{ fontWeight: 600, fontSize: '0.95rem' }}>
            Arrastre aquí el archivo del SII o haga clic para buscarlo
          </Typography>
          {!compacta && (
            <Typography sx={{ fontSize: '0.85rem', color: 'text.secondary', mt: 0.75, maxWidth: 560, mx: 'auto', lineHeight: 1.6 }}>
              El CSV del <b>Registro de Compras y Ventas</b> (compras o ventas) o el informe de
              <b> boletas de honorarios recibidas</b>, tal como lo descarga. Afable reconoce cuál es,
              no repite lo que ya cargó y le avisa qué filas no pudo leer.
            </Typography>
          )}
        </>
      )}
    </Box>
  );
}

function ResultadoDeCarga({ carga, onCerrar }) {
  const nombre = LIBROS.find((l) => l.key === carga.libro)?.label || carga.libro;
  return (
    // Entra con un destello verde: es lo recién cargado.
    <Destello sx={{ border: '1px solid', borderColor: 'divider', borderRadius: '12px', p: 2 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: carga.errores.length ? 1.25 : 0 }}>
        <CheckCircle2 size={17} color="#007956" />
        <Typography sx={{ fontSize: '0.9rem', flex: 1 }}>
          <b>{carga.nombre_archivo}</b> · {nombre}: {carga.nuevos} documentos nuevos
          {carga.duplicados > 0 && `, ${carga.duplicados} ya estaban cargados`}
          {carga.errores.length > 0 && `, ${carga.errores.length} con errores`}.
        </Typography>
        <Button size="small" onClick={onCerrar}>Cerrar</Button>
      </Box>
      {carga.errores.length > 0 && (
        <Box sx={{ pl: 3.25 }}>
          {carga.errores.slice(0, 8).map((e) => (
            <Typography key={`${e.fila}-${e.folio}`} sx={{ fontSize: '0.8rem', color: 'text.secondary' }}>
              <AlertTriangle size={12} style={{ verticalAlign: '-2px', color: '#b45309' }} /> Fila {e.fila}
              {e.folio && ` · folio ${e.folio}`}: {e.motivo}
            </Typography>
          ))}
        </Box>
      )}
    </Destello>
  );
}

const PAGO = {
  ventas: { si: 'Cobrada', no: 'Por cobrar' },
  compras: { si: 'Pagada', no: 'Por pagar' },
  honorarios: { si: 'Pagada', no: 'Por pagar' },
};

/* Las fichas de proveedores y clientes salieron de aquí el 22-10-2026: son la ficha única de
   contacto de Compras › Proveedores y Ventas › Clientes (`pages/comercial/Contactos`). */

export default function ContabilidadPage() {
  const theme = useTheme();
  const navigate = useNavigate();
  const { seccion: param } = useParams();
  const { slug, esEditor } = useWorkspace();
  const [docs, setDocs] = useState(null);
  const [categorias, setCategorias] = useState([]);
  const [proyectos, setProyectos] = useState([]);
  const [libro, setLibro] = useState('compras');
  const [soloPorRevisar, setSoloPorRevisar] = useState(false);
  const [seleccion, setSeleccion] = useState([]);
  const [cargando, setCargando] = useState(false);
  const [ultimaCarga, setUltimaCarga] = useState(null);
  const [sugiriendo, setSugiriendo] = useState(false);
  const [reparto, setReparto] = useState(null);
  const [menu, setMenu] = useState(null);           // { ancla, doc }
  const [revision, setRevision] = useState(null);   // la carga en borrador que se está revisando
  const [verGuia, setVerGuia] = useState(false);     // la guía para bajar los libros del SII
  const location = useLocation();

  // Una carga subida desde la guía del chat llega con su id: se abre su revisión aquí, que es
  // donde se revisa y se confirma antes de que entre nada.
  useEffect(() => {
    const id = location.state?.revisarCarga;
    if (!id || !slug) return;
    navigate(location.pathname, { replace: true, state: {} });
    api.finanzas.carga(slug, id).then(({ data }) => setRevision(data)).catch(() => {});
  }, [location.state, slug]); // eslint-disable-line react-hooks/exhaustive-deps
  // La sección viene de la dirección (/app/contabilidad/documentos) y se elige en el submenú
  // de la barra lateral. Sin sección, la primera del módulo.
  const seccion = seccionDe('contabilidad', param);
  const vista = seccion.slug;
  const setVista = (v) => navigate(`/app/contabilidad/${v}`);

  const recargar = useCallback(async () => {
    if (!slug) return;
    const [d, c] = await Promise.all([api.finanzas.documentos(slug), api.finanzas.categorias(slug)]);
    setDocs(d.data.documentos);
    setCategorias(c.data);
  }, [slug]);

  const recargarProyectos = useCallback(() => {
    if (slug) api.finanzas.proyectos(slug).then(({ data }) => setProyectos(data));
  }, [slug]);

  // La configuración vive en el panel de la derecha: al cambiarla se recargan los proyectos
  // y se rehacen las vistas de números (la tasa de PPM cambia el F29).
  const panel = usePanelLateral();
  const versionConfig = useVersionDeConfiguracion();
  useEffect(() => { recargar(); recargarProyectos(); }, [recargar, recargarProyectos, versionConfig]);
  usePantalla(vista === 'documentos' ? `libro de ${libro}` : '');
  useEffect(() => { setSeleccion([]); }, [libro, soloPorRevisar]);

  const cuenta = useMemo(() => {
    const r = {};
    LIBROS.forEach((l) => {
      const del = (docs || []).filter((d) => d.libro === l.key);
      r[l.key] = { total: del.length, revisar: del.filter((d) => d.estado === 'por_revisar').length };
    });
    return r;
  }, [docs]);

  const visibles = useMemo(() => (docs || [])
    .filter((d) => d.libro === libro && (!soloPorRevisar || d.estado === 'por_revisar')), [docs, libro, soloPorRevisar]);
  const categoriasDelLibro = categorias.filter((c) => (libro === 'ventas') === (c.tipo === 'ingreso'));

  const subir = async (archivo) => {
    setCargando(true);
    try {
      const { data } = await conPasos(['Leyendo el archivo', 'Reconociendo qué libro es', 'Revisando lo que ya estaba cargado', 'Proponiendo categorías'],
        () => api.finanzas.cargar(slug, archivo));
      if (data.filas_previas?.length) {
        setRevision(data);                       // se revisa antes de que entre nada
      } else {
        // Nada nuevo (todo ya estaba, o solo errores): no hay qué revisar.
        await api.finanzas.cancelarCarga(slug, data.id).catch(() => {});
        setUltimaCarga(data);
      }
    } catch (e) {
      toast.error(e.response?.data?.detail || 'No se pudo cargar el archivo.');
    } finally {
      setCargando(false);
    }
  };

  const actualizar = async (doc, cambios) => {
    try {
      const { data } = await api.finanzas.actualizarDocumento(slug, doc.id, cambios);
      if (data.regla_aplicada_a > 0) {
        const n = data.regla_aplicada_a;
        toast.success(`Regla guardada: se aplicó también a ${n} ${n === 1 ? 'documento' : 'documentos'} más de ${doc.razon_social}.`);
        await recargar();
      } else {
        setDocs((ds) => ds.map((d) => (d.id === doc.id ? data : d)));
      }
      return true;
    } catch (e) {
      toast.error(e.response?.data?.detail || 'No se pudo guardar.');
      return false;
    }
  };

  const enLote = async (cambios) => {
    try {
      const { data } = await api.finanzas.lote(slug, { ids: seleccion, ...cambios });
      toast.success(`${data.actualizados} ${data.actualizados === 1 ? 'documento actualizado' : 'documentos actualizados'}.`);
      setSeleccion([]);
      await recargar();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'No se pudo actualizar.');
    }
  };

  const sugerir = async () => {
    setSugiriendo(true);
    try {
      const { data } = await api.finanzas.sugerir(slug);
      toast.success(data.sugeridos
        ? `La IA propuso categoría para ${data.sugeridos} documentos. Revíselas y confírmelas.`
        : 'No hay documentos sin categoría.');
      await recargar();
    } catch {
      toast.error('La IA no pudo responder ahora. Intente de nuevo.');
    } finally {
      setSugiriendo(false);
    }
  };

  const sinCategoria = (docs || []).filter((d) => !d.categoria).length;
  const todos = visibles.length > 0 && seleccion.length === visibles.length;
  const borde = `1px solid ${theme.palette.divider}`;

  return (
    // minWidth 0: sin esto la tabla ancha estira la página entera en vez de hacer su propio scroll.
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', minWidth: 0, width: '100%' }}>
      <PageHeader
        title={seccion.label}
        crumbs={[{ label: 'Contabilidad', to: '/app/contabilidad' }]}
        back="/app"
        backLabel="Inicio"
      />

      <Box sx={{ flex: 1, minWidth: 0, overflow: 'auto', px: 3, py: 2.5, display: 'flex', flexDirection: 'column', gap: 2 }}>
        {/* Sin empresa no hay a quién cargarle nada: se dice, en vez de girar para siempre. */}
        {!slug ? (
          <Typography sx={{ m: 'auto', color: 'text.secondary', fontSize: '0.9rem', textAlign: 'center', maxWidth: 420 }}>
            Para cargar la información del SII primero tiene que crear su empresa en Afable.
          </Typography>
        ) : docs === null ? <CircularProgress size={22} sx={{ m: 'auto' }} /> : (
          <>
            {/* Cargar del SII vive en Documentos; sin nada cargado aparece en cualquier sección,
                porque sin eso no hay qué mostrar. */}
            {esEditor && (vista === 'documentos' || docs.length === 0) && (
              <>
                <ZonaDeCarga onArchivo={subir} cargando={cargando} compacta={docs.length > 0} />
                <Box>
                  <Button size="small" onClick={() => setVerGuia((v) => !v)} sx={{ textTransform: 'none', fontSize: '0.82rem' }}>
                    {verGuia ? 'Ocultar la guía' : '¿Cómo bajo estos archivos del SII? Ver la guía paso a paso'}
                  </Button>
                  {verGuia && (
                    <Box sx={{ mt: 1, p: 2.5, border: `1px solid ${theme.palette.divider}`, borderRadius: '14px', bgcolor: 'background.paper' }}>
                      <GuiaLibrosSII libroInicial={libro} onArchivo={(archivo) => subir(archivo)} cargando={cargando} />
                    </Box>
                  )}
                </Box>
              </>
            )}
            {ultimaCarga && <ResultadoDeCarga carga={ultimaCarga} onCerrar={() => setUltimaCarga(null)} />}

            {docs.length > 0 && vista === 'resumen' && <ResumenVista key={versionConfig} slug={slug} onVerImpuestos={() => setVista('impuestos')} />}
            {docs.length > 0 && vista === 'impuestos' && <ImpuestosVista key={versionConfig} slug={slug} esEditor={esEditor} />}
            {docs.length > 0 && vista === 'categorias' && <CategoriasVista slug={slug} />}
            {docs.length > 0 && vista === 'conciliacion' && <Conciliacion slug={slug} esEditor={esEditor} />}
            {docs.length > 0 && vista === 'proyectos' && <ProyectosVista key={versionConfig} slug={slug} onConfigurar={() => panel?.abrir('config')} />}

            {docs.length > 0 && vista === 'documentos' && (
              <>
                {/* Libros y filtros */}
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                  <Box sx={{ display: 'flex', gap: '2px', p: '3px', borderRadius: '9px', border: borde, bgcolor: 'action.hover' }}>
                    {LIBROS.map((l) => (
                      <Box key={l.key} component="button" onClick={() => setLibro(l.key)}
                        sx={{
                          border: 'none', cursor: 'pointer', fontFamily: 'inherit', fontSize: '0.84rem', fontWeight: 500,
                          px: 1.5, py: 0.5, borderRadius: '7px',
                          bgcolor: libro === l.key ? 'background.paper' : 'transparent',
                          color: libro === l.key ? 'text.primary' : 'text.secondary',
                          boxShadow: libro === l.key ? '0 1px 2px rgba(11,11,15,0.08)' : 'none',
                        }}>
                        {l.label} <span style={{ opacity: 0.6 }}>{cuenta[l.key].total}</span>
                      </Box>
                    ))}
                  </Box>
                  <Chip
                    label={<>Por revisar · <Numero valor={cuenta[libro].revisar} /></>}
                    onClick={() => setSoloPorRevisar((v) => !v)}
                    variant={soloPorRevisar ? 'filled' : 'outlined'}
                    sx={{ fontFamily: 'inherit', fontSize: '0.8rem', height: 30 }}
                  />
                  <Box sx={{ flex: 1 }} />
                  {esEditor && sinCategoria > 0 && (
                    <Button size="small" variant="outlined" onClick={sugerir} disabled={sugiriendo}
                      startIcon={sugiriendo ? <CircularProgress size={13} /> : <Sparkles size={14} color="var(--af-color)" />}>
                      Sugerir categorías con IA ({sinCategoria})
                    </Button>
                  )}
                </Box>

                {/* Acciones en lote */}
                {esEditor && seleccion.length > 0 && (
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25, px: 1.5, py: 1, borderRadius: '10px', bgcolor: 'var(--af-color-suave)' }}>
                    <Typography sx={{ fontSize: '0.85rem', fontWeight: 500 }}>{seleccion.length} seleccionados</Typography>
                    <Select size="small" displayEmpty value="" onChange={(e) => enLote({ categoria: e.target.value })}
                      sx={{ minWidth: 220, fontSize: '0.84rem', bgcolor: 'background.paper' }}
                      renderValue={() => 'Asignar categoría…'}>
                      {categoriasDelLibro.map((c) => <MenuItem key={c.id} value={c.id}>{c.nombre}</MenuItem>)}
                    </Select>
                    <Button size="small" variant="contained" startIcon={<Check size={14} />} onClick={() => enLote({ confirmar: true })}>
                      Confirmar
                    </Button>
                  </Box>
                )}

                {/* Documentos */}
                <Box sx={{ border: borde, borderRadius: '12px', overflow: 'auto', maxWidth: '100%', bgcolor: 'background.paper' }}>
                  <Table size="small" sx={{ '& td, & th': { fontSize: '0.84rem', borderColor: 'divider', whiteSpace: 'nowrap', px: 1.1 } }}>
                    <TableHead>
                      <TableRow sx={{ '& th': { color: 'text.secondary', fontWeight: 500, bgcolor: 'action.hover' } }}>
                        {esEditor && (
                          <TableCell padding="checkbox">
                            <Checkbox size="small" checked={todos}
                              indeterminate={seleccion.length > 0 && !todos}
                              onChange={() => setSeleccion(todos ? [] : visibles.map((d) => d.id))} />
                          </TableCell>
                        )}
                        <TableCell>Fecha</TableCell>
                        <TableCell>Documento</TableCell>
                        <TableCell>{libro === 'ventas' ? 'Cliente' : 'Proveedor'}</TableCell>
                        <TableCell align="right">Total</TableCell>
                        <TableCell>Categoría</TableCell>
                        <TableCell>Proyecto</TableCell>
                        <TableCell>Pago</TableCell>
                        <TableCell>Estado</TableCell>
                        <TableCell />
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {visibles.length === 0 && (
                        <TableRow><TableCell colSpan={10} sx={{ textAlign: 'center', color: 'text.secondary', py: 4 }}>
                          {soloPorRevisar ? 'Nada por revisar en este libro.' : 'Todavía no hay documentos en este libro.'}
                        </TableCell></TableRow>
                      )}
                      {visibles.map((d) => (
                        <TableRow key={d.id} hover selected={seleccion.includes(d.id)}>
                          {esEditor && (
                            <TableCell padding="checkbox">
                              <Checkbox size="small" checked={seleccion.includes(d.id)}
                                onChange={() => setSeleccion((s) => (s.includes(d.id) ? s.filter((x) => x !== d.id) : [...s, d.id]))} />
                            </TableCell>
                          )}
                          <TableCell>{fecha(d.fecha)}</TableCell>
                          <TableCell>
                            <Tooltip title={d.tipo_nombre} arrow><span>{d.tipo_documento === 'BHE' ? 'BHE' : `T${d.tipo_documento}`} · {d.folio}</span></Tooltip>
                          </TableCell>
                          <TableCell sx={{ maxWidth: 190, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                            {d.razon_social}
                            <Typography component="span" sx={{ fontSize: '0.75rem', color: 'text.secondary', ml: 0.75 }}>{d.rut}</Typography>
                          </TableCell>
                          <TableCell align="right" sx={{ fontVariantNumeric: 'tabular-nums', color: d.signo < 0 ? '#b42318' : 'inherit' }}>
                            {d.signo < 0 && '−'}{clp(d.monto_total)}
                          </TableCell>
                          <TableCell>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
                              <Select size="small" displayEmpty value={d.categoria || ''} disabled={!esEditor}
                                onChange={(e) => actualizar(d, { categoria: e.target.value || null })}
                                sx={{ width: 160, fontSize: '0.82rem', '& .MuiSelect-select': { py: 0.5 } }}
                                renderValue={(v) => (v ? categorias.find((c) => c.id === v)?.nombre : <span style={{ color: theme.palette.text.disabled }}>Sin categoría</span>)}>
                                <MenuItem value=""><em>Sin categoría</em></MenuItem>
                                {categoriasDelLibro.map((c) => <MenuItem key={c.id} value={c.id}>{c.nombre}</MenuItem>)}
                              </Select>
                              {d.origen_clasificacion === 'ia' && (
                                <Tooltip title="Sugerida por la IA: confírmela o cámbiela" arrow>
                                  <Box sx={{ display: 'flex', color: 'var(--af-color)' }}><Sparkles size={14} /></Box>
                                </Tooltip>
                              )}
                              {d.origen_clasificacion === 'regla' && (
                                <Tooltip title="Puesta por la regla de este proveedor" arrow>
                                  <Chip label="Regla" size="small" sx={{ height: 20, fontSize: '0.68rem' }} />
                                </Tooltip>
                              )}
                            </Box>
                          </TableCell>
                          <TableCell>
                            <Select size="small" displayEmpty disabled={!esEditor || proyectos.length === 0}
                              value={d.asignaciones.length === 1 && Number(d.asignaciones[0].porcentaje) === 100 ? d.asignaciones[0].proyecto : ''}
                              onChange={(e) => (e.target.value === 'repartir' ? setReparto(d)
                                : actualizar(d, { asignaciones: e.target.value ? [{ proyecto: e.target.value, porcentaje: 100 }] : [] }))}
                              sx={{ width: 115, fontSize: '0.82rem', '& .MuiSelect-select': { py: 0.5 } }}
                              renderValue={(v) => {
                                if (d.asignaciones.length > 1) return `${d.asignaciones.length} proyectos`;
                                if (d.asignaciones.length === 1 && !v) return `${d.asignaciones[0].proyecto_nombre} ${Number(d.asignaciones[0].porcentaje)}%`;
                                if (v) return proyectos.find((p) => p.id === v)?.nombre;
                                return <span style={{ color: theme.palette.text.disabled }}>{proyectos.length ? 'Sin proyecto' : '—'}</span>;
                              }}>
                              <MenuItem value=""><em>Sin proyecto</em></MenuItem>
                              {proyectos.map((p) => <MenuItem key={p.id} value={p.id}>{p.nombre}</MenuItem>)}
                              {proyectos.length > 1 && <MenuItem value="repartir" sx={{ borderTop: '1px solid', borderColor: 'divider', fontSize: '0.84rem' }}>Repartir entre varios…</MenuItem>}
                            </Select>
                          </TableCell>
                          <TableCell>
                            <Tooltip arrow title={d.pagado ? (d.fecha_pago ? `Marcado el ${fecha(d.fecha_pago)}` : 'Se dio por pagado al importar (ya había vencido)') : (d.fecha_vencimiento ? `Vence el ${fecha(d.fecha_vencimiento)}` : '')}>
                              <Chip size="small" clickable={esEditor} disabled={!esEditor}
                                label={(PAGO[d.libro] || PAGO.compras)[d.pagado ? 'si' : 'no']}
                                onClick={() => esEditor && actualizar(d, { pagado: !d.pagado })}
                                // Pagada en menta, por pagar en arena (30-10-2026, theme/tonos.js); si venció, lo dice
                                // el aviso al pasar el mouse.
                                sx={{ height: 22, fontSize: '0.72rem', fontFamily: 'inherit', fontWeight: 500,
                                  bgcolor: d.pagado ? TONOS.menta.suave : TONOS.arena.suave,
                                  color: d.pagado ? TONOS.menta.color : TONOS.arena.color }} />
                            </Tooltip>
                          </TableCell>
                          <TableCell>
                            {d.estado === 'confirmado'
                              ? <Chip label="Confirmado" size="small" sx={{ height: 22, fontSize: '0.72rem', fontWeight: 500, bgcolor: TONOS.salvia.suave, color: TONOS.salvia.color, fontFamily: 'inherit' }} />
                              : (
                                <Button size="small" disabled={!esEditor || !d.categoria} onClick={() => actualizar(d, { estado: 'confirmado' })}
                                  sx={{ fontSize: '0.76rem', py: 0.1, minWidth: 0 }}>
                                  Confirmar
                                </Button>
                              )}
                          </TableCell>
                          <TableCell padding="none">
                            {esEditor && (
                              <IconButton size="small" onClick={(e) => setMenu({ ancla: e.currentTarget, doc: d })}>
                                <MoreHorizontal size={15} />
                              </IconButton>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </Box>
              </>
            )}
          </>
        )}
      </Box>

      <Menu anchorEl={menu?.ancla} open={Boolean(menu)} onClose={() => setMenu(null)}>
        <MenuItem disabled={!menu?.doc?.categoria}
          onClick={() => { actualizar(menu.doc, { crear_regla: true, estado: 'confirmado' }); setMenu(null); }}>
          Siempre así para {menu?.doc?.razon_social || 'este proveedor'}
        </MenuItem>
      </Menu>

      {revision && (
        <RevisionCarga carga={revision} slug={slug} categorias={categorias} proyectos={proyectos}
          onCerrar={() => setRevision(null)}
          onImportada={async (carga) => {
            setRevision(null);
            setUltimaCarga(carga);
            setLibro(carga.libro);
            setVista('documentos');
            await recargar();
          }} />
      )}

      {reparto && (
        <Reparto doc={reparto} proyectos={proyectos} onCerrar={() => setReparto(null)}
          onGuardar={(asignaciones) => actualizar(reparto, { asignaciones })} />
      )}

    </Box>
  );
}
