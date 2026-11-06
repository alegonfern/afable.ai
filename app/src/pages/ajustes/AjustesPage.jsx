import { useEffect, useState } from 'react';
import { Navigate, useNavigate, useParams } from 'react-router-dom';
import { Box, Button, Divider, ListItemIcon, Menu, MenuItem, Typography, useMediaQuery } from '@mui/material';
import {
  ArrowLeft, ArrowRight, Boxes, Briefcase, Building2, Calculator, Check, ChevronLeft, ChevronRight, ChevronsUpDown,
  CreditCard, FileText, Lock, PackageOpen, Plug, Plus, ShoppingCart, SlidersHorizontal, User, Users, Wallet,
} from 'lucide-react';
import { MarcaWorkspace } from '../../components/SelectorWorkspace';
import { useWorkspace } from '../../context/WorkspaceContext';
import { api } from '../../services/api';
import { MODULOS } from '../../layout/Dashboard/modulos';
import { CONFIGURACION_DE_MODULO } from '../modulos/Configuraciones';
import FacturacionPage from '../admin/FacturacionPage';
import PersonasPage from '../admin/PersonasPage';
import { ModalNuevoWorkspace } from '../admin/WorkspacePage';
import FacturacionElectronica from '../dte/FacturacionElectronica';
import { useDteDisponible } from '../dte/useDte';
import Conectores from './Conectores';
import { Perfil, Preferencias, Seguridad } from './Cuenta';
import General from './General';
import { Cargando, Pagina, Tarjeta } from './piezas';

/*
 * Configuración (28-10-2026), al estilo de Linear y Vercel: una pantalla propia, con su menú en
 * lugar de la barra de Afable y "Volver a Afable" arriba. Todo trabaja sobre la EMPRESA ACTIVA,
 * que se elige (o se crea) en el selector de arriba del menú.
 *
 *   Empresa    /app/ajustes/general | equipo | facturacion-electronica | conectores | plan
 *   Módulos    /app/ajustes/modulos/<módulo>   (el ⚙ de cada módulo lleva aquí)
 *   Mi cuenta  /app/ajustes/perfil | preferencias | seguridad | empresas
 *
 * Las direcciones de antes (/app/ajustes/empresas/<slug|actual>/<pestaña>) siguen sirviendo:
 * dejan activa esa empresa y llevan a la página nueva.
 */

const ICONOS_MODULO = { ventas: ShoppingCart, compras: PackageOpen, inventario: Boxes, contabilidad: Calculator, finanzas: Wallet };

const DESCRIPCION_MODULO = {
  ventas: 'Las cotizaciones, qué se espera ver facturado y con qué datos se factura.',
  compras: 'Qué se espera ver facturado por sus proveedores.',
  inventario: 'Cómo se lleva el stock y en qué bodegas.',
  contabilidad: 'Los impuestos, los proyectos y el plan de cuentas.',
  finanzas: 'Las cuentas bancarias con que se calcula la caja.',
};
const SE_GUARDA_SOLO = new Set(['ventas', 'compras', 'inventario']);

// Las pestañas de la empresa de antes y su página nueva.
const PESTANA_ANTIGUA = { datos: 'general', equipo: 'equipo', 'facturacion-electronica': 'facturacion-electronica', plan: 'plan' };

export const ULTIMA_RUTA = 'afable_ultima_ruta';
const rutaDeVuelta = () => {
  try { return sessionStorage.getItem(ULTIMA_RUTA) || '/app'; } catch { return '/app'; }
};

function useMenu(dte) {
  return [
    { grupo: 'Empresa', items: [
      { clave: 'general', label: 'General', icono: Building2 },
      { clave: 'equipo', label: 'Equipo', icono: Users },
      ...(dte ? [{ clave: 'facturacion-electronica', label: 'Facturación electrónica', icono: FileText }] : []),
      { clave: 'conectores', label: 'Conectores', icono: Plug },
      { clave: 'plan', label: 'Plan y pagos', icono: CreditCard },
    ] },
    { grupo: 'Módulos', items: MODULOS.map((m) => ({ clave: `modulos/${m.slug}`, label: m.label, icono: ICONOS_MODULO[m.slug] })) },
    { grupo: 'Mi cuenta', items: [
      { clave: 'perfil', label: 'Perfil', icono: User },
      { clave: 'preferencias', label: 'Preferencias', icono: SlidersHorizontal },
      { clave: 'seguridad', label: 'Seguridad', icono: Lock },
      { clave: 'empresas', label: 'Mis empresas', icono: Briefcase },
    ] },
  ];
}

const ROLES = { admin: 'Administrador', editor: 'Editor', miembro: 'Miembro', member: 'Miembro' };

/* La empresa activa, arriba del menú: cambia de empresa o crea una nueva. */
function SelectorEmpresa({ onNueva }) {
  const { workspaces, workspace, seleccionar } = useWorkspace();
  const navigate = useNavigate();
  const [ancla, setAncla] = useState(null);
  return (
    <>
      <Box component="button" type="button" onClick={(e) => setAncla(e.currentTarget)} aria-haspopup="menu" aria-label="Cambiar de empresa"
        sx={{
          width: '100%', boxSizing: 'border-box', display: 'flex', alignItems: 'center', gap: 1.25, p: 1, borderRadius: '10px', cursor: 'pointer',
          border: '1px solid', borderColor: 'divider', bgcolor: 'background.paper', fontFamily: 'inherit', color: 'text.primary', textAlign: 'left',
          '&:hover': { borderColor: 'text.disabled' },
        }}>
        {workspace ? <MarcaWorkspace workspace={workspace} size={30} radio="8px" /> : (
          <Box sx={{ width: 30, height: 30, borderRadius: '8px', border: '1px dashed', borderColor: 'divider', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Plus size={14} />
          </Box>
        )}
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography noWrap sx={{ fontSize: '0.86rem', fontWeight: 600, lineHeight: 1.3 }}>{workspace?.name || 'Sin empresa'}</Typography>
          <Typography noWrap sx={{ fontSize: '0.74rem', color: 'text.secondary' }}>
            {workspace ? (ROLES[workspace.my_role] || workspace.my_role) : 'Cree su primera empresa'}
          </Typography>
        </Box>
        <ChevronsUpDown size={15} style={{ opacity: 0.55, flexShrink: 0 }} />
      </Box>
      <Menu anchorEl={ancla} open={Boolean(ancla)} onClose={() => setAncla(null)}
        PaperProps={{ sx: { width: ancla?.offsetWidth ? Math.max(ancla.offsetWidth, 260) : 260, mt: 0.75, borderRadius: '10px' } }}>
        <Typography sx={{ px: 1.75, pt: 0.75, pb: 0.5, fontSize: '0.72rem', color: 'text.secondary', fontWeight: 600 }}>Sus empresas</Typography>
        {workspaces.map((w) => (
          <MenuItem key={w.slug} selected={w.slug === workspace?.slug} sx={{ gap: 1.25, fontSize: '0.86rem', mx: 0.5, borderRadius: '6px' }}
            onClick={() => { setAncla(null); if (w.slug !== workspace?.slug) seleccionar(w.slug); }}>
            <MarcaWorkspace workspace={w} size={22} radio="6px" />
            <Box sx={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis' }}>{w.name}</Box>
            {w.slug === workspace?.slug && <Check size={15} />}
          </MenuItem>
        ))}
        <Divider sx={{ my: 0.5 }} />
        <MenuItem onClick={() => { setAncla(null); onNueva(); }} sx={{ fontSize: '0.86rem', mx: 0.5, borderRadius: '6px' }}>
          <ListItemIcon sx={{ minWidth: 30 }}><Plus size={15} /></ListItemIcon>Crear empresa
        </MenuItem>
        <MenuItem onClick={() => { setAncla(null); navigate('/app/ajustes/empresas'); }} sx={{ fontSize: '0.86rem', mx: 0.5, borderRadius: '6px' }}>
          <ListItemIcon sx={{ minWidth: 30 }}><Briefcase size={15} /></ListItemIcon>Ver todas
        </MenuItem>
      </Menu>
    </>
  );
}

function MenuAjustes({ activa, dte, onNueva, onElegir }) {
  const grupos = useMenu(dte);
  return (
    <Box component="nav" aria-label="Configuración" sx={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr)', alignContent: 'start', gap: 0.25 }}>
      <Box sx={{ mb: 1.5 }}><SelectorEmpresa onNueva={onNueva} /></Box>
      {grupos.map((g) => (
        <Box key={g.grupo} sx={{ mb: 1.25 }}>
          <Typography sx={{ fontSize: '0.72rem', fontWeight: 600, color: 'text.disabled', px: 1.25, pt: 1, pb: 0.5 }}>{g.grupo}</Typography>
          {g.items.map(({ clave, label, icono: Icono }) => {
            const actual = activa === clave;
            return (
              <Box key={clave} component="button" type="button" onClick={() => onElegir(clave)} aria-current={actual ? 'page' : undefined}
                sx={{
                  width: '100%', boxSizing: 'border-box', display: 'flex', alignItems: 'center', gap: 1.25, px: 1.25, py: 0.8, borderRadius: '7px', cursor: 'pointer',
                  border: 'none', fontFamily: 'inherit', fontSize: '0.875rem', textAlign: 'left',
                  color: actual ? 'text.primary' : 'text.secondary', fontWeight: actual ? 500 : 400,
                  bgcolor: actual ? 'action.selected' : 'transparent', '&:hover': { bgcolor: actual ? 'action.selected' : 'action.hover', color: 'text.primary' },
                }}>
                <Icono size={15} style={{ flexShrink: 0, opacity: actual ? 1 : 0.8 }} />
                <Box component="span" sx={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{label}</Box>
              </Box>
            );
          })}
        </Box>
      ))}
    </Box>
  );
}

function MisEmpresas({ onNueva }) {
  const { workspaces, workspace, seleccionar } = useWorkspace();
  const navigate = useNavigate();
  return (
    <Pagina titulo="Mis empresas" descripcion="Las empresas de las que es parte. Configuración y los módulos trabajan sobre la empresa activa."
      accion={<Button variant="contained" disableElevation size="small" startIcon={<Plus size={15} />} onClick={onNueva}
        sx={{ borderRadius: '8px', textTransform: 'none', fontWeight: 600, flexShrink: 0 }}>Crear empresa</Button>}>
      <Tarjeta sinRelleno>
        {workspaces.length === 0 && (
          <Typography sx={{ px: 3, py: 4, color: 'text.secondary', fontSize: '0.9rem' }}>Todavía no es parte de ninguna empresa.</Typography>
        )}
        {workspaces.map((w, i) => {
          const activa = w.slug === workspace?.slug;
          return (
            <Box key={w.slug} sx={{ display: 'flex', alignItems: 'center', gap: 1.75, px: 3, py: 1.75, borderTop: i ? '1px solid' : 'none', borderColor: 'divider' }}>
              <MarcaWorkspace workspace={w} size={36} radio="9px" />
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography noWrap sx={{ fontWeight: 600, fontSize: '0.92rem' }}>{w.name}</Typography>
                <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary' }}>
                  {ROLES[w.my_role] || w.my_role}{w.member_count ? ` · ${w.member_count} ${w.member_count === 1 ? 'persona' : 'personas'}` : ''}
                </Typography>
              </Box>
              {activa ? (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, fontSize: '0.78rem', fontWeight: 600, color: '#0f9d6b',
                  px: 1, py: 0.35, borderRadius: '999px', bgcolor: 'color-mix(in srgb, #0f9d6b 10%, transparent)' }}>
                  <Check size={13} /> Activa
                </Box>
              ) : (
                <Button size="small" variant="outlined" onClick={() => seleccionar(w.slug)}
                  sx={{ borderRadius: '8px', textTransform: 'none', fontWeight: 600 }}>Cambiar a esta</Button>
              )}
              <Button size="small" onClick={() => { if (!activa) seleccionar(w.slug); navigate('/app/ajustes/general'); }}
                endIcon={<ArrowRight size={14} />} sx={{ borderRadius: '8px', textTransform: 'none', fontWeight: 600, color: 'text.secondary' }}>
                Configurar
              </Button>
            </Box>
          );
        })}
      </Tarjeta>
    </Pagina>
  );
}

function ConfigModulo({ modulo }) {
  const navigate = useNavigate();
  const m = MODULOS.find((x) => x.slug === modulo);
  const Config = CONFIGURACION_DE_MODULO[modulo];
  if (!m || !Config) return <Navigate to="/app/ajustes/general" replace />;
  const descripcion = `${DESCRIPCION_MODULO[modulo] || ''}${SE_GUARDA_SOLO.has(modulo) ? ' Cada cambio se guarda solo.' : ''}`;
  return (
    <Pagina titulo={m.label} descripcion={descripcion}
      accion={<Button size="small" variant="outlined" endIcon={<ArrowRight size={14} />} onClick={() => navigate(`/app/${modulo}`)}
        sx={{ borderRadius: '8px', textTransform: 'none', fontWeight: 600, flexShrink: 0 }}>Ir a {m.label}</Button>}>
      <Config />
    </Pagina>
  );
}

function SinEmpresa({ onNueva }) {
  return (
    <Pagina titulo="Cree su empresa" descripcion="Para configurar la empresa, sus módulos y su equipo, primero cree una. Puede tener varias.">
      <Tarjeta>
        <Button variant="contained" disableElevation startIcon={<Plus size={15} />} onClick={onNueva}
          sx={{ borderRadius: '8px', textTransform: 'none', fontWeight: 600 }}>Crear empresa</Button>
      </Tarjeta>
    </Pagina>
  );
}

function Contenido({ clave, onNueva, dte }) {
  const { workspace, slug, esEditor, esAdmin } = useWorkspace();
  const deEmpresa = !['perfil', 'preferencias', 'seguridad', 'empresas'].includes(clave);
  if (deEmpresa && !workspace) return <SinEmpresa onNueva={onNueva} />;
  if (clave.startsWith('modulos/')) return <ConfigModulo key={`${slug}-${clave}`} modulo={clave.split('/')[1]} />;
  switch (clave) {
    case 'general': return <General key={slug} />;
    case 'equipo':
      return <Pagina key={slug} titulo="Equipo" descripcion={`Quiénes trabajan en ${workspace.name} y con qué rol. Lo que puede hacer cada rol está en General.`}>
        <PersonasPage embebido />
      </Pagina>;
    // Sin facturador habilitado no está en el menú; si se llega por dirección, la página lo dice.
    case 'facturacion-electronica':
      return <Pagina key={slug} titulo="Facturación electrónica" descripcion="Emita facturas, notas y guías directo al SII desde Afable, y reciba las de sus proveedores.">
        <FacturacionElectronica slug={slug} esEditor={esEditor} esAdmin={esAdmin} />
      </Pagina>;
    case 'conectores':
      return <Pagina key={slug} titulo="Conectores" descripcion={`Los servicios que Afable conecta con ${workspace.name}: CRM, bancos, el SII y más.`}>
        <Conectores />
      </Pagina>;
    case 'plan':
      return <Pagina key={slug} titulo="Plan y pagos" descripcion="El plan es de la empresa, no de una persona: todo el equipo queda cubierto con una sola suscripción.">
        <FacturacionPage embebido />
      </Pagina>;
    case 'perfil': return <Perfil />;
    case 'preferencias': return <Preferencias />;
    case 'seguridad': return <Seguridad />;
    case 'empresas': return <MisEmpresas onNueva={onNueva} />;
    default: return <Navigate to="/app/ajustes/general" replace />;
  }
}

export default function AjustesPage() {
  const { seccion, empresa, pestana } = useParams();
  const navigate = useNavigate();
  const { workspaces, workspace, slug, seleccionar, recargar, loading } = useWorkspace();
  const dte = useDteDisponible(slug);
  const telefono = useMediaQuery('(max-width:900px)');
  const [sectores, setSectores] = useState([]);
  const [nueva, setNueva] = useState(false);
  useEffect(() => { api.getSectors().then((r) => setSectores(r.data)).catch(() => setSectores([])); }, []);

  // Las direcciones de antes: /app/ajustes/empresas/<slug|actual>/<pestaña>.
  const antigua = seccion === 'empresas' && empresa;
  const destinoAntiguo = antigua && workspaces.find((w) => w.slug === empresa);
  useEffect(() => {
    if (destinoAntiguo && destinoAntiguo.slug !== workspace?.slug) seleccionar(destinoAntiguo.slug);
  }, [destinoAntiguo, workspace, seleccionar]);
  if (antigua) {
    if (loading) return <Cargando />;
    if (destinoAntiguo && destinoAntiguo.slug !== workspace?.slug) return <Cargando />;
    return <Navigate to={`/app/ajustes/${PESTANA_ANTIGUA[pestana] || 'general'}${window.location.hash}`} replace />;
  }
  if (seccion === 'modulos' && !empresa) return <Navigate to={`/app/ajustes/modulos/${MODULOS[0].slug}`} replace />;
  // En el computador, entrar a Configuración abre General; en el teléfono, el menú.
  if (!seccion && !telefono) return <Navigate to="/app/ajustes/general" replace />;

  const clave = seccion === 'modulos' ? `modulos/${empresa}` : seccion;
  const ir = (c) => navigate(`/app/ajustes/${c}`);
  const volver = () => navigate(rutaDeVuelta());
  const abrirNueva = () => setNueva(true);

  const botonVolver = (
    <Box component="button" type="button" onClick={volver} sx={{
      display: 'flex', alignItems: 'center', gap: 1, px: 1, py: 0.75, mb: 1.5, border: 'none', bgcolor: 'transparent', cursor: 'pointer',
      fontFamily: 'inherit', fontSize: '0.875rem', color: 'text.secondary', borderRadius: '7px', '&:hover': { color: 'text.primary', bgcolor: 'action.hover' },
    }}>
      <ArrowLeft size={15} /> Volver a Afable
    </Box>
  );

  const modal = (
    <ModalNuevoWorkspace abierto={nueva} cerrar={() => setNueva(false)} sectores={sectores}
      alCrear={async (creada) => { await recargar(); seleccionar(creada.slug); navigate('/app/ajustes/general'); }} />
  );

  if (loading) return <Cargando />;

  if (telefono) {
    return (
      <Box sx={{ minHeight: '100%', bgcolor: 'background.default', px: 2, py: 2, pb: 10 }}>
        {seccion ? (
          <>
            <Box component="button" type="button" onClick={() => navigate('/app/ajustes')} sx={{
              display: 'flex', alignItems: 'center', gap: 0.5, mb: 2, p: 0, border: 'none', bgcolor: 'transparent', cursor: 'pointer',
              fontFamily: 'inherit', fontSize: '0.9rem', color: 'var(--af-acento)', fontWeight: 500,
            }}>
              <ChevronLeft size={18} /> Configuración
            </Box>
            <Contenido clave={clave} onNueva={abrirNueva} dte={dte} />
          </>
        ) : (
          <>
            {botonVolver}
            <Typography sx={{ fontFamily: "'Sora', 'Inter', sans-serif", fontSize: '1.5rem', fontWeight: 600, mb: 2, px: 1 }}>Configuración</Typography>
            <MenuMovil dte={dte} onNueva={abrirNueva} onElegir={ir} />
          </>
        )}
        {modal}
      </Box>
    );
  }

  return (
    <Box sx={{ display: 'flex', height: '100%', minHeight: 0, bgcolor: 'background.default' }}>
      <Box sx={{ width: 264, flexShrink: 0, borderRight: '1px solid', borderColor: 'divider', bgcolor: 'background.paper',
        px: 1.5, py: 2, overflowY: 'auto' }}>
        {botonVolver}
        <MenuAjustes activa={clave} dte={dte} onNueva={abrirNueva} onElegir={ir} />
      </Box>
      <Box component="main" sx={{ flex: 1, minWidth: 0, overflowY: 'auto', px: { md: 5, lg: 8 }, py: 6 }}>
        <Contenido clave={clave} onNueva={abrirNueva} dte={dte} />
      </Box>
      {modal}
    </Box>
  );
}

/* En el teléfono el menú es la primera pantalla, como en los ajustes del celular. */
function MenuMovil({ dte, onNueva, onElegir }) {
  const grupos = useMenu(dte);
  return (
    <Box>
      <Box sx={{ mb: 2.5 }}><SelectorEmpresa onNueva={onNueva} /></Box>
      {grupos.map((g) => (
        <Box key={g.grupo} sx={{ mb: 2.5 }}>
          <Typography sx={{ fontSize: '0.75rem', fontWeight: 600, color: 'text.secondary', px: 1, mb: 0.75 }}>{g.grupo}</Typography>
          <Box sx={{ border: '1px solid', borderColor: 'divider', borderRadius: '12px', bgcolor: 'background.paper', overflow: 'hidden' }}>
            {g.items.map(({ clave, label, icono: Icono }, i) => (
              <Box key={clave} component="button" type="button" onClick={() => onElegir(clave)} sx={{
                width: '100%', boxSizing: 'border-box', display: 'flex', alignItems: 'center', gap: 1.5, px: 2, py: 1.5, border: 'none', cursor: 'pointer',
                borderTop: i ? '1px solid' : 'none', borderColor: 'divider', bgcolor: 'transparent', fontFamily: 'inherit',
                fontSize: '0.92rem', color: 'text.primary', textAlign: 'left',
              }}>
                <Icono size={17} style={{ opacity: 0.75 }} />
                <Box component="span" sx={{ flex: 1 }}>{label}</Box>
                <ChevronRight size={16} style={{ opacity: 0.4 }} />
              </Box>
            ))}
          </Box>
        </Box>
      ))}
    </Box>
  );
}
