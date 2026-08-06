import { useState, useEffect, useMemo } from 'react';
import { Box, Typography, Button, Chip, CircularProgress, useTheme } from '@mui/material';
import { Boxes, Table2, Activity, Plus, Zap, ShieldCheck } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import PageHeader from '../components/PageHeader';
import { api } from '../services/api';

// ── Layout automático de las entidades (el backend no entrega posiciones) ───────
const COLS = 3;
const CELL_W = 200, CELL_H = 96, PAD_X = 40, PAD_Y = 40, BOX_W = 150, BOX_H = 54;

function layout(entities) {
  const pos = {};
  entities.forEach((e, i) => {
    const col = i % COLS, row = Math.floor(i / COLS);
    pos[e.id] = { x: PAD_X + col * CELL_W, y: PAD_Y + row * CELL_H, w: BOX_W, h: BOX_H };
  });
  const rows = Math.ceil(entities.length / COLS) || 1;
  return { pos, width: PAD_X * 2 + COLS * CELL_W - (CELL_W - BOX_W), height: PAD_Y * 2 + rows * CELL_H };
}

const fmt = (n) => (n == null ? '—' : Number(n).toLocaleString('es-CL'));

// ── Vista: Mapa de entidades ───────────────────────────────────────────────────
function MapView({ entities, edges, pos, dims, selected, setSelected, theme }) {
  const d = theme.palette.mode === 'dark';
  const cardBg = theme.palette.background.paper;
  const lineColor = d ? 'rgba(255,255,255,0.18)' : 'rgba(0,0,0,0.16)';
  const center = (id) => {
    const p = pos[id];
    return p ? { cx: p.x + p.w / 2, cy: p.y + p.h / 2 } : null;
  };

  return (
    <svg viewBox={`0 0 ${dims.width} ${dims.height}`} style={{ width: '100%', height: 'auto', display: 'block' }}>
      <defs>
        <marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
          <path d="M0 1 L7 4 L0 7" fill="none" stroke={lineColor} strokeWidth="1.4" />
        </marker>
      </defs>

      {edges.map((e, i) => {
        const a = center(e.from), b = center(e.to);
        if (!a || !b) return null;
        return <line key={i} x1={a.cx} y1={a.cy} x2={b.cx} y2={b.cy} stroke={lineColor} strokeWidth="1.4" markerEnd="url(#arrow)" />;
      })}

      {entities.map((e) => {
        const p = pos[e.id];
        if (!p) return null;
        const active = selected === e.id;
        return (
          <g key={e.id} onClick={() => setSelected(e.id)} style={{ cursor: 'pointer' }}>
            <rect x={p.x} y={p.y} width={p.w} height={p.h} rx="12"
              fill={cardBg} stroke={active ? '#586AD0' : theme.palette.divider} strokeWidth={active ? 2 : 1.2} />
            <circle cx={p.x + 16} cy={p.y + p.h / 2} r="4" fill={e.color} />
            <text x={p.x + 30} y={p.y + 24} fontSize="13" fontWeight="600"
              fill={theme.palette.text.primary} fontFamily="'Sora','Inter',sans-serif">{e.table}</text>
            <text x={p.x + 30} y={p.y + 40} fontSize="10" fill={theme.palette.text.secondary}
              fontFamily="'JetBrains Mono', monospace">{fmt(e.count)} reg.</text>
          </g>
        );
      })}
    </svg>
  );
}

// ── Panel de detalle ────────────────────────────────────────────────────────────
function DetailPanel({ entity, edges, entitiesById, theme }) {
  const labelSx = { fontSize: '0.65rem', letterSpacing: '0.08em', textTransform: 'uppercase', color: 'text.disabled', fontWeight: 600, mb: 1 };
  const rels = edges
    .filter((r) => r.from === entity.id || r.to === entity.id)
    .map((r) => {
      const otherId = r.from === entity.id ? r.to : r.from;
      const other = entitiesById[otherId];
      return { to: other?.table || otherId.split(':')[1], via: r.from === entity.id ? r.from_column : r.to_column };
    });

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
      <Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: entity.color }} />
          <Typography sx={{ fontSize: '1.05rem', fontWeight: 700, letterSpacing: '-0.01em' }}>{entity.table}</Typography>
        </Box>
        <Typography sx={{ fontSize: '0.72rem', color: 'text.secondary', fontFamily: "'JetBrains Mono', monospace", mt: 0.5 }}>
          fuente: {entity.source}
        </Typography>
      </Box>

      <Box>
        <Typography sx={labelSx}>Campos ({entity.fields.length})</Typography>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.6, maxHeight: 260, overflowY: 'auto' }}>
          {entity.fields.map((f) => (
            <Box key={f.name} sx={{ display: 'flex', alignItems: 'baseline', gap: 1, fontSize: '0.78rem' }}>
              <Typography sx={{ fontWeight: 600, minWidth: 110, fontSize: '0.78rem' }}>{f.name}</Typography>
              <Typography sx={{ color: 'text.disabled', fontFamily: "'JetBrains Mono', monospace", fontSize: '0.72rem' }}>{f.type}</Typography>
            </Box>
          ))}
        </Box>
      </Box>

      {rels.length > 0 && (
        <Box>
          <Typography sx={labelSx}>Relaciones</Typography>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.75 }}>
            {rels.map((r, i) => (
              <Box key={i} sx={{ display: 'flex', alignItems: 'center', gap: 1, fontSize: '0.78rem' }}>
                <Typography sx={{ color: '#586AD0' }}>→</Typography>
                <Typography sx={{ fontWeight: 600, fontSize: '0.78rem' }}>{r.to}</Typography>
                {r.via && <Typography sx={{ color: 'text.disabled', fontSize: '0.72rem', fontFamily: "'JetBrains Mono',monospace" }}>{r.via}</Typography>}
              </Box>
            ))}
          </Box>
        </Box>
      )}

      <Box sx={{ pt: 1, borderTop: `1px solid ${theme.palette.divider}` }}>
        <Typography sx={{ fontSize: '0.74rem', color: 'text.secondary' }}>
          {fmt(entity.count)} registros · <Box component="span" sx={{ color: '#22C55E', fontWeight: 600 }}>live</Box> · no se almacena
        </Typography>
        <Typography sx={{ fontSize: '0.7rem', color: 'text.disabled', mt: 0.25 }}>
          El dato se consulta en el momento de la pregunta.
        </Typography>
      </Box>
    </Box>
  );
}

// ── Vista: Tabla ────────────────────────────────────────────────────────────────
function TableView({ entities, edges, entitiesById, setSelected, setView, theme }) {
  const relsFor = (id) => edges
    .filter((r) => r.from === id || r.to === id)
    .map((r) => entitiesById[r.from === id ? r.to : r.from]?.table)
    .filter(Boolean);
  return (
    <Box sx={{ border: `1px solid ${theme.palette.divider}`, borderRadius: 2, overflow: 'hidden' }}>
      <Box sx={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr 0.8fr 1.6fr', gap: 1, px: 2, py: 1.25,
        bgcolor: 'action.hover', fontSize: '0.68rem', letterSpacing: '0.06em', textTransform: 'uppercase', color: 'text.disabled', fontWeight: 600 }}>
        <span>Entidad</span><span>Fuente</span><span>Registros</span><span>Relaciones</span>
      </Box>
      {entities.map((e) => (
        <Box key={e.id} onClick={() => { setSelected(e.id); setView('mapa'); }}
          sx={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr 0.8fr 1.6fr', gap: 1, px: 2, py: 1.5,
            borderTop: `1px solid ${theme.palette.divider}`, cursor: 'pointer', alignItems: 'center', '&:hover': { bgcolor: 'action.hover' } }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Box sx={{ width: 7, height: 7, borderRadius: '50%', bgcolor: e.color }} />
            <Typography sx={{ fontWeight: 600, fontSize: '0.85rem' }}>{e.table}</Typography>
          </Box>
          <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary' }}>{e.source}</Typography>
          <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary' }}>{fmt(e.count)}</Typography>
          <Typography sx={{ fontSize: '0.78rem', color: 'text.disabled' }}>{relsFor(e.id).join(', ') || '—'}</Typography>
        </Box>
      ))}
    </Box>
  );
}

// ── Vista: Salud de las conexiones ──────────────────────────────────────────────
function HealthView({ sources, entities, theme }) {
  const countFor = (sid) => entities.filter((e) => e.source_id === sid).length;
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
      {sources.map((s) => {
        const synced = !!s.synced_at;
        return (
          <Box key={s.id} sx={{ display: 'flex', alignItems: 'center', gap: 1.5, px: 2, py: 1.5,
            border: `1px solid ${theme.palette.divider}`, borderRadius: 2 }}>
            <Box sx={{ width: 9, height: 9, borderRadius: '50%', bgcolor: synced ? s.color : 'text.disabled', flexShrink: 0 }} />
            <Box sx={{ flex: 1, minWidth: 0 }}>
              <Typography sx={{ fontWeight: 600, fontSize: '0.88rem' }}>{s.name}</Typography>
              <Typography sx={{ fontSize: '0.74rem', color: 'text.secondary' }}>{s.type}</Typography>
            </Box>
            <Typography sx={{ fontSize: '0.74rem', color: 'text.disabled', flexShrink: 0 }}>{countFor(s.id)} entidades</Typography>
            <Chip label={synced ? `✓ ${new Date(s.synced_at).toLocaleString('es-CL', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}` : 'sin sincronizar'}
              size="small" sx={{ height: 24, fontSize: '0.7rem',
                bgcolor: synced ? 'rgba(34,197,94,0.12)' : 'action.hover', color: synced ? '#16A34A' : 'text.disabled' }} />
          </Box>
        );
      })}
    </Box>
  );
}

// ── Página principal ────────────────────────────────────────────────────────────
export default function ModelPage() {
  const theme = useTheme();
  const navigate = useNavigate();
  const [view, setView] = useState('mapa');
  const [selected, setSelected] = useState(null);
  const [model, setModel] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getBusinessModel()
      .then((r) => {
        setModel(r.data);
        if (r.data.entities?.length) setSelected(r.data.entities[0].id);
      })
      .catch(() => setModel({ sources: [], entities: [], edges: [], synced: false }))
      .finally(() => setLoading(false));
  }, []);

  const entities = model?.entities || [];
  const edges = model?.edges || [];
  const sources = model?.sources || [];
  const entitiesById = useMemo(() => Object.fromEntries(entities.map((e) => [e.id, e])), [entities]);
  const { pos, ...dims } = useMemo(() => layout(entities), [entities]);
  const selectedEntity = entitiesById[selected];

  const tabs = [
    { key: 'mapa', label: 'Mapa', icon: <Boxes size={14} /> },
    { key: 'tabla', label: 'Tabla', icon: <Table2 size={14} /> },
    { key: 'salud', label: 'Salud', icon: <Activity size={14} /> },
  ];

  const segmented = (
    <Box sx={{ display: 'flex', p: '3px', gap: '2px', bgcolor: 'action.hover', borderRadius: '8px' }}>
      {tabs.map((t) => {
        const active = view === t.key;
        return (
          <Box key={t.key} onClick={() => setView(t.key)}
            sx={{ display: 'flex', alignItems: 'center', gap: 0.75, px: 1.5, py: 0.6, borderRadius: '6px',
              cursor: 'pointer', fontSize: '0.8rem', fontWeight: active ? 600 : 500,
              color: active ? 'text.primary' : 'text.secondary', bgcolor: active ? 'background.paper' : 'transparent',
              boxShadow: active ? (theme.palette.mode === 'dark' ? 'none' : '0 1px 2px rgba(0,0,0,0.06)') : 'none', transition: 'all 0.12s' }}>
            {t.icon}{t.label}
          </Box>
        );
      })}
    </Box>
  );

  const hasModel = model?.synced && entities.length > 0;

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100%' }}>
      <PageHeader
        title="Tu negocio" back="/app" backLabel="Inicio"
        actions={
          <>
            {hasModel && segmented}
            <Button variant="contained" size="small" startIcon={<Plus size={15} />} onClick={() => navigate('/app/contexto?tab=integraciones')}
              sx={{ bgcolor: '#586AD0', textTransform: 'none', fontWeight: 500, boxShadow: 'none', '&:hover': { bgcolor: '#6B4CE8', boxShadow: 'none' } }}>
              Conectar
            </Button>
          </>
        }
      />

      <Box sx={{ pt: 3, pb: 5, px: { xs: 2, sm: 3 }, width: '100%', maxWidth: 1180 }}>
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', pt: 8 }}><CircularProgress sx={{ color: '#586AD0' }} /></Box>
        ) : !hasModel ? (
          <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '50vh', gap: 2.5, textAlign: 'center' }}>
            <Box sx={{ width: 64, height: 64, borderRadius: '16px', bgcolor: 'rgba(88, 106, 208,0.1)', border: '0.5px solid rgba(88, 106, 208,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Boxes size={30} color="#9BA6E3" />
            </Box>
            <Box>
              <Typography sx={{ fontWeight: 700, fontSize: '1.1rem', mb: 0.75 }}>Aún no hay un modelo</Typography>
              <Typography sx={{ color: 'text.secondary', fontSize: '0.875rem', maxWidth: 380 }}>
                Conecta un sistema en Conexiones y sincronízalo. Afable construirá aquí el mapa real de tu operación.
              </Typography>
            </Box>
            <Button startIcon={<Plus size={16} />} onClick={() => navigate('/app/contexto?tab=integraciones')}
              sx={{ bgcolor: '#586AD0', color: '#fff', borderRadius: '9px', fontWeight: 600, px: 2.5, py: 1, '&:hover': { bgcolor: '#2F42A6' } }}>
              Conectar un sistema
            </Button>
          </Box>
        ) : (
          <>
            <Box sx={{ mb: 3 }}>
              <Typography sx={{ fontSize: '1.35rem', fontWeight: 700, letterSpacing: '-0.02em' }}>Afable entendió tu operación.</Typography>
              <Typography sx={{ fontSize: '0.9rem', color: 'text.secondary', mt: 0.5, maxWidth: 620, lineHeight: 1.6 }}>
                Esto es el mapa de tu negocio: las entidades que viven en tus sistemas y cómo se relacionan.
                No es una copia de tus datos — es el índice que deja a la IA responder con tu información real.
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mt: 2 }}>
                {sources.map((s) => (
                  <Box key={s.id} sx={{ display: 'flex', alignItems: 'center', gap: 0.75, px: 1.25, py: 0.5,
                    border: `1px solid ${theme.palette.divider}`, borderRadius: '999px', fontSize: '0.76rem', color: 'text.secondary' }}>
                    <Box sx={{ width: 7, height: 7, borderRadius: '50%', bgcolor: s.color }} />
                    {s.name}
                  </Box>
                ))}
              </Box>
            </Box>

            {view === 'mapa' && (
              <Box sx={{ display: 'flex', gap: 2.5, alignItems: 'flex-start', flexWrap: { xs: 'wrap', md: 'nowrap' } }}>
                <Box sx={{ flex: 1, minWidth: 0, border: `1px solid ${theme.palette.divider}`, borderRadius: 3, bgcolor: 'background.default', p: 2,
                  backgroundImage: theme.palette.mode === 'dark' ? 'radial-gradient(rgba(255,255,255,0.04) 1px, transparent 1px)' : 'radial-gradient(rgba(0,0,0,0.04) 1px, transparent 1px)',
                  backgroundSize: '22px 22px' }}>
                  <MapView entities={entities} edges={edges} pos={pos} dims={dims} selected={selected} setSelected={setSelected} theme={theme} />
                  <Box sx={{ display: 'flex', gap: 2, mt: 1, px: 1, fontSize: '0.74rem', color: 'text.disabled' }}>
                    <span>● {entities.length} entidades</span><span>● {edges.length} relaciones</span>
                  </Box>
                </Box>
                <Box sx={{ width: { xs: '100%', md: 320 }, flexShrink: 0, border: `1px solid ${theme.palette.divider}`, borderRadius: 3, p: 2.5, bgcolor: 'background.paper' }}>
                  {selectedEntity && <DetailPanel entity={selectedEntity} edges={edges} entitiesById={entitiesById} theme={theme} />}
                </Box>
              </Box>
            )}

            {view === 'tabla' && <TableView entities={entities} edges={edges} entitiesById={entitiesById} setSelected={setSelected} setView={setView} theme={theme} />}
            {view === 'salud' && <HealthView sources={sources} entities={entities} theme={theme} />}

            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1.5, mt: 3 }}>
              {[
                { icon: <Zap size={15} color="#586AD0" />, text: 'Habilita preguntas en lenguaje natural con la fuente citada' },
                { icon: <ShieldCheck size={15} color="#22C55E" />, text: 'Los datos no se almacenan: se consultan en vivo' },
              ].map((c, i) => (
                <Box key={i} sx={{ display: 'flex', alignItems: 'center', gap: 1, px: 1.75, py: 1,
                  border: `1px solid ${theme.palette.divider}`, borderRadius: 2, fontSize: '0.8rem', color: 'text.secondary' }}>
                  {c.icon}{c.text}
                </Box>
              ))}
            </Box>
          </>
        )}
      </Box>
    </Box>
  );
}
