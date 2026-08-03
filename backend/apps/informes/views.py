"""Visor mínimo que el navegador headless captura para la ayuda memoria.

Es una vista de Django y no HTML inyectado con `set_content` porque así las rutas de
`{% static %}` resuelven: MapLibre y pmtiles van servidos por el propio backend, y con
contenido inyectado no habría origen contra el que resolverlas. De paso, abrir la URL en un
navegador normal es la forma de depurar el mapa del PDF.
"""
from django.views.generic import TemplateView

from .mapa import ALTO, ANCHO


class VisorMapaView(TemplateView):
    template_name = "informes/mapa.html"

    def get_context_data(self, **kwargs):
        from django.conf import settings
        from django.urls import reverse

        params = self.request.GET
        consulta = "&".join(
            f"{clave}={params[clave]}"
            for clave in ("distrito", "provincia", "peligro", "nivel_min")
            if params.get(clave)
        )
        base = settings.BACKEND_URL.rstrip("/")
        return super().get_context_data(
            url_geojson=f"{base}{reverse('ccpp-geojson')}?{consulta}",
            url_capas=f"{base}{reverse('mapas-capas')}",
            ancho=int(params.get("ancho") or ANCHO),
            alto=int(params.get("alto") or ALTO),
            **kwargs,
        )
