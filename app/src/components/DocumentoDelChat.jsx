/**
 * Lo que el agente dejó escrito, sin salir de la conversación.
 *
 * ⭐ **El problema que resuelve.** Hasta acá el agente escribía un documento y lo contaba
 * con una frase: "listo, quedó guardado". El documento existía en otra pantalla, y para
 * verlo había que abandonar el chat, entrar a Archivos, buscarlo y confiar en que era
 * ese. En la práctica nadie iba, así que el trabajo del agente se aceptaba a ciegas o se
 * perdía.
 *
 * Son dos piezas:
 *
 * - `TarjetaDeArtefacto`: una tarjeta en el mensaje mismo. Cierra el recorrido.
 * - `DocumentoAlLado`: el documento abierto AL LADO de la conversación, con **qué cambió**
 *   resaltado y un botón para deshacer. Es la diferencia entre enterarse de que algo
 *   cambió y poder decidir si está bien.
 */
import { useCallback, useEffect, useState } from 'react';
import {
  Box, Button, CircularProgress, IconButton, Stack, Tooltip, Typography, useTheme,
} from '@mui/material';
import { Download, ExternalLink, FileText, RotateCcw, Send, X } from 'lucide-react';
import TextField from '@mui/material/TextField';
import { toast } from 'react-toastify';
import { api } from '../services/api';
import VistaDelArchivo from '../pages/archivos/VistaDelArchivo';

const DISPLAY = `'Sora', 'Inter', sans-serif`;

const VERBO = {
  creado: 'Creado',
  editado: 'Editado',
  reescrito: 'Reescrito',
};

/**
 * La tarjeta que queda en el mensaje: qué documento tocó y cómo abrirlo.
 */
export function TarjetaDeArtefacto({ artefactos, onAbrir }) {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const lista = (artefactos || []).filter((a) => a && a.id);
  if (!lista.length) return null;

  return (
    <Stack spacing={0.75} sx={{ mt: 1 }}>
      {lista.map((a) => (
        <Box
          key={a.id}
          onClick={() => onAbrir(a.id)}
          sx={{
            display: 'flex', alignItems: 'center', gap: 1, cursor: 'pointer',
            px: 1.25, py: 0.9, borderRadius: '10px',
            border: `1px solid ${d ? 'rgba(155,166,227,0.28)' : 'rgba(88,106,208,0.25)'}`,
            bgcolor: d ? 'rgba(88,106,208,0.10)' : 'rgba(88,106,208,0.05)',
            '&:hover': { bgcolor: d ? 'rgba(88,106,208,0.18)' : 'rgba(88,106,208,0.10)' },
          }}
        >
          <FileText size={15} color="#7B8AE0" />
          <Box sx={{ minWidth: 0, flex: 1 }}>
            <Typography sx={{
              fontFamily: DISPLAY, fontWeight: 600, fontSize: '0.82rem',
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }}>
              {a.titulo || 'Documento'}
            </Typography>
            <Typography sx={{ fontSize: '0.7rem', color: 'text.disabled' }}>
              {VERBO[a.accion] || 'Guardado'} por el agente · abrir al lado
            </Typography>
          </Box>
          <ExternalLink size={13} color="#7B8AE0" />
        </Box>
      ))}
    </Stack>
  );
}

/**
 * Las líneas que cambiaron, pintadas. Lo agregado en verde, lo quitado en rojo.
 *
 * Se muestran solo los pedazos con cambios y una línea de contexto: mostrar el documento
 * entero obligaría a buscar la diferencia a ojo, que es justo lo que nadie hace.
 */
function Cambios({ lineas }) {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  if (!lineas?.length) return null;

  const color = (tipo) => {
    if (tipo === 'mas') return d ? 'rgba(74,222,128,0.13)' : 'rgba(22,163,74,0.10)';
    if (tipo === 'menos') return d ? 'rgba(248,113,113,0.13)' : 'rgba(220,38,38,0.09)';
    return 'transparent';
  };

  return (
    <Box sx={{
      border: `1px solid ${theme.palette.divider}`, borderRadius: '10px',
      overflow: 'hidden', mb: 2,
    }}>
      {lineas.map((l, i) => (
        l.tipo === 'salto' ? (
          <Box key={i} sx={{ height: '1px', bgcolor: theme.palette.divider, my: 0.5 }} />
        ) : (
          <Box key={i} sx={{
            display: 'flex', gap: 1, px: 1.25, py: 0.3, bgcolor: color(l.tipo),
            fontSize: '0.78rem', lineHeight: 1.5,
            fontFamily: `'JetBrains Mono', monospace`,
          }}>
            <Box component="span" sx={{ color: 'text.disabled', userSelect: 'none', width: 10 }}>
              {l.tipo === 'mas' ? '+' : l.tipo === 'menos' ? '−' : ''}
            </Box>
            <Box component="span" sx={{
              whiteSpace: 'pre-wrap', wordBreak: 'break-word',
              color: l.tipo === 'igual' ? 'text.disabled' : 'text.primary',
            }}>
              {l.texto || ' '}
            </Box>
          </Box>
        )
      ))}
    </Box>
  );
}

/**
 * Mandar el documento a alguien, en PDF.
 *
 * ⚠️ **Lo confirma una persona, no lo dispara el agente.** El destinatario se escribe y
 * se ve antes de que salga: un agente eligiendo a quién mandar un documento interno se
 * equivoca una vez y no hay forma de deshacerlo.
 */
function Enviar({ docId, workspace, titulo, onListo }) {
  const [abierto, setAbierto] = useState(false);
  const [para, setPara] = useState('');
  const [mensaje, setMensaje] = useState('');
  const [enviando, setEnviando] = useState(false);

  if (!abierto) {
    return (
      <Button
        size="small" onClick={() => setAbierto(true)} startIcon={<Send size={13} />}
        sx={{ textTransform: 'none', fontSize: '0.75rem', color: 'text.secondary' }}
      >
        Enviar por correo
      </Button>
    );
  }

  const enviar = async () => {
    setEnviando(true);
    try {
      await api.enviarDocumento(docId, {
        workspace, para: para.trim(), asunto: titulo, mensaje,
      });
      toast.success(`Enviado a ${para.trim()}.`);
      setAbierto(false); setPara(''); setMensaje('');
      onListo?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'No se pudo enviar.');
    } finally {
      setEnviando(false);
    }
  };

  return (
    <Stack spacing={1} sx={{ width: '100%' }}>
      <TextField
        size="small" fullWidth autoFocus placeholder="correo@ejemplo.cl"
        value={para} onChange={(e) => setPara(e.target.value)}
        inputProps={{ style: { fontSize: '0.82rem' } }}
      />
      <TextField
        size="small" fullWidth multiline minRows={2} placeholder="Un mensaje (opcional)"
        value={mensaje} onChange={(e) => setMensaje(e.target.value)}
        inputProps={{ style: { fontSize: '0.82rem' } }}
      />
      <Typography sx={{ fontSize: '0.7rem', color: 'text.disabled' }}>
        Va «{titulo}» en PDF adjunto. Sale desde Afable, con tu correo para responder.
      </Typography>
      <Stack direction="row" spacing={1}>
        <Button
          size="small" variant="contained" onClick={enviar}
          disabled={enviando || !para.includes('@')}
          sx={{ textTransform: 'none', borderRadius: '8px', fontSize: '0.78rem' }}
        >
          {enviando ? 'Enviando…' : 'Enviar'}
        </Button>
        <Button
          size="small" onClick={() => setAbierto(false)}
          sx={{ textTransform: 'none', fontSize: '0.78rem', color: 'text.disabled' }}
        >
          Cancelar
        </Button>
      </Stack>
    </Stack>
  );
}

/**
 * El documento abierto al lado de la conversación.
 *
 * Lo primero que se ve es **qué cambió en la última versión**, no el documento entero:
 * quien acaba de pedir un cambio quiere revisar ESE cambio. El documento completo está
 * debajo, y "Abrir en Archivos" lleva a la pantalla con todo el historial.
 */
export function DocumentoAlLado({ docId, workspace, onCerrar }) {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';

  const [doc, setDoc] = useState(null);
  const [cambios, setCambios] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [deshaciendo, setDeshaciendo] = useState(false);

  const cargar = useCallback(async () => {
    if (!docId || !workspace) return;
    setCargando(true);
    try {
      const { data } = await api.getContenido(docId, workspace);
      setDoc(data);
      // El diff se pide aparte y su fallo no rompe el panel: si no se puede calcular,
      // igual se ve el documento, que es lo mínimo que la persona vino a buscar.
      const numero = data.ultima_version?.numero;
      if (numero) {
        try {
          const r = await api.getCambiosDeVersion(docId, numero, workspace);
          setCambios(r.data);
        } catch { setCambios(null); }
      } else {
        setCambios(null);
      }
    } catch {
      toast.error('No se pudo abrir el documento.');
      onCerrar?.();
    } finally {
      setCargando(false);
    }
  }, [docId, workspace, onCerrar]);

  useEffect(() => { cargar(); }, [cargar]);

  const deshacer = async () => {
    const numero = cambios?.numero;
    if (!numero || numero <= 1) return;
    setDeshaciendo(true);
    try {
      await api.restaurarVersion(docId, numero - 1, workspace);
      toast.success(`Se volvió a la versión ${numero - 1}.`);
      await cargar();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'No se pudo deshacer.');
    } finally {
      setDeshaciendo(false);
    }
  };

  const descargarPdf = async () => {
    try {
      const { data } = await api.descargarPdfDelArchivo(docId, workspace);
      const url = URL.createObjectURL(new Blob([data], { type: 'application/pdf' }));
      const enlace = document.createElement('a');
      enlace.href = url;
      enlace.download = `${(doc?.title || 'documento').replace(/[/\\?%*:|"<>]/g, '-')}.pdf`;
      document.body.appendChild(enlace);
      enlace.click();
      enlace.remove();
      URL.revokeObjectURL(url);
    } catch {
      toast.error('No se pudo generar el PDF.');
    }
  };

  // Deshacer solo se ofrece si de verdad deshace. En un binario la versión guarda el
  // texto extraído y no el archivo, así que el botón prometería algo que no cumple.
  const sePuedeDeshacer = cambios && !cambios.primera && cambios.reversible;

  return (
    <Box sx={{
      width: { xs: '100%', md: 460 }, flexShrink: 0, height: '100%',
      borderLeft: `1px solid ${theme.palette.divider}`,
      bgcolor: d ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.012)',
      display: 'flex', flexDirection: 'column',
    }}>
      <Box sx={{
        display: 'flex', alignItems: 'center', gap: 1, px: 2, py: 1.5,
        borderBottom: `1px solid ${theme.palette.divider}`,
      }}>
        <FileText size={16} color="#7B8AE0" />
        <Typography sx={{
          fontFamily: DISPLAY, fontWeight: 700, fontSize: '0.92rem', flex: 1, minWidth: 0,
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        }}>
          {doc?.title || 'Documento'}
        </Typography>
        {doc?.editable && (
          <Tooltip title="Descargar en PDF">
            <IconButton size="small" onClick={descargarPdf} sx={{ color: 'text.disabled' }}>
              <Download size={15} />
            </IconButton>
          </Tooltip>
        )}
        <Tooltip title="Abrir en Archivos, con todo el historial">
          <IconButton
            size="small" component="a" href={`/app/archivos/${docId}`} target="_blank"
            sx={{ color: 'text.disabled' }}
          >
            <ExternalLink size={15} />
          </IconButton>
        </Tooltip>
        <IconButton size="small" onClick={onCerrar} sx={{ color: 'text.disabled' }}>
          <X size={15} />
        </IconButton>
      </Box>

      {/* La salida, arriba y no escondida al final: es lo que convierte al documento en
          algo que sale de Afable y llega a alguien. */}
      <Box sx={{
        px: 2, py: 1.25, borderBottom: `1px solid ${theme.palette.divider}`,
        display: 'flex', alignItems: 'center',
      }}>
        <Enviar docId={docId} workspace={workspace} titulo={doc?.title || 'Documento'} />
      </Box>

      <Box sx={{ flex: 1, overflowY: 'auto', p: 2 }}>
        {cargando ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
            <CircularProgress size={22} />
          </Box>
        ) : (
          <>
            {cambios && !cambios.primera && (
              <>
                <Box sx={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  mb: 1,
                }}>
                  <Typography sx={{
                    fontSize: '0.7rem', fontWeight: 700, letterSpacing: '0.06em',
                    textTransform: 'uppercase', color: 'text.disabled',
                  }}>
                    Qué cambió · v{cambios.numero}
                  </Typography>
                  {sePuedeDeshacer && (
                    <Button
                      size="small" onClick={deshacer} disabled={deshaciendo}
                      startIcon={<RotateCcw size={13} />}
                      sx={{ textTransform: 'none', fontSize: '0.75rem', color: 'text.secondary' }}
                    >
                      Deshacer
                    </Button>
                  )}
                </Box>
                <Cambios lineas={cambios.lineas} />
                {cambios && !cambios.reversible && (
                  // Se dice, no se esconde: el archivo real ya cambió y la versión solo
                  // guarda su texto. Quien lo sepa puede pedir el archivo original a
                  // quien lo subió; quien no, lo descubre tarde.
                  <Typography sx={{ fontSize: '0.73rem', color: 'text.disabled', mb: 2 }}>
                    El cambio está hecho sobre el archivo. El historial guarda el texto
                    para que se pueda comparar, pero no devuelve el archivo anterior.
                  </Typography>
                )}
              </>
            )}

            <Typography sx={{
              fontSize: '0.7rem', fontWeight: 700, letterSpacing: '0.06em',
              textTransform: 'uppercase', color: 'text.disabled', mb: 1,
            }}>
              Documento
            </Typography>
            {doc?.editable ? (
              <Typography sx={{
                whiteSpace: 'pre-wrap', fontSize: '0.86rem', lineHeight: 1.7,
              }}>
                {doc.contenido || ''}
              </Typography>
            ) : (
              <VistaDelArchivo documentoId={docId} workspaceSlug={workspace} />
            )}
          </>
        )}
      </Box>
    </Box>
  );
}
