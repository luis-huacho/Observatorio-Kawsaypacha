# Despliegue sin Docker, con base de datos gestionada

Segunda vía de puesta en producción: el mismo código, sin contenedores. La base de datos es un
**servicio gestionado** contratado aparte; gunicorn y Meilisearch corren bajo systemd, y nginx sirve
la SPA compilada.

> **La vía recomendada sigue siendo Docker Compose** ([`despliegue.md`](./despliegue.md)): es la que
> está probada de punta a punta y la que fija las versiones de tippecanoe, GDAL y WeasyPrint. Este
> documento existe para cuando no se pueda usar Docker, o cuando la base de datos ya sea un servicio
> contratado y no tenga sentido levantar un PostgreSQL propio.

Todo lo que sigue se deriva de lo que ya funciona en contenedores: los paquetes salen de
`backend/Dockerfile`, y los comandos de `backend/docker-entrypoint.sh` y de su `CMD`. Lo que **no**
se ha podido verificar sin un servidor está marcado como tal al final.

## Topología

```
                 Internet
                    │
        ┌───────────┴────────────┐
        │  nginx  :80 → :443     │   observatorio.predes.org.pe → dist/ de la SPA
        └───┬───────────┬────────┘   obs.predes.org.pe          → todo lo demás
            │           │
   127.0.0.1:8000   127.0.0.1:7700         ┌──────────────────────────┐
   ┌────────┴───────┐  ┌──┴──────────┐     │  PostgreSQL gestionado   │
   │ gunicorn       │  │ Meilisearch │     │  (fuera del servidor)    │
   │ (systemd)      │  │ (systemd)   │     └────────────┬─────────────┘
   └────────┬───────┘  └─────────────┘                  │
            │                                            │
   ┌────────┴────────┐                                   │
   │ worker de tareas│───────────────────────────────────┘
   │ (systemd)       │  importaciones, tiles, PDF, correos, métricas
   └─────────────────┘
```

**Solo nginx escucha en el exterior.** gunicorn y Meilisearch se atan a `127.0.0.1`: publicarlos
dejaría el API accesible sin las cabeceras CORS y Meilisearch expuesto con su master key como única
defensa.

## 0. Antes de empezar

| Cosa | Quién la entrega |
|---|---|
| Servidor con Debian/Ubuntu o RHEL/Rocky/Fedora, acceso `sudo` | PREDES |
| **PostgreSQL 16 gestionado**: host, puerto, base, usuario, contraseña | PREDES |
| DNS de `observatorio.predes.org.pe` y `obs.predes.org.pe` apuntando al servidor | PREDES |
| Credenciales SMTP y `GEMINI_API_KEY` | PREDES (opcionales: sin ellas esas funciones se degradan con aviso) |
| `data/layers/` con los Excel y GeoJSON (145 MB) | PREDES |

Convención de rutas usada en todo el documento; ajústalas si prefieres otras:

```
/srv/observatorio            el repo clonado
/srv/observatorio/backend    BASE_DIR de Django (staticfiles/ y media/ cuelgan de aquí)
/var/www/observatorio        el dist/ de la SPA que sirve nginx
/var/lib/meilisearch         datos de Meilisearch
/var/backups/observatorio    volcados de la base
```

Y un usuario de servicio sin privilegios:

```bash
sudo useradd --system --home /srv/observatorio --shell /usr/sbin/nologin observatorio
sudo mkdir -p /srv/observatorio /var/www/observatorio /var/backups/observatorio
sudo chown -R observatorio: /srv/observatorio /var/www/observatorio /var/backups/observatorio
```

## 1. Paquetes del sistema

Agrupados por para qué sirven, igual que en el Dockerfile. Verificados en Debian 12 / Ubuntu 24.04
y en Rocky 9 / Fedora 41.

**Debian / Ubuntu**

```bash
sudo apt update && sudo apt install -y \
  libpango-1.0-0 libpangocairo-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 \
  libffi8 shared-mime-info fonts-dejavu-core \
  gdal-bin \
  libsqlite3-0 zlib1g \
  postgresql-client \
  nginx certbot python3-certbot-nginx \
  git curl ca-certificates
```

**RHEL / Rocky / Fedora** — en RHEL y Rocky hace falta EPEL antes (ahí viven `gdal` y `certbot`):

```bash
sudo dnf install -y epel-release        # solo RHEL/Rocky, no Fedora
sudo dnf install -y \
  pango cairo gdk-pixbuf2 libffi shared-mime-info dejavu-sans-fonts \
  gdal \
  sqlite-libs zlib \
  postgresql \
  nginx certbot python3-certbot-nginx \
  git curl ca-certificates
```

| Grupo | Para qué | Qué pasa sin él |
|---|---|---|
| pango, cairo, gdk-pixbuf, libffi, shared-mime-info, fuentes DejaVu | **WeasyPrint** (ayuda memoria PDF) | El PDF no se genera; sin las fuentes sale con cajas en vez de texto |
| `gdal-bin` / `gdal` (`ogr2ogr`) | Reproyectar y recortar las capas | Las capas cartográficas quedan en estado `error` |
| sqlite, zlib | Runtime de tippecanoe | tippecanoe no arranca |
| `postgresql-client` / `postgresql` (`pg_dump`, `psql`) | Respaldos y restauración | No hay backups (requisito 8 del TDR) |
| nginx, certbot | Edge y HTTPS | — |

> **SELinux (RHEL/Rocky/Fedora).** Con SELinux en *enforcing*, nginx **no puede leer** rutas fuera de
> `/var/www` y `/usr/share/nginx`, y tampoco conectarse a gunicorn. El síntoma es un **403** o un
> **502** sin nada útil en el log de la aplicación. Hay que habilitar las dos cosas:
>
> ```bash
> sudo setsebool -P httpd_can_network_connect 1          # proxy_pass a 127.0.0.1:8000
> sudo semanage fcontext -a -t httpd_sys_content_t "/srv/observatorio/backend/(staticfiles|media)(/.*)?"
> sudo restorecon -Rv /srv/observatorio/backend
> ```
>
> Alternativa más simple: dejar `staticfiles/` y `media/` bajo `/var/www/observatorio/`.

## 2. tippecanoe ≥ 2.17, desde el código fuente

No hay paquete ni en Debian ni en RHEL, y hace falta ≥ 2.17: es la versión que escribe PMTiles de
forma nativa. Con una anterior habría que pasar por MBTiles y convertir. Es la razón de que la imagen
de Docker tenga una etapa dedicada a compilarlo.

```bash
# Debian/Ubuntu
sudo apt install -y build-essential libsqlite3-dev zlib1g-dev
# RHEL/Rocky/Fedora
sudo dnf install -y gcc-c++ make sqlite-devel zlib-devel

git clone --depth 1 https://github.com/felt/tippecanoe.git /tmp/tippecanoe
make -C /tmp/tippecanoe -j"$(nproc)" && sudo make -C /tmp/tippecanoe install
tippecanoe --version        # >= 2.17
```

Los paquetes `*-devel`/`*-dev` solo hacen falta para compilar; se pueden quitar después.

## 3. Python y dependencias

**El proyecto exige Python 3.12 o 3.13** (`requires-python = ">=3.12,<3.14"`). Ojo: **Debian 12 trae
Python 3.11**, que no sirve; Ubuntu 24.04 trae 3.12 y RHEL 9 tiene `python3.12` como paquete aparte.

Lo más simple y portable es dejar que **`uv` gestione también el intérprete**, que es lo que ya usa
el proyecto para las dependencias:

```bash
sudo -u observatorio bash -lc '
  curl -LsSf https://astral.sh/uv/install.sh | sh
  git clone <repo> /srv/observatorio && cd /srv/observatorio/backend
  ~/.local/bin/uv python install 3.12
  ~/.local/bin/uv sync --no-dev          # crea backend/.venv con las dependencias fijadas por uv.lock
'
```

`--no-dev` deja fuera pytest y la barra de depuración: en un servidor de producción no hacen falta.

### Chromium para el mapa del PDF

```bash
sudo -u observatorio bash -lc 'cd /srv/observatorio/backend && .venv/bin/playwright install --with-deps chromium'
```

`--with-deps` instala las librerías de sistema que Chromium necesita. **Si se omite este paso la
plataforma funciona igual**: la ayuda memoria se genera sin el mapa y el motivo queda en el log del
worker. Es una degradación prevista, no un error.

> Y por eso **hay que comprobar que el mapa sale**, no solo que el PDF se descargue: el documento se
> genera igual sin él. La comprobación está en §13. El mapa base son teselas de openstreetmap.org: si
> este servidor no tiene salida a internet, el mapa sale con los centros poblados y las capas propias
> sobre fondo plano —y el log lo avisa—, en lugar de no salir.

## 4. Meilisearch como servicio

```bash
curl -L https://install.meilisearch.com | sh
sudo mv ./meilisearch /usr/local/bin/
sudo mkdir -p /var/lib/meilisearch && sudo chown observatorio: /var/lib/meilisearch
```

`/etc/systemd/system/meilisearch.service`:

```ini
[Unit]
Description=Meilisearch — buscador del Observatorio Kallpachakuy
After=network-online.target

[Service]
User=observatorio
Group=observatorio
# Solo en loopback: nginx lo proxya bajo /search/ y la master key no puede ser la única defensa.
ExecStart=/usr/local/bin/meilisearch --http-addr 127.0.0.1:7700 --db-path /var/lib/meilisearch
Environment=MEILI_ENV=production
# La misma MEILI_MASTER_KEY que backend/.env. 0400 y de root: no la lee nadie más.
EnvironmentFile=/etc/observatorio/meilisearch.env
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo mkdir -p /etc/observatorio
printf 'MEILI_MASTER_KEY=%s\n' "<la misma que backend/.env>" | sudo tee /etc/observatorio/meilisearch.env
sudo chmod 400 /etc/observatorio/meilisearch.env
sudo systemctl enable --now meilisearch && sudo systemctl status meilisearch --no-pager
```

## 5. Configuración: `backend/.env`

Se copia de `backend/.env.example` y se completa. Lo que cambia respecto del despliegue con Docker
son **los cinco valores de la base** y las URL internas, que dejan de ser nombres de servicio:

```ini
DEBUG=0
SECRET_KEY=<50+ caracteres aleatorios>
ALLOWED_HOSTS=obs.predes.org.pe,observatorio.predes.org.pe
SITE_URL=https://observatorio.predes.org.pe
BACKEND_URL=https://obs.predes.org.pe
CORS_ALLOWED_ORIGINS=https://observatorio.predes.org.pe
CSRF_TRUSTED_ORIGINS=https://obs.predes.org.pe,https://observatorio.predes.org.pe
ADMIN_URL=loginseguro/

# --- Base de datos GESTIONADA ---
POSTGRES_DB=observatorio
POSTGRES_USER=<usuario del servicio>
POSTGRES_PASSWORD=<contraseña del servicio>
POSTGRES_HOST=<host que da el proveedor>
POSTGRES_PORT=5432
# TLS obligatorio hacia la base. Ver la nota de abajo.
PGSSLMODE=require

# --- Servicios locales, ya no son nombres de contenedor ---
MEILI_URL=http://127.0.0.1:7700
MEILI_MASTER_KEY=<la misma que meilisearch.env>
RENDER_MAPA_BASE_URL=http://127.0.0.1:8000
DATOS_FUENTE_DIR=/srv/observatorio/data/layers

DJANGO_SUPERUSER_USERNAME= / _EMAIL= / _PASSWORD=
```

```bash
sudo chown observatorio: /srv/observatorio/backend/.env
sudo chmod 600 /srv/observatorio/backend/.env
```

> **Cómo llega `PGSSLMODE` a la base sin tocar código.** `settings.py` no fija `sslmode`, así que el
> parámetro lo resuelve **libpq**, que lee de las variables de entorno lo que no venga en la cadena
> de conexión. Y `environ.Env.read_env()` vuelca `backend/.env` en `os.environ` al importar los
> settings, de modo que basta escribirlo ahí: vale igual para gunicorn, para el worker y para
> `manage.py`. Comprobado: con un valor inválido, la conexión falla con
> `invalid sslmode value`, que es la prueba de que libpq lo está leyendo.
>
> Si el proveedor entrega un certificado de CA y quieres validarlo de verdad, `PGSSLMODE=verify-full`
> más `PGSSLROOTCERT=/ruta/ca.crt` — las dos también por entorno.

> **Afinado opcional, y es un cambio de una línea que aún NO está aplicado.** Con la base fuera del
> servidor, cada petición abre una conexión TCP + TLS nueva, y eso se nota. Añadir
> `"CONN_MAX_AGE": 60` y `"CONN_HEALTH_CHECKS": True` al diccionario `DATABASES` de
> `backend/config/settings.py` reutiliza conexiones. Se deja a criterio de quien despliegue porque
> interactúa con el *pooler* del proveedor: si usas el puerto del pooler en modo transacción,
> conviene dejarlo en 0.

## 6. Migrar, sembrar y recolectar estáticos

Mismos comandos que el entrypoint del contenedor, y en el mismo orden:

```bash
cd /srv/observatorio/backend
sudo -u observatorio .venv/bin/python manage.py migrate --noinput
sudo -u observatorio .venv/bin/python manage.py meili_setup      # imprime la llave de búsqueda
sudo -u observatorio .venv/bin/python manage.py seed --capas --tiles
sudo -u observatorio .venv/bin/python manage.py collectstatic --noinput
```

El `seed` imprime los conteos al terminar: **8.968 centros poblados, 10.978 clasificaciones, 13
provincias, 112 distritos**. Si no coinciden, algo se perdió en la importación. Las advertencias que
imprime son esperadas y son un entregable para PREDES (calidad de los datos de origen).

> **Guarda la llave que imprime `meili_setup`**: es la `VITE_MEILI_SEARCH_KEY` del paso 8. **No
> cambia** aunque se borre `/var/lib/meilisearch`: se deriva del uid fijo de la llave y de
> `MEILI_MASTER_KEY` (las llaves de Meilisearch son deterministas). Solo cambia si cambias la master
> key, y entonces hay que **rehacer el build del frontend**, porque la llave va horneada en el bundle.
> Con una llave que Meilisearch no reconozca, el sitio se degrada en tres sitios a la vez —búsqueda,
> conteos de las facetas de `/medidas` y autocompletado de lugares— y **solo el primero lo dice en
> pantalla**; la consola del navegador escribe `[buscador] Meilisearch rechazó la llave…`.

## 7. gunicorn y el worker, bajo systemd

`/etc/systemd/system/observatorio-backend.service`:

```ini
[Unit]
Description=Observatorio Kallpachakuy — API y admin (gunicorn)
After=network-online.target meilisearch.service
Wants=meilisearch.service

[Service]
User=observatorio
Group=observatorio
WorkingDirectory=/srv/observatorio/backend
# Los mismos parámetros que el CMD de la imagen. Solo en loopback: nginx es el único que entra.
ExecStart=/srv/observatorio/backend/.venv/bin/gunicorn config.wsgi:application \
    --bind 127.0.0.1:8000 --workers 3 --timeout 120 --access-logfile - --error-logfile -
Restart=always
# La base gestionada puede tardar en aceptar conexiones tras un reinicio del servidor; aquí no hay
# healthcheck que espere, así que systemd reintenta hasta que responda.
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

`/etc/systemd/system/observatorio-worker.service`:

```ini
[Unit]
Description=Observatorio Kallpachakuy — worker de tareas (django-tasks)
After=network-online.target observatorio-backend.service
Wants=observatorio-backend.service

[Service]
User=observatorio
Group=observatorio
WorkingDirectory=/srv/observatorio/backend
# Importaciones de Excel, generación de tiles, PDF, resúmenes con Gemini, correos y métricas.
# NO migra: dos `migrate` en paralelo compiten por el lock de la tabla de migraciones.
ExecStart=/srv/observatorio/backend/.venv/bin/python manage.py db_worker
Restart=always
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now observatorio-backend observatorio-worker
sudo systemctl status observatorio-backend observatorio-worker --no-pager
```

Logs: `journalctl -u observatorio-backend -f` y `journalctl -u observatorio-worker -f`. **Los avisos
del flujo editorial salen en el log del worker**; si dice «sin destinatarios», los usuarios del grupo
Publicador no tienen correo configurado.

## 8. El frontend

Vite **hornea las `VITE_*` en el bundle durante el build**; no se leen en runtime. Si apuntan a
`localhost`, el sitio queda mudo en el servidor sin un solo error en los logs.

```bash
cd /srv/observatorio/frontend
cat > .env.production <<'EOF'
VITE_API_URL=https://obs.predes.org.pe/api
VITE_SEARCH_URL=https://obs.predes.org.pe/search
VITE_TILES_URL=https://obs.predes.org.pe/tiles
VITE_MEILI_SEARCH_KEY=<la que imprimió meili_setup>
EOF

npm ci && npm run build
sudo rsync -a --delete dist/ /var/www/observatorio/
```

El `rm`/`--delete` va a propósito: los assets llevan hash en el nombre, así que sin borrar los
viejos se acumulan indefinidamente. La llave de búsqueda **va dentro del bundle** y es segura por
diseño: solo permite buscar, y solo en los índices públicos.

## 9. nginx

`/etc/nginx/conf.d/observatorio.conf`. Es la configuración de `deploy/nginx/conf.d/observatorio.conf`
con tres diferencias del *bare metal*: `proxy_pass` a `127.0.0.1:8000` (sin el `resolver` de Docker,
que ahí resolvía nombres de contenedor), `alias` a rutas reales y `root` al `dist/` copiado.

```nginx
proxy_cache_path /var/cache/nginx/tiles levels=1:2 keys_zone=tiles:10m max_size=512m inactive=7d;

# --- HTTP: solo el reto de certbot y la redirección -------------------------
server {
    listen 80 default_server;
    server_name observatorio.predes.org.pe obs.predes.org.pe;

    location /.well-known/acme-challenge/ { root /var/www/certbot; }
    location / { return 301 https://$host$request_uri; }
}

# --- SPA pública ------------------------------------------------------------
server {
    listen 443 ssl default_server;
    http2 on;
    server_name observatorio.predes.org.pe;

    ssl_certificate     /etc/letsencrypt/live/observatorio.predes.org.pe/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/observatorio.predes.org.pe/privkey.pem;

    root /var/www/observatorio;
    index index.html;

    gzip on;
    gzip_types text/css application/javascript application/json image/svg+xml;
    gzip_min_length 1024;

    # Los assets de Vite llevan hash: se cachean para siempre. index.html nunca.
    location /assets/     { expires 1y; add_header Cache-Control "public, immutable"; }
    location = /index.html { add_header Cache-Control "no-cache"; }

    # SPA: cualquier ruta del router cae en index.html. Sin esto, recargar /peligros da 404.
    location / { try_files $uri $uri/ /index.html; }
}

# --- Backend ----------------------------------------------------------------
server {
    listen 443 ssl;
    http2 on;
    server_name obs.predes.org.pe;

    # El MISMO certificado que la SPA, y no uno propio: `certbot -d A -d B` emite UNA sola lineage
    # —un certificado con los dos dominios como SAN— nombrada con el primer -d. La ruta
    # /etc/letsencrypt/live/obs.predes.org.pe/ NO existe, y apuntar ahí impide arrancar nginx.
    ssl_certificate     /etc/letsencrypt/live/observatorio.predes.org.pe/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/observatorio.predes.org.pe/privkey.pem;

    client_max_body_size 64M;      # Excel de 5.4 MB, GeoJSON de hasta 57 MB

    location /api/ {
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        # Sin esto, con SECURE_PROXY_SSL_HEADER activo Django cree que la petición es HTTP y
        # redirige en bucle.
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_pass http://127.0.0.1:8000;
    }

    location /loginseguro/ {       # el valor de ADMIN_URL; si lo cambias, cámbialo aquí
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_pass http://127.0.0.1:8000;
    }

    location /static/ {
        alias /srv/observatorio/backend/staticfiles/;
        expires 30d;
        add_header Cache-Control "public";
    }

    location /media/ {
        alias /srv/observatorio/backend/media/;
        add_header Access-Control-Allow-Origin "https://observatorio.predes.org.pe" always;
        expires 7d;
    }

    # Las tres cabeceras NO son opcionales: el protocolo pmtiles:// lee el archivo por trozos, y
    # sin Accept-Ranges ni Content-Range expuesto el visor se queda sin capas.
    location /tiles/ {
        alias /srv/observatorio/backend/media/tiles/;
        add_header Access-Control-Allow-Origin "https://observatorio.predes.org.pe" always;
        add_header Access-Control-Expose-Headers "Content-Length,Content-Range" always;
        add_header Accept-Ranges bytes always;
        add_header Cache-Control "public, max-age=3600" always;
    }

    # El prefijo se quita con `rewrite`. Con `proxy_pass http://127.0.0.1:7700/` funcionaría la
    # barra final, pero se deja explícito para que no se rompa el día que alguien meta una
    # variable en el destino: en cuanto proxy_pass lleva una variable, nginx DEJA de sustituir el
    # prefijo de la location y todo acaba en la raíz de Meilisearch. Eso dejó el buscador cayendo
    # al fallback de DRF en cada búsqueda, sin un error a la vista.
    location /search/ {
        rewrite ^/search/(.*)$ /$1 break;
        proxy_set_header Host $host;
        proxy_pass http://127.0.0.1:7700;
    }
}
```

```bash
sudo mkdir -p /var/cache/nginx/tiles /var/www/certbot
sudo nginx -t && sudo systemctl reload nginx
```

## 10. HTTPS

**El primer certificado se emite con nginx sin los bloques `443`**, porque nginx no arranca si
`ssl_certificate` apunta a un archivo que no existe: falla con `cannot load certificate`. Dos formas:

```bash
# a) La más simple: certbot edita la configuración de nginx por ti
sudo certbot --nginx -d observatorio.predes.org.pe -d obs.predes.org.pe \
  --email <correo> --agree-tos --no-eff-email

# b) Si prefieres pegar la configuración de arriba tal cual: emite primero, con nginx parado,
#    y añade los bloques 443 después.
sudo systemctl stop nginx
sudo certbot certonly --standalone --cert-name observatorio.predes.org.pe \
  -d observatorio.predes.org.pe -d obs.predes.org.pe \
  --email <correo> --agree-tos --no-eff-email
sudo systemctl start nginx
```

> **Es UN solo certificado con los dos dominios**, no dos. `--cert-name` fija el nombre de la
> lineage —el directorio de `/etc/letsencrypt/live/`— para que no dependa del orden de los `-d`, y
> **los dos bloques `443` leen de ahí**. Con la opción (a) da igual, porque el plugin de nginx
> reescribe las rutas él mismo.

La renovación la deja programada el propio paquete (`systemctl list-timers | grep certbot`). Se
comprueba con `sudo certbot renew --dry-run`.

## 11. Tareas periódicas

```cron
# Agregación diaria de métricas y purga de eventos de más de 90 días.
# Sin esto el panel del admin se queda en blanco —lee del agregado, no de los eventos crudos— y la
# tabla de eventos crece sin límite.
15 3 * * * cd /srv/observatorio/backend && sudo -u observatorio .venv/bin/python manage.py shell -c "from apps.core.tasks import agregar_metricas; agregar_metricas.func()" >> /var/log/observatorio-metricas.log 2>&1

# Vigilancia del buscador. Sale con código ≠ 0 si el servicio no responde o si algún índice está
# desfasado, y eso pasa **sin ningún síntoma**: lo publicado se ve en su página y no aparece al
# buscarlo. Comprueba y avisa; reindexar es una decisión de una persona (botón en el panel del admin).
30 4 * * * cd /srv/observatorio/backend && sudo -u observatorio .venv/bin/python manage.py meili_estado || mail -s "Observatorio: revisar el buscador" alguien@predes.org.pe

# Volcado diario de la base gestionada, con 14 días de retención.
30 2 * * * PGPASSWORD=<contraseña> pg_dump -h <host> -U <usuario> -d observatorio --clean --if-exists | gzip > /var/backups/observatorio/db-$(date +\%F).sql.gz && find /var/backups/observatorio -name 'db-*.sql.gz' -mtime +14 -delete

# Media (imágenes subidas, PDF, tiles, Excel importados), semanal.
0 3 * * 0 tar czf /var/backups/observatorio/media-$(date +\%F).tar.gz -C /srv/observatorio/backend media
```

Para no poner la contraseña en el cron, un `~/.pgpass` con permisos 600 es preferible.

## 12. Backups y restauración

Con base gestionada hay **dos niveles, y conviene tener los dos**:

1. Los **snapshots automáticos del proveedor** (retención y punto de recuperación según el plan
   contratado). Rápidos, pero viven en el mismo proveedor.
2. El **volcado propio** del cron anterior. Es la copia que PREDES controla, y hay que llevársela
   fuera del servidor (rclone a un destino de PREDES, o descarga mensual documentada). *Un backup que
   vive solo en el disco del servidor no es un backup.*

Restauración, con los mismos pasos ya cronometrados en la vía con Docker (**3 segundos** para una
base con todos los datos, sobre el esquema borrado por completo):

```bash
gunzip -c /var/backups/observatorio/db-2026-08-03.sql.gz | \
  PGPASSWORD=<contraseña> psql -h <host> -U <usuario> -d observatorio

# Los índices de búsqueda NO viajan en el volcado: se reconstruyen (~17 s).
cd /srv/observatorio/backend && sudo -u observatorio .venv/bin/python manage.py meili_rebuild
```

Y dos cosas que tampoco están en el volcado: el contenido de `media/` (se restaura del tar) y los
índices de Meilisearch (se reconstruyen, no hace falta respaldarlos).

## 13. Comprobaciones tras desplegar

```bash
systemctl is-active meilisearch observatorio-backend observatorio-worker nginx

# Buscador: servicio arriba **y** índices al día. Sale con código ≠ 0 si algo falla.
cd /srv/observatorio/backend && sudo -u observatorio .venv/bin/python manage.py meili_estado

curl -sI https://observatorio.predes.org.pe/ | head -1          # 200, la SPA
curl -s  https://obs.predes.org.pe/api/sitio/ | head -c 80      # JSON de configuración
curl -sI https://obs.predes.org.pe/loginseguro/login/ | head -1 # 200, el admin
curl -s https://obs.predes.org.pe/api/peligros/resumen/ | grep -o '"total_ccpp":[0-9]*'   # 8968

# Tiles por rangos: 206 y con Content-Range expuesto, o el visor se queda sin capas
curl -sr 0-127 -D - -o /dev/null https://obs.predes.org.pe/tiles/ccpp.pmtiles | grep -iE '206|content-range'

# Ayuda memoria CON su mapa: descargar el PDF no basta, sale igual sin él. El mapa es la única
# imagen rasterizada del documento, así que esto tiene que dar ≥ 1.
curl -so /tmp/am.pdf https://obs.predes.org.pe/api/distritos/080101/ayuda-memoria.pdf \
  && grep -c '/Subtype /Image' /tmp/am.pdf

# Buscador, las dos comprobaciones:
# a. Sin llave → 401. Confirma que Meilisearch recibe la ruta y no la raíz.
curl -s -o /dev/null -w '%{http_code}\n' -X POST \
  -H 'Content-Type: application/json' -d '{"queries":[]}' \
  https://obs.predes.org.pe/search/multi-search

# b. Con la llave del build → 200. Confirma que el bundle publicado puede buscar de verdad.
curl -s -o /dev/null -w '%{http_code}\n' -X POST \
  -H "Authorization: Bearer $VITE_MEILI_SEARCH_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"queries":[{"indexUid":"medidas","q":"cusco","limit":1}]}' \
  https://obs.predes.org.pe/search/multi-search
```

> **`GET /search/health` respondiendo 200 no prueba nada**: la raíz de Meilisearch también responde
> 200, así que un proxy que mande todo a la raíz pasa esa comprobación mientras el buscador cae al
> fallback de DRF. Un **405** en `multi-search` es la señal de proxy mal configurado; 401 (sin llave)
> o 200 (con ella) significan que llega bien.

Y la comprobación completa, si tienes Node en algún sitio:

```bash
E2E_URL=https://observatorio.predes.org.pe npx playwright test
```

En el navegador, `/peligros` tiene que pintar los puntos: confirma de una vez el API, los tiles,
CORS y el bundle.

## 14. Operación

| Operación | Comando |
|---|---|
| Desplegar una actualización | `git pull`, `uv sync --no-dev`, `migrate`, `collectstatic`, `systemctl restart observatorio-backend observatorio-worker`, y rehacer el build del frontend |
| Sembrar o resembrar datos | `manage.py seed` |
| **Comprobar el buscador** (servicio + índices al día) | `manage.py meili_estado` |
| Reindexar la búsqueda | `manage.py meili_rebuild` — o el botón de la tarjeta «Buscador» del panel del admin |
| Regenerar tiles | `manage.py generar_tiles_ccpp` · `manage.py generar_tiles --rehacer` |
| Logs | `journalctl -u observatorio-backend -u observatorio-worker -f` |
| Recargar nginx | `sudo nginx -t && sudo systemctl reload nginx` |

**Al actualizar, rehacer el build del frontend no es opcional** si cambió algo de `frontend/`: el
`dist/` de `/var/www/observatorio/` no se regenera solo.

## 15. Diagnóstico

| Síntoma | Dónde mirar |
|---|---|
| 502 en `/api/` | `systemctl status observatorio-backend`; con SELinux, `httpd_can_network_connect` |
| 403 en `/static/` o `/media/` | Permisos del usuario `nginx` sobre `/srv/observatorio/backend/`; con SELinux, el contexto `httpd_sys_content_t` |
| 400 Bad Request en todo | El `Host` no está en `ALLOWED_HOSTS` |
| Redirección infinita a HTTPS | Falta `proxy_set_header X-Forwarded-Proto $scheme` |
| El backend no arranca tras reiniciar el servidor | La base gestionada aún no acepta conexiones; systemd reintenta cada 5 s. Se ve en `journalctl -u observatorio-backend` |
| `could not connect to server` / `SSL is required` | `POSTGRES_HOST`/`PORT`, o falta `PGSSLMODE=require` |
| El visor sin capas | `/api/mapas/capas/`, y que `/tiles/` responda **206** |
| El buscador sin facetas, o «modo básico» | `POST /search/multi-search` **con la llave** (ver arriba). Un 401/403 ahí es el bundle construido con otra llave: `meili_setup`, actualizar `VITE_MEILI_SEARCH_KEY` y **rehacer el build** del frontend |
| Los correos no llegan | Log del worker, y que los usuarios del grupo tengan correo |
| El PDF sale sin mapa | Degradación prevista: falta Chromium o falló la captura. El motivo, en el log del worker |
| `ImportError` tras un `git pull` | El venv quedó desincronizado: `uv sync --no-dev` |

## 16. Qué se pierde respecto de Docker

Dicho sin adornos, porque es el argumento por el que la vía con Compose sigue siendo la recomendada:

- **Las versiones dejan de estar fijadas.** tippecanoe, GDAL y WeasyPrint pasan a depender del
  sistema, y una actualización puede cambiarlas por debajo. En la imagen están clavadas.
- **La reproducibilidad es manual.** Reconstruir el servidor exige repetir estos pasos a mano; con
  Compose es un `up -d --build`.
- **Hay más piezas que vigilar**: tres unidades de systemd, un cron y los permisos del sistema de
  archivos, en vez de un `docker compose ps`.

A cambio se ahorra la sobrecarga de los contenedores y se aprovecha una base de datos gestionada con
sus propios respaldos y su alta disponibilidad.

## Estado de verificación de este documento

Honestidad sobre qué está comprobado:

| Comprobado | Cómo |
|---|---|
| Los nombres de los paquetes | `apt-get install --dry-run` en Debian 12, y resolución en Rocky 9 (con EPEL) y Fedora 41 |
| Que Debian 12 trae Python 3.11 y no sirve | `apt-cache policy python3` en la imagen oficial |
| Que `PGSSLMODE` llega a libpq desde `backend/.env` | Un valor inválido produce `invalid sslmode value`, y `read_env()` deja la variable en `os.environ` |
| Que nginx no arranca sin los certificados | `nginx -t` con la configuración real y sin `/etc/letsencrypt` |
| Los comandos de Django, gunicorn y el worker | Son los mismos que ejecuta la imagen, en uso |

**Sin verificar, a falta de un servidor**: las unidades de systemd tal cual, la emisión con certbot,
los contextos de SELinux y la conexión a un PostgreSQL gestionado real. Conviene recorrer §13 en la
primera puesta en marcha y corregir aquí lo que haga falta.
