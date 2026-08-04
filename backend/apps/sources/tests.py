"""
Pruebas de la busqueda semantica: troceado, indexado, recuperacion y alcance.

Ninguna habla con Ollama. El proveedor de embeddings se reemplaza por
`_vector_falso`, que es determinista y se comporta como uno de verdad en lo unico
que importa aca: dos textos que hablan de lo mismo quedan cerca y dos que no,
lejos. Asi las pruebas corren en CI sin GPU, sin red y sin modelo bajado.
"""
import hashlib
import random
import re
import unittest.mock as mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.organizations.models import CompanyDocument, Organization, SystemConnection
from services.chunking import trocear
from services.embeddings import DIMENSION, EmbeddingsNoDisponibles

User = get_user_model()

MODELO_PRUEBA = 'modelo-de-prueba'

_PALABRAS = re.compile(r'\w+', re.UNICODE)

# Palabras que aparecen en cualquier frase y no dicen de que habla el texto. Un
# embedding de verdad las pondera solo; el falso las tiene que sacar a mano o
# termina midiendo gramatica en vez de tema.
_VACIAS = frozenset("""
a al algo ante antes aqui como con contra cual cuando de del desde donde dos el
ella ellas ellos en entre era es esa ese eso esta este esto ha hay la las le les
lo los mas me mi mucho muy no nos o otro para pero poco por porque que quien se
segun ser si sin sobre solo son su sus tambien tiene todo tras un una uno unos y
ya
""".split())

_cache_palabras = {}


def _vector_de_palabra(palabra: str) -> list[float]:
    """Un vector denso, estable y casi ortogonal al de cualquier otra palabra.

    La primera version de esto ponia cada palabra en UNA dimension (hash mod 768)
    y fallo por lo obvio en retrospectiva: con 768 casilleros, dos palabras chocan
    seguido, y un choque vale similitud 1.0. «las» caia en la dimension de
    «instalada» y el reglamento salia primero en una busqueda sobre encimeras.

    Repartiendo cada palabra por las 768 dimensiones, dos palabras distintas
    quedan a coseno ~0 (ruido ~1/sqrt(768) = 0.036) en vez de indistinguibles.
    """
    if palabra not in _cache_palabras:
        semilla = int.from_bytes(hashlib.blake2b(palabra.encode(), digest_size=8).digest(), 'big')
        rnd = random.Random(semilla)
        v = [rnd.uniform(-1.0, 1.0) for _ in range(DIMENSION)]
        norma = sum(x * x for x in v) ** 0.5
        _cache_palabras[palabra] = [x / norma for x in v]
    return _cache_palabras[palabra]


def _vector_falso(texto: str) -> list[float]:
    """Suma de los vectores de las palabras con contenido, normalizada.

    El coseno entre dos textos termina midiendo cuanto vocabulario de fondo
    comparten. No entiende sinonimos —ningun embedding falso lo hace— pero para
    probar el ranking, el corte por distancia y el aislamiento por Espacio, que es
    lo que se prueba aca, alcanza y sobra.
    """
    vector = [0.0] * DIMENSION
    for palabra in _PALABRAS.findall((texto or '').lower()):
        if palabra in _VACIAS:
            continue
        for i, x in enumerate(_vector_de_palabra(palabra)):
            vector[i] += x
    norma = sum(v * v for v in vector) ** 0.5
    if norma == 0:
        # pgvector no puede medir coseno contra el vector nulo.
        vector[0] = 1.0
        return vector
    return [v / norma for v in vector]


def _embed_documentos_falso(textos, titulos=None):
    return [_vector_falso(t) for t in textos]


def _embed_consulta_falso(consulta):
    return _vector_falso(consulta)


def con_embeddings_falsos(func):
    """Decorador: el proveedor de embeddings es el falso y esta disponible.

    Se parchean los dos lados por separado porque `indexing` importa
    `embed_documentos` al cargarse (referencia propia) mientras que `retrieval`
    importa dentro de la funcion.
    """
    func = mock.patch('services.indexing.embed_documentos', _embed_documentos_falso)(func)
    func = mock.patch('services.embeddings.embed_consulta', _embed_consulta_falso)(func)
    func = mock.patch('services.embeddings.disponible', lambda *a, **k: True)(func)
    # EMBEDDINGS_MODEL se respeta en los dos lados: `modelo_activo()` lo lee de
    # settings, asi que indexado y busqueda coinciden sin parchear nada mas.
    return override_settings(EMBEDDINGS_MODEL=MODELO_PRUEBA)(func)


class TroceadoTests(TestCase):
    """El texto se parte donde el texto ya venia partido."""

    def test_un_texto_corto_queda_en_un_solo_trozo(self):
        self.assertEqual(trocear('Somos una empresa de cocinas.'), ['Somos una empresa de cocinas.'])

    def test_un_texto_vacio_no_da_trozos(self):
        self.assertEqual(trocear(''), [])
        self.assertEqual(trocear('   \n  '), [])

    def test_un_texto_largo_se_parte_en_varios(self):
        parrafos = '\n\n'.join(f'Parrafo numero {i} sobre politicas internas. ' * 6 for i in range(20))
        trozos = trocear(parrafos, tamano=500, solape=50)
        self.assertGreater(len(trozos), 1)

    def test_ningun_trozo_pasa_el_tamano_mas_el_solape(self):
        parrafos = '\n\n'.join(f'Parrafo {i} con bastante texto adentro. ' * 8 for i in range(15))
        tamano, solape = 400, 60
        for trozo in trocear(parrafos, tamano=tamano, solape=solape):
            self.assertLessEqual(len(trozo), tamano + solape)

    def test_los_trozos_se_solapan(self):
        """Sin solape, la frase que responde la pregunta puede caer partida al medio."""
        parrafos = '\n\n'.join(f'Oracion distinta numero {i} del documento.' for i in range(40))
        trozos = trocear(parrafos, tamano=300, solape=80)
        self.assertGreater(len(trozos), 2)
        # El final de un trozo tiene que reaparecer al principio del siguiente.
        solapados = 0
        for anterior, siguiente in zip(trozos, trozos[1:]):
            cola = anterior[-40:].strip().split()
            if cola and cola[-1] in siguiente[:120]:
                solapados += 1
        self.assertGreater(solapados, 0)

    def test_un_bloque_sin_puntuacion_igual_se_parte(self):
        """Una tabla o un JSON pegado no tienen parrafos ni oraciones donde cortar."""
        pegote = 'x' * 3000
        trozos = trocear(pegote, tamano=500, solape=0)
        self.assertGreater(len(trozos), 1)
        self.assertEqual(''.join(trozos), pegote)

    def test_no_se_guardan_migajas(self):
        texto = ('Parrafo con contenido real y suficiente largo. ' * 12) + '\n\nSi.'
        trozos = trocear(texto, tamano=300, solape=40)
        self.assertNotIn('Si.', trozos)
        self.assertIn('Si.', trozos[-1])


class BaseConocimiento(TestCase):
    """Una empresa con dos documentos que hablan de cosas distintas."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='duena@afable.test', email='duena@afable.test', password='afable123',
        )
        self.org = Organization.objects.create(owner=self.user, name='Cocinas SpA')
        self.reglamento = CompanyDocument.objects.create(
            organization=self.org, title='Reglamento interno', file='r.pdf',
            extracted_text=(
                'Las vacaciones del personal se solicitan con quince dias de aviso.\n\n'
                'El horario de colacion es de una hora entre las trece y las quince.'
            ),
        )
        self.catalogo = CompanyDocument.objects.create(
            organization=self.org, title='Catalogo de productos', file='c.pdf',
            extracted_text=(
                'La encimera de granito negro cuesta cuatrocientos mil pesos instalada.\n\n'
                'El modulo de melamina blanca viene en dos anchos distintos.'
            ),
        )

    def indexar_todo(self):
        from services.indexing import indexar_documento
        return sum(indexar_documento(d) for d in (self.reglamento, self.catalogo))


class IndexadoTests(BaseConocimiento):

    @con_embeddings_falsos
    def test_indexar_guarda_fragmentos_con_el_modelo_usado(self):
        from apps.sources.models import Fragmento

        n = self.indexar_todo()
        self.assertEqual(n, Fragmento.objects.count())
        self.assertGreater(n, 0)
        self.assertEqual(set(Fragmento.objects.values_list('modelo', flat=True)), {MODELO_PRUEBA})

    @con_embeddings_falsos
    def test_reindexar_reemplaza_en_vez_de_acumular(self):
        from apps.sources.models import Fragmento
        from services.indexing import indexar_documento

        indexar_documento(self.reglamento)
        primeros = set(Fragmento.objects.filter(document=self.reglamento).values_list('id', flat=True))
        indexar_documento(self.reglamento)
        segundos = set(Fragmento.objects.filter(document=self.reglamento).values_list('id', flat=True))
        self.assertEqual(Fragmento.objects.filter(document=self.reglamento).count(), len(segundos))
        self.assertFalse(primeros & segundos)

    @con_embeddings_falsos
    def test_lo_que_el_documento_ya_no_dice_deja_de_estar_indexado(self):
        """El riesgo del indexado: un fragmento huerfano sigue afirmando lo viejo."""
        from apps.sources.models import Fragmento
        from services.indexing import indexar_documento

        indexar_documento(self.reglamento)
        self.assertTrue(Fragmento.objects.filter(texto__icontains='colacion').exists())

        self.reglamento.extracted_text = 'Las vacaciones se solicitan con treinta dias de aviso.'
        self.reglamento.save(update_fields=['extracted_text'])
        indexar_documento(self.reglamento)

        self.assertFalse(Fragmento.objects.filter(texto__icontains='colacion').exists())
        self.assertTrue(Fragmento.objects.filter(texto__icontains='treinta').exists())

    @con_embeddings_falsos
    def test_un_documento_sin_texto_no_deja_fragmentos(self):
        from apps.sources.models import Fragmento
        from services.indexing import indexar_documento

        vacio = CompanyDocument.objects.create(
            organization=self.org, title='Escaneo ilegible', file='v.pdf', extracted_text='',
        )
        self.assertEqual(indexar_documento(vacio), 0)
        self.assertEqual(Fragmento.objects.filter(document=vacio).count(), 0)

    @con_embeddings_falsos
    def test_borrar_el_documento_se_lleva_sus_fragmentos(self):
        from apps.sources.models import Fragmento

        self.indexar_todo()
        self.reglamento.delete()
        self.assertEqual(Fragmento.objects.filter(document_id=self.reglamento.pk).count(), 0)
        self.assertGreater(Fragmento.objects.count(), 0)

    @con_embeddings_falsos
    def test_documentos_sin_indexar_encuentra_los_de_otro_modelo(self):
        """Cambiar de modelo invalida los vectores viejos: hay que reindexar."""
        from services.indexing import documentos_sin_indexar

        self.indexar_todo()
        self.assertEqual(list(documentos_sin_indexar(self.org)), [])

        with override_settings(EMBEDDINGS_MODEL='otro-modelo'):
            pendientes = list(documentos_sin_indexar(self.org))
        self.assertCountEqual(pendientes, [self.reglamento, self.catalogo])


class IndexadoQueFallaTests(BaseConocimiento):
    """Que no haya embeddings no puede romperle nada al usuario."""

    def test_indexar_sin_ruido_se_traga_el_error_del_proveedor(self):
        from services.indexing import indexar_documento_sin_ruido

        def explota(*a, **k):
            raise EmbeddingsNoDisponibles('Ollama apagado')

        # `assertLogs` sirve doble: comprueba que la falla queda registrada (si no,
        # un indice que dejo de armarse no se nota nunca) y se come el log para que
        # no ensucie la salida de las pruebas.
        with mock.patch('services.indexing.embed_documentos', explota):
            with self.assertLogs('services.indexing', level='WARNING'):
                self.assertEqual(indexar_documento_sin_ruido(self.reglamento), 0)

    def test_indexar_sin_ruido_se_traga_un_error_inesperado(self):
        from services.indexing import indexar_documento_sin_ruido

        def explota(*a, **k):
            raise RuntimeError('cualquier cosa')

        with mock.patch('services.indexing.embed_documentos', explota):
            with self.assertLogs('services.indexing', level='ERROR'):
                self.assertEqual(indexar_documento_sin_ruido(self.reglamento), 0)

    @override_settings(EMBEDDINGS_PROVIDER='ninguno')
    def test_con_el_proveedor_apagado_la_busqueda_devuelve_vacio(self):
        from services.embeddings import disponible
        from services.retrieval import buscar

        self.assertFalse(disponible(recargar=True))
        self.assertEqual(buscar(self.org, 'vacaciones'), [])

    def test_un_vector_de_otra_dimension_no_se_guarda(self):
        """La dimension esta en la migracion: guardar otra cosa corrompe el indice."""
        from services.embeddings import _embed

        with mock.patch('services.embeddings._embed_ollama', lambda textos: [[0.0] * 512]):
            with self.assertRaises(EmbeddingsNoDisponibles) as ctx:
                _embed(['hola'])
        self.assertIn('512', str(ctx.exception))


class RecuperacionTests(BaseConocimiento):

    @con_embeddings_falsos
    def test_la_busqueda_trae_el_fragmento_que_habla_del_tema(self):
        from services.retrieval import buscar

        self.indexar_todo()
        resultados = buscar(self.org, 'aviso de vacaciones del personal')
        self.assertTrue(resultados)
        self.assertIn('vacaciones', resultados[0]['texto'].lower())
        self.assertEqual(resultados[0]['documento_id'], self.reglamento.pk)

    @con_embeddings_falsos
    def test_los_resultados_vienen_de_mas_parecido_a_menos(self):
        from services.retrieval import buscar

        self.indexar_todo()
        resultados = buscar(self.org, 'encimera de granito negro instalada')
        self.assertTrue(resultados)
        distancias = [r['distancia'] for r in resultados]
        self.assertEqual(distancias, sorted(distancias))
        self.assertEqual(resultados[0]['documento_id'], self.catalogo.pk)

    @con_embeddings_falsos
    def test_una_consulta_sin_nada_que_ver_no_trae_ruido(self):
        from services.retrieval import buscar

        self.indexar_todo()
        self.assertEqual(buscar(self.org, 'zzzz qqqq wwww kkkk'), [])

    @con_embeddings_falsos
    def test_el_alcance_del_espacio_recorta_la_busqueda(self):
        """Un fragmento fuera del alcance no puede volver ni con la mejor similitud."""
        from services.retrieval import buscar

        self.indexar_todo()
        resultados = buscar(self.org, 'aviso de vacaciones del personal',
                            allowed_doc_ids=[self.catalogo.pk])
        for r in resultados:
            self.assertEqual(r['documento_id'], self.catalogo.pk)

    @con_embeddings_falsos
    def test_un_alcance_vacio_no_busca_en_toda_la_empresa(self):
        from services.retrieval import buscar

        self.indexar_todo()
        self.assertEqual(buscar(self.org, 'vacaciones', allowed_doc_ids=[]), [])

    @con_embeddings_falsos
    def test_la_busqueda_no_cruza_de_empresa(self):
        from services.indexing import indexar_documento
        from services.retrieval import buscar

        otro_user = User.objects.create_user(
            username='otra@afable.test', email='otra@afable.test', password='afable123',
        )
        otra_org = Organization.objects.create(owner=otro_user, name='Muebles Ltda')
        ajeno = CompanyDocument.objects.create(
            organization=otra_org, title='Reglamento ajeno', file='a.pdf',
            extracted_text='Las vacaciones del personal se solicitan con quince dias de aviso.',
        )
        indexar_documento(ajeno)
        self.indexar_todo()

        for r in buscar(self.org, 'aviso de vacaciones del personal'):
            self.assertNotEqual(r['documento_id'], ajeno.pk)

    @con_embeddings_falsos
    def test_hay_indice_respeta_el_alcance(self):
        from services.retrieval import hay_indice

        self.assertFalse(hay_indice(self.org))
        self.indexar_todo()
        self.assertTrue(hay_indice(self.org))
        self.assertTrue(hay_indice(self.org, allowed_doc_ids=[self.catalogo.pk]))
        self.assertFalse(hay_indice(self.org, allowed_doc_ids=[]))

    @con_embeddings_falsos
    def test_el_indice_de_otro_modelo_no_se_usa(self):
        from services.retrieval import buscar, hay_indice

        self.indexar_todo()
        with override_settings(EMBEDDINGS_MODEL='otro-modelo'):
            self.assertFalse(hay_indice(self.org))
            self.assertEqual(buscar(self.org, 'vacaciones'), [])


class BusquedaEnFuentesTests(BaseConocimiento):
    """La herramienta que usa el agente: semantica y literal en la misma puerta."""

    @con_embeddings_falsos
    def test_encuentra_por_contenido_sin_coincidencia_textual(self):
        """«aviso previo del personal» no es subcadena de nada: lo trae la semantica."""
        from services.agent_tools import execute_tool

        self.indexar_todo()
        prov = []
        r = execute_tool('buscar_en_fuentes', {'consulta': 'aviso previo del personal'},
                         self.org, prov)
        self.assertTrue(r['encontrado'])
        ids = [h['id'] for h in r['resultados']]
        self.assertIn(self.reglamento.pk, ids)

    def test_sin_indice_la_busqueda_literal_sigue_funcionando(self):
        """Sin embeddings la herramienta no se queda muda: cae a la coincidencia exacta."""
        from services.agent_tools import execute_tool

        prov = []
        with mock.patch('services.embeddings.disponible', lambda *a, **k: False):
            r = execute_tool('buscar_en_fuentes', {'consulta': 'granito'}, self.org, prov)
        self.assertTrue(r['encontrado'])
        self.assertEqual([h['id'] for h in r['resultados']], [self.catalogo.pk])

    @con_embeddings_falsos
    def test_un_documento_no_se_repite_por_aparecer_de_las_dos_formas(self):
        from services.agent_tools import execute_tool

        self.indexar_todo()
        prov = []
        r = execute_tool('buscar_en_fuentes', {'consulta': 'vacaciones'}, self.org, prov)
        ids = [h['id'] for h in r['resultados']]
        self.assertEqual(len(ids), len(set(ids)))

    @con_embeddings_falsos
    def test_la_herramienta_respeta_el_alcance_del_espacio(self):
        from services.agent_tools import execute_tool

        self.indexar_todo()
        prov = []
        r = execute_tool('buscar_en_fuentes', {'consulta': 'aviso de vacaciones'},
                         self.org, prov, allowed_doc_ids=[self.catalogo.pk])
        for h in r.get('resultados', []):
            self.assertNotEqual(h['id'], self.reglamento.pk)


class PromptConCorpusGrandeTests(TestCase):
    """Cuando los documentos no caben, entran los fragmentos que responden."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='duena@afable.test', email='duena@afable.test', password='afable123',
        )
        self.org = Organization.objects.create(owner=self.user, name='Cocinas SpA')
        SystemConnection.objects.create(
            organization=self.org, name='Odoo Ventas', connector_type='odoo',
        )
        # Relleno: mas texto del que cabe en el presupuesto del prompt (60.000).
        self.relleno = CompanyDocument.objects.create(
            organization=self.org, title='Manual de operaciones', file='m.pdf',
            extracted_text='\n\n'.join(
                f'Procedimiento numero {i} de bodega, despacho y recepcion de mercaderia.' * 6
                for i in range(400)
            ),
        )
        self.reglamento = CompanyDocument.objects.create(
            organization=self.org, title='Reglamento interno', file='r.pdf',
            extracted_text='Las vacaciones del personal se solicitan con quince dias de aviso.',
        )

    @con_embeddings_falsos
    def test_con_corpus_grande_el_prompt_trae_los_fragmentos_relevantes(self):
        from apps.agents.views import _build_onboarding_context
        from services.indexing import indexar_documento

        indexar_documento(self.relleno)
        indexar_documento(self.reglamento)

        prompt = _build_onboarding_context(
            self.user, consulta='aviso de vacaciones del personal',
        )['system_prompt']
        self.assertIn('FRAGMENTOS RELEVANTES', prompt)
        self.assertIn('quince dias de aviso', prompt)

    @con_embeddings_falsos
    def test_el_prompt_no_se_contradice_al_recuperar(self):
        """Con fragmentos a la vista, el prompt no puede decir que no hay documentos.

        Es el bug que tuvo la primera version: para saltear el volcado se vaciaba la
        lista de documentos, y eso hacia caer la rama del corpus vacio.
        """
        from apps.agents.views import _build_onboarding_context
        from services.indexing import indexar_documento

        indexar_documento(self.relleno)
        indexar_documento(self.reglamento)

        prompt = _build_onboarding_context(
            self.user, consulta='aviso de vacaciones del personal',
        )['system_prompt']
        self.assertIn('FRAGMENTOS RELEVANTES', prompt)
        self.assertNotIn('todavia no tiene documentos', prompt)

    @con_embeddings_falsos
    def test_sin_pregunta_no_se_recupera_nada(self):
        """Una automatizacion sin prompt no tiene con que buscar: queda el camino viejo."""
        from apps.agents.views import _build_onboarding_context
        from services.indexing import indexar_documento

        indexar_documento(self.reglamento)
        prompt = _build_onboarding_context(self.user, consulta='')['system_prompt']
        self.assertNotIn('FRAGMENTOS RELEVANTES', prompt)

    @con_embeddings_falsos
    def test_un_corpus_chico_sigue_yendo_completo_al_prompt(self):
        """Si todo cabe, el texto entero le gana a cualquier recuperacion."""
        from apps.agents.views import _build_onboarding_context
        from services.indexing import indexar_documento

        self.relleno.delete()
        indexar_documento(self.reglamento)

        prompt = _build_onboarding_context(
            self.user, consulta='aviso de vacaciones del personal',
        )['system_prompt']
        self.assertNotIn('FRAGMENTOS RELEVANTES', prompt)
        self.assertIn('quince dias de aviso', prompt)

    def test_con_corpus_grande_y_sin_indice_se_recorta_como_antes(self):
        from apps.agents.views import _build_onboarding_context

        with mock.patch('services.embeddings.disponible', lambda *a, **k: False):
            prompt = _build_onboarding_context(
                self.user, consulta='aviso de vacaciones del personal',
            )['system_prompt']
        self.assertNotIn('FRAGMENTOS RELEVANTES', prompt)
        self.assertIn('CONTENIDO DE LOS DOCUMENTOS', prompt)
