import noche from '../assets/landing2/ing-noche.jpg';
import despegue from '../assets/landing2/ing-despegue.jpg';

/*
 * La imagen de fondo del ingreso y el registro: fotos de ingeniería de la NASA a color, como la landing
 * (01-11-2026; antes planos de Leonardo da Vinci). Dominio público. Cubre toda la pantalla y el
 * formulario va encima, al centro; abajo a la derecha, de dónde sale la imagen.
 *   ingreso  El Discovery de noche en su plataforma: una operación grande funcionando, a la que se vuelve.
 *   registro El Saturno V del Apolo 11 encendiendo motores: el punto de partida.
 */
const IMAGENES = {
  ingreso: { src: noche, credito: 'El transbordador Discovery en la plataforma 39A (2010). NASA', posicion: '60% 50%' },
  registro: { src: despegue, credito: 'El Saturno V del Apolo 11 al encender sus motores (1969). NASA', posicion: '50% 40%' },
};

// En el registro el formulario va a la derecha en pantallas anchas, para que se vea el abanico de trayectorias.
export const LADO = { ingreso: '', registro: ' auth-page--lado' };

export default function AuthFondo({ pintura }) {
  const p = IMAGENES[pintura];
  return (
    <>
      <img className="auth-fondo" src={p.src} alt="" aria-hidden="true" style={{ objectPosition: p.posicion }} />
      <span className="auth-fondo__credito">{p.credito}</span>
    </>
  );
}
