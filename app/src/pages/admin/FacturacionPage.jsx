import { useCallback, useEffect, useState } from 'react';
import {
  Box, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent,
  DialogTitle, IconButton, Tooltip, Typography, useTheme,
} from '@mui/material';
import { useSearchParams } from 'react-router-dom';
import { Check, CreditCard, Star, Trash2 } from 'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../../services/api';
import { useWorkspace } from '../../context/WorkspaceContext';

const DISPLAY = `'Sora', 'Inter', sans-serif`;

const FLOW = 'flow';
const PAYPAL = 'paypal';

// Cómo se llama cada pasarela para quien paga. Nadie contrata "una pasarela": elige
// pagar en pesos con su tarjeta chilena, o en dólares con PayPal.
const PASARELAS = {
  [FLOW]: { nombre: 'Tarjeta en pesos', detalle: 'Webpay · Flow', moneda: 'CLP' },
  [PAYPAL]: { nombre: 'PayPal en dólares', detalle: 'Para pagos desde fuera de Chile', moneda: 'USD' },
};

const ESTADOS = {
  trial: { texto: 'En prueba', color: 'info' },
  active: { texto: 'Activo', color: 'success' },
  suspended: { texto: 'Suspendido', color: 'warning' },
  cancelled: { texto: 'Cancelado', color: 'default' },
};

// Lo que le pasó a la persona en la pasarela, traducido. La URL trae `?pago=` cuando
// vuelve de Flow o de PayPal (ver `_pantalla_facturacion` en el backend).
const VUELTAS = {
  listo: ['success', 'Listo, su plan quedó activo.'],
  'tarjeta-lista': ['success', 'Tarjeta guardada.'],
  'tarjeta-sin-plan': ['warning', 'La tarjeta quedó guardada, pero no se pudo activar el plan. Vuelva a elegirlo.'],
  'sin-tarjeta': ['error', 'No se pudo guardar la tarjeta.'],
  rechazado: ['error', 'El pago no se completó.'],
};

const formatearMonto = (monto, moneda) =>
  moneda === 'USD'
    ? `US$${monto}`
    : `$${Number(monto).toLocaleString('es-CL')}`;

const formatearFecha = (iso) =>
  iso ? new Date(iso).toLocaleDateString('es-CL', { day: '2-digit', month: 'short', year: 'numeric' }) : '—';

/**
 * Facturación de la empresa: el plan, con qué se paga y qué se cobró.
 *
 * Sólo la ve el administrador del Workspace — el backend contesta 403 a un editor, y
 * acá se dice por qué en vez de mostrar una pantalla vacía.
 *
 * Las dos pasarelas están juntas y NO se elige "proveedor": se elige moneda. Flow cobra
 * en pesos y PayPal en dólares, y ese es el único criterio que le importa a quien paga.
 * Una pasarela sin credenciales cargadas no se ofrece (`proveedores` lo dice el
 * backend): un botón que revienta al apretarlo es peor que un botón que no está.
 */
export default function FacturacionPage() {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const { slug, esAdmin, loading: cargandoWorkspace } = useWorkspace();
  const [params, setParams] = useSearchParams();

  const textMuted = d ? 'rgba(255,255,255,0.66)' : 'rgba(0,0,0,0.62)';
  const textSemi = d ? 'rgba(255,255,255,0.82)' : 'rgba(0,0,0,0.76)';
  const bgSuave = d ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.02)';
  const borde = theme.palette.divider;

  const [datos, setDatos] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [trabajando, setTrabajando] = useState('');
  const [confirmarBaja, setConfirmarBaja] = useState(false);

  const cargar = useCallback(async () => {
    if (!slug) return;
    try {
      setCargando(true);
      const { data } = await api.getFacturacion(slug);
      setDatos(data);
    } catch (e) {
      if (e.response?.status !== 403) toast.error('No se pudo leer la facturación.');
    } finally {
      setCargando(false);
    }
  }, [slug]);

  useEffect(() => { cargar(); }, [cargar]);

  // El aviso de la vuelta se muestra una sola vez: si el parámetro se quedara en la
  // URL, recargar la pantalla volvería a felicitar por un pago viejo.
  useEffect(() => {
    const vuelta = params.get('pago') || (params.get('paypal') === 'cancelado' ? 'rechazado' : null);
    if (!vuelta) return;
    const [tipo, mensaje] = VUELTAS[vuelta] || ['info', 'Volvió de la pasarela.'];
    toast[tipo](mensaje);
    params.delete('pago');
    params.delete('paypal');
    setParams(params, { replace: true });
  }, [params, setParams]);

  const contratar = async (planId, proveedor) => {
    try {
      setTrabajando(`${planId}:${proveedor}`);
      const { data } = await api.suscribir(slug, planId, proveedor);
      // 202 con url = hay que ir a la pasarela (registrar tarjeta o aprobar en PayPal).
      if (data.url) {
        window.location.href = data.url;
        return;
      }
      toast.success('Plan activado.');
      cargar();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'No se pudo contratar el plan.');
    } finally {
      setTrabajando('');
    }
  };

  const agregarTarjeta = async () => {
    try {
      setTrabajando('tarjeta');
      const { data } = await api.agregarMetodoPago(slug, FLOW);
      if (data.url) window.location.href = data.url;
    } catch (e) {
      toast.error(e.response?.data?.detail || 'No se pudo abrir el registro de tarjeta.');
    } finally {
      setTrabajando('');
    }
  };

  const quitarMetodo = async (id) => {
    try {
      await api.quitarMetodoPago(slug, id);
      toast.success('Medio de pago quitado.');
      cargar();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'No se pudo quitar.');
    }
  };

  const hacerPrincipal = async (id) => {
    try {
      await api.metodoPagoPrincipal(slug, id);
      cargar();
    } catch {
      toast.error('No se pudo marcar como principal.');
    }
  };

  const darDeBaja = async () => {
    try {
      setTrabajando('baja');
      await api.cancelarSuscripcion(slug);
      toast.success('Plan dado de baja.');
      setConfirmarBaja(false);
      cargar();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'La pasarela no confirmó la baja.');
    } finally {
      setTrabajando('');
    }
  };

  if (cargandoWorkspace || cargando) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', pt: 12 }}>
        <CircularProgress size={26} sx={{ color: '#586AD0' }} />
      </Box>
    );
  }

  if (!esAdmin) {
    return (
      <Box sx={{ maxWidth: 860, mx: 'auto', px: 4, py: 8 }}>
        <Typography sx={{ color: textMuted, fontSize: '0.9375rem' }}>
          La facturación la administra quien tiene el rol de administrador en esta empresa.
        </Typography>
      </Box>
    );
  }

  if (!datos) return null;

  const { suscripcion, metodos_pago: metodos, cobros, planes, proveedores, dias_de_prueba } = datos;
  const disponibles = Object.keys(PASARELAS).filter((p) => proveedores?.[p]);

  const Seccion = ({ titulo, ayuda, children, accion }) => (
    <Box sx={{ mt: 5 }}>
      <Box sx={{ display: 'flex', alignItems: 'flex-end', gap: 2 }}>
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography sx={{ fontSize: '1.0625rem', fontWeight: 600 }}>{titulo}</Typography>
          {ayuda && (
            <Typography sx={{ color: textMuted, fontSize: '0.875rem', mt: 0.5 }}>{ayuda}</Typography>
          )}
        </Box>
        {accion}
      </Box>
      <Box sx={{ mt: 2 }}>{children}</Box>
    </Box>
  );

  return (
    <Box sx={{ maxWidth: 1000, mx: 'auto', px: { xs: 2.5, md: 5 }, py: { xs: 4, md: 6 }, width: '100%' }}>
      <CreditCard size={24} color={textSemi} strokeWidth={1.75} />
      <Typography
        sx={{ fontFamily: DISPLAY, fontSize: '1.875rem', fontWeight: 600, mt: 1.5, letterSpacing: '-0.01em' }}
      >
        Facturación
      </Typography>
      <Typography sx={{ color: textMuted, fontSize: '0.9375rem', mt: 0.75 }}>
        El plan es de la empresa, no de una persona: todo el equipo queda cubierto con una
        sola suscripción.
      </Typography>

      {/* ── El plan actual ───────────────────────────────────────────────────── */}
      <Seccion
        titulo="Su plan"
        accion={suscripcion && (
          <Button
            onClick={() => setConfirmarBaja(true)}
            sx={{ textTransform: 'none', color: textMuted, fontSize: '0.875rem' }}
          >
            Dar de baja
          </Button>
        )}
      >
        {suscripcion ? (
          <Box sx={{ border: `1px solid ${borde}`, borderRadius: '10px', p: 2.5, bgcolor: bgSuave }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap' }}>
              <Typography sx={{ fontSize: '1.125rem', fontWeight: 600 }}>
                {suscripcion.plan.name}
              </Typography>
              <Chip
                size="small"
                label={(ESTADOS[suscripcion.status] || {}).texto || suscripcion.status}
                color={(ESTADOS[suscripcion.status] || {}).color || 'default'}
                sx={{ height: 22, fontSize: '0.7rem' }}
              />
              {!suscripcion.aprobada && (
                <Chip
                  size="small" label="Falta terminar el pago" color="warning" variant="outlined"
                  sx={{ height: 22, fontSize: '0.7rem' }}
                />
              )}
            </Box>
            <Typography sx={{ color: textMuted, fontSize: '0.875rem', mt: 1 }}>
              {formatearMonto(
                suscripcion.moneda === 'USD'
                  ? suscripcion.plan.price_usd
                  : suscripcion.plan.price_clp,
                suscripcion.moneda,
              )}
              {' por mes · '}
              {PASARELAS[suscripcion.proveedor]?.nombre || suscripcion.proveedor}
              {suscripcion.current_period_end
                && ` · se renueva el ${formatearFecha(suscripcion.current_period_end)}`}
            </Typography>
          </Box>
        ) : (
          <Typography sx={{ color: textMuted, fontSize: '0.9375rem' }}>
            Todavía no hay ningún plan contratado. Los primeros {dias_de_prueba} días son de
            prueba.
          </Typography>
        )}
      </Seccion>

      {/* ── Elegir o cambiar de plan ─────────────────────────────────────────── */}
      <Seccion
        titulo={suscripcion ? 'Cambiar de plan' : 'Elegir un plan'}
        ayuda={
          disponibles.length === 2
            ? 'En pesos con tarjeta chilena, o en dólares con PayPal.'
            : disponibles.length === 1
              ? `Se cobra en ${PASARELAS[disponibles[0]].moneda}.`
              : 'Todavía no hay ninguna forma de pago configurada.'
        }
      >
        <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', md: '1fr 1fr 1fr' } }}>
          {planes.map((plan) => {
            const actual = suscripcion?.plan?.id === plan.id;
            return (
              <Box
                key={plan.id}
                sx={{
                  border: `1px solid ${actual ? '#586AD0' : borde}`,
                  borderRadius: '10px', p: 2.25,
                  display: 'flex', flexDirection: 'column', gap: 1,
                }}
              >
                <Typography sx={{ fontWeight: 600, fontSize: '1rem' }}>{plan.name}</Typography>
                <Typography sx={{ fontSize: '0.875rem', color: textSemi }}>
                  {plan.es_a_medida
                    ? 'A conversar'
                    : `$${Number(plan.price_clp).toLocaleString('es-CL')} CLP · US$${plan.price_usd}`}
                </Typography>
                <Typography sx={{ fontSize: '0.8125rem', color: textMuted, flex: 1 }}>
                  {plan.es_a_medida
                    ? 'Límites y condiciones a la medida de la empresa.'
                    : `${plan.max_agents} agentes · ${plan.max_integrations} conexiones · `
                      + `${Number(plan.queries_per_month).toLocaleString('es-CL')} consultas al mes`}
                </Typography>

                {actual ? (
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, color: '#586AD0' }}>
                    <Check size={15} />
                    <Typography sx={{ fontSize: '0.8125rem', fontWeight: 600 }}>Su plan</Typography>
                  </Box>
                ) : plan.es_a_medida ? (
                  <Button
                    href="mailto:hola@getafable.com?subject=Plan Enterprise"
                    sx={{ textTransform: 'none', justifyContent: 'flex-start', px: 0 }}
                  >
                    Escríbanos
                  </Button>
                ) : (
                  /* Un botón por moneda, no un selector: dos clics para elegir cómo
                     pagar es un paso más entre la decisión y el pago. */
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.75 }}>
                    {disponibles.map((prov) => (
                      <Button
                        key={prov}
                        variant={prov === FLOW ? 'contained' : 'outlined'}
                        size="small"
                        disabled={!!trabajando}
                        onClick={() => contratar(plan.id, prov)}
                        sx={{ textTransform: 'none', fontSize: '0.8125rem' }}
                      >
                        {trabajando === `${plan.id}:${prov}`
                          ? 'Abriendo...'
                          : PASARELAS[prov].nombre}
                      </Button>
                    ))}
                  </Box>
                )}
              </Box>
            );
          })}
        </Box>
      </Seccion>

      {/* ── Medios de pago ───────────────────────────────────────────────────── */}
      <Seccion
        titulo="Medios de pago"
        ayuda="La tarjeta se escribe en el formulario de la pasarela: Afable no guarda el número."
        accion={proveedores?.[FLOW] && (
          <Button
            variant="outlined" size="small" disabled={!!trabajando} onClick={agregarTarjeta}
            sx={{ textTransform: 'none' }}
          >
            {trabajando === 'tarjeta' ? 'Abriendo...' : 'Agregar tarjeta'}
          </Button>
        )}
      >
        {metodos.length === 0 ? (
          <Typography sx={{ color: textMuted, fontSize: '0.9375rem' }}>
            Todavía no hay ninguno guardado. Se guarda solo al contratar un plan.
          </Typography>
        ) : (
          <Box sx={{ border: `1px solid ${borde}`, borderRadius: '10px', overflow: 'hidden' }}>
            {metodos.map((m, i) => (
              <Box
                key={m.id}
                sx={{
                  display: 'flex', alignItems: 'center', gap: 1.5, px: 2, py: 1.5,
                  borderTop: i ? `1px solid ${borde}` : 'none',
                }}
              >
                <CreditCard size={16} color={textMuted} />
                <Typography sx={{ flex: 1, fontSize: '0.9375rem' }}>{m.etiqueta}</Typography>
                {m.principal ? (
                  <Chip
                    size="small" label="Principal"
                    sx={{ height: 22, fontSize: '0.7rem', bgcolor: bgSuave }}
                  />
                ) : (
                  <Tooltip title="Cobrar con este de ahora en adelante" arrow>
                    <IconButton size="small" onClick={() => hacerPrincipal(m.id)}>
                      <Star size={15} color={textMuted} />
                    </IconButton>
                  </Tooltip>
                )}
                <Tooltip title="Quitar" arrow>
                  <IconButton size="small" onClick={() => quitarMetodo(m.id)}>
                    <Trash2 size={15} color={textMuted} />
                  </IconButton>
                </Tooltip>
              </Box>
            ))}
          </Box>
        )}
      </Seccion>

      {/* ── Cartola ──────────────────────────────────────────────────────────── */}
      <Seccion titulo="Cobros" ayuda="Lo que se le ha cobrado a esta empresa.">
        {cobros.length === 0 ? (
          <Typography sx={{ color: textMuted, fontSize: '0.9375rem' }}>
            Todavía no hay ningún cobro.
          </Typography>
        ) : (
          <Box sx={{ border: `1px solid ${borde}`, borderRadius: '10px', overflow: 'hidden' }}>
            {cobros.map((c, i) => (
              <Box
                key={c.commerce_order}
                sx={{
                  display: 'flex', alignItems: 'center', gap: 2, px: 2, py: 1.5,
                  borderTop: i ? `1px solid ${borde}` : 'none',
                }}
              >
                <Typography sx={{ fontSize: '0.875rem', color: textMuted, width: 110 }}>
                  {formatearFecha(c.created_at)}
                </Typography>
                <Typography sx={{ flex: 1, fontSize: '0.9375rem', minWidth: 0 }}>
                  {c.subject}
                </Typography>
                <Typography sx={{ fontSize: '0.9375rem', fontWeight: 500 }}>
                  {formatearMonto(c.amount, c.moneda)}
                </Typography>
                <Chip
                  size="small"
                  label={c.status === 'paid' ? 'Pagado' : c.status === 'pending' ? 'Pendiente' : 'Rechazado'}
                  color={c.status === 'paid' ? 'success' : c.status === 'pending' ? 'default' : 'error'}
                  sx={{ height: 22, fontSize: '0.7rem', width: 88 }}
                />
              </Box>
            ))}
          </Box>
        )}
      </Seccion>

      <Dialog open={confirmarBaja} onClose={() => setConfirmarBaja(false)}>
        <DialogTitle sx={{ fontFamily: DISPLAY, fontSize: '1.125rem' }}>
          ¿Dar de baja el plan?
        </DialogTitle>
        <DialogContent>
          <Typography sx={{ fontSize: '0.9375rem', color: textSemi }}>
            La empresa deja de pagar y pierde el plan {suscripcion?.plan?.name}. Nada de lo
            que ya está cargado se borra.
          </Typography>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setConfirmarBaja(false)} sx={{ textTransform: 'none' }}>
            Mejor no
          </Button>
          <Button
            onClick={darDeBaja} color="error" variant="contained" disabled={trabajando === 'baja'}
            sx={{ textTransform: 'none' }}
          >
            {trabajando === 'baja' ? 'Dando de baja...' : 'Dar de baja'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
