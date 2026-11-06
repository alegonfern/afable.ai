import { useRef, useState } from 'react';
import { Box, CircularProgress, Typography } from '@mui/material';
import { Check, ExternalLink, Upload } from 'lucide-react';
import { TONOS } from '../theme/tonos';

/*
 * La guía paso a paso para bajar los libros del SII y cargarlos (25-10-2026): el Registro de
 * Compras, el de Ventas y las boletas de honorarios recibidas. Cada paso se marca al hacerlo, y
 * el último es subir el archivo ahí mismo. Se usa en Contabilidad (junto a la zona de carga) y
 * en el chat, como tarjeta, cuando alguien pregunta cómo cargar sus libros.
 *
 * ⚠️ Los nombres de los menús son los del sitio del SII a octubre de 2026: si el SII los cambia,
 * se corrigen aquí.
 */

const LIBROS = {
  compras: {
    nombre: 'Registro de Compras',
    pasos: [
      'Entre a sii.cl y presione «Ingresar a Mi SII» con el RUT de la empresa y su clave tributaria.',
      'En el menú vaya a Servicios online › Factura electrónica › Registro de Compras y Ventas.',
      'Presione «Ingresar al Registro de Compras y Ventas», elija la empresa y el período (mes y año) y presione «Consultar».',
      'Abra la pestaña «COMPRA» y presione «Descargar Detalles»: baja un archivo .csv.',
    ],
  },
  ventas: {
    nombre: 'Registro de Ventas',
    pasos: [
      'Entre a sii.cl y presione «Ingresar a Mi SII» con el RUT de la empresa y su clave tributaria.',
      'En el menú vaya a Servicios online › Factura electrónica › Registro de Compras y Ventas.',
      'Presione «Ingresar al Registro de Compras y Ventas», elija la empresa y el período (mes y año) y presione «Consultar».',
      'Abra la pestaña «VENTA» y presione «Descargar Detalles»: baja un archivo .csv.',
    ],
  },
  honorarios: {
    nombre: 'Boletas de honorarios',
    pasos: [
      'Entre a sii.cl y presione «Ingresar a Mi SII» con el RUT de la empresa y su clave tributaria.',
      'En el menú vaya a Servicios online › Boletas de honorarios electrónicas.',
      'Entre a la consulta de boletas de honorarios RECIBIDAS y elija el año y el mes.',
      'Descargue el informe como planilla (el botón para exportar o guardar el listado).',
    ],
  },
};

export default function GuiaLibrosSII({ libroInicial = 'compras', onArchivo, cargando = false }) {
  const [libro, setLibro] = useState(LIBROS[libroInicial] ? libroInicial : 'compras');
  const [hechos, setHechos] = useState({});
  const input = useRef(null);
  const guia = LIBROS[libro];
  const marcar = (i) => setHechos((h) => ({ ...h, [`${libro}-${i}`]: !h[`${libro}-${i}`] }));

  return (
    <Box>
      <Box sx={{ display: 'inline-flex', p: 0.4, gap: 0.4, borderRadius: '10px', bgcolor: 'action.hover', mb: 1.75, flexWrap: 'wrap' }}>
        {Object.entries(LIBROS).map(([clave, l]) => (
          <Box key={clave} component="button" onClick={() => setLibro(clave)} sx={{
            px: 1.4, py: 0.6, border: 0, borderRadius: '8px', cursor: 'pointer', fontFamily: 'inherit', fontSize: '0.8rem',
            fontWeight: libro === clave ? 600 : 400, color: libro === clave ? 'text.primary' : 'text.secondary',
            bgcolor: libro === clave ? 'background.paper' : 'transparent',
            boxShadow: libro === clave ? '0 1px 2px rgba(0,0,0,0.08)' : 'none',
          }}>
            {l.nombre}
          </Box>
        ))}
      </Box>

      <Box component="ol" sx={{ listStyle: 'none', m: 0, p: 0, display: 'flex', flexDirection: 'column', gap: 1 }}>
        {guia.pasos.map((texto, i) => {
          const hecho = Boolean(hechos[`${libro}-${i}`]);
          return (
            <Box component="li" key={i} onClick={() => marcar(i)} sx={{
              display: 'flex', gap: 1.25, alignItems: 'flex-start', cursor: 'pointer', p: 1, mx: -1, borderRadius: '8px',
              '&:hover': { bgcolor: 'action.hover' },
            }}>
              <Box sx={{ width: 22, height: 22, borderRadius: '50%', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: '0.74rem', fontWeight: 600, transition: 'all .2s',
                bgcolor: hecho ? TONOS.menta.color : TONOS.malva.suave, color: hecho ? '#fff' : TONOS.malva.color }}>
                {hecho ? <Check size={13} strokeWidth={3} /> : i + 1}
              </Box>
              <Typography sx={{ fontSize: '0.86rem', lineHeight: 1.55, color: hecho ? 'text.secondary' : 'text.primary',
                textDecoration: hecho ? 'line-through' : 'none', textDecorationColor: 'rgba(0,0,0,0.25)' }}>
                {texto}
              </Typography>
            </Box>
          );
        })}
        <Box component="li" sx={{ display: 'flex', gap: 1.25, alignItems: 'flex-start', p: 1, mx: -1 }}>
          <Box sx={{ width: 22, height: 22, borderRadius: '50%', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '0.74rem', fontWeight: 600, bgcolor: 'var(--af-acento)', color: 'var(--af-sobre-acento)' }}>
            {guia.pasos.length + 1}
          </Box>
          <Box sx={{ flex: 1 }}>
            <Typography sx={{ fontSize: '0.86rem', lineHeight: 1.55, mb: 1 }}>
              Súbalo aquí tal como bajó, sin abrirlo ni guardarlo con Excel. Afable reconoce qué libro es y no repite lo que ya cargó.
            </Typography>
            <input ref={input} type="file" hidden accept=".csv,.txt,.xls,.xlsx"
              onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ''; if (f) onArchivo?.(f, libro); }} />
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
              <Box component="button" disabled={cargando || !onArchivo} onClick={() => input.current?.click()} sx={{
                display: 'inline-flex', alignItems: 'center', gap: 0.75, px: 1.75, py: 0.8, borderRadius: '10px', cursor: 'pointer',
                fontFamily: 'inherit', fontSize: '0.82rem', fontWeight: 500, border: '1px solid var(--af-acento)',
                bgcolor: 'var(--af-acento)', color: 'var(--af-sobre-acento)', '&:disabled': { opacity: 0.5, cursor: 'default' },
              }}>
                {cargando ? <CircularProgress size={13} sx={{ color: 'inherit' }} /> : <Upload size={14} />} Subir el archivo
              </Box>
              <Box component="a" href="https://www.sii.cl" target="_blank" rel="noopener noreferrer" sx={{
                display: 'inline-flex', alignItems: 'center', gap: 0.6, px: 1.5, py: 0.8, borderRadius: '10px', fontSize: '0.82rem',
                border: '1px solid', borderColor: 'divider', color: 'text.primary', textDecoration: 'none',
                '&:hover': { bgcolor: 'action.hover' },
              }}>
                Abrir sii.cl <ExternalLink size={13} />
              </Box>
            </Box>
          </Box>
        </Box>
      </Box>
    </Box>
  );
}
