import time
from typing import Protocol
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx


class RobotsCheckerProtocol(Protocol):
    async def allowed(self, url: str, client: httpx.AsyncClient) -> bool: ...


class RobotsChecker:
    """Fetches and caches robots.txt per-domain, honouring it before any fetch."""

    def __init__(self, user_agent: str, cache_seconds: int = 3600) -> None:
        self.user_agent = user_agent
        self.cache_seconds = cache_seconds
        self._cache: dict[str, tuple[float, RobotFileParser]] = {}

    async def allowed(self, url: str, client: httpx.AsyncClient) -> bool:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        parser = await self._get_parser(origin, client)
        if parser is None:
            return True
        return parser.can_fetch(self.user_agent, url)

    async def _get_parser(self, origin: str, client: httpx.AsyncClient) -> RobotFileParser | None:
        cached = self._cache.get(origin)
        now = time.monotonic()
        if cached and now - cached[0] < self.cache_seconds:
            return cached[1]
        parser = RobotFileParser()
        robots_url = urljoin(origin, "/robots.txt")
        try:
            response = await client.get(robots_url, timeout=10)
        except httpx.HTTPError:
            # No reachable robots.txt: default to allowed. RobotFileParser()
            # disallows everything until parse() is called, so an empty
            # ruleset must be parsed explicitly to get that default.
            parser.parse([])
            self._cache[origin] = (now, parser)
            return parser
        if response.status_code >= 400:
            parser.parse([])
            self._cache[origin] = (now, parser)
            return parser
        parser.parse(response.text.splitlines())
        self._cache[origin] = (now, parser)
        return parser
