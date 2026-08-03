# 08 — Plan de pruebas

Qué se prueba, con qué, y cuándo se considera que la plataforma está lista para entregar. La regla que ordena el documento: **cada caso de prueba obligatorio nace de una anomalía verificada en los datos reales o de una decisión de arquitectura que se puede romper en silencio**. No se persigue cobertura por cobertura.

## Herramientas

| Nivel | Herramienta | Dónde | Qué cubre |
|---|---|---|---|
| Unitario / integración | **pytest + pytest-django** | `backend/tests/` | Importadores, contrato del API, flujo editorial, seed, emisor de tiles |
| Extremo a extremo | **Playwright** | `e2e/` | Las rutas críticas en navegador real contra el stack de compose |
| Tipos y build | `tsc --noEmit` + `vite build` | `frontend/` | Que el frontend compila antes de cada commit |

Comandos:

```bash
DC="docker compose -f compose.yaml -f compose.dev.yml"

$DC exec backend pytest                 # suite backend (112 pruebas, ~35 s)
$DC exec backend pytest -m lento        # los Excel completos y el PDF con mapa (~35 s más)
cd frontend && npm run lint && npm run build    # tipos + build
npx playwright test                             # E2E contra el stack levantado
E2E_URL=http://localhost npx playwright test    # E2E contra el bundle servido por nginx
```

`pytest` corre **dentro del contenedor** para usar las mismas versiones de GDAL, tippecanoe y WeasyPrint que producción. La imagen de `compose.dev.yml` se construye con `GRUPOS_UV=--group dev`, que es lo que instala pytest; tras cambiar esa opción hace falta `up -d --renew-anon-volumes backend`, porque `/app/.venv` es un volumen anónimo que sobrevive a la reconstrucción.

## Datos de prueba

Los Excel reales pesan 5.4 MB y tardan; las pruebas usan **muestras reducidas** en `backend/tests/datos/`, generadas por `generar_muestras.py` (que también se versiona, para poder rehacerlas cuando el cliente actualice sus archivos):

| Archivo | Contenido |
|---|---|
| `nivel_peligro_muestra.xlsx` | 4 hojas (`Sismo`, `Lluvias`, `Inundación`, `Incendios Forestales`) × ~40-70 filas: las dos discrepancias hoja/columna, SICUANI con `DISTRITO` vacío en una hoja, filas sin `NIVEL_PELI`, 2 huérfanas sin `CODIGO`, y las dos grafías de `Fuente` |
| `frecuencia_muestra.xlsx` | Hoja `NºEMERGENCIAS` con OLLANTAYTAMBO (desglose normal), CUSCO (solo `TOT_*`), SANGARARÁ y MOLLEPATA (descuadres), ACOPIA (fila vacía), y sin la fila de ACOMAYO |

**Las dos muestras tienen que ser consistentes entre sí.** El importador de frecuencia resuelve el distrito **por nombre** contra el padrón que dejó el de niveles: si la muestra de niveles no trae ningún centro poblado de OLLANTAYTAMBO, su fila de emergencias se omite con aviso y las pruebas de ADR-D1 pasan sin comprobar nada. El generador lo garantiza forzando un CCPP de cada distrito de `DISTRITOS_FRECUENCIA`, y avisa si no lo encuentra.

Las pruebas contra los archivos completos existen y van marcadas `@pytest.mark.lento`; quedan fuera de la corrida por defecto y se saltan solas si `data/layers/` no está.

## Casos obligatorios — backend

### `test_importadores.py`

Salen de la auditoría del 02/08 documentada en 01 y 03. Cada uno protege una decisión que un refactor puede deshacer sin que nada falle a la vista:

1. **ADR-D1**: CUSCO (080101) se importa en `TotalDeclaradoEmergencias` con `total=134` y **no** genera filas de `FrecuenciaEmergencia`. Es el caso que motivó el ADR: recalcular desde el desglose deja la capital regional en cero.
2. El peligro sale del **catálogo canónico**, no del título de la hoja: `Lluvias` → `Lluvias intensas`/`lluvias_intensas`, `Incendios Forestales` → `Incendios forestales`/`incendios_forestales`. Se comprueba además que no exista ningún tipo con el nombre de la hoja ni con el slug que produciría `slugify()` sobre él.
3. **Slugs con guion bajo**: ningún `TipoPeligro.slug` contiene `-`. Es la clave de las propiedades `nivel_<slug>` del tile; con guion el mapa deja de pintar y ninguna otra prueba lo nota.
4. Filas con `PELIGRO` pero sin `NIVEL_PELI` se descartan y quedan contadas en el `log`; no se asume nivel 1.
5. Filas sin `CODIGO` se descartan con aviso. Un `PELIGRO` fuera del catálogo se descarta citando hoja y fila.
6. Al deduplicar CCPP entre hojas se prefiere el valor no vacío: SICUANI conserva su distrito.
7. `CENEPRED_SIGRID` se normaliza a `SIGRID_CENEPRED`, y `2003 - 2022` a `2003-2022` sin reinterpretar el periodo.
8. Descuadre entre subtotal y desglose (SANGARARÁ): prevalece el desglose y la diferencia queda en el `log`.
9. Distrito del padrón sin fila en el Excel: aviso en el `log`, la importación no aborta. Con la muestra se prueba la política; el caso nominal de ACOMAYO va en las pruebas `lento`.
10. **Fila presente y enteramente vacía** (ACOPIA, y 21 distritos en el archivo real): es un tercer estado, distinto de «declara subtotales sin desagregar» y de «declara cero». Se cuenta en `distritos_sin_dato` con su propio aviso. Hasta que esta prueba se escribió, esos 21 distritos recibían el aviso de ADR-D1, que dice otra cosa, y quedaban indistinguibles del único que no tiene fila.
11. **Todo-o-nada**: un Excel con una hoja corrupta deja los datos activos previos intactos y el `DatasetUpload` en `error`. Un archivo sin hojas conocidas, y uno sin la hoja `NºEMERGENCIAS`, fallan citando lo que falta.
12. Reimportar reemplaza en vez de duplicar: dos importaciones seguidas del mismo archivo dan los mismos conteos, la anterior queda `reemplazado` y el padrón de centros poblados **no se borra** (medidas y frecuencias lo referencian).
13. `inversion_mef` no tiene importador (ADR-D3) y lo dice con un mensaje explícito, no con un `error` mudo.

### `test_api_peligros.py`, `test_api_editorial.py`, `test_api_sitio.py`

Un módulo por familia. El criterio es el **contrato del spec 02**, no la implementación:

- Forma exacta del payload de `/api/ccpp/{codigo}/`, `/api/peligros/resumen/` y `/api/peligros/frecuencia/`.
- **Las dos unidades del resumen cuadran cada una con su consulta**: `por_ccpp` con los centros poblados contados una vez y `por_peligro` con las clasificaciones. Es la prueba que habría cazado el «225 donde hay 75» de Acomayo.
- **`peligro` y `nivel_min` anotan pero no recortan**: sin `clasificados=1` la respuesta trae los 8,968 puntos con `nivel` en unos y `null` en otros, porque el mapa los pinta todos. Se fijan las dos semánticas juntas para que nadie «arregle» una rompiendo la otra.
- Los dos filtros se aplican **como una sola condición de join**, no en dos pasos.
- `desglose_disponible: false` y `solo_total: true` para CUSCO; `true`/`false` para OLLANTAYTAMBO.
- **404 para un distrito sin dato** frente a `total: 0` para uno con fila y sin emergencias.
- **El listado de frecuencia trae los distritos de las dos tablas**, incluidos los 26 que solo declaran subtotales. Consultar solo `FrecuenciaEmergencia` los dejaba fuera —Cusco incluido— mientras el detalle sí los servía.
- El export de frecuencia **respeta los filtros también para los declarados**: filtrado por un distrito no puede traer los declarados de toda la región.
- `clasificaciones: []` para un CCPP sin clasificar — «sin dato» no es «nivel bajo».
- Solo se sirve `estado=publicado`: un objeto en borrador, en revisión o archivado no aparece en listado, detalle (404, no 403) ni export.
- Paginación (`page_size` default 50, máximo 200) y filtros de cada endpoint; `?tema=` por coincidencia exacta y no parcial.
- Throttling de exports y PDF (`30/hour`). **Se parchea la clase, no el ajuste**: DRF liga `THROTTLE_RATES` al diccionario de `api_settings` cuando se define la clase, así que sobrescribir `REST_FRAMEWORK` no llega a las clases ya importadas y la prueba pasa o falla según el orden de los módulos.
- `/api/inversion/` responde `{"disponible": false, "motivo": …}`, y el comparador `inversion_disponible: false`.
- `/api/sitio/` trae config, bloques, menú y hero; omite los `EnlaceMenu` con `visible=False` (Prioridades) y **sí** anuncia Inversión; el hero solo muestra slides publicados; y responde con `Cache-Control`.
- `/api/mapas/capas/` solo anuncia capas con `estado_tiles=ok`, con URL absoluta y estilo de MapLibre.
- El comparador exige entre 2 y 4 distritos y avisa de un ubigeo inexistente.
- La búsqueda de DRF agrupa por tipo, no devuelve el catálogo con `q` vacío, y `/api/buscar/estado/` no ofrece índices cuando Meilisearch no responde.
- El beacon de métricas acepta `form-encoded`, responde 204, **no guarda PII**, y su `session_hash` lleva la fecha dentro (se reconstruye el hash para demostrarlo, en vez de viajar en el tiempo).
- `imagen_portada` llega **resuelta** por el serializer cuando el campo está vacío: la regla del default institucional vive en el backend y ningún cliente la replica.

### `test_informes.py`

- El PDF se genera de verdad (`%PDF`), con nombre que identifica el distrito, y **para un distrito sin datos de emergencias también**: si fallara ahí, los distritos con vacíos de información serían los únicos sin ayuda memoria.
- El PDF lee de **las mismas consultas** que el API, comparando cifra a cifra: es la única forma de garantizar que el papel no contradice a la pantalla.
- Los filtros del visor llegan al documento y se imprimen en él.
- Con el mapa (Chromium) también sale, marcado `lento`. Su fallo es una degradación prevista, no un error.

### `test_workflow.py`

- Transiciones válidas e inválidas de `WorkflowMixin.transicionar()` (`borrador → publicado` directo debe fallar).
- Cada transición encola su correo con el destinatario correcto: a revisión → grupo Publicador; publicado → autor; devuelto → autor **con la `nota_revision` en el cuerpo**, que es el único sitio donde se le explica qué corregir. Archivar no genera correo: un aviso que se ignora deja de ser un aviso.
- Se ejecuta la tarea real con sus argumentos reales, leídos de la cola de django-tasks.
- Sin destinatarios la transición sigue adelante: un buzón mal configurado no puede impedir publicar.
- `publicado_en` se sella al publicar y `revisado_por` queda registrado.
- Un editor no puede publicar lo que escribió, ni ve la acción; un superusuario sí, sin estar en el grupo.
- **El HTML se sanea en `save()`**, no en el admin: `HtmlRicoMixin` con `campos_html`. Mientras vivió en `WorkflowAdmin.save_model`, cualquier escritura que no pasara por el formulario —un `loaddata`, un script— metía el HTML sin filtrar, aunque el `help_text` del campo prometiera lo contrario. Se conserva `<oembed>`, que es cómo CKEditor 5 representa un video.

### `test_seed.py`

- Idempotencia: `seed` corre en **cada despliegue**, así que no puede pisar los textos que PREDES haya editado. El catálogo de peligros es la excepción deliberada —es código, no contenido— y sí se restaura.
- Grupos con sus permisos y con los nombres exactos de `core.grupos`; Prioridades oculta y no borrada.
- Conteos canónicos tras `manage.py seed` sobre los Excel reales (marcado `lento`): **13 provincias · 112 distritos · 8,968 CCPP · 3,238 clasificados · 5,730 sin dato · 10,978 clasificaciones · 644 frecuencias en 64 distritos · 104 totales declarados en 26 distritos**. Si un refactor del importador pierde filas, esta prueba es la que lo dice.
- Las anomalías conocidas siguen reportándose (229 sin nivel, 2 sin código, ACOMAYO sin fila, 21 con fila vacía, 90 con datos). **Las advertencias son un entregable**: son lo que PREDES le lleva a la fuente de los datos, así que silenciarlas es perder trabajo del cliente, no mejorar el importador.

### `test_tiles.py`

- El emisor de GeoJSONSeq **omite** las claves `nivel_*` ausentes en vez de escribir `null` (es lo que mantiene el tile en 3 MB y «sin dato» como categoría propia).
- Las claves emitidas coinciden exactamente con los slugs de `TipoPeligro`, con guion bajo.
- `nivel_max` es el máximo de los niveles presentes.
- Cada feature lleva lo que el popup necesita —se pinta **desde el tile**, sin pedir nada al API— y `poblacion` va como entero: con `null`, MapLibre descarta el punto al interpolar el radio.

## Casos obligatorios — E2E (Playwright)

Corren contra el stack de compose ya sembrado, en dos proyectos: **escritorio** y **móvil** (Pixel 5), porque el TDR pide que el sitio sirva en campo y en campo se entra desde el teléfono. 45 pruebas, ~1 min.

| Spec | Comprueba |
|---|---|
| `peligros.spec.ts` | El mapa **pinta de verdad** (se leen los píxeles del canvas: uno en blanco pasa cualquier `toBeVisible`) · las cifras de distribución salen del resumen del servidor y no de las filas cargadas · la tabla dice cuántos CCPP quedan sin clasificación · filtrar por peligro y nivel reduce la tabla · la ficha del CCPP abre desde la tabla · la ayuda memoria descarga un PDF · el selector de mapa base conmuta sin errores |
| `home.spec.ts` | Las cifras salen del API y **coinciden** con `/api/peligros/resumen/` · ninguna se queda en el marcador de carga · el cascarón viene de `/api/sitio/` · Prioridades no aparece · el bloque de actualidad enlaza a contenido real · una ruta inventada da el 404 del sitio y no el de nginx (prueba el `try_files`) |
| `buscar.spec.ts` | Una búsqueda devuelve resultados agrupados · **cuando Meilisearch está disponible se usa Meilisearch** · con él inalcanzable el fallback de DRF responde igual · una consulta sin resultados lo dice y ofrece a dónde ir |
| `medidas.spec.ts` | El listado sale del API y cada tarjeta tiene imagen (el default lo resuelve el servidor) · el filtro manda el **slug** al API y recorta · la ficha abre con su contenido · una medida inexistente no deja la página en blanco · los chips de tema llevan al listado recortado |
| `inversion.spec.ts` | Se muestra el estado vacío «información en preparación», **no un cero ni un gráfico en blanco** · la sección sigue anunciada en el menú (diferida no es oculta) |

Tres convenciones que la suite impone desde `e2e/apoyo.ts` y `e2e/fixtures.ts`:

1. **Se vigila la consola.** Un error de JavaScript no rompe la página de forma visible —React sigue pintando lo que puede—, así que sin esto se puede dar por bueno un visor que perdió su capa de puntos.
2. **El beacon de métricas se descarta.** El tráfico de las pruebas no es uso real y no debe acabar en el panel del admin.
3. **Los enlaces del menú se buscan con `:visible`.** Existen dos veces —nav de escritorio y panel móvil— y solo una se muestra según el ancho; `.first()` cae siempre en la de escritorio.

**La corrida contra nginx no es opcional.** `E2E_URL=http://localhost npx playwright test` sobre `compose.local.yml` es lo que destapó que el proxy `/search/` mandaba todas las peticiones a la raíz de Meilisearch: en desarrollo el navegador ataca a Meilisearch directamente y el fallo no existe.

## Comprobaciones manuales (previas a la entrega)

Automatizarlas no sale a cuenta, pero omitirlas sí:

1. **Restauración de backup**: compose limpio + `psql < dump` + `meili_rebuild` + visor OK. Se cronometra y el tiempo se documenta en `_docs/despliegue.md`. El TDR pide backups; un backup no probado no es un backup.
2. **Ciclo completo de administración**, tal como lo hará PREDES: subir el Excel → ver el cambio en el visor → crear una medida → enviarla a revisión → publicarla → verla en el sitio.
3. **Reemplazo de una capa cartográfica** y regeneración de tiles desde el admin.
4. **Impresión de la ayuda memoria** en vista previa de impresión, no solo la descarga.
5. **Responsive y accesibilidad** en las rutas principales (criterios de `archive/02-navegacion-ux.md`).

## Lo que encontró esta suite

Se anota porque es el argumento de por qué la fase existe. Ninguno de estos fallos rompía nada a la vista: en los cinco casos el sistema respondía 200 y la pantalla se veía bien.

| Hallazgo | Cómo se manifestaba |
|---|---|
| El proxy `/search/` llevaba **todo** a la raíz de Meilisearch (una variable en `proxy_pass` desactiva la sustitución del prefijo) | El buscador caía al fallback de DRF en cada búsqueda: sin facetas ni tolerancia a errores de tecleo. `GET /search/health` respondía 200 porque la raíz de Meili también responde 200 |
| El listado de frecuencia omitía los 26 distritos que solo declaran subtotales | Cusco no salía en la tabla y sí en su ficha: el sitio se contradecía consigo mismo |
| El export de frecuencia ignoraba los filtros al añadir los declarados | El Excel de un distrito traía los declarados de toda la región |
| El saneado de HTML vivía solo en el admin | El `help_text` del campo prometía «se sanea al guardar» y cualquier escritura fuera del formulario lo metía sin filtrar |
| 21 distritos con fila vacía recibían el aviso de ADR-D1 | Un vacío de información quedaba escondido detrás de un mensaje que dice otra cosa |
| El límite del beacon (60/min por IP) | Una oficina detrás de un NAT lo agota; las métricas se pierden en silencio |

Y dos cosas que las pruebas mismas enseñaron: que las dos muestras de Excel tienen que ser consistentes entre sí (si no, las pruebas de ADR-D1 pasan sin comprobar nada), y que los `<select>` del visor no tenían rótulo accesible.

## Criterio de "listo para entregar"

- `pytest` completo (incluido `-m lento`) en verde: 112 + 4 pruebas.
- `npm run lint && npm run build` sin errores.
- `npx playwright test` en verde **dos veces**: contra el dev server y contra el bundle servido por nginx (`E2E_URL=http://localhost`). La segunda es la que vale.
- Las cinco comprobaciones manuales hechas y documentadas.
- Los conteos canónicos verificados sobre la base de producción tras el seed real.
