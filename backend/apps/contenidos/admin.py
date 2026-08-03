from django.contrib import admin
from django_ckeditor_5.widgets import CKEditor5Widget
from unfold.admin import ModelAdmin

from apps.core.admin_workflow import WorkflowAdmin

from .models import Evento, Noticia, Video


@admin.register(Noticia)
class NoticiaAdmin(WorkflowAdmin, ModelAdmin):
    campos_rich = ["cuerpo"]

    list_display = ("titulo", "tipo", "fecha", "autor", "destacada")
    list_filter = ("estado", "tipo", "destacada")
    search_fields = ("titulo", "bajada", "slug")
    prepopulated_fields = {"slug": ("titulo",)}
    date_hierarchy = "fecha"

    fieldsets = (
        (None, {"fields": ("titulo", "slug", "bajada", "tipo", "autor", "fecha", "destacada")}),
        ("Contenido", {"fields": ("cuerpo", "palabras_clave")}),
        ("Portada", {
            "fields": ("imagen_portada", "imagen_titulo"),
            "description": "Vacía = ilustración institucional del tipo de contenido "
                           "(noticia, artículo u opinión).",
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


@admin.register(Video)
class VideoAdmin(WorkflowAdmin, ModelAdmin):
    list_display = ("titulo", "tema", "fecha")
    list_filter = ("estado", "tema")
    search_fields = ("titulo", "descripcion")
    autocomplete_fields = ("tema",)
    date_hierarchy = "fecha"


@admin.register(Evento)
class EventoAdmin(WorkflowAdmin, ModelAdmin):
    list_display = ("titulo", "inicio", "fin", "modalidad", "lugar")
    list_filter = ("estado", "modalidad")
    search_fields = ("titulo", "descripcion", "lugar")
    date_hierarchy = "inicio"
