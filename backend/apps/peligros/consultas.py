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


def resumen(queryset_ccpp, peligro: str = "", nivel_min="") -> dict:
    """Cifras del panel de distribución y de la portada.

    Devuelve **las dos unidades, rotuladas**, porque difieren en 3.4× y confundirlas fue un
    error real del prototipo:

    - `por_ccpp`: centros poblados contados una vez, en su nivel máximo. Es la unidad de la
      tabla y del mapa, y la única con la que el umbral de "nivel mínimo" se lee bien.
    - `por_peligro`: filas de clasificación. Un CCPP aporta una por cada peligro evaluado, así
      que los 75 centros poblados de Acomayo suman 225.
    """
    from apps.api.filters import anotar_nivel

    total_ccpp = queryset_ccpp.count()
    poblacion_total = queryset_ccpp.aggregate(t=Sum("poblacion"))["t"] or 0

    # --- Por centro poblado (nivel máximo) ---------------------------------
    # El conteo se hace en Python sobre una fila por centro poblado. Encadenar
    # `.values("nivel").annotate(Count(...))` sobre la anotación **no funciona**: Django
    # reagrupa por `nivel`, el `Max` se calcula sobre el grupo entero y el `Count` acaba
    # contando filas del join. Con los 3 peligros de Acomayo eso daba 225 donde hay 75
    # centros poblados, que es exactamente el error que este bloque existe para evitar.
    anotado = anotar_nivel(queryset_ccpp, peligro=peligro, nivel_min=nivel_min)
    niveles_ccpp = {str(n): 0 for n in range(1, 5)}
    sin_clasificar = 0
    for nivel in anotado.order_by().values_list("nivel", flat=True):
        if nivel is None:
            sin_clasificar += 1
        else:
            niveles_ccpp[str(nivel)] += 1

    # --- Por peligro (clasificaciones) ------------------------------------
    # La condición se rearma con los campos locales: `filters.condicion_clasificacion` está
    # escrita desde CentroPoblado (`clasificaciones__…`) y aquí se consulta desde la propia
    # ClasificacionPeligro.
    filtro = Q(centro_poblado__in=queryset_ccpp.values("pk"))
    if peligro:
        filtro &= Q(tipo_peligro__slug=peligro) | Q(tipo_peligro__nombre__iexact=peligro)
    try:
        minimo = int(nivel_min)
    except (TypeError, ValueError):
        minimo = 0
    if minimo:
        filtro &= Q(nivel__gte=minimo)

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
        if peligro and tipo.slug != peligro and tipo.nombre.lower() != peligro.lower():
            continue
        niveles = {str(n): 0 for n in range(1, 5)}
        niveles.update(conteos.get(tipo.slug, {}))
        evaluados = sum(niveles.values())
        por_peligro.append({
            "peligro": tipo.nombre,
            "slug": tipo.slug,
            "niveles": niveles,
            # Centros poblados del ámbito sin clasificación de ESTE peligro. Ausencia de dato
            # no es ausencia de riesgo: es un vacío de información, y se reporta como tal.
            "sin_dato": total_ccpp - evaluados,
        })

    return {
        "total_ccpp": total_ccpp,
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
