"""`/api/salud/`: la sonda del healthcheck (spec 02, spec 07).

Lo que protege es una garantía negativa, y es la que importa: **la sonda no puede fallar porque
falle una dependencia**. Si `/api/salud/` devolviera error con la base o el buscador caídos, el
healthcheck marcaría el contenedor «unhealthy», el vigilante de `deploy/vigilar-contenedores.sh`
lo reiniciaría, y tendríamos un bucle de reinicios que no arregla nada y borra el rastro del
fallo real. Reiniciar el backend no levanta PostgreSQL.

La otra garantía es la exención de throttling: con `interval: 10s` son 360 peticiones/hora contra
un techo anónimo de 1000/hora, así que una sonda sujeta al límite acabaría provocando 429 —y con
ellos, reinicios— sin que pasara nada en el sitio.
"""
import pytest

from apps.core.services import meili

pytestmark = pytest.mark.django_db

URL = "/api/salud/"


def test_responde_ok_con_todo_arriba(api, monkeypatch):
    monkeypatch.setattr(meili, "disponible", lambda: True)

    respuesta = api.get(URL)

    assert respuesta.status_code == 200
    assert respuesta.json() == {"servicio": "ok", "base": "ok", "buscador": "ok"}


def test_sigue_dando_200_con_el_buscador_caido(api, monkeypatch):
    """Un Meilisearch caído degrada la búsqueda, no tumba el backend: no se reinicia por eso."""
    monkeypatch.setattr(meili, "disponible", lambda: False)

    respuesta = api.get(URL)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["servicio"] == "ok"
    assert cuerpo["buscador"] == "sin respuesta"


def test_sigue_dando_200_con_la_base_caida(api, monkeypatch):
    """La comprobación más importante del archivo.

    Se simula el fallo en `_estado_base`, que es donde vive el `SELECT 1`: apagar de verdad la
    conexión desde una prueba con `django_db` no es reproducible. Lo que se fija es el contrato:
    la base sin responder **no** cambia el código de estado.
    """
    from apps.api.views import salud

    monkeypatch.setattr(salud, "_estado_base", lambda: "sin respuesta")
    monkeypatch.setattr(meili, "disponible", lambda: True)

    respuesta = api.get(URL)

    assert respuesta.status_code == 200
    assert respuesta.json()["base"] == "sin respuesta"


def test_no_gasta_cuota_de_throttling(api, monkeypatch):
    """Sin exención, 360 peticiones/hora de la sonda comerían la cuota anónima y darían 429.

    Se piden más veces de las que permitiría el `descarga` (30/hora), el más estrecho del
    proyecto, sin fixture `sin_throttling`: si alguien le quitara `throttle_classes = []` a la
    vista, esta prueba lo vería.
    """
    monkeypatch.setattr(meili, "disponible", lambda: True)

    codigos = {api.get(URL).status_code for _ in range(40)}

    assert codigos == {200}
