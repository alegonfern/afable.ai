import { useState } from 'react';
import {
  Box, Divider, Menu, MenuItem, Tooltip, Typography, useTheme,
} from '@mui/material';
import { Check, ChevronsUpDown, Settings, Users } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useWorkspace } from '../context/WorkspaceContext';

/**
 * En qué empresa se está trabajando, y cómo cambiar de una a otra.
 *
 * Hacía falta por una razón simple: el Workspace decide TODO lo que se ve —los archivos,
 * los agentes, las conexiones, las personas— y no había nada en pantalla que dijera cuál
 * estaba activo. `WorkspaceContext` ya sabía cambiar de Workspace, pero lo único que
 * llamaba a `seleccionar` eran la pantalla de Ajustes y la de aceptar una invitación: quien
 * pertenecía a dos empresas no tenía forma de pasar de una a la otra, y peor, no tenía
 * forma de notar en cuál estaba escribiendo.
 *
 * Vive arriba a la derecha, pegado al claro/oscuro: los dos son ajustes del MARCO y no del
 * contenido de la pantalla. Con un solo Workspace no es un conmutador y no finge serlo —
 * muestra la empresa y lleva a sus ajustes.
 *
 * `compacto` es la variante del encabezado: SOLO la marca y la flecha, unos 44px. Ahí
 * comparte fila con el selector de modelo y el buscador, y cualquier versión con el nombre
 * escrito les come el ancho — con el nombre completo el buscador quedaba partido en tres
 * líneas. La marca alcanza justamente porque para eso existe: se distingue una empresa de
 * otra sin leer. El nombre va en el tooltip y en el menú, que es donde hay lugar.
 */

// La paleta del monograma. Colores que se leen sobre claro y sobre oscuro, y que no
// compiten con el índigo de la marca.
const COLORES = [
  '#586AD0', '#0F9D8C', '#C2703D', '#8A5CC4', '#3F7FBF',
  '#B4485F', '#5E8C3A', '#9A7B2E',
];

/** Un color estable para un texto dado: la misma empresa siempre se ve igual. */
function colorDe(texto = '') {
  let suma = 0;
  for (let i = 0; i < texto.length; i += 1) suma = (suma * 31 + texto.charCodeAt(i)) % 100000;
  return COLORES[suma % COLORES.length];
}

/** La inicial que va en el monograma. Dos palabras dan dos letras. */
function inicialesDe(nombre = '') {
  const partes = nombre.trim().split(/\s+/).filter(Boolean);
  if (partes.length === 0) return '·';
  if (partes.length === 1) return partes[0].slice(0, 1).toUpperCase();
  return (partes[0][0] + partes[1][0]).toUpperCase();
}

/**
 * La marca de un Workspace: su logo si cargó uno, y si no un monograma.
 *
 * El monograma no es un relleno provisorio. Con logo o sin logo, la marca tiene que
 * ocupar el mismo lugar y el mismo tamaño, porque es por ella que se distingue una
 * empresa de otra sin leer: un hueco vacío obligaría a leer el nombre siempre.
 */
export function MarcaWorkspace({ workspace, size = 26, radio = '7px' }) {
  const fondo = colorDe(workspace?.slug || workspace?.name || '');
  const comun = {
    width: size, height: size, borderRadius: radio, flexShrink: 0,
    display: 'flex', alignItems: 'center', justifyContent: 'center',
  };

  if (workspace?.logo_url) {
    return (
      <Box
        component="img" src={workspace.logo_url} alt=""
        sx={{ ...comun, objectFit: 'cover', bgcolor: 'rgba(0,0,0,0.06)' }}
      />
    );
  }
  return (
    <Box sx={{ ...comun, bgcolor: fondo }}>
      <Typography sx={{
        fontSize: size * 0.42, fontWeight: 700, color: '#fff', lineHeight: 1,
        letterSpacing: '0.02em',
      }}>
        {inicialesDe(workspace?.name)}
      </Typography>
    </Box>
  );
}

export default function SelectorWorkspace({ open = true, compacto = true }) {
  const theme = useTheme();
  const navigate = useNavigate();
  const d = theme.palette.mode === 'dark';
  const textActive = d ? 'rgba(255,255,255,0.92)' : 'rgba(0,0,0,0.87)';
  const textMuted = d ? 'rgba(255,255,255,0.60)' : 'rgba(0,0,0,0.58)';
  const bgHover = d ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.04)';

  const { workspace, workspaces, seleccionar, loading } = useWorkspace();
  const [ancla, setAncla] = useState(null);

  // Sin Workspace no hay nada que mostrar: la app entera está en otro estado (recién
  // registrado, o sacado de la única empresa) y esa pantalla lo explica.
  if (loading || !workspace) return null;

  const varios = workspaces.length > 1;

  // La segunda línea: qué es esta empresa. El sector es lo más corto que la describe; si
  // no está cargado, la descripción sirve igual, recortada.
  const subtitulo = workspace.sector_label
    || (workspace.description || '').split('\n')[0]
    || `${workspace.member_count} ${workspace.member_count === 1 ? 'persona' : 'personas'}`;

  const cambiar = (slug) => {
    setAncla(null);
    if (slug !== workspace.slug) seleccionar(slug);
  };

  return (
    <>
      <Tooltip
        title={
          (compacto || !open)
            ? `${workspace.name}${varios ? ' — cambiar de empresa' : ''}`
            : ''
        }
        placement={compacto ? 'bottom' : 'right'} arrow
      >
        <Box
          component="button"
          onClick={(e) => setAncla(e.currentTarget)}
          sx={{
            border: 'none', bgcolor: 'transparent', cursor: 'pointer',
            fontFamily: 'inherit', textAlign: 'left', flexShrink: 0,
            display: 'flex', alignItems: 'center', gap: compacto ? 0.75 : 1,
            width: compacto ? 'auto' : '100%',
            px: open ? (compacto ? 0.75 : 1) : 0.5, py: compacto ? 0.4 : 0.75,
            borderRadius: '7px',
            justifyContent: open ? 'flex-start' : 'center',
            '&:hover': { bgcolor: bgHover }, transition: 'background-color 0.12s',
          }}
        >
          <MarcaWorkspace workspace={workspace} size={compacto ? 22 : 26} />
          {/* En el encabezado NO va el nombre escrito: le come el ancho al buscador. */}
          {open && !compacto && (
            <Box sx={{ minWidth: 0, flex: 1 }}>
              <Typography
                noWrap
                sx={{ fontSize: '0.8125rem', fontWeight: 600, color: textActive, lineHeight: 1.3 }}
              >
                {workspace.name}
              </Typography>
              <Typography noWrap sx={{ fontSize: '0.72rem', color: textMuted, lineHeight: 1.3 }}>
                {subtitulo}
              </Typography>
            </Box>
          )}
          {(open || compacto) && (
            <ChevronsUpDown size={12} style={{ flexShrink: 0, color: textMuted }} />
          )}
        </Box>
      </Tooltip>

      <Menu
        anchorEl={ancla} open={Boolean(ancla)} onClose={() => setAncla(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: compacto ? 'right' : 'left' }}
        transformOrigin={{ vertical: 'top', horizontal: compacto ? 'right' : 'left' }}
        PaperProps={{ sx: { minWidth: 268, borderRadius: '10px', mt: 0.5 } }}
      >
        {/* El encabezado solo aparece cuando hay de dónde elegir. */}
        {varios && (
          <Typography sx={{
            fontSize: '0.6875rem', fontWeight: 700, letterSpacing: '0.08em',
            textTransform: 'uppercase', color: textMuted, px: 2, pt: 0.5, pb: 0.75,
          }}>
            Tus empresas
          </Typography>
        )}

        {workspaces.map((w) => {
          const activo = w.slug === workspace.slug;
          return (
            <MenuItem
              key={w.slug} onClick={() => cambiar(w.slug)} selected={activo}
              sx={{ gap: 1.25, py: 0.85 }}
            >
              <MarcaWorkspace workspace={w} size={24} />
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography noWrap sx={{ fontSize: '0.875rem', fontWeight: 600 }}>
                  {w.name}
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, color: textMuted }}>
                  <Users size={11} />
                  <Typography sx={{ fontSize: '0.72rem' }}>
                    {w.member_count} · {ROLES[w.my_role] || w.my_role}
                  </Typography>
                </Box>
              </Box>
              {activo && <Check size={14} style={{ color: '#586AD0', flexShrink: 0 }} />}
            </MenuItem>
          );
        })}

        <Divider sx={{ my: 0.5 }} />

        <MenuItem
          onClick={() => { setAncla(null); navigate('/app/admin/workspace'); }}
          sx={{ gap: 1.25, fontSize: '0.85rem' }}
        >
          <Settings size={14} />
          Ajustes de la empresa
        </MenuItem>
      </Menu>
    </>
  );
}

// El rol en palabras: "miembro" guardado se lee igual, pero "admin" no.
const ROLES = { admin: 'Administrador', editor: 'Editor', miembro: 'Miembro' };
