import { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Volume2, VolumeX, X } from 'lucide-react';

/*
 * Video de bienvenida de la landing (12-11-2026, "Bienvenida Afable v2 (con música)", Fernanda).
 * Aparece como modal al entrar a afable.ai, una sola vez por navegador (se recuerda en localStorage;
 * `?bienvenida` lo muestra siempre, para revisarlo). Se cierra con la X, con Escape o tocando fuera.
 * Intenta partir con sonido. Si el navegador lo bloquea (sin un clic previo en el sitio), parte en
 * silencio y el sonido se activa solo al primer clic, toque o tecla, volviendo al inicio; el botón
 * "Ver con sonido" queda visible mientras tanto.
 */

const CLAVE = 'afable-bienvenida-vista';

function yaLaVio() {
  try {
    if (new URLSearchParams(window.location.search).has('bienvenida')) return false;
    return window.localStorage.getItem(CLAVE) === '1';
  } catch {
    return false;
  }
}

function marcarVista() {
  try { window.localStorage.setItem(CLAVE, '1'); } catch { /* sin almacenamiento: se mostrará otra vez */ }
}

export default function BienvenidaModal() {
  const [abierto, setAbierto] = useState(false);
  const [silencio, setSilencio] = useState(true);
  const video = useRef(null);
  const cerrarBoton = useRef(null);

  useEffect(() => {
    if (yaLaVio()) return undefined;
    const t = setTimeout(() => setAbierto(true), 700);
    return () => clearTimeout(t);
  }, []);

  const cerrar = () => {
    marcarVista();
    setAbierto(false);
  };

  useEffect(() => {
    if (!abierto) return undefined;
    const alTeclear = (e) => { if (e.key === 'Escape') cerrar(); };
    window.addEventListener('keydown', alTeclear);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    cerrarBoton.current?.focus();
    return () => {
      window.removeEventListener('keydown', alTeclear);
      document.body.style.overflow = overflow;
    };
  }, [abierto]);

  // Al abrir intenta reproducir CON sonido. Si el navegador lo bloquea (pasa en la primera visita),
  // parte en silencio y el sonido se activa solo al primer clic, toque o tecla en la página.
  useEffect(() => {
    if (!abierto) return undefined;
    const v = video.current;
    if (!v) return undefined;
    let quitar = () => {};
    v.muted = false;
    v.play().then(() => setSilencio(false)).catch(() => {
      v.muted = true;
      v.play().catch(() => {});
      setSilencio(true);
      const alPrimerGesto = () => {
        quitar();
        v.muted = false;
        v.currentTime = 0;
        v.play().catch(() => {});
        setSilencio(false);
      };
      const eventos = ['pointerdown', 'keydown', 'touchstart'];
      eventos.forEach((e) => document.addEventListener(e, alPrimerGesto, { once: true, capture: true }));
      quitar = () => eventos.forEach((e) => document.removeEventListener(e, alPrimerGesto, { capture: true }));
    });
    return () => quitar();
  }, [abierto]);

  const activarSonido = () => {
    const v = video.current;
    if (!v) return;
    v.muted = false;
    v.currentTime = 0;
    v.play().catch(() => {});
    setSilencio(false);
  };

  const alternarSonido = () => {
    const v = video.current;
    if (!v) return;
    v.muted = !v.muted;
    setSilencio(v.muted);
  };

  return (
    <AnimatePresence>
      {abierto && (
        <motion.div className="lp3-bienvenida" role="dialog" aria-modal="true" aria-label="Video de bienvenida a Afable"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.25 }}
          onClick={cerrar}>
          <motion.div className="lp3-bienvenida__caja" onClick={(e) => e.stopPropagation()}
            initial={{ opacity: 0, y: 16, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 8 }}
            transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}>
            <video ref={video} className="lp3-bienvenida__video" src="/videos/bienvenida.mp4" poster="/videos/bienvenida.jpg"
              playsInline controls={!silencio} preload="auto" />
            {silencio && (
              <button type="button" className="lp3-bienvenida__sonido" onClick={activarSonido}>
                <Volume2 size={18} /> Ver con sonido
              </button>
            )}
            {!silencio && (
              <button type="button" className="lp3-bienvenida__mudo" onClick={alternarSonido} aria-label="Silenciar">
                <VolumeX size={16} />
              </button>
            )}
            <button type="button" ref={cerrarBoton} className="lp3-bienvenida__cerrar" onClick={cerrar} aria-label="Cerrar el video">
              <X size={18} />
            </button>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
