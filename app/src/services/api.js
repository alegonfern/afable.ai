import axios from 'axios';
import Cookies from 'js-cookie';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001/api/v1';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,
});

// ── Attach access token ──
apiClient.interceptors.request.use(
  (config) => {
    const token = Cookies.get('access_token');
    if (token) config.headers.Authorization = `Bearer ${token}`;
    return config;
  },
  (error) => Promise.reject(error)
);

// ── Silent token refresh on 401 ──
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true;
      try {
        const refreshToken = Cookies.get('refresh_token');
        if (refreshToken) {
          const { data } = await axios.post(`${API_BASE_URL}/auth/refresh/`, { refresh: refreshToken });
          Cookies.set('access_token', data.access, { expires: 1 });
          original.headers.Authorization = `Bearer ${data.access}`;
          return apiClient(original);
        }
      } catch {
        Cookies.remove('access_token');
        Cookies.remove('refresh_token');
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export const api = {
  // ── Auth ──
  login: (credentials) => apiClient.post('/auth/login/', credentials),
  register: (data) => apiClient.post('/auth/register/', data),
  requestPasswordReset: (data) => apiClient.post('/auth/password-reset-request/', data),
  resetPassword: (data) => apiClient.post('/auth/password-reset-confirm/', data),

  // ── User ──
  getCurrentUser: () => apiClient.get('/user/me/'),
  updateProfile: (data) => apiClient.patch('/user/me/', data),
  changePassword: (data) => apiClient.post('/user/change-password/', data),
  uploadAvatar: (formData) =>
    apiClient.post('/user/avatar/', formData, { headers: { 'Content-Type': 'multipart/form-data' } }),
  deleteAvatar: () => apiClient.delete('/user/avatar/delete/'),

  // ── Chat ──
  directChat: (message, history) => apiClient.post('/agents/direct-chat/', { message, history }),

  // ── Documents ──
  getDocuments: () => apiClient.get('/agents/documents/'),
  getDocument: (id) => apiClient.get(`/agents/documents/${id}/`),
  createDocument: (data) => apiClient.post('/agents/documents/', data),
  updateDocument: (id, data) => apiClient.patch(`/agents/documents/${id}/`, data),
  deleteDocument: (id) => apiClient.delete(`/agents/documents/${id}/`),

  // ── Conversations ──
  getConversations: () => apiClient.get('/agents/conversations/'),
  getConversationMessages: (id) => apiClient.get(`/agents/conversations/${id}/messages/`),
  deleteConversation: (id) => apiClient.delete(`/agents/conversations/${id}/`),
  // Renombrar el hilo, o moverlo a una Sesión — que es lo que significa COMPARTIRLO:
  // deja de ser del historial privado y pasa a verlo el equipo de esa Sesión.
  updateConversation: (id, data) => apiClient.patch(`/agents/conversations/${id}/`, data),
  getAgentConversations: (agentId) => apiClient.get(`/agents/${agentId}/conversations/`),
  // Ramificar: copia el hilo hasta ese mensaje a una conversación nueva.
  branchConversation: (id, messageId) =>
    apiClient.post(`/agents/conversations/${id}/ramificar/`, { message_id: messageId }),
  // Editar la propia pregunta. Borra lo que venía después (devuelve cuántos).
  editMessage: (convId, messageId, content) =>
    apiClient.patch(`/agents/conversations/${convId}/messages/${messageId}/`, { content }),

  // ── Agents ──
  getAgents: () => apiClient.get('/agents/'),
  // Galeria de la vista Trabajo: pestañas, buscador, orden y paginado.
  getAgentGallery: (params) => apiClient.get('/agents/gallery/', { params }),
  favoriteAgent: (id, workspace) => apiClient.post(`/agents/${id}/favorite/`, { workspace }),
  // Admin > Agentes: que datos, reglas e informacion le entrega la empresa.
  getAdminAgents: (workspace) => apiClient.get('/agents/admin/', { params: { workspace } }),
  getAdminAgent: (id, workspace) => apiClient.get(`/agents/admin/${id}/`, { params: { workspace } }),
  updateAdminAgent: (id, data) => apiClient.patch(`/agents/admin/${id}/`, data),
  unfavoriteAgent: (id, workspace) =>
    apiClient.delete(`/agents/${id}/favorite/`, { params: { workspace } }),
  createAgent: (data) => apiClient.post('/agents/', data),
  deleteAgent: (id) => apiClient.delete(`/agents/${id}/`),
  // Constructor: crear y editar un agente. `opciones` trae en un solo viaje los
  // modelos, sistemas, Habilidades y Espacios con los que se arma el formulario.
  getBuilderOptions: (workspace) =>
    apiClient.get('/agents/constructor/opciones/', { params: { workspace } }),
  buildAgent: (data) => apiClient.post('/agents/constructor/', data),
  getBuilderAgent: (id, workspace) =>
    apiClient.get(`/agents/constructor/${id}/`, { params: { workspace } }),
  updateBuilderAgent: (id, data) => apiClient.patch(`/agents/constructor/${id}/`, data),
  getModels: () => apiClient.get('/agents/models/'),
  uploadChatAttachment: (formData) => apiClient.post('/agents/chat-attachment/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),

  // ── Plantillas (galería Explorar + agentes por rol) ──
  getTemplates: (opts = {}) => apiClient.get('/agents/templates/', {
    params: {
      ...(opts.featured ? { featured: 1 } : {}),
      ...(opts.kind ? { kind: opts.kind } : {}),
    },
  }),
  useTemplate: (id) => apiClient.post(`/agents/templates/${id}/use/`),

  // ── Integrations (legacy) ──
  getIntegrationScans: () => apiClient.get('/organizations/scans/'),
  getActiveIntegrations: () => apiClient.get('/organizations/integrations/'),
  connectIntegration: (integration_type) => apiClient.post('/organizations/integrations/connect/', { integration_type }),
  disconnectIntegration: (integration_type) => apiClient.post('/organizations/integrations/disconnect/', { integration_type }),
  requestIntegration: (data) => apiClient.post('/organizations/integrations/request/', data),

  // ── Dashboard ──
  getDashboard: () => apiClient.get('/organizations/dashboard/'),
  getBusinessModel: () => apiClient.get('/organizations/model/'),

  // ── SystemConnections ──
  getConnections: () => apiClient.get('/organizations/connections/'),
  createConnection: (data) => apiClient.post('/organizations/connections/', data),
  updateConnection: (id, data) => apiClient.patch(`/organizations/connections/${id}/`, data),
  deleteConnection: (id) => apiClient.delete(`/organizations/connections/${id}/`),
  testConnection: (id) => apiClient.post(`/organizations/connections/${id}/test/`),
  syncConnection: (id) => apiClient.post(`/organizations/connections/${id}/sync/`),
  startGoogleDriveConnect: () => apiClient.get('/organizations/connections/google-drive/start/'),
  getDriveAccessToken: (id) => apiClient.get(`/organizations/connections/${id}/google-drive/access-token/`),
  saveDriveFolder: (id, data) => apiClient.post(`/organizations/connections/${id}/google-drive/folder/`, data),
  // Archivos elegidos uno por uno: la unica via que autoriza el scope drive.file.
  saveDriveFiles: (id, files) => apiClient.post(`/organizations/connections/${id}/google-drive/files/`, { files }),

  // ── Workspaces, personas e invitaciones ──
  getWorkspaces: () => apiClient.get('/workspaces/'),
  getSectors: () => apiClient.get('/workspaces/sectores/'),
  createWorkspace: (data) => apiClient.post('/workspaces/', data),
  getWorkspace: (slug) => apiClient.get(`/workspaces/${slug}/`),
  updateWorkspace: (slug, data) => apiClient.patch(`/workspaces/${slug}/`, data),
  getMembers: (slug) => apiClient.get(`/workspaces/${slug}/members/`),
  updateMemberRole: (slug, id, role) => apiClient.patch(`/workspaces/${slug}/members/${id}/`, { role }),
  removeMember: (slug, id) => apiClient.delete(`/workspaces/${slug}/members/${id}/`),
  getInvitations: (slug) => apiClient.get(`/workspaces/${slug}/invitations/`),
  createInvitation: (slug, data) => apiClient.post(`/workspaces/${slug}/invitations/`, data),
  revokeInvitation: (slug, id) => apiClient.delete(`/workspaces/${slug}/invitations/${id}/`),
  resendInvitation: (slug, id) => apiClient.post(`/workspaces/${slug}/invitations/${id}/resend/`),
  // ── Habilidades (bloques de instrucciones que se comparten entre agentes) ──
  getSkills: () => apiClient.get('/agents/habilidades/'),
  createSkill: (data) => apiClient.post('/agents/habilidades/', data),
  updateSkill: (id, data) => apiClient.patch(`/agents/habilidades/${id}/`, data),
  deleteSkill: (id) => apiClient.delete(`/agents/habilidades/${id}/`),

  // ── Archivos: carpetas, contenido e historial ──
  // El explorador trae en un viaje el árbol completo (panel izquierdo) y el contenido
  // de la carpeta abierta, que es como se usa la pantalla.
  getExplorador: (workspace, opts = {}) =>
    apiClient.get('/archivos/', { params: { workspace, ...opts } }),
  subirArchivo: (workspace, formData) =>
    apiClient.post(`/archivos/subir/?workspace=${workspace}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  createCarpeta: (data) => apiClient.post('/archivos/carpetas/', data),
  updateCarpeta: (id, data) => apiClient.patch(`/archivos/carpetas/${id}/`, data),
  deleteCarpeta: (id, workspace) =>
    apiClient.delete(`/archivos/carpetas/${id}/`, { params: { workspace } }),
  updateArchivo: (id, data) => apiClient.patch(`/archivos/documentos/${id}/`, data),
  getContenido: (id, workspace) =>
    apiClient.get(`/archivos/documentos/${id}/contenido/`, { params: { workspace } }),
  saveContenido: (id, data) => apiClient.put(`/archivos/documentos/${id}/contenido/`, data),
  getVersiones: (id, workspace) =>
    apiClient.get(`/archivos/documentos/${id}/versiones/`, { params: { workspace } }),
  getVersion: (id, numero, workspace) =>
    apiClient.get(`/archivos/documentos/${id}/versiones/${numero}/`, { params: { workspace } }),
  restaurarVersion: (id, numero, workspace) =>
    apiClient.post(`/archivos/documentos/${id}/versiones/${numero}/`, { workspace }),

  // ── Sesiones ──
  // Donde trabaja el equipo: conversaciones, tareas y archivos. El Workspace va como
  // `?workspace=`, no en la ruta (ver apps/sesiones/urls.py).
  getSesiones: (workspace, opts = {}) =>
    apiClient.get('/sesiones/', { params: { workspace, ...opts } }),
  createSesion: (data) => apiClient.post('/sesiones/', data),
  getSesion: (slug, workspace) =>
    apiClient.get(`/sesiones/${slug}/`, { params: { workspace } }),
  updateSesion: (slug, data) => apiClient.patch(`/sesiones/${slug}/`, data),
  deleteSesion: (slug, workspace) =>
    apiClient.delete(`/sesiones/${slug}/`, { params: { workspace } }),
  getSesionDisponibles: (slug, workspace) =>
    apiClient.get(`/sesiones/${slug}/disponibles/`, { params: { workspace } }),
  addSesionMiembros: (slug, data) => apiClient.post(`/sesiones/${slug}/miembros/`, data),
  removeSesionMiembros: (slug, data) =>
    apiClient.delete(`/sesiones/${slug}/miembros/`, { data }),
  // El feed: conversaciones y tareas en la misma lista, agrupadas por tiempo.
  getSesionFeed: (slug, workspace) =>
    apiClient.get(`/sesiones/${slug}/feed/`, { params: { workspace } }),
  // Tareas de la Sesion. `mias` y `estado` son los filtros de la pantalla.
  getSesionTareas: (slug, workspace, opts = {}) =>
    apiClient.get(`/sesiones/${slug}/tareas/`, { params: { workspace, ...opts } }),
  createSesionTarea: (slug, data) => apiClient.post(`/sesiones/${slug}/tareas/`, data),
  updateSesionTarea: (slug, id, data) =>
    apiClient.patch(`/sesiones/${slug}/tareas/${id}/`, data),
  deleteSesionTarea: (slug, id, workspace) =>
    apiClient.delete(`/sesiones/${slug}/tareas/${id}/`, { params: { workspace } }),
  runSesionTarea: (slug, id, workspace) =>
    apiClient.post(`/sesiones/${slug}/tareas/${id}/ejecutar/`, { workspace }),
  // Archivos de la Sesion (son CompanyDocument, con su texto extraido e indexado).
  getSesionArchivos: (slug, workspace, opts = {}) =>
    apiClient.get(`/sesiones/${slug}/archivos/`, { params: { workspace, ...opts } }),
  uploadSesionArchivo: (slug, workspace, formData) =>
    apiClient.post(`/sesiones/${slug}/archivos/?workspace=${workspace}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  deleteSesionArchivo: (slug, id, workspace) =>
    apiClient.delete(`/sesiones/${slug}/archivos/${id}/`, { params: { workspace } }),

  // ── Espacios ──
  getSpaces: (slug) => apiClient.get(`/workspaces/${slug}/espacios/`),
  createSpace: (slug, data) => apiClient.post(`/workspaces/${slug}/espacios/`, data),
  getSpace: (slug, space) => apiClient.get(`/workspaces/${slug}/espacios/${space}/`),
  updateSpace: (slug, space, data) => apiClient.patch(`/workspaces/${slug}/espacios/${space}/`, data),
  deleteSpace: (slug, space) => apiClient.delete(`/workspaces/${slug}/espacios/${space}/`),
  getSpaceAvailable: (slug, space) => apiClient.get(`/workspaces/${slug}/espacios/${space}/disponibles/`),
  getSpaceConversations: (slug, space) =>
    apiClient.get(`/workspaces/${slug}/espacios/${space}/conversaciones/`),
  // coleccion: conexiones | documentos | agentes | personas
  addToSpace: (slug, space, coleccion, ids) =>
    apiClient.post(`/workspaces/${slug}/espacios/${space}/${coleccion}/`, { ids }),
  removeFromSpace: (slug, space, coleccion, ids) =>
    apiClient.delete(`/workspaces/${slug}/espacios/${space}/${coleccion}/`, { data: { ids } }),

  // Por token: quien abre el link todavía no es miembro de ningún Workspace.
  getInvitation: (token) => apiClient.get(`/invitations/${token}/`),
  acceptInvitation: (token) => apiClient.post(`/invitations/${token}/accept/`),

  // ── Organizations ──
  getOrganizations: () => apiClient.get('/organizations/'),
  createOrganization: (data) => apiClient.post('/organizations/', data),
  getOrganization: (id) => apiClient.get(`/organizations/${id}/`),
  updateOrganization: (id, data) => apiClient.put(`/organizations/${id}/`, data),
  deleteOrganization: (id) => apiClient.delete(`/organizations/${id}/`),

  // ── Contexto de empresa ──
  getOrgContext: (orgId) => apiClient.get(`/organizations/${orgId}/context/`),
  updateOrgContext: (orgId, data) => apiClient.patch(`/organizations/${orgId}/context/`, data),
  getCompanyDocuments: (orgId, scope) =>
    apiClient.get(`/organizations/${orgId}/documents/${scope ? `?scope=${scope}` : ''}`),
  getContextCubicles: (orgId) => apiClient.get(`/organizations/${orgId}/context-cubicles/`),
  createContextCubicle: (orgId, data) => apiClient.post(`/organizations/${orgId}/context-cubicles/`, data),
  updateContextCubicle: (orgId, cubicleId, data) => apiClient.patch(`/organizations/${orgId}/context-cubicles/${cubicleId}/`, data),
  deleteContextCubicle: (orgId, cubicleId) => apiClient.delete(`/organizations/${orgId}/context-cubicles/${cubicleId}/`),
  getContextMarkdown: (orgId) => apiClient.get(`/organizations/${orgId}/context-cubicles/markdown/`),
  uploadCompanyDocument: (orgId, formData) =>
    apiClient.post(`/organizations/${orgId}/documents/`, formData, { headers: { 'Content-Type': 'multipart/form-data' } }),
  deleteCompanyDocument: (orgId, docId) => apiClient.delete(`/organizations/${orgId}/documents/${docId}/`),

  // ── Contexto personal ──
  getUserContext: () => apiClient.get('/user/me/context/'),
  updateUserContext: (data) => apiClient.patch('/user/me/context/', data),

  // ── Automatizaciones ──
  getAutomations: () => apiClient.get('/agents/automations/'),
  createAutomation: (data) => apiClient.post('/agents/automations/', data),
  updateAutomation: (id, data) => apiClient.patch(`/agents/automations/${id}/`, data),
  deleteAutomation: (id) => apiClient.delete(`/agents/automations/${id}/`),
  runAutomation: (id) => apiClient.post(`/agents/automations/${id}/run/`),

  // ── Rutinas ──
  getRoutines: () => apiClient.get('/agents/routines/'),
  createRoutine: (data) => apiClient.post('/agents/routines/', data),
  updateRoutine: (id, data) => apiClient.patch(`/agents/routines/${id}/`, data),
  deleteRoutine: (id) => apiClient.delete(`/agents/routines/${id}/`),
  runRoutine: (id) => apiClient.post(`/agents/routines/${id}/run/`),
};

export default apiClient;
