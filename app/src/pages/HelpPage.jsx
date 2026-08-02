import { useState } from 'react';
import { Box, Typography, Accordion, AccordionSummary, AccordionDetails, Divider, useTheme } from '@mui/material';
import { ChevronDown, Keyboard, MessageSquare, Bot, LayoutDashboard, FileText, Search, Maximize2, X } from 'lucide-react';
import PageHeader from '../components/PageHeader';

const SHORTCUTS = [
  { keys: ['⌘', 'K'], desc: 'Abrir búsqueda / paleta de comandos' },
  { keys: ['Esc'], desc: 'Salir del modo enfoque (Chat)' },
  { keys: ['↑', '↓'], desc: 'Navegar en la paleta de comandos' },
  { keys: ['Enter'], desc: 'Ejecutar comando seleccionado' },
];

const NAV_SHORTCUTS = [
  { keys: ['G', 'C'], desc: 'Ir a Chat', icon: <MessageSquare size={13} /> },
  { keys: ['G', 'T'], desc: 'Ir a Tablero', icon: <LayoutDashboard size={13} /> },
  { keys: ['G', 'A'], desc: 'Ir a Agentes', icon: <Bot size={13} /> },
  { keys: ['G', 'I'], desc: 'Ir a Conexiones', icon: <FileText size={13} /> },
];

const CHAT_SHORTCUTS = [
  { icon: <Search size={13} />, desc: 'Barra de búsqueda', detail: 'Clic en la barra central del header o ⌘K para buscar páginas y ejecutar acciones.' },
  { icon: <Maximize2 size={13} />, desc: 'Modo enfoque', detail: 'El botón "Modo enfoque" del Chat oculta header y sidebar. Escapa para volver.' },
  { icon: <X size={13} />, desc: 'Minimizar ventanas', detail: 'Las ventanas del chat se pueden minimizar (—) y cerrar (×) independientemente.' },
];

const FAQ = [
  {
    q: '¿Cómo conecto Afable con mi ERP (Odoo)?',
    a: 'Ve a Workspace para los datos de la empresa, y a Espacios › Conexiones para conectar Odoo: ahí están los campos de URL, base de datos y credenciales.',
  },
  {
    q: '¿Mis conversaciones se guardan?',
    a: 'Sí. Cada ventana de chat tiene su propia conversación que se persiste en el servidor. Puedes acceder al historial en cualquier momento.',
  },
  {
    q: '¿Cómo cambio el modelo de IA?',
    a: 'En el header del backoffice hay un selector de modelo (muestra el modelo activo con un ícono de chispa). Haz clic para elegir entre Claude, GPT o modelos locales.',
  },
  {
    q: '¿Puedo crear agentes personalizados?',
    a: 'Sí. Ve a Agentes y usa el botón "Nuevo agente". Puedes definir nombre, descripción, instrucciones y modelo base para cada agente.',
  },
  {
    q: '¿Cómo subo documentos para que la IA los use?',
    a: 'Ve a Documentos. Puedes crear y editar documentos Markdown directamente en el canvas. La IA puede referenciarlos en sus respuestas.',
  },
];

export default function HelpPage() {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const [expanded, setExpanded] = useState(false);

  const textMuted = d ? 'rgba(255,255,255,0.45)' : 'rgba(0,0,0,0.45)';
  const bgCard = d ? 'rgba(255,255,255,0.04)' : '#ffffff';
  const borderColor = theme.palette.divider;
  const bgHover = theme.palette.action.hover;

  const KeyBadge = ({ k }) => (
    <Box sx={{
      px: 0.75, py: 0.2, borderRadius: '4px', minWidth: 22,
      border: `1px solid ${borderColor}`,
      bgcolor: bgHover,
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
    }}>
      <Typography sx={{ fontSize: '0.75rem', fontFamily: 'monospace', color: textMuted, lineHeight: 1.6 }}>
        {k}
      </Typography>
    </Box>
  );

  const Section = ({ title, icon, children }) => (
    <Box sx={{ mb: 4 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
        <Box sx={{ color: '#586AD0' }}>{icon}</Box>
        <Typography sx={{ fontSize: '0.6875rem', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: '#586AD0' }}>
          {title}
        </Typography>
      </Box>
      {children}
    </Box>
  );

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
      <PageHeader title="Ayuda" backLabel="Inicio" back="/app" />

      <Box sx={{ p: { xs: 2, sm: 3 }, maxWidth: 680 }}>

        {/* ── Atajos de teclado ── */}
        <Section title="Atajos de teclado" icon={<Keyboard size={14} />}>
          <Box sx={{ p: 2, borderRadius: '8px', bgcolor: bgCard, border: `1px solid ${borderColor}`, display: 'flex', flexDirection: 'column', gap: 0 }}>
            {SHORTCUTS.map((s, i) => (
              <Box key={i}>
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', py: 1.25, px: 0.5 }}>
                  <Typography sx={{ fontSize: '0.875rem', color: theme.palette.text.secondary }}>
                    {s.desc}
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 0.5, alignItems: 'center' }}>
                    {s.keys.map(k => <KeyBadge key={k} k={k} />)}
                  </Box>
                </Box>
                {i < SHORTCUTS.length - 1 && <Divider sx={{ borderColor }} />}
              </Box>
            ))}
          </Box>

          <Typography sx={{ fontSize: '0.75rem', color: textMuted, mt: 1.5, mb: 1 }}>
            Navegación rápida (desde la paleta ⌘K)
          </Typography>
          <Box sx={{ p: 2, borderRadius: '8px', bgcolor: bgCard, border: `1px solid ${borderColor}`, display: 'flex', flexDirection: 'column', gap: 0 }}>
            {NAV_SHORTCUTS.map((s, i) => (
              <Box key={i}>
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', py: 1.25, px: 0.5 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, color: theme.palette.text.secondary }}>
                    <Box sx={{ color: textMuted }}>{s.icon}</Box>
                    <Typography sx={{ fontSize: '0.875rem' }}>{s.desc}</Typography>
                  </Box>
                  <Box sx={{ display: 'flex', gap: 0.5 }}>
                    {s.keys.map(k => <KeyBadge key={k} k={k} />)}
                  </Box>
                </Box>
                {i < NAV_SHORTCUTS.length - 1 && <Divider sx={{ borderColor }} />}
              </Box>
            ))}
          </Box>
        </Section>

        <Divider sx={{ borderColor, mb: 4 }} />

        {/* ── Consejos rápidos ── */}
        <Section title="Consejos rápidos" icon={<Bot size={14} />}>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.25 }}>
            {CHAT_SHORTCUTS.map((c, i) => (
              <Box key={i} sx={{ display: 'flex', gap: 1.5, p: 1.75, borderRadius: '8px', bgcolor: bgCard, border: `1px solid ${borderColor}` }}>
                <Box sx={{ color: '#586AD0', mt: 0.25, flexShrink: 0 }}>{c.icon}</Box>
                <Box>
                  <Typography sx={{ fontSize: '0.875rem', fontWeight: 500, color: theme.palette.text.primary, mb: 0.25 }}>
                    {c.desc}
                  </Typography>
                  <Typography sx={{ fontSize: '0.8125rem', color: textMuted, lineHeight: 1.5 }}>
                    {c.detail}
                  </Typography>
                </Box>
              </Box>
            ))}
          </Box>
        </Section>

        <Divider sx={{ borderColor, mb: 4 }} />

        {/* ── FAQ ── */}
        <Section title="Preguntas frecuentes" icon={<MessageSquare size={14} />}>
          <Box sx={{ borderRadius: '8px', overflow: 'hidden', border: `1px solid ${borderColor}` }}>
            {FAQ.map((item, i) => (
              <Accordion
                key={i}
                expanded={expanded === i}
                onChange={() => setExpanded(expanded === i ? false : i)}
                disableGutters
                elevation={0}
                sx={{
                  bgcolor: bgCard,
                  borderBottom: i < FAQ.length - 1 ? `1px solid ${borderColor}` : 'none',
                  '&:before': { display: 'none' },
                }}
              >
                <AccordionSummary
                  expandIcon={<ChevronDown size={16} color={textMuted} />}
                  sx={{
                    px: 2.5, py: 0.5, minHeight: 52,
                    '& .MuiAccordionSummary-content': { my: 1.25 },
                    '&:hover': { bgcolor: bgHover },
                  }}
                >
                  <Typography sx={{ fontSize: '0.875rem', fontWeight: 500, color: theme.palette.text.primary }}>
                    {item.q}
                  </Typography>
                </AccordionSummary>
                <AccordionDetails sx={{ px: 2.5, pb: 2, pt: 0 }}>
                  <Typography sx={{ fontSize: '0.875rem', color: textMuted, lineHeight: 1.6 }}>
                    {item.a}
                  </Typography>
                </AccordionDetails>
              </Accordion>
            ))}
          </Box>
        </Section>

        {/* ── Footer info ── */}
        <Box sx={{ mt: 2, p: 2, borderRadius: '8px', bgcolor: bgHover, border: `1px solid ${borderColor}`, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography sx={{ fontSize: '0.8rem', color: textMuted }}>
            Afable v0.1 — Plataforma de IA empresarial
          </Typography>
          <Typography sx={{ fontSize: '0.8rem', color: '#586AD0', fontWeight: 500 }}>
            beta
          </Typography>
        </Box>
      </Box>
    </Box>
  );
}
