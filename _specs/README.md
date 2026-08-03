# Specs — Observatorio Kallpachakuy (fase de construcción)

Especificaciones técnicas de la plataforma real, sucesora del prototipo aprobado (`prototype/`, congelado como referencia). Contrato N°0362026/PREDES; plataforma en línea el **13/08/2026**.

## Estado

- Fase 0 (prototipo estático) **completada y aprobada** por PREDES.
- Fase actual: construcción de `frontend/` (Vite + React + TS + MapLibre) y `backend/` (Django 5.2 LTS + PostgreSQL + Meilisearch + PMTiles), desplegados con Docker Compose.

### Actualización 02/08/2026 — auditoría de los Excel y prueba del pipeline de tiles

Los specs se escribieron contra una versión anterior de los datos. Al auditar los archivos reales de `data/layers/` se corrigieron 00, 01, 02, 03, 05 y 06. Lo que cambió de fondo:

- El Excel de niveles fue actualizado por el cliente: **10,978 clasificaciones**, no ~6,566. Solo 3,238 de 8,968 CCPP tienen dato.
- El nombre del peligro está en la columna `PELIGRO`, **no en el título de la hoja** (dos discrepancias).
- `subtipo` sale de `ClasificacionPeligro` y pasa a `TipoPeligro.categoria_geo` (era funcionalmente dependiente del peligro).
- Nuevo **ADR-D1** y modelo `TotalDeclaradoEmergencias`: el distrito de Cusco declara 134 emergencias sin desglose.
- **`glaciares.geojson` está en EPSG:32718**, no en lat/lon — sin reproyectar, los tiles salen vacíos.
- El filtro de lagunas debe ser case-insensitive (`ILIKE`), o pierde 73 polígonos.

El pipeline del spec 05 se validó de punta a punta en el prototipo (`prototype/scripts/build_tiles.sh` + ruta `/peligros/mapa-nuevo`, solo en desarrollo). Los `.pmtiles` no se versionan.

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
| [07-despliegue-ops.md](07-despliegue-ops.md) | compose.yml, .env, HTTPS, backups, runbook, capacitación |

## Archivo histórico

`archive/` contiene los specs de la fase de prototipo (visión, UX, datos mock, arquitectura preliminar, roadmap). Siguen siendo válidos como referencia de **visión de producto** (`archive/00-vision.md`) y **UX/paleta/componentes** (`archive/02-navegacion-ux.md`); todo lo relativo a stack estático, mocks y hosting Vercel está superado por estos specs.
