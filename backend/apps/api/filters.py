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


def _lista(valor) -> list[str]:
    """`"sismo, heladas"` → `["sismo", "heladas"]`. Vacío o ausente → `[]`."""
    return [parte.strip() for parte in str(valor or "").split(",") if parte.strip()]


def parametros_exposicion(datos) -> tuple[list[str], list[int]]:
    """Lee los filtros de exposición de un querydict: `(slugs de peligro, niveles)`.

    Único sitio donde se interpretan los cuatro parámetros, para que el listado, el geojson,
    el export, el resumen y la ayuda memoria no puedan divergir en qué entienden por lo mismo.

    Los filtros son **selección múltiple**, no umbrales: `niveles=1,4` pide «Bajo» y «Muy alto»
    y deja fuera los de en medio, que con el antiguo `nivel_min` era inexpresable.

    Se aceptan `peligro` (un slug o nombre) y `nivel_min` (umbral) como compatibilidad: hay
    ayudas memoria compartidas con esas URL y el comparador todavía las emite. `nivel_min=3`
    significa lo que significaba, los niveles 3 y 4. Si vienen las dos formas gana la nueva.

    Una lista vacía —ausente, `peligros=`, o con solo valores desconocidos— no restringe nada.
    """
    peligros = _lista(datos.get("peligros"))
    if not peligros and (unico := str(datos.get("peligro") or "").strip()):
        peligros = [unico]

    niveles = [int(n) for n in _lista(datos.get("niveles")) if n.isdigit() and 1 <= int(n) <= 4]
    if not niveles:
        try:
            minimo = int(datos.get("nivel_min") or 0)
        except (TypeError, ValueError):
            minimo = 0
        if 1 <= minimo <= 4:
            niveles = list(range(minimo, 5))

    return _a_slugs(peligros), sorted(set(niveles))


def _a_slugs(valores: list[str]) -> list[str]:
    """Normaliza a slug lo que puede venir como slug o como nombre del peligro.

    El nombre se acepta porque el GeoSelector del prototipo trabajaba con nombres y quedan
    enlaces vivos. Se resuelve **aquí**, contra las 9 filas del catálogo, y no dentro del `Q`:
    así la condición del join es un `__in` de slugs y no se duplica por cada grafía admitida.
    """
    if not valores:
        return []
    from apps.peligros.models import TipoPeligro

    catalogo = {}
    for tipo in TipoPeligro.objects.all():
        catalogo[tipo.slug.lower()] = tipo.slug
        catalogo[tipo.nombre.lower()] = tipo.slug
    resueltos = [catalogo[v.lower()] for v in valores if v.lower() in catalogo]
    return sorted(set(resueltos))


class CentroPobladoFilter(django_filters.FilterSet):
    """Filtros del visor y de la tabla de /peligros.

    `peligros` y `niveles` se resuelven **en una sola condición de join**, no en dos pasos.
    Aplicarlos por separado dejaría pasar un centro poblado que tiene el peligro pedido en
    nivel 1 y otro peligro distinto en nivel 4: cada filtro encontraría su fila y el conjunto
    resultante mentiría. Es la misma semántica que el prototipo resolvía en memoria, y con
    selección múltiple la trampa es más fácil de pisar, no menos.
    """

    provincia = django_filters.CharFilter(method="filtrar_provincia")
    distrito = django_filters.CharFilter(method="filtrar_distrito")
    peligros = django_filters.CharFilter(method="marcador")
    niveles = django_filters.CharFilter(method="marcador")
    # Compatibilidad; los traduce `parametros_exposicion`.
    peligro = django_filters.CharFilter(method="marcador")
    nivel_min = django_filters.NumberFilter(method="marcador")
    buscar = django_filters.CharFilter(field_name="nombre", lookup_expr="icontains")
    categoria = django_filters.CharFilter(field_name="categoria", lookup_expr="iexact")
    clasificados = django_filters.BooleanFilter(method="marcador")

    class Meta:
        model = CentroPoblado
        fields = [
            "provincia", "distrito", "peligros", "niveles", "peligro", "nivel_min",
            "buscar", "categoria",
        ]

    def marcador(self, queryset, name, value):
        """No-op: los filtros de exposición se aplican juntos en `filter_queryset`."""
        return queryset

    def filtrar_provincia(self, queryset, name, value):
        return por_ubigeo_o_nombre(
            queryset, "distrito__provincia__ubigeo", "distrito__provincia__nombre", value
        )

    def filtrar_distrito(self, queryset, name, value):
        return por_ubigeo_o_nombre(queryset, "distrito__ubigeo", "distrito__nombre", value)

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        peligros, niveles = parametros_exposicion(self.data)
        queryset = anotar_nivel(
            queryset,
            peligros=peligros,
            niveles=niveles,
            solo_clasificados=str(self.data.get("clasificados") or "").lower()
            in {"1", "true", "sí", "si"},
        )
        # El orden se aplica **aquí** y no en `get_queryset()` del viewset: `nivel` es una
        # anotación que todavía no existe cuando DRF construye el queryset base.
        # `nulls_last` deja los "sin dato" al final, que es donde los espera quien lee una
        # tabla ordenada por gravedad.
        #
        # `codigo` cierra el orden, y no es decorativo: **el nombre no es único** —770 se
        # repiten en el padrón, «PUCARA» 21 veces—, así que ordenar solo por (nivel, nombre)
        # dejaba un orden parcial. Con `LIMIT`/`OFFSET` sobre un orden parcial PostgreSQL no
        # garantiza nada entre consultas: una misma fila podía salir en dos páginas y otra no
        # salir en ninguna. Se veía como filas repetidas al pulsar «Ver más», y lo que no se
        # veía —los centros poblados que se perdían— era lo grave.
        return queryset.order_by(F("nivel").desc(nulls_last=True), "nombre", "codigo")


def condicion_clasificacion(peligros=(), niveles=()) -> Q:
    """Condición que una clasificación debe cumplir para contar, **desde `CentroPoblado`**.

    Las dos partes van en un solo `Q` a propósito: ver el docstring de `CentroPobladoFilter`.
    """
    condicion = Q()
    if peligros:
        condicion &= Q(clasificaciones__tipo_peligro__slug__in=peligros)
    if niveles:
        condicion &= Q(clasificaciones__nivel__in=niveles)
    return condicion


def condicion_clasificacion_local(peligros=(), niveles=()) -> Q:
    """La misma condición, escrita **desde `ClasificacionPeligro`**.

    Existen las dos porque hay consultas que parten del centro poblado (tabla, mapa, anotación
    del nivel) y otras que parten de la clasificación (el bloque `por_peligro` del resumen).
    Tenerlas juntas es lo que evita que una se actualice y la otra no.
    """
    condicion = Q()
    if peligros:
        condicion &= Q(tipo_peligro__slug__in=peligros)
    if niveles:
        condicion &= Q(nivel__in=niveles)
    return condicion


def anotar_nivel(queryset, peligros=(), niveles=(), solo_clasificados: bool = False):
    """Añade `nivel` = máximo de las clasificaciones que sobreviven a los filtros.

    Es la unidad que usan la tabla, la grilla de resultados y el **color** de los símbolos del
    mapa: **centros poblados contados una vez, en su nivel más alto**. Agregar sobre las
    clasificaciones daría 10,978 donde la tabla lista 3,238 (los 75 CCPP de Acomayo tienen 3
    peligros cada uno). El **número** de los grupos del visor sí cuenta en esa otra unidad, y
    para eso el geojson expone `clasificaciones` por punto (ADR-A16).
    """
    condicion = condicion_clasificacion(peligros, niveles)
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
    # Único campo ordenable hoy: lo pide la portada para sus casos destacados. El resto del
    # listado sigue con el orden por defecto del modelo (`-publicado_en, -creado_en`).
    ordering = django_filters.OrderingFilter(fields=(("fecha_implementacion", "fecha_implementacion"),))

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
    # Por slug y no por pk, como en `VideoFilter`: la URL de un filtro se comparte y se guarda,
    # y un id autoincremental no sobrevive a una recarga de la base.
    entidad = django_filters.CharFilter(field_name="entidad_emisora__slug")

    class Meta:
        model = Norma
        fields = ["tipo", "ambito", "entidad", "anio", "tema"]


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
