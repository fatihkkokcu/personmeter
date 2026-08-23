"""
Local development settings.

Usage:
    python manage.py runserver --settings=personmeter.settings_local

Overrides the production setup (PostgreSQL + S3 + HTTPS cookies) with a
self-contained local one: SQLite database and filesystem media storage.
"""

from .settings import *  # noqa: F403

DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '[::1]']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',  # noqa: F405
    }
}

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'  # noqa: F405

# Cookies over plain HTTP in development
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_PROXY_SSL_HEADER = None
