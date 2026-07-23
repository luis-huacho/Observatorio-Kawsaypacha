from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedMixin


class DatasetUpload(TimeStampedMixin):
    """Carga de un Excel canónico que reemplaza los datos activos.

    Requisito central del TDR: PREDES actualiza la información subiendo el
    archivo, sin asistencia técnica. La importación valida, reemplaza en una
    transacción y deja un log legible de lo ocurrido.
    """

    class Tipo(models.TextChoices):
        NIVEL_PELIGRO = "nivel_peligro_ccpp", "Nivel de peligro por CCPP"
        FRECUENCIA = "frecuencia_emergencias", "Frecuencia de emergencias por distrito"
        INVERSION = "inversion_mef", "Inversión PPR 0068 (MEF)"

    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        VALIDANDO = "validando", "Validando"
        PROCESANDO = "procesando", "Procesando"
        OK = "ok", "Importado"
        ERROR = "error", "Error"

    tipo_dataset = models.CharField(max_length=30, choices=Tipo.choices)
    archivo = models.FileField(upload_to="datasets/%Y/%m/")
    estado = models.CharField(
        max_length=12, choices=Estado.choices, default=Estado.PENDIENTE, db_index=True
    )
    log = models.JSONField(default=dict, blank=True)
    filas_leidas = models.PositiveIntegerField(default=0)
    filas_importadas = models.PositiveIntegerField(default=0)
    subido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    activo = models.BooleanField(default=False, help_text="Versión vigente de este dataset")
    activado_en = models.DateTimeField(null=True, blank=True)
    checksum_sha256 = models.CharField(max_length=64, blank=True, editable=False)  # [+] futuro

    class Meta:
        ordering = ["-creado_en"]
        verbose_name = "carga de dataset"
        verbose_name_plural = "cargas de datasets"

    def __str__(self) -> str:
        return f"{self.get_tipo_dataset_display()} · {self.creado_en:%Y-%m-%d %H:%M}"
