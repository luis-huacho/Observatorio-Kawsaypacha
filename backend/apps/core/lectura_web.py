"""Lectura de una página web ajena: descarga acotada, texto legible e imagen de portada.

Es la mitad genérica de la redacción asistida (ADR-D7, ADR-D8). Nació dentro de
`apps/contenidos/redaccion.py`, para noticias, y se sacó aquí cuando normativa necesitó lo mismo:
nada de este módulo sabe de noticias ni de normas, y **duplicarlo habría duplicado también la
guarda anti-SSRF**, que es la forma segura de que una de las dos copias se quede atrás.

Lo que sí es de cada dominio —el esquema JSON, las instrucciones al modelo y la normalización
contra el modelo de datos— vive en el `redaccion.py` de su app.

Tres trampas que este módulo cierra y que conviene no reabrir:

1. **La descarga es una petición que hace el servidor con un destino que escribe un usuario.** Se
   limita a `http`/`https` y se rechazan los destinos internos **resolviendo el nombre**: sin eso,
   cualquier cuenta de editor podría sondear la red privada (`http://meilisearch:7700`) desde
   dentro.
2. **`nh3` con `tags=set()` descarta el contenido de `<script>` y `<style>`**, que es justo lo que
   arruinaría el prompt. Pero pega las palabras entre bloques («MenúTitularPrimer») si no se mete
   antes un salto de línea delante de cada etiqueta de bloque.
3. **Que la cabecera diga `image/…` no basta**: la imagen se abre de verdad con Pillow antes de
   guardarla.
"""
import ipaddress
import re
import socket
import urllib.request
from urllib.parse import urlparse

import nh3
from django.conf import settings

#: Tope de descarga por defecto. Un artículo son decenas de KB; más que esto es una página que no
#: interesa. Quien necesite otro (el PDF de una norma) lo pasa por argumento.
MAXIMO_BYTES = 5 * 1024 * 1024
TIMEOUT_DESCARGA = 20
NAVEGADOR = "Mozilla/5.0 (compatible; ObservatorioKallpachakuy/1.0; +https://predes.org.pe/)"

#: Solo delante de etiquetas de bloque. Sin esto nh3 pega las palabras («MenúTitularPrimer»);
#: rompiendo en todas, parte también las de dentro de un párrafo y el texto queda ilegible.
BLOQUES = re.compile(
    r"(?i)<(?=/?(p|div|br|h[1-6]|li|ul|ol|tr|td|th|section|article|header|footer|nav|aside"
    r"|main|blockquote|figure|figcaption|pre|table)\b)"
)
IMAGEN_META = re.compile(
    r"""(?is)<meta[^>]+(?:property|name)\s*=\s*["'](?:og:image(?::url)?|twitter:image)["'][^>]*"""
    r"""content\s*=\s*["']([^"']+)["']"""
)
IMAGEN_META_INVERSA = re.compile(
    r"""(?is)<meta[^>]+content\s*=\s*["']([^"']+)["'][^>]*"""
    r"""(?:property|name)\s*=\s*["'](?:og:image(?::url)?|twitter:image)["']"""
)


def descargar(url: str, *, maximo_bytes: int = MAXIMO_BYTES) -> tuple[bytes, str]:
    """Descarga acotada y solo hacia fuera. Devuelve el crudo y el `Content-Type` declarado.

    El tipo se devuelve porque quien llama necesita saber si le han dado un PDF en vez de una
    página: mirarlo por la extensión de la URL no vale, que los portales del Estado sirven PDF
    desde rutas sin `.pdf`.
    """
    comprobar_destino(url)
    peticion = urllib.request.Request(url, headers={"User-Agent": NAVEGADOR})
    with urllib.request.urlopen(peticion, timeout=TIMEOUT_DESCARGA) as respuesta:  # noqa: S310
        crudo = respuesta.read(maximo_bytes + 1)
        tipo = (respuesta.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    if len(crudo) > maximo_bytes:
        raise ValueError(f"La descarga supera los {maximo_bytes // (1024 * 1024)} MB.")
    return crudo, tipo


def comprobar_destino(url: str) -> None:
    """Solo http/https y solo hacia direcciones públicas.

    La URL la escribe un editor y la petición la hace el servidor: sin esta comprobación el
    formulario sería una forma de sondear la red interna desde dentro (`http://meilisearch:7700`,
    `http://db:5432`, el metadata de la nube). No basta con mirar el texto del host — hay que
    resolverlo, porque un nombre público puede apuntar a 127.0.0.1.
    """
    partes = urlparse(url)
    if partes.scheme not in {"http", "https"}:
        raise ValueError(f"Solo se aceptan enlaces http o https, no «{partes.scheme}».")
    if not partes.hostname:
        raise ValueError("El enlace no tiene servidor.")

    try:
        resueltas = socket.getaddrinfo(partes.hostname, None)
    except socket.gaierror as exc:
        raise ValueError(f"No se pudo resolver «{partes.hostname}»: {exc}") from exc

    for familia, *_resto, direccion in resueltas:
        ip = ipaddress.ip_address(direccion[0])
        if not ip.is_global:
            raise ValueError(
                f"«{partes.hostname}» apunta a una dirección interna ({ip}). Solo se aceptan "
                f"páginas públicas."
            )


def es_pdf(crudo: bytes, content_type: str = "") -> bool:
    """¿Lo descargado es un PDF?

    Se mira **el contenido además de la cabecera**: media Perú publica sus normas como PDF desde
    URL sin extensión y con servidores que declaran `application/octet-stream`. Al revés también
    pasa —cabecera correcta y cuerpo de error en HTML—, así que basta con que lo diga cualquiera
    de los dos y luego el parser se queja si no cuadra.
    """
    return content_type.startswith("application/pdf") or crudo[:5] == b"%PDF-"


def extraer_texto(html: str) -> str:
    """HTML → texto legible, sin dependencias nuevas.

    `nh3` ya está en el proyecto para sanear el HTML del editor, y con `tags=set()` lo deja sin
    etiquetas **descartando el contenido de `<script>` y `<style>`**, que es lo que arruinaría el
    prompt. El salto previo delante de cada bloque es lo que separa las palabras.
    """
    plano = nh3.clean(BLOQUES.sub("\n<", html), tags=set(), attributes={})
    plano = re.sub(r"[ \t]+", " ", plano)
    return re.sub(r"\n\s*\n+", "\n", plano).strip()


def descargar_imagen(html: str, url_base: str) -> tuple[str, bytes] | None:
    """La `og:image` de la página, verificada y reducida. `None` si la página no declara ninguna."""
    from io import BytesIO
    from urllib.parse import urljoin

    from PIL import Image

    encontrada = IMAGEN_META.search(html) or IMAGEN_META_INVERSA.search(html)
    if not encontrada:
        return None

    url_imagen = urljoin(url_base, encontrada.group(1).strip())
    crudo, _tipo = descargar(url_imagen)

    # Que la cabecera diga «image/…» no basta: se abre de verdad antes de guardarla.
    imagen = Image.open(BytesIO(crudo))
    imagen.verify()
    imagen = Image.open(BytesIO(crudo))
    formato = (imagen.format or "JPEG").upper()

    # El mismo tope que usa el editor para sus imágenes: una portada traída de fuera no
    # tiene por qué pesar más que una subida a mano.
    ancho_maximo = settings.CONTENIDO_ANCHO_MAXIMO_PX
    if imagen.width > ancho_maximo:
        alto = round(imagen.height * ancho_maximo / imagen.width)
        imagen = imagen.resize((ancho_maximo, alto), Image.LANCZOS)

    if formato not in {"JPEG", "PNG", "WEBP"}:
        formato = "JPEG"
    if formato == "JPEG" and imagen.mode not in {"RGB", "L"}:
        imagen = imagen.convert("RGB")

    buffer = BytesIO()
    imagen.save(buffer, format=formato, quality=85)
    extension = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}[formato]
    return f"portada.{extension}", buffer.getvalue()

