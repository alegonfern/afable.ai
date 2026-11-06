import { useEffect, useState } from 'react';
import { api } from '../../services/api';

/*
 * Si el facturador electrónico nativo está habilitado para la empresa (26-10-2026). Se pregunta
 * una vez por empresa y se recuerda mientras dure la página: lo usan el menú y Ventas.
 */
const recordado = {};

export function useDteDisponible(slug) {
  const [disponible, setDisponible] = useState(() => recordado[slug] ?? false);
  useEffect(() => {
    if (!slug) return;
    if (slug in recordado) { setDisponible(recordado[slug]); return; }
    let vivo = true;
    api.dte.estado(slug)
      .then(({ data }) => { recordado[slug] = !!data.disponible; if (vivo) setDisponible(recordado[slug]); })
      .catch(() => { /* sin red o servidor reiniciando: no se recuerda, se vuelve a preguntar */ });
    return () => { vivo = false; };
  }, [slug]);
  return disponible;
}
