from django.contrib.postgres.fields import ArrayField
from django.db import models

from apps.core.models import (
    HtmlRicoMixin,
    ImagenOptimizadaMixin,
    RedaccionIAMixin,
    TimeStampedMixin,
    WorkflowMixin,
    permiso_publicar,
)


class Noticia(TimeStampedMixin, WorkflowMixin, HtmlRicoMixin, ImagenOptimizadaMixin,
              RedaccionIAMixin):
    campos_html = ("cuerpo",)
    campos_imagen = ("imagen_portada",)

    class Tipo(models.TextChoices):
        NOTICIA = "noticia", "Noticia"
        ARTICULO = "articulo", "Artículo"
        OPINION = "opinion", "Opinión"
        PUBLICACION = "publicacion", "Publicación"
        BASE_DATOS = "base_datos", "Base de datos"

    slug = models.SlugField(max_length=120, unique=True)
    titulo = models.CharField(max_length=250)
    bajada = models.TextField(max_length=500)
    cuerpo = models.TextField(
        blank=True, help_text="HTML de CKEditor 5. Se sanea al guardar (ADR-D2)."
    )
    # El valor crudo **es el nombre de la ilustración por defecto** (`/img/default/<tipo>.svg`),
    # así que añadir una opción es también añadir un archivo — lo vigila `imagenes.clave_noticia`.
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.NOTICIA)
    autor = models.CharField(max_length=150, blank=True)
    fecha = models.DateField(db_index=True)
    imagen_portada = models.ImageField(
        upload_to="noticias/%Y/%m/",
        null=True,
        blank=True,
        help_text="Si lo dejas vacío se usa la ilustración institucional del tipo de contenido.",
    )
    imagen_titulo = models.CharField("pie de la imagen", max_length=300, blank=True)
    palabras_clave = ArrayField(
        models.CharField(max_length=60),
        verbose_name="palabras clave",
        default=list,
        blank=True,
    )
    destacada = models.BooleanField(default=False, help_text="Aparece en la portada.")

    class Meta:
        # Destacadas primero y, dentro de cada grupo, lo más reciente. `-id` remata el orden y no
        # es decorativo: `fecha` es un DateField, los empates del mismo día son la norma y el
        # listado se pagina, así que sobre un orden parcial `LIMIT`/`OFFSET` repetiría filas entre
        # páginas y se saltaría otras, en silencio.
        ordering = ["-destacada", "-fecha", "-id"]
        verbose_name = "noticia"
        permissions = permiso_publicar("noticias")
        indexes = [models.Index(fields=["estado", "-destacada", "-fecha"])]

    def __str__(self) -> str:
        return self.titulo

    @property
    def anio(self) -> int:
        return self.fecha.year


class Video(TimeStampedMixin, WorkflowMixin):
    titulo = models.CharField(max_length=250)
    descripcion = models.TextField("descripción", blank=True)
    url = models.URLField(help_text="Enlace de YouTube o Vimeo.")
    fecha = models.DateField(db_index=True)
    tema = models.ForeignKey(
        "peligros.TipoPeligro",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="videos",
    )
    # [+] futuro
    thumbnail_override = models.ImageField(upload_to="videos/", null=True, blank=True)
    duracion = models.CharField(max_length=12, blank=True)

    class Meta:
        ordering = ["-fecha"]
        verbose_name = "video"
        permissions = permiso_publicar("videos")

    def __str__(self) -> str:
        return self.titulo


class Evento(TimeStampedMixin, WorkflowMixin, ImagenOptimizadaMixin):

    campos_imagen = ("imagen",)
    class Modalidad(models.TextChoices):
        PRESENCIAL = "presencial", "Presencial"
        VIRTUAL = "virtual", "Virtual"
        MIXTA = "mixta", "Mixta"

    titulo = models.CharField(max_length=250)
    descripcion = models.TextField(blank=True)
    inicio = models.DateTimeField(db_index=True)
    fin = models.DateTimeField(null=True, blank=True)
    lugar = models.CharField(max_length=250, blank=True)
    modalidad = models.CharField(
        max_length=12, choices=Modalidad.choices, default=Modalidad.PRESENCIAL
    )
    # [+] futuro
    url_inscripcion = models.URLField(blank=True, null=True)
    organizador = models.CharField(max_length=200, blank=True)
    imagen = models.ImageField(upload_to="eventos/%Y/%m/", null=True, blank=True)

    class Meta:
        ordering = ["inicio"]
        verbose_name = "evento"
        permissions = permiso_publicar("eventos")

    def __str__(self) -> str:
        return f"{self.titulo} ({self.inicio:%d/%m/%Y})"
