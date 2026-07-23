from django.conf import settings
from django.db import models
from django.utils import timezone


class TimeStampedMixin(models.Model):
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


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
    revisado_por = models.ForeignKey(  # [+] futuro
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    nota_revision = models.TextField(blank=True)  # [+] futuro

    objects = models.Manager()
    publicados = PublicadosManager()

    class Meta:
        abstract = True

    def transicionar(self, nuevo_estado: str, usuario=None) -> None:
        actual = self.Estado(self.estado)
        nuevo = self.Estado(nuevo_estado)
        if nuevo not in self.TRANSICIONES[actual]:
            raise ValueError(f"Transición inválida: {actual.label} → {nuevo.label}")
        self.estado = nuevo
        if nuevo == self.Estado.PUBLICADO:
            self.publicado_en = timezone.now()
        if nuevo in {self.Estado.PUBLICADO, self.Estado.BORRADOR} and usuario is not None:
            self.revisado_por = usuario
        self.save()

        from apps.core.tasks import notificar_transicion_editorial

        notificar_transicion_editorial.enqueue(
            modelo=self._meta.label,
            pk=self.pk,
            titulo=str(self),
            de_estado=actual.value,
            a_estado=nuevo.value,
            usuario_id=getattr(usuario, "pk", None),
        )
