"""Visores mínimos que el navegador headless captura para los informes en PDF.

Es una vista de Django y no HTML inyectado con `set_content` porque así las rutas de
`{% static %}` resuelven: MapLibre y pmtiles van servidos por el propio backend, y con
contenido inyectado no habría origen contra el que resolverlas. De paso, abrir la URL en un
navegador normal es la forma de depurar el mapa del PDF.
"""
import json
from urllib.parse import urlencode

from django.utils.safestring import mark_safe
from django.views.generic import TemplateView

from . import escalas
from .mapa import ALTO, ANCHO, ESPERA_PINTADO_MS


class VisorMapaView(TemplateView):
    template_name = "informes/mapa.html"

    def get_context_data(self, **kwargs):
        from django.urls import reverse

        params = self.request.GET
        # `urlencode` y no una f-string: un valor con `&` o con comillas se colaría en la
        # consulta o se saldría de la cadena de JavaScript en la que acaba esta URL. `safe=","`
        # deja las comas de las listas legibles —son un separador válido en una query— para que
        # abrir esta página en un navegador siga sirviendo para depurar el mapa del PDF.
        consulta = urlencode({
            clave: params[clave]
            for clave in ("distrito", "provincia", "peligros", "niveles", "peligro", "nivel_min")
            if params.get(clave)
        }, safe=",")
        # URL **relativas**, sin host. El navegador las resuelve contra el origen de esta página,
        # que por construcción es alcanzable: acaba de cargarla.
        #
        # Aquí estuvo `BACKEND_URL`, y era un fallo silencioso: esa es la URL con la que **el
        # visitante** alcanza el backend, no una interna. Chromium corre dentro del contenedor, así
        # que en producción local (`BACKEND_URL=http://localhost`) pedía los datos al puerto 80 del
        # propio contenedor, donde no escucha nadie —nginx es otro contenedor—: «Failed to fetch», y
        # el PDF salía sin mapa. En desarrollo funcionaba por casualidad, porque allí `BACKEND_URL`
        # es `localhost:8000`, que sí es el puerto de este contenedor.
        return super().get_context_data(
            url_geojson=f"{reverse('ccpp-geojson')}?{consulta}",
            url_capas=reverse("mapas-capas"),
            ancho=int(params.get("ancho") or ANCHO),
            alto=int(params.get("alto") or ALTO),
            espera_ms=ESPERA_PINTADO_MS,
            **kwargs,
        )


class VisorMapaInversionView(TemplateView):
    """El coroplético del PP 0068, para el reporte de inversión.

    Vista aparte y no un parámetro de la anterior: dibujan cosas distintas —puntos por nivel de
    peligro contra polígonos por importe— y compartir plantilla habría dejado un archivo lleno
    de condicionales en el que ninguno de los dos mapas se lee.
    """

    template_name = "informes/mapa_inversion.html"

    def get_context_data(self, **kwargs):
        from django.urls import reverse

        params = self.request.GET
        consulta = urlencode({
            clave: params[clave]
            for clave in ("anio", "ambito", "provincia", "nivel")
            if params.get(clave)
        }, safe=",")
        # URL **relativas**, por lo mismo que en el visor de peligros: `BACKEND_URL` es la URL
        # con la que el visitante alcanza el backend, y este navegador corre dentro del
        # contenedor. Ver el comentario largo de `VisorMapaView`.
        return super().get_context_data(
            url_mapa=f"{reverse('inversion-mapa')}?{consulta}",
            url_capas=reverse("mapas-capas"),
            nivel=params.get("nivel") or "distrital",
            metrica=escalas.metrica_valida(params.get("metrica") or ""),
            # La rampa viaja desde Python: si la plantilla tuviera la suya, el mapa y la leyenda
            # del PDF podrían desincronizarse sin que nada fallara.
            escala=mark_safe(json.dumps({
                "sin_municipalidad": escalas.SIN_MUNICIPALIDAD,
                "no_calculable": escalas.NO_CALCULABLE,
                "rampa_dinero": escalas.RAMPA_DINERO,
                "rampa_ejecucion": escalas.RAMPA_EJECUCION,
                "cortes_ejecucion": escalas.CORTES_EJECUCION,
            })),
            ancho=int(params.get("ancho") or ANCHO),
            alto=int(params.get("alto") or ALTO),
            espera_ms=ESPERA_PINTADO_MS,
            **kwargs,
        )
