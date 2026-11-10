"""Ventanas locales o compartidas en Redis con reservas y devolución atómicas."""

from collections import defaultdict, deque
from contextvars import ContextVar
from secrets import token_hex
from threading import Lock
from time import monotonic

import redis
from redis.exceptions import RedisError

from app.core.config import settings


class RateLimitUnavailable(Exception):
    """Redis configurado pero indisponible: fallar cerrado y devolver 503."""


CHECK_SCRIPT = """
local now = redis.call('TIME')
local millis = now[1] * 1000 + math.floor(now[2] / 1000)
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', millis - tonumber(ARGV[1]))
if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[2]) then return 0 end
redis.call('ZADD', KEYS[1], millis, ARGV[3])
redis.call('PEXPIRE', KEYS[1], tonumber(ARGV[1]))
return 1
"""


class DistributedWindow:
    def __init__(self, url: str, window: int = 3600):
        self.window = window
        self.client = redis.Redis.from_url(url, socket_connect_timeout=1, socket_timeout=1)
        self.reservations: ContextVar[dict[str, str] | None] = ContextVar("limit_reservations",
                                                                          default=None)

    @staticmethod
    def redis_key(key: str) -> str:
        return f"tfg:limit:{key}"

    def check(self, key: str, limit: int) -> bool:
        reservation = token_hex(16)
        try:
            allowed = self.client.eval(CHECK_SCRIPT, 1, self.redis_key(key),
                                       self.window * 1000, limit, reservation)
        except RedisError as exc:
            raise RateLimitUnavailable from exc
        if allowed:
            self.reservations.set({**(self.reservations.get() or {}), key: reservation})
        return bool(allowed)

    def refund(self, key: str) -> None:
        reservation = (self.reservations.get() or {}).get(key)
        if reservation:
            try:
                self.client.zrem(self.redis_key(key), reservation)
            except RedisError as exc:
                raise RateLimitUnavailable from exc

    def clear(self, key: str) -> None:
        try:
            self.client.delete(self.redis_key(key))
        except RedisError as exc:
            raise RateLimitUnavailable from exc


def shared_window() -> DistributedWindow | None:
    return DistributedWindow(settings.redis_url) if settings.redis_url else None

def prune_buckets(buckets: dict[str | int, deque[float]], now: float,
                  window: int = 3600) -> None:
    for key, values in list(buckets.items()):
        while values and values[0] <= now - window:
            values.popleft()
        if not values:
            del buckets[key]


class SlidingWindow:
    def __init__(self, window: int = 3600, max_keys: int = 30000):
        self.window = window
        self.max_keys = max_keys
        self.requests: dict[str, deque[float]] = defaultdict(deque)
        self.lock = Lock()
        self.last_cleanup = 0.0

    def check(self, key: str, limit: int) -> bool:
        with self.lock:
            now = monotonic()
            if now - self.last_cleanup >= 60:
                for old_key, values in list(self.requests.items()):
                    while values and values[0] <= now - self.window:
                        values.popleft()
                    if not values:
                        del self.requests[old_key]
                self.last_cleanup = now
            if key not in self.requests and len(self.requests) >= self.max_keys:
                return False
            values = self.requests[key]
            while values and values[0] <= now - self.window:
                values.popleft()
            if len(values) >= limit:
                return False
            values.append(now)
            return True

    def refund(self, key: str) -> None:
        with self.lock:
            values = self.requests.get(key)
            if values:
                values.pop()
                if not values:
                    del self.requests[key]

    def clear(self, key: str) -> None:
        with self.lock:
            self.requests.pop(key, None)
