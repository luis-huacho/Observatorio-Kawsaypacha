"""Vistas del API, agrupadas por dominio.

Se parte en módulos y no en un único `views.py` porque son ~25 endpoints de cuatro áreas que se
tocan por separado: peligros (los datos reales), editorial (lo que administra PREDES), sitio
(el cascarón y las métricas) e incidencia (los productos para mesas técnicas).
"""
from .editorial import (
    CategoriaDocumentoListaView,
    DocumentoViewSet,
    EventoListaView,
    MedidaViewSet,
    NormaExportView,
    NormaViewSet,
    NoticiaViewSet,
    VideoViewSet,
)
from .incidencia import AyudaMemoriaView, ComparadorView
from .peligros import (
    CentroPobladoExportView,
    CentroPobladoGeoJSONView,
    CentroPobladoViewSet,
    DistritoViewSet,
    FrecuenciaDetalleView,
    FrecuenciaExportView,
    FrecuenciaListaView,
    ProvinciaViewSet,
    ResumenPeligrosView,
    TipoPeligroViewSet,
)
from .sitio import CapasMapaView, InversionView, MetricaEventoView, SitioView

__all__ = [
    "AyudaMemoriaView",
    "CapasMapaView",
    "CategoriaDocumentoListaView",
    "CentroPobladoExportView",
    "CentroPobladoGeoJSONView",
    "CentroPobladoViewSet",
    "ComparadorView",
    "DistritoViewSet",
    "DocumentoViewSet",
    "EventoListaView",
    "FrecuenciaDetalleView",
    "FrecuenciaExportView",
    "FrecuenciaListaView",
    "InversionView",
    "MedidaViewSet",
    "MetricaEventoView",
    "NormaExportView",
    "NormaViewSet",
    "NoticiaViewSet",
    "ProvinciaViewSet",
    "ResumenPeligrosView",
    "SitioView",
    "TipoPeligroViewSet",
    "VideoViewSet",
]
