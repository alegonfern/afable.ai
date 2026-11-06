import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Autocomplete, Box, Button, Chip, CircularProgress, MenuItem, Select, Switch, TextField, Tooltip, Typography,
} from '@mui/material';
import { Bell, CalendarClock, Mail, MessageCircle, Play, Users, Zap } from 'lucide-react';
import { toast } from 'react-toastify';
import PageHeader from '../../components/PageHeader';
import { useWorkspace } from '../../context/WorkspaceContext';
import { api } from '../../services/api';
import { MODULOS } from '../../layout/Dashboard/modulos';
import { Entra, MotionBox } from '../../components/Animado';
import { conPasos } from '../../components/ProgresoFlotante';
import { TONOS } from '../../theme/tonos';

/*
 * La vista Automatización de cada módulo (18-10-2026): lo que Afable hace solo. Es un
 * catálogo que la empresa activa. Desde el 22-10-2026 cada una se programa (cada día, semana
 * o mes, y a qué hora), tiene seguidores (a quién avisa; sin seguidores, a administradores y
 * editores) y avisa por la campana, el correo y WhatsApp.
 */

const SORA = "'Sora', sans-serif";
const DIAS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'];
const HORAS = Array.from({ length: 24 }, (_, h) => h);
const DIAS_MES = Array.from({ length: 28 }, (_, d) => d + 1);
const selectSx = { fontSize: '0.82rem', '& .MuiSelect-select': { py: 0.5 } };
const fecha = (iso) => new Date(iso).toLocaleString('es-CL', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });

function Fila({ icono: Icono, titulo, children }) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25, flexWrap: 'wrap', py: 0.75 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, width: 120, color: 'text.secondary', fontSize: '0.8rem' }}>
        <Icono size={14} /> {titulo}
      </Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap', flex: 1, minWidth: 0 }}>{children}</Box>
    </Box>
  );
}

function Programacion({ a, editable, cambiar }) {
  const p = a.programacion;
  if (!editable) return <Typography sx={{ fontSize: '0.82rem' }}>{a.cuando}</Typography>;
  return (
    <>
      <Select size="small" value={p.frecuencia} onChange={(e) => cambiar({ frecuencia: e.target.value })} sx={selectSx}>
        <MenuItem value="diaria">Cada día</MenuItem>
        <MenuItem value="semanal">Cada semana</MenuItem>
        <MenuItem value="mensual">Cada mes</MenuItem>
      </Select>
      {p.frecuencia === 'semanal' && (
        <Select size="small" value={p.dia_semana} onChange={(e) => cambiar({ dia_semana: e.target.value })} sx={selectSx}>
          {DIAS.map((d, i) => <MenuItem key={d} value={i}>{d}</MenuItem>)}
        </Select>
      )}
      {p.frecuencia === 'mensual' && (
        <Select size="small" value={p.dia_mes} onChange={(e) => cambiar({ dia_mes: e.target.value })} sx={selectSx}
          renderValue={(v) => `El día ${v}`}>
          {DIAS_MES.map((d) => <MenuItem key={d} value={d}>{d}</MenuItem>)}
        </Select>
      )}
      <Select size="small" value={p.hora} onChange={(e) => cambiar({ hora: e.target.value })} sx={selectSx}
        renderValue={(v) => `a las ${String(v).padStart(2, '0')}:00`}>
        {HORAS.map((h) => <MenuItem key={h} value={h}>{String(h).padStart(2, '0')}:00</MenuItem>)}
      </Select>
    </>
  );
}

function Tarjeta({ a, slug, esEditor, miembros, onCambio }) {
  const [prueba, setPrueba] = useState(null);
  const [probando, setProbando] = useState(false);
  const cambiar = async (datos) => {
    try {
      const { data } = await api.finanzas.actualizarAutomatizacion(slug, a.clave, datos);
      onCambio(data);
    } catch (e) { toast.error(e.response?.data?.detail || 'No se pudo guardar.'); }
  };
  const probar = async () => {
    setProbando(true);
    try {
      const { data } = await conPasos(['Revisando qué haría la automatización', 'Preparando el resultado de la prueba'],
        () => api.finanzas.probarAutomatizacion(slug, a.clave));
      setPrueba(data);
    } catch { toast.error('No se pudo probar ahora.'); } finally { setProbando(false); }
  };
  const editable = a.activa && esEditor;
  const seguidores = miembros.filter((m) => a.seguidores.includes(m.id));
  // A quién le llega: los seguidores o, sin seguidores, administradores y editores.
  const reciben = seguidores.length ? seguidores : miembros.filter((m) => m.role === 'admin' || m.role === 'editor');
  const sinWhatsapp = a.por_whatsapp ? reciben.filter((m) => !m.tiene_whatsapp) : [];

  return (
    // Al activarla, la tarjeta se ilumina un instante con el color de Afable.
    <MotionBox
      initial={false}
      animate={{ boxShadow: a.activa ? ['0 0 0 0 rgba(11,11,15,0.25)', '0 0 0 8px rgba(11,11,15,0)'] : '0 0 0 0 rgba(11,11,15,0)' }}
      transition={{ duration: 0.7, ease: 'easeOut' }}
      sx={{ border: '1px solid', borderColor: a.activa ? 'var(--af-color)' : 'divider', borderRadius: '14px', p: 2.5, bgcolor: 'background.paper', transition: 'border-color .2s' }}>
      <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2 }}>
        <Box sx={{ display: 'flex', p: 1, borderRadius: '10px', bgcolor: a.activa ? TONOS.pizarra.suave : 'action.hover', color: a.activa ? TONOS.pizarra.color : 'text.secondary' }}>
          <Zap size={18} />
        </Box>
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography sx={{ fontWeight: 600, fontSize: '1rem' }}>{a.nombre}</Typography>
          <Typography sx={{ fontSize: '0.86rem', color: 'text.secondary', mt: 0.25, lineHeight: 1.55 }}>{a.descripcion}</Typography>
          {!a.activa && <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary', mt: 1 }}>{a.cuando}</Typography>}
        </Box>
        <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 1 }}>
          <Switch checked={a.activa} disabled={!esEditor} onChange={(e) => cambiar({ activa: e.target.checked })}
            inputProps={{ 'aria-label': `Activar ${a.nombre}` }} />
          <Button size="small" startIcon={probando ? <CircularProgress size={12} /> : <Play size={13} />} onClick={probar} disabled={probando}>Probar ahora</Button>
        </Box>
      </Box>

      {a.activa && (
        <Box sx={{ mt: 1.5, pt: 1, borderTop: '1px solid', borderColor: 'divider' }}>
          <Fila icono={CalendarClock} titulo="Programación">
            <Programacion a={a} editable={editable} cambiar={cambiar} />
            {a.proxima_ejecucion && (
              <Typography sx={{ fontSize: '0.76rem', color: 'text.secondary' }}>Próxima: {fecha(a.proxima_ejecucion)}</Typography>
            )}
          </Fila>
          <Fila icono={Users} titulo="Seguidores">
            {editable ? (
              <Autocomplete multiple size="small" options={miembros} value={seguidores} disableCloseOnSelect
                getOptionLabel={(m) => m.full_name || m.email} isOptionEqualToValue={(o, v) => o.id === v.id}
                onChange={(_, v) => cambiar({ seguidores: v.map((m) => m.id) })}
                renderTags={(v, getTagProps) => v.map((m, i) => (
                  <Chip size="small" label={m.full_name || m.email} {...getTagProps({ index: i })} key={m.id} />
                ))}
                renderInput={(params) => (
                  <TextField {...params} placeholder={seguidores.length ? '' : 'Administradores y editores'}
                    sx={{ '& .MuiInputBase-root': { fontSize: '0.82rem', py: '2px !important' } }} />
                )}
                sx={{ flex: 1, minWidth: 220, maxWidth: 520 }} />
            ) : (
              <Typography sx={{ fontSize: '0.82rem' }}>
                {seguidores.length ? seguidores.map((m) => m.full_name || m.email).join(', ') : 'Administradores y editores'}
              </Typography>
            )}
          </Fila>
          <Fila icono={Bell} titulo="Avisar por">
            <Chip size="small" icon={<Bell size={12} />} label="Campana" />
            <Box component="label" sx={{ fontSize: '0.8rem', display: 'flex', alignItems: 'center', cursor: editable ? 'pointer' : 'default' }}>
              <Switch size="small" checked={a.por_correo} disabled={!editable} onChange={(e) => cambiar({ por_correo: e.target.checked })} />
              <Mail size={13} style={{ marginRight: 4 }} /> Correo
            </Box>
            <Tooltip arrow title={a.whatsapp_configurado ? '' : 'WhatsApp todavía no está conectado en el servidor de Afable: puede dejarlo activo y empezará a llegar cuando se conecte.'}>
              <Box component="label" sx={{ fontSize: '0.8rem', display: 'flex', alignItems: 'center', cursor: editable ? 'pointer' : 'default' }}>
                <Switch size="small" checked={a.por_whatsapp} disabled={!editable} onChange={(e) => cambiar({ por_whatsapp: e.target.checked })} />
                <MessageCircle size={13} style={{ marginRight: 4 }} /> WhatsApp
              </Box>
            </Tooltip>
          </Fila>
          {a.por_whatsapp && sinWhatsapp.length > 0 && (
            <Typography sx={{ fontSize: '0.76rem', color: 'warning.main', pl: '130px' }}>
              Sin WhatsApp en su perfil (no les llegará por ahí): {sinWhatsapp.map((m) => m.full_name || m.email).join(', ')}.
            </Typography>
          )}
          {a.por_whatsapp && !a.whatsapp_configurado && (
            <Typography sx={{ fontSize: '0.76rem', color: 'text.secondary', pl: '130px' }}>
              WhatsApp todavía no está conectado en el servidor: empezará a llegar cuando se conecte.
            </Typography>
          )}
        </Box>
      )}

      {a.ultima_ejecucion && (
        <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary', mt: 1 }}>
          Última revisión: {fecha(a.ultima_ejecucion)} · {a.ultimo_resultado || '—'}
        </Typography>
      )}
      {prueba && (
        <Box sx={{ mt: 1.5, p: 1.5, borderRadius: '10px', bgcolor: 'action.hover' }}>
          <Typography sx={{ fontSize: '0.76rem', fontWeight: 600, color: 'text.secondary', mb: 0.25 }}>ASÍ AVISARÍA HOY (no se envió)</Typography>
          {prueba.aviso
            ? <><Typography sx={{ fontWeight: 600, fontSize: '0.9rem' }}>{prueba.titulo}</Typography><Typography sx={{ fontSize: '0.86rem' }}>{prueba.detalle}</Typography></>
            : <Typography sx={{ fontSize: '0.86rem' }}>{prueba.detalle}</Typography>}
        </Box>
      )}
    </MotionBox>
  );
}

// `embebida`: dentro de la vista "Agente" del módulo (AgentePage, 25-10-2026), solo la lista.
export default function AutomatizacionesPage({ modulo, embebida = false }) {
  const navigate = useNavigate();
  const { slug, esEditor } = useWorkspace();
  const [lista, setLista] = useState(null);
  const [miembros, setMiembros] = useState([]);
  const nombre = MODULOS.find((m) => m.slug === modulo)?.label || modulo;
  useEffect(() => {
    if (!slug) return;
    api.finanzas.automatizaciones(slug, modulo).then(({ data }) => setLista(data));
    api.getMembers(slug).then(({ data }) => setMiembros((data.results || data).map((m) => ({ ...m.user, role: m.role })))).catch(() => {});
  }, [slug, modulo]);
  if (embebida) {
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.25 }}>
        {!slug ? null : !lista ? <CircularProgress size={18} /> : lista.map((a, i) => (
          <Entra key={a.clave} retraso={0.04 * i}>
            <Tarjeta a={a} slug={slug} esEditor={esEditor} miembros={miembros}
              onCambio={(nuevo) => setLista((l) => l.map((x) => (x.clave === nuevo.clave ? nuevo : x)))} />
          </Entra>
        ))}
      </Box>
    );
  }
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', minWidth: 0, width: '100%' }}>
      <PageHeader title="Automatizaciones" crumbs={[{ label: nombre, to: `/app/${modulo}` }]} back="/app" backLabel="Inicio" />
      <Box sx={{ flex: 1, overflow: 'auto', px: 3, py: 2.5, display: 'flex', flexDirection: 'column', gap: 1.5, maxWidth: 900 }}>
        <Typography sx={{ fontFamily: SORA, fontWeight: 600, fontSize: '1.25rem' }}>Lo que Afable hace solo con {nombre.toLowerCase()}</Typography>
        <Typography sx={{ fontSize: '0.88rem', color: 'text.secondary', mb: 1 }}>
          Active las que le sirvan, elija cada cuánto corren y a quién avisan. Afable avisa solo cuando hay algo que decir.
        </Typography>
        {!slug ? <Typography sx={{ color: 'text.secondary' }}>Primero tiene que crear su empresa en Afable.</Typography>
          : !lista ? <CircularProgress size={20} /> : lista.map((a, i) => (
            <Entra key={a.clave} retraso={0.04 * i}>
              <Tarjeta a={a} slug={slug} esEditor={esEditor} miembros={miembros}
                onCambio={(nuevo) => setLista((l) => l.map((x) => (x.clave === nuevo.clave ? nuevo : x)))} />
            </Entra>
          ))}
        <Button size="small" sx={{ alignSelf: 'flex-start', mt: 1 }} onClick={() => navigate('/app/chat')}>
          ¿Necesita otra? Pídasela al chat
        </Button>
      </Box>
    </Box>
  );
}
