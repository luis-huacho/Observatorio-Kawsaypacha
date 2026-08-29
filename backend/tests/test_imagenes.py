"""Optimización de las imágenes de los campos de modelo.

Lo que protege es un fallo que **no da ningún síntoma en el servidor**: una portada de 6 MB y
6.000 px se publica igual de bien que una de 200 KB, solo que el visitante la descarga entera. No
hay error, no hay log, no hay nada — solo una página que tarda.

Y protege también el modo de fallo contrario, que sería peor: que optimizar **pierda** la imagen.
De ahí las pruebas del SVG y del archivo corrupto.
"""
import os
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile

import pytest

from apps.core import imagenes

pytestmark = pytest.mark.django_db


def _bytes_imagen(ancho: int, alto: int, formato: str = "JPEG", modo: str = "RGB") -> bytes:
    from PIL import Image

    color = (0, 146, 87, 255) if modo == "RGBA" else (0, 146, 87)
    destino = BytesIO()
    Image.new(modo, (ancho, alto), color).save(destino, format=formato)
    return destino.getvalue()


def _subida(nombre: str, contenido: bytes) -> SimpleUploadedFile:
    return SimpleUploadedFile(nombre, contenido, content_type="image/jpeg")


def _abrir(campo):
    from PIL import Image

    campo.open()
    try:
        return Image.open(BytesIO(campo.read()))
    finally:
        campo.close()


@pytest.fixture
def noticia():
    import datetime

    from apps.contenidos.models import Noticia

    def crear(**extra):
        return Noticia.objects.create(
            slug=extra.pop("slug", "una-noticia"),
            titulo="Una noticia",
            bajada="",
            fecha=datetime.date.today(),
            **extra,
        )

    return crear


# --- La función ------------------------------------------------------------


def test_una_foto_grande_se_reduce(settings):
    original = _subida("campo.jpg", _bytes_imagen(3000, 2000))

    salida = imagenes.optimizar(original, settings.CONTENIDO_ANCHO_MAXIMO_PX,
                                imagenes.FORMATO_PUBLICACION)

    from PIL import Image

    assert Image.open(BytesIO(salida.read())).size == (settings.CONTENIDO_ANCHO_MAXIMO_PX, 1067)


def test_una_imagen_con_transparencia_no_va_a_jpeg(settings):
    """JPEG no tiene canal alfa: convertirla dejaría el fondo en negro."""
    original = _subida("logo.png", _bytes_imagen(2400, 1200, formato="PNG", modo="RGBA"))

    salida = imagenes.optimizar(original, settings.CONTENIDO_ANCHO_MAXIMO_PX,
                                imagenes.FORMATO_PUBLICACION)

    from PIL import Image

    assert Image.open(BytesIO(salida.read())).format == "WEBP"


def test_es_idempotente(settings):
    """Corre en cada `save()`: recomprimir cada vez degradaría la imagen poco a poco."""
    ya_hecha = _subida("ok.jpg", _bytes_imagen(800, 600))

    salida = imagenes.optimizar(ya_hecha, settings.CONTENIDO_ANCHO_MAXIMO_PX,
                                imagenes.FORMATO_PUBLICACION)

    assert salida is ya_hecha, "una imagen que ya cumple se devuelve intacta"


def test_un_svg_pasa_intacto(settings):
    """Los logotipos del sitio son SVG. Pillow no los abre, y eso basta: se guardan tal cual."""
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><rect width="10" height="10"/></svg>'
    original = _subida("logo.svg", svg)

    salida = imagenes.optimizar(original, 1600, imagenes.FORMATO_PUBLICACION)

    assert salida is original


def test_un_archivo_corrupto_no_se_pierde(settings):
    """Perder la foto de alguien por optimizarla sería peor que servirla grande."""
    original = _subida("roto.jpg", b"esto no es una imagen")

    assert imagenes.optimizar(original, 1600, imagenes.FORMATO_PUBLICACION) is original


def test_el_nombre_dice_lo_que_el_archivo_es():
    assert imagenes.renombrar("noticias/2026/08/foto.jpg", "WEBP") == "noticias/2026/08/foto.webp"
    assert imagenes.renombrar(None, "WEBP") is None


# --- El mixin en los modelos ----------------------------------------------


def test_la_portada_de_una_noticia_se_optimiza_al_guardar(noticia, settings):
    """El caso que motiva todo, y por la vía real: el `save()` del modelo."""
    grande = _bytes_imagen(3000, 2000)

    n = noticia(imagen_portada=_subida("campo.jpg", grande))

    assert _abrir(n.imagen_portada).size == (settings.CONTENIDO_ANCHO_MAXIMO_PX, 1067)
    assert n.imagen_portada.size < len(grande)


def test_la_ruta_no_se_duplica_al_renombrar(noticia):
    """`FieldFile.save` vuelve a pasar el nombre por `upload_to`, así que darle la ruta ya
    resuelta produciría `noticias/2026/08/noticias/2026/08/foto.jpg`."""
    n = noticia(imagen_portada=_subida("campo.jpg", _bytes_imagen(3000, 2000)))

    assert n.imagen_portada.name.count("noticias/") == 1


def test_volver_a_guardar_no_reprocesa_la_imagen(noticia):
    """Sin esto, cada edición del texto recomprimiría la portada una vez más."""
    n = noticia(imagen_portada=_subida("campo.jpg", _bytes_imagen(3000, 2000)))
    antes = (n.imagen_portada.name, n.imagen_portada.size)

    n.titulo = "Otro título"
    n.save()

    assert (n.imagen_portada.name, n.imagen_portada.size) == antes


def test_una_noticia_sin_portada_se_guarda_igual(noticia):
    """El campo es opcional y la mayoría de las noticias no traen imagen."""
    assert noticia(slug="sin-portada").pk is not None


def test_el_mixin_no_emite_migraciones():
    """La razón de procesar en `save()` y no con `storage=` en el campo: `storage` forma parte de
    `FileField.deconstruct()` y habría metido seis migraciones que no cambian ni una columna."""
    from io import StringIO

    from django.core.management import call_command

    salida = StringIO()
    call_command("makemigrations", "--check", "--dry-run", stdout=salida)
    assert "No changes detected" in salida.getvalue()


# --- El comando para lo ya subido -----------------------------------------


def test_el_comando_simula_sin_tocar_nada(noticia, settings):
    """`--simular` existe porque esto reescribe archivos del `media/` de producción."""
    from io import StringIO

    from django.core.management import call_command

    # Se salta el mixin (`update` no llama a `save()`) para dejar una imagen «antigua», grande,
    # como las que ya están publicadas.
    n = noticia(imagen_portada=_subida("campo.jpg", _bytes_imagen(400, 300)))
    ruta = n.imagen_portada.storage.path(n.imagen_portada.name)
    with open(ruta, "wb") as destino:
        destino.write(_bytes_imagen(3000, 2000))
    antes = open(ruta, "rb").read()

    salida = StringIO()
    call_command("optimizar_imagenes", "--simular", stdout=salida)

    assert "Simulación" in salida.getvalue()
    assert open(ruta, "rb").read() == antes, "con --simular no se escribe nada"


def test_el_comando_reduce_conservando_la_ruta(noticia, settings):
    """No cambia el formato a propósito: cambiar la extensión rompería los enlaces publicados."""
    from django.core.management import call_command

    n = noticia(imagen_portada=_subida("campo.jpg", _bytes_imagen(400, 300)))
    nombre = n.imagen_portada.name
    ruta = n.imagen_portada.storage.path(nombre)
    with open(ruta, "wb") as destino:
        destino.write(_bytes_imagen(3000, 2000))

    call_command("optimizar_imagenes")

    from PIL import Image

    with open(ruta, "rb") as archivo:
        reducida = Image.open(archivo)
        assert reducida.size == (settings.CONTENIDO_ANCHO_MAXIMO_PX, 1067)
        assert reducida.format == "JPEG", "el formato se conserva"
    n.refresh_from_db()
    assert n.imagen_portada.name == nombre, "la URL publicada no cambia"


def test_una_referencia_a_un_archivo_borrado_no_para_el_comando(noticia):
    """En `media/` sobreviven referencias a archivos borrados a mano."""
    from django.core.management import call_command

    n = noticia(imagen_portada=_subida("campo.jpg", _bytes_imagen(400, 300)))
    os.remove(n.imagen_portada.storage.path(n.imagen_portada.name))

    call_command("optimizar_imagenes")  # no debe lanzar
