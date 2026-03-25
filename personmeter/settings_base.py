import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent

dotenv_path = BASE_DIR / ".env"
load_dotenv(dotenv_path=dotenv_path)


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=None):
    value = os.getenv(name)
    if not value:
        return list(default or [])
    return [item.strip() for item in value.split(",") if item.strip()]


def env_int(name, default=0):
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ImproperlyConfigured(f"{name} must be an integer.") from exc


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", ["127.0.0.1", "localhost"])

LOGIN_REDIRECT_URL = "home"
LOGIN_URL = "login"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "core",
    "crispy_forms",
    "crispy_bootstrap5",
    "storages",
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

ROOT_URLCONF = "personmeter.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "personmeter.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / os.getenv("SQLITE_NAME", "db.sqlite3"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", False)
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", False)

PERSONMETER_S3_PRESIGNED_URLS = env_bool("PERSONMETER_S3_PRESIGNED_URLS", False)
PERSONMETER_S3_PRESIGNED_URL_EXPIRATION = env_int(
    "PERSONMETER_S3_PRESIGNED_URL_EXPIRATION",
    3600,
)

PERSONMETER_MAX_IMAGE_UPLOAD_MB = env_int("PERSONMETER_MAX_IMAGE_UPLOAD_MB", 5)
PERSONMETER_MAX_IMAGE_UPLOAD_BYTES = PERSONMETER_MAX_IMAGE_UPLOAD_MB * 1024 * 1024
PERSONMETER_MAX_IMAGE_PIXELS = env_int("PERSONMETER_MAX_IMAGE_PIXELS", 25_000_000)

_default_allowed_image_mime_types = [
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
]
_default_allowed_image_extensions = [
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
]
_default_allowed_image_formats = [
    "JPEG",
    "PNG",
    "WEBP",
    "GIF",
]

PERSONMETER_ALLOWED_IMAGE_MIME_TYPES = tuple(
    mime.lower()
    for mime in env_list(
        "PERSONMETER_ALLOWED_IMAGE_MIME_TYPES",
        _default_allowed_image_mime_types,
    )
)
PERSONMETER_ALLOWED_IMAGE_EXTENSIONS = tuple(
    (extension if extension.startswith(".") else f".{extension}").lower()
    for extension in env_list(
        "PERSONMETER_ALLOWED_IMAGE_EXTENSIONS",
        _default_allowed_image_extensions,
    )
)
PERSONMETER_ALLOWED_IMAGE_FORMATS = tuple(
    image_format.upper()
    for image_format in env_list(
        "PERSONMETER_ALLOWED_IMAGE_FORMATS",
        _default_allowed_image_formats,
    )
)
