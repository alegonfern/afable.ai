"""La empresa de ejemplo: poder probar Afable antes de cargar nada.

Lo que fijan estas pruebas es lo que hace que el ejemplo sirva y no engañe:

- Son **documentos de verdad**, así que recorren el mismo camino que los de un cliente y
  el agente los puede citar. Un "modo demo" con respuestas simuladas no probaría nada.
- Van **marcados** y se quitan de una sola vez. Si quedaran mezclados con los datos
  reales, el agente citaría un contrato inventado como si fuera de la empresa — la peor
  forma posible de perder la confianza de un cliente.
- **No se duplican** al pedirlos dos veces.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.workspaces.models import ROLE_ADMIN, ROLE_MEMBER, Workspace

from .datos_de_ejemplo import (
    DOCS_DISTRIBUIDORA, WORKSPACE_EJEMPLO, crear_para, quitar_de,
)

CUANTOS = len(DOCS_DISTRIBUIDORA)
from .models import CompanyDocument, Organization

User = get_user_model()


class DatosDeEjemploTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            username='admin@afable.test', email='admin@afable.test', password='afable123',
        )
        self.miembro = User.objects.create_user(
            username='miembro@afable.test', email='miembro@afable.test', password='afable123',
        )
        self.empresa = Organization.objects.create(owner=self.admin, name='Cocinas SpA')
        self.empresa.agregar_miembro(self.admin, ROLE_ADMIN)
        self.empresa.agregar_miembro(self.miembro, ROLE_MEMBER)

    def url(self):
        return f'/api/v1/workspaces/{self.empresa.slug}/ejemplo/'

    # ── Lo que deja ──────────────────────────────────────────────────────────

    def test_deja_documentos_de_verdad_en_su_propio_workspace(self):
        workspace, creados = crear_para(self.empresa, creado_por=self.admin)

        self.assertEqual(creados, CUANTOS)
        self.assertEqual(workspace.name, WORKSPACE_EJEMPLO)
        from apps.organizations.models import CompanyDocument
        docs = CompanyDocument.objects.filter(organization=self.empresa, source='ejemplo')
        self.assertEqual(docs.count(), CUANTOS)
        # Todos en una carpeta: es de donde un agente saca su alcance.
        self.assertTrue(all(d.carpeta_id for d in docs))

        # Con texto extraído: es lo que el agente lee y cita. Sin esto el ejemplo sería
        # una lista de títulos vacíos.
        for doc in docs:
            self.assertTrue(doc.extracted_text.strip())
            self.assertEqual(doc.source, 'ejemplo')

    def test_los_documentos_se_cruzan_entre_si(self):
        """La gracia del ejemplo es poder preguntar algo que obligue a mirar dos."""
        crear_para(self.empresa)
        textos = ' '.join(
            CompanyDocument.objects.filter(organization=self.empresa).values_list(
                'extracted_text', flat=True,
            )
        )
        # El hallazgo NO está escrito en ningún documento: hay que cruzar dos. La lista
        # de marzo y la de agosto traen el mismo producto a distinto precio, y el contrato
        # dice que había que avisar con 60 días. Ninguno de los tres dice "subieron 22%" —
        # si lo dijera, la demo no probaría nada, solo mostraría que la IA sabe leer.
        self.assertIn('marzo 2026', textos)
        self.assertIn('agosto 2026', textos)
        self.assertIn('60 días corridos de anticipación', textos)
        self.assertIn('Comercial Andes', textos)

    def test_no_se_duplican_al_pedirlos_dos_veces(self):
        crear_para(self.empresa)
        _, segunda = crear_para(self.empresa)

        self.assertEqual(segunda, 0)
        self.assertEqual(
            CompanyDocument.objects.filter(organization=self.empresa, source='ejemplo').count(),
            CUANTOS,
        )

    # ── Que se puedan sacar ──────────────────────────────────────────────────

    def test_se_quitan_de_una_sola_vez(self):
        """Mezclados con los datos reales, el agente citaría un contrato inventado."""
        crear_para(self.empresa)
        borrados = quitar_de(self.empresa)

        self.assertEqual(borrados, CUANTOS)
        self.assertEqual(CompanyDocument.objects.filter(organization=self.empresa).count(), 0)
        self.assertFalse(
            Workspace.objects.filter(organization=self.empresa, name=WORKSPACE_EJEMPLO).exists(),
        )

    def test_quitarlos_no_toca_los_documentos_reales(self):
        crear_para(self.empresa)
        mio = CompanyDocument.objects.create(
            organization=self.empresa, title='Mi contrato', file='c.pdf',
            content_type='application/pdf', extracted_text='lo mio',
        )

        quitar_de(self.empresa)

        self.assertTrue(CompanyDocument.objects.filter(pk=mio.pk).exists())

    # ── Quién puede ──────────────────────────────────────────────────────────

    def test_el_administrador_los_carga_desde_la_api(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post(self.url())

        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['documentos'], CUANTOS)
        # Las preguntas sugeridas viajan con la respuesta: quien recién llega no tiene
        # que inventar qué preguntar, que es donde la gente se traba.
        self.assertTrue(r.data['preguntas'])

    def test_un_miembro_no_llena_la_empresa_de_datos_falsos(self):
        self.client.force_authenticate(self.miembro)
        self.assertEqual(self.client.post(self.url()).status_code, 403)


class TresEmpresasDeEjemploTests(TestCase):
    """Las tres demos, y que cada una tenga su hallazgo plantado.

    La regla de estas pruebas: **el hallazgo no puede estar escrito**. Si un documento
    dijera «este proveedor subió 22%», la demo mostraría que la IA sabe leer, que no
    impresiona a nadie. Tiene que salir de cruzar dos.
    """

    def setUp(self):
        self.admin = User.objects.create_user(
            username='a@afable.test', email='a@afable.test', password='x',
        )
        self.empresa = Organization.objects.create(owner=self.admin, name='Prueba SpA')

    def textos(self, tipo):
        from .datos_de_ejemplo import EMPRESAS
        return ' '.join(d['texto'] for d in EMPRESAS[tipo]['documentos'])

    def test_las_tres_estan_en_el_catalogo(self):
        from .datos_de_ejemplo import CONSTRUCTORA, CONSULTORA, DISTRIBUIDORA, catalogo

        claves = {e['clave'] for e in catalogo()}
        self.assertEqual(claves, {DISTRIBUIDORA, CONSTRUCTORA, CONSULTORA})

    def test_cada_una_trae_sus_preguntas_para_arrancar(self):
        """Quien recién llega no tiene que inventar qué preguntar: ahí es donde se traba."""
        from .datos_de_ejemplo import catalogo

        for ficha in catalogo():
            self.assertTrue(ficha['preguntas'], ficha['clave'])
            self.assertGreaterEqual(ficha['documentos'], 5, ficha['clave'])

    def test_se_puede_cargar_cualquiera_de_las_tres(self):
        from .datos_de_ejemplo import CONSTRUCTORA, EMPRESAS, crear_para

        _, creados = crear_para(self.empresa, self.admin, tipo=CONSTRUCTORA)
        self.assertEqual(creados, len(EMPRESAS[CONSTRUCTORA]['documentos']))

        titulos = set(CompanyDocument.objects.filter(
            organization=self.empresa,
        ).values_list('title', flat=True))
        self.assertIn('Permiso de edificación — Dirección de Obras Ñuñoa', titulos)

    def test_un_tipo_desconocido_carga_la_de_siempre(self):
        """Nadie que ya llamaba a esta función empieza a recibir otra cosa."""
        from .datos_de_ejemplo import DOCS_DISTRIBUIDORA, crear_para

        _, creados = crear_para(self.empresa, self.admin, tipo='pesquera')
        self.assertEqual(creados, len(DOCS_DISTRIBUIDORA))

    # ── que el hallazgo exista, y que NO esté escrito ────────────────────────

    def test_la_distribuidora_esconde_un_alza_de_precios(self):
        from .datos_de_ejemplo import DISTRIBUIDORA

        textos = self.textos(DISTRIBUIDORA)
        # Los dos extremos del cruce están.
        self.assertIn('$4.500', textos)   # marzo
        self.assertIn('$5.490', textos)   # agosto
        # Y el alza no está calculada en ninguna parte.
        self.assertNotIn('22%', textos)

    def test_la_distribuidora_esconde_un_cliente_que_dejo_de_comprar(self):
        from .datos_de_ejemplo import DISTRIBUIDORA

        textos = self.textos(DISTRIBUIDORA)
        self.assertIn('Servicios Bío Bío', textos)
        # Aparece con ceros, no con un cartel que diga que se fue.
        self.assertNotIn('dejó de comprar', textos)

    def test_la_constructora_esconde_dos_vencimientos(self):
        from .datos_de_ejemplo import CONSTRUCTORA

        textos = self.textos(CONSTRUCTORA)
        self.assertIn('22 de septiembre de 2026', textos)   # subcontrato
        self.assertIn('30 de septiembre de 2026', textos)   # alcantarillado
        self.assertNotIn('está por vencer', textos)

    def test_la_constructora_esconde_un_estado_de_pago_sin_facturar(self):
        from .datos_de_ejemplo import CONSTRUCTORA

        # La columna dice "No" en facturado; nadie escribió que falta facturarlo.
        self.assertIn('7    Ago 2026     54%        3.880     Sí             No',
                      self.textos(CONSTRUCTORA))

    def test_la_consultora_esconde_un_trabajo_ya_hecho(self):
        """El hallazgo se encuentra por SIGNIFICADO: las dos no comparten las palabras."""
        from .datos_de_ejemplo import CONSULTORA

        from .datos_de_ejemplo import EMPRESAS

        docs = EMPRESAS[CONSULTORA]['documentos']
        textos = self.textos(CONSULTORA)
        self.assertIn('Alimentos del Valle', textos)   # lo que piden ahora
        self.assertIn('Frutícola Maitén', textos)      # lo que ya se hizo

        # ⭐ Lo que sostiene el hallazgo: NINGÚN documento nombra a los dos clientes a la
        # vez. El vínculo entre lo que piden y lo que ya se hizo no está escrito en
        # ninguna parte — hay que encontrarlo por significado, que es lo que esta demo
        # existe para mostrar. Además los dos textos usan palabras distintas para lo
        # mismo: «bodega» en uno, «centro de distribución» en el otro.
        for doc in docs:
            nombra_a_los_dos = (
                'Alimentos del Valle' in doc['texto'] and 'Frutícola Maitén' in doc['texto']
            )
            self.assertFalse(nombra_a_los_dos, doc['titulo'])

    def test_la_consultora_esconde_horas_sin_facturar(self):
        from .datos_de_ejemplo import CONSULTORA

        self.assertIn('64', self.textos(CONSULTORA))
