import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Alert, Box, Button, CircularProgress, IconButton, MenuItem,
  Select, Stack, TextField, Typography, useTheme,
} from '@mui/material';
import { FileText, Search, Trash2, Upload } from 'lucide-react';
import { api } from '../../services/api';

const ORDENES = [
  { value: 'reciente', label: 'Más recientes' },
  { value: 'nombre', label: 'Por nombre' },
];

/**
 * Los Archivos de una Sesión.
 *
 * No son adjuntos muertos: al subirlos se les extrae el texto y se indexan para la
 * búsqueda semántica, igual que a un documento de la empresa — son `CompanyDocument`
 * con la Sesión puesta. Eso es lo que permite que los agentes los lean.
 */
export default function SesionArchivos({ sesion, slug }) {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const textMuted = d ? 'rgba(255,255,255,0.66)' : 'rgba(0,0,0,0.62)';
  const bgSuave = d ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.02)';
  const borde = theme.palette.divider;

  const entrada = useRef(null);
  const [archivos, setArchivos] = useState(null);
  const [error, setError] = useState('');
  const [busqueda, setBusqueda] = useState('');
  const [orden, setOrden] = useState('reciente');
  const [subiendo, setSubiendo] = useState(false);

  const cargar = useCallback(async () => {
    if (!slug) return;
    try {
      const { data } = await api.getSesionArchivos(sesion.slug, slug, {
        ...(busqueda.trim() ? { q: busqueda.trim() } : {}),
        orden,
      });
      setArchivos(data.results);
    } catch {
      setError('No se pudieron leer los archivos.');
      setArchivos([]);
    }
  }, [sesion.slug, slug, busqueda, orden]);

  useEffect(() => {
    const t = setTimeout(cargar, busqueda ? 300 : 0);
    return () => clearTimeout(t);
  }, [cargar, busqueda]);

  const subir = async (e) => {
    const archivo = e.target.files?.[0];
    if (!archivo) return;
    try {
      setSubiendo(true);
      setError('');
      const fd = new FormData();
      fd.append('file', archivo);
      await api.uploadSesionArchivo(sesion.slug, slug, fd);
      await cargar();
    } catch (err) {
      setError(err.response?.data?.detail || 'No se pudo subir el archivo.');
    } finally {
      setSubiendo(false);
      if (entrada.current) entrada.current.value = '';
    }
  };

  const borrar = async (archivo) => {
    try {
      await api.deleteSesionArchivo(sesion.slug, archivo.id, slug);
      setArchivos((as) => as.filter((a) => a.id !== archivo.id));
    } catch {
      setError('No se pudo borrar el archivo.');
    }
  };

  if (archivos === null) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
        <CircularProgress size={22} sx={{ color: '#586AD0' }} />
      </Box>
    );
  }

  return (
    <Box sx={{ px: { xs: 2.5, sm: 4 }, pt: 2, pb: 6, maxWidth: 900, width: '100%' }}>
      <Stack direction="row" spacing={1.25} sx={{ mb: 2.5, flexWrap: 'wrap', gap: 1.25 }}>
        <TextField
          value={busqueda}
          onChange={(e) => setBusqueda(e.target.value)}
          placeholder="Buscar archivos"
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
        <Select
          size="small" value={orden} onChange={(e) => setOrden(e.target.value)}
          sx={{ fontSize: '0.8125rem', minWidth: 150 }}
        >
          {ORDENES.map((o) => (
            <MenuItem key={o.value} value={o.value} sx={{ fontSize: '0.8125rem' }}>{o.label}</MenuItem>
          ))}
        </Select>
        <Button
          onClick={() => entrada.current?.click()} variant="contained" disabled={subiendo}
          startIcon={subiendo ? <CircularProgress size={14} sx={{ color: 'inherit' }} /> : <Upload size={15} />}
          sx={{ textTransform: 'none', borderRadius: '8px', fontWeight: 600, px: 2.25 }}
        >
          {subiendo ? 'Subiendo…' : 'Agregar'}
        </Button>
        <input ref={entrada} type="file" hidden onChange={subir} />
      </Stack>

      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>{error}</Alert>}

      {archivos.length === 0 ? (
        <Box sx={{
          py: 6, textAlign: 'center', borderRadius: '12px',
          border: `1px dashed ${borde}`, bgcolor: bgSuave,
        }}>
          <Typography sx={{ fontSize: '0.9375rem', color: textMuted }}>
            {busqueda
              ? 'Ningún archivo coincide con la búsqueda.'
              : 'Todavía no hay archivos en esta Sesión.'}
          </Typography>
          {!busqueda && (
            <Typography sx={{ fontSize: '0.8125rem', color: textMuted, mt: 0.75 }}>
              Lo que suba acá se le extrae el texto y queda al alcance de los agentes.
            </Typography>
          )}
        </Box>
      ) : (
        <Stack spacing={1}>
          {archivos.map((a) => (
            <Stack
              key={a.id} direction="row" spacing={1.5} alignItems="center"
              sx={{
                p: 1.5, borderRadius: '10px', bgcolor: bgSuave,
                border: `1px solid ${borde}`,
              }}
            >
              <Box sx={{
                width: 32, height: 32, borderRadius: '8px', flexShrink: 0,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                bgcolor: 'rgba(88, 106, 208, 0.14)', color: '#9BA6E3',
              }}>
                <FileText size={16} />
              </Box>
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography sx={{
                  fontSize: '0.9375rem', fontWeight: 600,
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}>
                  {a.url ? (
                    <Box component="a" href={a.url} target="_blank" rel="noreferrer"
                      sx={{ color: 'inherit', textDecoration: 'none', '&:hover': { textDecoration: 'underline' } }}>
                      {a.title}
                    </Box>
                  ) : a.title}
                </Typography>
                <Typography sx={{ fontSize: '0.8125rem', color: textMuted }}>
                  {[a.author, a.processing_error ? 'sin texto extraído' : null]
                    .filter(Boolean).join(' · ')}
                </Typography>
              </Box>
              <IconButton onClick={() => borrar(a)} title="Borrar el archivo" size="small">
                <Trash2 size={15} />
              </IconButton>
            </Stack>
          ))}
        </Stack>
      )}
    </Box>
  );
}
