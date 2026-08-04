"""Almacenamiento de las imágenes que se insertan desde el editor de texto rico.

Existe porque `django-ckeditor-5` **ignora `CKEDITOR_5_UPLOAD_PATH`**: su
`storage_utils.handle_uploaded_file` hace `fs.save(f.name, f)` sin prefijo, de modo que las imágenes
caían en la raíz de `media/` revueltas con los datasets y los tiles. El único gancho que la librería
ofrece es `CKEDITOR_5_FILE_STORAGE`, y aquí se aprovecha para las dos cosas que hacían falta: poner
las imágenes en su carpeta y **no publicar fotos de 6.000 px**.

Alcance: esto vale para las imágenes que se insertan **desde el editor**. Las de los campos de imagen
del formulario (portadas, galería de medidas, hero) siguen guardándose tal cual; aplicarles lo mismo
sería otro cambio.
"""
from io import BytesIO
from pathlib import PurePosixPath

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.utils import timezone

#: Etiqueta EXIF de orientación. Las fotos de móvil llegan tumbadas con esto puesto.
EXIF_ORIENTACION = 0x0112

#: Formatos que se pueden reescalar sin perder nada. **GIF queda fuera a propósito**: Pillow pierde
#: la animación al reescalarlo. TIFF también: es formato de archivo, no de publicación.
FORMATOS_REESCALABLES = {"JPEG", "PNG", "WEBP"}

#: Opciones de guardado por formato, para no engordar el archivo al reescribirlo.
OPCIONES = {
    "JPEG": {"quality": 85, "optimize": True, "progressive": True},
    "PNG": {"optimize": True},
    "WEBP": {"quality": 85},
}


class AlmacenamientoContenido(FileSystemStorage):
    """Guarda bajo `CKEDITOR_5_UPLOAD_PATH` y reduce las imágenes grandes."""

    def _con_prefijo(self, nombre) -> str:
        """El nombre bajo `contenido/<año>/<mes>/`, como hace `upload_to` en los modelos.

        El prefijo se resuelve **en cada guardado**, no fijando `location` en el constructor:
        `location` es un `cached_property`, así que un gunicorn arrancado en julio seguiría
        escribiendo en `07/` durante agosto.

        Del nombre que manda el navegador se toma solo el basename, así que un `../../algo.png` no
        puede salir de la carpeta. Y es **idempotente**: si el nombre ya viene con el prefijo se deja
        igual, porque los campos de modelo pasan por `generate_filename` **y** por `save`, y de otro
        modo saldría `contenido/2026/08/contenido/2026/08/foto.jpg`.
        """
        nombre = str(nombre or "")
        prefijo = timezone.localdate().strftime(settings.CKEDITOR_5_UPLOAD_PATH)
        if nombre.startswith(prefijo):
            return nombre
        return str(PurePosixPath(prefijo) / PurePosixPath(nombre.replace("\\", "/")).name)

    def save(self, name, content, max_length=None):
        """`Storage.save` **no** llama a `generate_filename` —solo lo hace la ruta de los campos de
        modelo—, y la librería del editor guarda con `fs.save(f.name, f)`. Por eso el prefijo se
        aplica aquí; `generate_filename` se mantiene para que el storage también sirva a un
        `ImageField` si algún día se usa así."""
        return super().save(self._con_prefijo(name or getattr(content, "name", "")), content,
                            max_length)

    def generate_filename(self, filename: str) -> str:
        return super().generate_filename(self._con_prefijo(filename))

    def _save(self, name, content):
        return super()._save(name, self._reducida(content))

    def _reducida(self, archivo):
        """La imagen dentro del ancho máximo y con la orientación corregida.

        Devuelve el archivo **tal cual llegó** si no hay nada que hacer o si algo falla: perder la
        foto de alguien por un reescalado sería peor que servirla grande.
        """
        from PIL import Image, ImageOps

        maximo = settings.CONTENIDO_ANCHO_MAXIMO_PX
        try:
            archivo.seek(0)
            imagen = Image.open(archivo)
            formato = (imagen.format or "").upper()
            tumbada = imagen.getexif().get(EXIF_ORIENTACION, 1) not in (1, None)

            if formato not in FORMATOS_REESCALABLES or (imagen.width <= maximo and not tumbada):
                archivo.seek(0)
                return archivo

            imagen = ImageOps.exif_transpose(imagen)
            if imagen.width > maximo:
                alto = round(imagen.height * maximo / imagen.width)
                imagen = imagen.resize((maximo, alto), Image.LANCZOS)

            destino = BytesIO()
            imagen.save(destino, format=formato, **OPCIONES.get(formato, {}))
            return ContentFile(destino.getvalue(), name=getattr(archivo, "name", None))
        except Exception:  # noqa: BLE001 — un archivo raro se guarda sin tocar, no se pierde
            archivo.seek(0)
            return archivo
