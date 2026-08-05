"""Prueba de vida del backend, para el healthcheck de Docker y para vigilancia externa.

Existe porque el `restart: unless-stopped` de compose solo actúa si el **proceso muere**, y el
fallo que no cubre es el contrario: gunicorn con sus workers bloqueados, vivo y sin atender. El
contenedor figura `Up` y el sitio devuelve timeouts. Ese es el hueco que esta vista permite ver.

Y por eso mide **una sola cosa: que este proceso atienda peticiones**. Responde `200` aunque la
base o el buscador estén caídos, y lo cuenta en el cuerpo. Si fallara por ellos, una caída de
PostgreSQL marcaría el contenedor «unhealthy», el vigilante lo reiniciaría en bucle, y ni
arreglaría nada ni dejaría rastro que mirar. Liveness no es lo mismo que dependencias.

Por qué una vista propia y no reusar una URL existente (`/api/docs/`, `/api/schema/`): con el
`interval: 10s` del healthcheck son 360 peticiones/hora, y las dos son vistas DRF sujetas al
throttling anónimo de 1000/hora. Un 429 marcaría el contenedor «unhealthy» sin que pasara nada:
una caída autoinfligida. Esta va exenta. `/api/schema/` además regenera el esquema OpenAPI
completo en cada llamada —no hay `CACHES` configurado—, que son 0,4 s de CPU cada diez segundos.

El cuerpo es escueto a propósito —sin versiones, sin nombres de host, sin rutas—: es público.
"""
from django.db import connection

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


def _estado_base() -> str:
    """`ok` si la base contesta. Nunca lanza: la indisponibilidad es un estado, no un error."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return "ok"
    except Exception:  # noqa: BLE001
        return "sin respuesta"


def _estado_buscador() -> str:
    """Igual, contra Meilisearch. `disponible()` ya usa `TIMEOUT_ESTADO` y no lanza."""
    from apps.core.services import meili

    return "ok" if meili.disponible() else "sin respuesta"


class SaludView(APIView):
    """`/api/salud/` — 200 mientras el proceso atienda, con el detalle en el cuerpo.

    Sirve a la vez al healthcheck del contenedor y a la vigilancia desde fuera
    (`deploy/comprobar-sitio.sh`), que es lo único capaz de ver que el servidor entero cayó.
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    # Exenta de throttling: ver la cabecera del módulo. Es la diferencia entre una sonda y un
    # generador de reinicios.
    throttle_classes = []

    @extend_schema(responses={200: dict})
    def get(self, request):
        return Response({
            "servicio": "ok",
            "base": _estado_base(),
            "buscador": _estado_buscador(),
        })
