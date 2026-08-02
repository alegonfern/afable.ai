import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box, Button, CircularProgress, Menu, MenuItem, TextField, Typography, useTheme,
} from '@mui/material';
import { Bot, ChevronDown, Plus, Search, Settings2, Star } from 'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../../services/api';
import { useWorkspace } from '../../context/WorkspaceContext';

const PESTANAS = [
  { value: 'favoritos', label: 'Favoritos' },
  { value: 'todos', label: 'Todos los agentes' },
  { value: 'editables', label: 'Editables por mí' },
];

const ORDENES = [
  { value: 'popularidad', label: 'Por popularidad' },
  { value: 'nombre', label: 'Por nombre' },
  { value: 'reciente', label: 'Más recientes' },
];

/**
 * "Chatear con…": la galeria de Agentes de la vista Trabajo.
 *
 * Buscador, Crear y Gestionar, las tres pestañas, el orden y la grilla de
 * tarjetas con scroll infinito. Los agentes salen del Workspace activo.
 */
/**
 * props:
 *  - onElegir(agente)  Si viene, elegir una tarjeta NO navega: se lo entrega a
 *                      quien monta la vitrina. Es lo que permite usarla dentro
 *                      del chat para conmutar de agente sin perder el hilo.
 *  - embebida          Modo compacto para meterla en un panel: sin el título
 *                      "Chatear con…", sin Crear/Gestionar (que sacan de la
 *                      pantalla) y sin el margen superior de página.
 */
export default function AgentesGaleria({ onElegir, embebida = false, filtrarPorEspacio = false }) {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const navigate = useNavigate();
  const { slug, espacio, espacioSlug } = useWorkspace();
  // Ver todos, sin salir del Espacio: el filtro es de esta vitrina, no del Workspace.
  const [ignorarEspacio, setIgnorarEspacio] = useState(false);
  // El Espacio SOLO acota donde se está trabajando (el compositor del chat). La
  // galería completa es el catálogo de la empresa: filtrarla ahí hacía desaparecer
  // agentes en pantallas que nunca hablaron de Espacios.
  const espacioAplicado = filtrarPorEspacio && !ignorarEspacio ? espacioSlug : null;

  const textMuted = d ? 'rgba(255,255,255,0.66)' : 'rgba(0,0,0,0.62)';
  const bgSuave = d ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.02)';
  const bgTarjeta = d ? '#1a1a1a' : '#ffffff';
  const borde = theme.palette.divider;

  const [pestana, setPestana] = useState('todos');
  const [orden, setOrden] = useState('popularidad');
  const [busqueda, setBusqueda] = useState('');
  const [agentes, setAgentes] = useState([]);
  const [pagina, setPagina] = useState(1);
  const [hayMas, setHayMas] = useState(false);
  const [cargando, setCargando] = useState(true);
  const [puedeCrear, setPuedeCrear] = useState(false);
  const [menuCrear, setMenuCrear] = useState(null);
  const [menuGestionar, setMenuGestionar] = useState(null);
  const [menuOrden, setMenuOrden] = useState(null);

  const centinela = useRef(null);

  const cargar = useCallback(async (nuevaPagina) => {
    if (!slug) return;
    try {
      setCargando(true);
      const { data } = await api.getAgentGallery({
        workspace: slug, tab: pestana, orden, q: busqueda.trim(), page: nuevaPagina,
        // Con un Espacio activo se ofrecen SOLO sus agentes: es la mitad visible
        // de que el Espacio decida qué datos alcanza cada agente.
        espacio: espacioAplicado || undefined,
      });
      setAgentes((previos) => (nuevaPagina === 1 ? data.results : [...previos, ...data.results]));
      setHayMas(data.has_next);
      setPuedeCrear(data.can_create);
      setPagina(nuevaPagina);
    } catch {
      toast.error('No se pudieron cargar los agentes.');
    } finally {
      setCargando(false);
    }
  }, [slug, pestana, orden, busqueda, espacioAplicado]);

  // Cada cambio de pestaña, orden o búsqueda vuelve a la primera página.
  useEffect(() => {
    const t = setTimeout(() => cargar(1), busqueda ? 300 : 0);
    return () => clearTimeout(t);
  }, [cargar, busqueda]);

  // Scroll infinito: cuando el centinela entra en pantalla, se pide la siguiente.
  useEffect(() => {
    if (!hayMas || cargando) return undefined;
    const nodo = centinela.current;
    if (!nodo) return undefined;
    const observador = new IntersectionObserver((entradas) => {
      if (entradas[0].isIntersecting) cargar(pagina + 1);
    }, { rootMargin: '200px' });
    observador.observe(nodo);
    return () => observador.disconnect();
  }, [hayMas, cargando, pagina, cargar]);

  const alternarFavorito = async (agente, e) => {
    e.stopPropagation();
    const marcar = !agente.is_favorite;
    setAgentes((previos) =>
      previos.map((a) => (a.id === agente.id ? { ...a, is_favorite: marcar } : a)),
    );
    try {
      if (marcar) await api.favoriteAgent(agente.id, slug);
      else await api.unfavoriteAgent(agente.id, slug);
      if (pestana === 'favoritos' && !marcar) {
        setAgentes((previos) => previos.filter((a) => a.id !== agente.id));
      }
    } catch {
      setAgentes((previos) =>
        previos.map((a) => (a.id === agente.id ? { ...a, is_favorite: !marcar } : a)),
      );
      toast.error('No se pudo cambiar el favorito.');
    }
  };

  const chatear = (agente) => {
    if (onElegir) { onElegir({ id: agente.id, name: agente.name }); return; }
    navigate('/app/chat', { state: { agentId: agente.id, agentName: agente.name } });
  };

  const botonSx = {
    px: 1.75, py: 0.75, borderRadius: '8px', textTransform: 'none',
    fontSize: '0.875rem', fontWeight: 600, whiteSpace: 'nowrap',
    color: theme.palette.text.primary,
    border: `1px solid ${borde}`,
    bgcolor: bgTarjeta,
    '&:hover': { bgcolor: bgSuave },
  };

  // Los mas usados encabezan la lista: es lo primero que alguien busca.
  const masUsados = orden === 'popularidad' && !busqueda && pestana === 'todos'
    ? agentes.filter((a) => a.conversations > 0).slice(0, 3)
    : [];
  const resto = agentes.filter((a) => !masUsados.some((m) => m.id === a.id));

  const Tarjeta = ({ agente }) => (
    <Box
      onClick={() => chatear(agente)}
      sx={{
        p: 2, borderRadius: '10px', cursor: 'pointer',
        border: `1px solid ${borde}`, bgcolor: bgTarjeta,
        transition: 'border-color .15s, background-color .15s',
        '&:hover': { borderColor: d ? 'rgba(255,255,255,0.18)' : 'rgba(0,0,0,0.18)' },
        display: 'flex', flexDirection: 'column', gap: 1.25, minHeight: 118,
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1.25 }}>
        <Box sx={{
          width: 34, height: 34, borderRadius: '9px', flexShrink: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          bgcolor: 'rgba(88, 106, 208, 0.14)', color: '#9BA6E3',
        }}>
          <Bot size={18} />
        </Box>
        <Box sx={{ minWidth: 0, flex: 1 }}>
          <Typography sx={{ fontSize: '0.9375rem', fontWeight: 600, lineHeight: 1.3, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {agente.name}
          </Typography>
          <Typography sx={{ fontSize: '0.8125rem', color: textMuted, lineHeight: 1.3 }}>
            {agente.author}
          </Typography>
        </Box>
        <Box
          onClick={(e) => alternarFavorito(agente, e)}
          title={agente.is_favorite ? 'Quitar de favoritos' : 'Marcar como favorito'}
          sx={{
            display: 'flex', p: 0.5, borderRadius: '6px', flexShrink: 0, cursor: 'pointer',
            color: agente.is_favorite ? '#f0b429' : textMuted,
            '&:hover': { bgcolor: bgSuave },
          }}
        >
          <Star size={15} fill={agente.is_favorite ? '#f0b429' : 'none'} />
        </Box>
      </Box>
      <Typography sx={{
        fontSize: '0.875rem', color: textMuted, lineHeight: 1.45,
        display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden',
      }}>
        {agente.description || 'Sin descripción.'}
      </Typography>
    </Box>
  );

  // En el selector del compositor no hacen falta tarjetas: lo que se necesita es
  // reconocer al agente y elegirlo. Una fila por agente entra en el alto del panel
  // sin scrollear, que es justamente lo que hacía aparecer la barra.
  const Fila = ({ agente }) => (
    <Box
      onClick={() => chatear(agente)}
      sx={{
        display: 'flex', alignItems: 'center', gap: 1.25,
        px: 1, py: 0.75, borderRadius: '8px', cursor: 'pointer',
        '&:hover': { bgcolor: bgSuave },
      }}
    >
      <Box sx={{
        width: 26, height: 26, borderRadius: '7px', flexShrink: 0,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        bgcolor: 'rgba(88, 106, 208, 0.14)', color: '#9BA6E3',
      }}>
        <Bot size={14} />
      </Box>
      <Typography sx={{
        fontSize: '0.875rem', fontWeight: 600, flexShrink: 0, maxWidth: 190,
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
      }}>
        {agente.name}
      </Typography>
      <Typography sx={{
        fontSize: '0.8125rem', color: textMuted, flex: 1, minWidth: 0,
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
      }}>
        {agente.description || 'Sin descripción.'}
      </Typography>
      <Box
        onClick={(e) => alternarFavorito(agente, e)}
        title={agente.is_favorite ? 'Quitar de favoritos' : 'Marcar como favorito'}
        sx={{
          display: 'flex', p: 0.4, borderRadius: '6px', flexShrink: 0, cursor: 'pointer',
          color: agente.is_favorite ? '#f0b429' : textMuted,
          '&:hover': { bgcolor: bgSuave },
        }}
      >
        <Star size={14} fill={agente.is_favorite ? '#f0b429' : 'none'} />
      </Box>
    </Box>
  );

  const Grilla = ({ items }) => (embebida ? (
    <Box sx={{ display: 'flex', flexDirection: 'column', mt: 0.5 }}>
      {items.map((a) => <Fila key={a.id} agente={a} />)}
    </Box>
  ) : (
    <Box sx={{
      display: 'grid', gap: 1.5, mt: 1.5,
      gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr', lg: 'repeat(3, 1fr)' },
    }}>
      {items.map((a) => <Tarjeta key={a.id} agente={a} />)}
    </Box>
  ));

  const Grupo = ({ titulo }) => (embebida ? null : (
    <Typography sx={{ fontSize: '1rem', fontWeight: 600, mt: 3.5 }}>{titulo}</Typography>
  ));

  return (
    <Box sx={{ mt: embebida ? 0 : 6 }}>
      {!embebida && (
        <Typography sx={{ fontSize: '1.125rem', fontWeight: 600 }}>Chatear con…</Typography>
      )}

      {/* Buscador + Crear + Gestionar */}
      <Box sx={{ display: 'flex', gap: 1.25, mt: embebida ? 0 : 1.5, alignItems: 'stretch' }}>
        <TextField
          value={busqueda}
          onChange={(e) => setBusqueda(e.target.value)}
          placeholder="Buscar"
          fullWidth size="small"
          InputProps={{
            endAdornment: <Search size={16} color={textMuted} />,
            sx: {
              bgcolor: bgSuave, borderRadius: '8px', fontSize: '0.9375rem',
              '& fieldset': { borderColor: borde },
              '&.Mui-focused fieldset': { borderColor: '#586AD0' },
            },
          }}
        />
        {!embebida && (
          <>
            <Button
              onClick={(e) => setMenuCrear(e.currentTarget)}
              startIcon={<Plus size={15} />} endIcon={<ChevronDown size={14} />}
              disabled={!puedeCrear}
              sx={botonSx}
            >
              Crear
            </Button>
            <Button
              onClick={(e) => setMenuGestionar(e.currentTarget)}
              startIcon={<Settings2 size={15} />} endIcon={<ChevronDown size={14} />}
              sx={botonSx}
            >
              Gestionar
            </Button>
          </>
        )}
      </Box>

      {/* Que la lista venga acotada tiene que decirse, y tiene que poder deshacerse:
          una lista corta sin explicación se lee como "faltan agentes". */}
      {filtrarPorEspacio && espacio && (
        <Box sx={{
          display: 'flex', alignItems: 'center', gap: 1, mt: 1,
          fontSize: '0.78rem', color: textMuted,
        }}>
          <span>
            {ignorarEspacio
              ? `Mostrando todos los agentes de la empresa.`
              : `Solo los agentes de ${espacio.name}.`}
          </span>
          <Box
            component="button"
            onClick={() => setIgnorarEspacio((v) => !v)}
            sx={{
              border: 'none', bgcolor: 'transparent', p: 0, cursor: 'pointer',
              fontFamily: 'inherit', fontSize: 'inherit', fontWeight: 600,
              color: '#9BA6E3', '&:hover': { textDecoration: 'underline' },
            }}
          >
            {ignorarEspacio ? `Volver a ${espacio.name}` : 'Ver todos'}
          </Box>
        </Box>
      )}

      {/* Pestañas + orden */}
      <Box sx={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        gap: 2, mt: embebida ? 1.25 : 2.5, borderBottom: `1px solid ${borde}`,
      }}>
        <Box sx={{ display: 'flex', gap: 0.5 }}>
          {PESTANAS.map((p) => {
            const activa = pestana === p.value;
            return (
              <Box
                key={p.value}
                component="button"
                onClick={() => setPestana(p.value)}
                sx={{
                  border: 'none', bgcolor: 'transparent', cursor: 'pointer',
                  px: 1.5, pb: 1.25, pt: 0.5, fontFamily: 'inherit',
                  fontSize: '0.9375rem', fontWeight: activa ? 600 : 500,
                  color: activa ? theme.palette.text.primary : textMuted,
                  borderBottom: `2px solid ${activa ? '#586AD0' : 'transparent'}`,
                  mb: '-1px',
                  '&:hover': { color: theme.palette.text.primary },
                }}
              >
                {p.label}
              </Box>
            );
          })}
        </Box>
        {!embebida && (
          <Button
            onClick={(e) => setMenuOrden(e.currentTarget)}
            endIcon={<ChevronDown size={14} />}
            sx={{ ...botonSx, mb: 1, fontWeight: 500 }}
          >
            {(ORDENES.find((o) => o.value === orden) || ORDENES[0]).label}
          </Button>
        )}
      </Box>

      {/* Grilla */}
      {masUsados.length > 0 && (
        <>
          <Grupo titulo="Más usados" />
          <Grilla items={masUsados} />
        </>
      )}

      {resto.length > 0 && (
        <>
          {masUsados.length > 0 && <Grupo titulo="Todos" />}
          <Grilla items={resto} />
        </>
      )}

      {!cargando && agentes.length === 0 && (
        <Typography sx={{ color: textMuted, fontSize: '0.9375rem', py: 4 }}>
          {pestana === 'favoritos'
            ? 'Todavía no marcó ningún agente como favorito.'
            : pestana === 'editables'
              ? 'No hay agentes creados por usted.'
              : 'No hay agentes que coincidan con la búsqueda.'}
        </Typography>
      )}

      {/* Centinela del scroll infinito */}
      <Box ref={centinela} sx={{ display: 'flex', justifyContent: 'center', py: embebida ? 0.5 : 3 }}>
        {cargando && <CircularProgress size={22} sx={{ color: '#586AD0' }} />}
      </Box>

      <Menu anchorEl={menuCrear} open={Boolean(menuCrear)} onClose={() => setMenuCrear(null)}>
        <MenuItem onClick={() => { setMenuCrear(null); navigate('/app/agentes'); }} sx={{ fontSize: '0.9375rem' }}>
          Agente nuevo
        </MenuItem>
        <MenuItem onClick={() => { setMenuCrear(null); navigate('/app/home'); }} sx={{ fontSize: '0.9375rem' }}>
          Desde un agente existente
        </MenuItem>
      </Menu>

      <Menu anchorEl={menuGestionar} open={Boolean(menuGestionar)} onClose={() => setMenuGestionar(null)}>
        <MenuItem onClick={() => { setMenuGestionar(null); navigate('/app/agentes'); }} sx={{ fontSize: '0.9375rem' }}>
          Ver todos los agentes
        </MenuItem>
        <MenuItem onClick={() => { setMenuGestionar(null); navigate('/app/contexto'); }} sx={{ fontSize: '0.9375rem' }}>
          Espacios y conexiones
        </MenuItem>
      </Menu>

      <Menu anchorEl={menuOrden} open={Boolean(menuOrden)} onClose={() => setMenuOrden(null)}>
        {ORDENES.map((o) => (
          <MenuItem
            key={o.value}
            selected={o.value === orden}
            onClick={() => { setOrden(o.value); setMenuOrden(null); }}
            sx={{ fontSize: '0.9375rem' }}
          >
            {o.label}
          </MenuItem>
        ))}
      </Menu>
    </Box>
  );
}
