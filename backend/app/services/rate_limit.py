import os
from collections import defaultdict, deque
from threading import Lock
from time import time

from redis import Redis
from redis.exceptions import RedisError


class RateLimiter:
    def __init__(self) -> None:
        self.available = True
        self.hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str, limit: int, window: int = 3600) -> bool:
        if not self.available:
            return False
        with self._lock:
            now = time()
            bucket = self.hits[key]
            while bucket and bucket[0] <= now - window:
                bucket.popleft()
            if len(bucket) >= limit:
                return False
            bucket.append(now)
            return True

    def check_many(self, checks: list[tuple[str, int, int]]) -> bool:
        if not self.available:
            return False
        with self._lock:
            now = time()
            buckets = []
            for key, limit, window in checks:
                bucket = self.hits[key]
                while bucket and bucket[0] <= now - window:
                    bucket.popleft()
                if len(bucket) >= limit:
                    return False
                buckets.append(bucket)
            for bucket in buckets:
                bucket.append(now)
            return True


class RedisRateLimiter:
    """Atomic fixed-window limiter. Redis errors fail closed."""

    def __init__(self, url: str) -> None:
        self.client = Redis.from_url(url, decode_responses=True, socket_connect_timeout=2)
        self.client.ping()

    def check(self, key: str, limit: int, window: int = 3600) -> bool:
        try:
            value = self.client.incr(f"rate:{key}")
            if value == 1:
                self.client.expire(f"rate:{key}", window)
            return value <= limit
        except RedisError:
            return False

    def check_many(self, checks: list[tuple[str, int, int]]) -> bool:
        script = """
        for i = 1, #KEYS do
          local limit = tonumber(ARGV[(i - 1) * 2 + 1])
          local current = tonumber(redis.call('GET', KEYS[i]) or '0')
          if current >= limit then
            return 0
          end
        end
        for i = 1, #KEYS do
          local window = tonumber(ARGV[(i - 1) * 2 + 2])
          local value = redis.call('INCR', KEYS[i])
          if value == 1 then
            redis.call('EXPIRE', KEYS[i], window)
          end
        end
        return 1
        """
        try:
            keys = [f"rate:{key}" for key, _limit, _window in checks]
            args = [
                item
                for _key, limit, window in checks
                for item in (str(limit), str(window))
            ]
            return bool(self.client.eval(script, len(keys), *keys, *args))
        except RedisError:
            return False


def create_limiter():
    durable_local = os.getenv("USE_DURABLE_LOCAL", "false").lower() == "true"
    if os.getenv("APP_ENV", "local") == "local" and not durable_local:
        return RateLimiter()
    url = os.getenv("URL_CSDL_REDIS")
    if not url:
        raise RuntimeError("URL_CSDL_REDIS is required outside local mode")
    return RedisRateLimiter(url)


limiter = create_limiter()
