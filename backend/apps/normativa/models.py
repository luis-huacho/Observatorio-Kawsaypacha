from django.contrib.postgres.fields import ArrayField
from django.db import models

from apps.core.models import (
    HtmlRicoMixin,
    TimeStampedMixin,
    WorkflowMixin,
    permiso_publicar,
)


class Norma(TimeStampedMixin, WorkflowMixin, HtmlRicoMixin):
    """Norma del marco GRD/ACC, con ficha propia en /normativa/{slug}."""

    campos_html = ("contenido",)

    class Tipo(models.TextChoices):
        LEY = "Ley", "Ley"
        DS = "DS", "Decreto Supremo"
        RM = "RM", "Resolución Ministerial"
        RJ = "RJ", "Resolución Jefatural"
        ORDENANZA = "Ordenanza", "Ordenanza"

    class Ambito(models.TextChoices):
        NACIONAL = "nacional", "Nacional"
        REGIONAL = "regional", "Regional"
        LOCAL = "local", "Local"

    slug = models.SlugField(max_length=120, unique=True)
    titulo = models.CharField(max_length=300)
    tipo = models.CharField(max_length=12, choices=Tipo.choices)
    ambito = models.CharField("ámbito", max_length=10, choices=Ambito.choices, db_index=True)
    fecha = models.DateField(db_index=True)
    resumen = models.TextField(max_length=700)
    contenido = models.TextField(
        blank=True,
        help_text="Análisis desarrollado de la ficha (HTML de CKEditor 5, saneado al guardar).",
    )
    # Dos vías de acceso a la publicación oficial; el serializer prefiere el PDF alojado
    # porque los portales del Estado reorganizan sus URL y un enlace roto inutiliza el
    # repositorio. Los tres estados —PDF, portal, sin enlace— son reales.
    url_oficial = models.URLField(blank=True, null=True)
    documento = models.ForeignKey(
        "biblioteca.Documento",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="normas",
        help_text="PDF alojado por PREDES. Vía preferente; habilita el resumen con IA.",
    )
    analisis_predes = models.TextField(
        "análisis de PREDES", blank=True, null=True,
        help_text="Nota breve que se muestra en el listado."
    )
    imagen_portada = models.ImageField(
        upload_to="normativa/%Y/%m/",
        null=True,
        blank=True,
        help_text="Si lo dejas vacío se usa la ilustración institucional de normativa.",
    )
    imagen_titulo = models.CharField("pie de la imagen", max_length=300, blank=True)
    palabras_clave = ArrayField(
        models.CharField(max_length=60),
        verbose_name="palabras clave",
        default=list,
        blank=True,
    )

    # [+] futuro
    numero = models.CharField(max_length=80, blank=True, help_text='P. ej. "DS 048-2011-PCM".')
    estado_vigencia = models.CharField(
        "estado de vigencia",
        max_length=12,
        blank=True,
        choices=[("vigente", "Vigente"), ("derogada", "Derogada"), ("modificada", "Modificada")],
    )

    class Meta:
        ordering = ["-fecha"]
        verbose_name = "norma"
        verbose_name_plural = "normativa"
        permissions = permiso_publicar("normas")
        indexes = [models.Index(fields=["estado", "-fecha"])]

    def __str__(self) -> str:
        return self.titulo

    @property
    def anio(self) -> int:
        return self.fecha.year
