"""Ventana Inversión (PP 0068).

Tres endpoints y un export, con una división deliberada:

- **`/api/inversion/`** es el tablero: agregados, procesos, tendencia y ejercicios. Va en una
  sola petición porque esas piezas se dibujan juntas y hablan del mismo ejercicio; partirlo
  obligaría al cliente a coordinar respuestas que podrían venir de ejercicios distintos si
  alguien cambia la visibilidad entre medias.
- **`/api/inversion/entidades/`** es la tabla, y **sí** va aparte: se pagina, y el ranking se
  resuelve en el servidor. Ordenar en el cliente ordenaría solo lo que ya está cargado.
- **`/api/inversion/entidades/{codigo}/`** es la ficha de una municipalidad.

El contrato de «sin datos» se conserva tal cual: mientras ningún ejercicio esté visible, todos
responden `{disponible: false, motivo}` o 404, y el frontend muestra su estado vacío sin ningún
caso especial.
"""
from django.http import Http404, HttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_control
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.inversion import consultas
from apps.inversion.models import EntidadEjecutora

from .. import exports
from ..throttling import DescargaThrottle

MOTIVO_SIN_DATOS = "PREDES está consolidando los datos de inversión del PP 0068."

PARAMS_AMBITO = [
    OpenApiParameter("anio", int, description="Ejercicio. Por defecto, el más reciente visible."),
    OpenApiParameter(
        "ambito",
        str,
        description="municipal (por defecto), distrital, provincial, regional o todos.",
    ),
    OpenApiParameter("provincia", str, description="Ubigeo o nombre de provincia."),
]
PARAMS_MAPA = PARAMS_AMBITO + [
    OpenApiParameter(
        "nivel", str, description="distrital (por defecto) o provincial: el polígono que se pinta."
    ),
]
PARAMS_LISTADO = PARAMS_AMBITO + [
    OpenApiParameter("buscar", str, description="Texto en el nombre de la municipalidad."),
    OpenApiParameter(
        "ordenar",
        str,
        description="pim (por defecto), ejecucion, saldo, institucional o variacion.",
    ),
    OpenApiParameter(
        "comparar_con",
        int,
        description="Otro ejercicio visible: añade el bloque `comparacion` a cada fila.",
    ),
]


def _parametros(request) -> tuple[str, str]:
    ambito = (request.query_params.get("ambito") or consultas.AMBITO_POR_DEFECTO).strip()
    if ambito not in consultas.AMBITOS:
        ambito = consultas.AMBITO_POR_DEFECTO
    return ambito, (request.query_params.get("provincia") or "").strip()


def _ejercicio_comparado(request, ejercicio):
    """El ejercicio contra el que se compara, o `None`.

    Compararse consigo mismo daría una columna de ceros que parece un dato; se ignora.
    """
    pedido = request.query_params.get("comparar_con")
    if not pedido:
        return None
    otro = consultas.ejercicio_para(pedido)
    return otro if otro is not None and otro.pk != ejercicio.pk else None


class InversionView(APIView):
    """`/api/inversion/` — el tablero del PP 0068 por municipalidad."""

    @method_decorator(cache_control(max_age=300, public=True))
    @extend_schema(parameters=PARAMS_LISTADO, responses={200: dict})
    def get(self, request):
        ejercicio = consultas.ejercicio_para(request.query_params.get("anio"))
        if ejercicio is None:
            return Response({"disponible": False, "motivo": MOTIVO_SIN_DATOS})

        ambito, provincia = _parametros(request)
        comparado = _ejercicio_comparado(request, ejercicio)
        cuerpo = {
            "disponible": True,
            # Lo declara el payload y no una nota de la interfaz: cualquier cliente que dibuje
            # un % de ejecución de un corte a mitad de año tiene que poder advertirlo, y poder
            # decir de qué ejercicio es sin deducirlo por descarte (`en_curso`, `corte_legible`).
            **consultas.datos_ejercicio(ejercicio),
            "fuente": ejercicio.get_fuente_display(),
            "ambito": ambito,
            "unidad": "municipalidad (entidad ejecutora), no distrito",
            "agregados": consultas.agregados(ejercicio, ambito, provincia),
            **consultas.procesos(ejercicio, ambito, provincia),
            # El desglose de quién tiene los proyectos viaja con el agregado que lo necesita:
            # `agregados.pim_proyectos` solo se entiende sabiendo en cuántas manos está.
            "proyectos": consultas.proyectos_por_entidad(ejercicio, ambito, provincia),
            "tendencia": consultas.tendencia(ambito, provincia),
            "ejercicios": [
                consultas.datos_ejercicio(e)
                for e in consultas.Ejercicio.objects.filter(visible=True).order_by("-anio")
            ],
        }
        if comparado is not None:
            cuerpo["comparacion"] = consultas.comparacion_agregada(
                ejercicio, comparado, ambito, provincia
            )
        return Response(cuerpo)


class InversionEntidadesView(ListAPIView):
    """`/api/inversion/entidades/` — la tabla de municipalidades, paginada y ordenada en servidor.

    Se apoya en `ListAPIView` solo por la paginación: las filas no salen de un serializer sino
    de `consultas.por_entidad`, que es la misma función que alimenta el Excel. Duplicar los
    derivados en un serializer sería la forma segura de que un día no coincidan.
    """

    pagination_class = None  # se resuelve en `list`, ver abajo

    @extend_schema(parameters=PARAMS_LISTADO, responses={200: dict})
    def get(self, request, *args, **kwargs):
        ejercicio = consultas.ejercicio_para(request.query_params.get("anio"))
        if ejercicio is None:
            # Mismo sobre que una página vacía: el cliente no necesita un caso especial para
            # «todavía no hay ejercicio publicado».
            return Response({"count": 0, "next": None, "previous": None, "results": []})

        ambito, provincia = _parametros(request)
        comparado = _ejercicio_comparado(request, ejercicio)
        queryset = consultas.listado(
            ejercicio,
            ambito=ambito,
            provincia=provincia,
            ordenar=(request.query_params.get("ordenar") or "").strip(),
            buscar=request.query_params.get("buscar") or "",
            ejercicio_comparado=comparado,
        )

        from apps.api.paginacion import PaginacionEstandar

        paginador = PaginacionEstandar()
        pagina = paginador.paginate_queryset(queryset, request, view=self)
        return paginador.get_paginated_response(consultas.por_entidad(pagina, comparado))


class InversionEntidadDetalleView(APIView):
    """`/api/inversion/entidades/{codigo}/` — la ficha de una municipalidad.

    La llave es el **código MEF de la entidad ejecutora**, no el ubigeo. El árbol de rutas del
    prototipo proponía `/inversion/:ubigeo`, pero eso contradiría la unidad de análisis y
    dejaría fuera a las mancomunidades y al gobierno regional, que no tienen distrito.
    """

    @extend_schema(parameters=PARAMS_AMBITO, responses={200: dict})
    def get(self, request, codigo):
        try:
            entidad = EntidadEjecutora.objects.select_related("distrito", "provincia").get(
                codigo=codigo
            )
        except EntidadEjecutora.DoesNotExist:
            raise Http404("No hay ninguna entidad ejecutora con ese código.")

        ejercicio = consultas.ejercicio_para(request.query_params.get("anio"))
        if ejercicio is None:
            return Response({"disponible": False, "motivo": MOTIVO_SIN_DATOS})

        return Response({
            "disponible": True,
            "entidad": {
                "codigo": entidad.codigo,
                "nombre": entidad.nombre,
                "ambito": entidad.ambito,
                "ambito_nombre": entidad.get_ambito_display(),
                "ubigeo_distrito": entidad.distrito_id,
                "distrito": entidad.distrito.nombre if entidad.distrito_id else None,
                "provincia": entidad.provincia.nombre if entidad.provincia_id else None,
                # Se declara en el payload: sin distrito, esta municipalidad no se puede cruzar
                # con datos territoriales, y la ficha lo dice en vez de callarlo.
                "sin_territorio": entidad.sin_territorio,
            },
            **consultas.datos_ejercicio(ejercicio),
            "fuente": ejercicio.get_fuente_display(),
            "serie": consultas.serie_entidad(entidad),
            **consultas.procesos(ejercicio, entidad=entidad),
            "actividades": consultas.actividades_entidad(entidad, ejercicio),
            "ejercicios": [
                consultas.datos_ejercicio(e)
                for e in consultas.Ejercicio.objects.filter(visible=True).order_by("-anio")
            ],
        })


class InversionMapaView(APIView):
    """`/api/inversion/mapa/` — el coroplético por distrito o por provincia (ADR-D6).

    Va aparte del tablero porque tiene su propio eje —el `nivel`— y porque el tablero se
    dibuja igual sin él: si esta petición falla, la ventana sigue sirviendo sus cifras.
    """

    @method_decorator(cache_control(max_age=300, public=True))
    @extend_schema(parameters=PARAMS_MAPA, responses={200: dict})
    def get(self, request):
        ejercicio = consultas.ejercicio_para(request.query_params.get("anio"))
        if ejercicio is None:
            return Response({"disponible": False, "motivo": MOTIVO_SIN_DATOS})

        ambito, provincia = _parametros(request)
        return Response({
            "disponible": True,
            **consultas.datos_ejercicio(ejercicio),
            **consultas.mapa(
                ejercicio,
                ambito=ambito,
                provincia=provincia,
                nivel=(request.query_params.get("nivel") or "").strip(),
            ),
        })


class InversionReporteView(APIView):
    """`/api/inversion/reporte.pdf` — el tablero de la ventana, en un documento.

    El hermano de la ayuda memoria de `/peligros`: mismo membrete, misma maqueta y la misma
    exigencia de que sus cifras cuadren con las de la pantalla desde la que se pidió. Lleva las
    gráficas (en SVG, porque WeasyPrint no ejecuta JavaScript), el mapa y la tabla completa.

    Sin ejercicio visible **no da 404**: devuelve un documento de una página que explica el
    vacío, por el mismo criterio con el que el Excel trae su hoja «Sin datos».
    """

    throttle_classes = [DescargaThrottle]

    @extend_schema(
        parameters=PARAMS_MAPA + [
            OpenApiParameter("ordenar", str, description="El orden de la tabla, como el listado."),
            OpenApiParameter(
                "sin_mapa",
                bool,
                description="`1` omite la captura del mapa (más rápido, y salida determinista "
                "para las pruebas).",
            ),
        ],
        responses={200: bytes},
    )
    def get(self, request):
        from apps.informes.reporte_inversion import generar_pdf

        ambito, provincia = _parametros(request)
        pdf, nombre = generar_pdf(
            anio=request.query_params.get("anio"),
            ambito=ambito,
            provincia=provincia,
            ordenar=(request.query_params.get("ordenar") or "").strip(),
            nivel=(request.query_params.get("nivel") or "").strip()
            or consultas.NIVEL_POR_DEFECTO,
            metrica=(request.query_params.get("metrica") or "").strip(),
            con_mapa=request.query_params.get("sin_mapa") not in {"1", "true", "True"},
        )
        respuesta = HttpResponse(pdf, content_type="application/pdf")
        respuesta["Content-Disposition"] = f'attachment; filename="{nombre}"'
        return respuesta


class InversionExportView(APIView):
    """`/api/inversion/export.xlsx` — la misma tabla que se ve, con sus derivados y sin paginar."""

    throttle_classes = [DescargaThrottle]

    @extend_schema(parameters=PARAMS_LISTADO, responses={200: bytes})
    def get(self, request):
        ejercicio = consultas.ejercicio_para(request.query_params.get("anio"))
        if ejercicio is None:
            # Un Excel vacío se abriría igual y parecería que no hay presupuesto. Mejor una
            # sola hoja que diga por qué no hay nada que descargar.
            return exports.respuesta_excel(
                "inversion-pp0068-sin-datos.xlsx", "Sin datos", ["Motivo"], [[MOTIVO_SIN_DATOS]]
            )

        ambito, provincia = _parametros(request)
        comparado = _ejercicio_comparado(request, ejercicio)
        queryset = consultas.listado(
            ejercicio,
            ambito=ambito,
            provincia=provincia,
            ordenar=(request.query_params.get("ordenar") or "").strip(),
            buscar=request.query_params.get("buscar") or "",
            ejercicio_comparado=comparado,
        )
        filas = consultas.por_entidad(queryset, comparado)
        nombre = f"inversion-pp0068-{ejercicio.anio}"
        if comparado is not None:
            nombre += f"-vs-{comparado.anio}"
        return exports.respuesta_excel(
            f"{nombre}.xlsx",
            f"PP 0068 {ejercicio.anio}",
            exports.cabeceras_inversion(comparado),
            exports.filas_inversion(filas, ejercicio, comparado),
            exports.anchos_inversion(comparado),
        )
