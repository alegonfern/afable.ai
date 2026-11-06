"""El certificado digital (.pfx / .p12) de la persona que firma por la empresa.

El SII lo usa para dos cosas: firmar cada DTE y el envío (XMLDSig, RSA-SHA1) y autenticarse en sus
servicios (la semilla firmada). El RUT del titular viene en el certificado, en el nombre alternativo
de OID 1.3.6.1.4.1.8321.1 que ponen las autoridades certificadoras chilenas.
"""
import re
from datetime import datetime, timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

from . import ErrorDTE
from . import rut as ruts
from .xmlutil import b64, entero_b64

OID_RUT = x509.ObjectIdentifier('1.3.6.1.4.1.8321.1')


class ErrorCertificado(ErrorDTE):
    pass


def _rut_de_othername(valor):
    """El valor del otherName viene en DER: [0] explícito con un IA5String adentro (o directo)."""
    i = 0
    while i < len(valor) and valor[i] in (0xA0, 0x30):
        largo = valor[i + 1]
        i += 2 + (largo - 0x80 if largo & 0x80 else 0)
    if i < len(valor) and valor[i] in (0x16, 0x0C, 0x13):
        largo = valor[i + 1]
        return valor[i + 2:i + 2 + largo].decode('latin-1')
    return None


class Certificado:
    def __init__(self, llave, cert):
        if not isinstance(llave, rsa.RSAPrivateKey):
            raise ErrorCertificado('El certificado no tiene llave RSA: el SII solo acepta firmas RSA.')
        self.llave, self.cert = llave, cert

    @classmethod
    def desde_pfx(cls, datos, clave):
        try:
            llave, cert, _ = pkcs12.load_key_and_certificates(datos, (clave or '').encode() or None)
        except ValueError:
            raise ErrorCertificado('No se pudo abrir el certificado: la clave no es correcta o el archivo no es un .pfx/.p12.')
        if llave is None or cert is None:
            raise ErrorCertificado('El archivo no trae el certificado con su llave privada. Exporte el .pfx incluyendo la llave.')
        return cls(llave, cert)

    @property
    def rut(self):
        """El RUT del titular, o None si el certificado no lo trae."""
        try:
            san = self.cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
            for nombre in san.get_values_for_type(x509.OtherName):
                if nombre.type_id == OID_RUT:
                    valor = _rut_de_othername(nombre.value)
                    if valor and ruts.valido(valor):
                        return ruts.normalizar(valor)
        except x509.ExtensionNotFound:
            pass
        for atributo in self.cert.subject:
            m = re.search(r'\d{1,2}\.?\d{3}\.?\d{3}-[\dkK]', str(atributo.value))
            if m and ruts.valido(m.group(0)):
                return ruts.normalizar(m.group(0))
        return None

    @property
    def nombre(self):
        cn = self.cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        return cn[0].value if cn else self.cert.subject.rfc4514_string()

    @property
    def correo(self):
        em = self.cert.subject.get_attributes_for_oid(NameOID.EMAIL_ADDRESS)
        return em[0].value if em else ''

    @property
    def emisor(self):
        cn = self.cert.issuer.get_attributes_for_oid(NameOID.COMMON_NAME)
        return cn[0].value if cn else self.cert.issuer.rfc4514_string()

    @property
    def valido_desde(self):
        return self.cert.not_valid_before_utc

    @property
    def valido_hasta(self):
        return self.cert.not_valid_after_utc

    def vigente(self, ahora=None):
        ahora = ahora or datetime.now(timezone.utc)
        return self.valido_desde <= ahora <= self.valido_hasta

    def firmar(self, datos):
        return self.llave.sign(datos, padding.PKCS1v15(), hashes.SHA1())

    @property
    def modulo_b64(self):
        return entero_b64(self.llave.public_key().public_numbers().n)

    @property
    def exponente_b64(self):
        return entero_b64(self.llave.public_key().public_numbers().e)

    @property
    def cert_b64(self):
        return b64(self.cert.public_bytes(serialization.Encoding.DER))
