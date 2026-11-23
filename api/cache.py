"""Small in-memory LRU cache with a time-to-live, for the expensive ``/sensitivity`` answers (one call costs ~0.5 s).

Per process (each server instance has its own); thread-safe; the clock is injectable so tests can expire entries without sleeping.
"""
import hashlib
import json
import threading
import time
from collections import OrderedDict


def cache_key(*parts):
    """Stable hash of JSON-able parts (dict key order does not matter)."""
    raw = json.dumps(parts, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


class TTLCache:
    def __init__(self, max_entries=128, ttl_s=600, clock=time.monotonic):
        self.max_entries, self.ttl, self.clock = max_entries, ttl_s, clock
        self._data = OrderedDict()                 # key -> (expires_at, value), least recently used first
        self._lock = threading.Lock()
        self.hits = self.misses = 0

    @property
    def enabled(self):
        return self.max_entries > 0

    def get(self, key):
        if not self.enabled:
            return None
        now = self.clock()
        with self._lock:
            item = self._data.get(key)
            if item is None or item[0] <= now:
                self._data.pop(key, None)
                self.misses += 1
                return None
            self._data.move_to_end(key)
            self.hits += 1
            return item[1]

    def put(self, key, value):
        if not self.enabled:
            return
        with self._lock:
            self._data[key] = (self.clock() + self.ttl, value)
            self._data.move_to_end(key)
            while len(self._data) > self.max_entries:
                self._data.popitem(last=False)

    def __len__(self):
        return len(self._data)
