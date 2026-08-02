import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { MailOutline } from '@mui/icons-material';
import { toast } from 'react-toastify';
import { api } from '../services/api';
import { Logo } from '../components/Logo';
import './AuthPages.css';

export default function ForgotPassword() {
  const [emailSent, setEmailSent] = useState(false);
  const [sentTo, setSentTo] = useState('');

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm({ defaultValues: { email: '' } });

  const resetMutation = useMutation({
    mutationFn: api.requestPasswordReset,
    onSuccess: (_, variables) => {
      setSentTo(variables.email);
      setEmailSent(true);
    },
    onError: (error) => {
      toast.error(
        error.response?.data?.detail ||
          error.response?.data?.email?.[0] ||
          'Error al enviar el correo. Inténtalo de nuevo.'
      );
    },
  });

  const onSubmit = (data) => resetMutation.mutate(data);

  if (emailSent) {
    return (
      <div className="auth-page">
        <div className="auth-card auth-success">
          <div className="auth-success-icon">
            <MailOutline fontSize="large" />
          </div>
          <h2>Revisa tu correo</h2>
          <p>
            Enviamos un enlace de recuperación a <strong style={{ color: '#9BA6E3' }}>{sentTo}</strong>.
            Puede tardar unos minutos.
          </p>
          <Link className="auth-strong-link" to="/login">← Volver a iniciar sesión</Link>
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
          Recupera tu <span className="accent">acceso.</span>
        </h1>
        <p className="auth-subtitle">
          Ingresa tu correo y te enviaremos un enlace para restablecer tu contraseña.
        </p>

        <form className="auth-form" onSubmit={handleSubmit(onSubmit)} noValidate>
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

          <button
            className="auth-btn-primary"
            type="submit"
            disabled={resetMutation.isPending}
          >
            {resetMutation.isPending ? 'Enviando…' : 'Enviar enlace de recuperación'}
          </button>
        </form>

        <p className="auth-foot">
          <Link className="auth-link" to="/login">← Volver a iniciar sesión</Link>
        </p>
      </div>
    </div>
  );
}
