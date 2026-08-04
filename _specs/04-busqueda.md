# 04 — Búsqueda y faceting (Meilisearch)

Meilisearch v1.15 en contenedor propio (`meilisearch` en compose), volumen `meili_data`, `MEILI_MASTER_KEY` en `backend/.env`. No expuesto a internet directamente: nginx proxya solo la ruta de búsqueda, bajo el dominio del backend.

## Índices

| Índice | Documentos | searchableAttributes | filterable/facetas | sortable |
|---|---|---|---|---|
| `medidas` | Medidas publicadas | titulo, resumen_corto, contenido_texto, comunidad, tags | peligro, ambito, resultado, provincia, distrito | fecha |
| `normativa` | Normas publicadas | titulo, resumen, analisis_predes, numero | tipo, ambito, anio | fecha |
| `documentos` | Documentos publicados | titulo, resumen, autor_institucion | categoria, anio | fecha |
| `noticias` | Noticias publicadas | titulo, bajada, cuerpo_texto | tipo, anio | fecha |
| `videos` | Videos publicados | titulo, descripcion | tema | fecha |
| `eventos` | Eventos publicados | titulo, descripcion, lugar | modalidad, mes | inicio |
| `ccpp` | 8,968 centros poblados | nombre, distrito, provincia | provincia, distrito, categoria | — |

Documento tipo (ejemplo `medidas`):
```json
{ "id": 12, "slug": "qochas-pampallacta", "titulo": "Qochas comunales en Pampallacta",
  "resumen_corto": "…", "contenido_texto": "…texto plano sin markup…",
  "peligro": "Sequía", "ambito": "comunal", "resultado": "exito",
  "provincia": "Calca", "distrito": "Pisac", "tags": ["Siembra de agua"],
  "fecha": 1753830000, "url": "/medidas/qochas-pampallacta" }
```
`ccpp`: `{ "codigo": "0801010001", "nombre": "CUSCO", "categoria": "CIUDAD", "distrito": "CUSCO", "provincia": "CUSCO", "nivel_max": 4, "lat": …, "lon": … }` — alimenta el autocompletado del GeoSelector y el buscador del mapa (fly-to con lat/lon).

Los campos `*_texto` son el rich text convertido a texto plano al indexar. `fecha` como unix timestamp (sortable).

Con CKEditor 5 (ADR-D2) eso deja de ser un detalle: el `contenido` guardado es HTML real, así que **hay que despojar el markup antes de indexar** —no basta con mandar el campo tal cual—. Si no, Meili acaba indexando nombres de etiqueta, clases (`image-style-side`, `text-big`) y URLs de atributos, y una búsqueda por "figure" o "media" devuelve resultados. Extraer el texto con el mismo saneador del guardado (`nh3`/`bleach` en modo *strip*) mantiene una sola dependencia.

`palabras_clave` sustituye a `tags` como faceta en el índice `medidas`, para que las tres entidades editoriales faceten por el mismo nombre.

## Sincronización Django → Meilisearch

Doble mecanismo (señales para el día a día, comando para recuperación):

1. **Signals** `post_save`/`post_delete` en los modelos Workflow → encolan tarea `sync_meili(indice, pk)` (django-tasks; nunca bloquea el admin). Lógica: si `estado=publicado` → upsert del documento; en cualquier otro estado o borrado → delete del índice.
2. **Comando** `manage.py meili_rebuild [indice]` — reconstrucción total (swap por índice temporal para no dejar huecos). Se corre: al desplegar, tras `DatasetUpload` de peligros (índice `ccpp`) y ante cualquier inconsistencia.
3. **Comando** `manage.py meili_setup` — idempotente, corre en el arranque del backend: crea índices, aplica settings (searchable/filterable/sortable, ranking, synonyms es-PE opcionales: "helada"≈"friaje" NO — son peligros distintos; sinónimos solo ortográficos) y **genera la llave search-only** restringida a los índices públicos, imprimiéndola para copiarla a los `.env` (`VITE_MEILI_SEARCH_KEY`, ver abajo).

### La llave search-only es determinista, y tiene que serlo

Se crea con un **uid fijo** (`meili.UID_LLAVE_BUSQUEDA`). La documentación de Meilisearch lo dice así: *«Custom API keys are deterministic: the key itself is a SHA256 hash of the key's UID and the master key»*. Con uid fijo, el mismo `MEILI_MASTER_KEY` devuelve **siempre la misma llave**, de modo que recrear el volumen de Meilisearch o restaurar un respaldo no la invalida.

No es un detalle de elegancia: **la llave va horneada en el bundle compilado del frontend** (`VITE_*` son variables de build), así que una llave que cambia obliga a reconstruir y republicar el frontend, y si alguien no lo hace el sitio se degrada en tres sitios a la vez y **solo uno avisa**:

| Qué usa la llave | Qué pasa si la rechazan |
|---|---|
| `/buscar` (multi-search) | Cae al fallback de DRF **y lo dice en pantalla**: «el buscador está en modo básico» |
| Facetas de `/medidas` | `facetasDe` devuelve `{}` y los filtros se quedan **sin conteos**, sin ningún aviso |
| Autocompletado de lugares (visor, GeoSelector) | `buscarLugares` devuelve `[]`: el buscador de lugares no encuentra nada, sin ningún aviso |

Pasó en desarrollo: la llave se creaba con uid aleatorio, un `down -v` la cambió, se actualizó `frontend/.env` y no el `.env` de la raíz —el que Compose hornea en el bundle—, y el sitio compilado se quedó buscando con una llave inexistente. Por eso, además del uid fijo: `frontend/src/lib/search.ts` distingue el rechazo de credencial (401/403) del «no responde» y escribe en consola un mensaje explícito, que es la única pista disponible para quien opera el sitio.

Cambiar los índices públicos obliga a **borrar y recrear** la llave (`PATCH /keys/{uid}` solo admite `name` y `description`); al recrearla con el mismo uid vuelve a salir idéntica, así que el frontend ya desplegado sigue siendo válido. Sin eso, añadir un índice público dejaría a la llave sin permiso sobre él y ese índice devolvería 403 **solo él**, con el resto funcionando.

Cliente Python: paquete `meilisearch` en `core/services/meili.py`.

## Consumo desde el frontend (ADR-A4)

- nginx proxya `obs.predes.org.pe/search/*` → `meilisearch:7700` (ADR-A14; el navegador lo llama cross-origin, con CORS). El navegador usa la **llave search-only** (segura por diseño: solo búsqueda, solo índices permitidos; la master key nunca sale del backend).
- `/buscar` (búsqueda global): `POST /search/multi-search` federado sobre todos los índices de contenido; render agrupado por tipo con conteos.
- `/medidas`: índice `medidas` con `facets: ["peligro","ambito","resultado","provincia"]` — reemplaza el filtrado client-side del prototipo y muestra conteos por faceta.
- GeoSelector/buscador del mapa: índice `ccpp` con `limit: 8` para autocompletar.
- Cliente en `frontend/src/lib/search.ts` (fetch puro; no hace falta SDK).
- Cada búsqueda emite beacon `POST /api/metricas/evento/ {tipo:"busqueda", detalle:q}` (métrica interna TDR).

## Fallback

Si Meilisearch está caído, el frontend degrada a los endpoints DRF con filtros (`/api/medidas/?…`, `/api/ccpp/?buscar=`) — sin facetas ni typo-tolerance, pero funcional. Implementar como catch en `search.ts`.
