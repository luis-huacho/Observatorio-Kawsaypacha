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
- **Los "Resultados" cuentan centros poblados, no clasificaciones.** `peligros` está en formato largo (una fila por CCPP × peligro), así que agregar sobre él da 10,978 registros donde la tabla lista 3,238 centros poblados — en ACOMAYO eso mostraba 225 arriba y 75 abajo. **Cualquier endpoint de resumen tiene que declarar cuál de las dos unidades devuelve**.
- **La grilla de resultados desactiva la ambigüedad por construcción (ADR-A17).** Cada fila es un tipo de peligro, y ahí las dos unidades **son la misma cifra**: la constraint `unica_clasificacion_ccpp_peligro` impide que un centro poblado tenga dos filas del mismo peligro. La ambigüedad de 3.4× solo aparece al sumar la **columna**, así que el pie declara las dos y no hay total de columna a secas. El API publica la cifra ya nombrada en `por_peligro[].centros_poblados` para que el cliente no tenga que deducir por qué coincide con la suma de `niveles`.
- **Los resultados van FUERA del panel de filtros.** Estuvieron dentro del `<aside>`, bajo los controles, y ahí se leían como una leyenda del mapa en vez de como la respuesta a la consulta que el usuario acababa de hacer.
- **El mapa cuenta en la otra unidad, y la pantalla las reconcilia.** Desde ADR-A16 el número del círculo agrupado son **clasificaciones** (el nivel máximo por CCPP se quedó con el color, no con el número), así que las dos unidades conviven en la misma vista. El pie de la grilla de resultados las muestra juntas y rotuladas —`N CCPP · M peligros clasificados · K sin clasificación`— y `M` es exactamente lo que se obtiene sumando los círculos: sale de `por_peligro` del resumen, que responde a los mismos filtros que el GeoJSON del visor. Sin esa cifra en pantalla, el número del mapa no cuadra con nada y se lee como si contara pueblos. Salvedad: `/ccpp/geojson/` excluye los centros poblados sin coordenadas y el resumen no, de modo que `M` puede superar a la suma de los círculos si la fuente trae alguno sin ubicar.
- Eliminar: `public/data/*.json` (todos), convención `_mock`, componente `MockBadge`.

## Rutas

| Ruta | Cambio |
|---|---|
| `/` Home | Hero desde `/api/sitio/` (slides administrables); cifras de la banda: distritos (`/api/territorio/distritos/`), CCPP en nivel alto/muy alto (`/api/peligros/resumen/`), la tarjeta de Medidas (**`count` de `/api/medidas/` sin filtro de resultado**: el total publicado, que es lo que lista `/medidas`) y municipios con devengado (`/api/inversion/`, «…» si `disponible:false`); casos destacados desde `/api/medidas/?destacada`. **Bloque de actualidad a dos columnas** ya construido en el prototipo: últimas 3 noticias (`/api/noticias/?page_size=3`: el orden del API ya pone delante las destacadas, así que no hace falta filtrar) y últimas 3 normas (`/api/normativa/`), cada una con enlace a su listado |
| `/peligros` | **Solo exposición** (ADR-A17). Visor MapLibre con CCPP agrupados en fuente GeoJSON y capas de contexto en PMTiles (spec 05). Panel de filtros con **Ubicación → Tipo de peligro → Nivel de peligro**, los dos últimos como **checklist de selección múltiple** (`ChecklistFiltro.tsx`): varios peligros a la vez, y niveles sueltos con su nombre —Muy alto, Alto, Medio, Bajo— en vez del umbral «nivel mínimo». Desmarcar todo significa **ninguno**, y la página muestra su estado vacío sin llegar a pedir. Fuera del `<aside>` y sobre el mapa va la grilla de **Resultados** (`ResultadosExposicion.tsx`): una fila por tipo con su ícono, la cantidad de centros poblados, la barra por nivel y «Ver centros poblados», que deja marcado solo ese peligro y lleva el foco a la relación. Debajo, el mapa; y al final la tabla `Distrito · Centro poblado · Peligros`, paginada de **20 en 20** con «Ver más», **sin columna de población ni de nivel**: los peligros se listan **todos**, cada uno con su ícono y el color de **su** nivel, y una leyenda encima descifra el color. Hay además un botón **«Reiniciar»** que recarga la ruta limpia — el estado vive en `useState`, no en la URL, así que recargar es el reset completo. El catálogo de peligros —incluido el `icono`— sale de `/api/peligros/tipos/`, no de la constante `PELIGROS` de `types.ts`. Un cuarto bloque, **Emergencias** (ADR-A18), con dos casillas: *Ver las emergencias* —enciende la capa del visor y el gráfico— y *Agrupar por tipo de evento*, que alterna las barras entre los 21 eventos y las 4 familias. El gráfico va **bajo el visor**, lo titula la provincia y **solo la provincia lo actualiza**: ni el distrito ni los checklists de peligro/nivel lo mueven, que es lo que hace evidente que son ejes distintos. Marcar o desmarcar esas casillas **no toca la provincia ni el distrito** elegidos |
| `/peligros/:codigo` | Ficha del centro poblado. **Sin población** (ADR-A19) y **sin la columna «Tipo / Detalle»**, que renderizaba un campo que el API había dejado de enviar y mostraba «—» en las 3,238 fichas. Lleva un **mapa mínimo** (`MapaPunto.tsx`, diferido) que sitúa el punto con la misma corona de íconos del visor: no es `MapaPeligros` reutilizado —arrastraría clustering, buscador y leyenda— ni una imagen renderizada en servidor, que sería más costosa. La geometría compartida vive en `lib/iconosPeligro.ts` |
| `/peligros/:codigo` | `/api/ccpp/{codigo}/` |
| `/medidas`, `/medidas/:slug` | Facetas vía Meili (conteos); detalle vía API. **Ficha ya construida en el prototipo** con la estructura que tendrá en producción: portada, chip de resultado, contenido rico de CKEditor (`ContenidoRico`), galería (`GaleriaMedida`), video (`Video`), enlaces y palabras clave. Listado con portada por peligro y filtro `?tema=` |
| `/inversion` | `/api/inversion/`. Tablero del PP 0068 **por municipalidad** (ADR-D4): selector de ejercicio y provincia, 4 KPIs (PIM del 0068, devengado con su % , saldo por ejecutar, y **presupuesto institucional total** con el peso del 0068 sobre él como subtítulo — la lista de indicadores del cliente pide el total, no solo el ratio), barras **PIA → PIM → devengado** —que es la forma de responder «¿se ejecuta lo proyectado?»—, barras por proceso de la GRD, **tendencia 2022-2026 con PIA, PIM y devengado más su cuadro** —una fila por ejercicio con variación PIA-PIM, saldo, % de ejecución y fuente; el PIA va punteado en la línea porque es el punto de partida y la distancia hasta el PIM *es* la variación—, **el visor coroplético** (ver abajo) y tabla ordenable por los tres rankings de la hoja «Campos» (PIM, % de ejecución, saldo pendiente), con columna de PIM institucional a partir de `xl`. **Cada gráfico lleva debajo una `Declaracion`**: una frase en tercera persona que dice lo que el gráfico enseña —cuánto subió o bajó, en soles y en porcentaje, o dónde se concentra— porque un gráfico se deja leer pero no concluye, y la ventana la usan autoridades, periodistas y universidades. **Las redacta el backend** (`apps/inversion/declaraciones.py`) y viajan en `declaraciones` del payload: las imprimen la pantalla y el PDF, y redactarlas en el cliente dejaría dos versiones que un día no dirían lo mismo (ADR-D6). El componente `Declaracion` solo las pinta, con el filete de las `.declaracion` del reporte, y **no llevan color de semáforo**: `Delta` colorea porque compara dos ejercicios que alguien eligió, pero aquí más presupuesto no es de suyo una buena noticia. La de la tendencia compara **los dos últimos ejercicios completos** y nombra el corte parcial aparte, sin variación: comparar medio año con un año entero daría una caída que no existe. **«Proyectos de inversión frente a actividades» es sección propia** con su barra, su frase y el cuadro de qué municipalidades tienen obra (`proyectos` del payload): el porcentaje solo se leía como si todas hicieran obra —son 24 de 116— y se atribuía al Gobierno Regional, que **no está en el ámbito municipal**; la frase lo dice. Reglas de pintado: un porcentaje `null` se muestra **«—», nunca «0 %»**; el corte parcial se **identifica** junto a las cifras y se **explica** al pie del cuadro de tendencia, que es donde están los porcentajes que se comparan entre sí; los ejercicios parciales llevan asterisco en la tendencia. **El aviso nombra el ejercicio, no solo advierte de él** —«Ejercicio 2026, año fiscal en curso — corte a junio de 2026»—: la versión anterior solo decía que su % no era comparable «con el de un ejercicio cerrado», y de ahí había que deducir por descarte cuál se estaba mirando. **Y solo lo nombra**: la explicación de por qué un % de medio año no es media ejecución perdida vive en `PIE_EJERCICIO_PARCIAL`, al pie de la tendencia, y en el PDF entera —un documento en papel viaja sin su pantalla—. Tenerla también arriba eran cuatro líneas de aviso antes del primer número. Las etiquetas salen de `lib/inversion.ts` (`estadoEjercicio`, `etiquetaEjercicio`, `PIE_EJERCICIO_PARCIAL`), que las comparten el tablero y la ficha de municipalidad, y **la palabra «cerrado» no aparece en pantalla**: es jerga contable y define el dato por su contrario. **Y la página declara qué está viendo** («Viendo todas las municipalidades de la región Cusco, ejercicio 2026 al corte de junio. Fuente: …»): sin filtros sirve el ejercicio publicado más reciente y toda la región, y no lo decía en ninguna parte. Si `disponible:false` → **estado vacío elegante**: "Información en preparación" con `EmptyState`, que es lo que se ve entre una importación y su publicación. **Los filtros viven en la URL** (`anio`, `provincia`, `ordenar`, `vista`, `comparar_con`): sin eso la vista de comparación no sería enlazable y volver de una ficha devolvería al ejercicio por defecto. **La tabla se pagina en servidor** (`useApiPaginado` + pie «Mostrando X de Y» y «Ver 50 más», igual que `/peligros`) y el orden lo resuelve el API. Segunda vista **«Comparar ejercicios»** (`?vista=comparar`): agregados enfrentados, ranking por mayor variación de PIM y el Δ de % de ejecución marcado con asterisco cuando los cortes difieren, con la leyenda **pegada a la tabla** (ADR-D5). **Dice para qué sirve antes de pedir el segundo año** —enfrenta los ejercicios municipalidad por municipalidad, que es justo lo que el total de la tendencia no deja ver—: hasta aquí solo aparecía «Elige un ejercicio para comparar», que explica cómo usarla y no qué se gana |
**`/inversion` ofrece dos descargas** en la cabecera: el **Excel** de la tabla y el **Reporte (PDF)**, que es el tablero entero —gráficas, mapa y las 116 filas— y arrastra también `nivel` y `metrica`, para que el documento sea reproducible desde el mismo enlace con el que se pidió. La métrica de uso va como `descarga_pdf`, el mismo tipo de evento que la ayuda memoria.

**El visor de `/inversion`** (`MapaInversion.tsx`, ADR-D6) va entre la tendencia y la tabla, con
los filtros de la página más `nivel` y `metrica` en la URL para que la vista sea enlazable. Cuatro
botones de métrica (PIA / PIM / Devengado / % de ejecución) y conmutador distrito ↔ provincia.
Pulsar un polígono abre la ficha de su municipalidad **conservando los filtros** a nivel distrital,
y fija el filtro de provincia a nivel provincial. Lo que **no** es negociable en la interfaz:

- La leyenda imprime **los rangos en soles**, porque los tramos son quintiles de lo que se está
  viendo y el color es relativo a la vista.
- El pie declara **el importe que el nivel no puede pintar**, con el motivo que viene del API.
- Con la métrica de % de ejecución sobre un ejercicio parcial, la advertencia del corte se repite
  **junto al mapa**: el banner de arriba no viaja cuando alguien recorta el mapa para una lámina.
- Si el mapa o el catálogo de capas fallan, la sección dice que no está disponible y **el resto de
  la página sigue funcionando** — va en su propia petición justamente por eso.

| `/inversion/:codigo` | `/api/inversion/entidades/{codigo}/`. **NUEVA** — ficha de una municipalidad, por código MEF y no por ubigeo (las mancomunidades y el gobierno regional no tienen distrito). KPIs del ejercicio, **historia presupuestal** 2022-2026, reparto por procesos y desglose de actividades y proyectos con su proceso. Enlace a `/peligros` acotado a su distrito, y aviso propio cuando la municipalidad no casa con el padrón. Un código inexistente da `EmptyState` «Municipalidad no encontrada», sin `PageHeader`, como el resto de las fichas. El enlace de vuelta **conserva los filtros** con los que se llegó |
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
- **El menú de escritorio va en una sola línea** (desde `lg`). La barra tiene altura fija, así que un enlace que parte su texto en dos se sale por arriba y por abajo: los enlaces llevan `whitespace-nowrap`, logo y `nav` van con `shrink-0`, y el que cede espacio cuando falta es el buscador (`min-w-0` en el `form` y en el `input`, `w-40` hasta `xl` y `w-56` desde ahí). Medido a 1024, 1280 y 1440 px en `e2e/header.spec.ts`. Con «Sobre el observatorio» y «Buenas prácticas» el nav mide **555 px a 1024 px**, y ahí ceder dejó de alcanzar: al campo le quedaban 63 px, que no dan para escribir. Así que **entre `lg` y `xl` el buscador colapsa a un botón-lupa** que lleva a `/buscar` (`hidden md:flex lg:hidden xl:flex` en el `form`, `hidden lg:flex xl:hidden` en la lupa), y desde `xl` vuelve el campo entero con sus 224 px. De `md` a `lg` el campo sigue visible porque ahí el menú está detrás de la hamburguesa y sobra sitio. El `aria-label` de la lupa es «Ir al buscador» y no «Buscar»: navega en vez de buscar en sitio, y así no choca con el `input[aria-label="Buscar"]` que localizan las pruebas.
- Hero de portada: carrusel/slide único según nº de `HeroSlide` publicados.

## Compartir, títulos y recorte de texto

**Compartir** (`components/Compartir.tsx`) va al pie de las cinco fichas de detalle:
`navigator.share` en móvil, y WhatsApp / Facebook / LinkedIn / copiar enlace en escritorio. Sin
dependencia nueva —los iconos son de `lucide-react`, ya instalado—. **La previsualización no la
hace este componente**: sale de las metas que inyecta el servidor (ADR-A24), porque los
rastreadores no ejecutan JavaScript.

**Títulos por página** (`lib/meta.ts`). `useMetaPagina()` pone `document.title` y la
`description`; `META_RUTAS` tiene los de las rutas fijas y las fichas lo llaman con su contenido.
Dos reglas: **el hook va antes de cualquier `return`** —las fichas tienen returns condicionales de
carga y error, y llamarlo después haría que React viera un número distinto de hooks entre
renders—, y **no toca `og:*`**, que son del servidor: dos sitios escribiendo las mismas metas es
la forma segura de que un día discrepen. El recorte a 110 caracteres es el mismo que aplica el
servidor, a propósito.

**Recorte de texto largo.** El patrón del sitio es `line-clamp-2` / `line-clamp-3` de Tailwind
(nativo desde 3.3, `plugins: []`), acompañado de `break-words` cuando el texto puede traer tokens
sin espacios. Se recorta **por CSS y no por JS**: el texto entero sigue en el DOM para el lector de
pantalla y para Google, y el atributo `title` lo enseña al pasar el ratón. `/normativa` era la
única sección sin recorte y a una sola columna de 1280 px; sus tres campos largos —título (300),
resumen (700) y análisis (**sin límite**)— van clamped, y el `numero` de la norma se pinta de chip
porque es lo que permite recortar el título sin que el usuario pierda de qué norma se trata.

**Imágenes.** `Portada.tsx` es el único envoltorio compartido. Lleva `width`/`height` para reservar
el hueco, y **no** `loading="lazy"`: es la imagen LCP de su propia página. En los listados sí se
difiere.

## El mapa de Inversión y su diagrama de caja

La sección «¿Dónde está el presupuesto?» tenía **~150 palabras** de prosa alrededor del mapa —una
entradilla, el párrafo de quintiles y dos pies— con **los mismos 13 distritos capital explicados
dos veces con palabras distintas**, y dos frases que se justificaban a sí mismas ante el lector
(«los rangos van siempre en la leyenda por eso mismo», «la advertencia va aquí porque este mapa se
cita suelto»), que son comentarios de código impresos en la pantalla. Hoy quedan ~60 palabras: se
retiró la entradilla —lo que decía ya está en la línea de alcance de la cabecera— y cada pie dice
**su** hecho, uno el dinero que no se pinta y otro los polígonos en blanco. **Siguen siendo dos**:
hoy coinciden en los mismos 13 distritos, pero uno cuya municipalidad no tenga presupuesto este año
caería solo en el segundo, y fundirlos sería una simplificación que un día es falsa.

Y el mapa era **el único gráfico de la página sin `Declaracion`**: cuatro párrafos sobre lo que no
se pinta y ninguno sobre lo que sí. Ahora lleva la suya, y debajo un **diagrama de caja**
(`components/CajaDistribucion.tsx`) de la métrica y el nivel que estén seleccionados — el mapa dice
*dónde* está el dinero; la caja, *cómo de repartido* está.

- **Es SVG a mano, no Recharts.** El proyecto no usa `ErrorBar`, `Scatter` ni `ComposedChart` en
  ninguna parte, y componer un diagrama de caja con barras apiladas es más frágil que dibujarlo. El
  precedente ya existía (`ProyectosVsActividades`) y el PDF construye sus SVG con `rect`/`line`/
  `text`, así que el día que la caja pase al papel se traduce casi línea a línea.
- **El dinero va en escala logarítmica, y no es una preferencia**: medido, en un eje lineal de
  600 px la caja del PIM distrital ocupa **9 píxeles**. El % de ejecución va lineal de 0 a 100 —no
  hay cola que comprimir— y ahí un 0 % es un punto válido.
- **Dos repliegues, los dos porque `log(0)` no existe**: los ceros se excluyen del dibujo y **se
  declaran** en la frase; y si `q1` valiera 0 la escala se repliega a lineal. Sin lo segundo el
  borde de la caja sería `-Infinity` y el SVG no pintaría nada, **sin dar ningún error**.
- **Los atípicos llevan su nombre en un `<title>`**, que da tooltip nativo sin una línea de JS: un
  punto suelto a la derecha no dice nada, «PICHARI» sí.
- Los tres cuartiles van **escritos** bajo la caja: la forma enseña el sesgo, pero leer un número no
  puede depender de medir píxeles, y menos en logarítmica.

Los cinco números **no se calculan aquí**: vienen del payload junto a `cortes` (ver 02). `Declaracion`
salió de `Inversion.tsx` a `components/` al ganar un quinto usuario.

**La caja va enmarcada y con su frase dentro**, con el encuadre que ya usa `FiltroTema` para un panel
embebido. Apilada al mismo nivel que los demás párrafos se leía como dos apartados sueltos más de una
lista de ocho bloques separados por 6-16 px; ahora son seis, con 12-20. Y el `viewBox` mide 96 y no
78: **las etiquetas de los cuartiles tenían su línea base justo en el borde y se veían cortadas**, que
es un fallo que no da ningún error — lo vigila una prueba e2e que comprueba que cada `<text>` cabe.

Bajo el mapa queda **un solo pie**, el de ADR-D6, y **con su porcentaje**: «S/ 10.350.637 (19 %) no
está en el mapa. Es de 13 municipalidades provinciales y 4 entidades sin distrito. Sí cuenta en el
total del ámbito y en la tabla.» Cerraba justificando una decisión metodológica —«se declara aparte en
vez de repartirse»— en vez de contestar lo que el lector se pregunta, que es dónde está entonces ese
dinero. El pie de `poligonos.motivo` **se retiró de los dos medios**: pantalla y PDF traen en su
leyenda el cuadro blanco «sin municipalidad (N)», así que la frase solo repetía el porqué.

## Descargas (`BotonDescarga`)

Las cuatro descargas del sitio —ayuda memoria y Excel de `/peligros`, reporte y Excel de
`/inversion`— pasan por **`components/BotonDescarga.tsx`**, y ninguna es un `<a href>` a pelo. El
servidor tarda: la ayuda memoria **3,7-4,0 s** y el reporte de inversión **4,4 s**, porque los dos
renderizan su mapa con un Chromium headless. Con el enlace directo la página no cambiaba en
absoluto durante esos segundos —en escritorio salvaba el indicador del navegador; en móvil, que es
donde el TDR pide que el sitio sirva, no se veía nada— y el visitante volvía a pulsar.

- **El archivo se pide con `fetch` y se entrega desde un blob**, que es lo que permite tener estado
  real. No se finge con un temporizador: diría «listo» cuando no lo está.
- **Sigue siendo un `<a href>`, no un `<button>`.** El `onClick` intercepta el clic normal, pero
  Ctrl/Cmd/Shift/Alt y el botón central **se dejan pasar al navegador**: con un `<button>` se
  perderían «abrir en pestaña nueva» y «guardar enlace como», que hoy funcionan.
- **El estado se cuenta dos veces, y no sobra ninguna.** En el botón (icono girando, «Generando
  PDF…», `aria-disabled`) y en un aviso fijo abajo a la derecha (`AvisoDescarga.tsx`), porque los
  botones viven en el `PageHeader` y **dejan de verse en cuanto se baja a la tabla o al mapa**. El
  aviso de «generando» se retira solo —la descarga es la confirmación—; el de error **se queda
  hasta que se cierra**, porque un error que se autodestruye a los tres segundos no lo lee nadie.
- **El `aria-live` va en el aviso, no en el botón.** Con los dos, un lector de pantalla lo
  anunciaría dos veces. Los avisos se apilan en un contenedor único portado a `document.body`: dos
  descargas simultáneas son posibles (cada botón solo se bloquea a sí mismo) y sin él se pintarían
  encima. No hace falta un proveedor global de notificaciones para dos casos.
- **El 429 se explica.** El límite es de 30/hora **por IP** y una oficina entera comparte IP detrás
  de un NAT, así que no es hipotético: antes se veía como una pestaña con JSON crudo, o como nada.
- **El nombre del archivo sale de `Content-Disposition`, y eso exige `CORS_EXPOSE_HEADERS` en el
  backend** (ver 07). Sin esa cabecera no falla nada: el archivo se guarda con el identificador del
  blob, sin extensión. Por eso cada botón declara además un `nombreDeReserva` — un bundle nuevo
  contra un backend viejo es un estado real durante un despliegue.

Lo que **no** se hizo, y por qué: encolar la generación en django-tasks y sondear el estado. Para
cuatro segundos añade dos peticiones, una fila de BD y **un archivo que hay que guardar en algún
sitio** — y `MEDIA_ROOT` lo sirve nginx entero como estático público, así que una ayuda memoria
filtrada quedaría accesible por URL. El mecanismo se guarda para la generación por lotes, que sí
lo pide.

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
