import { useState, useEffect, useCallback } from 'react';
import { Outlet } from 'react-router-dom';
import BurbujaSoporte from '../../components/BurbujaSoporte';
import { Box, useMediaQuery, useTheme } from '@mui/material';
import Header from './Header';
import Drawer from './Drawer';

export default function DashboardLayout() {
  const theme = useTheme();
  const matchDownLG = useMediaQuery(theme.breakpoints.down('lg'));
  const [drawerOpen, setDrawerOpen] = useState(true);
  const [focusMode, setFocusMode] = useState(false);

  useEffect(() => {
    setDrawerOpen(!matchDownLG);
  }, [matchDownLG]);

  const handleDrawerToggle = () => setDrawerOpen((p) => !p);
  const toggleFocusMode = useCallback(() => setFocusMode((f) => !f), []);

  // Escape exits focus mode
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape' && focusMode) setFocusMode(false); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [focusMode]);

  return (
    <Box sx={{ display: 'flex', width: '100%', minHeight: '100vh', bgcolor: 'background.default' }}>
      {!focusMode && <Header open={drawerOpen} handleDrawerToggle={handleDrawerToggle} />}
      {!focusMode && <Drawer open={drawerOpen} handleDrawerToggle={handleDrawerToggle} />}

      <Box
        component="main"
        sx={{
          flexGrow: 1,
          width: '100%',
          // Alto definido, no solo mínimo: con `minHeight` el contenedor crece
          // con su contenido y los hijos flex nunca reciben un alto contra el
          // cual encogerse.
          height: '100vh',
          minHeight: '100vh',
          bgcolor: 'background.default',
          display: 'flex',
          flexDirection: 'column',
          pt: focusMode ? 0 : '52px',
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

      {/* Escribirle a soporte desde donde sea. En modo enfoque no: ahí la pantalla se
          vacía a propósito. */}
      {!focusMode && <BurbujaSoporte />}
    </Box>
  );
}
