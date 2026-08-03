# 04 — Fase 1: Arquitectura Post-Validación

> Esta fase **solo se inicia tras la aprobación del prototipo** (cierre de [[01-prototipo-fase0]]). El alcance puede recortarse o expandirse según el feedback recibido.

## Cambios respecto a la fase 0

| Aspecto | Fase 0 | Fase 1 |
| --- | --- | --- |
| Backend | Ninguno | Django + DRF |
| BD | JSON estáticos | PostgreSQL + PostGIS |
| Auth | Ninguna | Django auth para admin; público libre |
| Datos mock | Toda la app | Solo donde no haya fuente real cargada |
| Despliegue | Estático (nginx) | Docker compose (api + db + nginx + frontend) |
| CI/CD | Build local | GitHub Actions: lint, test, build, deploy |

## Stack fase 1

| Capa | Elección |
| --- | --- |
| Backend | **Django 5 + Django REST Framework** |
| BD | **PostgreSQL 16 + PostGIS** (para geometrías y queries espaciales) |
| Tareas | **Celery + Redis** (scrapers, ingestas periódicas, generación de productos) |
| Frontend | El mismo de fase 0 (Vite + React + TS), apuntando ahora al API |
| Cliente HTTP | `ky` o `tanstack/query` para cache y revalidación |
| Auth admin | Django admin nativo + sesiones |
| Storage | Local en VPS (`/var/data/observatorio/`) para fase 1; S3-compatible si el volumen crece |
| Despliegue | **Docker Compose** en VPS, **nginx** reverse-proxy + TLS Let's Encrypt |
| Observabilidad | logs JSON + journald, Uptime Kuma para monitoreo simple |

## Modelo de datos (Postgres)

Tablas mínimas para el MVP backend. PostGIS habilitado.

### Geografía
```sql
provincia(id, nombre, ubigeo, geom GEOMETRY(MultiPolygon, 4326))
distrito(id, provincia_id, nombre, ubigeo, geom GEOMETRY(MultiPolygon, 4326))
centro_poblado(
  id BIGSERIAL,
  codigo_inei VARCHAR(10) UNIQUE,
  distrito_id INT REFERENCES distrito,
  nombre,
  categoria,
  altitud INT,
  poblacion INT,
  geom GEOMETRY(Point, 4326)
)
```

### Peligros y riesgo
```sql
tipo_peligro(id, codigo, nombre, descripcion)  -- 9 tipos del Excel
peligro_ccpp(
  id, centro_poblado_id, tipo_peligro_id,
  subtipo, nivel SMALLINT CHECK (nivel BETWEEN 1 AND 4),
  fuente_id, fuente_url, anio_dato,
  created_at, updated_at
)
fuente(id, nombre, sigla, url_base)  -- SIGRID, INGEMMET, IGP, etc.
```

### Inversión PPR 0068
```sql
ejercicio_presupuestal(id, anio)
entidad_ejecutora(id, tipo, ubigeo, nombre)
inversion_ppr0068(
  id, ejercicio_id, entidad_id,
  pia NUMERIC(15,2), pim NUMERIC(15,2),
  devengado NUMERIC(15,2),
  clasificacion VARCHAR  -- 'prevencion' | 'respuesta' | 'mixto'
)
actividad_inversion(
  id, inversion_id, nombre, monto, etapa, fuente
)
```

### Medidas / casos
```sql
medida(
  id, titulo, slug UNIQUE,
  peligro_id, ambito,  -- comunal/distrital/regional
  resultado,           -- exito/leccion/mal_adaptacion
  ubigeo_distrito, comunidad,
  resumen_corto, contenido_md,
  video_url, imagen,
  publicado BOOLEAN, fecha_publicacion
)
medida_tag(medida_id, tag)
```

### Normativa
```sql
norma(
  id, titulo, tipo,    -- Ley, DS, RM, RJ, Ordenanza
  ambito,              -- nacional/regional/local
  fecha, url_oficial,
  resumen, analisis_predes,
  publicado, fecha_publicacion
)
```

### Editorial (gobernanza interna)
```sql
usuario (Django auth)
rol(id, nombre)  -- editor, revisor, admin
contenido_borrador(
  id, tipo_contenido,  -- 'medida' | 'norma'
  payload JSONB,
  estado,              -- 'borrador' | 'en_revision' | 'aprobado' | 'rechazado'
  creado_por, revisado_por,
  comentarios_revision
)
```

## API REST (esqueleto)

| Endpoint | Método | Uso |
| --- | --- | --- |
| `/api/ccpp/` | GET | Lista paginada + filtros |
| `/api/ccpp/:codigo/` | GET | Detalle con todos sus peligros |
| `/api/peligros/?distrito=&tipo=&nivel=` | GET | Tabla larga filtrable |
| `/api/peligros/coropleta/?nivel_admin=distrito` | GET | Agregado para mapa coroplético |
| `/api/medidas/?peligro=&ambito=` | GET | Casos publicados |
| `/api/medidas/:slug/` | GET | Detalle de caso |
| `/api/inversion/?anio=&ubigeo=` | GET | Tablero PPR 0068 |
| `/api/normativa/?tipo=&anio=` | GET | Repositorio |
| `/api/prioridades/?pesos=...` | GET | Calcula scoring multicriterio en server |
| `/api/buscar/?q=` | GET | Búsqueda global (Postgres full-text) |
| `/admin/` | GET (auth) | Django admin para edición |

Sin auth pública. Throttling con `django-ratelimit` (60 req/min por IP).

## Ingesta de datos

Comandos `manage.py` para cargar/refrescar:

```
python manage.py importar_ccpp data/Base_Nivel\ Peligro_CCPP_Cusco.xlsx
python manage.py importar_geometrias data/geo/cusco-distritos.shp
python manage.py importar_inversion --anio 2025 --csv data/mef-0068-2025.csv
```

**Scrapers (fase 1.5)**: tareas Celery programadas con `django-celery-beat`. Ej.: cada noche traer Consulta Amigable MEF para el PPR 0068 de los ubigeos de Cusco.

Cada ingesta corre dentro de una transacción y registra metadata en una tabla `import_log(id, fuente, fecha, filas_creadas, filas_actualizadas, errores JSONB)`.

## Despliegue (VPS)

```
vps/
├── docker-compose.yml      # api, postgres, redis, nginx, frontend
├── .env                    # secretos (gitignored)
├── nginx/
│   └── observatorio.conf
└── scripts/
    ├── backup-db.sh        # cron diario → /var/backups/
    └── restore-db.sh
```

**Recursos mínimos:** 2 vCPU, 4 GB RAM, 40 GB SSD. (~$10-20/mes Hetzner CX22 o equivalente.)

**Dominio sugerido:** `observatorio.predes.org.pe` (a confirmar con PREDES). HTTPS con Let's Encrypt vía `certbot`.

**Backups:**
- DB: `pg_dump` diario, retención 14 días, copia semanal off-site (Backblaze B2 o similar).
- Media (imágenes/videos): rsync diario al backup.

## Seguridad

- Django `SECRET_KEY` en `.env`, nunca commiteado.
- HTTPS obligatorio.
- CORS restringido al dominio del frontend.
- `DEBUG=False` en producción.
- Admin en URL no-default (`/_admin/` o similar).
- Rate-limit en endpoints públicos.
- Logs sin PII (no hay PII de usuarios públicos; admin sí tiene sesiones).

## Observabilidad

- Logs JSON estructurados (Django logging config).
- `django-health-check` expuesto en `/healthz/`.
- Uptime Kuma externo apuntando a `/healthz/` y a la portada.
- Alertas a Slack/Telegram del equipo PREDES.

---

**Documentos relacionados:** [[03-datos-mock]], [[05-roadmap]]
