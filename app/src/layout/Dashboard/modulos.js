// Los módulos y sus dos vistas, compartidos entre la barra lateral (que lleva a cada
// módulo) y el encabezado (donde vive el selector Módulo / Automatización, al estilo de
// Kapso: es una decisión de la página, no de la navegación).

// Los módulos del PMV (Finanzas se sumó el 17-10-2026, Compras el 22-10-2026). Detrás de cada uno
// hay un agente con su nombre (25-10-2026): el panel lateral es la conversación con él y su vista
// "Agente" es su espacio (conversación, automatizaciones y lo que hizo hoy).
export const MODULOS = [
  { slug: 'ventas',       label: 'Ventas',       agente: 'Agente de Ventas' },
  { slug: 'compras',      label: 'Compras',      agente: 'Agente de Compras' },
  // Inventario es módulo propio desde el 26-10-2026: Ventas y Compras muestran productos; el
  // stock, los movimientos y las bodegas, aquí.
  { slug: 'inventario',   label: 'Inventario',   agente: 'Agente de Inventario' },
  { slug: 'contabilidad', label: 'Contabilidad', agente: 'Agente de Contabilidad' },
  { slug: 'finanzas',     label: 'Finanzas',     agente: 'Agente de Finanzas' },
];
export const agenteDe = (slug) => MODULOS.find((m) => m.slug === slug)?.agente || null;

// Las secciones de cada módulo: el submenú de la barra lateral y la tercera parte del
// encabezado (Inicio / Contabilidad / Documentos). La primera es la que abre el módulo.
export const SECCIONES = {
  // Ventas y Compras siguen el camino de los documentos de Odoo (22-10-2026); los clientes y
  // proveedores son la misma ficha de contacto, vista desde cada lado.
  ventas: [
    { slug: 'resumen', label: 'Resumen' },
    { slug: 'cotizaciones', label: 'Cotizaciones' },
    { slug: 'ordenes', label: 'Órdenes de venta' },
    { slug: 'entregas', label: 'Entregas' },
    { slug: 'por-facturar', label: 'Por facturar' },
    { slug: 'clientes', label: 'Clientes' },
    { slug: 'productos', label: 'Productos' },
    { slug: 'reportes', label: 'Reportes' },
  ],
  compras: [
    { slug: 'resumen', label: 'Resumen' },
    { slug: 'cotizaciones', label: 'Solicitudes' },
    { slug: 'ordenes', label: 'Órdenes de compra' },
    { slug: 'entregas', label: 'Recepciones' },
    { slug: 'por-facturar', label: 'Por facturar' },
    { slug: 'proveedores', label: 'Proveedores' },
    { slug: 'productos', label: 'Productos' },
    { slug: 'reportes', label: 'Reportes' },
    { slug: 'recibidos', label: 'Documentos recibidos', dte: true },
  ],
  inventario: [
    { slug: 'resumen', label: 'Resumen' },
    { slug: 'stock', label: 'Stock' },
    { slug: 'movimientos', label: 'Movimientos' },
    { slug: 'conteos', label: 'Toma de inventario' },
    { slug: 'reportes', label: 'Reportes' },
    { slug: 'bodegas', label: 'Bodegas' },
  ],
  contabilidad: [
    { slug: 'resumen', label: 'Resumen' },
    { slug: 'documentos', label: 'Documentos' },
    { slug: 'impuestos', label: 'Impuestos' },
    { slug: 'conciliacion', label: 'Conciliación' },
    { slug: 'categorias', label: 'Categorías' },
    { slug: 'proyectos', label: 'Proyectos' },
  ],
  finanzas: [
    { slug: 'caja', label: 'Caja' },
    { slug: 'por-cobrar', label: 'Por cobrar' },
    { slug: 'por-pagar', label: 'Por pagar' },
    { slug: 'cuenta-dueno', label: 'Su cuenta con la empresa' },
  ],
};

// Las del facturador electrónico (`dte`) solo se listan si está habilitado para la empresa.
export const seccionesDe = (slug, { dte = false } = {}) => (SECCIONES[slug] || []).filter((s) => dte || !s.dte);
export const seccionDe = (slug, seccion) => {
  const lista = SECCIONES[slug] || [];
  return lista.find((s) => s.slug === seccion) || lista[0] || null;
};

// La clave 'automatizacion' (y su ruta /automatizaciones) se conserva para no romper enlaces; desde el
// 25-10-2026 esa vista es "Agente": el espacio de IA del módulo, que incluye sus automatizaciones.
export const VISTAS = [
  { key: 'modulo',         label: 'Módulo' },
  { key: 'automatizacion', label: 'Agente' },
];

export const rutaDe = (slug, vista) => (vista === 'automatizacion'
  ? `/app/${slug}/automatizaciones`
  : `/app/${slug}`);

// El módulo de la ruta actual y en cuál de sus dos páginas se está, o null.
export function moduloDeRuta(pathname) {
  const m = MODULOS.find((x) =>
    pathname === `/app/${x.slug}` || pathname.startsWith(`/app/${x.slug}/`));
  if (!m) return null;
  const automatizacion = pathname.endsWith('/automatizaciones');
  // /app/contabilidad/documentos → 'documentos'. Sin sección: la primera del módulo.
  const resto = pathname.slice(`/app/${m.slug}`.length).split('/').filter(Boolean);
  const seccion = automatizacion ? null : (resto[0] || seccionesDe(m.slug)[0]?.slug || null);
  return { ...m, vista: automatizacion ? 'automatizacion' : 'modulo', seccion };
}

// La última vista elegida: al entrar a otro módulo desde la barra se llega a la misma.
const CLAVE = 'afable_vista';
export const vistaGuardada = () => {
  try { return localStorage.getItem(CLAVE) === 'automatizacion' ? 'automatizacion' : 'modulo'; }
  catch { return 'modulo'; }
};
export const guardarVista = (v) => {
  try { localStorage.setItem(CLAVE, v); } catch { /* sin almacenamiento: no se recuerda */ }
};
