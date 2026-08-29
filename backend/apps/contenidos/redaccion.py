"""Redacción de una noticia a partir de la URL de origen (ADR-D7).

La lógica de dominio vive aquí y no en `core/services/openrouter.py`, que es la pasarela genérica:
ésta sabe de noticias, aquélla no sabe de nada. Y lo que tampoco sabe de noticias —descargar la
página sin abrir un agujero, sacarle el texto, traerse la `og:image`— vive en
`apps/core/lectura_web.py`, compartido con normativa (ADR-D8).

**Una sola llamada al API**, y es una decisión, no una casualidad. Se manda el texto de la página
una vez y se pide de vuelta el registro entero con un esquema JSON. Encadenar llamadas —una para el
título, otra para el resumen, otra para las palabras clave— multiplicaría el coste y el tiempo por
el mismo texto de entrada, que es lo caro.

Tres trampas que este módulo cierra y que conviene no reabrir:

1. **OpenRouter enruta cada petición a un proveedor distinto**, y del mismo modelo hay proveedores
   que **no** soportan salida estructurada (`structured_outputs=false` en CoreWeave, DigitalOcean,
   DeepSeek, BaseTen y varios más). Sin `provider.require_parameters` la llamada falla una de cada
   tantas veces, y siempre por una causa distinta — el peor modo de fallar que hay.
2. **El modelo propone y se equivoca.** Todo lo que vuelve se normaliza contra el modelo de datos:
   el tipo contra sus opciones, la fecha en ISO con repliegue a hoy, y las palabras clave recortadas
   al `max_length` del `ArrayField`. Un valor fuera de rango reventaría al guardar, en el worker,
   donde el editor no lo ve.
3. **El `cuerpo` puede volver sin etiquetas** pese a que el esquema pide HTML, y entonces se pinta
   corrido sin que falle nada. Lo rescata `salida_ia.a_html`, que lo envuelve por párrafos y lo
   avisa en la bitácora. No es teórico: medido el 28/08/2026, el modelo anterior devolvió 1.063
   caracteres de texto plano para una noticia real, y como aquí no había red se guardó tal cual
   (ADR-A23).

El `cuerpo` **no se sanea aquí**: lo hace `HtmlRicoMixin.save()` al guardar, y ahí el saneador de
ADR-D2 pasa a cumplir un papel que no tenía — ser la red bajo un HTML que no escribió una persona.
"""
from dataclasses import dataclass, field
from datetime import date

from apps.core import lectura_web
from apps.core.services import openrouter, salida_ia

#: Lo que se le manda al modelo. Recortar aquí es lo que mantiene barata la llamada.
MAXIMO_CARACTERES = 24_000

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
    crudo, _tipo = lectura_web.descargar(url)
    html = crudo.decode("utf-8", errors="replace")
    texto = lectura_web.extraer_texto(html)
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

    datos = salida_ia.interpretar_json(respuesta.texto)
    redaccion = _normalizar(datos, modelo=respuesta.modelo, costo=respuesta.costo)

    if con_imagen:
        try:
            redaccion.imagen = lectura_web.descargar_imagen(html, url)
        except Exception as exc:  # noqa: BLE001 — la portada es un extra, no la operación
            redaccion.avisos.append(f"No se pudo traer la imagen de portada: {exc}")

    return redaccion


# --- Internos ---------------------------------------------------------------


def _normalizar(datos: dict, *, modelo: str, costo: float | None) -> Redaccion:
    from apps.contenidos.models import Noticia

    avisos: list[str] = []
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
        cuerpo=salida_ia.a_html(str(datos.get("cuerpo") or "").strip(), avisos),
        tipo=tipo if tipo in tipos else Noticia.Tipo.NOTICIA,
        autor=str(datos.get("autor") or "").strip()[:150],
        fecha=_a_fecha(datos.get("fecha")),
        palabras_clave=claves[:8],
        imagen_titulo=str(datos.get("imagen_titulo") or "").strip()[:300],
        modelo=modelo,
        costo=costo,
        avisos=avisos,
    )


def _a_fecha(valor) -> date:
    """ISO, y si no se puede, hoy. Una fecha inventada es peor que una fecha por defecto."""
    try:
        return date.fromisoformat(str(valor)[:10])
    except (TypeError, ValueError):
        return date.today()
