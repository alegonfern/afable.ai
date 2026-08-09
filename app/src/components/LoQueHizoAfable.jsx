import { useCallback, useEffect, useState } from 'react';
import { Box, Typography, useTheme } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { CheckCircle2, FileText, MessageSquare, Sparkles } from 'lucide-react';
import { api } from '../services/api';
import { useWorkspace } from '../context/WorkspaceContext';

/**
 * Lo que los agentes hicieron solos, arriba en la home.
 *
 * ⭐ El producto promete que trabajan cuando uno no está —y ya lo hace— pero no había
 * dónde verlo junto: quien abre el lunes veía la misma pantalla del viernes y sentía que
 * paga por un chat. Esto es la evidencia, y es lo que hace que la renovación se justifique
 * sola.
 *
 * **Si no hubo nada, no se dibuja.** Un panel que dice "0 cosas esta semana" es un
 * recordatorio semanal de que el producto no está haciendo su trabajo.
 */

const ICONOS = {
  publicacion: MessageSquare,
  tarea: CheckCircle2,
  escritura: FileText,
};

const cuandoEnPalabras = (iso) => {
  const horas = (Date.now() - new Date(iso).getTime()) / 36e5;
  if (horas < 1) return 'recién';
  if (horas < 24) return `hace ${Math.round(horas)} h`;
  const dias = Math.round(horas / 24);
  return dias === 1 ? 'ayer' : `hace ${dias} días`;
};

export default function LoQueHizoAfable() {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const navigate = useNavigate();
  const { slug } = useWorkspace();

  const [datos, setDatos] = useState(null);

  const textMuted = d ? 'rgba(255,255,255,0.66)' : 'rgba(0,0,0,0.62)';
  const borde = theme.palette.divider;
  const verde = '#34D399';

  const cargar = useCallback(async () => {
    if (!slug) return;
    try {
      const { data } = await api.loQueHizoAfable(slug);
      setDatos(data);
    } catch {
      setDatos(null);
    }
  }, [slug]);

  useEffect(() => { cargar(); }, [cargar]);

  if (!datos || !datos.items?.length) return null;

  return (
    <Box sx={{
      border: `1px solid ${d ? 'rgba(52,211,153,0.28)' : 'rgba(52,211,153,0.4)'}`,
      borderRadius: '12px', px: 2.25, py: 1.75, mb: 3,
      bgcolor: d ? 'rgba(52,211,153,0.05)' : 'rgba(52,211,153,0.04)',
    }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
        <Sparkles size={15} color={verde} />
        <Typography sx={{ fontSize: '0.9375rem', fontWeight: 600 }}>
          Mientras no estaba
        </Typography>
        <Typography sx={{ fontSize: '0.8125rem', color: textMuted }}>
          {/* El número entero, no el recortado: "3 de 12" hace pensar que falta algo. */}
          {datos.total} {datos.total === 1 ? 'cosa' : 'cosas'} en {datos.dias} días
        </Typography>
      </Box>

      <Box sx={{ display: 'flex', flexDirection: 'column' }}>
        {datos.items.map((i, n) => {
          const Icono = ICONOS[i.tipo] || Sparkles;
          return (
            <Box
              key={`${i.tipo}-${n}`}
              onClick={() => navigate(i.ruta)}
              sx={{
                display: 'flex', alignItems: 'center', gap: 1.25,
                px: 1, py: 0.85, borderRadius: '8px', cursor: 'pointer',
                borderTop: n ? `1px solid ${borde}` : 'none',
                '&:hover': { bgcolor: d ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.025)' },
              }}
            >
              <Icono size={14} color={verde} style={{ flexShrink: 0 }} />
              <Typography sx={{
                fontSize: '0.875rem', flex: 1, minWidth: 0,
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>
                {i.titulo}
              </Typography>
              {/* Quién y dónde: sin eso, "revisó el tracker" no le dice a nadie de qué
                  trabajo está hablando. */}
              <Typography sx={{ fontSize: '0.75rem', color: textMuted, flexShrink: 0 }}>
                {i.quien}{i.donde ? ` · ${i.donde}` : ''} · {cuandoEnPalabras(i.cuando)}
              </Typography>
            </Box>
          );
        })}
      </Box>
    </Box>
  );
}
