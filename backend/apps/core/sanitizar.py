"""Saneamiento del HTML de CKEditor 5 (ADR-D2).

Se sanea **al guardar**, no al mostrar, por dos razones:

1. El frontend inyecta con `dangerouslySetInnerHTML` y no puede ser la última línea de defensa.
2. Saneando al guardar, lo que hay en la base es ya seguro: cualquier consumidor futuro —el PDF,
   el índice de Meilisearch, una app— hereda la garantía sin repetir el trabajo.

La lista blanca incluye las clases propias de CKEditor (`figure.image`, `figure.table`,
`.image-style-side`, `.text-big`), porque el frontend las estila en `.contenido-rico` y quitarlas
rompería la maqueta del contenido ya publicado.
"""
import re

import nh3

ETIQUETAS = {
    "p", "br", "strong", "b", "em", "i", "u", "s", "sub", "sup",
    "h2", "h3", "h4",
    "ul", "ol", "li",
    "blockquote", "hr",
    "a",
    "figure", "figcaption", "img",
    "table", "thead", "tbody", "tfoot", "tr", "th", "td",
    # CKEditor envuelve los videos en <figure class="media"><oembed url="…">. El frontend lo
    # convierte a iframe al pintar (`ContenidoRico`), así que la etiqueta tiene que sobrevivir
    # al saneado o el video desaparece sin dejar rastro.
    "oembed",
    "div", "span",
}

ATRIBUTOS = {
    # Sin `rel`: lo pone nh3 con `link_rel`, y declararlo aquí a la vez es un error.
    "a": {"href", "title", "target"},
    "img": {"src", "alt", "width", "height"},
    "oembed": {"url"},
    "figure": {"class"},
    "figcaption": {"class"},
    "span": {"class"},
    "div": {"class"},
    "table": {"class"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan", "scope"},
    "p": {"class"},
}

ESQUEMAS_URL = {"http", "https", "mailto", "tel"}


def sanear(html: str | None) -> str:
    """Devuelve el HTML con solo lo permitido. Cadena vacía si no hay contenido."""
    if not html:
        return ""
    limpio = nh3.clean(
        html,
        tags=ETIQUETAS,
        attributes=ATRIBUTOS,
        url_schemes=ESQUEMAS_URL,
        link_rel="noopener noreferrer",
        strip_comments=True,
    )
    # nh3 deja los párrafos vacíos que CKEditor añade al final al pulsar Enter; en el PDF y en
    # la ficha se ven como huecos sin explicación.
    return re.sub(r"(<p>(\s|&nbsp;|<br\s*/?>)*</p>\s*)+$", "", limpio).strip()


def a_texto_plano(html: str | None) -> str:
    """Texto plano para indexar en Meilisearch y para los resúmenes.

    Buscar «qochas» no puede fallar porque la palabra estuviera dentro de un `<strong>`.

    Antes de quitar el markup se **inserta un espacio en los límites de bloque**: sin eso,
    `</p><h2>` deja las dos palabras pegadas ("PampallactaCómo") y esa palabra inventada no
    coincide con ninguna búsqueda real.
    """
    if not html:
        return ""
    con_separadores = re.sub(
        r"</(p|h2|h3|h4|li|td|th|tr|div|figcaption|blockquote)\s*>|<br\s*/?>",
        " ",
        html,
        flags=re.IGNORECASE,
    )
    texto = nh3.clean(con_separadores, tags=set(), attributes={})
    return re.sub(r"\s+", " ", texto).strip()
