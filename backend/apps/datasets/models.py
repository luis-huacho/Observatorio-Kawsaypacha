from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedMixin


class DatasetUpload(TimeStampedMixin):
    """Carga de un Excel canónico que reemplaza los datos activos (ADR-A12).

    Requisito central del TDR: PREDES actualiza la información subiendo el archivo, sin
    asistencia técnica. La importación valida, reemplaza en una transacción y deja un log
    legible — el log es lo que el cliente lee para saber qué corregir en su Excel, así que
    va en español y cita hoja y fila.
    """

    class Tipo(models.TextChoices):
        PELIGROS_CCPP = "peligros_ccpp", "Nivel de peligro por centro poblado"
        FRECUENCIA = "frecuencia_emergencias", "Frecuencia de emergencias por distrito"
        # Tres formas, una sola carga: el Excel del cliente (un ejercicio con su corte) y las
        # dos series consolidadas del MEF. El importador las distingue por su cabecera.
        INVERSION = "inversion_mef", "Presupuesto PP 0068 por municipalidad"

    class Estado(models.TextChoices):
        SUBIDO = "subido", "Subido"
        VALIDANDO = "validando", "Validando"
        PROCESANDO = "procesando", "Procesando"
        ACTIVO = "activo", "Activo"
        REEMPLAZADO = "reemplazado", "Reemplazado"
        ERROR = "error", "Error"

    tipo = models.CharField("tipo de dataset", max_length=30, choices=Tipo.choices)
    archivo = models.FileField(upload_to="datasets/%Y/%m/")
    estado = models.CharField(
        max_length=12, choices=Estado.choices, default=Estado.SUBIDO, db_index=True
    )
    log = models.JSONField(default=dict, blank=True)
    filas_leidas = models.PositiveIntegerField(default=0)
    filas_importadas = models.PositiveIntegerField(default=0)
    subido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    activado_en = models.DateTimeField(null=True, blank=True)
    reemplaza_a = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reemplazado_por",
        help_text="Carga anterior del mismo tipo, que este archivo deja obsoleta.",
    )
    checksum_sha256 = models.CharField(max_length=64, blank=True, editable=False)  # [+] futuro
    parametros = models.JSONField(default=dict, blank=True)  # [+] futuro

    class Meta:
        ordering = ["-creado_en"]
        verbose_name = "carga de dataset"
        verbose_name_plural = "cargas de datasets"
        indexes = [models.Index(fields=["tipo", "estado"])]

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} · {self.creado_en:%Y-%m-%d %H:%M}"

    @property
    def advertencias(self) -> list[str]:
        return self.log.get("advertencias", []) if isinstance(self.log, dict) else []
