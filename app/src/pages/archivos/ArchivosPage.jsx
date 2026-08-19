import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Alert, Box, Button, CircularProgress, IconButton, InputBase, Menu, MenuItem,
  Stack, TextField, ToggleButton, ToggleButtonGroup, Typography, useTheme,
} from '@mui/material';
import {
  ChevronDown, ChevronRight, FileText, Folder, FolderPlus, Home, LayoutGrid, List, Lock,
  MoreVertical, Search, Upload,
} from 'lucide-react';
import { toast } from 'react-toastify';
import PageHeader from '../../components/PageHeader';
import NavConocimiento from '../../components/NavConocimiento';
import { api } from '../../services/api';
import DialogoPermisos from './DialogoPermisos';
import { useWorkspace } from '../../context/WorkspaceContext';

/**
 * El explorador de archivos de la empresa.
 *
 * Árbol de carpetas a la izquierda, contenido a la derecha, como en cualquier gestor de
 * archivos — la forma es conocida a propósito: nadie tiene que aprender a usarlo.
 *
 * La carpeta abierta va en el `?carpeta=` de la URL, así se puede compartir el enlace de
 * una carpeta y recargar no devuelve a la raíz.
 */
export default function ArchivosPage() {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const navigate = useNavigate();
  const { slug, espacioSlug, espacio, seleccionarEspacio } = useWorkspace();
  const [searchParams, setSearchParams] = useSearchParams();

  const textMuted = d ? 'rgba(255,255,255,0.66)' : 'rgba(0,0,0,0.62)';
  const bgSuave = d ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.02)';
  const borde = theme.palette.divider;

  const carpetaAbierta = searchParams.get('carpeta') || '';
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState('');
  const [busqueda, setBusqueda] = useState('');
  const [nombreNueva, setNombreNueva] = useState(null);   // null = no se está creando
  const [desplegadas, setDesplegadas] = useState({});
  const [menu, setMenu] = useState(null);                 // {tipo, item, anchor}
  const [renombrando, setRenombrando] = useState(null);
  const [subiendo, setSubiendo] = useState(false);
  const [permisos, setPermisos] = useState(null);   // {carpeta} o {documento}
  // Cuadrícula o lista. Se recuerda porque es una preferencia de cómo mirar, no del
  // contenido: quien eligió una vista no quiere volver a elegirla en cada carpeta.
  const [vista, setVista] = useState(() => localStorage.getItem('afable_vista_archivos') || 'cuadricula');

  const cambiarVista = (cual) => {
    setVista(cual);
    localStorage.setItem('afable_vista_archivos', cual);
  };
  const entrada = useRef(null);

  const cargar = useCallback(async () => {
    if (!slug) return;
    try {
      const { data } = await api.getExplorador(slug, {
        ...(carpetaAbierta ? { carpeta: carpetaAbierta } : {}),
        ...(busqueda.trim() ? { q: busqueda.trim() } : {}),
        // El Workspace elegido arriba acota lo que se ve. Con "Todos" no viaja y se
        // ven todos los archivos que la persona alcanza.
        ...(espacioSlug ? { espacio: espacioSlug } : {}),
      });
      setDatos(data);
    } catch {
      setError('No se pudieron leer los archivos.');
      setDatos({ arbol: [], subcarpetas: [], documentos: [], migas: [] });
    }
  }, [slug, espacioSlug, carpetaAbierta, busqueda]);

  useEffect(() => {
    const t = setTimeout(cargar, busqueda ? 300 : 0);
    return () => clearTimeout(t);
  }, [cargar, busqueda]);

  const abrir = (id) => setSearchParams(id ? { carpeta: String(id) } : {}, { replace: false });

  const crearCarpeta = async () => {
    const name = (nombreNueva || '').trim();
    if (!name) return;
    try {
      await api.createCarpeta({
        workspace: slug, name, ...(carpetaAbierta ? { parent: carpetaAbierta } : {}),
      });
      setNombreNueva(null);
      await cargar();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'No se pudo crear la carpeta.');
    }
  };

  const renombrar = async (tipo, item, nombre) => {
    const name = (nombre || '').trim();
    if (!name) return;
    try {
      if (tipo === 'carpeta') await api.updateCarpeta(item.id, { workspace: slug, name });
      else await api.updateArchivo(item.id, { workspace: slug, title: name });
      setRenombrando(null);
      await cargar();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'No se pudo renombrar.');
    }
  };

  const borrarCarpeta = async (carpeta) => {
    try {
      await api.deleteCarpeta(carpeta.id, slug);
      toast.success('Carpeta eliminada. Sus archivos quedaron en la raíz.');
      if (String(carpeta.id) === carpetaAbierta) abrir(null);
      else await cargar();
    } catch {
      toast.error('No se pudo eliminar la carpeta.');
    }
  };

  const mover = async (docId, carpetaId) => {
    try {
      await api.updateArchivo(docId, { workspace: slug, carpeta: carpetaId || null });
      await cargar();
    } catch {
      toast.error('No se pudo mover el archivo.');
    }
  };

  const subir = async (e) => {
    const archivo = e.target.files?.[0];
    if (!archivo) return;
    try {
      setSubiendo(true);
      const fd = new FormData();
      fd.append('file', archivo);
      // Va con la carpeta abierta: subir y después mover serían dos viajes, y un estado
      // intermedio raro si el segundo falla.
      if (carpetaAbierta) fd.append('carpeta', carpetaAbierta);
      await api.subirArchivo(slug, fd);
      await cargar();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'No se pudo subir el archivo.');
    } finally {
      setSubiendo(false);
      if (entrada.current) entrada.current.value = '';
    }
  };

  if (datos === null) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', pt: 12 }}>
        <CircularProgress size={26} sx={{ color: '#586AD0' }} />
      </Box>
    );
  }

  // Ramas del árbol: hijas de `padre`, dibujadas recursivamente.
  const Rama = ({ padre, nivel }) => {
    const hijas = datos.arbol.filter((c) => c.parent === padre);
    if (hijas.length === 0) return null;
    return hijas.map((c) => {
      const activa = String(c.id) === carpetaAbierta;
      const tieneHijas = datos.arbol.some((x) => x.parent === c.id);
      const abierta = desplegadas[c.id] ?? activa;
      return (
        <Box key={c.id}>
          <Stack
            direction="row" spacing={0.5} alignItems="center"
            onClick={() => abrir(c.id)}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              const docId = e.dataTransfer.getData('documento');
              if (docId) mover(Number(docId), c.id);
            }}
            sx={{
              pl: 1 + nivel * 1.5, pr: 1, py: 0.5, borderRadius: '6px', cursor: 'pointer',
              color: activa ? '#586AD0' : textMuted,
              bgcolor: activa ? (d ? 'rgba(88,106,208,0.14)' : 'rgba(88,106,208,0.09)') : 'transparent',
              '&:hover': { bgcolor: activa ? undefined : bgSuave },
            }}
          >
            <Box
              onClick={(e) => {
                e.stopPropagation();
                if (tieneHijas) setDesplegadas((p) => ({ ...p, [c.id]: !abierta }));
              }}
              sx={{ display: 'flex', width: 14, flexShrink: 0 }}
            >
              {tieneHijas && (abierta ? <ChevronDown size={13} /> : <ChevronRight size={13} />)}
            </Box>
            <Folder size={14} style={{ flexShrink: 0 }} />
            <Typography sx={{
              fontSize: '0.84rem', flex: 1, minWidth: 0, fontWeight: activa ? 600 : 400,
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }}>
              {c.name}
            </Typography>
          </Stack>
          {abierta && <Rama padre={c.id} nivel={nivel + 1} />}
        </Box>
      );
    });
  };

  /**
   * Una ficha de la cuadrícula: la carpeta se ve como carpeta.
   *
   * Comparte con `Fila` el arrastrar y soltar, el doble clic y el menú: lo único que
   * cambia es la forma. Lo que NO entra acá son las versiones y quién editó último — para
   * eso está la lista, y por eso las dos vistas se conservan en vez de reemplazarse.
   */
  const Ficha = ({ tipo, item }) => {
    const esCarpeta = tipo === 'carpeta';
    const nombre = esCarpeta ? item.name : item.title;
    const restringido = esCarpeta ? item.restringida : item.restringido;
    const editandoNombre = renombrando?.tipo === tipo && renombrando?.id === item.id;

    return (
      <Box
        draggable={!esCarpeta}
        onDragStart={(e) => { if (!esCarpeta) e.dataTransfer.setData('documento', String(item.id)); }}
        onDragOver={(e) => { if (esCarpeta) e.preventDefault(); }}
        onDrop={(e) => {
          if (!esCarpeta) return;
          e.preventDefault();
          const docId = e.dataTransfer.getData('documento');
          if (docId) mover(Number(docId), item.id);
        }}
        onDoubleClick={() => {
          if (esCarpeta) abrir(item.id);
          else navigate(`/app/archivos/${item.id}`);
        }}
        sx={{
          position: 'relative', p: 1.75, borderRadius: '12px', cursor: 'pointer',
          border: `1px solid ${borde}`, bgcolor: bgSuave,
          display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1,
          transition: 'border-color .15s, background-color .15s',
          '&:hover': {
            borderColor: d ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.2)',
            bgcolor: d ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.035)',
          },
        }}
      >
        <Box sx={{ position: 'absolute', top: 4, right: 4, display: 'flex', alignItems: 'center', gap: 0.25 }}>
          {restringido && (
            <Box
              title={`Restringido · ${(esCarpeta ? item.compartida_con : item.compartido_con) || 0} con acceso`}
              sx={{ display: 'flex', color: '#f0b429' }}
            >
              <Lock size={12} />
            </Box>
          )}
          <IconButton
            size="small"
            onClick={(e) => { e.stopPropagation(); setMenu({ tipo, item, anchor: e.currentTarget }); }}
          >
            <MoreVertical size={14} />
          </IconButton>
        </Box>

        <Box sx={{
          color: esCarpeta ? '#f0b429' : '#9BA6E3',
          mt: 0.5, display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          {esCarpeta ? <Folder size={44} strokeWidth={1.5} /> : <FileText size={40} strokeWidth={1.5} />}
        </Box>

        <Box sx={{ width: '100%', textAlign: 'center', minWidth: 0 }}>
          {editandoNombre ? (
            <InputBase
              autoFocus defaultValue={nombre}
              onClick={(e) => e.stopPropagation()}
              onKeyDown={(e) => {
                if (e.key === 'Enter') renombrar(tipo, item, e.target.value);
                if (e.key === 'Escape') setRenombrando(null);
              }}
              onBlur={(e) => renombrar(tipo, item, e.target.value)}
              sx={{ fontSize: '0.85rem', fontWeight: 600, width: '100%', '& input': { textAlign: 'center' } }}
            />
          ) : (
            <Typography
              title={nombre}
              sx={{
                fontSize: '0.85rem', fontWeight: 600, lineHeight: 1.35,
                display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
                overflow: 'hidden', wordBreak: 'break-word',
              }}
            >
              {nombre}
            </Typography>
          )}
          <Typography sx={{ fontSize: '0.72rem', color: textMuted, mt: 0.35 }}>
            {esCarpeta
              ? `${item.documentos} archivo${item.documentos === 1 ? '' : 's'}`
              : (item.editable ? 'editable' : 'solo lectura')}
          </Typography>
        </Box>
      </Box>
    );
  };

  const Fila = ({ tipo, item }) => {
    const esCarpeta = tipo === 'carpeta';
    const nombre = esCarpeta ? item.name : item.title;
    const editandoNombre = renombrando?.tipo === tipo && renombrando?.id === item.id;

    return (
      <Stack
        direction="row" spacing={1.5} alignItems="center"
        draggable={!esCarpeta}
        onDragStart={(e) => { if (!esCarpeta) e.dataTransfer.setData('documento', String(item.id)); }}
        onDragOver={(e) => { if (esCarpeta) e.preventDefault(); }}
        onDrop={(e) => {
          if (!esCarpeta) return;
          e.preventDefault();
          const docId = e.dataTransfer.getData('documento');
          if (docId) mover(Number(docId), item.id);
        }}
        onDoubleClick={() => {
          if (esCarpeta) abrir(item.id);
          else navigate(`/app/archivos/${item.id}`);
        }}
        sx={{
          px: 1.5, py: 1.25, borderRadius: '9px', cursor: 'pointer',
          border: `1px solid ${borde}`, bgcolor: bgSuave,
          '&:hover': { borderColor: d ? 'rgba(255,255,255,0.18)' : 'rgba(0,0,0,0.18)' },
        }}
      >
        <Box sx={{
          width: 30, height: 30, borderRadius: '8px', flexShrink: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          bgcolor: esCarpeta ? 'rgba(240,180,41,0.14)' : 'rgba(88,106,208,0.14)',
          color: esCarpeta ? '#f0b429' : '#9BA6E3',
        }}>
          {esCarpeta ? <Folder size={15} /> : <FileText size={15} />}
        </Box>

        {/* Un candado en la fila: restringido tiene que verse sin abrir nada, o nadie
            sabe qué está a la vista del equipo y qué no. */}
        {(esCarpeta ? item.restringida : item.restringido) && (
          <Box
            title={`Restringido · ${(esCarpeta ? item.compartida_con : item.compartido_con) || 0} con acceso`}
            sx={{ display: 'flex', color: '#f0b429', flexShrink: 0 }}
          >
            <Lock size={13} />
          </Box>
        )}

        <Box sx={{ flex: 1, minWidth: 0 }}>
          {editandoNombre ? (
            <InputBase
              autoFocus defaultValue={nombre}
              onKeyDown={(e) => {
                if (e.key === 'Enter') renombrar(tipo, item, e.target.value);
                if (e.key === 'Escape') setRenombrando(null);
              }}
              onBlur={(e) => renombrar(tipo, item, e.target.value)}
              sx={{ fontSize: '0.9375rem', fontWeight: 600, width: '100%' }}
            />
          ) : (
            <Typography sx={{
              fontSize: '0.9375rem', fontWeight: 600,
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }}>
              {nombre}
            </Typography>
          )}
          <Typography sx={{ fontSize: '0.8rem', color: textMuted }}>
            {esCarpeta
              ? [
                  item.hijas ? `${item.hijas} carpeta${item.hijas === 1 ? '' : 's'}` : null,
                  `${item.documentos} archivo${item.documentos === 1 ? '' : 's'}`,
                ].filter(Boolean).join(' · ')
              : [
                  item.editable ? 'editable' : 'solo lectura',
                  item.versiones > 1 ? `${item.versiones} versiones` : null,
                  item.ultima_version?.quien ? `última de ${item.ultima_version.quien}` : null,
                ].filter(Boolean).join(' · ')}
          </Typography>
        </Box>

        <IconButton
          size="small"
          onClick={(e) => { e.stopPropagation(); setMenu({ tipo, item, anchor: e.currentTarget }); }}
        >
          <MoreVertical size={15} />
        </IconButton>
      </Stack>
    );
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100%' }}>
      <PageHeader title="Archivos" back="/app" backLabel="Inicio" />

      {/* La misma barra que el hub: Archivos es del grupo Conocimiento aunque viva en su
          propia pantalla. Sin esto, estar acá dejaba sin forma de saltar a Conexiones. */}
      <NavConocimiento activa="archivos" />

      <Box sx={{ display: 'flex', flex: 1, minHeight: 0 }}>
        {/* Árbol */}
        <Box sx={{
          width: 240, flexShrink: 0, borderRight: `1px solid ${borde}`,
          py: 1.5, px: 1, display: { xs: 'none', md: 'block' },
        }}>
          <Stack
            direction="row" spacing={0.75} alignItems="center"
            onClick={() => abrir(null)}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              const docId = e.dataTransfer.getData('documento');
              if (docId) mover(Number(docId), null);
            }}
            sx={{
              px: 1, py: 0.5, borderRadius: '6px', cursor: 'pointer', mb: 0.5,
              color: !carpetaAbierta ? '#586AD0' : textMuted,
              bgcolor: !carpetaAbierta ? (d ? 'rgba(88,106,208,0.14)' : 'rgba(88,106,208,0.09)') : 'transparent',
              '&:hover': { bgcolor: !carpetaAbierta ? undefined : bgSuave },
            }}
          >
            <Home size={14} />
            <Typography sx={{ fontSize: '0.84rem', fontWeight: !carpetaAbierta ? 600 : 400 }}>
              Todos los archivos
            </Typography>
          </Stack>
          <Rama padre={null} nivel={0} />
        </Box>

        {/* Contenido */}
        <Box sx={{ flex: 1, minWidth: 0, px: { xs: 2, sm: 3 }, py: 2, pb: 6 }}>
          {/* Migas */}
          <Stack direction="row" spacing={0.5} alignItems="center" sx={{ mb: 1.5, flexWrap: 'wrap' }}>
            <Box component="button" onClick={() => abrir(null)} sx={{
              border: 'none', bgcolor: 'transparent', p: 0, cursor: 'pointer',
              fontFamily: 'inherit', fontSize: '0.875rem', color: textMuted,
              '&:hover': { textDecoration: 'underline' },
            }}>
              Todos los archivos
            </Box>
            {datos.migas.map((m) => (
              <Stack key={m.id} direction="row" spacing={0.5} alignItems="center">
                <Typography sx={{ color: textMuted, fontSize: '0.875rem' }}>/</Typography>
                <Box component="button" onClick={() => abrir(m.id)} sx={{
                  border: 'none', bgcolor: 'transparent', p: 0, cursor: 'pointer',
                  fontFamily: 'inherit', fontSize: '0.875rem', color: textMuted,
                  '&:hover': { textDecoration: 'underline' },
                }}>
                  {m.name}
                </Box>
              </Stack>
            ))}
            {datos.carpeta && (
              <>
                <Typography sx={{ color: textMuted, fontSize: '0.875rem' }}>/</Typography>
                <Typography sx={{ fontSize: '0.875rem', fontWeight: 600 }}>
                  {datos.carpeta.name}
                </Typography>
              </>
            )}
          </Stack>

          <Stack direction="row" spacing={1.25} sx={{ mb: 2.5, flexWrap: 'wrap', gap: 1.25 }}>
            <TextField
              value={busqueda}
              onChange={(e) => setBusqueda(e.target.value)}
              placeholder="Buscar en todos los archivos"
              size="small" sx={{ flex: 1, minWidth: 200 }}
              InputProps={{
                endAdornment: <Search size={15} color={textMuted} />,
                sx: {
                  bgcolor: bgSuave, borderRadius: '8px', fontSize: '0.9375rem',
                  '& fieldset': { borderColor: borde },
                  '&.Mui-focused fieldset': { borderColor: '#586AD0' },
                },
              }}
            />
            <Button
              onClick={() => setNombreNueva('')} startIcon={<FolderPlus size={15} />}
              sx={{ textTransform: 'none', fontWeight: 600 }}
            >
              Nueva carpeta
            </Button>
            <Button
              onClick={() => entrada.current?.click()} variant="contained" disabled={subiendo}
              startIcon={subiendo
                ? <CircularProgress size={14} sx={{ color: 'inherit' }} />
                : <Upload size={15} />}
              sx={{ textTransform: 'none', borderRadius: '8px', fontWeight: 600 }}
            >
              {subiendo ? 'Subiendo…' : 'Subir'}
            </Button>
            <input ref={entrada} type="file" hidden onChange={subir} />
            {/* Cuadrícula o lista. La lista muestra versiones y quién editó último, que
                en una ficha no caben: por eso conviven en vez de reemplazarse. */}
            <ToggleButtonGroup
              exclusive size="small" value={vista}
              onChange={(_, v) => { if (v) cambiarVista(v); }}
              sx={{
                '& .MuiToggleButton-root': {
                  px: 1, py: 0.4, borderColor: borde,
                  '&.Mui-selected': { bgcolor: 'rgba(88,106,208,0.16)', color: '#586AD0' },
                },
              }}
            >
              <ToggleButton value="cuadricula" title="Ver como carpetas">
                <LayoutGrid size={15} />
              </ToggleButton>
              <ToggleButton value="lista" title="Ver como lista">
                <List size={15} />
              </ToggleButton>
            </ToggleButtonGroup>
          </Stack>

          {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>{error}</Alert>}

          {datos.buscando && (
            <Typography sx={{ fontSize: '0.8125rem', color: textMuted, mb: 1.5 }}>
              Buscando en toda la empresa, no solo en esta carpeta.
            </Typography>
          )}

          {/* El campo para nombrar la carpeta nueva, igual en las dos vistas: lo que
              cambia es cómo se ve lo que ya existe. */}
          {nombreNueva !== null && (
            <Stack direction="row" spacing={1.5} alignItems="center" sx={{
              px: 1.5, py: 1.25, mb: 1.5, borderRadius: '9px',
              border: `1px dashed ${borde}`, bgcolor: bgSuave,
            }}>
              <Box sx={{
                width: 30, height: 30, borderRadius: '8px', flexShrink: 0,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                bgcolor: 'rgba(240,180,41,0.14)', color: '#f0b429',
              }}>
                <Folder size={15} />
              </Box>
              <InputBase
                autoFocus value={nombreNueva}
                onChange={(e) => setNombreNueva(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') crearCarpeta();
                  if (e.key === 'Escape') setNombreNueva(null);
                }}
                onBlur={() => { if (!nombreNueva.trim()) setNombreNueva(null); }}
                placeholder="Nombre de la carpeta"
                sx={{ fontSize: '0.9375rem', fontWeight: 600, flex: 1 }}
              />
            </Stack>
          )}

          {/* ⭐ Si el Workspace elegido arriba está escondiendo archivos, se DICE, con el
              número y la salida. Un filtro que actúa en silencio no se lee como filtro:
              se lee como «ese archivo no está», y quien no relaciona una cosa con la otra
              lo da por perdido. */}
          {datos.ocultos_por_espacio > 0 && (
            <Box sx={{
              display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap',
              px: 1.5, py: 1, mb: 1.5, borderRadius: '8px',
              bgcolor: 'action.hover',
            }}>
              <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary' }}>
                Mostrando {datos.documentos.length} de{' '}
                {datos.documentos.length + datos.ocultos_por_espacio} archivos.
                {' '}El Workspace <strong>{espacio?.name}</strong> deja fuera el resto.
              </Typography>
              <Typography
                onClick={() => seleccionarEspacio(null)}
                sx={{
                  fontSize: '0.78rem', fontWeight: 600, color: '#586AD0',
                  cursor: 'pointer', '&:hover': { textDecoration: 'underline' },
                }}
              >
                Ver todos
              </Typography>
            </Box>
          )}

          {vista === 'cuadricula' ? (
            <Box sx={{
              display: 'grid', gap: 1.25,
              // Fichas de ~132px que se acomodan solas: en una pantalla angosta entran
              // tres, en una ancha ocho, sin puntos de corte a mano.
              gridTemplateColumns: 'repeat(auto-fill, minmax(132px, 1fr))',
            }}>
              {!datos.buscando && datos.subcarpetas.map((c) => (
                <Ficha key={`c-${c.id}`} tipo="carpeta" item={c} />
              ))}
              {datos.documentos.map((doc) => (
                <Ficha key={`d-${doc.id}`} tipo="documento" item={doc} />
              ))}
            </Box>
          ) : (
            <Stack spacing={1}>
              {!datos.buscando && datos.subcarpetas.map((c) => (
                <Fila key={`c-${c.id}`} tipo="carpeta" item={c} />
              ))}
              {datos.documentos.map((doc) => (
                <Fila key={`d-${doc.id}`} tipo="documento" item={doc} />
              ))}
            </Stack>
          )}

          {datos.subcarpetas.length === 0 && datos.documentos.length === 0 && nombreNueva === null && (
            <Box sx={{
              py: 6, textAlign: 'center', borderRadius: '12px',
              border: `1px dashed ${borde}`, bgcolor: bgSuave,
            }}>
              <Typography sx={{ fontSize: '0.9375rem', color: textMuted }}>
                {datos.buscando ? 'Nada coincide con la búsqueda.' : 'Esta carpeta está vacía.'}
              </Typography>
            </Box>
          )}

          <Typography sx={{ fontSize: '0.8rem', color: textMuted, mt: 3 }}>
            Doble clic para abrir. Los archivos se arrastran a una carpeta del árbol para
            moverlos. Lo que no tiene candado lo ve todo el equipo; con «Compartir y
            permisos» se restringe una carpeta o un archivo suelto.
          </Typography>
        </Box>
      </Box>

      <DialogoPermisos
        abierto={Boolean(permisos)}
        onCerrar={() => setPermisos(null)}
        slug={slug}
        carpeta={permisos?.carpeta}
        documento={permisos?.documento}
        onCambio={cargar}
      />

      <Menu
        anchorEl={menu?.anchor} open={Boolean(menu)} onClose={() => setMenu(null)}
      >
        {menu?.tipo === 'documento' && (
          <MenuItem
            onClick={() => { navigate(`/app/archivos/${menu.item.id}`); setMenu(null); }}
            sx={{ fontSize: '0.9rem' }}
          >
            {menu.item.editable ? 'Abrir y editar' : 'Abrir'}
          </MenuItem>
        )}
        {menu?.tipo === 'carpeta' && (
          <MenuItem onClick={() => { abrir(menu.item.id); setMenu(null); }} sx={{ fontSize: '0.9rem' }}>
            Abrir
          </MenuItem>
        )}
        <MenuItem
          onClick={() => {
            setPermisos(menu.tipo === 'carpeta'
              ? { carpeta: menu.item.id }
              : { documento: menu.item.id });
            setMenu(null);
          }}
          sx={{ fontSize: '0.9rem' }}
        >
          Compartir y permisos…
        </MenuItem>
        <MenuItem
          onClick={() => { setRenombrando({ tipo: menu.tipo, id: menu.item.id }); setMenu(null); }}
          sx={{ fontSize: '0.9rem' }}
        >
          Renombrar
        </MenuItem>
        {menu?.tipo === 'documento' && menu.item.carpeta && (
          <MenuItem
            onClick={() => { mover(menu.item.id, null); setMenu(null); }}
            sx={{ fontSize: '0.9rem' }}
          >
            Sacar de la carpeta
          </MenuItem>
        )}
        {menu?.tipo === 'carpeta' && (
          <MenuItem
            onClick={() => { borrarCarpeta(menu.item); setMenu(null); }}
            sx={{ fontSize: '0.9rem', color: '#e5484d' }}
          >
            Eliminar la carpeta
          </MenuItem>
        )}
      </Menu>
    </Box>
  );
}
