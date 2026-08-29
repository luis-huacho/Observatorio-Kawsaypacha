# Entorno de desarrollo en servidor propio

Bitácora del despliegue del Observatorio en **`observatorio.somosiadigital.com`**, un servidor
propio con dominio público, hecho el **04/08/2026**. No es la producción de PREDES: existe para
probar la ruta de producción entera —dominios, HTTPS, nginx, la SPA compilada, el buscador— antes
de ejecutarla sobre `predes.org.pe`.

El procedimiento general está en [`despliegue.md`](./despliegue.md) y **no se repite aquí**. Este
documento registra qué se hizo en este servidor, qué quedó fuera, y **qué cambia para el pase de
PREDES**, que es la única pregunta que importa el día que toque hacerlo.

## Lo que se desplegó

| | |
|---|---|
| Fecha | 04/08/2026 |
| Servidor | Rocky Linux 10, 2 vCPU, 4 GB RAM, 40 GB de disco (`46.62.239.44`) |
| SPA | `https://observatorio.somosiadigital.com` |
| API, admin, media, tiles, búsqueda | `https://obs.somosiadigital.com` |
| Admin | `https://obs.somosiadigital.com/loginseguro/` |
| Certificado | Let's Encrypt, **uno solo** con los dos dominios como SAN, lineage `observatorio.somosiadigital.com`, vence el 02/11/2026 |
| Vía | Docker Compose (`compose.yaml` sin overrides) |

**Se añadieron 2 GB de swap.** El servidor venía sin nada de swap y la imagen del backend compila
tippecanoe desde el código fuente; con 4 GB justos, no es un lujo.

## Cuentas

Dos, y las contraseñas **no están aquí**: viven en `backend/.env`, que no se versiona, y se
entregaron aparte.

| Usuario | Correo | Rol |
|---|---|---|
| `adminpredes` | `l.huacho@gmail.com` | Superusuario. Lo crea `manage.py seed` desde `DJANGO_SUPERUSER_*` |
| `userobs` | `sistemas@predes.org.pe` | Staff + grupo **Administrador**, que es el rol máximo del proyecto (spec 03): publica, gestiona datos y capas, y además toca usuarios y configuración del sitio |

`userobs` no lo crea el seed, que solo sabe de un superusuario. Se creó así:

```bash
docker compose exec backend python manage.py shell -c "
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
U = get_user_model()
u, creado = U.objects.get_or_create(
    username='userobs', defaults={'email': 'sistemas@predes.org.pe'})
u.email = 'sistemas@predes.org.pe'
u.is_staff = True
u.set_password('<la contraseña>')
u.save()
u.groups.add(Group.objects.get(name='Administrador'))
print('creado' if creado else 'actualizado', u.username)
"
```

## Datos: lo que NO tiene este entorno

**Los Excel y GeoJSON canónicos no estaban en el servidor**, así que se sembró con
`seed --solo-catalogos --demo`: catálogos de peligros y eventos, configuración del sitio, menú,
capas (sin archivo), categorías, grupos, superusuario y el contenido de demostración.

Queda fuera, y es mucho:

- Los **8,968 centros poblados** y las **10,978 clasificaciones** de peligro.
- Las **frecuencias de emergencia**.
- Los **archivos de las capas** cartográficas y, por tanto, **todos los PMTiles**.

Consecuencia visible: **el visor de `/peligros` sale vacío**, la ayuda memoria en PDF no tiene de
qué hablar, y las pruebas E2E que cuentan centros poblados fallan. No es un fallo del despliegue;
es la ausencia del dato.

Para completarlo, cuando lleguen los archivos:

```bash
# data/layers/data/Base_Nivel Peligro_CCPP_Cusco.xlsx
# data/layers/data/Base_Frecuencia_Peligro_Cusco.xlsx
# data/layers/{rios,lagos-y-lagunas,glaciares}.geojson
docker compose exec backend python manage.py seed --capas --tiles
```

## Qué cambia para el pase de PREDES

Esta es la tabla que hay que leer el 13/08. **No hay que editar ningún archivo del repositorio**:
todo lo de abajo son variables de entorno y un comando.

| Qué | En este entorno | En producción PREDES |
|---|---|---|
| `SITE_DOMAIN` (`.env` raíz) | `observatorio.somosiadigital.com` | `observatorio.predes.org.pe` |
| `API_DOMAIN` (`.env` raíz) | `obs.somosiadigital.com` | `obs.predes.org.pe` |
| `VITE_API_URL` / `_SEARCH_URL` / `_TILES_URL` | contra `obs.somosiadigital.com` | contra `obs.predes.org.pe` |
| `ALLOWED_HOSTS`, `SITE_URL`, `BACKEND_URL`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` (`backend/.env`) | dominios de somosiadigital | dominios de predes |
| `SITIO_INDEXABLE` (`backend/.env`) | **`0` a partir de ese día** | `1` |
| Certificado | `--cert-name observatorio.somosiadigital.com` | `--cert-name observatorio.predes.org.pe` |
| Datos | `seed --solo-catalogos --demo` | `seed --capas --tiles`, con `data/layers/` completo |
| SMTP | sin configurar: los avisos del flujo editorial van al log | credenciales reales, o los correos no salen |
| `GEMINI_API_KEY` | vacío: el resumen automático de PDF queda deshabilitado con aviso | la llave real |
| `OPENROUTER_API_KEY` | vacío: las funciones de IA de propósito general quedan deshabilitadas | la llave real |
| Cuentas | `adminpredes` y `userobs` | las que PREDES decida |
| `ADMIN_URL` | `loginseguro/` | `loginseguro/`, salvo que PREDES quiera otro |
| Despliegue automático | Pipelines entra por SSH a este servidor | mismo pipeline, otro `DESPLIEGUE_HOST` y otra clave |

**Lo que NO cambia**: `deploy/nginx/`, `compose.yaml` y el resto del repositorio. Los dominios ya no
están escritos en ninguna parte del código — nginx los toma de `SITE_DOMAIN` y `API_DOMAIN` al
arrancar, con `envsubst`. Si algún día vuelve a hacer falta un `sed` sobre un `.conf` para cambiar
de dominio, es que se rompió esa propiedad.

> Y si se cambia `ADMIN_URL`, hay que cambiar **también** el `location` de
> `deploy/nginx/conf.d/observatorio.conf`. Son los dos únicos sitios donde vive el prefijo del
> admin, y tienen que coincidir.

## Comprobaciones, con lo que dieron

| Comprobación | Resultado |
|---|---|
| SPA, `GET /` | 200 |
| `GET /api/sitio/` | JSON de configuración |
| Admin, `GET /loginseguro/login/` | 200 |
| `GET /gestion/` (la ruta vieja) | 404, como debe |
| `http://` → `https://` | 301 |
| HSTS, `nosniff`, `Referrer-Policy` en la portada, en `/assets/*.js` y en `/static/` | presentes |
| `POST /search/multi-search` sin llave | **401** (un 405 sería el proxy mal configurado) |
| `POST /search/multi-search` con la llave del bundle | **200** |
| `manage.py meili_estado` | todos los índices al día |
| Señal → cola → worker → índice | verificado de punta a punta con un `save()` |
| `certbot renew --webroot --dry-run` | «all simulated renewals succeeded» |
| Certificado servido | SAN con los dos dominios, vence el 02/11/2026 |
| `docker compose exec backup /backup.sh` | volcado creado, con rotación diaria/semanal/mensual |
| Agregación de métricas | corre sin error |
| **Playwright E2E** | **39 pasan, 17 fallan, 6 se saltan** |

Los 17 fallos son **todos** por la ausencia de datos, y ninguno del despliegue: las siete pruebas
de `peligros.spec.ts` en sus dos perfiles, la cifra de la portada (`home.spec.ts:14` exige
`total_ccpp > 1000`) y el buscador de lugares del visor. Cuando entren los Excel, se vuelve a
correr la suite y tiene que pasar entera.

> Para correr Playwright en este servidor hizo falta instalar a mano las librerías de sistema de
> Chromium: sin ellas, la suite entera falla con `libatk-1.0.so.0: cannot open shared object file`,
> que se lee como si el sitio estuviera caído y no lo está. De ahí salió
> **`e2e/instalar-dependencias.sh`**, que ya lo hace por su cuenta —librerías, `npm install`,
> navegador y una comprobación de que arranca—. La provisión del servidor —un `install-rocky-10.sh`
> que **no vive en este repositorio**, porque es de la máquina y no del proyecto— deja Docker y
> Node 22; este script cubre lo que falta encima.

## Tareas de cron instaladas

En el crontab de `appdevuser`, con sus logs en `/home/appdevuser/`:

| Cuándo | Qué |
|---|---|
| 03:15 diario | Agregación de métricas y purga de eventos de más de 90 días. Sin ella el panel del admin se queda en blanco |
| 04:30 diario | `meili_estado`, que sale con código ≠ 0 si el buscador está caído o desfasado |
| 02:30 domingos | `tar` del volumen `media` a `/home/appdevuser/respaldos` |
| 05:00 lunes | Purga del caché de BuildKit y de las imágenes sin tag |
| **cada 2 min** | `deploy/vigilar-contenedores.sh`: reinicia backend o nginx si el healthcheck los marca enfermos, con tope de 3/hora |
| 04:35 diario | `cola_estado`, que avisa si el worker dejó de avanzar. **No reinicia**: una importación interrumpida hay que repetirla |

Los registros y el contador de reinicios viven en **`~/observatorio-registros/`**, no en
`/var/log`, para que respaldar el servidor sean dos carpetas: esa y `~/respaldos/`.
`vigilancia.log` está vacío mientras todo va bien.

Y una pieza que **no** está en este servidor a propósito: `deploy/comprobar-sitio.sh`, la
comprobación externa. Solo necesita `curl`, y hay que colgarla del cron de **otra máquina** — si el
servidor entero cae, el vigilante local cae con él.

Además, `/etc/docker/daemon.json` fija un techo de 4 GB al caché de construcción
(`builder.gc.defaultKeepStorage`). No existía —el servidor estaba con todo por defecto— y **no se
versiona**, así que hay que crearlo también en el servidor de PREDES; está documentado en
[`despliegue.md`](./despliegue.md).

El volcado de la base no va por cron: lo hace el servicio `backup` de compose, diario, con
retención de 7 diarios, 4 semanales y 6 mensuales.

**Lo que falta para que esto sea un respaldo de verdad**: sacar `/home/appdevuser/respaldos` fuera
del servidor. Un respaldo que vive en el mismo disco que la base no es un respaldo.

## Seis defectos que este despliegue destapó

El proyecto nunca se había desplegado contra un dominio real, así que este pase fue la primera vez
que la documentación de despliegue se ejecutó de verdad en vez de leerse. Encontró seis cosas, las
seis corregidas; el detalle está en la bitácora de `_specs/README.md`.

1. **El certificado que se emitía no era el que nginx buscaba.** El comando documentado creaba una
   sola lineage y la configuración pedía dos. nginx no habría arrancado.
2. **Lo mismo en la guía sin Docker**, en otras tres líneas.
3. **Dos comandos del runbook no hacían nada**: `certbot renew` sin `--entrypoint certbot` cae en el
   bucle y se ignora, y sin `--webroot -w` choca con nginx en el puerto 80.
4. **Nada recargaba nginx tras renovar**, aunque `compose.yaml` y el spec 07 lo daban por hecho.
5. **La sincronización de la búsqueda no había funcionado nunca**: las señales se conectaban con
   referencia débil y el recolector se las llevaba, así que lo publicado en el admin no aparecía al
   buscarlo hasta que alguien reindexara a mano. Es el más grave de los seis y el más silencioso.
6. **El dominio de la SPA no enviaba ninguna cabecera de seguridad**, ni HSTS ni `nosniff`.

Tres quedaron abiertos y **no corregidos** por estar fuera del encargo: E-006, E-007 y E-008. Su
ficha completa está en el tracker, que es el único sitio donde su estado se mantiene al día; el ciclo
está en `_specs/09-errores.md`.

## Despliegue automático desde Bitbucket

Desde el **27/08/2026**, cada push a `master` en Bitbucket redespliega este entorno. El pipeline
(`bitbucket-pipelines.yml`) comprueba los tipos del frontend y, si pasan, entra por SSH y lanza
`deploy/desplegar.sh`. **El build sigue ocurriendo aquí**, no en la nube de Atlassian: la imagen del
backend compila tippecanoe desde el código fuente, así que construirla sin caché de capas costaría
más de lo que ahorra y obligaría a montar un registry. El pipeline gasta ~1 min por despliegue.

Se montó porque ese mismo día el sitio estuvo sirviendo el bundle del 11/08 sin que nada fallara —el
detalle, y por qué el script verifica el resultado en vez de limitarse a ejecutar los pasos, está en
[`despliegue.md`](./despliegue.md#despliegue-automatico)—.

**Este servidor deja de usarse como copia de trabajo.** El script aborta si encuentra cambios locales
sin commitear, así que lo que se edite aquí bloquea el siguiente despliegue en vez de perderse.

### Lo que hubo que configurar a mano

No es versionable, y es lo que habría que repetir para PREDES:

1. **Bitbucket** → *Repository settings → SSH keys*: generar el par y registrar el known host del
   servidor. La clave pública es la que se copia al paso siguiente.
2. **Aquí**, en `~/.ssh/authorized_keys`, la clave **restringida con `command=`**:

   ```
   command="/home/appdevuser/observatorio-kallpachakuy/deploy/desplegar.sh",no-port-forwarding,no-agent-forwarding,no-X11-forwarding,no-pty ssh-ed25519 AAAA… bitbucket-pipelines
   ```

   Esto es lo que hace aceptable la superficie nueva que abre el pipeline: una clave SSH viva en la
   nube de Atlassian con acceso a la máquina. Con `command=`, esa clave **no da shell** — lo único
   que puede hacer es redesplegar `master`. El comando que manda el pipeline es solo un disparador;
   el que se ejecuta lo fija este archivo. Sin `command=`, quien tuviera la clave tendría el
   servidor, y con él la base, los certificados y el `.env`.
3. **Repository variables**: `DESPLIEGUE_HOST` = `46.62.239.44` y `DESPLIEGUE_USUARIO` = `appdevuser`.

### Comprobar qué está desplegado

```bash
curl -s https://observatorio.somosiadigital.com/version.txt
```

Devuelve el SHA que el sitio está sirviendo de verdad. Los despliegues quedan en
`~/observatorio-registros/despliegue.log`, junto a `vigilancia.log` y `metricas.log`.

## Además de la plataforma, este servidor lleva el tracker

Desde el **05/08/2026** aquí corre también el **tracker de errores** (Gitea, `compose.tracking.yaml`)
y el CLI de Claude Code. No forma parte del entregable ni toca a la plataforma: es herramienta de
trabajo, y está aquí y no en el portátil para que **haya un solo tracker** —dos listas de pendientes
divergen—.

| | |
|---|---|
| Proyecto Compose | `observatorio-tracking`, **independiente** del de la plataforma |
| Modo | **Publicado** desde el 05/08/2026 (`compose.tracking-publicado.yml`) |
| Acceso | <https://obs.somosiadigital.com/gitea/>, sin túnel |
| Vía de rescate | `ssh -L 3000:localhost:3000 …`; el puerto sigue publicado en loopback y es por donde entran `inicializar.sh` y el MCP |
| `RED_APP` en esta máquina | `observatorio-kallpachakuy_default` — el directorio del clon es `observatorio-kallpachakuy`, no `observatorio` |
| Consumo | 2,4 MB de datos; la imagen, unos 250 MB |

Publicarlo no exigió tocar nginx: la `location` de `/gitea` ya está en `conf.d/observatorio.conf`,
dentro del bloque del dominio del API, y es una subruta de un dominio que ya tenía DNS y certificado.
Sí exigió **recargar nginx**, porque el bloque llegó en un `git pull` posterior al arranque del
contenedor — ver la bitácora de `_specs/README.md`.

Cinco cosas que conviene tener presentes en **esta** máquina:

- **Su login está en internet**, con el `limit_req` de 30/min, el registro deshabilitado,
  `REQUIRE_SIGNIN_VIEW` y la versión oculta. La contraseña del admin es la del patrón que genera
  `inicializar.sh` y el `allow`/`deny` por IP sigue comentado: es un servidor de QA temporal y el
  endurecimiento se decide si esto se replica en el de PREDES.
- **El tracker de aquí está vacío.** El volumen `observatorio-tracking_gitea_data` nació el
  05/08/2026 con el usuario, el repositorio y las etiquetas, pero **sin issues**: los que se
  anotaron durante el despliegue —E-006, E-007 y E-008— siguen en el tracker de la máquina donde se
  abrieron. Se traen copiando el volumen entero, con el procedimiento de
  [`desarrollo.md`](./desarrollo.md); ojo, eso trae también su `admin.env`, así que las credenciales
  pasan a ser las de la máquina de origen.
- **No está en los backups.** El servicio `backup` de `compose.yaml` solo vuelca PostgreSQL; el
  volumen `observatorio-tracking_gitea_data` es sqlite y queda fuera. Se copia con el mismo
  procedimiento que documenta `desarrollo.md` para mudarlo de máquina.
- **No lo vigila nada.** `vigilar-contenedores.sh` filtra por proyecto Compose, así que el tracker
  queda fuera de su bucle de reinicio. Es deliberado: que se caiga el tracker no es una incidencia.
- **2 vCPU y 4 GB no dan para todo a la vez.** Reconstruir la imagen del backend compila tippecanoe
  desde el código fuente y ya obligó a añadir 2 GB de swap; no lances eso y Claude Code al mismo
  tiempo.

Cómo se levanta, cómo se muda el volumen y cómo se instala el CLI está en
[`desarrollo.md`](./desarrollo.md), en la sección del tracker.
