/**
 * Los últimos errores que tiró el navegador, para mandarlos con el mensaje a soporte.
 *
 * Quien escribe a soporte casi nunca sabe decir qué falló: dice "no me funciona". Esto
 * guarda lo que el navegador ya sabe, para que el mensaje llegue con el error de verdad
 * en vez de con una descripción de segunda mano.
 *
 * Se guarda **en memoria y acotado a los últimos cinco**: no es un registro de auditoría,
 * es lo que hace falta para entender lo que acaba de pasar. Nada de esto sale del
 * navegador hasta que la persona aprieta enviar.
 */

const MAXIMO = 5;
const errores = [];

function anotar(texto) {
  if (!texto) return;
  errores.push(String(texto).slice(0, 300));
  if (errores.length > MAXIMO) errores.shift();
}

export function instalarCapturaDeErrores() {
  window.addEventListener('error', (e) => {
    const donde = (e.filename || '').split('/').pop();
    anotar(`${e.message}${donde ? ` @ ${donde}:${e.lineno}` : ''}`);
  });
  // Una promesa rechazada sin `catch` no dispara 'error' y es de lo más común cuando
  // falla un pedido al backend.
  window.addEventListener('unhandledrejection', (e) => {
    anotar(e.reason?.message || e.reason);
  });
}

export function erroresRecientes() {
  return [...errores];
}
