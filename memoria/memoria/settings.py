import os
from pathlib import Path
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-key")
DEBUG = os.getenv("DEBUG", "True") == "True"

ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "memoria.urls"

TEMPLATES = [
    ***REMOVED***
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": ***REMOVED***
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
         ***REMOVED***,
      ***REMOVED***
  ***REMOVED***
]

WSGI_APPLICATION = "memoria.wsgi.application"

DATABASES = ***REMOVED***
    "default": dj_database_url.config(
        default=f"sqlite:///***REMOVED***BASE_DIR / 'db.sqlite3'***REMOVED***"
        if DEBUG
        else os.getenv("SUPABASE_DATABASE_URL")
    )
***REMOVED***

AUTH_PASSWORD_VALIDATORS = [
    ***REMOVED***
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
  ***REMOVED***
    ***REMOVED***"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"***REMOVED***,
    ***REMOVED***"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"***REMOVED***,
    ***REMOVED***"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"***REMOVED***,
]

LANGUAGE_CODE = "es-uy"
TIME_ZONE = "America/Montevideo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Configuración de Django REST Framework
REST_FRAMEWORK = ***REMOVED***
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ),
***REMOVED***


LOGGING = ***REMOVED***
    "version": 1,  # the dictConfig format version
    "disable_existing_loggers": False,  # retain the default loggers
***REMOVED***
