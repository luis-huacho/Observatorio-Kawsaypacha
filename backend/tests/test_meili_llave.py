"""La llave search-only del frontend (spec 04).

Por qué merece pruebas propias: la llave **va dentro del bundle compilado del frontend**, así que si
Meilisearch deja de reconocerla no falla nada de forma visible. El buscador cae al fallback de DRF
—con su aviso—, pero las facetas de `/medidas` se quedan sin conteos y el autocompletado de lugares
del visor sin resultados, las dos en silencio. Pasó de verdad: la llave se creaba con uid aleatorio,
un `down -v` la cambió y el bundle se quedó con una llave que ya no existía.

Lo que se fija aquí es que la llave se identifique por su **uid fijo**, que es lo que la hace
determinista (`key` es el SHA-256 del uid con la master key), y que los cambios de permisos se
apliquen recreándola con el mismo uid.

No hace falta un Meilisearch real: lo que se comprueba es con qué se le llama.
"""
import pytest

from apps.core.services import meili


class LlaveFalsa:
    def __init__(self, uid, actions, indexes, key="llave-derivada-del-uid", name=None):
        self.uid = uid
        self.name = name if name is not None else meili.NOMBRE_LLAVE_BUSQUEDA
        self.actions = actions
        self.indexes = indexes
        self.key = key


class ClienteFalso:
    """Lo mínimo de la API de llaves de Meilisearch, registrando lo que se le pide."""

    def __init__(self, llaves=()):
        self.llaves = {llave.uid: llave for llave in llaves}
        self.creadas: list[dict] = []
        self.borradas: list[str] = []

    def get_key(self, uid):
        if uid not in self.llaves:
            raise RuntimeError(f"api_key_not_found: {uid}")
        return self.llaves[uid]

    def get_keys(self):
        class Resultado:
            def __init__(self, results):
                self.results = results

        return Resultado(list(self.llaves.values()))

    def create_key(self, opciones):
        self.creadas.append(opciones)
        llave = LlaveFalsa(
            uid=opciones["uid"],
            actions=opciones["actions"],
            indexes=opciones["indexes"],
            key=f"derivada-de-{opciones['uid']}",
        )
        self.llaves[llave.uid] = llave
        return llave

    def delete_key(self, uid):
        self.borradas.append(uid)
        self.llaves.pop(uid, None)
        return 204


@pytest.fixture
def cliente(monkeypatch):
    """Devuelve una fábrica que instala el cliente falso en el módulo."""

    def instalar(llaves=()):
        falso = ClienteFalso(llaves)
        monkeypatch.setattr(meili, "cliente", lambda: falso)
        return falso

    return instalar


def _llave_correcta():
    return LlaveFalsa(
        uid=meili.UID_LLAVE_BUSQUEDA,
        actions=["search"],
        indexes=list(meili.INDICES_PUBLICOS),
        key="la-de-siempre",
    )


def test_la_llave_se_crea_con_el_uid_fijo(cliente):
    """Es lo único que la hace reproducible: sin uid, Meilisearch genera uno al azar."""
    falso = cliente()

    llave = meili.llave_busqueda()

    assert len(falso.creadas) == 1
    assert falso.creadas[0]["uid"] == meili.UID_LLAVE_BUSQUEDA
    assert falso.creadas[0]["actions"] == ["search"]
    assert set(falso.creadas[0]["indexes"]) == set(meili.INDICES_PUBLICOS)
    assert llave == f"derivada-de-{meili.UID_LLAVE_BUSQUEDA}"


def test_una_llave_ya_correcta_se_reutiliza_sin_tocar_nada(cliente):
    """`meili_setup` corre en cada arranque: si recreara la llave, cada despliegue la rotaría."""
    falso = cliente([_llave_correcta()])

    assert meili.llave_busqueda() == "la-de-siempre"
    assert falso.creadas == []
    assert falso.borradas == []


def test_si_cambian_los_indices_publicos_se_recrea_con_el_mismo_uid(cliente):
    """Añadir un índice público dejaría a la llave sin permiso sobre él: 403 solo en ese índice.

    `PATCH /keys/{uid}` no admite cambiar `indexes`, así que se borra y se crea de nuevo. Con el
    mismo uid la llave sale idéntica, de modo que el frontend ya desplegado sigue funcionando.
    """
    desfasada = LlaveFalsa(
        uid=meili.UID_LLAVE_BUSQUEDA,
        actions=["search"],
        indexes=["medidas"],
        key="la-vieja",
    )
    falso = cliente([desfasada])

    llave = meili.llave_busqueda()

    assert falso.borradas == [meili.UID_LLAVE_BUSQUEDA]
    assert len(falso.creadas) == 1
    assert falso.creadas[0]["uid"] == meili.UID_LLAVE_BUSQUEDA
    assert set(falso.creadas[0]["indexes"]) == set(meili.INDICES_PUBLICOS)
    assert llave == f"derivada-de-{meili.UID_LLAVE_BUSQUEDA}"


def test_una_llave_heredada_con_uid_aleatorio_se_retira(cliente):
    """Las creadas antes de fijar el uid. Dejarlas vivas mantendría dos llaves válidas."""
    heredada = LlaveFalsa(
        uid="6062abda-a5aa-4414-ac91-ecd7944c0f8d",
        actions=["search"],
        indexes=list(meili.INDICES_PUBLICOS),
        key="la-aleatoria",
    )
    falso = cliente([heredada])

    llave = meili.llave_busqueda()

    assert heredada.uid in falso.borradas
    assert llave == f"derivada-de-{meili.UID_LLAVE_BUSQUEDA}"


def test_no_se_toca_ninguna_otra_llave(cliente):
    """La master key y cualquier llave de administración no son asunto de esta función."""
    ajena = LlaveFalsa(
        uid="e9c9a1a4-1111-4444-8888-aaaaaaaaaaaa",
        actions=["*"],
        indexes=["*"],
        key="la-de-admin",
        name="Default Admin API Key",
    )
    falso = cliente([ajena])

    meili.llave_busqueda()

    assert ajena.uid not in falso.borradas
