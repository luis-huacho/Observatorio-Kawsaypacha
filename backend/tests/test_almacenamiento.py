"""Las imágenes que se insertan desde el editor de texto rico.

Dos ajustes que existían y no hacían nada: `CKEDITOR_5_UPLOAD_PATH` —la librería lo ignora— y
`CONTENIDO_ANCHO_MAXIMO_PX`, que no se usaba en ningún sitio mientras el comentario de al lado
prometía que las fotos «se reescalan al guardar». Lo que se fija aquí es que los dos sean verdad.

Las imágenes se generan al vuelo: son unos pocos píxeles y así la prueba dice exactamente qué entra.
"""
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

import pytest

from apps.core.almacenamiento import AlmacenamientoContenido

pytestmark = pytest.mark.django_db


def _imagen(ancho: int, alto: int, formato: str = "JPEG", exif=None) -> bytes:
    from PIL import Image

    imagen = Image.new("RGB", (ancho, alto), (0, 146, 87))
    destino = BytesIO()
    guardado = {"exif": exif} if exif is not None else {}
    imagen.save(destino, format=formato, **guardado)
    return destino.getvalue()


def _subida(nombre: str, contenido: bytes) -> SimpleUploadedFile:
    return SimpleUploadedFile(nombre, contenido, content_type="image/jpeg")


def _dimensiones(almacenamiento, ruta):
    from PIL import Image

    with almacenamiento.open(ruta) as archivo:
        return Image.open(archivo).size


@pytest.fixture
def almacenamiento():
    """Instancia nueva, como la que crea la librería en cada subida."""
    return AlmacenamientoContenido()


@pytest.fixture
def carpeta_del_mes():
    return timezone.localdate().strftime("contenido/%Y/%m")


def test_las_imagenes_van_a_la_carpeta_del_mes(almacenamiento, carpeta_del_mes):
    """La convención del resto del proyecto (`medidas/%Y/%m/`, `noticias/%Y/%m/`…)."""
    ruta = almacenamiento.save("foto.jpg", _subida("foto.jpg", _imagen(400, 300)))

    assert ruta.startswith(f"{carpeta_del_mes}/")
    assert almacenamiento.url(ruta).startswith("/media/contenido/")


def test_una_foto_grande_se_reduce_al_ancho_maximo(almacenamiento, settings):
    """El caso que motiva todo: una foto de campo sin recortar servida a cada visitante."""
    original = _imagen(3000, 2000)

    ruta = almacenamiento.save("campo.jpg", _subida("campo.jpg", original))

    assert _dimensiones(almacenamiento, ruta) == (settings.CONTENIDO_ANCHO_MAXIMO_PX, 1067)
    assert almacenamiento.size(ruta) < len(original)
    assert ruta.endswith(".webp")


def test_una_imagen_del_editor_se_convierte_a_webp(almacenamiento):
    """El contenido del editor va a WebP aunque ya quepa: ahí está el ahorro.

    Se puede porque estas imágenes viven dentro del cuerpo del artículo y **no se usan como
    `og:image`**, que es lo que obliga a las portadas a quedarse en JPEG (ver `core/imagenes.py`).
    """
    from PIL import Image

    original = _imagen(800, 600)

    ruta = almacenamiento.save("pequena.jpg", _subida("pequena.jpg", original))

    assert ruta.endswith(".webp"), "el nombre tiene que decir lo que el archivo es"
    assert _dimensiones(almacenamiento, ruta) == (800, 600)
    with almacenamiento.open(ruta) as archivo:
        assert Image.open(archivo).format == "WEBP"


def test_lo_que_ya_esta_en_webp_y_cabe_no_se_recomprime(almacenamiento):
    """Se escribe byte por byte: recomprimir «por si acaso» degrada un poco en cada guardado."""
    original = _imagen(800, 600, formato="WEBP")

    ruta = almacenamiento.save("pequena.webp", _subida("pequena.webp", original))

    assert _dimensiones(almacenamiento, ruta) == (800, 600)
    with almacenamiento.open(ruta) as archivo:
        assert archivo.read() == original


def test_un_gif_no_se_toca(almacenamiento):
    """Reescalar un GIF con Pillow se lleva por delante la animación."""
    original = _imagen(3000, 2000, formato="GIF")

    ruta = almacenamiento.save("animado.gif", _subida("animado.gif", original))

    with almacenamiento.open(ruta) as archivo:
        assert archivo.read() == original


def test_una_foto_tumbada_sale_derecha(almacenamiento):
    """Las fotos de móvil llegan con `Orientation`, y en un informe se ven tumbadas."""
    from PIL import Image

    imagen = Image.new("RGB", (1200, 800), (0, 146, 87))
    exif = imagen.getexif()
    exif[0x0112] = 6  # girada 90°
    ruta = almacenamiento.save("movil.jpg", _subida("movil.jpg", _imagen(1200, 800, exif=exif)))

    # Se intercambian ancho y alto, y aunque cabía de sobra se reescribe: la orientación es parte
    # del contenido, no un adorno.
    assert _dimensiones(almacenamiento, ruta) == (800, 1200)


def test_un_nombre_con_ruta_no_escapa_de_la_carpeta(almacenamiento, carpeta_del_mes):
    """El nombre lo pone el navegador, así que se toma solo el basename."""
    ruta = almacenamiento.save("../../fuera.jpg", _subida("x.jpg", _imagen(200, 200)))

    assert ruta.startswith(f"{carpeta_del_mes}/")
    assert ".." not in ruta


def test_un_archivo_que_no_es_imagen_no_rompe_la_subida(almacenamiento, carpeta_del_mes):
    """Si Pillow no puede abrirlo se guarda tal cual: mejor un archivo raro que una subida perdida."""
    ruta = almacenamiento.save("roto.jpg", _subida("roto.jpg", b"esto no es una imagen"))

    assert ruta.startswith(f"{carpeta_del_mes}/")
    with almacenamiento.open(ruta) as archivo:
        assert archivo.read() == b"esto no es una imagen"
