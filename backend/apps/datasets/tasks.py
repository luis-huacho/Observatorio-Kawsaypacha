from django.utils import timezone
from django_tasks import task


@task()
def procesar_dataset(upload_id: int) -> None:
    """Valida e importa una carga de dataset; reemplaza los datos activos.

    Corre en el worker (django-tasks). El resultado —conteos, advertencias
    o error— queda en el log del DatasetUpload, visible en el admin.
    """
    from apps.datasets.importers import frecuencia, nivel_peligro
    from apps.datasets.models import DatasetUpload

    importers = {
        DatasetUpload.Tipo.NIVEL_PELIGRO: nivel_peligro.importar,
        DatasetUpload.Tipo.FRECUENCIA: frecuencia.importar,
        # DatasetUpload.Tipo.INVERSION: pendiente — el cliente aún no entrega la data.
    }

    upload = DatasetUpload.objects.get(pk=upload_id)
    importer = importers.get(DatasetUpload.Tipo(upload.tipo_dataset))
    if importer is None:
        upload.estado = DatasetUpload.Estado.ERROR
        upload.log = {"error": f"Sin importador para '{upload.tipo_dataset}'"}
        upload.save(update_fields=["estado", "log"])
        return

    upload.estado = DatasetUpload.Estado.PROCESANDO
    upload.save(update_fields=["estado"])
    try:
        resultado = importer(upload)
    except Exception as exc:  # noqa: BLE001 — el error va al log del admin
        upload.estado = DatasetUpload.Estado.ERROR
        upload.log = {"error": str(exc)}
        upload.save(update_fields=["estado", "log"])
        return

    DatasetUpload.objects.filter(tipo_dataset=upload.tipo_dataset, activo=True).exclude(
        pk=upload.pk
    ).update(activo=False)
    upload.estado = DatasetUpload.Estado.OK
    upload.activo = True
    upload.activado_en = timezone.now()
    upload.filas_leidas = resultado.get("filas_leidas", 0)
    upload.filas_importadas = resultado.get("filas_importadas", 0)
    upload.log = resultado
    upload.save()

    # TODO (semana 3): encadenar regeneración de tiles CCPP y reindex Meilisearch.
