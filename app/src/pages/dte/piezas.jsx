import { useRef } from 'react';
import { Button } from '@mui/material';
import { Upload } from 'lucide-react';

/* Piezas compartidas de las pantallas del facturador electrónico. */

/* Elegir un archivo con un botón (el input queda oculto). */
export function ElegirArchivo({ acepta, onElegir, children, disabled }) {
  const ref = useRef();
  return (
    <>
      <input ref={ref} type="file" accept={acepta} hidden onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ''; if (f) onElegir(f); }} />
      <Button size="small" variant="outlined" startIcon={<Upload size={14} />} disabled={disabled} onClick={() => ref.current?.click()}>
        {children}
      </Button>
    </>
  );
}
