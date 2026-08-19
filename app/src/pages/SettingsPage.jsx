import { useState } from 'react';
import {
  Box, Typography, Divider, TextField, CircularProgress, Switch, useTheme,
} from '@mui/material';
import { Sun, Moon, Lock, Eye, EyeOff } from 'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../services/api';
import { useThemeMode } from '../context/ThemeContext';
import PageHeader from '../components/PageHeader';

const Section = ({ title, children }) => (
  <Box sx={{ mb: 4 }}>
    <Typography sx={{ fontSize: '0.6875rem', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: '#586AD0', mb: 2 }}>
      {title}
    </Typography>
    {children}
  </Box>
);

export default function SettingsPage() {
  const theme = useTheme();
  const { mode, toggleMode } = useThemeMode();
  const d = mode === 'dark';

  const [currentPwd, setCurrentPwd] = useState('');
  const [newPwd, setNewPwd] = useState('');
  const [confirmPwd, setConfirmPwd] = useState('');
  const [showCurrent, setShowCurrent] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [saving, setSaving] = useState(false);

  const textMuted = d ? 'rgba(255,255,255,0.45)' : 'rgba(0,0,0,0.45)';
  const textSemi = d ? 'rgba(255,255,255,0.70)' : 'rgba(0,0,0,0.70)';
  const bgCard = d ? 'rgba(255,255,255,0.04)' : '#ffffff';
  const borderColor = theme.palette.divider;
  const bgHover = theme.palette.action.hover;

  const inputSx = {
    '& .MuiOutlinedInput-root': {
      bgcolor: d ? 'rgba(255,255,255,0.04)' : theme.palette.background.paper,
      borderRadius: '8px',
      fontSize: '0.875rem',
      '& fieldset': { borderColor },
      '&:hover fieldset': { borderColor: d ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.2)' },
      '&.Mui-focused fieldset': { borderColor: '#586AD0' },
    },
    '& .MuiInputLabel-root': { color: textMuted, fontSize: '0.875rem' },
    '& .MuiInputLabel-root.Mui-focused': { color: '#9BA6E3' },
    '& .MuiInputBase-input': { color: theme.palette.text.primary },
  };

  const handleChangePassword = async () => {
    if (!currentPwd || !newPwd || !confirmPwd) {
      toast.error('Completa todos los campos');
      return;
    }
    if (newPwd !== confirmPwd) {
      toast.error('Las contraseñas no coinciden');
      return;
    }
    if (newPwd.length < 8) {
      toast.error('La nueva contraseña debe tener al menos 8 caracteres');
      return;
    }
    setSaving(true);
    try {
      await api.changePassword({ current_password: currentPwd, new_password: newPwd });
      toast.success('Contraseña actualizada');
      setCurrentPwd(''); setNewPwd(''); setConfirmPwd('');
    } catch (err) {
      const detail = err?.response?.data?.current_password?.[0] || err?.response?.data?.detail || 'Error al cambiar contraseña';
      toast.error(detail);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
      <PageHeader title="Configuración" backLabel="Inicio" back="/app" />

      <Box sx={{ p: { xs: 2, sm: 3 }, maxWidth: 560, width: '100%', mx: 'auto' }}>

        {/* ── Apariencia ── */}
        <Section title="Apariencia">
          <Box sx={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            p: 2, borderRadius: '8px', bgcolor: bgCard, border: `1px solid ${borderColor}`,
          }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
              <Box sx={{ color: textSemi, display: 'flex' }}>
                {d ? <Moon size={18} /> : <Sun size={18} />}
              </Box>
              <Box>
                <Typography sx={{ fontSize: '0.875rem', fontWeight: 500, color: theme.palette.text.primary }}>
                  Modo {d ? 'oscuro' : 'claro'}
                </Typography>
                <Typography sx={{ fontSize: '0.78rem', color: textMuted }}>
                  Cambia el tema visual de la app
                </Typography>
              </Box>
            </Box>
            <Switch
              checked={d}
              onChange={toggleMode}
              sx={{
                '& .MuiSwitch-switchBase.Mui-checked': { color: '#586AD0' },
                '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': { bgcolor: '#586AD0' },
              }}
            />
          </Box>
        </Section>

        <Divider sx={{ borderColor, mb: 4 }} />

        {/* ── Seguridad ── */}
        <Section title="Seguridad">
          <Box sx={{ p: 2.5, borderRadius: '8px', bgcolor: bgCard, border: `1px solid ${borderColor}`, display: 'flex', flexDirection: 'column', gap: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25, mb: 0.5 }}>
              <Lock size={16} color={textMuted} />
              <Typography sx={{ fontSize: '0.875rem', fontWeight: 500, color: theme.palette.text.primary }}>
                Cambiar contraseña
              </Typography>
            </Box>

            <TextField
              label="Contraseña actual"
              type={showCurrent ? 'text' : 'password'}
              value={currentPwd}
              onChange={e => setCurrentPwd(e.target.value)}
              size="small"
              fullWidth
              sx={inputSx}
              InputProps={{
                endAdornment: (
                  <Box
                    component="button" type="button"
                    onClick={() => setShowCurrent(p => !p)}
                    sx={{ border: 'none', bgcolor: 'transparent', cursor: 'pointer', color: textMuted, display: 'flex', p: 0.5, '&:hover': { color: theme.palette.text.primary } }}
                  >
                    {showCurrent ? <EyeOff size={15} /> : <Eye size={15} />}
                  </Box>
                ),
              }}
            />

            <TextField
              label="Nueva contraseña"
              type={showNew ? 'text' : 'password'}
              value={newPwd}
              onChange={e => setNewPwd(e.target.value)}
              size="small"
              fullWidth
              sx={inputSx}
              InputProps={{
                endAdornment: (
                  <Box
                    component="button" type="button"
                    onClick={() => setShowNew(p => !p)}
                    sx={{ border: 'none', bgcolor: 'transparent', cursor: 'pointer', color: textMuted, display: 'flex', p: 0.5, '&:hover': { color: theme.palette.text.primary } }}
                  >
                    {showNew ? <EyeOff size={15} /> : <Eye size={15} />}
                  </Box>
                ),
              }}
            />

            <TextField
              label="Confirmar nueva contraseña"
              type="password"
              value={confirmPwd}
              onChange={e => setConfirmPwd(e.target.value)}
              size="small"
              fullWidth
              sx={inputSx}
              error={!!confirmPwd && newPwd !== confirmPwd}
              helperText={!!confirmPwd && newPwd !== confirmPwd ? 'Las contraseñas no coinciden' : ''}
            />

            <Box
              component="button"
              onClick={handleChangePassword}
              disabled={saving || !currentPwd || !newPwd || !confirmPwd}
              sx={{
                alignSelf: 'flex-start', display: 'flex', alignItems: 'center', gap: 1,
                px: 2, py: 0.875, borderRadius: '6px', border: 'none',
                bgcolor: saving ? 'rgba(88, 106, 208,0.45)' : '#586AD0',
                color: '#fff', fontSize: '0.875rem', fontWeight: 600,
                cursor: saving ? 'default' : 'pointer',
                '&:hover:not(:disabled)': { bgcolor: '#2F42A6' },
                '&:disabled': { bgcolor: bgHover, color: textMuted, cursor: 'default' },
                transition: 'background 0.15s',
              }}
            >
              {saving && <CircularProgress size={13} sx={{ color: '#fff' }} />}
              {saving ? 'Guardando...' : 'Actualizar contraseña'}
            </Box>
          </Box>
        </Section>

      </Box>
    </Box>
  );
}
