from django.conf import settings
from django.db import models
from django.utils import timezone

# Permiso custom que habilita las transiciones de publicación (spec 03). Se declara en el
# Meta.permissions de cada modelo Workflow porque Django no hereda `permissions` de un abstracto.
PERMISO_PUBLICAR = "puede_publicar"


def permiso_publicar(entidad: str) -> list[tuple[str, str]]:
    """Fila lista para el `Meta.permissions` de un modelo Workflow."""
    return [(PERMISO_PUBLICAR, f"Puede publicar y archivar {entidad}")]


class TimeStampedMixin(models.Model):
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class HtmlRicoMixin(models.Model):
    """Sanea los campos de `campos_html` **en `save()`** (ADR-D2).

    Vivía solo en `WorkflowAdmin.save_model`, y eso dejaba la garantía a medias: cualquier
    escritura que no pasara por el formulario del admin —un `loaddata`, un script, un futuro
    importador— metía el HTML tal cual en la base. El `help_text` de esos campos ya prometía que
    se saneaba al guardar, así que la promesa estaba escrita en el sitio equivocado.

    Aquí abajo la garantía es del modelo, y el resto del sistema la hereda: el frontend inyecta
    con `dangerouslySetInnerHTML`, el PDF y el índice de Meilisearch leen de la base.
    """

    #: Campos con HTML de CKEditor que hay que sanear.
    campos_html: tuple[str, ...] = ()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        from apps.core.sanitizar import sanear

        for campo in self.campos_html:
            setattr(self, campo, sanear(getattr(self, campo, "")))
        super().save(*args, **kwargs)


class PublicadosManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(estado=WorkflowMixin.Estado.PUBLICADO)


class WorkflowMixin(models.Model):
    """Flujo editorial del TDR: borrador → revisión → publicado, con avisos por correo."""

    class Estado(models.TextChoices):
        BORRADOR = "borrador", "Borrador"
        REVISION = "revision", "En revisión"
        PUBLICADO = "publicado", "Publicado"
        ARCHIVADO = "archivado", "Archivado"

    TRANSICIONES = {
        Estado.BORRADOR: {Estado.REVISION, Estado.ARCHIVADO},
        Estado.REVISION: {Estado.PUBLICADO, Estado.BORRADOR},
        Estado.PUBLICADO: {Estado.ARCHIVADO, Estado.BORRADOR},
        Estado.ARCHIVADO: {Estado.BORRADOR},
    }

    # Transiciones que exigen el permiso `puede_publicar` (grupo Publicador o Administrador);
    # el resto las puede hacer cualquier editor sobre su propio contenido.
    TRANSICIONES_RESERVADAS = {
        (Estado.REVISION, Estado.PUBLICADO),
        (Estado.PUBLICADO, Estado.ARCHIVADO),
        (Estado.PUBLICADO, Estado.BORRADOR),
        (Estado.BORRADOR, Estado.ARCHIVADO),
    }

    estado = models.CharField(
        max_length=12, choices=Estado.choices, default=Estado.BORRADOR, db_index=True
    )
    publicado_en = models.DateTimeField(null=True, blank=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    nota_revision = models.TextField(
        "nota de revisión",
        blank=True,
        help_text="Comentario del revisor al devolver el contenido a borrador.",
    )

    objects = models.Manager()
    publicados = PublicadosManager()

    class Meta:
        abstract = True

    # -- Flujo editorial ---------------------------------------------------
    def usuario_puede_publicar(self, usuario) -> bool:
        codigo = f"{self._meta.app_label}.{PERMISO_PUBLICAR}"
        return bool(usuario and (usuario.is_superuser or usuario.has_perm(codigo)))

    def transiciones_posibles(self, usuario=None) -> set[str]:
        """Estados alcanzables desde el actual, ya filtrados por el permiso del usuario.

        El admin usa esto para no ofrecer botones que luego van a fallar (spec 03).
        """
        actual = self.Estado(self.estado)
        posibles = set(self.TRANSICIONES[actual])
        if usuario is not None and not self.usuario_puede_publicar(usuario):
            posibles -= {d for d in posibles if (actual, d) in self.TRANSICIONES_RESERVADAS}
        return {e.value for e in posibles}

    def transicionar(self, nuevo_estado: str, usuario=None) -> None:
        actual = self.Estado(self.estado)
        nuevo = self.Estado(nuevo_estado)
        if nuevo not in self.TRANSICIONES[actual]:
            raise ValueError(f"Transición inválida: {actual.label} → {nuevo.label}")
        if (
            usuario is not None
            and (actual, nuevo) in self.TRANSICIONES_RESERVADAS
            and not self.usuario_puede_publicar(usuario)
        ):
            raise PermissionError(
                f"«{usuario}» no tiene permiso para pasar de {actual.label} a {nuevo.label}."
            )

        self.estado = nuevo
        if nuevo == self.Estado.PUBLICADO:
            self.publicado_en = timezone.now()
        if nuevo in {self.Estado.PUBLICADO, self.Estado.BORRADOR} and usuario is not None:
            self.revisado_por = usuario
        self.save()

        # El correo se encola: un SMTP lento o caído no puede bloquear el admin.
        from apps.core.tasks import notificar_transicion_editorial

        notificar_transicion_editorial.enqueue(
            modelo=self._meta.label,
            pk=self.pk,
            titulo=str(self),
            de_estado=actual.value,
            a_estado=nuevo.value,
            usuario_id=getattr(usuario, "pk", None),
        )
