# Specs — Observatorio Kallpachakuy (fase de construcción)

Especificaciones técnicas de la plataforma real, sucesora del prototipo aprobado (`prototype/`, congelado como referencia). Plataforma en línea el **13/08/2026**.

## Estado

- Fase 0 (prototipo estático) **completada y aprobada** por PREDES.
- Fase actual: construcción de `frontend/` (Vite + React + TS + MapLibre) y `backend/` (Django 5.2 LTS + PostgreSQL + Meilisearch + PMTiles), desplegados con Docker Compose.

> Las entradas `### Actualización` de más abajo son la bitácora de **lo ya corregido**. Lo que se
> sabe roto y sigue sin arreglar vive en el **tracker**, en el servidor de desarrollo: se abre el
> túnel (`ssh -L 3000:localhost:3000 …`) y se consulta en
> `http://localhost:3000/<admin>/observatorio/issues`. Al cerrarse un error, se cierra allí y entra
> aquí como una entrada nueva. El ciclo —severidades, la regla de cierre, qué se hace al cerrar—
> está en **[09-errores.md](09-errores.md)**.

### Actualización 11/08/2026 — Inversión gana su reporte en PDF

`/peligros` tenía su ayuda memoria desde el principio; `/inversion` solo podía sacar el Excel de
la tabla, sin gráficas ni mapa. El cliente pidió el mismo tipo de documento, «con las gráficas y
las tablas según se visualiza en pantalla». Alcance regional con los filtros puestos y la tabla
completa de las 116 municipalidades, ambas decisiones suyas.

**Lo que condicionó el diseño fue que WeasyPrint no ejecuta JavaScript**, así que los gráficos de
Recharts no se podían reutilizar. Se generan en SVG desde el servidor (`apps/informes/graficos.py`),
y resultó mejor que capturarlos: es vectorial —nítido al imprimir, donde un PNG queda pastoso—,
determinista y probable con `assert` sobre la propia cadena. Tiene además un efecto que no es
estético: **el PDF sigue sin imágenes rasterizadas salvo el mapa**, que es justo como las pruebas
detectan si el mapa llegó. Pasar un gráfico a PNG rompería esa prueba sin que se note.

El mapa sí necesita navegador, con su propia página de un solo uso
(`templates/informes/mapa_inversion.html`) y la misma degradación de siempre: si la captura falla,
el documento sale sin él y con el resto intacto.

Cuatro cosas que se decidieron por el camino:

- **El documento declara el dinero que su mapa no pinta.** Es ADR-D6 llevado al papel: en pantalla
  el pie está debajo del mapa, pero un PDF circula por correo sin la página que lo explica. Hay una
  prueba que lo exige.
- **El total de la tabla sale de `agregados`, y las filas de `listado`**: dos caminos distintos a
  la misma cifra, con una prueba que los compara. Una contradicción dentro de la misma página no se
  vería sin sumar 116 filas a mano.
- **La rampa de color se mudó a `apps/informes/escalas.py`**, de donde la leen el visor headless y
  la leyenda del propio PDF. Iban a ser tres copias; un mapa y su leyenda desincronizados serían un
  documento que miente sin que nada falle.
- **Sin ejercicio publicado el reporte responde 200 con un PDF de una página** que explica el
  vacío, no un 404. Un documento en blanco se leería como «no hay inversión pública en gestión del
  riesgo», que es falso.

**Y por el camino salió un fallo viejo y serio, que llevaba ahí desde la ayuda memoria.** El
coroplético provincial del reporte salía **en blanco** —contornos dibujados, leyenda correcta al
lado— y la causa no estaba en el mapa nuevo: el autoescape de Django convierte `&` en `&amp;`
dentro de `{{ … }}`, y una URL metida en una cadena de JavaScript no lleva entidades HTML. **Del
segundo parámetro en adelante se perdían todos.** Sin `nivel`, el API cae a `distrital` y devuelve
ubigeos de seis dígitos que ningún polígono provincial puede casar.

Lo grave es lo que implicaba en `/peligros`, donde el mismo patrón existía desde el principio: una
ayuda memoria pedida con filtros —`?peligros=sismo&niveles=4`— **embebía el mapa del distrito
entero**, mientras su línea de filtros decía «Peligros: Sismo · Niveles: muy alto». Un documento
que se contradice a sí mismo en la misma página, sin un solo error en el log. Nadie lo había visto
porque el caso sin filtros lleva un único parámetro y no tiene ningún `&` que escapar.

Arreglado en los dos visores: la consulta se compone con `urlencode` —que percent-codifica los
valores, y es lo que hace que `|safe` sea seguro ahí— y la URL se imprime con `|safe`. Se descartó
`|escapejs`: funciona, pero escapa `=` y `-` y deja la URL ilegible justo cuando alguien abre esa
página en un navegador para depurar, que es para lo que es pública. Tres pruebas nuevas lo fijan,
una de ellas comprobando que un valor con comillas no se sale de la cadena de JavaScript.

Cinco fallos que solo se vieron mirando el PDF renderizado, no ejecutando pruebas:

1. **Un comentario de plantilla impreso en la portada.** En Django, `{# … #}` es de **una sola
   línea**: escrito en varias, se imprime tal cual. Para eso está `{% comment %}`.
2. **Los gráficos en dos columnas se salían del margen derecho** — tienen ancho fijo, y a media
   caja no caben. Se apilaron; reducirlos habría dejado las etiquetas de los procesos ilegibles.
3. **El total se repetía en cada página**: WeasyPrint repite el `tfoot` igual que el `thead`, y un
   «Total del ámbito» debajo de seis filas se lee como si esas seis sumaran el total.
   `display: table-row-group` lo deja una sola vez, al final.
4. **Las filas se partían por el salto de página**, y su mitad de arriba aparecía vacía en la
   siguiente como si fuera una municipalidad sin datos.
5. **El coroplético desperdiciaba un tercio del ancho.** Cusco es más alto que ancho, así que en un
   lienzo apaisado se ajusta por altura. Se captura casi cuadrado y la leyenda va a su lado.

De paso se eliminó `ayuda_memoria.sello_datos()`, que no tenía ningún llamador y daba a entender
que los informes tenían invalidación de caché.

`pytest` 259/259, más las 7 marcadas `lento` —que también pasan, incluida la que exige que el
reporte traiga su mapa de verdad—. Playwright 22/22 en `/inversion`.

### Actualización 11/08/2026 — Inversión gana su mapa, y el mapa declara lo que no pinta

El cliente pidió tres cosas sobre `/inversion` tras fijar el vocabulario presupuestal (PIM = PIA ±
modificaciones, `0 ≤ devengado ≤ PIM`, avance = devengado/PIM): confirmar los once indicadores de
su hoja «Campos», un cuadro de evolución en el tiempo, y **un visor con mapa de calor por PIA /
PIM / devengado**.

Los once indicadores **estaban los once** — se auditaron uno a uno contra `apps/inversion/consultas.py`,
sin añadir ningún cálculo. Lo que faltaba era enseñarlos: el PIA institucional viajaba en el
payload y no se pintaba, la tendencia dibujaba PIM y devengado pero **no el PIA**, y proyectos vs
productos era una frase suelta. Los tres arreglados, más un cuadro bajo la línea con una fila por
ejercicio (PIA, PIM, variación, devengado, % de ejecución, saldo y fuente).

**El mapa era la parte con enjundia, y no por lo técnico.** El plan anterior lo daba por imposible
—«no hay geometrías distritales en el proyecto»—, pero ADR-A20 las había traído dos días antes y
sus llaves casan exactas con el padrón: `UBIGEO` es `Distrito.ubigeo`, `IDPROV` es
`Provincia.ubigeo`. El problema real era otro: **el presupuesto es de municipalidades y los
polígonos son de territorios**. De los 112 distritos de Cusco, 99 tienen municipalidad distrital;
los 13 que faltan son exactamente las capitales de provincia, cuya municipalidad es la provincial y
gestiona el presupuesto de toda la provincia.

De ahí **ADR-D6**: se pinta el dinero que se puede atribuir al polígono sin inventarlo, y lo que no
se puede ubicar se declara —nunca se reparte—. Volcar el presupuesto provincial sobre el distrito
capital habría pintado un distrito de oscuro con el dinero de los otros catorce, que es la misma
invención de cifras distritales que fundó ADR-D4. En 2026 eso son **S/ 44,240,618 pintados y
S/ 10,350,637 declarados al pie**, que suman los S/ 54,591,255 de la tarjeta de arriba.

Esa suma es la prueba, y hay dos que la fijan en las dos direcciones (`test_el_mapa_no_pierde_ni_inventa_un_sol`).
Existen porque **un mapa al que le falta dinero se ve exactamente igual que uno correcto**: es el
tipo de fallo que ninguna revisión visual encuentra.

Cuatro cosas más que salieron por el camino:

- **La invariante del SIAF ahora se comprueba al importar.** `devengado > PIM` e importes negativos
  rechazan el archivo entero, enumerando las filas malas en un solo mensaje. Se cumplía en las
  1,902 filas cargadas y en los dos CSV de origen, pero nadie lo estaba mirando.
- **Un polígono sin municipalidad se pinta en blanco, no en gris claro.** El primer intento usaba
  un gris que era indistinguible del tramo más bajo de la rampa — justo la diferencia que el mapa
  existe para enseñar. Se vio en la primera captura.
- **La advertencia del corte parcial se repite junto al mapa.** El banner está arriba de la página,
  pero un mapa se recorta para una lámina y viaja solo; a mitad de año, un 50 % de ejecución sin su
  contexto se lee como mala gestión.
- **El registro del protocolo `pmtiles://` se mudó a `lib/pmtiles.ts`.** Estaba en un `let` de
  módulo dentro de `MapaPeligros`, y con un segundo mapa cada componente habría registrado su
  propio `Protocol` — sin que MapLibre se queje.

Y un fallo silencioso que el propio cambio creó y las pruebas encontraron: **al haber ahora dos
`<table>` en `/inversion`**, el test del ranking empezó a leer el cuadro de evolución como si fuera
el listado de municipalidades. Las cifras por año también son números, así que ordenaba «mal» sin
que nada explotara. Los selectores del spec se acotaron a su sección.

`pytest` 238/238 (5 deseleccionadas por `lento`), Playwright 69 pasan y 4 se saltan.

### Actualización 11/08/2026 — el Excel de /peligros decía menos que la pantalla

El botón «Excel» de `/peligros` descargaba las columnas de antes de rehacer la sección: altitud,
latitud y longitud —las tres que ya se habían quitado de la ficha por ser ruido para quien
consulta exposición— y **ningún peligro**. Solo llevaba `Nivel`, el máximo tras los filtros, así
que quien abría el archivo veía que un centro poblado era «Muy alto» pero no de qué. Es justo la
columna que la tabla sí muestra en pantalla.

**Se conserva una fila por centro poblado**, que es la unidad de la tabla y del contador (3,238
en toda la región); las 10,978 clasificaciones son la otra unidad y confundirlas es el error que
el proyecto lleva evitando. Los peligros entran en **dos formas complementarias**: una columna
`Peligros` legible de un vistazo —`Sismo (4 · Muy alto); Heladas (3 · Alto)`, la traducción a
texto de la columna de la tabla— y **una columna por peligro del catálogo** con su nivel como
número, que es lo que permite filtrar «los que tienen sismo en 4» o hacer una tabla dinámica.

No hizo falta consulta nueva: la vista del export ya instanciaba el viewset con `action="list"`,
así que el `Prefetch` con `to_attr="clasificaciones_filtradas"` —mismos filtros, mismo orden que
el ícono del visor— **ya venía montado y nadie lo leía**. Se lee **sin repliegue** a propósito:
un `getattr` con defecto convertiría la pérdida futura del prefetch en una consulta por fila,
silenciosa hasta producción. Las columnas de peligro salen de `TipoPeligro`, así que un décimo
peligro entra en el Excel sin tocar código.

La prueba que había solo contaba filas, y por eso no vio nada de esto. Ahora se comprueban las
columnas, que **el nivel de cada peligro cae en su columna** —la desalineación es el fallo
probable de una tabla con columnas dinámicas, y Excel no se queja de una fila más corta—, que un
Excel filtrado no habla de lo que el mapa oculta, y que el export no consulta uno a uno.

**La altitud sale también de la ayuda memoria en PDF**, que era el último documento que la
publicaba. No es el caso de la población (ADR-A19): la altitud es un dato real del padrón y
**sigue en la base**, solo que no aporta a una mesa de incidencia. La tabla se queda en tres
columnas y los 16 mm liberados van a «Peligros clasificados», que es la que se quedaba corta.
Queda en el popup del visor, donde sí orienta sobre el terreno.

### Actualización 11/08/2026 — el visor gana los límites, y los distritos su centroide

El visor no dibujaba ninguna división política, y la falta de geometría distrital arrastraba una
aproximación: el ícono de emergencias se colocaba en la **mediana de los centros poblados** del
distrito porque no había forma de calcular su centroide.

**Se evaluó primero el WMS de GeoPerú** y se descartó, con el porqué en el spec 05 para que
nadie reabra la vía: responde rápido y con CORS abierto, pero su **WFS está bloqueado (403 en
las tres rutas)** —así que no da geometría— y **prohíbe estilos propios** («Dynamic style usage
is forbidden»), con lo que solo quedaban dos estilos, uno con etiquetas y otro con relleno gris
opaco. Y obligaría a que cada visitante saliera a un tercero en cada carga.

**`josedaniel-cb/limites-peru-geojson` (MIT) sí sirve.** Trae `UBIGEO`, y ahí está la clave: sus
112 distritos y 13 provincias de Cusco **casan exactamente** con el padrón, sin sobrantes ni
faltantes. Entra por el **mismo pipeline** que ríos, lagunas y glaciares —`capas.yaml` con
`filtro_atributo: CCDD=08`, `seed --capas`, tippecanoe—, así que **no hizo falta escribir código
para la parte visual** y, sobre todo, los tiles los sirve nuestro nginx: si el repositorio de
origen desapareciera, el observatorio seguiría igual. Provinciales visibles por defecto (13
polígonos dan contexto); distritales apagadas, porque 112 a escala regional compiten con los
símbolos de peligro.

Lo que la geometría desbloquea: **`manage.py calcular_centroides`** guarda el centroide de cada
distrito en `Distrito.lat`/`lon`, y el ícono de emergencias deja de ser una aproximación. Medido
antes de cambiarlo: la mediana se desviaba **3.4 km de mediana y hasta 27 km** en los distritos
grandes de selva (Echarate 27.5, Checacupe 24.8). Ninguno de los dos métodos sacaba el punto de
su distrito, así que no era un error — pero ahora es el punto correcto.

**El repliegue se conserva a propósito.** 111 de los 112 tienen centroide; LLUSCO no, porque es
cóncavo y su centroide de área cae fuera de sí mismo. El comando lo detecta y deja el campo
vacío antes que guardar un punto en otro distrito, y `centroides_distritales()` cae en la
mediana para ese caso. Sin esa segunda vía, el distrito perdería su ícono.

### Actualización 11/08/2026 — la ficha del centro poblado: fuera lo que no hay, dentro un mapa

Tres cosas de `/peligros/:codigo`, y la del medio arrastró medio backend.

**La columna «Tipo / Detalle» estaba muerta.** Renderizaba `p.tipo`, un campo que el API dejó
de enviar en el commit `1932527` —pasó a `peligro_slug` + `categoria_geo`— y que el tipo de TS
nunca actualizó. Mostraba «—» en las 3,238 fichas y `tsc` no podía avisar, porque el tipo
declaraba el campo fantasma. Se quita la columna y se corrige el tipo.

**La población sale del producto entero (ADR-A19).** El Excel trae una columna `POBLACION`,
pero no es un padrón que el cliente haya entregado ni respaldado. ADR-A17 ya la había retirado
como canal visual del mapa por ilegible —948 de 8,968 valen 0 y la mediana es 17 habitantes—;
ahora deja de importarse y de publicarse en las nueve superficies donde estaba: lista, ficha,
geojson, resumen, comparador, export, tiles, buscador y PDF. **El campo del modelo se conserva
vacío**: borrarlo sería irreversible y el día que llegue un padrón oficial basta con reimportar.
Una migración de datos vacía lo ya cargado, para que la base no guarde una cifra que el sitio
no respalda.

Dos efectos que había que decidir y no dejar pasar:

- El **PDF de ayuda memoria** pierde su frase de «N habitantes expuestos» y su columna. Si el
  dato no es publicable en pantalla, tampoco en un documento que va a una mesa técnica.
- El **autocompletado de lugares** ordenaba por población descendente. Habría seguido
  funcionando con todos los valores a `NULL`, degradándose en silencio; pasa a alfabético.

**La ficha gana un mapa.** Antes solo daba las coordenadas como texto. No se reutiliza
`MapaPeligros` —seis props obligatorias, ningún interruptor, y con `tipos: []` ni siquiera
dibuja los símbolos— ni se renderiza una imagen en servidor, que sería **más** costosa: el
único renderizador del repo es Chromium headless, tarda segundos por captura y obligaría a
cachear una imagen por centro poblado. Se hace un `MapaPunto.tsx` pequeño que **comparte los
íconos y la corona** con el visor: `corona()` y `desplazamientoRanura()` salen de
`MapaPeligros` a `lib/iconosPeligro.ts`, de modo que tocar la geometría cambia los dos mapas a
la vez.

De paso, la cabecera de cifras desaparece entera: con la población fuera quedaban altitud y
coordenadas, y el mapa sitúa el punto mejor que un par de decimales. Los dos datos siguen en el
API —el mapa necesita `lat`/`lon`—: es presentación, no datos.

### Actualización 11/08/2026 — las emergencias vuelven a /peligros, pero como capa aparte

ADR-A17 sacó la frecuencia de emergencias de la página y dejó por escrito que su reubicación la
decidiría el cliente. Esta es esa decisión, y **ADR-A18** la registra.

Vuelve, pero no donde estaba. Antes era una sección más colgando del mapa, y ahí el problema no
era el sitio sino la falta de separación: los filtros de exposición no podían afectarla —son 21
tipos de evento por distrito frente a 9 peligros por centro poblado, y `INCENDIO FORESTAL` es
«inducido por acción humana» en un eje y «meteorológico» en el otro— así que ajustar «Tipo de
peligro» dejaba las barras quietas y la pantalla parecía mal calculada.

Ahora es **una capa que se enciende**, con su bloque propio de dos casillas: *Ver las
emergencias* y *Agrupar por tipo de evento*. El visor marca los distritos con registro y bajo él
aparece un gráfico de barras de la provincia. **Depende solo de la provincia** —ni del distrito
ni de los checklists—, y esa independencia es lo que hace evidente, sin explicarlo, que son dos
ejes que no se mezclan.

Lo que hubo que construir, porque no existía:

- **Un agregado provincial.** El eje de ocurrencia solo estaba disponible distrito a distrito.
- **Un punto por distrito** donde colgar el ícono: el proyecto no tiene geometría distrital, así
  que se deriva de la **mediana** de sus centros poblados. Mediana y no promedio, que en los
  distritos de selva se va detrás de los caseríos dispersos por los ríos. Es una aproximación y
  consta como tal; el popup habla del distrito, no del punto.

**Dos cosas que los datos obligaron a poner en pantalla:**

- **La cobertura.** Espinar declara 77 emergencias con **1 de sus 8 distritos** registrados y
  Cusco 608 con los 8: sin decirlo, Espinar parece la provincia más tranquila de la región
  cuando lo que le faltan son los datos. El subtítulo declara «N de M distritos con registro» y
  avisa cuando la cifra subestima.
- **Que las dos agrupaciones no suman igual.** El distrito de Cusco declara sus 134 emergencias
  por familia pero no por evento (ADR-D1), así que la provincia suma 608 agrupando por tipo de
  evento y 474 por evento. No es un descuadre: es lo que la fuente sabe. El gráfico lo dice en
  vez de dejar que el total cambie al pulsar una casilla.

El símbolo del visor es único y distinto del de exposición en los tres canales a la vez
—cuadrado en vez de círculo, color fijo fuera de la escala de niveles, e ícono que no es ninguno
de los nueve peligros—: compartir cualquiera lo habría hecho leerse como un décimo peligro.
`FrecuenciaEmergencias.tsx`, la versión por distrito que quedó huérfana en agosto, se elimina.

### Actualización 10/08/2026 — el visor mostraba un peligro de cada siete

Ajustes al rediseño anterior, pedidos al recorrerlo ya en funcionamiento. El de fondo: **el
mapa dibujaba un solo ícono por centro poblado**, el del peligro de mayor nivel, y los demás
quedaban escondidos en el popup. No era un problema de orden de pintado —solo se dibujaba uno—
y escondía casi todo: 2,372 de los 3,238 centros poblados clasificados tienen tres o más
peligros, y el máximo es siete.

Ahora cada punto los muestra **todos**, en corona sobre su ubicación, cada ícono con el color
de su propio nivel. Son nueve capas `symbol`, una por ranura: MapLibre dibuja un símbolo por
capa y feature, así que no hay manera de que una sola itere sobre una lista. La posición sale
de un `match` sobre el número de peligros, porque tampoco sabe construir un par (x, y) a partir
de dos expresiones. Un punto de 2 px marca el centro, que con la corona queda vacío y entre
centros poblados vecinos dejaba de verse de quién era cada ícono.

La tabla pasa a `Distrito · Centro poblado · Peligros`, con todos los peligros listados y una
leyenda de color encima; paginada de 20 en 20 con «Ver más». Y hay un botón «Reiniciar» que
recarga la ruta limpia.

**Dos fallos de paginación que salieron al bajar a 20 filas** —el segundo llevaba ahí desde el
principio, y ninguno de los dos avisaba:

- **El orden del API era parcial.** Ordenaba por `(nivel, nombre)`, y el nombre **no es único**:
  770 se repiten en el padrón, «PUCARA» 21 veces. Con `LIMIT`/`OFFSET` sobre un orden parcial
  PostgreSQL no garantiza nada entre consultas, así que una fila podía salir en dos páginas y
  otra en ninguna. Lo visible era la tabla repitiendo centros poblados; lo grave, los que se
  perdían. Se cierra el orden con `codigo`.
- **El cliente archivaba cada respuesta bajo el número de página equivocado.** Al avanzar hay al
  menos un render en que `pagina` ya es la nueva y el estado todavía trae la anterior —si la URL
  está en caché ni siquiera se pasa por `loading`—, de modo que las filas de una página se
  guardaban como si fueran de la siguiente. Además la acumulación concatenaba, que no es
  idempotente. `useApi` pasa a decir **de qué URL** salieron sus datos y `useApiPaginado` guarda
  por página, comprobando que la respuesta sea la que pidió. Afectaba a las siete rutas
  paginadas del sitio, no solo a /peligros.

### Actualización 10/08/2026 — /peligros vuelve a responder una sola pregunta

La revisión partió de una sospecha del cliente: que la data de `/peligros` estaba mal procesada.
**No lo estaba.** Recalculadas las dos bases desde cero contra los Excel originales, las cifras del
sitio coinciden exactamente: 10,978 clasificaciones, 3,238 centros poblados clasificados,
distribución por nivel máximo {1: 31, 2: 253, 3: 922, 4: 2,032}, y los nueve totales por tipo. Lo
que estaba mal era **la pantalla**, y de tres maneras.

**Se mezclaban los dos ejes de la fuente.** `Base_Nivel Peligro_CCPP` mide exposición (por centro
poblado, 9 peligros) y `Base_Frecuencia_Peligro` mide ocurrencia (por distrito, 21 tipos de evento).
No son convertibles —`INCENDIO FORESTAL` es *inducido por acción humana* en una y *meteorológico* en
la otra— y el panel de emergencias, embebido bajo el mapa, no reaccionaba a los filtros de la
página. Ajustar «Tipo de peligro» y ver las barras quietas se lee como un cálculo roto. **ADR-A17**
saca la frecuencia de esta ruta; su modelo, importador, endpoints, export, comparador y PDF quedan
intactos, y dónde reubicarla lo decide el cliente.

**Los filtros no dejaban preguntar lo que la gente pregunta.** Un peligro a la vez y un umbral de
«nivel mínimo». Ahora son checklists: varios peligros simultáneos, y niveles sueltos con su nombre
—Muy alto, Alto, Medio, Bajo—, de modo que «Muy alto y Bajo sin lo de en medio» pasa a ser
expresable, que antes no lo era. El API acompaña con `peligros=`/`niveles=` en CSV; `peligro` y
`nivel_min` sobreviven traducidos por un parser único, porque hay ayudas memoria compartidas con
esas URL.

**Los resultados vivían dentro del panel de filtros** y se leían como una leyenda del mapa. Salen
al lado, como grilla por tipo de exposición. El hallazgo que la hace posible sin ambigüedad: dentro
de una fila, «clasificaciones» y «centros poblados» **son la misma cifra**, porque
`unica_clasificacion_ccpp_peligro` impide dos filas del mismo peligro en un centro poblado. La
diferencia de 3.4× solo aparece al sumar la columna, y el pie declara las dos.

**En el mapa, la población dejó de ser un canal visual.** El cliente pidió no usarla; la fuente sí
la trae, pero 948 de los 8,968 centros poblados valen 0 y la mediana es 17 habitantes, así que el
tamaño no distinguía nada y además hablaba de algo distinto del número del mismo círculo. El
diámetro pasa a leer el mismo conteo que el número, y el canal que queda libre lo ocupa el **tipo
de peligro**, dibujado como ícono; el color se reserva al nivel. Los íconos salen del catálogo
(`TipoPeligro.icono`, editable en el admin), no de una tabla en el frontend.

De paso, dos fallos silenciosos que aparecieron al tocar esto:

- **El popup del mapa nunca mostró los peligros de un centro poblado.** Leía `p.clasif` —una
  propiedad *de grupo*, inexistente en un punto suelto— y esperaba unas claves que el API nunca
  envió, así que siempre caía en «sin clasificación registrada», también sobre los 3,238 que sí la
  tienen. Nada fallaba.
- **El selector de distrito se salía del panel de filtros** y se superponía a los resultados: el
  breakpoint `sm:flex-row` mira el ancho de la *ventana*, no el del contenedor de 280 px, y un
  `<select>` sin `min-w-0` no encoge por debajo de su opción más larga.

Y una trampa del visor que ahora está en el spec 05: sin `icon-allow-overlap`, MapLibre descarta por
colisión la mayoría de los símbolos **sin emitir un solo error**, y la capa `symbol` hay que añadirla
después de registrar las imágenes o escupe un error por punto y no pinta nada.

### Actualización 10/08/2026 — Inversión gana ficha, comparación y paginado

Tres cosas que el uso reclamaba en cuanto la ventana tuvo datos: **comparar ejercicios** (había
cinco años cargados y solo se veían de uno en uno), **una ficha por municipalidad** (el detalle
por actividad estaba en la base y no se podía consultar) y **paginar** la tabla, que servía sus
116 filas de golpe.

**El «ranking» no era un ranking.** Ordenaba en el cliente, y en cuanto la tabla se pagina eso
ordena solo lo que ya está cargado. El listado se va a `/api/inversion/entidades/` con el sobre de
DRF y el orden se resuelve en SQL — **con desempate por código de entidad**, que no es cosmético:
sin un orden total, dos filas empatadas salen en distinto orden en dos consultas y la paginación
repite unas y se salta otras sin que nada falle a la vista. Hay una prueba que recorre las páginas
de una en una y exige que cada municipalidad aparezca exactamente una vez.

**La comparación va en su propia vista** (`?vista=comparar`) y no como columnas de la tabla del
ejercicio. **ADR-D5** registra la decisión delicada: el Δ de % de ejecución **se muestra aunque uno
de los dos ejercicios sea un corte parcial**, marcado, en vez de suprimirse. Un 47.7 % de medio año
contra un 86.4 % de año cerrado no es una caída, y ocultarlo empuja a calcularlo fuera de la
plataforma, donde ya nadie pone la advertencia. La marca viaja en el dato (`comparable`), la
leyenda va pegada a la tabla y el Excel lleva una columna «Comparabilidad» fila a fila, porque el
archivo viaja solo por correo.

**Los filtros se mudan a la URL.** Era la condición para que la vista de comparación fuera
enlazable y para que volver de una ficha no devolviera al ejercicio por defecto. La prueba E2E de
ese recorrido fue la que destapó que `backTo` era una ruta fija y perdía los filtros.

Dos trampas que quedan escritas en el plan de pruebas, porque las dos hacían pasar un test que no
comprobaba nada: `esperarApi` casa **por subcadena**, así que pedir `/api/inversion/` atrapaba la
respuesta de `/api/inversion/entidades/` —cuyo cuerpo no tiene `disponible`— y el test daba por
vacía una ventana llena; y la espera hay que armarla **antes** de `goto`, porque la respuesta puede
llegar antes del `load` y entonces `waitForResponse` no la ve nunca.

De paso, dos arreglos: el importador no rellenaba el nombre de las clasificaciones que la semilla
ya había creado, así que las 30 actividades conocidas se mostraban con su código; y la tarjeta de
cifra, duplicada en dos rutas, se promueve a `components/KPI.tsx` antes de que la ficha fuera la
tercera copia.

### Actualización 10/08/2026 — Inversión deja de estar diferida, y su unidad es la municipalidad

Llegó la data que ADR-D3 estaba esperando: `Base_Prespuesto_PP0068_cusco_final.xlsx` (corte
2026-06, 119 pliegos) y la serie 2022-2025 reconstruida desde el comparativo del MEF. **ADR-D4**
la implementa y, al hacerlo, corrige la unidad que el spec 01 daba por buena.

**La unidad es la entidad ejecutora, no el distrito.** `InversionDistrito` era herencia del
prototipo. Quien tiene PIA, PIM y devengado es la municipalidad, y una provincial gestiona
presupuesto de toda su provincia: repartirlo entre sus distritos para encajar en el modelo
anterior habría inventado cifras distritales que ninguna fuente respalda.

**El reparto por procesos de la GRD se clasifica por actividad, no por producto.** Fue una
medición, no una preferencia: a nivel de producto, «3000001 Acciones comunes» concentra el 34.6 %
del PIM municipal de 2026 y los proyectos de inversión el 40.7 %, así que tres cuartas partes del
dinero acababan en dos cajones que no dicen nada. Las 30 actividades del programa sí nombran el
proceso. Los proyectos se clasifican por el proyecto y no por su acción de obra, porque
«expediente técnico» o «supervisión y liquidación» se repiten en obras de procesos distintos.
Con las 30 sembradas, «sin clasificar» sale en **cero** sobre los datos reales.

Se añade un sexto proceso, `gestion_transversal`, sobre los cinco que pide la hoja «Campos» del
cliente: sin él, las tres actividades de acciones comunes —monitoreo del programa, instrumentos
estratégicos, asistencia técnica, el 15.8 % del PIM— habría que empujarlas a un proceso que no son.

Tres cosas que la implementación dejó escritas en el dato y no en un comentario:

- **`es_parcial` viaja en el payload.** El 47.7 % de ejecución de 2026 es de medio año contra un
  PIM anual, y la advertencia no puede depender de que la interfaz se acuerde.
- **Un porcentaje que no se puede calcular es `null`, no `0`.** Una municipalidad sin total
  institucional no tiene un 0 % de su presupuesto en el 0068; en pantalla se pinta «—».
- **Importar no publica.** El ejercicio nace oculto y el aviso dice dónde se enciende, así que el
  estado vacío de la ventana pasa de ser el de una sección diferida al de un ejercicio en revisión.

Dos hallazgos que hay que devolver al cliente: el Excel trae **dos filas de presupuesto
institucional para Pillpinto y ninguna para Yaurisque** —la segunda cuadra en magnitud con
Yaurisque, pero repararlo por posición sería adivinar sobre datos ajenos, así que se descartan las
dos y esas municipalidades quedan sin denominador—, y **cuatro municipalidades de La Convención**
no casan con el padrón de distritos porque se crearon después.

El mapa coroplético del diseño original queda fuera: no hay geometrías distritales en el proyecto.
Toca `_specs/00`, `01`, `02`, `03`, `06` y `08`.

**Ampliación del mismo día.** Auditada la ventana contra la lista de «Campos o indicadores
requeridos» de la hoja 2 del Excel del cliente, faltaba exponer uno de los once: el *presupuesto
total institucional*. El PIA y el devengado institucionales se importaban y se guardaban desde el
principio, pero nunca salían —ni en el payload, ni en el Excel, ni en pantalla—, y del PIM solo se
publicaba el ratio. Ahora los tres viajan por entidad y agregados, con la regla de que **el total
y su porcentaje suman las mismas entidades**: publicar un total institucional que no cuadre con el
porcentaje de al lado es el mismo error que inflar el porcentaje mezclando universos.

### Actualización 10/08/2026 — el número de los grupos del visor no se movía con los filtros

Salió de una pregunta del dueño del proyecto: «los círculos con número, ¿qué cuentan?». Contaban
centros poblados —`point_count` de MapLibre— y ahí había dos problemas encadenados.

El de fondo es que **el filtro nunca llegaba al mapa**. `anotar_nivel` solo *anota* el nivel;
únicamente descarta filas cuando recibe `clasificados=1`, y ese parámetro lo manda la tabla pero no
`/ccpp/geojson/`. Es deliberado —el visor conserva los que no cumplen para pintarlos en gris, porque
ausencia de dato no es ausencia de riesgo— pero significaba que con «Heladas · nivel 4» puesto el
grupo seguía diciendo exactamente lo mismo que sin filtros, mientras la tabla de al lado ya había
encogido. Dos cifras contradictorias en la misma pantalla, y ninguna prueba lo veía porque las de
API comprobaban el recorte de la tabla y las E2E comprobaban que el mapa pintara.

El segundo es de lectura: un «3» sobre un mapa de peligros se entiende como «aquí hay 3 peligros»,
no como «3 pueblos». Con lo cual el número más visible del visor decía una cosa y se leía otra.

Se resolvió moviendo el número a la otra unidad (ADR-A16). El endpoint expone ahora
`clasificaciones` por punto —cuántas sobreviven a los filtros, que la vista ya calculaba para el
desglose del popup, así que no hay consulta nueva— y el cluster las suma. El tamaño pasa a sumar la
población **de los que aportan alguna**, para que número y diámetro hablen del mismo conjunto, con
repliegue a la población total cuando el grupo no aporta ninguna: encogerlo a nada lo escondería
justo donde falta información. El color se queda como estaba, en el peor nivel del grupo. Un grupo
sin ninguna clasificación se dibuja sin número, porque un «0» se leería como «evaluado, y sin
peligro».

El coste es que las dos unidades ahora conviven en la misma vista, así que la cabecera de la tabla
las muestra juntas y rotuladas: `N CCPP · M peligros clasificados · K sin clasificación`. `M` sale
de `por_peligro` del resumen y es exactamente lo que da sumar los círculos, de modo que el número
del mapa cuadra con algo escrito. Hay una prueba que fija esa igualdad, con la única diferencia
legítima descontada: el geojson excluye los centros poblados sin coordenadas y el resumen no.

Se añadió también un conmutador «Mostrar sin clasificación» en el control de capas, porque con el
filtro puesto los grises son mayoría y tapan lo que se busca. Va por `setFilter` y no por `setData`
a propósito: los agregados del grupo ya dejan fuera a los sin dato, así que esconderlos no cambia
ningún número. Ojo con el gotcha, que queda escrito en 05 y en el código —ocultarlos **no**
reagrupa: un grupo con 3 sin dato y 2 clasificados sigue siendo un círculo en el mismo sitio,
rotulado 2—.

Verificado con `pytest tests/test_api_peligros.py` (24 en verde, tres pruebas nuevas), `npm run
lint` y la suite E2E de `/peligros`.

### Actualización 10/08/2026 — el spec mandaba al modo lento para el día a día

El spec 07 describía **dos** modos de compose cuando ya había tres, y para «probar producción en
local» remitía a un mecanismo que había dejado de existir: levantar sin override y con
`SITE_DOMAIN=localhost`. Eso lo sustituyó `compose.local.yml`, que el spec no mencionaba en ningún
sitio. La misma frase obsoleta estaba repetida en la cabecera de `compose.dev.yml`, que es donde uno
la lee.

La consecuencia no fue un fallo sino un coste diario: siguiendo la documentación se acaba trabajando
en `compose.local.yml`, donde el código entra por `COPY` y **cada cambio pide `--build`** —y en el
frontend, además, relanzar el contenedor de un solo uso que publica `dist/`—. El modo con el código
montado y recarga en caliente, `compose.dev.yml`, llevaba todo el tiempo en el repositorio.

Lo que hacía difícil verlo es que los tres modos se parecen en la superficie y se diferencian en una
sola cosa: **de dónde sale el código que corre**. El spec ahora abre con esa tabla y describe los
tres, con dos advertencias que antes no estaban en ningún sitio: que comparten nombre de proyecto y
hay que bajar uno antes de levantar otro —al pasar a desarrollo, `nginx` no se detiene solo, porque
`profiles: ["prod"]` solo impide *arrancarlo*, y se queda sirviendo en el `:80` el bundle viejo de
`web_dist` contra el backend nuevo—, y que el frontend **no se puede montar** en su contenedor:
`frontend` no es un servidor sino un `alpine` de un solo uso que vuelca `dist/` en el volumen y
termina, así que en desarrollo lo compila Vite en el host.

De paso se corrigió la tabla de servicios, que atribuía al servicio `frontend` un «perfil build» que
no existe: en `compose.yaml` no tiene `profiles`, solo `restart: "no"`; quien le pone
`profiles: ["prod"]` es el override de desarrollo.

Al verificar el modo local salió un cuarto desajuste, este sí de comportamiento: `compose.local.yml`
**no fijaba `DEBUG`** y lo heredaba de `backend/.env`, mientras que `compose.dev.yml` sí lo fuerza a
`True`. O sea que el modo que existe para simular producción corría con `DEBUG=True` y servía la
traza de depuración de Django en un 404 —una de las cosas que tendría que estar comprobando—, y ser
fiel dependía de acordarse de editar el `.env`. Ahora lo fija a `False`, junto a las otras variables
que ya sobreescribe. `ALLOWED_HOSTS` ya traía `localhost`, así que no hizo falta nada más.

Verificado sobre `compose.local.yml`: el 404 sale limpio, y la suite E2E contra el bundle servido por
nginx queda en 56 pruebas en verde y 6 saltadas por condición, incluida la del PDF con mapa —la que
ejercita `RENDER_MAPA_BASE_URL`—. De paso quedó a la vista que la prueba del selector de mapa base se
salta en escritorio y en móvil porque su localizador no encuentra el control: esa función no está
cubierta hoy. Pendiente de abrir en el tracker.

### Actualización 05/08/2026 — el sitio no se recuperaba solo de un cuelgue

`restart: unless-stopped` cubría que un proceso muriera, y nada más. El fallo contrario —gunicorn
con sus workers bloqueados, vivo y sin atender— dejaba el contenedor en `Up`, el sitio devolviendo
timeouts y a nadie haciendo nada, porque **Compose no reinicia un contenedor «unhealthy»**: los
healthchecks solo informan. Y `backend`, `worker` y `nginx` —la ruta que ve el visitante— no tenían
healthcheck ninguno.

Se cubre con cuatro piezas, y lo que las hace correctas es lo que **no** hacen:

- **`GET /api/salud/`** (spec 02) mide *liveness*, no dependencias: responde 200 aunque PostgreSQL o
  Meilisearch estén caídos, y lo declara en el cuerpo. Si fallara por ellos, una caída de la base
  marcaría el backend «unhealthy» y el vigilante lo reiniciaría en bucle, sin arreglar nada
  —reiniciar el backend no levanta la base— y borrando el rastro. Va exenta de throttling porque con
  `interval: 10s` son 360 peticiones/hora contra un techo de 1000, y un 429 provocaría reinicios sin
  que pasara nada. Es también por lo que no se reutilizó `/api/docs/` ni `/api/schema/`.
- **Healthchecks** de `backend` y `nginx`. El del backend lleva `start_period: 90s` porque el
  entrypoint corre `migrate` y `meili_setup` antes de gunicorn; sin margen, cada despliegue nacería
  «unhealthy» y acabaría reiniciado a media migración.
- **`deploy/vigilar-contenedores.sh`** en el cron del anfitrión, con **tope de 3 reinicios por hora
  y servicio**: un reinicio que no arregla el problema no puede volverse un bucle que impida
  diagnosticarlo. Corre fuera de Docker y no como contenedor `autoheal` porque esa imagen exige
  `/var/run/docker.sock`, que es root del anfitrión cedido a un contenedor en una máquina pública.
- **`deploy/comprobar-sitio.sh`**, para otra máquina: solo `curl`, sin Docker ni SSH ni
  credenciales. Cubre el punto ciego insalvable del vigilante local —si el servidor cae, cae con
  él— y lo que solo se ve desde fuera: DNS, firewall y los días que le quedan al certificado.

**El worker queda fuera del reinicio automático**, y esto no contradice la doctrina de
`meili_estado` sino que la aplica: reindexar por tu cuenta de madrugada destruye información;
reiniciar un servidor web colgado no destruye nada. Pero matar un worker a mitad de una importación
de 10,978 filas sí puede dejar el dato peor que parado, así que ahí hay aviso —`manage.py
cola_estado`— y no remedio.

Dos cosas encontradas al construirlo, las dos comprobadas contra el servidor:

- **`_docs/despliegue.md` documentaba `ALLOWED_HOSTS` sin `localhost`.** La sonda pide
  `http://localhost:8000/` desde dentro del contenedor y Django responde **400** a cualquier `Host`
  que no esté en la lista: con la configuración documentada, el healthcheck habría fallado siempre
  y el vigilante habría reiniciado el backend en bucle. En el servidor de PREDES, no en este.
- **django-tasks-db no usa `NULL` para «sin retraso»**, usa el centinela `9999-01-01`
  (`get_date_max()`). Un filtro propio con `run_after__isnull=True` no casa con ninguna fila y deja
  el vigilante de la cola ciego **sin dar ningún error**. Lo destapó una prueba que falló; se
  corrigió reutilizando el `.ready()` de la propia librería, que es la definición que aplica el
  worker.

Verificado de punta a punta: `docker compose pause backend` → «unhealthy» en 5 s → reiniciado por el
vigilante → sitio en 200; `docker compose stop db` → `/api/salud/` responde 200 con
`"base": "sin respuesta"` y el contenedor **sigue sano**; y al cuarto intento seguido el vigilante
deja de reiniciar y registra que llegó al tope.

### Actualización 05/08/2026 — el tracker se puede publicar en `/gitea`, sin túnel

Al túnel SSH se le añade un segundo modo: `compose.tracking-publicado.yml` engancha el tracker al
nginx del sitio y lo sirve en `/gitea` del dominio del API. Un solo comando en cada sentido, sin DNS
ni certificado nuevos, y la `location` está siempre puesta.

**La decisión que importa es la dirección del acoplamiento.** Es el tracker el que se engancha a la
red de la aplicación, y nunca al revés: si fuera nginx quien se uniera a una red del tracker declarada
`external`, el sitio entero dejaría de arrancar el día que esa red faltara. Y como el destino va en
una variable con el resolver de Docker, nginx lo resuelve en cada petición. Comprobado con el tracker
apagado: `/gitea` da 502 y `/`, `/api/salud/` y `/search/health` siguen en 200. El sitio no depende
del tracker, y eso no es una promesa sino una prueba.

La subruta se eligió sobre un subdominio propio por no pedir DNS ni reemitir el certificado,
**sabiendo que la documentación de Gitea la desaconseja** —«not widely used and may have some issues
in rare cases»—. Por eso la `location` copia su bloque literal, con el doble `rewrite` que devuelve el
URI sin decodificar para no romper los `%2F`, y con `proxy_pass …$uri` porque con una variable en el
destino nginx deja de sustituir el prefijo. Es el mismo motivo por el que `/search/` necesitó su
`rewrite` en su día. Tampoco vale `proxy-comun.inc` aquí: fija `Connection ""` y con eso Gitea pierde
el upgrade a websocket.

Verificado en local contra `compose.local.yml`, no solo configurado: login por la subruta, listado de
issues, los assets sirviendo desde `/gitea/assets/` sin chocar con los de la SPA, los dos adjuntos de
un issue descargando enteros, y el `limit_req` cortando a la novena petición seguida al login sin
afectar al resto del sitio. Queda sin probar el caso de las URIs con `%2F`: el repositorio de Gitea
está vacío y no hay ramas que lo ejerciten.

**ADR-A15 se reescribe por tercera vez**, y ahora recoge el riesgo aceptado: publicado en
`predes.org.pe` esto es un login expuesto a internet en el dominio del entregable, para un sistema que
PREDES no sabe que existe. Se advirtió, se decidió publicarlo igual, y se hace endurecido: límite de
30 peticiones por minuto, sin registro, sin anunciar la versión, y con un `allow`/`deny` por IP
preparado y comentado por si más adelante se quiere recortar la exposición.

### Actualización 05/08/2026 — el tracker se muda al servidor, y se trabaja por número

El tracker nació en el portátil, y eso fabricaba el problema que venía a resolver: en cuanto se
consultara desde otra máquina habría **dos listas de pendientes divergiendo**. Ahora hay una sola, en
el servidor de desarrollo (`somosiadigital.com`, no la producción de PREDES), y se llega por túnel:
`ssh -L 3000:localhost:3000`. Sigue publicando solo en `127.0.0.1`, así que no hace falta certificado,
ni vhost de nginx, ni abrir un puerto. Es también la razón de que su `ROOT_URL` siga siendo
`http://localhost:3000/`: por el túnel, esa es la URL correcta. **ADR-A15 se reescribió**, porque
decía literalmente que no se desplegaba en el servidor.

Los issues no viajan en el repositorio —viven en el volumen sqlite— y se mudan copiando el volumen
entero, no exportando por el API: uno de los issues ya tenía una imagen adjunta y el export la habría
dejado atrás.

Y para trabajar uno, `/issue N`, o `/issue 6 3 1` para varios en un solo plan. Sin etiqueta de cola
ni asignación, y no por simplificar: **el MCP no lee asignados** —`list_issues` filtra por etiqueta,
hito, estado y fechas, y `issue_read` ni siquiera devuelve el campo; puede escribirlos, no leerlos—.
Descartada esa vía, una etiqueta de cola tampoco aporta: es estado que hay que sincronizar a mano, y
este tracker existe justamente porque el estado sincronizado a mano se desincroniza. El número del
issue es toda la instrucción necesaria.

Dos bordes que salieron probando contra el servidor, los dos escritos en el propio comando:
`issue_read` de un número inexistente **no da error, devuelve vacío**, y un issue abierto desde la web
llega sin etiquetas y sin línea de «Prueba de cierre», así que hay que proponerlas en el plan en vez
de tratarlo como una ficha rota.

`.claude/settings.json` se versiona junto a `.mcp.json` y lleva `enabledMcpjsonServers`, que es lo que
permite que el servidor de Gitea se habilite solo tras un `git pull` en una máquina nueva. Estaba en
`settings.local.json`, que el gitignore global ignora, y por ahí el montaje no era reproducible.

### Actualización 04/08/2026 — los errores abiertos se mudan a un tracker

La tabla de errores abiertos de `09-errores.md` se sostenía en que alguien la mantuviera sincronizada
a mano en tres documentos —ella misma, este README y `_docs/despliegue-entorno-desarrollo.md`—, y ya
había dejado un rastro de que eso no funciona: `seguridad-comun.inc` remitía a «E-005 en
09-errores.md» y E-005 llevaba días cerrado y fuera del archivo. Un puntero a una fila que ya no
existe es peor que ningún puntero. Y uno de los siete errores abiertos, E-003, era del propio
registro: la bitácora no está en orden cronológico.

Ahora hay un **Gitea local** en `compose.tracking.yaml` con los siete abiertos migrados íntegros,
prosa incluida, etiquetados por severidad y área. Tres decisiones que no son obvias:

- **Proyecto Compose independiente**, no un override de `compose.yaml`. Como override, un `down
  --remove-orphans` sin acordarse del tercer `-f` se llevaría el tracker por delante; y
  `vigilar-contenedores.sh`, que filtra por proyecto, lo metería en su bucle de reinicio sin querer.
- **Solo `127.0.0.1`, nunca en el servidor.** Es una herramienta de desarrollo: no se despliega, no
  entra en el entregable y no añade una pieza más que PREDES tenga que operar y respaldar. Ese es el
  mismo criterio con el que se descartó Caddy en ADR-A6bis.
- **El identificador `E-NNN` sobrevive en el título del issue**, porque hay comentarios en el código
  que citan errores por ese número.

Lo gestiona el servidor MCP oficial de Gitea, declarado en `.mcp.json`. El token no está en ese
archivo —viaja por `--env-file` desde `deploy/gitea/token.env`, que git ignora—, lo que permite
versionar la configuración sin filtrar credenciales, y lleva solo tres alcances:
`write:repository,write:issue,read:user`. El arranque (`deploy/gitea/inicializar.sh`) es idempotente
y usa autenticación básica precisamente para no tener que ampliarlos: crear un repositorio por API
exige `write:user`, que el MCP no necesita para nada.

Lo que **no** cambia, y es lo importante: la regla de que un error reproducible nace con una prueba
que falla y se cierra cuando esa prueba pasa. Cada issue lleva esa prueba escrita al pie. Y al
cerrarse, sigue entrando aquí como una entrada de bitácora, que es lo que queda en el repositorio
cuando nadie levante el contenedor. `09-errores.md` se queda con el ciclo y pierde la tabla.

### Actualización 04/08/2026 — primer despliegue real: seis cosas que solo se ven con un dominio

El Observatorio se desplegó por primera vez contra un servidor y un dominio públicos
(`observatorio.somosiadigital.com`, entorno de desarrollo en servidor propio; ver
`_docs/despliegue-entorno-desarrollo.md`). Ejecutar el procedimiento de `_docs/despliegue.md` de
principio a fin, en vez de leerlo, encontró seis defectos. **Cinco eran invisibles desde local**, y
los cuatro primeros habrían bloqueado el pase de PREDES exactamente igual.

- **El certificado que se emitía no era el que nginx buscaba.** El paso documentado emitía con
  `certonly -d observatorio… -d obs…`, que crea **una sola** lineage nombrada con el primer `-d`;
  pero el bloque del API pedía `/etc/letsencrypt/live/obs…/fullchain.pem`, que con ese comando no
  existe nunca. nginx habría abortado con `cannot load certificate`. Ahora los dos bloques 443 leen
  la misma lineage y el comando la fija con `--cert-name`, para que no dependa del orden de los
  argumentos. El mismo fallo estaba repetido en `despliegue-sin-docker.md`, y también se corrigió.

- **Nada recargaba nginx tras renovar el certificado**, aunque `compose.yaml` lo afirmaba en un
  comentario y el spec 07 lo daba por hecho. certbot habría renovado sobre el día 60 y nginx habría
  seguido sirviendo el viejo hasta caducar el 90. Se implementó en
  `deploy/nginx/docker-entrypoint.d/40-recarga-periodica.sh`. Va ahí y no en un `command:` de
  compose porque el entrypoint de la imagen solo ejecuta esos scripts —envsubst incluido— si el
  primer argumento es `nginx`: un `command` con `sh` habría saltado la generación de plantillas.

- **Dos comandos del runbook no hacían nada.** `docker compose run --rm certbot renew` sin
  `--entrypoint certbot` cae en el bucle de renovación e ignora los argumentos; y `renew` sin
  `--webroot -w /var/www/certbot` reusa el `standalone` de la primera emisión, que choca con nginx
  en el puerto 80. Los dos están corregidos y **comprobados con `--dry-run` contra Let's Encrypt**.

- **La sincronización de la búsqueda no funcionaba. Nunca.** `manage.py meili_estado` daba los tres
  índices editoriales a cero después de sembrar, y la medición en el servidor fue tajante:
  `post_save.receivers` tenía **una sola entrada, con su referencia débil ya muerta**, y un `save()`
  no encolaba nada. La causa es que `@receiver` conecta con referencia **débil** por defecto y los
  manejadores de `apps/core/signals.py` eran funciones locales de `_registrar`: el recolector se los
  llevaba en cuanto la función retornaba. Peor con `dispatch_uid`, porque la entrada muerta se queda
  en el registro con su clave y un segundo `conectar()` la ve ocupada y no vuelve a conectar.
  Arreglado con `weak=False`. El efecto era el que el propio archivo dice evitar, y de la forma más
  silenciosa posible: **lo publicado se ve en su página y no aparece al buscarlo**.

  No se reproduce bajo pytest —ahí los manejadores siguen vivos—, así que la prueba de
  `backend/tests/test_señales_meili.py` ataca la causa y no el síntoma: exige que los receptores no
  se guarden como `weakref`. Falla sobre el código anterior y pasa sobre el nuevo.

- **El dominio de la SPA no enviaba ninguna cabecera de seguridad** (era E-005): ni HSTS, ni
  `nosniff`, ni `Referrer-Policy`, ni en la portada ni en el JavaScript del bundle. `ssl-comun.inc`
  las declaraba a nivel `server`, pero **nginx descarta los `add_header` heredados en cuanto una
  `location` declara uno propio**, y las cinco que declaran su `Cache-Control` o sus cabeceras CORS
  se las comían. Se sacaron a `seguridad-comun.inc` y se incluyen también en esas cinco. Medido
  antes y después con `curl -sI`.

Y un cambio de fondo, que es la razón de que este despliegue no ensuciara el repositorio: **los
dominios ya no están escritos en ninguna parte del código**. `server_name`, las rutas del
certificado y el origen de CORS se generan al arrancar con envsubst, desde `SITE_DOMAIN` y
`API_DOMAIN` del `.env` de la raíz —la variable `SITE_DOMAIN`, que hasta hoy no la consumía nadie—.
Se generan **fragmentos incluidos** y no el archivo entero a propósito: si el directorio de salida
no fuera escribible, el script de la imagen deja un ERROR en el log y **sigue adelante**, y con el
archivo completo eso dejaría a nginx sirviendo su página de bienvenida sin un solo bloque 443. Con
fragmentos, el mismo fallo es un `include` inexistente y nginx no arranca.

Quedan abiertos, anotados y no corregidos: E-006 (caché declarada y nunca usada), E-007
(`--solo-catalogos` se come `--demo`) y E-008 (`ssl_stapling` ya no aplica). Los tres viven ahora en
el tracker, con su ficha completa; el ciclo está en [09-errores.md](09-errores.md).

Y un séptimo hallazgo, del mismo día y de la misma naturaleza —documentación que describe algo que
no basta—: **correr las E2E en el servidor exigía un paso que la guía no mencionaba.** `README.md` y
`desarrollo.md` decían `npm install && npx playwright install chromium`, y faltaban las librerías de
sistema de Chromium. Sin ellas las 62 pruebas fallan con `browserType.launch: Target page, context
or browser has been closed`, que se lee como si el sitio estuviera caído. Y no se veía venir, porque
en Debian/Ubuntu `--with-deps` las instala solo: **Playwright no soporta oficialmente la familia
RHEL** y ahí no instala nada, solo sabe de `apt`. Ahora lo hace `e2e/instalar-dependencias.sh`, que
detecta la distribución, cubre los tres pasos y **termina arrancando el navegador**, de modo que un
fallo de este tipo sale en dos segundos en vez de tras seis minutos de suite y disfrazado de caída
del sitio.

### Actualización 04/08/2026 — el panel del admin imprimía sus propios comentarios

Encima de la tarjeta «Buscador» salía, como texto visible, el comentario del código que explica
para qué sirve esa tarjeta. Eran dos, y estaban en `backend/templates/admin/index.html`.

**Causa**: `{# … #}` en Django es un comentario de **una sola línea**. Uno de varias no se ignora:
se renderiza tal cual. Los de una línea del mismo archivo funcionaban bien, y por eso no cantaba al
leer el código.

**Corrección**: los dos pasan a `{% comment %} … {% endcomment %}`, que sí es multilínea, con una
nota en el propio archivo para que nadie los devuelva a la almohadilla. Comprobado contra el sitio
desplegado: cero ocurrencias del texto y la tarjeta intacta.

Es cosmético, pero estaba en la primera pantalla que ve PREDES al entrar al admin.

### Actualización 04/08/2026 — la ayuda memoria salía sin mapa en producción

Reportado desde `/peligros` con Kunturkanki. Reproducido y corregido; las reglas quedan en 02:

- **Causa**: el visor que captura el navegador headless pedía sus datos con URL construidas a partir
  de `BACKEND_URL`, que es la URL con la que **el visitante** alcanza el backend. Chromium corre
  dentro del contenedor, así que en producción local (`http://localhost`) pedía al puerto 80 del
  propio contenedor, donde no escucha nadie: «Failed to fetch» y PDF sin mapa. **En desarrollo
  funcionaba por casualidad**, porque allí `BACKEND_URL` es el puerto de ese contenedor — y por eso
  la prueba del PDF con mapa no lo veía. Ahora las URL son relativas.
- **La misma causa una segunda vez**: `/api/mapas/capas/` devuelve las URL de los PMTiles en absoluto
  y con `BACKEND_URL`, así que las tres capas fallaban y el mapa no terminaba de pintar nunca. El
  visor del informe las reescribe contra su propio origen.
- **Una sola tesela costaba el mapa entero**: cualquier `error` de MapLibre se trataba como fatal, y
  el mapa base son teselas de openstreetmap.org. Ahora esos errores son avisos que van al log, hay un
  plazo de 8 s por si `idle` no llega, y el mapa sale con los centros poblados y las capas propias
  sobre fondo plano. Comprobado apuntando el mapa base a un host inexistente.
- **Una prueba que pasaba en vacío** (08): `test_con_el_mapa_tambien_sale` solo comprobaba que el PDF
  se generara y toleraba que viniera sin mapa. Pasa a exigir el mapa cuando Chromium está disponible,
  con su contraparte que comprueba que sin mapa no hay ninguna imagen.
- Hallazgo de datos anotado, sin cambio de código por decisión del dueño del proyecto: el Excel de ese
  distrito sale vacío porque **la fuente no clasificó ninguno de sus 61 centros poblados**, y hay
  **24 distritos así**, Sicuani incluido (302 centros poblados). La ayuda memoria sí lo explica en su
  párrafo de presentación; el export no dice nada.

### Actualización 03/08/2026 — las imágenes del editor, en su carpeta y a tamaño de pantalla

Arreglar el 404 de la subida de imágenes destapó **dos ajustes que no hacían nada**. Los dos se
cierran con un `CKEDITOR_5_FILE_STORAGE` propio (`apps.core.almacenamiento`), documentado en 03:

- **`CKEDITOR_5_UPLOAD_PATH` lo ignora la librería** (`fs.save(f.name, f)`, sin prefijo): las imágenes
  caían en la raíz de `media/`. Ahora van a `contenido/%Y/%m/`, la convención del resto del proyecto.
  Trampa por el camino: **`Storage.save` no llama a `generate_filename`** —solo lo hace la ruta de los
  campos de modelo—, así que el prefijo tiene que aplicarse en `save`.
- **`CONTENIDO_ANCHO_MAXIMO_PX` no se usaba en ningún sitio** mientras el comentario de al lado
  prometía que las fotos se reescalan al guardar. No se reescalaban. Medido con una subida real:
  4.000 px y 4,3 MB → 1.600 px y 513 KB. Con orientación EXIF corregida, sin tocar GIF ni TIFF, sin
  recomprimir lo que ya cabe y sin fallar nunca por esto.

### Actualización 03/08/2026 — estado del buscador en el panel, y un 404 escondido bajo el admin

Tres preguntas operativas —¿está caído el buscador?, ¿está indexado al 100%?, ¿cómo se reindexa?— de
las que **solo la primera tenía respuesta**. Se corrigieron 03, 04 y 08:

- **`meili.estado_indices()`**, con dos consumidores: `manage.py meili_estado` (sale con código ≠ 0,
  así que sirve de cron con `|| mail`) y una **tarjeta «Buscador» en el panel del admin** con un botón
  que encola `reindexar_meili`. PREDES puede ver el desfase y arreglarlo sin que nadie entre al
  servidor.
- **`numberOfDocuments` de `/stats` no sirve para esto**: está cacheado. Vaciando un índice de verdad
  se vio que seguía informando de 6 documentos mientras la búsqueda devolvía 0 —la primera versión de
  la comprobación daba el índice por bueno justo en el caso que debía detectar—. El total exacto es
  `get_documents({"limit": 0}).total`. Anotado en 04 y fijado con una prueba.
- **Las consultas de estado llevan timeout** (3 s). Sin él, un Meilisearch que acepta la conexión y no
  contesta cuelga `/api/buscar/estado/` —que el navegador pide en cada búsqueda— y la portada del
  admin.
- **Un 404 silencioso**: `admin.site.urls` iba **antes** que la ruta de subida de imágenes de
  CKEditor, y el `catch_all_view` del admin se queda con todo lo que cuelga de su prefijo. Insertar
  una imagen desde el texto rico devolvía 404 sin que nada lo dijera; el botón sí está en la barra del
  editor. Corregido el orden y con prueba de regresión, porque no se distingue desde fuera de un 404
  legítimo. Regla en 03.

### Actualización 03/08/2026 — botón de limpiar en las cajas de búsqueda

Las cinco cajas del sitio ganan una «X» para vaciarlas. Se corrigieron 06 y 08:

- **`CajaBusqueda.tsx`** concentra el comportamiento de las cuatro cajas en React —`/buscar`, el
  filtro de la biblioteca y las dos de la cabecera—: la «X» solo con texto, `type="button"` (dos
  viven dentro de un `<form>`), el foco de vuelta al campo y `Escape` como atajo. La del visor es un
  control de MapLibre a mano y lleva su equivalente imperativo, que **no borra el marcador**.
- Regla de producto en 06: **en `/buscar` la «X» no toca la URL**. El término vive en `?q=` y los
  resultados se quedan hasta que se envíe la nueva búsqueda.
- De paso, la prueba del buscador de lugares del visor **dejó de saltarse siempre**: miraba el DOM
  antes de que MapLibre añadiera el control, así que ese buscador no estaba cubierto por nadie.

### Actualización 03/08/2026 — la llave de búsqueda pasa a ser determinista

El buscador apareció en «modo básico» en el sitio compilado. La causa: la llave *search-only* se
creaba con **uid aleatorio**, así que vivía en el volumen de Meilisearch; un `down -v` la cambió, se
actualizó `frontend/.env` y no el `.env` de la raíz —el que Compose hornea en el bundle— y el sitio
quedó buscando con una llave inexistente (403). Se corrigieron 04 y 08:

- **La llave se crea con un uid fijo**, y por eso ya no caduca: la documentación de Meilisearch
  garantiza que `key` es el SHA-256 del uid con la master key, de modo que el mismo
  `MEILI_MASTER_KEY` devuelve siempre la misma llave. Comprobado destruyendo el volumen: sale
  idéntica. Cambiar los índices públicos obliga a borrar y recrear —`PATCH /keys` no admite tocar
  `indexes`—, y al recrear con el mismo uid la llave no cambia.
- **Un rechazo de llave degrada tres cosas y solo una avisa** (documentado en 04): la búsqueda global
  cae al fallback y lo dice; las facetas de `/medidas` se quedan sin conteos y el autocompletado de
  lugares sin resultados, las dos en silencio. `lib/search.ts` pasa a distinguir el 401/403 del «no
  responde» y a escribirlo en consola.
- **Dos pruebas que no probaban lo que decían** (en 08): la de «se usa Meilisearch» comprobaba que se
  llamara a `multi-search`, no que respondiera 200, así que pasaba con el 403; y la corrida en
  desarrollo no puede detectar este fallo, porque la llave del bundle solo se usa en el sitio
  compilado.

### Actualización 03/08/2026 — el comparador fuera del menú y el header en una línea

Dos cambios pedidos sobre el cascarón del sitio. Se corrigieron 00, 06 y 08:

- **Nuevo ADR-P2**: `/comparar` sale del menú principal y del pie, pero **la ruta y el endpoint se
  quedan** y responden por URL directa. Es un grado más suave que ADR-P1. El enlace vive en tres
  sitios y hay que tocar los tres o reaparece: la semilla (`visible: false`), la base ya sembrada
  —de ahí la migración `sitio.0002`, porque el seed crea lo que falta y no pisa lo que existe— y el
  **menú de respaldo del frontend**, que es el que se pinta mientras carga `/api/sitio/` y en modo
  degradado.
- **El menú de escritorio va en una línea.** No lo estaba: a 1024 px «Exposición a peligros» partía
  su texto en dos dentro de una barra de altura fija. Se fija en 06 quién cede el espacio —los
  enlaces con `whitespace-nowrap`, logo y `nav` con `shrink-0`, el buscador con `min-w-0`— y se mide
  en `e2e/header.spec.ts`.
- Trampa de medición anotada en 08: **`getClientRects().length` sobre el elemento no detecta el
  salto de línea** (los enlaces son bloques: un solo rectángulo aunque midan 56 px de alto). Las
  líneas se cuentan con un `Range` sobre el contenido.

### Actualización 03/08/2026 — auditoría de cifras del visor y clustering

Auditar por qué `/peligros` mostraba 225 en "Distribución" y 75 en la tabla para ACOMAYO destapó
una ambigüedad de unidades y arrastró un cambio de arquitectura en la capa CCPP. Se corrigieron
00, 01, 02, 05 y 06:

- **Las dos cifras eran correctas y contaban cosas distintas**: 225 clasificaciones = 75 CCPP × 3
  peligros evaluados. La UI pasa a contar centros poblados por su nivel máximo (misma unidad que la
  tabla y el mapa). Toda cifra de distribución en los specs lleva ahora su unidad declarada (01).
- **Nuevo ADR-A13**: la capa CCPP del visor deja PMTiles y pasa a fuente `geojson` agrupada, porque
  **MapLibre solo agrupa fuentes `geojson`** y el clustering con símbolos proporcionales a
  población es requisito. Ríos, lagunas y glaciares siguen en PMTiles.
- Con clustering, **filtrar con `setFilter` es incorrecto**: los clusters se calculan antes del
  filtro de capa y su conteo mentiría. Se filtra con `setData` (05).
- Hueco en el contrato de API: `/api/peligros/resumen/` no permitía derivar el nivel máximo por
  CCPP, y falta un `/api/ccpp/geojson/` para los puntos del visor. Ambos anotados en 02, el segundo
  **sin definir todavía**.
- Dos bugs reales encontrados por el camino, ambos documentados en 05: el guard de estilo
  `once("load")` que recomendaba el propio spec **no funciona** y perdía efectos en silencio, y
  `fonts.openmaptiles.org` dejó de servir glifos (devuelve HTML con status 200). Los glifos pasan a
  auto-hospedarse.

### Actualización 02/08/2026 — auditoría de los Excel y prueba del pipeline de tiles

Los specs se escribieron contra una versión anterior de los datos. Al auditar los archivos reales de `data/layers/` se corrigieron 00, 01, 02, 03, 05 y 06. Lo que cambió de fondo:

- El Excel de niveles fue actualizado por el cliente: **10,978 clasificaciones**, no ~6,566. Solo 3,238 de 8,968 CCPP tienen dato.
- El nombre del peligro está en la columna `PELIGRO`, **no en el título de la hoja** (dos discrepancias).
- `subtipo` sale de `ClasificacionPeligro` y pasa a `TipoPeligro.categoria_geo` (era funcionalmente dependiente del peligro).
- Nuevo **ADR-D1** y modelo `TotalDeclaradoEmergencias`: el distrito de Cusco declara 134 emergencias sin desglose.
- **`glaciares.geojson` está en EPSG:32718**, no en lat/lon — sin reproyectar, los tiles salen vacíos.
- El filtro de lagunas debe ser case-insensitive (`ILIKE`), o pierde 73 polígonos.

El pipeline del spec 05 se validó de punta a punta en el prototipo (`prototype/scripts/build_tiles.sh` + ruta `/peligros/mapa-nuevo`, solo en desarrollo). Los `.pmtiles` no se versionan.

### Actualización 03/08/2026 — decisiones de despliegue y arranque de la construcción

- **ADR-A6bis**: nginx + certbot en contenedor sustituyen a Caddy.
- **ADR-A14**: dos dominios — `observatorio.predes.org.pe` (SPA) y `obs.predes.org.pe` (API, admin, media, tiles, search), con CORS entre ambos. 07 reescrito en consecuencia. (A13 ya estaba tomado por la capa CCPP agrupada.)
- **ADR-D3**: la ventana Inversión se difiere; solo se entrega la ruta con su estado vacío. *(Superado por ADR-D4 el 10/08/2026.)*
- Se cierran los dos pendientes que los specs arrastraban: **`GET /api/ccpp/geojson/`** queda definido en 02 (FeatureCollection completo con los mismos filtros que la tabla), y el **mapa de la ayuda memoria se renderiza en servidor** con navegador headless.
- Nuevo **08-plan-pruebas.md**. Se evaluó añadir `data-model.md`, `infra.md`, `prod.md`, `tech.md` y `ui.md`: los cinco ya están cubiertos por 01, 07, 00 y 06, y duplicarlos solo garantiza que se desincronicen.
- `frontend/` se recreó desde `prototype/`: la copia anterior era previa a la migración a MapLibre.

### Actualización 03/08/2026 — la suite de pruebas y los seis fallos silenciosos

Escribir las pruebas del plan 08 encontró seis defectos, **ninguno visible**: en los seis casos el
sistema respondía 200 y la pantalla se veía bien. Se corrigieron con las pruebas que los detectan, y
08 los lista con su síntoma para que quede el argumento de por qué la fase existe:

- **El proxy `/search/` mandaba todo a la raíz de Meilisearch.** Una variable en `proxy_pass`
  desactiva la sustitución del prefijo de la `location`, así que la barra final no reescribía nada.
  El buscador caía al fallback de DRF en cada búsqueda. Y `GET /search/health` devolvía 200 —la raíz
  de Meilisearch también responde 200—, de modo que la comprobación obvia lo tapaba. Corregido en 07
  con `rewrite`; la verificación de despliegue pasa a ser `POST /search/multi-search`.
- **El listado de frecuencia omitía los 26 distritos que solo declaran subtotales** (ADR-D1), Cusco
  incluido, mientras su detalle sí los servía. Se añade `consultas.distritos_con_emergencias`, que
  mira las dos tablas: 64 → 90 entradas sobre los datos reales. Documentado en 02.
- **El export de frecuencia ignoraba los filtros** al añadir los declarados.
- **El saneado de HTML vivía en el admin**, no en `save()`, mientras el `help_text` del campo
  prometía lo contrario (01 y 03 actualizados con `HtmlRicoMixin`).
- **21 distritos con fila vacía** recibían el aviso de ADR-D1, que dice otra cosa. Nuevo hallazgo de
  calidad de datos en 00: son un vacío de información, no un «declara sin desagregar».
- **El beacon de métricas estaba limitado a 60/min por IP**, y una institución entera comparte IP
  detrás del NAT (07).

Dos lecciones de método, ya en 08: la corrida E2E **contra nginx** no es opcional —en desarrollo el
navegador ataca a Meilisearch directamente y el fallo del proxy no existe—, y las dos muestras de
Excel tienen que ser consistentes entre sí, porque el importador de frecuencia resuelve el distrito
por nombre contra el padrón y sin un CCPP de Ollantaytambo las pruebas de ADR-D1 pasaban sin
comprobar nada.

## Orden de lectura

| Doc | Contenido |
|---|---|
| [00-alcance-decisiones.md](00-alcance-decisiones.md) | Alcance, ventanas temáticas, ADRs (decisiones de arquitectura y de producto) |
| [01-modelo-datos.md](01-modelo-datos.md) | Apps y modelos Django, campos futuros `[+]`, índices, diagrama ER, datasets Excel canónicos |
| [02-api.md](02-api.md) | Contrato de endpoints DRF con ejemplos de payload |
| [03-admin-editorial.md](03-admin-editorial.md) | Admin Unfold, roles, flujo editorial + correos, importadores, Gemini |
| [04-busqueda.md](04-busqueda.md) | Índices Meilisearch, sincronización, llaves |
| [05-mapas-tiles.md](05-mapas-tiles.md) | Pipeline Tippecanoe/PMTiles con recorte a Cusco, capa CCPP, migración a MapLibre |
| [06-frontend.md](06-frontend.md) | Migración prototype→frontend, rutas nuevas, lib/api.ts, estados vacíos |
| [07-despliegue-ops.md](07-despliegue-ops.md) | compose.yaml, nginx + gunicorn, los dos dominios, .env, HTTPS, backups, runbook, capacitación |
| [08-plan-pruebas.md](08-plan-pruebas.md) | Qué se prueba y con qué; casos obligatorios derivados de la auditoría de datos; criterio de entrega |
| [09-errores.md](09-errores.md) | **Ciclo de errores**: severidades, la regla de «nace con una prueba que falla», y dónde está el tracker que guarda los abiertos |

## Archivo histórico

`archive/` contiene los specs de la fase de prototipo (visión, UX, datos mock, arquitectura preliminar, roadmap). Siguen siendo válidos como referencia de **visión de producto** (`archive/00-vision.md`) y **UX/paleta/componentes** (`archive/02-navegacion-ux.md`); todo lo relativo a stack estático, mocks y hosting Vercel está superado por estos specs.
