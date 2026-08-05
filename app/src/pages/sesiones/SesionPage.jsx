import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { Box, CircularProgress, Tooltip, Typography, useTheme } from '@mui/material';
import { ArrowLeft, CheckCircle2, FolderOpen, MessageSquare, Settings } from 'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../../services/api';
import { useWorkspace } from '../../context/WorkspaceContext';
import SesionTareas from './SesionTareas';
import SesionArchivos from './SesionArchivos';
import SesionAjustes from './SesionAjustes';

const DISPLAY = `'Sora', 'Inter', sans-serif`;

// Las pestañas van en icono y solo la activa muestra su etiqueta — el mismo patrón
// que el conmutador de modos de la barra lateral.
const PESTANAS = [
  { value: 'tareas',    label: 'Tareas',    icon: CheckCircle2 },
  { value: 'archivos',  label: 'Archivos',  icon: FolderOpen },
  { value: 'ajustes',   label: 'Ajustes',   icon: Settings },
];

/**
 * Una Sesión: donde el equipo y sus agentes trabajan sobre algo concreto.
 *
 * La pestaña de Conversación llega en el paso siguiente; mientras no exista de verdad
 * no se dibuja, porque una pestaña que no lleva a nada es peor que una pestaña menos.
 *
 * El `?tab=` es la fuente de verdad y no un estado local: así el enlace a una pestaña
 * se puede compartir y recargar la página no devuelve a la primera.
 */
export default function SesionPage() {
  const { sesionSlug } = useParams();
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const navigate = useNavigate();
  const { slug } = useWorkspace();
  const [searchParams, setSearchParams] = useSearchParams();

  const textMuted = d ? 'rgba(255,255,255,0.66)' : 'rgba(0,0,0,0.62)';
  const bgSuave = d ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.02)';
  const borde = theme.palette.divider;

  const [sesion, setSesion] = useState(null);
  const [cargando, setCargando] = useState(true);

  const pedida = searchParams.get('tab');
  const tab = PESTANAS.some((p) => p.value === pedida) ? pedida : 'tareas';

  const cargar = useCallback(async () => {
    if (!slug || !sesionSlug) return;
    try {
      setCargando(true);
      const { data } = await api.getSesion(sesionSlug, slug);
      setSesion(data);
    } catch {
      toast.error('Esta Sesión no existe o no tiene acceso.');
      navigate('/app');
    } finally {
      setCargando(false);
    }
  }, [slug, sesionSlug, navigate]);

  useEffect(() => { cargar(); }, [cargar]);

  if (cargando) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', pt: 12 }}>
        <CircularProgress size={26} sx={{ color: '#586AD0' }} />
      </Box>
    );
  }
  if (!sesion) return null;

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100%' }}>
      {/* Barra de pestañas, arriba, como en el cuadro de referencia */}
      <Box sx={{
        display: 'flex', alignItems: 'center', gap: 0.5,
        px: { xs: 1.5, sm: 2.5 }, py: 1.25, borderBottom: `1px solid ${borde}`,
      }}>
        <Box
          component="button"
          onClick={() => navigate('/app')}
          title="Volver"
          sx={{
            display: 'flex', alignItems: 'center', border: 'none', bgcolor: 'transparent',
            p: 0.75, mr: 0.5, borderRadius: '7px', cursor: 'pointer', color: textMuted,
            '&:hover': { bgcolor: bgSuave },
          }}
        >
          <ArrowLeft size={16} />
        </Box>

        {PESTANAS.map((p) => {
          const activa = tab === p.value;
          const Icono = p.icon;
          return (
            <Tooltip key={p.value} title={activa ? '' : p.label} placement="bottom">
              <Box
                component="button"
                onClick={() => setSearchParams({ tab: p.value }, { replace: true })}
                sx={{
                  display: 'flex', alignItems: 'center', gap: 0.75,
                  border: 'none', cursor: 'pointer', fontFamily: 'inherit',
                  px: activa ? 1.5 : 1, py: 0.75, borderRadius: '8px',
                  fontSize: '0.875rem', fontWeight: 600,
                  bgcolor: activa ? (d ? 'rgba(255,255,255,0.09)' : 'rgba(0,0,0,0.06)') : 'transparent',
                  color: activa ? theme.palette.text.primary : textMuted,
                  '&:hover': { bgcolor: bgSuave, color: theme.palette.text.primary },
                }}
              >
                <Icono size={16} />
                {activa && p.label}
              </Box>
            </Tooltip>
          );
        })}
      </Box>

      {/* Encabezado de la Sesión */}
      <Box sx={{ px: { xs: 2.5, sm: 4 }, pt: 3.5, pb: 1 }}>
        <Typography sx={{
          fontFamily: DISPLAY, fontSize: '1.625rem', fontWeight: 600, letterSpacing: '-0.01em',
          display: 'flex', alignItems: 'center', gap: 1.25,
        }}>
          <span>{sesion.icon || '💠'}</span>
          {sesion.name}
        </Typography>
        {sesion.description && (
          <Typography sx={{ color: textMuted, fontSize: '0.9375rem', mt: 0.75, maxWidth: 700 }}>
            {sesion.description}
          </Typography>
        )}
        {sesion.archivada && (
          <Typography sx={{ fontSize: '0.8125rem', color: '#f0b429', mt: 1, fontWeight: 600 }}>
            Archivada — no aparece en la barra lateral, pero su contenido sigue acá.
          </Typography>
        )}
      </Box>

      {tab === 'tareas' && <SesionTareas sesion={sesion} slug={slug} />}
      {tab === 'archivos' && <SesionArchivos sesion={sesion} slug={slug} />}
      {tab === 'ajustes' && (
        <SesionAjustes sesion={sesion} slug={slug} onCambio={setSesion} onBorrada={() => navigate('/app')} />
      )}
    </Box>
  );
}
