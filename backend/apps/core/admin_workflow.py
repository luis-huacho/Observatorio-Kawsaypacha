"""Admin del flujo editorial (spec 03).

Dos decisiones que gobiernan este módulo:

1. **El estado no se edita a mano.** `estado` es de solo lectura y se cambia con botones de
   acción. Un `<select>` guardaría el cambio **sin disparar el aviso por correo** y sin registrar
   quién lo hizo, que es justo lo que la transición aporta. Desde ADR-P3 ya no hay una revisión
   que saltarse, pero el argumento del correo sigue en pie.
2. **Las acciones que exigen `puede_publicar` no aparecen para quien no lo tiene.** Mostrarlas y
   responder «no tienes permiso» es una forma peor de decir lo mismo. Ojo: eso las filtra por
   **permiso, no por estado** — no hay `get_actions` en el proyecto, así que una acción cuya
   transición no cabe desde el estado actual se ofrece igual y falla con un aviso por objeto.
"""
from django.contrib import admin, messages
from django.utils.html import format_html

from apps.core.models import WorkflowMixin

COLORES_ESTADO = {
    "borrador": ("#6B7280", "#F3F4F6"),
    "publicado": ("#0B3B26", "#E7F0EA"),
    "archivado": ("#7C2D12", "#FEF2F2"),
}


def badge(texto: str, color: str, fondo: str) -> str:
    return format_html(
        '<span style="display:inline-block;padding:2px 8px;border-radius:9999px;'
        'font-size:11px;font-weight:600;color:{};background:{}">{}</span>',
        color, fondo, texto,
    )


class WorkflowAdmin(admin.ModelAdmin):
    """Base de los admin de contenido editorial."""

    #: Campos con HTML de CKEditor: eligen el widget. El saneado lo hace el modelo.
    campos_rich: list[str] = []

    readonly_fields = ("estado_badge", "publicado_en", "creado_por", "revisado_por",
                       "creado_en", "actualizado_en")
    list_filter = ("estado",)
    actions = ("publicar", "devolver_a_borrador", "archivar")

    @admin.display(description="estado", ordering="estado")
    def estado_badge(self, obj):
        color, fondo = COLORES_ESTADO.get(obj.estado, ("#1F2937", "#F3F4F6"))
        return badge(obj.get_estado_display(), color, fondo)

    def get_list_display(self, request):
        base = list(super().get_list_display(request))
        if "estado_badge" not in base:
            base.append("estado_badge")
        return base

    def get_exclude(self, request, obj=None):
        # `estado` fuera del formulario: se cambia con las acciones, que validan la transición
        # y encolan el correo.
        excluidos = list(super().get_exclude(request, obj) or [])
        if "estado" not in excluidos:
            excluidos.append("estado")
        return excluidos

    def save_model(self, request, obj, form, change):
        # El saneado del HTML **no** está aquí: lo hace `HtmlRicoMixin.save()`, para que la
        # garantía valga también fuera del admin (un `loaddata`, un script, un importador).
        # `campos_rich` sigue existiendo, pero solo para elegir el widget de CKEditor.
        if not change and not obj.creado_por_id:
            obj.creado_por = request.user
        super().save_model(request, obj, form, change)

    # -- Acciones de transición -------------------------------------------
    def _transicionar(self, request, queryset, destino: str, verbo: str):
        hechas, rechazadas, avisos = 0, [], []
        for obj in queryset:
            try:
                obj.transicionar(destino, usuario=request.user)
                hechas += 1
            except (ValueError, PermissionError) as exc:
                rechazadas.append(f"«{obj}»: {exc}")
                continue
            # Lo que no impide publicar pero hay que mirar una vez (p. ej. el bloque de contacto
            # de una ficha ACC, que lleva datos personales de un tercero).
            if destino == WorkflowMixin.Estado.PUBLICADO:
                avisos += [f"«{obj}»: {aviso}" for aviso in obj.avisos_al_publicar()]

        if hechas:
            self.message_user(
                request,
                f"{hechas} elemento(s) {verbo}. Los avisos por correo se envían en segundo plano.",
                messages.SUCCESS,
            )
        for aviso in avisos[:8]:
            self.message_user(request, aviso, messages.WARNING)
        for detalle in rechazadas[:8]:
            self.message_user(request, detalle, messages.WARNING)
        if len(rechazadas) > 8:
            self.message_user(
                request, f"…y {len(rechazadas) - 8} más sin cambiar.", messages.WARNING
            )

    @admin.action(description="Publicar", permissions=["publicar"])
    def publicar(self, request, queryset):
        self._transicionar(request, queryset, WorkflowMixin.Estado.PUBLICADO, "publicado(s)")

    @admin.action(
        description="Retirar del sitio y devolver a borrador (avisa al autor)",
        permissions=["publicar"],
    )
    def devolver_a_borrador(self, request, queryset):
        sin_nota = [str(o) for o in queryset if not (o.nota_revision or "").strip()]
        self._transicionar(request, queryset, WorkflowMixin.Estado.BORRADOR, "devuelto(s) a borrador")
        if sin_nota:
            # El correo de devolución sin observaciones deja al editor sin saber qué corregir.
            self.message_user(
                request,
                "Sin observaciones en: " + ", ".join(sin_nota[:5])
                + ". Escríbelas en «nota de revisión» antes de devolver, o el autor no sabrá "
                  "qué cambiar.",
                messages.WARNING,
            )

    @admin.action(description="Archivar", permissions=["publicar"])
    def archivar(self, request, queryset):
        self._transicionar(request, queryset, WorkflowMixin.Estado.ARCHIVADO, "archivado(s)")

    def has_publicar_permission(self, request) -> bool:
        """Gobierna qué acciones se ofrecen (`permissions=["publicar"]`)."""
        from apps.core.models import PERMISO_PUBLICAR

        return request.user.has_perm(f"{self.opts.app_label}.{PERMISO_PUBLICAR}")
