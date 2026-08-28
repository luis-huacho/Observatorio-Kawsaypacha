from datetime import date
from urllib.parse import urlparse
from uuid import uuid4

from django.conf import settings
from django.contrib import admin, messages
from django.utils.text import slugify
from django_ckeditor_5.widgets import CKEditor5Widget
from unfold.admin import ModelAdmin

from apps.core.admin_workflow import WorkflowAdmin, badge
from apps.core.models import EstadoIA

from .forms import NoticiaForm
from .models import Evento, Noticia, Video


@admin.register(Noticia)
class NoticiaAdmin(WorkflowAdmin, ModelAdmin):
    campos_rich = ["cuerpo"]
    form = NoticiaForm

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
            "description": "Vacía = ilustración institucional del tipo de contenido "
                           "(noticia, artículo u opinión).",
        }),
        ("Estado editorial", {
            "fields": ("estado_badge", "nota_revision", "publicado_en", "creado_por",
                       "revisado_por"),
        }),
    )

    class Media:
        # Solo hace algo cuando el estado es «procesando»: sondea y recarga al terminar. Es lo que
        # responde a «¿cómo sé cuándo acabó?» sin dejar al editor pulsando F5 a ciegas.
        js = ("admin/js/noticia_ia.js",)

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name in self.campos_rich:
            kwargs["widget"] = CKEditor5Widget(config_name="default")
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    def get_readonly_fields(self, request, obj=None):
        return tuple(super().get_readonly_fields(request, obj)) + ("ia_badge_ficha", "log_ia")

    def get_prepopulated_fields(self, request, obj=None):
        """Sin título no hay slug que derivar.

        `prepopulated_fields` es JS: copia lo que se teclea en `titulo`. Con la casilla marcada el
        editor no teclea nada, así que el slug saldría vacío y el segundo registro así creado
        chocaría contra el índice único. El provisional lo pone `save_model`.
        """
        if obj is None or not obj.redactada_por_ia:
            return {}
        return super().get_prepopulated_fields(request, obj)

    @admin.display(description="IA")
    def ia_badge(self, obj):
        estilos = {
            EstadoIA.PENDIENTE: ("#6B7280", "#F3F4F6"),
            EstadoIA.PROCESANDO: ("#1D4ED8", "#EFF6FF"),
            EstadoIA.OK: ("#0B3B26", "#E7F0EA"),
            EstadoIA.ERROR: ("#7C2D12", "#FEF2F2"),
        }
        color, fondo = estilos.get(obj.ia_estado, ("#1F2937", "#F3F4F6"))
        return badge(obj.get_ia_estado_display(), color, fondo)

    @admin.display(description="estado de la IA")
    def ia_badge_ficha(self, obj):
        return self.ia_badge(obj) if obj and obj.pk else "—"

    def save_model(self, request, obj, form, change):
        """Rellena los provisionales y encola, si el editor pidió la IA.

        Los provisionales no son cosmética: `fecha` y `slug` son `NOT NULL` en la base y `slug`
        además `unique`, así que relajarlos en el formulario no basta para poder guardar.
        """
        pedida = form.cleaned_data.get("procesar_con_ia") and not obj.redactada_por_ia

        if pedida:
            host = urlparse(obj.url_origen).hostname or "origen"
            if not obj.titulo:
                # Con este prefijo el listado se lee mientras tanto, y la tarea sabe que el título
                # lo puso la máquina y puede sustituirlo.
                obj.titulo = f"(redactando) {host}"[:250]
            if not obj.slug:
                # El sufijo aleatorio no es adorno: sin él, dos noticias creadas seguidas desde el
                # mismo medio chocan contra el índice único.
                obj.slug = f"{slugify(host)[:80]}-{uuid4().hex[:8]}"
            if not obj.fecha:
                obj.fecha = date.today()
            obj.ia_estado = EstadoIA.PROCESANDO

        super().save_model(request, obj, form, change)

        if not pedida:
            return

        if not settings.OPENROUTER_API_KEY:
            # Se avisa aquí y no en el worker: allí el editor no vería nunca por qué no pasó nada.
            obj.ia_estado = EstadoIA.PENDIENTE
            obj.save(update_fields=["ia_estado"])
            self.message_user(
                request,
                "La redacción con IA está deshabilitada: falta OPENROUTER_API_KEY en la "
                "configuración del servidor. Pídesela al administrador de la plataforma; mientras "
                "tanto, redacta la noticia a mano.",
                messages.ERROR,
            )
            return

        from apps.contenidos.tasks import redactar_noticia_desde_url

        redactar_noticia_desde_url.enqueue(pk=obj.pk)
        self.message_user(
            request,
            "Se está redactando con IA en segundo plano. La página se actualizará sola en cuanto "
            "termine. Revisa el resultado antes de publicar.",
            messages.INFO,
        )


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
