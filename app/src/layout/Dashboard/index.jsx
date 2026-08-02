import { useState, useEffect, useCallback } from 'react';
import { Outlet } from 'react-router-dom';
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
          minHeight: '100vh',
          bgcolor: 'background.default',
          display: 'flex',
          flexDirection: 'column',
          pt: focusMode ? 0 : '52px',
          transition: 'padding-top 0.2s ease',
        }}
      >
        <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          <Outlet context={{ focusMode, toggleFocusMode }} />
        </Box>
      </Box>
    </Box>
  );
}
