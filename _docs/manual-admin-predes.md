# Manual de administración

Para el equipo de PREDES. Cómo publicar contenido, actualizar los datos y cambiar los textos del
Observatorio Kallpachakuy sin ayuda técnica.

Este documento es también el **guion de la sesión de capacitación** (Fase III del TDR): los
apartados están en el orden en que conviene mostrarlos, y cada uno acaba en algo que la persona
puede hacer por sí misma.

## Entrar

`https://obs.predes.org.pe/loginseguro/` con el usuario y la contraseña que se entregaron aparte.

> Es `/loginseguro/`, no `/admin/`. Se cambió a propósito: `/admin/` es la primera dirección que
> prueban los robots que buscan sitios para atacar.

Al entrar se ve el **Panel**, que responde de un vistazo las preguntas del día:

- **Cuántas piezas esperan revisión**, y el reparto de todo el contenido por estado.
- Los últimos 30 días de uso: visitas, búsquedas, ayudas memoria y exports descargados.
- **Páginas más vistas**, **búsquedas más frecuentes** y **distritos con más ayudas memoria
  descargadas**. Esta última lista dice qué distritos se están llevando a mesas técnicas.
- La última carga de datos activa, y un aviso si alguna capa del mapa quedó con error.
- **El estado del buscador**, con su propio apartado más abajo.

Las búsquedas más frecuentes son la lista más útil para planificar contenido: dice qué le está
pidiendo la gente al Observatorio.

### La tarjeta «Buscador»

Dos columnas, y lo único que hay que mirar es que los números de cada fila **sean iguales**:

| Contenido | En el buscador | Publicado |
|---|---|---|
| Medidas | 6 | 6 |
| Centros poblados | 8,968 | 8,968 |

«Publicado» es lo que hay en el sitio; «En el buscador» es lo que se puede encontrar buscándolo. Son
dos cosas distintas: el buscador guarda su propia copia del contenido y la actualiza cada vez que se
publica algo, así que **puede quedarse atrás** —si el servicio estuvo apagado un rato, por ejemplo—.
Cuando eso pasa, lo publicado sigue viéndose en su página y simplemente no aparece al buscarlo, sin
ningún otro síntoma. Por eso está la tarjeta.

- **«activo y al día»**, en verde: todo correcto, no hay nada que hacer.
- **«con índices desfasados»**, en rojo: pulsa **Reindexar la búsqueda**. Tarda unos segundos, se
  puede repetir sin riesgo y el buscador **sigue funcionando mientras**. Si el aviso dice que hay
  tareas en cola, espera unos segundos y recarga antes de pulsar: puede que ya se esté actualizando.
- **«no responde»**: el servicio de búsqueda está caído. Esto **no se arregla desde el panel**: hay
  que avisar. Mientras tanto el sitio sigue funcionando y el buscador pasa a un modo básico —sin
  tolerancia a erratas ni acentos omitidos— y lo dice en pantalla a quien busque.

## Los tres roles

| Rol | Puede |
|---|---|
| **Editor** | Crear y modificar contenido, enviarlo a revisión. **No puede publicar** |
| **Publicador** | Todo lo del Editor, y además publicar, devolver y archivar |
| **Administrador** | Todo, incluidos los datos, las capas del mapa, los textos y los usuarios |

Un Editor no ve los botones de publicar: no están escondidos, simplemente no existen para su
usuario. Es a propósito — nada que un equipo no haya revisado sale al sitio público.

## Publicar contenido

Todo el contenido —medidas, normativa, noticias, videos, eventos, biblioteca— funciona igual y
pasa por cuatro estados:

```
   Borrador ──enviar a revisión──▶ En revisión ──publicar──▶ Publicado ──▶ Archivado
      ▲                                 │                        │            │
      └────────── devolver ─────────────┘                        └── volver a borrador ──┘
```

**En el sitio público solo se ve lo que está en Publicado.** Un borrador no aparece ni buscándolo
por su dirección exacta.

El paso de estado **no se hace editando un campo**, se hace con las acciones del final del
formulario o desde la lista, marcando las filas y eligiendo la acción:

- **Enviar a revisión** — avisa por correo al equipo de Publicadores.
- **Publicar** — lo saca al sitio y avisa a quien lo escribió.
- **Devolver a borrador** — pide unas observaciones, y **esas observaciones van en el correo** a
  quien lo escribió. Es el único sitio donde se le puede explicar qué corregir, así que conviene
  ser concreto.
- **Archivar** — lo retira del sitio sin borrarlo. **Archivar es lo correcto para retirar algo**;
  borrar destruye el historial y las direcciones que ya se hayan compartido.

### Ejercicio de la capacitación

Crear una noticia, enviarla a revisión, verla llegar por correo, devolverla con una observación,
corregirla y publicarla. Comprobar que aparece en `https://observatorio.predes.org.pe/noticias`.

### Escribir en el editor

El campo de contenido es un editor con negrita, listas, enlaces, imágenes y encabezados. Dos cosas
que conviene saber:

- **Las imágenes se suben ahí mismo** y quedan guardadas en el servidor. No hace falta subirlas a
  otro sitio ni pegar enlaces externos, que se rompen con el tiempo.
- **Las fotos grandes se reducen solas.** Se puede subir la foto tal como salió del teléfono o de la
  cámara: el sistema la deja en 1.600 px de ancho —de sobra para pantalla— y la endereza si venía
  tumbada. No hace falta recortarla ni comprimirla antes. El límite por archivo son **10 MB**; si se
  pasa, el editor lo dice y hay que reducirla antes de subirla.
- **Al pegar desde Word se limpia el formato.** Es intencional: el Word trae estilos que romperían
  el diseño del sitio. Los encabezados y las listas hay que volver a marcarlos con los botones.

### La imagen de portada

Si no se sube ninguna, el sitio pone **una ilustración institucional** según el peligro o el tipo
de contenido. Nunca sale un hueco. Subir una propia siempre queda mejor; el tamaño recomendado es
1200 × 675 px.

### Palabras clave

Alimentan el buscador y las etiquetas navegables de cada ficha. Conviene usar **las mismas
palabras entre registros** (siempre «heladas», no «helada» y «heladas» mezcladas): dos formas de
escribir lo mismo hacen dos etiquetas distintas y ninguna de las dos reúne todo.

## Actualizar los datos de peligros y emergencias

**Datos → Cargas de datos → Añadir**. Se sube el Excel, se elige de qué tipo es y se guarda.
Después, en la lista, se marca la fila y se elige **«Validar e importar»**.

La importación tarda un par de minutos. Al terminar, el estado cambia y aparece un **registro** con
lo que pasó, escrito para leerse: cuántas filas entraron, cuántas se descartaron y **por qué**,
citando la hoja y el número de fila. Ese registro es el documento que dice qué corregir en el
archivo.

Tres cosas importantes:

1. **Es todo o nada.** Si el archivo tiene un problema de fondo, no entra nada. No hay riesgo de
   quedarse con la mitad de los datos cargados.
2. **La carga anterior queda marcada como reemplazada, no se borra.** Siempre se puede ver qué
   archivo produjo qué datos y cuándo.
3. **Los avisos son normales.** El Excel actual produce unos cuantos: 229 filas sin nivel de
   peligro, 2 sin código, 26 distritos que declaran un total sin desglosar, 21 que tienen fila pero
   ningún dato, y Acomayo que no tiene fila. No son fallos del sistema: es la calidad de los datos de
   origen, y están anotados para pedírselos a quien los produce.

Al terminar una carga de peligros, **los puntos del mapa y el buscador se actualizan solos**. No
hay que hacer nada más.

## Cambiar las capas del mapa

**Mapa → Capas cartográficas.** Cada capa (ríos, lagunas, glaciares) tiene su archivo GeoJSON, su
color y su orden de dibujo.

Para reemplazar una: se abre, se sube el archivo nuevo, se guarda, y desde la lista se elige
**«(Re)generar tiles»**. Tarda entre uno y varios minutos según el tamaño. Cuando la etiqueta pasa
a **ok**, la capa ya está en el visor público.

**Mientras se está procesando, la capa desaparece del visor.** Es deliberado: es mejor que falte
una capa un minuto que mostrarla a medio generar. Si la etiqueta queda en **error**, el motivo está
en el campo de errores de esa misma capa, en castellano.

Se pueden añadir capas nuevas igual, sin que nadie toque el programa. Lo que **no** se puede es
cambiar el color de los niveles de peligro desde aquí: eso es parte del diseño del visor.

## Textos, portada y menú

**Sitio →**

- **Configuración** — nombre, contacto, redes sociales, el texto del pie. Es un solo registro; se
  edita, no se crea otro.
- **Textos** — los párrafos del sitio (presentación de la portada, la página «Sobre», las
  advertencias sobre los datos). Cada uno tiene una clave que dice dónde sale; **la clave no se
  cambia**, el texto sí.
- **Hero de portada** — las imágenes grandes de arriba. El orden se cambia escribiendo el número
  en la columna **orden** de la lista y guardando. Pasan por los mismos cuatro estados que el
  contenido, así que un slide se retira **archivándolo**, no borrándolo.
- **Menú** — los enlaces de la cabecera y del pie. Cada uno tiene una casilla **visible**: es la
  forma de ocultar una sección sin perder su configuración. Así está hoy **Prioridades**.
  **Inversión** sí está visible, y muestra su página en espera de datos.

Un cambio aquí se ve en el sitio en cuanto se recarga la página.

## Resúmenes con inteligencia artificial

En **Biblioteca**, la acción **«Generar resumen con IA»** propone un resumen del documento. Al
subir un documento nuevo también se genera solo.

Dos advertencias que conviene decir en voz alta durante la capacitación:

- **Es una propuesta, no un resultado.** Hay que leerla y corregirla antes de publicar. La IA se
  equivoca con seguridad aparente, y un resumen erróneo firmado por PREDES es peor que no tenerlo.
- **Nunca bloquea nada.** Si el servicio no responde, el documento se guarda y se publica igual. Si
  la acción sale desactivada, es que la clave del servicio no está configurada — es una tarea
  pendiente de configuración, no una avería.

## Lo que sale en el sitio público

Merece la pena recorrerlo en la capacitación, porque es donde se ve el efecto de todo lo anterior:

- **`/peligros`** — el visor. Filtros por provincia, distrito, peligro y nivel; la tabla de centros
  poblados; el gráfico de distribución; la descarga en Excel; y la **ayuda memoria en PDF** de cada
  distrito, de dos caras y con su mapa, pensada para llevarla impresa a una reunión.
- **`/comparar`** — hasta cuatro distritos lado a lado. **Hoy no está en el menú**: la página
  funciona y se abre escribiendo la dirección, pero no se ofrece en la navegación. Para volver a
  anunciarla, en **Menú** se marca «visible» en los dos enlaces «Comparar distritos» (el del menú
  principal y el del pie). Es el mismo mecanismo con el que se puede ocultar cualquier sección.
- **`/buscar`** — busca en todo el contenido publicado, tolera errores de tecleo.
- **`/inversion`** — hoy vacía, a la espera de los datos.

### Dos cifras que no significan lo mismo

Esto es lo más importante que se puede llevar alguien de la sesión, porque afecta a lo que se dice
en público:

- **3,238 centros poblados** tienen algún nivel de peligro evaluado.
- **10,978 clasificaciones** de peligro hay registradas.

Son la misma información contada en unidades distintas: un centro poblado con tres peligros
evaluados cuenta **una vez** en la primera cifra y **tres** en la segunda. El sitio siempre rotula
cuál está mostrando. Al citar una cifra en un informe o una nota de prensa hay que decir de qué
es: «**2,032 centros poblados** con su peligro más alto en nivel muy alto» o «**3,051
clasificaciones** en nivel muy alto» — nunca «2,032 casos», que no dice nada.

Y una tercera, igual de importante: **5,730 centros poblados no tienen ningún dato**. Salen en gris
en el mapa y se cuentan aparte. **Sin dato no es «bajo riesgo»**: es que nadie los ha evaluado, y
eso es en sí mismo un argumento para pedir que se haga.

## Cuando algo no funciona

| Lo que se ve | Qué hacer |
|---|---|
| Publiqué algo y no sale en el sitio | Recargar. Comprobar que el estado quedó en **Publicado** |
| Sale en su página pero el buscador no lo encuentra | Panel → tarjeta **Buscador** → **Reindexar la búsqueda**. Si la tarjeta dice «no responde», avisar |
| El Excel no entró | Leer el registro de la carga: dice hoja y fila |
| Una capa quedó en **error** | Leer el campo de errores de esa capa |
| No llegan los correos de revisión | Comprobar que los usuarios tienen correo en su ficha, y avisar |
| El mapa sale en blanco | Avisar. No es algo que se arregle desde el panel |

Para lo que hay que avisar, quien recibe el aviso encuentra el procedimiento en
`_docs/despliegue.md`.

## Buenas prácticas

- **Archivar, no borrar.** Borrar destruye el historial y rompe los enlaces ya compartidos.
- **Citar siempre la fuente.** Los datos son de CENEPRED/SIGRID y del INDECI; el Observatorio los
  reúne, no los produce. Cada registro tiene sus campos de fuente y conviene llenarlos.
- **Los periodos de emergencias son distintos en cada distrito** (hay 23 rangos de años en la
  fuente). Dos distritos no son comparables sin decir de qué años es cada cifra.
- **Contraseñas propias, nunca compartidas.** El sistema registra quién hizo cada cambio, y eso
  solo sirve si cada persona entra con su usuario.
- **Revisar el panel una vez por semana.** Las búsquedas más frecuentes son la agenda de contenido
  que pide el público, y la cola de «espera revisión» no se mueve sola.
