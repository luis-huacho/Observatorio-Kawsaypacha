# 03 — Admin, flujo editorial e importadores

Admin Django con **django-unfold** (ADR-A8). Objetivo TDR: que PREDES administre todo el contenido **sin asistencia técnica**: datos (Excel), capas (GeoJSON), contenido editorial, textos estáticos y hero.

## Navegación del admin (Unfold sidebar)

1. **Panel** — dashboard con métricas (ver abajo).
2. **Datos** — Cargas de datos (DatasetUpload), Centros poblados, Clasificaciones, Frecuencia de emergencias, Inversión.
3. **Contenido** — Medidas, Normativa, Noticias, Videos, Eventos, Biblioteca.
4. **Mapa** — Capas cartográficas.
5. **Sitio** — Configuración, Bloques de texto, Hero, Menú.
6. **Usuarios** — usuarios y grupos.

Idioma `es-pe`, zona horaria `America/Lima`. Branding con paleta PREDES (colores `mountain/earth/sky` del prototipo) vía `UNFOLD["COLORS"]` y logo.

## Roles y permisos (grupos Django)

| Grupo | Puede |
|---|---|
| **Editor** | Crear/editar contenido propio; pasar `borrador → revision`; subir documentos |
| **Publicador** | Todo lo del editor + `revision → publicado`, `publicado → archivado/borrador`; gestionar datasets y capas |
| **Administrador** | Todo + usuarios, configuración del sitio, menú |

Implementación: permisos custom `puede_publicar` por modelo Workflow; en Unfold se ocultan las acciones de transición no permitidas.

## Flujo editorial (WorkflowMixin)

Estados: `borrador → revision → publicado` (+ `archivado`). Reglas:
- Solo `publicado` aparece en API pública y en Meilisearch.
- Transiciones vía botones de acción en el change form (Unfold actions), no editando el campo a mano.
- `transicionar()` valida el paso y **encola** el correo (django-tasks, nunca bloquea el request).

### Avisos por correo (requisito TDR)
| Transición | Destinatario | Plantilla |
|---|---|---|
| borrador → revision | grupo Publicadores | `emails/a_revision.html` — "«{titulo}» espera revisión" + enlace admin |
| revision → publicado | autor (`creado_por`) | `emails/publicado.html` |
| revision → borrador (devuelto) | autor, incluye `nota_revision` | `emails/devuelto.html` |

SMTP de PREDES por `.env` (`EMAIL_HOST…`); en dev, `console.EmailBackend`. Plantillas en `backend/apps/core/templates/emails/` con marca PREDES.

## Importadores (DatasetUpload)

Admin de `DatasetUpload`: form de subida (tipo + archivo) → acción **"Validar e importar"** → tarea en worker. El change list muestra `estado` como badge (subido/validando/procesando/**activo**/reemplazado/error) y el `log` legible (advertencias fila a fila, conteos). Ver contrato de datos en `01-modelo-datos.md`.

| Importador | Archivo | Validaciones clave | Post-import |
|---|---|---|---|
| `nivel_peligro.py` | `Base_Nivel Peligro_CCPP_Cusco.xlsx` | 9 hojas esperadas; columnas exactas; codigo 10 díg; nivel ∈ 1-4 o vacío | upsert de Provincia/Distrito/CentroPoblado + reemplazo atómico de ClasificacionPeligro → `generar_tiles_ccpp` + `meili_rebuild ccpp` |
| `frecuencia.py` | `Base_Frecuencia_Peligro_Cusco.xlsx` | hoja `NºEMERGENCIAS`; resuelve distrito por `nombre_normalizado`; no-matches → log (no aborta) | reemplazo atómico de FrecuenciaEmergencia + TotalDeclaradoEmergencias |
| `inversion.py` | Excel de inversión (formato por definir **cuando el cliente entregue la data**) | por definir | reemplazo del ejercicio correspondiente |

Regla de oro: la importación es **todo-o-nada por dataset** (transacción); si falla, los datos activos previos quedan intactos.

### Qué va al log sin abortar

Auditado contra los archivos reales; el importador debe reconocer estos casos por nombre, no fallar ni silenciarlos (ver los conteos en `01-modelo-datos.md`):

**`nivel_peligro.py`**
- El nombre del peligro sale de la columna `PELIGRO`, **no del título de la hoja** (hoja `Lluvias` → `Lluvias intensas`; `Incendios Forestales` → `Incendios forestales`). El importador mapea hoja → `TipoPeligro` por la tabla del catálogo y avisa si la columna trae un valor inesperado.
- Filas con `PELIGRO` pero sin `NIVEL_PELI` (~229): se descartan con aviso, no se asume nivel 1.
- Filas sin `CODIGO` (2 al final de `Incendios Forestales`): se descartan con aviso.
- Al deduplicar el CCPP entre las 9 hojas hay que **preferir el valor no vacío** en cada campo, no el de la primera hoja (si no, SICUANI se queda sin distrito).
- `Fuente` admite `SIGRID_CENEPRED` y `SINAGERD_CENEPRED`; cualquier otra grafía va al log.

**`frecuencia.py`**
- Distrito del padrón sin fila en el Excel (hoy ACOMAYO) → aviso; el API responderá 404 para ese distrito.
- Distrito con `TOT_*` pero sin desglose (hoy CUSCO) → se guarda en `TotalDeclaradoEmergencias` y se avisa (ADR-D1).
- Subtotal que no cuadra con el desglose (hoy SANGARARÁ, MOLLEPATA) → prevalece el desglose, la diferencia al log.
- `FUENTE` se normaliza (`CENEPRED_SIGRID` → `SIGRID_CENEPRED`) y `TOTAL` se castea desde string.
- `RANGO FECHA` se guarda como texto tal cual, quitando espacios alrededor del guion.

El `log` del `DatasetUpload` es lo que PREDES lee para saber qué corregir en su Excel, así que los mensajes van en español y citan hoja y fila.

## Capas cartográficas

Admin de `CapaCartografica`: subir/reemplazar GeoJSON → acción **"(Re)generar tiles"** → pipeline del spec 05 (recorte a Cusco + tippecanoe). `estado_tiles` como badge; `log_error` visible. El campo `estilo` (JSON) permite cambiar color/grosor sin tocar código: el frontend lo aplica al vuelo. Reemplazar una capa = subir nuevo archivo y regenerar; swap atómico garantiza que el mapa público nunca vea tiles corruptos.

## Integración Gemini (resúmenes de PDF)

- Modelos con soporte: `biblioteca.Documento` y `normativa.Norma` (vía su documento adjunto).
- UI: botón **"Generar resumen con IA"** en el change form (Unfold action) + auto-encolado al guardar si hay PDF (archivo o `url_externa`) y `resumen` vacío.
- Tarea `generar_resumen(model, pk)` en `core/services/gemini.py`:
  1. Obtiene bytes del PDF: FileField directo, o descarga la URL (timeout 30 s, límite 50 MB). Inline si <20 MB; Files API de Gemini si más.
  2. `google-genai`, modelo **`gemini-2.5-flash`**, PDF como input nativo (sin extracción local).
  3. Prompt fijo (es-PE, dominio GRD): *"Eres analista de gestión del riesgo de desastres y adaptación al cambio climático en Perú. Resume este documento en 120–180 palabras, en español claro, para el público del Observatorio Kallpachakuy de PREDES (Cusco): qué es, qué establece o encuentra, y por qué importa para la GRD/ACC regional. Sin viñetas ni encabezados. No inventes datos; si el documento no es legible responde SOLO 'ILEGIBLE'."*
  4. Escribe `resumen` **solo si sigue vacío** (no pisa edición humana), `resumen_generado_por_ia=True`, `ia_estado=ok`. Respuesta "ILEGIBLE" o excepción → `ia_estado=error`, detalle en `log_ia`, mensaje amable en admin ("redáctelo manualmente").
- Timeout 60 s, 1 reintento con backoff. **La publicación nunca depende de Gemini.** `GEMINI_API_KEY` solo en `backend/.env`; jamás llega al frontend. El editor siempre revisa/corrige antes de publicar (humano en el loop).

## Dashboard de métricas (Unfold)

Página de inicio del admin con: visitas últimos 30 días (ResumenDiario), top páginas, búsquedas más frecuentes, descargas de PDF/Excel/documentos, conteos de contenido por estado. Tablas + gráficas simples (componentes de Unfold). Tarea nocturna (cron del worker): agregación a `ResumenDiario` + purga de `EventoUso` > 90 días.

## Pantallas de mantenimiento de textos estáticos

- `BloqueTexto` agrupado por `pagina` en el admin (fieldsets/filtros): el editor encuentra "Portada", "Sobre", "Footer" y edita el texto con rich text.

## Edición de contenido rico (CKEditor 5)

Los cuatro campos rich —`Medida.contenido`, `Norma.contenido`, `Noticia.cuerpo`,
`BloqueTexto.cuerpo`— usan **CKEditor 5** (ADR-D2). Lo que el admin tiene que resolver:

- **Barra acotada.** Encabezados h2–h4 (no h1: ese es el título de la página), negrita, cursiva,
  listas, enlace, cita, tabla, imagen y *media embed*. Cuanto más corta la barra, menos HTML raro
  que sanear y menos formas de romper la maqueta.
- **Subida de imágenes desde el editor**: aterrizan en `media/contenido/%Y/%m/`, con límite de
  tamaño y conversión a un ancho máximo razonable. Una foto de 6 MB subida sin recortar es lo
  normal cuando el editor viene del trabajo de campo.
- **Saneamiento al guardar**, no al mostrar: lista blanca de etiquetas y atributos antes de
  persistir (ver ADR-D2). Vale también para el contenido que llegue por importación.
- **`MedidaImagen` como inline ordenable** en el admin de Medida (Unfold sortable, igual que
  `HeroSlide`), con `pie` obligatorio.
- El editor debe ver que **dejar `imagen_portada` vacía usa la ilustración institucional** del
  peligro de la medida, para que no lo lea como un dato faltante.
- `HeroSlide` con vista previa de imagen y orden drag (Unfold sortable).
- `EnlaceMenu` por zona; **Prioridades existe con `visible=False`** (decisión de reunión — no borrar).
- `ConfiguracionSitio` como singleton (un solo registro editable).
