# Observatorio Kallpachakuy — Guía del proyecto

Plataforma web pública de monitoreo de GRD y ACC en la región Cusco, para PREDES (contrato N°0362026/PREDES; plataforma en línea el 13/08/2026). El prototipo aprobado vive en `prototype/` y está **congelado como referencia**; el trabajo activo está en `frontend/` y `backend/`.

## Arquitectura

- `frontend/` — Vite + React 18 + TS + Tailwind 3 + react-router 6 + MapLibre GL. Consume el API vía `src/lib/api.ts` (`VITE_API_URL`).
- `backend/` — Django 5.2 LTS + DRF + PostgreSQL 16 (sin PostGIS) + django-tasks (worker por BD, sin Redis) + admin con django-unfold. Apps en `backend/apps/`.
- `e2e/` — pruebas de extremo a extremo con Playwright; `deploy/nginx/` — configuración de nginx (`conf.d/` producción, `local/` prueba local sobre HTTP).
- Meilisearch: búsqueda y facetas (llave search-only para el frontend; master key solo en backend).
- Mapas, **son dos cosas distintas**:
  - Capas de contexto (ríos, lagunas, glaciares): GeoJSON → recorte a Cusco → Tippecanoe → `.pmtiles` estáticos en `media/tiles/`, servidos con HTTP Range.
  - Capa de centros poblados del visor: **fuente `geojson` agrupada** servida por `GET /api/ccpp/geojson/` (ADR-A13). MapLibre solo agrupa fuentes `geojson`, así que el clustering obliga a salirse del tile. `generar_tiles_ccpp` sigue existiendo, pero **el visor no lo consume**.
- Gemini 2.5 Flash: autocompleta resúmenes de PDF en el admin (humano siempre revisa antes de publicar).
- Orquestación: `compose.yaml` es la base (= producción **con contenedor de base de datos**), con dos overrides — `compose.dev.yml` (desarrollo) y `compose.local.yml` (modo producción en local, sobre HTTP).
- **Hay dos vías de producción, y las dos están documentadas**: con Docker Compose (recomendada, `_docs/despliegue.md`) y **sin Docker con base de datos gestionada** (`_docs/despliegue-sin-docker.md`, gunicorn y Meilisearch bajo systemd). Los archivos de compose y de nginx sirven a la primera; la segunda no necesita cambios de código, solo variables de entorno.
- Edge: **nginx + certbot** en contenedor (ADR-A6bis, sustituyó a Caddy), sobre **dos dominios** (ADR-A14): la SPA en `observatorio.predes.org.pe`, y API/admin/media/tiles/search en `obs.predes.org.pe`, con CORS entre ambos.
- Secretos en **tres** `.env`, nunca commiteados (los `.env.example` sí se versionan): `backend/.env` (secretos de Django, lo lee `read_env()` y también los contenedores por `env_file`), `frontend/.env` (URLs para `npm run dev`) y **`.env` en la raíz**, que es el que interpola Docker Compose con las `VITE_*` del build.

## Specs — leer antes de implementar cada área

`_specs/` es la fuente de verdad (los specs de la fase prototipo están en `_specs/archive/`, solo histórico):

- `00-alcance-decisiones.md` — alcance contractual y ADRs (incluye por qué Prioridades está desactivada)
- `01-modelo-datos.md` — modelos Django, índices, campos futuros [+]
- `02-api.md` — contrato de endpoints y payloads
- `03-admin-editorial.md` — Unfold, roles, flujo editorial, importadores, Gemini
- `04-busqueda.md` — índices Meilisearch y sincronización
- `05-mapas-tiles.md` — pipeline de tiles, capa CCPP agrupada, gotchas de MapLibre
- `06-frontend.md` — rutas, api.ts, estados vacíos
- `07-despliegue-ops.md` — compose, nginx, los dos dominios, HTTPS, backups, runbook
- `08-plan-pruebas.md` — qué se prueba y con qué; criterio de entrega, y los seis fallos silenciosos que la suite encontró

`_docs/` contiene la documentación técnica versionada (`arquitectura`, `desarrollo`, `despliegue`, `despliegue-sin-docker`, `api`, `manual-admin-predes`) más documentos para la dirección que no se versionan. Sirve para operar; **para implementar manda `_specs/`**. Ojo al añadir un documento: `.gitignore` ignora `/_docs/*` y hay que negar el archivo nuevo explícitamente.

## Comandos

- Dev completo: `docker compose -f compose.yaml -f compose.dev.yml up -d --build`, y luego `cd frontend && npm run dev` en el host (Node 22)
- Siembra: `seed` (+ `--demo`, `--capas`, `--tiles`, `--solo-catalogos`). Es idempotente y no pisa lo editado
- Backend: `manage.py migrate | createsuperuser | check`; Meilisearch: `meili_setup` (crea índices/llaves), `meili_rebuild`; tiles: `generar_tiles_ccpp`, `generar_tiles`
- Frontend: `npm run dev | build | lint` (lint = `tsc --noEmit`)
- Pruebas: `pytest` **dentro del contenedor** (`-m lento` para las 4 caras) y `npx playwright test` desde la raíz. La corrida que encuentra los fallos de integración es la de `compose.local.yml` con `E2E_URL=http://localhost` — ver `_docs/desarrollo.md`

## Convenciones

- Español en modelos, admin y UI (dominio GRD peruano: ubigeo, CCPP, PIM/PIA/devengado…).
- Los tipos TS de `frontend/src/lib/types.ts` son espejo de los serializers de `backend/apps/api/` — cambiar ambos juntos.
- **Todo dato pasa por `frontend/src/lib/api.ts`**, que es el único punto de integración. `useJsonData` ya no existe: si una página necesita datos nuevos se le añade un endpoint, no un `fetch` suelto.
- **Las dos unidades de la distribución no son intercambiables**: "centros poblados por su nivel máximo" (3,238) y "clasificaciones" (10,978) difieren en 3.4×, porque un CCPP aporta una fila por peligro evaluado. Cualquier cifra que se muestre tiene que declarar cuál es.
- **El slug del peligro lleva guion bajo** (`lluvias_intensas`). Es la clave de las propiedades `nivel_<slug>` de los tiles: con guion medio el visor deja de pintar y nada más falla.
- **El HTML rico se sanea en `save()` del modelo** (`HtmlRicoMixin.campos_html`), no en el admin. Al añadir un campo de CKEditor hay que declararlo ahí; `campos_rich` del admin solo elige el widget.
- **`pytest` vive en la imagen `predes-observatorio-backend-dev`** (`compose.dev.yml` la construye con `GRUPOS_UV=--group dev`). Si responde `executable file not found`, hace falta `up -d --build --renew-anon-volumes backend worker`: `/app/.venv` es un volumen anónimo que sobrevive a la reconstrucción y se queda con el venv viejo.
- **Con una variable en `proxy_pass`, nginx deja de sustituir el prefijo de la `location`**: el prefijo se quita con `rewrite`. Es lo que dejó el buscador cayendo al fallback de DRF, y la comprobación fácil no lo veía porque `GET /search/health` devuelve 200 igual (la raíz de Meilisearch también responde 200). Se comprueba con `POST /search/multi-search`.
- Contenido editorial siempre pasa por `WorkflowMixin` (borrador → revisión → publicado); nunca publicar directo ni saltarse las notificaciones.
- Importación de datos SOLO vía `DatasetUpload` (validación + reemplazo atómico); no escribir imports ad-hoc.
- Mantener la paleta/design tokens del prototipo (`tailwind.config.ts`: mountain/earth/sky/level-1..4).
- **Las imágenes del editor pasan por `apps.core.almacenamiento.AlmacenamientoContenido`**: las guarda en `contenido/%Y/%m/` y las reduce a `CONTENIDO_ANCHO_MAXIMO_PX`. Hace falta porque `django-ckeditor-5` **ignora `CKEDITOR_5_UPLOAD_PATH`** y su único gancho es `CKEDITOR_5_FILE_STORAGE`. Ojo: `Storage.save` **no** llama a `generate_filename` —solo lo hace la ruta de los campos de modelo—, así que el prefijo se aplica en `save`. Solo afecta al editor; los `ImageField` siguen con su `upload_to`.
- **Lo que se monte bajo `ADMIN_URL` va ANTES de `admin.site.urls`** en `config/urls.py`. `AdminSite` termina sus URLs con un `catch_all_view` que casa con cualquier cosa bajo su prefijo y responde 404, así que una ruta declarada después **nunca se alcanza**. La subida de imágenes de CKEditor estuvo detrás y daba 404 sin que nada lo dijera.
- **El desfase del índice de búsqueda es silencioso.** Se comprueba con `manage.py meili_estado` o en la tarjeta «Buscador» del panel del admin, y **el conteo no se toma de `numberOfDocuments` de `/stats`** —está cacheado y sigue devolviendo el valor anterior tras vaciar un índice—: se usa `get_documents({"limit": 0}).total`.
- **La llave de búsqueda es un artefacto de *build*.** `VITE_MEILI_SEARCH_KEY` va horneada en el bundle, y vive en **dos** `.env`: `frontend/.env` (para `npm run dev`) y el de la raíz (para el bundle que sirve nginx). Cambiarla exige **reconstruir** el frontend, no reiniciarlo. La llave en sí es determinista (uid fijo + `MEILI_MASTER_KEY`), así que ya no cambia al recrear el volumen de Meilisearch. Si Meilisearch la rechaza, se degradan tres cosas —búsqueda, conteos de las facetas de `/medidas` y autocompletado de lugares— y **solo la primera avisa en pantalla**.
- **El menú vive en tres sitios y hay que tocar los tres**: la semilla (`apps/sitio/semillas/sitio.yaml`), la base ya sembrada —el seed crea lo que falta y **no pisa lo que existe**, así que un cambio de visibilidad necesita migración de datos— y el **menú de respaldo** de `frontend/src/lib/sitio.tsx`, que es el que se pinta mientras carga `/api/sitio/` y en modo degradado.
- **El menú superior va en una sola línea en escritorio** (`Header.tsx`): enlaces con `whitespace-nowrap`, logo y `nav` con `shrink-0`, y el buscador como el que cede espacio (`min-w-0`). Se mide en `e2e/header.spec.ts`; hay que volver a medirlo si se añade una entrada al menú.
- "Prioridades" está desactivada por decisión de reunión (sin datos en el plazo) — no reactivar sin pedido explícito del usuario. "Comparar distritos" está **fuera del menú** (ADR-P2) pero su ruta y su endpoint siguen vivos — tampoco reactivar el enlace sin pedido explícito.
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
