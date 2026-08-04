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
| E-006 | baja | Zona de caché `proxy_cache_path` declarada y **nunca usada**: reserva 10 MB para nada | `deploy/nginx/conf.d/observatorio.conf:13` | — | abierto |
| E-007 | baja | `seed --solo-catalogos --demo` **ignora `--demo` en silencio**: el `return` del primero corta antes | `backend/apps/core/management/commands/seed.py:103` | pendiente | abierto |
| E-008 | baja | `ssl_stapling on` ya no hace nada: los certificados de Let's Encrypt no traen URL de OCSP, y nginx avisa en cada arranque y cada recarga | `deploy/nginx/conf.d/ssl-comun.inc` | — | abierto |

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

### E-006 — una zona de caché declarada que nunca se usa

`deploy/nginx/conf.d/observatorio.conf:13` declara
`proxy_cache_path /var/cache/nginx/tiles … keys_zone=tiles:10m max_size=512m`, con dos líneas de
comentario explicando por qué merece la pena cachear los tiles en nginx. Pero **no hay un solo
`proxy_cache tiles;` en el repositorio**, y `/tiles/` se sirve con `alias` desde el volumen `media`,
no por proxy: no hay nada que cachear. Además `/var/cache/nginx` no tiene volumen montado, así que
la caché tampoco sobreviviría a una recreación del contenedor.

Reserva 10 MB de memoria compartida para nada. El daño real es el comentario, que describe un
comportamiento que no ocurre y que alguien podría dar por bueno al diagnosticar la latencia de los
tiles.

**Arreglo**: borrar la directiva y su comentario. Si algún día se quiere de verdad, el sitio de la
caché no es este —los tiles no pasan por `proxy_pass`—, sino `expires`/`Cache-Control`, que ya está.

### E-007 — `--solo-catalogos` se come `--demo` sin decirlo

`seed --solo-catalogos --demo` siembra los catálogos y **no carga el contenido de demostración**,
sin una sola línea que lo advierta. La causa está a la vista en `seed.py`: `--solo-catalogos`
imprime su nota y hace `return`, y el bloque de `--demo` viene después.

Cada bandera por separado hace lo que dice, así que no es un error de ninguna de las dos: es que
juntas no componen. Apareció el 04/08/2026 al desplegar sin los Excel, que es justo el escenario
donde tiene sentido pedir las dos —catálogos sin importar nada, pero con algo que enseñar—. Se
resolvió llamando a `Command()._demo()` a mano.

**Arreglo**: mover el bloque de `--demo` delante del `return`, o rechazar la combinación con un
`CommandError` que lo explique. Lo primero es más útil. La prueba va en `backend/tests/test_seed.py`:
sembrar con las dos banderas y exigir que haya medidas.

### E-008 — `ssl_stapling` ya no aplica

`ssl-comun.inc` activa `ssl_stapling on` y `ssl_stapling_verify on`. Desde que Let's Encrypt dejó
de incluir la URL del respondedor OCSP en sus certificados, la directiva no puede hacer nada, y
nginx lo dice en cada arranque y en cada recarga:

```
nginx: [warn] "ssl_stapling" ignored, no OCSP responder URL in the certificate
```

No rompe nada —el grapado OCSP es una optimización, no un requisito—, pero **ensucia el log de
nginx con un aviso permanente**, y un aviso que siempre está es un aviso que nadie lee. Ese es el
daño real: el día que nginx avise de algo importante, estará al lado de este.

**Arreglo**: quitar las dos directivas y dejar un comentario que explique por qué no están, para
que nadie las vuelva a añadir «porque faltan».
