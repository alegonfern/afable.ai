"""El PDF de los DTE (pdf.py): sale del XML firmado, con el recuadro del SII, el timbre PDF417
que decodifica al TED, y el acuse de recibo en la copia cedible."""
import io
from datetime import date
from unittest import mock

from pypdf import PdfReader

from apps.comercial import emision

from . import motor, pdf, servicio
from .models import ConfiguracionDTE, DocumentoEmitido
from .nucleo import documento as d
from .nucleo.xmlutil import leer
from .tests import SIIFalso, _BaseDTE, caf_de_prueba


def _texto(contenido):
    return '\n'.join(pag.extract_text() for pag in PdfReader(io.BytesIO(contenido)).pages)


class PdfTests(_BaseDTE):
    def setUp(self):
        super().setUp()
        self._alta()
        with mock.patch.object(motor, 'cliente', return_value=SIIFalso()):
            self.doc = emision.emitir(self._orden(), usuario=self.editor)
        self.emitido = DocumentoEmitido.objects.get(organization=self.org)

    def test_pdf_con_recuadro_detalle_totales_y_leyendas(self):
        texto = _texto(pdf.generar(self.emitido))
        for esperado in ('R.U.T.: 76.000.000-0', 'FACTURA ELECTRÓNICA', 'N° 1', 'S.I.I. - PROVIDENCIA',
                         'Constructora Andes', '77.111.222-6', 'Saco de cemento', '$95.200', 'I.V.A. 19%',
                         'Timbre Electrónico SII', 'Res. 0 de 2026 - Verifique documento: www.sii.cl'):
            self.assertIn(esperado, texto)
        self.assertNotIn('CEDIBLE', texto)

    def test_el_logo_de_la_empresa_sale_en_la_factura(self):
        """El logo que se elige en Ajustes › Empresas › Datos y logo es el que se imprime en sus documentos."""
        import tempfile
        from django.test import override_settings
        with tempfile.TemporaryDirectory() as carpeta, override_settings(MEDIA_ROOT=carpeta):
            self._logo_en_la_factura()

    def _logo_en_la_factura(self):
        from django.core.files.base import ContentFile
        from PIL import Image as Imagen

        def imagenes(datos):
            return sum(len(pag.images) for pag in PdfReader(io.BytesIO(datos)).pages)

        sin_logo = imagenes(pdf.generar(self.emitido))  # solo el timbre
        png = io.BytesIO()
        Imagen.new('RGB', (300, 100), (200, 16, 46)).save(png, 'PNG')
        self.org.logo.save('logo.png', ContentFile(png.getvalue()), save=True)
        self.emitido.refresh_from_db()
        self.assertEqual(imagenes(pdf.generar(self.emitido)), sin_logo + 1)
        # Y también en la cotización o la orden de venta.
        from apps.comercial import pdf as pdf_pedido
        self.assertEqual(imagenes(pdf_pedido.generar(self.doc.pedidos.first().pedido)), 1)
        self.org.logo.delete(save=True)

    def test_cedible_trae_el_acuse_de_recibo(self):
        texto = _texto(pdf.generar(self.emitido, cedible=True))
        self.assertIn('CEDIBLE', texto)
        self.assertIn('Ley 19.983', texto)
        self.assertIn('Recinto:', texto)

    def test_notas_no_llevan_cedible(self):
        self.assertFalse(pdf.admite_cedible(61))
        self.assertFalse(pdf.admite_cedible(52, '5'))
        self.assertTrue(pdf.admite_cedible(52, '1'))

    def test_el_pdf417_decodifica_al_ted(self):
        try:
            import zxingcpp
        except ImportError:
            self.skipTest('zxing-cpp no está instalado (solo se usa para comprobar el código de barras)')
        datos = pdf.ted_plano(leer(self.emitido.xml.encode('iso-8859-1')))
        self.assertTrue(datos.startswith(b'<TED version="1.0"><DD><RE>76000000-0</RE>'))
        leidos = zxingcpp.read_barcodes(pdf.Timbre(datos).imagen)
        self.assertEqual(len(leidos), 1)
        self.assertEqual(leidos[0].bytes, datos)

    def test_por_la_api_y_desde_ventas(self):
        r = self.client.get(f'{self.dte}/documentos/{self.emitido.id}/pdf/?cedible=1')
        self.assertEqual((r.status_code, r['Content-Type']), (200, 'application/pdf'))
        self.assertIn('DTE-33-1-cedible.pdf', r['Content-Disposition'])
        r = self.client.get(f'{self.base}/facturas/{self.doc.id}/pdf/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('Timbre Electrónico SII', _texto(r.content))
        self.assertNotIn('ENTORNO DE PRUEBA', _texto(r.content))


def _plano(contenido):
    """El texto del PDF en una sola línea: los nombres largos se parten dentro del recuadro."""
    return ' '.join(_texto(contenido).split())


class TiposPdfTests(_BaseDTE):
    """Cada tipo de documento sale como pide el manual de muestras impresas."""

    def setUp(self):
        super().setUp()
        self._alta()
        for tipo in (34, 52, 56, 61):
            servicio.cargar_caf(self.org, caf_de_prueba('76000000-0', tipo=tipo))
        self.parche = mock.patch.object(motor, 'cliente', return_value=SIIFalso())
        self.parche.start()
        self.receptor = d.Receptor(rut='77111222-6', razon_social='Constructora Andes Ltda', giro='Construcción',
                                   direccion='Los Militares 5001', comuna='Las Condes', ciudad='Santiago')

    def tearDown(self):
        self.parche.stop()
        super().tearDown()

    def _emitir(self, tipo, lineas, **extra):
        doc = d.Documento(tipo=tipo, folio=None, fecha=date(2026, 10, 26), emisor=servicio.emisor(self.org),
                          receptor=extra.pop('receptor', self.receptor), lineas=lineas, **extra)
        return servicio.emitir(self.org, doc)

    def test_exenta_sin_neto_ni_iva(self):
        texto = _plano(pdf.generar(self._emitir(34, [d.Linea('Asesoría contable', cantidad=1, precio=150000)])))
        self.assertIn('FACTURA NO AFECTA O EXENTA ELECTRÓNICA', texto)
        self.assertIn('Monto exento', texto)
        self.assertNotIn('Monto neto', texto)
        self.assertNotIn('I.V.A.', texto)

    def test_notas_con_su_referencia_y_razon(self):
        factura = self._emitir(33, [d.Linea('Saco de cemento', cantidad=10, precio=6000)])
        nc = servicio.emitir_nota(self.org, factura, 61, d.CORRIGE_MONTOS, 'Devolución de 2 sacos',
                                  [{'nombre': 'Saco de cemento', 'cantidad': 2, 'precio': 6000}])
        texto = _plano(pdf.generar(nc))
        for esperado in ('NOTA DE CRÉDITO ELECTRÓNICA', 'Factura electrónica', 'Corrige montos · Devolución de 2 sacos',
                         '$14.280'):
            self.assertIn(esperado, texto)
        nd = servicio.emitir_nota(self.org, factura, 56, d.CORRIGE_MONTOS, 'Intereses por mora',
                                  [{'nombre': 'Intereses', 'cantidad': 1, 'precio': 2500}])
        texto = _plano(pdf.generar(nd))
        self.assertIn('NOTA DE DÉBITO ELECTRÓNICA', texto)
        self.assertIn('Intereses por mora', texto)
        self.assertNotIn('CEDIBLE', _plano(pdf.generar(nd, cedible=True)))

    def test_guia_de_venta_con_transporte_y_cedible_con_su_factura(self):
        guia = self._emitir(52, [d.Linea('Saco de cemento', cantidad=20, precio=6000)], indicador_traslado=1,
                            transporte=d.Transporte(patente='AB1234', rut_chofer='11111111-1', nombre_chofer='Juan Soto',
                                                    direccion_destino='Los Militares 5001', comuna_destino='Las Condes'))
        texto = _plano(pdf.generar(guia, cedible=True))
        for esperado in ('GUÍA DE DESPACHO ELECTRÓNICA', 'Operación constituye venta', 'Patente: AB1234',
                         'Juan Soto', 'Destino: Los Militares 5001, Las Condes', 'CEDIBLE CON SU FACTURA'):
            self.assertIn(esperado, texto)

    def test_guia_de_traslado_interno_sin_cedible(self):
        propia = d.Receptor(rut='76000000-0', razon_social='Ferretería Ejemplo SpA', giro='Ferretería',
                            direccion='Bodega 2', comuna='Quilicura')
        guia = self._emitir(52, [d.Linea('Saco de cemento', cantidad=50, precio=4000)], indicador_traslado=5,
                            receptor=propia)
        texto = _plano(pdf.generar(guia, cedible=True))
        self.assertIn('Traslados internos', texto)
        self.assertNotIn('CEDIBLE', texto)

    def test_oficina_del_sii_configurada(self):
        cfg = ConfiguracionDTE.de(self.org)
        cfg.oficina_sii = 'Santiago Oriente'
        cfg.save()
        emitido = self._emitir(33, [d.Linea('Flete', cantidad=1, precio=20000)])
        self.assertIn('S.I.I. - SANTIAGO ORIENTE', _plano(pdf.generar(emitido)))
        self.assertIn('S.I.I. - MAIPÚ', _plano(pdf.generar(emitido, oficina='Maipú')))

    def test_sesenta_lineas_pasan_a_otra_pagina_con_timbre_y_totales_enteros(self):
        lineas = [d.Linea(f'Producto número {i}', cantidad=i, precio=1000 + i) for i in range(1, 61)]
        emitido = self._emitir(33, lineas)
        paginas = [pag.extract_text() for pag in PdfReader(io.BytesIO(pdf.generar(emitido))).pages]
        self.assertGreaterEqual(len(paginas), 2)
        self.assertIn('Producto número 60', '\n'.join(paginas))
        # El encabezado de columnas se repite, y el timbre y los totales quedan juntos en la última.
        self.assertIn('Precio unit.', paginas[1])
        self.assertIn('página 2', paginas[1])
        ultima = paginas[-1]
        for esperado in ('Timbre Electrónico SII', 'Total', f'${emitido.monto_total:,}'.replace(',', '.')):
            self.assertIn(esperado, ultima)
        self.assertNotIn('Timbre Electrónico SII', '\n'.join(paginas[:-1]))
