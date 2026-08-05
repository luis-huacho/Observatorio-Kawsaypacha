---
description: Trabajar uno o varios issues del tracker de errores por número
argument-hint: "[número...] — p.ej. 6, o 6 3 1"
---

Trabaja los issues del tracker de errores del proyecto, en el Gitea del servidor.

El repositorio se llama siempre **`observatorio`**. El `owner` **no está escrito en ninguna parte y
no hay que adivinarlo**: es el dueño del token, y se obtiene con la herramienta `get_me` del MCP
(campo `login`). Lo genera el inicializador con el patrón `admin<NNN>`, así que **no es el mismo en
dos instalaciones**. Resuélvelo una vez al principio y reutilízalo en todas las llamadas.

Números pedidos: **$ARGUMENTS**

## 1. Qué se ha pedido

- **Con números** (uno o varios, separados por espacios): son esos issues y solo esos, estén como
  estén etiquetados.
- **Sin argumentos**: llama a `list_issues` con `state: "open"`, muestra los abiertos como
  `#N — título [severidad]` ordenados por severidad, y **detente ahí**. El usuario elige mirando la
  lista y vuelve a lanzar el comando con los números.

Si el MCP falla o no responde, casi siempre es que el tracker no está levantado. No devuelvas el
error crudo: di que hay que levantarlo y da el comando.

```bash
docker compose -f compose.tracking.yaml up -d
```

Si un número no existe, **`issue_read` no da error: devuelve resultado vacío**. Interprétalo como «no
existe», dilo y sigue con los demás; no abandones la invocación entera por uno malo, ni te quedes
esperando un error que no va a llegar.

## 2. Leer antes de decidir nada

Por cada issue, `issue_read` completo. Fíjate en dos cosas del cuerpo:

- La línea **«Prueba de cierre»** del pie. Dice exactamente qué demuestra que el error está
  arreglado. Es el criterio, no una sugerencia.
- Las etiquetas. `sev/…` da la prioridad y `area/…` dice dónde mirar. La etiqueta **`sin-prueba`**
  significa que **no es un defecto de código** —licencias, documentación, decisiones del cliente— y
  que el cierre es una revisión a ojo: no te inventes una prueba automática para esos.

Un issue abierto desde la web puede venir sin etiquetas y sin la línea «Prueba de cierre»: eso es
normal, no es un error de la ficha. En ese caso propón tú la severidad, el área y la prueba dentro
del plan, y si el usuario las aprueba, ponle las etiquetas con `issue_write` —los IDs los da
`label_read`— para que el issue quede como los demás.

Luego lee el código que la ficha nombra, y lo que necesites alrededor para entenderlo de verdad.
Consulta `_specs/` del área que toques antes de implementar; es la fuente de verdad del proyecto.

## 3. Plantear el plan y esperar

Usa `EnterPlanMode` y presenta el plan. Con varios issues, **un solo plan que los cubra todos**,
ordenados por severidad (`sev/alta` primero): así se ve el alcance real de una vez, y se nota si dos
issues se tocan entre sí antes de haber escrito nada.

No toques código hasta que el plan esté aprobado.

## 4. El flujo normal del proyecto

Aprobado el plan:

- **La prueba primero, y no es opcional aquí.** Un error reproducible nace con una prueba que falla
  —`@pytest.mark.xfail` en `backend/tests/`, o `test.fail()` en `e2e/`—. Escríbela, **comprueba que
  falla de verdad** sobre el código actual, arregla, comprueba que pasa y quita la marca. Una prueba
  que nunca se vio fallar no demuestra nada.
- Para los `sin-prueba`, haz la revisión que describe el pie del issue y deja constancia de qué
  miraste y qué encontraste.
- `pytest` va **dentro del contenedor**; las E2E son `npx playwright test` desde la raíz. Corre lo
  que corresponda al área que tocaste, no solo el archivo nuevo.

## 5. Comentar en cada issue

Al terminar cada uno, `issue_write` con `method: "add_comment"`. El comentario dice, en prosa breve:

- qué estaba pasando de verdad, si resultó ser distinto de lo que decía la ficha;
- qué se cambió y en qué archivos;
- **qué prueba lo demuestra**, con su ruta, o qué se revisó si era `sin-prueba`.

## 6. Parar ahí

**No commitees y no cierres el issue.** El usuario revisa y decide.

En el resumen final recuérdale que cerrar es doble: cerrar el issue en el tracker **y** escribir la
entrada `### Actualización DD/MM/AAAA` en la bitácora de `_specs/README.md` con la causa y la
corrección. Esa entrada es lo que queda en el repositorio cuando nadie levante el contenedor, y es
la mitad que se olvida.
