"""Agregados de peligros y emergencias.

Viven aquí y no en las vistas porque los consumen tres sitios: el API, la ayuda memoria PDF y
el comparador de distritos. Que los tres lean del mismo lugar es lo que garantiza que el PDF
diga lo mismo que la pantalla desde la que se pidió.
"""
import re
from statistics import median

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


#: Nota de vocabulario, porque en pantalla van al revés que aquí.
#:
#: La UI de /peligros llama **evento** a lo que el modelo llama `TipoEvento` (Huayco,
#: Deslizamiento… 21) y **tipo de evento** a lo que el modelo llama `CategoriaEvento`
#: (Geodinámica externa, Meteorológicos… 4). Los modelos no se renombran —arrastraría
#: migración, importador, admin y export por un asunto de etiqueta—, así que las funciones de
#: abajo publican `eventos` y `familias` con los nombres del modelo, y es el frontend quien
#: pone los rótulos. Quien lea `categoria_slug` bajo un título que dice «tipo de evento» está
#: viendo lo correcto.


def frecuencia_provincia(provincia) -> dict:
    """Emergencias registradas en **toda una provincia**, para el gráfico de /peligros.

    Existe porque el eje de ocurrencia solo estaba disponible distrito a distrito y la pantalla
    pregunta por provincia. Devuelve las **dos agrupaciones** que el gráfico puede pintar, y no
    suman lo mismo a propósito:

    - `eventos` (21 tipos) solo puede salir del desglose.
    - `familias` (4 categorías) suma además los **subtotales declarados** de los distritos que
      la fuente no desagrega (ADR-D1). Hoy es el distrito de Cusco, con 134 emergencias.

    Así que en la provincia de Cusco `familias` suma 608 y `eventos` 474. No es un descuadre: es
    que la fuente sabe la familia de esas 134 y no su evento. `total_sin_desglose` existe para
    que la pantalla pueda decirlo en vez de dejar que el total cambie al pulsar una casilla.

    Nunca devuelve `None`: una provincia sin ningún registro es un estado con forma —total 0,
    listas vacías— y no un 404, porque la provincia sí existe.
    """
    from apps.territorio.models import Distrito

    distritos = list(Distrito.objects.filter(provincia=provincia))
    ubigeos = [d.ubigeo for d in distritos]

    desglose = (
        FrecuenciaEmergencia.objects.filter(distrito__ubigeo__in=ubigeos)
        .values(
            "tipo_evento__nombre",
            "tipo_evento__slug",
            "tipo_evento__categoria__nombre",
            "tipo_evento__categoria__slug",
            "tipo_evento__categoria__orden",
        )
        .annotate(conteo=Sum("conteo"))
        .order_by("-conteo")
    )
    eventos = [
        {
            "evento": f["tipo_evento__nombre"],
            "slug": f["tipo_evento__slug"],
            "categoria": f["tipo_evento__categoria__nombre"],
            "categoria_slug": f["tipo_evento__categoria__slug"],
            "conteo": f["conteo"],
        }
        for f in desglose
        if f["conteo"]
    ]

    # Las familias parten del desglose y se les añaden los declarados.
    familias: dict[str, dict] = {}
    orden_familia: dict[str, int] = {}
    for f in desglose:
        slug = f["tipo_evento__categoria__slug"]
        orden_familia[slug] = f["tipo_evento__categoria__orden"]
        entrada = familias.setdefault(
            slug, {"categoria": f["tipo_evento__categoria__nombre"], "slug": slug, "conteo": 0}
        )
        entrada["conteo"] += f["conteo"]

    declarados = (
        TotalDeclaradoEmergencias.objects.filter(distrito__ubigeo__in=ubigeos)
        .values("categoria__nombre", "categoria__slug", "categoria__orden")
        .annotate(conteo=Sum("total"))
    )
    for f in declarados:
        slug = f["categoria__slug"]
        orden_familia[slug] = f["categoria__orden"]
        entrada = familias.setdefault(
            slug, {"categoria": f["categoria__nombre"], "slug": slug, "conteo": 0}
        )
        entrada["conteo"] += f["conteo"]

    # --- Cobertura y periodo -------------------------------------------------
    # Sin esto la cifra engaña por omisión: Espinar declara 77 emergencias con **1 de sus 8**
    # distritos registrados y Cusco 608 con los 8, así que parece la más tranquila de la región
    # cuando lo que le faltan son los datos.
    con_registro: list[dict] = []
    sin_desglose: list[dict] = []
    for distrito in distritos:
        datos = frecuencia(distrito)
        if not datos or not datos["total"]:
            continue
        con_registro.append(datos)
        if not datos["desglose_disponible"]:
            sin_desglose.append({"distrito": datos["distrito"], "total": datos["total"]})

    return {
        "provincia": provincia.nombre,
        "ubigeo": provincia.ubigeo,
        "total": sum(f["conteo"] for f in familias.values()),
        "distritos_con_registro": len(con_registro),
        "distritos_en_provincia": len(distritos),
        # El rango que **abarca** el conjunto, nunca «el periodo»: cada distrito trae el suyo
        # (21 variantes en la región, de 5 a 23 años) y no existe una ventana común.
        "periodo": _periodo_abarcado(con_registro),
        "periodos_distintos": len({d["rango_fecha"] for d in con_registro if d["rango_fecha"]}),
        "eventos": eventos,
        "familias": sorted(familias.values(), key=lambda f: -f["conteo"]),
        "sin_desglose": sin_desglose,
        "total_sin_desglose": sum(d["total"] for d in sin_desglose),
        "fuente": con_registro[0]["fuente"] if con_registro else None,
        "fuente_url": con_registro[0]["fuente_url"] if con_registro else None,
    }


def _periodo_abarcado(registros: list[dict]) -> str | None:
    """`"2003-2025"` a partir de los rangos sueltos de cada distrito.

    Se leen los años con una expresión regular en vez de partir por el guion: la fuente escribe
    el rango de 21 maneras distintas (`2007 - 2023`, `2003-2019`…) y el importador solo
    normaliza los espacios.
    """
    anios = [
        int(a)
        for r in registros
        if r["rango_fecha"]
        for a in re.findall(r"\d{4}", r["rango_fecha"])
    ]
    return f"{min(anios)}-{max(anios)}" if anios else None


def centroides_distritales() -> dict[str, tuple[float, float]]:
    """`{ubigeo: (lon, lat)}` derivado de los centros poblados de cada distrito.

    El visor necesita un punto donde poner el ícono de emergencias, que es un dato **por
    distrito**, y en el proyecto no hay geometría distrital: `Distrito` no tiene coordenadas y
    no existe ninguna capa de límites administrativos —solo el polígono departamental que usa
    el recorte de tiles—. Los 112 distritos sí tienen centros poblados georreferenciados, así
    que este es el único punto derivable de los datos que hay.

    **Mediana y no promedio**: en los distritos de selva de La Convención los centros poblados
    se reparten a lo largo de los ríos, y un promedio se va detrás de la cola. La mediana cae
    donde está la mayoría.

    Es una aproximación y conviene que conste: el punto no es la capital del distrito ni su
    centro geométrico, sino dónde se concentran sus centros poblados.
    """
    from apps.territorio.models import CentroPoblado

    por_distrito: dict[str, list[tuple[float, float]]] = {}
    for lon, lat, ubigeo in (
        CentroPoblado.objects.exclude(lat=None)
        .exclude(lon=None)
        .values_list("lon", "lat", "distrito_id")
    ):
        por_distrito.setdefault(ubigeo, []).append((lon, lat))

    return {
        ubigeo: (median(p[0] for p in puntos), median(p[1] for p in puntos))
        for ubigeo, puntos in por_distrito.items()
    }
