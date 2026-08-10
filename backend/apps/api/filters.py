import django_filters
from django.db.models import F, Max, Q

from apps.biblioteca.models import Documento
from apps.contenidos.models import Noticia, Video
from apps.medidas.models import Medida
from apps.normativa.models import Norma
from apps.peligros.models import FrecuenciaEmergencia
from apps.territorio.models import CentroPoblado, Distrito


def por_ubigeo_o_nombre(queryset, campo_ubigeo: str, campo_nombre: str, valor: str):
    """El frontend manda ubigeo cuando lo tiene y nombre cuando viene del GeoSelector."""
    if valor.isdigit():
        return queryset.filter(**{campo_ubigeo: valor})
    return queryset.filter(**{f"{campo_nombre}__iexact": valor})


class DistritoFilter(django_filters.FilterSet):
    provincia = django_filters.CharFilter(method="filtrar_provincia")

    class Meta:
        model = Distrito
        fields = ["provincia"]

    def filtrar_provincia(self, queryset, name, value):
        return por_ubigeo_o_nombre(queryset, "provincia__ubigeo", "provincia__nombre", value)


class CentroPobladoFilter(django_filters.FilterSet):
    """Filtros del visor y de la tabla de /peligros.

    `peligro` y `nivel_min` se resuelven **en una sola condición de join**, no en dos pasos.
    Aplicarlos por separado dejaría pasar un centro poblado que tiene el peligro pedido en
    nivel 1 y otro peligro distinto en nivel 4: cada filtro encontraría su fila y el conjunto
    resultante mentiría. Es la misma semántica que el prototipo resolvía en memoria.
    """

    provincia = django_filters.CharFilter(method="filtrar_provincia")
    distrito = django_filters.CharFilter(method="filtrar_distrito")
    peligro = django_filters.CharFilter(method="marcador")
    nivel_min = django_filters.NumberFilter(method="marcador")
    buscar = django_filters.CharFilter(field_name="nombre", lookup_expr="icontains")
    categoria = django_filters.CharFilter(field_name="categoria", lookup_expr="iexact")
    clasificados = django_filters.BooleanFilter(method="marcador")

    class Meta:
        model = CentroPoblado
        fields = ["provincia", "distrito", "peligro", "nivel_min", "buscar", "categoria"]

    def marcador(self, queryset, name, value):
        """No-op: `peligro`, `nivel_min` y `clasificados` se aplican juntos en `filter_queryset`."""
        return queryset

    def filtrar_provincia(self, queryset, name, value):
        return por_ubigeo_o_nombre(
            queryset, "distrito__provincia__ubigeo", "distrito__provincia__nombre", value
        )

    def filtrar_distrito(self, queryset, name, value):
        return por_ubigeo_o_nombre(queryset, "distrito__ubigeo", "distrito__nombre", value)

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        queryset = anotar_nivel(
            queryset,
            peligro=self.data.get("peligro") or "",
            nivel_min=self.data.get("nivel_min") or "",
            solo_clasificados=str(self.data.get("clasificados") or "").lower()
            in {"1", "true", "sí", "si"},
        )
        # El orden se aplica **aquí** y no en `get_queryset()` del viewset: `nivel` es una
        # anotación que todavía no existe cuando DRF construye el queryset base.
        # `nulls_last` deja los "sin dato" al final, que es donde los espera quien lee una
        # tabla ordenada por gravedad; `nombre` desempata para que la paginación no repita ni
        # se salte filas entre páginas.
        return queryset.order_by(F("nivel").desc(nulls_last=True), "nombre")


def condicion_clasificacion(peligro: str = "", nivel_min="") -> Q:
    """Condición que una clasificación debe cumplir para contar, dados los filtros."""
    condicion = Q()
    if peligro:
        # El slug es la clave canónica; se acepta el nombre porque el GeoSelector del
        # prototipo trabajaba con nombres y algún enlace viejo puede seguir usándolos.
        condicion &= Q(clasificaciones__tipo_peligro__slug=peligro) | Q(
            clasificaciones__tipo_peligro__nombre__iexact=peligro
        )
    try:
        minimo = int(nivel_min)
    except (TypeError, ValueError):
        minimo = 0
    if minimo:
        condicion &= Q(clasificaciones__nivel__gte=minimo)
    return condicion


def anotar_nivel(queryset, peligro: str = "", nivel_min="", solo_clasificados: bool = False):
    """Añade `nivel` = máximo de las clasificaciones que sobreviven a los filtros.

    Es la unidad que usan la tabla, el panel de distribución y el **color** de los símbolos del
    mapa: **centros poblados contados una vez, en su nivel más alto**. Agregar sobre las
    clasificaciones daría 10,978 donde la tabla lista 3,238 (los 75 CCPP de Acomayo tienen 3
    peligros cada uno). El **número** de los grupos del visor sí cuenta en esa otra unidad, y
    para eso el geojson expone `clasificaciones` por punto (ADR-A16).
    """
    condicion = condicion_clasificacion(peligro, nivel_min)
    queryset = queryset.annotate(
        nivel=Max("clasificaciones__nivel", filter=condicion if condicion else None)
    )
    if solo_clasificados:
        queryset = queryset.filter(nivel__isnull=False)
    return queryset


class FrecuenciaFilter(django_filters.FilterSet):
    distrito = django_filters.CharFilter(method="filtrar_distrito")
    provincia = django_filters.CharFilter(method="filtrar_provincia")
    categoria = django_filters.CharFilter(field_name="tipo_evento__categoria__slug")

    class Meta:
        model = FrecuenciaEmergencia
        fields = ["distrito", "provincia", "categoria"]

    def filtrar_distrito(self, queryset, name, value):
        return por_ubigeo_o_nombre(queryset, "distrito__ubigeo", "distrito__nombre", value)

    def filtrar_provincia(self, queryset, name, value):
        return por_ubigeo_o_nombre(
            queryset, "distrito__provincia__ubigeo", "distrito__provincia__nombre", value
        )


class TemaFilterMixin(django_filters.FilterSet):
    """`?tema=` filtra por coincidencia exacta en `palabras_clave`.

    Alimenta los chips navegables de las fichas: pinchar una palabra clave lleva al listado
    recortado por ella (ver 06).
    """

    tema = django_filters.CharFilter(field_name="palabras_clave", lookup_expr="contains",
                                     method="filtrar_tema")

    def filtrar_tema(self, queryset, name, value):
        return queryset.filter(palabras_clave__contains=[value])


class MedidaFilter(TemaFilterMixin):
    peligro = django_filters.CharFilter(field_name="tipo_peligro__slug")
    distrito = django_filters.CharFilter(method="filtrar_distrito")
    provincia = django_filters.CharFilter(method="filtrar_provincia")

    class Meta:
        model = Medida
        fields = ["peligro", "ambito", "resultado", "distrito", "provincia", "tema", "destacada"]

    def filtrar_distrito(self, queryset, name, value):
        return por_ubigeo_o_nombre(queryset, "distrito__ubigeo", "distrito__nombre", value)

    def filtrar_provincia(self, queryset, name, value):
        return por_ubigeo_o_nombre(
            queryset, "distrito__provincia__ubigeo", "distrito__provincia__nombre", value
        )


class NormaFilter(TemaFilterMixin):
    anio = django_filters.NumberFilter(field_name="fecha__year")

    class Meta:
        model = Norma
        fields = ["tipo", "ambito", "anio", "tema"]


class NoticiaFilter(TemaFilterMixin):
    anio = django_filters.NumberFilter(field_name="fecha__year")

    class Meta:
        model = Noticia
        fields = ["tipo", "destacada", "anio", "tema"]


class VideoFilter(django_filters.FilterSet):
    tema = django_filters.CharFilter(field_name="tema__slug")

    class Meta:
        model = Video
        fields = ["tema"]


class DocumentoFilter(django_filters.FilterSet):
    categoria = django_filters.CharFilter(field_name="categoria__slug")
    anio = django_filters.NumberFilter(field_name="fecha_publicacion__year")
    buscar = django_filters.CharFilter(method="filtrar_buscar")

    class Meta:
        model = Documento
        fields = ["categoria", "anio", "buscar"]

    def filtrar_buscar(self, queryset, name, value):
        return queryset.filter(
            Q(titulo__icontains=value)
            | Q(resumen__icontains=value)
            | Q(autor_institucion__icontains=value)
        )
