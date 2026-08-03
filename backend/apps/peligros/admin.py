from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import (
    CategoriaEvento,
    ClasificacionPeligro,
    Fuente,
    FrecuenciaEmergencia,
    TipoEvento,
    TipoPeligro,
    TotalDeclaradoEmergencias,
)


@admin.register(TipoPeligro)
class TipoPeligroAdmin(ModelAdmin):
    list_display = ["nombre", "slug", "categoria_geo", "hoja_excel", "orden"]
    search_fields = ["nombre", "slug"]
    # Sin `prepopulated_fields`: el slug lleva guion bajo y el widget de Django produce
    # guion medio, que rompería la clave `nivel_<slug>` de los tiles.
    list_editable = ["orden"]


@admin.register(Fuente)
class FuenteAdmin(ModelAdmin):
    list_display = ["nombre", "sigla"]


@admin.register(ClasificacionPeligro)
class ClasificacionPeligroAdmin(ModelAdmin):
    list_display = ["centro_poblado", "tipo_peligro", "nivel", "fuente"]
    list_filter = ["tipo_peligro", "nivel"]
    search_fields = ["centro_poblado__nombre", "centro_poblado__codigo"]
    list_select_related = ["centro_poblado", "tipo_peligro", "fuente"]
    raw_id_fields = ["centro_poblado"]
    # Se cargan por Excel (10,978 filas); el admin es para consultar y corregir casos
    # puntuales, no para dar de alta a mano.
    autocomplete_fields = ["tipo_peligro"]


@admin.register(CategoriaEvento)
class CategoriaEventoAdmin(ModelAdmin):
    list_display = ["nombre", "slug", "orden"]


@admin.register(TipoEvento)
class TipoEventoAdmin(ModelAdmin):
    list_display = ["nombre", "categoria", "orden"]
    list_filter = ["categoria"]


@admin.register(FrecuenciaEmergencia)
class FrecuenciaEmergenciaAdmin(ModelAdmin):
    list_display = ["distrito", "tipo_evento", "conteo", "rango_fecha"]
    list_filter = ["tipo_evento__categoria", "distrito__provincia"]
    search_fields = ["distrito__nombre"]
    list_select_related = ["distrito", "tipo_evento"]


@admin.register(TotalDeclaradoEmergencias)
class TotalDeclaradoEmergenciasAdmin(ModelAdmin):
    """Subtotales que la fuente declara sin desglosar (ADR-D1). Hoy solo el distrito de Cusco."""

    list_display = ["distrito", "categoria", "total", "rango_fecha", "fuente"]
    list_filter = ["categoria", "distrito__provincia"]
    search_fields = ["distrito__nombre"]
    list_select_related = ["distrito", "categoria"]
