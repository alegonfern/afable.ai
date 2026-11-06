import { useParams } from 'react-router-dom';
import { Box, Typography } from '@mui/material';
import PageHeader from '../../components/PageHeader';
import { useWorkspace } from '../../context/WorkspaceContext';
import { seccionDe } from '../../layout/Dashboard/modulos';
import { usePanelLateral } from '../../layout/Dashboard/panelContexto';
import { useVersionDeConfiguracion } from '../modulos/Configuraciones';
import { Bodegas } from '../comercial/ConfigComercial';
import { Tarjeta, useConfigComercial } from '../comercial/comun';
import Conteos from './Conteos';
import Movimientos from './Movimientos';
import Reportes from './Reportes';
import Resumen from './Resumen';
import Stock from './Stock';

/*
 * Inventario (26-10-2026): un módulo propio, separado de Ventas y Compras. Ventas y Compras
 * muestran sus productos; aquí está el stock de verdad: lo físico, lo comprometido, lo
 * disponible y lo que viene; entradas y salidas con su motivo; el kardex de cada producto; la
 * toma de inventario; la valorización y la rotación. Su configuración (sin inventario, básico o
 * completo, y las bodegas) es la de este módulo.
 */

export default function InventarioPage() {
  const { seccion: param, id } = useParams();
  const { slug, esEditor } = useWorkspace();
  const version = useVersionDeConfiguracion();
  const cfg = useConfigComercial(slug, version);
  const panel = usePanelLateral();
  const seccion = seccionDe('inventario', param);
  const abrirConfig = () => panel?.abrir('config');

  const contenido = () => {
    switch (seccion.slug) {
      case 'stock': return <Stock key={version} slug={slug} esEditor={esEditor} abrirConfig={abrirConfig} />;
      case 'movimientos': return <Movimientos slug={slug} />;
      case 'conteos': return <Conteos slug={slug} esEditor={esEditor} id={id} />;
      case 'reportes': return <Reportes slug={slug} />;
      case 'bodegas':
        return (
          <Tarjeta sx={{ p: 2.5, maxWidth: 720, display: 'grid', gap: 1.5 }}>
            <Typography sx={{ fontWeight: 600 }}>Bodegas</Typography>
            <Typography sx={{ fontSize: '0.84rem', color: 'text.secondary', lineHeight: 1.5 }}>
              {cfg?.nivel_inventario === 'completo'
                ? 'Cada entrega y recepción dice de qué bodega sale o a cuál llega. La principal es la que se usa si no se elige otra.'
                : 'Con el inventario básico hay una sola bodega, oculta. Para llevar varias, elija el inventario completo en la configuración de Inventario.'}
            </Typography>
            {cfg?.nivel_inventario === 'completo' && <Bodegas slug={slug} esEditor={esEditor} />}
          </Tarjeta>
        );
      default: return <Resumen key={version} slug={slug} esEditor={esEditor} abrirConfig={abrirConfig} />;
    }
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', minWidth: 0, width: '100%' }}>
      <PageHeader title={seccion.label} crumbs={[{ label: 'Inventario', to: '/app/inventario' }]} back="/app" backLabel="Inicio" />
      <Box sx={{ flex: 1, minWidth: 0, overflow: 'auto', px: 3, py: 2.5, display: 'flex', flexDirection: 'column', gap: 2 }}>
        {!slug ? <Typography sx={{ m: 'auto', color: 'text.secondary' }}>Primero tiene que crear su empresa en Afable.</Typography> : contenido()}
      </Box>
    </Box>
  );
}
