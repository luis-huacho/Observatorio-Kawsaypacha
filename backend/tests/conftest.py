"""Fixtures comunes de la suite.

Dos decisiones que explican casi todo lo demás:

**Los catálogos se siembran una vez por sesión.** Los importadores exigen que los 9 tipos de
peligro y los 21 tipos de evento existan antes de tocar el Excel (fallan con un mensaje
explícito si no), así que casi todas las pruebas los necesitan. Sembrarlos por prueba costaba
~0.4 s cada vez; con `django_db_setup` se hacen una sola vez sobre la base de prueba.

**Las importaciones se ejecutan en línea, no encoladas.** `procesar_dataset` es una tarea de
django-tasks, pero se la llama con `.func(...)` para correr en el mismo proceso: encolarla
dejaría la prueba comprobando que existe una fila en la cola, que no es lo que se quiere saber.
"""
import shutil
import tempfile

from django.core.files import File
from django.core.management import call_command

import pytest

from tests.rutas import MUESTRA_FRECUENCIA, MUESTRA_NIVEL


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    """Base de prueba con los catálogos ya sembrados.

    `--solo-catalogos` es justo lo que hace falta: tipos de peligro con su slug canónico,
    categorías y tipos de evento, grupos de trabajo con sus permisos, y los textos del sitio.
    No toca los Excel, así que no depende de `data/layers/`.
    """
    with django_db_blocker.unblock():
        call_command("seed", "--solo-catalogos", verbosity=0)


@pytest.fixture(autouse=True)
def media_temporal(settings, tmp_path):
    """MEDIA_ROOT aislado por prueba.

    Los `DatasetUpload` copian su Excel a MEDIA_ROOT y el pipeline de tiles escribe ahí: sin
    esto la suite ensucia el media de desarrollo y una prueba puede leer el archivo de otra.
    """
    settings.MEDIA_ROOT = str(tmp_path / "media")
    yield
    shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)


@pytest.fixture(autouse=True)
def registro_ia_temporal(settings, tmp_path):
    """`IA_LOGS_DIR` aislado por prueba, por la misma razón que `media_temporal`.

    `openrouter.registrar()` escribe **en cada llamada**, también con el cliente falso de la
    suite, y el directorio que hereda del contenedor lo bind-monta compose a `./logs` del host.
    Sin esto la suite ensucia el registro real: al inventariarlo, 308 de sus 318 entradas eran de
    pytest —se reconocen por `modelo pedido : modelo/por-defecto`— y las diez llamadas de verdad
    quedaban ahogadas entre ellas. Ese archivo es diario, en modo añadir y **sin rotación**, y es
    donde se mira qué se le pidió a la IA y qué contestó cuando algo sale raro en producción.

    Cinco pruebas de `test_openrouter.py` ya lo apuntaban a `tmp_path` a mano; con el fixture
    dejan de tener que acordarse, y las de los tres consumidores quedan cubiertas también.
    """
    settings.IA_LOGS_DIR = tmp_path / "ia"


def _upload(tipo: str, origen):
    from apps.datasets.models import DatasetUpload

    upload = DatasetUpload(tipo=tipo)
    with origen.open("rb") as fh:
        upload.archivo.save(origen.name, File(fh), save=True)
    return upload


@pytest.fixture
def importar():
    """Devuelve una función que importa un Excel y entrega el `DatasetUpload` ya procesado.

    Se pasa por `procesar_dataset` en vez de llamar al importador directamente porque el estado
    final, el `log` y el encadenado de tiles viven ahí — y es el mismo camino que recorre el
    botón del admin.
    """
    from apps.datasets.models import DatasetUpload
    from apps.datasets.tasks import procesar_dataset

    def _importar(tipo=DatasetUpload.Tipo.PELIGROS_CCPP, archivo=None, encadenar=False):
        origen = archivo or (
            MUESTRA_NIVEL if tipo == DatasetUpload.Tipo.PELIGROS_CCPP else MUESTRA_FRECUENCIA
        )
        upload = _upload(tipo, origen)
        procesar_dataset.func(upload.pk, encadenar=encadenar)
        upload.refresh_from_db()
        return upload

    return _importar


@pytest.fixture
def datos_muestra(importar):
    """Territorio, peligros y emergencias de las muestras, en el orden en que se importan.

    El orden importa: la frecuencia resuelve el distrito **por nombre** contra el padrón, así
    que sin importar antes los niveles de peligro no habría distritos y todas las filas se
    omitirían con aviso.
    """
    from apps.datasets.models import DatasetUpload

    return {
        "peligros": importar(DatasetUpload.Tipo.PELIGROS_CCPP),
        "frecuencia": importar(DatasetUpload.Tipo.FRECUENCIA),
    }


@pytest.fixture
def api():
    """Cliente de DRF sin autenticar: es como el público consume el API."""
    from rest_framework.test import APIClient

    return APIClient()


@pytest.fixture
def sin_throttling(monkeypatch):
    """Desactiva el throttling para las pruebas que hacen varias descargas seguidas.

    Se parchea `get_rate` en vez de sobrescribir `REST_FRAMEWORK`: DRF liga
    `SimpleRateThrottle.THROTTLE_RATES` al diccionario de `api_settings` **cuando se define la
    clase**, así que cambiar el ajuste después no llega a las clases ya importadas y la prueba
    pasaría o fallaría según el orden de los módulos. Con `rate=None` el throttle deja pasar todo.
    """
    from rest_framework.throttling import SimpleRateThrottle

    monkeypatch.setattr(SimpleRateThrottle, "get_rate", lambda self: None)
    yield


@pytest.fixture
def usuarios(db):
    """Un editor y un publicador reales, con grupo y correo.

    Con correo a propósito: un usuario sin correo hace que la tarea de aviso termine bien sin
    enviar nada, que es exactamente el fallo silencioso que estas pruebas tienen que detectar.
    """
    from django.contrib.auth import get_user_model
    from django.contrib.auth.models import Group

    from apps.core.grupos import EDITOR, PUBLICADOR

    Usuario = get_user_model()
    creados = {}
    for clave, grupo in (("editor", EDITOR), ("publicador", PUBLICADOR)):
        usuario = Usuario.objects.create_user(
            username=clave, email=f"{clave}@predes.test", password="x", is_staff=True
        )
        usuario.groups.add(Group.objects.get(name=grupo))
        creados[clave] = usuario
    return creados


@pytest.fixture
def carpeta_tiles(tmp_path):
    return tempfile.mkdtemp(dir=tmp_path)
