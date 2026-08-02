import React, { useState, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { Visibility, VisibilityOff } from '@mui/icons-material';
import { toast } from 'react-toastify';
import { api } from '../services/api';
import { authService } from '../services/auth';
import { Logo } from '../components/Logo';
import './AuthPages.css';

export default function Login() {
  const navigate = useNavigate();
  const location = useLocation();

  // A donde ir despues de entrar. Lo usa el link de invitacion, que manda a
  // /login?next=/invitacion/<token> para volver solo. Se acepta unicamente una
  // ruta interna: un ?next= a otro sitio seria un redirect abierto.
  const next = new URLSearchParams(location.search).get('next');
  const destino = next && next.startsWith('/') && !next.startsWith('//') ? next : '/app';
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm({ defaultValues: { email: '', password: '' } });

  useEffect(() => {
    if (authService.isAuthenticated()) navigate(destino, { replace: true });
  }, [navigate, destino]);

  const loginMutation = useMutation({
    mutationFn: api.login,
    onSuccess: (response) => {
      const { access, refresh } = response.data;
      authService.login(access, refresh, rememberMe);
      window.dispatchEvent(new Event('auth-login'));
      toast.success('¡Bienvenido a Afable!');
      navigate(destino, { replace: true });
    },
    onError: (error) => {
      toast.error(
        error.response?.data?.detail || 'Credenciales incorrectas. Inténtalo de nuevo.'
      );
    },
  });

  const onSubmit = (data) => loginMutation.mutate(data);

  const handleGoogleLogin = () => {
    const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001/api/v1';
    window.location.href = `${API_URL}/auth/google/login/`;
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        {/* Brand */}
        <Link to="/" className="auth-brand">
          <Logo size={24} />
        </Link>

        <h1 className="auth-title">
          Bienvenido de <span className="accent">vuelta.</span>
        </h1>
        <p className="auth-subtitle">
          Inicia sesión para gestionar tus agentes y automatizaciones.
        </p>

        <form className="auth-form" onSubmit={handleSubmit(onSubmit)} noValidate>
          <div>
            <label className="auth-label" htmlFor="email">Correo electrónico</label>
            <div className="auth-input-wrap">
              <input
                id="email"
                className="auth-input"
                type="email"
                placeholder="tu@empresa.com"
                autoComplete="email"
                {...register('email', {
                  required: 'El correo es requerido',
                  pattern: { value: /\S+@\S+\.\S+/, message: 'Correo inválido' },
                })}
              />
            </div>
            {errors.email && <p className="auth-error">{errors.email.message}</p>}
          </div>

          <div>
            <label className="auth-label" htmlFor="password">Contraseña</label>
            <div className="auth-input-wrap">
              <input
                id="password"
                className={`auth-input has-toggle`}
                type={showPassword ? 'text' : 'password'}
                placeholder="Tu contraseña"
                autoComplete="current-password"
                {...register('password', {
                  required: 'La contraseña es requerida',
                  minLength: { value: 6, message: 'Mínimo 6 caracteres' },
                })}
              />
              <button
                type="button"
                className="auth-toggle"
                onClick={() => setShowPassword((p) => !p)}
                aria-label={showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'}
              >
                {showPassword ? <VisibilityOff fontSize="small" /> : <Visibility fontSize="small" />}
              </button>
            </div>
            {errors.password && <p className="auth-error">{errors.password.message}</p>}
          </div>

          <div className="auth-row">
            <label className="auth-check">
              <input
                type="checkbox"
                checked={rememberMe}
                onChange={(e) => setRememberMe(e.target.checked)}
              />
              Recordarme
            </label>
            <Link className="auth-link" to="/forgot-password">¿Olvidaste tu contraseña?</Link>
          </div>

          <button
            className="auth-btn-primary"
            type="submit"
            disabled={loginMutation.isPending}
          >
            {loginMutation.isPending ? 'Ingresando…' : 'Iniciar sesión'}
          </button>
        </form>

        <div className="auth-divider">o</div>

        <button className="auth-btn-google" type="button" onClick={handleGoogleLogin}>
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            <path d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.875 2.684-6.615z" fill="#4285F4"/>
            <path d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z" fill="#34A853"/>
            <path d="M3.964 10.71A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.042l3.007-2.332z" fill="#FBBC05"/>
            <path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.958L3.964 7.29C4.672 5.163 6.656 3.58 9 3.58z" fill="#EA4335"/>
          </svg>
          Continuar con Google
        </button>

        <p className="auth-foot">
          ¿No tienes cuenta? <Link className="auth-link" to={`/register${location.search}`}>Regístrate</Link>
        </p>
      </div>
    </div>
  );
}
