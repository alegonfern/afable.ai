import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box, Typography, Divider, TextField, CircularProgress, useTheme, MenuItem, Select,
} from '@mui/material';
import { BookOpen, Package, ShieldCheck, DollarSign, File, Upload, Trash2, Building2, User } from 'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../services/api';
import PageHeader from '../components/PageHeader';
import ContextoPage from './ContextoPage';
import { useApp } from '../context/AppContext';

const CATEGORIES = [
  { value: 'politica',   label: 'Política',   icon: ShieldCheck },
  { value: 'manual',     label: 'Manual',     icon: BookOpen },
  { value: 'catalogo',   label: 'Catálogo',   icon: Package },
  { value: 'financiero', label: 'Financiero', icon: DollarSign },
  { value: 'otro',       label: 'Otro',       icon: File },
];

const categoryMeta = (value) => CATEGORIES.find(c => c.value === value) || CATEGORIES[4];

const SectionLabel = ({ children }) => (
  <Typography sx={{ fontSize: '0.6875rem', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: '#586AD0', mb: 1.5 }}>
    {children}
  </Typography>
);

const ORG_FIELDS = [
  { key: 'business_description', label: 'Qué hace la empresa', placeholder: 'Ej: Fabricamos e instalamos cocinas a medida para proyectos residenciales...', limit: 500, rows: 3 },
  { key: 'products_services',    label: 'Productos y servicios', placeholder: 'Ej: Diseño, fabricación e instalación de muebles de cocina, closets...', limit: 500, rows: 3 },
  { key: 'target_customers',     label: 'Clientes objetivo', placeholder: 'Ej: Inmobiliarias y arquitectos que desarrollan proyectos residenciales...', limit: 300, rows: 2 },
  { key: 'glossary',             label: 'Glosario de negocio', placeholder: 'Ej: "OC" = orden de compra, "cliente VIP" = compras sobre $5M/año...', limit: 800, rows: 3 },
  { key: 'tone_guidelines',      label: 'Cómo debe hablar el agente', placeholder: 'Ej: Formal pero cercano, sin tecnicismos, siempre en español...', limit: 300, rows: 2 },
  { key: 'restrictions',         label: 'Restricciones — qué NUNCA debe hacer', placeholder: 'Ej: Nunca ofrecer descuentos, nunca revelar márgenes o costos internos...', limit: 500, rows: 3 },
];


function SaveButton({ saving, onClick, children }) {
  return (
    <Box
      component="button" onClick={onClick} disabled={saving}
      sx={{
        alignSelf: 'flex-start', px: 3, py: 1, borderRadius: '8px', border: 'none',
        cursor: saving ? 'default' : 'pointer',
        bgcolor: saving ? 'rgba(88, 106, 208,0.4)' : '#586AD0',
        color: '#fff', fontSize: '0.875rem', fontWeight: 600,
        display: 'flex', alignItems: 'center', gap: 1,
        '&:hover:not(:disabled)': { bgcolor: '#2F42A6' },
      }}
    >
      {saving && <CircularProgress size={14} sx={{ color: '#fff' }} />}
      {saving ? 'Guardando...' : children}
    </Box>
  );
}

function ContextForm({ fields, form, setForm, inputSx, textMuted, disabled }) {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      {fields.map(f => (
        <Box key={f.key}>
          <TextField
            label={f.label}
            value={form[f.key] || ''}
            onChange={e => setForm(prev => ({ ...prev, [f.key]: e.target.value.slice(0, f.limit) }))}
            placeholder={f.placeholder}
            multiline rows={f.rows} fullWidth disabled={disabled} sx={{ ...inputSx, mb: 0.5 }}
          />
          {!disabled && (
            <Typography sx={{ fontSize: '0.7rem', color: textMuted, textAlign: 'right' }}>
              {(form[f.key] || '').length}/{f.limit}
            </Typography>
          )}
        </Box>
      ))}
    </Box>
  );
}

export default function MiContextoPage({ hideHeader = false }) {
  const navigate = useNavigate();
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const { selectedOrganization } = useApp();
  const orgId = selectedOrganization?.id;

  const textMuted = d ? 'rgba(255,255,255,0.45)' : 'rgba(0,0,0,0.45)';
  const textSemi = d ? 'rgba(255,255,255,0.70)' : 'rgba(0,0,0,0.70)';
  const bgInput = d ? 'rgba(255,255,255,0.04)' : theme.palette.background.paper;
  const bgCard = d ? 'rgba(255,255,255,0.04)' : theme.palette.background.paper;
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


  // ── Capa empresa ──
  const [orgForm, setOrgForm] = useState({});
  const [canEdit, setCanEdit] = useState(true);
  const [loadingOrg, setLoadingOrg] = useState(true);
  const [savingOrg, setSavingOrg] = useState(false);

  const [docs, setDocs] = useState([]);
  const [loadingDocs, setLoadingDocs] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadCategory, setUploadCategory] = useState('otro');
  const fileRef = useRef();

  // ── Capa personal ──

  useEffect(() => {
  }, []);

  useEffect(() => {
    if (!orgId) { setLoadingOrg(false); setLoadingDocs(false); return; }
    setLoadingOrg(true);
    api.getOrgContext(orgId).then(r => {
      setOrgForm(r.data);
      setCanEdit(r.data.can_edit !== false);
    }).catch(() => {}).finally(() => setLoadingOrg(false));
    loadDocs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orgId]);

  const loadDocs = () => {
    if (!orgId) return;
    setLoadingDocs(true);
    api.getCompanyDocuments(orgId).then(r => setDocs(r.data)).catch(() => {}).finally(() => setLoadingDocs(false));
  };

  const handleSaveOrg = async () => {
    if (!orgId) return;
    setSavingOrg(true);
    try {
      const { can_edit, updated_at, ...data } = orgForm;
      await api.updateOrgContext(orgId, data);
      toast.success('Contexto de empresa guardado. La IA lo usará en todas las conversaciones.');
    } catch {
      toast.error('Error al guardar el contexto');
    } finally {
      setSavingOrg(false);
    }
  };


  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file || !orgId) return;
    if (docs.length >= 20) { toast.error('Llegaste al máximo de 20 archivos.'); return; }
    if (file.size > 10 * 1024 * 1024) { toast.error('El archivo supera el máximo de 10MB.'); return; }

    setUploading(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('title', file.name);
      fd.append('category', uploadCategory);
      const res = await api.uploadCompanyDocument(orgId, fd);
      setDocs(prev => [res.data, ...prev]);
      toast.success(res.data.processing_error ? 'Archivo subido (sin resumen automático)' : 'Archivo subido y procesado');
    } catch {
      toast.error('Error al subir el archivo');
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (id) => {
    if (!orgId) return;
    try {
      await api.deleteCompanyDocument(orgId, id);
      setDocs(prev => prev.filter(doc => doc.id !== id));
      toast.success('Archivo eliminado');
    } catch {
      toast.error('Error al eliminar el archivo');
    }
  };

  const tabSx = {
    textTransform: 'none', fontSize: '0.85rem', fontWeight: 600, minHeight: 40,
    color: textMuted, '&.Mui-selected': { color: '#586AD0' },
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
      {!hideHeader && <PageHeader title="Contexto de la empresa" backLabel="Inicio" back="/app" />}


      {/* ══ Pestaña EMPRESA ══ */}
      {(
        <Box sx={{ p: { xs: 2, sm: 3 }, maxWidth: 720 }}>
          {!orgId ? (
            <Typography sx={{ color: textMuted, fontSize: '0.875rem' }}>
              Primero configure su Workspace para poder editar este contexto.
            </Typography>
          ) : (
            <>
              <Typography sx={{ fontSize: '0.8rem', color: textMuted, mb: 3 }}>
                Capa compartida con toda la empresa: la IA la usa en las conversaciones de todos los usuarios de{' '}
                {selectedOrganization?.nombre || 'tu empresa'}.
                {!canEdit && ' Solo el administrador puede editarla — la ves en modo lectura.'}
              </Typography>

              <SectionLabel>Formulario</SectionLabel>
              {loadingOrg ? (
                <CircularProgress size={20} sx={{ color: '#9BA6E3', mb: 3 }} />
              ) : (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mb: 3 }}>
                  <ContextForm
                    fields={ORG_FIELDS} form={orgForm} setForm={setOrgForm}
                    inputSx={inputSx} textMuted={textMuted} disabled={!canEdit}
                  />
                  {canEdit && <SaveButton saving={savingOrg} onClick={handleSaveOrg}>Guardar contexto</SaveButton>}
                </Box>
              )}

              <Divider sx={{ borderColor, mb: 3 }} />

              {/* Los Cubículos eran una pantalla aparte con su propia pestaña, y
                  entran al MISMO prompt que el formulario de arriba: dos lugares para
                  lo mismo, y ninguno mencionaba al otro. Acá son la sección libre de
                  esta pantalla, para lo que no cabe en un campo del formulario. */}
              <SectionLabel>Bloques libres</SectionLabel>
              <Typography sx={{ fontSize: '0.8rem', color: textMuted, mb: 2, mt: -1 }}>
                Para lo que no entra en los campos de arriba. Cada bloque se le entrega al
                agente tal como lo escriba.
              </Typography>
              <Box sx={{ mb: 3, ml: -3, mr: -3 }}>
                <ContextoPage hideHeader />
              </Box>

              <Divider sx={{ borderColor, mb: 3 }} />

              <SectionLabel>Archivos</SectionLabel>
              <Typography sx={{ fontSize: '0.8rem', color: textMuted, mb: 1.5, mt: -1 }}>
                Las políticas, manuales y catálogos viven en Archivos, con carpetas,
                versiones y edición. El agente los lee desde ahí.
              </Typography>
              <Box
                component="button"
                onClick={() => navigate('/app/archivos')}
                sx={{
                  border: `1px solid ${borderColor}`, bgcolor: 'transparent',
                  px: 2, py: 0.9, borderRadius: '8px', cursor: 'pointer',
                  fontFamily: 'inherit', fontSize: '0.875rem', fontWeight: 600,
                  color: '#586AD0', mb: 3,
                  '&:hover': { borderColor: '#586AD0' },
                }}
              >
                Ir a Archivos
              </Box>
            </>
          )}
        </Box>
      )}

    </Box>
  );
}
