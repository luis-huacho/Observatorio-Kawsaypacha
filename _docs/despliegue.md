# Despliegue y operación

Puesta en producción del Observatorio Kallpachakuy en un servidor propio, y qué hacer cuando algo
va mal. Requisito 8 del TDR: servidor propio, dominio, HTTPS y backups automáticos.

## Lo que hace falta antes de empezar

| Cosa | Quién la entrega | Sin ella |
|---|---|---|
| VPS con Docker y acceso SSH | PREDES / su proveedor | No hay dónde desplegar |
| DNS de los dos dominios (`SITE_DOMAIN` y `API_DOMAIN`) apuntando al VPS | PREDES | certbot no puede emitir certificados |
| Credenciales SMTP | PREDES | Los avisos del flujo editorial no salen (van a los logs) |
| API key de Gemini | PREDES o el desarrollador | El resumen automático de PDF queda deshabilitado, con aviso en el admin |
| Los Excel y GeoJSON de `data/layers/` | PREDES | El seed no tiene qué importar |

Los tres últimos **no bloquean el despliegue**: la plataforma arranca y funciona sin ellos, con
las funciones correspondientes desactivadas y avisando de por qué. Sin los Excel y GeoJSON hay que
sembrar con `seed --solo-catalogos`, y el visor de peligros sale vacío hasta que lleguen.

> Este procedimiento se ejecutó por primera vez contra un servidor y un dominio reales el
> **04/08/2026**; lo que se hizo y lo que cambia para el pase de PREDES está en
> [`despliegue-entorno-desarrollo.md`](./despliegue-entorno-desarrollo.md).

## Dimensionado

Medido con los datos reales:

| Recurso | Consumo |
|---|---|
| Imagen del backend | 2.2 GB (incluye tippecanoe, GDAL, WeasyPrint y Chromium) |
| Base de datos con todo sembrado | ~90 MB; el volcado comprimido, 2.6 MB |
| Tiles (`media/tiles/`) | 5.2 MB en total |
| Archivos fuente de las capas (`media/capas/`) | 140 MB |
| Índices de Meilisearch | ~30 MB |

Un VPS de **2 vCPU y 4 GB de RAM** con 40 GB de disco va sobrado. El pico de memoria es la
generación de tiles de las capas nacionales, no el tráfico.

## Puesta en marcha

**Ningún dominio está escrito en el repositorio.** Los `server_name`, las rutas del certificado y
el origen de CORS los genera nginx al arrancar, con `envsubst`, a partir de `SITE_DOMAIN` y
`API_DOMAIN` del `.env` de la raíz. Desplegar en otro dominio es cambiar esas dos variables y
recrear el contenedor; no se edita ni un `.conf`.

```bash
git clone <repo> observatorio && cd observatorio

# 1. Secretos y configuración
cp backend/.env.example backend/.env
cp .env.example .env
# El bind mount de los datos fuente existe siempre, aunque los Excel aún no estén.
mkdir -p data/layers
```

En **`backend/.env`** hay que poner, como mínimo:

```
SECRET_KEY=<50+ caracteres aleatorios>
DEBUG=0
ALLOWED_HOSTS=obs.predes.org.pe,observatorio.predes.org.pe
SITE_URL=https://observatorio.predes.org.pe
BACKEND_URL=https://obs.predes.org.pe
CORS_ALLOWED_ORIGINS=https://observatorio.predes.org.pe
CSRF_TRUSTED_ORIGINS=https://obs.predes.org.pe,https://observatorio.predes.org.pe
ADMIN_URL=loginseguro/
POSTGRES_PASSWORD=<contraseña fuerte>
MEILI_MASTER_KEY=<50+ caracteres aleatorios>
DJANGO_SUPERUSER_USERNAME= / _EMAIL= / _PASSWORD=
```

`SECRET_KEY` y `MEILI_MASTER_KEY`: `python -c "import secrets; print(secrets.token_urlsafe(50))"`.

**`ADMIN_URL=loginseguro/`** y no `admin/`: `/admin/` es lo primero que prueba cualquier escaneo
automático. Si lo cambias, ajusta el `location` correspondiente en
`deploy/nginx/conf.d/observatorio.conf` — tienen que coincidir.

En **`.env` de la raíz** (variables de compose, no de Django):

```
SITE_DOMAIN=observatorio.predes.org.pe
API_DOMAIN=obs.predes.org.pe
VITE_API_URL=https://obs.predes.org.pe/api
VITE_SEARCH_URL=https://obs.predes.org.pe/search
VITE_TILES_URL=https://obs.predes.org.pe/tiles
VITE_MEILI_SEARCH_KEY=<la imprime meili_setup; se rellena en el paso 4>
```

> `SITE_DOMAIN` y `API_DOMAIN` son las que consume nginx. Compose las exige con `:?`, así que un
> `.env` al que le falte una **aborta antes de crear un solo contenedor**, con el mensaje puesto.
> `CORS_ALLOWED_ORIGINS` de `backend/.env` tiene que ser `https://` + `SITE_DOMAIN`, exactamente:
> es el mismo valor que nginx pone en `Access-Control-Allow-Origin` para `/media/` y `/tiles/`, y
> si discrepan el visor se queda sin capas.

> **Las `VITE_*` se hornean en el bundle durante el build**, no se leen en runtime. Si apuntan a
> `localhost`, el sitio queda mudo en el servidor **sin un solo error en los logs**. Cada vez que
> cambien hay que reconstruir la imagen del frontend, no basta con reiniciar.

```bash
# 2. Certificado, con nginx todavía parado y certbot abriendo él mismo el puerto 80.
#    UN SOLO certificado con los dos dominios como SAN. `--cert-name` fija el nombre de la
#    lineage, que es de donde leen LOS DOS bloques 443. Sin él, certbot la nombra con el primer
#    -d, y basta reordenar los argumentos para que nginx deje de encontrar el archivo.
#    Conviene hacerlo antes con `--dry-run`: valida el reto ACME sin gastar cuota.
docker compose run --rm --entrypoint certbot --publish 80:80 certbot certonly \
  --standalone --cert-name observatorio.predes.org.pe \
  -d observatorio.predes.org.pe -d obs.predes.org.pe \
  --email <correo> --agree-tos --no-eff-email

# 3. Todo arriba
docker compose up -d --build

# 4. Índices y llave de búsqueda
docker compose exec backend python manage.py meili_setup
#    → copiar VITE_MEILI_SEARCH_KEY al .env de la raíz

# 5. Datos. Sin los Excel y GeoJSON en data/layers/ el seed aborta: para levantar la plataforma
#    sin ellos, `seed --solo-catalogos` (catálogos, sitio, menú, grupos y superusuario).
docker compose exec backend python manage.py seed --capas --tiles

# 6. Reconstruir el frontend con la llave ya en su sitio, y publicarlo
docker compose build frontend && docker compose run --rm frontend
```

`migrate` y `meili_setup` corren solos en cada arranque del contenedor (son idempotentes), así
que el paso 4 solo hace falta para **ver** la llave.

### Por qué el primer certificado va por `--standalone` y no por webroot

Tres razones, las tres comprobadas contra un servidor real el 04/08/2026:

1. **nginx no arranca sin los certificados.** Los bloques `443` declaran `ssl_certificate`, y con el
   archivo ausente nginx aborta con `cannot load certificate … No such file or directory`. Así que
   no puede servir el reto de `/.well-known/acme-challenge/` antes de que exista el primer
   certificado: es un círculo. Con `--standalone`, certbot abre el puerto 80 por su cuenta.
2. **`--entrypoint certbot` no es opcional.** El servicio `certbot` define un `entrypoint` con el
   bucle de renovación, de modo que `docker compose run --rm certbot certonly …` **ignora los
   argumentos** y se queda girando en el bucle sin emitir nada. El síntoma es un comando que no
   termina y no dice por qué.

3. **Un solo certificado, y hay que decirle cómo se llama.** `certonly -d A -d B` crea **una sola**
   lineage —un certificado con los dos dominios como SAN— y la nombra con el primer `-d`. Los dos
   bloques 443 leen de ahí, así que `--cert-name` deja de hacerlo depender del orden de los
   argumentos. Apuntar el bloque del API a `live/<API_DOMAIN>/` **no funciona**: ese directorio no
   existe y nginx aborta con `cannot load certificate`.

Las **renovaciones** sí van por webroot y no requieren nada: las hace el propio contenedor `certbot`
cada 12 h, y el `--webroot` de su bucle prevalece sobre el método guardado en la primera emisión.
Quien recoge el certificado renovado es nginx, que se recarga cada 6 h desde
`deploy/nginx/docker-entrypoint.d/40-recarga-periodica.sh`. Sin esa recarga, nginx seguiría
sirviendo el certificado viejo hasta que caducara.

## Comprobaciones tras desplegar

```bash
set -a && . ./.env && set +a          # SITE_DOMAIN, API_DOMAIN y VITE_MEILI_SEARCH_KEY

# Lo primero: que envsubst haya sustituido los dominios. Si algo falla ahí, nginx no arranca
# —los `include` apuntarían a archivos inexistentes—, pero conviene verlo con los ojos.
docker compose exec nginx nginx -T | grep -E 'server_name|ssl_certificate |Allow-Origin'

curl -sI https://$SITE_DOMAIN/ | head -1          # 200, la SPA
curl -s  https://$API_DOMAIN/api/sitio/ | head -c 80      # JSON de configuración
curl -sI https://$API_DOMAIN/loginseguro/login/ | head -1  # 200, el admin (el de ADMIN_URL)
curl -sr 0-99 -D - -o /dev/null https://$API_DOMAIN/tiles/ccpp.pmtiles | grep -i 206
curl -s https://$API_DOMAIN/api/peligros/resumen/ | grep -o '"total_ccpp":[0-9]*'

# Ayuda memoria CON su mapa. Descargar el PDF no basta: sale igual sin mapa —es la degradación
# prevista— y así estuvo saliendo en producción local sin que nada lo dijera. El mapa es la única
# imagen rasterizada del documento, así que contarlas es la comprobación: tiene que dar ≥ 1.
curl -so /tmp/am.pdf https://$API_DOMAIN/api/distritos/080101/ayuda-memoria.pdf \
  && grep -c '/Subtype /Image' /tmp/am.pdf

# Buscador, dos comprobaciones distintas y las dos necesarias:
# a. Sin llave → 401. Confirma que el proxy manda la ruta y no la raíz (un 405 sería el proxy mal).
curl -s -o /dev/null -w '%{http_code}\n' -X POST \
  -H 'Content-Type: application/json' -d '{"queries":[]}' \
  https://$API_DOMAIN/search/multi-search

# b. CON la llave del .env → 200. Confirma que la llave con la que se construyó el bundle sigue
#    siendo válida. Es la que faltaba, y su ausencia costó un buscador en modo básico.
curl -s -o /dev/null -w '%{http_code}\n' -X POST \
  -H "Authorization: Bearer $VITE_MEILI_SEARCH_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"queries":[{"indexUid":"medidas","q":"cusco","limit":1}]}' \
  https://$API_DOMAIN/search/multi-search
```

El del resumen debe decir `8968`.

> **`GET /search/health` respondiendo 200 no prueba nada.** La raíz de Meilisearch también
> responde 200, así que si el proxy manda todo a la raíz —lo que pasaba hasta que las pruebas E2E
> lo destaparon— esa comprobación pasa igual y el buscador cae al fallback de DRF en cada
> búsqueda, sin un error a la vista. Por eso se comprueba `multi-search` con POST: **405 significa
> proxy mal configurado**, y 401 (sin llave) o 200 (con ella) significa que llega bien.

> **Y un 401/403 *con* la llave tampoco es un problema del proxy: es la llave del bundle.** La
> `VITE_MEILI_SEARCH_KEY` va horneada en el frontend compilado, así que si no coincide con la de
> Meilisearch el sitio se degrada en tres sitios —búsqueda, conteos de las facetas de `/medidas` y
> autocompletado de lugares— y **solo el primero lo dice en pantalla**. La consola del navegador
> escribe `[buscador] Meilisearch rechazó la llave…`. Arreglo: `meili_setup`, copiar la llave al
> `.env` de la raíz y **reconstruir** el frontend (`build frontend` + `run --rm frontend`).
> La llave es estable —se deriva del uid fijo y de `MEILI_MASTER_KEY`—, así que esto solo puede
> pasar si se cambia la master key o si el bundle se construyó con un `.env` desactualizado.

Y en el navegador, `/peligros` tiene que pintar los puntos: es lo que confirma de una vez que el
API, los tiles, CORS y el bundle están todos bien. La verificación completa es la suite E2E:

```bash
./e2e/instalar-dependencias.sh                        # una sola vez por máquina
E2E_URL=https://$SITE_DOMAIN npx playwright test
```

> **El primer comando no es opcional en un servidor recién provisionado**, y menos en la familia
> RHEL. Playwright no la soporta oficialmente: descarga el binario de Ubuntu y **no instala sus
> dependencias**, porque solo sabe de `apt`. Sin ellas la suite entera falla con
> `browserType.launch: Target page, context or browser has been closed`, que **parece el sitio
> caído** justo cuando acabas de desplegarlo. El script instala las librerías, `npm install` y el
> navegador, y termina arrancándolo para comprobar que va. Se ejecuta como tu usuario, **no con
> sudo** (Node viene de nvm y los navegadores van a `~/.cache/ms-playwright`).

## Runbook

| Operación | Comando |
|---|---|
| Desplegar una actualización | `git pull && docker compose build backend frontend && docker compose up -d && docker compose run --rm frontend` |
| Migraciones (normalmente automáticas) | `docker compose exec backend python manage.py migrate` |
| Sembrar o resembrar datos | `docker compose exec backend python manage.py seed` |
| **Comprobar el buscador** (servicio + índices al día) | `docker compose exec backend python manage.py meili_estado` |
| Reindexar la búsqueda | `docker compose exec backend python manage.py meili_rebuild` — o el botón de la tarjeta «Buscador» del panel del admin, que hace lo mismo en segundo plano |
| Regenerar los tiles de CCPP | `docker compose exec backend python manage.py generar_tiles_ccpp` |
| Regenerar los tiles de las capas | `docker compose exec backend python manage.py generar_tiles --rehacer` |
| Agregar métricas y purgar | `docker compose exec backend python manage.py shell -c "from apps.core.tasks import agregar_metricas; agregar_metricas.func()"` |
| Recargar nginx | `docker compose exec nginx nginx -s reload` |
| **Cambiar de dominio** | Editar `SITE_DOMAIN`/`API_DOMAIN` en el `.env` de la raíz y `docker compose up -d nginx` — **recrear**, no `restart`: el entorno se congela al crear el contenedor. Y emitir el certificado del dominio nuevo antes |
| Ver la configuración efectiva de nginx | `docker compose exec nginx nginx -T` |
| Renovar certificados a mano | `docker compose run --rm --entrypoint certbot certbot renew --webroot -w /var/www/certbot && docker compose exec nginx nginx -s reload` |
| Comprobar que la renovación funcionará | el mismo comando con `--dry-run` (no gasta cuota) |
| Logs | `docker compose logs -f backend worker nginx` |
| Backup manual | `docker compose exec backup /backup.sh` |
| Ver cuánto ocupa Docker | `docker system df` y `sudo du -sh /var/lib/docker` (ver más abajo: no dicen lo mismo) |
| Limpiar imágenes y caché | `docker builder prune -f --max-used-space 4GB && docker image prune -f` |

### Que Docker no se coma el disco

Cada `docker compose build backend` crea una imagen de ~2.8 GB y **deja la anterior sin tag**. Con
un despliegue al mes no se nota; con varios seguidos, sí. A eso se suma el caché de construcción de
BuildKit, que guarda las capas intermedias —compilar tippecanoe, `uv sync`, `playwright install`— y
**no se limpia solo si no se le dice**.

Dos medidas, y la primera es la que evita tener que acordarse:

**1. Un techo al caché, en `/etc/docker/daemon.json`.** No existe por defecto; hay que crearlo.

```json
{
  "builder": { "gc": { "enabled": true, "defaultKeepStorage": "4GB" } }
}
```

Luego `sudo systemctl restart docker`. **Corta el servicio unos segundos**: los contenedores con
`restart: unless-stopped` vuelven solos, pero conviene hacerlo fuera de horario. El archivo vive en
el servidor y **no se versiona**, así que hay que crearlo en cada máquina.

**2. Una limpieza semanal en el cron del host**, por si el caché crece entre construcciones:

```cron
0 5 * * 1 docker builder prune -f --max-used-space 4GB >> /var/log/observatorio-limpieza.log 2>&1 && docker image prune -f >> /var/log/observatorio-limpieza.log 2>&1
```

`image prune` sin `-a` borra **solo las imágenes sin tag**, que son las que deja atrás cada
reconstrucción. Con `-a` se llevaría también las que no tengan un contenedor arriba, y eso incluye
la imagen de desarrollo con `pytest`: recuperarla cuesta recompilar tippecanoe.

> **Nunca `docker system prune --volumes`.** Ahí viven `pgdata`, `media`, `meili_data` y
> `certbot_conf`: la base, los PDF y las imágenes que sube PREDES, los índices de búsqueda y los
> certificados. `docker system prune` a secas es aceptable —se lleva el contenedor `frontend`
> parado, que es de un solo disparo y se recrea—, pero con `--volumes` te llevas la plataforma.

> **`docker system df` engaña, y por exceso.** Cuenta bajo «Build Cache» capas que están
> **compartidas con las imágenes vivas**, así que las suma dos veces: puede anunciar 6.6 GB de
> caché cuando `/var/lib/docker` entero ocupa 5.1 GB. Lo purgable de verdad es la columna
> `Private` de `docker buildx du`. Si un `prune` dice «Total reclaimed space: 0B», no está roto:
> es que lo privado ya estaba por debajo del techo que le pediste.

**Al desplegar, `docker compose run --rm frontend` no es opcional**: es lo que copia el `dist/`
nuevo al volumen que sirve nginx. Sin ese paso el backend se actualiza y el frontend no.

### Tarea nocturna de métricas

La agregación diaria y la purga de eventos de más de 90 días no se ejecutan solas. Añadir al cron
del host:

```cron
15 3 * * * cd /ruta/al/observatorio && docker compose exec -T backend python manage.py shell -c "from apps.core.tasks import agregar_metricas; agregar_metricas.func()" >> /var/log/observatorio-metricas.log 2>&1
```

Sin esto el panel del admin se queda en blanco (lee del agregado, no de los eventos crudos) y la
tabla de eventos crece sin límite.

### Vigilancia del buscador

`meili_estado` termina con **código distinto de 0** si el servicio no responde o si algún índice está
desfasado, así que sirve de comprobación desatendida:

```cron
30 4 * * * cd /ruta/al/observatorio && docker compose exec -T backend python manage.py meili_estado || mail -s "Observatorio: revisar el buscador" alguien@predes.org.pe
```

**Comprueba, no arregla**, a propósito: reconstruir índices por su cuenta a las cuatro de la mañana
no es lo que se quiere de un vigilante. Reindexar es una decisión de una persona, y tiene su botón en
el panel del admin.

Por qué hace falta vigilarlo: el índice se sincroniza por señales hacia el worker, así que si el
worker estuvo caído, si Meilisearch no respondía al guardar, o si alguien escribió en la base fuera
de la aplicación, **el índice se queda atrás sin ningún síntoma**. Lo publicado se ve en su página y
simplemente no aparece al buscarlo.

## Backups

- **Base de datos**: el servicio `backup` hace `pg_dump` diario a las 02:00 en el volumen
  `backups`, con retención de 7 diarios, 4 semanales y 6 mensuales.
- **Media** (uploads, tiles, datasets): cron del host, semanal:
  ```cron
  30 2 * * 0 docker run --rm -v predes-observatorio_media:/m -v /respaldos:/out alpine tar czf /out/media-$(date +\%F).tar.gz -C /m .
  ```
- **Fuera del servidor**: copiar `/respaldos` a un destino de PREDES (rclone, o descarga manual
  mensual documentada). **Un backup que vive solo en el mismo disco que la base no es un backup.**

### Restauración: probada

Ensayada el 03/08/2026 sobre la base con todos los datos sembrados:

```bash
# 1. Volcado
docker compose exec -T db pg_dump -U observatorio -d observatorio --clean --if-exists > respaldo.sql

# 2. Restauración (esto BORRA y recrea el esquema)
docker compose exec -T db psql -U observatorio -d observatorio < respaldo.sql

# 3. Reconstruir los índices de búsqueda: no viajan en el volcado
docker compose exec backend python manage.py meili_rebuild
```

**Resultado medido**: volcado de 2.6 MB en menos de 1 s. Con el esquema **borrado por completo**
(`DROP SCHEMA public CASCADE`, 0 tablas), la restauración tardó **3 segundos, sin un solo error**,
y los conteos volvieron exactos: 8,968 centros poblados, 10,978 clasificaciones, 6 medidas. El
reindexado de Meilisearch tarda otros ~17 s por los 8,968 centros poblados. El sitio respondió
con normalidad inmediatamente después.

Dos cosas que **no** están en el volcado de la base y hay que restaurar aparte:

1. El volumen `media` (imágenes subidas, PDF, tiles, Excel importados).
2. Los índices de Meilisearch — se reconstruyen con `meili_rebuild`, no hace falta respaldarlos.

## Diagnóstico

**502 Bad Gateway en todo, justo después de un despliegue.** Era el fallo clásico de esta
configuración: nginx resuelve los nombres del bloque `upstream` una sola vez, al cargar la
configuración, y cada recreación del contenedor le da una IP nueva. Ya está resuelto con un
`resolver 127.0.0.11` y el destino en una variable, de modo que la resolución ocurre en cada
petición. Si vuelve a aparecer, comprobar que esa parte de
`deploy/nginx/conf.d/observatorio.conf` sigue intacta.

**El visor sale sin capas.** Por orden: que `/api/mapas/capas/` devuelva algo (una capa con
`estado_tiles != ok` no se anuncia a propósito); que la URL que anuncia sea alcanzable desde el
navegador (`BACKEND_URL`); y que `/tiles/` responda **206** a una petición con `Range`, no 200.

**El visor sale sin puntos, pero con capas.** `/api/ccpp/geojson/` con los mismos parámetros que
manda la página. Si devuelve `features: []`, el filtro está de más.

**El buscador no encuentra algo que sí está publicado.** `meili_rebuild`. Si se arregla, hubo una
escritura fuera del ORM (un import, un `update()` de queryset) que las señales no vieron.

**El buscador funciona pero sin facetas ni tolerancia a errores de tecleo.** Está cayendo al
fallback de DRF. Comprobar `POST /search/multi-search` (ver arriba): un 405 es el proxy mandando
todo a la raíz de Meilisearch, y se arregla en el `location /search/` de
`deploy/nginx/conf.d/observatorio.conf`, que quita el prefijo con `rewrite` y **no** con la barra
final de `proxy_pass`.

**Un Excel no entra.** Admin → Cargas de datos → el `log` de la carga. Está escrito en español y
cita hoja y fila; es el documento que dice qué corregir en el archivo.

**Los correos no llegan.** Log del `worker`. Si dice «sin destinatarios», los usuarios del grupo
Publicador no tienen correo configurado — la tarea termina bien y el fallo es invisible desde
fuera, así que conviene revisarlo antes de darlo por bueno.

**El PDF sale sin mapa.** Es una degradación prevista, no un fallo: si la captura con Chromium no
sale, el documento se genera igual con todo lo demás y el motivo queda en el log del worker.

## Seguridad

- `DEBUG=0`, admin fuera de `/admin/`, HSTS, `nosniff` y `Referrer-Policy` (ya en la config).
- Ningún contenedor publica puertos salvo nginx. En producción **no** se usa `compose.dev.yml`,
  que sí abre 5432, 7700 y 8000.
- Throttling de DRF: 1000/hora general, 30/hora en exports y PDF, 60/minuto en el beacon de
  métricas.
- Las métricas no guardan PII: `session_hash` es un hash **diario** de IP+UA truncado, que no
  permite reidentificar a nadie ni seguirle la pista entre días.
- Actualizar las imágenes base mensualmente: `docker compose pull && docker compose up -d`.

## Capacitación (Fase III del TDR)

El guion de la sesión grabada está en **`manual-admin-predes.md`**, que es también el manual que
se le entrega al equipo.
