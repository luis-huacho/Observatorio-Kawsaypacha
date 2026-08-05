# 09 — Ciclo de errores

Lo que se sabe roto y **todavía no está corregido** vive en el tracker, no en este archivo. Corre en
el servidor y admite dos modos, según cómo se haya levantado:

| Modo | Cómo se llega |
|---|---|
| **Aislado** (por defecto del repositorio) | `ssh -L 3000:localhost:3000 …` → `http://localhost:3000/<admin>/observatorio/issues` |
| **Publicado** (`compose.tracking-publicado.yml`) | `https://<API_DOMAIN>/gitea/<admin>/observatorio/issues`, sin túnel |

En el servidor de desarrollo está **publicado** desde el 05/08/2026. El túnel queda como vía de
rescate; el detalle, en `_docs/despliegue-entorno-desarrollo.md`.

`<admin>` es la cuenta que genera el inicializador con el patrón `admin<NNN>`; el nombre real está en
`deploy/gitea/admin.env`, que git ignora. No está escrito en el repositorio a propósito.

Si hay que levantarlo —la primera vez, o en una máquina nueva— son dos comandos desde la raíz del
repositorio, y el segundo es idempotente:

```
docker compose -f compose.tracking.yaml up -d
./deploy/gitea/inicializar.sh
```

Este documento se queda con lo que el tracker no guarda: **el ciclo**. Qué significa cada etiqueta,
cuándo nace un error, cuándo se puede cerrar y dónde va a parar cuando se cierra.

## Por qué dejó de ser una tabla

Hasta el 04/08/2026 los errores abiertos eran una tabla Markdown aquí mismo, con una ficha en prosa
por cada uno. Funcionaba, y se abandonó por tres razones concretas, no por gusto:

- **El estado se duplicaba a mano en tres documentos**: esta tabla, [`README.md`](README.md) y
  `_docs/despliegue-entorno-desarrollo.md` repetían la lista de abiertos. Nada garantizaba que
  cuadraran, y de hecho no siempre cuadraban.
- **Ya había una referencia rota desde el código**: `deploy/nginx/conf.d/seguridad-comun.inc` citaba
  «ver E-005 en 09-errores.md», y E-005 se había cerrado y salido del archivo. Un puntero a una fila
  que ya no existe es peor que ningún puntero.
- **Uno de los errores abiertos era del propio registro** (E-003: «las entradas de la bitácora no
  están en orden cronológico»). Un tracker con fechas lo elimina por construcción.

Las siete fichas que había se migraron íntegras a issues, con su prosa completa. **El identificador
`E-NNN` se conserva en el título del issue** —`E-007 — ...`— porque hay comentarios en el código que
citan errores por ese número y tienen que seguir siendo buscables.

## Cómo se usa

**Numeración.** `E-NNN` correlativo, en el título del issue. Los números no se reutilizan nunca: si
un error se descarta, el issue se cierra con la nota de por qué, para que nadie lo vuelva a levantar
dentro de tres semanas. El último asignado es **E-008**.

**Severidad** — etiquetas `sev/…`, excluyentes entre sí:

| | Qué significa |
|---|---|
| **`sev/alta`** | Lo ve el público o afecta a lo que PREDES entrega. Bloquea la puesta en línea |
| **`sev/media`** | Degrada el sistema sin romperlo, o es un riesgo que se materializa fuera de nuestro control |
| **`sev/baja`** | Cosmético, de mantenimiento o de documentación |

**Área** — etiquetas `area/…`, también excluyentes: `backend`, `frontend`, `mapas`, `buscador`,
`admin`, `despliegue`, `datos`, `docs`. Son las mismas áreas en que está dividido el repositorio, y
sirven para lo de siempre: consultarlas antes de tocar una.

**La regla de cierre.** No cambia, y es lo más importante de este documento. Un error reproducible
**nace con una prueba que falla** —`@pytest.mark.xfail` en `backend/tests/`, o `test.fail()` en
`e2e/`— y se cierra cuando esa prueba pasa y se le quita la marca. Es lo que impide las dos formas
de mentir sobre un error: darlo por arreglado sin demostrarlo, y que desaparezca en silencio en un
refactor. Cada issue lleva al pie una línea **«Prueba de cierre»** que dice cuál es esa prueba.

Los que no son defectos de código —licencias, documentación, decisiones del cliente— llevan la
etiqueta **`sin-prueba`**: para esos el cierre es la revisión a ojo, y la línea del pie explica qué
hay que mirar.

**Trabajar uno.** Se mira la lista en la web y se lanza `/issue N` en Claude Code —o `/issue 6 3 1`
para varios, que salen en un solo plan—. El comando lee la ficha, plantea el plan, y solo con el plan
aprobado escribe la prueba que falla, la hace pasar y comenta en el issue qué lo demuestra. No
commitea ni cierra: eso se revisa. Está en `.claude/commands/issue.md` y el detalle en
[`_docs/desarrollo.md`](../_docs/desarrollo.md).

**Al cerrar**, el issue se cierra en el tracker **y** entra en la bitácora de
[`README.md`](README.md) como una entrada `### Actualización DD/MM/AAAA` con su causa y su
corrección, que es el formato que ya usa el proyecto. Esa entrada es la que se lee sin levantar
ningún contenedor, y la que queda en el repositorio para PREDES. Un solo sitio para lo pendiente,
un solo sitio para lo hecho.

## Qué hace falta para consultarlo

El tracker es **de desarrollo y no forma parte del entregable**, aunque comparta servidor con la
plataforma. **Hay uno solo**, a propósito: dos trackers son dos listas de pendientes que divergen,
que es el problema del que se venía.

Aislado no expone nada —escucha en `127.0.0.1` y se llega por túnel—. Publicado en `/gitea` gana
acceso desde cualquier navegador y, a cambio, deja un login en internet; el porqué de la decisión y
lo que la mitiga están en **ADR-A15**. En ninguno de los dos modos el sitio depende de él: si el
tracker cae, `/gitea` da 502 y el resto responde con normalidad.

Quien clone el repositorio y no lo levante no pierde nada del producto — pierde la lista de
pendientes, que es información de trabajo. Lo ya corregido sí está en el repositorio, en la bitácora.

Los detalles de operación (dónde vive el token, cómo se regenera, cómo se gestiona desde Claude
Code) están en [`_docs/desarrollo.md`](../_docs/desarrollo.md), y el porqué de la decisión en
**ADR-A15** de [`00-alcance-decisiones.md`](00-alcance-decisiones.md).
