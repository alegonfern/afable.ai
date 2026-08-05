import { Box, Tabs, Tab, useTheme } from '@mui/material';
import { useSearchParams } from 'react-router-dom';
import PageHeader from '../components/PageHeader';
import IntegrationsPage from './IntegrationsPage';
import MiContextoPage from './MiContextoPage';
import DocumentosTab from './DocumentosTab';
import EspaciosTab from './espacios/EspaciosTab';

// De donde sale lo que el agente sabe. Cada pestaña es también un item del menú
// (modo Espacios), así que el `?tab=` es la fuente de verdad y no un estado local.
const TABS = [
  { value: 'espacios',      label: 'Espacios',              titulo: 'Espacios' },
  { value: 'integraciones', label: 'Conexiones',            titulo: 'Conexiones' },
  { value: 'documentos',    label: 'Documentos',            titulo: 'Documentos' },
  { value: 'mi-contexto',   label: 'Contexto de la empresa', titulo: 'Contexto de la empresa' },
];

export default function ContextoHubPage() {
  const theme = useTheme();
  const [searchParams, setSearchParams] = useSearchParams();

  // Derivado de la URL, no un `useState(inicial)`. Con estado local, entrar desde
  // otro item del menú (mismo pathname, otro ?tab=) no remontaba el componente y la
  // pestaña se quedaba en la anterior.
  const pedida = searchParams.get('tab');
  const tab = TABS.some((t) => t.value === pedida) ? pedida : 'espacios';
  const actual = TABS.find((t) => t.value === tab);

  const handleChange = (_, value) => setSearchParams({ tab: value }, { replace: true });

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100%' }}>
      {/* El título sigue a la pestaña: decía "Espacios" incluso estando en Conexiones. */}
      <PageHeader title={actual.titulo} back="/app" backLabel="Chat" />

      <Box sx={{ borderBottom: `1px solid ${theme.palette.divider}`, px: { xs: 2, sm: 3 } }}>
        <Tabs
          value={tab} onChange={handleChange} variant="scrollable" scrollButtons="auto"
          sx={{ minHeight: 40, '& .MuiTab-root': { minHeight: 40, textTransform: 'none', fontSize: '0.82rem' } }}
        >
          {TABS.map(t => <Tab key={t.value} value={t.value} label={t.label} />)}
        </Tabs>
      </Box>

      {tab === 'espacios' && <EspaciosTab />}
      {tab === 'integraciones' && <IntegrationsPage hideHeader />}
      {tab === 'mi-contexto' && <MiContextoPage hideHeader />}
      {tab === 'documentos' && (
        <Box sx={{ pt: 2.5, pb: 5, px: { xs: 2, sm: 3 }, maxWidth: 860, width: '100%' }}>
          <DocumentosTab />
        </Box>
      )}
    </Box>
  );
}
