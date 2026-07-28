import asyncio
import time


class DomainRateLimiter:
    """Serializes and throttles requests per-domain so a job can't hammer a target site."""

    def __init__(self, min_interval_seconds: float) -> None:
        self.min_interval_seconds = min_interval_seconds
        self._last_request_at: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def wait(self, domain: str) -> None:
        async with self._lock:
            now = time.monotonic()
            last = self._last_request_at.get(domain, 0.0)
            delay = max(0.0, self.min_interval_seconds - (now - last))
            self._last_request_at[domain] = now + delay
        if delay > 0:
            await asyncio.sleep(delay)
