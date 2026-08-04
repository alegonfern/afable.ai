import { Box, Typography, Button } from '@mui/material';
import { Bot, ArrowRight, Plug } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export default function DashboardHome() {
  const navigate = useNavigate();

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
      <Box
        sx={{
          width: 56,
          height: 56,
          borderRadius: '12px',
          background: 'rgba(88, 106, 208,0.12)',
          border: '1px solid rgba(88, 106, 208,0.2)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <Bot size={26} color="#586AD0" />
      </Box>

      <Box>
        <Typography
          variant="h3"
          sx={{
            fontWeight: 600,
            color: 'text.primary',
            letterSpacing: '-0.02em',
            mb: 0.75,
          }}
        >
          Bienvenido a <span style={{ color: '#586AD0' }}>Afable</span>
        </Typography>
        <Typography
          sx={{
            color: 'text.secondary',
            fontSize: '0.9375rem',
            maxWidth: 400,
            lineHeight: 1.65,
          }}
        >
          Tu espacio de trabajo está listo. Crea tu primer agente o conecta un sistema para comenzar.
        </Typography>
      </Box>

      <Box sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap', justifyContent: 'center', mt: 0.5 }}>
        <Button
          variant="contained"
          endIcon={<ArrowRight size={15} />}
          onClick={() => navigate('/app/agentes/nuevo')}
          sx={{
            background: '#586AD0',
            '&:hover': { background: '#2F42A6' },
            px: 2.5,
            py: 1,
            fontSize: '0.875rem',
          }}
        >
          Crear agente
        </Button>
        <Button
          variant="outlined"
          startIcon={<Plug size={15} />}
          onClick={() => navigate('/app/contexto?tab=integraciones')}
          sx={{
            borderColor: 'divider',
            color: 'text.secondary',
            '&:hover': {
              borderColor: 'text.secondary',
              color: 'text.primary',
              bgcolor: 'action.hover',
            },
            px: 2.5,
            py: 1,
            fontSize: '0.875rem',
          }}
        >
          Ver conexiones
        </Button>
      </Box>
    </Box>
  );
}
