"""Los documentos que el sitio publica para que lo descubra una máquina.

Aquí viven `/robots.txt` y `/.well-known/api-catalog`. Es el vecino de `vistas_html.py` —que sirve
el `index.html` de la SPA con las metas de cada ficha, y el `sitemap.xml`— pero con otro destinatario:
aquello es para el rastreador que va a *enseñar* una página, esto es para el cliente que quiere
*consumir* los datos.

**Por qué el robots.txt lo genera Django y no es un archivo estático.** Lo era, en
`frontend/public/robots.txt`, y traía esta línea escrita a mano:

    Sitemap: https://observatorio.predes.org.pe/sitemap.xml

El sitio en el aire es otro (`observatorio.somosiadigital.com`), y ese host **ni siquiera resuelve**
todavía. Resultado medido: el sitemap existe, funciona y responde 26 URL en `/sitemap.xml`, y no lo
lee nadie, porque el único sitio que lo anuncia apunta a un dominio que no está. Además, aunque el
dominio estuviera arriba, Google **ignora un sitemap declarado en otro host** sin verificación
cruzada. Un archivo estático no puede interpolar `SITE_URL`; el sitemap ya lo hace y por eso él sí
sale bien. Esto lo iguala.

**Y el archivo estático sigue existiendo, como red.** Que el robots.txt dependa del backend tiene un
riesgo que no es cosmético: un 5xx en `/robots.txt` no hace que Google rastree el sitio entero, hace
que **deje de rastrearlo**. Por eso el `location = /robots.txt` de nginx repliega a
`@robots_estatico`, que sirve el archivo del bundle. Si esto se cae, el peor caso es un robots.txt
sin la línea `Sitemap:`, no un sitio desindexado.
"""
import json

from django.conf import settings
from django.http import HttpResponse
from django.urls import reverse
from django.views.decorators.cache import cache_control

#: Preferencias de uso del contenido por sistemas de IA (contentsignals.org, borrador de IETF).
#: Decisión de PREDES: que un asistente pueda **encontrar y citar** el contenido del observatorio,
#: no que se use como corpus de entrenamiento.
#:
#: Va dentro del grupo `User-agent:`, que es donde la define el borrador. Es seguro aunque nadie la
#: implemente: RFC 9309 obliga a los parsers de robots.txt a ignorar las directivas que no conocen,
#: así que no puede romper el rastreo de nadie.
SENALES_CONTENIDO = "ai-train=no, search=yes, ai-input=yes"

CABECERA_ROBOTS = """\
# Observatorio Kallpachakuy — https://predes.org.pe
#
# El sitio es público y su razón de ser es que la información de GRD y ACC de Cusco se encuentre.
# Lo genera el backend (apps/sitio/descubrimiento.py) y no es un archivo estático, para que la
# línea `Sitemap:` apunte SIEMPRE al dominio desde el que te lo estás descargando.
#
# `/comparar` sigue viva pero está fuera del menú por decisión de producto (ADR-P2). No se prohíbe
# —no es secreta— pero tampoco se anuncia en el sitemap.
"""

AVISO_NO_INDEXABLE = """\
# Este despliegue NO es el sitio canónico (SITIO_INDEXABLE=0). Se prohíbe el rastreo entero para
# que no compita en los buscadores con el dominio bueno: dos copias idénticas del mismo sitio son
# contenido duplicado, y quien elige cuál sobrevive es Google, no nosotros.
"""


def _sitio() -> str:
    return settings.SITE_URL.rstrip("/")


def _api(nombre: str) -> str:
    """URL pública absoluta de una ruta del backend.

    Con `BACKEND_URL`, que es la URL con la que **el cliente** alcanza el API — la SPA y el API
    viven en dominios distintos (ADR-A14)—, y con `reverse()` en vez de una cadena literal: así
    renombrar una ruta rompe la prueba en vez de dejar el catálogo apuntando a una URL muerta.
    """
    return f"{settings.BACKEND_URL.rstrip('/')}{reverse(nombre)}"


@cache_control(max_age=3600, public=True)
def robots_txt(request):
    lineas = [CABECERA_ROBOTS]
    if not settings.SITIO_INDEXABLE:
        lineas.append(AVISO_NO_INDEXABLE)
    lineas.append(
        "User-agent: *\n"
        f"Content-Signal: {SENALES_CONTENIDO}\n"
        + ("Allow: /\n" if settings.SITIO_INDEXABLE else "Disallow: /\n")
    )
    # Sin sitemap cuando el sitio está cerrado al rastreo: anunciar un mapa de lo que acabas de
    # prohibir es una contradicción, y las contradicciones en robots.txt las resuelve el rastreador.
    if settings.SITIO_INDEXABLE:
        lineas.append(f"Sitemap: {_sitio()}{reverse('sitemap')}\n")

    return HttpResponse("\n".join(lineas), content_type="text/plain; charset=utf-8")


@cache_control(max_age=3600, public=True)
def api_catalog(request):
    """Catálogo de API en `application/linkset+json` (RFC 9727, formato de la RFC 9264).

    Es el único documento de descubrimiento que este sitio puede publicar **sin mentir**: describe
    un API que existe, es público, es de solo lectura y ya tiene esquema OpenAPI y documentación.
    Los otros que pide el informe de agent-readiness —`openid-configuration`,
    `oauth-protected-resource`, `auth.md`, la tarjeta de servidor MCP— describirían capacidades que
    aquí no hay, y un agente que las leyera intentaría un flujo que no está al otro lado (ADR-A26).
    """
    catalogo = {
        "linkset": [
            {
                "anchor": _api("api-root"),
                "service-desc": [
                    # El esquema se sirve en YAML por defecto y en JSON a petición; se listan los
                    # dos para que un cliente no tenga que adivinar el parámetro.
                    {"href": _api("schema"), "type": "application/vnd.oai.openapi"},
                    {
                        "href": f"{_api('schema')}?format=json",
                        "type": "application/vnd.oai.openapi+json",
                    },
                ],
                "service-doc": [
                    {
                        "href": _api("swagger-ui"),
                        "type": "text/html",
                        "title": "Documentación del API del Observatorio Kallpachakuy",
                    }
                ],
                "status": [{"href": _api("salud"), "type": "application/json"}],
                "author": [{"href": "https://predes.org.pe"}],
            }
        ]
    }
    respuesta = HttpResponse(
        json.dumps(catalogo, ensure_ascii=False, indent=2) + "\n",
        content_type="application/linkset+json",
    )
    # Público y sin credenciales: un agente que lo lea desde otro origen tiene que poder. El resto
    # del dominio de la SPA no lleva CORS porque no lo necesita; esto sí.
    respuesta["Access-Control-Allow-Origin"] = "*"
    return respuesta
