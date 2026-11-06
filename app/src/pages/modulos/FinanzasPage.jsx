import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Box, Button, Chip, CircularProgress, Table, TableBody, TableCell, TableHead, TableRow,
  Tooltip, Typography, useTheme,
} from '@mui/material';
import { Landmark } from 'lucide-react';
import { toast } from 'react-toastify';
import { useVersionDeConfiguracion } from './Configuraciones';
import PageHeader from '../../components/PageHeader';
import { useWorkspace } from '../../context/WorkspaceContext';
import { api } from '../../services/api';
import { seccionDe } from '../../layout/Dashboard/modulos';
import { TONOS } from '../../theme/tonos';

/*
 * Finanzas › Módulo (PMV financiero, 17-10-2026): la plata de la empresa. Contabilidad dice
 * lo que pasó; acá se ve si hay plata y qué decidir con ella. Caja (disponible, cuánto puede
 * retirar, meses de caja, saldo en 30 días), por cobrar, por pagar y su cuenta con la empresa.
 */

const clp = (n) => (n == null ? '—' : `${n < 0 ? '−' : ''}$${Math.abs(Math.round(Number(n) || 0)).toLocaleString('es-CL')}`);
const ddmm = (iso) => iso.split('-').reverse().join('-');
const SORA = "'Sora', sans-serif";
const NUM = { fontVariantNumeric: 'tabular-nums' };

function Tarjeta({ children, sx }) {
  return <Box sx={{ border: '1px solid', borderColor: 'divider', borderRadius: '14px', bgcolor: 'background.paper', ...sx }}>{children}</Box>;
}
function Etiqueta({ children }) {
  return <Typography sx={{ fontSize: '0.74rem', fontWeight: 600, letterSpacing: '0.07em', textTransform: 'uppercase', color: 'text.secondary' }}>{children}</Typography>;
}

function Caja({ slug, onIrConciliacion }) {
  const [c, setC] = useState(null);
  useEffect(() => { api.finanzas.caja(slug).then(({ data }) => setC(data)); }, [slug]);
  if (!c) return <CircularProgress size={20} sx={{ m: 'auto' }} />;
  const sinBanco = c.disponible == null;
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      {sinBanco && (
        <Tarjeta sx={{ p: 2.5, display: 'flex', alignItems: 'center', gap: 2 }}>
          <Box sx={{ display: 'flex', p: 1, borderRadius: '10px', bgcolor: TONOS.pizarra.suave, color: TONOS.pizarra.color }}><Landmark size={18} /></Box>
          <Typography sx={{ flex: 1, fontSize: '0.9rem' }}>
            Para saber cuánta plata hay y cuánto puede retirar, suba la cartola de sus cuentas en Contabilidad › Conciliación.
          </Typography>
          <Button variant="contained" size="small" onClick={onIrConciliacion}>Ir a Conciliación</Button>
        </Tarjeta>
      )}
      <Typography sx={{ fontFamily: SORA, fontWeight: 600, fontSize: '1.3rem' }}>Para decidir hoy</Typography>
      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: 'repeat(3, 1fr)' }, gap: 2 }}>
        <Tarjeta sx={{ p: 2.5 }}>
          <Etiqueta>Puede retirar hasta</Etiqueta>
          <Typography sx={{ fontFamily: SORA, fontWeight: 600, fontSize: '1.9rem', color: 'var(--af-color)', fontStyle: 'italic', mt: 0.5, ...NUM }}>{clp(c.puede_retirar)}</Typography>
          <Typography sx={{ fontSize: '0.84rem', color: 'text.secondary', mt: 0.5, lineHeight: 1.5 }}>
            {sinBanco ? 'Necesita el saldo de sus cuentas.' : c.puede_retirar === 0
              ? `Su caja no alcanza para cubrir lo que debe en ${c.horizonte_dias} días más un mes de reserva. Este mes conviene no retirar.`
              : `Después de pagar lo comprometido en ${c.horizonte_dias} días y dejar un mes de gasto de reserva.`}
          </Typography>
        </Tarjeta>
        <Tarjeta sx={{ p: 2.5 }}>
          <Etiqueta>Meses de caja</Etiqueta>
          <Typography sx={{ fontFamily: SORA, fontWeight: 600, fontSize: '1.9rem', mt: 0.5, ...NUM }}>
            {c.meses_de_caja == null ? '—' : `${String(c.meses_de_caja).replace('.', ',')} meses`}
          </Typography>
          <Typography sx={{ fontSize: '0.84rem', color: 'text.secondary', mt: 0.5, lineHeight: 1.5 }}>
            Cuánto dura su caja si dejara de entrar plata, gastando {clp(c.gasto_mensual)} al mes como ahora.
          </Typography>
        </Tarjeta>
        <Tarjeta sx={{ p: 2.5 }}>
          <Etiqueta>Saldo en {c.horizonte_dias} días</Etiqueta>
          <Typography sx={{ fontFamily: SORA, fontWeight: 600, fontSize: '1.9rem', mt: 0.5, color: c.saldo_30_dias < 0 ? '#b42318' : 'text.primary', ...NUM }}>{clp(c.saldo_30_dias)}</Typography>
          <Typography sx={{ fontSize: '0.84rem', color: 'text.secondary', mt: 0.5, lineHeight: 1.5 }}>
            Entradas esperadas {clp(c.entradas_esperadas)} − salidas comprometidas {clp(c.salidas_comprometidas)}.
          </Typography>
        </Tarjeta>
      </Box>
      <Tarjeta sx={{ p: 2.5 }}>
        <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 2 }}>
          <Etiqueta>Disponible hoy</Etiqueta>
          <Typography sx={{ fontFamily: SORA, fontWeight: 600, fontSize: '1.5rem', ...NUM }}>{clp(c.disponible)}</Typography>
        </Box>
        {c.cuentas.map((x) => (
          <Box key={x.id} sx={{ display: 'flex', justifyContent: 'space-between', py: 0.75, borderTop: '1px solid', borderColor: 'divider', mt: 1 }}>
            <Typography sx={{ fontSize: '0.88rem' }}>{x.etiqueta}</Typography>
            <Typography sx={{ fontSize: '0.88rem', color: 'text.secondary', ...NUM }}>
              {x.saldo == null ? 'sin cartola' : `${clp(x.saldo)} · al ${ddmm(x.al)}`}
            </Typography>
          </Box>
        ))}
        <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary', mt: 1.5, lineHeight: 1.6 }}>
          Comprometido en {c.horizonte_dias} días: proveedores {clp(c.detalle_salidas.proveedores)} e impuestos {clp(c.detalle_salidas.impuestos)}.
          {c.fuente_gasto === 'banco' ? ' El gasto mensual sale de sus cartolas (últimos 3 meses, sin traspasos ni retiros).' : ' El gasto mensual sale de sus documentos del SII.'}
        </Typography>
      </Tarjeta>
    </Box>
  );
}

const TRAMOS = [
  ['vencido_30', 'Vencido más de 30 días', '#b42318'], ['vencido', 'Vencido', '#e5484d'],
  ['semana', 'Vence esta semana', TONOS.arena.color], ['mes', 'Vence este mes', '#c4b088'], ['despues', 'Después', '#e3dccb'],
];

function Cuentas({ slug, tipo, esEditor }) {
  const theme = useTheme();
  const [d, setD] = useState(null);
  const [vista, setVista] = useState('documento');
  const cargar = useCallback(() => api.finanzas.cuentasPor(slug, tipo).then(({ data }) => setD(data)), [slug, tipo]);
  useEffect(() => { cargar(); }, [cargar]);
  const cobrar = tipo === 'cobrar';

  const marcar = async (f) => {
    try {
      await api.finanzas.actualizarDocumento(slug, f.id, { pagado: true });
      toast.success(cobrar ? 'Marcada como cobrada.' : 'Marcada como pagada.');
      cargar();
    } catch (e) { toast.error(e.response?.data?.detail || 'No se pudo.'); }
  };

  if (!d) return <CircularProgress size={20} sx={{ m: 'auto' }} />;
  const cambio = d.total - d.cierre_mes_anterior;
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1.3fr 1fr' }, gap: 2 }}>
        <Box>
          <Etiqueta>Total por {cobrar ? 'cobrar' : 'pagar'}</Etiqueta>
          <Typography sx={{ fontFamily: SORA, fontWeight: 700, fontSize: '2.6rem', letterSpacing: '-0.02em', ...NUM }}>{clp(d.total)}</Typography>
          <Chip size="small" label={`${cambio >= 0 ? '▲ +' : '▼ '}${clp(cambio)} vs cierre del mes anterior`} sx={{ fontFamily: 'inherit', bgcolor: 'action.hover', mb: 1 }} />
          <Typography sx={{ fontSize: '1.05rem', color: 'text.secondary' }}>{clp(d.vencido)} vencido ({d.porcentaje_vencido}%)</Typography>
          {/* Vencimientos por tramo */}
          <Box sx={{ display: 'flex', height: 12, borderRadius: 6, overflow: 'hidden', mt: 2, bgcolor: 'action.hover' }}>
            {TRAMOS.map(([k, , color]) => d.tramos[k] > 0 && (
              <Tooltip key={k} arrow title={`${TRAMOS.find((t) => t[0] === k)[1]}: ${clp(d.tramos[k])}`}>
                <Box sx={{ width: `${(d.tramos[k] / Math.max(1, d.total)) * 100}%`, bgcolor: color }} />
              </Tooltip>
            ))}
          </Box>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1.5, mt: 1 }}>
            {TRAMOS.filter(([k]) => d.tramos[k]).map(([k, label, color]) => (
              <Typography key={k} sx={{ fontSize: '0.78rem', color: 'text.secondary', display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <span style={{ width: 8, height: 8, borderRadius: 2, background: color, display: 'inline-block' }} /> {label} {clp(d.tramos[k])}
              </Typography>
            ))}
          </Box>
        </Box>
        <Tarjeta sx={{ p: 2.5 }}>
          <Typography sx={{ fontFamily: SORA, fontWeight: 600, fontSize: '1.15rem', mb: 1 }}>Prioridad de {cobrar ? 'cobro' : 'pago'}</Typography>
          {d.prioridad.length === 0 && <Typography sx={{ fontSize: '0.86rem', color: 'text.secondary' }}>Nada vencido.</Typography>}
          {d.prioridad.map((f) => (
            <Box key={f.id} sx={{ display: 'flex', alignItems: 'center', gap: 1.5, py: 1, borderTop: '1px solid', borderColor: 'divider' }}>
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography sx={{ fontWeight: 600, fontSize: '0.9rem' }} noWrap>{f.razon_social}</Typography>
                <Chip size="small" label={`Atrasado · hace ${f.dias} días`} sx={{ height: 18, fontSize: '0.68rem', bgcolor: '#fde2e1', color: '#b42318', fontFamily: 'inherit' }} />
              </Box>
              <Typography sx={{ fontWeight: 700, ...NUM }}>{clp(f.monto)}</Typography>
              {esEditor && <Button size="small" variant="outlined" onClick={() => marcar(f)}>{cobrar ? 'Marcar cobrada' : 'Marcar pagada'}</Button>}
            </Box>
          ))}
        </Tarjeta>
      </Box>

      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <Typography sx={{ fontFamily: SORA, fontWeight: 600, fontSize: '1.15rem', flex: 1 }}>{cobrar ? 'Cuentas por cobrar' : 'Cuentas por pagar'}</Typography>
        {[['documento', 'Por documento'], ['contraparte', cobrar ? 'Por cliente' : 'Por proveedor']].map(([k, l]) => (
          <Chip key={k} label={l} onClick={() => setVista(k)} variant={vista === k ? 'filled' : 'outlined'} sx={{ fontFamily: 'inherit' }} />
        ))}
      </Box>
      <Tarjeta sx={{ overflow: 'auto' }}>
        <Table size="small" sx={{ '& td, & th': { fontSize: '0.86rem', borderColor: 'divider', whiteSpace: 'nowrap' } }}>
          {vista === 'documento' ? (
            <>
              <TableHead><TableRow sx={{ '& th': { color: 'text.secondary', fontWeight: 600, fontSize: '0.72rem', letterSpacing: '0.06em', textTransform: 'uppercase' } }}>
                <TableCell>{cobrar ? 'Cliente' : 'Proveedor'}</TableCell><TableCell>Documento</TableCell><TableCell>Emisión</TableCell>
                <TableCell>Vence</TableCell><TableCell align="right">Plazo</TableCell><TableCell align="right">Monto</TableCell><TableCell />
              </TableRow></TableHead>
              <TableBody>
                {d.documentos.length === 0 && <TableRow><TableCell colSpan={7} sx={{ textAlign: 'center', color: 'text.secondary', py: 3 }}>Nada pendiente.</TableCell></TableRow>}
                {d.documentos.map((f) => (
                  <TableRow key={f.id} hover>
                    <TableCell sx={{ maxWidth: 260, overflow: 'hidden', textOverflow: 'ellipsis' }}>{f.razon_social}</TableCell>
                    <TableCell>{f.tipo_nombre} {f.folio}</TableCell>
                    <TableCell sx={NUM}>{ddmm(f.emision)}</TableCell>
                    <TableCell sx={NUM}>{ddmm(f.vence)}</TableCell>
                    <TableCell align="right" sx={{ color: f.dias > 0 ? '#b42318' : 'text.secondary', ...NUM }}>{f.dias > 0 ? `${f.dias} de atraso` : f.dias === 0 ? 'vence hoy' : `en ${-f.dias} días`}</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 600, ...NUM }}>{clp(f.monto)}</TableCell>
                    <TableCell padding="none">{esEditor && <Button size="small" onClick={() => marcar(f)} sx={{ fontSize: '0.74rem' }}>{cobrar ? 'Cobrada' : 'Pagada'}</Button>}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </>
          ) : (
            <>
              <TableHead><TableRow sx={{ '& th': { color: 'text.secondary', fontWeight: 600, fontSize: '0.72rem', letterSpacing: '0.06em', textTransform: 'uppercase' } }}>
                <TableCell>{cobrar ? 'Cliente' : 'Proveedor'}</TableCell><TableCell align="right">Documentos</TableCell>
                <TableCell align="right">Vencido</TableCell><TableCell align="right">Atraso máx.</TableCell><TableCell align="right">Total</TableCell>
              </TableRow></TableHead>
              <TableBody>
                {d.por_contraparte.map((x) => (
                  <TableRow key={x.rut} hover>
                    <TableCell>{x.razon_social} <span style={{ color: theme.palette.text.secondary, fontSize: '0.76rem' }}>{x.rut}</span></TableCell>
                    <TableCell align="right">{x.documentos}</TableCell>
                    <TableCell align="right" sx={{ color: x.vencido ? '#b42318' : 'text.secondary', ...NUM }}>{clp(x.vencido)}</TableCell>
                    <TableCell align="right" sx={NUM}>{x.dias_max ? `${x.dias_max} días` : '—'}</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 600, ...NUM }}>{clp(x.monto)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </>
          )}
        </Table>
      </Tarjeta>
    </Box>
  );
}

function CuentaDueno({ slug, onIrConciliacion }) {
  const [d, setD] = useState(null);
  useEffect(() => { api.finanzas.cuentaDueno(slug).then(({ data }) => setD(data)); }, [slug]);
  if (!d) return <CircularProgress size={20} sx={{ m: 'auto' }} />;
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Typography sx={{ fontFamily: SORA, fontWeight: 600, fontSize: '1.3rem' }}>Su cuenta con la empresa</Typography>
      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 2 }}>
        <Tarjeta sx={{ p: 2.5 }}><Etiqueta>Retiros acumulados</Etiqueta>
          <Typography sx={{ fontFamily: SORA, fontWeight: 600, fontSize: '1.6rem', mt: 0.5, ...NUM }}>{clp(d.retiros)}</Typography>
          <Typography sx={{ fontSize: '0.82rem', color: 'text.secondary' }}>Total retirado como ganancia.</Typography></Tarjeta>
        <Tarjeta sx={{ p: 2.5 }}><Etiqueta>Capital invertido</Etiqueta>
          <Typography sx={{ fontFamily: SORA, fontWeight: 600, fontSize: '1.6rem', mt: 0.5, ...NUM }}>{clp(d.capital)}</Typography>
          <Typography sx={{ fontSize: '0.82rem', color: 'text.secondary' }}>Total aportado de su bolsillo.</Typography></Tarjeta>
      </Box>
      <Tarjeta sx={{ overflow: 'auto' }}>
        <Box sx={{ px: 2.5, pt: 2, pb: 1 }}><Etiqueta>Últimos movimientos</Etiqueta></Box>
        <Table size="small" sx={{ '& td': { fontSize: '0.86rem', borderColor: 'divider' } }}>
          <TableBody>
            {d.movimientos.length === 0 && (
              <TableRow><TableCell sx={{ color: 'text.secondary', py: 3, textAlign: 'center' }}>
                Aparecen cuando en la conciliación marca un movimiento como retiro del dueño, aporte de capital o pago de impuestos.{' '}
                <Box component="span" sx={{ color: 'var(--af-color)', fontStyle: 'italic', cursor: 'pointer' }} onClick={onIrConciliacion}>Ir a Conciliación</Box>
              </TableCell></TableRow>
            )}
            {d.movimientos.map((m, i) => (
              <TableRow key={i} hover>
                <TableCell sx={NUM}>{ddmm(m.fecha)}</TableCell>
                <TableCell><Chip size="small" label={m.tipo_nombre} sx={{ height: 20, fontSize: '0.7rem', fontFamily: 'inherit', bgcolor: m.tipo === 'retiro_dueno' ? '#fbe1d1' : 'action.hover' }} /></TableCell>
                <TableCell sx={{ color: 'text.secondary' }}>{m.descripcion}</TableCell>
                <TableCell align="right" sx={{ fontWeight: 600, ...NUM }}>{clp(m.monto)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Tarjeta>
    </Box>
  );
}

export default function FinanzasPage() {
  const navigate = useNavigate();
  const { seccion: param } = useParams();
  const { slug, esEditor } = useWorkspace();
  // La sección viene de la dirección y se elige en el submenú de la barra lateral.
  const seccion = seccionDe('finanzas', param);
  const vista = seccion.slug;
  const irConciliacion = () => navigate('/app/contabilidad/conciliacion');
  const version = useVersionDeConfiguracion();   // una cuenta nueva cambia la caja
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', minWidth: 0, width: '100%' }}>
      <PageHeader title={seccion.label} crumbs={[{ label: 'Finanzas', to: '/app/finanzas' }]} back="/app" backLabel="Inicio" />
      <Box sx={{ flex: 1, minWidth: 0, overflow: 'auto', px: 3, py: 2.5, display: 'flex', flexDirection: 'column', gap: 2 }}>
        {!slug ? (
          <Typography sx={{ m: 'auto', color: 'text.secondary' }}>Primero tiene que crear su empresa en Afable.</Typography>
        ) : (
          <>
            {vista === 'caja' && <Caja key={`caja-${version}`} slug={slug} onIrConciliacion={irConciliacion} />}
            {vista === 'por-cobrar' && <Cuentas key={`cobrar-${version}`} slug={slug} tipo="cobrar" esEditor={esEditor} />}
            {vista === 'por-pagar' && <Cuentas key={`pagar-${version}`} slug={slug} tipo="pagar" esEditor={esEditor} />}
            {vista === 'cuenta-dueno' && <CuentaDueno key={`dueno-${version}`} slug={slug} onIrConciliacion={irConciliacion} />}
          </>
        )}
      </Box>
    </Box>
  );
}
