import React, { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { Visibility, VisibilityOff, CheckCircle } from '@mui/icons-material';
import { toast } from 'react-toastify';
import { api } from '../services/api';
import { Logo } from '../components/Logo';
import './AuthPages.css';

export default function Register() {
  const navigate = useNavigate();
  const location = useLocation();  // arrastra el ?next= del link de invitacion
  const [showPassword, setShowPassword] = useState(false);
  const [success, setSuccess] = useState(false);

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm({
    defaultValues: { first_name: '', last_name: '', email: '', username: '', password: '' },
  });

  const registerMutation = useMutation({
    mutationFn: api.register,
    onSuccess: () => {
      setSuccess(true);
    },
    onError: (error) => {
      const data = error.response?.data;
      const msg =
        data?.email?.[0] ||
        data?.username?.[0] ||
        data?.detail ||
        'Error al crear la cuenta. Inténtalo de nuevo.';
      toast.error(msg);
    },
  });

  const onSubmit = (data) => registerMutation.mutate(data);

  if (success) {
    return (
      <div className="auth-page">
        <div className="auth-card auth-success">
          <div className="auth-success-icon">
            <CheckCircle fontSize="large" />
          </div>
          <h2>¡Cuenta creada!</h2>
          <p>Revisa tu correo electrónico para activar tu cuenta y comenzar a usar Afable.</p>
          <Link className="auth-strong-link" to={`/login${location.search}`}>Ir a iniciar sesión →</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <Link to="/" className="auth-brand">
          <Logo size={24} />
        </Link>

        <h1 className="auth-title">
          Crea tu <span className="accent">cuenta.</span>
        </h1>
        <p className="auth-subtitle">
          Empieza a automatizar tu operación con agentes de IA en minutos.
        </p>

        <form className="auth-form" onSubmit={handleSubmit(onSubmit)} noValidate>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
            <div>
              <label className="auth-label" htmlFor="first_name">Nombre</label>
              <div className="auth-input-wrap">
                <input
                  id="first_name"
                  className="auth-input"
                  type="text"
                  placeholder="Tu nombre"
                  {...register('first_name', { required: 'Requerido' })}
                />
              </div>
              {errors.first_name && <p className="auth-error">{errors.first_name.message}</p>}
            </div>
            <div>
              <label className="auth-label" htmlFor="last_name">Apellido</label>
              <div className="auth-input-wrap">
                <input
                  id="last_name"
                  className="auth-input"
                  type="text"
                  placeholder="Tu apellido"
                  {...register('last_name', { required: 'Requerido' })}
                />
              </div>
              {errors.last_name && <p className="auth-error">{errors.last_name.message}</p>}
            </div>
          </div>

          <div>
            <label className="auth-label" htmlFor="email">Correo electrónico</label>
            <div className="auth-input-wrap">
              <input
                id="email"
                className="auth-input"
                type="email"
                placeholder="nombre@empresa.com"
                autoComplete="email"
                {...register('email', {
                  required: 'El correo es requerido',
                  pattern: { value: /^[^\s@]+@[^\s@]+\.[^\s@]+$/, message: 'Correo inválido' },
                })}
              />
            </div>
            {errors.email && <p className="auth-error">{errors.email.message}</p>}
          </div>

          <div>
            <label className="auth-label" htmlFor="username">Nombre de usuario</label>
            <div className="auth-input-wrap">
              <input
                id="username"
                className="auth-input"
                type="text"
                placeholder="usuario_único"
                autoComplete="username"
                {...register('username', {
                  required: 'El usuario es requerido',
                  minLength: { value: 3, message: 'Mínimo 3 caracteres' },
                  pattern: { value: /^[a-zA-Z0-9_.-]+$/, message: 'Solo letras, números, _ . -' },
                })}
              />
            </div>
            {errors.username && <p className="auth-error">{errors.username.message}</p>}
          </div>

          <div>
            <label className="auth-label" htmlFor="password">Contraseña</label>
            <div className="auth-input-wrap">
              <input
                id="password"
                className="auth-input has-toggle"
                type={showPassword ? 'text' : 'password'}
                placeholder="Mínimo 8 caracteres"
                autoComplete="new-password"
                {...register('password', {
                  required: 'La contraseña es requerida',
                  minLength: { value: 8, message: 'Mínimo 8 caracteres' },
                })}
              />
              <button
                type="button"
                className="auth-toggle"
                onClick={() => setShowPassword((p) => !p)}
                aria-label={showPassword ? 'Ocultar' : 'Mostrar'}
              >
                {showPassword ? <VisibilityOff fontSize="small" /> : <Visibility fontSize="small" />}
              </button>
            </div>
            {errors.password && <p className="auth-error">{errors.password.message}</p>}
          </div>

          <button
            className="auth-btn-primary"
            type="submit"
            disabled={registerMutation.isPending}
          >
            {registerMutation.isPending ? 'Creando cuenta…' : 'Crear cuenta'}
          </button>
        </form>

        <p className="auth-foot">
          ¿Ya tienes cuenta? <Link className="auth-link" to={`/login${location.search}`}>Inicia sesión</Link>
        </p>
      </div>
    </div>
  );
}
