# Comandos — Observatorio Kallpachakuy

Chuleta. Los porqués están en `_docs/` y `_specs/`.

## Atajos

```bash
alias dc='docker compose -f compose.yaml -f compose.dev.yml'
alias dcl='docker compose -f compose.yaml -f compose.local.yml'
alias dm='docker compose -f compose.yaml -f compose.dev.yml exec backend python manage.py'
alias dmp='docker compose exec backend python manage.py'
```

## Entornos (local)

```bash
# Desarrollo: código montado, recarga en caliente, API en :8000
dc up -d

# Desarrollo reconstruyendo; solo hace falta si cambian pyproject.toml o uv.lock
dc up -d --build

# Rehacer el venv del volumen anónimo; arregla «pytest: executable file not found»
dc up -d --build --renew-anon-volumes backend worker

# Bajar conservando los datos
dc down

# Reset total: BORRA base, índices, media y tiles
dc down -v

# Vite en el host, :5173 con HMR
cd frontend && npm run dev

# Producción en local: nginx sirviendo el bundle compilado en el :80
dcl up -d --build
dcl run --rm frontend
dcl exec backend python manage.py collectstatic --noinput

# Qué está corriendo
dc ps
```

## Datos y siembra

```bash
# Catálogos, territorio y peligros; idempotente, no pisa lo editado
dm seed

# Con el contenido de demostración del prototipo
dm seed --demo

# Adjunta los GeoJSON fuente a las capas, y genera los PMTiles
dm seed --capas --tiles

# Sin importar ningún Excel, para levantar sin los datos del cliente
dm seed --solo-catalogos

# Carpeta con los Excel y GeoJSON; por defecto DATOS_FUENTE_DIR, montada en /datos
dm seed --datos /datos

# Arranque de un entorno nuevo
dm seed --demo --capas --tiles

# Migraciones; corren solas en cada arranque
dm migrate

# Superusuario del admin
dm createsuperuser

# Comprobar la configuración de Django
dm check
```

## Búsqueda

```bash
# Crea índices y ajustes; imprime VITE_MEILI_SEARCH_KEY
dm meili_setup

# ¿Está arriba y al día? Sale ≠ 0 si hay desfase. Avisa, no arregla
dm meili_estado

# Reconstruye todos los índices desde la base
dm meili_rebuild

# Solo los indicados: medidas normativa noticias documentos videos eventos ccpp
dm meili_rebuild medidas ccpp

# Comprobar el proxy, en modo local o en el servidor; en desarrollo no hay nginx.
# Da 200 con la llave buena. /search/health da 200 aunque el proxy esté roto
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://localhost/search/multi-search \
  -H "Authorization: Bearer $VITE_MEILI_SEARCH_KEY" -H 'Content-Type: application/json' \
  -d '{"queries":[{"indexUid":"medidas","q":"cusco","limit":1}]}'
```

## Cola de tareas

```bash
# ¿Avanza el worker? Sale ≠ 0 si está atascada. Avisa, no arregla
dm cola_estado

# Reiniciarlo; comprobar antes qué tarea quedó a medias
dc restart worker
```

## Mapas y tiles

```bash
# Regenera media/tiles/ccpp.pmtiles desde la base
dm generar_tiles_ccpp

# Genera los PMTiles de las capas pendientes
dm generar_tiles

# Solo esas capas
dm generar_tiles rios lagunas glaciares

# Regenera también las que ya están en «ok»
dm generar_tiles --rehacer

# Los tiles deben servirse por rangos: tiene que dar 206
curl -sr 0-99 -o /dev/null -w '%{http_code}\n' http://localhost:8000/tiles/ccpp.pmtiles
```

## Pruebas

```bash
# Suite backend, dentro del contenedor
dc exec backend pytest

# Las lentas: Excel completos y el PDF con mapa
dc exec backend pytest -m lento

# Dependencias de Playwright; una sola vez por máquina, sin sudo
./e2e/instalar-dependencias.sh

# E2E contra el dev server de Vite
npx playwright test

# E2E contra el bundle servido por nginx; la que encuentra los fallos de integración
E2E_URL=http://localhost npx playwright test

# Modo interactivo, e informe de la última corrida
npm run e2e:ui
npm run e2e:informe
```

## Frontend

```bash
# Dev server con HMR
cd frontend && npm run dev

# Compilar, y comprobar tipos (el lint del proyecto)
cd frontend && npm run build
cd frontend && npm run lint

# Republicar el bundle; obligatorio tras cambiar cualquier VITE_*
dcl build frontend && dcl run --rm frontend
```

## Despliegue (servidor)

```bash
# Levantar producción
docker compose up -d --build

# Desplegar una actualización
git pull && docker compose build backend frontend && docker compose up -d && docker compose run --rm frontend

# Recargar nginx tras tocar conf.d/*.conf o *.inc
docker compose exec nginx nginx -s reload

# Recrear nginx tras cambiar SITE_DOMAIN o API_DOMAIN; recrear, no restart
docker compose up -d nginx

# Ver la configuración efectiva, ya sustituida
docker compose exec nginx nginx -T

# Primera emisión del certificado, con nginx parado
docker compose run --rm --entrypoint certbot --publish 80:80 certbot certonly --standalone \
  --cert-name observatorio.predes.org.pe -d observatorio.predes.org.pe -d obs.predes.org.pe \
  --email <correo> --agree-tos --no-eff-email

# Renovar a mano
docker compose run --rm --entrypoint certbot certbot renew --webroot -w /var/www/certbot \
  && docker compose exec nginx nginx -s reload
```

## Backups (servidor)

```bash
# Backup manual de la base; el servicio backup lo hace solo a diario
docker compose exec backup /backup.sh

# Volcado manual
docker compose exec -T db pg_dump -U observatorio -d observatorio --clean --if-exists > respaldo.sql

# Restaurar: BORRA y recrea el esquema
docker compose exec -T db psql -U observatorio -d observatorio < respaldo.sql

# Obligatorio tras restaurar: los índices no viajan en el volcado
dmp meili_rebuild

# Respaldo del volumen media; el prefijo del volumen es el nombre del directorio del proyecto
docker volume ls --format '{{.Name}}' | grep media
docker run --rm -v <proyecto>_media:/m -v ~/respaldos:/out alpine \
  tar czf /out/media-$(date +%F).tar.gz -C /m .
```

## Diagnóstico

```bash
# Logs de desarrollo; los correos del flujo editorial salen aquí
dc logs -f backend worker

# Logs de producción
docker compose logs -f backend worker nginx

# Reiniciar los contenedores «unhealthy»; nunca toca el worker
./deploy/vigilar-contenedores.sh
./deploy/vigilar-contenedores.sh --dry-run

# Comprobar el sitio desde fuera, solo con curl
./deploy/comprobar-sitio.sh "$SITE_DOMAIN" "$API_DOMAIN" "$VITE_MEILI_SEARCH_KEY"

# Cargar SITE_DOMAIN, API_DOMAIN y la llave antes de las comprobaciones
set -a && . ./.env && set +a

# Vida del backend; responde 200 aunque la base o el buscador estén caídos
curl -s https://$API_DOMAIN/api/salud/

# El admin, bajo su prefijo ADMIN_URL, que ya lleva la barra final
curl -sI https://$API_DOMAIN/${ADMIN_URL}login/ | head -1

# El PDF trae su mapa: tiene que dar ≥ 1. Que descargue no basta
curl -so /tmp/am.pdf https://$API_DOMAIN/api/distritos/080101/ayuda-memoria.pdf \
  && grep -c '/Subtype /Image' /tmp/am.pdf
```

## Tracker de errores

```bash
# Túnel al Gitea del servidor de desarrollo
ssh -L 3000:localhost:3000 usuario@servidor

# Levantarlo
docker compose -f compose.tracking.yaml up -d

# Publicarlo bajo /gitea, y retirarlo
docker compose -f compose.tracking.yaml -f compose.tracking-publicado.yml up -d
docker compose -f compose.tracking.yaml up -d
```
