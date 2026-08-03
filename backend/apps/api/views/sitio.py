"""Sitio, mapas, métricas e Inversión (diferida)."""
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_control
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.mapas.models import CapaCartografica
from apps.sitio.models import BloqueTexto, ConfiguracionSitio, EnlaceMenu, HeroSlide

from .. import serializers
from ..throttling import BeaconThrottle


class SitioView(APIView):
    """`/api/sitio/` — un solo payload con todo lo administrable del cascarón del sitio.

    El frontend lo pide una vez al montar `Layout` y de ahí salen el menú, el pie, el hero y
    los textos. Va en una sola petición y cacheado porque es lo primero que necesita cualquier
    página: partirlo en cuatro endpoints añadiría cuatro round-trips al primer render.
    """

    @method_decorator(cache_control(max_age=300, public=True))
    @extend_schema(responses={200: dict})
    def get(self, request):
        config = ConfiguracionSitio.objects.first()
        menu = EnlaceMenu.objects.filter(visible=True).order_by("orden")
        return Response({
            "config": (
                serializers.ConfiguracionSitioSerializer(config).data if config else {}
            ),
            # Diccionario clave → bloque: el frontend pide `bloques["home.hero.titulo"]` sin
            # recorrer una lista.
            "bloques": {
                b.clave: {"titulo": b.titulo, "cuerpo": b.cuerpo}
                for b in BloqueTexto.objects.all()
            },
            "menu": {
                zona: serializers.EnlaceMenuSerializer(
                    [e for e in menu if e.zona == zona], many=True
                ).data
                for zona in ("header", "footer")
            },
            "hero": serializers.HeroSlideSerializer(
                HeroSlide.publicados.order_by("orden"), many=True
            ).data,
        })


class CapasMapaView(APIView):
    """`/api/mapas/capas/` — solo las capas con tiles listos.

    Una capa con `estado_tiles != ok` no se anuncia: el visor pediría un .pmtiles inexistente
    y MapLibre llenaría la consola de errores por cada tesela.
    """

    @extend_schema(responses={200: serializers.CapaMapaSerializer(many=True)})
    def get(self, request):
        capas = CapaCartografica.objects.filter(
            estado_tiles=CapaCartografica.EstadoTiles.OK
        ).order_by("orden")
        return Response(serializers.CapaMapaSerializer(capas, many=True).data)


class InversionView(APIView):
    """`/api/inversion/` — diferida (ADR-D3).

    El TDR incluye la ventana y sigue siendo parte del producto, pero el cliente aún no tiene
    claridad sobre la data: ni el formato del Excel ni el alcance del PPR 0068 están definidos.
    Modelar contra un formato imaginado se tira a la basura en cuanto llegue el real, así que
    el endpoint responde con el contrato de "sin datos" y el frontend muestra su estado vacío.
    Cuando llegue la data se añade la app `inversion` sin tocar el frontend.
    """

    @extend_schema(responses={200: dict})
    def get(self, request):
        return Response({
            "disponible": False,
            "motivo": "PREDES está consolidando los datos de inversión del PPR 0068.",
        })


class MetricaEventoView(APIView):
    """`POST /api/metricas/evento/` — beacon de métricas internas (ADR-A11).

    Sin cookies y sin PII: `session_hash` es un hash **diario** de IP+UA truncado a 12
    caracteres, que permite distinguir sesiones dentro del día sin poder reidentificar a nadie
    ni seguirle la pista entre días. Responde 204 porque `sendBeacon` descarta el cuerpo.
    """

    throttle_classes = [BeaconThrottle]

    @extend_schema(request=serializers.EventoUsoSerializer, responses={204: None})
    def post(self, request):
        entrada = serializers.EventoUsoSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)

        from apps.metricas.models import EventoUso

        EventoUso.objects.create(
            **entrada.validated_data, session_hash=_hash_sesion(request)
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


def _hash_sesion(request) -> str:
    import hashlib
    from datetime import date

    ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip() or request.META.get(
        "REMOTE_ADDR", ""
    )
    ua = request.META.get("HTTP_USER_AGENT", "")[:200]
    # La fecha entra en el hash a propósito: cambia cada día, así que el mismo visitante no es
    # correlacionable entre jornadas.
    semilla = f"{ip}|{ua}|{date.today().isoformat()}"
    return hashlib.sha256(semilla.encode()).hexdigest()[:12]
