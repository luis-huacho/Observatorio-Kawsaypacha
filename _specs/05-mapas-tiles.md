# 05 — Mapas y Vector Tiles (Tippecanoe + PMTiles + MapLibre)

El visor migra de Leaflet (prototipo) a **MapLibre GL JS** (ADR-A7) consumiendo **PMTiles estáticos** (ADR-A5). Tippecanoe (≥2.17, escribe PMTiles nativo) y GDAL (`ogr2ogr`) se instalan en la imagen del backend (multi-stage); el worker ejecuta el pipeline. Salida: `media/tiles/{slug}.pmtiles`, servidos por Caddy con HTTP Range.

## Capas fuente reales (`data/layers/`)

**Son de escala NACIONAL y enormes** — el recorte a Cusco es obligatorio:

| Archivo | Tamaño | Features | En Cusco | Geometría | CRS | Filtro |
|---|---|---|---|---|---|---|
| `rios.geojson` | 57 MB | 33,950 | **3,164** | MultiLineString | EPSG:4326 | `DN99 = 'CUSCO'` (props: JER_HIDRO, DPD99, DIN99, PN99, DN99) |
| `lagos-y-lagunas.geojson` | 51 MB | 27,464 | **2,512** | MultiPolygon | EPSG:4326 | `DPTO ILIKE 'cusco'` (props: NOMBRE, CUENCA, DISTRITO, PROVINCIA, DPTO…) |
| `glaciares.geojson` | 32 MB | 3,067 | ~1,155 | MultiPolygon | **EPSG:32718** | sin campo dpto → cordillera + recorte espacial (props: nomb_base, cordillera, cuenca, area_km2, alt_max) |

Dos trampas verificadas contra los archivos reales:

- **`glaciares.geojson` NO está en lat/lon.** Viene proyectado en UTM 18S (`urn:ogc:def:crs:EPSG::32718`), con X entre 184k y 1,123k — toda la sierra peruana forzada a una sola zona. Sin `-t_srs EPSG:4326` en el `ogr2ogr`, tippecanoe recibe coordenadas fuera del rango geográfico y produce tiles vacíos. Verificado: tras reproyectar, la capa cae en lon −73.21…−70.25 / lat −14.55…−12.95.
- **El filtro de lagunas debe ignorar mayúsculas.** La fuente escribe `"Cusco"` (2,439) y `"CUSCO"` (73); comparar con `DPTO = 'Cusco'` pierde 73 polígonos. El `-where` de OGR no tiene `UPPER()`, pero sí `ILIKE`.

Cordilleras presentes en Cusco: Vilcanota (449), Vilcabamba (355), Urubamba (164), La Raya (35) y parte de Carabaya (191, compartida con Puno).

Reemplazan a los `*.demo.geojson` del prototipo (lagunas/rios/nevados → glaciares). Polígono regional para clip: `backend/apps/mapas/fixtures/cusco_region.geojson` — **todavía no existe en el repo**; hay que obtenerlo de una fuente pública (INEI, geoBoundaries ADM1). Mientras tanto, `prototype/scripts/build_tiles.sh` acota glaciares con `cordillera IN (…)` + `-spat` sobre el bbox regional, que es suficiente para la demo pero no para producción.

## Pipeline: capas subidas por admin

Disparo: guardar `CapaCartografica` con archivo nuevo, o acción "(Re)generar tiles". Tarea en worker:

1. **Validación**: JSON parseable, `FeatureCollection` con features y geometrías.
2. **Reproyección**: `-t_srs EPSG:4326` **siempre**, incondicionalmente. ogr2ogr lee el CRS declarado en el archivo y no hace nada si ya es geográfico, así que el coste es cero y cubre capas proyectadas como glaciares. Registrar en el log el CRS de origen detectado.
3. **Recorte a Cusco**:
   - con `filtro_atributo` definido (`DN99=CUSCO`): `ogr2ogr -f GeoJSONSeq /tmp/{slug}.jsonl in.geojson -where "DN99='CUSCO'"`. El campo admite `ILIKE` para fuentes con mayúsculas inconsistentes.
   - sin filtro: `ogr2ogr -clipsrc cusco_region.geojson …`
4. **Simplificación** opcional (`simplificacion` de la capa): `-simplify <tol>`; tippecanoe aplica además la suya por zoom.
5. **Tiles**: `tippecanoe -o /tmp/{slug}.tmp.pmtiles -l {slug} -Z{min_zoom} -z{max_zoom} --drop-densest-as-needed --generate-ids --force /tmp/{slug}.jsonl` (si `max_zoom` nulo: `-zg`). Requiere **tippecanoe ≥ 2.17**, que es donde aparece la escritura nativa de PMTiles; con versiones anteriores hay que pasar por MBTiles y convertir.
6. **Swap atómico**: `mv` a `media/tiles/{slug}.pmtiles` (rename en el mismo volumen) — el mapa público nunca ve un tile corrupto.
7. `estado_tiles=ok` + log de tippecanoe; en fallo `estado_tiles=error` + `log_error`.

## Capa CCPP desde la BD (la capa central del visor)

No es una CapaCartografica: comando `manage.py generar_tiles_ccpp` (encadenado tras cada import de `peligros_ccpp`; también botón en admin).

1. Query pivotada: CCPP × nivel por peligro (formato **ancho**).
2. Emite GeoJSONSeq de Points por stdin a tippecanoe. **Las claves ausentes no se escriben**: solo 3,238 de los 8,968 CCPP tienen alguna clasificación, y omitirlas en vez de mandar `null` reduce mucho el tile.
```json
{ "type": "Feature", "geometry": { "type": "Point", "coordinates": [-71.9767, -13.5192] },
  "properties": { "codigo": "0801010001", "nombre": "CUSCO", "categoria": "CIUDAD",
    "distrito": "CUSCO", "provincia": "CUSCO", "ubigeo_distrito": "080101",
    "poblacion": 111930, "altitud": 3439,
    "nivel_sismo": 4, "nivel_max": 4 } }
```
Los nueve slugs, que deben coincidir con `TipoPeligro.slug` y con `PELIGROS` en `frontend/src/lib/types.ts`: `nivel_sismo`, `nivel_heladas`, `nivel_bajas_temperaturas`, `nivel_friaje`, `nivel_sequia`, **`nivel_lluvias_intensas`**, `nivel_inundacion`, **`nivel_incendios_forestales`**, `nivel_movimientos_en_masa`, más `nivel_max`.

3. `tippecanoe -o ccpp.tmp.pmtiles -l ccpp -Z3 -z12 -r1 --drop-densest-as-needed --force` → swap a `media/tiles/ccpp.pmtiles`. `-r1` conserva todos los puntos en los zooms bajos. **El maxzoom va explícito**: con `-zg` tippecanoe deduce z6 a partir del espaciado medio de los CCPP, y a esa escala las coordenadas se cuantizan a ~150 m — se ve bien pero el clic cae en el punto equivocado. Referencia: con `-z12` el tile pesa 2.7 MB.

El formato ancho permite al frontend **filtrar y colorear con expresiones MapLibre sin round-trips** al cambiar peligro/nivel. El `coalesce(…, 0)` es lo que mantiene "sin dato" como categoría propia y no como nivel bajo:
```js
paint: { "circle-color": ["match", ["coalesce", ["get", `nivel_${slug}`], 0],
         1, C.level1, 2, C.level2, 3, C.level3, 4, C.level4, /*sin dato*/ C.sinDato ] }
filter: [">=", ["coalesce", ["get", `nivel_${slug}`], 0], nivelMin]
```

Implementación de referencia ya validada en local: `prototype/scripts/ccpp_to_geojsonseq.py` (emisor del formato ancho) y `prototype/scripts/build_tiles.sh` (pipeline completo con ogr2ogr y tippecanoe en contenedores).

## Servido

Caddy sirve `/tiles/*` desde el volumen `media/tiles/` como estático: `Accept-Ranges` nativo, `Cache-Control: public, max-age=3600`. Mismo origen → sin CORS. Sin tileserver.

## Frontend (MapLibre)

- Deps: `maplibre-gl` + `pmtiles`. Registro una vez: `maplibregl.addProtocol("pmtiles", new pmtiles.Protocol().tile)`.
- Basemap: **cuatro mapas base conmutables**, cada uno con su fuente ráster y su capa, todas declaradas en el estilo y solo una visible. Se prefiere esto a reescribir una fuente única con `setTiles()`: las fuentes sin capa visible no descargan teselas (verificado en red), y el `AttributionControl` solo publica las que están en uso, así que la atribución cambia sola al conmutar.

  | id | Nombre | maxzoom | Nota |
  |---|---|---|---|
  | `osm` | OpenStreetMap | 19 | **por defecto** |
  | `claro` | Claro (CARTO light) | 20 | fondo neutro, el que mejor deja leer el semáforo |
  | `satelite` | Satélite (Esri World Imagery) | 19 | la URL es `/{z}/{y}/{x}`, no `/{z}/{x}/{y}` |
  | `topografico` | Topográfico (OpenTopoMap) | 17 | relieve; útil para huaycos y movimientos en masa |

  `maxzoom` por fuente hace que MapLibre sobre-escale el último nivel disponible en vez de pedir teselas inexistentes. **OpenTopoMap es un servicio voluntario con política de uso restrictiva**: vale para el prototipo, pero en producción hay que sustituirlo por una fuente propia o con contrato. Los cuatro envían cabeceras CORS, así que la exportación PNG funciona con todos (comprobado); aun así el control captura `SecurityError` y avisa al usuario, porque las capas son administrables y el catálogo puede crecer.
- Al montar, `GET /api/mapas/capas/` → por cada capa: `addSource(slug, { type: "vector", url: "pmtiles://" + VITE_TILES_URL + "/" + slug + ".pmtiles" })` + layer con paint derivado de `estilo` (JSON del admin → reemplazo de capas sin tocar código, requisito TDR). Fuente `ccpp` siempre presente.
- `MapaPeligros.tsx` y `MapaControles.ts` se portan del prototipo. Controles ya implementados: buscador de lugar (en `frontend/` pasa a alimentarse del índice Meili `ccpp` en vez del padrón en memoria) + `flyTo`, medición de distancia/área, exportar PNG, selector de mapa base + conmutador de capas en un solo panel, leyenda semáforo, vista inicial y pantalla completa.
- Popups: `queryRenderedFeatures` con las props del tile; ficha completa desde `/api/ccpp/{codigo}/`.
- Colores nivel 1-4: tokens `level-1..4` de `tailwind.config.ts` del prototipo.

### Implementación de referencia (`prototype/src/components/MapaPeligros.tsx`)

**La migración ya está hecha en el prototipo**: `/peligros` corre sobre MapLibre + PMTiles y el visor Leaflet fue eliminado junto con sus dependencias (`leaflet`, `react-leaflet`, `html-to-image`). Para `frontend/` el trabajo es portar el componente cambiando el origen de datos (JSON estáticos → API + `/api/mapas/capas/`), no reescribirlo.

Lo que costó y conviene no volver a descubrir:

- **El mapa se crea con `preserveDrawingBuffer: true`.** Sin eso, `map.getCanvas().toDataURL()` devuelve un PNG en blanco. Además hay que forzar un `triggerRepaint()` y leer el canvas dentro de un `once("render")`.
- **Los controles se añaden antes de que el estilo cargue.** Cualquier `addSource`/`addLayer`/`setPaintProperty` en `IControl.onAdd` o en un efecto lanza *"Style is not done loading"*. Todo cambio de estilo pasa por un guard `map.isStyleLoaded() ? fn() : map.once("load", fn)`.
- **`addProtocol("pmtiles", …)` se registra una vez por sesión**, no por instancia de mapa.
- **Filtrar por distrito no basta**: hay que mover la cámara (`fitBounds` sobre los CCPP del distrito), o el usuario se queda mirando toda la región con casi todo oculto.
- Los enlaces dentro de un popup no pueden ser `<a href>` — recargarían la SPA. Se usa un `<button>` con un handler que llama a `navigate()` del router.
- El buscador de lugares necesita `stopPropagation` de `keydown` en su contenedor; si no, teclear dispara los atajos de teclado de MapLibre.
- **`circle-stroke-opacity` es independiente de `circle-opacity`** y vale 1 por defecto. Con el relleno atenuado y el anillo opaco, los 5,730 puntos sin clasificar se funden en una mancha blanca, muy visible sobre ortofoto. Hay que atenuar ambas con la misma expresión.
- Cada propiedad de pintado debe tener **un solo efecto que la escriba**. Al añadir el selector de base tuvimos dos efectos tocando `circle-opacity` con dependencias distintas, y el resultado dependía de cuál corriera último.

En el prototipo los `.pmtiles` **se versionan** (`prototype/public/tiles/`, ~6 MB): sin ellos el visor sale en blanco y no todo el mundo tiene Docker para regenerarlos. Es un artefacto derivado que hay que rehacer y commitear cuando cambie el Excel de peligros o una capa. En la plataforma real el problema desaparece: el worker regenera los tiles al final de cada `DatasetUpload`.
