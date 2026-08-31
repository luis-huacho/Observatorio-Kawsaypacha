# Specs — Observatorio Kallpachakuy (fase de construcción)

Especificaciones técnicas de la plataforma real, sucesora del prototipo aprobado (`prototype/`, congelado como referencia). Plataforma en línea el **13/08/2026**.

## Estado

- Fase 0 (prototipo estático) **completada y aprobada** por PREDES.
- Fase actual: construcción de `frontend/` (Vite + React + TS + MapLibre) y `backend/` (Django 5.2 LTS + PostgreSQL + Meilisearch + PMTiles), desplegados con Docker Compose.

> Las entradas `### Actualización` de más abajo son la bitácora de **lo ya corregido**. Lo que se
> sabe roto y sigue sin arreglar vive en el **tracker**, en el servidor de desarrollo, publicado en
> `https://<API_DOMAIN>/gitea/<admin>/observatorio/issues` (y por túnel como rescate). Al cerrarse un
> error, se cierra allí y entra aquí como una entrada nueva. El ciclo —severidades, la regla de
> cierre, qué se hace al cerrar— está en **[09-errores.md](09-errores.md)**.

### Actualización 31/08/2026 — dos tipos más de noticia, y el valor crudo era el nombre de un archivo

PREDES necesitaba **«Publicación»** y **«Base de datos»** en el desplegable «Tipo» del formulario de
noticias: es lo que el observatorio publica además de piezas editoriales —un informe, un conjunto de
datos liberado—. Son dos líneas en un `TextChoices`, y detrás había tres cosas que fallan sin dar
ningún error.

- **El valor crudo del tipo ES el nombre de la ilustración por defecto** (`/img/default/<tipo>.svg`,
  vía `serializers._clave_portada` → `imagenes.portada`). Un tipo sin su SVG dejaba **toda noticia
  sin portada propia con la imagen rota**. Se cierra con `imagenes.clave_noticia()`, que repliega a
  `noticia.svg` —calcado de `clave_medida`, que ya resolvía lo mismo para los peligros— y con los dos
  dibujos nuevos, en el lenguaje visual de la casa.
- **La red de esa red tuvo que rehacerse a mitad de camino.** El caso e2e comprobaba que ninguna
  petición a `/img/default/` respondiera 4xx, y **daba verde siempre**: el `try_files $uri
  /index.html` de la SPA —y el dev server de Vite— responden **200 con `text/html`** a un archivo que
  no existe (es el mismo mecanismo que fundó ADR-A26). Ahora se mide con `naturalWidth`: un HTML
  servido donde iba una imagen no decodifica. Comprobado escondiendo `publicacion.svg` y viendo la
  prueba caer, que es la única forma de saber que una prueba prueba algo.
- **El `enum` de `tipo` que se le manda a la IA estaba escrito a mano**, aparte de los `choices`.
  `_normalizar` sí validaba contra `Noticia.Tipo`, así que los dos tipos nuevos habrían quedado
  disponibles para el editor y **la IA no habría podido proponerlos nunca**, sin que fallara nada.
  `ESQUEMA` pasa a `_esquema()` y el `enum` sale de los choices, como en medidas y normativa; el
  spec 03 afirmaba esto de todos los esquemas y para noticias era falso.
- **`max_length=10` y `publicacion` son 11 caracteres.** La migración amplía la columna a 20 además
  de registrar los choices. Sin eso, el error habría salido al guardar en el admin.
- **Un detalle de dibujo que se vio solo en pantalla**: la cordillera de cierre partía el sello de
  `publicacion.svg` exactamente por la mitad, y eso no se lee como «el motivo se tapa tras la
  cresta» sino como un recorte fallido. El sello se movió al valle entre dos picos.
- La descripción del fieldset «Portada» del admin enumeraba «(noticia, artículo u opinión)». Se
  quitó la lista en vez de ampliarla: ya se había quedado corta una vez.

Suite: **509 + 7 deselected** en pytest (6 pruebas nuevas) y **1 caso e2e nuevo** en
`noticias.spec.ts`. Dos noticias demo nuevas, una de cada tipo y **sin portada propia a propósito**,
que son las que ejercitan las ilustraciones.

### Actualización 31/08/2026 — cuatro segundos de espera sin una sola señal en pantalla

Pedir la ayuda memoria en `/peligros` tarda **3,7-4,0 s** —el PDF renderiza su mapa con un Chromium
headless— y el reporte de `/inversion`, 4,4 s. Durante esos segundos **la interfaz no cambiaba en
absoluto**: los cuatro botones de descarga del sitio eran `<a href>` a pelo y el navegador se
llevaba la petición sin que la página se enterara. En escritorio salvaba el indicador del propio
navegador; en móvil, que es donde el TDR pide que el sitio sirva, no se veía nada y el visitante
volvía a pulsar.

**Y no era solo la espera. Había dos fallos invisibles debajo.** El límite de descargas es de
**30/hora por IP** (`DescargaThrottle`) y una oficina entera comparte IP detrás de un NAT: al
pasarse, el 429 se veía como una pestaña con JSON crudo, o como nada. Y la captura del mapa no
propaga errores a propósito (`mapa.py:131-133`) —un documento sin mapa sirve; uno que no se genera,
no—, así que lo único que llegaba al cliente era el 5xx, que tampoco se veía.

Ahora las cuatro pasan por `components/BotonDescarga.tsx`: se piden con `fetch`, se entregan desde
un blob, y el estado es real. Cuatro decisiones que no son evidentes:

- **Sigue siendo un `<a href>`, no un `<button>`.** El `onClick` intercepta el clic normal pero
  **deja pasar Ctrl/Cmd/Shift/Alt y el botón central**: con un `<button>` se habrían perdido «abrir
  en pestaña nueva» y «guardar enlace como», que hoy funcionan. Hay una prueba e2e que lo fija, y
  **no afirma sobre la URL de la pestaña nueva**: el reporte se sirve como `attachment`, así que el
  navegador lo descarga y la pestaña se queda en `about:blank`.
- **El estado se cuenta dos veces y no sobra ninguna.** En el botón y en un aviso fijo abajo a la
  derecha (`AvisoDescarga.tsx`), porque los botones viven en el `PageHeader` y **dejan de verse en
  cuanto se baja a la tabla o al mapa**. El de «generando» se retira solo —la descarga es la
  confirmación—; el de error **se queda hasta que se cierra**, porque un error que se autodestruye
  a los tres segundos no lo lee nadie. El `aria-live` va en el aviso y **no** en el botón: con los
  dos, un lector de pantalla lo anunciaría dos veces.
- **Hizo falta `CORS_EXPOSE_HEADERS = ["Content-Disposition"]`.** La SPA y el API viven en dominios
  distintos (ADR-A14) y un `fetch` cross-origin **solo lee las cabeceras que el servidor autoriza**;
  no había ninguna expuesta. Sin esa línea no falla nada: el archivo se guarda con el identificador
  del blob, sin extensión, en vez de `ayuda-memoria-accha-20260830.pdf`. Tiene prueba a los dos
  lados —una de backend sobre `Access-Control-Expose-Headers` y una e2e sobre
  `suggestedFilename()`— y cada botón lleva además un `nombreDeReserva`, porque un bundle nuevo
  contra un backend viejo es un estado real durante un despliegue.
- **`URL.revokeObjectURL` no se llama en el mismo tick que el `click()`**, que puede abortar la
  descarga antes de que el navegador llegue a leer el blob.

**Lo que NO se hizo, y por qué.** Encolar la generación en django-tasks y sondear el estado es la
respuesta arquitectónica obvia y aquí es la equivocada: para cuatro segundos añade dos peticiones,
una fila de BD y **un archivo que hay que guardar en algún sitio** — y `MEDIA_ROOT` lo sirve nginx
entero como estático público, así que una ayuda memoria filtrada quedaría accesible por URL a quien
la adivinara. El mecanismo se guarda para la generación por lotes, que sí lo pide. Tampoco se finge
el estado con un temporizador: diría «listo» cuando no lo está.

De camino salieron dos cosas que quedan **anotadas en `_docs/deuda-tecnica.md`, no arregladas**: el
Excel de normativa tiene endpoint, límite y prueba pero **ningún botón que lo pida**
(`Normativa.tsx:24` calcula la URL y no la pinta; `noUnusedLocals` está en `false`, por eso nada
avisó), y el visor headless pide su página **al mismo gunicorn** que genera el PDF con solo tres
workers — se destraba solo a los 25 s con los PDF sin mapa, pero no está reproducido.

Sin ADR: no cambia ninguna decisión. Suite: **481 + 7** y **73 casos e2e** (146 corridas), en verde.

### Actualización 31/08/2026 — la misma frase, redactada dos veces, es dos frases

Las cuatro declaraciones de la entrada de abajo nacieron en TypeScript, y el encargo siguiente
fue ponerlas también en el PDF. Duplicarlas en Python habría dejado **dos redacciones de la
misma frase**: el día que se retoque una, la otra se queda atrás y nada avisa. Es exactamente lo
que el proyecto ya había decidido dos veces —ADR-D6, «el payload lleva `no_ubicado` con **su
motivo ya redactado**: la advertencia viaja con el dato, no con la interfaz», y el encabezado de
`consultas.py`, «que los tres calculen el % de ejecución por su cuenta es la forma segura de que
un día no coincidan»—.

Así que la redacción **baja al backend**: `apps/inversion/declaraciones.py`. Viaja en
`declaraciones` del payload, la SPA imprime la cadena y el PDF llama a las mismas funciones. Se
comprobó que el texto salía **carácter por carácter idéntico** antes de borrar el TypeScript.

**Lo único que no se comparte es la tipografía**, y por eso los formateadores entran por
parámetro: el navegador escribe `53%` (es-PE, `Intl`) y el reporte `53.0 %` (sus filtros). La
frase es una; cómo se escribe un porcentaje lo pone cada medio. Igualar los dos habría obligado
a tocar todos los porcentajes de uno de los dos documentos.

En el PDF, las cuatro frases van bajo su gráfico con la clase `.declaracion` que ya existía —de
donde salió el registro— y llega además **el desglose de proyectos**, que el reporte no tenía en
ninguna forma. Dos detalles de maquetación que no son cosméticos: la magnitud PIA-PIM **sube del
párrafo de encima a la frase de debajo**, como ya hizo la pantalla, porque decirla dos veces en
la misma tarjeta era repetirse; y **el cuadro va en su propia sección, fuera de `evitar-corte`**,
con la clase `tabla-larga` que repite cabecera al partir — pegar a un gráfico una tabla que crece
con el ámbito arrastraría el gráfico a la página siguiente dejando media en blanco.

**Una prueba encontró una frase correcta y engañosa.** Con un reparto plano —cinco
municipalidades con lo mismo— «las 4 primeras concentran el 80 %» es cierto por pura aritmética,
y hace sonar concentrado justo lo que está repartido: lo contrario de lo que la frase viene a
contar. No falla a la vista, porque la cifra es exacta. Ahora la concentración **solo se declara
si las que se llevan el 80 % son minoría**. Salió de `test_declaraciones.py`, que prueba la
redacción directamente en vez del texto renderizado: al ser la única redacción, un fallo de
copy sale a la vez en la pantalla y en el documento, y se caza en un sitio.

### Actualización 31/08/2026 — los gráficos de `/inversion` se dejaban leer pero no concluían

Cuatro gráficos y ninguno decía nada: la conclusión la tenía que sacar quien mirara. La ventana
la van a usar autoridades, periodistas y universidades, y lo que esa gente necesita es **la
frase que se puede copiar**. Cada gráfico lleva ahora debajo una `Declaracion` que dice, en
tercera persona y sin adjetivos, cuánto subió o bajó en soles y en porcentaje, o dónde se
concentra el dinero.

**No se inventó un registro nuevo: ya existía.** El PDF tiene una clase `.declaracion` —filete
izquierdo, texto pequeño y gris— y la usa para exactamente esto («S/ X **no aparecen en el
mapa**», «S/ X **cuelgan de** códigos que el catálogo aún no imputa»). Las cuatro frases copian
ese registro y el componente replica el filete. Se redactan en `lib/inversion.ts`, como
funciones puras, para poder probarlas sin montar React y para que las cuatro suenen igual.

**Sin verde ni rojo, a propósito.** `Delta` colorea las subidas y las bajadas y ahí está bien,
porque compara dos ejercicios que alguien eligió. Aquí no: más presupuesto no es de suyo una
buena noticia, y teñir de verde un incremento es opinar por el lector.

**La frase de la tendencia compara los dos últimos ejercicios COMPLETOS.** El devengado a junio
de 2026 (26.1 M) contra el de 2025 entero (64.0 M) daría un «bajó 59.3 %» que no mide una caída:
mide medio año contra un año entero. El corte parcial se nombra aparte, sin variación, que es la
única forma de que la frase no tenga que desmentirse a renglón seguido. Y no dice «cerrado»,
sino «completo»: hay una prueba e2e que fija que esa jerga no vuelve.

## «Este monto parece alto» — y el supuesto de quién lo gasta era falso

El encargo venía con una hipótesis: que el 40 % en proyectos de inversión «principalmente es del
Gobierno Regional». **No lo es, y comprobarlo antes de escribir evitó publicar algo falso.** El
tablero sirve el ámbito `municipal` y el frontend nunca manda otro: el GORE **no entra**. Ese
40 % es íntegramente municipal (S/ 22,217,511); el Gobierno Regional tiene su propio 78.8 %, en
otro ámbito que esta pantalla no muestra.

Lo que sí explica la cifra es la **concentración**: de las 116 municipalidades, **24 tienen
presupuesto en obra** y cinco se llevan el 81.6 %. La Convención sola reúne el 74.7 %. Eso es lo
que ahora se ve: «Proyectos de inversión frente a actividades» pasa a ser sección propia —tenía
media tarjeta prestada de «¿En qué se invierte?»— con su barra, su frase y **el cuadro de qué
municipalidades tienen obra**, con cuánto y qué porcentaje de su propio PIM es.

La frase remata diciendo que el Gobierno Regional no está en el ámbito. Se dice porque es
exactamente la lectura que tuvo el dueño del proyecto, y si la tuvo él la tendrá un periodista.

Cuatro decisiones del desglose que no son obvias:

- **Va en el payload del tablero, no en la tabla paginada.** `pim_proyectos` se calcula en
  Python **después** de paginar, así que ordenar la tabla por él exigiría anotarlo en SQL. Con
  24 filas como mucho, el desglose viaja entero y `ORDENES` no se toca.
- **Solo entran las que tienen PIM de proyectos > 0.** Una fila en cero las haría contar como si
  tuvieran obra, y «24 de 116» es justo la frase que el cuadro sostiene.
- **La lista no se recorta a un top N.** Un «y otras N» no lo podría comprobar nadie.
- **Hay una prueba de que la suma del desglose es exactamente `agregados.pim_proyectos`**, la
  misma disciplina que `test_el_mapa_no_pierde_ni_inventa_un_sol`: un desglose al que le falta
  dinero se ve idéntico a uno correcto.

**Dos cosas que el e2e cazó y que no habrían fallado a la vista.** Los enlaces del cuadro nuevo
no arrastraban los filtros, así que volver de una ficha devolvía al ejercicio por defecto en vez
de al que se estaba mirando. Y la prueba de la ficha usaba un `table tbody tr` **sin acotar**,
que con la tercera tabla de la página pasó a leer el desglose en vez del ranking: se acotó con
`tablaDeMunicipalidades`, el helper que existe para eso desde que apareció la segunda.

**Lo que no entra**: el PDF no recibe estas frases. Ya lleva su propia prosa y sus
`.declaracion`, y sus gráficos son SVG generados en servidor; añadirlas ahí es un encargo
aparte, no un efecto secundario de este.

### Actualización 31/08/2026 — el contexto de `/inversion` se identificaba dos veces y se explicaba tres

La entrada de abajo, de ayer, arregló que el aviso del ejercicio parcial **nombrara** el
ejercicio en vez de solo advertir de él. Al verlo en pantalla apareció el problema siguiente:
entre el selector de filtros y la primera cifra había **sesenta palabras** de contexto, en dos
párrafos, y ninguna era un número.

Se recorta cada uno a lo que identifica lo que se está mirando:

- «Viendo todas las municipalidades de la región Cusco **(115 de 116 con presupuesto del
  0068)**, ejercicio 2026 al corte de junio. **Unidad: la municipalidad (entidad ejecutora), no
  el distrito.** Fuente: …» → se van el recuento y la unidad.
- «Ejercicio 2026, año fiscal en curso — **datos al corte de** junio de 2026. **El devengado no
  cubre el año completo, pero el porcentaje de ejecución se calcula contra el PIM de todo el
  año: un 47.7 % a mitad de año no es media ejecución perdida, y no se puede comparar con el de
  un año completo.**» → queda «— corte a junio de 2026».

**El argumento no es que sobrara, es que ya estaba dicho más abajo.** La explicación del corte
parcial es literalmente `PIE_EJERCICIO_PARCIAL` («el devengado no cubre el año completo, así que
su % de ejecución no se compara con el de un año ya terminado»), que se pinta al pie del cuadro
de tendencia **de esta misma página** y de la ficha de municipalidad — y ahí está mejor puesta,
porque es donde hay porcentajes de varios ejercicios uno debajo de otro, que es cuando la
comparación se hace de verdad. La unidad la siguen diciendo el encabezado «Municipalidades», la
columna de la tabla y la leyenda «sin municipalidad» del mapa.

**Lo que esto invierte, y a sabiendas**: el spec 06 decía «el corte parcial se avisa **junto a
las cifras**, no al pie». Ahora se identifica junto a las cifras y se explica al pie. Queda
reescrito así, no borrado, porque la regla vieja seguía siendo buena para el sitio donde nació:
**el PDF no cambia** y conserva la explicación entera y arriba, por la razón que ya llevaba
escrita en su plantilla —«un documento en papel viaja sin su pantalla»—. Las tres mitigaciones
de ADR-D5 son otros elementos (el asterisco del Δ, su leyenda pegada a la tabla y la columna
«Comparabilidad» del Excel) y no se tocan.

**Ninguna prueba cambió, y eso se comprobó antes de recortar, no después.** Las tres aserciones
e2e que rozan la banda miran el `<strong>` («Ejercicio 2026, año fiscal en curso»), que
`corte_legible` esté visible, y que la palabra «cerrado» siga sin aparecer: las tres se
cumplen. Ojo con la segunda —`corte_legible` completo («junio de 2026») se pinta **en un solo
punto del tablero**, esta banda—: acortarla a «corte a junio» rompería `e2e/inversion.spec.ts`
sin tocar nada más.

**De paso, la fuente pasa a llamarse «Base PP 0068 desarrollada por PREDES»** (era «entregada»):
la base la construyó PREDES, no se la entregó un tercero. Vive en el label de
`Ejercicio.Fuente.CLIENTE`, así que el cambio es de una línea y **emite migración**
(`inversion.0002`, `AlterField` de metadatos: Django serializa los `choices` y hay dos pruebas
que corren `makemigrations --check`). Con el label cambian solos la pantalla, la columna
«Fuente» de la tendencia, la cabecera del PDF y el Excel de export; las **dos frases en prosa**
que repetían el literal a mano —el pie de fuentes del PDF y el texto de la tendencia— hubo que
igualarlas aparte, que es justo el precio de escribir a mano lo que ya sirve el modelo.

**Deuda que queda declarada**: la banda gemela de la ficha de municipalidad
(`InversionDetalle.tsx`) sigue diciendo «— datos al corte de … El devengado no cubre el año
completo», así que las dos pantallas usan ahora fórmulas distintas para el mismo aviso.
`lib/inversion.ts` existe precisamente para que no pase; alinearlas es un encargo aparte.

### Actualización 30/08/2026 — `/inversion` decía qué NO era el dato y nunca qué era

La ventana del PP 0068 abría con una sola frase sobre el ejercicio que estaba mostrando: «**Corte a
2026-06.** El devengado no cubre el año completo, así que su porcentaje de ejecución no es
comparable con el de un **ejercicio cerrado**». Es correcta y era lo único que había. El problema es
que **define el dato por su contrario**: obliga a saber que un «ejercicio cerrado» es un año fiscal
terminado y liquidado para deducir, por descarte, que 2026 es el año en curso. Nunca lo decía.

**El PDF ya lo decía bien, y ese es el argumento.** `reporte_inversion.html` abría con «El ejercicio
2026 **está en curso** (corte a 2026-06)» y remataba con «un 50 % a mitad de año no es media
ejecución perdida»; su tabla de cabecera declaraba además el ámbito («Municipal **de la región
Cusco**»). El documento en papel estaba mejor redactado que la pantalla de la que sale. Este cambio
sube a la pantalla lo que el reporte ya había resuelto.

**«Parcial» y «en curso» no son lo mismo, y el PDF tenía ahí un fallo latente.** `es_parcial` dice
*el devengado no cubre el año entero*; «en curso» dice *el año no ha terminado*. Hoy coinciden
porque el único parcial es el del año corriente, y el PDF afirmaba «está en curso» sobre
`es_parcial` a secas: el día que PREDES cargue un corte a junio de un año ya pasado, el documento
diría en negrita algo falso. Ahora son dos propiedades de `Ejercicio` —`en_curso`
(`es_parcial and anio >= hoy.year`) y `corte_legible` («junio de 2026»)—, **no columnas: no emiten
migración**, y las dos viajan en el payload junto a `corte` y `es_parcial`.

**El bloque que identifica un ejercicio estaba copiado a mano en siete payloads** —la raíz del
tablero, el selector, la tendencia, las dos caras de la comparación, la ficha de la municipalidad y
el contexto del PDF—. Añadir dos claves a seis de los siete es la forma segura de que un cliente se
quede sin poder nombrar lo que pinta, así que salen de un solo `consultas.datos_ejercicio()`, y hay
una prueba que recorre los cinco sitios del API. En el frontend el espejo es
`InversionEjercicio`, del que ahora derivan los siete tipos por intersección.

**Y de paso, dos preguntas que la página tampoco contestaba.** Sin filtrar nada servía el ejercicio
publicado más reciente y **toda la región Cusco** sin declararlo en ninguna parte —el encabezado
ponía «ejercicio 2026» y nadie decía que era un valor por defecto ni cuál era el ámbito
territorial—; ahora hay una línea de alcance con la tabla de cabecera del PDF como modelo, que
nunca dice «toda la región» mientras hay una provincia filtrada, ni siquiera si el catálogo de
provincias aún no ha llegado. Y la pestaña «Comparar ejercicios» solo mostraba «Elige un ejercicio
para comparar», que explica cómo usarla pero no qué se gana: ahora dice que enfrenta los ejercicios
**municipalidad por municipalidad**, que es justo lo que el total de la tendencia no deja ver.

La palabra «cerrado» **desaparece de la interfaz** —donde hace falta el término de comparación se
dice «un año completo» o «un año ya terminado»— y hay una aserción e2e que lo fija, porque el copy
es lo más fácil de revertir sin querer en el siguiente retoque. Se queda en los `help_text` del
admin, que es su público: ahí «ejercicio cerrado» es el término contable correcto, y cambiarlo
emitiría una migración por texto.

Sin ADR: no cambia ninguna decisión, corrige la redacción de una que ya estaba tomada (ADR-D5). No
se toca ninguna cifra ni el Excel, donde `corte` es una columna de dato y `AAAA-MM` es lo que se
quiere en una celda. Suite: **480 + 7** y **69 casos e2e** (138 corridas), en verde.

### Actualización 29/08/2026 — el sitio decía «200, aquí está» a documentos que no existen (ADR-A26)

Un test externo de *agent-readiness* señaló doce carencias. Se comprobaron **las doce contra el
sitio en vivo** antes de tocar nada, y el reparto no era el que decía el informe.

**Cuatro hallazgos eran un solo bug, y no el que se reportaba.** «El catálogo de la API devolvió
HTML en lugar de JSON», y lo mismo de `auth.md`, del índice de skills y del manifiesto ARD. La causa
es una línea: `location / { try_files $uri /index.html; }`. Sin `=404` al final, **toda URL
desconocida responde 200 con el `index.html`** — comprobado en `/.well-known/api-catalog`,
`/.well-known/ai-catalog.json`, `/.well-known/agent-skills/index.json` y `/llms.txt`, los cuatro
`200` + `text/html`. Esos documentos no estaban rotos: **no existen**, y el fallback los disfrazaba.
Decirle 200 a un cliente que pregunta por algo que no se tiene es peor que decirle 404, porque el
404 es información. Ahora `/.well-known/` corta con un `return 404`.

**Seis pedían describir capacidades inexistentes, y no se hicieron.** El API es anónimo y de solo
lectura (`AllowAny`, sin `DEFAULT_AUTHENTICATION_CLASSES`); no hay recursos protegidos por token ni
servidor MCP del sitio. Publicar `openid-configuration` u `oauth-protected-resource` mandaría a un
agente a negociar credenciales contra la nada, y además es justo lo que escanean los bots buscando
IdP mal configurados: fabricarlo **empeora** la superficie. DNS-AID es zona DNS y DNSSEC. Queda
escrito en ADR-A26 para que el próximo informe automático no reabra la discusión.

**Y el hallazgo propio, que el informe no vio: el `robots.txt` anunciaba el sitemap en un dominio
que no resuelve.** Era un archivo estático del bundle con la línea escrita a mano —
`Sitemap: https://observatorio.predes.org.pe/sitemap.xml`— y el sitio vivo es otro; ese host
devuelve `000`. El sitemap funcionaba perfectamente —26 URL, `application/xml`, todo en verde— y
**no lo leía nadie**, porque el único documento que dice dónde está apuntaba a la nada. Es de la
misma familia que el incidente del 27/08: todas las piezas correctas y el resultado, cero. Pasa a
Django, que interpola `SITE_URL` igual que el sitemap.

Lo que se publica, entonces, es **solo lo que existe**: `/robots.txt` y `/.well-known/api-catalog`
(RFC 9727), que enlaza el OpenAPI de `/api/schema/`, la documentación de `/api/docs/` y la sonda de
`/api/salud/` — con `reverse()`, para que renombrar una ruta rompa la prueba en vez de dejar el
catálogo apuntando a una URL muerta. Hay una prueba que **pide cada enlace**: un catálogo que existe
y apunta a URLs muertas se ve exactamente igual que uno bueno.

Cuatro cosas que costaron más de lo que parecen:

1. **El repliegue de `/robots.txt` es el archivo estático, no `@spa`.** Un 5xx en `/robots.txt` no
   hace que Google rastree el sitio entero, hace que **deje de rastrearlo**. El peor caso tiene que
   ser un robots.txt permisivo sin `Sitemap:`, nunca un HTML. Probado parando el contenedor.
2. **La cabecera `Link` va en `location = /index.html`**, no en `location /`. El `/index.html` final
   del `try_files` es una **redirección interna**, así que la portada entra por ese bloque — se ve
   en que responde con el `Cache-Control: no-cache` que solo se declara ahí. Y `add_header` no se
   hereda por acumulación: declararla en `location /` habría tumbado HSTS y `nosniff`.
3. **Certbot no se toca.** El corte de `/.well-known/` va solo en el server 443 de la SPA, que nunca
   tuvo un bloque ahí; el reto ACME se sirve en el `:80` y en el del API. Verificado, no deducido.
4. **`/sitemap.xml` dejó de replegar a `@spa`**, y esto lo encontró la corrida de `compose.local.yml`
   parando el backend a propósito: devolvía **HTML con 200** a quien pedía XML. Una ficha replegada
   sigue siendo una página legible; un sitemap replegado se lee como un sitemap roto. Un 502 se
   reintenta; un 200 mal formado, no. Las fichas conservan su repliegue, que es donde tiene sentido.

Las señales de contenido las decidió PREDES: `ai-train=no, search=yes, ai-input=yes` — que el
contenido se pueda encontrar y citar, no que sea corpus de entrenamiento. Y `SITIO_INDEXABLE` queda
en `1`: el entorno de desarrollo es hoy el **único** sitio vivo, y apagarlo lo dejaría fuera de
Google; se pone en `0` el día que el dominio definitivo entre en el aire, que es cuando pasan a ser
dos copias compitiendo.

**Lo que queda fuera, medido y anotado en deuda técnica:** `GET /noticias/<slug>` devuelve 2 674
bytes con **0 caracteres de texto en el `<body>`**. Las metas de ADR-A24 arreglan la
previsualización al compartir, pero el artículo en sí sigue siendo invisible sin JavaScript. La
negociación `text/markdown` y `/llms.txt` lo saldarían; se dejaron fuera del alcance a propósito.

475 pruebas de backend (11 nuevas) y 4 de extremo a extremo. `_specs/00` (ADR-A26), `02`, `07`, `08`,
`CLAUDE.md` y `_docs/deuda-tecnica.md` actualizados.

### Actualización 29/08/2026 — normativa que se deforma, compartir, SEO, imágenes y estáticos

Cuatro encargos sobre el sitio desplegado. Los cuatro se diagnosticaron **midiendo el sitio en
vivo**, y en dos de ellos lo medido no era lo que se pensaba.

- **Normativa no desbordaba: crecía.** A 1905 px el desbordamiento horizontal era **cero**. Lo que
  pasa es que `/normativa` es el **único listado del sitio a una columna de 1280 px** y el único
  que no recorta nada, con tres campos largos encima: título (300), resumen (700) y
  `analisis_predes`, que es un `TextField` **sin límite** cuyo `help_text` promete «nota breve» y
  nada lo hace cumplir. Medido: la tarjeta larga pasa de 393 px a 293 px con el recorte, y —lo que
  importa— queda **acotada** por mucho que crezca el análisis.
- **Y el dato de origen está roto**: tres de las seis normas de producción tienen el título en
  **exactamente 300 caracteres**, el `max_length` del campo, cortado a media palabra por la base.
  No es un título, es la sumilla entera. Recortar en pantalla lo tapa; el arreglo de verdad es
  separar `titulo` y `sumilla`, y queda en deuda.
- **Lo que hace que recortar no cueste información** es que el `numero` de la norma **ya viajaba en
  el serializer y no se pintaba en ninguna parte**. «DS 048-2011-PCM» identifica la norma en 16
  caracteres donde el título necesita 300.

- **Compartir y SEO resultaron ser el mismo problema**, y no el que parecía. No es que faltaran
  botones: es que **el `<head>` era idéntico en todas las URL** —sin `og:*`, sin `canonical`, sin
  `robots.txt` ni `sitemap.xml`—, así que compartir una noticia se previsualizaba igual que
  compartir la portada. Poner las metas desde React habría arreglado Google y **nada más**:
  WhatsApp, Facebook y LinkedIn no ejecutan JavaScript. Se inyectan en el servidor, sobre el
  `index.html` **compilado** (ADR-A24), y **para todo el mundo**: distinguir bots es *cloaking*.
- **El modo producción en local encontró lo que el de desarrollo no podía**: nginx tiene **dos**
  configuraciones y la local es otro archivo. Todo funcionaba en las pruebas y no habría funcionado
  en `compose.local.yml`. Es la tercera vez que esa corrida salva un despliegue a medias.
- **El repliegue se probó parando el contenedor**, no razonándolo: con el backend caído la ficha
  devuelve 200, la SPA carga y solo se pierden las metas.

- **En imágenes el hallazgo fue peor de lo que decía el encargo.** No es que estuvieran poco
  optimizadas: **ningún `ImageField` de ningún modelo se reescalaba**. El reescalado a 1600 px
  cubría solo el editor de texto rico, cosa que su propio docstring declaraba desde el principio.
  Medido con el comando nuevo: el hero de la portada —la imagen **LCP del sitio**— pesa 1 439 KB y
  debería pesar 248 KB. Un 83 % que se descarga cada visitante nuevo **sin ningún síntoma**.

- **De `collectstatic` la alarma era falsa, y comprobarlo importó.** El informe inicial decía que el
  admin de producción estaría devolviendo 500. Se comprobó **contra el servidor** antes de tocar
  nada: 276 entradas en el manifiesto, el `redaccion_ia.js` del día anterior incluido, y todos los
  archivos con hash en 200. **No estaba roto.** Lo que falta es la garantía: el volumen `static` se
  monta encima de lo que escribió el build y **Docker solo siembra un volumen nombrado cuando está
  vacío**, así que hoy funciona por haberse recreado, no por diseño.

- **Doce pruebas de `peligros.spec.ts` fallan en móvil, y no es de este cambio.** Se comprobó
  ejecutándolas **contra producción, que corre `master`**: fallan nueve de las mismas. La causa está
  medida y anotada en deuda: `/peligros` desborda 104 px a 375 px de ancho —el `<aside>` de filtros
  mide 463 px— y el botón «Ninguno» queda en x=414, **fuera de la pantalla**. El panel de filtros no
  se puede usar en un móvil. La corrección es un `min-w-0`, pero es otra página y otro encargo.

### Actualización 28/08/2026 — se cambia el modelo de IA, y la red deja de estar en un solo sitio

- **La decisión que ADR-D10 dejó abierta se cierra con medición, no con opinión.** Aquel día quedó
  escrito «no se cambió la variable: afecta también a noticias y normas y es una decisión de coste
  del dueño del proyecto». Eso era exactamente lo que faltaba medir, así que se midieron **los tres
  consumidores con las mismas entradas que ya estaban en el registro de IA** — la comparación salió
  gratis porque `logs/ia-2026-08-28.txt` guarda entrada **y** salida de cada llamada.

  | Caso | `deepseek/deepseek-v4-flash-0731` | `google/gemini-2.5-flash` |
  |---|---|---|
  | Noticia (ADR-D7) | 1.063 car. **sin una sola etiqueta** · $0.00038 | 1.237 car. con `<p>` · $0.0015 |
  | Norma HTML (D8), 1ª | 1.448 car. con `h2`/`p`/`blockquote` · $0.00016 | 803 car. con `h2`/`ul`/`li`/`p` · $0.0012 |
  | Norma HTML (D8), 2ª — **misma URL** | 543 car. **sin etiquetas**, `estado_vigencia="vigente"` inventada · $0.00005 | — |
  | Norma PDF (D8) | 255 car. **sin etiquetas**, `vigencia` inventada · $0.00009 | 1.919 car. con `h2`/`ul`/`li`/`strong` · $0.0024 |
  | Medida ×3 (D10) | 3 clasificaciones distintas, sin etiquetas, `resultado=""` · $0.00007 | 3 idénticas, 7 `<h2>`, cero avisos · $0.0028 |

- **Lo más elocuente es la fila de la norma repetida**: la misma URL, el mismo modelo, dos
  resultados — uno formateado y otro corrido. No es que deepseek formatee mal, es que no formatea
  de forma predecible, y eso no se arregla insistiendo en el prompt.
- **`estado_vigencia="vigente"` es peor que un formato feo.** El prompt dice «no deduzcas la
  vigencia del paso del tiempo» y deepseek la dedujo dos veces; gemini la dejó vacía las tres.
  Un campo vacío el editor lo ve; uno relleno y falso, no.
- **La rama PDF no obligó a tocar `OPENROUTER_PDF_ENGINE`.** Era el riesgo real de cambiar de
  modelo —quien parsea el PDF cambia— y `pdf-text` siguió sirviendo: 1.919 caracteres bien
  formados. También se descartó el otro riesgo, que `provider.require_parameters` dejara la
  petición sin proveedor por pedir salida estructurada **y** razonamiento a la vez.
- **Se paga unas 20 veces más y merece la pena**: $0.0028 contra $0.00007 por registro son $3 por
  cada mil frente a $0.10, sobre un flujo editorial de decenas al mes. Lo que estaba en juego no
  era el gasto sino que un editor publique algo mal formado.
- **Y la lección de fondo: elegir bien el modelo no es una defensa.** La red que envuelve en
  párrafos un contenido sin etiquetas vivía **solo en medidas**; noticias y normas guardaban lo que
  viniera y no avisaban. Es decir, aquellas 1.063 caracteres de noticia corrida se publicaron sin
  que nada lo dijera. `_a_html` sube a `apps/core/services/salida_ia.py` como `a_html` y la usan
  los tres, con sus tres pruebas cada uno (envolver, no tocar el HTML bueno, y que el aviso llegue
  al `log_ia`). La cañería ya estaba: las tres bitácoras hacían `lineas += propuesta.avisos` — solo
  faltaba quien las llenara.
- **`interpretar_json` se muda con ella** y cierra su fila de deuda: vivía en `core/lectura_web.py`,
  que dejó de describir lo que hace desde que medidas —que no descarga nada— pasó a usarlo. Las dos
  funciones normalizan lo que vuelve del modelo, así que viven juntas y al lado de `openrouter.py`.
- **Dos trampas de operación, comprobadas a mano, no supuestas.** Cambiar `OPENROUTER_MODELO` en el
  `.env` y hacer `docker compose restart` **no cambia nada**: `restart` no relee `env_file` y el
  contenedor sigue con el modelo viejo sin avisar. Hay que `up -d`, que lo recrea — la misma
  lección que ya tenía la fila «Cambiar de dominio» del runbook. Y **el `.env` de un servidor ya
  instalado tiene la línea escrita**, así que cambiar el `default=` de `settings.py` no lo alcanza:
  se despliega, sale todo en verde y se sigue redactando con el modelo viejo. Esta vez **no es
  silencioso**, porque los tres consumidores escriben «Redactada con …» en la bitácora de cada
  registro; se comprueba en frío con `printenv OPENROUTER_MODELO`.
- **De camino salió que la suite ensuciaba el registro de IA real**: de las 318 entradas del día,
  308 eran de pytest —`modelo pedido : modelo/por-defecto`— y las diez llamadas de verdad quedaban
  ahogadas entre ellas, en un archivo diario, en modo añadir y sin rotación. Cinco pruebas ya
  apuntaban `IA_LOGS_DIR` a `tmp_path` a mano; ahora lo hace un fixture `autouse` de `conftest.py`,
  hermano del que ya aislaba `MEDIA_ROOT` por la misma razón. Tras el arreglo, una corrida completa
  deja el archivo con el **mismo tamaño exacto**.

### Actualización 28/08/2026 — la llave de CARTO, y el estilo que NO se cambió

- **CARTO empezó a exigir llave para sus teselas ráster** y estampaba una marca de agua sobre el
  mapa base «Claro»: el del visor de peligros y **el único fondo** de la ficha del centro poblado.
  La llave entra por `VITE_CARTO_KEY`, artefacto de *build* como la de Meilisearch, con su misma
  cadena: los dos `.env`, `compose.yaml`, `frontend/Dockerfile`. En los `.env.example` va con el
  valor vacío — la credencial no entra en ningún archivo versionado.
- **Lo que más valor tuvo fue no hacer caso al correo.** CARTO recomendaba pasar a
  `rastertiles/voyager`; seguirlo habría cambiado el diseño del mapa sin necesidad. `voyager` va a
  color y este visor está construido sobre el gris casi liso de `light_all` —el que deja leer el
  semáforo, y la razón de que el halo de los puntos sea de 0.5 px **solo** sobre este fondo—. Se
  midió que `light_all` **con** la llave responde 200 y sin marca: el cambio real era añadir
  `?key=` a las URL que ya había.
- **Medido, no mirado.** Comparando la misma tesela con y sin llave: 4,313 píxeles distintos
  (1.6 %), agrupados en diagonal por el centro, y la versión sin llave más oscura en esa banda
  (235.9 frente a 241.8 de luminancia media) — la firma de una marca repetida. En la aplicación,
  12 de 12 teselas salen con `key=` en los dos mapas, y `canvas.toDataURL()` sigue funcionando, o
  sea que **CORS aguanta y la exportación PNG no se rompe** (era el riesgo silencioso: una tesela
  sin CORS contamina el canvas y lanza `SecurityError`).
- **Las URL se juntan en `frontend/src/lib/mapasBase.ts`.** Estaban escritas dos veces carácter por
  carácter, y con una credencial dentro eso es duplicar el sitio donde se olvida de actualizarla.
  Mismo motivo que llevó `pmtiles.ts` a `lib/`. De paso, `vite-env.d.ts` deja de estar vacío de
  tipos propios: ahora un `VITE_CARTO_KEI` mal escrito lo caza `tsc` en vez de devolver `undefined`
  y reaparecer como una marca de agua.
- **Sin llave las URL quedan idénticas a las de antes**, no con un `?key=` colgando: el mapa sigue
  pintando, con la marca. Comprobado vaciando la variable — 12 teselas, cero con `?`. Es lo que
  mantiene `npm run dev` usable para quien no tenga la llave.
- **Sin prueba automática, a propósito.** El CI no corre Playwright ni pytest
  (`bitbucket-pipelines.yml:22`); una prueba que exigiera `key=` fallaría en cualquier máquina sin
  la llave y para pasar habría que repartir la credencial. Y el fallo que protegería **se ve**: la
  marca de agua es visible, que es justo lo contrario del caso silencioso del enlace de la barra
  superior.

### Actualización 28/08/2026 — la barra superior llevaba nueve días sin el enlace a predes.org.pe

- **El síntoma no era el que parecía.** «El enlace no se ve» sonaba a CSS —la banda es blanco al
  90 % sobre `mountain-500`—, pero no había nada que ver: `GET /api/sitio/` del servidor devolvía
  `menu.top: []` y el `<a>` no estaba en el DOM. La banda no lleva una sola clase de breakpoint,
  así que ninguna hipótesis de maquetación podía ser cierta.
- **Se añadió a dos de los tres sitios donde vive el menú.** El 19/08/2026 entró en la semilla
  (`sitio.yaml`) y en el respaldo del frontend (`lib/sitio.tsx`), y faltó el tercero: la base ya
  sembrada. Lo arregla la migración de datos `sitio.0007`, idempotente y reversible, que casa por
  `(zona, url)` como `0004` —el texto es editable desde el admin y casar por él crearía una
  segunda fila en vez de reconocer la que ya está—.
- **Lo que lo volvió invisible fue una frase falsa repetida en cuatro sitios: «el seed corre en
  cada despliegue».** No corre. `docker-entrypoint.sh` hace `migrate` y `meili_setup`, y `seed` es
  un paso manual del runbook para la instalación inicial y las recargas. Por eso el enlace se veía
  perfecto en desarrollo —donde alguien lo sembró a mano después del 19/08— y no existía en
  ningún servidor. Corregida en `08-plan-pruebas.md`, en los docstrings de `test_seed.py` y en la
  regla de `CLAUDE.md`, que ahora pide migración para **cualquier** cambio de menú y no solo para
  uno de visibilidad. Las etiquetas del menú principal sí estaban al día en el servidor, y eso
  confirma el mecanismo: llegaron por las migraciones `0004` y `0005`, no por el seed.
- **La prueba que faltaba era e2e, y se comprobó que falla.** Las tres de `header.spec.ts`
  localizaban `getByRole("navigation", { name: "Principal" })`, o sea solo el nav: la banda
  superior no tenía ninguna cobertura. La nueva exige el `a[href="https://predes.org.pe/"]`
  visible y con `target="_blank"`. Se verificó revirtiendo `sitio.0007` —lo que reproduce el
  estado exacto del servidor—: falla en escritorio y en móvil, y vuelve a pasar al aplicarla. La
  prueba de API que la acompaña guarda la semilla y el serializer, pero **no** habría cazado esto:
  corre sobre una base recién sembrada por fixtures, que es justo el entorno donde el fallo no
  existe.
- **Queda fuera, anotado y sin tocar**: el contraste de la banda (2.2:1 medido en vivo, por debajo
  del 4.5:1 de AA a 12 px) viene del prototipo aprobado; correr `seed --solo-catalogos` en el
  entrypoint cerraría toda esta clase de fallo pero es un cambio de comportamiento del despliegue;
  y `ConfiguracionSitio.redes` se serializa (`web: https://predes.org.pe/`) sin que ninguna
  plantilla lo pinte.

### Actualización 28/08/2026 — una medida nace de una ficha ACC, y el contacto no pasa por la IA (ADR-D10)

- **ADR-D10** extiende ADR-D7/D8 a `medidas.Medida` y estrena lo que faltaba: **un origen que no es
  una URL**. El formulario lleva arriba el select de la ficha ACC y la casilla «Procesar con IA»;
  marcada, los obligatorios dejan de serlo, la medida se guarda al instante y el worker redacta
  título, resumen, tipo de peligro, alcance, resultado, distrito, comunidad, contenido, palabras
  clave, actores, fecha de implementación y costo referencial. Una sola llamada, como siempre.
- **Se generalizó otra vez, y lo que se partió fue el origen.** `RedaccionIAMixin` mezclaba el
  estado de la IA con el hecho de que la procedencia fuera una URL. Ahora `core.EstadoIAMixin`
  tiene el candado, la bitácora y el estado, y `RedaccionIAMixin(EstadoIAMixin)` solo añade
  `url_origen`; quién es el origen lo nombra `campo_origen` en el formulario y
  `fechas_provisionales` dice qué fechas `NOT NULL` provisionar — en medidas, ninguna. **La
  partición no emitió ni una migración** para noticias y normas, y entró con la suite en verde
  (340 pruebas antes, 429 después).
- **Etiquetas XML en la entrada, JSON estricto en la salida.** Diecisiete respuestas de texto libre
  concatenadas se confunden entre sí y varias empiezan igual («Describa brevemente…»), así que cada
  una viaja como `<value_006 pregunta="…">…</value_006>`. La salida no cambia de formato porque es
  lo que hace que el proveedor garantice los `enum`. El valor se escapa: el Excel lo rellena un
  tercero y un `</value_007>` dentro del texto rompería el marcado.
- **El contacto de la ficha no se le manda a la IA, y sí se pega al final del contenido.**
  `value_004` es nombre, cargo, teléfono y correo de una persona; ningún campo de `Medida` se
  alimenta de él y habría quedado en claro en `ia-AAAA-MM-DD.txt`, que es diario y sin rotación.
  Lo pega el servidor en un bloque con la clase `contacto-ficha-acc`, y publicar con ese bloque
  puesto **avisa pero no bloquea**: es el editor quien decide. El marcador tuvo que ser una clase
  y no un comentario HTML — `sanear()` corre con `strip_comments=True` y se lo habría llevado en
  silencio, dejando el aviso sin disparar.
- **`tipo_peligro` pasa a nullable y publicar exige los cinco obligatorios de vuelta.** Era el
  único que no podía guardarse como cadena vacía, y replegarlo a un peligro cualquiera habría
  puesto una clasificación falsa que nadie revisaría. La guarda vive en
  `WorkflowMixin.transicionar()` y no en un `clean()`, porque `estado` está excluido del formulario
  y publicar no pasa por ninguno. El título provisional cuenta como faltante.
- **El candado es la ficha, y es derivado**: sin campo nuevo, una ficha está gastada si alguna
  medida la referencia con `redactada_por_ia=True`. Dos trampas que costaron su prueba cada una: el
  queryset del select **tiene que incluir la propia ficha** de la medida que se edita —si no, una
  medida ya redactada no se puede volver a guardar nunca, y el mensaje sería «Escoja una opción
  válida» sobre un campo que el editor no tocó—, y la tarea vuelve a comprobarlo porque entre
  validar el formulario y encolar caben dos peticiones.
- **`Decimal("0.00")` es *falsy*, y un costo de cero es un dato legítimo.** «Aporte comunal, sin
  costo monetario» es una respuesta real de la ficha, así que `costo_referencial` y
  `fecha_implementacion` se comprueban con `is not None`. Es el equivalente de lo que `Noticia.tipo`
  fue en ADR-D7: el campo donde «¿está lleno?» no significa lo que parece.
- **Probado de extremo a extremo contra el API real, y ahí salió lo que ninguna prueba con dobles
  iba a ver.** Con `deepseek/deepseek-v4-flash-0731` —el valor por defecto de `OPENROUTER_MODELO`—
  la misma ficha dio tres resultados distintos en tres llamadas de ~$0.0002, y en las tres el
  `contenido` volvió **en texto plano o en Markdown**, transcribiendo la ficha campo por campo en
  vez de redactarla; una de ellas además dejó `ambito` en «regional» para una experiencia comunal y
  `actores` en «community». La misma ficha con `google/gemini-2.5-flash` salió con subtítulos
  `<h2>`, la clasificación correcta y cero avisos, por $0.003. **La variable no se cambió**: afecta
  también a noticias y normas y es una decisión de coste del dueño del proyecto. *(Se cambió ese
  mismo día, tras medir los otros dos consumidores — ver la entrada de más arriba y ADR-A23.)*
- **De ahí salieron tres arreglos que no estaban en el plan**, los tres del mismo tipo —cosas que
  se ven mal sin fallar—: un `contenido` sin etiquetas se envuelve en párrafos y queda anotado en
  el registro de la IA (el frontend lo inyecta con `dangerouslySetInnerHTML`); «180,000 soles» se
  lee como monto, porque quitar el separador de millar no cambia la cifra —lo que se sigue
  rechazando son las otras monedas, que exigirían inventar un tipo de cambio—; y «2019-2022», que
  es lo que el modelo devuelve cuando se le pide la fecha de inicio de un periodo, se fecha al 1 de
  enero de 2019 con su aviso, en vez de perderse.
- **Una lección de método, y es la misma que dejó ADR-D8 escrita**: la prueba que comprobaba el JS
  renderizando la pantalla del admin volvió a fallar por el manifiesto de estáticos, no por el
  código. La comprobación que vale es la de `ModelAdmin.media`; la de la pantalla se quedó, pero
  mirando el bloque «Origen», que es lo que sí puede romperse al tocar un `fieldsets`.

### Actualización 28/08/2026 — la ficha ACC se suelta de la medida y se carga en lote (ADR-D9)

- **La ficha ACC deja de colgar de una `Medida`.** La FK obligatoria se elimina del modelo: el
  formulario que PREDES reparte es autónomo, y exigir una medida ya publicada a la cual colgarlo
  bloqueaba la carga sin aportar nada. **Nadie leía esa relación** —ni serializer, ni endpoint, ni
  frontend, ni semilla, ni una sola prueba; solo el diagrama ER—, así que el radio de impacto se
  agotó en `admin.py`. **La migración es irreversible** y se aceptó a sabiendas: se pierde qué
  ficha pertenecía a qué medida en lo ya cargado. Quien identifica la ficha pasa a ser `value_001`.
- **Su importador no pasa por `DatasetUpload`, y eso acota la regla en vez de romperla.** Esa vía
  se diseñó para datasets de reemplazo total, asíncronos y todo-o-nada; las fichas son lo contrario
  en las tres dimensiones —aditivas, parciales por diseño y síncronas, porque la confirmación tiene
  que responder en el momento—. La regla queda escrita como dos vías que no se mezclan, y el import
  ad-hoc sigue prohibido.
- **La cabecera aborta el archivo entero; una fila mala, no.** Es la asimetría que sostiene todo lo
  demás: con las columnas corridas cada texto se guardaría en el campo de al lado y la ficha
  quedaría **plausible y mal**, que es justo lo que no da síntomas. Una fila incompleta o repetida
  se omite con su motivo y las demás entran. La cabecera sí tolera espacios de más y tildes
  perdidas, porque son preguntas largas que el usuario copia y pega.
- **El nombre repetido se compara recortado y en mayúsculas, y solo para comparar.** Se guarda el
  texto tal como vino: normalizarlo al guardar destrozaría el nombre que PREDES publica. Se detecta
  contra la base y dentro del propio archivo. **No hay `UniqueConstraint`**: los datos ya cargados
  podrían violarla y la migración fallaría en producción sin un mensaje útil, así que la regla vive
  en el importador. El alta manual sigue admitiendo un repetido — asimetría deliberada.
- **Los 17 `verbose_name` son la única fuente**: de ahí salen la plantilla descargable, el
  validador de la cabecera y la lista que se pinta en pantalla, así que solo pueden separarse por
  accidente. Hay una prueba redonda que descarga la plantilla, la rellena y la importa.
- **Dos hallazgos de camino.** El Excel a medio importar necesitaba un sitio, y el primero elegido
  cayó **dentro del repositorio**: la suite dejaba ahí un `.xlsx` por prueba y el barrido solo se
  lleva los de más de seis horas. Ahora es `IMPORTACIONES_TMP_DIR`, fuera de `MEDIA_ROOT` por lo
  mismo que `IA_LOGS_DIR`, ignorado en git, y una fixture `autouse` lo manda a `tmp_path`. Y el
  **CSS de Unfold viene precompilado**: `sm:grid-cols-2`, `tabular-nums`, `list-decimal` y varias
  más no existen, y una clase ausente **no da error, simplemente no hace nada** — las dos tarjetas
  del resumen salían apiladas por eso. Queda anotado en CLAUDE.md; `templates/admin/index.html` ya
  tenía tres clases muertas de antes.
- Quince pruebas nuevas en `backend/tests/test_fichas_acc.py`; la suite pasa de 340 a 355.

### Actualización 28/08/2026 — el flujo editorial pierde el paso de revisión (ADR-P3)

- **ADR-P3**: los estados pasan a ser **`borrador → publicado`**, con `archivado` para retirar sin
  borrar, y el grupo **Editor recibe `puede_publicar`**. Las dos mitades van juntas: al quitar el
  paso de revisión, «Enviar a revisión» era la única acción que tenía un Editor sobre su propio
  contenido, así que sin el permiso se quedaba sin poder hacer nada.
- **Se aparta del requisito 2 del TDR**, que pedía literalmente «borrador → revisión →
  publicación». Queda dicho en el ADR y anotado en la propia lista de requisitos: documentarlo como
  si el TDR no lo pidiera habría sido la peor forma de resolverlo. La otra mitad del requisito —los
  avisos por correo— **se conserva**.
- **Lo que queda para contener el riesgo** de que nadie mire antes de publicar: el estado sigue sin
  editarse a mano (un `<select>` guardaría el cambio sin disparar el aviso ni registrar quién fue),
  y `TRANSICIONES_RESERVADAS` se conserva entera — ya no separa a un editor de un publicador, pero
  es lo único que impide publicar a una cuenta de staff **sin grupo**.
- **Los correos se reducen a dos y los dos van al autor**, y se añade una regla nueva: **no se
  avisa a quien se avisaría a sí mismo**. Ahora el autor suele ser quien publica, y un correo que
  informa a alguien de lo que acaba de hacer es la forma más rápida de que se dejen de leer todos
  los demás. Se retiran la constante `GRUPOS_REVISORES` y las plantillas `emails/a_revision.*`, y
  se corrige `publicado.html`, que decía «que enviaste a revisión fue publicada».
- **Dos migraciones de datos, y ninguna es opcional.** La columna `estado` **no tiene `CHECK` en
  PostgreSQL** —comprobado—, así que una fila que quedara en `revision` no daría ningún error: se
  mostraría en crudo y sin ninguna transición que la sacara de ahí; va un `RunPython` defensivo en
  las cinco apps. Y el permiso del Editor necesita la suya (`core.0001`) porque **el seed no corre
  en el despliegue**: `docker-entrypoint.sh` solo hace `migrate` y `meili_setup`, así que cambiar
  `seed.py` solo se vería en instalaciones nuevas. Es el mismo razonamiento de `sitio.0002`.
- **Fuera del panel** el aviso «N contenido(s) esperando revisión» y su columna: con el estado
  retirado contarían siempre cero, y una columna que siempre vale cero se lee como un dato.
- **`revisado_por` y `nota_revision` conservan su nombre** aunque hoy signifiquen «quién publicó o
  retiró» y «por qué se retiró». Renombrarlos costaba catorce `AlterField` en cinco apps para
  cambiar dos rótulos.
- **Comprobado en el admin con un usuario del grupo Editor**: ve «Publicar», «Retirar del sitio» y
  «Archivar», no ve «Enviar a revisión», y publica un borrador de un clic sellando `publicado_en`.

### Actualización 28/08/2026 — una noticia puede nacer de una URL (ADR-D7)

- **ADR-D7**: el formulario de Noticias lleva arriba **URL de origen** y la casilla **«Procesar con
  IA»**. Marcada, los obligatorios dejan de serlo, el registro se guarda al instante y el worker
  rellena título, bajada, cuerpo, tipo, autor, fecha, palabras clave y **la portada** desde la
  `og:image`. Editable después, y **una sola vez por registro**.
- **Asíncrono, con los números delante.** gunicorn corre con `--timeout 120` y 3 workers, y la
  llamada puede tardar hasta ~120 s (60 s más el reintento con backoff): síncrono, gunicorn mataría
  al worker **justo en el límite** y el editor vería un 502 con el guardado a medias, mientras tres
  redacciones a la vez dejarían el admin sin atender. Para que el asíncrono sea usable, **la ficha
  se refresca sola**: sondea un endpoint de estado y recarga al terminar. Esa ruta va **antes** de
  `admin.site.urls`, o el `catch_all_view` del AdminSite la deja en 404 sin que nada más falle — la
  misma trampa que rompió la subida de imágenes de CKEditor en su día.
- **El candado solo se cierra si la IA llegó a escribir**, por decisión del usuario. Un timeout deja
  `ia_estado=error` con el motivo y permite reintentar: un corte de red no puede inutilizar una
  noticia para siempre.
- **Relajar los obligatorios en el formulario no bastaba.** `slug`, `titulo`, `bajada` y `fecha` son
  `NOT NULL` y `slug` además `unique`: `fecha=None` da `IntegrityError` y dos noticias sin slug
  chocan entre sí. Se rellenan con provisionales al guardar —el slug con sufijo aleatorio— en vez de
  migrar el modelo a `null=True`, que dejaría publicar noticias sin título.
- **Tres cosas que solo salieron al probar, y una era un fallo:**
  - **`tipo` tiene default**, así que la comprobación de «¿lo escribió una persona?» lo leía siempre
    como escrito a mano y **la clasificación de la IA no se aplicaba nunca**. Lo delató el propio
    registro, que declaraba «se conservó lo escrito a mano en: tipo» sobre algo que nadie había
    escrito. Ahora solo se respeta un valor distinto del default, y hay dos pruebas.
  - **Del mismo modelo hay proveedores sin salida estructurada** (CoreWeave, DigitalOcean, DeepSeek,
    BaseTen, GMICloud, Relace, StreamLake), y OpenRouter enruta cada petición por separado — las dos
    llamadas reales del día anterior habían caído justo en dos de ellos. Se fija con
    `provider.require_parameters`; sin eso la función falla de forma intermitente.
  - **`/media/` es público**: nginx lo sirve entero con CORS `*`. Los `.txt` de la IA van al mismo
    directorio que `despliegue.log` y `vigilancia.log`, por bind mount que **nginx no monta**.
- **La descarga se acota.** Solo `http`/`https`, y se resuelve el nombre para rechazar destinos
  internos: la URL la escribe un editor y la petición la hace el servidor, así que sin eso el
  formulario sería una vía para sondear la red privada desde dentro.
- **El saneador de ADR-D2 estrena papel**: ser la red bajo un HTML que no escribió una persona. El
  cuerpo propuesto pasa por `HtmlRicoMixin.save()` como todo lo demás.
- **Probado de extremo a extremo contra el API real**: una noticia del portal del Senamhi quedó con
  titular, bajada, cuerpo, autor, fecha, cinco palabras clave y portada descargada, por $0.000318.

### Actualización 28/08/2026 — OpenRouter: una pasarela para el resto de los usos de IA (ADR-A22)

- **ADR-A22**: **OpenRouter** entra como pasarela de IA de propósito general, con la librería
  `openai` apuntada a su `base_url` — OpenRouter expone esa misma API, así que no hay que llamar a
  OpenAI para usar su cliente. Un solo secreto y un solo cliente para cualquier modelo, y **el
  modelo se elige con `OPENROUTER_MODELO`**: cambiar de proveedor deja de ser código y pasa a ser
  una variable de entorno.
- **A10 no se supera.** Gemini conserva los resúmenes de PDF porque lee el PDF de forma nativa, que
  es de lo que depende esa función. Conviven, y la frontera de proveedor sigue confinada a
  `services/` y a las settings: los campos del modelo ya se llaman `ia_estado` y `log_ia`, sin el
  nombre de nadie.
- **Se entrega solo la capa de servicio**, por decisión del usuario:
  `apps/core/services/openrouter.py`, las settings, el bloque de `backend/.env.example`, la
  dependencia y las pruebas. Todavía no la usa ninguna pantalla.
- **La continuidad del razonamiento es lo único que puede romperse en silencio.** OpenRouter exige
  que `reasoning_details` se reenvíe idéntico y en el mismo orden; si se altera, la segunda llamada
  responde igual de bien y el modelo simplemente ya no retoma su razonamiento. Lo resuelve
  `Respuesta.como_mensaje()`, y lo fija una prueba que compara el bloque reenviado con el recibido.
- **Dos trampas del SDK, documentadas donde se tropieza con ellas.** `reasoning_details` es un campo
  *extra*: el atributo **no existe** cuando el modelo no razona, así que leerlo directo revienta en
  vez de degradarse — va con `getattr`. Y `razonamiento` acepta `None`/`bool`/`dict` sin traducir
  nada: inventar aquí un vocabulario propio solo añadiría una capa que mantener sincronizada.
- **De paso se cumple lo que 03 pedía y nunca se implementó**: timeout de 60 s y un reintento con
  backoff. No hay que escribirlos — el cliente de `openai` los trae y basta pasárselos al
  constructor. Tampoco se hereda el otro desajuste de Gemini, que ignora su propia
  `GEMINI_MODELO` y lleva el modelo escrito a fuego.
- **`manage.py ia_probar`** hace una llamada real y muestra modelo, texto, tokens y coste. Existe
  porque todo lo demás se prueba con un cliente falso: sin él, la única forma de saber si la llave
  y el modelo sirven sería conectar la capa a una pantalla y descubrirlo ahí. No es un `estado`
  para un cron —gasta dinero—, y ahí está la diferencia con `meili_estado`.
- **Coste que queda escrito por primera vez**: la llave viaja también a los contenedores `db`,
  `meilisearch` y `backup`, que comparten `env_file: backend/.env`. Ya ocurría con
  `GEMINI_API_KEY` y no constaba en ninguna parte.
- **Dos cosas que solo salieron al probar contra el API real**, con la llave puesta:
  - **`razonamiento=None` no significa «sin razonamiento».** El modelo configurado razona por
    defecto, así que `None` —que deja mandar al proveedor— sigue pagando esos tokens. La bandera
    `--sin-razonamiento` de `ia_probar` mapeaba a `None` y **quedaba sin efecto**, sin que nada lo
    delatara: la respuesta era correcta y la factura, la misma. Ahora manda `False` (44 tokens de
    salida contra 3) y hay una prueba que lo fija. `{"exclude": True}` es otra cosa distinta: el
    modelo razona igual y **se cobra igual**, solo que no devuelve los bloques.
  - **OpenRouter enruta cada petición por separado**: en la misma conversación el turno 1 salió por
    CoreWeave y el 2 por DigitalOcean. La continuidad del razonamiento aguanta el salto, pero **los
    tokens de entrada no son comparables entre turnos** —cada upstream cuenta a su manera; el
    segundo turno, con más historial, informó menos entrada que el primero—. Si alguna vez hace
    falta un conteo estable, hay que fijar el proveedor con `extra_body={"provider": …}`.

### Actualización 28/08/2026 — noticias: destacadas primero, y el cuerpo que se leía en HTML

Dos restos de la fase prototipo en la misma sección.

- **El orden.** `Noticia.Meta.ordering` era `["-fecha"]`: el campo `destacada` existía, era
  filtrable y no ordenaba nada. Pasa a **`["-destacada", "-fecha", "-id"]`** por decisión del
  usuario, aplicado **en todo el API** para que lo sirvan igual la portada y `/noticias`. Sin
  distintivo visual en las tarjetas, también por decisión explícita: una destacada antigua puede
  quedar por encima de otras más nuevas sin que nada en pantalla lo explique.
- **El remate único no es cosmético.** `fecha` es un `DateField` y `/noticias` acumula páginas con
  `useApiPaginado`: `["-fecha"]` ya era un **orden parcial**, el mismo fallo silencioso que costó
  filas repetidas en `/api/ccpp/`. Anteponer `-destacada` lo habría agravado —crea un bloque
  enorme de empates—, así que el `-id` entra en el mismo cambio. Lo fija
  `test_el_listado_de_noticias_no_repite_ni_se_salta_filas_al_paginar`.
- **El índice sigue al orden.** `(estado, -fecha)` dejaba de cubrir el `ORDER BY`; se sustituye por
  `(estado, -destacada, -fecha)` en la migración `contenidos.0002`.
- **El admin se queda cronológico** (`ordering = ("-fecha",)` en `NoticiaAdmin`). La lista del
  admin es una cola de trabajo, no la portada, y `destacada` ya es columna ordenable ahí.
- **El cuerpo se pintaba como texto.** `NoticiaDetalle.tsx` seguía con el
  `whitespace-pre-line` del prototipo, cuando `cuerpo` venía de un JSON en texto plano; hoy es
  HTML de CKEditor y en `/noticias/mesa-tecnica-quispicanchi` se leían las etiquetas. Pasa por
  **`ContenidoRico`**, que es lo que ya usaban `NormaDetalle` y `MedidaDetalle` — noticias fue la
  única que se quedó atrás. Además de pintarlo, el componente devuelve tamaño a los encabezados y
  viñetas a las listas (el Preflight de Tailwind los resetea) y convierte el `<oembed>` del editor
  en un iframe: sin él, **un video incrustado en una noticia no se vería**.
- **Ninguna de las dos tenía prueba.** Ahora: dos de backend en `test_api_editorial.py` y
  `e2e/noticias.spec.ts`, el primer spec e2e que cubre el HTML rico en cualquier ficha. Las dos
  del e2e se comprobaron en rojo antes de arreglar.

### Actualización 28/08/2026 — la portada decía 4 y `/medidas` listaba 6

La banda de cifras mostraba **4** experiencias mientras la sección enseñaba **6** filas. No era un
error de cálculo: `Home.tsx` pedía `/api/medidas/?resultado=exito`, y el listado de `/medidas` no
filtra por resultado al cargar. Las dos que faltaban son precisamente las que **no** son casos de
éxito — una «lección aprendida» (EVAR desactualizado, Quispicanchi) y una «mal-adaptación»
(reservorio sin operación, Paucartambo).

- **El problema no era la cifra, era el par.** Cada número describía bien lo suyo, pero puestos a un
  clic de distancia el visitante solo ve un descuadre, y la pantalla no ofrece nada que lo explique.
- **La decisión (usuario, 28/08/2026): la tarjeta cuenta el total publicado en Medidas**, sin filtro
  de resultado, y **el texto de la tarjeta no se toca**. Queda registrado que la etiqueta sigue
  diciendo «Experiencias exitosas» mientras cuenta también la lección y la mal-adaptación; es una
  decisión explícita, no un descuido.
- **El arreglo.** Se quita `resultado: "exito"` de la llamada y se renombran los locales
  (`medidasPublicadas` / `totalMedidas`), que si no mentirían sobre lo que contienen. Se conserva el
  `page_size: 1`: solo se usa `count`, que es el total de la queryset y no el de la página.
- **La prueba.** `e2e/home.spec.ts` compara la tarjeta contra el `count` de `/api/medidas/`. Espera
  la petición **sin filtros** por expresión regular (`/medidas/?page_size=1$`) porque la portada
  hace una segunda a `/medidas/?destacada=true…` para el carrusel de casos, y por subcadena se
  quedaría con la que llegue primero. Antes no había ninguna prueba sobre esta cifra.
- **Hallazgo aparte, sin cerrar.** El primer caso de `home.spec.ts` busca «Centros poblados
  monitoreados», etiqueta que ya no existe en la portada (solo sobrevive en `prototype/`), y falla
  por una causa previa y ajena. El tracker estaba apagado al detectarlo, así que queda pendiente de
  issue.

### Actualización 27/08/2026 — la suite E2E no cabía en su propia cuota (429)

La suite completa fallaba en bloque —`peligros`, `inversion`, `medidas`, `buscar`— y parecía una
regresión de los cambios del día. No lo era: **el API respondía 429 a media corrida**.

- **La aritmética.** `AnonRateThrottle` a `anon: 1000/hour` por IP se aplicaba **igual en desarrollo
  que en producción**: no estaba dentro de ningún `if DEBUG`. La suite son 56 casos × 2 proyectos =
  112 corridas, **cada una con caché de navegador fría** —Playwright abre un contexto nuevo por
  prueba, no hay `storageState`— y la portada sola dispara 8 peticiones. ~1.100 contra 1.000: **la
  suite no cabe en la cuota**, y una vez agotada todo responde 429 durante el resto de la hora.
- **Por qué costó verlo.** *Un 429 no se parece a un límite, se parece a un sitio caído.* La prueba
  solo ve que los datos no llegan y agota sus 30 s igual que con el backend muerto. Lo delató que
  las corridas **sueltas** pasaban siempre: el fallo dependía del volumen, no del código. Se
  confirmó recargando la portada a mano mientras la suite corría — la consola pasó de 0 a 8 errores,
  los ocho `429`.
- **La caché no era la salida.** Era la hipótesis natural («que no repita las peticiones»), y no
  sirve: cada prueba parte de un contexto nuevo, así que no hay nada que reutilizar.
- **El arreglo.** `THROTTLE_PRODUCCION` en `settings.py` conserva los valores del servicio, y cada
  uno se puede sustituir por su variable de entorno; **vaciarla desactiva ese límite**.
  `compose.dev.yml` las vacía las tres. Producción no cambia: sin variables definidas rigen los
  mismos 1000/hora, 30/hora y 600/min, comprobado en un contenedor sin ellas.
- **Las tres, no solo `anon`.** `descarga: 30/hour` es aún más justa, y `inversion.spec.ts` pide el
  PDF en los dos proyectos.
- **La prueba que lo cazó bien.** `test_las_descargas_estan_limitadas` afirmaba sobre la tasa
  *efectiva* y se puso roja al vaciarla — tenía razón en existir, pero el anclaje ya no valía: ahora
  afirma sobre `THROTTLE_PRODUCCION`, que no depende de dónde se corra. Una prueba de configuración
  debe fijar **la decisión**, no el valor que resulte del entorno.
- El techo de **producción** sí va corto (125 vistas/hora por IP, y una oficina tras NAT comparte
  IP), pero es otra decisión: queda con la caché en `_docs/deuda-tecnica.md`, archivo nuevo porque
  el tracker estaba inaccesible ese día.

### Actualización 27/08/2026 — los textos de la portada, «Buenas prácticas» y la lupa

Encargo de contenido con dos consecuencias técnicas que solo salieron al medirlo.

- **El hero no necesitaba tocar código.** El título y el subtítulo pedidos ya estaban, palabra por
  palabra, en la semilla y en los respaldos de `Home.tsx` desde el commit `b635d54`; lo que se veía
  salía de la base, que se quedó con los del prototipo. Segunda vez en el mismo día que aparece este
  patrón: **si un texto administrable «no cambia», mirar la BD antes que el código.**
- **`Medidas` → `Buenas prácticas` en todo lo visible**, con una regla para no pasarse: se cambia
  donde nombra la sección (menú, pie, H1, grupo del buscador, `Comparar`), y se deja donde «medidas»
  es un sustantivo común dentro de una frase. La ruta `/medidas`, el API, el índice de Meilisearch y
  el admin **no se tocan**. De paso cierra una incoherencia que ya existía: la tarjeta de la portada
  decía «Buenas prácticas» mientras el menú decía «Medidas».
- **El buscador de la cabecera colapsa a lupa entre `lg` y `xl`.** Con la etiqueta nueva el nav pasa
  de 496 a **555 px** a 1024 px, y al campo le quedaban **63 px**. Lo importante: *la prueba de la
  línea única seguía pasando* —no hay enlaces partidos ni desborde—, así que el arreglo anterior
  «que el buscador ceda» habría degradado el buscador hasta lo inservible **sin que nada fallara**.
  De `md` a `lg` el campo sigue visible, porque ahí el menú está tras la hamburguesa y sobra sitio.
- **Tres pruebas de la portada estaban en rojo con el sitio perfecto.** No era un fallo del front
  —las 8 peticiones responden 200 y la consola está limpia—, sino del arnés: `esperarApi` registraba
  el escucha **después** de `page.goto()`, y como `goto` resuelve con `load` (que espera la imagen
  del hero), React ya había disparado y recibido sus peticiones. La única que pasaba lo hacía por
  casualidad: esperaba `/api/sitio/`, la última respuesta en llegar. El spec 08 ya había anotado la
  trampa para `inversion.spec.ts` sin generalizarla; ahora vive en `irEsperando`, que registra y
  luego navega, y se aplicó a los **37 sitios** con ese patrón. `esperarApi` se queda para las
  esperas que siguen a un clic, donde no hay carrera.
- Migración `sitio.0005`. Los bloques del hero se reescriben **solo si conservan el texto viejo
  exacto**: son contenido que PREDES edita, y el contrato es no pisar lo editado.

### Actualización 27/08/2026 — el menú abre con «Sobre el observatorio»

Cambio pedido sobre el menú principal: «Exposición a peligros» pasa a llamarse **«Peligros»**,
«Sobre» pasa a **«Sobre el observatorio»**, y esta última **abre el menú** en lugar de cerrarlo. El
nav queda `Sobre el observatorio · Peligros · Medidas · Inversión · Normativa` (Medidas pasó a
«Buenas prácticas» ese mismo día, ver la entrada de arriba), y la barra superior
gris se queda con `predes.org.pe` y `Contacto`.

- **La mitad del cambio ya estaba en el código y no se veía.** El commit `51a9795` había renombrado
  las etiquetas en la semilla y en el respaldo del frontend, pero **sin migración de datos**: como
  `semilla.sembrar` crea lo que falta y no pisa lo que existe, la base ya sembrada seguía sirviendo
  las etiquetas viejas y el cambio solo se habría visto en instalaciones nuevas. Que la zona `top`
  estuviera **vacía** en la BD fue la prueba de que `seed` no había vuelto a correr desde entonces.
- **La trampa que cerró la migración `sitio.0004`.** El seed casa las filas por
  `(zona, url, texto)`, así que cambiar solo la etiqueta del YAML **no actualiza** la fila: crea una
  segunda, y el menú habría mostrado «Exposición a peligros» *y* «Peligros». La migración opera por
  `(zona, url)` —lo estable— y desduplica antes de renombrar, por si algún entorno ya había sembrado
  con el YAML nuevo. Se comprueba con una prueba que corre `seed` **dos veces** y exige que ningún
  `(zona, url)` tenga más de una fila; y tras aplicarla, `seed` reporta *1 enlace nuevo* (el
  `predes.org.pe` de la barra superior, que nunca llegó a sembrarse) y *17 ya existían*.
- **El menú sigue entrando en una línea, y esta vez se midió.** «Sobre el observatorio» tiene los
  mismos 21 caracteres que «Exposición a peligros», la etiqueta que en su día partía el nav en dos a
  1024 px. Ahora no se parte porque aquel arreglo dejó los enlaces con `whitespace-nowrap` y al
  buscador como el que cede: a 1024 px el nav mide 495 px y el buscador baja a 184 px (campo de
  134 px, con el marcador de posición recortado). Pasa, pero sin margen para otra entrada.
- Los tres sitios tocados, como manda la regla: la semilla, la base sembrada (migración) y el menú
  de respaldo de `frontend/src/lib/sitio.tsx`. Se corrigieron además 02 y 06.

### Actualización 27/08/2026 — el pipeline llega a los specs, y la documentación deja de mentir

El despliegue automático de la entrada de abajo quedó bien contado en `_docs` y en esta bitácora,
pero **no en `_specs/`**. Y este proyecto tiene escrito que para operar sirve `_docs/` y **para
implementar manda `_specs/`**, así que quien fuera a tocar el despliegue leyendo los specs se
encontraba el mundo anterior. Nuevo **[10-pipeline-cicd.md](10-pipeline-cicd.md)** y **ADR-A21**.

El spec no repite el procedimiento —eso ya está en `_docs/despliegue.md`— sino el orden, las
invariantes de cada etapa y tres cosas que no estaban escritas en ninguna parte: que un check verde
de Pipelines significa que **el frontend compila**, no que las pruebas pasaran —el CI no corre
`pytest` ni Playwright, a propósito—; que solo despliega **QA** y no producción; y que el pipeline
vive en **`drinux`**, de modo que un `git push` a secas, que solo alcanza `origin`, deja el entorno
sin desplegar y nada avisa.

Lo que obligó a mirar el resto fue el runbook de **07**, que seguía mandando desplegar con
`git pull && build && up -d` —la cadena sin `run --rm frontend` que causó justo el incidente de la
entrada siguiente— y ofrecía un `docker compose run --rm certbot renew` que **no renueva nada**: el
servicio tiene `entrypoint` propio con un bucle, así que el argumento se ignora y el comando se
queda en primer plano. Se quitó la tabla entera en vez de corregir esas dos filas. Las diez estaban
cubiertas, y mejor, en `_docs/despliegue.md`; mantener la segunda copia fue lo que produjo la
divergencia, y corregirla sin quitarla solo aplazaba la siguiente.

De ahí salió un barrido de todo lo que la documentación decía y ya no era cierto:

- **Las cifras de pruebas.** «144 pruebas» en tres sitios y «112 + 4» en un cuarto, cuando
  `--collect-only` da **259**, más **7** marcadas `lento`. Las E2E eran otro caso: «56» no estaba
  mal, estaba sin declarar qué contaba —son 56 casos que Playwright ejecuta 112 veces, uno por
  proyecto— y sin decir cuál es, la siguiente persona lo «corrige» al otro. Donde la cifra se
  conserva queda al lado **el comando que la reproduce**; donde solo era el síntoma de una `.so`
  ausente, se quita.
- **Dos párrafos que anunciaban un número distinto al de su propia tabla**: ocho comprobaciones
  sobre nueve, cinco fallos silenciosos sobre seis.
- **Una tabla partida en dos** en `_docs/despliegue.md`: el aviso del tracker estaba dentro del
  runbook y dejaba once filas huérfanas bajo una cabecera falsa. No lo encuentra ningún `grep`.
- **Cuatro archivos de prueba sin declarar** en 08 —`test_api_salud`, `test_cola_estado`,
  `test_meili_llave` y `test_señales_meili`—, que son precisamente los que cumplen la regla del
  documento: cada uno cubre un fallo que no da síntomas.
- **Cinco comentarios que citaban ADR-D3 en presente**, superado por D4 el 10/08. Decir la razón
  vieja invita a «arreglarlo» añadiendo el bloque de inversión cuando lleguen los datos, y los datos
  ya llegaron: la razón vigente es que su unidad es la municipalidad y no el distrito.
- **Una referencia colgante** a `install-rocky-10.sh`, citado dos veces como si bastara con buscarlo.
  No está y no debe estar: es provisión de la máquina.

Y un documento nuevo fuera de los specs: **`_docs/deuda-tecnica.md`**. Este repositorio no tiene ni
un `TODO` ni un `FIXME` —cada decisión está donde toca, con su comentario—, y el efecto secundario es
que la deuda es invisible desde el código: quien llega no distingue una decisión de un olvido. El
documento **no guarda estado**; cada entrada apunta a su ADR, a su spec o a su archivo, y dice qué la
salda con un disparador en vez de una fecha. Lo roto sigue solo en el tracker: un inventario que
además listara defectos sería un segundo tracker, y de eso este proyecto ya salió una vez.

`pytest` 259/259 (7 deseleccionadas por `lento`) y `npm run lint` sin errores tras tocar los
comentarios de `incidencia.py`, `Comparar.tsx`, `Home.tsx` y `test_api_sitio.py`.

### Actualización 27/08/2026 — el sitio servía el bundle de hace dieciséis días, en verde

Los últimos commits no se veían en el entorno de desarrollo. La causa: el despliegue se había hecho
con `docker compose up -d` **sin `--build`**. Como el servicio `frontend` es de un solo disparo y su
`CMD` empieza por `rm -rf /out/*` y vuelve a copiar su `dist` al volumen que sirve nginx, el sitio se
«refrescó» —`index.html` con fecha de ese día, `last-modified` nuevo— con el bundle del 11/08. El
backend, igual, con la imagen del 11: los cambios de `filters.py`, `serializers.py`, `consultas.py` y
`medidas/models.py` no estaban corriendo.

**Lo que hace grave a este fallo no es la causa, que es trivial, sino que es indistinguible del
éxito.** Todo lo que uno miraría daba bien: la SPA 200, el API 200, los siete contenedores `healthy`,
`last-modified` de hoy, cero errores en los logs de nginx, del backend y del worker. La única forma de
verlo era abrir el bundle y buscar dentro un texto que se había cambiado. `deploy/comprobar-sitio.sh`
ya declaraba este punto ciego en su cabecera desde que se escribió —«que nginx conteste pero sirva el
bundle equivocado»— y no lo cubría.

Recompilar no es evitable: **Vite hornea el bundle y las `VITE_*` en tiempo de build**, no hay nada
que leer en runtime. La pregunta no era si se construye, sino quién se acuerda y cómo se sabe que
llegó. Son dos problemas distintos y se arreglan por separado:

- **Quién se acuerda** → `deploy/desplegar.sh`, el despliegue entero en un comando, que sustituye a
  la cadena de cinco del runbook. Olvidar uno de los cinco es exactamente lo que pasó, y ya había
  pasado antes por otro eslabón: la entrada del 05/08 de más abajo corrigió esa misma cadena porque
  no recargaba nginx. Un procedimiento que se arregla añadiéndole pasos es un procedimiento que
  volverá a fallar.
- **Cómo se sabe que llegó** → el script **sella** el SHA desplegado en `/version.txt`, dentro del
  propio `dist`, y luego lo pide por HTTPS y lo compara. Si el `dist` publicado no es el de ese
  commit, el archivo delata el que sí es y el despliegue **falla** en vez de terminar en verde.
  `comprobar-sitio.sh` acepta ese SHA como cuarto argumento; sin él informa el servido sin juzgarlo,
  que es lo que quiere un cron desde fuera —no sabe qué commit debería estar arriba—.

En `master` lo lanza **Bitbucket Pipelines** por SSH (`bitbucket-pipelines.yml`), tras comprobar los
tipos del frontend. El pipeline no lleva lógica ninguna a propósito: el procedimiento vive en el
script versionado y **vale igual lanzado a mano**. El CI no es un procedimiento paralelo, solo es
quien llama — si el script no sirve desde una terminal, no sirve.

El build sigue ocurriendo **en el servidor**, no en la nube de Atlassian: la imagen del backend
compila tippecanoe desde el código fuente e instala Chromium, así que construirla allí sin caché de
capas costaría más de lo que ahorra y obligaría a montar un registry. Si algún día molesta, la salida
es Pipelines + registry y el script no cambia.

Dos gotchas que el script trata y la cadena manual no:

- **`nginx -s reload` devuelve 0 aunque la configuración esté rota.** Solo manda la señal; el maestro
  rechaza la recarga por su cuenta y escribe el error en *su* log. Sin un `nginx -t` delante, un error
  de sintaxis en `conf.d/` pasaría el despliegue en verde dejando nginx con la configuración
  anterior — la misma familia de fallo silencioso que originó esta entrada.
- **`git pull --ff-only`**, para que una historia divergida falle en vez de fabricar en el servidor un
  merge que no está en Bitbucket y que nadie vería nunca.

La clave SSH de Pipelines vive en `~/.ssh/authorized_keys` del servidor **restringida con `command=`**:
no da shell, ni túneles, ni agente; lo único que puede hacer es redesplegar `master`. Una clave con
acceso a esa máquina que se guarda en un tercero tiene que poder hacer una sola cosa.

Sin issue en el tracker: se encontró y se cerró en el acto. El detalle operativo está en
`_docs/despliegue.md` y en `_docs/despliegue-entorno-desarrollo.md`.

### Actualización 05/08/2026 — el tracker publicado en `/gitea`, y el nginx que no se enteró

El tracker pasó a modo **publicado** en el servidor de desarrollo: se levanta con
`compose.tracking.yaml` + `compose.tracking-publicado.yml`, con `RED_APP` y `TRACKER_URL` en el `.env`
de la raíz, y se llega por el dominio del API sin túnel. No hizo falta tocar el DNS, ni el
certificado —la subruta cuelga de un dominio que ya existía—, ni editar nginx.

Lo que sí destapó es un **fallo de la documentación de despliegue**, y es el motivo de esta entrada:

**El comando de «desplegar una actualización» no recargaba nginx.** El one-liner documentado en el
README y en el runbook de `_docs/despliegue.md` era
`git pull && build && up -d && run --rm frontend`. Ninguno de esos cuatro pasos recarga nginx: `up -d`
solo recrea los contenedores cuya definición de compose cambió, y la de nginx casi nunca cambia. Así
que un `git pull` que toque `deploy/nginx/conf.d/` deja el archivo nuevo montado —es un *bind
mount*— y el proceso corriendo con el que cargó al arrancar. La tabla «¿Reconstruir, recrear o
reiniciar?» del README ya lo decía bien; lo que fallaba era el comando que uno copia.

Tres cosas lo hacen difícil de ver, y por eso queda escrito:

- **El síntoma es un 404, no un error.** Con la `location` cargada y el tracker apagado, `/gitea`
  responde 502 —ese es el diseño, el sitio no depende del tracker—. Sin la `location`, la petición cae
  al manejador estático del `server` y devuelve **404**, que se lee como «esa ruta no existe» y manda
  a buscar el problema en el compose del tracker, que es donde no está.
- **`nginx -T` no sirve para comprobarlo**: relee los archivos del disco, así que enseña la
  configuración nueva y da la impresión de que está cargada. Lo que sí distingue es el comportamiento
  —el `limit_req` de la `location` no dispara— y el log de error, que delataba el archivo estático que
  nginx estaba buscando.
- **Se arregla solo, tarde y sin avisar.** `40-recarga-periodica.sh` recarga cada 6 h, de modo que el
  cambio acaba aplicándose; entre medias, el sitio sirve una configuración que no es la del
  repositorio y nadie lo sabe.

Corregido añadiendo `docker compose exec nginx nginx -s reload` al final del comando en los dos
sitios, con la explicación al lado. Sin issue en el tracker: se encontró y se cerró en el acto.

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

### Actualización 28/08/2026 — una norma también nace de una URL, y esa URL puede ser un PDF (ADR-D8)

- **ADR-D8** extiende ADR-D7 a `normativa.Norma`: mismo bloque «Origen», mismos obligatorios
  relajados, mismo candado de una vez por registro, mismo «el editor revisa siempre». La IA rellena
  título, número, tipo, ámbito, fecha, resumen, contenido, palabras clave, estado de vigencia y la
  portada.
- **Se generalizó en vez de copiarse.** Cuatro piezas pasan a `core` —`RedaccionIAMixin`,
  `RedaccionIAAdminMixin`, `forms.RedaccionIAFormMixin` y `lectura_web`— y el endpoint de sondeo y
  su JS pasan a ser **uno solo** para los dos modelos. El argumento no es la elegancia: duplicar
  habría duplicado la **guarda anti-SSRF**, y una de las dos copias se habría quedado atrás. El
  refactor entró con la suite entera en verde (312 pruebas antes, 340 después).
- **La rama PDF es lo único realmente nuevo.** Media Perú publica sus normas como PDF y por la rama
  de HTML el extractor le habría pasado al modelo basura binaria decodificada. El archivo viaja en
  base64 dentro del mismo mensaje y lo parsea el `file-parser` de OpenRouter: **sigue siendo una
  sola petición**, que es la razón de no haber metido a Gemini a extraer el texto primero. Se
  detecta por los bytes `%PDF-` además de por la cabecera, porque hay servidores del Estado que lo
  sirven declarando `application/octet-stream`.
- **Dos campos que la IA no escribe, y no por olvido**: `analisis_predes` es la voz institucional
  que firma PREDES en el listado, y `url_oficial` presenta un enlace como publicación oficial — no
  puede acabar apuntando a la nota de prensa que el editor pegó arriba. `url_origen` es la
  procedencia y es otra cosa; el spec 01 lo dice ahora explícitamente.
- **Nada de repliegues inventados en la clasificación.** Un `tipo` o un `ambito` fuera del catálogo
  se dejan **vacíos** para que el editor elija. Replegar a una opción cualquiera pondría una
  clasificación falsa que nadie revisaría, porque el campo se vería lleno. Es lo contrario de lo que
  hace `Noticia.tipo`, y la diferencia es que ahí el default es una opción honesta y aquí no la hay.
- **Dos fallos silenciosos que este trabajo cerró antes de que ocurrieran**: un PDF escaneado
  devuelve la ficha en blanco sin quejarse —y se habría guardado vacía **con el candado cerrado**,
  lo único que no se puede reintentar—, y el base64 del adjunto habría entrado entero en
  `ia-AAAA-MM-DD.txt`, que es un archivo diario en modo añadir y sin rotación: un PDF de 5 MB son
  ~7 MB por llamada. `openrouter.registrar` lo elide y conserva el prompt, con su prueba.
- **Se corrigió una promesa caduca del spec 03**, que desde la fase de diseño afirmaba soporte de
  Gemini para `normativa.Norma` «vía su documento adjunto». Nunca se implementó:
  `generar_resumen_ia` asume los campos de `biblioteca.Documento` y no funcionaría sobre `Norma`.
  Ahora el spec dice qué hay y qué no.
- **Probado de extremo a extremo contra el API real**, las dos ramas: una norma de gob.pe quedó con
  título, número, tipo, ámbito, fecha, resumen, cinco palabras clave y portada descargada por
  $0.00016; el mismo documento en PDF, por $0.00009. El registro en disco muestra los dos
  intercambios y el adjunto elidido a «33 KB omitidos».
- Una lección de método: la prueba nueva que comprobaba el JS renderizando la ficha del admin
  **falló por el manifiesto de estáticos**, no por el código. Se reescribió para mirar
  `ModelAdmin.media`, que es lo que de verdad está en riesgo al mover un `class Media` a un mixin,
  y además no obliga a haber corrido `collectstatic` para pasar.

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
| [10-pipeline-cicd.md](10-pipeline-cicd.md) | Cómo llega el código al servidor: Bitbucket Pipelines, `desplegar.sh`, el sello de `/version.txt`, qué comprueba el CI y qué sigue siendo manual |

## Archivo histórico

`archive/` contiene los specs de la fase de prototipo (visión, UX, datos mock, arquitectura preliminar, roadmap). Siguen siendo válidos como referencia de **visión de producto** (`archive/00-vision.md`) y **UX/paleta/componentes** (`archive/02-navegacion-ux.md`); todo lo relativo a stack estático, mocks y hosting Vercel está superado por estos specs.
