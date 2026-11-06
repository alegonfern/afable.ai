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
  // Abrir un hilo NUEVO dentro de una Sesión, sin salir de ella. `sesion` es lo que hace
  // que la conversación quede colgada ahí y la vea el equipo.
  directChatEnSesion: (data) => apiClient.post('/agents/direct-chat/', data),

  // Responder DENTRO de un hilo que ya existe: es lo que convierte a la Sesión en una
  // conversación del equipo y no en un muro de hilos sueltos. El permiso lo resuelve el
  // backend (`hilo_para_escribir`): entra quien alcance la Sesión.
  responderEnHilo: (conversationId, message, extra = {}) =>
    apiClient.post('/agents/direct-chat/', { message, conversation_id: conversationId, ...extra }),

  // ── Documents ──
  getDocuments: () => apiClient.get('/agents/documents/'),
  getDocument: (id) => apiClient.get(`/agents/documents/${id}/`),
  createDocument: (data) => apiClient.post('/agents/documents/', data),
  updateDocument: (id, data) => apiClient.patch(`/agents/documents/${id}/`, data),
  deleteDocument: (id) => apiClient.delete(`/agents/documents/${id}/`),

  // ── Conversations ──
  // params: { q, limite, compartidos }. Sin params se comporta como antes.
  getConversations: (params) => apiClient.get('/agents/conversations/', { params }),
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
  // A quién se puede mencionar acá: agentes Y personas, en una sola lista. Para quien
  // escribe, `@` es UNA cosa —"a quién le hablo"— y no dos.
  getMencionables: (workspace, sesion) =>
    apiClient.get('/agents/mencionables/', { params: { workspace, sesion } }),
  // La ficha de un agente: a qué alcanza, qué preguntarle y qué ya hizo.
  getFichaDelAgente: (id, workspace) =>
    apiClient.get(`/agents/${id}/ficha/`, { params: { workspace } }),
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

  // Los agentes que Afable propone sobre las carpetas que ya tienen material. La lista es
  // barata; redactar cuesta una llamada al modelo, por eso se pide de a una.
  // Qué le conviene hacer ahora a quien pregunta. Se CALCULA en el servidor a partir del
  // estado real de la empresa: no gasta tokens. La IA entra recién si tocan una.
  getRecomendaciones: (workspace) =>
    apiClient.get('/agents/recomendaciones/', { params: { workspace } }),
  // Sobre qué puede trabajar un agente nuevo: carpetas con material y herramientas
  // conectadas. Es lo que reemplaza al formulario en blanco.
  getOrigenesDeAgente: (workspace) =>
    apiClient.get('/agents/propuestas/origenes/', { params: { workspace } }),
  getPropuestasDeAgente: (workspace) =>
    apiClient.get('/agents/propuestas/', { params: { workspace } }),
  redactarPropuestaDeAgente: (workspace, carpeta) =>
    apiClient.post('/agents/propuestas/redactar/', { workspace, carpeta }),
  aceptarPropuestaDeAgente: (data) =>
    apiClient.post('/agents/propuestas/aceptar/', data),
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
  // ⭐ Esto NO borra: apaga el conector. Lo que entró por él se queda, porque borrarlo
  // dejaría documentos sin origen y agentes apuntando a un sistema que ya no existe.
  desactivarConnection: (id) => apiClient.delete(`/organizations/connections/${id}/`),
  // La excepción: descartar el conector de PRUEBA cuando el test falla. Ese nunca llegó
  // a ser un conector de la empresa, es un intento — y si se desactivara en vez de
  // borrarse, cada credencial mal tipeada dejaría un fantasma en la lista.
  descartarConnectionDePrueba: (id) =>
    apiClient.delete(`/organizations/connections/${id}/?descartar=1`),
  getCatalogoDeConectores: () => apiClient.get('/organizations/connections/catalogo/'),

  // Banco de pruebas: recorrer estados del producto sin armarlos a mano. Solo responde a
  // los correos de CUENTAS_DE_PRUEBA; para el resto es 403.
  getBancoDePruebas: (workspace) =>
    apiClient.get('/organizations/banco-de-pruebas/', { params: { workspace } }),
  correrEnBancoDePruebas: (data) =>
    apiClient.post('/organizations/banco-de-pruebas/', data),
  cambiarEstadoConnection: (id, is_active) =>
    apiClient.post(`/organizations/connections/${id}/estado/`, { is_active }),
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
  // Acepta JSON o un FormData (el logo). El cliente fuerza `application/json` por
  // omisión, y con ese encabezado el multipart viaja sin su boundary y el backend
  // responde 400: hay que dejar que axios lo arme cuando el cuerpo es un FormData.
  // Las tareas cruzando Sesiones: la pantalla "qué tengo pendiente".
  getTareasDelWorkspace: (workspace, params = {}) =>
    apiClient.get('/tareas/', { params: { workspace, ...params } }),

  updateWorkspace: (slug, data) =>
    apiClient.patch(`/workspaces/${slug}/`, data,
      data instanceof FormData ? { headers: { 'Content-Type': 'multipart/form-data' } } : undefined),
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
  // Permisos por carpeta y por archivo. `restringido` prende o apaga la restricción;
  // `ids` + `nivel` reparten el acceso.
  getCompartido: (workspace, opts) =>
    apiClient.get('/archivos/compartir/', { params: { workspace, ...opts } }),
  compartir: (data) => apiClient.post('/archivos/compartir/', data),
  descompartir: (data) => apiClient.delete('/archivos/compartir/', { data }),
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
  // Qué cambió exactamente en una versión: líneas agregadas y quitadas.
  getCambiosDeVersion: (id, numero, workspace) =>
    apiClient.get(`/archivos/documentos/${id}/versiones/${numero}/cambios/`, {
      params: { workspace },
    }),

  // ── Notificaciones ──
  // Lo dirigido a ESTA persona. El contador viene aparte del listado: es sobre todas las
  // sin leer, no sobre las que se alcanzan a mostrar.
  getNotificaciones: () => apiClient.get('/notificaciones/'),
  marcarNotificacionesLeidas: () => apiClient.post('/notificaciones/'),
  marcarNotificacionLeida: (id) => apiClient.post(`/notificaciones/${id}/leida/`),

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

  // ── Soporte ──
  // El formulario de la burbuja. El contexto (pantalla, empresa, Workspace, modelo y
  // errores) lo arma el componente: quien está atascado no tiene por qué saberlo.
  enviarMensajeSoporte: (data) => apiClient.post('/soporte/', data),

  // Lo que los agentes hicieron solos: la evidencia del trabajo autónomo.
  loQueHizoAfable: (slug, dias) =>
    apiClient.get(`/workspaces/${slug}/lo-que-hizo/`, { params: dias ? { dias } : {} }),

  // Descargar el documento como PDF con formato: es lo que se le manda a un cliente.
  //
  // ⚠️ Baja por `apiClient`, NO como enlace directo. Un `<a href>` lo pide el navegador
  // por su cuenta y no lleva la cabecera `Authorization`: la API contesta 401 y la
  // persona ve un error donde esperaba su archivo. Además, así el PDF también aprovecha
  // el reintento que refresca el token vencido.
  descargarPdfDelArchivo: (id, workspace) =>
    apiClient.get(`/archivos/documentos/${id}/pdf/`, {
      params: { workspace },
      responseType: 'blob',
    }),

  // El archivo mismo, con la sesión puesta. Un <iframe src> o un <img src> lo pediría el
  // navegador por su cuenta, sin la cabecera de sesión: por eso se baja como blob y se
  // dibuja desde memoria.
  descargarArchivo: (id, workspace) =>
    apiClient.get(`/archivos/documentos/${id}/archivo/`, {
      params: { workspace }, responseType: 'blob',
    }),
  // Cómo se MUESTRA un archivo: planilla, documento con formato, PDF o texto.
  getVistaDelArchivo: (id, workspace) =>
    apiClient.get(`/archivos/documentos/${id}/vista/`, { params: { workspace } }),

  // ── La primera hora ──
  // La empresa de ejemplo: documentos de verdad para poder preguntar antes de cargar
  // nada. Van marcados y se quitan de una sola vez.
  cargarDatosDeEjemplo: (slug) => apiClient.post(`/workspaces/${slug}/ejemplo/`),
  quitarDatosDeEjemplo: (slug) => apiClient.delete(`/workspaces/${slug}/ejemplo/`),
  // Qué le falta a la empresa. El avance lo calcula el backend del estado real, así que
  // acá no hay nada que recordar entre pantallas.
  getPrimerosPasos: (slug) => apiClient.get(`/workspaces/${slug}/primeros-pasos/`),
  ocultarPrimerosPasos: (slug) => apiClient.post(`/workspaces/${slug}/primeros-pasos/`, {}),

  // ── Facturación ──
  // Cuelga del Workspace porque el que paga es la empresa, no la persona. Todo esto
  // exige ser administrador: el backend contesta 403 a un editor.
  getFacturacion: (slug) => apiClient.get(`/workspaces/${slug}/facturacion/`),
  suscribir: (slug, planId, proveedor) =>
    apiClient.post(`/workspaces/${slug}/facturacion/suscribir/`, { plan_id: planId, proveedor }),
  cancelarSuscripcion: (slug) =>
    apiClient.post(`/workspaces/${slug}/facturacion/cancelar/`),
  agregarMetodoPago: (slug, proveedor) =>
    apiClient.post(`/workspaces/${slug}/facturacion/metodos/`, { proveedor }),
  quitarMetodoPago: (slug, id) =>
    apiClient.delete(`/workspaces/${slug}/facturacion/metodos/${id}/`),
  metodoPagoPrincipal: (slug, id) =>
    apiClient.post(`/workspaces/${slug}/facturacion/metodos/${id}/principal/`),

  // ── Finanzas ── lo que la empresa descarga del SII, clasificado. Cuelga de la Empresa:
  // ver es de cualquier miembro; cargar, clasificar y configurar, de editor para arriba.
  // Compras y Ventas (22-10-2026): /workspaces/<slug>/comercial/...
  comercial: {
    configuracion: (slug) => apiClient.get(`/workspaces/${slug}/comercial/configuracion/`),
    guardarConfiguracion: (slug, datos) => apiClient.put(`/workspaces/${slug}/comercial/configuracion/`, datos),
    resumen: (slug, tipo) => apiClient.get(`/workspaces/${slug}/comercial/resumen/`, { params: { tipo } }),
    contactos: (slug, params) => apiClient.get(`/workspaces/${slug}/comercial/contactos/`, { params }),
    contacto: (slug, id) => apiClient.get(`/workspaces/${slug}/comercial/contactos/${id}/`),
    crearContacto: (slug, datos) => apiClient.post(`/workspaces/${slug}/comercial/contactos/`, datos),
    actualizarContacto: (slug, id, datos) => apiClient.patch(`/workspaces/${slug}/comercial/contactos/${id}/`, datos),
    productos: (slug, params) => apiClient.get(`/workspaces/${slug}/comercial/productos/`, { params }),
    crearProducto: (slug, datos) => apiClient.post(`/workspaces/${slug}/comercial/productos/`, datos),
    actualizarProducto: (slug, id, datos) => apiClient.patch(`/workspaces/${slug}/comercial/productos/${id}/`, datos),
    bodegas: (slug) => apiClient.get(`/workspaces/${slug}/comercial/bodegas/`),
    crearBodega: (slug, datos) => apiClient.post(`/workspaces/${slug}/comercial/bodegas/`, datos),
    actualizarBodega: (slug, id, datos) => apiClient.patch(`/workspaces/${slug}/comercial/bodegas/${id}/`, datos),
    stock: (slug) => apiClient.get(`/workspaces/${slug}/comercial/stock/`),
    ajustar: (slug, datos) => apiClient.post(`/workspaces/${slug}/comercial/stock/ajuste/`, datos),
    traspasar: (slug, datos) => apiClient.post(`/workspaces/${slug}/comercial/stock/traspaso/`, datos),
    movimientos: (slug, params) => apiClient.get(`/workspaces/${slug}/comercial/movimientos/`, { params }),
    pedidos: (slug, params) => apiClient.get(`/workspaces/${slug}/comercial/pedidos/`, { params }),
    pedido: (slug, id) => apiClient.get(`/workspaces/${slug}/comercial/pedidos/${id}/`),
    crearPedido: (slug, datos) => apiClient.post(`/workspaces/${slug}/comercial/pedidos/`, datos),
    actualizarPedido: (slug, id, datos) => apiClient.patch(`/workspaces/${slug}/comercial/pedidos/${id}/`, datos),
    borrarPedido: (slug, id) => apiClient.delete(`/workspaces/${slug}/comercial/pedidos/${id}/`),
    accion: (slug, id, accion, extra = {}) => apiClient.post(`/workspaces/${slug}/comercial/pedidos/${id}/accion/`, { accion, ...extra }),
    entregar: (slug, id, datos) => apiClient.post(`/workspaces/${slug}/comercial/pedidos/${id}/entregar/`, datos),
    anularEntrega: (slug, id) => apiClient.post(`/workspaces/${slug}/comercial/entregas/${id}/anular/`),
    // La guía de despacho electrónica (52) de una entrega, con el facturador nativo.
    emitirGuia: (slug, pedido, entrega, transporte = {}) =>
      apiClient.post(`/workspaces/${slug}/comercial/pedidos/${pedido}/entregas/${entrega}/guia/`, transporte),
    entregas: (slug, tipo) => apiClient.get(`/workspaces/${slug}/comercial/entregas/`, { params: { tipo } }),
    candidatas: (slug, id) => apiClient.get(`/workspaces/${slug}/comercial/pedidos/${id}/facturas/`),
    vincular: (slug, id, datos) => apiClient.post(`/workspaces/${slug}/comercial/pedidos/${id}/facturas/`, datos),
    desvincular: (slug, id, documento) =>
      apiClient.delete(`/workspaces/${slug}/comercial/pedidos/${id}/facturas/`, { params: { documento } }),
    pdf: (slug, id) => apiClient.get(`/workspaces/${slug}/comercial/pedidos/${id}/pdf/`, { responseType: 'blob' }),
    pdfFactura: (slug, id) => apiClient.get(`/workspaces/${slug}/comercial/facturas/${id}/pdf/`, { responseType: 'blob' }),
    enviarCorreo: (slug, id, datos) => apiClient.post(`/workspaces/${slug}/comercial/pedidos/${id}/correo/`, datos),
    porFacturar: (slug, tipo) => apiClient.get(`/workspaces/${slug}/comercial/por-facturar/`, { params: { tipo } }),
    // 24-10-2026: cobros y pagos, devoluciones, precios por contacto, reponer, reportes y planillas.
    pagar: (slug, id, datos) => apiClient.post(`/workspaces/${slug}/comercial/pedidos/${id}/pagos/`, datos),
    borrarPago: (slug, id, pago) => apiClient.delete(`/workspaces/${slug}/comercial/pedidos/${id}/pagos/${pago}/`),
    devolver: (slug, id, datos) => apiClient.post(`/workspaces/${slug}/comercial/pedidos/${id}/devolver/`, datos),
    precios: (slug, params) => apiClient.get(`/workspaces/${slug}/comercial/precios/`, { params }),
    guardarPrecio: (slug, datos) => apiClient.post(`/workspaces/${slug}/comercial/precios/`, datos),
    borrarPrecio: (slug, id) => apiClient.delete(`/workspaces/${slug}/comercial/precios/${id}/`),
    reponer: (slug) => apiClient.post(`/workspaces/${slug}/comercial/stock/reponer/`),
    reporte: (slug, params) => apiClient.get(`/workspaces/${slug}/comercial/reportes/`, { params }),
    exportar: (slug, que, params) => apiClient.get(`/workspaces/${slug}/comercial/exportar/${que}/`, { params, responseType: 'blob' }),
    plantilla: (slug, que) => apiClient.get(`/workspaces/${slug}/comercial/importar/${que}/`, { responseType: 'blob' }),
    importar: (slug, que, archivo) => {
      const datos = new FormData();
      datos.append('file', archivo);
      return apiClient.post(`/workspaces/${slug}/comercial/importar/${que}/`, datos, { headers: { 'Content-Type': 'multipart/form-data' } });
    },
    tipoCambio: (slug, moneda, fecha) =>
      apiClient.get(`/workspaces/${slug}/comercial/tipo-cambio/`, { params: { moneda, fecha } }),
  },
  // Conectores (27-10-2026): /workspaces/<slug>/conectores/... Ver: miembros; sincronizar: editor;
  // conectar, opciones y desconectar: administrador.
  conectores: {
    lista: (slug) => apiClient.get(`/workspaces/${slug}/conectores/`),
    detalle: (slug, tipo) => apiClient.get(`/workspaces/${slug}/conectores/${tipo}/`),
    opciones: (slug, tipo, config) => apiClient.patch(`/workspaces/${slug}/conectores/${tipo}/`, { config }),
    conectar: (slug, tipo, datos = {}) => apiClient.post(`/workspaces/${slug}/conectores/${tipo}/conectar/`, datos),
    sincronizar: (slug, tipo, opciones = {}) => apiClient.post(`/workspaces/${slug}/conectores/${tipo}/sincronizar/`, opciones),
    desconectar: (slug, tipo) => apiClient.post(`/workspaces/${slug}/conectores/${tipo}/desconectar/`),
    historial: (slug, tipo) => apiClient.get(`/workspaces/${slug}/conectores/${tipo}/historial/`),
  },
  // Inventario (26-10-2026): /workspaces/<slug>/comercial/inventario/... Ver es de cualquier
  // miembro; entradas, salidas, conteos e importaciones, de editor para arriba.
  inventario: {
    resumen: (slug, params) => apiClient.get(`/workspaces/${slug}/comercial/inventario/resumen/`, { params }),
    stock: (slug, params) => apiClient.get(`/workspaces/${slug}/comercial/inventario/stock/`, { params }),
    entrada: (slug, datos) => apiClient.post(`/workspaces/${slug}/comercial/inventario/entrada/`, datos),
    salida: (slug, datos) => apiClient.post(`/workspaces/${slug}/comercial/inventario/salida/`, datos),
    kardex: (slug, id, params) => apiClient.get(`/workspaces/${slug}/comercial/inventario/kardex/${id}/`, { params }),
    movimientos: (slug, params) => apiClient.get(`/workspaces/${slug}/comercial/inventario/movimientos/`, { params }),
    valorizacion: (slug, params) => apiClient.get(`/workspaces/${slug}/comercial/inventario/valorizacion/`, { params }),
    rotacion: (slug, params) => apiClient.get(`/workspaces/${slug}/comercial/inventario/rotacion/`, { params }),
    conteos: (slug) => apiClient.get(`/workspaces/${slug}/comercial/inventario/conteos/`),
    crearConteo: (slug, datos) => apiClient.post(`/workspaces/${slug}/comercial/inventario/conteos/`, datos),
    conteo: (slug, id) => apiClient.get(`/workspaces/${slug}/comercial/inventario/conteos/${id}/`),
    contar: (slug, id, lineas) => apiClient.patch(`/workspaces/${slug}/comercial/inventario/conteos/${id}/lineas/`, { lineas }),
    aplicarConteo: (slug, id) => apiClient.post(`/workspaces/${slug}/comercial/inventario/conteos/${id}/aplicar/`),
    cancelarConteo: (slug, id) => apiClient.post(`/workspaces/${slug}/comercial/inventario/conteos/${id}/cancelar/`),
    planillaConteo: (slug, id) => apiClient.get(`/workspaces/${slug}/comercial/inventario/conteos/${id}/planilla/`, { responseType: 'blob' }),
    subirPlanillaConteo: (slug, id, archivo) => {
      const datos = new FormData();
      datos.append('archivo', archivo);
      return apiClient.post(`/workspaces/${slug}/comercial/inventario/conteos/${id}/planilla/`, datos, { headers: { 'Content-Type': 'multipart/form-data' } });
    },
    plantillaInicial: (slug) => apiClient.get(`/workspaces/${slug}/comercial/inventario/plantilla-inicial/`, { responseType: 'blob' }),
    importarInicial: (slug, archivo) => {
      const datos = new FormData();
      datos.append('archivo', archivo);
      return apiClient.post(`/workspaces/${slug}/comercial/inventario/importar-inicial/`, datos, { headers: { 'Content-Type': 'multipart/form-data' } });
    },
    exportar: (slug, que, params) => apiClient.get(`/workspaces/${slug}/comercial/inventario/exportar/${que}/`, { params, responseType: 'blob' }),
  },
  // Facturación electrónica nativa (26-10-2026): /workspaces/<slug>/dte/... Ver es de cualquier
  // miembro; el certificado, los folios y activar son del administrador; notas y reintentos, de editor.
  dte: {
    estado: (slug, ambiente) => apiClient.get(`/workspaces/${slug}/dte/estado/`, { params: { ambiente } }),
    guardarConfiguracion: (slug, datos) => apiClient.put(`/workspaces/${slug}/dte/configuracion/`, datos),
    subirCertificado: (slug, archivo, clave) => {
      const datos = new FormData();
      datos.append('archivo', archivo);
      datos.append('clave', clave);
      return apiClient.post(`/workspaces/${slug}/dte/certificado/`, datos, { headers: { 'Content-Type': 'multipart/form-data' } });
    },
    cafs: (slug, ambiente) => apiClient.get(`/workspaces/${slug}/dte/cafs/`, { params: { ambiente } }),
    subirCaf: (slug, archivo, primerFolio) => {
      const datos = new FormData();
      datos.append('archivo', archivo);
      if (primerFolio) datos.append('primer_folio', primerFolio);
      return apiClient.post(`/workspaces/${slug}/dte/cafs/`, datos, { headers: { 'Content-Type': 'multipart/form-data' } });
    },
    probarConexion: (slug, ambiente) => apiClient.post(`/workspaces/${slug}/dte/probar-conexion/`, { ambiente }),
    activar: (slug, ambiente) => apiClient.post(`/workspaces/${slug}/dte/activar/`, { ambiente }),
    desactivar: (slug) => apiClient.post(`/workspaces/${slug}/dte/desactivar/`),
    documentos: (slug, params) => apiClient.get(`/workspaces/${slug}/dte/documentos/`, { params }),
    xml: (slug, id) => apiClient.get(`/workspaces/${slug}/dte/documentos/${id}/xml/`, { responseType: 'blob' }),
    pdf: (slug, id, cedible) => apiClient.get(`/workspaces/${slug}/dte/documentos/${id}/pdf/`, { params: cedible ? { cedible: 1 } : {}, responseType: 'blob' }),
    nota: (slug, id, datos) => apiClient.post(`/workspaces/${slug}/dte/documentos/${id}/nota/`, datos),
    envio: (slug, id) => apiClient.get(`/workspaces/${slug}/dte/envios/${id}/`),
    reintentar: (slug, id) => apiClient.post(`/workspaces/${slug}/dte/envios/${id}/reintentar/`),
    // Intercambio: lo que llega de los proveedores y la casilla donde llega.
    recibidos: (slug, params) => apiClient.get(`/workspaces/${slug}/dte/recibidos/`, { params }),
    subirRecibido: (slug, archivo) => {
      const datos = new FormData();
      datos.append('archivo', archivo);
      return apiClient.post(`/workspaces/${slug}/dte/recibidos/subir/`, datos, { headers: { 'Content-Type': 'multipart/form-data' } });
    },
    aceptarRecibido: (slug, id, datos = {}) => apiClient.post(`/workspaces/${slug}/dte/recibidos/${id}/aceptar/`, datos),
    reclamarRecibido: (slug, id, datos) => apiClient.post(`/workspaces/${slug}/dte/recibidos/${id}/reclamar/`, datos),
    xmlRecibido: (slug, id) => apiClient.get(`/workspaces/${slug}/dte/recibidos/${id}/xml/`, { responseType: 'blob' }),
    casilla: (slug) => apiClient.get(`/workspaces/${slug}/dte/casilla/`),
    guardarCasilla: (slug, datos) => apiClient.put(`/workspaces/${slug}/dte/casilla/`, datos),
    probarCasilla: (slug) => apiClient.post(`/workspaces/${slug}/dte/casilla/probar/`),
    revisarCasilla: (slug) => apiClient.post(`/workspaces/${slug}/dte/casilla/revisar/`),
    enviarACliente: (slug, id, correo) => apiClient.post(`/workspaces/${slug}/dte/documentos/${id}/enviar-a-cliente/`, correo ? { correo } : {}),
    // Certificación ante el SII, paso a paso.
    certificacion: (slug) => apiClient.get(`/workspaces/${slug}/dte/certificacion/`),
    cargarSet: (slug, texto, archivo) => {
      const datos = new FormData();
      if (texto) datos.append('texto', texto);
      if (archivo) datos.append('archivo', archivo);
      return apiClient.post(`/workspaces/${slug}/dte/certificacion/set/`, datos, { headers: { 'Content-Type': 'multipart/form-data' } });
    },
    generarCertificacion: (slug, que, datos = {}) => apiClient.post(`/workspaces/${slug}/dte/certificacion/generar/`, { que, ...datos }),
    subirCertificacion: (slug) => apiClient.post(`/workspaces/${slug}/dte/certificacion/subir/`),
    consultarCertificacion: (slug) => apiClient.post(`/workspaces/${slug}/dte/certificacion/consultar/`),
    pasoCertificacion: (slug, paso) => apiClient.post(`/workspaces/${slug}/dte/certificacion/paso/`, { paso }),
    xmlCertificacion: (slug, id) => apiClient.get(`/workspaces/${slug}/dte/certificacion/envios/${id}/xml/`, { responseType: 'blob' }),
    intercambioCertificacion: (slug, archivo) => {
      const datos = new FormData();
      datos.append('archivo', archivo);
      return apiClient.post(`/workspaces/${slug}/dte/certificacion/intercambio/`, datos, { headers: { 'Content-Type': 'multipart/form-data' }, responseType: 'blob' });
    },
    muestrasCertificacion: (slug) => apiClient.get(`/workspaces/${slug}/dte/certificacion/muestras/`, { responseType: 'blob' }),
  },
  finanzas: {
    configuracion: (slug) => apiClient.get(`/workspaces/${slug}/finanzas/configuracion/`),
    guardarConfiguracion: (slug, datos) =>
      apiClient.put(`/workspaces/${slug}/finanzas/configuracion/`, datos),
    categorias: (slug) => apiClient.get(`/workspaces/${slug}/finanzas/categorias/`),
    actualizarCategoria: (slug, id, datos) =>
      apiClient.patch(`/workspaces/${slug}/finanzas/categorias/${id}/`, datos),
    proyectos: (slug) => apiClient.get(`/workspaces/${slug}/finanzas/proyectos/`),
    crearProyecto: (slug, nombre) =>
      apiClient.post(`/workspaces/${slug}/finanzas/proyectos/`, { nombre }),
    cargas: (slug) => apiClient.get(`/workspaces/${slug}/finanzas/cargas/`),
    cargar: (slug, archivo, libro) => {
      const datos = new FormData();
      datos.append('file', archivo);
      if (libro) datos.append('libro', libro);
      return apiClient.post(`/workspaces/${slug}/finanzas/cargas/`, datos, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
    },
    // La carga queda en borrador: se revisa, se puede pedir a la IA lo que falte y se confirma.
    carga: (slug, id) => apiClient.get(`/workspaces/${slug}/finanzas/cargas/${id}/`),
    cancelarCarga: (slug, id) => apiClient.delete(`/workspaces/${slug}/finanzas/cargas/${id}/`),
    sugerirCarga: (slug, id) => apiClient.post(`/workspaces/${slug}/finanzas/cargas/${id}/sugerir/`),
    confirmarCarga: (slug, id, decisiones) =>
      apiClient.post(`/workspaces/${slug}/finanzas/cargas/${id}/confirmar/`, { decisiones }),
    contrapartes: (slug, libros) =>
      apiClient.get(`/workspaces/${slug}/finanzas/contrapartes/`, {
        params: { libro: libros }, paramsSerializer: { indexes: null },
      }),
    actualizarContraparte: (slug, id, cambios) =>
      apiClient.patch(`/workspaces/${slug}/finanzas/contrapartes/${id}/`, cambios),
    // Los números (calculados en el servidor desde los documentos).
    resumen: (slug, anio) => apiClient.get(`/workspaces/${slug}/finanzas/resumen/`, { params: { anio } }),
    impuestos: (slug, anio) => apiClient.get(`/workspaces/${slug}/finanzas/impuestos/`, { params: { anio } }),
    marcarF29: (slug, anio, mes, datos) =>
      apiClient.patch(`/workspaces/${slug}/finanzas/impuestos/${anio}/${mes}/`, datos),
    porCategoria: (slug, params) => apiClient.get(`/workspaces/${slug}/finanzas/por-categoria/`, { params }),
    margenProyectos: (slug, anio) =>
      apiClient.get(`/workspaces/${slug}/finanzas/proyectos/margen/`, { params: { anio } }),
    // Conciliación ("El cuadre").
    cuentas: (slug) => apiClient.get(`/workspaces/${slug}/finanzas/cuentas/`),
    crearCuenta: (slug, datos) => apiClient.post(`/workspaces/${slug}/finanzas/cuentas/`, datos),
    subirCartola: (slug, cuenta, archivo) => {
      const datos = new FormData();
      datos.append('cuenta', cuenta);
      datos.append('file', archivo);
      return apiClient.post(`/workspaces/${slug}/finanzas/cartolas/`, datos, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
    },
    cuadre: (slug, params) => apiClient.get(`/workspaces/${slug}/finanzas/cuadre/`, { params }),
    movimientos: (slug, params) => apiClient.get(`/workspaces/${slug}/finanzas/movimientos/`, { params }),
    accionMovimiento: (slug, id, accion, datos = {}) =>
      apiClient.post(`/workspaces/${slug}/finanzas/movimientos/${id}/${accion}/`, datos),
    cierres: (slug) => apiClient.get(`/workspaces/${slug}/finanzas/cuadre/cierres/`),
    cerrarMes: (slug, anio, mes) => apiClient.post(`/workspaces/${slug}/finanzas/cuadre/cierres/`, { anio, mes }),
    reabrirMes: (slug, anio, mes) =>
      apiClient.delete(`/workspaces/${slug}/finanzas/cuadre/cierres/`, { params: { anio, mes } }),
    ventas: (slug, anio) => apiClient.get(`/workspaces/${slug}/finanzas/ventas/`, { params: { anio } }),
    // Automatizaciones de cada módulo (catálogo fijo que la empresa activa).
    // Lo que hizo hoy el agente de un módulo (vista "Agente", 25-10-2026).
    actividadAgente: (slug, modulo) => apiClient.get(`/workspaces/${slug}/finanzas/agentes/${modulo}/hoy/`),
    automatizaciones: (slug, modulo) =>
      apiClient.get(`/workspaces/${slug}/finanzas/automatizaciones/`, { params: { modulo } }),
    actualizarAutomatizacion: (slug, clave, datos) =>
      apiClient.patch(`/workspaces/${slug}/finanzas/automatizaciones/${clave}/`, datos),
    probarAutomatizacion: (slug, clave) =>
      apiClient.post(`/workspaces/${slug}/finanzas/automatizaciones/${clave}/`),
    // Finanzas: la plata.
    cuentasPor: (slug, tipo) => apiClient.get(`/workspaces/${slug}/finanzas/cuentas-por/${tipo}/`),
    caja: (slug) => apiClient.get(`/workspaces/${slug}/finanzas/caja/`),
    cuentaDueno: (slug) => apiClient.get(`/workspaces/${slug}/finanzas/cuenta-dueno/`),
    documentos: (slug, filtros = {}) =>
      apiClient.get(`/workspaces/${slug}/finanzas/documentos/`, { params: filtros }),
    actualizarDocumento: (slug, id, cambios) =>
      apiClient.patch(`/workspaces/${slug}/finanzas/documentos/${id}/`, cambios),
    lote: (slug, datos) => apiClient.post(`/workspaces/${slug}/finanzas/documentos/lote/`, datos),
    sugerir: (slug) => apiClient.post(`/workspaces/${slug}/finanzas/documentos/sugerir/`),
  },

  // ── Rutinas ──
  getRoutines: () => apiClient.get('/agents/routines/'),
  createRoutine: (data) => apiClient.post('/agents/routines/', data),
  updateRoutine: (id, data) => apiClient.patch(`/agents/routines/${id}/`, data),
  deleteRoutine: (id) => apiClient.delete(`/agents/routines/${id}/`),
  runRoutine: (id) => apiClient.post(`/agents/routines/${id}/run/`),
};

export default apiClient;
