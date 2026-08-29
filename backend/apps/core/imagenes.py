"""Optimización de imágenes: una sola implementación para el editor y para los modelos.

Nació dentro de `almacenamiento.py`, que reducía las imágenes pegadas en el editor de texto rico.
Su propio docstring declaraba el hueco: *«las de los campos de imagen del formulario (portadas,
galería de medidas, hero) siguen guardándose tal cual»*. Ese hueco era casi todo — **ningún
`ImageField` de ningún modelo pasaba por aquí**, así que una foto de campo de 6 MB y 6.000 px
subida como portada de una medida se publicaba entera.

Aquí vive el trabajo; quién lo aplica son dos:

- `AlmacenamientoContenido` (editor de CKEditor), que ya lo hacía y no cambia de comportamiento.
- `ImagenOptimizadaMixin` (`apps.core.models`), para los campos de imagen de los modelos.

**Tres decisiones que conviene no reabrir:**

1. **Si algo falla, el archivo se guarda tal cual.** Perder la foto de alguien por optimizarla sería
   mucho peor que servirla grande. Todo el camino va dentro de un `except` que devuelve el original,
   y de ahí sale gratis que un SVG o un PDF mal etiquetado pasen intactos: Pillow no los abre.
2. **GIF y TIFF quedan fuera.** Pillow pierde la animación al reescalar un GIF; TIFF es formato de
   archivo, no de publicación.
3. **El formato de destino depende de para qué es la imagen**, y lo elige quien llama:
   - `FORMATO_PUBLICACION` (JPEG progresivo) para las **portadas de los modelos**, porque son justo
     las candidatas a `og:image` y **WhatsApp y Facebook son poco fiables con WebP**. Una portada
     que no se previsualiza al compartir vale menos que los kilobytes que ahorra.
   - `FORMATO_EDITOR` (WebP) para lo que se pega **dentro del contenido**, que no tiene esa
     restricción y donde WebP gana entre un 25 % y un 35 % sobre JPEG a calidad equivalente.
   - En ambos casos, **una imagen con transparencia nunca va a JPEG**: perdería el canal alfa y
     saldría con fondo negro. Cae a WebP, que sí lo soporta.
"""
from io import BytesIO
from pathlib import PurePosixPath

from django.core.files.base import ContentFile

#: Etiqueta EXIF de orientación. Las fotos de móvil llegan tumbadas con esto puesto.
EXIF_ORIENTACION = 0x0112

#: Formatos que se pueden reescalar sin perder nada. Ver la decisión 2 del encabezado.
FORMATOS_REESCALABLES = {"JPEG", "PNG", "WEBP"}

#: Modos de Pillow que llevan canal alfa. Convertirlos a JPEG los deja con fondo negro.
MODOS_CON_ALFA = {"RGBA", "LA", "PA", "P"}

#: Opciones de guardado por formato, para no engordar el archivo al reescribirlo.
OPCIONES = {
    "JPEG": {"quality": 85, "optimize": True, "progressive": True},
    "PNG": {"optimize": True},
    "WEBP": {"quality": 85, "method": 6},
}

#: Destino de las portadas de los modelos. JPEG por compatibilidad con las previsualizaciones.
FORMATO_PUBLICACION = "JPEG"
#: Destino de las imágenes pegadas en el editor. WebP porque aquí sí se puede.
FORMATO_EDITOR = "WEBP"

EXTENSIONES = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}


def optimizar(archivo, ancho_maximo: int, formato_destino: str | None = None):
    """La imagen dentro del ancho máximo, orientada y en el formato pedido.

    Devuelve el archivo **tal cual llegó** si no hay nada que hacer o si algo falla.

    `formato_destino` a `None` conserva el formato de origen, que es lo que hacía esto cuando vivía
    en `almacenamiento.py`. Con un formato pedido, se convierte — salvo que la imagen tenga
    transparencia y el destino sea JPEG, en cuyo caso se usa WebP (ver decisión 3).

    **Es idempotente**: una imagen ya reducida y ya en el formato de destino se devuelve intacta,
    sin recomprimir. Importa porque el mixin corre en cada `save()` del modelo, y recomprimir un
    JPEG en cada guardado lo degrada un poco cada vez.
    """
    from PIL import Image, ImageOps

    try:
        archivo.seek(0)
        imagen = Image.open(archivo)
        origen = (imagen.format or "").upper()
        if origen not in FORMATOS_REESCALABLES:
            archivo.seek(0)
            return archivo

        destino = _formato_final(imagen, origen, formato_destino)
        tumbada = imagen.getexif().get(EXIF_ORIENTACION, 1) not in (1, None)

        if imagen.width <= ancho_maximo and not tumbada and destino == origen:
            archivo.seek(0)
            return archivo

        imagen = ImageOps.exif_transpose(imagen)
        if imagen.width > ancho_maximo:
            alto = round(imagen.height * ancho_maximo / imagen.width)
            imagen = imagen.resize((ancho_maximo, alto), Image.LANCZOS)

        # JPEG no admite alfa ni paleta. Solo se llega aquí sin alfa (lo garantiza `_formato_final`),
        # así que la conversión es segura.
        if destino == "JPEG" and imagen.mode not in ("RGB", "L"):
            imagen = imagen.convert("RGB")

        salida = BytesIO()
        imagen.save(salida, format=destino, **OPCIONES.get(destino, {}))
        return ContentFile(salida.getvalue(), name=renombrar(getattr(archivo, "name", None), destino))
    except Exception:  # noqa: BLE001 — un archivo raro se guarda sin tocar, no se pierde
        archivo.seek(0)
        return archivo


def renombrar(nombre: str | None, formato: str) -> str | None:
    """El mismo nombre con la extensión del formato de destino.

    Hace falta porque convertir a WebP y dejar el archivo llamándose `.jpg` funciona —el navegador
    mira el `Content-Type`— pero deja un `media/` en el que nada es lo que dice ser, y a la primera
    descarga el usuario se encuentra un `.jpg` que su visor no abre.
    """
    if not nombre:
        return nombre
    ruta = PurePosixPath(str(nombre))
    return str(ruta.with_suffix(EXTENSIONES.get(formato, ruta.suffix)))


def _formato_final(imagen, origen: str, pedido: str | None) -> str:
    """Qué formato se escribe, respetando la transparencia."""
    if pedido is None:
        return origen
    tiene_alfa = imagen.mode in MODOS_CON_ALFA or "transparency" in imagen.info
    if pedido == "JPEG" and tiene_alfa:
        return "WEBP"
    return pedido
