import json
import logging
from typing import Any, Optional

from config import REDIS_ENABLED, REDIS_URL


logger = logging.getLogger(__name__)


class RedisCache:
    """Redis cache with an in-memory fallback for local demos."""

    def __init__(self):
        self._memory = {}
        self._redis = None
        if not REDIS_ENABLED:
            return
        try:
            import redis

            self._redis = redis.Redis.from_url(REDIS_URL, decode_responses=True)
            self._redis.ping()
        except Exception as exc:
            logger.warning("Redis unavailable, using in-memory fallback: %s", exc)
            self._redis = None

    def get_json(self, key: str) -> Optional[Any]:
        if self._redis:
            value = self._redis.get(key)
            return json.loads(value) if value else None
        return self._memory.get(key)

    def set_json(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        if self._redis:
            payload = json.dumps(value, ensure_ascii=False)
            self._redis.set(key, payload, ex=ttl_seconds)
            return
        self._memory[key] = value

    def delete(self, key: str) -> None:
        if self._redis:
            self._redis.delete(key)
        else:
            self._memory.pop(key, None)


redis_cache = RedisCache()
