import React from 'react';
import { logoDeServicio } from '../assets/logos';
import { AfableMark } from './Logo';

/**
 * "Imagen de proceso" de una plantilla: los iconos de las apps involucradas
 * conectados en flujo (Shopify → Afable → WhatsApp).
 *
 * Self-contained (estilos inline, sin MUI) para reusarse igual en la app
 * (ExplorePage) y en el landing (CSS propio).
 *
 * Cuando tenemos el logo real del servicio se usa ese; el emoji de `icon`
 * queda solo como respaldo para los servicios que aún no tienen logo.
 *
 * props:
 *  - flow:   [{ app, icon, color }]
 *  - accent: color de acento del proceso (fondo)
 *  - dark:   tema oscuro (ajusta contraste)
 */
export default function ProcessFlow({ flow = [], accent = '#586AD0', dark = false }) {
  if (!flow.length) return null;

  const labelColor = dark ? 'rgba(255,255,255,0.62)' : 'rgba(15,15,20,0.55)';
  const connector = dark ? 'rgba(255,255,255,0.22)' : 'rgba(15,15,20,0.18)';

  return (
    <div
      style={{
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 4,
        padding: '20px 14px',
        borderRadius: 12,
        overflow: 'hidden',
        background: dark
          ? `linear-gradient(135deg, ${accent}24 0%, rgba(255,255,255,0.02) 70%)`
          : `linear-gradient(135deg, ${accent}1f 0%, rgba(255,255,255,0.5) 70%)`,
        border: `1px solid ${accent}33`,
      }}
    >
      {/* malla de puntos sutil */}
      <div
        aria-hidden
        style={{
          position: 'absolute', inset: 0,
          backgroundImage: `radial-gradient(${connector} 0.7px, transparent 0.7px)`,
          backgroundSize: '14px 14px',
          opacity: 0.5, pointerEvents: 'none',
        }}
      />
      {flow.map((step, i) => {
        const logo = logoDeServicio(step.app);
        const esAfable = String(step.app).trim().toLowerCase() === 'afable';
        return (
        <React.Fragment key={`${step.app}-${i}`}>
          <div style={{ position: 'relative', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, minWidth: 56 }}>
            <div
              style={{
                width: 42, height: 42, borderRadius: 11,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 21, lineHeight: 1,
                // Con logo real el fondo va siempre blanco: las marcas están
                // hechas para leerse sobre blanco, no sobre el tinte del paso.
                background: logo ? '#fff' : (dark ? `${step.color}2e` : '#fff'),
                border: `1.5px solid ${step.color}`,
                boxShadow: `0 4px 12px ${step.color}33`,
                padding: logo ? 7 : 0,
                boxSizing: 'border-box',
              }}
            >
              {logo ? (
                <img
                  src={logo}
                  alt={step.app}
                  style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain', display: 'block' }}
                />
              ) : esAfable ? (
                <AfableMark size={20} color={step.color} />
              ) : (
                <span role="img" aria-label={step.app}>{step.icon}</span>
              )}
            </div>
            <span style={{ fontSize: 10.5, fontWeight: 600, color: labelColor, whiteSpace: 'nowrap' }}>
              {step.app}
            </span>
          </div>
          {i < flow.length - 1 && (
            <svg width="26" height="12" viewBox="0 0 26 12" fill="none" style={{ position: 'relative', flexShrink: 0, marginBottom: 16 }}>
              <line x1="1" y1="6" x2="18" y2="6" stroke={connector} strokeWidth="1.5" strokeDasharray="3 3" />
              <path d="M17 1.5 L24 6 L17 10.5" stroke={accent} strokeWidth="1.6" fill="none" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          )}
        </React.Fragment>
        );
      })}
    </div>
  );
}
