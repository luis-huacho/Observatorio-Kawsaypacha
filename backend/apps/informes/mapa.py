"""Captura de los mapas que se incrustan en los informes en PDF.

Son dos —los centros poblados por nivel de peligro de la ayuda memoria, y el coroplético del PP
0068 del reporte de inversión—, cada uno con su página de un solo uso en `templates/informes/`.
Lo que comparten es `_capturar`, donde vive todo lo delicado.

Se renderiza **en el servidor** con un navegador headless (decisión del dueño del proyecto, ver
02): así el PDF se puede generar desde el admin y por lotes, sin depender de que alguien tenga
el visor abierto, y el documento es reproducible a partir de sus parámetros.

El coste asumido es explícito: Chromium en la imagen y un punto más de fallo. Por eso **nunca
propaga la excepción**: si la captura falla, devuelve `(None, motivo)` y el PDF sale sin mapa
con el resto del contenido intacto. Un documento sin mapa sigue sirviendo en una reunión; uno
que no se genera, no.
"""
import base64
import logging
from urllib.parse import urlencode

from django.conf import settings
from django.urls import reverse

logger = logging.getLogger(__name__)

ANCHO = 1100
ALTO = 700
TIMEOUT_MS = 25_000

#: El coroplético se captura casi cuadrado, y no apaisado como el de peligros.
#:
#: Cusco es más alto que ancho (~394 km × ~474 km), así que en un lienzo 1100×700 la región se
#: ajusta por altura y deja un tercio del ancho en blanco. Ese hueco se pagaba en el PDF como
#: papel desperdiciado; con estas medidas el mapa llena su caja y la leyenda cabe a su lado.
ANCHO_INVERSION = 640
ALTO_INVERSION = 700

#: Plazo tras el que la página se da por pintada aunque `idle` no haya llegado.
#:
#: El mapa base son teselas de openstreetmap.org: si ese servicio se atasca, `idle` no llega nunca
#: y la captura se iba al timeout dejando el documento sin mapa. Pasado este plazo se captura lo
#: que haya —los centros poblados y las capas propias ya están dibujados—, que es mejor que nada.
#: Holgado respecto a lo que tarda en local (~2 s) y muy por debajo de `TIMEOUT_MS`.
ESPERA_PINTADO_MS = 8_000


def url_visor(distrito, peligros=(), niveles=()) -> str:
    params = {"distrito": distrito.ubigeo, "ancho": ANCHO, "alto": ALTO}
    if peligros:
        params["peligros"] = ",".join(peligros)
    if niveles:
        params["niveles"] = ",".join(str(n) for n in niveles)
    base = settings.RENDER_MAPA_BASE_URL.rstrip("/")
    return f"{base}{reverse('visor-mapa')}?{urlencode(params)}"


def url_visor_inversion(anio=None, ambito="", provincia="", nivel="distrital", metrica="pim") -> str:
    params = {"ancho": ANCHO_INVERSION, "alto": ALTO_INVERSION, "nivel": nivel, "metrica": metrica}
    if anio:
        params["anio"] = anio
    if ambito:
        params["ambito"] = ambito
    if provincia:
        params["provincia"] = provincia
    base = settings.RENDER_MAPA_BASE_URL.rstrip("/")
    return f"{base}{reverse('visor-mapa-inversion')}?{urlencode(params)}"


def capturar_mapa_inversion(
    anio=None, ambito="", provincia="", nivel="distrital", metrica="pim"
) -> tuple[str | None, str | None]:
    """El coroplético del PP 0068, para el reporte de inversión.

    Misma degradación que `capturar_mapa`: nunca propaga la excepción, porque un reporte sin
    mapa sigue sirviendo en una reunión y uno que no se genera, no.
    """
    return _capturar(
        url_visor_inversion(anio, ambito, provincia, nivel, metrica),
        f"inversión {anio or 'último'}/{nivel}",
        ancho=ANCHO_INVERSION,
        alto=ALTO_INVERSION,
    )


def capturar_mapa(distrito, peligros=(), niveles=()) -> tuple[str | None, str | None]:
    """Devuelve `(data_uri_png, None)` o `(None, motivo_del_fallo)`."""
    return _capturar(
        url_visor(distrito, peligros=peligros, niveles=niveles), distrito.ubigeo
    )


def _capturar(url: str, referencia: str, ancho: int = ANCHO, alto: int = ALTO) -> tuple[str | None, str | None]:
    """El navegador headless, compartido por los dos mapas.

    Todo lo delicado vive aquí —el doble señalizador, el búfer de dibujo, los avisos que no
    abortan— y no se duplica por mapa: cada trampa se aprendió una vez y hay que arreglarla en
    un solo sitio.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None, "Playwright no está instalado en esta imagen"

    try:
        with sync_playwright() as p:
            navegador = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
            try:
                pagina = navegador.new_page(
                    viewport={"width": ancho, "height": alto}, device_scale_factor=2
                )
                pagina.goto(url, wait_until="load", timeout=TIMEOUT_MS)
                # La página señaliza una de dos cosas: que MapLibre terminó de dibujar
                # (`idle`) o que falló. Se esperan **ambas** y el fallo se trata como fallo:
                # esperar solo el "listo" y capturar de todas formas produciría un PNG en
                # blanco incrustado en el PDF como si fuera un mapa.
                pagina.wait_for_function(
                    "window.__mapaListo === true || window.__mapaError",
                    timeout=TIMEOUT_MS,
                )
                if error := pagina.evaluate("window.__mapaError || null"):
                    return None, str(error)[:200]
                # Avisos que no abortaron la captura —teselas del mapa base, una capa que no
                # respondió—. Van al log porque si no, un mapa base caído solo se nota mirando el
                # PDF y preguntándose por qué tiene el fondo en blanco.
                if avisos := pagina.evaluate("window.__mapaAvisos || []"):
                    logger.warning(
                        "Mapa de %s capturado con avisos: %s", referencia, "; ".join(avisos)
                    )
                png = pagina.screenshot(type="png")
            finally:
                navegador.close()
    except Exception as exc:  # noqa: BLE001 — el PDF tiene que salir igual
        logger.warning("No se pudo capturar el mapa de %s: %s", referencia, exc)
        return None, str(exc)[:200]

    return "data:image/png;base64," + base64.b64encode(png).decode(), None
