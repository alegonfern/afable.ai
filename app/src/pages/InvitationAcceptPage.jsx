import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Box, Button, CircularProgress, Typography, useTheme } from '@mui/material';
import { AlertCircle, Users } from 'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../services/api';
import { authService } from '../services/auth';
import { useWorkspace } from '../context/WorkspaceContext';
import { Logo } from '../components/Logo';

const DISPLAY = `'Sora', 'Inter', sans-serif`;

/**
 * Aceptar una invitacion a un Workspace.
 *
 * Publica: quien llega todavia no tiene sesion. Muestra a que Workspace lo
 * invitan y quien lo invita, y manda a iniciar sesion o crear cuenta con
 * ?next= para volver aca solo. Aceptar exige sesion y que el correo coincida
 * con el invitado — eso lo valida el backend, no esta pantalla.
 */
export default function InvitationAcceptPage() {
  const { token } = useParams();
  const navigate = useNavigate();
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const { recargar, seleccionar } = useWorkspace();

  const textMuted = d ? 'rgba(255,255,255,0.45)' : 'rgba(0,0,0,0.45)';
  const borde = theme.palette.divider;

  const [invitacion, setInvitacion] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [aceptando, setAceptando] = useState(false);
  const [errorCarga, setErrorCarga] = useState(null);

  const autenticado = authService.isAuthenticated();
  const volverAca = encodeURIComponent(`/invitacion/${token}`);

  useEffect(() => {
    api.getInvitation(token)
      .then((r) => setInvitacion(r.data))
      .catch(() => setErrorCarga('Esta invitación no existe o el enlace está mal copiado.'))
      .finally(() => setCargando(false));
  }, [token]);

  const aceptar = useCallback(async () => {
    try {
      setAceptando(true);
      const { data } = await api.acceptInvitation(token);
      await recargar();
      seleccionar(data.workspace.slug);
      toast.success(`Ya es parte de ${data.empresa.name}.`);
      navigate('/app/admin/personas', { replace: true });
    } catch (e) {
      toast.error(e.response?.data?.detail || 'No se pudo aceptar la invitación.');
    } finally {
      setAceptando(false);
    }
  }, [token, recargar, seleccionar, navigate]);

  const Marco = ({ children }) => (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        px: 3,
        bgcolor: 'background.default',
      }}
    >
      <Box sx={{ mb: 4 }}>
        <Link to="/">
          <Logo size={26} />
        </Link>
      </Box>
      <Box
        sx={{
          width: '100%',
          maxWidth: 420,
          p: 4,
          borderRadius: '14px',
          border: `1px solid ${borde}`,
          bgcolor: 'background.paper',
          textAlign: 'center',
        }}
      >
        {children}
      </Box>
    </Box>
  );

  if (cargando) {
    return (
      <Marco>
        <CircularProgress size={24} sx={{ color: '#586AD0' }} />
      </Marco>
    );
  }

  if (errorCarga) {
    return (
      <Marco>
        <AlertCircle size={26} color="#d97706" />
        <Typography sx={{ fontFamily: DISPLAY, fontSize: '1.25rem', fontWeight: 600, mt: 2 }}>
          Enlace no válido
        </Typography>
        <Typography sx={{ color: textMuted, fontSize: '0.875rem', mt: 1 }}>{errorCarga}</Typography>
        <Button component={Link} to="/" sx={{ mt: 3, textTransform: 'none' }}>
          Ir al inicio
        </Button>
      </Marco>
    );
  }

  const vigente = invitacion.status === 'pendiente';

  if (!vigente) {
    const textos = {
      aceptada: 'Esta invitación ya fue aceptada. Inicie sesión para entrar a la Empresa.',
      revocada: 'Esta invitación fue revocada por quien administra la Empresa.',
      vencida: 'Esta invitación venció. Pídale a quien administra la Empresa que la reenvíe.',
    };
    return (
      <Marco>
        <AlertCircle size={26} color="#d97706" />
        <Typography sx={{ fontFamily: DISPLAY, fontSize: '1.25rem', fontWeight: 600, mt: 2 }}>
          Invitación {invitacion.status}
        </Typography>
        <Typography sx={{ color: textMuted, fontSize: '0.875rem', mt: 1 }}>
          {textos[invitacion.status]}
        </Typography>
        <Button
          component={Link}
          to={`/login?next=${volverAca}`}
          variant="contained"
          fullWidth
          sx={{ mt: 3, borderRadius: '8px', textTransform: 'none', fontWeight: 600 }}
        >
          Iniciar sesión
        </Button>
      </Marco>
    );
  }

  return (
    <Marco>
      <Users size={24} color={textMuted} strokeWidth={1.75} />
      <Typography sx={{ fontFamily: DISPLAY, fontSize: '1.375rem', fontWeight: 600, mt: 2, letterSpacing: '-0.01em' }}>
        Invitación a {invitacion.workspace_name}
      </Typography>
      <Typography sx={{ color: textMuted, fontSize: '0.875rem', mt: 1.5, lineHeight: 1.6 }}>
        {invitacion.invited_by_name
          ? `${invitacion.invited_by_name} lo invitó a unirse`
          : 'Lo invitaron a unirse'}{' '}
        como <strong style={{ color: theme.palette.text.primary }}>{invitacion.role}</strong>, con el
        correo <strong style={{ color: theme.palette.text.primary }}>{invitacion.email}</strong>.
      </Typography>

      {autenticado ? (
        <Button
          onClick={aceptar}
          disabled={aceptando}
          variant="contained"
          fullWidth
          sx={{ mt: 3, borderRadius: '8px', textTransform: 'none', fontWeight: 600 }}
        >
          {aceptando ? 'Entrando…' : 'Aceptar invitación'}
        </Button>
      ) : (
        <>
          <Typography sx={{ color: textMuted, fontSize: '0.8125rem', mt: 2.5 }}>
            Para aceptarla, entre con la cuenta de ese correo.
          </Typography>
          <Button
            component={Link}
            to={`/login?next=${volverAca}`}
            variant="contained"
            fullWidth
            sx={{ mt: 2, borderRadius: '8px', textTransform: 'none', fontWeight: 600 }}
          >
            Iniciar sesión
          </Button>
          <Button
            component={Link}
            to={`/register?next=${volverAca}`}
            fullWidth
            sx={{ mt: 1, borderRadius: '8px', textTransform: 'none', fontWeight: 500, color: textMuted }}
          >
            No tengo cuenta — crear una
          </Button>
        </>
      )}
    </Marco>
  );
}
