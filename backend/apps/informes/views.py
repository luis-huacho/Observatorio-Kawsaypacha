"""Visor mínimo que el navegador headless captura para la ayuda memoria.

Es una vista de Django y no HTML inyectado con `set_content` porque así las rutas de
`{% static %}` resuelven: MapLibre y pmtiles van servidos por el propio backend, y con
contenido inyectado no habría origen contra el que resolverlas. De paso, abrir la URL en un
navegador normal es la forma de depurar el mapa del PDF.
"""
from django.views.generic import TemplateView

from .mapa import ALTO, ANCHO, ESPERA_PINTADO_MS


class VisorMapaView(TemplateView):
    template_name = "informes/mapa.html"

    def get_context_data(self, **kwargs):
        from django.urls import reverse

        params = self.request.GET
        consulta = "&".join(
            f"{clave}={params[clave]}"
            for clave in ("distrito", "provincia", "peligro", "nivel_min")
            if params.get(clave)
        )
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
