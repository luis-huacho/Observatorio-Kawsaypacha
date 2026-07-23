"""Serializers espejo de los tipos del prototipo (frontend/src/lib/types.ts)."""
from rest_framework import serializers

from apps.peligros.models import ClasificacionPeligro, FrecuenciaEmergencia, TipoPeligro
from apps.territorio.models import CentroPoblado, Distrito, Provincia


class ProvinciaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Provincia
        fields = ["ubigeo", "nombre"]


class DistritoSerializer(serializers.ModelSerializer):
    provincia = serializers.CharField(source="provincia.nombre", read_only=True)

    class Meta:
        model = Distrito
        fields = ["ubigeo", "nombre", "provincia"]


class CentroPobladoSerializer(serializers.ModelSerializer):
    # Misma forma que ccpp.json del prototipo.
    departamento = serializers.SerializerMethodField()
    provincia = serializers.CharField(source="distrito.provincia.nombre", read_only=True)
    distrito = serializers.CharField(source="distrito.nombre", read_only=True)
    ubigeo_distrito = serializers.CharField(source="distrito_id", read_only=True)

    class Meta:
        model = CentroPoblado
        fields = [
            "codigo", "nombre", "categoria", "departamento", "provincia",
            "distrito", "ubigeo_distrito", "lat", "lon", "altitud", "poblacion",
        ]

    def get_departamento(self, obj) -> str:
        return "CUSCO"


class ClasificacionPeligroSerializer(serializers.ModelSerializer):
    # Misma forma que peligros.json del prototipo.
    codigo_ccpp = serializers.CharField(source="centro_poblado.codigo", read_only=True)
    peligro = serializers.CharField(source="tipo_peligro.nombre", read_only=True)
    tipo = serializers.CharField(source="subtipo", read_only=True)
    fuente = serializers.SerializerMethodField()

    class Meta:
        model = ClasificacionPeligro
        fields = ["codigo_ccpp", "peligro", "tipo", "nivel", "fuente", "fuente_url"]

    def get_fuente(self, obj) -> str | None:
        return str(obj.fuente) if obj.fuente else None


class CentroPobladoDetalleSerializer(CentroPobladoSerializer):
    clasificaciones = ClasificacionPeligroSerializer(many=True, read_only=True)

    class Meta(CentroPobladoSerializer.Meta):
        fields = CentroPobladoSerializer.Meta.fields + ["clasificaciones"]


class TipoPeligroSerializer(serializers.ModelSerializer):
    class Meta:
        model = TipoPeligro
        fields = ["slug", "nombre", "orden", "descripcion", "icono", "color"]


class FrecuenciaEmergenciaSerializer(serializers.ModelSerializer):
    distrito = serializers.CharField(source="distrito.nombre", read_only=True)
    ubigeo_distrito = serializers.CharField(source="distrito.ubigeo", read_only=True)
    provincia = serializers.CharField(source="distrito.provincia.nombre", read_only=True)
    evento = serializers.CharField(source="tipo_evento.nombre", read_only=True)
    categoria = serializers.CharField(source="tipo_evento.categoria.nombre", read_only=True)

    class Meta:
        model = FrecuenciaEmergencia
        fields = [
            "ubigeo_distrito", "distrito", "provincia", "evento", "categoria",
            "conteo", "rango_fecha", "fuente", "fuente_url",
        ]
