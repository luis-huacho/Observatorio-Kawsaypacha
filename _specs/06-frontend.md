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
- **`TIPOS_PELIGRO` pasa a derivarse de `PELIGROS` (nombre + slug).** La constante del prototipo listaba nombres que no existían en los datos (`"Incendios Forestales"` con F mayúscula), de modo que ese filtro devolvía cero resultados. El slug sigue siendo la clave de las propiedades `nivel_<slug>` del tile CCPP, así que catálogo y tiles tienen que salir de la misma lista — aunque el visor ya no consuma ese tile (ADR-A13): el filtro de peligro compara contra el **nombre** de la clasificación, y ahí el desajuste de mayúsculas era el que rompía.
- **"Distribución" cuenta centros poblados, no clasificaciones.** `peligros` está en formato largo (una fila por CCPP × peligro), así que agregar sobre él da 10,978 registros donde la tabla lista 3,238 centros poblados — en ACOMAYO eso mostraba 225 arriba y 75 abajo. El panel agrega sobre el **nivel máximo por CCPP**, la misma unidad que la tabla, y rotula la unidad y el total en pantalla. Efecto colateral: así el umbral de "nivel mínimo" se lee bien, porque que los niveles bajo el umbral queden en cero describe los datos en lugar de ser un artefacto de filtrar registros sueltos antes de agregar. Al portar a la API, **cualquier endpoint de resumen tiene que declarar cuál de las dos unidades devuelve**.
- **El mapa cuenta en la otra unidad, y la pantalla las reconcilia.** Desde ADR-A16 el número del círculo agrupado son **clasificaciones** (el nivel máximo por CCPP se quedó con el color, no con el número), así que las dos unidades conviven en la misma vista. La cabecera de la tabla las muestra juntas y rotuladas —`N CCPP · M peligros clasificados · K sin clasificación`— y `M` es exactamente lo que se obtiene sumando los círculos: sale de `por_peligro` del resumen, que responde a los mismos filtros que el GeoJSON del visor. Sin esa cifra en pantalla, el número del mapa no cuadra con nada y se lee como si contara pueblos. Salvedad: `/ccpp/geojson/` excluye los centros poblados sin coordenadas y el resumen no, de modo que `M` puede superar a la suma de los círculos si la fuente trae alguno sin ubicar.
- Eliminar: `public/data/*.json` (todos), convención `_mock`, componente `MockBadge`.

## Rutas

| Ruta | Cambio |
|---|---|
| `/` Home | Hero desde `/api/sitio/` (slides administrables); cifras desde `/api/peligros/resumen/`; casos destacados desde `/api/medidas/?destacada`. **Bloque de actualidad a dos columnas** ya construido en el prototipo: últimas 3 noticias (`/api/noticias/?destacada=1`) y últimas 3 normas (`/api/normativa/`), cada una con enlace a su listado |
| `/peligros` | **Ya migrada en el prototipo**: visor MapLibre con CCPP agrupados en fuente GeoJSON y capas de contexto en PMTiles (spec 05), panel de distribución **por centro poblado**, sección "Frecuencia de emergencias" (`FrecuenciaEmergencias.tsx`), tabla de CCPP paginada de 50 en 50 ordenada por nivel, y **botón de ayuda memoria imprimible** (`ReporteImpresion.tsx`, ver 02). El trabajo en `frontend/` es cambiar el origen de datos: `/api/ccpp/` para la tabla, `/api/peligros/frecuencia/` para las barras, `/api/mapas/capas/` para las capas de contexto, **el GeoJSON de puntos del visor (endpoint sin definir, ver 05)**, apuntar la ayuda memoria al endpoint del backend en vez de imprimir en cliente, y añadir el botón de export Excel |
| `/peligros/:codigo` | `/api/ccpp/{codigo}/` |
| `/medidas`, `/medidas/:slug` | Facetas vía Meili (conteos); detalle vía API. **Ficha ya construida en el prototipo** con la estructura que tendrá en producción: portada, chip de resultado, contenido rico de CKEditor (`ContenidoRico`), galería (`GaleriaMedida`), video (`Video`), enlaces y palabras clave. Listado con portada por peligro y filtro `?tema=` |
| `/inversion` | `/api/inversion/`. Tablero del PP 0068 **por municipalidad** (ADR-D4): selector de ejercicio y provincia, 4 KPIs (PIM, devengado con su % , saldo por ejecutar, peso sobre el presupuesto municipal), barras **PIA → PIM → devengado** —que es la forma de responder «¿se ejecuta lo proyectado?»—, barras por proceso de la GRD, tendencia 2022-2026 y tabla ordenable por los tres rankings de la hoja «Campos» (PIM, % de ejecución, saldo pendiente). Reglas de pintado: un porcentaje `null` se muestra **«—», nunca «0 %»**; el corte parcial se avisa **junto a las cifras**, no al pie; los ejercicios parciales llevan asterisco en la tendencia. Si `disponible:false` → **estado vacío elegante**: "Información en preparación" con `EmptyState`, que es lo que se ve entre una importación y su publicación |
| `/normativa`, `/normativa/:slug` | `/api/normativa/` + export Excel. **La ficha es nueva** (`NormaDetalle.tsx`, ya construida en el prototipo). El acceso a la publicación oficial está en **los dos** sitios vía `EnlaceNorma.tsx`, que resuelve las tres variantes: PDF (descarga), página del portal (enlace externo) y sin enlace registrado. Por eso la tarjeta del listado **no** es un `<Link>` envolvente —tiene dos destinos y anidar anclas es HTML inválido—: enlaza el título y deja el de la norma como hermano. **Los `url_oficial` del prototipo son de ejemplo**; al portar, vienen del dato que carga el editor |
| `/recursos` | `/api/biblioteca/` (deja de ser estático) |
| `/noticias`, `/noticias/:slug` | **Ya construidas en el prototipo** (`Noticias.tsx`, `NoticiaDetalle.tsx`): listado con filtro por tipo y detalle. Portar cambiando el JSON por `/api/noticias/`. **No va en el menú principal** por decisión del dueño del proyecto: se llega desde el bloque de actualidad de la portada y desde la columna "Más" del pie |
| `/videos` | **NUEVA** — grilla con embeds YouTube/Vimeo |
| `/eventos` | **NUEVA** — calendario público (vista mes + lista; `desde/hasta`) |
| `/comparar` | **NUEVA** — tablero comparativo: selector de 2–4 distritos → `/api/comparador/distritos/` → tarjetas lado a lado (población, semáforo por peligro, frecuencia, inversión si hay, medidas). **Fuera del menú (ADR-P2)**: la ruta sigue registrada y responde por URL directa, pero no se anuncia ni en el header ni en el pie — a diferencia de `/prioridades`, que no tiene ruta |
| `/buscar` | Multi-search federado Meili, agrupado por tipo |
| `/sobre` | Texto desde bloques `sobre.*` de `/api/sitio/` |
| `/prioridades` | **RUTA NO REGISTRADA** (decisión de reunión). `Prioridades.tsx` se conserva en el código |
| `*` NotFound | igual |

## Layout y textos administrables

- `Layout.tsx` pide `/api/sitio/` una vez (contexto React `SitioContext`); `Header`/`Footer` renderizan menú (`EnlaceMenu`) y textos desde ahí — se eliminan los arrays hardcodeados (`NAV` en `Header.tsx`, fuentes en `Footer.tsx`).
- Mientras carga: skeleton con los textos por defecto actuales (fallback estático para no parpadear). Ese respaldo **es el menú en modo degradado**, así que lo que se oculte en `EnlaceMenu` hay que quitarlo también de ahí o reaparece en cada carga y cuando el API no responde.
- **Las cajas de búsqueda pasan por `CajaBusqueda.tsx`**, que es donde vive su comportamiento: la
  «X» de limpiar aparece solo cuando hay texto, es `type="button"` —dos de las cajas están dentro de
  un `<form>` y sin eso lo enviarían—, devuelve el foco al campo y `Escape` hace lo mismo. Cubre
  `/buscar`, el filtro de `/recursos` y las dos cajas de la cabecera; su prop `tono` solo cambia el
  aspecto. La quinta caja, el buscador de centros poblados del visor, es un control de MapLibre
  hecho a mano y lleva su equivalente imperativo en `MapaControles.ts`, donde la «X» **no quita el
  marcador**: vacía el campo para escribir otra cosa.
  Regla de producto: **en `/buscar` la «X» no toca la URL**. El término vive en `?q=` y los
  resultados anteriores se quedan en pantalla hasta que se envíe la nueva búsqueda — es «borrar para
  escribir», no «cancelar la búsqueda». En `/recursos` el filtro es en vivo y por eso ahí sí amplía
  el listado al instante.
- **El menú de escritorio va en una sola línea** (desde `lg`). La barra tiene altura fija, así que un enlace que parte su texto en dos se sale por arriba y por abajo: los enlaces llevan `whitespace-nowrap`, logo y `nav` van con `shrink-0`, y el que cede espacio cuando falta es el buscador (`min-w-0` en el `form` y en el `input`, `w-40` hasta `xl` y `w-56` desde ahí). Medido a 1024, 1280 y 1440 px en `e2e/header.spec.ts`.
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

`npm run build` (tsc + vite) → `dist/` copiado al volumen `web_dist` que sirve nginx en `observatorio.predes.org.pe` (spec 07). `npm run lint` = `tsc --noEmit`.
