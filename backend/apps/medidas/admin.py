from django.contrib import admin, messages
from django.utils.html import format_html
from django_ckeditor_5.widgets import CKEditor5Widget
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import action

from apps.core.admin_ia import RedaccionIAAdminMixin
from apps.core.admin_workflow import WorkflowAdmin
from apps.core.importacion_admin import ImportadorExcelAdminMixin, cuenta

from . import importacion
from .forms import MedidaForm, SubirFichasACCForm
from .models import Medida, MedidaFichaACC, MedidaImagen, extracto

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
class MedidaAdmin(RedaccionIAAdminMixin, WorkflowAdmin, ModelAdmin):
    """La medida puede nacer de una ficha ACC ya cargada (ADR-D10).

    El mecanismo entero —insignia, campos de solo lectura, provisionales, encolado y el JS que
    refresca la ficha— vive en `RedaccionIAAdminMixin`, compartido con noticias y normas. Va
    **primero** en las bases para que su `save_model` envuelva al de `WorkflowAdmin`; al revés no
    se encolaría nada y no lo diría ningún error.
    """

    campos_rich = ["contenido"]
    form = MedidaForm

    #: `Medida` no tiene ninguna fecha `NOT NULL`. `fecha_implementacion` es nullable y ponerle
    #: la de hoy sería un dato falso indistinguible de uno real.
    fechas_provisionales = ()

    list_display = ("titulo", "tipo_peligro", "ambito", "resultado", "distrito", "destacada",
                    "ia_badge")
    list_filter = ("estado", "resultado", "ambito", "tipo_peligro", "destacada", "ia_estado")
    search_fields = ("titulo", "comunidad", "resumen_corto", "slug")
    prepopulated_fields = {"slug": ("titulo",)}
    # `ficha_acc` va aquí y no en un `<select>` plano: las fichas entran por Excel en lote y
    # cargarlas todas en cada alta es inmanejable.
    autocomplete_fields = ("tipo_peligro", "distrito", "ficha_acc")
    inlines = (MedidaImagenInline,)
    list_select_related = ("tipo_peligro", "distrito")

    fieldsets = (
        ("Origen", {
            "fields": ("ficha_acc", "procesar_con_ia", "ia_badge_ficha", "log_ia"),
            "description": "Elige la ficha ACC de la experiencia, marca la casilla y guarda: se "
                           "redactará el resto en segundo plano. Los demás campos pueden quedar "
                           "en blanco. Cada ficha puede usar la IA una sola vez, y lo redactado "
                           "hay que revisarlo antes de publicar.",
        }),
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

    def etiqueta_provisional(self, obj) -> str:
        """El nombre de la experiencia, que es lo que identifica una ficha.

        Se normalizan los espacios porque `value_001` viene de un Excel y puede traer saltos de
        línea, que en el título del listado quedarían crudos.
        """
        if not obj.ficha_acc_id:
            return "ficha ACC"
        return " ".join((obj.ficha_acc.value_001 or "").split())[:120] or "ficha ACC"

    def encolar_ia(self, obj) -> None:
        from apps.medidas.tasks import redactar_medida_desde_ficha

        redactar_medida_desde_ficha.enqueue(pk=obj.pk)


@admin.register(MedidaFichaACC)
class MedidaFichaACCAdmin(ImportadorExcelAdminMixin, ModelAdmin):
    """Separado de Medida (no inline): la ficha tiene 17 preguntas y mezclarla en el
    formulario de Medida lo haría inmanejable. Tampoco cuelga de una Medida — ver el modelo."""

    actions_list = ["importar_excel", "descargar_plantilla"]

    # La fontanería de las tres etapas vive en `core.importacion_admin`, compartida con el
    # importador de normativa: copiarla habría copiado la guarda del token contra `../`.
    importacion_modulo = importacion
    importacion_form = SubirFichasACCForm
    importacion_clave_sesion = "fichas_acc_importacion"
    importacion_plantillas = "admin/medidas/medidafichaacc"
    importacion_titulo = "Importar fichas ACC desde Excel"
    importacion_archivo_plantilla = "plantilla-fichas-acc.xlsx"
    importacion_sustantivo = ("ficha", "fichas")

    list_display = ("columna_001", "columna_002", "columna_003", "columna_005", "creado_en")
    search_fields = ("value_001", "value_002", "value_003")

    def get_search_results(self, request, queryset, search_term):
        """En el autocompletado de una Medida, solo las fichas que la IA todavía no gastó.

        El queryset del formulario es lo que **valida**; esto es lo que evita ofrecer una opción
        que después se rechaza con «Escoja una opción válida» sin decir por qué.
        """
        resultados, duplicados = super().get_search_results(request, queryset, search_term)
        if request.GET.get("field_name") == "ficha_acc":
            resultados = resultados.disponibles_para_ia()
        return resultados, duplicados

    @admin.display(description=MedidaFichaACC._meta.get_field("value_001").verbose_name)
    def columna_001(self, obj):
        return extracto(obj.value_001)

    @admin.display(description=MedidaFichaACC._meta.get_field("value_002").verbose_name)
    def columna_002(self, obj):
        return extracto(obj.value_002)

    @admin.display(description=MedidaFichaACC._meta.get_field("value_003").verbose_name)
    def columna_003(self, obj):
        return extracto(obj.value_003)

    @admin.display(description=MedidaFichaACC._meta.get_field("value_005").verbose_name)
    def columna_005(self, obj):
        return extracto(obj.value_005)

    # --- Importación desde Excel ------------------------------------------------------------
    #
    # Unfold rutea `actions_list` desde su propio `get_urls()`, así que no hace falta declarar
    # URLs ni sustituir el `change_list_template`. Las acciones se declaran aquí y no en el mixin
    # porque Unfold arma el nombre de la URL con el `app_label` y el modelo, y el decorador tiene
    # que verlas en la clase concreta.

    @action(description="Importar desde Excel", url_path="importar", icon="upload_file",
            permissions=["add"])
    def importar_excel(self, request):
        return self.vista_importar(request)

    @action(description="Descargar plantilla", url_path="plantilla", icon="download",
            permissions=["add"])
    def descargar_plantilla(self, request):
        return self.vista_plantilla(request)

    def contexto_importacion(self, request, extra):
        """Las 17 cabeceras, que la pantalla de subida lista para poder compararlas."""
        return super().contexto_importacion(
            request, {"columnas": importacion.columnas_esperadas(), **extra}
        )

    def mensaje_importacion(self, creados, analisis):
        """Se dice el motivo típico, que aquí son solo dos y caben en la frase."""
        omitidas = len(analisis.omitidas)
        if not omitidas:
            return super().mensaje_importacion(creados, analisis)
        return (
            f"Se {cuenta(creados, 'importó', 'importaron', 'ficha', 'fichas')} y se "
            f"{cuenta(omitidas, 'omitió', 'omitieron', 'fila', 'filas')} "
            "(nombre repetido o campos obligatorios vacíos).",
            messages.WARNING,
        )
