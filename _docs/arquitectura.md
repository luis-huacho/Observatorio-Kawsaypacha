# Arquitectura del Observatorio Kallpachakuy

Vista de conjunto de la plataforma: qué piezas hay, por qué están y dónde mirar cuando algo
falla. Las decisiones con su razonamiento completo viven en `_specs/00-alcance-decisiones.md`
(los ADR); aquí se resumen y se conectan.

## En una imagen

```
                    observatorio.predes.org.pe          obs.predes.org.pe
                              │                                │
                              ▼                                ▼
                    ┌───────────────────────────────────────────────────┐
                    │  nginx  (:80/:443, certbot renueva los certs)     │
                    └───────┬───────────────────┬───────────────┬───────┘
                       dist/│         /api/ /loginseguro/       │ /tiles/ /media/ /static/
                            │                   │               │
                     ┌──────▼─────┐      ┌──────▼──────┐  ┌─────▼──────────┐
                     │  SPA React │      │  gunicorn   │  │ volumen media  │
                     │  (estática)│      │  Django 5.2 │  │  + static      │
                     └────────────┘      └──┬───────┬──┘  └────────────────┘
                                            │       │
                              ┌─────────────▼─┐   ┌─▼──────────────┐
                              │ PostgreSQL 16 │   │  Meilisearch   │
                              └───────────────┘   └────────────────┘
                                            ▲
                                    ┌───────┴────────┐
                                    │  worker        │  importaciones de Excel,
                                    │  (django-tasks)│  tiles, PDF, correos,
                                    └────────────────┘  Gemini, métricas
```

## Los dos dominios (ADR-A14)

| Dominio | Sirve |
|---|---|
| `observatorio.predes.org.pe` | La SPA compilada. Es lo que se difunde |
| `obs.predes.org.pe` | `/api/`, el admin, `/static/`, `/media/`, `/tiles/`, `/search/` |

Separar el backend del dominio público deja el admin y el API fuera de lo que se publica, y
permite mover uno sin tocar el otro. **El coste es CORS**: el navegador habla con dos orígenes.
Eso tiene tres consecuencias que conviene tener presentes al depurar:

1. `django-cors-headers` con allowlist (`CORS_ALLOWED_ORIGINS` en `backend/.env`).
2. nginx pone las cabeceras CORS de `/media/` y `/tiles/`, que Django no sirve.
3. Los tiles necesitan además `Accept-Ranges` y `Access-Control-Expose-Headers` con
   `Content-Range`: el protocolo `pmtiles://` lee el archivo por trozos, y sin poder leer la
   respuesta parcial el visor se queda sin capas.

**`BACKEND_URL` es la URL con la que el navegador alcanza al backend**, no una dirección interna:
el API la usa para construir las URL absolutas de tiles y media que devuelve a la SPA. Si
apunta a un sitio que el navegador no puede alcanzar, el visor pide tiles a un puerto cerrado
mientras el resto del sitio funciona con normalidad.

## Datos: de los Excel a la pantalla

```
data/layers/                    manage.py seed / admin (DatasetUpload)

  Base_Nivel Peligro…xlsx   ──▶  importers/nivel_peligro.py  ──▶  CentroPoblado (8,968)
                                                             └─▶  ClasificacionPeligro (10,978)

  Base_Frecuencia…xlsx      ──▶  importers/frecuencia.py     ──▶  FrecuenciaEmergencia (644)
                                                             └─▶  TotalDeclarado… (104)

  rios/lagos/glaciares.geojson ─▶ mapas/pipeline.py          ──▶  media/tiles/*.pmtiles
                                  (ogr2ogr + tippecanoe)
```

Las dos primeras filas son **ejes distintos y no se mezclan**: el de arriba es *exposición*
(a qué está expuesto cada centro poblado, 9 peligros) y el de abajo *ocurrencia* (qué emergencias
se registraron en cada distrito, 21 tipos de evento). Sus taxonomías no se convierten entre sí
—`INCENDIO FORESTAL` es «inducido por acción humana» en una y «meteorológico» en la otra—, y
`/peligros` publica solo la primera (ADR-A17).

El camino del admin y el del seed son **el mismo código**. Es deliberado: si el seed funciona,
el camino que recorrerá PREDES al subir su Excel también, y no hay un segundo importador que se
quede atrás.

Tres cifras que conviene memorizar, porque son el termómetro de que los datos están bien:

- **8,968** centros poblados, de los que solo **3,238** tienen alguna clasificación.
- **10,978** clasificaciones de peligro.
- **644** registros de frecuencia en 64 distritos, más **104** totales declarados sin desglose.

«Sin dato» no es «nivel bajo». Los 5,730 centros poblados sin clasificar se pintan en gris y se
cuentan aparte en todos los agregados: la ausencia de información es en sí misma un argumento
de incidencia, y colapsarla con «bajo riesgo» sería falsear el dato.

## Apps de Django

| App | Qué contiene |
|---|---|
| `core` | Mixins (`TimeStamped`, `Workflow`), tareas comunes, saneado de HTML, panel del admin, semilla |
| `territorio` | Provincia, Distrito, CentroPoblado |
| `peligros` | Catálogo de peligros y eventos, clasificaciones, frecuencias, totales declarados, agregados |
| `datasets` | `DatasetUpload` y los importadores de Excel |
| `medidas`, `normativa`, `biblioteca`, `contenidos` | Contenido editorial, todo con flujo de publicación |
| `sitio` | Configuración, textos, hero y menú administrables |
| `mapas` | Capas cartográficas y el pipeline de tiles |
| `metricas` | Eventos de uso y su agregado diario |
| `informes` | Ayuda memoria PDF y el visor que se captura para su mapa |
| `api` | Serializers, filtros y vistas. Sin modelos |

La app **`inversion`** (ADR-D4) modela el PP 0068 **por entidad ejecutora**, no por distrito: quien
tiene PIA, PIM y devengado es la municipalidad. Guarda el detalle por actividad y calcula el
reparto por procesos de la GRD al vuelo, contra un catálogo editable en el admin, de modo que
corregir una clasificación se ve en la web sin reimportar ni recalcular nada. Mientras ningún
ejercicio esté marcado `visible`, `/api/inversion/` responde `{"disponible": false}` y el frontend
muestra su estado vacío.

## Búsqueda

El navegador consulta **Meilisearch directamente** con una llave *search-only* (ADR-A4), sin
pasar por Django: así las facetas y la tolerancia a errores de tecleo no requieren código de
servidor. La llave es segura por diseño —solo busca, y solo en los índices públicos— y la master
key nunca sale del backend.

Si Meilisearch no responde, el frontend cae a `/api/buscar/`, que devuelve la misma forma sin
facetas. El fallback existe porque el buscador es la puerta de entrada al contenido: un sitio que
responde «no se pudo buscar» se lee como roto, no como degradado.

Los índices se sincronizan por **dos mecanismos a la vez**: señales `post_save`/`post_delete`
para el día a día y `manage.py meili_rebuild` para recuperación. Solo con señales, cualquier
escritura fuera del ORM —un import masivo, un `update()` de queryset— desincronizaría el índice
sin manera de notarlo.

## El visor

La capa de centros poblados **no** sale de un tile vectorial, a diferencia del resto: se pidió
clustering con símbolos proporcionales a la población, y MapLibre solo agrupa fuentes `geojson`
(ADR-A13). Viene de `/api/ccpp/geojson/`, que devuelve el padrón filtrado — 3.3 MB en crudo,
~314 KB con gzip. Ríos, lagunas y glaciares sí son PMTiles.

Las capas de contexto salen de `/api/mapas/capas/` con su estilo y su orden: PREDES sube un
GeoJSON nuevo, regenera los tiles desde el admin y el visor lo dibuja **sin que nadie despliegue
nada**. Es el requisito de reemplazo de capas del TDR.

## Tareas en segundo plano

Cola en la propia base de datos (`django-tasks`, ADR-A3): sin broker extra. El contenedor
`worker` la procesa. Ahí viven las importaciones de Excel, la generación de tiles, los resúmenes
con Gemini, los correos del flujo editorial y la agregación nocturna de métricas.

Regla transversal: **nada de esto puede tumbar la operación que lo disparó**. Un SMTP caído no
impide publicar, un fallo de Gemini no deja un documento sin guardar, y un Meilisearch ausente no
impide editar contenido.

## Dónde mirar cuando algo falla

| Síntoma | Primer sitio |
|---|---|
| El visor sale sin capas | `/api/mapas/capas/` (¿`estado_tiles=ok`?) y las cabeceras de `/tiles/` |
| El visor sale sin puntos | `/api/ccpp/geojson/` y los filtros que manda la página |
| Una capa no se genera | Admin → Capas cartográficas → `log_error` de la capa |
| Un Excel no entra | Admin → Cargas de datos → el `log`, que está escrito para leerse |
| No llegan los correos | Log del `worker`, y que los usuarios del grupo tengan correo |
| El buscador no encuentra algo publicado | `manage.py meili_rebuild` |
| 502 tras un despliegue | El resolver de nginx (ver `deploy/nginx/conf.d/observatorio.conf`) |

## Documentos hermanos

- **`desarrollo.md`** — levantar el entorno, sembrar datos, correr pruebas.
- **`despliegue.md`** — VPS, DNS, certificados, runbook y backups.
- **`manual-admin-predes.md`** — cómo se administra la plataforma, para el equipo de PREDES.
- **`api.md`** — el contrato del API y cómo explorarlo.
- **`_specs/`** — las especificaciones y los ADR con el razonamiento completo.
