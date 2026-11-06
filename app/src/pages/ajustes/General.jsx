import { useEffect, useMemo, useState } from 'react';
import { Box, Button, MenuItem, TextField, ToggleButton, ToggleButtonGroup, Typography } from '@mui/material';
import { Check, Minus, Upload } from 'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../../services/api';
import { useWorkspace } from '../../context/WorkspaceContext';
import { MarcaWorkspace } from '../../components/SelectorWorkspace';
import DatosParaFacturar from './DatosParaFacturar';
import { BotonGuardar, Pagina, Tarjeta, campoSx } from './piezas';

/*
 * Configuración › General (28-10-2026): la empresa activa. Su logo, su identidad, los datos con
 * que factura y quién puede crear agentes, cada cosa en su tarjeta con su propio Guardar.
 * Reemplaza a la pestaña "Datos y logo" (antes pages/admin/WorkspacePage).
 */

const POLITICAS = [
  { value: 'todos', label: 'Todos' },
  { value: 'editores', label: 'Editores y administradores' },
  { value: 'admins', label: 'Solo administradores' },
];

// Qué puede hacer cada rol. Se muestra y no se configura: el rol ya contesta la pregunta.
const PERMISOS = [
  ['Usar el chat y los módulos', true, true, true],
  ['Registrar ventas, compras y movimientos', false, true, true],
  ['Cargar datos del SII y sincronizar conectores', false, true, true],
  ['Configurar módulos y automatizaciones', false, true, true],
  ['Conectar servicios y el facturador electrónico', false, false, true],
  ['Invitar personas y cambiar roles', false, false, true],
  ['Datos de la empresa, plan y pagos', false, false, true],
];

const SOLO_ADMIN = 'Solo un administrador de la empresa puede cambiar esto.';

function Logo({ empresa, esAdmin, recargar }) {
  const [subiendo, setSubiendo] = useState(false);
  const subir = async (archivo) => {
    if (archivo === undefined) return;
    if (archivo && archivo.size > 2 * 1024 * 1024) { toast.error('El logo puede pesar hasta 2 MB.'); return; }
    setSubiendo(true);
    try {
      if (archivo) {
        const fd = new FormData();
        fd.append('logo', archivo);
        await api.updateWorkspace(empresa.slug, fd);
      } else {
        await api.updateWorkspace(empresa.slug, { logo: null });
      }
      await recargar();
      toast.success(archivo ? 'Logo actualizado.' : 'Logo quitado.');
    } catch (e) {
      toast.error(e.response?.data?.logo?.[0] || 'No se pudo subir el logo.');
    } finally { setSubiendo(false); }
  };
  return (
    <Tarjeta titulo="Logo"
      descripcion="Identifica a la empresa en Afable y sale impreso en sus facturas, cotizaciones y órdenes."
      pie={esAdmin ? 'Cuadrado, PNG o SVG, hasta 2 MB. Sin logo se usan las iniciales.' : SOLO_ADMIN}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2.5 }}>
        <MarcaWorkspace workspace={empresa} size={64} radio="14px" />
        {esAdmin && (
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Button component="label" variant="outlined" size="small" disabled={subiendo} startIcon={<Upload size={14} />}
              sx={{ borderRadius: '8px', textTransform: 'none', fontWeight: 600 }}>
              {empresa.logo_url ? 'Cambiar logo' : 'Subir logo'}
              <input hidden type="file" accept="image/png,image/jpeg,image/svg+xml,image/webp" onChange={(e) => subir(e.target.files?.[0])} />
            </Button>
            {empresa.logo_url && (
              <Button size="small" disabled={subiendo} onClick={() => subir(null)}
                sx={{ borderRadius: '8px', textTransform: 'none', fontWeight: 600, color: 'text.secondary' }}>
                Quitar
              </Button>
            )}
          </Box>
        )}
      </Box>
    </Tarjeta>
  );
}

function Identidad({ empresa, esAdmin, recargar }) {
  const [sectores, setSectores] = useState([]);
  const inicial = useMemo(() => ({
    name: empresa.name || '', rut: empresa.rut || '', sector: empresa.sector || '',
    employees: empresa.employees ? String(empresa.employees) : '', description: empresa.description || '',
  }), [empresa]);
  const [form, setForm] = useState(inicial);
  const [guardando, setGuardando] = useState(false);
  useEffect(() => setForm(inicial), [inicial]);
  useEffect(() => { api.getSectors().then((r) => setSectores(r.data)).catch(() => setSectores([])); }, []);

  const cambios = Object.keys(form).some((k) => form[k] !== inicial[k]);
  const guardar = async () => {
    if (!form.name.trim()) { toast.error('La empresa necesita un nombre.'); return; }
    setGuardando(true);
    try {
      await api.updateWorkspace(empresa.slug, { ...form, name: form.name.trim(), rut: form.rut.trim() });
      await recargar();
      toast.success('Empresa actualizada.');
    } catch (e) {
      const d = e.response?.data || {};
      toast.error(d.detail || d.rut?.[0] || d.name?.[0] || 'No se pudo guardar.');
    } finally { setGuardando(false); }
  };
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  return (
    <Tarjeta titulo="Empresa"
      descripcion="Los agentes leen esta descripción antes de contestar: mientras mejor diga qué hace la empresa, mejores respuestas."
      pie={esAdmin ? 'El RUT se valida con su dígito verificador.' : SOLO_ADMIN}
      accion={esAdmin && <BotonGuardar guardando={guardando} cambios={cambios} onClick={guardar} />}>
      <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' } }}>
        <TextField label="Nombre" value={form.name} onChange={set('name')} disabled={!esAdmin} size="small" sx={campoSx} />
        <TextField label="RUT" value={form.rut} onChange={set('rut')} disabled={!esAdmin} placeholder="76.123.456-7" size="small" sx={campoSx} />
        <TextField select label="Sector" value={sectores.some((s) => s.value === form.sector) ? form.sector : ''} onChange={set('sector')}
          disabled={!esAdmin} size="small" sx={campoSx}>
          {sectores.map((s) => <MenuItem key={s.value} value={s.value} sx={{ fontSize: '0.875rem' }}>{s.label}</MenuItem>)}
        </TextField>
        <TextField label="Número de personas" value={form.employees} onChange={set('employees')} disabled={!esAdmin} placeholder="Ej: 25"
          size="small" sx={campoSx} />
        <TextField label="Qué hace la empresa" value={form.description} onChange={set('description')} disabled={!esAdmin}
          placeholder="Ej: distribuimos materiales de construcción a ferreterías de la Región Metropolitana."
          multiline minRows={3} size="small" sx={{ ...campoSx, gridColumn: '1 / -1' }} />
      </Box>
    </Tarjeta>
  );
}

function Permisos({ empresa, esAdmin, recargar }) {
  const [politica, setPolitica] = useState(empresa.agent_creation_policy || 'editores');
  const [guardando, setGuardando] = useState(false);
  useEffect(() => setPolitica(empresa.agent_creation_policy || 'editores'), [empresa]);
  const guardar = async () => {
    setGuardando(true);
    try {
      await api.updateWorkspace(empresa.slug, { agent_creation_policy: politica });
      await recargar();
      toast.success('Permisos guardados.');
    } catch (e) { toast.error(e.response?.data?.detail || 'No se pudo guardar.'); } finally { setGuardando(false); }
  };
  const celda = (si) => (
    <Box sx={{ display: 'flex', justifyContent: 'center', color: si ? 'var(--af-acento)' : 'text.disabled' }}>
      {si ? <Check size={15} /> : <Minus size={15} />}
    </Box>
  );
  return (
    <Tarjeta titulo="Roles y permisos"
      descripcion="Cada persona tiene un rol en la empresa. El rol de cada una se cambia en Equipo."
      pie={esAdmin ? 'Crear agentes es lo único que se elige; lo demás lo decide el rol.' : SOLO_ADMIN}
      accion={esAdmin && <BotonGuardar guardando={guardando} cambios={politica !== (empresa.agent_creation_policy || 'editores')} onClick={guardar} />}>
      <Box sx={{ border: '1px solid', borderColor: 'divider', borderRadius: '10px', overflow: 'hidden' }}>
        <Box sx={{ display: 'grid', gridTemplateColumns: '1fr repeat(3, 84px)', px: 2, py: 1, bgcolor: 'action.hover',
          fontSize: '0.74rem', fontWeight: 600, color: 'text.secondary' }}>
          <span /><Box sx={{ textAlign: 'center' }}>Miembro</Box><Box sx={{ textAlign: 'center' }}>Editor</Box><Box sx={{ textAlign: 'center' }}>Admin</Box>
        </Box>
        {PERMISOS.map(([que, m, e, a]) => (
          <Box key={que} sx={{ display: 'grid', gridTemplateColumns: '1fr repeat(3, 84px)', px: 2, py: 1.1, alignItems: 'center',
            borderTop: '1px solid', borderColor: 'divider', fontSize: '0.85rem' }}>
            <span>{que}</span>{celda(m)}{celda(e)}{celda(a)}
          </Box>
        ))}
      </Box>
      <Typography sx={{ fontSize: '0.875rem', fontWeight: 500, mt: 2.5, mb: 1 }}>Quién puede crear agentes</Typography>
      <ToggleButtonGroup exclusive size="small" value={politica} disabled={!esAdmin} onChange={(_, v) => v && setPolitica(v)}
        sx={{ flexWrap: 'wrap', '& .MuiToggleButton-root': { textTransform: 'none', fontSize: '0.82rem', px: 1.75, py: 0.6, borderRadius: '8px !important',
          border: '1px solid !important', borderColor: 'divider', mr: 0.75, mb: 0.75 },
          '& .Mui-selected': { borderColor: 'color-mix(in srgb, var(--af-acento) 45%, transparent) !important',
            bgcolor: 'color-mix(in srgb, var(--af-acento) 10%, transparent) !important', color: 'var(--af-acento) !important' } }}>
        {POLITICAS.map((p) => <ToggleButton key={p.value} value={p.value}>{p.label}</ToggleButton>)}
      </ToggleButtonGroup>
    </Tarjeta>
  );
}

export default function General() {
  const { workspace, esAdmin, recargar } = useWorkspace();
  // Al llegar con #facturar (desde Ventas o el facturador), se baja a esa tarjeta.
  useEffect(() => {
    if (window.location.hash !== '#facturar') return undefined;
    const t = setTimeout(() => document.getElementById('facturar')?.scrollIntoView({ behavior: 'smooth' }), 400);
    return () => clearTimeout(t);
  }, []);
  return (
    <Pagina titulo="General" descripcion={`Los datos de ${workspace.name}: cómo se llama, qué hace y con qué datos factura.`}>
      <Logo empresa={workspace} esAdmin={esAdmin} recargar={recargar} />
      <Identidad empresa={workspace} esAdmin={esAdmin} recargar={recargar} />
      <DatosParaFacturar />
      <Permisos empresa={workspace} esAdmin={esAdmin} recargar={recargar} />
    </Pagina>
  );
}
