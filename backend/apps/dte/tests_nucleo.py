"""Pruebas del núcleo del facturador (apps/dte/nucleo), sin base de datos ni red.

El ancla son los dos timbres oficiales del SII: el del manual de certificación (§5.2) y el del
EnvioDTE de ejemplo F60T33. Las firmas XMLDSig se prueban con un certificado generado acá y se
verifican también con signxml (otra implementación) cuando está instalada.
"""
import base64
import hashlib
import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from lxml import etree

from apps.dte.nucleo import ErrorDTE, documento as d, envio, firma, rut, ted
from apps.dte.nucleo.caf import Caf
from apps.dte.nucleo.certificado import OID_RUT, Certificado, ErrorCertificado
from apps.dte.nucleo.esquemas import validar
from apps.dte.nucleo.xmlutil import SII, leer, texto

PRUEBAS = Path(__file__).parent / 'nucleo' / 'pruebas'
NS = {'s': SII}


def caf_ejemplo():
    return Caf((PRUEBAS / 'caf_33_ejemplo_sii.xml').read_bytes())


def pfx_de_prueba(rut_titular='7880442-4', clave='secreta', dias=365):
    """Un .pfx autofirmado con el RUT en el otherName 1.3.6.1.4.1.8321.1, como los chilenos."""
    llave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nombre = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Firmante de Prueba'),
                        x509.NameAttribute(NameOID.EMAIL_ADDRESS, 'firma@afable.test')])
    numero, digito = rut_titular.split('-')
    ia5 = numero.zfill(8).encode() + b'-' + digito.encode()
    valor = bytes([0xA0, len(ia5) + 2, 0x16, len(ia5)]) + ia5
    ahora = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(nombre).issuer_name(nombre).public_key(llave.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(ahora - timedelta(days=1))
            .not_valid_after(ahora + timedelta(days=dias))
            .add_extension(x509.SubjectAlternativeName([x509.OtherName(OID_RUT, valor)]), critical=False)
            .sign(llave, hashes.SHA256()))
    return pkcs12.serialize_key_and_certificates(b'firma', llave, cert, None,
                                                 serialization.BestAvailableEncryption(clave.encode()))


EMISOR = d.Emisor(rut='97975000-5', razon_social='RUT DE PRUEBA', giro='Insumos de Computacion', actecos=['726000'],
                  direccion='Teatinos 120, Piso 4', comuna='Santiago', ciudad='Santiago')
RECEPTOR = d.Receptor(rut='77777777-7', razon_social='EMPRESA  LTDA', giro='COMPUTACION', direccion='SAN DIEGO 2222',
                      comuna='LA FLORIDA', ciudad='SANTIAGO')


def factura_f60():
    """Los datos del EnvioDTE de ejemplo del SII (F60T33)."""
    return d.Documento(tipo=33, folio=60, fecha=date(2003, 10, 13), emisor=EMISOR, receptor=RECEPTOR, lineas=[
        d.Linea('Parlantes Multimedia 180W.', cantidad=20, precio=4500, codigo='011'),
        d.Linea('Mouse Inalambrico PS/2', cantidad=1, precio=5000, codigo='0231'),
        d.Linea('Caja de Diskettes 10 Unidades', cantidad=5, precio=1000, codigo='1515'),
    ])


class RutTest(unittest.TestCase):
    def test_normaliza_y_valida(self):
        self.assertEqual(rut.normalizar('97.975.000-5'), '97975000-5')
        self.assertEqual(rut.normalizar('60803000k'), '60803000-K')
        self.assertEqual(rut.dv(7880442), '4')
        with self.assertRaises(ErrorDTE):
            rut.normalizar('97975000-4')


class TimbreOficialTest(unittest.TestCase):
    """El timbre se reproduce bit a bit contra los ejemplos publicados por el SII."""

    def test_caf_ejemplo_se_lee_y_su_llave_calza(self):
        caf = caf_ejemplo()
        self.assertEqual((caf.rut, caf.tipo, caf.desde, caf.hasta, caf.idk), ('97975000-5', 33, 1, 200, 100))
        self.assertTrue(caf.certificacion)
        self.assertTrue(caf.caf_plano.startswith('<CAF version="1.0"><DA><RE>97975000-5</RE>'))

    def test_firma_del_manual_de_certificacion(self):
        caf = caf_ejemplo()
        msj = ted.mensaje('97975000-5', 33, 27, '2003-09-08', '8414240-9', 'JORGE GONZALEZ LTDA', 502946,
                          'Cajon AFECTO', caf.caf_plano, '2003-09-08T12:28:31')
        esperado = ('pqjXHHQLJmyFPMRvxScN7tYHvIsty0pqL2LLYaG43jMmnfiZfllLA0wb32lP+HBJ'
                    '/tf8nziSeorvjlx410ZImw==')
        self.assertEqual(base64.b64encode(caf.firmar(msj)).decode(), esperado)

    def test_factura_f60_del_ejemplo_oficial(self):
        dte = d.construir(factura_f60(), caf_ejemplo(), datetime(2003, 10, 13, 9, 33, 20))
        frmt = dte.findtext('.//s:FRMT', namespaces=NS)
        self.assertEqual(frmt, 'GbmDcS9e/jVC2LsLIe1iRV12Bf6lxsILtbQiCkh6mbjckFCJ7fj/kakFTS06Jo8iS4HXvJj3oYZuey53Krniew==')
        self.assertEqual(dte.findtext('.//s:MntTotal', namespaces=NS), '119000')

    def test_verifica_el_timbre_del_xml_oficial(self):
        raiz = leer((PRUEBAS / 'F60T33-ejemplo.xml').read_bytes())
        self.assertTrue(ted.verificar(raiz.find('.//s:TED', NS), caf_ejemplo()))

    def test_c14n_calza_con_el_digest_oficial_del_setdoc(self):
        """El digest del SetDoc del ejemplo del SII se reproduce con nuestro C14N (con el xsi
        heredado). Con tostring(method='c14n') de libxml2 no calza: emite xmlns="" de más."""
        raiz = leer((PRUEBAS / 'F60T33-ejemplo.xml').read_bytes())
        setdoc = raiz.find('s:SetDTE', NS)
        digest = base64.b64encode(hashlib.sha1(firma.c14n(setdoc)).digest()).decode()
        oficial = raiz.xpath('//ds:Reference[@URI="#SetDoc"]/ds:DigestValue/text()',
                             namespaces={'ds': 'http://www.w3.org/2000/09/xmldsig#'})[0]
        self.assertEqual(digest, oficial)
        self.assertNotIn(b'xmlns=""', firma.c14n(setdoc))


class CafTest(unittest.TestCase):
    def test_rechaza_llave_que_no_calza(self):
        xml = (PRUEBAS / 'caf_33_ejemplo_sii.xml').read_text()
        otra = rsa.generate_private_key(public_exponent=3, key_size=1024).private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption()).decode()
        inicio, fin = xml.index('-----BEGIN'), xml.index('</RSASK>')
        with self.assertRaisesRegex(ErrorDTE, 'alterado'):
            Caf(xml[:inicio] + otra + xml[fin:])

    def test_rechaza_lo_que_no_es_caf(self):
        with self.assertRaises(ErrorDTE):
            Caf(b'<hola/>')

    def test_folio_fuera_de_rango_y_otro_tipo(self):
        doc = factura_f60()
        doc.folio = 201
        with self.assertRaisesRegex(ErrorDTE, 'no está en el CAF'):
            d.construir(doc, caf_ejemplo())
        doc = factura_f60()
        doc.tipo = 34
        with self.assertRaisesRegex(ErrorDTE, 'tipo 33'):
            d.construir(doc, caf_ejemplo())


class CertificadoTest(unittest.TestCase):
    def test_lee_rut_nombre_y_vigencia(self):
        c = Certificado.desde_pfx(pfx_de_prueba(), 'secreta')
        self.assertEqual(c.rut, '7880442-4')
        self.assertEqual(c.nombre, 'Firmante de Prueba')
        self.assertTrue(c.vigente())

    def test_clave_incorrecta(self):
        with self.assertRaisesRegex(ErrorCertificado, 'clave no es correcta'):
            Certificado.desde_pfx(pfx_de_prueba(), 'otra')


class TotalesTest(unittest.TestCase):
    def test_descuentos_por_linea_y_global_y_exentos(self):
        doc = d.Documento(tipo=33, folio=1, fecha=date(2026, 10, 26), emisor=EMISOR, receptor=RECEPTOR, lineas=[
            d.Linea('Servicio', cantidad=Decimal('2.5'), precio=Decimal('1000.4'), descuento_pct=10),
            d.Linea('Libro', cantidad=1, precio=3000, exento=True),
        ], descuentos=[d.DescuentoGlobal(valor=5, glosa='Cliente frecuente')])
        t = d.totales(doc)
        # 2,5 x 1000,4 = 2501; 10% = 250,1 -> 250; línea 2251; 5% global = 112,55 -> 113; neto 2138
        self.assertEqual((t.neto, t.exento, t.iva, t.total), (2138, 3000, 406, 5544))

    def test_33_todo_exento_pide_34(self):
        doc = factura_f60()
        for linea in doc.lineas:
            linea.exento = True
        with self.assertRaisesRegex(ErrorDTE, '34'):
            d.validar(doc)

    def test_nota_sin_referencia(self):
        doc = factura_f60()
        doc.tipo = 61
        with self.assertRaisesRegex(ErrorDTE, 'documento que modifica'):
            d.validar(doc)

    def test_texto_solo_iso_8859_1(self):
        self.assertEqual(texto('“Café” — ñandú 🚀'), '"Café" - ñandú')
        self.assertEqual(texto('x' * 50, 40), 'x' * 40)


class EnvioTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cert = Certificado.desde_pfx(pfx_de_prueba(), 'secreta')
        cls.caratula = envio.Caratula(rut_emisor='97975000-5', rut_envia='7880442-4',
                                      fecha_resolucion=date(2003, 9, 2), numero_resolucion=0)

    def _caf(self, tipo):
        """El CAF oficial es de 33; para otros tipos se arma uno igual con su TD (sin la firma
        del SII, que el núcleo no verifica)."""
        xml = (PRUEBAS / 'caf_33_ejemplo_sii.xml').read_text().replace('<TD>33</TD>', f'<TD>{tipo}</TD>')
        return Caf(xml)

    def test_envio_completo_valida_esquema_firmas_y_timbres(self):
        momento = datetime(2026, 10, 26, 10, 15, 0)
        dtes = [d.construir(factura_f60(), caf_ejemplo(), momento)]
        exenta = d.Documento(tipo=34, folio=7, fecha=date(2026, 10, 26), emisor=EMISOR, receptor=RECEPTOR,
                             lineas=[d.Linea('Asesoría exenta', cantidad=1, precio=150000)], forma_pago=2,
                             fecha_vencimiento=date(2026, 11, 25))
        dtes.append(d.construir(exenta, self._caf(34), momento))
        nc = d.Documento(tipo=61, folio=3, fecha=date(2026, 10, 26), emisor=EMISOR, receptor=RECEPTOR,
                         lineas=[d.Linea('Parlantes Multimedia 180W.', cantidad=2, precio=4500)],
                         referencias=[d.Referencia('33', '60', date(2003, 10, 13), codigo=d.CORRIGE_MONTOS,
                                                   razon='Devolución de 2 unidades')])
        dtes.append(d.construir(nc, self._caf(61), momento))
        nd = d.Documento(tipo=56, folio=4, fecha=date(2026, 10, 26), emisor=EMISOR, receptor=RECEPTOR,
                         lineas=[d.Linea('Intereses por mora', cantidad=1, precio=2500)],
                         referencias=[d.Referencia('33', '60', date(2003, 10, 13), codigo=d.CORRIGE_MONTOS,
                                                   razon='Intereses')])
        dtes.append(d.construir(nd, self._caf(56), momento))
        guia = d.Documento(tipo=52, folio=9, fecha=date(2026, 10, 26), emisor=EMISOR, receptor=RECEPTOR,
                           lineas=[d.Linea('Parlantes Multimedia 180W.', cantidad=20, precio=4500)],
                           indicador_traslado=1, transporte=d.Transporte(
                               patente='AB1234', direccion_destino='San Diego 2222', comuna_destino='La Florida'))
        dtes.append(d.construir(guia, self._caf(52), momento))

        datos = envio.armar(dtes, self.caratula, self.cert, momento)

        self.assertTrue(datos.startswith(
            b'<?xml version="1.0" encoding="ISO-8859-1"?>\n<EnvioDTE xmlns="http://www.sii.cl/SiiDte" '
            b'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            b'xsi:schemaLocation="http://www.sii.cl/SiiDte EnvioDTE_v10.xsd" version="1.0">\n'))
        raiz = leer(datos)
        self.assertEqual(validar(raiz, 'EnvioDTE'), [])
        self.assertEqual([ok for _, ok, _ in firma.verificar(raiz)], [True] * 6)
        cafs = {('97975000-5', t): (caf_ejemplo() if t == 33 else self._caf(t)) for t in (33, 34, 52, 56, 61)}
        envio.revisar(datos, cafs=cafs)
        self.assertEqual(raiz.xpath('//s:SubTotDTE/s:TpoDTE/text()', namespaces=NS), ['33', '34', '61', '56', '52'])
        # No quedan prefijos inventados ni declaraciones sueltas en los DTE.
        self.assertNotIn(b'ns0:', datos)
        self.assertEqual(datos.count(b'xmlns:xsi='), 1)

    def test_firma_cambia_si_se_toca_el_contenido(self):
        datos = envio.armar([d.construir(factura_f60(), caf_ejemplo())], self.caratula, self.cert)
        adulterado = datos.replace(b'<MntTotal>119000</MntTotal>', b'<MntTotal>119001</MntTotal>')
        with self.assertRaisesRegex(ErrorDTE, 'Firma inválida'):
            envio.revisar(adulterado, validar_esquema=False)

    def test_certificado_de_otra_persona(self):
        car = envio.Caratula(rut_emisor='97975000-5', rut_envia='11111111-1', fecha_resolucion=date(2003, 9, 2),
                             numero_resolucion=0)
        with self.assertRaisesRegex(ErrorDTE, 'certificado es de'):
            envio.armar([d.construir(factura_f60(), caf_ejemplo())], car, self.cert)

    def test_dte_suelto_conserva_su_firma_y_se_reenvia(self):
        datos = envio.armar([d.construir(factura_f60(), caf_ejemplo())], self.caratula, self.cert)
        suelto = envio.dte_suelto(envio.dtes_de(datos)[0])
        self.assertTrue(all(ok for _, ok, _ in firma.verificar(leer(suelto))))
        # Reenviado dentro de otro EnvioDTE (el intercambio con el cliente), la firma del DTE sigue válida.
        car = envio.Caratula(rut_emisor='97975000-5', rut_envia='7880442-4', fecha_resolucion=date(2003, 9, 2),
                             numero_resolucion=0, rut_receptor='77777777-7')
        otro = envio.armar([leer(suelto)], car, self.cert)
        self.assertEqual(len(firma.verificar(leer(otro))), 2)

    def test_firmas_verificadas_por_xmlsec(self):
        """Contraste con xmlsec (C14N por conjunto de nodos, como PHP/LibreDTE). signxml no sirve:
        usa el mismo camino de libxml2 que emite xmlns="" de más."""
        try:
            import xmlsec
        except ImportError:
            self.skipTest('xmlsec no está instalado (solo se usa para contrastar)')
        datos = envio.armar([d.construir(factura_f60(), caf_ejemplo())], self.caratula, self.cert)
        pem = self.cert.cert.public_bytes(serialization.Encoding.PEM)
        for xml in (datos, envio.dte_suelto(envio.dtes_de(datos)[0])):
            raiz = etree.fromstring(xml)
            xmlsec.tree.add_ids(raiz, ['ID'])
            for sig in raiz.iter('{http://www.w3.org/2000/09/xmldsig#}Signature'):
                ctx = xmlsec.SignatureContext()
                ctx.key = xmlsec.Key.from_memory(pem, xmlsec.constants.KeyDataFormatCertPem)
                ctx.verify(sig)  # lanza si no verifica


if __name__ == '__main__':
    unittest.main()
