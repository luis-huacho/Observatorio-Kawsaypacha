# 06 — Frontend

`frontend/` nace **copiando `prototype/`** (sin `node_modules/`, `dist/`, `vercel.json`) y migrando la capa de datos. Misma tecnología: Vite 5 + React 18 + TypeScript + Tailwind 3 + react-router 6 + Recharts + lucide.

El salto a MapLibre **ya ocurrió en el prototipo**: Leaflet, `react-leaflet` y `html-to-image` fueron desinstalados y `MapaPeligros.tsx`/`MapaControles.ts` están escritos contra MapLibre + PMTiles. Queda un único cambio de fondo: JSON estáticos → API (spec 02) + Meilisearch (spec 04). `prototype/` sigue siendo la referencia; conviene re-copiarlo antes de empezar, porque el `frontend/` actual es una copia anterior a esta migración.

## Variables de entorno (`frontend/.env`)

```
VITE_API_URL=/api
VITE_SEARCH_URL=/search
VITE_MEILI_SEARCH_KEY=<llave search-only, de manage.py meili_setup>
VITE_TILES_URL=/tiles
```
En dev apuntan a `http://localhost:8000/api` etc. (o proxy de Vite). `.env` no se commitea; `.env.example` sí.

## Capa de datos

- `src/lib/useJsonData.ts` (fetch a `/data/*.json` + cache en Map) evoluciona a **`src/lib/api.ts`**: mismo patrón `useApi<T>(path, params)` con cache, estados `loading/error/data`, base `VITE_API_URL`, serialización de query params y abort on unmount. Es el **único punto de integración** — las páginas cambian la URL, no su lógica.
- `src/lib/search.ts`: cliente fetch de Meilisearch (multi-search, facetas) con fallback a DRF (spec 04).
- `src/lib/types.ts` se conserva y amplía: `Noticia`, `Video`, `Evento`, `Documento`, `FrecuenciaDistrito`, `SitioPayload`, `CapaMapa`, `ComparadorDistrito`, `InversionResponse` (con `disponible`). Tipos espejo de los serializers DRF.
- **Contenido rico de CKEditor**: `ContenidoRico.tsx` inyecta el HTML del editor y hace dos cosas
  sin las cuales no se ve bien:
  - Lo envuelve en `.contenido-rico` (`index.css`), una hoja **escrita a mano y no con
    `@tailwindcss/typography`**. El plugin no conoce las clases propias de CKEditor —`figure.image`,
    `figure.table`, `.image-style-side`, `.text-big`—, que hay que estilar igual, así que añadir la
    dependencia no ahorraría el trabajo. Esa hoja devuelve lo que el Preflight borra (tamaños de
    encabezado, viñetas, márgenes) y **subraya los enlaces**: la regla global del sitio los deja
    solo con color, y en texto corrido el color como único distintivo es un problema de accesibilidad.
  - Sustituye el `<oembed>` por un iframe. Es obligatorio: CKEditor no emite iframes para los
    videos incrustados y el navegador no pinta `<oembed>`. La conversión de URL vive en
    `src/lib/video.ts`, compartida con el `video_url` suelto de la medida.
- **Imagen por defecto**: `src/lib/imagenes.ts` resuelve la portada de noticias y normas contra
  `/img/default/{tipo}.svg` cuando la pieza no trae la suya, y el pie contra un texto genérico que
  la declara ilustración (ver el bloque de imagen por defecto en 01). En `frontend/` la resolución
  se hace en el serializer, así que el helper se reduce a usar lo que devuelve el API; conviene
  conservar el componente `Portada.tsx`, que es donde vive el maquetado de figura + pie.
- **Filtro por palabra clave en la URL**: `/noticias` y `/normativa` leen `?tema=` con
  `useSearchParams` y lo combinan con sus `<select>`. Es el único filtro del prototipo que vive en
  la URL, y necesita el aviso visible de `FiltroTema.tsx`: quien llega desde una ficha ve el
  listado recortado sin ningún control que lo explique.
- **`TIPOS_PELIGRO` pasa a derivarse de `PELIGROS` (nombre + slug).** La constante del prototipo listaba nombres que no existían en los datos (`"Incendios Forestales"` con F mayúscula), de modo que ese filtro devolvía cero resultados. El slug es además la clave de las propiedades `nivel_<slug>` de los tiles, así que catálogo y tiles tienen que salir de la misma lista.
- Eliminar: `public/data/*.json` (todos), convención `_mock`, componente `MockBadge`.

## Rutas

| Ruta | Cambio |
|---|---|
| `/` Home | Hero desde `/api/sitio/` (slides administrables); cifras desde `/api/peligros/resumen/`; casos destacados desde `/api/medidas/?destacada`. **Bloque de actualidad a dos columnas** ya construido en el prototipo: últimas 3 noticias (`/api/noticias/?destacada=1`) y últimas 3 normas (`/api/normativa/`), cada una con enlace a su listado |
| `/peligros` | **Ya migrada en el prototipo**: visor MapLibre + PMTiles (spec 05), panel de distribución, sección "Frecuencia de emergencias" (`FrecuenciaEmergencias.tsx`), tabla de CCPP paginada de 50 en 50 ordenada por nivel, y **botón de ayuda memoria imprimible** (`ReporteImpresion.tsx`, ver 02). El trabajo en `frontend/` es cambiar el origen de datos: `/api/ccpp/` para la tabla, `/api/peligros/frecuencia/` para las barras, `/api/mapas/capas/` para las capas de contexto, apuntar la ayuda memoria al endpoint del backend en vez de imprimir en cliente, y añadir el botón de export Excel |
| `/peligros/:codigo` | `/api/ccpp/{codigo}/` |
| `/medidas`, `/medidas/:slug` | Facetas vía Meili (conteos); detalle vía API. **Ficha ya construida en el prototipo** con la estructura que tendrá en producción: portada, chip de resultado, contenido rico de CKEditor (`ContenidoRico`), galería (`GaleriaMedida`), video (`Video`), enlaces y palabras clave. Listado con portada por peligro y filtro `?tema=` |
| `/inversion` | `/api/inversion/`; si `disponible:false` → **estado vacío elegante**: "Información en preparación — PREDES está consolidando los datos de inversión PPR 0068" con `EmptyState` |
| `/normativa`, `/normativa/:slug` | `/api/normativa/` + export Excel. **La ficha es nueva** (`NormaDetalle.tsx`, ya construida en el prototipo). El acceso a la publicación oficial está en **los dos** sitios vía `EnlaceNorma.tsx`, que resuelve las tres variantes: PDF (descarga), página del portal (enlace externo) y sin enlace registrado. Por eso la tarjeta del listado **no** es un `<Link>` envolvente —tiene dos destinos y anidar anclas es HTML inválido—: enlaza el título y deja el de la norma como hermano. **Los `url_oficial` del prototipo son de ejemplo**; al portar, vienen del dato que carga el editor |
| `/recursos` | `/api/biblioteca/` (deja de ser estático) |
| `/noticias`, `/noticias/:slug` | **Ya construidas en el prototipo** (`Noticias.tsx`, `NoticiaDetalle.tsx`): listado con filtro por tipo y detalle. Portar cambiando el JSON por `/api/noticias/`. **No va en el menú principal** por decisión del dueño del proyecto: se llega desde el bloque de actualidad de la portada y desde la columna "Más" del pie |
| `/videos` | **NUEVA** — grilla con embeds YouTube/Vimeo |
| `/eventos` | **NUEVA** — calendario público (vista mes + lista; `desde/hasta`) |
| `/comparar` | **NUEVA** — tablero comparativo: selector de 2–4 distritos → `/api/comparador/distritos/` → tarjetas lado a lado (población, semáforo por peligro, frecuencia, inversión si hay, medidas) |
| `/buscar` | Multi-search federado Meili, agrupado por tipo |
| `/sobre` | Texto desde bloques `sobre.*` de `/api/sitio/` |
| `/prioridades` | **RUTA NO REGISTRADA** (decisión de reunión). `Prioridades.tsx` se conserva en el código |
| `*` NotFound | igual |

## Layout y textos administrables

- `Layout.tsx` pide `/api/sitio/` una vez (contexto React `SitioContext`); `Header`/`Footer` renderizan menú (`EnlaceMenu`) y textos desde ahí — se eliminan los arrays hardcodeados (`NAV` en `Header.tsx`, fuentes en `Footer.tsx`).
- Mientras carga: skeleton con los textos por defecto actuales (fallback estático para no parpadear).
- Hero de portada: carrusel/slide único según nº de `HeroSlide` publicados.

## Métricas (beacon)

Hook `useMetrica()`: pageview en cada cambio de ruta (`navigator.sendBeacon` a `/api/metricas/evento/`), y eventos en descargas (PDF, Excel, documento) y búsquedas. Sin cookies, sin PII.

La ayuda memoria de `/peligros` debe emitir `descarga_pdf` con el ubigeo en `detalle`; el tipo ya está en `EventoUso` (`01-modelo-datos.md`). Es la métrica que dice a PREDES qué distritos se están llevando a mesas técnicas, así que conviene no olvidarla al portar el botón.

## UI/estilo

- Paleta, tipografía (Metropolis self-hosted, JetBrains Mono) y componentes (`SemaforoChip`, `SourceLink`, `GeoSelector`, `EmptyState`, `PageHeader`, `Reveal`) se mantienen tal cual del prototipo (`archive/02-navegacion-ux.md` sigue vigente para UX).
- `GeoSelector` puede seguir con selects dependientes (`/api/territorio/*`); el autocompletado Meili es para el buscador del mapa.
- `DownloadButton` deja de estar disabled: apunta a los exports reales.
- Accesibilidad y responsive: criterios del spec archivado se mantienen.

## Build

`npm run build` (tsc + vite) → `dist/` copiado al volumen `web_dist` que sirve Caddy (spec 07). `npm run lint` = `tsc --noEmit`.
