"""Ayuda memoria PDF por distrito (requisito 4 del TDR).

Es el entregable pensado para llevar a una mesa técnica, así que la exigencia real no es que
salga un PDF: es que sus cifras cuadren con las de la pantalla desde la que se pidió. Por eso
lee de `apps.peligros.consultas`, el mismo módulo que sirve el API, y no reimplementa ningún
agregado.

La maqueta se porta de `prototype/src/components/ReporteImpresion.tsx`, ya validada en pantalla
y en vista previa de impresión. Es HTML+CSS estándar, que es justo lo que consume WeasyPrint
(ADR-A9).
"""
import unicodedata
from datetime import datetime

from django.conf import settings
from django.db.models import Max
from django.template.loader import render_to_string
from django.utils import timezone

from apps.peligros import consultas
from apps.peligros.models import ClasificacionPeligro
from apps.territorio.models import CentroPoblado

NIVEL_LABEL = {1: "Bajo", 2: "Medio", 3: "Alto", 4: "Muy alto"}
NIVEL_COLOR = {1: "#5BBB5D", 2: "#EBB320", 3: "#F57C15", 4: "#970A00"}


def generar_pdf(distrito, peligros=(), niveles=(), con_mapa: bool = True):
    """Devuelve `(bytes_pdf, nombre_archivo)`."""
    from weasyprint import HTML

    contexto = reunir_datos(distrito, peligros=peligros, niveles=niveles)

    if con_mapa:
        from apps.informes.mapa import capturar_mapa

        # Si la captura falla, el PDF sale SIN mapa y con el resto intacto. Un documento sin
        # mapa sigue sirviendo en una reunión; uno que no se genera, no.
        contexto["mapa_png"], contexto["mapa_error"] = capturar_mapa(
            distrito, peligros=peligros, niveles=niveles
        )
    else:
        contexto["mapa_png"], contexto["mapa_error"] = None, None

    html = render_to_string("informes/ayuda_memoria.html", contexto)
    pdf = HTML(string=html, base_url=str(settings.BASE_DIR)).write_pdf()
    return pdf, nombre_archivo(distrito, contexto["generado_en"])


def nombre_archivo(distrito, generado_en: datetime) -> str:
    limpio = "".join(
        c for c in unicodedata.normalize("NFD", distrito.nombre) if unicodedata.category(c) != "Mn"
    )
    slug = limpio.lower().replace(" ", "-")
    return f"ayuda-memoria-{slug}-{generado_en:%Y%m%d}.pdf"


def reunir_datos(distrito, peligros=(), niveles=()) -> dict:
    """Todo lo que la plantilla necesita, con las mismas cifras que el API."""
    ccpp_ambito = CentroPoblado.objects.filter(distrito=distrito)
    resumen = consultas.resumen(ccpp_ambito, peligros=peligros, niveles=niveles)
    frecuencia = consultas.frecuencia(distrito)

    filas, clasificaciones_contadas, fuentes = _filas_tabla(ccpp_ambito, peligros, niveles)

    total_ambito = resumen["total_ccpp"]
    total_clasificados = len(filas)
    niveles_ccpp = {int(k): v for k, v in resumen["por_ccpp"]["niveles"].items()}

    # El documento va a una mesa técnica, así que la línea de filtros tiene que decir
    # exactamente qué se pidió: con selección múltiple, «nivel mínimo 3» ya no describe una
    # selección de «Muy alto y Bajo», y un pie que miente sobre su propio recorte es peor que
    # no llevar pie.
    nombres = [p["peligro"] for p in resumen["por_peligro"]] if peligros else []
    filtros = [
        f"Peligros: {', '.join(nombres)}" if nombres else "Todos los peligros",
        f"Niveles: {', '.join(NIVEL_LABEL[n].lower() for n in sorted(niveles, reverse=True))}"
        if niveles
        else "Todos los niveles",
    ]

    return {
        "distrito": distrito,
        "provincia": distrito.provincia.nombre,
        "generado_en": timezone.localtime(),
        "nombre_peligro": ", ".join(nombres),
        "niveles_pedidos": sorted(niveles, reverse=True),
        "filtros": " · ".join(filtros),
        "total_ambito": total_ambito,
        "total_clasificados": total_clasificados,
        "sin_dato": total_ambito - total_clasificados,
        "poblacion_expuesta": sum(f["poblacion"] or 0 for f in filas),
        "criticos": sum(1 for f in filas if f["nivel_max"] >= 3),
        "niveles": [
            {"nivel": n, "label": NIVEL_LABEL[n], "color": NIVEL_COLOR[n],
             "conteo": niveles_ccpp.get(n, 0)}
            for n in (4, 3, 2, 1)
        ],
        "total_niveles": sum(niveles_ccpp.values()),
        "clasificaciones_contadas": clasificaciones_contadas,
        "frecuencia": frecuencia,
        "evento_mas_frecuente": _evento_mas_frecuente(frecuencia),
        "filas": filas,
        "fuentes": sorted(fuentes) or ["SIGRID-CENEPRED"],
        "firma": _bloque("informe.firma"),
    }


def _filas_tabla(ccpp_ambito, peligros=(), niveles=()):
    """Una fila por centro poblado **clasificado**, con sus peligros agrupados.

    Los "sin dato" quedan fuera de la tabla y se cuentan en el texto: ese vacío de información
    es en sí mismo un argumento de incidencia, y una tabla de 8,968 filas mayoritariamente
    vacías no sirve para una reunión.
    """
    from apps.api.filters import condicion_clasificacion_local

    clasificaciones = (
        ClasificacionPeligro.objects.filter(centro_poblado__in=ccpp_ambito.values("pk"))
        .filter(condicion_clasificacion_local(peligros, niveles))
        .select_related("centro_poblado", "tipo_peligro", "fuente")
        .order_by("-nivel")
    )

    por_ccpp: dict[str, dict] = {}
    fuentes: set[str] = set()
    total = 0
    for c in clasificaciones:
        total += 1
        if c.fuente_id:
            fuentes.add(str(c.fuente))
        ccpp = c.centro_poblado
        fila = por_ccpp.setdefault(
            ccpp.codigo,
            {
                "codigo": ccpp.codigo,
                "nombre": ccpp.nombre,
                "categoria": ccpp.categoria or "—",
                "poblacion": ccpp.poblacion,
                "altitud": ccpp.altitud,
                "peligros": [],
                "nivel_max": c.nivel,
            },
        )
        fila["peligros"].append({
            "peligro": c.tipo_peligro.nombre,
            "nivel": c.nivel,
            "label": NIVEL_LABEL[c.nivel],
            "color": NIVEL_COLOR[c.nivel],
        })
        fila["nivel_max"] = max(fila["nivel_max"], c.nivel)

    for fila in por_ccpp.values():
        fila["peligros"].sort(key=lambda p: (-p["nivel"], p["peligro"]))

    filas = sorted(por_ccpp.values(), key=lambda f: (-f["nivel_max"], f["nombre"]))
    return filas, total, fuentes


def _evento_mas_frecuente(frecuencia) -> str:
    if not frecuencia:
        return ""
    eventos = [e for c in frecuencia["categorias"] for e in c["eventos"]]
    if not eventos:
        return ""
    top = max(eventos, key=lambda e: e["conteo"])
    return f"{top['evento'].lower()} ({top['conteo']} registros)"


def _bloque(clave: str) -> str:
    """Texto administrable. La firma institucional sale de `BloqueTexto`, no cableada."""
    from apps.sitio.models import BloqueTexto

    bloque = BloqueTexto.objects.filter(clave=clave).first()
    return bloque.cuerpo if bloque else ""


def sello_datos() -> str:
    """Marca de la última importación; invalida la caché de informes al reimportar."""
    ultimo = ClasificacionPeligro.objects.aggregate(m=Max("actualizado_en"))["m"]
    return ultimo.isoformat() if ultimo else "vacio"
