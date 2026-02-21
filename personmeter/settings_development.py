import os

from .settings_base import *  # noqa: F403,F401


DEBUG = env_bool("DJANGO_DEBUG", True)  # noqa: F405
SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "django-insecure-dev-only-key-change-me",
)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", ["127.0.0.1", "localhost"])  # noqa: F405

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / os.getenv("SQLITE_NAME", "db.sqlite3"),  # noqa: F405
    }
}

SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
