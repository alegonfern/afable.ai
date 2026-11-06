import { api } from './api';

/*
 * "Revisa la respuesta de Afable" (25-10-2026). El servidor deja la notificación en la campana
 * cada vez que el chat responde (notificaciones/avisos.avisar_respuesta). Queda SIN LEER: la
 * campana muestra su número en rojo hasta que la persona la abre. Si además está en otra pestaña
 * o ventana, salta la notificación del navegador, que al hacerle clic vuelve a la conversación.
 */

// Se pide al enviar el primer mensaje: el navegador solo deja pedirlo tras una acción de la persona.
export function pedirPermisoDeAvisos() {
  try {
    if ('Notification' in window && Notification.permission === 'default') Notification.requestPermission();
  } catch { /* navegador sin notificaciones */ }
}

const texto = (detalle) => (detalle || '').replace(/[#*_`>[\]]/g, '').replace(/\s+/g, ' ').trim()
  .replace(/^[-•]\s*/, '').slice(0, 140);

export function avisarRespuesta({ notificacionId, conversacionId, detalle, alAbrir }) {
  if (!notificacionId) return;
  const mirando = document.visibilityState === 'visible' && document.hasFocus();
  if (!mirando) {
    try {
      if ('Notification' in window && Notification.permission === 'granted') {
        const aviso = new Notification('Revisa la respuesta de Afable', {
          body: texto(detalle), icon: '/afable-icon.svg', tag: `afable-conv-${conversacionId}`,
        });
        aviso.onclick = () => {
          window.focus();
          alAbrir?.();
          api.marcarNotificacionLeida(notificacionId).catch(() => {});
          aviso.close();
        };
      }
    } catch { /* sin permiso o sin soporte: queda en la campana */ }
  }
  // La campana se pone al día ahora (con su número), no en su próxima vuelta.
  window.dispatchEvent(new Event('afable-notificaciones'));
}
