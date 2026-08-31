from django.contrib import admin
from django.db.models import Count
from django_ckeditor_5.widgets import CKEditor5Widget
from unfold.admin import ModelAdmin

from apps.core.admin_ia import RedaccionIAAdminMixin
from apps.core.admin_workflow import WorkflowAdmin

from .forms import NormaForm
from .models import EntidadEmisora, Norma


@admin.register(Norma)
class NormaAdmin(RedaccionIAAdminMixin, WorkflowAdmin, ModelAdmin):
    """La norma puede nacer del enlace a su publicación oficial (ADR-D8).

    El mecanismo entero —insignia, campos de solo lectura, provisionales, encolado y el JS que
    refresca la ficha— vive en `RedaccionIAAdminMixin`, compartido con noticias. Va **primero** en
    las bases para que su `save_model` envuelva al de `WorkflowAdmin`.
    """

    campos_rich = ["contenido"]
    form = NormaForm

    list_display = ("titulo", "tipo", "entidad_emisora", "ambito", "fecha", "acceso", "ia_badge")
    list_filter = ("estado", "tipo", "ambito", "entidad_emisora", "estado_vigencia", "ia_estado")
    search_fields = ("titulo", "numero", "resumen", "slug")
    prepopulated_fields = {"slug": ("titulo",)}
    autocomplete_fields = ("documento", "entidad_emisora")
    date_hierarchy = "fecha"

    fieldsets = (
        ("Origen", {
            "fields": ("url_origen", "procesar_con_ia", "ia_badge_ficha", "log_ia"),
            "description": "Pega el enlace a la publicación oficial —página web o PDF—, marca la "
                           "casilla y guarda: se leerá y se redactará el resto en segundo plano. "
                           "Los demás campos pueden quedar en blanco. Cada norma puede usar la IA "
                           "una sola vez, el análisis de PREDES lo sigues escribiendo tú, y lo "
                           "redactado hay que revisarlo antes de publicar.",
        }),
        (None, {"fields": ("titulo", "slug", "numero", "resumen")}),
        ("Clasificación", {
            "fields": ("entidad_emisora", "tipo", "ambito", "fecha", "estado_vigencia"),
            "description": "Si la entidad que la emite no está en la lista, créala con el «+» sin salir de aquí.",
        }),
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

    def encolar_ia(self, obj) -> None:
        from apps.normativa.tasks import redactar_norma_desde_url

        redactar_norma_desde_url.enqueue(pk=obj.pk)


@admin.register(EntidadEmisora)
class EntidadEmisoraAdmin(ModelAdmin):
    """Pantalla de mantenimiento del catálogo.

    `search_fields` no es cosmético: sin él, el `autocomplete_fields` de `NormaAdmin` revienta.
    """

    list_display = ("nombre", "sigla", "slug", "orden", "total_normas")
    list_editable = ("orden",)
    search_fields = ("nombre", "sigla")
    prepopulated_fields = {"slug": ("nombre",)}
    ordering = ("orden", "nombre")

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_normas=Count("normas"))

    @admin.display(description="normas", ordering="_normas")
    def total_normas(self, obj) -> int:
        """Cuántas la usan. Es lo que distingue una entidad viva de una que sobra —y la que
        avisa, antes de intentarlo, de que borrarla va a dar error de protección."""
        return obj._normas
