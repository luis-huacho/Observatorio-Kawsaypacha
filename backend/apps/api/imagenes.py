"""Resolución de la portada e imagen por defecto del contenido editorial.

La regla vive en el servidor a propósito (spec 01/02): el API entrega `imagen_portada` ya
resuelta y ningún cliente —web, PDF o una futura app— reimplementa la lógica. Cambiar la
ilustración institucional es tocar un solo sitio.

Es el puerto de `prototype/src/lib/imagenes.ts`, que resolvía lo mismo en el navegador.
"""
from django.conf import settings

# Las ilustraciones son SVG de 600×400 construidas con el lenguaje visual del favicon; pesan
# unos pocos KB y escalan sin pérdida. Viven en el frontend porque las sirve el dominio público
# junto con el resto de estáticos de la SPA.
BASE_DEFAULT = "/img/default"
PIE_POR_DEFECTO = "Ilustración del Observatorio Kallpachakuy"


def url_absoluta(archivo) -> str | None:
    """URL completa de un FileField. Absoluta porque la SPA vive en otro dominio (ADR-A14)."""
    if not archivo:
        return None
    url = archivo.url
    if url.startswith(("http://", "https://")):
        return url
    return f"{settings.BACKEND_URL.rstrip('/')}{url}"


def portada(archivo, clave_defecto: str) -> str:
    """La imagen propia si existe; si no, la ilustración institucional de su tipo.

    El default se elige por el **tipo de contenido**, no por la pieza: es justo lo que lo hace
    un default y no una decisión editorial artículo por artículo.
    """
    return url_absoluta(archivo) or f"{BASE_DEFAULT}/{clave_defecto}.svg"


def pie(propio: str | None, es_propia: bool) -> str:
    """Pie de imagen.

    Cuando la portada es la ilustración institucional, el pie genérico dice que es una
    ilustración: no debe hacer pasar el gráfico por una fotografía de un hecho real.
    """
    if propio:
        return propio
    return "" if es_propia else PIE_POR_DEFECTO


#: Los tipos de noticia que tienen ilustración propia en `frontend/public/img/default/`.
#:
#: Se declara aquí porque el backend **no puede comprobarlo**: los SVG viven en el bundle del
#: frontend y el contenedor solo monta `./backend`. Una prueba fija que todo `Noticia.Tipo` esté en
#: este conjunto, que es el olvido probable; el archivo ausente lo caza el e2e.
CLAVES_NOTICIA = frozenset(
    {"noticia", "articulo", "opinion", "publicacion", "base_datos"}
)


def clave_noticia(tipo: str | None) -> str:
    """La noticia se ilustra por su tipo de contenido.

    Si el tipo no tiene ilustración —dato viejo, o una opción nueva cuyo SVG no se dibujó— cae en
    la reserva `noticia`, que es preferible a un 404 de imagen. Mismo criterio que `clave_medida`.
    """
    return tipo if tipo in CLAVES_NOTICIA else "noticia"


def clave_medida(slug_peligro: str | None) -> str:
    """La medida se ilustra por su peligro, que es el eje con el que se explora la sección.

    Si el peligro no casa con el catálogo —dato viejo o peligro nuevo— cae en la reserva
    `medida`, que es preferible a un 404 de imagen.
    """
    from apps.peligros.catalogo import SLUGS_PELIGRO

    return f"peligro-{slug_peligro}" if slug_peligro in SLUGS_PELIGRO else "medida"
