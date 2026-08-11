# Observatorio Kallpachakuy

Plataforma web pública de PREDES para monitorear la **Gestión del Riesgo de Desastres (GRD)** y la
**Adaptación al Cambio Climático (ACC)** en la región Cusco, Perú.

> El prototipo aprobado vive en `prototype/` y está congelado como referencia visual; el trabajo
> activo es `backend/` + `frontend/`.

## Qué ofrece

| Ruta | Contenido |
| --- | --- |
| `/peligros`, `/peligros/:codigo` | Visor de exposición: 8.968 centros poblados sobre MapLibre, agrupados y dimensionados por población, con su nivel de peligro. Ficha por centro poblado y ayuda memoria imprimible |
| `/medidas`, `/medidas/:slug` | Medidas de adaptación con facetas |
| `/inversion` | Ejecución del presupuesto del PP 0068 **por municipalidad** (la ruta tolera el estado vacío mientras no haya ejercicio publicado) |
| `/normativa`, `/normativa/:slug` | Normativa GRD/ACC con enlace a la publicación oficial y export Excel |
| `/recursos` | Biblioteca documental |
| `/noticias`, `/eventos`, `/videos` | Actualidad |
| `/comparar` | Comparativa entre distritos. **Fuera del menú** (ADR-P2): la página funciona y se llega por URL, pero no se anuncia; se reactiva desde **Menú** en el admin |
| `/buscar` | Búsqueda global con facetas (Meilisearch) |

## Stack

- **Backend** — Django 5.2 LTS + DRF + PostgreSQL 16 (sin PostGIS) + django-tasks (worker por BD,
  sin Redis) + admin con django-unfold. Gemini 2.5 Flash autocompleta resúmenes de PDF; siempre los
  revisa una persona antes de publicar.
- **Frontend** — Vite + React 18 + TypeScript + Tailwind 3 + react-router 6 + MapLibre GL.
- **Búsqueda** — Meilisearch, con llave *search-only* en el bundle del navegador.
- **Mapas** — capas de contexto (ríos, lagunas, glaciares) como PMTiles estáticos servidos con HTTP
  Range; los centros poblados llegan como GeoJSON desde el API.
- **Edge** — nginx, sobre dos dominios.

## Mapa del repo

```
.
├── backend/           Django. `apps/` una carpeta por dominio; `config/` settings y urls
├── frontend/          Vite + React + TS. `src/lib/` capa de datos; `src/routes/` una por página
├── e2e/               Pruebas de extremo a extremo (Playwright)
├── deploy/nginx/      `conf.d/` producción · `templates/` dominios · `local/` prueba HTTP
├── _specs/            Especificaciones y ADR — se leen ANTES de cambiar algo de fondo
├── _docs/             Documentación técnica y entregables (arquitectura, desarrollo, despliegue)
├── prototype/         Prototipo aprobado. CONGELADO: referencia visual, no se toca
├── data/              Excel y GeoJSON canónicos — NO se versionan (145 MB, los entrega PREDES)
├── compose.yaml       Base (= producción con Docker)
├── compose.dev.yml    Override de desarrollo
├── compose.local.yml  Override para probar el modo producción en local, sobre HTTP
├── CLAUDE.md          Guía del proyecto para el agente
└── README.md          Este archivo
```

---

# Entorno local

## Requisitos

- **Docker** y Docker Compose.
- **Node 22** y npm, para el frontend en modo desarrollo y para las pruebas E2E.
- Los **archivos de datos**, que no se versionan (145 MB): `data/layers/data/*.xlsx` y
  `data/layers/*.geojson`. Los entrega PREDES; sin ellos el seed no tiene qué importar, pero la
  plataforma arranca igual (con `seed --solo-catalogos`).
- Opcional: `uv` y Python 3.12+, solo si quieres correr `manage.py` desde el host.

## 1. Primera vez

```bash
# a. Configuración: tres archivos, cada uno para una cosa distinta (ver §3)
cp backend/.env.example backend/.env     # secretos de Django
cp .env.example .env                     # variables que interpola Docker Compose
cp frontend/.env.example frontend/.env   # URLs que usa Vite en dev

# b. En backend/.env, como mínimo:
#      SECRET_KEY            → python -c "import secrets; print(secrets.token_urlsafe(50))"
#      POSTGRES_PASSWORD     → cualquier contraseña
#      MEILI_MASTER_KEY      → otra cadena larga y aleatoria
#      DJANGO_SUPERUSER_USERNAME / _EMAIL / _PASSWORD  → tu acceso al admin

# c. Levantar base de datos, búsqueda, backend y worker
docker compose -f compose.yaml -f compose.dev.yml up -d --build

# d. Sembrar: catálogos, los Excel reales, contenido de demostración y tiles
docker compose -f compose.yaml -f compose.dev.yml exec backend \
  python manage.py seed --demo --capas --tiles

# e. Copiar la llave de búsqueda que imprime el paso anterior a LOS DOS .env
#    (también la reimprime `manage.py meili_setup`): frontend/.env para `npm run dev`
#    y el .env de la raíz para el bundle compilado (§7). No cambia con el tiempo.
#      VITE_MEILI_SEARCH_KEY=...

# f. El frontend, en el host
cd frontend && npm install && npm run dev
```

El primer build tarda unos minutos porque **compila tippecanoe**; es una sola vez. El seed con
`--tiles` tarda otro par de minutos y al final imprime los conteos: compáralos con la tabla de
[Los datos](#los-datos).

## 2. Qué se sirve y dónde

| Servicio | URL | Acceso | De dónde sale |
| --- | --- | --- | --- |
| **El sitio** (Vite, en el host) | http://localhost:5173 | público | `npm run dev` |
| **API** | http://localhost:8000/api/ | público, sin autenticación | contenedor `backend` |
| Documentación del API | http://localhost:8000/api/docs/ | público | Swagger UI |
| Esquema OpenAPI | http://localhost:8000/api/schema/ | público | YAML, para generar clientes |
| **Admin** | http://localhost:8000/**`$ADMIN_URL`** | usuario y contraseña | `DJANGO_SUPERUSER_*` de `backend/.env`, creado por `seed` |
| Tiles | http://localhost:8000/tiles/ccpp.pmtiles | público | vista propia, **solo con `DEBUG=True`** |
| Media subida | http://localhost:8000/media/… | público | Django, **solo con `DEBUG=True`** |
| **Meilisearch** | http://localhost:7700 | `Authorization: Bearer <master key>` | `MEILI_MASTER_KEY` de `backend/.env` |
| **PostgreSQL** | localhost:5432 | usuario / contraseña / base | `POSTGRES_*` de `backend/.env` |
| Worker de tareas | sin puerto | — | `logs -f worker` |

**El prefijo del admin lo fija `ADMIN_URL`** en `backend/.env`, y el `.env.example` trae
`loginseguro/`: si lo copiaste sin cambiarlo, el admin está en
**http://localhost:8000/loginseguro/**, no en `/admin/`. Se cambia a propósito, porque `/admin/` es lo
primero que prueba cualquier escaneo automático. En local puedes dejar `ADMIN_URL=admin/` si te
resulta más cómodo.

Comprobación rápida de que todo responde:

```bash
curl -s localhost:8000/api/peligros/resumen/ | grep -o '"total_ccpp":[0-9]*'   # 8968
curl -sr 0-99 -D - -o /dev/null localhost:8000/tiles/ccpp.pmtiles | head -1    # 206
curl -s localhost:7700/health                                                  # available
```

En dev, **el navegador ataca a Meilisearch directamente** en el 7700 con la llave de solo búsqueda
(en producción pasa por nginx bajo `/search/`). Si el 7700 no responde, el buscador sigue
funcionando contra `/api/buscar/`, pero sin facetas ni tolerancia a errores de tecleo.

## 3. Los tres `.env`

Es la confusión más habitual: son tres archivos, con tres consumidores distintos.

| Archivo | Lo lee | Contiene |
| --- | --- | --- |
| `backend/.env` | Django (`environ.Env.read_env`) y los contenedores (`env_file`) | Secretos: `SECRET_KEY`, `POSTGRES_*`, `MEILI_MASTER_KEY`, SMTP, Gemini, superusuario, `ADMIN_URL` |
| `.env` (raíz) | **Docker Compose**, al interpolar `compose.yaml` | Las `VITE_*` que se hornean en el bundle del frontend al construir la imagen |
| `frontend/.env` | Vite en `npm run dev` | URL del API, de la búsqueda y de los tiles para el modo desarrollo |

Ninguno se versiona; los tres `.env.example` sí. Dos cosas que conviene saber:

- **Las `VITE_*` se hornean en el bundle durante el build**, no se leen en runtime. Cambiarlas exige
  reconstruir la imagen del frontend, no reiniciarla. Ojo con la consecuencia: la
  `VITE_MEILI_SEARCH_KEY` es **la misma en los dos últimos archivos** y hay que cambiarla en los dos.
  Actualizar solo `frontend/.env` arregla `npm run dev` y deja el sitio compilado con una llave
  inválida — es exactamente lo que pasó una vez.
- **`backend/.env` lo lee Django directamente**, así que también sirve para correr `manage.py` desde
  el host (ver §9).

## 4. El día a día

```bash
alias dc='docker compose -f compose.yaml -f compose.dev.yml'
alias dm='docker compose -f compose.yaml -f compose.dev.yml exec backend python manage.py'

dc up -d                      # arriba
dc down                       # abajo (los datos se conservan)
dc ps                         # qué está corriendo
dc logs -f backend worker     # los correos del flujo editorial salen aquí, por consola
dm <comando>                  # cualquier comando de Django
```

Comandos propios del proyecto:

| Comando | Para qué |
| --- | --- |
| `seed [--demo] [--capas] [--tiles] [--solo-catalogos]` | Sembrar. Idempotente y **no pisa lo editado** |
| `meili_setup` | Crear índices e imprimir la llave de solo búsqueda |
| `meili_estado` | ¿Está arriba el buscador y al día? Sale con código ≠ 0 si no |
| `meili_rebuild [indice]` | Reconstruir la búsqueda desde la base |
| `cola_estado` | ¿Sigue avanzando el worker? Sale con código ≠ 0 si la cola está atascada |
| `generar_tiles_ccpp` | Regenerar los PMTiles de centros poblados |
| `generar_tiles [--rehacer]` | Regenerar los PMTiles de las capas de contexto |

### ¿Reconstruir, recrear o reiniciar?

Depende de si lo que cambiaste vive **dentro de la imagen** o **montado desde el disco**.

| Qué cambias | Qué hace falta |
| --- | --- |
| Código Python, plantillas, migraciones | `docker compose build backend && docker compose up -d backend worker` |
| `pyproject.toml` / `uv.lock` | Lo mismo: reconstruir |
| Código del frontend o cualquier `VITE_*` | `docker compose build frontend && docker compose run --rm frontend` |
| `deploy/nginx/conf.d/*.conf` y `*.inc` | `docker compose exec nginx nginx -s reload` |
| `deploy/nginx/templates/*` y `docker-entrypoint.d/*` | `docker compose restart nginx` |
| `SITE_DOMAIN`, `API_DOMAIN` o cualquier cosa de `backend/.env` | `docker compose up -d` — **recrear**, no `restart` |

**`restart` no relee los `.env`.** Las variables de entorno se fijan cuando se **crea** el
contenedor, no cuando arranca: si cambias `backend/.env` o los dominios y haces `restart`, el
contenedor sigue con los valores viejos **y no lo dice**. `up -d` sí recrea al detectar que la
configuración cambió.

**En producción el backend no monta el código.** `compose.yaml` solo monta `media`, `static` y
`data/layers`; el código va horneado por el `COPY` del Dockerfile, así que un `restart` tras editar
un `.py` no hace nada. En **desarrollo** es al revés: `compose.dev.yml` monta `./backend:/app` y
`runserver` recarga solo, de modo que ahí no se reconstruye salvo que cambien las dependencias.

**Y el que más se olvida: `docker compose run --rm frontend`.** Ese servicio es de un solo disparo
—construye el bundle y lo copia al volumen que sirve nginx— y **no es opcional en cada
despliegue**. Sin él, el backend se actualiza y el sitio se queda con el bundle anterior, sin un
solo error. `restart frontend` tampoco sirve: ese contenedor ya terminó su trabajo.

**Y el segundo que más se olvida: `nginx -s reload`.** `up -d` solo recrea los contenedores cuya
configuración de compose cambió, y la de nginx casi nunca cambia: si el `git pull` trae un cambio en
`deploy/nginx/conf.d/`, el archivo está en su sitio —el volumen es un *bind mount*— pero el proceso
sigue con la configuración que cargó al arrancar. **El síntoma no es un error, es un 404** que parece
«esa ruta no existe». Pasó el 05/08/2026 con el bloque `/gitea`. Y cuidado al diagnosticarlo:
`nginx -T` **relee los archivos del disco**, así que enseña la configuración nueva y da la impresión
de que está cargada.

```bash
# Desplegar una actualización, entera y en orden
git pull && docker compose build backend frontend && docker compose up -d \
  && docker compose run --rm frontend \
  && docker compose exec nginx nginx -s reload
```

Y la contrapartida de reconstruir tanto: cada `build` del backend deja atrás una imagen de ~2.8 GB
sin tag, y BuildKit guarda las capas intermedias. Se limpia con

```bash
docker builder prune -f --max-used-space 4GB && docker image prune -f
```

**Nunca con `--volumes`**: ahí viven la base, los archivos subidos, los índices y los certificados.
En el servidor esto se automatiza con un techo en `/etc/docker/daemon.json` y un cron semanal — ver
[«Que Docker no se coma el disco»](./_docs/despliegue.md) en la guía de despliegue.

## 5. Revisar que el sistema está bien

Ocho comprobaciones, elegidas porque cada una cubre algo que **falla en silencio**: la página carga,
el API responde 200 y la cifra que se publica es otra.

| Qué | Cómo | Qué confirma |
| --- | --- | --- |
| Los datos entraron completos | `curl -s localhost:8000/api/peligros/resumen/` | `total_ccpp: 8968`; los importadores no perdieron filas |
| El visor pinta | abrir http://localhost:5173/peligros | API, GeoJSON y MapLibre funcionando a la vez |
| Los tiles salen por rangos | `curl -sr 0-99 -D - -o /dev/null localhost:8000/tiles/ccpp.pmtiles` | **206**, no 200: sin Range el visor descarga 3 MB por tesela |
| Las capas se anuncian | `curl -s localhost:8000/api/mapas/capas/` | tres capas con su URL: los PMTiles se generaron |
| Los filtros llegan al API | filtrar por peligro y nivel en `/peligros` | la tabla se recorta y el total lo da el servidor, no las filas cargadas |
| El buscador está arriba **y al día** | `dm meili_estado` | La tabla con los documentos de cada índice frente a la base. Sale con **código ≠ 0** si el servicio no responde o si algo está desfasado, que no da ningún otro síntoma: lo publicado se ve en su página y no aparece al buscarlo |
| La búsqueda usa Meilisearch **con la llave del navegador** | `curl -s -o /dev/null -w '%{http_code}\n' -X POST localhost:7700/multi-search -H "Authorization: Bearer $VITE_MEILI_SEARCH_KEY" -H 'Content-Type: application/json' -d '{"queries":[{"indexUid":"medidas","q":"cusco","limit":1}]}'` | **200**. Mide otra cosa que la fila anterior: un **403** es la llave del bundle caducada. `/api/buscar/estado/` dice `meili_disponible: true` igualmente, porque el backend consulta con la master key, y `/search/health` responde 200 sin credencial |
| El admin y el flujo editorial | entrar, crear una noticia, enviarla a revisión y publicarla | credenciales, permisos y avisos por correo (van a `logs -f worker`) |
| La ayuda memoria, **con su mapa** | `curl -so /tmp/am.pdf localhost:8000/api/distritos/080101/ayuda-memoria.pdf && grep -c '/Subtype /Image' /tmp/am.pdf` | **≥ 1**: WeasyPrint y la captura con Chromium. Descargar el PDF no basta — sale igual sin mapa, y así estuvo saliendo. El mapa es la única imagen rasterizada del documento |

Las cinco comprobaciones **manuales previas a la entrega** —más exigentes que estas— están en
[`_specs/08-plan-pruebas.md`](./_specs/08-plan-pruebas.md).

## 6. Probar

```bash
dc exec backend pytest                 # 144 pruebas, ~30 s
dc exec backend pytest -m lento        # 4 más: los Excel completos y el PDF con mapa

cd frontend && npm run lint            # tsc --noEmit
cd frontend && npm run build           # el build es parte de la verificación

./e2e/instalar-dependencias.sh         # una sola vez, en la raíz
npx playwright test                    # 56 E2E en escritorio y móvil
```

`pytest` corre **dentro del contenedor**, con las mismas versiones de GDAL, tippecanoe y WeasyPrint
que producción. Si responde `executable file not found`, ver §9.

**`instalar-dependencias.sh` sustituye al `npm install && npx playwright install chromium` que
había aquí**, porque ese par se dejaba fuera el paso que rompe: las librerías de sistema de
Chromium. En Debian/Ubuntu no se nota —`playwright install --with-deps` las instala solo—, pero en
RHEL/Rocky/Fedora **Playwright solo sabe de apt** y no instala nada, así que las 62 pruebas fallan
con `browserType.launch: Target page, context or browser has been closed`, que parece el sitio
caído y es una `.so` ausente. El script cubre los tres pasos y termina arrancando el navegador
para comprobarlo. Se ejecuta **como tu usuario, no con sudo**; da por hecho un servidor ya
provisionado con Docker y Node 22, y si falta algo avisa en vez de instalarlo.

Con el dev server recién arrancado conviene visitar las rutas una vez antes de lanzar Playwright:
Vite compila cada módulo la primera vez que se lo piden, y con varios navegadores en paralelo esa
compilación se lleva por delante el *timeout* de las peticiones.

```bash
for r in / /peligros /medidas /buscar /inversion; do curl -so /dev/null localhost:5173$r; done
```

## 7. Modo producción en local

El modo desarrollo no cubre cuatro cosas: que el bundle compilado se sirva bien, que las rutas del
router resuelvan por `try_files`, que los estáticos del admin estén donde nginx los busca, y que los
tiles salgan por rangos con sus cabeceras CORS. Para eso hay un tercer override, sobre HTTP y un
solo host:

```bash
# El .env de la raíz debe apuntar a http://localhost (ver .env.example)
docker compose -f compose.yaml -f compose.local.yml up -d --build
docker compose -f compose.yaml -f compose.local.yml run --rm frontend        # publica dist/
docker compose -f compose.yaml -f compose.local.yml exec backend \
  python manage.py collectstatic --noinput
```

Aquí **todo sale por el puerto 80**, como en producción: http://localhost el sitio,
`/api/`, `/api/docs/`, el admin, `/static/`, `/media/`, `/tiles/` y `/search/`. Ningún otro puerto
queda publicado.

Tres cosas que conviene saber de este modo:

- **Es fiel solo con `DEBUG=False`** en `backend/.env` (lo que trae el `.env.example`). En
  desarrollo, `compose.dev.yml` fuerza `DEBUG=True`; aquí no se fuerza nada, así que si tu
  `backend/.env` dice `True`, estás probando algo a medio camino.
- Con `DEBUG=False`, **`ALLOWED_HOSTS` tiene que contener el host que uses**. Trae `localhost`; si
  abres el sitio desde otra máquina de la red por IP, Django responde **400 Bad Request** hasta que
  añadas esa IP (y a `CSRF_TRUSTED_ORIGINS` para poder usar el admin).
- El login del admin **sí funciona** en `http://localhost` aunque las cookies sean `Secure`, porque
  el navegador considera `localhost` un origen de confianza. Sobre una IP de red sin HTTPS no
  funcionaría: la cookie de sesión se descarta y el login parece fallar sin decir por qué.

Es también la corrida de pruebas que más vale:

```bash
E2E_URL=http://localhost npx playwright test
```

**Encuentra fallos de integración que el modo desarrollo no puede ver**: en dev el navegador ataca a
Meilisearch directamente, así que un proxy `/search/` mal configurado es invisible. Ya pasó una vez.

## 8. Empezar de cero

```bash
dc down -v      # ⚠️ -v BORRA los volúmenes: base de datos, índices, media y tiles
dc up -d
dm seed --demo --capas --tiles
dm meili_setup  # reimprime la llave de búsqueda, que NO cambia con el reset
```

`down` sin `-v` conserva los datos; `down -v` los borra. Es la forma de comprobar que las
instrucciones de §1 funcionan en una máquina limpia — en un reset real tarda unos 50 s: 20 s en
levantar y 29 s en sembrar con tiles.

> **La llave de búsqueda ya no cambia con el reset.** Se deriva del uid fijo de la llave y de
> `MEILI_MASTER_KEY` (las llaves de Meilisearch son deterministas: `key` es el SHA-256 de las dos
> cosas), así que borrar el volumen la deja igual. Antes se creaba con uid aleatorio y **esto pasó de
> verdad**: tras un `down -v` el bundle se quedó con una llave inexistente y el buscador cayó al
> fallback de DRF, con las facetas de `/medidas` sin conteos y el autocompletado de lugares vacío.
>
> La llave **solo** cambia si cambias `MEILI_MASTER_KEY`. Y entonces va a **los dos** `.env`:
> `frontend/.env` para `npm run dev` y el **`.env` de la raíz** para el bundle compilado, que es lo
> que sirve nginx. Vite hornea las `VITE_*` en el build: hay que **reconstruir** el frontend, no
> reiniciarlo.

## 9. Cuando algo no arranca

| Síntoma | Causa y arreglo |
| --- | --- |
| `pytest: executable file not found` | La imagen de dev se reconstruyó sin el grupo `dev`, o el venv del volumen anónimo es el viejo: `dc up -d --build --renew-anon-volumes backend worker` |
| El visor sale sin capas | Los tiles no se generaron: `dm seed --capas --tiles`, y comprobar `/api/mapas/capas/` |
| El visor sale sin puntos | `/api/ccpp/geojson/` con los mismos filtros que manda la página; si devuelve `features: []`, el filtro está de más |
| El buscador no encuentra algo publicado | `dm meili_estado` para ver qué índice está desfasado, y `dm meili_rebuild` (o el botón de la tarjeta «Buscador» del panel del admin) |
| El sitio carga pero sin datos | `frontend/.env`: `VITE_API_URL` no apunta a `http://localhost:8000/api` |
| **403** al buscar, o el aviso «modo básico», o los filtros de `/medidas` sin conteos | La `VITE_MEILI_SEARCH_KEY` con la que se construyó el frontend no existe en Meilisearch. `dm meili_setup` y copiarla a **los dos** `.env` (`frontend/.env` y el de la raíz); si estás en modo producción local, además **reconstruir**: `docker compose -f compose.yaml -f compose.local.yml build frontend && … run --rm frontend`. La consola del navegador lo dice con todas las letras (`[buscador] Meilisearch rechazó la llave…`) |
| El admin da 404 | El prefijo es `ADMIN_URL`, no `/admin/`: mira `backend/.env` |
| «port is already allocated» | Otro proyecto ocupa 5432, 7700, 8000 o 80. `dc down` en el otro, o cambia el puerto publicado en `compose.dev.yml` |
| Un Excel no entra | Admin → Cargas de datos → el `log` de la carga, que cita hoja y fila |
| El PDF sale sin mapa | Degradación prevista: si la captura con Chromium falla, el documento se genera igual. El motivo está en `logs -f worker` |

## 10. Sin Docker en local (opcional)

Para iterar más rápido en el backend se puede correr `manage.py` desde el host, con la base y la
búsqueda todavía en contenedores:

```bash
cd backend && uv sync --all-groups
POSTGRES_HOST=localhost MEILI_URL=http://localhost:7700 .venv/bin/python manage.py shell
```

Sin esos dos, Django busca los hosts `db` y `meilisearch`, que solo existen dentro de la red de
Compose. **El pipeline de tiles y el PDF no funcionan así**: necesitan tippecanoe, GDAL y Chromium,
que viven en la imagen. Para un servidor entero sin contenedores, ver
[`_docs/despliegue-sin-docker.md`](./_docs/despliegue-sin-docker.md).

---

## Los datos

El seed es **idempotente** y no pisa lo que se haya editado, así que puede correrse en cada
despliegue sin devolverle a PREDES sus textos al valor de fábrica. Al terminar imprime los conteos;
si no coinciden con estos, algo se perdió por el camino:

| Dataset | Conteo | Origen |
| --- | ---: | --- |
| Provincias / distritos | 13 / 112 | INEI |
| Centros poblados | 8.968 | Excel SIGRID-CENEPRED + INEI |
| — con alguna clasificación | 3.238 | |
| — sin dato clasificado | 5.730 | |
| Clasificaciones de peligro | 10.978 | Excel SIGRID-CENEPRED |
| Frecuencias de emergencia | 644 (en 64 distritos) | Excel SIGRID-CENEPRED |
| Totales declarados (ADR-D1) | 104 (en 26 distritos) | |

**Dos unidades que no son intercambiables.** «Centros poblados por su nivel máximo» (3.238) y
«clasificaciones» (10.978) difieren en 3.4×, porque un centro poblado aporta una fila por cada
peligro evaluado. El API devuelve las dos rotuladas; usar la que no toca fue un error real del
prototipo, visible como un panel que decía 225 donde la tabla de al lado decía 75.

El seed también imprime **advertencias esperadas**: 229 filas del Excel sin `NIVEL_PELI`, 2 sin
`CODIGO`, **26 distritos que declaran subtotales sin desglosar**, **21 con fila pero sin ningún
dato** y Acomayo sin fila. No son fallos del importador sino calidad de los datos de origen, y están
anotadas en [`_specs/00-alcance-decisiones.md`](./_specs/00-alcance-decisiones.md) para
devolvérselas al cliente.

---

# Producción

Dos dominios en ambas vías, con CORS entre ellos:

| Dominio | Sirve |
| --- | --- |
| `observatorio.predes.org.pe` | La SPA compilada. Es lo que se difunde |
| `obs.predes.org.pe` | `/api/`, el admin, `/static/`, `/media/`, `/tiles/`, `/search/` |

## Qué vía elegir

| | **Docker Compose** (recomendada) | **Sin Docker** |
| --- | --- | --- |
| Base de datos | Contenedor PostgreSQL 16 + respaldo con rotación | **Servicio gestionado** (la contrata PREDES) |
| Backend | Contenedor con gunicorn | gunicorn bajo systemd |
| Búsqueda | Contenedor Meilisearch | Meilisearch bajo systemd |
| tippecanoe, GDAL, WeasyPrint, Chromium | Fijados en la imagen | Instalados en el servidor |
| Reproducibilidad | Alta: la imagen fija cada versión | A cargo de quien administra |
| Cuándo usarla | Por defecto: es la probada de punta a punta | Cuando no se pueda usar Docker, o la base ya sea un servicio contratado |
| Procedimiento | [`_docs/despliegue.md`](./_docs/despliegue.md) | [`_docs/despliegue-sin-docker.md`](./_docs/despliegue-sin-docker.md) |

## Con Docker Compose

```bash
git clone <repo> observatorio && cd observatorio
cp backend/.env.example backend/.env     # dominios reales, secretos, ADMIN_URL
cp .env.example .env                     # VITE_* con https://obs.predes.org.pe

# 1. Certificado, ANTES de levantar nginx (ver la nota de abajo). UNO SOLO con los dos dominios
#    como SAN: `--cert-name` fija el nombre de la lineage, que es de donde leen los DOS bloques
#    443. Sin él lo nombra el primer -d, y reordenar los argumentos rompe nginx.
docker compose run --rm --entrypoint certbot --publish 80:80 certbot certonly \
  --standalone --cert-name observatorio.predes.org.pe \
  -d observatorio.predes.org.pe -d obs.predes.org.pe \
  --email <correo> --agree-tos --no-eff-email

# 2. Todo arriba
docker compose up -d --build

# 3. Índices, llave de búsqueda y datos
docker compose exec backend python manage.py meili_setup      # imprime VITE_MEILI_SEARCH_KEY
docker compose exec backend python manage.py seed --capas --tiles

# 4. Reconstruir el frontend con la llave ya en el .env de la raíz, y publicarlo
docker compose build frontend && docker compose run --rm frontend

# 5. Lo del ANFITRIÓN, que no está en el repositorio y sin lo cual el sitio sirve pero no se
#    vigila, no se limpia y no agrega métricas: el techo del caché de Docker en
#    /etc/docker/daemon.json, la carpeta ~/observatorio-registros/ y seis tareas de cron.
#    Está entero, listo para pegar, en el paso 7 de _docs/despliegue.md.
```

> **El primer certificado se emite con `--standalone` y con nginx parado**, no por webroot. La
> configuración de nginx declara `ssl_certificate`, así que **nginx no arranca hasta que los
> certificados existen** —falla con `cannot load certificate`—, y sin nginx no hay quién sirva el
> reto de `/.well-known/acme-challenge/`. Certbot abre él mismo el puerto 80 para resolverlo. Las
> renovaciones posteriores sí van por webroot, con nginx ya en marcha: las hace solo el contenedor
> `certbot`.
>
> Y **`--entrypoint certbot` no es opcional**: el servicio trae un `entrypoint` con el bucle de
> renovación, de modo que sin sobreescribirlo los argumentos se ignoran y el comando se queda
> girando en el bucle sin emitir nada.

Incluye `nginx` con HTTPS, `certbot` renovando solo, y `pg_dump` diario con rotación 7/4/6 —
restauración probada y cronometrada en 3 s. El detalle, el runbook y el diagnóstico están en
[`_docs/despliegue.md`](./_docs/despliegue.md).

## Sin Docker, con base de datos gestionada

Mismo código y mismos dos dominios, sin contenedores: la base es un servicio gestionado, gunicorn y
Meilisearch corren bajo systemd, y nginx sirve la SPA compilada. Resumen:

```bash
# 1. Paquetes del sistema (WeasyPrint, GDAL, runtime de tippecanoe, nginx, certbot,
#    postgresql-client) y tippecanoe >= 2.17 compilado: no hay paquete en Debian ni en RHEL
# 2. Python 3.12+ y dependencias:  uv python install 3.12 && uv sync --no-dev
#    (Debian 12 trae Python 3.11, que NO sirve: el proyecto exige >= 3.12)
# 3. Meilisearch como servicio systemd, escuchando solo en 127.0.0.1:7700
# 4. La base gestionada: POSTGRES_HOST/PORT/... y PGSSLMODE=require en backend/.env
# 5. migrate + meili_setup + seed + collectstatic
# 6. Dos unidades systemd: gunicorn (:8000) y el worker de tareas
# 7. nginx con los dos server_name, y certbot para los certificados
# 8. Cron: agregación nocturna de métricas y pg_dump con rotación
```

El procedimiento completo —con los paquetes para Debian/Ubuntu **y** RHEL/Fedora, las unidades
systemd y la configuración de nginx listas para copiar, las comprobaciones posteriores y el
diagnóstico— está en
[`_docs/despliegue-sin-docker.md`](./_docs/despliegue-sin-docker.md).

## El tracker de errores, en `/gitea`

Un Gitea que **no forma parte de la plataforma**: es donde se anota todo lo que se encuentra probando
el sitio desplegado, para que no acabe repartido entre correos y mensajes. Corre como proyecto Compose
aparte, así que ni `docker compose up -d` ni `down` de la plataforma lo tocan.

Por defecto solo escucha en `127.0.0.1` y se llega por túnel (`ssh -L 3000:localhost:3000 …`).
Publicarlo bajo el dominio del API es opcional y explícito.

### Publicarlo en el servidor

**1.** Dos variables en el `.env` de la raíz:

```bash
# El nombre de la red del proyecto de la APLICACIÓN. No es igual en todas las máquinas: compose lo
# deriva del nombre del directorio. Comprobarlo antes con `docker network ls`.
RED_APP=observatorio_default
# La URL pública, CON la barra final. Gitea genera todos sus enlaces a partir de ella.
TRACKER_URL=https://obs.predes.org.pe/gitea/
```

**2.** Levantarlo con los dos archivos —el segundo es el que lo engancha al nginx del sitio— y
ejecutar el inicializador, que es idempotente:

```bash
docker compose -f compose.tracking.yaml -f compose.tracking-publicado.yml up -d
./deploy/gitea/inicializar.sh
```

**3.** Comprobar `https://obs.predes.org.pe/gitea/`. Para retirarlo, se levanta otra vez **sin** el
segundo `-f` y vuelve a quedar solo tras el túnel.

**No hace falta editar nginx, ni el DNS, ni el certificado.** La `location` de `/gitea` ya está en
`deploy/nginx/conf.d/observatorio.conf`, dentro del bloque del dominio del API, y por ser una subruta
del dominio que ya existe no necesita un registro ni un `-d` más en certbot. Con el tracker apagado,
`/gitea` responde 502 y **el resto del sitio sigue funcionando**: nginx resuelve su destino en cada
petición, así que la plataforma nunca depende del tracker.

Sí puede hacer falta **recargarlo**: si el bloque llegó en un `git pull` posterior al arranque del
contenedor, nginx aún no lo tiene y `/gitea` da **404** en vez de 502. `docker compose exec nginx
nginx -s reload` (§4).

### Las cuentas

`./deploy/gitea/inicializar.sh` **genera** el administrador la primera vez, con el patrón
`admin<NNN>` y contraseña `PREDES.<NNN>.<año>`, y lo escribe en **`deploy/gitea/admin.env`**, que git
ignora. Los valores reales no están en el repositorio ni en este README a propósito: se entregan
aparte, igual que las cuentas de Django (ver `_docs/despliegue-entorno-desarrollo.md`).

QA puede usar esa misma cuenta, o una propia creada a mano desde la web (*Administración → Usuarios*);
el registro abierto está deshabilitado.

> **Si se publica en internet, cambiar la contraseña generada por una de verdad.** El patrón es
> público y solo varían tres dígitos: son 900 combinaciones, y lo único que hay delante es el límite
> de 30 peticiones por minuto de nginx. En `deploy/nginx/conf.d/observatorio.conf` hay además un
> `allow`/`deny` por IP preparado y comentado. El volumen del tracker **tampoco entra en los
> backups**, que solo vuelcan PostgreSQL.

### Cómo se trabaja lo anotado

En el servidor, desde Claude Code en la raíz del repositorio:

```
/issue 6            un issue
/issue 6 3 1        varios; sale un solo plan que los cubre todos
/issue              lista los abiertos y se detiene, para elegir
```

Lee la ficha, plantea un plan, espera aprobación, escribe la prueba que falla, la hace pasar y
comenta en el issue qué lo demuestra. No commitea ni cierra: eso se revisa. Cerrar son **dos** gestos
—cerrar el issue y escribir la entrada `### Actualización DD/MM/AAAA` en la bitácora de
[`_specs/README.md`](./_specs/README.md)—, y esa entrada es lo que queda en el repositorio cuando
nadie levante el contenedor.

## Lo que depende de PREDES

Se implementó todo con valores por defecto seguros, y estas piezas quedan pendientes del cliente:
DNS de los dos dominios, credenciales SMTP (mientras tanto los correos van al log),
`GEMINI_API_KEY` (sin ella el resumen con IA se deshabilita con aviso), publicar el ejercicio de
Inversión —la importación lo deja oculto a propósito—, la fila de Acomayo, y sustituir OpenTopoMap
por una fuente de mapa base con licencia apta para producción.

---

## Documentación

| Quiero… | Ir a |
| --- | --- |
| Entender cómo encaja todo | [`_docs/arquitectura.md`](./_docs/arquitectura.md) |
| Levantarlo y trabajar en él | [`_docs/desarrollo.md`](./_docs/desarrollo.md) |
| Desplegarlo con Docker y operarlo | [`_docs/despliegue.md`](./_docs/despliegue.md) |
| Desplegarlo sin Docker | [`_docs/despliegue-sin-docker.md`](./_docs/despliegue-sin-docker.md) |
| Usar el API | [`_docs/api.md`](./_docs/api.md) |
| Administrar contenido (para PREDES) | [`_docs/manual-admin-predes.md`](./_docs/manual-admin-predes.md) |
| **Implementar algo** | [`_specs/`](./_specs/) — modelo de datos, contrato de API, ADR |
| Saber por qué se decidió algo | [`_specs/00-alcance-decisiones.md`](./_specs/00-alcance-decisiones.md) |
| **Ver qué está roto y pendiente** | El tracker — ver [El tracker de errores, en `/gitea`](#el-tracker-de-errores-en-gitea). El ciclo está en [`_specs/09-errores.md`](./_specs/09-errores.md) y lo ya corregido en la bitácora de [`_specs/README.md`](./_specs/README.md) |
| Ver el historial del prototipo | [`_specs/archive/`](./_specs/archive/) |

## Licencia y créditos

Operado por [PREDES](https://www.predes.org.pe/) — Centro de Estudios y Prevención de Desastres.

Fuentes de datos: SIGRID-CENEPRED, INEI, MEF, SENAMHI, INGEMMET, IGP, ANA, INAIGEM.
