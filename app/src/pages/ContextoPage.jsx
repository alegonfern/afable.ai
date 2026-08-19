import { useState, useEffect, useCallback } from 'react';
import { Box, Typography, TextField, CircularProgress, useTheme } from '@mui/material';
import { Plus, Trash2, Pencil, FileText as FileIcon, Sparkles } from 'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../services/api';
import PageHeader from '../components/PageHeader';
import { useApp } from '../context/AppContext';

function SectionLabel({ children }) {
  return (
    <Typography sx={{ fontSize: '0.6875rem', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: '#586AD0', mb: 1.5 }}>
      {children}
    </Typography>
  );
}

export default function ContextoPage({ hideHeader = false }) {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const { selectedOrganization } = useApp();
  const orgId = selectedOrganization?.id;

  const textMuted = d ? 'rgba(255,255,255,0.45)' : 'rgba(0,0,0,0.45)';
  const textSemi = d ? 'rgba(255,255,255,0.70)' : 'rgba(0,0,0,0.70)';
  const bgCard = d ? 'rgba(255,255,255,0.04)' : theme.palette.background.paper;
  const bgInput = d ? 'rgba(255,255,255,0.04)' : theme.palette.background.paper;
  const borderColor = theme.palette.divider;

  const inputSx = {
    '& .MuiOutlinedInput-root': {
      bgcolor: bgInput, borderRadius: '8px', fontSize: '0.875rem', color: theme.palette.text.primary,
      '& fieldset': { borderColor },
      '&:hover fieldset': { borderColor: d ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.2)' },
      '&.Mui-focused fieldset': { borderColor: '#586AD0' },
    },
    '& .MuiInputLabel-root': { color: textMuted, fontSize: '0.875rem' },
    '& .MuiInputLabel-root.Mui-focused': { color: '#9BA6E3' },
  };

  const [cubicles, setCubicles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [markdown, setMarkdown] = useState('');
  const [loadingMd, setLoadingMd] = useState(true);

  const [newTitle, setNewTitle] = useState('');
  const [newContent, setNewContent] = useState('');
  const [creating, setCreating] = useState(false);

  const [editingId, setEditingId] = useState(null);
  const [editTitle, setEditTitle] = useState('');
  const [editContent, setEditContent] = useState('');
  const [saving, setSaving] = useState(false);

  const refreshMarkdown = useCallback(() => {
    if (!orgId) return;
    setLoadingMd(true);
    api.getContextMarkdown(orgId)
      .then(r => setMarkdown(r.data.markdown || ''))
      .catch(() => {})
      .finally(() => setLoadingMd(false));
  }, [orgId]);

  useEffect(() => {
    if (!orgId) { setLoading(false); setLoadingMd(false); return; }
    setLoading(true);
    api.getContextCubicles(orgId)
      .then(r => setCubicles(r.data))
      .catch(() => {})
      .finally(() => setLoading(false));
    refreshMarkdown();
  }, [orgId, refreshMarkdown]);

  const handleCreate = async () => {
    if (!newTitle.trim() || !newContent.trim() || !orgId) return;
    setCreating(true);
    try {
      const res = await api.createContextCubicle(orgId, { title: newTitle.trim(), content: newContent.trim() });
      setCubicles(prev => [...prev, res.data]);
      setNewTitle(''); setNewContent('');
      refreshMarkdown();
      toast.success('Cubículo agregado');
    } catch {
      toast.error('No se pudo crear el cubículo');
    } finally {
      setCreating(false);
    }
  };

  const startEdit = (c) => { setEditingId(c.id); setEditTitle(c.title); setEditContent(c.content); };
  const cancelEdit = () => setEditingId(null);

  const handleSaveEdit = async (id) => {
    if (!orgId) return;
    setSaving(true);
    try {
      const res = await api.updateContextCubicle(orgId, id, { title: editTitle.trim(), content: editContent.trim() });
      setCubicles(prev => prev.map(c => c.id === id ? res.data : c));
      setEditingId(null);
      refreshMarkdown();
      toast.success('Cubículo actualizado');
    } catch {
      toast.error('No se pudo guardar');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id) => {
    if (!orgId) return;
    try {
      await api.deleteContextCubicle(orgId, id);
      setCubicles(prev => prev.filter(c => c.id !== id));
      refreshMarkdown();
      toast.success('Cubículo eliminado');
    } catch {
      toast.error('No se pudo eliminar');
    }
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
      {!hideHeader && <PageHeader title="Contexto" backLabel="Inicio" back="/app" />}

      <Box sx={{ p: { xs: 2, sm: 3 }, display: 'flex', gap: 3, flexWrap: 'wrap', alignItems: 'flex-start' }}>
        {!orgId ? (
          <Typography sx={{ color: textMuted, fontSize: '0.875rem' }}>
            Primero configure su Workspace para poder editar este contexto.
          </Typography>
        ) : (
          <>
            <Box sx={{ flex: '1 1 420px', minWidth: 320, maxWidth: 560 }}>
              <Typography sx={{ fontSize: '0.8rem', color: textMuted, mb: 2.5, lineHeight: 1.5 }}>
                Cada cubículo es un bloque de información sobre tu empresa — lo que sea que quieras que la IA sepa
                siempre. Todos se juntan en un archivo <strong>contexto.md</strong> real (lo ves a la derecha) que
                el agente lee antes de responderte. Agrega uno y pregúntale al agente sobre eso — vas a ver
                exactamente de dónde saca la respuesta.
              </Typography>

              <SectionLabel>Nuevo cubículo</SectionLabel>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5, mb: 3, p: 2, borderRadius: '10px', border: `1px solid ${borderColor}`, bgcolor: bgCard }}>
                <TextField
                  label="Título" value={newTitle} onChange={e => setNewTitle(e.target.value.slice(0, 120))}
                  placeholder="Ej: Horarios de atención, Política de garantía, Nuestros valores..."
                  fullWidth size="small" sx={inputSx}
                />
                <TextField
                  label="Contenido" value={newContent} onChange={e => setNewContent(e.target.value)}
                  placeholder="Escriba lo que quiera que la IA sepa sobre esto..."
                  multiline rows={3} fullWidth sx={inputSx}
                />
                <Box
                  component="button" onClick={handleCreate} disabled={creating || !newTitle.trim() || !newContent.trim()}
                  sx={{
                    alignSelf: 'flex-start', px: 2.5, py: 1, borderRadius: '8px', border: 'none',
                    cursor: creating ? 'default' : 'pointer',
                    bgcolor: (creating || !newTitle.trim() || !newContent.trim()) ? 'rgba(88, 106, 208,0.4)' : '#586AD0',
                    color: '#fff', fontSize: '0.8rem', fontWeight: 600,
                    display: 'flex', alignItems: 'center', gap: 0.75,
                    '&:hover:not(:disabled)': { bgcolor: '#2F42A6' },
                  }}
                >
                  {creating ? <CircularProgress size={13} sx={{ color: '#fff' }} /> : <Plus size={14} />}
                  {creating ? 'Agregando...' : 'Agregar cubículo'}
                </Box>
              </Box>

              <SectionLabel>Tus cubículos ({cubicles.length})</SectionLabel>
              {loading ? (
                <CircularProgress size={20} sx={{ color: '#9BA6E3' }} />
              ) : cubicles.length === 0 ? (
                <Typography sx={{ fontSize: '0.8rem', color: textMuted }}>Todavía no hay cubículos.</Typography>
              ) : (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.25 }}>
                  {cubicles.map(c => (
                    <Box key={c.id} sx={{ p: 1.5, borderRadius: '8px', border: `1px solid ${borderColor}`, bgcolor: bgCard }}>
                      {editingId === c.id ? (
                        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                          <TextField value={editTitle} onChange={e => setEditTitle(e.target.value.slice(0, 120))} size="small" sx={inputSx} />
                          <TextField value={editContent} onChange={e => setEditContent(e.target.value)} multiline rows={3} sx={inputSx} />
                          <Box sx={{ display: 'flex', gap: 1 }}>
                            <Box component="button" onClick={() => handleSaveEdit(c.id)} disabled={saving}
                              sx={{ px: 2, py: 0.6, borderRadius: '6px', border: 'none', cursor: 'pointer', bgcolor: '#586AD0', color: '#fff', fontSize: '0.75rem', fontWeight: 600 }}>
                              {saving ? 'Guardando...' : 'Guardar'}
                            </Box>
                            <Box component="button" onClick={cancelEdit}
                              sx={{ px: 2, py: 0.6, borderRadius: '6px', border: `1px solid ${borderColor}`, cursor: 'pointer', bgcolor: 'transparent', color: theme.palette.text.primary, fontSize: '0.75rem', fontWeight: 600 }}>
                              Cancelar
                            </Box>
                          </Box>
                        </Box>
                      ) : (
                        <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1.5 }}>
                          <Box sx={{ flex: 1, minWidth: 0 }}>
                            <Typography sx={{ fontSize: '0.85rem', fontWeight: 600, color: theme.palette.text.primary }}>
                              {c.title}
                            </Typography>
                            <Typography sx={{ fontSize: '0.75rem', color: textSemi, mt: 0.5, lineHeight: 1.4, whiteSpace: 'pre-wrap' }}>
                              {c.content}
                            </Typography>
                          </Box>
                          <Box sx={{ display: 'flex', gap: 0.5, flexShrink: 0 }}>
                            <Box onClick={() => startEdit(c)} sx={{ color: textMuted, cursor: 'pointer', p: 0.5, '&:hover': { color: '#9BA6E3' } }}>
                              <Pencil size={14} />
                            </Box>
                            <Box onClick={() => handleDelete(c.id)} sx={{ color: textMuted, cursor: 'pointer', p: 0.5, '&:hover': { color: '#e57373' } }}>
                              <Trash2 size={14} />
                            </Box>
                          </Box>
                        </Box>
                      )}
                    </Box>
                  ))}
                </Box>
              )}
            </Box>

            <Box sx={{ flex: '1 1 380px', minWidth: 300, maxWidth: 520, position: 'sticky', top: 16 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
                <FileIcon size={14} color="#9BA6E3" />
                <Typography sx={{ fontSize: '0.75rem', fontFamily: 'JetBrains Mono, monospace', color: textMuted }}>
                  contexto.md
                </Typography>
                <Sparkles size={12} color="#9BA6E3" />
              </Box>
              <Box
                sx={{
                  p: 2, borderRadius: '10px', border: `1px solid ${borderColor}`, bgcolor: bgCard,
                  fontFamily: 'JetBrains Mono, monospace', fontSize: '0.75rem', lineHeight: 1.6,
                  color: textSemi, whiteSpace: 'pre-wrap', maxHeight: '70vh', overflowY: 'auto',
                }}
              >
                {loadingMd ? (
                  <CircularProgress size={16} sx={{ color: '#9BA6E3' }} />
                ) : markdown ? markdown : (
                  <Typography sx={{ fontSize: '0.75rem', color: textMuted, fontStyle: 'italic' }}>
                    Este archivo se genera solo — agrega tu primer cubículo y aparece acá.
                  </Typography>
                )}
              </Box>
            </Box>
          </>
        )}
      </Box>
    </Box>
  );
}
