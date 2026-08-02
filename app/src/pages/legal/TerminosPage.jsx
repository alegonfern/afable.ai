import React from 'react';
import LegalLayout from './LegalLayout';

export default function TerminosPage() {
  return (
    <LegalLayout
      title="Términos de servicio"
      updated="1 de agosto de 2026"
      intro="Condiciones aplicables al uso de Afable. La creación de una cuenta implica su aceptación."
    >
      <h2>1. Servicio</h2>
      <p>
        Afable es una plataforma que conecta los sistemas y archivos de una empresa para que su
        equipo pueda consultarlos y automatizar tareas mediante inteligencia artificial. El
        servicio se presta según las funcionalidades disponibles en cada momento, las que pueden
        variar.
      </p>

      <h2>2. Cuenta</h2>
      <ul>
        <li>La información entregada en el registro debe ser veraz y mantenerse actualizada.</li>
        <li>El titular es responsable del uso de su cuenta y del resguardo de sus credenciales.</li>
        <li>
          El titular debe ser mayor de edad y contar con facultades para obligar a la empresa que
          representa.
        </li>
        <li>Todo uso no autorizado debe ser informado a Afable en cuanto se detecte.</li>
      </ul>

      <h2>3. Workspace</h2>
      <p>
        Quien crea un Workspace lo administra y define sus miembros, roles y niveles de acceso.
        Cuando un usuario es incorporado al Workspace de otra empresa, dicha empresa administra ese
        espacio y su contenido. La información cargada en un Workspace pertenece a la empresa que
        lo administra.
      </p>

      <h2>4. Titularidad de la información</h2>
      <p>
        Afable no adquiere derechos de propiedad sobre la información que conectas o cargas. Su
        tratamiento se limita a lo necesario para la prestación del servicio, conforme a la{' '}
        <a href="/privacidad">Política de privacidad</a> y a las medidas descritas en{' '}
        <a href="/seguridad">Seguridad</a>.
      </p>

      <h2>5. Uso permitido</h2>
      <p>No está permitido utilizar Afable para:</p>
      <ul>
        <li>Conectar sistemas o datos sobre los que no se cuenta con autorización.</li>
        <li>Actividades ilícitas o que vulneren derechos de terceros.</li>
        <li>Vulnerar, sobrecargar o eludir los límites técnicos del servicio.</li>
        <li>
          Revender el servicio o facilitar su acceso a terceros ajenos a la empresa titular, sin
          acuerdo previo con Afable.
        </li>
      </ul>

      <h2>6. Resultados generados</h2>
      <p>
        Las respuestas se generan mediante modelos de lenguaje a partir de la información
        conectada y pueden contener errores. No constituyen asesoría contable, tributaria, legal ni
        financiera. Las decisiones basadas en ellas requieren verificación previa en la fuente
        correspondiente.
      </p>

      <h2>7. Planes y pagos</h2>
      <ul>
        <li>Los precios aplicables son los publicados en el sitio.</li>
        <li>Los planes de pago se cobran por anticipado según la periodicidad contratada.</li>
        <li>
          La cancelación puede solicitarse en cualquier momento y el servicio permanece disponible
          hasta el término del período pagado.
        </li>
        <li>
          Las modificaciones de precio se comunican antes de su aplicación a la siguiente
          renovación.
        </li>
      </ul>

      <h2>8. Disponibilidad</h2>
      <p>
        El servicio puede presentar interrupciones por mantenimiento, fallas o incidencias de
        proveedores. Las interrupciones programadas de duración significativa se comunican con
        anticipación. El servicio no contempla un acuerdo de nivel de servicio con disponibilidad
        garantizada.
      </p>

      <h2>9. Propiedad intelectual</h2>
      <p>
        La plataforma, su código, su marca y su diseño son de titularidad de Afable. El contenido y
        los datos del usuario permanecen bajo su titularidad. Las sugerencias sobre el producto
        pueden ser implementadas sin generar obligaciones a favor de quien las formula.
      </p>

      <h2>10. Suspensión y término</h2>
      <p>
        El usuario puede cerrar su cuenta en cualquier momento. Afable puede suspender una cuenta
        por incumplimiento grave de estos términos, por falta de pago, o cuando su uso comprometa
        la seguridad del servicio o de otros usuarios. Salvo casos de urgencia, la suspensión se
        notifica previamente otorgando un plazo de subsanación.
      </p>
      <p>
        Terminada la relación, el usuario puede solicitar una copia de su información dentro de los
        30 días siguientes.
      </p>

      <h2>11. Responsabilidad</h2>
      <p>
        El servicio se presta sin garantías distintas de las exigidas por la ley. En la medida en
        que la ley lo permita, la responsabilidad total de Afable se limita al monto pagado por el
        servicio durante los 12 meses anteriores al hecho que motive el reclamo, y no comprende
        lucro cesante ni daños indirectos. Lo anterior no limita las responsabilidades que la ley
        declara indisponibles.
      </p>

      <h2>12. Modificaciones</h2>
      <p>
        Estos términos pueden ser actualizados. Las modificaciones relevantes se comunican por
        correo electrónico antes de su entrada en vigencia. El uso del servicio con posterioridad a
        esa fecha implica su aceptación.
      </p>

      <h2>13. Ley aplicable</h2>
      <p>
        Estos términos se rigen por la ley chilena. Las controversias se someten a los tribunales
        de Santiago de Chile.
      </p>
    </LegalLayout>
  );
}
