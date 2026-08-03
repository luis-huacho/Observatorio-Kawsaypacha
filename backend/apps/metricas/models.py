from django.db import models


class TipoEventoUso(models.TextChoices):
    PAGEVIEW = "pageview", "Visita"
    DESCARGA_PDF = "descarga_pdf", "Descarga de ayuda memoria"
    EXPORT_EXCEL = "export_excel", "Export a Excel"
    BUSQUEDA = "busqueda", "Búsqueda"
    DESCARGA_DOCUMENTO = "descarga_documento", "Descarga de documento"
    CLICK_CAPA = "click_capa", "Activación de capa del mapa"


class EventoUso(models.Model):
    """Evento de uso, sin PII (ADR-A11).

    El TDR pide métricas *internas*: no hay analítica de terceros ni cookies. `session_hash`
    es un hash diario de IP+UA truncado, que permite distinguir sesiones dentro del día sin
    poder reidentificar a nadie ni seguirle la pista entre días.
    """

    tipo = models.CharField(max_length=20, choices=TipoEventoUso.choices)
    ruta = models.CharField(max_length=250, db_index=True)
    detalle = models.CharField(
        max_length=250,
        blank=True,
        help_text="Término buscado, ubigeo del informe, slug del documento…",
    )
    fecha = models.DateTimeField(auto_now_add=True, db_index=True)
    session_hash = models.CharField(max_length=16, blank=True)

    class Meta:
        verbose_name = "evento de uso"
        verbose_name_plural = "eventos de uso"
        indexes = [models.Index(fields=["tipo", "-fecha"])]

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} · {self.ruta}"


class ResumenDiario(models.Model):
    """Agregado que sobrevive a la purga de `EventoUso` (>90 días), poblado por tarea nocturna."""

    fecha = models.DateField(db_index=True)
    tipo = models.CharField(max_length=20, choices=TipoEventoUso.choices)
    ruta = models.CharField(max_length=250)
    detalle = models.CharField(max_length=250, blank=True)
    conteo = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-fecha"]
        verbose_name = "resumen diario"
        verbose_name_plural = "resúmenes diarios"
        constraints = [
            models.UniqueConstraint(
                fields=["fecha", "tipo", "ruta", "detalle"], name="unico_resumen_diario"
            )
        ]

    def __str__(self) -> str:
        return f"{self.fecha} · {self.tipo} · {self.ruta}: {self.conteo}"
