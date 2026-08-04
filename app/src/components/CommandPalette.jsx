import { useState, useEffect, useRef, useCallback } from 'react';
import { Box, Typography, InputBase, useTheme } from '@mui/material';
import {
  MessageSquare, Bot, LayoutDashboard, Plug, Plus, Search,
  Settings, HelpCircle, Building2, User, FileText, Users,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const COMMANDS = [
  { group: 'Navegación', icon: MessageSquare,  label: 'Chat',             shortcut: 'G C', action: '/app' },
  { group: 'Navegación', icon: LayoutDashboard, label: 'Tablero',         shortcut: 'G T', action: '/app/tablero' },
  { group: 'Navegación', icon: Bot,            label: 'Agentes',          shortcut: 'G A', action: '/app/agentes' },
  { group: 'Navegación', icon: Plug,           label: 'Conexiones',    shortcut: 'G I', action: '/app/integraciones' },
  { group: 'Navegación', icon: FileText,       label: 'Documentos',                        action: '/app/documentos' },
  { group: 'Navegación', icon: Building2,      label: 'Workspace',                         action: '/app/admin/workspace' },
  { group: 'Navegación', icon: User,           label: 'Mi Perfil',                         action: '/app/perfil' },
  { group: 'Navegación', icon: Users,          label: 'Equipo',                             action: '/app/equipo' },
  { group: 'Navegación', icon: Settings,       label: 'Configuración',                     action: '/app/configuracion' },
  { group: 'Navegación', icon: HelpCircle,     label: 'Ayuda',                             action: '/app/ayuda' },
  { group: 'Acciones',   icon: Plus,           label: 'Nueva conversación',                action: 'new-chat' },
  { group: 'Acciones',   icon: Bot,            label: 'Crear agente',                      action: '/app/agentes/nuevo' },
];

export default function CommandPalette({ open, onClose }) {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState(0);
  const inputRef = useRef(null);
  const navigate = useNavigate();

  const textMuted = d ? 'rgba(255,255,255,0.35)' : 'rgba(0,0,0,0.35)';
  const textSemi = d ? 'rgba(255,255,255,0.65)' : 'rgba(0,0,0,0.65)';
  const textMain = theme.palette.text.primary;
  const bgPalette = d ? '#1a1a1a' : '#ffffff';
  const bgHover = d ? 'rgba(88, 106, 208,0.15)' : 'rgba(88, 106, 208,0.08)';
  const borderPalette = d ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)';
  const borderActive = '#586AD0';
  const bgGroup = d ? 'rgba(255,255,255,0.25)' : 'rgba(0,0,0,0.25)';
  const bgInput = d ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.05)';

  useEffect(() => {
    if (open) {
      setQuery('');
      setSelected(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  const filtered = COMMANDS.filter(c =>
    c.label.toLowerCase().includes(query.toLowerCase())
  );

  const execute = useCallback((cmd) => {
    onClose();
    if (cmd.action.startsWith('/')) {
      navigate(cmd.action);
    } else {
      window.dispatchEvent(new CustomEvent('afable-cmd', { detail: cmd.action }));
    }
  }, [navigate, onClose]);

  const handleKeyDown = (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setSelected(s => Math.min(s + 1, filtered.length - 1)); }
    if (e.key === 'ArrowUp')   { e.preventDefault(); setSelected(s => Math.max(s - 1, 0)); }
    if (e.key === 'Enter' && filtered[selected]) execute(filtered[selected]);
    if (e.key === 'Escape') onClose();
  };

  if (!open) return null;

  const groups = [...new Set(filtered.map(c => c.group))];

  return (
    <Box
      onClick={onClose}
      sx={{
        position: 'fixed', inset: 0, zIndex: 2000,
        bgcolor: d ? 'rgba(0,0,0,0.55)' : 'rgba(0,0,0,0.35)',
        backdropFilter: 'blur(4px)',
        display: 'flex', alignItems: 'flex-start', justifyContent: 'center',
        pt: '15vh',
      }}
    >
      <Box
        onClick={e => e.stopPropagation()}
        sx={{
          width: 580, maxWidth: '90vw',
          bgcolor: bgPalette,
          border: `1px solid ${borderPalette}`,
          borderRadius: '12px',
          boxShadow: d ? '0 32px 80px rgba(0,0,0,0.7)' : '0 16px 48px rgba(0,0,0,0.18)',
          overflow: 'hidden',
        }}
      >
        {/* Search input */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, px: 2, py: 1.5, borderBottom: `1px solid ${borderPalette}` }}>
          <Search size={16} color={textMuted} />
          <InputBase
            inputRef={inputRef}
            fullWidth
            placeholder="Buscar comando..."
            value={query}
            onChange={e => { setQuery(e.target.value); setSelected(0); }}
            onKeyDown={handleKeyDown}
            sx={{
              fontSize: '0.9375rem', color: textMain,
              '& input::placeholder': { color: textMuted },
            }}
          />
          <Box sx={{ px: 0.75, py: 0.25, borderRadius: '4px', border: `1px solid ${borderPalette}`, bgcolor: bgInput }}>
            <Typography sx={{ fontSize: '0.6875rem', color: textMuted, lineHeight: 1.5 }}>ESC</Typography>
          </Box>
        </Box>

        {/* Results */}
        <Box sx={{ maxHeight: 400, overflowY: 'auto', py: 1 }}>
          {filtered.length === 0 && (
            <Typography sx={{ px: 3, py: 2, fontSize: '0.875rem', color: textMuted }}>
              Sin resultados para "{query}"
            </Typography>
          )}
          {groups.map(group => {
            const items = filtered.filter(c => c.group === group);
            return (
              <Box key={group}>
                <Typography sx={{ px: 3, pt: 1.25, pb: 0.5, fontSize: '0.6875rem', fontWeight: 600, color: d ? 'rgba(255,255,255,0.25)' : 'rgba(0,0,0,0.3)', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
                  {group}
                </Typography>
                {items.map((cmd) => {
                  const globalIdx = filtered.indexOf(cmd);
                  const isSelected = globalIdx === selected;
                  const Icon = cmd.icon;
                  return (
                    <Box
                      key={cmd.label}
                      onClick={() => execute(cmd)}
                      onMouseEnter={() => setSelected(globalIdx)}
                      sx={{
                        mx: 1, px: 2, py: 0.875, borderRadius: '6px',
                        display: 'flex', alignItems: 'center', gap: 1.5,
                        cursor: 'pointer',
                        bgcolor: isSelected ? bgHover : 'transparent',
                        borderLeft: isSelected ? `2px solid ${borderActive}` : '2px solid transparent',
                        transition: 'all 0.1s',
                      }}
                    >
                      <Icon size={15} color={isSelected ? '#9BA6E3' : textMuted} />
                      <Typography sx={{ flex: 1, fontSize: '0.875rem', color: isSelected ? textMain : textSemi, fontWeight: isSelected ? 500 : 400 }}>
                        {cmd.label}
                      </Typography>
                      {cmd.shortcut && (
                        <Box sx={{ display: 'flex', gap: 0.5 }}>
                          {cmd.shortcut.split(' ').map(k => (
                            <Box key={k} sx={{ px: 0.625, py: 0.125, borderRadius: '4px', border: `1px solid ${borderPalette}`, bgcolor: bgInput }}>
                              <Typography sx={{ fontSize: '0.6875rem', color: textMuted, lineHeight: 1.5 }}>{k}</Typography>
                            </Box>
                          ))}
                        </Box>
                      )}
                    </Box>
                  );
                })}
              </Box>
            );
          })}
        </Box>
      </Box>
    </Box>
  );
}
