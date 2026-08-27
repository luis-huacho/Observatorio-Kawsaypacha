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
| **El CI no corre las pruebas.** Bitbucket Pipelines solo comprueba tipos (`tsc --noEmit`) | ADR-A21, [`_specs/10-pipeline-cicd.md`](../_specs/10-pipeline-cicd.md) | 259 pruebas de backend y 56 casos E2E que **nadie dispara automáticamente**. Un check verde no dice que pasaran; dice que el frontend compila. La puerta previa al despliegue es una regla de conducta | Un runner con GDAL, tippecanoe, WeasyPrint y Chromium, o el stack levantado en CI. Hoy no compensa: por eso el ADR |
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
| **`prototype/`, 100 archivos versionados y congelados** | `CLAUDE.md`, `_specs/archive/` | Peso en el repositorio y confusión al buscar: un `grep` devuelve resultados de código que no corre | Nada previsto. Es referencia aprobada por el cliente y borrarla pierde el original |

## Datos provisionales y lo que falta

| Qué es | Declarado en | Qué cuesta hoy | Qué lo salda |
|---|---|---|---|
| **El polígono de Cusco es de geoBoundaries, no del INEI** | [`_specs/05`](../_specs/05-mapas-tiles.md) | El recorte de todas las capas depende de un límite no oficial. Funciona; no es la fuente que un organismo público citaría | Que PREDES entregue el polígono del INEI. Entra por el mismo pipeline |
| **Ocho observaciones de calidad de datos, abiertas con el cliente** | [`_specs/00`](../_specs/00-alcance-decisiones.md) §Observaciones | Filas sin nivel, un distrito sin fila de frecuencia, subtotales sin desagregar, dos grafías de la misma fuente. El sitio publica lo que hay y lo declara | Que PREDES corrija en origen. **No se copian aquí**: eran seis y ya son ocho, y una copia se habría quedado en seis |
| **Dependencias del cliente aún abiertas** | [`_specs/00`](../_specs/00-alcance-decisiones.md) §Dependencias | Las funciones afectadas se degradan con aviso, no fallan | Cada una, cuando llegue lo suyo |

## Documentación como deuda

| Qué es | Qué cuesta hoy | Qué lo salda |
|---|---|---|
| **El procedimiento de despliegue vivía en cinco documentos** (`README`, `comandos.md`, `_docs/despliegue.md`, `_specs/07` y ahora el 10) | Divergieron, y no de forma inocua: `_specs/07` acabó mandando la cadena que causó el incidente del 27/08 y un `certbot renew` que no renueva. Se corrigió quitando la copia del spec | Que ningún documento nuevo vuelva a copiar la secuencia. El 10 lleva una tabla de «qué no está aquí» justo para eso |
| **`comandos.md` está versionado y no lo cita ni el README ni CLAUDE.md** | Un documento sin dueño declarado envejece sin que nadie lo note | Darle una fila en la tabla de documentación, o fundirlo con el README |
| **Toda cifra escrita a mano en la documentación** | «144 pruebas» sobrevivió a que fueran 259; «ocho comprobaciones» a que fueran nueve. Una cifra desfasada no da ningún síntoma | Escribir al lado el comando que la reproduce. Es lo que se hizo con los conteos de pruebas |

## Residuos del árbol de trabajo, que no del repositorio

En la máquina de desarrollo hay `inversion_cusco.sqlite3` (0 bytes), `pp0068_cusco.sqlite3`
(795 KB), `test-results/` y algún `__pycache__` con `.pyc` de Python 3.14 —mientras el proyecto pide
`>=3.12,<3.14`—.

**Git no versiona ninguno**: los tapan las reglas `__pycache__/`, `/*.sqlite3` y `/test-results/` de
`.gitignore`, y un clon limpio no los tiene. Se anotan aquí precisamente para que nadie los confunda con deuda del proyecto y «arregle»
un `.gitignore` que ya funciona. Se saldan borrándolos, o no saldándolos.

## Lo que este documento no puede saber

**Los defectos abiertos no están aquí.** Viven en el tracker, en el servidor de desarrollo; el último
identificador asignado es `E-008`. Cómo se levanta y cómo se consulta está en
[`_specs/09-errores.md`](../_specs/09-errores.md).

Un inventario de deuda que también listara lo roto sería un segundo tracker, y dos listas de
pendientes divergen — que es de lo que este proyecto ya salió una vez.
