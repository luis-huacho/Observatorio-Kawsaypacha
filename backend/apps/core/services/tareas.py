"""Estado de la cola de django-tasks, para vigilar que el worker sigue avanzando.

El worker procesa lo que no puede esperar a una petición HTTP: importaciones de Excel, teselado,
resúmenes con Gemini, correos del flujo editorial, agregación de métricas y la sincronización del
buscador. **Si se atasca, no se nota**: el sitio sigue sirviendo, el admin sigue guardando, y lo
que falla es lo que nadie está mirando en ese momento —un Excel que no entra, un correo que no
sale, un índice que se queda atrás—.

Se mira desde fuera, contando filas de la tabla de resultados, y no preguntándole al worker: un
proceso colgado contesta que está bien.

Devuelve un dict y **no lanza nunca**, igual que `meili.estado_indices()`: la indisponibilidad es
un estado que hay que poder contar, no una excepción que corte el informe.
"""
from datetime import timedelta

from django.apps import apps
from django.utils import timezone

# Cuánto puede llevar una tarea esperando antes de considerar que la cola no avanza. El teselado
# de las capas nacionales es lo más lento del sistema y se mide en minutos, no en horas.
ESPERA_MAXIMA = timedelta(minutes=15)
# Y cuánto puede llevar una tarea EN CURSO antes de sospechar que el worker se colgó a mitad.
EJECUCION_MAXIMA = timedelta(minutes=30)


def _modelo():
    """El `app_label` es `django_tasks_database`, no el nombre del paquete (`django_tasks_db`)."""
    return apps.get_model("django_tasks_database", "DBTaskResult")


def estado_cola(ahora=None) -> dict:
    """Resumen de la cola: conteos por estado y las dos señales de atasco."""
    ahora = ahora or timezone.now()
    vacio = {
        "disponible": False,
        "conteos": {},
        "esperando": None,
        "atascada": False,
        "en_curso_colgada": None,
        "fallidas": 0,
        "motivos": [],
    }

    try:
        modelo = _modelo()
        conteos = {
            estado: modelo.objects.filter(status=estado).count()
            for estado in ("READY", "RUNNING", "FAILED", "SUCCESSFUL")
        }

        # La tarea más antigua que YA debería haberse ejecutado. Se usa el `.ready()` de la propia
        # librería en vez de reescribir el filtro, y no es un detalle: django-tasks-db **no usa
        # NULL** para «sin retraso», usa el centinela `9999-01-01` (`get_date_max()`). Un filtro
        # propio con `run_after__isnull=True` no casa con ninguna fila y deja el vigilante ciego
        # sin dar ningún error. Reutilizando `.ready()`, la definición de «lista para ejecutar» es
        # exactamente la que aplica el worker.
        mas_antigua = (
            modelo.objects.ready()
            .order_by("enqueued_at")
            .values_list("enqueued_at", flat=True)
            .first()
        )
        esperando = (ahora - mas_antigua) if mas_antigua else None

        # Una tarea RUNNING que empezó hace mucho es la firma de un worker colgado a mitad.
        arrancada = (
            modelo.objects.filter(status="RUNNING")
            .order_by("started_at")
            .values_list("started_at", flat=True)
            .first()
        )
        en_curso = (ahora - arrancada) if arrancada else None
    except Exception:  # noqa: BLE001 — la base caída es un estado, no un error de este informe
        return vacio

    motivos = []
    if esperando and esperando > ESPERA_MAXIMA:
        motivos.append(
            f"hay tareas esperando desde hace {_humano(esperando)} "
            f"(el margen son {_humano(ESPERA_MAXIMA)})"
        )
    if en_curso and en_curso > EJECUCION_MAXIMA:
        motivos.append(
            f"hay una tarea en curso desde hace {_humano(en_curso)} "
            f"(el margen son {_humano(EJECUCION_MAXIMA)})"
        )

    return {
        "disponible": True,
        "conteos": conteos,
        "esperando": esperando,
        "en_curso_colgada": en_curso,
        "fallidas": conteos.get("FAILED", 0),
        "atascada": bool(motivos),
        "motivos": motivos,
    }


def _humano(delta: timedelta) -> str:
    minutos = int(delta.total_seconds() // 60)
    if minutos < 60:
        return f"{minutos} min"
    horas, resto = divmod(minutos, 60)
    return f"{horas} h {resto} min" if resto else f"{horas} h"
