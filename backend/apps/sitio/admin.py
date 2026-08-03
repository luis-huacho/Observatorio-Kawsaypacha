from django.contrib import admin
from django.utils.html import format_html
from django_ckeditor_5.widgets import CKEditor5Widget
from unfold.admin import ModelAdmin

from apps.core.admin_workflow import WorkflowAdmin
from apps.core.sanitizar import sanear

from .models import BloqueTexto, ConfiguracionSitio, EnlaceMenu, HeroSlide


@admin.register(ConfiguracionSitio)
class ConfiguracionSitioAdmin(ModelAdmin):
    """Singleton: se edita, no se crea ni se borra."""

    def has_add_permission(self, request):
        return not ConfiguracionSitio.objects.exists()

    def has_delete_permission(self, request, obj=None):
        # Borrarla dejaría el pie y la marca del sitio en blanco sin manera obvia de volver.
        return False

    fieldsets = (
        ("Marca", {"fields": ("nombre_sitio", "logo", "logo_footer")}),
        ("Pie de página", {"fields": ("descripcion_footer",)}),
        ("Contacto", {"fields": ("email_contacto", "telefono", "direccion", "redes")}),
        ("Aviso temporal", {
            "fields": ("mensaje_banner",),
            "description": "Si lo rellenas aparece una franja en todas las páginas. Déjalo "
                           "vacío para quitarla.",
        }),
    )


@admin.register(BloqueTexto)
class BloqueTextoAdmin(ModelAdmin):
    """Textos estáticos, agrupados por página para que el editor los encuentre."""

    list_display = ("clave", "pagina", "titulo")
    list_filter = ("pagina",)
    search_fields = ("clave", "titulo", "cuerpo")
    ordering = ("pagina", "clave")

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == "cuerpo":
            kwargs["widget"] = CKEditor5Widget(config_name="default")
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        # Vale también aquí: el saneado es del contenido, no del modelo que lo guarda.
        obj.cuerpo = sanear(obj.cuerpo)
        super().save_model(request, obj, form, change)

    def get_readonly_fields(self, request, obj=None):
        # La clave la consume el frontend por su nombre; renombrarla rompe la página en
        # silencio, así que solo se elige al crear.
        return ("clave",) if obj else ()


@admin.register(HeroSlide)
class HeroSlideAdmin(WorkflowAdmin, ModelAdmin):
    list_display = ("titulo", "orden", "vista_previa")
    list_editable = ("orden",)
    ordering = ("orden",)

    @admin.display(description="imagen")
    def vista_previa(self, obj):
        if not obj.imagen:
            return "—"
        return format_html('<img src="{}" style="height:48px;border-radius:4px">', obj.imagen.url)


@admin.register(EnlaceMenu)
class EnlaceMenuAdmin(ModelAdmin):
    list_display = ("texto", "zona", "grupo", "url", "orden", "visible")
    list_filter = ("zona", "visible")
    list_editable = ("orden", "visible")
    ordering = ("zona", "orden")
    search_fields = ("texto", "url")

    def get_fieldsets(self, request, obj=None):
        return (
            (None, {"fields": ("zona", "texto", "url", "orden", "visible")}),
            ("Pie de página", {
                "fields": ("grupo",),
                "description": "Columna del pie en la que se agrupa (p. ej. «Más»). Se ignora "
                               "en el menú principal.",
            }),
        )
