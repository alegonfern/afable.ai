import apiClient from './api';

export const getPlans = () =>
  apiClient.get('/payments/plans/').then(r => r.data);

export const createCheckout = (planId, subject, amount) =>
  apiClient.post('/payments/checkout/', { plan_id: planId, subject, amount }).then(r => r.data);

export const getSubscription = () =>
  apiClient.get('/payments/subscription/').then(r => r.data);

export const cancelSubscription = () =>
  apiClient.post('/payments/subscription/cancel/').then(r => r.data);
