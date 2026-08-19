"""Pruebas de las Sesiones.

Lo que cubren, en orden de importancia: el permiso de dos niveles (Workspace y después
Sesión, con la diferencia entre no verla —404— y verla sin poder administrarla —403—),
que una Sesión restringida esconda su contenido, y que las Tareas y los Archivos hayan
llegado enteros a su contenedor nuevo.

La ejecución de tareas no habla con ningún modelo: `_run_prompt` se reemplaza.
"""

import unittest.mock as mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from apps.agents.models import Agent
from apps.organizations.models import CompanyDocument, Organization
from apps.sesiones.models import (
    ROL_EDITOR, ROL_MIEMBRO, VISIBILIDAD_RESTRINGIDA,
    Sesion, SesionMiembro, TAREA_LISTA, Task,
)
from apps.workspaces.models import ROLE_ADMIN, ROLE_MEMBER, Workspace

User = get_user_model()

URL = '/api/v1/sesiones/'


class BaseSesiones(TestCase):

    def setUp(self):
        self.client = APIClient()

        self.admin = User.objects.create_user(
            username='admin@afable.test', email='admin@afable.test', password='afable123',
        )
        self.colega = User.objects.create_user(
            username='colega@afable.test', email='colega@afable.test', password='afable123',
        )
        self.ajeno = User.objects.create_user(
            username='ajeno@afable.test', email='ajeno@afable.test', password='afable123',
        )

        self.org = Organization.objects.create(owner=self.admin, name='Cocinas SpA')
        self.ws = Workspace.objects.create(organization=self.org, name='General')
        self.org.agregar_miembro(self.admin, ROLE_ADMIN)
        self.org.agregar_miembro(self.colega, ROLE_MEMBER)

        self.agente = Agent.objects.create(organization=self.org, name='Cobranzas')

        self.sesion = Sesion.objects.create(
            workspace=self.ws, name='Cliente Rever', created_by=self.admin,
        )

    def como(self, quien):
        self.client.force_authenticate(user=quien)

    def url(self, sufijo='', sesion=None):
        return f'{URL}{(sesion or self.sesion).slug}/{sufijo}'

    def q(self):
        return {'workspace': self.org.slug}


class PermisoTests(BaseSesiones):

    def test_una_sesion_abierta_la_ve_cualquier_miembro_del_workspace(self):
        """Eso es lo que significa «abierta»: no hace falta estar agregado."""
        self.como(self.colega)
        r = self.client.get(self.url(), self.q())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['mi_rol'], ROL_MIEMBRO)
        self.assertFalse(r.data['puedo_administrar'])

    def test_quien_no_es_del_workspace_no_sabe_que_existe(self):
        self.como(self.ajeno)
        self.assertEqual(self.client.get(self.url(), self.q()).status_code, 404)

    def test_una_sesion_restringida_no_se_ve_sin_estar_agregado(self):
        self.sesion.visibility = VISIBILIDAD_RESTRINGIDA
        self.sesion.save(update_fields=['visibility'])
        self.como(self.colega)
        self.assertEqual(self.client.get(self.url(), self.q()).status_code, 404)

    def test_agregado_a_la_restringida_si_entra(self):
        self.sesion.visibility = VISIBILIDAD_RESTRINGIDA
        self.sesion.save(update_fields=['visibility'])
        SesionMiembro.objects.create(sesion=self.sesion, user=self.colega, role=ROL_MIEMBRO)
        self.como(self.colega)
        self.assertEqual(self.client.get(self.url(), self.q()).status_code, 200)

    def test_el_administrador_del_workspace_entra_siempre_como_editor(self):
        """No puede administrar lo que no ve."""
        self.sesion.visibility = VISIBILIDAD_RESTRINGIDA
        self.sesion.save(update_fields=['visibility'])
        self.como(self.admin)
        r = self.client.get(self.url(), self.q())
        self.assertEqual(r.data['mi_rol'], ROL_EDITOR)

    def test_un_miembro_ve_la_sesion_pero_no_la_configura(self):
        """403 y no 404: la diferencia entre no verla y no poder tocarla importa."""
        self.como(self.colega)
        r = self.client.patch(self.url(), {**self.q(), 'name': 'Secuestrada'}, format='json')
        self.assertEqual(r.status_code, 403)
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.name, 'Cliente Rever')

    def test_solo_un_administrador_del_workspace_borra_una_sesion(self):
        """Borrar se lleva conversaciones, tareas y archivos del equipo."""
        SesionMiembro.objects.create(sesion=self.sesion, user=self.colega, role=ROL_EDITOR)
        self.como(self.colega)
        self.assertEqual(self.client.delete(self.url(), self.q()).status_code, 403)

        self.como(self.admin)
        self.assertEqual(self.client.delete(self.url(), self.q()).status_code, 204)
        self.assertEqual(Sesion.objects.count(), 0)

    def test_la_sesion_de_otro_workspace_no_se_alcanza_por_slug(self):
        otra_org = Organization.objects.create(owner=self.ajeno, name='Muebles Ltda')
        otro_ws = Workspace.objects.create(organization=otra_org, name='General')
        otro_ws.organization.agregar_miembro(self.ajeno, ROLE_ADMIN)
        ajena = Sesion.objects.create(workspace=otro_ws, name='Cliente Rever')

        self.como(self.admin)
        r = self.client.get(f'{URL}{ajena.slug}/', self.q())
        # Mismo slug, otro Workspace: no existe para mí.
        self.assertEqual(r.data['id'], self.sesion.id)


class CreacionYAjustesTests(BaseSesiones):

    def test_quien_la_crea_queda_editor(self):
        """Si no, nadie podría configurar la Sesión que acaba de abrir."""
        self.como(self.colega)
        r = self.client.post(
            URL, {'workspace': self.org.slug, 'name': 'Cierre de mes'}, format='json',
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['mi_rol'], ROL_EDITOR)

    def test_sin_nombre_no_se_crea(self):
        self.como(self.admin)
        r = self.client.post(URL, {'workspace': self.org.slug, 'name': '  '}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_el_slug_se_arma_solo_y_no_choca(self):
        self.como(self.admin)
        r = self.client.post(
            URL, {'workspace': self.org.slug, 'name': 'Cliente Rever'}, format='json',
        )
        self.assertEqual(r.data['slug'], 'cliente-rever-2')

    def test_renombrar_no_cambia_el_slug(self):
        """Es la URL de la Sesión: cambiarla rompe los enlaces que el equipo se pasó."""
        antes = self.sesion.slug
        self.como(self.admin)
        self.client.patch(self.url(), {**self.q(), 'name': 'Otro nombre'}, format='json')
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.slug, antes)
        self.assertEqual(self.sesion.name, 'Otro nombre')

    def test_una_visibilidad_inventada_no_pasa(self):
        self.como(self.admin)
        r = self.client.patch(
            self.url(), {**self.q(), 'visibility': 'secretisima'}, format='json',
        )
        self.assertEqual(r.status_code, 400)

    def test_archivar_no_borra_y_la_saca_de_la_lista(self):
        self.como(self.admin)
        self.client.patch(self.url(), {**self.q(), 'archivada': True}, format='json')
        self.sesion.refresh_from_db()
        self.assertTrue(self.sesion.archivada)
        self.assertIsNotNone(self.sesion.archivada_at)

        self.assertEqual(self.client.get(URL, self.q()).data['count'], 0)
        con_archivadas = self.client.get(URL, {**self.q(), 'archivadas': '1'})
        self.assertEqual(con_archivadas.data['count'], 1)

    def test_desarchivar_limpia_la_fecha(self):
        self.como(self.admin)
        self.client.patch(self.url(), {**self.q(), 'archivada': True}, format='json')
        self.client.patch(self.url(), {**self.q(), 'archivada': False}, format='json')
        self.sesion.refresh_from_db()
        self.assertFalse(self.sesion.archivada)
        self.assertIsNone(self.sesion.archivada_at)


class MiembrosTests(BaseSesiones):

    def test_un_editor_agrega_gente_del_workspace(self):
        self.como(self.admin)
        r = self.client.post(
            self.url('miembros/'),
            {**self.q(), 'ids': [self.colega.id], 'role': ROL_EDITOR}, format='json',
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            SesionMiembro.objects.get(sesion=self.sesion, user=self.colega).role, ROL_EDITOR,
        )

    def test_no_se_agrega_a_alguien_de_fuera_del_workspace(self):
        """Para eso están las invitaciones al Workspace, no una Sesión."""
        self.como(self.admin)
        r = self.client.post(
            self.url('miembros/'), {**self.q(), 'ids': [self.ajeno.id]}, format='json',
        )
        self.assertEqual(r.status_code, 400)
        self.assertEqual(SesionMiembro.objects.filter(user=self.ajeno).count(), 0)

    def test_un_miembro_simple_no_agrega_gente(self):
        self.como(self.colega)
        r = self.client.post(
            self.url('miembros/'), {**self.q(), 'ids': [self.ajeno.id]}, format='json',
        )
        self.assertEqual(r.status_code, 403)

    def test_se_saca_a_alguien(self):
        SesionMiembro.objects.create(sesion=self.sesion, user=self.colega, role=ROL_MIEMBRO)
        self.como(self.admin)
        r = self.client.delete(
            self.url('miembros/'), {**self.q(), 'ids': [self.colega.id]}, format='json',
        )
        self.assertEqual(r.status_code, 200)
        self.assertFalse(SesionMiembro.objects.filter(user=self.colega).exists())

    def test_los_disponibles_no_repiten_a_quien_ya_esta(self):
        self.como(self.admin)
        antes = self.client.get(self.url('disponibles/'), self.q()).data['personas']
        self.assertIn(self.colega.id, [p['id'] for p in antes])

        SesionMiembro.objects.create(sesion=self.sesion, user=self.colega, role=ROL_MIEMBRO)
        despues = self.client.get(self.url('disponibles/'), self.q()).data['personas']
        self.assertNotIn(self.colega.id, [p['id'] for p in despues])


class TareasTests(BaseSesiones):
    """Las Tareas se mudaron del Espacio a la Sesión: tienen que seguir enteras."""

    def crear(self, **datos):
        self.como(self.admin)
        cuerpo = {**self.q(), 'title': 'Revisar facturas'}
        cuerpo.update(datos)
        return self.client.post(self.url('tareas/'), cuerpo, format='json')

    def test_se_crea_en_la_sesion(self):
        r = self.crear()
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Task.objects.get(pk=r.data['id']).sesion_id, self.sesion.id)

    def test_cualquier_miembro_de_la_sesion_crea_una_tarea(self):
        self.como(self.colega)
        r = self.client.post(
            self.url('tareas/'), {**self.q(), 'title': 'Algo'}, format='json',
        )
        self.assertEqual(r.status_code, 201)

    def test_las_pendientes_van_arriba(self):
        Task.objects.create(sesion=self.sesion, title='Ya hecha', state='lista')
        Task.objects.create(sesion=self.sesion, title='En curso', state='en_curso')
        Task.objects.create(sesion=self.sesion, title='Falta', state='pendiente')
        self.como(self.admin)
        estados = [t['state'] for t in self.client.get(self.url('tareas/'), self.q()).data['results']]
        self.assertEqual(estados, ['pendiente', 'en_curso', 'lista'])

    def test_el_filtro_mine_deja_solo_las_mias(self):
        Task.objects.create(sesion=self.sesion, title='De otro', assignee=self.colega)
        mia = Task.objects.create(sesion=self.sesion, title='Mía', assignee=self.admin)
        self.como(self.admin)
        r = self.client.get(self.url('tareas/'), {**self.q(), 'mias': '1'})
        self.assertEqual([t['id'] for t in r.data['results']], [mia.id])

    def test_el_filtro_de_estado_saca_las_listas(self):
        Task.objects.create(sesion=self.sesion, title='Ya hecha', state='lista')
        Task.objects.create(sesion=self.sesion, title='Falta', state='pendiente')
        self.como(self.admin)
        r = self.client.get(self.url('tareas/'), {**self.q(), 'estado': 'abiertas'})
        self.assertEqual(r.data['count'], 1)

    def test_no_se_asigna_un_agente_de_otra_empresa(self):
        otra_org = Organization.objects.create(owner=self.ajeno, name='Muebles Ltda')
        ajeno = Agent.objects.create(organization=otra_org, name='Ajeno')
        self.assertEqual(self.crear(agent=ajeno.id).status_code, 400)

    def test_una_tarea_de_otra_sesion_no_se_alcanza_por_id(self):
        otra = Sesion.objects.create(workspace=self.ws, name='Otra')
        ajena = Task.objects.create(sesion=otra, title='De otra Sesión')
        self.como(self.admin)
        r = self.client.patch(
            self.url(f'tareas/{ajena.pk}/'), {**self.q(), 'state': 'lista'}, format='json',
        )
        self.assertEqual(r.status_code, 404)

    def test_borrar_la_sesion_se_lleva_sus_tareas(self):
        self.crear()
        self.sesion.delete()
        self.assertEqual(Task.objects.count(), 0)

    def test_el_agente_la_ejecuta_y_el_resultado_queda_guardado(self):
        r = self.crear(description='Arma el resumen.', agent=self.agente.id)
        with mock.patch(
            'services.automation_runner._run_prompt', return_value='Hay 3 facturas vencidas.',
        ):
            corrida = self.client.post(
                self.url(f'tareas/{r.data["id"]}/ejecutar/'), self.q(), format='json',
            )
        self.assertEqual(corrida.status_code, 200)
        tarea = Task.objects.get(pk=r.data['id'])
        self.assertEqual(tarea.resultado, 'Hay 3 facturas vencidas.')
        self.assertEqual(tarea.state, 'lista')

    def test_si_el_modelo_falla_la_tarea_vuelve_a_pendiente(self):
        r = self.crear(agent=self.agente.id)
        with mock.patch(
            'services.automation_runner._run_prompt', side_effect=RuntimeError('modelo caido'),
        ):
            with self.assertLogs('apps.sesiones.tareas', level='ERROR'):
                corrida = self.client.post(
                    self.url(f'tareas/{r.data["id"]}/ejecutar/'), self.q(), format='json',
                )
        self.assertEqual(corrida.status_code, 502)
        self.assertEqual(Task.objects.get(pk=r.data['id']).state, 'pendiente')

    def test_sin_agente_no_se_ejecuta(self):
        r = self.crear()
        corrida = self.client.post(
            self.url(f'tareas/{r.data["id"]}/ejecutar/'), self.q(), format='json',
        )
        self.assertEqual(corrida.status_code, 400)


class ArchivosTests(BaseSesiones):
    """Los archivos de la Sesión son CompanyDocument: heredan todo lo que ya funciona."""

    def subir(self, nombre='contrato.txt', contenido=b'El plazo es de 45 dias.'):
        self.como(self.admin)
        archivo = SimpleUploadedFile(nombre, contenido, content_type='text/plain')
        # `_summarize_text` le pide el resumen a Anthropic: sin parchearlo, estas
        # pruebas salen a la red y dependen de una API key.
        with mock.patch('services.document_processing._summarize_text', return_value='Resumen.'):
            with mock.patch('services.indexing.indexar_documento_sin_ruido', return_value=1):
                return self.client.post(
                    f'{self.url("archivos/")}?workspace={self.org.slug}',
                    {'file': archivo, 'title': 'Contrato'}, format='multipart',
                )

    def test_el_archivo_queda_colgado_de_la_sesion(self):
        r = self.subir()
        self.assertEqual(r.status_code, 201)
        doc = CompanyDocument.objects.get(pk=r.data['id'])
        self.assertEqual(doc.sesion_id, self.sesion.id)
        self.assertEqual(doc.organization_id, self.org.id)

    def test_se_le_extrae_el_texto_al_subirlo(self):
        """Es lo que lo vuelve consultable por el agente, no un adjunto muerto."""
        r = self.subir(contenido=b'El plazo de entrega es de 45 dias corridos.')
        doc = CompanyDocument.objects.get(pk=r.data['id'])
        self.assertIn('45 dias', doc.extracted_text)

    def test_se_manda_a_indexar(self):
        self.como(self.admin)
        archivo = SimpleUploadedFile('c.txt', b'texto', content_type='text/plain')
        with mock.patch('services.document_processing._summarize_text', return_value='R.'):
            with mock.patch('services.indexing.indexar_documento_sin_ruido') as indexar:
                self.client.post(
                    f'{self.url("archivos/")}?workspace={self.org.slug}',
                    {'file': archivo}, format='multipart',
                )
        self.assertTrue(indexar.called)

    def test_la_lista_no_muestra_los_de_otra_sesion(self):
        otra = Sesion.objects.create(workspace=self.ws, name='Otra')
        CompanyDocument.objects.create(
            organization=self.org, sesion=otra, title='De otra', file='x.txt',
        )
        self.subir()
        self.como(self.admin)
        titulos = [a['title'] for a in self.client.get(self.url('archivos/'), self.q()).data['results']]
        self.assertEqual(titulos, ['Contrato'])

    def test_la_lista_no_muestra_los_documentos_de_la_empresa(self):
        """El repositorio de la empresa y los archivos de una Sesión son cosas distintas."""
        CompanyDocument.objects.create(
            organization=self.org, title='Reglamento interno', file='r.pdf',
        )
        self.subir()
        self.como(self.admin)
        titulos = [a['title'] for a in self.client.get(self.url('archivos/'), self.q()).data['results']]
        self.assertNotIn('Reglamento interno', titulos)

    def test_sin_archivo_no_se_crea_nada(self):
        self.como(self.admin)
        r = self.client.post(
            f'{self.url("archivos/")}?workspace={self.org.slug}', {}, format='multipart',
        )
        self.assertEqual(r.status_code, 400)

    def test_se_borra(self):
        r = self.subir()
        self.como(self.admin)
        borrado = self.client.delete(self.url(f'archivos/{r.data["id"]}/'), self.q())
        self.assertEqual(borrado.status_code, 204)
        self.assertEqual(CompanyDocument.objects.filter(sesion=self.sesion).count(), 0)

    def test_borrar_la_sesion_se_lleva_sus_archivos(self):
        self.subir()
        self.sesion.delete()
        self.assertEqual(CompanyDocument.objects.filter(title='Contrato').count(), 0)


class FeedTests(BaseSesiones):
    """El feed: una tarea y una conversación son el mismo tipo de item.

    Separarlas en dos listas obliga a mirar en dos lados para saber qué pasó en la
    Sesión, que es justo lo que la Sesión viene a resolver.
    """

    def setUp(self):
        super().setUp()
        from apps.agents.models import Conversation, Message

        self.tarea = Task.objects.create(
            sesion=self.sesion, title='Revisar facturas', created_by=self.admin,
            description='El detalle', resultado='Hay 3 vencidas.', agent=self.agente,
        )
        self.conv = Conversation.objects.create(
            sesion=self.sesion, user=self.admin, agent=self.agente, title='Sobre el contrato',
        )
        Message.objects.create(conversation=self.conv, role='user', content='¿Qué dice el plazo?')
        Message.objects.create(
            conversation=self.conv, role='assistant', content='45 días.', agent=self.agente,
        )

    def feed(self, quien=None):
        self.como(quien or self.admin)
        return self.client.get(self.url('feed/'), self.q()).data

    def test_trae_tareas_y_conversaciones_juntas(self):
        datos = self.feed()
        tipos = {i['tipo'] for g in datos['grupos'] for i in g['items']}
        self.assertEqual(tipos, {'tarea', 'conversacion'})
        self.assertEqual(datos['count'], 2)

    def test_una_tarea_con_resultado_cuenta_como_una_respuesta(self):
        """Es lo que la vuelve equivalente a una conversación en la lista."""
        item = [i for g in self.feed()['grupos'] for i in g['items'] if i['tipo'] == 'tarea'][0]
        self.assertEqual(item['respuestas'], 1)
        self.assertEqual(item['ultima_de'], self.agente.name)

    def test_una_conversacion_cuenta_las_respuestas_del_agente(self):
        item = [
            i for g in self.feed()['grupos'] for i in g['items'] if i['tipo'] == 'conversacion'
        ][0]
        self.assertEqual(item['respuestas'], 1)
        self.assertEqual(item['ultima_de'], self.agente.name)

    def test_lo_de_hoy_va_en_el_grupo_de_hoy(self):
        self.assertEqual(self.feed()['grupos'][0]['titulo'], 'Hoy')

    def test_no_trae_lo_de_otra_sesion(self):
        from apps.agents.models import Conversation

        otra = Sesion.objects.create(workspace=self.ws, name='Otra')
        Task.objects.create(sesion=otra, title='De otra')
        Conversation.objects.create(
            sesion=otra, user=self.admin, agent=self.agente, title='De otra',
        )

        titulos = [i['titulo'] for g in self.feed()['grupos'] for i in g['items']]
        self.assertNotIn('De otra', titulos)

    def test_no_trae_las_conversaciones_personales(self):
        """Una conversación sin Sesión es del historial privado de quien la escribió."""
        from apps.agents.models import Conversation

        Conversation.objects.create(
            user=self.admin, agent=self.agente, title='Mi hilo privado',
        )
        titulos = [i['titulo'] for g in self.feed()['grupos'] for i in g['items']]
        self.assertNotIn('Mi hilo privado', titulos)

    def test_marca_lo_mio(self):
        """El feed es del equipo: hay que poder distinguir lo propio de un vistazo."""
        item = [i for g in self.feed()['grupos'] for i in g['items'] if i['tipo'] == 'conversacion'][0]
        self.assertTrue(item['es_mio'])

        del_colega = [
            i for g in self.feed(self.colega)['grupos'] for i in g['items']
            if i['tipo'] == 'conversacion'
        ][0]
        self.assertFalse(del_colega['es_mio'])

    def test_quien_no_ve_la_sesion_no_ve_su_feed(self):
        self.sesion.visibility = VISIBILIDAD_RESTRINGIDA
        self.sesion.save(update_fields=['visibility'])
        self.como(self.colega)
        self.assertEqual(self.client.get(self.url('feed/'), self.q()).status_code, 404)

    def test_el_saludo_viene_del_backend(self):
        """Se elige acá y no en el navegador para que no cambie en cada dibujado."""
        self.assertTrue(self.feed()['saludo'])


class ConversacionEnLaSesionTests(BaseSesiones):
    """El chat puede abrir el hilo DENTRO de una Sesión."""

    def test_el_hilo_queda_colgado_de_la_sesion(self):
        from apps.agents.views import _sesion_del_pedido

        pedido = mock.Mock(user=self.admin, data={
            'sesion': self.sesion.slug, 'workspace': self.org.slug,
        })
        self.assertEqual(_sesion_del_pedido(pedido), self.sesion)

    def test_una_sesion_que_no_alcanzo_deja_el_hilo_personal(self):
        """El resultado seguro: personal, no un error ni una Sesión ajena."""
        from apps.agents.views import _sesion_del_pedido

        self.sesion.visibility = VISIBILIDAD_RESTRINGIDA
        self.sesion.save(update_fields=['visibility'])
        pedido = mock.Mock(user=self.colega, data={
            'sesion': self.sesion.slug, 'workspace': self.org.slug,
        })
        self.assertIsNone(_sesion_del_pedido(pedido))

    def test_sin_sesion_en_el_pedido_no_pasa_nada(self):
        from apps.agents.views import _sesion_del_pedido

        pedido = mock.Mock(user=self.admin, data={'workspace': self.org.slug})
        self.assertIsNone(_sesion_del_pedido(pedido))

    def test_borrar_la_sesion_no_borra_la_conversacion(self):
        """SET_NULL: el hilo vuelve a ser personal en vez de desaparecer con la Sesión."""
        from apps.agents.models import Conversation

        conv = Conversation.objects.create(
            sesion=self.sesion, user=self.admin, agent=self.agente, title='Hilo',
        )
        self.sesion.delete()
        conv.refresh_from_db()
        self.assertIsNone(conv.sesion_id)


class LaSesionPrestaContextoTests(BaseSesiones):
    """Lo que hace que la Sesión sirva para algo y no sea una carpeta bonita.

    Tres cosas: sus instrucciones llegan a todos sus agentes, sus archivos AMPLÍAN lo
    que el agente alcanza, y su agente por defecto toma los hilos nuevos.
    """

    def setUp(self):
        super().setUp()
        from apps.workspaces.models import Workspace

        self.sesion.instrucciones_para_agentes = 'Acá hablamos del cliente Rever.'
        self.sesion.save(update_fields=['instrucciones_para_agentes'])

        # Un agente ENCERRADO en un Espacio: es el caso donde ampliar importa.
        self.espacio = Workspace.objects.create(organization=self.org, name='Ventas')
        self.espacio.agents.add(self.agente)
        self.doc_del_espacio = CompanyDocument.objects.create(
            organization=self.org, title='Catálogo', file='c.pdf', extracted_text='precios',
        )
        self.espacio.documents.add(self.doc_del_espacio)

        self.archivo_de_la_sesion = CompanyDocument.objects.create(
            organization=self.org, sesion=self.sesion, title='Contrato Rever',
            file='r.pdf', extracted_text='El plazo es de 45 dias.',
        )

    def contexto(self, sesion=None):
        from apps.agents.views import _build_onboarding_context

        return _build_onboarding_context(
            self.admin, self.agente, consulta='¿cuál es el plazo?', sesion=sesion,
        )

    def test_las_instrucciones_de_la_sesion_llegan_al_agente(self):
        prompt = self.contexto(self.sesion)['system_prompt']
        self.assertIn('cliente Rever', prompt)
        self.assertIn(self.sesion.name, prompt)

    def test_sin_sesion_no_llegan(self):
        self.assertNotIn('cliente Rever', self.contexto(None)['system_prompt'])

    def test_los_archivos_de_la_sesion_AMPLIAN_el_alcance_del_agente(self):
        """El agente está encerrado en su Espacio; la Sesión le presta lo suyo.

        Se comprueba sobre el PROMPT y no sobre `allowed_doc_ids`, que solo viaja en el
        modo con sistemas conectados: lo que importa es qué llega a ver el agente.
        """
        sin = self.contexto(None)['system_prompt']
        self.assertIn('Catálogo', sin)
        self.assertNotIn('Contrato Rever', sin)

        con = self.contexto(self.sesion)['system_prompt']
        self.assertIn('Contrato Rever', con)

    def test_la_sesion_nunca_RECORTA_lo_que_el_espacio_dio(self):
        """Al revés sería un error: la Sesión presta, el Espacio restringe."""
        con = self.contexto(self.sesion)['system_prompt']
        self.assertIn('Catálogo', con)

    def test_un_agente_sin_espacio_sigue_alcanzando_todo(self):
        """`None` es "alcanza todo": sumarle una lista lo habría restringido."""
        from apps.agents.views import _build_onboarding_context

        suelto = Agent.objects.create(organization=self.org, name='Suelto')
        ajeno_a_todo = CompanyDocument.objects.create(
            organization=self.org, title='Reglamento', file='x.pdf', extracted_text='reglas',
        )
        prompt = _build_onboarding_context(self.admin, suelto, sesion=self.sesion)['system_prompt']
        # Ve el de la Sesión, el del Espacio ajeno y uno que no está en ninguna parte.
        self.assertIn('Contrato Rever', prompt)
        self.assertIn('Reglamento', prompt)
        self.assertIn('Catálogo', prompt)

    def test_las_habilidades_de_la_sesion_se_suman(self):
        from apps.agents.models import Skill

        habilidad = Skill.objects.create(
            organization=self.org, name='Tono con Rever', instructions='Trate de usted.',
        )
        self.sesion.habilidades_por_defecto.add(habilidad)
        prompt = self.contexto(self.sesion)['system_prompt']
        self.assertIn('Trate de usted', prompt)

    def test_el_agente_por_defecto_de_la_sesion_toma_el_hilo(self):
        from apps.agents.views import _agente_inicial

        propio = Agent.objects.create(organization=self.org, name='De la Sesión')
        self.sesion.agente_por_defecto = propio
        self.sesion.save(update_fields=['agente_por_defecto'])

        pedido = mock.Mock(user=self.admin, data={})
        elegido = _agente_inicial(pedido, 'hola', None, self.agente, self.sesion)
        self.assertEqual(elegido, propio)

    def test_un_agente_apagado_no_toma_el_hilo_aunque_sea_el_por_defecto(self):
        from apps.agents.views import _agente_inicial

        apagado = Agent.objects.create(organization=self.org, name='Apagado', is_active=False)
        self.sesion.agente_por_defecto = apagado
        self.sesion.save(update_fields=['agente_por_defecto'])

        pedido = mock.Mock(user=self.admin, data={})
        elegido = _agente_inicial(pedido, 'hola', None, self.agente, self.sesion)
        self.assertEqual(elegido, self.agente)

    def test_no_se_pone_como_defecto_un_agente_de_otra_empresa(self):
        otra_org = Organization.objects.create(owner=self.ajeno, name='Muebles Ltda')
        ajeno = Agent.objects.create(organization=otra_org, name='Ajeno')
        self.como(self.admin)
        r = self.client.patch(
            self.url(), {**self.q(), 'agente_por_defecto': ajeno.id}, format='json',
        )
        self.assertEqual(r.status_code, 400)

    def test_las_instrucciones_se_guardan_desde_la_api(self):
        self.como(self.admin)
        r = self.client.patch(
            self.url(),
            {**self.q(), 'instrucciones_para_agentes': 'Nunca prometas fechas.'},
            format='json',
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['instrucciones_para_agentes'], 'Nunca prometas fechas.')

    def test_un_miembro_simple_no_toca_las_instrucciones(self):
        self.como(self.colega)
        r = self.client.patch(
            self.url(), {**self.q(), 'instrucciones_para_agentes': 'Mías'}, format='json',
        )
        self.assertEqual(r.status_code, 403)


class CompartirUnaConversacionTests(BaseSesiones):
    """Compartir un hilo = moverlo a una Sesión.

    No hay un enlace público ni un permiso nuevo: se apoya en lo que la Sesión ya
    significa — lo que está en ella lo ve su equipo.
    """

    def setUp(self):
        super().setUp()
        from apps.agents.models import Conversation

        self.conv = Conversation.objects.create(
            user=self.admin, agent=self.agente, title='Mi hilo privado',
        )
        self.url_conv = f'/api/v1/agents/conversations/{self.conv.pk}/'

    def test_mover_el_hilo_a_una_sesion_lo_comparte(self):
        self.como(self.admin)
        r = self.client.patch(
            self.url_conv, {'workspace': self.org.slug, 'sesion': self.sesion.slug}, format='json',
        )
        self.assertEqual(r.status_code, 200)
        self.conv.refresh_from_db()
        self.assertEqual(self.conv.sesion_id, self.sesion.id)

    def test_mandar_nulo_lo_devuelve_al_historial_privado(self):
        self.conv.sesion = self.sesion
        self.conv.save(update_fields=['sesion'])

        self.como(self.admin)
        self.client.patch(self.url_conv, {'workspace': self.org.slug, 'sesion': None}, format='json')
        self.conv.refresh_from_db()
        self.assertIsNone(self.conv.sesion_id)

    def test_no_se_comparte_en_una_sesion_que_no_se_alcanza(self):
        """Meter el hilo en una Sesión restringida ajena sería ponerlo donde no va."""
        self.sesion.visibility = VISIBILIDAD_RESTRINGIDA
        self.sesion.save(update_fields=['visibility'])

        from apps.agents.models import Conversation

        del_colega = Conversation.objects.create(
            user=self.colega, agent=self.agente, title='Hilo del colega',
        )
        self.como(self.colega)
        r = self.client.patch(
            f'/api/v1/agents/conversations/{del_colega.pk}/',
            {'workspace': self.org.slug, 'sesion': self.sesion.slug}, format='json',
        )
        self.assertEqual(r.status_code, 400)
        del_colega.refresh_from_db()
        self.assertIsNone(del_colega.sesion_id)

    def test_solo_el_dueño_del_hilo_lo_comparte(self):
        """Compartir el trabajo de otro no es una decisión de quien lo lee."""
        self.como(self.colega)
        r = self.client.patch(
            self.url_conv, {'workspace': self.org.slug, 'sesion': self.sesion.slug}, format='json',
        )
        self.assertEqual(r.status_code, 404)

    def test_se_renombra_el_hilo(self):
        self.como(self.admin)
        r = self.client.patch(self.url_conv, {'title': 'Otro nombre'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.conv.refresh_from_db()
        self.assertEqual(self.conv.title, 'Otro nombre')

    def test_un_nombre_vacio_no_pasa(self):
        self.como(self.admin)
        r = self.client.patch(self.url_conv, {'title': '   '}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_la_lista_dice_en_que_sesion_esta(self):
        """La barra lateral lo usa para distinguir lo compartido de lo privado."""
        self.conv.sesion = self.sesion
        self.conv.save(update_fields=['sesion'])

        self.como(self.admin)
        r = self.client.get('/api/v1/agents/conversations/')
        fila = next(c for c in r.data if c['id'] == self.conv.pk)
        self.assertEqual(fila['sesion_nombre'], self.sesion.name)
        self.assertEqual(fila['sesion_slug'], self.sesion.slug)


class TareasCruzandoSesionesTests(BaseSesiones):
    """`GET /api/v1/tareas/` — todo lo pendiente, sin abrir Sesión por Sesión.

    Las tareas existían solo adentro de su Sesión, cuatro niveles adentro de la barra
    lateral, así que "¿qué tengo pendiente?" no se podía contestar sin recorrer todas las
    Sesiones y acordarse de todas. Lo que estas pruebas cuidan, en orden: que junte de
    varias Sesiones, que NO junte de las que la persona no ve, y que los contadores de las
    pestañas no dependan del filtro que está puesto.
    """

    URL = '/api/v1/tareas/'

    def setUp(self):
        super().setUp()
        self.otra = Sesion.objects.create(
            workspace=self.ws, name='Cliente Atika', created_by=self.admin,
        )
        # Una restringida donde el colega NO está agregado.
        self.privada = Sesion.objects.create(
            workspace=self.ws, name='Sueldos', created_by=self.admin,
            visibility=VISIBILIDAD_RESTRINGIDA,
        )

        self.mia = Task.objects.create(
            sesion=self.sesion, title='Llamar al cliente', assignee=self.colega,
            created_by=self.admin,
        )
        self.de_otro = Task.objects.create(
            sesion=self.otra, title='Revisar la propuesta', assignee=self.admin,
            created_by=self.admin,
        )
        self.del_agente = Task.objects.create(
            sesion=self.otra, title='Resumir los pagos', agent=self.agente,
            created_by=self.admin,
        )
        self.hecha = Task.objects.create(
            sesion=self.sesion, title='Enviar el contrato', state=TAREA_LISTA,
            assignee=self.colega, created_by=self.admin,
        )
        self.secreta = Task.objects.create(
            sesion=self.privada, title='Ajustar sueldos', created_by=self.admin,
        )

    def pedir(self, quien, **params):
        self.como(quien)
        return self.client.get(self.URL, {'workspace': self.org.slug, **params})

    def titulos(self, r):
        return {t['title'] for t in r.data['results']}

    def test_junta_las_tareas_de_varias_sesiones(self):
        r = self.pedir(self.admin)
        self.assertEqual(r.status_code, 200)
        self.assertIn('Llamar al cliente', self.titulos(r))
        self.assertIn('Revisar la propuesta', self.titulos(r))

    def test_cada_tarea_dice_de_que_sesion_es(self):
        """Sin eso, una lista que cruza Sesiones es una lista sin contexto."""
        r = self.pedir(self.admin)
        de = {t['title']: t['sesion']['name'] for t in r.data['results']}
        self.assertEqual(de['Llamar al cliente'], 'Cliente Rever')
        self.assertEqual(de['Revisar la propuesta'], 'Cliente Atika')

    def test_no_trae_las_de_una_sesion_que_no_se_ve(self):
        """Lo que esta vista existe para no romper: cruzar Sesiones no puede ser la
        forma de leer las tareas de una Sesión restringida ajena."""
        r = self.pedir(self.colega)
        self.assertNotIn('Ajustar sueldos', self.titulos(r))
        # Y el administrador sí, porque ve todo el Workspace.
        self.assertIn('Ajustar sueldos', self.titulos(self.pedir(self.admin)))

    def test_agregado_a_la_restringida_si_las_ve(self):
        SesionMiembro.objects.create(sesion=self.privada, user=self.colega)
        self.assertIn('Ajustar sueldos', self.titulos(self.pedir(self.colega)))

    def test_mias_deja_solo_las_asignadas_a_quien_pregunta(self):
        r = self.pedir(self.colega, mias=1, estado='abiertas')
        self.assertEqual(self.titulos(r), {'Llamar al cliente'})

    def test_de_agentes_deja_solo_las_que_ejecuta_un_agente(self):
        r = self.pedir(self.admin, agente=1, estado='abiertas')
        self.assertEqual(self.titulos(r), {'Resumir los pagos'})

    def test_abiertas_no_trae_las_hechas(self):
        r = self.pedir(self.admin, estado='abiertas')
        self.assertNotIn('Enviar el contrato', self.titulos(r))

    def test_los_contadores_no_dependen_del_filtro_puesto(self):
        """Son los números de las pestañas: si contaran lo ya filtrado, la pestaña
        "Del equipo" mostraría 0 justo estando en "Mías" y nadie iría a mirarla."""
        r = self.pedir(self.colega, mias=1, estado='abiertas')
        self.assertEqual(len(r.data['results']), 1)              # lo filtrado
        totales = r.data['totales']
        self.assertEqual(totales['mias'], 1)
        self.assertEqual(totales['pendientes'], 3)               # las 3 abiertas que ve
        self.assertEqual(totales['de_agentes'], 1)
        self.assertEqual(totales['todas'], 4)                    # sin la de la privada

    def test_las_pendientes_van_antes_que_las_hechas(self):
        """La lista se lee para saber qué falta."""
        r = self.pedir(self.admin)
        estados = [t['state'] for t in r.data['results']]
        self.assertEqual(estados[-1], TAREA_LISTA)

    def test_sin_workspace_no_adivina(self):
        self.como(self.admin)
        self.assertEqual(self.client.get(self.URL).status_code, 400)

    def test_alguien_de_afuera_no_llega(self):
        self.assertEqual(self.pedir(self.ajeno).status_code, 404)


class ElAgenteActuaSoloTests(BaseSesiones):
    """El principio de los Pods: "todo lo que un humano puede hacer, un agente también".

    Estaba a medias. El agente ejecutaba una tarea, pero SOLO si alguien apretaba ▷, y el
    resultado se iba por correo a una persona: el equipo no se enteraba. Lo que se prueba
    acá es lo que faltaba — que un Disparador publique en la Sesión sin que nadie lo pida,
    y que el agente pueda ANOTAR una tarea él mismo.
    """

    def crear_disparador(self, **extra):
        from apps.agents.models import Automation

        datos = {
            'user': self.admin, 'organization': self.org, 'name': 'Facturas sin pagar',
            'prompt': 'Revisa si hay facturas vencidas.', 'sesion': self.sesion,
            'agent': self.agente, 'notify_email': '',
        }
        datos.update(extra)
        return Automation.objects.create(**datos)

    # ── El Disparador publica en la Sesión ────────────────────────────────────

    def test_publica_una_conversacion_que_ve_el_equipo(self):
        from apps.agents.models import Conversation
        from services.automation_runner import entregar

        d = self.crear_disparador()
        self.assertEqual(entregar(d, 'Hay 3 facturas vencidas.'), '')

        conv = Conversation.objects.get(sesion=self.sesion)
        self.assertTrue(conv.autonoma)
        self.assertEqual(conv.agent, self.agente)
        # Los DOS turnos: sin el encargo, quien lo lee tres días después no sabe qué se
        # había pedido.
        textos = [m.content for m in conv.messages.order_by('created_at')]
        self.assertEqual(textos, ['Revisa si hay facturas vencidas.', 'Hay 3 facturas vencidas.'])

    def test_aparece_en_el_feed_marcada_como_autonoma(self):
        from services.automation_runner import entregar

        entregar(self.crear_disparador(), 'Hay 3 facturas vencidas.')
        self.como(self.colega)
        r = self.client.get(self.url('feed/'), self.q())
        item = next(
            i for g in r.data['grupos'] for i in g['items'] if i['tipo'] == 'conversacion'
        )
        self.assertTrue(item['autonoma'])
        # Y no es "mía" de nadie: no la escribió una persona.
        self.assertFalse(item['es_mio'])

    def test_ademas_puede_dejar_la_tarea_anotada(self):
        from services.automation_runner import entregar

        entregar(self.crear_disparador(crear_tarea=True), 'Hay 3 facturas vencidas.')
        tarea = Task.objects.get(sesion=self.sesion, title='Facturas sin pagar')
        self.assertEqual(tarea.agent, self.agente)
        self.assertIn('3 facturas', tarea.resultado)

    def test_sin_crear_tarea_no_anota_nada(self):
        from services.automation_runner import entregar

        entregar(self.crear_disparador(), 'Hay 3 facturas vencidas.')
        self.assertFalse(Task.objects.filter(sesion=self.sesion).exists())

    def test_los_dos_destinos_conviven(self):
        from apps.agents.models import Conversation
        from django.core import mail
        from services.automation_runner import entregar

        entregar(self.crear_disparador(notify_email='jefe@afable.test'), 'Todo al día.')
        self.assertEqual(Conversation.objects.filter(sesion=self.sesion).count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_que_falle_el_correo_no_pierde_la_publicacion(self):
        """Lo que queda guardado es la publicación: el correo solo avisa afuera."""
        from apps.agents.models import Conversation
        from services.automation_runner import entregar

        d = self.crear_disparador(notify_email='jefe@afable.test')
        with mock.patch('services.automation_runner._send_result_email', side_effect=RuntimeError('SMTP caído')):
            error = entregar(d, 'Todo al día.')
        self.assertIn('correo', error)
        self.assertEqual(Conversation.objects.filter(sesion=self.sesion).count(), 1)

    def test_sin_sesion_sigue_yendo_solo_por_correo(self):
        """Lo que ya funcionaba no puede cambiar: la mayoría de los encargos no tienen Sesión."""
        from apps.agents.models import Conversation
        from django.core import mail
        from services.automation_runner import entregar

        entregar(self.crear_disparador(sesion=None, notify_email='jefe@afable.test'), 'Listo.')
        self.assertEqual(len(mail.outbox), 1)
        self.assertFalse(Conversation.objects.filter(sesion=self.sesion).exists())

    # ── El agente anota tareas él mismo ───────────────────────────────────────

    def test_el_agente_anota_una_tarea(self):
        from services.agent_tools import execute_tool

        r = execute_tool(
            'crear_tarea', {'titulo': 'Pagar la factura 4021', 'detalle': 'Vence el viernes'},
            self.org, [], agente=self.agente, sesion=self.sesion,
        )
        self.assertTrue(r['ok'])
        tarea = Task.objects.get(sesion=self.sesion, title='Pagar la factura 4021')
        self.assertEqual(tarea.description, 'Vence el viernes')
        # Sin `para_mi` la señala pero no se compromete: nadie la ejecuta por él.
        self.assertIsNone(tarea.agent)
        self.assertIsNone(tarea.created_by)

    def test_con_para_mi_queda_asignada_al_agente(self):
        from services.agent_tools import execute_tool

        execute_tool(
            'crear_tarea', {'titulo': 'Resumir los pagos', 'para_mi': True},
            self.org, [], agente=self.agente, sesion=self.sesion,
        )
        self.assertEqual(Task.objects.get(title='Resumir los pagos').agent, self.agente)

    def test_fuera_de_una_sesion_no_hay_donde_anotar(self):
        from services.agent_tools import execute_tool

        r = execute_tool(
            'crear_tarea', {'titulo': 'Algo'}, self.org, [], agente=self.agente, sesion=None,
        )
        self.assertIn('error', r)
        self.assertFalse(Task.objects.exists())

    def test_sin_titulo_no_crea_una_tarea_en_blanco(self):
        from services.agent_tools import execute_tool

        r = execute_tool(
            'crear_tarea', {'detalle': 'solo detalle'}, self.org, [],
            agente=self.agente, sesion=self.sesion,
        )
        self.assertIn('error', r)
        self.assertFalse(Task.objects.exists())

    def test_la_herramienta_no_se_ofrece_fuera_de_una_sesion(self):
        """Prometerle una herramienta que no tiene lo hace gastar el turno invocándola."""
        from services.agent_tools import tools_for_anthropic

        sin = {t['name'] for t in tools_for_anthropic(self.org, None, None)}
        con = {t['name'] for t in tools_for_anthropic(self.org, None, self.sesion)}
        self.assertNotIn('crear_tarea', sin)
        self.assertIn('crear_tarea', con)

    def test_el_prompt_le_cuenta_de_la_sesion_solo_si_hay_sesion(self):
        from apps.agents.views import _build_onboarding_context

        con = _build_onboarding_context(self.admin, sesion=self.sesion)['system_prompt']
        sin = _build_onboarding_context(self.admin)['system_prompt']
        self.assertIn('crear_tarea', con)
        self.assertIn(self.sesion.name, con)
        self.assertNotIn('crear_tarea', sin)
