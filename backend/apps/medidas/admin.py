from django.contrib import admin
from django.utils.html import format_html
from django_ckeditor_5.widgets import CKEditor5Widget
from unfold.admin import ModelAdmin, TabularInline

from apps.core.admin_workflow import WorkflowAdmin

from .models import Medida, MedidaImagen


class MedidaImagenInline(TabularInline):
    """Galería. `pie` es obligatorio en el modelo, así que el inline no lo deja en blanco."""

    model = MedidaImagen
    extra = 1
    fields = ("imagen", "vista_previa", "pie", "orden")
    readonly_fields = ("vista_previa",)
    ordering = ("orden",)

    @admin.display(description="vista previa")
    def vista_previa(self, obj):
        if not obj.pk or not obj.imagen:
            return "—"
        return format_html(
            '<img src="{}" style="height:64px;border-radius:4px">', obj.imagen.url
        )


@admin.register(Medida)
class MedidaAdmin(WorkflowAdmin, ModelAdmin):
    campos_rich = ["contenido"]

    list_display = ("titulo", "tipo_peligro", "ambito", "resultado", "distrito", "destacada")
    list_filter = ("estado", "resultado", "ambito", "tipo_peligro", "destacada")
    search_fields = ("titulo", "comunidad", "resumen_corto", "slug")
    prepopulated_fields = {"slug": ("titulo",)}
    autocomplete_fields = ("tipo_peligro", "distrito")
    inlines = (MedidaImagenInline,)
    list_select_related = ("tipo_peligro", "distrito")

    fieldsets = (
        (None, {"fields": ("titulo", "slug", "resumen_corto", "destacada")}),
        ("Clasificación", {"fields": ("tipo_peligro", "ambito", "resultado")}),
        ("Ubicación", {"fields": ("distrito", "comunidad", "centro_poblado")}),
        ("Contenido", {"fields": ("contenido", "video_url", "enlaces", "palabras_clave")}),
        ("Portada", {
            "fields": ("imagen_portada", "imagen_titulo"),
            "description": "Si dejas la portada vacía se usa la ilustración institucional del "
                           "peligro de la medida. No es un dato faltante.",
        }),
        ("Ficha técnica", {
            "classes": ("collapse",),
            "fields": ("fecha_implementacion", "actores", "costo_referencial", "documentos"),
        }),
        ("Estado editorial", {
            "fields": ("estado_badge", "nota_revision", "publicado_en", "creado_por",
                       "revisado_por"),
        }),
    )

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name in self.campos_rich:
            kwargs["widget"] = CKEditor5Widget(config_name="default")
        return super().formfield_for_dbfield(db_field, request, **kwargs)
