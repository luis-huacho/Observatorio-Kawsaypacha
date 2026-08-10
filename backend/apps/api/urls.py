"""Rutas del API (contrato del spec 02).

Las rutas concretas van **antes** del router: `export.xlsx` y `geojson/` cuelgan del mismo
prefijo que el detalle de `/ccpp/{codigo}/`, y si el router se registrara primero atraparía
`export.xlsx` como si fuera un código de centro poblado.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.informes.views import VisorMapaView

from . import views

router = DefaultRouter()
router.register("territorio/provincias", views.ProvinciaViewSet, basename="provincias")
router.register("territorio/distritos", views.DistritoViewSet, basename="distritos")
router.register("ccpp", views.CentroPobladoViewSet, basename="ccpp")
router.register("peligros/tipos", views.TipoPeligroViewSet, basename="tipos-peligro")
router.register("medidas", views.MedidaViewSet, basename="medidas")
router.register("normativa", views.NormaViewSet, basename="normativa")
router.register("noticias", views.NoticiaViewSet, basename="noticias")
router.register("videos", views.VideoViewSet, basename="videos")
router.register("biblioteca", views.DocumentoViewSet, basename="biblioteca")

urlpatterns = [
    # --- Peligros -----------------------------------------------------------
    path("ccpp/export.xlsx", views.CentroPobladoExportView.as_view(), name="ccpp-export"),
    path("ccpp/geojson/", views.CentroPobladoGeoJSONView.as_view(), name="ccpp-geojson"),
    path("peligros/resumen/", views.ResumenPeligrosView.as_view(), name="peligros-resumen"),
    path(
        "peligros/frecuencia/export.xlsx",
        views.FrecuenciaExportView.as_view(),
        name="frecuencia-export",
    ),
    path("peligros/frecuencia/", views.FrecuenciaListaView.as_view(), name="frecuencia-lista"),
    path(
        "peligros/frecuencia/<str:ubigeo>/",
        views.FrecuenciaDetalleView.as_view(),
        name="frecuencia-detalle",
    ),
    # --- Editorial ----------------------------------------------------------
    path("normativa/export.xlsx", views.NormaExportView.as_view(), name="normativa-export"),
    path("eventos/", views.EventoListaView.as_view(), name="eventos"),
    path(
        "biblioteca/categorias/",
        views.CategoriaDocumentoListaView.as_view(),
        name="biblioteca-categorias",
    ),
    # --- Incidencia ---------------------------------------------------------
    path("comparador/distritos/", views.ComparadorView.as_view(), name="comparador"),
    path(
        "distritos/<str:ubigeo>/ayuda-memoria.pdf",
        views.AyudaMemoriaView.as_view(),
        name="ayuda-memoria",
    ),
    # --- Búsqueda (fallback de Meilisearch; ver 04) --------------------------
    path("buscar/", views.BusquedaView.as_view(), name="buscar"),
    path("buscar/estado/", views.EstadoBusquedaView.as_view(), name="buscar-estado"),
    # --- Sitio, mapas, métricas e inversión ---------------------------------
    # --- Salud --------------------------------------------------------------
    # Prueba de vida para el healthcheck del contenedor y para la vigilancia externa.
    # Exenta de throttling y sin dependencias duras: ver apps/api/views/salud.py.
    path("salud/", views.SaludView.as_view(), name="salud"),

    path("sitio/", views.SitioView.as_view(), name="sitio"),
    path("mapas/capas/", views.CapasMapaView.as_view(), name="mapas-capas"),
    # `export.xlsx` antes de `inversion/`: si no, DRF nunca llegaría a la ruta concreta.
    path("inversion/export.xlsx", views.InversionExportView.as_view(), name="inversion-export"),
    path(
        "inversion/entidades/",
        views.InversionEntidadesView.as_view(),
        name="inversion-entidades",
    ),
    path(
        "inversion/entidades/<str:codigo>/",
        views.InversionEntidadDetalleView.as_view(),
        name="inversion-entidad",
    ),
    path("inversion/", views.InversionView.as_view(), name="inversion"),
    path("metricas/evento/", views.MetricaEventoView.as_view(), name="metricas-evento"),
    # Visor mínimo que el navegador headless captura para el mapa del PDF. Público a
    # propósito: abrirlo en un navegador normal es la forma de depurar ese mapa.
    path("informes/visor-mapa/", VisorMapaView.as_view(), name="visor-mapa"),
    path("", include(router.urls)),
]
