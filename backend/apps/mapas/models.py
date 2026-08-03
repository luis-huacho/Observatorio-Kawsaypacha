from django.db import models

from apps.core.models import TimeStampedMixin


class CapaCartografica(TimeStampedMixin):
    """Capa de contexto del visor: GeoJSON subido por admin → PMTiles servidos por nginx.

    La capa de centros poblados NO es una CapaCartografica: se sirve como GeoJSON agrupado
    desde `/api/ccpp/geojson/` porque MapLibre solo agrupa fuentes `geojson` (ADR-A13).
    """

    class Geometria(models.TextChoices):
        PUNTO = "punto", "Puntos"
        LINEA = "linea", "Líneas"
        POLIGONO = "poligono", "Polígonos"

    class EstadoTiles(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        GENERANDO = "generando", "Generando"
        OK = "ok", "Listo"
        ERROR = "error", "Error"

    slug = models.SlugField(
        max_length=60,
        unique=True,
        help_text="Nombre de la capa dentro del tile y del archivo .pmtiles (rios, lagunas…).",
    )
    nombre = models.CharField(max_length=120)
    descripcion = models.TextField(blank=True)
    archivo_geojson = models.FileField(upload_to="capas/%Y/%m/")
    tipo_geometria = models.CharField(
        max_length=10, choices=Geometria.choices, blank=True, editable=False
    )
    estilo = models.JSONField(
        default=dict,
        blank=True,
        help_text="Paint de MapLibre (color, grosor, opacidad). Permite recolorear la capa "
        "sin tocar código, que es el requisito de reemplazo de capas del TDR.",
    )
    min_zoom = models.PositiveSmallIntegerField(default=0)
    max_zoom = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="Vacío = que tippecanoe lo deduzca (-zg)."
    )
    filtro_atributo = models.CharField(
        max_length=120,
        blank=True,
        help_text="Recorte por atributo, p. ej. DN99=CUSCO o DPTO ILIKE cusco. Vacío = "
        "se recorta espacialmente con el polígono regional.",
    )
    visible_por_defecto = models.BooleanField(default=False)
    orden = models.PositiveSmallIntegerField(default=0)
    atribucion = models.CharField(max_length=250, blank=True)
    fuente = models.CharField(max_length=200, blank=True)
    simplificacion = models.FloatField(
        null=True, blank=True, help_text="Tolerancia de -simplify de ogr2ogr, en grados."
    )

    estado_tiles = models.CharField(
        max_length=10, choices=EstadoTiles.choices, default=EstadoTiles.PENDIENTE, editable=False
    )
    pmtiles = models.CharField(max_length=200, blank=True, editable=False)
    log_error = models.TextField(blank=True, editable=False)
    crs_origen = models.CharField(
        max_length=40,
        blank=True,
        editable=False,
        help_text="CRS detectado en el archivo. Se registra porque hay fuentes proyectadas "
        "(glaciares viene en EPSG:32718) y sin reproyectar los tiles salen vacíos.",
    )
    features_generados = models.PositiveIntegerField(default=0, editable=False)

    class Meta:
        ordering = ["orden", "nombre"]
        verbose_name = "capa cartográfica"
        verbose_name_plural = "capas cartográficas"

    def __str__(self) -> str:
        return self.nombre
