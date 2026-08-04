import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Box, Button, Chip, CircularProgress, MenuItem, TextField, Typography, useTheme,
} from '@mui/material';
import { ArrowLeft, Bot } from 'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../../services/api';
import { useWorkspace } from '../../context/WorkspaceContext';

const DISPLAY = `'Sora', 'Inter', sans-serif`;

const VACIO = {
  name: '', description: '', instructions: '', model: '',
  system_ids: [], skill_ids: [], space_ids: [],
};

/**
 * Crear un agente, y editar uno que ya existe.
 *
 * Es la misma pantalla para las dos cosas: con `:id` en la ruta carga el agente y
 * guarda con PATCH, sin `:id` crea. Separarlas dejaba dos formularios que hay que
 * mantener iguales a mano.
 *
 * Lo que NO esta aca, a proposito: las Herramientas (hoy son las mismas para todos
 * los agentes, no se eligen por agente) y los Disparadores (cuelgan de una
 * Automatizacion, no del agente). Un selector para cualquiera de las dos seria
 * decorativo.
 */
export default function AgenteNuevoPage() {
  const { id } = useParams();
  const editando = Boolean(id);
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const navigate = useNavigate();
  const { slug } = useWorkspace();

  const textMuted = d ? 'rgba(255,255,255,0.66)' : 'rgba(0,0,0,0.62)';
  const bgSuave = d ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.02)';
  const borde = theme.palette.divider;

  const [form, setForm] = useState(VACIO);
  const [opciones, setOpciones] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [handle, setHandle] = useState('');

  const campoSx = useMemo(() => ({
    '& .MuiOutlinedInput-root': {
      bgcolor: bgSuave, borderRadius: '8px', fontSize: '0.9375rem',
      '& fieldset': { borderColor: borde },
      '&.Mui-focused fieldset': { borderColor: '#586AD0' },
    },
  }), [bgSuave, borde]);

  const cargar = useCallback(async () => {
    if (!slug) return;
    try {
      setCargando(true);
      const pedidos = [api.getBuilderOptions(slug)];
      if (editando) pedidos.push(api.getBuilderAgent(id, slug));
      const [{ data: opts }, agente] = await Promise.all(pedidos);
      setOpciones(opts);
      if (agente) {
        const a = agente.data;
        setHandle(a.handle || '');
        setForm({
          name: a.name || '', description: a.description || '',
          instructions: a.instructions || '', model: a.model || '',
          system_ids: a.system_ids || [], skill_ids: a.skill_ids || [],
          space_ids: a.space_ids || [],
        });
      }
    } catch (e) {
      if (e.response?.status === 403) {
        toast.error(e.response.data.detail);
      } else {
        toast.error('No se pudo abrir el constructor.');
      }
      navigate('/app/agentes');
    } finally {
      setCargando(false);
    }
  }, [slug, id, editando, navigate]);

  useEffect(() => { cargar(); }, [cargar]);

  const alternar = (clave, valor) => {
    setForm((f) => ({
      ...f,
      [clave]: f[clave].includes(valor)
        ? f[clave].filter((v) => v !== valor)
        : [...f[clave], valor],
    }));
  };

  const guardar = async () => {
    if (!form.name.trim()) {
      toast.error('El agente necesita un nombre.');
      return;
    }
    try {
      setGuardando(true);
      const cuerpo = { workspace: slug, ...form, name: form.name.trim() };
      const { data } = editando
        ? await api.updateBuilderAgent(id, cuerpo)
        : await api.buildAgent(cuerpo);
      toast.success(
        editando
          ? `${data.name} quedó actualizado.`
          : `${data.name} ya existe. Se lo menciona con @${data.handle}.`,
      );
      // Cae en el chat con él: un agente que se acaba de crear y no se puede
      // probar en el mismo momento es un formulario, no un agente.
      navigate('/app/chat', { state: { agentId: data.id, agentName: data.name } });
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

  if (!opciones?.puede_crear) {
    return (
      <Box sx={{ maxWidth: 900, mx: 'auto', px: 5, py: 6 }}>
        <Typography sx={{ color: textMuted, fontSize: '0.9375rem' }}>
          En este Workspace solo los editores y administradores crean agentes.
          Un administrador puede cambiarlo en Admin › Workspace.
        </Typography>
      </Box>
    );
  }

  const modelos = opciones.modelos?.models || [];

  return (
    <Box sx={{ maxWidth: 900, mx: 'auto', px: { xs: 2.5, md: 5 }, py: { xs: 4, md: 6 }, width: '100%' }}>
      <Button
        onClick={() => navigate('/app/agentes')}
        startIcon={<ArrowLeft size={15} />}
        sx={{ textTransform: 'none', color: textMuted, fontSize: '0.875rem', mb: 2, ml: -1 }}
      >
        Agentes
      </Button>

      <Bot size={24} color={d ? 'rgba(255,255,255,0.82)' : 'rgba(0,0,0,0.76)'} strokeWidth={1.75} />
      <Typography sx={{ fontFamily: DISPLAY, fontSize: '1.875rem', fontWeight: 600, letterSpacing: '-0.01em', mt: 1.5 }}>
        {editando ? form.name : 'Agente nuevo'}
      </Typography>
      <Typography sx={{ color: textMuted, fontSize: '0.9375rem', mt: 0.75 }}>
        {editando
          ? `Se lo menciona con @${handle}. El nombre se puede cambiar; la mención no, para no romper las conversaciones que ya lo nombran.`
          : 'Un asistente con un oficio, sus propias instrucciones y acceso solo a lo que usted le dé.'}
      </Typography>

      <Seccion titulo="Cómo se llama" ayuda="El nombre con el que aparece en la galería y en las conversaciones.">
        <TextField
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
          placeholder="Analista de Cobranzas"
          fullWidth size="small" sx={campoSx}
        />
      </Seccion>

      <Seccion titulo="Para qué sirve" ayuda="Una línea. Es lo que su equipo lee en la galería para saber cuándo usarlo.">
        <TextField
          value={form.description}
          onChange={(e) => setForm({ ...form, description: e.target.value })}
          placeholder="Revisa facturas vencidas y prepara el resumen de cobranza de la semana."
          fullWidth size="small" sx={campoSx}
        />
      </Seccion>

      <Seccion
        titulo="Instrucciones"
        ayuda="Cómo tiene que comportarse, en sus palabras: qué hace, qué tono usa, qué no debe hacer nunca. Es lo que más define al agente."
      >
        <TextField
          value={form.instructions}
          onChange={(e) => setForm({ ...form, instructions: e.target.value })}
          placeholder={'Eres el analista de cobranzas de la empresa. Cuando te pregunten por deuda, '
            + 'parte siempre por el total y después el detalle por cliente. Nunca informes un monto '
            + 'sin decir de qué fecha es. Si un dato no está en los sistemas, dilo en vez de estimarlo.'}
          multiline minRows={6} fullWidth size="small" sx={campoSx}
        />
      </Seccion>

      <Seccion titulo="Qué modelo usa" ayuda="Vacío deja el modelo por defecto del Workspace.">
        <TextField
          select
          value={form.model}
          onChange={(e) => setForm({ ...form, model: e.target.value })}
          fullWidth size="small" sx={campoSx}
        >
          <MenuItem value="">
            <span style={{ color: textMuted }}>El del Workspace ({opciones.modelos?.default || 'sin definir'})</span>
          </MenuItem>
          {modelos.map((m) => (
            <MenuItem key={m.id} value={m.id} sx={{ fontSize: '0.9375rem' }}>
              {m.label} {m.kind ? `· ${m.kind}` : ''}
            </MenuItem>
          ))}
        </TextField>
      </Seccion>

      <Elegibles
        titulo="A qué sistemas mira"
        ayuda="Los sistemas conectados que puede consultar. Sin ninguno elegido, alcanza todos los de la empresa."
        vacio="Todavía no hay sistemas conectados. Se conectan en Contexto › Integraciones."
        items={opciones.sistemas}
        etiqueta={(s) => `${s.name} · ${s.connector_type}`}
        elegidos={form.system_ids}
        onAlternar={(v) => alternar('system_ids', v)}
      />

      <Elegibles
        titulo="Qué habilidades usa"
        ayuda="Bloques de instrucciones que comparte con otros agentes, por ejemplo el tono con el que se le habla a un cliente."
        vacio="Todavía no hay habilidades. Se crean en Admin › Agentes › Habilidades."
        items={opciones.habilidades}
        etiqueta={(s) => s.name}
        elegidos={form.skill_ids}
        onAlternar={(v) => alternar('skill_ids', v)}
      />

      <Elegibles
        titulo="En qué espacios vive"
        ayuda="Un agente dentro de un Espacio solo alcanza las fuentes de ese Espacio. Sin ninguno, alcanza todo lo de la empresa."
        vacio="Todavía no hay espacios. Se crean en Contexto › Espacios."
        items={opciones.espacios}
        etiqueta={(e) => `${e.name}${e.visibility === 'restringido' ? ' · restringido' : ''}`}
        elegidos={form.space_ids}
        onAlternar={(v) => alternar('space_ids', v)}
      />

      <Button
        onClick={guardar}
        disabled={guardando}
        variant="contained"
        sx={{ mt: 5, borderRadius: '8px', textTransform: 'none', fontWeight: 600, px: 3 }}
      >
        {guardando ? 'Guardando…' : editando ? 'Guardar cambios' : 'Crear agente'}
      </Button>

      <Typography sx={{ color: textMuted, fontSize: '0.8125rem', mt: 2 }}>
        {editando
          ? 'Al guardar se abre una conversación con él para probarlo.'
          : 'Al crearlo se abre una conversación para probarlo. Queda pendiente en Admin › Agentes '
            + 'hasta que la empresa le diga con qué datos y reglas trabaja.'}
      </Typography>
    </Box>
  );
}

function Seccion({ titulo, ayuda, children }) {
  const theme = useTheme();
  const textMuted = theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.66)' : 'rgba(0,0,0,0.62)';
  return (
    <Box sx={{ mt: 4 }}>
      <Typography sx={{ fontSize: '1rem', fontWeight: 600 }}>{titulo}</Typography>
      <Typography sx={{ fontSize: '0.875rem', color: textMuted, mt: 0.5, mb: 1.5 }}>{ayuda}</Typography>
      {children}
    </Box>
  );
}

/**
 * Una lista de cosas que se marcan y desmarcan.
 *
 * Cuando no hay ninguna, dice DONDE se crean en vez de mostrar un hueco: una
 * seccion vacia sin salida es la forma mas rapida de que alguien crea que la
 * funcionalidad no existe.
 */
function Elegibles({ titulo, ayuda, vacio, items, etiqueta, elegidos, onAlternar }) {
  const theme = useTheme();
  const textMuted = theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.66)' : 'rgba(0,0,0,0.62)';
  const lista = items || [];
  return (
    <Seccion titulo={titulo} ayuda={ayuda}>
      {lista.length === 0 ? (
        <Typography sx={{ fontSize: '0.875rem', color: textMuted, fontStyle: 'italic' }}>
          {vacio}
        </Typography>
      ) : (
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
          {lista.map((item) => {
            const activo = elegidos.includes(item.id);
            return (
              <Chip
                key={item.id}
                label={etiqueta(item)}
                onClick={() => onAlternar(item.id)}
                variant={activo ? 'filled' : 'outlined'}
                sx={{
                  borderRadius: '8px', fontSize: '0.875rem', cursor: 'pointer',
                  ...(activo
                    ? { bgcolor: 'rgba(88, 106, 208, 0.16)', color: '#586AD0', border: '1px solid rgba(88, 106, 208, 0.4)', fontWeight: 600 }
                    : { borderColor: theme.palette.divider, color: textMuted }),
                }}
              />
            );
          })}
        </Box>
      )}
    </Seccion>
  );
}
