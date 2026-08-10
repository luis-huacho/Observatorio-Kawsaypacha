"""Territorio, centros poblados y peligros: la ventana con datos reales."""
import hashlib
import json

from django.db.models import Max
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.text import slugify
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.peligros import consultas
from apps.peligros.models import FrecuenciaEmergencia, TipoPeligro
from apps.territorio.models import CentroPoblado, Distrito, Provincia

from .. import exports, serializers
from ..filters import (
    CentroPobladoFilter,
    DistritoFilter,
    FrecuenciaFilter,
    anotar_nivel,
    por_ubigeo_o_nombre,
)
from ..throttling import DescargaThrottle

PARAMS_CCPP = [
    OpenApiParameter("provincia", description="Ubigeo de 4 dígitos o nombre."),
    OpenApiParameter("distrito", description="Ubigeo de 6 dígitos o nombre."),
    OpenApiParameter("peligro", description="Slug del peligro (p. ej. `movimientos_en_masa`)."),
    OpenApiParameter("nivel_min", description="Nivel mínimo, 1-4.", type=int),
    OpenApiParameter("buscar", description="Coincidencia parcial en el nombre."),
    OpenApiParameter(
        "clasificados",
        description="`1` deja solo los centros poblados con clasificación tras aplicar los "
        "filtros. Es lo que usa la tabla del visor; el padrón completo la convertiría en una "
        "lista de «sin dato» (5,730 de 8,968 en toda la región).",
        type=bool,
    ),
]


class ProvinciaViewSet(viewsets.ReadOnlyModelViewSet):
    """Las 13 provincias de Cusco. Sin paginar: alimenta un `<select>`."""

    queryset = Provincia.objects.all()
    serializer_class = serializers.ProvinciaSerializer
    pagination_class = None
    lookup_field = "ubigeo"


class DistritoViewSet(viewsets.ReadOnlyModelViewSet):
    """Los 112 distritos. Sin paginar."""

    queryset = Distrito.objects.select_related("provincia")
    serializer_class = serializers.DistritoSerializer
    filterset_class = DistritoFilter
    pagination_class = None
    lookup_field = "ubigeo"


@extend_schema(parameters=PARAMS_CCPP)
class CentroPobladoViewSet(viewsets.ReadOnlyModelViewSet):
    """Padrón de 8,968 centros poblados con su nivel de peligro."""

    queryset = CentroPoblado.objects.select_related("distrito__provincia")
    filterset_class = CentroPobladoFilter
    lookup_field = "codigo"
    lookup_value_regex = r"\d{10}"

    def get_serializer_class(self):
        if self.action == "retrieve":
            return serializers.CentroPobladoDetalleSerializer
        return serializers.CentroPobladoSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action == "retrieve":
            return qs.prefetch_related("clasificaciones__tipo_peligro", "clasificaciones__fuente")
        # El orden por nivel lo pone `CentroPobladoFilter.filter_queryset`, que es donde ya
        # existe la anotación.
        return qs


class CentroPobladoExportView(APIView):
    """`/api/ccpp/export.xlsx` — misma consulta y mismos filtros que el listado."""

    throttle_classes = [DescargaThrottle]

    @extend_schema(parameters=PARAMS_CCPP, responses={200: bytes})
    def get(self, request):
        vista = CentroPobladoViewSet(request=request, action="list", format_kwarg=None)
        vista.kwargs = {}
        queryset = vista.filter_queryset(vista.get_queryset())
        return exports.respuesta_excel(
            "centros-poblados-cusco.xlsx",
            "Centros poblados",
            exports.CABECERAS_CCPP,
            exports.filas_ccpp(queryset),
            exports.ANCHOS_CCPP,
        )


class CentroPobladoGeoJSONView(APIView):
    """`/api/ccpp/geojson/` — la fuente de puntos del visor (ADR-A13).

    MapLibre solo agrupa fuentes `geojson`, así que la capa de centros poblados no sale del
    tile vectorial. Se devuelve el `FeatureCollection` completo que pasa los filtros, sin
    paginar, e **incluyendo los no clasificados** (`nivel: 0`), que el visor pinta en gris.

    Se responde con `ETag`: el payload region-wide ronda los 2 MB y no cambia entre cargas
    salvo que se reimporte el Excel, así que lo normal es que el navegador revalide y no
    vuelva a descargarlo.
    """

    @extend_schema(parameters=PARAMS_CCPP, responses={200: dict})
    def get(self, request):
        queryset = CentroPoblado.objects.select_related("distrito__provincia").exclude(
            lat=None
        ).exclude(lon=None)
        filtro = CentroPobladoFilter(request.query_params, queryset=queryset, request=request)
        queryset = filtro.qs

        # El popup necesita el desglose por peligro. Se trae en una sola consulta y se agrupa
        # en memoria: 10,978 filas es barato, y hacerlo por punto serían 8,968 consultas.
        peligros_por_ccpp: dict[int, list] = {}
        from apps.peligros.models import ClasificacionPeligro

        condicion = ClasificacionPeligro.objects.filter(
            centro_poblado__in=queryset.values("pk")
        ).select_related("tipo_peligro")
        if peligro := request.query_params.get("peligro"):
            condicion = condicion.filter(tipo_peligro__slug=peligro)
        if nivel_min := request.query_params.get("nivel_min"):
            try:
                condicion = condicion.filter(nivel__gte=int(nivel_min))
            except (TypeError, ValueError):
                pass
        for c in condicion:
            peligros_por_ccpp.setdefault(c.centro_poblado_id, []).append(
                {"p": c.tipo_peligro.nombre, "n": c.nivel}
            )

        features = []
        for c in queryset.iterator(chunk_size=2000):
            desglose = sorted(
                peligros_por_ccpp.get(c.pk, []), key=lambda x: x["n"], reverse=True
            )
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [c.lon, c.lat]},
                "properties": {
                    "codigo": c.codigo,
                    "nombre": c.nombre,
                    "categoria": c.categoria,
                    "distrito": c.distrito.nombre,
                    "provincia": c.distrito.provincia.nombre,
                    "ubigeo_distrito": c.distrito_id,
                    "poblacion": c.poblacion or 0,
                    "altitud": c.altitud,
                    # 0 = sin dato. Mantenerlo como categoría propia, y no como nivel bajo, es
                    # lo que impide que un vacío de información se lea como ausencia de riesgo.
                    "nivel": c.nivel or 0,
                    # Cuántas clasificaciones aporta este punto con los filtros puestos. Es el
                    # número que el visor suma dentro de cada círculo agrupado: la unidad de
                    # 10,978, no la de 3,238. Vale 0 para los que no cumplen, que siguen en la
                    # respuesta para pintarse en gris — y así el conteo del mapa sí reacciona a
                    # los filtros, cosa que `point_count` de MapLibre no podía hacer.
                    "clasificaciones": len(desglose),
                    # Serializado: las propiedades de un feature agrupado tienen que ser
                    # escalares (spec 05), así que el desglose viaja como texto y el popup lo
                    # parsea.
                    "peligros": json.dumps(desglose, ensure_ascii=False),
                },
            })

        cuerpo = {"type": "FeatureCollection", "features": features}
        respuesta = JsonResponse(cuerpo)
        etag = hashlib.md5(
            f"{len(features)}:{request.get_full_path()}:{_sello_datos()}".encode()
        ).hexdigest()
        respuesta["ETag"] = f'W/"{etag}"'
        respuesta["Cache-Control"] = "public, max-age=300"
        return respuesta


def _sello_datos() -> str:
    """Marca de la última importación de peligros, para invalidar el ETag al reimportar."""
    from apps.peligros.models import ClasificacionPeligro

    ultimo = ClasificacionPeligro.objects.aggregate(m=Max("actualizado_en"))["m"]
    return ultimo.isoformat() if ultimo else "vacio"


class TipoPeligroViewSet(viewsets.ReadOnlyModelViewSet):
    """Catálogo de los 9 peligros. Sin paginar; es la fuente del selector del visor."""

    queryset = TipoPeligro.objects.all()
    serializer_class = serializers.TipoPeligroSerializer
    pagination_class = None
    lookup_field = "slug"


class ResumenPeligrosView(APIView):
    """`/api/peligros/resumen/` — cifras de la portada y del panel de distribución."""

    @extend_schema(
        parameters=[
            OpenApiParameter("provincia"), OpenApiParameter("distrito"),
            OpenApiParameter("peligro"), OpenApiParameter("nivel_min", type=int),
        ],
        responses={200: dict},
    )
    def get(self, request):
        queryset = CentroPoblado.objects.all()
        if provincia := request.query_params.get("provincia"):
            queryset = por_ubigeo_o_nombre(
                queryset, "distrito__provincia__ubigeo", "distrito__provincia__nombre", provincia
            )
        if distrito := request.query_params.get("distrito"):
            queryset = por_ubigeo_o_nombre(
                queryset, "distrito__ubigeo", "distrito__nombre", distrito
            )
        datos = consultas.resumen(
            queryset,
            peligro=request.query_params.get("peligro", ""),
            nivel_min=request.query_params.get("nivel_min", ""),
        )
        return Response(datos)


class FrecuenciaListaView(APIView):
    """`/api/peligros/frecuencia/` — una entrada por distrito con datos. Sin paginar (≤111)."""

    @extend_schema(
        parameters=[
            OpenApiParameter("provincia"), OpenApiParameter("distrito"),
            OpenApiParameter("categoria"),
        ],
        responses={200: list},
    )
    def get(self, request):
        # Los distritos salen de `consultas`, que mira **las dos** tablas: filtrar solo por
        # FrecuenciaEmergencia dejaba fuera a los 26 distritos que declaran subtotales sin
        # desglose (ADR-D1), Cusco incluido, mientras el detalle sí los servía.
        distritos = consultas.distritos_con_emergencias(request.query_params)
        return Response([consultas.frecuencia(d) for d in distritos])


class FrecuenciaDetalleView(APIView):
    """`/api/peligros/frecuencia/{ubigeo}/` — el panel de un distrito.

    **404 cuando el distrito no tiene fila en el Excel** (hoy solo Acomayo, 080201). Es un
    estado distinto de "tiene fila y suma 0", y la UI los distingue: el primero es un vacío de
    la fuente que hay que pedirle al cliente, el segundo es un dato real.
    """

    @extend_schema(responses={200: dict, 404: dict})
    def get(self, request, ubigeo: str):
        distrito = get_object_or_404(Distrito.objects.select_related("provincia"), ubigeo=ubigeo)
        datos = consultas.frecuencia(distrito)
        if datos is None:
            raise Http404(
                f"El distrito de {distrito.nombre} no tiene fila en el registro histórico de "
                f"emergencias de la fuente."
            )
        return Response(datos)


class FrecuenciaExportView(APIView):
    """`/api/peligros/frecuencia/export.xlsx` — formato largo distrito × evento."""

    throttle_classes = [DescargaThrottle]

    @extend_schema(responses={200: bytes})
    def get(self, request):
        queryset = FrecuenciaEmergencia.objects.select_related(
            "distrito__provincia", "tipo_evento__categoria"
        )
        filtro = FrecuenciaFilter(request.query_params, queryset=queryset, request=request)

        def filas():
            for f in filtro.qs.order_by("distrito__nombre", "tipo_evento__categoria__orden"):
                yield [
                    f.distrito.provincia.nombre,
                    f.distrito.nombre,
                    f.distrito.ubigeo,
                    f.tipo_evento.categoria.nombre,
                    f.tipo_evento.nombre,
                    f.conteo,
                    f.rango_fecha,
                    f.fuente,
                    f.fuente_url,
                ]
            # Los totales declarados van en las mismas filas, marcados: si no aparecieran, el
            # Excel dejaría a Cusco en cero y contradiría al sitio (ADR-D1).
            #
            # Se acotan a los distritos que **pasan los mismos filtros**. La primera versión
            # los excluía por los ubigeos que devolvía el desglose, y con un filtro que no
            # casaba con ningún desglose esa lista salía vacía: el `exclude` no recortaba nada y
            # el Excel de un solo distrito acababa trayendo los declarados de toda la región.
            from apps.peligros.models import TotalDeclaradoEmergencias

            ubigeos = set(
                consultas.distritos_con_emergencias(request.query_params).values_list(
                    "ubigeo", flat=True
                )
            )
            declarados = TotalDeclaradoEmergencias.objects.filter(
                distrito__ubigeo__in=ubigeos
            ).select_related("distrito__provincia", "categoria")
            for t in declarados.order_by("distrito__nombre", "categoria__orden"):
                yield [
                    t.distrito.provincia.nombre,
                    t.distrito.nombre,
                    t.distrito.ubigeo,
                    t.categoria.nombre,
                    "(la fuente no desagrega por tipo de evento)",
                    t.total,
                    t.rango_fecha,
                    t.fuente,
                    t.fuente_url,
                ]

        return exports.respuesta_excel(
            "emergencias-por-distrito-cusco.xlsx",
            "Emergencias",
            ["Provincia", "Distrito", "Ubigeo", "Categoría", "Tipo de evento", "Nº emergencias",
             "Rango de fechas", "Fuente", "Enlace"],
            filas(),
            [18, 20, 10, 30, 34, 14, 16, 20, 40],
        )
