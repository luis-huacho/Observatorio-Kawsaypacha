"""El HTML de la SPA con las metas de cada ficha ya puestas, y el sitemap.

**El problema que resuelve.** La SPA es un bundle de Vite servido por nginx con
`try_files $uri /index.html`, así que **toda URL devolvía el mismo `<head>`**: un `<title>`
genérico, una `description` genérica y ni una sola meta Open Graph. Consecuencia medida en
producción: compartir una noticia por WhatsApp se previsualizaba igual que compartir la portada
—mismo texto, sin imagen— y Google indexaba todas las páginas con el mismo título.

**Por qué en el servidor.** Google ejecuta JavaScript, así que poner las metas desde React
arreglaría a Google. Pero los rastreadores de WhatsApp, Facebook y LinkedIn **no ejecutan nada**:
leen el HTML tal cual llega. Y esos son justamente los de compartir.

**Y por qué para todo el mundo, no solo para los bots.** Detectar el `User-Agent` y servir HTML
distinto a los rastreadores es *cloaking*: Google lo penaliza explícitamente, y además duplica el
camino que hay que mantener —el que se prueba y el que se sirve dejan de ser el mismo—. Aquí todos
reciben la misma respuesta.

**Se inyecta sobre el `index.html` compilado**, el mismo que sirve nginx, leído del volumen
`web_dist`. Generar un HTML propio desde una plantilla parecería más limpio y sería una trampa:
los nombres de los bundles llevan hash y cambian en cada build, así que la plantilla se quedaría
apuntando a archivos que ya no existen y **la SPA no arrancaría**.

Si el backend se cae, nginx repliega estas rutas al `index.html` de siempre (`error_page 502`): la
ficha sigue abriendo, solo pierde las metas.

Lo que se publica para que descubra el sitio una **máquina** —`/robots.txt` y el catálogo de API—
está al lado, en `descubrimiento.py`: mismo dominio y mismo motivo (la URL del sitio va dentro del
documento), pero otro destinatario.
"""
import html
import re
from pathlib import Path

from django.conf import settings
from django.http import Http404, HttpResponse
from django.utils.html import escape
from django.views.decorators.cache import cache_control

#: Dónde está el `index.html` compilado. Es el volumen `web_dist` que llena el servicio `frontend`
#: y que lee nginx; el backend lo monta de solo lectura (ver `compose.yaml`).
RAIZ_SPA = Path(settings.SPA_DIST_DIR)

#: Imagen de respaldo cuando la ficha no tiene portada. **Tiene que ser PNG o JPG**: las
#: ilustraciones por defecto del sitio son SVG de 600×400 y ni Facebook ni WhatsApp los renderizan.
OG_POR_DEFECTO = "/img/compartir.png"

DESCRIPCION_SITIO = (
    "Observatorio Kallpachakuy — monitoreo de gestión del riesgo de desastres y adaptación al "
    "cambio climático en Cusco, Perú."
)

#: Marca dónde termina el `<head>`, que es donde se inyecta.
FIN_HEAD = re.compile(r"</head>", re.IGNORECASE)


def _sitio() -> str:
    return settings.SITE_URL.rstrip("/")


# --- Qué se sabe de cada tipo de ficha --------------------------------------
#
# Lista blanca explícita, como la de `MODELOS_CON_IA`: el tipo llega desde la URL y no puede elegir
# qué modelo se consulta. Cada entrada dice cómo encontrar la ficha y cómo describirla.


def _noticia(slug):
    from apps.api.imagenes import url_absoluta
    from apps.contenidos.models import Noticia

    n = Noticia.objects.filter(slug=slug, estado="publicado").first()
    if not n:
        return None
    return {
        "titulo": n.titulo,
        "descripcion": n.bajada,
        # Sin portada propia se deja `None`: la ilustración por defecto del sitio es un SVG y
        # ni Facebook ni WhatsApp los renderizan. El respaldo PNG lo pone `_con_metas`.
        "imagen": url_absoluta(n.imagen_portada),
        "tipo_og": "article",
    }


def _norma(slug):
    from apps.api.imagenes import url_absoluta
    from apps.normativa.models import Norma

    n = Norma.objects.filter(slug=slug, estado="publicado").first()
    if not n:
        return None
    # El número identifica la norma mucho mejor que un título de 300 caracteres, así que encabeza
    # el titular compartido. Es la misma razón por la que el listado lo pinta de chip.
    titulo = f"{n.numero} — {n.titulo}" if n.numero else n.titulo
    return {
        "titulo": titulo,
        "descripcion": n.resumen,
        "imagen": url_absoluta(n.imagen_portada),
        "tipo_og": "article",
    }


def _medida(slug):
    from apps.api.imagenes import url_absoluta
    from apps.medidas.models import Medida

    m = Medida.objects.filter(slug=slug, estado="publicado").first()
    if not m:
        return None
    return {
        "titulo": m.titulo,
        "descripcion": m.resumen_corto,
        "imagen": url_absoluta(m.imagen_portada),
        "tipo_og": "article",
    }


def _centro_poblado(codigo):
    from apps.territorio.models import CentroPoblado

    cp = CentroPoblado.objects.filter(codigo=codigo).select_related("distrito").first()
    if not cp:
        return None
    lugar = f"{cp.nombre}, {cp.distrito.nombre}" if cp.distrito_id else cp.nombre
    return {
        "titulo": f"{cp.nombre} — exposición a peligros",
        "descripcion": f"Niveles de exposición a peligros del centro poblado de {lugar} (Cusco).",
        "imagen": None,
        "tipo_og": "website",
    }


#: `tipo de la URL -> (resolver, ruta pública)`. La ruta se usa para el `canonical`.
FICHAS = {
    "noticias": _noticia,
    "normativa": _norma,
    "medidas": _medida,
    "peligros": _centro_poblado,
}


# --- La vista ---------------------------------------------------------------


@cache_control(max_age=300, public=True)
def ficha_html(request, tipo: str, clave: str):
    """El `index.html` de la SPA con las metas de esta ficha.

    Un tipo desconocido o una ficha inexistente devuelven el HTML **sin metas propias**, no un 404:
    la ruta la resuelve el router de React, que ya sabe enseñar su propio «no encontrado». Un 404
    aquí sustituiría esa pantalla por la de nginx.
    """
    resolver = FICHAS.get(tipo)
    datos = resolver(clave) if resolver else None
    canonical = f"{_sitio()}/{tipo}/{clave}"
    return HttpResponse(_con_metas(datos, canonical), content_type="text/html; charset=utf-8")


def _con_metas(datos: dict | None, canonical: str) -> str:
    base = _leer_index()
    if datos is None:
        # Sin ficha, al menos el canonical y las metas del sitio: es mejor que nada y evita que
        # una URL desconocida herede el `og:` de otra página por la caché del rastreador.
        datos = {
            "titulo": "Observatorio Kallpachakuy — GRD y ACC en Cusco",
            "descripcion": DESCRIPCION_SITIO,
            "imagen": None,
            "tipo_og": "website",
        }

    titulo = _recortar(datos["titulo"], 110)
    descripcion = _recortar(datos["descripcion"] or DESCRIPCION_SITIO, 200)
    imagen = datos["imagen"] or f"{_sitio()}{OG_POR_DEFECTO}"

    metas = "\n".join([
        f'    <title>{escape(titulo)} | Observatorio Kallpachakuy</title>',
        f'    <link rel="canonical" href="{escape(canonical)}" />',
        f'    <meta name="description" content="{escape(descripcion)}" />',
        f'    <meta property="og:type" content="{datos["tipo_og"]}" />',
        f'    <meta property="og:site_name" content="Observatorio Kallpachakuy" />',
        f'    <meta property="og:locale" content="es_PE" />',
        f'    <meta property="og:url" content="{escape(canonical)}" />',
        f'    <meta property="og:title" content="{escape(titulo)}" />',
        f'    <meta property="og:description" content="{escape(descripcion)}" />',
        f'    <meta property="og:image" content="{escape(imagen)}" />',
        f'    <meta name="twitter:card" content="summary_large_image" />',
        f'    <meta name="twitter:title" content="{escape(titulo)}" />',
        f'    <meta name="twitter:description" content="{escape(descripcion)}" />',
        f'    <meta name="twitter:image" content="{escape(imagen)}" />',
        "  </head>",
    ])
    # El `<title>` y la `description` del index.html se quitan para no duplicarlos: dos `<title>`
    # en un documento no son un error de sintaxis, pero cada rastreador elige uno distinto.
    limpio = re.sub(r"\s*<title>.*?</title>", "", base, count=1, flags=re.IGNORECASE | re.DOTALL)
    limpio = re.sub(r'\s*<meta\s+name="description"[^>]*/?>', "", limpio, count=1,
                    flags=re.IGNORECASE)
    return FIN_HEAD.sub(metas, limpio, count=1)


#: `(mtime, contenido)` del index.html. Releerlo en cada petición sería un `stat` y una lectura de
#: disco por visita; no releerlo nunca dejaría la SPA servida con los bundles del despliegue
#: anterior hasta el próximo reinicio, que es el fallo silencioso de siempre.
_cache: tuple[float, str] | None = None


def _leer_index() -> str:
    global _cache

    ruta = RAIZ_SPA / "index.html"
    try:
        marca = ruta.stat().st_mtime
    except OSError as exc:
        # En desarrollo no hay `dist/`: la SPA la sirve `npm run dev`. Sin esto, cualquier prueba
        # que toque estas rutas dependería de haber compilado el frontend antes.
        raise Http404("La SPA no está compilada en este entorno") from exc

    if _cache is None or _cache[0] != marca:
        _cache = (marca, ruta.read_text(encoding="utf-8"))
    return _cache[1]


def _recortar(texto: str, maximo: int) -> str:
    """Recorta por palabras y añade puntos suspensivos.

    Los rastreadores cortan por su cuenta —Facebook alrededor de 300 caracteres, X bastante
    antes— pero lo hacen a mitad de palabra. Recortar aquí deja la frase legible.
    """
    texto = html.unescape(re.sub(r"<[^>]+>", " ", texto or "")).strip()
    texto = re.sub(r"\s+", " ", texto)
    if len(texto) <= maximo:
        return texto
    return texto[:maximo].rsplit(" ", 1)[0].rstrip(",;:.") + "…"


# --- Sitemap ----------------------------------------------------------------


#: Rutas fijas de la SPA. `/comparar` queda fuera a propósito: sigue viva pero está fuera del menú
#: (ADR-P2), y anunciarla en el sitemap sería reactivarla por la puerta de atrás.
RUTAS_FIJAS = ["", "/sobre", "/peligros", "/medidas", "/inversion", "/normativa", "/noticias",
               "/recursos", "/videos", "/eventos"]


@cache_control(max_age=3600, public=True)
def sitemap(request):
    """Sitemap con las rutas fijas y las fichas publicadas.

    Dinámico y no un archivo estático porque el contenido crece: una norma publicada hoy tiene que
    poder indexarse hoy, sin recompilar el frontend.
    """
    from apps.contenidos.models import Noticia
    from apps.medidas.models import Medida
    from apps.normativa.models import Norma

    sitio = _sitio()
    urls = [(f"{sitio}{ruta}", None) for ruta in RUTAS_FIJAS]
    for modelo, prefijo in ((Noticia, "noticias"), (Norma, "normativa"), (Medida, "medidas")):
        for slug, actualizado in (
            modelo.objects.filter(estado="publicado").values_list("slug", "actualizado_en")
        ):
            urls.append((f"{sitio}/{prefijo}/{slug}", actualizado))

    cuerpo = "\n".join(
        "  <url><loc>{}</loc>{}</url>".format(
            escape(url),
            f"<lastmod>{fecha:%Y-%m-%d}</lastmod>" if fecha else "",
        )
        for url, fecha in urls
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{cuerpo}\n</urlset>\n"
    )
    return HttpResponse(xml, content_type="application/xml")
