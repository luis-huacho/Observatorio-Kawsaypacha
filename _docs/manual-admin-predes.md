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

- **El reparto de todo el contenido por estado**: qué hay en borrador, qué está publicado y qué se retiró.
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
| **Editor** | Crear y modificar contenido, **publicarlo y retirarlo** |
| **Publicador** | Todo lo del Editor, y además borrar y gestionar los datos y las capas |
| **Administrador** | Todo, incluidos los textos del sitio y los usuarios |

Conviene decirlo en voz alta en la capacitación: **quien escribe también publica**, y no hay
ningún paso intermedio en el que otra persona lo revise. Lo que salga al sitio sale con lo que
tenga escrito, así que la relectura antes de pulsar «Publicar» es la única que hay.

## Publicar contenido

Todo el contenido —medidas, normativa, noticias, videos, eventos, biblioteca— funciona igual y
pasa por tres estados:

```
   Borrador ──publicar──▶ Publicado ──archivar──▶ Archivado
      ▲                       │                       │
      └── retirar del sitio ──┘                       └── volver a borrador ──┘
```

**En el sitio público solo se ve lo que está en Publicado.** Un borrador no aparece ni buscándolo
por su dirección exacta.

El paso de estado **no se hace editando un campo**, se hace con las acciones del final del
formulario o desde la lista, marcando las filas y eligiendo la acción:

- **Publicar** — lo saca al sitio. Si lo publica otra persona, avisa por correo a quien lo
  escribió; si lo publicas tú, no te llega un correo contándote lo que acabas de hacer.
- **Retirar del sitio y devolver a borrador** — pide unas observaciones, y **esas observaciones
  van en el correo** a quien lo escribió. Es el único sitio donde se le puede explicar qué
  corregir, así que conviene ser concreto.
- **Archivar** — lo retira del sitio sin borrarlo. **Archivar es lo correcto para retirar algo**;
  borrar destruye el historial y las direcciones que ya se hayan compartido.

### Adjuntar enlaces y archivos a una noticia

Al final del formulario de una noticia, debajo de todo, hay dos bloques donde se añaden filas:

- **Enlaces** — un título y una dirección. El título es obligatorio y es lo que se lee en el
  sitio: una dirección pelada no la puede leer en voz alta ni citar nadie. Se abren en una pestaña
  nueva.
- **Archivos** — el documento y su título. Se ven al pie de la noticia como una tarjeta con el
  formato y el peso («PDF · 2,3 MB»).

El campo **Orden** decide cuál va antes; si se dejan todos en cero, salen en el orden en que se
dieron de alta. Se pueden repetir números sin que pase nada.

Se aceptan PDF, Word, Excel, PowerPoint, CSV, texto, ZIP e imágenes, **hasta 20 MB**. Si el
archivo es de otro tipo o pesa más, el formulario lo dice al guardar y no se pierde el resto de lo
escrito. Las páginas web guardadas (`.html`) y los gráficos vectoriales (`.svg`) **no se admiten a
propósito**, por seguridad: son archivos que el navegador ejecuta.

> **Un archivo adjunto queda accesible en cuanto guardas, aunque la noticia siga en borrador.** No
> es como el texto, que no se ve hasta publicar: el archivo vive en una dirección propia y quien
> la tenga puede abrirlo. La dirección no se puede adivinar —lleva un código aleatorio— pero se
> puede compartir. **No subas ahí nada reservado o bajo embargo** hasta que puedas publicarlo.

### Ejercicio de la capacitación

Crear una noticia, publicarla y comprobar que aparece en
`https://observatorio.predes.org.pe/noticias`. Después, entre dos personas: que una la retire del
sitio con una observación concreta, que la otra reciba el correo con esa observación, la corrija y
la vuelva a publicar. Esa segunda parte es la que enseña para qué sirve el campo de observaciones.

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

## Actualizar el presupuesto del PP 0068

Se sube por el mismo sitio —**Datos → Cargas de datos**— eligiendo el tipo **«Presupuesto PP 0068
por municipalidad»**. El archivo del día a día es el Excel del periodo, el mismo que llega con la
hoja `Base AAAA`: trae las filas del programa y las de presupuesto institucional, y con eso basta.

Después de importar hay **un paso más que en los otros datos**, y es a propósito:

1. **Inversión → Ejercicios.** El ejercicio nuevo aparece con la casilla **visible** desmarcada.
   Mientras siga así, la página `/inversion` muestra «información en preparación». Importar no
   publica: la revisión es de PREDES.
2. Se revisan las cifras y se marca **visible**. La página aparece al recargar.

**Si el archivo trae un devengado mayor que su PIM, la carga se rechaza entera** y el registro
enumera las filas. No es una manía del sistema: el PIM es el techo de gasto y el SIAF no deja
devengar por encima, así que un archivo así viene mal de origen y hay que pedirlo de nuevo. Lo
mismo con cualquier importe negativo. Nada se escribe hasta que el archivo esté bien.

Dos avisos que conviene leer en el registro de la carga:

- **Municipalidades «sin territorio».** Son las que no casan con el padrón de distritos, hoy cuatro
  de La Convención creadas después. **Cuentan en los totales**; lo único que no pueden es cruzarse
  con datos por distrito. Se ven en **Inversión → Entidades ejecutoras**.
- **Códigos sin proceso asignado.** Si el archivo trae una actividad o un proyecto que el catálogo
  no conoce, su importe aparece en el gráfico como **«sin clasificar»**, nunca repartido entre los
  demás. La pantalla de inicio del admin avisa de cuánto dinero está en esa situación.

### El catálogo de procesos de la GRD

**Inversión → Procesos de la GRD.** Es la tabla que decide en qué barra del gráfico cae cada sol:
cada actividad o proyecto del programa tiene asignado un proceso (estimación, prevención y
reducción, preparación, respuesta, rehabilitación o gestión transversal).

Las asignaciones que trae el sistema son una **propuesta**, y la lista lo marca en la columna
«revisado». En cuanto alguien de PREDES guarda una fila, esa asignación pasa a ser suya: **ninguna
importación futura vuelve a tocarla**. El cambio se ve en el sitio al recargar, sin volver a subir
nada.

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
  **Inversión** sí está visible.

Un cambio aquí se ve en el sitio en cuanto se recarga la página.

## Redactar una noticia desde un enlace

En **Noticias**, arriba del formulario hay dos campos: **URL de origen** y la casilla **«Procesar
con IA»**. Si la marcas y guardas, puedes dejar el resto en blanco: se leerá esa página y se
rellenarán el titular, la bajada, el cuerpo, el autor, la fecha, las palabras clave y la imagen de
portada. No hay que esperar mirando — **la pantalla se actualiza sola** en cuanto termina, y suele
tardar unos segundos.

Tres cosas que conviene decir en la capacitación:

- **Cada noticia puede usarlo una sola vez.** Después la casilla queda desactivada y se sigue
  editando a mano, como cualquier otra noticia. Si el intento falla —porque el enlace no responde o
  la página está tras un muro de pago—, no se gasta: aparece el motivo y se puede reintentar.
- **Es una propuesta, no un resultado.** Hay que leerla y corregirla antes de publicar, igual que
  los resúmenes de Biblioteca.
- **Ojo con la imagen.** La portada se trae de la página de origen, y eso **no** significa que se
  tenga permiso para publicarla. Antes de publicar hay que comprobar de quién es o sustituirla; sin
  imagen, el sitio usa la ilustración institucional y se ve perfectamente.

## Registrar una norma desde su enlace

En **Normativa** funciona igual que en Noticias, y con una ventaja: **el enlace puede ser un PDF**.
Pega en **URL de origen** la dirección de la publicación oficial —la página de El Peruano o de
gob.pe, o directamente el PDF—, marca **«Procesar con IA»** y guarda dejando el resto en blanco. Se
rellenarán el título, el número, el tipo, el ámbito, la fecha, el resumen, el análisis desarrollado,
las palabras clave y el estado de vigencia. La pantalla se actualiza sola al terminar.

Lo mismo que en Noticias —una sola vez por norma, es una propuesta y no un resultado, y ojo con los
derechos de la imagen— más cuatro cosas propias de aquí:

- **El «análisis de PREDES» lo escribes tú.** La IA no lo toca a propósito: es la nota que firma la
  organización en el listado, y ponerle un texto de máquina sería atribuirle a PREDES algo que no
  ha dicho.
- **La «URL oficial» tampoco se rellena sola.** «URL de origen» es de dónde se leyó la norma, que
  puede ser cualquier sitio; «URL oficial» es el enlace que ve el público como publicación oficial.
  Si son el mismo, cópialo tú.
- **Revisa siempre el tipo, el ámbito y la fecha.** Si la IA no pudo deducir el tipo o el ámbito los
  deja **vacíos** —a propósito: prefiere no clasificar a clasificar mal— y tendrás que elegirlos
  antes de guardar. Y cuando el documento no trae fecha visible, se pone la de hoy: casi nunca es la
  correcta.
- **Si el PDF está escaneado, no se puede leer.** Un PDF escaneado es una foto de un texto, y el
  lector configurado solo entiende texto de verdad. Aparecerá un aviso diciéndolo. Salidas: pegar el
  enlace a la versión web de la norma, o pedirle al administrador de la plataforma que cambie el
  lector a uno que reconozca imágenes (tiene coste por página, por eso no está puesto por defecto).

## Cargar fichas ACC desde un Excel

Las **Fichas de Adaptación al Cambio Climático** son las 17 preguntas del formulario que se
reparte en campo. Se pueden llenar de a una desde el admin, o cargarlas todas juntas desde un
Excel. Una ficha **no depende de ninguna medida**: es un registro por su cuenta.

En **Medidas - Fichas ACC** hay dos botones arriba a la derecha:

1. **Descargar plantilla.** Baja un Excel con las 17 columnas ya puestas y en el orden correcto.
   Cada título trae un comentario con la indicación de cómo llenarlo, y hay una segunda hoja
   **Instrucciones** con lo mismo en texto. Empieza siempre por aquí: ahorra el ida y vuelta de
   «¿qué columnas van?».
2. **Importar desde Excel.** Sube el archivo lleno. **No se guarda nada todavía**: primero
   aparece una pantalla que dice cuántas fichas van a entrar y **cuáles no, con el motivo de cada
   una**. Recién al pulsar «Importar» se guardan.

Una fila no se carga por dos motivos, y los dos se ven en esa pantalla:

- **Le falta algún dato obligatorio.** El aviso nombra la columna vacía. Los únicos tres que
  pueden ir en blanco son *Ubicación*, *Persona de contacto* y *Descripción de la práctica*.
- **El nombre de la experiencia está repetido.** El *«Nombre de la experiencia, práctica proyecto
  o programa»* tiene que ser distinto en cada ficha. Al comparar no se distinguen mayúsculas ni
  espacios de más, así que «Cosecha de agua en Ccatca» y «  cosecha DE AGUA en Ccatca » cuentan
  como la misma. Se comprueba contra lo que ya está cargado **y dentro del propio archivo**.

Las fichas que sí están bien se cargan igual: no hace falta corregir el Excel entero para
aprovechar lo que ya está listo. Corrige lo que la pantalla te señaló y vuelve a subir solo esas.

**Lo único que detiene el archivo completo es la cabecera.** Si la fila 1 no trae las 17 columnas
esperadas no se carga nada, y el aviso muestra qué esperaba y qué encontró. Es a propósito: con
las columnas cambiadas de sitio, cada respuesta se guardaría en la pregunta equivocada y las
fichas se verían bien estando mal. Si te pasa, descarga la plantilla y copia tus datos ahí.

Lo importado se edita después como cualquier otra ficha.

## Redactar una medida desde una ficha ACC

Una vez que las fichas están cargadas, no hay que volver a teclear su contenido: la medida se
redacta desde la ficha. En **Medidas → Añadir medida**, arriba del todo hay un bloque **Origen**:

1. Elige la **ficha ACC de origen** en el buscador. Escribe unas palabras del nombre de la
   experiencia y aparecerán las que coincidan. **Solo salen las fichas que todavía no se han
   usado**: cada ficha sirve para una medida y no vuelve a ofrecerse.
2. Marca **«Procesar con IA»** y pulsa **Guardar**, dejando todo lo demás en blanco.
3. La medida aparece con el título provisional «(redactando) …» y la pantalla **se actualiza sola**
   en cuanto termina — normalmente unos segundos.

Se rellenan el título, el resumen corto, el tipo de peligro, el alcance, el resultado, el distrito,
la comunidad, el contenido, las palabras clave, los actores, la fecha de implementación y el costo
referencial. Todo es editable después, como cualquier otra medida.

Cinco cosas que conviene saber:

- **Es una propuesta, no un resultado.** Léela entera antes de publicar. Presta atención sobre todo
  al **alcance** y al **resultado**: una ficha ACC describe una buena práctica, así que casi
  siempre se clasificará como «Éxito», y eso no siempre es lo que corresponde.
- **No se puede publicar a medias.** Si falta el título, el tipo de peligro, el alcance, el
  resultado o el resumen corto, al pulsar «Publicar» aparece un aviso diciendo cuáles faltan y no
  se publica nada. Tampoco se publica con el título «(redactando) …» todavía puesto.
- **Al final del contenido aparece un bloque «Contacto de la experiencia»** con el nombre, el
  teléfono y el correo que traía la ficha. **Esos datos no se le mandan a la inteligencia
  artificial** —los pone el sistema directamente—, pero **el contenido de una medida es público**.
  Antes de publicar, bórralo, o confirma con esa persona que acepta que sus datos aparezcan en el
  sitio. Al publicar sale un recordatorio.
- **Lo que quedó vacío es a propósito.** Si la IA no pudo deducir el peligro, el alcance o el
  resultado los deja **en blanco** en vez de poner cualquier cosa: prefiere no clasificar a
  clasificar mal. Lo mismo con el distrito cuando la ficha no dice de qué provincia es, con el
  costo cuando viene en otra moneda —no se convierten monedas— y con la fecha cuando no hay periodo.
- **Si la IA falla, la ficha no se gasta.** Aparece el motivo en «Registro de la IA» y puedes
  volver a marcar la casilla. Y en el registro se anota siempre lo que hay que revisar.

**No se rellenan la portada, el video, los enlaces ni «Caso destacado»**, y no es un olvido: una
ficha no trae ninguna de esas cosas, e inventarlas sería peor que dejarlas vacías. Sin portada, el
sitio usa la ilustración institucional del peligro y se ve perfectamente.

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
- **`/inversion`** — cuánto y cómo ejecuta cada **municipalidad** el presupuesto del PP 0068,
  con un mapa que colorea el territorio por PIA, PIM, devengado o % de ejecución.

### Dos descargas, para dos cosas distintas

En `/inversion` hay dos botones y conviene no confundirlos:

- **Reporte (PDF)** — el tablero tal como se ve: las cifras, las gráficas, el mapa y la tabla
  completa. Es el documento que se lleva impreso a una reunión, con membrete y fecha.
- **Excel** — solo la tabla, pero **con todas las columnas** y lista para filtrar y sumar. Es lo
  que se manda a quien va a trabajar con los números.

El PDF respeta lo que haya en pantalla: el ejercicio, la provincia, el orden de la tabla y **la
vista del mapa** (métrica y si está por distrito o por provincia). Si se quiere un reporte con el
mapa de % de ejecución por provincia, se pone así en pantalla y se descarga.

### Por qué el mapa de Inversión tiene trece distritos en blanco

No es un error ni un dato que falte. **El presupuesto lo tiene la municipalidad, no el
territorio**, y las capitales de provincia no tienen municipalidad distrital: quien gobierna ahí
es la municipalidad provincial, que gestiona el presupuesto de **toda** su provincia. Pintar ese
dinero sobre el distrito capital diría que ese distrito recibe lo que en realidad se reparte entre
todos los de la provincia.

Por eso el mapa hace dos cosas en vez de una: deja esos polígonos en blanco, y **debajo declara
cuánto dinero no está dibujado y por qué**. Si lo que se quiere es una lámina sin huecos, se
cambia el selector a **«Provincia»**: a ese nivel entra todo y no queda nada fuera.

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
| No llegan los correos del flujo editorial | Comprobar que los usuarios tienen correo en su ficha, y avisar. Ojo: publicar algo tuyo **no** genera correo, es a propósito |
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
  que pide el público, y lo que lleva semanas en borrador no se publica solo.
