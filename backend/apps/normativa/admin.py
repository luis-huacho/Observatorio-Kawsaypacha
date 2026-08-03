from django.contrib import admin
from django_ckeditor_5.widgets import CKEditor5Widget
from unfold.admin import ModelAdmin

from apps.core.admin_workflow import WorkflowAdmin

from .models import Norma


@admin.register(Norma)
class NormaAdmin(WorkflowAdmin, ModelAdmin):
    campos_rich = ["contenido"]

    list_display = ("titulo", "tipo", "ambito", "fecha", "acceso")
    list_filter = ("estado", "tipo", "ambito", "estado_vigencia")
    search_fields = ("titulo", "numero", "resumen", "slug")
    prepopulated_fields = {"slug": ("titulo",)}
    autocomplete_fields = ("documento",)
    date_hierarchy = "fecha"

    fieldsets = (
        (None, {"fields": ("titulo", "slug", "numero", "resumen")}),
        ("Clasificación", {"fields": ("tipo", "ambito", "fecha", "estado_vigencia")}),
        ("Análisis", {"fields": ("analisis_predes", "contenido", "palabras_clave")}),
        ("Acceso a la publicación oficial", {
            "fields": ("documento", "url_oficial"),
            "description": "Si adjuntas el PDF alojado por PREDES, el sitio lo prefiere sobre "
                           "el enlace al portal: los portales del Estado reorganizan sus URL y "
                           "un enlace roto inutiliza el repositorio.",
        }),
        ("Portada", {
            "fields": ("imagen_portada", "imagen_titulo"),
            "description": "Vacía = ilustración institucional de normativa.",
        }),
        ("Estado editorial", {
            "fields": ("estado_badge", "nota_revision", "publicado_en", "creado_por",
                       "revisado_por"),
        }),
    )

    @admin.display(description="acceso")
    def acceso(self, obj):
        """Los tres estados reales del acceso, visibles de un vistazo en el listado."""
        if obj.documento_id:
            return "PDF alojado"
        if obj.url_oficial:
            return "Enlace al portal"
        return "— sin enlace"

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name in self.campos_rich:
            kwargs["widget"] = CKEditor5Widget(config_name="default")
        return super().formfield_for_dbfield(db_field, request, **kwargs)
