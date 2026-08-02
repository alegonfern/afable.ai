import { useState, useEffect } from 'react';
import {
  Box, Typography, TextField, CircularProgress, useTheme, Collapse, Switch, MenuItem,
} from '@mui/material';
import { Timer, Plus, Play, Trash2, ChevronDown, ChevronRight, Mail, Clock, Zap, ArrowRight, MessageSquare, Database } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { toast } from 'react-toastify';
import { api } from '../services/api';
import PageHeader from '../components/PageHeader';
import { useApp } from '../context/AppContext';

const fmtDate = (iso) => iso ? new Date(iso).toLocaleString('es-CL', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : 'nunca';

const EVENT_LABELS = {
  new_table: 'Nueva tabla o base de datos',
  new_rows: 'Nuevas filas en una tabla',
  connection_down: 'Conexión caída',
};

function FlowNode({ icon, label, active, d }) {
  return (
    <Box sx={{
      display: 'inline-flex', alignItems: 'center', gap: 0.6, px: 1.25, py: 0.5,
      borderRadius: '999px', fontSize: '0.75rem', fontWeight: 600, whiteSpace: 'nowrap',
      border: `1px solid ${active ? '#586AD0' : (d ? 'rgba(255,255,255,0.15)' : 'rgba(0,0,0,0.15)')}`,
      bgcolor: active ? 'rgba(88,106,208,0.15)' : 'transparent',
      color: active ? (d ? '#9BA6E3' : '#586AD0') : (d ? 'rgba(255,255,255,0.35)' : 'rgba(0,0,0,0.35)'),
    }}>
      {icon} {label}
    </Box>
  );
}

function FieldLabel({ children, textMuted }) {
  return (
    <Typography sx={{ fontSize: '0.7rem', fontWeight: 700, letterSpacing: '0.04em', textTransform: 'uppercase', color: textMuted, mb: 1 }}>
      {children}
    </Typography>
  );
}

export default function AutomationsPage() {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const { selectedOrganization, currentUser } = useApp();

  const textMuted = d ? 'rgba(255,255,255,0.45)' : 'rgba(0,0,0,0.45)';
  const textSemi = d ? 'rgba(255,255,255,0.70)' : 'rgba(0,0,0,0.70)';
  const bgCard = d ? 'rgba(255,255,255,0.04)' : theme.palette.background.paper;
  const borderColor = theme.palette.divider;

  const inputSx = {
    '& .MuiOutlinedInput-root': {
      bgcolor: d ? 'rgba(255,255,255,0.04)' : theme.palette.background.paper,
      borderRadius: '8px', fontSize: '0.875rem', color: theme.palette.text.primary,
      '& fieldset': { borderColor },
      '&:hover fieldset': { borderColor: d ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.2)' },
      '&.Mui-focused fieldset': { borderColor: '#586AD0' },
    },
    '& .MuiInputLabel-root': { color: textMuted, fontSize: '0.875rem' },
    '& .MuiInputLabel-root.Mui-focused': { color: '#9BA6E3' },
  };

  const emptyForm = {
    name: '', prompt: '', interval_minutes: 60, notify_email: '',
    trigger_type: 'interval', connection: '', event_type: 'new_table', event_table: '',
  };
  const [autos, setAutos] = useState([]);
  const [connections, setConnections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [runningId, setRunningId] = useState(null);
  const [expandedId, setExpandedId] = useState(null);
  const [form, setForm] = useState(emptyForm);

  useEffect(() => {
    api.getAutomations().then(r => setAutos(r.data)).catch(() => {}).finally(() => setLoading(false));
    api.getConnections().then(r => setConnections(r.data)).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (currentUser?.email && !form.notify_email) {
      setForm(prev => ({ ...prev, notify_email: currentUser.email }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentUser]);

  const isEvent = form.trigger_type === 'event';

  const handleCreate = async () => {
    if (!form.name.trim() || !form.notify_email.trim()) {
      toast.error('Completa nombre y correo.');
      return;
    }
    if (!isEvent && !form.prompt.trim()) {
      toast.error('Las programadas necesitan un prompt.');
      return;
    }
    if (isEvent && !form.connection) {
      toast.error('Elige qué conexión vigilar.');
      return;
    }
    if (isEvent && form.event_type === 'new_rows' && !form.event_table.trim()) {
      toast.error('Indica la tabla (o modelo Odoo) a vigilar.');
      return;
    }
    if (!selectedOrganization?.id) {
      toast.error('Primero configure su Workspace.');
      return;
    }
    if (selectedOrganization.nombre === 'Personal') {
      toast.error('Las automatizaciones no funcionan en "Personal" — cambia a una empresa real arriba.');
      return;
    }
    setSaving(true);
    try {
      const payload = {
        name: form.name, prompt: form.prompt, interval_minutes: form.interval_minutes,
        notify_email: form.notify_email, trigger_type: form.trigger_type,
        organization: selectedOrganization.id,
      };
      if (isEvent) {
        payload.connection = form.connection;
        payload.event_type = form.event_type;
        payload.event_config = form.event_type === 'new_rows' ? { table: form.event_table.trim() } : {};
      }
      const res = await api.createAutomation(payload);
      setAutos(prev => [res.data, ...prev]);
      setForm({ ...emptyForm, notify_email: currentUser?.email || '' });
      setShowForm(false);
      toast.success(isEvent
        ? 'Automatización creada. Afable vigilará el evento según el intervalo de revisión.'
        : 'Automatización creada. Se ejecutará según su intervalo.');
    } catch (e) {
      const d = e.response?.data || {};
      toast.error(d.interval_minutes?.[0] || d.connection?.[0] || d.event_type?.[0]
        || d.event_config?.[0] || d.prompt?.[0] || d.organization?.[0] || 'Error al crear la automatización');
    } finally {
      setSaving(false);
    }
  };

  const handleToggle = async (auto) => {
    try {
      const res = await api.updateAutomation(auto.id, { is_active: !auto.is_active });
      setAutos(prev => prev.map(a => a.id === auto.id ? res.data : a));
    } catch {
      toast.error('Error al actualizar');
    }
  };

  const handleDelete = async (id) => {
    try {
      await api.deleteAutomation(id);
      setAutos(prev => prev.filter(a => a.id !== id));
      toast.success('Automatización eliminada');
    } catch {
      toast.error('Error al eliminar');
    }
  };

  const handleRunNow = async (auto) => {
    setRunningId(auto.id);
    try {
      const res = await api.runAutomation(auto.id);
      setAutos(prev => prev.map(a => a.id === auto.id ? res.data : a));
      setExpandedId(auto.id);
      if (res.data.run_ok && res.data.fired === false) {
        toast.info('Revisado — sin cambios detectados');
      } else if (res.data.run_ok) {
        toast.success(res.data.last_error ? 'Ejecutada — el correo falló (revisa SMTP)' : 'Ejecutada y correo enviado');
      } else {
        toast.error('La ejecución falló — revisa el detalle');
      }
    } catch {
      toast.error('Error al ejecutar');
    } finally {
      setRunningId(null);
    }
  };

  const btnPrimary = {
    px: 2.5, py: 0.9, borderRadius: '8px', border: 'none', cursor: 'pointer',
    bgcolor: '#586AD0', color: '#fff', fontSize: '0.85rem', fontWeight: 600,
    display: 'inline-flex', alignItems: 'center', gap: 0.75,
    '&:hover': { bgcolor: '#2F42A6' }, '&:disabled': { bgcolor: 'rgba(88,106,208,0.4)', cursor: 'default' },
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
      <PageHeader title="Disparadores" backLabel="Inicio" back="/app" />

      <Box sx={{ p: { xs: 2, sm: 3 }, maxWidth: 820 }}>
        <Typography sx={{ fontSize: '0.8rem', color: textMuted, mb: 3 }}>
          Automatiza qué quieres obtener de Afable: un prompt programado ("cada mañana envíame el
          resumen de ventas") o un aviso cuando pase algo en tus sistemas ("notifícame si aparece
          una nueva base de datos"). Afable lo hace solo y te llega por correo.
        </Typography>

        {!showForm && (
          <Box component="button" onClick={() => setShowForm(true)} sx={{ ...btnPrimary, mb: 3 }}>
            <Plus size={15} /> Nueva automatización
          </Box>
        )}

        {/* ── Constructor de automatizaciones ── */}
        <Collapse in={showForm}>
          <Box sx={{ p: 2.5, mb: 3, borderRadius: '10px', bgcolor: bgCard, border: `1px solid ${borderColor}`, display: 'flex', flexDirection: 'column', gap: 2.5 }}>

            {/* ── Vista previa del flujo (se arma solo, en vivo) ── */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap', p: 1.5, borderRadius: '8px', bgcolor: d ? 'rgba(88,106,208,0.06)' : 'rgba(88,106,208,0.05)', border: `1px dashed ${d ? 'rgba(88,106,208,0.35)' : 'rgba(88,106,208,0.3)'}` }}>
              <FlowNode icon={<MessageSquare size={13} />} label={form.prompt.trim() ? 'Prompt listo' : 'Prompt'} active={!!form.prompt.trim()} d={d} />
              <ArrowRight size={13} color={textMuted} />
              <FlowNode icon={isEvent ? <Zap size={13} /> : <Clock size={13} />} label={isEvent ? 'Evento' : 'Programado'} active d={d} />
              {isEvent && (
                <>
                  <ArrowRight size={13} color={textMuted} />
                  <FlowNode icon={<Database size={13} />} label={form.connection ? (connections.find(c => c.id === form.connection)?.name || 'Conexión') : 'Elegir conexión'} active={!!form.connection} d={d} />
                </>
              )}
              <ArrowRight size={13} color={textMuted} />
              <FlowNode icon={<Mail size={13} />} label={form.notify_email ? 'Avisa por correo' : 'Correo'} active={!!form.notify_email.trim()} d={d} />
            </Box>

            {/* ── 1. Qué querés que Afable haga ── */}
            <Box>
              <FieldLabel textMuted={textMuted}>1. ¿Qué querés que Afable haga?</FieldLabel>
              <TextField
                value={form.prompt} fullWidth multiline rows={3} sx={inputSx}
                placeholder={isEvent
                  ? 'Opcional. Ej: Cuando dispare, analiza qué cambió y dame un resumen. Si lo dejas vacío, solo te llega el aviso.'
                  : 'Ej: Revisa la última venta registrada en Odoo y dime el cliente, el monto y la fecha.'}
                onChange={e => setForm(prev => ({ ...prev, prompt: e.target.value }))}
              />
            </Box>

            {/* ── 2. Disparador ── */}
            <Box>
              <FieldLabel textMuted={textMuted}>2. Elegí el disparador</FieldLabel>
              <Box sx={{ display: 'flex', gap: 1 }}>
                {[
                  { value: 'interval', label: 'Programado (cada X)', icon: <Clock size={14} /> },
                  { value: 'event', label: 'Cuando pase algo (evento)', icon: <Zap size={14} /> },
                ].map(opt => (
                  <Box
                    key={opt.value} component="button" onClick={() => setForm(prev => ({ ...prev, trigger_type: opt.value }))}
                    sx={{
                      display: 'inline-flex', alignItems: 'center', gap: 0.75, px: 1.75, py: 0.8,
                      borderRadius: '8px', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 600,
                      border: `1px solid ${form.trigger_type === opt.value ? '#586AD0' : borderColor}`,
                      bgcolor: form.trigger_type === opt.value ? 'rgba(88,106,208,0.12)' : 'transparent',
                      color: form.trigger_type === opt.value ? (d ? '#9BA6E3' : '#586AD0') : textSemi,
                    }}
                  >
                    {opt.icon} {opt.label}
                  </Box>
                ))}
              </Box>
            </Box>

            {/* ── 3. Desencadenante — qué condición exacta lo dispara ── */}
            {isEvent && (
              <Box>
                <FieldLabel textMuted={textMuted}>3. Elegí el desencadenante</FieldLabel>
                <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                  <TextField
                    select label="Conexión a vigilar" value={form.connection} sx={{ ...inputSx, flex: 1, minWidth: 220 }}
                    onChange={e => setForm(prev => ({ ...prev, connection: e.target.value }))}
                  >
                    {connections.length === 0 && <MenuItem value="" disabled>No tienes conexiones</MenuItem>}
                    {connections.map(c => (
                      <MenuItem key={c.id} value={c.id}>{c.name}</MenuItem>
                    ))}
                  </TextField>
                  <TextField
                    select label="Tipo de evento" value={form.event_type} sx={{ ...inputSx, flex: 1, minWidth: 220 }}
                    onChange={e => setForm(prev => ({ ...prev, event_type: e.target.value }))}
                  >
                    {Object.entries(EVENT_LABELS).map(([value, label]) => (
                      <MenuItem key={value} value={value}>{label}</MenuItem>
                    ))}
                  </TextField>
                  {form.event_type === 'new_rows' && (
                    <TextField
                      label="Tabla (o modelo Odoo) a vigilar" value={form.event_table} sx={{ ...inputSx, flex: 1, minWidth: 220 }}
                      placeholder="Ej: sale.order"
                      onChange={e => setForm(prev => ({ ...prev, event_table: e.target.value }))}
                    />
                  )}
                </Box>
              </Box>
            )}

            {/* ── 4. Cuándo revisar + a quién avisar ── */}
            <Box>
              <FieldLabel textMuted={textMuted}>4. Frecuencia y aviso</FieldLabel>
              <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                <TextField
                  label={isEvent ? 'Revisar cada cuántos minutos' : 'Cada cuántos minutos'}
                  type="number" value={form.interval_minutes} sx={{ ...inputSx, width: 220 }}
                  inputProps={{ min: 5 }}
                  onChange={e => setForm(prev => ({ ...prev, interval_minutes: Math.max(1, parseInt(e.target.value) || 0) }))}
                />
                <TextField
                  label="Correo de notificación" value={form.notify_email} sx={{ ...inputSx, flex: 1, minWidth: 240 }}
                  onChange={e => setForm(prev => ({ ...prev, notify_email: e.target.value }))}
                />
              </Box>
            </Box>

            <TextField
              label="Nombre de la automatización" value={form.name} fullWidth sx={inputSx}
              placeholder={isEvent ? 'Ej: Avisarme si aparece una tabla nueva' : 'Ej: Última venta cada 10 minutos'}
              onChange={e => setForm(prev => ({ ...prev, name: e.target.value.slice(0, 120) }))}
            />

            <Box sx={{ display: 'flex', gap: 1.5 }}>
              <Box component="button" onClick={handleCreate} disabled={saving} sx={btnPrimary}>
                {saving ? <CircularProgress size={14} sx={{ color: '#fff' }} /> : <Plus size={15} />}
                {saving ? 'Creando...' : 'Crear automatización'}
              </Box>
              <Box
                component="button" onClick={() => setShowForm(false)}
                sx={{ px: 2, py: 0.9, borderRadius: '8px', cursor: 'pointer', border: `1px solid ${borderColor}`, bgcolor: 'transparent', color: textSemi, fontSize: '0.85rem', fontWeight: 600 }}
              >
                Cancelar
              </Box>
            </Box>
          </Box>
        </Collapse>

        {/* ── Listado ── */}
        {loading ? (
          <CircularProgress size={20} sx={{ color: '#9BA6E3' }} />
        ) : autos.length === 0 ? (
          <Box sx={{ textAlign: 'center', py: 6, color: textMuted }}>
            <Timer size={32} style={{ opacity: 0.4, marginBottom: 8 }} />
            <Typography sx={{ fontSize: '0.875rem' }}>Todavía no tienes automatizaciones.</Typography>
          </Box>
        ) : (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
            {autos.map(auto => (
              <Box key={auto.id} sx={{ borderRadius: '10px', bgcolor: bgCard, border: `1px solid ${borderColor}`, overflow: 'hidden' }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, p: 2 }}>
                  <Box
                    onClick={() => setExpandedId(expandedId === auto.id ? null : auto.id)}
                    sx={{ display: 'flex', color: textMuted, cursor: 'pointer' }}
                  >
                    {expandedId === auto.id ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                  </Box>
                  <Box sx={{ flex: 1, minWidth: 0 }}>
                    <Typography sx={{ fontSize: '0.9rem', fontWeight: 600, color: theme.palette.text.primary }}>
                      {auto.name}
                    </Typography>
                    <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mt: 0.25 }}>
                      {auto.trigger_type === 'event' && (
                        <Typography sx={{ fontSize: '0.72rem', color: d ? '#9BA6E3' : '#586AD0', display: 'inline-flex', alignItems: 'center', gap: 0.5 }}>
                          <Zap size={11} /> {EVENT_LABELS[auto.event_type] || auto.event_type}
                          {auto.event_config?.table ? ` («${auto.event_config.table}»)` : ''}
                          {auto.connection_name ? ` en ${auto.connection_name}` : ''}
                        </Typography>
                      )}
                      <Typography sx={{ fontSize: '0.72rem', color: textMuted, display: 'inline-flex', alignItems: 'center', gap: 0.5 }}>
                        <Clock size={11} /> {auto.trigger_type === 'event' ? 'revisa cada' : 'cada'} {auto.interval_minutes} min
                      </Typography>
                      <Typography sx={{ fontSize: '0.72rem', color: textMuted, display: 'inline-flex', alignItems: 'center', gap: 0.5 }}>
                        <Mail size={11} /> {auto.notify_email}
                      </Typography>
                      <Typography sx={{ fontSize: '0.72rem', color: textMuted }}>
                        última: {fmtDate(auto.last_run_at)} · {auto.run_count} ejecuciones
                      </Typography>
                    </Box>
                    {auto.last_error && (
                      <Typography sx={{ fontSize: '0.72rem', color: '#e57373', mt: 0.25 }}>{auto.last_error}</Typography>
                    )}
                  </Box>
                  <Box
                    component="button" onClick={() => handleRunNow(auto)} disabled={runningId === auto.id}
                    title="Ejecutar ahora"
                    sx={{ display: 'flex', alignItems: 'center', gap: 0.5, px: 1.5, py: 0.6, borderRadius: '6px', cursor: 'pointer', border: `1px solid ${borderColor}`, bgcolor: 'transparent', color: textSemi, fontSize: '0.75rem', fontWeight: 600, '&:hover': { borderColor: '#586AD0', color: '#9BA6E3' } }}
                  >
                    {runningId === auto.id ? <CircularProgress size={12} sx={{ color: '#9BA6E3' }} /> : <Play size={12} />}
                    {runningId === auto.id ? 'Ejecutando...' : 'Ejecutar ahora'}
                  </Box>
                  <Switch
                    size="small" checked={auto.is_active} onChange={() => handleToggle(auto)}
                    sx={{ '& .MuiSwitch-switchBase.Mui-checked': { color: '#586AD0' }, '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': { bgcolor: '#586AD0' } }}
                  />
                  <Box
                    onClick={() => handleDelete(auto.id)}
                    sx={{ color: textMuted, cursor: 'pointer', display: 'flex', p: 0.5, '&:hover': { color: '#e57373' } }}
                  >
                    <Trash2 size={14} />
                  </Box>
                </Box>

                <Collapse in={expandedId === auto.id}>
                  <Box sx={{ px: 2.5, pb: 2, borderTop: `1px solid ${borderColor}` }}>
                    <Typography sx={{ fontSize: '0.72rem', color: textMuted, mt: 1.5, mb: 0.5, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                      Prompt
                    </Typography>
                    <Typography sx={{ fontSize: '0.8rem', color: auto.prompt ? textSemi : textMuted }}>
                      {auto.prompt || 'Sin prompt — solo llega el aviso del evento.'}
                    </Typography>
                    <Typography sx={{ fontSize: '0.72rem', color: textMuted, mt: 1.5, mb: 0.5, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                      {auto.trigger_type === 'event' ? 'Último evento detectado' : 'Último resultado'}
                    </Typography>
                    {auto.last_result ? (
                      <Box sx={{ fontSize: '0.8rem', color: textSemi, '& p': { m: 0, mb: 1 }, '& table': { borderCollapse: 'collapse' }, '& td, & th': { border: `1px solid ${borderColor}`, px: 1, py: 0.25, fontSize: '0.75rem' } }}>
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{auto.last_result}</ReactMarkdown>
                      </Box>
                    ) : (
                      <Typography sx={{ fontSize: '0.8rem', color: textMuted }}>
                        {auto.trigger_type === 'event' ? 'Aún no detecta ningún cambio.' : 'Aún no se ejecuta.'}
                      </Typography>
                    )}
                  </Box>
                </Collapse>
              </Box>
            ))}
          </Box>
        )}
      </Box>
    </Box>
  );
}
