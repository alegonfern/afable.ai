import React, { useState, useRef, useEffect } from 'react';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001/api/v1';

const GREETING = {
  role: 'assistant',
  content: '¡Hola! Cuéntame qué tarea le quitarías a tu equipo o qué agente necesitas, y te oriento en un minuto.',
};

export default function LandingLeadChat({ navigate }) {
  const [expanded, setExpanded] = useState(false);
  const [messages, setMessages] = useState([GREETING]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [segment, setSegment] = useState(null);
  const [leadCaptured, setLeadCaptured] = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, loading, expanded]);

  const send = async () => {
    const text = input.trim();
    if (!text || loading) return;
    if (!expanded) setExpanded(true);
    const next = [...messages, { role: 'user', content: text }];
    setMessages(next);
    setInput('');
    setError(false);
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/leads/chat/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: next }),
      });
      if (!res.ok) throw new Error('bad status');
      const data = await res.json();
      setMessages((prev) => [...prev, { role: 'assistant', content: data.reply }]);
      if (data.segment) setSegment(data.segment);
      if (data.lead_captured) setLeadCaptured(true);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  };

  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  return (
    <div className={`lp-ask${expanded ? ' expanded' : ''}`} id="asistente">
      {expanded && (
        <div className="lp-ask-body" ref={scrollRef}>
          {messages.map((m, i) => (
            <div key={i} className={`lp-ask-msg lp-ask-msg--${m.role}`}>{m.content}</div>
          ))}
          {loading && (
            <div className="lp-ask-msg lp-ask-msg--assistant lp-ask-typing">
              <span /><span /><span />
            </div>
          )}
          {segment === 'saas' && !leadCaptured && (
            <div className="lp-ask-cta">
              <button className="lp-btn-pill" onClick={() => navigate('/register')}>Crear cuenta gratis</button>
              <a className="lp-btn-signin" href="#precios">Ver precios</a>
            </div>
          )}
          {leadCaptured && (
            <div className="lp-ask-done">✓ Listo — un especialista te contactará por correo.</div>
          )}
          {error && <div className="lp-ask-error">No pudimos responder ahora. Intenta de nuevo.</div>}
        </div>
      )}

      {!leadCaptured && (
        <div className="lp-ask-bar">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder={expanded ? 'Escribe tu respuesta…' : '¿Qué agente necesitas o qué quieres automatizar?'}
            disabled={loading}
            aria-label="Pregúntale al asistente de Afable"
          />
          <button onClick={send} disabled={loading || !input.trim()} aria-label="Enviar">
            <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </div>
      )}
    </div>
  );
}
