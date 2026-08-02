import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Box, Button, CircularProgress, TextField, Typography, useTheme } from '@mui/material';
import { ArrowLeft, Bot } from 'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../../services/api';
import { useWorkspace } from '../../context/WorkspaceContext';

const DISPLAY = `'Sora', 'Inter', sans-serif`;

const CAMPOS = [
  {
    clave: 'datos',
    titulo: 'Qué datos puede mirar',
    ayuda: 'Nombre las tablas, sistemas o documentos que puede consultar, y los que no. '
         + 'Ejemplo: "Facturas y notas de crédito en Odoo. No mirar remuneraciones."',
    placeholder: 'Ventas y facturas de Odoo. Los documentos de la carpeta Contabilidad en Drive.',
  },
  {
    clave: 'reglas',
    titulo: 'Con qué reglas responde',
    ayuda: 'Lo que siempre debe hacer y lo que nunca. Es lo que evita respuestas inventadas.',
    placeholder: 'Nunca invente montos: si falta un dato, dígalo. Los precios se informan sin IVA.',
  },
  {
    clave: 'info_util',
    titulo: 'Qué le conviene saber',
    ayuda: 'Lo que su equipo sabe de memoria y no está escrito en ningún sistema.',
    placeholder: 'Nuestro año comercial cierra en marzo. El cliente grande es Constructora Vera.',
  },
];

/**
 * Admin › Agentes › configurar uno.
 *
 * Tres cosas: a qué datos mira, con qué reglas responde y qué le conviene saber.
 * Lo que se escribe acá entra al prompt del agente (AgentConfig.como_contexto),
 * así que no es un formulario decorativo.
 */
export default function AgenteConfigPage() {
  const { id } = useParams();
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const navigate = useNavigate();
  const { slug, esAdmin } = useWorkspace();

  const textMuted = d ? 'rgba(255,255,255,0.66)' : 'rgba(0,0,0,0.62)';
  const textSemi = d ? 'rgba(255,255,255,0.82)' : 'rgba(0,0,0,0.76)';
  const bgSuave = d ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.02)';
  const borde = theme.palette.divider;

  const [agente, setAgente] = useState(null);
  const [form, setForm] = useState({ datos: '', reglas: '', info_util: '' });
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);

  const cargar = useCallback(async () => {
    if (!slug) return;
    try {
      setCargando(true);
      const { data } = await api.getAdminAgent(id, slug);
      setAgente(data);
      setForm({ datos: data.datos || '', reglas: data.reglas || '', info_util: data.info_util || '' });
    } catch {
      toast.error('No se pudo cargar el agente.');
      navigate('/app/admin/agentes');
    } finally {
      setCargando(false);
    }
  }, [id, slug, navigate]);

  useEffect(() => { cargar(); }, [cargar]);

  const guardar = async () => {
    try {
      setGuardando(true);
      const { data } = await api.updateAdminAgent(id, { workspace: slug, ...form });
      setAgente(data);
      toast.success(
        data.configurado
          ? `${data.name} ya sabe con qué trabajar.`
          : `${data.name} quedó sin información: vuelve a estar pendiente.`,
      );
    } catch (e) {
      toast.error(e.response?.data?.detail || 'No se pudo guardar.');
    } finally {
      setGuardando(false);
    }
  };

  if (cargando) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', pt: 12 }}>
        <CircularProgress size={26} sx={{ color: '#586AD0' }} />
      </Box>
    );
  }

  if (!esAdmin || !agente) {
    return (
      <Box sx={{ maxWidth: 900, mx: 'auto', px: 5, py: 6 }}>
        <Typography sx={{ color: textMuted, fontSize: '0.9375rem' }}>
          Solo un administrador del Workspace configura los agentes.
        </Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ maxWidth: 900, mx: 'auto', px: { xs: 2.5, md: 5 }, py: { xs: 4, md: 6 }, width: '100%' }}>
      <Button
        onClick={() => navigate('/app/admin/agentes')}
        startIcon={<ArrowLeft size={15} />}
        sx={{ textTransform: 'none', color: textMuted, fontSize: '0.875rem', mb: 2, ml: -1 }}
      >
        Agentes
      </Button>

      <Bot size={24} color={textSemi} strokeWidth={1.75} />
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mt: 1.5, flexWrap: 'wrap' }}>
        <Typography sx={{ fontFamily: DISPLAY, fontSize: '1.875rem', fontWeight: 600, letterSpacing: '-0.01em' }}>
          {agente.name}
        </Typography>
        <Box component="span" sx={{
          px: 1, py: 0.25, borderRadius: '6px', fontSize: '0.8125rem', fontWeight: 600,
          bgcolor: agente.configurado ? 'rgba(52, 211, 153, 0.14)' : 'rgba(240, 180, 41, 0.14)',
          color: agente.configurado ? '#34D399' : '#f0b429',
          border: `1px solid ${agente.configurado ? 'rgba(52, 211, 153, 0.3)' : 'rgba(240, 180, 41, 0.3)'}`,
        }}>
          {agente.configurado ? 'Configurado' : 'Pendiente'}
        </Box>
      </Box>
      <Typography sx={{ color: textMuted, fontSize: '0.9375rem', mt: 0.75 }}>
        {agente.description}
      </Typography>

      {agente.instructions && (
        <Box sx={{ mt: 3, p: 2, borderRadius: '10px', bgcolor: bgSuave, border: `1px solid ${borde}` }}>
          <Typography sx={{ fontSize: '0.6875rem', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: textMuted, mb: 0.75 }}>
            Su oficio (viene con el agente)
          </Typography>
          <Typography sx={{ fontSize: '0.9375rem', color: textSemi, lineHeight: 1.55 }}>
            {agente.instructions}
          </Typography>
        </Box>
      )}

      {CAMPOS.map((campo) => (
        <Box key={campo.clave} sx={{ mt: 4 }}>
          <Typography sx={{ fontSize: '1rem', fontWeight: 600 }}>{campo.titulo}</Typography>
          <Typography sx={{ fontSize: '0.875rem', color: textMuted, mt: 0.5, mb: 1.5 }}>
            {campo.ayuda}
          </Typography>
          <TextField
            value={form[campo.clave]}
            onChange={(e) => setForm({ ...form, [campo.clave]: e.target.value })}
            placeholder={campo.placeholder}
            multiline minRows={3} fullWidth size="small"
            sx={{
              '& .MuiOutlinedInput-root': {
                bgcolor: bgSuave, borderRadius: '8px', fontSize: '0.9375rem',
                '& fieldset': { borderColor: borde },
                '&.Mui-focused fieldset': { borderColor: '#586AD0' },
              },
            }}
          />
        </Box>
      ))}

      <Button
        onClick={guardar}
        disabled={guardando}
        variant="contained"
        sx={{ mt: 4, borderRadius: '8px', textTransform: 'none', fontWeight: 600, px: 3 }}
      >
        {guardando ? 'Guardando…' : 'Guardar'}
      </Button>

      <Typography sx={{ color: textMuted, fontSize: '0.8125rem', mt: 2 }}>
        Lo que escriba acá entra en cada respuesta de {agente.name}.
      </Typography>
    </Box>
  );
}
