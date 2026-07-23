from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import (
    CategoriaEvento,
    ClasificacionPeligro,
    Fuente,
    FrecuenciaEmergencia,
    TipoEvento,
    TipoPeligro,
)


@admin.register(TipoPeligro)
class TipoPeligroAdmin(ModelAdmin):
    list_display = ["nombre", "slug", "orden"]
    prepopulated_fields = {"slug": ["nombre"]}


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
