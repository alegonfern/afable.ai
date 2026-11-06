"""El PDF de un DTE emitido: `/api/v1/workspaces/<slug>/dte/documentos/<pk>/pdf/?cedible=1`."""
from django.http import HttpResponse
from rest_framework import status
from rest_framework.response import Response

from . import pdf
from .models import DocumentoEmitido
from .views import _Base


class DocumentoPdfView(_Base):
    def get(self, request, slug, pk):
        x = DocumentoEmitido.objects.filter(organization=request.empresa, pk=pk).first()
        if x is None:
            return Response({'detail': 'No existe.'}, status=status.HTTP_404_NOT_FOUND)
        cedible = request.query_params.get('cedible') in ('1', 'true', 'si')
        r = HttpResponse(pdf.generar(x, cedible=cedible), content_type='application/pdf')
        sufijo = '-cedible' if cedible and pdf.admite_cedible(x.tipo) else ''
        r['Content-Disposition'] = f'inline; filename="DTE-{x.tipo}-{x.folio}{sufijo}.pdf"'
        return r
