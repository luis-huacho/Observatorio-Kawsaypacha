from django.contrib.postgres.fields import ArrayField
from django.db import models

from apps.core.models import (
    HtmlRicoMixin,
    TimeStampedMixin,
    WorkflowMixin,
    permiso_publicar,
)


def extracto(texto: str, limite: int = 80) -> str:
    """Recorte para identificar un texto largo de un vistazo (columnas del admin, `__str__`)."""
    texto = (texto or "").strip()
    return texto[:limite] + ("…" if len(texto) > limite else "")


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


class MedidaFichaACC(TimeStampedMixin):
    """Ficha de Adaptación al Cambio Climático (formulario docs/medida_fichas_acc.csv).

    Cada value_NNN corresponde, en el mismo orden, a la pregunta NNN de
    docs/medida_fichas_acc_fields.csv.

    **No cuelga de una Medida.** El formulario que PREDES reparte es autónomo y llega en lote
    por Excel, así que exigir una medida ya publicada a la cual colgarla bloqueaba la carga sin
    aportar nada: nadie leía la relación (no hay serializer, API ni frontend que la use). Quien
    identifica la ficha es `value_001`, el nombre de la experiencia.
    """

    value_001 = models.TextField("Nombre de la experiencia, práctica proyecto o programa")
    value_002 = models.TextField(
        "Ubicación",
        help_text="Indicar: Departamento / Provincia / Distrito / Comunidad Donde se "
        "implementó o implementa",
        blank=True,
        default="",
    )
    value_003 = models.TextField(
        "Institución u organización responsable de la ejecución",
        help_text="",
    )
    value_004 = models.TextField(
        "Persona de contacto: nombre, cargo, teléfono y correo",
        help_text="Se considera a la persona que puede aclarar dudas Respecto a la "
        "experiencia.",
        blank=True,
        default="",
    )
    value_005 = models.TextField(
        "Periodo de tiempo de la implementación",
        help_text="Indicar la fecha de inicio y cierre de la practica",
    )
    value_006 = models.TextField(
        "¿Qué peligros o amenazas naturales atiende esta práctica?",
        help_text="Marcar una o más opciones",
    )
    value_007 = models.TextField(
        "Descripción del problema",
        help_text="Describa brevemente la problemática en relación con la Manifestación "
        "de los impactos del peligro que atiende Esta práctica (máx. 5 líneas)",
    )
    value_008 = models.TextField(
        "Descripción de la práctica, experiencia, programa o proyecto",
        help_text="Describa brevemente en qué consiste la práctica, cómo funciona y qué "
        "medidas se han implementado (máx. 10 líneas)",
        blank=True,
        default="",
    )
    value_009 = models.TextField(
        "Enfoque de la práctica, experiencia, programa o proyecto",
        help_text="Indique con qué enfoque se relaciona con mayor cercanía. Puede marcar "
        "más de una opción",
    )
    value_010 = models.TextField(
        "La práctica incorpora saberes ancestrales y enfoque de género? ¿Cuáles?",
        help_text="indique hasta 3 saberes ancestrales y 3 prácticas de enfoque de género",
    )
    value_011 = models.TextField(
        "Resultados cuantitativos o beneficios logrados con la práctica, experiencia, "
        "programa o proyecto",
        help_text="Describe los resultados clave, de preferencia utilizando cifras: Nº de "
        "personas / familias beneficiadas, hectáreas, litros de agua almacenada, etc.",
    )
    value_012 = models.TextField(
        "Resultados cualitativos o beneficios logrados con la práctica, experiencia, "
        "programa o proyecto",
        help_text="Describe brevemente los cambios positivos que ha generado el proyecto: "
        "en el comportamiento de sus beneficiarios, actitudes, prácticas, conocimientos, "
        "etc.",
    )
    value_013 = models.TextField(
        "Costo aproximado de la implementación y fuente de financiamiento",
        help_text="Indicar el monto aproximado en soles y fuente (institución, programa, "
        "otro)",
    )
    value_014 = models.TextField(
        "Principales factores de éxito",
        help_text="Indica al menos 3 factores que han contribuido a que la práctica se "
        "desarrolle con éxito (por ejemplo: participación activa de las comunidades, "
        "articulación con gobiernos locales y otras organizaciones, etc)",
    )
    value_015 = models.TextField(
        "Principales lecciones aprendidas",
        help_text="Indica al menos 3 lecciones aprendidas claves a resaltar y tener en "
        "cuenta al replicar este tipo de intervención",
    )
    value_016 = models.TextField(
        "¿Quién se encarga de mantener o gestionar actualmente la práctica?",
        help_text="Describir brevemente si es una persona, entidad o comunidad, e indicar "
        "el rol que cumplen.",
    )
    value_017 = models.TextField(
        "¿Es replicable en otras comunidades? ¿Qué se necesitaría para replicarla?",
        help_text="Indicar brevemente por qué es replicable y qué necesitaría par serlo. "
        "Por ejemplo: Costos accesibles, participación comunitaria, resultados "
        "demostrados.",
    )

    class Meta:
        verbose_name = "Ficha de Adaptación al Cambio Climático"
        verbose_name_plural = "fichas de Adaptación al Cambio Climático"
        # Orden TOTAL: `creado_en` empata en las filas de una misma importación —entran todas en
        # el mismo `bulk_create`— y un orden parcial paginado repite y se salta filas en silencio.
        ordering = ["-creado_en", "id"]

    def __str__(self) -> str:
        return f"Ficha ACC · {extracto(self.value_001)}"
