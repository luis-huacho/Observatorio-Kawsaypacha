"""Lo que vuelve del modelo, antes de que nadie lo crea.

`openrouter.py` entrega un texto; aquí se convierte en algo con lo que se puede trabajar. Son las
dos comprobaciones que los tres consumidores —noticias (ADR-D7), normas (ADR-D8) y medidas
(ADR-D10)— necesitan por igual, así que viven una sola vez:

- `interpretar_json` — el JSON, tolerando que venga envuelto en un bloque de código.
- `a_html` — la red para cuando el contenido vuelve sin etiquetas pese a que el esquema pide HTML.

Ninguna de las dos es específica de un modelo ni de un origen. `interpretar_json` estaba en
`core/lectura_web.py`, que ya no describía lo que hace desde que medidas —que no descarga nada—
pasó a usarlo; se mueve aquí, que es de donde viene el JSON.
"""
import json
import re
from html import escape

#: El aviso que se deja en la bitácora cuando hubo que envolver el contenido. Es texto exacto y
#: hay pruebas que lo buscan por «sin formato»: cambiarlo es cambiar el contrato con el editor.
AVISO_SIN_FORMATO = (
    "El contenido volvió sin formato y se envolvió en párrafos: revisa la maqueta y añade "
    "subtítulos si hace falta."
)


def interpretar_json(texto: str) -> dict:
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


def a_html(texto: str, avisos: list[str]) -> str:
    """Red para cuando el modelo devuelve texto plano pese a que el esquema pide HTML.

    No es teórico y no le pasa solo a las medidas, que es donde nació esta función. Medido el
    28/08/2026 contra el API real con `deepseek/deepseek-v4-flash-0731`: el cuerpo de una noticia
    volvió en 1.063 caracteres **sin una sola etiqueta**, y de tres normas dos volvieron igual.
    Noticias y normas no tenían red, así que se guardó tal cual y **nadie se enteró**.

    Y ahí está el motivo de que esto no sea un lujo: el frontend inyecta estos campos con
    `dangerouslySetInnerHTML` y el PDF los maqueta, así que un texto sin etiquetas se pinta como un
    bloque corrido con los saltos de línea comidos — se ve mal, pero **no falla**, que es la peor
    forma de fallar. Se envuelve por párrafos y se avisa en la bitácora que ve el editor.

    Cambiar `OPENROUTER_MODELO` a uno que sí formatea quita el síntoma, no la exposición: la
    variable la puede cambiar cualquiera y el modelo de mañana no se sabe. La red va en el código.

    **La detección es deliberadamente laxa**: basta un `<` en cualquier parte para dar el texto por
    formateado, así que un Markdown que contenga uno se cuela. Endurecerla —exigir una etiqueta
    conocida al principio, por ejemplo— arriesga envolver HTML legítimo y escapárselo, que
    destruiría contenido bueno en vez de rescatar contenido malo. Se prefiere el falso negativo.
    """
    if not texto or "<" in texto:
        return texto
    parrafos = [p.strip() for p in re.split(r"\n\s*\n", texto) if p.strip()]
    avisos.append(AVISO_SIN_FORMATO)
    return "".join(f"<p>{escape(p)}</p>" for p in parrafos)
