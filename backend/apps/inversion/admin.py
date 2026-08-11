from django.contrib import admin, messages
from django.db.models import Sum
from django.utils.html import format_html

from unfold.admin import ModelAdmin

from .models import (
    ClasificacionActividad,
    Ejercicio,
    EntidadEjecutora,
    PresupuestoActividad,
    PresupuestoEntidad,
    ProcesoGRD,
)


@admin.register(ProcesoGRD)
class ProcesoGRDAdmin(ModelAdmin):
    list_display = ["nombre", "slug", "orden", "color"]
    list_editable = ["orden"]
    # Sin `prepopulated_fields`: el slug lleva guion bajo, igual que en peligros, y el widget
    # de Django produciría guion medio.


@admin.register(Ejercicio)
class EjercicioAdmin(ModelAdmin):
    """El interruptor de la ventana: sin ningún ejercicio visible, /inversion sigue vacía."""

    list_display = ["anio", "corte", "fuente", "es_parcial", "visible", "entidades"]
    list_filter = ["visible", "es_parcial", "fuente"]
    list_editable = ["visible"]
    ordering = ["-anio"]

    @admin.display(description="entidades con presupuesto")
    def entidades(self, obj):
        return obj.presupuestos.filter(pim__gt=0).count()


@admin.register(ClasificacionActividad)
class ClasificacionActividadAdmin(ModelAdmin):
    """El catálogo que decide el gráfico de procesos de la GRD.

    No hay ninguna acción de «reprocesar»: el reparto se calcula al vuelo sobre
    `PresupuestoActividad`, así que un cambio aquí se ve en la web en el siguiente request.
    """

    list_display = ["codigo", "nombre_corto", "origen", "proceso", "revisado", "pim_2026"]
    list_filter = ["proceso", "origen", "automatico"]
    search_fields = ["codigo", "nombre"]
    list_select_related = ["proceso"]
    autocomplete_fields = []
    actions = ["marcar_revisadas"]
    ordering = ["origen", "codigo"]

    @admin.display(description="nombre")
    def nombre_corto(self, obj):
        return obj.nombre[:80] + ("…" if len(obj.nombre) > 80 else "")

    @admin.display(description="revisado", boolean=True)
    def revisado(self, obj):
        return not obj.automatico

    @admin.display(description="PIM en ejercicios visibles")
    def pim_2026(self, obj):
        total = obj.presupuestos.filter(ejercicio__visible=True).aggregate(t=Sum("pim"))["t"]
        return f"S/ {total:,.0f}" if total else "—"

    def save_model(self, request, obj, form, change):
        """Guardar desde el admin es la decisión de PREDES: deja de ser una propuesta.

        A partir de aquí ninguna importación ni ninguna semilla vuelve a tocar la fila.
        """
        obj.automatico = False
        super().save_model(request, obj, form, change)

    @admin.action(description="Marcar como revisadas (sin cambiar el proceso)")
    def marcar_revisadas(self, request, queryset):
        actualizadas = queryset.update(automatico=False)
        self.message_user(
            request,
            f"{actualizadas} clasificación(es) marcadas como revisadas por PREDES.",
            messages.SUCCESS,
        )


@admin.register(EntidadEjecutora)
class EntidadEjecutoraAdmin(ModelAdmin):
    list_display = ["nombre", "codigo", "ambito", "provincia", "distrito", "territorio"]
    list_filter = ["ambito", "provincia"]
    search_fields = ["nombre", "codigo"]
    list_select_related = ["provincia", "distrito"]

    @admin.display(description="territorio")
    def territorio(self, obj):
        """Marca las municipalidades que no casan con el padrón de distritos.

        Son reales y cuentan en los totales, pero sin distrito no pueden cruzarse con los
        datos de peligros. Verlas aquí es lo que permite pedir el padrón actualizado.
        """
        if not obj.sin_territorio:
            return "—"
        return format_html('<span style="color:#b45309">sin distrito en el padrón</span>')


@admin.register(PresupuestoEntidad)
class PresupuestoEntidadAdmin(ModelAdmin):
    list_display = ["entidad", "ejercicio", "pia", "pim", "devengado", "pim_institucional"]
    list_filter = ["ejercicio", "entidad__ambito", "entidad__provincia"]
    search_fields = ["entidad__nombre", "entidad__codigo"]
    list_select_related = ["entidad", "ejercicio"]
    # Se cargan por archivo; el admin es para consultar y corregir casos puntuales.
    raw_id_fields = ["entidad"]


@admin.register(PresupuestoActividad)
class PresupuestoActividadAdmin(ModelAdmin):
    list_display = ["entidad", "ejercicio", "clasificacion", "pim", "devengado"]
    list_filter = ["ejercicio", "clasificacion__proceso", "clasificacion__origen"]
    search_fields = ["entidad__nombre", "clasificacion__codigo", "clasificacion__nombre"]
    list_select_related = ["entidad", "ejercicio", "clasificacion"]
    raw_id_fields = ["entidad", "clasificacion"]
