import { useState, useEffect, useCallback } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import BurbujaSoporte from '../../components/BurbujaSoporte';
import { Box, useMediaQuery, useTheme } from '@mui/material';
import Header from './Header';
import Drawer from './Drawer';
import { PanelLateral, PanelLateralProvider, SoloSinPanel } from './PanelLateral';
import ProgresoFlotante from '../../components/ProgresoFlotante';
import { ULTIMA_RUTA } from '../../pages/ajustes/AjustesPage';

export default function DashboardLayout() {
  const theme = useTheme();
  const matchDownLG = useMediaQuery(theme.breakpoints.down('lg'));
  const [drawerOpen, setDrawerOpen] = useState(true);
  const [focusMode, setFocusMode] = useState(false);

  useEffect(() => {
    setDrawerOpen(!matchDownLG);
  }, [matchDownLG]);

  // Configuración es una pantalla propia (28-10-2026, como en Linear): sin la barra lateral ni la
  // superior. Se recuerda la última pantalla de trabajo para su "Volver a Afable".
  const { pathname, search } = useLocation();
  const enAjustes = pathname.startsWith('/app/ajustes');
  useEffect(() => {
    if (enAjustes) return;
    try { sessionStorage.setItem(ULTIMA_RUTA, pathname + search); } catch { /* sin almacenamiento */ }
  }, [enAjustes, pathname, search]);

  const handleDrawerToggle = () => setDrawerOpen((p) => !p);
  const toggleFocusMode = useCallback(() => setFocusMode((f) => !f), []);

  // Escape exits focus mode
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape' && focusMode) setFocusMode(false); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [focusMode]);

  if (enAjustes) {
    return (
      <PanelLateralProvider>
        <Box component="div" sx={{ height: '100vh', '@supports (height: 100dvh)': { height: '100dvh' }, bgcolor: 'background.default' }}>
          <Outlet context={{ focusMode: false, toggleFocusMode }} />
        </Box>
      </PanelLateralProvider>
    );
  }

  return (
    <PanelLateralProvider>
    <Box sx={{ display: 'flex', width: '100%', minHeight: '100vh', bgcolor: 'background.default' }}>
      {!focusMode && <Header open={drawerOpen} handleDrawerToggle={handleDrawerToggle} />}
      {!focusMode && <Drawer open={drawerOpen} handleDrawerToggle={handleDrawerToggle} />}

      <Box
        component="main"
        sx={{
          flexGrow: 1,
          width: '100%',
          // minWidth 0: sin esto, contenido ancho (una tabla) estira la app más allá de la
          // ventana en vez de hacer su propio scroll horizontal.
          minWidth: 0,
          // Alto definido, no solo mínimo: con `minHeight` el contenedor crece
          // con su contenido y los hijos flex nunca reciben un alto contra el
          // cual encogerse.
          height: '100vh',
          minHeight: '100vh',
          // En el teléfono, el alto visible de verdad: con 100vh la barra del navegador
          // tapa el borde de abajo (y con él, la caja del chat).
          '@supports (height: 100dvh)': { height: '100dvh', minHeight: '100dvh' },
          bgcolor: 'background.default',
          display: 'flex',
          flexDirection: 'column',
          pt: focusMode ? 0 : '52px',
          // En el teléfono, una franja libre abajo para el botón de soporte, que si no
          // tapa la última línea de cada pantalla.
          pb: { xs: focusMode ? 0 : '58px', sm: 0 },
          transition: 'padding-top 0.2s ease',
        }}
      >
        {/* minHeight:0 — sin esto un hijo flex no puede encogerse por debajo de
            su contenido, así que una pantalla que crece (el chat cuando se
            despliega la vitrina de agentes) empuja el layout fuera del alto de
            la ventana en vez de repartirse el espacio. */}
        <Box sx={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
          <Outlet context={{ focusMode, toggleFocusMode }} />
        </Box>
      </Box>

      {/* Chat y configuración del módulo: al costado, empujando el contenido. */}
      {!focusMode && <PanelLateral />}

      {/* Los pasos de una tarea pesada fuera del chat (components/ProgresoFlotante). */}
      <ProgresoFlotante />

      {/* Escribirle a soporte desde donde sea. En modo enfoque no: ahí la pantalla se
          vacía a propósito. */}
      {!focusMode && <SoloSinPanel><BurbujaSoporte /></SoloSinPanel>}
    </Box>
    </PanelLateralProvider>
  );
}
