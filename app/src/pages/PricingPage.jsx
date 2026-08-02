import { useState, useEffect } from 'react';
import {
  Box, Typography, Card, CardContent, Button, Chip,
  CircularProgress, Alert, useTheme,
} from '@mui/material';
import { Check } from 'lucide-react';
import { getSubscription, createCheckout } from '../services/payments';

const PLANS = [
  {
    id: 'afable_starter_monthly',
    name: 'Starter',
    price: '$99.000',
    period: '/ mes',
    desc: 'Para equipos que están empezando a automatizar.',
    features: [
      '3 agentes activos',
      '10 conexiones',
      '5.000 consultas/mes',
      'Canvas multi-ventana',
      'Tablero ejecutivo',
      'Soporte por email',
    ],
    featured: false,
    amount: 99000,
  },
  {
    id: 'afable_growth_monthly',
    name: 'Growth',
    price: '$299.000',
    period: '/ mes',
    desc: 'Para operaciones en crecimiento que necesitan escala.',
    features: [
      'Agentes ilimitados',
      '50 conexiones',
      '50.000 consultas/mes',
      'Todo en Starter',
      'Gestión de equipos y roles',
      'Documentos IA',
      'Soporte prioritario',
    ],
    featured: true,
    amount: 299000,
  },
  {
    id: 'afable_enterprise_monthly',
    name: 'Enterprise',
    price: 'Custom',
    period: '',
    desc: 'Para empresas con requerimientos específicos de escala o seguridad.',
    features: [
      'Todo en Growth',
      'Conexiones personalizadas',
      'SSO / SAML',
      'SLA garantizado',
      'Onboarding dedicado',
      'Contrato anual',
    ],
    featured: false,
    amount: 0,
    enterprise: true,
  },
];

export default function PricingPage() {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';

  const [subscription, setSubscription] = useState(null);
  const [loadingPlan, setLoadingPlan] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    getSubscription()
      .then(setSubscription)
      .catch(() => {});
  }, []);

  const handleCheckout = async (plan) => {
    if (plan.enterprise) {
      window.open('https://wa.me/56955181000', '_blank');
      return;
    }
    setLoadingPlan(plan.id);
    setError('');
    try {
      const data = await createCheckout(plan.id, `Afable ${plan.name}`, plan.amount);
      if (data.url) {
        window.location.href = data.url;
      } else {
        setError('No se pudo iniciar el pago. Intenta de nuevo.');
      }
    } catch {
      setError('Error al conectar con el procesador de pago. Intenta de nuevo.');
    } finally {
      setLoadingPlan(null);
    }
  };

  const isCurrentPlan = (planId) =>
    subscription?.plan?.id === planId && ['active', 'trial'].includes(subscription?.status);

  return (
    <Box sx={{ p: { xs: 2, md: 4 }, maxWidth: 1100, mx: 'auto' }}>
      <Box sx={{ mb: 4 }}>
        <Typography
          variant="h4"
          sx={{ fontWeight: 700, letterSpacing: '-0.03em', color: 'text.primary', mb: 0.75 }}
        >
          Planes Afable
        </Typography>
        <Typography sx={{ color: 'text.secondary', fontSize: '0.9375rem' }}>
          14 días gratis en cualquier plan. Sin tarjeta de crédito requerida.
        </Typography>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3, borderRadius: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', md: 'repeat(3, 1fr)' },
          gap: 2,
          alignItems: 'start',
        }}
      >
        {PLANS.map((plan) => {
          const current = isCurrentPlan(plan.id);
          const loading = loadingPlan === plan.id;

          return (
            <Card
              key={plan.id}
              elevation={0}
              sx={{
                border: plan.featured
                  ? '2px solid #586AD0'
                  : `1px solid ${theme.palette.divider}`,
                borderRadius: 3,
                bgcolor: 'background.paper',
                position: 'relative',
                transition: 'box-shadow 0.15s',
                '&:hover': {
                  boxShadow: plan.featured
                    ? '0 0 0 4px rgba(88, 106, 208,0.12)'
                    : theme.shadows[2],
                },
              }}
            >
              {plan.featured && (
                <Box sx={{ position: 'absolute', top: -1, left: 20 }}>
                  <Chip
                    label="Más popular"
                    size="small"
                    sx={{
                      bgcolor: '#586AD0',
                      color: '#fff',
                      fontSize: '0.6875rem',
                      fontWeight: 600,
                      height: 22,
                      borderRadius: '0 0 6px 6px',
                    }}
                  />
                </Box>
              )}

              <CardContent sx={{ p: 3, pt: plan.featured ? 4 : 3 }}>
                {current && (
                  <Chip
                    label="Tu plan actual"
                    size="small"
                    sx={{
                      bgcolor: d ? 'rgba(88, 106, 208,0.18)' : 'rgba(88, 106, 208,0.1)',
                      color: '#586AD0',
                      fontSize: '0.6875rem',
                      fontWeight: 600,
                      mb: 1.5,
                    }}
                  />
                )}

                <Typography
                  sx={{
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    letterSpacing: '0.08em',
                    textTransform: 'uppercase',
                    color: 'text.secondary',
                    mb: 1,
                  }}
                >
                  {plan.name}
                </Typography>

                <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 0.5, mb: 1 }}>
                  <Typography
                    sx={{
                      fontSize: plan.price === 'Custom' ? '1.75rem' : '2rem',
                      fontWeight: 700,
                      letterSpacing: '-0.03em',
                      color: plan.featured ? '#586AD0' : 'text.primary',
                    }}
                  >
                    {plan.price}
                  </Typography>
                  {plan.period && (
                    <Typography sx={{ fontSize: '0.875rem', color: 'text.secondary' }}>
                      {plan.period}
                    </Typography>
                  )}
                </Box>

                <Typography sx={{ fontSize: '0.8125rem', color: 'text.secondary', mb: 2.5, lineHeight: 1.5 }}>
                  {plan.desc}
                </Typography>

                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, mb: 3 }}>
                  {plan.features.map((f) => (
                    <Box key={f} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Check size={14} color="#586AD0" style={{ flexShrink: 0 }} />
                      <Typography sx={{ fontSize: '0.8125rem', color: 'text.secondary' }}>{f}</Typography>
                    </Box>
                  ))}
                </Box>

                <Button
                  fullWidth
                  variant={plan.featured ? 'contained' : 'outlined'}
                  disabled={current || loading}
                  onClick={() => handleCheckout(plan)}
                  sx={
                    plan.featured
                      ? {
                          bgcolor: '#586AD0',
                          '&:hover': { bgcolor: '#2F42A6' },
                          '&:disabled': { bgcolor: d ? 'rgba(88, 106, 208,0.3)' : 'rgba(88, 106, 208,0.4)', color: '#fff' },
                          borderRadius: 2,
                          py: 1.25,
                          fontWeight: 600,
                          fontSize: '0.875rem',
                        }
                      : {
                          borderColor: current ? '#586AD0' : 'divider',
                          color: current ? '#586AD0' : 'text.secondary',
                          '&:hover': { borderColor: 'text.secondary', color: 'text.primary', bgcolor: 'action.hover' },
                          borderRadius: 2,
                          py: 1.25,
                          fontWeight: 500,
                          fontSize: '0.875rem',
                        }
                  }
                >
                  {loading ? (
                    <CircularProgress size={18} sx={{ color: '#fff' }} />
                  ) : current ? (
                    'Plan actual'
                  ) : plan.enterprise ? (
                    'Hablar con ventas'
                  ) : (
                    'Suscribirse'
                  )}
                </Button>
              </CardContent>
            </Card>
          );
        })}
      </Box>

      <Typography
        sx={{ mt: 4, fontSize: '0.8125rem', color: 'text.secondary', textAlign: 'center', opacity: 0.6 }}
      >
        Pagos procesados de forma segura por Flow · Webpay · Transbank
      </Typography>
    </Box>
  );
}
