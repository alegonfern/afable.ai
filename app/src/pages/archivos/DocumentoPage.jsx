import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Alert, Box, Button, Chip, CircularProgress, IconButton, Stack, TextField,
  Typography, useTheme,
} from '@mui/material';
import { ArrowLeft, Bot, Download, History, RotateCcw, Save, User, X } from 'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../../services/api';
import VistaDelArchivo from './VistaDelArchivo';
import { useWorkspace } from '../../context/WorkspaceContext';

const DISPLAY = `'Sora', 'Inter', sans-serif`;
const MONO = `'JetBrains Mono', 'Fira Code', monospace`;

/**
 * Un documento: su texto a la izquierda y su historia a la derecha.
 *
 * El historial no es un adorno: es lo que hace razonable que un agente edite los
 * documentos de la empresa. Cada versión dice quién la escribió —una persona o un
 * agente, con su @— y se puede leer y restaurar.
 *
 * Un documento no editable (un PDF, un Excel) se muestra igual, en modo lectura, con el
 * texto que se le extrajo. Ocultarlo sería peor: existe, el agente lo lee, y quien entra
 * tiene que poder ver lo mismo.
 */
export default function DocumentoPage() {
  const { docId } = useParams();
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const navigate = useNavigate();
  const { slug } = useWorkspace();

  const textMuted = d ? 'rgba(255,255,255,0.66)' : 'rgba(0,0,0,0.62)';
  const bgSuave = d ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.02)';
  const borde = theme.palette.divider;

  const [doc, setDoc] = useState(null);
  const [texto, setTexto] = useState('');
  const [guardado, setGuardado] = useState('');   // lo último confirmado por el servidor
  const [mensaje, setMensaje] = useState('');
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState('');
  const [versiones, setVersiones] = useState([]);
  const [verHistorial, setVerHistorial] = useState(true);
  const [viendo, setViendo] = useState(null);     // versión que se está mirando
  const [bajandoPdf, setBajandoPdf] = useState(false);

  /**
   * Trae el PDF con la sesión puesta y lo entrega como descarga.
   *
   * Se arma un enlace temporal en memoria en vez de mandar al navegador a la URL: la
   * petición tiene que llevar el token, y una pestaña nueva no lo lleva.
   */
  const descargarPdf = async () => {
    setBajandoPdf(true);
    try {
      const { data } = await api.descargarPdfDelArchivo(doc.id, slug);
      const url = URL.createObjectURL(new Blob([data], { type: 'application/pdf' }));
      const enlace = document.createElement('a');
      enlace.href = url;
      enlace.download = `${(doc.title || 'documento').replace(/[/\\?%*:|"<>]/g, '-')}.pdf`;
      document.body.appendChild(enlace);
      enlace.click();
      enlace.remove();
      // Sin esto el blob queda ocupando memoria hasta que se recargue la página.
      URL.revokeObjectURL(url);
    } catch {
      toast.error('No se pudo generar el PDF de este documento.');
    } finally {
      setBajandoPdf(false);
    }
  };

  const cargar = useCallback(async () => {
    if (!slug || !docId) return;
    try {
      const { data } = await api.getContenido(docId, slug);
      setDoc(data);
      setTexto(data.contenido || '');
      setGuardado(data.contenido || '');
    } catch {
      toast.error('Este documento no existe o no tiene acceso.');
      navigate('/app/archivos');
    }
  }, [slug, docId, navigate]);

  const cargarVersiones = useCallback(async () => {
    if (!slug || !docId) return;
    try {
      const { data } = await api.getVersiones(docId, slug);
      setVersiones(data.results || []);
    } catch { /* el historial es accesorio: si falla, el editor sigue sirviendo */ }
  }, [slug, docId]);

  useEffect(() => { cargar(); }, [cargar]);
  useEffect(() => { cargarVersiones(); }, [cargarVersiones]);

  const sinGuardar = texto !== guardado;

  const guardar = async () => {
    try {
      setGuardando(true);
      setError('');
      const { data } = await api.saveContenido(docId, {
        workspace: slug, contenido: texto, mensaje,
      });
      setGuardado(data.contenido || '');
      setMensaje('');
      await cargarVersiones();
      toast.success(`Guardado como versión ${data.version.numero}.`);
    } catch (e) {
      setError(e.response?.data?.detail || 'No se pudo guardar.');
    } finally {
      setGuardando(false);
    }
  };

  const mirar = async (numero) => {
    try {
      const { data } = await api.getVersion(docId, numero, slug);
      setViendo(data);
    } catch {
      toast.error('No se pudo leer esa versión.');
    }
  };

  const restaurar = async (numero) => {
    try {
      const { data } = await api.restaurarVersion(docId, numero, slug);
      setTexto(data.contenido || '');
      setGuardado(data.contenido || '');
      setViendo(null);
      await cargarVersiones();
      toast.success(`Se volvió a la versión ${numero}. Nada se borró: quedó como la ${data.version.numero}.`);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'No se pudo restaurar.');
    }
  };

  if (doc === null) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', pt: 12 }}>
        <CircularProgress size={26} sx={{ color: '#586AD0' }} />
      </Box>
    );
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100%' }}>
      {/* Barra */}
      <Stack
        direction="row" spacing={1} alignItems="center"
        sx={{ px: { xs: 1.5, sm: 2.5 }, py: 1.25, borderBottom: `1px solid ${borde}` }}
      >
        <IconButton size="small" onClick={() => navigate('/app/archivos')} title="Volver a Archivos">
          <ArrowLeft size={16} />
        </IconButton>
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography sx={{
            fontFamily: DISPLAY, fontSize: '1.0625rem', fontWeight: 600,
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}>
            {doc.title}
          </Typography>
          <Typography sx={{ fontSize: '0.78rem', color: textMuted }}>
            {[
              doc.editable ? 'editable' : 'solo lectura',
              doc.versiones > 0 ? (doc.versiones === 1 ? '1 versión' : `${doc.versiones} versiones`) : null,
              sinGuardar ? 'sin guardar' : null,
            ].filter(Boolean).join(' · ')}
          </Typography>
        </Box>
        {/* Lo que sale de Afable y se le manda a alguien. Sin este botón, generar el
            PDF existiría solo en el backend — y una ruta sin enlace es una pantalla que
            no existe. */}
        <Button
          onClick={descargarPdf}
          disabled={bajandoPdf}
          startIcon={<Download size={15} />}
          sx={{ textTransform: 'none', fontWeight: 600, color: textMuted }}
        >
          {bajandoPdf ? 'Generando…' : 'PDF'}
        </Button>
        <Button
          onClick={() => setVerHistorial((v) => !v)}
          startIcon={<History size={15} />}
          sx={{ textTransform: 'none', fontWeight: 600, color: textMuted }}
        >
          Historial
        </Button>
        {doc.editable && (
          <Button
            onClick={guardar} variant="contained" disabled={guardando || !sinGuardar}
            startIcon={<Save size={15} />}
            sx={{ textTransform: 'none', borderRadius: '8px', fontWeight: 600 }}
          >
            {guardando ? 'Guardando…' : 'Guardar'}
          </Button>
        )}
      </Stack>

      <Box sx={{ display: 'flex', flex: 1, minHeight: 0 }}>
        {/* Editor */}
        <Box sx={{ flex: 1, minWidth: 0, px: { xs: 2, sm: 3 }, py: 2.5 }}>
          {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>{error}</Alert>}

          {!doc.editable && (
            <Alert severity="info" sx={{ mb: 2, fontSize: '0.85rem' }}>
              Este archivo no se edita como texto. Se muestra tal como es, y el agente lo
              lee completo para responder sobre él.
            </Alert>
          )}

          {doc.editable ? (
            <TextField
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            disabled={!doc.editable}
            multiline minRows={20} fullWidth
            placeholder={doc.editable ? 'Escriba acá…' : 'Sin texto extraído.'}
            InputProps={{
              sx: {
                bgcolor: bgSuave, borderRadius: '10px', fontFamily: MONO,
                fontSize: '0.875rem', lineHeight: 1.7, alignItems: 'flex-start',
                '& fieldset': { borderColor: borde },
                '&.Mui-focused fieldset': { borderColor: '#586AD0' },
              },
            }}
          />

          ) : (
            <VistaDelArchivo documentoId={doc.id} workspaceSlug={slug} />
          )}

          {doc.editable && sinGuardar && (
            <TextField
              value={mensaje}
              onChange={(e) => setMensaje(e.target.value)}
              placeholder="Qué cambió, en una línea (opcional pero ayuda al que lo lea después)"
              size="small" fullWidth sx={{ mt: 1.5 }}
              InputProps={{
                sx: {
                  bgcolor: bgSuave, borderRadius: '8px', fontSize: '0.875rem',
                  '& fieldset': { borderColor: borde },
                },
              }}
            />
          )}
        </Box>

        {/* Historial */}
        {verHistorial && (
          <Box sx={{
            width: 300, flexShrink: 0, borderLeft: `1px solid ${borde}`,
            px: 2, py: 2.5, display: { xs: 'none', md: 'block' },
          }}>
            <Typography sx={{
              fontSize: '0.6875rem', fontWeight: 700, letterSpacing: '0.08em',
              textTransform: 'uppercase', color: '#586AD0', mb: 1.75,
            }}>
              Historial
            </Typography>

            {versiones.length === 0 ? (
              <Typography sx={{ fontSize: '0.85rem', color: textMuted }}>
                Todavía no hay versiones.
              </Typography>
            ) : (
              <Stack spacing={1}>
                {versiones.map((v) => {
                  const deAgente = v.origen === 'agente';
                  return (
                    <Box key={v.numero} sx={{
                      p: 1.25, borderRadius: '9px', bgcolor: bgSuave,
                      border: `1px solid ${viendo?.numero === v.numero ? '#586AD0' : borde}`,
                    }}>
                      <Stack direction="row" spacing={0.75} alignItems="center">
                        <Box sx={{
                          width: 22, height: 22, borderRadius: '6px', flexShrink: 0,
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          bgcolor: deAgente ? 'rgba(88,106,208,0.16)' : 'rgba(0,0,0,0.06)',
                          color: deAgente ? '#9BA6E3' : textMuted,
                        }}>
                          {deAgente ? <Bot size={12} /> : <User size={12} />}
                        </Box>
                        <Typography sx={{ fontSize: '0.85rem', fontWeight: 600, flex: 1 }}>
                          v{v.numero}
                        </Typography>
                        <Chip
                          size="small" label={v.quien}
                          sx={{
                            fontSize: '0.7rem', height: 20,
                            ...(deAgente
                              ? { bgcolor: 'rgba(88,106,208,0.16)', color: '#9BA6E3', fontWeight: 600 }
                              : {}),
                          }}
                        />
                      </Stack>
                      {v.mensaje && (
                        <Typography sx={{ fontSize: '0.8rem', color: textMuted, mt: 0.6 }}>
                          {v.mensaje}
                        </Typography>
                      )}
                      <Stack direction="row" spacing={0.5} sx={{ mt: 0.75 }}>
                        <Button
                          size="small" onClick={() => mirar(v.numero)}
                          sx={{ textTransform: 'none', fontSize: '0.78rem', minWidth: 0, px: 0.75 }}
                        >
                          Ver
                        </Button>
                        {doc.editable && v.numero !== versiones[0]?.numero && (
                          <Button
                            size="small" onClick={() => restaurar(v.numero)}
                            startIcon={<RotateCcw size={12} />}
                            sx={{
                              textTransform: 'none', fontSize: '0.78rem', minWidth: 0, px: 0.75,
                              color: '#f0b429',
                            }}
                          >
                            Volver a esta
                          </Button>
                        )}
                      </Stack>
                    </Box>
                  );
                })}
              </Stack>
            )}

            <Typography sx={{ fontSize: '0.75rem', color: textMuted, mt: 2 }}>
              Volver a una versión anterior no borra las de después: queda como una versión
              nueva.
            </Typography>
          </Box>
        )}
      </Box>

      {/* Lo que dice una versión vieja */}
      {viendo && (
        <Box
          onClick={() => setViendo(null)}
          sx={{
            position: 'fixed', inset: 0, zIndex: 1400, display: 'flex',
            alignItems: 'center', justifyContent: 'center', p: 3,
            bgcolor: 'rgba(0,0,0,0.55)', backdropFilter: 'blur(3px)',
          }}
        >
          <Box
            onClick={(e) => e.stopPropagation()}
            sx={{
              width: 760, maxWidth: '92vw', maxHeight: '80vh', overflow: 'auto',
              bgcolor: theme.palette.background.paper, borderRadius: '14px',
              border: `1px solid ${borde}`, p: 3,
            }}
          >
            <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.5 }}>
              <Typography sx={{ fontFamily: DISPLAY, fontSize: '1.0625rem', fontWeight: 600, flex: 1 }}>
                Versión {viendo.numero} · {viendo.quien}
              </Typography>
              <IconButton size="small" onClick={() => setViendo(null)}>
                <X size={16} />
              </IconButton>
            </Stack>
            {viendo.mensaje && (
              <Typography sx={{ fontSize: '0.85rem', color: textMuted, mb: 1.5 }}>
                {viendo.mensaje}
              </Typography>
            )}
            <Typography sx={{
              fontFamily: MONO, fontSize: '0.82rem', lineHeight: 1.7, whiteSpace: 'pre-wrap',
              p: 1.75, borderRadius: '9px', bgcolor: bgSuave, border: `1px solid ${borde}`,
            }}>
              {viendo.contenido || '(vacío)'}
            </Typography>
            {doc.editable && (
              <Button
                onClick={() => restaurar(viendo.numero)} startIcon={<RotateCcw size={14} />}
                sx={{ textTransform: 'none', fontWeight: 600, mt: 2, color: '#f0b429' }}
              >
                Volver a esta versión
              </Button>
            )}
          </Box>
        </Box>
      )}
    </Box>
  );
}
