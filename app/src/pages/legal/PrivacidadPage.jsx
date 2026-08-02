import React from 'react';
import LegalLayout from './LegalLayout';

export default function PrivacidadPage() {
  return (
    <LegalLayout
      title="Política de privacidad"
      updated="1 de agosto de 2026"
      intro="Información que Afable trata, con qué finalidad, durante cuánto tiempo y con qué derechos cuentas sobre ella."
    >
      <h2>1. Responsable</h2>
      <p>
        Afable es un servicio operado desde Chile. Las consultas sobre esta política se reciben en{' '}
        <a href="mailto:hi@getafable.com">hi@getafable.com</a>.
      </p>

      <h2>2. Información que tratamos</h2>

      <h3>Datos de la cuenta</h3>
      <p>
        Nombre, correo electrónico y contraseña. En el registro mediante Google: nombre, correo
        electrónico y fotografía de perfil. De forma opcional, nombre y rubro de la empresa.
      </p>

      <h3>Contenido del Workspace</h3>
      <p>
        Datos de la empresa, archivos cargados, carpetas sincronizadas, y las personas invitadas
        con sus respectivos roles.
      </p>

      <h3>Credenciales de conexión</h3>
      <p>
        Datos de acceso a los sistemas que conectas, almacenados cifrados. Las medidas técnicas
        están detalladas en <a href="/seguridad">Seguridad</a>.
      </p>

      <h3>Estructura de los sistemas conectados</h3>
      <p>
        Nombres de tablas y columnas, relaciones y cantidad de registros. Afable no conserva una
        copia de los registros: se consultan en el momento de responder.
      </p>

      <h3>Conversaciones</h3>
      <p>
        Las consultas realizadas por los miembros del Workspace y las respuestas generadas se
        almacenan en el Workspace correspondiente.
      </p>

      <h3>Datos de uso</h3>
      <p>Registros técnicos de la aplicación: accesos, errores y funcionalidades utilizadas.</p>

      <h2>3. Finalidades</h2>
      <ul>
        <li>Prestación del servicio: respuesta a consultas, ejecución de disparadores y administración de accesos.</li>
        <li>Operación y continuidad: monitoreo, respaldos y diagnóstico de fallas.</li>
        <li>Facturación y cobro de los planes contratados.</li>
        <li>Comunicaciones relativas a la cuenta y a cambios en el servicio.</li>
      </ul>
      <p>
        Afable no comercializa esta información, no la cede a terceros con fines publicitarios y no
        la utiliza para el entrenamiento de modelos.
      </p>

      <h2>4. Terceros que intervienen</h2>
      <ul>
        <li>
          Proveedores de modelos de lenguaje, a los que se transmite la consulta y el contexto
          necesario para generar cada respuesta.
        </li>
        <li>Proveedor de infraestructura donde se ejecutan la aplicación y su base de datos.</li>
        <li>Proveedor de correo transaccional, para notificaciones del servicio.</li>
        <li>
          Procesador de pagos, en el caso de planes contratados. Afable no almacena datos de
          tarjetas.
        </li>
      </ul>
      <p>
        La información podrá entregarse a la autoridad competente cuando exista un requerimiento
        legal válido.
      </p>

      <h2>5. Plazos de conservación</h2>
      <ul>
        <li>El contenido del Workspace se conserva mientras la cuenta permanezca activa.</li>
        <li>
          La eliminación de una conexión implica la eliminación de sus credenciales y de la
          estructura almacenada de ese sistema.
        </li>
        <li>
          El cierre de la cuenta implica la eliminación de los datos asociados dentro de los 30
          días siguientes, con excepción de aquellos que deban conservarse por obligación legal o
          contable.
        </li>
        <li>Los registros técnicos se conservan por períodos acotados y luego se descartan.</li>
      </ul>

      <h2>6. Derechos</h2>
      <p>
        Puedes solicitar el acceso, la rectificación, la eliminación y la portabilidad de la
        información que te concierne, escribiendo a{' '}
        <a href="mailto:hi@getafable.com">hi@getafable.com</a> desde el correo asociado a tu
        cuenta.
      </p>
      <p>
        Cuando el Workspace es administrado por otra empresa, parte de esa información queda bajo
        su control. En ese caso la solicitud se deriva a la empresa administradora.
      </p>

      <h2>7. Menores de edad</h2>
      <p>Afable es un servicio dirigido a empresas y no está destinado a menores de 18 años.</p>

      <h2>8. Modificaciones</h2>
      <p>
        Las modificaciones a esta política se reflejan en la fecha de actualización del
        encabezado. Los cambios que afecten el tratamiento de la información se comunican por
        correo electrónico antes de su entrada en vigencia.
      </p>
    </LegalLayout>
  );
}
