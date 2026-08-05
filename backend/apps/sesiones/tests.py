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
    Sesion, SesionMiembro, Task,
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
        self.ws = Workspace.objects.create(name='Cocinas SpA', organization=self.org)
        self.ws.add_member(self.admin, ROLE_ADMIN)
        self.ws.add_member(self.colega, ROLE_MEMBER)

        self.agente = Agent.objects.create(organization=self.org, name='Cobranzas')

        self.sesion = Sesion.objects.create(
            workspace=self.ws, name='Cliente Rever', created_by=self.admin,
        )

    def como(self, quien):
        self.client.force_authenticate(user=quien)

    def url(self, sufijo='', sesion=None):
        return f'{URL}{(sesion or self.sesion).slug}/{sufijo}'

    def q(self):
        return {'workspace': self.ws.slug}


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
        otro_ws = Workspace.objects.create(name='Muebles Ltda', organization=otra_org)
        otro_ws.add_member(self.ajeno, ROLE_ADMIN)
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
            URL, {'workspace': self.ws.slug, 'name': 'Cierre de mes'}, format='json',
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['mi_rol'], ROL_EDITOR)

    def test_sin_nombre_no_se_crea(self):
        self.como(self.admin)
        r = self.client.post(URL, {'workspace': self.ws.slug, 'name': '  '}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_el_slug_se_arma_solo_y_no_choca(self):
        self.como(self.admin)
        r = self.client.post(
            URL, {'workspace': self.ws.slug, 'name': 'Cliente Rever'}, format='json',
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
                    f'{self.url("archivos/")}?workspace={self.ws.slug}',
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
                    f'{self.url("archivos/")}?workspace={self.ws.slug}',
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
            f'{self.url("archivos/")}?workspace={self.ws.slug}', {}, format='multipart',
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
            'sesion': self.sesion.slug, 'workspace': self.ws.slug,
        })
        self.assertEqual(_sesion_del_pedido(pedido), self.sesion)

    def test_una_sesion_que_no_alcanzo_deja_el_hilo_personal(self):
        """El resultado seguro: personal, no un error ni una Sesión ajena."""
        from apps.agents.views import _sesion_del_pedido

        self.sesion.visibility = VISIBILIDAD_RESTRINGIDA
        self.sesion.save(update_fields=['visibility'])
        pedido = mock.Mock(user=self.colega, data={
            'sesion': self.sesion.slug, 'workspace': self.ws.slug,
        })
        self.assertIsNone(_sesion_del_pedido(pedido))

    def test_sin_sesion_en_el_pedido_no_pasa_nada(self):
        from apps.agents.views import _sesion_del_pedido

        pedido = mock.Mock(user=self.admin, data={'workspace': self.ws.slug})
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
