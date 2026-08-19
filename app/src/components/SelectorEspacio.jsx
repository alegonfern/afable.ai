import { useState } from 'react';
import { Box, Divider, Menu, MenuItem, Typography, useTheme } from '@mui/material';
import { Check, ChevronDown } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useWorkspace } from '../context/WorkspaceContext';
import { MarcaWorkspace } from './SelectorWorkspace';

/**
 * Dónde estoy parado: **la Empresa y el Workspace, en un solo control**.
 *
 * Antes eran dos: la empresa arriba a la derecha y el Workspace adentro del compositor
 * del chat. Dos controles para responder la misma pregunta —"¿dónde está lo que estoy
 * haciendo?"— obligan a mirar dos esquinas de la pantalla y a adivinar cuál manda.
 *
 * Se lee como una ruta, `Empresa / Workspace`, y el menú tiene las dos listas. La empresa
 * sólo aparece como algo que se puede cambiar cuando la persona pertenece a más de una;
 * si no, es identidad y nada más.
 *
 * Elegir Workspace acota lo que se ve: la galería ofrece sólo sus agentes y las
 * conversaciones nuevas quedan guardadas ahí. Con "Todos" se ve todo lo que la persona
 * alcanza, que es como funcionaba antes de que los Workspaces existieran.
 */
export default function SelectorEspacio() {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const navigate = useNavigate();
  const {
    workspace, workspaces, seleccionar,
    espacios, espacio, seleccionarEspacio,
  } = useWorkspace();
  const [ancla, setAncla] = useState(null);

  const textMuted = d ? 'rgba(255,255,255,0.66)' : 'rgba(0,0,0,0.62)';
  const variasEmpresas = workspaces.length > 1;

  if (!workspace) return null;

  const elegirWorkspace = (slug) => {
    seleccionarEspacio(slug);
    setAncla(null);
  };

  const elegirEmpresa = (slug) => {
    seleccionar(slug);
    setAncla(null);
  };

  return (
    <>
      <Box
        onClick={(e) => setAncla(e.currentTarget)}
        title="Dónde estoy trabajando"
        sx={{
          display: 'flex', alignItems: 'center', gap: 0.75,
          px: 1, py: 0.4, borderRadius: '7px', cursor: 'pointer', maxWidth: 340,
          bgcolor: ancla ? (d ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.04)') : 'transparent',
          '&:hover': { bgcolor: d ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.04)' },
        }}
      >
        <MarcaWorkspace workspace={workspace} size={20} />

        {/* La empresa en tono apagado y el Workspace destacado: lo que cambia seguido
            es el segundo, y es el que hay que poder leer de un vistazo. */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, minWidth: 0 }}>
          <Typography
            sx={{
              fontSize: '0.8125rem', color: textMuted, flexShrink: 1, minWidth: 0,
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }}
          >
            {workspace.name}
          </Typography>
          <Typography sx={{ fontSize: '0.8125rem', color: textMuted, opacity: 0.5 }}>/</Typography>
          <Typography
            sx={{
              fontSize: '0.8125rem', fontWeight: 600, flexShrink: 0,
              color: espacio ? theme.palette.text.primary : textMuted,
              display: 'flex', alignItems: 'center', gap: 0.4,
            }}
          >
            {espacio?.icon && <Box component="span">{espacio.icon}</Box>}
            {espacio ? espacio.name : 'Todos'}
          </Typography>
        </Box>

        <ChevronDown size={13} style={{ flexShrink: 0, opacity: 0.6 }} />
      </Box>

      <Menu
        anchorEl={ancla} open={Boolean(ancla)} onClose={() => setAncla(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
        transformOrigin={{ vertical: 'top', horizontal: 'left' }}
        PaperProps={{ sx: { minWidth: 288, borderRadius: '10px', mt: 0.5 } }}
      >
        <Typography sx={SECCION(textMuted)}>Workspaces</Typography>

        <MenuItem
          selected={!espacio} onClick={() => elegirWorkspace(null)}
          sx={{ fontSize: '0.875rem', gap: 1 }}
        >
          <Box sx={{ width: 16, display: 'flex' }}>{!espacio && <Check size={14} />}</Box>
          Todos
          <Typography component="span" sx={{ fontSize: '0.75rem', color: textMuted, ml: 'auto', pl: 2 }}>
            todo lo que alcanzo
          </Typography>
        </MenuItem>

        {espacios.map((e) => (
          <MenuItem
            key={e.id} selected={espacio?.slug === e.slug} onClick={() => elegirWorkspace(e.slug)}
            sx={{ fontSize: '0.875rem', gap: 1 }}
          >
            <Box sx={{ width: 16, display: 'flex' }}>
              {espacio?.slug === e.slug && <Check size={14} />}
            </Box>
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
            Todavía no hay Workspaces — crear el primero
          </MenuItem>
        )}

        {/* La empresa va abajo y sólo si hay de dónde elegir: es lo que casi nunca
            cambia, y ocupando el lugar de arriba le robaba atención al que sí. */}
        {variasEmpresas && [
          <Divider key="sep" sx={{ my: 0.75 }} />,
          <Typography key="titulo" sx={SECCION(textMuted)}>Sus empresas</Typography>,
          ...workspaces.map((w) => (
            <MenuItem
              key={w.id} selected={w.slug === workspace.slug} onClick={() => elegirEmpresa(w.slug)}
              sx={{ fontSize: '0.875rem', gap: 1 }}
            >
              <Box sx={{ width: 16, display: 'flex' }}>
                {w.slug === workspace.slug && <Check size={14} />}
              </Box>
              <MarcaWorkspace workspace={w} size={18} />
              {w.name}
            </MenuItem>
          )),
        ]}

        <Divider sx={{ my: 0.75 }} />
        <MenuItem
          onClick={() => { setAncla(null); navigate('/app/admin/workspace'); }}
          sx={{ fontSize: '0.8125rem', color: textMuted }}
        >
          Ajustes de la empresa
        </MenuItem>
      </Menu>
    </>
  );
}

const SECCION = (color) => ({
  fontSize: '0.6875rem', fontWeight: 700, letterSpacing: '0.08em',
  textTransform: 'uppercase', color, px: 2, pt: 0.5, pb: 0.75,
});
