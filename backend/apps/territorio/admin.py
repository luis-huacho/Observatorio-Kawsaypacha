from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import CentroPoblado, Distrito, Provincia


@admin.register(Provincia)
class ProvinciaAdmin(ModelAdmin):
    list_display = ["nombre", "ubigeo"]
    search_fields = ["nombre", "ubigeo"]


@admin.register(Distrito)
class DistritoAdmin(ModelAdmin):
    list_display = ["nombre", "ubigeo", "provincia"]
    list_filter = ["provincia"]
    search_fields = ["nombre", "ubigeo"]


@admin.register(CentroPoblado)
class CentroPobladoAdmin(ModelAdmin):
    list_display = ["nombre", "codigo", "distrito", "categoria", "poblacion"]
    list_filter = ["distrito__provincia", "categoria"]
    search_fields = ["nombre", "codigo"]
    list_select_related = ["distrito", "distrito__provincia"]
