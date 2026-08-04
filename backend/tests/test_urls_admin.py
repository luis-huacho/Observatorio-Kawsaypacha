"""Las rutas que cuelgan del prefijo del admin, y el botón de reindexar.

Existe por un fallo real y silencioso: `AdminSite` termina sus URLs con un `catch_all_view` que casa
con **cualquier cosa** bajo su prefijo y responde 404, así que una ruta declarada después de
`admin.site.urls` nunca se alcanza. La subida de imágenes del editor estaba en esa situación: el
botón de imagen existe en la barra de CKEditor y su endpoint devolvía 404, sin que nada lo dijera.

De ahí que la prueba mire a **qué vista resuelve** cada URL y no solo el código de respuesta: un 404
del catch-all y un 404 de verdad son indistinguibles desde fuera.
"""
from django.conf import settings
from django.urls import resolve, reverse

import pytest

pytestmark = pytest.mark.django_db


def _la_captura_el_admin(ruta: str) -> bool:
    """¿Cae la URL en el `catch_all_view` del admin? Se compara por nombre porque el admin envuelve
    sus vistas con `admin_view`, así que el objeto que devuelve `resolve` no es la función original
    —conserva el nombre gracias a `functools.wraps`—."""
    vista = resolve(ruta).func
    return getattr(vista, "__name__", "") == "catch_all_view"


def test_la_subida_de_imagenes_del_editor_no_la_captura_el_admin():
    """Si esto falla, insertar una imagen desde el texto rico vuelve a dar 404."""
    ruta = f"/{settings.ADMIN_URL}ckeditor5/image_upload/"

    assert not _la_captura_el_admin(ruta)
    assert resolve(ruta).url_name == "ck_editor_5_upload_file"


def test_la_ruta_de_reindexar_no_la_captura_el_admin():
    from apps.core.vistas_admin import reindexar_busqueda

    ruta = reverse("reindexar-busqueda")

    assert not _la_captura_el_admin(ruta)
    # `staff_member_required` y `require_POST` envuelven la vista en dos capas; ambas conservan el
    # nombre, así que es lo que se compara.
    assert resolve(ruta).func.__name__ == reindexar_busqueda.__name__


def test_reindexar_vive_bajo_el_prefijo_del_admin():
    """No es una URL pública: cuelga del prefijo del admin, que no se anuncia."""
    assert reverse("reindexar-busqueda").startswith(f"/{settings.ADMIN_URL}")


# --- La vista ---------------------------------------------------------------


def test_sin_sesion_de_staff_no_se_puede_reindexar(client):
    respuesta = client.post(reverse("reindexar-busqueda"))

    # Redirige al login del admin: no ejecuta nada.
    assert respuesta.status_code == 302
    assert "login" in respuesta["Location"]


class TareaFalsa:
    """Sustituye a la tarea sin ejecutarla. `Task` de django-tasks es inmutable, así que se
    reemplaza el nombre del módulo —la vista lo importa dentro de la función— y no su atributo."""

    def __init__(self):
        self.llamadas = []

    def enqueue(self, *args, **kwargs):
        self.llamadas.append((args, kwargs))


@pytest.fixture
def tarea_reindexar(monkeypatch):
    falsa = TareaFalsa()
    monkeypatch.setattr("apps.core.tasks.reindexar_meili", falsa)
    return falsa


def test_por_get_no_se_reindexa(client, usuarios, tarea_reindexar):
    """Un GET no puede disparar una acción: bastaría con que alguien enlazara la URL."""
    client.force_login(usuarios["publicador"])

    respuesta = client.get(reverse("reindexar-busqueda"))

    assert respuesta.status_code == 405
    assert tarea_reindexar.llamadas == []


def test_el_boton_encola_la_reindexacion_y_vuelve_al_panel(client, usuarios, tarea_reindexar):
    """Encola, no ejecuta: reconstruir el índice de centros poblados son ~16 s y 8.968 documentos,
    y una petición HTTP no es el sitio para eso."""
    client.force_login(usuarios["publicador"])

    respuesta = client.post(reverse("reindexar-busqueda"), follow=True)

    assert len(tarea_reindexar.llamadas) == 1
    assert respuesta.status_code == 200
    mensajes = [str(m) for m in respuesta.context["messages"]]
    assert any("reconstruyendo" in m for m in mensajes), mensajes


def test_el_panel_del_admin_muestra_el_estado_del_buscador(client, usuarios, monkeypatch):
    """La tarjeta es la única forma que tiene PREDES de ver un índice desfasado."""
    from apps.core.services import meili

    monkeypatch.setattr(
        meili,
        "estado_indices",
        lambda: {
            "disponible": True,
            "pendientes": 0,
            "al_dia": False,
            "indices": [
                {"slug": "medidas", "etiqueta": "Medidas", "en_meili": 0, "en_bd": 3,
                 "al_dia": False}
            ],
        },
    )
    client.force_login(usuarios["publicador"])

    contenido = client.get(f"/{settings.ADMIN_URL}").content.decode()

    assert "Buscador" in contenido
    assert "no está en el buscador" in contenido
    assert "Reindexar la búsqueda" in contenido


def test_con_el_buscador_caido_el_panel_sigue_abriendo(client, usuarios, monkeypatch):
    """Un servicio caído no puede tumbar la portada del admin."""
    from apps.core.services import meili

    monkeypatch.setattr(
        meili,
        "estado_indices",
        lambda: {"disponible": False, "pendientes": 0, "al_dia": False, "indices": []},
    )
    client.force_login(usuarios["publicador"])

    respuesta = client.get(f"/{settings.ADMIN_URL}")

    assert respuesta.status_code == 200
    assert "no está respondiendo" in respuesta.content.decode()
