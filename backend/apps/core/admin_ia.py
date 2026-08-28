"""Lo que comparten los admin que dejan que la IA redacte una ficha desde una URL.

Noticias (ADR-D7) estrenó el patrón y normativa (ADR-D8) lo repite entero: la insignia de estado,
los dos campos de solo lectura, el `prepopulated_fields` neutralizado, el JS que refresca la ficha,
los valores provisionales que hacen posible guardar sin escribir nada y el encolado con su aviso.
Duplicarlo habría dejado dos copias que divergen; peor aún, el **sondeo que refresca la ficha es
uno solo para los dos**, así que si el estado o el candado se llamaran distinto en cada app, ese
endpoint dejaría de valer para una de ellas.

Lo único que pone cada admin es `encolar_ia()`: qué tarea se manda al worker. El resto es idéntico
porque los cuatro campos vienen de `core.RedaccionIAMixin` y los tres provisionales —`titulo`,
`slug`, `fecha`— existen con el mismo nombre en los dos modelos.
"""
from datetime import date
from urllib.parse import urlparse
from uuid import uuid4

from django.conf import settings
from django.contrib import admin, messages
from django.utils.text import slugify

from apps.core.admin_workflow import badge
from apps.core.models import EstadoIA

#: Sondea el estado y recarga la ficha cuando el worker termina. Uno solo para todos los modelos:
#: deriva la ruta de la propia URL en vez de llevar la app escrita a fuego.
JS_REDACCION_IA = "admin/js/redaccion_ia.js"

ESTILOS_IA = {
    EstadoIA.PENDIENTE: ("#6B7280", "#F3F4F6"),
    EstadoIA.PROCESANDO: ("#1D4ED8", "#EFF6FF"),
    EstadoIA.OK: ("#0B3B26", "#E7F0EA"),
    EstadoIA.ERROR: ("#7C2D12", "#FEF2F2"),
}


class RedaccionIAAdminMixin:
    """Va **antes** de `WorkflowAdmin` en la lista de bases, para que su `save_model` envuelva."""

    class Media:
        # Solo hace algo cuando el estado es «procesando»: sondea y recarga al terminar. Es lo que
        # responde a «¿cómo sé cuándo acabó?» sin dejar al editor pulsando F5 a ciegas.
        js = (JS_REDACCION_IA,)

    # --- Lo que pone cada admin ---------------------------------------------

    def encolar_ia(self, obj) -> None:
        """Manda la tarea de redacción al worker. La importación va dentro, no arriba."""
        raise NotImplementedError

    # --- Lo común -----------------------------------------------------------

    @admin.display(description="IA")
    def ia_badge(self, obj):
        color, fondo = ESTILOS_IA.get(obj.ia_estado, ("#1F2937", "#F3F4F6"))
        return badge(obj.get_ia_estado_display(), color, fondo)

    @admin.display(description="estado de la IA")
    def ia_badge_ficha(self, obj):
        return self.ia_badge(obj) if obj and obj.pk else "—"

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

    def save_model(self, request, obj, form, change):
        """Rellena los provisionales y encola, si el editor pidió la IA."""
        pedida = form.cleaned_data.get("procesar_con_ia") and not obj.redactada_por_ia

        if pedida:
            self.provisionales_ia(obj)
            obj.ia_estado = EstadoIA.PROCESANDO

        super().save_model(request, obj, form, change)

        if not pedida:
            return

        nombre = self.opts.verbose_name

        if not settings.OPENROUTER_API_KEY:
            # Se avisa aquí y no en el worker: allí el editor no vería nunca por qué no pasó nada.
            obj.ia_estado = EstadoIA.PENDIENTE
            obj.save(update_fields=["ia_estado"])
            self.message_user(
                request,
                "La redacción con IA está deshabilitada: falta OPENROUTER_API_KEY en la "
                "configuración del servidor. Pídesela al administrador de la plataforma; mientras "
                f"tanto, redacta la {nombre} a mano.",
                messages.ERROR,
            )
            return

        self.encolar_ia(obj)
        self.message_user(
            request,
            "Se está redactando con IA en segundo plano. La página se actualizará sola en cuanto "
            "termine. Revisa el resultado antes de publicar.",
            messages.INFO,
        )

    def provisionales_ia(self, obj) -> None:
        """Lo mínimo para que el registro entre en la base con el formulario casi vacío.

        No es cosmética: `fecha` y `slug` son `NOT NULL` y `slug` además `unique`, así que relajar
        los obligatorios en el formulario no basta para poder guardar. Migrarlos a `null=True`
        habría sido peor — dejaría publicar fichas sin título.
        """
        host = urlparse(obj.url_origen).hostname or "origen"

        if not obj.titulo:
            # Con este prefijo el listado se lee mientras tanto, y la tarea sabe que el título lo
            # puso la máquina y puede sustituirlo.
            tope = obj._meta.get_field("titulo").max_length
            obj.titulo = f"{obj.PREFIJO_PROVISIONAL} {host}"[:tope]
        if not obj.slug:
            # El sufijo aleatorio no es adorno: sin él, dos fichas creadas seguidas desde el mismo
            # sitio chocan contra el índice único.
            obj.slug = f"{slugify(host)[:80]}-{uuid4().hex[:8]}"
        if not obj.fecha:
            obj.fecha = date.today()
