"""El timbre electrónico (TED) de cada DTE (ESPEC_SII.md §5.2).

El DD lleva los datos clave del documento y el CAF; se firma con la llave del CAF (SHA1withRSA,
no XMLDSig) sobre el DD "aplanado": sin espacios entre tags, sin namespaces, en ISO-8859-1.
Comprobado contra los dos ejemplos oficiales del SII (tests_nucleo.py).
"""
import base64
import re
from xml.sax.saxutils import escape

from lxml import etree

from . import ErrorDTE
from .xmlutil import SII, sub, texto


def mensaje(re_, td, folio, fe, rr, rsr, mnt, it1, caf_plano, tsted):
    """El DD aplanado, exactamente como lo firma (y lo verifica) el SII."""
    campos = [('RE', re_), ('TD', td), ('F', folio), ('FE', fe), ('RR', rr), ('RSR', rsr), ('MNT', mnt),
              ('IT1', it1)]
    cuerpo = ''.join(f'<{t}>{escape(str(v))}</{t}>' for t, v in campos)
    return f'<DD>{cuerpo}{caf_plano}<TSTED>{tsted}</TSTED></DD>'.encode('iso-8859-1')


def timbrar(padre, documento, total, caf, tsted):
    """Agrega a `padre` (el <Documento>) el TED de `documento` (documento.Documento), firmado con `caf`."""
    d = documento
    if caf.tipo != d.tipo:
        raise ErrorDTE(f'El CAF es de documentos tipo {caf.tipo} y el documento es tipo {d.tipo}.')
    if caf.rut != d.emisor.rut:
        raise ErrorDTE(f'El CAF es del RUT {caf.rut} y el documento lo emite {d.emisor.rut}.')
    if not caf.contiene(d.folio):
        raise ErrorDTE(f'El folio {d.folio} no está en el CAF (del {caf.desde} al {caf.hasta}).')
    valores = dict(re_=d.emisor.rut, td=d.tipo, folio=d.folio, fe=d.fecha.isoformat(), rr=d.receptor.rut,
                   rsr=texto(d.receptor.razon_social, 40), mnt=int(total),
                   it1=texto(d.lineas[0].nombre, 40), tsted=tsted.strftime('%Y-%m-%dT%H:%M:%S'))
    frmt = caf.firmar(mensaje(caf_plano=caf.caf_plano, **valores))

    ted = sub(padre, 'TED', version='1.0')
    dd = sub(ted, 'DD')
    for tag, clave in (('RE', 're_'), ('TD', 'td'), ('F', 'folio'), ('FE', 'fe'), ('RR', 'rr'), ('RSR', 'rsr'),
                       ('MNT', 'mnt'), ('IT1', 'it1')):
        sub(dd, tag, valores[clave])
    caf.copiar_en(dd)
    sub(dd, 'TSTED', valores['tsted'])
    sub(ted, 'FRMT', base64.b64encode(frmt).decode(), algoritmo='SHA1withRSA')
    return ted


def aplanar(dd):
    """El DD de un XML ya armado, aplanado como para firmarlo: sirve para verificar un timbre."""
    s = etree.tostring(dd, encoding='unicode', with_tail=False)
    s = re.sub(r'\s+xmlns(:\w+)?="[^"]*"', '', s)
    return re.sub(r'>\s+<', '><', s).encode('iso-8859-1')


def verificar(ted, caf):
    """True si el FRMT del TED corresponde a su DD con la llave del CAF."""
    dd = ted.find(f'{{{SII}}}DD')
    frmt = base64.b64decode(''.join(ted.findtext(f'{{{SII}}}FRMT').split()))
    return caf.verificar(aplanar(dd), frmt)
