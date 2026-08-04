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
`.env.example` trae `gestion/`, así que copiándolo tal cual el admin está en `/gestion/` y no en
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
dc exec backend pytest                 # 118 pruebas, ~28 s (sin las lentas)
dc exec backend pytest -m lento        # 4 más: los Excel completos y el PDF con mapa
cd frontend && npm run lint            # tsc --noEmit
cd frontend && npm run build           # el build es parte de la verificación
npm install && npx playwright install chromium   # una sola vez, en la raíz
npx playwright test                    # 56 E2E en escritorio y móvil
```

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
deploy/nginx/     `conf.d/` producción, `local/` prueba local sobre HTTP
data/             Excel y GeoJSON canónicos. NO se versionan
```
