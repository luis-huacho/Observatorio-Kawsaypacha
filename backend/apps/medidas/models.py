from django.contrib.postgres.fields import ArrayField
from django.db import models

from apps.core.models import (
    HtmlRicoMixin,
    TimeStampedMixin,
    WorkflowMixin,
    permiso_publicar,
)


class Medida(TimeStampedMixin, WorkflowMixin, HtmlRicoMixin):
    """Buena práctica o experiencia de campo documentada por PREDES."""

    campos_html = ("contenido",)

    class Ambito(models.TextChoices):
        COMUNAL = "comunal", "Comunal"
        DISTRITAL = "distrital", "Distrital"
        PROVINCIAL = "provincial", "Provincial"
        REGIONAL = "regional", "Regional"

    class Resultado(models.TextChoices):
        EXITO = "exito", "Éxito"
        LECCION = "leccion", "Lección aprendida"
        MAL_ADAPTACION = "mal_adaptacion", "Mala adaptación"

    slug = models.SlugField(max_length=120, unique=True)
    titulo = models.CharField(max_length=200)
    tipo_peligro = models.ForeignKey(
        "peligros.TipoPeligro", on_delete=models.PROTECT, related_name="medidas"
    )
    ambito = models.CharField("Alcance de la experiencia", max_length=12, choices=Ambito.choices)
    resultado = models.CharField(max_length=16, choices=Resultado.choices, db_index=True)
    distrito = models.ForeignKey(
        "territorio.Distrito",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="medidas",
    )
    comunidad = models.CharField(max_length=150, blank=True)
    resumen_corto = models.TextField("resumen corto", max_length=500)
    contenido = models.TextField(
        blank=True, help_text="HTML de CKEditor 5. Se sanea al guardar (ADR-D2)."
    )
    video_url = models.URLField("URL del video", blank=True, null=True)
    imagen_portada = models.ImageField(
        upload_to="medidas/%Y/%m/",
        null=True,
        blank=True,
        help_text="Si lo dejas vacío se usa la ilustración institucional del peligro.",
    )
    imagen_titulo = models.CharField(
        "pie de la imagen", max_length=300, blank=True,
        help_text="Se muestra debajo de la portada."
    )
    palabras_clave = ArrayField(
        models.CharField(max_length=60),
        verbose_name="palabras clave",
        default=list,
        blank=True,
    )
    enlaces = models.JSONField(
        default=list, blank=True, help_text='Lista de {"titulo": …, "url": …}.'
    )
    # La portada pide "casos destacados" (spec 06); sin este campo habría que elegirlos por
    # fecha, que no es un criterio editorial.
    destacada = models.BooleanField(default=False)

    # [+] futuro
    centro_poblado = models.ForeignKey(
        "territorio.CentroPoblado",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="medidas",
    )
    fecha_implementacion = models.DateField(null=True, blank=True)
    actores = models.CharField(max_length=300, blank=True)
    costo_referencial = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    documentos = models.ManyToManyField("biblioteca.Documento", blank=True, related_name="medidas")

    class Meta:
        ordering = ["-publicado_en", "-creado_en"]
        verbose_name = "medida"
        permissions = permiso_publicar("medidas")
        indexes = [models.Index(fields=["estado", "-publicado_en"])]

    def __str__(self) -> str:
        return self.titulo


class MedidaImagen(TimeStampedMixin):
    """Foto de la galería de una medida.

    El pie es obligatorio a propósito: una foto sin pie no se puede citar en un informe ni
    describir a quien navega con lector de pantalla.
    """

    medida = models.ForeignKey(Medida, on_delete=models.CASCADE, related_name="galeria")
    imagen = models.ImageField(upload_to="medidas/%Y/%m/")
    pie = models.CharField(max_length=300)
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["orden"]
        verbose_name = "imagen de la medida"
        verbose_name_plural = "galería"
        constraints = [
            models.UniqueConstraint(fields=["medida", "orden"], name="unico_orden_galeria_medida")
        ]

    def __str__(self) -> str:
        return f"{self.medida.slug} #{self.orden}"
