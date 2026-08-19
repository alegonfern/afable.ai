import { useEffect, useState } from 'react';
import { Box, CircularProgress, Tab, Tabs, Typography, useTheme } from '@mui/material';
import { api } from '../../services/api';

/**
 * Cada archivo se ve como lo que es.
 *
 * Antes todo se dibujaba igual: el texto extraído, en monoespaciado. Una planilla de 300
 * filas era un chorro de palabras y un contrato perdía sus títulos — servía para que el
 * agente leyera, no para que una persona mirara, y es de las cosas que más hacían sentir
 * que el archivo estaba de adorno.
 *
 * Una planilla se dibuja como tabla, un documento de Word conserva su jerarquía, y un PDF
 * se muestra tal cual: el original siempre se va a ver mejor que cualquier reconstrucción
 * que hagamos nosotros.
 */
export default function VistaDelArchivo({ documentoId, workspaceSlug }) {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  const [vista, setVista] = useState(null);
  const [hoja, setHoja] = useState(0);
  const [pdfUrl, setPdfUrl] = useState(null);

  const borde = theme.palette.divider;
  const textMuted = d ? 'rgba(255,255,255,0.66)' : 'rgba(0,0,0,0.62)';
  const bgSuave = d ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.02)';

  // El PDF se baja aparte, con sesión, y se libera al salir: si no, el blob se queda
  // ocupando memoria hasta recargar la página.
  useEffect(() => {
    if (vista?.tipo !== 'pdf') return undefined;
    let vivo = true;
    let url = null;
    api.descargarArchivo(documentoId, workspaceSlug)
      .then(({ data }) => {
        if (!vivo) return;
        url = URL.createObjectURL(new Blob([data], { type: 'application/pdf' }));
        setPdfUrl(url);
      })
      .catch(() => {});
    return () => { vivo = false; if (url) URL.revokeObjectURL(url); };
  }, [vista?.tipo, documentoId, workspaceSlug]);

  useEffect(() => {
    let vivo = true;
    api.getVistaDelArchivo(documentoId, workspaceSlug)
      .then(({ data }) => { if (vivo) setVista(data); })
      .catch(() => { if (vivo) setVista({ tipo: 'texto', texto: '' }); });
    return () => { vivo = false; };
  }, [documentoId, workspaceSlug]);

  if (!vista) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
        <CircularProgress size={22} sx={{ color: '#586AD0' }} />
      </Box>
    );
  }

  // ── Planilla ──────────────────────────────────────────────────────────────
  if (vista.tipo === 'planilla' && vista.hojas?.length) {
    const actual = vista.hojas[Math.min(hoja, vista.hojas.length - 1)];
    return (
      <Box>
        {vista.hojas.length > 1 && (
          <Tabs
            value={Math.min(hoja, vista.hojas.length - 1)}
            onChange={(_, v) => setHoja(v)}
            variant="scrollable" scrollButtons="auto"
            sx={{ minHeight: 36, mb: 1, '& .MuiTab-root': { minHeight: 36, textTransform: 'none', fontSize: '0.8rem' } }}
          >
            {vista.hojas.map((h) => <Tab key={h.nombre} label={h.nombre} />)}
          </Tabs>
        )}

        <Box sx={{ border: `1px solid ${borde}`, borderRadius: '10px', overflow: 'auto', maxHeight: 560 }}>
          <Box component="table" sx={{ borderCollapse: 'collapse', width: '100%', fontSize: '0.82rem' }}>
            <tbody>
              {actual.filas.map((fila, i) => (
                <Box
                  component="tr" key={i}
                  sx={{ bgcolor: i === 0 ? bgSuave : 'transparent' }}
                >
                  {fila.map((celda, j) => (
                    <Box
                      component="td" key={j}
                      sx={{
                        border: `1px solid ${borde}`, px: 1.25, py: 0.6,
                        fontWeight: i === 0 ? 700 : 400,
                        whiteSpace: 'nowrap',
                        // Los números a la derecha, como en cualquier planilla: leer una
                        // columna de montos alineada a la izquierda es una tortura.
                        textAlign: i > 0 && /^-?[\d.,$%\s]+$/.test(celda) && celda.trim() ? 'right' : 'left',
                      }}
                    >
                      {celda}
                    </Box>
                  ))}
                </Box>
              ))}
            </tbody>
          </Box>
        </Box>

        {/* Cuánto quedó fuera. Decirlo evita que alguien saque conclusiones de una
            planilla que creía completa. */}
        {actual.recortada && (
          <Typography sx={{ fontSize: '0.75rem', color: textMuted, mt: 0.75 }}>
            Se muestran las primeras {actual.filas.length} filas de {actual.total_filas}.
            El agente sí lee la planilla completa.
          </Typography>
        )}
      </Box>
    );
  }

  // ── Documento con formato ─────────────────────────────────────────────────
  if (vista.tipo === 'texto_rico') {
    return (
      <Box
        sx={{
          border: `1px solid ${borde}`, borderRadius: '10px', p: 3, maxHeight: 620,
          overflow: 'auto', fontSize: '0.9rem', lineHeight: 1.7,
          '& h2': { fontSize: '1.15rem', mt: 2.5, mb: 1 },
          '& h3': { fontSize: '1rem', mt: 2, mb: 0.75 },
          '& p': { my: 1 },
          '& table': { borderCollapse: 'collapse', width: '100%', my: 2 },
          '& td': { border: `1px solid ${borde}`, px: 1.25, py: 0.6, fontSize: '0.82rem' },
        }}
        dangerouslySetInnerHTML={{ __html: vista.html || '' }}
      />
    );
  }

  // ── PDF ───────────────────────────────────────────────────────────────────
  if (vista.tipo === 'pdf') {
    // El iframe apunta a un blob de memoria, no a /media/: el archivo se bajó con la
    // sesión puesta. Antes se le pasaba la dirección directa, que cualquiera abría sin
    // estar logueado.
    if (!pdfUrl) {
      return (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
          <CircularProgress size={22} />
        </Box>
      );
    }
    return (
      <Box
        component="iframe"
        src={pdfUrl}
        title="Documento"
        sx={{ width: '100%', height: 620, border: `1px solid ${borde}`, borderRadius: '10px' }}
      />
    );
  }

  // ── Texto ─────────────────────────────────────────────────────────────────
  return (
    <Box sx={{
      border: `1px solid ${borde}`, borderRadius: '10px', p: 2, maxHeight: 620,
      overflow: 'auto', bgcolor: bgSuave,
      fontFamily: `'JetBrains Mono', 'Fira Code', monospace`,
      fontSize: '0.82rem', lineHeight: 1.7, whiteSpace: 'pre-wrap',
    }}>
      {vista.texto || 'Sin texto extraído.'}
    </Box>
  );
}
