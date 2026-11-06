"""El núcleo del facturador electrónico nativo de Afable (26-10-2026).

Python puro, sin Django: arma los DTE (33, 34, 52, 56, 61) en el XML del SII, los timbra con el
CAF, los firma con el certificado de la empresa y los junta en el EnvioDTE. No habla con el SII:
eso es `apps.dte.sii`. La especificación, con sus fuentes, está en `apps/dte/ESPEC_SII.md`.

    caf.py          el archivo de folios: leerlo, validarlo, firmar el timbre
    certificado.py  el .pfx de quien firma: RUT, vigencia, firma RSA-SHA1
    documento.py    los datos de un DTE, sus totales y su XML
    ted.py          el timbre electrónico (TED)
    firma.py        la firma XMLDSig del perfil del SII
    envio.py        el EnvioDTE con su carátula, firmado
    esquemas/       los XSD oficiales y la validación contra ellos
"""


class ErrorDTE(Exception):
    """Un problema con los datos del documento, dicho para quien lo emite."""
