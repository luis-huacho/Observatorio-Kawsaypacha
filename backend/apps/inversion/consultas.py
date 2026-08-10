"""Agregados y derivados de Inversión.

Viven aquí y no en las vistas por la misma razón que `apps.peligros.consultas`: los leen el API,
el export a Excel y el admin, y que los tres calculen el % de ejecución por su cuenta es la
forma segura de que un día no coincidan.

Ningún derivado se guarda. Todos salen de `PresupuestoEntidad` (totales) y `PresupuestoActividad`
(el grano fino), así que una corrección del catálogo se ve en el siguiente request.
"""
from decimal import Decimal

from django.db.models import (
    DecimalField,
    ExpressionWrapper,
    F,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce, NullIf

from apps.inversion.models import (
    Ejercicio,
    EntidadEjecutora,
    PresupuestoActividad,
    PresupuestoEntidad,
    ProcesoGRD,
)

CERO = Decimal("0")

#: Ámbitos que la ventana ofrece. «municipal» es el que responde a la pregunta del cliente:
#: cómo ejecutan las municipalidades. El regional y el nacional se guardan porque están en la
#: fuente y sirven de contexto, pero mezclarlos en el mismo ranking compararía un pliego de
#: miles de millones con una municipalidad distrital.
AMBITOS = {
    "municipal": [EntidadEjecutora.Ambito.DISTRITAL, EntidadEjecutora.Ambito.PROVINCIAL],
    "distrital": [EntidadEjecutora.Ambito.DISTRITAL],
    "provincial": [EntidadEjecutora.Ambito.PROVINCIAL],
    "regional": [EntidadEjecutora.Ambito.REGIONAL],
    "todos": list(EntidadEjecutora.Ambito.values),
}
AMBITO_POR_DEFECTO = "municipal"


def _suma(campo):
    return Coalesce(Sum(campo), Value(CERO), output_field=DecimalField(max_digits=18,
                                                                      decimal_places=2))


def ejercicio_para(anio=None) -> Ejercicio | None:
    """El ejercicio que hay que mostrar: el pedido si es visible, si no el más reciente visible.

    Un `anio` que no existe o que está oculto **no cae al último**: devuelve None y el API
    responde su estado vacío. Servir otro año que el pedido sería peor que no servir nada,
    porque el gráfico se vería bien y las cifras serían de otro ejercicio.
    """
    visibles = Ejercicio.objects.filter(visible=True)
    if anio:
        try:
            return visibles.get(anio=int(anio))
        except (Ejercicio.DoesNotExist, TypeError, ValueError):
            return None
    return visibles.order_by("-anio").first()


def entidades(ambito: str = AMBITO_POR_DEFECTO, provincia: str = ""):
    """Queryset de entidades del ámbito pedido, opcionalmente acotado a una provincia."""
    queryset = EntidadEjecutora.objects.filter(
        ambito__in=AMBITOS.get(ambito, AMBITOS[AMBITO_POR_DEFECTO])
    )
    if valor := (provincia or "").strip():
        # Igual que en `api.filters`: el cliente manda ubigeo cuando lo tiene y nombre cuando no.
        if valor.isdigit():
            queryset = queryset.filter(provincia__ubigeo=valor)
        else:
            queryset = queryset.filter(provincia__nombre__iexact=valor)
    return queryset


#: Claves de ordenación de la tabla de municipalidades. Los tres primeros son los rankings que
#: pide la hoja «Campos» del cliente; `variacion` solo tiene sentido comparando dos ejercicios.
#:
#: El orden se resuelve en SQL y no en Python porque la tabla se pagina: ordenar la página ya
#: recibida daría un «ranking» que solo ordena lo que se ha cargado.
ORDENES = {
    "pim": "pim",
    "ejecucion": "pct_ejecucion",
    "saldo": "saldo",
    "institucional": "pct_institucional",
    "variacion": "delta_pim",
}
ORDEN_POR_DEFECTO = "pim"

#: Denominador seguro: `NULLIF(x, 0)` deja la división en NULL en vez de reventar, y así los
#: «no se puede calcular» viajan como nulos y acaban al final del orden.
_DECIMAL = DecimalField(max_digits=20, decimal_places=10)


def anotar_derivados(queryset, ejercicio_comparado=None):
    """Anota en SQL los derivados por los que se puede ordenar.

    Se anotan aunque no se vayan a ordenar por ellos: son baratos y dejan la consulta lista
    para cualquier `ordenar` sin ramificar el queryset.
    """
    queryset = queryset.annotate(
        saldo=ExpressionWrapper(F("pim") - F("devengado"), output_field=_DECIMAL),
        pct_ejecucion=ExpressionWrapper(
            F("devengado") / NullIf(F("pim"), Value(CERO)), output_field=_DECIMAL
        ),
        pct_institucional=ExpressionWrapper(
            F("pim") / NullIf(F("pim_institucional"), Value(CERO)), output_field=_DECIMAL
        ),
    )
    if ejercicio_comparado is None:
        # Sin comparación no hay delta. Se anota como NULL para que `ordenar=variacion` no
        # rompa la consulta: simplemente deja todas las filas empatadas y desempata el código.
        return queryset.annotate(delta_pim=Value(None, output_field=_DECIMAL))

    pim_comparado = Subquery(
        PresupuestoEntidad.objects.filter(
            entidad=OuterRef("entidad"), ejercicio=ejercicio_comparado
        ).values("pim")[:1],
        output_field=_DECIMAL,
    )
    return queryset.annotate(
        pim_comparado=pim_comparado,
        delta_pim=ExpressionWrapper(F("pim") - pim_comparado, output_field=_DECIMAL),
    )


def ordenar_listado(queryset, ordenar: str = ORDEN_POR_DEFECTO):
    """Aplica el orden pedido **con desempate estable por código de entidad**.

    El desempate no es cosmético: sin un orden total, dos filas empatadas pueden salir en
    distinto orden en dos consultas y la paginación repite unas y se salta otras. Es el mismo
    motivo por el que el listado de centros poblados desempata por nombre.
    """
    campo = ORDENES.get(ordenar, ORDENES[ORDEN_POR_DEFECTO])
    return queryset.order_by(F(campo).desc(nulls_last=True), "entidad__codigo")


def listado(ejercicio, ambito=AMBITO_POR_DEFECTO, provincia="", ordenar=ORDEN_POR_DEFECTO,
            buscar="", ejercicio_comparado=None):
    """Queryset de `PresupuestoEntidad` listo para paginar, filtrar y exportar.

    Lo comparten el listado paginado y el Excel, para que el archivo salga exactamente de la
    misma consulta que la pantalla —mismo criterio que `CentroPobladoExportView`—.
    """
    queryset = PresupuestoEntidad.objects.filter(
        ejercicio=ejercicio, entidad__in=entidades(ambito, provincia)
    ).select_related("entidad__distrito", "entidad__provincia", "ejercicio")
    if texto := (buscar or "").strip():
        queryset = queryset.filter(entidad__nombre__icontains=texto)
    return ordenar_listado(anotar_derivados(queryset, ejercicio_comparado), ordenar)


def _o_nulo(valor):
    """`float` o `None`. Nunca convierte un dato ausente en un cero."""
    return float(valor) if valor is not None else None


def _porcentaje(parte, total):
    """Fracción 0-1, o None cuando no hay denominador.

    Devolver None y no 0 es deliberado: «no se puede calcular» y «es cero» se dibujan distinto,
    y una municipalidad sin total institucional no tiene un 0 % de su presupuesto en el 0068.
    """
    if total in (None, CERO, 0):
        return None
    return float(Decimal(parte or CERO) / Decimal(total))


def fila_entidad(presupuesto: PresupuestoEntidad, reparto: dict | None = None) -> dict:
    """Una fila de la tabla de municipalidades, con sus derivados."""
    entidad = presupuesto.entidad
    pim, pia, devengado = presupuesto.pim, presupuesto.pia, presupuesto.devengado
    reparto = reparto or {}
    return {
        "codigo": entidad.codigo,
        "entidad": entidad.nombre,
        "ambito": entidad.ambito,
        "ubigeo_distrito": entidad.distrito_id,
        "distrito": entidad.distrito.nombre if entidad.distrito_id else None,
        "provincia": entidad.provincia.nombre if entidad.provincia_id else None,
        "pia": float(pia),
        "pim": float(pim),
        "devengado": float(devengado),
        "pct_ejecucion": _porcentaje(devengado, pim),
        # Lo que falta por gastar de lo aprobado. Es uno de los tres rankings que pide la hoja
        # «Campos», y el que señala el presupuesto parado.
        "saldo": float(pim - devengado),
        # Cuánto se reprogramó respecto de lo que se aprobó al abrir el año: responde a la
        # primera mitad de «¿se está ejecutando lo proyectado?».
        "variacion_pia_pim": float(pim - pia),
        "pct_variacion_pia_pim": _porcentaje(pim - pia, pia),
        # El presupuesto de la entidad entera, que es el contexto del 0068. Los tres van
        # nulables: solo existen para las entidades que ejecutan desde el departamento, y una
        # municipalidad sin este dato no tiene un presupuesto institucional de cero.
        "pia_institucional": _o_nulo(presupuesto.pia_institucional),
        "pim_institucional": _o_nulo(presupuesto.pim_institucional),
        "devengado_institucional": _o_nulo(presupuesto.devengado_institucional),
        "pct_0068_institucional": _porcentaje(pim, presupuesto.pim_institucional),
        "pim_proyectos": float(reparto.get("proyecto", CERO)),
        "pim_actividades": float(reparto.get("actividad", CERO)),
        "pct_proyectos": _porcentaje(reparto.get("proyecto", CERO), pim),
    }


def son_comparables(a: Ejercicio, b: Ejercicio) -> bool:
    """Dos ejercicios comparan sus porcentajes de ejecución solo si tienen el mismo tipo de corte.

    Un 47.7 % a junio contra un 83 % de año cerrado no es una caída de ejecución: son dos
    medidas distintas. La comparación **se muestra igual, marcada** (ver el ADR), y este campo
    es lo que permite marcarla en todas partes —pantalla y Excel— sin que cada cliente tenga
    que redescubrir la regla.
    """
    return a.es_parcial == b.es_parcial


def comparacion_fila(presupuesto: PresupuestoEntidad, otro: PresupuestoEntidad | None,
                     ejercicio_comparado: Ejercicio) -> dict:
    """Bloque de comparación de una municipalidad contra otro ejercicio.

    `otro` es `None` cuando la municipalidad no tenía presupuesto del 0068 ese año: sus deltas
    son `None`, no cero. Aparecer de la nada no es lo mismo que no haber cambiado.
    """
    comparable = son_comparables(presupuesto.ejercicio, ejercicio_comparado)
    if otro is None:
        return {
            "anio": ejercicio_comparado.anio,
            "corte": ejercicio_comparado.corte,
            "es_parcial": ejercicio_comparado.es_parcial,
            "comparable": comparable,
            "sin_presupuesto": True,
            "pia": None, "pim": None, "devengado": None, "pct_ejecucion": None,
            "delta_pim": None, "pct_delta_pim": None,
            "delta_devengado": None, "delta_pct_ejecucion": None,
        }

    pct_actual = _porcentaje(presupuesto.devengado, presupuesto.pim)
    pct_otro = _porcentaje(otro.devengado, otro.pim)
    return {
        "anio": ejercicio_comparado.anio,
        "corte": ejercicio_comparado.corte,
        "es_parcial": ejercicio_comparado.es_parcial,
        "comparable": comparable,
        "sin_presupuesto": False,
        "pia": float(otro.pia),
        "pim": float(otro.pim),
        "devengado": float(otro.devengado),
        "pct_ejecucion": pct_otro,
        "delta_pim": float(presupuesto.pim - otro.pim),
        "pct_delta_pim": _porcentaje(presupuesto.pim - otro.pim, otro.pim),
        "delta_devengado": float(presupuesto.devengado - otro.devengado),
        # Se calcula aunque no sea comparable: la decisión fue mostrarlo marcado, no ocultarlo.
        # Quien lo pinte tiene `comparable` al lado para decir que no es una caída real.
        "delta_pct_ejecucion": (
            None if pct_actual is None or pct_otro is None else pct_actual - pct_otro
        ),
    }


def comparacion_agregada(ejercicio, ejercicio_comparado, ambito=AMBITO_POR_DEFECTO,
                         provincia="") -> dict:
    """Los agregados del ejercicio comparado y sus deltas, para la cabecera de la comparación."""
    otros = agregados(ejercicio_comparado, ambito, provincia)
    actuales = agregados(ejercicio, ambito, provincia)
    return {
        "anio": ejercicio_comparado.anio,
        "corte": ejercicio_comparado.corte,
        "es_parcial": ejercicio_comparado.es_parcial,
        "comparable": son_comparables(ejercicio, ejercicio_comparado),
        "agregados": otros,
        "deltas": {
            "pia": actuales["pia"] - otros["pia"],
            "pim": actuales["pim"] - otros["pim"],
            "devengado": actuales["devengado"] - otros["devengado"],
            "pct_pim": _porcentaje(
                Decimal(str(actuales["pim"] - otros["pim"])), Decimal(str(otros["pim"]))
            ),
            "pct_ejecucion": (
                None
                if actuales["pct_ejecucion"] is None or otros["pct_ejecucion"] is None
                else actuales["pct_ejecucion"] - otros["pct_ejecucion"]
            ),
        },
    }


def _reparto_por_origen(ejercicio, queryset_entidades) -> dict[str, dict[str, Decimal]]:
    """PIM por entidad y origen (proyecto / actividad), para el % de proyectos vs actividades."""
    filas = (
        PresupuestoActividad.objects.filter(ejercicio=ejercicio, entidad__in=queryset_entidades)
        .values("entidad__codigo", "clasificacion__origen")
        .annotate(pim=_suma("pim"))
    )
    reparto: dict[str, dict[str, Decimal]] = {}
    for fila in filas:
        reparto.setdefault(fila["entidad__codigo"], {})[fila["clasificacion__origen"]] = fila["pim"]
    return reparto


def por_entidad(presupuestos, ejercicio_comparado=None) -> list[dict]:
    """Convierte una **página** de `PresupuestoEntidad` en filas de la tabla.

    Recibe ya la lista paginada y resuelve de una sola consulta lo que cada fila necesita
    —el reparto proyectos/actividades y, si se compara, el presupuesto del otro ejercicio—,
    acotado a los códigos de la página. Hacerlo fila a fila sería una consulta por
    municipalidad.
    """
    presupuestos = list(presupuestos)
    if not presupuestos:
        return []

    codigos = [p.entidad.codigo for p in presupuestos]
    ejercicio = presupuestos[0].ejercicio
    reparto = _reparto_por_origen(ejercicio, EntidadEjecutora.objects.filter(codigo__in=codigos))

    comparados: dict[str, PresupuestoEntidad] = {}
    if ejercicio_comparado is not None:
        comparados = {
            p.entidad.codigo: p
            for p in PresupuestoEntidad.objects.filter(
                ejercicio=ejercicio_comparado, entidad__codigo__in=codigos
            ).select_related("entidad")
        }

    filas = []
    for presupuesto in presupuestos:
        fila = fila_entidad(presupuesto, reparto.get(presupuesto.entidad.codigo))
        if ejercicio_comparado is not None:
            fila["comparacion"] = comparacion_fila(
                presupuesto, comparados.get(presupuesto.entidad.codigo), ejercicio_comparado
            )
        filas.append(fila)
    return filas


def agregados(ejercicio, ambito=AMBITO_POR_DEFECTO, provincia="") -> dict:
    """Las cifras de cabecera: PIA/PIM/devengado del ámbito y sus derivados."""
    queryset_entidades = entidades(ambito, provincia)
    base = PresupuestoEntidad.objects.filter(ejercicio=ejercicio, entidad__in=queryset_entidades)

    totales = base.aggregate(pia=_suma("pia"), pim=_suma("pim"), devengado=_suma("devengado"))
    reparto = (
        PresupuestoActividad.objects.filter(ejercicio=ejercicio, entidad__in=queryset_entidades)
        .values("clasificacion__origen")
        .annotate(pim=_suma("pim"))
    )
    pim_por_origen = {f["clasificacion__origen"]: f["pim"] for f in reparto}

    # El total institucional y el % sobre él salen del **mismo universo**: solo las entidades
    # que tienen ese dato. Mezclar un numerador de 116 municipalidades con un denominador de
    # 114 inflaría el porcentaje sin que nada lo dijera, y publicar un total institucional que
    # no cuadre con el porcentaje que hay al lado es el mismo problema por otra vía. Por eso
    # `entidades_con_institucional` viaja al lado de las tres cifras: es su rótulo.
    con_institucional = base.filter(pim_institucional__isnull=False)
    comparables = con_institucional.aggregate(
        pim=_suma("pim"),
        pia_institucional=_suma("pia_institucional"),
        pim_institucional=_suma("pim_institucional"),
        devengado_institucional=_suma("devengado_institucional"),
    )
    hay_institucional = con_institucional.exists()

    return {
        "pia": float(totales["pia"]),
        "pim": float(totales["pim"]),
        "devengado": float(totales["devengado"]),
        "pct_ejecucion": _porcentaje(totales["devengado"], totales["pim"]),
        "saldo": float(totales["pim"] - totales["devengado"]),
        "variacion_pia_pim": float(totales["pim"] - totales["pia"]),
        "entidades_con_presupuesto": base.filter(pim__gt=0).count(),
        "entidades_en_ambito": queryset_entidades.count(),
        # Sin ninguna entidad con dato, los tres son `None` y no cero: la suma de un conjunto
        # vacío se leería como «estas municipalidades no tienen presupuesto».
        "pia_institucional": float(comparables["pia_institucional"]) if hay_institucional else None,
        "pim_institucional": float(comparables["pim_institucional"]) if hay_institucional else None,
        "devengado_institucional": (
            float(comparables["devengado_institucional"]) if hay_institucional else None
        ),
        "pct_0068_institucional": _porcentaje(
            comparables["pim"], comparables["pim_institucional"]
        ),
        "entidades_con_institucional": con_institucional.count(),
        "pim_proyectos": float(pim_por_origen.get("proyecto", CERO)),
        "pim_actividades": float(pim_por_origen.get("actividad", CERO)),
        "pct_proyectos": _porcentaje(pim_por_origen.get("proyecto", CERO), totales["pim"]),
    }


def procesos(ejercicio, ambito=AMBITO_POR_DEFECTO, provincia="", entidad=None) -> dict:
    """Reparto del 0068 entre procesos de la GRD, más lo que el catálogo aún no clasifica.

    Sale del catálogo vigente en este mismo instante: si PREDES corrige una actividad en el
    admin, el siguiente request ya lo refleja.

    Con `entidad` se acota a una sola municipalidad: es lo que pinta su ficha, con el mismo
    cálculo que el gráfico del tablero para que las dos pantallas no se separen.
    """
    ambitos = [entidad] if entidad is not None else entidades(ambito, provincia)
    filas = (
        PresupuestoActividad.objects.filter(ejercicio=ejercicio, entidad__in=ambitos)
        .values("clasificacion__proceso__slug")
        .annotate(pim=_suma("pim"), devengado=_suma("devengado"))
    )
    por_slug = {f["clasificacion__proceso__slug"]: f for f in filas}
    total = sum((f["pim"] for f in filas), CERO)

    detalle = []
    for proceso in ProcesoGRD.objects.all():
        fila = por_slug.get(proceso.slug, {})
        pim = fila.get("pim", CERO)
        detalle.append({
            "slug": proceso.slug,
            "nombre": proceso.nombre,
            "color": proceso.color,
            "pim": float(pim),
            "devengado": float(fila.get("devengado", CERO)),
            "pct": _porcentaje(pim, total),
        })

    sin = por_slug.get(None, {})
    return {
        "procesos": detalle,
        # No se reparte entre los demás ni se esconde: es la medida de cuánto le falta al
        # catálogo, y sale en el gráfico para que se vea.
        "sin_clasificar": {
            "pim": float(sin.get("pim", CERO)),
            "devengado": float(sin.get("devengado", CERO)),
            "pct": _porcentaje(sin.get("pim", CERO), total),
        },
    }


def tendencia(ambito=AMBITO_POR_DEFECTO, provincia="") -> list[dict]:
    """Serie de PIM y devengado por ejercicio visible.

    Cada punto lleva su `corte`, su `fuente` y `es_parcial`: la serie mezcla el comparativo del
    MEF con la base del cliente, y el último punto suele ser medio año. Un gráfico que no lo
    diga insinúa una caída de ejecución que no existe.
    """
    queryset_entidades = entidades(ambito, provincia)
    por_anio = {
        f["ejercicio__anio"]: f
        for f in PresupuestoEntidad.objects.filter(entidad__in=queryset_entidades,
                                                   ejercicio__visible=True)
        .values("ejercicio__anio")
        .annotate(pia=_suma("pia"), pim=_suma("pim"), devengado=_suma("devengado"))
    }
    serie = []
    for ejercicio in Ejercicio.objects.filter(visible=True).order_by("anio"):
        fila = por_anio.get(ejercicio.anio, {})
        serie.append({
            "anio": ejercicio.anio,
            "corte": ejercicio.corte,
            "es_parcial": ejercicio.es_parcial,
            "fuente": ejercicio.get_fuente_display(),
            "pia": float(fila.get("pia", CERO)),
            "pim": float(fila.get("pim", CERO)),
            "devengado": float(fila.get("devengado", CERO)),
        })
    return serie


def serie_entidad(entidad: EntidadEjecutora) -> list[dict]:
    """La historia presupuestal de una municipalidad, un punto por ejercicio publicado.

    Es la comparación entre años **a nivel de municipalidad**: donde la vista de comparación
    enfrenta dos ejercicios de toda la región, esto enseña los cinco de una sola entidad.
    Los ejercicios en los que no tuvo presupuesto del 0068 **no se rellenan con ceros**: se
    omiten, porque «no participó del programa» no es «participó con cero soles».
    """
    presupuestos = {
        p.ejercicio_id: p
        for p in PresupuestoEntidad.objects.filter(
            entidad=entidad, ejercicio__visible=True
        ).select_related("ejercicio")
    }
    serie = []
    for ejercicio in Ejercicio.objects.filter(visible=True).order_by("anio"):
        presupuesto = presupuestos.get(ejercicio.pk)
        if presupuesto is None:
            continue
        serie.append({
            "anio": ejercicio.anio,
            "corte": ejercicio.corte,
            "es_parcial": ejercicio.es_parcial,
            "fuente": ejercicio.get_fuente_display(),
            **{
                clave: fila_entidad(presupuesto)[clave]
                for clave in (
                    "pia", "pim", "devengado", "pct_ejecucion", "saldo", "variacion_pia_pim",
                    "pct_variacion_pia_pim", "pia_institucional", "pim_institucional",
                    "devengado_institucional", "pct_0068_institucional",
                )
            },
        })
    return serie


def actividades_entidad(entidad: EntidadEjecutora, ejercicio: Ejercicio) -> list[dict]:
    """Actividades y proyectos del 0068 de una municipalidad en un ejercicio.

    **No se pagina**: son 3 de media por entidad y ejercicio, con 50 en el máximo real. Es el
    mismo criterio con el que no se paginan los 112 distritos ni los 9 peligros — lo que crece
    es la tabla de municipalidades, y esa sí se pagina.
    """
    filas = (
        PresupuestoActividad.objects.filter(entidad=entidad, ejercicio=ejercicio)
        .select_related("clasificacion__proceso")
        .order_by("-pim", "clasificacion__codigo")
    )
    return [
        {
            "codigo": f.clasificacion.codigo,
            "nombre": f.clasificacion.nombre,
            "origen": f.clasificacion.origen,
            "proceso": f.clasificacion.proceso.nombre if f.clasificacion.proceso_id else None,
            "proceso_slug": f.clasificacion.proceso.slug if f.clasificacion.proceso_id else None,
            "pia": float(f.pia),
            "pim": float(f.pim),
            "devengado": float(f.devengado),
            "pct_ejecucion": _porcentaje(f.devengado, f.pim),
        }
        for f in filas
    ]


def sin_clasificar_pendiente() -> dict:
    """Cuánto PIM cuelga de códigos sin proceso, para la tarjeta del panel del admin.

    Un catálogo a medio mapear no rompe nada: los gráficos siguen dibujándose y la barra «sin
    clasificar» crece sin que nadie mire. Por eso la cifra sube al panel, como la del buscador.
    """
    from apps.inversion.models import ClasificacionActividad

    pendiente = PresupuestoActividad.objects.filter(
        ejercicio__visible=True, clasificacion__proceso__isnull=True
    ).aggregate(pim=_suma("pim"))["pim"]
    total = PresupuestoActividad.objects.filter(ejercicio__visible=True).aggregate(
        pim=_suma("pim")
    )["pim"]
    return {
        "pim_sin_clasificar": float(pendiente),
        "pim_total": float(total),
        "pct": _porcentaje(pendiente, total),
        "codigos_sin_proceso": ClasificacionActividad.objects.filter(
            proceso__isnull=True
        ).count(),
        "codigos_automaticos": ClasificacionActividad.objects.filter(
            automatico=True, proceso__isnull=False
        ).count(),
    }
