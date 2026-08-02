import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { api } from '../services/api';
import { authService } from '../services/auth';
import { useApp } from './AppContext';

/**
 * El Workspace activo del usuario.
 *
 * El backend recibe el Workspace en la URL (/api/v1/workspaces/<slug>/...), asi
 * que quien arma esas URLs es este contexto: guarda cual esta activo y su rol.
 * Lo consumen el conmutador del encabezado, la barra lateral, Personas y la
 * pantalla de Workspace.
 */

const CLAVE_GUARDADA = 'afable_workspace_slug';
// El Espacio en el que se esta trabajando. Se guarda por Workspace: cambiar de
// empresa no puede dejar activo el Espacio de la anterior.
const CLAVE_ESPACIO = 'afable_espacio_slug';

const WorkspaceContext = createContext();

export const useWorkspace = () => {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) throw new Error('useWorkspace debe usarse dentro de WorkspaceProvider');
  return ctx;
};

export const WorkspaceProvider = ({ children }) => {
  const { organizations, selectedOrganization, selectOrganization, refreshOrganizations } = useApp();
  const [workspaces, setWorkspaces] = useState([]);
  const [slugActivo, setSlugActivo] = useState(() => localStorage.getItem(CLAVE_GUARDADA) || null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const cargar = useCallback(async () => {
    if (!authService.isAuthenticated()) {
      setWorkspaces([]);
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      setError(null);
      const { data } = await api.getWorkspaces();
      const lista = Array.isArray(data) ? data : [];
      setWorkspaces(lista);

      // El guardado manda, salvo que ya no exista (lo sacaron del Workspace).
      const guardado = localStorage.getItem(CLAVE_GUARDADA);
      const elegido = lista.find((w) => w.slug === guardado) || lista[0] || null;
      setSlugActivo(elegido ? elegido.slug : null);
      if (elegido) localStorage.setItem(CLAVE_GUARDADA, elegido.slug);
      else localStorage.removeItem(CLAVE_GUARDADA);
    } catch (e) {
      setError(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar]);

  useEffect(() => {
    const alEntrar = () => cargar();
    window.addEventListener('auth-login', alEntrar);
    return () => window.removeEventListener('auth-login', alEntrar);
  }, [cargar]);

  // ── El Espacio activo ────────────────────────────────────────────────────
  // Es el "estoy trabajando en Finanzas" del chat: acota los agentes que se
  // ofrecen y a que Espacio quedan las conversaciones nuevas. `null` = sin
  // Espacio, se ve todo lo que la persona alcanza.
  const [espacios, setEspacios] = useState([]);
  const [espacioSlug, setEspacioSlug] = useState(null);

  const cargarEspacios = useCallback(async () => {
    if (!slugActivo) { setEspacios([]); return; }
    try {
      const { data } = await api.getSpaces(slugActivo);
      setEspacios(data);
      // El guardado solo vale si sigue existiendo y sigue siendo visible.
      const guardado = localStorage.getItem(`${CLAVE_ESPACIO}:${slugActivo}`);
      setEspacioSlug(data.some((e) => e.slug === guardado) ? guardado : null);
    } catch {
      setEspacios([]);
    }
  }, [slugActivo]);

  useEffect(() => { cargarEspacios(); }, [cargarEspacios]);

  const seleccionarEspacio = (slug) => {
    setEspacioSlug(slug);
    if (!slugActivo) return;
    if (slug) localStorage.setItem(`${CLAVE_ESPACIO}:${slugActivo}`, slug);
    else localStorage.removeItem(`${CLAVE_ESPACIO}:${slugActivo}`);
  };

  const seleccionar = (slug) => {
    setSlugActivo(slug);
    if (slug) localStorage.setItem(CLAVE_GUARDADA, slug);
    else localStorage.removeItem(CLAVE_GUARDADA);
  };

  const workspace = workspaces.find((w) => w.slug === slugActivo) || null;
  const espacio = espacios.find((e) => e.slug === espacioSlug) || null;
  const rol = workspace ? workspace.my_role : null;

  // Puente con la app anterior: Contexto, Documentos y Automatizaciones consultan
  // por Organization (AppContext.selectedOrganization). Cada Workspace tiene la
  // suya enlazada, asi que al cambiar de Workspace se apunta a la que corresponde
  // y esas pantallas siguen funcionando sin tocarlas. Cuando ya no quede ninguna
  // pantalla consultando por Organization, este efecto se borra.
  //
  // Si la enlazada no esta en la lista (recien se creo el Workspace, o es de otro
  // dueño) se pide UNA recarga por id: sin ese tope el efecto quedaria girando.
  const recargasPedidas = useRef(new Set());

  useEffect(() => {
    const orgId = workspace?.organization_id;
    if (!orgId || selectedOrganization?.id === orgId) return;

    const org = organizations.find((o) => o.id === orgId);
    if (org) {
      selectOrganization(org);
      return;
    }
    if (!recargasPedidas.current.has(orgId)) {
      recargasPedidas.current.add(orgId);
      refreshOrganizations();
    }
  }, [workspace, organizations, selectedOrganization, selectOrganization, refreshOrganizations]);

  return (
    <WorkspaceContext.Provider
      value={{
        workspaces,
        workspace,
        slug: workspace ? workspace.slug : null,
        rol,
        esAdmin: rol === 'admin',
        esEditor: rol === 'admin' || rol === 'editor',
        seleccionar,
        espacios,
        espacio,
        espacioSlug: espacio ? espacio.slug : null,
        seleccionarEspacio,
        recargarEspacios: cargarEspacios,
        recargar: cargar,
        loading,
        error,
      }}
    >
      {children}
    </WorkspaceContext.Provider>
  );
};
