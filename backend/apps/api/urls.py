from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("territorio/provincias", views.ProvinciaViewSet, basename="provincias")
router.register("territorio/distritos", views.DistritoViewSet, basename="distritos")
router.register("territorio/ccpp", views.CentroPobladoViewSet, basename="ccpp")
router.register("peligros/tipos", views.TipoPeligroViewSet, basename="tipos-peligro")
router.register("peligros/frecuencia", views.FrecuenciaViewSet, basename="frecuencia")

urlpatterns = [
    path("peligros/resumen/", views.ResumenPeligrosView.as_view(), name="resumen-peligros"),
    path("", include(router.urls)),
]
