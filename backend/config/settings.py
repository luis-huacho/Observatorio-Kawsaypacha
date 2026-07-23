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
ADMIN_URL = env("ADMIN_URL", default="admin/")

INSTALLED_APPS = [
    # Theme del admin: debe ir antes de django.contrib.admin.
    "unfold",
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
    # Apps del proyecto
    "apps.core",
    "apps.territorio",
    "apps.peligros",
    "apps.datasets",
    "apps.api",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
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
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_RATES": {"anon": "120/min"},
}

SPECTACULAR_SETTINGS = {
    "TITLE": "API Observatorio Kallpachakuy",
    "DESCRIPTION": "API pública de solo lectura del Observatorio GRD y ACC de Cusco.",
    "VERSION": "0.1.0",
}

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

# --- Seguridad producción --------------------------------------------------
if not DEBUG:
    CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[SITE_URL])
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
