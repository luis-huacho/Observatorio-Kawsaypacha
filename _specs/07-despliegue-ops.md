# 07 — Despliegue y operación

Docker Compose en servidor propio (VPS) con dominio, HTTPS y backups automáticos (requisito TDR).

## Dominios (ADR-A14)

| Dominio | Sirve |
|---|---|
| `observatorio.predes.org.pe` | La SPA estática (`dist/`). Es lo que el público conoce |
| `obs.predes.org.pe` | `/api/`, el admin (`ADMIN_URL`), `/static/`, `/media/`, `/tiles/` y `/search/` |

Separar el sitio público del backend deja el admin y el API fuera del dominio que se difunde, y permite mover cualquiera de los dos sin tocar el otro. El coste es que **el frontend deja de ser mismo-origen**: se activa `django-cors-headers` con allowlist de los dos dominios, y nginx añade cabeceras CORS en `/media/` y `/tiles/` (las necesitan PMTiles por HTTP Range y la exportación del mapa a PNG desde el canvas).

## Servicios (`compose.yaml` en la raíz)

| Servicio | Imagen | Rol |
|---|---|---|
| `db` | `postgres:16-alpine` | volumen `pgdata`; healthcheck `pg_isready` |
| `backend` | build `backend/` | **gunicorn** `:8000`; volúmenes `media` (RW) y `static`; depends_on db+meilisearch healthy |
| `worker` | misma imagen | `manage.py db_worker` (django-tasks): importaciones, tiles, Gemini, correos, agregación de métricas |
| `meilisearch` | `getmeili/meilisearch:v1.15` | volumen `meili_data`; `MEILI_MASTER_KEY`; sin puertos publicados |
| `frontend` | build `frontend/` | compila y copia `dist/` al volumen `web_dist`; termina (perfil build) |
| `nginx` | `nginx:1.27-alpine` | `:80/:443`; los dos server blocks; ver abajo |
| `certbot` | `certbot/certbot` | emisión y renovación de certificados (webroot) |
| `backup` | `prodrigestivill/postgres-backup-local` | `pg_dump` diario, retención 7d/4w/6m, volumen `backups` |

Volúmenes: `pgdata`, `meili_data`, `media` (incluye `media/tiles/`, `media/datasets/`, `media/informes/`, `media/contenido/`), `static` (estáticos del admin tras `collectstatic`), `web_dist`, `certbot_conf`, `certbot_www`, `backups`.

**ADR-A6bis — nginx en contenedor sustituye a Caddy.** El spec original usaba Caddy por el HTTPS automático. Se cambia a nginx + certbot por decisión del dueño del proyecto: es lo que PREDES y su proveedor de hosting ya saben operar, y el ahorro de Caddy (un fichero de configuración más corto) no compensa introducir una pieza que nadie más en la organización sabe depurar. El coste asumido es explícito: la renovación de certificados deja de ser automática por diseño y pasa a depender del contenedor `certbot` y de su cron.

## Desarrollo local

Un solo comando levanta y baja todo el sitio, backend incluido:

```bash
docker compose -f compose.yaml -f compose.dev.yml up -d --build   # arriba
docker compose -f compose.yaml -f compose.dev.yml down            # abajo
```

El override de desarrollo:

- publica `db` (5432), `meilisearch` (7700) y `backend` (8000) en el host;
- corre `runserver` con el código montado (recarga en caliente);
- deja `nginx`, `certbot`, `backup` y `frontend` fuera (perfil `prod`);
- fuerza `DEBUG=1` y `EMAIL_BACKEND=console`.

El frontend en desarrollo corre en el host con `npm run dev` (Vite en `:5173`) apuntando a `http://localhost:8000`. Para probar el modo producción completo en local —SPA compilada servida por nginx— se levanta con el perfil `prod` y `SITE_DOMAIN=localhost`.

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
    location /gestion/ { proxy_pass http://backend:8000; }   # ADMIN_URL del .env
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

Ambos bloques con `listen 443 ssl` y redirección desde `:80`. Los certificados los emite `certbot` por webroot y los renueva su cron; nginx recarga tras cada renovación.

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
ADMIN_URL=gestion/     # admin fuera de /admin/ por defecto
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
