import os

from django.core.exceptions import ImproperlyConfigured

from .settings_base import *  # noqa: F403,F401


DEBUG = env_bool("DJANGO_DEBUG", False)  # noqa: F405
if DEBUG:
    raise ImproperlyConfigured("DJANGO_DEBUG must be false in production.")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set for production.")

ALLOWED_HOSTS = env_list(  # noqa: F405
    "DJANGO_ALLOWED_HOSTS",
    ["personmeter.net", "www.personmeter.net"],
)
if "*" in ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS cannot contain '*' in production.")

required_db_vars = ["DB_NAME", "DB_USER", "DB_PASSWORD", "DB_HOST", "DB_PORT"]
missing_db_vars = [key for key in required_db_vars if not os.getenv(key)]
if missing_db_vars:
    raise ImproperlyConfigured(
        f"Missing database environment variables: {', '.join(missing_db_vars)}"
    )

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME"),
        "USER": os.getenv("DB_USER"),
        "PASSWORD": os.getenv("DB_PASSWORD"),
        "HOST": os.getenv("DB_HOST"),
        "PORT": os.getenv("DB_PORT"),
    }
}

required_aws_vars = [
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_STORAGE_BUCKET_NAME",
    "AWS_S3_REGION_NAME",
]
missing_aws_vars = [key for key in required_aws_vars if not os.getenv(key)]
if missing_aws_vars:
    raise ImproperlyConfigured(
        f"Missing AWS environment variables: {', '.join(missing_aws_vars)}"
    )

aws_bucket = os.getenv("AWS_STORAGE_BUCKET_NAME")
aws_region = os.getenv("AWS_S3_REGION_NAME")

STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "access_key": os.getenv("AWS_ACCESS_KEY_ID"),
            "secret_key": os.getenv("AWS_SECRET_ACCESS_KEY"),
            "bucket_name": aws_bucket,
            "region_name": aws_region,
            "custom_domain": f"{aws_bucket}.s3.{aws_region}.amazonaws.com",
            "file_overwrite": False,
            "default_acl": None,
            "querystring_auth": PERSONMETER_S3_PRESIGNED_URLS,  # noqa: F405
            "querystring_expire": PERSONMETER_S3_PRESIGNED_URL_EXPIRATION,  # noqa: F405
        },
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

MEDIA_URL = f"https://{aws_bucket}.s3.{aws_region}.amazonaws.com/"
MEDIA_ROOT = ""

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = env_bool("DJANGO_USE_X_FORWARDED_HOST", True)  # noqa: F405
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)  # noqa: F405
SECURE_HSTS_SECONDS = env_int("DJANGO_SECURE_HSTS_SECONDS", 31_536_000)  # noqa: F405
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", True)  # noqa: F405
SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", True)  # noqa: F405
SECURE_CONTENT_TYPE_NOSNIFF = env_bool("DJANGO_SECURE_CONTENT_TYPE_NOSNIFF", True)  # noqa: F405
SECURE_REFERRER_POLICY = os.getenv(
    "DJANGO_SECURE_REFERRER_POLICY",
    "strict-origin-when-cross-origin",
)
X_FRAME_OPTIONS = os.getenv("DJANGO_X_FRAME_OPTIONS", "DENY")
WHITENOISE_MAX_AGE = env_int("DJANGO_WHITENOISE_MAX_AGE", 31536000)  # noqa: F405

_default_csrf_trusted_origins = [
    f"https://{host.lstrip('.')}"
    for host in ALLOWED_HOSTS
    if host and host != "*" and "://" not in host
]
CSRF_TRUSTED_ORIGINS = env_list(  # noqa: F405
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    _default_csrf_trusted_origins,
)
