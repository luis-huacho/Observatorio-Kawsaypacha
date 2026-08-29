"""Almacenamiento de las imágenes que se insertan desde el editor de texto rico.

Existe porque `django-ckeditor-5` **ignora `CKEDITOR_5_UPLOAD_PATH`**: su
`storage_utils.handle_uploaded_file` hace `fs.save(f.name, f)` sin prefijo, de modo que las imágenes
caían en la raíz de `media/` revueltas con los datasets y los tiles. El único gancho que la librería
ofrece es `CKEDITOR_5_FILE_STORAGE`, y aquí se aprovecha para las dos cosas que hacían falta: poner
las imágenes en su carpeta y **no publicar fotos de 6.000 px**.

Alcance: esto vale para las imágenes que se insertan **desde el editor**. Las de los campos de imagen
de los modelos (portadas, galería de medidas, hero) las cubre `ImagenOptimizadaMixin`, y el trabajo
en sí lo hace `apps.core.imagenes`, compartido por los dos.

Aquí el destino es **WebP**: el contenido del editor no se comparte por redes como `og:image`, así
que no le aplica la cautela que obliga a las portadas a quedarse en JPEG (ver `imagenes.py`).
"""
from pathlib import PurePosixPath

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils import timezone

from apps.core import imagenes


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
        """Reduce y convierte a WebP antes de escribir.

        El nombre se ajusta **solo si la imagen se reescribió**: `optimizar` devuelve el archivo
        original cuando no había nada que hacer o cuando no supo abrirlo (un SVG, por ejemplo), y en
        ese caso renombrarlo a `.webp` sería mentir sobre el contenido.
        """
        reducida = imagenes.optimizar(
            content, settings.CONTENIDO_ANCHO_MAXIMO_PX, imagenes.FORMATO_EDITOR
        )
        if reducida is not content:
            name = imagenes.renombrar(name, imagenes.FORMATO_EDITOR)
        return super()._save(name, reducida)
