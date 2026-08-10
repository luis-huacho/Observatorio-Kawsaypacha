"""Serializers del API público.

Las formas espejan los tipos del prototipo (`frontend/src/lib/types.ts`) para que la migración
del frontend cambie la URL y no la lógica de las páginas. Donde el spec 02 fija una forma, la
forma manda sobre lo que sería natural en DRF.
"""
from django.conf import settings
from rest_framework import serializers

from apps.biblioteca.models import CategoriaDocumento, Documento
from apps.contenidos.models import Evento, Noticia, Video
from apps.mapas.models import CapaCartografica
from apps.medidas.models import Medida, MedidaImagen
from apps.normativa.models import Norma
from apps.peligros.models import ClasificacionPeligro, TipoPeligro
from apps.sitio.models import BloqueTexto, ConfiguracionSitio, EnlaceMenu, HeroSlide
from apps.territorio.models import CentroPoblado, Distrito, Provincia

from . import imagenes


# --- Territorio y peligros --------------------------------------------------
class ProvinciaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Provincia
        fields = ["ubigeo", "nombre"]


class DistritoSerializer(serializers.ModelSerializer):
    provincia = serializers.CharField(source="provincia.nombre", read_only=True)
    ubigeo_provincia = serializers.CharField(source="provincia.ubigeo", read_only=True)

    class Meta:
        model = Distrito
        fields = ["ubigeo", "nombre", "provincia", "ubigeo_provincia"]


class CentroPobladoSerializer(serializers.ModelSerializer):
    departamento = serializers.SerializerMethodField()
    provincia = serializers.CharField(source="distrito.provincia.nombre", read_only=True)
    distrito = serializers.CharField(source="distrito.nombre", read_only=True)
    ubigeo_distrito = serializers.CharField(source="distrito_id", read_only=True)
    # Máximo de las clasificaciones que pasan los filtros; null = sin dato con esos filtros.
    # La anotación la pone `filters.anotar_nivel`.
    nivel = serializers.IntegerField(read_only=True, allow_null=True, required=False)

    class Meta:
        model = CentroPoblado
        # Sin `poblacion`: la fuente la trae, pero 948 centros poblados valen 0 y la mediana es
        # 17 habitantes, así que como columna comparable o como escala del mapa es ilegible.
        # Sigue en la ficha individual (`CentroPobladoDetalleSerializer`), donde es un atributo
        # del lugar y no una magnitud que se compare con nada.
        fields = [
            "codigo", "nombre", "categoria", "departamento", "provincia",
            "distrito", "ubigeo_distrito", "lat", "lon", "altitud", "nivel",
        ]

    def get_departamento(self, obj) -> str:
        # El observatorio es regional: el padrón entero es de Cusco, así que es constante y no
        # se guarda por fila. Se devuelve porque el tipo del prototipo lo tiene.
        return "CUSCO"


class ClasificacionPeligroSerializer(serializers.ModelSerializer):
    codigo_ccpp = serializers.CharField(source="centro_poblado.codigo", read_only=True)
    peligro = serializers.CharField(source="tipo_peligro.nombre", read_only=True)
    peligro_slug = serializers.CharField(source="tipo_peligro.slug", read_only=True)
    categoria_geo = serializers.CharField(source="tipo_peligro.categoria_geo", read_only=True)
    fuente = serializers.SerializerMethodField()

    class Meta:
        model = ClasificacionPeligro
        fields = [
            "codigo_ccpp", "peligro", "peligro_slug", "categoria_geo",
            "nivel", "fuente", "fuente_url",
        ]

    def get_fuente(self, obj) -> str | None:
        return str(obj.fuente) if obj.fuente_id else None


class CentroPobladoDetalleSerializer(CentroPobladoSerializer):
    clasificaciones = ClasificacionPeligroSerializer(many=True, read_only=True)

    class Meta(CentroPobladoSerializer.Meta):
        # La ficha sí publica la población: ahí es un dato del centro poblado, no una escala
        # con la que se le compare contra los otros 8,967.
        fields = CentroPobladoSerializer.Meta.fields + ["poblacion", "clasificaciones"]


class TipoPeligroSerializer(serializers.ModelSerializer):
    class Meta:
        model = TipoPeligro
        fields = ["slug", "nombre", "categoria_geo", "orden", "descripcion", "icono", "color"]


# --- Contenido editorial ----------------------------------------------------
class DistritoBreveSerializer(serializers.ModelSerializer):
    provincia = serializers.CharField(source="provincia.nombre", read_only=True)

    class Meta:
        model = Distrito
        fields = ["ubigeo", "nombre", "provincia"]


class MedidaImagenSerializer(serializers.ModelSerializer):
    imagen = serializers.SerializerMethodField()

    class Meta:
        model = MedidaImagen
        fields = ["imagen", "pie", "orden"]

    def get_imagen(self, obj) -> str | None:
        return imagenes.url_absoluta(obj.imagen)


class PortadaMixin(serializers.Serializer):
    """`imagen_portada` e `imagen_titulo` resueltos en el servidor (spec 01/02).

    Las subclases declaran `clave_portada` o sobreescriben `_clave_portada()`.
    """

    clave_portada = "noticia"

    imagen_portada = serializers.SerializerMethodField()
    imagen_titulo = serializers.SerializerMethodField()

    def _clave_portada(self, obj) -> str:
        return self.clave_portada

    def get_imagen_portada(self, obj) -> str:
        return imagenes.portada(obj.imagen_portada, self._clave_portada(obj))

    def get_imagen_titulo(self, obj) -> str:
        return imagenes.pie(obj.imagen_titulo, es_propia=bool(obj.imagen_portada))


class MedidaListaSerializer(PortadaMixin, serializers.ModelSerializer):
    peligro = serializers.CharField(source="tipo_peligro.nombre", read_only=True)
    peligro_slug = serializers.CharField(source="tipo_peligro.slug", read_only=True)
    distrito = DistritoBreveSerializer(read_only=True)

    class Meta:
        model = Medida
        fields = [
            "slug", "titulo", "peligro", "peligro_slug", "ambito", "resultado",
            "distrito", "comunidad", "resumen_corto", "imagen_portada", "imagen_titulo",
            "palabras_clave", "destacada", "publicado_en",
        ]

    def _clave_portada(self, obj) -> str:
        return imagenes.clave_medida(obj.tipo_peligro.slug if obj.tipo_peligro_id else None)


class MedidaDetalleSerializer(MedidaListaSerializer):
    galeria = MedidaImagenSerializer(many=True, read_only=True)

    class Meta(MedidaListaSerializer.Meta):
        fields = MedidaListaSerializer.Meta.fields + [
            # HTML de CKEditor ya saneado en servidor (ADR-D2); el cliente lo inyecta tal cual.
            "contenido", "video_url", "galeria", "enlaces",
        ]


class NormaSerializer(PortadaMixin, serializers.ModelSerializer):
    clave_portada = "norma"
    anio = serializers.IntegerField(read_only=True)
    # El acceso a la publicación oficial va en el listado y en la ficha: quien prepara un
    # expediente entra al repositorio a por el documento, y obligarle a abrir la ficha añade
    # un paso. Los tres estados —PDF alojado, portal, sin enlace— son reales.
    documento_url = serializers.SerializerMethodField()

    class Meta:
        model = Norma
        fields = [
            "slug", "titulo", "tipo", "ambito", "fecha", "anio", "resumen",
            "analisis_predes", "url_oficial", "documento_url",
            "imagen_portada", "imagen_titulo", "palabras_clave", "numero", "estado_vigencia",
        ]

    def get_documento_url(self, obj) -> str | None:
        """El PDF alojado por PREDES tiene prioridad sobre el enlace al portal.

        Los portales del Estado reorganizan sus URL con frecuencia, y un enlace roto en un
        repositorio normativo lo inutiliza.
        """
        if obj.documento_id and obj.documento.archivo:
            return imagenes.url_absoluta(obj.documento.archivo)
        return None


class NormaDetalleSerializer(NormaSerializer):
    class Meta(NormaSerializer.Meta):
        fields = NormaSerializer.Meta.fields + ["contenido"]


class NoticiaListaSerializer(PortadaMixin, serializers.ModelSerializer):
    class Meta:
        model = Noticia
        fields = [
            "slug", "titulo", "bajada", "tipo", "autor", "fecha",
            "imagen_portada", "imagen_titulo", "palabras_clave", "destacada",
        ]

    def _clave_portada(self, obj) -> str:
        # La ilustración va por tipo de contenido: noticia, artículo u opinión.
        return obj.tipo or "noticia"


class NoticiaDetalleSerializer(NoticiaListaSerializer):
    class Meta(NoticiaListaSerializer.Meta):
        fields = NoticiaListaSerializer.Meta.fields + ["cuerpo"]


class VideoSerializer(serializers.ModelSerializer):
    tema = serializers.CharField(source="tema.nombre", read_only=True, default=None)
    tema_slug = serializers.CharField(source="tema.slug", read_only=True, default=None)

    class Meta:
        model = Video
        fields = ["id", "titulo", "descripcion", "url", "fecha", "tema", "tema_slug", "duracion"]


class EventoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Evento
        fields = [
            "id", "titulo", "descripcion", "inicio", "fin", "lugar",
            "modalidad", "url_inscripcion", "organizador",
        ]


class CategoriaDocumentoSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoriaDocumento
        fields = ["slug", "nombre", "orden"]


class DocumentoSerializer(serializers.ModelSerializer):
    categoria = serializers.CharField(source="categoria.nombre", read_only=True)
    categoria_slug = serializers.CharField(source="categoria.slug", read_only=True)
    archivo = serializers.SerializerMethodField()

    class Meta:
        model = Documento
        fields = [
            "id", "titulo", "categoria", "categoria_slug", "archivo", "url_externa",
            "resumen", "resumen_generado_por_ia", "autor_institucion", "fecha_publicacion",
            "paginas", "peso_bytes",
        ]

    def get_archivo(self, obj) -> str | None:
        return imagenes.url_absoluta(obj.archivo)


# --- Sitio y mapas ----------------------------------------------------------
class ConfiguracionSitioSerializer(serializers.ModelSerializer):
    logo = serializers.SerializerMethodField()

    class Meta:
        model = ConfiguracionSitio
        fields = [
            "nombre_sitio", "descripcion_footer", "email_contacto", "telefono",
            "direccion", "redes", "mensaje_banner", "logo",
        ]

    def get_logo(self, obj) -> str | None:
        return imagenes.url_absoluta(obj.logo)


class EnlaceMenuSerializer(serializers.ModelSerializer):
    class Meta:
        model = EnlaceMenu
        fields = ["texto", "url", "grupo", "orden"]


class HeroSlideSerializer(serializers.ModelSerializer):
    imagen = serializers.SerializerMethodField()

    class Meta:
        model = HeroSlide
        fields = ["titulo", "subtitulo", "imagen", "cta_texto", "cta_url", "orden"]

    def get_imagen(self, obj) -> str | None:
        return imagenes.url_absoluta(obj.imagen)


class BloqueTextoSerializer(serializers.ModelSerializer):
    class Meta:
        model = BloqueTexto
        fields = ["clave", "titulo", "cuerpo", "pagina"]


class CapaMapaSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = CapaCartografica
        fields = [
            "slug", "nombre", "descripcion", "url", "tipo_geometria", "estilo",
            "min_zoom", "max_zoom", "visible_por_defecto", "orden", "atribucion", "fuente",
        ]

    def get_url(self, obj) -> str:
        """URL absoluta del .pmtiles: nginx lo sirve desde el dominio del backend (ADR-A14)."""
        return f"{settings.BACKEND_URL.rstrip('/')}/tiles/{obj.slug}.pmtiles"


# --- Métricas (único endpoint de escritura) ---------------------------------
class EventoUsoSerializer(serializers.Serializer):
    """Beacon de métricas. Sin PII: no se acepta ni se guarda nada que identifique a nadie."""

    tipo = serializers.CharField(max_length=20)
    ruta = serializers.CharField(max_length=250)
    detalle = serializers.CharField(max_length=250, required=False, allow_blank=True, default="")

    def validate_tipo(self, valor):
        from apps.metricas.models import TipoEventoUso

        if valor not in TipoEventoUso.values:
            raise serializers.ValidationError(
                f"Tipo desconocido. Válidos: {', '.join(TipoEventoUso.values)}."
            )
        return valor
