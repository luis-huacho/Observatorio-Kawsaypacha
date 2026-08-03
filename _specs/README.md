# Specs — Observatorio Kallpachakuy (fase de construcción)

Especificaciones técnicas de la plataforma real, sucesora del prototipo aprobado (`prototype/`, congelado como referencia). Contrato N°0362026/PREDES; plataforma en línea el **13/08/2026**.

## Estado

- Fase 0 (prototipo estático) **completada y aprobada** por PREDES.
- Fase actual: construcción de `frontend/` (Vite + React + TS + MapLibre) y `backend/` (Django 5.2 LTS + PostgreSQL + Meilisearch + PMTiles), desplegados con Docker Compose.

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
- **ADR-A13**: dos dominios — `observatorio.predes.org.pe` (SPA) y `obs.predes.org.pe` (API, admin, media, tiles, search), con CORS entre ambos. 07 reescrito en consecuencia.
- **ADR-D3**: la ventana Inversión se difiere; solo se entrega la ruta con su estado vacío.
- Se cierran los dos pendientes que los specs arrastraban: **`GET /api/ccpp/geojson/`** queda definido en 02 (FeatureCollection completo con los mismos filtros que la tabla), y el **mapa de la ayuda memoria se renderiza en servidor** con navegador headless.
- Nuevo **08-plan-pruebas.md**. Se evaluó añadir `data-model.md`, `infra.md`, `prod.md`, `tech.md` y `ui.md`: los cinco ya están cubiertos por 01, 07, 00 y 06, y duplicarlos solo garantiza que se desincronicen.
- `frontend/` se recreó desde `prototype/`: la copia anterior era previa a la migración a MapLibre.

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
