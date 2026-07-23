from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.models import TimeStampedMixin


class TipoPeligro(TimeStampedMixin):
    """Los 9 peligros del Excel base (Sismo, Heladas, …, Movimientos en masa)."""

    slug = models.SlugField(max_length=50, unique=True)
    nombre = models.CharField(max_length=100, unique=True)
    orden = models.PositiveSmallIntegerField(default=0)
    descripcion = models.TextField(blank=True)  # [+] futuro
    icono = models.CharField(max_length=50, blank=True)  # [+] futuro
    color = models.CharField(max_length=7, blank=True)  # [+] futuro (hex)

    class Meta:
        ordering = ["orden", "nombre"]
        verbose_name = "tipo de peligro"
        verbose_name_plural = "tipos de peligro"

    def __str__(self) -> str:
        return self.nombre


class Fuente(TimeStampedMixin):
    nombre = models.CharField(max_length=200, unique=True)
    sigla = models.CharField(max_length=50, blank=True)
    url_base = models.URLField(blank=True)  # [+] futuro

    class Meta:
        ordering = ["nombre"]

    def __str__(self) -> str:
        return self.sigla or self.nombre


class ClasificacionPeligro(TimeStampedMixin):
    """Nivel de peligro (1-4) de un centro poblado para un tipo de peligro."""

    NIVELES = {1: "Bajo", 2: "Medio", 3: "Alto", 4: "Muy alto"}

    centro_poblado = models.ForeignKey(
        "territorio.CentroPoblado", on_delete=models.CASCADE, related_name="clasificaciones"
    )
    tipo_peligro = models.ForeignKey(
        TipoPeligro, on_delete=models.PROTECT, related_name="clasificaciones"
    )
    subtipo = models.CharField(max_length=100, blank=True)  # "Geodinamica interna", etc.
    nivel = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(4)]
    )
    fuente = models.ForeignKey(Fuente, null=True, blank=True, on_delete=models.SET_NULL)
    fuente_url = models.URLField(blank=True)
    anio_dato = models.PositiveSmallIntegerField(null=True, blank=True)  # [+] futuro
    vigente = models.BooleanField(default=True)  # [+] futuro (histórico de reemplazos)

    class Meta:
        verbose_name = "clasificación de peligro"
        verbose_name_plural = "clasificaciones de peligro"
        constraints = [
            models.UniqueConstraint(
                fields=["centro_poblado", "tipo_peligro", "subtipo"],
                name="unica_clasificacion_ccpp_peligro",
            )
        ]
        indexes = [models.Index(fields=["tipo_peligro", "nivel"])]

    def __str__(self) -> str:
        return f"{self.centro_poblado_id} · {self.tipo_peligro} · nivel {self.nivel}"


class CategoriaEvento(TimeStampedMixin):
    """Agrupación SIGRID de los tipos de evento del Excel de frecuencia."""

    slug = models.SlugField(max_length=50, unique=True)
    nombre = models.CharField(max_length=100)
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["orden"]
        verbose_name = "categoría de evento"
        verbose_name_plural = "categorías de evento"

    def __str__(self) -> str:
        return self.nombre


class TipoEvento(TimeStampedMixin):
    """Tipos de emergencia del Excel de frecuencia (~25: huayco, helada, …)."""

    slug = models.SlugField(max_length=60, unique=True)
    nombre = models.CharField(max_length=100, unique=True)
    categoria = models.ForeignKey(CategoriaEvento, on_delete=models.PROTECT, related_name="tipos")
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["categoria__orden", "orden"]
        verbose_name = "tipo de evento"
        verbose_name_plural = "tipos de evento"

    def __str__(self) -> str:
        return self.nombre


class FrecuenciaEmergencia(TimeStampedMixin):
    """Nº de emergencias registradas por distrito × tipo de evento
    (Excel Base_Frecuencia_Peligro_Cusco.xlsx, formato largo)."""

    distrito = models.ForeignKey(
        "territorio.Distrito", on_delete=models.CASCADE, related_name="frecuencias"
    )
    tipo_evento = models.ForeignKey(
        TipoEvento, on_delete=models.PROTECT, related_name="frecuencias"
    )
    conteo = models.PositiveIntegerField()
    rango_fecha = models.CharField(max_length=50, blank=True)  # texto fuente ("2005-2022")
    fuente = models.CharField(max_length=100, blank=True)
    fuente_url = models.URLField(blank=True)
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

    def __str__(self) -> str:
        return f"{self.distrito} · {self.tipo_evento}: {self.conteo}"
