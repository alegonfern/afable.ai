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
import ProfilePage from './pages/ProfilePage';
import MiContextoPage from './pages/MiContextoPage';
import ContextoPage from './pages/ContextoPage';
import ContextoHubPage from './pages/ContextoHubPage';
import EspacioDetallePage from './pages/espacios/EspacioDetallePage';
import AutomationsPage from './pages/AutomationsPage';
import SettingsPage from './pages/SettingsPage';
import HelpPage from './pages/HelpPage';

// Pantallas nuevas, que van reemplazando a las anteriores una por una.
// Personas reemplaza a TeamPage: la pertenencia y los roles ahora viven en el
// Workspace (Membership), no en los campos org_admin/areas del usuario.
import TrabajoHome from './pages/trabajo/TrabajoHome';
import AgentesPage from './pages/trabajo/AgentesPage';
import AgenteNuevoPage from './pages/trabajo/AgenteNuevoPage';
import SesionPage from './pages/sesiones/SesionPage';
import ArchivosPage from './pages/archivos/ArchivosPage';
import DocumentoPage from './pages/archivos/DocumentoPage';
import PersonasPage from './pages/admin/PersonasPage';
import WorkspacePage from './pages/admin/WorkspacePage';
import TareasPage from './pages/TareasPage';
import AgentesAdminPage from './pages/admin/AgentesAdminPage';
import FacturacionPage from './pages/admin/FacturacionPage';

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

          <Route path="/" element={<LandingPage />} />
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
            <Route index                     element={<TrabajoHome />} />
            <Route path="chat"               element={<ChatPage />} />
            <Route path="modelo"             element={<ModelPage />} />
            <Route path="agentes"            element={<AgentesPage />} />
            {/* El constructor: la misma pantalla crea y edita. */}
            <Route path="agentes/nuevo"      element={<AgenteNuevoPage />} />
            <Route path="agentes/:id/editar" element={<AgenteNuevoPage />} />
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
            <Route path="perfil"             element={<ProfilePage />} />
            <Route path="configuracion"      element={<SettingsPage />} />
            <Route path="ayuda"              element={<HelpPage />} />
            {/* La vitrina de precios y la pantalla de "gracias" se reemplazaron por
                Facturación, que además dice con qué se paga y qué se cobró. Las rutas
                viejas redirigen porque quedaron enlaces dando vuelta (y la pasarela
                vuelve con `?pago=`, que Facturación sabe leer). */}
            <Route path="precios"            element={<Navigate to="/app/admin/facturacion" replace />} />
            <Route path="pago/resultado"     element={<Navigate to="/app/admin/facturacion" replace />} />

            {/* Pantallas nuevas; las rutas viejas redirigen para no romper enlaces */}
            <Route path="admin/personas"     element={<PersonasPage />} />
            <Route path="equipo"             element={<Navigate to="/app/admin/personas" replace />} />
            {/* Tareas: todo lo pendiente cruzando Sesiones. Las tareas viven dentro de
                una Sesión, pero "qué tengo pendiente" no es una pregunta sobre una Sesión. */}
            <Route path="tareas"             element={<TareasPage />} />
            <Route path="admin/workspace"    element={<WorkspacePage />} />
            <Route path="admin/agentes"      element={<AgentesAdminPage />} />
            {/* Facturación: el plan es de la empresa, así que vive en Admin y no en el
                perfil de la persona. `precios` queda como la vitrina publica. */}
            <Route path="admin/facturacion"  element={<FacturacionPage />} />
            {/* La ficha de un agente es UNA: el constructor. Admin > Agentes es la
                lista (ahi se ve de un vistazo lo que falta configurar) y abre ahi. */}
            <Route path="admin/agentes/:id"  element={<Navigate to="/app/agentes" replace />} />
            <Route path="organizaciones"     element={<Navigate to="/app/admin/workspace" replace />} />
          </Route>

          <Route path="*" element={<Navigate to="/app" replace />} />
        </Routes>
      </WorkspaceProvider>
    </AppProvider>
  );
}
