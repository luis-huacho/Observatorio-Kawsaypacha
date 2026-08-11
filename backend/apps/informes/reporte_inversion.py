"""Reporte PDF de la ventana Inversión (PP 0068).

El hermano de `ayuda_memoria.py`, con la misma exigencia: no es «que salga un PDF», es que sus
cifras cuadren con las de la pantalla desde la que se pidió. Por eso lee **exclusivamente** de
`apps.inversion.consultas` —el mismo módulo que sirve el API y el Excel— y no reimplementa
ningún agregado. Dos implementaciones «equivalentes» divergen en cuanto una se toca, y un
documento en papel no se puede comprobar en mitad de una reunión.

Los gráficos van en SVG generado en servidor (`graficos.py`): WeasyPrint no ejecuta JavaScript,
así que los de Recharts no se pueden reutilizar. El único que necesita navegador es el mapa.
"""
import unicodedata
from datetime import datetime

from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone

from apps.informes import escalas, graficos
from apps.inversion import consultas

MOTIVO_SIN_DATOS = "PREDES está consolidando los datos de inversión del PP 0068."

#: Los mismos que la pantalla (`tailwind.config.ts`): el documento y el sitio no pueden usar
#: colores distintos para la misma magnitud.
COLOR_PIA = "#B8753C"
COLOR_PIM = "#007480"
COLOR_DEVENGADO = "#009257"
COLOR_PROYECTOS = "#007480"
COLOR_ACTIVIDADES = "#F1DCC0"
COLOR_SIN_CLASIFICAR = "#9CA3AF"

#: Etiqueta corta de la fuente para la columna del cuadro. El nombre completo se dice una vez
#: en el pie de fuentes: repetirlo en cada fila partía la celda en cuatro líneas y estiraba el
#: cuadro entero para no aportar nada.
FUENTE_CORTA = {"MEF": "MEF", "BASE_PP0068": "PREDES"}

AMBITOS_NOMBRE = {
    "municipal": "municipalidades distritales y provinciales",
    "distrital": "municipalidades distritales",
    "provincial": "municipalidades provinciales",
    "regional": "gobierno regional",
    "todos": "todas las entidades ejecutoras",
}


def generar_pdf(
    anio=None,
    ambito=consultas.AMBITO_POR_DEFECTO,
    provincia="",
    ordenar="",
    nivel=consultas.NIVEL_POR_DEFECTO,
    metrica=escalas.METRICA_POR_DEFECTO,
    con_mapa: bool = True,
):
    """Devuelve `(bytes_pdf, nombre_archivo)`."""
    from weasyprint import HTML

    contexto = reunir_datos(
        anio=anio, ambito=ambito, provincia=provincia, ordenar=ordenar,
        nivel=nivel, metrica=metrica,
    )

    if con_mapa and contexto["disponible"]:
        # Si la captura falla, el reporte sale SIN mapa y con el resto intacto: un documento sin
        # mapa sigue sirviendo en una reunión; uno que no se genera, no.
        from apps.informes.mapa import capturar_mapa_inversion

        contexto["mapa_png"], contexto["mapa_error"] = capturar_mapa_inversion(
            anio=contexto["anio"], ambito=ambito, provincia=provincia,
            nivel=nivel, metrica=metrica,
        )
    else:
        contexto["mapa_png"], contexto["mapa_error"] = None, None

    html = render_to_string("informes/reporte_inversion.html", contexto)
    pdf = HTML(string=html, base_url=str(settings.BASE_DIR)).write_pdf()
    return pdf, nombre_archivo(contexto)


def nombre_archivo(contexto: dict) -> str:
    partes = ["reporte-inversion-pp0068"]
    if contexto["disponible"]:
        partes.append(str(contexto["anio"]))
    if contexto.get("provincia"):
        partes.append(_slug(contexto["provincia"]))
    partes.append(f"{contexto['generado_en']:%Y%m%d}")
    return "-".join(partes) + ".pdf"


def _slug(texto: str) -> str:
    limpio = "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )
    return limpio.lower().replace(" ", "-")


def reunir_datos(
    anio=None,
    ambito=consultas.AMBITO_POR_DEFECTO,
    provincia="",
    ordenar="",
    nivel=consultas.NIVEL_POR_DEFECTO,
    metrica=escalas.METRICA_POR_DEFECTO,
) -> dict:
    """Todo lo que la plantilla necesita, con las mismas cifras que el API."""
    generado_en = timezone.localtime()
    ejercicio = consultas.ejercicio_para(anio)
    if ejercicio is None:
        # No es un error: es el estado normal entre una importación y su publicación. Sale un
        # documento de una página que lo explica, por el mismo criterio con el que el Excel trae
        # su hoja «Sin datos» — un PDF vacío parecería que no hay inversión pública en GRD.
        return {
            "disponible": False,
            "motivo": MOTIVO_SIN_DATOS,
            "generado_en": generado_en,
            "provincia": provincia,
            "firma": _bloque("informe.firma"),
        }

    ambito = ambito if ambito in consultas.AMBITOS else consultas.AMBITO_POR_DEFECTO
    metrica = escalas.metrica_valida(metrica)

    fuente_por_anio = dict(
        consultas.Ejercicio.objects.filter(visible=True).values_list("anio", "fuente")
    )
    agregados = consultas.agregados(ejercicio, ambito, provincia)
    reparto = consultas.procesos(ejercicio, ambito, provincia)
    tendencia = consultas.tendencia(ambito, provincia)
    mapa = consultas.mapa(ejercicio, ambito=ambito, provincia=provincia, nivel=nivel)
    filas = consultas.por_entidad(
        consultas.listado(ejercicio, ambito=ambito, provincia=provincia, ordenar=ordenar)
    )

    procesos = [
        (p["nombre"], p["pim"], p["color"] or COLOR_PIM) for p in reparto["procesos"]
    ]
    if reparto["sin_clasificar"]["pim"] > 0:
        procesos.append(
            ("Sin clasificar", reparto["sin_clasificar"]["pim"], COLOR_SIN_CLASIFICAR)
        )

    return {
        "disponible": True,
        "generado_en": generado_en,
        "anio": ejercicio.anio,
        "corte": ejercicio.corte,
        "es_parcial": ejercicio.es_parcial,
        "fuente": ejercicio.get_fuente_display(),
        "ambito": ambito,
        "ambito_nombre": AMBITOS_NOMBRE.get(ambito, ambito),
        "provincia": provincia,
        "agregados": agregados,
        "procesos": reparto["procesos"],
        "sin_clasificar": reparto["sin_clasificar"],
        "tendencia": [
            {**t, "saldo": t["pim"] - t["devengado"], "variacion": t["pim"] - t["pia"],
             "pct": (t["devengado"] / t["pim"]) if t["pim"] else None,
             "fuente_corta": FUENTE_CORTA.get(fuente_por_anio.get(t["anio"], ""), "—")}
            for t in tendencia
        ],
        "anio_desde": tendencia[0]["anio"] if tendencia else ejercicio.anio,
        "anio_hasta": tendencia[-1]["anio"] if tendencia else ejercicio.anio,
        "filas": filas,
        "mapa": mapa,
        "metrica": metrica,
        "metrica_nombre": escalas.METRICAS[metrica],
        "nivel": mapa["nivel"],
        "leyenda": _leyenda(metrica, mapa["cortes"]),
        "color_sin_municipalidad": escalas.SIN_MUNICIPALIDAD,
        # --- Gráficos, en SVG: WeasyPrint no ejecuta JavaScript ---------------------------
        "grafico_ejecucion": graficos.barras_verticales([
            ("PIA", agregados["pia"], COLOR_PIA),
            ("PIM", agregados["pim"], COLOR_PIM),
            ("Devengado", agregados["devengado"], COLOR_DEVENGADO),
        ]),
        "grafico_procesos": graficos.barras_horizontales(procesos),
        "grafico_origen": graficos.barra_apilada([
            ("Proyectos", agregados["pim_proyectos"], COLOR_PROYECTOS),
            ("Actividades", agregados["pim_actividades"], COLOR_ACTIVIDADES),
        ]),
        "grafico_tendencia": graficos.lineas(
            [f"{t['anio']}*" if t["es_parcial"] else str(t["anio"]) for t in tendencia],
            [
                ("PIA", [t["pia"] for t in tendencia], COLOR_PIA, True),
                ("PIM", [t["pim"] for t in tendencia], COLOR_PIM, False),
                ("Devengado", [t["devengado"] for t in tendencia], COLOR_DEVENGADO, False),
            ],
        ),
        "color_proyectos": COLOR_PROYECTOS,
        "color_actividades": COLOR_ACTIVIDADES,
        "color_pia": COLOR_PIA,
        "color_pim": COLOR_PIM,
        "color_devengado": COLOR_DEVENGADO,
        "firma": _bloque("informe.firma"),
    }


def _leyenda(metrica: str, cortes_por_metrica: dict) -> list[dict]:
    """Los cinco tramos con su rango, ya formateados.

    Se arma aquí y no en la plantilla porque los rangos **en soles** son obligatorios: el color
    de las métricas de dinero es relativo a la vista (quintiles), así que una leyenda de
    «bajo/alto» no dejaría reconstruir de qué cifras habla el mapa.
    """
    cortes, rampa = escalas.escala(metrica, cortes_por_metrica)
    fmt = (lambda v: f"{v * 100:.0f} %") if metrica == "pct_ejecucion" else (
        lambda v: f"S/ {v:,.0f}"
    )
    etiquetas = [
        f"hasta {fmt(cortes[0])}",
        f"{fmt(cortes[0])} – {fmt(cortes[1])}",
        f"{fmt(cortes[1])} – {fmt(cortes[2])}",
        f"{fmt(cortes[2])} – {fmt(cortes[3])}",
        f"más de {fmt(cortes[3])}",
    ]
    return [{"color": c, "etiqueta": e} for c, e in zip(rampa, etiquetas)]


def _bloque(clave: str) -> str:
    """Texto administrable. La firma institucional sale de `BloqueTexto`, no cableada."""
    from apps.sitio.models import BloqueTexto

    bloque = BloqueTexto.objects.filter(clave=clave).first()
    return bloque.cuerpo if bloque else ""
