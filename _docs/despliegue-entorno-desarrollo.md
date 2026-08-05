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
| Certificado | `--cert-name observatorio.somosiadigital.com` | `--cert-name observatorio.predes.org.pe` |
| Datos | `seed --solo-catalogos --demo` | `seed --capas --tiles`, con `data/layers/` completo |
| SMTP | sin configurar: los avisos del flujo editorial van al log | credenciales reales, o los correos no salen |
| `GEMINI_API_KEY` | vacío: el resumen automático de PDF queda deshabilitado con aviso | la llave real |
| Cuentas | `adminpredes` y `userobs` | las que PREDES decida |
| `ADMIN_URL` | `loginseguro/` | `loginseguro/`, salvo que PREDES quiera otro |

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
correr la suite y tienen que pasar las 56.

> Para correr Playwright en este servidor hizo falta instalar a mano las librerías de sistema de
> Chromium: sin ellas, las 62 pruebas fallan con `libatk-1.0.so.0: cannot open shared object file`,
> que se lee como si el sitio estuviera caído y no lo está. De ahí salió
> **`e2e/instalar-dependencias.sh`**, que ya lo hace por su cuenta —librerías, `npm install`,
> navegador y una comprobación de que arranca—. La provisión del servidor
> (`install-rocky-10.sh`) deja Docker y Node 22; este script cubre lo que falta encima.

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
ficha completa está en el tracker (`docker compose -f compose.tracking.yaml up -d` →
<http://localhost:3000/luishuacho/observatorio/issues>), que es el único sitio donde su estado se
mantiene al día; el ciclo está en `_specs/09-errores.md`.
