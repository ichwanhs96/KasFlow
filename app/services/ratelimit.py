import threading
import time
from collections import deque


class SlidingWindowLimiter:
    """At most `limit` acquisitions per `window_s` seconds. Thread-safe; in-process only.

    Production runs a single Cloud Run instance (`--max-instances 1`), so this is a global limit.
    """

    def __init__(self, limit: int, window_s: float, clock=time.monotonic) -> None:
        self.limit = limit
        self.window_s = window_s
        self.clock = clock
        self._hits: deque[float] = deque()
        self._lock = threading.Lock()

    def try_acquire(self) -> bool:
        with self._lock:
            now = self.clock()
            while self._hits and now - self._hits[0] >= self.window_s:
                self._hits.popleft()
            if len(self._hits) >= self.limit:
                return False
            self._hits.append(now)
            return True
