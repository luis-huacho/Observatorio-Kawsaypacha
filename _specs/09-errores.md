# 09 — Errores abiertos

Lo que se sabe roto y **todavía no está corregido**. Es la contraparte de la bitácora de
[`README.md`](README.md), que registra lo ya arreglado: un error entra aquí el día que se descubre y
sale de aquí el día que se cierra.

Existe porque los hallazgos que se decidía no arreglar en el momento no tenían dónde vivir. Se
narraban dentro de una entrada de bitácora —«anotado, sin cambio de código por decisión del dueño del
proyecto»— y desde ahí no había forma de volver a encontrarlos.

## Cómo se usa

**Numeración.** `E-NNN` correlativo. Los números no se reutilizan nunca: si un error se descarta, se
queda con su nota de por qué, para que nadie lo vuelva a levantar dentro de tres semanas.

**Severidad.**

| | Qué significa |
|---|---|
| **alta** | Lo ve el público o afecta a lo que PREDES entrega. Bloquea la puesta en línea |
| **media** | Degrada el sistema sin romperlo, o es un riesgo que se materializa fuera de nuestro control |
| **baja** | Cosmético, de mantenimiento o de documentación |

**La regla de cierre.** Un error reproducible **nace con una prueba que falla** —`@pytest.mark.xfail`
en `backend/tests/`, o `test.fail()` en `e2e/`— y se cierra cuando esa prueba pasa y se le quita la
marca. Es lo que impide las dos formas de mentir sobre un error: darlo por arreglado sin demostrarlo,
y que desaparezca en silencio en un refactor. Los que no son defectos de código (licencias,
documentación) llevan `—` en la columna *Prueba*; para esos el cierre es la revisión a ojo.

**Al cerrar**, el error sale de la tabla de abajo y entra en la bitácora de [`README.md`](README.md)
como una entrada `### Actualización DD/MM/AAAA` con su causa y su corrección, que es el formato que ya
usa el proyecto. Un solo sitio para lo pendiente, un solo sitio para lo hecho.

---

## Errores abiertos

| ID | Sev | Síntoma | Dónde | Prueba | Estado |
|---|---|---|---|---|---|
| E-001 | alta | El Excel de un distrito sin clasificaciones sale **vacío y sin explicar por qué**; son 24 distritos, Sicuani incluido | `backend/apps/api/exports.py` | pendiente | abierto |
| E-002 | media | El mapa base **OpenTopoMap no tiene licencia apta para producción**: es un servicio voluntario con política de uso restrictiva | `frontend/src/components/MapaPeligros.tsx:162` | — | abierto |
| E-003 | baja | Las entradas de la bitácora **no están en orden cronológico** | `_specs/README.md` | — | abierto |
| E-004 | baja | `_docs/propuesta.md` está **desfasado** frente al encargo real | `_docs/propuesta.md` | — | abierto |

---

### E-001 — el export vacío no dice que está vacío

**Reproducción.** Ir a `/peligros`, filtrar por el distrito de Kunturkanki y descargar el Excel:
llegan las cabeceras y ninguna fila. Lo mismo con Sicuani, que tiene 302 centros poblados.

**Qué pasa de verdad.** No es un fallo del importador ni del filtro. La fuente **no clasificó ninguno
de los centros poblados de esos distritos**: son 24 distritos en esa situación. El export está
haciendo lo correcto y comunicándolo del peor modo posible, porque un Excel sin filas se lee como «no
hay peligros aquí» cuando lo que significa es «nadie ha medido esto todavía». La diferencia importa
en una mesa técnica.

**La prueba de que es un problema de comunicación y no de datos**: la ayuda memoria en PDF **sí lo
explica** en su párrafo de presentación. Dos salidas del mismo dato, con el mismo vacío detrás, y
solo una lo cuenta.

**Precedente en el repo.** Es el mismo patrón que ya se corrigió una vez y está documentado en
`08-plan-pruebas.md`: 21 distritos con fila vacía recibían el aviso de ADR-D1, «un vacío de
información escondido detrás de un mensaje que dice otra cosa».

**Se anotó y no se arregló** por decisión del dueño del proyecto al cerrar la revisión del 04/08/2026
(ver la entrada correspondiente en `README.md`). Queda aquí para que la decisión sea revisable, no
para revertirla.

**Cómo se cerraría.** Una prueba en `backend/tests/test_api_peligros.py` que pida el export de un
distrito sin clasificaciones y exija que el libro lleve la advertencia; hoy fallaría.

### E-002 — OpenTopoMap no se puede usar en producción

`05-mapas-tiles.md:158` ya lo dice sin ambigüedad: «OpenTopoMap es un servicio voluntario con
política de uso restrictiva: vale para el prototipo, pero en producción hay que sustituirlo por una
fuente propia o con contrato». El comentario de `MapaPeligros.tsx:124` repite la advertencia.

Sigue siendo el mapa base **que arranca visible**, así que es el que va a recibir el tráfico real
desde el día de la puesta en línea. No rompe nada hoy; el riesgo es que el proveedor corte el
servicio por volumen, y entonces se cae el fondo del visor principal.

Los otros tres mapas base del selector siguen disponibles, así que la mitigación mínima —cambiar cuál
arranca por defecto— es de una línea. La solución de fondo es una fuente con contrato.

Aparece también en el README como una de las piezas pendientes del cliente, porque contratar la
fuente no es una decisión técnica.

### E-003 — la bitácora no está en orden

En `README.md` las entradas van 04/08, varias de 03/08, **02/08**, y otra vez 03/08 dos veces más.
Se lee de arriba abajo como si fuera cronológica y no lo es, así que quien busque «qué pasó después
de la auditoría de los Excel» se lleva una respuesta equivocada.

Reordenar de más reciente a más antigua. Es mover bloques de texto, sin riesgo.

### E-004 — la propuesta no coincide con el encargo real

`_docs/propuesta.md` sigue llamando al proyecto **«Kawsaypacha»** y describe un calendario
08/06→23/07/2026 con entrega el 19/07, cuando el trabajo real corre hasta el **13/08/2026**.

Es un documento **precontractual** y el propio pie lo admite («los montos y plazos son estimaciones
de buena fe sujetas a ajuste»), así que no es una contradicción vergonzante — pero es el documento
que alguien abriría buscando el alcance acordado, y le daría fechas que ya no existen.

No se versiona (`.gitignore` ignora `/_docs/*` salvo la documentación técnica), así que el arreglo
no tiene ningún efecto sobre el repo publicado. Vale con una nota al principio que diga qué documento
manda.
