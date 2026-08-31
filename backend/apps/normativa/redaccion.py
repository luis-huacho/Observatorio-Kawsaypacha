"""Redacción de una norma a partir del enlace a su publicación oficial (ADR-D8).

Hermana de `apps/contenidos/redaccion.py`: la mitad genérica —descarga acotada, guarda anti-SSRF,
texto legible, `og:image`— vive en `apps/core/lectura_web.py`, y aquí queda lo que solo vale para
una norma: el esquema JSON, las instrucciones y la normalización contra `Norma`.

**Dos ramas de entrada y una sola llamada al API en las dos.** La diferencia con noticias es que
buena parte de las normas peruanas se publica **como PDF** —El Peruano, gob.pe— y el extractor de
HTML le pasaría basura al modelo. Cuando lo descargado es un PDF se manda el archivo dentro del
mismo mensaje y lo parsea OpenRouter con su plugin `file-parser`; sigue siendo una petición.

Cinco trampas que este módulo cierra:

1. **OpenRouter enruta cada petición a un proveedor distinto**, y del mismo modelo hay proveedores
   sin salida estructurada. Sin `provider.require_parameters` la llamada falla una de cada tantas
   veces y siempre por una causa distinta.
2. **Un PDF escaneado no tiene capa de texto**, y `pdf-text` devuelve nada sin quejarse: el modelo
   contesta una ficha en blanco y, sin la guarda de abajo, se guardaría vacía **con el candado
   cerrado**. Se detecta por el título vacío y se dice qué hacer.
3. **El adjunto no puede acabar en el registro de IA.** Un PDF en base64 son megabytes por llamada
   y `ia-AAAA-MM-DD.txt` es un archivo diario en modo añadir y sin rotación; `openrouter.registrar`
   lo elide (`_aligerar`).
4. **El modelo propone y se equivoca.** Todo lo que vuelve se normaliza contra `Norma`: tipo,
   ámbito y estado de vigencia contra sus opciones, la fecha en ISO con repliegue a hoy, y los
   textos recortados a su `max_length`. Un valor fuera de rango reventaría al guardar, en el
   worker, donde el editor no lo ve.
5. **El `contenido` puede volver sin etiquetas** pese a que el esquema pide HTML, y entonces se
   pinta corrido sin que falle nada. Lo rescata `salida_ia.a_html`, que lo envuelve por párrafos y
   lo avisa en la bitácora. Aquí es donde más se vio: medido el 28/08/2026, de tres normas el
   modelo anterior devolvió dos en texto plano —una de ellas la del PDF— y la tercera, con la misma
   URL que una de esas dos, sí formateada (ADR-A23).

El `contenido` **no se sanea aquí**: lo hace `HtmlRicoMixin.save()` al guardar, que es donde el
saneador de ADR-D2 hace de red bajo un HTML que no escribió una persona.
"""
import base64
from dataclasses import dataclass, field
from datetime import date
from urllib.parse import unquote, urlparse

from django.conf import settings

from apps.core import lectura_web
from apps.core.services import openrouter, salida_ia

#: Lo que se le manda al modelo en la rama HTML. Recortar aquí es lo que mantiene barata la llamada.
#: Más generoso que en noticias: una norma trae articulado y el corte se nota antes.
MAXIMO_CARACTERES = 40_000
#: Tope propio para el PDF. El base64 crece un tercio sobre el original, y lo que el parser extraiga
#: se paga como tokens de entrada: un boletín entero del diario oficial no es lo que se quiere leer.
MAXIMO_BYTES_PDF = 8 * 1024 * 1024


def _esquema() -> dict:
    """El esquema se arma al vuelo, porque el `enum` de entidades sale del catálogo vivo.

    Escribir la lista a mano aquí obligaría a tocar el prompt cada vez que PREDES da de alta una
    institución desde el admin, y las dos copias se desincronizarían el primer día. Es el mismo
    mecanismo que usa `apps/medidas/redaccion.py` con los nueve peligros.
    """
    from apps.normativa.models import EntidadEmisora

    entidades = list(EntidadEmisora.objects.values_list("slug", flat=True))

    return {
        "name": "norma",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["titulo", "numero", "tipo", "ambito", "entidad_emisora", "fecha", "resumen",
                         "contenido", "palabras_clave", "estado_vigencia", "imagen_titulo"],
            "properties": {
                "titulo": {
                    "type": "string",
                    "description": (
                        "Nombre oficial de la norma, máximo 300 caracteres. Cadena vacía si el "
                        "documento no permite identificarla."
                    ),
                },
                "numero": {
                    "type": "string",
                    "description": (
                        'Identificador corto, p. ej. "DS 048-2011-PCM", "Ley 29664", '
                        '"Ordenanza Regional 123-2020-CR/GRC.CUSCO". Vacío si no aparece.'
                    ),
                },
                "tipo": {"type": "string", "enum": ["Ley", "DS", "RM", "RJ", "Ordenanza"]},
                "ambito": {
                    "type": "string",
                    "enum": ["nacional", "regional", "local"],
                    "description": (
                        "Nivel de gobierno de la entidad que la emite: Congreso, PCM o un ministerio "
                        "son 'nacional'; un gobierno regional, 'regional'; una municipalidad, 'local'."
                    ),
                },
                "entidad_emisora": {
                    "type": "string",
                    "enum": [*entidades, ""],
                    "description": (
                        "Institución que dicta la norma, elegida de la lista. Cadena vacía si la "
                        "que la emite no está en ella: no elijas la más parecida ni la del mismo "
                        "nivel de gobierno."
                    ),
                },
                "fecha": {
                    "type": "string",
                    "description": "Fecha de publicación oficial en formato AAAA-MM-DD.",
                },
                "resumen": {
                    "type": "string",
                    "description": (
                        "Sumilla en prosa de qué dispone la norma y a quién obliga, máximo 700 "
                        "caracteres. Sin copiar el articulado."
                    ),
                },
                "contenido": {
                    "type": "string",
                    "description": (
                        "Análisis desarrollado en HTML simple: solo <p>, <h2>, <h3>, <ul>, <ol>, "
                        "<li>, <strong>, <em> y <blockquote>. Organiza el contenido de la norma por "
                        "temas —objeto, alcance, obligaciones, plazos— en vez de transcribir "
                        "artículos. Sin <html>, <head>, <script> ni atributos de estilo."
                    ),
                },
                "palabras_clave": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Entre 3 y 6 términos del dominio de GRD/ACC (p. ej. SINAGERD, EVAR, "
                        "competencias municipales), máximo 60 caracteres cada uno."
                    ),
                },
                "estado_vigencia": {
                    "type": "string",
                    "enum": ["vigente", "derogada", "modificada", ""],
                    "description": (
                        "Solo si el propio documento lo dice. Cadena vacía si no consta: es preferible "
                        "no declarar la vigencia a declararla mal."
                    ),
                },
                "imagen_titulo": {
                    "type": "string",
                    "description": "Pie para la imagen de portada, con su crédito si aparece. Puede ir vacío.",
                },
            },
        },
    }

INSTRUCCIONES = (
    "Eres editor del Observatorio Kallpachakuy de PREDES, sobre gestión del riesgo de desastres y "
    "adaptación al cambio climático en la región Cusco, Perú. A partir del documento que se te "
    "entrega —la publicación oficial de una norma— completa su ficha en español peruano, con la "
    "terminología del dominio (GRD, ACC, SINAGERD, ubigeo, centro poblado, EVAR). "
    "No inventes datos: si un campo no se puede deducir del documento, déjalo vacío. En particular, "
    "no deduzcas la vigencia del paso del tiempo ni de lo que sepas por otras fuentes. "
    "El análisis debe explicar qué dispone la norma y a quién obliga, no transcribir el articulado."
)


@dataclass
class Redaccion:
    """Lo que la IA propuso, ya normalizado contra `Norma`."""

    titulo: str
    numero: str
    tipo: str
    ambito: str
    entidad_emisora: object | None
    fecha: date
    resumen: str
    contenido: str
    palabras_clave: list[str]
    estado_vigencia: str
    imagen_titulo: str
    modelo: str = ""
    costo: float | None = None
    imagen: tuple[str, bytes] | None = None
    avisos: list[str] = field(default_factory=list)


def redactar(url: str, *, con_imagen: bool = True) -> Redaccion:
    """Lee la publicación oficial y devuelve la ficha propuesta. Lanza si algo impide continuar."""
    crudo, content_type = lectura_web.descargar(url, maximo_bytes=MAXIMO_BYTES_PDF)
    es_pdf = lectura_web.es_pdf(crudo, content_type)

    if es_pdf:
        html = ""
        mensaje_usuario, extra_plugins = _entrada_pdf(url, crudo)
        etiqueta = f"norma (pdf) desde {url}"
    else:
        html = crudo.decode("utf-8", errors="replace")
        mensaje_usuario, extra_plugins = _entrada_html(url, html), {}
        etiqueta = f"norma desde {url}"

    respuesta = openrouter.completar(
        [
            {"role": "system", "content": INSTRUCCIONES},
            mensaje_usuario,
        ],
        # Extraer campos de un documento no mejora razonando y sí se paga. `None` no valdría: el
        # modelo por defecto razona salvo que se le diga que no.
        razonamiento=False,
        response_format={"type": "json_schema", "json_schema": _esquema()},
        # `require_parameters` cierra el fallo intermitente del encabezado; `plugins` solo aparece
        # en la rama PDF, y lo resuelve OpenRouter antes de elegir proveedor.
        extra_body={"provider": {"require_parameters": True}, **extra_plugins},
        etiqueta=etiqueta,
    )

    datos = salida_ia.interpretar_json(respuesta.texto)
    if not str(datos.get("titulo") or "").strip():
        raise ValueError(_MOTIVO_SIN_TEXTO if es_pdf else _MOTIVO_SIN_FICHA)

    redaccion = _normalizar(datos, modelo=respuesta.modelo, costo=respuesta.costo)

    # Un PDF no trae `og:image`, así que la portada solo se busca en la rama HTML.
    if con_imagen and html:
        try:
            redaccion.imagen = lectura_web.descargar_imagen(html, url)
        except Exception as exc:  # noqa: BLE001 — la portada es un extra, no la operación
            redaccion.avisos.append(f"No se pudo traer la imagen de portada: {exc}")

    return redaccion


# --- Internos ---------------------------------------------------------------

_MOTIVO_SIN_TEXTO = (
    "El PDF no tiene capa de texto: es casi seguro un escaneo, y el motor de lectura configurado "
    "(OPENROUTER_PDF_ENGINE=pdf-text) solo lee texto. Puede resolverlo el administrador de la "
    "plataforma cambiando esa variable a «mistral-ocr», que sí reconoce imágenes y se cobra por "
    "página. Mientras tanto, pega el enlace a la versión web de la norma o redáctala a mano."
)
_MOTIVO_SIN_FICHA = (
    "La página no permitió identificar la norma. Puede ser un índice, un muro de pago o una página "
    "que se carga con JavaScript; en ese caso hay que pegar el enlace al documento o redactarla "
    "a mano."
)


def _entrada_html(url: str, html: str) -> dict:
    texto = lectura_web.extraer_texto(html)
    if len(texto) < 200:
        raise ValueError(
            "La página no tiene texto legible. Puede ser un muro de pago o cargarse con "
            "JavaScript; en ese caso hay que redactar la norma a mano."
        )
    return {"role": "user", "content": f"URL: {url}\n\n{texto[:MAXIMO_CARACTERES]}"}


def _entrada_pdf(url: str, crudo: bytes) -> tuple[dict, dict]:
    """El PDF viaja dentro del mensaje y lo parsea OpenRouter. Sigue siendo **una** petición.

    Se manda como `data:` URI en base64, que es el único formato que acepta la API de chat para un
    adjunto. Ese base64 **no** llega al registro en disco: `openrouter.registrar` lo elide.
    """
    mensaje = {
        "role": "user",
        "content": [
            {"type": "text", "text": f"URL: {url}"},
            {
                "type": "file",
                "file": {
                    "filename": _nombre_pdf(url),
                    "file_data": "data:application/pdf;base64,"
                    + base64.b64encode(crudo).decode("ascii"),
                },
            },
        ],
    }
    plugins = {
        "plugins": [{"id": "file-parser", "pdf": {"engine": settings.OPENROUTER_PDF_ENGINE}}]
    }
    return mensaje, plugins


def _nombre_pdf(url: str) -> str:
    """El nombre del archivo, solo para que el modelo lo vea; nunca toca el disco."""
    ultimo = unquote(urlparse(url).path.rsplit("/", 1)[-1])
    return ultimo[:120] if ultimo.lower().endswith(".pdf") else "norma.pdf"


def _normalizar(datos: dict, *, modelo: str, costo: float | None) -> Redaccion:
    from apps.normativa.models import Norma

    avisos: list[str] = []
    tipos = {opcion for opcion, _ in Norma.Tipo.choices}
    ambitos = {opcion for opcion, _ in Norma.Ambito.choices}
    vigencias = {"vigente", "derogada", "modificada"}

    tipo = str(datos.get("tipo") or "").strip()
    ambito = str(datos.get("ambito") or "").strip().lower()
    vigencia = str(datos.get("estado_vigencia") or "").strip().lower()

    claves = [
        str(palabra).strip()[:60]
        for palabra in (datos.get("palabras_clave") or [])
        if str(palabra).strip()
    ]

    return Redaccion(
        titulo=str(datos.get("titulo") or "").strip()[:300],
        numero=str(datos.get("numero") or "").strip()[:80],
        # Sin repliegue inventado: si el tipo o el ámbito no cuadran con el catálogo se dejan
        # vacíos, que es lo que el modelo permite y lo que hace que el editor lo vea y lo elija.
        tipo=tipo if tipo in tipos else "",
        ambito=ambito if ambito in ambitos else "",
        entidad_emisora=_resolver_entidad(datos.get("entidad_emisora"), avisos),
        fecha=_a_fecha(datos.get("fecha")),
        resumen=str(datos.get("resumen") or "").strip()[:700],
        contenido=salida_ia.a_html(str(datos.get("contenido") or "").strip(), avisos),
        palabras_clave=claves[:8],
        estado_vigencia=vigencia if vigencia in vigencias else "",
        imagen_titulo=str(datos.get("imagen_titulo") or "").strip()[:300],
        modelo=modelo,
        costo=costo,
        avisos=avisos,
    )


def _resolver_entidad(slug, avisos: list[str]):
    """La entidad se elige del catálogo o se deja vacía; nunca se crea desde aquí.

    El `enum` del esquema ya la restringe, pero la salida estructurada falla de vez en cuando y un
    slug inventado reventaría al guardar **dentro del worker**, donde el editor no lo ve. Crear la
    entidad que falta tampoco vale: acabaría con «MINAM» y «Ministerio del Ambiente» como dos filas
    distintas, que es justo lo que un catálogo existe para evitar.
    """
    from apps.normativa.models import EntidadEmisora

    slug = str(slug or "").strip()
    if not slug:
        return None
    entidad = EntidadEmisora.objects.filter(slug=slug).first()
    if entidad is None:
        avisos.append(
            f"«{slug}» no está en el catálogo de entidades emisoras: elígela a mano, o créala "
            f"desde «Normativa - Entidades emisoras»."
        )
    return entidad


def _a_fecha(valor) -> date:
    """ISO, y si no se puede, hoy. Una fecha inventada es peor que una fecha por defecto."""
    try:
        return date.fromisoformat(str(valor)[:10])
    except (TypeError, ValueError):
        return date.today()
