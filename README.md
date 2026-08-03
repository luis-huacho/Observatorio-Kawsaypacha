# Observatorio Kallpachakuy

Plataforma web pública de PREDES para monitorear la **Gestión del Riesgo de Desastres (GRD)** y la
**Adaptación al Cambio Climático (ACC)** en la región Cusco, Perú.

> Contrato N°0362026/PREDES. En línea el **13/08/2026**. El prototipo aprobado vive en
> `prototype/` y está congelado como referencia visual; el trabajo activo es `backend/` +
> `frontend/`.

## Qué ofrece

| Ruta | Contenido |
| --- | --- |
| `/peligros`, `/peligros/:codigo` | Visor de exposición: 8.968 centros poblados sobre MapLibre, agrupados y dimensionados por población, con su nivel de peligro. Ficha por centro poblado y ayuda memoria imprimible |
| `/medidas`, `/medidas/:slug` | Medidas de adaptación con facetas |
| `/inversion` | Inversión PPR 0068 (a la espera del dato del cliente; la ruta tolera el estado vacío) |
| `/normativa`, `/normativa/:slug` | Normativa GRD/ACC con enlace a la publicación oficial y export Excel |
| `/recursos` | Biblioteca documental |
| `/noticias`, `/eventos`, `/videos` | Actualidad |
| `/comparar` | Comparativa entre distritos |
| `/buscar` | Búsqueda global con facetas (Meilisearch) |

## Stack

- **Backend** — Django 5.2 LTS + DRF + PostgreSQL 16 (sin PostGIS) + django-tasks (worker por BD,
  sin Redis) + admin con django-unfold. Gemini 2.5 Flash autocompleta resúmenes de PDF; siempre los
  revisa una persona antes de publicar.
- **Frontend** — Vite + React 18 + TypeScript + Tailwind 3 + react-router 6 + MapLibre GL.
- **Búsqueda** — Meilisearch, con llave *search-only* en el bundle del navegador.
- **Mapas** — capas de contexto (ríos, lagunas, glaciares) como PMTiles estáticos servidos con HTTP
  Range; los centros poblados llegan como GeoJSON desde el API.
- **Edge** — nginx + certbot en contenedor, sobre dos dominios.

## Mapa del repo

```
.
├── backend/           Django. `apps/` una carpeta por dominio; `config/` settings y urls
├── frontend/          Vite + React + TS. `src/lib/` capa de datos; `src/routes/` una por página
├── e2e/               Pruebas de extremo a extremo (Playwright)
├── deploy/nginx/      `conf.d/` producción · `local/` prueba local sobre HTTP
├── _specs/            Especificaciones y ADR — se leen ANTES de cambiar algo de fondo
├── _docs/             Documentación técnica y entregables (arquitectura, desarrollo, despliegue)
├── prototype/         Prototipo aprobado. CONGELADO: referencia visual, no se toca
├── data/              Excel y GeoJSON canónicos — NO se versionan (145 MB, los entrega PREDES)
├── compose.yaml       Base (= producción)
├── compose.dev.yml    Override de desarrollo
├── compose.local.yml  Override para probar el modo producción en local, sobre HTTP
├── Claude.md          Guía del proyecto para el agente
└── README.md          Este archivo
```

## Requisitos

- Docker y Docker Compose.
- Node 22 y npm, para el frontend en modo desarrollo.
- Los archivos de datos, que **no se versionan**: `data/layers/data/*.xlsx` y
  `data/layers/*.geojson`. Sin ellos el seed no tiene qué importar.
- Opcional: `uv` y Python 3.12+, si quieres correr `manage.py` desde el host.

## Primera vez

```bash
# 1. Configuración
cp backend/.env.example backend/.env     # secretos de Django (rellenar SECRET_KEY y contraseñas)
cp .env.example .env                     # variables de compose (dominios y VITE_*)
cp frontend/.env.example frontend/.env   # URLs que usa el frontend en dev

# 2. Levantar base, búsqueda, backend y worker
docker compose -f compose.yaml -f compose.dev.yml up -d --build

# 3. Sembrar: catálogos, datos reales de los Excel, contenido de demostración y tiles
docker compose -f compose.yaml -f compose.dev.yml exec backend \
  python manage.py seed --demo --capas --tiles

# 4. Copiar a frontend/.env la llave de búsqueda que imprime el paso anterior

# 5. El frontend, en el host
cd frontend && npm install && npm run dev
```

Con eso: **http://localhost:5173** el sitio, **http://localhost:8000/admin/** el admin,
**http://localhost:8000/api/docs/** el API.

El primer build de la imagen del backend tarda unos minutos porque **compila tippecanoe**. Es una
sola vez.

## El día a día

```bash
docker compose -f compose.yaml -f compose.dev.yml up -d      # arriba
docker compose -f compose.yaml -f compose.dev.yml down       # abajo
docker compose -f compose.yaml -f compose.dev.yml logs -f backend worker
docker compose -f compose.yaml -f compose.dev.yml exec backend python manage.py <comando>
```

Un alias ahorra teclear:

```bash
alias dc='docker compose -f compose.yaml -f compose.dev.yml'
alias dm='docker compose -f compose.yaml -f compose.dev.yml exec backend python manage.py'
```

Comandos propios: `seed` (con `--demo`, `--capas`, `--tiles`, `--solo-catalogos`), `meili_setup`,
`meili_rebuild`, `generar_tiles_ccpp`, `generar_tiles`.

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
| Frecuencias de emergencia | 644 | Excel SIGRID-CENEPRED |
| Totales declarados (ADR-D1) | 104 | |

**Dos unidades que no son intercambiables.** «Centros poblados por su nivel máximo» (3.238) y
«clasificaciones» (10.978) difieren en 3.4×, porque un centro poblado aporta una fila por cada
peligro evaluado. El API devuelve las dos rotuladas; usar la que no toca fue un error real del
prototipo, visible como un panel que decía 225 donde la tabla de al lado decía 75.

El seed también imprime **advertencias esperadas**: 229 filas del Excel sin `NIVEL_PELI`, 2 sin
`CODIGO`, 47 distritos que declaran subtotales sin desglosar y Acomayo sin fila. No son fallos del
importador sino calidad de los datos de origen, y están anotadas en
[`_specs/00-alcance-decisiones.md`](./_specs/00-alcance-decisiones.md) para devolvérselas al cliente.

## Pruebas

```bash
dc exec backend pytest                 # 112 pruebas, ~35 s
dc exec backend pytest -m lento        # 4 más: los Excel completos y el PDF con mapa
cd frontend && npm run lint            # tsc --noEmit
cd frontend && npm run build           # el build es parte de la verificación
npm install && npx playwright install chromium   # una sola vez, en la raíz
npx playwright test                    # 45 E2E contra el dev server
```

`pytest` corre **dentro del contenedor**, con las mismas versiones de GDAL, tippecanoe y WeasyPrint
que producción.

### La corrida que de verdad importa

```bash
docker compose -f compose.yaml -f compose.local.yml up -d --build
docker compose -f compose.yaml -f compose.local.yml run --rm frontend
E2E_URL=http://localhost npx playwright test
```

Contra el bundle compilado servido por nginx. **Es la que encuentra los fallos de integración**: en
desarrollo el navegador ataca a Meilisearch directamente, así que un proxy `/search/` mal
configurado es invisible hasta que el sitio se sirve como en producción. Ya pasó una vez.

## Despliegue

Servidor propio con Docker Compose, nginx + certbot para HTTPS y backups automáticos de PostgreSQL
(requisito 8 del TDR). Dos dominios: `observatorio.predes.org.pe` sirve la SPA y
`obs.predes.org.pe` el API, el admin, media, tiles y búsqueda, con CORS entre ambos.

Puesta en marcha, comprobaciones posteriores, runbook, backups y diagnóstico:
[`_docs/despliegue.md`](./_docs/despliegue.md).

## Documentación

| Quiero… | Ir a |
| --- | --- |
| Entender cómo encaja todo | [`_docs/arquitectura.md`](./_docs/arquitectura.md) |
| Levantarlo y trabajar en él | [`_docs/desarrollo.md`](./_docs/desarrollo.md) |
| Desplegarlo y operarlo | [`_docs/despliegue.md`](./_docs/despliegue.md) |
| Usar el API | [`_docs/api.md`](./_docs/api.md) |
| Administrar contenido (para PREDES) | [`_docs/manual-admin-predes.md`](./_docs/manual-admin-predes.md) |
| **Implementar algo** | [`_specs/`](./_specs/) — modelo de datos, contrato de API, ADR |
| Saber por qué se decidió algo | [`_specs/00-alcance-decisiones.md`](./_specs/00-alcance-decisiones.md) |
| Ver el historial del prototipo | [`_specs/archive/`](./_specs/archive/) |

## Licencia y créditos

Operado por [PREDES](https://www.predes.org.pe/) — Centro de Estudios y Prevención de Desastres.

Fuentes de datos: SIGRID-CENEPRED, INEI, MEF, SENAMHI, INGEMMET, IGP, ANA, INAIGEM.
