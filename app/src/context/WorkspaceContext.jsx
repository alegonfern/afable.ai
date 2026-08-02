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

  const seleccionar = (slug) => {
    setSlugActivo(slug);
    if (slug) localStorage.setItem(CLAVE_GUARDADA, slug);
    else localStorage.removeItem(CLAVE_GUARDADA);
  };

  const workspace = workspaces.find((w) => w.slug === slugActivo) || null;
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
        recargar: cargar,
        loading,
        error,
      }}
    >
      {children}
    </WorkspaceContext.Provider>
  );
};
