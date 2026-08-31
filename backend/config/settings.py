"""Settings del Observatorio Kallpachakuy.

Toda la configuración sensible o dependiente del entorno se lee de
variables de entorno / backend/.env (django-environ). Ver .env.example.
"""
from pathlib import Path

import environ
from django.urls import reverse_lazy

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY", default="inseguro-solo-para-collectstatic")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")

# URL pública del sitio (correos, sitemaps) y prefijo del admin.
SITE_URL = env("SITE_URL", default="http://localhost:5173")
# Dominio del backend (ADR-A14). Es la base de las URL absolutas que el API devuelve para
# media y tiles: la SPA vive en otro origen y una ruta relativa apuntaría al sitio público.
BACKEND_URL = env("BACKEND_URL", default="http://localhost:8000")
# ¿Es este despliegue el sitio canónico? En `0`, `/robots.txt` prohíbe el rastreo entero.
# Existe porque el entorno de desarrollo sirve el MISMO contenido en otro dominio y se
# autocanonicaliza: el día que el dominio definitivo entre en el aire habrá dos copias idénticas
# compitiendo por las mismas búsquedas, y quién sobrevive lo decide Google. Hoy va en `1` a
# propósito —el dominio definitivo todavía no resuelve y apagarlo dejaría el observatorio
# invisible—; se pone en `0` en el .env del entorno de desarrollo el día del cambio.
SITIO_INDEXABLE = env.bool("SITIO_INDEXABLE", default=True)
ADMIN_URL = env("ADMIN_URL", default="admin/")
# Sin esto, entrar al admin sin `?next=` aterriza en /accounts/profile/, que no existe: el
# editor ve un 404 justo después de escribir bien su contraseña.
LOGIN_REDIRECT_URL = f"/{ADMIN_URL}"
LOGIN_URL = f"/{ADMIN_URL}login/"

INSTALLED_APPS = [
    # Theme del admin: debe ir antes de django.contrib.admin.
    "unfold",
    "unfold.contrib.filters",
    "unfold.contrib.forms",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Terceros
    "rest_framework",
    "django_filters",
    "drf_spectacular",
    "django_tasks",
    "django_tasks_db",
    "corsheaders",
    "django_ckeditor_5",
    # Apps del proyecto
    "apps.core",
    "apps.territorio",
    "apps.peligros",
    "apps.inversion",
    "apps.datasets",
    "apps.medidas",
    "apps.normativa",
    "apps.biblioteca",
    "apps.contenidos",
    "apps.sitio",
    "apps.mapas",
    "apps.metricas",
    "apps.informes",
    "apps.api",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # CorsMiddleware va lo más arriba posible: tiene que poder responder al preflight
    # antes de que cualquier otro middleware decida redirigir o rechazar.
    "corsheaders.middleware.CorsMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", default="observatorio"),
        "USER": env("POSTGRES_USER", default="observatorio"),
        "PASSWORD": env("POSTGRES_PASSWORD", default=""),
        "HOST": env("POSTGRES_HOST", default="db"),
        "PORT": env("POSTGRES_PORT", default="5432"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es-pe"
TIME_ZONE = "America/Lima"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# Estáticos del proyecto (no de una app): el logo que incrusta WeasyPrint y las copias de
# MapLibre y pmtiles que usa el visor del PDF. Django solo autodescubre `<app>/static/`, así
# que sin esto el navegador headless recibía 404 y el mapa nunca llegaba a dibujarse.
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# Dónde está el `index.html` COMPILADO de la SPA. Lo usa `apps.sitio.vistas_html` para servir las
# fichas con sus metas Open Graph ya puestas, y tiene que ser el bundle real —no una plantilla—
# porque los nombres de los assets llevan hash y cambian en cada build. En producción es el volumen
# `web_dist` que llena el servicio `frontend`; en desarrollo no existe y esas rutas las sirve Vite.
SPA_DIST_DIR = Path(env("SPA_DIST_DIR", default=str(BASE_DIR / "spa_dist")))

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- DRF -------------------------------------------------------------------
# Tasas del throttling del API.
#
# `THROTTLE_PRODUCCION` es la fuente de verdad de los valores del servicio, y hay una prueba que
# los fija (`test_las_descargas_estan_limitadas`): son un ajuste de producto, no un detalle de
# despliegue, y cambiarlos a la ligera es cómo se abre un agujero o se corta a los visitantes.
#
# Cada tasa se puede sustituir por su variable de entorno, y **vaciarla la desactiva** (cadena
# vacía -> `None`, que es como DRF entiende «sin límite»). Eso es cosa de desarrollo:
# `compose.dev.yml` las vacía las tres. En producción no se define nada y rige lo de aquí abajo.
#
# Hizo falta porque el throttling se aplicaba **igual en desarrollo que en producción**, y la
# suite E2E no cabe en la cuota: 56 casos x 2 proyectos = 112 corridas, cada una con caché de
# navegador fría —Playwright abre un contexto nuevo por prueba— y la portada sola pide 8 veces.
# Son ~1.100 peticiones contra 1.000, así que a mitad de suite todo empezaba a responder 429. Y
# un 429 no se parece a un límite: se parece a un sitio caído, porque la prueba solo ve que los
# datos no llegan y agota su espera igual que si el backend estuviera muerto.
THROTTLE_PRODUCCION = {
    "anon": "1000/hour",
    # Los exports y el PDF cuestan mucho más que una lectura: un bucle de descargas
    # tumbaría el worker antes que el API.
    "descarga": "30/hour",
    # 60/min era demasiado poco: **toda una oficina detrás de un NAT comparte IP**, y un
    # taller con treinta personas navegando pasa de 60 vistas por minuto sin esfuerzo. Lo
    # descubrieron las pruebas E2E, que desde una sola IP empezaron a recibir 429 en la
    # consola del navegador. Cada beacon es un INSERT, así que el techo puede ser alto y
    # seguir sirviendo para lo que es: cortar a un cliente roto o a quien infle las cifras.
    "beacon": "600/min",
}

THROTTLE_RATES = {
    ambito: env(f"API_THROTTLE_{ambito.upper()}", default=defecto) or None
    for ambito, defecto in THROTTLE_PRODUCCION.items()
}

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
    "DEFAULT_PAGINATION_CLASS": "apps.api.paginacion.PaginacionEstandar",
    "PAGE_SIZE": 50,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.AnonRateThrottle"],
    "DEFAULT_THROTTLE_RATES": THROTTLE_RATES,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "API Observatorio Kallpachakuy",
    "DESCRIPTION": "API pública de solo lectura del Observatorio GRD y ACC de Cusco.",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}

# --- CORS (ADR-A14: la SPA y el API viven en dominios distintos) ------------
CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:4173"],
)
CORS_ALLOW_CREDENTIALS = False
# El nombre del archivo viaja en `Content-Disposition`, y un `fetch` cross-origin **solo lee las
# cabeceras que el servidor autoriza**. La interfaz pide las descargas con `fetch` —para poder
# enseñar que está generando y explicar un 429 en vez de abrir una pestaña con JSON crudo—, así
# que sin esto todos los archivos se guardarían con el nombre del blob: un identificador
# aleatorio y sin extensión. No rompe nada al faltar, solo pierde el nombre.
CORS_EXPOSE_HEADERS = ["Content-Disposition"]

# --- Admin (django-unfold, ADR-A8) -----------------------------------------
# El sidebar reproduce los seis grupos del spec 03. El orden no es alfabético: es el orden en
# que PREDES trabaja — primero lo que revisa a diario (contenido), luego los datos, y al final
# la configuración, que se toca una vez.
UNFOLD = {
    "SITE_TITLE": "Observatorio Kallpachakuy",
    "SITE_HEADER": "Observatorio Kallpachakuy",
    "SITE_SUBHEADER": "PREDES · GRD y ACC · Región Cusco",
    "SITE_URL": SITE_URL,
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": False,
    "DASHBOARD_CALLBACK": "apps.core.dashboard.datos_panel",
    "LOGIN": {"image": lambda request: None},
    "COLORS": {
        # Verde institucional de predes.org.pe. Unfold espera los canales RGB sueltos.
        "primary": {
            "50": "229 244 238", "100": "229 244 238", "200": "199 230 214",
            "300": "150 209 181", "400": "91 187 93", "500": "0 146 87",
            "600": "27 127 79", "700": "20 101 74", "800": "11 59 38",
            "900": "11 59 38", "950": "6 36 23",
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "navigation": [
            {
                "title": "Panel",
                "items": [
                    {"title": "Inicio", "icon": "dashboard",
                     "link": lambda r: reverse_lazy("admin:index")},
                ],
            },
            {
                "title": "Contenido",
                "items": [
                    {"title": "Medidas", "icon": "eco",
                     "link": lambda r: reverse_lazy("admin:medidas_medida_changelist")},
                    {"title": "Medidas - Fichas ACC", "icon": "fact_check",
                     "link": lambda r: reverse_lazy("admin:medidas_medidafichaacc_changelist")},
                    {"title": "Normativa", "icon": "gavel",
                     "link": lambda r: reverse_lazy("admin:normativa_norma_changelist")},
                    {"title": "Normativa - Entidades emisoras", "icon": "account_balance",
                     "link": lambda r: reverse_lazy(
                         "admin:normativa_entidademisora_changelist")},
                    {"title": "Noticias", "icon": "feed",
                     "link": lambda r: reverse_lazy("admin:contenidos_noticia_changelist")},
                    {"title": "Videos", "icon": "play_circle",
                     "link": lambda r: reverse_lazy("admin:contenidos_video_changelist")},
                    {"title": "Eventos", "icon": "event",
                     "link": lambda r: reverse_lazy("admin:contenidos_evento_changelist")},
                    {"title": "Biblioteca", "icon": "library_books",
                     "link": lambda r: reverse_lazy("admin:biblioteca_documento_changelist")},
                ],
            },
            {
                "title": "Datos",
                "items": [
                    {"title": "Cargas de datos", "icon": "upload_file",
                     "link": lambda r: reverse_lazy("admin:datasets_datasetupload_changelist")},
                    {"title": "Centros poblados", "icon": "location_city",
                     "link": lambda r: reverse_lazy("admin:territorio_centropoblado_changelist")},
                    {"title": "Clasificaciones", "icon": "warning",
                     "link": lambda r: reverse_lazy(
                         "admin:peligros_clasificacionpeligro_changelist")},
                    {"title": "Emergencias", "icon": "crisis_alert",
                     "link": lambda r: reverse_lazy(
                         "admin:peligros_frecuenciaemergencia_changelist")},
                ],
            },
            {
                "title": "Inversión (PP 0068)",
                "items": [
                    {"title": "Ejercicios", "icon": "event_available",
                     "link": lambda r: reverse_lazy("admin:inversion_ejercicio_changelist")},
                    {"title": "Presupuesto por entidad", "icon": "payments",
                     "link": lambda r: reverse_lazy(
                         "admin:inversion_presupuestoentidad_changelist")},
                    {"title": "Procesos de la GRD", "icon": "rule",
                     "link": lambda r: reverse_lazy(
                         "admin:inversion_clasificacionactividad_changelist")},
                    {"title": "Entidades ejecutoras", "icon": "account_balance",
                     "link": lambda r: reverse_lazy(
                         "admin:inversion_entidadejecutora_changelist")},
                ],
            },
            {
                "title": "Mapa",
                "items": [
                    {"title": "Capas cartográficas", "icon": "layers",
                     "link": lambda r: reverse_lazy("admin:mapas_capacartografica_changelist")},
                ],
            },
            {
                "title": "Sitio",
                "items": [
                    {"title": "Configuración", "icon": "settings",
                     "link": lambda r: reverse_lazy(
                         "admin:sitio_configuracionsitio_changelist")},
                    {"title": "Textos", "icon": "text_fields",
                     "link": lambda r: reverse_lazy("admin:sitio_bloquetexto_changelist")},
                    {"title": "Hero de portada", "icon": "wallpaper",
                     "link": lambda r: reverse_lazy("admin:sitio_heroslide_changelist")},
                    {"title": "Menú", "icon": "menu",
                     "link": lambda r: reverse_lazy("admin:sitio_enlacemenu_changelist")},
                ],
            },
            {
                "title": "Uso y usuarios",
                "items": [
                    {"title": "Resumen diario", "icon": "insights",
                     "link": lambda r: reverse_lazy("admin:metricas_resumendiario_changelist")},
                    {"title": "Usuarios", "icon": "person",
                     "link": lambda r: reverse_lazy("admin:auth_user_changelist")},
                    {"title": "Grupos", "icon": "group",
                     "link": lambda r: reverse_lazy("admin:auth_group_changelist")},
                ],
            },
        ],
    },
}

# --- CKEditor 5 (ADR-D2) ---------------------------------------------------
# Barra corta a propósito: cuanto menos HTML raro se pueda generar, menos hay que sanear
# y menos formas hay de romper la maqueta. Sin h1: ese es el título de la página.
CKEDITOR_5_CONFIGS = {
    "default": {
        "language": "es",
        "toolbar": [
            "heading", "|",
            "bold", "italic", "link", "bulletedList", "numberedList", "blockQuote", "|",
            "insertTable", "imageUpload", "mediaEmbed", "|",
            "undo", "redo",
        ],
        "heading": {
            "options": [
                {"model": "paragraph", "title": "Párrafo", "class": "ck-heading_paragraph"},
                {"model": "heading2", "view": "h2", "title": "Título 2"},
                {"model": "heading3", "view": "h3", "title": "Título 3"},
                {"model": "heading4", "view": "h4", "title": "Título 4"},
            ]
        },
        "image": {
            "toolbar": ["imageTextAlternative", "imageStyle:inline", "imageStyle:block",
                        "imageStyle:side"],
        },
        "table": {"contentToolbar": ["tableColumn", "tableRow", "mergeTableCells"]},
    }
}
# Destino de las imágenes que se insertan desde el editor. Lo aplica **nuestro storage**, no la
# librería: `django-ckeditor-5` ignora este ajuste (guarda con `fs.save(f.name, f)`, sin prefijo) y
# sin el storage las imágenes caían en la raíz de `media/`. Admite `strftime`, como `upload_to`.
CKEDITOR_5_UPLOAD_PATH = "contenido/%Y/%m/"
CKEDITOR_5_FILE_STORAGE = "apps.core.almacenamiento.AlmacenamientoContenido"
CKEDITOR_5_FILE_UPLOAD_PERMISSION = "staff"
# Una foto de campo sin recortar ronda los 6 MB; se aceptan y se reescalan al guardar (el reescalado
# lo hace `AlmacenamientoContenido`, y solo para las imágenes del editor).
CKEDITOR_5_MAX_FILE_SIZE = 10  # MB
CONTENIDO_ANCHO_MAXIMO_PX = 1600

# --- django-tasks (cola en BD, procesada por el servicio `worker`) ---------
TASKS = {
    "default": {"BACKEND": "django_tasks_db.DatabaseBackend", "QUEUES": ["default"]},
}

# --- Correo (flujo editorial) ---------------------------------------------
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="observatorio@predes.org.pe")
if not EMAIL_HOST:
    # Sin SMTP configurado los correos van a consola (dev).
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# --- Servicios externos ----------------------------------------------------
MEILI_URL = env("MEILI_URL", default="http://meilisearch:7700")
MEILI_MASTER_KEY = env("MEILI_MASTER_KEY", default="")
GEMINI_API_KEY = env("GEMINI_API_KEY", default="")
GEMINI_MODELO = env("GEMINI_MODELO", default="gemini-2.5-flash")
# OpenRouter (ADR-A22): pasarela de IA de propósito general. Un solo secreto y un solo cliente
# para cualquier modelo; el modelo se elige por variable de entorno y no por código.
OPENROUTER_API_KEY = env("OPENROUTER_API_KEY", default="")
# Medido el 28/08/2026 contra el API real, los tres consumidores y las mismas entradas: con
# `deepseek/deepseek-v4-flash-0731` el contenido volvió **sin etiquetas HTML** en 4 de 6 llamadas
# —incluida la noticia entera, 1.063 caracteres de texto corrido—, dio tres redacciones distintas
# de la misma ficha ACC y dedujo `estado_vigencia="vigente"` que el prompt prohíbe deducir. Con
# éste, 7 de 7 con etiquetas, cero avisos y la misma clasificación en las tres repeticiones. Cuesta
# ~20 veces más: $0.0028 contra $0.00007 por registro, que son $3 por cada mil frente a $0.10.
OPENROUTER_MODELO = env("OPENROUTER_MODELO", default="google/gemini-2.5-flash")
OPENROUTER_BASE_URL = env("OPENROUTER_BASE_URL", default="https://openrouter.ai/api/v1")
# El timeout y el reintento con backoff que 03 pedía y que la integración con Gemini nunca llegó
# a implementar. Aquí no hay que escribirlos: el cliente de `openai` los trae, basta pasárselos.
OPENROUTER_TIMEOUT = env.float("OPENROUTER_TIMEOUT", default=60.0)
OPENROUTER_REINTENTOS = env.int("OPENROUTER_REINTENTOS", default=1)
# Cómo lee OpenRouter un PDF adjunto (plugin `file-parser`, ADR-D8). `pdf-text` extrae la capa
# de texto y **no se cobra**, que es lo que sirve para las normas del diario oficial. Un PDF
# escaneado no tiene capa de texto y con este motor vuelve en blanco: ahí se cambia a
# `mistral-ocr`, que sí lo lee y se cobra por página. Es una perilla de entorno a propósito —
# escrita en código obligaría a desplegar para atender un caso que se ve una vez al mes.
OPENROUTER_PDF_ENGINE = env("OPENROUTER_PDF_ENGINE", default="pdf-text")
# Dónde queda el .txt con cada intercambio con la IA (entrada y salida). **Fuera de MEDIA_ROOT**:
# nginx sirve todo /media/ como estático público con CORS abierto, y un nombre como
# `ia-2026-08-28.txt` se adivina. Compose lo bind-monta al mismo directorio en el que ya escriben
# `desplegar.sh` y `vigilar-contenedores.sh`, que es donde mira quien opera.
IA_LOGS_DIR = Path(env("IA_LOGS_DIR", default=str(BASE_DIR / "logs")))

# Dónde espera el Excel de fichas ACC entre la pantalla de confirmación y el «Importar». También
# **fuera de MEDIA_ROOT**, y por lo mismo: son datos del cliente sin publicar, y /media/ es
# público. Se barre solo, pero es un directorio de paso: nada de aquí debe versionarse.
IMPORTACIONES_TMP_DIR = Path(env("IMPORTACIONES_TMP_DIR", default=str(BASE_DIR / "importaciones")))

# --- Datos y pipeline geoespacial ------------------------------------------
# Excel y GeoJSON canónicos que alimentan `manage.py seed`. Fuera de la imagen: son 145 MB
# que no se versionan (ver _docs/desarrollo.md).
DATOS_FUENTE_DIR = env("DATOS_FUENTE_DIR", default=str(BASE_DIR.parent / "data" / "layers"))
TIPPECANOE_BIN = env("TIPPECANOE_BIN", default="tippecanoe")
OGR2OGR_BIN = env("OGR2OGR_BIN", default="ogr2ogr")
# URL con la que el navegador headless que captura el mapa del PDF llega al propio backend.
RENDER_MAPA_BASE_URL = env("RENDER_MAPA_BASE_URL", default="http://localhost:8000")

# --- Seguridad producción --------------------------------------------------
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[SITE_URL])
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
