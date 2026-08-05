# 09 — Ciclo de errores

Lo que se sabe roto y **todavía no está corregido** vive en el tracker, no en este archivo:

```
docker compose -f compose.tracking.yaml up -d     # Gitea local, solo en 127.0.0.1:3000
./deploy/gitea/inicializar.sh                     # idempotente; la primera vez crea todo
```

→ **<http://localhost:3000/luishuacho/observatorio/issues>**

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

**Al cerrar**, el issue se cierra en el tracker **y** entra en la bitácora de
[`README.md`](README.md) como una entrada `### Actualización DD/MM/AAAA` con su causa y su
corrección, que es el formato que ya usa el proyecto. Esa entrada es la que se lee sin levantar
ningún contenedor, y la que queda en el repositorio para PREDES. Un solo sitio para lo pendiente,
un solo sitio para lo hecho.

## Qué hace falta para consultarlo

El tracker es **local y de desarrollo**: escucha solo en `127.0.0.1`, no se despliega en el servidor
de producción y no forma parte del entregable. Quien clone el repositorio y no lo levante no pierde
nada del producto — pierde la lista de pendientes, que es información de trabajo.

Los detalles de operación (dónde vive el token, cómo se regenera, cómo se gestiona desde Claude
Code) están en [`_docs/desarrollo.md`](../_docs/desarrollo.md), y el porqué de la decisión en
**ADR-A15** de [`00-alcance-decisiones.md`](00-alcance-decisiones.md).
