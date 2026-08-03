# 00 — Alcance y registro de decisiones

## Marco contractual

- **Contrato N°0362026/PREDES** (locación de servicios, firmado 14/07/2026 en Lima). Comitente: PREDES (RUC 20109358658). Locador: Luis Huacho. Marco: proyecto "Incremento de la Resiliencia Ante el Riesgo Climático en las Comunidades Altoandinas de Cusco, Perú" (Brot für die Welt).
- **Objeto**: implementar la plataforma web pública de monitoreo de la GRD y la ACC en la región Cusco, para el funcionamiento del observatorio.
- **Entregables**: E1 Plan de trabajo (16/07/2026, 40%); E2 Informe final + plataforma funcionando en internet (13/08/2026, 60%). Penalidad por mora: 1%/día hasta 10%.
- Fuentes: `data/contrato/TDR Plataforma y Diseño observatorio GRD Y ACC (1).pdf` y `data/contrato/Contrato de Servicio_Luis Huacho_Plataforma y Diseño Observatorio GRD y ACC.pdf`.

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
| Inversión (PPR 0068) | Activa, **sin datos** | **Pendiente: el cliente aún no entrega la data.** Módulo completo con estado vacío elegante / ocultable desde admin |
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

Complementan a las ventanas: portada (hero administrable), buscador global, noticias, videos, eventos, biblioteca/recursos, comparador de distritos, sección Sobre.

## ADRs de arquitectura

| # | Decisión | Alternativa descartada | Razón |
|---|---|---|---|
| A1 | **PostgreSQL 16 plano** + pipeline geo offline | PostGIS | No hay consultas espaciales en runtime (CCPP son lat/lon planos; las capas solo se convierten a tiles). Evita GDAL/GEOS en la imagen Django |
| A2 | **DRF** + django-filter + drf-spectacular | Django Ninja | API 95% lectura con filtros/paginación; ecosistema probado (throttling, exports) |
| A3 | **django-tasks** (backend BD) + contenedor `worker` + cron | Celery + Redis | Sin broker extra; suficiente para Gemini, tiles, correos e importaciones con 1 desarrollador y 4 semanas |
| A4 | Búsqueda: llave **search-only** de Meilisearch expuesta al navegador, proxy vía Caddy `/search/` | Proxy DRF | Las llaves search-only son seguras por diseño; facetas y typo-tolerance sin boilerplate. Las búsquedas se registran en métricas vía beacon |
| A5 | Tiles: **PMTiles estáticos** servidos por Caddy con HTTP Range | tileserver dedicado / tiles dinámicos | MapLibre + protocolo `pmtiles://` lee por rangos; cero servicios adicionales. **Excepción: la capa CCPP** — ver A13 |
| A13 | Capa CCPP del visor: **fuente `geojson` agrupada** (clustering + símbolos proporcionales a población) | PMTiles como el resto de capas | El clustering se pidió como requisito y **MapLibre solo agrupa fuentes `geojson`**; no hay clustering sobre fuentes vectoriales. Solo afecta a CCPP: ríos, lagunas y glaciares siguen en PMTiles. Detalle y pendientes en 05 |
| A6 | Edge: **Caddy** (auto-Let's Encrypt) | nginx + certbot | Un contenedor: SPA + media/tiles + proxy api/admin/search + HTTPS automático |
| A7 | Mapa: **MapLibre GL JS** (reescritura de `MapaPeligros`) | Leaflet + protomaps-leaflet | Soporte nativo MVT/PMTiles; mejor rendimiento con 8,968 puntos. Decisión del dueño del proyecto |
| A8 | Admin: **django-unfold** | jazzmin / admin plano | UX moderna para editores no técnicos; dashboard personalizable. Decisión del dueño del proyecto |
| A9 | PDF distrito: **WeasyPrint** | reportlab / Chrome headless | Reusa plantillas HTML con la paleta PREDES |
| A10 | Gemini `gemini-2.5-flash` vía SDK `google-genai`, PDF como input nativo | extracción de texto local | Acepta PDF directo; barato y suficiente para resúmenes |
| A11 | Métricas: app propia (eventos → agregados diarios, sin PII) | Google Analytics / Plausible | El TDR pide métricas *internas*; privacidad y cero dependencias externas |
| A12 | Actualización de datos: **DatasetUpload** con reemplazo atómico | edición manual fila a fila | Requisito TDR: el cliente re-sube el mismo Excel actualizado y los datos se reemplazan |

## Fuera de alcance (esta fase)

- Ventana Prioridades (ADR-P1).
- Scraping automático de Consulta Amigable MEF (la inversión se carga por Excel).
- i18n quechua, series temporales, 7 procesos GRD, directorio de actores (roadmap futuro, ver `archive/05-roadmap.md`).

## Dependencias del cliente (riesgos)

| Dependencia | Impacto si no llega | Mitigación |
|---|---|---|
| Data de Inversión (Excel) | Ventana vacía | Estado "información en preparación" u ocultar desde admin |
| Capas SIG oficiales (especialista SIG) | Capas referenciales | Publicar capas nacionales recortadas a Cusco con atribución |
| **Polígono oficial de Cusco** (`cusco_region.geojson`) | Sin recorte espacial para capas sin campo de departamento (glaciares) | Fuente pública (INEI / geoBoundaries ADM1). Provisional en la demo: filtro por `cordillera` + bbox regional (ver 05) |
| **Fila de frecuencia de ACOMAYO** (080201) | Un distrito sin historial de emergencias | Estado vacío explícito; pedir la fila al cliente |
| Textos definitivos, dominio, SMTP | Bloqueo de despliegue/correos | Solicitud formal en semana 1 (ver `_docs/planner.md`) |

## Observaciones de calidad de datos a devolver al cliente

Detectadas al auditar los Excel (02/08/2026); ninguna bloquea el desarrollo, todas conviene que PREDES las corrija en origen:

1. El distrito de **Cusco** declara 134 emergencias sin desglose por tipo de evento.
2. Falta la fila del distrito de **Acomayo** en `Base_Frecuencia_Peligro_Cusco.xlsx`.
3. **229 filas** del Excel de niveles traen peligro y respaldo documental pero sin `NIVEL_PELI`.
4. Descuadres entre subtotal y desglose en **Sangarará** y **Mollepata**.
5. Dos grafías de la misma fuente (`SIGRID_CENEPRED` / `CENEPRED_SIGRID`) y 23 formatos de `RANGO FECHA`.
6. `Incendio forestal` está clasificado como "inducido por acción humana" en un Excel y como "meteorológico" en el otro.
