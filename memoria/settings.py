import os
from pathlib import Path
import dj_database_url
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-key")
DEBUG = os.getenv("DEBUG", "True") == "True"
VERBOSE_LOGGING = os.getenv("VERBOSE_LOGGING", str(DEBUG)) == "True"

# Database URL - Railway uses DATABASE_URL, Supabase uses SUPABASE_DATABASE_URL
DATABASE_URL_ENV = os.getenv("DATABASE_URL", os.getenv("SUPABASE_DATABASE_URL", None))

# ALLOWED_HOSTS - Railway provides RAILWAY_PUBLIC_DOMAIN
allowed_hosts = os.getenv("ALLOWED_HOSTS", "*").split(",")
railway_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN")
if railway_domain:
    allowed_hosts.append(railway_domain)
ALLOWED_HOSTS = [host.strip() for host in allowed_hosts if host.strip()]

# CSRF trusted origins - split by comma to support multiple domains
csrf_origins = os.getenv("CSRF_TRUSTED_ORIGINS", "https://memoria.uy").split(",")
if railway_domain:
    csrf_origins.append(f"https://{railway_domain}")
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in csrf_origins]


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "corsheaders",
    "django_browser_reload",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "rest_framework",
    "tailwind",
    "theme",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

# Only add browser reload middleware in DEBUG mode
if DEBUG:
    MIDDLEWARE.append("django_browser_reload.middleware.BrowserReloadMiddleware")

ROOT_URLCONF = "memoria.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            BASE_DIR / "templates",
            os.path.join(BASE_DIR, "memoria", "templates"),
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.request",
            ],
        },
    },
]
TEMPLATE_DEBUG = True

WSGI_APPLICATION = "memoria.wsgi.application"

# Get database URL based on environment
default_db_url = (
    f"sqlite:///{BASE_DIR / 'db.sqlite3'}" if not DATABASE_URL_ENV else DATABASE_URL_ENV
)

# Configure the database
DATABASES = {"default": dj_database_url.config(default=default_db_url)}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es-uy"
TIME_ZONE = "America/Montevideo"
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.1/howto/static-files/

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# WhiteNoise configuration for serving static files
# CompressedStaticFilesStorage works without manifest
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

# Media files configuration
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Configuración de Django REST Framework
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ),
}


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{levelname}] {asctime} {name}: {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "DEBUG" if VERBOSE_LOGGING else "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "core": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "allauth": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
        "django.core.mail": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}

# Cache configuration for task locking, rate limiting, and report snapshots
# Using Redis for persistence and sharing across workers
redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": redis_url,
        "KEY_PREFIX": "memoria_cache",
        "TIMEOUT": 3600,  # Default timeout 1 hour
    }
}

# Rate limiting configuration
RATELIMIT_ENABLE = os.getenv("RATELIMIT_ENABLE", "True") == "True"
RATELIMIT_USE_CACHE = "default"


AUTHENTICATION_BACKENDS = [
    # Needed to login by username in Django admin, regardless of `allauth`
    "django.contrib.auth.backends.ModelBackend",
    # `allauth` specific authentication methods, such as login by email
    "allauth.account.auth_backends.AuthenticationBackend",
]

LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
ACCOUNT_ADAPTER = "memoria.adapter.CustomAccountAdapter"

# Email confirmation redirects
ACCOUNT_EMAIL_CONFIRMATION_ANONYMOUS_REDIRECT_URL = "/"  # Redirige a timeline
ACCOUNT_EMAIL_CONFIRMATION_AUTHENTICATED_REDIRECT_URL = "/"  # Redirige a timeline después de confirmar

# A custom variable we created to tell the CustomAccountAdapter whether to
# allow signups.
ACCOUNT_ALLOW_SIGNUPS = os.getenv("ACCOUNT_ALLOW_SIGNUPS", "False") == "True"

# Email configuration (Resend HTTP API by default)
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND", "core.email_backends.resend.ResendEmailBackend"
)
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
RESEND_API_URL = os.getenv("RESEND_API_URL", "https://api.resend.com/emails")

# SMTP fallback configuration (not used by default)
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.resend.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "resend")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True") == "True"
EMAIL_USE_SSL = False
DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL", "memoria.uy <noreply@memoria.uy>"
)
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# Django-allauth configuration
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_EMAIL_VERIFICATION = os.getenv("ACCOUNT_EMAIL_VERIFICATION", "mandatory")
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_SESSION_REMEMBER = True
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True  # Auto-login after email confirmation
SOCIALACCOUNT_AUTO_SIGNUP = True
ACCOUNT_FORMS = {
    'signup': 'core.forms.CustomSignupForm',
}

TAILWIND_APP_NAME = "theme"


INTERNAL_IPS = ["127.0.0.1"]

# Celery Configuration
# Using Redis as broker and result backend
CELERY_BROKER_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = os.getenv("REDIS_URL", "redis://redis:6379/0")

CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

# CORS Configuration for Browser Extension
# Allow extensions to communicate with API
CORS_ALLOW_ALL_ORIGINS = DEBUG
cors_allowed = os.getenv(
    "CORS_ALLOWED_ORIGINS", "http://localhost:8000,https://memoria.uy"
).split(",")
if railway_domain:
    cors_allowed.append(f"https://{railway_domain}")
CORS_ALLOWED_ORIGINS = [origin.strip() for origin in cors_allowed]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    "x-extension-session",
]
