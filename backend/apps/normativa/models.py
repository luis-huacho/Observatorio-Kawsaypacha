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


class TipoNorma(TimeStampedMixin):
    """Qué clase de norma es: ley, decreto supremo, ordenanza…

    Era un `TextChoices` de cinco opciones fijas, y ampliarlo exigía tocar el modelo, migrar y
    desplegar. Es catálogo por el mismo motivo que `EntidadEmisora` (ADR-D11): lo mantiene PREDES.

    **`sinonimos` no es decorativo**: es lo que el importador de Excel consulta para reconocer
    «D.S.» u «Ordenanza Regional» como lo que son. Sin él, dar de alta un tipo desde el admin lo
    dejaría disponible en el formulario y en la IA, pero el importador seguiría omitiendo sus
    filas, y nada relacionaría las dos cosas.
    """

    nombre = models.CharField(max_length=120, unique=True)
    abreviatura = models.CharField(
        max_length=20, blank=True,
        help_text='Sigla con la que se cita, p. ej. "DS". Es lo que se muestra en las tarjetas '
                  "del listado, donde no cabe el nombre completo. Vacía en «Ley» u «Ordenanza», "
                  "que ya son cortas.",
    )
    slug = models.SlugField(max_length=60, unique=True)
    sinonimos = ArrayField(
        models.CharField(max_length=80),
        verbose_name="sinónimos",
        default=list,
        blank=True,
        help_text="Otras formas en que llega escrito en los Excel que se importan, separadas por "
                  "comas («D.S.», «Ordenanza Regional»). No hace falta cuidar tildes ni "
                  "mayúsculas: se comparan normalizados.",
    )
    orden = models.PositiveSmallIntegerField(
        default=0, help_text="Los de menor número salen primero en el desplegable."
    )

    class Meta:
        ordering = ["orden", "nombre"]
        verbose_name = "tipo de norma"
        verbose_name_plural = "tipos de norma"

    def __str__(self) -> str:
        return self.nombre


class EntidadEmisora(TimeStampedMixin):
    """Institución que dicta la norma: PCM, un gobierno regional, una municipalidad.

    Es catálogo y no texto libre por una razón muy concreta: escrito a mano, «PCM»,
    «Presidencia del Consejo de Ministros» y «P.C.M.» serían tres valores distintos y el filtro
    del listado no serviría para nada. PREDES lo mantiene desde su propia pantalla del admin, y
    también puede dar de alta una entidad sin salir del formulario de la norma, con el «+» del
    desplegable.
    """

    nombre = models.CharField(max_length=200, unique=True)
    sigla = models.CharField(
        max_length=20, blank=True,
        help_text='Abreviatura con la que se la conoce, p. ej. "PCM" o "MINAM". Es lo que se '
                  "muestra en las tarjetas del listado, donde no cabe el nombre completo.",
    )
    slug = models.SlugField(max_length=80, unique=True)
    orden = models.PositiveSmallIntegerField(
        default=0, help_text="Las de menor número salen primero en el desplegable."
    )

    class Meta:
        ordering = ["orden", "nombre"]
        verbose_name = "entidad emisora"
        verbose_name_plural = "entidades emisoras"

    def __str__(self) -> str:
        return self.nombre


class Norma(TimeStampedMixin, WorkflowMixin, HtmlRicoMixin, ImagenOptimizadaMixin,
            RedaccionIAMixin):
    """Norma del marco GRD/ACC, con ficha propia en /normativa/{slug}.

    Puede nacer de una URL: `RedaccionIAMixin` trae `url_origen` y el candado con los que la
    IA redacta la ficha desde la publicación oficial, sea página web o PDF (ADR-D8). Lo que
    **no** escribe la IA es `analisis_predes` —es la voz institucional, y es justo lo que
    aporta la persona— ni `url_oficial`, que no puede acabar presentando un enlace cualquiera
    como publicación oficial.
    """

    campos_html = ("contenido",)
    campos_imagen = ("imagen_portada",)

    #: Sin tipo no se publica. Antes era imposible que faltara —el campo era obligatorio en el
    #: formulario—, pero al pasar a clave foránea admite nulo, que es lo que la IA y el importador
    #: necesitan para decir «no lo sé». La guarda devuelve la garantía en el único punto donde
    #: importa. De paso cierra un agujero que ya existía: una norma redactada por IA con el tipo
    #: en blanco sí se podía publicar, y salía en el listado con el chip vacío.
    CAMPOS_PARA_PUBLICAR = ("tipo",)

    class Ambito(models.TextChoices):
        NACIONAL = "nacional", "Nacional"
        REGIONAL = "regional", "Regional"
        LOCAL = "local", "Local"

    slug = models.SlugField(max_length=120, unique=True)
    titulo = models.CharField(max_length=300)
    entidad_emisora = models.ForeignKey(
        EntidadEmisora,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="normas",
        verbose_name="entidad emisora",
        help_text="Institución que la dicta. Vacío si no consta.",
    )
    tipo = models.ForeignKey(
        TipoNorma,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="normas",
        help_text="Vacío si no consta; hace falta para publicar.",
    )
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
