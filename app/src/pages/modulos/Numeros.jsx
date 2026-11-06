import { useCallback, useEffect, useState } from 'react';
import {
  Box, Button, Chip, CircularProgress, Table, TableBody, TableCell, TableHead, TableRow,
  Tooltip, Typography, useTheme,
} from '@mui/material';
import { AlertTriangle, ArrowRight, Check } from 'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../../services/api';
import { BarraQueCrece, Numero } from '../../components/Animado';
import { TONOS } from '../../theme/tonos';

/*
 * Los números del mes (PMV financiero, etapa 2, 17-10-2026): Resumen, Impuestos (F29),
 * Categorías y Proyectos. Todo se calcula en el servidor desde los documentos del SII.
 * Ingresos y gastos van sin IVA y antes del impuesto a la renta; el F29 es una provisión.
 */

const clp = (n) => `${n < 0 ? '−' : ''}$${Math.abs(Math.round(Number(n) || 0)).toLocaleString('es-CL')}`;
const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
const MESES_LARGO = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];
const fechaLarga = (iso) => {
  const [a, m, d] = iso.split('-').map(Number);
  return `${d} de ${MESES_LARGO[m - 1].toLowerCase()} de ${a}`;
};
const SORA = "'Sora', sans-serif";
const MONO = { fontVariantNumeric: 'tabular-nums' };

function Tarjeta({ children, sx }) {
  return <Box sx={{ border: '1px solid', borderColor: 'divider', borderRadius: '14px', bgcolor: 'background.paper', ...sx }}>{children}</Box>;
}

function Etiqueta({ children }) {
  return <Typography sx={{ fontSize: '0.74rem', fontWeight: 600, letterSpacing: '0.07em', textTransform: 'uppercase', color: 'text.secondary' }}>{children}</Typography>;
}

/* Barras de los 12 meses: el elegido en índigo, los anteriores en gris, los futuros apagados. */
// Cada serie en su tono (30-10-2026, theme/tonos.js): el mes elegido en el tono y los demás en su versión suave.
function Barras({ valores, elegido, tono = TONOS.neutro }) {
  const max = Math.max(1, ...valores.map((v) => Math.abs(v ?? 0)));
  return (
    <Box sx={{ display: 'flex', alignItems: 'flex-end', gap: '3px', height: 54, mt: 2 }}>
      {valores.map((v, i) => (
        <Tooltip key={i} title={`${MESES[i]}: ${v == null ? 'sin datos' : clp(v)}`} arrow>
          <BarraQueCrece i={i} sx={{
            flex: 1, borderRadius: '3px 3px 0 0',
            height: v == null ? 4 : `${Math.max(6, (Math.abs(v) / max) * 100)}%`,
            bgcolor: i === elegido ? tono.color : v == null ? 'action.hover' : v < 0 ? '#e7b4b0' : tono.suave,
          }} />
        </Tooltip>
      ))}
    </Box>
  );
}

export function ResumenVista({ slug, onVerImpuestos }) {
  const [anio, setAnio] = useState(new Date().getFullYear());
  const [datos, setDatos] = useState(null);
  const [f29, setF29] = useState(null);
  const [mes, setMes] = useState(null);

  useEffect(() => {
    Promise.all([api.finanzas.resumen(slug, anio), api.finanzas.impuestos(slug, anio)]).then(([r, i]) => {
      setDatos(r.data);
      setF29(i.data);
      const conDatos = r.data.meses.filter((m) => m.con_datos);
      setMes(conDatos.length ? conDatos[conDatos.length - 1].mes : new Date().getMonth() + 1);
      if (!conDatos.length && r.data.anios.length && !r.data.anios.includes(anio)) setAnio(r.data.anios[0]);
    });
  }, [slug, anio]);

  if (!datos || mes == null) return <CircularProgress size={20} sx={{ m: 'auto' }} />;
  const m = datos.meses[mes - 1];
  const previo = mes > 1 ? datos.meses[mes - 2] : null;
  const variacion = (actual, antes) => (antes && antes !== 0 ? Math.round(((actual - antes) / Math.abs(antes)) * 100) : null);
  const declaracion = f29?.meses.find((x) => x.mes === mes);
  const conDatos = datos.meses.filter((x) => x.con_datos);

  const Cifra = ({ titulo, valor, serie, antes, grande, color, tono }) => {
    const v = variacion(valor, antes);
    return (
      <Box sx={{ p: 2.5, minWidth: 0 }}>
        <Etiqueta>{titulo}</Etiqueta>
        <Typography sx={{ fontFamily: SORA, fontWeight: 600, fontSize: grande ? '2.3rem' : '1.55rem', mt: 0.75, color: color || 'text.primary', fontStyle: color === 'var(--af-color)' ? 'italic' : 'normal', letterSpacing: '-0.02em', ...MONO }} noWrap>
          <Numero valor={valor} formato={(x) => `${grande && valor > 0 ? '+' : ''}${clp(x)}`} />
        </Typography>
        {v != null && (
          <Chip size="small" label={`${v >= 0 ? '▲' : '▼'} ${Math.abs(v)}% vs ${MESES[mes - 2]}`}
            sx={{ height: 20, fontSize: '0.7rem', mt: 0.5, bgcolor: 'action.hover', fontFamily: 'inherit' }} />
        )}
        <Barras valores={serie} elegido={mes - 1} tono={tono} />
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 0.5 }}>
          <Typography sx={{ fontSize: '0.7rem', color: 'text.disabled' }}>ene</Typography>
          <Typography sx={{ fontSize: '0.7rem', color: 'text.disabled' }}>dic</Typography>
        </Box>
      </Box>
    );
  };
  const serie = (k) => datos.meses.map((x) => (x.con_datos ? x[k] : null));

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      {/* Mes y año */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
        {conDatos.map((x) => (
          <Chip key={x.mes} label={MESES_LARGO[x.mes - 1]} onClick={() => setMes(x.mes)}
            variant={x.mes === mes ? 'filled' : 'outlined'} sx={{ fontFamily: 'inherit', fontSize: '0.82rem' }} />
        ))}
        <Box sx={{ flex: 1 }} />
        {datos.anios.length > 1 && datos.anios.map((a) => (
          <Chip key={a} label={a} size="small" onClick={() => setAnio(a)} variant={a === anio ? 'filled' : 'outlined'} />
        ))}
      </Box>

      <Tarjeta>
        <Box sx={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', flexWrap: 'wrap', columnGap: 2, px: 2.5, pt: 2, pb: 1, borderBottom: '1px solid', borderColor: 'divider' }}>
          <Typography sx={{ fontFamily: SORA, fontWeight: 600, fontSize: '1.25rem' }}>{MESES_LARGO[mes - 1]} {anio}</Typography>
          <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary' }}>Sin IVA y antes del impuesto a la renta</Typography>
        </Box>
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1.4fr 1fr 1fr' },
          '& > div + div': { borderLeft: { xs: 0, md: '1px solid' }, borderTop: { xs: '1px solid', md: 0 }, borderColor: 'divider' } }}>
          <Cifra titulo="Ganancia" valor={m.ganancia} antes={previo?.ganancia} serie={serie('ganancia')} grande tono={TONOS.menta}
            color={m.ganancia >= 0 ? 'var(--af-color)' : '#b42318'} />
          <Cifra titulo="Ingresos" valor={m.ingresos} antes={previo?.ingresos} serie={serie('ingresos')} tono={TONOS.salvia} />
          <Cifra titulo="Gastos" valor={m.gastos} antes={previo?.gastos} serie={serie('gastos')} tono={TONOS.ladrillo} />
        </Box>
        <Box sx={{ borderTop: '1px solid', borderColor: 'divider', px: 2.5, py: 1 }}>
          {[
            ['Margen neto', m.margen == null ? '—' : `${m.margen > 0 ? '+' : ''}${String(m.margen).replace('.', ',')}%`,
              m.margen == null ? 'Sin ventas este mes.' : `de cada $100 que vendió (sin IVA), quedan $${Math.round(m.margen)}.`],
            [`Resultado de ${anio}`, `${datos.ganancia > 0 ? '+' : ''}${clp(datos.ganancia)}`, 'ganancia acumulada del año, sin IVA.'],
          ].map(([t, v, d]) => (
            <Box key={t} sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr auto', md: '200px 180px 1fr' }, alignItems: 'center', columnGap: 1.5, py: 1, '& > :nth-of-type(3)': { gridColumn: { xs: '1 / -1', md: 'auto' } } }}>
              <Etiqueta>{t}</Etiqueta>
              <Typography sx={{ fontFamily: SORA, fontWeight: 600, fontSize: '1.1rem', ...MONO }}>{v}</Typography>
              <Typography sx={{ fontSize: '0.86rem', color: 'text.secondary' }}>{d}</Typography>
            </Box>
          ))}
          {declaracion && (
            <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr auto', md: '200px 180px 1fr' }, alignItems: 'center', columnGap: 1.5, py: 1, '& > :nth-of-type(3)': { gridColumn: { xs: '1 / -1', md: 'auto' } } }}>
              <Etiqueta>F29 de {MESES[mes - 1]} · a pagar</Etiqueta>
              <Typography sx={{ fontFamily: SORA, fontWeight: 600, fontSize: '1.1rem', color: declaracion.pagado ? 'text.secondary' : 'var(--af-color)', fontStyle: declaracion.pagado ? 'normal' : 'italic', ...MONO }}>
                <Numero valor={declaracion.estimado} formato={clp} />
              </Typography>
              <Typography sx={{ fontSize: '0.86rem', color: 'text.secondary' }}>
                {declaracion.pagado
                  ? `Pagado${declaracion.fecha_pago ? ` el ${fechaLarga(declaracion.fecha_pago)}` : ''}.`
                  : `Vence el ${fechaLarga(declaracion.vence)}. No es suya, es del SII: apártela hoy. `}
                <Box component="span" onClick={onVerImpuestos} sx={{ color: 'var(--af-color)', fontStyle: 'italic', cursor: 'pointer', fontWeight: 500, whiteSpace: 'nowrap' }}>
                  Ver el desglose <ArrowRight size={13} style={{ verticalAlign: '-2px' }} />
                </Box>
              </Typography>
            </Box>
          )}
        </Box>
      </Tarjeta>
      <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary' }}>
        Caja disponible, cuánto puede retirar y los meses de caja llegan con la conciliación bancaria y el módulo Finanzas.
      </Typography>
    </Box>
  );
}

export function ImpuestosVista({ slug, esEditor }) {
  const [anio] = useState(new Date().getFullYear());
  const [datos, setDatos] = useState(null);
  const cargar = useCallback(() => api.finanzas.impuestos(slug, anio).then(({ data }) => setDatos(data)), [slug, anio]);
  useEffect(() => { cargar(); }, [cargar]);

  const marcar = async (fila, pagado) => {
    try {
      const { data } = await api.finanzas.marcarF29(slug, fila.anio, fila.mes,
        pagado ? { pagado: true, monto_pagado: fila.estimado } : { pagado: false });
      setDatos(data);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'No se pudo guardar.');
    }
  };

  if (!datos) return <CircularProgress size={20} sx={{ m: 'auto' }} />;
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25 }}>
        <Typography sx={{ fontFamily: SORA, fontWeight: 600, fontSize: '1.25rem' }}>Historial del F29</Typography>
        <Chip size="small" label="Provisión estimada" sx={{ fontFamily: 'inherit', fontSize: '0.72rem' }} />
      </Box>
      {!datos.tasa_ppm_confirmada && (
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', px: 1.5, py: 1, borderRadius: '10px', bgcolor: '#fbe1d1', color: '#8a5a00', fontSize: '0.84rem' }}>
          <AlertTriangle size={15} /> El PPM se calcula con la tasa sugerida ({String(Number(datos.tasa_ppm)).replace('.', ',')}%). Confirme la tasa de su último F29 en Configuración.
        </Box>
      )}
      <Tarjeta sx={{ overflow: 'auto' }}>
        <Table size="small" sx={{ '& td, & th': { fontSize: '0.86rem', borderColor: 'divider', whiteSpace: 'nowrap' }, '& td': MONO }}>
          <TableHead>
            <TableRow sx={{ '& th': { color: 'text.secondary', fontWeight: 600, fontSize: '0.72rem', letterSpacing: '0.06em', textTransform: 'uppercase' } }}>
              <TableCell>Período</TableCell>
              <TableCell align="right">IVA débito</TableCell>
              <TableCell align="right">IVA crédito</TableCell>
              <TableCell align="right">IVA neto</TableCell>
              <TableCell align="right">PPM</TableCell>
              <TableCell align="right">Ret. honorarios</TableCell>
              <TableCell align="right">Estimado</TableCell>
              <TableCell>Estado</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {datos.meses.length === 0 && (
              <TableRow><TableCell colSpan={8} sx={{ textAlign: 'center', color: 'text.secondary', py: 4 }}>Cargue el Registro de Compras y Ventas para ver la provisión.</TableCell></TableRow>
            )}
            {datos.meses.map((f) => (
              <TableRow key={f.mes} hover>
                <TableCell sx={{ fontWeight: 600 }}>{MESES_LARGO[f.mes - 1].slice(0, 3)} {f.anio}</TableCell>
                <TableCell align="right">{clp(f.iva_debito)}</TableCell>
                <TableCell align="right">{clp(f.iva_credito)}</TableCell>
                <TableCell align="right">
                  {f.remanente > 0
                    ? <Tooltip arrow title="El crédito supera al débito: queda remanente a favor para el mes siguiente."><span>{clp(0)} <Typography component="span" sx={{ fontSize: '0.72rem', color: '#007956' }}>rem. {clp(f.remanente)}</Typography></span></Tooltip>
                    : clp(f.iva_neto)}
                </TableCell>
                <TableCell align="right">{clp(f.ppm)}</TableCell>
                <TableCell align="right">{clp(f.retencion)}</TableCell>
                <TableCell align="right" sx={{ fontWeight: 700 }}>{clp(f.estimado)}</TableCell>
                <TableCell>
                  {f.pagado ? (
                    <Chip size="small" icon={<Check size={12} />} onClick={esEditor ? () => marcar(f, false) : undefined}
                      label={`Pagado ${f.monto_pagado != null ? clp(f.monto_pagado) : ''}${f.fecha_pago ? ` · ${f.fecha_pago.split('-').reverse().join('-')}` : ''}`}
                      sx={{ height: 22, fontSize: '0.72rem', bgcolor: 'action.selected', color: 'text.primary', fontFamily: 'inherit' }} />
                  ) : (
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Chip size="small" label={`Pendiente · vence ${f.vence.split('-').reverse().slice(0, 2).join('-')}`}
                        sx={{ height: 22, fontSize: '0.72rem', bgcolor: 'action.selected', color: 'text.primary', fontFamily: 'inherit' }} />
                      {esEditor && <Button size="small" sx={{ fontSize: '0.74rem', minWidth: 0, py: 0 }} onClick={() => marcar(f, true)}>Marcar pagado</Button>}
                    </Box>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Tarjeta>
      <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary', lineHeight: 1.6 }}>
        IVA débito: el de sus ventas. IVA crédito: el de sus compras. PPM: la tasa configurada sobre los ingresos del mes.
        Vence el día {datos.dia_vencimiento} del mes siguiente (el 12 si no factura electrónicamente). Es una estimación para apartar la plata: la declaración la hace su contador o usted en el SII.
      </Typography>
    </Box>
  );
}

export function CategoriasVista({ slug }) {
  const hoy = new Date();
  const [periodo, setPeriodo] = useState('anio');
  const [datos, setDatos] = useState(null);
  useEffect(() => {
    api.finanzas.porCategoria(slug, { periodo, anio: hoy.getFullYear(), mes: hoy.getMonth() + 1 }).then(({ data }) => setDatos(data));
  }, [slug, periodo]); // eslint-disable-line react-hooks/exhaustive-deps

  const Lista = ({ titulo, tabla, nota }) => (
    <Tarjeta sx={{ overflow: 'hidden' }}>
      <Box sx={{ px: 2.5, pt: 2, pb: 1 }}>
        <Typography sx={{ fontFamily: SORA, fontWeight: 600, fontSize: '1.1rem' }}>{titulo}</Typography>
        <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary' }}>{nota}</Typography>
      </Box>
      <Table size="small" sx={{ '& td, & th': { fontSize: '0.86rem', borderColor: 'divider' } }}>
        <TableHead>
          <TableRow sx={{ '& th': { color: 'text.secondary', fontWeight: 600, fontSize: '0.72rem', letterSpacing: '0.06em', textTransform: 'uppercase' } }}>
            <TableCell>Categoría</TableCell><TableCell align="right">Monto</TableCell>
            <TableCell align="right" sx={{ width: 220 }}>%</TableCell><TableCell align="right">Acum.</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {tabla.filas.length === 0 && <TableRow><TableCell colSpan={4} sx={{ color: 'text.secondary', textAlign: 'center', py: 3 }}>Sin movimientos en el período.</TableCell></TableRow>}
          {tabla.filas.map((f) => (
            <TableRow key={f.categoria} hover>
              <TableCell sx={{ fontWeight: 500, color: f.categoria === 'Sin categoría' ? 'text.secondary' : 'text.primary' }}>{f.categoria}</TableCell>
              <TableCell align="right" sx={{ fontWeight: 600, ...MONO }}>{clp(f.monto)}</TableCell>
              <TableCell align="right">
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, justifyContent: 'flex-end' }}>
                  <Box sx={{ width: 140, height: 6, borderRadius: 3, bgcolor: 'action.hover', overflow: 'hidden' }}>
                    <Box sx={{ width: `${Math.max(0, f.porcentaje)}%`, height: '100%', bgcolor: TONOS.malva.color }} />
                  </Box>
                  <span style={{ minWidth: 40 }}>{String(f.porcentaje).replace('.', ',')}%</span>
                </Box>
              </TableCell>
              <TableCell align="right" sx={{ color: 'text.secondary' }}>{String(f.acumulado).replace('.', ',')}%</TableCell>
            </TableRow>
          ))}
          <TableRow><TableCell sx={{ fontWeight: 700 }}>Total</TableCell><TableCell align="right" sx={{ fontWeight: 700, ...MONO }}>{clp(tabla.total)}</TableCell><TableCell /><TableCell /></TableRow>
        </TableBody>
      </Table>
    </Tarjeta>
  );

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <Typography sx={{ fontFamily: SORA, fontWeight: 600, fontSize: '1.25rem', flex: 1 }}>¿En qué se va la plata?</Typography>
        {[['mes', MESES_LARGO[hoy.getMonth()]], ['anio', String(hoy.getFullYear())], ['todo', 'Todo']].map(([k, l]) => (
          <Chip key={k} label={l} onClick={() => setPeriodo(k)} variant={periodo === k ? 'filled' : 'outlined'} sx={{ fontFamily: 'inherit' }} />
        ))}
      </Box>
      {!datos ? <CircularProgress size={20} /> : (
        <>
          <Lista titulo="Gasto por categoría" tabla={datos.gastos} nota="Con IVA y con las notas de crédito ya restadas." />
          <Lista titulo="Ingreso por categoría" tabla={datos.ingresos} nota="Con IVA y con las notas de crédito ya restadas." />
        </>
      )}
    </Box>
  );
}

export function ProyectosVista({ slug, onConfigurar }) {
  const [datos, setDatos] = useState(null);
  useEffect(() => { api.finanzas.margenProyectos(slug).then(({ data }) => setDatos(data)); }, [slug]);
  if (!datos) return <CircularProgress size={20} sx={{ m: 'auto' }} />;
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
      <Typography sx={{ fontFamily: SORA, fontWeight: 600, fontSize: '1.25rem' }}>¿Qué parte del negocio gana y cuál se lo come?</Typography>
      {datos.proyectos.length === 0 ? (
        <Tarjeta sx={{ p: 4, textAlign: 'center' }}>
          <Typography sx={{ color: 'text.secondary', fontSize: '0.9rem', mb: 1.5 }}>
            Cree sus proyectos (obras, locales, clientes o líneas de producto) y asígneles los documentos para ver el margen de cada uno.
          </Typography>
          <Button variant="outlined" size="small" onClick={onConfigurar}>Crear proyectos</Button>
        </Tarjeta>
      ) : (
        <Tarjeta sx={{ overflow: 'auto' }}>
          <Table size="small" sx={{ '& td, & th': { fontSize: '0.86rem', borderColor: 'divider', whiteSpace: 'nowrap' }, '& td': MONO }}>
            <TableHead>
              <TableRow sx={{ '& th': { color: 'text.secondary', fontWeight: 600, fontSize: '0.72rem', letterSpacing: '0.06em', textTransform: 'uppercase' } }}>
                <TableCell>Proyecto</TableCell><TableCell align="right">Ingresos</TableCell><TableCell align="right">Gastos</TableCell>
                <TableCell align="right">Ganancia</TableCell><TableCell align="right">Margen</TableCell><TableCell align="right">Documentos</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {datos.proyectos.map((p) => (
                <TableRow key={p.id} hover>
                  <TableCell sx={{ fontWeight: 600 }}>{p.nombre}</TableCell>
                  <TableCell align="right">{clp(p.ingresos)}</TableCell>
                  <TableCell align="right">{clp(p.gastos)}</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700, color: p.ganancia < 0 ? '#b42318' : 'text.primary' }}>{clp(p.ganancia)}</TableCell>
                  <TableCell align="right">{p.margen == null ? '—' : `${String(p.margen).replace('.', ',')}%`}</TableCell>
                  <TableCell align="right" sx={{ color: 'text.secondary' }}>{p.documentos}</TableCell>
                </TableRow>
              ))}
              <TableRow>
                <TableCell sx={{ color: 'text.secondary' }}>Sin asignar a un proyecto</TableCell>
                <TableCell align="right" sx={{ color: 'text.secondary' }}>{clp(datos.sin_asignar.ingresos)}</TableCell>
                <TableCell align="right" sx={{ color: 'text.secondary' }}>{clp(datos.sin_asignar.gastos)}</TableCell>
                <TableCell colSpan={3} />
              </TableRow>
            </TableBody>
          </Table>
        </Tarjeta>
      )}
      <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary' }}>Sin IVA. Una factura repartida entre proyectos suma a cada uno según su porcentaje.</Typography>
    </Box>
  );
}
