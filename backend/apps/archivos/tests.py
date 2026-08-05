"""Pruebas de los archivos: carpetas, versiones y la escritura por el agente.

Lo que cubren, en orden de importancia: que **nada se pierda** (borrar una carpeta no se
lleva los documentos, restaurar no borra el historial, una edición puntual no toca el
resto), que un binario no se pueda editar aunque se insista, y que cada cambio quede
firmado por quien lo hizo.

Ninguna habla con un modelo: las herramientas del agente se ejecutan directo.
"""

import unittest.mock as mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.agents.models import Agent
from apps.archivos.models import Carpeta, Version
from apps.organizations.models import CompanyDocument, Organization
from apps.workspaces.models import ROLE_ADMIN, Workspace

User = get_user_model()

URL = '/api/v1/archivos/'


class BaseArchivos(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='duena@afable.test', email='duena@afable.test', password='afable123',
        )
        self.ajeno = User.objects.create_user(
            username='ajeno@afable.test', email='ajeno@afable.test', password='afable123',
        )
        self.org = Organization.objects.create(owner=self.user, name='Cocinas SpA')
        self.ws = Workspace.objects.create(name='Cocinas SpA', organization=self.org)
        self.ws.add_member(self.user, ROLE_ADMIN)

        self.agente = Agent.objects.create(organization=self.org, name='Redactor')

        self.texto = CompanyDocument.objects.create(
            organization=self.org, title='Procedimiento', file='p.md',
            content_type='text/markdown', editable=True,
            extracted_text='Paso 1: revisar.\nPaso 2: aprobar.',
        )
        self.pdf = CompanyDocument.objects.create(
            organization=self.org, title='Contrato', file='c.pdf',
            content_type='application/pdf', editable=False,
            extracted_text='El plazo es de 45 dias.',
        )

    def como(self, quien=None):
        self.client.force_authenticate(user=quien or self.user)

    def q(self):
        return {'workspace': self.ws.slug}


class CarpetasTests(BaseArchivos):

    def test_se_crea_una_carpeta_en_la_raiz(self):
        self.como()
        r = self.client.post(f'{URL}carpetas/', {**self.q(), 'name': 'Contabilidad'}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertIsNone(Carpeta.objects.get(pk=r.data['id']).parent_id)

    def test_no_se_repite_el_nombre_en_el_mismo_lugar(self):
        Carpeta.objects.create(organization=self.org, name='Contabilidad')
        self.como()
        r = self.client.post(f'{URL}carpetas/', {**self.q(), 'name': 'Contabilidad'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_el_mismo_nombre_en_otra_carpeta_si_se_puede(self):
        madre = Carpeta.objects.create(organization=self.org, name='2026')
        Carpeta.objects.create(organization=self.org, name='Facturas')
        self.como()
        r = self.client.post(
            f'{URL}carpetas/', {**self.q(), 'name': 'Facturas', 'parent': madre.pk}, format='json',
        )
        self.assertEqual(r.status_code, 201)

    def test_la_ruta_arma_el_rastro_de_migas(self):
        a = Carpeta.objects.create(organization=self.org, name='Contabilidad')
        b = Carpeta.objects.create(organization=self.org, name='2026', parent=a)
        c = Carpeta.objects.create(organization=self.org, name='Facturas', parent=b)
        self.assertEqual(c.ruta(), 'Contabilidad / 2026 / Facturas')
        self.assertEqual([x.name for x in c.ancestros()], ['Contabilidad', '2026'])

    def test_no_se_mueve_una_carpeta_dentro_de_si_misma(self):
        """Dejaría un ciclo, y con él una rama que desaparece del árbol."""
        madre = Carpeta.objects.create(organization=self.org, name='Madre')
        hija = Carpeta.objects.create(organization=self.org, name='Hija', parent=madre)

        self.como()
        r = self.client.patch(
            f'{URL}carpetas/{madre.pk}/', {**self.q(), 'parent': hija.pk}, format='json',
        )
        self.assertEqual(r.status_code, 400)
        madre.refresh_from_db()
        self.assertIsNone(madre.parent_id)

    def test_tampoco_dentro_de_si_misma_directamente(self):
        c = Carpeta.objects.create(organization=self.org, name='Sola')
        self.como()
        r = self.client.patch(f'{URL}carpetas/{c.pk}/', {**self.q(), 'parent': c.pk}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_borrar_la_carpeta_NO_borra_sus_documentos(self):
        """Borrar una carpeta no puede llevarse el trabajo que hay dentro."""
        carpeta = Carpeta.objects.create(organization=self.org, name='Vieja')
        self.texto.carpeta = carpeta
        self.texto.save(update_fields=['carpeta'])

        self.como()
        self.assertEqual(self.client.delete(f'{URL}carpetas/{carpeta.pk}/', self.q()).status_code, 204)
        self.texto.refresh_from_db()
        self.assertIsNone(self.texto.carpeta_id)   # subió a la raíz
        self.assertTrue(CompanyDocument.objects.filter(pk=self.texto.pk).exists())

    def test_una_carpeta_de_otra_empresa_no_se_alcanza(self):
        otra = Organization.objects.create(owner=self.ajeno, name='Muebles Ltda')
        ajena = Carpeta.objects.create(organization=otra, name='Ajena')
        self.como()
        r = self.client.patch(f'{URL}carpetas/{ajena.pk}/', {**self.q(), 'name': 'Robada'}, format='json')
        self.assertEqual(r.status_code, 404)


class ExploradorTests(BaseArchivos):

    def test_la_raiz_muestra_lo_que_no_esta_en_ninguna_carpeta(self):
        carpeta = Carpeta.objects.create(organization=self.org, name='Contabilidad')
        self.pdf.carpeta = carpeta
        self.pdf.save(update_fields=['carpeta'])

        self.como()
        datos = self.client.get(URL, self.q()).data
        titulos = [d['title'] for d in datos['documentos']]
        self.assertIn('Procedimiento', titulos)
        self.assertNotIn('Contrato', titulos)
        self.assertEqual([c['name'] for c in datos['subcarpetas']], ['Contabilidad'])

    def test_buscar_mira_toda_la_empresa_no_solo_la_carpeta_abierta(self):
        """Quien busca un archivo no sabe dónde está: si lo supiera, navegaría."""
        carpeta = Carpeta.objects.create(organization=self.org, name='Contabilidad')
        self.pdf.carpeta = carpeta
        self.pdf.save(update_fields=['carpeta'])

        self.como()
        datos = self.client.get(URL, {**self.q(), 'q': 'Contrato'}).data
        self.assertEqual([d['title'] for d in datos['documentos']], ['Contrato'])
        self.assertTrue(datos['buscando'])

    def test_se_mueve_un_documento_de_carpeta(self):
        carpeta = Carpeta.objects.create(organization=self.org, name='Contabilidad')
        self.como()
        r = self.client.patch(
            f'{URL}documentos/{self.texto.pk}/', {**self.q(), 'carpeta': carpeta.pk}, format='json',
        )
        self.assertEqual(r.status_code, 200)
        self.texto.refresh_from_db()
        self.assertEqual(self.texto.carpeta_id, carpeta.pk)

    def test_no_se_ven_los_documentos_de_otra_empresa(self):
        otra = Organization.objects.create(owner=self.ajeno, name='Muebles Ltda')
        CompanyDocument.objects.create(organization=otra, title='Ajeno', file='a.txt')
        self.como()
        titulos = [d['title'] for d in self.client.get(URL, self.q()).data['documentos']]
        self.assertNotIn('Ajeno', titulos)


class VersionesTests(BaseArchivos):

    def setUp(self):
        super().setUp()
        # El indexado semántico no es lo que se prueba acá.
        self.parche = mock.patch('services.indexing.indexar_documento_sin_ruido', return_value=1)
        self.parche.start()
        self.addCleanup(self.parche.stop)

    def test_guardar_crea_una_version_firmada(self):
        self.como()
        r = self.client.put(
            f'{URL}documentos/{self.texto.pk}/contenido/',
            {**self.q(), 'contenido': 'Paso 1: revisar.\nPaso 2: aprobar.\nPaso 3: archivar.',
             'mensaje': 'Agregado el paso 3'},
            format='json',
        )
        self.assertEqual(r.status_code, 200)
        # v1 = como estaba, v2 = el cambio. Sin la v1 no habría a dónde volver.
        self.assertEqual(Version.objects.filter(document=self.texto).count(), 2)
        ultima = Version.objects.filter(document=self.texto).first()
        self.assertEqual(ultima.numero, 2)
        self.assertEqual(ultima.autor, self.user)
        self.assertEqual(ultima.mensaje, 'Agregado el paso 3')

    def test_un_pdf_no_se_puede_editar(self):
        self.como()
        r = self.client.put(
            f'{URL}documentos/{self.pdf.pk}/contenido/',
            {**self.q(), 'contenido': 'otra cosa'}, format='json',
        )
        self.assertEqual(r.status_code, 400)
        self.pdf.refresh_from_db()
        self.assertEqual(self.pdf.extracted_text, 'El plazo es de 45 dias.')

    def test_restaurar_NO_borra_el_historial(self):
        """Borrar la historia para volver atrás es la única forma de perder trabajo."""
        from services.documentos import asegurar_version_inicial, escribir

        # La v1 es el estado con el que entró: es lo que hace la vista antes de escribir,
        # y sin ella "volver al original" no existiría.
        asegurar_version_inicial(self.texto)
        original = self.texto.extracted_text
        escribir(self.texto, 'version dos', autor=self.user)
        escribir(self.texto, 'version tres', autor=self.user)

        self.como()
        r = self.client.post(f'{URL}documentos/{self.texto.pk}/versiones/1/', self.q(), format='json')
        self.assertEqual(r.status_code, 200)

        numeros = list(Version.objects.filter(document=self.texto).values_list('numero', flat=True))
        self.assertEqual(sorted(numeros), [1, 2, 3, 4])
        self.texto.refresh_from_db()
        self.assertEqual(self.texto.extracted_text, original)

    def test_la_version_de_un_agente_se_firma_con_su_handle(self):
        from services.documentos import escribir

        version = escribir(self.texto, 'lo que escribió el agente', agente=self.agente)
        self.assertEqual(version.origen, 'agente')
        self.assertEqual(version.quien, f'@{self.agente.handle}')

    def test_borrar_el_documento_se_lleva_sus_versiones(self):
        from services.documentos import escribir

        escribir(self.texto, 'algo', autor=self.user)
        self.texto.delete()
        self.assertEqual(Version.objects.count(), 0)


class EdicionPorReemplazoTests(BaseArchivos):
    """El modo de edición que se le da al agente: quirúrgico, no reescribir todo."""

    def setUp(self):
        super().setUp()
        self.parche = mock.patch('services.indexing.indexar_documento_sin_ruido', return_value=1)
        self.parche.start()
        self.addCleanup(self.parche.stop)

    def test_cambia_solo_el_fragmento(self):
        from services.documentos import editar_por_reemplazo

        editar_por_reemplazo(
            self.texto, 'Paso 2: aprobar.', 'Paso 2: aprobar y firmar.', agente=self.agente,
        )
        self.texto.refresh_from_db()
        self.assertIn('Paso 1: revisar.', self.texto.extracted_text)
        self.assertIn('aprobar y firmar', self.texto.extracted_text)

    def test_un_fragmento_que_no_esta_no_cambia_nada(self):
        from services.documentos import TextoNoEncontrado, editar_por_reemplazo

        with self.assertRaises(TextoNoEncontrado):
            editar_por_reemplazo(self.texto, 'Paso 9: inventado.', 'otra cosa', agente=self.agente)
        self.texto.refresh_from_db()
        self.assertEqual(self.texto.extracted_text, 'Paso 1: revisar.\nPaso 2: aprobar.')

    def test_un_fragmento_ambiguo_se_rechaza(self):
        """Adivinar cuál de las dos apariciones cambiar es cambiar la línea equivocada."""
        from services.documentos import TextoNoEncontrado, editar_por_reemplazo

        self.texto.extracted_text = 'revisar\nrevisar'
        self.texto.save(update_fields=['extracted_text'])
        with self.assertRaises(TextoNoEncontrado) as ctx:
            editar_por_reemplazo(self.texto, 'revisar', 'aprobar', agente=self.agente)
        self.assertIn('2 veces', str(ctx.exception))

    def test_no_se_edita_por_reemplazo_un_binario(self):
        from services.documentos import NoEditable, editar_por_reemplazo

        with self.assertRaises(NoEditable):
            editar_por_reemplazo(self.pdf, '45 dias', '60 dias', agente=self.agente)


class HerramientasDelAgenteTests(BaseArchivos):
    """Las tres herramientas de escritura, ejecutadas como las ejecuta el agente."""

    def setUp(self):
        super().setUp()
        self.parche = mock.patch('services.indexing.indexar_documento_sin_ruido', return_value=1)
        self.parche.start()
        self.addCleanup(self.parche.stop)

    def ejecutar(self, nombre, args, allowed_doc_ids=None):
        from services.agent_tools import execute_tool

        return execute_tool(
            nombre, args, self.org, [], allowed_doc_ids=allowed_doc_ids, agente=self.agente,
        )

    def test_crear_documento_lo_guarda_y_lo_firma(self):
        r = self.ejecutar('crear_documento', {'titulo': 'Informe', 'contenido': '# Informe\nTexto.'})
        self.assertTrue(r.get('ok'))
        doc = CompanyDocument.objects.get(pk=r['id'])
        self.assertTrue(doc.editable)
        self.assertEqual(doc.versiones.first().agente, self.agente)

    def test_no_crea_un_documento_vacio(self):
        r = self.ejecutar('crear_documento', {'titulo': 'Vacío', 'contenido': '   '})
        self.assertIn('error', r)

    def test_editar_documento_deja_una_version_del_agente(self):
        r = self.ejecutar('editar_documento', {
            'id': self.texto.pk, 'viejo': 'Paso 2: aprobar.', 'nuevo': 'Paso 2: aprobar y firmar.',
            'mensaje': 'Se agrega la firma',
        })
        self.assertTrue(r.get('ok'))
        self.assertEqual(r['version'], 2)
        ultima = Version.objects.filter(document=self.texto).first()
        self.assertEqual(ultima.agente, self.agente)
        self.assertEqual(ultima.mensaje, 'Se agrega la firma')

    def test_el_agente_no_edita_un_binario_y_recibe_una_salida(self):
        """El error tiene que decirle qué hacer, no solo que no puede."""
        r = self.ejecutar('editar_documento', {'id': self.pdf.pk, 'viejo': '45', 'nuevo': '60'})
        self.assertIn('error', r)
        self.assertIn('crear_documento', r['error'])

    def test_el_agente_no_edita_lo_que_su_espacio_no_alcanza(self):
        """El alcance de siempre: `allowed_doc_ids` vale también para escribir."""
        r = self.ejecutar(
            'editar_documento',
            {'id': self.texto.pk, 'viejo': 'Paso 1', 'nuevo': 'Paso uno'},
            allowed_doc_ids=[self.pdf.pk],
        )
        self.assertIn('error', r)
        self.texto.refresh_from_db()
        self.assertIn('Paso 1', self.texto.extracted_text)

    def test_reescribir_reemplaza_todo(self):
        r = self.ejecutar('reescribir_documento', {
            'id': self.texto.pk, 'contenido': 'Todo nuevo.', 'mensaje': 'Reescrito',
        })
        self.assertTrue(r.get('ok'))
        self.texto.refresh_from_db()
        self.assertEqual(self.texto.extracted_text, 'Todo nuevo.')

    def test_no_reescribe_a_vacio(self):
        r = self.ejecutar('reescribir_documento', {'id': self.texto.pk, 'contenido': ''})
        self.assertIn('error', r)

    def test_un_documento_de_otra_empresa_no_se_toca(self):
        otra = Organization.objects.create(owner=self.ajeno, name='Muebles Ltda')
        ajeno = CompanyDocument.objects.create(
            organization=otra, title='Ajeno', file='a.md', editable=True, extracted_text='hola',
        )
        r = self.ejecutar('editar_documento', {'id': ajeno.pk, 'viejo': 'hola', 'nuevo': 'chau'})
        self.assertIn('error', r)


class HerramientasSegunLoConectadoTests(BaseArchivos):
    """Sin sistemas conectados quedan las de documentos, no ninguna.

    Antes se entregaban todas o ninguna: una empresa con solo documentos tenía un agente
    SIN herramientas, así que no podía ni buscar ni escribir.
    """

    def test_sin_conexiones_quedan_las_de_documentos(self):
        from services.agent_tools import _tools_spec

        nombres = [t['name'] for t in _tools_spec(self.org)]
        self.assertIn('crear_documento', nombres)
        self.assertIn('editar_documento', nombres)
        self.assertIn('buscar_en_fuentes', nombres)
        self.assertNotIn('run_sql', nombres)
        self.assertNotIn('query_odoo', nombres)

    def test_con_conexiones_estan_todas(self):
        from apps.organizations.models import SystemConnection
        from services.agent_tools import _tools_spec

        SystemConnection.objects.create(
            organization=self.org, name='Odoo', connector_type='odoo', is_active=True,
        )
        nombres = [t['name'] for t in _tools_spec(self.org)]
        self.assertIn('run_sql', nombres)
        self.assertIn('crear_documento', nombres)


class EsEditableTests(TestCase):
    """Qué tipos se pueden editar. La IA edita texto; un PDF o un Excel, no."""

    def test_los_de_texto_si(self):
        from services.documentos import es_editable

        for nombre, ct in [
            ('notas.md', 'text/markdown'), ('a.txt', 'text/plain'),
            ('datos.csv', 'text/csv'), ('x.md', ''), ('y.json', ''),
        ]:
            self.assertTrue(es_editable(nombre, ct), f'{nombre} debería ser editable')

    def test_los_binarios_no(self):
        from services.documentos import es_editable

        for nombre, ct in [
            ('c.pdf', 'application/pdf'),
            ('x.docx', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'),
            ('h.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('f.png', 'image/png'),
        ]:
            self.assertFalse(es_editable(nombre, ct), f'{nombre} NO debería ser editable')


class PermisosBase(BaseArchivos):
    """Una empresa con un admin, dos personas comunes, y carpetas para restringir."""

    def setUp(self):
        super().setUp()
        from apps.workspaces.models import ROLE_MEMBER

        # `self.user` es ADMIN del Workspace (lo pone BaseArchivos), así que ve todo.
        self.ana = User.objects.create_user(
            username='ana@afable.test', email='ana@afable.test', password='afable123',
        )
        self.beto = User.objects.create_user(
            username='beto@afable.test', email='beto@afable.test', password='afable123',
        )
        self.ws.add_member(self.ana, ROLE_MEMBER)
        self.ws.add_member(self.beto, ROLE_MEMBER)

        self.rrhh = Carpeta.objects.create(
            organization=self.org, name='RRHH', restringida=True, created_by=self.user,
        )
        self.contratos = Carpeta.objects.create(
            organization=self.org, name='Contratos', parent=self.rrhh,
        )
        self.sueldos = CompanyDocument.objects.create(
            organization=self.org, title='Sueldos 2026', file='s.md',
            content_type='text/markdown', editable=True, carpeta=self.rrhh,
            extracted_text='El gerente gana 5 millones.',
        )
        # Uno público, para comprobar que restringir no arrastra a los demás.
        self.publico = CompanyDocument.objects.create(
            organization=self.org, title='Manual de marca', file='m.md',
            content_type='text/markdown', editable=True,
            extracted_text='El logo va en indigo.',
        )

    def nivel_doc(self, quien, doc):
        from apps.archivos.permisos import nivel_sobre_documento
        from apps.workspaces.permissions import membership_por_organizacion

        return nivel_sobre_documento(quien, doc, membership_por_organizacion(quien, self.org))

    def visibles(self, quien):
        from apps.archivos.permisos import documentos_visibles
        from apps.workspaces.permissions import membership_por_organizacion

        return set(
            documentos_visibles(quien, self.org, membership_por_organizacion(quien, self.org))
            .values_list('title', flat=True)
        )


class HerenciaDePermisosTests(PermisosBase):
    """Manda la restricción más cercana, y restringir es la excepción."""

    def test_sin_restringir_lo_ve_cualquier_miembro(self):
        self.assertEqual(self.nivel_doc(self.ana, self.publico), 'edicion')

    def test_una_carpeta_restringida_esconde_lo_que_tiene_adentro(self):
        self.assertIsNone(self.nivel_doc(self.ana, self.sueldos))
        self.assertNotIn('Sueldos 2026', self.visibles(self.ana))

    def test_pero_no_esconde_lo_de_afuera(self):
        """Restringir una carpeta no puede volver invisible el resto de la empresa."""
        self.assertIn('Manual de marca', self.visibles(self.ana))

    def test_la_restriccion_se_hereda_hacia_abajo(self):
        """Una subcarpeta de una carpeta restringida también queda restringida."""
        from apps.archivos.permisos import nivel_sobre_carpeta
        from apps.workspaces.permissions import membership_por_organizacion

        nivel = nivel_sobre_carpeta(
            self.ana, self.contratos, membership_por_organizacion(self.ana, self.org),
        )
        self.assertIsNone(nivel)

    def test_con_permiso_de_lectura_lo_ve_pero_no_lo_edita(self):
        from apps.archivos.models import Permiso

        Permiso.objects.create(carpeta=self.rrhh, user=self.ana, nivel='lectura')
        self.assertEqual(self.nivel_doc(self.ana, self.sueldos), 'lectura')
        self.assertIn('Sueldos 2026', self.visibles(self.ana))

    def test_con_permiso_de_edicion_lo_edita(self):
        from apps.archivos.models import Permiso

        Permiso.objects.create(carpeta=self.rrhh, user=self.ana, nivel='edicion')
        self.assertEqual(self.nivel_doc(self.ana, self.sueldos), 'edicion')

    def test_el_permiso_de_una_persona_no_alcanza_a_otra(self):
        from apps.archivos.models import Permiso

        Permiso.objects.create(carpeta=self.rrhh, user=self.ana, nivel='lectura')
        self.assertIsNone(self.nivel_doc(self.beto, self.sueldos))

    def test_el_administrador_del_workspace_ve_todo(self):
        """No puede administrar lo que no ve."""
        self.assertEqual(self.nivel_doc(self.user, self.sueldos), 'edicion')
        self.assertIn('Sueldos 2026', self.visibles(self.user))

    def test_quien_subio_el_archivo_no_pierde_el_acceso(self):
        """Perder acceso a lo propio no se entiende de ninguna manera."""
        propio = CompanyDocument.objects.create(
            organization=self.org, title='Lo de Ana', file='a.md',
            uploaded_by=self.ana, carpeta=self.rrhh, editable=True,
        )
        self.assertEqual(self.nivel_doc(self.ana, propio), 'edicion')

    def test_un_documento_se_restringe_por_si_solo(self):
        """Sin carpeta restringida: la restricción propia del archivo alcanza."""
        self.publico.restringido = True
        self.publico.save(update_fields=['restringido'])
        self.assertIsNone(self.nivel_doc(self.ana, self.publico))
        self.assertNotIn('Manual de marca', self.visibles(self.ana))

    def test_un_permiso_en_el_documento_gana_sobre_su_carpeta(self):
        """La restricción MÁS CERCANA manda: la del archivo antes que la de la carpeta."""
        from apps.archivos.models import Permiso

        self.sueldos.restringido = True
        self.sueldos.save(update_fields=['restringido'])
        Permiso.objects.create(document=self.sueldos, user=self.ana, nivel='lectura')
        self.assertEqual(self.nivel_doc(self.ana, self.sueldos), 'lectura')


class ElExploradorRespetaLosPermisosTests(PermisosBase):

    def test_la_carpeta_restringida_no_aparece_en_el_arbol(self):
        """Que no exista para quien no entra es más simple que un «sin acceso»."""
        self.client.force_authenticate(user=self.ana)
        datos = self.client.get(URL, self.q()).data
        self.assertNotIn('RRHH', [c['name'] for c in datos['arbol']])

    def test_el_administrador_si_la_ve(self):
        self.client.force_authenticate(user=self.user)
        datos = self.client.get(URL, self.q()).data
        self.assertIn('RRHH', [c['name'] for c in datos['arbol']])

    def test_buscar_no_encuentra_lo_restringido(self):
        """El buscador es el agujero clásico: mira toda la empresa."""
        self.client.force_authenticate(user=self.ana)
        datos = self.client.get(URL, {**self.q(), 'q': 'Sueldos'}).data
        self.assertEqual(datos['documentos'], [])

    def test_leer_un_documento_restringido_da_404_no_403(self):
        """Un 403 confirmaría que existe y filtraría su id."""
        self.client.force_authenticate(user=self.ana)
        r = self.client.get(f'{URL}documentos/{self.sueldos.pk}/contenido/', self.q())
        self.assertEqual(r.status_code, 404)

    def test_con_lectura_lo_lee_pero_guardar_da_403(self):
        """Verlo y no poder editarlo SÍ es un 403: la diferencia importa."""
        from apps.archivos.models import Permiso

        Permiso.objects.create(carpeta=self.rrhh, user=self.ana, nivel='lectura')
        self.client.force_authenticate(user=self.ana)

        self.assertEqual(
            self.client.get(f'{URL}documentos/{self.sueldos.pk}/contenido/', self.q()).status_code,
            200,
        )
        r = self.client.put(
            f'{URL}documentos/{self.sueldos.pk}/contenido/',
            {**self.q(), 'contenido': 'otra cosa'}, format='json',
        )
        self.assertEqual(r.status_code, 403)
        self.sueldos.refresh_from_db()
        self.assertIn('5 millones', self.sueldos.extracted_text)

    def test_con_lectura_tampoco_lo_renombra_ni_lo_mueve(self):
        from apps.archivos.models import Permiso

        Permiso.objects.create(carpeta=self.rrhh, user=self.ana, nivel='lectura')
        self.client.force_authenticate(user=self.ana)
        r = self.client.patch(
            f'{URL}documentos/{self.sueldos.pk}/', {**self.q(), 'title': 'Robado'}, format='json',
        )
        self.assertEqual(r.status_code, 403)

    def test_con_lectura_no_restaura_una_version(self):
        from apps.archivos.models import Permiso
        from services.documentos import asegurar_version_inicial

        asegurar_version_inicial(self.sueldos)
        Permiso.objects.create(carpeta=self.rrhh, user=self.ana, nivel='lectura')
        self.client.force_authenticate(user=self.ana)
        r = self.client.post(
            f'{URL}documentos/{self.sueldos.pk}/versiones/1/', self.q(), format='json',
        )
        self.assertEqual(r.status_code, 403)

    def test_el_historial_de_lo_restringido_no_se_lee(self):
        self.client.force_authenticate(user=self.ana)
        r = self.client.get(f'{URL}documentos/{self.sueldos.pk}/versiones/', self.q())
        self.assertEqual(r.status_code, 404)


class CompartirTests(PermisosBase):

    def test_se_comparte_una_carpeta_con_alguien(self):
        self.client.force_authenticate(user=self.user)
        r = self.client.post(
            f'{URL}compartir/',
            {**self.q(), 'carpeta': self.rrhh.pk, 'ids': [self.ana.pk], 'nivel': 'lectura'},
            format='json',
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['compartido_con'][0]['email'], self.ana.email)
        self.assertEqual(self.nivel_doc(self.ana, self.sueldos), 'lectura')

    def test_se_sube_de_lectura_a_edicion(self):
        from apps.archivos.models import Permiso

        Permiso.objects.create(carpeta=self.rrhh, user=self.ana, nivel='lectura')
        self.client.force_authenticate(user=self.user)
        self.client.post(
            f'{URL}compartir/',
            {**self.q(), 'carpeta': self.rrhh.pk, 'ids': [self.ana.pk], 'nivel': 'edicion'},
            format='json',
        )
        self.assertEqual(self.nivel_doc(self.ana, self.sueldos), 'edicion')

    def test_se_saca_el_permiso(self):
        from apps.archivos.models import Permiso

        Permiso.objects.create(carpeta=self.rrhh, user=self.ana, nivel='lectura')
        self.client.force_authenticate(user=self.user)
        r = self.client.delete(
            f'{URL}compartir/', {**self.q(), 'carpeta': self.rrhh.pk, 'ids': [self.ana.pk]},
            format='json',
        )
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(self.nivel_doc(self.ana, self.sueldos))

    def test_no_se_comparte_con_alguien_de_fuera_del_workspace(self):
        """Compartir con alguien de afuera es invitarlo a la empresa, y eso va en Admin."""
        self.client.force_authenticate(user=self.user)
        r = self.client.post(
            f'{URL}compartir/',
            {**self.q(), 'carpeta': self.rrhh.pk, 'ids': [self.ajeno.pk]}, format='json',
        )
        self.assertEqual(r.status_code, 400)

    def test_quien_solo_lee_no_reparte_accesos(self):
        """Si no, el nivel de lectura no significaría nada."""
        from apps.archivos.models import Permiso

        Permiso.objects.create(carpeta=self.rrhh, user=self.ana, nivel='lectura')
        self.client.force_authenticate(user=self.ana)
        r = self.client.post(
            f'{URL}compartir/',
            {**self.q(), 'carpeta': self.rrhh.pk, 'ids': [self.beto.pk]}, format='json',
        )
        self.assertEqual(r.status_code, 403)

    def test_se_restringe_y_se_desrestringe_un_documento(self):
        self.client.force_authenticate(user=self.user)
        self.client.post(
            f'{URL}compartir/',
            {**self.q(), 'documento': self.publico.pk, 'restringido': True}, format='json',
        )
        self.publico.refresh_from_db()
        self.assertTrue(self.publico.restringido)
        self.assertIsNone(self.nivel_doc(self.ana, self.publico))

        self.client.post(
            f'{URL}compartir/',
            {**self.q(), 'documento': self.publico.pk, 'restringido': False}, format='json',
        )
        self.publico.refresh_from_db()
        self.assertEqual(self.nivel_doc(self.ana, self.publico), 'edicion')


class NadieUsaUnAgenteParaSaltearUnPermisoTests(PermisosBase):
    """La propiedad por la que existe todo este bloque.

    Si el alcance del agente no se intersectara con lo que ve la persona, restringir un
    archivo sería teatro: bastaría con preguntárselo al agente.
    """

    def prompt(self, quien):
        from apps.agents.views import _build_onboarding_context

        return _build_onboarding_context(quien, consulta='¿cuánto gana el gerente?')['system_prompt']

    def test_el_prompt_de_quien_no_ve_el_archivo_no_lo_trae(self):
        self.assertNotIn('5 millones', self.prompt(self.ana))

    def test_el_prompt_del_administrador_si_lo_trae(self):
        self.assertIn('5 millones', self.prompt(self.user))

    def test_con_permiso_el_prompt_lo_trae(self):
        from apps.archivos.models import Permiso

        Permiso.objects.create(carpeta=self.rrhh, user=self.ana, nivel='lectura')
        self.assertIn('5 millones', self.prompt(self.ana))

    def test_lo_no_restringido_sigue_llegando_a_todos(self):
        """Restringir uno no puede dejar al agente sin el resto."""
        self.assertIn('indigo', self.prompt(self.ana))

    def test_las_herramientas_tampoco_lo_alcanzan(self):
        """`allowed_doc_ids` recortado viaja hasta `_documentos` en agent_tools."""
        from apps.agents.views import _build_onboarding_context
        from services.agent_tools import execute_tool

        contexto = _build_onboarding_context(self.ana, consulta='sueldos')
        r = execute_tool(
            'read_company_document', {'id': self.sueldos.pk}, self.org, [],
            allowed_doc_ids=contexto.get('allowed_doc_ids'),
        )
        self.assertIn('error', r)
