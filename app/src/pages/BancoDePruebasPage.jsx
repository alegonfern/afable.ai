import { useCallback, useEffect, useState } from 'react';
import {
  Box, Button, CircularProgress, MenuItem, TextField, Typography, useTheme,
} from '@mui/material';
import { toast } from 'react-toastify';
import { api } from '../services/api';
import { useWorkspace } from '../context/WorkspaceContext';

/**
 * El banco de pruebas: llegar a cualquier estado del producto con un botón.
 *
 * Probar Afable de punta a punta significa llegar a estados que cuestan armar a mano —una
 * empresa recién creada, una con carpetas llenas y sin agentes, una con documentos
 * esperando aprobación— y por eso en la práctica no se prueban. Se prueba lo que es fácil
 * de alcanzar, que no es donde están los errores.
 *
 * **No falsea nada.** Cada botón llama exactamente al mismo código que usaría un usuario
 * real. Si `crear_estructura` se rompe, esta pantalla se rompe igual: probar contra un
 * camino distinto del real no prueba nada.
 *
 * El servidor decide quién entra (`CUENTAS_DE_PRUEBA`). Acá el 403 se muestra tal cual, sin
 * esconder la pantalla: si alguien llega por la dirección directa, es mejor que lea por qué
 * no puede a que vea una página en blanco.
 */

const DEMOS = [
  { valor: 'distribuidora', nombre: 'Distribuidora — comparar precios en el tiempo' },
  { valor: 'constructora', nombre: 'Constructora — fechas que se vencen' },
  { valor: 'consultora', nombre: 'Consultora — encontrar por significado' },
];

const RUBROS = [
  { valor: 'general', nombre: 'General' },
  { valor: 'servicios', nombre: 'Servicios o consultoría' },
  { valor: 'comercio', nombre: 'Comercio o retail' },
  { valor: 'manufactura', nombre: 'Manufactura' },
  { valor: 'construccion', nombre: 'Construcción' },
];

// Las que borran van juntas y aparte: no conviene que un botón que vacía carpetas quede
// pegado a uno que solo carga documentos.
const DESTRUCTIVAS = new Set(['quitar_demo', 'vaciar_estructura']);

export default function BancoDePruebasPage() {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const { slug } = useWorkspace();

  const [datos, setDatos] = useState(null);
  const [error, setError] = useState('');
  const [cargando, setCargando] = useState(true);
  const [corriendo, setCorriendo] = useState('');
  const [demo, setDemo] = useState('distribuidora');
  const [rubro, setRubro] = useState('general');

  const textMuted = d ? 'rgba(255,255,255,0.66)' : 'rgba(0,0,0,0.62)';
  const bgSuave = d ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.015)';
  const borde = theme.palette.divider;

  const cargar = useCallback(async () => {
    if (!slug) return;
    setCargando(true);
    try {
      const { data } = await api.getBancoDePruebas(slug);
      setDatos(data);
      setError('');
    } catch (e) {
      setError(e?.response?.data?.detail || 'No se pudo abrir el banco de pruebas.');
    } finally {
      setCargando(false);
    }
  }, [slug]);

  useEffect(() => { cargar(); }, [cargar]);

  const correr = async (accion) => {
    setCorriendo(accion);
    try {
      const { data } = await api.correrEnBancoDePruebas({
        workspace: slug, accion, tipo: demo, rubro,
      });
      setDatos((previo) => ({ ...previo, estado: data.estado }));
      toast.success(data.hecho);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'No se pudo correr.');
    } finally {
      setCorriendo('');
    }
  };

  if (cargando) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', pt: 12 }}>
        <CircularProgress size={26} sx={{ color: '#586AD0' }} />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ maxWidth: 720, mx: 'auto', px: 5, py: 6 }}>
        <Typography sx={{ fontSize: '1.35rem', fontWeight: 700, mb: 1 }}>
          Banco de pruebas
        </Typography>
        <Typography sx={{ color: textMuted, fontSize: '0.9375rem' }}>{error}</Typography>
      </Box>
    );
  }

  const estado = datos?.estado || {};
  const acciones = datos?.acciones || [];

  const Cifra = ({ etiqueta, valor }) => (
    <Box sx={{
      px: 1.75, py: 1.25, borderRadius: '8px', bgcolor: bgSuave,
      border: `1px solid ${borde}`, minWidth: 128,
    }}>
      <Typography sx={{ fontSize: '1.35rem', fontWeight: 600, lineHeight: 1.1 }}>
        {valor}
      </Typography>
      <Typography sx={{ fontSize: '0.78rem', color: textMuted }}>{etiqueta}</Typography>
    </Box>
  );

  const botonSx = (destructiva) => ({
    textTransform: 'none', justifyContent: 'flex-start', px: 1.75, py: 1.1,
    border: `1px solid ${destructiva ? 'rgba(194,91,91,0.5)' : borde}`,
    borderRadius: '8px', color: destructiva ? '#C25B5B' : 'text.primary',
    '&:hover': { borderColor: destructiva ? '#C25B5B' : '#586AD0' },
  });

  return (
    <Box sx={{ maxWidth: 820, mx: 'auto', px: { xs: 2.5, md: 5 }, py: { xs: 4, md: 6 }, width: '100%' }}>
      <Typography sx={{ fontSize: '1.35rem', fontWeight: 700, mb: 0.5 }}>
        Banco de pruebas
      </Typography>
      <Typography sx={{ fontSize: '0.9375rem', color: textMuted, mb: 3 }}>
        Cada botón llama al mismo código que usaría un usuario real. Nada acá está simulado.
      </Typography>

      {/* El estado, primero: es lo que se mira antes y después de tocar un botón. */}
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 3 }}>
        <Cifra etiqueta="Carpetas" valor={estado.carpetas} />
        <Cifra etiqueta="Personales" valor={estado.carpetas_personales} />
        <Cifra etiqueta="Documentos" valor={estado.documentos} />
        <Cifra etiqueta="De ejemplo" valor={estado.documentos_de_ejemplo} />
        <Cifra etiqueta="Agentes" valor={estado.agentes} />
        <Cifra etiqueta="Con carpeta" valor={estado.agentes_con_carpeta} />
        <Cifra etiqueta="Conectores" valor={estado.conectores} />
        <Cifra etiqueta="Personas" valor={estado.personas} />
        <Cifra etiqueta="Por aprobar" valor={estado.publicaciones_pendientes} />
      </Box>

      {/* Lo que el usuario vería ahora en el chat: la forma rápida de comprobar que las
          recomendaciones reaccionan al estado, sin cambiar de pantalla. */}
      <Box sx={{ mb: 3.5, p: 2, borderRadius: '9px', bgcolor: bgSuave, border: `1px solid ${borde}` }}>
        <Typography sx={{
          fontSize: '0.78rem', fontWeight: 600, color: textMuted,
          textTransform: 'uppercase', letterSpacing: '0.06em', mb: 1,
        }}>
          Lo que vería ahora en el chat
        </Typography>
        {(estado.recomendaciones || []).length === 0 ? (
          <Typography sx={{ fontSize: '0.875rem', color: textMuted }}>
            Nada. No le falta nada que valga la pena recomendarle.
          </Typography>
        ) : (
          estado.recomendaciones.map((r) => (
            <Typography key={r} sx={{ fontSize: '0.875rem' }}>· {r}</Typography>
          ))
        )}
      </Box>

      <Box sx={{ display: 'flex', gap: 1.5, mb: 2.5, flexWrap: 'wrap' }}>
        <TextField
          select size="small" label="Empresa de ejemplo" value={demo}
          onChange={(e) => setDemo(e.target.value)} sx={{ minWidth: 300 }}
        >
          {DEMOS.map((o) => <MenuItem key={o.valor} value={o.valor}>{o.nombre}</MenuItem>)}
        </TextField>
        <TextField
          select size="small" label="Rubro de la estructura" value={rubro}
          onChange={(e) => setRubro(e.target.value)} sx={{ minWidth: 220 }}
        >
          {RUBROS.map((o) => <MenuItem key={o.valor} value={o.valor}>{o.nombre}</MenuItem>)}
        </TextField>
      </Box>

      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
        {acciones.map((a) => (
          <Button
            key={a.clave}
            onClick={() => correr(a.clave)}
            disabled={Boolean(corriendo)}
            sx={botonSx(DESTRUCTIVAS.has(a.clave))}
          >
            {corriendo === a.clave ? 'Corriendo…' : a.que_hace}
          </Button>
        ))}
      </Box>
    </Box>
  );
}
