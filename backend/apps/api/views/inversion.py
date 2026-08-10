"""Ventana Inversión (PP 0068).

Un solo endpoint con todo lo que pinta la página, más su export. Va en una petición porque las
cuatro piezas —cabecera, procesos, tendencia y tabla— se dibujan juntas y hablan del mismo
ejercicio: partirlo obligaría al cliente a coordinar cuatro respuestas que podrían venir de
ejercicios distintos si alguien cambia la visibilidad entre medias.

El contrato de «sin datos» se conserva tal cual estaba cuando la ventana estaba diferida
(ADR-D3): mientras ningún ejercicio esté visible, responde `{disponible: false, motivo}` y el
frontend muestra su estado vacío sin ningún caso especial.
"""
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_control
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.inversion import consultas

from .. import exports
from ..throttling import DescargaThrottle

MOTIVO_SIN_DATOS = "PREDES está consolidando los datos de inversión del PP 0068."

PARAMS = [
    OpenApiParameter("anio", int, description="Ejercicio. Por defecto, el más reciente visible."),
    OpenApiParameter(
        "ambito",
        str,
        description="municipal (por defecto), distrital, provincial, regional o todos.",
    ),
    OpenApiParameter("provincia", str, description="Ubigeo o nombre de provincia."),
]


def _parametros(request) -> tuple[str, str]:
    ambito = (request.query_params.get("ambito") or consultas.AMBITO_POR_DEFECTO).strip()
    if ambito not in consultas.AMBITOS:
        ambito = consultas.AMBITO_POR_DEFECTO
    return ambito, (request.query_params.get("provincia") or "").strip()


class InversionView(APIView):
    """`/api/inversion/` — el tablero del PP 0068 por municipalidad."""

    @method_decorator(cache_control(max_age=300, public=True))
    @extend_schema(parameters=PARAMS, responses={200: dict})
    def get(self, request):
        ejercicio = consultas.ejercicio_para(request.query_params.get("anio"))
        if ejercicio is None:
            return Response({"disponible": False, "motivo": MOTIVO_SIN_DATOS})

        ambito, provincia = _parametros(request)
        return Response({
            "disponible": True,
            "anio": ejercicio.anio,
            "corte": ejercicio.corte,
            # Lo declara el payload y no una nota de la interfaz: cualquier cliente que dibuje
            # un % de ejecución de un corte a mitad de año tiene que poder advertirlo.
            "es_parcial": ejercicio.es_parcial,
            "fuente": ejercicio.get_fuente_display(),
            "ambito": ambito,
            "unidad": "municipalidad (entidad ejecutora), no distrito",
            "agregados": consultas.agregados(ejercicio, ambito, provincia),
            **consultas.procesos(ejercicio, ambito, provincia),
            "tendencia": consultas.tendencia(ambito, provincia),
            "por_entidad": consultas.por_entidad(ejercicio, ambito, provincia),
            "ejercicios": [
                {"anio": e.anio, "corte": e.corte, "es_parcial": e.es_parcial}
                for e in consultas.Ejercicio.objects.filter(visible=True).order_by("-anio")
            ],
        })


class InversionExportView(APIView):
    """`/api/inversion/export.xlsx` — la misma tabla que se ve, con sus derivados."""

    throttle_classes = [DescargaThrottle]

    @extend_schema(parameters=PARAMS, responses={200: bytes})
    def get(self, request):
        ejercicio = consultas.ejercicio_para(request.query_params.get("anio"))
        if ejercicio is None:
            # Un Excel vacío se abriría igual y parecería que no hay presupuesto. Mejor una
            # sola hoja que diga por qué no hay nada que descargar.
            return exports.respuesta_excel(
                "inversion-pp0068-sin-datos.xlsx", "Sin datos", ["Motivo"], [[MOTIVO_SIN_DATOS]]
            )

        ambito, provincia = _parametros(request)
        filas = consultas.por_entidad(ejercicio, ambito, provincia)
        return exports.respuesta_excel(
            f"inversion-pp0068-{ejercicio.anio}.xlsx",
            f"PP 0068 {ejercicio.anio}",
            exports.CABECERAS_INVERSION,
            exports.filas_inversion(filas, ejercicio),
            exports.ANCHOS_INVERSION,
        )
