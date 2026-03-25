#!/bin/sh
set -eu

if [ "${PERSONMETER_RUN_MIGRATIONS:-0}" = "1" ]; then
    python manage.py migrate --noinput
fi

if [ "${PERSONMETER_COLLECTSTATIC:-1}" = "1" ]; then
    python manage.py collectstatic --noinput
fi

if [ "$#" -eq 0 ]; then
    set -- gunicorn personmeter.wsgi:application \
        --bind "0.0.0.0:${PORT:-8000}" \
        --workers "${GUNICORN_WORKERS:-3}" \
        --timeout "${GUNICORN_TIMEOUT:-120}"
fi

exec "$@"
