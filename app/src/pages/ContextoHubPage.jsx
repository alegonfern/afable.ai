import { Box } from '@mui/material';
import { useSearchParams } from 'react-router-dom';
import PageHeader from '../components/PageHeader';
import NavConocimiento from '../components/NavConocimiento';
import IntegrationsPage from './IntegrationsPage';
import MiContextoPage from './MiContextoPage';
import EspaciosTab from './espacios/EspaciosTab';

// De dónde sale lo que el agente sabe. Archivos es del mismo grupo pero vive en su propia
// pantalla (tiene árbol de carpetas y su propio `?carpeta=`), así que la barra de pestañas
// se comparte — ver `NavConocimiento`. El `?tab=` es la fuente de verdad y no un estado
// local: con estado, entrar desde otro item del menú no cambiaba de pestaña.
const TITULOS = {
  espacios: 'Espacios',
  integraciones: 'Conexiones',
  'mi-contexto': 'Contexto de la empresa',
};

export default function ContextoHubPage() {
  const [searchParams] = useSearchParams();

  const pedida = searchParams.get('tab');
  const tab = TITULOS[pedida] ? pedida : 'espacios';

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100%' }}>
      {/* El título sigue a la pestaña: decía "Espacios" incluso estando en Conexiones. */}
      <PageHeader title={TITULOS[tab]} back="/app" backLabel="Inicio" />

      <NavConocimiento activa={tab} />

      {tab === 'espacios' && <EspaciosTab />}
      {tab === 'integraciones' && <IntegrationsPage hideHeader />}
      {tab === 'mi-contexto' && <MiContextoPage hideHeader />}
    </Box>
  );
}
