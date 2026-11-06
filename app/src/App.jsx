import React, { useState, useEffect } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { AppProvider } from './context/AppContext';
import { WorkspaceProvider } from './context/WorkspaceContext';
import ProtectedRoute from './components/ProtectedRoute';
import DashboardLayout from './layout/Dashboard';
import CommandPalette from './components/CommandPalette';

// Auth
import Login from './pages/Login';
import Register from './pages/Register';
import ForgotPassword from './pages/ForgotPassword';
import ResetPassword from './pages/ResetPassword';
import GoogleAuthCallback from './pages/GoogleAuthCallback';

// Publico
import LandingPage from './pages/LandingPage';
import Landing2Page from './pages/landing2/Landing2Page';
import InvitationAcceptPage from './pages/InvitationAcceptPage';
import PrivacidadPage from './pages/legal/PrivacidadPage';
import TerminosPage from './pages/legal/TerminosPage';
import SeguridadPage from './pages/legal/SeguridadPage';

// App
import ChatPage from './pages/ChatPage';
import ModelPage from './pages/ModelPage';
import IntegrationsPage from './pages/IntegrationsPage';
import BancoDePruebasPage from './pages/BancoDePruebasPage';
import TablondePage from './pages/TablondePage';
import MiContextoPage from './pages/MiContextoPage';
import ContextoPage from './pages/ContextoPage';
import ContextoHubPage from './pages/ContextoHubPage';
import EspacioDetallePage from './pages/espacios/EspacioDetallePage';
import AutomationsPage from './pages/AutomationsPage';
import HelpPage from './pages/HelpPage';

// Pantallas nuevas, que van reemplazando a las anteriores una por una.
// Personas reemplaza a TeamPage: la pertenencia y los roles ahora viven en el
// Workspace (Membership), no en los campos org_admin/areas del usuario.
import SesionPage from './pages/sesiones/SesionPage';
import ArchivosPage from './pages/archivos/ArchivosPage';
import DocumentoPage from './pages/archivos/DocumentoPage';
import TareasPage from './pages/TareasPage';
import ComercialPage from './pages/comercial/ComercialPage';
import ContabilidadPage from './pages/modulos/ContabilidadPage';
import AgentePage from './pages/modulos/AgentePage';
import FinanzasPage from './pages/modulos/FinanzasPage';
import AjustesPage from './pages/ajustes/AjustesPage';
import InventarioPage from './pages/inventario/InventarioPage';

export default function App() {
  const [cmdOpen, setCmdOpen] = useState(false);

  useEffect(() => {
    const handler = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        setCmdOpen((prev) => !prev);
      }
    };
    const openHandler = () => setCmdOpen(true);
    document.addEventListener('keydown', handler);
    window.addEventListener('afable-open-search', openHandler);
    return () => {
      document.removeEventListener('keydown', handler);
      window.removeEventListener('afable-open-search', openHandler);
    };
  }, []);

  return (
    <AppProvider>
      <WorkspaceProvider>
        <CommandPalette open={cmdOpen} onClose={() => setCmdOpen(false)} />
        <Routes>
          <Route path="/login"           element={<Login />} />
          <Route path="/register"        element={<Register />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password"  element={<ResetPassword />} />
          <Route path="/auth/google/callback" element={<GoogleAuthCallback />} />

          {/* 30-10-2026: la landing 2 (hero con marco, Leonardo, sobria) pasa a ser la principal; la
              anterior queda de respaldo en /landing-backup. /landing2 lleva a la principal. */}
          <Route path="/" element={<Landing2Page />} />
          <Route path="/landing-backup" element={<LandingPage />} />
          <Route path="/landing2" element={<Navigate to="/" replace />} />
          <Route path="/invitacion/:token" element={<InvitationAcceptPage />} />
          <Route path="/privacidad" element={<PrivacidadPage />} />
          <Route path="/terminos"   element={<TerminosPage />} />
          <Route path="/seguridad"  element={<SeguridadPage />} />

          <Route
            path="/app"
            element={
              <ProtectedRoute>
                <DashboardLayout />
              </ProtectedRoute>
            }
          >
            {/* El inicio es el chat (25-10-2026): desde ahí se opera el ERP. La home anterior,
                con la galería de agentes, queda en pages/trabajo/TrabajoHome.jsx sin ruta. */}
            <Route index                     element={<Navigate to="/app/chat" replace />} />
            <Route path="chat"               element={<ChatPage />} />
            {/* Ajustes (26-10-2026): perfil, preferencias, empresa, equipo, empresas, facturador
                electrónico y plan, en un solo lugar. Las direcciones de antes redirigen aquí. */}
            <Route path="ajustes"            element={<AjustesPage />} />
            <Route path="ajustes/:seccion"   element={<AjustesPage />} />
            <Route path="ajustes/:seccion/:empresa" element={<AjustesPage />} />
            <Route path="ajustes/:seccion/:empresa/:pestana" element={<AjustesPage />} />
            <Route path="ventas/facturacion-electronica" element={<Navigate to="/app/ajustes/facturacion-electronica" replace />} />
            {/* Los módulos, cada uno en las dos posiciones del selector de la barra:
                Módulo (trabajarlo) y Automatización (lo que Afable hace solo con él). */}
            <Route path="ventas"                          element={<ComercialPage key="ventas" modulo="ventas" />} />
            <Route path="ventas/automatizaciones"         element={<AgentePage modulo="ventas" />} />
            <Route path="ventas/:seccion"                 element={<ComercialPage key="ventas" modulo="ventas" />} />
            <Route path="ventas/:seccion/:id"             element={<ComercialPage key="ventas" modulo="ventas" />} />
            <Route path="compras"                         element={<ComercialPage key="compras" modulo="compras" />} />
            <Route path="compras/automatizaciones"        element={<AgentePage modulo="compras" />} />
            <Route path="compras/inventario"              element={<Navigate to="/app/inventario" replace />} />
            <Route path="inventario"                      element={<InventarioPage />} />
            <Route path="inventario/automatizaciones"     element={<AgentePage modulo="inventario" />} />
            <Route path="inventario/:seccion"             element={<InventarioPage />} />
            <Route path="inventario/:seccion/:id"         element={<InventarioPage />} />
            <Route path="compras/:seccion"                element={<ComercialPage key="compras" modulo="compras" />} />
            <Route path="compras/:seccion/:id"            element={<ComercialPage key="compras" modulo="compras" />} />
            {/* Contabilidad › Módulo ya trabaja: carga del SII y clasificación (PMV, etapa 1). */}
            <Route path="contabilidad"                    element={<ContabilidadPage />} />
            <Route path="contabilidad/automatizaciones"   element={<AgentePage modulo="contabilidad" />} />
            {/* Cada sección del módulo es su propia dirección: el submenú de la barra lateral
                la marca y el encabezado dice Inicio / Contabilidad / Documentos. */}
            <Route path="contabilidad/:seccion"           element={<ContabilidadPage />} />
            <Route path="finanzas"                        element={<FinanzasPage />} />
            <Route path="finanzas/automatizaciones"       element={<AgentePage modulo="finanzas" />} />
            <Route path="finanzas/:seccion"               element={<FinanzasPage />} />
            <Route path="modelo"             element={<ModelPage />} />
            {/* Los agentes antiguos (galería, constructor, fichas) se quitaron el 25-10-2026: ahora hay
                un agente detrás de cada módulo (vista "Agente"). Sus direcciones llevan al chat. */}
            <Route path="agentes/*"          element={<Navigate to="/app/chat" replace />} />
            <Route path="tablero"            element={<TablondePage />} />
            {/* Banco de pruebas: interna. El servidor decide quién entra
                (`CUENTAS_DE_PRUEBA`); acá la ruta existe para todos y quien no
                corresponde recibe el 403 explicado, no una página en blanco. */}
            <Route path="banco-de-pruebas"   element={<BancoDePruebasPage />} />
            {/* Archivos: EL lugar de los archivos de la empresa, con carpetas,
                versiones y edición. La pestaña Documentos del hub redirige acá. */}
            <Route path="archivos"           element={<ArchivosPage />} />
            <Route path="archivos/:docId"    element={<DocumentoPage />} />
            <Route path="contexto"           element={<ContextoHubPage />} />
            <Route path="espacios/:spaceSlug" element={<EspacioDetallePage />} />
            {/* Sesiones: donde trabaja el equipo. El Espacio es permisos sobre el
                conocimiento; la Sesion es la superficie de trabajo. */}
            <Route path="sesiones/:sesionSlug" element={<SesionPage />} />
            <Route path="automatizaciones"   element={<AutomationsPage />} />
            <Route path="perfil"             element={<Navigate to="/app/ajustes/perfil" replace />} />
            <Route path="configuracion"      element={<Navigate to="/app/ajustes/preferencias" replace />} />
            <Route path="ayuda"              element={<HelpPage />} />
            {/* La vitrina de precios y la pantalla de "gracias" se reemplazaron por
                Facturación, que además dice con qué se paga y qué se cobró. Las rutas
                viejas redirigen porque quedaron enlaces dando vuelta (y la pasarela
                vuelve con `?pago=`, que Facturación sabe leer). */}
            <Route path="precios"            element={<Navigate to="/app/ajustes/plan" replace />} />
            <Route path="pago/resultado"     element={<Navigate to="/app/ajustes/plan" replace />} />

            {/* Pantallas nuevas; las rutas viejas redirigen para no romper enlaces */}
            <Route path="admin/personas"     element={<Navigate to="/app/ajustes/equipo" replace />} />
            <Route path="equipo"             element={<Navigate to="/app/ajustes/equipo" replace />} />
            {/* Tareas: todo lo pendiente cruzando Sesiones. Las tareas viven dentro de
                una Sesión, pero "qué tengo pendiente" no es una pregunta sobre una Sesión. */}
            <Route path="tareas"             element={<TareasPage />} />
            <Route path="admin/workspace"    element={<Navigate to="/app/ajustes/general" replace />} />
            <Route path="admin/agentes"      element={<Navigate to="/app/chat" replace />} />
            {/* Facturación: el plan es de la empresa, así que vive en Admin y no en el
                perfil de la persona. `precios` queda como la vitrina publica. */}
            <Route path="admin/facturacion"  element={<Navigate to="/app/ajustes/plan" replace />} />
            {/* La ficha de un agente es UNA: el constructor. Admin > Agentes es la
                lista (ahi se ve de un vistazo lo que falta configurar) y abre ahi. */}
            <Route path="admin/agentes/:id"  element={<Navigate to="/app/chat" replace />} />
            <Route path="organizaciones"     element={<Navigate to="/app/ajustes/empresas" replace />} />
          </Route>

          <Route path="*" element={<Navigate to="/app" replace />} />
        </Routes>
      </WorkspaceProvider>
    </AppProvider>
  );
}
