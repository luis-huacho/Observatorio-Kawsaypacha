# 00 — Alcance y registro de decisiones

## Marco

- **Objeto**: implementar la plataforma web pública de monitoreo de la GRD y la ACC en la región Cusco, para el funcionamiento del observatorio. Encargo de PREDES, dentro del proyecto de resiliencia ante el riesgo climático en comunidades altoandinas de Cusco.
- **Fecha de puesta en línea: 13/08/2026.** Es la restricción que decide el alcance: lo que no quepa antes de esa fecha se difiere con un ADR, no se recorta en silencio.
- El detalle contractual —partes, entregables, calendario de pagos y penalidades— **no se versiona**: vive en `_docs/producto1-plan-de-trabajo.md` y en los PDF de `data/contrato/`, ambos fuera del repo publicado. Aquí solo queda lo que condiciona decisiones técnicas.

## Requisitos obligatorios del TDR

1. Sistema integrado único con ventanas temáticas, **administrable por PREDES sin asistencia técnica**: actualización por **carga de archivos** (Excel de exposición, presupuesto, etc.) y **reemplazo de capas cartográficas**.
2. Flujo editorial **borrador → revisión → publicación** con **avisos por correo**.
3. **Exportar tablas a Excel**.
4. **Ayudas memoria PDF por distrito** (para mesas técnicas).
5. **Tableros comparativos entre distritos**.
6. **Noticias/artículos**, **repositorio de videos**, **calendario público de eventos**.
7. **Métricas internas de uso**.
8. Despliegue en **servidor propio** con dominio, **HTTPS** y **backups automáticos**.
9. Fase III: capacitación al equipo PREDES + registro audiovisual del funcionamiento.

## Ventanas temáticas

| Ventana | Estado | Fuente de datos |
|---|---|---|
| Exposición a peligros naturales | Activa | Excel `Base_Nivel Peligro_CCPP_Cusco.xlsx` (10,978 clasificaciones sobre 8,968 CCPP) + `Base_Frecuencia_Peligro_Cusco.xlsx` (111 distritos) — ver 01 |
| Medidas (buenas prácticas) | Activa | Contenido editorial (admin) |
| Inversión (PPR 0068) | **Diferida** (ADR-D3) | **Pendiente: el cliente aún no tiene claridad sobre la data.** Solo se entrega la ruta con estado vacío; sin modelos ni importador |
| Normativa | Activa | Contenido editorial (admin) |
| Prioridades | **Desactivada** | — |

> **ADR-D2 — CKEditor 5 como editor de los campos rich.** Los specs pedían "rich text" en cuatro campos (`Medida.contenido`, `Norma.contenido`, `Noticia.cuerpo`, `BloqueTexto.cuerpo`) sin decir con qué se editan. Se adopta **CKEditor 5** en el admin (`django-ckeditor-5`), que es el que el equipo editorial va a usar. Arrastra tres consecuencias que no son opcionales:
>
> 1. **Sanear en servidor antes de guardar**, con lista blanca de etiquetas y atributos (`nh3` o `bleach`; ninguno está aún en `pyproject.toml`). El frontend inyecta con `dangerouslySetInnerHTML` y no puede ser la última línea de defensa.
> 2. **Convertir el `<oembed>`**. Para un video incrustado CKEditor no emite un iframe sino `<figure class="media"><oembed url="…"></oembed></figure>`, que **ningún navegador pinta**. La conversión está resuelta en `prototype/src/components/ContenidoRico.tsx`.
> 3. **El frontend necesita hoja de estilos propia.** El Preflight de Tailwind deja `h1..h6` en `font-size: inherit` y las listas sin viñeta: sin la clase `.contenido-rico` el HTML del editor se ve como un bloque plano de párrafos. Ver 06.
>
> Decisión del dueño del proyecto.

> **ADR-D1 — Los subtotales `TOT_*` de frecuencia sí se almacenan, como total declarado.** El spec original decía descartarlos y recalcular todo desde el desglose por evento. Al auditar el Excel real apareció que **el distrito de Cusco trae los cuatro subtotales llenos (`TOTAL` 134) y ninguna columna de evento**: recalcular dejaría a la capital regional mostrando 0 emergencias, que es peor que no mostrar nada. Se añade `peligros.TotalDeclaradoEmergencias` (distrito × categoría). Regla: si hay desglose se usa el desglose y el declarado se ignora (registrando el descuadre en el log); si no lo hay, se muestra el declarado con la leyenda explícita de que la fuente no desagrega. Decisión del dueño del proyecto.

> **ADR-P1 — Prioridades desactivada.** El TDR menciona "cinco ventanas temáticas". En **reunión de trabajo** se decidió desactivar "Prioridades" para este proyecto porque no se dispondrá de la información dentro del plazo. El código del prototipo se conserva pero **sin ruta registrada** y fuera del menú (menú controlado por datos: `EnlaceMenu.visible=False`). No reactivar sin pedido explícito.

> **ADR-P2 — El comparador de distritos sale de la navegación.** `/comparar` deja de ofrecerse en el menú principal y en el pie. **No se retira nada más**: la ruta del SPA sigue registrada y responde por URL directa, `GET /api/comparador/distritos/` sigue publicado y probado, y el enlace de menú se conserva con `EnlaceMenu.visible=False`, así que volver a mostrarlo es marcar una casilla en el admin. Es un grado más suave que ADR-P1, donde la ruta ni existe. Hizo falta además una migración de datos (`sitio.0002`), porque el seed crea lo que falta y no toca lo que ya existe: sin ella las bases ya sembradas seguirían sirviendo el enlace. Decisión del dueño del proyecto.

Complementan a las ventanas: portada (hero administrable), buscador global, noticias, videos, eventos, biblioteca/recursos, comparador de distritos (accesible por URL, fuera del menú — ADR-P2), sección Sobre.

## ADRs de arquitectura

| # | Decisión | Alternativa descartada | Razón |
|---|---|---|---|
| A1 | **PostgreSQL 16 plano** + pipeline geo offline | PostGIS | No hay consultas espaciales en runtime (CCPP son lat/lon planos; las capas solo se convierten a tiles). Evita GDAL/GEOS en la imagen Django |
| A2 | **DRF** + django-filter + drf-spectacular | Django Ninja | API 95% lectura con filtros/paginación; ecosistema probado (throttling, exports) |
| A3 | **django-tasks** (backend BD) + contenedor `worker` + cron | Celery + Redis | Sin broker extra; suficiente para Gemini, tiles, correos e importaciones con 1 desarrollador y 4 semanas |
| A4 | Búsqueda: llave **search-only** de Meilisearch expuesta al navegador, proxy vía nginx `/search/` | Proxy DRF | Las llaves search-only son seguras por diseño; facetas y typo-tolerance sin boilerplate. Las búsquedas se registran en métricas vía beacon |
| A5 | Tiles: **PMTiles estáticos** servidos por nginx con HTTP Range | tileserver dedicado / tiles dinámicos | MapLibre + protocolo `pmtiles://` lee por rangos; cero servicios adicionales. **Excepción: la capa CCPP** — ver A13 |
| A13 | Capa CCPP del visor: **fuente `geojson` agrupada** (clustering + símbolos proporcionales a población) | PMTiles como el resto de capas | El clustering se pidió como requisito y **MapLibre solo agrupa fuentes `geojson`**; no hay clustering sobre fuentes vectoriales. Solo afecta a CCPP: ríos, lagunas y glaciares siguen en PMTiles. Detalle y pendientes en 05 |
| A6 | ~~Edge: **Caddy** (auto-Let's Encrypt)~~ | — | **Superado por A6bis.** Se conserva la fila para que el historial de la decisión quede legible |
| A7 | Mapa: **MapLibre GL JS** (reescritura de `MapaPeligros`) | Leaflet + protomaps-leaflet | Soporte nativo MVT/PMTiles; mejor rendimiento con 8,968 puntos. Decisión del dueño del proyecto |
| A8 | Admin: **django-unfold** | jazzmin / admin plano | UX moderna para editores no técnicos; dashboard personalizable. Decisión del dueño del proyecto |
| A9 | PDF distrito: **WeasyPrint** | reportlab / Chrome headless | Reusa plantillas HTML con la paleta PREDES. **Matiz**: el navegador headless sí entra, pero solo para capturar el PNG del mapa (ver 02) — la maquetación del documento sigue siendo WeasyPrint |
| A10 | Gemini `gemini-2.5-flash` vía SDK `google-genai`, PDF como input nativo | extracción de texto local | Acepta PDF directo; barato y suficiente para resúmenes |
| A11 | Métricas: app propia (eventos → agregados diarios, sin PII) | Google Analytics / Plausible | El TDR pide métricas *internas*; privacidad y cero dependencias externas |
| A12 | Actualización de datos: **DatasetUpload** con reemplazo atómico | edición manual fila a fila | Requisito TDR: el cliente re-sube el mismo Excel actualizado y los datos se reemplazan |
| A6bis | Edge: **nginx + certbot en contenedor** (sustituye a Caddy) | Caddy | Es lo que PREDES y su hosting saben operar; el ahorro de configuración de Caddy no compensa una pieza que nadie más sabe depurar. Decisión del dueño del proyecto. Coste asumido: la renovación de certificados depende del cron de certbot, no es automática por diseño |
| A14 | **Dos dominios**: `observatorio.predes.org.pe` (SPA) y `obs.predes.org.pe` (API, admin, media, tiles, search) | dominio único con `/api` en el mismo origen | Deja el admin y el API fuera del dominio que se difunde, y permite mover cualquiera de los dos por separado. Coste asumido: CORS entre ambos, incluidas cabeceras en `/tiles` y `/media`. Decisión del dueño del proyecto |

> **ADR-D3 — La ventana Inversión no se implementa en esta fase.** El TDR la incluye y sigue siendo parte del producto, pero **el cliente aún no tiene claridad sobre la data**: ni el formato del Excel ni el alcance del PPR 0068 están definidos, y modelar contra un formato imaginado se tira a la basura en cuanto llegue el real. No se crean la app `inversion` ni sus modelos; `GET /api/inversion/` responde `{"disponible": false}` de forma fija y `/inversion` muestra el estado vacío del spec 06. El enlace de menú existe con `EnlaceMenu.visible` editable, así que PREDES puede ocultarlo. Cuando llegue la data se añade la app sin tocar el frontend. Decisión del dueño del proyecto.

## Fuera de alcance (esta fase)

- Ventana Prioridades (ADR-P1).
- Ventana Inversión: modelos, importador y endpoint con datos (ADR-D3). La ruta y su estado vacío sí se entregan.
- Scraping automático de Consulta Amigable MEF (la inversión se carga por Excel).
- i18n quechua, series temporales, 7 procesos GRD, directorio de actores (roadmap futuro, ver `archive/05-roadmap.md`).

## Dependencias del cliente (riesgos)

| Dependencia | Impacto si no llega | Mitigación |
|---|---|---|
| Data de Inversión (Excel) | Ventana vacía | Estado "información en preparación" u ocultar desde admin (ADR-D3) |
| Capas SIG oficiales (especialista SIG) | Capas referenciales | Publicar capas nacionales recortadas a Cusco con atribución |
| **Polígono oficial de Cusco** (`cusco_region.geojson`) | Ninguno hoy: **resuelto de forma provisional** con geoBoundaries ADM1 (CC BY 4.0), versionado en `backend/apps/mapas/datos/`. Se sustituye por el del INEI cuando llegue | Ver 05 |
| **Fila de frecuencia de ACOMAYO** (080201) | Un distrito sin historial de emergencias | Estado vacío explícito; pedir la fila al cliente |
| Textos definitivos, dominio, SMTP | Bloqueo de despliegue/correos | Solicitud formal en semana 1 (ver `_docs/planner.md`) |

## Observaciones de calidad de datos a devolver al cliente

Detectadas al auditar los Excel (02/08/2026); ninguna bloquea el desarrollo, todas conviene que PREDES las corrija en origen:

1. El distrito de **Cusco** declara 134 emergencias sin desglose por tipo de evento. Con él, **26 distritos** declaran subtotales sin desagregar (104 filas de total declarado).
2. Falta la fila del distrito de **Acomayo** en `Base_Frecuencia_Peligro_Cusco.xlsx`.
3. **229 filas** del Excel de niveles traen peligro y respaldo documental pero sin `NIVEL_PELI`.
4. Descuadres entre subtotal y desglose en **Sangarará** y **Mollepata**.
5. Dos grafías de la misma fuente (`SIGRID_CENEPRED` / `CENEPRED_SIGRID`) y 23 formatos de `RANGO FECHA`.
6. `Incendio forestal` está clasificado como "inducido por acción humana" en un Excel y como "meteorológico" en el otro.
7. En `lagos-y-lagunas.geojson`, 4 lagunas traen `DPTO` compuesto (`Arequipa/Cusco`, `Madre deDios/Cusco`, `Cusco/Junin`): cruzan el límite regional y ningún filtro por departamento las incluye. Conviene decidir con PREDES si deben mostrarse.
8. **21 distritos tienen fila en el Excel de frecuencia y ni un solo dato** (ACOPIA, ACOS, MOSOC LLACTA, POMACANCHI, RONDOCAN, ANTA, CHINCHAYPUJIO, HUAROCONDO, LIMATAMBO, PUCYURA, ZURITE, ALTO PICHIGUA, CONDOROMA, COPORAQUE, ESPINAR, OCORURO, PALLPATA, PICHIGUA, INKAWASI, OCOBAMBA, SANTA ANA): ni por evento ni como subtotal. Sumados a Acomayo, son **22 de los 112 distritos sin historial de emergencias**, y el API responde 404 para todos ellos. Es distinto de declarar cero, y distinto de declarar un subtotal sin desagregar: no hay dato. Detectado el 03/08/2026 al escribir las pruebas del importador.
