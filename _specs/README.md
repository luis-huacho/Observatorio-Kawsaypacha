# Specs — Observatorio Kallpachakuy (fase de construcción)

Especificaciones técnicas de la plataforma real, sucesora del prototipo aprobado (`prototype/`, congelado como referencia). Contrato N°0362026/PREDES; plataforma en línea el **13/08/2026**.

## Estado

- Fase 0 (prototipo estático) **completada y aprobada** por PREDES.
- Fase actual: construcción de `frontend/` (Vite + React + TS + MapLibre) y `backend/` (Django 5.2 LTS + PostgreSQL + Meilisearch + PMTiles), desplegados con Docker Compose.

### Actualización 03/08/2026 — botón de limpiar en las cajas de búsqueda

Las cinco cajas del sitio ganan una «X» para vaciarlas. Se corrigieron 06 y 08:

- **`CajaBusqueda.tsx`** concentra el comportamiento de las cuatro cajas en React —`/buscar`, el
  filtro de la biblioteca y las dos de la cabecera—: la «X» solo con texto, `type="button"` (dos
  viven dentro de un `<form>`), el foco de vuelta al campo y `Escape` como atajo. La del visor es un
  control de MapLibre a mano y lleva su equivalente imperativo, que **no borra el marcador**.
- Regla de producto en 06: **en `/buscar` la «X» no toca la URL**. El término vive en `?q=` y los
  resultados se quedan hasta que se envíe la nueva búsqueda.
- De paso, la prueba del buscador de lugares del visor **dejó de saltarse siempre**: miraba el DOM
  antes de que MapLibre añadiera el control, así que ese buscador no estaba cubierto por nadie.

### Actualización 03/08/2026 — la llave de búsqueda pasa a ser determinista

El buscador apareció en «modo básico» en el sitio compilado. La causa: la llave *search-only* se
creaba con **uid aleatorio**, así que vivía en el volumen de Meilisearch; un `down -v` la cambió, se
actualizó `frontend/.env` y no el `.env` de la raíz —el que Compose hornea en el bundle— y el sitio
quedó buscando con una llave inexistente (403). Se corrigieron 04 y 08:

- **La llave se crea con un uid fijo**, y por eso ya no caduca: la documentación de Meilisearch
  garantiza que `key` es el SHA-256 del uid con la master key, de modo que el mismo
  `MEILI_MASTER_KEY` devuelve siempre la misma llave. Comprobado destruyendo el volumen: sale
  idéntica. Cambiar los índices públicos obliga a borrar y recrear —`PATCH /keys` no admite tocar
  `indexes`—, y al recrear con el mismo uid la llave no cambia.
- **Un rechazo de llave degrada tres cosas y solo una avisa** (documentado en 04): la búsqueda global
  cae al fallback y lo dice; las facetas de `/medidas` se quedan sin conteos y el autocompletado de
  lugares sin resultados, las dos en silencio. `lib/search.ts` pasa a distinguir el 401/403 del «no
  responde» y a escribirlo en consola.
- **Dos pruebas que no probaban lo que decían** (en 08): la de «se usa Meilisearch» comprobaba que se
  llamara a `multi-search`, no que respondiera 200, así que pasaba con el 403; y la corrida en
  desarrollo no puede detectar este fallo, porque la llave del bundle solo se usa en el sitio
  compilado.

### Actualización 03/08/2026 — el comparador fuera del menú y el header en una línea

Dos cambios pedidos sobre el cascarón del sitio. Se corrigieron 00, 06 y 08:

- **Nuevo ADR-P2**: `/comparar` sale del menú principal y del pie, pero **la ruta y el endpoint se
  quedan** y responden por URL directa. Es un grado más suave que ADR-P1. El enlace vive en tres
  sitios y hay que tocar los tres o reaparece: la semilla (`visible: false`), la base ya sembrada
  —de ahí la migración `sitio.0002`, porque el seed crea lo que falta y no pisa lo que existe— y el
  **menú de respaldo del frontend**, que es el que se pinta mientras carga `/api/sitio/` y en modo
  degradado.
- **El menú de escritorio va en una línea.** No lo estaba: a 1024 px «Exposición a peligros» partía
  su texto en dos dentro de una barra de altura fija. Se fija en 06 quién cede el espacio —los
  enlaces con `whitespace-nowrap`, logo y `nav` con `shrink-0`, el buscador con `min-w-0`— y se mide
  en `e2e/header.spec.ts`.
- Trampa de medición anotada en 08: **`getClientRects().length` sobre el elemento no detecta el
  salto de línea** (los enlaces son bloques: un solo rectángulo aunque midan 56 px de alto). Las
  líneas se cuentan con un `Range` sobre el contenido.

### Actualización 03/08/2026 — auditoría de cifras del visor y clustering

Auditar por qué `/peligros` mostraba 225 en "Distribución" y 75 en la tabla para ACOMAYO destapó
una ambigüedad de unidades y arrastró un cambio de arquitectura en la capa CCPP. Se corrigieron
00, 01, 02, 05 y 06:

- **Las dos cifras eran correctas y contaban cosas distintas**: 225 clasificaciones = 75 CCPP × 3
  peligros evaluados. La UI pasa a contar centros poblados por su nivel máximo (misma unidad que la
  tabla y el mapa). Toda cifra de distribución en los specs lleva ahora su unidad declarada (01).
- **Nuevo ADR-A13**: la capa CCPP del visor deja PMTiles y pasa a fuente `geojson` agrupada, porque
  **MapLibre solo agrupa fuentes `geojson`** y el clustering con símbolos proporcionales a
  población es requisito. Ríos, lagunas y glaciares siguen en PMTiles.
- Con clustering, **filtrar con `setFilter` es incorrecto**: los clusters se calculan antes del
  filtro de capa y su conteo mentiría. Se filtra con `setData` (05).
- Hueco en el contrato de API: `/api/peligros/resumen/` no permitía derivar el nivel máximo por
  CCPP, y falta un `/api/ccpp/geojson/` para los puntos del visor. Ambos anotados en 02, el segundo
  **sin definir todavía**.
- Dos bugs reales encontrados por el camino, ambos documentados en 05: el guard de estilo
  `once("load")` que recomendaba el propio spec **no funciona** y perdía efectos en silencio, y
  `fonts.openmaptiles.org` dejó de servir glifos (devuelve HTML con status 200). Los glifos pasan a
  auto-hospedarse.

### Actualización 02/08/2026 — auditoría de los Excel y prueba del pipeline de tiles

Los specs se escribieron contra una versión anterior de los datos. Al auditar los archivos reales de `data/layers/` se corrigieron 00, 01, 02, 03, 05 y 06. Lo que cambió de fondo:

- El Excel de niveles fue actualizado por el cliente: **10,978 clasificaciones**, no ~6,566. Solo 3,238 de 8,968 CCPP tienen dato.
- El nombre del peligro está en la columna `PELIGRO`, **no en el título de la hoja** (dos discrepancias).
- `subtipo` sale de `ClasificacionPeligro` y pasa a `TipoPeligro.categoria_geo` (era funcionalmente dependiente del peligro).
- Nuevo **ADR-D1** y modelo `TotalDeclaradoEmergencias`: el distrito de Cusco declara 134 emergencias sin desglose.
- **`glaciares.geojson` está en EPSG:32718**, no en lat/lon — sin reproyectar, los tiles salen vacíos.
- El filtro de lagunas debe ser case-insensitive (`ILIKE`), o pierde 73 polígonos.

El pipeline del spec 05 se validó de punta a punta en el prototipo (`prototype/scripts/build_tiles.sh` + ruta `/peligros/mapa-nuevo`, solo en desarrollo). Los `.pmtiles` no se versionan.

### Actualización 03/08/2026 — decisiones de despliegue y arranque de la construcción

- **ADR-A6bis**: nginx + certbot en contenedor sustituyen a Caddy.
- **ADR-A14**: dos dominios — `observatorio.predes.org.pe` (SPA) y `obs.predes.org.pe` (API, admin, media, tiles, search), con CORS entre ambos. 07 reescrito en consecuencia. (A13 ya estaba tomado por la capa CCPP agrupada.)
- **ADR-D3**: la ventana Inversión se difiere; solo se entrega la ruta con su estado vacío.
- Se cierran los dos pendientes que los specs arrastraban: **`GET /api/ccpp/geojson/`** queda definido en 02 (FeatureCollection completo con los mismos filtros que la tabla), y el **mapa de la ayuda memoria se renderiza en servidor** con navegador headless.
- Nuevo **08-plan-pruebas.md**. Se evaluó añadir `data-model.md`, `infra.md`, `prod.md`, `tech.md` y `ui.md`: los cinco ya están cubiertos por 01, 07, 00 y 06, y duplicarlos solo garantiza que se desincronicen.
- `frontend/` se recreó desde `prototype/`: la copia anterior era previa a la migración a MapLibre.

### Actualización 03/08/2026 — la suite de pruebas y los seis fallos silenciosos

Escribir las pruebas del plan 08 encontró seis defectos, **ninguno visible**: en los seis casos el
sistema respondía 200 y la pantalla se veía bien. Se corrigieron con las pruebas que los detectan, y
08 los lista con su síntoma para que quede el argumento de por qué la fase existe:

- **El proxy `/search/` mandaba todo a la raíz de Meilisearch.** Una variable en `proxy_pass`
  desactiva la sustitución del prefijo de la `location`, así que la barra final no reescribía nada.
  El buscador caía al fallback de DRF en cada búsqueda. Y `GET /search/health` devolvía 200 —la raíz
  de Meilisearch también responde 200—, de modo que la comprobación obvia lo tapaba. Corregido en 07
  con `rewrite`; la verificación de despliegue pasa a ser `POST /search/multi-search`.
- **El listado de frecuencia omitía los 26 distritos que solo declaran subtotales** (ADR-D1), Cusco
  incluido, mientras su detalle sí los servía. Se añade `consultas.distritos_con_emergencias`, que
  mira las dos tablas: 64 → 90 entradas sobre los datos reales. Documentado en 02.
- **El export de frecuencia ignoraba los filtros** al añadir los declarados.
- **El saneado de HTML vivía en el admin**, no en `save()`, mientras el `help_text` del campo
  prometía lo contrario (01 y 03 actualizados con `HtmlRicoMixin`).
- **21 distritos con fila vacía** recibían el aviso de ADR-D1, que dice otra cosa. Nuevo hallazgo de
  calidad de datos en 00: son un vacío de información, no un «declara sin desagregar».
- **El beacon de métricas estaba limitado a 60/min por IP**, y una institución entera comparte IP
  detrás del NAT (07).

Dos lecciones de método, ya en 08: la corrida E2E **contra nginx** no es opcional —en desarrollo el
navegador ataca a Meilisearch directamente y el fallo del proxy no existe—, y las dos muestras de
Excel tienen que ser consistentes entre sí, porque el importador de frecuencia resuelve el distrito
por nombre contra el padrón y sin un CCPP de Ollantaytambo las pruebas de ADR-D1 pasaban sin
comprobar nada.

## Orden de lectura

| Doc | Contenido |
|---|---|
| [00-alcance-decisiones.md](00-alcance-decisiones.md) | Alcance contractual, ventanas temáticas, ADRs (decisiones de arquitectura y de producto) |
| [01-modelo-datos.md](01-modelo-datos.md) | Apps y modelos Django, campos futuros `[+]`, índices, diagrama ER, datasets Excel canónicos |
| [02-api.md](02-api.md) | Contrato de endpoints DRF con ejemplos de payload |
| [03-admin-editorial.md](03-admin-editorial.md) | Admin Unfold, roles, flujo editorial + correos, importadores, Gemini |
| [04-busqueda.md](04-busqueda.md) | Índices Meilisearch, sincronización, llaves |
| [05-mapas-tiles.md](05-mapas-tiles.md) | Pipeline Tippecanoe/PMTiles con recorte a Cusco, capa CCPP, migración a MapLibre |
| [06-frontend.md](06-frontend.md) | Migración prototype→frontend, rutas nuevas, lib/api.ts, estados vacíos |
| [07-despliegue-ops.md](07-despliegue-ops.md) | compose.yaml, nginx + gunicorn, los dos dominios, .env, HTTPS, backups, runbook, capacitación |
| [08-plan-pruebas.md](08-plan-pruebas.md) | Qué se prueba y con qué; casos obligatorios derivados de la auditoría de datos; criterio de entrega |

## Archivo histórico

`archive/` contiene los specs de la fase de prototipo (visión, UX, datos mock, arquitectura preliminar, roadmap). Siguen siendo válidos como referencia de **visión de producto** (`archive/00-vision.md`) y **UX/paleta/componentes** (`archive/02-navegacion-ux.md`); todo lo relativo a stack estático, mocks y hosting Vercel está superado por estos specs.
