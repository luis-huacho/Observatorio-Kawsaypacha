from django.db import models

from apps.core.models import TimeStampedMixin


class PorUbigeoManager(models.Manager):
    """Llave natural por ubigeo: las fixtures y los importadores hablan ubigeo, no pks."""

    def get_by_natural_key(self, ubigeo):
        return self.get(ubigeo=ubigeo)


class Provincia(TimeStampedMixin):
    objects = PorUbigeoManager()

    ubigeo = models.CharField(max_length=4, unique=True)
    nombre = models.CharField(max_length=100)
    poblacion_censo = models.PositiveIntegerField(null=True, blank=True)  # [+] futuro
    superficie_km2 = models.DecimalField(  # [+] futuro
        max_digits=10, decimal_places=2, null=True, blank=True
    )

    class Meta:
        ordering = ["nombre"]
        verbose_name = "provincia"

    def __str__(self) -> str:
        return self.nombre

    def natural_key(self):
        return (self.ubigeo,)


class Distrito(TimeStampedMixin):
    objects = PorUbigeoManager()

    ubigeo = models.CharField(max_length=6, unique=True, db_index=True)
    provincia = models.ForeignKey(Provincia, on_delete=models.PROTECT, related_name="distritos")
    nombre = models.CharField(max_length=100)
    # Para resolver datasets que llegan sin ubigeo (p.ej. Excel de frecuencia):
    nombre_normalizado = models.CharField(max_length=100, db_index=True, editable=False)
    poblacion_censo = models.PositiveIntegerField(null=True, blank=True)  # [+] futuro
    superficie_km2 = models.DecimalField(  # [+] futuro
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    contacto_gdr = models.CharField(max_length=200, blank=True)  # [+] futuro (ayudas memoria)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "distrito"

    def __str__(self) -> str:
        return f"{self.nombre} ({self.provincia.nombre})"

    def natural_key(self):
        return (self.ubigeo,)

    def save(self, *args, **kwargs):
        from apps.territorio.utils import normalizar_nombre

        self.nombre_normalizado = normalizar_nombre(self.nombre)
        super().save(*args, **kwargs)


class PorCodigoManager(models.Manager):
    def get_by_natural_key(self, codigo):
        return self.get(codigo=codigo)


class CentroPoblado(TimeStampedMixin):
    objects = PorCodigoManager()

    codigo = models.CharField("código INEI", max_length=10, unique=True, db_index=True)
    distrito = models.ForeignKey(
        Distrito, to_field="ubigeo", on_delete=models.PROTECT, related_name="centros_poblados"
    )
    nombre = models.CharField(max_length=150)
    categoria = models.CharField(max_length=50, blank=True)
    lat = models.FloatField(null=True, blank=True)
    lon = models.FloatField(null=True, blank=True)
    altitud = models.IntegerField(null=True, blank=True)
    poblacion = models.PositiveIntegerField(null=True, blank=True)
    vigente = models.BooleanField(default=True)  # [+] futuro (depuraciones INEI)
    fuente_padron = models.CharField(max_length=100, blank=True)  # [+] futuro
    anio_padron = models.PositiveSmallIntegerField(null=True, blank=True)  # [+] futuro

    class Meta:
        ordering = ["codigo"]
        verbose_name = "centro poblado"
        indexes = [models.Index(fields=["distrito", "nombre"])]

    def __str__(self) -> str:
        return f"{self.nombre} ({self.codigo})"

    def natural_key(self):
        return (self.codigo,)
