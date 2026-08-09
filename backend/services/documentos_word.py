"""Editar un documento de Word de verdad: el contrato del cliente, no una copia.

Mismo principio que con las planillas y con el texto: **reemplazo de un fragmento EXACTO**,
no "reescribe el documento". Pedirle el documento completo al modelo hace que reescriba de
memoria lo que no había que tocar, y en un contrato eso no se nota hasta que alguien lo
firma.

⚠️ **Lo que se pierde, dicho de frente.** `python-docx` trabaja sobre los "runs" —los
pedazos con formato propio dentro de un párrafo— y una frase partida entre varios runs
(porque una palabra está en negrita, por ejemplo) se reescribe con el formato del primero.
El texto queda correcto; el formato fino de ESE párrafo puede aplanarse. Por eso:

- cada cambio deja versión, y el original siempre está en la v1;
- se avisa en la respuesta cuando el párrafo tenía formato mezclado, en vez de que la
  persona lo descubra imprimiendo.
"""

import logging

logger = logging.getLogger(__name__)


class ErrorDeWord(Exception):
    """Algo que la persona puede corregir: un fragmento que no está o que está repetido."""


def _abrir(doc):
    from docx import Document

    if not (doc.file.name or '').lower().endswith('.docx'):
        raise ErrorDeWord('Ese archivo no es un documento de Word.')
    return Document(doc.file.path)


def reemplazar(doc, viejo, nuevo, *, agente=None, autor=None, mensaje=''):
    """Cambia un fragmento exacto dentro del documento. Devuelve un mensaje para la persona.

    El fragmento tiene que aparecer **una sola vez**: si aparece más, se rechaza en vez de
    adivinar cuál. Cambiar el párrafo equivocado de un contrato es peor que no cambiar
    nada, porque nadie lo revisa dos veces.
    """
    viejo = (viejo or '').strip()
    if not viejo:
        raise ErrorDeWord('Diga qué fragmento hay que cambiar.')

    documento = _abrir(doc)
    parrafos = list(documento.paragraphs)
    for tabla in documento.tables:
        for fila in tabla.rows:
            for celda in fila.cells:
                parrafos.extend(celda.paragraphs)

    coincidencias = [p for p in parrafos if viejo in p.text]
    if not coincidencias:
        raise ErrorDeWord(
            'Ese texto no está en el documento, tal como lo escribiste. Léelo primero y '
            'copia el fragmento exacto.'
        )
    if len(coincidencias) > 1:
        raise ErrorDeWord(
            f'Ese texto aparece {len(coincidencias)} veces. Incluye más texto alrededor '
            'para que sea único.'
        )

    parrafo = coincidencias[0]
    formato_mezclado = len([r for r in parrafo.runs if r.text.strip()]) > 1

    # Se reescribe el párrafo entero en su primer run y se vacían los demás: es la forma
    # de que el reemplazo no dependa de dónde caiga el corte entre runs.
    completo = parrafo.text.replace(viejo, nuevo)
    if parrafo.runs:
        parrafo.runs[0].text = completo
        for run in parrafo.runs[1:]:
            run.text = ''
    else:
        parrafo.text = completo

    documento.save(doc.file.path)

    from services.documentos import registrar_version_de_binario
    registrar_version_de_binario(
        doc, agente=agente, autor=autor,
        mensaje=mensaje or f'Cambió "{viejo[:40]}" por "{nuevo[:40]}"',
    )

    aviso = ''
    if formato_mezclado:
        aviso = (
            ' Ojo: ese párrafo tenía formato mezclado (negritas o cursivas dentro), así '
            'que puede haber quedado con un formato parejo. El original está en la v1.'
        )
    return f'Listo, el documento quedó cambiado.{aviso}'


def resumen_de(doc):
    """Los párrafos con su número, para que el agente sepa qué copiar.

    Devuelve poco a propósito: leer el documento entero ya lo hace
    `read_company_document`. Esto es para ubicar dónde escribir.
    """
    documento = _abrir(doc)
    parrafos = [
        {'n': i, 'texto': p.text.strip()[:200]}
        for i, p in enumerate(documento.paragraphs) if p.text.strip()
    ]
    return {'parrafos': parrafos[:120], 'total': len(parrafos)}
