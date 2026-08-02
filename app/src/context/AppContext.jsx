import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { api } from '../services/api';
import { authService } from '../services/auth';

const AppContext = createContext();

export const useApp = () => {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp debe usarse dentro de AppProvider');
  return ctx;
};

export const AppProvider = ({ children }) => {
  const [organizations, setOrganizations] = useState([]);
  const [selectedOrganization, setSelectedOrganization] = useState(null);
  const [currentUser, setCurrentUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [aiModel, setAiModelState] = useState(() => localStorage.getItem('afable_aiModel') || null);

  const setAiModel = (model) => {
    setAiModelState(model);
    if (model) localStorage.setItem('afable_aiModel', model);
    else localStorage.removeItem('afable_aiModel');
  };

  const loadData = useCallback(async () => {
    if (!authService.isAuthenticated()) {
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      const [orgsRes, userRes] = await Promise.all([
        api.getOrganizations(),
        api.getCurrentUser(),
      ]);

      const orgs = Array.isArray(orgsRes.data) ? orgsRes.data : orgsRes.data.results || [];
      setOrganizations(orgs);
      setCurrentUser(userRes.data);

      const savedId = localStorage.getItem('afable_selectedOrgId');
      const saved = orgs.find((o) => o.id === parseInt(savedId));
      const active = saved || orgs[0] || null;
      setSelectedOrganization(active);
      if (active) localStorage.setItem('afable_selectedOrgId', active.id);
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    const onLogin = () => loadData();
    window.addEventListener('auth-login', onLogin);
    return () => window.removeEventListener('auth-login', onLogin);
  }, [loadData]);

  const selectOrganization = (org) => {
    setSelectedOrganization(org);
    if (org) localStorage.setItem('afable_selectedOrgId', org.id);
  };

  const refreshOrganizations = () => loadData();

  return (
    <AppContext.Provider
      value={{
        organizations,
        selectedOrganization,
        selectOrganization,
        refreshOrganizations,
        currentUser,
        setCurrentUser,
        loading,
        aiModel,
        setAiModel,
      }}
    >
      {children}
    </AppContext.Provider>
  );
};
