# 05 — Mapas y Vector Tiles (Tippecanoe + PMTiles + MapLibre)

El visor migra de Leaflet (prototipo) a **MapLibre GL JS** (ADR-A7) consumiendo **PMTiles estáticos** (ADR-A5). Tippecanoe (≥2.17, escribe PMTiles nativo) y GDAL (`ogr2ogr`) se instalan en la imagen del backend (multi-stage); el worker ejecuta el pipeline. Salida: `media/tiles/{slug}.pmtiles`, servidos por nginx con HTTP Range.

## Capas fuente reales (`data/layers/`)

**Son de escala NACIONAL y enormes** — el recorte a Cusco es obligatorio:

| Archivo | Tamaño | Features | En Cusco | Geometría | CRS | Filtro |
|---|---|---|---|---|---|---|
| `rios.geojson` | 57 MB | 33,950 | **3,164** | MultiLineString | EPSG:4326 | `DN99 = 'CUSCO'` (props: JER_HIDRO, DPD99, DIN99, PN99, DN99) |
| `lagos-y-lagunas.geojson` | 51 MB | 27,464 | **2,512** | MultiPolygon | EPSG:4326 | `DPTO ILIKE 'cusco'` (props: NOMBRE, CUENCA, DISTRITO, PROVINCIA, DPTO…) |
| `glaciares.geojson` | 32 MB | 3,067 | ~1,155 | MultiPolygon | **EPSG:32718** | sin campo dpto → cordillera + recorte espacial (props: nomb_base, cordillera, cuenca, area_km2, alt_max) |

Dos particularidades de los archivos, **con una corrección importante del 03/08/2026**:

- **`glaciares.geojson` está guardado en UTM 18S** (`EPSG:32718`), con X entre 184k y 1,123k — toda la sierra peruana forzada a una sola zona. Este spec afirmaba que sin `-t_srs EPSG:4326` los tiles saldrían vacíos. **Medido con GDAL 3.10.3: no ocurre.** El driver GeoJSON de OGR reproyecta a WGS84 por su cuenta al escribir la salida, porque RFC 7946 obliga a que un GeoJSON esté en WGS84; con y sin `-t_srs` el `.jsonl` sale idéntico (mismas coordenadas, mismo tile de 108,439 bytes, cero avisos de tippecanoe).
- **El filtro de lagunas con `ILIKE`.** La fuente sí escribe `"Cusco"` (2,439) y `"CUSCO"` (73). Este spec afirmaba que `DPTO = 'Cusco'` pierde esos 73. **Medido: tampoco ocurre** — el `-where` de OGR sobre el driver GeoJSON compara texto sin distinguir mayúsculas, y las dos formas devuelven los 2,512.

**Aun así el pipeline mantiene `-t_srs EPSG:4326` incondicional y el `ILIKE`.** No por las razones de arriba, sino porque ambas hacen explícita la intención y no dependen de un detalle de implementación del driver: el `=` insensible a mayúsculas del filtro de atributos de OGR no está documentado como garantía y no se cumple con un backend SQL real, y la reproyección automática solo aplica a formatos de salida que exigen WGS84. Escribir la intención cuesta dos palabras; descubrir por qué un tile sale vacío costó una tarde.

**Hallazgo nuevo para devolver al cliente**: 4 lagunas tienen `DPTO` compuesto (`Arequipa/Cusco`, `Madre deDios/Cusco`, `Cusco/Junin`) y ningún filtro por departamento las captura. Son cuerpos de agua que cruzan el límite regional; 2,516 mencionan Cusco de alguna forma frente a los 2,512 que entran.

Cordilleras presentes en Cusco: Vilcanota (449), Vilcabamba (355), Urubamba (164), La Raya (35) y parte de Carabaya (191, compartida con Puno).

Reemplazan a los `*.demo.geojson` del prototipo (lagunas/rios/nevados → glaciares).

**Polígono regional para el clip: resuelto (03/08/2026).** Vive en `backend/apps/mapas/datos/cusco_region.geojson` (21 KB, 485 vértices), extraído de geoBoundaries gbOpen ADM1 (CC BY 4.0); la atribución va dentro del propio archivo, que es el único sitio donde sobrevive a una copia. Bbox verificado: lon −73.98…−70.35 / lat −15.47…−11.24, que contiene el rango de glaciares del spec. Sigue siendo **provisional**: se sustituye por el polígono oficial del INEI cuando PREDES lo entregue. Glaciares se acota además por `cordillera IN (…)` y por `-spat` sobre el bbox regional, como pre-filtro barato antes del `-clipsrc`.

## Límites administrativos (ADR-A20)

Dos capas más, por el **mismo pipeline** que ríos, lagunas y glaciares: se descarga el GeoJSON
una vez a `data/layers/`, `seed --capas` lo adjunta y tippecanoe publica el `.pmtiles`. **El
visitante nunca sale al origen**; los tiles los sirve nuestro nginx como los demás.

| Capa | Filtro | Features en Cusco | Tile | Por defecto |
|---|---|---|---|---|
| `limites-provinciales` | `CCDD=08` | 13 | 0.5 MB | **visible** |
| `limites-distritales` | `CCDD=08` | 112 | 1.1 MB | oculta |

Fuente: **`josedaniel-cb/limites-peru-geojson`** (MIT), archivos `LIM_PROVINCIAL_PERU.json` y
`LIM_DISTRITAL_PERU.json`. Se usa la versión **completa y no la `_MIN`**: la simplificada tiene
mediana de 46 vértices por distrito y se ve angulosa al acercarse, y tippecanoe ya simplifica
por zoom — partir de la `_MIN` sería simplificar dos veces.

Traen **`UBIGEO` por distrito**, y ahí está lo que las hace útiles más allá de dibujar: los 112
distritos y las 13 provincias de Cusco **casan exactamente** con el padrón, sin sobrantes ni
faltantes. Eso es lo que permite calcular el centroide de cada distrito (ver 01).

Estilo de **solo contorno** (`fill-opacity: 0`): un relleno taparía ríos, lagunas y los propios
centros poblados. La provincial va más marcada que la distrital para poder distinguirlas
superpuestas, y las dos con `orden` 0 y 1 para dibujarse por debajo de todo lo demás.

### El coroplético de Inversión (ADR-D6)

`MapaInversion.tsx` reutiliza estas dos capas, y es el segundo consumidor que tienen. Cuatro
cosas que hay que saber antes de tocarlo:

- **Las llaves son `UBIGEO` (6 dígitos, distrito) e `IDPROV` (4, provincia)**, y casan sin
  traducción con `Distrito.ubigeo` y `Provincia.ubigeo`. Sobreviven a tippecanoe porque
  `ATRIBUTOS` de `pipeline.py` **no tiene entrada para estas capas**: sin `-select`, ogr2ogr
  conserva todos los campos. Añadir una entrada para adelgazar el tile rompería el mapa.
- **El color se calcula en JavaScript y se inyecta como `["match", ["get", "UBIGEO"], …]`**, con
  una rama por polígono. Los tiles solo traen geometría y códigos; el dinero llega por el API.
  Se descartó `feature-state`, que exigiría `promoteId`, volver a aplicar el estado en cada
  `sourcedata` y que aun así solo alcanza a los tiles ya cargados.
- **El componente no hereda el `estilo` del catálogo**, que es de contorno con `fill-opacity: 0`
  a propósito. Monta su propio `fill` y su propio `line`.
- **Las dos capas se montan a la vez y se conmuta su visibilidad.** Reconstruir la fuente al
  cambiar de nivel deja una ventana en la que el estilo todavía no está cargado, y ahí las
  mutaciones de `paint` se pierden **sin dar ningún error**.

### El coroplético en el PDF

El reporte de inversión incrusta este mismo mapa, capturado con Chromium headless por
**`templates/informes/mapa_inversion.html`** — el hermano de `mapa.html`, con el mismo protocolo
(`__mapaListo` / `__mapaError` / `__mapaAvisos`) y las mismas trampas ya documentadas:
`preserveDrawingBuffer: true` y URL reescritas contra el origen de la propia página.

Dos diferencias con el visor de peligros que sí son decisiones:

- **Sin mapa base.** Un coroplético sobre teselas de OSM se lee peor —los colores compiten con el
  fondo— y ahorra depender de un servicio externo justo cuando alguien necesita el documento.
- **Encuadre fijo de la región**, no ajustado a lo pintado: los tiles no entregan sus geometrías
  hasta estar cargados, y perseguir el encuadre dispararía otra ronda de carga justo cuando la
  captura espera el `idle`. Con un filtro de provincia se ve la provincia pintada dentro de
  Cusco, que además avisa al lector de que está viendo un recorte.

**La rampa de color no se declara en la plantilla**: viene de `apps/informes/escalas.py`, que es
también de donde la lee la leyenda del PDF. Un mapa y su propia leyenda desincronizados serían un
documento que miente sin que nada falle. Queda una copia en `MapaInversion.tsx`, que es la
frontera frontend/backend de siempre.

El registro del protocolo `pmtiles://` vive en **`frontend/src/lib/pmtiles.ts`** desde que hay
dos mapas con tiles. Estaba en un `let` de módulo dentro de `MapaPeligros`, y con dos
componentes cada uno tendría su bandera y registraría su propio `Protocol`: el segundo pisa al
primero y quedan dos cachés de tiles vivas, otra vez sin que MapLibre se queje.

> **Por qué no el WMS de GeoPerú.** Se evaluó
> `espacialg.geoperu.gob.pe/geoserver/geoperu/peru_distrito_/wms`, que publica los mismos
> límites. Responde en 0.2 s y tiene CORS abierto, pero **su WFS está bloqueado (403 en
> `/geoperu/wfs`, `/geoserver/wfs` y `/ows`)**, así que no da geometría —no serviría para los
> centroides— y **prohíbe estilos propios** («Dynamic style usage is forbidden»): solo hay dos
> publicados, uno con etiquetas y relleno azulado y otro con relleno gris opaco, ninguno de
> solo líneas. Además obligaría a depender de un tercero en cada carga del visor. Queda
> registrado para no reabrir la vía.

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

## Capa CCPP: GeoJSON agrupado, no tile vectorial

> **Cambio respecto de la versión anterior de este spec.** Los centros poblados del visor **ya no
> se leen de `ccpp.pmtiles`**. El dueño del proyecto pidió *marker clustering* (entonces con
> símbolos proporcionales a población, que ADR-A17 retiró después), y **MapLibre solo agrupa
> fuentes `geojson`**: no existe clustering
> sobre fuentes vectoriales, ni parámetro que lo habilite. Las capas de contexto (ríos, lagunas,
> glaciares) siguen en PMTiles sin cambios; la excepción es únicamente la capa CCPP.
>
> Consecuencias que arrastra la decisión, verificadas en el prototipo:
>
> - **El filtrado no puede ir por `setFilter`.** Supercluster agrupa la fuente entera *antes* de
>   que la capa aplique su filtro, así que los grupos siguen dibujándose donde y como los dictan
>   los puntos descartados. Se filtra reemplazando los datos con `setData`.
>   *Matiz (ADR-A16)*: lo que un grupo **dice** ya no depende de `point_count` sino de agregados
>   calculados por punto, y esos sí distinguen quién cumple. Por eso el conmutador de «sin
>   clasificación» sí puede ir por `setFilter` —solo esconde, no recuenta—, mientras que los
>   filtros de la página siguen yendo por `setData`.
> - **Las propiedades de un feature agrupado deben ser escalares.** Lo que no lo sea (el desglose
>   de peligros del popup) viaja serializado con `JSON.stringify`.
> - **El formato ancho `nivel_<slug>` deja de hacer falta en el cliente**, porque la fuente se
>   construye ya filtrada: cada punto lleva un solo campo `nivel` con el máximo de los peligros que
>   sobrevivieron a los filtros, y `0` para "sin dato".
> - En el prototipo la fuente se arma en `Peligros.tsx` desde los JSON ya cargados, de modo que el
>   mapa hereda **exactamente** los mismos filtros que la tabla. Esto corrigió una desalineación
>   real: el visor solo conocía el ubigeo del distrito, así que al elegir únicamente una provincia
>   seguía dibujando toda la región mientras la tabla sí se recortaba.
>
> **Resuelto (03/08/2026)**: el GeoJSON sale de **`GET /api/ccpp/geojson/`**, que acepta los mismos
> filtros que `/api/ccpp/` y devuelve el `FeatureCollection` completo que pasa el filtro, sin
> paginar, con un único `nivel` por punto y el desglose serializado para el popup. Contrato y
> justificación del tamaño en 02. Se descartó agrupar en servidor por zoom/bbox: obliga a
> reimplementar supercluster en Python y a pedir datos en cada paneo; queda como salida si el
> payload llegara a molestar.

### Los canales del símbolo (ADR-A17)

**Un punto suelto muestra TODOS sus peligros**: un ícono por cada uno, repartidos en corona
sobre la ubicación, donde la FORMA dice el tipo y el COLOR dice el nivel. Ni el tamaño ni la
población entran ya en la ecuación.

Se dibujaban todos porque dibujar solo el peor escondía la mayor parte de lo evaluado: **2,372
de los 3,238 centros poblados clasificados tienen tres o más peligros**, y el máximo es siete.
Como los sueltos solo aparecen por encima del zoom de agrupación, hay sitio para desplegarlos.

| canal | qué dice | cómo |
|---|---|---|
| ícono | **un ícono por peligro**, repartidos en corona sobre la ubicación | Una capa `symbol` por ranura (`ccpp-peligro-0`…`ccpp-peligro-8`), cada una leyendo `s<k>` / `n_<k>`. MapLibre dibuja un símbolo por capa y feature, así que mostrar N peligros exige N capas: no hay forma de que una sola itere sobre una lista |
| posición | la ranura `k` dentro de una corona de `total` peligros | `icon-offset` con un `match` sobre `clasificaciones`. **No** se puede calcular: MapLibre no sabe construir un array de dos números a partir de dos expresiones, y los pares del `match` van envueltos en `["literal", …]` o rechaza la capa entera |
| ancla | dónde está el lugar de verdad | Capa `circle` de 2 px (`ccpp-ancla`) cuando hay más de un peligro: con la corona el centro queda vacío y, entre centros poblados vecinos, no se distingue de quién es cada ícono |
| color | nivel 1-4 | horneado en la imagen: 36 bitmaps (9 tipos × 4 niveles) |
| gris liso | sin clasificación | capa `circle` aparte (`ccpp-sin-dato`), sin ícono: darle uno lo haría parecer evaluado |

**Por qué 36 imágenes rasterizadas y no SDF.** Con `{sdf: true}` bastaría una por tipo y el color
saldría de `icon-color`, pero SDF resuelve mal los íconos de **trazo** como los de lucide: adelgaza
el contorno hasta hacerlo ilegible al tamaño de un punto de mapa. 36 bitmaps de 88×88 no cuestan
nada y dan control total sobre el disco, el anillo y el grosor.

**La población salió como canal visual.** La fuente la trae y el reparto real es este —948 CCPP con
0 y mediana 17 habitantes—, así que 6,419 de 8,968 caían en los dos peldaños más pequeños y el
tamaño no distinguía casi nada. Peor: el diámetro hablaba de población y el número de
clasificaciones, dos cosas distintas en el mismo círculo.

**El círculo agrupado codifica tres variables y ninguna es «cuántos puntos hay»** (ADR-A16, con el
tamaño revisado por A17):

| canal | qué dice | `clusterProperties` |
|---|---|---|
| número | clasificaciones que pasan los filtros | `clasif` = `["+", ["coalesce", ["get","clasificaciones"], 0]]` |
| tamaño | **lo mismo que el número** — así los dos hablan del mismo conjunto | `clasif`, escala `step` 9→26 px |
| color | el **peor** nivel que contiene | `nivelMax` = `["max", ["coalesce", ["get","nivel"], 0]]` |
| desglose | de qué niveles y de qué tipos está hecho el grupo | `niv1..niv4` y `t_<slug>`, sumas de las `n<k>` / `p_<slug>` del feature |

```js
cluster: true, clusterRadius: 50, clusterMaxZoom: 12,
clusterProperties: {
  clasif:   ["+",   ["coalesce", ["get", "clasificaciones"], 0]],
  nivelMax: ["max", ["coalesce", ["get", "nivel"],           0]],
  niv1: ["+", ["coalesce", ["get","n1"], 0]],  // … niv2, niv3, niv4
  ...Object.fromEntries(tipos.map(t => [`t_${t.slug}`,
        ["+", ["coalesce", ["get", `p_${t.slug}`], 0]]])),
}
```

MapLibre solo sabe acumular escalares que **ya vengan en el feature**, así que sin `n<k>` y
`p_<slug>` un grupo no puede decir de qué está hecho. El API los emite **solo cuando no son cero**:
el punto medio tiene 1.2 clasificaciones, y trece ceros por feature engordarían un payload de 2 MB
sin aportar nada.

**Por qué el número no es `point_count`.** Cuenta lo que hay en la fuente, y la fuente no se
recorta con los filtros: los que no cumplen se quedan para pintarse en gris (`clasificados=1` es
cosa de la tabla, no del visor). Con «Heladas · nivel 4» puesto, el grupo seguía diciendo lo mismo
que sin filtros mientras la tabla ya había encogido. Sumando `clasificaciones` —que el API calcula
**ya filtrada**— el número sí reacciona. Efecto secundario: el mapa cuenta en la unidad de las
10,978 y la tabla en la de las 3,238, así que la pantalla muestra las dos rotuladas (ver 06).

Un grupo sin ninguna clasificación se dibuja **sin número**: el gris ya dice «sin dato», y un «0»
se leería como «evaluado, y sin peligro».

### La capa de emergencias (ADR-A18)

Fuente `emergencias`, **sin clustering**: son como mucho 65 puntos, uno por distrito con
registro, y agruparlos escondería justo lo que la capa viene a mostrar. Se enciende y apaga con
`visibility`, no recreando la fuente.

**El símbolo es único y deliberadamente distinto del de exposición**, en los tres canales a la
vez, porque comparten mapa y son ejes que no se mezclan:

| | Exposición | Emergencias |
|---|---|---|
| fondo | círculo | **cuadrado redondeado** |
| color | escala de nivel (verde→rojo) | **`mountain-900` fijo**, fuera de esa escala |
| ícono | uno por tipo de peligro (9) | **`Siren`, siempre el mismo** |
| unidad | centro poblado | distrito |

Si compartiera cualquiera de los tres, un ícono de emergencia sobre un distrito se leería como
un décimo peligro o como un nivel más. La leyenda lo separa en su propio bloque por lo mismo.

**El punto no es una ubicación real del suceso**: es la mediana de lat/lon de los centros
poblados del distrito, porque no hay geometría distrital en el proyecto (`Distrito` no tiene
coordenadas y no existe ninguna capa de límites administrativos, solo el polígono departamental
del recorte). Mediana y no promedio: en los distritos de selva los centros poblados se reparten
a lo largo de los ríos y el promedio se va detrás de la cola. El popup habla del distrito, no
del punto.

#### Dos gotchas que no dan ningún error

1. **`icon-allow-overlap` es obligatorio.** Sin él, el motor de etiquetado de MapLibre descarta por
   colisión la mayoría de los 3,238 símbolos y el visor se ve medio vacío **sin una sola línea en
   consola**. Va con `icon-ignore-placement: true`.
2. **La capa `symbol` se añade DESPUÉS de registrar las imágenes**, no en el estilo inicial. Un
   `icon-image` que apunta a una imagen inexistente emite un error *por punto* y no dibuja nada.
   Como red de seguridad hay un `styleimagemissing` que registra un píxel blanco, de modo que un
   ícono que falle degrada a punto liso en vez de desaparecer.

Cuatro capas sobre la misma fuente: `ccpp-sin-dato` (suelto y `clasificaciones == 0`, círculo
gris), `ccpp-puntos` (suelto y `clasificaciones > 0`, **`symbol`** con el ícono del tipo),
`ccpp-clusters` y `ccpp-clusters-num` (`["has","point_count"]`). Los sueltos van **debajo** del
cluster: a zoom intermedio conviven y el grupo resume más información. `symbol-sort-key` =
`["-", 4, ["get","nivel"]]` para que donde se solapen gane el más grave. Clic en cluster →
`getClusterExpansionZoom` + `easeTo`.

**El conmutador «Mostrar sin clasificación» va por `setFilter`, no por `setData`.** Los agregados
del grupo ya dejan fuera a los sin dato, así que el conmutador solo decide qué se dibuja: se le
añade `[">", ["get","clasif"], 0]` a las capas de grupo y el equivalente sobre `clasificaciones` a
la de puntos sueltos. Ojo, **ocultarlos no reagrupa**: un grupo con 3 sin dato y 2 clasificados
sigue siendo un solo círculo en el mismo sitio, rotulado 2. Es correcto —supercluster agrupa antes
de que la capa filtre— y es la razón de no tocar los datos: con `setData` el número cambiaría al
ocultar, y el usuario leería dos cifras distintas para lo mismo.

**Cada canal necesita su clave en la leyenda.** Sin rotularlos, un círculo grande se lee como «más
peligroso» en vez de «más gente expuesta», y el número como «cuántos pueblos hay».

### Pipeline de tiles CCPP (se mantiene, pero ya no alimenta el visor)

El comando sigue existiendo y el tile se sigue generando: es la referencia del formato ancho y deja
la puerta abierta a una capa vectorial de CCPP para otros usos. Simplemente **el visor no lo
consume**. Si se confirma que ningún consumidor lo necesita, es candidato a retirarse.

No es una CapaCartografica: comando `manage.py generar_tiles_ccpp` (encadenado tras cada import de `peligros_ccpp`; también botón en admin).

1. Query pivotada: CCPP × nivel por peligro (formato **ancho**).
2. Emite GeoJSONSeq de Points por stdin a tippecanoe. **Las claves ausentes no se escriben**: solo 3,238 de los 8,968 CCPP tienen alguna clasificación, y omitirlas en vez de mandar `null` reduce mucho el tile.
```json
{ "type": "Feature", "geometry": { "type": "Point", "coordinates": [-71.9767, -13.5192] },
  "properties": { "codigo": "0801010001", "nombre": "CUSCO", "categoria": "CIUDAD",
    "distrito": "CUSCO", "provincia": "CUSCO", "ubigeo_distrito": "080101",
    "altitud": 3439, "peligro": "sismo", "n4": 1, "p_sismo": 1,
    "nivel_sismo": 4, "nivel_max": 4 } }
```
Los nueve slugs, que deben coincidir con `TipoPeligro.slug` y con `PELIGROS` en `frontend/src/lib/types.ts`: `nivel_sismo`, `nivel_heladas`, `nivel_bajas_temperaturas`, `nivel_friaje`, `nivel_sequia`, **`nivel_lluvias_intensas`**, `nivel_inundacion`, **`nivel_incendios_forestales`**, `nivel_movimientos_en_masa`, más `nivel_max`.

3. `tippecanoe -o ccpp.tmp.pmtiles -l ccpp -Z3 -z12 -r1 --drop-densest-as-needed --force` → swap a `media/tiles/ccpp.pmtiles`. `-r1` conserva todos los puntos en los zooms bajos. **El maxzoom va explícito**: con `-zg` tippecanoe deduce z6 a partir del espaciado medio de los CCPP, y a esa escala las coordenadas se cuantizan a ~150 m — se ve bien pero el clic cae en el punto equivocado. Referencia: con `-z12` el tile pesa 2.7 MB.

El formato ancho se diseñó para que el frontend **filtrara y coloreara con expresiones MapLibre sin
round-trips** al cambiar peligro/nivel. Con la capa CCPP servida como GeoJSON agrupado eso ya no
aplica al visor: el filtro por peligro y por nivel se resuelve al construir la fuente, y cada punto
llega con un único `nivel`. Lo que **sí** sobrevive es el `coalesce(…, 0)`, que es lo que mantiene
"sin dato" como categoría propia y no como nivel bajo:
```js
paint: { "circle-color": ["match", ["coalesce", ["get", "nivel"], 0],
         1, C.level1, 2, C.level2, 3, C.level3, 4, C.level4, /*sin dato*/ C.sinDato ] }
```

Implementación de referencia ya validada en local: `prototype/scripts/ccpp_to_geojsonseq.py` (emisor del formato ancho) y `prototype/scripts/build_tiles.sh` (pipeline completo con ogr2ogr y tippecanoe en contenedores).

## Servido

**nginx** sirve `/tiles/*` desde el volumen `media/tiles/` como estático, bajo el dominio del backend (`obs.predes.org.pe`): `Accept-Ranges bytes`, `Cache-Control: public, max-age=3600` y **cabeceras CORS** para el dominio público — con dos dominios (ADR-A14) el visor lee los tiles cross-origin, y sin `Access-Control-Expose-Headers: Content-Length,Content-Range` el protocolo `pmtiles://` no puede leer por rangos. Sin tileserver.

## Frontend (MapLibre)

- Deps: `maplibre-gl` + `pmtiles`. Registro una vez: `maplibregl.addProtocol("pmtiles", new pmtiles.Protocol().tile)`.
- Basemap: **cuatro mapas base conmutables**, cada uno con su fuente ráster y su capa, todas declaradas en el estilo y solo una visible. Se prefiere esto a reescribir una fuente única con `setTiles()`: las fuentes sin capa visible no descargan teselas (verificado en red), y el `AttributionControl` solo publica las que están en uso, así que la atribución cambia sola al conmutar.

  | id | Nombre | maxzoom | Nota |
  |---|---|---|---|
  | `osm` | OpenStreetMap | 19 | **por defecto** |
  | `claro` | Claro (CARTO `light_all`) | 20 | fondo neutro, el que mejor deja leer el semáforo; **exige llave** |
  | `satelite` | Satélite (Esri World Imagery) | 19 | la URL es `/{z}/{y}/{x}`, no `/{z}/{x}/{y}` |
  | `topografico` | Topográfico (OpenTopoMap) | 17 | relieve; útil para huaycos y movimientos en masa |

  **CARTO exige llave desde 08/2026**, y sin ella estampa una marca de agua en diagonal sobre cada tesela (medido: 1.6 % de los píxeles, agrupados en la banda central). La llave viaja en `VITE_CARTO_KEY` —artefacto de *build*, como la de Meilisearch— y las URL se arman en un solo sitio, `frontend/src/lib/mapasBase.ts`, porque la ficha del centro poblado usa este mismo fondo y duplicar la credencial es duplicar dónde se olvida de actualizarla. Sin llave las URL quedan idénticas a las de antes (no un `?key=` colgando) y el mapa sigue pintando, con la marca.

  **El estilo es `light_all` y no se cambia a `voyager`**, aunque sea lo que CARTO recomienda en su aviso de la llave: `voyager` va a color y este visor está construido sobre el gris casi liso —es lo que deja leer el semáforo, y `MapaPeligros` afina el halo de los puntos a 0.5 px **solo** sobre este fondo por eso mismo—. Comprobado que `light_all` con llave responde 200 y sin marca: no hay ninguna razón para cambiar de estilo.

  `maxzoom` por fuente hace que MapLibre sobre-escale el último nivel disponible en vez de pedir teselas inexistentes. **OpenTopoMap es un servicio voluntario con política de uso restrictiva**: vale para el prototipo, pero en producción hay que sustituirlo por una fuente propia o con contrato. Los cuatro envían cabeceras CORS, así que la exportación PNG funciona con todos (comprobado); aun así el control captura `SecurityError` y avisa al usuario, porque las capas son administrables y el catálogo puede crecer.
- Al montar, `GET /api/mapas/capas/` → por cada capa: `addSource(slug, { type: "vector", url: "pmtiles://" + VITE_TILES_URL + "/" + slug + ".pmtiles" })` + layer con paint derivado de `estilo` (JSON del admin → reemplazo de capas sin tocar código, requisito TDR). Esto vale para las capas de contexto; la fuente `ccpp`, siempre presente, es aparte y de tipo `geojson` agrupado (ver arriba).
- `glyphs` apunta a los glifos auto-hospedados, no a `fonts.openmaptiles.org` (ver gotchas).
- `MapaPeligros.tsx` y `MapaControles.ts` se portan del prototipo. Controles ya implementados: buscador de lugar (en `frontend/` pasa a alimentarse del índice Meili `ccpp` en vez del padrón en memoria) + `flyTo`, medición de distancia/área, exportar PNG, selector de mapa base + conmutador de capas en un solo panel, leyenda semáforo, vista inicial y pantalla completa.
- Popups: `queryRenderedFeatures` con las props del feature; ficha completa desde `/api/ccpp/{codigo}/`. El desglose de peligros llega serializado (ver capa CCPP), así que el popup lo parsea.
- Colores nivel 1-4: tokens `level-1..4` de `tailwind.config.ts` del prototipo.

### Implementación de referencia (`prototype/src/components/MapaPeligros.tsx`)

**La migración ya está hecha en el prototipo**: `/peligros` corre sobre MapLibre + PMTiles y el visor Leaflet fue eliminado junto con sus dependencias (`leaflet`, `react-leaflet`, `html-to-image`). Para `frontend/` el trabajo es portar el componente cambiando el origen de datos (JSON estáticos → API + `/api/mapas/capas/`), no reescribirlo.

Lo que costó y conviene no volver a descubrir:

- **El mapa se crea con `preserveDrawingBuffer: true`.** Sin eso, `map.getCanvas().toDataURL()` devuelve un PNG en blanco. Además hay que forzar un `triggerRepaint()` y leer el canvas dentro de un `once("render")`.
- **Los controles se añaden antes de que el estilo cargue.** Cualquier `addSource`/`addLayer`/`setPaintProperty` en `IControl.onAdd` o en un efecto lanza *"Style is not done loading"*, así que todo cambio de estilo necesita un guard.
- **⚠ El guard `map.isStyleLoaded() ? fn() : map.once("load", fn)` está MAL** y estuvo escrito así en el prototipo. Cuando el efecto corre justo después de que React reaccionara al propio evento `load`, `isStyleLoaded()` todavía puede devolver `false` —hay cambios de estilo en vuelo— y entonces registra un `once("load")` sobre un mapa **que ya cargó**, que no se ejecuta jamás. El efecto se pierde en silencio: el síntoma fue un visor que arrancaba sin datos y sin colores, con cinco listeners colgados y cero errores en consola. `styledata` por sí solo tampoco basta, porque sus últimas emisiones llegan con el estilo aún sin asentar y después no vuelve a haber ninguna. El guard correcto reintenta en **`styledata` y `idle`**, y `idle` es el que cierra el hueco: se emite cuando no queda nada pendiente por cargar ni dibujar. Ambos se limpian solos con `map.remove()`.
  ```js
  function cuandoListo(map, fn) {
    if (map.isStyleLoaded()) { fn(); return; }
    const reintentar = () => {
      if (!map.isStyleLoaded()) return;
      map.off("styledata", reintentar); map.off("idle", reintentar); fn();
    };
    map.on("styledata", reintentar); map.on("idle", reintentar);
  }
  ```
- **`fonts.openmaptiles.org` ya no sirve glifos.** Devuelve una página HTML con **status 200** para cualquier fontstack, que MapLibre intenta parsear como protobuf: `Unimplemented type: 4`, repetido por tesela. No falla mientras el estilo no tenga ninguna capa `symbol`, así que la URL muerta puede llevar tiempo ahí sin que nadie lo note. Los glifos se **auto-hospedan** en `public/fonts/glyphs/{fontstack}/{range}.pbf`: los rótulos de los clusters solo usan dígitos y la abreviatura k/M, así que basta el rango `0-255` de Noto Sans Regular y Bold — 168 KB, sin dependencia de terceros.
- **`addProtocol("pmtiles", …)` se registra una vez por sesión**, no por instancia de mapa.
- **Filtrar no basta**: hay que mover la cámara (`fitBounds` sobre los puntos que quedan), o el usuario se queda mirando toda la región con casi todo oculto. Encuadrar sobre la fuente ya filtrada —en vez de sobre "los CCPP del distrito"— hace que funcione igual para provincia sola que para distrito.
- **Resolver un ubigeo por nombre de distrito es frágil.** `find(c => c.distrito === nombre)` sobre el padrón completo devuelve el primer homónimo de cualquier provincia. En Cusco hoy no hay colisiones, pero la suposición era implícita; hay que acotar también por provincia.
- Los enlaces dentro de un popup no pueden ser `<a href>` — recargarían la SPA. Se usa un `<button>` con un handler que llama a `navigate()` del router.
- El buscador de lugares necesita `stopPropagation` de `keydown` en su contenedor; si no, teclear dispara los atajos de teclado de MapLibre.
- **`circle-stroke-opacity` es independiente de `circle-opacity`** y vale 1 por defecto. Con el relleno atenuado y el anillo opaco, los 5,730 puntos sin clasificar se funden en una mancha blanca, muy visible sobre ortofoto. Hay que atenuar ambas con la misma expresión.
- Cada propiedad de pintado debe tener **un solo efecto que la escriba**. Al añadir el selector de base tuvimos dos efectos tocando `circle-opacity` con dependencias distintas, y el resultado dependía de cuál corriera último.

En el prototipo los `.pmtiles` **se versionan** (`prototype/public/tiles/`, ~6 MB): sin ellos el visor sale en blanco y no todo el mundo tiene Docker para regenerarlos. Es un artefacto derivado que hay que rehacer y commitear cuando cambie el Excel de peligros o una capa. En la plataforma real el problema desaparece: el worker regenera los tiles al final de cada `DatasetUpload`.
