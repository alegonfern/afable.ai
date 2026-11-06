import { useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Box, useTheme } from '@mui/material';
import { VISTAS, guardarVista, moduloDeRuta, rutaDe } from '../modulos';

/**
 * Módulo / Automatización, centrado en el encabezado como el "Chat | Activity" de Kapso.
 *
 * Solo aparece dentro de un módulo: en el chat o en el perfil no hay nada que alternar.
 * El estado lo da la URL —cada vista es su propia página— y la última elegida se guarda
 * para que la barra lateral lleve a la misma vista en el otro módulo.
 */
export default function SelectorVista() {
  const theme = useTheme();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const d = theme.palette.mode === 'dark';
  const actual = moduloDeRuta(pathname);

  // Si se llegó por un enlace, lo recordado pasa a ser lo que se está viendo.
  useEffect(() => { if (actual) guardarVista(actual.vista); }, [actual?.vista]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!actual) return null;

  return (
    <Box
      role="tablist"
      aria-label={`Vista de ${actual.label}`}
      sx={{
        // Centrado sobre la barra en pantallas anchas; en el teléfono va en la fila, entre los
        // íconos, para no montarse sobre ellos.
        position: { xs: 'static', md: 'absolute' }, left: { md: '50%' }, transform: { md: 'translateX(-50%)' },
        mx: { xs: 'auto', md: 0 }, flexShrink: 0,
        display: 'flex', gap: '2px', p: '3px', borderRadius: '9px',
        bgcolor: d ? 'rgba(255,255,255,0.06)' : 'rgba(11,11,15,0.05)',
        border: `1px solid ${theme.palette.divider}`,
      }}
    >
      {VISTAS.map((v) => {
        const activa = actual.vista === v.key;
        return (
          <Box
            key={v.key}
            component="button"
            role="tab"
            aria-selected={activa}
            onClick={() => {
              if (activa) return;
              guardarVista(v.key);
              navigate(rutaDe(actual.slug, v.key));
            }}
            sx={{
              px: { xs: 1, sm: 1.75 }, py: 0.5, border: 'none', borderRadius: '7px', cursor: activa ? 'default' : 'pointer',
              fontFamily: 'inherit', fontSize: { xs: '0.75rem', sm: '0.8125rem' }, fontWeight: 500, letterSpacing: '-0.01em', whiteSpace: 'nowrap',
              color: activa ? 'text.primary' : 'text.secondary',
              bgcolor: activa ? (d ? 'rgba(255,255,255,0.1)' : '#fff') : 'transparent',
              boxShadow: activa && !d ? '0 1px 2px rgba(11,11,15,0.08), 0 0 0 1px rgba(11,11,15,0.04)' : 'none',
              '&:hover': { color: 'text.primary' },
              '&:focus-visible': { outline: '2px solid var(--af-color)', outlineOffset: '1px' },
              transition: 'all 0.12s',
            }}
          >
            {v.label}
          </Box>
        );
      })}
    </Box>
  );
}
