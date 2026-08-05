import { Box, Tab, Tabs, useTheme } from '@mui/material';
import { useNavigate } from 'react-router-dom';

/**
 * La barra de pestañas del grupo "Conocimiento": de dónde sale lo que el agente sabe.
 *
 * Existe porque las cuatro cosas del grupo NO viven en la misma pantalla: tres son
 * pestañas del hub (`/app/contexto?tab=…`) y Archivos es una pantalla aparte, con su
 * árbol de carpetas y su propio `?carpeta=`. Sin una barra común, estar en Archivos
 * dejaba sin forma de saltar a Conexiones, y en el hub no había pestaña de Archivos —
 * cuatro items del menú que se comportaban como dos cosas distintas.
 *
 * `activa` es el valor de la pestaña en la que se está.
 */
const PESTANAS = [
  { value: 'espacios',      label: 'Espacios',               destino: '/app/contexto?tab=espacios' },
  { value: 'integraciones', label: 'Conexiones',             destino: '/app/contexto?tab=integraciones' },
  { value: 'archivos',      label: 'Archivos',               destino: '/app/archivos' },
  { value: 'mi-contexto',   label: 'Contexto de la empresa', destino: '/app/contexto?tab=mi-contexto' },
  { value: 'cubiculos',     label: 'Cubículos',              destino: '/app/contexto?tab=cubiculos' },
];

export default function NavConocimiento({ activa }) {
  const theme = useTheme();
  const navigate = useNavigate();

  // Cubículos ya no es una pestaña propia (vive dentro de Contexto de la empresa), pero
  // si alguien llega a su URL vieja la barra tiene que poder representarlo.
  const visibles = PESTANAS.filter((p) => p.value !== 'cubiculos' || activa === 'cubiculos');

  return (
    <Box sx={{ borderBottom: `1px solid ${theme.palette.divider}`, px: { xs: 2, sm: 3 } }}>
      <Tabs
        value={visibles.some((p) => p.value === activa) ? activa : 'espacios'}
        onChange={(_, valor) => {
          const p = PESTANAS.find((x) => x.value === valor);
          if (p) navigate(p.destino);
        }}
        variant="scrollable" scrollButtons="auto"
        sx={{
          minHeight: 40,
          '& .MuiTab-root': { minHeight: 40, textTransform: 'none', fontSize: '0.82rem' },
        }}
      >
        {visibles.map((p) => <Tab key={p.value} value={p.value} label={p.label} />)}
      </Tabs>
    </Box>
  );
}
