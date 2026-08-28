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
| **Editor** | Crear/editar contenido propio, **publicarlo y retirarlo** (ADR-P3); subir documentos |
| **Publicador** | Todo lo del editor + borrar, y gestionar datasets y capas |
| **Administrador** | Todo + usuarios, configuración del sitio, menú |

Implementación: permisos custom `puede_publicar` por modelo Workflow. Desde ADR-P3 lo tienen los tres grupos; se conserva porque es lo único que impide publicar a una cuenta de staff **sin grupo**. En Unfold se ocultan las acciones de transición no permitidas — por **permiso, no por estado**: no hay `get_actions` en el proyecto, así que una acción imposible desde el estado actual se ofrece igual y falla con un aviso por objeto.

## Flujo editorial (WorkflowMixin)

Estados: `borrador → publicado`, con `archivado` para retirar sin borrar (ADR-P3; el paso de «revisión» se retiró). Reglas:
- Solo `publicado` aparece en API pública y en Meilisearch.
- Transiciones vía botones de acción en el change form (Unfold actions), **no editando el campo a mano**: un guardado directo no dispara el aviso ni registra quién lo hizo.
- `transicionar()` valida el paso y **encola** el correo (django-tasks, nunca bloquea el request).

### Avisos por correo (requisito TDR)
| Transición | Destinatario | Plantilla |
|---|---|---|
| borrador → publicado | autor (`creado_por`) | `emails/publicado.html` |
| publicado → borrador (retirado) | autor, incluye `nota_revision` | `emails/devuelto.html` |

**No se avisa a quien se avisaría a sí mismo**: desde ADR-P3 el autor suele ser quien publica, y un correo que informa a alguien de lo que acaba de hacer es la forma más rápida de que se dejen de leer los demás. Archivar no genera correo, por lo mismo.

SMTP de PREDES por `.env` (`EMAIL_HOST…`); en dev, `console.EmailBackend`. Plantillas en `backend/apps/core/templates/emails/` con marca PREDES.

## Importadores (DatasetUpload)

Admin de `DatasetUpload`: form de subida (tipo + archivo) → acción **"Validar e importar"** → tarea en worker. El change list muestra `estado` como badge (subido/validando/procesando/**activo**/reemplazado/error) y el `log` legible (advertencias fila a fila, conteos). Ver contrato de datos en `01-modelo-datos.md`.

| Importador | Archivo | Validaciones clave | Post-import |
|---|---|---|---|
| `nivel_peligro.py` | `Base_Nivel Peligro_CCPP_Cusco.xlsx` | 9 hojas esperadas; columnas exactas; codigo 10 díg; nivel ∈ 1-4 o vacío | upsert de Provincia/Distrito/CentroPoblado + reemplazo atómico de ClasificacionPeligro → `generar_tiles_ccpp` + `meili_rebuild ccpp` |
| `frecuencia.py` | `Base_Frecuencia_Peligro_Cusco.xlsx` | hoja `NºEMERGENCIAS`; resuelve distrito por `nombre_normalizado`; no-matches → log (no aborta) | reemplazo atómico de FrecuenciaEmergencia + TotalDeclaradoEmergencias |
| `inversion.py` | Tres formas, distinguidas por su cabecera: Excel del cliente (hoja `Base AAAA`), serie consolidada del programa (CSV) y serie de totales institucionales (CSV) | un solo `Periodo` en el Excel, formato `AAAA-MM`; el CSV tiene que traer las columnas de una de las dos series; el padrón de distritos tiene que existir | reemplazo atómico **por ejercicio y por parte**; descubre códigos nuevos en el catálogo de procesos sin pisar lo editado; **el ejercicio nace oculto** |

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

**`inversion.py`**
- Municipalidad que no casa con el padrón de distritos (hoy 4, creadas en La Convención después del padrón) → aviso. **Cuenta en los totales** y queda marcada «sin territorio» en el admin: descartarla restaría presupuesto en silencio y asignarla a un distrito cualquiera contaminaría cualquier cruce distrital.
- Código de actividad o proyecto que el catálogo no conoce → se añade con la clasificación propuesta y se avisa. Si no hay propuesta, entra **sin proceso** y su importe se muestra como «sin clasificar»: nunca se reparte entre los demás.
- Ejercicio nuevo → se crea **oculto**, con el aviso de dónde se publica. Importar no es publicar.
- Ningún ejercicio visible al terminar → aviso de que la ruta sigue mostrando «información en preparación».

El `log` del `DatasetUpload` es lo que PREDES lee para saber qué corregir en su Excel, así que los mensajes van en español y citan hoja y fila.

### Catálogo de procesos de la GRD

`ClasificacionActividad` es el único catálogo del proyecto que PREDES edita y que el importador también escribe, así que la regla de precedencia es explícita: **al guardarlo desde el admin se desmarca `automatico`, y a partir de ahí ni la semilla ni ninguna importación vuelven a tocar la fila**. El listado filtra por «asignado automáticamente» y por proceso vacío, y hay una acción para marcar como revisadas sin cambiar nada.

No hay ninguna acción de «reprocesar»: el reparto se calcula al vuelo sobre `PresupuestoActividad`, así que un cambio aquí se ve en la web en el siguiente request. La tarjeta del panel avisa de cuánto PIM publicado sigue sin proceso, porque un catálogo a medias no da ningún síntoma salvo una barra «sin clasificar» que nadie mira.

## Capas cartográficas

Admin de `CapaCartografica`: subir/reemplazar GeoJSON → acción **"(Re)generar tiles"** → pipeline del spec 05 (recorte a Cusco + tippecanoe). `estado_tiles` como badge; `log_error` visible. El campo `estilo` (JSON) permite cambiar color/grosor sin tocar código: el frontend lo aplica al vuelo. Reemplazar una capa = subir nuevo archivo y regenerar; swap atómico garantiza que el mapa público nunca vea tiles corruptos.

## Redacción de noticias desde una URL (ADR-D7)

- **Dónde**: bloque «Origen», arriba del todo del formulario de Noticias — `url_origen`, casilla
  **«Procesar con IA»**, insignia de estado y registro.
- **Qué hace**: con la casilla marcada, `titulo`, `slug`, `bajada` y `fecha` dejan de ser
  obligatorios y el registro se guarda al instante con valores provisionales —el `slug` lleva sufijo
  aleatorio para no chocar contra su índice único—. La tarea `redactar_noticia_desde_url` lee la
  página y rellena título, bajada, cuerpo (HTML), tipo, autor, fecha, palabras clave y **la portada**
  desde la `og:image`, reducida al mismo ancho que las del editor.
- **Una sola llamada**, con `response_format` de tipo `json_schema` y todos los campos a la vez.
  Encadenar una llamada por campo multiplicaría por nada el coste del texto de entrada, que es lo
  caro.
- **`provider.require_parameters` siempre.** OpenRouter enruta cada petición por separado y del mismo
  modelo hay proveedores sin salida estructurada; sin fijarlo la función falla de forma intermitente.
  Y `razonamiento=False`: extraer campos no mejora razonando y sí se paga.
- **El candado es por registro** (`redactada_por_ia`) y **solo se cierra si se llegó a escribir**. Un
  fallo deja `ia_estado=error` con el motivo y permite reintentar. En la ficha ya redactada la
  casilla llega `disabled`, así que tampoco se salta por POST.
- **Nunca pisa una edición humana**: la tarea recarga desde la base justo antes de escribir. Cuidado
  con los campos que tienen default (`tipo`, `fecha`): ahí «¿está lleno?» no distingue elección de
  default y hay que decidirlo campo a campo.
- **La ficha se refresca sola**: un JS sondea `<ADMIN_URL>contenidos/noticia/<pk>/estado-ia/` cada
  2 s mientras el estado es «procesando» y recarga al terminar, con corte a los 3 minutos. Esa ruta
  va **antes** de `admin.site.urls` en `config/urls.py`, o el `catch_all_view` del AdminSite
  responde 404 y el refresco deja de funcionar sin que nada más falle.
- **Seguridad de la descarga**: solo `http`/`https`, y se resuelve el nombre para rechazar destinos
  internos. La URL la escribe un editor y la petición la hace el servidor.
- **Registro**: cada intercambio (entrada y salida) va a un `.txt` diario en `IA_LOGS_DIR`, **fuera
  de `MEDIA_ROOT`** porque nginx sirve `/media/` entero como estático público. Sin rotación.
- **El editor revisa siempre.** El `log_ia` de cada ficha lo recuerda, y avisa además de los derechos
  de la imagen: viene de un sitio ajeno.

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

Además, **tarjeta «Buscador»** (`meili.estado_indices()`): si el servicio responde y, por índice, documentos indexados frente a publicados. Es la única forma que tiene PREDES de enterarse de un índice desfasado, que no da ningún otro síntoma que «lo publicado no aparece al buscarlo» (ver 04). Con un botón **Reindexar la búsqueda** que encola `core.tasks.reindexar_meili` —encolar y no ejecutar: reconstruir `ccpp` son ~16 s y 8.968 documentos—, en `apps/core/vistas_admin.py`, con `staff_member_required` + `require_POST`.

### Imágenes insertadas desde el editor

Van por `apps.core.almacenamiento.AlmacenamientoContenido` (`CKEDITOR_5_FILE_STORAGE`), que hace dos cosas que la librería no hace:

- **Las guarda en `contenido/%Y/%m/`.** `django-ckeditor-5` **ignora `CKEDITOR_5_UPLOAD_PATH`** —guarda con `fs.save(f.name, f)`, sin prefijo—, así que sin el storage caían en la raíz de `media/`. El ajuste lo aplica ahora nuestro storage, y el prefijo se resuelve en cada guardado (fijarlo en `location` lo congelaría al arrancar el proceso: un gunicorn de julio escribiría en `07/` en agosto).
- **Reduce el ancho a `CONTENIDO_ANCHO_MAXIMO_PX`** (1.600 px) y corrige la orientación EXIF. Ese ajuste existía y **no se usaba en ningún sitio**: una foto de campo de 4.000 px y 4,3 MB se servía tal cual. Medido tras el arreglo: 513 KB y 1.600 px. No toca GIF ni TIFF (Pillow pierde la animación), no recomprime lo que ya cabe (se escribe byte por byte) y si Pillow falla guarda el original — perder la foto de alguien sería peor que servirla grande.

**Solo aplica a las imágenes del editor.** Las de los campos de imagen del formulario (portadas, galería de medidas, hero) se guardan tal cual, cada una con su `upload_to`.

> **Todo lo que se monte bajo `ADMIN_URL` va ANTES de `admin.site.urls`.** `AdminSite` termina sus URLs con un `catch_all_view` que casa con cualquier cosa bajo su prefijo y responde 404, así que una ruta declarada después nunca se alcanza. La subida de imágenes de CKEditor estuvo así y devolvía 404 sin decirlo; hay prueba de regresión en `tests/test_urls_admin.py`.

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
  persistir (ver ADR-D2). Vale también para el contenido que llegue por importación, y por eso vive
  en **`HtmlRicoMixin.save()`** del modelo (con `campos_html`) y no en el admin: mientras estuvo en
  `WorkflowAdmin.save_model`, cualquier escritura que no pasara por el formulario —un `loaddata`, un
  script— metía el HTML sin filtrar, aunque el `help_text` del campo prometiera lo contrario. El
  `campos_rich` del admin queda solo para elegir el widget de CKEditor.
- **`MedidaImagen` como inline** en el admin de Medida, con `pie` obligatorio y campo `orden`.
- El editor debe ver que **dejar `imagen_portada` vacía usa la ilustración institucional** del
  peligro de la medida, para que no lo lea como un dato faltante.
- `HeroSlide` con vista previa de imagen y `orden` editable en la lista. Pasa por el mismo flujo
  editorial que el contenido, así que un slide se retira **archivándolo**.
- `EnlaceMenu` por zona; **Prioridades existe con `visible=False`** (decisión de reunión — no borrar).
- `ConfiguracionSitio` como singleton (un solo registro editable).
