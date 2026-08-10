# El API

Guía de uso del API público. El **contrato formal** —cada campo de cada payload— está en
`_specs/02-api.md`, y la referencia siempre viva la genera drf-spectacular a partir del código:

- **`https://obs.predes.org.pe/api/docs/`** — Swagger UI, se puede probar desde el navegador.
- **`https://obs.predes.org.pe/api/schema/`** — el OpenAPI 3 en YAML, para generar clientes.

En desarrollo, `http://localhost:8000/api/docs/`.

Si el esquema y este documento discrepan, gana el esquema: sale del código.

## Reglas generales

**Todo es público y de solo lectura**, sin autenticación, con dos excepciones: el `POST` de
métricas (también anónimo) y el admin, que no es parte del API. Escribir se hace desde el admin.

**Solo se ve lo publicado.** Todos los recursos editoriales filtran por `estado=publicado`; los
borradores y lo que está en revisión no existen para el API, no aparecen ni con un id directo.

**Paginación** al estilo DRF, `?page=` y `?page_size=` (por defecto 50, máximo 200):

```json
{"count": 3238, "next": "...?page=2", "previous": null, "results": [...]}
```

**Límites de uso**: 1000 peticiones/hora por IP en general, 30/hora en exports Excel y en el PDF
(son caros de generar), 60/minuto en el beacon de métricas. Al pasarse, `429` con `Retry-After`.

**CORS**: el origen `https://observatorio.predes.org.pe` está en la allowlist. Para consumir el
API desde otro dominio hay que pedir que lo añadan a `CORS_ALLOWED_ORIGINS`. Desde un servidor
(curl, Python, R) CORS no aplica y funciona sin más.

## Territorio y peligros

| Endpoint | Devuelve |
|---|---|
| `GET /api/territorio/provincias/` | Las 13 provincias de Cusco, con conteos |
| `GET /api/territorio/distritos/` | Los 112 distritos. `?provincia=` por ubigeo o nombre |
| `GET /api/ccpp/` | El padrón de 8,968 centros poblados, paginado |
| `GET /api/ccpp/{codigo}/` | Ficha de un centro poblado con sus clasificaciones |
| `GET /api/ccpp/geojson/` | Los mismos, como FeatureCollection para el mapa |
| `GET /api/ccpp/export.xlsx` | Lo filtrado, en Excel |
| `GET /api/peligros/tipos/` | El catálogo de 9 peligros con slug, color y categoría |
| `GET /api/peligros/resumen/` | Agregados para las tarjetas y el gráfico de distribución |
| `GET /api/peligros/frecuencia/` | Frecuencia de emergencias, un registro por distrito |
| `GET /api/peligros/frecuencia/{ubigeo}/` | El desglose por tipo de evento de un distrito |
| `GET /api/peligros/frecuencia/export.xlsx` | Lo anterior en Excel |

Filtros de `/api/ccpp/` y `/api/ccpp/geojson/` — los mismos que la interfaz de `/peligros`:

| Parámetro | Ejemplo | Nota |
|---|---|---|
| `provincia`, `distrito` | `?provincia=0803` | Acepta **ubigeo o nombre** |
| `peligro` | `?peligro=lluvias_intensas` | Slug del catálogo. **Guion bajo** |
| `nivel_min` | `?nivel_min=3` | 1 muy bajo … 4 muy alto |
| `clasificados` | `?clasificados=1` | Descarta los que no cumplen (ver abajo) |
| `categoria` | `?categoria=CASERIO` | Categoría del centro poblado |
| `buscar` | `?buscar=pisac` | Coincidencia parcial en el nombre |

Dos cosas sobre estos filtros, y ambas se han malinterpretado antes:

**`peligro` y `nivel_min` se aplican como una sola condición**, no en dos pasos.
`?peligro=heladas&nivel_min=4` describe centros poblados con **heladas** en nivel 4, no los que
tienen heladas *y además* cualquier otra cosa en nivel 4. Aplicarlos por separado daría un conjunto
más grande y falso.

**Por sí solos no recortan la lista: rellenan el campo `nivel`.** Sin `clasificados=1` la respuesta
trae los 8,968 centros poblados, con `nivel` en los que cumplen y `null` en el resto. Es
intencional —el mapa necesita pintar todos los puntos, en gris los que no cumplen—, pero significa
que **`count` no es la respuesta a «cuántos cumplen»**:

```
?peligro=lluvias_intensas&nivel_min=4                    → count 8968   ← no es lo que parece
?clasificados=1&peligro=lluvias_intensas&nivel_min=4      → count    4   ← esta es la cifra
```

Para contar, filtrar o exportar: **`clasificados=1` siempre**. Para dibujar el mapa: sin él.

Los resultados vienen ordenados por nivel descendente, con los «sin dato» al final.

### Dos unidades distintas, y no son intercambiables

`GET /api/peligros/resumen/` trae dos bloques que **cuentan cosas distintas**:

```json
{
  "total_ccpp": 8968,
  "poblacion_total": 1205527,
  "por_ccpp": {
    "niveles": {"1": 31, "2": 253, "3": 922, "4": 2032},
    "sin_clasificar": 5730
  },
  "por_peligro": [
    {"peligro": "Sismo", "slug": "sismo",
     "niveles": {"1": 80, "2": 103, "3": 203, "4": 1127}, "sin_dato": 7455}
  ],
  "unidades": {
    "por_ccpp": "centros poblados, por su nivel máximo",
    "por_peligro": "clasificaciones (un centro poblado aporta una por peligro evaluado)"
  }
}
```

- **`por_ccpp.niveles`** cuenta **centros poblados**, cada uno una vez, en su nivel más alto → los
  cuatro valores suman 3,238.
- **`por_peligro`** cuenta **clasificaciones**: un centro poblado aporta una por cada peligro que
  tenga evaluado. Sumado sobre los 9 peligros da 10,978.

Difieren en 3.4×, y confundirlas es el error más fácil de cometer con estos datos: los 75 centros
poblados de Acomayo tienen 3 peligros cada uno y aparecerían como 225. Por eso el payload declara
sus propias unidades en `unidades` — **cualquier gráfico que se dibuje con esto tiene que decir
cuál de las dos está mostrando**: en nivel muy alto hay 2,032 centros poblados y 3,051
clasificaciones, y ninguna de las dos cifras es «2,032 casos».

**`sin_clasificar` y `sin_dato` no son «nivel bajo»**, son ausencia de información. Se cuentan
aparte a propósito, y `sin_dato` es por peligro: un centro poblado puede tener lluvias evaluadas y
heladas no.

### Frecuencia: 404 y `total: 0` significan cosas distintas

`GET /api/peligros/frecuencia/{ubigeo}/`:

- **`404`** → ese distrito **no tiene fila** en la fuente. No sabemos nada de él. Es el caso de
  Acomayo, y está anotado como dato a pedirle a PREDES.
- **`200` con `total: 0`** → hay fila y declara cero emergencias.

Además, `desglose_disponible` distingue un tercer estado. Cusco, por ejemplo:

```json
{
  "distrito": "CUSCO", "ubigeo": "080101", "provincia": "CUSCO",
  "rango_fecha": "2003-2022",
  "fuente": "SIGRID_CENEPRED", "fuente_url": "https://n9.cl/e9qwr",
  "desglose_disponible": false,
  "categorias": [
    {"categoria": "Geodinámica externa", "slug": "geodinamica_externa",
     "total": 43, "solo_total": true, "eventos": []}
  ],
  "total": 134
}
```

26 distritos declaran subtotales por categoría sin desglosarlos por tipo de evento (ADR-D1). Los
totales son reales y se pueden citar; lo que falta es el reparto interno. Un cliente que interprete
`eventos: []` como «cero emergencias» dirá justo lo contrario de lo que dice el dato: por eso está
`solo_total`, para que la interfaz lo enuncie en vez de dibujar un gráfico vacío.

**`rango_fecha` es por distrito** —hay 23 periodos distintos en la fuente—, así que los totales de
dos distritos no son comparables sin decir de qué años son cada uno, y ningún agregado provincial
o regional puede anunciar un periodo único.

## Contenido editorial

| Endpoint | Filtros |
|---|---|
| `GET /api/medidas/` · `/{slug}/` | `peligro`, `ambito`, `resultado`, `provincia`, `distrito`, `tema`, `destacada` |
| `GET /api/normativa/` · `/{slug}/` · `export.xlsx` | `tipo`, `ambito`, `anio`, `tema` |
| `GET /api/noticias/` · `/{slug}/` | `tipo`, `anio`, `tema`, `destacada` |
| `GET /api/videos/` | `tema` |
| `GET /api/eventos/` | — |
| `GET /api/biblioteca/` · `/{slug}/` · `categorias/` | `categoria`, `anio`, `buscar` |

`?tema=` cruza `palabras_clave`; es lo que hace navegables los chips de las fichas.

El campo `imagen_portada` **siempre trae una URL utilizable**: si el registro no tiene imagen
propia, el serializer resuelve una ilustración institucional según el peligro o el tipo. El
cliente no tiene que decidir nada ni llevar un catálogo de imágenes por defecto.

## Incidencia

**`GET /api/comparador/distritos/?ubigeos=080101,080301`** — **entre 2 y 4** distritos lado a lado
con sus cifras de peligro y emergencias; fuera de ese rango responde `400`. Trae
`inversion_disponible: false` mientras esa sección siga diferida (ver abajo). Sigue publicado y
soportado aunque **su página ya no se anuncie en el menú del sitio** (ADR-P2): `/comparar` responde
por URL directa y el enlace se recupera desde el admin.

**`GET /api/distritos/{ubigeo}/ayuda-memoria.pdf`** — la ayuda memoria de dos caras, generada en
el servidor con su mapa. Tarda unos segundos porque captura el mapa con un navegador headless. Si
esa captura falla, **el PDF se entrega igual, sin mapa**: es una degradación deliberada, para que
un fallo del renderizador no deje a nadie sin su documento en una reunión.

## Sitio, mapas, búsqueda

**`GET /api/sitio/`** — un solo payload con la configuración administrable: textos, menús, hero,
redes y datos de contacto. Es la primera petición que hace la SPA. Cacheable.

**`GET /api/mapas/capas/`** — las capas de contexto del visor (hoy ríos, lagunas y glaciares), cada
una con su `url` de tiles **absoluta**, su `tipo_geometria` y un `estilo` que es directamente una
especificación de capa de MapLibre:

```json
[{"slug": "rios", "nombre": "Ríos", "url": "https://obs.predes.org.pe/tiles/rios.pmtiles",
  "tipo_geometria": "linea", "estilo": {"tipo": "line", "line-color": "#0095A4", "…": "…"}}]
```

Solo se anuncian las capas con tiles generados: una a medio procesar no aparece, y por eso una
lista vacía es el primer síntoma a mirar cuando el visor sale sin capas. Que el estilo y la URL
vengan del servidor es lo que permite a PREDES subir un GeoJSON nuevo y verlo en el mapa **sin
desplegar nada**.

**`GET /api/buscar/?q=`** — búsqueda agrupada por tipo de contenido. Es el **fallback**: el
frontend consulta Meilisearch directamente para tener facetas y tolerancia a errores de tecleo.
`GET /api/buscar/estado/` dice si Meilisearch está disponible.

**`POST /api/metricas/evento/`** — registro de uso, `application/x-www-form-urlencoded` para que
`navigator.sendBeacon` no necesite preflight. No guarda datos personales: la sesión es un hash
diario de IP+user-agent truncado, que no permite reidentificar a nadie ni seguirle la pista de un
día para otro.

## Inversión

**`GET /api/inversion/`** — el tablero del PP 0068 **por municipalidad**. Acepta `anio`, `ambito`
(`municipal` por defecto, `distrital`, `provincial`, `regional`, `todos`) y `provincia` (ubigeo o
nombre). **`GET /api/inversion/export.xlsx`** devuelve la misma tabla en Excel, con los mismos
filtros.

Mientras PREDES no publique ningún ejercicio, responde:

```json
{"disponible": false, "motivo": "PREDES está consolidando los datos de inversión del PP 0068."}
```

No es un residuo de cuando la sección estaba diferida: es el estado normal entre una importación y
su revisión, y ahorra al cliente un caso especial. Un `anio` que no esté publicado devuelve lo
mismo en vez de caer al último visible, que se vería bien con las cifras de otro año.

Con datos, el payload trae `agregados`, `procesos` (más `sin_clasificar`), `tendencia`,
`por_entidad` y la lista de `ejercicios` publicados. Tres detalles que conviene no perder al
consumirlo:

- **`es_parcial` y `corte`** viajan en la raíz y en cada punto de la tendencia. El ejercicio en
  curso llega a mitad de año y su % de ejecución se calcula contra un PIM anual.
- **Un porcentaje que no se puede calcular es `null`, no `0`** (`pct_ejecucion`,
  `pct_0068_institucional`, `pct_proyectos`).
- **`pct_0068_institucional` de `agregados` solo suma entidades comparables**; por eso viene
  acompañado de `entidades_con_institucional`.

## Los tiles

No son parte del API REST, pero se consumen igual desde el navegador. **No hay que construir estas
URL a mano**: salen de `/api/mapas/capas/`, y cablearlas fue un error real que dejó el visor pidiendo
tiles al servidor de desarrollo del frontend.

```
https://obs.predes.org.pe/tiles/{rios,lagunas,glaciares}.pmtiles     (contexto)
https://obs.predes.org.pe/tiles/ccpp.pmtiles                         (centros poblados)
```

Son archivos **PMTiles**, que se leen por trozos con peticiones `Range` — no hay que descargarlos
enteros. Con MapLibre:

```js
import { Protocol } from 'pmtiles'
maplibregl.addProtocol('pmtiles', new Protocol().tile)
// source: { type: 'vector', url: 'pmtiles://https://obs.predes.org.pe/tiles/rios.pmtiles' }
```

`ccpp.pmtiles` (3.0 MB, zoom 3–12) está publicado para quien quiera montar su propio visor, pero
**el visor del Observatorio no lo usa**: la capa de centros poblados viene de
`/api/ccpp/geojson/`, porque MapLibre solo agrupa en clusters las fuentes `geojson` y el diseño
pide símbolos proporcionales a la población (ADR-A13).

En sus features, las propiedades de nivel por peligro se llaman **`nivel_<slug>`** con guion bajo:
`nivel_lluvias_intensas`, `nivel_heladas`. Las claves ausentes se omiten en lugar de ir a `null`,
así que hay que comprobar existencia, no valor.

## Ejemplos

```bash
# Cuántos centros poblados hay con heladas en nivel muy alto (ojo al clasificados=1)
curl -s 'https://obs.predes.org.pe/api/ccpp/?clasificados=1&peligro=heladas&nivel_min=4&page_size=1' \
  | python -c 'import json,sys; print(json.load(sys.stdin)["count"])'   # 345

# Los de una provincia, en Excel
curl -sO 'https://obs.predes.org.pe/api/ccpp/export.xlsx?provincia=Calca&clasificados=1'

# La ayuda memoria de un distrito
curl -so acomayo.pdf 'https://obs.predes.org.pe/api/distritos/080201/ayuda-memoria.pdf'
```

```python
import requests

BASE = "https://obs.predes.org.pe/api"

# Recorrer todas las páginas
url, filas = f"{BASE}/ccpp/?clasificados=1&page_size=200", []
while url:
    datos = requests.get(url, timeout=60).json()
    filas += datos["results"]
    url = datos["next"]
print(len(filas))  # 3238
```

## Citar los datos

El Observatorio **no es la fuente primaria**: los niveles de peligro salen de CENEPRED/SIGRID y
las emergencias del INDECI. Cada recurso trae `fuente` y `fuente_url`, y lo correcto es citar la
fuente original indicando al Observatorio como intermediario y la fecha de consulta. Los datos son
de acceso abierto; el uso indebido de una cifra sin su unidad ni su fuente es el riesgo real de
este API, no el volumen de peticiones.
