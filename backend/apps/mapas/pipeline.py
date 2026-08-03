"""Pipeline de vector tiles (spec 05): GeoJSON → recorte a Cusco → PMTiles.

Puerto de `prototype/scripts/build_tiles.sh`, que ya se validó de punta a punta con los archivos
reales. Los flags no son intercambiables y cada uno está aquí por un motivo concreto:

- **`-t_srs EPSG:4326` siempre** y **`ILIKE` en el filtro de lagunas.** Los dos van por hacer
  explícita la intención, no porque el driver los necesite: medido con GDAL 3.10.3, el driver
  GeoJSON ya reproyecta a WGS84 al escribir (lo exige RFC 7946) y su `-where` compara texto sin
  distinguir mayúsculas. Ninguna de las dos cosas está documentada como garantía —el `=`
  insensible es un detalle del filtro de atributos de OGR, y con un backend SQL real no se
  cumple—, así que se declaran. Ver la corrección del 03/08 en el spec 05.
- **`-r1` y maxzoom explícito en los centros poblados.** Con `-zg` tippecanoe deduce z6 del
  espaciado medio, y a esa escala las coordenadas se cuantizan a ~150 m: el mapa se ve bien
  pero el clic cae en el centro poblado equivocado.
- **Swap por rename.** Escribir directamente sobre el `.pmtiles` publicado deja al visor
  leyendo un archivo a medias; el rename en el mismo volumen es atómico.
"""
import json
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)

#: Polígono regional para las capas que no traen campo de departamento (glaciares).
POLIGONO_CUSCO = Path(__file__).resolve().parent / "datos" / "cusco_region.geojson"

#: Bbox de Cusco con margen, tomado del padrón de centros poblados. Va junto al polígono como
#: pre-filtro: `-spat` descarta por índice espacial antes de recortar, y sobre una capa nacional
#: de 32 MB eso es la diferencia entre segundos y minutos.
BBOX = (-74.1, -15.6, -70.3, -11.2)

TIMEOUT_OGR = 900
TIMEOUT_TIPPECANOE = 900

#: Atributos que se conservan por capa. Lo que no se nombra no viaja al tile: cada propiedad se
#: repite en cada feature de cada zoom, así que arrastrar columnas que nadie consulta engorda el
#: tile sin dar nada a cambio.
ATRIBUTOS = {
    "rios": "JER_HIDRO,DIN99,PN99",
    "lagunas": "NOMBRE,CUENCA,DISTRITO,PROVINCIA,ALTITUD",
    "glaciares": "nomb_base,cordillera,cuenca,area_km2,alt_max",
}

#: Cordilleras de Cusco. Acotan glaciares antes del recorte espacial (ver spec 05).
CORDILLERAS_CUSCO = ["Vilcanota", "Vilcabamba", "Urubamba", "La Raya", "Carabaya"]


class ErrorPipeline(RuntimeError):
    """Fallo del pipeline, con un mensaje pensado para que lo lea el editor en el admin."""


def _ejecutar(comando: list[str], timeout: int) -> str:
    logger.info("ejecutando: %s", " ".join(comando[:6]) + (" …" if len(comando) > 6 else ""))
    try:
        proceso = subprocess.run(
            comando, capture_output=True, text=True, timeout=timeout, check=False
        )
    except FileNotFoundError as exc:
        raise ErrorPipeline(
            f"No se encontró «{comando[0]}». Los tiles se generan dentro del contenedor del "
            f"backend, que sí lo trae instalado."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise ErrorPipeline(
            f"«{comando[0]}» superó el tiempo límite de {timeout} s. Si la capa es de escala "
            f"nacional, prueba a simplificarla o a acotar su filtro."
        ) from exc
    if proceso.returncode != 0:
        salida = (proceso.stderr or proceso.stdout or "").strip()
        raise ErrorPipeline(f"«{Path(comando[0]).name}» falló:\n{salida[-1500:]}")
    return (proceso.stderr or "") + (proceso.stdout or "")


def _directorio_tiles() -> Path:
    destino = Path(settings.MEDIA_ROOT) / "tiles"
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def _publicar(temporal: Path, nombre: str) -> Path:
    """Mueve el tile recién generado a su sitio, de forma atómica."""
    destino = _directorio_tiles() / nombre
    provisional = destino.with_name(destino.name + ".nuevo")
    shutil.move(str(temporal), str(provisional))
    provisional.replace(destino)
    return destino


def _detectar_crs(ruta: Path) -> str:
    """CRS declarado en el archivo, para dejarlo registrado en la capa.

    Se registra siempre: es el dato que explica por qué una capa sale vacía, y descubrirlo con
    glaciares costó una tarde.
    """
    binario = shutil.which("ogrinfo") or settings.OGR2OGR_BIN.replace("ogr2ogr", "ogrinfo")
    try:
        salida = _ejecutar([binario, "-al", "-so", str(ruta)], 180)
    except ErrorPipeline:
        return ""
    for linea in salida.splitlines():
        if "ID[" in linea and "EPSG" in linea:
            return "EPSG:" + linea.split("ID[")[-1].split(",")[-1].strip('"] ')
    return ""


def _condicion_where(filtro: str) -> str:
    """Traduce `DN99=CUSCO` o `DPTO ILIKE cusco` a una cláusula SQL de OGR.

    El campo del admin usa esa forma corta a propósito: pedirle a un editor que escriba SQL con
    comillas es pedirle que se equivoque.
    """
    filtro = (filtro or "").strip()
    if not filtro:
        return ""
    bajo = filtro.upper()
    if " ILIKE " in bajo:
        corte = bajo.index(" ILIKE ")
        campo, valor, comparador = filtro[:corte], filtro[corte + 7 :], "ILIKE"
    elif "=" in filtro:
        campo, _, valor = filtro.partition("=")
        comparador = "="
    else:
        raise ErrorPipeline(
            f"No se entiende el filtro «{filtro}». Usa CAMPO=VALOR o CAMPO ILIKE VALOR."
        )
    return f"{campo.strip()} {comparador} '{valor.strip().strip(chr(39)+chr(34))}'"


def generar_capa(capa_id: int) -> str:
    """Genera los PMTiles de una `CapaCartografica` y deja el resultado en la propia capa."""
    from apps.mapas.models import CapaCartografica

    capa = CapaCartografica.objects.get(pk=capa_id)
    capa.estado_tiles = CapaCartografica.EstadoTiles.GENERANDO
    capa.log_error = ""
    capa.save(update_fields=["estado_tiles", "log_error"])

    try:
        resultado = _generar_capa(capa)
    except Exception as exc:  # noqa: BLE001 — el motivo va al admin, no solo al log del worker
        capa.estado_tiles = CapaCartografica.EstadoTiles.ERROR
        capa.log_error = str(exc)[:4000]
        capa.save(update_fields=["estado_tiles", "log_error", "crs_origen"])
        logger.warning("Tiles de «%s» fallaron: %s", capa.slug, exc)
        return f"error: {exc}"

    capa.estado_tiles = CapaCartografica.EstadoTiles.OK
    capa.log_error = ""
    capa.save()
    return resultado


def _generar_capa(capa) -> str:
    origen = Path(capa.archivo_geojson.path)
    if not origen.exists():
        raise ErrorPipeline(f"El archivo «{origen.name}» no está en el servidor.")

    # Se valida antes de invocar nada externo: un JSON roto se explica mejor aquí que en el
    # stderr de ogr2ogr.
    _validar_geojson(origen)
    capa.crs_origen = _detectar_crs(origen)

    with tempfile.TemporaryDirectory() as tmp:
        intermedio = Path(tmp) / f"{capa.slug}.jsonl"
        comando = [
            settings.OGR2OGR_BIN, "-f", "GeoJSONSeq", str(intermedio), str(origen),
            # Incondicional: cubre las capas proyectadas y no hace nada con las geográficas.
            "-t_srs", "EPSG:4326",
        ]

        if where := _condicion_where(capa.filtro_atributo):
            comando += ["-where", where]
        else:
            # Sin campo de departamento: recorte espacial. `-spat` como pre-filtro barato y
            # `-clipsrc` después para cortar por el límite real.
            comando += [
                "-spat", *[str(v) for v in BBOX], "-spat_srs", "EPSG:4326",
                "-clipsrc", str(POLIGONO_CUSCO),
            ]
            if capa.slug == "glaciares":
                lista = ",".join(f"'{c}'" for c in CORDILLERAS_CUSCO)
                comando += ["-where", f"cordillera IN ({lista})"]

        if atributos := ATRIBUTOS.get(capa.slug):
            comando += ["-select", atributos]
        if capa.simplificacion:
            comando += ["-simplify", str(capa.simplificacion)]

        _ejecutar(comando, TIMEOUT_OGR)

        features = _contar_lineas(intermedio)
        if features == 0:
            raise ErrorPipeline(
                "El recorte a Cusco dejó la capa sin ningún elemento. Revisa el filtro "
                f"(«{capa.filtro_atributo or 'recorte espacial'}») y el CRS del archivo "
                f"(detectado: {capa.crs_origen or 'no declarado'})."
            )

        tmp_pmtiles = Path(tmp) / f"{capa.slug}.pmtiles"
        zoom_max = f"-z{capa.max_zoom}" if capa.max_zoom else "-zg"
        _ejecutar(
            [
                settings.TIPPECANOE_BIN, "-o", str(tmp_pmtiles), "-l", capa.slug,
                f"-Z{capa.min_zoom or 6}", zoom_max,
                "--drop-densest-as-needed", "--generate-ids", "--force", str(intermedio),
            ],
            TIMEOUT_TIPPECANOE,
        )
        destino = _publicar(tmp_pmtiles, f"{capa.slug}.pmtiles")

    capa.pmtiles = f"tiles/{capa.slug}.pmtiles"
    capa.features_generados = features
    if not capa.tipo_geometria:
        capa.tipo_geometria = _geometria_de(origen)
    return f"{features:,} features, {destino.stat().st_size / 1e6:.1f} MB"


def _validar_geojson(ruta: Path) -> None:
    """Comprueba que es un GeoJSON con contenido, leyendo solo la cabecera.

    No se parsea el archivo completo: son hasta 57 MB, y cargarlos en memoria para validar
    sería el paso más caro de todo el pipeline.
    """
    with ruta.open("r", encoding="utf-8", errors="replace") as fh:
        cabecera = fh.read(4096)
    if '"FeatureCollection"' not in cabecera and '"Feature"' not in cabecera:
        raise ErrorPipeline(
            "El archivo no parece un GeoJSON: no aparece «FeatureCollection» al principio. Si "
            "es un shapefile o un KML, conviértelo antes de subirlo."
        )
    if '"features": []' in cabecera.replace("\n", " ").replace('"features":[]', '"features": []'):
        raise ErrorPipeline("El GeoJSON no tiene ningún elemento.")


def _geometria_de(ruta: Path) -> str:
    """Tipo de geometría del primer feature, para clasificar la capa en el admin."""
    try:
        with ruta.open("r", encoding="utf-8", errors="replace") as fh:
            fragmento = fh.read(200_000)
    except OSError:
        return ""
    indice = fragmento.find('"geometry"')
    tipo = fragmento[indice : indice + 200] if indice >= 0 else ""
    if "Point" in tipo:
        return "punto"
    if "LineString" in tipo:
        return "linea"
    if "Polygon" in tipo:
        return "poligono"
    return ""


def _contar_lineas(ruta: Path) -> int:
    """GeoJSONSeq es una línea por feature, así que contar líneas es contar features."""
    with ruta.open("rb") as fh:
        return sum(1 for _ in fh)


# --- Centros poblados ------------------------------------------------------
def generar_ccpp() -> str:
    """`media/tiles/ccpp.pmtiles` desde la base de datos.

    El visor **no consume este tile** (usa GeoJSON agrupado, ADR-A13); se mantiene porque es la
    referencia del formato ancho y deja abierta una capa vectorial de CCPP para otros usos. Si
    se confirma que ningún consumidor lo necesita, es candidato a retirarse.
    """
    with tempfile.TemporaryDirectory() as tmp:
        intermedio = Path(tmp) / "ccpp.jsonl"
        total = escribir_geojsonseq_ccpp(intermedio)
        if total == 0:
            raise ErrorPipeline(
                "No hay centros poblados con coordenadas: importa primero el Excel de peligros."
            )

        tmp_pmtiles = Path(tmp) / "ccpp.pmtiles"
        _ejecutar(
            [
                settings.TIPPECANOE_BIN, "-o", str(tmp_pmtiles), "-l", "ccpp",
                # -Z3/-z12 y -r1 fijos: ver la cabecera del módulo.
                "-Z3", "-z12", "-r1", "--drop-densest-as-needed", "--generate-ids", "--force",
                str(intermedio),
            ],
            TIMEOUT_TIPPECANOE,
        )
        destino = _publicar(tmp_pmtiles, "ccpp.pmtiles")

    return f"{total:,} centros poblados, {destino.stat().st_size / 1e6:.1f} MB"


def escribir_geojsonseq_ccpp(destino: Path) -> int:
    """Formato ancho: una propiedad `nivel_<slug>` por peligro evaluado, más `nivel_max`.

    **Las claves ausentes no se escriben.** Solo 3,238 de los 8,968 CCPP tienen alguna
    clasificación; mandar `null` en las otras propiedades de cada punto multiplicaría el peso
    del tile sin añadir información, y "sin dato" tiene que seguir siendo distinguible de
    "nivel bajo".
    """
    from apps.peligros.models import ClasificacionPeligro
    from apps.territorio.models import CentroPoblado

    # Las 10,978 clasificaciones en una consulta, agrupadas en memoria: hacerlo por punto
    # serían 8,968 consultas sueltas.
    niveles: dict[int, dict[str, int]] = {}
    for ccpp_id, slug, nivel in ClasificacionPeligro.objects.values_list(
        "centro_poblado_id", "tipo_peligro__slug", "nivel"
    ):
        niveles.setdefault(ccpp_id, {})[f"nivel_{slug}"] = nivel

    escritos = 0
    consulta = (
        CentroPoblado.objects.exclude(lat=None)
        .exclude(lon=None)
        .select_related("distrito__provincia")
    )
    with destino.open("w", encoding="utf-8") as fh:
        for c in consulta.iterator(chunk_size=2000):
            propiedades = {
                "codigo": c.codigo,
                "nombre": c.nombre,
                "categoria": c.categoria,
                "distrito": c.distrito.nombre,
                "provincia": c.distrito.provincia.nombre,
                "ubigeo_distrito": c.distrito_id,
                "poblacion": c.poblacion or 0,
                "altitud": c.altitud,
            }
            if por_peligro := niveles.get(c.pk):
                propiedades.update(por_peligro)
                propiedades["nivel_max"] = max(por_peligro.values())
            fh.write(
                json.dumps(
                    {
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [c.lon, c.lat]},
                        "properties": propiedades,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            escritos += 1
    return escritos
