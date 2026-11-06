import { useLayoutEffect, useRef, useState } from 'react';
import { useInView, useReducedMotion } from 'framer-motion';
import { useEscritorio } from './HeroAnimado';
import { ALTO, ANCHO, VistaAgente } from './VistaAgente';
import oficina from '../../../assets/landing2/fondo-oficina-algodon.jpg';
import raboteurs from '../../../assets/landing2/fondo-raboteurs.jpg';
import bolsa from '../../../assets/landing2/fondo-bolsa.jpg';
import hammershoi from '../../../assets/landing2/fondo-hammershoi.jpg';
import laminador from '../../../assets/landing2/fondo-laminador.jpg';
import operadoras from '../../../assets/landing2/auto-operadoras.jpg';
import tarjetas from '../../../assets/landing2/auto-tarjetas.jpg';
import perforadora from '../../../assets/landing2/auto-perforadora.jpg';
import babbage from '../../../assets/landing2/auto-babbage.jpg';
import central from '../../../assets/landing2/auto-central.jpg';
import carro from '../../../assets/landing2/davinci-carro.jpg';
import volante from '../../../assets/landing2/davinci-volante.jpg';
import engranaje from '../../../assets/landing2/davinci-engranaje.jpg';
import madrid from '../../../assets/landing2/davinci-madrid.jpg';
import tanques from '../../../assets/landing2/davinci-tanques.jpg';
import espejo from '../../../assets/landing2/ing-espejo.jpg';
import motor from '../../../assets/landing2/ing-motor.jpg';
import control from '../../../assets/landing2/ing-control.jpg';
import rover from '../../../assets/landing2/ing-rover.jpg';
import plataforma from '../../../assets/landing2/ing-plataforma.jpg';
import './HeroMarco.css';

/*
 * Hero de la landing 2 (30-10-2026): titular, descripción y botones centrados, y debajo un marco
 * con una pintura de fondo y la pantalla real de Afable por delante: la vista Agente de Finanzas
 * (VistaAgente.jsx), que se anima una vez al aparecer. `MarcoPintado` repite el mismo marco en
 * otras secciones (Así trabaja, Con su ERP o sin él).
 * Bajo 1024 px va la misma vista sin la barra lateral, en una columna.
 */

// Las imágenes de fondo, recortadas por el marco como un cuadro. Hay tres series (30-10-2026) y cada
// imagen dice algo de lo que hace Afable:
//
// Ingeniería a color (01-11-2026, la serie vigente): fotos de la NASA, dominio público, en alta resolución.
// Vibra ingenieril y de emprender: gente construyendo cosas que no existían.
//   espejo      el panal dorado del espejo del telescopio Webb: precisión (tarjeta Afable)
//   motor       un motor del transbordador encendido en prueba: la máquina funcionando (Así trabaja)
//   control     la sala de control del Apolo 9: preguntarle a su operación (chat)
//   rover       el Curiosity en Marte, trabajando solo; el color llena todo el marco (hero)
//   plataforma  el Discovery en su torre: los sistemas grandes que ya existen (tarjeta Afable Proyectos)
//
// Leonardo da Vinci, SOLO sus planos de ingeniería (30-10-2026: las pinturas se sacaron porque desviaban
// el foco; Afable son máquinas que trabajan solas). Dominio público, en su color original.
//   volante    una máquina de volante completa (hero)
//   engranaje  una gran rueda dentada: la máquina funcionando (Así trabaja)
//   madrid     Códice de Madrid I, engranajes y cadenas, oscurecido detrás del chat (chat)
//   carro      el carro autopropulsado, el primer robot programable: trabaja solo (tarjeta Afable)
//   tanques    máquinas de guerra (British Museum): los sistemas grandes y pesados que ya existen
//              (tarjeta Afable Proyectos)
//
// Pinturas (dominio público, Wikimedia Commons):
//   oficina    el trabajo administrativo que Afable opera (hero)
//   raboteurs  el trabajo manual y repetitivo que automatiza (Así trabaja)
//   bolsa      gente consultando cifras: preguntarle a su empresa (chat)
//   hammershoi orden y calma: la empresa que corre sola (tarjeta Afable)
//   laminador  la gran industria, donde están SAP y Oracle (tarjeta Afable Proyectos)
//
// Historia de la automatización (fotos y grabados de época, en blanco y negro): Afable como el paso
// siguiente de 200 años de automatizar el trabajo de oficina.
//   tarjetas    las tarjetas perforadas del telar de Jacquard (1804): los primeros datos de la
//               automatización; llenan el marco como textura (hero)
//   central     la central de la policía de Nueva York: la operación del día a día (Así trabaja;
//               es oscura, así que los capítulos en blanco se leen encima)
//   perforadora digitar dato por dato las tarjetas del censo (chat)
//   babbage     la máquina diferencial de Babbage: una máquina que calcula sola (tarjeta Afable)
//   operadoras  una sala de operadoras telefónicas: una operación grande ya montada
//               (tarjeta Afable Proyectos)
export const FONDOS = {
  espejo: { src: espejo, credito: 'Segmentos del espejo del telescopio James Webb. NASA/MSFC/David Higginbotham', posicion: '50% 50%' },
  motor: { src: motor, credito: 'Prueba de encendido de un motor principal del transbordador espacial. NASA', posicion: '50% 55%' },
  control: { src: control, credito: 'Sala de control de misión durante el Apolo 9 (1969). NASA', posicion: '50% 40%' },
  rover: { src: rover, credito: 'Autorretrato del rover Curiosity en Marte (2021). NASA/JPL-Caltech/MSSS', posicion: '50% 45%' },
  plataforma: { src: plataforma, credito: 'El transbordador Discovery en la plataforma 39A (2010). NASA', posicion: '50% 35%' },
  engranaje: { src: engranaje, credito: 'Leonardo da Vinci, estudio de una rueda dentada', posicion: '50% 45%' },
  madrid: { src: madrid, credito: 'Leonardo da Vinci, Códice de Madrid I. Biblioteca Nacional de España', posicion: '50% 35%' },
  tanques: { src: tanques, credito: 'Leonardo da Vinci, estudios de máquinas de guerra (c. 1485). British Museum', posicion: '50% 60%' },
  carro: { src: carro, credito: 'Leonardo da Vinci, carro autopropulsado, Códice Atlántico', posicion: '50% 60%' },
  volante: { src: volante, credito: 'Leonardo da Vinci, máquina de volante', posicion: '50% 45%' },
  oficina: { src: oficina, credito: 'Edgar Degas, Un bureau de coton à La Nouvelle-Orléans (1873)', posicion: '50% 35%' },
  raboteurs: { src: raboteurs, credito: 'Gustave Caillebotte, Les raboteurs de parquet (1875)', posicion: '50% 60%' },
  bolsa: { src: bolsa, credito: 'Edgar Degas, Portraits à la Bourse (1879)', posicion: '50% 30%' },
  hammershoi: { src: hammershoi, credito: 'Vilhelm Hammershøi, Støvkornenes dans i solstrålerne (1900)', posicion: '50% 45%' },
  laminador: { src: laminador, credito: 'Adolph Menzel, Das Eisenwalzwerk (1875)', posicion: '50% 50%' },
  operadoras: { src: operadoras, credito: 'Central telefónica, de The History of the Telephone (1910)', posicion: '50% 60%' },
  tarjetas: { src: tarjetas, credito: 'Tarjetas perforadas de un telar de Jacquard, National Museum of Scotland. Foto: Stephencdickson, CC BY-SA 4.0 (en blanco y negro)', posicion: '50% 50%' },
  perforadora: { src: perforadora, credito: 'Perforadora de tarjetas del censo (c. 1940). National Archives, EE. UU.', posicion: '50% 40%' },
  babbage: { src: babbage, credito: 'Máquina diferencial de Babbage, Harper’s New Monthly Magazine (1864)', posicion: '50% 30%' },
  central: { src: central, credito: 'Central telefónica de la policía de Nueva York (1909). Bain Collection, Library of Congress', posicion: '50% 40%' },
};

// Qué imagen va en cada lugar según el tema. Por defecto, ingeniería a color (01-11-2026);
// `?tema=davinci`, `?tema=automatizacion` y `?tema=pinturas` dejan comparar con las series anteriores.
const TEMAS = {
  ingenieria: { hero: 'rover', escena: 'motor', chat: 'control', afable: 'espejo', proyectos: 'plataforma' },
  davinci: { hero: 'volante', escena: 'engranaje', chat: 'madrid', afable: 'carro', proyectos: 'tanques' },
  pinturas: { hero: 'oficina', escena: 'raboteurs', chat: 'bolsa', afable: 'hammershoi', proyectos: 'laminador' },
  automatizacion: { hero: 'tarjetas', escena: 'central', chat: 'perforadora', afable: 'babbage', proyectos: 'operadoras' },
};

export function useFondos() {
  const tema = typeof window !== 'undefined' ? new URLSearchParams(window.location.search).get('tema') : null;
  return TEMAS[tema] || TEMAS.ingenieria;
}

// El movimiento de cámara de cada plano (30-10-2026): un acercamiento lento y un desplazamiento hacia donde
// está el mecanismo, distinto en cada uno para que no se muevan todos igual. Lo anima HeroMarco.css
// (hm-camara); con "reducir movimiento" la imagen queda quieta.
const CAMARA = {
  espejo: { x: '-2%', y: '-2%', s: 1.1, t: '28s' },
  motor: { x: '0%', y: '3%', s: 1.1, t: '26s' },
  control: { x: '2%', y: '-2%', s: 1.08, t: '34s' },
  rover: { x: '-2%', y: '1%', s: 1.1, t: '30s' },
  plataforma: { x: '1%', y: '-3%', s: 1.08, t: '28s' },
  volante: { x: '-2%', y: '-3%', s: 1.14, t: '26s' },
  engranaje: { x: '3%', y: '-2%', s: 1.16, t: '30s' },
  madrid: { x: '0%', y: '-4%', s: 1.12, t: '34s' },
  carro: { x: '-3%', y: '2%', s: 1.15, t: '24s' },
  tanques: { x: '3%', y: '1%', s: 1.12, t: '28s' },
};

export function FondoPintado({ fondo }) {
  const f = FONDOS[fondo] || FONDOS.oficina;
  const c = CAMARA[fondo];
  const estilo = { objectPosition: f.posicion };
  if (c) Object.assign(estilo, { '--cam-x': c.x, '--cam-y': c.y, '--cam-s': c.s, '--cam-t': c.t });
  return <img className={`hm-fondo${c ? ' hm-fondo--camara' : ''}`} src={f.src} alt="" aria-hidden="true" loading="lazy" style={estilo} />;
}

// El marco con pintura para cualquier contenido: la pintura de fondo y lo que va delante, centrado.
export function MarcoPintado({ fondo, className = '', children }) {
  return (
    <div className={`hm-marco hm-marco--libre ${className}`}>
      <FondoPintado fondo={fondo} />
      {children}
    </div>
  );
}

// El ancho disponible del marco: de ahí sale la escala de la pantalla (84 % del marco).
function useAnchoMarco(ref) {
  const [ancho, setAncho] = useState(1200);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    const medir = () => setAncho(el.clientWidth);
    medir();
    const obs = new ResizeObserver(medir);
    obs.observe(el);
    return () => obs.disconnect();
  }, [ref]);
  return ancho;
}

function PantallaEscritorio({ reducido, fondo }) {
  const marco = useRef(null);
  const ancho = useAnchoMarco(marco);
  const visible = useInView(marco, { once: true, amount: 0.25 });
  const escala = Math.min(1, (ancho * 0.8) / ANCHO);
  const margenY = Math.max(48, ancho * 0.06);
  return (
    <div ref={marco} className="hm-marco" style={{ height: ALTO * escala + margenY * 2 }}>
      <FondoPintado fondo={fondo} />
      <div className="hm-pantalla" style={{ top: margenY, width: ANCHO * escala, height: ALTO * escala }}>
        <div style={{ transform: `scale(${escala})`, transformOrigin: '0 0' }} aria-hidden="true">
          <VistaAgente activa={visible} reducido={reducido} />
        </div>
      </div>
    </div>
  );
}

export default function HeroMarco({ titulo, lado, fondo = 'oficina' }) {
  const escritorio = useEscritorio();
  const reducido = useReducedMotion();
  const marcoMovil = useRef(null);
  const visibleMovil = useInView(marcoMovil, { once: true, amount: 0.2 });
  return (
    <section className="hm">
      <div className="hm__cabeza">
        <div className="hm__titulo">{titulo}</div>
        <div className="hm__lado">{lado}</div>
      </div>
      {escritorio ? (
        <PantallaEscritorio reducido={reducido} fondo={fondo} />
      ) : (
        <div ref={marcoMovil} className="hm-marco hm-marco--movil">
          <FondoPintado fondo={fondo} />
          <div className="hm-pantalla hm-pantalla--movil"><VistaAgente compacta activa={visibleMovil} reducido={reducido} /></div>
        </div>
      )}
    </section>
  );
}
