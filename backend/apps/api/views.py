from django.db.models import Count
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.peligros.models import ClasificacionPeligro, FrecuenciaEmergencia, TipoPeligro
from apps.territorio.models import CentroPoblado, Distrito, Provincia

from .filters import CentroPobladoFilter, DistritoFilter, FrecuenciaFilter
from .serializers import (
    CentroPobladoDetalleSerializer,
    CentroPobladoSerializer,
    DistritoSerializer,
    FrecuenciaEmergenciaSerializer,
    ProvinciaSerializer,
    TipoPeligroSerializer,
)


class ProvinciaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Provincia.objects.all()
    serializer_class = ProvinciaSerializer
    pagination_class = None


class DistritoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Distrito.objects.select_related("provincia")
    serializer_class = DistritoSerializer
    filterset_class = DistritoFilter
    pagination_class = None


class CentroPobladoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CentroPoblado.objects.select_related("distrito", "distrito__provincia")
    filterset_class = CentroPobladoFilter
    lookup_field = "codigo"

    def get_serializer_class(self):
        if self.action == "retrieve":
            return CentroPobladoDetalleSerializer
        return CentroPobladoSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action == "retrieve":
            qs = qs.prefetch_related(
                "clasificaciones__tipo_peligro", "clasificaciones__fuente"
            )
        return qs


class TipoPeligroViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = TipoPeligro.objects.all()
    serializer_class = TipoPeligroSerializer
    pagination_class = None


class ResumenPeligrosView(APIView):
    """Conteos de clasificaciones por tipo de peligro × nivel (cifras del visor).

    Query params opcionales: provincia, distrito (ubigeo o nombre).
    """

    def get(self, request):
        qs = ClasificacionPeligro.objects.all()
        provincia = request.query_params.get("provincia")
        distrito = request.query_params.get("distrito")
        if provincia:
            campo = (
                "centro_poblado__distrito__provincia__ubigeo"
                if provincia.isdigit()
                else "centro_poblado__distrito__provincia__nombre__iexact"
            )
            qs = qs.filter(**{campo: provincia})
        if distrito:
            campo = (
                "centro_poblado__distrito__ubigeo"
                if distrito.isdigit()
                else "centro_poblado__distrito__nombre__iexact"
            )
            qs = qs.filter(**{campo: distrito})

        por_peligro = qs.values("tipo_peligro__nombre", "nivel").annotate(total=Count("id"))
        resumen: dict[str, dict[str, int]] = {}
        for fila in por_peligro:
            resumen.setdefault(fila["tipo_peligro__nombre"], {})[str(fila["nivel"])] = fila[
                "total"
            ]
        return Response({
            "total_ccpp": CentroPoblado.objects.count(),
            "total_clasificaciones": qs.count(),
            "por_peligro": resumen,
        })


class FrecuenciaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = FrecuenciaEmergencia.objects.select_related(
        "distrito__provincia", "tipo_evento__categoria"
    )
    serializer_class = FrecuenciaEmergenciaSerializer
    filterset_class = FrecuenciaFilter
