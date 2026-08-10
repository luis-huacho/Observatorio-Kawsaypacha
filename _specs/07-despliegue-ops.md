# 07 — Despliegue y operación

Docker Compose en servidor propio (VPS) con dominio, HTTPS y backups automáticos (requisito TDR).

## Dominios (ADR-A14)

| Dominio | Sirve |
|---|---|
| `SITE_DOMAIN` (producción: `observatorio.predes.org.pe`) | La SPA estática (`dist/`). Es lo que el público conoce |
| `API_DOMAIN` (producción: `obs.predes.org.pe`) | `/api/`, el admin (`ADMIN_URL`), `/static/`, `/media/`, `/tiles/` y `/search/` |

**Los dominios no están escritos en el repositorio.** Salen de esas dos variables del `.env` de la raíz, y nginx los toma al arrancar con `envsubst`: la imagen renderiza `deploy/nginx/templates/*.template` en `/etc/nginx/generado`, que `observatorio.conf` incluye. Se generan **fragmentos incluidos** y no el archivo entero a propósito — si el directorio de salida no fuera escribible, el script de la imagen deja un ERROR en el log y **sigue adelante**, y con el archivo entero eso dejaría a nginx sirviendo su página de bienvenida sin ningún bloque 443. Con fragmentos, el mismo fallo es un `include` inexistente y nginx no arranca.

Separar el sitio público del backend deja el admin y el API fuera del dominio que se difunde, y permite mover cualquiera de los dos sin tocar el otro. El coste es que **el frontend deja de ser mismo-origen**: se activa `django-cors-headers` con allowlist de los dos dominios, y nginx añade cabeceras CORS en `/media/` y `/tiles/` (las necesitan PMTiles por HTTP Range y la exportación del mapa a PNG desde el canvas).

## Servicios (`compose.yaml` en la raíz)

| Servicio | Imagen | Rol |
|---|---|---|
| `db` | `postgres:16-alpine` | volumen `pgdata`; healthcheck `pg_isready` |
| `backend` | build `backend/` | **gunicorn** `:8000`; volúmenes `media` (RW) y `static`; depends_on db+meilisearch healthy |
| `worker` | misma imagen | `manage.py db_worker` (django-tasks): importaciones, tiles, Gemini, correos, agregación de métricas |
| `meilisearch` | `getmeili/meilisearch:v1.15` | volumen `meili_data`; `MEILI_MASTER_KEY`; sin puertos publicados |
| `frontend` | build `frontend/` | compila la SPA y copia `dist/` al volumen `web_dist`; **termina al copiar** (`restart: "no"`), no es un servidor. Quien sirve es nginx montando `web_dist`. En el override de desarrollo queda apagado con `profiles: ["prod"]` |
| `nginx` | `nginx:1.27-alpine` | `:80/:443`; los dos server blocks; ver abajo |
| `certbot` | `certbot/certbot` | emisión y renovación de certificados (webroot) |
| `backup` | `prodrigestivill/postgres-backup-local` | `pg_dump` diario, retención 7d/4w/6m, volumen `backups` |

Volúmenes: `pgdata`, `meili_data`, `media` (incluye `media/tiles/`, `media/datasets/`, `media/informes/`, `media/contenido/`), `static` (estáticos del admin tras `collectstatic`), `web_dist`, `certbot_conf`, `certbot_www`, `backups`.

**ADR-A6bis — nginx en contenedor sustituye a Caddy.** El spec original usaba Caddy por el HTTPS automático. Se cambia a nginx + certbot por decisión del dueño del proyecto: es lo que PREDES y su proveedor de hosting ya saben operar, y el ahorro de Caddy (un fichero de configuración más corto) no compensa introducir una pieza que nadie más en la organización sabe depurar. El coste asumido es explícito: la renovación de certificados deja de ser automática por diseño y pasa a depender del contenedor `certbot` y de su cron.

## Los tres modos de compose

`compose.yaml` es la base (= producción) y hay **dos** overrides. No son intercambiables y se distinguen por una cosa: **de dónde sale el código que corre**.

| Modo | Comando | Código | Frontend | nginx |
|---|---|---|---|---|
| Producción | `docker compose up -d --build` | `COPY` en la imagen | imagen que vuelca `dist/` en `web_dist` | sí, TLS y dos dominios |
| **Desarrollo** | `-f compose.yaml -f compose.dev.yml` | **montado** (`./backend:/app`) | host, `npm run dev` `:5173` | no |
| Producción en local | `-f compose.yaml -f compose.local.yml` | `COPY` en la imagen | imagen, `run --rm frontend` | sí, HTTP en el `:80` |

Los tres comparten nombre de proyecto, así que **hay que bajar uno antes de levantar otro**. Al pasar de local a desarrollo, `nginx` no se detiene solo —`profiles: ["prod"]` solo impide arrancarlo— y se queda sirviendo en el `:80` el bundle viejo de `web_dist` contra el backend nuevo.

### Desarrollo (`compose.dev.yml`)

```bash
docker compose -f compose.yaml -f compose.dev.yml up -d --build   # arriba
docker compose -f compose.yaml -f compose.dev.yml down            # abajo
```

- publica `db` (5432), `meilisearch` (7700) y `backend` (8000) en el host;
- corre `runserver` **con el código montado**, así que edita y recarga: `--build` solo hace falta al cambiar dependencias (`pyproject.toml` / `uv.lock`);
- construye con `GRUPOS_UV=--group dev` sobre un tag propio (`predes-observatorio-backend-dev`) para que `pytest` viva en el contenedor y las dos imágenes convivan. `/app/.venv` es un **volumen anónimo**: al cambiar `GRUPOS_UV` hace falta `--renew-anon-volumes backend worker`, porque sobrevive a la reconstrucción;
- deja `nginx`, `certbot`, `backup` y `frontend` fuera (perfil `prod`);
- fuerza `DEBUG=1` y `EMAIL_BACKEND=console`.

El frontend corre en el host con `npm run dev` (Vite en `:5173`) apuntando a `http://localhost:8000`, con HMR. No se puede montar dentro del contenedor `frontend`: ese servicio no es un servidor sino un `alpine` de un solo uso que copia `dist/` y termina.

### Producción en local (`compose.local.yml`)

El sitio entero por el `:80`, sobre HTTP y en un solo host, sin dominios ni TLS. **No es un modo para iterar** —el código va por `COPY`, así que cada cambio pide `--build`—: es el paso de verificación antes de commitear.

```bash
docker compose -f compose.yaml -f compose.local.yml up -d --build
docker compose -f compose.yaml -f compose.local.yml run --rm frontend        # publica dist/ en web_dist
docker compose -f compose.yaml -f compose.local.yml exec backend python manage.py collectstatic --noinput
```

Qué cambia respecto de la base:

- `backend` y `worker` reciben `BACKEND_URL`, `SITE_URL` y `CORS_ALLOWED_ORIGINS` = `http://localhost`. `BACKEND_URL` es la URL con la que **el navegador del visitante** alcanza el backend —el API la usa para construir las URL absolutas de `/tiles/` y `/media/`—, y aquí el backend no publica el `8000`: apuntarla ahí deja al visor pidiendo tiles a un puerto cerrado. Para lo interno está `RENDER_MAPA_BASE_URL=http://backend:8000`, que es lo que usa el Chromium que renderiza el PDF dentro del contenedor;
- `nginx` **reemplaza** `conf.d` por `deploy/nginx/local/` —mismo target, así que compose sustituye en vez de acumular— y monta la configuración de producción en `/etc/nginx/comun` para los includes compartidos; publica solo el `80:80`;
- `certbot` y `backup` van a `profiles: ["nunca"]`.

Sigue exigiendo `SITE_DOMAIN` y `API_DOMAIN` en el `.env` de la raíz —`compose.yaml` las declara con `:?`— aunque la configuración local no las use.

**Para qué existe: verifica lo que el modo de desarrollo no puede ver**, porque en desarrollo no hay nginx y el navegador ataca a Django y a Meilisearch directamente. Solo aquí se comprueba que el bundle de Vite se sirve bien, que las rutas del router resuelven por `try_files`, que los estáticos del admin están donde nginx los busca, que los tiles salen por rangos con sus cabeceras CORS, y que el proxy `/search/` no cae al fallback de DRF. Es la corrida E2E que vale (`E2E_URL=http://localhost npx playwright test`, ver `08-plan-pruebas.md`).

## nginx (esquema)

```nginx
# --- SPA pública -----------------------------------------------------------
server {
    server_name observatorio.predes.org.pe;
    root /srv/www;
    gzip on;
    location / { try_files $uri /index.html; }          # client-side routing
    location /.well-known/acme-challenge/ { root /var/www/certbot; }
}

# --- Backend ---------------------------------------------------------------
server {
    server_name obs.predes.org.pe;
    client_max_body_size 64M;                            # Excel de 5.4 MB, GeoJSON de 57 MB

    location /api/     { proxy_pass http://backend:8000; }
    location /loginseguro/ { proxy_pass http://backend:8000; }  # ADMIN_URL del .env
    location /static/  { alias /srv/static/; }

    # El prefijo se quita con `rewrite`, NO con la barra final de proxy_pass: la configuración
    # real usa una variable en el destino (ver el resolver, más abajo), y en cuanto proxy_pass
    # lleva una variable nginx deja de sustituir el prefijo de la location. Con
    # `proxy_pass http://$destino/` todas las peticiones llegaban a la RAÍZ de Meilisearch:
    # `/search/health` daba 200 —la raíz también responde 200— y `POST /search/multi-search`
    # daba 405, así que el buscador caía al fallback de DRF en cada búsqueda sin un error a la
    # vista. La comprobación de despliegue es `POST /search/multi-search`, no `/search/health`.
    location /search/ {
        rewrite ^/search/(.*)$ /$1 break;
        proxy_pass http://meilisearch:7700;
    }

    location /media/ {
        alias /srv/media/;
        add_header Access-Control-Allow-Origin "https://observatorio.predes.org.pe";
    }
    location /tiles/ {
        alias /srv/media/tiles/;
        add_header Access-Control-Allow-Origin "https://observatorio.predes.org.pe";
        add_header Access-Control-Expose-Headers "Content-Length,Content-Range";
        add_header Accept-Ranges bytes;
        add_header Cache-Control "public, max-age=3600";
    }
}
```

Ambos bloques con `listen 443 ssl` y redirección desde `:80`. **Un solo certificado con los dos dominios como SAN**, en la lineage `SITE_DOMAIN`, de la que leen los dos bloques: `certbot -d A -d B` emite una sola y la nombra con el primer `-d`, así que apuntar el bloque del API a `live/API_DOMAIN/` impide arrancar nginx. La primera emisión va por `--standalone` con nginx parado (es un círculo: nginx no arranca sin los `.pem` y no puede servir el reto); las renovaciones, por webroot desde el contenedor `certbot`. La recarga que las recoge la hace el propio nginx cada 6 h, desde `deploy/nginx/docker-entrypoint.d/40-recarga-periodica.sh`.

## Dockerfile backend (multi-stage)

1. Stage `tippecanoe`: compila tippecanoe ≥2.17 (es la versión donde aparece la escritura nativa de PMTiles).
2. Stage final `python:3.12-slim`: deps apt (`gdal-bin`, libs de WeasyPrint: pango/cairo/gdk-pixbuf), binarios de tippecanoe copiados del stage anterior, `uv sync` desde `pyproject.toml`, `collectstatic`, gunicorn.

Al arranque el contenedor corre `migrate` y `meili_setup` (ambos idempotentes) antes de levantar gunicorn.

## Variables de entorno

`backend/.env` (nunca se commitea; `.env.example` versionado):

```
SECRET_KEY=            DEBUG=0
ALLOWED_HOSTS=obs.predes.org.pe,observatorio.predes.org.pe
SITE_URL=https://observatorio.predes.org.pe        # el que se difunde y va en los correos
BACKEND_URL=https://obs.predes.org.pe
CORS_ALLOWED_ORIGINS=https://observatorio.predes.org.pe
CSRF_TRUSTED_ORIGINS=https://obs.predes.org.pe,https://observatorio.predes.org.pe
POSTGRES_DB= POSTGRES_USER= POSTGRES_PASSWORD= POSTGRES_HOST=db POSTGRES_PORT=5432
MEILI_URL=http://meilisearch:7700        MEILI_MASTER_KEY=
GEMINI_API_KEY=
EMAIL_HOST= EMAIL_PORT= EMAIL_HOST_USER= EMAIL_HOST_PASSWORD= DEFAULT_FROM_EMAIL=
ADMIN_URL=loginseguro/ # admin fuera de /admin/ por defecto
DJANGO_SUPERUSER_USERNAME= DJANGO_SUPERUSER_EMAIL= DJANGO_SUPERUSER_PASSWORD=   # los usa `manage.py seed`
```

`frontend/.env`: ver spec 06. En producción las tres URL son absolutas contra `obs.predes.org.pe`.

## Backups (requisito TDR)

- **BD**: servicio `backup` — `pg_dump` diario 02:00, retención 7 diarios / 4 semanales / 6 mensuales en volumen `backups`.
- **Media** (uploads, tiles, datasets): cron del host — `tar` semanal de `media/` al mismo destino.
- **Off-site**: copiar `backups/` fuera del servidor (rclone a almacenamiento de PREDES o descarga manual mensual documentada).
- **Restauración probada** (obligatorio antes de la entrega): `psql < dump` en un compose limpio + `meili_rebuild` + verificación del visor. Documentar el tiempo que tomó.

## Runbook

| Operación | Comando |
|---|---|
| Desplegar actualización | `git pull && docker compose build backend frontend && docker compose up -d` |
| Migraciones | `docker compose exec backend python manage.py migrate` |
| Sembrar datos iniciales | `docker compose exec backend python manage.py seed` |
| Reindexar búsqueda | `docker compose exec backend python manage.py meili_rebuild` |
| Regenerar tiles CCPP | `docker compose exec backend python manage.py generar_tiles_ccpp` |
| Recargar nginx | `docker compose exec nginx nginx -s reload` |
| Renovar certificados | `docker compose run --rm certbot renew` |
| Logs | `docker compose logs -f backend worker` |
| Backup manual | `docker compose exec backup /backup.sh` |
| Restaurar BD | ver procedimiento en `_docs/despliegue.md` |

Seguridad: `DEBUG=0`, admin en `ADMIN_URL` no-default, throttling DRF, `SECURE_*` headers de Django, contenedores sin puertos publicados salvo nginx, actualizaciones de imágenes mensuales.

## Vigilancia y recuperación

`restart: unless-stopped` cubre que un proceso **muera**. No cubre que se **cuelgue**: gunicorn con sus workers bloqueados sigue `Up` y el sitio devuelve timeouts. Y Compose **no reinicia un contenedor «unhealthy»** — los healthchecks solo informan—, así que hace falta alguien que mire y decida.

| Pieza | Qué cubre | Dónde |
|---|---|---|
| `healthcheck` de `backend` y `nginx` | Que el proceso atienda de verdad | `compose.yaml` |
| `deploy/vigilar-contenedores.sh` (cron */2 min) | Reinicia lo «unhealthy», máx. 3/hora por servicio | anfitrión |
| `manage.py cola_estado` (cron diario) | Avisa si la cola no avanza. **No reinicia** | anfitrión |
| `deploy/comprobar-sitio.sh` | Lo que el anfitrión no puede ver: servidor caído, DNS, certificado | **otra máquina** |

**`GET /api/salud/` mide liveness, no dependencias** (spec 02). Responde `200` aunque PostgreSQL o Meilisearch estén caídos, y lo declara en el cuerpo. Si fallara por ellos, una caída de la base marcaría el backend «unhealthy» y el vigilante lo reiniciaría en bucle: reiniciar el backend no levanta la base, y el bucle borra el rastro. Por lo mismo va exenta de throttling — con `interval: 10s` son 360 peticiones/hora contra un techo anónimo de 1000, y un 429 provocaría reinicios sin que pasara nada.

**El worker se reinicia a mano, nunca solo.** Si se atasca a mitad de una importación de 10,978 filas, matarlo puede dejar el dato peor que parado. Es la misma doctrina que `meili_estado` —comprobar y arreglar se piden por separado—, y la razón de que ahí sí valga automatizar el reinicio de `backend` y `nginx`: reiniciar un servidor web colgado no destruye nada y la alternativa es un sitio caído.

**El vigilante corre en el anfitrión, no como contenedor.** `willfarrell/autoheal` y equivalentes exigen montar `/var/run/docker.sock`, que es la API de Docker sin autenticación: root del servidor cedido a un contenedor, en una máquina pública. Y añade una pieza que PREDES tendría que saber operar, que es justo lo que ADR-A6bis evitó al descartar Caddy.

**`nginx` mantiene `depends_on` sin `condition: service_healthy`**, a propósito: esperar a un backend sano dejaría el sitio entero caído en vez de degradado, y el `resolver 127.0.0.11` con destino en variable ya está puesto para que nginx sobreviva a un backend que aún no responde.

El estado de todo esto vive bajo `$HOME` (`~/observatorio-registros/`), no en `/var/log`, para que respaldar el servidor sean dos carpetas.

## Checklist de capacitación a PREDES (Fase III del TDR)

Sesión grabada (registro audiovisual = anexo del informe final). El guion desarrollado está en `_docs/manual-admin-predes.md`:

1. Ingreso al admin, roles y contraseñas.
2. Subir/reemplazar el Excel de peligros y el de frecuencia (DatasetUpload) — ver el cambio en el visor.
3. Subir/reemplazar una capa GeoJSON y regenerar tiles.
4. Crear medida/noticia → enviar a revisión → publicar (correo incluido).
5. Subir un PDF y generar resumen con IA; corregirlo.
6. Editar textos del sitio (hero, footer, sobre) y el menú.
7. Descargar ayuda memoria PDF y exports Excel.
8. Leer el dashboard de métricas.
9. Dónde están los backups y a quién llamar si algo falla.

Pendientes de PREDES para producción: DNS de los dos dominios, credenciales SMTP, API key de Gemini (o se entrega una), servidor (acceso SSH), data de inversión, capas SIG oficiales, textos definitivos.
