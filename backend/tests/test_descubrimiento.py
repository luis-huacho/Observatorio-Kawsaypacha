"""Lo que el sitio publica para que lo descubra una máquina: `/robots.txt` y el catálogo de API.

**La prueba que da sentido a todo el archivo es `test_el_sitemap_se_anuncia_en_el_dominio_del_sitio`.**
El robots.txt era un archivo estático con esta línea escrita a mano:

    Sitemap: https://observatorio.predes.org.pe/sitemap.xml

y el sitio en el aire era otro dominio, que además todavía no resuelve. El sitemap funcionaba —26
URL, `application/xml`, todo correcto— y no lo leía nadie, porque el único documento que dice dónde
está apuntaba a un host inexistente. Un fallo silencioso de manual: todas las piezas en verde y el
resultado, cero.
"""
import datetime
import json

from django.test import Client

import pytest

pytestmark = pytest.mark.django_db


@pytest.fixture
def cliente():
    return Client(headers={"host": "localhost"})


def _robots(cliente) -> str:
    return cliente.get("/robots.txt").content.decode()


def _directivas(cuerpo: str) -> str:
    """El robots.txt sin comentarios.

    Hace falta porque el preámbulo explica por qué la línea `Sitemap:` la genera el backend, y
    buscar la palabra a secas encontraría esa explicación en vez de la directiva.
    """
    return "\n".join(
        linea for linea in cuerpo.splitlines() if linea.strip() and not linea.startswith("#")
    )


# --- robots.txt -------------------------------------------------------------


def test_el_robots_es_texto_plano(cliente):
    """Servido con el `Content-Type` equivocado no lo lee ningún rastreador."""
    respuesta = cliente.get("/robots.txt")

    assert respuesta.status_code == 200
    assert respuesta["Content-Type"].startswith("text/plain")


def test_el_sitemap_se_anuncia_en_el_dominio_del_sitio(cliente, settings):
    """La regresión: la URL sale de `SITE_URL`, no de una cadena escrita a mano.

    Se comprueba cambiando el ajuste, que es la única forma de distinguir «está bien» de «está
    clavado y coincide por casualidad con el entorno en el que corre la prueba».
    """
    settings.SITE_URL = "https://otro-dominio.example.pe"

    assert "Sitemap: https://otro-dominio.example.pe/sitemap.xml" in _robots(cliente)


def test_el_sitemap_anunciado_existe_de_verdad(cliente, settings):
    """Anunciar un sitemap que no responde es peor que no anunciarlo: gasta el presupuesto de
    rastreo y deja al buscador sin la lista de URL."""
    settings.SITE_URL = "https://localhost"
    ruta = _robots(cliente).split("Sitemap: https://localhost")[1].strip()

    assert cliente.get(ruta).status_code == 200


def test_las_senales_de_contenido_van_dentro_del_grupo_de_user_agent(cliente):
    """Content-Signal es una directiva del grupo, no una línea suelta del preámbulo.

    Fuera del grupo, un parser que sí la implemente no sabe a qué agentes se aplica.
    """
    cuerpo = _robots(cliente)

    assert "Content-Signal: ai-train=no, search=yes, ai-input=yes" in cuerpo
    grupo = cuerpo.index("User-agent: *")
    assert grupo < cuerpo.index("Content-Signal:") < cuerpo.index("Allow: /")


def test_un_despliegue_que_no_es_el_canonico_se_cierra_entero(cliente, settings):
    settings.SITIO_INDEXABLE = False
    directivas = _directivas(_robots(cliente))

    assert "Disallow: /" in directivas
    assert "Allow: /" not in directivas
    # Y sin sitemap: anunciar el mapa de lo que acabas de prohibir es una contradicción, y quien
    # la resuelve es el rastreador, no nosotros.
    assert "Sitemap:" not in directivas


def test_por_defecto_el_sitio_se_deja_rastrear(cliente):
    """El default importa: un `SITIO_INDEXABLE` ausente del `.env` no puede desindexar el sitio."""
    directivas = _directivas(_robots(cliente))

    assert "Allow: /" in directivas
    assert "Disallow: /" not in directivas


# --- El catálogo de API -----------------------------------------------------


def _catalogo(cliente) -> dict:
    return json.loads(cliente.get("/.well-known/api-catalog").content)


def test_el_catalogo_es_linkset_json(cliente):
    """RFC 9727 fija la ruta y el tipo. Con otro tipo, un cliente conforme lo descarta."""
    respuesta = cliente.get("/.well-known/api-catalog")

    assert respuesta.status_code == 200
    assert respuesta["Content-Type"] == "application/linkset+json"
    assert respuesta["Access-Control-Allow-Origin"] == "*"


def test_el_catalogo_describe_el_api_publico(cliente):
    enlaces = _catalogo(cliente)["linkset"]

    assert len(enlaces) == 1
    contexto = enlaces[0]
    assert contexto["anchor"].endswith("/api/")
    # Las tres relaciones que hacen útil el catálogo: qué habla, cómo se lee y si está vivo.
    for relacion in ("service-desc", "service-doc", "status"):
        assert contexto[relacion], f"falta {relacion}"


def test_el_catalogo_apunta_al_dominio_del_api_y_no_al_de_la_spa(cliente, settings):
    """La SPA y el API viven en dominios distintos (ADR-A14): el catálogo describe el segundo."""
    settings.BACKEND_URL = "https://api.example.pe"

    assert _catalogo(cliente)["linkset"][0]["anchor"] == "https://api.example.pe/api/"


def test_ningun_enlace_del_catalogo_esta_muerto(cliente, settings):
    """El modo de fallo del caso: un catálogo que existe y apunta a URLs que ya no están se ve
    exactamente igual que uno bueno. Solo se nota pidiéndolas."""
    settings.BACKEND_URL = "http://testserver"
    contexto = _catalogo(cliente)["linkset"][0]

    destinos = [contexto["anchor"]]
    for relacion in ("service-desc", "service-doc", "status"):
        destinos += [enlace["href"] for enlace in contexto[relacion]]

    for url in destinos:
        ruta = url.removeprefix("http://testserver")
        assert cliente.get(ruta).status_code == 200, f"{ruta} no responde 200"


def test_el_catalogo_no_promete_autenticacion(cliente):
    """El API es anónimo y de solo lectura. Declarar un `authorization_servers` o un flujo OAuth
    mandaría a un agente a negociar credenciales contra algo que no existe (ADR-A26)."""
    crudo = cliente.get("/.well-known/api-catalog").content.decode().lower()

    for palabra in ("oauth", "openid", "authorization_servers", "token_endpoint"):
        assert palabra not in crudo
