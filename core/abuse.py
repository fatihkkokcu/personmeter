import time
from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone


def consume_rate_limit(scope, actor_id, limit, window_seconds):
    now = int(time.time())
    bucket = now // window_seconds
    key = f"abuse:{scope}:{actor_id}:{bucket}"
    current = cache.get(key, 0)

    if current >= limit:
        retry_after = window_seconds - (now % window_seconds)
        return False, retry_after

    if current == 0:
        cache.add(key, 1, timeout=window_seconds)
    else:
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, current + 1, timeout=window_seconds)

    return True, 0


def is_flooding(last_action_at, min_interval_seconds):
    if not last_action_at:
        return False
    return timezone.now() - last_action_at < timedelta(seconds=min_interval_seconds)
