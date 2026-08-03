from django.db import models

from apps.core.models import TimeStampedMixin, WorkflowMixin, permiso_publicar


class CategoriaDocumento(TimeStampedMixin):
    nombre = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=60, unique=True)
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["orden", "nombre"]
        verbose_name = "categoría de documento"
        verbose_name_plural = "categorías de documento"

    def __str__(self) -> str:
        return self.nombre


class Documento(TimeStampedMixin, WorkflowMixin):
    """Publicación del repositorio. Puede estar alojada (PDF) o ser un enlace externo."""

    class EstadoIA(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        PROCESANDO = "procesando", "Procesando"
        OK = "ok", "Generado"
        ERROR = "error", "Error"

    titulo = models.CharField(max_length=300)
    categoria = models.ForeignKey(
        CategoriaDocumento, on_delete=models.PROTECT, related_name="documentos"
    )
    archivo = models.FileField(upload_to="biblioteca/%Y/%m/", null=True, blank=True)
    url_externa = models.URLField(blank=True, null=True)
    resumen = models.TextField(blank=True)
    resumen_generado_por_ia = models.BooleanField(default=False)
    autor_institucion = models.CharField(max_length=200, blank=True)
    fecha_publicacion = models.DateField(null=True, blank=True)
    ia_estado = models.CharField(
        max_length=12, choices=EstadoIA.choices, default=EstadoIA.PENDIENTE
    )
    log_ia = models.TextField(blank=True)

    # [+] futuro
    portada = models.ImageField(upload_to="biblioteca/portadas/", null=True, blank=True)
    paginas = models.PositiveSmallIntegerField(null=True, blank=True)
    peso_bytes = models.PositiveBigIntegerField(null=True, blank=True, editable=False)
    descargas = models.PositiveIntegerField(default=0, editable=False)
    idioma = models.CharField(max_length=20, blank=True, default="es")

    class Meta:
        ordering = ["-fecha_publicacion", "-creado_en"]
        verbose_name = "documento"
        permissions = permiso_publicar("documentos")
        constraints = [
            # Un documento sin archivo ni enlace no es un documento: no hay nada que abrir.
            models.CheckConstraint(
                condition=~(models.Q(archivo="") & models.Q(url_externa__isnull=True)),
                name="documento_con_archivo_o_url",
            )
        ]

    def __str__(self) -> str:
        return self.titulo

    @property
    def tiene_pdf_local(self) -> bool:
        return bool(self.archivo)
