import { useState } from 'react';
import {
  Box, Button, Dialog, DialogActions, DialogContent, DialogTitle,
  Menu, MenuItem, Select, Stack, Typography, useTheme,
} from '@mui/material';
import { MoreHorizontal } from 'lucide-react';

/**
 * Los tres puntos de una fila de la barra lateral (una conversación, una Sesión).
 *
 * Dos piezas y una regla:
 *  - Un menú con las acciones. Aparece al pasar el mouse por la fila, no siempre: una
 *    lista con un icono fijo en cada línea se lee peor que la lista sola.
 *  - Un diálogo de confirmación SOLO para lo que no se puede deshacer. Confirmar todo
 *    entrena a la gente a apretar "sí" sin leer, y entonces la confirmación que importa
 *    tampoco se lee.
 *
 * `acciones` es una lista de `{ clave, label, color?, confirmar?, aviso? }`. Con
 * `confirmar` se abre el diálogo antes de avisarle a quien lo montó.
 */
export default function MenuDeFila({ acciones, onElegir, visible = true, titulo }) {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const textMuted = d ? 'rgba(255,255,255,0.6)' : 'rgba(0,0,0,0.55)';

  const [anchor, setAnchor] = useState(null);
  const [confirmando, setConfirmando] = useState(null);

  const elegir = (accion) => {
    setAnchor(null);
    if (accion.confirmar) setConfirmando(accion);
    else onElegir(accion.clave);
  };

  return (
    <>
      <Box
        component="button"
        onClick={(e) => { e.stopPropagation(); setAnchor(e.currentTarget); }}
        title="Más opciones"
        sx={{
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          border: 'none', bgcolor: 'transparent', p: 0.25, borderRadius: '4px',
          cursor: 'pointer', flexShrink: 0, color: textMuted,
          // Se muestra al pasar el mouse por la fila, o mientras su menú está abierto.
          opacity: visible || anchor ? 1 : 0,
          transition: 'opacity .12s',
          '&:hover': { bgcolor: d ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.08)' },
        }}
      >
        <MoreHorizontal size={13} />
      </Box>

      <Menu
        anchorEl={anchor} open={Boolean(anchor)}
        onClose={() => setAnchor(null)}
        onClick={(e) => e.stopPropagation()}
      >
        {acciones.map((a) => (
          <MenuItem
            key={a.clave} onClick={() => elegir(a)}
            sx={{ fontSize: '0.875rem', ...(a.color ? { color: a.color } : {}) }}
          >
            {a.label}
          </MenuItem>
        ))}
      </Menu>

      <Dialog
        open={Boolean(confirmando)} onClose={() => setConfirmando(null)}
        onClick={(e) => e.stopPropagation()}
        PaperProps={{ sx: { borderRadius: '14px', minWidth: 380 } }}
      >
        <DialogTitle sx={{ fontSize: '1.0625rem', fontWeight: 600, pb: 1 }}>
          {confirmando?.label}
        </DialogTitle>
        <DialogContent sx={{ pb: 1 }}>
          <Typography sx={{ fontSize: '0.9rem', color: textMuted }}>
            {confirmando?.aviso || 'Esto no se puede deshacer.'}
          </Typography>
          {titulo && (
            <Typography sx={{ fontSize: '0.9rem', fontWeight: 600, mt: 1.25 }}>
              {titulo}
            </Typography>
          )}
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2.5 }}>
          <Button
            onClick={() => setConfirmando(null)}
            sx={{ textTransform: 'none', color: textMuted }}
          >
            Cancelar
          </Button>
          <Button
            onClick={() => { const a = confirmando; setConfirmando(null); onElegir(a.clave); }}
            variant="contained"
            sx={{
              textTransform: 'none', fontWeight: 600, borderRadius: '8px',
              ...(confirmando?.color === '#e5484d'
                ? { bgcolor: '#e5484d', '&:hover': { bgcolor: '#c93b3f' } }
                : {}),
            }}
          >
            {confirmando?.label}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}

/**
 * El diálogo de "compartir en una Sesión".
 *
 * Compartir una conversación es moverla a una Sesión: deja de estar en el historial
 * privado de quien la escribió y pasa a verla el equipo de esa Sesión. No hay un enlace
 * público ni un permiso nuevo — se apoya en lo que la Sesión ya significa.
 */
export function DialogoCompartir({ abierto, onCerrar, sesiones, sesionActual, onCompartir }) {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const textMuted = d ? 'rgba(255,255,255,0.6)' : 'rgba(0,0,0,0.55)';
  const [elegida, setElegida] = useState(sesionActual || '');

  return (
    <Dialog
      open={abierto} onClose={onCerrar}
      PaperProps={{ sx: { borderRadius: '14px', minWidth: 420 } }}
    >
      <DialogTitle sx={{ fontSize: '1.0625rem', fontWeight: 600, pb: 1 }}>
        Compartir con el equipo
      </DialogTitle>
      <DialogContent sx={{ pb: 1 }}>
        <Typography sx={{ fontSize: '0.9rem', color: textMuted, mb: 2 }}>
          La conversación pasa a una Sesión y la ve cualquiera que pertenezca a ella. Hoy
          está en su historial privado.
        </Typography>
        {sesiones.length === 0 ? (
          <Typography sx={{ fontSize: '0.9rem', color: textMuted, fontStyle: 'italic' }}>
            Todavía no hay Sesiones. Se crean con el + de la sección Sesiones.
          </Typography>
        ) : (
          <Select
            size="small" fullWidth displayEmpty
            value={elegida} onChange={(e) => setElegida(e.target.value)}
            sx={{ fontSize: '0.9rem' }}
          >
            <MenuItem value="" sx={{ fontSize: '0.9rem' }}>
              Dejarla en mi historial privado
            </MenuItem>
            {sesiones.map((s) => (
              <MenuItem key={s.slug} value={s.slug} sx={{ fontSize: '0.9rem' }}>
                {s.icon || '💠'}  {s.name}
              </MenuItem>
            ))}
          </Select>
        )}
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2.5 }}>
        <Button onClick={onCerrar} sx={{ textTransform: 'none', color: textMuted }}>
          Cancelar
        </Button>
        <Button
          onClick={() => onCompartir(elegida || null)}
          variant="contained" disabled={sesiones.length === 0}
          sx={{ textTransform: 'none', fontWeight: 600, borderRadius: '8px' }}
        >
          {elegida ? 'Compartir' : 'Quitar de la Sesión'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
