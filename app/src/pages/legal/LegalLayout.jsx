import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Isotipo } from '../../components/Logo';
import '../LandingPage.css';
import './LegalPage.css';

/**
 * Cascarón compartido de las páginas públicas de texto (Privacidad, Términos,
 * Seguridad). Reusa las variables de LandingPage.css para no duplicar el tema.
 */
export default function LegalLayout({ title, updated, intro, children }) {
  const navigate = useNavigate();

  useEffect(() => {
    window.scrollTo(0, 0);
    const previo = document.title;
    document.title = `${title} — Afable`;
    return () => { document.title = previo; };
  }, [title]);

  const goHome = (e) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
    e.preventDefault();
    navigate('/');
  };

  return (
    <div className="lp-page lg-page">
      <nav className="lg-nav">
        <a href="/" className="lg-nav-logo" onClick={goHome}>
          <Isotipo bgColor="#FFFFFF" /><span>Afable</span>
        </a>
        <a href="/" className="lg-nav-back" onClick={goHome}>← Volver al inicio</a>
      </nav>

      <main className="lg-main">
        <header className="lg-head">
          <h1>{title}</h1>
          {updated && <p className="lg-updated">Última actualización: {updated}</p>}
          {intro && <p className="lg-intro">{intro}</p>}
        </header>

        <div className="lg-body">{children}</div>

        <footer className="lg-foot">
          <p>
            Consultas: <a href="mailto:hi@getafable.com">hi@getafable.com</a>
          </p>
          <div className="lg-foot-links">
            <a href="/privacidad" onClick={(e) => { if (e.button === 0 && !e.metaKey && !e.ctrlKey) { e.preventDefault(); navigate('/privacidad'); } }}>Privacidad</a>
            <a href="/terminos" onClick={(e) => { if (e.button === 0 && !e.metaKey && !e.ctrlKey) { e.preventDefault(); navigate('/terminos'); } }}>Términos</a>
            <a href="/seguridad" onClick={(e) => { if (e.button === 0 && !e.metaKey && !e.ctrlKey) { e.preventDefault(); navigate('/seguridad'); } }}>Seguridad</a>
          </div>
        </footer>
      </main>
    </div>
  );
}
