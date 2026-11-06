/*
 * Tonos de las funcionalidades (30-10-2026). La interfaz es blanco y negro; el color queda solo para lo
 * funcional (etiquetas, pasos, cargas, el ícono de cada tipo de acción) y nunca para decorar. Tonos
 * apagados y terrosos, tomados de la interfaz de producto de harvey.ai (medidos en su Command Center:
 * pizarra #586470, malva #817b92, salvia #939c8f, ladrillo #775c5f), un poco más oscuros para que el
 * texto en ese color se lea sobre blanco.
 *
 * Cada tono trae `color` (ícono o texto) y `suave` (fondo de la ficha o la etiqueta).
 */
export const TONOS = {
  salvia: { color: '#5c7a62', suave: 'rgba(92, 122, 98, 0.13)' },
  pizarra: { color: '#4f6475', suave: 'rgba(79, 100, 117, 0.13)' },
  malva: { color: '#74678e', suave: 'rgba(116, 103, 142, 0.14)' },
  ladrillo: { color: '#8a5a52', suave: 'rgba(138, 90, 82, 0.13)' },
  arena: { color: '#87703f', suave: 'rgba(135, 112, 63, 0.15)' },
  menta: { color: '#3d8571', suave: 'rgba(61, 133, 113, 0.13)' },
  neutro: { color: 'var(--af-acento, #0b0b0f)', suave: 'rgba(127, 127, 127, 0.12)' },
};

// Un tono por módulo: se repite en su etiqueta del chat, su ficha, su agente y sus tarjetas.
const TONO_MODULO = { ventas: 'salvia', compras: 'pizarra', inventario: 'arena', contabilidad: 'malva', finanzas: 'menta' };
export const tonoModulo = (slug) => TONOS[TONO_MODULO[slug]] || TONOS.neutro;

// Un tono por tipo de hecho de "Lo que hizo hoy" (finanzas/actividad.py).
const TONO_HECHO = {
  orden: 'salvia', pago: 'menta', entrega: 'arena', factura: 'malva', carga: 'arena', cartola: 'pizarra',
  stock: 'arena', automatizacion: 'pizarra',
};
export const tonoHecho = (tipo) => TONOS[TONO_HECHO[tipo]] || TONOS.neutro;

// Las etapas de un documento de Ventas o Compras: el tono dice en qué punto del camino está.
export function tonoEtapa(etapa = '') {
  const e = etapa.toLowerCase();
  if (/anulad|cancelad|rechazad|devuel/.test(e)) return TONOS.ladrillo;
  if (/falta|parcial/.test(e)) return TONOS.arena;
  if (/facturad/.test(e)) return TONOS.menta;
  if (/entregad|recibid/.test(e)) return TONOS.salvia;
  if (/orden/.test(e)) return TONOS.malva;
  if (/cotizaci|solicitud/.test(e)) return TONOS.pizarra;
  return TONOS.neutro;
}
