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
from apps.core.almacenamiento import ruta_adjunto
from apps.core.validadores import extension_de, validar_adjunto


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


class NoticiaEnlace(models.Model):
    """Un enlace externo que acompaña a la noticia.

    Es una tabla y no el `JSONField` con el que `Medida` resuelve lo mismo: aquel se administra
    como un textarea de JSON crudo —sin widget ni validación— y aquí quien escribe es un editor,
    no un programador. **El contrato del API no cambia por eso**: los dos salen como
    `[{"titulo": …, "url": …}]` y el frontend no puede distinguirlos.
    """

    noticia = models.ForeignKey("contenidos.Noticia", on_delete=models.CASCADE,
                                related_name="enlaces")
    titulo = models.CharField(max_length=200, help_text="Lo que se lee en la ficha.")
    url = models.URLField(max_length=500)
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        # **Orden total, y no es adorno.** `orden` tiene `default=0`, así que el empate es la
        # norma: sin el remate por `id` el desempate lo elige el planificador de Postgres y dos
        # peticiones seguidas pueden devolver los anexos en orden distinto sin que nada falle.
        #
        # Y **no lleva `unique (noticia, orden)`**, que es lo que sí tiene `MedidaImagen`: con
        # `default=0` y un inline de `extra=1`, añadir dos filas sin tocar el número violaría la
        # restricción. Esa trampa no se hereda.
        ordering = ["orden", "id"]
        verbose_name = "enlace de la noticia"
        verbose_name_plural = "enlaces"

    def __str__(self) -> str:
        return self.titulo


class NoticiaArchivo(models.Model):
    """Un archivo adjunto de la noticia: el informe, el comunicado o la resolución que la nota
    acompaña.

    **No es un `biblioteca.Documento`**: aquello es el repositorio de publicaciones, con categoría,
    resumen y flujo editorial propios, y un anexo no tiene por qué aparecer ahí. Tampoco se indexa
    en el buscador.

    **El archivo es público desde que se guarda, aunque la noticia siga en borrador**: nginx sirve
    `/media/` entero como estático. Servirlo por una vista que comprobara el estado costaría una
    ruta, tumbaría el servido estático y pasaría cada descarga por gunicorn; se acepta y se avisa
    en el `help_text`.
    """

    noticia = models.ForeignKey("contenidos.Noticia", on_delete=models.CASCADE,
                                related_name="archivos")
    archivo = models.FileField(
        # `ruta_adjunto` mete un segmento aleatorio para que la URL no se pueda deducir del
        # título. Cierra lo adivinable, no el acceso: ver su docstring.
        upload_to=ruta_adjunto,
        validators=[validar_adjunto],
        help_text="Queda accesible por su URL en cuanto guardas, aunque la noticia siga en "
                  "borrador. No subas aquí nada reservado.",
    )
    titulo = models.CharField(max_length=200, help_text="Lo que se lee en la ficha.")
    orden = models.PositiveSmallIntegerField(default=0)
    #: Se guarda en vez de leerse al serializar: `archivo.size` toca el almacenamiento en cada
    #: petición y **lanza excepción si el archivo desapareció del disco**, o sea un 500 en una
    #: página pública por un anexo perdido. Guardado, la fila sigue pintando y lo que falla es la
    #: descarga, que se ve.
    peso_bytes = models.PositiveBigIntegerField(default=0, editable=False)

    class Meta:
        ordering = ["orden", "id"]  # total, por lo mismo que en NoticiaEnlace
        verbose_name = "archivo de la noticia"
        verbose_name_plural = "archivos"

    def __str__(self) -> str:
        return self.titulo

    @property
    def extension(self) -> str:
        return extension_de(self.archivo.name) if self.archivo else ""

    def save(self, *args, **kwargs):
        # **`_committed` es la pregunta correcta**, no si hay archivo: dice si este `FieldFile`
        # trae contenido nuevo sin escribir todavía. Volver a guardar la fila para corregir el
        # título no tiene por qué ir al almacenamiento a remedir lo mismo. Mismo criterio que
        # `ImagenOptimizadaMixin`.
        if self.archivo and not self.archivo._committed:
            self.peso_bytes = self.archivo.size
        super().save(*args, **kwargs)


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
