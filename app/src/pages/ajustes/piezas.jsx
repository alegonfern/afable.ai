import { Box, Button, CircularProgress, Typography } from '@mui/material';

/*
 * Las piezas de Configuración (28-10-2026), al estilo de Vercel y Linear: cada página tiene un
 * título con su explicación y, debajo, tarjetas. Cada tarjeta dice qué es y para qué sirve, y su
 * pie lleva la ayuda a la izquierda y la acción a la derecha. Así todas las pantallas de
 * Configuración se leen igual, vengan de donde vengan.
 */

export const ANCHO_PAGINA = 880;

/* El campo de texto de Configuración (TextField de MUI). */
export const campoSx = {
  '& .MuiOutlinedInput-root': {
    borderRadius: '8px', fontSize: '0.875rem', bgcolor: 'background.paper',
    '& fieldset': { borderColor: 'divider' },
    '&.Mui-focused fieldset': { borderColor: 'var(--af-acento)', borderWidth: 1 },
  },
  '& .MuiInputLabel-root': { fontSize: '0.875rem' },
  '& .MuiInputLabel-root.Mui-focused': { color: 'var(--af-acento)' },
};

export function Pagina({ titulo, descripcion, accion, ancho = ANCHO_PAGINA, children }) {
  return (
    <Box sx={{ maxWidth: ancho, width: '100%', mx: 'auto' }}>
      <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2, mb: 3.5, flexDirection: { xs: 'column', sm: 'row' } }}>
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography component="h1" sx={{ fontFamily: "'Sora', 'Inter', sans-serif", fontSize: '1.5rem', fontWeight: 600, letterSpacing: '-0.015em' }}>
            {titulo}
          </Typography>
          {descripcion && (
            <Typography sx={{ color: 'text.secondary', fontSize: '0.9rem', mt: 0.75, lineHeight: 1.55, maxWidth: 620 }}>
              {descripcion}
            </Typography>
          )}
        </Box>
        {accion}
      </Box>
      <Box sx={{ display: 'grid', gap: 2.5 }}>{children}</Box>
    </Box>
  );
}

export function Tarjeta({ titulo, descripcion, pie, accion, peligro = false, sinRelleno = false, children }) {
  return (
    <Box component="section" sx={{
      border: '1px solid', borderColor: peligro ? 'color-mix(in srgb, #dc2626 35%, transparent)' : 'divider',
      borderRadius: '12px', bgcolor: 'background.paper', overflow: 'hidden',
    }}>
      {(titulo || descripcion) && (
        <Box sx={{ px: { xs: 2, sm: 3 }, pt: 2.75, pb: children ? 0 : 2.75 }}>
          {titulo && <Typography component="h2" sx={{ fontWeight: 600, fontSize: '1rem' }}>{titulo}</Typography>}
          {descripcion && (
            <Typography sx={{ color: 'text.secondary', fontSize: '0.86rem', mt: 0.5, lineHeight: 1.55 }}>{descripcion}</Typography>
          )}
        </Box>
      )}
      {children && <Box sx={sinRelleno ? { mt: titulo ? 2 : 0 } : { px: { xs: 2, sm: 3 }, pt: titulo || descripcion ? 2.25 : 2.75, pb: 2.75 }}>{children}</Box>}
      {(pie || accion) && (
        <Box sx={{
          display: 'flex', alignItems: 'center', gap: 2, px: { xs: 2, sm: 3 }, py: 1.5, minHeight: 56,
          borderTop: '1px solid', borderColor: peligro ? 'color-mix(in srgb, #dc2626 25%, transparent)' : 'divider',
          bgcolor: peligro ? 'color-mix(in srgb, #dc2626 4%, transparent)' : 'action.hover',
        }}>
          <Typography component="div" sx={{ flex: 1, fontSize: '0.8rem', color: 'text.secondary', lineHeight: 1.5 }}>{pie}</Typography>
          {accion}
        </Box>
      )}
    </Box>
  );
}

/* Una fila de opción: el rótulo y su ayuda a la izquierda, el control a la derecha. */
export function Fila({ etiqueta, ayuda, children, primera = false }) {
  return (
    <Box sx={{
      display: 'flex', alignItems: { xs: 'flex-start', sm: 'center' }, flexDirection: { xs: 'column', sm: 'row' },
      gap: { xs: 1, sm: 3 }, py: 1.75, borderTop: primera ? 'none' : '1px solid', borderColor: 'divider',
      '&:first-of-type': { borderTop: 'none', pt: 0 }, '&:last-of-type': { pb: 0 },
    }}>
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Typography sx={{ fontSize: '0.875rem', fontWeight: 500 }}>{etiqueta}</Typography>
        {ayuda && <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary', mt: 0.25, lineHeight: 1.5 }}>{ayuda}</Typography>}
      </Box>
      <Box sx={{ flexShrink: 0, maxWidth: '100%' }}>{children}</Box>
    </Box>
  );
}

export function BotonGuardar({ guardando, cambios = true, onClick, children = 'Guardar' }) {
  return (
    <Button variant="contained" size="small" disableElevation onClick={onClick} disabled={guardando || !cambios}
      sx={{ borderRadius: '8px', textTransform: 'none', fontWeight: 600, px: 2, minWidth: 92 }}>
      {guardando ? <CircularProgress size={14} sx={{ color: 'inherit' }} /> : children}
    </Button>
  );
}

export function Cargando() {
  return <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}><CircularProgress size={22} /></Box>;
}

/* "Listo" en verde o "Falta…" en ámbar, con su punto. */
export function Estado({ ok, children }) {
  return (
    <Box component="span" sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.75, fontWeight: 500, color: ok ? '#0f9d6b' : '#b45309' }}>
      <Box component="span" sx={{ width: 7, height: 7, borderRadius: '50%', bgcolor: 'currentColor', flexShrink: 0 }} />
      {children}
    </Box>
  );
}
