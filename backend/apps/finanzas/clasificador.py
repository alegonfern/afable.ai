"""La IA propone la categoría de lo que está sin clasificar.

Lo más pesado de ordenar las finanzas es clasificar cada compra y cada venta. Acá la IA
propone, y la persona confirma: nada queda confirmado solo por la IA.

Se pregunta por contraparte (RUT + razón social), no por documento: todas las facturas de un
mismo proveedor suelen ir a la misma categoría, y así cientos de documentos se resuelven en
una sola consulta. Corre en el modelo del trabajo autónomo, el más barato.

Sirve en dos lugares: en la revisión antes de importar (`sugerir_en_carga`) y sobre los
documentos ya cargados (`sugerir`).
"""

import json
import logging
import re

from .models import Carga, Categoria, DocumentoTributario

logger = logging.getLogger(__name__)

MAX_CONTRAPARTES = 80

SISTEMA = (
    'Eres el asistente contable de una empresa chilena. Clasificas documentos tributarios en '
    'categorías. Respondes SOLO un objeto JSON, sin texto antes ni después.'
)


def _preguntar(prompt, organization):
    # Importado acá: el servicio de IA arrastra dependencias pesadas que los tests no necesitan.
    from services.agent_service import chat_direct, modelo_autonomo
    return chat_direct([{'role': 'user', 'content': prompt}], SISTEMA,
                       model=modelo_autonomo(), organization=organization,
                       motivo='finanzas_clasificacion')


def _extraer_json(texto):
    m = re.search(r'\{.*\}', texto or '', re.DOTALL)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}


def proponer(organization, contrapartes):
    """`contrapartes`: [{"clave", "libro", "nombre"}]. Devuelve {clave: Categoria} con lo que
    la IA propone, descartando lo que no calza (un ingreso para una compra, por ejemplo)."""
    Categoria.asegurar_iniciales(organization)
    contrapartes = contrapartes[:MAX_CONTRAPARTES]
    if not contrapartes:
        return {}
    categorias = {cat.nombre: cat for cat in Categoria.objects.filter(organization=organization)}
    ingresos = [n for n, cat in categorias.items() if cat.tipo == 'ingreso']
    gastos = [n for n, cat in categorias.items() if cat.tipo == 'gasto']
    lineas = [f'- {x["clave"]} | {x["libro"]} | {x["nombre"] or "(sin nombre)"}' for x in contrapartes]
    prompt = (
        'Clasifica cada contraparte en UNA categoría de la lista que corresponde a su libro.\n'
        f'Para "ventas" usa solo: {", ".join(ingresos)}.\n'
        f'Para "compras" y "honorarios" usa solo: {", ".join(gastos)}.\n'
        'Si no hay pistas suficientes, usa "Otros gastos" u "Otros ingresos".\n\n'
        'Contrapartes (clave | libro | razón social):\n' + '\n'.join(lineas) + '\n\n'
        'Responde {"<clave>": "<categoría>", ...} con TODAS las claves.'
    )
    try:
        respuesta = _extraer_json(_preguntar(prompt, organization))
    except Exception:
        logger.exception('finanzas: la clasificación con IA falló')
        return {}
    resultado = {}
    for x in contrapartes:
        categoria = categorias.get(str(respuesta.get(x['clave'], '')).strip())
        # Una categoría de ingreso nunca va a una compra, aunque el modelo se equivoque.
        if categoria and (x['libro'] == 'ventas') == (categoria.tipo == 'ingreso'):
            resultado[x['clave']] = categoria
    return resultado


def sugerir(organization, documentos=None):
    """Propone categoría para los documentos cargados sin categoría. Devuelve cuántos."""
    qs = documentos if documentos is not None else DocumentoTributario.objects.filter(
        organization=organization)
    pendientes = list(qs.filter(categoria__isnull=True).order_by('rut'))
    grupos = {}
    for d in pendientes:
        grupos.setdefault(f'{d.libro}|{d.rut}', {'clave': f'{d.libro}|{d.rut}', 'libro': d.libro,
                                                'nombre': d.razon_social, 'docs': []})['docs'].append(d)
    propuestas = proponer(organization, list(grupos.values()))
    sugeridos = 0
    for clave, categoria in propuestas.items():
        for d in grupos[clave]['docs']:
            d.categoria = categoria
            d.origen_clasificacion = DocumentoTributario.ORIGEN_IA
            d.save(update_fields=['categoria', 'origen_clasificacion'])
            sugeridos += 1
    return sugeridos


def sugerir_en_carga(carga):
    """Completa la categoría de las filas sin proponer de una carga en borrador."""
    if carga.estado != Carga.BORRADOR:
        return 0
    grupos = {}
    for f in carga.filas_previas:
        if not f['categoria']:
            grupos.setdefault(f['rut'], {'clave': f['rut'], 'libro': carga.libro,
                                         'nombre': f['razon_social']})
    propuestas = proponer(carga.organization, list(grupos.values()))
    sugeridos = 0
    for f in carga.filas_previas:
        if not f['categoria'] and f['rut'] in propuestas:
            f['categoria'] = propuestas[f['rut']].id
            f['origen'] = DocumentoTributario.ORIGEN_IA
            sugeridos += 1
    carga.save(update_fields=['filas_previas'])
    return sugeridos
