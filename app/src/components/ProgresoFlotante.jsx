import { useEffect, useState } from 'react';
import { AnimatePresence } from 'framer-motion';
import { Box } from '@mui/material';
import PasosDelChat from './PasosDelChat';
import { MotionBox, EASE } from './Animado';

/*
 * Los pasos de una tarea pesada fuera del chat (25-10-2026): cargar los libros del SII, sugerir
 * categorías con IA, subir una cartola, probar una automatización. La pantalla envuelve su llamada
 * con `conPasos([...pasos], () => api...)` y abajo a la derecha aparece "Trabajando…" con cada paso,
 * el signo girando en el que corre y su ✓ al terminar; al final queda "Hizo N pasos" un momento.
 *
 * Los pasos son las etapas reales de lo que hace el servidor; como la llamada no las va avisando,
 * avanzan con el tiempo y el último queda corriendo hasta que el servidor responde.
 */

const EVENTO = 'afable-progreso';
const CADA = 900;

export async function conPasos(pasos, tarea) {
  const id = Date.now() + Math.random();
  window.dispatchEvent(new CustomEvent(EVENTO, { detail: { id, pasos, estado: 'corriendo' } }));
  try {
    const resultado = await tarea();
    window.dispatchEvent(new CustomEvent(EVENTO, { detail: { id, estado: 'listo' } }));
    return resultado;
  } catch (e) {
    window.dispatchEvent(new CustomEvent(EVENTO, { detail: { id, estado: 'error' } }));
    throw e;
  }
}

export default function ProgresoFlotante() {
  const [tarea, setTarea] = useState(null);     // { id, pasos, estado, visibles }

  useEffect(() => {
    const alAvisar = (e) => {
      const { id, pasos, estado } = e.detail;
      if (estado === 'corriendo') setTarea({ id, pasos, estado, visibles: 1 });
      // Si el servidor terminó antes de mostrar todos los pasos, los que faltan se marcan rápido
      // ('terminando') en vez de saltar directo al final.
      else if (estado === 'listo') setTarea((t) => (t && t.id === id ? { ...t, estado: t.visibles < t.pasos.length ? 'terminando' : 'listo' } : t));
      else setTarea((t) => (t && t.id === id ? { ...t, estado } : t));
    };
    window.addEventListener(EVENTO, alAvisar);
    return () => window.removeEventListener(EVENTO, alAvisar);
  }, []);

  // Mientras corre, un paso más cada CADA ms; el último espera al servidor. Terminando, más rápido.
  useEffect(() => {
    if (!tarea || !['corriendo', 'terminando'].includes(tarea.estado)) return undefined;
    if (tarea.visibles >= tarea.pasos.length) {
      if (tarea.estado === 'terminando') setTarea((x) => (x && x.id === tarea.id ? { ...x, estado: 'listo' } : x));
      return undefined;
    }
    const t = setTimeout(() => setTarea((x) => (x && x.id === tarea.id ? { ...x, visibles: x.visibles + 1 } : x)),
      tarea.estado === 'terminando' ? 350 : CADA);
    return () => clearTimeout(t);
  }, [tarea]);

  // Terminada, se queda un momento plegada y se va. Si falló, se va enseguida: el error lo dice la pantalla.
  useEffect(() => {
    if (!tarea || ['corriendo', 'terminando'].includes(tarea.estado)) return undefined;
    const t = setTimeout(() => setTarea((x) => (x && x.id === tarea.id ? null : x)), tarea.estado === 'listo' ? 2600 : 300);
    return () => clearTimeout(t);
  }, [tarea]);

  return (
    <Box sx={{ position: 'fixed', right: 24, bottom: 88, zIndex: 1400, width: 320, maxWidth: 'calc(100vw - 32px)', pointerEvents: 'none' }}>
      <AnimatePresence>
        {tarea && (
          <MotionBox key={tarea.id} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 8 }}
            transition={{ duration: 0.3, ease: EASE }}
            sx={{ pointerEvents: 'auto', boxShadow: '0 12px 32px -12px rgba(4, 23, 43, 0.28)', borderRadius: '12px' }}>
            <PasosDelChat pasos={tarea.pasos.slice(0, tarea.visibles)} trabajando={tarea.estado !== 'listo' && tarea.estado !== 'error'} />
          </MotionBox>
        )}
      </AnimatePresence>
    </Box>
  );
}
