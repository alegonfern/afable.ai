import { useCallback, useEffect, useMemo, useState } from 'react';
import { Box, Button, Chip, InputBase, Typography } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { Search } from 'lucide-react';
import { excel, googleDrive, odoo, postgresqlMarca, sap } from '../../assets/logos';
import { useWorkspace } from '../../context/WorkspaceContext';
import { api } from '../../services/api';
import DialogoConector from './DialogoConector';

/*
 * Ajustes › Conectores (26-10-2026): el catálogo de lo que Afable conecta, con el logo real de
 * cada servicio. Los que ya funcionan llevan a donde se configuran; los demás se muestran como
 * "Pronto", para que la empresa vea hacia dónde va la plataforma.
 *
 * Los logos viven en assets/logos (los de servicios ya conectados) y en assets/logos/integraciones
 * (el resto: marcas de Simple Icons con su color oficial, y los de servicios chilenos desde sus
 * sitios o Wikimedia Commons). Un conector sin logo usable muestra su inicial.
 */

const ARCHIVOS = import.meta.glob('../../assets/logos/integraciones/*.{svg,png,webp}', { eager: true, import: 'default' });
const LOGOS = {
  odoo, sap, googledrive: googleDrive, postgresql: postgresqlMarca, excel,
  ...Object.fromEntries(Object.entries(ARCHIVOS).map(([ruta, url]) => [ruta.split('/').pop().replace(/\.\w+$/, ''), url])),
};

const DISPONIBLE = 'disponible';
const PARCIAL = 'parcial';
const PRONTO = 'pronto';

// enlace: a dónde se configura (los disponibles). nota: qué hay hoy, en los parciales.
const CONECTORES = [
  // SII y obligaciones
  { id: 'sii', logo: 'sii', nombre: 'SII · Libros contables', cat: 'sii', estado: DISPONIBLE, conector: 'sii_rcv',
    desc: 'El Registro de Compras y Ventas descargado del SII con su certificado, listo para revisar en Contabilidad.',
    nota: 'También puede subir el archivo a mano en Contabilidad › Documentos.' },
  { id: 'sii-dte', logo: 'sii', nombre: 'SII · Facturación electrónica', cat: 'sii', estado: DISPONIBLE,
    desc: 'Facturas, notas, guías y el intercambio con proveedores, con el facturador de Afable.', enlace: '/app/ajustes/facturacion-electronica' },
  { id: 'previred', logo: 'previred', nombre: 'Previred', cat: 'sii', estado: PRONTO, desc: 'Las cotizaciones previsionales de cada mes, cuadradas con remuneraciones.' },
  // CRM
  { id: 'hubspot', logo: 'hubspot-marca', nombre: 'HubSpot', cat: 'crm', estado: DISPONIBLE, conector: 'hubspot',
    desc: 'Empresas y contactos como clientes, y cada negocio ganado como cotización en borrador.' },
  { id: 'salesforce', logo: 'salesforce-marca', nombre: 'Salesforce', cat: 'crm', estado: PRONTO, desc: 'Oportunidades cerradas y cuentas sincronizadas con Ventas.' },
  { id: 'pipedrive', logo: 'pipedrive', nombre: 'Pipedrive', cat: 'crm', estado: PRONTO, desc: 'Tratos ganados convertidos en órdenes de venta.' },
  { id: 'zoho', logo: 'zoho', nombre: 'Zoho CRM', cat: 'crm', estado: PRONTO, desc: 'Contactos y oportunidades conectados con Ventas.' },
  // Bancos
  { id: 'fintoc', logo: 'fintoc', nombre: 'Fintoc', cat: 'bancos', estado: PRONTO, desc: 'Cartolas de todos los bancos chilenos al día, para la caja y la conciliación.' },
  { id: 'bancochile', logo: 'bancochile', nombre: 'Banco de Chile', cat: 'bancos', estado: PARCIAL, desc: 'Movimientos de la cuenta para conciliar con lo del SII.', nota: 'Hoy: se sube la cartola en Finanzas.', enlace: '/app/finanzas/caja' },
  { id: 'bancoestado', logo: 'bancoestado', nombre: 'BancoEstado', cat: 'bancos', estado: PARCIAL, desc: 'Movimientos de la cuenta para conciliar con lo del SII.', nota: 'Hoy: se sube la cartola en Finanzas.', enlace: '/app/finanzas/caja' },
  { id: 'santander', logo: 'santander', nombre: 'Santander', cat: 'bancos', estado: PARCIAL, desc: 'Movimientos de la cuenta para conciliar con lo del SII.', nota: 'Hoy: se sube la cartola en Finanzas.', enlace: '/app/finanzas/caja' },
  { id: 'bci', logo: 'bci', nombre: 'BCI', cat: 'bancos', estado: PARCIAL, desc: 'Movimientos de la cuenta para conciliar con lo del SII.', nota: 'Hoy: se sube la cartola en Finanzas.', enlace: '/app/finanzas/caja' },
  { id: 'itau', logo: 'itau', nombre: 'Itaú', cat: 'bancos', estado: PARCIAL, desc: 'Movimientos de la cuenta para conciliar con lo del SII.', nota: 'Hoy: se sube la cartola en Finanzas.', enlace: '/app/finanzas/caja' },
  { id: 'scotiabank', logo: 'scotiabank', nombre: 'Scotiabank', cat: 'bancos', estado: PARCIAL, desc: 'Movimientos de la cuenta para conciliar con lo del SII.', nota: 'Hoy: se sube la cartola en Finanzas.', enlace: '/app/finanzas/caja' },
  { id: 'bice', logo: 'bice', nombre: 'BICE', cat: 'bancos', estado: PARCIAL, desc: 'Movimientos de la cuenta para conciliar con lo del SII.', nota: 'Hoy: se sube la cartola en Finanzas.', enlace: '/app/finanzas/caja' },
  { id: 'bbva', logo: 'bbva', nombre: 'BBVA', cat: 'bancos', estado: PRONTO, desc: 'Movimientos de la cuenta para conciliar.' },
  { id: 'global66', logo: 'global66', nombre: 'Global66', cat: 'bancos', estado: PRONTO, desc: 'Pagos y cobros en otras monedas, conciliados en pesos.' },
  // Pagos
  { id: 'transbank', logo: 'transbank', nombre: 'Transbank · Webpay', cat: 'pagos', estado: PRONTO, desc: 'Ventas con tarjeta y sus abonos, cuadrados con lo facturado.' },
  { id: 'mercadopago', logo: 'mercadopago', nombre: 'Mercado Pago', cat: 'pagos', estado: PRONTO, desc: 'Cobros, comisiones y liquidaciones conciliados.' },
  { id: 'flow', logo: 'flow', nombre: 'Flow', cat: 'pagos', estado: PRONTO, desc: 'Links de pago en cada cotización y sus pagos registrados solos.' },
  { id: 'khipu', logo: 'khipu', nombre: 'Khipu', cat: 'pagos', estado: PRONTO, desc: 'Cobros por transferencia con aviso y conciliación.' },
  { id: 'stripe', logo: 'stripe', nombre: 'Stripe', cat: 'pagos', estado: PRONTO, desc: 'Cobros internacionales y suscripciones.' },
  { id: 'paypal', logo: 'paypal', nombre: 'PayPal', cat: 'pagos', estado: PRONTO, desc: 'Cobros en el extranjero, en pesos al tipo de cambio del día.' },
  // E-commerce
  { id: 'shopify', logo: 'shopify', nombre: 'Shopify', cat: 'ecommerce', estado: PRONTO, desc: 'Pedidos de la tienda como órdenes de venta, con stock al día.' },
  { id: 'woocommerce', logo: 'woocommerce', nombre: 'WooCommerce', cat: 'ecommerce', estado: PRONTO, desc: 'Pedidos y stock sincronizados con su tienda WordPress.' },
  { id: 'mercadolibre', logo: 'mercadolibre', nombre: 'Mercado Libre', cat: 'ecommerce', estado: PRONTO, desc: 'Ventas del marketplace, comisiones y stock publicado.' },
  { id: 'jumpseller', logo: 'jumpseller', nombre: 'Jumpseller', cat: 'ecommerce', estado: PRONTO, desc: 'Pedidos y stock de su tienda chilena.' },
  { id: 'vtex', logo: 'vtex', nombre: 'VTEX', cat: 'ecommerce', estado: PRONTO, desc: 'Pedidos, inventario y catálogo de comercio a gran escala.' },
  { id: 'wix', logo: 'wix', nombre: 'Wix', cat: 'ecommerce', estado: PRONTO, desc: 'Ventas de su sitio Wix como órdenes de venta.' },
  { id: 'bsale', logo: 'bsale', nombre: 'Bsale', cat: 'ecommerce', estado: PRONTO, desc: 'Ventas del punto de venta y su stock, en un solo inventario.' },
  // ERP y contabilidad
  { id: 'odoo', logo: 'odoo', nombre: 'Odoo', cat: 'erp', estado: DISPONIBLE, desc: 'Lea sus datos de Odoo desde el chat y los agentes.', enlace: '/app/contexto?tab=integraciones' },
  { id: 'sap', logo: 'sap', nombre: 'SAP Business One', cat: 'erp', estado: DISPONIBLE, desc: 'Consulte su SAP B1 desde el chat y los agentes.', enlace: '/app/contexto?tab=integraciones' },
  { id: 'defontana', logo: 'defontana', nombre: 'Defontana', cat: 'erp', estado: PRONTO, desc: 'Traiga su contabilidad y documentos para migrar o convivir.' },
  { id: 'nubox', logo: 'nubox', nombre: 'Nubox', cat: 'erp', estado: PRONTO, desc: 'Contabilidad y remuneraciones de Nubox, leídas por Afable.' },
  { id: 'quickbooks', logo: 'quickbooks', nombre: 'QuickBooks', cat: 'erp', estado: PRONTO, desc: 'Para filiales o socios que llevan su contabilidad en QuickBooks.' },
  { id: 'xero', logo: 'xero', nombre: 'Xero', cat: 'erp', estado: PRONTO, desc: 'Contabilidad de Xero conectada a sus reportes.' },
  // Personas y gastos
  { id: 'buk', logo: 'buk', nombre: 'Buk', cat: 'personas', estado: PRONTO, desc: 'Remuneraciones del mes como gasto, por centro de costo.' },
  { id: 'talana', logo: 'talana', nombre: 'Talana', cat: 'personas', estado: PRONTO, desc: 'Liquidaciones y costos de personal en sus resultados.' },
  { id: 'rindegastos', logo: 'rindegastos', nombre: 'Rindegastos', cat: 'personas', estado: PRONTO, desc: 'Rendiciones aprobadas como gastos clasificados.' },
  // Logística
  { id: 'chilexpress', logo: 'chilexpress', nombre: 'Chilexpress', cat: 'logistica', estado: PRONTO, desc: 'Envíos desde cada entrega, con su número de seguimiento.' },
  { id: 'starken', logo: 'starken', nombre: 'Starken', cat: 'logistica', estado: PRONTO, desc: 'Órdenes de flete y seguimiento de despachos.' },
  { id: 'bluexpress', logo: 'bluexpress', nombre: 'Blue Express', cat: 'logistica', estado: PRONTO, desc: 'Envíos y seguimiento de cada despacho.' },
  // Productividad y comunicación
  { id: 'googledrive', logo: 'googledrive', nombre: 'Google Drive', cat: 'productividad', estado: DISPONIBLE, desc: 'Sus documentos como contexto para el chat y los agentes.', enlace: '/app/contexto?tab=integraciones' },
  { id: 'excel', logo: 'excel', nombre: 'Excel / CSV', cat: 'productividad', estado: DISPONIBLE, desc: 'Importe productos, contactos y stock, y exporte cualquier lista.', enlace: '/app/contexto?tab=integraciones' },
  { id: 'googlesheets', logo: 'googlesheets', nombre: 'Google Sheets', cat: 'productividad', estado: PRONTO, desc: 'Reportes que se actualizan solos en una planilla compartida.' },
  { id: 'gmail', logo: 'gmail', nombre: 'Gmail', cat: 'productividad', estado: PRONTO, desc: 'Facturas de proveedores que llegan al correo, leídas solas.' },
  { id: 'googlecalendar', logo: 'googlecalendar', nombre: 'Google Calendar', cat: 'productividad', estado: PRONTO, desc: 'Vencimientos de pagos, F29 y entregas en su calendario.' },
  { id: 'whatsapp', logo: 'whatsapp', nombre: 'WhatsApp Business', cat: 'productividad', estado: PRONTO, desc: 'Avisos de las automatizaciones y conversaciones con el agente.' },
  { id: 'slack', logo: 'slack', nombre: 'Slack', cat: 'productividad', estado: PRONTO, desc: 'Avisos y aprobaciones en los canales del equipo.' },
  { id: 'notion', logo: 'notion', nombre: 'Notion', cat: 'productividad', estado: PRONTO, desc: 'Procesos y políticas de la empresa como contexto para los agentes.' },
  { id: 'trello', logo: 'trello', nombre: 'Trello', cat: 'productividad', estado: PRONTO, desc: 'Tareas que nacen de una orden o de una alerta.' },
  { id: 'asana', logo: 'asana', nombre: 'Asana', cat: 'productividad', estado: PRONTO, desc: 'Proyectos conectados con su margen real.' },
  { id: 'dropbox', logo: 'dropbox', nombre: 'Dropbox', cat: 'productividad', estado: PRONTO, desc: 'Sus archivos como contexto, igual que Drive.' },
  // Marketing y datos
  { id: 'meta', logo: 'meta', nombre: 'Meta Ads', cat: 'marketing', estado: PRONTO, desc: 'Lo invertido en Facebook e Instagram contra lo vendido.' },
  { id: 'googleanalytics', logo: 'googleanalytics', nombre: 'Google Analytics', cat: 'marketing', estado: PRONTO, desc: 'Visitas y conversiones al lado de sus ventas.' },
  { id: 'mailchimp', logo: 'mailchimp', nombre: 'Mailchimp', cat: 'marketing', estado: PRONTO, desc: 'Listas de clientes segmentadas por lo que compran.' },
  { id: 'zapier', logo: 'zapier', nombre: 'Zapier', cat: 'marketing', estado: PRONTO, desc: 'Conecte Afable con miles de aplicaciones más.' },
  { id: 'postgresql', logo: 'postgresql', nombre: 'PostgreSQL', cat: 'marketing', estado: DISPONIBLE, desc: 'Consulte sus bases de datos desde el chat.', enlace: '/app/contexto?tab=integraciones' },
];

const CATEGORIAS = [
  ['sii', 'SII y obligaciones'], ['crm', 'CRM y ventas'], ['bancos', 'Bancos'], ['pagos', 'Pagos'],
  ['ecommerce', 'E-commerce y punto de venta'], ['erp', 'ERP y contabilidad'], ['personas', 'Personas y gastos'],
  ['logistica', 'Logística'], ['productividad', 'Productividad y comunicación'], ['marketing', 'Marketing, datos y más'],
];
const ESTADOS = {
  conectado: { nombre: 'Conectado', color: '#0f9d6b' },
  error: { nombre: 'Con error', color: '#c8102e' },
  [DISPONIBLE]: { nombre: 'Disponible', color: '#0f9d6b' },
  [PARCIAL]: { nombre: 'Por archivo', color: '#b45309' },
  [PRONTO]: { nombre: 'Pronto', color: '#6b7280' },
};

function Logo({ c }) {
  const src = LOGOS[c.logo];
  return (
    <Box sx={{ width: 64, height: 48, flexShrink: 0, borderRadius: '12px', bgcolor: '#fff', border: '1px solid rgba(0,0,0,0.08)',
      display: 'grid', placeItems: 'center', p: src ? '7px' : 0, boxSizing: 'border-box' }}>
      {src ? <Box component="img" src={src} alt="" sx={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain', display: 'block' }} />
        : <Typography sx={{ fontWeight: 700, fontSize: '1.1rem', color: '#1f2328' }}>{c.nombre[0]}</Typography>}
    </Box>
  );
}

function Tarjeta({ c, vivo, onAbrir }) {
  const navigate = useNavigate();
  // Los conectores con backend propio muestran su estado real (conectado, con error o disponible).
  const e = ESTADOS[vivo && vivo.estado !== 'desconectado' ? vivo.estado : c.estado];
  return (
    <Box sx={{ border: '1px solid', borderColor: 'divider', borderRadius: '14px', bgcolor: 'background.paper', p: 2,
      display: 'flex', flexDirection: 'column', gap: 1.25, minHeight: 168, transition: 'border-color .15s',
      '&:hover': { borderColor: c.enlace ? 'text.secondary' : 'divider' } }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
        <Logo c={c} />
        <Box sx={{ minWidth: 0, flex: 1 }}>
          <Typography sx={{ fontWeight: 600, fontSize: '0.92rem', lineHeight: 1.3 }}>{c.nombre}</Typography>
          <Box component="span" sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5, fontSize: '0.74rem', color: 'text.secondary', mt: 0.25 }}>
            <Box component="span" sx={{ width: 7, height: 7, borderRadius: '50%', bgcolor: e.color }} />{e.nombre}
          </Box>
        </Box>
      </Box>
      <Typography sx={{ fontSize: '0.82rem', color: 'text.secondary', lineHeight: 1.5, flex: 1 }}>{c.desc}</Typography>
      {c.nota && <Typography sx={{ fontSize: '0.76rem', color: 'text.secondary', lineHeight: 1.45 }}>{c.nota}</Typography>}
      {c.conector && (
        <Box>
          <Button size="small" variant={vivo?.estado === 'conectado' ? 'outlined' : 'contained'} onClick={onAbrir}>
            {vivo && vivo.estado !== 'desconectado' ? 'Gestionar' : 'Conectar'}
          </Button>
        </Box>
      )}
      {!c.conector && c.enlace && (
        <Box>
          <Button size="small" variant={c.estado === DISPONIBLE ? 'contained' : 'outlined'} onClick={() => navigate(c.enlace)}>
            {c.estado === DISPONIBLE ? 'Configurar' : 'Ir a cargar'}
          </Button>
        </Box>
      )}
    </Box>
  );
}

export default function Conectores() {
  const { slug } = useWorkspace();
  const [q, setQ] = useState('');
  const [cat, setCat] = useState('');
  const [vivos, setVivos] = useState({});
  const [abierto, setAbierto] = useState(null);
  const cargar = useCallback(() => {
    if (!slug) return;
    api.conectores.lista(slug).then(({ data }) => setVivos(Object.fromEntries(data.map((x) => [x.tipo, x])))).catch(() => {});
  }, [slug]);
  useEffect(() => { cargar(); }, [cargar]);
  const visibles = useMemo(() => {
    const t = q.trim().toLowerCase();
    return CONECTORES.filter((c) => (!cat || c.cat === cat) && (!t || `${c.nombre} ${c.desc}`.toLowerCase().includes(t)));
  }, [q, cat]);
  const disponibles = CONECTORES.filter((c) => c.estado !== PRONTO).length;
  return (
    <Box sx={{ display: 'grid', gap: 2 }}>
      <Typography sx={{ color: 'text.secondary', fontSize: '0.86rem' }}>
        {disponibles} ya se pueden usar; el resto viene en camino.
      </Typography>
      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', alignItems: 'center' }}>
        <InputBase placeholder="Buscar un conector" value={q} onChange={(e) => setQ(e.target.value)}
          startAdornment={<Search size={14} style={{ marginRight: 6, opacity: 0.5 }} />} inputProps={{ 'aria-label': 'Buscar un conector' }}
          sx={{ border: '1px solid', borderColor: 'divider', borderRadius: '8px', px: 1.25, py: 0.4, fontSize: '0.86rem', minWidth: 240, bgcolor: 'background.paper' }} />
        <Chip label="Todos" size="small" onClick={() => setCat('')} variant={cat ? 'outlined' : 'filled'} sx={{ fontFamily: 'inherit' }} />
        {CATEGORIAS.map(([k, n]) => (
          <Chip key={k} label={n} size="small" onClick={() => setCat(cat === k ? '' : k)} variant={cat === k ? 'filled' : 'outlined'}
            sx={{ fontFamily: 'inherit' }} />
        ))}
      </Box>
      {CATEGORIAS.filter(([k]) => visibles.some((c) => c.cat === k)).map(([k, n]) => (
        <Box key={k} sx={{ display: 'grid', gap: 1.25 }}>
          <Typography sx={{ fontSize: '0.72rem', fontWeight: 600, letterSpacing: '0.07em', textTransform: 'uppercase', color: 'text.secondary' }}>{n}</Typography>
          <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: 1.5 }}>
            {visibles.filter((c) => c.cat === k).map((c) => (
              <Tarjeta key={c.id} c={c} vivo={c.conector ? vivos[c.conector] : null} onAbrir={() => setAbierto(c)} />
            ))}
          </Box>
        </Box>
      ))}
      {visibles.length === 0 && <Typography sx={{ color: 'text.secondary', fontSize: '0.88rem' }}>Ningún conector con «{q}».</Typography>}
      {abierto && <DialogoConector tipo={abierto.conector} nombre={abierto.nombre} onCerrar={() => { setAbierto(null); cargar(); }} onCambio={cargar} />}
    </Box>
  );
}
