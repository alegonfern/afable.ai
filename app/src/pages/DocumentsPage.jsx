import { useState, useEffect, useRef, useCallback } from 'react';
import GridLayout from 'react-grid-layout';
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';
import ReactMarkdown, { defaultUrlTransform } from 'react-markdown';
import {
  Box, Typography, IconButton, Tooltip, useTheme,
} from '@mui/material';
import {
  FileText, Plus, X, Pencil, Check, GripHorizontal, Sparkles,
} from 'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../services/api';

const GRID_STYLES = `
  .afable-grid .react-grid-item.react-grid-placeholder {
    background: rgba(88, 106, 208,0.12) !important;
    border: 1px dashed rgba(88, 106, 208,0.35) !important;
    border-radius: 8px !important;
    box-shadow: none !important;
  }
  .afable-grid .react-resizable-handle { opacity: 0.2; transition: opacity 0.15s; }
  .afable-grid .react-grid-item:hover .react-resizable-handle { opacity: 0.55; }
  .afable-grid .react-grid-item.react-draggable-dragging {
    box-shadow: 0 16px 48px rgba(0,0,0,0.25) !important;
    z-index: 100;
  }
  .afable-grid .react-grid-item { transition: none !important; }
  .afable-grid .react-grid-item.cssTransforms { transition: transform 200ms ease !important; }
`;

// Los análisis guardados desde el chat traen gráficos como data:image/png —
// react-markdown los bloquea por defecto; hay que dejarlos pasar.
const allowChartImages = (url) =>
  url.startsWith('data:image/') ? url : defaultUrlTransform(url);

function getMarkdownComponents(d) {
  return {
    img: ({ src, alt }) => (
      <Box component="img" src={src} alt={alt}
        sx={{ maxWidth: '100%', borderRadius: '8px', my: 1, display: 'block', bgcolor: '#fff', p: 0.5 }} />
    ),
    h1: ({ children }) => <Typography sx={{ fontSize: '1rem', fontWeight: 700, color: 'text.primary', mb: 1, mt: 1.5 }}>{children}</Typography>,
    h2: ({ children }) => <Typography sx={{ fontSize: '0.9375rem', fontWeight: 600, color: 'text.primary', mb: 0.75, mt: 1.25 }}>{children}</Typography>,
    h3: ({ children }) => <Typography sx={{ fontSize: '0.875rem', fontWeight: 600, color: 'text.primary', mb: 0.5, mt: 1 }}>{children}</Typography>,
    p:  ({ children }) => <Typography sx={{ fontSize: '0.8125rem', color: 'text.secondary', lineHeight: 1.7, mb: 1 }}>{children}</Typography>,
    strong: ({ children }) => <Box component="strong" sx={{ color: 'text.primary', fontWeight: 600 }}>{children}</Box>,
    ul: ({ children }) => <Box component="ul" sx={{ pl: 2.5, mb: 1 }}>{children}</Box>,
    ol: ({ children }) => <Box component="ol" sx={{ pl: 2.5, mb: 1 }}>{children}</Box>,
    li: ({ children }) => <Box component="li" sx={{ fontSize: '0.8125rem', color: 'text.secondary', lineHeight: 1.7, mb: 0.25 }}>{children}</Box>,
    code: ({ children }) => <Box component="code" sx={{ bgcolor: d ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)', px: 0.625, py: 0.125, borderRadius: '3px', fontSize: '0.78em', color: '#9BA6E3', fontFamily: 'monospace' }}>{children}</Box>,
    blockquote: ({ children }) => <Box sx={{ borderLeft: '2px solid #586AD0', pl: 1.5, my: 1, color: 'text.secondary', fontStyle: 'italic' }}>{children}</Box>,
    hr: () => <Box sx={{ borderTop: '1px solid', borderColor: 'divider', my: 1.5 }} />,
  };
}

function DocumentCard({ doc, onDelete, onUpdate }) {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const [mode, setMode] = useState('view');
  const [title, setTitle] = useState(doc.title);
  const [content, setContent] = useState(doc.content);
  const mdComponents = getMarkdownComponents(d);

  const handleTitleBlur = async () => {
    if (title === doc.title) return;
    try {
      await api.updateDocument(doc.id, { title });
      onUpdate(doc.id, { title });
    } catch { setTitle(doc.title); }
  };

  const handleContentBlur = async () => {
    setMode('view');
    if (content === doc.content) return;
    try {
      await api.updateDocument(doc.id, { content });
      onUpdate(doc.id, { content });
    } catch { setContent(doc.content); }
  };

  const handleDelete = async () => {
    if (!window.confirm('¿Eliminar este documento?')) return;
    try {
      await api.deleteDocument(doc.id);
      onDelete(doc.id);
    } catch { toast.error('Error al eliminar'); }
  };

  return (
    <Box sx={{
      height: '100%', display: 'flex', flexDirection: 'column',
      bgcolor: 'background.paper',
      border: `1px solid ${theme.palette.divider}`,
      borderRadius: '8px', overflow: 'hidden',
    }}>
      {/* Header — drag handle */}
      <Box
        className="card-header"
        sx={{
          display: 'flex', alignItems: 'center', gap: 0.75,
          px: 1.5, py: 1,
          borderBottom: `1px solid ${theme.palette.divider}`,
          cursor: 'grab', flexShrink: 0,
          bgcolor: 'background.paper',
          '&:active': { cursor: 'grabbing' },
        }}
      >
        <FileText size={13} color="#9BA6E3" style={{ flexShrink: 0 }} />

        <Box
          component="input"
          value={title}
          onChange={e => setTitle(e.target.value)}
          onBlur={handleTitleBlur}
          onMouseDown={e => e.stopPropagation()}
          sx={{
            flex: 1, minWidth: 0,
            bgcolor: 'transparent', border: 'none', outline: 'none',
            fontSize: '0.8125rem', fontWeight: 500,
            color: 'text.primary',
            fontFamily: 'Inter, sans-serif', cursor: 'text',
          }}
        />

        {doc.conversation && (
          <Box sx={{ px: 0.625, py: 0.125, borderRadius: '3px', bgcolor: 'rgba(155, 166, 227,0.12)', border: '0.5px solid rgba(155, 166, 227,0.2)', flexShrink: 0 }}>
            <Typography sx={{ fontSize: '0.625rem', fontWeight: 600, color: '#9BA6E3', letterSpacing: '0.05em' }}>IA</Typography>
          </Box>
        )}

        <GripHorizontal size={11} color={d ? 'rgba(255,255,255,0.18)' : 'rgba(0,0,0,0.2)'} style={{ flexShrink: 0 }} />

        <Tooltip title={mode === 'edit' ? 'Ver' : 'Editar'} placement="top">
          <IconButton
            size="small" className="nodrag"
            onMouseDown={e => e.stopPropagation()}
            onClick={() => setMode(m => m === 'edit' ? 'view' : 'edit')}
            sx={{ p: 0.25, color: mode === 'edit' ? '#9BA6E3' : 'text.disabled', '&:hover': { color: '#9BA6E3' } }}
          >
            {mode === 'edit' ? <Check size={12} /> : <Pencil size={12} />}
          </IconButton>
        </Tooltip>

        <IconButton
          size="small" className="nodrag"
          onMouseDown={e => e.stopPropagation()}
          onClick={handleDelete}
          sx={{ p: 0.25, color: 'text.disabled', '&:hover': { color: '#f87171' } }}
        >
          <X size={12} />
        </IconButton>
      </Box>

      {/* Content */}
      <Box sx={{ flex: 1, overflow: 'hidden', position: 'relative' }}>
        {mode === 'edit' ? (
          <Box
            component="textarea"
            value={content}
            onChange={e => setContent(e.target.value)}
            onBlur={handleContentBlur}
            autoFocus
            sx={{
              width: '100%', height: '100%', p: 1.5,
              bgcolor: 'background.paper',
              border: 'none', outline: 'none', resize: 'none',
              color: 'text.primary',
              fontSize: '0.8125rem', lineHeight: 1.65,
              fontFamily: 'Inter, sans-serif',
              '&::placeholder': { color: d ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.3)' },
              boxSizing: 'border-box',
            }}
            placeholder="Escribe aquí..."
          />
        ) : (
          <Box
            onDoubleClick={() => setMode('edit')}
            sx={{ height: '100%', overflowY: 'auto', px: 1.75, pt: 1.25, pb: 1, cursor: 'text' }}
          >
            {content ? (
              <ReactMarkdown components={mdComponents} urlTransform={allowChartImages}>{content}</ReactMarkdown>
            ) : (
              <Typography sx={{ fontSize: '0.8rem', color: 'text.disabled', fontStyle: 'italic' }}>
                Doble click para editar…
              </Typography>
            )}
          </Box>
        )}
      </Box>
    </Box>
  );
}

const STORAGE_KEY = 'afable-docs-layout';

export default function DocumentsPage() {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const [docs, setDocs] = useState([]);
  const [layout, setLayout] = useState([]);
  const [loading, setLoading] = useState(true);
  const [containerWidth, setContainerWidth] = useState(900);
  const containerRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const ro = new ResizeObserver(entries => {
      setContainerWidth(entries[0].contentRect.width);
    });
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    api.getDocuments()
      .then(res => {
        const data = res.data || [];
        setDocs(data);
        const saved = (() => {
          try { return JSON.parse(localStorage.getItem(STORAGE_KEY)) || []; }
          catch { return []; }
        })();
        if (saved.length > 0 && saved.every(s => data.find(d => String(d.id) === String(s.i)))) {
          setLayout(saved);
        } else {
          setLayout(data.map((doc, idx) => ({
            i: String(doc.id),
            x: (idx % 2) * 6, y: Math.floor(idx / 2) * 6,
            w: doc.grid_w || 6, h: doc.grid_h || 5,
            minW: 3, minH: 3,
          })));
        }
      })
      .catch(() => setDocs([]))
      .finally(() => setLoading(false));
  }, []);

  const handleLayoutChange = useCallback((newLayout) => {
    setLayout(newLayout);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(newLayout));
  }, []);

  const handleDelete = (id) => {
    setDocs(prev => prev.filter(d => d.id !== id));
    setLayout(prev => prev.filter(l => l.i !== String(id)));
    toast.success('Documento eliminado');
  };

  const handleUpdate = (id, changes) => {
    setDocs(prev => prev.map(d => d.id === id ? { ...d, ...changes } : d));
  };

  const handleNew = async () => {
    try {
      const nextY = layout.reduce((max, l) => Math.max(max, l.y + l.h), 0);
      const res = await api.createDocument({
        title: 'Nuevo documento', content: '',
        grid_x: 0, grid_y: nextY, grid_w: 6, grid_h: 5,
      });
      const doc = res.data;
      setDocs(prev => [...prev, doc]);
      setLayout(prev => [...prev, { i: String(doc.id), x: 0, y: nextY, w: 6, h: 5, minW: 3, minH: 3 }]);
    } catch {
      toast.error('Error al crear documento');
    }
  };

  return (
    <Box ref={containerRef} sx={{ minHeight: 'calc(100vh - 52px)' }}>
      <style>{GRID_STYLES}</style>

      {/* Header */}
      <Box sx={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        px: 3, py: 2,
        borderBottom: `1px solid ${theme.palette.divider}`,
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <FileText size={16} color="#9BA6E3" />
          <Typography sx={{ fontSize: '0.9375rem', fontWeight: 600, color: 'text.primary' }}>
            Lienzo de documentos
          </Typography>
          {!loading && docs.length > 0 && (
            <Box sx={{ px: 0.75, py: 0.125, borderRadius: '4px', bgcolor: d ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)' }}>
              <Typography sx={{ fontSize: '0.7rem', color: 'text.secondary', fontWeight: 500 }}>{docs.length}</Typography>
            </Box>
          )}
        </Box>
        <Box
          onClick={handleNew}
          sx={{
            display: 'flex', alignItems: 'center', gap: 0.75,
            px: 1.25, py: 0.625, borderRadius: '6px',
            border: `1px solid ${theme.palette.divider}`,
            cursor: 'pointer', color: 'text.secondary',
            '&:hover': { bgcolor: 'action.hover', color: 'text.primary' },
            transition: 'all 0.12s',
          }}
        >
          <Plus size={13} />
          <Typography sx={{ fontSize: '0.8125rem', fontWeight: 500 }}>Nuevo</Typography>
        </Box>
      </Box>

      {/* Loading */}
      {loading && (
        <Box sx={{ p: 3, display: 'flex', gap: 1.5 }}>
          {[1, 2, 3].map(i => (
            <Box key={i} sx={{ flex: 1, height: 280, bgcolor: 'action.hover', borderRadius: '8px', opacity: 0.3 + i * 0.1 }} />
          ))}
        </Box>
      )}

      {/* Empty state */}
      {!loading && docs.length === 0 && (
        <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '60vh', gap: 2 }}>
          <FileText size={40} color={d ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.15)'} />
          <Typography sx={{ color: 'text.secondary', fontSize: '0.9rem', fontWeight: 500 }}>
            Tu lienzo está vacío
          </Typography>
          <Typography sx={{ color: 'text.disabled', fontSize: '0.8rem', textAlign: 'center', maxWidth: 320, lineHeight: 1.6 }}>
            Pide al AI que genere un reporte o análisis y aparecerá aquí automáticamente
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, px: 1.25, py: 0.625, borderRadius: '6px', bgcolor: 'rgba(88, 106, 208,0.08)', border: '1px solid rgba(88, 106, 208,0.15)', color: '#9BA6E3', cursor: 'default' }}>
            <Sparkles size={13} />
            <Typography sx={{ fontSize: '0.8rem' }}>Prueba: "genera un reporte de ventas Q1"</Typography>
          </Box>
        </Box>
      )}

      {/* Canvas */}
      {!loading && docs.length > 0 && containerWidth > 0 && (
        <Box sx={{ px: 1.5, pt: 1.5 }}>
          <GridLayout
            className="afable-grid"
            layout={layout}
            cols={12}
            rowHeight={55}
            width={containerWidth - 24}
            draggableHandle=".card-header"
            onLayoutChange={handleLayoutChange}
            compactType={null}
            preventCollision={false}
            margin={[12, 12]}
            isResizable
            isDraggable
          >
            {docs.map(doc => (
              <div key={String(doc.id)}>
                <DocumentCard doc={doc} onDelete={handleDelete} onUpdate={handleUpdate} />
              </div>
            ))}
          </GridLayout>
        </Box>
      )}
    </Box>
  );
}
