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
import AgentsPage from './pages/AgentsPage';
import ExplorePage from './pages/ExplorePage';
import ModelPage from './pages/ModelPage';
import IntegrationsPage from './pages/IntegrationsPage';
import TablondePage from './pages/TablondePage';
import DocumentsPage from './pages/DocumentsPage';
import ProfilePage from './pages/ProfilePage';
import MiContextoPage from './pages/MiContextoPage';
import ContextoPage from './pages/ContextoPage';
import ContextoHubPage from './pages/ContextoHubPage';
import EspacioDetallePage from './pages/espacios/EspacioDetallePage';
import AutomationsPage from './pages/AutomationsPage';
import RutinaPage from './pages/RutinaPage';
import SettingsPage from './pages/SettingsPage';
import HelpPage from './pages/HelpPage';
import PricingPage from './pages/PricingPage';
import PaymentResultPage from './pages/PaymentResultPage';

// Pantallas nuevas, que van reemplazando a las anteriores una por una.
// Personas reemplaza a TeamPage: la pertenencia y los roles ahora viven en el
// Workspace (Membership), no en los campos org_admin/areas del usuario.
import TrabajoHome from './pages/trabajo/TrabajoHome';
import AgentesPage from './pages/trabajo/AgentesPage';
import PersonasPage from './pages/admin/PersonasPage';
import WorkspacePage from './pages/admin/WorkspacePage';
import AgentesAdminPage from './pages/admin/AgentesAdminPage';
import AgenteConfigPage from './pages/admin/AgenteConfigPage';

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
            {/* "Agentes" es la galería del Workspace. La pantalla anterior
                (plantillas de rol) queda accesible hasta que se decida si la
                absorbe la galería. */}
            <Route path="agentes"            element={<AgentesPage />} />
            <Route path="agentes/plantillas" element={<AgentsPage />} />
            <Route path="home"               element={<ExplorePage />} />
            <Route path="integraciones"      element={<IntegrationsPage />} />
            <Route path="tablero"            element={<TablondePage />} />
            <Route path="documentos"         element={<DocumentsPage />} />
            <Route path="mi-contexto"        element={<MiContextoPage />} />
            <Route path="contexto"           element={<ContextoHubPage />} />
            <Route path="espacios/:spaceSlug" element={<EspacioDetallePage />} />
            <Route path="contexto-cubiculos" element={<ContextoPage />} />
            <Route path="contexto-empresa"   element={<Navigate to="/app/mi-contexto" replace />} />
            <Route path="automatizaciones"   element={<AutomationsPage />} />
            <Route path="rutina"             element={<RutinaPage />} />
            <Route path="perfil"             element={<ProfilePage />} />
            <Route path="configuracion"      element={<SettingsPage />} />
            <Route path="ayuda"              element={<HelpPage />} />
            <Route path="precios"            element={<PricingPage />} />
            <Route path="pago/resultado"     element={<PaymentResultPage />} />

            {/* Pantallas nuevas; las rutas viejas redirigen para no romper enlaces */}
            <Route path="admin/personas"     element={<PersonasPage />} />
            <Route path="equipo"             element={<Navigate to="/app/admin/personas" replace />} />
            <Route path="admin/workspace"    element={<WorkspacePage />} />
            <Route path="admin/agentes"      element={<AgentesAdminPage />} />
            <Route path="admin/agentes/:id"  element={<AgenteConfigPage />} />
            <Route path="organizaciones"     element={<Navigate to="/app/admin/workspace" replace />} />
          </Route>

          <Route path="*" element={<Navigate to="/app" replace />} />
        </Routes>
      </WorkspaceProvider>
    </AppProvider>
  );
}
