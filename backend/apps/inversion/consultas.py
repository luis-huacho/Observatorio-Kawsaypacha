"""Agregados y derivados de Inversión.

Viven aquí y no en las vistas por la misma razón que `apps.peligros.consultas`: los leen el API,
el export a Excel y el admin, y que los tres calculen el % de ejecución por su cuenta es la
forma segura de que un día no coincidan.

Ningún derivado se guarda. Todos salen de `PresupuestoEntidad` (totales) y `PresupuestoActividad`
(el grano fino), así que una corrección del catálogo se ve en el siguiente request.
"""
from decimal import Decimal

from django.db.models import DecimalField, F, Q, Sum, Value
from django.db.models.functions import Coalesce

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
        "pim_institucional": (
            float(presupuesto.pim_institucional)
            if presupuesto.pim_institucional is not None
            else None
        ),
        "pct_0068_institucional": _porcentaje(pim, presupuesto.pim_institucional),
        "pim_proyectos": float(reparto.get("proyecto", CERO)),
        "pim_actividades": float(reparto.get("actividad", CERO)),
        "pct_proyectos": _porcentaje(reparto.get("proyecto", CERO), pim),
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


def por_entidad(ejercicio, ambito=AMBITO_POR_DEFECTO, provincia="") -> list[dict]:
    """Una fila por entidad con presupuesto del 0068 en el ejercicio, ya con sus derivados."""
    queryset_entidades = entidades(ambito, provincia)
    reparto = _reparto_por_origen(ejercicio, queryset_entidades)
    presupuestos = (
        PresupuestoEntidad.objects.filter(ejercicio=ejercicio, entidad__in=queryset_entidades)
        .select_related("entidad__distrito", "entidad__provincia")
        .order_by("-pim")
    )
    return [fila_entidad(p, reparto.get(p.entidad.codigo)) for p in presupuestos]


def agregados(ejercicio, ambito=AMBITO_POR_DEFECTO, provincia="") -> dict:
    """Las cifras de cabecera: PIA/PIM/devengado del ámbito y sus derivados."""
    queryset_entidades = entidades(ambito, provincia)
    base = PresupuestoEntidad.objects.filter(ejercicio=ejercicio, entidad__in=queryset_entidades)

    totales = base.aggregate(
        pia=_suma("pia"),
        pim=_suma("pim"),
        devengado=_suma("devengado"),
        pim_institucional=_suma("pim_institucional"),
    )
    reparto = (
        PresupuestoActividad.objects.filter(ejercicio=ejercicio, entidad__in=queryset_entidades)
        .values("clasificacion__origen")
        .annotate(pim=_suma("pim"))
    )
    pim_por_origen = {f["clasificacion__origen"]: f["pim"] for f in reparto}

    # El denominador del % sobre el institucional solo suma las entidades que **tienen** ese
    # dato; si no, el porcentaje mezclaría un numerador de 116 municipalidades con un
    # denominador de 114 y saldría inflado sin que nada lo dijera.
    con_institucional = base.filter(pim_institucional__isnull=False)
    comparables = con_institucional.aggregate(pim=_suma("pim"), institucional=_suma(
        "pim_institucional"))

    return {
        "pia": float(totales["pia"]),
        "pim": float(totales["pim"]),
        "devengado": float(totales["devengado"]),
        "pct_ejecucion": _porcentaje(totales["devengado"], totales["pim"]),
        "saldo": float(totales["pim"] - totales["devengado"]),
        "variacion_pia_pim": float(totales["pim"] - totales["pia"]),
        "entidades_con_presupuesto": base.filter(pim__gt=0).count(),
        "entidades_en_ambito": queryset_entidades.count(),
        "pct_0068_institucional": _porcentaje(comparables["pim"], comparables["institucional"]),
        "entidades_con_institucional": con_institucional.count(),
        "pim_proyectos": float(pim_por_origen.get("proyecto", CERO)),
        "pim_actividades": float(pim_por_origen.get("actividad", CERO)),
        "pct_proyectos": _porcentaje(pim_por_origen.get("proyecto", CERO), totales["pim"]),
    }


def procesos(ejercicio, ambito=AMBITO_POR_DEFECTO, provincia="") -> dict:
    """Reparto del 0068 entre procesos de la GRD, más lo que el catálogo aún no clasifica.

    Sale del catálogo vigente en este mismo instante: si PREDES corrige una actividad en el
    admin, el siguiente request ya lo refleja.
    """
    filas = (
        PresupuestoActividad.objects.filter(
            ejercicio=ejercicio, entidad__in=entidades(ambito, provincia)
        )
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
