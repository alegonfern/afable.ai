import { useParams } from 'react-router-dom';
import { Box, Typography } from '@mui/material';
import PageHeader from '../../components/PageHeader';
import { useWorkspace } from '../../context/WorkspaceContext';
import { seccionDe } from '../../layout/Dashboard/modulos';
import { useVersionDeConfiguracion } from '../modulos/Configuraciones';
import { ResumenVentasSII } from '../modulos/ResumenVentasSII';
import Recibidos from '../dte/Recibidos';
import Contactos from './Contactos';
import FichaPedido from './FichaPedido';
import ListaPedidos from './ListaPedidos';
import Productos from './Productos';
import Reportes from './Reportes';
import { Embudo, Entregas, PorFacturar } from './Seguimiento';
import { TIPO_DE_MODULO, useConfigComercial } from './comun';

/*
 * Ventas y Compras (22-10-2026): las dos usan la misma página, cada una desde su lado. Cada
 * sección del menú es una dirección propia (/app/ventas/ordenes) y cada documento también
 * (/app/ventas/ordenes/12), así se puede compartir el enlace o volver con el botón atrás.
 */

export default function ComercialPage({ modulo }) {
  const { seccion: param, id } = useParams();
  const { slug, esEditor } = useWorkspace();
  const version = useVersionDeConfiguracion();
  const cfg = useConfigComercial(slug, version);
  const seccion = seccionDe(modulo, param);
  const tipo = TIPO_DE_MODULO[modulo];
  const nombre = modulo === 'ventas' ? 'Ventas' : 'Compras';

  const contenido = () => {
    if (id) return <FichaPedido key={id} slug={slug} id={id} modulo={modulo} seccion={seccion.slug} esEditor={esEditor} />;
    switch (seccion.slug) {
      case 'cotizaciones':
      case 'ordenes':
        return <ListaPedidos key={seccion.slug} slug={slug} tipo={tipo} modulo={modulo} vista={seccion.slug} esEditor={esEditor} />;
      case 'entregas':
        return <Entregas slug={slug} tipo={tipo} modulo={modulo} />;
      case 'por-facturar':
        return <PorFacturar slug={slug} tipo={tipo} modulo={modulo} />;
      case 'clientes':
        return <Contactos key="cliente" slug={slug} rol="cliente" esEditor={esEditor} />;
      case 'proveedores':
        return <Contactos key="proveedor" slug={slug} rol="proveedor" esEditor={esEditor} />;
      case 'productos':
        return <Productos slug={slug} esEditor={esEditor} conInventario={cfg?.nivel_inventario && cfg.nivel_inventario !== 'ninguno'} />;
      case 'reportes':
        return <Reportes key={modulo} slug={slug} tipo={tipo} />;
      case 'recibidos':
        return <Recibidos slug={slug} esEditor={esEditor} />;
      default:
        return (
          <>
            <Embudo key={version} slug={slug} tipo={tipo} modulo={modulo} />
            {modulo === 'ventas' && <ResumenVentasSII slug={slug} />}
          </>
        );
    }
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', minWidth: 0, width: '100%' }}>
      <PageHeader title={seccion.label} crumbs={[{ label: nombre, to: `/app/${modulo}` }]} back="/app" backLabel="Inicio" />
      <Box sx={{ flex: 1, minWidth: 0, overflow: 'auto', px: 3, py: 2.5, display: 'flex', flexDirection: 'column', gap: 2 }}>
        {!slug ? <Typography sx={{ m: 'auto', color: 'text.secondary' }}>Primero tiene que crear su empresa en Afable.</Typography> : contenido()}
      </Box>
    </Box>
  );
}
