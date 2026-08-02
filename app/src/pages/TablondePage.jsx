import { useState, useRef, useEffect } from 'react';
import GridLayout from 'react-grid-layout';
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';
import {
  BarChart, Bar, AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer,
} from 'recharts';
import {
  Box, Typography, IconButton, Menu, MenuItem, useTheme,
  Dialog, DialogTitle, DialogContent, DialogActions, Button, TextField,
} from '@mui/material';
import {
  X, TrendingUp, BarChart2, DollarSign, FileText, Plus, GripHorizontal,
  Settings, Minus, Activity,
} from 'lucide-react';
import { toast } from 'react-toastify';
import PageHeader from '../components/PageHeader';
import { api } from '../services/api';

const GRID_STYLES = `
  .afable-grid .react-grid-item.react-grid-placeholder {
    background: rgba(88, 106, 208, 0.12) !important;
    border: 1px dashed rgba(88, 106, 208, 0.35) !important;
    border-radius: 8px !important;
    box-shadow: none !important;
  }
  .afable-grid .react-resizable-handle { opacity: 0.25; transition: opacity 0.15s; }
  .afable-grid .react-grid-item:hover .react-resizable-handle { opacity: 0.6; }
  .afable-grid .react-grid-item.react-draggable-dragging {
    box-shadow: 0 16px 48px rgba(0,0,0,0.3) !important;
    z-index: 100;
  }
`;

const DEFAULT_LAYOUT = [
  { i: 'live',  x: 0, y: 0, w: 8, h: 5, minW: 3, minH: 3 },
  { i: 'notas', x: 8, y: 0, w: 4, h: 5, minW: 3, minH: 2 },
];

const DEFAULT_CARDS = {
  live:  { type: 'live', title: 'Datos en vivo', color: '#34D399' },
  notas: { type: 'nota', title: 'Notas',         color: '#9BA6E3', text: '' },
};

const PRESET_COLORS = ['#586AD0', '#34D399', '#60A5FA', '#F59E0B', '#F87171', '#9BA6E3', '#38BDF8', '#FB923C'];

function cardIconFor(type) {
  if (type === 'ventas' || type === 'kpi') return TrendingUp;
  if (type === 'kpis'   || type === 'bar') return BarChart2;
  if (type === 'gastos')                   return DollarSign;
  if (type === 'line')                     return Activity;
  return FileText;
}

// ─── Recharts custom tooltip ────────────────────────────────────────────────

function ChartTooltip({ active, payload, label, unit = '' }) {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  if (!active || !payload?.length) return null;
  return (
    <Box sx={{
      bgcolor: d ? '#252525' : '#fff',
      border: `1px solid ${theme.palette.divider}`,
      borderRadius: '6px', px: 1.25, py: 0.75,
      boxShadow: '0 4px 16px rgba(0,0,0,0.12)',
    }}>
      <Typography sx={{ fontSize: '0.72rem', color: 'text.secondary', mb: 0.2 }}>{label}</Typography>
      <Typography sx={{ fontSize: '0.875rem', fontWeight: 600, color: 'text.primary' }}>
        {unit}{typeof payload[0].value === 'number' ? payload[0].value.toLocaleString() : payload[0].value}
      </Typography>
    </Box>
  );
}

// ─── Card content ──────────────────────────────────────────────────────────────

// KPIs REALES de los sistemas conectados (vía /organizations/dashboard/)
function LiveKpisContent() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    api.getDashboard()
      .then(r => setData(r.data))
      .catch(() => setData({ connections: [] }))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Box sx={{ px: 2, pb: 2, fontSize: '0.8rem', color: 'text.disabled' }}>Cargando datos en vivo…</Box>;
  const conns = data?.connections || [];
  if (!conns.length) {
    return (
      <Box sx={{ px: 2, pb: 2, fontSize: '0.8rem', color: 'text.secondary' }}>
        Conecta un sistema en Conexiones para ver KPIs en vivo.
      </Box>
    );
  }
  return (
    <Box sx={{ px: 2, pb: 2, display: 'flex', flexDirection: 'column', gap: 1.5 }}>
      {conns.map((c) => (
        <Box key={c.connection_id}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mb: 0.75 }}>
            <Box sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: c.status === 'ok' ? '#34D399' : '#F87171' }} />
            <Typography sx={{ fontSize: '0.74rem', fontWeight: 600, color: 'text.secondary' }}>{c.name}</Typography>
          </Box>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
            {(c.kpis || []).map((k, i) => (
              <Box key={i} sx={{ minWidth: 96, flex: '1 1 auto' }}>
                <Typography sx={{ fontSize: '1.1rem', fontWeight: 700, color: 'text.primary', letterSpacing: '-0.02em', lineHeight: 1.2 }}>
                  {k.value}
                </Typography>
                <Typography sx={{ fontSize: '0.7rem', color: 'text.secondary' }}>{k.label}</Typography>
              </Box>
            ))}
            {!(c.kpis || []).length && (
              <Typography sx={{ fontSize: '0.74rem', color: 'text.disabled' }}>Sincroniza este sistema para ver datos.</Typography>
            )}
          </Box>
        </Box>
      ))}
    </Box>
  );
}

function NotaContent({ text, onChange }) {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  return (
    <Box sx={{ px: 2, pb: 2, flex: 1, display: 'flex' }}>
      <Box
        component="textarea"
        value={text}
        onChange={e => onChange(e.target.value)}
        placeholder="Escribe una nota..."
        sx={{
          flex: 1, width: '100%', minHeight: 60,
          bgcolor: 'transparent', border: 'none', outline: 'none', resize: 'none',
          color: 'text.primary', fontSize: '0.875rem', lineHeight: 1.6,
          fontFamily: 'Inter, sans-serif',
          '&::placeholder': { color: d ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.3)' },
        }}
      />
    </Box>
  );
}

// ─── Card content: KPI configurable ─────────────────────────────────────────

function KpiCardContent({ meta }) {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const { value = '—', unit = '', target, trend, period, color = '#586AD0' } = meta;
  const trendNum  = parseFloat(trend) || 0;
  const targetNum = parseFloat(target) || 0;
  const valueNum  = parseFloat(value)  || 0;
  const hasTarget = target !== undefined && target !== '' && targetNum > 0;
  const pct       = hasTarget ? Math.min(100, Math.round((valueNum / targetNum) * 100)) : null;
  const trendUp   = trendNum >= 0;

  return (
    <Box sx={{ px: 2, pb: 2 }}>
      <Typography sx={{ fontSize: '2rem', fontWeight: 700, letterSpacing: '-0.04em', color: 'text.primary', lineHeight: 1.1 }}>
        {unit}{value}
      </Typography>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mt: 0.5, flexWrap: 'wrap' }}>
        {trendNum !== 0 && (
          <Box sx={{
            px: 0.75, py: 0.125, borderRadius: '4px',
            bgcolor: trendUp ? 'rgba(52,211,153,0.12)' : 'rgba(248,113,113,0.12)',
            border:  `1px solid ${trendUp ? 'rgba(52,211,153,0.25)' : 'rgba(248,113,113,0.25)'}`,
          }}>
            <Typography sx={{ fontSize: '0.75rem', fontWeight: 600, color: trendUp ? '#34D399' : '#F87171' }}>
              {trendUp ? '+' : ''}{trendNum}%
            </Typography>
          </Box>
        )}
        {period && <Typography sx={{ fontSize: '0.75rem', color: 'text.secondary' }}>{period}</Typography>}
      </Box>
      {pct !== null && (
        <Box sx={{ mt: 1.75 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
            <Typography sx={{ fontSize: '0.7rem', color: 'text.secondary' }}>Meta {unit}{target}</Typography>
            <Typography sx={{ fontSize: '0.7rem', color: 'text.secondary' }}>{pct}%</Typography>
          </Box>
          <Box sx={{ height: 3, bgcolor: d ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.08)', borderRadius: 2 }}>
            <Box sx={{ height: '100%', width: `${pct}%`, bgcolor: color, borderRadius: 2, transition: 'width 0.4s ease' }} />
          </Box>
        </Box>
      )}
    </Box>
  );
}

// ─── Card content: Gráfico de barras ─────────────────────────────────────────

function BarChartContent({ meta }) {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const gridColor = d ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)';
  const tickColor = d ? 'rgba(255,255,255,0.35)' : 'rgba(0,0,0,0.35)';
  const data  = meta.data  || [];
  const color = meta.color || '#586AD0';
  const unit  = meta.unit  || '';

  return (
    <Box sx={{ px: 1, pb: 1.5, flex: 1, minHeight: 0 }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={gridColor} vertical={false} />
          <XAxis dataKey="name" tick={{ fontSize: 11, fill: tickColor }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fontSize: 11, fill: tickColor }} axisLine={false} tickLine={false} />
          <RechartsTooltip content={<ChartTooltip unit={unit} />} cursor={{ fill: d ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)' }} />
          <Bar dataKey="valor" fill={color} radius={[3, 3, 0, 0]} maxBarSize={48} />
        </BarChart>
      </ResponsiveContainer>
    </Box>
  );
}

// ─── Card content: Gráfico de línea (área) ───────────────────────────────────

function LineChartContent({ meta, id }) {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const gridColor = d ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)';
  const tickColor = d ? 'rgba(255,255,255,0.35)' : 'rgba(0,0,0,0.35)';
  const data  = meta.data  || [];
  const color = meta.color || '#586AD0';
  const unit  = meta.unit  || '';
  const gradId = `lg-${id}`;

  return (
    <Box sx={{ px: 1, pb: 1.5, flex: 1, minHeight: 0 }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
          <defs>
            <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%"   stopColor={color} stopOpacity={0.28} />
              <stop offset="100%" stopColor={color} stopOpacity={0}    />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke={gridColor} vertical={false} />
          <XAxis dataKey="name" tick={{ fontSize: 11, fill: tickColor }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fontSize: 11, fill: tickColor }} axisLine={false} tickLine={false} />
          <RechartsTooltip content={<ChartTooltip unit={unit} />} cursor={{ stroke: d ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.08)', strokeWidth: 1 }} />
          <Area type="monotone" dataKey="valor" stroke={color} strokeWidth={2} fill={`url(#${gradId})`} dot={false} activeDot={{ r: 3, fill: color }} />
        </AreaChart>
      </ResponsiveContainer>
    </Box>
  );
}

// ─── Diálogo de configuración ─────────────────────────────────────────────────

const CONFIGURABLE = ['kpi', 'bar', 'line'];

function ConfigDialog({ open, onClose, card, cardId, onSave }) {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const [form, setForm] = useState({});
  const [rows, setRows] = useState([{ name: '', valor: '' }]);

  useEffect(() => {
    if (!card) return;
    setForm({
      title:  card.title  || '',
      value:  card.value  || '',
      unit:   card.unit   || '',
      target: card.target || '',
      trend:  card.trend  !== undefined ? String(card.trend) : '',
      period: card.period || '',
      color:  card.color  || '#586AD0',
    });
    setRows(card.data?.length ? card.data.map(r => ({ ...r, valor: String(r.valor) })) : [{ name: '', valor: '' }]);
  }, [card, open]);

  if (!card) return null;
  const isChart = card.type === 'bar' || card.type === 'line';
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const addRow    = ()          => setRows(r => [...r, { name: '', valor: '' }]);
  const removeRow = (i)         => setRows(r => r.filter((_, idx) => idx !== i));
  const setRow    = (i, k, v)   => setRows(r => r.map((row, idx) => idx === i ? { ...row, [k]: v } : row));

  const handleSave = () => {
    const updated = { ...card, ...form };
    if (isChart) {
      updated.data = rows
        .filter(r => r.name.trim())
        .map(r => ({ name: r.name, valor: parseFloat(r.valor) || 0 }));
    }
    onSave(cardId, updated);
    onClose();
  };

  const inputSx = {
    '& .MuiOutlinedInput-root': {
      fontSize: '0.875rem',
      '& fieldset':             { borderColor: theme.palette.divider },
      '&:hover fieldset':       { borderColor: theme.palette.divider },
      '&.Mui-focused fieldset': { borderColor: '#586AD0' },
    },
    '& .MuiInputLabel-root.Mui-focused': { color: '#586AD0' },
    '& .MuiInputBase-input': { color: 'text.primary' },
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      PaperProps={{
        sx: {
          bgcolor: 'background.paper', backgroundImage: 'none',
          borderRadius: '10px', border: `1px solid ${theme.palette.divider}`,
          minWidth: 380, maxWidth: 460,
          boxShadow: d ? '0 16px 48px rgba(0,0,0,0.5)' : '0 8px 32px rgba(0,0,0,0.15)',
        },
      }}
    >
      <DialogTitle sx={{ fontSize: '0.9375rem', fontWeight: 600, pb: 0.5, color: 'text.primary' }}>
        Configurar tarjeta
      </DialogTitle>

      <DialogContent sx={{ pt: 1.5, display: 'flex', flexDirection: 'column', gap: 1.5 }}>
        {/* Título */}
        <TextField
          label="Título" value={form.title} onChange={e => set('title', e.target.value)}
          size="small" fullWidth sx={inputSx}
        />

        {/* Campos KPI */}
        {card.type === 'kpi' && (
          <>
            <Box sx={{ display: 'flex', gap: 1 }}>
              <TextField label="Prefijo" placeholder="$, %, €…" value={form.unit} onChange={e => set('unit', e.target.value)} size="small" sx={{ ...inputSx, width: 90 }} />
              <TextField label="Valor"   value={form.value}  onChange={e => set('value',  e.target.value)} size="small" sx={{ ...inputSx, flex: 1 }} />
            </Box>
            <Box sx={{ display: 'flex', gap: 1 }}>
              <TextField label="Meta"         value={form.target} onChange={e => set('target', e.target.value)} size="small" sx={{ ...inputSx, flex: 1 }} />
              <TextField label="Tendencia (%)" value={form.trend}  onChange={e => set('trend',  e.target.value)} size="small" sx={{ ...inputSx, flex: 1 }} type="number" />
            </Box>
            <TextField label="Período" placeholder="ej. Q1 2026" value={form.period} onChange={e => set('period', e.target.value)} size="small" fullWidth sx={inputSx} />
          </>
        )}

        {/* Unidad para gráficos */}
        {isChart && (
          <TextField label="Unidad (tooltip)" placeholder="$, %, unidades…" value={form.unit} onChange={e => set('unit', e.target.value)} size="small" fullWidth sx={inputSx} />
        )}

        {/* Tabla de datos para gráficos */}
        {isChart && (
          <Box>
            <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary', mb: 0.875 }}>Datos</Typography>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.625 }}>
              {rows.map((row, i) => (
                <Box key={i} sx={{ display: 'flex', gap: 0.75, alignItems: 'center' }}>
                  <TextField
                    placeholder="Etiqueta" value={row.name}
                    onChange={e => setRow(i, 'name', e.target.value)}
                    size="small" sx={{ ...inputSx, flex: 1.5 }}
                  />
                  <TextField
                    placeholder="Valor" value={row.valor}
                    onChange={e => setRow(i, 'valor', e.target.value)}
                    size="small" sx={{ ...inputSx, flex: 1 }} type="number"
                  />
                  <IconButton
                    size="small" onClick={() => removeRow(i)} disabled={rows.length <= 1}
                    sx={{ p: 0.5, color: 'text.disabled', '&:hover:not(:disabled)': { color: '#F87171' } }}
                  >
                    <Minus size={14} />
                  </IconButton>
                </Box>
              ))}
              <Box
                onClick={addRow}
                sx={{ display: 'flex', alignItems: 'center', gap: 0.5, py: 0.5, px: 0.25, cursor: 'pointer', color: 'text.disabled', borderRadius: '4px', '&:hover': { color: '#586AD0' }, transition: 'color 0.12s', width: 'fit-content' }}
              >
                <Plus size={13} />
                <Typography sx={{ fontSize: '0.78rem' }}>Agregar fila</Typography>
              </Box>
            </Box>
          </Box>
        )}

        {/* Selector de color */}
        <Box>
          <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary', mb: 0.875 }}>Color</Typography>
          <Box sx={{ display: 'flex', gap: 0.75, flexWrap: 'wrap' }}>
            {PRESET_COLORS.map(c => (
              <Box
                key={c}
                onClick={() => set('color', c)}
                sx={{
                  width: 22, height: 22, borderRadius: '50%', bgcolor: c, cursor: 'pointer',
                  outline: form.color === c ? `2px solid ${d ? '#fff' : '#111'}` : '2px solid transparent',
                  outlineOffset: '2px',
                  transition: 'transform 0.1s', '&:hover': { transform: 'scale(1.18)' },
                }}
              />
            ))}
          </Box>
        </Box>
      </DialogContent>

      <DialogActions sx={{ px: 2.5, pb: 2, gap: 1 }}>
        <Button onClick={onClose} size="small" sx={{ color: 'text.secondary', fontSize: '0.8125rem', textTransform: 'none' }}>
          Cancelar
        </Button>
        <Button
          onClick={handleSave} variant="contained" size="small"
          sx={{ bgcolor: '#586AD0', '&:hover': { bgcolor: '#2F42A6' }, fontSize: '0.8125rem', textTransform: 'none', boxShadow: 'none', borderRadius: '6px', px: 2 }}
        >
          Guardar
        </Button>
      </DialogActions>
    </Dialog>
  );
}

// ─── Card ─────────────────────────────────────────────────────────────────────

function Card({ id, meta, onRemove, onNoteChange, onConfig }) {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const Icon = cardIconFor(meta.type);

  return (
    <Box sx={{
      height: '100%', display: 'flex', flexDirection: 'column',
      bgcolor: 'background.paper',
      border: `1px solid ${theme.palette.divider}`,
      borderRadius: '8px', overflow: 'hidden',
    }}>
      {/* Header / drag handle */}
      <Box
        className="card-header"
        sx={{
          display: 'flex', alignItems: 'center', gap: 1,
          px: 2, py: 1.25,
          borderBottom: `1px solid ${theme.palette.divider}`,
          cursor: 'grab', flexShrink: 0,
          '&:active': { cursor: 'grabbing' },
        }}
      >
        <Icon size={14} color={meta.color} />
        <Typography sx={{ flex: 1, fontSize: '0.8125rem', fontWeight: 500, color: 'text.primary' }}>
          {meta.title}
        </Typography>
        <GripHorizontal size={12} color={d ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.2)'} />

        {CONFIGURABLE.includes(meta.type) && (
          <IconButton
            size="small" onClick={() => onConfig(id)} className="nodrag"
            sx={{ p: 0.25, color: 'text.disabled', '&:hover': { color: '#586AD0' }, ml: 0.25 }}
          >
            <Settings size={12} />
          </IconButton>
        )}
        <IconButton
          size="small" onClick={() => onRemove(id)} className="nodrag"
          sx={{ p: 0.25, color: 'text.disabled', '&:hover': { color: '#f87171' }, ml: 0.25 }}
        >
          <X size={13} />
        </IconButton>
      </Box>

      {/* Contenido */}
      <Box sx={{ flex: 1, overflowY: 'auto', pt: 1.5, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        {(meta.type === 'live' || meta.type === 'ventas' || meta.type === 'kpis' || meta.type === 'gastos') && <LiveKpisContent />}
        {meta.type === 'nota'   && <NotaContent text={meta.text || ''} onChange={t => onNoteChange(id, t)} />}
        {meta.type === 'kpi'    && <KpiCardContent meta={meta} />}
        {meta.type === 'bar'    && <BarChartContent meta={meta} />}
        {meta.type === 'line'   && <LineChartContent meta={meta} id={id} />}
      </Box>
    </Box>
  );
}

// ─── TablondePage ─────────────────────────────────────────────────────────────

function loadCards() {
  try {
    const saved = JSON.parse(localStorage.getItem('afable-tablero-cards'));
    return saved || DEFAULT_CARDS;
  } catch { return DEFAULT_CARDS; }
}

function saveCards(cards) {
  localStorage.setItem('afable-tablero-cards', JSON.stringify(cards));
}

export default function TablondePage() {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const containerRef = useRef(null);
  const [containerWidth, setContainerWidth] = useState(1200);
  const [layout, setLayout] = useState(() => {
    try { return JSON.parse(localStorage.getItem('afable-tablero-layout')) || DEFAULT_LAYOUT; }
    catch { return DEFAULT_LAYOUT; }
  });
  const [cards, setCards] = useState(loadCards);
  const [menuAnchor,  setMenuAnchor]  = useState(null);
  const [configCardId, setConfigCardId] = useState(null);

  useEffect(() => {
    const obs = new ResizeObserver(entries => {
      const w = entries[0]?.contentRect.width;
      if (w) setContainerWidth(w - 48);
    });
    if (containerRef.current) obs.observe(containerRef.current);
    return () => obs.disconnect();
  }, []);

  const handleLayoutChange = (newLayout) => {
    setLayout(newLayout);
    localStorage.setItem('afable-tablero-layout', JSON.stringify(newLayout));
  };

  const updateCards = (updater) => {
    setCards(prev => {
      const next = typeof updater === 'function' ? updater(prev) : updater;
      saveCards(next);
      return next;
    });
  };

  const removeCard = (id) => {
    setLayout(prev => prev.filter(l => l.i !== id));
    updateCards(prev => { const n = { ...prev }; delete n[id]; return n; });
  };

  const nextY = () => layout.reduce((m, l) => Math.max(m, l.y + l.h), 0);

  const addNota = () => {
    const id = `nota-${Date.now()}`;
    setLayout(prev => [...prev, { i: id, x: 0, y: nextY(), w: 5, h: 3, minW: 3, minH: 2 }]);
    updateCards(prev => ({ ...prev, [id]: { type: 'nota', title: 'Nueva nota', color: '#9BA6E3', text: '' } }));
    setMenuAnchor(null);
  };

  const addKpi = () => {
    const id = `kpi-${Date.now()}`;
    setLayout(prev => [...prev, { i: id, x: 0, y: nextY(), w: 3, h: 4, minW: 2, minH: 3 }]);
    updateCards(prev => ({ ...prev, [id]: { type: 'kpi', title: 'Nuevo KPI', value: '0', unit: '', target: '', trend: '0', period: '', color: '#586AD0' } }));
    setMenuAnchor(null);
    setConfigCardId(id);
  };

  const addBar = () => {
    const id = `bar-${Date.now()}`;
    setLayout(prev => [...prev, { i: id, x: 0, y: nextY(), w: 5, h: 5, minW: 3, minH: 3 }]);
    updateCards(prev => ({
      ...prev,
      [id]: {
        type: 'bar', title: 'Gráfico de barras', color: '#586AD0', unit: '',
        data: [
          { name: 'Ene', valor: 400 }, { name: 'Feb', valor: 620 },
          { name: 'Mar', valor: 480 }, { name: 'Abr', valor: 800 },
          { name: 'May', valor: 710 }, { name: 'Jun', valor: 950 },
        ],
      },
    }));
    setMenuAnchor(null);
    setConfigCardId(id);
  };

  const addLine = () => {
    const id = `line-${Date.now()}`;
    setLayout(prev => [...prev, { i: id, x: 0, y: nextY(), w: 5, h: 5, minW: 3, minH: 3 }]);
    updateCards(prev => ({
      ...prev,
      [id]: {
        type: 'line', title: 'Tendencia', color: '#60A5FA', unit: '',
        data: [
          { name: 'Ene', valor: 120 }, { name: 'Feb', valor: 180 },
          { name: 'Mar', valor: 150 }, { name: 'Abr', valor: 240 },
          { name: 'May', valor: 210 }, { name: 'Jun', valor: 310 },
        ],
      },
    }));
    setMenuAnchor(null);
    setConfigCardId(id);
  };

  const handleNoteChange = (id, text) => {
    updateCards(prev => ({ ...prev, [id]: { ...prev[id], text } }));
  };

  const handleSaveCard = (id, updated) => {
    updateCards(prev => ({ ...prev, [id]: updated }));
  };

  const activeLayout = layout.filter(l => cards[l.i]);
  const menuBg     = d ? '#252525' : '#ffffff';
  const menuBorder = d ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)';

  const addCardBtn = (
    <Box
      onClick={e => setMenuAnchor(e.currentTarget)}
      sx={{
        display: 'flex', alignItems: 'center', gap: 0.75,
        px: 1.25, py: 0.6, borderRadius: '6px', cursor: 'pointer',
        border: `1px solid ${theme.palette.divider}`,
        color: 'text.secondary',
        '&:hover': { bgcolor: 'action.hover', color: 'text.primary' },
        transition: 'all 0.12s',
      }}
    >
      <Plus size={14} />
      <Typography sx={{ fontSize: '0.8125rem', fontWeight: 500 }}>Agregar tarjeta</Typography>
    </Box>
  );

  const menuItemSx = {
    fontSize: '0.875rem', color: 'text.secondary', gap: 1.5, py: 1,
    '&:hover': { bgcolor: 'action.hover', color: 'text.primary' },
  };

  return (
    <Box ref={containerRef} sx={{ display: 'flex', flexDirection: 'column', minHeight: '100%' }}>
      <style>{GRID_STYLES}</style>

      <PageHeader title="Mi tablero" back="/app" backLabel="Chat" actions={addCardBtn} />

      <Box sx={{ px: 3, pt: 2, pb: 4, flex: 1 }}>

        <Menu
          anchorEl={menuAnchor}
          open={Boolean(menuAnchor)}
          onClose={() => setMenuAnchor(null)}
          PaperProps={{
            sx: {
              bgcolor: menuBg, border: `1px solid ${menuBorder}`,
              borderRadius: '8px',
              boxShadow: d ? '0 8px 32px rgba(0,0,0,0.4)' : '0 4px 20px rgba(0,0,0,0.12)',
              minWidth: 190,
            },
          }}
        >
          <MenuItem onClick={addNota}  sx={menuItemSx}><FileText   size={15} /> Nota libre</MenuItem>
          <MenuItem onClick={addKpi}   sx={menuItemSx}><TrendingUp size={15} /> KPI</MenuItem>
          <MenuItem onClick={addBar}   sx={menuItemSx}><BarChart2  size={15} /> Gráfico de barras</MenuItem>
          <MenuItem onClick={addLine}  sx={menuItemSx}><Activity   size={15} /> Gráfico de línea</MenuItem>
        </Menu>

        <GridLayout
          className="afable-grid"
          layout={activeLayout}
          cols={12}
          rowHeight={60}
          width={containerWidth}
          onLayoutChange={handleLayoutChange}
          draggableHandle=".card-header"
          margin={[12, 12]}
          containerPadding={[0, 0]}
        >
          {activeLayout.map(({ i }) => cards[i] ? (
            <div key={i}>
              <Card
                id={i}
                meta={cards[i]}
                onRemove={removeCard}
                onNoteChange={handleNoteChange}
                onConfig={setConfigCardId}
              />
            </div>
          ) : null)}
        </GridLayout>

        {activeLayout.length === 0 && (
          <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '50vh', gap: 2 }}>
            <Typography sx={{ color: 'text.secondary', fontSize: '0.9375rem' }}>El tablero está vacío</Typography>
            <Box
              onClick={e => setMenuAnchor(e.currentTarget)}
              sx={{
                display: 'flex', alignItems: 'center', gap: 0.75,
                px: 1.5, py: 0.875, borderRadius: '6px',
                border: `1px solid ${theme.palette.divider}`,
                cursor: 'pointer', color: 'text.secondary',
                '&:hover': { bgcolor: 'action.hover', color: 'text.primary' },
              }}
            >
              <Plus size={14} />
              <Typography sx={{ fontSize: '0.875rem' }}>Agregar primera tarjeta</Typography>
            </Box>
          </Box>
        )}
      </Box>

      <ConfigDialog
        open={Boolean(configCardId)}
        onClose={() => setConfigCardId(null)}
        card={configCardId ? cards[configCardId] : null}
        cardId={configCardId}
        onSave={handleSaveCard}
      />
    </Box>
  );
}
