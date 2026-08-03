# 07 — Despliegue y operación

Docker Compose en servidor propio (VPS) con dominio, HTTPS y backups automáticos (requisito TDR). Referencia de dominio: `observatorio.predes.org.pe` (confirmar con PREDES).

## Servicios (`compose.yml` en la raíz)

| Servicio | Imagen | Rol |
|---|---|---|
| `db` | `postgres:16-alpine` | volumen `pgdata`; healthcheck `pg_isready` |
| `backend` | build `backend/` | gunicorn `:8000`; volúmenes `media` (RW); depends_on db+meilisearch healthy |
| `worker` | misma imagen | `manage.py db_worker` (django-tasks): importaciones, tiles, Gemini, correos, agregación de métricas |
| `meilisearch` | `getmeili/meilisearch:v1.15` | volumen `meili_data`; `MEILI_MASTER_KEY`; sin puertos publicados |
| `frontend` | build `frontend/` | compila y copia `dist/` al volumen `web_dist`; termina (perfil build) |
| `caddy` | `caddy:2` | `:80/:443`; ver Caddyfile |
| `backup` | `prodrigestivill/postgres-backup-local` | `pg_dump` diario, retención 7d/4w/6m, volumen `backups` |

Volúmenes: `pgdata`, `meili_data`, `media` (incluye `media/tiles/`, `media/datasets/`, `media/informes/`), `web_dist`, `caddy_data`, `backups`.

`compose.dev.yml` (override): puertos abiertos (5432, 7700, 8000), `runserver` con reload, Vite dev server aparte (`npm run dev`, no en compose), `EMAIL_BACKEND=console`, DEBUG=1.

## Caddyfile (esquema)

```
observatorio.predes.org.pe {
    encode gzip zstd
    handle /api/* { reverse_proxy backend:8000 }
    handle /admin/* { reverse_proxy backend:8000 }      # ruta real desde ADMIN_URL del .env
    handle /search/* { uri strip_prefix /search; reverse_proxy meilisearch:7700 }
    handle_path /tiles/* { root * /srv/media/tiles; file_server; header Cache-Control "public, max-age=3600" }
    handle_path /media/* { root * /srv/media; file_server }
    handle { root * /srv/web; try_files {path} /index.html; file_server }  # SPA
}
```
HTTPS automático (Let's Encrypt) — solo requiere el DNS apuntando al servidor.

## Dockerfile backend (multi-stage)

1. Stage `tippecanoe`: compila tippecanoe ≥2.17.
2. Stage final `python:3.12-slim`: deps apt (`gdal-bin`, libs de WeasyPrint: pango/cairo/gdk-pixbuf), binarios de tippecanoe, `uv sync` desde `pyproject.toml`, `collectstatic` (whitenoise para estáticos del admin), gunicorn.

## Variables de entorno

`backend/.env` (nunca commitear; `.env.example` versionado):
```
SECRET_KEY=            DEBUG=0            ALLOWED_HOSTS=observatorio.predes.org.pe
DATABASE_URL=postgres://observatorio:***@db:5432/observatorio
MEILI_URL=http://meilisearch:7700        MEILI_MASTER_KEY=
GEMINI_API_KEY=
EMAIL_HOST= EMAIL_PORT= EMAIL_HOST_USER= EMAIL_HOST_PASSWORD= DEFAULT_FROM_EMAIL=
ADMIN_URL=gestion/     # admin fuera de /admin/ por defecto
SITE_URL=https://observatorio.predes.org.pe
```
`frontend/.env`: ver spec 06.

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
| Reindexar búsqueda | `docker compose exec backend python manage.py meili_rebuild` |
| Regenerar tiles CCPP | `docker compose exec backend python manage.py generar_tiles_ccpp` |
| Logs | `docker compose logs -f backend worker` |
| Backup manual | `docker compose exec backup /backup.sh` |
| Restaurar BD | ver procedimiento en este doc (compose limpio + psql) |

Seguridad: `DEBUG=0`, admin en `ADMIN_URL` no-default, throttling DRF, `SECURE_*` headers de Django, contenedores sin puertos publicados salvo Caddy, actualizaciones de imágenes mensuales.

## Checklist de capacitación a PREDES (Fase III del TDR)

Sesión grabada (registro audiovisual = anexo del informe final):
1. Ingreso al admin, roles y contraseñas.
2. Subir/reemplazar el Excel de peligros y el de frecuencia (DatasetUpload) — ver el cambio en el visor.
3. Subir/reemplazar una capa GeoJSON y regenerar tiles.
4. Crear medida/noticia → enviar a revisión → publicar (correo incluido).
5. Subir un PDF y generar resumen con IA; corregirlo.
6. Editar textos del sitio (hero, footer, sobre) y el menú.
7. Descargar ayuda memoria PDF y exports Excel.
8. Leer el dashboard de métricas.
9. Dónde están los backups y a quién llamar si algo falla.

Pendientes de PREDES para producción: dominio/DNS, credenciales SMTP, API key de Gemini (o se entrega una), servidor (acceso SSH), data de inversión, capas SIG oficiales, textos definitivos.
