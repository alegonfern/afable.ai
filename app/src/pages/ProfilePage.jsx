import { useState, useEffect, useRef } from 'react';
import {
  Box, Typography, Avatar, Divider, TextField, CircularProgress, useTheme,
} from '@mui/material';
import { Zap, BarChart2, Wrench, Camera } from 'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../services/api';
import PageHeader from '../components/PageHeader';

const ROLES = [
  'Gerente General', 'Gerente Financiero', 'Gerente Comercial',
  'Gerente de Operaciones', 'Jefe de TI / CTO', 'Contador / Controller',
  'Analista de Datos', 'Jefe de RRHH', 'Dueño de empresa', 'Otro',
];

const STYLES = [
  { value: 'ejecutivo', icon: <Zap size={18} />, label: 'Ejecutivo', desc: 'Bullet points, directo al grano' },
  { value: 'analitico', icon: <BarChart2 size={18} />, label: 'Analítico', desc: 'Análisis completo, cifras y tendencias' },
  { value: 'tecnico',   icon: <Wrench size={18} />,    label: 'Técnico',   desc: 'Terminología especializada' },
];

const CAMPOS_PERSONALES = [
  { key: 'about_me', label: 'Sobre mi trabajo', limit: 500,
    placeholder: 'Ej: Soy jefe de operaciones; superviso producción, compras y despachos día a día...' },
  { key: 'priorities', label: 'Mis prioridades actuales', limit: 500,
    placeholder: 'Ej: Reducir el quiebre de stock, cerrar el presupuesto de julio...' },
  { key: 'custom_instructions', label: 'Cómo quiero que me responda', limit: 500,
    placeholder: 'Ej: Directo al grano, siempre con cifras, avísame si detectas algo raro...' },
];

const SectionLabel = ({ children, muted }) => (
  <Typography sx={{ fontSize: '0.6875rem', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: '#586AD0', mb: 1.5 }}>
    {children}
  </Typography>
);

export default function ProfilePage() {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';

  const textMuted = d ? 'rgba(255,255,255,0.45)' : 'rgba(0,0,0,0.45)';
  const textSemi = d ? 'rgba(255,255,255,0.70)' : 'rgba(0,0,0,0.70)';
  const bgInput = d ? 'rgba(255,255,255,0.04)' : theme.palette.background.paper;
  const bgChip = d ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.04)';
  const bgChipActive = 'rgba(88, 106, 208,0.12)';
  const borderColor = theme.palette.divider;
  const bgCard = d ? 'rgba(255,255,255,0.04)' : theme.palette.background.paper;

  const inputSx = {
    '& .MuiOutlinedInput-root': {
      bgcolor: bgInput,
      borderRadius: '8px',
      fontSize: '0.875rem',
      color: theme.palette.text.primary,
      '& fieldset': { borderColor },
      '&:hover fieldset': { borderColor: d ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.2)' },
      '&.Mui-focused fieldset': { borderColor: '#586AD0' },
    },
    '& .MuiInputLabel-root': { color: textMuted, fontSize: '0.875rem' },
    '& .MuiInputLabel-root.Mui-focused': { color: '#9BA6E3' },
    '& .MuiInputBase-input.Mui-disabled': { color: textMuted, WebkitTextFillColor: textMuted },
  };

  const [user, setUser]             = useState(null);
  const [firstName, setFirstName]   = useState('');
  const [lastName, setLastName]     = useState('');
  const [role, setRole]             = useState('');
  const [customRole, setCustomRole] = useState('');
  const [department, setDepartment] = useState('');
  const [objectives, setObjectives] = useState('');
  const [responseStyle, setResponseStyle] = useState('ejecutivo');
  const [contexto, setContexto]     = useState({ about_me: '', priorities: '', custom_instructions: '' });
  const [saving, setSaving]         = useState(false);
  const [uploading, setUploading]   = useState(false);
  const fileRef = useRef();

  useEffect(() => {
    api.getCurrentUser().then(r => {
      const u = r.data;
      setUser(u);
      setFirstName(u.first_name || '');
      setLastName(u.last_name || '');
      setObjectives(u.objectives || '');
      setDepartment(u.department || '');
      setResponseStyle(u.response_style || 'ejecutivo');
      if (u.role) {
        if (ROLES.slice(0, -1).includes(u.role)) {
          setRole(u.role);
        } else {
          setRole('Otro');
          setCustomRole(u.role);
        }
      }
    }).catch(() => {});
    api.getUserContext()
      .then(r => setContexto({
        about_me: r.data.about_me || '',
        priorities: r.data.priorities || '',
        custom_instructions: r.data.custom_instructions || '',
      }))
      .catch(() => {});
  }, []);

  const getInitials = () => {
    if (firstName && lastName) return `${firstName[0]}${lastName[0]}`.toUpperCase();
    if (firstName) return firstName[0].toUpperCase();
    return '?';
  };

  const handleAvatarChange = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append('avatar', file);
      const res = await api.uploadAvatar(fd);
      setUser(prev => ({ ...prev, avatar_url: res.data.avatar_url }));
      toast.success('Foto actualizada');
    } catch {
      toast.error('Error al subir la imagen');
    } finally {
      setUploading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const finalRole = role === 'Otro' ? customRole : role;
      // Los dos van juntos: para quien usa la app es UNA pantalla, aunque atrás sean
      // dos modelos (User y UserContext).
      await Promise.all([
        api.updateProfile({ first_name: firstName, last_name: lastName, role: finalRole, department, objectives, response_style: responseStyle }),
        api.updateUserContext(contexto),
      ]);
      toast.success('Perfil actualizado. La IA usará tu contexto en las próximas conversaciones.');
    } catch {
      toast.error('Error al guardar el perfil');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
      <PageHeader title="Mi Perfil" backLabel="Inicio" back="/app" />

      <Box sx={{ p: { xs: 2, sm: 3 }, maxWidth: 640 }}>

        {/* ── Sección 1: Info personal ── */}
        <SectionLabel>Información personal</SectionLabel>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2.5, mb: 3 }}>
          <Box sx={{ position: 'relative', flexShrink: 0 }}>
            <Avatar
              src={user?.avatar_url}
              sx={{ width: 72, height: 72, bgcolor: '#586AD0', fontSize: '1.5rem', fontWeight: 700, border: `2px solid rgba(88, 106, 208,0.3)` }}
            >
              {!user?.avatar_url && getInitials()}
            </Avatar>
            <Box
              onClick={() => fileRef.current?.click()}
              sx={{
                position: 'absolute', bottom: 0, right: 0,
                width: 24, height: 24, borderRadius: '50%',
                bgcolor: theme.palette.background.paper,
                border: `1.5px solid ${borderColor}`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                cursor: 'pointer',
                '&:hover': { bgcolor: theme.palette.action.hover },
              }}
            >
              {uploading
                ? <CircularProgress size={12} sx={{ color: '#9BA6E3' }} />
                : <Camera size={12} color={textMuted} />}
            </Box>
            <input ref={fileRef} type="file" accept="image/*" style={{ display: 'none' }} onChange={handleAvatarChange} />
          </Box>
          <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 1.5 }}>
            <Box sx={{ display: 'flex', gap: 1.5 }}>
              <TextField label="Nombre"   value={firstName} onChange={e => setFirstName(e.target.value)} size="small" fullWidth sx={inputSx} />
              <TextField label="Apellido" value={lastName}  onChange={e => setLastName(e.target.value)}  size="small" fullWidth sx={inputSx} />
            </Box>
            <TextField label="Email" value={user?.email || ''} disabled size="small" fullWidth sx={inputSx} />
          </Box>
        </Box>

        <Divider sx={{ borderColor, mb: 3 }} />

        {/* ── Sección 2: Contexto profesional ── */}
        <SectionLabel>Tu contexto para la IA</SectionLabel>
        <Typography sx={{ fontSize: '0.8rem', color: textMuted, mb: 2, mt: -1 }}>
          Afable adapta sus respuestas según tu rol y objetivos
        </Typography>

        <Typography sx={{ fontSize: '0.8rem', color: textSemi, mb: 1 }}>Tu rol</Typography>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75, mb: 2 }}>
          {ROLES.map(r => (
            <Box
              key={r} onClick={() => setRole(r)}
              sx={{
                px: 1.5, py: 0.6, borderRadius: '6px', cursor: 'pointer', fontSize: '0.8rem',
                bgcolor: role === r ? bgChipActive : bgChip,
                border: `1px solid ${role === r ? '#586AD0' : borderColor}`,
                color: role === r ? '#9BA6E3' : textSemi,
                transition: 'all 0.12s',
                '&:hover': { borderColor: 'rgba(88, 106, 208,0.4)', color: theme.palette.text.primary },
              }}
            >
              {r}
            </Box>
          ))}
        </Box>

        {role === 'Otro' && (
          <TextField label="Especifica tu rol" value={customRole} onChange={e => setCustomRole(e.target.value)} size="small" fullWidth sx={{ ...inputSx, mb: 2 }} />
        )}

        <TextField
          label="Área o Departamento"
          value={department} onChange={e => setDepartment(e.target.value)}
          placeholder="Ej: Finanzas, Tecnología, Comercial..."
          size="small" fullWidth sx={{ ...inputSx, mb: 2 }}
        />

        <Box sx={{ position: 'relative' }}>
          <TextField
            label="¿Qué quieres lograr con Afable?"
            value={objectives} onChange={e => setObjectives(e.target.value.slice(0, 300))}
            placeholder="Ej: Reducir el tiempo de generación de reportes, monitorear KPIs en tiempo real..."
            multiline rows={3} fullWidth sx={{ ...inputSx, mb: 0.5 }}
          />
          <Typography sx={{ fontSize: '0.7rem', color: textMuted, textAlign: 'right', mb: 2 }}>
            {objectives.length}/300
          </Typography>
        </Box>

        <Divider sx={{ borderColor, mb: 3 }} />

        {/* ── Lo que estaba en Mi Contexto › Personal ── */}
        <SectionLabel>Tu trabajo y tus prioridades</SectionLabel>
        <Typography sx={{ fontSize: '0.8rem', color: textMuted, mb: 2, mt: -1 }}>
          Solo aplica a tus conversaciones. La IA lo combina con el contexto de la empresa
          para responderte a ti.
        </Typography>
        {CAMPOS_PERSONALES.map(c => (
          <Box key={c.key} sx={{ position: 'relative' }}>
            <TextField
              label={c.label}
              value={contexto[c.key]}
              onChange={e => setContexto({ ...contexto, [c.key]: e.target.value.slice(0, c.limit) })}
              placeholder={c.placeholder}
              multiline rows={3} fullWidth sx={{ ...inputSx, mb: 0.5 }}
            />
            <Typography sx={{ fontSize: '0.7rem', color: textMuted, textAlign: 'right', mb: 2 }}>
              {contexto[c.key].length}/{c.limit}
            </Typography>
          </Box>
        ))}

        <Divider sx={{ borderColor, mb: 3 }} />

        {/* ── Sección 3: Estilo de respuesta ── */}
        <SectionLabel>¿Cómo quieres que te responda la IA?</SectionLabel>
        <Box sx={{ display: 'flex', gap: 1.5, mb: 3, flexWrap: 'wrap' }}>
          {STYLES.map(s => (
            <Box
              key={s.value} onClick={() => setResponseStyle(s.value)}
              sx={{
                flex: '1 1 160px', p: 2, borderRadius: '8px', cursor: 'pointer',
                bgcolor: responseStyle === s.value ? bgChipActive : bgCard,
                border: `1px solid ${responseStyle === s.value ? '#586AD0' : borderColor}`,
                transition: 'all 0.12s',
                '&:hover': { borderColor: 'rgba(88, 106, 208,0.3)' },
              }}
            >
              <Box sx={{ color: responseStyle === s.value ? '#9BA6E3' : textMuted, mb: 0.75 }}>
                {s.icon}
              </Box>
              <Typography sx={{ fontSize: '0.875rem', fontWeight: 600, color: responseStyle === s.value ? theme.palette.text.primary : textSemi, mb: 0.25 }}>
                {s.label}
              </Typography>
              <Typography sx={{ fontSize: '0.75rem', color: textMuted, lineHeight: 1.4 }}>
                {s.desc}
              </Typography>
            </Box>
          ))}
        </Box>

        {/* ── Guardar ── */}
        <Box
          component="button" onClick={handleSave} disabled={saving}
          sx={{
            width: '100%', py: 1.25, borderRadius: '8px', border: 'none',
            cursor: saving ? 'default' : 'pointer',
            bgcolor: saving ? 'rgba(88, 106, 208,0.4)' : '#586AD0',
            color: '#fff', fontSize: '0.875rem', fontWeight: 600,
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 1,
            '&:hover:not(:disabled)': { bgcolor: '#2F42A6' },
            transition: 'background 0.15s',
          }}
        >
          {saving && <CircularProgress size={14} sx={{ color: '#fff' }} />}
          {saving ? 'Guardando...' : 'Guardar perfil'}
        </Box>
      </Box>
    </Box>
  );
}
