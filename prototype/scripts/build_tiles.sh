#!/usr/bin/env bash
# Genera los PMTiles del visor de peligros.
#
# Reproduce en local el pipeline que el backend correrá en su worker (ver _specs/05-mapas-tiles.md):
# recorte de las capas nacionales a Cusco con ogr2ogr, teselado con tippecanoe, salida PMTiles
# servida por HTTP Range. Aquí ambos binarios vienen en contenedores para no instalar GDAL ni
# tippecanoe en la máquina.
#
#   bash prototype/scripts/build_tiles.sh
#
# La salida (prototype/public/tiles/, ~6 MB) SÍ se versiona: /peligros depende de ella, así que
# un clon sin los tiles mostraría el visor en blanco y no todo el mundo tiene Docker.
#
# OJO: son un artefacto derivado. Si cambia Base_Nivel Peligro_CCPP_Cusco.xlsx o alguna capa de
# data/layers/, hay que volver a correr este script y commitear los .pmtiles resultantes, o el
# mapa quedará desincronizado de los JSON que ve la tabla. En la plataforma real esto no aplica:
# el worker de Django regenera los tiles tras cada importación (ver _specs/05-mapas-tiles.md).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LAYERS="$ROOT/data/layers"
OUT="$ROOT/prototype/public/tiles"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

GDAL_IMG="${GDAL_IMG:-ghcr.io/osgeo/gdal:alpine-small-latest}"
# Hace falta tippecanoe >= 2.17, que es donde aparece la escritura nativa de PMTiles. La imagen
# oficial de felt no es pública; esta trae v2.53. La de naxgrp sirve pero se quedó en v1.36.
TIPPE_IMG="${TIPPE_IMG:-emotionalcities/tippecanoe:latest}"

# Cusco: bbox tomado del padrón de centros poblados, con un margen.
BBOX_W=-74.1; BBOX_S=-15.6; BBOX_E=-70.3; BBOX_N=-11.2

mkdir -p "$OUT"

gdal() { docker run --rm -u "$(id -u):$(id -g)" -v "$ROOT:$ROOT" -v "$TMP:$TMP" -w "$ROOT" "$GDAL_IMG" "$@"; }
tippe() { docker run --rm -u "$(id -u):$(id -g)" -v "$ROOT:$ROOT" -v "$TMP:$TMP" -w "$ROOT" --entrypoint tippecanoe "$TIPPE_IMG" "$@"; }

echo "==> Descargando imágenes si hace falta"
docker image inspect "$GDAL_IMG" >/dev/null 2>&1 || docker pull "$GDAL_IMG"
docker image inspect "$TIPPE_IMG" >/dev/null 2>&1 || docker pull "$TIPPE_IMG"

# --- 1. Centros poblados (desde la BD del prototipo: los JSON generados) --------------------
echo "==> ccpp: generando GeoJSONSeq en formato ancho"
python3 "$ROOT/prototype/scripts/ccpp_to_geojsonseq.py" > "$TMP/ccpp.jsonl"

echo "==> ccpp: teselando"
# -r1 desactiva el descarte por densidad en los zooms bajos: queremos los 8,968 puntos siempre.
# El maxzoom va fijo en 12: con -zg tippecanoe deduce z6 a partir del espaciado medio, y a esa
# escala las coordenadas se cuantizan a ~150 m, suficiente para ver la mancha pero no para
# hacer clic en el centro poblado correcto.
tippe -o "$TMP/ccpp.pmtiles" -l ccpp -Z3 -z12 -r1 --drop-densest-as-needed --force "$TMP/ccpp.jsonl"

# --- 2. Capas cartográficas nacionales recortadas a Cusco -----------------------------------
# Ríos: el atributo de departamento viene en mayúsculas y es consistente.
echo "==> rios: recortando a Cusco (DN99='CUSCO')"
gdal ogr2ogr -f GeoJSONSeq "$TMP/rios.jsonl" "$LAYERS/rios.geojson" \
  -where "DN99='CUSCO'" -select "JER_HIDRO,DIN99,PN99"
echo "==> rios: teselando"
tippe -o "$TMP/rios.pmtiles" -l rios -Z6 -z13 --drop-densest-as-needed --force "$TMP/rios.jsonl"

# Lagunas: la fuente mezcla "Cusco" y "CUSCO"; comparar sin distinguir mayúsculas evita
# perder 73 de los 2,512 polígonos. El filtro -where de OGR no tiene UPPER(), pero sí ILIKE.
echo "==> lagunas: recortando a Cusco (DPTO ILIKE 'cusco')"
gdal ogr2ogr -f GeoJSONSeq "$TMP/lagunas.jsonl" "$LAYERS/lagos-y-lagunas.geojson" \
  -where "DPTO ILIKE 'cusco'" -select "NOMBRE,CUENCA,DISTRITO,PROVINCIA,ALTITUD"
echo "==> lagunas: teselando"
tippe -o "$TMP/lagunas.pmtiles" -l lagunas -Z6 -z13 --drop-densest-as-needed --force "$TMP/lagunas.jsonl"

# Glaciares: la capa viene proyectada en UTM 18S, no en lat/lon — sin -t_srs los tiles salen
# vacíos. Además no trae departamento, así que se acota por cordillera y por bbox.
echo "==> glaciares: reproyectando de EPSG:32718 a EPSG:4326 y recortando a Cusco"
gdal ogr2ogr -f GeoJSONSeq "$TMP/glaciares.jsonl" "$LAYERS/glaciares.geojson" \
  -t_srs EPSG:4326 \
  -where "cordillera IN ('Vilcanota','Vilcabamba','Urubamba','La Raya','Carabaya')" \
  -spat $BBOX_W $BBOX_S $BBOX_E $BBOX_N -spat_srs EPSG:4326 \
  -select "nomb_base,cordillera,cuenca,area_km2,alt_max"
echo "==> glaciares: teselando"
tippe -o "$TMP/glaciares.pmtiles" -l glaciares -Z6 -z13 --drop-densest-as-needed --force "$TMP/glaciares.jsonl"

# --- 3. Publicación -------------------------------------------------------------------------
for capa in ccpp rios lagunas glaciares; do
  mv "$TMP/$capa.pmtiles" "$OUT/$capa.pmtiles"
done

echo
echo "==> Listo. Tiles en prototype/public/tiles/:"
ls -lh "$OUT" | tail -n +2 | awk '{printf "    %-22s %s\n", $9, $5}'
