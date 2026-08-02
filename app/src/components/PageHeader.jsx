import { Box, Typography, IconButton, Tooltip, useTheme } from '@mui/material';
import { ChevronLeft } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

/**
 * Encabezado estándar para páginas internas.
 * Muestra breadcrumb, título y acciones opcionales.
 *
 * @param {string}   title       — título de la página
 * @param {string}   back        — ruta a la que navega ← (default: -1 en historial)
 * @param {string}   backLabel   — texto del breadcrumb padre
 * @param {ReactNode} actions    — botones / controles a la derecha
 */
export default function PageHeader({ title, back, backLabel = 'Inicio', actions }) {
  const theme = useTheme();
  const navigate = useNavigate();
  const d = theme.palette.mode === 'dark';

  const handleBack = () => {
    if (back) navigate(back);
    else navigate(-1);
  };

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 1.5,
        px: 3,
        pt: 2.25,
        pb: 2,
        borderBottom: `1px solid ${theme.palette.divider}`,
        bgcolor: 'background.default',
        flexShrink: 0,
      }}
    >
      {/* Back button */}
      <Tooltip title={`Volver a ${backLabel}`} arrow>
        <IconButton
          size="small"
          onClick={handleBack}
          sx={{
            color: d ? 'rgba(255,255,255,0.4)' : 'rgba(0,0,0,0.4)',
            border: `1px solid ${theme.palette.divider}`,
            borderRadius: '6px',
            width: 28,
            height: 28,
            '&:hover': {
              color: theme.palette.text.primary,
              bgcolor: theme.palette.action.hover,
              borderColor: d ? 'rgba(255,255,255,0.15)' : 'rgba(0,0,0,0.15)',
            },
            transition: 'all 0.12s',
          }}
        >
          <ChevronLeft size={16} />
        </IconButton>
      </Tooltip>

      {/* Breadcrumb */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, flex: 1, minWidth: 0 }}>
        <Typography
          onClick={handleBack}
          sx={{
            fontSize: '0.8125rem',
            color: d ? 'rgba(255,255,255,0.35)' : 'rgba(0,0,0,0.35)',
            cursor: 'pointer',
            '&:hover': { color: theme.palette.text.secondary },
            transition: 'color 0.12s',
            whiteSpace: 'nowrap',
          }}
        >
          {backLabel}
        </Typography>
        <Typography sx={{ fontSize: '0.8125rem', color: d ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.2)' }}>
          /
        </Typography>
        <Typography
          sx={{
            fontSize: '0.9375rem',
            fontWeight: 600,
            color: theme.palette.text.primary,
            letterSpacing: '-0.01em',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {title}
        </Typography>
      </Box>

      {/* Right actions */}
      {actions && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexShrink: 0 }}>
          {actions}
        </Box>
      )}
    </Box>
  );
}
