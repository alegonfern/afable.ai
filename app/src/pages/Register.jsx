import React, { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { Visibility, VisibilityOff, CheckCircle } from '@mui/icons-material';
import { toast } from 'react-toastify';
import { api } from '../services/api';
import { authService } from '../services/auth';
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
    defaultValues: { first_name: '', last_name: '', email: '', empresa: '', password: '' },
  });

  const next = new URLSearchParams(location.search).get('next');
  // A dónde va después de registrarse. Respeta el ?next= de un link de invitación: quien
  // llega invitado a un Workspace tiene que caer ahí y no en su propia empresa vacía.
  const destino = next && next.startsWith('/') && !next.startsWith('//') ? next : '/app';

  const registerMutation = useMutation({
    mutationFn: api.register,
    onSuccess: (response) => {
      // ⭐ **Queda adentro, no en una pantalla de espera.** Antes decía "Revise su correo
      // para activar la cuenta" — y NUNCA se mandaba ese correo: la cuenta nace activa y
      // el registro ya devuelve las llaves de sesión, que la pantalla tiraba a la basura.
      // O sea que la persona se quedaba esperando algo que no existía, justo en el momento
      // en que más ganas tenía de entrar. Es el peor lugar donde perder a alguien.
      const { access, refresh } = response.data || {};
      if (access && refresh) {
        authService.login(access, refresh, true);
        window.dispatchEvent(new Event('auth-login'));
        navigate(destino, { replace: true });
        return;
      }
      // Sin llaves no se puede entrar solo, pero tampoco se inventa un correo: se manda a
      // iniciar sesión, que es lo que de verdad funciona.
      setSuccess(true);
    },
    onError: (error) => {
      const data = error.response?.data;
      const msg =
        data?.email?.[0] ||
        data?.detail ||
        'No se pudo crear la cuenta. Vuelva a intentarlo.';
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
          <p>Ya puede entrar con su correo y su contraseña.</p>
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
          Cree su <span className="accent">cuenta.</span>
        </h1>
        <p className="auth-subtitle">
          Ponga a trabajar agentes de IA sobre lo que su empresa ya tiene.
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
                  placeholder="Su nombre"
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
                  placeholder="Su apellido"
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

          {/* ⭐ El nombre de la empresa, en lugar del "nombre de usuario" que había acá.
              Ese campo era obligatorio y el backend lo DESCARTABA: se pedía un dato que no
              se guardaba en ninguna parte. Este sí se usa, y evita que la empresa nazca
              llamándose "Empresa de Rosa" — el primer nombre que ven sus colegas.
              Opcional: poner una pared en el registro cuesta más de lo que vale el dato. */}
          <div>
            <label className="auth-label" htmlFor="empresa">Nombre de su empresa</label>
            <div className="auth-input-wrap">
              <input
                id="empresa"
                className="auth-input"
                type="text"
                placeholder="Panadería del Sur"
                autoComplete="organization"
                {...register('empresa', {
                  maxLength: { value: 200, message: 'Demasiado largo' },
                })}
              />
            </div>
            <p className="auth-hint">Puede cambiarlo después. Si trabaja solo, ponga su nombre.</p>
            {errors.empresa && <p className="auth-error">{errors.empresa.message}</p>}
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
          ¿Ya tiene cuenta? <Link className="auth-link" to={`/login${location.search}`}>Inicie sesión</Link>
        </p>
      </div>
    </div>
  );
}
