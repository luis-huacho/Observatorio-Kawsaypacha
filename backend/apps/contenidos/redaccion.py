"""Redacción de una noticia a partir de la URL de origen (ADR-D7).

La lógica de dominio vive aquí y no en `core/services/openrouter.py`, que es la pasarela genérica:
ésta sabe de noticias, aquélla no sabe de nada.

**Una sola llamada al API**, y es una decisión, no una casualidad. Se manda el texto de la página
una vez y se pide de vuelta el registro entero con un esquema JSON. Encadenar llamadas —una para el
título, otra para el resumen, otra para las palabras clave— multiplicaría el coste y el tiempo por
el mismo texto de entrada, que es lo caro.

Tres trampas que este módulo cierra y que conviene no reabrir:

1. **OpenRouter enruta cada petición a un proveedor distinto**, y del mismo modelo hay proveedores
   que **no** soportan salida estructurada (`structured_outputs=false` en CoreWeave, DigitalOcean,
   DeepSeek, BaseTen y varios más). Sin `provider.require_parameters` la llamada falla una de cada
   tantas veces, y siempre por una causa distinta — el peor modo de fallar que hay.
2. **La descarga de la URL es una petición que hace el servidor con un destino que escribe un
   usuario.** Se limita a `http`/`https` y se rechazan los destinos internos: sin eso, cualquier
   cuenta de editor podría sondear la red privada (`http://meilisearch:7700`) desde dentro.
3. **El modelo propone y se equivoca.** Todo lo que vuelve se normaliza contra el modelo de datos:
   el tipo contra sus opciones, la fecha en ISO con repliegue a hoy, y las palabras clave recortadas
   al `max_length` del `ArrayField`. Un valor fuera de rango reventaría al guardar, en el worker,
   donde el editor no lo ve.

El `cuerpo` **no se sanea aquí**: lo hace `HtmlRicoMixin.save()` al guardar, y ahí el saneador de
ADR-D2 pasa a cumplir un papel que no tenía — ser la red bajo un HTML que no escribió una persona.
"""
import ipaddress
import json
import re
import socket
import urllib.request
from dataclasses import dataclass, field
from datetime import date
from urllib.parse import urlparse

import nh3
from django.conf import settings

from apps.core.services import openrouter

#: Tope de descarga. Un artículo son decenas de KB; más que esto es una página que no interesa.
MAXIMO_BYTES = 5 * 1024 * 1024
TIMEOUT_DESCARGA = 20
#: Lo que se le manda al modelo. Recortar aquí es lo que mantiene barata la llamada.
MAXIMO_CARACTERES = 24_000
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

ESQUEMA = {
    "name": "noticia",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["titulo", "bajada", "cuerpo", "tipo", "autor", "fecha", "palabras_clave",
                     "imagen_titulo"],
        "properties": {
            "titulo": {"type": "string", "description": "Titular en español, máximo 250 caracteres."},
            "bajada": {
                "type": "string",
                "description": "Resumen de 1 o 2 frases, máximo 500 caracteres. Sin repetir el titular.",
            },
            "cuerpo": {
                "type": "string",
                "description": (
                    "Cuerpo en HTML simple: solo <p>, <h2>, <h3>, <ul>, <ol>, <li>, <strong>, "
                    "<em> y <blockquote>. Sin <html>, <head>, <script> ni atributos de estilo."
                ),
            },
            "tipo": {"type": "string", "enum": ["noticia", "articulo", "opinion"]},
            "autor": {"type": "string", "description": "Firma del artículo, o cadena vacía."},
            "fecha": {"type": "string", "description": "Fecha de publicación en formato AAAA-MM-DD."},
            "palabras_clave": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Entre 3 y 6 términos del dominio de GRD/ACC, máximo 60 caracteres.",
            },
            "imagen_titulo": {
                "type": "string",
                "description": "Pie para la imagen principal, con su crédito si aparece. Puede ir vacío.",
            },
        },
    },
}

INSTRUCCIONES = (
    "Eres editor del Observatorio Kallpachakuy de PREDES, sobre gestión del riesgo de desastres y "
    "adaptación al cambio climático en la región Cusco, Perú. A partir del texto de una página web "
    "que se te entrega, redacta la ficha de la noticia en español peruano, con la terminología del "
    "dominio (GRD, ACC, ubigeo, centro poblado, EVAR). "
    "No inventes datos: si un campo no se puede deducir del texto, déjalo vacío. "
    "El cuerpo debe resumir y reorganizar la información, no copiarla literalmente. "
    "Clasifica como 'opinion' solo si el texto está firmado como columna o editorial, y como "
    "'articulo' si es un análisis extenso; en cualquier otro caso, 'noticia'."
)


@dataclass
class Redaccion:
    """Lo que la IA propuso, ya normalizado contra el modelo de datos."""

    titulo: str
    bajada: str
    cuerpo: str
    tipo: str
    autor: str
    fecha: date
    palabras_clave: list[str]
    imagen_titulo: str
    modelo: str = ""
    costo: float | None = None
    imagen: tuple[str, bytes] | None = None
    avisos: list[str] = field(default_factory=list)


def redactar(url: str, *, con_imagen: bool = True) -> Redaccion:
    """Descarga la URL y devuelve la ficha propuesta. Lanza si algo impide continuar."""
    html = _descargar(url).decode("utf-8", errors="replace")
    texto = extraer_texto(html)
    if len(texto) < 200:
        raise ValueError(
            "La página no tiene texto legible. Puede ser un muro de pago o cargarse con JavaScript; "
            "en ese caso hay que redactar la noticia a mano."
        )

    respuesta = openrouter.completar(
        [
            {"role": "system", "content": INSTRUCCIONES},
            {"role": "user", "content": f"URL: {url}\n\n{texto[:MAXIMO_CARACTERES]}"},
        ],
        # Extraer campos de un texto no mejora razonando y sí se paga. `None` no valdría: el modelo
        # por defecto razona salvo que se le diga que no.
        razonamiento=False,
        response_format={"type": "json_schema", "json_schema": ESQUEMA},
        # Sin esto OpenRouter puede enrutar a un proveedor sin salida estructurada y la llamada
        # falla de forma intermitente. Ver el encabezado del módulo.
        extra_body={"provider": {"require_parameters": True}},
        etiqueta=f"noticia desde {url}",
    )

    datos = _interpretar(respuesta.texto)
    redaccion = _normalizar(datos, modelo=respuesta.modelo, costo=respuesta.costo)

    if con_imagen:
        try:
            redaccion.imagen = descargar_imagen(html, url)
        except Exception as exc:  # noqa: BLE001 — la portada es un extra, no la operación
            redaccion.avisos.append(f"No se pudo traer la imagen de portada: {exc}")

    return redaccion


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
    crudo = _descargar(url_imagen)

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


# --- Internos ---------------------------------------------------------------


def _descargar(url: str) -> bytes:
    """Descarga acotada, y solo hacia fuera."""
    _comprobar_destino(url)
    peticion = urllib.request.Request(url, headers={"User-Agent": NAVEGADOR})
    with urllib.request.urlopen(peticion, timeout=TIMEOUT_DESCARGA) as respuesta:  # noqa: S310
        crudo = respuesta.read(MAXIMO_BYTES + 1)
    if len(crudo) > MAXIMO_BYTES:
        raise ValueError(f"La descarga supera los {MAXIMO_BYTES // (1024 * 1024)} MB.")
    return crudo


def _comprobar_destino(url: str) -> None:
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


def _interpretar(texto: str) -> dict:
    """El JSON del modelo, tolerando que lo envuelva en un bloque de código."""
    limpio = texto.strip()
    if limpio.startswith("```"):
        limpio = re.sub(r"^```[a-z]*\n?|\n?```$", "", limpio).strip()
    try:
        datos = json.loads(limpio)
    except json.JSONDecodeError as exc:
        raise ValueError(f"La IA no devolvió un JSON válido: {exc}") from exc
    if not isinstance(datos, dict):
        raise ValueError("La IA devolvió algo que no es una ficha.")
    return datos


def _normalizar(datos: dict, *, modelo: str, costo: float | None) -> Redaccion:
    from apps.contenidos.models import Noticia

    tipos = {opcion for opcion, _ in Noticia.Tipo.choices}
    tipo = str(datos.get("tipo") or "").strip()

    claves = [
        str(palabra).strip()[:60]
        for palabra in (datos.get("palabras_clave") or [])
        if str(palabra).strip()
    ]

    return Redaccion(
        titulo=str(datos.get("titulo") or "").strip()[:250],
        bajada=str(datos.get("bajada") or "").strip()[:500],
        cuerpo=str(datos.get("cuerpo") or "").strip(),
        tipo=tipo if tipo in tipos else Noticia.Tipo.NOTICIA,
        autor=str(datos.get("autor") or "").strip()[:150],
        fecha=_a_fecha(datos.get("fecha")),
        palabras_clave=claves[:8],
        imagen_titulo=str(datos.get("imagen_titulo") or "").strip()[:300],
        modelo=modelo,
        costo=costo,
    )


def _a_fecha(valor) -> date:
    """ISO, y si no se puede, hoy. Una fecha inventada es peor que una fecha por defecto."""
    try:
        return date.fromisoformat(str(valor)[:10])
    except (TypeError, ValueError):
        return date.today()
