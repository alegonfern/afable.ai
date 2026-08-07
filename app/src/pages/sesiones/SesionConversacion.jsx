import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Alert, Box, CircularProgress, IconButton, MenuItem,
  Select, Stack, TextField, Typography, useTheme,
} from '@mui/material';
import { Bot, CheckCircle2, MessageSquare, Search, Send, Sparkles } from 'lucide-react';
import { api } from '../../services/api';

/**
 * La Conversación de una Sesión: el compositor arriba y debajo lo que pasó.
 *
 * Dos decisiones que vienen del cuadro de referencia y no son cosméticas:
 *
 * - **El compositor va arriba**, no abajo. Esta pantalla no es un chat abierto: es el
 *   lugar donde uno llega a empezar algo. Lo primero que se ve es dónde escribir.
 * - **Una tarea y una conversación son el mismo tipo de item** en la lista. Las dos
 *   son "algo que alguien empezó, con respuestas debajo"; separarlas en dos listas
 *   obliga a mirar en dos lados para saber qué pasó en la Sesión.
 */
export default function SesionConversacion({ sesion, slug, onSaludo }) {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const navigate = useNavigate();

  const textMuted = d ? 'rgba(255,255,255,0.66)' : 'rgba(0,0,0,0.62)';
  const bgSuave = d ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.02)';
  const borde = theme.palette.divider;

  const [feed, setFeed] = useState(null);
  const [error, setError] = useState('');
  const [mensaje, setMensaje] = useState('');
  const [busqueda, setBusqueda] = useState('');
  const [agentes, setAgentes] = useState([]);
  const [agente, setAgente] = useState('');

  const cargar = useCallback(async () => {
    if (!slug) return;
    try {
      const { data } = await api.getSesionFeed(sesion.slug, slug);
      setFeed(data);
      // El saludo lo elige el backend (rota por día) y lo muestra el título de arriba:
      // calcularlo en el navegador lo haría cambiar en cada dibujado de React.
      if (onSaludo) onSaludo(data.saludo);
    } catch {
      setError('No se pudo leer lo que pasó en esta Sesión.');
      setFeed({ grupos: [], count: 0, saludo: 'a trabajar' });
    }
  }, [sesion.slug, slug, onSaludo]);

  useEffect(() => { cargar(); }, [cargar]);

  useEffect(() => {
    if (!slug) return;
    api.getAgentGallery({ workspace: slug, tab: 'todos', page: 1 })
      .then(({ data }) => setAgentes(data.results || []))
      .catch(() => {});
  }, [slug]);

  // Enviar abre el hilo EN esta Sesión: el chat recibe la Sesión y la conversación
  // queda colgada de ella, así la ve cualquiera que entre acá.
  const enviar = () => {
    const texto = mensaje.trim();
    if (!texto) return;
    navigate('/app/chat', {
      state: {
        initialMessage: texto,
        sesionSlug: sesion.slug,
        ...(agente ? { agentId: agente } : {}),
      },
    });
  };

  if (feed === null) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
        <CircularProgress size={22} sx={{ color: '#586AD0' }} />
      </Box>
    );
  }

  const filtrados = (grupo) => grupo.items.filter((i) =>
    !busqueda.trim() || i.titulo.toLowerCase().includes(busqueda.trim().toLowerCase()),
  );
  const visibles = feed.grupos.map((g) => ({ ...g, items: filtrados(g) }))
    .filter((g) => g.items.length > 0);

  return (
    <Box sx={{ px: { xs: 2.5, sm: 4 }, pt: 1, pb: 6, maxWidth: 900, width: '100%', mx: 'auto' }}>
      {/* El compositor, arriba */}
      <Box sx={{
        p: 1.75, mb: 2, borderRadius: '12px',
        bgcolor: bgSuave, border: `1px solid ${borde}`,
      }}>
        <TextField
          value={mensaje}
          onChange={(e) => setMensaje(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); enviar(); }
          }}
          placeholder="Empezar algo en esta Sesión…"
          multiline minRows={2} fullWidth variant="standard"
          InputProps={{ disableUnderline: true, sx: { fontSize: '0.9375rem' } }}
        />
        <Stack direction="row" spacing={1} alignItems="center" sx={{ mt: 1 }}>
          <Select
            size="small" displayEmpty value={agente}
            onChange={(e) => setAgente(e.target.value)}
            sx={{
              fontSize: '0.8125rem', minWidth: 160,
              '& fieldset': { borderColor: borde },
            }}
            startAdornment={<Bot size={14} style={{ marginRight: 6, opacity: 0.6 }} />}
          >
            <MenuItem value="" sx={{ fontSize: '0.8125rem' }}>El agente por defecto</MenuItem>
            {agentes.map((a) => (
              <MenuItem key={a.id} value={a.id} sx={{ fontSize: '0.8125rem' }}>{a.name}</MenuItem>
            ))}
          </Select>
          <Box sx={{ flex: 1 }} />
          <IconButton
            onClick={enviar} disabled={!mensaje.trim()}
            sx={{
              bgcolor: mensaje.trim() ? '#586AD0' : 'transparent',
              color: mensaje.trim() ? '#fff' : textMuted,
              '&:hover': { bgcolor: mensaje.trim() ? '#2F42A6' : bgSuave },
            }}
            size="small"
          >
            <Send size={15} />
          </IconButton>
        </Stack>
      </Box>

      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>{error}</Alert>}

      {feed.count > 0 && (
        <TextField
          value={busqueda}
          onChange={(e) => setBusqueda(e.target.value)}
          placeholder="Buscar en esta Sesión"
          size="small" fullWidth sx={{ mb: 2.5 }}
          InputProps={{
            endAdornment: <Search size={15} color={textMuted} />,
            sx: {
              bgcolor: bgSuave, borderRadius: '8px', fontSize: '0.9375rem',
              '& fieldset': { borderColor: borde },
              '&.Mui-focused fieldset': { borderColor: '#586AD0' },
            },
          }}
        />
      )}

      {visibles.length === 0 ? (
        <Typography sx={{ fontSize: '0.9375rem', color: textMuted, py: 3 }}>
          {feed.count === 0
            ? 'Todavía no pasó nada en esta Sesión. Escriba arriba para empezar.'
            : 'Nada coincide con la búsqueda.'}
        </Typography>
      ) : visibles.map((g) => (
        <Box key={g.titulo} sx={{ mb: 3 }}>
          <Typography sx={{
            fontSize: '0.6875rem', fontWeight: 700, letterSpacing: '0.08em',
            textTransform: 'uppercase', color: textMuted, mb: 1.25,
          }}>
            {g.titulo}
          </Typography>
          <Stack spacing={1}>
            {g.items.map((i) => (
              <Stack
                key={`${i.tipo}-${i.id}`}
                direction="row" spacing={1.5} alignItems="flex-start"
                onClick={() => {
                  if (i.tipo === 'conversacion') navigate(`/app/chat?conversation=${i.id}`);
                }}
                sx={{
                  p: 1.5, borderRadius: '10px',
                  cursor: i.tipo === 'conversacion' ? 'pointer' : 'default',
                  border: `1px solid ${borde}`, bgcolor: bgSuave,
                  '&:hover': i.tipo === 'conversacion'
                    ? { borderColor: d ? 'rgba(255,255,255,0.18)' : 'rgba(0,0,0,0.18)' }
                    : {},
                }}
              >
                <Box sx={{
                  width: 30, height: 30, borderRadius: '8px', flexShrink: 0, mt: 0.25,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  // Lo que trajo un agente solo va en verde y con otro icono: es la
                  // diferencia que hay que ver de un vistazo entre "alguien escribió
                  // esto" y "esto apareció sin que nadie lo pidiera".
                  bgcolor: i.autonoma ? 'rgba(52, 211, 153, 0.14)'
                    : i.tipo === 'tarea' ? 'rgba(240, 180, 41, 0.14)' : 'rgba(88, 106, 208, 0.14)',
                  color: i.autonoma ? '#34D399'
                    : i.tipo === 'tarea' ? '#f0b429' : '#9BA6E3',
                }}>
                  {i.autonoma ? <Sparkles size={15} />
                    : i.tipo === 'tarea' ? <CheckCircle2 size={15} /> : <MessageSquare size={15} />}
                </Box>
                <Box sx={{ flex: 1, minWidth: 0 }}>
                  <Typography sx={{ fontSize: '0.9375rem', fontWeight: 600 }}>
                    <Box component="span" sx={{ color: textMuted, fontWeight: 500 }}>
                      {i.tipo === 'tarea' ? 'Tarea · ' : ''}
                    </Box>
                    {i.titulo}
                    {/* Con `autonoma` NO se firma con el nombre de una persona: nadie lo
                        escribió. Decir "Alexis Gonzalez" ahí sería atribuirle a alguien
                        algo que trajo el agente por su cuenta. */}
                    {i.autonoma ? (
                      <Box component="span" sx={{ color: '#34D399', fontWeight: 600, ml: 1, fontSize: '0.8125rem' }}>
                        lo trajo {i.agente || 'un agente'}, sin que nadie lo pidiera
                      </Box>
                    ) : i.autor && (
                      <Box component="span" sx={{ color: textMuted, fontWeight: 400, ml: 1, fontSize: '0.875rem' }}>
                        {i.es_mio ? 'usted' : i.autor}
                      </Box>
                    )}
                  </Typography>
                  {i.detalle && (
                    <Typography sx={{ fontSize: '0.875rem', color: textMuted, mt: 0.35 }}>
                      {i.detalle}
                    </Typography>
                  )}
                  {i.respuestas > 0 && (
                    <Typography sx={{ fontSize: '0.8125rem', color: '#9BA6E3', mt: 0.6, fontWeight: 600 }}>
                      {i.respuestas} {i.respuestas === 1 ? 'respuesta' : 'respuestas'}
                      {i.ultima_de && ` · la última de ${i.ultima_de}`}
                    </Typography>
                  )}
                </Box>
              </Stack>
            ))}
          </Stack>
        </Box>
      ))}
    </Box>
  );
}
