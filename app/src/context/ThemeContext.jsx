import React, { createContext, useContext, useState, useEffect } from 'react';

const ThemeCtx = createContext({ mode: 'light', toggleMode: () => {} });

export function ThemeContextProvider({ children }) {
  const [mode, setMode] = useState(
    () => localStorage.getItem('afable_theme') || 'dark'
  );

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', mode);
    localStorage.setItem('afable_theme', mode);
  }, [mode]);

  const toggleMode = () => setMode((m) => (m === 'light' ? 'dark' : 'light'));

  return (
    <ThemeCtx.Provider value={{ mode, toggleMode }}>
      {children}
    </ThemeCtx.Provider>
  );
}

export const useThemeMode = () => useContext(ThemeCtx);
