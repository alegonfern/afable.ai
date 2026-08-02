import odoo from './odoo.png';
import sap from './sap.webp';
import googleDrive from './google-drive.png';
// PostgreSQL viene como bloque vertical (elefante arriba, texto abajo). En una
// baldosa chica el texto queda en unos 5px y no se lee, así que para iconos se
// usa la marca sola; el bloque completo queda disponible para usos grandes.
import postgresqlMarca from './postgresql-marca.webp';
import postgresqlBloque from './postgresql.webp';
import excel from './excel.webp';

/**
 * Logos reales de los servicios que conectamos.
 *
 * Registro único: cualquier vista que muestre un servicio resuelve el logo por
 * nombre con `logoDeServicio()`. Así las plantillas que vienen del backend
 * (que solo traen el nombre de la app y un emoji) también salen con el logo
 * real, sin tocar el backend.
 *
 * Las claves van en minúscula y sin acentos. Se admiten alias porque el mismo
 * servicio aparece nombrado de varias formas ("Drive", "Google Drive").
 */
const LOGOS = {
  'odoo': odoo,

  'sap': sap,
  'sap b1': sap,
  'sap business one': sap,

  'drive': googleDrive,
  'google drive': googleDrive,

  'postgresql': postgresqlMarca,
  'postgres': postgresqlMarca,

  // El conector se llama "Excel / CSV": el logo es el de Excel, que es la marca
  // reconocible, y el nombre al lado sigue diciendo que también acepta CSV.
  'excel': excel,
  'excel / csv': excel,
};

/** Devuelve el logo del servicio, o null si todavía no tenemos uno real. */
export function logoDeServicio(nombre) {
  if (!nombre) return null;
  return LOGOS[String(nombre).trim().toLowerCase()] || null;
}

export { odoo, sap, googleDrive, postgresqlMarca, postgresqlBloque, excel };
