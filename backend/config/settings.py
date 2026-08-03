"""Settings del Observatorio Kallpachakuy.

Toda la configuración sensible o dependiente del entorno se lee de
variables de entorno / backend/.env (django-environ). Ver .env.example.
"""
from pathlib import Path

import environ

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
ADMIN_URL = env("ADMIN_URL", default="admin/")

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
    "apps.datasets",
    "apps.medidas",
    "apps.normativa",
    "apps.biblioteca",
    "apps.contenidos",
    "apps.sitio",
    "apps.mapas",
    "apps.metricas",
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
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- DRF -------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
    "DEFAULT_PAGINATION_CLASS": "apps.api.paginacion.PaginacionEstandar",
    "PAGE_SIZE": 50,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.AnonRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "1000/hour",
        # Los exports y el PDF cuestan mucho más que una lectura: un bucle de descargas
        # tumbaría el worker antes que el API.
        "descarga": "30/hour",
        "beacon": "60/min",
    },
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
CKEDITOR_5_UPLOAD_PATH = "contenido/"
CKEDITOR_5_FILE_UPLOAD_PERMISSION = "staff"
# Una foto de campo sin recortar ronda los 6 MB; se aceptan y se reescalan al guardar.
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
