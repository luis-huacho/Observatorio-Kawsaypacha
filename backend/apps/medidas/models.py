from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils.html import escape

from apps.core.models import (
    EstadoIAMixin,
    HtmlRicoMixin,
    ImagenOptimizadaMixin,
    TimeStampedMixin,
    WorkflowMixin,
    permiso_publicar,
)


def extracto(texto: str, limite: int = 80) -> str:
    """Recorte para identificar un texto largo de un vistazo (columnas del admin, `__str__`)."""
    texto = (texto or "").strip()
    return texto[:limite] + ("…" if len(texto) > limite else "")


class Medida(TimeStampedMixin, WorkflowMixin, HtmlRicoMixin, ImagenOptimizadaMixin,
             EstadoIAMixin):
    """Buena práctica o experiencia de campo documentada por PREDES.

    Puede **nacer de una ficha ACC** (ADR-D10): el editor elige una arriba del formulario, marca
    «Procesar con IA» y el worker redacta el borrador desde las respuestas de esa ficha. Es el
    tercer caso del mecanismo de ADR-D7/D8 y el primero cuyo origen no es una URL.
    """

    campos_html = ("contenido",)
    campos_imagen = ("imagen_portada",)

    #: Clase del bloque de contacto que la tarea pega al final del contenido. **Es el marcador**,
    #: y por eso es una clase y no un comentario HTML: `sanear()` corre con `strip_comments=True`
    #: y se llevaría un comentario en silencio, dejando `tiene_bloque_de_contacto()` en falso
    #: sobre un contenido que sí lleva datos personales.
    CLASE_CONTACTO = "contacto-ficha-acc"

    #: Sin esto no se publica. `contenido` no está: una medida puede ser un apunte breve, y la
    #: portada ya se resuelve sola desde el peligro.
    CAMPOS_PARA_PUBLICAR = ("titulo", "tipo_peligro", "ambito", "resultado", "resumen_corto")

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
    titulo = models.CharField("título", max_length=200)
    # Nullable desde ADR-D10: un borrador recién creado desde una ficha ACC todavía no tiene
    # peligro, y replegarlo a una opción cualquiera pondría una clasificación falsa que nadie
    # revisaría porque el campo se vería lleno. Lo que no puede es publicarse así — de eso se
    # encarga `faltantes_para_publicar()`.
    tipo_peligro = models.ForeignKey(
        "peligros.TipoPeligro",
        verbose_name="tipo de peligro",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="medidas",
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

    #: La procedencia (ADR-D10). `PROTECT` y no `SET_NULL`: borrar la ficha borraría de dónde
    #: salió la medida **y liberaría el candado**, dejando redactar dos medidas de lo mismo.
    ficha_acc = models.ForeignKey(
        "medidas.MedidaFichaACC",
        verbose_name="ficha ACC de origen",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="medidas",
        help_text="Ficha de la que la IA redactó esta medida. Queda como procedencia.",
    )

    class Meta:
        ordering = ["-publicado_en", "-creado_en"]
        verbose_name = "medida"
        permissions = permiso_publicar("medidas")
        indexes = [models.Index(fields=["estado", "-publicado_en"])]

    def __str__(self) -> str:
        return self.titulo

    # -- Flujo editorial ---------------------------------------------------
    def tiene_bloque_de_contacto(self) -> bool:
        """¿El contenido todavía lleva los datos de contacto que venían de la ficha ACC?"""
        return self.CLASE_CONTACTO in (self.contenido or "")

    def avisos_al_publicar(self) -> list[str]:
        if not self.tiene_bloque_de_contacto():
            return []
        return [
            "aún lleva el bloque de contacto de la ficha ACC, con el nombre, el teléfono y el "
            "correo de un tercero. El contenido es público: bórralo del contenido o confirma "
            "que esa persona autorizó publicarlo."
        ]

    def bloque_de_contacto(self) -> str:
        """El HTML del contacto, listo para pegarse al final del contenido.

        El valor se escapa porque lo rellenó un tercero en un Excel. La clase es el marcador y
        sobrevive al saneador: `figure`, `div`, `span` y `p` conservan `class` (ver
        `core/sanitizar.py`).
        """
        contacto = " ".join((self.ficha_acc.value_004 or "").split()) if self.ficha_acc_id else ""
        if not contacto:
            return ""
        return (
            f'<div class="{self.CLASE_CONTACTO}"><h3>Contacto de la experiencia</h3>'
            f"<p>{escape(contacto)}</p></div>"
        )


class MedidaImagen(TimeStampedMixin, ImagenOptimizadaMixin):
    """Foto de la galería de una medida.

    El pie es obligatorio a propósito: una foto sin pie no se puede citar en un informe ni
    describir a quien navega con lector de pantalla.
    """

    campos_imagen = ("imagen",)

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


class FichasACCQuerySet(models.QuerySet):
    def disponibles_para_ia(self, incluyendo=None):
        """Las que todavía no ha gastado la IA (ADR-D10).

        **El candado es derivado y no un campo:** una ficha está gastada si existe una Medida que
        la referencia y cuya IA llegó a escribir. Así hay una sola fuente de verdad —el mismo
        `redactada_por_ia` que ya gobierna a noticias y normas—, y una medida fallida o borrada
        devuelve su ficha a la circulación sola, sin nada que sincronizar.

        `incluyendo` no es una comodidad: sin ella, una medida ya redactada **no se podría volver
        a guardar nunca**, porque su propia ficha habría salido del queryset del select y el
        `ModelChoiceField` respondería «Escoja una opción válida» sin decir por qué.
        """
        libres = self.exclude(medidas__redactada_por_ia=True)
        if incluyendo is None:
            return libres
        return self.filter(models.Q(pk__in=libres.values("pk")) | models.Q(pk=incluyendo))


class MedidaFichaACC(TimeStampedMixin):
    """Ficha de Adaptación al Cambio Climático (formulario docs/medida_fichas_acc.csv).

    Cada value_NNN corresponde, en el mismo orden, a la pregunta NNN de
    docs/medida_fichas_acc_fields.csv.

    **No cuelga de una Medida.** El formulario que PREDES reparte es autónomo y llega en lote
    por Excel, así que exigir una medida ya publicada a la cual colgarla bloqueaba la carga sin
    aportar nada: nadie leía la relación (no hay serializer, API ni frontend que la use). Quien
    identifica la ficha es `value_001`, el nombre de la experiencia.
    """

    objects = FichasACCQuerySet.as_manager()

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
