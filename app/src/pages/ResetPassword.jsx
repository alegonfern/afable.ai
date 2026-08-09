import React, { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { Visibility, VisibilityOff } from '@mui/icons-material';
import { toast } from 'react-toastify';
import { api } from '../services/api';
import { Logo } from '../components/Logo';
import './AuthPages.css';

export default function ResetPassword() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm({ defaultValues: { password: '', confirmPassword: '' } });

  const password = watch('password');

  const resetMutation = useMutation({
    mutationFn: api.resetPassword,
    onSuccess: () => {
      toast.success('Contraseña actualizada correctamente');
      setTimeout(() => navigate('/login'), 2000);
    },
    onError: (error) => {
      toast.error(
        error.response?.data?.detail ||
          error.response?.data?.password?.[0] ||
          'Error al restablecer. El enlace puede haber expirado.'
      );
    },
  });

  const onSubmit = (data) => {
    if (!token) {
      toast.error('Enlace de recuperación inválido');
      return;
    }
    resetMutation.mutate({ token, password: data.password });
  };

  if (!token) {
    return (
      <div className="auth-page">
        <div className="auth-card auth-success">
          <h2>Enlace inválido</h2>
          <p>Este enlace de recuperación no es válido o ha expirado. Solicita uno nuevo.</p>
          <Link className="auth-strong-link" to="/forgot-password">Solicitar nuevo enlace →</Link>
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
          Nueva <span className="accent">contraseña.</span>
        </h1>
        <p className="auth-subtitle">
          Elija una contraseña segura para su cuenta de Afable.
        </p>

        <form className="auth-form" onSubmit={handleSubmit(onSubmit)} noValidate>
          <div>
            <label className="auth-label" htmlFor="password">Nueva contraseña</label>
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

          <div>
            <label className="auth-label" htmlFor="confirmPassword">Confirmar contraseña</label>
            <div className="auth-input-wrap">
              <input
                id="confirmPassword"
                className="auth-input has-toggle"
                type={showConfirm ? 'text' : 'password'}
                placeholder="Repita su contraseña"
                autoComplete="new-password"
                {...register('confirmPassword', {
                  required: 'Confirme su contraseña',
                  validate: (v) => v === password || 'Las contraseñas no coinciden',
                })}
              />
              <button
                type="button"
                className="auth-toggle"
                onClick={() => setShowConfirm((p) => !p)}
                aria-label={showConfirm ? 'Ocultar' : 'Mostrar'}
              >
                {showConfirm ? <VisibilityOff fontSize="small" /> : <Visibility fontSize="small" />}
              </button>
            </div>
            {errors.confirmPassword && <p className="auth-error">{errors.confirmPassword.message}</p>}
          </div>

          <button
            className="auth-btn-primary"
            type="submit"
            disabled={resetMutation.isPending}
          >
            {resetMutation.isPending ? 'Guardando…' : 'Establecer nueva contraseña'}
          </button>
        </form>

        <p className="auth-foot">
          <Link className="auth-link" to="/login">← Volver a iniciar sesión</Link>
        </p>
      </div>
    </div>
  );
}
