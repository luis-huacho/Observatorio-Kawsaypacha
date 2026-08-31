# 02 — Contrato del API

DRF + django-filter + drf-spectacular (ADR-A2). Prefijo `/api/`. Todo el API público es **solo lectura**, devuelve únicamente contenido con `estado=publicado`, paginado (`page`/`page_size`, default 50, máx 200) salvo donde se indique. OpenAPI en `/api/schema/` + Swagger UI en `/api/docs/`.

Las formas de respuesta **espejan los tipos del prototipo** (`prototype/src/lib/types.ts` y los JSON de `prototype/public/data/`) para minimizar cambios en el frontend; se eliminan los flags `_mock`.

## Territorio y peligros

| Endpoint | Params | Notas |
|---|---|---|
| `GET /api/territorio/provincias/` | — | sin paginar (13) |
| `GET /api/territorio/distritos/` | `provincia=<ubigeo4>` | sin paginar (112) |
| `GET /api/ccpp/` | `provincia`, `distrito` (ubigeo6), `peligros` (slugs CSV), `niveles` (1-4 CSV), `buscar`, `clasificados`, `page` | Padrón con `nivel` anotado (máximo tras los filtros; `null` = sin dato). **`clasificados=1`** deja solo los que tienen clasificación: es lo que usa la tabla del visor, porque el padrón completo la convertiría en una lista de «sin dato» (5,730 de 8,968 en la región). Cada fila trae **`peligros`**: todos los del centro poblado que pasan los filtros, con `{slug, nombre, nivel}`, no solo el máximo. Ordena por nivel descendente, luego nombre y **`codigo`** — el nombre no es único (770 se repiten, «PUCARA» 21 veces) y sin ese desempate `LIMIT`/`OFFSET` repetía filas entre páginas y se saltaba otras |
| `GET /api/ccpp/{codigo}/` | — | ficha con clasificaciones anidadas |
| `GET /api/ccpp/export.xlsx` | mismos filtros que la lista | openpyxl, streaming. **Una fila por centro poblado**, la unidad de la tabla y del contador de la pantalla — no por clasificación. Lleva sus peligros en dos formas: una columna `Peligros` legible (`Sismo (4 · Muy alto); …`) y **una columna por peligro del catálogo** con su nivel, que es lo que permite filtrar y pivotar en Excel. Las columnas de peligro se generan desde `TipoPeligro`, así que un décimo peligro entra sin tocar código. Sin altitud ni coordenadas (ver 06), y sin población (ADR-A19) |
| `GET /api/ccpp/geojson/` | mismos filtros que la lista, **sin paginar** | Puntos del visor (ver 05 / ADR-A13). `FeatureCollection` de `Point`; ver el ejemplo y la nota de tamaño más abajo |
| `GET /api/peligros/tipos/` | — | catálogo (9) con orden, color e **`icono`** (nombre lucide en kebab-case). Es la fuente del selector y de los símbolos del visor: el frontend no conoce los peligros de antemano |
| `GET /api/peligros/resumen/` | `provincia`, `distrito`, `peligros`, `niveles` | agregados para cifras del home/visor. Devuelve **las dos unidades** (por CCPP y por clasificación) rotuladas; ver el ejemplo |
| `GET /api/peligros/frecuencia/` | `distrito`, `provincia`, `categoria` | Lista, sin paginar (90 de 112): una entrada por distrito **con datos de cualquiera de las dos tablas** |
| `GET /api/peligros/frecuencia/{ubigeo}/` | — | El panel de un distrito. **404** si no tiene fila (ver abajo) |
| `GET /api/peligros/frecuencia/export.xlsx` | ídem | Incluye los totales declarados marcados, o el Excel dejaría a Cusco en cero |
| `GET /api/peligros/frecuencia/provincia/<ubigeo4>/` | — | **Agregado provincial** (ADR-A18): lo que pinta el gráfico de /peligros. Nunca 404 si la provincia existe: sin registros devuelve ceros, que es un estado con forma. Ver el ejemplo |
| `GET /api/peligros/frecuencia/geojson/` | `provincia`, `distrito` | La capa del visor: un `Point` por distrito **con emergencias** (65 de 112). Los 25 que declaran cero (ADR-D1) quedan fuera — un ícono sobre ellos afirmaría lo que la fuente calla. El punto es el **centroide del distrito** (ADR-A20), con repliegue a la mediana de sus centros poblados en el único distrito cuyo centroide cae fuera de sí mismo |

> **Los filtros de exposición son listas, no valores sueltos (ADR-A17).** `peligros=sismo,heladas`
> y `niveles=1,4`, ambos CSV. Es una **selección**, no un umbral: `niveles=1,4` deja fuera los
> niveles 2 y 3, consulta que el antiguo `nivel_min` no podía expresar. Reglas del parser, que
> vive en un solo sitio (`apps/api/filters.py: parametros_exposicion`) porque lo comparten la
> lista, el geojson, el export, el resumen, la ayuda memoria y el visor headless:
>
> - Ausente, vacío, o con solo valores desconocidos → **no restringe nada**.
> - Se aceptan `peligro` (un slug o nombre) y `nivel_min` (umbral) como **compatibilidad**: hay
>   ayudas memoria compartidas con esas URL. `nivel_min=3` se traduce a `niveles=3,4`. Si vienen
>   las dos formas, gana la nueva.
> - **Tipo y nivel se aplican en una sola condición de join**, nunca en dos pasos. Con listas la
>   trampa es más fácil de pisar: un centro poblado con sismo en nivel 1 y heladas en nivel 4 no
>   cumple `peligros=sismo&niveles=4`, pero dos filtros separados encontrarían cada uno su fila.

> **Desviación deliberada respecto de la primera versión de este contrato.** El ejemplo original
> mostraba `?distrito=…` devolviendo **un objeto** y 404 para Acomayo, pero el mismo endpoint sin
> `distrito` tiene que devolver una lista (es lo que consume `FrecuenciaEmergencias.tsx`). Un
> endpoint que cambia de forma según los parámetros es peor que dos endpoints, así que la lista y
> el detalle se separan: `?distrito=080201` en la lista devuelve `[]`, y `/frecuencia/080201/` da
> 404. Los dos estados vacíos siguen siendo distinguibles, que es lo que el contrato exigía.

> **La lista mira las dos tablas.** Los distritos salen de `consultas.distritos_con_emergencias`,
> que une `FrecuenciaEmergencia` y `TotalDeclaradoEmergencias`. Consultar solo la primera —lo que
> hacía la implementación inicial— dejaba fuera a los **26 distritos que declaran subtotales sin
> desagregar** (ADR-D1), Cusco incluido: 64 entradas en vez de 90. El detalle sí los servía, así que
> la tabla y la ficha del mismo distrito se contradecían sin que ninguna consulta fallara. El export
> tiene que acotar los declarados **con los mismos filtros**, o un Excel de un distrito acaba
> trayendo los declarados de toda la región.

### `/api/ccpp/geojson/` — la fuente del visor

MapLibre solo agrupa fuentes `geojson` (ADR-A13), así que la capa de centros poblados no sale del tile vectorial. El endpoint devuelve **el padrón que pasa los filtros**, sin paginar, e incluye **también los no clasificados** — el visor los pinta en gris, y ese vacío de información es en sí mismo un dato.

```jsonc
// GET /api/ccpp/geojson/?provincia=0803&peligros=sismo,inundacion&niveles=3,4
{
  "type": "FeatureCollection",
  "features": [
    { "type": "Feature",
      "geometry": { "type": "Point", "coordinates": [-71.97675606, -13.51927548] },
      "properties": {
        "codigo": "0801010001", "nombre": "CUSCO", "categoria": "CIUDAD",
        "distrito": "CUSCO", "provincia": "CUSCO", "altitud": 3439,
        // Sin `poblacion` (ADR-A17). `peligro` = el que pinta el ícono: mayor nivel, y a
        // igualdad el primero del catálogo. `n<k>` y `p_<slug>` son el desglose que suma
        // `clusterProperties`, y **solo vienen las claves distintas de cero**.
        "peligro": "sismo", "n4": 1, "p_sismo": 1,
        // Ranuras de la corona: un peligro por ranura, en orden de nivel descendente. El
        // visor dibuja **un ícono por cada una**. El nivel va como `n_0` y no `n0` porque
        // `n1`…`n4` ya son el desglose que suman los grupos.
        "s0": "sismo", "n_0": 4, "s1": "heladas", "n_1": 3,
        // Máximo de los peligros que sobrevivieron a los filtros. 0 = sin dato.
        "nivel": 4,
        // Cuántas clasificaciones sobrevivieron a los filtros. 0 en los que no cumplen,
        // que siguen en la respuesta para pintarse en gris. Es lo que el visor suma para
        // rotular cada grupo (ADR-A16): la unidad de las 10,978, no la de las 3,238.
        "clasificaciones": 1,
        // Desglose para el popup, SERIALIZADO: las propiedades de un feature agrupado
        // tienen que ser escalares (ver 05).
        "peligros": "[{\"p\":\"Sismo\",\"n\":4}]"
      } }
  ]
}
```

Decisión de tamaño: se sirve el `FeatureCollection` completo en vez de agrupar en servidor. Region-wide son 8,968 features (~2 MB, ~400 KB con gzip, que es del orden de lo que el prototipo ya descarga y funciona), y al filtrar por provincia o distrito baja mucho. Agrupar en servidor obligaría a reimplementar supercluster en Python y a pedir datos en cada paneo del mapa; se deja como salida si el payload llegara a molestar. Se responde con `ETag` para que el navegador revalide en vez de re-descargar.

```jsonc
// GET /api/ccpp/0801010001/
{
  "codigo": "0801010001", "nombre": "CUSCO", "categoria": "CIUDAD",
  "departamento": "CUSCO", "provincia": "CUSCO", "distrito": "CUSCO",
  "ubigeo_distrito": "080101", "lat": -13.51927548, "lon": -71.97675606,
  "altitud": 3439,
  "clasificaciones": [
    { "peligro": "Sismo", "peligro_slug": "sismo", "categoria_geo": "Geodinamica interna",
      "nivel": 4, "fuente": "SIGRID_CENEPRED", "fuente_url": "https://n9.cl/lic6j" }
  ]
}
// `clasificaciones` viene vacío en 5,730 de los 8,968 CCPP: la mayoría no está clasificada.
// El frontend debe distinguir "sin dato" de "nivel bajo", no colapsarlos.

// GET /api/peligros/resumen/?distrito=080101
// El payload declara la unidad de cada bloque en un campo `unidades`: las dos lecturas
// difieren en 3.4× y cualquier cliente que dibuje una de las dos tiene que poder rotularla.
{
  "total_ccpp": 123,
  // [+] Distribución por nivel MÁXIMO de cada centro poblado: es lo que debe cuadrar con el
  // conteo de la tabla de /peligros.
  // NO se puede derivar de `por_peligro` — sumar por peligro cuenta cada CCPP tantas veces
  // como peligros tenga evaluados (ACOMAYO: 75 CCPP → 225 clasificaciones). Tiene que venir
  // agregado del servidor, y debe respetar los mismos filtros de peligro y nivel.
  "por_ccpp": { "niveles": { "1": 0, "2": 0, "3": 26, "4": 49 }, "sin_clasificar": 0 },
  "por_peligro": [
    // `centros_poblados` coincide siempre con la suma de `niveles`, y no por casualidad: la
    // constraint `unica_clasificacion_ccpp_peligro` impide dos filas del mismo peligro en un
    // mismo centro poblado. Por eso la grilla de resultados puede rotular cada FILA como
    // centros poblados sin ambigüedad; la de 3.4× solo aparece al sumar la COLUMNA.
    { "peligro": "Sismo", "slug": "sismo",
      "niveles": { "1": 0, "2": 3, "3": 40, "4": 80 },
      "centros_poblados": 123, "sin_dato": 0 }
  ]
}

// GET /api/peligros/frecuencia/?distrito=081306   (Ollantaytambo: caso normal)
{
  "distrito": "OLLANTAYTAMBO", "ubigeo": "081306",
  "rango_fecha": "2003-2019", "fuente": "SIGRID_CENEPRED", "fuente_url": "https://n9.cl/ulacc",
  "desglose_disponible": true,
  "categorias": [
    { "categoria": "Meteorológicos / oceanográficos", "slug": "meteorologico", "total": 22,
      "solo_total": false,
      "eventos": [ { "evento": "Helada", "slug": "helada", "conteo": 13 },
                   { "evento": "Inundación", "slug": "inundacion", "conteo": 4 } ] }
  ],
  "total": 36
}

// GET /api/peligros/frecuencia/provincia/0801/   (ADR-A18)
// **Las dos agrupaciones no suman lo mismo, y es correcto.** `familias` incluye los subtotales
// que la fuente declara sin desagregar (ADR-D1) y `eventos` no puede incluirlos, así que en
// Cusco `familias` suma 608 y `eventos` 474. `total_sin_desglose` existe para que la pantalla
// lo explique en vez de dejar que el total cambie al pulsar una casilla.
//
// Ojo al vocabulario: la UI llama «evento» a `eventos` (Huayco, Deslizamiento…) y «tipo de
// evento» a `familias` (Geodinámica externa…), al revés que los modelos.
{
  "provincia": "CUSCO", "ubigeo": "0801", "total": 608,
  // Sin esto la cifra engaña: Espinar declara 77 con 1 de sus 8 distritos registrados y parece
  // más tranquila que Cusco, cuando lo que le faltan son los datos.
  "distritos_con_registro": 8, "distritos_en_provincia": 8,
  // Rango que ABARCA el conjunto, nunca «el periodo»: cada distrito trae el suyo.
  "periodo": "2003-2025", "periodos_distintos": 6,
  "eventos": [ { "evento": "Lluvias intensas", "slug": "lluvias_intensas_evento",
                 "categoria": "Meteorológicos / oceanográficos",
                 "categoria_slug": "meteorologico", "conteo": 87 } ],
  "familias": [ { "categoria": "Meteorológicos / oceanográficos",
                  "slug": "meteorologico", "conteo": 335 } ],
  "sin_desglose": [ { "distrito": "CUSCO", "total": 134 } ], "total_sin_desglose": 134,
  "fuente": "SIGRID_CENEPRED", "fuente_url": "https://n9.cl/e9qwr"
}

// GET /api/peligros/frecuencia/?distrito=080101   (Cusco: la fuente no desagrega — ADR-D1)
{
  "distrito": "CUSCO", "ubigeo": "080101",
  "rango_fecha": "2003-2022", "fuente": "SIGRID_CENEPRED", "fuente_url": "https://n9.cl/e9qwr",
  "desglose_disponible": false,
  "categorias": [
    { "categoria": "Geodinámica externa", "slug": "geodinamica_externa", "total": 43,
      "solo_total": true, "eventos": [] }
  ],
  "total": 134
}
```

Notas del contrato:

- `desglose_disponible: false` significa que los totales salen de `TotalDeclaradoEmergencias`, no de la suma por evento. El frontend debe decirlo explícitamente en vez de dibujar un gráfico vacío o un cero.
- **`rango_fecha` es por distrito** (23 variantes distintas, rango global 2000–2025). No existe un periodo regional, así que ningún agregado provincial o regional puede anunciar uno: los totales entre distritos no son directamente comparables.
- Los distritos sin fila en el Excel (hoy solo **ACOMAYO, 080201**) responden **404** en el detalle; los que tienen fila pero sin emergencias devuelven `total: 0`. Son dos estados vacíos distintos y la UI los distingue: el primero es un vacío de la fuente que hay que pedirle al cliente, el segundo es un dato real.

## Contenido editorial

| Endpoint | Params | Notas |
|---|---|---|
| `GET /api/medidas/` | `peligro`, `ambito`, `resultado`, `distrito`, `tema`, `page` | facetado fino vía Meilisearch (04); este endpoint es la fuente canónica |
| `GET /api/medidas/{slug}/` | — | incluye `contenido` HTML saneado, `galeria` anidada y `enlaces` |
| `GET /api/normativa/` | `tipo`, `ambito`, `entidad`, `anio`, `tema`, `page` | `entidad` es el **slug** de la entidad emisora |
| `GET /api/normativa/entidades/` | — | catálogo para el desplegable: solo las entidades **con alguna norma publicada**, sin paginar. Ofrecer el catálogo entero sería ofrecer filtros que devuelven cero resultados |
| `GET /api/normativa/{slug}/` | — | ficha con `contenido` desarrollado |
| `GET /api/normativa/export.xlsx` | ídem que el listado | |
| `GET /api/noticias/` | `tipo`, `destacada`, `tema`, `page` | orden `-destacada, -fecha, -id`: las destacadas encabezan y dentro de cada grupo manda la fecha. El remate por `id` no es cosmético — `fecha` es un `DateField` y el listado se pagina |
| `GET /api/noticias/{slug}/` | — | |

`tema` filtra por coincidencia exacta en `palabras_clave`; es lo que alimenta los chips navegables de las fichas (`?tema=…` en el frontend).

**`entidad_emisora` viaja como objeto anidado** (`{slug, nombre, sigla}`) o `null`, que es un estado real y frecuente: no toda norma tiene entidad, y la ficha repliega entonces al nivel de gobierno que se deduce de `ambito`. Objeto y no cadena porque los tres consumidores piden cosas distintas —el listado pinta la sigla, la ficha el nombre completo, el filtro viaja por slug— y salen del mismo sitio.

**`url_oficial` va en el listado y en el detalle**, no solo en el detalle: el acceso a la publicación oficial se ofrece en los dos sitios (ver 01). Si la norma tiene `documento` adjunto, el serializer devuelve la URL del PDF alojado y no la externa — el portal del organismo puede haber movido la suya.

**`imagen_portada` se devuelve resuelta.** Si la pieza no tiene imagen propia, el serializer entrega la URL de la ilustración institucional de su tipo (ver el bloque de imagen por defecto en 01). Así ningún cliente —web, PDF o futura app— reimplementa la regla, y cambiarla es tocar un solo sitio.
| `GET /api/videos/` | `tema`, `page` | |
| `GET /api/eventos/` | `desde`, `hasta` (ISO date; default mes visible) | sin paginar |
| `GET /api/biblioteca/` | `categoria`, `buscar`, `page` | |
| `GET /api/biblioteca/{id}/` | — | incrementa contador de descarga vía métricas cuando el front lo reporta |

```jsonc
// GET /api/medidas/qochas-pampallacta/   (forma = medidas.mock.json sin _mock)
{
  "slug": "qochas-pampallacta", "titulo": "Qochas comunales en Pampallacta",
  "peligro": "Sequía", "ambito": "comunal", "resultado": "exito",
  "distrito": { "ubigeo": "080302", "nombre": "Pisac", "provincia": "Calca" },
  "comunidad": "Pampallacta",
  "resumen_corto": "Construcción de 12 qochas…",
  // HTML de CKEditor 5 YA SANEADO en servidor (ADR-D2). El cliente lo inyecta tal cual.
  "contenido": "<p>La comunidad de Pampallacta…</p><h2>Cómo se hizo</h2><ul><li>…</li></ul>",
  "video_url": null,
  "imagen_portada": "/media/medidas/qochas.jpg",   // resuelta: propia o ilustración por peligro
  "imagen_titulo": "Qochas construidas por la comunidad de Pampallacta.",
  "galeria": [
    { "imagen": "/media/medidas/qochas-1.jpg", "pie": "Faena comunal de excavación.", "orden": 1 }
  ],
  "enlaces": [ { "titulo": "INAIGEM — siembra y cosecha de agua", "url": "https://www.gob.pe/inaigem" } ],
  "palabras_clave": ["Siembra de agua", "Qochas", "Pisac", "Gestión comunal"],
  "publicado_en": "2026-07-30T10:00:00-05:00"
}

// GET /api/normativa/?tipo=Ley   (forma = normativa.mock.json)
{ "count": 1, "results": [ {
  "id": 1, "titulo": "Ley N° 29664 — SINAGERD", "tipo": "Ley", "ambito": "nacional",
  "entidad_emisora": {"slug": "congreso", "nombre": "Congreso de la República",
                      "sigla": "Congreso"},
  "fecha": "2011-02-19", "resumen": "Crea el SINAGERD…",
  "url_oficial": "https://…", "analisis_predes": null
} ] }
```

## Inversión (PP 0068)

| Endpoint | Params |
|---|---|
| `GET /api/inversion/` | `anio` (default: el más reciente visible), `ambito` (`municipal` por defecto \| distrital \| provincial \| regional \| todos), `provincia` (ubigeo o nombre), `comparar_con` |
| `GET /api/inversion/entidades/` | los mismos + `buscar`, `ordenar`, `page`, `page_size`. **Paginado** |
| `GET /api/inversion/entidades/{codigo}/` | `anio`. `codigo` = código MEF de la entidad ejecutora |
| `GET /api/inversion/mapa/` | `anio`, `ambito`, `provincia` + `nivel` (`distrital` por defecto \| `provincial`) |
| `GET /api/inversion/reporte.pdf` | los del mapa + `ordenar` y `sin_mapa` |
| `GET /api/inversion/export.xlsx` | los mismos que el listado, sin paginar |

**El tablero y la tabla van en endpoints distintos, a propósito.** `/api/inversion/` sirve las piezas que se dibujan juntas y hablan del mismo ejercicio (agregados, procesos, tendencia, ejercicios); la tabla se pagina y su orden se resuelve en el servidor, porque ordenar en el cliente ordenaría solo lo ya cargado. Ojo al probarlo: `/api/inversion/entidades/` **contiene** la cadena `/api/inversion/`, y un matcher por subcadena atrapa la respuesta equivocada.

`ordenar` acepta `pim` (por defecto), `ejecucion`, `saldo`, `institucional` y `variacion` (este último solo con `comparar_con`). Todos ordenan **con desempate por código de entidad**: sin un orden total, la paginación repite unas filas y se salta otras sin que nada falle a la vista.

Sin ningún ejercicio `visible`:
```json
{ "disponible": false, "motivo": "PREDES está consolidando los datos de inversión del PP 0068." }
```

Es el **mismo contrato** que servía la ventana cuando estaba diferida, y se conserva a propósito: el cliente no necesita un caso especial para «hay datos pero todavía sin publicar», que es el estado normal entre una importación y la revisión de PREDES.

Un `anio` que no existe o que no está visible **no cae al último**: devuelve `disponible: false`. Servir otro ejercicio se vería perfecto y todas las cifras serían del año equivocado.

Con datos:
```jsonc
{
  "disponible": true, "anio": 2026, "corte": "2026-06", "corte_legible": "junio de 2026",
  "es_parcial": true, "en_curso": true,
  "fuente": "Base PP 0068 desarrollada por PREDES",
  "ambito": "municipal", "unidad": "municipalidad (entidad ejecutora), no distrito",
  "agregados": { "pia": 16754644, "pim": 54591255, "devengado": 26064745,
                 "pct_ejecucion": 0.4775, "saldo": 28526510, "variacion_pia_pim": 37836611,
                 "entidades_con_presupuesto": 115, "entidades_en_ambito": 116,
                 "pia_institucional": null, "pim_institucional": 4305815597,
                 "devengado_institucional": null,
                 "pct_0068_institucional": 0.0127, "entidades_con_institucional": 114,
                 "pim_proyectos": 22217511, "pim_actividades": 32373744, "pct_proyectos": 0.407 },
  "procesos": [ { "slug": "prevencion_reduccion", "nombre": "Prevención y reducción",
                  "color": "#009257", "pim": 28909461, "devengado": 0, "pct": 0.53 } ],
  "sin_clasificar": { "pim": 0, "devengado": 0, "pct": 0 },
  "proyectos": { "pim": 22217511, "con_proyectos": 24, "de": 116,
                 "entidades": [ { "codigo": "301027", "entidad": "MUNICIPALIDAD DISTRITAL DE PICHARI",
                                  "ambito": "distrital", "provincia": "LA CONVENCION",
                                  "pim": 9327510, "pim_proyectos": 6455719,
                                  "pct_proyectos": 0.692 } ] },
  "tendencia": [ { "anio": 2022, "corte": "anual", "corte_legible": "", "es_parcial": false,
                   "en_curso": false, "fuente": "…",
                   "pia": 18060834, "pim": 48813109, "devengado": 37260987 } ],
  "declaraciones": { "ejecucion": "El presupuesto creció S/ 37,836,611 (225.8%) entre lo aprobado…",
                     "procesos": "Prevención y reducción concentra el 53%…",
                     "tendencia": "Entre 2024 y 2025, los dos últimos ejercicios completos…",
                     "proyectos": "24 de las 116 municipalidades del ámbito tienen presupuesto…" },
  "ejercicios": [ { "anio": 2026, "corte": "2026-06", "corte_legible": "junio de 2026",
                    "es_parcial": true, "en_curso": true } ]
}

// GET /api/inversion/entidades/?anio=2026&ordenar=saldo  → sobre estándar de DRF
{ "count": 116, "next": "…?page=2", "previous": null,
  "results": [ { "codigo": "300684", "entidad": "MUNICIPALIDAD PROVINCIAL DEL CUZCO",
                 "ambito": "provincial", "ubigeo_distrito": "080101",
                 "distrito": "CUSCO", "provincia": "CUSCO",
                 "pia": 54508, "pim": 1278015, "devengado": 371786, "pct_ejecucion": 0.291,
                 "saldo": 906229, "variacion_pia_pim": 1223507, "pct_variacion_pia_pim": 22.4,
                 "pia_institucional": 176788063, "pim_institucional": 270220526,
                 "devengado_institucional": 128401242, "pct_0068_institucional": 0.0047,
                 "pim_proyectos": 0, "pim_actividades": 1278015, "pct_proyectos": 0.0 } ] }

// Con `comparar_con=2025`, cada fila añade:
"comparacion": { "anio": 2025, "corte": "anual", "corte_legible": "", "es_parcial": false,
                 "en_curso": false, "comparable": false, "sin_presupuesto": false,
                 "pia": 40000, "pim": 585804, "devengado": 500000, "pct_ejecucion": 0.85,
                 "delta_pim": 692211, "pct_delta_pim": 1.18,
                 "delta_devengado": -128214, "delta_pct_ejecucion": -0.56 }

// GET /api/inversion/entidades/300757/  → la ficha de una municipalidad
{ "disponible": true,
  "entidad": { "codigo": "300757", "nombre": "…", "ambito": "distrital",
               "ambito_nombre": "Municipalidad distrital", "ubigeo_distrito": "080910",
               "distrito": "PICHARI", "provincia": "LA CONVENCION", "sin_territorio": false },
  "anio": 2026, "corte": "2026-06", "corte_legible": "junio de 2026",
  "es_parcial": true, "en_curso": true, "fuente": "…",
  "serie": [ { "anio": 2022, "corte": "anual", "corte_legible": "", "es_parcial": false,
               "en_curso": false, "…": "los mismos derivados" } ],
  "procesos": [ … ], "sin_clasificar": { … },
  "actividades": [ { "codigo": "2534780", "nombre": "CREACION DEL SERVICIO…",
                     "origen": "proyecto", "proceso": "Prevención y reducción",
                     "proceso_slug": "prevencion_reduccion",
                     "pia": 0, "pim": 6150969, "devengado": 6150968, "pct_ejecucion": 1.0 } ],
  "ejercicios": [ … ] }
```

> **`declaraciones` es lo que cada gráfico DICE, ya redactado.** Un gráfico se deja leer pero no
> concluye, y la ventana la usan autoridades, periodistas y universidades. Las cuatro frases se
> escriben en **`apps/inversion/declaraciones.py`, un solo sitio**, y las imprimen la SPA —que
> las recibe aquí— y el PDF, que llama a las mismas funciones con sus propios filtros. Es la
> misma decisión de ADR-D6 (`no_ubicado` viaja con «su motivo ya redactado») y el argumento del
> encabezado de `consultas.py`: dos redacciones de la misma frase acaban no diciendo lo mismo.
> Lo único que no comparten es la tipografía —`53%` en el navegador, `53.0 %` en el reporte—,
> y por eso los formateadores entran por parámetro. Una clave puede ser `null`: sin datos que
> declarar no se pinta un filete con una frase vacía debajo del gráfico.
>
> Tres cosas que la redacción codifica y un refactor puede deshacer sin que nada falle a la
> vista: **la de la tendencia compara los dos últimos ejercicios COMPLETOS** —contra el corte
> parcial daría una caída del devengado que solo mide medio año contra doce meses—; **no dice
> «cerrado»**, que es jerga contable con una prueba e2e que lo fija; y **la concentración solo
> se declara si las que se llevan el 80 % son minoría**, porque con un reparto plano cuatro de
> cinco suman el 80 % por aritmética y decirlo haría sonar concentrado lo que está repartido.
>
> **`proyectos` desglosa lo que `agregados.pim_proyectos` solo cuenta.** Un «40 % en proyectos
> de inversión» se lee como si las municipalidades estuvieran haciendo obra por toda la región,
> y no es eso: en 2026 **24 de las 116** tienen presupuesto en obra y cinco concentran el 81 %.
> `de` es el total de entidades del ámbito —sin él, «24» no dice nada—, y solo entran las que
> tienen PIM de proyectos **> 0**: una fila en cero las haría contar como si tuvieran obra. La
> lista **va entera y no recortada a un top N**, porque son 24 en la región y 9 en la provincia
> más cargada, y un «y otras N» no lo podría comprobar nadie. El orden es total (importe
> descendente, código de desempate) para que no baile entre peticiones. Hay una prueba que fija
> que la suma del desglose es exactamente `agregados.pim_proyectos`: un desglose al que le falta
> dinero se ve idéntico a uno correcto.
>
> **No está en `ORDENES` de la tabla paginada, y es a propósito.** `pim_proyectos` se calcula en
> Python después de paginar; ordenar por él exigiría anotarlo en SQL con una subconsulta sobre
> `PresupuestoActividad`. Con 24 filas como mucho, el desglose viaja completo en el tablero.


La `serie` **omite los ejercicios sin presupuesto** en vez de rellenarlos con ceros: no participar del programa un año no es participar con cero soles. Las `actividades` no se paginan —3 de media por entidad y ejercicio, 50 en el máximo real—, con el mismo criterio por el que no se paginan los 112 distritos.

Cinco reglas del payload que la interfaz no puede reinventar:

- **Los cinco campos que identifican el ejercicio viajan con el dato**, en la raíz y en cada punto de `tendencia`, `ejercicios`, `comparacion` y `serie`. Salen todos de `consultas.datos_ejercicio()`, que es lo que impide que un payload se quede sin uno. `es_parcial` y `corte` dicen qué **no** es el dato —un % de ejecución de medio año se calcula contra un PIM anual, y cualquier cliente que lo dibuje tiene que poder advertirlo—; **`en_curso` y `corte_legible` dicen qué es**, que es lo que la pantalla no podía decir sin deducirlo por descarte. **`en_curso` no es un alias de `es_parcial`**: un corte a junio de un año ya pasado es parcial sin estar en curso, y llamarlo «en curso» sería afirmar algo falso.
- **Un porcentaje que no se puede calcular es `null`, no `0`.** Una municipalidad sin total institucional no tiene un 0 % de su presupuesto en el 0068.
- **Los importes institucionales de `agregados` y su porcentaje salen del mismo universo**: solo las entidades que tienen ese dato. Con el numerador de las 116 y el denominador de las 114 que tienen total, el porcentaje saldría inflado sin que nada lo dijera, y publicar un total institucional que no cuadre con el porcentaje de al lado es el mismo problema por otra vía. Por eso `entidades_con_institucional` viaja junto a las tres cifras: es su rótulo. Sin ninguna entidad con dato, los tres son `null` y no cero.
- **`comparacion.comparable`** es `false` cuando los dos ejercicios tienen cortes distintos. El Δ de % de ejecución se sirve igual —así se decidió (ADR-D5)— pero nadie debe pintarlo sin la marca: un 47.7 % de medio año contra un 86.4 % de un año completo no es una caída. Las variaciones de PIA, PIM y devengado sí son comparables.
- **`comparacion.sin_presupuesto`** distingue «no participó del programa ese año» de «participó con cero». En ese caso los deltas son `null`: aparecer de la nada no es no haber cambiado.

### El mapa — `GET /api/inversion/mapa/`

Alimenta el coroplético de `/inversion`, y su contrato **es ADR-D6**: se pinta lo que se puede atribuir al polígono sin inventarlo, y lo que no se puede ubicar se declara.

```jsonc
// GET /api/inversion/mapa/?anio=2026&nivel=distrital
{ "disponible": true, "anio": 2026, "corte": "2026-06", "corte_legible": "junio de 2026",
  "es_parcial": true, "en_curso": true,
  "nivel": "distrital", "ambito": "municipal",
  "filas": [ { "ubigeo": "080910", "nombre": "PICHARI", "provincia": "LA CONVENCION",
               "codigo_entidad": "300757", "entidad": "MUNICIPALIDAD DISTRITAL DE PICHARI",
               "entidades": 1, "pia": 123997, "pim": 9331232, "devengado": 7178924,
               "saldo": 2152308, "pct_ejecucion": 0.769 } ],
  "cortes": { "pia": [...4], "pim": [28750, 55000, 94740, 216445], "devengado": [...4] },
  "distribucion": { "pim": { "n": 99, "ceros": 1,
                             "q1": 38000, "mediana": 73510, "q3": 179422,
                             "bigote_min": 0, "bigote_max": 370009,
                             "atipicos": [ { "nombre": "PICHARI", "valor": 9331232 }, … ],
                             "frase": "La mitad de los 99 distritos está entre…" },
                    "pia": {…}, "devengado": {…}, "pct_ejecucion": {…} },
  "no_ubicado": { "pia": …, "pim": 10350637, "devengado": …, "entidades": 17,
                  "pct": { "pia": 0.107, "pim": 0.190, "devengado": 0.172 },
                  "motivo": "Es de 13 municipalidades provinciales y 4 entidades sin distrito.
                             Sí cuenta en el total del ámbito y en la tabla." },
  "poligonos": { "pintados": 99, "sin_dato": 13,
                 "motivo": "Sin municipalidad distrital con presupuesto este año…" } }
```

Cinco cosas que no son detalles de implementación:

- **`ubigeo` casa directamente con el tile**: seis dígitos = `UBIGEO` de `limites-distritales`, cuatro = `IDPROV` de `limites-provinciales`. No hay traducción intermedia.
- **Las cuatro métricas viajan en cada fila.** Conmutar entre PIA, PIM, devengado y % de ejecución no dispara otra petición, así que dos métricas del mismo mapa no pueden acabar viniendo de ejercicios distintos si alguien cambia la visibilidad entre medias.
- **`suma(filas) + no_ubicado == el total del ámbito`, siempre.** Es la contabilidad completa del mapa, y hay dos pruebas que la fijan: un mapa al que le falta dinero se ve exactamente igual que uno correcto.
- **`poligonos.sin_dato`** cuenta los polígonos sin municipalidad —a nivel distrital son las 13 capitales de provincia— y es distinto de una municipalidad con PIM cero, que **sí** aparece en `filas` con sus ceros y su `pct_ejecucion: null`. Su `motivo` **ya no lo pinta nadie**: tanto la pantalla como el PDF traen en la leyenda un cuadro blanco rotulado «sin municipalidad (N)», y la frase solo repetía el porqué. Sigue en el payload para un cliente que dibuje este mapa sin esa leyenda.
- **`no_ubicado.pct` dice qué PARTE del ámbito se queda fuera**, una por métrica de dinero (19 % del PIM en 2026, 10,7 % del PIA, 17,2 % del devengado). Un importe suelto obliga a ir a buscar el total para saber si es mucho o poco; es la contabilidad de ADR-D6 —pintado + declarado == total— dicha en la unidad en la que se lee. Con un ámbito sin nada que declarar vale **0, no una división por cero**. Y el `motivo` termina diciendo **dónde sí está contado** ese dinero, en vez de justificar la decisión de no repartirlo: era lo que el lector se preguntaba y lo que hacía inútil el pie.
- **`distribucion` es lo que el coroplético no puede enseñar.** Los quintiles son la escala correcta para un mapa, pero su último tramo se traga toda la cola: con el PIM distrital de 2026 arranca en S/ 216.445, así que un distrito de 220 mil y otro de 9,3 millones **se pintan del mismo color**. La mediana es S/ 73.510 y el máximo, 127 veces más. Los cinco números salen del servidor por lo mismo que `cortes` y los dos `motivo` (ADR-D6): dos cálculos de la misma mediana acaban discrepando. Tres reglas: los **cuartiles van por índice, sin interpolar**, igual que `cortes` —son estadísticos distintos y no pueden coincidir, pero con métodos distintos nadie sabría si la diferencia es del dato o del método—; los **ceros cuentan para el cuartil y se cuentan aparte**, porque no caben en el eje logarítmico que el cliente dibuja y hay que poder declararlos; y **`pct_ejecucion` descarta los nulos**, que no son un 0 %. Las cuatro métricas viajan juntas por el mismo motivo que las de `filas`.

### El reporte — `GET /api/inversion/reporte.pdf`

El equivalente de la ayuda memoria de `/peligros` para esta ventana: el tablero completo en un
documento, con sus gráficas, su mapa y la tabla de las 116 municipalidades. Alcance **regional
con los filtros puestos**, no una ficha por municipalidad.

Cuatro decisiones del contrato:

- **Sin ejercicio visible responde 200 con un PDF de una página** que explica el vacío, no un 404.
  Un documento en blanco se leería como «no hay inversión pública en gestión del riesgo», que es
  falso; es el mismo criterio de la hoja «Sin datos» del Excel.
- **Las gráficas son SVG generado en servidor** (`apps/informes/graficos.py`). WeasyPrint no
  ejecuta JavaScript, así que los de Recharts no se pueden reutilizar; el SVG además es vectorial
  y determinista, y deja el PDF sin imágenes rasterizadas salvo el mapa —que es como las pruebas
  detectan si el mapa llegó—.
- **El único que necesita navegador es el mapa**, con la misma degradación de siempre: si la
  captura falla, el documento sale sin él y con el resto intacto.
- **El documento declara el importe que su mapa no pinta** (ADR-D6). En pantalla el pie está
  debajo del mapa; en un PDF que circula por correo, si la declaración no viaja dentro no viaja.

`sin_mapa=1` omite la captura: es lo que usan las pruebas para tener una salida determinista y
rápida.

Los `cortes` son los cuatro quintiles de lo pintado, así que el color es relativo a la vista: al acotar por provincia, un mismo distrito puede cambiar de tono. Se sirve así a propósito —una rampa lineal sobre una distribución tan sesgada deja un polígono oscuro y todos los demás pálidos— y el precio se paga imprimiendo los rangos en soles en la leyenda. Pueden salir repetidos (con muchos ceros, los tres primeros valen 0): el cliente clasifica recorriendo la lista, así que un tramo vacío se dibuja vacío. Lo que **no** se puede hacer con ellos es un `step` de MapLibre, que exige cortes estrictamente crecientes. El **% de ejecución no tiene cortes en el payload**: son fijos (25/50/75/90) porque es un porcentaje, y con una escala relativa el mismo 90 % se pintaría de verde o de rojo según con quién compartiera pantalla.

## Productos de incidencia

| Endpoint | Params | Notas |
|---|---|---|
| `GET /api/comparador/distritos/` | `ubigeos=080101,080301` (2–4), `anio` | por distrito: población, conteo CCPP por peligro×nivel, frecuencia de emergencias, inversión (si `disponible`), nº medidas publicadas |
| `GET /api/distritos/{ubigeo}/ayuda-memoria.pdf` | `anio`, `peligros` (CSV), `niveles` (CSV) | WeasyPrint; cache en `media/informes/` 24 h, invalidado por imports |

**La maqueta de la ayuda memoria ya existe**: `prototype/src/components/ReporteImpresion.tsx`, validada en pantalla y en vista previa de impresión. Es HTML+CSS estándar, que es justo lo que consume WeasyPrint, así que la plantilla del backend parte de ahí en vez de diseñarse de cero. Estructura del documento: membrete PREDES · ámbito y filtros aplicados · fecha de generación · párrafo de presentación redactado con las cifras del propio filtro · mapa · distribución por nivel · emergencias del distrito · tabla de centros poblados clasificados · fuentes y firma institucional.

Notas de contrato heredadas de la maqueta:

- **El alcance es un distrito**, con `peligros` y `niveles` como refinamientos opcionales. Un reporte regional o provincial produce decenas de páginas y deja de servir para una mesa técnica.
- La tabla lista **solo los centros poblados clasificados**; los "sin dato" se cuentan en el texto como vacío de información, que es en sí mismo un argumento de incidencia.
- **El mapa se renderiza en el servidor** (decisión del dueño del proyecto). El worker abre una página headless (Playwright + Chromium) con un visor mínimo que consume `/api/ccpp/geojson/` y las capas de contexto, encuadra el distrito y captura el PNG, que WeasyPrint incrusta. Se prefiere esto a que el cliente envíe el canvas de su vista: así el PDF se puede generar **desde el admin y por lotes**, sin depender de que alguien tenga el visor abierto, y el documento es reproducible a partir de sus parámetros. Coste asumido: Chromium en la imagen del backend (~400 MB) y un punto más de fallo — si la captura falla, el PDF sale **sin mapa** y con el resto del contenido intacto, nunca con un hueco roto.
- Los textos de firma salen de `ConfiguracionSitio` y `BloqueTexto`, no cableados como en el prototipo.

Y tres reglas de la captura, las tres pagadas con un PDF que salió sin mapa en producción local:

- **Todo lo que pide esa página va por su propio origen.** El navegador headless corre dentro del contenedor y abre el visor por la URL interna (`RENDER_MAPA_BASE_URL`), así que sus `fetch` son **relativos** y las URL de los PMTiles que devuelve `/api/mapas/capas/` se reescriben contra `location.origin`. `BACKEND_URL` es la URL con la que **el visitante** alcanza el backend y no sirve aquí: en producción local es `http://localhost`, el puerto 80 del propio contenedor, donde no escucha nadie. Con eso el documento salía sin mapa, y en desarrollo funcionaba por casualidad porque allí `BACKEND_URL` sí es el puerto de ese contenedor.
- **Qué es fatal y qué no.** No poder cargar los datos (`/ccpp/geojson/`, `/mapas/capas/`) sí lo es: un mapa sin puntos incrustado como si fuera el mapa engaña. Un error de MapLibre —una tesela del mapa base, una capa que no responde— **no** aborta: se recoge como aviso, va al log del servidor y se captura lo que haya. El mapa base son teselas de openstreetmap.org, y con la regla anterior una sola tesela costaba el mapa entero.
- **Hay un plazo, además del timeout.** Si algo externo se atasca, `idle` puede no llegar nunca; pasado `ESPERA_PINTADO_MS` (8 s) se captura igual. Comprobado apuntando el mapa base a un host inexistente: el PNG sale con los centros poblados y las capas propias sobre fondo plano.

## Sitio, mapas y métricas

| Endpoint | Params | Notas |
|---|---|---|
| `GET /api/sitio/` | — | payload único cacheable (`Cache-Control: max-age=300`): ConfiguracionSitio + BloqueTexto + EnlaceMenu visibles + HeroSlides publicados. El frontend lo pide una vez al montar `Layout` |
| `GET /api/salud/` | — | Prueba de vida. **Siempre 200 si el proceso atiende**, incluso con la base o el buscador caídos; ver abajo |

### `/api/salud/` — liveness, no dependencias

No lo consume el frontend: lo consumen el `healthcheck` de `backend` en `compose.yaml` y
`deploy/comprobar-sitio.sh` desde otra máquina (spec 07).

```json
{"servicio": "ok", "base": "sin respuesta", "buscador": "ok"}
```

**Devuelve 200 aunque falten sus dependencias, y lo declara en el cuerpo.** Es la decisión que
define el endpoint: si respondiera 5xx cuando PostgreSQL no contesta, el healthcheck marcaría el
contenedor «unhealthy», el vigilante lo reiniciaría en bucle, y ni arreglaría nada —reiniciar el
backend no levanta la base— ni dejaría rastro que mirar.

Va **exenta de throttling** por la misma razón: con `interval: 10s` son 360 peticiones/hora contra
el techo anónimo de 1000/hora, y un 429 provocaría reinicios sin que pasara nada en el sitio. Es
también el motivo de no reutilizar `/api/docs/` ni `/api/schema/`, que sí están sujetas.

### Las tasas se configuran por entorno

`THROTTLE_PRODUCCION` en `settings.py` es la fuente de verdad de los valores del servicio —1000/hora
anónimas, 30/hora de descargas, 600/min de beacon— y hay una prueba que los fija. Cada uno se puede
sustituir por su variable (`API_THROTTLE_ANON`, `API_THROTTLE_DESCARGA`, `API_THROTTLE_BEACON`), y
**vaciarla desactiva ese límite**; `compose.dev.yml` las vacía las tres.

Hizo falta porque **el throttling se aplicaba igual en desarrollo que en producción**, y la suite
E2E no cabe en la cuota: 56 casos × 2 proyectos = 112 corridas, cada una con caché de navegador
fría —Playwright abre un contexto nuevo por prueba— y la portada sola pide 8 veces. Son ~1.100
peticiones contra 1.000, así que a media suite el API empezaba a responder 429 y **fallaba en bloque
lo que no tenía nada roto**: `peligros`, `inversion`, `medidas` y `buscar`. Lo caro de depurar es que
**un 429 no se parece a un límite sino a un sitio caído**: la prueba solo ve que los datos no llegan
y agota su espera igual que si el backend estuviera muerto.

La caché no era la salida, y conviene dejarlo escrito para no volver a proponerla: cada prueba parte
de un contexto de navegador nuevo, así que no hay nada cacheado que reutilizar.

Que el techo de **producción** va corto es harina de otro costal y está en
[`_docs/deuda-tecnica.md`](../_docs/deuda-tecnica.md): 1000/hora ÷ 8 peticiones por portada son 125
vistas de página por hora **y por IP**, y una oficina tras un NAT comparte una sola.

El cuerpo es escueto a propósito —sin versiones, sin nombres de host, sin rutas—: es público.
| `GET /api/mapas/capas/` | — | capas con `estado_tiles=ok` y `visible_por_defecto`/orden: `[{ slug, nombre, url: "/tiles/rios.pmtiles", tipo_geometria, estilo, min_zoom, max_zoom, atribucion }]` |
| `POST /api/metricas/evento/` | body `form-encoded` `tipo=busqueda&ruta=/buscar&detalle=heladas` | beacon (`navigator.sendBeacon`); throttle **600/min por IP**; respuesta 204 |

> **`form-encoded` y no JSON**: con JSON el navegador exige preflight y `sendBeacon` no siempre
> puede completarlo, así que las métricas se perdían en silencio. Y **600/min y no 60**: una
> institución entera comparte IP detrás del NAT, de modo que un límite pensado para «una persona
> navegando» castiga a una oficina. Cada beacon es un `INSERT`; el coste no justifica un techo bajo.

```jsonc
// GET /api/sitio/
{
  "config": { "nombre_sitio": "Observatorio Kallpachakuy", "descripcion_footer": "…",
              "email_contacto": "…", "redes": { "facebook": "…" } },
  "bloques": { "home.hero.titulo": "…", "sobre.mision": "…", "footer.creditos": "…" },
  "menu": { "top": [ { "texto": "predes.org.pe", "url": "https://predes.org.pe/", "orden": 1 } ],
            "header": [ { "texto": "Sobre el observatorio", "url": "/sobre", "orden": 1 } ],
            "footer": [ … ] },
  "hero": [ { "titulo": "…", "subtitulo": "…", "imagen": "/media/hero/1.webp",
              "cta_texto": "Explorar el visor", "cta_url": "/peligros", "orden": 1 } ]
}
```

## Búsqueda

La búsqueda global y las facetas van **directo a Meilisearch** (`/search/`, llave search-only; ver 04), no por DRF.

## Convenciones transversales

- Errores en JSON estándar DRF (`{"detail": …}`); 404 para slugs/códigos inexistentes.
- Throttling anónimo global (p.ej. `1000/hour`), más estricto en exports y PDF (`30/hour`).
- **CORS activo también en producción** (ADR-A14: la SPA vive en `observatorio.predes.org.pe` y el API en `obs.predes.org.pe`). `django-cors-headers` con allowlist desde `CORS_ALLOWED_ORIGINS`; en dev, `localhost:5173`. nginx añade las cabeceras de `/media/` y `/tiles/`, que Django no sirve.
- Los serializers viven en `backend/apps/api/`; sus formas se reflejan en `frontend/src/lib/types.ts`.

## Rutas que NO son del API pero las sirve Django (ADR-A24, ADR-A26)

Cuelgan de la raíz, no de `/api/`, porque las pide el **dominio público** de la SPA:

| Ruta | Qué devuelve |
|---|---|
| `/(noticias\|normativa\|medidas\|peligros)/<clave>` | El `index.html` compilado de la SPA con `title`, `canonical` y `og:*` de esa ficha. Una ficha inexistente o en borrador devuelve **200 con las metas del sitio**, no un 404: el «no encontrado» lo pinta el router de React |
| `/sitemap.xml` | Las rutas fijas más las fichas publicadas, con `lastmod`. `/comparar` no se anuncia (ADR-P2) |
| `/robots.txt` | `text/plain`. Permite todo, declara `Content-Signal: ai-train=no, search=yes, ai-input=yes` y anuncia el sitemap **con `SITE_URL`**. Con `SITIO_INDEXABLE=0` pasa a `Disallow: /` y **sin** línea `Sitemap:` |
| `/.well-known/api-catalog` | `application/linkset+json` (RFC 9727, formato RFC 9264) y `Access-Control-Allow-Origin: *` |

Los tipos que acepta la primera son una **lista blanca** en `apps/sitio/vistas_html.py`, igual que
`MODELOS_CON_IA`: el segmento viene de la URL y no puede elegir qué modelo se consulta.

Las dos últimas viven en `apps/sitio/descubrimiento.py`. Están aquí y no en el bundle de la SPA por
el mismo motivo que el sitemap: **llevan dentro la URL del sitio**, y un archivo estático no puede
interpolarla — el `robots.txt` lo era y su línea `Sitemap:` acabó clavada a un dominio que no
resolvía, con lo que el sitemap funcionaba y no lo leía nadie.

### El catálogo de API

Un solo contexto, anclado en `/api/`, con las URL absolutas del **dominio del API** (`BACKEND_URL`,
ADR-A14) construidas con `reverse()`:

| Relación | Destino | Tipo |
|---|---|---|
| `service-desc` | `/api/schema/` y `/api/schema/?format=json` | `application/vnd.oai.openapi` y `…+json` |
| `service-doc` | `/api/docs/` | `text/html` |
| `status` | `/api/salud/` | `application/json` |
| `author` | `https://predes.org.pe` | — |

Se publica en **los dos orígenes** —el de la SPA y el del API—, porque un agente que llegue a
`obs.…` lo buscará ahí. Hay una prueba que **pide cada `href`**: un catálogo que existe y apunta a
URLs muertas se ve exactamente igual que uno bueno.

**No lleva nada de autenticación**, y no por olvido: el API es anónimo y de solo lectura, así que
declarar `authorization_servers` o un `token_endpoint` mandaría a un agente a negociar credenciales
contra la nada. Lo mismo vale para todo lo que el sitio decide **no** publicar bajo `/.well-known/`
(ADR-A26); nginx responde 404 ahí, que es información, en vez del 200 con HTML de antes.
