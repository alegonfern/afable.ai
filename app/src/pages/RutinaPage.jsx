import { useState, useEffect } from 'react';
import {
  Box, Typography, TextField, CircularProgress, useTheme, Collapse, Switch,
  Select, MenuItem,
} from '@mui/material';
import { ListChecks, Plus, Play, Trash2, ChevronDown, ChevronRight, Mail, Clock, X, Bot } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { toast } from 'react-toastify';
import { api } from '../services/api';
import PageHeader from '../components/PageHeader';
import { useApp } from '../context/AppContext';

const fmtDate = (iso) => iso ? new Date(iso).toLocaleString('es-CL', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : 'nunca';

const EMPTY_STEP = { prompt: '', agent_id: null };

export default function RutinaPage() {
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

  const [routines, setRoutines] = useState([]);
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [runningId, setRunningId] = useState(null);
  const [expandedId, setExpandedId] = useState(null);

  const [name, setName] = useState('');
  const [steps, setSteps] = useState([{ ...EMPTY_STEP }]);
  const [intervalMin, setIntervalMin] = useState('');   // vacío = solo manual
  const [notifyEmail, setNotifyEmail] = useState('');

  useEffect(() => {
    Promise.all([api.getRoutines(), api.getAgents()])
      .then(([r, a]) => { setRoutines(r.data); setAgents(a.data); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const setStep = (i, patch) =>
    setSteps(prev => prev.map((s, idx) => idx === i ? { ...s, ...patch } : s));

  const addStep = () => {
    if (steps.length >= 10) { toast.error('Máximo 10 pasos.'); return; }
    setSteps(prev => [...prev, { ...EMPTY_STEP }]);
  };

  const removeStep = (i) => setSteps(prev => prev.filter((_, idx) => idx !== i));

  const resetForm = () => {
    setName(''); setSteps([{ ...EMPTY_STEP }]); setIntervalMin(''); setNotifyEmail('');
    setShowForm(false);
  };

  const handleCreate = async () => {
    const cleanSteps = steps.filter(s => s.prompt.trim());
    if (!name.trim() || cleanSteps.length === 0) {
      toast.error('Ponle nombre y al menos un paso con prompt.');
      return;
    }
    if (!selectedOrganization?.id) {
      toast.error('Primero configure su Workspace.');
      return;
    }
    if (selectedOrganization.nombre === 'Personal') {
      toast.error('Las rutinas no funcionan en "Personal" — cambia a una empresa real arriba.');
      return;
    }
    setSaving(true);
    try {
      const res = await api.createRoutine({
        organization: selectedOrganization.id,
        name,
        steps: cleanSteps,
        interval_minutes: intervalMin === '' ? null : parseInt(intervalMin),
        notify_email: notifyEmail.trim(),
      });
      setRoutines(prev => [res.data, ...prev]);
      resetForm();
      toast.success(intervalMin === ''
        ? 'Rutina creada. Ejecútala con "Ejecutar ahora".'
        : `Rutina creada. Se ejecutará cada ${intervalMin} minutos.`);
    } catch (e) {
      const data = e.response?.data || {};
      toast.error(data.interval_minutes?.[0] || data.steps?.[0] || data.organization?.[0] || 'Error al crear la rutina');
    } finally {
      setSaving(false);
    }
  };

  const handleToggle = async (routine) => {
    try {
      const res = await api.updateRoutine(routine.id, { is_active: !routine.is_active });
      setRoutines(prev => prev.map(r => r.id === routine.id ? res.data : r));
    } catch {
      toast.error('Error al actualizar');
    }
  };

  const handleDelete = async (id) => {
    try {
      await api.deleteRoutine(id);
      setRoutines(prev => prev.filter(r => r.id !== id));
      toast.success('Rutina eliminada');
    } catch {
      toast.error('Error al eliminar');
    }
  };

  const handleRunNow = async (routine) => {
    setRunningId(routine.id);
    toast.info(`Ejecutando «${routine.name}» — ${routine.steps.length} pasos, puede tardar...`);
    try {
      const res = await api.runRoutine(routine.id);
      setRoutines(prev => prev.map(r => r.id === routine.id ? res.data : r));
      setExpandedId(routine.id);
      if (res.data.run_ok) {
        toast.success('Rutina ejecutada — revisa los resultados por paso');
      } else {
        toast.error('La rutina falló en un paso — revisa el detalle');
      }
    } catch {
      toast.error('Error al ejecutar la rutina');
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

  const mdSx = {
    fontSize: '0.8rem', color: textSemi,
    '& p': { m: 0, mb: 1 }, '& table': { borderCollapse: 'collapse' },
    '& td, & th': { border: `1px solid ${borderColor}`, px: 1, py: 0.25, fontSize: '0.75rem' },
    '& img': { maxWidth: '100%' },
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
      <PageHeader title="Mi rutina" backLabel="Inicio" back="/app" />

      <Box sx={{ p: { xs: 2, sm: 3 }, maxWidth: 860 }}>
        <Typography sx={{ fontSize: '0.8rem', color: textMuted, mb: 3 }}>
          Encadena pasos que se ejecutan en orden: el resultado de cada paso se le entrega al siguiente.
          Ej: 1) trae las últimas 10 ventas → 2) calcula el promedio → 3) analízalo con el Científico de Datos.
          Ejecútala a mano o prográmala cada X minutos.
        </Typography>

        {!showForm && (
          <Box component="button" onClick={() => setShowForm(true)} sx={{ ...btnPrimary, mb: 3 }}>
            <Plus size={15} /> Nueva rutina
          </Box>
        )}

        {/* ── Constructor ── */}
        <Collapse in={showForm}>
          <Box sx={{ p: 2.5, mb: 3, borderRadius: '10px', bgcolor: bgCard, border: `1px solid ${borderColor}`, display: 'flex', flexDirection: 'column', gap: 2 }}>
            <TextField
              label="Nombre de la rutina" value={name} fullWidth sx={inputSx}
              placeholder="Ej: Análisis de ventas de la mañana"
              onChange={e => setName(e.target.value.slice(0, 120))}
            />

            <Typography sx={{ fontSize: '0.72rem', fontWeight: 700, color: '#586AD0', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              Pasos ({steps.length})
            </Typography>
            {steps.map((step, i) => (
              <Box key={i} sx={{ display: 'flex', gap: 1.5, alignItems: 'flex-start' }}>
                <Box sx={{
                  width: 26, height: 26, borderRadius: '50%', flexShrink: 0, mt: 1.2,
                  bgcolor: 'rgba(88,106,208,0.15)', color: '#586AD0',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: '0.75rem', fontWeight: 700,
                }}>
                  {i + 1}
                </Box>
                <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 1 }}>
                  <TextField
                    value={step.prompt} fullWidth multiline rows={2} sx={inputSx}
                    placeholder={i === 0
                      ? 'Ej: Trae las últimas 10 ventas registradas con cliente, monto y fecha.'
                      : 'Ej: Con el resultado anterior, calcula el promedio de los montos.'}
                    onChange={e => setStep(i, { prompt: e.target.value })}
                  />
                  <Select
                    size="small" displayEmpty
                    value={step.agent_id ?? ''}
                    onChange={e => setStep(i, { agent_id: e.target.value === '' ? null : e.target.value })}
                    sx={{ ...inputSx, maxWidth: 320, '& .MuiOutlinedInput-notchedOutline': { borderColor }, fontSize: '0.8rem' }}
                    renderValue={(v) => {
                      if (v === '') return <Typography sx={{ fontSize: '0.8rem', color: textMuted, display: 'flex', alignItems: 'center', gap: 0.75 }}><Bot size={13} /> Agente por defecto</Typography>;
                      const a = agents.find(x => x.id === v);
                      return <Typography sx={{ fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: 0.75 }}><Bot size={13} /> {a?.name || `Agente #${v}`}</Typography>;
                    }}
                  >
                    <MenuItem value=""><em>Agente por defecto</em></MenuItem>
                    {agents.map(a => <MenuItem key={a.id} value={a.id}>{a.name}</MenuItem>)}
                  </Select>
                </Box>
                {steps.length > 1 && (
                  <Box onClick={() => removeStep(i)} sx={{ color: textMuted, cursor: 'pointer', mt: 1.4, '&:hover': { color: '#e57373' } }}>
                    <X size={15} />
                  </Box>
                )}
              </Box>
            ))}
            <Box
              component="button" onClick={addStep}
              sx={{ alignSelf: 'flex-start', px: 1.5, py: 0.6, borderRadius: '6px', cursor: 'pointer', border: `1px dashed ${borderColor}`, bgcolor: 'transparent', color: textSemi, fontSize: '0.78rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 0.5, '&:hover': { borderColor: '#586AD0', color: '#9BA6E3' } }}
            >
              <Plus size={13} /> Agregar paso
            </Box>

            <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
              <TextField
                label="Cada cuántos minutos (vacío = solo manual)" type="number" value={intervalMin}
                sx={{ ...inputSx, width: 280 }} inputProps={{ min: 5 }}
                onChange={e => setIntervalMin(e.target.value)}
              />
              <TextField
                label="Correo de notificación (opcional)" value={notifyEmail}
                placeholder={currentUser?.email || ''}
                sx={{ ...inputSx, flex: 1, minWidth: 240 }}
                onChange={e => setNotifyEmail(e.target.value)}
              />
            </Box>

            <Box sx={{ display: 'flex', gap: 1.5 }}>
              <Box component="button" onClick={handleCreate} disabled={saving} sx={btnPrimary}>
                {saving ? <CircularProgress size={14} sx={{ color: '#fff' }} /> : <Plus size={15} />}
                {saving ? 'Creando...' : 'Crear rutina'}
              </Box>
              <Box
                component="button" onClick={resetForm}
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
        ) : routines.length === 0 ? (
          <Box sx={{ textAlign: 'center', py: 6, color: textMuted }}>
            <ListChecks size={32} style={{ opacity: 0.4, marginBottom: 8 }} />
            <Typography sx={{ fontSize: '0.875rem' }}>Todavía no tienes rutinas.</Typography>
          </Box>
        ) : (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
            {routines.map(routine => (
              <Box key={routine.id} sx={{ borderRadius: '10px', bgcolor: bgCard, border: `1px solid ${borderColor}`, overflow: 'hidden' }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, p: 2 }}>
                  <Box
                    onClick={() => setExpandedId(expandedId === routine.id ? null : routine.id)}
                    sx={{ display: 'flex', color: textMuted, cursor: 'pointer' }}
                  >
                    {expandedId === routine.id ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                  </Box>
                  <Box sx={{ flex: 1, minWidth: 0 }}>
                    <Typography sx={{ fontSize: '0.9rem', fontWeight: 600, color: theme.palette.text.primary }}>
                      {routine.name}
                    </Typography>
                    <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mt: 0.25 }}>
                      <Typography sx={{ fontSize: '0.72rem', color: textMuted, display: 'inline-flex', alignItems: 'center', gap: 0.5 }}>
                        <ListChecks size={11} /> {routine.steps.length} pasos
                      </Typography>
                      <Typography sx={{ fontSize: '0.72rem', color: textMuted, display: 'inline-flex', alignItems: 'center', gap: 0.5 }}>
                        <Clock size={11} /> {routine.interval_minutes ? `cada ${routine.interval_minutes} min` : 'manual'}
                      </Typography>
                      {routine.notify_email && (
                        <Typography sx={{ fontSize: '0.72rem', color: textMuted, display: 'inline-flex', alignItems: 'center', gap: 0.5 }}>
                          <Mail size={11} /> {routine.notify_email}
                        </Typography>
                      )}
                      <Typography sx={{ fontSize: '0.72rem', color: textMuted }}>
                        última: {fmtDate(routine.last_run_at)} · {routine.run_count} ejecuciones
                      </Typography>
                    </Box>
                    {routine.last_error && (
                      <Typography sx={{ fontSize: '0.72rem', color: '#e57373', mt: 0.25 }}>{routine.last_error}</Typography>
                    )}
                  </Box>
                  <Box
                    component="button" onClick={() => handleRunNow(routine)} disabled={runningId === routine.id}
                    title="Ejecutar ahora"
                    sx={{ display: 'flex', alignItems: 'center', gap: 0.5, px: 1.5, py: 0.6, borderRadius: '6px', cursor: 'pointer', border: `1px solid ${borderColor}`, bgcolor: 'transparent', color: textSemi, fontSize: '0.75rem', fontWeight: 600, '&:hover': { borderColor: '#586AD0', color: '#9BA6E3' } }}
                  >
                    {runningId === routine.id ? <CircularProgress size={12} sx={{ color: '#9BA6E3' }} /> : <Play size={12} />}
                    {runningId === routine.id ? 'Ejecutando...' : 'Ejecutar ahora'}
                  </Box>
                  {routine.interval_minutes && (
                    <Switch
                      size="small" checked={routine.is_active} onChange={() => handleToggle(routine)}
                      sx={{ '& .MuiSwitch-switchBase.Mui-checked': { color: '#586AD0' }, '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': { bgcolor: '#586AD0' } }}
                    />
                  )}
                  <Box
                    onClick={() => handleDelete(routine.id)}
                    sx={{ color: textMuted, cursor: 'pointer', display: 'flex', p: 0.5, '&:hover': { color: '#e57373' } }}
                  >
                    <Trash2 size={14} />
                  </Box>
                </Box>

                <Collapse in={expandedId === routine.id}>
                  <Box sx={{ px: 2.5, pb: 2, borderTop: `1px solid ${borderColor}` }}>
                    {(routine.last_steps_results?.length ? routine.last_steps_results : routine.steps.map((s, i) => ({ step: i + 1, prompt: s.prompt, agent: null, result: '', error: '' }))).map((r, i) => (
                      <Box key={i} sx={{ mt: 1.5 }}>
                        <Typography sx={{ fontSize: '0.72rem', color: textMuted, mb: 0.5, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                          Paso {r.step}{r.agent ? ` · ${r.agent}` : ''} — {r.prompt || '(paso)'}
                        </Typography>
                        {r.error ? (
                          <Typography sx={{ fontSize: '0.8rem', color: '#e57373' }}>{r.error}</Typography>
                        ) : r.result ? (
                          <Box sx={mdSx}>
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>{r.result}</ReactMarkdown>
                          </Box>
                        ) : (
                          <Typography sx={{ fontSize: '0.8rem', color: textMuted }}>Aún no se ejecuta.</Typography>
                        )}
                      </Box>
                    ))}
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
