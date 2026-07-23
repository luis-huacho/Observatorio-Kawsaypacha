# Observatorio Kallpachakuy — Guía del proyecto

Plataforma web pública de monitoreo de GRD y ACC en la región Cusco, para PREDES (contrato N°0362026/PREDES; plataforma en línea el 13/08/2026). El prototipo aprobado vive en `prototype/` y está **congelado como referencia**; el trabajo activo está en `frontend/` y `backend/`.

## Arquitectura

- `frontend/` — Vite + React 18 + TS + Tailwind 3 + react-router 6; mapa en migración Leaflet → MapLibre GL + PMTiles. Consume el API vía `src/lib/api.ts` (`VITE_API_URL`).
- `backend/` — Django 5.2 LTS + DRF + PostgreSQL 16 (sin PostGIS) + django-tasks (worker por BD, sin Redis) + admin con django-unfold. Apps en `backend/apps/`.
- Meilisearch: búsqueda y facetas (llave search-only para el frontend; master key solo en backend).
- Tiles: GeoJSON → recorte a Cusco → Tippecanoe → `.pmtiles` estáticos en `media/tiles/` (servidos con HTTP Range por Caddy). La capa de CCPP se regenera desde la BD (`generar_tiles_ccpp`).
- Gemini 2.5 Flash: autocompleta resúmenes de PDF en el admin (humano siempre revisa antes de publicar).
- Orquestación: `compose.yml` (+ `compose.dev.yml` para desarrollo). Caddy es el único punto de entrada (SPA, /api, /admin, /search, /media, /tiles).
- Secretos SIEMPRE en `.env` en la raíz de `frontend/` y `backend/` — nunca commitear (los `.env.example` sí se versionan).

## Specs — leer antes de implementar cada área

`_specs/` es la fuente de verdad (los specs de la fase prototipo están en `_specs/archive/`, solo histórico):

- `00-alcance-decisiones.md` — alcance contractual y ADRs (incluye por qué Prioridades está desactivada)
- `01-modelo-datos.md` — modelos Django, índices, campos futuros [+]
- `02-api.md` — contrato de endpoints y payloads
- `03-admin-editorial.md` — Unfold, roles, flujo editorial, importadores, Gemini
- `04-busqueda.md` — índices Meilisearch y sincronización
- `05-mapas-tiles.md` — pipeline de tiles y migración a MapLibre
- `06-frontend.md` — rutas, api.ts, estados vacíos
- `07-despliegue-ops.md` — compose, HTTPS, backups, runbook

`_docs/` contiene documentos para la dirección y entregables contractuales (no técnicos): no usarlos como spec.

## Comandos

- Dev completo: `docker compose -f compose.yml -f compose.dev.yml up`
- Backend: `uv run manage.py migrate | createsuperuser | check`; Meilisearch: `meili_setup` (crea índices/llaves), `meili_rebuild`; tiles: `generar_tiles_ccpp`
- Frontend: `npm run dev | build | lint` (lint = `tsc --noEmit`)

## Convenciones

- Español en modelos, admin y UI (dominio GRD peruano: ubigeo, CCPP, PIM/PIA/devengado…).
- Los tipos TS de `frontend/src/lib/types.ts` son espejo de los serializers de `backend/apps/api/` — cambiar ambos juntos.
- Contenido editorial siempre pasa por `WorkflowMixin` (borrador → revisión → publicado); nunca publicar directo ni saltarse las notificaciones.
- Importación de datos SOLO vía `DatasetUpload` (validación + reemplazo atómico); no escribir imports ad-hoc.
- Mantener la paleta/design tokens del prototipo (`tailwind.config.ts`: mountain/earth/sky/level-1..4).
- "Prioridades" está desactivada por decisión de reunión (sin datos en el plazo) — no reactivar sin pedido explícito del usuario.
- La data de Inversión aún no ha sido entregada por el cliente: el módulo debe tolerar estado "sin datos".

# Directivas del Agente

Reglas de comportamiento que debo seguir al asistir con generación y refactor de código en este proyecto.

## Decisión y comunicación

- Pedir aclaración cuando falte contexto; no asumir detalles críticos.
- Avisar de inmediato si las instrucciones se contradicen o no tienen sentido arquitectónico.
- Exponer pros y contras antes de implementar soluciones complejas.
- Cuestionar de forma constructiva los enfoques ineficientes; no adular.
- Esbozar un plan corto antes de escribir bloques grandes de código.

## Estándares de código

- Preferir la solución más simple y legible; evitar sobreingeniería.
- Eliminar código muerto y restos de refactors anteriores.
- No modificar código ni comentarios fuera del alcance de la tarea actual.

## Workflow y ejecución

- Iterar y depurar hasta agotar opciones lógicas antes de detenerse.
- TDD: para nuevas funcionalidades, escribir primero las pruebas y trabajar hasta que pasen.
- Optimización en dos fases: primero una versión correcta aunque ingenua, luego optimizar manteniendo las pruebas.
- Operar por criterios de éxito declarativos, iterando hasta cumplir la meta final.
