import { useState } from 'react';
import {
  Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, IconButton, InputBase, MenuItem,
  Select, Typography,
} from '@mui/material';
import { Plus, X } from 'lucide-react';

/*
 * Repartir un documento entre varios proyectos (18-10-2026). Cada línea es un proyecto y su
 * porcentaje; lo que falte para 100% queda sin asignar, como en el margen por proyecto.
 */

const clp = (n) => `$${Math.round(Number(n) || 0).toLocaleString('es-CL')}`;

export default function Reparto({ doc, proyectos, onCerrar, onGuardar }) {
  const inicial = doc.asignaciones.length
    ? doc.asignaciones.map((a) => ({ proyecto: a.proyecto, porcentaje: String(Number(a.porcentaje)) }))
    : [{ proyecto: '', porcentaje: '50' }, { proyecto: '', porcentaje: '50' }];
  const [filas, setFilas] = useState(inicial);
  const [guardando, setGuardando] = useState(false);

  const validas = filas.filter((f) => f.proyecto && Number(f.porcentaje) > 0);
  const suma = validas.reduce((s, f) => s + Number(String(f.porcentaje).replace(',', '.')), 0);
  const repetido = new Set(validas.map((f) => f.proyecto)).size < validas.length;
  const base = doc.libro === 'honorarios' ? doc.monto_total : Number(doc.monto_neto) + Number(doc.monto_exento);
  const error = suma > 100 ? `Suma ${suma}%: no puede pasar de 100%.` : repetido ? 'Hay un proyecto repetido.' : null;

  const cambiar = (i, campo, valor) => setFilas((fs) => fs.map((f, j) => {
    if (j === i) return { ...f, [campo]: valor };
    // Con dos proyectos, el otro se completa solo hasta 100%.
    if (campo === 'porcentaje' && fs.length === 2) {
      const n = Number(String(valor).replace(',', '.'));
      if (!Number.isNaN(n) && n <= 100) return { ...f, porcentaje: String(Math.round((100 - n) * 100) / 100) };
    }
    return f;
  }));
  const guardar = async () => {
    setGuardando(true);
    const ok = await onGuardar(validas.map((f) => ({ proyecto: f.proyecto, porcentaje: String(f.porcentaje).replace(',', '.') })));
    setGuardando(false);
    if (ok) onCerrar();
  };

  return (
    <Dialog open onClose={onCerrar} maxWidth="xs" fullWidth>
      <DialogTitle sx={{ fontFamily: "'Sora', sans-serif", fontWeight: 600, pb: 0.5 }}>Repartir entre proyectos</DialogTitle>
      <DialogContent>
        <Typography sx={{ fontSize: '0.84rem', color: 'text.secondary', mb: 2 }}>
          {doc.razon_social} · folio {doc.folio} · {clp(base)} sin IVA
        </Typography>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
          {filas.map((f, i) => (
            <Box key={i} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Select size="small" displayEmpty value={f.proyecto} onChange={(e) => cambiar(i, 'proyecto', e.target.value)}
                sx={{ flex: 1, fontSize: '0.86rem' }}
                renderValue={(v) => (v ? proyectos.find((p) => p.id === v)?.nombre : <span style={{ opacity: 0.5 }}>Proyecto</span>)}>
                {proyectos.map((p) => <MenuItem key={p.id} value={p.id}>{p.nombre}</MenuItem>)}
              </Select>
              <Box sx={{ display: 'flex', alignItems: 'center', border: '1px solid', borderColor: 'divider', borderRadius: '8px', px: 1, width: 80 }}>
                <InputBase value={f.porcentaje} onChange={(e) => cambiar(i, 'porcentaje', e.target.value.replace(/[^\d.,]/g, ''))}
                  inputProps={{ style: { textAlign: 'right', fontSize: '0.86rem', padding: '7px 0' } }} />
                <Typography sx={{ fontSize: '0.86rem', color: 'text.secondary', ml: 0.25 }}>%</Typography>
              </Box>
              <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary', width: 90, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                {f.proyecto ? clp((base * Number(String(f.porcentaje).replace(',', '.') || 0)) / 100) : ''}
              </Typography>
              <IconButton size="small" onClick={() => setFilas((fs) => fs.filter((_, j) => j !== i))} aria-label="Quitar"><X size={14} /></IconButton>
            </Box>
          ))}
        </Box>
        <Button size="small" startIcon={<Plus size={14} />} sx={{ mt: 1 }} disabled={filas.length >= proyectos.length}
          onClick={() => setFilas((fs) => [...fs, { proyecto: '', porcentaje: String(Math.max(0, 100 - suma)) }])}>
          Agregar proyecto
        </Button>
        <Typography sx={{ fontSize: '0.82rem', mt: 1.5, color: error ? 'error.main' : 'text.secondary' }}>
          {error || (suma < 100 && validas.length ? `Repartido ${suma}%: el ${Math.round((100 - suma) * 10) / 10}% queda sin proyecto.` : `Repartido ${suma}%.`)}
        </Typography>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onCerrar}>Cancelar</Button>
        <Button variant="contained" onClick={guardar} disabled={!!error || guardando}>Guardar</Button>
      </DialogActions>
    </Dialog>
  );
}
