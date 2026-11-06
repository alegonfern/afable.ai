import { createContext, useContext } from 'react';

// El estado del panel de la derecha (chat y configuración del módulo). Ver PanelLateral.jsx.
export const PanelContext = createContext(null);
export const usePanelLateral = () => useContext(PanelContext);
