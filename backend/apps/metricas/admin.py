from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import EventoUso, ResumenDiario


@admin.register(EventoUso)
class EventoUsoAdmin(ModelAdmin):
    """Solo lectura: los eventos los escribe el beacon del frontend, nadie a mano."""

    list_display = ("fecha", "tipo", "ruta", "detalle")
    list_filter = ("tipo",)
    search_fields = ("ruta", "detalle")
    date_hierarchy = "fecha"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ResumenDiario)
class ResumenDiarioAdmin(ModelAdmin):
    """Agregado que sobrevive a la purga de eventos (>90 días)."""

    list_display = ("fecha", "tipo", "ruta", "detalle", "conteo")
    list_filter = ("tipo",)
    search_fields = ("ruta", "detalle")
    date_hierarchy = "fecha"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
