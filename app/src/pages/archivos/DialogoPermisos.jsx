import { useCallback, useEffect, useState } from 'react';
import {
  Alert, Box, Button, Checkbox, CircularProgress, Dialog, DialogActions,
  DialogContent, DialogTitle, IconButton, ListItemText, MenuItem, Select, Stack, Switch,
  Typography, useTheme,
} from '@mui/material';
import { Building2, Globe, Lock, Trash2, UserPlus } from 'lucide-react';
import { api } from '../../services/api';

/**
 * Con quién está compartida una carpeta o un archivo.
 *
 * La regla que la pantalla tiene que dejar clara en una línea: **restringir es la
 * excepción**. Sin restringir, lo ve y lo edita cualquiera del equipo; al restringir,
 * solo las personas de la lista. Y la restricción de una carpeta baja a todo lo que
 * tiene adentro.
 *
 * Si eso no se entiende de un vistazo, la gente va a restringir cosas sin querer o va a
 * creer que restringió algo que sigue a la vista de todos.
 *
 * ## Dos formas de dar acceso, y por qué hacen falta las dos
 *
 * Persona por persona sirve para las excepciones. Pero el caso más común de una empresa es
 * "que lo vea todo el equipo, y que solo estos dos lo editen", y eso, de a una persona a la
 * vez, son tantas cargas como gente haya — una lista que además hay que recordar actualizar
 * cada vez que entra alguien nuevo. Para eso está **Todo el Workspace**: una casilla que
 * vale para cualquier miembro, presente y futuro.
 *
 * Va arriba de la lista porque es la decisión gruesa: primero cuánto se abre para el
 * equipo, después a quién se le da algo más.
 */
export default function DialogoPermisos({ abierto, onCerrar, slug, carpeta, documento, onCambio }) {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const textMuted = d ? 'rgba(255,255,255,0.66)' : 'rgba(0,0,0,0.62)';
  const bgSuave = d ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.02)';
  const borde = theme.palette.divider;

  const [datos, setDatos] = useState(null);
  const [error, setError] = useState('');
  // Varias a la vez: dar acceso a cinco personas eran cinco vueltas por este formulario.
  const [aAgregar, setAAgregar] = useState([]);
  const [nivel, setNivel] = useState('lectura');

  const objetivo = carpeta ? { carpeta } : { documento };
  const esCarpeta = Boolean(carpeta);

  const cargar = useCallback(async () => {
    if (!abierto || !slug) return;
    try {
      const { data } = await api.getCompartido(slug, objetivo);
      setDatos(data);
    } catch {
      setError('No se pudo leer con quién está compartido.');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [abierto, slug, carpeta, documento]);

  useEffect(() => { cargar(); }, [cargar]);

  const cambiar = async (extra) => {
    try {
      setError('');
      const { data } = await api.compartir({ workspace: slug, ...objetivo, ...extra });
      setDatos(data);
      if (onCambio) onCambio();
    } catch (e) {
      setError(e.response?.data?.detail || 'No se pudo guardar.');
    }
  };

  const sacar = async (userId) => {
    try {
      const { data } = await api.descompartir({ workspace: slug, ...objetivo, ids: [userId] });
      setDatos(data);
      if (onCambio) onCambio();
    } catch {
      setError('No se pudo sacar el permiso.');
    }
  };

  return (
    <Dialog
      open={abierto} onClose={onCerrar}
      PaperProps={{ sx: { borderRadius: '14px', minWidth: 480 } }}
    >
      <DialogTitle sx={{ fontSize: '1.0625rem', fontWeight: 600, pb: 0.75 }}>
        Compartir {esCarpeta ? 'la carpeta' : 'el archivo'}
        {datos?.nombre && (
          <Box component="span" sx={{ color: textMuted, fontWeight: 400 }}> · {datos.nombre}</Box>
        )}
      </DialogTitle>

      <DialogContent sx={{ pb: 1 }}>
        {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>{error}</Alert>}

        {datos === null ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress size={22} sx={{ color: '#586AD0' }} />
          </Box>
        ) : (
          <>
            {/* El interruptor y su explicación: es lo que la gente tiene que entender */}
            <Stack
              direction="row" spacing={1.5} alignItems="flex-start"
              sx={{ p: 1.75, borderRadius: '10px', bgcolor: bgSuave, border: `1px solid ${borde}`, mb: 2.5 }}
            >
              <Box sx={{ mt: 0.25, color: datos.restringido ? '#f0b429' : '#34D399' }}>
                {datos.restringido ? <Lock size={17} /> : <Globe size={17} />}
              </Box>
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography sx={{ fontSize: '0.9375rem', fontWeight: 600 }}>
                  {datos.restringido ? 'Solo las personas de abajo' : 'Todo el equipo'}
                </Typography>
                <Typography sx={{ fontSize: '0.8125rem', color: textMuted, mt: 0.25 }}>
                  {datos.restringido
                    ? (esCarpeta
                        ? 'Nadie más la ve, ni lo que tenga adentro.'
                        : 'Nadie más lo ve, aunque la carpeta sea abierta.')
                    : (esCarpeta
                        ? 'Cualquier miembro de la empresa entra y edita lo que hay dentro.'
                        : 'Cualquier miembro de la empresa lo ve y lo edita.')}
                </Typography>
              </Box>
              <Switch
                checked={datos.restringido}
                onChange={(e) => cambiar({ restringido: e.target.checked })}
              />
            </Stack>

            {datos.restringido && (
              <>
                <Typography sx={{
                  fontSize: '0.6875rem', fontWeight: 700, letterSpacing: '0.08em',
                  textTransform: 'uppercase', color: '#586AD0', mb: 1.25,
                }}>
                  Quiénes entran
                </Typography>

                {/* La decisión gruesa primero: cuánto se abre para el equipo entero. */}
                <Stack
                  direction="row" spacing={1} alignItems="center"
                  sx={{
                    p: 1, pl: 0.5, mb: 1.25, borderRadius: '8px',
                    bgcolor: datos.workspace_nivel ? 'rgba(88,106,208,0.07)' : bgSuave,
                    border: `1px solid ${datos.workspace_nivel ? 'rgba(88,106,208,0.35)' : borde}`,
                  }}
                >
                  <Checkbox
                    size="small"
                    checked={Boolean(datos.workspace_nivel)}
                    onChange={(e) => cambiar({ workspace_nivel: e.target.checked ? 'lectura' : null })}
                  />
                  <Box sx={{ color: '#586AD0', display: 'flex', mt: 0.25 }}>
                    <Building2 size={16} />
                  </Box>
                  <Box sx={{ flex: 1, minWidth: 0 }}>
                    <Typography sx={{ fontSize: '0.9rem', fontWeight: 600 }}>
                      Todo el Workspace
                    </Typography>
                    <Typography sx={{ fontSize: '0.78rem', color: textMuted }}>
                      {datos.miembros === 1
                        ? '1 persona, y quien entre más adelante'
                        : `Las ${datos.miembros} personas de ${datos.workspace_nombre}, y quien entre más adelante`}
                    </Typography>
                  </Box>
                  {/* Sin la casilla marcada el nivel no significa nada, así que no se ofrece. */}
                  {datos.workspace_nivel && (
                    <Select
                      size="small" value={datos.workspace_nivel}
                      onChange={(e) => cambiar({ workspace_nivel: e.target.value })}
                      sx={{ fontSize: '0.8rem', minWidth: 122 }}
                    >
                      <MenuItem value="lectura" sx={{ fontSize: '0.8rem' }}>Puede ver</MenuItem>
                      <MenuItem value="edicion" sx={{ fontSize: '0.8rem' }}>Puede editar</MenuItem>
                    </Select>
                  )}
                </Stack>

                <Stack spacing={0.75} sx={{ mb: 2 }}>
                  {/* Con el equipo adentro, "nadie todavía" sería falso: lo dice la casilla. */}
                  {datos.compartido_con.length === 0 ? (
                    !datos.workspace_nivel && (
                      <Typography sx={{ fontSize: '0.875rem', color: textMuted, fontStyle: 'italic' }}>
                        Nadie todavía. Solo usted y los administradores.
                      </Typography>
                    )
                  ) : datos.compartido_con.map((p) => (
                    <Stack
                      key={p.user} direction="row" spacing={1} alignItems="center"
                      sx={{ p: 1, borderRadius: '8px', bgcolor: bgSuave, border: `1px solid ${borde}` }}
                    >
                      <Box sx={{ flex: 1, minWidth: 0 }}>
                        <Typography sx={{ fontSize: '0.9rem', fontWeight: 600 }}>{p.name}</Typography>
                        <Typography sx={{ fontSize: '0.78rem', color: textMuted }}>{p.email}</Typography>
                      </Box>
                      <Select
                        size="small" value={p.nivel}
                        onChange={(e) => cambiar({ ids: [p.user], nivel: e.target.value })}
                        sx={{ fontSize: '0.8rem', minWidth: 122 }}
                      >
                        <MenuItem value="lectura" sx={{ fontSize: '0.8rem' }}>Puede ver</MenuItem>
                        <MenuItem value="edicion" sx={{ fontSize: '0.8rem' }}>Puede editar</MenuItem>
                      </Select>
                      <IconButton size="small" onClick={() => sacar(p.user)} title="Sacar el acceso">
                        <Trash2 size={14} />
                      </IconButton>
                    </Stack>
                  ))}
                </Stack>

                {datos.disponibles.length > 0 && (
                  <Stack direction="row" spacing={1}>
                    <Select
                      multiple size="small" displayEmpty value={aAgregar}
                      onChange={(e) => setAAgregar(e.target.value)}
                      // Con `multiple`, MUI muestra los ids crudos si nadie le dice cómo
                      // pintar la selección.
                      renderValue={(elegidos) => (
                        elegidos.length === 0
                          ? <Box component="span" sx={{ color: textMuted }}>Elegir personas…</Box>
                          : elegidos.length === 1
                            ? datos.disponibles.find((p) => p.id === elegidos[0])?.name
                            : `${elegidos.length} personas`
                      )}
                      sx={{ fontSize: '0.85rem', flex: 1 }}
                    >
                      {datos.disponibles.map((p) => (
                        <MenuItem key={p.id} value={p.id} sx={{ fontSize: '0.85rem', py: 0.25 }}>
                          <Checkbox size="small" checked={aAgregar.includes(p.id)} sx={{ mr: 0.5 }} />
                          <ListItemText
                            primary={p.name} secondary={p.email}
                            primaryTypographyProps={{ fontSize: '0.85rem' }}
                            secondaryTypographyProps={{ fontSize: '0.75rem' }}
                          />
                        </MenuItem>
                      ))}
                    </Select>
                    <Select
                      size="small" value={nivel} onChange={(e) => setNivel(e.target.value)}
                      sx={{ fontSize: '0.85rem', minWidth: 130 }}
                    >
                      <MenuItem value="lectura" sx={{ fontSize: '0.85rem' }}>Puede ver</MenuItem>
                      <MenuItem value="edicion" sx={{ fontSize: '0.85rem' }}>Puede editar</MenuItem>
                    </Select>
                    <Button
                      onClick={() => { cambiar({ ids: aAgregar, nivel }); setAAgregar([]); }}
                      disabled={aAgregar.length === 0} startIcon={<UserPlus size={14} />}
                      sx={{ textTransform: 'none', fontWeight: 600, whiteSpace: 'nowrap' }}
                    >
                      Dar acceso
                    </Button>
                  </Stack>
                )}

                <Typography sx={{ fontSize: '0.78rem', color: textMuted, mt: 2 }}>
                  Los administradores del Workspace entran siempre, y quien subió un archivo
                  no pierde el acceso a lo suyo.
                </Typography>
              </>
            )}

            {/* El agente lee lo que lee la persona: conviene que se sepa. */}
            <Alert severity="info" sx={{ mt: 2.5, fontSize: '0.82rem' }}>
              Los agentes leen lo mismo que la persona que les pregunta. Si alguien no ve
              este {esCarpeta ? 'contenido' : 'archivo'}, tampoco puede llegar a él
              preguntándole a un agente.
            </Alert>
          </>
        )}
      </DialogContent>

      <DialogActions sx={{ px: 3, pb: 2.5 }}>
        <Button onClick={onCerrar} sx={{ textTransform: 'none', fontWeight: 600 }}>
          Listo
        </Button>
      </DialogActions>
    </Dialog>
  );
}
