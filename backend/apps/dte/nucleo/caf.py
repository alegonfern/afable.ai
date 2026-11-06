"""El CAF: el archivo que entrega el SII al autorizar folios (ESPEC_SII.md §5.1).

Trae el rango de folios, la llave pública firmada por el SII y la llave privada con que se firma
el timbre de cada documento. El nodo <CAF> se copia sin cambios dentro de cada TED, por eso se
guarda el archivo original completo y se trabaja sobre su texto.
"""
import base64
import re
from datetime import date

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from lxml import etree

from . import ErrorDTE
from . import rut as ruts
from .xmlutil import SII, leer

# [NV] Desde 2016 el SII da por vencidos a los seis meses los folios de estos tipos que no se usaron;
# se usa solo para avisar, nunca para bloquear: si el SII lo rechaza, lo dirá al enviar.
TIPOS_QUE_VENCEN = {33, 34, 43, 46, 52, 56, 61}


class Caf:
    def __init__(self, xml):
        if isinstance(xml, str):
            xml = xml.encode('iso-8859-1')
        self.xml = xml
        try:
            raiz = leer(xml)
        except Exception:
            raise ErrorDTE('El archivo no es un CAF: no se pudo leer como XML.')
        if raiz.tag != 'AUTORIZACION' or raiz.find('CAF/DA') is None:
            raise ErrorDTE('El archivo no es un CAF del SII (falta AUTORIZACION/CAF/DA).')
        da = raiz.find('CAF/DA')
        self.rut = ruts.normalizar(da.findtext('RE'))
        self.razon_social = da.findtext('RS') or ''
        self.tipo = int(da.findtext('TD'))
        self.desde = int(da.findtext('RNG/D'))
        self.hasta = int(da.findtext('RNG/H'))
        self.fecha_autorizacion = date.fromisoformat(da.findtext('FA'))
        self.idk = int(da.findtext('IDK') or 0)
        modulo = int.from_bytes(base64.b64decode(da.findtext('RSAPK/M')), 'big')
        exponente = int.from_bytes(base64.b64decode(da.findtext('RSAPK/E')), 'big')
        self.llave_publica = rsa.RSAPublicNumbers(exponente, modulo).public_key()
        try:
            self._llave = serialization.load_pem_private_key((raiz.findtext('RSASK') or '').strip().encode(), None)
        except Exception:
            raise ErrorDTE('El CAF no trae una llave privada válida (RSASK). Descárguelo de nuevo desde el SII.')
        pub = self._llave.public_key().public_numbers()
        if (pub.n, pub.e) != (modulo, exponente):
            raise ErrorDTE('El CAF está alterado: la llave privada no corresponde a la llave pública autorizada.')
        texto = xml.decode('iso-8859-1')
        m = re.search(r'<CAF\b.*?</CAF>', texto, re.S)
        # El <CAF> tal como viene, sin el espacio entre tags: así va al mensaje que firma el timbre.
        self.caf_plano = re.sub(r'>\s+<', '><', m.group(0).strip())

    @property
    def certificacion(self):
        """Los CAF del ambiente de certificación los firma la llave 100 del SII."""
        return self.idk == 100

    @property
    def cantidad(self):
        return self.hasta - self.desde + 1

    def contiene(self, folio):
        return self.desde <= int(folio) <= self.hasta

    @property
    def vence(self):
        if self.tipo not in TIPOS_QUE_VENCEN:
            return None
        f = self.fecha_autorizacion
        mes = f.month + 6
        anio, mes = f.year + (mes - 1) // 12, (mes - 1) % 12 + 1
        try:
            return f.replace(year=anio, month=mes)
        except ValueError:
            return f.replace(year=anio, month=mes, day=28)

    def firmar(self, mensaje):
        """SHA1withRSA con la llave del CAF: la firma (FRMT) del timbre."""
        return self._llave.sign(mensaje, padding.PKCS1v15(), hashes.SHA1())

    def verificar(self, mensaje, firma):
        try:
            self.llave_publica.verify(firma, mensaje, padding.PKCS1v15(), hashes.SHA1())
            return True
        except Exception:
            return False

    def copiar_en(self, padre):
        """Copia el <CAF> dentro de `padre` (el DD), con los mismos textos y atributos, en el
        namespace del SII. Se arma dentro del árbol para no arrastrar declaraciones de namespace."""
        def copiar(origen, destino):
            el = etree.SubElement(destino, f'{{{SII}}}{origen.tag}', dict(origen.attrib))
            el.text = origen.text if len(origen) == 0 else None
            for hijo in origen:
                copiar(hijo, el)
        copiar(leer(self.caf_plano.encode('iso-8859-1')), padre)
