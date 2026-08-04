"""Estado del buscador: ¿está arriba, y está al día? (spec 04)

Lo que protege: que exista una respuesta a «¿está indexado al 100%?». **El desfase del índice no da
ningún síntoma**: el contenido se ve en el sitio y simplemente no aparece al buscarlo. Sin esta
comprobación nadie se enteraría hasta que alguien lo notara.

El cliente de Meilisearch es falso, y el desfase se simula por el lado de Meilisearch —documentos
que la base no tiene, o que le faltan—: lo que se fija aquí es la interpretación de los conteos, no
que Meilisearch sepa contar.
"""
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError

import pytest

from apps.core.services import meili

pytestmark = pytest.mark.django_db


class IndiceFalso:
    def __init__(self, total):
        self.total = total

    def get_documents(self, parametros=None):
        if self.total is None:
            raise RuntimeError("MeilisearchApiError: index_not_found")

        class Resultado:
            total = self.total

        return Resultado()


class ClienteFalso:
    """`index().get_documents` y `get_tasks`, que es todo lo que `estado_indices` consulta.

    **No expone `get_all_stats` a propósito.** Si alguien vuelve a contar documentos con
    `numberOfDocuments` de `/stats`, estas pruebas fallan con `AttributeError`, y eso es lo que se
    quiere: ese conteo está cacheado y sigue devolviendo el valor anterior después de vaciar un
    índice, justo en el caso que hay que detectar.
    """

    def __init__(self, documentos_por_indice: dict, pendientes: int = 0, cae: bool = False):
        self.documentos = documentos_por_indice
        self.pendientes = pendientes
        self.cae = cae

    def index(self, slug):
        return IndiceFalso(self.documentos.get(slug))

    def get_tasks(self, parametros=None):
        if self.cae:
            raise RuntimeError("MeilisearchCommunicationError: no responde")

        class Resultado:
            total = self.pendientes

        return Resultado()


@pytest.fixture
def meilisearch(monkeypatch):
    """Instala un Meilisearch falso con los documentos que se le digan."""

    def instalar(documentos=None, pendientes=0, cae=False):
        falso = ClienteFalso(documentos or {}, pendientes, cae)
        monkeypatch.setattr(meili, "cliente", lambda timeout=None: falso)
        return falso

    return instalar


def _cuadrando() -> dict:
    """Lo que Meilisearch tendría que tener para estar al día con la base de las pruebas.

    El seed de las pruebas trae catálogos, no contenido, así que todos los índices van a cero.
    """
    return {slug: 0 for slug in meili.INDICES}


def test_con_los_conteos_cuadrados_esta_al_dia(meilisearch):
    meilisearch(_cuadrando())

    estado = meili.estado_indices()

    assert estado["disponible"] is True
    assert estado["al_dia"] is True
    assert {i["slug"] for i in estado["indices"]} == set(meili.INDICES)


def test_un_indice_descuadrado_se_senala_sin_arrastrar_a_los_demas(meilisearch):
    """El caso real: se publicó algo y la sincronización no llegó al índice (o al revés)."""
    documentos = _cuadrando() | {"medidas": 3}
    meilisearch(documentos)

    estado = meili.estado_indices()

    assert estado["al_dia"] is False
    medidas = next(i for i in estado["indices"] if i["slug"] == "medidas")
    assert (medidas["en_meili"], medidas["en_bd"], medidas["al_dia"]) == (3, 0, False)
    assert all(i["al_dia"] for i in estado["indices"] if i["slug"] != "medidas")


def test_el_conteo_no_sale_de_las_estadisticas_cacheadas(meilisearch):
    """El hallazgo que costó descubrir vaciando un índice de verdad.

    `numberOfDocuments` de `/stats` **está cacheado**: en Meilisearch 1.15, tras vaciar un índice
    sigue devolviendo el conteo anterior mientras la búsqueda ya no encuentra nada. Una comprobación
    basada en él daría el índice por bueno exactamente en el caso que tiene que detectar. El cliente
    falso no tiene `get_all_stats`, así que volver a usarlo rompe estas pruebas.
    """
    falso = meilisearch(_cuadrando())

    assert not hasattr(falso, "get_all_stats")
    assert meili.estado_indices()["disponible"] is True


def test_un_indice_que_no_existe_se_distingue_de_uno_vacio(meilisearch):
    """`None` (no existe) no es lo mismo que 0: significa que `meili_setup` no ha corrido aquí."""
    documentos = _cuadrando()
    del documentos["medidas"]
    meilisearch(documentos)

    estado = meili.estado_indices()
    medidas = next(i for i in estado["indices"] if i["slug"] == "medidas")

    assert medidas["en_meili"] is None


def test_las_tareas_en_cola_se_reportan(meilisearch):
    """Tras un rebuild los conteos van con retraso: eso es «indexando», no «desfasado»."""
    meilisearch(_cuadrando(), pendientes=3)

    assert meili.estado_indices()["pendientes"] == 3


def test_con_meilisearch_caido_no_lanza(meilisearch):
    """Alimenta la portada del admin: un buscador caído no puede tumbarla."""
    meilisearch(cae=True)

    estado = meili.estado_indices()

    assert estado == {"disponible": False, "pendientes": 0, "al_dia": False, "indices": []}


def test_las_consultas_de_estado_llevan_timeout():
    """Sin timeout, un Meilisearch que acepta la conexión y no contesta cuelga a quien pregunta:
    `/api/buscar/estado/` en cada búsqueda, y la portada del admin."""
    assert meili.TIMEOUT_ESTADO and meili.TIMEOUT_ESTADO <= 5


# --- El comando -------------------------------------------------------------


def test_el_comando_pasa_cuando_todo_esta_al_dia(meilisearch):
    meilisearch(_cuadrando())
    salida = StringIO()

    call_command("meili_estado", stdout=salida)

    assert "al día" in salida.getvalue()


def test_el_comando_falla_si_hay_desfase(meilisearch):
    """Termina con código ≠ 0 a propósito: es lo que lo hace usable en un cron con `|| mail`."""
    meilisearch(_cuadrando() | {"medidas": 3})

    with pytest.raises(CommandError) as fallo:
        call_command("meili_estado", stdout=StringIO())

    assert "medidas" in str(fallo.value)
    # Y dice cómo arreglarlo, que es la mitad del valor de un aviso automático.
    assert "meili_rebuild" in str(fallo.value)


def test_el_comando_falla_si_el_servicio_no_responde(meilisearch):
    meilisearch(cae=True)

    with pytest.raises(CommandError) as fallo:
        call_command("meili_estado", stdout=StringIO())

    assert "no responde" in str(fallo.value)
