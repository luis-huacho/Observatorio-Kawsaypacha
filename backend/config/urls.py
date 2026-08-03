from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.mapas.vistas_tiles import servir_tile

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    # Subida de imágenes desde el editor. Va bajo el prefijo del admin porque solo la usa el
    # personal autenticado; expuesta aparte sería una vía de subida sin dueño claro.
    path(f"{settings.ADMIN_URL}ckeditor5/", include("django_ckeditor_5.urls")),
    path("api/", include("apps.api.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    # En producción `/tiles/` lo sirve nginx (ADR-A14). En desarrollo lo sirve esta vista, que
    # **sí implementa Range**: `django.views.static.serve` no lo hace, y sin rangos el
    # protocolo pmtiles:// descarga los 3 MB del archivo en cada tesela.
    urlpatterns += [
        re_path(r"^tiles/(?P<ruta>[\w.\-]+)$", servir_tile, name="tiles-dev"),
    ]
