"""TTL cache in front of the task store."""
import time


class TTLCache:
    def __init__(self, ttl_seconds):
        self.ttl = ttl_seconds
        self._data = {}

    def get(self, key):
        entry = self._data.get(key)
        if entry is None:
            return None
        value, stored_at = entry
        if time.monotonic() - stored_at > self.ttl:
            del self._data[key]
            return None
        return value

    def set(self, key, value):
        self._data[key] = (value, time.monotonic())

    def invalidate(self, key):
        self._data.pop(key, None)

    def invalidate_prefix(self, prefix):
        for k in [k for k in self._data if k.startswith(prefix)]:
            del self._data[k]

    def clear(self):
        self._data.clear()
