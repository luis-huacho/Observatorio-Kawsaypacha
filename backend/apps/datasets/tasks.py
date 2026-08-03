from django.utils import timezone
from django_tasks import task


@task()
def procesar_dataset(upload_id: int, encadenar: bool = True) -> None:
    """Valida e importa una carga de dataset; reemplaza los datos activos (ADR-A12).

    Corre en el worker (django-tasks). El resultado —conteos, advertencias o error— queda en el
    log del DatasetUpload, que es lo que PREDES lee en el admin para saber qué corregir.
    """
    from apps.datasets.importers import frecuencia, nivel_peligro
    from apps.datasets.models import DatasetUpload

    importadores = {
        DatasetUpload.Tipo.PELIGROS_CCPP: nivel_peligro.importar,
        DatasetUpload.Tipo.FRECUENCIA: frecuencia.importar,
        # INVERSION: sin importador — la ventana está diferida (ADR-D3) y el formato del
        # Excel no está definido. Modelar contra un formato imaginado se tira a la basura.
    }

    upload = DatasetUpload.objects.get(pk=upload_id)
    importador = importadores.get(DatasetUpload.Tipo(upload.tipo))
    if importador is None:
        upload.estado = DatasetUpload.Estado.ERROR
        upload.log = {
            "error": f"Todavía no hay importador para «{upload.get_tipo_display()}».",
            "advertencias": [],
        }
        upload.save(update_fields=["estado", "log"])
        return

    upload.estado = DatasetUpload.Estado.PROCESANDO
    upload.save(update_fields=["estado"])
    try:
        resultado = importador(upload)
    except Exception as exc:  # noqa: BLE001 — el error va al log que lee el editor
        upload.estado = DatasetUpload.Estado.ERROR
        upload.log = {"error": str(exc), "advertencias": []}
        upload.save(update_fields=["estado", "log"])
        return

    anteriores = DatasetUpload.objects.filter(
        tipo=upload.tipo, estado=DatasetUpload.Estado.ACTIVO
    ).exclude(pk=upload.pk)
    ultimo_activo = anteriores.order_by("-activado_en").first()
    anteriores.update(estado=DatasetUpload.Estado.REEMPLAZADO)

    upload.estado = DatasetUpload.Estado.ACTIVO
    upload.activado_en = timezone.now()
    upload.reemplaza_a = ultimo_activo
    upload.filas_leidas = resultado.get("filas_leidas", 0)
    upload.filas_importadas = resultado.get("filas_importadas", 0)
    upload.log = resultado
    upload.save()

    if encadenar:
        encadenar_post_import(upload)


def encadenar_post_import(upload) -> None:
    """Rehace lo que depende de los datos importados: tiles y búsqueda.

    Con try/except propio: si falla la regeneración de tiles, la importación ya está hecha y
    es correcta, y marcarla como error sería mentir sobre lo que pasó. El aviso va al log.
    """
    from apps.datasets.models import DatasetUpload

    if upload.tipo != DatasetUpload.Tipo.PELIGROS_CCPP:
        return

    avisos: list[str] = []
    try:
        from apps.mapas.tasks import generar_tiles_ccpp

        generar_tiles_ccpp.enqueue()
    except Exception as exc:  # noqa: BLE001
        avisos.append(f"No se pudo encolar la regeneración de tiles: {exc}")
    try:
        from apps.core.tasks import reindexar_meili

        reindexar_meili.enqueue(indice="ccpp")
    except Exception as exc:  # noqa: BLE001
        avisos.append(f"No se pudo encolar la reindexación de búsqueda: {exc}")

    if avisos:
        log = dict(upload.log or {})
        log.setdefault("advertencias", []).extend(avisos)
        upload.log = log
        upload.save(update_fields=["log"])
