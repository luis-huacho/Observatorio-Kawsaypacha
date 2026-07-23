import django_filters

from apps.peligros.models import FrecuenciaEmergencia
from apps.territorio.models import CentroPoblado, Distrito


def _por_ubigeo_o_nombre(queryset, campo_ubigeo: str, campo_nombre: str, valor: str):
    if valor.isdigit():
        return queryset.filter(**{campo_ubigeo: valor})
    return queryset.filter(**{f"{campo_nombre}__iexact": valor})


class DistritoFilter(django_filters.FilterSet):
    provincia = django_filters.CharFilter(method="filtrar_provincia")

    class Meta:
        model = Distrito
        fields = ["provincia"]

    def filtrar_provincia(self, queryset, name, value):
        return _por_ubigeo_o_nombre(queryset, "provincia__ubigeo", "provincia__nombre", value)


class CentroPobladoFilter(django_filters.FilterSet):
    provincia = django_filters.CharFilter(method="filtrar_provincia")
    distrito = django_filters.CharFilter(method="filtrar_distrito")
    peligro = django_filters.CharFilter(method="filtrar_peligro")
    nivel = django_filters.NumberFilter(method="filtrar_nivel_minimo")
    buscar = django_filters.CharFilter(field_name="nombre", lookup_expr="icontains")

    class Meta:
        model = CentroPoblado
        fields = ["provincia", "distrito", "peligro", "nivel", "buscar", "categoria"]

    def filtrar_provincia(self, queryset, name, value):
        return _por_ubigeo_o_nombre(
            queryset, "distrito__provincia__ubigeo", "distrito__provincia__nombre", value
        )

    def filtrar_distrito(self, queryset, name, value):
        return _por_ubigeo_o_nombre(queryset, "distrito__ubigeo", "distrito__nombre", value)

    def filtrar_peligro(self, queryset, name, value):
        return queryset.filter(
            clasificaciones__tipo_peligro__slug=value
        ) | queryset.filter(clasificaciones__tipo_peligro__nombre__iexact=value)

    def filtrar_nivel_minimo(self, queryset, name, value):
        peligro = self.data.get("peligro")
        filtro = {"clasificaciones__nivel__gte": value}
        if peligro:
            filtro["clasificaciones__tipo_peligro__slug"] = peligro
        return queryset.filter(**filtro).distinct()


class FrecuenciaFilter(django_filters.FilterSet):
    distrito = django_filters.CharFilter(method="filtrar_distrito")
    provincia = django_filters.CharFilter(method="filtrar_provincia")
    categoria = django_filters.CharFilter(field_name="tipo_evento__categoria__slug")

    class Meta:
        model = FrecuenciaEmergencia
        fields = ["distrito", "provincia", "categoria"]

    def filtrar_distrito(self, queryset, name, value):
        return _por_ubigeo_o_nombre(queryset, "distrito__ubigeo", "distrito__nombre", value)

    def filtrar_provincia(self, queryset, name, value):
        return _por_ubigeo_o_nombre(
            queryset, "distrito__provincia__ubigeo", "distrito__provincia__nombre", value
        )
