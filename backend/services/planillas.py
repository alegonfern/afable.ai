"""Editar una planilla de verdad: el archivo del cliente, no una copia.

Hasta acá el agente leía un Excel y, si había que cambiarlo, creaba un documento de texto
nuevo. Eso es lo que hacía sentir el producto de juguete: la planilla con la que la empresa
trabaja seguía intacta y uno terminaba copiando a mano.

⭐ **Operaciones acotadas, no "reescribe el archivo".** El agente no manda un xlsx entero:
pide cambios concretos (escribir una celda, agregar una columna, sumar una fila) y acá se
aplican sobre el archivo real con `openpyxl`, que conserva todo lo que no se tocó. Pedirle
el archivo completo tendría el mismo problema que pedirle el texto completo de un
documento: reescribe de memoria lo que no había que tocar.

**Cada cambio deja versión**, igual que en los documentos de texto: es lo que hace que
dejar a un agente escribir sobre un archivo de la empresa no sea una apuesta.
"""

import io
import logging

from openpyxl.utils import get_column_letter

logger = logging.getLogger(__name__)

MAX_FILAS_NUEVAS = 500


class ErrorDePlanilla(Exception):
    """Algo que la persona puede corregir: una hoja que no existe, una celda inválida."""


def _abrir(doc):
    from openpyxl import load_workbook

    if not (doc.file.name or '').lower().endswith(('.xlsx', '.xlsm')):
        raise ErrorDePlanilla('Ese archivo no es una planilla de Excel.')
    return load_workbook(doc.file.path)


def _hoja(libro, nombre):
    if not nombre:
        return libro.active
    if nombre not in libro.sheetnames:
        disponibles = ', '.join(libro.sheetnames)
        raise ErrorDePlanilla(f'No hay una hoja "{nombre}". Las que hay: {disponibles}.')
    return libro[nombre]


def _guardar(doc, libro, *, agente=None, autor=None, mensaje=''):
    """Escribe el archivo y deja la versión. Un solo lugar para las dos cosas."""
    from services.documentos import registrar_version_de_binario

    buffer = io.BytesIO()
    libro.save(buffer)
    contenido = buffer.getvalue()

    with open(doc.file.path, 'wb') as f:
        f.write(contenido)

    return registrar_version_de_binario(doc, agente=agente, autor=autor, mensaje=mensaje)


def escribir_celda(doc, celda, valor, *, hoja=None, agente=None, autor=None):
    """Escribe UNA celda: `escribir_celda(doc, 'C4', 'Pagado')`."""
    libro = _abrir(doc)
    h = _hoja(libro, hoja)
    try:
        h[celda] = valor
    except (ValueError, KeyError) as e:
        raise ErrorDePlanilla(f'"{celda}" no es una celda válida.') from e

    _guardar(doc, libro, agente=agente, autor=autor,
             mensaje=f'{h.title}!{celda} = {valor}')
    return f'Listo: {h.title}!{celda} quedó en "{valor}".'


def agregar_columna(doc, titulo, valores=None, formula=None, *, hoja=None,
                    agente=None, autor=None):
    """Agrega una columna al final, con valores o con una fórmula por fila.

    `formula` usa `{fila}` donde va el número de fila: `'=B{fila}*0.19'`. Es la forma de
    pedir "agrégale el IVA" sin que el agente tenga que enumerar 300 celdas —y sin que se
    equivoque en la 217.
    """
    if not titulo:
        raise ErrorDePlanilla('La columna necesita un título.')
    if not valores and not formula:
        raise ErrorDePlanilla('Diga qué va en la columna: valores o una fórmula.')

    libro = _abrir(doc)
    h = _hoja(libro, hoja)
    col = h.max_column + 1
    letra = get_column_letter(col)

    h.cell(row=1, column=col, value=titulo)
    ultima = min(h.max_row, MAX_FILAS_NUEVAS)
    for fila in range(2, ultima + 1):
        if formula:
            h.cell(row=fila, column=col, value=formula.replace('{fila}', str(fila)))
        else:
            i = fila - 2
            h.cell(row=fila, column=col, value=valores[i] if i < len(valores) else None)

    _guardar(doc, libro, agente=agente, autor=autor,
             mensaje=f'Columna "{titulo}" en {h.title} ({letra})')
    return f'Listo: la columna "{titulo}" quedó en {h.title}, columna {letra}.'


def agregar_fila(doc, valores, *, hoja=None, agente=None, autor=None):
    """Agrega una fila al final de la hoja."""
    if not valores:
        raise ErrorDePlanilla('La fila necesita valores.')

    libro = _abrir(doc)
    h = _hoja(libro, hoja)
    h.append(list(valores))

    _guardar(doc, libro, agente=agente, autor=autor,
             mensaje=f'Fila nueva en {h.title}: {", ".join(str(v) for v in valores[:4])}')
    return f'Listo: se agregó una fila al final de {h.title}.'


def resumen_de(doc):
    """Qué hojas y columnas tiene, para que el agente sepa dónde escribir.

    Sin esto el agente adivina los nombres de las columnas, y una fórmula sobre la columna
    equivocada es peor que no hacer nada: queda escrita y con cara de correcta.
    """
    libro = _abrir(doc)
    hojas = []
    for h in libro.worksheets:
        encabezados = []
        for fila in h.iter_rows(min_row=1, max_row=1, values_only=True):
            encabezados = [
                f'{get_column_letter(i + 1)}: {c}' for i, c in enumerate(fila) if c is not None
            ]
            break
        hojas.append({'nombre': h.title, 'filas': h.max_row, 'columnas': encabezados})
    libro.close()
    return hojas
