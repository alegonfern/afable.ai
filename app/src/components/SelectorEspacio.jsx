import { useState } from 'react';
import { Box, Menu, MenuItem, Typography, useTheme } from '@mui/material';
import { ChevronDown, Layers } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useWorkspace } from '../context/WorkspaceContext';

/**
 * El Espacio en el que se está trabajando, dentro del compositor.
 *
 * Elegirlo hace dos cosas concretas: la vitrina ofrece solo los agentes de ese
 * Espacio, y las conversaciones nuevas quedan guardadas ahí, a la vista de quienes
 * pertenecen al Espacio. Sin Espacio elegido se ve todo lo que la persona alcanza,
 * que es como funcionaba antes de que los Espacios existieran.
 */
export default function SelectorEspacio() {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const navigate = useNavigate();
  const { espacios, espacio, seleccionarEspacio } = useWorkspace();
  const [ancla, setAncla] = useState(null);

  const textMuted = d ? 'rgba(255,255,255,0.66)' : 'rgba(0,0,0,0.62)';

  const elegir = (slug) => {
    seleccionarEspacio(slug);
    setAncla(null);
  };

  return (
    <>
      <Box
        onClick={(e) => setAncla(e.currentTarget)}
        title="Elegir en qué Workspace trabajar"
        sx={{
          display: 'flex', alignItems: 'center', gap: 0.6,
          px: 0.875, py: 0.4, borderRadius: '6px', cursor: 'pointer',
          color: espacio ? '#9BA6E3' : textMuted,
          fontSize: '0.8125rem', fontWeight: 500, maxWidth: 190,
          bgcolor: ancla ? (d ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.04)') : 'transparent',
          '&:hover': { bgcolor: d ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.04)' },
        }}
      >
        {espacio?.icon
          ? <Box component="span" sx={{ fontSize: '0.9rem', flexShrink: 0 }}>{espacio.icon}</Box>
          : <Layers size={14} style={{ flexShrink: 0 }} />}
        <Box component="span" sx={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {espacio ? espacio.name : 'Todos'}
        </Box>
        <ChevronDown size={12} style={{ flexShrink: 0 }} />
      </Box>

      <Menu
        anchorEl={ancla} open={Boolean(ancla)} onClose={() => setAncla(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
        transformOrigin={{ vertical: 'top', horizontal: 'left' }}
      >
        <MenuItem
          selected={!espacio} onClick={() => elegir(null)}
          sx={{ fontSize: '0.875rem' }}
        >
          Todos los Workspaces
        </MenuItem>

        {espacios.map((e) => (
          <MenuItem
            key={e.id} selected={espacio?.slug === e.slug} onClick={() => elegir(e.slug)}
            sx={{ fontSize: '0.875rem', gap: 1 }}
          >
            <Box component="span">{e.icon || '📁'}</Box>
            {e.name}
            <Typography component="span" sx={{ fontSize: '0.75rem', color: textMuted, ml: 'auto', pl: 2 }}>
              {e.counts.agents} {e.counts.agents === 1 ? 'agente' : 'agentes'}
            </Typography>
          </MenuItem>
        ))}

        {espacios.length === 0 && (
          <MenuItem
            onClick={() => { setAncla(null); navigate('/app/contexto?tab=espacios'); }}
            sx={{ fontSize: '0.875rem' }}
          >
            Todavía no hay Espacios — crear el primero
          </MenuItem>
        )}
      </Menu>
    </>
  );
}
