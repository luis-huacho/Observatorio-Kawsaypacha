from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.core.vistas_admin import estado_ia, reindexar_busqueda
from apps.mapas.vistas_tiles import servir_tile
from apps.sitio.vistas_html import ficha_html, sitemap

urlpatterns = [
    # ⚠️ Todo lo que cuelgue del prefijo del admin va **ANTES** de `admin.site.urls`. El AdminSite
    # de Django termina sus URLs con un `catch_all_view` que casa con cualquier cosa bajo su
    # prefijo y responde 404, así que una ruta declarada después nunca se alcanza. Estas dos
    # estuvieron detrás y la subida de imágenes del editor daba 404 sin que nada lo dijera.
    #
    # Subida de imágenes desde el editor. Va bajo el prefijo del admin porque solo la usa el
    # personal autenticado; expuesta aparte sería una vía de subida sin dueño claro.
    path(f"{settings.ADMIN_URL}ckeditor5/", include("django_ckeditor_5.urls")),
    # Botón «reindexar la búsqueda» del panel.
    path(
        f"{settings.ADMIN_URL}buscador/reindexar/",
        reindexar_busqueda,
        name="reindexar-busqueda",
    ),
    # Sondeo de la ficha mientras la IA redacta en el worker. Una sola ruta para noticias y
    # normas (ADR-D8); qué modelos acepta lo decide la lista blanca de la vista, no el patrón.
    # También aquí arriba: colgada detrás de `admin.site.urls` devolvería 404 y el refresco
    # automático no funcionaría sin que nada más fallara.
    path(
        f"{settings.ADMIN_URL}<slug:app_label>/<slug:modelo>/<int:pk>/estado-ia/",
        estado_ia,
        name="estado-ia",
    ),
    path(settings.ADMIN_URL, admin.site.urls),
    path("api/", include("apps.api.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    # --- El HTML de la SPA con las metas de cada ficha (compartir y SEO) ---
    #
    # Estas rutas las sirve la SPA, no el API: nginx las pasa por aquí en el dominio público para
    # que WhatsApp, Facebook y LinkedIn —que NO ejecutan JavaScript— vean el título, la bajada y la
    # portada de la ficha. Se responde lo mismo a todo el mundo; servir HTML distinto a los
    # rastreadores es cloaking. Ver el encabezado de `apps/sitio/vistas_html.py`.
    path("sitemap.xml", sitemap, name="sitemap"),
    # El patrón enumera los tipos en vez de aceptar cualquier segmento: un `<slug:tipo>` suelto
    # casaría con `media/foo.jpg` y taparía los archivos que sirve Django en desarrollo.
    re_path(
        r"^(?P<tipo>noticias|normativa|medidas|peligros)/(?P<clave>[^/]+)/?$",
        ficha_html,
        name="ficha-html",
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    # En producción `/tiles/` lo sirve nginx (ADR-A14). En desarrollo lo sirve esta vista, que
    # **sí implementa Range**: `django.views.static.serve` no lo hace, y sin rangos el
    # protocolo pmtiles:// descarga los 3 MB del archivo en cada tesela.
    urlpatterns += [
        re_path(r"^tiles/(?P<ruta>[\w.\-]+)$", servir_tile, name="tiles-dev"),
    ]
