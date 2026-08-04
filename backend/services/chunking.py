"""
Troceado de texto para la busqueda semantica.

Un embedding representa UN significado. Si se vectoriza un manual entero, el
vector queda en el promedio de todo lo que dice y no se parece a ninguna
pregunta concreta; si se vectorizan lineas sueltas, cada pedazo pierde el hilo de
lo que venia diciendo. El tamano de trozo es ese equilibrio.

Dos decisiones que valen explicarse:

- **Se corta en los limites que el texto ya trae** (parrafo, y dentro del
  parrafo, oracion) antes que en una cuenta de caracteres. Un trozo que empieza a
  mitad de una frase se recupera peor y se lee peor cuando se cita.
- **Los trozos se solapan.** Sin solape, la frase que responde la pregunta puede
  caer justo partida entre dos trozos y no parecerse a la pregunta en ninguno de
  los dos.
"""
import re

TAMANO = 1200      # caracteres por trozo (~350 tokens, bien dentro del num_ctx del modelo)
SOLAPE = 200       # cola del trozo anterior que se repite al principio del siguiente
MINIMO = 80        # menos que esto no se guarda: son migajas, no conocimiento

_PARRAFOS = re.compile(r'\n\s*\n+')
_ORACIONES = re.compile(r'(?<=[.!?:;])\s+')


def trocear(texto: str, tamano: int = TAMANO, solape: int = SOLAPE) -> list[str]:
    """Parte un texto en trozos solapados, respetando parrafos y oraciones."""
    texto = (texto or '').strip()
    if not texto:
        return []
    if len(texto) <= tamano:
        return [texto]

    trozos = []
    actual = ''
    for unidad in _unidades(texto, tamano):
        if not actual:
            actual = unidad
        elif len(actual) + 1 + len(unidad) <= tamano:
            actual = f'{actual}\n{unidad}'
        else:
            trozos.append(actual)
            actual = _cola(actual, solape) + unidad
    if actual:
        trozos.append(actual)

    # El ultimo trozo puede quedar en migajas (un parrafo corto suelto al final).
    # Se pega al anterior en vez de guardarse solo, salvo que sea el unico.
    if len(trozos) > 1 and len(trozos[-1]) < MINIMO:
        cola = trozos.pop()
        trozos[-1] = f'{trozos[-1]} {cola}'
    return [t.strip() for t in trozos if t.strip()]


def _unidades(texto: str, tamano: int) -> list[str]:
    """Los pedazos indivisibles con los que se arman los trozos.

    Primero parrafos; el parrafo que no cabe en un trozo se baja a oraciones, y la
    oracion que tampoco cabe (una tabla, un JSON pegado, un texto sin puntuacion)
    se corta a lo bruto por largo, que es lo unico que queda.
    """
    unidades = []
    for parrafo in _PARRAFOS.split(texto):
        parrafo = parrafo.strip()
        if not parrafo:
            continue
        if len(parrafo) <= tamano:
            unidades.append(parrafo)
            continue
        for oracion in _ORACIONES.split(parrafo):
            oracion = oracion.strip()
            if not oracion:
                continue
            if len(oracion) <= tamano:
                unidades.append(oracion)
            else:
                unidades.extend(
                    oracion[i:i + tamano] for i in range(0, len(oracion), tamano)
                )
    return unidades


def _cola(trozo: str, solape: int) -> str:
    """Los ultimos `solape` caracteres del trozo, cortados en un espacio.

    Cortar en medio de una palabra ensucia el trozo siguiente sin aportar nada.
    """
    if solape <= 0 or len(trozo) <= solape:
        return ''
    cola = trozo[-solape:]
    espacio = cola.find(' ')
    if espacio > 0:
        cola = cola[espacio + 1:]
    return cola.strip() + ' ' if cola.strip() else ''
