import { useState } from 'react';
import { Box, Tabs, Tab, useTheme } from '@mui/material';
import { useSearchParams } from 'react-router-dom';
import PageHeader from '../components/PageHeader';
import IntegrationsPage from './IntegrationsPage';
import MiContextoPage from './MiContextoPage';
import ContextoPage from './ContextoPage';
import DocumentosTab from './DocumentosTab';

const TABS = [
  { value: 'integraciones', label: 'Conexiones' },
  { value: 'mi-contexto',   label: 'Mi Contexto' },
  { value: 'cubiculos',     label: 'Cubículos' },
  { value: 'documentos',    label: 'Carpetas' },
];

export default function ContextoHubPage() {
  const theme = useTheme();
  const [searchParams, setSearchParams] = useSearchParams();
  const initial = TABS.some(t => t.value === searchParams.get('tab'))
    ? searchParams.get('tab') : 'integraciones';
  const [tab, setTab] = useState(initial);

  const handleChange = (_, value) => {
    setTab(value);
    setSearchParams({ tab: value }, { replace: true });
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100%' }}>
      <PageHeader title="Espacios" back="/app" backLabel="Chat" />

      <Box sx={{ borderBottom: `1px solid ${theme.palette.divider}`, px: { xs: 2, sm: 3 } }}>
        <Tabs
          value={tab} onChange={handleChange}
          sx={{ minHeight: 40, '& .MuiTab-root': { minHeight: 40, textTransform: 'none', fontSize: '0.82rem' } }}
        >
          {TABS.map(t => <Tab key={t.value} value={t.value} label={t.label} />)}
        </Tabs>
      </Box>

      {tab === 'integraciones' && <IntegrationsPage hideHeader />}
      {tab === 'mi-contexto' && <MiContextoPage hideHeader />}
      {tab === 'cubiculos' && <ContextoPage hideHeader />}
      {tab === 'documentos' && (
        <Box sx={{ pt: 2.5, pb: 5, px: { xs: 2, sm: 3 }, maxWidth: 860, width: '100%' }}>
          <DocumentosTab />
        </Box>
      )}
    </Box>
  );
}
