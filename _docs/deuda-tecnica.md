# Deuda técnica

Lo que este proyecto decidió **a sabiendas** y sigue costando. No es la lista de lo que está roto
—eso vive en el tracker— ni la de lo que falta por hacer: es la de las decisiones cuyo precio se
paga a plazos, reunidas en un sitio para que se vean juntas.

Existe porque en este repositorio la deuda es **invisible desde el código**. No hay un solo `TODO`
ni un `FIXME`: cada cosa está donde tiene que estar, con su comentario explicando por qué. El efecto
secundario es que alguien que llega no puede distinguir una decisión de un olvido, y «arregla» lo
que estaba bien.

## Cómo se lee

**Ninguna entrada de aquí es la fuente de verdad de su propio estado.** Cada una apunta al ADR que
la decidió, al spec que la describe o al archivo y la línea donde vive. Si una entrada se puede leer
entera sin seguir su puntero, está mal escrita: se ha copiado algo que ya existía en otro sitio, y
las dos copias empezarán a divergir hoy mismo.

Es la lección de [`_specs/09-errores.md`](../_specs/09-errores.md) aplicada a otra cosa. Allí se
eliminó una tabla de errores abiertos porque el estado se duplicaba a mano en tres documentos y no
siempre cuadraba. Aquí se evita por construcción: **este documento no contiene estado**.

Cada entrada dice cuatro cosas: **qué es · dónde está declarado · qué cuesta hoy · qué la salda**. Lo
último es un disparador, no una fecha: «cuando llegue el polígono del INEI», no «revisar en
septiembre». Una deuda con disparador no necesita que nadie la revise — se salda cuando pasa lo que
dice, y entonces **se borra de aquí**. No se tacha ni se archiva: el historial son los ADR y la
bitácora, no esta lista.

## Lo que no está aquí

| Qué | Dónde va |
|---|---|
| Algo roto, pendiente de corregir | El **tracker**. Un solo sitio para lo pendiente (09) |
| Algo aún no decidido | Un **ADR** en `_specs/00`. Este documento no decide nada |
| Una mejora, una idea, un deseo | En ningún sitio de este repositorio |
| Lo ya corregido | La **bitácora** de `_specs/README.md` |

## Automatización que falta

| Qué es | Declarado en | Qué cuesta hoy | Qué lo salda |
|---|---|---|---|
| **El CI no corre las pruebas.** Bitbucket Pipelines solo comprueba tipos (`tsc --noEmit`) | ADR-A21, [`_specs/10-pipeline-cicd.md`](../_specs/10-pipeline-cicd.md) | 261 pruebas de backend y 56 casos E2E que **nadie dispara automáticamente**. Un check verde no dice que pasaran; dice que el frontend compila. La puerta previa al despliegue es una regla de conducta | Un runner con GDAL, tippecanoe, WeasyPrint y Chromium, o el stack levantado en CI. Hoy no compensa: por eso el ADR |
| **`ruff` está configurado y no instalado** | `backend/pyproject.toml` (`[tool.ruff]`, línea 56) | Un bloque de configuración que no gobierna nada. Quien lo lea supondrá que el código pasa por un linter, y no pasa | Añadir `ruff` al grupo `dev` y correrlo, o borrar el bloque. Las dos salidas son mejores que la actual |
| **No hay ESLint**: `npm run lint` es `tsc --noEmit` | `frontend/package.json` | Los tipos se comprueban; las reglas de estilo y los errores que el compilador no ve, no | Cuando el frontend lo pida. No es urgente con un solo desarrollador |
| **No hay ningún script que corra la suite completa** | — | La secuencia entera está en `comandos.md` y en 08, y se teclea a mano cada vez, en el orden correcto | Un script, el día que el orden se recuerde mal — que es exactamente lo que pasó con el despliegue el 27/08 |
| **Las ramas `process.env.CI` de Playwright no se ejecutan nunca** | `playwright.config.ts` (retries, workers, reporter `github`) | Código preparado para un CI que no corre E2E. Se lee como un CI a medio terminar | Que el CI corra Playwright, o quitarlas |
| **Seis tareas de cron se instalan a mano en cada servidor, y nada comprueba que estén puestas** | [`despliegue.md`](./despliegue.md) §7 | Si falta la de métricas, el panel del admin sale en blanco y la tabla de eventos crece sin límite. En silencio | Que la provisión del servidor las ponga, o una comprobación que avise de su ausencia |
| **El certificado dejó de renovarse solo por diseño** | ADR-A6bis | Depende del contenedor `certbot` y de su bucle; la recarga de nginx va por un cron aparte cada 6 h | Nada previsto: fue el precio explícito de que PREDES pueda operar nginx |
| **El worker nunca se reinicia solo** | [`_specs/07`](../_specs/07-despliegue-ops.md) §Vigilancia | Un worker colgado a mitad de una importación necesita una persona. Es deliberado: matarlo puede dejar el dato peor que parado | Nada. Es la decisión, no su efecto colateral |

## Código vivo que no se usa

| Qué es | Declarado en | Qué cuesta hoy | Qué lo salda |
|---|---|---|---|
| **`Prioridades.tsx` sin ruta registrada**, con su import comentado en `App.tsx` | ADR-P1 | Un componente completo que no se renderiza nunca y que hay que mantener compilando | Que PREDES pida la ventana, o que se decida borrarla. **No reactivar sin pedido explícito** |
| **`/comparar` fuera del menú**, con ruta y endpoint vivos y probados | ADR-P2 | Una migración de datos (`sitio.0002`) existe solo para ocultar un enlace, porque el seed no pisa lo que ya está sembrado | Igual que la anterior |
| **Los campos `[+]` del modelo**: 25 líneas de `01-modelo-datos.md` los declaran | [`_specs/01`](../_specs/01-modelo-datos.md) (la convención, en su primer párrafo) | Columnas nullables que ninguna vista usa. Coste real bajo —se crearon a coste cero— pero engordan el ER y el admin | Que una funcionalidad los estrene, o una limpieza deliberada. No se listan aquí: la lista es el spec |
| **El Excel de normativa no tiene botón que lo pida.** `frontend/src/routes/Normativa.tsx:24` calcula `urlExport` y nunca lo pinta; el `Download` que importa en la línea 3 tampoco se usa | Hallado el 31/08/2026 al unificar las descargas | El endpoint existe, está limitado a 30/hora y tiene prueba en el backend (`test_las_descargas_estan_limitadas` lo usa como cobaya), pero **ningún botón de la SPA llega a él**. `noUnusedLocals` está en `false` (`frontend/tsconfig.json:16`), por eso nada avisó | Decidir si la ventana lleva export, que es una decisión de producto: o se añade el botón con `BotonDescarga` —dos minutos, el componente ya existe— o se borran las dos líneas |
| **`prototype/`, 100 archivos versionados y congelados** | `CLAUDE.md`, `_specs/archive/` | Peso en el repositorio y confusión al buscar: un `grep` devuelve resultados de código que no corre | Nada previsto. Es referencia aprobada por el cliente y borrarla pierde el original |
| ~~**`interpretar_json` vive en `core/lectura_web.py`**, que ya usan tres apps y una de ellas —medidas— no descarga nada~~ | ADR-D10 | **Cerrado el 28/08/2026 (ADR-A23)**: se movió a `core/services/salida_ia.py`, junto a `openrouter.py`, que es de quien es el JSON | Salió de camino: `a_html` tenía que subir al mismo sitio por el mismo motivo, así que mover las dos juntas costó tres líneas de import más que mover una |

## Datos provisionales y lo que falta

| Qué es | Declarado en | Qué cuesta hoy | Qué lo salda |
|---|---|---|---|
| **El polígono de Cusco es de geoBoundaries, no del INEI** | [`_specs/05`](../_specs/05-mapas-tiles.md) | El recorte de todas las capas depende de un límite no oficial. Funciona; no es la fuente que un organismo público citaría | Que PREDES entregue el polígono del INEI. Entra por el mismo pipeline |
| **Ocho observaciones de calidad de datos, abiertas con el cliente** | [`_specs/00`](../_specs/00-alcance-decisiones.md) §Observaciones | Filas sin nivel, un distrito sin fila de frecuencia, subtotales sin desagregar, dos grafías de la misma fuente. El sitio publica lo que hay y lo declara | Que PREDES corrija en origen. **No se copian aquí**: eran seis y ya son ocho, y una copia se habría quedado en seis |
| **Dependencias del cliente aún abiertas** | [`_specs/00`](../_specs/00-alcance-decisiones.md) §Dependencias | Las funciones afectadas se degradan con aviso, no fallan | Cada una, cuando llegue lo suyo |

## Rendimiento y límites del API

Todo esto salió de una misma investigación (27/08/2026): la suite E2E no cabía en la cuota anónima
del API y fallaba en bloque con 429. El límite en desarrollo ya está resuelto —las tasas se leen del
entorno y `compose.dev.yml` las vacía—; lo que queda aquí es lo que sigue costando en producción.

| Qué es | Declarado en | Qué cuesta hoy | Qué lo salda |
|---|---|---|---|
| **El techo anónimo va corto para una oficina.** `anon: 1000/hour` por IP, y la portada pide 8 veces por carga | `THROTTLE_PRODUCCION` en `backend/config/settings.py`, [`_specs/02`](../_specs/02-api.md) §Las tasas se configuran por entorno | **125 vistas de página por hora y por IP**, y una oficina entera tras un NAT comparte una sola: treinta personas tienen ~4 vistas cada una antes del 429. Es el mismo escenario que ya obligó a subir el beacon a 600/min, resuelto allí y no aquí | Decidir la cifra. **Ya no hace falta tocar código**: basta `API_THROTTLE_ANON` en el `.env` del servidor. Ojo también con `descarga: 30/hour`, la más justa de las tres |
| **Cinco de los siete endpoints de la portada no mandan `Cache-Control`**: `/peligros/resumen/`, `/territorio/distritos/`, `/medidas/`, `/noticias/`, `/normativa/` | Las cabeceras que sí existen, en `backend/apps/api/views/sitio.py:24` e `inversion.py:84` y `:210` | El más caro está entre los descubiertos: `/peligros/resumen/` hace **dos pasadas completas sobre los 8.968 centros poblados** (`backend/apps/peligros/consultas.py:57-97`), con un bucle en Python, en cada carga. `/territorio/distritos/` sirve los 112 distritos enteros para un catálogo que no cambia nunca | Añadir `cache_control` donde toque, que es una línea por vista. El criterio de cuánto dura cada uno es la decisión, no el código |
| **No hay caché de servidor en ningún nivel**: `CACHES` sin configurar, sin `cache_page`, y la zona `proxy_cache_path` de nginx **declarada y nunca usada** | `deploy/nginx/conf.d/observatorio.conf:23` | Cada petición recalcula. Y una consecuencia poco intuitiva: **el contador del throttle vive en esa caché**, así que con `LocMemCache` es por proceso — con N workers de gunicorn el límite efectivo es N × la tasa, e inconsistente entre ellos | Configurar `CACHES`, o usar la zona de nginx que ya está declarada. Mientras tanto, reiniciar el backend borra los 429 al instante |
| **El visor headless del PDF pide su página al mismo gunicorn que está generando el PDF**, y solo hay 3 workers | `backend/apps/informes/mapa.py:52` (`RENDER_MAPA_BASE_URL` → `http://backend:8000`), `backend/Dockerfile:70` (`--workers 3`) | En teoría, tres PDF simultáneos ocupan los tres workers esperando una página que ninguno puede servir. Se destraba solo a los 25 s (`mapa.py:110-118`) y los PDF salen **sin mapa**, que es la degradación correcta, así que el sitio no cae — pero son 25 s de espera. **No está reproducido**: es una lectura del código, no una medición | Subir `--workers`, añadir `--threads`, o sacar el render a un proceso aparte. Antes de tocar nada, reproducirlo: si no se puede provocar, la deuda es menor de lo que parece |
| **La portada pide 8 veces lo que cabría en 2** | `frontend/src/routes/Home.tsx:39-68` | Tres de las cuatro cifras bajan un payload entero para leer un número: los 112 distritos para hacer `.length`, un `COUNT(*)` para leer `.count`, un agregado caro para un solo campo. Y `/medidas/` se pide dos veces | Un `/api/portada/` con `cache_control`. El patrón ya existe y está bendecido: el docstring de `backend/apps/api/views/sitio.py:17-22` explica por qué el cascarón va en una sola petición |

| **`/peligros` desborda 104 px en móvil y deja el panel de filtros fuera de la pantalla** | `frontend/src/routes/Peligros.tsx:247,249` | Medido el 29/08/2026 a 375 px, **y también en producción**: `scrollWidth` 479 contra 375 de viewport, el `<aside>` mide 463 px y el botón «Ninguno» de cada checklist queda en x=414. **No se puede pulsar**: 12 pruebas de `peligros.spec.ts` fallan en el proyecto `movil` por esto, en master y en cualquier rama | Un `min-w-0` en el `<aside>` (o `grid-cols-1` explícito): un ítem de grid tiene `min-width: auto` y no encoge por debajo del ancho intrínseco de su contenido. En escritorio la columna la fija `lg:grid-cols-[280px_1fr]`, así que no cambia nada ahí |
| **No hay derivados de imagen: la lista compacta de noticias descarga la portada entera para un thumb de 96×96** | `frontend/src/routes/Noticias.tsx:141-149` | Con el mixin de ADR-A25 la portada ya no pasa de 1600 px, así que el peor caso bajó mucho — pero sigue siendo una imagen de ~200 KB para 96 px de lado. Mitigado con `loading="lazy"`, no resuelto | Un derivado por tamaño, o `srcset`. Exige generar y guardar variantes, que es un salto de alcance respecto a optimizar el original |
| **El título de una norma llega a 300 caracteres y la base lo corta a media palabra** | `backend/apps/normativa/models.py:38`, la IA lo llena | Tres de las seis normas de producción tienen exactamente 300 caracteres de título. No es un título, es la sumilla entera. El listado ya lo recorta al pintarlo (ADR-A24 lo encabeza con el `numero`), pero **el dato guardado sigue truncado** y así viaja al buscador y al export | Separar `titulo` y `sumilla` en el modelo, con migración de datos. Se dejó fuera de `bugfix/home` por ser un cambio de datos y no de vista |
| **El contenido del sitio es invisible para quien no ejecuta JavaScript** | `backend/apps/sitio/vistas_html.py` inyecta las metas, pero no el cuerpo | Medido el 29/08/2026 en producción: `GET /noticias/<slug>` devuelve 2 674 bytes y el `<body>` tiene **0 caracteres de texto**. Las metas de ADR-A24 arreglan la previsualización al compartir —título, bajada, imagen— pero **el artículo en sí no llega**. Google ejecuta JS y lo ve; muchos agentes y clientes de lectura, no | Negociación de contenido: devolver `text/markdown` cuando el `Accept` lo pide, reutilizando los resolvers de la lista blanca que ya existen. Y `/llms.txt`, que es el convenio más adoptado hoy. Se dejó fuera del alcance de ADR-A26 a propósito |
| **`SITIO_INDEXABLE` sigue en `1` en el entorno de desarrollo** | `backend/config/settings.py`, ADR-A26 | Hoy no cuesta nada: `observatorio.predes.org.pe` **no resuelve** y el entorno de desarrollo es el único sitio vivo, así que apagarlo dejaría el observatorio fuera de Google. El día que el dominio definitivo entre en el aire pasan a ser **dos copias idénticas que se autocanonicalizan** y compiten por las mismas búsquedas | Poner `SITIO_INDEXABLE=0` en el `.env` del entorno de desarrollo **ese mismo día**, y `up -d` (no `restart`, que no relee `env_file`). Es un paso del cambio de dominio, no un pendiente de código |
| **Lo que el informe de agent-readiness pide y aquí no se hizo** | ADR-A26 | Seis documentos describirían capacidades inexistentes (OAuth/OIDC, `auth.md`, tarjeta MCP) y **no deben hacerse mientras no existan**. WebMCP es un *origin trial* de Chrome y el índice de agent-skills y el manifiesto ARD son borradores sin adopción; DNS-AID es zona DNS y DNSSEC, fuera de este repositorio | Reevaluar si alguna de esas specs se asienta. La condición para publicar cualquiera de ellas sigue siendo la misma: que describa algo que el sitio hace de verdad |

## Documentación como deuda

| Qué es | Qué cuesta hoy | Qué lo salda |
|---|---|---|
| **El procedimiento de despliegue vivía en cinco documentos** (`README`, `comandos.md`, `_docs/despliegue.md`, `_specs/07` y ahora el 10) | Divergieron, y no de forma inocua: `_specs/07` acabó mandando la cadena que causó el incidente del 27/08 y un `certbot renew` que no renueva. Se corrigió quitando la copia del spec | Que ningún documento nuevo vuelva a copiar la secuencia. El 10 lleva una tabla de «qué no está aquí» justo para eso |
| **`comandos.md` está versionado y no lo cita ni el README ni CLAUDE.md** | Un documento sin dueño declarado envejece sin que nadie lo note | Darle una fila en la tabla de documentación, o fundirlo con el README |
| **Toda cifra escrita a mano en la documentación** | «144 pruebas» sobrevivió a que fueran 259; «ocho comprobaciones» a que fueran nueve. Una cifra desfasada no da ningún síntoma | Escribir al lado el comando que la reproduce. Es lo que se hizo con los conteos de pruebas |
| ~~**La calidad de lo que redacta la IA depende de `OPENROUTER_MODELO`, y el valor por defecto no da la talla**~~ | **Cerrado el 28/08/2026 (ADR-A23)**: se midió contra los tres consumidores y se cambió a `google/gemini-2.5-flash`; la red anti-texto-plano, que solo estaba en medidas, pasó a los tres | Lo que queda vivo es de operación, no de código: **el gasto de IA no se vigila desde ninguna parte**. El coste por llamada se anota en la bitácora de cada registro y en el `.txt` del registro de IA, pero nadie suma. Con ~$0.003 por registro no urge; lo saldaría un total en el panel del admin, junto a la tarjeta del buscador |

## Residuos del árbol de trabajo, que no del repositorio

En la máquina de desarrollo hay `inversion_cusco.sqlite3` (0 bytes), `pp0068_cusco.sqlite3`
(795 KB), `test-results/` y algún `__pycache__` con `.pyc` de Python 3.14 —mientras el proyecto pide
`>=3.12,<3.14`—.

**Git no versiona ninguno**: los tapan las reglas `__pycache__/`, `/*.sqlite3` y `/test-results/` de
`.gitignore`, y un clon limpio no los tiene. Se anotan aquí precisamente para que nadie los confunda con deuda del proyecto y «arregle»
un `.gitignore` que ya funciona. Se saldan borrándolos, o no saldándolos.

## Pendientes de pasar al tracker

> **Esta sección viola a propósito la regla de arriba, y es temporal.** Son defectos, no deuda, y su
> sitio es el tracker; se anotan aquí porque el 27/08/2026 el MCP de Gitea no conectaba y perder el
> hallazgo era peor que ensuciar el documento. **Al abrir cada issue, se borra su entrada.** Si esta
> sección sigue aquí dentro de unas semanas, el problema ya no son los defectos sino ella.

- **Un 429 se reintenta en bucle y realimenta el propio límite.** `frontend/src/lib/api.ts` borra de
  la caché las peticiones fallidas a propósito (líneas 98-99 y 149-151), para poder reintentar. Pero
  no distingue el 429 ni aplica backoff: `ErrorApi.status` se guarda y **nadie lo consulta** — cero
  apariciones de `429` o `Retry-After` en todo `frontend/src`. Una vez agotada la cuota, cada vuelta
  a la portada relanza las 8 peticiones contra el límite que la está bloqueando.

- **`home.spec.ts:19` busca una tarjeta que la portada ya no tiene.** La prueba «las cifras salen del
  API y coinciden con el resumen» localiza `getByText("Centros poblados monitoreados")`; esa tarjeta
  no existe desde el commit `0e216c3` (18/08/2026), que rehízo las cifras. Lleva rota desde entonces,
  tapada primero por una carrera en `esperarApi` y después por los 429. **No basta con renombrar el
  texto**: la portada dejó de publicar el total de centros poblados, así que hay que decidir qué debe
  demostrar. Lo más fiel a su intención es cuadrar «Centros poblados con peligro alto/muy alto»
  contra la suma de los niveles 3 y 4 de `/api/peligros/resumen/`, que es lo que calcula
  `Home.tsx:55-57`.

- **Once E2E del visor agotan el tiempo en el proyecto móvil, sin atribuir.** Primera corrida
  completa sin 429 (27/08/2026, contra el dev server de Vite): 93 pasan, 13 fallan, 6 se saltan, y
  **cero respuestas 429**. Dos de los fallos son la prueba de arriba; los otros once se concentran en
  `movil` —diez de `peligros.spec.ts`, uno de `buscar.spec.ts`— y nueve agotan exactamente los 60 s.
  La sospecha razonable es la que advierte el propio `playwright.config.ts` —contra el dev server,
  Vite compila cada módulo la primera vez y con varios navegadores en paralelo eso se lleva por
  delante las esperas—, pero **no está comprobado**. Lo zanja correr la suite como manda la
  documentación, contra el bundle compilado: `compose.local.yml` con `E2E_URL=http://localhost`.

## Lo que este documento no puede saber

**Los defectos abiertos no están aquí.** Viven en el tracker, en el servidor de desarrollo; el último
identificador asignado es `E-008`. Cómo se levanta y cómo se consulta está en
[`_specs/09-errores.md`](../_specs/09-errores.md).

Un inventario de deuda que también listara lo roto sería un segundo tracker, y dos listas de
pendientes divergen — que es de lo que este proyecto ya salió una vez.
