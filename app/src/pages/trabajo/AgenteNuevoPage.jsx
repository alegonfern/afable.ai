import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Box, Button, Chip, CircularProgress, MenuItem, TextField, Typography, useTheme,
} from '@mui/material';
import { ArrowLeft, Bot, FolderOpen, Plug } from 'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../../services/api';
import { useWorkspace } from '../../context/WorkspaceContext';

const DISPLAY = `'Sora', 'Inter', sans-serif`;

const VACIO = {
  name: '', description: '', instructions: '', model: '',
  system_ids: [], skill_ids: [], space_ids: [],
  datos: '', reglas: '', info_util: '',
};

// Lo que la EMPRESA le entrega a este agente. Antes vivía en una pantalla aparte
// (Admin › Agentes › configurar), así que había dos lugares para configurar el mismo
// agente y ninguno mencionaba al otro. Solo lo ve un administrador: sigue siendo una
// decisión de la empresa y no de quien construye el agente.
const CAMPOS_DE_EMPRESA = [
  {
    clave: 'datos',
    titulo: 'Qué datos puede mirar',
    ayuda: 'Nombre las tablas, sistemas o documentos que puede consultar, y los que no.',
    placeholder: 'Ventas y facturas de Odoo. Los documentos de la carpeta Contabilidad.',
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
  // De dónde cuelga el agente nuevo. Mientras esté vacío no se muestra el formulario:
  // es lo que impide crear un agente sobre la nada.
  const [origenes, setOrigenes] = useState(null);
  const [origen, setOrigen] = useState(null);
  const [preparando, setPreparando] = useState(false);
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
          datos: a.datos || '', reglas: a.reglas || '', info_util: a.info_util || '',
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

  useEffect(() => {
    if (editando || !slug) return;
    api.getOrigenesDeAgente(slug)
      .then(({ data }) => setOrigenes(data))
      .catch(() => setOrigenes({ carpetas: [], herramientas: [] }));
  }, [slug, editando]);

  // Elegir una carpeta no abre un formulario vacío: Afable mira lo que hay adentro y lo
  // deja escrito. La persona corrige si quiere, pero nunca parte de cero.
  const elegirCarpeta = async (carpeta) => {
    setPreparando(true);
    try {
      const { data } = await api.redactarPropuestaDeAgente(slug, carpeta.id);
      setForm((f) => ({
        ...f,
        name: data.nombre || carpeta.nombre,
        description: data.descripcion || '',
        instructions: data.instrucciones || '',
      }));
      setOrigen({ tipo: 'carpeta', id: carpeta.id, nombre: carpeta.ruta || carpeta.nombre });
    } catch {
      // Si no se pudo redactar, igual se sigue: peor es dejar a la persona trabada.
      setForm((f) => ({ ...f, name: carpeta.nombre }));
      setOrigen({ tipo: 'carpeta', id: carpeta.id, nombre: carpeta.ruta || carpeta.nombre });
    } finally {
      setPreparando(false);
    }
  };

  const elegirHerramienta = (h) => {
    setForm((f) => ({ ...f, name: f.name || h.nombre, system_ids: [h.id] }));
    setOrigen({ tipo: 'herramienta', id: h.id, nombre: h.nombre });
  };

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
      if (!editando && origen?.tipo === 'carpeta') cuerpo.carpeta = origen.id;
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

  // ⛔ Sin material no hay agente. El material es una carpeta con documentos o una
  // herramienta conectada — ninguno de los dos es una pantalla en blanco, que es lo que
  // esta regla existe para prohibir. Editar no pasa por acá: ese agente ya tiene origen.
  if (!editando && !origen) {
    const carpetas = origenes?.carpetas || [];
    const herramientas = origenes?.herramientas || [];
    const hayDonde = carpetas.length > 0 || herramientas.length > 0;

    const Opcion = ({ icono, titulo, detalle, onClick }) => (
      <Box
        component="button" onClick={onClick} disabled={preparando}
        sx={{
          display: 'flex', alignItems: 'center', gap: 1.25, width: '100%',
          px: 1.75, py: 1.4, mb: 1, borderRadius: '9px', cursor: 'pointer',
          fontFamily: 'inherit', textAlign: 'left', bgcolor: bgSuave,
          border: `1px solid ${borde}`, color: 'inherit',
          '&:hover': { borderColor: '#586AD0' },
          '&:disabled': { opacity: 0.6, cursor: 'default' },
          transition: 'border-color 0.12s',
        }}
      >
        <Box sx={{ color: textMuted, display: 'flex' }}>{icono}</Box>
        <Box sx={{ minWidth: 0 }}>
          <Typography sx={{ fontSize: '0.9375rem', color: 'text.primary' }}>{titulo}</Typography>
          <Typography sx={{ fontSize: '0.8125rem', color: textMuted }}>{detalle}</Typography>
        </Box>
      </Box>
    );

    return (
      <Box sx={{ maxWidth: 700, mx: 'auto', px: { xs: 2.5, md: 5 }, py: { xs: 4, md: 6 }, width: '100%' }}>
        <Button
          onClick={() => navigate('/app/agentes')}
          startIcon={<ArrowLeft size={15} />}
          sx={{ textTransform: 'none', color: textMuted, fontSize: '0.875rem', mb: 2, ml: -1 }}
        >
          Agentes
        </Button>

        <Typography sx={{ fontSize: '1.35rem', fontWeight: 700, mb: 0.5 }}>
          ¿Sobre qué va a trabajar?
        </Typography>
        <Typography sx={{ fontSize: '0.9375rem', color: textMuted, mb: 3 }}>
          {hayDonde
            ? 'Un agente responde sobre algo concreto. Elija de dónde saca lo que sabe.'
            : 'Todavía no hay sobre qué. Un agente necesita material para poder responder.'}
        </Typography>

        {preparando && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25, mb: 2 }}>
            <CircularProgress size={15} sx={{ color: '#586AD0' }} />
            <Typography sx={{ fontSize: '0.875rem', color: textMuted }}>
              Mirando lo que hay en la carpeta…
            </Typography>
          </Box>
        )}

        {carpetas.length > 0 && (
          <>
            <Typography sx={{ fontSize: '0.78rem', fontWeight: 600, color: textMuted,
                              textTransform: 'uppercase', letterSpacing: '0.06em', mb: 1 }}>
              Sus carpetas
            </Typography>
            {carpetas.map((c) => (
              <Opcion
                key={`c-${c.id}`} icono={<FolderOpen size={17} />}
                titulo={c.nombre} detalle={`${c.documentos} documentos · ${c.ruta}`}
                onClick={() => elegirCarpeta(c)}
              />
            ))}
          </>
        )}

        {herramientas.length > 0 && (
          <>
            <Typography sx={{ fontSize: '0.78rem', fontWeight: 600, color: textMuted,
                              textTransform: 'uppercase', letterSpacing: '0.06em', mt: 2.5, mb: 1 }}>
              Sus herramientas
            </Typography>
            {herramientas.map((h) => (
              <Opcion
                key={`h-${h.id}`} icono={<Plug size={17} />}
                titulo={h.nombre} detalle={`Consulta en vivo · ${h.tipo}`}
                onClick={() => elegirHerramienta(h)}
              />
            ))}
          </>
        )}

        {/* La IA como andamio: quien llega sin nada no ve un formulario que no sabe
            llenar, ve el paso que le falta. */}
        {origenes && !hayDonde && (
          <Box sx={{ display: 'flex', gap: 1, mt: 1 }}>
            <Button onClick={() => navigate('/app/archivos')} sx={{ textTransform: 'none' }}>
              Subir documentos
            </Button>
            <Button
              onClick={() => navigate('/app/contexto?tab=integraciones')}
              sx={{ textTransform: 'none' }}
            >
              Conectar una herramienta
            </Button>
          </Box>
        )}
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

      <Seccion titulo="Qué modelo usa" ayuda="Vacío deja el modelo por defecto de la Empresa.">
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

      {/* Solo para administradores: el backend ignora estos campos sin ese rol. */}
      {opciones.puede_configurar_empresa && (
        <>
          <Box sx={{ mt: 5, pt: 4, borderTop: `1px solid ${borde}` }}>
            <Typography sx={{ fontFamily: DISPLAY, fontSize: '1.125rem', fontWeight: 600 }}>
              Lo que la empresa le entrega
            </Typography>
            <Typography sx={{ fontSize: '0.875rem', color: textMuted, mt: 0.5 }}>
              El agente llega sabiendo su oficio; lo que no sabe es nada de ESTA empresa.
              Esto entra en cada una de sus respuestas.
            </Typography>
          </Box>
          {CAMPOS_DE_EMPRESA.map((campo) => (
            <Seccion key={campo.clave} titulo={campo.titulo} ayuda={campo.ayuda}>
              <TextField
                value={form[campo.clave]}
                onChange={(e) => setForm({ ...form, [campo.clave]: e.target.value })}
                placeholder={campo.placeholder}
                multiline minRows={3} fullWidth size="small" sx={campoSx}
              />
            </Seccion>
          ))}
        </>
      )}

      <Elegibles
        titulo="En qué workspaces vive"
        ayuda="Un agente dentro de un Workspace solo alcanza las fuentes de ese Workspace. Sin ninguno, alcanza todo lo de la empresa."
        vacio="Todavía no hay workspaces. Se crean en Contexto › Workspaces."
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
