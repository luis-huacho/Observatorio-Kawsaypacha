"""Productos de incidencia: comparador de distritos y ayuda memoria PDF.

Son los dos entregables del TDR pensados para llevar a una mesa técnica, así que la exigencia
no es "que salga un documento" sino que las cifras cuadren con las de la pantalla desde la que
se pidieron. Por eso ambos leen de `apps.peligros.consultas`, igual que el API.
"""
from django.http import Http404, HttpResponse
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.medidas.models import Medida
from apps.peligros import consultas
from apps.territorio.models import CentroPoblado, Distrito

from ..filters import parametros_exposicion
from ..throttling import DescargaThrottle

MAX_DISTRITOS = 4


class ComparadorView(APIView):
    """`/api/comparador/distritos/` — tablero comparativo (requisito 5 del TDR).

    Entre 2 y 4 distritos. El techo no es arbitrario: son tarjetas lado a lado, y a partir de
    cinco dejan de caber en pantalla y de leerse en una reunión.

    No lleva bloque de inversión: la ventana está diferida (ADR-D3).
    """

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "ubigeos",
                description="Ubigeos de 6 dígitos separados por coma, entre 2 y 4.",
                required=True,
            ),
            OpenApiParameter("peligro"),
            OpenApiParameter("nivel_min", type=int),
        ],
        responses={200: dict},
    )
    def get(self, request):
        crudos = [u.strip() for u in request.query_params.get("ubigeos", "").split(",") if u.strip()]
        if not 2 <= len(crudos) <= MAX_DISTRITOS:
            raise ValidationError({
                "ubigeos": f"Indica entre 2 y {MAX_DISTRITOS} distritos separados por coma."
            })
        distritos = list(
            Distrito.objects.filter(ubigeo__in=crudos).select_related("provincia")
        )
        encontrados = {d.ubigeo for d in distritos}
        if faltan := [u for u in crudos if u not in encontrados]:
            raise ValidationError({"ubigeos": f"Ubigeo no encontrado: {', '.join(faltan)}."})

        peligro = request.query_params.get("peligro", "")
        nivel_min = request.query_params.get("nivel_min", "")

        # Se respeta el orden en que el usuario los pidió: es el orden de las columnas.
        por_ubigeo = {d.ubigeo: d for d in distritos}
        tarjetas = [
            self._tarjeta(por_ubigeo[u], peligro, nivel_min) for u in crudos
        ]
        return Response({
            "distritos": tarjetas,
            # Los periodos de observación son por distrito (23 variantes): comparar totales de
            # emergencias sin decirlo sería engañoso, así que se advierte en el propio payload.
            "advertencia_periodos": (
                "Cada distrito tiene su propio periodo de observación en la fuente, así que los "
                "totales de emergencias no son directamente comparables entre distritos."
            ),
            "inversion_disponible": False,
        })

    def _tarjeta(self, distrito, peligro: str, nivel_min) -> dict:
        ccpp = CentroPoblado.objects.filter(distrito=distrito)
        resumen = consultas.resumen(ccpp, peligro=peligro, nivel_min=nivel_min)
        return {
            "ubigeo": distrito.ubigeo,
            "distrito": distrito.nombre,
            "provincia": distrito.provincia.nombre,
            "poblacion": resumen["poblacion_total"],
            "total_ccpp": resumen["total_ccpp"],
            "por_ccpp": resumen["por_ccpp"],
            "por_peligro": resumen["por_peligro"],
            "frecuencia": consultas.frecuencia(distrito),
            "medidas_publicadas": Medida.publicados.filter(distrito=distrito).count(),
        }


class AyudaMemoriaView(APIView):
    """`/api/distritos/{ubigeo}/ayuda-memoria.pdf` — el documento de las mesas técnicas.

    El alcance es **un distrito**, con `peligro` y `nivel_min` como refinamientos opcionales:
    un reporte regional o provincial produce decenas de páginas y deja de servir para una
    reunión.
    """

    throttle_classes = [DescargaThrottle]

    @extend_schema(
        parameters=[
            OpenApiParameter("peligro"),
            OpenApiParameter("nivel_min", type=int),
            OpenApiParameter(
                "sin_mapa",
                description="`1` omite la captura del mapa (más rápido, y salida determinista "
                "para las pruebas).",
                type=bool,
            ),
        ],
        responses={200: bytes},
    )
    def get(self, request, ubigeo: str):
        from apps.informes.ayuda_memoria import generar_pdf

        distrito = Distrito.objects.filter(ubigeo=ubigeo).select_related("provincia").first()
        if distrito is None:
            raise Http404(f"No existe el distrito con ubigeo {ubigeo}.")

        peligros, niveles = parametros_exposicion(request.query_params)
        pdf, nombre = generar_pdf(
            distrito,
            peligros=peligros,
            niveles=niveles,
            con_mapa=request.query_params.get("sin_mapa") not in {"1", "true", "True"},
        )
        respuesta = HttpResponse(pdf, content_type="application/pdf")
        respuesta["Content-Disposition"] = f'attachment; filename="{nombre}"'
        return respuesta
