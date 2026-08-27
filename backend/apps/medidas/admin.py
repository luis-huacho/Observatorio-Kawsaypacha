from django.contrib import admin
from django.utils.html import format_html
from django_ckeditor_5.widgets import CKEditor5Widget
from unfold.admin import ModelAdmin, TabularInline

from apps.core.admin_workflow import WorkflowAdmin

from .models import Medida, MedidaFichaACC, MedidaImagen


def _extracto(texto: str, limite: int = 80) -> str:
    return texto[:limite] + ("…" if len(texto) > limite else "")


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


@admin.register(MedidaFichaACC)
class MedidaFichaACCAdmin(ModelAdmin):
    """Separado de Medida (no inline): la ficha tiene 17 preguntas y mezclarla en el
    formulario de Medida lo haría inmanejable."""

    list_display = ("medida", "columna_001", "columna_002", "columna_003", "columna_004",
                     "columna_005")
    list_select_related = ("medida",)
    search_fields = ("medida__titulo", "medida__slug")
    autocomplete_fields = ("medida",)

    @admin.display(description=MedidaFichaACC._meta.get_field("value_001").verbose_name)
    def columna_001(self, obj):
        return _extracto(obj.value_001)

    @admin.display(description=MedidaFichaACC._meta.get_field("value_002").verbose_name)
    def columna_002(self, obj):
        return _extracto(obj.value_002)

    @admin.display(description=MedidaFichaACC._meta.get_field("value_003").verbose_name)
    def columna_003(self, obj):
        return _extracto(obj.value_003)

    @admin.display(description=MedidaFichaACC._meta.get_field("value_004").verbose_name)
    def columna_004(self, obj):
        return _extracto(obj.value_004)

    @admin.display(description=MedidaFichaACC._meta.get_field("value_005").verbose_name)
    def columna_005(self, obj):
        return _extracto(obj.value_005)
