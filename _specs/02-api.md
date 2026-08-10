# 02 — Contrato del API

DRF + django-filter + drf-spectacular (ADR-A2). Prefijo `/api/`. Todo el API público es **solo lectura**, devuelve únicamente contenido con `estado=publicado`, paginado (`page`/`page_size`, default 50, máx 200) salvo donde se indique. OpenAPI en `/api/schema/` + Swagger UI en `/api/docs/`.

Las formas de respuesta **espejan los tipos del prototipo** (`prototype/src/lib/types.ts` y los JSON de `prototype/public/data/`) para minimizar cambios en el frontend; se eliminan los flags `_mock`.

## Territorio y peligros

| Endpoint | Params | Notas |
|---|---|---|
| `GET /api/territorio/provincias/` | — | sin paginar (13) |
| `GET /api/territorio/distritos/` | `provincia=<ubigeo4>` | sin paginar (112) |
| `GET /api/ccpp/` | `provincia`, `distrito` (ubigeo6), `peligro` (slug), `nivel_min` 1-4, `buscar`, `clasificados`, `page` | Padrón con `nivel` anotado (máximo tras los filtros; `null` = sin dato). **`clasificados=1`** deja solo los que tienen clasificación: es lo que usa la tabla del visor, porque el padrón completo la convertiría en una lista de «sin dato» (5,730 de 8,968 en la región). Ordena por nivel descendente con los «sin dato» al final |
| `GET /api/ccpp/{codigo}/` | — | ficha con clasificaciones anidadas |
| `GET /api/ccpp/export.xlsx` | mismos filtros que la lista | openpyxl, streaming |
| `GET /api/ccpp/geojson/` | mismos filtros que la lista, **sin paginar** | Puntos del visor (ver 05 / ADR-A13). `FeatureCollection` de `Point`; ver el ejemplo y la nota de tamaño más abajo |
| `GET /api/peligros/tipos/` | — | catálogo (9) con orden y color |
| `GET /api/peligros/resumen/` | `provincia`, `distrito`, `peligro`, `nivel_min` | agregados para cifras del home/visor. Devuelve **las dos unidades** (por CCPP y por clasificación) rotuladas; ver el ejemplo |
| `GET /api/peligros/frecuencia/` | `distrito`, `provincia`, `categoria` | Lista, sin paginar (90 de 112): una entrada por distrito **con datos de cualquiera de las dos tablas** |
| `GET /api/peligros/frecuencia/{ubigeo}/` | — | El panel de un distrito. **404** si no tiene fila (ver abajo) |
| `GET /api/peligros/frecuencia/export.xlsx` | ídem | Incluye los totales declarados marcados, o el Excel dejaría a Cusco en cero |

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
// GET /api/ccpp/geojson/?provincia=0803&peligro=sismo&nivel_min=3
{
  "type": "FeatureCollection",
  "features": [
    { "type": "Feature",
      "geometry": { "type": "Point", "coordinates": [-71.97675606, -13.51927548] },
      "properties": {
        "codigo": "0801010001", "nombre": "CUSCO", "categoria": "CIUDAD",
        "distrito": "CUSCO", "provincia": "CUSCO", "poblacion": 111930, "altitud": 3439,
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
  "altitud": 3439, "poblacion": 111930,
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
  "total_ccpp": 123, "poblacion_total": 130000,
  // [+] Distribución por nivel MÁXIMO de cada centro poblado: es lo que pinta el panel
  // "Distribución" de /peligros y lo que debe cuadrar con el conteo de la tabla.
  // NO se puede derivar de `por_peligro` — sumar por peligro cuenta cada CCPP tantas veces
  // como peligros tenga evaluados (ACOMAYO: 75 CCPP → 225 clasificaciones). Tiene que venir
  // agregado del servidor, y debe respetar los mismos filtros de peligro y nivel mínimo.
  "por_ccpp": { "niveles": { "1": 0, "2": 0, "3": 26, "4": 49 }, "sin_clasificar": 0 },
  "por_peligro": [
    { "peligro": "Sismo", "slug": "sismo",
      "niveles": { "1": 0, "2": 3, "3": 40, "4": 80 }, "sin_dato": 0 }
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
| `GET /api/normativa/` | `tipo`, `ambito`, `anio`, `tema`, `page` | |
| `GET /api/normativa/{slug}/` | — | ficha con `contenido` desarrollado |
| `GET /api/normativa/export.xlsx` | ídem que el listado | |
| `GET /api/noticias/` | `tipo`, `destacada`, `tema`, `page` | orden -fecha |
| `GET /api/noticias/{slug}/` | — | |

`tema` filtra por coincidencia exacta en `palabras_clave`; es lo que alimenta los chips navegables de las fichas (`?tema=…` en el frontend).

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
  "fecha": "2011-02-19", "resumen": "Crea el SINAGERD…",
  "url_oficial": "https://…", "analisis_predes": null
} ] }
```

## Inversión (PP 0068)

| Endpoint | Params |
|---|---|
| `GET /api/inversion/` | `anio` (default: el más reciente visible), `ambito` (`municipal` por defecto \| distrital \| provincial \| regional \| todos), `provincia` (ubigeo o nombre) |
| `GET /api/inversion/export.xlsx` | los mismos |

Sin ningún ejercicio `visible`:
```json
{ "disponible": false, "motivo": "PREDES está consolidando los datos de inversión del PP 0068." }
```

Es el **mismo contrato** que servía la ventana cuando estaba diferida, y se conserva a propósito: el cliente no necesita un caso especial para «hay datos pero todavía sin publicar», que es el estado normal entre una importación y la revisión de PREDES.

Un `anio` que no existe o que no está visible **no cae al último**: devuelve `disponible: false`. Servir otro ejercicio se vería perfecto y todas las cifras serían del año equivocado.

Con datos:
```jsonc
{
  "disponible": true, "anio": 2026, "corte": "2026-06", "es_parcial": true,
  "fuente": "Base PP 0068 entregada por PREDES",
  "ambito": "municipal", "unidad": "municipalidad (entidad ejecutora), no distrito",
  "agregados": { "pia": 16754644, "pim": 54591255, "devengado": 26064745,
                 "pct_ejecucion": 0.4775, "saldo": 28526510, "variacion_pia_pim": 37836611,
                 "entidades_con_presupuesto": 115, "entidades_en_ambito": 116,
                 "pct_0068_institucional": 0.0127, "entidades_con_institucional": 114,
                 "pim_proyectos": 22217511, "pim_actividades": 32373744, "pct_proyectos": 0.407 },
  "procesos": [ { "slug": "prevencion_reduccion", "nombre": "Prevención y reducción",
                  "color": "#009257", "pim": 28909461, "devengado": 0, "pct": 0.53 } ],
  "sin_clasificar": { "pim": 0, "devengado": 0, "pct": 0 },
  "tendencia": [ { "anio": 2022, "corte": "anual", "es_parcial": false, "fuente": "…",
                   "pia": 18060834, "pim": 48813109, "devengado": 37260987 } ],
  "por_entidad": [ { "codigo": "300684", "entidad": "MUNICIPALIDAD PROVINCIAL DEL CUZCO",
                     "ambito": "provincial", "ubigeo_distrito": "080101",
                     "distrito": "CUSCO", "provincia": "CUSCO",
                     "pia": 0, "pim": 0, "devengado": 0, "pct_ejecucion": 0.0,
                     "saldo": 0, "variacion_pia_pim": 0, "pct_variacion_pia_pim": 0.0,
                     "pim_institucional": 270220526, "pct_0068_institucional": 0.0,
                     "pim_proyectos": 0, "pim_actividades": 0, "pct_proyectos": 0.0 } ],
  "ejercicios": [ { "anio": 2026, "corte": "2026-06", "es_parcial": true } ]
}
```

Tres reglas del payload que la interfaz no puede reinventar:

- **`es_parcial` y `corte` viajan con el dato**, en la raíz y en cada punto de `tendencia`. Un % de ejecución de medio año se calcula contra un PIM anual: cualquier cliente que lo dibuje tiene que poder advertirlo.
- **Un porcentaje que no se puede calcular es `null`, no `0`.** Una municipalidad sin total institucional no tiene un 0 % de su presupuesto en el 0068.
- **`pct_0068_institucional` de `agregados` solo suma entidades comparables.** Con el numerador de las 116 y el denominador de las 114 que tienen total, el porcentaje saldría inflado sin que nada lo dijera; por eso viaja `entidades_con_institucional`.

## Productos de incidencia

| Endpoint | Params | Notas |
|---|---|---|
| `GET /api/comparador/distritos/` | `ubigeos=080101,080301` (2–4), `anio` | por distrito: población, conteo CCPP por peligro×nivel, frecuencia de emergencias, inversión (si `disponible`), nº medidas publicadas |
| `GET /api/distritos/{ubigeo}/ayuda-memoria.pdf` | `anio`, `peligro` (slug), `nivel_min` | WeasyPrint; cache en `media/informes/` 24 h, invalidado por imports |

**La maqueta de la ayuda memoria ya existe**: `prototype/src/components/ReporteImpresion.tsx`, validada en pantalla y en vista previa de impresión. Es HTML+CSS estándar, que es justo lo que consume WeasyPrint, así que la plantilla del backend parte de ahí en vez de diseñarse de cero. Estructura del documento: membrete PREDES · ámbito y filtros aplicados · fecha de generación · párrafo de presentación redactado con las cifras del propio filtro · mapa · distribución por nivel · emergencias del distrito · tabla de centros poblados clasificados · fuentes y firma institucional.

Notas de contrato heredadas de la maqueta:

- **El alcance es un distrito**, con `peligro` y `nivel_min` como refinamientos opcionales. Un reporte regional o provincial produce decenas de páginas y deja de servir para una mesa técnica.
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
  "menu": { "header": [ { "texto": "Exposición a peligros", "url": "/peligros", "orden": 1 } ],
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
