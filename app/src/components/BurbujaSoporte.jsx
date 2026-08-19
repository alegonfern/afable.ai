import { useState } from 'react';
import { Box, Button, IconButton, TextField, Typography, useTheme } from '@mui/material';
import { useLocation } from 'react-router-dom';
import { LifeBuoy, Send, X } from 'lucide-react';
import { api } from '../services/api';
import { erroresRecientes } from '../services/erroresRecientes';
import { useApp } from '../context/AppContext';
import { useWorkspace } from '../context/WorkspaceContext';

/**
 * Escribirle a soporte sin salir de donde se está.
 *
 * **Es un formulario, no un chat**, y se nota a propósito: dice que la respuesta llega
 * por correo. Una burbuja que promete conversación y contesta tres horas después deja
 * peor parado que un formulario que cumple lo que dice.
 *
 * Pero va en la esquina, como una burbuja, y no en una pantalla aparte: se escribe a
 * soporte justo cuando algo se rompió, y mandar a la persona a otra pantalla le hace
 * perder lo que estaba haciendo — y a nosotros, el dato de dónde falló.
 *
 * El mensaje viaja con el contexto (pantalla, empresa, Workspace, modelo y los últimos
 * errores del navegador). Eso se ARMA ACÁ y no se le pide a la persona: quien está
 * atascado no tiene por qué saber en qué ruta está.
 */
export default function BurbujaSoporte() {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const location = useLocation();
  const { currentUser } = useApp();
  const { workspace, espacio } = useWorkspace();

  const [abierta, setAbierta] = useState(false);
  const [texto, setTexto] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [listo, setListo] = useState(false);
  const [error, setError] = useState('');

  const borde = theme.palette.divider;
  const textMuted = d ? 'rgba(255,255,255,0.66)' : 'rgba(0,0,0,0.62)';

  const cerrar = () => {
    setAbierta(false);
    // El estado se limpia al cerrar, no al enviar: así el acuse queda a la vista el
    // tiempo que la persona quiera leerlo.
    setTimeout(() => { setListo(false); setTexto(''); setError(''); }, 200);
  };

  const enviar = async () => {
    const mensaje = texto.trim();
    if (!mensaje) return;
    try {
      setEnviando(true);
      setError('');
      await api.enviarMensajeSoporte({
        texto: mensaje,
        contexto: {
          ruta: location.pathname + location.search,
          empresa: workspace?.name || null,
          workspace: espacio?.name || null,
          modelo: localStorage.getItem('afable_modelo') || null,
          errores: erroresRecientes(),
          navegador: navigator.userAgent,
        },
      });
      setListo(true);
    } catch (e) {
      setError(e.response?.data?.detail || 'No se pudo enviar. Intente de nuevo.');
    } finally {
      setEnviando(false);
    }
  };

  if (!abierta) {
    return (
      <IconButton
        onClick={() => setAbierta(true)}
        title="Escribir a soporte"
        sx={{
          position: 'fixed', right: 20, bottom: 20, zIndex: 1200,
          width: 44, height: 44, bgcolor: '#586AD0', color: '#fff',
          boxShadow: '0 4px 14px rgba(0,0,0,0.25)',
          '&:hover': { bgcolor: '#2F42A6' },
        }}
      >
        <LifeBuoy size={20} />
      </IconButton>
    );
  }

  return (
    <Box
      sx={{
        position: 'fixed', right: 20, bottom: 20, zIndex: 1200,
        width: { xs: 'calc(100vw - 40px)', sm: 348 },
        border: `1px solid ${borde}`, borderRadius: '12px',
        bgcolor: theme.palette.background.paper,
        boxShadow: '0 12px 32px rgba(0,0,0,0.28)',
        overflow: 'hidden',
      }}
    >
      <Box sx={{
        display: 'flex', alignItems: 'center', gap: 1, px: 2, py: 1.5,
        borderBottom: `1px solid ${borde}`,
      }}>
        <LifeBuoy size={16} color="#586AD0" />
        <Typography sx={{ flex: 1, fontSize: '0.9375rem', fontWeight: 600 }}>Soporte</Typography>
        <IconButton size="small" onClick={cerrar} sx={{ color: textMuted }}>
          <X size={15} />
        </IconButton>
      </Box>

      <Box sx={{ px: 2, py: 2 }}>
        {listo ? (
          <>
            <Typography sx={{ fontSize: '0.9375rem', fontWeight: 600, mb: 0.75 }}>
              Recibido.
            </Typography>
            <Typography sx={{ fontSize: '0.875rem', color: textMuted }}>
              Le respondemos a <b>{currentUser?.email}</b> dentro del día hábil. Nos llegó
              con la pantalla en la que estaba, así que no hace falta que explique dónde fue.
            </Typography>
            <Button onClick={cerrar} sx={{ mt: 1.5, textTransform: 'none' }} size="small">
              Cerrar
            </Button>
          </>
        ) : (
          <>
            <Typography sx={{ fontSize: '0.875rem', color: textMuted, mb: 1.5 }}>
              Cuéntenos qué pasó. Le respondemos por correo — esto no es un chat en vivo.
            </Typography>
            <TextField
              value={texto}
              onChange={(e) => setTexto(e.target.value)}
              placeholder="No puedo subir un archivo, me dice que…"
              multiline minRows={4} maxRows={9} fullWidth autoFocus
              inputProps={{ maxLength: 4000 }}
              sx={{ '& .MuiOutlinedInput-root': { fontSize: '0.875rem', borderRadius: '8px' } }}
            />
            {error && (
              <Typography sx={{ fontSize: '0.8125rem', color: 'error.main', mt: 1 }}>{error}</Typography>
            )}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 1.5 }}>
              <Typography sx={{ fontSize: '0.75rem', color: textMuted, flex: 1 }}>
                Se envía con la pantalla y el error, si hubo.
              </Typography>
              <Button
                variant="contained" size="small" disabled={!texto.trim() || enviando}
                onClick={enviar} startIcon={<Send size={14} />}
                sx={{ textTransform: 'none' }}
              >
                {enviando ? 'Enviando...' : 'Enviar'}
              </Button>
            </Box>
          </>
        )}
      </Box>
    </Box>
  );
}
