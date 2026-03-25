import logging

from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)


def get_storage_url(path):
    if not path:
        return None

    try:
        return default_storage.url(path)
    except Exception:
        logger.exception("Unable to build storage URL for path: %s", path)
        return None
