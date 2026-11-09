"""Sliding-window rate limiter."""
import threading
import time


class SlidingWindowLimiter:
    """Allows at most `limit` acquisitions per `window` seconds.

    When the limit is hit, requests receive a 429 rather than blocking
    (fair for an API; the caller retries after the window slides).

    Thread-safe: the sliding window is only ever mutated under an internal
    lock, so concurrent try_acquire calls cannot race or miscount.
    """

    def __init__(self, limit, window):
        self.limit = limit
        self.window = window
        self._lock = threading.Lock()
        self._events = []

    def try_acquire(self):
        """Return (allowed, retry_after_seconds)."""
        with self._lock:
            now = time.monotonic()
            self._events = [t for t in self._events if now - t < self.window]
            if len(self._events) >= self.limit:
                retry_after = max(0.0, self.window - (now - self._events[0]))
                return False, retry_after
            self._events.append(now)
            return True, 0.0
