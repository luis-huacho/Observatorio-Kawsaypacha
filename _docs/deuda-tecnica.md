# Deuda técnica

Cosas que sabemos que hay que hacer y que **no** están rotas hoy: el sitio funciona con ellas
pendientes. No es el registro de errores — eso vive en el tracker y su ciclo está en
[`_specs/09-errores.md`](../_specs/09-errores.md).

Cada punto lleva el archivo y la línea, para que se pueda retomar sin repetir la investigación.

> Estas entradas nacieron el 27/08/2026, al descubrir por qué la suite E2E completa no podía pasar.
> El tracker (Gitea) estaba inaccesible ese día, así que se anotaron aquí. **Conviene pasarlas a
> issues cuando el tracker vuelva.**

---

## 1. El techo anónimo del API va corto para producción

`backend/config/settings.py` — `anon: 1000/hour` por IP.

La portada dispara **8 peticiones** por carga, así que el techo son **125 vistas de página por hora
y por IP**. El detalle que lo vuelve un problema real: **una oficina entera detrás de un NAT comparte
una sola IP**. Treinta personas en un taller tienen ~4 vistas cada una antes de empezar a recibir
429.

No es una hipótesis: es exactamente el escenario que el comentario de ese mismo bloque ya describe
para el beacon de métricas, donde se resolvió subiendo la tasa a `600/min`. Quedó resuelto para el
beacon y pendiente para el resto del API.

Desde el 27/08/2026 las tres tasas se leen del entorno (`API_THROTTLE_ANON`, `API_THROTTLE_DESCARGA`,
`API_THROTTLE_BEACON`), con los valores de hoy como defecto — así que **subir el techo ya no exige
tocar código**, solo decidir la cifra. Lo que falta es decidirla.

Ojo también con `descarga: 30/hour`, que es la más justa de las tres.

## 2. Cinco de los siete endpoints de la portada no mandan cabecera de caché

Sin `Cache-Control`: `/peligros/resumen/`, `/territorio/distritos/`, `/medidas/`, `/noticias/`,
`/normativa/`. Solo llevan `cache_control(max_age=300, public=True)`:

- `backend/apps/api/views/sitio.py:24` — `/api/sitio/`
- `backend/apps/api/views/inversion.py:84` y `:210`

Y el más caro está entre los descubiertos: **`/peligros/resumen/` hace dos pasadas completas sobre
los 8.968 centros poblados** (`backend/apps/peligros/consultas.py:57-97`), con un bucle en Python por
medio, en cada carga de la portada.

`/territorio/distritos/` es el otro candidato obvio: `pagination_class = None`, o sea los 112
distritos serializados enteros, para un catálogo que no cambia nunca.

## 3. No hay caché de servidor en ningún nivel

- **`CACHES` no está configurado** en `settings.py`. Django cae a `LocMemCache`.
- No hay `cache_page`, ni middleware de caché, ni `from django.core.cache` en `backend/apps/`.
- En nginx, la zona `proxy_cache_path` de `deploy/nginx/conf.d/observatorio.conf:23` **está declarada
  y no se usa en ningún `location`**. `location /api/` es un `proxy_pass` desnudo.

Consecuencia adicional, y poco intuitiva: **el contador del throttle vive en esa caché**, así que es
por proceso. Con varios workers de gunicorn el límite efectivo es N × la tasa, y es inconsistente
entre ellos. Efecto lateral útil mientras tanto: reiniciar el backend borra los 429 al instante.

## 4. La portada podría pedir bastante menos

Tres de las cuatro cifras se bajan un payload entero para leer un número:

- `/territorio/distritos/` → los 112 distritos, para hacer `.length` (`Home.tsx:45`)
- `/medidas/?page_size=1&resultado=exito` → paga el `COUNT(*)` de la paginación para leer `.count`
- `/inversion/` → un agregado caro, para un solo campo (`entidades_con_devengado`)

Además `/medidas/` se pide **dos veces** con parámetros distintos.

El patrón para arreglarlo ya existe en el repo y está bendecido: `/api/sitio/`, cuyo docstring
(`backend/apps/api/views/sitio.py:17-22`) explica por qué se sirve todo el cascarón en una sola
petición cacheada en vez de partirlo en cuatro. Nadie lo aplicó a `Home`. Un `/api/portada/` con
`cache_control` reduciría de 8 peticiones a 2 o 3.

## 5. Un 429 se reintenta en bucle y realimenta el propio límite

`frontend/src/lib/api.ts` **borra de la caché las peticiones fallidas a propósito** (líneas 98-99 y
149-151), para que un fallo transitorio pueda reintentarse en el siguiente montaje. Correcto en
general, pero no distingue el 429 ni aplica ningún backoff: `ErrorApi.status` se guarda (línea 67) y
**nadie lo consulta** — cero apariciones de `429` o `Retry-After` en todo `frontend/src`.

El resultado es que, una vez agotada la cuota, cada vuelta a la portada relanza las 8 peticiones y
alimenta el límite que la está bloqueando. Faltaría respetar `Retry-After` o, como mínimo, no
reintentar en el mismo montaje.

## 6. `home.spec.ts` busca una tarjeta que la portada ya no tiene

`e2e/home.spec.ts:19` — la prueba «las cifras salen del API y coinciden con el resumen» localiza
`page.getByText("Centros poblados monitoreados")` y comprueba que su número sea `resumen.total_ccpp`.

Esa tarjeta **no existe**. Las cuatro de la portada son «Distritos cubiertos», «Centros poblados
con peligro alto/muy alto», «Experiencias exitosas» y «Municipios con presupuesto ejecutado»
(`frontend/src/routes/Home.tsx:142-145`). El commit `0e216c3` (18/08/2026, «pagina02: completado»)
rehízo las cifras y la prueba se quedó con las viejas.

Ojo con el parecido: «Centros poblados con peligro alto/muy alto» **no** satisface al localizador,
que busca «Centros poblados monitoreados» como subcadena. Sigue en rojo.

Lleva rota desde entonces sin que se notara, tapada primero por la carrera de `esperarApi` —que la
hacía morir antes de llegar a esta línea— y después por los 429. Es **el único fallo real** que
apareció al despejar el ruido.

No es solo renombrar el texto: la portada **dejó de publicar el total de centros poblados**, así que
hay que decidir qué debe demostrar la prueba. Lo más fiel a su intención («las cifras vienen del API
y cuadran») es afirmar sobre «CCPP con peligro alto/muy alto» contra la suma de los niveles 3 y 4 de
`/api/peligros/resumen/`, que es justo lo que `Home.tsx:55-57` calcula.

## 7. Las E2E del visor agotan el tiempo en el proyecto móvil

Primera corrida completa con el throttling ya desactivado (27/08/2026, contra el dev server de
Vite): **93 pasan, 13 fallan, 6 se saltan**, y **cero respuestas 429** en toda la corrida — el
problema del techo está cerrado.

De los 13 fallos, 2 son el punto 6 (la prueba obsoleta). Los **11 restantes se concentran en el
proyecto `movil`** —10 de `peligros.spec.ts` y 1 de `buscar.spec.ts`— y **9 agotan exactamente los
60 s de tiempo límite**. Son las pruebas caras: el visor con MapLibre, ~3 MB de GeoJSON y los tiles
por rangos, emulando un Pixel 5.

**No está atribuido**, y conviene no darlo por ambiental sin comprobarlo. La sospecha razonable es
la que advierte el propio `playwright.config.ts`: contra el dev server, Vite compila cada módulo la
primera vez que se lo piden y con varios navegadores en paralelo esa compilación se lleva por
delante los tiempos de espera. Lo que zanja la duda es correr la suite **como manda la
documentación**, contra el bundle compilado:

```
docker compose -f compose.yaml -f compose.local.yml up -d --build
E2E_URL=http://localhost npx playwright test
```

Si ahí pasan, es saturación del entorno de desarrollo y basta con documentarlo. Si fallan igual, hay
algo real en el visor móvil.
