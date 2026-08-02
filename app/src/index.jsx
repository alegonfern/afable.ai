import React, { useMemo } from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider, createTheme, CssBaseline } from '@mui/material';
import { ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import App from './App';
import { ThemeContextProvider, useThemeMode } from './context/ThemeContext';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
  },
});

// Cursor-style: near-black surfaces, ultra-subtle borders, restrained accent.
const MONO = `'JetBrains Mono', 'Fira Code', ui-monospace, SFMono-Regular, Menlo, monospace`;

export function getAfableTheme(mode) {
  const d = mode === 'dark';
  const border    = d ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.07)';
  const borderSub = d ? '#1f1f1f' : '#e6e6e6';

  return createTheme({
    palette: {
      mode,
      background: {
        default: d ? '#0e0e0e' : '#fbfbfa',
        paper:   d ? '#161616' : '#ffffff',
      },
      primary:   { main: '#586AD0', light: '#7886D9', dark: '#2F42A6', contrastText: '#fff' },
      secondary: { main: '#9BA6E3' },
      divider: borderSub,
      // Grises con mas contraste: los anteriores (#7d7d7d / #4a4a4a) obligaban a
      // forzar la vista sobre el fondo casi negro. Se mantiene la jerarquia, sube
      // el piso.
      text: {
        primary:   d ? '#f2f2f2' : '#141416',
        secondary: d ? '#b4b4b4' : '#52525b',
        disabled:  d ? '#7a7a7a' : '#8a8a8a',
      },
      action: {
        hover:    d ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.04)',
        selected: 'rgba(88, 106, 208,0.12)',
      },
      error:   { main: '#f87171' },
      success: { main: '#34D399' },
      warning: { main: '#fbbf24' },
    },
    typography: {
      fontFamily: `'Inter', 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif`,
      fontSize: 14,
      h1: { fontWeight: 600, letterSpacing: '-0.02em',  fontSize: '1.875rem' },
      h2: { fontWeight: 600, letterSpacing: '-0.015em', fontSize: '1.5rem' },
      h3: { fontWeight: 600, letterSpacing: '-0.01em',  fontSize: '1.25rem' },
      h4: { fontWeight: 600, letterSpacing: '-0.01em',  fontSize: '1.125rem' },
      h5: { fontWeight: 500, fontSize: '1rem' },
      h6: { fontWeight: 500, fontSize: '0.9375rem' },
      // Un escalón más que antes, encima de la raíz de 17px: el texto de lectura
      // queda cerca de 16px y los secundarios dejan de caer bajo los 14.
      body1:     { fontSize: '0.9375rem', lineHeight: 1.62 },
      body2:     { fontSize: '0.875rem',  lineHeight: 1.58 },
      subtitle1: { fontSize: '0.9375rem', fontWeight: 500 },
      subtitle2: { fontSize: '0.875rem',  fontWeight: 500 },
      caption:   { fontSize: '0.8125rem' },
    },
    shape: { borderRadius: 6 },
    components: {
      MuiCssBaseline: {
        styleOverrides: {
          // La escala de toda la app cuelga de acá. Prácticamente todos los
          // tamaños del proyecto están en `rem`, así que subir la raíz de los
          // 16px del navegador a 17px agranda la interfaz completa de una vez,
          // en vez de ir pantalla por pantalla.
          html: {
            fontSize: '17px',
            WebkitFontSmoothing: 'antialiased',
            MozOsxFontSmoothing: 'grayscale',
            textRendering: 'optimizeLegibility',
          },
          body: {
            backgroundColor: d ? '#0e0e0e' : '#fbfbfa',
            fontSize: '0.9375rem',
          },
          // La barra fina va en TODO lo que scrollea, no solo en la página.
          // Estaba puesta solo sobre `body`, así que cada caja con scroll propio
          // — la vitrina de agentes en el compositor, la lista de menciones, la
          // galería del home — se dibujaba con la barra gruesa del sistema. En
          // Linux esa barra además ocupa lugar y corre el contenido al aparecer.
          '*': {
            scrollbarWidth: 'thin',
            scrollbarColor: d
              ? 'rgba(255,255,255,0.12) transparent'
              : 'rgba(0,0,0,0.15) transparent',
            '&::-webkit-scrollbar': { width: '6px', height: '6px' },
            '&::-webkit-scrollbar-track': { background: 'transparent' },
            '&::-webkit-scrollbar-thumb': {
              background: 'transparent',
              borderRadius: '3px',
            },
          },
          // El pulgar aparece recién cuando el cursor está sobre la caja: la
          // barra deja de ser parte permanente del dibujo.
          '*:hover::-webkit-scrollbar-thumb, *:focus-within::-webkit-scrollbar-thumb': {
            background: d ? 'rgba(255,255,255,0.14)' : 'rgba(0,0,0,0.17)',
          },
          '*::-webkit-scrollbar-thumb:hover': {
            background: d ? 'rgba(255,255,255,0.24)' : 'rgba(0,0,0,0.28)',
          },
        },
      },
      MuiAppBar: {
        styleOverrides: {
          root: {
            backgroundColor: d ? '#0e0e0e' : '#fbfbfa',
            borderBottom: `1px solid ${borderSub}`,
            boxShadow: 'none',
          },
        },
      },
      MuiDrawer: {
        styleOverrides: {
          paper: {
            backgroundColor: d ? '#121212' : '#f7f7f6',
            borderRight: `1px solid ${borderSub}`,
          },
        },
      },
      MuiButton: {
        styleOverrides: {
          root: {
            textTransform: 'none',
            fontWeight: 500,
            letterSpacing: 0,
            fontSize: '0.82rem',
            borderRadius: 6,
            boxShadow: 'none',
            '&:hover': { boxShadow: 'none' },
          },
          containedPrimary: {
            background: '#586AD0',
            '&:hover': { background: '#2F42A6', boxShadow: 'none' },
          },
          outlinedPrimary: {
            borderColor: border,
            '&:hover': { borderColor: d ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.2)', boxShadow: 'none' },
          },
        },
      },
      MuiPaper: {
        styleOverrides: {
          root: {
            backgroundImage: 'none',
            backgroundColor: d ? '#161616' : '#ffffff',
            border: `1px solid ${border}`,
          },
        },
      },
      MuiDialog: {
        styleOverrides: {
          paper: {
            borderRadius: 12,
            backgroundImage: 'none',
          },
        },
      },
      MuiMenu: {
        styleOverrides: {
          paper: {
            backgroundColor: d ? '#1a1a1a' : '#ffffff',
            border: `1px solid ${border}`,
            boxShadow: d
              ? '0 8px 32px rgba(0,0,0,0.6)'
              : '0 4px 20px rgba(0,0,0,0.12)',
          },
        },
      },
      MuiMenuItem: {
        styleOverrides: {
          root: {
            fontSize: '0.875rem',
            borderRadius: 4,
            '&:hover': {
              backgroundColor: d ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.04)',
            },
            '&.Mui-selected': {
              backgroundColor: 'rgba(88, 106, 208,0.12)',
              '&:hover': { backgroundColor: 'rgba(88, 106, 208,0.18)' },
            },
          },
        },
      },
      MuiTextField: {
        styleOverrides: {
          root: {
            '& .MuiOutlinedInput-root': {
              fontSize: '0.875rem',
              borderRadius: 6,
              '& fieldset': {
                borderColor: d ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.15)',
              },
              '&:hover fieldset': {
                borderColor: d ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.25)',
              },
              '&.Mui-focused fieldset': { borderColor: 'rgba(88, 106, 208,0.6)' },
            },
            '& .MuiInputLabel-root': { fontSize: '0.875rem' },
          },
        },
      },
      MuiDivider: {
        styleOverrides: { root: { borderColor: borderSub } },
      },
      MuiListItemButton: {
        styleOverrides: {
          root: {
            borderRadius: 5,
            fontSize: '0.875rem',
            '&.Mui-selected': {
              backgroundColor: 'rgba(88, 106, 208,0.12)',
              '&:hover': { backgroundColor: 'rgba(88, 106, 208,0.16)' },
            },
            '&:hover': {
              backgroundColor: d ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.04)',
            },
          },
        },
      },
      MuiTooltip: {
        styleOverrides: {
          tooltip: {
            backgroundColor: d ? '#1e1e1e' : '#18181b',
            fontSize: '0.75rem',
            fontWeight: 500,
            border: d ? '1px solid rgba(255,255,255,0.06)' : 'none',
            boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
          },
          arrow: { color: d ? '#1e1e1e' : '#18181b' },
        },
      },
      MuiIconButton: {
        styleOverrides: {
          root: {
            borderRadius: 6,
            '&:hover': {
              backgroundColor: d ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.04)',
            },
          },
        },
      },
      MuiChip: {
        styleOverrides: {
          root: {
            fontSize: '0.72rem',
            fontWeight: 500,
            borderRadius: 5,
            fontFamily: MONO,
            letterSpacing: '-0.01em',
          },
        },
      },
    },
  });
}

function ThemeWrapper({ children }) {
  const { mode } = useThemeMode();
  const theme = useMemo(() => getAfableTheme(mode), [mode]);
  const isDark = mode === 'dark';
  const toastBg = isDark ? '#252525' : '#ffffff';
  const toastColor = isDark ? 'rgba(255,255,255,0.87)' : 'rgba(0,0,0,0.87)';
  const toastBorder = isDark ? '1px solid rgba(255,255,255,0.1)' : '1px solid rgba(0,0,0,0.1)';

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      {children}
      <ToastContainer
        position="top-right"
        autoClose={3500}
        theme={isDark ? 'dark' : 'light'}
        toastStyle={{
          background: toastBg,
          border: toastBorder,
          color: toastColor,
          fontSize: '0.875rem',
          boxShadow: '0 8px 24px rgba(0,0,0,0.15)',
        }}
      />
    </ThemeProvider>
  );
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <ThemeContextProvider>
      <BrowserRouter>
        <QueryClientProvider client={queryClient}>
          <ThemeWrapper>
            <App />
          </ThemeWrapper>
        </QueryClientProvider>
      </BrowserRouter>
    </ThemeContextProvider>
  </React.StrictMode>
);
