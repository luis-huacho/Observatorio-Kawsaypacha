from django.conf import settings
from django.contrib import admin, messages
from unfold.admin import ModelAdmin

from apps.core.admin_workflow import WorkflowAdmin, badge

from .models import CategoriaDocumento, Documento


@admin.register(CategoriaDocumento)
class CategoriaDocumentoAdmin(ModelAdmin):
    list_display = ("nombre", "slug", "orden")
    prepopulated_fields = {"slug": ("nombre",)}
    search_fields = ("nombre",)


@admin.register(Documento)
class DocumentoAdmin(WorkflowAdmin, ModelAdmin):
    list_display = ("titulo", "categoria", "fecha_publicacion", "ia_badge")
    list_filter = ("estado", "categoria", "ia_estado", "resumen_generado_por_ia")
    search_fields = ("titulo", "resumen", "autor_institucion")
    autocomplete_fields = ("categoria",)
    actions = WorkflowAdmin.actions + ("generar_resumen_con_ia",)

    fieldsets = (
        (None, {"fields": ("titulo", "categoria", "autor_institucion", "fecha_publicacion")}),
        ("Archivo", {
            "fields": ("archivo", "url_externa"),
            "description": "Hace falta al menos uno de los dos: un documento sin archivo ni "
                           "enlace no se puede abrir.",
        }),
        ("Resumen", {
            "fields": ("resumen", "resumen_generado_por_ia", "ia_estado", "log_ia"),
            "description": "El resumen con IA es una ayuda, no un sustituto: revísalo y "
                           "corrígelo antes de publicar.",
        }),
        ("Estado editorial", {
            "fields": ("estado_badge", "nota_revision", "publicado_en", "creado_por",
                       "revisado_por"),
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        return tuple(super().get_readonly_fields(request, obj)) + (
            "resumen_generado_por_ia", "ia_estado", "log_ia",
        )

    @admin.display(description="resumen IA")
    def ia_badge(self, obj):
        estilos = {
            "pendiente": ("#6B7280", "#F3F4F6"),
            "procesando": ("#1D4ED8", "#EFF6FF"),
            "ok": ("#0B3B26", "#E7F0EA"),
            "error": ("#7C2D12", "#FEF2F2"),
        }
        color, fondo = estilos.get(obj.ia_estado, ("#1F2937", "#F3F4F6"))
        return badge(obj.get_ia_estado_display(), color, fondo)

    @admin.action(description="Generar resumen con IA")
    def generar_resumen_con_ia(self, request, queryset):
        if not settings.GEMINI_API_KEY:
            # Se dice qué falta y quién lo arregla, en vez de dejar la acción fallando en el
            # worker sin que el editor entienda por qué.
            self.message_user(
                request,
                "La generación con IA está deshabilitada: falta GEMINI_API_KEY en la "
                "configuración del servidor. Pídesela al administrador de la plataforma; "
                "mientras tanto, redacta el resumen a mano.",
                messages.ERROR,
            )
            return

        from apps.core.tasks import generar_resumen_ia

        encolados = 0
        for doc in queryset:
            if not doc.archivo and not doc.url_externa:
                self.message_user(
                    request, f"«{doc}» no tiene PDF ni enlace: nada que resumir.",
                    messages.WARNING,
                )
                continue
            generar_resumen_ia.enqueue(modelo=doc._meta.label, pk=doc.pk)
            encolados += 1
        if encolados:
            self.message_user(
                request,
                f"{encolados} documento(s) en cola. El resumen aparecerá en unos segundos; "
                f"recarga la página. Nunca se sobreescribe un resumen escrito a mano.",
                messages.SUCCESS,
            )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # Auto-encolado al guardar: si hay PDF y el resumen está vacío, se intenta sin que el
        # editor tenga que acordarse de pedirlo.
        if settings.GEMINI_API_KEY and not (obj.resumen or "").strip():
            if obj.archivo or obj.url_externa:
                from apps.core.tasks import generar_resumen_ia

                generar_resumen_ia.enqueue(modelo=obj._meta.label, pk=obj.pk)
                self.message_user(
                    request,
                    "Se está generando un resumen con IA en segundo plano. Revísalo antes de "
                    "publicar.",
                    messages.INFO,
                )
