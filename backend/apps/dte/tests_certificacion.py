"""El asistente de certificación (certificacion.py) con un set de ejemplo y un SII simulado:
interpretar el set, generar los DTE y los libros (validados contra los XSD), la simulación,
subir y consultar en maullin, y los pasos del proceso."""
from pathlib import Path
from unittest import mock

from lxml import etree

from . import certificacion, motor, servicio, sii
from .models import DocumentoEmitido, EnvioSII, ProcesoCertificacion
from .nucleo import ErrorDTE, envio
from .nucleo.esquemas import validar
from .nucleo.xmlutil import SII, leer
from .tests import SIIFalso, _BaseDTE, caf_de_prueba

SET = (Path(__file__).parent / 'nucleo' / 'pruebas' / 'set_pruebas_ejemplo.txt').read_text(encoding='utf-8')
NS = {'s': SII}


class SIILibros(SIIFalso):
    """Responde estados de libro (LOK, LRH...) a los envíos de libros y EPR a los de DTE."""

    def __init__(self, estado_dte='EPR', estado_libro='LOK'):
        super().__init__(estado_dte)
        self.estado_libro, self.trackids = estado_libro, {}

    def enviar(self, xml, rut_empresa, nombre=''):
        r = super().enviar(xml, rut_empresa, nombre)
        r.trackid = str(1000 + len(self.subidos))
        self.trackids[r.trackid] = nombre
        return r

    def estado_envio(self, rut, trackid):
        if self.trackids.get(trackid, '').startswith('libro'):
            return sii.EstadoEnvio(estado=self.estado_libro, glosa='', resumen=[], xml='<R/>')
        return super().estado_envio(rut, trackid)


class InterpretarSetTests(_BaseDTE):
    def test_lee_los_sets_y_sus_casos(self):
        sets = certificacion.interpretar_set(SET)
        self.assertEqual([s['tipo_set'] for s in sets], ['basico', 'guias', 'exenta', 'libro_compras'])
        basico = sets[0]
        self.assertEqual(basico['atencion'], '4329504')
        self.assertEqual([c['tipo'] for c in basico['casos']], [33, 33, 33, 33, 61, 61, 61, 56])
        c2 = basico['casos'][1]
        self.assertEqual(c2['items'][0], {'nombre': 'Pañuelo AFECTO', 'cantidad': '235', 'precio': '2059',
                                          'descuento_pct': '4', 'unidad': '', 'exento': False})
        self.assertTrue(basico['casos'][2]['items'][2]['exento'])
        self.assertEqual(basico['casos'][3]['descuento_global_pct'], '10')
        c5 = basico['casos'][4]
        self.assertEqual((c5['referencia_caso'], c5['codigo_referencia']), ('4329504-1', 2))
        self.assertEqual(basico['casos'][6]['codigo_referencia'], 1)
        guias = sets[1]['casos']
        self.assertEqual([(c['indicador_traslado'], c['tipo_despacho']) for c in guias], [(5, 3), (1, 1), (1, 2)])
        self.assertEqual(sets[2]['casos'][0]['items'][0]['unidad'], 'Hora')
        compras = sets[3]
        self.assertEqual(compras['factor'], '0.60')
        self.assertEqual(compras['compras'][1]['exento'], 10633)
        self.assertEqual(compras['compras'][1]['afecto'], 11473)
        self.assertEqual((compras['compras'][6]['referencia_tipo'], compras['compras'][6]['referencia_folio']), (33, 32))
        self.assertFalse(any(c['problemas'] for s in sets for c in s['casos']))

    def test_lo_que_no_entiende_queda_como_problema_del_caso(self):
        texto = 'SET BASICO - NUMERO DE ATENCION: 1\nCASO 1-1\nDOCUMENTO\tBOLETA RARA\n\n\tITEM\tCANTIDAD\n\tUno\t1\n'
        caso = certificacion.interpretar_set(texto)[0]['casos'][0]
        self.assertIn('No se reconoce el tipo de documento', caso['problemas'][0])
        with self.assertRaisesMessage(ErrorDTE, 'no parece un set'):
            certificacion.interpretar_set('hola')


class GenerarTests(_BaseDTE):
    def setUp(self):
        super().setUp()
        self._alta(activar=False)
        for tipo in (34, 52, 56, 61):
            servicio.cargar_caf(self.org, caf_de_prueba('76000000-0', tipo=tipo))
        self.client.force_authenticate(self.admin)
        self.cert_url = f'{self.dte}/certificacion'
        r = self.client.post(f'{self.cert_url}/set/', {'texto': SET}, format='json')
        self.assertEqual(r.status_code, 200, r.content)

    def _cafs(self):
        from .models import Caf
        return {('76000000-0', c.tipo): c.cargar() for c in Caf.objects.filter(organization=self.org)}

    def _generar(self, que, **extra):
        r = self.client.post(f'{self.cert_url}/generar/', {'que': que, **extra}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        return EnvioSII.objects.filter(pk__in=r.data['generados']).order_by('id')

    def test_genera_un_envio_por_set_valido_y_con_las_referencias_del_set(self):
        envios = list(self._generar('set'))
        self.assertEqual([e.proposito for e in envios], [EnvioSII.SET_PRUEBAS] * 3)
        self.assertEqual([e.documentos.count() for e in envios], [8, 3, 3])
        self.assertTrue(all(e.siguiente_intento is None for e in envios))
        cafs = self._cafs()
        raices = [envio.revisar(e.xml.encode('iso-8859-1'), cafs=cafs) for e in envios]
        for raiz in raices:
            self.assertEqual(raiz.findtext('.//s:RutReceptor', namespaces=NS), '60803000-K')
            self.assertEqual(raiz.findtext('.//s:NroResol', namespaces=NS), '0')
            for doc in raiz.iter(f'{{{SII}}}Documento'):
                primera = doc.find('s:Referencia', NS)
                self.assertEqual(primera.findtext('s:TpoDocRef', namespaces=NS), 'SET')
                self.assertTrue(primera.findtext('s:RazonRef', namespaces=NS).startswith('CASO 43295'))
        basico = raices[0]
        docs = list(basico.iter(f'{{{SII}}}Documento'))
        folio = lambda x: x.findtext('.//s:Folio', namespaces=NS)
        # El caso 2: descuentos por ítem de 4% y 14% sobre las cantidades del set.
        self.assertEqual(docs[1].findtext('.//s:MntNeto', namespaces=NS), str(483865 - 19355 + 216062 - 30249))
        # El caso 5 (NC que corrige giro) referencia el folio real de la factura del caso 1, con montos en cero.
        ref = docs[4].findall('s:Referencia', NS)[1]
        self.assertEqual((ref.findtext('s:TpoDocRef', namespaces=NS), ref.findtext('s:FolioRef', namespaces=NS),
                          ref.findtext('s:CodRef', namespaces=NS)), ('33', folio(docs[0]), '2'))
        self.assertEqual(docs[4].findtext('.//s:MntTotal', namespaces=NS), '0')
        # El caso 6 (devolución) usa el precio y el descuento de la factura original.
        self.assertEqual(docs[5].findtext('s:Detalle/s:PrcItem', namespaces=NS), '2059')
        self.assertEqual(docs[5].findtext('s:Detalle/s:DescuentoPct', namespaces=NS), '4')
        # El caso 8 (ND) anula la NC del caso 5.
        ref = docs[7].findall('s:Referencia', NS)[1]
        self.assertEqual((ref.findtext('s:TpoDocRef', namespaces=NS), ref.findtext('s:FolioRef', namespaces=NS)),
                         ('61', folio(docs[4])))
        # Guía de traslado interno: el receptor es la misma empresa.
        guia = next(raices[1].iter(f'{{{SII}}}Documento'))
        self.assertEqual(guia.findtext('.//s:RUTRecep', namespaces=NS), '76000000-0')
        # Exenta y su nota: sin IVA.
        exentas = list(raices[2].iter(f'{{{SII}}}Documento'))
        self.assertIsNone(exentas[1].find('.//s:IVA', NS))
        self.assertEqual(exentas[1].findtext('.//s:MntExe', namespaces=NS), str(3 * 6390))
        # Facturas con receptores distintos.
        ruts = [d.findtext('.//s:RUTRecep', namespaces=NS) for d in docs[:4]]
        self.assertEqual(len(set(ruts)), 4)

    def test_el_motor_no_toma_los_envios_de_la_certificacion(self):
        self._generar('set')
        with mock.patch.object(motor, 'cliente', return_value=SIIFalso()):
            self.assertEqual(motor.procesar(), 0)

    def test_libros_de_ventas_compras_y_guias(self):
        self._generar('set')
        libros = list(self._generar('libros', guias_anuladas=['4329505-3']))
        self.assertEqual([e.proposito for e in libros],
                         [EnvioSII.LIBRO_VENTAS, EnvioSII.LIBRO_COMPRAS, EnvioSII.LIBRO_GUIAS])
        ventas, compras, guias = [leer(e.xml.encode('iso-8859-1')) for e in libros]
        self.assertEqual(validar(ventas, 'LibroCompraVenta'), [])
        self.assertEqual(validar(compras, 'LibroCompraVenta'), [])
        self.assertEqual(validar(guias, 'LibroGuia'), [])
        self.assertEqual(ventas.findtext('.//s:FolioNotificacion', namespaces=NS), '1')
        self.assertEqual(compras.findtext('.//s:FolioNotificacion', namespaces=NS), '2')
        self.assertEqual(len(ventas.findall('.//s:EnvioLibro/s:Detalle', NS)), 11)  # 8 del básico + 3 exentas
        self.assertEqual(compras.findtext('.//s:FctProp', namespaces=NS), '0.6')
        self.assertTrue(compras.findtext('.//s:TotIVAUsoComun', namespaces=NS))
        self.assertEqual(guias.findtext('.//s:TotGuiaAnulada', namespaces=NS), '1')

    def test_simulacion_sin_referencias_set(self):
        sim = self._generar('simulacion', cantidad=12)[0]
        raiz = envio.revisar(sim.xml.encode('iso-8859-1'), cafs=self._cafs())
        self.assertEqual(len(list(raiz.iter(f'{{{SII}}}Documento'))), 12)
        self.assertNotIn('SET', raiz.xpath('//s:TpoDocRef/text()', namespaces=NS))
        r = self.client.post(f'{self.cert_url}/generar/', {'que': 'simulacion', 'cantidad': 5}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_subir_y_consultar_hasta_aceptado(self):
        self._generar('set')
        self._generar('libros')
        falso = SIILibros()
        with mock.patch.object(motor, 'cliente', return_value=falso):
            r = self.client.post(f'{self.cert_url}/subir/')
            self.assertEqual(len(r.data['subidos']), 6)
            r = self.client.post(f'{self.cert_url}/consultar/')
        self.assertEqual({e['estado'] for e in r.data['envios']}, {EnvioSII.ACEPTADO})
        self.assertEqual(len(r.data['aceptados']), 6)
        self.assertEqual(DocumentoEmitido.objects.filter(estado=DocumentoEmitido.ACEPTADO).count(), 14)

    def test_libro_rechazado_y_set_con_reparos(self):
        self._generar('set')
        self._generar('libros')
        falso = SIILibros(estado_dte='RPR', estado_libro='LRH')
        with mock.patch.object(motor, 'cliente', return_value=falso):
            certificacion.subir_pendientes(self.org)
            certificacion.consultar(self.org)
        estados = dict(EnvioSII.objects.values_list('proposito', 'estado').distinct())
        self.assertEqual(estados[EnvioSII.LIBRO_VENTAS], EnvioSII.RECHAZADO)
        self.assertEqual(estados[EnvioSII.SET_PRUEBAS], EnvioSII.REPAROS)

    def test_faltan_folios_dice_cuales(self):
        from .models import Caf
        Caf.objects.filter(organization=self.org, tipo=56).delete()
        r = self.client.post(f'{self.cert_url}/generar/', {'que': 'set'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('nota de débito', r.data['detail'])
        self.assertFalse(DocumentoEmitido.objects.exists())

    def test_estado_y_pasos(self):
        r = self.client.get(f'{self.cert_url}/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['paso'], ProcesoCertificacion.SET_PRUEBAS)
        self.assertEqual([p['clave'] for p in r.data['pasos']][:2], ['postulacion', 'set_pruebas'])
        self.assertTrue(r.data['pasos'][0]['listo'])
        self.assertTrue(r.data['pasos'][1]['usted'])
        self.assertEqual(r.data['sets'][0]['casos'][0]['caso'], '4329504-1')
        r = self.client.post(f'{self.cert_url}/paso/', {'paso': 'terminado'}, format='json')
        self.assertEqual(r.data['paso'], 'terminado')
        from .models import ConfiguracionDTE
        self.assertEqual(ConfiguracionDTE.de(self.org).camino, ConfiguracionDTE.YA_EMISOR)

    def test_solo_el_administrador_carga_y_genera(self):
        self.client.force_authenticate(self.editor)
        self.assertEqual(self.client.post(f'{self.cert_url}/set/', {'texto': SET}, format='json').status_code, 403)
        self.assertEqual(self.client.get(f'{self.cert_url}/').status_code, 200)

    def test_xml_del_envio(self):
        e = self._generar('set')[0]
        r = self.client.get(f'{self.cert_url}/envios/{e.id}/xml/')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b'<?xml version="1.0" encoding="ISO-8859-1"?>'))
