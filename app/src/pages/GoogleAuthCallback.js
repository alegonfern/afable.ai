import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'react-toastify';
import { authService } from '../services/auth';

// Destino del redirect de GoogleLoginCallbackView (backend): trae los tokens
// en el hash (#access=...&refresh=...) para que nunca lleguen a un log de servidor.
export default function GoogleAuthCallback() {
  const navigate = useNavigate();

  useEffect(() => {
    const params = new URLSearchParams(window.location.hash.slice(1));
    const access = params.get('access');
    const refresh = params.get('refresh');
    if (access && refresh) {
      authService.login(access, refresh, true);
      window.dispatchEvent(new Event('auth-login'));
      toast.success('¡Bienvenido a Afable!');
      navigate('/app', { replace: true });
    } else {
      toast.error('No se pudo iniciar sesión con Google.');
      navigate('/login', { replace: true });
    }
  }, [navigate]);

  return null;
}
