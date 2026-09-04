import { useCallback, useEffect, useState } from 'react';
import { Box, Button, CircularProgress, TextField, Typography, useTheme } from '@mui/material';
import { Sparkles, X } from 'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../services/api';
import { useWorkspace } from '../context/WorkspaceContext';

/**
 * Los agentes que Afable propone, arriba de la galería.
 *
 * Reemplaza a la pregunta que el usuario no técnico no puede contestar —«¿qué
 * instrucciones le doy a su agente?»— por una que sí: «¿le sirve este?».
 *
 * El recorrido es de dos pasos a propósito. Primero se listan las carpetas que ya tienen
 * material, que es barato; recién cuando la persona elige una se le pide a Afable que
 * redacte, que cuesta una llamada al modelo. Si redactara las seis de entrada, abrir esta
 * pantalla costaría seis llamadas antes de que mirara ninguna.
 *
 * **No se dibuja si no hay carpetas listas.** Un panel que dice «todavía no hay nada que
 * proponerte» es ruido permanente en la pantalla que más se usa.
 */
export default function PropuestasDeAgente({ onCreado }) {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const { slug } = useWorkspace();

  const [carpetas, setCarpetas] = useState([]);
  const [abierta, setAbierta] = useState(null);      // la carpeta que se está mirando
  const [borrador, setBorrador] = useState(null);
  const [redactando, setRedactando] = useState(false);
  const [creando, setCreando] = useState(false);

  const textMuted = d ? 'rgba(255,255,255,0.66)' : 'rgba(0,0,0,0.62)';
  const bgSuave = d ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.015)';

  const cargar = useCallback(async () => {
    if (!slug) return;
    try {
      const { data } = await api.getPropuestasDeAgente(slug);
      setCarpetas(data.carpetas || []);
    } catch {
      // Silencio a propósito: es un panel de sugerencias. Si falla, la galería de
      // abajo sigue sirviendo y no vale la pena un error en la cara.
      setCarpetas([]);
    }
  }, [slug]);

  useEffect(() => { cargar(); }, [cargar]);

  const abrir = async (carpeta) => {
    setAbierta(carpeta);
    setBorrador(null);
    setRedactando(true);
    try {
      const { data } = await api.redactarPropuestaDeAgente(slug, carpeta.id);
      setBorrador(data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'No pude preparar la propuesta.');
      setAbierta(null);
    } finally {
      setRedactando(false);
    }
  };

  const aceptar = async () => {
    setCreando(true);
    try {
      const { data } = await api.aceptarPropuestaDeAgente({
        workspace: slug,
        carpeta: abierta.id,
        nombre: borrador.nombre,
        descripcion: borrador.descripcion,
        instrucciones: borrador.instrucciones,
        icono: borrador.icono,
      });
      toast.success(`${data.nombre} ya está trabajando sobre ${data.carpeta}.`);
      setAbierta(null);
      setBorrador(null);
      cargar();
      onCreado?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'No pude crear el agente.');
    } finally {
      setCreando(false);
    }
  };

  if (!carpetas.length) return null;

  return (
    <Box sx={{
      mb: 3, p: 2.25, borderRadius: '10px',
      border: `1px solid ${theme.palette.divider}`, bgcolor: bgSuave,
    }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
        <Sparkles size={15} color="#586AD0" />
        <Typography sx={{ fontSize: '0.9rem', fontWeight: 600, color: 'text.primary' }}>
          {abierta ? `Un agente para ${abierta.nombre}` : 'Estas carpetas ya pueden tener agente'}
        </Typography>
      </Box>

      {!abierta && (
        <>
          <Typography sx={{ fontSize: '0.83rem', color: textMuted, mb: 1.5 }}>
            Tienen documentos suficientes para que un agente responda sobre ellas.
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
            {carpetas.map((c) => (
              <Box
                key={c.id}
                component="button"
                onClick={() => abrir(c)}
                sx={{
                  display: 'flex', alignItems: 'baseline', gap: 0.75,
                  px: 1.5, py: 0.85, borderRadius: '8px', cursor: 'pointer',
                  fontFamily: 'inherit', fontSize: '0.875rem', color: 'text.primary',
                  bgcolor: 'transparent', border: `1px solid ${theme.palette.divider}`,
                  '&:hover': { borderColor: '#586AD0' }, transition: 'border-color 0.12s',
                }}
              >
                {c.nombre}
                <Typography component="span" sx={{ fontSize: '0.78rem', color: textMuted }}>
                  {c.documentos} documentos
                </Typography>
              </Box>
            ))}
          </Box>
        </>
      )}

      {abierta && redactando && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25, py: 1.5 }}>
          <CircularProgress size={15} />
          <Typography sx={{ fontSize: '0.85rem', color: textMuted }}>
            Mirando lo que hay en la carpeta…
          </Typography>
        </Box>
      )}

      {abierta && borrador && !redactando && (
        <Box sx={{ mt: 1.5 }}>
          <Typography sx={{ fontSize: '0.83rem', color: textMuted, mb: 1.5 }}>
            Esto es lo que le propongo. Cámbielo si quiere antes de crearlo.
          </Typography>

          <TextField
            label="Nombre" value={borrador.nombre} size="small" fullWidth
            onChange={(e) => setBorrador({ ...borrador, nombre: e.target.value })}
            sx={{ mb: 1.25 }}
          />
          <TextField
            label="Qué responde" value={borrador.descripcion} size="small" fullWidth
            onChange={(e) => setBorrador({ ...borrador, descripcion: e.target.value })}
            sx={{ mb: 1.25 }}
          />
          <TextField
            label="Cómo debe trabajar" value={borrador.instrucciones}
            size="small" fullWidth multiline minRows={2}
            onChange={(e) => setBorrador({ ...borrador, instrucciones: e.target.value })}
            sx={{ mb: 1.5 }}
          />

          <Box sx={{ display: 'flex', gap: 1 }}>
            <Button
              onClick={aceptar}
              disabled={creando || !borrador.nombre?.trim()}
              sx={{
                textTransform: 'none', bgcolor: '#586AD0', color: '#fff',
                px: 2, '&:hover': { bgcolor: '#4757b8' },
              }}
            >
              {creando ? 'Creando…' : 'Crear este agente'}
            </Button>
            <Button
              onClick={() => { setAbierta(null); setBorrador(null); }}
              startIcon={<X size={14} />}
              sx={{ textTransform: 'none', color: textMuted }}
            >
              Ahora no
            </Button>
          </Box>
        </Box>
      )}
    </Box>
  );
}
