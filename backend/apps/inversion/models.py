"""Modelos de la ventana Inversión (PP 0068).

La unidad es la **municipalidad**, no el distrito. El TDR y el spec 01 la modelaban por distrito
—herencia del prototipo—, pero la pregunta que el cliente quiere responder es «¿esta
municipalidad ejecuta lo que se le aprobó?», y quien tiene PIA, PIM y devengado es la entidad
ejecutora. Una municipalidad provincial gestiona presupuesto de toda su provincia: repartirlo
entre sus distritos para encajar en el modelo anterior habría inventado cifras distritales que
ninguna fuente respalda.

Los derivados —saldo, variación PIA-PIM, % de ejecución, % sobre el institucional, rankings— no
se guardan: se calculan en `consultas.py`, que es lo que garantiza que el API, el admin y el
Excel digan lo mismo (mismo criterio que `apps.peligros.consultas`).
"""
from django.db import models

from apps.core.models import TimeStampedMixin


class PorSlugManager(models.Manager):
    def get_by_natural_key(self, slug):
        return self.get(slug=slug)


class PorCodigoManager(models.Manager):
    def get_by_natural_key(self, codigo):
        return self.get(codigo=codigo)


class ProcesoGRD(TimeStampedMixin):
    """Proceso de la gestión del riesgo al que se imputa el gasto (ver `catalogo.py`)."""

    objects = PorSlugManager()

    # Guion bajo como en `TipoPeligro.slug`: es clave de payload del API y del frontend.
    slug = models.SlugField(max_length=40, unique=True)
    nombre = models.CharField(max_length=80, unique=True)
    orden = models.PositiveSmallIntegerField(default=0)
    color = models.CharField(max_length=7, blank=True, help_text="Hex, para los gráficos.")
    descripcion = models.TextField("descripción", blank=True)

    class Meta:
        ordering = ["orden", "nombre"]
        verbose_name = "proceso de la GRD"
        verbose_name_plural = "procesos de la GRD"

    def __str__(self) -> str:
        return self.nombre

    def natural_key(self):
        return (self.slug,)


class ClasificacionActividad(TimeStampedMixin):
    """Actividad o proyecto del PP 0068 → proceso de la GRD.

    Es el catálogo que PREDES edita. El importador **descubre** códigos nuevos y los añade con
    el proceso que propone `catalogo.py` (o sin proceso, si no lo conoce), pero nunca pisa lo
    que un editor haya guardado: `automatico` es lo que distingue una propuesta de una decisión.

    Un código sin proceso no se reparte ni se esconde: su importe va a «sin clasificar», que es
    la señal de que al catálogo le falta trabajo.
    """

    class Origen(models.TextChoices):
        ACTIVIDAD = "actividad", "Actividad del programa"
        PROYECTO = "proyecto", "Proyecto de inversión"

    objects = PorCodigoManager()

    codigo = models.CharField("código", max_length=10, unique=True, db_index=True)
    # Los proyectos de inversión no tienen nombre sino descripción: el más largo de la serie
    # 2022-2026 mide 339 caracteres y enumera los ambientes que se reparan.
    nombre = models.TextField()
    origen = models.CharField(max_length=10, choices=Origen.choices, db_index=True)
    proceso = models.ForeignKey(
        ProcesoGRD,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="actividades",
        help_text="Vacío = sin clasificar. Su importe se muestra aparte, nunca repartido.",
    )
    automatico = models.BooleanField(
        "asignado automáticamente",
        default=True,
        help_text="Lo puso la semilla o el importador. Al guardarlo desde el admin se "
        "desmarca: a partir de ahí la asignación es de PREDES y nada la sobrescribe.",
    )

    class Meta:
        ordering = ["origen", "codigo"]
        verbose_name = "clasificación de actividad"
        verbose_name_plural = "clasificación de actividades (procesos de la GRD)"
        indexes = [models.Index(fields=["proceso", "origen"])]

    def __str__(self) -> str:
        return f"{self.codigo} · {self.nombre[:60]}"

    def natural_key(self):
        return (self.codigo,)


class Ejercicio(TimeStampedMixin):
    """Un año de presupuesto, con su corte y su fuente.

    `corte` y `es_parcial` no son adorno: el ejercicio en curso llega a mitad de año, y su % de
    ejecución se calcula contra un PIM **anual**. Comparar ese número con el de un año cerrado
    sin decirlo es la forma más fácil de que la ventana mienta, así que el dato viaja con él.
    """

    class Fuente(models.TextChoices):
        MEF = "MEF", "Consulta Amigable / comparativo del MEF"
        CLIENTE = "BASE_PP0068", "Base PP 0068 entregada por PREDES"

    anio = models.PositiveSmallIntegerField("año", unique=True)
    corte = models.CharField(
        max_length=10,
        default="anual",
        help_text="'anual' para un ejercicio cerrado; 'AAAA-MM' para un corte a mitad de año.",
    )
    fuente = models.CharField(max_length=20, choices=Fuente.choices, default=Fuente.MEF)
    es_parcial = models.BooleanField(
        "es parcial",
        default=False,
        help_text="El devengado no cubre el año entero. La ventana lo advierte y no compara "
        "su % de ejecución con el de un ejercicio cerrado.",
    )
    fecha_corte = models.DateField(null=True, blank=True)
    visible = models.BooleanField(
        default=False,
        help_text="Interruptor de la ventana: sin ningún ejercicio visible, /inversion "
        "muestra su estado «información en preparación».",
    )

    class Meta:
        ordering = ["-anio"]
        verbose_name = "ejercicio presupuestal"
        verbose_name_plural = "ejercicios presupuestales"

    def __str__(self) -> str:
        return f"{self.anio}" + ("" if self.corte == "anual" else f" (corte {self.corte})")


class EntidadEjecutora(TimeStampedMixin):
    """La municipalidad —o el gobierno regional— que ejecuta el presupuesto.

    Se identifica por el código con que la nombra el MEF (SEC_EJEC para los gobiernos locales,
    que llevan el pliego vacío; PLIEGO para el resto). Ese código es estable entre ejercicios;
    los nombres de provincia y distrito no lo son, así que la geografía se refresca con cada
    importación y la llave nunca cambia.

    `distrito` es la **sede**, y puede quedar vacío: hay municipalidades en el archivo del MEF
    que no casan con el padrón (de centro poblado, o de distritos creados después). Quedan
    visibles como «sin territorio» en vez de descartarse.
    """

    class Ambito(models.TextChoices):
        DISTRITAL = "distrital", "Municipalidad distrital"
        PROVINCIAL = "provincial", "Municipalidad provincial"
        # Asociaciones de municipalidades. Son gobierno local en el MEF, pero no gobiernan un
        # distrito: meterlas en el ranking municipal compararía una entidad sin territorio con
        # las que sí lo tienen.
        MANCOMUNIDAD = "mancomunidad", "Mancomunidad municipal"
        REGIONAL = "regional", "Gobierno regional"
        NACIONAL = "nacional", "Gobierno nacional"

    objects = PorCodigoManager()

    codigo = models.CharField("código MEF", max_length=10, unique=True, db_index=True)
    nombre = models.CharField(max_length=200)
    ambito = models.CharField("ámbito", max_length=12, choices=Ambito.choices, db_index=True)
    distrito = models.ForeignKey(
        "territorio.Distrito",
        to_field="ubigeo",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="entidades_ejecutoras",
        help_text="Distrito sede. Para una municipalidad provincial es su capital, no su ámbito.",
    )
    provincia = models.ForeignKey(
        "territorio.Provincia",
        to_field="ubigeo",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="entidades_ejecutoras",
    )

    class Meta:
        ordering = ["nombre"]
        verbose_name = "entidad ejecutora"
        verbose_name_plural = "entidades ejecutoras"
        indexes = [models.Index(fields=["ambito", "provincia"])]

    def __str__(self) -> str:
        return self.nombre

    def natural_key(self):
        return (self.codigo,)

    @property
    def sin_territorio(self) -> bool:
        return self.ambito in {self.Ambito.DISTRITAL, self.Ambito.PROVINCIAL} and (
            self.distrito_id is None
        )


class PresupuestoEntidad(TimeStampedMixin):
    """Lo que una entidad tiene y gasta en un ejercicio, dentro del 0068 y en total.

    Los importes institucionales pueden ser nulos: solo existen para las entidades que ejecutan
    desde el departamento (el recorte del MEF es departamental) y para las que el Excel del
    cliente trae sin ambigüedad. Nulo significa «no se puede calcular el % sobre el
    institucional», que es distinto de cero.
    """

    ejercicio = models.ForeignKey(Ejercicio, on_delete=models.CASCADE, related_name="presupuestos")
    entidad = models.ForeignKey(
        EntidadEjecutora, on_delete=models.CASCADE, related_name="presupuestos"
    )

    pia = models.DecimalField("PIA del 0068", max_digits=16, decimal_places=2, default=0)
    pim = models.DecimalField("PIM del 0068", max_digits=16, decimal_places=2, default=0)
    devengado = models.DecimalField(
        "devengado del 0068", max_digits=16, decimal_places=2, default=0
    )

    pia_institucional = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    pim_institucional = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    devengado_institucional = models.DecimalField(
        max_digits=16, decimal_places=2, null=True, blank=True
    )

    dataset_upload = models.ForeignKey(
        "datasets.DatasetUpload",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="presupuestos",
        help_text="Carga que trajo este dato (trazabilidad).",
    )

    class Meta:
        verbose_name = "presupuesto por entidad"
        verbose_name_plural = "presupuestos por entidad"
        constraints = [
            models.UniqueConstraint(
                fields=["ejercicio", "entidad"], name="unico_presupuesto_ejercicio_entidad"
            )
        ]
        indexes = [models.Index(fields=["ejercicio", "entidad"])]

    def __str__(self) -> str:
        return f"{self.entidad} · {self.ejercicio}: PIM {self.pim}"


class PresupuestoActividad(TimeStampedMixin):
    """Grano fino: lo que una entidad tiene en una actividad o proyecto del 0068, en un ejercicio.

    Es la tabla de hechos, y con ~1,900 filas cabe de sobra. Guardar el detalle en vez del
    reparto ya hecho por proceso es lo que permite que **editar el catálogo cambie los gráficos
    al instante**: el reparto es un `GROUP BY clasificacion__proceso` sobre esto, así que no hay
    ningún agregado que recalcular ni que pueda quedarse desfasado tras una corrección.

    De aquí salen también el reparto proyectos vs actividades (`clasificacion__origen`) y el
    importe «sin clasificar» (`clasificacion__proceso IS NULL`).
    """

    ejercicio = models.ForeignKey(
        Ejercicio, on_delete=models.CASCADE, related_name="actividades"
    )
    entidad = models.ForeignKey(
        EntidadEjecutora, on_delete=models.CASCADE, related_name="actividades"
    )
    clasificacion = models.ForeignKey(
        ClasificacionActividad, on_delete=models.PROTECT, related_name="presupuestos"
    )
    pia = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    pim = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    devengado = models.DecimalField(max_digits=16, decimal_places=2, default=0)

    class Meta:
        verbose_name = "presupuesto por actividad"
        verbose_name_plural = "presupuestos por actividad"
        constraints = [
            models.UniqueConstraint(
                fields=["ejercicio", "entidad", "clasificacion"],
                name="unico_presupuesto_ejercicio_entidad_actividad",
            )
        ]
        indexes = [
            models.Index(fields=["ejercicio", "entidad"]),
            models.Index(fields=["ejercicio", "clasificacion"]),
        ]

    def __str__(self) -> str:
        return f"{self.entidad} · {self.ejercicio} · {self.clasificacion.codigo}"
