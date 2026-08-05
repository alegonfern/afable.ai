import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Alert, Box, Button, CircularProgress, IconButton, InputBase, Menu, MenuItem,
  Stack, TextField, Typography, useTheme,
} from '@mui/material';
import {
  ChevronDown, ChevronRight, FileText, Folder, FolderPlus, Home,
  MoreVertical, Search, Upload,
} from 'lucide-react';
import { toast } from 'react-toastify';
import PageHeader from '../../components/PageHeader';
import { api } from '../../services/api';
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
  const { slug } = useWorkspace();
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
  const entrada = useRef(null);

  const cargar = useCallback(async () => {
    if (!slug) return;
    try {
      const { data } = await api.getExplorador(slug, {
        ...(carpetaAbierta ? { carpeta: carpetaAbierta } : {}),
        ...(busqueda.trim() ? { q: busqueda.trim() } : {}),
      });
      setDatos(data);
    } catch {
      setError('No se pudieron leer los archivos.');
      setDatos({ arbol: [], subcarpetas: [], documentos: [], migas: [] });
    }
  }, [slug, carpetaAbierta, busqueda]);

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
      <PageHeader title="Archivos" back="/app" backLabel="Chat" />

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
          </Stack>

          {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>{error}</Alert>}

          {datos.buscando && (
            <Typography sx={{ fontSize: '0.8125rem', color: textMuted, mb: 1.5 }}>
              Buscando en toda la empresa, no solo en esta carpeta.
            </Typography>
          )}

          <Stack spacing={1}>
            {nombreNueva !== null && (
              <Stack direction="row" spacing={1.5} alignItems="center" sx={{
                px: 1.5, py: 1.25, borderRadius: '9px',
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

            {!datos.buscando && datos.subcarpetas.map((c) => (
              <Fila key={`c-${c.id}`} tipo="carpeta" item={c} />
            ))}
            {datos.documentos.map((doc) => (
              <Fila key={`d-${doc.id}`} tipo="documento" item={doc} />
            ))}

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
          </Stack>

          <Typography sx={{ fontSize: '0.8rem', color: textMuted, mt: 3 }}>
            Doble clic para abrir. Los archivos se arrastran a una carpeta del árbol para
            moverlos. Todo lo que hay acá lo ve el equipo de la empresa: los permisos por
            archivo son lo próximo.
          </Typography>
        </Box>
      </Box>

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
