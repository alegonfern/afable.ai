"""La firma XMLDSig con el perfil restringido del SII (ESPEC_SII.md §6).

C14N inclusivo, RSA-SHA1 y SHA-1 fijos, una sola Reference al ID del nodo firmado y KeyInfo con
KeyValue y X509Data. La firma se calcula con el nodo ya puesto en su árbol final: el C14N inclusivo
incluye los namespaces heredados y cualquier cambio posterior de contexto rompe el digest.
"""
import base64
import copy
import hashlib

from lxml import etree

from .xmlutil import DS

C14N = 'http://www.w3.org/TR/2001/REC-xml-c14n-20010315'
RSA_SHA1 = 'http://www.w3.org/2000/09/xmldsig#rsa-sha1'
SHA1 = 'http://www.w3.org/2000/09/xmldsig#sha1'


def _ds(padre, tag, texto=None, **attrs):
    el = etree.SubElement(padre, f'{{{DS}}}{tag}', **attrs) if padre is not None else \
        etree.Element(f'{{{DS}}}{tag}', nsmap={None: DS}, **attrs)
    if texto is not None:
        el.text = texto
    el.tail = '\n'
    return el


def c14n(nodo):
    """C14N 1.0 inclusivo de un nodo como "document subset": el nodo con todos sus namespaces en
    alcance declarados en él. No se usa tostring(nodo, method='c14n') porque libxml2 (2.11) emite
    xmlns="" en los descendientes de un subárbol cuando hay namespaces por defecto anidados, y el SII
    calcula otra cosa. Comprobado: así calza el digest del SetDoc del ejemplo oficial (tests_nucleo)."""
    copia = etree.Element(nodo.tag, attrib=dict(nodo.attrib), nsmap=nodo.nsmap)
    copia.text = nodo.text
    for hijo in nodo:
        copia.append(copy.deepcopy(hijo))
    return etree.tostring(etree.ElementTree(copia), method='c14n')


def _digest(nodo):
    return base64.b64encode(hashlib.sha1(c14n(nodo)).digest()).decode()


def firmar(nodo, certificado, despues_de=None):
    """Firma `nodo` (que debe tener atributo ID) con `certificado`. La Signature queda como hermana
    siguiente de `despues_de` (por defecto, del mismo nodo), con saltos de línea entre tags."""
    uri = nodo.get('ID')
    ancla = despues_de if despues_de is not None else nodo
    sig = _ds(None, 'Signature')
    sig.text = '\n'
    si = _ds(sig, 'SignedInfo')
    si.text = '\n'
    _ds(si, 'CanonicalizationMethod', Algorithm=C14N)
    _ds(si, 'SignatureMethod', Algorithm=RSA_SHA1)
    ref = _ds(si, 'Reference', URI=f'#{uri}')
    ref.text = '\n'
    trs = _ds(ref, 'Transforms')
    trs.text = '\n'
    _ds(trs, 'Transform', Algorithm=C14N)
    _ds(ref, 'DigestMethod', Algorithm=SHA1)
    dv = _ds(ref, 'DigestValue')
    sv = _ds(sig, 'SignatureValue')
    ki = _ds(sig, 'KeyInfo')
    ki.text = '\n'
    kv = _ds(ki, 'KeyValue')
    kv.text = '\n'
    rkv = _ds(kv, 'RSAKeyValue')
    rkv.text = '\n'
    _ds(rkv, 'Modulus', certificado.modulo_b64)
    _ds(rkv, 'Exponent', certificado.exponente_b64)
    xd = _ds(ki, 'X509Data')
    xd.text = '\n'
    _ds(xd, 'X509Certificate', certificado.cert_b64)

    # Primero al árbol, después los cálculos: así el C14N ve los mismos ancestros que verá el SII.
    sig.tail = ancla.tail
    ancla.tail = '\n'
    ancla.addnext(sig)
    dv.text = _digest(nodo)
    firma = certificado.firmar(c14n(si))
    sv.text = base64.b64encode(firma).decode()
    return sig


def firmar_documento(raiz, certificado):
    """Firma "enveloped" de todo el documento (Reference URI="" + transform enveloped-signature),
    como la pide el SII para la semilla. La Signature va al final de la raíz sin espacio alrededor:
    así el documento sin la firma es exactamente el que se digirió antes de agregarla."""
    digest = base64.b64encode(hashlib.sha1(etree.tostring(etree.ElementTree(raiz), method='c14n')).digest()).decode()
    sig = _ds(None, 'Signature')
    sig.text = '\n'
    si = _ds(sig, 'SignedInfo')
    si.text = '\n'
    _ds(si, 'CanonicalizationMethod', Algorithm=C14N)
    _ds(si, 'SignatureMethod', Algorithm=RSA_SHA1)
    ref = _ds(si, 'Reference', URI='')
    ref.text = '\n'
    trs = _ds(ref, 'Transforms')
    trs.text = '\n'
    _ds(trs, 'Transform', Algorithm='http://www.w3.org/2000/09/xmldsig#enveloped-signature')
    _ds(ref, 'DigestMethod', Algorithm=SHA1)
    _ds(ref, 'DigestValue', digest)
    sv = _ds(sig, 'SignatureValue')
    ki = _ds(sig, 'KeyInfo')
    ki.text = '\n'
    kv = _ds(ki, 'KeyValue')
    kv.text = '\n'
    rkv = _ds(kv, 'RSAKeyValue')
    rkv.text = '\n'
    _ds(rkv, 'Modulus', certificado.modulo_b64)
    _ds(rkv, 'Exponent', certificado.exponente_b64)
    xd = _ds(ki, 'X509Data')
    xd.text = '\n'
    _ds(xd, 'X509Certificate', certificado.cert_b64)
    sig.tail = None
    raiz.append(sig)
    sv.text = base64.b64encode(certificado.firmar(c14n(si))).decode()
    return sig


def verificar(raiz):
    """Revisa todas las firmas del árbol: [(uri, ok, motivo)]. Comprueba el digest del nodo
    referenciado y la firma de SignedInfo con la llave del certificado incluido."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding

    resultado = []
    ids = {e.get('ID'): e for e in raiz.iter() if isinstance(e.tag, str) and e.get('ID')}
    for sig in raiz.iter(f'{{{DS}}}Signature'):
        si = sig.find(f'{{{DS}}}SignedInfo')
        ref = si.find(f'{{{DS}}}Reference')
        uri = (ref.get('URI') or '')[1:]
        if uri:
            nodo = ids.get(uri)
            if nodo is None:
                resultado.append((uri, False, 'no existe el nodo firmado'))
                continue
            digest = _digest(nodo)
        else:  # enveloped sobre todo el documento: se digiere sin la propia Signature
            copia = copy.deepcopy(raiz)
            for s in copia.iter(f'{{{DS}}}Signature'):
                s.getparent().remove(s)
                break
            digest = base64.b64encode(hashlib.sha1(etree.tostring(etree.ElementTree(copia), method='c14n')).digest()).decode()
        if digest != (ref.findtext(f'{{{DS}}}DigestValue') or '').strip():
            resultado.append((uri, False, 'el contenido cambió después de firmar (digest)'))
            continue
        der = base64.b64decode(''.join(sig.findtext(f'.//{{{DS}}}X509Certificate').split()))
        valor = base64.b64decode(''.join(sig.findtext(f'{{{DS}}}SignatureValue').split()))
        try:
            x509.load_der_x509_certificate(der).public_key().verify(
                valor, c14n(si), padding.PKCS1v15(), hashes.SHA1())
            resultado.append((uri, True, ''))
        except Exception:
            resultado.append((uri, False, 'la firma no corresponde al certificado'))
    return resultado
