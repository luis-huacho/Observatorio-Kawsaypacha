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

$DC exec backend pytest                 # suite backend (259 pruebas, ~30 s)
                                        # la cifra sale de `pytest --collect-only -q`, no de la memoria
$DC exec backend pytest -m lento        # 7 más: los Excel completos y el PDF con mapa (~35 s)
cd frontend && npm run lint && npm run build    # tipos + build
./e2e/instalar-dependencias.sh                  # una sola vez por máquina (ver abajo)
npx playwright test                             # E2E contra el stack levantado
E2E_URL=http://localhost npx playwright test    # E2E contra el bundle servido por nginx
```

**`instalar-dependencias.sh` no es un `npm install` con otro nombre.** Instala además las librerías
de sistema de Chromium, que es el paso que faltaba en esta lista hasta el 04/08/2026 y el que
rompe: Playwright **no soporta oficialmente la familia RHEL**, así que en Rocky/Fedora descarga el
binario de Ubuntu y no instala ninguna dependencia —solo sabe de `apt`—. La suite entera falla con
`browserType.launch: Target page, context or browser has been closed`, que parece el sitio caído
y es una `.so` ausente. El script termina arrancando el navegador, para que eso salga en dos
segundos en vez de tras seis minutos de suite.

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
13. **Inversión** (`inversion_mef`): las dos series entran y se distinguen por su cabecera; **cargarlas en cualquier orden deja el mismo resultado** (ninguna borra lo que no trae —la institucional no lleva geografía, la del programa no lleva el total institucional—); reimportar no duplica; el catálogo se descubre solo pero un código desconocido queda **sin proceso** y se declara; una municipalidad fuera del padrón cuenta en los totales y se avisa; **importar no publica**; el corte parcial y su fuente se marcan por ejercicio; un archivo que no es ninguna de las tres formas falla citando lo que falta; y **un archivo que incumple `0 ≤ devengado ≤ PIM` se rechaza entero** —el SIAF bloquea devengar por encima del PIM, así que un archivo así está mal en origen— enumerando las filas malas en un solo mensaje y sin escribir nada.

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
- **Paginación y ranking del listado** (`test_api_inversion.py`): forma y techo del sobre; **orden estable entre páginas** —recorrerlas de una en una tiene que dar cada municipalidad exactamente una vez, que es el fallo que el desempate por código existe para evitar y no se ve a simple vista—; cada clave de `ordenar` ordena de verdad con los nulos al final; `buscar` recorta por nombre.
- **Comparación entre ejercicios**: los deltas cuadran a mano; `comparable` es `false` con cortes distintos; una entidad sin presupuesto el otro año da deltas `null` y no cero; comparar un ejercicio consigo mismo se ignora; el Excel comparado lleva la columna «Comparabilidad» en cada fila.
- **Ficha de una municipalidad**: la serie trae un punto por ejercicio publicado y **omite** aquellos sin presupuesto; las actividades suman exactamente el PIM de la entidad; una entidad sin territorio se sirve igual; un código inexistente responde 404.
- `/api/inversion/` (`test_api_inversion.py`): sin ejercicio visible responde `{"disponible": false, "motivo": …}`; **un año oculto no cae al último visible**; los derivados de una entidad cuadran a mano (saldo, variación PIA-PIM, % de ejecución, % sobre el institucional); un porcentaje sin denominador es `null` **y no 0**; el agregado sobre el institucional **solo suma entidades comparables**; el ámbito municipal deja fuera al gobierno regional; el reparto por procesos **sale del catálogo vigente** —editarlo cambia la respuesta sin reimportar— y lo no clasificado se declara aparte y cuadra con el total; el export lleva el corte en cada fila, y sin datos explica por qué. El comparador declara `inversion_disponible`.
- **El reporte PDF** (`test_informes.py`): se genera de verdad; **sale de `inversion.consultas`**, no de una consulta paralela; **el total de la tabla es el agregado del ámbito** —dos caminos distintos a la misma cifra, y sin esta prueba una contradicción dentro de la misma página no se vería sin sumar 116 filas a mano—; declara el importe que su mapa no pinta (ADR-D6, que en papel no tiene pantalla que lo compense); avisa del corte parcial; acotar por provincia recorta tabla **y** total a la vez; una métrica inventada cae a la de por defecto; y sin ejercicio publicado responde **200 con un PDF que explica el vacío**, no 404. Marcadas `lento`: con Chromium el reporte **trae** su mapa (≥1 imagen rasterizada) y sin él **ninguna** — lo segundo demuestra además que las gráficas son vectoriales.
- **Los visores headless** (`test_informes.py`): cada uno **conserva todos sus filtros** en la URL que pide —el autoescape de Django convertía `&` en `&amp;` y del segundo parámetro en adelante se perdían todos, dejando la ayuda memoria con un mapa sin filtrar bajo una línea que listaba los filtros— y **un valor con comillas no se sale de la cadena de JavaScript**, que es lo que impide que quitar el escapado abra una inyección.
- **Los gráficos SVG** (`test_graficos.py`, sin base de datos ni navegador): una serie vacía dice «sin datos» en vez de dejar un hueco mudo; todo a cero no revienta ni produce barras infinitas; la barra apilada reparte en proporción y con total cero no dibuja un reparto inventado; los importes se abrevian; las etiquetas se escapan.
- **El mapa** (`/api/inversion/mapa/`): a nivel distrital solo pinta lo atribuible y ninguna fila se repite; **la suma de lo pintado más `no_ubicado` es exactamente el total del ámbito, a los dos niveles** —son las dos pruebas que hacen cumplir ADR-D6, y existen porque un mapa al que le falta dinero se ve idéntico a uno correcto—; las cuatro métricas viajan en cada fila y el saldo y el % cuadran a mano; una municipalidad con PIM cero tiene `pct_ejecucion: null`; un ámbito sin geografía posible devuelve `filas: []` **con motivo** en vez de un mapa en blanco; los cortes son cuatro y no decrecen ni con dos filas; `provincia` acota; sin ejercicio visible, el mismo estado vacío que el resto de la ventana.
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
- **El visor de la captura pide sus datos a su propio origen**: las URL del contexto son relativas y no llevan `BACKEND_URL`, que se pone a un host inalcanzable en la prueba precisamente para que se note. Es la prueba que faltaba: con `BACKEND_URL` ahí, el documento salía **sin mapa** en producción local y en desarrollo funcionaba por casualidad.
- **Con el mapa (Chromium) el PDF trae el mapa**, marcado `lento`: se cuentan las imágenes rasterizadas del PDF (el mapa es la única; el logotipo es vectorial) y se exige ≥ 1, con su contraparte que comprueba que con `sin_mapa=1` no hay ninguna. La versión anterior de esta prueba solo comprobaba que el PDF se generara y **toleraba que viniera sin mapa**, así que el fallo de arriba le era invisible: la degradación prevista tapaba el defecto. La degradación se sigue probando, pero en su propia prueba.

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
- Grupos con sus permisos y con los nombres exactos de `core.grupos`; Prioridades oculta y no borrada, y el comparador sembrado fuera del menú (ADR-P2) con sus dos enlaces intactos.
- Conteos canónicos tras `manage.py seed` sobre los Excel reales (marcado `lento`): **13 provincias · 112 distritos · 8,968 CCPP · 3,238 clasificados · 5,730 sin dato · 10,978 clasificaciones · 644 frecuencias en 64 distritos · 104 totales declarados en 26 distritos**. Si un refactor del importador pierde filas, esta prueba es la que lo dice.
- Las anomalías conocidas siguen reportándose (229 sin nivel, 2 sin código, ACOMAYO sin fila, 21 con fila vacía, 90 con datos). **Las advertencias son un entregable**: son lo que PREDES le lleva a la fuente de los datos, así que silenciarlas es perder trabajo del cliente, no mejorar el importador.

### `test_meili_estado.py` y `test_urls_admin.py`

- El desfase del índice **se detecta**: un índice con más o menos documentos que la base se señala sin
  arrastrar a los demás, y el comando sale con código ≠ 0 diciendo cómo arreglarlo.
- **El conteo no puede volver a salir de `numberOfDocuments`**: el cliente falso no expone
  `get_all_stats`, así que usarlo rompe las pruebas. Ese conteo está cacheado —tras vaciar un índice
  sigue informando del valor anterior— y con él la comprobación fallaba justo en el caso que existe
  para detectar. Se descubrió vaciando un índice de verdad, no leyendo el diff.
- Un índice que **no existe** se distingue de uno **vacío**: lo primero significa que `meili_setup` no
  ha corrido en esa instancia.
- Meilisearch caído → `disponible: False` **sin excepción**, y la portada del admin sigue abriendo.
- **`resolve()` de las rutas que cuelgan del prefijo del admin no cae en `catch_all_view`.** Es la
  prueba de regresión del 404 de la subida de imágenes del editor, y tiene que mirar *a qué vista
  resuelve*: un 404 del catch-all y uno legítimo son indistinguibles desde fuera.
- El botón de reindexar: sin sesión de staff no hace nada, por `GET` responde 405, y por `POST`
  **encola** la tarea (no la ejecuta) y vuelve al panel con su aviso.

### `test_almacenamiento.py`

Las imágenes del editor, y **los dos ajustes que no hacían nada** hasta que se escribieron estas pruebas:
caen en `contenido/<año>/<mes>/`; una de 3.000 px sale con 1.600 y pesando menos; una que ya cabe se
escribe **byte por byte** (recomprimir «por si acaso» degrada sin ganar nada); un GIF no se toca
(Pillow le quita la animación); una foto con `Orientation` sale derecha; un nombre con `../` no escapa
de la carpeta; y un archivo que no es imagen **no rompe la subida**.

### `test_tiles.py`

- El emisor de GeoJSONSeq **omite** las claves `nivel_*` ausentes en vez de escribir `null` (es lo que mantiene el tile en 3 MB y «sin dato» como categoría propia).
- Las claves emitidas coinciden exactamente con los slugs de `TipoPeligro`, con guion bajo.
- `nivel_max` es el máximo de los niveles presentes.
- Cada feature lleva lo que el popup necesita —se pinta **desde el tile**, sin pedir nada al API— y `poblacion` va como entero: con `null`, MapLibre descarta el punto al interpolar el radio.

## Casos obligatorios — E2E (Playwright)

Corren contra el stack de compose ya sembrado, en dos proyectos: **escritorio** y **móvil** (Pixel 5), porque el TDR pide que el sitio sirva en campo y en campo se entra desde el teléfono. **56 casos, que Playwright ejecuta 112 veces** —uno por proyecto—, ~1.4 min. `npx playwright test --list` cuenta lo segundo: al escribir una cifra aquí hay que decir cuál de las dos es, o la siguiente persona la «corrige» a la otra.

| Spec | Comprueba |
|---|---|
| `peligros.spec.ts` | El mapa **pinta de verdad** (se leen los píxeles del canvas: uno en blanco pasa cualquier `toBeVisible`) · las cifras de distribución salen del resumen del servidor y no de las filas cargadas · la tabla dice cuántos CCPP quedan sin clasificación · filtrar por peligro y nivel reduce la tabla · la ficha del CCPP abre desde la tabla · la ayuda memoria descarga un PDF · el selector de mapa base conmuta sin errores |
| `home.spec.ts` | Las cifras salen del API y **coinciden** con `/api/peligros/resumen/` · ninguna se queda en el marcador de carga · el cascarón viene de `/api/sitio/` · Prioridades no aparece · el bloque de actualidad enlaza a contenido real · una ruta inventada da el 404 del sitio y no el de nginx (prueba el `try_files`) |
| `buscar.spec.ts` | Una búsqueda devuelve resultados agrupados · **cuando Meilisearch está disponible se usa Meilisearch** (mirando el status, no la llamada) · con él inalcanzable el fallback de DRF responde igual · una consulta sin resultados lo dice y ofrece a dónde ir · la **«X» vacía la caja sin cancelar la búsqueda**: no toca la URL, no relanza la consulta, no pierde los resultados y devuelve el foco · el buscador de lugares del visor sugiere y se vacía con su «X» |
| `medidas.spec.ts` | El listado sale del API y cada tarjeta tiene imagen (el default lo resuelve el servidor) · el filtro manda el **slug** al API y recorta · la ficha abre con su contenido · una medida inexistente no deja la página en blanco · los chips de tema llevan al listado recortado |
| `inversion.spec.ts` | Según lo que responda el API del entorno: con ejercicio publicado se dibuja el tablero (KPIs, PIA→PIM→devengado, procesos de la GRD, tabla de **municipalidades** y aviso del corte parcial); sin él, el estado vacío, **no un cero ni un gráfico en blanco** · el ranking **ordena de verdad** por su columna, que con 116 filas no se nota a ojo · la tabla **se pagina** y «Ver 50 más» trae más filas · la ficha se abre y **el ejercicio elegido sobrevive al volver** · una municipalidad inexistente no deja la página en blanco · comparar ejercicios **advierte** cuando los cortes no son comparables · la sección sigue anunciada en el menú · **el cuadro de evolución** trae una fila por ejercicio publicado y marca el corte parcial · **el visor declara el dinero que no puede pintar** y a nivel provincial ese pie desaparece, porque a ese nivel no queda nada fuera · **el reporte en PDF se ofrece y se descarga de verdad**, y su enlace arrastra `nivel` y `metrica`; se afirma sobre la **respuesta HTTP** (`%PDF` y `content-type`) y no sobre el visor de PDF del navegador, que sería una dependencia ajena al fallo que importa. Del mapa se afirma sobre **la leyenda y el pie**, que son DOM real: el canvas de MapLibre no se inspecciona, porque un `expect` sobre píxeles falla por razones que no son el fallo que importa. **Tres trampas del propio spec**: `esperarApi` casa por subcadena, así que `/api/inversion/` atrapa la respuesta de `/api/inversion/entidades/`; la espera hay que armarla **antes** de `goto`, porque la respuesta puede llegar antes del `load`; y desde que existe el cuadro de evolución **hay dos `<table>` en la página**, así que los selectores del listado se acotan a su sección — un `table tbody tr` suelto leería las cifras por año como si fueran municipalidades, y también son números |
| `header.spec.ts` | «Comparar distritos» no se ofrece en la navegación (ADR-P2), y el resto del menú sí sigue ahí · en escritorio el menú **cabe en una línea** a 1024, 1280 y 1440 px, sin que la página desborde a lo ancho · la «X» vacía la caja de búsqueda de la cabecera sin navegar |

Tres convenciones que la suite impone desde `e2e/apoyo.ts` y `e2e/fixtures.ts`:

1. **Se vigila la consola.** Un error de JavaScript no rompe la página de forma visible —React sigue pintando lo que puede—, así que sin esto se puede dar por bueno un visor que perdió su capa de puntos.
2. **El beacon de métricas se descarta.** El tráfico de las pruebas no es uso real y no debe acabar en el panel del admin.
3. **Los enlaces del menú se buscan con `:visible`.** Existen dos veces —nav de escritorio y panel móvil— y solo una se muestra según el ancho; `.first()` cae siempre en la de escritorio.

Y dos trampas más, las dos con la misma forma —**la prueba comprobaba la intención y no el
resultado**—, las dos encontradas por un fallo real:

- **La prueba «se usa Meilisearch» pasaba con la llave caducada.** Comprobaba que *se llamara* a
  `multi-search`; la llamada se hacía, devolvía **403** y el sitio se iba al fallback igualmente. Y si
  no se llamaba, hacía `test.skip` en vez de fallar. Ahora mira los **status** —exige al menos un
  200— y que el aviso «modo básico» no esté en pantalla; el `skip` queda solo para el entorno sin
  buscador configurado. Es el mismo error que dar por bueno el proxy porque `GET /search/health`
  devolvía 200.
- **Correr la suite en desarrollo no cubre la llave de búsqueda.** En `npm run dev` el navegador ataca
  a Meilisearch con `frontend/.env`; la llave que puede estar mal es la que **se horneó en el bundle**
  desde el `.env` de la raíz. Otra razón por la que la corrida contra nginx no es opcional.

Y una trampa de medición, que costó una prueba que no comprobaba nada: **`elemento.getClientRects().length` no detecta que un texto se parta en dos líneas.** Los enlaces del menú son bloques, así que devuelven un solo rectángulo aunque su contenido ocupe dos líneas (se midió: 56 px de alto, un rectángulo). Las líneas se cuentan con un `Range` sobre el contenido del elemento, que devuelve un rectángulo por caja de línea.

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

- `pytest` completo (incluido `-m lento`) en verde: 259 + 7 pruebas.
- `npm run lint && npm run build` sin errores.
- `npx playwright test` en verde **dos veces**: contra el dev server y contra el bundle servido por nginx (`E2E_URL=http://localhost`). La segunda es la que vale.
- Las cinco comprobaciones manuales hechas y documentadas.
- Los conteos canónicos verificados sobre la base de producción tras el seed real.
