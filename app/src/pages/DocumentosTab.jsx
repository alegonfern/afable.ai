import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Box, Typography, Button, LinearProgress, CircularProgress, useTheme,
  Switch, FormControlLabel, IconButton, Tabs, Tab,
} from '@mui/material';
import { Upload, Trash2, FileText, Globe, Lock } from 'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../services/api';
import { useApp } from '../context/AppContext';

const QUOTA_BYTES = 100 * 1024 * 1024; // 100MB por usuario

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function DocumentosTab() {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const { selectedOrganization } = useApp();
  const orgId = selectedOrganization?.id;
  const fileRef = useRef(null);

  const [view, setView] = useState('mine'); // 'mine' | 'company'
  const [mine, setMine] = useState([]);
  const [company, setCompany] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [makePublic, setMakePublic] = useState(false);

  const bgCard = d ? 'rgba(255,255,255,0.04)' : theme.palette.background.paper;
  const borderColor = theme.palette.divider;
  const textMuted = d ? 'rgba(255,255,255,0.45)' : 'rgba(0,0,0,0.45)';

  const load = useCallback(() => {
    if (!orgId) return;
    setLoading(true);
    Promise.all([
      api.getCompanyDocuments(orgId, 'mine'),
      api.getCompanyDocuments(orgId, 'company'),
    ])
      .then(([m, c]) => { setMine(m.data); setCompany(c.data); })
      .catch(() => toast.error('No se pudieron cargar los documentos'))
      .finally(() => setLoading(false));
  }, [orgId]);

  useEffect(() => { load(); }, [load]);

  const usedBytes = mine.reduce((sum, doc) => sum + (doc.size || 0), 0);
  const usedPct = Math.min(100, (usedBytes / QUOTA_BYTES) * 100);

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file || !orgId) return;
    if (usedBytes + file.size > QUOTA_BYTES) {
      toast.error('Ese archivo supera tu cuota de 100MB.');
      e.target.value = '';
      return;
    }
    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);
    formData.append('title', file.name);
    formData.append('is_public', makePublic ? 'true' : 'false');
    try {
      await api.uploadCompanyDocument(orgId, formData);
      toast.success('Documento subido');
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'No se pudo subir el archivo');
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  const handleDelete = async (docId) => {
    if (!orgId) return;
    try {
      await api.deleteCompanyDocument(orgId, docId);
      load();
    } catch {
      toast.error('No se pudo eliminar');
    }
  };

  const list = view === 'mine' ? mine : company;

  return (
    <Box>
      <Typography sx={{ fontSize: '0.85rem', color: 'text.secondary', mb: 2 }}>
        Archivos que sirven de contexto para la IA. 100MB de espacio por usuario — nacen
        privados, vos decidís si se ven para toda la empresa.
      </Typography>

      {/* Cuota */}
      <Box sx={{ mb: 2.5, p: 1.5, borderRadius: '8px', border: `1px solid ${borderColor}`, bgcolor: bgCard }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.75 }}>
          <Typography sx={{ fontSize: '0.75rem', color: textMuted }}>Tu almacenamiento</Typography>
          <Typography sx={{ fontSize: '0.75rem', color: textMuted }}>
            {formatSize(usedBytes)} / 100 MB
          </Typography>
        </Box>
        <LinearProgress
          variant="determinate" value={usedPct}
          sx={{
            height: 6, borderRadius: 3, bgcolor: d ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)',
            '& .MuiLinearProgress-bar': { bgcolor: usedPct > 90 ? '#ef4444' : '#586AD0', borderRadius: 3 },
          }}
        />
      </Box>

      {/* Subir */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 3, flexWrap: 'wrap' }}>
        <Button
          variant="outlined" size="small" component="label"
          startIcon={uploading ? <CircularProgress size={14} /> : <Upload size={14} />}
          disabled={uploading}
          sx={{ textTransform: 'none', fontSize: '0.8rem' }}
        >
          Subir documento
          <input ref={fileRef} type="file" hidden onChange={handleUpload} />
        </Button>
        <FormControlLabel
          control={<Switch size="small" checked={makePublic} onChange={(e) => setMakePublic(e.target.checked)} />}
          label={<Typography sx={{ fontSize: '0.78rem', color: textMuted }}>Subir como público</Typography>}
        />
      </Box>

      {/* Mis documentos / Documentos de la empresa */}
      <Tabs
        value={view} onChange={(_, v) => setView(v)}
        sx={{ minHeight: 32, mb: 1.5, '& .MuiTab-root': { minHeight: 32, textTransform: 'none', fontSize: '0.8rem' } }}
      >
        <Tab value="mine" label="Mis documentos" />
        <Tab value="company" label="Documentos de la empresa" />
      </Tabs>

      {loading ? (
        <CircularProgress size={20} />
      ) : list.length === 0 ? (
        <Typography sx={{ fontSize: '0.8rem', color: textMuted }}>
          {view === 'mine' ? 'Todavía no subiste ningún documento.' : 'Nadie marcó documentos como públicos.'}
        </Typography>
      ) : (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.75 }}>
          {list.map(doc => (
            <Box
              key={doc.id}
              sx={{
                display: 'flex', alignItems: 'center', gap: 1.25, px: 1.5, py: 1,
                borderRadius: '6px', border: `1px solid ${borderColor}`, bgcolor: bgCard,
              }}
            >
              <FileText size={16} color={textMuted} style={{ flexShrink: 0 }} />
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography sx={{ fontSize: '0.82rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {doc.title}
                </Typography>
                <Typography sx={{ fontSize: '0.72rem', color: textMuted }}>
                  {formatSize(doc.size || 0)}
                </Typography>
              </Box>
              {doc.is_public ? <Globe size={13} color="#34D399" /> : <Lock size={13} color={textMuted} />}
              {doc.is_mine && (
                <IconButton size="small" onClick={() => handleDelete(doc.id)}>
                  <Trash2 size={14} color={textMuted} />
                </IconButton>
              )}
            </Box>
          ))}
        </Box>
      )}
    </Box>
  );
}
