"""`manage.py cola_estado`: ¿sigue avanzando el worker? (spec 07)

Lo que protege: que exista una respuesta a «¿está la cola atascada?». Un worker colgado **no da
ningún síntoma** —el sitio sirve, el admin guarda— y lo que se rompe es lo que nadie está mirando:
un Excel que no entra, un correo que no sale, el índice de búsqueda que se queda atrás. Es el
mismo tipo de fallo mudo que `meili_estado` cubre para la búsqueda, y se comprueba igual: por el
código de salida, para poder colgarlo de un cron.

La cola se llena escribiendo filas directamente en `DBTaskResult`, y no encolando tareas de
verdad, porque lo que se fija aquí es **la interpretación de los tiempos**, no que django-tasks
sepa encolar.
"""
from datetime import timedelta
from io import StringIO

from django.apps import apps
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

import pytest

from apps.core.services import tareas

pytestmark = pytest.mark.django_db


def crear(estado, *, encolada_hace=None, arrancada_hace=None, run_after=None):
    """Crea una fila de la cola con la antigüedad que haga falta.

    `run_after` por defecto es el centinela `get_date_max()` —9999-01-01—, que es como
    django-tasks-db escribe «sin retraso»: NO usa NULL. Pasar `None` aquí daría una fila que el
    `.ready()` de la librería nunca devuelve.
    """
    from django_tasks_db.models import get_date_max

    ahora = timezone.now()
    modelo = apps.get_model("django_tasks_database", "DBTaskResult")
    run_after = get_date_max() if run_after is None else run_after
    fila = modelo.objects.create(
        status=estado,
        args_kwargs={"args": [], "kwargs": {}},
        task_path="apps.core.tasks.sincronizar_meili",
        backend_name="default",
        queue_name="default",
        run_after=run_after,
    )
    # `enqueued_at` es auto_now_add: hay que pisarlo con un UPDATE para simular antigüedad.
    campos = {}
    if encolada_hace is not None:
        campos["enqueued_at"] = ahora - encolada_hace
    if arrancada_hace is not None:
        campos["started_at"] = ahora - arrancada_hace
    if campos:
        modelo.objects.filter(pk=fila.pk).update(**campos)
    return fila


def test_cola_vacia_sale_bien():
    salida = StringIO()
    call_command("cola_estado", stdout=salida)
    assert "avanza con normalidad" in salida.getvalue()


def test_una_tarea_recien_encolada_no_es_un_atasco():
    """Que haya cola no es un problema; que no se mueva, sí."""
    crear("READY", encolada_hace=timedelta(minutes=1))

    salida = StringIO()
    call_command("cola_estado", stdout=salida)

    assert "avanza con normalidad" in salida.getvalue()


def test_tarea_programada_a_futuro_no_cuenta_como_atasco():
    """`run_after` en el futuro significa «todavía no toca», no «nadie la coge»."""
    crear(
        "READY",
        encolada_hace=timedelta(hours=3),
        run_after=timezone.now() + timedelta(days=1),
    )

    salida = StringIO()
    call_command("cola_estado", stdout=salida)

    assert "avanza con normalidad" in salida.getvalue()


def test_espera_larga_falla_y_dice_que_hacer():
    crear("READY", encolada_hace=tareas.ESPERA_MAXIMA + timedelta(minutes=5))

    with pytest.raises(CommandError) as fallo:
        call_command("cola_estado", stdout=StringIO())

    mensaje = str(fallo.value)
    assert "no avanza" in mensaje
    # La regla del proyecto: el error dice cómo arreglarlo, y avisa del riesgo de reiniciar.
    assert "logs worker" in mensaje
    assert "importación interrumpida" in mensaje


def test_tarea_en_curso_eterna_es_un_worker_colgado():
    """La firma de un worker colgado a mitad: RUNNING que empezó hace mucho y no termina."""
    crear("RUNNING", arrancada_hace=tareas.EJECUCION_MAXIMA + timedelta(minutes=5))

    with pytest.raises(CommandError) as fallo:
        call_command("cola_estado", stdout=StringIO())

    assert "en curso desde hace" in str(fallo.value)


def test_las_fallidas_se_avisan_pero_no_atascan():
    """Una tarea fallida es un fallo silencioso; no bloquea la cola, pero hay que contarlo."""
    crear("FAILED", encolada_hace=timedelta(hours=2))

    salida = StringIO()
    call_command("cola_estado", stdout=salida)

    texto = salida.getvalue()
    assert "fallida" in texto
    assert "avanza con normalidad" in texto
