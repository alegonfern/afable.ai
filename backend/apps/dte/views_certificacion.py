"""El asistente de certificación: `/api/v1/workspaces/<slug>/dte/certificacion/...`.

Ver el avance es de cualquier miembro; cargar el set, generar, subir y avanzar es del
administrador (firma y manda al SII a nombre de la empresa).
"""
from django.http import HttpResponse
from rest_framework import status
from rest_framework.response import Response

from . import certificacion
from .models import EnvioSII
from .nucleo import ErrorDTE
from .views import MAX_ARCHIVO, _Base


def _estado(org, **extra):
    return Response({**certificacion.estado_proceso(org), **extra})


class CertificacionView(_Base):
    def get(self, request, slug):
        return _estado(request.empresa)


class SetView(_Base):
    """El set de pruebas: como texto (`texto`) o como archivo (`archivo`)."""

    def post(self, request, slug):
        archivo = request.FILES.get('archivo')
        if archivo is not None:
            if archivo.size > MAX_ARCHIVO:
                raise ErrorDTE('El archivo es demasiado grande para ser un set de pruebas.')
            texto = archivo.read()
        else:
            texto = request.data.get('texto') or ''
        if not texto or not str(texto).strip():
            raise ErrorDTE('Pegue el texto del set de pruebas o adjunte el archivo que descargó del SII.')
        certificacion.guardar_set(request.empresa, texto)
        return _estado(request.empresa)


class GenerarView(_Base):
    """{que: 'set' | 'libros' | 'simulacion', cantidad?: 10-100, guias_anuladas?: ['4329505-3']}"""

    def post(self, request, slug):
        que, org = request.data.get('que'), request.empresa
        if que == 'set':
            generados = certificacion.generar_set(org, request.user)
        elif que == 'libros':
            generados = certificacion.generar_libros(org, guias_anuladas=request.data.get('guias_anuladas') or [])
        elif que == 'simulacion':
            generados = [certificacion.generar_simulacion(org, request.data.get('cantidad') or 20)]
        else:
            raise ErrorDTE('Indique qué generar: set, libros o simulacion.')
        return _estado(org, generados=[e.id for e in generados])


class SubirView(_Base):
    def post(self, request, slug):
        subidos = certificacion.subir_pendientes(request.empresa)
        return _estado(request.empresa, subidos=[e.id for e in subidos])


class ConsultarView(_Base):
    def post(self, request, slug):
        consultados = certificacion.consultar(request.empresa)
        return _estado(request.empresa, consultados=[e.id for e in consultados])


class PasoView(_Base):
    def post(self, request, slug):
        certificacion.avanzar(request.empresa, request.data.get('paso'))
        return _estado(request.empresa)


class EnvioXmlView(_Base):
    def get(self, request, slug, pk):
        e = certificacion.envios(request.empresa).filter(pk=pk).first()
        if e is None:
            return Response({'detail': 'No existe.'}, status=status.HTTP_404_NOT_FOUND)
        r = HttpResponse(e.xml.encode('iso-8859-1'), content_type='application/xml; charset=ISO-8859-1')
        r['Content-Disposition'] = f'attachment; filename="{e.proposito}_{e.id}.xml"'
        return r


class IntercambioView(_Base):
    """El EnvioDTE que el SII mandó para el paso de intercambio (`archivo`) -> .zip con las respuestas."""

    def post(self, request, slug):
        archivo = request.FILES.get('archivo')
        if archivo is None:
            raise ErrorDTE('Adjunte el XML que le envió el SII para el intercambio.')
        if archivo.size > MAX_ARCHIVO * 4:
            raise ErrorDTE('El archivo es demasiado grande.')
        respuestas = certificacion.responder_intercambio(request.empresa, archivo.read())
        import io
        import zipfile
        salida = io.BytesIO()
        with zipfile.ZipFile(salida, 'w', zipfile.ZIP_DEFLATED) as z:
            for nombre, datos in respuestas.items():
                z.writestr(nombre, datos)
        r = HttpResponse(salida.getvalue(), content_type='application/zip')
        r['Content-Disposition'] = 'attachment; filename="respuestas_intercambio.zip"'
        return r


class MuestrasView(_Base):
    def get(self, request, slug):
        r = HttpResponse(certificacion.muestras_impresas(request.empresa), content_type='application/zip')
        r['Content-Disposition'] = 'attachment; filename="muestras_impresas.zip"'
        return r
