/**
 * La ficha del agente: qué hace, a qué alcanza y qué preguntarle.
 *
 * ⭐ **Por qué existe.** La galería daba el nombre y una frase. Con eso una pyme no puede
 * elegir a cuál preguntarle, ni sabe si el agente está viendo sus documentos o
 * contestando de memoria — y un agente del que no se sabe qué alcanza no se usa para nada
 * que importe. Los agentes son el centro de lo que Afable ofrece; hasta acá se
 * presentaban como una fila de texto.
 *
 * Tres bloques, en el orden en que hacen falta:
 *
 * 1. **A qué alcanza** — los documentos y sistemas por su nombre. Es la diferencia entre
 *    "una IA" y "la IA de mi empresa".
 * 2. **Qué preguntarle** — tres ejemplos armados con SUS fuentes, que se clickean y
 *    arrancan la conversación. Una caja vacía es la peor pantalla para quien nunca usó
 *    esto.
 * 3. **Qué ya hizo** — respuestas y documentos. La prueba de que sirve.
 */
import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box, Button, CircularProgress, Drawer, Stack, Typography, useTheme,
} from '@mui/material';
import { FileText, MessageSquare, Plug, Sparkles, X } from 'lucide-react';
import { api } from '../services/api';

const DISPLAY = `'Sora', 'Inter', sans-serif`;

function Titulo({ children }) {
  return (
    <Typography sx={{
      fontSize: '0.7rem', fontWeight: 700, letterSpacing: '0.06em',
      textTransform: 'uppercase', color: 'text.disabled', mb: 1,
    }}>
      {children}
    </Typography>
  );
}

function cuando(iso) {
  if (!iso) return null;
  const dias = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
  if (dias <= 0) return 'hoy';
  if (dias === 1) return 'ayer';
  if (dias < 30) return `hace ${dias} días`;
  return `hace ${Math.floor(dias / 30)} meses`;
}

export default function FichaDelAgente({ agenteId, workspace, onCerrar }) {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const navigate = useNavigate();

  const [ficha, setFicha] = useState(null);
  const [cargando, setCargando] = useState(true);

  const cargar = useCallback(async () => {
    if (!agenteId || !workspace) return;
    setCargando(true);
    try {
      const { data } = await api.getFichaDelAgente(agenteId, workspace);
      setFicha(data);
    } catch {
      onCerrar?.();
    } finally {
      setCargando(false);
    }
  }, [agenteId, workspace, onCerrar]);

  useEffect(() => { cargar(); }, [cargar]);

  // Una pregunta de ejemplo no se copia: se manda. Si hubiera que copiarla y pegarla, la
  // mitad de la gente no llega.
  const preguntar = (texto) => {
    onCerrar?.();
    navigate('/app/chat', { state: { agentId: agenteId, agentName: ficha.name, pregunta: texto } });
  };

  const cara = ficha?.cara || {};
  const alcance = ficha?.alcance;
  const trabajo = ficha?.trabajo;

  return (
    <Drawer
      anchor="right" open={Boolean(agenteId)} onClose={onCerrar}
      PaperProps={{ sx: {
        width: { xs: '100%', sm: 440 }, p: 0,
        // Columna: cabecera y botón fijos, el medio scrollea. Sin esto el último bloque
        // ("lo que ya hizo") quedaba tapado por el botón, que es justo la prueba de valor.
        display: 'flex', flexDirection: 'column',
      } }}
    >
      {cargando || !ficha ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
          <CircularProgress size={22} />
        </Box>
      ) : (
        <>
          <Box sx={{
            display: 'flex', alignItems: 'flex-start', gap: 1.5, p: 2.5,
            borderBottom: `1px solid ${theme.palette.divider}`,
          }}>
            <Box sx={{
              width: 44, height: 44, borderRadius: '12px', flexShrink: 0,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 22, lineHeight: 1,
              bgcolor: cara.icon ? `${cara.accent}26` : cara.accent,
              border: cara.icon ? `1px solid ${cara.accent}59` : 'none',
              color: '#fff',
            }}>
              {cara.icon || (ficha.handle || '?').charAt(0).toUpperCase()}
            </Box>
            <Box sx={{ flex: 1, minWidth: 0 }}>
              <Typography sx={{ fontFamily: DISPLAY, fontWeight: 700, fontSize: '1.05rem' }}>
                @{ficha.handle}
              </Typography>
              <Typography sx={{ fontSize: '0.78rem', color: 'text.disabled' }}>
                Por {ficha.author}
                {ficha.recommended_frequency ? ` · ${ficha.recommended_frequency}` : ''}
              </Typography>
            </Box>
            <Box onClick={onCerrar} sx={{ cursor: 'pointer', color: 'text.disabled', p: 0.5 }}>
              <X size={17} />
            </Box>
          </Box>

          <Box sx={{ p: 2.5, overflowY: 'auto', flex: 1, minHeight: 0 }}>
            <Typography sx={{ fontSize: '0.9rem', lineHeight: 1.6, mb: 3 }}>
              {ficha.description || 'Sin descripción.'}
            </Typography>

            {/* ── A qué alcanza ─────────────────────────────────────────────── */}
            <Titulo>A qué alcanza</Titulo>
            {alcance.sin_fuentes ? (
              // Se dice de frente. Alguien que cree que le contestan con SUS datos y en
              // realidad le contestan de memoria toma decisiones sobre arena.
              <Box sx={{
                p: 1.5, mb: 3, borderRadius: '10px', bgcolor: 'action.hover',
                fontSize: '0.82rem', color: 'text.secondary',
              }}>
                Todavía no alcanza ningún documento ni sistema de su empresa, así que
                contesta con conocimiento general.{' '}
                <Box
                  component="span"
                  onClick={() => { onCerrar?.(); navigate('/app/archivos'); }}
                  sx={{ color: '#586AD0', fontWeight: 600, cursor: 'pointer' }}
                >
                  Suba un documento
                </Box>{' '}
                y cambia lo que puede responder.
              </Box>
            ) : (
              <Stack spacing={0.75} sx={{ mb: 3 }}>
                {alcance.sistemas.map((s) => (
                  <Box key={s} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Plug size={14} color="#3E8E7E" />
                    <Typography sx={{ fontSize: '0.84rem' }}>{s}</Typography>
                  </Box>
                ))}
                {alcance.documentos.map((t, i) => (
                  <Box key={`${t}-${i}`} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <FileText size={14} color="#7B8AE0" />
                    <Typography sx={{
                      fontSize: '0.84rem', overflow: 'hidden',
                      textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }}>
                      {t}
                    </Typography>
                  </Box>
                ))}
                {alcance.total_documentos > alcance.documentos.length && (
                  // Se dice cuántos quedaron fuera: una lista recortada en silencio se lee
                  // como la lista completa.
                  <Typography sx={{ fontSize: '0.78rem', color: 'text.disabled', pl: 2.75 }}>
                    y {alcance.total_documentos - alcance.documentos.length} documentos más
                  </Typography>
                )}
              </Stack>
            )}

            {/* ── Qué preguntarle ───────────────────────────────────────────── */}
            <Titulo>Qué preguntarle</Titulo>
            <Stack spacing={0.75} sx={{ mb: 3 }}>
              {ficha.preguntas.map((p) => (
                <Box
                  key={p}
                  onClick={() => preguntar(p)}
                  sx={{
                    display: 'flex', alignItems: 'center', gap: 1, cursor: 'pointer',
                    px: 1.25, py: 1, borderRadius: '10px',
                    border: `1px solid ${theme.palette.divider}`,
                    '&:hover': {
                      borderColor: '#586AD0',
                      bgcolor: d ? 'rgba(88,106,208,0.10)' : 'rgba(88,106,208,0.05)',
                    },
                  }}
                >
                  <Sparkles size={13} color="#7B8AE0" />
                  <Typography sx={{ fontSize: '0.84rem', lineHeight: 1.4 }}>{p}</Typography>
                </Box>
              ))}
            </Stack>

            {/* ── Qué ya hizo ───────────────────────────────────────────────── */}
            {trabajo.respuestas > 0 && (
              <>
                <Titulo>Lo que ya hizo por usted</Titulo>
                <Stack direction="row" spacing={3} sx={{ mb: 1 }}>
                  <Box>
                    <Typography sx={{ fontFamily: DISPLAY, fontWeight: 700, fontSize: '1.3rem' }}>
                      {trabajo.respuestas}
                    </Typography>
                    <Typography sx={{ fontSize: '0.75rem', color: 'text.disabled' }}>
                      {trabajo.respuestas === 1 ? 'respuesta' : 'respuestas'}
                    </Typography>
                  </Box>
                  {trabajo.documentos > 0 && (
                    <Box>
                      <Typography sx={{ fontFamily: DISPLAY, fontWeight: 700, fontSize: '1.3rem' }}>
                        {trabajo.documentos}
                      </Typography>
                      <Typography sx={{ fontSize: '0.75rem', color: 'text.disabled' }}>
                        {trabajo.documentos === 1 ? 'documento escrito' : 'documentos escritos'}
                      </Typography>
                    </Box>
                  )}
                </Stack>
                {cuando(trabajo.ultima_vez) && (
                  <Typography sx={{ fontSize: '0.78rem', color: 'text.disabled' }}>
                    La última vez, {cuando(trabajo.ultima_vez)}.
                  </Typography>
                )}
              </>
            )}
          </Box>

          <Box sx={{ p: 2, flexShrink: 0, borderTop: `1px solid ${theme.palette.divider}` }}>
            <Button
              fullWidth variant="contained" startIcon={<MessageSquare size={15} />}
              onClick={() => { onCerrar?.(); navigate('/app/chat', { state: { agentId: agenteId, agentName: ficha.name } }); }}
              sx={{ textTransform: 'none', borderRadius: '10px', fontWeight: 600 }}
            >
              Hablar con @{ficha.handle}
            </Button>
          </Box>
        </>
      )}
    </Drawer>
  );
}
