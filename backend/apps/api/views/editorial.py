"""Contenido editorial: medidas, normativa, noticias, videos, eventos y biblioteca.

Todos filtran por `estado=publicado` a través del manager `publicados` de `WorkflowMixin`: el
API público no puede ser la vía por la que se escape un borrador.
"""
from datetime import date, timedelta

from django.utils.dateparse import parse_date
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.biblioteca.models import Documento
from apps.contenidos.models import Evento, Noticia, Video
from apps.medidas.models import Medida
from apps.normativa.models import EntidadEmisora, Norma, TipoNorma

from .. import exports, serializers
from ..filters import DocumentoFilter, MedidaFilter, NoticiaFilter, NormaFilter, VideoFilter
from ..throttling import DescargaThrottle


class MedidaViewSet(viewsets.ReadOnlyModelViewSet):
    """Buenas prácticas y experiencias de campo."""

    queryset = (
        Medida.publicados.select_related("tipo_peligro", "distrito__provincia")
        .prefetch_related("galeria")
    )
    filterset_class = MedidaFilter
    lookup_field = "slug"

    def get_serializer_class(self):
        if self.action == "retrieve":
            return serializers.MedidaDetalleSerializer
        return serializers.MedidaListaSerializer


class NormaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Norma.publicados.select_related("documento", "entidad_emisora", "tipo")
    filterset_class = NormaFilter
    lookup_field = "slug"

    def get_serializer_class(self):
        if self.action == "retrieve":
            return serializers.NormaDetalleSerializer
        return serializers.NormaSerializer

    @extend_schema(responses={200: serializers.EntidadEmisoraSerializer(many=True)})
    @action(detail=False, methods=["get"], pagination_class=None)
    def entidades(self, request):
        """Las entidades que alimentan el desplegable de `/normativa`.

        Solo las que tienen alguna norma publicada: ofrecer el resto sería ofrecer filtros que
        devuelven cero resultados. Va como acción del router y no como ruta suelta porque así
        se registra antes que `/<slug>/` y no puede chocar con una norma llamada «entidades».
        """
        entidades = (
            EntidadEmisora.objects.filter(normas__estado=Norma.Estado.PUBLICADO)
            .distinct()
            .order_by("orden", "nombre")
        )
        return Response(serializers.EntidadEmisoraSerializer(entidades, many=True).data)

    @extend_schema(responses={200: serializers.TipoNormaSerializer(many=True)})
    @action(detail=False, methods=["get"], pagination_class=None)
    def tipos(self, request):
        """Los tipos que alimentan el desplegable de `/normativa`. Ver `entidades`."""
        tipos = (
            TipoNorma.objects.filter(normas__estado=Norma.Estado.PUBLICADO)
            .distinct()
            .order_by("orden", "nombre")
        )
        return Response(serializers.TipoNormaSerializer(tipos, many=True).data)


class NormaExportView(APIView):
    throttle_classes = [DescargaThrottle]

    @extend_schema(responses={200: bytes})
    def get(self, request):
        queryset = Norma.publicados.select_related("documento", "entidad_emisora", "tipo")
        filtro = NormaFilter(request.query_params, queryset=queryset, request=request)

        def filas():
            for n in filtro.qs.order_by("-fecha"):
                yield [
                    n.titulo,
                    n.tipo.nombre if n.tipo_id else "",
                    n.numero,
                    n.get_ambito_display(),
                    n.entidad_emisora.nombre if n.entidad_emisora_id else "",
                    n.fecha,
                    n.get_estado_vigencia_display() if n.estado_vigencia else "",
                    n.resumen,
                    n.url_oficial or "",
                ]

        return exports.respuesta_excel(
            "normativa-grd-acc.xlsx",
            "Normativa",
            ["Título", "Tipo", "Número", "Ámbito", "Entidad emisora", "Fecha", "Vigencia",
             "Resumen", "Enlace"],
            filas(),
            [60, 18, 20, 12, 38, 12, 14, 70, 40],
        )


class NoticiaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Noticia.publicados.all()
    filterset_class = NoticiaFilter
    lookup_field = "slug"

    def get_serializer_class(self):
        if self.action == "retrieve":
            return serializers.NoticiaDetalleSerializer
        return serializers.NoticiaListaSerializer


class VideoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Video.publicados.select_related("tema")
    serializer_class = serializers.VideoSerializer
    filterset_class = VideoFilter


class EventoListaView(APIView):
    """`/api/eventos/` — calendario público. Sin paginar: el cliente pide un rango.

    Por defecto devuelve el mes visible más un margen, que es lo que necesita una vista de
    calendario para pintar los días de las semanas que asoman de los meses vecinos.
    """

    @extend_schema(
        parameters=[
            OpenApiParameter("desde", description="Fecha ISO. Default: hace 7 días."),
            OpenApiParameter("hasta", description="Fecha ISO. Default: dentro de 45 días."),
        ],
        responses={200: serializers.EventoSerializer(many=True)},
    )
    def get(self, request):
        hoy = date.today()
        desde = parse_date(request.query_params.get("desde", "")) or hoy - timedelta(days=7)
        hasta = parse_date(request.query_params.get("hasta", "")) or hoy + timedelta(days=45)
        queryset = Evento.publicados.filter(
            inicio__date__gte=desde, inicio__date__lte=hasta
        ).order_by("inicio")
        return Response(serializers.EventoSerializer(queryset, many=True).data)


class DocumentoViewSet(viewsets.ReadOnlyModelViewSet):
    """Repositorio de documentos (/recursos)."""

    queryset = Documento.publicados.select_related("categoria")
    serializer_class = serializers.DocumentoSerializer
    filterset_class = DocumentoFilter


class CategoriaDocumentoListaView(APIView):
    @extend_schema(responses={200: serializers.CategoriaDocumentoSerializer(many=True)})
    def get(self, request):
        from apps.biblioteca.models import CategoriaDocumento

        datos = serializers.CategoriaDocumentoSerializer(
            CategoriaDocumento.objects.all(), many=True
        ).data
        return Response(datos)
