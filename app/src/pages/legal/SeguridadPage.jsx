import React from 'react';
import LegalLayout from './LegalLayout';

export default function SeguridadPage() {
  return (
    <LegalLayout
      title="Seguridad"
      updated="1 de agosto de 2026"
      intro="Medidas técnicas con las que Afable protege los accesos y la información de tu empresa."
    >
      <h2>Credenciales de conexión</h2>
      <p>
        Los usuarios, contraseñas y llaves de acceso de cada conexión se cifran antes de
        almacenarse, mediante cifrado simétrico autenticado Fernet (AES en modo CBC con HMAC de
        integridad). La llave de cifrado reside en la configuración del servidor, fuera de la base
        de datos, y no está disponible desde el panel de administración.
      </p>

      <h2>Consultas de solo lectura</h2>
      <p>
        Toda consulta generada por un agente se valida antes de ejecutarse contra tus sistemas. Se
        admiten únicamente sentencias <code>SELECT</code> y <code>WITH</code>, una por consulta. Se
        rechazan las operaciones de escritura y de definición de estructura, entre ellas{' '}
        <code>INSERT</code>, <code>UPDATE</code>, <code>DELETE</code>, <code>DROP</code> y{' '}
        <code>ALTER</code>. Una consulta que no cumple la validación no se ejecuta.
      </p>
      <p>Afable no puede modificar ni eliminar datos en los sistemas que conectas.</p>

      <h2>Tratamiento de los datos de tus sistemas</h2>
      <p>
        Afable no replica tus bases de datos. Almacena su estructura: nombres de tablas, nombres y
        tipos de columnas, relaciones entre tablas y cantidad de registros. Los registros se
        consultan en el momento de responder y no se conservan como copia.
      </p>

      <h2>Control de acceso</h2>
      <p>
        El acceso se administra por persona dentro de cada Workspace, mediante roles. Un usuario
        que no es miembro de un Workspace no accede a su información ni a su existencia. La
        resolución de permisos está centralizada en un único punto del sistema.
      </p>

      <h2>Cifrado en tránsito</h2>
      <p>
        El tráfico entre el navegador y Afable, y entre Afable y los sistemas conectados cuando el
        protocolo lo permite, se transmite sobre HTTPS/TLS.
      </p>

      <h2>Contraseñas de cuenta</h2>
      <p>
        Las contraseñas de las cuentas de Afable se almacenan mediante función de hash de un solo
        sentido. No son reversibles.
      </p>

      <h2>Proveedores de modelos de lenguaje</h2>
      <p>
        Para generar respuestas, Afable transmite la consulta y el contexto necesario a proveedores
        externos de modelos de lenguaje. Esta información sale de la infraestructura de Afable. El
        listado de proveedores en uso está disponible a solicitud en{' '}
        <a href="mailto:hi@getafable.com">hi@getafable.com</a>.
      </p>

      <h2>Eliminación de conexiones</h2>
      <p>
        Al eliminar una conexión se eliminan sus credenciales cifradas y la estructura almacenada
        de ese sistema.
      </p>

      <h2>Reporte de vulnerabilidades</h2>
      <p>
        Los reportes de seguridad se reciben en{' '}
        <a href="mailto:hi@getafable.com">hi@getafable.com</a>, con la información necesaria para
        reproducir el hallazgo. Cada reporte recibe respuesta con el resultado de su revisión. No
        se emprenden acciones legales contra quienes investigan de buena fe y notifican en privado
        antes de divulgar.
      </p>

      <h2>Tratamiento de datos personales</h2>
      <p>
        Las finalidades, plazos de conservación y derechos aplicables están detallados en la{' '}
        <a href="/privacidad">Política de privacidad</a>.
      </p>
    </LegalLayout>
  );
}
