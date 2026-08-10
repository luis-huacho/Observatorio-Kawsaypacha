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
| Inversión (PP 0068) | Activa (ADR-D4, supera a ADR-D3) | `Base_Prespuesto_PP0068_cusco_final.xlsx` (corte 2026-06, 119 pliegos) + serie 2022-2025 del comparativo del MEF, consolidadas por `scripts/consolidar_pp0068.py` y `scripts/totales_institucionales.py` — ver 01 |
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
| A13 | Capa CCPP del visor: **fuente `geojson` agrupada** (clustering; los símbolos ya no son proporcionales a población — ver A17) | PMTiles como el resto de capas | El clustering se pidió como requisito y **MapLibre solo agrupa fuentes `geojson`**; no hay clustering sobre fuentes vectoriales. Solo afecta a CCPP: ríos, lagunas y glaciares siguen en PMTiles. Detalle y pendientes en 05 |
| A6 | ~~Edge: **Caddy** (auto-Let's Encrypt)~~ | — | **Superado por A6bis.** Se conserva la fila para que el historial de la decisión quede legible |
| A7 | Mapa: **MapLibre GL JS** (reescritura de `MapaPeligros`) | Leaflet + protomaps-leaflet | Soporte nativo MVT/PMTiles; mejor rendimiento con 8,968 puntos. Decisión del dueño del proyecto |
| A8 | Admin: **django-unfold** | jazzmin / admin plano | UX moderna para editores no técnicos; dashboard personalizable. Decisión del dueño del proyecto |
| A9 | PDF distrito: **WeasyPrint** | reportlab / Chrome headless | Reusa plantillas HTML con la paleta PREDES. **Matiz**: el navegador headless sí entra, pero solo para capturar el PNG del mapa (ver 02) — la maquetación del documento sigue siendo WeasyPrint |
| A10 | Gemini `gemini-2.5-flash` vía SDK `google-genai`, PDF como input nativo | extracción de texto local | Acepta PDF directo; barato y suficiente para resúmenes |
| A11 | Métricas: app propia (eventos → agregados diarios, sin PII) | Google Analytics / Plausible | El TDR pide métricas *internas*; privacidad y cero dependencias externas |
| A12 | Actualización de datos: **DatasetUpload** con reemplazo atómico | edición manual fila a fila | Requisito TDR: el cliente re-sube el mismo Excel actualizado y los datos se reemplazan |
| A6bis | Edge: **nginx + certbot en contenedor** (sustituye a Caddy) | Caddy | Es lo que PREDES y su hosting saben operar; el ahorro de configuración de Caddy no compensa una pieza que nadie más sabe depurar. Decisión del dueño del proyecto. Coste asumido: la renovación de certificados depende del cron de certbot, no es automática por diseño |
| A15 | Seguimiento de errores: **Gitea** (`compose.tracking.yaml`), gestionado por el MCP oficial. **Dos modos**: aislado tras túnel SSH, o publicado en `/gitea` del dominio del API con `compose.tracking-publicado.yml` | tabla Markdown en `09-errores.md` · GitHub Issues en `origin` · subdominio `git.…` propio | La tabla duplicaba el estado a mano en tres documentos y ya había dejado una referencia rota desde el código. GitHub Issues costaría cero infraestructura, pero saca la lista de pendientes del control del desarrollador y la publica en un servicio de terceros. Hay **un solo tracker**, en el servidor: dos listas de pendientes divergen, que es el problema del que se venía. La subruta se elige sobre el subdominio por no pedir DNS ni reemitir el certificado, **a sabiendas de que la propia documentación de Gitea la desaconseja**; se usa su bloque nginx literal, con el doble `rewrite` que preserva las URIs sin decodificar. El acoplamiento va del tracker a la aplicación y nunca al revés —el tracker se engancha a la red del sitio, y nginx resuelve su destino por variable—, de modo que **si el tracker cae, `/gitea` da 502 y el resto del sitio no se entera**; verificado. **Riesgo aceptado por el dueño del proyecto, sobre objeción explícita:** publicado en `predes.org.pe` es un login expuesto a internet en el dominio del entregable, para un sistema que PREDES no sabe que existe. Mitigado con `limit_req` (30/min), sin anunciar versión, sin registro y con `allow`/`deny` por IP preparado y comentado en la configuración. Coste asumido: el volumen sqlite sigue fuera del servicio de backups, que solo vuelca PostgreSQL. Detalle en 09 |
| A16 | Visor: el número del círculo agrupado cuenta **clasificaciones** (`clasificaciones` del feature, sumada en `clusterProperties`), y su tamaño la población de los centros poblados que aportan alguna | `point_count` de MapLibre (centros poblados del grupo) | `point_count` cuenta lo que hay en la fuente, y la fuente **no se recorta con los filtros**: los que no cumplen siguen en ella para pintarse en gris (A13). El grupo seguía diciendo lo mismo con «Heladas · nivel 4» puesto que sin filtros, mientras la tabla de al lado ya había encogido — dos cifras contradictorias en la misma pantalla. Además la lectura espontánea de un «3» sobre el mapa es «aquí hay 3 peligros», no «3 pueblos». Coste asumido: el mapa queda en la unidad de las 10,978 y la tabla en la de las 3,238, así que **la pantalla muestra las dos rotuladas** y la cabecera de la tabla las reconcilia. Los sin clasificación siguen visibles en gris, con conmutador para ocultarlos. **Matizado por A17**: el tamaño ya no es población sino el mismo conteo del número |
| A17 | **`/peligros` es solo exposición**, con filtros de selección múltiple y símbolos que codifican **tipo en el ícono y nivel en el color** | mantener la página como estaba (un peligro a la vez, umbral de nivel mínimo, panel de frecuencia embebido) | Revisa A16 sin anularlo. Cuatro cambios, y ninguno es cosmético: **(a)** la **frecuencia de emergencias sale de la página** — es el otro eje de la fuente (lo ocurrido, por distrito, con 21 tipos de evento frente a 9 peligros, y taxonomías no convertibles: `INCENDIO FORESTAL` es *inducido por acción humana* allí y *meteorológico* aquí). Embebida bajo el mapa, los filtros de exposición no la afectaban y la pantalla parecía mal calculada. Su modelo, importador, endpoints, export, comparador y PDF quedan **intactos**; solo se retira de esta ruta, y dónde reubicarla lo decide el cliente. **(b)** Los filtros pasan a **checklist** —varios peligros a la vez, y niveles no contiguos como «Muy alto + Bajo», que con el `nivel_min` anterior era inexpresable—, y con ellos el API a parámetros de lista `peligros=`/`niveles=` (`peligro`/`nivel_min` sobreviven traducidos en un único parser). **(c)** **La población deja de ser un canal visual**: la fuente la trae, pero 948 de los 8,968 centros poblados valen 0 y la mediana es 17 habitantes, así que la inmensa mayoría caía en el peldaño más pequeño y el tamaño no distinguía nada; además diámetro y número del círculo hablaban de cosas distintas. El tamaño pasa a leer `clasif`, el mismo conteo que el número. Sigue publicada en la ficha individual y en `poblacion_total` (que consume el comparador), pero no en la lista ni en el geojson. **(d)** El canal que la población deja libre lo ocupa el **tipo de peligro**, dibujado como ícono (`TipoPeligro.icono`, editable en el admin y servido por el API), con el color reservado al nivel. Coste asumido: 36 imágenes rasterizadas (9 tipos × 4 niveles) que hay que registrar **antes** de añadir la capa `symbol`, y `icon-allow-overlap`, sin el cual MapLibre descarta la mayoría de los símbolos por colisión sin emitir ningún error. Decisión del dueño del proyecto |
| A14 | **Dos dominios**: `observatorio.predes.org.pe` (SPA) y `obs.predes.org.pe` (API, admin, media, tiles, search) | dominio único con `/api` en el mismo origen | Deja el admin y el API fuera del dominio que se difunde, y permite mover cualquiera de los dos por separado. Coste asumido: CORS entre ambos, incluidas cabeceras en `/tiles` y `/media`. Decisión del dueño del proyecto |

> **ADR-D3 — La ventana Inversión no se implementa en esta fase.** ~~El TDR la incluye y sigue siendo parte del producto, pero **el cliente aún no tiene claridad sobre la data**: ni el formato del Excel ni el alcance del PPR 0068 están definidos, y modelar contra un formato imaginado se tira a la basura en cuanto llegue el real. No se crean la app `inversion` ni sus modelos; `GET /api/inversion/` responde `{"disponible": false}` de forma fija y `/inversion` muestra el estado vacío del spec 06.~~ **Superado por ADR-D4** (10/08/2026): llegó la data. Lo que sí sobrevive: el enlace de menú existe con `EnlaceMenu.visible` editable, y el contrato `{"disponible": false, "motivo"}` se conserva como modo normal —es lo que sirve la ventana mientras PREDES revisa un ejercicio recién importado—. Decisión del dueño del proyecto.

> **ADR-D4 — La unidad de Inversión es la municipalidad, no el distrito.** Supera a ADR-D3, que difería la ventana por falta de data. El cliente entregó `Base_Prespuesto_PP0068_cusco_final.xlsx` (corte 2026-06) y la serie 2022-2025 se reconstruyó desde el comparativo del MEF, así que la ventana se implementa. Al hacerlo cambia la unidad que el spec 01 daba por buena: `InversionDistrito` era herencia del prototipo, pero **quien tiene PIA, PIM y devengado es la entidad ejecutora**, y una municipalidad provincial gestiona presupuesto de toda su provincia — repartirlo entre sus distritos para encajar en el modelo anterior habría inventado cifras distritales que ninguna fuente respalda. Consecuencias que no son opcionales:
>
> - Los modelos son `EntidadEjecutora`, `Ejercicio`, `PresupuestoEntidad` y `PresupuestoActividad`; `EjercicioPresupuestal` e `InversionDistrito` del spec 01 quedan sustituidos (ver 01).
> - **El reparto por procesos de la GRD se clasifica por actividad, no por producto.** A nivel de producto, «3000001 Acciones comunes» (34.6 % del PIM municipal de 2026) y los proyectos de inversión (40.7 %) dejarían tres cuartas partes del dinero en dos cajones que no dicen nada. Las 30 actividades del programa sí nombran el proceso; los proyectos se clasifican por el proyecto, porque sus acciones de obra («expediente técnico», «supervisión y liquidación») son genéricas y se repiten en obras de procesos distintos.
> - **Seis procesos y no los cinco de la hoja «Campos» del cliente.** Sin un sexto transversal, las tres actividades de acciones comunes —monitoreo del programa, instrumentos estratégicos, asistencia técnica, el 15.8 % del PIM municipal— habría que empujarlas a un proceso que no son.
> - El mapa coroplético por distrito del diseño original **queda fuera**: no hay geometrías distritales en el proyecto, solo el polígono regional. Ver 06.
> - **El ejercicio nace oculto.** Importar no publica: `Ejercicio.visible` es una decisión editorial de PREDES, y mientras no la tome la ruta sigue en su estado vacío.
>
> Decisión del dueño del proyecto, sobre alcance pedido en reunión: «saber por municipalidad local cómo es el avance de ejecución del presupuesto, en el marco del 0068».

## Fuera de alcance (esta fase)

- Ventana Prioridades (ADR-P1).
- Mapa coroplético por distrito en Inversión: no hay geometrías distritales en el proyecto (ADR-D4).
- Scraping automático de Consulta Amigable MEF: la inversión se carga por archivo, vía `DatasetUpload`.
- i18n quechua, series temporales, 7 procesos GRD, directorio de actores (roadmap futuro, ver `archive/05-roadmap.md`).

## Dependencias del cliente (riesgos)

| Dependencia | Impacto si no llega | Mitigación |
|---|---|---|
| Data de Inversión (Excel) | ~~Ventana vacía~~ **Entregada** el 09/08/2026 (`Base_Prespuesto_PP0068_cusco_final.xlsx`). Pendiente: el archivo trae dos filas de presupuesto institucional para Pillpinto y ninguna para Yaurisque, así que esas dos municipalidades quedan sin denominador | Cargas siguientes por `DatasetUpload`; mientras no haya ejercicio visible, la ruta muestra "información en preparación" (ADR-D4) |
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
