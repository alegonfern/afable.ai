import { useCallback, useEffect, useState } from 'react';
import { Box, Collapse, IconButton, LinearProgress, Tooltip, Typography, useTheme } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { Check, ChevronDown, ChevronRight, X } from 'lucide-react';
import { api } from '../services/api';
import { useWorkspace } from '../context/WorkspaceContext';

/**
 * La primera hora: lo que le falta a la empresa, arriba en la home.
 *
 * Va acá y no en una pantalla propia porque una pantalla de bienvenida se cierra y no se
 * vuelve a abrir nunca. Los pasos toman más de una sesión —conectar un sistema puede
 * necesitar a otra persona— así que tienen que seguir a la vista al volver.
 *
 * Se dibuja sólo si: es administrador, no lo cerró, y falta algo. Cuando termina, se va
 * solo: un panel de bienvenida que sigue ahí para siempre es ruido en la pantalla que
 * más se usa.
 *
 * **El primer paso pendiente va abierto y los demás plegados.** Seis tarjetas
 * desplegadas empujan el compositor fuera de la pantalla, que es lo que la persona vino
 * a usar.
 */
export default function PrimerosPasos() {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const navigate = useNavigate();
  const { slug, esAdmin } = useWorkspace();

  const textMuted = d ? 'rgba(255,255,255,0.66)' : 'rgba(0,0,0,0.62)';
  const bgCaja = d ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.015)';
  const borde = theme.palette.divider;

  const [datos, setDatos] = useState(null);
  const [abierto, setAbierto] = useState(true);
  const [cargandoEjemplo, setCargandoEjemplo] = useState(false);

  const cargar = useCallback(async () => {
    if (!slug || !esAdmin) return;
    try {
      const { data } = await api.getPrimerosPasos(slug);
      setDatos(data);
    } catch {
      // Si no se puede leer, no se dibuja nada: es un panel de ayuda, no puede ser el
      // que arruine la home con un cartel de error.
      setDatos(null);
    }
  }, [slug, esAdmin]);

  useEffect(() => { cargar(); }, [cargar]);

  const cargarEjemplo = async () => {
    if (cargandoEjemplo) return;
    try {
      setCargandoEjemplo(true);
      const { data } = await api.cargarDatosDeEjemplo(slug);
      // Se va derecho al chat con la primera pregunta escrita: quien recién llega no
      // tiene que inventar qué preguntar, que es justo donde la gente se traba.
      navigate('/app/chat', { state: { initialMessage: data.preguntas?.[0] } });
    } catch {
      setCargandoEjemplo(false);
    }
  };

  const cerrar = async () => {
    setDatos(null);
    try {
      await api.ocultarPrimerosPasos(slug);
    } catch {
      cargar();
    }
  };

  if (!datos || datos.oculto || datos.terminado) return null;

  const { pasos, hechos, total } = datos;
  const primerPendiente = pasos.find((p) => !p.hecho);

  return (
    <Box
      sx={{
        border: `1px solid ${borde}`, borderRadius: '12px', bgcolor: bgCaja,
        px: 2.25, py: 1.75, mb: 3,
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
        <Box
          onClick={() => setAbierto((v) => !v)}
          sx={{ flex: 1, minWidth: 0, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 1 }}
        >
          {abierto ? <ChevronDown size={16} color={textMuted} /> : <ChevronRight size={16} color={textMuted} />}
          <Typography sx={{ fontSize: '0.9375rem', fontWeight: 600 }}>
            Para que Afable le sirva de verdad
          </Typography>
          <Typography sx={{ fontSize: '0.8125rem', color: textMuted }}>
            {hechos} de {total}
          </Typography>
        </Box>
        <Tooltip title="No mostrar más" arrow>
          <IconButton size="small" onClick={cerrar} sx={{ color: textMuted }}>
            <X size={15} />
          </IconButton>
        </Tooltip>
      </Box>

      <LinearProgress
        variant="determinate"
        value={(hechos / total) * 100}
        sx={{
          mt: 1.5, height: 4, borderRadius: 2,
          bgcolor: d ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)',
          '& .MuiLinearProgress-bar': { bgcolor: '#586AD0', borderRadius: 2 },
        }}
      />

      <Collapse in={abierto}>
        <Box sx={{ mt: 2, display: 'flex', flexDirection: 'column', gap: 0.25 }}>
          {pasos.map((paso) => {
            const destacado = paso.id === primerPendiente?.id;
            return (
              <Box
                key={paso.id}
                onClick={() => !paso.hecho && navigate(paso.ruta)}
                sx={{
                  display: 'flex', gap: 1.5, alignItems: 'flex-start',
                  px: 1.25, py: 1, borderRadius: '8px',
                  cursor: paso.hecho ? 'default' : 'pointer',
                  bgcolor: destacado ? (d ? 'rgba(88,106,208,0.10)' : 'rgba(88,106,208,0.06)') : 'transparent',
                  '&:hover': paso.hecho ? {} : { bgcolor: d ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.03)' },
                  transition: 'background-color .12s',
                }}
              >
                {/* La marca de hecho tiene que leerse de un vistazo: es lo único que se
                    mira al volver a la pantalla. */}
                <Box
                  sx={{
                    mt: '2px', width: 17, height: 17, borderRadius: '50%', flexShrink: 0,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    bgcolor: paso.hecho ? '#586AD0' : 'transparent',
                    border: paso.hecho ? 'none' : `1.5px solid ${d ? 'rgba(255,255,255,0.25)' : 'rgba(0,0,0,0.2)'}`,
                  }}
                >
                  {paso.hecho && <Check size={11} color="#fff" strokeWidth={3} />}
                </Box>

                <Box sx={{ flex: 1, minWidth: 0 }}>
                  <Typography
                    sx={{
                      fontSize: '0.875rem',
                      fontWeight: destacado ? 600 : 500,
                      color: paso.hecho ? textMuted : theme.palette.text.primary,
                      textDecoration: paso.hecho ? 'line-through' : 'none',
                    }}
                  >
                    {paso.titulo}
                  </Typography>
                  {/* La explicación sólo en el que toca: en los demás es texto que nadie
                      lee y que hace la lista tres veces más alta. */}
                  {destacado && (
                    <Typography sx={{ fontSize: '0.8125rem', color: textMuted, mt: 0.35 }}>
                      {paso.ayuda}
                    </Typography>
                  )}
                  {/* El paso que más cuesta es traer los datos, y es el que traba a la
                      mayoría: sin ellos el agente contesta como cualquier IA gratuita y
                      nadie llega a ver de qué se trata. Con la empresa de ejemplo se
                      puede preguntar antes de cargar nada. */}
                  {!paso.hecho && paso.id === 'conocimiento' && (
                    <Typography
                      onClick={(e) => { e.stopPropagation(); cargarEjemplo(); }}
                      sx={{
                        fontSize: '0.8125rem', fontWeight: 600, color: '#586AD0',
                        mt: 0.75, cursor: 'pointer', '&:hover': { textDecoration: 'underline' },
                      }}
                    >
                      {cargandoEjemplo
                        ? 'Preparando la empresa de ejemplo...'
                        : '…o pruébelo primero con una empresa de ejemplo →'}
                    </Typography>
                  )}
                  {paso.detalle && paso.hecho && (
                    <Typography sx={{ fontSize: '0.75rem', color: textMuted, mt: 0.25 }}>
                      {paso.detalle}
                    </Typography>
                  )}
                </Box>

                {!paso.hecho && (
                  <Typography
                    sx={{
                      fontSize: '0.8125rem', fontWeight: 600, color: '#586AD0',
                      flexShrink: 0, whiteSpace: 'nowrap',
                    }}
                  >
                    {paso.accion} →
                  </Typography>
                )}
              </Box>
            );
          })}
        </Box>
      </Collapse>
    </Box>
  );
}
