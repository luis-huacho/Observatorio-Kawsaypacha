"""Validación de los archivos que sube un editor.

**Vive en `core` y no en la app que lo estrena porque es una guarda de seguridad**, y el proyecto
ya tomó dos veces la misma decisión por el mismo motivo: ADR-D8 generalizó `RedaccionIAMixin`
para no duplicar la guarda anti-SSRF, y `core.importacion_admin` se extrajo para no duplicar la
anti-*path traversal*. Una comprobación de seguridad copiada es una comprobación que un día se
arregla en un sitio y no en el otro. Hoy la usa `contenidos.NoticiaArchivo`; el día que una norma
o una medida acepten adjuntos, la reutilizan.

**Por qué la lista de extensiones es una guarda y no un capricho de formato:** nginx sirve
`/media/` entero como estático público, y lo hace en el **dominio del API**, que es el mismo donde
vive la sesión del admin. Un `.html` o un `.svg` subido ahí se sirve como HTML o como
`image/svg+xml` y **ejecuta JavaScript en ese origen** — XSS almacenado. El `nosniff` que ese
`location` ya lleva no lo cubre: impide que el navegador *adivine* un tipo, no que nginx sirva un
`.html` como `text/html`, que es exactamente lo que haría. Y el bloque no pone
`Content-Disposition: attachment`, así que la lista blanca es lo único que hay.

**Y por qué es una función y no `FileExtensionValidator(allowed_extensions=[…])`, que sería lo
primero que uno prueba:** ese validador es una instancia deconstruible y su lista de extensiones
entra en `Field.deconstruct()`, o sea **en la migración**. Aceptar un formato nuevo sería un
`AlterField` y un despliegue. Una función se serializa como su ruta de importación, así que
ampliar `EXTENSIONES_ADJUNTO` no emite nada — el mismo argumento con el que `ImagenOptimizadaMixin`
optimiza en `save()` en vez de declarar un `storage=`, y con el que `TipoNorma` dejó de ser un
`TextChoices` (ADR-D11). Hay una prueba de `makemigrations --check` que lo vigila.
"""
from pathlib import PurePosixPath

from django.core.exceptions import ValidationError

#: Documentos, hojas de cálculo, presentaciones, comprimidos e imágenes. **Sin `svg` ni `html`**
#: —ver el docstring—, y sin nada ejecutable.
EXTENSIONES_ADJUNTO = frozenset({
    "pdf",
    "doc", "docx", "odt", "rtf",
    "xls", "xlsx", "ods", "csv",
    "ppt", "pptx", "odp",
    "txt",
    "zip",
    "jpg", "jpeg", "png", "webp", "gif",
})

#: Tiene que quedar **por debajo del `client_max_body_size 80M` de nginx**: si el límite efectivo
#: fuera el del servidor web, pasarse devolvería un 413 crudo en vez de un error de campo con su
#: mensaje. Django no impone ninguno por su cuenta — `FILE_UPLOAD_MAX_MEMORY_SIZE` solo decide
#: memoria contra archivo temporal, no rechaza nada.
TAMANO_MAXIMO_ADJUNTO_MB = 20


def extension_de(nombre: str) -> str:
    """`Informe FINAL.PDF` → `pdf`. En minúscula, sin punto y sin la ruta."""
    return PurePosixPath(nombre).suffix.lstrip(".").lower()


def validar_adjunto(archivo) -> None:
    extension = extension_de(archivo.name)
    if extension not in EXTENSIONES_ADJUNTO:
        permitidas = ", ".join(sorted(EXTENSIONES_ADJUNTO))
        raise ValidationError(
            "No se admiten archivos «.%(extension)s». Formatos aceptados: %(permitidas)s.",
            code="extension_no_admitida",
            params={"extension": extension or "(sin extensión)", "permitidas": permitidas},
        )

    try:
        peso = archivo.size
    except (FileNotFoundError, OSError):
        # **`full_clean()` corre los validadores en cada guardado**, también sobre un archivo que
        # ya estaba escrito. Si ese archivo desapareció del disco, `.size` no lanza `ValidationError`
        # sino `FileNotFoundError`: el editor vería un 500 al corregir un título, sin ninguna
        # relación aparente con lo que estaba haciendo. Un archivo ausente no es un archivo
        # demasiado grande, y no le toca a este validador denunciarlo.
        return

    tope = TAMANO_MAXIMO_ADJUNTO_MB * 1024 * 1024
    if peso > tope:
        raise ValidationError(
            "El archivo pesa %(peso).1f MB y el máximo son %(tope)s MB.",
            code="archivo_demasiado_grande",
            params={"peso": peso / (1024 * 1024), "tope": TAMANO_MAXIMO_ADJUNTO_MB},
        )
