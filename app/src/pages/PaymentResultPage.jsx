import { Box, Typography, Button } from '@mui/material';
import { CheckCircle, XCircle } from 'lucide-react';
import { useNavigate, useSearchParams } from 'react-router-dom';

export default function PaymentResultPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const success = params.get('status') === 'success';

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: 'calc(100vh - 52px)',
        textAlign: 'center',
        gap: 2.5,
        px: 3,
      }}
    >
      {success ? (
        <CheckCircle size={52} color="#4ade80" strokeWidth={1.5} />
      ) : (
        <XCircle size={52} color="#f87171" strokeWidth={1.5} />
      )}

      <Box>
        <Typography
          variant="h5"
          sx={{ fontWeight: 700, letterSpacing: '-0.02em', color: 'text.primary', mb: 1 }}
        >
          {success ? '¡Pago exitoso!' : 'El pago no pudo completarse'}
        </Typography>
        <Typography sx={{ color: 'text.secondary', fontSize: '0.9375rem', maxWidth: 360, lineHeight: 1.65 }}>
          {success
            ? 'Tu plan ya está activo. Puedes comenzar a usar todas las funcionalidades de Afable.'
            : 'Hubo un problema al procesar tu pago. Puedes intentarlo de nuevo cuando quieras.'}
        </Typography>
      </Box>

      <Button
        variant={success ? 'contained' : 'outlined'}
        onClick={() => navigate(success ? '/app' : '/app/precios')}
        sx={
          success
            ? { bgcolor: '#586AD0', '&:hover': { bgcolor: '#2F42A6' }, px: 3, py: 1.25, borderRadius: 2, fontWeight: 600 }
            : { borderColor: 'divider', color: 'text.secondary', '&:hover': { borderColor: 'text.primary', color: 'text.primary' }, px: 3, py: 1.25, borderRadius: 2 }
        }
      >
        {success ? 'Ir al dashboard' : 'Intentar de nuevo'}
      </Button>
    </Box>
  );
}
