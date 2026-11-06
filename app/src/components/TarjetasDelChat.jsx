import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Cookies from 'js-cookie';
import { Box, Typography } from '@mui/material';
import { useReducedMotion } from 'framer-motion';
import {
  ArrowRight, Boxes, Calculator, Check, Download, FileText, PackageOpen, ShoppingCart, Wallet,
} from 'lucide-react';
import { EASE, MotionBox } from './Animado';
import { useWorkspace } from '../context/WorkspaceContext';
import { toast } from 'react-toastify';
import { api } from '../services/api';
import GuiaLibrosSII from './GuiaLibrosSII';
import IsotipoPensando from './IsotipoPensando';
import { TONOS, tonoModulo } from '../theme/tonos';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001/api/v1';

/*
 * Las tarjetas del chat (25-10-2026): lo que Afable hizo o consultó en el ERP, dibujado
 * como en la animación de la landing (EscenaPrincipal): el documento con sus líneas y su
 * total, lo que pide confirmación con sus dos botones, las cifras y las barras.
 *
 * Llegan armadas del servidor (services/tarjetas_chat.py), con los montos ya formateados;
 * aquí solo se dibujan. Las usan el chat completo y el panel lateral de cada módulo.
 */

const ICONOS = {
  ventas: ShoppingCart, compras: PackageOpen, inventario: Boxes, contabilidad: Calculator, finanzas: Wallet,
};

const sxTarjeta = {
  border: '1px solid', borderColor: 'divider', borderRadius: '14px', bgcolor: 'background.paper',
  overflow: 'hidden', boxShadow: '0 1px 2px rgba(4, 23, 43, 0.04), 0 12px 32px -18px rgba(4, 23, 43, 0.18)',
};

function Cabeza({ t }) {
  const Icono = ICONOS[t.modulo] || ShoppingCart;
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25, px: 2, pt: 1.75, pb: 1.25 }}>
      <Box sx={{ width: 30, height: 30, borderRadius: '9px', flexShrink: 0, display: 'flex', alignItems: 'center',
        justifyContent: 'center', bgcolor: tonoModulo(t.modulo).suave, color: tonoModulo(t.modulo).color }}>
        <Icono size={15} />
      </Box>
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Typography sx={{ fontSize: '0.92rem', fontWeight: 600, lineHeight: 1.3 }}>{t.titulo}</Typography>
        {t.subtitulo && (
          <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary', lineHeight: 1.3 }}>{t.subtitulo}</Typography>
        )}
      </Box>
      {t.estado && <Estado texto={t.estado} />}
    </Box>
  );
}

function Estado({ texto }) {
  return (
    // Negro (25-10-2026): el estado del documento es información, no un acento de la marca.
    <Box component="span" sx={{ flexShrink: 0, px: 1, py: 0.25, borderRadius: '999px', fontSize: '0.72rem', fontWeight: 500,
      bgcolor: 'action.selected', color: 'text.primary', whiteSpace: 'nowrap' }}>
      {texto}
    </Box>
  );
}

function Pie({ t }) {
  const navigate = useNavigate();
  if (!t.enlace && !t.nota) return null;
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, px: 2, py: 1.1, borderTop: '1px solid', borderColor: 'divider',
      bgcolor: 'action.hover' }}>
      <Typography sx={{ flex: 1, fontSize: '0.75rem', color: 'text.secondary' }}>{t.nota}</Typography>
      {t.enlace && (
        <Box component="button" onClick={() => navigate(t.enlace)} sx={{
          display: 'inline-flex', alignItems: 'center', gap: 0.5, border: 0, bgcolor: 'transparent', cursor: 'pointer',
          fontFamily: 'inherit', fontSize: '0.78rem', fontWeight: 500, color: 'text.primary', p: 0,
          '&:hover': { color: 'var(--af-color)' },
        }}>
          Abrir <ArrowRight size={13} />
        </Box>
      )}
    </Box>
  );
}

function Totales({ totales }) {
  if (!totales?.length) return null;
  return (
    <Box sx={{ px: 2, py: 1.25, display: 'flex', flexDirection: 'column', gap: 0.4 }}>
      {totales.map((x) => (
        <Box key={x.etiqueta} sx={{ display: 'flex', justifyContent: 'space-between', gap: 2,
          fontSize: x.destacado ? '0.92rem' : '0.8rem', fontWeight: x.destacado ? 600 : 400,
          color: x.destacado ? 'text.primary' : 'text.secondary', fontVariantNumeric: 'tabular-nums' }}>
          <span>{x.etiqueta}</span><span>{x.valor}</span>
        </Box>
      ))}
    </Box>
  );
}

function Documento({ t }) {
  return (
    <>
      <Cabeza t={t} />
      {t.lineas?.length > 0 && (
        <Box sx={{ mx: 2, borderTop: '1px solid', borderBottom: '1px solid', borderColor: 'divider' }}>
          {t.lineas.map((l, i) => (
            <Box key={i} sx={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 2, py: 0.9, fontSize: '0.82rem',
              borderTop: i ? '1px dashed' : 0, borderColor: 'divider' }}>
              <Box sx={{ minWidth: 0 }}>
                <Typography sx={{ fontSize: '0.84rem', overflow: 'hidden', textOverflow: 'ellipsis' }}>{l.descripcion}</Typography>
                <Typography sx={{ fontSize: '0.74rem', color: 'text.secondary' }}>{l.cantidad} × {l.precio}</Typography>
              </Box>
              <Typography sx={{ fontSize: '0.84rem', fontVariantNumeric: 'tabular-nums', alignSelf: 'center' }}>{l.monto}</Typography>
            </Box>
          ))}
        </Box>
      )}
      <Totales totales={t.totales} />
      <Pie t={t} />
    </>
  );
}

function Confirmar({ t, onResponder }) {
  const [respuesta, setRespuesta] = useState(null);
  const activa = Boolean(onResponder) && !respuesta;
  const responder = (si) => {
    setRespuesta(si ? 'si' : 'no');
    onResponder(si ? 'Sí, confirmo.' : 'No, déjelo así.');
  };
  return (
    <>
      <Cabeza t={t} />
      <Typography sx={{ px: 2, pb: 1.5, fontSize: '0.86rem', lineHeight: 1.6 }}>{t.texto}</Typography>
      <Box sx={{ display: 'flex', gap: 1, px: 2, pb: 1.75 }}>
        <Box component="button" disabled={!activa} onClick={() => responder(true)} sx={{
          display: 'inline-flex', alignItems: 'center', gap: 0.6, px: 1.75, py: 0.8, borderRadius: '10px', cursor: 'pointer',
          fontFamily: 'inherit', fontSize: '0.82rem', fontWeight: 500, border: '1px solid var(--af-acento)',
          bgcolor: 'var(--af-acento)', color: 'var(--af-sobre-acento)', '&:hover:not(:disabled)': { bgcolor: 'var(--af-acento-hover)' },
          '&:disabled': { cursor: 'default', opacity: respuesta === 'si' ? 1 : 0.4 },
        }}>
          {respuesta === 'si' && <Check size={14} />} Confirmar
        </Box>
        <Box component="button" disabled={!activa} onClick={() => responder(false)} sx={{
          px: 1.75, py: 0.8, borderRadius: '10px', cursor: 'pointer', fontFamily: 'inherit', fontSize: '0.82rem',
          border: '1px solid', borderColor: 'divider', bgcolor: 'transparent', color: 'text.primary',
          '&:hover:not(:disabled)': { bgcolor: 'action.hover' },
          '&:disabled': { cursor: 'default', opacity: respuesta === 'no' ? 1 : 0.4 },
        }}>
          Cancelar
        </Box>
      </Box>
    </>
  );
}

// Elegir entre opciones (25-10-2026), por ejemplo facturar lo vendido o lo entregado: cada botón
// manda su respuesta al chat. Como la confirmación, solo se contesta en la última respuesta.
function Elegir({ t, onResponder }) {
  const [elegida, setElegida] = useState(null);
  const activa = Boolean(onResponder) && elegida === null;
  return (
    <>
      <Cabeza t={t} />
      <Typography sx={{ px: 2, pb: 1.5, fontSize: '0.86rem', lineHeight: 1.6 }}>{t.texto}</Typography>
      <Box sx={{ display: 'flex', gap: 1, px: 2, pb: 1.75, flexWrap: 'wrap' }}>
        {(t.opciones || []).map((o, i) => (
          <Box key={o.respuesta} component="button" disabled={!activa} onClick={() => { setElegida(i); onResponder(o.respuesta); }} sx={{
            display: 'inline-flex', alignItems: 'center', gap: 0.6, px: 1.75, py: 0.8, borderRadius: '10px', cursor: 'pointer',
            fontFamily: 'inherit', fontSize: '0.82rem', fontWeight: 500,
            border: '1px solid', borderColor: i === 0 ? 'var(--af-acento)' : 'divider',
            bgcolor: i === 0 ? 'var(--af-acento)' : 'transparent', color: i === 0 ? 'var(--af-sobre-acento)' : 'text.primary',
            '&:hover:not(:disabled)': { bgcolor: i === 0 ? 'var(--af-acento-hover)' : 'action.hover' },
            '&:disabled': { cursor: 'default', opacity: elegida === i ? 1 : 0.4 },
          }}>
            {elegida === i && <Check size={14} />} {o.texto}
          </Box>
        ))}
      </Box>
    </>
  );
}

function Hecho({ t }) {
  return (
    <>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25, px: 2, pt: 1.75, pb: 1 }}>
        <Box sx={{ width: 30, height: 30, borderRadius: '50%', flexShrink: 0, display: 'flex', alignItems: 'center',
          justifyContent: 'center', bgcolor: 'rgba(15, 157, 107, 0.12)', color: '#0f9d6b' }}>
          <Check size={16} strokeWidth={2.5} />
        </Box>
        <Typography sx={{ flex: 1, fontSize: '0.92rem', fontWeight: 600 }}>{t.titulo}</Typography>
        {t.estado && <Estado texto={t.estado} />}
      </Box>
      <Typography sx={{ px: 2, pb: 1.5, pl: 7.25, fontSize: '0.84rem', color: 'text.secondary', lineHeight: 1.55 }}>{t.texto}</Typography>
      <Pie t={t} />
    </>
  );
}

function Lista({ t }) {
  const navigate = useNavigate();
  return (
    <>
      <Cabeza t={t} />
      <Box sx={{ borderTop: '1px solid', borderColor: 'divider' }}>
        {t.filas.map((f, i) => (
          <Box key={i} onClick={f.enlace ? () => navigate(f.enlace) : undefined} sx={{
            display: 'grid', gridTemplateColumns: '1fr auto', gap: 1.5, alignItems: 'center', px: 2, py: 0.9,
            borderTop: i ? '1px solid' : 0, borderColor: 'divider', cursor: f.enlace ? 'pointer' : 'default',
            '&:hover': f.enlace ? { bgcolor: 'action.hover' } : {},
          }}>
            <Box sx={{ minWidth: 0 }}>
              <Typography sx={{ fontSize: '0.84rem', fontWeight: 500 }}>{f.titulo}</Typography>
              {(f.detalle || f.estado) && (
                <Typography sx={{ fontSize: '0.74rem', color: 'text.secondary', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {[f.detalle, f.estado].filter(Boolean).join(' · ')}
                </Typography>
              )}
            </Box>
            {f.valor && <Typography sx={{ fontSize: '0.84rem', fontVariantNumeric: 'tabular-nums' }}>{f.valor}</Typography>}
          </Box>
        ))}
      </Box>
      <Pie t={t} />
    </>
  );
}

function Barras({ t }) {
  const reducido = useReducedMotion();
  return (
    <>
      <Cabeza t={t} />
      <Box sx={{ px: 2, pb: 0.5, display: 'flex', flexDirection: 'column', gap: 1.1 }}>
        {t.barras.map((b, i) => (
          <Box key={i}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 2, fontSize: '0.8rem', mb: 0.5 }}>
              <Box component="span" sx={{ color: 'text.secondary', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{b.etiqueta}</Box>
              <Box component="span" sx={{ fontVariantNumeric: 'tabular-nums', color: b.alerta ? '#b45309' : 'text.primary', whiteSpace: 'nowrap' }}>{b.valor}</Box>
            </Box>
            <Box sx={{ height: 6, borderRadius: 3, bgcolor: 'action.hover', overflow: 'hidden' }}>
              <MotionBox
                initial={reducido ? false : { width: 0 }}
                animate={{ width: `${Math.max(2, (b.proporcion || 0) * 100)}%` }}
                transition={{ duration: 0.7, ease: EASE, delay: 0.08 * i }}
                sx={{ height: '100%', borderRadius: 3, bgcolor: tonoModulo(t.modulo).color }}
              />
            </Box>
          </Box>
        ))}
      </Box>
      <Totales totales={t.totales} />
      <Pie t={t} />
    </>
  );
}

function Cifras({ t }) {
  return (
    <>
      <Cabeza t={t} />
      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, borderTop: '1px solid', borderColor: 'divider' }}>
        {/* Ancho y color por separado: el atajo `1px solid` dentro de un valor responsivo
            pisa el color con el del texto y la línea sale negra. */}
        {t.cifras.map((c, i) => (
          <Box key={i} sx={{ px: 2, py: 1.4, borderStyle: 'solid', borderColor: 'divider', borderWidth: 0,
            borderTopWidth: { xs: i ? 1 : 0, sm: i > 1 ? 1 : 0 }, borderLeftWidth: { xs: 0, sm: i % 2 ? 1 : 0 } }}>
            <Typography sx={{ fontSize: '0.7rem', fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'text.secondary' }}>
              {c.etiqueta}
            </Typography>
            <Typography sx={{ fontSize: c.destacado ? '1.35rem' : '1.1rem', fontWeight: 600, letterSpacing: '-0.02em', mt: 0.25,
              color: c.destacado ? 'var(--af-color)' : 'text.primary', fontStyle: c.destacado ? 'italic' : 'normal', fontVariantNumeric: 'tabular-nums' }}>
              {c.valor}
            </Typography>
            {c.detalle && <Typography sx={{ fontSize: '0.74rem', color: 'text.secondary' }}>{c.detalle}</Typography>}
          </Box>
        ))}
      </Box>
      <Pie t={t} />
    </>
  );
}

/*
 * La factura electrónica emitida, con la animación de la landing (EscenaFacturar) cuando recién
 * se emite: se arma con sus líneas, se firma, va al SII y queda aceptada con su folio. Al volver a
 * abrir la conversación se ve terminada. El PDF se baja con la sesión del usuario.
 */
// Los estados en negro, como el resto (25-10-2026); el avance lo cuenta la barra de abajo.
const FASES = [
  { texto: 'Armando la factura', fondo: 'action.selected', color: 'text.primary' },
  { texto: 'Firmando', fondo: 'action.selected', color: 'text.primary' },
  { texto: 'Enviando al SII', fondo: 'action.selected', color: 'text.primary' },
  { texto: 'Aceptada por el SII', fondo: 'action.selected', color: 'text.primary' },
];

function Factura({ t, animar }) {
  const navigate = useNavigate();
  const { slug } = useWorkspace();
  const reducido = useReducedMotion();
  const [fase, setFase] = useState(animar && !reducido ? 0 : 3);
  useEffect(() => {
    if (!animar || reducido) return undefined;
    const relojes = [900, 1700, 3300].map((ms, i) => setTimeout(() => setFase(i + 1), ms));
    return () => relojes.forEach(clearTimeout);
  }, [animar, reducido]);
  const aceptada = fase === 3;
  const f = FASES[fase];

  const bajarPdf = async () => {
    const res = await fetch(`${API_URL}/workspaces/${slug}/comercial/facturas/${t.documento_id}/pdf/`, {
      headers: { Authorization: `Bearer ${Cookies.get('access_token')}` },
    });
    if (!res.ok) return;
    const url = URL.createObjectURL(await res.blob());
    window.open(url, '_blank', 'noopener');
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  };

  return (
    <Box sx={{ transition: 'box-shadow .4s, border-color .4s', borderRadius: '14px',
      boxShadow: aceptada ? '0 0 0 4px rgba(15, 157, 107, 0.12)' : 'none' }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25, px: 2, pt: 1.75, pb: 1.25 }}>
        <Box sx={{ width: 30, height: 30, borderRadius: '9px', flexShrink: 0, display: 'flex', alignItems: 'center',
          justifyContent: 'center', bgcolor: TONOS.malva.suave, color: TONOS.malva.color }}>
          <FileText size={15} />
        </Box>
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography sx={{ fontSize: '0.92rem', fontWeight: 600, lineHeight: 1.3 }}>
            Factura electrónica{' '}
            <Box component="span" sx={{ transition: 'opacity .4s', opacity: aceptada ? 1 : 0 }}>N° {t.folio}</Box>
          </Typography>
          <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary', lineHeight: 1.3 }}>{t.subtitulo}</Typography>
        </Box>
        <Box component="span" sx={{ flexShrink: 0, display: 'inline-flex', alignItems: 'center', gap: 0.5, px: 1, py: 0.25,
          borderRadius: '999px', fontSize: '0.72rem', fontWeight: 500, bgcolor: f.fondo, color: f.color,
          transition: 'all .3s', whiteSpace: 'nowrap' }}>
          {aceptada && <Check size={12} strokeWidth={3} />} {f.texto}{!aceptada && '…'}
        </Box>
      </Box>
      {t.lineas?.length > 0 && (
        <Box sx={{ mx: 2, borderTop: '1px solid', borderBottom: '1px solid', borderColor: 'divider' }}>
          {t.lineas.map((l, i) => (
            <MotionBox key={i} initial={animar && !reducido ? { opacity: 0, x: -8 } : false} animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.35, ease: EASE, delay: 0.25 + 0.15 * i }}
              sx={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 2, py: 0.9, borderTop: i ? '1px dashed' : 0, borderColor: 'divider' }}>
              <Box sx={{ minWidth: 0 }}>
                <Typography sx={{ fontSize: '0.84rem' }}>{l.descripcion}</Typography>
                <Typography sx={{ fontSize: '0.74rem', color: 'text.secondary' }}>{l.cantidad} × {l.precio}</Typography>
              </Box>
              <Typography sx={{ fontSize: '0.84rem', fontVariantNumeric: 'tabular-nums', alignSelf: 'center' }}>{l.monto}</Typography>
            </MotionBox>
          ))}
        </Box>
      )}
      <Totales totales={t.totales} />
      {/* La barra del envío al SII: se llena mientras "envía" y queda verde al aceptarse. */}
      <Box sx={{ mx: 2, mb: 1.5, height: 4, borderRadius: 2, bgcolor: 'action.hover', overflow: 'hidden' }}>
        <MotionBox
          initial={false}
          animate={{ width: fase >= 3 ? '100%' : fase === 2 ? '85%' : fase === 1 ? '20%' : '0%' }}
          transition={{ duration: fase === 2 ? 1.4 : 0.4, ease: fase === 2 ? 'linear' : EASE }}
          sx={{ height: '100%', bgcolor: aceptada ? '#0f9d6b' : 'var(--af-color)', transition: 'background-color .4s' }}
        />
      </Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, px: 2, py: 1.1, borderTop: '1px solid', borderColor: 'divider', bgcolor: 'action.hover' }}>
        <Typography sx={{ flex: 1, fontSize: '0.75rem', color: 'text.secondary' }}>{t.nota}</Typography>
        <Box component="button" disabled={!aceptada} onClick={bajarPdf} sx={{
          display: 'inline-flex', alignItems: 'center', gap: 0.5, border: 0, bgcolor: 'transparent', cursor: 'pointer',
          fontFamily: 'inherit', fontSize: '0.78rem', fontWeight: 500, color: 'text.primary', p: 0,
          '&:hover:not(:disabled)': { color: 'var(--af-color)' }, '&:disabled': { opacity: 0.4, cursor: 'default' },
        }}>
          <Download size={13} /> PDF
        </Box>
        {t.enlace && (
          <Box component="button" onClick={() => navigate(t.enlace)} sx={{
            display: 'inline-flex', alignItems: 'center', gap: 0.5, border: 0, bgcolor: 'transparent', cursor: 'pointer',
            fontFamily: 'inherit', fontSize: '0.78rem', fontWeight: 500, color: 'text.primary', p: 0,
            '&:hover': { color: 'var(--af-color)' },
          }}>
            Abrir <ArrowRight size={13} />
          </Box>
        )}
      </Box>
    </Box>
  );
}

// La guía para bajar los libros del SII, con la carga incluida: lo subido pasa a la misma
// revisión de Contabilidad, donde se confirma antes de que entre nada.
function Guia({ t }) {
  const navigate = useNavigate();
  const { slug } = useWorkspace();
  const [cargando, setCargando] = useState(false);
  const subir = async (archivo) => {
    setCargando(true);
    try {
      const { data } = await api.finanzas.cargar(slug, archivo);
      if (data.filas_previas?.length) {
        navigate('/app/contabilidad/documentos', { state: { revisarCarga: data.id } });
      } else {
        await api.finanzas.cancelarCarga(slug, data.id).catch(() => {});
        toast.info(data.errores?.length ? 'No se pudo leer ninguna fila nueva del archivo.' : 'Todo lo de ese archivo ya estaba cargado.');
      }
    } catch (e) {
      toast.error(e.response?.data?.detail || 'No se pudo cargar el archivo.');
    } finally {
      setCargando(false);
    }
  };
  return (
    <>
      <Cabeza t={t} />
      <Box sx={{ px: 2, pb: 2 }}>
        <GuiaLibrosSII libroInicial={t.libro} onArchivo={subir} cargando={cargando} />
      </Box>
    </>
  );
}

const POR_TIPO = { elegir: Elegir, guia: Guia, factura: Factura, documento: Documento, confirmar: Confirmar, hecho: Hecho, lista: Lista, barras: Barras, cifras: Cifras };

// `onResponder` solo llega a la última respuesta: una confirmación vieja ya no se contesta.
export default function TarjetasDelChat({ acciones, onResponder, animar = false }) {
  const reducido = useReducedMotion();
  const validas = (acciones || []).filter((t) => POR_TIPO[t?.tipo]);
  // Si en la respuesta hay algo que confirmar o algo hecho, eso es lo que importa: la lista
  // que el modelo consultó para llegar ahí (los pendientes, las órdenes) sobra.
  const decide = validas.some((t) => ['confirmar', 'elegir', 'hecho', 'factura'].includes(t.tipo));
  const visibles = decide ? validas.filter((t) => !['lista', 'cifras', 'barras'].includes(t.tipo)) : validas;
  if (!visibles.length) return null;
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.25, mb: 1.25, maxWidth: 520 }}>
      {visibles.map((t, i) => {
        const Cuerpo = POR_TIPO[t.tipo];
        return (
          <MotionBox key={i} sx={sxTarjeta}
            initial={reducido ? false : { opacity: 0, y: 12, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.45, ease: EASE, delay: 0.12 * i }}>
            {/* Quién hizo el trabajo: el agente del módulo (25-10-2026). */}
            {t.agente && (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, px: 2, py: 0.75, borderBottom: '1px solid', borderColor: 'divider',
                bgcolor: 'action.hover' }}>
                <IsotipoPensando size={11} girando={false} />
                <Typography sx={{ fontSize: '0.72rem', fontWeight: 600, letterSpacing: '0.02em', color: 'text.secondary' }}>{t.agente}</Typography>
              </Box>
            )}
            <Cuerpo t={t} onResponder={onResponder} animar={animar} />
          </MotionBox>
        );
      })}
    </Box>
  );
}
