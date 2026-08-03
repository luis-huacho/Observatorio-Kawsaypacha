from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.models import TimeStampedMixin


class PorSlugManager(models.Manager):
    """Llave natural por slug, para que las fixtures no dependan de pks autoincrementales."""

    def get_by_natural_key(self, slug):
        return self.get(slug=slug)


class TipoPeligro(TimeStampedMixin):
    """Los 9 peligros del Excel base (Sismo, Heladas, …, Movimientos en masa)."""

    objects = PorSlugManager()

    # El slug lleva guion BAJO, no guion medio: es la clave de las propiedades `nivel_<slug>`
    # del tile de CCPP y de la constante PELIGROS del frontend. Un `slugify()` produciría
    # "lluvias-intensas" y el visor dejaría de pintar sin que nada más fallara.
    slug = models.SlugField(max_length=50, unique=True)
    nombre = models.CharField(
        max_length=100,
        unique=True,
        help_text="Valor de la columna PELIGRO del Excel, no el título de la hoja.",
    )
    hoja_excel = models.CharField(
        max_length=100,
        blank=True,
        help_text="Título de la hoja en el Excel canónico. Lo usa el importador para mapear "
        "hoja → peligro; difiere del nombre en Lluvias e Incendios Forestales.",
    )
    categoria_geo = models.CharField(
        "categoría geodinámica",
        max_length=100,
        blank=True,
        help_text="El TIP_PELIG de la fuente (Geodinamica interna/externa, Metereologicas).",
    )
    orden = models.PositiveSmallIntegerField(default=0)
    descripcion = models.TextField("descripción", blank=True)  # [+] futuro
    icono = models.CharField(max_length=50, blank=True)  # [+] futuro
    color = models.CharField(max_length=7, blank=True)  # [+] futuro (hex)

    class Meta:
        ordering = ["orden", "nombre"]
        verbose_name = "tipo de peligro"
        verbose_name_plural = "tipos de peligro"

    def __str__(self) -> str:
        return self.nombre

    def natural_key(self):
        return (self.slug,)


class Fuente(TimeStampedMixin):
    nombre = models.CharField(max_length=200, unique=True)
    sigla = models.CharField(max_length=50, blank=True)
    url_base = models.URLField(blank=True)  # [+] futuro

    class Meta:
        ordering = ["nombre"]

    def __str__(self) -> str:
        return self.sigla or self.nombre


class ClasificacionPeligro(TimeStampedMixin):
    """Nivel de peligro (1-4) de un centro poblado para un tipo de peligro.

    Solo 3,238 de los 8,968 CCPP tienen alguna clasificación: la ausencia de fila significa
    "sin dato", que no es lo mismo que nivel bajo.
    """

    NIVELES = {1: "Bajo", 2: "Medio", 3: "Alto", 4: "Muy alto"}

    centro_poblado = models.ForeignKey(
        "territorio.CentroPoblado", on_delete=models.CASCADE, related_name="clasificaciones"
    )
    tipo_peligro = models.ForeignKey(
        TipoPeligro, on_delete=models.PROTECT, related_name="clasificaciones"
    )
    nivel = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(4)]
    )
    fuente = models.ForeignKey(Fuente, null=True, blank=True, on_delete=models.SET_NULL)
    fuente_url = models.URLField(blank=True)
    dataset_upload = models.ForeignKey(
        "datasets.DatasetUpload",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="clasificaciones",
        help_text="Carga que trajo este dato (trazabilidad).",
    )
    anio_dato = models.PositiveSmallIntegerField(null=True, blank=True)  # [+] futuro
    vigente = models.BooleanField(default=True)  # [+] futuro (histórico de reemplazos)

    class Meta:
        verbose_name = "clasificación de peligro"
        verbose_name_plural = "clasificaciones de peligro"
        constraints = [
            models.UniqueConstraint(
                fields=["centro_poblado", "tipo_peligro"],
                name="unica_clasificacion_ccpp_peligro",
            ),
            models.CheckConstraint(
                condition=models.Q(nivel__gte=1) & models.Q(nivel__lte=4),
                name="nivel_peligro_entre_1_y_4",
            ),
        ]
        indexes = [
            models.Index(fields=["tipo_peligro", "nivel"]),
            models.Index(fields=["centro_poblado"]),
        ]

    def __str__(self) -> str:
        return f"{self.centro_poblado_id} · {self.tipo_peligro} · nivel {self.nivel}"


class CategoriaEvento(TimeStampedMixin):
    """Agrupación SIGRID de los tipos de evento del Excel de frecuencia (4)."""

    objects = PorSlugManager()

    slug = models.SlugField(max_length=50, unique=True)
    nombre = models.CharField(max_length=100)
    orden = models.PositiveSmallIntegerField(default=0)
    # Encabezado del subtotal en el Excel ancho (TOT_GEODINAMICA EXTERNA, …). Lo usa el
    # importador para leer los TOT_* como total declarado (ADR-D1).
    columna_total = models.CharField(max_length=60, blank=True)

    class Meta:
        ordering = ["orden"]
        verbose_name = "categoría de evento"
        verbose_name_plural = "categorías de evento"

    def __str__(self) -> str:
        return self.nombre

    def natural_key(self):
        return (self.slug,)


class TipoEvento(TimeStampedMixin):
    """Tipos de emergencia del Excel de frecuencia (~25: huayco, helada, …)."""

    objects = PorSlugManager()

    slug = models.SlugField(max_length=60, unique=True)
    nombre = models.CharField(max_length=100, unique=True)
    categoria = models.ForeignKey(CategoriaEvento, on_delete=models.PROTECT, related_name="tipos")
    orden = models.PositiveSmallIntegerField(default=0)
    # Encabezado exacto de la columna en el Excel ancho (HUAYCO, BAJA TEMPERATURA, …).
    columna_excel = models.CharField(max_length=60, blank=True)

    class Meta:
        ordering = ["categoria__orden", "orden"]
        verbose_name = "tipo de evento"
        verbose_name_plural = "tipos de evento"

    def __str__(self) -> str:
        return self.nombre

    def natural_key(self):
        return (self.slug,)


class FrecuenciaEmergencia(TimeStampedMixin):
    """Nº de emergencias registradas por distrito × tipo de evento
    (Excel Base_Frecuencia_Peligro_Cusco.xlsx, normalizado a formato largo)."""

    distrito = models.ForeignKey(
        "territorio.Distrito", on_delete=models.CASCADE, related_name="frecuencias"
    )
    tipo_evento = models.ForeignKey(
        TipoEvento, on_delete=models.PROTECT, related_name="frecuencias"
    )
    conteo = models.PositiveIntegerField()
    # Texto de la fuente tal cual ("2005-2022"). Es POR DISTRITO: no existe un periodo
    # regional, así que los totales entre distritos no son directamente comparables.
    rango_fecha = models.CharField(max_length=50, blank=True)
    fuente = models.CharField(max_length=100, blank=True)
    fuente_url = models.URLField(blank=True)
    dataset_upload = models.ForeignKey(
        "datasets.DatasetUpload",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="frecuencias",
    )
    anio_inicio = models.PositiveSmallIntegerField(null=True, blank=True)  # [+] futuro
    anio_fin = models.PositiveSmallIntegerField(null=True, blank=True)  # [+] futuro

    class Meta:
        verbose_name = "frecuencia de emergencia"
        verbose_name_plural = "frecuencias de emergencia"
        constraints = [
            models.UniqueConstraint(
                fields=["distrito", "tipo_evento"], name="unica_frecuencia_distrito_evento"
            )
        ]
        indexes = [models.Index(fields=["distrito"]), models.Index(fields=["tipo_evento"])]

    def __str__(self) -> str:
        return f"{self.distrito} · {self.tipo_evento}: {self.conteo}"


class TotalDeclaradoEmergencias(TimeStampedMixin):
    """Subtotal por categoría que la fuente declara SIN desglosar por evento (ADR-D1).

    El distrito de Cusco trae los cuatro TOT_* llenos (TOTAL 134) y ninguna columna de evento.
    Descartarlos dejaría a la capital regional mostrando 0 emergencias, que es peor que no
    mostrar nada. Regla: si hay desglose se usa el desglose y esto se ignora (registrando el
    descuadre en el log); si no lo hay, se muestra este total con la leyenda de que la fuente
    no desagrega.
    """

    distrito = models.ForeignKey(
        "territorio.Distrito", on_delete=models.CASCADE, related_name="totales_declarados"
    )
    categoria = models.ForeignKey(
        CategoriaEvento, on_delete=models.PROTECT, related_name="totales_declarados"
    )
    total = models.PositiveIntegerField()
    rango_fecha = models.CharField(max_length=50, blank=True)
    fuente = models.CharField(max_length=100, blank=True)
    fuente_url = models.URLField(blank=True)
    dataset_upload = models.ForeignKey(
        "datasets.DatasetUpload",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="totales_declarados",
    )

    class Meta:
        verbose_name = "total declarado de emergencias"
        verbose_name_plural = "totales declarados de emergencias"
        constraints = [
            models.UniqueConstraint(
                fields=["distrito", "categoria"], name="unico_total_declarado_distrito_categoria"
            )
        ]
        indexes = [models.Index(fields=["distrito"])]

    def __str__(self) -> str:
        return f"{self.distrito} · {self.categoria} (declarado): {self.total}"
