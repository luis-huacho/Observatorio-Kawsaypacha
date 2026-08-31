from django.contrib import admin
from django_ckeditor_5.widgets import CKEditor5Widget
from unfold.admin import ModelAdmin, TabularInline

from apps.core.admin_ia import RedaccionIAAdminMixin
from apps.core.admin_workflow import WorkflowAdmin

from .forms import NoticiaForm
from .models import Evento, Noticia, NoticiaArchivo, NoticiaEnlace, Video


class NoticiaEnlaceInline(TabularInline):
    """Enlaces externos que acompañan a la noticia.

    `TabularInline` es el de **`unfold.admin`**, no el de `django.contrib.admin`: el del admin
    clásico se pinta sin los estilos de Unfold.
    """

    model = NoticiaEnlace
    extra = 1
    fields = ("titulo", "url", "orden")
    ordering = ("orden", "id")


class NoticiaArchivoInline(TabularInline):
    """Anexos descargables. Ojo: `peso_bytes` es `editable=False`, así que **no puede ir en
    `fields`** — se enseña con un método de solo lectura, como la vista previa de la galería de
    medidas."""

    model = NoticiaArchivo
    extra = 1
    fields = ("archivo", "titulo", "peso_legible", "orden")
    readonly_fields = ("peso_legible",)
    ordering = ("orden", "id")

    @admin.display(description="peso")
    def peso_legible(self, obj):
        if not obj.pk or not obj.peso_bytes:
            return "—"
        if obj.peso_bytes < 1024 * 1024:
            return f"{obj.peso_bytes / 1024:.0f} KB"
        return f"{obj.peso_bytes / (1024 * 1024):.1f} MB".replace(".", ",")


@admin.register(Noticia)
class NoticiaAdmin(RedaccionIAAdminMixin, WorkflowAdmin, ModelAdmin):
    """La noticia puede nacer de una URL (ADR-D7).

    El mecanismo entero —insignia, campos de solo lectura, provisionales, encolado y el JS que
    refresca la ficha— vive en `RedaccionIAAdminMixin`, compartido con normativa. Va **primero**
    en las bases para que su `save_model` envuelva al de `WorkflowAdmin`.
    """

    campos_rich = ["cuerpo"]
    form = NoticiaForm
    # Los inlines se pintan **debajo de todos los fieldsets**, o sea tras «Estado editorial»,
    # que es donde tienen que estar: son material de apoyo, no parte de la nota.
    inlines = (NoticiaEnlaceInline, NoticiaArchivoInline)

    list_display = ("titulo", "tipo", "fecha", "autor", "destacada", "ia_badge")
    list_filter = ("estado", "tipo", "destacada", "ia_estado")
    search_fields = ("titulo", "bajada", "slug")
    # El modelo ordena por `-destacada` para el sitio público; aquí la lista es una cola de
    # trabajo y se queda cronológica. `destacada` ya es columna ordenable, así que el otro orden
    # está a un clic.
    ordering = ("-fecha",)
    prepopulated_fields = {"slug": ("titulo",)}
    date_hierarchy = "fecha"

    fieldsets = (
        ("Origen", {
            "fields": ("url_origen", "procesar_con_ia", "ia_badge_ficha", "log_ia"),
            "description": "Marca la casilla y guarda: se leerá la URL y se redactará el resto en "
                           "segundo plano. Los demás campos pueden quedar en blanco. Cada noticia "
                           "puede usar la IA una sola vez, y lo redactado hay que revisarlo.",
        }),
        (None, {"fields": ("titulo", "slug", "bajada", "tipo", "autor", "fecha", "destacada")}),
        ("Contenido", {"fields": ("cuerpo", "palabras_clave")}),
        ("Portada", {
            "fields": ("imagen_portada", "imagen_titulo"),
            "description": "Vacía = ilustración institucional del tipo de contenido.",
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

    def encolar_ia(self, obj) -> None:
        from apps.contenidos.tasks import redactar_noticia_desde_url

        redactar_noticia_desde_url.enqueue(pk=obj.pk)


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
