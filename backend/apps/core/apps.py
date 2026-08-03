from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "apps.core"
    verbose_name = "Núcleo"

    def ready(self):
        from django.contrib import admin

        # Los títulos se fijan aquí y no solo en `UNFOLD`: la cabecera y el <title> del admin
        # los sirve `AdminSite.each_context`, así que sin esto PREDES entra a una pantalla que
        # dice «Sitio administrativo» y no menciona el observatorio.
        admin.site.site_header = "Observatorio Kallpachakuy"
        admin.site.site_title = "Observatorio Kallpachakuy"
        admin.site.index_title = "Panel de administración"
