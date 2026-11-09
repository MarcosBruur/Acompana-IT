"""Ventanas deslizantes locales; para varios procesos se necesita un limitador compartido."""

from collections import defaultdict, deque
from threading import Lock
from time import monotonic


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
