"""Búsqueda por DRF: el fallback de cuando Meilisearch no responde (spec 04).

La búsqueda normal va **directo a Meilisearch** desde el navegador con la llave search-only, sin
pasar por Django. Este endpoint existe para que el buscador siga funcionando cuando el servicio
está caído o reindexándose: sin facetas ni tolerancia a errores de tecleo, pero devolviendo la
misma forma para que `lib/search.ts` solo cambie de origen.

Que el fallback exista es una decisión de producto: el buscador es la puerta de entrada al
contenido, y un sitio que responde «no se pudo buscar» ante una consulta se lee como un sitio
roto, no como un servicio degradado.
"""
from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.biblioteca.models import Documento
from apps.contenidos.models import Evento, Noticia, Video
from apps.core.services import meili
from apps.medidas.models import Medida
from apps.normativa.models import Norma
from apps.territorio.models import CentroPoblado

LIMITE_POR_TIPO = 8


class BusquedaView(APIView):
    """`GET /api/buscar/?q=…` — búsqueda global agrupada por tipo."""

    @extend_schema(
        parameters=[
            OpenApiParameter("q", description="Términos de búsqueda.", required=True),
            OpenApiParameter(
                "limite", description=f"Resultados por tipo (default {LIMITE_POR_TIPO}).", type=int
            ),
        ],
        responses={200: dict},
    )
    def get(self, request):
        consulta = (request.query_params.get("q") or "").strip()
        try:
            limite = min(int(request.query_params.get("limite", LIMITE_POR_TIPO)), 20)
        except (TypeError, ValueError):
            limite = LIMITE_POR_TIPO

        if not consulta:
            return Response({"q": "", "grupos": [], "total": 0, "motor": "drf"})

        grupos = [
            self._grupo("medidas", "Medidas", self._medidas(consulta, limite)),
            self._grupo("normativa", "Normativa", self._normas(consulta, limite)),
            self._grupo("noticias", "Noticias", self._noticias(consulta, limite)),
            self._grupo("documentos", "Documentos", self._documentos(consulta, limite)),
            self._grupo("videos", "Videos", self._videos(consulta, limite)),
            self._grupo("eventos", "Eventos", self._eventos(consulta, limite)),
            self._grupo("ccpp", "Centros poblados", self._ccpp(consulta, limite)),
        ]
        grupos = [g for g in grupos if g["resultados"]]
        return Response({
            "q": consulta,
            "grupos": grupos,
            "total": sum(g["total"] for g in grupos),
            # El cliente lo usa para avisar de que está en modo degradado: sin facetas y sin
            # tolerancia a errores de tecleo.
            "motor": "drf",
            "meili_disponible": meili.disponible(),
        })

    def _grupo(self, slug: str, etiqueta: str, resultados: list) -> dict:
        return {
            "indice": slug,
            "etiqueta": etiqueta,
            "resultados": resultados,
            "total": len(resultados),
        }

    def _medidas(self, q: str, limite: int) -> list:
        qs = Medida.publicados.filter(
            Q(titulo__icontains=q) | Q(resumen_corto__icontains=q)
            | Q(contenido__icontains=q) | Q(comunidad__icontains=q)
        ).select_related("tipo_peligro")[:limite]
        return [
            {"titulo": m.titulo, "detalle": m.resumen_corto[:180],
             "extra": m.tipo_peligro.nombre if m.tipo_peligro_id else "",
             "url": f"/medidas/{m.slug}"}
            for m in qs
        ]

    def _normas(self, q: str, limite: int) -> list:
        qs = Norma.publicados.filter(
            Q(titulo__icontains=q) | Q(resumen__icontains=q) | Q(numero__icontains=q)
            | Q(contenido__icontains=q)
        )[:limite]
        return [
            {"titulo": n.titulo, "detalle": n.resumen[:180],
             "extra": f"{n.get_tipo_display()} · {n.fecha.year}", "url": f"/normativa/{n.slug}"}
            for n in qs
        ]

    def _noticias(self, q: str, limite: int) -> list:
        qs = Noticia.publicados.filter(
            Q(titulo__icontains=q) | Q(bajada__icontains=q) | Q(cuerpo__icontains=q)
        )[:limite]
        return [
            {"titulo": n.titulo, "detalle": n.bajada[:180],
             "extra": n.get_tipo_display(), "url": f"/noticias/{n.slug}"}
            for n in qs
        ]

    def _documentos(self, q: str, limite: int) -> list:
        qs = Documento.publicados.filter(
            Q(titulo__icontains=q) | Q(resumen__icontains=q)
            | Q(autor_institucion__icontains=q)
        ).select_related("categoria")[:limite]
        return [
            {"titulo": d.titulo, "detalle": (d.resumen or "")[:180],
             "extra": d.categoria.nombre if d.categoria_id else "", "url": "/recursos"}
            for d in qs
        ]

    def _videos(self, q: str, limite: int) -> list:
        qs = Video.publicados.filter(
            Q(titulo__icontains=q) | Q(descripcion__icontains=q)
        )[:limite]
        return [
            {"titulo": v.titulo, "detalle": (v.descripcion or "")[:180], "extra": "",
             "url": "/videos"}
            for v in qs
        ]

    def _eventos(self, q: str, limite: int) -> list:
        qs = Evento.publicados.filter(
            Q(titulo__icontains=q) | Q(descripcion__icontains=q) | Q(lugar__icontains=q)
        )[:limite]
        return [
            {"titulo": e.titulo, "detalle": (e.descripcion or "")[:180],
             "extra": e.inicio.strftime("%d/%m/%Y"), "url": "/eventos"}
            for e in qs
        ]

    def _ccpp(self, q: str, limite: int) -> list:
        qs = (
            CentroPoblado.objects.filter(nombre__icontains=q)
            .select_related("distrito__provincia")
            .order_by("-poblacion")[:limite]
        )
        return [
            {"titulo": c.nombre,
             "detalle": f"{c.distrito.nombre}, {c.distrito.provincia.nombre}",
             "extra": c.categoria, "url": f"/peligros/{c.codigo}"}
            for c in qs
        ]


class EstadoBusquedaView(APIView):
    """`GET /api/buscar/estado/` — le dice al frontend qué motor puede usar.

    El frontend lo consulta una vez al montar el buscador. Sin esto tendría que intentar contra
    Meilisearch y esperar el timeout para descubrir que está caído, y ese retraso lo paga el
    usuario en cada búsqueda.
    """

    @extend_schema(responses={200: dict})
    def get(self, request):
        disponible = meili.disponible()
        return Response({
            "meili_disponible": disponible,
            "indices": meili.INDICES_BUSQUEDA_GLOBAL if disponible else [],
            "indice_lugares": "ccpp" if disponible else "",
        })
