"""Agregados de peligros y emergencias.

Viven aquí y no en las vistas porque los consumen tres sitios: el API, la ayuda memoria PDF y
el comparador de distritos. Que los tres lean del mismo lugar es lo que garantiza que el PDF
diga lo mismo que la pantalla desde la que se pidió.
"""
from django.db.models import Count, Q, Sum

from apps.peligros.models import (
    ClasificacionPeligro,
    FrecuenciaEmergencia,
    TipoPeligro,
    TotalDeclaradoEmergencias,
)


def distritos_con_emergencias(params=None):
    """Distritos que tienen **algo que mostrar** de emergencias, según los filtros pedidos.

    Mira las dos tablas, y ahí está la razón de existir de esta función: consultar solo
    `FrecuenciaEmergencia` deja fuera a los 26 distritos que declaran subtotales sin desglose
    (ADR-D1) —entre ellos Cusco, que es el caso que motivó el ADR—, así que la tabla y el export
    perdían justo los distritos que el ADR existe para no perder. El detalle sí los servía, de
    modo que el sitio se contradecía consigo mismo sin que nada fallara.

    `params` acepta los mismos filtros que el resto de la familia: `distrito` y `provincia` por
    ubigeo o nombre, y `categoria` por slug.
    """
    from apps.territorio.models import Distrito

    params = params or {}
    tiene_desglose = Q(frecuencias__isnull=False)
    tiene_declarado = Q(totales_declarados__isnull=False)
    if categoria := (params.get("categoria") or "").strip():
        tiene_desglose &= Q(frecuencias__tipo_evento__categoria__slug=categoria)
        tiene_declarado &= Q(totales_declarados__categoria__slug=categoria)

    queryset = Distrito.objects.filter(tiene_desglose | tiene_declarado).distinct()

    if valor := (params.get("distrito") or "").strip():
        queryset = _por_ubigeo_o_nombre(queryset, "ubigeo", "nombre", valor)
    if valor := (params.get("provincia") or "").strip():
        queryset = _por_ubigeo_o_nombre(queryset, "provincia__ubigeo", "provincia__nombre", valor)
    return queryset.select_related("provincia").order_by("nombre")


def _por_ubigeo_o_nombre(queryset, campo_ubigeo: str, campo_nombre: str, valor: str):
    """Igual que en `api.filters`: el cliente manda ubigeo cuando lo tiene y nombre cuando no."""
    if valor.isdigit():
        return queryset.filter(**{campo_ubigeo: valor})
    return queryset.filter(**{f"{campo_nombre}__iexact": valor})


def resumen(queryset_ccpp, peligros=(), niveles=(), *, peligro: str = "", nivel_min="") -> dict:
    """Cifras de la grilla de resultados y de la portada.

    Devuelve **las dos unidades, rotuladas**, porque difieren en 3.4× y confundirlas fue un
    error real del prototipo:

    - `por_ccpp`: centros poblados contados una vez, en su nivel máximo. Es la unidad de la
      tabla y del color de los símbolos del mapa.
    - `por_peligro`: filas de clasificación. Un CCPP aporta una por cada peligro evaluado, así
      que los 75 centros poblados de Acomayo suman 225.

    `peligro`/`nivel_min` se aceptan como compatibilidad (los emiten el comparador y la ayuda
    memoria) y se traducen con el mismo parser que usa el API, para que no haya dos lecturas.
    """
    from apps.api.filters import anotar_nivel, condicion_clasificacion_local, parametros_exposicion

    if not peligros and not niveles and (peligro or nivel_min):
        peligros, niveles = parametros_exposicion(
            {"peligro": peligro, "nivel_min": nivel_min}
        )

    total_ccpp = queryset_ccpp.count()
    poblacion_total = queryset_ccpp.aggregate(t=Sum("poblacion"))["t"] or 0

    # --- Por centro poblado (nivel máximo) ---------------------------------
    # El conteo se hace en Python sobre una fila por centro poblado. Encadenar
    # `.values("nivel").annotate(Count(...))` sobre la anotación **no funciona**: Django
    # reagrupa por `nivel`, el `Max` se calcula sobre el grupo entero y el `Count` acaba
    # contando filas del join. Con los 3 peligros de Acomayo eso daba 225 donde hay 75
    # centros poblados, que es exactamente el error que este bloque existe para evitar.
    anotado = anotar_nivel(queryset_ccpp, peligros=peligros, niveles=niveles)
    niveles_ccpp = {str(n): 0 for n in range(1, 5)}
    sin_clasificar = 0
    for nivel in anotado.order_by().values_list("nivel", flat=True):
        if nivel is None:
            sin_clasificar += 1
        else:
            niveles_ccpp[str(nivel)] += 1

    # --- Por peligro (clasificaciones) ------------------------------------
    filtro = Q(centro_poblado__in=queryset_ccpp.values("pk"))
    filtro &= condicion_clasificacion_local(peligros, niveles)

    conteos: dict[str, dict[str, int]] = {}
    for fila in (
        ClasificacionPeligro.objects.filter(filtro)
        .values("tipo_peligro__slug", "nivel")
        .annotate(n=Count("id"))
    ):
        por_nivel = conteos.setdefault(fila["tipo_peligro__slug"], {})
        por_nivel[str(fila["nivel"])] = fila["n"]

    por_peligro = []
    for tipo in TipoPeligro.objects.all():
        if peligros and tipo.slug not in peligros:
            continue
        niveles_tipo = {str(n): 0 for n in range(1, 5)}
        niveles_tipo.update(conteos.get(tipo.slug, {}))
        evaluados = sum(niveles_tipo.values())
        por_peligro.append({
            "peligro": tipo.nombre,
            "slug": tipo.slug,
            "niveles": niveles_tipo,
            # Centros poblados con ESTE peligro tras los filtros. Coincide con la suma de
            # `niveles` y no es casualidad: `unica_clasificacion_ccpp_peligro` impide que un
            # centro poblado tenga dos filas del mismo peligro, así que dentro de una fila las
            # dos unidades son la misma. Se publica con su nombre para que la grilla de
            # resultados pueda rotular «centros poblados» sin que nadie tenga que deducirlo.
            "centros_poblados": evaluados,
            # Centros poblados del ámbito sin clasificación de ESTE peligro. Ausencia de dato
            # no es ausencia de riesgo: es un vacío de información, y se reporta como tal.
            "sin_dato": total_ccpp - evaluados,
        })

    return {
        "total_ccpp": total_ccpp,
        # No lo usa /peligros —la población salió del visor por ilegible como escala— pero sí
        # el comparador de distritos, que la publica como población del ámbito.
        "poblacion_total": poblacion_total,
        "por_ccpp": {"niveles": niveles_ccpp, "sin_clasificar": sin_clasificar},
        "por_peligro": por_peligro,
        # Se declara la unidad de cada bloque en el propio payload: cualquier cliente que
        # dibuje una de las dos distribuciones tiene que poder rotularla.
        "unidades": {
            "por_ccpp": "centros poblados, por su nivel máximo",
            "por_peligro": "clasificaciones (un centro poblado aporta una por peligro evaluado)",
        },
    }


def frecuencia(distrito) -> dict | None:
    """Emergencias históricas de un distrito, según el contrato del spec 02.

    Devuelve `None` cuando el distrito **no tiene fila** en el Excel (hoy solo Acomayo): eso es
    un 404, distinto de un distrito con fila y `total: 0`. Son dos estados vacíos y la UI los
    distingue.
    """
    desglose = list(
        FrecuenciaEmergencia.objects.filter(distrito=distrito)
        .select_related("tipo_evento__categoria")
        .order_by("tipo_evento__categoria__orden", "-conteo")
    )
    declarados = list(
        TotalDeclaradoEmergencias.objects.filter(distrito=distrito)
        .select_related("categoria")
        .order_by("categoria__orden")
    )
    if not desglose and not declarados:
        return None

    origen = desglose[0] if desglose else declarados[0]
    categorias: list[dict] = []

    if desglose:
        por_categoria: dict[str, dict] = {}
        for fila in desglose:
            cat = fila.tipo_evento.categoria
            entrada = por_categoria.setdefault(
                cat.slug,
                {"categoria": cat.nombre, "slug": cat.slug, "total": 0,
                 "solo_total": False, "eventos": []},
            )
            entrada["total"] += fila.conteo
            entrada["eventos"].append({
                "evento": fila.tipo_evento.nombre,
                "slug": fila.tipo_evento.slug,
                "conteo": fila.conteo,
            })
        categorias = list(por_categoria.values())
    else:
        # ADR-D1: la fuente declara subtotales y no desagrega. Se muestran los declarados con
        # `solo_total`, que es lo que la UI usa para decirlo en vez de dibujar un gráfico vacío.
        categorias = [
            {
                "categoria": t.categoria.nombre,
                "slug": t.categoria.slug,
                "total": t.total,
                "solo_total": True,
                "eventos": [],
            }
            for t in declarados
        ]

    return {
        "distrito": distrito.nombre,
        "ubigeo": distrito.ubigeo,
        "provincia": distrito.provincia.nombre,
        # El periodo es POR DISTRITO (23 variantes distintas): ningún agregado provincial o
        # regional puede anunciar uno, y los totales entre distritos no son comparables sin
        # decirlo.
        "rango_fecha": origen.rango_fecha or None,
        "fuente": origen.fuente or None,
        "fuente_url": origen.fuente_url or None,
        "desglose_disponible": bool(desglose),
        "categorias": categorias,
        "total": sum(c["total"] for c in categorias),
    }
