"""Vistas del API, agrupadas por dominio.

Se parte en módulos y no en un único `views.py` porque son ~25 endpoints de cuatro áreas que se
tocan por separado: peligros (los datos reales), editorial (lo que administra PREDES), sitio
(el cascarón y las métricas) e incidencia (los productos para mesas técnicas).
"""
from .busqueda import BusquedaView, EstadoBusquedaView
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
from .inversion import (
    InversionEntidadDetalleView,
    InversionEntidadesView,
    InversionExportView,
    InversionView,
)
from .salud import SaludView
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
from .sitio import CapasMapaView, MetricaEventoView, SitioView

__all__ = [
    "AyudaMemoriaView",
    "BusquedaView",
    "CapasMapaView",
    "CategoriaDocumentoListaView",
    "CentroPobladoExportView",
    "CentroPobladoGeoJSONView",
    "CentroPobladoViewSet",
    "ComparadorView",
    "DistritoViewSet",
    "DocumentoViewSet",
    "EstadoBusquedaView",
    "EventoListaView",
    "FrecuenciaDetalleView",
    "FrecuenciaExportView",
    "FrecuenciaListaView",
    "InversionEntidadDetalleView",
    "InversionEntidadesView",
    "InversionExportView",
    "InversionView",
    "MedidaViewSet",
    "MetricaEventoView",
    "NormaExportView",
    "NormaViewSet",
    "NoticiaViewSet",
    "ProvinciaViewSet",
    "ResumenPeligrosView",
    "SaludView",
    "SitioView",
    "TipoPeligroViewSet",
    "VideoViewSet",
]
