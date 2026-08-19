"""Cómo se MUESTRA cada archivo, según lo que es.

Hasta acá todo se dibujaba igual: el texto que se le extrajo, en monoespaciado. Una
planilla de 300 filas se veía como un chorro de palabras y un contrato perdía sus títulos.
Servía para que el agente leyera, no para que una persona mirara — y es de las cosas que
más hacían sentir que el archivo estaba "de adorno".

Cada formato se devuelve como lo que es:

- **Planilla** → hojas, filas y celdas. La pantalla dibuja una tabla de verdad.
- **Documento de Word** → HTML acotado (títulos, negritas, listas, tablas). Se conserva la
  jerarquía, que es lo que hace leíble un contrato.
- **PDF** → se muestra el archivo mismo, que el navegador ya sabe dibujar. Nada de
  reconstruirlo: el original siempre se va a ver mejor que cualquier aproximación. La
  pantalla lo baja por la API (con sesión) y lo dibuja desde memoria.
- **Texto** → como estaba.

⚠️ **Se acota a propósito** (`MAX_FILAS`, `MAX_COLUMNAS`): una planilla de 50.000 filas
mandada entera cuelga el navegador. Se avisa cuánto se recortó, en vez de mentir mostrando
lo que entró.
"""

import logging

logger = logging.getLogger(__name__)

MAX_FILAS = 200
MAX_COLUMNAS = 40

PLANILLA = ('.xlsx', '.xlsm')
DOCUMENTO = ('.docx',)
PDF = ('.pdf',)


def vista_de(doc):
    """Devuelve `{tipo, ...}` con lo que la pantalla necesita para dibujarlo."""
    nombre = (doc.file.name or '').lower()

    try:
        if nombre.endswith(PLANILLA):
            return _planilla(doc)
        if nombre.endswith(DOCUMENTO):
            return _documento(doc)
        if nombre.endswith(PDF):
            # Sin dirección: la pantalla lo pide por la API, que comprueba permisos. Antes
            # se mandaba `doc.file.url` (/media/…), que cualquiera con la dirección abría
            # sin sesión.
            return {'tipo': 'pdf'}
    except Exception:
        # Un archivo dañado o con una variante rara del formato no puede dejar la
        # pantalla en blanco: se cae al texto extraído, que es lo que había antes.
        logger.exception('No se pudo armar la vista de %s', doc.pk)

    return {'tipo': 'texto', 'texto': doc.extracted_text or ''}


def _planilla(doc):
    from openpyxl import load_workbook

    # Dos lecturas: `data_only` trae el valor calculado, pero una fórmula que Excel
    # todavía no evaluó viene vacía — y una columna recién agregada por el agente se
    # vería en blanco, como si no hubiera hecho nada. La segunda lectura trae la fórmula
    # para mostrarla mientras tanto.
    libro = load_workbook(doc.file.path, data_only=True, read_only=True)
    try:
        formulas = load_workbook(doc.file.path, data_only=False)
    except Exception:
        formulas = None
    hojas = []
    for hoja in libro.worksheets:
        crudas = None
        if formulas is not None and hoja.title in formulas.sheetnames:
            crudas = list(formulas[hoja.title].iter_rows(values_only=True))

        filas, recortada = [], False
        for i, fila in enumerate(hoja.iter_rows(values_only=True)):
            if i >= MAX_FILAS:
                recortada = True
                break
            celdas = []
            for j, c in enumerate(fila[:MAX_COLUMNAS]):
                if c is None and crudas and i < len(crudas) and j < len(crudas[i]):
                    c = crudas[i][j]
                celdas.append('' if c is None else str(c))
            filas.append(celdas)
        hojas.append({
            'nombre': hoja.title,
            'filas': filas,
            # Cuánto se dejó fuera. Decirlo evita que alguien saque conclusiones de una
            # planilla que creía completa.
            'recortada': recortada,
            'total_filas': hoja.max_row,
        })
    libro.close()
    if formulas is not None:
        formulas.close()
    return {'tipo': 'planilla', 'hojas': hojas}


def _documento(doc):
    from docx import Document

    from html import escape

    documento = Document(doc.file.path)
    partes = []
    for parrafo in documento.paragraphs:
        texto = parrafo.text.strip()
        if not texto:
            continue
        estilo = (parrafo.style.name or '').lower()
        if 'heading 1' in estilo or estilo == 'title':
            partes.append(f'<h2>{escape(texto)}</h2>')
        elif 'heading' in estilo:
            partes.append(f'<h3>{escape(texto)}</h3>')
        elif 'list' in estilo:
            partes.append(f'<li>{escape(texto)}</li>')
        else:
            partes.append(f'<p>{escape(texto)}</p>')

    for tabla in documento.tables:
        filas = []
        for fila in tabla.rows:
            celdas = ''.join(f'<td>{escape(c.text.strip())}</td>' for c in fila.cells)
            filas.append(f'<tr>{celdas}</tr>')
        if filas:
            partes.append(f'<table>{"".join(filas)}</table>')

    return {'tipo': 'texto_rico', 'html': '\n'.join(partes)}
