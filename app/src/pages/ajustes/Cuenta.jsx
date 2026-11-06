import { useEffect, useMemo, useRef, useState } from 'react';
import { Avatar, Box, Button, CircularProgress, IconButton, InputAdornment, TextField, Typography } from '@mui/material';
import { BarChart2, Camera, Eye, EyeOff, Moon, Sun, Wrench, Zap } from 'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../../services/api';
import { useThemeMode } from '../../context/ThemeContext';
import { BotonGuardar, Cargando, Pagina, Tarjeta, campoSx } from './piezas';

/*
 * Configuración › Mi cuenta (28-10-2026): lo de la persona, igual en todas sus empresas.
 *   Perfil        nombre, foto, contacto y su trabajo.
 *   Preferencias  la apariencia y cómo le responde Afable.
 *   Seguridad     la contraseña.
 * Reemplaza a pages/ProfilePage y pages/SettingsPage dentro de Configuración.
 */

const ROLES = [
  'Dueño de empresa', 'Gerente General', 'Gerente Financiero', 'Gerente Comercial', 'Gerente de Operaciones',
  'Contador / Controller', 'Jefe de TI / CTO', 'Analista de Datos', 'Jefe de RRHH', 'Otro',
];

const ESTILOS = [
  { value: 'ejecutivo', icono: Zap, label: 'Ejecutivo', desc: 'Directo al grano, en puntos.' },
  { value: 'analitico', icono: BarChart2, label: 'Analítico', desc: 'Completo, con cifras y tendencias.' },
  { value: 'tecnico', icono: Wrench, label: 'Técnico', desc: 'Con la terminología del rubro.' },
];

const CONTEXTO = [
  { key: 'about_me', label: 'Sobre su trabajo', placeholder: 'Ej: superviso producción, compras y despachos día a día.' },
  { key: 'priorities', label: 'Sus prioridades hoy', placeholder: 'Ej: reducir el quiebre de stock y cerrar el presupuesto de julio.' },
  { key: 'custom_instructions', label: 'Cómo quiere que le responda', placeholder: 'Ej: siempre con cifras; avíseme si ve algo raro.' },
];

// Una opción elegible como tarjeta (tema, estilo de respuesta).
function Opcion({ activa, onClick, icono: Icono, titulo, desc }) {
  return (
    <Box component="button" type="button" onClick={onClick} aria-pressed={activa} sx={{
      flex: '1 1 160px', textAlign: 'left', p: 1.75, borderRadius: '10px', cursor: 'pointer', fontFamily: 'inherit',
      bgcolor: activa ? 'color-mix(in srgb, var(--af-acento) 8%, transparent)' : 'transparent', color: 'text.primary',
      border: '1px solid', borderColor: activa ? 'var(--af-acento)' : 'divider',
      boxShadow: activa ? '0 0 0 1px var(--af-acento)' : 'none', transition: 'border-color .12s, background .12s',
      '&:hover': { borderColor: activa ? 'var(--af-acento)' : 'text.disabled' },
    }}>
      <Box sx={{ color: activa ? 'var(--af-acento)' : 'text.secondary', display: 'flex', mb: 0.75 }}><Icono size={17} /></Box>
      <Typography sx={{ fontSize: '0.875rem', fontWeight: 600 }}>{titulo}</Typography>
      {desc && <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary', mt: 0.25, lineHeight: 1.45 }}>{desc}</Typography>}
    </Box>
  );
}

function useUsuario() {
  const [usuario, setUsuario] = useState(null);
  useEffect(() => { api.getCurrentUser().then((r) => setUsuario(r.data)).catch(() => setUsuario({})); }, []);
  return [usuario, setUsuario];
}

export function Perfil() {
  const [usuario, setUsuario] = useUsuario();
  const [form, setForm] = useState(null);
  const [guardando, setGuardando] = useState(false);
  const [subiendo, setSubiendo] = useState(false);
  const archivo = useRef();

  const inicial = useMemo(() => {
    if (!usuario) return null;
    const conocido = ROLES.slice(0, -1).includes(usuario.role);
    return {
      first_name: usuario.first_name || '', last_name: usuario.last_name || '', telefono: usuario.telefono || '',
      department: usuario.department || '', rol: usuario.role ? (conocido ? usuario.role : 'Otro') : '',
      otroRol: usuario.role && !conocido ? usuario.role : '',
    };
  }, [usuario]);
  useEffect(() => setForm(inicial), [inicial]);
  if (!form) return <Pagina titulo="Perfil"><Cargando /></Pagina>;

  // Cada tarjeta guarda lo suyo: su botón se enciende solo con cambios en sus campos.
  const cambiosEn = (claves) => claves.some((k) => form[k] !== inicial[k]);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const guardar = async () => {
    setGuardando(true);
    try {
      const { data } = await api.updateProfile({
        first_name: form.first_name.trim(), last_name: form.last_name.trim(), telefono: form.telefono, department: form.department.trim(),
        role: form.rol === 'Otro' ? form.otroRol.trim() : form.rol,
      });
      setUsuario((u) => ({ ...u, ...data }));
      toast.success('Perfil guardado.');
    } catch { toast.error('No se pudo guardar el perfil.'); } finally { setGuardando(false); }
  };
  const subirFoto = async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setSubiendo(true);
    try {
      const fd = new FormData();
      fd.append('avatar', f);
      const { data } = await api.uploadAvatar(fd);
      setUsuario((u) => ({ ...u, avatar_url: data.avatar_url }));
      toast.success('Foto actualizada.');
    } catch { toast.error('No se pudo subir la foto.'); } finally { setSubiendo(false); }
  };
  const iniciales = `${form.first_name[0] || ''}${form.last_name[0] || ''}`.toUpperCase() || (usuario.email || '?')[0].toUpperCase();

  return (
    <Pagina titulo="Perfil" descripcion="Cómo lo ven en Afable sus equipos y cómo lo conoce el asistente. Es el mismo en todas sus empresas.">
      <Tarjeta titulo="Sus datos" pie="El correo es con el que entra a Afable; no se puede cambiar."
        accion={<BotonGuardar guardando={guardando} cambios={cambiosEn(['first_name', 'last_name', 'telefono'])} onClick={guardar} />}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2.5 }}>
          <Avatar src={usuario.avatar_url} sx={{ width: 64, height: 64, bgcolor: 'var(--af-acento)', fontSize: '1.3rem', fontWeight: 700 }}>
            {!usuario.avatar_url && iniciales}
          </Avatar>
          <Button variant="outlined" size="small" disabled={subiendo} onClick={() => archivo.current?.click()}
            startIcon={subiendo ? <CircularProgress size={13} /> : <Camera size={14} />}
            sx={{ borderRadius: '8px', textTransform: 'none', fontWeight: 600 }}>
            {usuario.avatar_url ? 'Cambiar foto' : 'Subir foto'}
          </Button>
          <input ref={archivo} type="file" accept="image/*" hidden onChange={subirFoto} />
        </Box>
        <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' } }}>
          <TextField label="Nombre" value={form.first_name} onChange={set('first_name')} size="small" sx={campoSx} />
          <TextField label="Apellido" value={form.last_name} onChange={set('last_name')} size="small" sx={campoSx} />
          <TextField label="Correo" value={usuario.email || ''} disabled size="small" sx={campoSx} />
          <TextField label="WhatsApp" value={form.telefono} placeholder="+56 9 1234 5678" size="small" sx={campoSx}
            onChange={(e) => setForm({ ...form, telefono: e.target.value.replace(/[^\d+ ]/g, '').slice(0, 20) })}
            helperText="Para recibir los avisos de las automatizaciones que siga." />
        </Box>
      </Tarjeta>

      <Tarjeta titulo="Su trabajo" descripcion="Con su cargo, Afable ajusta lo que le muestra y cómo se lo explica."
        pie="El asistente lo considera en cada conversación."
        accion={<BotonGuardar guardando={guardando} cambios={cambiosEn(['rol', 'otroRol', 'department'])} onClick={guardar} />}>
        <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary', mb: 1 }}>Cargo</Typography>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75, mb: 2 }}>
          {ROLES.map((r) => {
            const activo = form.rol === r;
            return (
              <Box key={r} component="button" type="button" onClick={() => setForm({ ...form, rol: r })} aria-pressed={activo} sx={{
                px: 1.4, py: 0.55, borderRadius: '999px', cursor: 'pointer', fontFamily: 'inherit', fontSize: '0.8rem',
                border: '1px solid', borderColor: activo ? 'var(--af-acento)' : 'divider',
                bgcolor: activo ? 'color-mix(in srgb, var(--af-acento) 10%, transparent)' : 'transparent',
                color: activo ? 'var(--af-acento)' : 'text.secondary', fontWeight: activo ? 600 : 400,
                '&:hover': { color: 'text.primary', borderColor: activo ? 'var(--af-acento)' : 'text.disabled' },
              }}>{r}</Box>
            );
          })}
        </Box>
        <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' } }}>
          {form.rol === 'Otro' && <TextField label="Su cargo" value={form.otroRol} onChange={set('otroRol')} size="small" sx={campoSx} />}
          <TextField label="Área" value={form.department} onChange={set('department')} placeholder="Ej: Finanzas, Comercial" size="small" sx={campoSx} />
        </Box>
      </Tarjeta>
    </Pagina>
  );
}

export function Preferencias() {
  const { mode, toggleMode } = useThemeMode();
  const [usuario, setUsuario] = useUsuario();
  const [estilo, setEstilo] = useState(null);
  const [objetivos, setObjetivos] = useState('');
  const [contexto, setContexto] = useState(null);
  const [original, setOriginal] = useState(null);
  const [guardando, setGuardando] = useState(false);

  useEffect(() => {
    if (!usuario) return;
    api.getUserContext().catch(() => ({ data: {} })).then(({ data }) => {
      const ctx = Object.fromEntries(CONTEXTO.map((c) => [c.key, data[c.key] || '']));
      const est = usuario.response_style || 'ejecutivo';
      setContexto(ctx); setEstilo(est); setObjetivos(usuario.objectives || '');
      setOriginal(JSON.stringify({ ctx, est, obj: usuario.objectives || '' }));
    });
  }, [usuario]);

  const cambios = contexto && original !== JSON.stringify({ ctx: contexto, est: estilo, obj: objetivos });
  const guardar = async () => {
    setGuardando(true);
    try {
      const [{ data }] = await Promise.all([
        api.updateProfile({ response_style: estilo, objectives: objetivos }),
        api.updateUserContext(contexto),
      ]);
      setUsuario((u) => ({ ...u, ...data }));
      toast.success('Listo: Afable lo tendrá en cuenta desde su próxima pregunta.');
    } catch { toast.error('No se pudo guardar.'); } finally { setGuardando(false); }
  };

  return (
    <Pagina titulo="Preferencias" descripcion="Cómo se ve Afable y cómo le responde. Solo cambia para usted.">
      <Tarjeta titulo="Apariencia" descripcion="El tema se guarda en este navegador.">
        <Box sx={{ display: 'flex', gap: 1.25, flexWrap: 'wrap' }}>
          <Opcion activa={mode === 'light'} onClick={() => mode !== 'light' && toggleMode()} icono={Sun} titulo="Claro" desc="Fondo blanco, ideal de día." />
          <Opcion activa={mode === 'dark'} onClick={() => mode !== 'dark' && toggleMode()} icono={Moon} titulo="Oscuro" desc="Descansa la vista de noche." />
        </Box>
      </Tarjeta>

      <Tarjeta titulo="Cómo le responde Afable"
        descripcion="Se suma al contexto de la empresa en cada respuesta, solo en sus conversaciones."
        pie="Los agentes de cada módulo también lo usan."
        accion={contexto && <BotonGuardar guardando={guardando} cambios={cambios} onClick={guardar} />}>
        {!contexto ? <Cargando /> : (
          <>
            <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary', mb: 1 }}>Estilo</Typography>
            <Box sx={{ display: 'flex', gap: 1.25, flexWrap: 'wrap', mb: 2.5 }}>
              {ESTILOS.map((s) => <Opcion key={s.value} activa={estilo === s.value} onClick={() => setEstilo(s.value)} icono={s.icono} titulo={s.label} desc={s.desc} />)}
            </Box>
            <Box sx={{ display: 'grid', gap: 2 }}>
              <TextField label="Qué quiere lograr con Afable" value={objetivos} onChange={(e) => setObjetivos(e.target.value.slice(0, 300))}
                placeholder="Ej: tener los números del mes sin esperar al contador." multiline minRows={2} size="small" sx={campoSx}
                helperText={`${objetivos.length}/300`} FormHelperTextProps={{ sx: { textAlign: 'right', mx: 0 } }} />
              {CONTEXTO.map((c) => (
                <TextField key={c.key} label={c.label} value={contexto[c.key]} placeholder={c.placeholder} multiline minRows={2} size="small" sx={campoSx}
                  onChange={(e) => setContexto({ ...contexto, [c.key]: e.target.value.slice(0, 500) })}
                  helperText={`${contexto[c.key].length}/500`} FormHelperTextProps={{ sx: { textAlign: 'right', mx: 0 } }} />
              ))}
            </Box>
          </>
        )}
      </Tarjeta>
    </Pagina>
  );
}

function CampoClave({ label, value, onChange, error, helperText, autoComplete }) {
  const [ver, setVer] = useState(false);
  return (
    <TextField label={label} type={ver ? 'text' : 'password'} value={value} onChange={onChange} size="small" fullWidth sx={campoSx}
      error={error} helperText={helperText} autoComplete={autoComplete}
      InputProps={{ endAdornment: (
        <InputAdornment position="end">
          <IconButton size="small" onClick={() => setVer((v) => !v)} aria-label={ver ? 'Ocultar' : 'Mostrar'} edge="end">
            {ver ? <EyeOff size={15} /> : <Eye size={15} />}
          </IconButton>
        </InputAdornment>
      ) }} />
  );
}

export function Seguridad() {
  const [actual, setActual] = useState('');
  const [nueva, setNueva] = useState('');
  const [repetida, setRepetida] = useState('');
  const [guardando, setGuardando] = useState(false);
  const corta = nueva.length > 0 && nueva.length < 8;
  const distinta = repetida.length > 0 && nueva !== repetida;
  const lista = actual && nueva.length >= 8 && nueva === repetida;

  const guardar = async () => {
    setGuardando(true);
    try {
      await api.changePassword({ current_password: actual, new_password: nueva });
      toast.success('Contraseña actualizada.');
      setActual(''); setNueva(''); setRepetida('');
    } catch (e) {
      const d = e.response?.data || {};
      toast.error(d.current_password?.[0] || d.new_password?.[0] || d.detail || 'No se pudo cambiar la contraseña.');
    } finally { setGuardando(false); }
  };

  return (
    <Pagina titulo="Seguridad" descripcion="Cómo entra a Afable.">
      <Tarjeta titulo="Contraseña" descripcion="La que usa para entrar con su correo."
        pie="Use al menos 8 caracteres; mejor si mezcla letras, números y símbolos."
        accion={<BotonGuardar guardando={guardando} cambios={lista} onClick={guardar}>Cambiar contraseña</BotonGuardar>}>
        <Box sx={{ display: 'grid', gap: 2, maxWidth: 420 }}>
          <CampoClave label="Contraseña actual" value={actual} onChange={(e) => setActual(e.target.value)} autoComplete="current-password" />
          <CampoClave label="Nueva contraseña" value={nueva} onChange={(e) => setNueva(e.target.value)} autoComplete="new-password"
            error={corta} helperText={corta ? 'Mínimo 8 caracteres.' : ' '} />
          <CampoClave label="Repita la nueva contraseña" value={repetida} onChange={(e) => setRepetida(e.target.value)} autoComplete="new-password"
            error={distinta} helperText={distinta ? 'No coincide con la nueva.' : ' '} />
        </Box>
      </Tarjeta>
    </Pagina>
  );
}
