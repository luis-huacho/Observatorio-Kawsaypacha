"""Captura del mapa que se incrusta en la ayuda memoria.

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

#: Plazo tras el que la página se da por pintada aunque `idle` no haya llegado.
#:
#: El mapa base son teselas de openstreetmap.org: si ese servicio se atasca, `idle` no llega nunca
#: y la captura se iba al timeout dejando el documento sin mapa. Pasado este plazo se captura lo
#: que haya —los centros poblados y las capas propias ya están dibujados—, que es mejor que nada.
#: Holgado respecto a lo que tarda en local (~2 s) y muy por debajo de `TIMEOUT_MS`.
ESPERA_PINTADO_MS = 8_000


def url_visor(distrito, peligro: str = "", nivel_min="") -> str:
    params = {"distrito": distrito.ubigeo, "ancho": ANCHO, "alto": ALTO}
    if peligro:
        params["peligro"] = peligro
    if nivel_min:
        params["nivel_min"] = nivel_min
    base = settings.RENDER_MAPA_BASE_URL.rstrip("/")
    return f"{base}{reverse('visor-mapa')}?{urlencode(params)}"


def capturar_mapa(distrito, peligro: str = "", nivel_min="") -> tuple[str | None, str | None]:
    """Devuelve `(data_uri_png, None)` o `(None, motivo_del_fallo)`."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None, "Playwright no está instalado en esta imagen"

    url = url_visor(distrito, peligro=peligro, nivel_min=nivel_min)
    try:
        with sync_playwright() as p:
            navegador = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
            try:
                pagina = navegador.new_page(
                    viewport={"width": ANCHO, "height": ALTO}, device_scale_factor=2
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
                        "Mapa de %s capturado con avisos: %s", distrito.ubigeo, "; ".join(avisos)
                    )
                png = pagina.screenshot(type="png")
            finally:
                navegador.close()
    except Exception as exc:  # noqa: BLE001 — el PDF tiene que salir igual
        logger.warning("No se pudo capturar el mapa de %s: %s", distrito.ubigeo, exc)
        return None, str(exc)[:200]

    return "data:image/png;base64," + base64.b64encode(png).decode(), None
