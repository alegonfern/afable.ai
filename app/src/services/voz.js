/*
 * Voz en el chat, versión básica (12-11-2026): dictar con el reconocimiento de voz del navegador
 * y escuchar la respuesta con su síntesis de voz. Todo ocurre en el navegador, sin pasar por el
 * servidor. Funciona en Chrome y Edge; en Safari a medias; en Firefox no hay dictado (el botón
 * no aparece).
 */
import { useCallback, useEffect, useRef, useState } from 'react';

const Reconocimiento = typeof window !== 'undefined'
  ? (window.SpeechRecognition || window.webkitSpeechRecognition)
  : null;

export const hayDictado = Boolean(Reconocimiento);

/**
 * Dictado. `alCambiar(texto)` recibe lo que se va entendiendo (para mostrarlo en el cuadro) y
 * `alTerminar(texto)` la frase completa cuando la persona deja de hablar.
 */
export function useDictado({ alCambiar, alTerminar }) {
  const [escuchando, setEscuchando] = useState(false);
  const rec = useRef(null);
  const llamadas = useRef({ alCambiar, alTerminar });
  llamadas.current = { alCambiar, alTerminar };

  const detener = useCallback(() => { rec.current?.stop(); }, []);

  const empezar = useCallback(() => {
    if (!Reconocimiento || rec.current) return;
    callar();
    const r = new Reconocimiento();
    r.lang = 'es-CL';
    r.interimResults = true;
    r.continuous = false;
    let final = '';
    r.onresult = (e) => {
      let parcial = '';
      for (let i = e.resultIndex; i < e.results.length; i += 1) {
        const t = e.results[i][0].transcript;
        if (e.results[i].isFinal) final += t; else parcial += t;
      }
      llamadas.current.alCambiar?.((final + parcial).trim());
    };
    r.onerror = () => {};
    r.onend = () => {
      rec.current = null;
      setEscuchando(false);
      if (final.trim()) llamadas.current.alTerminar?.(final.trim());
    };
    rec.current = r;
    setEscuchando(true);
    try { r.start(); } catch { rec.current = null; setEscuchando(false); }
  }, []);

  useEffect(() => {
    // Chrome carga las voces con retraso; pedirlas aquí las deja listas para la primera respuesta.
    try { window.speechSynthesis?.getVoices(); } catch { /* sin síntesis de voz */ }
    return () => { rec.current?.abort(); callar(); };
  }, []);

  return { escuchando, empezar, detener };
}

// Lo que se lee en voz alta: el texto sin markdown, tablas ni enlaces, y solo el comienzo.
// Las tablas, montos detallados y botones quedan en pantalla.
function paraLeer(texto, maximo = 320) {
  const limpio = (texto || '')
    .replace(/\[\[[\s\S]*?\]\]/g, ' ')
    .replace(/```[\s\S]*?```/g, ' ')
    .split('\n').filter((l) => !l.trim().startsWith('|')).join('\n')
    .replace(/!?\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/[#*_>`~]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
  if (limpio.length <= maximo) return limpio;
  const corte = limpio.slice(0, maximo);
  const fin = Math.max(corte.lastIndexOf('. '), corte.lastIndexOf('? '), corte.lastIndexOf(': '));
  return fin > 80 ? corte.slice(0, fin + 1) : `${corte.slice(0, corte.lastIndexOf(' '))}…`;
}

function vozEnEspanol() {
  const voces = window.speechSynthesis?.getVoices() || [];
  const es = voces.filter((v) => v.lang?.toLowerCase().startsWith('es'));
  return es.find((v) => /es-(cl|us|mx|419)/i.test(v.lang)) || es.find((v) => /natural|online|google/i.test(v.name)) || es[0] || null;
}

export function leerEnVoz(texto) {
  const s = window.speechSynthesis;
  const frase = paraLeer(texto);
  if (!s || !frase) return;
  s.cancel();
  const u = new SpeechSynthesisUtterance(frase);
  const voz = vozEnEspanol();
  if (voz) u.voice = voz;
  u.lang = voz?.lang || 'es-CL';
  u.rate = 1.05;
  s.speak(u);
}

export function callar() {
  try { window.speechSynthesis?.cancel(); } catch { /* sin síntesis de voz */ }
}
