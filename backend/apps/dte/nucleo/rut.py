"""El RUT como lo pide el SII: sin puntos, con guion y la K mayúscula (12345678-K)."""
import re

from . import ErrorDTE


def dv(numero):
    """El dígito verificador de un RUT (módulo 11)."""
    suma, factor = 0, 2
    for d in reversed(str(int(numero))):
        suma += int(d) * factor
        factor = 2 if factor == 7 else factor + 1
    resto = 11 - suma % 11
    return {11: '0', 10: 'K'}.get(resto, str(resto))


def normalizar(rut):
    """'12.345.678-k' -> '12345678-K'. Lanza ErrorDTE si el dígito verificador no calza."""
    limpio = re.sub(r'[^0-9kK]', '', str(rut or '')).upper()
    if len(limpio) < 2 or not limpio[:-1].isdigit():
        raise ErrorDTE(f'El RUT «{rut}» no es válido.')
    numero, digito = limpio[:-1].lstrip('0') or '0', limpio[-1]
    if dv(numero) != digito:
        raise ErrorDTE(f'El RUT «{rut}» no es válido: el dígito verificador no corresponde.')
    return f'{numero}-{digito}'


def valido(rut):
    try:
        normalizar(rut)
        return True
    except ErrorDTE:
        return False


def partes(rut):
    """('12345678', 'K'), como piden los campos rutSender/dvSender del SII."""
    numero, digito = normalizar(rut).split('-')
    return numero, digito
