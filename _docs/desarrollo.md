# Desarrollo

Cómo levantar el Observatorio en una máquina local, sembrarlo con los datos reales y correr las
pruebas.

## Requisitos

- Docker y Docker Compose.
- Node 22 y npm, para el frontend en modo desarrollo.
- Los **archivos de datos**, que no se versionan (145 MB): `data/layers/data/*.xlsx` y
  `data/layers/*.geojson`. Los entrega PREDES; sin ellos el seed no tiene qué importar.
- Opcional: `uv` y Python 3.12+, si quieres correr `manage.py` desde el host.

## Primera vez

```bash
# 1. Configuración
cp backend/.env.example backend/.env     # secretos de Django (rellenar SECRET_KEY y contraseñas)
cp .env.example .env                     # variables de compose (dominios y VITE_*)
cp frontend/.env.example frontend/.env   # URLs que usa el frontend en dev

# 2. Levantar la base, la búsqueda, el backend y el worker
docker compose -f compose.yaml -f compose.dev.yml up -d --build

# 3. Sembrar: catálogos, datos reales de los Excel, contenido de demostración y tiles
docker compose -f compose.yaml -f compose.dev.yml exec backend \
  python manage.py seed --demo --capas --tiles

# 4. Copiar la llave de búsqueda que imprime el paso anterior a LOS DOS .env:
#    frontend/.env (para `npm run dev`) y el .env de la raíz (para el bundle compilado).
#    También la imprime `manage.py meili_setup`, y no cambia con el tiempo.

# 5. El frontend, en el host
cd frontend && npm install && npm run dev
```

Con eso: **http://localhost:5173** el sitio, **http://localhost:8000/api/docs/** el API, y el admin
en **http://localhost:8000/`$ADMIN_URL`** — el prefijo lo fija `ADMIN_URL` en `backend/.env`, y el
`.env.example` trae `loginseguro/`, así que copiándolo tal cual el admin está ahí y no en
`/admin/`. La tabla completa de accesos, con puertos y credenciales, está en el README.

El primer build de la imagen del backend tarda unos minutos porque **compila tippecanoe**. Es una
sola vez; las siguientes reutilizan la capa.

## El día a día

```bash
# Arriba / abajo
docker compose -f compose.yaml -f compose.dev.yml up -d
docker compose -f compose.yaml -f compose.dev.yml down

# Logs (los correos del flujo editorial salen aquí, en la consola)
docker compose -f compose.yaml -f compose.dev.yml logs -f backend worker

# Cualquier comando de Django
docker compose -f compose.yaml -f compose.dev.yml exec backend python manage.py <comando>
```

Un alias ahorra teclear:

```bash
alias dc='docker compose -f compose.yaml -f compose.dev.yml'
alias dm='docker compose -f compose.yaml -f compose.dev.yml exec backend python manage.py'
```

### Correr `manage.py` desde el host

Se puede, pero hay que redirigir dos nombres de servicio a `localhost`:

```bash
cd backend && uv sync --all-groups
POSTGRES_HOST=localhost MEILI_URL=http://localhost:7700 .venv/bin/python manage.py shell
```

Sin esos dos, Django busca los hosts `db` y `meilisearch`, que solo existen dentro de la red de
compose. Va más rápido para iterar, pero **el pipeline de tiles y el PDF no funcionan** desde el
host: necesitan tippecanoe, GDAL y Chromium, que viven en la imagen.

## El seed

```bash
dm seed                    # catálogos, territorio, peligros y frecuencia
dm seed --demo             # además, el contenido de demostración del prototipo
dm seed --capas            # adjunta los GeoJSON a las capas cartográficas
dm seed --tiles            # genera los PMTiles (necesita tippecanoe: usar el contenedor)
dm seed --solo-catalogos   # solo catálogos, grupos y textos; sin importar Excel
```

Y para el buscador:

```bash
dm meili_estado            # ¿está arriba y al día? sale con código ≠ 0 si no
dm meili_rebuild [indice]  # reconstruir; también hay un botón en el panel del admin
```

Es **idempotente** y **no pisa lo que hayas editado**: crea lo que falta y deja en paz lo que ya
existe. Se puede correr en cada despliegue sin miedo a devolverle a PREDES sus textos al valor de
fábrica.

Al terminar imprime los conteos. Si no coinciden con estos, algo se perdió por el camino:

```
  Provincias                        13
  Distritos                        112
  Centros poblados               8,968
    con alguna clasificación     3,238
    sin dato clasificado         5,730
  Clasificaciones de peligro    10,978
  Frecuencias de emergencia        644
    distritos con desglose          64
  Totales declarados (ADR-D1)      104
```

El seed también imprime **advertencias**, y son esperadas: 229 filas del Excel sin `NIVEL_PELI`,
2 sin `CODIGO`, **26 distritos que declaran subtotales sin desglosar**, **21 con fila pero sin
ningún dato** y Acomayo sin fila. No son errores del importador: son la calidad de los datos de
origen, y están anotadas en `_specs/00-alcance-decisiones.md` para devolvérselas al cliente.

## Probar el modo producción en local

El modo desarrollo no cubre cuatro cosas: que el bundle compilado se sirva bien, que las rutas
del router resuelvan por `try_files`, que los estáticos del admin estén donde nginx los busca, y
que los tiles salgan por rangos. Para eso hay un tercer override, sobre HTTP y un solo host:

```bash
# El .env de la raíz debe apuntar a http://localhost (ver .env.example)
docker compose -f compose.yaml -f compose.local.yml up -d --build
docker compose -f compose.yaml -f compose.local.yml run --rm frontend   # publica dist/
docker compose -f compose.yaml -f compose.local.yml exec backend python manage.py collectstatic --noinput
```

→ **http://localhost/** el sitio compilado, el admin bajo su `ADMIN_URL`, **/api/docs/** el API.
Todo por el puerto 80: en este modo no queda ningún otro puerto publicado.

Ojo con `VITE_*`: **Vite las hornea en el bundle durante el build**, no las lee en runtime. Si
cambias una, hay que reconstruir la imagen del frontend (`--build`), no basta con reiniciar.

Y con dos cosas más de este modo: es fiel solo con `DEBUG=False` en `backend/.env` (en desarrollo,
`compose.dev.yml` fuerza `True`; aquí no se fuerza nada), y con `DEBUG=False` **`ALLOWED_HOSTS` tiene
que contener el host que uses** — si abres el sitio desde otra máquina por IP, Django responde 400
hasta que la añadas.

## Pruebas

```bash
dc exec backend pytest                 # 144 pruebas, ~30 s (sin las lentas)
dc exec backend pytest -m lento        # 5 más: los Excel completos y el PDF con mapa
cd frontend && npm run lint            # tsc --noEmit
cd frontend && npm run build           # el build es parte de la verificación
./e2e/instalar-dependencias.sh         # una sola vez, en la raíz
npx playwright test                    # 56 E2E en escritorio y móvil
```

### Preparar la máquina para las E2E

`e2e/instalar-dependencias.sh` hace **tres** cosas, y hasta el 04/08/2026 aquí solo se documentaban
dos: las librerías de sistema de Chromium, `npm install` y la descarga del navegador. La que
faltaba es la que rompe.

El detalle que lo explica: **Playwright no soporta oficialmente la familia RHEL**. En Debian y
Ubuntu, `playwright install --with-deps` instala esos paquetes por su cuenta; en Rocky, Fedora o
RHEL descarga el binario compilado para Ubuntu —lo avisa con un `BEWARE: your OS is not officially
supported`— y **no instala ninguna dependencia**, porque solo sabe de `apt`. El resultado es que
las 62 pruebas fallan con `browserType.launch: Target page, context or browser has been closed`,
que se lee como si el sitio estuviera caído cuando lo que falta es una `.so`.

El script detecta la familia de la distribución, delega en Playwright si es Debian/Ubuntu, instala
la lista con `dnf` si es RHEL, y **termina arrancando el navegador** para que el fallo salga en dos
segundos y no tras seis minutos de suite. Es idempotente. Se ejecuta **como tu usuario, no con
sudo**: Node viene de nvm (que es por usuario) y los navegadores van a `~/.cache/ms-playwright`, así
que con `sudo` acabarían en `/root` y las pruebas seguirían fallando igual. También acepta
`--dry-run` y `--help`.

No instala Docker ni Node: eso corresponde a la provisión del servidor, y el script se limita a
comprobarlo.

`pytest` vive **dentro del contenedor**, para correr con las mismas versiones de GDAL, tippecanoe
y WeasyPrint que producción. Se instala porque `compose.dev.yml` construye la imagen con
`GRUPOS_UV=--group dev`; si cambias esa opción hace falta
`dc up -d --renew-anon-volumes backend`, porque `/app/.venv` es un volumen anónimo que sobrevive
a la reconstrucción y se queda con el venv viejo.

### La corrida que de verdad importa

```bash
docker compose -f compose.yaml -f compose.local.yml up -d --build
docker compose -f compose.yaml -f compose.local.yml run --rm frontend
E2E_URL=http://localhost npx playwright test
```

Contra el bundle compilado servido por nginx. **Es la que encuentra los fallos de integración**:
en desarrollo el navegador ataca a Meilisearch directamente, así que un proxy `/search/` mal
configurado —lo que pasaba— es invisible hasta que el sitio se sirve como en producción.

El plan completo, con los casos obligatorios, de dónde sale cada uno y lo que la suite ya
encontró, está en `_specs/08-plan-pruebas.md`.

## El tracker de errores

Lo que se sabe roto y sigue sin arreglar vive en un **Gitea**, no en un archivo del repositorio. Corre
en el servidor de desarrollo y escucha solo en `127.0.0.1:3000`: no forma parte de lo que se entrega
a PREDES (ADR-A15). Se llega a él abriendo el túnel y luego el navegador:

```bash
ssh -L 3000:localhost:3000 usuario@observatorio.somosiadigital.com
```

→ <http://localhost:3000/luishuacho/observatorio/issues> · usuario y contraseña en
`deploy/gitea/admin.env`.

Para levantarlo —la primera vez, o en una máquina nueva— son dos comandos desde la raíz:

```bash
docker compose -f compose.tracking.yaml up -d     # levantar
./deploy/gitea/inicializar.sh                     # idempotente; la primera vez crea todo
```

Se levanta **solo**, nunca junto a `compose.yaml`. Es un proyecto Compose aparte
(`observatorio-tracking`) a propósito: como override, un `down --remove-orphans` sin acordarse del
tercer `-f` se llevaría el tracker por delante, y `vigilar-contenedores.sh` —que filtra contenedores
por proyecto— lo metería en su bucle de reinicio automático. La cabecera de `compose.tracking.yaml`
lo explica entero.

`inicializar.sh` crea, si no existen, el usuario administrador, un token, el repositorio y las
etiquetas de severidad y área. Correrlo dos veces seguidas no cambia nada, y si el token guardado ha
dejado de valer —por ejemplo tras un `down -v`— lo detecta y genera otro.

Deja dos archivos, los dos ignorados por git:

| Archivo | Qué lleva |
|---|---|
| `deploy/gitea/admin.env` | usuario y contraseña del admin, para entrar por la web |
| `deploy/gitea/token.env` | `GITEA_HOST` y `GITEA_ACCESS_TOKEN`, y nada más |

Van separados porque `token.env` se le pasa **entero** al contenedor del servidor MCP con
`--env-file`, y la contraseña del admin no tiene por qué viajar ahí dentro. Eso es también lo que
permite versionar `.mcp.json`: el token no está escrito en él.

El token lleva solo `write:repository,write:issue,read:user`. El arranque no lo usa —habla con el
API por autenticación básica— justamente para no tener que ampliarlo: crear un repositorio por API
exige `write:user`, un permiso que el MCP no necesita para nada.

**Dos cosas que se ven raras y son deliberadas** en `.mcp.json`:

- El contenedor del MCP corre con `--network host` y `GITEA_HOST=http://localhost:3000`, no en la
  red de compose. Gitea construye los `html_url` de su API **a partir de la cabecera `Host` de la
  petición**, así que entrando por `http://gitea:3000` devolvería enlaces que el navegador no puede
  abrir. El puerto solo escucha en loopback, de modo que `--network host` no expone nada nuevo.
- El binario se nombra explícitamente (`/app/gitea-mcp -t stdio`) porque la imagen **no declara
  `ENTRYPOINT`**: sin él, docker toma `-t stdio` como el comando y el contenedor no arranca.

Si Claude Code dice que el servidor `gitea` falla, casi siempre es que el tracker no está en pie.
Un `.mcp.json` nuevo o modificado **solo se carga al reiniciar la sesión**.

### Pasarle un issue a Claude

Se mira la lista en la web —ahí están las fichas completas, las etiquetas y el historial— y se lanza
el comando con los números:

```
/issue 6            un issue
/issue 6 3 1        varios; sale un solo plan que los cubre todos
/issue              sin argumentos: lista los abiertos y se detiene, para elegir
```

El comando está en `.claude/commands/issue.md` y hace el flujo del proyecto: lee la ficha, lee el
código, **plantea un plan y espera aprobación**, y solo entonces escribe la prueba que falla, la hace
pasar y comenta en el issue qué hizo y qué prueba lo demuestra. **No commitea y no cierra el issue**
a propósito: una corrección que nadie ha visto no se da por buena.

No hay cola, ni etiqueta «para Claude», ni asignación. Por dos razones. La primera es que **el MCP no
lee asignados**: `list_issues` filtra por etiqueta, hito, estado y fechas, pero no por asignado, y
`issue_read` ni siquiera devuelve el campo —puede escribirlos, no leerlos; es una asimetría de
`gitea-mcp` 1.6.0—. La segunda es que una cola es estado que hay que mantener sincronizado a mano, y
este tracker existe justamente porque el estado mantenido a mano se desincroniza.

Cerrar sigue siendo cosa tuya, y son **dos** gestos: cerrar el issue en el tracker y escribir la
entrada `### Actualización DD/MM/AAAA` en la bitácora de `_specs/README.md`.

### El tracker vive en el servidor de desarrollo

**Hay un solo tracker**, en `observatorio.somosiadigital.com`, y se alcanza por túnel SSH. Dos
trackers —uno local y otro remoto— serían dos listas de pendientes que divergen, que es exactamente
el problema del que se venía.

Que corra ahí no lo expone: `compose.tracking.yaml` publica en `127.0.0.1:3000` y eso no cambia. El
túnel trae ese puerto a tu máquina:

```bash
ssh -L 3000:localhost:3000 usuario@observatorio.somosiadigital.com
```

Y con el túnel abierto, <http://localhost:3000> en el navegador funciona igual que cuando corría en
local. Ni certificado, ni vhost de nginx, ni un puerto más abierto a internet. Es también la razón de
que el `ROOT_URL` del contenedor siga siendo `http://localhost:3000/`: por el túnel, esa **es** la
URL correcta.

Ojo con una cosa: no es la producción de PREDES, es el servidor de desarrollo (Rocky Linux, 2 vCPU,
4 GB). Gitea consume poco, pero **no lances una reconstrucción de la imagen del backend y Claude Code
a la vez**: tippecanoe se compila desde el código fuente y esa máquina ya necesitó 2 GB de swap para
que le cupiera.

#### Mudar el tracker de una máquina a otra

Los issues **no están en el repositorio**: viven en el volumen `observatorio-tracking_gitea_data`,
con su base sqlite y los adjuntos. Se mueven copiando el volumen entero, que es la única forma de no
perder los adjuntos por el camino —un export por el API se los deja—. Pesa poco: ~1,3 MB con ocho
issues.

En el origen, **con el tracker parado** (sqlite en caliente no se copia entero de forma fiable):

```bash
docker compose -f compose.tracking.yaml stop
docker run --rm -v observatorio-tracking_gitea_data:/data:ro -v "$PWD":/salida \
    alpine tar czf /salida/gitea-data.tgz -C /data .
scp gitea-data.tgz deploy/gitea/*.env usuario@servidor:~/observatorio/
```

En el destino, con el repositorio ya clonado:

```bash
cd ~/observatorio
docker compose -f compose.tracking.yaml create        # crea el volumen, sin arrancar
docker run --rm -v observatorio-tracking_gitea_data:/data -v "$PWD":/entrada \
    alpine tar xzf /entrada/gitea-data.tgz -C /data
mv gitea-data.tgz /tmp && mv *.env deploy/gitea/
docker compose -f compose.tracking.yaml up -d
```

Los dos `.env` viajan aparte porque git los ignora. Si no los copias, `inicializar.sh` se planta con
un mensaje explícito: encuentra el usuario ya creado en la base y no tiene su contraseña para seguir.
Con ellos, el script es un no-op — está para eso.

#### Claude Code en el servidor

Hace falta el CLI instalado y autenticado allí; la autenticación es interactiva y la haces tú.

```bash
curl -fsSL https://claude.ai/install.sh | bash
cd ~/observatorio && claude          # la primera vez pide iniciar sesión
```

Lo demás ya viaja en el repositorio: `.mcp.json`, `.claude/commands/issue.md` y `.claude/settings.json`
—que lleva `enabledMcpjsonServers` justamente para que el servidor de Gitea se habilite solo tras el
`git pull`, sin tener que aprobarlo a mano en cada máquina—.

El ciclo —cuándo nace un error, qué significa cada etiqueta, cuándo se puede cerrar y qué se escribe
al cerrarlo— está en `_specs/09-errores.md`.

## Trampas que ya nos costaron tiempo

- **`useJsonData` ya no existe.** Todo pasa por `lib/api.ts`, que es el único punto de
  integración. Si una página necesita datos nuevos, se le añade un endpoint, no un `fetch` suelto.
- **El slug del peligro lleva guion bajo** (`lluvias_intensas`). Es la clave de las propiedades
  `nivel_<slug>` de los tiles: con guion medio el visor deja de pintar y nada más falla.
- **`nginx` resuelve los nombres del `upstream` una sola vez.** Por eso la configuración usa un
  `resolver` y una variable en `proxy_pass`: sin eso, cada despliegue del backend le cambia la IP
  y nginx devuelve 502 hasta que alguien lo reinicia.
- **Las dos unidades de la distribución difieren en 3.4×.** «Centros poblados por su nivel
  máximo» (3,238) y «clasificaciones» (10,978) no son intercambiables. El API las devuelve
  rotuladas las dos; usar la que no toca fue un error real del prototipo.
- **Los tiles necesitan HTTP Range.** En desarrollo los sirve una vista propia porque ni
  `static.serve` ni `FileResponse` lo implementan en Django 5.2: sin rangos el visor «funciona»
  pero descarga 3 MB por tesela y va lentísimo solo en local.
- **Una variable en `proxy_pass` desactiva la sustitución del prefijo de la `location`.** Es la
  contrapartida del truco del resolver: `proxy_pass http://$destino/` no reescribe `/search/x → /x`,
  manda todo a `/`. Por eso ese bloque quita el prefijo con `rewrite`. Y ojo con la comprobación
  fácil: `GET /search/health` devolvía 200 **porque la raíz de Meilisearch también devuelve 200**.
- **El HTML rico se sanea en `save()` del modelo** (`HtmlRicoMixin.campos_html`), no en el admin.
  Si añades un campo de CKEditor, declárarlo ahí: `campos_rich` del admin solo elige el widget.
- **Lo que cuelgue del prefijo del admin va antes de `admin.site.urls`.** El `AdminSite` de Django
  termina con un `catch_all_view` que se queda con todo su prefijo y responde 404: una ruta
  declarada después nunca se alcanza. Pasó con la subida de imágenes del editor, que daba 404 sin
  decirlo. Hay prueba de regresión en `tests/test_urls_admin.py`.
- **`numberOfDocuments` de las estadísticas de Meilisearch está cacheado.** Tras vaciar un índice
  sigue devolviendo el conteo anterior mientras la búsqueda ya no encuentra nada, así que no sirve
  para comprobar si el índice está al día: se usa `get_documents({"limit": 0}).total`. Lo comprueba
  `manage.py meili_estado`.
- **La llave de búsqueda va dentro del bundle**, no se lee en runtime, y vive en **dos** `.env`:
  `frontend/.env` para `npm run dev` y el de la raíz para el sitio compilado. Actualizar solo el
  primero deja el bundle con una llave que Meilisearch rechaza, y entonces se degradan tres cosas
  —búsqueda global, conteos de las facetas de `/medidas` y autocompletado de lugares— de las que
  **solo la primera avisa en pantalla**. Pasó. La llave ya no cambia por sí sola (uid fijo +
  `MEILI_MASTER_KEY`), así que esto solo ocurre si se cambia la master key.
- **El menú vive en tres sitios.** Ocultar o añadir una entrada exige tocar la semilla
  (`apps/sitio/semillas/sitio.yaml`), **la base ya sembrada** —el seed no pisa lo que existe, así que
  un cambio de visibilidad necesita migración de datos, como `sitio.0002`— y el menú de respaldo de
  `frontend/src/lib/sitio.tsx`, que es el que se pinta mientras carga `/api/sitio/` y cuando el API
  no responde. Cambiar solo uno «funciona» en la máquina de quien lo cambió y no en la siguiente.

## Estructura

```
backend/          Django. `apps/` una carpeta por dominio; `config/` settings y urls
frontend/         Vite + React + TS. `src/lib/` capa de datos; `src/routes/` una por página
prototype/        Prototipo aprobado. CONGELADO: es la referencia visual, no se toca
_specs/           Especificaciones y ADR. Se leen antes de cambiar algo de fondo
_docs/            Esta documentación
deploy/nginx/     `conf.d/` producción · `templates/` fragmentos con dominio · `local/` HTTP
data/             Excel y GeoJSON canónicos. NO se versionan
```
